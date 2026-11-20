"""Customer Control Work Service for MVP-B.

Implements version-pinned control work, owner assignment, evidence creation,
snapshot revision pinning, deliberate revision reuse, suitability review,
and event history under tenant isolation.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize
from conformly.authz.roles import Capability, Role
from conformly.catalog_v2.digest import canonical_json, format_canonical_datetime
from conformly.compliance.models import (
    EvidenceItem,
    EvidenceRevision,
)
from conformly.compliance.service import ComplianceService
from conformly.config import get_settings
from conformly.crypto.envelope import get_envelope_encryption_service
from conformly.crypto.fields import get_encrypted_field_codec
from conformly.crypto.policy import DataClassification
from conformly.crypto.types import EncryptionContext
from conformly.customer_demo.fixture import (
    PACK_VERSION_V2_ID,
    SOURCE_PROVENANCE_DISCLAIMER,
    get_bundle_by_version_id,
    get_bundle_digest,
)
from conformly.customer_demo.models import (
    CustomerDemoAdoption,
    CustomerDemoEvaluation,
    CustomerDemoWorkspace,
)
from conformly.customer_demo.policy import (
    CustomerDemoAdmissionError,
    verify_customer_demo_admission,
)
from conformly.customer_demo.schemas import RequirementEvaluationResultDTO
from conformly.customer_demo.work_models import (
    CustomerControlEvidenceLink,
    CustomerControlWork,
    CustomerControlWorkEvent,
)
from conformly.customer_demo.work_scanner import (
    StrictEvidenceMalwareScanner,
)
from conformly.customer_demo.work_schemas import (
    CreateEvidenceRequest,
    CreateLinkRequest,
    CreateReviewRequest,
    EventDTO,
    InitializeWorkRequest,
    LinkDTO,
    MutationReceipt,
    OwnerDirectoryItemDTO,
    OwnerDirectoryResponse,
    PatchWorkRequest,
    WorkDTO,
    WorkHistoryResponse,
    WorkListResponse,
)
from conformly.entitlements.models import TenantEntitlement
from conformly.identity.models import Membership, MembershipStatus, User, UserStatus
from conformly.storage.models import StoredFile, StoredFileStatus
from conformly.storage.providers import get_storage_provider
from conformly.storage.service import StorageService


def compute_evidence_revision_digest(
    *,
    evidence_id: UUID,
    revision_number: int,
    title: str,
    description: str,
    classification: str,
    status_val: str,
    valid_from: datetime | None,
    valid_until: datetime | None,
    file_ids: Sequence[UUID | str],
    control_ids: Sequence[UUID | str],
) -> str:
    """Compute deterministic SHA-256 digest of an evidence revision snapshot."""
    payload = {
        "classification": str(classification),
        "control_ids": sorted(str(cid).lower() for cid in control_ids),
        "description": str(description),
        "evidence_id": str(evidence_id).lower(),
        "file_ids": sorted(str(fid).lower() for fid in file_ids),
        "revision_number": int(revision_number),
        "status": str(status_val),
        "title": str(title),
        "valid_from": format_canonical_datetime(valid_from) if valid_from else None,
        "valid_until": format_canonical_datetime(valid_until) if valid_until else None,
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ValidatedAssessmentLink:
    link_id: UUID
    work_id: UUID
    evidence_id: UUID
    revision_number: int
    revision_digest: str
    latest_review_event_id: UUID
    file_id: UUID
    file_hash: str
    scan_verified_at: datetime | None


class CustomerControlWorkService:
    """Business logic for Customer Control Work & Evidence integration."""

    def __init__(
        self,
        session: Session,
        *,
        scanner: StrictEvidenceMalwareScanner | None = None,
        storage_service: StorageService | None = None,
    ) -> None:
        self.session = session
        self.codec = get_encrypted_field_codec()
        self.scanner = scanner or StrictEvidenceMalwareScanner()
        self._storage_service = storage_service

    def _get_storage_service(self) -> StorageService:
        if self._storage_service is not None:
            return self._storage_service
        settings = get_settings()
        return StorageService(
            session=self.session,
            storage_provider=get_storage_provider(),
            encryption_service=get_envelope_encryption_service(),
            malware_scanner=self.scanner,
            max_file_size_bytes=settings.max_file_size_bytes,
        )

    @staticmethod
    def _ensure_utc(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)

    def _verify_evidence_entitlement(self, tenant_id: UUID) -> None:
        """Enforce evidence module entitlement by direct tenant-scoped query."""
        ent = self.session.scalar(
            select(TenantEntitlement).where(TenantEntitlement.tenant_id == tenant_id)
        )
        if ent is None:
            raise CustomerDemoAdmissionError(
                "Tenant entitlement missing", status_code=status.HTTP_403_FORBIDDEN
            )
        if "evidence" not in (ent.enabled_modules or []):
            raise CustomerDemoAdmissionError(
                "Evidence module not entitled for tenant", status_code=status.HTTP_403_FORBIDDEN
            )
        now = datetime.now(UTC)
        eff_from = self._ensure_utc(ent.effective_from)
        eff_until = self._ensure_utc(ent.effective_until)
        if eff_from and eff_from > now:
            raise CustomerDemoAdmissionError(
                "Tenant entitlement not yet effective", status_code=status.HTTP_403_FORBIDDEN
            )
        if eff_until and eff_until < now:
            raise CustomerDemoAdmissionError(
                "Tenant entitlement expired", status_code=status.HTTP_403_FORBIDDEN
            )

    def _verify_eligible_owner(self, tenant_id: UUID, user_id: UUID) -> User:
        """Validate that a user is an eligible active control owner in the tenant."""
        now = datetime.now(UTC)
        stmt = (
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.tenant_id == tenant_id,
                Membership.user_id == user_id,
                Membership.status == MembershipStatus.ACTIVE,
                Membership.role.in_([Role.OWNER, Role.COMPLIANCE_MANAGER, Role.CONTROL_OWNER]),
                Membership.legal_entity_id.is_(None),
                Membership.business_unit_id.is_(None),
                Membership.is_workforce.is_(False),
                Membership.is_external_advisor.is_(False),
                (Membership.expires_at.is_(None) | (Membership.expires_at > now)),
                User.status == UserStatus.ACTIVE,
            )
        )
        user = self.session.scalar(stmt)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Selected owner is not an eligible active member of this tenant",
            )
        return user

    def _admit_work_service_caller(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        operation: Literal["read", "mutate"],
    ) -> Membership:
        """Centralized admission helper for all public work_service.py entries.

        Enforces direct database validation of User, Membership, Role, entitlement,
        MFA, capabilities, tenant lifecycle, and subscope flags.
        """
        # Base customer demo admission (MFA, whole-tenant context, role in context, capabilities, tenant lifecycle, DB connection)
        verify_customer_demo_admission(
            principal,
            tenant_context,
            operation=operation,
            session=self.session,
        )

        # Identity match between principal and tenant context
        if principal.user_id != tenant_context.user_id:
            raise CustomerDemoAdmissionError(
                "Principal and tenant context user identity mismatch",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Direct DB lookup of active User
        user = self.session.query(User).filter(User.id == principal.user_id).first()
        if user is None:
            raise CustomerDemoAdmissionError(
                "User not found",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        if user.status != UserStatus.ACTIVE:
            raise CustomerDemoAdmissionError(
                f"User account '{user.status.value}' is not active",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Direct DB lookup of active unexpired same-tenant Membership
        membership = (
            self.session.query(Membership)
            .filter(
                Membership.tenant_id == tenant_context.tenant_id,
                Membership.user_id == principal.user_id,
            )
            .first()
        )
        if membership is None:
            raise CustomerDemoAdmissionError(
                "Membership not found for tenant",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        if membership.status != MembershipStatus.ACTIVE:
            raise CustomerDemoAdmissionError(
                f"Membership status '{membership.status.value}' is not active",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        now = datetime.now(UTC)
        if membership.expires_at is not None:
            exp = self._ensure_utc(membership.expires_at)
            if exp and exp <= now:
                raise CustomerDemoAdmissionError(
                    "Membership has expired",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

        if membership.role != tenant_context.role:
            raise CustomerDemoAdmissionError(
                f"Membership role '{membership.role.value}' does not match context role '{tenant_context.role.value}'",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if membership.role not in {Role.OWNER, Role.COMPLIANCE_MANAGER}:
            raise CustomerDemoAdmissionError(
                f"Membership role '{membership.role.value}' not admitted to customer demo",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if membership.is_workforce:
            raise CustomerDemoAdmissionError(
                "Workforce membership denied for customer demo",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        if membership.is_external_advisor:
            raise CustomerDemoAdmissionError(
                "External advisor membership denied for customer demo",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        if membership.legal_entity_id is not None or membership.business_unit_id is not None:
            raise CustomerDemoAdmissionError(
                "Sub-entity scoped membership denied for customer demo",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Direct DB check for evidence entitlement
        self._verify_evidence_entitlement(tenant_context.tenant_id)

        return membership

    def _validate_evidence_lifecycle_and_proof(
        self,
        *,
        tenant_id: UUID,
        evidence_id: UUID,
        revision_number: int,
        expected_revision_digest: str | None = None,
        link_id: UUID | None = None,
        rationale_encrypted: dict[str, Any] | str | None = None,
        require_valid_proof: bool = True,
    ) -> tuple[EvidenceItem, EvidenceRevision, StoredFile, dict[str, Any] | None, datetime | None]:
        """Shared tenant-scoped validation path for evidence lifecycle and scan proof.

        Evaluates BOTH pinned revision and current EvidenceItem:
        - Rejects absent head or revision
        - Rejects ARCHIVED, REJECTED, EXPIRED statuses
        - Rejects not-yet-valid or expired dates (expiry boundary: now >= valid_until)
        - Rejects changed digest
        - Rejects wrong/multiple/oversize (> 1 MiB) files
        - Rejects unavailable or inactive storage
        - Validates decrypted scan proof against current stored file hash and identity
        """
        now = datetime.now(UTC)

        # 1. Current EvidenceItem (head)
        evidence_item = self.session.scalar(
            select(EvidenceItem).where(
                EvidenceItem.tenant_id == tenant_id,
                EvidenceItem.id == evidence_id,
            )
        )
        if evidence_item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence item not found",
            )

        head_status = str(
            evidence_item.status.value
            if hasattr(evidence_item.status, "value")
            else evidence_item.status
        ).lower()
        if head_status in ("archived", "rejected", "expired"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Evidence item lifecycle state '{head_status}' is not valid",
            )

        ev_from = self._ensure_utc(evidence_item.valid_from)
        ev_until = self._ensure_utc(evidence_item.valid_until)
        if ev_from and ev_from > now:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evidence item is not yet valid",
            )
        if ev_until and ev_until <= now:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evidence item has expired",
            )

        # 2. Pinned EvidenceRevision
        rev = self.session.scalar(
            select(EvidenceRevision).where(
                EvidenceRevision.tenant_id == tenant_id,
                EvidenceRevision.evidence_id == evidence_id,
                EvidenceRevision.revision_number == revision_number,
            )
        )
        if rev is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Pinned evidence revision missing",
            )

        rev_status = str(rev.status.value if hasattr(rev.status, "value") else rev.status).lower()
        if rev_status in ("archived", "rejected", "expired"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Evidence revision lifecycle state '{rev_status}' is not valid",
            )

        rev_from = self._ensure_utc(rev.valid_from)
        rev_until = self._ensure_utc(rev.valid_until)
        if rev_from and rev_from > now:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evidence revision is not yet valid",
            )
        if rev_until and rev_until <= now:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evidence revision has expired",
            )

        # Digest check
        computed_digest = compute_evidence_revision_digest(
            evidence_id=rev.evidence_id,
            revision_number=rev.revision_number,
            title=rev.title,
            description=rev.description,
            classification=str(
                rev.classification.value
                if hasattr(rev.classification, "value")
                else rev.classification
            ),
            status_val=str(rev.status.value if hasattr(rev.status, "value") else rev.status),
            valid_from=rev.valid_from,
            valid_until=rev.valid_until,
            file_ids=rev.file_ids or [],
            control_ids=rev.control_ids or [],
        )
        if expected_revision_digest and computed_digest != expected_revision_digest:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evidence revision snapshot digest altered",
            )

        # File validation
        file_ids = rev.file_ids or []
        if len(file_ids) != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evidence revision must contain exactly one file",
            )

        file_id = UUID(str(file_ids[0]))
        stored_file = self.session.scalar(
            select(StoredFile).where(
                StoredFile.tenant_id == tenant_id,
                StoredFile.id == file_id,
            )
        )
        if stored_file is None or stored_file.status != StoredFileStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Attached file is not active in storage",
            )
        if stored_file.plaintext_size_bytes > 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Payload exceeds 1 MiB limit for customer demo evidence",
            )

        # Proof validation
        proof_dict: dict[str, Any] | None = None
        verified_at: datetime | None = None
        if rationale_encrypted and link_id:
            ctx = EncryptionContext(
                tenant_id=tenant_id,
                resource_type="customer_control_evidence_link",
                resource_id=str(link_id),
                field_name="rationale",
            )
            payload = (
                json.loads(rationale_encrypted)
                if isinstance(rationale_encrypted, str)
                else rationale_encrypted
            )
            raw = self.codec.decrypt_text(payload, ctx)
            try:
                proof_dict = json.loads(raw)
            except Exception:
                proof_dict = None

            if require_valid_proof:
                if not isinstance(proof_dict, dict):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Conflict: Evidence scan proof missing or corrupt",
                    )
                if proof_dict.get("file_id") != str(stored_file.id):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Conflict: Evidence scan proof file identity mismatch",
                    )
                if proof_dict.get("plaintext_sha256") != stored_file.plaintext_sha256:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Conflict: Evidence scan proof hash does not match current stored file",
                    )
                if proof_dict.get("scanner") != "strict_clamav":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Conflict: Evidence scan proof scanner type invalid",
                    )
            if isinstance(proof_dict, dict) and proof_dict.get("verified_at"):
                try:
                    verified_at = datetime.fromisoformat(proof_dict["verified_at"])
                except Exception:
                    verified_at = None

        return evidence_item, rev, stored_file, proof_dict, verified_at

    def get_owners(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> OwnerDirectoryResponse:
        """Return bounded directory of eligible same-tenant control owners."""
        self._admit_work_service_caller(principal, tenant_context, operation="read")
        authorize(principal, tenant_context, Capability.FRAMEWORK_READ)
        authorize(principal, tenant_context, Capability.EVIDENCE_READ)
        authorize(principal, tenant_context, Capability.MEMBERSHIP_READ)

        bounded_limit = max(1, min(100, limit))
        bounded_offset = max(0, offset)
        now = datetime.now(UTC)

        base_stmt = (
            select(User.id, User.display_name)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.tenant_id == tenant_context.tenant_id,
                Membership.status == MembershipStatus.ACTIVE,
                Membership.role.in_([Role.OWNER, Role.COMPLIANCE_MANAGER, Role.CONTROL_OWNER]),
                Membership.legal_entity_id.is_(None),
                Membership.business_unit_id.is_(None),
                Membership.is_workforce.is_(False),
                Membership.is_external_advisor.is_(False),
                (Membership.expires_at.is_(None) | (Membership.expires_at > now)),
                User.status == UserStatus.ACTIVE,
            )
            .order_by(User.display_name.asc(), User.id.asc())
        )

        total = len(self.session.execute(base_stmt).all())
        rows = self.session.execute(base_stmt.limit(bounded_limit).offset(bounded_offset)).all()

        items = [OwnerDirectoryItemDTO(user_id=r[0], display_name=r[1]) for r in rows]
        return OwnerDirectoryResponse(items=items, total=total)

    def get_control_work_list(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        adoption_id: UUID | None = None,
    ) -> WorkListResponse:
        """Return control work items for current or specified historical adoption."""
        self._admit_work_service_caller(principal, tenant_context, operation="read")
        authorize(principal, tenant_context, Capability.FRAMEWORK_READ)
        authorize(principal, tenant_context, Capability.EVIDENCE_READ)

        tenant_id = tenant_context.tenant_id
        ws = (
            self.session.query(CustomerDemoWorkspace)
            .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
            .first()
        )

        if ws is None or ws.selection_revision == 0:
            return WorkListResponse(
                tenant_id=tenant_id,
                adoption_id=None,
                selection_revision=0,
                answer_revision=0,
                is_current=False,
                is_stale=True,
                items=[],
                total=0,
            )

        current_adoption = (
            self.session.query(CustomerDemoAdoption)
            .filter(
                CustomerDemoAdoption.tenant_id == tenant_id,
                CustomerDemoAdoption.selection_revision == ws.selection_revision,
            )
            .first()
        )

        if current_adoption is None:
            return WorkListResponse(
                tenant_id=tenant_id,
                adoption_id=None,
                selection_revision=ws.selection_revision,
                answer_revision=ws.current_revision,
                is_current=False,
                is_stale=True,
                items=[],
                total=0,
            )

        target_adoption: CustomerDemoAdoption | None = None
        if adoption_id is not None:
            target_adoption = (
                self.session.query(CustomerDemoAdoption)
                .filter(
                    CustomerDemoAdoption.tenant_id == tenant_id,
                    CustomerDemoAdoption.id == adoption_id,
                )
                .first()
            )
            if target_adoption is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Requested customer demo adoption not found",
                )
        else:
            target_adoption = current_adoption

        is_current = target_adoption.id == current_adoption.id
        adopt_eval = (
            self.session.query(CustomerDemoEvaluation)
            .filter(
                CustomerDemoEvaluation.tenant_id == tenant_id,
                CustomerDemoEvaluation.id == target_adoption.evaluation_id,
            )
            .first()
        )
        answer_rev = adopt_eval.answer_revision if adopt_eval else 0
        is_stale = (not is_current) or (ws.current_revision > answer_rev)

        # Query work items
        work_rows = (
            self.session.query(CustomerControlWork)
            .filter(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.adoption_id == target_adoption.id,
            )
            .order_by(CustomerControlWork.control_version_id.asc())
            .all()
        )

        items = [
            self._build_work_dto(w, target_adoption, adopt_eval, is_current, is_stale)
            for w in work_rows
        ]
        return WorkListResponse(
            tenant_id=tenant_id,
            adoption_id=target_adoption.id,
            selection_revision=target_adoption.selection_revision,
            answer_revision=answer_rev,
            is_current=is_current,
            is_stale=is_stale,
            items=items,
            total=len(items),
        )

    def _build_work_dto(
        self,
        work: CustomerControlWork,
        adoption: CustomerDemoAdoption,
        evaluation: CustomerDemoEvaluation | None,
        is_current: bool,
        is_stale: bool,
    ) -> WorkDTO:
        """Construct WorkDTO including requirement results and link statuses."""
        bundle = get_bundle_by_version_id(adoption.pack_version_id)
        try:
            pack_ver_int = int(str(bundle.get("version", "1.0.0")).split(".")[0])
        except (ValueError, TypeError):
            pack_ver_int = 1

        # Find matching control in bundle
        ctrl_title = "Unknown Control"
        matching_req_results: list[RequirementEvaluationResultDTO] = []

        eval_results_map: dict[str, Any] = {}
        if evaluation and evaluation.results:
            for r in evaluation.results:
                eval_results_map[str(r["requirement_version_id"])] = r

        for req in bundle.get("requirements", []):
            if req.get("control_version_id") == str(work.control_version_id):
                ctrl_title = f"{req.get('control_identifier')}: {req.get('control_title')}"
                req_ver_id = req.get("version_id")
                if req_ver_id and str(req_ver_id) in eval_results_map:
                    matching_req_results.append(
                        RequirementEvaluationResultDTO(**eval_results_map[str(req_ver_id)])
                    )

        # Lookup owner name
        owner_name: str | None = None
        if work.owner_user_id is not None:
            user = self.session.query(User).filter(User.id == work.owner_user_id).first()
            if user:
                owner_name = user.display_name

        # Links
        links = self._get_links_for_work(work)

        return WorkDTO(
            id=work.id,
            adoption_id=work.adoption_id,
            control_id=work.control_id,
            control_version_id=work.control_version_id,
            title=ctrl_title,
            provenance=bundle.get("source_provenance_disclaimer", SOURCE_PROVENANCE_DISCLAIMER),
            pack_version=pack_ver_int,
            bundle_digest=adoption.bundle_digest,
            requirement_results=matching_req_results,
            owner_user_id=work.owner_user_id,
            owner_display_name=owner_name,
            due_date=work.due_date,
            version=work.version,
            is_current=is_current,
            is_stale=is_stale,
            links=links,
        )

    def _get_links_for_work(self, work: CustomerControlWork) -> list[LinkDTO]:
        """Fetch and decrypt links and evaluate validity and review state."""
        link_rows = (
            self.session.query(CustomerControlEvidenceLink)
            .filter(
                CustomerControlEvidenceLink.tenant_id == work.tenant_id,
                CustomerControlEvidenceLink.work_id == work.id,
            )
            .order_by(CustomerControlEvidenceLink.created_at.asc())
            .all()
        )

        dtos: list[LinkDTO] = []
        now = datetime.now(UTC)

        for link_row in link_rows:
            # Evidence current head and pinned revision
            evidence_head = self.session.scalar(
                select(EvidenceItem).where(
                    EvidenceItem.tenant_id == work.tenant_id,
                    EvidenceItem.id == link_row.evidence_id,
                )
            )
            rev = self.session.scalar(
                select(EvidenceRevision).where(
                    EvidenceRevision.tenant_id == work.tenant_id,
                    EvidenceRevision.evidence_id == link_row.evidence_id,
                    EvidenceRevision.revision_number == link_row.evidence_revision_number,
                )
            )

            validity: Literal[
                "MISSING",
                "AVAILABLE",
                "NOT_YET_VALID",
                "EXPIRED",
                "QUARANTINED",
                "UNAVAILABLE",
                "UNVERIFIED",
            ] = "AVAILABLE"
            filename: str = "evidence.bin"
            file_size: int = 0
            classification_val: str = "Restricted"
            file_ids: list[UUID] = []
            stored_file: StoredFile | None = None

            if evidence_head is None or rev is None:
                validity = "UNAVAILABLE"
            else:
                classification_val = str(
                    rev.classification.value
                    if hasattr(rev.classification, "value")
                    else rev.classification
                )
                file_ids = [UUID(str(fid)) for fid in (rev.file_ids or [])]

                head_status = str(
                    evidence_head.status.value
                    if hasattr(evidence_head.status, "value")
                    else evidence_head.status
                ).lower()
                rev_status = str(
                    rev.status.value if hasattr(rev.status, "value") else rev.status
                ).lower()

                # Check digest
                computed_digest = compute_evidence_revision_digest(
                    evidence_id=rev.evidence_id,
                    revision_number=rev.revision_number,
                    title=rev.title,
                    description=rev.description,
                    classification=classification_val,
                    status_val=str(
                        rev.status.value if hasattr(rev.status, "value") else rev.status
                    ),
                    valid_from=rev.valid_from,
                    valid_until=rev.valid_until,
                    file_ids=rev.file_ids or [],
                    control_ids=rev.control_ids or [],
                )
                head_from = self._ensure_utc(evidence_head.valid_from)
                head_until = self._ensure_utc(evidence_head.valid_until)
                rev_from = self._ensure_utc(rev.valid_from)
                rev_until = self._ensure_utc(rev.valid_until)

                if computed_digest != link_row.evidence_revision_digest:
                    validity = "UNAVAILABLE"
                elif head_status in ("archived", "rejected") or rev_status in (
                    "archived",
                    "rejected",
                ):
                    validity = "UNAVAILABLE"
                elif (head_from and head_from > now) or (rev_from and rev_from > now):
                    validity = "NOT_YET_VALID"
                elif (
                    (head_until and head_until <= now)
                    or (rev_until and rev_until <= now)
                    or head_status == "expired"
                    or rev_status == "expired"
                ):
                    validity = "EXPIRED"
                elif not file_ids:
                    validity = "MISSING"
                else:
                    stored_file = self.session.scalar(
                        select(StoredFile).where(
                            StoredFile.tenant_id == work.tenant_id,
                            StoredFile.id == file_ids[0],
                        )
                    )
                    if stored_file is None or stored_file.status == StoredFileStatus.DELETED:
                        validity = "MISSING"
                    elif stored_file.status == StoredFileStatus.QUARANTINED:
                        validity = "QUARANTINED"
                    elif stored_file.status != StoredFileStatus.ACTIVE:
                        validity = "UNAVAILABLE"
                    elif len(file_ids) != 1 or stored_file.plaintext_size_bytes > 1024 * 1024:
                        validity = "UNAVAILABLE"
                    else:
                        filename = stored_file.original_filename
                        file_size = stored_file.plaintext_size_bytes

            # Review status from latest review event
            latest_review_event = (
                self.session.query(CustomerControlWorkEvent)
                .filter(
                    CustomerControlWorkEvent.tenant_id == work.tenant_id,
                    CustomerControlWorkEvent.work_id == work.id,
                    CustomerControlWorkEvent.link_id == link_row.id,
                    CustomerControlWorkEvent.event_type == "EVIDENCE_REVIEWED",
                )
                .order_by(CustomerControlWorkEvent.work_revision.desc())
                .first()
            )

            review_status: Literal["PENDING", "ACCEPTED", "REJECTED"] = "PENDING"
            if latest_review_event is not None:
                if latest_review_event.decision == "ACCEPTED":
                    review_status = "ACCEPTED"
                elif latest_review_event.decision == "REJECTED":
                    review_status = "REJECTED"

            # Decrypt rationale and derive historic scan proof
            ctx = EncryptionContext(
                tenant_id=work.tenant_id,
                resource_type="customer_control_evidence_link",
                resource_id=str(link_row.id),
                field_name="rationale",
            )
            raw_decrypted = self.codec.decrypt_text(link_row.rationale_encrypted, ctx)
            rationale_text = raw_decrypted
            scan_status: Literal["SCANNED_AT_LINK", "UNVERIFIED"] = "UNVERIFIED"
            scan_verified_at: datetime | None = None
            proof_verified = False

            try:
                proof = json.loads(raw_decrypted)
                if isinstance(proof, dict):
                    rationale_text = proof.get("rationale", raw_decrypted)
                    if (
                        stored_file is not None
                        and proof.get("file_id") == str(stored_file.id)
                        and proof.get("plaintext_sha256") == stored_file.plaintext_sha256
                        and proof.get("scanner") == "strict_clamav"
                    ):
                        proof_verified = True
                        scan_status = "SCANNED_AT_LINK"
                        verified_str = proof.get("verified_at")
                        if verified_str:
                            try:
                                scan_verified_at = datetime.fromisoformat(verified_str)
                            except Exception:
                                scan_verified_at = None
            except Exception:
                rationale_text = raw_decrypted

            if validity == "AVAILABLE" and not proof_verified:
                validity = "UNVERIFIED"

            dtos.append(
                LinkDTO(
                    id=link_row.id,
                    evidence_id=link_row.evidence_id,
                    revision_number=link_row.evidence_revision_number,
                    digest=link_row.evidence_revision_digest,
                    file_ids=file_ids,
                    filename=filename,
                    file_size=file_size,
                    classification=classification_val,
                    validity=validity,
                    scan_status=scan_status,
                    scan_verified_at=scan_verified_at,
                    review=review_status,
                    rationale=rationale_text,
                    created_at=link_row.created_at,
                )
            )

        return dtos

    def _fetch_work_adopt_eval(
        self, tenant_id: UUID, work_id: UUID
    ) -> tuple[CustomerControlWork, CustomerDemoAdoption, CustomerDemoEvaluation]:
        work = (
            self.session.query(CustomerControlWork)
            .filter(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.id == work_id,
            )
            .first()
        )
        if work is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer control work item not found",
            )
        adopt = (
            self.session.query(CustomerDemoAdoption)
            .filter(
                CustomerDemoAdoption.tenant_id == tenant_id,
                CustomerDemoAdoption.id == work.adoption_id,
            )
            .first()
        )
        if adopt is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer demo adoption not found",
            )
        ev = (
            self.session.query(CustomerDemoEvaluation)
            .filter(
                CustomerDemoEvaluation.tenant_id == tenant_id,
                CustomerDemoEvaluation.id == adopt.evaluation_id,
            )
            .first()
        )
        if ev is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer demo evaluation not found",
            )
        return work, adopt, ev

    def initialize_work(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        body: InitializeWorkRequest,
        *,
        request_id: str,
    ) -> WorkListResponse:
        """Initialize control work items for an adopted customer demo pack."""
        self._admit_work_service_caller(principal, tenant_context, operation="mutate")
        authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)
        authorize(principal, tenant_context, Capability.CONTROL_STATUS_MANAGE)
        authorize(principal, tenant_context, Capability.EVIDENCE_MANAGE)

        tenant_id = tenant_context.tenant_id

        # Lock workspace
        ws = (
            self.session.query(CustomerDemoWorkspace)
            .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
            .with_for_update()
            .first()
        )
        if ws is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Customer demo workspace not found",
            )

        if ws.selection_revision != body.expected_selection_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Selection revision mismatch: expected {body.expected_selection_revision}, found {ws.selection_revision}",
            )

        # Target adoption
        adoption = (
            self.session.query(CustomerDemoAdoption)
            .filter(
                CustomerDemoAdoption.tenant_id == tenant_id,
                CustomerDemoAdoption.id == body.adoption_id,
            )
            .first()
        )
        if adoption is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Adoption not found",
            )

        if adoption.selection_revision != ws.selection_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Target adoption is not the current active selection",
            )

        # Adoption evaluation and answers
        evaluation = (
            self.session.query(CustomerDemoEvaluation)
            .filter(
                CustomerDemoEvaluation.tenant_id == tenant_id,
                CustomerDemoEvaluation.id == adoption.evaluation_id,
            )
            .first()
        )
        if evaluation is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evaluation referenced by adoption not found",
            )

        if evaluation.answer_revision != body.expected_answer_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Answer revision mismatch: expected {body.expected_answer_revision}, found {evaluation.answer_revision}",
            )

        if ws.current_revision != evaluation.answer_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Current answers have advanced past adopted evaluation",
            )

        expected_bundle_digest = get_bundle_digest(adoption.pack_version_id)
        if adoption.bundle_digest != expected_bundle_digest:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Adoption bundle digest mismatch",
            )

        # Extract controls mapped in the pack
        bundle = get_bundle_by_version_id(adoption.pack_version_id)
        controls_to_init: dict[UUID, tuple[UUID, UUID]] = {}
        for req in bundle.get("requirements", []):
            cid = UUID(str(req["control_id"]))
            cvid = UUID(str(req["control_version_id"]))
            controls_to_init[cvid] = (cid, cvid)

        # Canonical request payload for digest
        norm_req = {
            "adoption_id": str(body.adoption_id),
            "expected_answer_revision": body.expected_answer_revision,
            "expected_selection_revision": body.expected_selection_revision,
            "operation": "initialize",
            "operation_id": str(body.operation_id),
        }
        req_digest = hashlib.sha256(canonical_json(norm_req).encode("utf-8")).hexdigest()

        # Create work items in sorted control_version_id order
        for cvid in sorted(controls_to_init.keys()):
            cid, _ = controls_to_init[cvid]
            existing_work = (
                self.session.query(CustomerControlWork)
                .filter(
                    CustomerControlWork.tenant_id == tenant_id,
                    CustomerControlWork.adoption_id == adoption.id,
                    CustomerControlWork.control_version_id == cvid,
                )
                .first()
            )

            if existing_work is None:
                work = CustomerControlWork(
                    tenant_id=tenant_id,
                    id=uuid.uuid4(),
                    adoption_id=adoption.id,
                    control_id=cid,
                    control_version_id=cvid,
                    owner_user_id=None,
                    due_date=None,
                    version=1,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                self.session.add(work)
                self.session.flush()

                # Derived operation ID for each initialized control
                event_op_id = uuid.uuid5(body.operation_id, str(cvid))
                event_id = uuid.uuid4()
                evt_details = {"control_id": str(cid), "control_version_id": str(cvid)}
                ctx = EncryptionContext(
                    tenant_id=tenant_id,
                    resource_type="customer_control_work_event",
                    resource_id=str(event_id),
                    field_name="details",
                )
                enc_details = self.codec.encrypt_text(json.dumps(evt_details, sort_keys=True), ctx)

                event = CustomerControlWorkEvent(
                    tenant_id=tenant_id,
                    id=event_id,
                    work_id=work.id,
                    work_revision=1,
                    operation_id=event_op_id,
                    request_digest=req_digest,
                    event_type="INITIALIZED",
                    link_id=None,
                    decision=None,
                    details_encrypted=enc_details,
                    actor_id=principal.user_id,
                    created_at=datetime.now(UTC),
                )
                self.session.add(event)

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_demo.control_work.initialize",
            resource_type="customer_control_work",
            resource_id=str(adoption.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"adoption_id": str(adoption.id)},
        )
        self.session.flush()

        return self.get_control_work_list(principal, tenant_context, adoption_id=adoption.id)

    def patch_work(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        work_id: UUID,
        body: PatchWorkRequest,
        *,
        request_id: str,
    ) -> MutationReceipt:
        """Update owner assignment and due date of a control work item."""
        self._admit_work_service_caller(principal, tenant_context, operation="mutate")
        authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)
        authorize(principal, tenant_context, Capability.CONTROL_STATUS_MANAGE)
        authorize(principal, tenant_context, Capability.EVIDENCE_MANAGE)

        tenant_id = tenant_context.tenant_id

        # Canonical request digest
        norm_req = {
            "due_date": body.due_date.isoformat() if body.due_date else None,
            "expected_answer_revision": body.expected_answer_revision,
            "expected_selection_revision": body.expected_selection_revision,
            "expected_work_version": body.expected_work_version,
            "operation": "patch_work",
            "operation_id": str(body.operation_id),
            "owner_user_id": str(body.owner_user_id) if body.owner_user_id else None,
            "work_id": str(work_id),
        }
        req_digest = hashlib.sha256(canonical_json(norm_req).encode("utf-8")).hexdigest()

        # Replay detection before stale expected-version rejection
        existing_event = (
            self.session.query(CustomerControlWorkEvent)
            .filter(
                CustomerControlWorkEvent.tenant_id == tenant_id,
                CustomerControlWorkEvent.operation_id == body.operation_id,
            )
            .first()
        )
        if existing_event is not None:
            if existing_event.request_digest != req_digest:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflict: Operation ID already used with different payload or target",
                )
            # Replay!
            replay_work, replay_adopt, replay_ev = self._fetch_work_adopt_eval(tenant_id, work_id)
            dto = self._build_work_dto(
                replay_work, replay_adopt, replay_ev, is_current=True, is_stale=False
            )
            return MutationReceipt(
                operation_id=body.operation_id,
                event_id=existing_event.id,
                applied_work_version=existing_event.work_revision,
                replayed=True,
                current_work=dto,
            )

        # Lock workspace then selected work row
        ws = (
            self.session.query(CustomerDemoWorkspace)
            .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
            .with_for_update()
            .first()
        )
        if ws is None or ws.selection_revision != body.expected_selection_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Workspace selection revision mismatch",
            )

        work = (
            self.session.query(CustomerControlWork)
            .filter(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.id == work_id,
            )
            .with_for_update()
            .first()
        )
        if work is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Control work item not found",
            )

        adoption = (
            self.session.query(CustomerDemoAdoption)
            .filter(
                CustomerDemoAdoption.tenant_id == tenant_id,
                CustomerDemoAdoption.id == work.adoption_id,
            )
            .first()
        )
        if adoption is None or adoption.selection_revision != ws.selection_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Control work belongs to historical adoption",
            )

        evaluation = (
            self.session.query(CustomerDemoEvaluation)
            .filter(
                CustomerDemoEvaluation.tenant_id == tenant_id,
                CustomerDemoEvaluation.id == adoption.evaluation_id,
            )
            .first()
        )
        if evaluation is None or evaluation.answer_revision != body.expected_answer_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evaluation answer revision mismatch",
            )

        if ws.current_revision != evaluation.answer_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Current answers have advanced past adopted evaluation",
            )

        if work.version != body.expected_work_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Work version mismatch: expected {body.expected_work_version}, found {work.version}",
            )

        # Validate owner if assigned
        if body.owner_user_id is not None:
            self._verify_eligible_owner(tenant_id, body.owner_user_id)

        # Update work
        work.owner_user_id = body.owner_user_id
        work.due_date = body.due_date
        work.version += 1
        work.updated_at = datetime.now(UTC)

        # Add event
        event_id = uuid.uuid4()
        evt_details = {
            "due_date": body.due_date.isoformat() if body.due_date else None,
            "owner_user_id": str(body.owner_user_id) if body.owner_user_id else None,
        }
        ctx = EncryptionContext(
            tenant_id=tenant_id,
            resource_type="customer_control_work_event",
            resource_id=str(event_id),
            field_name="details",
        )
        enc_details = self.codec.encrypt_text(json.dumps(evt_details, sort_keys=True), ctx)

        event = CustomerControlWorkEvent(
            tenant_id=tenant_id,
            id=event_id,
            work_id=work.id,
            work_revision=work.version,
            operation_id=body.operation_id,
            request_digest=req_digest,
            event_type="OWNER_DUE_UPDATED",
            link_id=None,
            decision=None,
            details_encrypted=enc_details,
            actor_id=principal.user_id,
            created_at=datetime.now(UTC),
        )
        self.session.add(event)

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_demo.control_work.update",
            resource_type="customer_control_work",
            resource_id=str(work.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"control_id": str(work.control_id)},
        )
        self.session.flush()

        dto = self._build_work_dto(work, adoption, evaluation, is_current=True, is_stale=False)
        return MutationReceipt(
            operation_id=body.operation_id,
            event_id=event.id,
            applied_work_version=work.version,
            replayed=False,
            current_work=dto,
        )

    def create_evidence(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        work_id: UUID,
        body: CreateEvidenceRequest,
        *,
        request_id: str,
    ) -> MutationReceipt:
        """Create and pin new evidence from an uploaded same-tenant file."""
        self._admit_work_service_caller(principal, tenant_context, operation="mutate")
        authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)
        authorize(principal, tenant_context, Capability.CONTROL_STATUS_MANAGE)
        authorize(principal, tenant_context, Capability.EVIDENCE_MANAGE)
        authorize(principal, tenant_context, Capability.FILE_READ)

        tenant_id = tenant_context.tenant_id

        # Canonical request digest
        norm_req = {
            "expected_answer_revision": body.expected_answer_revision,
            "expected_selection_revision": body.expected_selection_revision,
            "expected_work_version": body.expected_work_version,
            "file_id": str(body.file_id),
            "operation": "create_evidence",
            "operation_id": str(body.operation_id),
            "rationale": body.rationale,
            "valid_until": format_canonical_datetime(body.valid_until)
            if body.valid_until
            else None,
            "work_id": str(work_id),
        }
        req_digest = hashlib.sha256(canonical_json(norm_req).encode("utf-8")).hexdigest()

        # Replay check
        existing_event = (
            self.session.query(CustomerControlWorkEvent)
            .filter(
                CustomerControlWorkEvent.tenant_id == tenant_id,
                CustomerControlWorkEvent.operation_id == body.operation_id,
            )
            .first()
        )
        if existing_event is not None:
            if existing_event.request_digest != req_digest:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflict: Operation ID already used with different payload or target",
                )
            replay_work, replay_adopt, replay_ev = self._fetch_work_adopt_eval(tenant_id, work_id)
            dto = self._build_work_dto(
                replay_work, replay_adopt, replay_ev, is_current=True, is_stale=False
            )
            return MutationReceipt(
                operation_id=body.operation_id,
                event_id=existing_event.id,
                applied_work_version=existing_event.work_revision,
                replayed=True,
                current_work=dto,
            )

        # Lock workspace then selected work row
        ws = (
            self.session.query(CustomerDemoWorkspace)
            .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
            .with_for_update()
            .first()
        )
        if ws is None or ws.selection_revision != body.expected_selection_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Workspace selection revision mismatch",
            )

        work = (
            self.session.query(CustomerControlWork)
            .filter(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.id == work_id,
            )
            .with_for_update()
            .first()
        )
        if work is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Control work item not found",
            )

        adoption = (
            self.session.query(CustomerDemoAdoption)
            .filter(
                CustomerDemoAdoption.tenant_id == tenant_id,
                CustomerDemoAdoption.id == work.adoption_id,
            )
            .first()
        )
        if adoption is None or adoption.selection_revision != ws.selection_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Control work belongs to historical adoption",
            )

        evaluation = (
            self.session.query(CustomerDemoEvaluation)
            .filter(
                CustomerDemoEvaluation.tenant_id == tenant_id,
                CustomerDemoEvaluation.id == adoption.evaluation_id,
            )
            .first()
        )
        if evaluation is None or evaluation.answer_revision != body.expected_answer_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evaluation answer revision mismatch",
            )

        if ws.current_revision != evaluation.answer_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Current answers have advanced past adopted evaluation",
            )

        if work.version != body.expected_work_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Work version mismatch: expected {body.expected_work_version}, found {work.version}",
            )

        # Validate stored file
        stored_file = self.session.scalar(
            select(StoredFile).where(
                StoredFile.tenant_id == tenant_id,
                StoredFile.id == body.file_id,
            )
        )
        if stored_file is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored file not found",
            )
        if stored_file.status != StoredFileStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Stored file status '{stored_file.status.value}' is not active",
            )
        if stored_file.plaintext_size_bytes > 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Payload exceeds 1 MiB limit for customer demo evidence",
            )

        # Download and decrypt bytes through StorageService
        storage_service = self._get_storage_service()
        _, file_bytes = storage_service.download_file(
            principal,
            tenant_context,
            file_id=body.file_id,
            request_id=request_id,
        )

        # Strict scanner verification
        self.scanner.scan(file_bytes, stored_file.original_filename)

        # Retrieve control identifier from bundle
        bundle = get_bundle_by_version_id(adoption.pack_version_id)
        ctrl_ident = "SYNTH-CTRL-001"
        for req in bundle.get("requirements", []):
            if req.get("control_version_id") == str(work.control_version_id):
                ctrl_ident = req.get("control_identifier", ctrl_ident)
                break

        # Evidence creation and revision snapshotting
        comp_service = ComplianceService(self.session, codec=self.codec)
        evidence_owner = work.owner_user_id or principal.user_id

        evidence = comp_service.create_evidence(
            principal,
            tenant_context,
            title=ctrl_ident,
            description=f"Synthetic evidence for control {ctrl_ident}",
            classification=DataClassification.RESTRICTED,
            owner_user_id=evidence_owner,
            valid_until=body.valid_until,
        )

        comp_service.attach_file_to_evidence(
            principal,
            tenant_context,
            evidence_id=evidence.id,
            file_id=body.file_id,
        )

        self.session.refresh(evidence)
        # update_evidence increments evidence.version to 2 and snapshots file_links
        comp_service.update_evidence(
            principal,
            tenant_context,
            evidence.id,
            expected_version=evidence.version,
        )

        # Fetch resulting pinned revision (revision 2)
        rev = self.session.scalar(
            select(EvidenceRevision).where(
                EvidenceRevision.tenant_id == tenant_id,
                EvidenceRevision.evidence_id == evidence.id,
                EvidenceRevision.revision_number == 2,
            )
        )
        if rev is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record post-attachment evidence revision",
            )

        rev_digest = compute_evidence_revision_digest(
            evidence_id=rev.evidence_id,
            revision_number=rev.revision_number,
            title=rev.title,
            description=rev.description,
            classification=str(
                rev.classification.value
                if hasattr(rev.classification, "value")
                else rev.classification
            ),
            status_val=str(rev.status.value if hasattr(rev.status, "value") else rev.status),
            valid_from=rev.valid_from,
            valid_until=rev.valid_until,
            file_ids=rev.file_ids or [],
            control_ids=rev.control_ids or [],
        )

        # Create link
        link_id = uuid.uuid4()
        verified_time = datetime.now(UTC)
        proof = {
            "file_id": str(body.file_id),
            "plaintext_sha256": hashlib.sha256(file_bytes).hexdigest(),
            "rationale": body.rationale,
            "scanner": "strict_clamav",
            "verified_at": verified_time.isoformat(),
        }
        ctx_link = EncryptionContext(
            tenant_id=tenant_id,
            resource_type="customer_control_evidence_link",
            resource_id=str(link_id),
            field_name="rationale",
        )
        enc_rationale = self.codec.encrypt_text(json.dumps(proof, sort_keys=True), ctx_link)

        link = CustomerControlEvidenceLink(
            tenant_id=tenant_id,
            id=link_id,
            work_id=work.id,
            evidence_id=evidence.id,
            evidence_revision_number=rev.revision_number,
            evidence_revision_digest=rev_digest,
            rationale_encrypted=enc_rationale,
            actor_id=principal.user_id,
            created_at=verified_time,
        )
        self.session.add(link)

        # Update work
        work.version += 1
        work.updated_at = verified_time

        # Create event
        event_id = uuid.uuid4()
        evt_details = {
            "evidence_id": str(evidence.id),
            "link_id": str(link.id),
            "revision_digest": rev_digest,
            "revision_number": rev.revision_number,
        }
        ctx_evt = EncryptionContext(
            tenant_id=tenant_id,
            resource_type="customer_control_work_event",
            resource_id=str(event_id),
            field_name="details",
        )
        enc_details = self.codec.encrypt_text(json.dumps(evt_details, sort_keys=True), ctx_evt)

        event = CustomerControlWorkEvent(
            tenant_id=tenant_id,
            id=event_id,
            work_id=work.id,
            work_revision=work.version,
            operation_id=body.operation_id,
            request_digest=req_digest,
            event_type="EVIDENCE_LINKED",
            link_id=link.id,
            decision=None,
            details_encrypted=enc_details,
            actor_id=principal.user_id,
            created_at=verified_time,
        )
        self.session.add(event)

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_demo.control_work.evidence_pin",
            resource_type="customer_control_work",
            resource_id=str(work.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "control_id": str(work.control_id),
                "evidence_id": str(evidence.id),
                "file_id": str(body.file_id),
                "link_id": str(link.id),
            },
        )
        self.session.flush()

        dto = self._build_work_dto(work, adoption, evaluation, is_current=True, is_stale=False)
        return MutationReceipt(
            operation_id=body.operation_id,
            event_id=event.id,
            applied_work_version=work.version,
            replayed=False,
            current_work=dto,
        )

    def create_link(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        work_id: UUID,
        body: CreateLinkRequest,
        *,
        request_id: str,
    ) -> MutationReceipt:
        """Deliberately reuse an existing same-tenant evidence revision snapshot."""
        self._admit_work_service_caller(principal, tenant_context, operation="mutate")
        authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)
        authorize(principal, tenant_context, Capability.CONTROL_STATUS_MANAGE)
        authorize(principal, tenant_context, Capability.EVIDENCE_MANAGE)
        authorize(principal, tenant_context, Capability.FILE_READ)

        tenant_id = tenant_context.tenant_id

        # Canonical request digest
        norm_req = {
            "evidence_id": str(body.evidence_id),
            "evidence_revision_digest": body.evidence_revision_digest,
            "evidence_revision_number": body.evidence_revision_number,
            "expected_answer_revision": body.expected_answer_revision,
            "expected_selection_revision": body.expected_selection_revision,
            "expected_work_version": body.expected_work_version,
            "operation": "create_link",
            "operation_id": str(body.operation_id),
            "rationale": body.rationale,
            "work_id": str(work_id),
        }
        req_digest = hashlib.sha256(canonical_json(norm_req).encode("utf-8")).hexdigest()

        # Replay check
        existing_event = (
            self.session.query(CustomerControlWorkEvent)
            .filter(
                CustomerControlWorkEvent.tenant_id == tenant_id,
                CustomerControlWorkEvent.operation_id == body.operation_id,
            )
            .first()
        )
        if existing_event is not None:
            if existing_event.request_digest != req_digest:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflict: Operation ID already used with different payload or target",
                )
            replay_work, replay_adopt, replay_ev = self._fetch_work_adopt_eval(tenant_id, work_id)
            dto = self._build_work_dto(
                replay_work, replay_adopt, replay_ev, is_current=True, is_stale=False
            )
            return MutationReceipt(
                operation_id=body.operation_id,
                event_id=existing_event.id,
                applied_work_version=existing_event.work_revision,
                replayed=True,
                current_work=dto,
            )

        # Lock workspace then selected work row then evidence item
        ws = (
            self.session.query(CustomerDemoWorkspace)
            .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
            .with_for_update()
            .first()
        )
        if ws is None or ws.selection_revision != body.expected_selection_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Workspace selection revision mismatch",
            )

        work = (
            self.session.query(CustomerControlWork)
            .filter(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.id == work_id,
            )
            .with_for_update()
            .first()
        )
        if work is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Control work item not found",
            )

        adoption = (
            self.session.query(CustomerDemoAdoption)
            .filter(
                CustomerDemoAdoption.tenant_id == tenant_id,
                CustomerDemoAdoption.id == work.adoption_id,
            )
            .first()
        )
        if adoption is None or adoption.selection_revision != ws.selection_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Control work belongs to historical adoption",
            )

        evaluation = (
            self.session.query(CustomerDemoEvaluation)
            .filter(
                CustomerDemoEvaluation.tenant_id == tenant_id,
                CustomerDemoEvaluation.id == adoption.evaluation_id,
            )
            .first()
        )
        if evaluation is None or evaluation.answer_revision != body.expected_answer_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evaluation answer revision mismatch",
            )

        if ws.current_revision != evaluation.answer_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Current answers have advanced past adopted evaluation",
            )

        if work.version != body.expected_work_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Work version mismatch: expected {body.expected_work_version}, found {work.version}",
            )

        # Lock and validate evidence head, revision, and stored file
        evidence_head, rev, stored_file, _, _ = self._validate_evidence_lifecycle_and_proof(
            tenant_id=tenant_id,
            evidence_id=body.evidence_id,
            revision_number=body.evidence_revision_number,
            expected_revision_digest=body.evidence_revision_digest,
            require_valid_proof=False,
        )
        file_id = stored_file.id
        rev_digest = body.evidence_revision_digest

        # Download and strict scan
        storage_service = self._get_storage_service()
        _, file_bytes = storage_service.download_file(
            principal,
            tenant_context,
            file_id=file_id,
            request_id=request_id,
        )
        self.scanner.scan(file_bytes, stored_file.original_filename)

        # Check duplicate natural link for this work
        existing_link = self.session.scalar(
            select(CustomerControlEvidenceLink).where(
                CustomerControlEvidenceLink.tenant_id == tenant_id,
                CustomerControlEvidenceLink.work_id == work.id,
                CustomerControlEvidenceLink.evidence_id == body.evidence_id,
                CustomerControlEvidenceLink.evidence_revision_number
                == body.evidence_revision_number,
            )
        )
        if existing_link is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evidence revision already linked to this control work",
            )

        # Create link
        link_id = uuid.uuid4()
        verified_time = datetime.now(UTC)
        proof = {
            "file_id": str(file_id),
            "plaintext_sha256": hashlib.sha256(file_bytes).hexdigest(),
            "rationale": body.rationale,
            "scanner": "strict_clamav",
            "verified_at": verified_time.isoformat(),
        }
        ctx_link = EncryptionContext(
            tenant_id=tenant_id,
            resource_type="customer_control_evidence_link",
            resource_id=str(link_id),
            field_name="rationale",
        )
        enc_rationale = self.codec.encrypt_text(json.dumps(proof, sort_keys=True), ctx_link)

        link = CustomerControlEvidenceLink(
            tenant_id=tenant_id,
            id=link_id,
            work_id=work.id,
            evidence_id=body.evidence_id,
            evidence_revision_number=body.evidence_revision_number,
            evidence_revision_digest=rev_digest,
            rationale_encrypted=enc_rationale,
            actor_id=principal.user_id,
            created_at=verified_time,
        )
        self.session.add(link)

        # Update work
        work.version += 1
        work.updated_at = verified_time

        # Create event
        event_id = uuid.uuid4()
        evt_details = {
            "evidence_id": str(body.evidence_id),
            "link_id": str(link.id),
            "revision_digest": rev_digest,
            "revision_number": body.evidence_revision_number,
        }
        ctx_evt = EncryptionContext(
            tenant_id=tenant_id,
            resource_type="customer_control_work_event",
            resource_id=str(event_id),
            field_name="details",
        )
        enc_details = self.codec.encrypt_text(json.dumps(evt_details, sort_keys=True), ctx_evt)

        event = CustomerControlWorkEvent(
            tenant_id=tenant_id,
            id=event_id,
            work_id=work.id,
            work_revision=work.version,
            operation_id=body.operation_id,
            request_digest=req_digest,
            event_type="EVIDENCE_LINKED",
            link_id=link.id,
            decision=None,
            details_encrypted=enc_details,
            actor_id=principal.user_id,
            created_at=verified_time,
        )
        self.session.add(event)

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_demo.control_work.link_reuse",
            resource_type="customer_control_work",
            resource_id=str(work.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "control_id": str(work.control_id),
                "evidence_id": str(body.evidence_id),
                "link_id": str(link.id),
            },
        )
        self.session.flush()

        dto = self._build_work_dto(work, adoption, evaluation, is_current=True, is_stale=False)
        return MutationReceipt(
            operation_id=body.operation_id,
            event_id=event.id,
            applied_work_version=work.version,
            replayed=False,
            current_work=dto,
        )

    def create_review(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        work_id: UUID,
        link_id: UUID,
        body: CreateReviewRequest,
        *,
        request_id: str,
    ) -> MutationReceipt:
        """Record an evidence suitability review decision (ACCEPTED or REJECTED)."""
        self._admit_work_service_caller(principal, tenant_context, operation="mutate")
        authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)
        authorize(principal, tenant_context, Capability.CONTROL_STATUS_MANAGE)
        authorize(principal, tenant_context, Capability.EVIDENCE_MANAGE)
        if body.decision == "ACCEPTED":
            authorize(principal, tenant_context, Capability.FILE_READ)

        tenant_id = tenant_context.tenant_id

        # Canonical request digest
        norm_req = {
            "decision": body.decision,
            "expected_answer_revision": body.expected_answer_revision,
            "expected_selection_revision": body.expected_selection_revision,
            "expected_work_version": body.expected_work_version,
            "link_id": str(link_id),
            "operation": "create_review",
            "operation_id": str(body.operation_id),
            "rationale": body.rationale,
            "work_id": str(work_id),
        }
        req_digest = hashlib.sha256(canonical_json(norm_req).encode("utf-8")).hexdigest()

        # Replay check
        existing_event = (
            self.session.query(CustomerControlWorkEvent)
            .filter(
                CustomerControlWorkEvent.tenant_id == tenant_id,
                CustomerControlWorkEvent.operation_id == body.operation_id,
            )
            .first()
        )
        if existing_event is not None:
            if existing_event.request_digest != req_digest:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflict: Operation ID already used with different payload or target",
                )
            replay_work, replay_adopt, replay_ev = self._fetch_work_adopt_eval(tenant_id, work_id)
            dto = self._build_work_dto(
                replay_work, replay_adopt, replay_ev, is_current=True, is_stale=False
            )
            return MutationReceipt(
                operation_id=body.operation_id,
                event_id=existing_event.id,
                applied_work_version=existing_event.work_revision,
                replayed=True,
                current_work=dto,
            )

        # Lock workspace then selected work row
        ws = (
            self.session.query(CustomerDemoWorkspace)
            .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
            .with_for_update()
            .first()
        )
        if ws is None or ws.selection_revision != body.expected_selection_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Workspace selection revision mismatch",
            )

        work = (
            self.session.query(CustomerControlWork)
            .filter(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.id == work_id,
            )
            .with_for_update()
            .first()
        )
        if work is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Control work item not found",
            )

        adoption = (
            self.session.query(CustomerDemoAdoption)
            .filter(
                CustomerDemoAdoption.tenant_id == tenant_id,
                CustomerDemoAdoption.id == work.adoption_id,
            )
            .first()
        )
        if adoption is None or adoption.selection_revision != ws.selection_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Control work belongs to historical adoption",
            )

        evaluation = (
            self.session.query(CustomerDemoEvaluation)
            .filter(
                CustomerDemoEvaluation.tenant_id == tenant_id,
                CustomerDemoEvaluation.id == adoption.evaluation_id,
            )
            .first()
        )
        if evaluation is None or evaluation.answer_revision != body.expected_answer_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evaluation answer revision mismatch",
            )

        if ws.current_revision != evaluation.answer_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Current answers have advanced past adopted evaluation",
            )

        if work.version != body.expected_work_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Work version mismatch: expected {body.expected_work_version}, found {work.version}",
            )

        # Validate link exists and belongs to this work item
        link = self.session.scalar(
            select(CustomerControlEvidenceLink).where(
                CustomerControlEvidenceLink.tenant_id == tenant_id,
                CustomerControlEvidenceLink.id == link_id,
                CustomerControlEvidenceLink.work_id == work.id,
            )
        )
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence link not found for this control work item",
            )

        # If ACCEPTED, enforce valid snapshot, active file, and strict scan
        scan_proof: dict[str, Any] | None = None
        now = datetime.now(UTC)

        if body.decision == "ACCEPTED":
            # Dual lifecycle and proof validation for ACCEPTED review
            _, rev, stored_file, proof_dict, _ = self._validate_evidence_lifecycle_and_proof(
                tenant_id=tenant_id,
                evidence_id=link.evidence_id,
                revision_number=link.evidence_revision_number,
                expected_revision_digest=link.evidence_revision_digest,
                link_id=link.id,
                rationale_encrypted=link.rationale_encrypted,
                require_valid_proof=True,
            )
            file_id = stored_file.id

            storage_service = self._get_storage_service()
            _, file_bytes = storage_service.download_file(
                principal,
                tenant_context,
                file_id=file_id,
                request_id=request_id,
            )
            self.scanner.scan(file_bytes, stored_file.original_filename)

            scan_proof = {
                "file_id": str(file_id),
                "plaintext_sha256": hashlib.sha256(file_bytes).hexdigest(),
                "scanner": "strict_clamav",
                "verified_at": now.isoformat(),
            }

        # Update work
        work.version += 1
        work.updated_at = now

        # Create event
        event_id = uuid.uuid4()
        evt_details = {
            "decision": body.decision,
            "link_id": str(link.id),
            "rationale": body.rationale,
            "scan_proof": scan_proof,
        }
        ctx_evt = EncryptionContext(
            tenant_id=tenant_id,
            resource_type="customer_control_work_event",
            resource_id=str(event_id),
            field_name="details",
        )
        enc_details = self.codec.encrypt_text(json.dumps(evt_details, sort_keys=True), ctx_evt)

        event = CustomerControlWorkEvent(
            tenant_id=tenant_id,
            id=event_id,
            work_id=work.id,
            work_revision=work.version,
            operation_id=body.operation_id,
            request_digest=req_digest,
            event_type="EVIDENCE_REVIEWED",
            link_id=link.id,
            decision=body.decision,
            details_encrypted=enc_details,
            actor_id=principal.user_id,
            created_at=now,
        )
        self.session.add(event)

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_demo.control_work.review",
            resource_type="customer_control_work",
            resource_id=str(work.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "control_id": str(work.control_id),
                "link_id": str(link.id),
            },
        )
        self.session.flush()

        dto = self._build_work_dto(work, adoption, evaluation, is_current=True, is_stale=False)
        return MutationReceipt(
            operation_id=body.operation_id,
            event_id=event.id,
            applied_work_version=work.version,
            replayed=False,
            current_work=dto,
        )

    def get_history(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        work_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> WorkHistoryResponse:
        """Return revision-ordered event history for a control work item."""
        self._admit_work_service_caller(principal, tenant_context, operation="read")
        authorize(principal, tenant_context, Capability.FRAMEWORK_READ)
        authorize(principal, tenant_context, Capability.EVIDENCE_READ)

        tenant_id = tenant_context.tenant_id
        work = (
            self.session.query(CustomerControlWork)
            .filter(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.id == work_id,
            )
            .first()
        )
        if work is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Control work item not found",
            )

        bounded_limit = max(1, min(100, limit))
        bounded_offset = max(0, offset)

        stmt = (
            select(CustomerControlWorkEvent)
            .where(
                CustomerControlWorkEvent.tenant_id == tenant_id,
                CustomerControlWorkEvent.work_id == work.id,
            )
            .order_by(CustomerControlWorkEvent.work_revision.asc())
        )

        total = len(self.session.scalars(stmt).all())
        events = self.session.scalars(stmt.limit(bounded_limit).offset(bounded_offset)).all()

        items: list[EventDTO] = []
        for e in events:
            ctx = EncryptionContext(
                tenant_id=tenant_id,
                resource_type="customer_control_work_event",
                resource_id=str(e.id),
                field_name="details",
            )
            dec = self.codec.decrypt_text(e.details_encrypted, ctx)
            try:
                details_dict = json.loads(dec)
            except Exception:
                details_dict = {"raw": dec}

            items.append(
                EventDTO(
                    revision=e.work_revision,
                    type=e.event_type,
                    actor_id=e.actor_id,
                    time=e.created_at,
                    link_id=e.link_id,
                    decision=e.decision,
                    details=details_dict,
                )
            )

        return WorkHistoryResponse(items=items, total=total)

    def download_pinned_file(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        work_id: UUID,
        link_id: UUID,
        file_id: UUID,
        *,
        request_id: str,
    ) -> tuple[StoredFile, bytes]:
        """Validate pinned link and download bytes using StorageService and strict scanner."""
        self._admit_work_service_caller(principal, tenant_context, operation="read")
        authorize(principal, tenant_context, Capability.FRAMEWORK_READ)
        authorize(principal, tenant_context, Capability.EVIDENCE_READ)
        authorize(principal, tenant_context, Capability.FILE_READ)

        tenant_id = tenant_context.tenant_id
        work = (
            self.session.query(CustomerControlWork)
            .filter(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.id == work_id,
            )
            .first()
        )
        if work is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Control work item not found",
            )

        link = self.session.scalar(
            select(CustomerControlEvidenceLink).where(
                CustomerControlEvidenceLink.tenant_id == tenant_id,
                CustomerControlEvidenceLink.id == link_id,
                CustomerControlEvidenceLink.work_id == work.id,
            )
        )
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence link not found",
            )

        # Dual lifecycle and proof validation before returning bytes
        _, rev, stored_file, _, _ = self._validate_evidence_lifecycle_and_proof(
            tenant_id=tenant_id,
            evidence_id=link.evidence_id,
            revision_number=link.evidence_revision_number,
            expected_revision_digest=link.evidence_revision_digest,
            link_id=link.id,
            rationale_encrypted=link.rationale_encrypted,
            require_valid_proof=True,
        )

        if str(file_id) != str(stored_file.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File is not part of this pinned evidence revision",
            )

        storage_service = self._get_storage_service()
        stored_file, file_bytes = storage_service.download_file(
            principal,
            tenant_context,
            file_id=file_id,
            request_id=request_id,
        )

        # Strict scanner verification before returning bytes
        self.scanner.scan(file_bytes, stored_file.original_filename)

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_demo.control_work.download",
            resource_type="customer_control_work",
            resource_id=str(work.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "file_id": str(file_id),
                "link_id": str(link.id),
            },
        )
        return stored_file, file_bytes

    def authorize_assessment_access(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        operation: Literal["read", "mutate"] = "read",
    ) -> None:
        """Public read/validation facade delegating to caller admission."""
        self._admit_work_service_caller(principal, tenant_context, operation=operation)
        return None

    def get_validated_assessment_link(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        work_id: UUID,
        link_id: UUID,
    ) -> ValidatedAssessmentLink:
        """Public read/validation facade validating evidence link lifecycle, review status, and proof."""
        self._admit_work_service_caller(principal, tenant_context, operation="read")
        tenant_id = tenant_context.tenant_id

        # 1. Tenant-scoped work and link lookup
        work = self.session.scalar(
            select(CustomerControlWork).where(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.id == work_id,
            )
        )
        if work is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Control work item not found",
            )

        link = self.session.scalar(
            select(CustomerControlEvidenceLink).where(
                CustomerControlEvidenceLink.tenant_id == tenant_id,
                CustomerControlEvidenceLink.work_id == work_id,
                CustomerControlEvidenceLink.id == link_id,
            )
        )
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence link not found",
            )

        # 2. Require latest contextual review ACCEPTED
        latest_review = self.session.scalar(
            select(CustomerControlWorkEvent)
            .where(
                CustomerControlWorkEvent.tenant_id == tenant_id,
                CustomerControlWorkEvent.work_id == work_id,
                CustomerControlWorkEvent.link_id == link_id,
                CustomerControlWorkEvent.event_type == "EVIDENCE_REVIEWED",
            )
            .order_by(CustomerControlWorkEvent.work_revision.desc())
        )
        if latest_review is None or latest_review.decision != "ACCEPTED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evidence link does not have an ACCEPTED contextual review",
            )

        # 3. Validate evidence lifecycle and proof
        _item, _rev, stored_file, _proof_dict, scan_verified_at = (
            self._validate_evidence_lifecycle_and_proof(
                tenant_id=tenant_id,
                evidence_id=link.evidence_id,
                revision_number=link.evidence_revision_number,
                expected_revision_digest=link.evidence_revision_digest,
                link_id=link.id,
                require_valid_proof=True,
            )
        )

        return ValidatedAssessmentLink(
            link_id=link.id,
            work_id=link.work_id,
            evidence_id=link.evidence_id,
            revision_number=link.evidence_revision_number,
            revision_digest=link.evidence_revision_digest,
            latest_review_event_id=latest_review.id,
            file_id=stored_file.id,
            file_hash=stored_file.plaintext_sha256,
            scan_verified_at=scan_verified_at,
        )
