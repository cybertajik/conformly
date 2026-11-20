"""FastAPI endpoint and admission matrix tests for customer demo routes."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conformly.auth.dependencies import (
    get_current_principal,
    get_tenant_context,
)
from conformly.auth.session import hash_session_id
from conformly.auth.tokens import mint_dev_token
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.config import get_settings
from conformly.customer_demo.api import register_customer_demo_routes
from conformly.customer_demo.fixture import PACK_VERSION_V1_ID
from conformly.db.session import get_db
from conformly.identity.models import (
    AuthSession,
    Membership,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
    UserStatus,
)


@pytest.fixture(autouse=True)
def enable_demo_env(monkeypatch):
    """Ensure environment enables customer demo for tests and clears settings cache."""
    monkeypatch.setenv("CONFORMLY_ENABLE_CUSTOMER_DEMO", "true")
    monkeypatch.setenv("CONFORMLY_ENVIRONMENT", "test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def test_app(session: Session):
    """Create test FastAPI application with registered customer demo routes and yielding get_db."""
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
def test_fixtures(session: Session):
    """Seed test tenant and user."""
    tenant_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    tenant = Tenant(
        id=tenant_id,
        name="API Test Tenant",
        slug="api-test-tenant",
        status=TenantStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    user = User(
        id=user_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="sub-user-api",
        email="api@example.com",
        display_name="API User",
        created_at=now,
        updated_at=now,
    )
    session.add(tenant)
    session.add(user)
    session.commit()
    return tenant_id, user_id


def test_headers_and_feature_flag(test_app: FastAPI, test_fixtures, monkeypatch):
    """Verify security headers, correlation headers, and feature flag disabling."""
    tenant_id, user_id = test_fixtures

    # Setup valid owner auth
    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=user_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        role=Role.OWNER,
    )

    client = TestClient(test_app)
    resp = client.get(
        f"/v2/tenants/{tenant_id}/customer-demo/workspace",
        headers={"X-Correlation-ID": "test-corr-123"},
    )
    assert resp.status_code == 200
    assert "no-store" in resp.headers.get("Cache-Control", "")
    assert "Authorization" in resp.headers.get("Vary", "")
    assert resp.headers.get("X-Correlation-ID") == "test-corr-123"

    # Now disable customer demo
    monkeypatch.setenv("CONFORMLY_ENABLE_CUSTOMER_DEMO", "false")
    get_settings.cache_clear()

    disabled_app = FastAPI()
    register_customer_demo_routes(disabled_app)
    disabled_client = TestClient(disabled_app)
    resp_off = disabled_client.get(f"/v2/tenants/{tenant_id}/customer-demo/workspace")
    assert resp_off.status_code == 404


def test_admission_matrix(test_app: FastAPI, test_fixtures, session: Session):
    """Comprehensive admission test: role, MFA, scoping, workforce, and lifecycle."""
    tenant_id, user_id = test_fixtures
    client = TestClient(test_app)

    # 1. No MFA -> 403
    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=user_id, mfa_verified=False
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=tenant_id, user_id=user_id, role=Role.OWNER
    )
    r = client.get(f"/v2/tenants/{tenant_id}/customer-demo/workspace")
    assert r.status_code == 403
    assert "MFA" in r.json()["detail"]

    # 2. Roles: Owner -> 200, Compliance Manager -> 200, Admin -> 403, Reviewer -> 403, Employee -> 403
    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=user_id, mfa_verified=True
    )

    for role, expected_status in [
        (Role.OWNER, 200),
        (Role.COMPLIANCE_MANAGER, 200),
        (Role.ADMINISTRATOR, 403),
        (Role.REVIEWER, 403),
        (Role.EMPLOYEE, 403),
    ]:
        test_app.dependency_overrides[get_tenant_context] = lambda r=role: TenantContext(
            tenant_id=tenant_id, user_id=user_id, role=r
        )
        resp = client.get(f"/v2/tenants/{tenant_id}/customer-demo/workspace")
        assert resp.status_code == expected_status, f"Role {role} gave {resp.status_code}"

    # 3. Sub-tenant scoping: legal_entity_id -> 403
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=tenant_id, user_id=user_id, role=Role.OWNER, legal_entity_id=uuid4()
    )
    r_le = client.get(f"/v2/tenants/{tenant_id}/customer-demo/workspace")
    assert r_le.status_code == 403

    # 4. Workforce or External Advisor -> 403
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=tenant_id, user_id=user_id, role=Role.OWNER, is_workforce=True
    )
    r_wf = client.get(f"/v2/tenants/{tenant_id}/customer-demo/workspace")
    assert r_wf.status_code == 403

    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=tenant_id, user_id=user_id, role=Role.OWNER, is_external_advisor=True
    )
    r_ea = client.get(f"/v2/tenants/{tenant_id}/customer-demo/workspace")
    assert r_ea.status_code == 403

    # 5. Non-active tenant: mutations rejected
    t_obj = session.query(Tenant).filter(Tenant.id == tenant_id).first()
    assert t_obj is not None
    t_obj.status = TenantStatus.CANCELLING
    session.commit()

    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=tenant_id, user_id=user_id, role=Role.OWNER
    )
    r_mut = client.put(
        f"/v2/tenants/{tenant_id}/customer-demo/answers",
        json={
            "expected_revision": 0,
            "company_code": "ALPHA",
            "answers": {"synthetic_wp09_uses_cloud": True},
        },
    )
    assert r_mut.status_code == 409


def test_full_api_journey(test_app: FastAPI, test_fixtures):
    """End-to-end API test: read workspace -> save answers -> evaluate -> adopt -> verify state."""
    tenant_id, user_id = test_fixtures

    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=user_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=tenant_id, user_id=user_id, role=Role.OWNER
    )

    client = TestClient(test_app)

    # 1. Initial Workspace read
    r_ws = client.get(f"/v2/tenants/{tenant_id}/customer-demo/workspace")
    assert r_ws.status_code == 200
    assert r_ws.json()["current_revision"] == 0

    # 2. Save Answers: Fictional Alpha (cloud=true, region=EU)
    r_ans = client.put(
        f"/v2/tenants/{tenant_id}/customer-demo/answers",
        json={
            "expected_revision": 0,
            "company_code": "ALPHA",
            "answers": {
                "synthetic_wp09_uses_cloud": True,
                "synthetic_wp09_operating_region": "EU",
            },
        },
    )
    assert r_ans.status_code == 200
    ans_data = r_ans.json()
    assert ans_data["revision"] == 1
    assert len(ans_data["content_digest"]) == 64

    # 3. Evaluate against Pack v1
    r_eval = client.post(
        f"/v2/tenants/{tenant_id}/customer-demo/evaluations",
        json={
            "expected_revision": 1,
            "pack_version_id": str(PACK_VERSION_V1_ID),
        },
    )
    assert r_eval.status_code == 201
    eval_data = r_eval.json()
    assert eval_data["answer_revision"] == 1
    assert len(eval_data["results"]) == 2
    assert eval_data["results"][0]["result"] == "APPLICABLE"
    assert eval_data["results"][1]["result"] == "APPLICABLE"

    # 4. Adopt Pack v1
    eval_id = eval_data["id"]
    r_adopt = client.post(
        f"/v2/tenants/{tenant_id}/customer-demo/adoptions",
        json={
            "expected_revision": 1,
            "evaluation_id": eval_id,
            "pack_version_id": str(PACK_VERSION_V1_ID),
            "acknowledge_synthetic": True,
            "acknowledge_missing_information": False,
        },
    )
    assert r_adopt.status_code == 201
    adopt_data = r_adopt.json()
    assert adopt_data["selection_revision"] == 1
    assert adopt_data["is_current"] is True

    # 5. Read workspace again: verify updated state and non-stale selection
    r_ws2 = client.get(f"/v2/tenants/{tenant_id}/customer-demo/workspace")
    assert r_ws2.status_code == 200
    ws2 = r_ws2.json()
    assert ws2["current_revision"] == 1
    assert ws2["selection_revision"] == 1
    assert ws2["selected_pack"]["is_stale"] is False
    assert ws2["selected_pack"]["pack_version_id"] == str(PACK_VERSION_V1_ID)


def test_body_size_limit_16kib(test_app: FastAPI, test_fixtures):
    """Verify pre-parse body size limiter rejects payloads exceeding 16 KiB (R7)."""
    tenant_id, user_id = test_fixtures

    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=user_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=tenant_id, user_id=user_id, role=Role.OWNER
    )

    client = TestClient(test_app)

    # 1. Payload > 16 KiB with Content-Length header
    oversized_data = "x" * 17000
    resp = client.put(
        f"/v2/tenants/{tenant_id}/customer-demo/answers",
        content=oversized_data,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 413
    assert "16 KiB" in resp.json()["detail"]
    assert "no-store" in resp.headers.get("Cache-Control", "")

    # 2. Payload with empty Content-Length header string (malformed)
    resp_empty_len = client.put(
        f"/v2/tenants/{tenant_id}/customer-demo/answers",
        content="{}",
        headers={"Content-Length": "", "Content-Type": "application/json"},
    )
    assert resp_empty_len.status_code == 400
    assert "Malformed Content-Length header" in resp_empty_len.json()["detail"]


def test_body_boundary_streaming_and_mismatched_content_length(test_app: FastAPI, test_fixtures):
    """Verify boundary streaming: absent Content-Length, chunked, and spoofed-small headers (R7)."""
    import json

    tenant_id, user_id = test_fixtures
    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=user_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=tenant_id, user_id=user_id, role=Role.OWNER
    )
    client = TestClient(test_app)

    # 1. Chunked / streamed generator without Content-Length header (<= 16 KiB)
    def valid_stream_gen():
        payload = json.dumps(
            {
                "expected_revision": 0,
                "company_code": "ALPHA",
                "answers": {},
            }
        ).encode()
        yield payload[:10]
        yield payload[10:]

    r_stream = client.put(
        f"/v2/tenants/{tenant_id}/customer-demo/answers",
        content=valid_stream_gen(),
        headers={"Content-Type": "application/json"},
    )
    assert r_stream.status_code == 200

    # 2. Oversized chunked stream without Content-Length header (> 16 KiB) -> 413
    def oversized_stream_gen():
        yield b"x" * 9000
        yield b"x" * 9000

    r_oversized = client.put(
        f"/v2/tenants/{tenant_id}/customer-demo/answers",
        content=oversized_stream_gen(),
        headers={"Content-Type": "application/json"},
    )
    assert r_oversized.status_code == 413
    assert "Payload exceeds 16 KiB limit" in r_oversized.json()["detail"]

    # 3. Spoofed-small Content-Length header: header says 10 bytes, but body has 100 bytes -> 400
    r_spoofed = client.put(
        f"/v2/tenants/{tenant_id}/customer-demo/answers",
        content=b"x" * 100,
        headers={"Content-Length": "10", "Content-Type": "application/json"},
    )
    assert r_spoofed.status_code == 400
    assert "Mismatched Content-Length header" in r_spoofed.json()["detail"]


def test_real_customer_auth_dependency_enforcement(
    test_app: FastAPI, session: Session, test_fixtures
):
    """Verify genuine customer-auth dependencies without principal/tenant mock overrides.

    Exercises the full auth pipeline:
    1. HTTP Bearer extraction (bearer_scheme in get_current_principal)
    2. JWT cryptographic verification (TokenVerifier.verify with RS256/HS256)
    3. Session resolution & revocation check (authenticate_claims in DB)
    4. Tenant membership & scoping check (resolve_tenant_context in DB)
    5. Feature admission policy (verify_customer_demo_admission)
    """
    tenant_id, user_id = test_fixtures
    test_app.dependency_overrides.pop(get_current_principal, None)
    test_app.dependency_overrides.pop(get_tenant_context, None)

    settings = get_settings()
    secret = settings.invitation_token_pepper or "conformly-development-token-signing-secret"
    now = datetime.now(UTC)

    # Ensure user has valid active status and known OIDC issuer
    user = session.get(User, user_id)
    assert user is not None
    user.oidc_issuer = "https://development.invalid"
    user.oidc_subject = "sub-user-api"
    user.status = UserStatus.ACTIVE

    # Create active Owner membership in tenant
    membership = Membership(
        user_id=user_id,
        tenant_id=tenant_id,
        role=Role.OWNER,
        status=MembershipStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    session.add(membership)

    # Create active session in database
    sid_valid = f"valid-session-{uuid4()}"
    auth_session = AuthSession(
        user_id=user_id,
        session_id_hash=hash_session_id(sid_valid),
        expires_at=now + timedelta(hours=2),
        revoked_at=None,
        created_at=now,
        updated_at=now,
    )
    session.add(auth_session)
    session.commit()

    client = TestClient(test_app, raise_server_exceptions=False)

    # 1. Missing Authorization header -> 401
    # Boundary: bearer_scheme in get_current_principal detects missing credentials
    r_no_auth = client.get(f"/v2/tenants/{tenant_id}/customer-demo/workspace")
    assert r_no_auth.status_code == 401
    assert r_no_auth.json()["detail"] in ("Unauthorized", "authentication required")
    assert "no-store" in r_no_auth.headers.get("Cache-Control", "")
    assert "Authorization" in r_no_auth.headers.get("Vary", "")

    # 2. Malformed Bearer token -> 401
    # Boundary: TokenVerifier.verify catches decode errors and raises AuthenticationError
    r_bad_token = client.get(
        f"/v2/tenants/{tenant_id}/customer-demo/workspace",
        headers={"Authorization": "Bearer not.a.valid.jwt.token"},
    )
    assert r_bad_token.status_code == 401
    assert r_bad_token.json()["detail"] in ("Unauthorized", "invalid authentication")
    assert "no-store" in r_bad_token.headers.get("Cache-Control", "")
    assert "Authorization" in r_bad_token.headers.get("Vary", "")

    # 3. Valid admitted customer succeeds -> 200
    # Boundary: cryptographic signature valid, active session found, active membership found, role admitted
    valid_token = mint_dev_token(
        issuer=user.oidc_issuer,
        subject=user.oidc_subject,
        email=user.email,
        session_id=sid_valid,
        mfa_verified=True,
        expires_in_seconds=3600,
        secret=secret,
    )
    r_valid = client.get(
        f"/v2/tenants/{tenant_id}/customer-demo/workspace",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert r_valid.status_code == 200
    assert r_valid.json()["current_revision"] == 0
    assert "no-store" in r_valid.headers.get("Cache-Control", "")
    assert "Authorization" in r_valid.headers.get("Vary", "")

    # 4. Genuinely expired token (JWT exp claim expired) -> 401
    # Boundary: TokenVerifier.verify catches jwt.ExpiredSignatureError and raises AuthenticationError
    expired_token = mint_dev_token(
        issuer=user.oidc_issuer,
        subject=user.oidc_subject,
        email=user.email,
        session_id=sid_valid,
        mfa_verified=True,
        expires_in_seconds=-3600,
        secret=secret,
    )
    r_exp_token = client.get(
        f"/v2/tenants/{tenant_id}/customer-demo/workspace",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert r_exp_token.status_code == 401
    assert r_exp_token.json()["detail"] in ("Unauthorized", "invalid authentication")
    assert "no-store" in r_exp_token.headers.get("Cache-Control", "")
    assert "Authorization" in r_exp_token.headers.get("Vary", "")

    # 5. Genuinely expired DB session (token valid, but AuthSession.expires_at in past) -> 401
    # Boundary: authenticate_claims filters AuthSession.expires_at > current_time
    sid_exp = f"exp-session-{uuid4()}"
    session.add(
        AuthSession(
            user_id=user_id,
            session_id_hash=hash_session_id(sid_exp),
            expires_at=now - timedelta(minutes=10),
            revoked_at=None,
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(hours=1),
        )
    )
    session.commit()
    token_exp_session = mint_dev_token(
        issuer=user.oidc_issuer,
        subject=user.oidc_subject,
        email=user.email,
        session_id=sid_exp,
        mfa_verified=True,
        expires_in_seconds=3600,
        secret=secret,
    )
    r_exp_session = client.get(
        f"/v2/tenants/{tenant_id}/customer-demo/workspace",
        headers={"Authorization": f"Bearer {token_exp_session}"},
    )
    assert r_exp_session.status_code == 401
    assert r_exp_session.json()["detail"] in ("Unauthorized", "invalid authentication")
    assert "no-store" in r_exp_session.headers.get("Cache-Control", "")
    assert "Authorization" in r_exp_session.headers.get("Vary", "")

    # 6. Previously valid session explicitly revoked -> 401
    # Boundary: authenticate_claims filters AuthSession.revoked_at.is_(None)
    auth_session.revoked_at = datetime.now(UTC)
    session.commit()
    r_revoked = client.get(
        f"/v2/tenants/{tenant_id}/customer-demo/workspace",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert r_revoked.status_code == 401
    assert r_revoked.json()["detail"] in ("Unauthorized", "invalid authentication")
    assert "no-store" in r_revoked.headers.get("Cache-Control", "")
    assert "Authorization" in r_revoked.headers.get("Vary", "")
    auth_session.revoked_at = None
    session.commit()

    # 7. Valid active identity without membership in selected tenant -> 403
    # Boundary: resolve_tenant_context searches Membership for selected tenant, fails, raises TenantContextError
    other_tenant_id = uuid4()
    session.add(
        Tenant(
            id=other_tenant_id,
            name="Unrelated Tenant",
            slug="unrelated-tenant",
            status=TenantStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    r_nonmember = client.get(
        f"/v2/tenants/{other_tenant_id}/customer-demo/workspace",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert r_nonmember.status_code == 403
    assert r_nonmember.json()["detail"] in ("Customer demo access denied", "tenant access denied")
    assert "no-store" in r_nonmember.headers.get("Cache-Control", "")
    assert "Authorization" in r_nonmember.headers.get("Vary", "")

    # 8. Valid-shaped token under an untrusted issuer -> 401
    # Boundary: authenticate_claims verifies User.oidc_issuer == claims.issuer
    untrusted_token = mint_dev_token(
        issuer="https://untrusted-foreign-idp.example.com",
        subject=user.oidc_subject,
        email=user.email,
        session_id=sid_valid,
        mfa_verified=True,
        expires_in_seconds=3600,
        secret=secret,
    )
    r_untrusted = client.get(
        f"/v2/tenants/{tenant_id}/customer-demo/workspace",
        headers={"Authorization": f"Bearer {untrusted_token}"},
    )
    assert r_untrusted.status_code == 401
    assert r_untrusted.json()["detail"] in ("Unauthorized", "invalid authentication")
    assert "no-store" in r_untrusted.headers.get("Cache-Control", "")
    assert "Authorization" in r_untrusted.headers.get("Vary", "")


def test_transaction_rollback_on_rejected_requests(session: Session, test_fixtures):
    """Verify yielding get_db executes session.rollback() on 422/409, committing zero rows (P1)."""
    from conformly.customer_demo.models import CustomerDemoAnswers, CustomerDemoWorkspace

    tenant_id, user_id = test_fixtures
    app = FastAPI()
    db_log = []

    def _logged_yielding_db():
        db_log.append("enter")
        try:
            yield session
            session.commit()
            db_log.append("commit")
        except Exception:
            session.rollback()
            db_log.append("rollback")
            raise

    app.dependency_overrides[get_db] = _logged_yielding_db
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=user_id, mfa_verified=True
    )
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=tenant_id, user_id=user_id, role=Role.OWNER
    )
    register_customer_demo_routes(app)

    client = TestClient(app, raise_server_exceptions=False)

    # Send invalid answers payload (unknown fact key) -> 422
    r_bad = client.put(
        f"/v2/tenants/{tenant_id}/customer-demo/answers",
        json={
            "expected_revision": 0,
            "company_code": "ALPHA",
            "answers": {"nonexistent_fact_uuid": True},
        },
    )
    assert r_bad.status_code == 422
    assert "rollback" in db_log
    assert "commit" not in db_log

    # Workspace and answers must not be committed
    assert (
        session.query(CustomerDemoWorkspace)
        .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
        .first()
        is None
    )
    assert (
        session.query(CustomerDemoAnswers)
        .filter(CustomerDemoAnswers.tenant_id == tenant_id)
        .first()
        is None
    )


def test_privacy_headers_and_non_echoing_errors(test_app: FastAPI, test_fixtures):
    """Verify privacy headers and non-echoing of hostile markers on error outcomes (R8)."""
    tenant_id, user_id = test_fixtures

    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=user_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=tenant_id, user_id=user_id, role=Role.OWNER
    )

    client = TestClient(test_app)

    hostile_marker = "<script>alert('XSS_ATTACK_VECTOR')</script>"
    bad_payload = {
        "expected_revision": 0,
        "company_code": hostile_marker,
        "answers": {hostile_marker: True},
    }

    resp = client.put(
        f"/v2/tenants/{tenant_id}/customer-demo/answers",
        json=bad_payload,
        headers={"X-Correlation-ID": "corr-err-456"},
    )
    assert resp.status_code in (422, 400)
    assert "no-store" in resp.headers.get("Cache-Control", "")
    assert "Authorization" in resp.headers.get("Vary", "")
    assert resp.headers.get("X-Correlation-ID") == "corr-err-456"

    # Crucial security assertion: hostile marker must NEVER be echoed back in body
    resp_text = resp.text
    assert hostile_marker not in resp_text
    assert "XSS_ATTACK_VECTOR" not in resp_text


def test_unexpected_500_privacy_headers_and_transaction_rollback(
    session: Session, test_fixtures, monkeypatch
):
    """Verify unexpected 500 errors render privacy headers, sanitized correlation ID, and roll back (P2/Closeout A)."""
    from conformly.audit.models import AuditEvent, AuditOutcome
    from conformly.customer_demo.models import CustomerDemoAnswers, CustomerDemoWorkspace

    tenant_id, user_id = test_fixtures
    app = FastAPI()
    db_events: list[Any] = []
    service_stages: list[str] = []

    def _logged_yielding_db():
        db_events.append("enter")
        try:
            yield session
            session.commit()
            db_events.append("commit")
        except Exception as exc:
            session.rollback()
            db_events.append(("rollback", type(exc).__name__, str(exc)))
            raise

    app.dependency_overrides[get_db] = _logged_yielding_db
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=user_id, mfa_verified=True
    )
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=tenant_id, user_id=user_id, role=Role.OWNER
    )
    register_customer_demo_routes(app)

    # Inject failure inside service after fully valid pending uncommitted database work
    def _failing_service(*args, **kwargs):
        now = datetime.now(UTC)
        # 1. Construction and add of valid workspace and answers satisfying all DB constraints
        ws = CustomerDemoWorkspace(
            tenant_id=tenant_id,
            current_revision=1,
            selection_revision=0,
            created_at=now,
            updated_at=now,
        )
        session.add(ws)
        ans = CustomerDemoAnswers(
            tenant_id=tenant_id,
            revision=1,
            company_code="ALPHA",
            answers={"synthetic_wp09_uses_cloud": True},
            content_digest="a" * 64,
            actor_id=user_id,
            created_at=now,
        )
        session.add(ans)
        # Explicit flush to prove DB transaction received pending rows before crash
        session.flush()

        # 2. Explicitly assert pending rows are visible inside this failing transaction before error injection
        assert (
            session.query(CustomerDemoWorkspace).filter_by(tenant_id=tenant_id).first() is not None
        )
        assert (
            session.query(CustomerDemoAnswers).filter_by(tenant_id=tenant_id, revision=1).first()
            is not None
        )
        service_stages.append("pre_injection_flush_verified")

        # 3. Raise intended synthetic RuntimeError (must NOT fail on constructor/flush)
        raise RuntimeError("FATAL_INTERNAL_DB_PASSWORD_MARKER_SHOULD_NEVER_LEAK")

    monkeypatch.setattr(
        "conformly.customer_demo.api.service_save_answers",
        _failing_service,
    )

    client = TestClient(app, raise_server_exceptions=False)

    corr_input = "test-corr-id-500!@#$%"
    resp = client.put(
        f"/v2/tenants/{tenant_id}/customer-demo/answers",
        json={
            "expected_revision": 0,
            "company_code": "ALPHA",
            "answers": {"synthetic_wp09_uses_cloud": True},
        },
        headers={"X-Correlation-ID": corr_input},
    )

    # 1. Status 500 Internal Server Error
    assert resp.status_code == 500

    # 2. Sanitized generic error detail (no private exception marker leaked)
    assert resp.json() == {"detail": "Internal server error"}
    assert "FATAL_INTERNAL_DB_PASSWORD_MARKER" not in resp.text

    # 3. Privacy headers present
    assert "no-store" in resp.headers.get("Cache-Control", "")
    assert "no-cache" in resp.headers.get("Cache-Control", "")
    assert "must-revalidate" in resp.headers.get("Cache-Control", "")
    assert "private" in resp.headers.get("Cache-Control", "")
    assert "no-cache" in resp.headers.get("Pragma", "")
    assert "Authorization" in resp.headers.get("Vary", "")

    # 4. Bounded, sanitized correlation ID present
    expected_sanitized_corr = "test-corr-id-500"
    assert resp.headers.get("X-Correlation-ID") == expected_sanitized_corr

    # 5. Intended synthetic RuntimeError reached and yielding dependency entered rollback, not commit
    assert "pre_injection_flush_verified" in service_stages
    assert "commit" not in db_events
    rollback_events = [evt for evt in db_events if isinstance(evt, tuple) and evt[0] == "rollback"]
    assert len(rollback_events) == 1
    assert rollback_events[0][1] == "RuntimeError"
    assert "FATAL_INTERNAL_DB_PASSWORD_MARKER_SHOULD_NEVER_LEAK" in rollback_events[0][2]

    # 6. From fresh transaction/session, no pending business row or success audit survives
    with Session(session.bind) as fresh_session:
        assert (
            fresh_session.query(CustomerDemoWorkspace).filter_by(tenant_id=tenant_id).first()
            is None
        )
        assert (
            fresh_session.query(CustomerDemoAnswers)
            .filter_by(tenant_id=tenant_id, revision=1)
            .first()
            is None
        )
        assert (
            fresh_session.query(AuditEvent)
            .filter(AuditEvent.tenant_id == tenant_id, AuditEvent.outcome == AuditOutcome.SUCCESS)
            .first()
            is None
        )

    # 7. Unrelated V1 default 500 comparison before vs after registration
    # Observable baseline on an app without customer demo registration:
    baseline_app = FastAPI()

    @baseline_app.get("/v1/unrelated-failure")
    def _baseline_v1_failure():
        raise RuntimeError("unrelated_v1_crash")

    baseline_client = TestClient(baseline_app, raise_server_exceptions=False)
    r_baseline = baseline_client.get("/v1/unrelated-failure")

    # Observable response on app with customer demo routes registered:
    @app.get("/v1/unrelated-failure")
    def _v1_failure():
        raise RuntimeError("unrelated_v1_crash")

    r_v1 = client.get("/v1/unrelated-failure")

    # Compare complete observable default response: status, body, and content headers
    assert r_v1.status_code == r_baseline.status_code == 500
    assert r_v1.text == r_baseline.text == "Internal Server Error"
    assert (
        r_v1.headers.get("content-type")
        == r_baseline.headers.get("content-type")
        == "text/plain; charset=utf-8"
    )
    assert r_v1.headers.get("content-length") == r_baseline.headers.get("content-length")
    # Verify no customer demo privacy or correlation headers leak onto unrelated V1 routes
    assert "X-Correlation-ID" not in r_v1.headers
    assert "no-store" not in r_v1.headers.get("Cache-Control", "")

    # 8. Preserve preinstalled custom exception handler on unrelated routes
    custom_app = FastAPI()

    async def _custom_exc_handler(request: Request, exc: Exception) -> Response:
        return JSONResponse(
            status_code=500,
            content={"custom_error": True, "exc_type": type(exc).__name__},
        )

    custom_app.add_exception_handler(Exception, _custom_exc_handler)
    register_customer_demo_routes(custom_app)

    @custom_app.get("/v1/custom-unrelated-crash")
    def _custom_unrelated_crash():
        raise RuntimeError("custom_crash_in_v1")

    custom_client = TestClient(custom_app, raise_server_exceptions=False)
    r_custom = custom_client.get("/v1/custom-unrelated-crash")
    assert r_custom.status_code == 500
    assert r_custom.json() == {"custom_error": True, "exc_type": "RuntimeError"}
    assert "X-Correlation-ID" not in r_custom.headers
