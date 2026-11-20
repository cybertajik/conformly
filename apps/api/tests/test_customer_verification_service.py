"""Tests for CustomerVerificationService: synthetic issuance, validity, CAS, tamper protection, suspension, revocation, and atomic supersession."""

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
    CreatePreauditRequest,
    FreezeScopeRequest,
    ReviewDecisionRequest,
    SubmitReviewRequest,
)
from conformly.customer_demo.preaudit_service import CustomerPreauditService
from conformly.customer_demo.verification_crypto import (
    compute_valid_through,
    decrypt_verification_payload,
)
from conformly.customer_demo.verification_models import (
    CustomerReadinessVerification,
    CustomerReadinessVerificationEvent,
)
from conformly.customer_demo.verification_schemas import (
    CorrectVerificationRequest,
    IssueVerificationRequest,
    ReconcileVerificationRequest,
    RevokeVerificationRequest,
    SupersedeVerificationRequest,
    SuspendVerificationRequest,
)
from conformly.customer_demo.verification_service import CustomerVerificationService, CustomerDemoDatabaseAdmissionError, verify_verification_database_connection
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


class MockSuccessfulScanner:
    def scan(self, data: bytes, filename: str) -> None:
        pass


@pytest.fixture(autouse=True)
def enable_verification_env(monkeypatch):
    """Ensure customer demo, preaudit, and readiness verification features are enabled for tests."""
    monkeypatch.setenv("CONFORMLY_ENABLE_CUSTOMER_DEMO", "true")
    monkeypatch.setenv("CONFORMLY_ENABLE_CUSTOMER_PREAUDIT", "true")
    monkeypatch.setenv("CONFORMLY_ENABLE_CUSTOMER_READINESS_VERIFICATION", "true")
    monkeypatch.setenv("CONFORMLY_ENVIRONMENT", "test")
    from conformly.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def verification_test_env(session: Session):
    """Seed tenant, users, adoption, and initial control work matching pre-audit fixtures."""
    tenant_id = uuid4()
    owner_id = uuid4()
    mgr_id = uuid4()
    rev_id = uuid4()
    now = datetime.now(UTC)

    tenant = Tenant(
        id=tenant_id,
        name="Verification Test Corp",
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
            id=rev_id,
            oidc_issuer="https://auth.example.com",
            oidc_subject="sub-rev",
            email="rev@example.com",
            display_name="Charlie Reviewer",
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
            user_id=rev_id,
            role=Role.COMPLIANCE_MANAGER,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
    ]
    session.add_all(memberships)

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
        "rev_id": rev_id,
        "adoption_id": adoption.id,
    }

    return {
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "mgr_id": mgr_id,
        "rev_id": rev_id,
        "adoption_id": adoption_id,
    }


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


def _setup_approved_case(session: Session, env: dict) -> tuple[CustomerPreaudit, CustomerPreauditSnapshot]:
    """Helper to take a pre-audit case from DRAFT to APPROVED with passing evidence."""
    lead_principal = Principal(user_id=env["mgr_id"], mfa_verified=True)
    lead_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["mgr_id"], role=Role.COMPLIANCE_MANAGER)

    rev_principal = Principal(user_id=env["rev_id"], mfa_verified=True)
    rev_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["rev_id"], role=Role.COMPLIANCE_MANAGER)

    owner_principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    owner_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)

    _seed_all_controls_passing(session, env["tenant_id"], env["owner_id"])

    preaudit_svc = CustomerPreauditService(session)

    # 1. Create case
    case = preaudit_svc.create_case(
        lead_principal,
        lead_context,
        CreatePreauditRequest(
            operation_id=uuid4(),
            adoption_id=env["adoption_id"],
            lead_user_id=env["mgr_id"],
            reviewer_user_id=env["rev_id"],
            title="Readiness Verification Source Case",
        ),
    )

    # 2. Freeze scope
    preaudit_svc.freeze_scope(
        lead_principal,
        lead_context,
        case.id,
        FreezeScopeRequest(operation_id=uuid4(), expected_revision=1),
    )

    # 3. Submit review
    sub = preaudit_svc.submit_review(
        lead_principal,
        lead_context,
        case.id,
        SubmitReviewRequest(operation_id=uuid4(), expected_revision=2, submission_notes="All PASS"),
    )
    assert len(sub.blockers) == 0

    # 4. Independent reviewer accepts
    reviewed = preaudit_svc.review_decision(
        rev_principal,
        rev_context,
        case.id,
        ReviewDecisionRequest(
            operation_id=uuid4(),
            expected_revision=3,
            snapshot_id=sub.current_review_snapshot_id,
            snapshot_digest=sub.current_review_snapshot_digest,
            decision="ACCEPT",
            notes="Independent review accepted",
        ),
    )
    assert reviewed.status == "REVIEWED"

    # 5. Owner approves
    approved = preaudit_svc.approve_case(
        owner_principal,
        owner_context,
        case.id,
        ApprovePreauditRequest(
            operation_id=uuid4(),
            expected_revision=4,
            snapshot_id=sub.current_review_snapshot_id,
            snapshot_digest=sub.current_review_snapshot_digest,
            approval_notes="Owner formal approval granted",
        ),
    )
    assert approved.status == "APPROVED"

    session.commit()
    session_case = session.query(CustomerPreaudit).filter_by(id=case.id).scalar()
    session_snap = session.query(CustomerPreauditSnapshot).filter_by(id=session_case.current_review_snapshot_id).scalar()
    return session_case, session_snap


