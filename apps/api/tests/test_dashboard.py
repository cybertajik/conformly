from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from conformly.assets import service as asset_service
from conformly.assets.models import AssetClassification, AssetType
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.compliance.models import (
    ComplianceTask,
    ControlImplementationStatus,
    ControlStatusRecord,
    EvidenceItem,
    EvidenceStatus,
    Policy,
    PolicyStatus,
    TaskPriority,
    TaskStatus,
)
from conformly.dashboard import service as dashboard_service
from conformly.organization import service as org_service
from conformly.risks import service as risk_service
from conformly.risks.models import RiskCategory
from conformly.vendors import service as vendor_service
from conformly.vendors.models import VendorCriticality


def test_dashboard_summary_compliance_view(session: Session):
    tenant_id = uuid4()
    user_id = uuid4()
    principal = Principal(user_id=user_id)
    context = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.COMPLIANCE_MANAGER)
    now = datetime.now(UTC)

    # 1. Add Evidence Item expiring in 15 days
    evidence = EvidenceItem(
        tenant_id=tenant_id,
        title="Annual Penetration Test Report",
        description="Independent third-party pentest summary",
        classification="Confidential",
        status=EvidenceStatus.VALID,
        owner_user_id=user_id,
        valid_from=now - timedelta(days=350),
        valid_until=now + timedelta(days=15),
    )
    session.add(evidence)

    # 2. Add Policy due for review in 10 days
    policy = Policy(
        tenant_id=tenant_id,
        title="Access Control and Password Policy",
        description="Enforces MFA and passphrase complexity",
        version_string="2.0",
        status=PolicyStatus.APPROVED,
        owner_user_id=user_id,
        review_cycle_days=365,
        next_review_due=now + timedelta(days=10),
    )
    session.add(policy)

    # 3. Add open task
    task = ComplianceTask(
        tenant_id=tenant_id,
        title="Review firewall access rules",
        description="Verify ingress/egress rules for production VPC",
        due_date=now + timedelta(days=5),
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
        assignee_user_id=user_id,
    )
    session.add(task)

    # 4. Add risk
    risk = risk_service.create_risk(
        session,
        principal,
        context,
        title="DDoS attack on public edge",
        description="Volumetric attack on edge endpoints",
        category=RiskCategory.SECURITY,
        likelihood=4,
        impact=4,
        owner_user_id=user_id,
        control_id=None,
        request_id="req-dash-risk",
    )

    # 5. Add vendor
    vendor = vendor_service.create_vendor(
        session,
        principal,
        context,
        name="Cloudflare",
        service_description="Edge WAF and DDoS mitigation",
        criticality=VendorCriticality.CRITICAL,
        data_classification_accessed="Confidential",
        country_residency="US",
        dpa_signed=True,
        security_reviewed_at=None,
        next_review_due_at=None,
        request_id="req-dash-vendor",
    )

    session.commit()

    # Call Dashboard Service
    summary = dashboard_service.get_dashboard_summary(session, principal, context, request_id="req-dash-1")

    assert summary.is_administrator_view is False
    assert summary.admin_metrics is None

    # Check expiring evidence
    assert len(summary.expiring_evidence) >= 1
    exp_ev = next((e for e in summary.expiring_evidence if e.id == evidence.id), None)
    assert exp_ev is not None
    assert exp_ev.title == "Annual Penetration Test Report"
    assert exp_ev.days_remaining <= 16

    # Check review due policy
    assert len(summary.review_due_policies) >= 1
    rev_pol = next((p for p in summary.review_due_policies if p.id == policy.id), None)
    assert rev_pol is not None
    assert rev_pol.title == "Access Control and Password Policy"

    # Check open tasks
    assert len(summary.open_tasks) >= 1
    open_t = next((t for t in summary.open_tasks if t.id == task.id), None)
    assert open_t is not None
    assert open_t.priority == "high"

    # Check top risks
    assert len(summary.top_risks) >= 1
    r_item = next((r for r in summary.top_risks if r.id == risk.id), None)
    assert r_item is not None
    assert r_item.inherent_score == 16

    # Check vendor health
    assert summary.vendor_health.total_vendors >= 1
    assert summary.vendor_health.signed_dpa_count >= 1
    assert summary.vendor_health.critical_vendors >= 1


def test_dashboard_summary_administrator_view(session: Session):
    tenant_id = uuid4()
    user_id = uuid4()
    principal = Principal(user_id=user_id)
    admin_context = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.ADMINISTRATOR)

    # Create legal entity via organization service
    legal_entity = org_service.create_legal_entity(
        session,
        principal,
        admin_context,
        name="Conformly Admin Holding SE",
        registration_number="HRB 99999",
        country="DE",
        is_primary=True,
        request_id="req-dash-admin-le",
    )

    summary = dashboard_service.get_dashboard_summary(session, principal, admin_context, request_id="req-dash-admin-1")

    assert summary.is_administrator_view is True
    assert summary.admin_metrics is not None
    assert summary.admin_metrics.legal_entities >= 1

    # Verify compliance isolation for Tenant Administrator
    assert len(summary.expiring_evidence) == 0
    assert len(summary.review_due_policies) == 0
    assert len(summary.open_tasks) == 0
    assert len(summary.top_risks) == 0
    assert summary.vendor_health.total_vendors == 0
