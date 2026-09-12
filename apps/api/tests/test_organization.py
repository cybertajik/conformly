from uuid import uuid4
import pytest
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal, TenantContext, AuthorizationDeniedError
from conformly.authz.roles import Role
from conformly.organization import service
from conformly.organization.service import OrganizationNotFoundError


def test_organization_crud_and_tenant_isolation(session: Session):
    tenant_a = uuid4()
    tenant_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()

    principal_a = Principal(user_id=user_a)
    context_a = TenantContext(tenant_id=tenant_a, user_id=user_a, role=Role.ADMINISTRATOR)

    principal_b = Principal(user_id=user_b)
    context_b = TenantContext(tenant_id=tenant_b, user_id=user_b, role=Role.ADMINISTRATOR)

    # Tenant A creates primary legal entity
    entity_a = service.create_legal_entity(
        session,
        principal_a,
        context_a,
        name="Acme Germany GmbH",
        registration_number="HRB 12345",
        country="DE",
        is_primary=True,
        request_id="req-1",
    )
    assert entity_a.name == "Acme Germany GmbH"
    assert entity_a.tenant_id == tenant_a

    # Tenant A creates business unit
    bu_a = service.create_business_unit(
        session,
        principal_a,
        context_a,
        legal_entity_id=entity_a.id,
        name="Security & IT Operations",
        code="SEC-OPS",
        request_id="req-2",
    )
    assert bu_a.name == "Security & IT Operations"
    assert bu_a.legal_entity_id == entity_a.id

    # Tenant A creates location
    loc_a = service.create_location(
        session,
        principal_a,
        context_a,
        legal_entity_id=entity_a.id,
        name="Frankfurt Data Center 1",
        country="DE",
        city="Frankfurt",
        address="Mainzer Landstr. 100",
        request_id="req-3",
    )
    assert loc_a.city == "Frankfurt"

    # Tenant A lists entities
    entities_a = service.list_legal_entities(session, principal_a, context_a, request_id="req-4")
    assert len(entities_a) == 1
    assert entities_a[0].id == entity_a.id

    # Tenant B should see 0 entities
    entities_b = service.list_legal_entities(session, principal_b, context_b, request_id="req-5")
    assert len(entities_b) == 0

    # Tenant B cannot create business unit attached to Tenant A's legal entity
    with pytest.raises(OrganizationNotFoundError):
        service.create_business_unit(
            session,
            principal_b,
            context_b,
            legal_entity_id=entity_a.id,
            name="Rogue BU",
            code="ROGUE",
            request_id="req-6",
        )