def test_positive_synthetic_verification_lifecycle(session: Session, verification_test_env):
    """Full positive lifecycle: issue, reload, allowlisted projection, correction, suspend, revoke."""
    env = verification_test_env
    case, snapshot = _setup_approved_case(session, env)

    owner_principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    owner_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)

    service = CustomerVerificationService(session)

    issue_op = uuid4()
    req = IssueVerificationRequest(
        operation_id=issue_op,
        preaudit_id=case.id,
        expected_case_revision=case.revision,
        snapshot_id=snapshot.id,
        snapshot_digest=snapshot.digest,
        limitations=["Internal assessment only", "No production telemetry evaluated"],
        notes="Synthetic test result issued",
    )

    # 1. Issue verification
    v_res = service.issue_verification(owner_principal, owner_context, req)
    assert v_res.status == "ACTIVE"
    assert v_res.effective_status == "ACTIVE"
    assert v_res.revision == 1
    assert v_res.replayed is False
    assert v_res.preaudit_id == case.id
    assert v_res.snapshot_id == snapshot.id
    assert v_res.synthetic_marker == "PRIVATE SYNTHETIC INTERNAL TEST RESULT"
    assert len(v_res.limitations) == 2

    # 2. Exact replay returns recorded outcome
    v_replay = service.issue_verification(owner_principal, owner_context, req)
    assert v_replay.replayed is True
    assert v_replay.id == v_res.id

    # 3. Altered request with same op ID raises 409
    altered_req = req.model_copy(update={"notes": "Altered notes"})
    with pytest.raises(HTTPException) as exc_info:
        service.issue_verification(owner_principal, owner_context, altered_req)
    assert exc_info.value.status_code == 409

    # 4. List verifications
    v_list = service.list_verifications(owner_principal, owner_context)
    assert v_list.total == 1
    assert len(v_list.verifications) == 1
    assert v_list.verifications[0].id == v_res.id
    assert v_list.verifications[0].status == "ACTIVE"

    # 5. Detail retrieval and payload decrypt
    detail = service.get_verification(owner_principal, owner_context, v_res.id)
    assert detail.id == v_res.id
    assert detail.issuer_user_id == env["owner_id"]
    assert detail.reviewer_user_id == env["rev_id"]

    # 6. Allowlisted private preview projection
    proj = service.get_verification_projection(owner_principal, owner_context, v_res.id)
    assert proj.verification_id == v_res.id
    assert proj.status == "ACTIVE"
    assert proj.effective_status == "ACTIVE"
    assert proj.controls_count > 0
    assert proj.synthetic_marker == "PRIVATE SYNTHETIC INTERNAL TEST RESULT"
    # Ensure sensitive IDs are NOT in projection schema
    assert not hasattr(proj, "tenant_id")
    assert not hasattr(proj, "user_id")
    assert not hasattr(proj, "raw_snapshot")

    # 7. Explanatory correction (append-only event, status remains ACTIVE, revision advances)
    cor_op = uuid4()
    cor_res = service.correct_verification(
        owner_principal,
        owner_context,
        v_res.id,
        CorrectVerificationRequest(
            operation_id=cor_op,
            expected_revision=1,
            correction_notes="Clarifying testing parameters for internal audit team",
        ),
    )
    assert cor_res.status == "ACTIVE"
    assert cor_res.revision == 2

    # 8. Suspend verification
    susp_op = uuid4()
    susp_res = service.suspend_verification(
        owner_principal,
        owner_context,
        v_res.id,
        SuspendVerificationRequest(
            operation_id=susp_op,
            expected_revision=2,
            reason="Investigating configuration discrepancy",
        ),
    )
    assert susp_res.status == "SUSPENDED"
    assert susp_res.revision == 3

    # Cannot suspend an already suspended verification
    with pytest.raises(HTTPException) as exc_info:
        service.suspend_verification(
            owner_principal,
            owner_context,
            v_res.id,
            SuspendVerificationRequest(operation_id=uuid4(), expected_revision=3, reason="Duplicate suspend"),
        )
    assert exc_info.value.status_code == 409

    # 9. Revoke verification (terminal state)
    rev_op = uuid4()
    rev_res = service.revoke_verification(
        owner_principal,
        owner_context,
        v_res.id,
        RevokeVerificationRequest(
            operation_id=rev_op,
            expected_revision=3,
            reason="Superseded by comprehensive external audit",
        ),
    )
    assert rev_res.status == "REVOKED"
    assert rev_res.revision == 4

    # Terminal state: cannot revoke again
    with pytest.raises(HTTPException) as exc_info:
        service.revoke_verification(
            owner_principal,
            owner_context,
            v_res.id,
            RevokeVerificationRequest(operation_id=uuid4(), expected_revision=4, reason="Another revoke"),
        )
    assert exc_info.value.status_code == 409

    # 10. History verification
    history = service.get_verification_history(owner_principal, owner_context, v_res.id)
    assert len(history.events) == 4
    assert [e.event_type for e in history.events] == ["ISSUED", "CORRECTED", "SUSPENDED", "REVOKED"]


def test_12_calendar_month_validity_and_leap_year_clamp(session: Session, verification_test_env):
    """Ensure exact 12-calendar-month validity, Feb 29 leap clamping, and boundary expiry."""
    env = verification_test_env
    case, snapshot = _setup_approved_case(session, env)

    owner_principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    owner_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)

    # Leap year issuance: 2024-02-29 12:00:00 UTC
    leap_issue = datetime(2024, 2, 29, 12, 0, 0, tzinfo=UTC)
    service_leap = CustomerVerificationService(session, clock_override=leap_issue)

    res = service_leap.issue_verification(
        owner_principal,
        owner_context,
        IssueVerificationRequest(
            operation_id=uuid4(),
            preaudit_id=case.id,
            expected_case_revision=case.revision,
            snapshot_id=snapshot.id,
            snapshot_digest=snapshot.digest,
        ),
    )
    # Feb 29 in leap year clamped to Feb 28 in non-leap year 2025
    assert res.issued_at == leap_issue
    assert res.valid_through == datetime(2025, 2, 28, 12, 0, 0, tzinfo=UTC)

    # 1 second before expiration: still ACTIVE
    service_before = CustomerVerificationService(
        session, clock_override=res.valid_through - timedelta(seconds=1)
    )
    detail_before = service_before.get_verification(owner_principal, owner_context, res.id)
    assert detail_before.status == "ACTIVE"
    assert detail_before.effective_status == "ACTIVE"

    # At valid_through boundary: effectively EXPIRED
    service_at = CustomerVerificationService(session, clock_override=res.valid_through)
    detail_at = service_at.get_verification(owner_principal, owner_context, res.id)
    assert detail_at.status == "ACTIVE"  # Persisted status untouched on GET
    assert detail_at.effective_status == "EXPIRED"
    assert "elapsed" in (detail_at.effective_reason or "").lower()


