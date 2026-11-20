"""Backend integration tests for catalog demo API endpoints, feature gating, and headers."""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from conformly.audit.models import AuditActorType, AuditEvent, AuditOutcome
from conformly.catalog_demo.api import register_catalog_demo_routes, router
from conformly.catalog_demo.auth import (
    TestWorkforceTokenVerifier,
    get_workforce_verifier,
)
from conformly.catalog_demo.dataset import setup_catalog_demo_fixture
from conformly.catalog_demo.db import AuditPersistenceError, get_catalog_db
from conformly.config import Settings, get_settings
from conformly.db.base import Base
from conformly.db.session import get_db
from conformly.identity.models import User, UserStatus


@pytest.fixture(scope="module")
def rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_priv = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pem_pub = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pem_priv, pem_pub


@pytest.fixture
def test_app_and_db(rsa_keys) -> Generator[tuple[TestClient, Session, User], None, None]:
    pem_priv, pem_pub = rsa_keys
    verifier = TestWorkforceTokenVerifier("https://workforce.test", "staff-client", pem_pub)

    # In-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    # Configure audit session factory to use in-memory SQLite
    from sqlalchemy.orm import sessionmaker

    from conformly.catalog_demo.api import set_audit_session_factory

    test_session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    set_audit_session_factory(test_session_factory)

    # Build FastAPI test app
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_catalog_db] = override_get_db
    app.dependency_overrides[get_workforce_verifier] = lambda: verifier

    with Session(engine) as session:
        # Seed user & catalog dataset
        admin = User(
            oidc_issuer="https://workforce.test",
            oidc_subject="staff-admin-01",
            email="admin@staff.local",
            display_name="Staff Administrator",
            status=UserStatus.ACTIVE,
            is_platform_admin=True,
        )
        session.add(admin)
        session.commit()
        setup_catalog_demo_fixture(session)
        session.commit()

        client = TestClient(app)
        try:
            yield client, session, admin
        finally:
            set_audit_session_factory(None)


def test_feature_gating_disabled_and_prod():
    # 1. Feature disabled
    app_disabled = FastAPI()
    settings_disabled = Settings(enable_catalog_demo=False, environment="test")
    app_disabled.dependency_overrides[get_settings] = lambda: settings_disabled
    register_catalog_demo_routes(app_disabled)
    client_disabled = TestClient(app_disabled)
    assert client_disabled.get("/v2/catalog-demo/catalog").status_code == 404

    # 2. Production environment
    app_prod = FastAPI()
    settings_prod = Settings(enable_catalog_demo=True, environment="production")
    app_prod.dependency_overrides[get_settings] = lambda: settings_prod
    register_catalog_demo_routes(app_prod)
    client_prod = TestClient(app_prod)
    assert client_prod.get("/v2/catalog-demo/catalog").status_code == 404


