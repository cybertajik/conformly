from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize
from conformly.authz.roles import Capability
from conformly.entitlements.models import DEFAULT_TIER_A_MODULES, TenantEntitlement


class EntitlementLimitExceededError(Exception):
    """Raised when tenant exceeds entitled capacity (e.g. member count)."""


class StorageQuotaExceededError(Exception):
    """Raised when tenant exceeds storage quota in bytes."""


class EntitlementInactiveError(Exception):
    """Raised when tenant entitlement is expired or not yet active."""


class FrameworkPackNotEntitledError(Exception):
    """Raised when a framework is not covered by tenant entitlement packs."""


def get_or_create_tenant_entitlement(database: Session, tenant_id: UUID) -> TenantEntitlement:
    stmt = select(TenantEntitlement).where(TenantEntitlement.tenant_id == tenant_id)
    entitlement = database.scalar(stmt)
    if entitlement is None:
        entitlement = TenantEntitlement(
            tenant_id=tenant_id,
            plan_code="tier_a",
            enabled_modules=list(DEFAULT_TIER_A_MODULES),
            allowed_framework_slugs=list(["*"]),
        )
        database.add(entitlement)
        database.flush()
    return entitlement


def is_module_enabled(database: Session, tenant_id: UUID, module_name: str) -> bool:
    entitlement = get_or_create_tenant_entitlement(database, tenant_id)
    now = datetime.now(UTC)
    if entitlement.effective_from:
        eff_from = (
            entitlement.effective_from
            if entitlement.effective_from.tzinfo
            else entitlement.effective_from.replace(tzinfo=UTC)
        )
        if now < eff_from:
            return False
    if entitlement.effective_until:
        eff_until = (
            entitlement.effective_until
            if entitlement.effective_until.tzinfo
            else entitlement.effective_until.replace(tzinfo=UTC)
        )
        if now > eff_until:
            return False
    return module_name in entitlement.enabled_modules


def is_framework_allowed(database: Session, tenant_id: UUID, framework_slug: str) -> bool:
    entitlement = get_or_create_tenant_entitlement(database, tenant_id)
    now = datetime.now(UTC)
    if entitlement.effective_from:
        eff_from = (
            entitlement.effective_from
            if entitlement.effective_from.tzinfo
            else entitlement.effective_from.replace(tzinfo=UTC)
        )
        if now < eff_from:
            return False
    if entitlement.effective_until:
        eff_until = (
            entitlement.effective_until
            if entitlement.effective_until.tzinfo
            else entitlement.effective_until.replace(tzinfo=UTC)
        )
        if now > eff_until:
            return False
    allowed = entitlement.allowed_framework_slugs or ["*"]
    if "*" in allowed:
        return True
    return framework_slug.strip().lower() in [s.strip().lower() for s in allowed]


def check_member_limit(database: Session, tenant_id: UUID) -> None:
    from conformly.identity.models import Membership, MembershipStatus

    stmt = select(func.count(Membership.id)).where(
        Membership.tenant_id == tenant_id,
        Membership.status == MembershipStatus.ACTIVE,
    )
    current_members = database.scalar(stmt) or 0
    entitlement = get_or_create_tenant_entitlement(database, tenant_id)
    if current_members >= entitlement.max_members:
        raise EntitlementLimitExceededError(
            f"Tenant member limit of {entitlement.max_members} reached"
        )


def check_storage_limit(database: Session, tenant_id: UUID, additional_bytes: int = 0) -> None:
    from conformly.storage.models import StoredFile, StoredFileStatus

    stmt = select(func.coalesce(func.sum(StoredFile.ciphertext_size_bytes), 0)).where(
        StoredFile.tenant_id == tenant_id,
        StoredFile.status == StoredFileStatus.ACTIVE,
    )
    current_bytes = database.scalar(stmt) or 0
    entitlement = get_or_create_tenant_entitlement(database, tenant_id)
    if current_bytes + additional_bytes > entitlement.max_storage_bytes:
        raise StorageQuotaExceededError(
            f"Tenant storage quota of {entitlement.max_storage_bytes} bytes exceeded"
        )


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
    allowed_framework_slugs: list[str] | None = None,
    effective_from: datetime | None = None,
    effective_until: datetime | None = None,
) -> TenantEntitlement:
    authorize(principal, tenant_context, Capability.ENTITLEMENT_MANAGE)
    entitlement = get_or_create_tenant_entitlement(database, tenant_context.tenant_id)
    entitlement.enabled_modules = [m.strip().lower() for m in enabled_modules]
    entitlement.max_members = max_members
    entitlement.max_storage_bytes = max_storage_bytes
    if allowed_framework_slugs is not None:
        entitlement.allowed_framework_slugs = [s.strip().lower() for s in allowed_framework_slugs]
    if effective_from is not None:
        entitlement.effective_from = effective_from
    if effective_until is not None:
        entitlement.effective_until = effective_until
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