def test_reconcile_lifecycle_idempotency(session: Session, verification_test_env):
    """POST /reconcile deterministic state reconciliation transitions due records."""
    env = verification_test_env
    case, snapshot = _setup_approved_case(session, env)

    owner_principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    owner_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)

    issue_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    service = CustomerVerificationService(session, clock_override=issue_time)

    res = service.issue_verification(
        owner_principal,
        owner_context,
        IssueVerificationRequest(
            operation_id=uuid4(),
            preaudit_id=case.id,
            expected_case_revision=case.revision,
            snapshot_id=snapshot.id,
            snapshot_digest=snapshot.digest,
        ),
    )
    assert res.status == "ACTIVE"

    # Reconcile after expiry (2027-01-02)
    after_expiry = datetime(2027, 1, 2, 12, 0, 0, tzinfo=UTC)
    service.clock_override = after_expiry
    reconcile_res = service.reconcile_lifecycle(
        owner_principal,
        owner_context,
        ReconcileVerificationRequest(),
    )
    assert reconcile_res["reconciled_count"] == 1
    assert reconcile_res["results"][0]["new_status"] == "EXPIRED"

    # Verify persisted status in database is now EXPIRED
    detail = service.get_verification(owner_principal, owner_context, res.id)
    assert detail.status == "EXPIRED"
    assert detail.revision == 2

    # Reconciling again is idempotent (0 transitioned)
    reconcile_again = service.reconcile_lifecycle(
        owner_principal,
        owner_context,
        ReconcileVerificationRequest(),
    )
    assert reconcile_again["reconciled_count"] == 0


def test_atomic_supersession_workflow(session: Session, verification_test_env):
    """Atomic supersession links old record to replacement and preserves history."""
    env = verification_test_env
    case1, snap1 = _setup_approved_case(session, env)

    owner_principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    owner_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)

    service = CustomerVerificationService(session)

    # 1. Issue first verification
    v1 = service.issue_verification(
        owner_principal,
        owner_context,
        IssueVerificationRequest(
            operation_id=uuid4(),
            preaudit_id=case1.id,
            expected_case_revision=case1.revision,
            snapshot_id=snap1.id,
            snapshot_digest=snap1.digest,
        ),
    )
    assert v1.status == "ACTIVE"

    # 2. Setup second approved case with fresh snapshot
    lead_principal = Principal(user_id=env["mgr_id"], mfa_verified=True)
    lead_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["mgr_id"], role=Role.COMPLIANCE_MANAGER)
    rev_principal = Principal(user_id=env["rev_id"], mfa_verified=True)
    rev_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["rev_id"], role=Role.COMPLIANCE_MANAGER)

    preaudit_svc = CustomerPreauditService(session)
    case2 = preaudit_svc.create_case(
        lead_principal,
        lead_context,
        CreatePreauditRequest(
            operation_id=uuid4(),
            adoption_id=env["adoption_id"],
            lead_user_id=env["mgr_id"],
            reviewer_user_id=env["rev_id"],
            title="Replacement Pre-Audit Journey",
        ),
    )
    preaudit_svc.freeze_scope(
        lead_principal, lead_context, case2.id, FreezeScopeRequest(operation_id=uuid4(), expected_revision=1)
    )
    sub2 = preaudit_svc.submit_review(
        lead_principal,
        lead_context,
        case2.id,
        SubmitReviewRequest(operation_id=uuid4(), expected_revision=2, submission_notes="Second review"),
    )
    preaudit_svc.review_decision(
        rev_principal,
        rev_context,
        case2.id,
        ReviewDecisionRequest(
            operation_id=uuid4(),
            expected_revision=3,
            snapshot_id=sub2.current_review_snapshot_id,
            snapshot_digest=sub2.current_review_snapshot_digest,
            decision="ACCEPT",
            notes="Second review accepted",
        ),
    )
    preaudit_svc.approve_case(
        owner_principal,
        owner_context,
        case2.id,
        ApprovePreauditRequest(
            operation_id=uuid4(),
            expected_revision=4,
            snapshot_id=sub2.current_review_snapshot_id,
            snapshot_digest=sub2.current_review_snapshot_digest,
            approval_notes="Approved replacement",
        ),
    )
    snap2 = session.query(CustomerPreauditSnapshot).filter_by(id=sub2.current_review_snapshot_id).scalar()

    # 3. Supersede v1 with case2/snap2
    sup_op = uuid4()
    v2 = service.supersede_verification(
        owner_principal,
        owner_context,
        v1.id,
        SupersedeVerificationRequest(
            operation_id=sup_op,
            expected_revision=1,
            new_preaudit_id=case2.id,
            new_expected_case_revision=5,
            new_snapshot_id=snap2.id,
            new_snapshot_digest=snap2.digest,
            notes="Upgraded to replacement audit scope",
        ),
    )
    assert v2.status == "ACTIVE"
    assert v2.supersedes_id == v1.id

    # Verify old verification status and linkage
    old_detail = service.get_verification(owner_principal, owner_context, v1.id)
    assert old_detail.status == "SUPERSEDED"
    assert old_detail.superseded_by_id == v2.id
    assert old_detail.revision == 2

    # Cannot supersede an already superseded verification
    with pytest.raises(HTTPException) as exc_info:
        service.supersede_verification(
            owner_principal,
            owner_context,
            v1.id,
            SupersedeVerificationRequest(
                operation_id=uuid4(),
                expected_revision=2,
                new_preaudit_id=case2.id,
                new_expected_case_revision=5,
                new_snapshot_id=snap2.id,
                new_snapshot_digest=snap2.digest,
            ),
        )
    assert exc_info.value.status_code == 409


