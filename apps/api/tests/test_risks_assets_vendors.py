from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from conformly.assets import service as asset_service
from conformly.assets.models import AssetClassification, AssetStatus, AssetType
from conformly.authz.policy import AuthorizationDeniedError, Principal, TenantContext
from conformly.authz.roles import Role
from conformly.organization import service as org_service
from conformly.risks import service as risk_service
from conformly.risks.models import RiskCategory, RiskStatus, RiskTreatmentStrategy
from conformly.vendors import service as vendor_service
from conformly.vendors.models import VendorCriticality, VendorStatus


def test_risks_assets_vendors_lifecycle_and_isolation(session: Session) -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()

    principal_a = Principal(user_id=user_a)
    context_a = TenantContext(tenant_id=tenant_a, user_id=user_a, role=Role.OWNER)

    principal_b = Principal(user_id=user_b)
    context_b = TenantContext(tenant_id=tenant_b, user_id=user_b, role=Role.OWNER)

    # 1. Organization Structure
    legal_entity = org_service.create_legal_entity(
        session,
        principal_a,
        context_a,
        name="Conformly Technologies GmbH",
        registration_number="HRB 123456",
        country="DE",
        is_primary=True,
        request_id="req-le-1",
    )
    assert legal_entity.name == "Conformly Technologies GmbH"

    bu = org_service.create_business_unit(
        session,
        principal_a,
        context_a,
        legal_entity_id=legal_entity.id,
        name="Platform Engineering",
        code="ENG",
        request_id="req-bu-1",
    )
    assert bu.name == "Platform Engineering"

    location = org_service.create_location(
        session,
        principal_a,
        context_a,
        legal_entity_id=legal_entity.id,
        name="Frankfurt Datacenter",
        country="DE",
        city="Frankfurt",
        address="Mainzer Landstr. 100",
        request_id="req-loc-1",
    )
    assert location.city == "Frankfurt"

    # 2. Risks & Treatments with Scope
    finding_id = uuid4()
    risk_a = risk_service.create_risk(
        session,
        principal_a,
        context_a,
        title="Unencrypted backup storage risk",
        description="Backup storage might lack application-layer encryption.",
        category=RiskCategory.SECURITY,
        likelihood=3,
        impact=4,
        owner_user_id=user_a,
        control_id=None,
        request_id="req-r1",
        finding_id=finding_id,
        legal_entity_id=legal_entity.id,
        business_unit_id=bu.id,
    )
    assert risk_a.inherent_score == 12
    assert risk_a.status == RiskStatus.IDENTIFIED
    assert risk_a.finding_id == finding_id
    assert risk_a.legal_entity_id == legal_entity.id

    treatment_a = risk_service.add_risk_treatment(
        session,
        principal_a,
        context_a,
        risk_id=risk_a.id,
        strategy=RiskTreatmentStrategy.MITIGATE,
        treatment_plan="Enforce AES-256-GCM envelope encryption for all backups.",
        target_date=None,
        request_id="req-r2",
        owner_user_id=user_a,
    )
    assert risk_a.status == RiskStatus.TREATING
    assert treatment_a.strategy == RiskTreatmentStrategy.MITIGATE
    assert treatment_a.owner_user_id == user_a

    # Update risk treatment
    updated_treatment = risk_service.update_risk_treatment(
        session,
        principal_a,
        context_a,
        treatment_id=treatment_a.id,
        strategy=RiskTreatmentStrategy.MITIGATE,
        treatment_plan="Implemented AES-256-GCM envelope encryption via KMS.",
        target_date=datetime.now(UTC) + timedelta(days=30),
        status="completed",
        owner_user_id=user_a,
        request_id="req-r-treat-up",
    )
    assert updated_treatment.status == "completed"

    # Update risk & review
    updated_risk = risk_service.update_risk(
        session,
        principal_a,
        context_a,
        risk_id=risk_a.id,
        title="Unencrypted backup storage risk (Mitigated)",
        description="Backup encryption active.",
        category=RiskCategory.SECURITY,
        likelihood=1,
        impact=4,
        residual_score=4,
        status=RiskStatus.MONITORED,
        owner_user_id=user_a,
        control_id=None,
        finding_id=finding_id,
        request_id="req-r-up",
        legal_entity_id=legal_entity.id,
        business_unit_id=bu.id,
    )
    assert updated_risk.residual_score == 4
    assert updated_risk.status == RiskStatus.MONITORED

    due_review = datetime.now(UTC) + timedelta(days=90)
    reviewed_risk = risk_service.complete_risk_review(
        session,
        principal_a,
        context_a,
        risk_id=risk_a.id,
        next_review_due_at=due_review,
        request_id="req-r-rev",
    )
    assert reviewed_risk.last_reviewed_at is not None
    assert reviewed_risk.next_review_due_at == due_review

    # Verify risk listing and tenant isolation
    risks_a = risk_service.list_risks(session, principal_a, context_a, request_id="req-r3")
    assert len(risks_a) == 1
    assert risks_a[0].id == risk_a.id

    risks_b = risk_service.list_risks(session, principal_b, context_b, request_id="req-r4")
    assert len(risks_b) == 0

    # 3. Assets with Restricted Encryption
    asset_a = asset_service.create_asset(
        session,
        principal_a,
        context_a,
        name="Production PostgreSQL Primary",
        asset_type=AssetType.CLOUD_SERVICE,
        classification=AssetClassification.RESTRICTED,
        description="Primary EU database cluster with secret credentials",
        owner_user_id=user_a,
        request_id="req-a1",
        legal_entity_id=legal_entity.id,
        business_unit_id=bu.id,
    )
    assert asset_a.name == "Production PostgreSQL Primary"
    # Mandatory encryption principle verification:
    # Restricted description MUST NOT be stored in plaintext in the DB column
    assert asset_a.description is None
    assert asset_a.encrypted_description is not None
    assert asset_a.encrypted_description.get("algorithm") == "AES-256-GCM"
    assert "ciphertext" in asset_a.encrypted_description

    # Transparent decryption on read
    decrypted_desc = asset_service.resolve_asset_description(asset_a)
    assert decrypted_desc == "Primary EU database cluster with secret credentials"

    # Asset Review
    reviewed_asset = asset_service.complete_asset_review(
        session,
        principal_a,
        context_a,
        asset_id=asset_a.id,
        next_review_due_at=due_review,
        request_id="req-a-rev",
    )
    assert reviewed_asset.last_reviewed_at is not None

    # Asset Update
    updated_asset = asset_service.update_asset(
        session,
        principal_a,
        context_a,
        asset_id=asset_a.id,
        name="Production PostgreSQL Primary (HA)",
        asset_type=AssetType.CLOUD_SERVICE,
        classification=AssetClassification.INTERNAL,
        description="Non-restricted description now",
        owner_user_id=user_a,
        status=AssetStatus.ACTIVE,
        control_id=None,
        finding_id=None,
        request_id="req-a-up",
    )
    assert updated_asset.classification == AssetClassification.INTERNAL
    assert updated_asset.description == "Non-restricted description now"
    assert updated_asset.encrypted_description is None

    # 4. Vendors
    vendor_a = vendor_service.create_vendor(
        session,
        principal_a,
        context_a,
        name="Hetzner Online GmbH",
        service_description="Dedicated root servers and hosting infrastructure",
        criticality=VendorCriticality.HIGH,
        data_classification_accessed="Confidential",
        country_residency="DE",
        dpa_signed=True,
        security_reviewed_at=None,
        next_review_due_at=None,
        request_id="req-v1",
        legal_entity_id=legal_entity.id,
        business_unit_id=bu.id,
    )
    assert vendor_a.name == "Hetzner Online GmbH"
    assert vendor_a.dpa_signed is True

    # Vendor Review
    reviewed_vendor = vendor_service.complete_vendor_review(
        session,
        principal_a,
        context_a,
        vendor_id=vendor_a.id,
        next_review_due_at=due_review,
        request_id="req-v-rev",
    )
    assert reviewed_vendor.security_reviewed_at is not None

    # Vendor Update
    updated_vendor = vendor_service.update_vendor(
        session,
        principal_a,
        context_a,
        vendor_id=vendor_a.id,
        name="Hetzner Online GmbH & Co. KG",
        service_description="Root servers, VPCs, and storage boxes",
        criticality=VendorCriticality.CRITICAL,
        data_classification_accessed="Confidential",
        country_residency="DE",
        dpa_signed=True,
        status=VendorStatus.ACTIVE,
        owner_user_id=user_a,
        control_id=None,
        finding_id=None,
        request_id="req-v-up",
    )
    assert updated_vendor.criticality == VendorCriticality.CRITICAL

    # Verify listings
    vendors_a = vendor_service.list_vendors(session, principal_a, context_a, request_id="req-v2")
    assert len(vendors_a) == 1
    assert vendors_a[0].id == vendor_a.id

    vendors_b = vendor_service.list_vendors(session, principal_b, context_b, request_id="req-v3")
    assert len(vendors_b) == 0

    # 5. Resource-scoping enforcement
    scoped_context = TenantContext(
        tenant_id=tenant_a,
        user_id=user_a,
        role=Role.COMPLIANCE_MANAGER,
        legal_entity_id=uuid4(),  # Different legal entity
    )
    # Trying to read risk belonging to legal_entity from scoped_context should raise AuthorizationDeniedError
    with pytest.raises(AuthorizationDeniedError):
        risk_service.get_risk(session, principal_a, scoped_context, risk_a.id, request_id="req-scope-check")

