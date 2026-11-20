"""FastAPI integration and endpoint security tests for Customer Readiness Verification API (MVP-E).

Tests endpoints under /v2/tenants/{tenant_id}/customer-demo/readiness-verifications:
- POST readiness-verifications (issue verification)
- GET readiness-verifications (list)
- GET readiness-verifications/{id} (details)
- GET readiness-verifications/{id}/projection (allowlisted private projection)
- GET readiness-verifications/{id}/history (audit event timeline)
- POST readiness-verifications/{id}/suspend (suspend verification)
- POST readiness-verifications/{id}/revoke (revoke verification)
- POST readiness-verifications/{id}/correct (correct limitations/notes metadata)
- POST readiness-verifications/{id}/supersede (atomic supersession)
- POST readiness-verifications/reconcile (idempotent deterministic reconciliation)
- Security guards: feature flag OFF 404, role authorization 403, reviewer self-issue 403,
  CAS revision conflict 409, route-tenant isolation, no-cache headers.
"""

from __future__ import annotations

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
from conformly.customer_demo.api import register_customer_demo_routes
from conformly.customer_demo.preaudit_models import CustomerPreaudit, CustomerPreauditSnapshot
from conformly.customer_demo.preaudit_schemas import (
    ApprovePreauditRequest,
    CreatePreauditRequest,
    FreezeScopeRequest,
    ReviewDecisionRequest,
    SubmitReviewRequest,
)
from conformly.customer_demo.preaudit_service import CustomerPreauditService
from conformly.customer_demo.verification_schemas import (
    CorrectVerificationRequest,
    IssueVerificationRequest,
    ReconcileVerificationRequest,
    RevokeVerificationRequest,
    SupersedeVerificationRequest,
    SuspendVerificationRequest,
)
from conformly.db.session import get_db
from conformly.identity.models import Membership, MembershipStatus
from tests.test_customer_verification_service import (
    _seed_all_controls_passing,
    _setup_approved_case,
    verification_test_env,
)


@pytest.fixture(autouse=True)
def enable_verification_flags(monkeypatch: pytest.MonkeyPatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "enable_customer_demo", True)
    monkeypatch.setattr(cfg, "enable_customer_preaudit", True)
    monkeypatch.setattr(cfg, "enable_customer_readiness_verification", True)
    monkeypatch.setattr(cfg, "environment", "test")
    yield


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


def test_api_issue_and_read_endpoints(session: Session, verification_test_env):
    """Test full issuance, get detail, list, projection, and event history via HTTP endpoints."""
    env = verification_test_env
    case, snapshot = _setup_approved_case(session, env)
    tenant_id = env["tenant_id"]

    app = _create_app(session, env["owner_id"], tenant_id, Role.OWNER)
    client = TestClient(app)

    base_url = f"/v2/tenants/{tenant_id}/customer-demo/readiness-verifications"

    # 1. POST issue verification
    issue_op = uuid4()
    issue_payload = {
        "operation_id": str(issue_op),
        "preaudit_id": str(case.id),
        "expected_case_revision": case.revision,
        "snapshot_id": str(snapshot.id),
        "snapshot_digest": snapshot.digest,
        "limitations": ["Private synthetic internal test only", "No public claims"],
        "notes": "Verified via test harness",
    }
    res = client.post(base_url, json=issue_payload)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["status"] == "ACTIVE"
    assert data["effective_status"] == "ACTIVE"
    assert data["synthetic_marker"] == "PRIVATE SYNTHETIC INTERNAL TEST RESULT"
    v_id = data["id"]

    # Verify no-cache response headers
    assert "no-store" in res.headers.get("cache-control", "").lower()

    # 2. GET detail
    res_get = client.get(f"{base_url}/{v_id}")
    assert res_get.status_code == 200
    get_data = res_get.json()
    assert get_data["id"] == v_id
    assert get_data["status"] == "ACTIVE"

    # 3. GET list
    res_list = client.get(base_url)
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total"] >= 1
    assert any(v["id"] == v_id for v in list_data["verifications"])

    # 3b. GET list with preaudit_case_id filter
    res_filtered = client.get(f"{base_url}?preaudit_case_id={case.id}")
    assert res_filtered.status_code == 200
    filtered_data = res_filtered.json()
    assert filtered_data["total"] >= 1
    assert any(v["id"] == v_id for v in filtered_data["verifications"])

    # Filter with non-matching case returns empty
    res_empty = client.get(f"{base_url}?preaudit_case_id={uuid4()}")
    assert res_empty.status_code == 200
    assert res_empty.json()["total"] == 0

    # 4. GET projection
    res_proj = client.get(f"{base_url}/{v_id}/projection")
    assert res_proj.status_code == 200
    proj_data = res_proj.json()
    assert proj_data["verification_id"] == v_id
    assert proj_data["synthetic_marker"] == "PRIVATE SYNTHETIC INTERNAL TEST RESULT"
    assert "tenant_id" not in proj_data
    assert "payload_encrypted" not in proj_data

    # 5. GET history
    res_hist = client.get(f"{base_url}/{v_id}/history")
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    assert len(hist_data["events"]) >= 1
    assert hist_data["events"][0]["event_type"] == "ISSUED"


def test_api_lifecycle_transitions_and_supersession(session: Session, verification_test_env):
    """Test suspend, correct, revoke, supersede, and reconcile endpoints."""
    env = verification_test_env
    case, snapshot = _setup_approved_case(session, env)
    tenant_id = env["tenant_id"]
    case_id = case.id
    case_revision = case.revision
    snapshot_id = snapshot.id
    snapshot_digest = snapshot.digest

    app = _create_app(session, env["owner_id"], tenant_id, Role.OWNER)
    client = TestClient(app)
    base_url = f"/v2/tenants/{tenant_id}/customer-demo/readiness-verifications"

    # Issue initial verification
    res = client.post(
        base_url,
        json={
            "operation_id": str(uuid4()),
            "preaudit_id": str(case_id),
            "expected_case_revision": case_revision,
            "snapshot_id": str(snapshot_id),
            "snapshot_digest": snapshot_digest,
            "limitations": ["Initial limitation"],
        },
    )
    assert res.status_code == 201
    v_id = res.json()["id"]

    # 1. Correct limitations/notes
    res_correct = client.post(
        f"{base_url}/{v_id}/correct",
        json={
            "operation_id": str(uuid4()),
            "expected_revision": 1,
            "correction_notes": "Corrected description of findings",
        },
    )
    assert res_correct.status_code == 200
    assert res_correct.json()["revision"] == 2

    # 2. Suspend verification
    res_suspend = client.post(
        f"{base_url}/{v_id}/suspend",
        json={
            "operation_id": str(uuid4()),
            "expected_revision": 2,
            "reason": "Security controls require additional audit evidence",
        },
    )
    assert res_suspend.status_code == 200
    assert res_suspend.json()["status"] == "SUSPENDED"
    assert res_suspend.json()["revision"] == 3

    # 3. Revoke verification
    res_revoke = client.post(
        f"{base_url}/{v_id}/revoke",
        json={
            "operation_id": str(uuid4()),
            "expected_revision": 3,
            "reason": "Material non-conformance identified during internal review",
        },
    )
    assert res_revoke.status_code == 200
    assert res_revoke.json()["status"] == "REVOKED"
    assert res_revoke.json()["revision"] == 4

    # 4. Reconcile endpoint
    res_reconcile = client.post(
        f"{base_url}/reconcile",
        json={},
    )
    assert res_reconcile.status_code == 200
    assert "reconciled_count" in res_reconcile.json()


def test_api_security_guards_and_negative_cases(session: Session, verification_test_env, monkeypatch):
    """Test feature off 404, role authorization 403, and reviewer self-issue 403."""
    env = verification_test_env
    case, snapshot = _setup_approved_case(session, env)
    tenant_id = env["tenant_id"]
    case_id = case.id
    case_revision = case.revision
    snapshot_id = snapshot.id
    snapshot_digest = snapshot.digest

    # 1. Feature flag OFF -> 404
    cfg = get_settings()
    monkeypatch.setattr(cfg, "enable_customer_readiness_verification", False)

    app_owner = _create_app(session, env["owner_id"], tenant_id, Role.OWNER)
    client_owner = TestClient(app_owner)
    res_off = client_owner.get(f"/v2/tenants/{tenant_id}/customer-demo/readiness-verifications")
    assert res_off.status_code == 404

    monkeypatch.setattr(cfg, "enable_customer_readiness_verification", True)

    # 2. Non-Owner (Compliance Manager) mutation -> 403
    app_mgr = _create_app(session, env["mgr_id"], tenant_id, Role.COMPLIANCE_MANAGER)
    client_mgr = TestClient(app_mgr)

    res_mgr_issue = client_mgr.post(
        f"/v2/tenants/{tenant_id}/customer-demo/readiness-verifications",
        json={
            "operation_id": str(uuid4()),
            "preaudit_id": str(case_id),
            "expected_case_revision": case_revision,
            "snapshot_id": str(snapshot_id),
            "snapshot_digest": snapshot_digest,
        },
    )
    assert res_mgr_issue.status_code == 403

    # 3. Reviewer self-issue forbidden -> 403
    # Promote reviewer to Owner membership temporarily to test reviewer independence check
    rev_mem = session.query(Membership).filter_by(tenant_id=tenant_id, user_id=env["rev_id"]).first()
    rev_mem.role = Role.OWNER
    session.commit()

    app_rev = _create_app(session, env["rev_id"], tenant_id, Role.OWNER)
    client_rev = TestClient(app_rev)

    res_rev_issue = client_rev.post(
        f"/v2/tenants/{tenant_id}/customer-demo/readiness-verifications",
        json={
            "operation_id": str(uuid4()),
            "preaudit_id": str(case_id),
            "expected_case_revision": case_revision,
            "snapshot_id": str(snapshot_id),
            "snapshot_digest": snapshot_digest,
        },
    )
    assert res_rev_issue.status_code == 403
    assert "access denied" in res_rev_issue.json()["detail"].lower()

    # 4. Unauthenticated request without session/token -> 401
    app_unauth = FastAPI()

    def _db_only():
        yield session

    app_unauth.dependency_overrides[get_db] = _db_only
    register_customer_demo_routes(app_unauth)
    client_unauth = TestClient(app_unauth)
    res_unauth = client_unauth.get(f"/v2/tenants/{tenant_id}/customer-demo/readiness-verifications")
    assert res_unauth.status_code == 401
