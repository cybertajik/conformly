from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal, TenantContext
from conformly.identity.models import (
    Membership,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
    UserStatus,
)
from conformly.tenancy.rls import set_rls_context


class TenantContextError(Exception):
    """Raised when a tenant selector cannot produce an authorized context."""


def resolve_tenant_context(
    session: Session, principal: Principal, selected_tenant_id: UUID
) -> TenantContext:
    # Bootstrap access can see only this user's membership. Tenant-wide access is
    # enabled only after the application has validated that active membership.
    set_rls_context(
        session,
        user_id=principal.user_id,
        tenant_id=selected_tenant_id,
        tenant_verified=False,
    )
    current_time = datetime.now(UTC)
    membership = session.scalar(
        select(Membership)
        .join(Membership.tenant)
        .join(Membership.user)
        .where(
            Membership.tenant_id == selected_tenant_id,
            Membership.user_id == principal.user_id,
            Membership.status == MembershipStatus.ACTIVE,
            or_(
                Tenant.status == TenantStatus.ACTIVE,
                and_(
                    Tenant.status == TenantStatus.CANCELLING,
                    Tenant.export_until.is_not(None),
                    Tenant.export_until >= current_time,
                ),
            ),
            User.status == UserStatus.ACTIVE,
        )
    )
    if membership is None:
        raise TenantContextError("active tenant membership not found")

    # Enforce engagement expiration
    exp: datetime | None = None
    if membership.expires_at is not None:
        exp = (
            membership.expires_at
            if membership.expires_at.tzinfo is not None
            else membership.expires_at.replace(tzinfo=UTC)
        )
        if current_time >= exp:
            raise TenantContextError("membership engagement has expired")

    # Workforce members have no standing access: require active expiring engagement
    if membership.is_workforce and membership.expires_at is None:
        raise TenantContextError("workforce members must have an active expiring engagement")

    # External advisors must have a time-limited engagement
    if membership.is_external_advisor and membership.expires_at is None:
        raise TenantContextError("external advisors must have a time-limited engagement")

    set_rls_context(
        session,
        user_id=principal.user_id,
        tenant_id=selected_tenant_id,
        tenant_verified=True,
    )
    return TenantContext(
        tenant_id=membership.tenant_id,
        user_id=membership.user_id,
        role=membership.role,
        legal_entity_id=membership.legal_entity_id,
        business_unit_id=membership.business_unit_id,
        is_external_advisor=membership.is_external_advisor,
        expires_at=exp,
        is_workforce=membership.is_workforce,
    )
