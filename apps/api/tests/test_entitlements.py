from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.entitlements import service
from conformly.entitlements.dependencies import require_module


def test_entitlements_default_and_module_check(session: Session):
    tenant_id = uuid4()
    user_id = uuid4()
    principal = Principal(user_id=user_id)
    context = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.ADMINISTRATOR)

    # By default, Tier A modules are enabled
    entitlement = service.get_tenant_entitlement(session, principal, context, request_id="req-e1")
    assert entitlement.plan_code == "tier_a"
    assert service.is_module_enabled(session, tenant_id, "frameworks") is True
    assert service.is_module_enabled(session, tenant_id, "risks") is True
    assert service.is_module_enabled(session, tenant_id, "assets") is True
    assert service.is_module_enabled(session, tenant_id, "vendors") is True
    # Whistleblower is a separate later add-on, not enabled by default in Tier A Core
    assert service.is_module_enabled(session, tenant_id, "whistleblower") is False

    # require_module dependency test
    guard_frameworks = require_module("frameworks")
    guard_frameworks(tenant_context=context, database=session)  # should not raise

    guard_whistleblower = require_module("whistleblower")
    with pytest.raises(HTTPException) as exc_info:
        guard_whistleblower(tenant_context=context, database=session)
    assert exc_info.value.status_code == 403
    assert "not enabled" in exc_info.value.detail

    # Updating entitlement to enable whistleblower add-on
    service.update_tenant_entitlement(
        session,
        principal,
        context,
        enabled_modules=["frameworks", "whistleblower"],
        max_members=50,
        max_storage_bytes=5 * 1024 * 1024 * 1024,
        request_id="req-e2",
    )
    assert service.is_module_enabled(session, tenant_id, "whistleblower") is True
    guard_whistleblower(tenant_context=context, database=session)  # now succeeds
