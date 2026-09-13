from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditEvent, AuditOutcome
from conformly.auth.session import hash_session_id
from conformly.auth.tokens import (
    AuthenticationError,
    TokenClaims,
    TokenVerifier,
    get_token_verifier,
)
from conformly.authz.roles import Role
from conformly.db.session import get_db
from conformly.identity.models import (
    AuthSession,
    Membership,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
)
from conformly.main import app


class StaticVerifier(TokenVerifier):
    def __init__(self, claims: TokenClaims | None) -> None:
        self.claims = claims

    def verify(self, token: str) -> TokenClaims:
        if self.claims is None or token != "verified-token":
            raise AuthenticationError("invalid bearer token")
        return self.claims


def client_for(session: Session, claims: TokenClaims | None) -> TestClient:
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: StaticVerifier(claims)
    return TestClient(app)


def oidc_claims(*, email: str = "person@example.test") -> TokenClaims:
    return TokenClaims(
        issuer="https://identity.example.test",
        subject=str(uuid4()),
        session_id=str(uuid4()),
        expires_at=int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        email=email,
        display_name="Verified Person",
        email_verified=True,
    )


def test_verified_oidc_identity_bootstraps_hashed_application_session(
    session: Session,
) -> None:
    claims = oidc_claims()
    client = client_for(session, claims)
    try:
        response = client.post(
            "/v1/auth/session",
            headers={"Authorization": "Bearer verified-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["email"] == claims.email
    user = session.scalars(select(User)).one()
    auth_session = session.scalars(select(AuthSession)).one()
    assert auth_session.user_id == user.id
    assert auth_session.session_id_hash == hash_session_id(claims.session_id)
    serialized_audits = str(session.scalars(select(AuditEvent)).all())
    assert claims.session_id not in serialized_audits


def test_invalid_oidc_bootstrap_is_generically_denied_and_audited(session: Session) -> None:
    client = client_for(session, None)
    try:
        response = client.post(
            "/v1/auth/session",
            headers={"Authorization": "Bearer untrusted-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid authentication"}
    event = session.scalars(select(AuditEvent)).one()
    assert event.outcome is AuditOutcome.DENIED
    assert event.safe_metadata == {"reason": "invalid_identity"}
    assert "untrusted-token" not in str(event.safe_metadata)


def test_bootstrap_does_not_reactivate_a_revoked_provider_session(session: Session) -> None:
    claims = oidc_claims()
    user = User(
        oidc_issuer=claims.issuer,
        oidc_subject=claims.subject,
        email=claims.email or "person@example.test",
        display_name="Person",
    )
    session.add(user)
    session.flush()
    session.add(
        AuthSession(
            user_id=user.id,
            session_id_hash=hash_session_id(claims.session_id),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            revoked_at=datetime.now(UTC),
        )
    )
    session.commit()
    client = client_for(session, claims)
    try:
        response = client.post(
            "/v1/auth/session",
            headers={"Authorization": "Bearer verified-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert session.scalars(select(AuthSession)).one().revoked_at is not None


def test_bootstrap_refuses_automatic_email_collision_linking(session: Session) -> None:
    claims = oidc_claims(email="shared@example.test")
    session.add(
        User(
            oidc_issuer="https://another-provider.example.test",
            oidc_subject="another-subject",
            email="shared@example.test",
            display_name="Existing User",
        )
    )
    session.commit()
    client = client_for(session, claims)
    try:
        response = client.post(
            "/v1/auth/session",
            headers={"Authorization": "Bearer verified-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert session.scalar(select(User).where(User.oidc_subject == claims.subject)) is None


def test_my_tenants_returns_only_active_memberships_and_tenants(session: Session) -> None:
    claims = oidc_claims()
    user = User(
        oidc_issuer=claims.issuer,
        oidc_subject=claims.subject,
        email=claims.email or "person@example.test",
        display_name="Person",
    )
    active = Tenant(name="Active", slug=f"active-{uuid4()}")
    suspended = Tenant(
        name="Suspended",
        slug=f"suspended-{uuid4()}",
        status=TenantStatus.SUSPENDED,
    )
    unrelated = Tenant(name="Unrelated", slug=f"unrelated-{uuid4()}")
    session.add_all([user, active, suspended, unrelated])
    session.flush()
    session.add_all(
        [
            AuthSession(
                user_id=user.id,
                session_id_hash=hash_session_id(claims.session_id),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            ),
            Membership(
                tenant_id=active.id,
                user_id=user.id,
                role=Role.COMPLIANCE_MANAGER,
                status=MembershipStatus.ACTIVE,
            ),
            Membership(
                tenant_id=suspended.id,
                user_id=user.id,
                role=Role.VIEWER,
                status=MembershipStatus.ACTIVE,
            ),
        ]
    )
    session.commit()
    client = client_for(session, claims)
    try:
        response = client.get(
            "/v1/me/tenants",
            headers={"Authorization": "Bearer verified-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {
            "tenant_id": str(active.id),
            "tenant_name": "Active",
            "tenant_slug": active.slug,
            "role": "compliance_manager",
        }
    ]


def test_authenticated_user_can_revoke_current_session(session: Session) -> None:
    claims = oidc_claims()
    user = User(
        oidc_issuer=claims.issuer,
        oidc_subject=claims.subject,
        email=claims.email or "person@example.test",
        display_name="Person",
    )
    session.add(user)
    session.flush()
    auth_session = AuthSession(
        user_id=user.id,
        session_id_hash=hash_session_id(claims.session_id),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add(auth_session)
    session.commit()
    client = client_for(session, claims)
    try:
        response = client.delete(
            "/v1/auth/session",
            headers={"Authorization": "Bearer verified-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    session.refresh(auth_session)
    assert auth_session.revoked_at is not None


def test_dev_login_endpoint(session: Session) -> None:
    client = client_for(session, None)
    try:
        response = client.post(
            "/v1/auth/dev-login", json={"email": "example-user@development.invalid"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert "access_token" in payload
    assert payload["token_type"] == "bearer"
