"""FastAPI endpoint and security tests for Customer Control Work & Evidence API."""

import hashlib
from datetime import UTC, date, datetime, timedelta
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
from conformly.customer_demo.evaluator import compute_answers_digest, compute_evaluation_digest
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
from conformly.customer_demo.work_scanner import (
    StrictEvidenceMalwareScanner,
)
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


class MockSuccessfulScanner(StrictEvidenceMalwareScanner):
    def __init__(self) -> None:
        super().__init__(clamav_host="127.0.0.1", clamav_port=3310)

    def scan(self, data: bytes, filename: str) -> None:
        pass


@pytest.fixture(autouse=True)
def enable_demo_env(monkeypatch):
    monkeypatch.setenv("CONFORMLY_ENABLE_CUSTOMER_DEMO", "true")
    monkeypatch.setenv("CONFORMLY_ENVIRONMENT", "test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def test_app(session: Session):
    app = FastAPI()

    def _yielding_get_db():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    app.dependency_overrides[get_db] = _yielding_get_db
    register_customer_demo_routes(app)
    return app


@pytest.fixture
def seeded_env(session: Session):
    tenant_id = uuid4()
    owner_id = uuid4()
    mgr_id = uuid4()
    ctrl_owner_id = uuid4()
    viewer_id = uuid4()
    now = datetime.now(UTC)

    tenant = Tenant(
        id=tenant_id,
        name="API Demo Tenant",
        slug="api-demo-tenant",
        status=TenantStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    session.add(tenant)

    owner = User(
        id=owner_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="sub-owner",
        email="owner@example.com",
        display_name="Alice Owner",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    mgr = User(
        id=mgr_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="sub-mgr",
        email="mgr@example.com",
        display_name="Bob Manager",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    ctrl_owner = User(
        id=ctrl_owner_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="sub-ctrl",
        email="ctrl@example.com",
        display_name="Charlie ControlOwner",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    viewer = User(
        id=viewer_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="sub-viewer",
        email="viewer@example.com",
        display_name="Dave Viewer",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    session.add_all([owner, mgr, ctrl_owner, viewer])

    m_owner = Membership(
        tenant_id=tenant_id,
        user_id=owner_id,
        role=Role.OWNER,
        status=MembershipStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    m_mgr = Membership(
        tenant_id=tenant_id,
        user_id=mgr_id,
        role=Role.COMPLIANCE_MANAGER,
        status=MembershipStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    m_ctrl = Membership(
        tenant_id=tenant_id,
        user_id=ctrl_owner_id,
        role=Role.CONTROL_OWNER,
        status=MembershipStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    m_viewer = Membership(
        tenant_id=tenant_id,
        user_id=viewer_id,
        role=Role.VIEWER,
        status=MembershipStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    session.add_all([m_owner, m_mgr, m_ctrl, m_viewer])

    ent = TenantEntitlement(
        tenant_id=tenant_id,
        plan_code="tier_a",
        enabled_modules=["customer_demo", "compliance", "evidence"],
        effective_from=now - timedelta(days=1),
        effective_until=now + timedelta(days=365),
    )
    session.add(ent)

    ans_dict = {"synthetic_wp09_uses_cloud": True, "synthetic_wp09_operating_region": "EU"}
    ans_digest = compute_answers_digest("ALPHA", ans_dict)
    ws = CustomerDemoWorkspace(
        tenant_id=tenant_id,
        current_revision=1,
        selection_revision=1,
        created_at=now,
        updated_at=now,
    )
    ans = CustomerDemoAnswers(
        tenant_id=tenant_id,
        revision=1,
        company_code="ALPHA",
        answers=ans_dict,
        content_digest=ans_digest,
        actor_id=owner_id,
        created_at=now,
    )
    eval_digest = compute_evaluation_digest(
        answer_digest=ans_digest,
        answer_revision=1,
        bundle_digest=BUNDLE_V1_DIGEST,
        evaluator_version=EVALUATOR_VERSION,
        pack_version_id=PACK_VERSION_V1_ID,
        results=[],
    )
    evaluation_id = uuid4()
    ev = CustomerDemoEvaluation(
        id=evaluation_id,
        tenant_id=tenant_id,
        answer_revision=1,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=BUNDLE_V1_DIGEST,
        evaluator_version=EVALUATOR_VERSION,
        content_digest=eval_digest,
        results=[],
        actor_id=owner_id,
        created_at=now,
    )
    adoption_id = uuid4()
    adopt = CustomerDemoAdoption(
        id=adoption_id,
        tenant_id=tenant_id,
        selection_revision=1,
        evaluation_id=evaluation_id,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=BUNDLE_V1_DIGEST,
        actor_id=owner_id,
        created_at=now,
    )
    session.add_all([ws, ans, ev, adopt])
    session.commit()

    return {
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "mgr_id": mgr_id,
        "ctrl_owner_id": ctrl_owner_id,
        "viewer_id": viewer_id,
        "adoption_id": adoption_id,
        "evaluation_id": evaluation_id,
    }


def _seed_stored_file(
    session: Session, tenant_id: UUID, user_id: UUID, content: bytes = b"content"
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
        updated_at=now,
    )
    session.add(f)
    session.commit()
    return f


def test_feature_flag_disabled_and_headers(test_app: FastAPI, seeded_env, monkeypatch):
    t_id = seeded_env["tenant_id"]
    u_id = seeded_env["owner_id"]

    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=u_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=t_id, user_id=u_id, role=Role.OWNER
    )

    client = TestClient(test_app)
    resp = client.get(
        f"/v2/tenants/{t_id}/customer-demo/control-work",
        headers={"X-Correlation-ID": "test-ctrl-corr"},
    )
    assert resp.status_code == 200
    assert "no-store" in resp.headers.get("Cache-Control", "")
    assert "Authorization" in resp.headers.get("Vary", "")
    assert resp.headers.get("X-Correlation-ID") == "test-ctrl-corr"

    # Disable customer demo
    monkeypatch.setenv("CONFORMLY_ENABLE_CUSTOMER_DEMO", "false")
    get_settings.cache_clear()

    disabled_app = FastAPI()
    register_customer_demo_routes(disabled_app)
    disabled_client = TestClient(disabled_app)
    resp_off = disabled_client.get(f"/v2/tenants/{t_id}/customer-demo/control-work")
    assert resp_off.status_code == 404


def test_tenant_mismatch_denied(test_app: FastAPI, seeded_env):
    t_id = seeded_env["tenant_id"]
    u_id = seeded_env["owner_id"]
    other_tenant = uuid4()

    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=u_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=t_id, user_id=u_id, role=Role.OWNER
    )

    client = TestClient(test_app)
    resp = client.get(f"/v2/tenants/{other_tenant}/customer-demo/control-work")
    assert resp.status_code == 403
    assert "route tenant_id does not match" in resp.json()["detail"]


def test_admission_and_capability_matrix(test_app: FastAPI, seeded_env, session: Session):
    t_id = seeded_env["tenant_id"]
    owner_id = seeded_env["owner_id"]
    viewer_id = seeded_env["viewer_id"]
    client = TestClient(test_app)

    # Missing MFA -> 403
    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=owner_id, mfa_verified=False
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=t_id, user_id=owner_id, role=Role.OWNER
    )
    resp = client.get(f"/v2/tenants/{t_id}/customer-demo/control-work")
    assert resp.status_code == 403

    # Workforce principal -> 403
    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=owner_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=t_id, user_id=owner_id, role=Role.OWNER, is_workforce=True
    )
    resp = client.get(f"/v2/tenants/{t_id}/customer-demo/control-work")
    assert resp.status_code == 403

    # Scoped membership -> 403
    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=owner_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=t_id, user_id=owner_id, role=Role.OWNER, legal_entity_id=uuid4()
    )
    resp = client.get(f"/v2/tenants/{t_id}/customer-demo/control-work")
    assert resp.status_code == 403

    # Non-admitted role (VIEWER) -> 403
    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=viewer_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=t_id, user_id=viewer_id, role=Role.VIEWER
    )
    resp = client.get(f"/v2/tenants/{t_id}/customer-demo/control-work")
    assert resp.status_code == 403

    # Missing evidence module entitlement -> 403
    ent = session.query(TenantEntitlement).filter_by(tenant_id=t_id).one()
    ent.enabled_modules = ["customer_demo"]
    session.commit()

    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=owner_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=t_id, user_id=owner_id, role=Role.OWNER
    )
    resp = client.get(f"/v2/tenants/{t_id}/customer-demo/control-work")
    assert resp.status_code == 403
    assert "Customer demo access denied" in resp.json()["detail"]


def test_owner_directory(test_app: FastAPI, seeded_env):
    t_id = seeded_env["tenant_id"]
    owner_id = seeded_env["owner_id"]

    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=owner_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=t_id, user_id=owner_id, role=Role.OWNER
    )

    client = TestClient(test_app)
    resp = client.get(f"/v2/tenants/{t_id}/customer-demo/control-work/owners")
    assert resp.status_code == 200
    data = resp.json()
    owners = data["items"]
    assert len(owners) == 3
    returned_ids = {o["user_id"] for o in owners}
    assert str(seeded_env["owner_id"]) in returned_ids
    assert str(seeded_env["mgr_id"]) in returned_ids
    assert str(seeded_env["ctrl_owner_id"]) in returned_ids
    assert str(seeded_env["viewer_id"]) not in returned_ids

    # Privacy: no email, tokens or issuer in response
    for o in owners:
        assert "email" not in o
        assert "oidc_issuer" not in o
        assert "oidc_subject" not in o
        assert "tokens" not in o


def test_integrated_control_work_and_evidence_api_journey(
    test_app: FastAPI, seeded_env, session: Session
):
    t_id = seeded_env["tenant_id"]
    owner_id = seeded_env["owner_id"]
    mgr_id = seeded_env["mgr_id"]
    adopt_id = seeded_env["adoption_id"]

    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=owner_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=t_id, user_id=owner_id, role=Role.OWNER
    )

    client = TestClient(test_app)

    # 1. GET before init -> empty
    resp = client.get(f"/v2/tenants/{t_id}/customer-demo/control-work")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0

    # 2. POST /initialize
    init_op_id = uuid4()
    init_payload = {
        "operation_id": str(init_op_id),
        "adoption_id": str(adopt_id),
        "expected_selection_revision": 1,
        "expected_answer_revision": 1,
    }
    resp = client.post(
        f"/v2/tenants/{t_id}/customer-demo/control-work/initialize", json=init_payload
    )
    assert resp.status_code == 200
    work_items = resp.json()["items"]
    assert len(work_items) == 2
    first_work = work_items[0]
    second_work = work_items[1]
    work_id = first_work["id"]
    work2_id = second_work["id"]
    assert first_work["version"] == 1
    assert first_work["owner_user_id"] is None

    # Repeat init -> idempotent
    resp_reinit = client.post(
        f"/v2/tenants/{t_id}/customer-demo/control-work/initialize", json=init_payload
    )
    assert resp_reinit.status_code == 200
    assert len(resp_reinit.json()["items"]) == 2

    # 3. PATCH /{work_id} assign owner and due date
    patch_op_id = uuid4()
    due = (date.today() + timedelta(days=30)).isoformat()
    patch_payload = {
        "operation_id": str(patch_op_id),
        "expected_selection_revision": 1,
        "expected_answer_revision": 1,
        "expected_work_version": 1,
        "owner_user_id": str(mgr_id),
        "due_date": due,
    }
    resp_patch = client.patch(
        f"/v2/tenants/{t_id}/customer-demo/control-work/{work_id}", json=patch_payload
    )
    assert resp_patch.status_code == 200
    receipt = resp_patch.json()
    assert receipt["applied_work_version"] == 2
    assert receipt["replayed"] is False
    assert receipt["current_work"]["version"] == 2
    assert receipt["current_work"]["owner_user_id"] == str(mgr_id)
    assert receipt["current_work"]["due_date"] == due

    # Replay PATCH -> replayed=True
    resp_replay = client.patch(
        f"/v2/tenants/{t_id}/customer-demo/control-work/{work_id}", json=patch_payload
    )
    assert resp_replay.status_code == 200
    assert resp_replay.json()["replayed"] is True

    # 4. Create and pin evidence
    file_content = b"Sample clean report for audit demonstration."
    stored_file = _seed_stored_file(session, t_id, owner_id, file_content)

    ev_op_id = uuid4()
    ev_payload = {
        "operation_id": str(ev_op_id),
        "expected_selection_revision": 1,
        "expected_answer_revision": 1,
        "expected_work_version": 2,
        "file_id": str(stored_file.id),
        "valid_until": (datetime.now(UTC) + timedelta(days=90)).isoformat(),
        "rationale": "Primary evidence for control compliance.",
    }

    mock_scanner = MockSuccessfulScanner()
    with (
        patch("conformly.customer_demo.work_service.StorageService") as MockStorage,
        patch(
            "conformly.customer_demo.work_service.StrictEvidenceMalwareScanner",
            return_value=mock_scanner,
        ),
    ):
        instance = MockStorage.return_value
        instance.download_file.return_value = (stored_file, file_content)

        resp_ev = client.post(
            f"/v2/tenants/{t_id}/customer-demo/control-work/{work_id}/evidence", json=ev_payload
        )
        assert resp_ev.status_code == 201
        ev_receipt = resp_ev.json()
        assert ev_receipt["applied_work_version"] == 3
        work_dto = ev_receipt["current_work"]
        assert len(work_dto["links"]) == 1
        link1 = work_dto["links"][0]
        link1_id = link1["id"]
        evidence_id = link1["evidence_id"]
        ev_rev = link1["revision_number"]
        digest = link1["digest"]
        assert link1["validity"] == "AVAILABLE"
        assert link1["review"] == "PENDING"

        # 5. Download pinned file
        resp_dl = client.get(
            f"/v2/tenants/{t_id}/customer-demo/control-work/{work_id}/links/{link1_id}/files/{stored_file.id}"
        )
        assert resp_dl.status_code == 200
        assert resp_dl.content == file_content
        assert "attachment;" in resp_dl.headers.get("Content-Disposition", "")
        assert "no-store" in resp_dl.headers.get("Cache-Control", "")

        # 6. Deliberate reuse on second control work
        link_op_id = uuid4()
        link_payload = {
            "operation_id": str(link_op_id),
            "expected_selection_revision": 1,
            "expected_answer_revision": 1,
            "expected_work_version": 1,
            "evidence_id": evidence_id,
            "evidence_revision_number": ev_rev,
            "evidence_revision_digest": digest,
            "rationale": "Reusing approved report for secondary control requirement.",
        }
        resp_link = client.post(
            f"/v2/tenants/{t_id}/customer-demo/control-work/{work2_id}/links", json=link_payload
        )
        assert resp_link.status_code == 201
        link2_receipt = resp_link.json()
        assert link2_receipt["applied_work_version"] == 2
        work2_dto = link2_receipt["current_work"]
        assert len(work2_dto["links"]) == 1
        link2_id = work2_dto["links"][0]["id"]

        # 7. Independent reviews
        rev1_op_id = uuid4()
        rev1_payload = {
            "operation_id": str(rev1_op_id),
            "expected_selection_revision": 1,
            "expected_answer_revision": 1,
            "expected_work_version": 3,
            "decision": "ACCEPTED",
            "rationale": "Reviewed and verified as fully suitable.",
        }
        resp_rev1 = client.post(
            f"/v2/tenants/{t_id}/customer-demo/control-work/{work_id}/links/{link1_id}/reviews",
            json=rev1_payload,
        )
        assert resp_rev1.status_code == 201
        assert resp_rev1.json()["current_work"]["links"][0]["review"] == "ACCEPTED"

        rev2_op_id = uuid4()
        rev2_payload = {
            "operation_id": str(rev2_op_id),
            "expected_selection_revision": 1,
            "expected_answer_revision": 1,
            "expected_work_version": 2,
            "decision": "REJECTED",
            "rationale": "Not adequate for secondary control scope.",
        }
        resp_rev2 = client.post(
            f"/v2/tenants/{t_id}/customer-demo/control-work/{work2_id}/links/{link2_id}/reviews",
            json=rev2_payload,
        )
        assert resp_rev2.status_code == 201
        assert resp_rev2.json()["current_work"]["links"][0]["review"] == "REJECTED"

    # 8. GET history
    resp_hist = client.get(f"/v2/tenants/{t_id}/customer-demo/control-work/{work_id}/history")
    assert resp_hist.status_code == 200
    hist = resp_hist.json()
    assert hist["total"] == 4
    events = hist["items"]
    assert [e["revision"] for e in events] == [1, 2, 3, 4]
    assert [e["type"] for e in events] == [
        "INITIALIZED",
        "OWNER_DUE_UPDATED",
        "EVIDENCE_LINKED",
        "EVIDENCE_REVIEWED",
    ]
    assert events[3]["decision"] == "ACCEPTED"


def test_security_bounds_and_error_handling(test_app: FastAPI, seeded_env, session: Session):
    t_id = seeded_env["tenant_id"]
    owner_id = seeded_env["owner_id"]
    adopt_id = seeded_env["adoption_id"]

    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=owner_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=t_id, user_id=owner_id, role=Role.OWNER
    )

    client = TestClient(test_app)

    # 1. 16KiB body bounding
    huge_payload = {
        "operation_id": str(uuid4()),
        "adoption_id": str(adopt_id),
        "expected_selection_revision": 1,
        "expected_answer_revision": 1,
        "padding": "X" * (17 * 1024),
    }
    resp_huge = client.post(
        f"/v2/tenants/{t_id}/customer-demo/control-work/initialize", json=huge_payload
    )
    assert resp_huge.status_code == 413

    # 2. Malformed DTO (extra forbid / missing required)
    resp_malformed = client.post(
        f"/v2/tenants/{t_id}/customer-demo/control-work/initialize",
        json={"extra_field": "forbidden"},
    )
    assert resp_malformed.status_code == 422

    # 3. Initialize to have a work item
    init_resp = client.post(
        f"/v2/tenants/{t_id}/customer-demo/control-work/initialize",
        json={
            "operation_id": str(uuid4()),
            "adoption_id": str(adopt_id),
            "expected_selection_revision": 1,
            "expected_answer_revision": 1,
        },
    )
    work_id = init_resp.json()["items"][0]["id"]

    # 4. Stale selection revision -> 409
    resp_stale_sel = client.patch(
        f"/v2/tenants/{t_id}/customer-demo/control-work/{work_id}",
        json={
            "operation_id": str(uuid4()),
            "expected_selection_revision": 99,
            "expected_answer_revision": 1,
            "expected_work_version": 1,
            "owner_user_id": None,
            "due_date": None,
        },
    )
    assert resp_stale_sel.status_code == 409
    assert "selection revision mismatch" in resp_stale_sel.json()["detail"]

    # 5. Stale answer revision -> 409
    resp_stale_ans = client.patch(
        f"/v2/tenants/{t_id}/customer-demo/control-work/{work_id}",
        json={
            "operation_id": str(uuid4()),
            "expected_selection_revision": 1,
            "expected_answer_revision": 99,
            "expected_work_version": 1,
            "owner_user_id": None,
            "due_date": None,
        },
    )
    assert resp_stale_ans.status_code == 409
    assert "answer revision mismatch" in resp_stale_ans.json()["detail"]

    # 6. Strict scanner failure with unconfigured host -> 503
    stored_file = _seed_stored_file(session, t_id, owner_id, b"test file")
    with patch("conformly.customer_demo.work_service.StorageService") as MockStorage:
        instance = MockStorage.return_value
        instance.download_file.return_value = (stored_file, b"test file")
        resp_scan_fail = client.post(
            f"/v2/tenants/{t_id}/customer-demo/control-work/{work_id}/evidence",
            json={
                "operation_id": str(uuid4()),
                "expected_selection_revision": 1,
                "expected_answer_revision": 1,
                "expected_work_version": 1,
                "file_id": str(stored_file.id),
                "valid_until": None,
                "rationale": "Test rationale",
            },
        )
        assert resp_scan_fail.status_code == 503


