from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize, authorize_resource
from conformly.authz.roles import Capability
from conformly.organization.models import BusinessUnit, LegalEntity, Location


class OrganizationNotFoundError(Exception):
    """Raised when an entity, unit, or location is not found in the tenant."""


def list_legal_entities(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    request_id: str,
) -> list[LegalEntity]:
    authorize(principal, tenant_context, Capability.ORGANIZATION_READ)
    stmt = (
        select(LegalEntity)
        .where(LegalEntity.tenant_id == tenant_context.tenant_id)
    )
    if tenant_context.legal_entity_id is not None:
        stmt = stmt.where(LegalEntity.id == tenant_context.legal_entity_id)
    stmt = stmt.order_by(LegalEntity.created_at.asc())
    entities = list(database.scalars(stmt).all())
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="organization.legal_entity.list",
        resource_type="legal_entity",
        resource_id=None,
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"count": len(entities)},
    )
    return entities


def create_legal_entity(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    name: str,
    registration_number: str | None,
    country: str,
    is_primary: bool,
    request_id: str,
) -> LegalEntity:
    authorize(principal, tenant_context, Capability.ORGANIZATION_MANAGE)
    entity = LegalEntity(
        tenant_id=tenant_context.tenant_id,
        name=name.strip(),
        registration_number=registration_number.strip() if registration_number else None,
        country=country.upper()[:2],
        is_primary=is_primary,
    )
    database.add(entity)
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="organization.legal_entity.create",
        resource_type="legal_entity",
        resource_id=str(entity.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"name": entity.name, "country": entity.country},
    )
    return entity


def list_business_units(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    request_id: str,
    legal_entity_id: UUID | None = None,
) -> list[BusinessUnit]:
    authorize(principal, tenant_context, Capability.ORGANIZATION_READ)
    effective_legal_entity_id = tenant_context.legal_entity_id or legal_entity_id
    if (
        tenant_context.legal_entity_id is not None
        and legal_entity_id is not None
        and legal_entity_id != tenant_context.legal_entity_id
    ):
        return []
    stmt = select(BusinessUnit).where(BusinessUnit.tenant_id == tenant_context.tenant_id)
    if effective_legal_entity_id:
        stmt = stmt.where(BusinessUnit.legal_entity_id == effective_legal_entity_id)
    if tenant_context.business_unit_id:
        stmt = stmt.where(BusinessUnit.id == tenant_context.business_unit_id)
    stmt = stmt.order_by(BusinessUnit.created_at.asc())
    units = list(database.scalars(stmt).all())
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="organization.business_unit.list",
        resource_type="business_unit",
        resource_id=None,
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"count": len(units)},
    )
    return units


def create_business_unit(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    legal_entity_id: UUID,
    name: str,
    code: str | None,
    request_id: str,
) -> BusinessUnit:
    authorize_resource(
        principal,
        tenant_context,
        Capability.ORGANIZATION_MANAGE,
        legal_entity_id=legal_entity_id,
    )
    entity = database.scalar(
        select(LegalEntity).where(
            LegalEntity.id == legal_entity_id,
            LegalEntity.tenant_id == tenant_context.tenant_id,
        )
    )
    if entity is None:
        raise OrganizationNotFoundError("Legal entity not found in tenant")
    unit = BusinessUnit(
        tenant_id=tenant_context.tenant_id,
        legal_entity_id=legal_entity_id,
        name=name.strip(),
        code=code.strip().upper() if code else None,
    )
    database.add(unit)
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="organization.business_unit.create",
        resource_type="business_unit",
        resource_id=str(unit.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"name": unit.name, "legal_entity_id": str(legal_entity_id)},
    )
    return unit


def list_locations(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    request_id: str,
    legal_entity_id: UUID | None = None,
) -> list[Location]:
    authorize(principal, tenant_context, Capability.ORGANIZATION_READ)
    effective_legal_entity_id = tenant_context.legal_entity_id or legal_entity_id
    if (
        tenant_context.legal_entity_id is not None
        and legal_entity_id is not None
        and legal_entity_id != tenant_context.legal_entity_id
    ):
        return []
    stmt = select(Location).where(Location.tenant_id == tenant_context.tenant_id)
    if effective_legal_entity_id:
        stmt = stmt.where(Location.legal_entity_id == effective_legal_entity_id)
    stmt = stmt.order_by(Location.created_at.asc())
    locations = list(database.scalars(stmt).all())
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="organization.location.list",
        resource_type="location",
        resource_id=None,
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"count": len(locations)},
    )
    return locations


def create_location(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    legal_entity_id: UUID,
    name: str,
    country: str,
    city: str,
    address: str | None,
    request_id: str,
) -> Location:
    authorize_resource(
        principal,
        tenant_context,
        Capability.ORGANIZATION_MANAGE,
        legal_entity_id=legal_entity_id,
    )
    entity = database.scalar(
        select(LegalEntity).where(
            LegalEntity.id == legal_entity_id,
            LegalEntity.tenant_id == tenant_context.tenant_id,
        )
    )
    if entity is None:
        raise OrganizationNotFoundError("Legal entity not found in tenant")
    location = Location(
        tenant_id=tenant_context.tenant_id,
        legal_entity_id=legal_entity_id,
        name=name.strip(),
        country=country.upper()[:2],
        city=city.strip(),
        address=address.strip() if address else None,
    )
    database.add(location)
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="organization.location.create",
        resource_type="location",
        resource_id=str(location.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"name": location.name, "city": location.city},
    )
    return location
