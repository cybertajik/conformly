"""Backend unit tests for workforce OIDC/MFA authentication and staff sessions."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from conformly.catalog_demo.auth import (
    DefaultWorkforceTokenVerifier,
    TestWorkforceTokenVerifier,
    WorkforceAuthError,
    create_staff_session,
    get_current_staff_session_data,
    parse_workforce_payload,
    resolve_and_authorize_admin_user,
    revoke_staff_session,
    verify_auth_time_and_token_expiry,
)
from conformly.db.base import Base
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
def sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_workforce_verifier_success(rsa_keys):
    pem_priv, pem_pub = rsa_keys
    verifier = TestWorkforceTokenVerifier("https://workforce.test", "staff-client", pem_pub)

    now_ts = int(datetime.now(UTC).timestamp())
    payload = {
        "iss": "https://workforce.test",
        "sub": "admin-1",
        "sid": "session-12345",
        "aud": "staff-client",
        "exp": now_ts + 3600,
        "auth_time": now_ts,
        "email": "admin@test.local",
        "email_verified": True,
        "amr": ["otp", "mfa"],
        "name": "Admin One",
    }
    token = jwt.encode(payload, pem_priv, algorithm="RS256")
    claims = verifier.verify(token)
    assert claims.subject == "admin-1"
    assert claims.session_id == "session-12345"
    assert claims.email == "admin@test.local"
    assert claims.email_verified is True
    assert claims.auth_time == now_ts
    assert claims.mfa_verified is True


def test_workforce_rejects_hs256():
    payload = {
        "iss": "https://workforce.test",
        "sub": "admin-1",
        "sid": "session-1",
        "aud": "staff-client",
        "exp": int(datetime.now(UTC).timestamp()) + 3600,
        "auth_time": int(datetime.now(UTC).timestamp()),
        "email": "admin@test.local",
        "email_verified": True,
        "amr": ["otp"],
    }
    token = jwt.encode(payload, "secret-key", algorithm="HS256")
    verifier = TestWorkforceTokenVerifier("https://workforce.test", "staff-client", "public-key")
    with pytest.raises(WorkforceAuthError, match="Unsupported token algorithm"):
        verifier.verify(token)


def test_workforce_requires_integer_auth_time():
    now_ts = int(datetime.now(UTC).timestamp())
    base = {
        "iss": "https://workforce.test",
        "sub": "admin-1",
        "sid": "sid-1",
        "aud": "staff-client",
        "exp": now_ts + 3600,
        "email": "admin@test.local",
        "email_verified": True,
        "amr": ["otp"],
    }

    # String auth_time
    payload_str = base | {"auth_time": str(now_ts)}
    with pytest.raises(WorkforceAuthError, match="Missing or invalid integer auth_time"):
        parse_workforce_payload(payload_str)

    # Boolean auth_time
    payload_bool = base | {"auth_time": True}
    with pytest.raises(WorkforceAuthError, match="Missing or invalid integer auth_time"):
        parse_workforce_payload(payload_bool)

    # Missing auth_time
    payload_none = base.copy()
    del payload_none["amr"]
    with pytest.raises(WorkforceAuthError, match="Missing or invalid integer auth_time"):
        parse_workforce_payload(payload_none)


def test_workforce_requires_verified_email():
    now_ts = int(datetime.now(UTC).timestamp())
    base = {
        "iss": "https://workforce.test",
        "sub": "admin-1",
        "sid": "sid-1",
        "aud": "staff-client",
        "exp": now_ts + 3600,
        "auth_time": now_ts,
        "email": "admin@test.local",
        "amr": ["otp"],
    }

    # email_verified False
    with pytest.raises(WorkforceAuthError, match="Workforce email must be verified"):
        parse_workforce_payload(base | {"email_verified": False})

    # email_verified missing
    with pytest.raises(WorkforceAuthError, match="Workforce email must be verified"):
        parse_workforce_payload(base)


def test_workforce_requires_mfa_evidence():
    now_ts = int(datetime.now(UTC).timestamp())
    base = {
        "iss": "https://workforce.test",
        "sub": "admin-1",
        "sid": "sid-1",
        "aud": "staff-client",
        "exp": now_ts + 3600,
        "auth_time": now_ts,
        "email": "admin@test.local",
        "email_verified": True,
    }

    # Bare mfa_verified flag must be rejected
    with pytest.raises(WorkforceAuthError, match="Signed MFA proof"):
        parse_workforce_payload(base | {"mfa_verified": True})

    # Unrecognized AMR
    with pytest.raises(WorkforceAuthError, match="Signed MFA proof"):
        parse_workforce_payload(base | {"amr": ["pwd", "sms_unverified"]})

    # Recognized AMR
    claims_amr = parse_workforce_payload(base | {"amr": ["totp"]})
    assert claims_amr.mfa_verified is True

    # Recognized ACR
    claims_acr = parse_workforce_payload(base | {"acr": "loa2"})
    assert claims_acr.mfa_verified is True


def test_workforce_stale_and_future_auth_time():
    now_dt = datetime.now(UTC)

    # Future (+10 seconds)
    future_claims = parse_workforce_payload(
        {
            "iss": "https://workforce.test",
            "sub": "s1",
            "sid": "sid1",
            "aud": "staff-client",
            "exp": int((now_dt + timedelta(hours=1)).timestamp()),
            "auth_time": int((now_dt + timedelta(seconds=10)).timestamp()),
            "email": "a@test.local",
            "email_verified": True,
            "amr": ["otp"],
        }
    )
    with pytest.raises(WorkforceAuthError, match="future"):
        verify_auth_time_and_token_expiry(future_claims, now_dt)

    # Stale (20 minutes ago)
    stale_claims = parse_workforce_payload(
        {
            "iss": "https://workforce.test",
            "sub": "s1",
            "sid": "sid1",
            "aud": "staff-client",
            "exp": int((now_dt + timedelta(hours=1)).timestamp()),
            "auth_time": int((now_dt - timedelta(minutes=20)).timestamp()),
            "email": "a@test.local",
            "email_verified": True,
            "amr": ["otp"],
        }
    )
    with pytest.raises(WorkforceAuthError, match="Authentication expired"):
        verify_auth_time_and_token_expiry(stale_claims, now_dt)


def test_workforce_user_authorization_strict_lookup(sqlite_session):
    now_ts = int(datetime.now(UTC).timestamp())
    claims = parse_workforce_payload(
        {
            "iss": "https://workforce.test",
            "sub": "admin-subject-1",
            "sid": "sid-1",
            "aud": "staff-client",
            "exp": now_ts + 3600,
            "auth_time": now_ts,
            "email": "admin@conformly.local",
            "email_verified": True,
            "amr": ["otp"],
        }
    )

    # 1. User not in DB
    with pytest.raises(WorkforceAuthError, match="not an active platform administrator"):
        resolve_and_authorize_admin_user(sqlite_session, claims)

    # 2. Email fallback cannot match user if subject differs
    other_user = User(
        oidc_issuer="https://workforce.test",
        oidc_subject="different-subject",
        email="admin@conformly.local",
        display_name="Admin",
        status=UserStatus.ACTIVE,
        is_platform_admin=True,
    )
    sqlite_session.add(other_user)
    sqlite_session.commit()

    with pytest.raises(WorkforceAuthError, match="not an active platform administrator"):
        resolve_and_authorize_admin_user(sqlite_session, claims)

    # 3. User with matching subject but mismatched email rejected
    sqlite_session.delete(other_user)
    sqlite_session.commit()

    mismatched_email_admin = User(
        oidc_issuer="https://workforce.test",
        oidc_subject="admin-subject-1",
        email="different@conformly.local",
        display_name="Admin",
        status=UserStatus.ACTIVE,
        is_platform_admin=True,
    )
    sqlite_session.add(mismatched_email_admin)
    sqlite_session.commit()

    with pytest.raises(WorkforceAuthError, match="mismatch"):
        resolve_and_authorize_admin_user(sqlite_session, claims)

    # 4. User is matching subject and email, but is_platform_admin=False
    mismatched_email_admin.email = "admin@conformly.local"
    mismatched_email_admin.is_platform_admin = False
    sqlite_session.commit()

    with pytest.raises(WorkforceAuthError, match="not an active platform administrator"):
        resolve_and_authorize_admin_user(sqlite_session, claims)

    # 5. User is active platform admin
    mismatched_email_admin.is_platform_admin = True
    sqlite_session.commit()

    authorized = resolve_and_authorize_admin_user(sqlite_session, claims)
    assert authorized.id == mismatched_email_admin.id


def test_staff_session_bootstrap_and_revoke_flow(rsa_keys, sqlite_session):
    pem_priv, pem_pub = rsa_keys
    verifier = TestWorkforceTokenVerifier("https://workforce.test", "staff-client", pem_pub)
    now_ts = int(datetime.now(UTC).timestamp())

    admin_user = User(
        oidc_issuer="https://workforce.test",
        oidc_subject="staff-boss-1",
        email="boss@conformly.local",
        display_name="Staff Boss",
        status=UserStatus.ACTIVE,
        is_platform_admin=True,
    )
    sqlite_session.add(admin_user)
    sqlite_session.commit()

    token = jwt.encode(
        {
            "iss": "https://workforce.test",
            "sub": "staff-boss-1",
            "sid": "session-boss-1",
            "aud": "staff-client",
            "exp": now_ts + 3600,
            "auth_time": now_ts,
            "email": "boss@conformly.local",
            "email_verified": True,
            "amr": ["webauthn"],
        },
        pem_priv,
        algorithm="RS256",
    )

    # Bootstrap session
    resp = create_staff_session(sqlite_session, token, "req-1", verifier)
    assert resp.user_id == str(admin_user.id)
    assert resp.capabilities == ["DRAFT_READ"]

    # Active session retrieval via token
    user, sess, auth_dt, expires_at = get_current_staff_session_data(
        sqlite_session, token, verifier
    )
    assert user.id == admin_user.id
    assert sess.revoked_at is None

    # Revoke session
    revoke_staff_session(sqlite_session, token, "req-2", verifier)

    # Subsequent retrieval fails with 401
    with pytest.raises(WorkforceAuthError, match="Active staff session not found"):
        get_current_staff_session_data(sqlite_session, token, verifier)


def test_default_workforce_token_verifier_with_asymmetric_keys(rsa_keys):
    """Test actual DefaultWorkforceTokenVerifier with generated asymmetric keys and stubbed JWKS."""
    import json
    from unittest.mock import patch

    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
    from jwt import PyJWK
    from jwt.algorithms import RSAAlgorithm

    pem_priv, pem_pub = rsa_keys
    public_key = serialization.load_pem_public_key(pem_pub)
    assert isinstance(public_key, RSAPublicKey)
    jwk_dict = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk_dict["kid"] = "staff-key-1"
    jwk_dict["alg"] = "RS256"
    jwk_dict["use"] = "sig"

    now_ts = int(datetime.now(UTC).timestamp())
    payload = {
        "iss": "https://workforce.production.test",
        "sub": "staff-admin-99",
        "sid": "session-default-verifier-1",
        "aud": "staff-portal-client",
        "exp": now_ts + 3600,
        "auth_time": now_ts,
        "email": "staff99@conformly.local",
        "email_verified": True,
        "amr": ["fido", "mfa"],
        "name": "Staff Ninety-Nine",
    }
    token = jwt.encode(
        payload,
        pem_priv,
        algorithm="RS256",
        headers={"kid": "staff-key-1", "alg": "RS256"},
    )

    verifier = DefaultWorkforceTokenVerifier(
        issuer="https://workforce.production.test",
        audience="staff-portal-client",
        jwks_url="https://workforce.production.test/.well-known/jwks.json",
    )

    # Stub the JWKS client's signing key retrieval
    stub_jwk = PyJWK.from_json(json.dumps(jwk_dict))
    with patch.object(verifier._jwks_client, "get_signing_key_from_jwt", return_value=stub_jwk):
        claims = verifier.verify(token)
        assert claims.subject == "staff-admin-99"
        assert claims.session_id == "session-default-verifier-1"
        assert claims.email == "staff99@conformly.local"
        assert claims.email_verified is True
        assert claims.mfa_verified is True

        # Negative test: HS256 algorithm rejection without reflecting raw alg
        hs_token = jwt.encode(payload, "secret-key", algorithm="HS256")
        with pytest.raises(WorkforceAuthError, match="Unsupported token algorithm"):
            verifier.verify(hs_token)

        # Negative test: invalid signature
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_priv = other_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        invalid_sig_token = jwt.encode(
            payload,
            other_priv,
            algorithm="RS256",
            headers={"kid": "staff-key-1", "alg": "RS256"},
        )
        with pytest.raises(WorkforceAuthError, match="Invalid workforce bearer token"):
            verifier.verify(invalid_sig_token)


def test_create_staff_session_rejects_past_expiry(rsa_keys, sqlite_session):
    """Verify create_staff_session refuses to create sessions with past expiry."""
    pem_priv, pem_pub = rsa_keys
    verifier = TestWorkforceTokenVerifier("https://workforce.test", "staff-client", pem_pub)

    # Stale auth time 14.9 minutes ago
    past_auth_ts = int((datetime.now(UTC) - timedelta(seconds=895)).timestamp())

    admin_user = User(
        oidc_issuer="https://workforce.test",
        oidc_subject="staff-boss-expired",
        email="expired@conformly.local",
        display_name="Staff Expired",
        status=UserStatus.ACTIVE,
        is_platform_admin=True,
    )
    sqlite_session.add(admin_user)
    sqlite_session.commit()

    # Token already expired 10 seconds ago
    token = jwt.encode(
        {
            "iss": "https://workforce.test",
            "sub": "staff-boss-expired",
            "sid": "session-boss-expired",
            "aud": "staff-client",
            "exp": int((datetime.now(UTC) - timedelta(seconds=10)).timestamp()),
            "auth_time": past_auth_ts,
            "email": "expired@conformly.local",
            "email_verified": True,
            "amr": ["webauthn"],
        },
        pem_priv,
        algorithm="RS256",
    )

    with pytest.raises(WorkforceAuthError, match="expired"):
        create_staff_session(sqlite_session, token, "req-expired", verifier)
