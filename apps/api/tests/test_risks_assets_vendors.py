from uuid import uuid4
import pytest
from sqlalchemy.orm import Session

from conformly.assets import service as asset_service
from conformly.assets.models import AssetClassification, AssetType
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.risks import service as risk_service
from conformly.risks.models import RiskCategory, RiskStatus, RiskTreatmentStrategy
from conformly.vendors import service as vendor_service
from conformly.vendors.models import VendorCriticality


def test_risks_assets_vendors_lifecycle_and_isolation(session: Session):
    tenant_a = uuid4()
    tenant_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()

    principal_a = Principal(user_id=user_a)
    context_a = TenantContext(tenant_id=tenant_a, user_id=user_a, role=Role.COMPLIANCE_MANAGER)

    principal_b = Principal(user_id=user_b)
    context_b = TenantContext(tenant_id=tenant_b, user_id=user_b, role=Role.COMPLIANCE_MANAGER)

    # 1. Risks
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
    )
    assert risk_a.inherent_score == 12
    assert risk_a.status == RiskStatus.IDENTIFIED

    treatment_a = risk_service.add_risk_treatment(
        session,
        principal_a,
        context_a,
        risk_id=risk_a.id,
        strategy=RiskTreatmentStrategy.MITIGATE,
        treatment_plan="Enforce AES-256-GCM envelope encryption for all backups.",
        target_date=None,
        request_id="req-r2",
    )
    assert risk_a.status == RiskStatus.TREATING
    assert treatment_a.strategy == RiskTreatmentStrategy.MITIGATE

    # Verify risk listing and tenant isolation
    risks_a = risk_service.list_risks(session, principal_a, context_a, request_id="req-r3")
    assert len(risks_a) == 1
    assert risks_a[0].id == risk_a.id

    risks_b = risk_service.list_risks(session, principal_b, context_b, request_id="req-r4")
    assert len(risks_b) == 0

    # 2. Assets
    asset_a = asset_service.create_asset(
        session,
        principal_a,
        context_a,
        name="Production PostgreSQL Primary",
        asset_type=AssetType.CLOUD_SERVICE,
        classification=AssetClassification.RESTRICTED,
        description="Primary EU database cluster",
        owner_user_id=user_a,
        request_id="req-a1",
    )
    assert asset_a.name == "Production PostgreSQL Primary"

    assets_a = asset_service.list_assets(session, principal_a, context_a, request_id="req-a2")
    assert len(assets_a) == 1
    assert assets_a[0].id == asset_a.id

    assets_b = asset_service.list_assets(session, principal_b, context_b, request_id="req-a3")
    assert len(assets_b) == 0

    # 3. Vendors
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
    )
    assert vendor_a.name == "Hetzner Online GmbH"
    assert vendor_a.dpa_signed is True

    vendors_a = vendor_service.list_vendors(session, principal_a, context_a, request_id="req-v2")
    assert len(vendors_a) == 1
    assert vendors_a[0].id == vendor_a.id

    vendors_b = vendor_service.list_vendors(session, principal_b, context_b, request_id="req-v3")
    assert len(vendors_b) == 0
