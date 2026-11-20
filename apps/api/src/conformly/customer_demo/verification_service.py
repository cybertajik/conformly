"""Service implementation for V2 Customer Readiness Verification Lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.config import get_settings
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.customer_demo.fixture import get_bundle_by_version_id
from conformly.customer_demo.models import CustomerDemoAdoption
from conformly.customer_demo.policy import (
    CustomerDemoAdmissionError,
    CustomerDemoDatabaseAdmissionError,
    verify_customer_demo_admission,
)
from conformly.customer_demo.preaudit_models import (
    CustomerPreaudit,
    CustomerPreauditEvent,
    CustomerPreauditSnapshot,
)
from conformly.customer_demo.preaudit_service import CustomerPreauditService
from conformly.customer_demo.preaudit_snapshot import (
    decrypt_event_payload,
    decrypt_snapshot_payload,
)
from conformly.customer_demo.verification_crypto import (
    canonicalize_json,
    compute_digest,
    compute_valid_through,
    decrypt_verification_event_payload,
    decrypt_verification_payload,
    encrypt_verification_event_payload,
    encrypt_verification_payload,
)
from conformly.customer_demo.verification_models import (
    CustomerReadinessVerification,
    CustomerReadinessVerificationEvent,
)
from conformly.customer_demo.verification_projection import build_verification_projection
from conformly.customer_demo.verification_schemas import (
    SYNTHETIC_MARKER,
    TEST_QUALIFICATION,
    CorrectVerificationRequest,
    IssueVerificationRequest,
    ReconcileVerificationRequest,
    RevokeVerificationRequest,
    SupersedeVerificationRequest,
    SuspendVerificationRequest,
    VerificationDetailResponse,
    VerificationEventItem,
    VerificationHistoryResponse,
    VerificationListResponse,
    VerificationListSummary,
    VerificationProjectionResponse,
)
from conformly.identity.models import Membership, MembershipStatus, User, UserStatus
from conformly.tenancy.rls import set_rls_context


def verify_verification_database_connection(session: Session) -> None:
    """Verify runtime database connection is conformly_app non-owner for verification tables on PostgreSQL."""
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    row = session.execute(
        text("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
    ).first()
    if row is None:
        raise CustomerDemoDatabaseAdmissionError("Unable to verify PostgreSQL runtime identity")

    user_name, is_super, is_bypass = row[0], row[1], row[2]
    if is_super or is_bypass or user_name != "conformly_app":
        raise CustomerDemoDatabaseAdmissionError(
            f"Disallowed PostgreSQL runtime identity: {user_name} (superuser={is_super}, bypassrls={is_bypass})"
        )

    owned_tables = (
        session.execute(
            text(
                """
                SELECT c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_roles r ON r.oid = c.relowner
                WHERE c.relname IN (
                    'customer_readiness_verifications',
                    'customer_readiness_verification_events'
                )
                AND n.nspname = 'public'
                AND r.rolname = current_user
                """
            )
        )
        .scalars()
        .all()
    )
    if owned_tables:
        raise CustomerDemoDatabaseAdmissionError(
            f"Runtime user {user_name} must not own verification tables: {list(owned_tables)}",
        )



class CustomerVerificationService:
    """Manages private synthetic readiness verification results and lifecycle transitions."""

    def __init__(
        self,
        session: Session,
        codec: EncryptedFieldCodec | None = None,
        clock_override: datetime | None = None,
    ) -> None:
        self.session = session
        self.codec = codec or get_encrypted_field_codec()
        self._clock_override = clock_override
        self.preaudit_service = CustomerPreauditService(session, codec=self.codec)

    @property
    def clock_override(self) -> datetime | None:
        return self._clock_override

    @clock_override.setter
    def clock_override(self, val: datetime | None) -> None:
        self._clock_override = val

    def _get_clock(self) -> datetime:
        return self._clock_override or datetime.now(UTC)

    def _verify_admission(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        operation: str = "read",
    ) -> None:
        """Validate feature flags, environment boundaries and role authorization."""
        settings = get_settings()
        if not settings.enable_customer_readiness_verification:
            raise HTTPException(status_code=404, detail="Readiness verification feature is not enabled")
        if not settings.enable_customer_demo:
            raise HTTPException(status_code=404, detail="Customer demo feature is not enabled")
        if not settings.enable_customer_preaudit:
            raise HTTPException(status_code=404, detail="Pre-audit review feature is not enabled")
        if settings.environment not in ("local", "development", "test"):
            raise HTTPException(
                status_code=404,
                detail="Readiness verification prohibited in non-development environments",
            )

        verify_customer_demo_admission(
            principal,
            tenant_context,
            "mutate" if operation == "mutate" else "read",
            session=self.session,
        )
        verify_verification_database_connection(self.session)
        set_rls_context(
            self.session,
            user_id=principal.user_id,
            tenant_id=tenant_context.tenant_id,
            tenant_verified=True,
        )

        m = self.session.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.tenant_id == tenant_context.tenant_id,
                Membership.user_id == principal.user_id,
                Membership.status == MembershipStatus.ACTIVE,
                User.status == UserStatus.ACTIVE,
            )
        ).first()
        if not m or m[0].role != tenant_context.role:
            raise CustomerDemoAdmissionError(
                "Active membership with admitted role required",
                status_code=403,
            )

        if operation == "mutate":
            if tenant_context.role != Role.OWNER:
                raise HTTPException(
                    status_code=403,
                    detail="Only tenant Owner can manage readiness verification lifecycle",
                )
        else:
            # Read operations permitted for known tenant roles
            if tenant_context.role not in (
                Role.OWNER,
                Role.COMPLIANCE_MANAGER,
                Role.AUDITOR,
            ):
                raise HTTPException(status_code=403, detail="Role not permitted to view readiness verifications")

    def _check_idempotency(
        self,
        tenant_id: UUID,
        operation_id: UUID,
        expected_verification_id: UUID | None,
        expected_event_type: str,
        actor_user_id: UUID,
        request_digest: str,
    ) -> CustomerReadinessVerificationEvent | None:
        """Verify strict operation identity replay vs 409 conflict rejections."""
        event = self.session.execute(
            select(CustomerReadinessVerificationEvent).where(
                CustomerReadinessVerificationEvent.tenant_id == tenant_id,
                CustomerReadinessVerificationEvent.operation_id == operation_id,
            )
        ).scalar_one_or_none()
        if not event:
            return None

        if event.request_digest != request_digest:
            raise HTTPException(
                status_code=409,
                detail="Operation ID conflict: request payload altered from previous execution",
            )
        if event.event_type != expected_event_type:
            raise HTTPException(
                status_code=409,
                detail=f"Operation ID conflict: replayed against different action {event.event_type}",
            )
        if expected_verification_id and event.verification_id != expected_verification_id:
            raise HTTPException(
                status_code=409,
                detail="Operation ID conflict: replayed against different verification entity",
            )
        if event.actor_user_id != actor_user_id:
            raise HTTPException(
                status_code=409,
                detail="Operation ID conflict: replayed by different user actor",
            )
        return event

    def _compute_effective_status(
        self,
        verification: CustomerReadinessVerification,
        now: datetime,
    ) -> tuple[str, str | None]:
        """Compute effective lifecycle status and reason without mutating database records."""
        if verification.status in ("REVOKED", "EXPIRED", "SUPERSEDED"):
            return verification.status, None

        # Check time boundary first for ALL non-terminal statuses (ACTIVE and SUSPENDED)
        vt = verification.valid_through
        if vt.tzinfo is None:
            vt = vt.replace(tzinfo=UTC)
        check_now = now
        if check_now.tzinfo is None:
            check_now = check_now.replace(tzinfo=UTC)

        if check_now >= vt:
            return "EXPIRED", "12-month validity window has elapsed"

        if verification.status == "SUSPENDED":
            return "SUSPENDED", "Manually suspended by tenant Owner"

        # Check source currentness without mutating
        is_current, change_reason = self.preaudit_service.check_case_currency(
            verification.tenant_id,
            verification.preaudit_id,
            verification.snapshot_id,
            None,
        )
        if not is_current:
            return "SUSPENDED", change_reason or "Underlying compliance work has changed"

        return "ACTIVE", None

    def _freeze_case_provenance(
        self,
        tenant_id: UUID,
        case: CustomerPreaudit,
        r_snap: CustomerPreauditSnapshot,
        snap_payload: dict[str, Any],
        approval_event: CustomerPreauditEvent | None,
        v_id: UUID,
        now: datetime,
        valid_through: datetime,
        principal: Principal,
        limitations: list[str],
        notes: str | None,
        supersedes_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Assemble frozen cryptographic provenance from approved scope and review snapshots."""
        scope_payload: dict[str, Any] = {}
        if case.current_scope_snapshot_id:
            scope_snap = self.session.execute(
                select(CustomerPreauditSnapshot).where(
                    CustomerPreauditSnapshot.tenant_id == tenant_id,
                    CustomerPreauditSnapshot.id == case.current_scope_snapshot_id,
                )
            ).scalar_one_or_none()
            if not scope_snap:
                raise HTTPException(status_code=409, detail="Referenced scope snapshot not found")
            scope_payload = decrypt_snapshot_payload(
                self.codec,
                tenant_id,
                scope_snap.id,
                scope_snap.payload_encrypted,
                scope_snap.digest,
            )

        pack_version_id_str = scope_payload.get("pack_version_id")
        bundle: dict[str, Any] = {}
        if pack_version_id_str:
            try:
                bundle = get_bundle_by_version_id(UUID(pack_version_id_str))
            except Exception:
                pass

        if not bundle and case.adoption_id:
            adopt = self.session.execute(
                select(CustomerDemoAdoption).where(
                    CustomerDemoAdoption.tenant_id == tenant_id,
                    CustomerDemoAdoption.id == case.adoption_id,
                )
            ).scalar_one_or_none()
            if adopt and adopt.pack_version_id:
                try:
                    bundle = get_bundle_by_version_id(adopt.pack_version_id)
                except Exception:
                    pass

        work_items = snap_payload.get("work_items", [])
        if not work_items:
            raise HTTPException(status_code=409, detail="Cannot freeze verification from empty work set")

        pass_count = sum(1 for w in work_items if w.get("primary_state") == "PASS")
        na_count = sum(1 for w in work_items if w.get("primary_state") == "NOT_APPLICABLE")
        controls_count = len(work_items)
        covered_count = pass_count
        exempt_count = na_count
        not_applicable_count = na_count

        control_version_pins = scope_payload.get("control_version_pins")
        if not control_version_pins:
            control_version_pins = [w.get("control_version_id") for w in work_items if w.get("control_version_id")]

        bundle_digest = scope_payload.get("bundle_digest") or bundle.get("bundle_digest") or r_snap.digest
        framework_id = bundle.get("pack_id") or scope_payload.get("pack_id") or str(case.adoption_id)
        framework_version = bundle.get("version") or scope_payload.get("bundle_version") or "1.0.0"
        framework_display_name = bundle.get("name") or "Synthetic Customer Baseline Pack"

        # Evidence pins
        evidence_pins: list[dict[str, Any]] = []
        for w in work_items:
            c_id = w.get("control_version_id")
            for link in w.get("evidence_links", []):
                if not link.get("evidence_id") or link.get("revision_number") is None:
                    raise HTTPException(status_code=409, detail=f"Control {c_id} has incomplete evidence pin")
                pin_item = {
                    "control_version_id": str(c_id) if c_id else None,
                    "link_id": str(link.get("link_id")),
                    "evidence_id": str(link.get("evidence_id")),
                    "revision_number": int(link.get("revision_number")),
                    "revision_digest": str(link.get("revision_digest")),
                    "file_hash": str(link.get("file_hash")),
                    "latest_review_event_id": str(link.get("latest_review_event_id")) if link.get("latest_review_event_id") else None,
                }
                evidence_pins.append(pin_item)

        if pass_count > 0 and not evidence_pins:
            raise HTTPException(status_code=409, detail="Passing controls require verified evidence pins")

        # Independent review decision event
        review_event = self.session.execute(
            select(CustomerPreauditEvent)
            .where(
                CustomerPreauditEvent.tenant_id == tenant_id,
                CustomerPreauditEvent.preaudit_id == case.id,
                CustomerPreauditEvent.event_type == "REVIEWED",
                CustomerPreauditEvent.snapshot_id == r_snap.id,
            )
            .order_by(CustomerPreauditEvent.revision.desc())
        ).scalars().first()
        if not review_event:
            review_event = self.session.execute(
                select(CustomerPreauditEvent)
                .where(
                    CustomerPreauditEvent.tenant_id == tenant_id,
                    CustomerPreauditEvent.preaudit_id == case.id,
                    CustomerPreauditEvent.event_type == "REVIEWED",
                )
                .order_by(CustomerPreauditEvent.revision.desc())
            ).scalars().first()

        if not review_event:
            raise HTTPException(status_code=409, detail="Pre-audit case lacks recorded reviewer decision event")

        try:
            rev_payload = decrypt_event_payload(
                self.codec,
                tenant_id,
                review_event.id,
                review_event.payload_encrypted,
            )
        except Exception as e:
            raise HTTPException(status_code=409, detail=f"Corrupt or invalid review decision event ciphertext: {e}") from e

        reviewer_notes = rev_payload.get("notes")
        reviewer_decision = rev_payload.get("decision")
        if not reviewer_decision or reviewer_notes is None:
            raise HTTPException(status_code=409, detail="Review decision event missing required decision or notes")

        # Owner approval event
        if not approval_event:
            approval_event = self.session.execute(
                select(CustomerPreauditEvent)
                .where(
                    CustomerPreauditEvent.tenant_id == tenant_id,
                    CustomerPreauditEvent.preaudit_id == case.id,
                    CustomerPreauditEvent.event_type == "APPROVED",
                    CustomerPreauditEvent.snapshot_id == r_snap.id,
                )
                .order_by(CustomerPreauditEvent.revision.desc())
            ).scalars().first()
            if not approval_event:
                approval_event = self.session.execute(
                    select(CustomerPreauditEvent)
                    .where(
                        CustomerPreauditEvent.tenant_id == tenant_id,
                        CustomerPreauditEvent.preaudit_id == case.id,
                        CustomerPreauditEvent.event_type == "APPROVED",
                    )
                    .order_by(CustomerPreauditEvent.revision.desc())
                ).scalars().first()

        if not approval_event:
            raise HTTPException(status_code=409, detail="Pre-audit case lacks recorded Owner approval event")

        try:
            app_payload = decrypt_event_payload(
                self.codec,
                tenant_id,
                approval_event.id,
                approval_event.payload_encrypted,
            )
        except Exception as e:
            raise HTTPException(status_code=409, detail=f"Corrupt or invalid approval event ciphertext: {e}") from e

        approval_notes = app_payload.get("notes")

        payload_dict: dict[str, Any] = {
            "synthetic_marker": SYNTHETIC_MARKER,
            "test_qualification": TEST_QUALIFICATION,
            "verification_id": str(v_id),
            "preaudit_id": str(case.id),
            "snapshot_id": str(r_snap.id),
            "snapshot_digest": r_snap.digest,
            "adoption_id": str(case.adoption_id),
            "pack_version_id": str(bundle.get("pack_version_id")) if bundle.get("pack_version_id") else pack_version_id_str,
            "framework_id": str(framework_id),
            "framework_version": str(framework_version),
            "framework_display_name": framework_display_name,
            "organization_display_name": "Conformly Demo Organization",
            "bundle_digest": bundle_digest,
            "control_version_pins": control_version_pins,
            "evidence_pins": evidence_pins,
            "scope_summary": {
                "framework_id": str(framework_id),
                "version_id": str(framework_version),
                "controls_count": controls_count,
                "covered_count": covered_count,
                "exempt_count": exempt_count,
                "not_applicable_count": not_applicable_count,
            },
            "controls_count": controls_count,
            "covered_count": covered_count,
            "exempt_count": exempt_count,
            "not_applicable_count": not_applicable_count,
            "limitations": limitations or [],
            "issued_at": now.isoformat(),
            "valid_through": valid_through.isoformat(),
            "issuer_user_id": str(principal.user_id),
            "reviewer_user_id": str(case.reviewer_user_id),
            "approver_user_id": str(approval_event.actor_user_id if approval_event else principal.user_id),
            "review_event_id": str(review_event.id),
            "review_event_timestamp": review_event.created_at.isoformat() if review_event.created_at else now.isoformat(),
            "reviewer_decision": reviewer_decision,
            "reviewer_decision_notes": reviewer_notes,
            "approval_event_id": str(approval_event.id),
            "approval_event_timestamp": approval_event.created_at.isoformat() if approval_event.created_at else now.isoformat(),
            "owner_approval_notes": approval_notes,
            "notes": notes,
        }
        if supersedes_id:
            payload_dict["supersedes_id"] = str(supersedes_id)

        return payload_dict

    def issue_verification(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        req: IssueVerificationRequest,
        request_id: str | None = None,
    ) -> VerificationDetailResponse:
        """Issue a private synthetic readiness verification from an approved pre-audit case."""
        self._verify_admission(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id

        req_digest = compute_digest(canonicalize_json(req.model_dump()))
        existing_event = self._check_idempotency(
            tenant_id=tenant_id,
            operation_id=req.operation_id,
            expected_verification_id=None,
            expected_event_type="ISSUED",
            actor_user_id=principal.user_id,
            request_digest=req_digest,
        )
        if existing_event is not None:
            detail = self.get_verification(principal, tenant_context, existing_event.verification_id)
            return detail.model_copy(
                update={
                    "replayed": True,
                    "applied_event_id": existing_event.id,
                }
            )

        # Validate approved pre-audit case and snapshot inputs
        case, r_snap, snap_payload, approval_event = (
            self.preaudit_service.validate_approved_case_for_verification(
                principal=principal,
                tenant_context=tenant_context,
                case_id=req.preaudit_id,
                expected_case_revision=req.expected_case_revision,
                expected_snapshot_id=req.snapshot_id,
                expected_snapshot_digest=req.snapshot_digest,
                for_update=True,
            )
        )

        # Race-safe uniqueness check on snapshot
        existing_v = self.session.execute(
            select(CustomerReadinessVerification).where(
                CustomerReadinessVerification.tenant_id == tenant_id,
                CustomerReadinessVerification.snapshot_id == r_snap.id,
            )
        ).scalar_one_or_none()
        if existing_v:
            raise HTTPException(
                status_code=409,
                detail="A readiness verification has already been issued for this review snapshot",
            )

        now = self._get_clock()
        valid_through = compute_valid_through(now)
        v_id = uuid4()

        payload_dict = self._freeze_case_provenance(
            tenant_id=tenant_id,
            case=case,
            r_snap=r_snap,
            snap_payload=snap_payload,
            approval_event=approval_event,
            v_id=v_id,
            now=now,
            valid_through=valid_through,
            principal=principal,
            limitations=req.limitations,
            notes=req.notes,
        )

        enc_payload, digest = encrypt_verification_payload(self.codec, tenant_id, v_id, payload_dict)

        verification = CustomerReadinessVerification(
            tenant_id=tenant_id,
            id=v_id,
            preaudit_id=case.id,
            snapshot_id=r_snap.id,
            status="ACTIVE",
            revision=1,
            issued_at=now,
            valid_through=valid_through,
            payload_encrypted=enc_payload,
            digest=digest,
        )
        self.session.add(verification)
        self.session.flush()

        event_id = uuid4()
        event_enc = encrypt_verification_event_payload(
            self.codec,
            tenant_id,
            event_id,
            {"action": "issue", "notes": req.notes, "limitations": req.limitations},
        )
        event = CustomerReadinessVerificationEvent(
            tenant_id=tenant_id,
            id=event_id,
            verification_id=v_id,
            sequence=1,
            operation_id=req.operation_id,
            request_digest=req_digest,
            event_type="ISSUED",
            actor_user_id=principal.user_id,
            actor_role=tenant_context.role.value,
            prior_status=None,
            new_status="ACTIVE",
            reason=req.notes,
            payload_encrypted=event_enc,
            created_at=now,
        )
        self.session.add(event)
        verification.current_event_id = event_id
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_readiness_verification.issued",
            resource_type="customer_readiness_verification",
            resource_id=str(v_id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
        )
        self.session.flush()

        detail = self.get_verification(principal, tenant_context, v_id)
        return detail.model_copy(
            update={
                "replayed": False,
                "applied_event_id": event.id,
            }
        )

    def list_verifications(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        limit: int = 50,
        offset: int = 0,
        preaudit_case_id: UUID | None = None,
    ) -> VerificationListResponse:
        """List tenant readiness verification summaries without side effects on GET."""
        self._verify_admission(principal, tenant_context, operation="read")
        tenant_id = tenant_context.tenant_id
        now = self._get_clock()

        query = select(CustomerReadinessVerification).where(
            CustomerReadinessVerification.tenant_id == tenant_id
        )
        if preaudit_case_id is not None:
            query = query.where(CustomerReadinessVerification.preaudit_id == preaudit_case_id)

        total = self.session.execute(
            select(func.count()).select_from(query.subquery())
        ).scalar() or 0

        rows = self.session.execute(
            query.order_by(CustomerReadinessVerification.issued_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars().all()

        summaries = []
        for r in rows:
            eff_status, _ = self._compute_effective_status(r, now)
            # Decrypt payload for display metadata
            try:
                decrypted = decrypt_verification_payload(
                    self.codec, tenant_id, r.id, r.payload_encrypted, r.digest
                )
                fw_name = decrypted.get("framework_display_name")
                fw_ver = decrypted.get("framework_version")
            except Exception:
                fw_name = None
                fw_ver = None

            summaries.append(
                VerificationListSummary(
                    id=r.id,
                    preaudit_id=r.preaudit_id,
                    status=r.status,
                    effective_status=eff_status,
                    revision=r.revision,
                    issued_at=r.issued_at,
                    valid_through=r.valid_through,
                    framework_display_name=fw_name,
                    framework_version=fw_ver,
                    synthetic_marker=SYNTHETIC_MARKER,
                )
            )

        return VerificationListResponse(
            verifications=summaries,
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_verification(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        verification_id: UUID,
    ) -> VerificationDetailResponse:
        """Retrieve full verification detail and verify payload integrity without GET writes."""
        self._verify_admission(principal, tenant_context, operation="read")
        tenant_id = tenant_context.tenant_id
        now = self._get_clock()

        v = self.session.execute(
            select(CustomerReadinessVerification).where(
                CustomerReadinessVerification.tenant_id == tenant_id,
                CustomerReadinessVerification.id == verification_id,
            )
        ).scalar_one_or_none()
        if not v:
            raise HTTPException(status_code=404, detail="Readiness verification not found")

        decrypted = decrypt_verification_payload(
            self.codec, tenant_id, v.id, v.payload_encrypted, v.digest
        )

        eff_status, eff_reason = self._compute_effective_status(v, now)

        issuer_id = UUID(decrypted["issuer_user_id"]) if decrypted.get("issuer_user_id") else None
        reviewer_id = UUID(decrypted["reviewer_user_id"]) if decrypted.get("reviewer_user_id") else None
        approver_id = UUID(decrypted["approver_user_id"]) if decrypted.get("approver_user_id") else None

        return VerificationDetailResponse(
            id=v.id,
            preaudit_id=v.preaudit_id,
            snapshot_id=v.snapshot_id,
            status=v.status,
            effective_status=eff_status,
            effective_reason=eff_reason,
            revision=v.revision,
            issued_at=v.issued_at,
            valid_through=v.valid_through,
            digest=v.digest,
            current_event_id=v.current_event_id,
            superseded_by_id=v.superseded_by_id,
            supersedes_id=v.supersedes_id,
            synthetic_marker=SYNTHETIC_MARKER,
            test_qualification=TEST_QUALIFICATION,
            framework_id=decrypted.get("framework_id"),
            framework_version=decrypted.get("framework_version"),
            framework_display_name=decrypted.get("framework_display_name"),
            organization_display_name=decrypted.get("organization_display_name"),
            scope_summary=decrypted.get("scope_summary"),
            limitations=decrypted.get("limitations", []),
            notes=decrypted.get("notes"),
            issuer_user_id=issuer_id,
            reviewer_user_id=reviewer_id,
            approver_user_id=approver_id,
            created_at=v.created_at,
            updated_at=v.updated_at,
            replayed=False,
        )

    def get_verification_projection(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        verification_id: UUID,
    ) -> VerificationProjectionResponse:
        """Allowlisted private preview projection excluding secrets and private notes."""
        detail = self.get_verification(principal, tenant_context, verification_id)
        v = self.session.execute(
            select(CustomerReadinessVerification).where(
                CustomerReadinessVerification.tenant_id == tenant_context.tenant_id,
                CustomerReadinessVerification.id == verification_id,
            )
        ).scalar_one()

        decrypted = decrypt_verification_payload(
            self.codec, tenant_context.tenant_id, v.id, v.payload_encrypted, v.digest
        )

        return build_verification_projection(
            verification=v,
            decrypted_payload=decrypted,
            effective_status=detail.effective_status,
            effective_reason=detail.effective_reason,
        )

    def get_verification_history(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        verification_id: UUID,
    ) -> VerificationHistoryResponse:
        """Return immutable chronological event history for a verification."""
        self._verify_admission(principal, tenant_context, operation="read")
        tenant_id = tenant_context.tenant_id

        events = self.session.execute(
            select(CustomerReadinessVerificationEvent)
            .where(
                CustomerReadinessVerificationEvent.tenant_id == tenant_id,
                CustomerReadinessVerificationEvent.verification_id == verification_id,
            )
            .order_by(CustomerReadinessVerificationEvent.sequence.asc())
        ).scalars().all()

        items = []
        for e in events:
            try:
                dec = decrypt_verification_event_payload(self.codec, tenant_id, e.id, e.payload_encrypted)
                notes = dec.get("notes") or dec.get("reason") or dec.get("correction_notes")
            except Exception:
                notes = None

            items.append(
                VerificationEventItem(
                    id=e.id,
                    verification_id=e.verification_id,
                    sequence=e.sequence,
                    operation_id=e.operation_id,
                    event_type=e.event_type,
                    actor_user_id=e.actor_user_id,
                    actor_role=e.actor_role,
                    prior_status=e.prior_status,
                    new_status=e.new_status,
                    reason=e.reason,
                    notes=notes or e.reason,
                    request_digest=e.request_digest,
                    created_at=e.created_at,
                )
            )

        return VerificationHistoryResponse(verification_id=verification_id, events=items)

    def suspend_verification(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        verification_id: UUID,
        req: SuspendVerificationRequest,
        request_id: str | None = None,
    ) -> VerificationDetailResponse:
        """Owner suspends an active verification with encrypted reason and CAS check."""
        self._verify_admission(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id

        req_digest = compute_digest(canonicalize_json(req.model_dump()))
        existing_event = self._check_idempotency(
            tenant_id=tenant_id,
            operation_id=req.operation_id,
            expected_verification_id=verification_id,
            expected_event_type="SUSPENDED",
            actor_user_id=principal.user_id,
            request_digest=req_digest,
        )
        if existing_event is not None:
            detail = self.get_verification(principal, tenant_context, verification_id)
            return detail.model_copy(
                update={
                    "replayed": True,
                    "applied_event_id": existing_event.id,
                }
            )

        v = self.session.execute(
            select(CustomerReadinessVerification)
            .where(
                CustomerReadinessVerification.tenant_id == tenant_id,
                CustomerReadinessVerification.id == verification_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if not v:
            raise HTTPException(status_code=404, detail="Readiness verification not found")

        if v.revision != req.expected_revision:
            raise HTTPException(
                status_code=409,
                detail=f"Revision conflict: expected revision {req.expected_revision}, current {v.revision}",
            )

        if v.status != "ACTIVE":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot suspend verification in status {v.status}; must be ACTIVE",
            )

        now = self._get_clock()
        prior_status = v.status
        v.status = "SUSPENDED"
        v.revision = v.revision + 1
        self.session.flush()

        max_seq = self.session.execute(
            select(func.coalesce(func.max(CustomerReadinessVerificationEvent.sequence), 0)).where(
                CustomerReadinessVerificationEvent.tenant_id == tenant_id,
                CustomerReadinessVerificationEvent.verification_id == v.id,
            )
        ).scalar() or 0

        event_id = uuid4()
        event_enc = encrypt_verification_event_payload(
            self.codec,
            tenant_id,
            event_id,
            {"action": "suspend", "reason": req.reason},
        )
        event = CustomerReadinessVerificationEvent(
            tenant_id=tenant_id,
            id=event_id,
            verification_id=v.id,
            sequence=max_seq + 1,
            operation_id=req.operation_id,
            request_digest=req_digest,
            event_type="SUSPENDED",
            actor_user_id=principal.user_id,
            actor_role=tenant_context.role.value,
            prior_status=prior_status,
            new_status="SUSPENDED",
            reason=req.reason,
            payload_encrypted=event_enc,
            created_at=now,
        )
        self.session.add(event)
        v.current_event_id = event_id
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_readiness_verification.suspended",
            resource_type="customer_readiness_verification",
            resource_id=str(v.id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
        )
        self.session.flush()

        detail = self.get_verification(principal, tenant_context, v.id)
        return detail.model_copy(
            update={
                "replayed": False,
                "applied_event_id": event.id,
            }
        )

    def revoke_verification(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        verification_id: UUID,
        req: RevokeVerificationRequest,
        request_id: str | None = None,
    ) -> VerificationDetailResponse:
        """Owner revokes a verification permanently; terminal state cannot reactivate."""
        self._verify_admission(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id

        req_digest = compute_digest(canonicalize_json(req.model_dump()))
        existing_event = self._check_idempotency(
            tenant_id=tenant_id,
            operation_id=req.operation_id,
            expected_verification_id=verification_id,
            expected_event_type="REVOKED",
            actor_user_id=principal.user_id,
            request_digest=req_digest,
        )
        if existing_event is not None:
            detail = self.get_verification(principal, tenant_context, verification_id)
            return detail.model_copy(
                update={
                    "replayed": True,
                    "applied_event_id": existing_event.id,
                }
            )

        v = self.session.execute(
            select(CustomerReadinessVerification)
            .where(
                CustomerReadinessVerification.tenant_id == tenant_id,
                CustomerReadinessVerification.id == verification_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if not v:
            raise HTTPException(status_code=404, detail="Readiness verification not found")

        if v.revision != req.expected_revision:
            raise HTTPException(
                status_code=409,
                detail=f"Revision conflict: expected revision {req.expected_revision}, current {v.revision}",
            )

        if v.status == "REVOKED":
            raise HTTPException(
                status_code=409,
                detail="Verification is already REVOKED",
            )

        now = self._get_clock()
        prior_status = v.status
        v.status = "REVOKED"
        v.revision = v.revision + 1
        self.session.flush()

        max_seq = self.session.execute(
            select(func.coalesce(func.max(CustomerReadinessVerificationEvent.sequence), 0)).where(
                CustomerReadinessVerificationEvent.tenant_id == tenant_id,
                CustomerReadinessVerificationEvent.verification_id == v.id,
            )
        ).scalar() or 0

        event_id = uuid4()
        event_enc = encrypt_verification_event_payload(
            self.codec,
            tenant_id,
            event_id,
            {"action": "revoke", "reason": req.reason},
        )
        event = CustomerReadinessVerificationEvent(
            tenant_id=tenant_id,
            id=event_id,
            verification_id=v.id,
            sequence=max_seq + 1,
            operation_id=req.operation_id,
            request_digest=req_digest,
            event_type="REVOKED",
            actor_user_id=principal.user_id,
            actor_role=tenant_context.role.value,
            prior_status=prior_status,
            new_status="REVOKED",
            reason=req.reason,
            payload_encrypted=event_enc,
            created_at=now,
        )
        self.session.add(event)
        v.current_event_id = event_id
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_readiness_verification.revoked",
            resource_type="customer_readiness_verification",
            resource_id=str(v.id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
        )
        self.session.flush()

        detail = self.get_verification(principal, tenant_context, v.id)
        return detail.model_copy(
            update={
                "replayed": False,
                "applied_event_id": event.id,
            }
        )

    def correct_verification(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        verification_id: UUID,
        req: CorrectVerificationRequest,
        request_id: str | None = None,
    ) -> VerificationDetailResponse:
        """Append an explanatory correction event without overwriting frozen facts."""
        self._verify_admission(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id

        req_digest = compute_digest(canonicalize_json(req.model_dump()))
        existing_event = self._check_idempotency(
            tenant_id=tenant_id,
            operation_id=req.operation_id,
            expected_verification_id=verification_id,
            expected_event_type="CORRECTED",
            actor_user_id=principal.user_id,
            request_digest=req_digest,
        )
        if existing_event is not None:
            detail = self.get_verification(principal, tenant_context, verification_id)
            return detail.model_copy(
                update={
                    "replayed": True,
                    "applied_event_id": existing_event.id,
                }
            )

        v = self.session.execute(
            select(CustomerReadinessVerification)
            .where(
                CustomerReadinessVerification.tenant_id == tenant_id,
                CustomerReadinessVerification.id == verification_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if not v:
            raise HTTPException(status_code=404, detail="Readiness verification not found")

        if v.revision != req.expected_revision:
            raise HTTPException(
                status_code=409,
                detail=f"Revision conflict: expected revision {req.expected_revision}, current {v.revision}",
            )

        now = self._get_clock()
        v.revision = v.revision + 1
        self.session.flush()

        max_seq = self.session.execute(
            select(func.coalesce(func.max(CustomerReadinessVerificationEvent.sequence), 0)).where(
                CustomerReadinessVerificationEvent.tenant_id == tenant_id,
                CustomerReadinessVerificationEvent.verification_id == v.id,
            )
        ).scalar() or 0

        event_id = uuid4()
        event_enc = encrypt_verification_event_payload(
            self.codec,
            tenant_id,
            event_id,
            {"action": "correct", "correction_notes": req.correction_notes},
        )
        event = CustomerReadinessVerificationEvent(
            tenant_id=tenant_id,
            id=event_id,
            verification_id=v.id,
            sequence=max_seq + 1,
            operation_id=req.operation_id,
            request_digest=req_digest,
            event_type="CORRECTED",
            actor_user_id=principal.user_id,
            actor_role=tenant_context.role.value,
            prior_status=v.status,
            new_status=v.status,
            reason=req.correction_notes,
            payload_encrypted=event_enc,
            created_at=now,
        )
        self.session.add(event)
        v.current_event_id = event_id
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_readiness_verification.corrected",
            resource_type="customer_readiness_verification",
            resource_id=str(v.id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
        )
        self.session.flush()

        detail = self.get_verification(principal, tenant_context, v.id)
        return detail.model_copy(
            update={
                "replayed": False,
                "applied_event_id": event.id,
            }
        )

    def supersede_verification(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        old_verification_id: UUID,
        req: SupersedeVerificationRequest,
        request_id: str | None = None,
    ) -> VerificationDetailResponse:
        """Atomically link old verification to a newly issued replacement from a fresh approved case."""
        self._verify_admission(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id

        req_digest = compute_digest(canonicalize_json(req.model_dump()))
        existing_event = self._check_idempotency(
            tenant_id=tenant_id,
            operation_id=req.operation_id,
            expected_verification_id=old_verification_id,
            expected_event_type="SUPERSEDED",
            actor_user_id=principal.user_id,
            request_digest=req_digest,
        )
        if existing_event is not None:
            # Replayed supersession: return the new replacement verification detail
            old_v = self.session.execute(
                select(CustomerReadinessVerification).where(
                    CustomerReadinessVerification.tenant_id == tenant_id,
                    CustomerReadinessVerification.id == old_verification_id,
                )
            ).scalar_one()
            assert old_v.superseded_by_id is not None
            detail = self.get_verification(principal, tenant_context, old_v.superseded_by_id)
            return detail.model_copy(
                update={
                    "replayed": True,
                    "applied_event_id": existing_event.id,
                }
            )

        old_v = self.session.execute(
            select(CustomerReadinessVerification)
            .where(
                CustomerReadinessVerification.tenant_id == tenant_id,
                CustomerReadinessVerification.id == old_verification_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if not old_v:
            raise HTTPException(status_code=404, detail="Original readiness verification not found")

        if old_v.revision != req.expected_revision:
            raise HTTPException(
                status_code=409,
                detail=f"Revision conflict: expected revision {req.expected_revision}, current {old_v.revision}",
            )

        if old_v.status == "REVOKED":
            raise HTTPException(status_code=409, detail="Terminal REVOKED verification cannot be superseded")

        if old_v.status == "SUPERSEDED":
            raise HTTPException(status_code=409, detail="Verification has already been superseded")

        # Validate fresh approved source
        new_case, new_r_snap, new_snap_payload, new_approval_event = (
            self.preaudit_service.validate_approved_case_for_verification(
                principal=principal,
                tenant_context=tenant_context,
                case_id=req.new_preaudit_id,
                expected_case_revision=req.new_expected_case_revision,
                expected_snapshot_id=req.new_snapshot_id,
                expected_snapshot_digest=req.new_snapshot_digest,
                for_update=True,
            )
        )

        if new_r_snap.id == old_v.snapshot_id:
            raise HTTPException(
                status_code=409,
                detail="Superseding verification requires a new distinct review snapshot",
            )

        # Race-safe uniqueness check on new snapshot
        existing_new = self.session.execute(
            select(CustomerReadinessVerification).where(
                CustomerReadinessVerification.tenant_id == tenant_id,
                CustomerReadinessVerification.snapshot_id == new_r_snap.id,
            )
        ).scalar_one_or_none()
        if existing_new:
            raise HTTPException(
                status_code=409,
                detail="A readiness verification has already been issued for the replacement snapshot",
            )

        now = self._get_clock()
        new_valid_through = compute_valid_through(now)
        new_v_id = uuid4()

        new_payload_dict = self._freeze_case_provenance(
            tenant_id=tenant_id,
            case=new_case,
            r_snap=new_r_snap,
            snap_payload=new_snap_payload,
            approval_event=new_approval_event,
            v_id=new_v_id,
            now=now,
            valid_through=new_valid_through,
            principal=principal,
            limitations=req.limitations,
            notes=req.notes,
            supersedes_id=old_v.id,
        )

        enc_new_payload, new_digest = encrypt_verification_payload(
            self.codec, tenant_id, new_v_id, new_payload_dict
        )

        new_v = CustomerReadinessVerification(
            tenant_id=tenant_id,
            id=new_v_id,
            preaudit_id=new_case.id,
            snapshot_id=new_r_snap.id,
            status="ACTIVE",
            revision=1,
            issued_at=now,
            valid_through=new_valid_through,
            payload_encrypted=enc_new_payload,
            digest=new_digest,
            supersedes_id=old_v.id,
        )
        self.session.add(new_v)
        self.session.flush()

        # Update old verification
        prior_old_status = old_v.status
        old_v.status = "SUPERSEDED"
        old_v.superseded_by_id = new_v.id
        old_v.revision = old_v.revision + 1
        self.session.flush()

        # Event on old verification: SUPERSEDED
        old_max_seq = self.session.execute(
            select(func.coalesce(func.max(CustomerReadinessVerificationEvent.sequence), 0)).where(
                CustomerReadinessVerificationEvent.tenant_id == tenant_id,
                CustomerReadinessVerificationEvent.verification_id == old_v.id,
            )
        ).scalar() or 0

        old_event_id = uuid4()
        old_event_enc = encrypt_verification_event_payload(
            self.codec,
            tenant_id,
            old_event_id,
            {"action": "superseded", "superseded_by_id": str(new_v.id), "notes": req.notes},
        )
        old_event = CustomerReadinessVerificationEvent(
            tenant_id=tenant_id,
            id=old_event_id,
            verification_id=old_v.id,
            sequence=old_max_seq + 1,
            operation_id=req.operation_id,
            request_digest=req_digest,
            event_type="SUPERSEDED",
            actor_user_id=principal.user_id,
            actor_role=tenant_context.role.value,
            prior_status=prior_old_status,
            new_status="SUPERSEDED",
            reason=req.notes,
            payload_encrypted=old_event_enc,
            created_at=now,
        )
        self.session.add(old_event)
        old_v.current_event_id = old_event_id

        # Event on new verification: ISSUED
        new_event_id = uuid4()
        new_event_enc = encrypt_verification_event_payload(
            self.codec,
            tenant_id,
            new_event_id,
            {"action": "issue_superseding", "supersedes_id": str(old_v.id), "notes": req.notes},
        )
        new_event = CustomerReadinessVerificationEvent(
            tenant_id=tenant_id,
            id=new_event_id,
            verification_id=new_v.id,
            sequence=1,
            operation_id=uuid4(),  # distinct internal event operation
            request_digest=new_digest,
            event_type="ISSUED",
            actor_user_id=principal.user_id,
            actor_role=tenant_context.role.value,
            prior_status=None,
            new_status="ACTIVE",
            reason=req.notes,
            payload_encrypted=new_event_enc,
            created_at=now,
        )
        self.session.add(new_event)
        new_v.current_event_id = new_event_id
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_readiness_verification.superseded",
            resource_type="customer_readiness_verification",
            resource_id=str(old_v.id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
        )
        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_readiness_verification.issued",
            resource_type="customer_readiness_verification",
            resource_id=str(new_v.id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
        )
        self.session.flush()

        detail = self.get_verification(principal, tenant_context, new_v.id)
        return detail.model_copy(
            update={
                "replayed": False,
                "applied_event_id": old_event.id,
            }
        )

    def reconcile_lifecycle(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        req: ReconcileVerificationRequest,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Reconcile expired or stale active verifications, persisting due state transitions."""
        self._verify_admission(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id
        now = self._get_clock()

        active_rows = self.session.execute(
            select(CustomerReadinessVerification)
            .where(
                CustomerReadinessVerification.tenant_id == tenant_id,
                CustomerReadinessVerification.status.in_(["ACTIVE", "SUSPENDED"]),
            )
            .with_for_update()
        ).scalars().all()

        reconciled = []
        for v in active_rows:
            eff_status, eff_reason = self._compute_effective_status(v, now)
            if eff_status != v.status:
                prior_status = v.status
                v.status = eff_status
                v.revision = v.revision + 1
                self.session.flush()

                max_seq = self.session.execute(
                    select(func.coalesce(func.max(CustomerReadinessVerificationEvent.sequence), 0)).where(
                        CustomerReadinessVerificationEvent.tenant_id == tenant_id,
                        CustomerReadinessVerificationEvent.verification_id == v.id,
                    )
                ).scalar() or 0

                event_id = uuid4()
                event_enc = encrypt_verification_event_payload(
                    self.codec,
                    tenant_id,
                    event_id,
                    {"action": "reconcile", "new_status": eff_status, "reason": eff_reason},
                )
                event = CustomerReadinessVerificationEvent(
                    tenant_id=tenant_id,
                    id=event_id,
                    verification_id=v.id,
                    sequence=max_seq + 1,
                    operation_id=uuid4(),
                    request_digest=compute_digest(canonicalize_json({"reconcile": str(event_id)})),
                    event_type="RECONCILED",
                    actor_user_id=principal.user_id,
                    actor_role=tenant_context.role.value,
                    prior_status=prior_status,
                    new_status=eff_status,
                    reason=eff_reason,
                    payload_encrypted=event_enc,
                    created_at=now,
                )
                self.session.add(event)
                v.current_event_id = event_id
                self.session.flush()

                record_audit_event(
                    self.session,
                    tenant_id=tenant_id,
                    actor_type=AuditActorType.USER,
                    actor_id=principal.user_id,
                    action=f"customer_readiness_verification.{eff_status.lower()}",
                    resource_type="customer_readiness_verification",
                    resource_id=str(v.id),
                    request_id=request_id or f"req-{uuid4()}",
                    outcome=AuditOutcome.SUCCESS,
                )
                reconciled.append(
                    {
                        "verification_id": str(v.id),
                        "prior_status": prior_status,
                        "new_status": eff_status,
                        "reason": eff_reason,
                    }
                )

        self.session.flush()
        return {"reconciled_count": len(reconciled), "results": reconciled}
