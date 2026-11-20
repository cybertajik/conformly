"""Tests for CustomerPreauditService: lifecycle, admission, freezing, independent review, approval, and tamper protection."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.crypto.policy import DataClassification
from conformly.customer_demo.assessment_schemas import (
    AssessmentCreateRequest,
    AssessmentCriterionResultDto,
)
from conformly.customer_demo.assessment_service import CustomerAssessmentService
from conformly.customer_demo.evaluator import compute_answers_digest, compute_evaluation_digest, evaluate_bundle
from conformly.customer_demo.fixture import (
    BUNDLE_V1_DIGEST,
    EVALUATOR_VERSION,
    PACK_VERSION_V1_ID,
    get_bundle_by_version_id,
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
    CustomerPreauditSnapshot,
)
from conformly.customer_demo.preaudit_schemas import (
    ApprovePreauditRequest,
    CancelPreauditRequest,
    CreatePreauditRequest,
    DownloadPreauditReportRequest,
    FreezeScopeRequest,
    ReviewDecisionRequest,
    SubmitReviewRequest,
)
from conformly.customer_demo.preaudit_service import CustomerPreauditService
from conformly.customer_demo.preaudit_snapshot import PreauditIntegrityError, decrypt_snapshot_payload
from conformly.customer_demo.work_models import CustomerControlWork
from conformly.customer_demo.work_schemas import (
    CreateEvidenceRequest,
    CreateReviewRequest,
    InitializeWorkRequest,
)
from conformly.customer_demo.work_service import CustomerControlWorkService
from conformly.entitlements.models import TenantEntitlement
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User, UserStatus
from conformly.storage.models import StoredFile, StoredFileStatus
from tests.test_customer_assessment_api import MockSuccessfulScanner


@pytest.fixture
def enable_preaudit_env(monkeypatch: pytest.MonkeyPatch):
    from conformly.config import get_settings

    cfg = get_settings()
    monkeypatch.setattr(cfg, "enable_customer_demo", True)
    monkeypatch.setattr(cfg, "enable_customer_preaudit", True)
    monkeypatch.setattr(cfg, "environment", "test")


@pytest.fixture
def preaudit_env(session: Session, enable_preaudit_env):
    tenant_id = uuid4()
    owner_id = uuid4()
    mgr_id = uuid4()
    employee_id = uuid4()
    now = datetime.now(UTC)

    tenant = Tenant(
        id=tenant_id,
        name="Pre-Audit Demo Tenant",
        slug=f"tenant-{tenant_id}",
        status=TenantStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    session.add(tenant)
    session.add(
        TenantEntitlement(
            tenant_id=tenant_id,
            plan_code="tier_a",
            enabled_modules=["frameworks", "evidence", "tasks", "preaudit", "findings"],
            max_members=100,
            max_storage_bytes=10000000,
            allowed_framework_slugs=["*"],
            effective_from=now - timedelta(days=1),
            effective_until=now + timedelta(days=365),
        )
    )

    users = [
        User(
            id=owner_id,
            oidc_issuer="https://auth.example.com",
            oidc_subject="sub-owner",
            email="owner@example.com",
            display_name="Alice Owner",
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        User(
            id=mgr_id,
            oidc_issuer="https://auth.example.com",
            oidc_subject="sub-mgr",
            email="mgr@example.com",
            display_name="Bob Manager",
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        User(
            id=employee_id,
            oidc_issuer="https://auth.example.com",
            oidc_subject="sub-emp",
            email="emp@example.com",
            display_name="Eve Employee",
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
    ]
    session.add_all(users)

    memberships = [
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
            user_id=mgr_id,
            role=Role.COMPLIANCE_MANAGER,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        Membership(
            tenant_id=tenant_id,
            user_id=employee_id,
            role=Role.EMPLOYEE,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
    ]
    session.add_all(memberships)

    # Workspace, answers, evaluation, adoption
    ws = CustomerDemoWorkspace(
        tenant_id=tenant_id,
        current_revision=1,
        selection_revision=1,
        created_at=now,
        updated_at=now,
    )
    session.add(ws)

    answers_data = {"synthetic_wp09_uses_cloud": True, "synthetic_wp09_operating_region": "EU"}
    answers = CustomerDemoAnswers(
        tenant_id=tenant_id,
        revision=1,
        company_code="ALPHA",
        answers=answers_data,
        content_digest=compute_answers_digest("ALPHA", answers_data),
        actor_id=owner_id,
        created_at=now,
    )
    session.add(answers)

    eval_results = evaluate_bundle(PACK_VERSION_V1_ID, answers_data)
    eval_digest = compute_evaluation_digest(
        answer_digest=answers.content_digest,
        answer_revision=1,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=BUNDLE_V1_DIGEST,
        evaluator_version=EVALUATOR_VERSION,
        results=eval_results,
    )
    evaluation = CustomerDemoEvaluation(
        tenant_id=tenant_id,
        id=uuid4(),
        answer_revision=1,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=BUNDLE_V1_DIGEST,
        evaluator_version=EVALUATOR_VERSION,
        results=eval_results,
        content_digest=eval_digest,
        actor_id=owner_id,
        created_at=now,
    )
    session.add(evaluation)

    adoption = CustomerDemoAdoption(
        tenant_id=tenant_id,
        id=uuid4(),
        evaluation_id=evaluation.id,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=BUNDLE_V1_DIGEST,
        actor_id=owner_id,
        created_at=now,
        selection_revision=1,
    )
    session.add(adoption)
    session.flush()

    # Initialize work
    work_service = CustomerControlWorkService(session, scanner=MockSuccessfulScanner())
    owner_p = Principal(user_id=owner_id, mfa_verified=True)
    owner_t = TenantContext(tenant_id=tenant_id, user_id=owner_id, role=Role.OWNER)
    work_service.initialize_work(
        owner_p,
        owner_t,
        InitializeWorkRequest(
            operation_id=uuid4(),
            adoption_id=adoption.id,
            expected_selection_revision=1,
            expected_answer_revision=1,
        ),
        request_id="req-init",
    )
    session.commit()

    return {
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "mgr_id": mgr_id,
        "employee_id": employee_id,
        "adoption_id": adoption.id,
    }


def test_get_eligible_actors(session: Session, preaudit_env):
    env = preaudit_env
    principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    tenant_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)

    svc = CustomerPreauditService(session)
    actors = svc.get_eligible_actors(principal, tenant_context)

    # Must contain owner and manager, but not employee
    uids = [a.user_id for a in actors]
    assert env["owner_id"] in uids
    assert env["mgr_id"] in uids
    assert env["employee_id"] not in uids


def test_create_case_lifecycle_and_idempotency(session: Session, preaudit_env):
    env = preaudit_env
    principal = Principal(user_id=env["mgr_id"], mfa_verified=True)
    tenant_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["mgr_id"], role=Role.COMPLIANCE_MANAGER)

    svc = CustomerPreauditService(session)
    op_id = uuid4()
    req = CreatePreauditRequest(
        operation_id=op_id,
        adoption_id=env["adoption_id"],
        lead_user_id=env["mgr_id"],
        reviewer_user_id=env["owner_id"],
        title="ISO 27001 Rehearsal",
        description="Comprehensive audit prep",
    )
    case_detail = svc.create_case(principal, tenant_context, req)
    assert case_detail.status == "DRAFT"
    assert case_detail.revision == 1
    assert case_detail.title == "ISO 27001 Rehearsal"
    assert case_detail.lead_user_id == env["mgr_id"]
    assert case_detail.reviewer_user_id == env["owner_id"]

    # Exact idempotent retry
    retry_detail = svc.create_case(principal, tenant_context, req)
    assert retry_detail.id == case_detail.id
    assert retry_detail.revision == 1

    # Conflict on mismatched payload
    diff_req = CreatePreauditRequest(
        operation_id=op_id,
        adoption_id=env["adoption_id"],
        lead_user_id=env["mgr_id"],
        reviewer_user_id=env["owner_id"],
        title="Different Title",
    )
    with pytest.raises(HTTPException) as exc:
        svc.create_case(principal, tenant_context, diff_req)
    assert exc.value.status_code == 409


def test_create_case_validation_rules(session: Session, preaudit_env):
    env = preaudit_env
    principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    tenant_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)
    svc = CustomerPreauditService(session)

    # Lead cannot equal reviewer
    with pytest.raises(HTTPException) as exc:
        svc.create_case(
            principal,
            tenant_context,
            CreatePreauditRequest(
                operation_id=uuid4(),
                adoption_id=env["adoption_id"],
                lead_user_id=env["owner_id"],
                reviewer_user_id=env["owner_id"],
            ),
        )
    assert exc.value.status_code == 400

    # Reviewer cannot be non-admitted employee
    with pytest.raises(HTTPException) as exc:
        svc.create_case(
            principal,
            tenant_context,
            CreatePreauditRequest(
                operation_id=uuid4(),
                adoption_id=env["adoption_id"],
                lead_user_id=env["owner_id"],
                reviewer_user_id=env["employee_id"],
            ),
        )
    assert exc.value.status_code == 400


def test_full_preaudit_state_machine_and_report_download(session: Session, preaudit_env):
    env = preaudit_env
    lead_principal = Principal(user_id=env["mgr_id"], mfa_verified=True)
    lead_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["mgr_id"], role=Role.COMPLIANCE_MANAGER)

    rev_principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    rev_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)

    svc = CustomerPreauditService(session)

    # 1. Create case in DRAFT
    case = svc.create_case(
        lead_principal,
        lead_context,
        CreatePreauditRequest(
            operation_id=uuid4(),
            adoption_id=env["adoption_id"],
            lead_user_id=env["mgr_id"],
            reviewer_user_id=env["owner_id"],
            title="Q4 Readiness Check",
        ),
    )
    assert case.status == "DRAFT"

    # 2. Freeze scope -> FROZEN
    frozen_case = svc.freeze_scope(
        lead_principal,
        lead_context,
        case.id,
        FreezeScopeRequest(operation_id=uuid4(), expected_revision=1),
    )
    assert frozen_case.status == "FROZEN"
    assert frozen_case.revision == 2
    assert frozen_case.current_scope_snapshot_id is not None
    assert frozen_case.current_scope_snapshot_digest is not None

    # 3. Submit review -> IN_REVIEW (with blockers because work items are unassessed)
    in_review_case = svc.submit_review(
        lead_principal,
        lead_context,
        case.id,
        SubmitReviewRequest(
            operation_id=uuid4(),
            expected_revision=2,
            submission_notes="Ready for review",
        ),
    )
    assert in_review_case.status == "IN_REVIEW"
    assert in_review_case.revision == 3
    assert in_review_case.current_review_snapshot_id is not None
    assert len(in_review_case.blockers) > 0

    # 4. Reviewer attempts to ACCEPT while blockers exist -> fails closed (409)
    with pytest.raises(HTTPException) as exc:
        svc.review_decision(
            rev_principal,
            rev_context,
            case.id,
            ReviewDecisionRequest(
                operation_id=uuid4(),
                expected_revision=3,
                snapshot_id=in_review_case.current_review_snapshot_id,
                snapshot_digest=in_review_case.current_review_snapshot_digest,
                decision="ACCEPT",
                notes="Premature acceptance",
            ),
        )
    assert exc.value.status_code == 409

    # 5. Lead attempts self-review -> forbidden (403)
    with pytest.raises(HTTPException) as exc:
        svc.review_decision(
            lead_principal,
            lead_context,
            case.id,
            ReviewDecisionRequest(
                operation_id=uuid4(),
                expected_revision=3,
                snapshot_id=in_review_case.current_review_snapshot_id,
                snapshot_digest=in_review_case.current_review_snapshot_digest,
                decision="REQUEST_CHANGES",
                notes="Self review attempt",
            ),
        )
    assert exc.value.status_code == 403

    # 6. Reviewer requests changes -> CHANGES_REQUESTED
    changes_case = svc.review_decision(
        rev_principal,
        rev_context,
        case.id,
        ReviewDecisionRequest(
            operation_id=uuid4(),
            expected_revision=3,
            snapshot_id=in_review_case.current_review_snapshot_id,
            snapshot_digest=in_review_case.current_review_snapshot_digest,
            decision="REQUEST_CHANGES",
            notes="Please complete assessments for all required controls.",
        ),
    )
    assert changes_case.status == "CHANGES_REQUESTED"
    assert changes_case.revision == 4

    # 7. Resubmit review -> IN_REVIEW (sequence 2)
    resubmitted_case = svc.submit_review(
        lead_principal,
        lead_context,
        case.id,
        SubmitReviewRequest(
            operation_id=uuid4(),
            expected_revision=4,
            submission_notes="Resubmitted after addressing feedback",
        ),
    )
    assert resubmitted_case.status == "IN_REVIEW"
    assert resubmitted_case.revision == 5

    # 8. Download report archive from review snapshot
    zip_bytes, sha256, c_obj, snap_obj = svc.download_report(
        lead_principal,
        lead_context,
        case.id,
        DownloadPreauditReportRequest(
            expected_revision=5,
            snapshot_id=resubmitted_case.current_review_snapshot_id,
        ),
    )
    assert len(zip_bytes) > 0
    assert sha256 == hashlib.sha256(zip_bytes).hexdigest()

    # 9. Cancel case by Owner -> CANCELLED
    cancelled_case = svc.cancel_case(
        rev_principal,
        rev_context,
        case.id,
        CancelPreauditRequest(
            operation_id=uuid4(),
            expected_revision=5,
            reason="Project superseded by annual audit",
        ),
    )
    assert cancelled_case.status == "CANCELLED"
    assert cancelled_case.revision == 6

    # 10. History contains all 6 events
    history = svc.get_case_history(lead_principal, lead_context, case.id)
    assert len(history.events) == 6
    types = [e.event_type for e in history.events]
    assert types == [
        "CREATED",
        "SCOPE_FROZEN",
        "SUBMITTED",
        "CHANGES_REQUESTED",
        "SUBMITTED",
        "CANCELLED",
    ]


def test_snapshot_tamper_detection(session: Session, preaudit_env):
    env = preaudit_env
    lead_principal = Principal(user_id=env["mgr_id"], mfa_verified=True)
    lead_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["mgr_id"], role=Role.COMPLIANCE_MANAGER)
    svc = CustomerPreauditService(session)

    case = svc.create_case(
        lead_principal,
        lead_context,
        CreatePreauditRequest(
            operation_id=uuid4(),
            adoption_id=env["adoption_id"],
            lead_user_id=env["mgr_id"],
            reviewer_user_id=env["owner_id"],
        ),
    )
    frozen = svc.freeze_scope(
        lead_principal,
        lead_context,
        case.id,
        FreezeScopeRequest(operation_id=uuid4(), expected_revision=1),
    )

    # Attempt to decrypt with wrong expected digest
    snap = session.execute(
        session.query(CustomerPreauditSnapshot).filter_by(id=frozen.current_scope_snapshot_id)
    ).scalar_one()

    with pytest.raises(PreauditIntegrityError):
        decrypt_snapshot_payload(
            svc.codec,
            env["tenant_id"],
            snap.id,
            snap.payload_encrypted,
            expected_digest="0" * 64,
        )


def _seed_all_controls_passing(session: Session, tenant_id: UUID, actor_id: UUID) -> None:
    works = session.query(CustomerControlWork).filter_by(tenant_id=tenant_id).all()
    principal = Principal(user_id=actor_id, mfa_verified=True)
    tenant_context = TenantContext(tenant_id=tenant_id, user_id=actor_id, role=Role.OWNER)
    work_svc = CustomerControlWorkService(session, scanner=MockSuccessfulScanner())
    assess_svc = CustomerAssessmentService(session)

    for w in works:
        file_id = uuid4()
        now = datetime.now(UTC)
        content = b"Verified evidence for control compliance."
        sf = StoredFile(
            id=file_id,
            tenant_id=tenant_id,
            original_filename="audit_proof.txt",
            content_type="text/plain",
            plaintext_size_bytes=len(content),
            ciphertext_size_bytes=len(content) + 28,
            storage_backend="local",
            encryption_algorithm="AES-256-GCM",
            key_version="v1",
            wrapped_dek_nonce="nonce123456",
            wrapped_dek="wrappeddek123456",
            ciphertext_nonce="nonce123456",
            object_key=f"tenants/{tenant_id}/files/{file_id}/audit_proof.txt",
            classification=DataClassification.RESTRICTED.value,
            status=StoredFileStatus.ACTIVE,
            ciphertext_sha256=hashlib.sha256(b"cipher").hexdigest(),
            plaintext_sha256=hashlib.sha256(content).hexdigest(),
            created_by_user_id=actor_id,
            created_at=now,
        )
        session.add(sf)
        session.commit()

        with patch("conformly.customer_demo.work_service.StorageService") as MockStorage:
            instance = MockStorage.return_value
            instance.download_file.return_value = (sf, content)
            ev_receipt = work_svc.create_evidence(
                principal,
                tenant_context,
                w.id,
                CreateEvidenceRequest(
                    operation_id=uuid4(),
                    expected_selection_revision=1,
                    expected_answer_revision=1,
                    expected_work_version=w.version,
                    file_id=sf.id,
                    rationale="Audit policy evidence",
                ),
                request_id=f"req-pin-{w.id}",
            )
            link_id = ev_receipt.current_work.links[0].id
            session.refresh(w)

            work_svc.create_review(
                principal,
                tenant_context,
                w.id,
                link_id,
                CreateReviewRequest(
                    operation_id=uuid4(),
                    expected_selection_revision=1,
                    expected_answer_revision=1,
                    expected_work_version=w.version,
                    decision="ACCEPTED",
                    rationale="Evidence accepted",
                ),
                request_id=f"req-rev-{w.id}",
            )
            session.refresh(w)

            proc = assess_svc.get_procedure(principal, tenant_context, w.id)
            assess_svc.record_assessment(
                principal,
                tenant_context,
                w.id,
                AssessmentCreateRequest(
                    operation_id=uuid4(),
                    expected_answer_revision=1,
                    expected_selection_revision=1,
                    expected_work_version=w.version,
                    expected_assessment_revision=0,
                    procedure_id=proc.id,
                    procedure_version=proc.version,
                    procedure_digest=proc.digest,
                    result="PASS",
                    rationale="All criteria verified and pass",
                    evidence_link_ids=[link_id],
                    criterion_results=[
                        AssessmentCriterionResultDto(criterion_id=c.id, result="PASS")
                        for c in proc.criteria
                    ],
                ),
                request_id=f"req-pass-{w.id}",
            )
            session.refresh(w)
    session.commit()


def test_positive_end_to_end_approval_workflow(session: Session, preaudit_env):
    """Full positive lifecycle with real work, real evidence, and real PASS assessments."""
    env = preaudit_env
    lead_principal = Principal(user_id=env["mgr_id"], mfa_verified=True)
    lead_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["mgr_id"], role=Role.COMPLIANCE_MANAGER)

    rev_principal = Principal(user_id=env["mgr_id"], mfa_verified=True)
    # Give reviewer another active user
    another_mgr_id = uuid4()
    now = datetime.now(UTC)
    session.add(
        User(
            id=another_mgr_id,
            oidc_issuer="https://auth.example.com",
            oidc_subject="sub-another",
            email="another@example.com",
            display_name="David Reviewer",
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        Membership(
            tenant_id=env["tenant_id"],
            user_id=another_mgr_id,
            role=Role.COMPLIANCE_MANAGER,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()

    rev_principal = Principal(user_id=another_mgr_id, mfa_verified=True)
    rev_context = TenantContext(tenant_id=env["tenant_id"], user_id=another_mgr_id, role=Role.COMPLIANCE_MANAGER)

    owner_principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    owner_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)

    svc = CustomerPreauditService(session)

    # 1. Create case
    case = svc.create_case(
        lead_principal,
        lead_context,
        CreatePreauditRequest(
            operation_id=uuid4(),
            adoption_id=env["adoption_id"],
            lead_user_id=env["mgr_id"],
            reviewer_user_id=another_mgr_id,
            title="Complete Pre-Audit Journey",
        ),
    )
    assert case.status == "DRAFT"

    # 2. Freeze scope
    frozen = svc.freeze_scope(
        lead_principal,
        lead_context,
        case.id,
        FreezeScopeRequest(operation_id=uuid4(), expected_revision=1),
    )
    assert frozen.status == "FROZEN"

    # 3. Submit review initially -> has blockers because work is not assessed yet
    sub1 = svc.submit_review(
        lead_principal,
        lead_context,
        case.id,
        SubmitReviewRequest(operation_id=uuid4(), expected_revision=2, submission_notes="Initial submission"),
    )
    assert sub1.status == "IN_REVIEW"
    assert len(sub1.blockers) > 0

    # Reviewer requests changes
    chg = svc.review_decision(
        rev_principal,
        rev_context,
        case.id,
        ReviewDecisionRequest(
            operation_id=uuid4(),
            expected_revision=3,
            snapshot_id=sub1.current_review_snapshot_id,
            snapshot_digest=sub1.current_review_snapshot_digest,
            decision="REQUEST_CHANGES",
            notes="Please complete all control assessments",
        ),
    )
    assert chg.status == "CHANGES_REQUESTED"

    # 4. Resolve blockers by completing all control work with valid evidence and PASS assessments
    _seed_all_controls_passing(session, env["tenant_id"], env["owner_id"])

    # 5. Resubmit review -> IN_REVIEW with 0 blockers
    sub2 = svc.submit_review(
        lead_principal,
        lead_context,
        case.id,
        SubmitReviewRequest(operation_id=uuid4(), expected_revision=4, submission_notes="Resubmitted with PASS assessments"),
    )
    assert sub2.status == "IN_REVIEW"
    assert len(sub2.blockers) == 0

    # 6. Reviewer accepts -> REVIEWED
    reviewed = svc.review_decision(
        rev_principal,
        rev_context,
        case.id,
        ReviewDecisionRequest(
            operation_id=uuid4(),
            expected_revision=5,
            snapshot_id=sub2.current_review_snapshot_id,
            snapshot_digest=sub2.current_review_snapshot_digest,
            decision="ACCEPT",
            notes="All controls passed and verified",
        ),
    )
    assert reviewed.status == "REVIEWED"

    # 7. Non-owner cannot approve (403)
    with pytest.raises(HTTPException) as exc:
        svc.approve_case(
            lead_principal,
            lead_context,
            case.id,
            ApprovePreauditRequest(
                operation_id=uuid4(),
                expected_revision=6,
                snapshot_id=sub2.current_review_snapshot_id,
                snapshot_digest=sub2.current_review_snapshot_digest,
                approval_notes="Manager cannot approve",
            ),
        )
    assert exc.value.status_code == 403

    # Reviewer cannot approve (403)
    with pytest.raises(HTTPException) as exc:
        svc.approve_case(
            rev_principal,
            rev_context,
            case.id,
            ApprovePreauditRequest(
                operation_id=uuid4(),
                expected_revision=6,
                snapshot_id=sub2.current_review_snapshot_id,
                snapshot_digest=sub2.current_review_snapshot_digest,
                approval_notes="Reviewer cannot approve",
            ),
        )
    assert exc.value.status_code == 403

    # 8. Owner approves -> APPROVED
    approved = svc.approve_case(
        owner_principal,
        owner_context,
        case.id,
        ApprovePreauditRequest(
            operation_id=uuid4(),
            expected_revision=6,
            snapshot_id=sub2.current_review_snapshot_id,
            snapshot_digest=sub2.current_review_snapshot_digest,
            approval_notes="Approved by Tenant Owner",
        ),
    )
    assert approved.status == "APPROVED"
    assert approved.revision == 7

    # 9. Download report
    report_bytes, sha256, c_obj, snap_obj = svc.download_report(
        owner_principal,
        owner_context,
        case.id,
        DownloadPreauditReportRequest(
            expected_revision=7,
            snapshot_id=sub2.current_review_snapshot_id,
        ),
    )
    assert len(report_bytes) > 0
    assert sha256 == hashlib.sha256(report_bytes).hexdigest()


def test_negative_validations(session: Session, preaudit_env):
    """Negative tests covering non-lead actions, stale pins, stale projections, replay across actions/cases."""
    env = preaudit_env
    lead_principal = Principal(user_id=env["mgr_id"], mfa_verified=True)
    lead_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["mgr_id"], role=Role.COMPLIANCE_MANAGER)

    owner_principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    owner_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)

    svc = CustomerPreauditService(session)

    case = svc.create_case(
        lead_principal,
        lead_context,
        CreatePreauditRequest(
            operation_id=uuid4(),
            adoption_id=env["adoption_id"],
            lead_user_id=env["mgr_id"],
            reviewer_user_id=env["owner_id"],
        ),
    )

    # 1. Non-lead (Owner) cannot freeze scope (lead is mgr_id) -> 403
    with pytest.raises(HTTPException) as exc:
        svc.freeze_scope(
            owner_principal,
            owner_context,
            case.id,
            FreezeScopeRequest(operation_id=uuid4(), expected_revision=1),
        )
    assert exc.value.status_code == 403

    # 2. Lead freezes scope
    op_freeze = uuid4()
    frozen = svc.freeze_scope(
        lead_principal,
        lead_context,
        case.id,
        FreezeScopeRequest(operation_id=op_freeze, expected_revision=1),
    )
    assert frozen.status == "FROZEN"

    # 3. Non-lead (Owner) cannot submit review -> 403
    with pytest.raises(HTTPException) as exc:
        svc.submit_review(
            owner_principal,
            owner_context,
            case.id,
            SubmitReviewRequest(operation_id=uuid4(), expected_revision=2),
        )
    assert exc.value.status_code == 403

    # 4. Action replay across actions: replaying op_freeze on submit_review -> 409
    with pytest.raises(HTTPException) as exc:
        svc.submit_review(
            lead_principal,
            lead_context,
            case.id,
            SubmitReviewRequest(operation_id=op_freeze, expected_revision=2),
        )
    assert exc.value.status_code == 409

    # 5. Stale scope pins: simulate adoption/workspace change
    ws = session.query(CustomerDemoWorkspace).filter_by(tenant_id=env["tenant_id"]).one()
    ws.current_revision = 999
    session.commit()

    with pytest.raises(HTTPException) as exc:
        svc.submit_review(
            lead_principal,
            lead_context,
            case.id,
            SubmitReviewRequest(operation_id=uuid4(), expected_revision=2),
        )
    assert exc.value.status_code == 409
    assert "stale" in exc.value.detail.lower()

    # Restore workspace revision
    ws.current_revision = 1
    session.commit()

    # 6. Submit review -> IN_REVIEW
    sub = svc.submit_review(
        lead_principal,
        lead_context,
        case.id,
        SubmitReviewRequest(operation_id=uuid4(), expected_revision=2),
    )
    assert sub.status == "IN_REVIEW"

    # 7. Stale review projection: answers change during review
    answers = session.query(CustomerDemoAnswers).filter_by(tenant_id=env["tenant_id"]).one()
    answers.revision = 999
    session.commit()

    with pytest.raises(HTTPException) as exc:
        svc.review_decision(
            owner_principal,
            owner_context,
            case.id,
            ReviewDecisionRequest(
                operation_id=uuid4(),
                expected_revision=3,
                snapshot_id=sub.current_review_snapshot_id,
                snapshot_digest=sub.current_review_snapshot_digest,
                decision="REQUEST_CHANGES",
                notes="Changes needed due to answer update",
            ),
        )
    assert exc.value.status_code == 409
    assert "stale" in exc.value.detail.lower()


def test_evidence_dependency_lock_race_injection(session: Session, preaudit_env):
    """Deterministic race injection at validation boundary: modifying file or evidence invalidates positive review/approval."""
    env = preaudit_env
    lead_principal = Principal(user_id=env["mgr_id"], mfa_verified=True)
    lead_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["mgr_id"], role=Role.COMPLIANCE_MANAGER)

    another_mgr_id = uuid4()
    now = datetime.now(UTC)
    session.add(
        User(
            id=another_mgr_id,
            oidc_issuer="https://auth.example.com",
            oidc_subject="sub-rev-race",
            email="rev-race@example.com",
            display_name="Reviewer Race",
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        Membership(
            tenant_id=env["tenant_id"],
            user_id=another_mgr_id,
            role=Role.COMPLIANCE_MANAGER,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()

    rev_principal = Principal(user_id=another_mgr_id, mfa_verified=True)
    rev_context = TenantContext(tenant_id=env["tenant_id"], user_id=another_mgr_id, role=Role.COMPLIANCE_MANAGER)

    owner_principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    owner_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)

    svc = CustomerPreauditService(session)

    # Complete all control work with valid passing evidence
    _seed_all_controls_passing(session, env["tenant_id"], env["owner_id"])

    # Create and freeze
    case = svc.create_case(
        lead_principal,
        lead_context,
        CreatePreauditRequest(
            operation_id=uuid4(),
            adoption_id=env["adoption_id"],
            lead_user_id=env["mgr_id"],
            reviewer_user_id=another_mgr_id,
            title="Race Injection Test Case",
        ),
    )
    svc.freeze_scope(lead_principal, lead_context, case.id, FreezeScopeRequest(operation_id=uuid4(), expected_revision=1))
    sub = svc.submit_review(lead_principal, lead_context, case.id, SubmitReviewRequest(operation_id=uuid4(), expected_revision=2))
    assert sub.status == "IN_REVIEW"
    assert len(sub.blockers) == 0

    # Race injection: mutate linked stored file status to QUARANTINED
    sf = session.query(StoredFile).filter_by(tenant_id=env["tenant_id"]).first()
    assert sf is not None
    sf.status = StoredFileStatus.QUARANTINED
    session.commit()

    # Positive review acceptance fails with 409 because evidence dependency is quarantined
    with pytest.raises(HTTPException) as exc:
        svc.review_decision(
            rev_principal,
            rev_context,
            case.id,
            ReviewDecisionRequest(
                operation_id=uuid4(),
                expected_revision=3,
                snapshot_id=sub.current_review_snapshot_id,
                snapshot_digest=sub.current_review_snapshot_digest,
                decision="ACCEPT",
                notes="Attempting acceptance with quarantined file",
            ),
        )
    assert exc.value.status_code == 409

    # Case remains IN_REVIEW at revision 3, no review snapshot or event committed
    c_check = session.query(CustomerPreaudit).filter_by(id=case.id).one()
    assert c_check.status == "IN_REVIEW"
    assert c_check.revision == 3

    # Restore file status to ACTIVE
    sf.status = StoredFileStatus.ACTIVE
    session.commit()

    # Now acceptance succeeds
    reviewed = svc.review_decision(
        rev_principal,
        rev_context,
        case.id,
        ReviewDecisionRequest(
            operation_id=uuid4(),
            expected_revision=3,
            snapshot_id=sub.current_review_snapshot_id,
            snapshot_digest=sub.current_review_snapshot_digest,
            decision="ACCEPT",
            notes="Acceptance with restored active file",
        ),
    )
    assert reviewed.status == "REVIEWED"
    assert reviewed.revision == 4


def test_valid_all_not_applicable_approval_lifecycle(session: Session, enable_preaudit_env):
    """Answers produce NOT_APPLICABLE for all controls; validated N/A scope completes full approval lifecycle."""
    tenant_id = uuid4()
    owner_id = uuid4()
    mgr_id = uuid4()
    reviewer_id = uuid4()
    now = datetime.now(UTC)

    tenant = Tenant(
        id=tenant_id,
        name="All NA Tenant",
        slug=f"tenant-na-{tenant_id}",
        status=TenantStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    session.add(tenant)
    session.add(
        TenantEntitlement(
            tenant_id=tenant_id,
            plan_code="tier_a",
            enabled_modules=["frameworks", "evidence", "tasks", "preaudit", "findings"],
            max_members=100,
            max_storage_bytes=10000000,
            allowed_framework_slugs=["*"],
            effective_from=now - timedelta(days=1),
            effective_until=now + timedelta(days=365),
        )
    )
    for uid, r in [(owner_id, Role.OWNER), (mgr_id, Role.COMPLIANCE_MANAGER), (reviewer_id, Role.COMPLIANCE_MANAGER)]:
        session.add(
            User(
                id=uid,
                oidc_issuer="https://auth.example.com",
                oidc_subject=f"sub-{uid}",
                email=f"{uid}@example.com",
                display_name=f"User {uid}",
                status=UserStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Membership(
                tenant_id=tenant_id,
                user_id=uid,
                role=r,
                status=MembershipStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
        )

    ws = CustomerDemoWorkspace(
        tenant_id=tenant_id,
        current_revision=1,
        selection_revision=1,
        created_at=now,
        updated_at=now,
    )
    session.add(ws)

    # Cloud=False and region=OTHER evaluate all requirements to NOT_APPLICABLE
    answers_data = {"synthetic_wp09_uses_cloud": False, "synthetic_wp09_operating_region": "OTHER"}
    answers = CustomerDemoAnswers(
        tenant_id=tenant_id,
        revision=1,
        company_code="BETA",
        answers=answers_data,
        content_digest=compute_answers_digest("BETA", answers_data),
        actor_id=owner_id,
        created_at=now,
    )
    session.add(answers)

    eval_results = evaluate_bundle(PACK_VERSION_V1_ID, answers_data)
    eval_digest = compute_evaluation_digest(
        answer_digest=answers.content_digest,
        answer_revision=1,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=BUNDLE_V1_DIGEST,
        evaluator_version=EVALUATOR_VERSION,
        results=eval_results,
    )
    evaluation = CustomerDemoEvaluation(
        tenant_id=tenant_id,
        id=uuid4(),
        answer_revision=1,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=BUNDLE_V1_DIGEST,
        evaluator_version=EVALUATOR_VERSION,
        results=eval_results,
        content_digest=eval_digest,
        actor_id=owner_id,
        created_at=now,
    )
    session.add(evaluation)

    adoption = CustomerDemoAdoption(
        tenant_id=tenant_id,
        id=uuid4(),
        evaluation_id=evaluation.id,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=BUNDLE_V1_DIGEST,
        actor_id=owner_id,
        created_at=now,
        selection_revision=1,
    )
    session.add(adoption)
    session.flush()

    work_service = CustomerControlWorkService(session, scanner=MockSuccessfulScanner())
    owner_p = Principal(user_id=owner_id, mfa_verified=True)
    owner_t = TenantContext(tenant_id=tenant_id, user_id=owner_id, role=Role.OWNER)
    work_service.initialize_work(
        owner_p,
        owner_t,
        InitializeWorkRequest(
            operation_id=uuid4(),
            adoption_id=adoption.id,
            expected_selection_revision=1,
            expected_answer_revision=1,
        ),
        request_id="req-init-na",
    )
    session.commit()

    lead_p = Principal(user_id=mgr_id, mfa_verified=True)
    lead_t = TenantContext(tenant_id=tenant_id, user_id=mgr_id, role=Role.COMPLIANCE_MANAGER)
    rev_p = Principal(user_id=reviewer_id, mfa_verified=True)
    rev_t = TenantContext(tenant_id=tenant_id, user_id=reviewer_id, role=Role.COMPLIANCE_MANAGER)

    svc = CustomerPreauditService(session)

    # 1. Create case
    case = svc.create_case(
        lead_p,
        lead_t,
        CreatePreauditRequest(
            operation_id=uuid4(),
            adoption_id=adoption.id,
            lead_user_id=mgr_id,
            reviewer_user_id=reviewer_id,
            title="All N/A Pre-Audit Journey",
        ),
    )
    assert case.status == "DRAFT"

    # 2. Freeze scope
    frozen = svc.freeze_scope(lead_p, lead_t, case.id, FreezeScopeRequest(operation_id=uuid4(), expected_revision=1))
    assert frozen.status == "FROZEN"

    # 3. Submit review: validated NOT_APPLICABLE controls have no blockers
    sub = svc.submit_review(lead_p, lead_t, case.id, SubmitReviewRequest(operation_id=uuid4(), expected_revision=2))
    assert sub.status == "IN_REVIEW"
    assert len(sub.blockers) == 0

    # 4. Independent reviewer accepts
    reviewed = svc.review_decision(
        rev_p,
        rev_t,
        case.id,
        ReviewDecisionRequest(
            operation_id=uuid4(),
            expected_revision=3,
            snapshot_id=sub.current_review_snapshot_id,
            snapshot_digest=sub.current_review_snapshot_digest,
            decision="ACCEPT",
            notes="All N/A requirements verified and accepted",
        ),
    )
    assert reviewed.status == "REVIEWED"

    # 5. Owner approves
    approved = svc.approve_case(
        owner_p,
        owner_t,
        case.id,
        ApprovePreauditRequest(
            operation_id=uuid4(),
            expected_revision=4,
            snapshot_id=sub.current_review_snapshot_id,
            snapshot_digest=sub.current_review_snapshot_digest,
            approval_notes="Approved all-NA compliance profile",
        ),
    )
    assert approved.status == "APPROVED"
    assert approved.revision == 5

    # 6. Report download succeeds
    report_bytes, sha256, c_obj, snap_obj = svc.download_report(
        owner_p,
        owner_t,
        case.id,
        DownloadPreauditReportRequest(
            expected_revision=5,
            snapshot_id=sub.current_review_snapshot_id,
        ),
    )
    assert len(report_bytes) > 0
    assert sha256 == hashlib.sha256(report_bytes).hexdigest()


def test_replay_receipt_semantics_and_head_advancement(session: Session, preaudit_env):
    """Replay receipt semantics: replayed=True on exact replay; preserves event/snapshot identifiers across head advancements."""
    env = preaudit_env
    lead_principal = Principal(user_id=env["mgr_id"], mfa_verified=True)
    lead_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["mgr_id"], role=Role.COMPLIANCE_MANAGER)

    svc = CustomerPreauditService(session)

    op_create = uuid4()
    req_create = CreatePreauditRequest(
        operation_id=op_create,
        adoption_id=env["adoption_id"],
        lead_user_id=env["mgr_id"],
        reviewer_user_id=env["owner_id"],
        title="Replay Receipt Test",
    )

    # 1. Fresh create -> replayed=False
    c1 = svc.create_case(lead_principal, lead_context, req_create)
    assert c1.replayed is False
    assert c1.applied_event_id is not None
    assert c1.applied_revision == 1

    # 2. Exact replay -> replayed=True with matching receipt
    c2 = svc.create_case(lead_principal, lead_context, req_create)
    assert c2.replayed is True
    assert c2.applied_event_id == c1.applied_event_id
    assert c2.applied_revision == 1
    assert c2.id == c1.id

    # 3. Fresh freeze -> replayed=False
    op_freeze = uuid4()
    req_freeze = FreezeScopeRequest(operation_id=op_freeze, expected_revision=1)
    f1 = svc.freeze_scope(lead_principal, lead_context, c1.id, req_freeze)
    assert f1.replayed is False
    assert f1.applied_event_id is not None
    assert f1.applied_revision == 2

    # 4. Exact freeze replay -> replayed=True
    f2 = svc.freeze_scope(lead_principal, lead_context, c1.id, req_freeze)
    assert f2.replayed is True
    assert f2.applied_event_id == f1.applied_event_id
    assert f2.applied_revision == 2

    # 5. Advance head by submitting review
    op_submit = uuid4()
    req_submit = SubmitReviewRequest(operation_id=op_submit, expected_revision=2)
    s1 = svc.submit_review(lead_principal, lead_context, c1.id, req_submit)
    assert s1.replayed is False
    assert s1.revision == 3

    # 6. Replay older freeze operation against advanced head
    # Still returns replayed=True and original applied_revision=2, while case current revision reflects head advancement (3)
    f3 = svc.freeze_scope(lead_principal, lead_context, c1.id, req_freeze)
    assert f3.replayed is True
    assert f3.applied_event_id == f1.applied_event_id
    assert f3.applied_revision == 2
    assert f3.revision == 3