def test_api_session_lifecycle_and_catalog_read(test_app_and_db, rsa_keys):
    client, session, admin = test_app_and_db
    pem_priv, pem_pub = rsa_keys

    now_ts = int(datetime.now(UTC).timestamp())
    session_id = str(uuid4())
    token = jwt.encode(
        {
            "iss": "https://workforce.test",
            "sub": "staff-admin-01",
            "aud": "staff-client",
            "sid": session_id,
            "exp": now_ts + 3600,
            "auth_time": now_ts,
            "amr": ["mfa", "totp"],
            "email": "admin@staff.local",
            "email_verified": True,
            "name": "Staff Administrator",
        },
        pem_priv,
        algorithm="RS256",
    )

    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. POST /v2/catalog-demo/session (Bootstrap session)
    post_resp = client.post("/v2/catalog-demo/session", headers=auth_headers)
    assert post_resp.status_code == 201
    assert post_resp.headers["Cache-Control"] == "no-store"
    assert post_resp.headers["Vary"] == "Authorization"
    data = post_resp.json()
    assert data["user_id"] == str(admin.id)
    assert data["display_name"] == "Staff Administrator"
    assert data["capabilities"] == ["DRAFT_READ"]
    assert "authenticated_at" in data
    assert "expires_at" in data

    # 2. GET /v2/catalog-demo/session (Verify session)
    get_resp = client.get("/v2/catalog-demo/session", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.headers["Cache-Control"] == "no-store"
    assert get_resp.headers["Vary"] == "Authorization"
    assert get_resp.json()["user_id"] == str(admin.id)

    # 3. GET /v2/catalog-demo/catalog (Read catalog graph)
    cat_resp = client.get("/v2/catalog-demo/catalog", headers=auth_headers)
    assert cat_resp.status_code == 200
    # Safe headers assertions
    assert cat_resp.headers["X-Catalog-Synthetic"] == "true"
    assert cat_resp.headers["X-Catalog-Draft-Only"] == "true"
    assert cat_resp.headers["Cache-Control"] == "no-store"
    assert cat_resp.headers["Vary"] == "Authorization"

    cat_data = cat_resp.json()
    assert cat_data["demo_id"] == "catalog-demo-v1"
    assert cat_data["synthetic"] is True
    assert cat_data["status"] == "Draft"
    assert cat_data["source"]["source_key"] == "DEMO08-SOURCE"
    assert cat_data["source"]["title"] == "Synthetic Conformly catalog demo"
    assert len(cat_data["requirements"]) == 2
    assert len(cat_data["controls"]) == 2
    ctrl_keys = {c["control_key"] for c in cat_data["controls"]}
    assert ctrl_keys == {"CC-DEMO-001", "CC-DEMO-002"}
    assert len(cat_data["mappings"]) == 2
    assert len(cat_data["evidence_requirements"]) == 2
    assert len(cat_data["assessment_procedures"]) == 2

    # 4. DELETE /v2/catalog-demo/session (Revocation - 204 No Content)
    del_resp = client.delete("/v2/catalog-demo/session", headers=auth_headers)
    assert del_resp.status_code == 204
    assert del_resp.text == ""
    assert del_resp.headers["Cache-Control"] == "no-store"
    assert del_resp.headers["Vary"] == "Authorization"

    # 5. Subsequent GET /catalog returns 401
    revoked_resp = client.get("/v2/catalog-demo/catalog", headers=auth_headers)
    assert revoked_resp.status_code == 401


def test_api_unauthorized_and_custom_header(test_app_and_db):
    client, session, admin = test_app_and_db

    # No credentials
    no_auth = client.get("/v2/catalog-demo/catalog")
    assert no_auth.status_code == 401

    # Invalid session / custom header ignored
    bad_auth = client.get(
        "/v2/catalog-demo/catalog",
        headers={"X-Catalog-Demo-Session": "completely-invalid-session-key"},
    )
    assert bad_auth.status_code == 401
    assert "completely-invalid-session-key" not in bad_auth.text


def test_dependency_error_headers_and_auditing(test_app_and_db, rsa_keys):
    """Verify security headers (no-store, Vary: Authorization) and durable auditing on all error outcomes."""
    client, session, admin = test_app_and_db
    pem_priv, pem_pub = rsa_keys

    # 1. Missing Authorization header (Dependency failure before route body)
    res_no_auth = client.get("/v2/catalog-demo/catalog")
    assert res_no_auth.status_code == 401
    assert res_no_auth.headers["Cache-Control"] == "no-store"
    assert "Authorization" in res_no_auth.headers["Vary"]
    assert res_no_auth.json()["detail"] == "Invalid or revoked authentication credentials"

    # Verify denial audited via isolated transaction with no invented actor
    audit_evt = (
        session.query(AuditEvent)
        .filter(AuditEvent.action == "catalog.demo_access_denied")
        .order_by(AuditEvent.occurred_at.desc())
        .first()
    )
    assert audit_evt is not None
    assert audit_evt.outcome == AuditOutcome.DENIED
    assert audit_evt.actor_id is None
    assert audit_evt.actor_type == AuditActorType.SYSTEM

    # 2. Non-staff user (Platform admin = False)
    non_staff = User(
        oidc_issuer="https://workforce.test",
        oidc_subject="non-staff-999",
        email="user@staff.local",
        display_name="Regular Staff",
        status=UserStatus.ACTIVE,
        is_platform_admin=False,
    )
    session.add(non_staff)
    session.commit()

    now_ts = int(datetime.now(UTC).timestamp())
    non_staff_token = jwt.encode(
        {
            "iss": "https://workforce.test",
            "sub": "non-staff-999",
            "aud": "staff-client",
            "sid": "session-non-staff",
            "exp": now_ts + 3600,
            "auth_time": now_ts,
            "amr": ["otp"],
            "email": "user@staff.local",
            "email_verified": True,
        },
        pem_priv,
        algorithm="RS256",
    )

    res_forbidden = client.get(
        "/v2/catalog-demo/catalog",
        headers={"Authorization": f"Bearer {non_staff_token}"},
    )
    assert res_forbidden.status_code == 403
    assert res_forbidden.headers["Cache-Control"] == "no-store"
    assert "Authorization" in res_forbidden.headers["Vary"]
    assert res_forbidden.json()["detail"] == "Insufficient staff permissions"

    # Verify denial audited with known actor_id
    audit_evt_staff = (
        session.query(AuditEvent)
        .filter(
            AuditEvent.action == "catalog.demo_access_denied",
            AuditEvent.actor_id == non_staff.id,
        )
        .order_by(AuditEvent.occurred_at.desc())
        .first()
    )
    assert audit_evt_staff is not None
    assert audit_evt_staff.outcome == AuditOutcome.DENIED
    assert audit_evt_staff.actor_type == AuditActorType.USER


def test_sink_failure_surfaces_as_sanitized_503(test_app_and_db, rsa_keys):
    """Verify that an audit persistence error is surfaced as 503 without being swallowed."""
    from unittest.mock import patch

    client, session, admin = test_app_and_db
    pem_priv, pem_pub = rsa_keys

    now_ts = int(datetime.now(UTC).timestamp())
    token = jwt.encode(
        {
            "iss": "https://workforce.test",
            "sub": "staff-admin-01",
            "aud": "staff-client",
            "sid": str(uuid4()),
            "exp": now_ts + 3600,
            "auth_time": now_ts,
            "amr": ["mfa", "totp"],
            "email": "admin@staff.local",
            "email_verified": True,
        },
        pem_priv,
        algorithm="RS256",
    )

    auth_headers = {"Authorization": f"Bearer {token}"}
    client.post("/v2/catalog-demo/session", headers=auth_headers)

    # Simulate audit sink failure during projection
    with patch(
        "conformly.catalog_demo.api.project_catalog_demo_graph",
        side_effect=AuditPersistenceError("Simulated audit disk failure"),
    ):
        res = client.get("/v2/catalog-demo/catalog", headers=auth_headers)
        assert res.status_code == 503
        assert res.headers["Cache-Control"] == "no-store"
        assert "Authorization" in res.headers["Vary"]
        assert "Simulated" not in res.text
        assert (
            res.json()["detail"]
            == "Catalog service or audit infrastructure temporarily unavailable"
        )


def test_bounded_and_sanitized_correlation_id(test_app_and_db, rsa_keys):
    """Verify request ID is bounded and stripped of malicious characters in audit trail."""
    client, session, admin = test_app_and_db
    pem_priv, pem_pub = rsa_keys

    malicious_req_id = "req-test--<script>alert(1)</script>--" + ("A" * 200)

    res = client.get(
        "/v2/catalog-demo/catalog",
        headers={"X-Request-ID": malicious_req_id},
    )
    assert res.status_code == 401

    evt = (
        session.query(AuditEvent)
        .filter(AuditEvent.action == "catalog.demo_access_denied")
        .order_by(AuditEvent.occurred_at.desc())
        .first()
    )
    assert evt is not None
    assert "<script>" not in evt.request_id
    assert len(evt.request_id) <= 64


def test_healthy_adapter_persists_denial_audit_with_allowed_metadata(test_app_and_db):
    from uuid import uuid4

    from conformly.audit.models import AuditEvent, AuditOutcome
    from conformly.audit.service import validate_safe_metadata
    from conformly.catalog_demo.db import AppAuditDeniedSink

    client, session, admin = test_app_and_db

    sink = AppAuditDeniedSink(session_factory=lambda: session)

    actor_uuid = uuid4()
    req_key = "req-test-denial-sink-1"
    sink.record_denial(
        actor_id=actor_uuid,
        reason_code="access_denied_test",
        operation="draft_read",
        request_key=req_key,
    )

    evt = session.query(AuditEvent).filter(AuditEvent.request_id == req_key).first()
    assert evt is not None
    assert evt.outcome == AuditOutcome.DENIED
    assert evt.action == "catalog.draft_read"
    assert "operation" not in evt.safe_metadata
    assert evt.safe_metadata.get("reason") == "access_denied_test"
    validate_safe_metadata(evt.safe_metadata)


def test_failing_sink_or_service_swallowed_audit_failure_yields_503_and_no_sentinel_leak(
    test_app_and_db, rsa_keys
):
    from datetime import timedelta
    from unittest.mock import patch

    client, session, admin = test_app_and_db
    pem_priv, pem_pub = rsa_keys

    token = jwt.encode(
        {
            "iss": "https://workforce.test",
            "sub": "staff-admin-01",
            "sid": "session-boss-1",
            "aud": "staff-client",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "auth_time": int(datetime.now(UTC).timestamp()),
            "email": "admin@staff.local",
            "email_verified": True,
            "amr": ["webauthn"],
        },
        pem_priv,
        algorithm="RS256",
    )

    auth_headers = {"Authorization": f"Bearer {token}"}
    client.post("/v2/catalog-demo/session", headers=auth_headers)

    sentinel_secret = "postgresql://secret_user:super_secret_pw@db.local/secret_db"
    sentinel_token = "bearer-jwt-super-secret-sentinel-xyz"

    with patch(
        "conformly.catalog_demo.api.project_catalog_demo_graph",
        side_effect=AuditPersistenceError(
            f"Underlying audit failure: {sentinel_secret} {sentinel_token}"
        ),
    ):
        res = client.get("/v2/catalog-demo/catalog", headers=auth_headers)
        assert res.status_code == 503
        assert res.headers["Cache-Control"] == "no-store"
        assert "Authorization" in res.headers["Vary"]
        assert sentinel_secret not in res.text
        assert sentinel_token not in res.text
        assert (
            res.json()["detail"]
            == "Catalog service or audit infrastructure temporarily unavailable"
        )


def test_bootstrap_revoked_sid_returns_401_with_denial_audit(test_app_and_db, rsa_keys):
    from datetime import timedelta

    from conformly.auth.session import hash_session_id
    from conformly.identity.models import AuthSession

    client, session, admin = test_app_and_db
    pem_priv, pem_pub = rsa_keys

    sid = "session-revocation-test-123"
    token = jwt.encode(
        {
            "iss": "https://workforce.test",
            "sub": "staff-admin-01",
            "sid": sid,
            "aud": "staff-client",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "auth_time": int(datetime.now(UTC).timestamp()),
            "email": "admin@staff.local",
            "email_verified": True,
            "amr": ["webauthn"],
        },
        pem_priv,
        algorithm="RS256",
    )

    auth_headers = {"Authorization": f"Bearer {token}", "X-Request-ID": "req-revoked-bootstrap-1"}

    res1 = client.post("/v2/catalog-demo/session", headers=auth_headers)
    assert res1.status_code == 201

    sid_hash = hash_session_id(sid)
    auth_sess = session.query(AuthSession).filter(AuthSession.session_id_hash == sid_hash).first()
    assert auth_sess is not None
    auth_sess.revoked_at = datetime.now(UTC)
    session.commit()

    res2 = client.post(
        "/v2/catalog-demo/session",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req-revoked-bootstrap-2"},
    )
    assert res2.status_code == 401
    assert "detail" in res2.json()

    res3 = client.get(
        "/v2/catalog-demo/session",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req-revoked-get-1"},
    )
    assert res3.status_code == 401
    assert res3.headers["Cache-Control"] == "no-store"
    assert "Authorization" in res3.headers["Vary"]

    denial_evt = (
        session.query(AuditEvent).filter(AuditEvent.request_id == "req-revoked-get-1").first()
    )
    assert denial_evt is not None
    assert denial_evt.outcome == AuditOutcome.DENIED
    assert denial_evt.safe_metadata.get("reason") in (
        "session_invalid_or_expired",
        "session_not_found_or_revoked",
        "missing_or_invalid_bearer",
    )


def test_corrupted_assurance_aggregate_returns_sanitized_404_with_denial_audit_and_headers(
    test_app_and_db, rsa_keys
):
    """Verify that stored corrupted assurance aggregate content returns sanitized 404,
    persists a denial audit event with reason 'graph_unavailable', and includes mandatory headers,
    while separate infrastructure/audit failures return 503."""
    from conformly.audit.models import AuditEvent, AuditOutcome
    from conformly.catalog_demo.dataset import (
        EVID_1_VER_ID,
        setup_catalog_demo_fixture,
    )
    from conformly.catalog_v2.models import CatalogEvidenceRequirementVersion

    client, session, admin = test_app_and_db
    pem_priv, pem_pub = rsa_keys

    setup_catalog_demo_fixture(session)
    session.commit()

    now_ts = int(datetime.now(UTC).timestamp())
    session_id = str(uuid4())
    token = jwt.encode(
        {
            "iss": "https://workforce.test",
            "sub": "staff-admin-01",
            "aud": "staff-client",
            "sid": session_id,
            "exp": now_ts + 3600,
            "auth_time": now_ts,
            "amr": ["mfa", "totp"],
            "email": "admin@staff.local",
            "email_verified": True,
            "name": "Staff Administrator",
        },
        pem_priv,
        algorithm="RS256",
    )

    auth_headers = {"Authorization": f"Bearer {token}", "X-Request-ID": "req-corrupt-1"}

    res_boot = client.post("/v2/catalog-demo/session", headers=auth_headers)
    assert res_boot.status_code == 201

    res_ok = client.get("/v2/catalog-demo/catalog", headers=auth_headers)
    assert res_ok.status_code == 200

    evid = session.get(CatalogEvidenceRequirementVersion, EVID_1_VER_ID)
    assert evid is not None
    evid.title = "Corrupted Title Text"
    session.commit()

    corrupt_headers = {"Authorization": f"Bearer {token}", "X-Request-ID": "req-corrupt-preview-1"}
    res_corrupt = client.get("/v2/catalog-demo/catalog", headers=corrupt_headers)

    assert res_corrupt.status_code == 404
    assert res_corrupt.json() == {"detail": "Catalog demo graph unavailable"}
    assert res_corrupt.headers["Cache-Control"] == "no-store"
    assert "Authorization" in res_corrupt.headers["Vary"]

    denial_evt = (
        session.query(AuditEvent).filter(AuditEvent.request_id == "req-corrupt-preview-1").first()
    )
    assert denial_evt is not None
    assert denial_evt.outcome == AuditOutcome.DENIED
    assert denial_evt.safe_metadata.get("reason") == "graph_unavailable"


def test_trusted_clock_broken_pipe_returns_fixed_503_with_headers(test_app_and_db, rsa_keys):
    """Verify that actual BrokenPipeError during trusted-clock read returns HTTP 503
    with no-store and Vary: Authorization headers, and is NOT misclassified as 404."""
    from conformly.catalog_demo.dataset import setup_catalog_demo_fixture

    client, session, admin = test_app_and_db
    pem_priv, _ = rsa_keys

    setup_catalog_demo_fixture(session)
    session.commit()

    now_ts = int(datetime.now(UTC).timestamp())
    session_id = str(uuid4())
    token = jwt.encode(
        {
            "iss": "https://workforce.test",
            "sub": "staff-admin-01",
            "aud": "staff-client",
            "sid": session_id,
            "exp": now_ts + 3600,
            "auth_time": now_ts,
            "amr": ["mfa", "totp"],
            "email": "admin@staff.local",
            "email_verified": True,
            "name": "Staff Administrator",
        },
        pem_priv,
        algorithm="RS256",
    )

    auth_headers = {"Authorization": f"Bearer {token}", "X-Request-ID": "req-clock-broken-1"}

    res_boot = client.post("/v2/catalog-demo/session", headers=auth_headers)
    assert res_boot.status_code == 201

    orig_override = client.app.dependency_overrides[get_catalog_db]

    def mock_get_catalog_db():
        for sess in orig_override():
            orig_exec = sess.execute

            def mock_exec(statement, *args, _orig=orig_exec, **kwargs):
                stmt_str = str(statement)
                if (
                    "clock_timestamp" in stmt_str
                    or "strftime" in stmt_str
                    or "CURRENT_TIMESTAMP" in stmt_str
                ):
                    raise BrokenPipeError("Broken pipe")
                return _orig(statement, *args, **kwargs)

            sess.execute = mock_exec
            yield sess

    client.app.dependency_overrides[get_catalog_db] = mock_get_catalog_db

    res_preview = client.get("/v2/catalog-demo/catalog", headers=auth_headers)

    # Must be 503 Service Unavailable, strictly NOT 404
    assert res_preview.status_code == 503
    assert res_preview.json() == {
        "detail": "Catalog service or audit infrastructure temporarily unavailable"
    }
    assert res_preview.headers["Cache-Control"] == "no-store"
    assert "Authorization" in res_preview.headers["Vary"]


def test_connection_failure_with_digest_or_mismatch_diagnostic_returns_503(
    test_app_and_db, rsa_keys
):
    """Verify that a DB connection/operational failure containing keywords like 'digest' or 'mismatch'
    returns HTTP 503 with no-store and Vary headers, and does not collide into 404."""
    from sqlalchemy.exc import OperationalError

    from conformly.catalog_demo.dataset import setup_catalog_demo_fixture

    client, session, admin = test_app_and_db
    pem_priv, _ = rsa_keys

    setup_catalog_demo_fixture(session)
    session.commit()

    now_ts = int(datetime.now(UTC).timestamp())
    session_id = str(uuid4())
    token = jwt.encode(
        {
            "iss": "https://workforce.test",
            "sub": "staff-admin-01",
            "aud": "staff-client",
            "sid": session_id,
            "exp": now_ts + 3600,
            "auth_time": now_ts,
            "amr": ["mfa", "totp"],
            "email": "admin@staff.local",
            "email_verified": True,
            "name": "Staff Administrator",
        },
        pem_priv,
        algorithm="RS256",
    )

    auth_headers = {"Authorization": f"Bearer {token}", "X-Request-ID": "req-conn-mismatch-1"}

    res_boot = client.post("/v2/catalog-demo/session", headers=auth_headers)
    assert res_boot.status_code == 201

    orig_override = client.app.dependency_overrides[get_catalog_db]

    def mock_get_catalog_db():
        for sess in orig_override():
            orig_exec = sess.execute

            def mock_exec(statement, *args, _orig=orig_exec, **kwargs):
                stmt_str = str(statement)
                if (
                    "clock_timestamp" in stmt_str
                    or "strftime" in stmt_str
                    or "CURRENT_TIMESTAMP" in stmt_str
                ):
                    raise OperationalError(
                        "SSL SYSCALL error: handshake digest mismatch", {}, Exception("diagnostic")
                    )
                return _orig(statement, *args, **kwargs)

            sess.execute = mock_exec
            yield sess

    client.app.dependency_overrides[get_catalog_db] = mock_get_catalog_db

    res_preview = client.get("/v2/catalog-demo/catalog", headers=auth_headers)

    assert res_preview.status_code == 503
    assert res_preview.json() == {
        "detail": "Catalog service or audit infrastructure temporarily unavailable"
    }
    assert res_preview.headers["Cache-Control"] == "no-store"
    assert "Authorization" in res_preview.headers["Vary"]


def test_trusted_clock_invalid_result_returns_503(test_app_and_db, rsa_keys):
    """Verify that trusted clock returning invalid/null result returns HTTP 503."""
    from unittest.mock import MagicMock

    from conformly.catalog_demo.dataset import setup_catalog_demo_fixture

    client, session, admin = test_app_and_db
    pem_priv, _ = rsa_keys

    setup_catalog_demo_fixture(session)
    session.commit()

    now_ts = int(datetime.now(UTC).timestamp())
    session_id = str(uuid4())
    token = jwt.encode(
        {
            "iss": "https://workforce.test",
            "sub": "staff-admin-01",
            "aud": "staff-client",
            "sid": session_id,
            "exp": now_ts + 3600,
            "auth_time": now_ts,
            "amr": ["mfa", "totp"],
            "email": "admin@staff.local",
            "email_verified": True,
            "name": "Staff Administrator",
        },
        pem_priv,
        algorithm="RS256",
    )

    auth_headers = {"Authorization": f"Bearer {token}", "X-Request-ID": "req-clock-null-1"}

    res_boot = client.post("/v2/catalog-demo/session", headers=auth_headers)
    assert res_boot.status_code == 201

    orig_override = client.app.dependency_overrides[get_catalog_db]

    def mock_get_catalog_db():
        for sess in orig_override():
            orig_exec = sess.execute

            def mock_exec(statement, *args, _orig=orig_exec, **kwargs):
                stmt_str = str(statement)
                if (
                    "clock_timestamp" in stmt_str
                    or "strftime" in stmt_str
                    or "CURRENT_TIMESTAMP" in stmt_str
                ):
                    mock_res = MagicMock()
                    mock_res.scalar.return_value = None
                    return mock_res
                return _orig(statement, *args, **kwargs)

            sess.execute = mock_exec
            yield sess

    client.app.dependency_overrides[get_catalog_db] = mock_get_catalog_db

    res_preview = client.get("/v2/catalog-demo/catalog", headers=auth_headers)

    assert res_preview.status_code == 503
    assert res_preview.json() == {
        "detail": "Catalog service or audit infrastructure temporarily unavailable"
    }
    assert res_preview.headers["Cache-Control"] == "no-store"
    assert "Authorization" in res_preview.headers["Vary"]
