from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize, authorize_resource
from conformly.authz.roles import Capability
from conformly.vendors.models import Vendor, VendorCriticality, VendorStatus


class VendorNotFoundError(Exception):
    """Raised when a vendor is not found in the tenant."""


def list_vendors(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    request_id: str,
    criticality: VendorCriticality | None = None,
    status: VendorStatus | None = None,
) -> list[Vendor]:
    authorize(principal, tenant_context, Capability.VENDOR_READ)
    stmt = (
        select(Vendor)
        .where(Vendor.tenant_id == tenant_context.tenant_id)
    )
    if tenant_context.legal_entity_id is not None:
        stmt = stmt.where(Vendor.legal_entity_id == tenant_context.legal_entity_id)
    if tenant_context.business_unit_id is not None:
        stmt = stmt.where(Vendor.business_unit_id == tenant_context.business_unit_id)
    if criticality is not None:
        stmt = stmt.where(Vendor.criticality == criticality)
    if status is not None:
        stmt = stmt.where(Vendor.status == status)
    stmt = stmt.order_by(Vendor.name.asc())
    vendors = list(database.scalars(stmt).all())
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="vendor.list",
        resource_type="vendor",
        resource_id=None,
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"count": len(vendors)},
    )
    return vendors


def get_vendor(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    vendor_id: UUID,
    request_id: str,
) -> Vendor:
    authorize(principal, tenant_context, Capability.VENDOR_READ)
    vendor = database.scalar(
        select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == tenant_context.tenant_id)
    )
    if vendor is None:
        raise VendorNotFoundError("Vendor not found in tenant")
    authorize_resource(
        principal,
        tenant_context,
        Capability.VENDOR_READ,
        legal_entity_id=vendor.legal_entity_id,
        business_unit_id=vendor.business_unit_id,
    )
    return vendor


def create_vendor(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    name: str,
    service_description: str,
    criticality: VendorCriticality,
    data_classification_accessed: str,
    country_residency: str,
    dpa_signed: bool,
    security_reviewed_at: datetime | None,
    next_review_due_at: datetime | None,
    request_id: str,
    owner_user_id: UUID | None = None,
    control_id: UUID | None = None,
    finding_id: UUID | None = None,
    legal_entity_id: UUID | None = None,
    business_unit_id: UUID | None = None,
) -> Vendor:
    effective_legal_entity_id = tenant_context.legal_entity_id or legal_entity_id
    effective_business_unit_id = tenant_context.business_unit_id or business_unit_id
    authorize(principal, tenant_context, Capability.VENDOR_MANAGE)
    authorize_resource(
        principal,
        tenant_context,
        Capability.VENDOR_MANAGE,
        legal_entity_id=effective_legal_entity_id,
        business_unit_id=effective_business_unit_id,
    )
    vendor = Vendor(
        tenant_id=tenant_context.tenant_id,
        name=name.strip(),
        service_description=service_description.strip(),
        criticality=criticality,
        data_classification_accessed=data_classification_accessed.strip(),
        country_residency=country_residency.strip().upper(),
        dpa_signed=dpa_signed,
        security_reviewed_at=security_reviewed_at,
        next_review_due_at=next_review_due_at,
        owner_user_id=owner_user_id,
        control_id=control_id,
        finding_id=finding_id,
        legal_entity_id=effective_legal_entity_id,
        business_unit_id=effective_business_unit_id,
        status=VendorStatus.ACTIVE,
    )
    database.add(vendor)
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="vendor.create",
        resource_type="vendor",
        resource_id=str(vendor.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"name": vendor.name, "criticality": vendor.criticality.value},
    )
    return vendor


def update_vendor(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    vendor_id: UUID,
    name: str,
    service_description: str,
    criticality: VendorCriticality,
    data_classification_accessed: str,
    country_residency: str,
    dpa_signed: bool,
    status: VendorStatus,
    owner_user_id: UUID | None,
    control_id: UUID | None,
    finding_id: UUID | None,
    request_id: str,
    legal_entity_id: UUID | None = None,
    business_unit_id: UUID | None = None,
) -> Vendor:
    authorize(principal, tenant_context, Capability.VENDOR_MANAGE)
    vendor = get_vendor(database, principal, tenant_context, vendor_id, request_id)
    authorize_resource(
        principal,
        tenant_context,
        Capability.VENDOR_MANAGE,
        legal_entity_id=vendor.legal_entity_id,
        business_unit_id=vendor.business_unit_id,
    )

    vendor.name = name.strip()
    vendor.service_description = service_description.strip()
    vendor.criticality = criticality
    vendor.data_classification_accessed = data_classification_accessed.strip()
    vendor.country_residency = country_residency.strip().upper()
    vendor.dpa_signed = dpa_signed
    vendor.status = status
    vendor.owner_user_id = owner_user_id
    vendor.control_id = control_id
    vendor.finding_id = finding_id
    if legal_entity_id is not None:
        vendor.legal_entity_id = legal_entity_id
    if business_unit_id is not None:
        vendor.business_unit_id = business_unit_id

    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="vendor.update",
        resource_type="vendor",
        resource_id=str(vendor.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"name": vendor.name, "status": vendor.status.value},
    )
    return vendor


def complete_vendor_review(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    vendor_id: UUID,
    next_review_due_at: datetime | None,
    request_id: str,
) -> Vendor:
    authorize(principal, tenant_context, Capability.VENDOR_MANAGE)
    vendor = get_vendor(database, principal, tenant_context, vendor_id, request_id)
    authorize_resource(
        principal,
        tenant_context,
        Capability.VENDOR_MANAGE,
        legal_entity_id=vendor.legal_entity_id,
        business_unit_id=vendor.business_unit_id,
    )
    now = datetime.now(UTC)
    vendor.security_reviewed_at = now
    vendor.next_review_due_at = next_review_due_at
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="vendor.review.complete",
        resource_type="vendor",
        resource_id=str(vendor.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"security_reviewed_at": now.isoformat()},
    )
    return vendor


def delete_vendor(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    vendor_id: UUID,
    request_id: str,
) -> None:
    authorize(principal, tenant_context, Capability.VENDOR_MANAGE)
    vendor = get_vendor(database, principal, tenant_context, vendor_id, request_id)
    authorize_resource(
        principal,
        tenant_context,
        Capability.VENDOR_MANAGE,
        legal_entity_id=vendor.legal_entity_id,
        business_unit_id=vendor.business_unit_id,
    )
    database.delete(vendor)
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="vendor.delete",
        resource_type="vendor",
        resource_id=str(vendor_id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"name": vendor.name},
    )

