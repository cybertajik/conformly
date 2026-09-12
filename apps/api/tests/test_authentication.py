from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy.orm import Session

from conformly.auth.session import authenticate_claims, hash_session_id
from conformly.auth.tokens import AuthenticationError, OIDCTokenVerifier, TokenClaims
from conformly.identity.models import AuthSession, User


def create_user_session(session: Session, *, session_id: str, revoked: bool = False) -> User:
    now = datetime.now(UTC)
    user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject=str(uuid4()),
        email=f"{uuid4()}@example.test",
        display_name="Authentication Test",
    )
    session.add(user)
    session.flush()
    session.add(
        AuthSession(
            user_id=user.id,
            session_id_hash=hash_session_id(session_id),
            expires_at=now + timedelta(hours=1),
            revoked_at=now if revoked else None,
        )
    )
    session.commit()
    return user


def claims_for(user: User, session_id: str, *, expires_at: datetime | None = None) -> TokenClaims:
    expiry = expires_at or datetime.now(UTC) + timedelta(minutes=30)
    return TokenClaims(
        issuer=user.oidc_issuer,
        subject=user.oidc_subject,
        session_id=session_id,
        expires_at=int(expiry.timestamp()),
    )


def test_active_session_authenticates(session: Session) -> None:
    user = create_user_session(session, session_id="active-session")

    principal = authenticate_claims(session, claims_for(user, "active-session"))

    assert principal.user_id == user.id


def test_revoked_session_is_denied(session: Session) -> None:
    user = create_user_session(session, session_id="revoked-session", revoked=True)

    with pytest.raises(AuthenticationError):
        authenticate_claims(session, claims_for(user, "revoked-session"))


def test_expired_token_is_denied(session: Session) -> None:
    user = create_user_session(session, session_id="expired-session")
    expired_at = datetime.now(UTC) - timedelta(minutes=1)

    with pytest.raises(AuthenticationError):
        authenticate_claims(
            session,
            claims_for(user, "expired-session", expires_at=expired_at),
        )


def test_oidc_verifier_validates_signature_issuer_audience_and_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    token = jwt.encode(
        {
            "iss": "https://identity.example.test",
            "sub": "subject-1",
            "sid": "session-1",
            "aud": "conformly-api",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "email": "subject-1@example.test",
            "email_verified": True,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    verifier = OIDCTokenVerifier(
        issuer="https://identity.example.test",
        audience="conformly-api",
        jwks_url="https://identity.example.test/.well-known/jwks.json",
    )
    monkeypatch.setattr(
        verifier._jwks_client,
        "get_signing_key_from_jwt",
        lambda _: SimpleNamespace(key=public_key),
    )

    claims = verifier.verify(token)

    assert claims.subject == "subject-1"
    assert claims.session_id == "session-1"
    assert claims.email_verified is True


def test_oidc_verifier_rejects_wrong_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        {
            "iss": "https://identity.example.test",
            "sub": "subject-1",
            "sid": "session-1",
            "aud": "another-api",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "email": "subject-1@example.test",
            "email_verified": True,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    verifier = OIDCTokenVerifier(
        issuer="https://identity.example.test",
        audience="conformly-api",
        jwks_url="https://identity.example.test/.well-known/jwks.json",
    )
    monkeypatch.setattr(
        verifier._jwks_client,
        "get_signing_key_from_jwt",
        lambda _: SimpleNamespace(key=private_key.public_key()),
    )

    with pytest.raises(AuthenticationError):
        verifier.verify(token)


def test_dev_token_verifier_and_mint_roundtrip() -> None:
    from conformly.auth.tokens import DevTokenVerifier, mint_dev_token

    token = mint_dev_token(
        email="dev-tester@development.invalid",
        subject="dev-tester",
        display_name="Dev Tester",
    )
    verifier = DevTokenVerifier()
    claims = verifier.verify(token)

    assert claims.email == "dev-tester@development.invalid"
    assert claims.subject == "dev-tester"
    assert claims.display_name == "Dev Tester"
    assert claims.email_verified is True
    assert claims.issuer == "https://development.invalid"

