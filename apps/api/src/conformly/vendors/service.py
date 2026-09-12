from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize
from conformly.authz.roles import Capability
from conformly.vendors.models import Vendor, VendorCriticality, VendorStatus


def list_vendors(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    request_id: str,
) -> list[Vendor]:
    authorize(principal, tenant_context, Capability.VENDOR_READ)
    stmt = (
        select(Vendor)
        .where(Vendor.tenant_id == tenant_context.tenant_id)
        .order_by(Vendor.name.asc())
    )
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
) -> Vendor:
    authorize(principal, tenant_context, Capability.VENDOR_MANAGE)
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