def test_negative_validations_and_role_security(session: Session, verification_test_env):
    """Negative tests: reviewer self-issue, non-Owner, tampered digest, feature OFF."""
    env = verification_test_env
    case, snapshot = _setup_approved_case(session, env)

    service = CustomerVerificationService(session)

    # 1. Reviewer self-issue is forbidden (even if reviewer is an Owner)
    from conformly.identity.models import Membership
    rev_mem = session.query(Membership).filter_by(tenant_id=env["tenant_id"], user_id=env["rev_id"]).first()
    rev_mem.role = Role.OWNER
    session.commit()

    rev_principal = Principal(user_id=env["rev_id"], mfa_verified=True)
    rev_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["rev_id"], role=Role.OWNER)
    with pytest.raises(HTTPException) as exc_info:
        service.issue_verification(
            rev_principal,
            rev_context,
            IssueVerificationRequest(
                operation_id=uuid4(),
                preaudit_id=case.id,
                expected_case_revision=case.revision,
                snapshot_id=snapshot.id,
                snapshot_digest=snapshot.digest,
            ),
        )
    assert exc_info.value.status_code == 403
    assert "reviewer" in exc_info.value.detail.lower()

    # 2. Non-Owner cannot issue
    lead_principal = Principal(user_id=env["mgr_id"], mfa_verified=True)
    lead_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["mgr_id"], role=Role.COMPLIANCE_MANAGER)
    with pytest.raises(HTTPException) as exc_info:
        service.issue_verification(
            lead_principal,
            lead_context,
            IssueVerificationRequest(
                operation_id=uuid4(),
                preaudit_id=case.id,
                expected_case_revision=case.revision,
                snapshot_id=snapshot.id,
                snapshot_digest=snapshot.digest,
            ),
        )
    assert exc_info.value.status_code == 403

    # 3. Snapshot digest mismatch
    owner_principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    owner_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)
    with pytest.raises(HTTPException) as exc_info:
        service.issue_verification(
            owner_principal,
            owner_context,
            IssueVerificationRequest(
                operation_id=uuid4(),
                preaudit_id=case.id,
                expected_case_revision=case.revision,
                snapshot_id=snapshot.id,
                snapshot_digest="f" * 64,
            ),
        )
    assert exc_info.value.status_code == 409

    # 4. Feature OFF denies access with 404
    with patch("conformly.customer_demo.verification_service.get_settings") as mock_settings:
        cfg = mock_settings.return_value
        cfg.enable_customer_readiness_verification = False
        with pytest.raises(HTTPException) as exc_info:
            service.issue_verification(
                owner_principal,
                owner_context,
                IssueVerificationRequest(
                    operation_id=uuid4(),
                    preaudit_id=case.id,
                    expected_case_revision=case.revision,
                    snapshot_id=snapshot.id,
                    snapshot_digest=snapshot.digest,
                ),
            )
        assert exc_info.value.status_code == 404


def test_suspended_results_expire_at_12_calendar_months_and_reconcile_idempotent(session: Session, verification_test_env):
    """Suspended verification must expire when validity window elapses, and reconcile is idempotent."""
    env = verification_test_env
    case, snapshot = _setup_approved_case(session, env)

    owner_principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    owner_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)

    issue_time = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
    service = CustomerVerificationService(session, clock_override=issue_time)

    v_res = service.issue_verification(
        owner_principal,
        owner_context,
        IssueVerificationRequest(
            operation_id=uuid4(),
            preaudit_id=case.id,
            expected_case_revision=case.revision,
            snapshot_id=snapshot.id,
            snapshot_digest=snapshot.digest,
        ),
    )
    assert v_res.status == "ACTIVE"

    # Suspend it
    susp_time = datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC)
    service.clock_override = susp_time
    susp_res = service.suspend_verification(
        owner_principal,
        owner_context,
        v_res.id,
        SuspendVerificationRequest(
            operation_id=uuid4(),
            expected_revision=1,
            reason="Investigation pending",
        ),
    )
    assert susp_res.status == "SUSPENDED"

    # Advance clock past 12 calendar months (2027-03-02)
    past_expiry = datetime(2027, 3, 2, 10, 0, 0, tzinfo=UTC)
    service.clock_override = past_expiry

    reconcile_res = service.reconcile_lifecycle(
        owner_principal,
        owner_context,
        ReconcileVerificationRequest(),
    )
    assert reconcile_res["reconciled_count"] == 1
    assert reconcile_res["results"][0]["new_status"] == "EXPIRED"

    # Verify persisted status is now EXPIRED
    detail = service.get_verification(owner_principal, owner_context, v_res.id)
    assert detail.status == "EXPIRED"
    assert detail.effective_status == "EXPIRED"

    # Idempotent re-reconcile
    reconcile_again = service.reconcile_lifecycle(
        owner_principal,
        owner_context,
        ReconcileVerificationRequest(),
    )
    assert reconcile_again["reconciled_count"] == 0


