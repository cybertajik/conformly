"""Unit tests for customer demo service layer, optimistic concurrency, and audit logging."""

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from conformly.audit.models import AuditEvent
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.config import get_settings
from conformly.customer_demo.fixture import (
    EVALUATOR_VERSION,
    FACT_CLOUD_V1_ID,
    FACT_REGION_V1_ID,
    PACK_VERSION_V1_ID,
    PACK_2_VERSION_V1_ID,
    PACK_2_VERSION_V2_ID,
    BUNDLE_2_V1_DIGEST,
    BUNDLE_2_V2_DIGEST,
)
from conformly.customer_demo.models import (
    CustomerDemoAnswers,
    CustomerDemoWorkspace,
)
from conformly.customer_demo.policy import (
    CustomerDemoAdmissionError,
    CustomerDemoDisabledError,
)
from conformly.customer_demo.service import (
    adopt_evaluation,
    evaluate_answers,
    get_workspace_data,
    save_answers,
)
from conformly.db.base import Base
from conformly.identity.models import Tenant, TenantStatus, User


@pytest.fixture(autouse=True)
def enable_customer_demo_feature(monkeypatch):
    """Enable customer demo feature and test environment for all unit tests."""
    cfg = get_settings()
    monkeypatch.setattr(cfg, "enable_customer_demo", True)
    monkeypatch.setattr(cfg, "environment", "test")


