from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize
from conformly.authz.roles import Capability
from conformly.entitlements.models import DEFAULT_TIER_A_MODULES, TenantEntitlement


def get_or_create_tenant_entitlement(database: Session, tenant_id: UUID) -> TenantEntitlement:
    stmt = select(TenantEntitlement).where(TenantEntitlement.tenant_id == tenant_id)
    entitlement = database.scalar(stmt)
    if entitlement is None:
        entitlement = TenantEntitlement(
            tenant_id=tenant_id,
            plan_code="tier_a",
            enabled_modules=list(DEFAULT_TIER_A_MODULES),
        )
        database.add(entitlement)
        database.flush()
    return entitlement


def is_module_enabled(database: Session, tenant_id: UUID, module_name: str) -> bool:
    entitlement = get_or_create_tenant_entitlement(database, tenant_id)
    return module_name in entitlement.enabled_modules


def get_tenant_entitlement(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    request_id: str,
) -> TenantEntitlement:
    authorize(principal, tenant_context, Capability.ENTITLEMENT_READ)
    entitlement = get_or_create_tenant_entitlement(database, tenant_context.tenant_id)
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="entitlement.read",
        resource_type="entitlement",
        resource_id=str(entitlement.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"plan_code": entitlement.plan_code},
    )
    return entitlement


def update_tenant_entitlement(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    enabled_modules: list[str],
    max_members: int,
    max_storage_bytes: int,
    request_id: str,
) -> TenantEntitlement:
    authorize(principal, tenant_context, Capability.ENTITLEMENT_MANAGE)
    entitlement = get_or_create_tenant_entitlement(database, tenant_context.tenant_id)
    entitlement.enabled_modules = [m.strip().lower() for m in enabled_modules]
    entitlement.max_members = max_members
    entitlement.max_storage_bytes = max_storage_bytes
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="entitlement.update",
        resource_type="entitlement",
        resource_id=str(entitlement.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "count": len(entitlement.enabled_modules),
            "max_members": max_members,
        },
    )
    return entitlement