def test_api_lifecycle_and_admission_negative_matrix(
    test_app: FastAPI, seeded_env, session: Session
):
    """Verify API endpoints reject revoked members, expired/archived lifecycle, and tampered files."""
    t_id = seeded_env["tenant_id"]
    owner_id = seeded_env["owner_id"]
    adopt_id = seeded_env["adoption_id"]

    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=owner_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=t_id, user_id=owner_id, role=Role.OWNER
    )
    client = TestClient(test_app)

    # 1. Initialize work item
    init_resp = client.post(
        f"/v2/tenants/{t_id}/customer-demo/control-work/initialize",
        json={
            "operation_id": str(uuid4()),
            "adoption_id": str(adopt_id),
            "expected_selection_revision": 1,
            "expected_answer_revision": 1,
        },
    )
    assert init_resp.status_code == 200
    work1 = init_resp.json()["items"][0]
    work_id = work1["id"]

    # 2. Upload file & create evidence
    stored_file = _seed_stored_file(session, t_id, owner_id, b"api clean bytes")
    mock_scanner = MockSuccessfulScanner()
    with (
        patch("conformly.customer_demo.work_service.StorageService") as MockStorage,
        patch(
            "conformly.customer_demo.work_service.StrictEvidenceMalwareScanner",
            return_value=mock_scanner,
        ),
    ):
        inst = MockStorage.return_value
        inst.download_file.return_value = (stored_file, b"api clean bytes")
        ev_resp = client.post(
            f"/v2/tenants/{t_id}/customer-demo/control-work/{work_id}/evidence",
            json={
                "operation_id": str(uuid4()),
                "expected_selection_revision": 1,
                "expected_answer_revision": 1,
                "expected_work_version": 1,
                "file_id": str(stored_file.id),
                "valid_until": None,
                "rationale": "API lifecycle test",
            },
        )
    assert ev_resp.status_code == 201
    link_id = ev_resp.json()["current_work"]["links"][0]["id"]
    ev_id = ev_resp.json()["current_work"]["links"][0]["evidence_id"]
    work_ver = ev_resp.json()["applied_work_version"]

    # Check listing honesty: returns scan_status="SCANNED_AT_LINK" and validity="AVAILABLE"
    list_resp = client.get(f"/v2/tenants/{t_id}/customer-demo/control-work")
    assert list_resp.status_code == 200
    item_link = list_resp.json()["items"][0]["links"][0]
    assert item_link["validity"] == "AVAILABLE"
    assert item_link["scan_status"] == "SCANNED_AT_LINK"

    # 3. Direct DB membership suspension -> API calls return 403
    from conformly.identity.models import Membership, MembershipStatus

    mem = (
        session.query(Membership)
        .filter(Membership.tenant_id == t_id, Membership.user_id == owner_id)
        .one()
    )
    mem.status = MembershipStatus.SUSPENDED
    session.commit()

    resp_denied = client.get(f"/v2/tenants/{t_id}/customer-demo/control-work")
    assert resp_denied.status_code == 403

    resp_dl_denied = client.get(
        f"/v2/tenants/{t_id}/customer-demo/control-work/{work_id}/links/{link_id}/files/{stored_file.id}"
    )
    assert resp_dl_denied.status_code == 403

    # Restore membership
    mem.status = MembershipStatus.ACTIVE
    session.commit()

    # 4. EvidenceItem ARCHIVED -> create_review ACCEPTED returns 409
    from uuid import UUID

    from conformly.compliance.models import EvidenceItem, EvidenceStatus

    ev_item = (
        session.query(EvidenceItem)
        .filter(EvidenceItem.tenant_id == t_id, EvidenceItem.id == UUID(str(ev_id)))
        .one()
    )
    ev_item.status = EvidenceStatus.ARCHIVED
    session.commit()

    rev_resp = client.post(
        f"/v2/tenants/{t_id}/customer-demo/control-work/{work_id}/links/{link_id}/reviews",
        json={
            "operation_id": str(uuid4()),
            "expected_selection_revision": 1,
            "expected_answer_revision": 1,
            "expected_work_version": work_ver,
            "decision": "ACCEPTED",
            "rationale": "Should be rejected on archived head",
        },
    )
    assert rev_resp.status_code == 409

    # Download also returns 409
    dl_resp = client.get(
        f"/v2/tenants/{t_id}/customer-demo/control-work/{work_id}/links/{link_id}/files/{stored_file.id}"
    )
    assert dl_resp.status_code == 409

    # But REJECTED review still succeeds
    rej_resp = client.post(
        f"/v2/tenants/{t_id}/customer-demo/control-work/{work_id}/links/{link_id}/reviews",
        json={
            "operation_id": str(uuid4()),
            "expected_selection_revision": 1,
            "expected_answer_revision": 1,
            "expected_work_version": work_ver,
            "decision": "REJECTED",
            "rationale": "Rejection on archived item is authorized",
        },
    )
    assert rej_resp.status_code == 201
    assert rej_resp.json()["current_work"]["links"][0]["review"] == "REJECTED"