def _setup_approved_mixed_case(session: Session, env: dict, approval_notes: str | None = "Owner approves for production") -> tuple[CustomerPreaudit, CustomerPreauditSnapshot, CustomerPreauditEvent, CustomerPreauditEvent, dict]:
    """Helper to take a pre-audit case from DRAFT to APPROVED with genuine mixed PASS and NOT_APPLICABLE controls on an isolated tenant."""
    now = datetime.now(UTC)
    tenant_id = uuid4()
    owner_id = uuid4()
    mgr_id = uuid4()
    rev_id = uuid4()

    tenant = Tenant(
        id=tenant_id,
        name="Mixed Verification Tenant",
        slug=f"tenant-mixed-{tenant_id}",
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
    for uid, r in [(owner_id, Role.OWNER), (mgr_id, Role.COMPLIANCE_MANAGER), (rev_id, Role.COMPLIANCE_MANAGER)]:
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

    # Answers: uses_cloud=True, operating_region=OTHER -> 1 APPLICABLE, 1 NOT_APPLICABLE
    answers_data = {"synthetic_wp09_uses_cloud": True, "synthetic_wp09_operating_region": "OTHER"}
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
        request_id="req-init-mixed",
    )
    session.commit()

    # Seed evidence only on the APPLICABLE work item
    works = session.query(CustomerControlWork).filter_by(tenant_id=tenant_id, adoption_id=adoption.id).all()
    assess_svc = CustomerAssessmentService(session)

    for w in works:
        bundle = get_bundle_by_version_id(PACK_VERSION_V1_ID)
        req = next(r for r in bundle["requirements"] if r["control_version_id"] == str(w.control_version_id))
        req_id = req["id"]
        req_res = next(r for r in eval_results if r["requirement_id"] == req_id)

        if req_res["result"] == "APPLICABLE":
            file_id = uuid4()
            content = b"Verified evidence for cloud control compliance."
            sf = StoredFile(
                id=file_id,
                tenant_id=tenant_id,
                original_filename="cloud_audit.txt",
                content_type="text/plain",
                plaintext_size_bytes=len(content),
                ciphertext_size_bytes=len(content) + 28,
                storage_backend="local",
                encryption_algorithm="AES-256-GCM",
                key_version="v1",
                wrapped_dek_nonce="nonce123456",
                wrapped_dek="wrappeddek123456",
                ciphertext_nonce="nonce123456",
                object_key=f"tenants/{tenant_id}/files/{file_id}/cloud_audit.txt",
                classification=DataClassification.RESTRICTED.value,
                status=StoredFileStatus.ACTIVE,
                ciphertext_sha256=hashlib.sha256(b"cipher").hexdigest(),
                plaintext_sha256=hashlib.sha256(content).hexdigest(),
                created_by_user_id=owner_id,
                created_at=now,
            )
            session.add(sf)
            session.commit()

            with patch("conformly.customer_demo.work_service.StorageService") as MockStorage:
                instance = MockStorage.return_value
                instance.download_file.return_value = (sf, content)
                ev_receipt = work_service.create_evidence(
                    owner_p,
                    owner_t,
                    w.id,
                    CreateEvidenceRequest(
                        operation_id=uuid4(),
                        expected_selection_revision=1,
                        expected_answer_revision=1,
                        expected_work_version=w.version,
                        file_id=sf.id,
                        rationale="Cloud compliance evidence",
                    ),
                    request_id=f"req-pin-mixed-{w.id}",
                )
                link_id = ev_receipt.current_work.links[0].id
                session.refresh(w)

                work_service.create_review(
                    owner_p,
                    owner_t,
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
                    request_id=f"req-rev-mixed-{w.id}",
                )
                session.refresh(w)

                proc = assess_svc.get_procedure(owner_p, owner_t, w.id)
                assess_svc.record_assessment(
                    owner_p,
                    owner_t,
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
                    request_id=f"req-assess-mixed-{w.id}",
                )
                session.commit()

    lead_principal = Principal(user_id=mgr_id, mfa_verified=True)
    lead_context = TenantContext(tenant_id=tenant_id, user_id=mgr_id, role=Role.COMPLIANCE_MANAGER)
    rev_principal = Principal(user_id=rev_id, mfa_verified=True)
    rev_context = TenantContext(tenant_id=tenant_id, user_id=rev_id, role=Role.COMPLIANCE_MANAGER)

    preaudit_svc = CustomerPreauditService(session)

    # 1. Create case
    case = preaudit_svc.create_case(
        lead_principal,
        lead_context,
        CreatePreauditRequest(
            operation_id=uuid4(),
            adoption_id=adoption.id,
            lead_user_id=mgr_id,
            reviewer_user_id=rev_id,
            title="Readiness Mixed Case",
        ),
    )

    # 2. Freeze scope
    preaudit_svc.freeze_scope(
        lead_principal,
        lead_context,
        case.id,
        FreezeScopeRequest(operation_id=uuid4(), expected_revision=1),
    )

    # 3. Submit review with distinct lead notes
    sub = preaudit_svc.submit_review(
        lead_principal,
        lead_context,
        case.id,
        SubmitReviewRequest(
            operation_id=uuid4(),
            expected_revision=2,
            submission_notes="Lead notes: All ready for review",
        ),
    )
    assert len(sub.blockers) == 0

    # 4. Independent reviewer accepts
    reviewed = preaudit_svc.review_decision(
        rev_principal,
        rev_context,
        case.id,
        ReviewDecisionRequest(
            operation_id=uuid4(),
            expected_revision=3,
            snapshot_id=sub.current_review_snapshot_id,
            snapshot_digest=sub.current_review_snapshot_digest,
            decision="ACCEPT",
            notes="Independent review accepted",
        ),
    )
    assert reviewed.status == "REVIEWED"

    review_event = session.query(CustomerPreauditEvent).filter_by(
        tenant_id=tenant_id,
        preaudit_id=case.id,
        event_type="REVIEWED",
    ).first()

    # 5. Owner approves with distinct approval notes
    approved = preaudit_svc.approve_case(
        owner_p,
        owner_t,
        case.id,
        ApprovePreauditRequest(
            operation_id=uuid4(),
            expected_revision=4,
            snapshot_id=sub.current_review_snapshot_id,
            snapshot_digest=sub.current_review_snapshot_digest,
            approval_notes=approval_notes,
        ),
    )
    assert approved.status == "APPROVED"

    approval_event = session.query(CustomerPreauditEvent).filter_by(
        tenant_id=tenant_id,
        preaudit_id=case.id,
        event_type="APPROVED",
    ).first()

    session.commit()

    session_case = session.query(CustomerPreaudit).filter_by(id=case.id).scalar()
    session_snap = session.query(CustomerPreauditSnapshot).filter_by(id=session_case.current_review_snapshot_id).scalar()

    env_mixed = {
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "mgr_id": mgr_id,
        "rev_id": rev_id,
        "adoption_id": adoption.id,
    }

    return session_case, session_snap, review_event, approval_event, env_mixed

