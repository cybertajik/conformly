"""Customer Assessment Service for MVP-C.

Implements version-pinned human assessment, explicit findings,
remediation updates, human retest, and truthful readiness summaries.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize
from conformly.authz.roles import Capability
from conformly.catalog_v2.digest import canonical_json
from conformly.compliance.models import EvidenceItem
from conformly.crypto.fields import get_encrypted_field_codec
from conformly.crypto.types import EncryptionContext
from conformly.customer_demo.assessment_models import (
    CustomerAssessmentEvent,
    CustomerAssessmentFinding,
    CustomerAssessmentHead,
)
from conformly.customer_demo.assessment_procedures import (
    get_procedure_for_control_version,
)
from conformly.customer_demo.assessment_schemas import (
    AssessmentCreateRequest,
    AssessmentHistoryItemDto,
    AssessmentHistoryResponse,
    AssessmentOperationReceiptDto,
    AssessmentWorkItemDto,
    AssessmentWorkListResponse,
    FindingDto,
    FindingPatchRequest,
    LatestAssessmentDto,
    PinnedEvidenceDto,
    ProcedureCriterionDto,
    ProcedureDto,
    ReadinessSummaryDto,
    RetestCreateRequest,
)
from conformly.customer_demo.evaluator import (
    compute_answers_digest,
    compute_evaluation_digest,
    evaluate_bundle,
    normalize_answers,
)
from conformly.customer_demo.fixture import (
    EVALUATOR_VERSION,
    get_bundle_by_version_id,
    get_bundle_digest,
)
from conformly.customer_demo.models import (
    CustomerDemoAdoption,
    CustomerDemoAnswers,
    CustomerDemoEvaluation,
    CustomerDemoWorkspace,
)
from conformly.customer_demo.policy import (
    CustomerDemoAdmissionError,
    CustomerDemoDatabaseAdmissionError,
)
from conformly.customer_demo.work_models import (
    CustomerControlEvidenceLink,
    CustomerControlWork,
)
from conformly.customer_demo.work_service import (
    CustomerControlWorkService,
    ValidatedAssessmentLink,
)
from conformly.entitlements.models import TenantEntitlement
from conformly.identity.models import User


class CustomerAssessmentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.codec = get_encrypted_field_codec()
        self.work_service = CustomerControlWorkService(session)

    def _ensure_utc(self, dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    def _verify_database_connection(self) -> None:
        bind = self.session.get_bind()
        if bind is None or bind.dialect.name != "postgresql":
            try:
                self.session.execute(text("SELECT 1"))
            except Exception as exc:
                raise CustomerDemoDatabaseAdmissionError("Database connection unavailable") from exc
            return

        row = self.session.execute(
            text(
                "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )
        ).first()
        if row is None:
            raise CustomerDemoDatabaseAdmissionError("Unable to verify PostgreSQL runtime identity")

        user_name, is_super, is_bypass = row[0], row[1], row[2]
        if is_super or is_bypass or user_name != "conformly_app":
            raise CustomerDemoDatabaseAdmissionError(
                f"Disallowed PostgreSQL runtime identity: {user_name} (superuser={is_super}, bypassrls={is_bypass})"
            )

        # Table ownership check: current_user must not own customer assessment tables
        owned_tables = (
            self.session.execute(
                text(
                    """
                SELECT c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_roles r ON r.oid = c.relowner
                WHERE c.relname IN (
                    'customer_assessment_heads',
                    'customer_assessment_events',
                    'customer_assessment_findings'
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
                f"PostgreSQL user '{user_name}' illegally owns customer assessment tables: {list(owned_tables)}"
            )

    def _verify_module_entitlements(self, tenant_id: UUID) -> None:
        ent = self.session.scalar(
            select(TenantEntitlement).where(TenantEntitlement.tenant_id == tenant_id)
        )
        if ent is None:
            raise CustomerDemoAdmissionError(
                "Tenant entitlement missing", status_code=status.HTTP_403_FORBIDDEN
            )
        enabled = ent.enabled_modules or []
        if "preaudit" not in enabled:
            raise CustomerDemoAdmissionError(
                "Preaudit module not entitled for tenant", status_code=status.HTTP_403_FORBIDDEN
            )
        if "findings" not in enabled:
            raise CustomerDemoAdmissionError(
                "Findings module not entitled for tenant", status_code=status.HTTP_403_FORBIDDEN
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

    def _get_current_workspace_and_adoption(
        self, tenant_id: UUID, for_update: bool = False
    ) -> tuple[CustomerDemoWorkspace | None, CustomerDemoAdoption | None]:
        stmt = select(CustomerDemoWorkspace).where(CustomerDemoWorkspace.tenant_id == tenant_id)
        if for_update:
            stmt = stmt.with_for_update()
        ws = self.session.scalar(stmt)
        if ws is None or ws.selection_revision == 0:
            return ws, None
        adoption = self.session.scalar(
            select(CustomerDemoAdoption).where(
                CustomerDemoAdoption.tenant_id == tenant_id,
                CustomerDemoAdoption.selection_revision == ws.selection_revision,
            )
        )
        return ws, adoption

    def _admit_assessment_caller(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        operation: Literal["read", "mutate"],
    ) -> None:
        self.work_service.authorize_assessment_access(
            principal, tenant_context, operation=operation
        )
        self._verify_database_connection()
        self._verify_module_entitlements(tenant_context.tenant_id)
        if operation == "read":
            authorize(principal, tenant_context, Capability.PREAUDIT_READ)
            authorize(principal, tenant_context, Capability.FINDING_READ)
        else:
            authorize(principal, tenant_context, Capability.PREAUDIT_MANAGE)
            authorize(principal, tenant_context, Capability.PREAUDIT_REVIEW)
            authorize(principal, tenant_context, Capability.FINDING_MANAGE)

    def _get_or_create_head(self, tenant_id: UUID, work_id: UUID) -> CustomerAssessmentHead:
        head = self.session.scalar(
            select(CustomerAssessmentHead)
            .where(
                CustomerAssessmentHead.tenant_id == tenant_id,
                CustomerAssessmentHead.work_id == work_id,
            )
            .with_for_update()
        )
        if head is None:
            now = datetime.now(UTC)
            head = CustomerAssessmentHead(
                tenant_id=tenant_id,
                work_id=work_id,
                current_revision=0,
                created_at=now,
                updated_at=now,
            )
            try:
                with self.session.begin_nested():
                    self.session.add(head)
                    self.session.flush()
            except IntegrityError:
                head = self.session.scalar(
                    select(CustomerAssessmentHead)
                    .where(
                        CustomerAssessmentHead.tenant_id == tenant_id,
                        CustomerAssessmentHead.work_id == work_id,
                    )
                    .with_for_update()
                )
                if head is None:
                    raise
        return head

    def _validate_adoption_and_snapshots(
        self,
        tenant_id: UUID,
        ws: CustomerDemoWorkspace,
        work: CustomerControlWork,
    ) -> tuple[CustomerDemoAdoption, CustomerDemoEvaluation, CustomerDemoAnswers]:
        _, current_adoption = self._get_current_workspace_and_adoption(tenant_id)
        if current_adoption is None or work.adoption_id != current_adoption.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Control work does not belong to current active adoption",
            )

        # 1. Verify bundle digest
        expected_bundle_digest = get_bundle_digest(current_adoption.pack_version_id)
        if current_adoption.bundle_digest != expected_bundle_digest:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Adoption bundle digest mismatch with current pack version",
            )

        # 2. Verify work control_version association with pack bundle
        bundle = get_bundle_by_version_id(current_adoption.pack_version_id)
        valid_control_versions = {
            UUID(str(req["control_version_id"])) for req in bundle.get("requirements", [])
        }
        if work.control_version_id not in valid_control_versions:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Control work item version not associated with current adopted bundle",
            )

        # 3. Retrieve and verify saved answer record and recompute digest
        answer = self.session.scalar(
            select(CustomerDemoAnswers).where(
                CustomerDemoAnswers.tenant_id == tenant_id,
                CustomerDemoAnswers.revision == ws.current_revision,
            )
        )
        if answer is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Saved answers for current workspace revision not found",
            )

        recomp_answers_digest = compute_answers_digest(answer.company_code, answer.answers)
        if answer.content_digest != recomp_answers_digest:
            norm_a = normalize_answers(answer.answers)
            norm_digest = compute_answers_digest(answer.company_code, norm_a)
            if answer.content_digest == norm_digest:
                recomp_answers_digest = norm_digest
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflict: Answer set content digest mismatch with computed digest",
                )
        computed_answers_digest = recomp_answers_digest

        # 4. Retrieve and verify evaluation record and recompute evaluation results & digest
        evaluation = self.session.scalar(
            select(CustomerDemoEvaluation).where(
                CustomerDemoEvaluation.tenant_id == tenant_id,
                CustomerDemoEvaluation.id == current_adoption.evaluation_id,
            )
        )
        if evaluation is None or evaluation.answer_revision != ws.current_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evaluation referenced by adoption not found or answer revision mismatch",
            )

        if evaluation.pack_version_id != current_adoption.pack_version_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evaluation pack version mismatch with adoption",
            )

        if evaluation.bundle_digest != expected_bundle_digest:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evaluation bundle digest mismatch with adoption",
            )

        if evaluation.evaluator_version != EVALUATOR_VERSION:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evaluation evaluator version mismatch",
            )

        computed_eval_results = evaluate_bundle(current_adoption.pack_version_id, answer.answers)
        if evaluation.results != computed_eval_results:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evaluation results mismatch with evaluated bundle",
            )

        computed_eval_digest = compute_evaluation_digest(
            answer_digest=computed_answers_digest,
            answer_revision=ws.current_revision,
            pack_version_id=current_adoption.pack_version_id,
            bundle_digest=expected_bundle_digest,
            results=computed_eval_results,
            evaluator_version=EVALUATOR_VERSION,
        )
        if evaluation.content_digest != computed_eval_digest:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Evaluation content digest mismatch with computed digest",
            )

        return current_adoption, evaluation, answer

    def record_assessment(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        work_id: UUID,
        body: AssessmentCreateRequest,
        request_id: str | None = None,
    ) -> AssessmentOperationReceiptDto:
        """Record an explicit human control assessment."""
        self._admit_assessment_caller(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id

        norm_req = {
            "criterion_results": [
                {"criterion_id": c.criterion_id, "result": c.result}
                for c in sorted(body.criterion_results, key=lambda x: x.criterion_id)
            ],
            "endpoint": "record_assessment",
            "evidence_link_ids": [str(lid).lower() for lid in sorted(body.evidence_link_ids)],
            "expected_answer_revision": body.expected_answer_revision,
            "expected_assessment_revision": body.expected_assessment_revision,
            "expected_selection_revision": body.expected_selection_revision,
            "expected_work_version": body.expected_work_version,
            "finding": (
                {
                    "due_date": body.finding.due_date.isoformat()
                    if body.finding.due_date
                    else None,
                    "owner_user_id": str(body.finding.owner_user_id).lower()
                    if body.finding.owner_user_id
                    else None,
                    "severity": body.finding.severity,
                }
                if body.finding
                else None
            ),
            "operation_id": str(body.operation_id).lower(),
            "procedure_digest": body.procedure_digest.lower(),
            "procedure_id": str(body.procedure_id).lower(),
            "procedure_version": body.procedure_version,
            "rationale": body.rationale,
            "result": body.result,
            "work_id": str(work_id).lower(),
        }
        req_digest = hashlib.sha256(canonical_json(norm_req).encode("utf-8")).hexdigest()

        existing_event = self.session.scalar(
            select(CustomerAssessmentEvent).where(
                CustomerAssessmentEvent.tenant_id == tenant_id,
                CustomerAssessmentEvent.operation_id == body.operation_id,
            )
        )
        if existing_event is not None:
            if existing_event.request_digest != req_digest:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflict: Operation ID already used with different request parameters",
                )
            current_item = self._build_work_item(
                tenant_id, work_id, principal=principal, tenant_context=tenant_context
            )
            summary = self._compute_summary(
                tenant_id, principal=principal, tenant_context=tenant_context
            )
            return AssessmentOperationReceiptDto(
                operation_id=body.operation_id,
                event_id=existing_event.id,
                applied_revision=existing_event.revision,
                replayed=True,
                current_item=current_item,
                summary=summary,
            )

        # 1. Lock workspace
        ws = self.session.scalar(
            select(CustomerDemoWorkspace)
            .where(CustomerDemoWorkspace.tenant_id == tenant_id)
            .with_for_update()
        )
        if ws is None or ws.selection_revision == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer demo workspace or active selection not found",
            )

        # 2. Lock work item
        work = self.session.scalar(
            select(CustomerControlWork)
            .where(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.id == work_id,
            )
            .with_for_update()
        )
        if work is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Control work item not found",
            )

        # 3. Lock or create assessment head
        head = self._get_or_create_head(tenant_id, work_id)

        # 4. Lock evidence heads (items) in sorted UUID order
        if body.evidence_link_ids:
            links = self.session.scalars(
                select(CustomerControlEvidenceLink).where(
                    CustomerControlEvidenceLink.tenant_id == tenant_id,
                    CustomerControlEvidenceLink.work_id == work_id,
                    CustomerControlEvidenceLink.id.in_(body.evidence_link_ids),
                )
            ).all()
            if len(links) != len(body.evidence_link_ids):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Evidence link not found or belongs to another work item",
                )
            evidence_ids = sorted(list({lnk.evidence_id for lnk in links}))
            self.session.scalars(
                select(EvidenceItem)
                .where(
                    EvidenceItem.tenant_id == tenant_id,
                    EvidenceItem.id.in_(evidence_ids),
                )
                .order_by(EvidenceItem.id)
                .with_for_update()
            ).all()

        # Recheck committed operation under existing locks before CAS verification
        committed_event = self.session.scalar(
            select(CustomerAssessmentEvent).where(
                CustomerAssessmentEvent.tenant_id == tenant_id,
                CustomerAssessmentEvent.operation_id == body.operation_id,
            )
        )
        if committed_event is not None:
            if committed_event.request_digest != req_digest:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflict: Operation ID already used with different request parameters",
                )
            current_item = self._build_work_item(
                tenant_id, work_id, principal=principal, tenant_context=tenant_context
            )
            summary = self._compute_summary(
                tenant_id, principal=principal, tenant_context=tenant_context
            )
            return AssessmentOperationReceiptDto(
                operation_id=body.operation_id,
                event_id=committed_event.id,
                applied_revision=committed_event.revision,
                replayed=True,
                current_item=current_item,
                summary=summary,
            )

        # CAS verification
        if ws.current_revision != body.expected_answer_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Stale expected answer revision",
            )
        if ws.selection_revision != body.expected_selection_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Stale expected selection revision",
            )
        if work.version != body.expected_work_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Stale expected work version",
            )
        if head.current_revision != body.expected_assessment_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Stale expected assessment revision",
            )

        # Adoption and snapshot verification
        adoption, evaluation, answer = self._validate_adoption_and_snapshots(tenant_id, ws, work)

        # Procedure check
        proc = get_procedure_for_control_version(work.control_version_id)
        if (
            body.procedure_id != proc["id"]
            or body.procedure_version != proc["version"]
            or body.procedure_digest.lower() != proc["digest"].lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Procedure ID, version or digest does not match synthetic procedure for control",
            )

        criteria_map = {c.criterion_id: c.result for c in body.criterion_results}
        all_pass = all(res == "PASS" for res in criteria_map.values())
        any_fail = any(res == "FAIL" for res in criteria_map.values())
        any_insufficient = any(res == "INSUFFICIENT_EVIDENCE" for res in criteria_map.values())
        has_pass = any(res == "PASS" for res in criteria_map.values())

        bundle = get_bundle_by_version_id(adoption.pack_version_id)
        eval_results_map: dict[str, str] = {}
        if evaluation and evaluation.results:
            for r in evaluation.results:
                eval_results_map[str(r["requirement_version_id"])] = str(
                    r.get("result") or r.get("status") or ""
                )

        mapped_req_statuses: list[str] = []
        for req in bundle.get("requirements", []):
            if req.get("control_version_id") == str(work.control_version_id):
                req_ver_id = req.get("version_id")
                if req_ver_id:
                    st = eval_results_map.get(str(req_ver_id), "NEEDS_INFORMATION")
                    mapped_req_statuses.append(st)

        all_reqs_applicable = bool(mapped_req_statuses) and all(
            st == "APPLICABLE" for st in mapped_req_statuses
        )
        all_reqs_not_applicable = bool(mapped_req_statuses) and all(
            st == "NOT_APPLICABLE" for st in mapped_req_statuses
        )

        if body.result == "PASS":
            if not all_pass:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="PASS assessment requires all criteria to be PASS",
                )
            if len(body.evidence_link_ids) < 1:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="PASS assessment requires at least one validated evidence link",
                )
            if not all_reqs_applicable:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="PASS assessment requires all mapped requirements to be APPLICABLE",
                )
            if all_reqs_not_applicable:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Cannot assess control as PASS when all mapped requirements are NOT_APPLICABLE",
                )
            if body.finding is not None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Finding specification is forbidden for PASS assessment",
                )
        elif body.result == "FAIL":
            if not any_fail:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="FAIL assessment requires at least one FAIL criterion",
                )
            if body.finding is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Finding specification is required for FAIL assessment",
                )
        elif body.result == "PARTIAL":
            if not (has_pass and not all_pass):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="PARTIAL assessment requires at least one PASS and at least one non-PASS criterion",
                )
            if body.finding is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Finding specification is required for PARTIAL assessment",
                )
        elif body.result == "INSUFFICIENT_EVIDENCE":
            if not any_insufficient:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="INSUFFICIENT_EVIDENCE assessment requires at least one INSUFFICIENT_EVIDENCE criterion",
                )
            if body.finding is not None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Finding specification is forbidden for INSUFFICIENT_EVIDENCE assessment",
                )

        if body.finding and body.finding.owner_user_id:
            owners_resp = self.work_service.get_owners(principal, tenant_context, limit=100)
            if not any(o.user_id == body.finding.owner_user_id for o in owners_resp.items):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Selected owner is not an eligible active member of this tenant",
                )

        validated_pins: list[ValidatedAssessmentLink] = []
        for lid in body.evidence_link_ids:
            v_link = self.work_service.get_validated_assessment_link(
                principal,
                tenant_context,
                work_id=work.id,
                link_id=lid,
            )
            validated_pins.append(v_link)

        now = datetime.now(UTC)
        event_id = uuid4()
        new_revision = head.current_revision + 1

        details_payload = {
            "adoption_id": str(work.adoption_id),
            "adopted_control_id": str(work.control_id),
            "answer_digest": answer.content_digest,
            "answer_revision": ws.current_revision,
            "bundle_digest": adoption.bundle_digest,
            "control_version_id": str(work.control_version_id),
            "criterion_results": [
                {"criterion_id": c.criterion_id, "result": c.result}
                for c in sorted(body.criterion_results, key=lambda x: x.criterion_id)
            ],
            "evaluation_digest": evaluation.content_digest,
            "evaluation_id": str(adoption.evaluation_id),
            "evidence_pins": [
                {
                    "evidence_id": str(p.evidence_id),
                    "file_hash": p.file_hash,
                    "file_id": str(p.file_id),
                    "latest_review_event_id": str(p.latest_review_event_id),
                    "link_id": str(p.link_id),
                    "revision_digest": p.revision_digest,
                    "revision_number": p.revision_number,
                    "scan_verified_at": p.scan_verified_at.isoformat()
                    if p.scan_verified_at
                    else None,
                }
                for p in validated_pins
            ],
            "observed_work_version": work.version,
            "pack_version_id": str(adoption.pack_version_id),
            "procedure_snapshot": proc,
            "rationale": body.rationale,
            "selection_revision": ws.selection_revision,
        }

        ctx = EncryptionContext(
            tenant_id=tenant_id,
            resource_type="customer_assessment_event",
            resource_id=str(event_id),
            field_name="details",
        )
        enc_details = self.codec.encrypt_text(
            json.dumps(details_payload, sort_keys=True, default=str), ctx
        )

        event = CustomerAssessmentEvent(
            tenant_id=tenant_id,
            id=event_id,
            work_id=work.id,
            revision=new_revision,
            operation_id=body.operation_id,
            request_digest=req_digest,
            event_type="ASSESSMENT",
            result=body.result,
            observed_work_version=work.version,
            details_encrypted=enc_details,
            actor_id=principal.user_id,
            created_at=now,
        )
        self.session.add(event)

        if body.result in ("FAIL", "PARTIAL") and body.finding:
            finding = CustomerAssessmentFinding(
                tenant_id=tenant_id,
                id=uuid4(),
                work_id=work.id,
                source_event_id=event_id,
                current_event_id=event_id,
                severity=body.finding.severity,
                owner_user_id=body.finding.owner_user_id,
                due_date=body.finding.due_date,
                status="OPEN",
                version=1,
                created_at=now,
                updated_at=now,
            )
            self.session.add(finding)

        head.current_revision = new_revision
        head.updated_at = now

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_demo.assessment.create",
            resource_type="customer_assessment_event",
            resource_id=str(event_id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "adoption_id": str(work.adoption_id),
                "control_id": str(work.control_id),
                "revision_number": new_revision,
            },
        )
        self.session.flush()

        current_item = self._build_work_item(
            tenant_id, work.id, principal=principal, tenant_context=tenant_context
        )
        summary = self._compute_summary(
            tenant_id, principal=principal, tenant_context=tenant_context
        )

        return AssessmentOperationReceiptDto(
            operation_id=body.operation_id,
            event_id=event_id,
            applied_revision=new_revision,
            replayed=False,
            current_item=current_item,
            summary=summary,
        )

    def record_retest(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        work_id: UUID,
        body: RetestCreateRequest,
        request_id: str | None = None,
    ) -> AssessmentOperationReceiptDto:
        """Record an explicit human retest against open findings."""
        self._admit_assessment_caller(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id

        norm_req = {
            "criterion_results": [
                {"criterion_id": c.criterion_id, "result": c.result}
                for c in sorted(body.criterion_results, key=lambda x: x.criterion_id)
            ],
            "endpoint": "record_retest",
            "evidence_link_ids": [str(lid).lower() for lid in sorted(body.evidence_link_ids)],
            "expected_answer_revision": body.expected_answer_revision,
            "expected_assessment_revision": body.expected_assessment_revision,
            "expected_selection_revision": body.expected_selection_revision,
            "expected_work_version": body.expected_work_version,
            "findings": [
                {"expected_version": f.expected_version, "id": str(f.id).lower()}
                for f in sorted(body.findings, key=lambda x: str(x.id))
            ],
            "operation_id": str(body.operation_id).lower(),
            "procedure_digest": body.procedure_digest.lower(),
            "procedure_id": str(body.procedure_id).lower(),
            "procedure_version": body.procedure_version,
            "rationale": body.rationale,
            "result": body.result,
            "work_id": str(work_id).lower(),
        }
        req_digest = hashlib.sha256(canonical_json(norm_req).encode("utf-8")).hexdigest()

        existing_event = self.session.scalar(
            select(CustomerAssessmentEvent).where(
                CustomerAssessmentEvent.tenant_id == tenant_id,
                CustomerAssessmentEvent.operation_id == body.operation_id,
            )
        )
        if existing_event is not None:
            if existing_event.request_digest != req_digest:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflict: Operation ID already used with different request parameters",
                )
            current_item = self._build_work_item(
                tenant_id, work_id, principal=principal, tenant_context=tenant_context
            )
            summary = self._compute_summary(
                tenant_id, principal=principal, tenant_context=tenant_context
            )
            return AssessmentOperationReceiptDto(
                operation_id=body.operation_id,
                event_id=existing_event.id,
                applied_revision=existing_event.revision,
                replayed=True,
                current_item=current_item,
                summary=summary,
            )

        # 1. Lock workspace
        ws = self.session.scalar(
            select(CustomerDemoWorkspace)
            .where(CustomerDemoWorkspace.tenant_id == tenant_id)
            .with_for_update()
        )
        if ws is None or ws.selection_revision == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer demo workspace or active selection not found",
            )

        # 2. Lock work item
        work = self.session.scalar(
            select(CustomerControlWork)
            .where(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.id == work_id,
            )
            .with_for_update()
        )
        if work is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Control work item not found",
            )

        # 3. Lock or create assessment head
        head = self._get_or_create_head(tenant_id, work_id)

        # 4. Lock finding rows in sorted UUID order
        finding_ids = sorted([f.id for f in body.findings])
        locked_findings = self.session.scalars(
            select(CustomerAssessmentFinding)
            .where(
                CustomerAssessmentFinding.tenant_id == tenant_id,
                CustomerAssessmentFinding.work_id == work.id,
                CustomerAssessmentFinding.id.in_(finding_ids),
            )
            .order_by(CustomerAssessmentFinding.id)
            .with_for_update()
        ).all()
        if len(locked_findings) != len(finding_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more specified findings not found for this control work item",
            )
        for f_row in locked_findings:
            ref = next(f for f in body.findings if f.id == f_row.id)
            if f_row.status == "RESOLVED":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Conflict: Finding '{f_row.id}' is already RESOLVED",
                )
            if f_row.version != ref.expected_version:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Conflict: Stale expected version for finding '{f_row.id}'",
                )

        # 5. Lock evidence heads in sorted UUID order
        if body.evidence_link_ids:
            links = self.session.scalars(
                select(CustomerControlEvidenceLink).where(
                    CustomerControlEvidenceLink.tenant_id == tenant_id,
                    CustomerControlEvidenceLink.work_id == work_id,
                    CustomerControlEvidenceLink.id.in_(body.evidence_link_ids),
                )
            ).all()
            if len(links) != len(body.evidence_link_ids):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Evidence link not found or belongs to another work item",
                )
            evidence_ids = sorted(list({lnk.evidence_id for lnk in links}))
            self.session.scalars(
                select(EvidenceItem)
                .where(
                    EvidenceItem.tenant_id == tenant_id,
                    EvidenceItem.id.in_(evidence_ids),
                )
                .order_by(EvidenceItem.id)
                .with_for_update()
            ).all()

        # Recheck committed operation under existing locks before CAS verification
        committed_event = self.session.scalar(
            select(CustomerAssessmentEvent).where(
                CustomerAssessmentEvent.tenant_id == tenant_id,
                CustomerAssessmentEvent.operation_id == body.operation_id,
            )
        )
        if committed_event is not None:
            if committed_event.request_digest != req_digest:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflict: Operation ID already used with different request parameters",
                )
            current_item = self._build_work_item(
                tenant_id, work_id, principal=principal, tenant_context=tenant_context
            )
            summary = self._compute_summary(
                tenant_id, principal=principal, tenant_context=tenant_context
            )
            return AssessmentOperationReceiptDto(
                operation_id=body.operation_id,
                event_id=committed_event.id,
                applied_revision=committed_event.revision,
                replayed=True,
                current_item=current_item,
                summary=summary,
            )

        # CAS verification
        if ws.current_revision != body.expected_answer_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Stale expected answer revision",
            )
        if ws.selection_revision != body.expected_selection_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Stale expected selection revision",
            )
        if work.version != body.expected_work_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Stale expected work version",
            )
        if head.current_revision != body.expected_assessment_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Stale expected assessment revision",
            )

        # Adoption and snapshot verification
        adoption, evaluation, answer = self._validate_adoption_and_snapshots(tenant_id, ws, work)

        # Procedure check
        proc = get_procedure_for_control_version(work.control_version_id)
        if (
            body.procedure_id != proc["id"]
            or body.procedure_version != proc["version"]
            or body.procedure_digest.lower() != proc["digest"].lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Procedure ID, version or digest does not match synthetic procedure for control",
            )

        criteria_map = {c.criterion_id: c.result for c in body.criterion_results}
        all_pass = all(res == "PASS" for res in criteria_map.values())
        any_fail = any(res == "FAIL" for res in criteria_map.values())
        any_insufficient = any(res == "INSUFFICIENT_EVIDENCE" for res in criteria_map.values())
        has_pass = any(res == "PASS" for res in criteria_map.values())

        bundle = get_bundle_by_version_id(adoption.pack_version_id)
        eval_results_map: dict[str, str] = {}
        if evaluation and evaluation.results:
            for r in evaluation.results:
                eval_results_map[str(r["requirement_version_id"])] = str(
                    r.get("result") or r.get("status") or ""
                )

        mapped_req_statuses: list[str] = []
        for req in bundle.get("requirements", []):
            if req.get("control_version_id") == str(work.control_version_id):
                req_ver_id = req.get("version_id")
                if req_ver_id:
                    st = eval_results_map.get(str(req_ver_id), "NEEDS_INFORMATION")
                    mapped_req_statuses.append(st)

        all_reqs_applicable = bool(mapped_req_statuses) and all(
            st == "APPLICABLE" for st in mapped_req_statuses
        )

        if body.result == "PASS":
            if not all_pass:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="PASS retest requires all criteria to be PASS",
                )
            if len(body.evidence_link_ids) < 1:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="PASS retest requires at least one validated evidence link",
                )
            if not all_reqs_applicable:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="PASS retest requires all mapped requirements to be APPLICABLE",
                )
        elif body.result == "FAIL":
            if not any_fail:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="FAIL retest requires at least one FAIL criterion",
                )
        elif body.result == "PARTIAL":
            if not (has_pass and not all_pass):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="PARTIAL retest requires at least one PASS and at least one non-PASS criterion",
                )
        elif body.result == "INSUFFICIENT_EVIDENCE":
            if not any_insufficient:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="INSUFFICIENT_EVIDENCE retest requires at least one INSUFFICIENT_EVIDENCE criterion",
                )

        validated_pins: list[ValidatedAssessmentLink] = []
        for lid in body.evidence_link_ids:
            v_link = self.work_service.get_validated_assessment_link(
                principal,
                tenant_context,
                work_id=work.id,
                link_id=lid,
            )
            validated_pins.append(v_link)

        now = datetime.now(UTC)
        event_id = uuid4()
        new_revision = head.current_revision + 1

        details_payload = {
            "adoption_id": str(work.adoption_id),
            "adopted_control_id": str(work.control_id),
            "answer_digest": answer.content_digest,
            "answer_revision": ws.current_revision,
            "bundle_digest": adoption.bundle_digest,
            "control_version_id": str(work.control_version_id),
            "criterion_results": [
                {"criterion_id": c.criterion_id, "result": c.result}
                for c in sorted(body.criterion_results, key=lambda x: x.criterion_id)
            ],
            "evaluation_digest": evaluation.content_digest,
            "evaluation_id": str(adoption.evaluation_id),
            "evidence_pins": [
                {
                    "evidence_id": str(p.evidence_id),
                    "file_hash": p.file_hash,
                    "file_id": str(p.file_id),
                    "latest_review_event_id": str(p.latest_review_event_id),
                    "link_id": str(p.link_id),
                    "revision_digest": p.revision_digest,
                    "revision_number": p.revision_number,
                    "scan_verified_at": p.scan_verified_at.isoformat()
                    if p.scan_verified_at
                    else None,
                }
                for p in validated_pins
            ],
            "observed_work_version": work.version,
            "pack_version_id": str(adoption.pack_version_id),
            "procedure_snapshot": proc,
            "rationale": body.rationale,
            "retested_finding_ids": [str(f.id) for f in locked_findings],
            "selection_revision": ws.selection_revision,
        }

        ctx = EncryptionContext(
            tenant_id=tenant_id,
            resource_type="customer_assessment_event",
            resource_id=str(event_id),
            field_name="details",
        )
        enc_details = self.codec.encrypt_text(
            json.dumps(details_payload, sort_keys=True, default=str), ctx
        )

        event = CustomerAssessmentEvent(
            tenant_id=tenant_id,
            id=event_id,
            work_id=work.id,
            revision=new_revision,
            operation_id=body.operation_id,
            request_digest=req_digest,
            event_type="RETEST",
            result=body.result,
            observed_work_version=work.version,
            details_encrypted=enc_details,
            actor_id=principal.user_id,
            created_at=now,
        )
        self.session.add(event)

        if body.result == "PASS":
            for f_row in locked_findings:
                f_row.status = "RESOLVED"
                f_row.current_event_id = event_id
                f_row.version = f_row.version + 1
                f_row.updated_at = now

        head.current_revision = new_revision
        head.updated_at = now

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_demo.assessment.retest",
            resource_type="customer_assessment_event",
            resource_id=str(event_id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "adoption_id": str(work.adoption_id),
                "control_id": str(work.control_id),
                "revision_number": new_revision,
            },
        )
        self.session.flush()

        current_item = self._build_work_item(
            tenant_id, work.id, principal=principal, tenant_context=tenant_context
        )
        summary = self._compute_summary(
            tenant_id, principal=principal, tenant_context=tenant_context
        )

        return AssessmentOperationReceiptDto(
            operation_id=body.operation_id,
            event_id=event_id,
            applied_revision=new_revision,
            replayed=False,
            current_item=current_item,
            summary=summary,
        )

    def update_finding(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        finding_id: UUID,
        body: FindingPatchRequest,
        request_id: str | None = None,
    ) -> AssessmentOperationReceiptDto:
        """Update remediation details on an assessment finding."""
        self._admit_assessment_caller(principal, tenant_context, operation="mutate")
        tenant_id = tenant_context.tenant_id

        # Determine work_id
        pre_finding = self.session.scalar(
            select(CustomerAssessmentFinding).where(
                CustomerAssessmentFinding.tenant_id == tenant_id,
                CustomerAssessmentFinding.id == finding_id,
            )
        )
        if not pre_finding:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assessment finding not found",
            )
        work_id = pre_finding.work_id

        norm_req = {
            "due_date": body.due_date.isoformat() if body.due_date else None,
            "endpoint": "update_finding",
            "expected_answer_revision": body.expected_answer_revision,
            "expected_assessment_revision": body.expected_assessment_revision,
            "expected_finding_version": body.expected_finding_version,
            "expected_selection_revision": body.expected_selection_revision,
            "expected_work_version": body.expected_work_version,
            "finding_id": str(finding_id).lower(),
            "operation_id": str(body.operation_id).lower(),
            "owner_user_id": str(body.owner_user_id).lower() if body.owner_user_id else None,
            "remediation_note": body.remediation_note,
            "severity": body.severity,
            "status": body.status,
            "work_id": str(work_id).lower(),
        }
        req_digest = hashlib.sha256(canonical_json(norm_req).encode("utf-8")).hexdigest()

        existing_event = self.session.scalar(
            select(CustomerAssessmentEvent).where(
                CustomerAssessmentEvent.tenant_id == tenant_id,
                CustomerAssessmentEvent.operation_id == body.operation_id,
            )
        )
        if existing_event is not None:
            if existing_event.request_digest != req_digest:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflict: Operation ID already used with different request parameters",
                )
            current_item = self._build_work_item(
                tenant_id, work_id, principal=principal, tenant_context=tenant_context
            )
            summary = self._compute_summary(
                tenant_id, principal=principal, tenant_context=tenant_context
            )
            return AssessmentOperationReceiptDto(
                operation_id=body.operation_id,
                event_id=existing_event.id,
                applied_revision=existing_event.revision,
                replayed=True,
                current_item=current_item,
                summary=summary,
            )

        # 1. Lock workspace
        ws = self.session.scalar(
            select(CustomerDemoWorkspace)
            .where(CustomerDemoWorkspace.tenant_id == tenant_id)
            .with_for_update()
        )
        if ws is None or ws.selection_revision == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer demo workspace or active selection not found",
            )

        # 2. Lock work item
        work = self.session.scalar(
            select(CustomerControlWork)
            .where(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.id == work_id,
            )
            .with_for_update()
        )
        if work is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Control work item not found",
            )

        # 3. Lock assessment head
        head = self._get_or_create_head(tenant_id, work_id)

        # 4. Lock finding row
        finding = self.session.scalar(
            select(CustomerAssessmentFinding)
            .where(
                CustomerAssessmentFinding.tenant_id == tenant_id,
                CustomerAssessmentFinding.id == finding_id,
                CustomerAssessmentFinding.work_id == work_id,
            )
            .with_for_update()
        )
        if finding is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assessment finding not found",
            )

        # Recheck committed operation under existing locks before CAS verification
        committed_event = self.session.scalar(
            select(CustomerAssessmentEvent).where(
                CustomerAssessmentEvent.tenant_id == tenant_id,
                CustomerAssessmentEvent.operation_id == body.operation_id,
            )
        )
        if committed_event is not None:
            if committed_event.request_digest != req_digest:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflict: Operation ID already used with different request parameters",
                )
            current_item = self._build_work_item(
                tenant_id, work_id, principal=principal, tenant_context=tenant_context
            )
            summary = self._compute_summary(
                tenant_id, principal=principal, tenant_context=tenant_context
            )
            return AssessmentOperationReceiptDto(
                operation_id=body.operation_id,
                event_id=committed_event.id,
                applied_revision=committed_event.revision,
                replayed=True,
                current_item=current_item,
                summary=summary,
            )

        # CAS verification
        if ws.current_revision != body.expected_answer_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Stale expected answer revision",
            )
        if ws.selection_revision != body.expected_selection_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Stale expected selection revision",
            )
        if work.version != body.expected_work_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Stale expected work version",
            )
        if head.current_revision != body.expected_assessment_revision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Stale expected assessment revision",
            )
        if finding.version != body.expected_finding_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Stale expected finding version",
            )

        if finding.status == "RESOLVED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Cannot patch a RESOLVED finding",
            )

        # Adoption and snapshot verification
        adoption, evaluation, answer = self._validate_adoption_and_snapshots(tenant_id, ws, work)

        if body.owner_user_id:
            owners_resp = self.work_service.get_owners(principal, tenant_context, limit=100)
            if not any(o.user_id == body.owner_user_id for o in owners_resp.items):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Selected owner is not an eligible active member of this tenant",
                )

        now = datetime.now(UTC)
        event_id = uuid4()
        new_revision = head.current_revision + 1

        details_payload = {
            "adoption_id": str(work.adoption_id),
            "adopted_control_id": str(work.control_id),
            "answer_digest": answer.content_digest,
            "answer_revision": ws.current_revision,
            "bundle_digest": adoption.bundle_digest,
            "control_version_id": str(work.control_version_id),
            "evaluation_digest": evaluation.content_digest,
            "evaluation_id": str(adoption.evaluation_id),
            "finding_id": str(finding.id),
            "new_due_date": body.due_date.isoformat() if body.due_date else None,
            "new_owner_user_id": str(body.owner_user_id) if body.owner_user_id else None,
            "new_severity": body.severity,
            "new_status": body.status,
            "observed_work_version": work.version,
            "pack_version_id": str(adoption.pack_version_id),
            "previous_due_date": finding.due_date.isoformat() if finding.due_date else None,
            "previous_owner_user_id": str(finding.owner_user_id) if finding.owner_user_id else None,
            "previous_severity": finding.severity,
            "previous_status": finding.status,
            "remediation_note": body.remediation_note,
            "selection_revision": ws.selection_revision,
        }

        ctx = EncryptionContext(
            tenant_id=tenant_id,
            resource_type="customer_assessment_event",
            resource_id=str(event_id),
            field_name="details",
        )
        enc_details = self.codec.encrypt_text(
            json.dumps(details_payload, sort_keys=True, default=str), ctx
        )

        event = CustomerAssessmentEvent(
            tenant_id=tenant_id,
            id=event_id,
            work_id=work.id,
            revision=new_revision,
            operation_id=body.operation_id,
            request_digest=req_digest,
            event_type="FINDING_UPDATED",
            result=None,
            observed_work_version=work.version,
            details_encrypted=enc_details,
            actor_id=principal.user_id,
            created_at=now,
        )
        self.session.add(event)

        finding.current_event_id = event_id
        finding.severity = body.severity
        finding.owner_user_id = body.owner_user_id
        finding.due_date = body.due_date
        finding.status = body.status
        finding.version = finding.version + 1
        finding.updated_at = now

        head.current_revision = new_revision
        head.updated_at = now

        record_audit_event(
            self.session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="customer_demo.assessment.finding_update",
            resource_type="customer_assessment_event",
            resource_id=str(event_id),
            request_id=request_id or f"req-{uuid4()}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "finding_id": str(finding.id),
                "version": finding.version,
                "revision_number": new_revision,
            },
        )
        self.session.flush()

        current_item = self._build_work_item(
            tenant_id, work.id, principal=principal, tenant_context=tenant_context
        )
        summary = self._compute_summary(
            tenant_id, principal=principal, tenant_context=tenant_context
        )

        return AssessmentOperationReceiptDto(
            operation_id=body.operation_id,
            event_id=event_id,
            applied_revision=new_revision,
            replayed=False,
            current_item=current_item,
            summary=summary,
        )

    def get_assessment_work_list(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        adoption_id: UUID | None = None,
    ) -> AssessmentWorkListResponse:
        """List assessment work items and overall readiness posture."""
        self._admit_assessment_caller(principal, tenant_context, operation="read")
        tenant_id = tenant_context.tenant_id

        ws, current_adoption = self._get_current_workspace_and_adoption(tenant_id)
        if ws is None or ws.selection_revision == 0:
            return AssessmentWorkListResponse(
                tenant_id=tenant_id,
                adoption_id=None,
                answer_revision=0,
                selection_revision=0,
                is_stale=False,
                summary=ReadinessSummaryDto(
                    total_controls=0,
                    stale_work=0,
                    needs_information=0,
                    not_applicable=0,
                    unassessed=0,
                    unavailable_evidence=0,
                    stale_assessment=0,
                    insufficient_evidence=0,
                    fail=0,
                    partial=0,
                    pass_with_open_findings=0,
                    pass_count=0,
                    open_findings=0,
                    in_remediation_findings=0,
                    resolved_findings=0,
                    blocked_control_ids=[],
                    reason_codes=[],
                ),
                items=[],
            )

        target_adoption = current_adoption
        if adoption_id is not None:
            target_adoption = self.session.scalar(
                select(CustomerDemoAdoption).where(
                    CustomerDemoAdoption.tenant_id == tenant_id,
                    CustomerDemoAdoption.id == adoption_id,
                )
            )

        if target_adoption is None:
            return AssessmentWorkListResponse(
                tenant_id=tenant_id,
                adoption_id=adoption_id,
                answer_revision=ws.current_revision,
                selection_revision=ws.selection_revision,
                is_stale=True,
                summary=ReadinessSummaryDto(
                    total_controls=0,
                    stale_work=0,
                    needs_information=0,
                    not_applicable=0,
                    unassessed=0,
                    unavailable_evidence=0,
                    stale_assessment=0,
                    insufficient_evidence=0,
                    fail=0,
                    partial=0,
                    pass_with_open_findings=0,
                    pass_count=0,
                    open_findings=0,
                    in_remediation_findings=0,
                    resolved_findings=0,
                    blocked_control_ids=[],
                    reason_codes=["ADOPTION_NOT_FOUND"],
                ),
                items=[],
            )

        work_items = self.session.scalars(
            select(CustomerControlWork)
            .where(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.adoption_id == target_adoption.id,
            )
            .order_by(CustomerControlWork.id)
        ).all()

        items = [
            self._build_work_item(
                tenant_id, w.id, principal=principal, tenant_context=tenant_context
            )
            for w in work_items
        ]
        summary = self._compute_summary(
            tenant_id,
            principal=principal,
            tenant_context=tenant_context,
            target_adoption_id=target_adoption.id,
        )
        is_stale = target_adoption.selection_revision != ws.selection_revision

        return AssessmentWorkListResponse(
            tenant_id=tenant_id,
            adoption_id=target_adoption.id,
            answer_revision=ws.current_revision,
            selection_revision=ws.selection_revision,
            is_stale=is_stale,
            summary=summary,
            items=items,
        )

    def get_assessment_work_item(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        work_id: UUID,
    ) -> AssessmentWorkItemDto:
        """Get single assessment work item."""
        self._admit_assessment_caller(principal, tenant_context, operation="read")
        return self._build_work_item(
            tenant_context.tenant_id, work_id, principal=principal, tenant_context=tenant_context
        )

    def _build_work_item(
        self,
        tenant_id: UUID,
        work_id: UUID,
        principal: Principal,
        tenant_context: TenantContext,
    ) -> AssessmentWorkItemDto:
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

        head = self.session.scalar(
            select(CustomerAssessmentHead).where(
                CustomerAssessmentHead.tenant_id == tenant_id,
                CustomerAssessmentHead.work_id == work_id,
            )
        )
        assessment_rev = head.current_revision if head else 0

        proc = get_procedure_for_control_version(work.control_version_id)
        procedure_dto = ProcedureDto(
            id=proc["id"],
            version=proc["version"],
            digest=proc["digest"],
            criteria=[ProcedureCriterionDto(**c) for c in proc["criteria"]],
            disclaimer=proc["disclaimer"],
        )

        events = self.session.scalars(
            select(CustomerAssessmentEvent)
            .where(
                CustomerAssessmentEvent.tenant_id == tenant_id,
                CustomerAssessmentEvent.work_id == work_id,
            )
            .order_by(CustomerAssessmentEvent.revision.desc())
        ).all()

        history_items: list[AssessmentHistoryItemDto] = []
        for e in events:
            ctx = EncryptionContext(
                tenant_id=tenant_id,
                resource_type="customer_assessment_event",
                resource_id=str(e.id),
                field_name="details",
            )
            try:
                dec_text = self.codec.decrypt_text(e.details_encrypted, ctx)
                det = json.loads(dec_text) if isinstance(dec_text, str) else dec_text
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Corrupt assessment event details: failed closed",
                ) from exc

            history_items.append(
                AssessmentHistoryItemDto(
                    event_id=e.id,
                    revision=e.revision,
                    operation_id=e.operation_id,
                    event_type=e.event_type,
                    result=e.result,
                    observed_work_version=e.observed_work_version,
                    actor_id=e.actor_id,
                    created_at=e.created_at,
                    details=det,
                )
            )

        latest_assessment_event = next(
            (
                e
                for e in events
                if e.event_type in ("ASSESSMENT", "RETEST") and e.result is not None
            ),
            None,
        )

        latest_assessment_dto: LatestAssessmentDto | None = None
        is_unavailable_evidence = False
        is_stale_assessment = False
        unavailable_reasons: list[str] = []
        stale_reasons: list[str] = []

        if latest_assessment_event:
            ctx = EncryptionContext(
                tenant_id=tenant_id,
                resource_type="customer_assessment_event",
                resource_id=str(latest_assessment_event.id),
                field_name="details",
            )
            try:
                dec_text = self.codec.decrypt_text(latest_assessment_event.details_encrypted, ctx)
                det = json.loads(dec_text) if isinstance(dec_text, str) else dec_text
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Corrupt assessment event details: failed closed",
                ) from exc

            crit_results = det.get("criterion_results", [])
            evidence_pins = det.get("evidence_pins", [])

            ws = self.session.scalar(
                select(CustomerDemoWorkspace).where(CustomerDemoWorkspace.tenant_id == tenant_id)
            )
            if ws and (
                det.get("answer_revision") != ws.current_revision
                or det.get("selection_revision") != ws.selection_revision
            ):
                is_stale_assessment = True
                stale_reasons.append("Workspace answers or selection revision changed")
            if work.version != latest_assessment_event.observed_work_version:
                is_stale_assessment = True
                stale_reasons.append("Control work version incremented since assessment")
            if proc["digest"] != det.get("procedure_snapshot", {}).get("digest"):
                is_stale_assessment = True
                stale_reasons.append("Procedure content or digest changed")

            REQUIRED_SNAPSHOT_FIELDS = (
                "adoption_id",
                "adopted_control_id",
                "control_version_id",
                "pack_version_id",
                "bundle_digest",
                "evaluation_id",
                "evaluation_digest",
                "answer_revision",
                "answer_digest",
                "selection_revision",
                "observed_work_version",
                "criterion_results",
                "evidence_pins",
                "procedure_snapshot",
                "rationale",
            )
            missing_req = [f for f in REQUIRED_SNAPSHOT_FIELDS if det.get(f) is None]
            if missing_req:
                is_stale_assessment = True
                stale_reasons.append(
                    f"Required assessment snapshot metadata missing or malformed: {', '.join(missing_req)}"
                )

            # Validate answer, evaluation & adoption chain snapshots against current records
            snap_ans_rev = det.get("answer_revision")
            snap_eval_id_raw = det.get("evaluation_id")
            snap_ans_digest = det.get("answer_digest")
            snap_eval_digest = det.get("evaluation_digest")
            snap_pack_vid_raw = det.get("pack_version_id")
            snap_bundle_digest = det.get("bundle_digest")
            snap_adoption_id_raw = det.get("adoption_id")

            snap_adoption_id: UUID | None = None
            snap_eval_id: UUID | None = None
            snap_pack_vid: UUID | None = None
            try:
                if snap_adoption_id_raw:
                    snap_adoption_id = UUID(str(snap_adoption_id_raw))
                if snap_eval_id_raw:
                    snap_eval_id = UUID(str(snap_eval_id_raw))
                if snap_pack_vid_raw:
                    snap_pack_vid = UUID(str(snap_pack_vid_raw))
            except Exception:
                is_stale_assessment = True
                stale_reasons.append("Malformed UUID in assessment snapshot metadata")

            # Validate adoption association
            adoption: CustomerDemoAdoption | None = None
            expected_bundle_digest: str | None = None
            if snap_adoption_id is not None:
                if work.adoption_id != snap_adoption_id:
                    is_stale_assessment = True
                    stale_reasons.append("Assessment snapshot adoption mismatch with work item")

                adoption = self.session.scalar(
                    select(CustomerDemoAdoption).where(
                        CustomerDemoAdoption.tenant_id == tenant_id,
                        CustomerDemoAdoption.id == work.adoption_id,
                    )
                )
                if adoption is None:
                    is_stale_assessment = True
                    stale_reasons.append("Adoption snapshot record missing")
                else:
                    if snap_pack_vid is not None and adoption.pack_version_id != snap_pack_vid:
                        is_stale_assessment = True
                        stale_reasons.append("Adoption pack version mismatch with snapshot")
                    if snap_eval_id is not None and adoption.evaluation_id != snap_eval_id:
                        is_stale_assessment = True
                        stale_reasons.append("Adoption evaluation ID mismatch with snapshot")
                    if (
                        snap_bundle_digest is not None
                        and adoption.bundle_digest != snap_bundle_digest
                    ):
                        is_stale_assessment = True
                        stale_reasons.append("Adoption bundle digest mismatch with snapshot")

                    try:
                        expected_bundle_digest = get_bundle_digest(adoption.pack_version_id)
                        bundle = get_bundle_by_version_id(adoption.pack_version_id)
                        valid_cv_ids = {
                            str(req.get("control_version_id"))
                            for req in bundle.get("requirements", [])
                        }
                        if str(work.control_version_id) not in valid_cv_ids:
                            is_stale_assessment = True
                            stale_reasons.append("Control version not in adopted bundle")
                    except Exception:
                        is_stale_assessment = True
                        stale_reasons.append("Unknown or unresolvable adopted pack version")

                    if (
                        expected_bundle_digest is not None
                        and adoption.bundle_digest != expected_bundle_digest
                    ):
                        is_stale_assessment = True
                        stale_reasons.append(
                            "Adoption bundle digest mismatch with authoritative pack bundle"
                        )

            # Validate evaluation association & fields
            current_eval: CustomerDemoEvaluation | None = None
            if snap_eval_id is None:
                is_stale_assessment = True
                stale_reasons.append("Evaluation snapshot ID missing")
            else:
                current_eval = self.session.scalar(
                    select(CustomerDemoEvaluation).where(
                        CustomerDemoEvaluation.tenant_id == tenant_id,
                        CustomerDemoEvaluation.id == snap_eval_id,
                    )
                )
                if current_eval is None:
                    is_stale_assessment = True
                    stale_reasons.append("Evaluation snapshot missing")
                else:
                    if snap_pack_vid is not None and current_eval.pack_version_id != snap_pack_vid:
                        is_stale_assessment = True
                        stale_reasons.append("Evaluation pack version mismatch with snapshot")
                    if (
                        adoption is not None
                        and current_eval.pack_version_id != adoption.pack_version_id
                    ):
                        is_stale_assessment = True
                        stale_reasons.append("Evaluation pack version mismatch with adoption")
                    if (
                        snap_bundle_digest is not None
                        and current_eval.bundle_digest != snap_bundle_digest
                    ):
                        is_stale_assessment = True
                        stale_reasons.append("Evaluation bundle digest mismatch with snapshot")
                    if (
                        expected_bundle_digest is not None
                        and current_eval.bundle_digest != expected_bundle_digest
                    ):
                        is_stale_assessment = True
                        stale_reasons.append("Evaluation bundle digest mismatch with pack bundle")
                    if (
                        adoption is not None
                        and current_eval.bundle_digest != adoption.bundle_digest
                    ):
                        is_stale_assessment = True
                        stale_reasons.append("Evaluation bundle digest mismatch with adoption")
                    if current_eval.evaluator_version != EVALUATOR_VERSION:
                        is_stale_assessment = True
                        stale_reasons.append(
                            "Evaluation evaluator version mismatch with authoritative evaluator"
                        )
                    if snap_ans_rev is not None and current_eval.answer_revision != snap_ans_rev:
                        is_stale_assessment = True
                        stale_reasons.append("Evaluation answer revision mismatch with snapshot")

            # Validate answer record & content
            current_ans: CustomerDemoAnswers | None = None
            recomp_ans_digest: str | None = None
            if snap_ans_rev is None:
                is_stale_assessment = True
                stale_reasons.append("Saved answer snapshot revision missing")
            else:
                current_ans = self.session.scalar(
                    select(CustomerDemoAnswers).where(
                        CustomerDemoAnswers.tenant_id == tenant_id,
                        CustomerDemoAnswers.revision == snap_ans_rev,
                    )
                )
                if current_ans is None:
                    is_stale_assessment = True
                    stale_reasons.append("Saved answer snapshot missing")
                else:
                    if (
                        current_eval is not None
                        and current_ans.revision != current_eval.answer_revision
                    ):
                        is_stale_assessment = True
                        stale_reasons.append("Answer revision mismatch with evaluation")

                    recomp_ans_digest = compute_answers_digest(
                        current_ans.company_code, current_ans.answers
                    )
                    if current_ans.content_digest != recomp_ans_digest:
                        norm_a = normalize_answers(current_ans.answers)
                        norm_d = compute_answers_digest(current_ans.company_code, norm_a)
                        if current_ans.content_digest == norm_d:
                            recomp_ans_digest = norm_d
                        else:
                            is_stale_assessment = True
                            stale_reasons.append("Saved answer content digest corrupted")
                    if snap_ans_digest is not None and (
                        recomp_ans_digest != snap_ans_digest
                        or current_ans.content_digest != snap_ans_digest
                    ):
                        is_stale_assessment = True
                        stale_reasons.append("Saved answer content or digest changed")

            # Validate computed evaluation results and digest
            if (
                current_eval is not None
                and current_ans is not None
                and adoption is not None
                and recomp_ans_digest is not None
                and snap_ans_rev is not None
            ):
                try:
                    recomp_results = evaluate_bundle(adoption.pack_version_id, current_ans.answers)
                    if current_eval.results != recomp_results:
                        is_stale_assessment = True
                        stale_reasons.append("Evaluation results changed for current answers")
                    recomp_eval_digest = compute_evaluation_digest(
                        answer_digest=recomp_ans_digest,
                        answer_revision=snap_ans_rev,
                        pack_version_id=adoption.pack_version_id,
                        bundle_digest=expected_bundle_digest or adoption.bundle_digest,
                        results=recomp_results,
                        evaluator_version=EVALUATOR_VERSION,
                    )
                    if snap_eval_digest is not None and (
                        recomp_eval_digest != snap_eval_digest
                        or current_eval.content_digest != snap_eval_digest
                    ):
                        is_stale_assessment = True
                        stale_reasons.append("Evaluation content digest changed")
                    if current_eval.content_digest != recomp_eval_digest:
                        is_stale_assessment = True
                        stale_reasons.append("Saved evaluation content digest corrupted")
                except Exception:
                    is_stale_assessment = True
                    stale_reasons.append("Failed to evaluate bundle for evaluation verification")

            # Validate each pinned evidence link via B facade with caller context
            for pin in evidence_pins:
                link_id = (
                    UUID(pin["link_id"]) if isinstance(pin["link_id"], str) else pin["link_id"]
                )
                try:
                    v_link = self.work_service.get_validated_assessment_link(
                        principal,
                        tenant_context,
                        work_id=work.id,
                        link_id=link_id,
                    )
                except HTTPException as http_exc:
                    if http_exc.status_code in (
                        status.HTTP_404_NOT_FOUND,
                        status.HTTP_400_BAD_REQUEST,
                        status.HTTP_409_CONFLICT,
                    ):
                        is_unavailable_evidence = True
                        unavailable_reasons.append(
                            f"Evidence link '{link_id}' is unavailable: {http_exc.detail}"
                        )
                        continue
                    raise
                except (CustomerDemoAdmissionError, CustomerDemoDatabaseAdmissionError):
                    raise
                except Exception as exc:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Internal error verifying evidence link: failed closed",
                    ) from exc

                if str(v_link.latest_review_event_id) != str(pin["latest_review_event_id"]):
                    is_stale_assessment = True
                    stale_reasons.append(
                        f"Evidence link '{link_id}' was reviewed again after assessment snapshot"
                    )
                if v_link.revision_digest != pin["revision_digest"]:
                    is_unavailable_evidence = True
                    unavailable_reasons.append(
                        f"Evidence link '{link_id}' revision digest changed since assessment snapshot"
                    )
                if v_link.file_hash != pin["file_hash"]:
                    is_unavailable_evidence = True
                    unavailable_reasons.append(
                        f"Evidence link '{link_id}' file content hash changed since assessment snapshot"
                    )
                if v_link.revision_number != pin["revision_number"]:
                    is_unavailable_evidence = True
                    unavailable_reasons.append(
                        f"Evidence link '{link_id}' revision number changed since assessment snapshot"
                    )
            pin_dtos = [
                PinnedEvidenceDto(
                    link_id=UUID(p["link_id"]) if isinstance(p["link_id"], str) else p["link_id"],
                    evidence_id=UUID(p["evidence_id"])
                    if isinstance(p["evidence_id"], str)
                    else p["evidence_id"],
                    revision_number=p["revision_number"],
                    revision_digest=p["revision_digest"],
                    latest_review_event_id=UUID(p["latest_review_event_id"])
                    if isinstance(p["latest_review_event_id"], str)
                    else p["latest_review_event_id"],
                    file_id=UUID(p["file_id"]) if isinstance(p["file_id"], str) else p["file_id"],
                    file_hash=p["file_hash"],
                    scan_verified_at=(
                        datetime.fromisoformat(p["scan_verified_at"])
                        if p.get("scan_verified_at")
                        else None
                    ),
                )
                for p in evidence_pins
            ]

            all_stale_reasons = unavailable_reasons + stale_reasons
            latest_assessment_dto = LatestAssessmentDto(
                event_id=latest_assessment_event.id,
                revision=latest_assessment_event.revision,
                result=latest_assessment_event.result or "UNKNOWN",
                actor_id=latest_assessment_event.actor_id,
                created_at=latest_assessment_event.created_at,
                rationale=det.get("rationale", ""),
                criterion_results=crit_results,
                evidence_pins=pin_dtos,
                is_stale=bool(all_stale_reasons),
                stale_reasons=all_stale_reasons,
            )

        findings_rows = self.session.scalars(
            select(CustomerAssessmentFinding)
            .where(
                CustomerAssessmentFinding.tenant_id == tenant_id,
                CustomerAssessmentFinding.work_id == work_id,
            )
            .order_by(CustomerAssessmentFinding.created_at.desc())
        ).all()

        findings_dtos: list[FindingDto] = []
        for f in findings_rows:
            owner_display: str | None = None
            if f.owner_user_id:
                u = self.session.scalar(select(User).where(User.id == f.owner_user_id))
                if u:
                    owner_display = u.display_name
            findings_dtos.append(
                FindingDto(
                    id=f.id,
                    source_event_id=f.source_event_id,
                    current_event_id=f.current_event_id,
                    severity=f.severity,
                    owner_user_id=f.owner_user_id,
                    owner_display_name=owner_display,
                    due_date=f.due_date,
                    status=f.status,
                    version=f.version,
                    created_at=f.created_at,
                    updated_at=f.updated_at,
                )
            )

        primary_state, blockers, req_results = self._evaluate_control_state(
            tenant_id=tenant_id,
            work=work,
            latest_assessment=latest_assessment_dto,
            findings=findings_dtos,
            is_unavailable_evidence=is_unavailable_evidence,
            is_stale_assessment=is_stale_assessment,
        )

        return AssessmentWorkItemDto(
            work_id=work.id,
            control_version_id=work.control_version_id,
            work_version=work.version,
            assessment_revision=assessment_rev,
            procedure=procedure_dto,
            latest_assessment=latest_assessment_dto,
            primary_state=primary_state,
            blockers=blockers,
            findings=findings_dtos,
            history=history_items,
            requirement_results=req_results,
        )

    def _evaluate_control_state(
        self,
        tenant_id: UUID,
        work: CustomerControlWork,
        latest_assessment: LatestAssessmentDto | None,
        findings: list[FindingDto],
        is_unavailable_evidence: bool = False,
        is_stale_assessment: bool = False,
    ) -> tuple[str, list[str], list[dict[str, Any]]]:
        blockers: list[str] = []

        ws, current_adoption = self._get_current_workspace_and_adoption(tenant_id)
        adoption = self.session.scalar(
            select(CustomerDemoAdoption).where(
                CustomerDemoAdoption.tenant_id == tenant_id,
                CustomerDemoAdoption.id == work.adoption_id,
            )
        )
        is_stale_work = False
        if ws and current_adoption and current_adoption.id != work.adoption_id:
            is_stale_work = True
            blockers.append("WORK_STALE")

        evaluation = (
            self.session.scalar(
                select(CustomerDemoEvaluation).where(
                    CustomerDemoEvaluation.tenant_id == tenant_id,
                    CustomerDemoEvaluation.id == adoption.evaluation_id,
                )
            )
            if adoption
            else None
        )
        try:
            bundle = get_bundle_by_version_id(adoption.pack_version_id) if adoption else {}
        except Exception:
            bundle = {}
            blockers.append("PACK_VERSION_INVALID")
            is_stale_work = True
        eval_results_map: dict[str, str] = {}
        if evaluation and evaluation.results:
            for r in evaluation.results:
                eval_results_map[str(r["requirement_version_id"])] = str(
                    r.get("result") or r.get("status") or ""
                )

        mapped_req_statuses: list[str] = []
        req_results_list: list[dict[str, Any]] = []
        for req in bundle.get("requirements", []):
            if req.get("control_version_id") == str(work.control_version_id):
                req_ver_id = req.get("version_id")
                req_code = req.get("requirement_code") or req.get("code") or "REQ"
                req_title = req.get("title") or req.get("summary") or "Requirement"
                if req_ver_id:
                    st = eval_results_map.get(str(req_ver_id), "NEEDS_INFORMATION")
                    mapped_req_statuses.append(st)
                    req_results_list.append(
                        {
                            "requirement_version_id": str(req_ver_id),
                            "code": req_code,
                            "title": req_title,
                            "status": st,
                        }
                    )

        all_not_applicable = bool(mapped_req_statuses) and all(
            st == "NOT_APPLICABLE" for st in mapped_req_statuses
        )
        has_needs_info = any(st == "NEEDS_INFORMATION" for st in mapped_req_statuses)

        if has_needs_info:
            blockers.append("REQUIREMENTS_NEED_INFORMATION")
        if all_not_applicable:
            blockers.append("CONTROL_NOT_APPLICABLE")

        open_findings = [f for f in findings if f.status in ("OPEN", "IN_REMEDIATION")]
        if open_findings:
            blockers.append("OPEN_FINDINGS_EXIST")

        # Contracted priority: STALE_WORK, NEEDS_INFORMATION, NOT_APPLICABLE, UNASSESSED,
        # UNAVAILABLE_EVIDENCE, STALE_ASSESSMENT, INSUFFICIENT_EVIDENCE, FAIL, PARTIAL,
        # PASS_WITH_OPEN_FINDINGS, PASS
        if is_stale_work:
            return "STALE_WORK", blockers, req_results_list
        if has_needs_info:
            return "NEEDS_INFORMATION", blockers, req_results_list
        if all_not_applicable:
            return "NOT_APPLICABLE", blockers, req_results_list

        if latest_assessment is None:
            blockers.append("ASSESSMENT_REQUIRED")
            return "UNASSESSED", blockers, req_results_list

        if is_unavailable_evidence:
            blockers.append("PINNED_EVIDENCE_UNAVAILABLE")
            return "UNAVAILABLE_EVIDENCE", blockers, req_results_list

        if is_stale_assessment or latest_assessment.is_stale:
            blockers.append("ASSESSMENT_STALE")
            return "STALE_ASSESSMENT", blockers, req_results_list

        if latest_assessment.result == "INSUFFICIENT_EVIDENCE":
            blockers.append("EVIDENCE_INSUFFICIENT")
            return "INSUFFICIENT_EVIDENCE", blockers, req_results_list
        if latest_assessment.result == "FAIL":
            blockers.append("ASSESSMENT_FAILED")
            return "FAIL", blockers, req_results_list
        if latest_assessment.result == "PARTIAL":
            blockers.append("ASSESSMENT_PARTIAL")
            return "PARTIAL", blockers, req_results_list

        if latest_assessment.result == "PASS":
            if open_findings:
                return "PASS_WITH_OPEN_FINDINGS", blockers, req_results_list
            return "PASS", blockers, req_results_list

        return "UNASSESSED", blockers, req_results_list

    def _compute_summary(
        self,
        tenant_id: UUID,
        *,
        principal: Principal,
        tenant_context: TenantContext,
        target_adoption_id: UUID | None = None,
    ) -> ReadinessSummaryDto:
        ws, current_adoption = self._get_current_workspace_and_adoption(tenant_id)
        if ws is None or current_adoption is None:
            return ReadinessSummaryDto(
                total_controls=0,
                stale_work=0,
                needs_information=0,
                not_applicable=0,
                unassessed=0,
                unavailable_evidence=0,
                stale_assessment=0,
                insufficient_evidence=0,
                fail=0,
                partial=0,
                pass_with_open_findings=0,
                pass_count=0,
                open_findings=0,
                in_remediation_findings=0,
                resolved_findings=0,
                blocked_control_ids=[],
                reason_codes=[],
            )

        eff_adopt_id = target_adoption_id or current_adoption.id
        work_items = self.session.scalars(
            select(CustomerControlWork).where(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.adoption_id == eff_adopt_id,
            )
        ).all()

        stale_work_cnt = 0
        needs_info_cnt = 0
        not_app_cnt = 0
        unassessed_cnt = 0
        unavailable_evidence_cnt = 0
        stale_assess_cnt = 0
        insufficient_cnt = 0
        fail_cnt = 0
        partial_cnt = 0
        pass_open_cnt = 0
        pass_cnt = 0

        blocked_cids: set[UUID] = set()
        all_reasons: set[str] = set()

        for w in work_items:
            dto = self._build_work_item(
                tenant_id, w.id, principal=principal, tenant_context=tenant_context
            )
            st = dto.primary_state
            if st == "STALE_WORK":
                stale_work_cnt += 1
                blocked_cids.add(w.control_id)
            elif st == "NEEDS_INFORMATION":
                needs_info_cnt += 1
                blocked_cids.add(w.control_id)
            elif st == "NOT_APPLICABLE":
                not_app_cnt += 1
            elif st == "UNASSESSED":
                unassessed_cnt += 1
                blocked_cids.add(w.control_id)
            elif st == "UNAVAILABLE_EVIDENCE":
                unavailable_evidence_cnt += 1
                blocked_cids.add(w.control_id)
            elif st == "STALE_ASSESSMENT":
                stale_assess_cnt += 1
                blocked_cids.add(w.control_id)
            elif st == "INSUFFICIENT_EVIDENCE":
                insufficient_cnt += 1
                blocked_cids.add(w.control_id)
            elif st == "FAIL":
                fail_cnt += 1
                blocked_cids.add(w.control_id)
            elif st == "PARTIAL":
                partial_cnt += 1
                blocked_cids.add(w.control_id)
            elif st == "PASS_WITH_OPEN_FINDINGS":
                pass_open_cnt += 1
                blocked_cids.add(w.control_id)
            elif st == "PASS":
                pass_cnt += 1

            for b in dto.blockers:
                all_reasons.add(b)

        work_ids = [w.id for w in work_items]
        findings = (
            self.session.scalars(
                select(CustomerAssessmentFinding).where(
                    CustomerAssessmentFinding.tenant_id == tenant_id,
                    CustomerAssessmentFinding.work_id.in_(work_ids),
                )
            ).all()
            if work_ids
            else []
        )

        open_cnt = sum(1 for f in findings if f.status == "OPEN")
        in_rem_cnt = sum(1 for f in findings if f.status == "IN_REMEDIATION")
        resolved_cnt = sum(1 for f in findings if f.status == "RESOLVED")

        return ReadinessSummaryDto(
            total_controls=len(work_items),
            stale_work=stale_work_cnt,
            needs_information=needs_info_cnt,
            not_applicable=not_app_cnt,
            unassessed=unassessed_cnt,
            unavailable_evidence=unavailable_evidence_cnt,
            stale_assessment=stale_assess_cnt,
            insufficient_evidence=insufficient_cnt,
            fail=fail_cnt,
            partial=partial_cnt,
            pass_with_open_findings=pass_open_cnt,
            pass_count=pass_cnt,
            open_findings=open_cnt,
            in_remediation_findings=in_rem_cnt,
            resolved_findings=resolved_cnt,
            blocked_control_ids=sorted(list(blocked_cids)),
            reason_codes=sorted(list(all_reasons)),
        )

    def get_procedure(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        work_id: UUID,
    ) -> ProcedureDto:
        """Get synthetic procedure for work item."""
        self._admit_assessment_caller(principal, tenant_context, operation="read")
        tenant_id = tenant_context.tenant_id
        work = self.session.scalar(
            select(CustomerControlWork).where(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.id == work_id,
            )
        )
        if not work:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Control work item not found",
            )
        proc = get_procedure_for_control_version(work.control_version_id)
        return ProcedureDto(
            id=proc["id"],
            version=proc["version"],
            digest=proc["digest"],
            criteria=[ProcedureCriterionDto(**c) for c in proc["criteria"]],
            disclaimer=proc["disclaimer"],
        )

    patch_finding = update_finding

    def get_history(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        work_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> AssessmentHistoryResponse:
        """Get paginated history events for work item."""
        self._admit_assessment_caller(principal, tenant_context, operation="read")
        tenant_id = tenant_context.tenant_id
        work = self.session.scalar(
            select(CustomerControlWork).where(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.id == work_id,
            )
        )
        if not work:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Control work item not found",
            )

        events = self.session.scalars(
            select(CustomerAssessmentEvent)
            .where(
                CustomerAssessmentEvent.tenant_id == tenant_id,
                CustomerAssessmentEvent.work_id == work_id,
            )
            .order_by(CustomerAssessmentEvent.revision.asc())
        ).all()

        total = len(events)
        paged = events[offset : offset + limit]

        items: list[AssessmentHistoryItemDto] = []
        for e in paged:
            ctx = EncryptionContext(
                tenant_id=tenant_id,
                resource_type="customer_assessment_event",
                resource_id=str(e.id),
                field_name="details",
            )
            try:
                dec_text = self.codec.decrypt_text(e.details_encrypted, ctx)
                det = json.loads(dec_text) if isinstance(dec_text, str) else dec_text
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Corrupt assessment event details: failed closed",
                ) from exc

            items.append(
                AssessmentHistoryItemDto(
                    event_id=e.id,
                    revision=e.revision,
                    operation_id=e.operation_id,
                    event_type=e.event_type,
                    result=e.result,
                    observed_work_version=e.observed_work_version,
                    actor_id=e.actor_id,
                    created_at=e.created_at,
                    details=det,
                )
            )

        return AssessmentHistoryResponse(
            work_id=work_id,
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )
