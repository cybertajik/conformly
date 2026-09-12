from uuid import UUID

from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import AuthorizationDeniedError, Principal, TenantContext, authorize
from conformly.authz.roles import Capability, Role
from conformly.identity.models import Membership, MembershipStatus
from conformly.identity.repository import MembershipRepository


def list_tenant_memberships(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    request_id: str,
) -> list[Membership]:
    try:
        authorize(principal, tenant_context, Capability.MEMBERSHIP_READ)
    except AuthorizationDeniedError:
        record_audit_event(
            database,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="membership.list",
            resource_type="membership",
            resource_id=None,
            request_id=request_id,
            outcome=AuditOutcome.DENIED,
        )
        raise
    repository = MembershipRepository(database, tenant_context.tenant_id)
    memberships = repository.list_memberships()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="membership.list",
        resource_type="membership",
        resource_id=None,
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"record_count": len(memberships)},
    )
    return memberships


class MembershipNotFoundError(Exception):
    """Raised without revealing whether an ID exists in another tenant."""


class MembershipInvariantError(Exception):
    """Raised when a change would violate tenant ownership invariants."""


def change_membership_role(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    membership_id: UUID,
    new_role: Role,
    request_id: str,
) -> Membership:
    try:
        authorize(principal, tenant_context, Capability.MEMBERSHIP_MANAGE)
    except AuthorizationDeniedError:
        record_audit_event(
            database,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="membership.role_change",
            resource_type="membership",
            resource_id=str(membership_id),
            request_id=request_id,
            outcome=AuditOutcome.DENIED,
        )
        raise

    repository = MembershipRepository(database, tenant_context.tenant_id)
    membership = repository.get_membership(membership_id)
    if membership is None:
        record_audit_event(
            database,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="membership.role_change",
            resource_type="membership",
            resource_id=str(membership_id),
            request_id=request_id,
            outcome=AuditOutcome.DENIED,
            metadata={"reason": "not_found_in_tenant"},
        )
        raise MembershipNotFoundError

    if (
        membership.role is Role.OWNER
        and new_role is not Role.OWNER
        and membership.status is MembershipStatus.ACTIVE
        and repository.count_active_role(Role.OWNER, MembershipStatus.ACTIVE) <= 1
    ):
        record_audit_event(
            database,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="membership.role_change",
            resource_type="membership",
            resource_id=str(membership.id),
            request_id=request_id,
            outcome=AuditOutcome.FAILURE,
            metadata={"reason": "last_active_owner"},
        )
        raise MembershipInvariantError("tenant must retain an active owner")

    previous_role = membership.role
    membership.role = new_role
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="membership.role_change",
        resource_type="membership",
        resource_id=str(membership.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"previous_role": previous_role.value, "new_role": new_role.value},
    )
    database.flush()
    return membership


def revoke_membership(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    membership_id: UUID,
    request_id: str,
) -> Membership:
    try:
        authorize(principal, tenant_context, Capability.MEMBERSHIP_MANAGE)
    except AuthorizationDeniedError:
        record_audit_event(
            database,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="membership.revoke",
            resource_type="membership",
            resource_id=str(membership_id),
            request_id=request_id,
            outcome=AuditOutcome.DENIED,
        )
        raise

    repository = MembershipRepository(database, tenant_context.tenant_id)
    membership = repository.get_membership(membership_id)
    if membership is None:
        record_audit_event(
            database,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="membership.revoke",
            resource_type="membership",
            resource_id=str(membership_id),
            request_id=request_id,
            outcome=AuditOutcome.DENIED,
            metadata={"reason": "not_found_in_tenant"},
        )
        raise MembershipNotFoundError

    if membership.status is MembershipStatus.REVOKED:
        record_audit_event(
            database,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="membership.revoke",
            resource_type="membership",
            resource_id=str(membership.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"already_revoked": True},
        )
        return membership

    if (
        membership.role is Role.OWNER
        and membership.status is MembershipStatus.ACTIVE
        and repository.count_active_role(Role.OWNER, MembershipStatus.ACTIVE) <= 1
    ):
        record_audit_event(
            database,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="membership.revoke",
            resource_type="membership",
            resource_id=str(membership.id),
            request_id=request_id,
            outcome=AuditOutcome.FAILURE,
            metadata={"reason": "last_active_owner"},
        )
        raise MembershipInvariantError("tenant must retain an active owner")

    previous_status = membership.status
    membership.status = MembershipStatus.REVOKED
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="membership.revoke",
        resource_type="membership",
        resource_id=str(membership.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"previous_status": previous_status.value},
    )
    database.flush()
    return membership
