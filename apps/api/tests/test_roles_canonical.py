from uuid import uuid4
import pytest
from conformly.authz.policy import AuthorizationDeniedError, Principal, TenantContext, authorize
from conformly.authz.roles import Capability, Role


def test_canonical_roles_exist():
    expected_roles = {
        "owner",
        "administrator",
        "compliance_manager",
        "control_owner",
        "reviewer",
        "employee",
    }
    actual_roles = {r.value for r in Role}
    assert expected_roles.issubset(actual_roles)


def test_tenant_administrator_denied_compliance_content():
    """Verify that Tenant Administrator cannot access or manage compliance content."""
    tenant_id = uuid4()
    user_id = uuid4()
    principal = Principal(user_id=user_id, is_platform_admin=False)
    tenant_context = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.ADMINISTRATOR)

    # Allowed administrative actions
    authorize(principal, tenant_context, Capability.TENANT_READ)
    authorize(principal, tenant_context, Capability.MEMBERSHIP_READ)
    authorize(principal, tenant_context, Capability.MEMBERSHIP_MANAGE)
    authorize(principal, tenant_context, Capability.AUDIT_READ)
    authorize(principal, tenant_context, Capability.ORGANIZATION_MANAGE)

    # Denied compliance actions per Card 8 / Card 11
    compliance_capabilities = [
        Capability.EVIDENCE_READ,
        Capability.EVIDENCE_MANAGE,
        Capability.POLICY_READ,
        Capability.POLICY_MANAGE,
        Capability.TASK_READ,
        Capability.TASK_MANAGE,
        Capability.FINDING_READ,
        Capability.FINDING_MANAGE,
        Capability.CONTROL_STATUS_MANAGE,
        Capability.PREAUDIT_MANAGE,
        Capability.RISK_MANAGE,
        Capability.ASSET_MANAGE,
        Capability.VENDOR_MANAGE,
    ]
    for cap in compliance_capabilities:
        with pytest.raises(AuthorizationDeniedError):
            authorize(principal, tenant_context, cap)


def test_compliance_manager_authorized_for_compliance_operations():
    """Verify that Compliance Manager can manage compliance operations."""
    tenant_id = uuid4()
    user_id = uuid4()
    principal = Principal(user_id=user_id, is_platform_admin=False)
    tenant_context = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.COMPLIANCE_MANAGER)

    authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)
    authorize(principal, tenant_context, Capability.EVIDENCE_MANAGE)
    authorize(principal, tenant_context, Capability.POLICY_MANAGE)
    authorize(principal, tenant_context, Capability.TASK_MANAGE)
    authorize(principal, tenant_context, Capability.FINDING_MANAGE)
    authorize(principal, tenant_context, Capability.CONTROL_STATUS_MANAGE)
    authorize(principal, tenant_context, Capability.PREAUDIT_MANAGE)
    authorize(principal, tenant_context, Capability.RISK_MANAGE)
    authorize(principal, tenant_context, Capability.ASSET_MANAGE)
    authorize(principal, tenant_context, Capability.VENDOR_MANAGE)


def test_control_owner_and_reviewer_and_employee():
    tenant_id = uuid4()
    user_id = uuid4()
    principal = Principal(user_id=user_id, is_platform_admin=False)

    co_context = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.CONTROL_OWNER)
    authorize(principal, co_context, Capability.FILE_WRITE)
    authorize(principal, co_context, Capability.EVIDENCE_MANAGE)
    authorize(principal, co_context, Capability.TASK_MANAGE)

    rev_context = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.REVIEWER)
    authorize(principal, rev_context, Capability.EVIDENCE_READ)
    authorize(principal, rev_context, Capability.PREAUDIT_READ)
    with pytest.raises(AuthorizationDeniedError):
        authorize(principal, rev_context, Capability.PREAUDIT_MANAGE)

    emp_context = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.EMPLOYEE)
    authorize(principal, emp_context, Capability.POLICY_READ)
    with pytest.raises(AuthorizationDeniedError):
        authorize(principal, emp_context, Capability.EVIDENCE_READ)
