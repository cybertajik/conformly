import base64
import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditEvent, AuditOutcome
from conformly.authz.policy import AuthorizationDeniedError, Principal, TenantContext
from conformly.authz.roles import Role
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.identity.invitation_tokens import InvitationTokenService
from conformly.identity.invitations import (
    InvitationAcceptanceError,
    accept_membership_invitation,
    issue_membership_invitation,
)
from conformly.identity.models import (
    InvitationStatus,
    Membership,
    MembershipInvitation,
    MembershipStatus,
    Tenant,
    User,
)
from conformly.notifications.models import NotificationOutbox
from conformly.notifications.service import decrypt_notification_payload


def codec() -> EncryptedFieldCodec:
    key = base64.b64encode(os.urandom(32)).decode("ascii")
    return EncryptedFieldCodec(
        EnvelopeEncryptionService(
            AES256GCMProvider(), LocalKeyManagementProvider({"v1": key}, "v1")
        )
    )


def seed_invitation_context(
    session: Session, *, invited_email: str = "invitee@example.test"
) -> tuple[Principal, TenantContext, User]:
    owner = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject="owner-subject",
        email="owner@example.test",
        display_name="Owner",
    )
    invited_user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject="invitee-subject",
        email=invited_email,
        display_name="Invitee",
    )
    tenant = Tenant(name="Invitation Tenant", slug=f"invite-{uuid4()}")
    session.add_all([owner, invited_user, tenant])
    session.flush()
    session.add(
        Membership(
            tenant_id=tenant.id,
            user_id=owner.id,
            role=Role.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    session.flush()
    return (
        Principal(user_id=owner.id),
        TenantContext(tenant_id=tenant.id, user_id=owner.id, role=Role.OWNER),
        invited_user,
    )


def test_invitation_and_delivery_secret_are_never_stored_in_plaintext(session: Session) -> None:
    principal, tenant_context, _ = seed_invitation_context(session)
    token_service = InvitationTokenService(os.urandom(32))
    encryption = codec()

    issued = issue_membership_invitation(
        session,
        principal,
        tenant_context,
        email=" Invitee@Example.TEST ",
        role=Role.CONTRIBUTOR,
        request_id="request-invite",
        tokens=token_service,
        codec=encryption,
    )

    invitation = issued.invitation
    outbox = session.get(NotificationOutbox, issued.outbox_message_id)
    assert outbox is not None
    serialized_outbox = json.dumps(outbox.encrypted_payload)
    assert invitation.email == "invitee@example.test"
    assert invitation.email not in serialized_outbox
    assert invitation.token_digest not in serialized_outbox
    delivery = decrypt_notification_payload(encryption, outbox)
    assert delivery["email"] == invitation.email
    assert token_service.verify(delivery["invitation_token"], invitation.token_digest)
    audit = session.scalars(select(AuditEvent)).one()
    assert audit.safe_metadata == {"role": "contributor"}


def test_invited_user_can_accept_once(session: Session) -> None:
    owner, tenant_context, invited_user = seed_invitation_context(session)
    token_service = InvitationTokenService(os.urandom(32))
    encryption = codec()
    issued = issue_membership_invitation(
        session,
        owner,
        tenant_context,
        email=invited_user.email,
        role=Role.AUDITOR,
        request_id="request-issue",
        tokens=token_service,
        codec=encryption,
    )
    outbox = session.get(NotificationOutbox, issued.outbox_message_id)
    assert outbox is not None
    token = decrypt_notification_payload(encryption, outbox)["invitation_token"]

    membership = accept_membership_invitation(
        session,
        Principal(user_id=invited_user.id),
        token=token,
        request_id="request-accept",
        tokens=token_service,
    )

    assert membership.tenant_id == tenant_context.tenant_id
    assert membership.role is Role.AUDITOR
    assert membership.status is MembershipStatus.ACTIVE
    assert issued.invitation.status is InvitationStatus.ACCEPTED
    with pytest.raises(InvitationAcceptanceError):
        accept_membership_invitation(
            session,
            Principal(user_id=invited_user.id),
            token=token,
            request_id="request-replay",
            tokens=token_service,
        )


def test_wrong_email_and_expired_invitation_fail_generically(session: Session) -> None:
    owner, tenant_context, invited_user = seed_invitation_context(
        session, invited_email="different@example.test"
    )
    token_service = InvitationTokenService(os.urandom(32))
    encryption = codec()
    now = datetime.now(UTC)
    issued = issue_membership_invitation(
        session,
        owner,
        tenant_context,
        email="target@example.test",
        role=Role.VIEWER,
        request_id="request-issue",
        tokens=token_service,
        codec=encryption,
        now=now,
    )
    outbox = session.get(NotificationOutbox, issued.outbox_message_id)
    assert outbox is not None
    token = decrypt_notification_payload(encryption, outbox)["invitation_token"]

    with pytest.raises(InvitationAcceptanceError, match="invitation cannot be accepted"):
        accept_membership_invitation(
            session,
            Principal(user_id=invited_user.id),
            token=token,
            request_id="request-wrong-email",
            tokens=token_service,
        )
    issued.invitation.email = invited_user.email
    with pytest.raises(InvitationAcceptanceError, match="invitation cannot be accepted"):
        accept_membership_invitation(
            session,
            Principal(user_id=invited_user.id),
            token=token,
            request_id="request-expired",
            tokens=token_service,
            now=now + timedelta(days=8),
        )


def test_new_invitation_revokes_previous_pending_invitation(session: Session) -> None:
    principal, tenant_context, _ = seed_invitation_context(session)
    token_service = InvitationTokenService(os.urandom(32))
    encryption = codec()
    first = issue_membership_invitation(
        session,
        principal,
        tenant_context,
        email="invitee@example.test",
        role=Role.VIEWER,
        request_id="request-first",
        tokens=token_service,
        codec=encryption,
    )
    second = issue_membership_invitation(
        session,
        principal,
        tenant_context,
        email="INVITEE@example.test",
        role=Role.CONTRIBUTOR,
        request_id="request-second",
        tokens=token_service,
        codec=encryption,
    )

    assert first.invitation.status is InvitationStatus.REVOKED
    assert second.invitation.status is InvitationStatus.PENDING


def test_invitation_creation_and_outbox_are_transactional(session: Session) -> None:
    principal, tenant_context, _ = seed_invitation_context(session)
    issue_membership_invitation(
        session,
        principal,
        tenant_context,
        email="invitee@example.test",
        role=Role.VIEWER,
        request_id="request-rollback",
        tokens=InvitationTokenService(os.urandom(32)),
        codec=codec(),
    )

    session.rollback()

    assert session.scalar(select(MembershipInvitation)) is None
    assert session.scalar(select(NotificationOutbox)) is None


def test_viewer_cannot_issue_invitation(session: Session) -> None:
    principal, tenant_context, _ = seed_invitation_context(session)
    tenant_context = TenantContext(
        tenant_id=tenant_context.tenant_id,
        user_id=tenant_context.user_id,
        role=Role.VIEWER,
    )

    with pytest.raises(AuthorizationDeniedError):
        issue_membership_invitation(
            session,
            principal,
            tenant_context,
            email="invitee@example.test",
            role=Role.VIEWER,
            request_id="request-denied",
            tokens=InvitationTokenService(os.urandom(32)),
            codec=codec(),
        )

    audit = session.scalars(select(AuditEvent)).one()
    assert audit.outcome is AuditOutcome.DENIED
