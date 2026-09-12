import base64
import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conformly.audit.models import AuditEvent, AuditOutcome
from conformly.auth.session import hash_session_id
from conformly.auth.tokens import TokenClaims, TokenVerifier, get_token_verifier
from conformly.authz.roles import Role
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.db.session import get_db
from conformly.identity.invitation_tokens import (
    InvitationTokenService,
    get_invitation_token_service,
)
from conformly.identity.models import AuthSession, Membership, MembershipStatus, Tenant, User
from conformly.main import app
from conformly.notifications.models import NotificationOutbox
from conformly.notifications.service import decrypt_notification_payload


class FakeTokenVerifier(TokenVerifier):
    def __init__(self, claims: TokenClaims) -> None:
        self.claims = claims

    def verify(self, token: str) -> TokenClaims:
        assert token == "opaque-test-token"
        return self.claims


def encryption_codec() -> EncryptedFieldCodec:
    key = base64.b64encode(os.urandom(32)).decode("ascii")
    return EncryptedFieldCodec(
        EnvelopeEncryptionService(
            AES256GCMProvider(), LocalKeyManagementProvider({"v1": key}, "v1")
        )
    )


def authenticated_user(session: Session, *, email: str) -> tuple[User, TokenClaims]:
    session_id = str(uuid4())
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject=str(uuid4()),
        email=email,
        display_name="API User",
    )
    session.add(user)
    session.flush()
    session.add(
        AuthSession(
            user_id=user.id,
            session_id_hash=hash_session_id(session_id),
            expires_at=expires_at,
        )
    )
    session.commit()
    return user, TokenClaims(
        issuer=user.oidc_issuer,
        subject=user.oidc_subject,
        session_id=session_id,
        expires_at=int(expires_at.timestamp()),
    )


def configure_client(
    session: Session,
    claims: TokenClaims,
    tokens: InvitationTokenService,
    codec: EncryptedFieldCodec,
) -> TestClient:
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(claims)
    app.dependency_overrides[get_invitation_token_service] = lambda: tokens
    app.dependency_overrides[get_encrypted_field_codec] = lambda: codec
    return TestClient(app)


def test_invitation_api_queues_encrypted_delivery_without_returning_secret(
    session: Session,
) -> None:
    owner, claims = authenticated_user(session, email="owner@example.test")
    tenant = Tenant(name="API Invitation Tenant", slug=f"invite-api-{uuid4()}")
    session.add(tenant)
    session.flush()
    session.add(
        Membership(
            tenant_id=tenant.id,
            user_id=owner.id,
            role=Role.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    session.commit()
    tokens = InvitationTokenService(os.urandom(32))
    codec = encryption_codec()
    client = configure_client(session, claims, tokens, codec)
    try:
        response = client.post(
            f"/v1/tenants/{tenant.id}/invitations",
            headers={"Authorization": "Bearer opaque-test-token"},
            json={"email": " Invitee@Example.TEST ", "role": "contributor"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["email"] == "invitee@example.test"
    assert "token" not in json.dumps(response.json()).lower()
    outbox = session.query(NotificationOutbox).one()
    stored = json.dumps(outbox.encrypted_payload)
    assert "invitee@example.test" not in stored
    assert "invitation_token" not in stored
    assert decrypt_notification_payload(codec, outbox)["email"] == "invitee@example.test"


def test_authenticated_matching_user_accepts_invitation_through_api(session: Session) -> None:
    owner, owner_claims = authenticated_user(session, email="owner@example.test")
    tenant = Tenant(name="Acceptance Tenant", slug=f"accept-api-{uuid4()}")
    session.add(tenant)
    session.flush()
    session.add(
        Membership(
            tenant_id=tenant.id,
            user_id=owner.id,
            role=Role.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    session.commit()
    tokens = InvitationTokenService(os.urandom(32))
    codec = encryption_codec()
    client = configure_client(session, owner_claims, tokens, codec)
    response = client.post(
        f"/v1/tenants/{tenant.id}/invitations",
        headers={"Authorization": "Bearer opaque-test-token"},
        json={"email": "invitee@example.test", "role": "auditor"},
    )
    assert response.status_code == 202
    outbox = session.query(NotificationOutbox).one()
    token = decrypt_notification_payload(codec, outbox)["invitation_token"]

    invitee, invitee_claims = authenticated_user(session, email="invitee@example.test")
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(invitee_claims)
    try:
        response = client.post(
            "/v1/invitations/accept",
            headers={"Authorization": "Bearer opaque-test-token"},
            json={"token": token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"tenant_id": str(tenant.id), "role": "auditor"}
    membership = session.query(Membership).filter_by(user_id=invitee.id).one()
    assert membership.tenant_id == tenant.id


def test_invalid_invitation_acceptance_is_safely_audited(session: Session) -> None:
    user, claims = authenticated_user(session, email="person@example.test")
    tokens = InvitationTokenService(os.urandom(32))
    client = configure_client(session, claims, tokens, encryption_codec())
    invalid_token = "invalid-secret-value"
    try:
        response = client.post(
            "/v1/invitations/accept",
            headers={"Authorization": "Bearer opaque-test-token"},
            json={"token": invalid_token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    event = session.query(AuditEvent).one()
    assert event.tenant_id is None
    assert event.actor_id == user.id
    assert event.outcome is AuditOutcome.DENIED
    assert event.safe_metadata == {"reason": "invalid_invitation"}
    assert invalid_token not in str(event.safe_metadata)