def test_real_provenance_freeze_and_projection(session: Session, verification_test_env):
    """Provenance freeze captures genuine reviewer decisions, evidence pins, mixed N/A counts, and allowlisted projection."""
    env = verification_test_env
    case, snapshot, rev_event, app_event, env = _setup_approved_mixed_case(session, env)

    owner_principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    owner_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)

    service = CustomerVerificationService(session)
    v_res = service.issue_verification(
        owner_principal,
        owner_context,
        IssueVerificationRequest(
            operation_id=uuid4(),
            preaudit_id=case.id,
            expected_case_revision=case.revision,
            snapshot_id=snapshot.id,
            snapshot_digest=snapshot.digest,
            limitations=["Testing only"],
        ),
    )

    # 1. Inspect raw stored record and decrypted payload
    raw_v = session.query(CustomerReadinessVerification).filter_by(
        tenant_id=env["tenant_id"],
        id=v_res.id,
    ).one()

    decrypted = decrypt_verification_payload(
        service.codec,
        env["tenant_id"],
        v_res.id,
        raw_v.payload_encrypted,
        raw_v.digest,
    )

    # Reviewer decision provenance
    assert decrypted["review_event_id"] == str(rev_event.id)
    assert decrypted["reviewer_decision"] == "ACCEPT"
    assert decrypted["reviewer_decision_notes"] == "Independent review accepted"
    # Never substitute lead submission notes!
    assert decrypted["reviewer_decision_notes"] != "Lead notes: All ready for review"

    # Approver provenance
    assert decrypted["approval_event_id"] == str(app_event.id)
    assert decrypted["owner_approval_notes"] == "Owner approves for production"

    # Evidence pins
    assert len(decrypted["evidence_pins"]) > 0
    pin = decrypted["evidence_pins"][0]
    assert pin["link_id"] is not None
    assert pin["evidence_id"] is not None
    assert pin["revision_number"] >= 1
    assert pin["revision_digest"] is not None
    assert pin["file_hash"] is not None
    assert pin["latest_review_event_id"] is not None

    # Mixed N/A counts derived from real approved control states
    assert decrypted["controls_count"] == 2
    assert decrypted["covered_count"] == 1
    assert decrypted["exempt_count"] == 1
    assert decrypted["not_applicable_count"] == 1
    assert decrypted["scope_summary"]["controls_count"] == 2
    assert decrypted["scope_summary"]["covered_count"] == 1
    assert decrypted["scope_summary"]["exempt_count"] == 1
    assert decrypted["scope_summary"]["not_applicable_count"] == 1

    # 2. Allowlisted private projection reflects mixed N/A counts without leaking secrets
    proj = service.get_verification_projection(owner_principal, owner_context, v_res.id)
    assert proj.verification_id == v_res.id
    assert proj.status == "ACTIVE"
    assert proj.controls_count == 2
    assert proj.scope_summary["covered_count"] == 1
    assert proj.scope_summary["exempt_count"] == 1
    assert proj.framework_display_name is not None
    assert proj.public_disclosure_statement != ""

    # 3. Reproducible historical read
    reloaded = service.get_verification(owner_principal, owner_context, v_res.id)
    assert reloaded.id == v_res.id
    assert reloaded.status == "ACTIVE"
    assert reloaded.revision == 1


def test_provenance_freeze_fails_closed_on_missing_or_corrupt_proof(session: Session, verification_test_env):
    """Integrity failure: corrupt ciphertext or missing required decision events fail closed."""
    env = verification_test_env
    case, snapshot, rev_event, app_event, env = _setup_approved_mixed_case(session, env)

    owner_principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    owner_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)
    service = CustomerVerificationService(session)

    # 1. Corrupt review event payload ciphertext fails closed with 409
    orig_rev_enc = dict(rev_event.payload_encrypted)
    rev_event.payload_encrypted = {"ciphertext": "corrupted", "nonce": "bad", "tag": "bad"}
    session.flush()

    with pytest.raises(HTTPException) as exc_info:
        service.issue_verification(
            owner_principal,
            owner_context,
            IssueVerificationRequest(
                operation_id=uuid4(),
                preaudit_id=case.id,
                expected_case_revision=case.revision,
                snapshot_id=snapshot.id,
                snapshot_digest=snapshot.digest,
            ),
        )
    assert exc_info.value.status_code == 409
    assert "Corrupt or invalid review decision" in exc_info.value.detail

    # Restore review event
    rev_event.payload_encrypted = orig_rev_enc
    session.flush()

    # 2. Corrupt approval event payload ciphertext fails closed with 409
    orig_app_enc = dict(app_event.payload_encrypted)
    app_event.payload_encrypted = {"ciphertext": "corrupted", "nonce": "bad", "tag": "bad"}
    session.flush()

    with pytest.raises(HTTPException) as exc_info:
        service.issue_verification(
            owner_principal,
            owner_context,
            IssueVerificationRequest(
                operation_id=uuid4(),
                preaudit_id=case.id,
                expected_case_revision=case.revision,
                snapshot_id=snapshot.id,
                snapshot_digest=snapshot.digest,
            ),
        )
    assert exc_info.value.status_code == 409
    assert "Corrupt or invalid approval" in exc_info.value.detail

    # Restore approval event
    app_event.payload_encrypted = orig_app_enc
    session.flush()


