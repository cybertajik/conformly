from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal
from conformly.authz.roles import Role
from conformly.identity.models import Membership, MembershipStatus, Tenant, User
from conformly.tenancy.context import TenantContextError, resolve_tenant_context


def create_membership(session: Session) -> tuple[User, Tenant]:
    user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject=str(uuid4()),
        email=f"{uuid4()}@example.test",
        display_name="Test User",
    )
    tenant = Tenant(name="Test Tenant", slug=f"tenant-{uuid4()}")
    session.add_all([user, tenant])
    session.flush()
    session.add(
        Membership(
            tenant_id=tenant.id,
            user_id=user.id,
            role=Role.CONTRIBUTOR,
            status=MembershipStatus.ACTIVE,
        )
    )
    session.commit()
    return user, tenant


def test_active_membership_resolves_same_tenant_context(session: Session) -> None:
    user, tenant = create_membership(session)

    context = resolve_tenant_context(session, Principal(user_id=user.id), tenant.id)

    assert context.tenant_id == tenant.id
    assert context.user_id == user.id
    assert context.role is Role.CONTRIBUTOR


def test_cross_tenant_selection_is_denied(session: Session) -> None:
    user, _ = create_membership(session)
    other_tenant = Tenant(name="Other Tenant", slug="other-tenant")
    session.add(other_tenant)
    session.commit()

    with pytest.raises(TenantContextError):
        resolve_tenant_context(session, Principal(user_id=user.id), other_tenant.id)


def test_user_without_membership_is_denied(session: Session) -> None:
    _, tenant = create_membership(session)

    with pytest.raises(TenantContextError):
        resolve_tenant_context(session, Principal(user_id=uuid4()), tenant.id)


def test_suspended_membership_is_denied(session: Session) -> None:
    user, tenant = create_membership(session)
    membership = session.query(Membership).one()
    membership.status = MembershipStatus.SUSPENDED
    session.commit()

    with pytest.raises(TenantContextError):
        resolve_tenant_context(session, Principal(user_id=user.id), tenant.id)
