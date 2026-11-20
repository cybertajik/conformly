"""Unit tests for Customer Assessment Service Layer (MVP-C).

Tests positive and negative assessment lifecycles, findings, CAS concurrency,
replay idempotency, module entitlements, encryption, and staleness detection.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.config import get_settings
from conformly.crypto.policy import DataClassification
from conformly.customer_demo.assessment_models import (
    CustomerAssessmentEvent,
    CustomerAssessmentHead,
)
from conformly.customer_demo.assessment_schemas import (
    AssessmentCreateRequest,
    AssessmentCriterionResultDto,
    FindingCreateSpecificationDto,
    FindingPatchRequest,
    RetestCreateRequest,
    RetestFindingReferenceDto,
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
from conformly.customer_demo.policy import CustomerDemoAdmissionError
from conformly.customer_demo.work_models import (
    CustomerControlWork,
)
from conformly.customer_demo.work_scanner import (
    StrictEvidenceMalwareScanner,
)
from conformly.customer_demo.work_schemas import (
    CreateEvidenceRequest,
    CreateReviewRequest,
    InitializeWorkRequest,
)
from conformly.customer_demo.work_service import CustomerControlWorkService
from conformly.db.base import Base
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


class MockSuccessfulScanner(StrictEvidenceMalwareScanner):
    """Test scanner subclass simulating successful ClamAV verification."""

    def __init__(self) -> None:
        super().__init__(clamav_host="127.0.0.1", clamav_port=3310)

    def scan(self, data: bytes, filename: str) -> None:
        pass


def _seed_stored_file(
    session: Session, tenant_id: UUID, user_id: UUID, content: bytes = b"test evidence content"
) -> StoredFile:
    file_id = uuid4()
    now = datetime.now(UTC)
    f = StoredFile(
        id=file_id,
        tenant_id=tenant_id,
        original_filename="audit_log.txt",
        content_type="text/plain",
        plaintext_size_bytes=len(content),
        ciphertext_size_bytes=len(content) + 28,
        storage_backend="local",
        encryption_algorithm="AES-256-GCM",
        key_version="v1",
        wrapped_dek_nonce="nonce123456",
        wrapped_dek="wrappeddek123456",
        ciphertext_nonce="nonce123456",
        object_key=f"tenants/{tenant_id}/files/{file_id}/audit_log.txt",
        classification=DataClassification.RESTRICTED.value,
        status=StoredFileStatus.ACTIVE,
        ciphertext_sha256=hashlib.sha256(b"cipher").hexdigest(),
        plaintext_sha256=hashlib.sha256(content).hexdigest(),
        created_by_user_id=user_id,
        created_at=now,
    )
    session.add(f)
    session.commit()
    return f


@pytest.fixture(autouse=True)
def enable_customer_demo_feature(monkeypatch):
    """Enable customer demo feature in test environment."""
    cfg = get_settings()
    monkeypatch.setattr(cfg, "enable_customer_demo", True)
    monkeypatch.setattr(cfg, "environment", "test")


@pytest.fixture
def db_session():
    """In-memory SQLite session with all models created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def test_setup(db_session: Session):
    """Seed test tenant, users, entitlement, workspace, and control work."""
    tenant_id = uuid4()
    owner_id = uuid4()
    mgr_id = uuid4()
    ctrl_owner_id = uuid4()
    auditor_id = uuid4()
    foreign_user_id = uuid4()
    now = datetime.now(UTC)

    tenant = Tenant(
        id=tenant_id,
        name="Test Tenant",
        slug=f"tenant-{tenant_id}",
        status=TenantStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    db_session.add(tenant)

    owner_user = User(
        id=owner_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="sub-owner",
        email="owner@example.com",
        display_name="Alice Owner",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    mgr_user = User(
        id=mgr_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="sub-mgr",
        email="mgr@example.com",
        display_name="Bob Manager",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    ctrl_owner_user = User(
        id=ctrl_owner_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="sub-ctrl",
        email="ctrl@example.com",
        display_name="Carol ControlOwner",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    auditor_user = User(
        id=auditor_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="sub-auditor",
        email="auditor@example.com",
        display_name="Dave Auditor",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    foreign_user = User(
        id=foreign_user_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="sub-foreign",
        email="foreign@example.com",
        display_name="Foreign User",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([owner_user, mgr_user, ctrl_owner_user, auditor_user, foreign_user])

    # Memberships
    m_owner = Membership(
        tenant_id=tenant_id,
        user_id=owner_id,
        role=Role.OWNER,
        status=MembershipStatus.ACTIVE,
        is_workforce=False,
        is_external_advisor=False,
        created_at=now,
        updated_at=now,
    )
    m_mgr = Membership(
        tenant_id=tenant_id,
        user_id=mgr_id,
        role=Role.COMPLIANCE_MANAGER,
        status=MembershipStatus.ACTIVE,
        is_workforce=False,
        is_external_advisor=False,
        created_at=now,
        updated_at=now,
    )
    m_ctrl = Membership(
        tenant_id=tenant_id,
        user_id=ctrl_owner_id,
        role=Role.CONTROL_OWNER,
        status=MembershipStatus.ACTIVE,
        is_workforce=False,
        is_external_advisor=False,
        created_at=now,
        updated_at=now,
    )
    m_auditor = Membership(
        tenant_id=tenant_id,
        user_id=auditor_id,
        role=Role.AUDITOR,
        status=MembershipStatus.ACTIVE,
        is_workforce=False,
        is_external_advisor=False,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([m_owner, m_mgr, m_ctrl, m_auditor])

    # Entitlement with preaudit and findings modules enabled
    ent = TenantEntitlement(
        tenant_id=tenant_id,
        plan_code="tier_a",
        enabled_modules=["frameworks", "evidence", "tasks", "preaudit", "findings"],
        max_members=100,
        max_storage_bytes=10000000,
        allowed_framework_slugs=["*"],
        effective_from=now - timedelta(days=1),
        effective_until=now + timedelta(days=365),
    )
    db_session.add(ent)

    # Workspace & Adoption
    ws = CustomerDemoWorkspace(
        tenant_id=tenant_id,
        current_revision=1,
        selection_revision=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(ws)

    ans_digest = compute_answers_digest(
        "ALPHA", {"synthetic_wp09_uses_cloud": True, "synthetic_wp09_operating_region": "EU"}
    )
    answers = CustomerDemoAnswers(
        tenant_id=tenant_id,
        revision=1,
        company_code="ALPHA",
        answers={"synthetic_wp09_uses_cloud": True, "synthetic_wp09_operating_region": "EU"},
        content_digest=ans_digest,
        actor_id=owner_id,
        created_at=now,
    )
    db_session.add(answers)

    eval_results = evaluate_bundle(
        PACK_VERSION_V1_ID,
        {"synthetic_wp09_uses_cloud": True, "synthetic_wp09_operating_region": "EU"},
    )
    eval_digest = compute_evaluation_digest(
        answer_digest=ans_digest,
        answer_revision=1,
        bundle_digest=BUNDLE_V1_DIGEST,
        evaluator_version=EVALUATOR_VERSION,
        pack_version_id=PACK_VERSION_V1_ID,
        results=eval_results,
    )
    eval_id = uuid4()
    evaluation = CustomerDemoEvaluation(
        id=eval_id,
        tenant_id=tenant_id,
        answer_revision=1,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=BUNDLE_V1_DIGEST,
        evaluator_version=EVALUATOR_VERSION,
        content_digest=eval_digest,
        results=eval_results,
        actor_id=owner_id,
        created_at=now,
    )
    db_session.add(evaluation)

    adopt_id = uuid4()
    adoption = CustomerDemoAdoption(
        id=adopt_id,
        tenant_id=tenant_id,
        selection_revision=1,
        evaluation_id=eval_id,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=BUNDLE_V1_DIGEST,
        actor_id=owner_id,
        created_at=now,
    )
    db_session.add(adoption)
    db_session.commit()

    # Initialize work items using CustomerControlWorkService
    owner_p = Principal(user_id=owner_id, mfa_verified=True)
    owner_t = TenantContext(tenant_id=tenant_id, role=Role.OWNER, user_id=owner_id)
    work_svc = CustomerControlWorkService(db_session, scanner=MockSuccessfulScanner())
    init_res = work_svc.initialize_work(
        owner_p,
        owner_t,
        InitializeWorkRequest(
            operation_id=uuid4(),
            adoption_id=adopt_id,
            expected_selection_revision=1,
            expected_answer_revision=1,
        ),
        request_id="req-init",
    )
    work_item_dto = init_res.items[0]
    work_orm = (
        db_session.query(CustomerControlWork)
        .filter_by(tenant_id=tenant_id, id=work_item_dto.id)
        .one()
    )

    # Pin verified evidence
    file_content = b"Encrypted test file contents for compliance."
    stored_file = _seed_stored_file(db_session, tenant_id, owner_id, file_content)

    with patch("conformly.customer_demo.work_service.StorageService") as MockStorage:
        instance = MockStorage.return_value
        instance.download_file.return_value = (stored_file, file_content)
        ev_receipt = work_svc.create_evidence(
            owner_p,
            owner_t,
            work_item_dto.id,
            CreateEvidenceRequest(
                operation_id=uuid4(),
                expected_selection_revision=1,
                expected_answer_revision=1,
                expected_work_version=work_orm.version,
                file_id=stored_file.id,
                rationale="Audit policy evidence",
            ),
            request_id="req-pin",
        )
        link_id = ev_receipt.current_work.links[0].id

        # Review and accept evidence link so it is valid for assessment
        db_session.refresh(work_orm)
        work_svc.create_review(
            owner_p,
            owner_t,
            work_item_dto.id,
            link_id,
            CreateReviewRequest(
                operation_id=uuid4(),
                expected_selection_revision=1,
                expected_answer_revision=1,
                expected_work_version=work_orm.version,
                decision="ACCEPTED",
                rationale="Evidence reviewed and accepted for assessment",
            ),
            request_id="req-rev",
        )

    # Refresh work_orm
    db_session.refresh(work_orm)

    return {
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "mgr_id": mgr_id,
        "ctrl_owner_id": ctrl_owner_id,
        "auditor_id": auditor_id,
        "foreign_user_id": foreign_user_id,
        "work": work_orm,
        "link_id": link_id,
        "adoption_id": adopt_id,
        "owner_p": owner_p,
        "owner_t": owner_t,
        "mgr_p": Principal(user_id=mgr_id, mfa_verified=True),
        "mgr_t": TenantContext(tenant_id=tenant_id, role=Role.COMPLIANCE_MANAGER, user_id=mgr_id),
        "ctrl_p": Principal(user_id=ctrl_owner_id, mfa_verified=True),
        "ctrl_t": TenantContext(
            tenant_id=tenant_id, role=Role.CONTROL_OWNER, user_id=ctrl_owner_id
        ),
        "auditor_p": Principal(user_id=auditor_id, mfa_verified=True),
        "auditor_t": TenantContext(tenant_id=tenant_id, role=Role.AUDITOR, user_id=auditor_id),
    }


def test_positive_assessment_findings_retest_journey(
    db_session: Session, test_setup: dict[str, Any]
):
    """Test full journey: FAIL assessment with finding -> patch remediation -> successful retest -> PASS."""
    tenant_id = test_setup["tenant_id"]
    ctrl_owner_id = test_setup["ctrl_owner_id"]
    work: CustomerControlWork = test_setup["work"]
    link_id: UUID = test_setup["link_id"]

    principal = test_setup["mgr_p"]
    tenant_ctx = test_setup["mgr_t"]
    service = CustomerAssessmentService(db_session)

    proc = service.get_procedure(principal, tenant_ctx, work.id)
    assert proc.digest is not None
    assert len(proc.criteria) == 3

    # Step 1: Initial human assessment as FAIL with a finding
    op1_id = uuid4()
    req1 = AssessmentCreateRequest(
        operation_id=op1_id,
        expected_answer_revision=1,
        expected_selection_revision=1,
        expected_work_version=work.version,
        expected_assessment_revision=0,
        procedure_id=proc.id,
        procedure_version=proc.version,
        procedure_digest=proc.digest,
        evidence_link_ids=[link_id],
        criterion_results=[
            AssessmentCriterionResultDto(criterion_id="implementation", result="FAIL"),
            AssessmentCriterionResultDto(criterion_id="evidence", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="operation", result="PASS"),
        ],
        result="FAIL",
        rationale="Policy signoff missing from Q3 review",
        finding=FindingCreateSpecificationDto(
            severity="MEDIUM",
            owner_user_id=ctrl_owner_id,
            due_date=date.today() + timedelta(days=14),
        ),
    )

    receipt1 = service.record_assessment(principal, tenant_ctx, work.id, req1)
    assert receipt1.replayed is False
    assert receipt1.applied_revision == 1
    assert receipt1.current_item.primary_state == "FAIL"
    assert len(receipt1.current_item.findings) == 1

    finding = receipt1.current_item.findings[0]
    assert finding.status == "OPEN"
    assert finding.severity == "MEDIUM"
    assert finding.owner_user_id == ctrl_owner_id

    # Verify head and encrypted event
    head = (
        db_session.query(CustomerAssessmentHead)
        .filter_by(tenant_id=tenant_id, work_id=work.id)
        .one()
    )
    assert head.current_revision == 1

    event = (
        db_session.query(CustomerAssessmentEvent)
        .filter_by(tenant_id=tenant_id, work_id=work.id, revision=1)
        .one()
    )
    assert event.event_type == "ASSESSMENT"
    assert event.result == "FAIL"
    assert event.details_encrypted is not None

    # Step 2: Patch finding into IN_REMEDIATION with remediation note
    patch_req = FindingPatchRequest(
        operation_id=uuid4(),
        expected_answer_revision=1,
        expected_selection_revision=1,
        expected_work_version=work.version,
        expected_assessment_revision=1,
        expected_finding_version=finding.version,
        severity="MEDIUM",
        owner_user_id=ctrl_owner_id,
        due_date=finding.due_date,
        status="IN_REMEDIATION",
        remediation_note="Drafted revised policy sign-off sheet",
    )
    receipt_patch = service.update_finding(principal, tenant_ctx, finding.id, patch_req)
    assert receipt_patch.replayed is False
    updated_finding = [f for f in receipt_patch.current_item.findings if f.id == finding.id][0]
    assert updated_finding.status == "IN_REMEDIATION"
    assert updated_finding.version == finding.version + 1

    # Step 3: Record explicit retest passing the finding
    op2_id = uuid4()
    retest_req = RetestCreateRequest(
        operation_id=op2_id,
        expected_answer_revision=1,
        expected_selection_revision=1,
        expected_work_version=work.version,
        expected_assessment_revision=2,
        procedure_id=proc.id,
        procedure_version=proc.version,
        procedure_digest=proc.digest,
        evidence_link_ids=[link_id],
        criterion_results=[
            AssessmentCriterionResultDto(criterion_id="implementation", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="evidence", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="operation", result="PASS"),
        ],
        result="PASS",
        rationale="All criteria met and sign-off provided",
        findings=[
            RetestFindingReferenceDto(id=finding.id, expected_version=updated_finding.version)
        ],
    )
    receipt_retest = service.record_retest(principal, tenant_ctx, work.id, retest_req)
    assert receipt_retest.applied_revision == 3
    resolved_finding = [f for f in receipt_retest.current_item.findings if f.id == finding.id][0]
    assert resolved_finding.status == "RESOLVED"
    assert receipt_retest.current_item.primary_state == "PASS"

    # Step 4: Verify summary
    summary = receipt_retest.summary
    assert summary.pass_count == 1
    assert summary.open_findings == 0
    assert summary.in_remediation_findings == 0
    assert summary.resolved_findings == 1
    assert summary.unassessed == 1
    assert work.control_id not in summary.blocked_control_ids
    assert len(summary.blocked_control_ids) == 1


def test_assessment_idempotent_replay(db_session: Session, test_setup: dict[str, Any]):
    """Test idempotent retry of exact matching operation vs conflict on payload mismatch."""
    work: CustomerControlWork = test_setup["work"]
    link_id: UUID = test_setup["link_id"]

    principal = test_setup["mgr_p"]
    tenant_ctx = test_setup["mgr_t"]
    service = CustomerAssessmentService(db_session)

    proc = service.get_procedure(principal, tenant_ctx, work.id)
    op_id = uuid4()
    req = AssessmentCreateRequest(
        operation_id=op_id,
        expected_answer_revision=1,
        expected_selection_revision=1,
        expected_work_version=work.version,
        expected_assessment_revision=0,
        procedure_id=proc.id,
        procedure_version=proc.version,
        procedure_digest=proc.digest,
        evidence_link_ids=[link_id],
        criterion_results=[
            AssessmentCriterionResultDto(criterion_id="implementation", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="evidence", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="operation", result="PASS"),
        ],
        result="PASS",
        rationale="Initial pass",
        finding=None,
    )

    receipt1 = service.record_assessment(principal, tenant_ctx, work.id, req)
    assert receipt1.replayed is False
    assert receipt1.applied_revision == 1

    # Exact replay
    receipt2 = service.record_assessment(principal, tenant_ctx, work.id, req)
    assert receipt2.replayed is True
    assert receipt2.event_id == receipt1.event_id
    assert receipt2.applied_revision == receipt1.applied_revision

    # Conflict on changed rationale with same operation_id
    req_mismatch = req.model_copy(update={"rationale": "Different rationale"})
    with pytest.raises(HTTPException) as exc_info:
        service.record_assessment(principal, tenant_ctx, work.id, req_mismatch)
    assert exc_info.value.status_code == 409


def test_cas_concurrency_guards(db_session: Session, test_setup: dict[str, Any]):
    """Test CAS rejection on wrong expected_work_version or expected_finding_version."""
    work: CustomerControlWork = test_setup["work"]
    link_id: UUID = test_setup["link_id"]

    principal = test_setup["mgr_p"]
    tenant_ctx = test_setup["mgr_t"]
    service = CustomerAssessmentService(db_session)

    proc = service.get_procedure(principal, tenant_ctx, work.id)

    # Wrong work version
    req = AssessmentCreateRequest(
        operation_id=uuid4(),
        expected_answer_revision=1,
        expected_selection_revision=1,
        expected_work_version=work.version + 99,
        expected_assessment_revision=0,
        procedure_id=proc.id,
        procedure_version=proc.version,
        procedure_digest=proc.digest,
        evidence_link_ids=[link_id],
        criterion_results=[
            AssessmentCriterionResultDto(criterion_id="implementation", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="evidence", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="operation", result="PASS"),
        ],
        result="PASS",
        rationale="Pass",
        finding=None,
    )
    with pytest.raises(HTTPException) as exc:
        service.record_assessment(principal, tenant_ctx, work.id, req)
    assert exc.value.status_code == 409


def test_entitlement_and_role_denials(db_session: Session, test_setup: dict[str, Any]):
    """Test that missing modules or unauthorized roles are denied access."""
    tenant_id = test_setup["tenant_id"]
    work: CustomerControlWork = test_setup["work"]
    service = CustomerAssessmentService(db_session)

    # Auditor is not admitted to customer demo
    auditor_p = test_setup["auditor_p"]
    auditor_t = test_setup["auditor_t"]
    with pytest.raises(CustomerDemoAdmissionError):
        service.get_procedure(auditor_p, auditor_t, work.id)

    # Disable findings module and verify 403
    ent = db_session.query(TenantEntitlement).filter_by(tenant_id=tenant_id).one()
    ent.enabled_modules = ["frameworks", "evidence", "tasks"]  # missing preaudit & findings
    db_session.commit()

    mgr_p = test_setup["mgr_p"]
    mgr_t = test_setup["mgr_t"]
    with pytest.raises(HTTPException) as exc:
        service.get_procedure(mgr_p, mgr_t, work.id)
    assert exc.value.status_code == 403


def test_strict_dto_validation_and_rejections(db_session: Session, test_setup: dict[str, Any]):
    """Verify strict nonbool, hex64, nonblank, exact 3 criteria validation."""
    work = test_setup["work"]
    from pydantic import ValidationError

    from conformly.customer_demo.assessment_schemas import (
        AssessmentCreateRequest,
        AssessmentCriterionResultDto,
    )

    valid_criteria = [
        AssessmentCriterionResultDto(criterion_id="implementation", result="PASS"),
        AssessmentCriterionResultDto(criterion_id="evidence", result="PASS"),
        AssessmentCriterionResultDto(criterion_id="operation", result="PASS"),
    ]

    # 1. Reject bool True for expected_answer_revision
    try:
        AssessmentCreateRequest(
            operation_id=uuid4(),
            expected_answer_revision=True,  # type: ignore
            expected_selection_revision=1,
            expected_work_version=work.version,
            expected_assessment_revision=0,
            procedure_id=uuid4(),
            procedure_version="1.0.0",
            procedure_digest="a" * 64,
            result="PASS",
            rationale="Valid rationale",
            criterion_results=valid_criteria,
            evidence_link_ids=[uuid4()],
        )
        pytest.fail("Expected ValidationError for bool True revision")
    except ValidationError:
        pass

    # 2. Reject non-hex64 procedure_digest
    try:
        AssessmentCreateRequest(
            operation_id=uuid4(),
            expected_answer_revision=1,
            expected_selection_revision=1,
            expected_work_version=work.version,
            expected_assessment_revision=0,
            procedure_id=uuid4(),
            procedure_version="1.0.0",
            procedure_digest="not-a-valid-hex64-digest",
            result="PASS",
            rationale="Valid rationale",
            criterion_results=valid_criteria,
            evidence_link_ids=[uuid4()],
        )
        pytest.fail("Expected ValidationError for non-hex64 digest")
    except ValidationError:
        pass

    # 3. Reject whitespace-only rationale
    try:
        AssessmentCreateRequest(
            operation_id=uuid4(),
            expected_answer_revision=1,
            expected_selection_revision=1,
            expected_work_version=work.version,
            expected_assessment_revision=0,
            procedure_id=uuid4(),
            procedure_version="1.0.0",
            procedure_digest="a" * 64,
            result="PASS",
            rationale="   \t\n  ",
            criterion_results=valid_criteria,
            evidence_link_ids=[uuid4()],
        )
        pytest.fail("Expected ValidationError for blank rationale")
    except ValidationError:
        pass

    # 4. Reject missing criterion (only 2 criteria)
    try:
        AssessmentCreateRequest(
            operation_id=uuid4(),
            expected_answer_revision=1,
            expected_selection_revision=1,
            expected_work_version=work.version,
            expected_assessment_revision=0,
            procedure_id=uuid4(),
            procedure_version="1.0.0",
            procedure_digest="a" * 64,
            result="PASS",
            rationale="Valid rationale",
            criterion_results=valid_criteria[:2],
            evidence_link_ids=[uuid4()],
        )
        pytest.fail("Expected ValidationError for incomplete criteria")
    except ValidationError:
        pass

    # 5. Reject duplicate evidence link IDs
    dup_id = uuid4()
    try:
        AssessmentCreateRequest(
            operation_id=uuid4(),
            expected_answer_revision=1,
            expected_selection_revision=1,
            expected_work_version=work.version,
            expected_assessment_revision=0,
            procedure_id=uuid4(),
            procedure_version="1.0.0",
            procedure_digest="a" * 64,
            result="PASS",
            rationale="Valid rationale",
            criterion_results=valid_criteria,
            evidence_link_ids=[dup_id, dup_id],
        )
        pytest.fail("Expected ValidationError for duplicate evidence links")
    except ValidationError:
        pass


def test_procedure_digest_mismatch_and_adoption_guards(
    db_session: Session, test_setup: dict[str, Any]
):
    """Verify procedure digest mismatch raises 422, retest outcome consistency with real findings, and work outside adoption raises 409."""
    service = CustomerAssessmentService(db_session)
    work = test_setup["work"]
    principal = test_setup["owner_p"]
    tenant_ctx = test_setup["owner_t"]
    proc = service.get_procedure(principal, tenant_ctx, work.id)

    # 1. Procedure digest mismatch raises 422
    wrong_digest_req = AssessmentCreateRequest(
        operation_id=uuid4(),
        expected_answer_revision=1,
        expected_selection_revision=1,
        expected_work_version=work.version,
        expected_assessment_revision=0,
        procedure_id=proc.id,
        procedure_version=proc.version,
        procedure_digest="f" * 64,  # wrong digest
        result="FAIL",
        rationale="Human noted failure",
        criterion_results=[
            AssessmentCriterionResultDto(criterion_id="implementation", result="FAIL"),
            AssessmentCriterionResultDto(criterion_id="evidence", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="operation", result="PASS"),
        ],
        finding=FindingCreateSpecificationDto(
            severity="MEDIUM",
            owner_user_id=test_setup["owner_id"],
            due_date=date(2026, 11, 1),
        ),
    )
    with pytest.raises(HTTPException) as exc_info:
        service.record_assessment(principal, tenant_ctx, work.id, wrong_digest_req)
    assert exc_info.value.status_code == 422

    # 2. Record a valid initial assessment creating a real unresolved finding
    initial_fail_req = AssessmentCreateRequest(
        operation_id=uuid4(),
        expected_answer_revision=1,
        expected_selection_revision=1,
        expected_work_version=work.version,
        expected_assessment_revision=0,
        procedure_id=proc.id,
        procedure_version=proc.version,
        procedure_digest=proc.digest,
        result="FAIL",
        rationale="Valid assessment producing finding",
        criterion_results=[
            AssessmentCriterionResultDto(criterion_id="implementation", result="FAIL"),
            AssessmentCriterionResultDto(criterion_id="evidence", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="operation", result="PASS"),
        ],
        finding=FindingCreateSpecificationDto(
            severity="HIGH",
            owner_user_id=test_setup["owner_id"],
            due_date=date(2026, 12, 1),
        ),
    )
    res_initial = service.record_assessment(principal, tenant_ctx, work.id, initial_fail_req)
    assert res_initial.current_item.primary_state == "FAIL"
    item = service.get_assessment_work_item(principal, tenant_ctx, work.id)
    assert len(item.findings) == 1
    real_finding = item.findings[0]
    assert real_finding.status == "OPEN"

    # 3. Retest negative outcome consistency with real unresolved finding
    # Case A: result=FAIL with all PASS criteria raises 422
    inconsistent_retest_req_a = RetestCreateRequest(
        operation_id=uuid4(),
        expected_answer_revision=1,
        expected_selection_revision=1,
        expected_work_version=work.version,
        expected_assessment_revision=1,
        procedure_id=proc.id,
        procedure_version=proc.version,
        procedure_digest=proc.digest,
        result="FAIL",
        rationale="Contradictory retest result",
        criterion_results=[
            AssessmentCriterionResultDto(criterion_id="implementation", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="evidence", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="operation", result="PASS"),
        ],
        findings=[
            RetestFindingReferenceDto(id=real_finding.id, expected_version=real_finding.version)
        ],
    )
    with pytest.raises(HTTPException) as exc_a:
        service.record_retest(principal, tenant_ctx, work.id, inconsistent_retest_req_a)
    assert exc_a.value.status_code == 422
    assert "FAIL retest requires at least one FAIL criterion" in str(exc_a.value.detail)

    # Case B: result=PASS with a FAIL criterion raises 422
    inconsistent_retest_req_b = RetestCreateRequest(
        operation_id=uuid4(),
        expected_answer_revision=1,
        expected_selection_revision=1,
        expected_work_version=work.version,
        expected_assessment_revision=1,
        procedure_id=proc.id,
        procedure_version=proc.version,
        procedure_digest=proc.digest,
        result="PASS",
        rationale="Contradictory pass retest",
        criterion_results=[
            AssessmentCriterionResultDto(criterion_id="implementation", result="FAIL"),
            AssessmentCriterionResultDto(criterion_id="evidence", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="operation", result="PASS"),
        ],
        findings=[
            RetestFindingReferenceDto(id=real_finding.id, expected_version=real_finding.version)
        ],
    )
    with pytest.raises(HTTPException) as exc_b:
        service.record_retest(principal, tenant_ctx, work.id, inconsistent_retest_req_b)
    assert exc_b.value.status_code == 422
    assert "PASS retest requires all criteria to be PASS" in str(exc_b.value.detail)

    # 4. Adoption guard: work outside active adoption raises 409 Conflict
    original_adoption_id = work.adoption_id
    try:
        work.adoption_id = uuid4()
        db_session.flush()

        adopt_req = AssessmentCreateRequest(
            operation_id=uuid4(),
            expected_answer_revision=1,
            expected_selection_revision=1,
            expected_work_version=work.version,
            expected_assessment_revision=1,
            procedure_id=proc.id,
            procedure_version=proc.version,
            procedure_digest=proc.digest,
            result="FAIL",
            rationale="Testing adoption guard",
            criterion_results=[
                AssessmentCriterionResultDto(criterion_id="implementation", result="FAIL"),
                AssessmentCriterionResultDto(criterion_id="evidence", result="PASS"),
                AssessmentCriterionResultDto(criterion_id="operation", result="PASS"),
            ],
            finding=FindingCreateSpecificationDto(
                severity="MEDIUM",
                owner_user_id=test_setup["owner_id"],
                due_date=date(2026, 11, 1),
            ),
        )
        with pytest.raises(HTTPException) as exc_adopt:
            service.record_assessment(principal, tenant_ctx, work.id, adopt_req)
        assert exc_adopt.value.status_code == 409
        assert "does not belong to current active adoption" in str(exc_adopt.value.detail)

        with pytest.raises(HTTPException) as exc_adopt_retest:
            service.record_retest(principal, tenant_ctx, work.id, inconsistent_retest_req_a)
        assert exc_adopt_retest.value.status_code == 409

        with pytest.raises(HTTPException) as exc_adopt_patch:
            from conformly.customer_demo.assessment_schemas import FindingPatchRequest

            patch_req = FindingPatchRequest(
                operation_id=uuid4(),
                expected_answer_revision=1,
                expected_selection_revision=1,
                expected_work_version=work.version,
                expected_assessment_revision=1,
                expected_finding_version=real_finding.version,
                severity="LOW",
                owner_user_id=None,
                due_date=None,
                status="IN_REMEDIATION",
                remediation_note="Testing adoption guard on patch",
            )
            service.update_finding(principal, tenant_ctx, real_finding.id, patch_req)
        assert exc_adopt_patch.value.status_code == 409
    finally:
        work.adoption_id = original_adoption_id
        db_session.flush()


def test_snapshot_digest_tampering_and_chain_verification(
    db_session: Session, test_setup: dict[str, Any]
):
    """Verify saved answer/evaluation/bundle digest tampering is rejected on write (409) and detected on read."""
    service = CustomerAssessmentService(db_session)
    work = test_setup["work"]
    principal = test_setup["owner_p"]
    tenant_ctx = test_setup["owner_t"]
    ws = db_session.scalar(
        select(CustomerDemoWorkspace).where(CustomerDemoWorkspace.tenant_id == tenant_ctx.tenant_id)
    )
    assert ws is not None
    proc = service.get_procedure(principal, tenant_ctx, work.id)

    answer = db_session.scalar(
        select(CustomerDemoAnswers).where(
            CustomerDemoAnswers.tenant_id == tenant_ctx.tenant_id,
            CustomerDemoAnswers.revision == ws.current_revision,
        )
    )
    assert answer is not None
    original_answer_digest = answer.content_digest

    adoption = db_session.scalar(
        select(CustomerDemoAdoption).where(
            CustomerDemoAdoption.tenant_id == tenant_ctx.tenant_id,
            CustomerDemoAdoption.selection_revision == ws.selection_revision,
        )
    )
    assert adoption is not None
    original_bundle_digest = adoption.bundle_digest

    evaluation = db_session.scalar(
        select(CustomerDemoEvaluation).where(
            CustomerDemoEvaluation.tenant_id == tenant_ctx.tenant_id,
            CustomerDemoEvaluation.id == adoption.evaluation_id,
        )
    )
    assert evaluation is not None
    original_eval_digest = evaluation.content_digest
    original_eval_results = list(evaluation.results)

    valid_pass_req = AssessmentCreateRequest(
        operation_id=uuid4(),
        expected_answer_revision=1,
        expected_selection_revision=1,
        expected_work_version=work.version,
        expected_assessment_revision=0,
        procedure_id=proc.id,
        procedure_version=proc.version,
        procedure_digest=proc.digest,
        result="PASS",
        rationale="Valid initial pass",
        criterion_results=[
            AssessmentCriterionResultDto(criterion_id="implementation", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="evidence", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="operation", result="PASS"),
        ],
        evidence_link_ids=[test_setup["link_id"]],
    )

    # A. Saved answer digest tampering ('0'*64) rejects on record_assessment with 409
    try:
        answer.content_digest = "0" * 64
        db_session.flush()

        with pytest.raises(HTTPException) as exc_ans:
            service.record_assessment(principal, tenant_ctx, work.id, valid_pass_req)
        assert exc_ans.value.status_code == 409
        assert "Answer set content digest mismatch" in str(exc_ans.value.detail)
    finally:
        answer.content_digest = original_answer_digest
        db_session.flush()

    # B. Record valid pass
    res = service.record_assessment(principal, tenant_ctx, work.id, valid_pass_req)
    assert res.current_item.primary_state == "PASS"

    # Verify read is clean
    item = service.get_assessment_work_item(principal, tenant_ctx, work.id)
    assert item.primary_state == "PASS"
    assert item.latest_assessment is not None
    assert item.latest_assessment.is_stale is False

    # C. Tamper saved answer digest -> read detects stale assessment
    try:
        answer.content_digest = "0" * 64
        db_session.flush()

        item_tampered = service.get_assessment_work_item(principal, tenant_ctx, work.id)
        assert item_tampered.latest_assessment is not None
        assert item_tampered.latest_assessment.is_stale is True
        assert item_tampered.primary_state == "STALE_ASSESSMENT"
    finally:
        answer.content_digest = original_answer_digest
        db_session.flush()

    # D. Tamper evaluation content digest ('1'*64) -> read detects stale assessment, write rejects 409
    try:
        evaluation.content_digest = "1" * 64
        db_session.flush()

        item_eval_tampered = service.get_assessment_work_item(principal, tenant_ctx, work.id)
        assert item_eval_tampered.latest_assessment is not None
        assert item_eval_tampered.latest_assessment.is_stale is True
        assert item_eval_tampered.primary_state == "STALE_ASSESSMENT"

        with pytest.raises(HTTPException) as exc_eval_write:
            new_req_eval = valid_pass_req.model_copy(
                update={"operation_id": uuid4(), "expected_assessment_revision": 1}
            )
            service.record_assessment(principal, tenant_ctx, work.id, new_req_eval)
        assert exc_eval_write.value.status_code == 409
        assert "Evaluation content digest mismatch" in str(exc_eval_write.value.detail)
    finally:
        evaluation.content_digest = original_eval_digest
        db_session.flush()

    # E. Tamper evaluation results -> write rejects 409, read detects stale
    try:
        tampered_results = [dict(r) for r in original_eval_results]
        if tampered_results:
            tampered_results[0]["result"] = "FAIL"
        evaluation.results = tampered_results
        db_session.flush()

        with pytest.raises(HTTPException) as exc_eval_res:
            new_req_res = valid_pass_req.model_copy(
                update={"operation_id": uuid4(), "expected_assessment_revision": 1}
            )
            service.record_assessment(principal, tenant_ctx, work.id, new_req_res)
        assert exc_eval_res.value.status_code == 409
        assert "Evaluation results mismatch" in str(exc_eval_res.value.detail)
    finally:
        evaluation.results = original_eval_results
        db_session.flush()

    # F. Tamper adoption bundle digest -> write rejects 409
    try:
        adoption.bundle_digest = "2" * 64
        db_session.flush()

        with pytest.raises(HTTPException) as exc_bundle:
            new_req_bundle = valid_pass_req.model_copy(
                update={"operation_id": uuid4(), "expected_assessment_revision": 1}
            )
            service.record_assessment(principal, tenant_ctx, work.id, new_req_bundle)
        assert exc_bundle.value.status_code == 409
        assert "bundle digest mismatch" in str(exc_bundle.value.detail)
    finally:
        adoption.bundle_digest = original_bundle_digest
        db_session.flush()

    # G. Final clean read
    clean_item = service.get_assessment_work_item(principal, tenant_ctx, work.id)
    assert clean_item.primary_state == "PASS"
    assert clean_item.latest_assessment is not None
    assert clean_item.latest_assessment.is_stale is False


@pytest.mark.parametrize(
    "field,tampered_val",
    [
        ("evaluator_version", "corrupt-version"),
        ("pack_version_id", uuid4()),
        ("bundle_digest", "0" * 64),
        ("answer_revision", 99),
    ],
)
def test_read_chain_evaluation_metadata_tampering_probes(
    db_session: Session, test_setup: dict[str, Any], field: str, tampered_val: Any
):
    """Verify that changing saved evaluation pack, bundle, answer revision, or evaluator version
    does not leave historical PASS marked current in item, list, summary, or replay projection."""
    service = CustomerAssessmentService(db_session)
    work = test_setup["work"]
    principal = test_setup["owner_p"]
    tenant_ctx = test_setup["owner_t"]
    ws = db_session.scalar(
        select(CustomerDemoWorkspace).where(CustomerDemoWorkspace.tenant_id == tenant_ctx.tenant_id)
    )
    assert ws is not None
    proc = service.get_procedure(principal, tenant_ctx, work.id)

    adoption = db_session.scalar(
        select(CustomerDemoAdoption).where(
            CustomerDemoAdoption.tenant_id == tenant_ctx.tenant_id,
            CustomerDemoAdoption.selection_revision == ws.selection_revision,
        )
    )
    assert adoption is not None

    evaluation = db_session.scalar(
        select(CustomerDemoEvaluation).where(
            CustomerDemoEvaluation.tenant_id == tenant_ctx.tenant_id,
            CustomerDemoEvaluation.id == adoption.evaluation_id,
        )
    )
    assert evaluation is not None

    valid_pass_req = AssessmentCreateRequest(
        operation_id=uuid4(),
        expected_answer_revision=ws.current_revision,
        expected_selection_revision=ws.selection_revision,
        expected_work_version=work.version,
        expected_assessment_revision=0,
        procedure_id=proc.id,
        procedure_version=proc.version,
        procedure_digest=proc.digest,
        result="PASS",
        rationale="Valid initial pass for read chain verification",
        criterion_results=[
            AssessmentCriterionResultDto(criterion_id="implementation", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="evidence", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="operation", result="PASS"),
        ],
        evidence_link_ids=[test_setup["link_id"]],
    )

    # Record valid PASS assessment
    res = service.record_assessment(principal, tenant_ctx, work.id, valid_pass_req)
    assert res.current_item.primary_state == "PASS"
    assert res.current_item.latest_assessment is not None
    assert res.current_item.latest_assessment.is_stale is False

    # Verify baseline clean read across all projection endpoints
    baseline_item = service.get_assessment_work_item(principal, tenant_ctx, work.id)
    assert baseline_item.primary_state == "PASS"
    assert baseline_item.latest_assessment is not None
    assert baseline_item.latest_assessment.is_stale is False

    baseline_list = service.get_assessment_work_list(principal, tenant_ctx)
    assert baseline_list.summary.pass_count == 1
    assert baseline_list.summary.stale_assessment == 0
    matched_item = next(i for i in baseline_list.items if i.work_id == work.id)
    assert matched_item.primary_state == "PASS"
    assert matched_item.latest_assessment is not None
    assert matched_item.latest_assessment.is_stale is False

    baseline_summary = service._compute_summary(
        tenant_ctx.tenant_id, principal=principal, tenant_context=tenant_ctx
    )
    assert baseline_summary.pass_count == 1
    assert baseline_summary.stale_assessment == 0

    replay_res = service.record_assessment(principal, tenant_ctx, work.id, valid_pass_req)
    assert replay_res.replayed is True
    assert replay_res.current_item.primary_state == "PASS"
    assert replay_res.summary.pass_count == 1

    # Tamper evaluation metadata field
    orig_val = getattr(evaluation, field)
    try:
        setattr(evaluation, field, tampered_val)
        db_session.flush()

        # 1. Item read projection must detect stale and not mark PASS
        item_tampered = service.get_assessment_work_item(principal, tenant_ctx, work.id)
        assert item_tampered.latest_assessment is not None
        assert item_tampered.latest_assessment.is_stale is True
        assert item_tampered.primary_state == "STALE_ASSESSMENT"
        assert "ASSESSMENT_STALE" in item_tampered.blockers

        # 2. List read projection must reflect STALE_ASSESSMENT and 0 pass_count
        list_tampered = service.get_assessment_work_list(principal, tenant_ctx)
        assert list_tampered.summary.pass_count == 0
        assert list_tampered.summary.stale_assessment >= 1
        assert work.control_id in list_tampered.summary.blocked_control_ids
        matched_t = next(i for i in list_tampered.items if i.work_id == work.id)
        assert matched_t.primary_state == "STALE_ASSESSMENT"
        assert matched_t.latest_assessment is not None
        assert matched_t.latest_assessment.is_stale is True

        # 3. Summary computation projection must reflect STALE_ASSESSMENT
        summary_tampered = service._compute_summary(
            tenant_ctx.tenant_id, principal=principal, tenant_context=tenant_ctx
        )
        assert summary_tampered.pass_count == 0
        assert summary_tampered.stale_assessment >= 1
        assert work.control_id in summary_tampered.blocked_control_ids

        # 4. Exact replay projection must return STALE_ASSESSMENT and 0 pass_count
        replay_tampered = service.record_assessment(principal, tenant_ctx, work.id, valid_pass_req)
        assert replay_tampered.replayed is True
        assert replay_tampered.current_item.primary_state == "STALE_ASSESSMENT"
        assert replay_tampered.current_item.latest_assessment is not None
        assert replay_tampered.current_item.latest_assessment.is_stale is True
        assert replay_tampered.summary.pass_count == 0
    finally:
        setattr(evaluation, field, orig_val)
        db_session.flush()

    # Verify restoration returns cleanly to PASS
    restored_item = service.get_assessment_work_item(principal, tenant_ctx, work.id)
    assert restored_item.primary_state == "PASS"
    assert restored_item.latest_assessment is not None
    assert restored_item.latest_assessment.is_stale is False


def test_read_chain_adoption_association_mismatch_probes(
    db_session: Session, test_setup: dict[str, Any]
):
    """Verify that tampering adoption pack version, bundle digest, or evaluation id
    marks assessment stale in read projection."""
    service = CustomerAssessmentService(db_session)
    work = test_setup["work"]
    principal = test_setup["owner_p"]
    tenant_ctx = test_setup["owner_t"]
    ws = db_session.scalar(
        select(CustomerDemoWorkspace).where(CustomerDemoWorkspace.tenant_id == tenant_ctx.tenant_id)
    )
    assert ws is not None
    proc = service.get_procedure(principal, tenant_ctx, work.id)

    adoption = db_session.scalar(
        select(CustomerDemoAdoption).where(
            CustomerDemoAdoption.tenant_id == tenant_ctx.tenant_id,
            CustomerDemoAdoption.selection_revision == ws.selection_revision,
        )
    )
    assert adoption is not None

    valid_pass_req = AssessmentCreateRequest(
        operation_id=uuid4(),
        expected_answer_revision=ws.current_revision,
        expected_selection_revision=ws.selection_revision,
        expected_work_version=work.version,
        expected_assessment_revision=0,
        procedure_id=proc.id,
        procedure_version=proc.version,
        procedure_digest=proc.digest,
        result="PASS",
        rationale="Valid initial pass for adoption mismatch test",
        criterion_results=[
            AssessmentCriterionResultDto(criterion_id="implementation", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="evidence", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="operation", result="PASS"),
        ],
        evidence_link_ids=[test_setup["link_id"]],
    )

    res = service.record_assessment(principal, tenant_ctx, work.id, valid_pass_req)
    assert res.current_item.primary_state == "PASS"

    # Probe A: adoption.pack_version_id mismatch
    orig_pack = adoption.pack_version_id
    try:
        adoption.pack_version_id = uuid4()
        db_session.flush()

        item = service.get_assessment_work_item(principal, tenant_ctx, work.id)
        assert item.latest_assessment is not None
        assert item.latest_assessment.is_stale is True
        assert item.primary_state in ("STALE_ASSESSMENT", "STALE_WORK")
    finally:
        adoption.pack_version_id = orig_pack
        db_session.flush()

    # Probe B: adoption.evaluation_id mismatch
    orig_eval_id = adoption.evaluation_id
    try:
        adoption.evaluation_id = uuid4()
        db_session.flush()

        item = service.get_assessment_work_item(principal, tenant_ctx, work.id)
        assert item.latest_assessment is not None
        assert item.latest_assessment.is_stale is True
        assert item.primary_state in ("STALE_ASSESSMENT", "STALE_WORK", "NEEDS_INFORMATION")
        assert item.primary_state != "PASS"
    finally:
        adoption.evaluation_id = orig_eval_id
        db_session.flush()


def test_read_chain_missing_required_encrypted_snapshot_fields_fails_closed(
    db_session: Session, test_setup: dict[str, Any]
):
    """Verify that assessment events missing required encrypted snapshot fields fail closed to STALE_ASSESSMENT."""
    import json

    from conformly.crypto.types import EncryptionContext
    from conformly.customer_demo.assessment_models import CustomerAssessmentEvent

    service = CustomerAssessmentService(db_session)
    work = test_setup["work"]
    principal = test_setup["owner_p"]
    tenant_ctx = test_setup["owner_t"]
    ws = db_session.scalar(
        select(CustomerDemoWorkspace).where(CustomerDemoWorkspace.tenant_id == tenant_ctx.tenant_id)
    )
    assert ws is not None
    proc = service.get_procedure(principal, tenant_ctx, work.id)

    valid_pass_req = AssessmentCreateRequest(
        operation_id=uuid4(),
        expected_answer_revision=ws.current_revision,
        expected_selection_revision=ws.selection_revision,
        expected_work_version=work.version,
        expected_assessment_revision=0,
        procedure_id=proc.id,
        procedure_version=proc.version,
        procedure_digest=proc.digest,
        result="PASS",
        rationale="Valid initial pass for missing fields test",
        criterion_results=[
            AssessmentCriterionResultDto(criterion_id="implementation", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="evidence", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="operation", result="PASS"),
        ],
        evidence_link_ids=[test_setup["link_id"]],
    )

    res = service.record_assessment(principal, tenant_ctx, work.id, valid_pass_req)
    event_id = res.event_id

    event = db_session.scalar(
        select(CustomerAssessmentEvent).where(
            CustomerAssessmentEvent.tenant_id == tenant_ctx.tenant_id,
            CustomerAssessmentEvent.id == event_id,
        )
    )
    assert event is not None
    orig_enc = event.details_encrypted

    # Re-encrypt with missing required fields (omit evaluation_id and pack_version_id)
    ctx = EncryptionContext(
        tenant_id=tenant_ctx.tenant_id,
        resource_type="customer_assessment_event",
        resource_id=str(event.id),
        field_name="details",
    )
    dec_text = service.codec.decrypt_text(orig_enc, ctx)
    det = json.loads(dec_text)
    del det["evaluation_id"]
    del det["pack_version_id"]

    try:
        event.details_encrypted = service.codec.encrypt_text(json.dumps(det), ctx)
        db_session.flush()

        item = service.get_assessment_work_item(principal, tenant_ctx, work.id)
        assert item.latest_assessment is not None
        assert item.latest_assessment.is_stale is True
        assert item.primary_state in ("STALE_ASSESSMENT", "STALE_WORK")
    finally:
        event.details_encrypted = orig_enc
        db_session.flush()


def test_assessment_service_concurrent_idempotency_replay_under_lock(
    test_setup: dict[str, Any], db_session: Session
) -> None:
    """Verify that concurrent identical operation ID returns replayed receipt rather than false 409 stale-CAS."""
    service = CustomerAssessmentService(db_session)
    work = test_setup["work"]
    principal = test_setup["owner_p"]
    tenant_ctx = test_setup["owner_t"]
    link_id = test_setup["link_id"]
    shared_op_id = uuid4()

    proc = service.get_procedure(principal, tenant_ctx, work.id)

    req = AssessmentCreateRequest(
        operation_id=shared_op_id,
        expected_answer_revision=1,
        expected_selection_revision=1,
        expected_work_version=work.version,
        expected_assessment_revision=0,
        procedure_id=proc.id,
        procedure_version=proc.version,
        procedure_digest=proc.digest,
        result="FAIL",
        criterion_results=[
            AssessmentCriterionResultDto(criterion_id="implementation", result="FAIL"),
            AssessmentCriterionResultDto(criterion_id="evidence", result="FAIL"),
            AssessmentCriterionResultDto(criterion_id="operation", result="FAIL"),
        ],
        evidence_link_ids=[link_id],
        finding=FindingCreateSpecificationDto(severity="HIGH"),
        rationale="Initial human assessment for idempotency test",
    )

    # 1. First execution succeeds (head revision becomes 1)
    receipt1 = service.record_assessment(principal, tenant_ctx, work.id, req)
    assert receipt1.replayed is False
    assert receipt1.applied_revision == 1
    db_session.commit()

    # 2. Concurrent second execution with identical payload and expected_assessment_revision=0
    # Before our fix, this would fail with 'Conflict: Stale expected assessment revision' because head revision is 1.
    # With the under-lock idempotency check, it returns the replayed receipt cleanly!
    receipt2 = service.record_assessment(principal, tenant_ctx, work.id, req)
    assert receipt2.replayed is True
    assert receipt2.event_id == receipt1.event_id
    assert receipt2.applied_revision == 1

    # 3. Third execution with SAME operation_id but DIFFERENT payload raises 409 Conflict
    mismatched_req = AssessmentCreateRequest(
        operation_id=shared_op_id,
        expected_answer_revision=1,
        expected_selection_revision=1,
        expected_work_version=work.version,
        expected_assessment_revision=0,
        procedure_id=proc.id,
        procedure_version=proc.version,
        procedure_digest=proc.digest,
        result="PASS",
        criterion_results=[
            AssessmentCriterionResultDto(criterion_id="implementation", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="evidence", result="PASS"),
            AssessmentCriterionResultDto(criterion_id="operation", result="PASS"),
        ],
        evidence_link_ids=[link_id],
        rationale="Mismatched rationale for conflict check",
    )
    with pytest.raises(HTTPException) as exc_info:
        service.record_assessment(principal, tenant_ctx, work.id, mismatched_req)
    assert exc_info.value.status_code == 409
    assert "different request parameters" in exc_info.value.detail