def test_verification_database_connection_admission_checks():
    """Verify runtime PostgreSQL database connection admission: superuser, bypassrls, user, and table ownership checks."""
    class MockPgSession:
        def __init__(self, user="conformly_app", is_super=False, is_bypass=False, owned_tables=None):
            self.user = user
            self.is_super = is_super
            self.is_bypass = is_bypass
            self.owned_tables = owned_tables or []
            self.executed_queries = []

        def get_bind(self):
            class Dialect:
                name = "postgresql"
            class Bind:
                dialect = Dialect()
            return Bind()

        def execute(self, statement, *args, **kwargs):
            sql = str(statement)
            self.executed_queries.append(sql)
            if "pg_class" in sql:
                class ScalarResult:
                    def __init__(self, items):
                        self._items = items
                    def scalars(self):
                        return self
                    def all(self):
                        return self._items
                return ScalarResult(self.owned_tables)
            elif "pg_roles" in sql:
                class RoleRow:
                    def __init__(self, u, s, b):
                        self._r = (u, s, b)
                    def first(self):
                        return self._r
                    def __getitem__(self, idx):
                        return self._r[idx]
                return RoleRow(self.user, self.is_super, self.is_bypass)
            raise NotImplementedError(sql)

    # 1. Superuser rejected
    with pytest.raises(CustomerDemoDatabaseAdmissionError) as exc_info:
        verify_verification_database_connection(MockPgSession(is_super=True))
    assert "superuser=True" in str(exc_info.value)

    # 2. BypassRLS rejected
    with pytest.raises(CustomerDemoDatabaseAdmissionError) as exc_info:
        verify_verification_database_connection(MockPgSession(is_bypass=True))
    assert "bypassrls=True" in str(exc_info.value)

    # 3. Disallowed user rejected
    with pytest.raises(CustomerDemoDatabaseAdmissionError) as exc_info:
        verify_verification_database_connection(MockPgSession(user="postgres"))
    assert "Disallowed PostgreSQL runtime identity: postgres" in str(exc_info.value)

    # 4. Owner of ONLY customer_readiness_verification_events rejected
    with pytest.raises(CustomerDemoDatabaseAdmissionError) as exc_info:
        verify_verification_database_connection(MockPgSession(owned_tables=["customer_readiness_verification_events"]))
    assert "must not own verification tables: ['customer_readiness_verification_events']" in str(exc_info.value)

    # 5. Owner of ONLY customer_readiness_verifications rejected
    with pytest.raises(CustomerDemoDatabaseAdmissionError) as exc_info:
        verify_verification_database_connection(MockPgSession(owned_tables=["customer_readiness_verifications"]))
    assert "must not own verification tables: ['customer_readiness_verifications']" in str(exc_info.value)

    # 6. Legitimate non-owner connection accepted
    sess = MockPgSession(owned_tables=[])
    verify_verification_database_connection(sess)
    # Assert actual schema-qualified SQL executed
    last_query = sess.executed_queries[-1]
    assert "customer_readiness_verifications" in last_query
    assert "customer_readiness_verification_events" in last_query
    assert "pg_namespace" in last_query
    assert "n.nspname = 'public'" in last_query
    assert "r.rolname = current_user" in last_query


