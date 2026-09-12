from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import AuthorizationDeniedError, Principal, TenantContext, authorize
from conformly.authz.roles import Capability, Role
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.identity.invitation_tokens import InvitationTokenService
from conformly.identity.models import (
    InvitationStatus,
    Membership,
    MembershipInvitation,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
    UserStatus,
    normalize_email_address,
)
from conformly.notifications.service import enqueue_encrypted_notification
from conformly.tenancy.rls import set_rls_context

INVITATION_LIFETIME = timedelta(days=7)


class InvitationAcceptanceError(Exception):
    """Generic failure that does not disclose invitation existence or state."""


@dataclass(frozen=True, slots=True)
class IssuedInvitation:
    invitation: MembershipInvitation
    outbox_message_id: UUID


def issue_membership_invitation(
    session: Session,
    principal: Principal,
    tenant_context: TenantContext,
    *,
    email: str,
    role: Role,
    request_id: str,
    tokens: InvitationTokenService,
    codec: EncryptedFieldCodec,
    now: datetime | None = None,
) -> IssuedInvitation:
    current_time = now or datetime.now(UTC)
    normalized_email = normalize_email_address(email)
    try:
        authorize(principal, tenant_context, Capability.MEMBERSHIP_MANAGE)
    except AuthorizationDeniedError:
        record_audit_event(
            session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="membership.invite",
            resource_type="membership_invitation",
            resource_id=None,
            request_id=request_id,
            outcome=AuditOutcome.DENIED,
        )
        raise

    previous_invitations = session.scalars(
        select(MembershipInvitation).where(
            MembershipInvitation.tenant_id == tenant_context.tenant_id,
            MembershipInvitation.email == normalized_email,
            MembershipInvitation.status == InvitationStatus.PENDING,
        )
    )
    for previous in previous_invitations:
        previous.status = InvitationStatus.REVOKED

    token, token_digest = tokens.issue()
    invitation_id = uuid4()
    invitation = MembershipInvitation(
        id=invitation_id,
        tenant_id=tenant_context.tenant_id,
        email=normalized_email,
        role=role,
        status=InvitationStatus.PENDING,
        token_digest=token_digest,
        invited_by_user_id=principal.user_id,
        expires_at=current_time + INVITATION_LIFETIME,
    )
    session.add(invitation)
    message_id = uuid4()
    enqueue_encrypted_notification(
        session,
        codec,
        message_id=message_id,
        tenant_id=tenant_context.tenant_id,
        kind="membership_invitation",
        idempotency_key=f"membership-invitation:{invitation_id}",
        payload={
            "email": normalized_email,
            "invitation_token": token,
            "invitation_id": str(invitation_id),
        },
        available_at=current_time,
    )
    record_audit_event(
        session,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="membership.invite",
        resource_type="membership_invitation",
        resource_id=str(invitation_id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"role": role.value},
        occurred_at=current_time,
    )
    session.flush()
    return IssuedInvitation(invitation=invitation, outbox_message_id=message_id)


def accept_membership_invitation(
    session: Session,
    principal: Principal,
    *,
    token: str,
    request_id: str,
    tokens: InvitationTokenService,
    now: datetime | None = None,
) -> Membership:
    current_time = now or datetime.now(UTC)
    token_digest = tokens.digest(token)
    invitation = session.scalar(
        select(MembershipInvitation)
        .join(Tenant, Tenant.id == MembershipInvitation.tenant_id)
        .where(
            MembershipInvitation.token_digest == token_digest,
            MembershipInvitation.status == InvitationStatus.PENDING,
            Tenant.status == TenantStatus.ACTIVE,
        )
    )
    user = session.scalar(
        select(User).where(User.id == principal.user_id, User.status == UserStatus.ACTIVE)
    )
    expires_at = invitation.expires_at if invitation is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if (
        invitation is None
        or user is None
        or expires_at is None
        or expires_at <= current_time
        or not tokens.verify(token, invitation.token_digest)
        or user.email != invitation.email
    ):
        raise InvitationAcceptanceError("invitation cannot be accepted")

    # The invitation secret and matching authenticated email establish tenant
    # authority for the membership upsert that follows.
    set_rls_context(
        session,
        user_id=principal.user_id,
        tenant_id=invitation.tenant_id,
        tenant_verified=True,
    )

    membership = session.scalar(
        select(Membership).where(
            Membership.tenant_id == invitation.tenant_id,
            Membership.user_id == principal.user_id,
        )
    )
    if membership is None:
        membership = Membership(
            tenant_id=invitation.tenant_id,
            user_id=principal.user_id,
            role=invitation.role,
            status=MembershipStatus.ACTIVE,
        )
        session.add(membership)
    else:
        membership.role = invitation.role
        membership.status = MembershipStatus.ACTIVE

    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = current_time
    record_audit_event(
        session,
        tenant_id=invitation.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="membership.invitation_accept",
        resource_type="membership_invitation",
        resource_id=str(invitation.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        occurred_at=current_time,
    )
    session.flush()
    return membership
