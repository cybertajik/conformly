"""Service layer for V2 Pre-Audit Review Workflow."""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.catalog_v2.digest import canonical_json
from conformly.compliance.models import EvidenceItem, EvidenceRevision
from conformly.config import get_settings
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.customer_demo.assessment_models import (
    CustomerAssessmentEvent,
    CustomerAssessmentFinding,
    CustomerAssessmentHead,
)
from conformly.customer_demo.assessment_procedures import get_procedure_for_control_version
from conformly.customer_demo.assessment_service import CustomerAssessmentService
from conformly.customer_demo.evaluator import (
    compute_answers_digest,
    compute_evaluation_digest,
    evaluate_bundle,
)
from conformly.customer_demo.fixture import EVALUATOR_VERSION, get_bundle_by_version_id
from conformly.customer_demo.models import (
    CustomerDemoAdoption,
    CustomerDemoAnswers,
    CustomerDemoEvaluation,
    CustomerDemoWorkspace,
)
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
from conformly.customer_demo.preaudit_report import generate_preaudit_report_archive
from conformly.customer_demo.preaudit_schemas import (
    ApprovePreauditRequest,
    CancelPreauditRequest,
    CreatePreauditRequest,
    DownloadPreauditReportRequest,
    FreezeScopeRequest,
    PreauditActorDTO,
    PreauditBlockerDTO,
    PreauditDetailResponse,
    PreauditEventDTO,
    PreauditHistoryResponse,
    PreauditListResponse,
    PreauditSnapshotSummaryDTO,
    PreauditSummaryDTO,
    ReviewDecisionRequest,
    SubmitReviewRequest,
)
from conformly.customer_demo.preaudit_snapshot import (
    canonicalize_json,
    compute_digest,
    decrypt_event_payload,
    decrypt_snapshot_payload,
    encrypt_event_payload,
    encrypt_snapshot_payload,
)
from conformly.customer_demo.work_models import (
    CustomerControlEvidenceLink,
    CustomerControlWork,
    CustomerControlWorkEvent,
)
from conformly.identity.models import Membership, MembershipStatus, User, UserStatus
from conformly.storage.models import StoredFile
from conformly.tenancy.rls import set_rls_context