def test_strict_integer_revisions_rejection():
    """Ensure strict=True rejects boolean, string, and float revisions across request models."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SuspendVerificationRequest(
            operation_id=uuid4(),
            expected_revision=True,  # type: ignore
            reason="test",
        )

    with pytest.raises(ValidationError):
        SuspendVerificationRequest(
            operation_id=uuid4(),
            expected_revision="1",  # type: ignore
            reason="test",
        )

    with pytest.raises(ValidationError):
        SuspendVerificationRequest(
            operation_id=uuid4(),
            expected_revision=1.5,  # type: ignore
            reason="test",
        )


def test_provenance_freeze_accepts_absent_owner_approval_notes(session: Session, verification_test_env):
    """Provenance freeze accepts legitimate pre-audit approvals where notes are None, preserving verified approval identity."""
    env = verification_test_env
    case, snapshot, rev_event, app_event, env = _setup_approved_mixed_case(session, env, approval_notes=None)

    owner_principal = Principal(user_id=env["owner_id"], mfa_verified=True)
    owner_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["owner_id"], role=Role.OWNER)
    lead_principal = Principal(user_id=env["mgr_id"], mfa_verified=True)
    lead_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["mgr_id"], role=Role.COMPLIANCE_MANAGER)
    rev_principal = Principal(user_id=env["rev_id"], mfa_verified=True)
    rev_context = TenantContext(tenant_id=env["tenant_id"], user_id=env["rev_id"], role=Role.COMPLIANCE_MANAGER)

    service = CustomerVerificationService(session)
    preaudit_svc = CustomerPreauditService(session)

    # 1. Successful issuance with absent approval notes
    v_res = service.issue_verification(
        owner_principal,
        owner_context,
        IssueVerificationRequest(
            operation_id=uuid4(),
            preaudit_id=case.id,
            expected_case_revision=case.revision,
            snapshot_id=snapshot.id,
            snapshot_digest=snapshot.digest,
            limitations=[],  # empty list
        ),
    )
    assert v_res.status == "ACTIVE"

    raw_v = session.query(CustomerReadinessVerification).filter_by(
        tenant_id=env["tenant_id"],
        id=v_res.id,
    ).one()

    decrypted = decrypt_verification_payload(
        service.codec,
        env["tenant_id"],
        v_res.id,
        raw_v.payload_encrypted,
        raw_v.digest,
    )
    # Notes are None honestly preserved
    assert decrypted["owner_approval_notes"] is None
    # Rigorous cryptographic provenance bindings remain intact
    assert decrypted["approval_event_id"] == str(app_event.id)
    assert decrypted["approver_user_id"] == str(env["owner_id"])
    assert decrypted["issuer_user_id"] == str(env["owner_id"])
    assert decrypted["reviewer_user_id"] == str(env["rev_id"])
    assert decrypted["review_event_id"] == str(rev_event.id)
    assert decrypted["reviewer_decision"] == "ACCEPT"
    assert decrypted["reviewer_decision_notes"] == "Independent review accepted"

    # 2. Detail and projection work cleanly
    detail = service.get_verification(owner_principal, owner_context, v_res.id)
    assert detail.id == v_res.id
    assert detail.status == "ACTIVE"

    proj = service.get_verification_projection(owner_principal, owner_context, v_res.id)
    assert proj.verification_id == v_res.id
    assert proj.status == "ACTIVE"
    assert proj.controls_count == 2

    # 3. Supersession works when referencing a replacement case with absent approval notes
    case2 = preaudit_svc.create_case(
        lead_principal,
        lead_context,
        CreatePreauditRequest(
            operation_id=uuid4(),
            adoption_id=env["adoption_id"],
            lead_user_id=env["mgr_id"],
            reviewer_user_id=env["rev_id"],
            title="Replacement Case No Notes",
        ),
    )
    preaudit_svc.freeze_scope(
        lead_principal,
        lead_context,
        case2.id,
        FreezeScopeRequest(operation_id=uuid4(), expected_revision=1),
    )
    sub2 = preaudit_svc.submit_review(
        lead_principal,
        lead_context,
        case2.id,
        SubmitReviewRequest(
            operation_id=uuid4(),
            expected_revision=2,
            submission_notes="Lead notes 2",
        ),
    )
    preaudit_svc.review_decision(
        rev_principal,
        rev_context,
        case2.id,
        ReviewDecisionRequest(
            operation_id=uuid4(),
            expected_revision=3,
            snapshot_id=sub2.current_review_snapshot_id,
            snapshot_digest=sub2.current_review_snapshot_digest,
            decision="ACCEPT",
            notes="Review accepted 2",
        ),
    )
    preaudit_svc.approve_case(
        owner_principal,
        owner_context,
        case2.id,
        ApprovePreauditRequest(
            operation_id=uuid4(),
            expected_revision=4,
            snapshot_id=sub2.current_review_snapshot_id,
            snapshot_digest=sub2.current_review_snapshot_digest,
            approval_notes=None,
        ),
    )
    snap2 = session.query(CustomerPreauditSnapshot).filter_by(id=sub2.current_review_snapshot_id).scalar()

    v2 = service.supersede_verification(
        owner_principal,
        owner_context,
        v_res.id,
        SupersedeVerificationRequest(
            operation_id=uuid4(),
            expected_revision=1,
            new_preaudit_id=case2.id,
            new_expected_case_revision=5,
            new_snapshot_id=snap2.id,
            new_snapshot_digest=snap2.digest,
            notes="Superseded without approval notes",
        ),
    )
    assert v2.status == "ACTIVE"
    assert v2.supersedes_id == v_res.id

    # 4. Fail-closed: unapproved case fails with 409 without partial writes
    case3 = preaudit_svc.create_case(
        lead_principal,
        lead_context,
        CreatePreauditRequest(
            operation_id=uuid4(),
            adoption_id=env["adoption_id"],
            lead_user_id=env["mgr_id"],
            reviewer_user_id=env["rev_id"],
            title="Unapproved Case 3",
        ),
    )
    preaudit_svc.freeze_scope(
        lead_principal,
        lead_context,
        case3.id,
        FreezeScopeRequest(operation_id=uuid4(), expected_revision=1),
    )
    sub3 = preaudit_svc.submit_review(
        lead_principal,
        lead_context,
        case3.id,
        SubmitReviewRequest(
            operation_id=uuid4(),
            expected_revision=2,
            submission_notes="Lead notes 3",
        ),
    )
    preaudit_svc.review_decision(
        rev_principal,
        rev_context,
        case3.id,
        ReviewDecisionRequest(
            operation_id=uuid4(),
            expected_revision=3,
            snapshot_id=sub3.current_review_snapshot_id,
            snapshot_digest=sub3.current_review_snapshot_digest,
            decision="ACCEPT",
            notes="Review accepted 3",
        ),
    )
    snap3 = session.query(CustomerPreauditSnapshot).filter_by(id=sub3.current_review_snapshot_id).scalar()

    with pytest.raises(HTTPException) as exc_unapproved:
        service.issue_verification(
            owner_principal,
            owner_context,
            IssueVerificationRequest(
                operation_id=uuid4(),
                preaudit_id=case3.id,
                expected_case_revision=4,
                snapshot_id=snap3.id,
                snapshot_digest=snap3.digest,
            ),
        )
    assert exc_unapproved.value.status_code == 409
    assert "APPROVED" in str(exc_unapproved.value.detail)
    assert session.query(CustomerReadinessVerification).filter_by(tenant_id=env["tenant_id"], preaudit_id=case3.id).first() is None

    # 5. Fail-closed: Corrupt ciphertext on approval event fails with 409 without partial writes
    preaudit_svc.approve_case(
        owner_principal,
        owner_context,
        case3.id,
        ApprovePreauditRequest(
            operation_id=uuid4(),
            expected_revision=4,
            snapshot_id=sub3.current_review_snapshot_id,
            snapshot_digest=sub3.current_review_snapshot_digest,
            approval_notes=None,
        ),
    )
    app_ev3 = session.query(CustomerPreauditEvent).filter_by(
        tenant_id=env["tenant_id"],
        preaudit_id=case3.id,
        event_type="APPROVED",
    ).first()
    assert app_ev3 is not None
    app_ev3.payload_encrypted = {"ciphertext_b64": "corrupt", "nonce_b64": "corrupt"}
    session.commit()

    with pytest.raises(HTTPException) as exc_corrupt:
        service.issue_verification(
            owner_principal,
            owner_context,
            IssueVerificationRequest(
                operation_id=uuid4(),
                preaudit_id=case3.id,
                expected_case_revision=5,
                snapshot_id=snap3.id,
                snapshot_digest=snap3.digest,
            ),
        )
    assert exc_corrupt.value.status_code == 409
    assert "Corrupt or invalid approval event ciphertext" in str(exc_corrupt.value.detail)
    assert session.query(CustomerReadinessVerification).filter_by(tenant_id=env["tenant_id"], preaudit_id=case3.id).first() is None
