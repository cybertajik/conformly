"""Connected offline integration test: negative evidence upload -> human rejection -> blocked assessment -> blocked pre-audit & cross-tenant denial."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditEvent
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.config import get_settings
from conformly.crypto.policy import DataClassification
from conformly.customer_demo.assessment_models import (
    CustomerAssessmentEvent,
    CustomerAssessmentFinding,
    CustomerAssessmentHead,
)
from conformly.customer_demo.assessment_procedures import get_procedure_for_control_version
from conformly.customer_demo.assessment_schemas import (
    AssessmentCreateRequest,
    AssessmentCriterionResultDto,
    FindingCreateSpecificationDto,
)
from conformly.customer_demo.assessment_service import CustomerAssessmentService
from conformly.customer_demo.evaluator import (
    compute_answers_digest,
    compute_evaluation_digest,
    evaluate_bundle,
)
from conformly.customer_demo.fixture import (
    BUNDLE_V1_DIGEST,
    EVALUATOR_VERSION,
    PACK_VERSION_V1_ID,
)
from conformly.customer_demo.models import (
    CustomerDemoAdoption,
    CustomerDemoAnswers,
    CustomerDemoEvaluation,
    CustomerDemoWorkspace,
)
from conformly.customer_demo.preaudit_models import (
    CustomerPreaudit,
    CustomerPreauditEvent,
)
from conformly.customer_demo.preaudit_schemas import (
    ApprovePreauditRequest,
    CreatePreauditRequest,
    DownloadPreauditReportRequest,
    FreezeScopeRequest,
    ReviewDecisionRequest,
    SubmitReviewRequest,
)
from conformly.customer_demo.preaudit_service import CustomerPreauditService
from conformly.customer_demo.work_models import CustomerControlWork
from conformly.customer_demo.work_scanner import StrictEvidenceMalwareScanner
from conformly.customer_demo.work_schemas import (
    CreateEvidenceRequest,
    CreateReviewRequest,
    InitializeWorkRequest,
)
from conformly.customer_demo.work_service import CustomerControlWorkService
from conformly.entitlements.models import TenantEntitlement
from conformly.identity.models import (
    Membership,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
    UserStatus,
)
from conformly.storage.models import StoredFile, StoredFileStatus


class InjectedCleanScanner(StrictEvidenceMalwareScanner):
    """Test-only scanner simulating a clean ClamAV scan without network sockets."""

    def __init__(self) -> None:
        super().__init__(clamav_host="127.0.0.1", clamav_port=3310)
        self.scanned_files: list[str] = []

    def scan(self, data: bytes, filename: str) -> None:
        self.scanned_files.append(filename)


def _seed_tenant_with_adoption(
    session: Session,
    *,
    name: str,
    seed_pack: bool,
) -> dict:
    now = datetime.now(UTC)
    tenant_id = uuid4()
    owner_id = uuid4()
    reviewer_id = uuid4()

    session.add(
        Tenant(
            id=tenant_id,
            name=name,
            slug=f"tenant-{tenant_id}",
            status=TenantStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        TenantEntitlement(
            tenant_id=tenant_id,
            plan_code="tier_a",
            enabled_modules=["frameworks", "evidence", "tasks", "preaudit", "findings"],
            max_members=100,
            max_storage_bytes=10_000_000,
            allowed_framework_slugs=["*"],
            effective_from=now - timedelta(days=1),
            effective_until=now + timedelta(days=365),
        )
    )

    owner_user = User(
        id=owner_id,
        oidc_issuer="https://synth-auth.invalid",
        oidc_subject=f"sub-owner-{tenant_id}",
        email=f"owner-{tenant_id}@synth.invalid",
        display_name=f"{name} Owner",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    reviewer_user = User(
        id=reviewer_id,
        oidc_issuer="https://synth-auth.invalid",
        oidc_subject=f"sub-rev-{tenant_id}",
        email=f"reviewer-{tenant_id}@synth.invalid",
        display_name=f"{name} Reviewer",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    session.add_all([owner_user, reviewer_user])
    session.add_all(
        [
            Membership(
                tenant_id=tenant_id,
                user_id=owner_id,
                role=Role.OWNER,
                status=MembershipStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            ),
            Membership(
                tenant_id=tenant_id,
                user_id=reviewer_id,
                role=Role.COMPLIANCE_MANAGER,
                status=MembershipStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            ),
        ]
    )

    adoption_id = None
    if seed_pack:
        answers_data = {
            "synthetic_wp09_uses_cloud": True,
            "synthetic_wp09_operating_region": "EU",
        }
        ans_digest = compute_answers_digest("ALPHA", answers_data)
        eval_results = evaluate_bundle(PACK_VERSION_V1_ID, answers_data)
        eval_digest = compute_evaluation_digest(
            answer_digest=ans_digest,
            answer_revision=1,
            pack_version_id=PACK_VERSION_V1_ID,
            bundle_digest=BUNDLE_V1_DIGEST,
            results=eval_results,
            evaluator_version=EVALUATOR_VERSION,
        )
        session.add(
            CustomerDemoWorkspace(
                tenant_id=tenant_id,
                current_revision=1,
                selection_revision=1,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            CustomerDemoAnswers(
                tenant_id=tenant_id,
                revision=1,
                company_code="ALPHA",
                answers=answers_data,
                content_digest=ans_digest,
                actor_id=owner_id,
                created_at=now,
            )
        )
        ev = CustomerDemoEvaluation(
            id=uuid4(),
            tenant_id=tenant_id,
            answer_revision=1,
            pack_version_id=PACK_VERSION_V1_ID,
            bundle_digest=BUNDLE_V1_DIGEST,
            evaluator_version=EVALUATOR_VERSION,
            results=eval_results,
            content_digest=eval_digest,
            actor_id=owner_id,
            created_at=now,
        )
        session.add(ev)
        adopt = CustomerDemoAdoption(
            id=uuid4(),
            tenant_id=tenant_id,
            selection_revision=1,
            evaluation_id=ev.id,
            pack_version_id=PACK_VERSION_V1_ID,
            bundle_digest=BUNDLE_V1_DIGEST,
            actor_id=owner_id,
            created_at=now,
        )
        session.add(adopt)
        adoption_id = adopt.id

    session.commit()

    owner_principal = Principal(
        user_id=owner_id,
        mfa_verified=True,
    )
    owner_ctx = TenantContext(
        tenant_id=tenant_id,
        user_id=owner_id,
        role=Role.OWNER,
    )
    reviewer_principal = Principal(
        user_id=reviewer_id,
        mfa_verified=True,
    )
    reviewer_ctx = TenantContext(
        tenant_id=tenant_id,
        user_id=reviewer_id,
        role=Role.COMPLIANCE_MANAGER,
    )
    return {
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "reviewer_id": reviewer_id,
        "adoption_id": adoption_id,
        "owner_principal": owner_principal,
        "owner_ctx": owner_ctx,
        "reviewer_principal": reviewer_principal,
        "reviewer_ctx": reviewer_ctx,
    }


def test_negative_evidence_to_preaudit_blocks_positive_outcomes_and_denies_cross_tenant(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = get_settings()
    monkeypatch.setattr(cfg, "enable_customer_demo", True)
    monkeypatch.setattr(cfg, "enable_customer_preaudit", True)
    monkeypatch.setattr(cfg, "environment", "test")

    tenant_a = _seed_tenant_with_adoption(session, name="Alpha Tenant", seed_pack=True)
    tenant_b = _seed_tenant_with_adoption(session, name="Beta Tenant", seed_pack=True)

    scanner = InjectedCleanScanner()
    work_svc = CustomerControlWorkService(session, scanner=scanner)
    assess_svc = CustomerAssessmentService(session)
    preaudit_svc = CustomerPreauditService(session)

    # 1. Initialize control work for Tenant A
    work_list = work_svc.initialize_work(
        tenant_a["owner_principal"],
        tenant_a["owner_ctx"],
        InitializeWorkRequest(
            operation_id=uuid4(),
            adoption_id=tenant_a["adoption_id"],
            expected_selection_revision=1,
            expected_answer_revision=1,
        ),
        request_id="req-init-work-a",
    )
    assert len(work_list.items) >= 1
    target_work = work_list.items[0]

    # 2. Seed clean synthetic file representing overdue review / missing approval metadata
    pdf_bytes = (
        b"%PDF-1.4\n% Synthetic overdue supplier review LP-003 (next review due 2026-05-15)\n"
    )
    stored_file = StoredFile(
        id=uuid4(),
        tenant_id=tenant_a["tenant_id"],
        original_filename="overdue_supplier_review_lp003.pdf",
        content_type="application/pdf",
        plaintext_size_bytes=len(pdf_bytes),
        ciphertext_size_bytes=len(pdf_bytes) + 28,
        storage_backend="local",
        encryption_algorithm="AES-256-GCM",
        key_version="v1",
        wrapped_dek_nonce="nonce-wrap-001",
        wrapped_dek="wrapped-dek-001",
        ciphertext_nonce="nonce-ct-001",
        object_key=f"tenants/{tenant_a['tenant_id']}/files/lp003.pdf",
        classification=DataClassification.RESTRICTED.value,
        status=StoredFileStatus.ACTIVE,
        ciphertext_sha256=hashlib.sha256(b"cipher:" + pdf_bytes).hexdigest(),
        plaintext_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        created_by_user_id=tenant_a["owner_id"],
        created_at=datetime.now(UTC),
    )
    session.add(stored_file)
    session.commit()

    with patch("conformly.customer_demo.work_service.StorageService") as mock_storage_cls:
        mock_storage_cls.return_value.download_file.return_value = (stored_file, pdf_bytes)
        ev_receipt = work_svc.create_evidence(
            tenant_a["owner_principal"],
            tenant_a["owner_ctx"],
            target_work.id,
            CreateEvidenceRequest(
                operation_id=uuid4(),
                expected_selection_revision=1,
                expected_answer_revision=1,
                expected_work_version=target_work.version,
                file_id=stored_file.id,
                rationale="Overdue Supplier Review LP-003 (due 2026-05-15, missing 2026 sign-off).",
            ),
            request_id="req-create-ev-a",
        )
    assert "overdue_supplier_review_lp003.pdf" in scanner.scanned_files
    assert len(ev_receipt.current_work.links) == 1
    rejected_link_id = ev_receipt.current_work.links[0].id
    work_ver_after_ev = ev_receipt.applied_work_version

    # 3. Human reviewer explicitly rejects the overdue/incomplete evidence link
    rev_receipt = work_svc.create_review(
        tenant_a["reviewer_principal"],
        tenant_a["reviewer_ctx"],
        target_work.id,
        rejected_link_id,
        CreateReviewRequest(
            operation_id=uuid4(),
            expected_selection_revision=1,
            expected_answer_revision=1,
            expected_work_version=work_ver_after_ev,
            decision="REJECTED",
            rationale="Rejected: supplier review overdue since 2026-05-15 and approval missing.",
        ),
        request_id="req-reject-ev-a",
    )
    assert rev_receipt.current_work.links[0].review == "REJECTED"
    work_ver_after_rej = rev_receipt.applied_work_version

    # 4. Rejected evidence link CANNOT support a positive (PASS) assessment
    proc = get_procedure_for_control_version(target_work.control_version_id)
    pass_criteria = [
        AssessmentCriterionResultDto(criterion_id=c["id"], result="PASS") for c in proc["criteria"]
    ]
    with pytest.raises(HTTPException) as exc_pass:
        assess_svc.record_assessment(
            tenant_a["owner_principal"],
            tenant_a["owner_ctx"],
            target_work.id,
            AssessmentCreateRequest(
                operation_id=uuid4(),
                expected_work_version=work_ver_after_rej,
                expected_assessment_revision=0,
                expected_answer_revision=1,
                expected_selection_revision=1,
                procedure_id=proc["id"],
                procedure_version=proc["version"],
                procedure_digest=proc["digest"],
                result="PASS",
                rationale="Attempted PASS using rejected overdue evidence link.",
                evidence_link_ids=[rejected_link_id],
                criterion_results=pass_criteria,
            ),
        )
    assert exc_pass.value.status_code in (409, 422)
    assert (
        session.scalar(
            select(func.count())
            .select_from(CustomerAssessmentEvent)
            .where(
                CustomerAssessmentEvent.tenant_id == tenant_a["tenant_id"],
                CustomerAssessmentEvent.work_id == target_work.id,
            )
        )
        == 0
    )

    # 5. Explicitly record FAIL assessment with an OPEN finding
    fail_criteria = [
        AssessmentCriterionResultDto(
            criterion_id=c["id"],
            result="FAIL" if idx == 0 else "PASS",
        )
        for idx, c in enumerate(proc["criteria"])
    ]
    fail_receipt = assess_svc.record_assessment(
        tenant_a["owner_principal"],
        tenant_a["owner_ctx"],
        target_work.id,
        AssessmentCreateRequest(
            operation_id=uuid4(),
            expected_work_version=work_ver_after_rej,
            expected_assessment_revision=0,
            expected_answer_revision=1,
            expected_selection_revision=1,
            procedure_id=proc["id"],
            procedure_version=proc["version"],
            procedure_digest=proc["digest"],
            result="FAIL",
            rationale="Supplier review overdue and management approval missing.",
            evidence_link_ids=[],
            criterion_results=fail_criteria,
            finding=FindingCreateSpecificationDto(
                severity="HIGH",
                owner_user_id=tenant_a["owner_id"],
                due_date=date(2026, 12, 15),
            ),
        ),
    )
    assert fail_receipt.current_item.latest_assessment is not None
    assert fail_receipt.current_item.latest_assessment.result == "FAIL"
    open_findings = session.scalars(
        select(CustomerAssessmentFinding).where(
            CustomerAssessmentFinding.tenant_id == tenant_a["tenant_id"],
            CustomerAssessmentFinding.work_id == target_work.id,
            CustomerAssessmentFinding.status == "OPEN",
        )
    ).all()
    assert len(open_findings) == 1

    # 6. Pre-audit case without qualifying review snapshot CANNOT return a private report
    case_draft = preaudit_svc.create_case(
        tenant_a["owner_principal"],
        tenant_a["owner_ctx"],
        CreatePreauditRequest(
            operation_id=uuid4(),
            adoption_id=tenant_a["adoption_id"],
            lead_user_id=tenant_a["owner_id"],
            reviewer_user_id=tenant_a["reviewer_id"],
            title="Negative Evidence Pre-Audit Case",
            description="Verifies open findings block positive review and unreviewed case blocks report.",
        ),
    )
    assert case_draft.status == "DRAFT"
    assert case_draft.current_review_snapshot_id is None

    with pytest.raises(HTTPException) as exc_rep_no_snap:
        preaudit_svc.download_report(
            tenant_a["owner_principal"],
            tenant_a["owner_ctx"],
            case_draft.id,
            DownloadPreauditReportRequest(
                expected_revision=case_draft.revision,
                snapshot_id=uuid4(),
            ),
        )
    assert exc_rep_no_snap.value.status_code == 409
    assert (
        session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.tenant_id == tenant_a["tenant_id"],
                AuditEvent.action == "customer_preaudit.report_download_prepared",
            )
        )
        == 0
    )

    # 7. Freeze scope and submit review -> open finding / FAIL control blocks positive advancement
    case_frozen = preaudit_svc.freeze_scope(
        tenant_a["owner_principal"],
        tenant_a["owner_ctx"],
        case_draft.id,
        FreezeScopeRequest(operation_id=uuid4(), expected_revision=case_draft.revision),
    )
    assert case_frozen.status == "FROZEN"

    case_in_review = preaudit_svc.submit_review(
        tenant_a["owner_principal"],
        tenant_a["owner_ctx"],
        case_draft.id,
        SubmitReviewRequest(
            operation_id=uuid4(),
            expected_revision=case_frozen.revision,
        ),
    )
    assert case_in_review.status == "IN_REVIEW"
    assert len(case_in_review.blockers) > 0
    assert case_in_review.current_review_snapshot_id is not None
    assert case_in_review.current_review_snapshot_digest is not None

    with pytest.raises(HTTPException) as exc_accept:
        preaudit_svc.review_decision(
            tenant_a["reviewer_principal"],
            tenant_a["reviewer_ctx"],
            case_in_review.id,
            ReviewDecisionRequest(
                operation_id=uuid4(),
                expected_revision=case_in_review.revision,
                snapshot_id=case_in_review.current_review_snapshot_id,
                snapshot_digest=case_in_review.current_review_snapshot_digest,
                decision="ACCEPT",
                notes="Attempted positive review despite open finding.",
            ),
        )
    assert exc_accept.value.status_code == 409

    with pytest.raises(HTTPException) as exc_approve:
        preaudit_svc.approve_case(
            tenant_a["owner_principal"],
            tenant_a["owner_ctx"],
            case_in_review.id,
            ApprovePreauditRequest(
                operation_id=uuid4(),
                expected_revision=case_in_review.revision,
                snapshot_id=case_in_review.current_review_snapshot_id,
                snapshot_digest=case_in_review.current_review_snapshot_digest,
                approval_notes="Attempted owner approval without REVIEWED state.",
            ),
        )
    assert exc_approve.value.status_code == 409

    # Verify Tenant A state unchanged after blocked positive transitions
    case_row_before = session.scalar(
        select(CustomerPreaudit).where(CustomerPreaudit.id == case_in_review.id)
    )
    assert case_row_before is not None
    assert case_row_before.status == "IN_REVIEW"
    assert case_row_before.revision == case_in_review.revision
    event_count_before = session.scalar(
        select(func.count())
        .select_from(CustomerPreauditEvent)
        .where(CustomerPreauditEvent.preaudit_id == case_in_review.id)
    )
    work_row_before = session.scalar(
        select(CustomerControlWork).where(CustomerControlWork.id == target_work.id)
    )
    assert work_row_before is not None
    work_ver_before = work_row_before.version
    head_row_before = session.scalar(
        select(CustomerAssessmentHead).where(CustomerAssessmentHead.work_id == target_work.id)
    )
    assert head_row_before is not None
    head_rev_before = head_row_before.current_revision

    # 8. Cross-tenant denial: Tenant B cannot read or mutate Tenant A evidence, work, case, or report
    with pytest.raises(HTTPException) as exc_b_file:
        work_svc.download_pinned_file(
            tenant_b["owner_principal"],
            tenant_b["owner_ctx"],
            target_work.id,
            rejected_link_id,
            stored_file.id,
            request_id="req-cross-file-b",
        )
    assert exc_b_file.value.status_code in (403, 404)

    with pytest.raises(HTTPException) as exc_b_rev:
        work_svc.create_review(
            tenant_b["reviewer_principal"],
            tenant_b["reviewer_ctx"],
            target_work.id,
            rejected_link_id,
            CreateReviewRequest(
                operation_id=uuid4(),
                expected_selection_revision=1,
                expected_answer_revision=1,
                expected_work_version=work_ver_before,
                decision="ACCEPTED",
                rationale="Cross-tenant review hijack attempt.",
            ),
            request_id="req-cross-rev-b",
        )
    assert exc_b_rev.value.status_code in (403, 404)

    with pytest.raises(HTTPException) as exc_b_case:
        preaudit_svc.get_case(
            tenant_b["owner_principal"],
            tenant_b["owner_ctx"],
            case_in_review.id,
        )
    assert exc_b_case.value.status_code == 404

    with pytest.raises(HTTPException) as exc_b_report:
        preaudit_svc.download_report(
            tenant_b["owner_principal"],
            tenant_b["owner_ctx"],
            case_in_review.id,
            DownloadPreauditReportRequest(
                expected_revision=case_in_review.revision,
                snapshot_id=case_in_review.current_review_snapshot_id,
            ),
        )
    assert exc_b_report.value.status_code == 404

    # Confirm denied cross-tenant mutations left Tenant A state completely unchanged
    session.expire_all()
    case_row_after = session.scalar(
        select(CustomerPreaudit).where(CustomerPreaudit.id == case_in_review.id)
    )
    assert case_row_after is not None
    assert case_row_after.status == "IN_REVIEW"
    assert case_row_after.revision == case_in_review.revision
    assert (
        session.scalar(
            select(func.count())
            .select_from(CustomerPreauditEvent)
            .where(CustomerPreauditEvent.preaudit_id == case_in_review.id)
        )
        == event_count_before
    )
    work_row_after = session.scalar(
        select(CustomerControlWork).where(CustomerControlWork.id == target_work.id)
    )
    assert work_row_after is not None
    assert work_row_after.version == work_ver_before
    head_row_after = session.scalar(
        select(CustomerAssessmentHead).where(CustomerAssessmentHead.work_id == target_work.id)
    )
    assert head_row_after is not None
    assert head_row_after.current_revision == head_rev_before