class CustomerPreauditService:
    """Business logic for V2 pre-audit case management, freezing, reviews, and reports."""

    def __init__(self, session: Session, codec: EncryptedFieldCodec | None = None) -> None:
        self.session = session
        self.codec = codec or get_encrypted_field_codec()

    def _verify_preaudit_admission(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        operation: str = "read",
    ) -> None:
        """Enforce default-off feature guard, database connection check, and customer-demo admission + active membership/user verification."""
        settings = get_settings()
        if not settings.enable_customer_preaudit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pre-audit review feature is not enabled",
            )
        if not settings.enable_customer_demo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer demo feature is not enabled",
            )
        if settings.environment not in ("local", "development", "test"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pre-audit review prohibited in non-development environments",
            )

        # Database connection on PostgreSQL: non-owner conformly_app without superuser/bypassrls and non-owner of the 3 preaudit tables
        bind = self.session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            row = self.session.execute(
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
                self.session.execute(
                    text(
                        """
                        SELECT c.relname
                        FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        JOIN pg_roles r ON r.oid = c.relowner
                        WHERE c.relname IN ('customer_preaudits', 'customer_preaudit_snapshots', 'customer_preaudit_events')
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
                    f"PostgreSQL user '{user_name}' illegally owns customer preaudit tables: {list(owned_tables)}"
                )

        verify_customer_demo_admission(
            principal,
            tenant_context,
            "mutate" if operation == "mutate" else "read",
            session=self.session,
        )
        set_rls_context(
            self.session,
            user_id=principal.user_id,
            tenant_id=tenant_context.tenant_id,
            tenant_verified=True,
        )

        # Verify active persisted User and Membership with matching role
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
                status_code=status.HTTP_403_FORBIDDEN,
            )

    def _check_idempotency(
        self,
        tenant_id: UUID,
        operation_id: UUID,
        expected_preaudit_id: UUID | None,
        expected_event_type: str,
        actor_user_id: UUID,
        request_digest: str,
    ) -> CustomerPreauditEvent | None:
        """Check idempotency against existing pre-audit events. Fail closed on conflict."""
        existing = self.session.execute(
            select(CustomerPreauditEvent).where(
                CustomerPreauditEvent.tenant_id == tenant_id,
                CustomerPreauditEvent.operation_id == operation_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            if expected_preaudit_id is not None and existing.preaudit_id != expected_preaudit_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Operation ID conflict: replayed against different pre-audit case",
                )
            if existing.event_type != expected_event_type:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Operation ID conflict: replayed across different actions (expected {expected_event_type}, found {existing.event_type})",
                )
            if existing.actor_user_id != actor_user_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Operation ID conflict: replayed by different actor",
                )
            if existing.request_digest != request_digest:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Operation ID conflict: replayed with different request payload",
                )
        return existing

    def _derive_expected_scope_pins(
        self,
        tenant_id: UUID,
        adoption: CustomerDemoAdoption,
        evaluation: CustomerDemoEvaluation,
    ) -> tuple[list[dict[str, Any]], set[UUID], dict[str, str]]:
        """Derive complete expected control version pins from registered bundle requirements."""
        bundle = get_bundle_by_version_id(adoption.pack_version_id)
        req_results_map: dict[str, str] = {}
        for r in evaluation.results:
            req_results_map[str(r["requirement_version_id"])] = str(
                r.get("result") or r.get("status") or "NEEDS_INFORMATION"
            )

        reqs_by_cv: dict[UUID, list[dict[str, Any]]] = {}
        for req in bundle.get("requirements", []):
            cv_id = UUID(str(req["control_version_id"]))
            reqs_by_cv.setdefault(cv_id, []).append(req)

        control_version_pins: list[dict[str, Any]] = []
        for cv_id in sorted(reqs_by_cv.keys(), key=lambda uid: str(uid)):
            reqs = reqs_by_cv[cv_id]
            first_req = reqs[0]
            proc = get_procedure_for_control_version(cv_id)
            control_version_pins.append({
                "control_id": str(first_req.get("control_id") or first_req.get("id")),
                "control_version_id": str(cv_id),
                "code": first_req.get("control_identifier") or first_req.get("code") or "",
                "title": first_req.get("control_title") or first_req.get("title") or "",
                "procedure_pins": [
                    {
                        "procedure_id": str(proc["id"]),
                        "version": proc["version"],
                        "digest": proc["digest"],
                    }
                ],
                "requirements": [
                    {
                        "requirement_id": str(rq.get("id")),
                        "requirement_version_id": str(rq.get("version_id")),
                        "identifier": rq.get("identifier") or "",
                        "title": rq.get("title") or "",
                        "evaluated_status": req_results_map.get(str(rq.get("version_id")), "NEEDS_INFORMATION"),
                    }
                    for rq in reqs
                ],
            })

        return control_version_pins, set(reqs_by_cv.keys()), req_results_map

    def _compute_canonical_review_projection(
        self,
        tenant_id: UUID,
        case: CustomerPreaudit,
        principal: Principal,
        tenant_context: TenantContext,
        for_update: bool = False,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], str, bool]:
        """Compute coherent canonical review projection, validate full work set, and compute deterministic fingerprint."""
        ws_stmt = select(CustomerDemoWorkspace).where(CustomerDemoWorkspace.tenant_id == tenant_id)
        adopt_stmt = select(CustomerDemoAdoption).where(
            CustomerDemoAdoption.tenant_id == tenant_id,
            CustomerDemoAdoption.id == case.adoption_id,
        )
        if for_update:
            ws_stmt = ws_stmt.with_for_update()
            adopt_stmt = adopt_stmt.with_for_update()

        workspace = self.session.execute(ws_stmt).scalar_one_or_none()
        adoption = self.session.execute(adopt_stmt).scalar_one_or_none()
        if not workspace or not adoption:
            raise HTTPException(status_code=404, detail="Workspace or adoption record missing")

        eval_stmt = select(CustomerDemoEvaluation).where(
            CustomerDemoEvaluation.tenant_id == tenant_id,
            CustomerDemoEvaluation.id == adoption.evaluation_id,
        )
        if for_update:
            eval_stmt = eval_stmt.with_for_update()
        evaluation = self.session.execute(eval_stmt).scalar_one_or_none()
        if not evaluation:
            raise HTTPException(status_code=404, detail="Referenced evaluation record missing")

        ans_stmt = select(CustomerDemoAnswers).where(
            CustomerDemoAnswers.tenant_id == tenant_id,
            CustomerDemoAnswers.revision == evaluation.answer_revision,
        )
        if for_update:
            ans_stmt = ans_stmt.with_for_update()
        answers = self.session.execute(ans_stmt).scalar_one_or_none()

        is_scope_current = bool(
            workspace.selection_revision == adoption.selection_revision
            and workspace.current_revision == evaluation.answer_revision
        )

        if answers is not None:
            recomputed_ans_digest = compute_answers_digest(answers.company_code, answers.answers)
            if answers.content_digest != recomputed_ans_digest:
                is_scope_current = False
            try:
                recomp_results = evaluate_bundle(adoption.pack_version_id, answers.answers)
                if evaluation.results != recomp_results:
                    is_scope_current = False
                recomp_eval_digest = compute_evaluation_digest(
                    answer_digest=recomputed_ans_digest,
                    answer_revision=evaluation.answer_revision,
                    pack_version_id=adoption.pack_version_id,
                    bundle_digest=adoption.bundle_digest,
                    results=recomp_results,
                    evaluator_version=EVALUATOR_VERSION,
                )
                if evaluation.content_digest != recomp_eval_digest:
                    is_scope_current = False
            except Exception:
                is_scope_current = False
        else:
            is_scope_current = False

        control_version_pins, expected_cv_ids, req_results_map = self._derive_expected_scope_pins(
            tenant_id, adoption, evaluation
        )

        work_stmt = (
            select(CustomerControlWork)
            .where(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.adoption_id == adoption.id,
            )
            .order_by(CustomerControlWork.control_version_id.asc())
        )
        if for_update:
            work_stmt = work_stmt.with_for_update()
        works = self.session.execute(work_stmt).scalars().all()

        blockers: list[dict[str, Any]] = []

        if len(works) == 0:
            blockers.append({
                "code": "MISSING_INITIALIZED_WORK",
                "description": "No initialized compliance control work items exist for this adoption",
                "work_id": None,
                "control_code": None,
            })

        found_cv_ids = {w.control_version_id for w in works}
        if len(found_cv_ids) != len(works):
            blockers.append({
                "code": "DUPLICATE_WORK_ITEMS",
                "description": "Duplicate control work items detected for adoption",
                "work_id": None,
                "control_code": None,
            })

        for exp_cv in sorted(expected_cv_ids, key=lambda u: str(u)):
            if exp_cv not in found_cv_ids:
                blockers.append({
                    "code": "INCOMPLETE_WORK_SET",
                    "description": f"Missing initialized work for required control version {exp_cv}",
                    "work_id": None,
                    "control_code": str(exp_cv)[:8],
                })

        for w in works:
            if w.control_version_id not in expected_cv_ids:
                blockers.append({
                    "code": "UNEXPECTED_WORK_ITEM",
                    "description": f"Control work item {w.id} references unexpected control version {w.control_version_id}",
                    "work_id": str(w.id),
                    "control_code": str(w.control_version_id)[:8],
                })

        if for_update and works:
            w_ids = [w.id for w in works]
            self.session.execute(
                select(CustomerAssessmentHead)
                .where(CustomerAssessmentHead.tenant_id == tenant_id, CustomerAssessmentHead.work_id.in_(w_ids))
                .order_by(CustomerAssessmentHead.work_id.asc())
                .with_for_update()
            ).scalars().all()
            links = self.session.execute(
                select(CustomerControlEvidenceLink)
                .where(CustomerControlEvidenceLink.tenant_id == tenant_id, CustomerControlEvidenceLink.work_id.in_(w_ids))
                .order_by(CustomerControlEvidenceLink.id.asc())
                .with_for_update()
            ).scalars().all()
            self.session.execute(
                select(CustomerAssessmentFinding)
                .where(CustomerAssessmentFinding.tenant_id == tenant_id, CustomerAssessmentFinding.work_id.in_(w_ids))
                .order_by(CustomerAssessmentFinding.id.asc())
                .with_for_update()
            ).scalars().all()

            # Acquire deterministic tenant-scoped locks for actual evidence/revision/file dependencies
            ev_ids = sorted(list({lnk.evidence_id for lnk in links if lnk.evidence_id is not None}))
            if ev_ids:
                self.session.execute(
                    select(EvidenceItem)
                    .where(EvidenceItem.tenant_id == tenant_id, EvidenceItem.id.in_(ev_ids))
                    .order_by(EvidenceItem.id.asc())
                    .with_for_update()
                ).scalars().all()

                locked_revs = self.session.execute(
                    select(EvidenceRevision)
                    .where(EvidenceRevision.tenant_id == tenant_id, EvidenceRevision.evidence_id.in_(ev_ids))
                    .order_by(EvidenceRevision.evidence_id.asc(), EvidenceRevision.revision_number.asc())
                    .with_for_update()
                ).scalars().all()

                file_ids = set()
                for r in locked_revs:
                    if r.file_ids:
                        for fid in r.file_ids:
                            try:
                                file_ids.add(UUID(str(fid)))
                            except Exception:
                                pass
                if file_ids:
                    sorted_fids = sorted(list(file_ids), key=lambda u: str(u))
                    self.session.execute(
                        select(StoredFile)
                        .where(StoredFile.id.in_(sorted_fids))
                        .order_by(StoredFile.id.asc())
                        .with_for_update()
                    ).scalars().all()

        assessment_svc = CustomerAssessmentService(self.session)
        work_items_data: list[dict[str, Any]] = []
        canonical_works: list[dict[str, Any]] = []

        for w in works:
            try:
                item_dto = assessment_svc._build_work_item(tenant_id, w.id, principal, tenant_context)
            except Exception as exc:
                blockers.append({
                    "code": "CORRUPT_WORK_ASSESSMENT",
                    "description": f"Error loading assessment state for work {w.id}: {exc}",
                    "work_id": str(w.id),
                    "control_code": str(w.control_version_id)[:8],
                })
                continue

            if item_dto.primary_state not in ("PASS", "NOT_APPLICABLE"):
                blockers.append({
                    "code": "CONTROL_NOT_SATISFIED",
                    "description": f"Control {w.control_version_id} in unsatisfactory state: {item_dto.primary_state}",
                    "work_id": str(w.id),
                    "control_code": str(w.control_version_id)[:8],
                })

            if item_dto.blockers:
                for b_code in item_dto.blockers:
                    # Treat validated current applicability N/A as satisfied for this workflow;
                    # do not treat informational CONTROL_NOT_APPLICABLE as a blocking finding.
                    if b_code == "CONTROL_NOT_APPLICABLE" and item_dto.primary_state == "NOT_APPLICABLE":
                        continue
                    blockers.append({
                        "code": b_code,
                        "description": f"Control {w.control_version_id} blocker: {b_code}",
                        "work_id": str(w.id),
                        "control_code": str(w.control_version_id)[:8],
                    })

            open_findings = [f for f in item_dto.findings if f.status in ("OPEN", "IN_REMEDIATION")]
            for fn in open_findings:
                blockers.append({
                    "code": "OPEN_FINDING",
                    "description": f"Open finding {fn.id} ({fn.severity}) on control {w.control_version_id}",
                    "work_id": str(w.id),
                    "control_code": str(w.control_version_id)[:8],
                })

            links_summary = []
            if item_dto.latest_assessment and item_dto.latest_assessment.evidence_pins:
                for pin in item_dto.latest_assessment.evidence_pins:
                    links_summary.append({
                        "link_id": str(pin.link_id),
                        "evidence_id": str(pin.evidence_id),
                        "revision_number": pin.revision_number,
                        "revision_digest": pin.revision_digest,
                        "file_hash": pin.file_hash,
                        "latest_review_event_id": str(pin.latest_review_event_id),
                    })

            result_val = item_dto.latest_assessment.result if item_dto.latest_assessment else None
            work_items_data.append({
                "work_id": str(w.id),
                "control_version_id": str(w.control_version_id),
                "work_version": w.version,
                "primary_state": item_dto.primary_state,
                "assessment_revision": item_dto.assessment_revision,
                "latest_assessment": {
                    "result": result_val,
                },
                "evidence_links": links_summary,
                "open_findings_count": len(open_findings),
            })

            canonical_works.append({
                "work_id": str(w.id),
                "control_version_id": str(w.control_version_id),
                "work_version": w.version,
                "primary_state": item_dto.primary_state,
                "assessment_revision": item_dto.assessment_revision,
                "assessment_event_id": str(item_dto.latest_assessment.event_id) if item_dto.latest_assessment else None,
                "assessment_result": result_val,
                "evidence_links": links_summary,
                "open_findings": [str(f.id) for f in open_findings],
            })

        projection_dict = {
            "adoption_id": str(adoption.id),
            "selection_revision": workspace.selection_revision,
            "answer_revision": evaluation.answer_revision,
            "answers_digest": answers.content_digest if answers else "",
            "evaluation_id": str(evaluation.id),
            "evaluation_digest": evaluation.content_digest,
            "pack_version_id": str(adoption.pack_version_id),
            "bundle_digest": adoption.bundle_digest,
            "is_scope_current": is_scope_current,
            "works": canonical_works,
        }

        review_fingerprint = hashlib.sha256(canonical_json(projection_dict).encode("utf-8")).hexdigest()
        review_payload = {
            "scope_snapshot_id": str(case.current_scope_snapshot_id) if case.current_scope_snapshot_id else "",
            "adoption_id": str(case.adoption_id),
            "work_items": work_items_data,
            "blockers": blockers,
            "review_fingerprint": review_fingerprint,
        }

        return review_payload, blockers, review_fingerprint, is_scope_current

    def get_eligible_actors(
        self,
        principal: Principal,
        tenant_context: TenantContext,
    ) -> list[PreauditActorDTO]:
        """List active tenant members with Owner or ComplianceManager roles."""
        self._verify_preaudit_admission(principal, tenant_context, operation="read")
        stmt = (
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.tenant_id == tenant_context.tenant_id,
                Membership.status == MembershipStatus.ACTIVE,
                User.status == UserStatus.ACTIVE,
                Membership.role.in_([Role.OWNER, Role.COMPLIANCE_MANAGER]),
            )
            .order_by(User.email.asc())
        )
        rows = self.session.execute(stmt).all()
        actors = []
        for m, u in rows:
            display_name = u.display_name or u.email.split("@")[0]
            actors.append(
                PreauditActorDTO(
                    user_id=u.id,
                    role=m.role.value,
                    email=u.email,
                    display_name=display_name,
                )
            )
        return actors

    def create_case(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        req: CreatePreauditRequest,
        request_id: str | None = None,
    ) -> PreauditDetailResponse:
        """Create a new pre-audit case in DRAFT status."""
        self._verify_preaudit_admission(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id

        req_digest = compute_digest(canonicalize_json(req.model_dump()))
        existing_event = self._check_idempotency(
            tenant_id=tenant_id,
            operation_id=req.operation_id,
            expected_preaudit_id=None,
            expected_event_type="CREATED",
            actor_user_id=principal.user_id,
            request_digest=req_digest,
        )
        if existing_event is not None:
            detail = self.get_case(principal, tenant_context, existing_event.preaudit_id)
            return detail.model_copy(
                update={
                    "replayed": True,
                    "applied_event_id": existing_event.id,
                    "applied_revision": existing_event.revision,
                    "applied_snapshot_id": existing_event.snapshot_id,
                }
            )

        if req.lead_user_id == req.reviewer_user_id:
            raise HTTPException(status_code=400, detail="Lead and reviewer must be different individuals")

        if principal.user_id != req.lead_user_id and tenant_context.role != Role.OWNER:
            raise HTTPException(status_code=403, detail="Only assigned lead or tenant Owner can create pre-audit case")

        for uid in (req.lead_user_id, req.reviewer_user_id):
            row = self.session.execute(
                select(Membership, User)
                .join(User, User.id == Membership.user_id)
                .where(
                    Membership.tenant_id == tenant_id,
                    Membership.user_id == uid,
                    Membership.status == MembershipStatus.ACTIVE,
                    User.status == UserStatus.ACTIVE,
                    Membership.role.in_([Role.OWNER, Role.COMPLIANCE_MANAGER]),
                )
            ).first()
            if not row:
                raise HTTPException(status_code=400, detail=f"User {uid} is not an active eligible tenant member")

        adopt = self.session.execute(
            select(CustomerDemoAdoption).where(
                CustomerDemoAdoption.tenant_id == tenant_id,
                CustomerDemoAdoption.id == req.adoption_id,
            )
        ).scalar_one_or_none()
        if not adopt:
            raise HTTPException(status_code=404, detail="Referenced adoption not found")

        workspace = self.session.execute(
            select(CustomerDemoWorkspace).where(CustomerDemoWorkspace.tenant_id == tenant_id)
        ).scalar_one_or_none()
        if not workspace or workspace.selection_revision != adopt.selection_revision:
            raise HTTPException(status_code=400, detail="Referenced adoption is not the current active adoption")

        case_id = uuid4()
        case = CustomerPreaudit(
            tenant_id=tenant_id,
            id=case_id,
            adoption_id=req.adoption_id,
            lead_user_id=req.lead_user_id,
            reviewer_user_id=req.reviewer_user_id,
            status="DRAFT",
            revision=1,
        )
        self.session.add(case)
        self.session.flush()

        event_id = uuid4()
        enc_payload = encrypt_event_payload(
            self.codec,
            tenant_id,
            event_id,
            {"title": req.title, "description": req.description},
        )
        event = CustomerPreauditEvent(
            tenant_id=tenant_id,
            id=event_id,
            preaudit_id=case_id,
            revision=1,
            operation_id=req.operation_id,
            request_digest=req_digest,
            event_type="CREATED",
            actor_user_id=principal.user_id,
            prior_status=None,
            new_status="DRAFT",
            payload_encrypted=enc_payload,
        )
        self.session.add(event)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_preaudit.case_created",
            resource_type="customer_preaudit",
            resource_id=str(case_id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
        )

        detail = self.get_case(principal, tenant_context, case_id)
        return detail.model_copy(
            update={
                "replayed": False,
                "applied_event_id": event.id,
                "applied_revision": event.revision,
                "applied_snapshot_id": event.snapshot_id,
            }
        )

    def get_case(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        case_id: UUID,
    ) -> PreauditDetailResponse:
        """Fetch pre-audit case details including snapshot references, real blockers, and currentness."""
        self._verify_preaudit_admission(principal, tenant_context, operation="read")
        tenant_id = tenant_context.tenant_id

        case = self.session.execute(
            select(CustomerPreaudit).where(
                CustomerPreaudit.tenant_id == tenant_id,
                CustomerPreaudit.id == case_id,
            )
        ).scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Pre-audit case not found")

        adopt = self.session.execute(
            select(CustomerDemoAdoption).where(
                CustomerDemoAdoption.tenant_id == tenant_id,
                CustomerDemoAdoption.id == case.adoption_id,
            )
        ).scalar_one()

        try:
            bundle = get_bundle_by_version_id(adopt.pack_version_id)
            pack_name = bundle.get("name", "Compliance Pack")
            pack_version = str(bundle.get("version", "1.0"))
        except Exception:
            pack_name = "Compliance Pack"
            pack_version = "1.0"

        lead_user = self.session.execute(
            select(User).where(User.id == case.lead_user_id)
        ).scalar_one_or_none()
        rev_user = self.session.execute(
            select(User).where(User.id == case.reviewer_user_id)
        ).scalar_one_or_none()
        lead_name = (lead_user.display_name or lead_user.email.split("@")[0]) if lead_user else str(case.lead_user_id)
        reviewer_name = (rev_user.display_name or rev_user.email.split("@")[0]) if rev_user else str(case.reviewer_user_id)

        review_proj, live_blockers_data, live_fingerprint, is_scope_current = self._compute_canonical_review_projection(
            tenant_id, case, principal, tenant_context, for_update=False
        )

        scope_digest = None
        if case.current_scope_snapshot_id:
            s_snap = self.session.execute(
                select(CustomerPreauditSnapshot).where(
                    CustomerPreauditSnapshot.tenant_id == tenant_id,
                    CustomerPreauditSnapshot.id == case.current_scope_snapshot_id,
                )
            ).scalar_one_or_none()
            if s_snap:
                scope_digest = s_snap.digest

        review_digest = None
        is_review_current = is_scope_current
        display_blockers: list[PreauditBlockerDTO] = []

        if case.current_review_snapshot_id:
            r_snap = self.session.execute(
                select(CustomerPreauditSnapshot).where(
                    CustomerPreauditSnapshot.tenant_id == tenant_id,
                    CustomerPreauditSnapshot.id == case.current_review_snapshot_id,
                )
            ).scalar_one_or_none()
            if r_snap:
                review_digest = r_snap.digest
                payload = decrypt_snapshot_payload(
                    self.codec, tenant_id, r_snap.id, r_snap.payload_encrypted, r_snap.digest
                )
                if live_fingerprint != payload.get("review_fingerprint"):
                    is_review_current = False
                for b in payload.get("blockers", []):
                    display_blockers.append(
                        PreauditBlockerDTO(
                            code=b.get("code", "BLOCKER"),
                            description=b.get("description", ""),
                            work_id=UUID(b["work_id"]) if b.get("work_id") else None,
                            control_code=b.get("control_code"),
                        )
                    )
        else:
            for b in live_blockers_data:
                display_blockers.append(
                    PreauditBlockerDTO(
                        code=b.get("code", "BLOCKER"),
                        description=b.get("description", ""),
                        work_id=UUID(b["work_id"]) if b.get("work_id") else None,
                        control_code=b.get("control_code"),
                    )
                )

        title = None
        description = None
        created_event = self.session.execute(
            select(CustomerPreauditEvent).where(
                CustomerPreauditEvent.tenant_id == tenant_id,
                CustomerPreauditEvent.preaudit_id == case.id,
                CustomerPreauditEvent.event_type == "CREATED",
            )
        ).scalar_one_or_none()
        if created_event:
            ev_payload = decrypt_event_payload(self.codec, tenant_id, created_event.id, created_event.payload_encrypted)
            title = ev_payload.get("title")
            description = ev_payload.get("description")

        return PreauditDetailResponse(
            id=case.id,
            tenant_id=case.tenant_id,
            adoption_id=case.adoption_id,
            pack_name=pack_name,
            pack_version=pack_version,
            lead_user_id=case.lead_user_id,
            reviewer_user_id=case.reviewer_user_id,
            lead_name=lead_name,
            reviewer_name=reviewer_name,
            status=case.status,
            revision=case.revision,
            current_scope_snapshot_id=case.current_scope_snapshot_id,
            current_scope_snapshot_digest=scope_digest,
            current_review_snapshot_id=case.current_review_snapshot_id,
            current_review_snapshot_digest=review_digest,
            is_scope_current=is_scope_current,
            is_review_current=is_review_current,
            blockers=display_blockers,
            title=title,
            description=description,
            created_at=case.created_at,
            updated_at=case.updated_at,
        )

    def list_cases(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        limit: int = 50,
        offset: int = 0,
    ) -> PreauditListResponse:
        """List pre-audit cases for tenant as summaries."""
        self._verify_preaudit_admission(principal, tenant_context, operation="read")
        tenant_id = tenant_context.tenant_id
        safe_limit = min(max(1, limit), 100)
        safe_offset = max(0, offset)

        total = self.session.execute(
            select(func.count()).select_from(CustomerPreaudit).where(CustomerPreaudit.tenant_id == tenant_id)
        ).scalar() or 0

        cases = self.session.execute(
            select(CustomerPreaudit)
            .where(CustomerPreaudit.tenant_id == tenant_id)
            .order_by(CustomerPreaudit.created_at.desc())
            .limit(safe_limit)
            .offset(safe_offset)
        ).scalars().all()

        items = []
        for c in cases:
            try:
                adopt = self.session.execute(
                    select(CustomerDemoAdoption).where(
                        CustomerDemoAdoption.tenant_id == tenant_id,
                        CustomerDemoAdoption.id == c.adoption_id,
                    )
                ).scalar_one()
                bundle = get_bundle_by_version_id(adopt.pack_version_id)
                pack_name = bundle.get("name", "Compliance Pack")
                pack_version = str(bundle.get("version", "1.0"))
            except Exception:
                pack_name = "Compliance Pack"
                pack_version = "1.0"

            created_event = self.session.execute(
                select(CustomerPreauditEvent).where(
                    CustomerPreauditEvent.tenant_id == tenant_id,
                    CustomerPreauditEvent.preaudit_id == c.id,
                    CustomerPreauditEvent.event_type == "CREATED",
                )
            ).scalar_one_or_none()
            title = f"Case {str(c.id)[:8]}"
            if created_event:
                ev_payload = decrypt_event_payload(self.codec, tenant_id, created_event.id, created_event.payload_encrypted)
                if ev_payload.get("title"):
                    title = ev_payload["title"]

            items.append(
                PreauditSummaryDTO(
                    id=c.id,
                    tenant_id=c.tenant_id,
                    adoption_id=c.adoption_id,
                    pack_name=pack_name,
                    pack_version=pack_version,
                    lead_user_id=c.lead_user_id,
                    reviewer_user_id=c.reviewer_user_id,
                    status=c.status,
                    revision=c.revision,
                    title=title,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                )
            )

        return PreauditListResponse(items=items, total=total)

    def get_case_history(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        case_id: UUID,
    ) -> PreauditHistoryResponse:
        """Fetch immutable history of case state transitions and events."""
        self._verify_preaudit_admission(principal, tenant_context, operation="read")
        tenant_id = tenant_context.tenant_id

        case = self.session.execute(
            select(CustomerPreaudit).where(
                CustomerPreaudit.tenant_id == tenant_id,
                CustomerPreaudit.id == case_id,
            )
        ).scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Pre-audit case not found")

        events = self.session.execute(
            select(CustomerPreauditEvent)
            .where(
                CustomerPreauditEvent.tenant_id == tenant_id,
                CustomerPreauditEvent.preaudit_id == case_id,
            )
            .order_by(CustomerPreauditEvent.revision.asc())
        ).scalars().all()

        dtos = []
        user_cache: dict[UUID, str] = {}
        for ev in events:
            if ev.actor_user_id not in user_cache:
                u = self.session.execute(select(User).where(User.id == ev.actor_user_id)).scalar_one_or_none()
                user_cache[ev.actor_user_id] = (u.display_name or u.email.split("@")[0]) if u else str(ev.actor_user_id)

            notes = None
            try:
                ev_payload = decrypt_event_payload(self.codec, tenant_id, ev.id, ev.payload_encrypted)
                notes = ev_payload.get("notes") or ev_payload.get("reason") or ev_payload.get("title")
            except Exception:
                pass

            dtos.append(
                PreauditEventDTO(
                    id=ev.id,
                    revision=ev.revision,
                    event_type=ev.event_type,
                    actor_user_id=ev.actor_user_id,
                    actor_name=user_cache[ev.actor_user_id],
                    snapshot_id=ev.snapshot_id,
                    prior_status=ev.prior_status,
                    new_status=ev.new_status,
                    notes=notes,
                    created_at=ev.created_at,
                )
            )

        return PreauditHistoryResponse(events=dtos)

    def freeze_scope(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        case_id: UUID,
        req: FreezeScopeRequest,
        request_id: str | None = None,
    ) -> PreauditDetailResponse:
        """Freeze scope snapshot for a DRAFT case. Assigned lead only."""
        self._verify_preaudit_admission(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id

        req_digest = compute_digest(canonicalize_json(req.model_dump()))
        existing_event = self._check_idempotency(
            tenant_id=tenant_id,
            operation_id=req.operation_id,
            expected_preaudit_id=case_id,
            expected_event_type="SCOPE_FROZEN",
            actor_user_id=principal.user_id,
            request_digest=req_digest,
        )
        if existing_event is not None:
            detail = self.get_case(principal, tenant_context, case_id)
            return detail.model_copy(
                update={
                    "replayed": True,
                    "applied_event_id": existing_event.id,
                    "applied_revision": existing_event.revision,
                    "applied_snapshot_id": existing_event.snapshot_id,
                }
            )

        case = self.session.execute(
            select(CustomerPreaudit)
            .where(CustomerPreaudit.tenant_id == tenant_id, CustomerPreaudit.id == case_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Pre-audit case not found")

        if case.revision != req.expected_revision:
            raise HTTPException(
                status_code=409,
                detail=f"Revision conflict: expected {req.expected_revision}, current {case.revision}",
            )

        # Assigned lead action only; no blanket Owner override
        if principal.user_id != case.lead_user_id:
            raise HTTPException(status_code=403, detail="Only assigned lead can freeze pre-audit scope")

        if case.status != "DRAFT":
            raise HTTPException(status_code=409, detail=f"Cannot freeze scope in {case.status} status; must be DRAFT")

        adopt = self.session.execute(
            select(CustomerDemoAdoption).where(
                CustomerDemoAdoption.tenant_id == tenant_id,
                CustomerDemoAdoption.id == case.adoption_id,
            )
        ).scalar_one()

        workspace = self.session.execute(
            select(CustomerDemoWorkspace).where(CustomerDemoWorkspace.tenant_id == tenant_id)
        ).scalar_one()
        if workspace.selection_revision != adopt.selection_revision:
            raise HTTPException(status_code=409, detail="Adoption is stale; newer pack has been selected")

        evaluation = self.session.execute(
            select(CustomerDemoEvaluation).where(
                CustomerDemoEvaluation.tenant_id == tenant_id,
                CustomerDemoEvaluation.id == adopt.evaluation_id,
            )
        ).scalar_one()

        control_version_pins, expected_cv_ids, req_results_map = self._derive_expected_scope_pins(
            tenant_id, adopt, evaluation
        )

        # Require complete initialized work set
        works = self.session.execute(
            select(CustomerControlWork).where(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.adoption_id == adopt.id,
            )
        ).scalars().all()

        if len(works) == 0:
            raise HTTPException(
                status_code=409,
                detail="Cannot freeze scope: initialized control work is empty for adopted pack",
            )

        found_cv_ids = {w.control_version_id for w in works}
        if len(found_cv_ids) != len(works):
            raise HTTPException(
                status_code=409,
                detail="Cannot freeze scope: duplicate control work items detected",
            )
        for exp_cv in expected_cv_ids:
            if exp_cv not in found_cv_ids:
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot freeze scope: missing initialized work for required control version {exp_cv}",
                )

        bundle = get_bundle_by_version_id(adopt.pack_version_id)
        scope_payload = {
            "pack_version_id": str(adopt.pack_version_id),
            "bundle_version": str(bundle.get("version", "1.0")),
            "bundle_digest": adopt.bundle_digest,
            "source_provenance_disclaimer": bundle.get("source_provenance_disclaimer", ""),
            "evaluation_id": str(adopt.evaluation_id),
            "evaluation_digest": evaluation.content_digest,
            "answer_revision": evaluation.answer_revision,
            "selection_revision": adopt.selection_revision,
            "requirement_results": evaluation.results,
            "control_version_pins": control_version_pins,
            "limitations": [
                "Synthetic demonstration pre-audit review scope.",
                "Frozen scope governs compliance procedures for this review.",
            ],
        }

        snap_id = uuid4()
        enc_payload, digest = encrypt_snapshot_payload(self.codec, tenant_id, snap_id, scope_payload)

        snapshot = CustomerPreauditSnapshot(
            tenant_id=tenant_id,
            id=snap_id,
            preaudit_id=case.id,
            kind="SCOPE",
            sequence=1,
            digest=digest,
            payload_encrypted=enc_payload,
            created_by_user_id=principal.user_id,
        )
        self.session.add(snapshot)
        self.session.flush()

        case.status = "FROZEN"
        case.current_scope_snapshot_id = snap_id
        case.revision = case.revision + 1
        self.session.flush()

        event_id = uuid4()
        event_enc = encrypt_event_payload(self.codec, tenant_id, event_id, {"snapshot_digest": digest})
        event = CustomerPreauditEvent(
            tenant_id=tenant_id,
            id=event_id,
            preaudit_id=case.id,
            revision=case.revision,
            operation_id=req.operation_id,
            request_digest=req_digest,
            event_type="SCOPE_FROZEN",
            actor_user_id=principal.user_id,
            snapshot_id=snap_id,
            prior_status="DRAFT",
            new_status="FROZEN",
            payload_encrypted=event_enc,
        )
        self.session.add(event)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_preaudit.scope_frozen",
            resource_type="customer_preaudit",
            resource_id=str(case.id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
        )

        detail = self.get_case(principal, tenant_context, case.id)
        return detail.model_copy(
            update={
                "replayed": False,
                "applied_event_id": event.id,
                "applied_revision": event.revision,
                "applied_snapshot_id": event.snapshot_id,
            }
        )

    def submit_review(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        case_id: UUID,
        req: SubmitReviewRequest,
        request_id: str | None = None,
    ) -> PreauditDetailResponse:
        """Capture review snapshot and transition case to IN_REVIEW. Assigned lead only."""
        self._verify_preaudit_admission(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id

        req_digest = compute_digest(canonicalize_json(req.model_dump()))
        existing_event = self._check_idempotency(
            tenant_id=tenant_id,
            operation_id=req.operation_id,
            expected_preaudit_id=case_id,
            expected_event_type="SUBMITTED",
            actor_user_id=principal.user_id,
            request_digest=req_digest,
        )
        if existing_event is not None:
            detail = self.get_case(principal, tenant_context, case_id)
            return detail.model_copy(
                update={
                    "replayed": True,
                    "applied_event_id": existing_event.id,
                    "applied_revision": existing_event.revision,
                    "applied_snapshot_id": existing_event.snapshot_id,
                }
            )

        case = self.session.execute(
            select(CustomerPreaudit)
            .where(CustomerPreaudit.tenant_id == tenant_id, CustomerPreaudit.id == case_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Pre-audit case not found")

        if case.revision != req.expected_revision:
            raise HTTPException(
                status_code=409,
                detail=f"Revision conflict: expected {req.expected_revision}, current {case.revision}",
            )

        # Assigned lead action only; no blanket Owner override
        if principal.user_id != case.lead_user_id:
            raise HTTPException(status_code=403, detail="Only assigned lead can submit pre-audit review")

        if case.status not in ("FROZEN", "CHANGES_REQUESTED"):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot submit review in {case.status} status; must be FROZEN or CHANGES_REQUESTED",
            )

        if not case.current_scope_snapshot_id:
            raise HTTPException(status_code=409, detail="Pre-audit scope has not been frozen")

        review_proj, blockers, review_fingerprint, is_scope_current = self._compute_canonical_review_projection(
            tenant_id, case, principal, tenant_context, for_update=True
        )

        if not is_scope_current:
            raise HTTPException(status_code=409, detail="Cannot submit review: scope is stale, workspace has changed")

        last_seq = self.session.execute(
            select(func.max(CustomerPreauditSnapshot.sequence)).where(
                CustomerPreauditSnapshot.tenant_id == tenant_id,
                CustomerPreauditSnapshot.preaudit_id == case.id,
                CustomerPreauditSnapshot.kind == "REVIEW",
            )
        ).scalar() or 0
        next_seq = last_seq + 1

        review_payload = {
            "scope_snapshot_id": str(case.current_scope_snapshot_id),
            "adoption_id": str(case.adoption_id),
            "work_items": review_proj.get("work_items", []),
            "blockers": blockers,
            "review_fingerprint": review_fingerprint,
            "submission_notes": req.submission_notes,
        }

        snap_id = uuid4()
        enc_payload, digest = encrypt_snapshot_payload(self.codec, tenant_id, snap_id, review_payload)

        snapshot = CustomerPreauditSnapshot(
            tenant_id=tenant_id,
            id=snap_id,
            preaudit_id=case.id,
            kind="REVIEW",
            sequence=next_seq,
            digest=digest,
            payload_encrypted=enc_payload,
            created_by_user_id=principal.user_id,
        )
        self.session.add(snapshot)
        self.session.flush()

        prior_status = case.status
        case.status = "IN_REVIEW"
        case.current_review_snapshot_id = snap_id
        case.revision = case.revision + 1
        self.session.flush()

        event_id = uuid4()
        event_enc = encrypt_event_payload(
            self.codec,
            tenant_id,
            event_id,
            {"notes": req.submission_notes, "snapshot_digest": digest},
        )
        event = CustomerPreauditEvent(
            tenant_id=tenant_id,
            id=event_id,
            preaudit_id=case.id,
            revision=case.revision,
            operation_id=req.operation_id,
            request_digest=req_digest,
            event_type="SUBMITTED",
            actor_user_id=principal.user_id,
            snapshot_id=snap_id,
            prior_status=prior_status,
            new_status="IN_REVIEW",
            payload_encrypted=event_enc,
        )
        self.session.add(event)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_preaudit.review_submitted",
            resource_type="customer_preaudit",
            resource_id=str(case.id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
        )

        detail = self.get_case(principal, tenant_context, case.id)
        return detail.model_copy(
            update={
                "replayed": False,
                "applied_event_id": event.id,
                "applied_revision": event.revision,
                "applied_snapshot_id": event.snapshot_id,
            }
        )

    def review_decision(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        case_id: UUID,
        req: ReviewDecisionRequest,
        request_id: str | None = None,
    ) -> PreauditDetailResponse:
        """Independent reviewer records review decision (ACCEPT or REQUEST_CHANGES)."""
        self._verify_preaudit_admission(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id

        req_digest = compute_digest(canonicalize_json(req.model_dump()))
        expected_type = "REVIEWED" if req.decision == "ACCEPT" else "CHANGES_REQUESTED"
        existing_event = self._check_idempotency(
            tenant_id=tenant_id,
            operation_id=req.operation_id,
            expected_preaudit_id=case_id,
            expected_event_type=expected_type,
            actor_user_id=principal.user_id,
            request_digest=req_digest,
        )
        if existing_event is not None:
            detail = self.get_case(principal, tenant_context, case_id)
            return detail.model_copy(
                update={
                    "replayed": True,
                    "applied_event_id": existing_event.id,
                    "applied_revision": existing_event.revision,
                    "applied_snapshot_id": existing_event.snapshot_id,
                }
            )

        case = self.session.execute(
            select(CustomerPreaudit)
            .where(CustomerPreaudit.tenant_id == tenant_id, CustomerPreaudit.id == case_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Pre-audit case not found")

        if case.revision != req.expected_revision:
            raise HTTPException(
                status_code=409,
                detail=f"Revision conflict: expected {req.expected_revision}, current {case.revision}",
            )

        if principal.user_id != case.reviewer_user_id:
            raise HTTPException(status_code=403, detail="Only assigned reviewer can record review decision")
        if principal.user_id == case.lead_user_id:
            raise HTTPException(status_code=403, detail="Self-review prohibited: reviewer cannot be the lead")

        if case.status != "IN_REVIEW":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot record review decision in {case.status} status; must be IN_REVIEW",
            )

        if req.snapshot_id != case.current_review_snapshot_id:
            raise HTTPException(status_code=409, detail="Snapshot ID does not match current review snapshot")

        r_snap = self.session.execute(
            select(CustomerPreauditSnapshot).where(
                CustomerPreauditSnapshot.tenant_id == tenant_id,
                CustomerPreauditSnapshot.id == case.current_review_snapshot_id,
            )
        ).scalar_one()

        if r_snap.digest != req.snapshot_digest.lower():
            raise HTTPException(status_code=409, detail="Snapshot digest does not match current review snapshot")

        review_proj, live_blockers, live_fingerprint, is_scope_current = self._compute_canonical_review_projection(
            tenant_id, case, principal, tenant_context, for_update=True
        )

        snap_payload = decrypt_snapshot_payload(
            self.codec, tenant_id, r_snap.id, r_snap.payload_encrypted, r_snap.digest
        )

        if not is_scope_current or live_fingerprint != snap_payload.get("review_fingerprint"):
            raise HTTPException(
                status_code=409,
                detail="Review snapshot is stale; underlying compliance work has changed",
            )

        if req.decision == "ACCEPT":
            blockers = snap_payload.get("blockers", [])
            if len(blockers) > 0:
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot accept review with {len(blockers)} outstanding blockers; reviewer must request changes",
                )
            new_status = "REVIEWED"
            event_type = "REVIEWED"
            action_name = "customer_preaudit.review_accepted"
        else:
            new_status = "CHANGES_REQUESTED"
            event_type = "CHANGES_REQUESTED"
            action_name = "customer_preaudit.changes_requested"

        prior_status = case.status
        case.status = new_status
        case.revision = case.revision + 1
        self.session.flush()

        event_id = uuid4()
        event_enc = encrypt_event_payload(
            self.codec,
            tenant_id,
            event_id,
            {"notes": req.notes, "decision": req.decision},
        )
        event = CustomerPreauditEvent(
            tenant_id=tenant_id,
            id=event_id,
            preaudit_id=case.id,
            revision=case.revision,
            operation_id=req.operation_id,
            request_digest=req_digest,
            event_type=event_type,
            actor_user_id=principal.user_id,
            snapshot_id=case.current_review_snapshot_id,
            prior_status=prior_status,
            new_status=new_status,
            payload_encrypted=event_enc,
        )
        self.session.add(event)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action=action_name,
            resource_type="customer_preaudit",
            resource_id=str(case.id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
        )

        detail = self.get_case(principal, tenant_context, case.id)
        return detail.model_copy(
            update={
                "replayed": False,
                "applied_event_id": event.id,
                "applied_revision": event.revision,
                "applied_snapshot_id": event.snapshot_id,
            }
        )

    def approve_case(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        case_id: UUID,
        req: ApprovePreauditRequest,
        request_id: str | None = None,
    ) -> PreauditDetailResponse:
        """Tenant Owner grants explicit approval to a REVIEWED case."""
        self._verify_preaudit_admission(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id

        if tenant_context.role != Role.OWNER:
            raise HTTPException(status_code=403, detail="Only tenant Owner can grant pre-audit approval")

        req_digest = compute_digest(canonicalize_json(req.model_dump()))
        existing_event = self._check_idempotency(
            tenant_id=tenant_id,
            operation_id=req.operation_id,
            expected_preaudit_id=case_id,
            expected_event_type="APPROVED",
            actor_user_id=principal.user_id,
            request_digest=req_digest,
        )
        if existing_event is not None:
            detail = self.get_case(principal, tenant_context, case_id)
            return detail.model_copy(
                update={
                    "replayed": True,
                    "applied_event_id": existing_event.id,
                    "applied_revision": existing_event.revision,
                    "applied_snapshot_id": existing_event.snapshot_id,
                }
            )

        case = self.session.execute(
            select(CustomerPreaudit)
            .where(CustomerPreaudit.tenant_id == tenant_id, CustomerPreaudit.id == case_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Pre-audit case not found")

        if case.revision != req.expected_revision:
            raise HTTPException(
                status_code=409,
                detail=f"Revision conflict: expected {req.expected_revision}, current {case.revision}",
            )

        if principal.user_id == case.reviewer_user_id:
            raise HTTPException(status_code=403, detail="Approver cannot be the independent reviewer")

        if case.status != "REVIEWED":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot approve case in {case.status} status; must be REVIEWED",
            )

        if req.snapshot_id != case.current_review_snapshot_id:
            raise HTTPException(status_code=409, detail="Snapshot ID does not match current review snapshot")

        r_snap = self.session.execute(
            select(CustomerPreauditSnapshot).where(
                CustomerPreauditSnapshot.tenant_id == tenant_id,
                CustomerPreauditSnapshot.id == case.current_review_snapshot_id,
            )
        ).scalar_one()

        if r_snap.digest != req.snapshot_digest.lower():
            raise HTTPException(status_code=409, detail="Snapshot digest does not match current review snapshot")

        review_proj, live_blockers, live_fingerprint, is_scope_current = self._compute_canonical_review_projection(
            tenant_id, case, principal, tenant_context, for_update=True
        )

        snap_payload = decrypt_snapshot_payload(
            self.codec, tenant_id, r_snap.id, r_snap.payload_encrypted, r_snap.digest
        )

        if not is_scope_current or live_fingerprint != snap_payload.get("review_fingerprint"):
            raise HTTPException(
                status_code=409,
                detail="Cannot approve: review snapshot is stale, underlying work has changed",
            )

        blockers = snap_payload.get("blockers", [])
        if len(blockers) > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot approve case with {len(blockers)} outstanding blockers",
            )

        prior_status = case.status
        case.status = "APPROVED"
        case.revision = case.revision + 1
        self.session.flush()

        event_id = uuid4()
        event_enc = encrypt_event_payload(self.codec, tenant_id, event_id, {"notes": req.approval_notes})
        event = CustomerPreauditEvent(
            tenant_id=tenant_id,
            id=event_id,
            preaudit_id=case.id,
            revision=case.revision,
            operation_id=req.operation_id,
            request_digest=req_digest,
            event_type="APPROVED",
            actor_user_id=principal.user_id,
            snapshot_id=case.current_review_snapshot_id,
            prior_status=prior_status,
            new_status="APPROVED",
            payload_encrypted=event_enc,
        )
        self.session.add(event)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_preaudit.case_approved",
            resource_type="customer_preaudit",
            resource_id=str(case.id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
        )

        detail = self.get_case(principal, tenant_context, case.id)
        return detail.model_copy(
            update={
                "replayed": False,
                "applied_event_id": event.id,
                "applied_revision": event.revision,
                "applied_snapshot_id": event.snapshot_id,
            }
        )

    def cancel_case(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        case_id: UUID,
        req: CancelPreauditRequest,
        request_id: str | None = None,
    ) -> PreauditDetailResponse:
        """Tenant Owner cancels a nonterminal pre-audit case."""
        self._verify_preaudit_admission(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id

        if tenant_context.role != Role.OWNER:
            raise HTTPException(status_code=403, detail="Only tenant Owner can cancel pre-audit case")

        req_digest = compute_digest(canonicalize_json(req.model_dump()))
        existing_event = self._check_idempotency(
            tenant_id=tenant_id,
            operation_id=req.operation_id,
            expected_preaudit_id=case_id,
            expected_event_type="CANCELLED",
            actor_user_id=principal.user_id,
            request_digest=req_digest,
        )
        if existing_event is not None:
            detail = self.get_case(principal, tenant_context, case_id)
            return detail.model_copy(
                update={
                    "replayed": True,
                    "applied_event_id": existing_event.id,
                    "applied_revision": existing_event.revision,
                    "applied_snapshot_id": existing_event.snapshot_id,
                }
            )

        case = self.session.execute(
            select(CustomerPreaudit)
            .where(CustomerPreaudit.tenant_id == tenant_id, CustomerPreaudit.id == case_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Pre-audit case not found")

        if case.revision != req.expected_revision:
            raise HTTPException(
                status_code=409,
                detail=f"Revision conflict: expected {req.expected_revision}, current {case.revision}",
            )

        if case.status in ("APPROVED", "CANCELLED"):
            raise HTTPException(status_code=409, detail=f"Cannot cancel terminal case in {case.status} status")

        prior_status = case.status
        case.status = "CANCELLED"
        case.revision = case.revision + 1
        self.session.flush()

        event_id = uuid4()
        event_enc = encrypt_event_payload(self.codec, tenant_id, event_id, {"reason": req.reason})
        event = CustomerPreauditEvent(
            tenant_id=tenant_id,
            id=event_id,
            preaudit_id=case.id,
            revision=case.revision,
            operation_id=req.operation_id,
            request_digest=req_digest,
            event_type="CANCELLED",
            actor_user_id=principal.user_id,
            snapshot_id=case.current_review_snapshot_id,
            prior_status=prior_status,
            new_status="CANCELLED",
            payload_encrypted=event_enc,
        )
        self.session.add(event)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_preaudit.case_cancelled",
            resource_type="customer_preaudit",
            resource_id=str(case.id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
        )

        detail = self.get_case(principal, tenant_context, case.id)
        return detail.model_copy(
            update={
                "replayed": False,
                "applied_event_id": event.id,
                "applied_revision": event.revision,
                "applied_snapshot_id": event.snapshot_id,
            }
        )

    def download_report(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        case_id: UUID,
        req: DownloadPreauditReportRequest,
        request_id: str | None = None,
    ) -> tuple[bytes, str, CustomerPreaudit, CustomerPreauditSnapshot]:
        """Download private report archive from frozen snapshot. Stages audit and leaves commit to caller."""
        self._verify_preaudit_admission(principal, tenant_context, operation="read")
        tenant_id = tenant_context.tenant_id

        case = self.session.execute(
            select(CustomerPreaudit).where(
                CustomerPreaudit.tenant_id == tenant_id,
                CustomerPreaudit.id == case_id,
            )
        ).scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Pre-audit case not found")

        if case.revision != req.expected_revision:
            raise HTTPException(status_code=409, detail="Revision mismatch for report download")

        if not case.current_review_snapshot_id or case.current_review_snapshot_id != req.snapshot_id:
            raise HTTPException(status_code=409, detail="Case has no matching frozen review snapshot")

        snapshot = self.session.execute(
            select(CustomerPreauditSnapshot).where(
                CustomerPreauditSnapshot.tenant_id == tenant_id,
                CustomerPreauditSnapshot.id == case.current_review_snapshot_id,
            )
        ).scalar_one()

        payload = decrypt_snapshot_payload(
            self.codec, tenant_id, snapshot.id, snapshot.payload_encrypted, snapshot.digest
        )

        events = self.session.execute(
            select(CustomerPreauditEvent)
            .where(
                CustomerPreauditEvent.tenant_id == tenant_id,
                CustomerPreauditEvent.preaudit_id == case.id,
            )
            .order_by(CustomerPreauditEvent.revision.asc())
        ).scalars().all()

        review_proj, live_blockers, live_fingerprint, is_scope_current = self._compute_canonical_review_projection(
            tenant_id, case, principal, tenant_context, for_update=False
        )
        is_current = bool(is_scope_current and (live_fingerprint == payload.get("review_fingerprint")))

        zip_bytes, zip_sha256 = generate_preaudit_report_archive(
            tenant_id=tenant_id,
            case=case,
            snapshot=snapshot,
            snapshot_payload=payload,
            events=events,
            is_current=is_current,
        )

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_preaudit.report_download_prepared",
            resource_type="customer_preaudit",
            resource_id=str(case.id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
        )
        self.session.flush()

        return zip_bytes, zip_sha256, case, snapshot

    def validate_approved_case_for_verification(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        case_id: UUID,
        expected_case_revision: int,
        expected_snapshot_id: UUID,
        expected_snapshot_digest: str,
        for_update: bool = True,
    ) -> tuple[CustomerPreaudit, CustomerPreauditSnapshot, dict[str, Any], CustomerPreauditEvent]:
        """Narrow locked approved-input adapter for readiness verification issuance."""
        self._verify_preaudit_admission(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id

        if tenant_context.role != Role.OWNER:
            raise HTTPException(status_code=403, detail="Only tenant Owner can issue readiness verification")

        stmt = select(CustomerPreaudit).where(
            CustomerPreaudit.tenant_id == tenant_id,
            CustomerPreaudit.id == case_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        case = self.session.execute(stmt).scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Pre-audit case not found")

        if case.revision != expected_case_revision:
            raise HTTPException(
                status_code=409,
                detail=f"Revision conflict: expected case revision {expected_case_revision}, current {case.revision}",
            )

        if case.status != "APPROVED":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot issue verification for pre-audit in {case.status} status; must be APPROVED",
            )

        if principal.user_id == case.reviewer_user_id:
            raise HTTPException(status_code=403, detail="Issuer cannot be the independent reviewer")

        if case.current_review_snapshot_id != expected_snapshot_id:
            raise HTTPException(
                status_code=409,
                detail="Snapshot ID does not match current review snapshot",
            )

        r_snap = self.session.execute(
            select(CustomerPreauditSnapshot).where(
                CustomerPreauditSnapshot.tenant_id == tenant_id,
                CustomerPreauditSnapshot.id == expected_snapshot_id,
            )
        ).scalar_one_or_none()
        if not r_snap:
            raise HTTPException(status_code=404, detail="Review snapshot not found")

        if r_snap.digest != expected_snapshot_digest.lower():
            raise HTTPException(
                status_code=409,
                detail="Snapshot digest does not match current review snapshot",
            )

        snap_payload = decrypt_snapshot_payload(
            self.codec, tenant_id, r_snap.id, r_snap.payload_encrypted, r_snap.digest
        )

        approval_event = self.session.execute(
            select(CustomerPreauditEvent)
            .where(
                CustomerPreauditEvent.tenant_id == tenant_id,
                CustomerPreauditEvent.preaudit_id == case.id,
                CustomerPreauditEvent.snapshot_id == r_snap.id,
                CustomerPreauditEvent.event_type == "APPROVED",
            )
            .order_by(CustomerPreauditEvent.revision.desc())
        ).scalars().first()
        if not approval_event:
            raise HTTPException(
                status_code=409,
                detail="Pre-audit case lacks recorded Owner approval event for current snapshot",
            )

        review_proj, live_blockers, live_fingerprint, is_scope_current = self._compute_canonical_review_projection(
            tenant_id, case, principal, tenant_context, for_update=for_update
        )

        if not is_scope_current or live_fingerprint != snap_payload.get("review_fingerprint"):
            raise HTTPException(
                status_code=409,
                detail="Pre-audit review snapshot is stale; underlying compliance work has changed",
            )

        blockers = snap_payload.get("blockers", [])
        if len(blockers) > 0 or len(live_blockers) > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot issue verification with {len(blockers) or len(live_blockers)} outstanding blockers",
            )

        work_items = snap_payload.get("work_items", [])
        if not work_items:
            raise HTTPException(
                status_code=409,
                detail="Cannot issue verification from an empty work set",
            )

        return case, r_snap, snap_payload, approval_event

    def check_case_currency(
        self,
        tenant_id: UUID,
        case_id: UUID,
        snapshot_id: UUID,
        snapshot_digest: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if source pre-audit snapshot remains current without mutating database or emitting events."""
        case = self.session.execute(
            select(CustomerPreaudit).where(
                CustomerPreaudit.tenant_id == tenant_id,
                CustomerPreaudit.id == case_id,
            )
        ).scalar_one_or_none()
        if not case:
            return False, "Source pre-audit case not found"
        if case.status == "CANCELLED":
            return False, "Source pre-audit case was cancelled"
        if case.current_review_snapshot_id != snapshot_id:
            return False, "Source pre-audit review snapshot has been replaced"

        r_snap = self.session.execute(
            select(CustomerPreauditSnapshot).where(
                CustomerPreauditSnapshot.tenant_id == tenant_id,
                CustomerPreauditSnapshot.id == snapshot_id,
            )
        ).scalar_one_or_none()
        if not r_snap:
            return False, "Source pre-audit review snapshot not found"
        if snapshot_digest is not None and r_snap.digest != snapshot_digest.lower():
            return False, "Source snapshot digest mismatch"

        try:
            snap_payload = decrypt_snapshot_payload(
                self.codec, tenant_id, r_snap.id, r_snap.payload_encrypted, r_snap.digest
            )
        except Exception:
            return False, "Snapshot payload decryption failed"

        try:
            lead_mem = self.session.query(Membership).filter_by(tenant_id=tenant_id, user_id=case.lead_user_id).first()
            lead_role = lead_mem.role if lead_mem else Role.COMPLIANCE_MANAGER
            dummy_principal = Principal(user_id=case.lead_user_id, mfa_verified=True)
            dummy_ctx = TenantContext(tenant_id=tenant_id, user_id=case.lead_user_id, role=lead_role)
            _, live_blockers, live_fingerprint, is_scope_current = self._compute_canonical_review_projection(
                tenant_id, case, dummy_principal, dummy_ctx, for_update=False
            )
            if not is_scope_current or live_fingerprint != snap_payload.get("review_fingerprint"):
                return False, "Underlying compliance work or scope has changed since review freeze"
            if len(live_blockers) > 0:
                return False, "Underlying compliance work has new blocking gaps"
        except Exception as exc:
            return False, f"Currency check failed: {exc}"

        return True, None

