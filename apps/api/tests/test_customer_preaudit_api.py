"""FastAPI integration and endpoint security tests for Customer Pre-audit API (MVP-D).

Tests endpoints under /v2/tenants/{tenant_id}/customer-demo/preaudits:
- GET preaudits (list)
- GET preaudits/actors (eligible actors)
- POST preaudits (create pre-audit)
- GET preaudits/{id} (details, blockers, currentness)
- GET preaudits/{id}/history (immutable event history)
- POST preaudits/{id}/freeze (freeze scope snapshot)
- POST preaudits/{id}/submit (submit for review)
- POST preaudits/{id}/review (record review decision)
- POST preaudits/{id}/approve (owner approval)
- POST preaudits/{id}/cancel (cancel case)
- POST preaudits/{id}/report/download (private report archive)
- Security guards: feature flag guard, route-tenant isolation, role checks, self-review denial.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conformly.auth.dependencies import get_current_principal, get_tenant_context
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.config import get_settings
from conformly.crypto.policy import DataClassification
from conformly.customer_demo.api import register_customer_demo_routes
from conformly.customer_demo.assessment_schemas import (
    AssessmentCreateRequest,
    AssessmentCriterionResultDto,
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
from conformly.customer_demo.preaudit_service import CustomerPreauditService
from conformly.customer_demo.models import (
    CustomerDemoAdoption,
    CustomerDemoAnswers,
    CustomerDemoEvaluation,
    CustomerDemoWorkspace,
)
from conformly.customer_demo.work_models import CustomerControlWork
from conformly.customer_demo.work_schemas import (
    CreateEvidenceRequest,
    CreateReviewRequest,
    InitializeWorkRequest,
)
from conformly.customer_demo.work_service import CustomerControlWorkService
from conformly.db.session import get_db
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
from tests.test_customer_assessment_api import MockSuccessfulScanner


@pytest.fixture(autouse=True)
def enable_preaudit_env(monkeypatch: pytest.MonkeyPatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "enable_customer_demo", True)
    monkeypatch.setattr(cfg, "enable_customer_preaudit", True)
    monkeypatch.setattr(cfg, "environment", "test")
    yield


@pytest.fixture
def env_fixture(session: Session):
    tenant_id = uuid4()
    owner_id = uuid4()
    mgr_id = uuid4()
    reviewer_id = uuid4()
    employee_id = uuid4()
    now = datetime.now(UTC)

    tenant = Tenant(
        id=tenant_id,
        name="Pre-Audit API Demo Tenant",
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
            id=reviewer_id,
            oidc_issuer="https://auth.example.com",
            oidc_subject="sub-rev",
            email="reviewer@example.com",
            display_name="Carol Reviewer",
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
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=owner_id,
            role=Role.OWNER,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        Membership(
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=mgr_id,
            role=Role.COMPLIANCE_MANAGER,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        Membership(
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=reviewer_id,
            role=Role.COMPLIANCE_MANAGER,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        Membership(
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=employee_id,
            role=Role.EMPLOYEE,
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

    answers_data = {
        "synthetic_wp09_uses_cloud": True,
        "synthetic_wp09_operating_region": "EU",
    }
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
    work_svc = CustomerControlWorkService(session, scanner=MockSuccessfulScanner())
    owner_principal = Principal(user_id=owner_id, mfa_verified=True)
    t_ctx = TenantContext(tenant_id=tenant_id, user_id=owner_id, role=Role.OWNER)
    work_svc.initialize_work(
        owner_principal,
        t_ctx,
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
        "reviewer_id": reviewer_id,
        "employee_id": employee_id,
        "adoption_id": adoption.id,
    }


def _create_app(session: Session, user_id: UUID, tenant_id: UUID, role: Role) -> FastAPI:
    app = FastAPI()

    def _get_db_override():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=user_id,
        mfa_verified=True,
    )
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        role=role,
    )
    register_customer_demo_routes(app)
    return app


def test_feature_flag_guard(env_fixture, session, monkeypatch):
    from conformly.config import get_settings

    cfg = get_settings()
    monkeypatch.setattr(cfg, "enable_customer_preaudit", False)

    app = _create_app(session, env_fixture["owner_id"], env_fixture["tenant_id"], Role.OWNER)

    with TestClient(app) as client:
        res = client.get(f"/v2/tenants/{env_fixture['tenant_id']}/customer-demo/preaudits")
        assert res.status_code == 404


def test_route_tenant_mismatch(env_fixture, session):
    foreign_tenant_id = uuid4()
    app = _create_app(session, env_fixture["owner_id"], env_fixture["tenant_id"], Role.OWNER)

    with TestClient(app) as client:
        res = client.get(f"/v2/tenants/{foreign_tenant_id}/customer-demo/preaudits")
        assert res.status_code == 403


def test_role_admission_and_denials(env_fixture, session):
    # Employee cannot access preaudit endpoints
    emp_app = _create_app(session, env_fixture["employee_id"], env_fixture["tenant_id"], Role.EMPLOYEE)
    with TestClient(emp_app) as client:
        res = client.get(f"/v2/tenants/{env_fixture['tenant_id']}/customer-demo/preaudits")
        assert res.status_code == 403

    # Owner can access
    owner_app = _create_app(session, env_fixture["owner_id"], env_fixture["tenant_id"], Role.OWNER)
    with TestClient(owner_app) as client:
        res = client.get(f"/v2/tenants/{env_fixture['tenant_id']}/customer-demo/preaudits")
        assert res.status_code == 200


def test_eligible_actors_endpoint(env_fixture, session):
    app = _create_app(session, env_fixture["owner_id"], env_fixture["tenant_id"], Role.OWNER)
    with TestClient(app) as client:
        res = client.get(f"/v2/tenants/{env_fixture['tenant_id']}/customer-demo/preaudits/actors")
        assert res.status_code == 200
        data = res.json()
        assert "actors" in data
        actor_ids = [a["user_id"] for a in data["actors"]]
        assert str(env_fixture["owner_id"]) in actor_ids
        assert str(env_fixture["mgr_id"]) in actor_ids
        assert str(env_fixture["reviewer_id"]) in actor_ids


def test_create_preaudit_and_idempotency(env_fixture, session):
    app = _create_app(session, env_fixture["owner_id"], env_fixture["tenant_id"], Role.OWNER)
    op_id = str(uuid4())

    with TestClient(app) as client:
        payload = {
            "operation_id": op_id,
            "adoption_id": str(env_fixture["adoption_id"]),
            "lead_user_id": str(env_fixture["mgr_id"]),
            "reviewer_user_id": str(env_fixture["reviewer_id"]),
        }
        res = client.post(f"/v2/tenants/{env_fixture['tenant_id']}/customer-demo/preaudits", json=payload)
        assert res.status_code == 201
        case = res.json()
        assert case["status"] == "DRAFT"
        assert case["revision"] == 1
        assert case["lead_user_id"] == str(env_fixture["mgr_id"])
        assert case["reviewer_user_id"] == str(env_fixture["reviewer_id"])

        # Replay with same op_id returns identical case (200 OK on replay)
        res_replay = client.post(f"/v2/tenants/{env_fixture['tenant_id']}/customer-demo/preaudits", json=payload)
        assert res_replay.status_code in (200, 201)
        assert res_replay.json()["id"] == case["id"]


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


def test_full_workflow_state_machine_and_report_download(env_fixture, session):
    tenant_id = env_fixture["tenant_id"]

    owner_app = _create_app(session, env_fixture["owner_id"], tenant_id, Role.OWNER)
    mgr_app = _create_app(session, env_fixture["mgr_id"], tenant_id, Role.COMPLIANCE_MANAGER)
    rev_app = _create_app(session, env_fixture["reviewer_id"], tenant_id, Role.COMPLIANCE_MANAGER)

    # 1. Create case
    with TestClient(owner_app) as client:
        op_create = str(uuid4())
        res = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/preaudits",
            json={
                "operation_id": op_create,
                "adoption_id": str(env_fixture["adoption_id"]),
                "lead_user_id": str(env_fixture["mgr_id"]),
                "reviewer_user_id": str(env_fixture["reviewer_id"]),
            },
        )
        assert res.status_code == 201
        case_id = res.json()["id"]

        # Check details
        res_det = client.get(f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{case_id}")
        assert res_det.status_code == 200
        det = res_det.json()
        assert det["status"] == "DRAFT"
        assert det["blockers"] is not None

        # Check list
        res_list = client.get(f"/v2/tenants/{tenant_id}/customer-demo/preaudits")
        assert res_list.status_code == 200
        assert any(c["id"] == case_id for c in res_list.json()["items"])

    # 2. Freeze scope
    with TestClient(mgr_app) as client:
        op_freeze = str(uuid4())
        res_freeze = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{case_id}/freeze",
            json={"operation_id": op_freeze, "expected_revision": 1},
        )
        assert res_freeze.status_code == 200
        frozen = res_freeze.json()
        assert frozen["status"] == "FROZEN"
        assert frozen["current_scope_snapshot_id"] is not None

    # 3. Submit for review
    with TestClient(mgr_app) as client:
        op_sub = str(uuid4())
        res_sub = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{case_id}/submit",
            json={"operation_id": op_sub, "expected_revision": 2, "submission_notes": "Ready for preaudit"},
        )
        assert res_sub.status_code == 200
        in_rev = res_sub.json()
        assert in_rev["status"] == "IN_REVIEW"
        assert in_rev["current_review_snapshot_id"] is not None
        rev1_snap_id = in_rev["current_review_snapshot_id"]
        rev1_snap_digest = in_rev["current_review_snapshot_digest"]

    # 4. Self-review rejection: Lead attempts to review decision -> 403
    with TestClient(mgr_app) as client:
        res_bad_rev = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{case_id}/review",
            json={
                "operation_id": str(uuid4()),
                "expected_revision": 3,
                "snapshot_id": rev1_snap_id,
                "snapshot_digest": rev1_snap_digest,
                "decision": "ACCEPT",
                "notes": "Self review",
            },
        )
        assert res_bad_rev.status_code == 403

    # 5. Premature acceptance by reviewer fails closed with 409, then request changes
    with TestClient(rev_app) as client:
        res_premature = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{case_id}/review",
            json={
                "operation_id": str(uuid4()),
                "expected_revision": 3,
                "snapshot_id": rev1_snap_id,
                "snapshot_digest": rev1_snap_digest,
                "decision": "ACCEPT",
                "notes": "Premature acceptance",
            },
        )
        assert res_premature.status_code == 409

        # Review decision: REQUEST_CHANGES
        op_changes = str(uuid4())
        res_chg = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{case_id}/review",
            json={
                "operation_id": op_changes,
                "expected_revision": 3,
                "snapshot_id": rev1_snap_id,
                "snapshot_digest": rev1_snap_digest,
                "decision": "REQUEST_CHANGES",
                "notes": "Please verify evidence",
            },
        )
        assert res_chg.status_code == 200
        assert res_chg.json()["status"] == "CHANGES_REQUESTED"

    # 6. Re-submit after resolving blockers
    _seed_all_controls_passing(session, tenant_id, env_fixture["owner_id"])

    with TestClient(mgr_app) as client:
        op_resub = str(uuid4())
        res_resub = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{case_id}/submit",
            json={"operation_id": op_resub, "expected_revision": 4, "submission_notes": "Fixed evidence and cleared blockers"},
        )
        assert res_resub.status_code == 200
        assert res_resub.json()["status"] == "IN_REVIEW"
        latest_rev_snap_id = res_resub.json()["current_review_snapshot_id"]
        latest_rev_snap_digest = res_resub.json()["current_review_snapshot_digest"]

        # 7. Review decision: ACCEPT -> REVIEWED
        with TestClient(rev_app) as client:
            op_acc = str(uuid4())
            res_acc = client.post(
                f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{case_id}/review",
                json={
                    "operation_id": op_acc,
                    "expected_revision": 5,
                    "snapshot_id": latest_rev_snap_id,
                    "snapshot_digest": latest_rev_snap_digest,
                    "decision": "ACCEPT",
                    "notes": "Looks solid",
                },
            )
            assert res_acc.status_code == 200
            assert res_acc.json()["status"] == "REVIEWED"

    # 8. Non-owner cannot approve
    with TestClient(mgr_app) as client:
        res_bad_app = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{case_id}/approve",
            json={
                "operation_id": str(uuid4()),
                "expected_revision": 6,
                "snapshot_id": latest_rev_snap_id,
                "snapshot_digest": latest_rev_snap_digest,
                "approval_notes": "Manager approve",
            },
        )
        assert res_bad_app.status_code == 403

    # 9. Owner approval -> APPROVED
    with TestClient(owner_app) as client:
        op_app = str(uuid4())
        res_app = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{case_id}/approve",
            json={
                "operation_id": op_app,
                "expected_revision": 6,
                "snapshot_id": latest_rev_snap_id,
                "snapshot_digest": latest_rev_snap_digest,
                "approval_notes": "Approved by Owner",
            },
        )
        assert res_app.status_code == 200
        assert res_app.json()["status"] == "APPROVED"

    # 10. Check event history
    with TestClient(owner_app) as client:
        res_hist = client.get(f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{case_id}/history")
        assert res_hist.status_code == 200
        events = res_hist.json()["events"]
        assert len(events) == 7
        event_types = [e["event_type"] for e in events]
        assert event_types == [
            "CREATED",
            "SCOPE_FROZEN",
            "SUBMITTED",
            "CHANGES_REQUESTED",
            "SUBMITTED",
            "REVIEWED",
            "APPROVED",
        ]

    # 11. Download private report
    with TestClient(owner_app) as client:
        res_dl = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{case_id}/report/download",
            json={"expected_revision": 7, "snapshot_id": latest_rev_snap_id},
        )
        assert res_dl.status_code == 200
        assert res_dl.headers["content-type"] == "application/zip"
        assert res_dl.headers["x-preaudit-id"] == case_id
        assert "x-preaudit-snapshot-digest" in res_dl.headers
        assert "no-store" in res_dl.headers.get("cache-control", "")
        assert "x-report-sha256" in res_dl.headers
        assert res_dl.headers["x-report-sha256"] == hashlib.sha256(res_dl.content).hexdigest()

        zf = zipfile.ZipFile(io.BytesIO(res_dl.content))
        names = zf.namelist()
        assert "preaudit.json" in names
        assert "preaudit.html" in names
        assert "manifest.json" in names


def test_cancel_endpoint(env_fixture, session):
    tenant_id = env_fixture["tenant_id"]

    owner_app = _create_app(session, env_fixture["owner_id"], tenant_id, Role.OWNER)
    mgr_app = _create_app(session, env_fixture["mgr_id"], tenant_id, Role.COMPLIANCE_MANAGER)

    with TestClient(owner_app) as client:
        res = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/preaudits",
            json={
                "operation_id": str(uuid4()),
                "adoption_id": str(env_fixture["adoption_id"]),
                "lead_user_id": str(env_fixture["mgr_id"]),
                "reviewer_user_id": str(env_fixture["reviewer_id"]),
            },
        )
        assert res.status_code == 201
        case_id = res.json()["id"]

    # Manager cannot cancel
    with TestClient(mgr_app) as client:
        res_bad = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{case_id}/cancel",
            json={"operation_id": str(uuid4()), "expected_revision": 1, "reason": "Not needed"},
        )
        assert res_bad.status_code == 403

    # Owner can cancel
    with TestClient(owner_app) as client:
        res_cancel = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{case_id}/cancel",
            json={"operation_id": str(uuid4()), "expected_revision": 1, "reason": "Tenant decided to cancel"},
        )
        assert res_cancel.status_code == 200
        assert res_cancel.json()["status"] == "CANCELLED"


def test_boolean_revision_rejection(env_fixture, session):
    tenant_id = env_fixture["tenant_id"]
    mgr_app = _create_app(session, env_fixture["mgr_id"], tenant_id, Role.COMPLIANCE_MANAGER)

    with TestClient(mgr_app) as client:
        res = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{uuid4()}/freeze",
            json={"operation_id": str(uuid4()), "expected_revision": True},
        )
        assert res.status_code == 422


def test_payload_size_limit(env_fixture, session):
    tenant_id = env_fixture["tenant_id"]
    mgr_app = _create_app(session, env_fixture["mgr_id"], tenant_id, Role.COMPLIANCE_MANAGER)

    with TestClient(mgr_app) as client:
        large_note = "x" * 20000
        res = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/preaudits/{uuid4()}/submit",
            json={"operation_id": str(uuid4()), "expected_revision": 1, "submission_notes": large_note},
        )
        assert res.status_code in (413, 422)


def test_preaudit_api_replay_receipts(env_fixture, session):
    tenant_id = env_fixture["tenant_id"]
    mgr_app = _create_app(session, env_fixture["mgr_id"], tenant_id, Role.COMPLIANCE_MANAGER)
    op_id = str(uuid4())

    with TestClient(mgr_app) as client:
        payload = {
            "operation_id": op_id,
            "adoption_id": str(env_fixture["adoption_id"]),
            "lead_user_id": str(env_fixture["mgr_id"]),
            "reviewer_user_id": str(env_fixture["owner_id"]),
            "title": "API Replay Receipt Test",
        }
        res1 = client.post(f"/v2/tenants/{tenant_id}/customer-demo/preaudits", json=payload)
        assert res1.status_code == 201
        data1 = res1.json()
        assert data1["replayed"] is False
        assert data1["applied_event_id"] is not None
        assert data1["applied_revision"] == 1

        # Replay exact same payload with same operation_id
        res2 = client.post(f"/v2/tenants/{tenant_id}/customer-demo/preaudits", json=payload)
        assert res2.status_code == 201
        data2 = res2.json()
        assert data2["replayed"] is True
        assert data2["applied_event_id"] == data1["applied_event_id"]
        assert data2["applied_revision"] == data1["applied_revision"]
        assert data2["id"] == data1["id"]

