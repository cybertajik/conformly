from uuid import uuid4

import pytest

from conformly.authz.policy import (
    AuthorizationDeniedError,
    Principal,
    TenantContext,
    authorize,
)
from conformly.authz.roles import Capability, Role


def test_owner_has_membership_management_capability() -> None:
    user_id = uuid4()
    authorize(
        Principal(user_id=user_id),
        TenantContext(tenant_id=uuid4(), user_id=user_id, role=Role.OWNER),
        Capability.MEMBERSHIP_MANAGE,
    )


def test_viewer_cannot_manage_memberships() -> None:
    user_id = uuid4()
    with pytest.raises(AuthorizationDeniedError):
        authorize(
            Principal(user_id=user_id),
            TenantContext(tenant_id=uuid4(), user_id=user_id, role=Role.VIEWER),
            Capability.MEMBERSHIP_MANAGE,
        )


def test_principal_cannot_reuse_another_users_tenant_context() -> None:
    with pytest.raises(AuthorizationDeniedError):
        authorize(
            Principal(user_id=uuid4()),
            TenantContext(tenant_id=uuid4(), user_id=uuid4(), role=Role.OWNER),
            Capability.TENANT_READ,
        )


def test_platform_admin_does_not_implicitly_bypass_tenant_policy() -> None:
    with pytest.raises(AuthorizationDeniedError):
        authorize(
            Principal(user_id=uuid4(), is_platform_admin=True),
            TenantContext(tenant_id=uuid4(), user_id=uuid4(), role=Role.OWNER),
            Capability.TENANT_READ,
        )