@pytest.fixture
def db_session():
    """In-memory SQLite session with all tables created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def fixture_tenant_and_user(db_session: Session):
    """Seed tenant and user records for FK validity."""
    tenant_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    tenant = Tenant(
        id=tenant_id,
        name="Test Tenant Alpha",
        slug="test-tenant-alpha",
        status=TenantStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    user = User(
        id=user_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="sub-123",
        email="compliance@example.com",
        display_name="Compliance Manager",
        created_at=now,
        updated_at=now,
    )
    db_session.add(tenant)
    db_session.add(user)
    db_session.commit()
    return tenant_id, user_id


@pytest.fixture
def valid_contexts(fixture_tenant_and_user):
    tenant_id, user_id = fixture_tenant_and_user
    principal = Principal(user_id=user_id, mfa_verified=True)
    tenant_context = TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        role=Role.COMPLIANCE_MANAGER,
    )
    return principal, tenant_context


def test_get_workspace_initial(db_session: Session, valid_contexts):
    """Verify initial read returns revision 0 and emits read audit event."""
    principal, tenant_context = valid_contexts

    data = get_workspace_data(db_session, principal, tenant_context, "req-1")
    assert data["tenant_id"] == tenant_context.tenant_id
    assert data["current_revision"] == 0
    assert data["selection_revision"] == 0
    assert data["answers"] is None
    assert data["selected_pack"] is None
    assert len(data["manifest"]["packs"]) == 4
    assert len({p["pack_id"] for p in data["manifest"]["packs"]}) == 2

    # Verify audit event emitted
    audit = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.tenant_id == tenant_context.tenant_id)
        .first()
    )
    assert audit is not None
    assert audit.action == "customer_demo.workspace.read"
    assert audit.safe_metadata["revision_number"] == 0


def test_save_answers_success_and_conflict(db_session: Session, valid_contexts):
    """Verify answer saving increments revision and 409 on revision conflict."""
    principal, tenant_context = valid_contexts
    tenant_id = tenant_context.tenant_id

    # Initial save: expected_revision = 0 -> saves revision 1
    raw = {"synthetic_wp09_uses_cloud": True, "synthetic_wp09_operating_region": "EU"}
    ans1 = save_answers(
        db_session,
        principal,
        tenant_context,
        expected_revision=0,
        company_code="ALPHA",
        raw_answers=raw,
        request_id="req-2",
    )
    assert ans1.revision == 1
    assert ans1.company_code == "ALPHA"
    assert len(ans1.content_digest) == 64

    # Workspace updated
    ws = (
        db_session.query(CustomerDemoWorkspace)
        .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
        .first()
    )
    assert ws is not None
    assert ws.current_revision == 1

    # Conflict: saving with expected_revision = 0 again raises 409
    with pytest.raises(HTTPException) as exc_info:
        save_answers(
            db_session,
            principal,
            tenant_context,
            expected_revision=0,
            company_code="ALPHA",
            raw_answers=raw,
            request_id="req-3",
        )
    assert exc_info.value.status_code == 409

    # Second save: expected_revision = 1 -> saves revision 2
    raw2 = {"synthetic_wp09_uses_cloud": False, "synthetic_wp09_operating_region": "OTHER"}
    ans2 = save_answers(
        db_session,
        principal,
        tenant_context,
        expected_revision=1,
        company_code="BETA",
        raw_answers=raw2,
        request_id="req-4",
    )
    assert ans2.revision == 2
    assert ans2.company_code == "BETA"
    assert ans2.content_digest != ans1.content_digest


def test_evaluate_answers_success_and_validation(db_session: Session, valid_contexts):
    """Verify evaluation computation, version validation, and snapshot persistence."""
    principal, tenant_context = valid_contexts

    # Cannot evaluate without answers
    with pytest.raises(HTTPException) as exc_info:
        evaluate_answers(
            db_session,
            principal,
            tenant_context,
            expected_revision=1,
            pack_version_id=PACK_VERSION_V1_ID,
            request_id="req-5",
        )
    assert exc_info.value.status_code in (400, 409)

    # Save answers (cloud=True, region=EU)
    raw = {"synthetic_wp09_uses_cloud": True, "synthetic_wp09_operating_region": "EU"}
    save_answers(
        db_session,
        principal,
        tenant_context,
        expected_revision=0,
        company_code="ALPHA",
        raw_answers=raw,
        request_id="req-6",
    )

    # Positive evaluation
    ev = evaluate_answers(
        db_session,
        principal,
        tenant_context,
        expected_revision=1,
        pack_version_id=PACK_VERSION_V1_ID,
        request_id="req-7",
    )
    assert ev.answer_revision == 1
    assert ev.pack_version_id == PACK_VERSION_V1_ID
    assert len(ev.results) == 2
    assert ev.results[0]["result"] == "APPLICABLE"
    assert ev.results[1]["result"] == "APPLICABLE"
    assert len(ev.content_digest) == 64

    # Stale revision conflict: expected_revision = 2 when workspace is at 1
    with pytest.raises(HTTPException) as exc_info:
        evaluate_answers(
            db_session,
            principal,
            tenant_context,
            expected_revision=2,
            pack_version_id=PACK_VERSION_V1_ID,
            request_id="req-8",
        )
    assert exc_info.value.status_code == 409

    # Unknown pack version ID
    with pytest.raises(HTTPException) as exc_info:
        evaluate_answers(
            db_session,
            principal,
            tenant_context,
            expected_revision=1,
            pack_version_id=uuid4(),
            request_id="req-9",
        )
    assert exc_info.value.status_code == 404


def test_adopt_evaluation_flow_idempotency_and_stale(db_session: Session, valid_contexts):
    """Verify adoption flow, idempotent retry, missing info acknowledgement, and stale invalidation."""
    principal, tenant_context = valid_contexts
    tenant_id = tenant_context.tenant_id

    # Save partial answers: cloud=True, region unknown
    raw = {"synthetic_wp09_uses_cloud": True}
    save_answers(
        db_session,
        principal,
        tenant_context,
        expected_revision=0,
        company_code="ALPHA",
        raw_answers=raw,
        request_id="req-10",
    )

    # Evaluate against v1 -> produces NEEDS_INFORMATION on req 2
    ev = evaluate_answers(
        db_session,
        principal,
        tenant_context,
        expected_revision=1,
        pack_version_id=PACK_VERSION_V1_ID,
        request_id="req-11",
    )
    assert ev.results[1]["result"] == "NEEDS_INFORMATION"

    # Adopt without synthetic acknowledgement -> 422
    with pytest.raises(HTTPException) as exc_info:
        adopt_evaluation(
            db_session,
            principal,
            tenant_context,
            expected_revision=1,
            evaluation_id=ev.id,
            pack_version_id=PACK_VERSION_V1_ID,
            acknowledge_synthetic=False,
            acknowledge_missing_information=True,
            request_id="req-12",
        )
    assert exc_info.value.status_code == 422

    # Adopt without missing information acknowledgement when NEEDS_INFORMATION present -> 422
    with pytest.raises(HTTPException) as exc_info:
        adopt_evaluation(
            db_session,
            principal,
            tenant_context,
            expected_revision=1,
            evaluation_id=ev.id,
            pack_version_id=PACK_VERSION_V1_ID,
            acknowledge_synthetic=True,
            acknowledge_missing_information=False,
            request_id="req-13",
        )
    assert exc_info.value.status_code == 422

    # Positive adoption with both acknowledgements
    adopt_res = adopt_evaluation(
        db_session,
        principal,
        tenant_context,
        expected_revision=1,
        evaluation_id=ev.id,
        pack_version_id=PACK_VERSION_V1_ID,
        acknowledge_synthetic=True,
        acknowledge_missing_information=True,
        request_id="req-14",
    )
    assert adopt_res["selection_revision"] == 1
    assert adopt_res["is_current"] is True

    audit_count_before = (
        db_session.query(AuditEvent)
        .filter(
            AuditEvent.tenant_id == tenant_id, AuditEvent.action == "customer_demo.adoption.create"
        )
        .count()
    )
    assert audit_count_before == 1

    # Idempotent retry on same evaluation
    retry_res = adopt_evaluation(
        db_session,
        principal,
        tenant_context,
        expected_revision=1,
        evaluation_id=ev.id,
        pack_version_id=PACK_VERSION_V1_ID,
        acknowledge_synthetic=True,
        acknowledge_missing_information=True,
        request_id="req-15",
    )
    assert retry_res["id"] == adopt_res["id"]
    assert retry_res["selection_revision"] == 1
    assert retry_res["is_current"] is True

    # No duplicate audit event emitted on retry!
    audit_count_after = (
        db_session.query(AuditEvent)
        .filter(
            AuditEvent.tenant_id == tenant_id, AuditEvent.action == "customer_demo.adoption.create"
        )
        .count()
    )
    assert audit_count_after == 1

    # Now change answers to revision 2
    save_answers(
        db_session,
        principal,
        tenant_context,
        expected_revision=1,
        company_code="BETA",
        raw_answers={"synthetic_wp09_uses_cloud": False},
        request_id="req-16",
    )

    # Adopting the old evaluation (revision 1) when workspace is at 2 raises 409
    with pytest.raises(HTTPException) as exc_info:
        adopt_evaluation(
            db_session,
            principal,
            tenant_context,
            expected_revision=1,
            evaluation_id=ev.id,
            pack_version_id=PACK_VERSION_V1_ID,
            acknowledge_synthetic=True,
            acknowledge_missing_information=True,
            request_id="req-17",
        )
    assert exc_info.value.status_code == 409


def test_audit_failure_causes_rollback(db_session: Session, valid_contexts):
    """Verify that a failure during audit event recording rolls back business writes."""
    principal, tenant_context = valid_contexts
    tenant_id = tenant_context.tenant_id

    raw = {"synthetic_wp09_uses_cloud": True}

    with patch(
        "conformly.customer_demo.service.record_audit_event",
        side_effect=RuntimeError("Audit disk full"),
    ):
        with pytest.raises(RuntimeError, match="Audit disk full"):
            save_answers(
                db_session,
                principal,
                tenant_context,
                expected_revision=0,
                company_code="ALPHA",
                raw_answers=raw,
                request_id="req-fail",
            )

    # Verify no answers record persisted
    ans_count = (
        db_session.query(CustomerDemoAnswers)
        .filter(CustomerDemoAnswers.tenant_id == tenant_id)
        .count()
    )
    assert ans_count == 0

    # Workspace revision remained 0
    ws = (
        db_session.query(CustomerDemoWorkspace)
        .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
        .first()
    )
    assert ws is None or ws.current_revision == 0


def test_service_admission_mfa_required(db_session: Session, valid_contexts):
    """Verify MFA requirement is strictly enforced on both read and mutate entries."""
    _, tenant_context = valid_contexts
    unverified_principal = Principal(user_id=tenant_context.user_id, mfa_verified=False)

    with pytest.raises(CustomerDemoAdmissionError, match="MFA verification required"):
        get_workspace_data(db_session, unverified_principal, tenant_context, "req-mfa-read")

    with pytest.raises(CustomerDemoAdmissionError, match="MFA verification required"):
        save_answers(
            db_session,
            unverified_principal,
            tenant_context,
            expected_revision=0,
            company_code="ALPHA",
            raw_answers={"synthetic_wp09_uses_cloud": True},
            request_id="req-mfa-write",
        )


def test_service_admission_tenant_active_required(db_session: Session, valid_contexts):
    """Verify mutations fail if tenant lifecycle is not ACTIVE (R3)."""
    principal, tenant_context = valid_contexts
    tenant = db_session.query(Tenant).filter(Tenant.id == tenant_context.tenant_id).first()
    assert tenant is not None
    tenant.status = TenantStatus.SUSPENDED
    db_session.commit()

    with pytest.raises(CustomerDemoAdmissionError) as exc_info:
        save_answers(
            db_session,
            principal,
            tenant_context,
            expected_revision=0,
            company_code="ALPHA",
            raw_answers={"synthetic_wp09_uses_cloud": True},
            request_id="req-suspended",
        )
    assert exc_info.value.status_code == 409


def test_service_admission_workforce_and_advisor_prohibited(db_session: Session, valid_contexts):
    """Verify workforce and external advisors are denied entry (R3)."""
    principal, tenant_context = valid_contexts

    workforce_ctx = TenantContext(
        tenant_id=tenant_context.tenant_id,
        user_id=tenant_context.user_id,
        role=Role.OWNER,
        is_workforce=True,
    )
    with pytest.raises(CustomerDemoAdmissionError, match="Workforce access denied"):
        get_workspace_data(db_session, principal, workforce_ctx, "req-wf")

    advisor_ctx = TenantContext(
        tenant_id=tenant_context.tenant_id,
        user_id=tenant_context.user_id,
        role=Role.OWNER,
        is_external_advisor=True,
    )
    with pytest.raises(CustomerDemoAdmissionError, match="External advisor access denied"):
        get_workspace_data(db_session, principal, advisor_ctx, "req-adv")


def test_service_admission_feature_disabled_and_environment(
    monkeypatch, db_session: Session, valid_contexts
):
    """Verify 404 when disabled and 403 when environment prohibited (R3)."""
    principal, tenant_context = valid_contexts
    cfg = get_settings()

    monkeypatch.setattr(cfg, "enable_customer_demo", False)
    with pytest.raises(CustomerDemoDisabledError):
        get_workspace_data(db_session, principal, tenant_context, "req-disabled")

    monkeypatch.setattr(cfg, "enable_customer_demo", True)
    monkeypatch.setattr(cfg, "environment", "production")
    with pytest.raises(CustomerDemoAdmissionError, match="prohibited in non-development"):
        get_workspace_data(db_session, principal, tenant_context, "req-prod")


def test_adopt_evaluation_tamper_refusal(db_session: Session, valid_contexts):
    """Verify R5 snapshot integrity checks refuse tampered evaluations."""
    principal, tenant_context = valid_contexts

    raw = {"synthetic_wp09_uses_cloud": True, "synthetic_wp09_operating_region": "EU"}
    save_answers(
        db_session,
        principal,
        tenant_context,
        expected_revision=0,
        company_code="ALPHA",
        raw_answers=raw,
        request_id="req-save",
    )
    ev = evaluate_answers(
        db_session,
        principal,
        tenant_context,
        expected_revision=1,
        pack_version_id=PACK_VERSION_V1_ID,
        request_id="req-eval",
    )

    # 1. Tampered evaluator version
    ev.evaluator_version = "evaluator_v_tampered"
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        adopt_evaluation(
            db_session,
            principal,
            tenant_context,
            expected_revision=1,
            evaluation_id=ev.id,
            pack_version_id=PACK_VERSION_V1_ID,
            acknowledge_synthetic=True,
            acknowledge_missing_information=True,
            request_id="req-t1",
        )
    assert exc.value.status_code == 422
    assert "Incompatible evaluator version" in exc.value.detail

    # Restore evaluator_version
    ev.evaluator_version = EVALUATOR_VERSION
    db_session.commit()

    # 2. Tampered bundle digest
    ev.bundle_digest = "0000000000000000000000000000000000000000000000000000000000000000"
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        adopt_evaluation(
            db_session,
            principal,
            tenant_context,
            expected_revision=1,
            evaluation_id=ev.id,
            pack_version_id=PACK_VERSION_V1_ID,
            acknowledge_synthetic=True,
            acknowledge_missing_information=True,
            request_id="req-t2",
        )
    assert exc.value.status_code == 422
    assert "Invalid bundle digest" in exc.value.detail

    # Restore bundle_digest and tamper answers digest
    from conformly.customer_demo.fixture import get_bundle_digest

    ev.bundle_digest = get_bundle_digest(PACK_VERSION_V1_ID)
    ans_row = (
        db_session.query(CustomerDemoAnswers).filter(CustomerDemoAnswers.revision == 1).first()
    )
    assert ans_row is not None
    orig_ans_digest = ans_row.content_digest
    ans_row.content_digest = "1111111111111111111111111111111111111111111111111111111111111111"
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        adopt_evaluation(
            db_session,
            principal,
            tenant_context,
            expected_revision=1,
            evaluation_id=ev.id,
            pack_version_id=PACK_VERSION_V1_ID,
            acknowledge_synthetic=True,
            acknowledge_missing_information=True,
            request_id="req-t3",
        )
    assert exc.value.status_code == 422
    assert "Corrupted answers content digest" in exc.value.detail

    # Restore answers digest and tamper evaluation content_digest (lineage)
    ans_row.content_digest = orig_ans_digest
    ev.content_digest = "2222222222222222222222222222222222222222222222222222222222222222"
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        adopt_evaluation(
            db_session,
            principal,
            tenant_context,
            expected_revision=1,
            evaluation_id=ev.id,
            pack_version_id=PACK_VERSION_V1_ID,
            acknowledge_synthetic=True,
            acknowledge_missing_information=True,
            request_id="req-t4",
        )
    assert exc.value.status_code == 422
    assert "Corrupted evaluation content digest or invalid lineage" in exc.value.detail


def test_adopt_evaluation_insertion_based_tampering_refusal(db_session, fixture_tenant_and_user):
    """Verify adopt_evaluation rejects an inserted evaluation with tampered results even if hash is internally valid (P2)."""
    tenant_id, user_id = fixture_tenant_and_user
    principal = Principal(user_id=user_id, mfa_verified=True)
    tenant_context = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.OWNER)

    # 1. Save valid answers (cloud=False -> beta facts)
    from conformly.customer_demo.evaluator import (
        compute_evaluation_digest,
        evaluate_bundle,
    )
    from conformly.customer_demo.fixture import (
        FACT_CLOUD_V1_ID,
        get_bundle_digest,
    )
    from conformly.customer_demo.models import CustomerDemoEvaluation

    facts = {str(FACT_CLOUD_V1_ID): False}
    ans = save_answers(
        db_session,
        principal,
        tenant_context,
        expected_revision=0,
        company_code="BETA",
        raw_answers=facts,
        request_id="req-ins-1",
    )

    # True evaluation has result NOT_APPLICABLE for req-1
    true_results = evaluate_bundle(PACK_VERSION_V1_ID, ans.answers)
    assert true_results[0]["result"] == "NOT_APPLICABLE"

    # Insert a tampered evaluation row claiming APPLICABLE, computing a self-consistent digest
    import copy

    tampered_results = copy.deepcopy(true_results)
    tampered_results[0]["result"] = "APPLICABLE"
    tampered_results[0]["explanation_tree"]["result"] = "APPLICABLE"
    bundle_digest = get_bundle_digest(PACK_VERSION_V1_ID)

    self_consistent_digest = compute_evaluation_digest(
        answer_digest=ans.content_digest,
        answer_revision=1,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=bundle_digest,
        results=tampered_results,
    )

    tampered_eval = CustomerDemoEvaluation(
        tenant_id=tenant_id,
        answer_revision=1,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=bundle_digest,
        evaluator_version=EVALUATOR_VERSION,
        results=tampered_results,
        content_digest=self_consistent_digest,
        actor_id=user_id,
    )
    db_session.add(tampered_eval)
    db_session.commit()

    # Attempt adoption of the inserted tampered evaluation
    with pytest.raises(HTTPException) as exc:
        adopt_evaluation(
            db_session,
            principal,
            tenant_context,
            expected_revision=1,
            evaluation_id=tampered_eval.id,
            pack_version_id=PACK_VERSION_V1_ID,
            acknowledge_synthetic=True,
            acknowledge_missing_information=True,
            request_id="req-ins-adopt",
        )
    assert exc.value.status_code == 422
    assert "Evaluation results mismatch deterministic evaluation" in exc.value.detail


def test_service_transaction_rollback_on_errors(db_session, fixture_tenant_and_user):
    """Verify service operations roll back complete transaction and do not persist workspace row on rejected operations (P1)."""
    tenant_id, user_id = fixture_tenant_and_user
    principal = Principal(user_id=user_id, mfa_verified=True)
    tenant_context = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.OWNER)

    # Calling save_answers with invalid payload fails before/during transaction
    with pytest.raises(HTTPException) as exc:
        save_answers(
            db_session,
            principal,
            tenant_context,
            expected_revision=0,
            company_code="ALPHA",
            raw_answers={"bad_field": 12345},
            request_id="req-err-1",
        )
    assert exc.value.status_code == 422

    # Workspace row must NOT exist or be committed
    ws = (
        db_session.query(CustomerDemoWorkspace)
        .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
        .first()
    )
    assert ws is None


def test_pack_2_evaluation_and_adoption_lifecycle(db_session, fixture_tenant_and_user):
    """Verify evaluation, deterministic results, and adoption for second synthetic pack (Pack 2)."""
    tenant_id, user_id = fixture_tenant_and_user
    principal = Principal(user_id=user_id, mfa_verified=True)
    tenant_context = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.OWNER)

    # Save answers
    saved = save_answers(
        db_session,
        principal,
        tenant_context,
        expected_revision=0,
        company_code="ALPHA",
        raw_answers={
            str(FACT_CLOUD_V1_ID): True,
            str(FACT_REGION_V1_ID): "EU",
        },
        request_id="req-p2-answers",
    )
    assert saved.revision == 1

    # Evaluate Pack 2 v1
    eval_res = evaluate_answers(
        db_session,
        principal,
        tenant_context,
        expected_revision=1,
        pack_version_id=PACK_2_VERSION_V1_ID,
        request_id="req-p2-eval-1",
    )
    assert eval_res.pack_version_id == PACK_2_VERSION_V1_ID
    assert eval_res.bundle_digest == BUNDLE_2_V1_DIGEST
    assert len(eval_res.results) == 3

    # Adopt Pack 2 v1
    adopt_res = adopt_evaluation(
        db_session,
        principal,
        tenant_context,
        expected_revision=1,
        evaluation_id=eval_res.id,
        pack_version_id=PACK_2_VERSION_V1_ID,
        acknowledge_synthetic=True,
        acknowledge_missing_information=True,
        request_id="req-p2-adopt-1",
    )
    assert adopt_res["is_current"] is True
    assert adopt_res["current_pack_version_id"] == PACK_2_VERSION_V1_ID
    assert adopt_res["current_selection_revision"] == 1
    assert adopt_res["bundle_digest"] == BUNDLE_2_V1_DIGEST


def test_cross_pack_replacement_preserves_history_and_replaces_current(db_session, fixture_tenant_and_user):
    """Verify adopting Pack 2 replaces Pack 1 as current adoption while preserving history."""
    tenant_id, user_id = fixture_tenant_and_user
    principal = Principal(user_id=user_id, mfa_verified=True)
    tenant_context = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.OWNER)

    # Setup answers
    save_answers(
        db_session,
        principal,
        tenant_context,
        expected_revision=0,
        company_code="ALPHA",
        raw_answers={
            str(FACT_CLOUD_V1_ID): True,
            str(FACT_REGION_V1_ID): "EU",
        },
        request_id="req-cp-answers",
    )

    # 1. Adopt Pack 1 v1
    eval_p1 = evaluate_answers(
        db_session,
        principal,
        tenant_context,
        expected_revision=1,
        pack_version_id=PACK_VERSION_V1_ID,
        request_id="req-cp-eval-p1",
    )
    adopt_p1 = adopt_evaluation(
        db_session,
        principal,
        tenant_context,
        expected_revision=1,
        evaluation_id=eval_p1.id,
        pack_version_id=PACK_VERSION_V1_ID,
        acknowledge_synthetic=True,
        acknowledge_missing_information=True,
        request_id="req-cp-adopt-p1",
    )
    assert adopt_p1["current_selection_revision"] == 1
    assert adopt_p1["current_pack_version_id"] == PACK_VERSION_V1_ID

    # 2. Evaluate and adopt Pack 2 v1 (cross-pack replacement!)
    eval_p2 = evaluate_answers(
        db_session,
        principal,
        tenant_context,
        expected_revision=1,
        pack_version_id=PACK_2_VERSION_V1_ID,
        request_id="req-cp-eval-p2",
    )
    adopt_p2 = adopt_evaluation(
        db_session,
        principal,
        tenant_context,
        expected_revision=1,
        evaluation_id=eval_p2.id,
        pack_version_id=PACK_2_VERSION_V1_ID,
        acknowledge_synthetic=True,
        acknowledge_missing_information=True,
        request_id="req-cp-adopt-p2",
    )
    assert adopt_p2["current_selection_revision"] == 2
    assert adopt_p2["current_pack_version_id"] == PACK_2_VERSION_V1_ID

    # 3. Verify workspace state and history
    ws_data = get_workspace_data(db_session, principal, tenant_context, "req-cp-ws")
    assert ws_data["selection_revision"] == 2
    assert ws_data["selected_pack"]["pack_version_id"] == PACK_2_VERSION_V1_ID
    assert ws_data["selected_pack"]["bundle_digest"] == BUNDLE_2_V1_DIGEST

    # History contains both adoptions in sequence
    history = ws_data["history_summary"]
    assert len(history) == 2
    assert history[0]["selection_revision"] == 2
    assert history[0]["pack_version_id"] == str(PACK_2_VERSION_V1_ID)
    assert history[1]["selection_revision"] == 1
    assert history[1]["pack_version_id"] == str(PACK_VERSION_V1_ID)


def test_unknown_pack_version_fails_closed(db_session, fixture_tenant_and_user):
    """Verify evaluating or adopting an unknown pack version ID fails closed before writes."""
    tenant_id, user_id = fixture_tenant_and_user
    principal = Principal(user_id=user_id, mfa_verified=True)
    tenant_context = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.OWNER)

    unknown_id = uuid4()

    # Evaluation with unknown pack version -> 404
    with pytest.raises(HTTPException) as exc_eval:
        evaluate_answers(
            db_session,
            principal,
            tenant_context,
            expected_revision=1,
            pack_version_id=unknown_id,
            request_id="req-unknown-eval",
        )
    assert exc_eval.value.status_code == 404

    # Adoption with unknown pack version -> 400
    with pytest.raises(HTTPException) as exc_adopt:
        adopt_evaluation(
            db_session,
            principal,
            tenant_context,
            expected_revision=1,
            evaluation_id=uuid4(),
            pack_version_id=unknown_id,
            acknowledge_synthetic=True,
            acknowledge_missing_information=True,
            request_id="req-unknown-adopt",
        )
    assert exc_adopt.value.status_code == 400
