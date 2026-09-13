from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditEvent, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.compliance.models import (
    ComplianceTask,
    ControlImplementationStatus,
    ControlStatusRecord,
    EvidenceItem,
    Policy,
    TaskStatus,
)
from conformly.entitlements.models import TenantEntitlement
from conformly.frameworks.models import AdoptionStatus, CanonicalControl, TenantFrameworkAdoption
from conformly.identity.models import Membership, MembershipStatus
from conformly.organization.models import BusinessUnit, LegalEntity, Location
from conformly.risks.models import Risk
from conformly.tenancy.rls import set_rls_context
from conformly.vendors.models import Vendor, VendorCriticality


class DashboardControlsSummary(BaseModel):
    total: int
    implemented: int
    in_progress: int
    not_started: int


class DashboardFrameworkProgress(BaseModel):
    framework_id: UUID
    framework_name: str
    version_name: str | None = None
    total_controls: int
    implemented_controls: int
    progress_percentage: int


class DashboardExpiringEvidence(BaseModel):
    id: UUID
    title: str
    expires_at: datetime
    days_remaining: int
    classification: str


class DashboardReviewDuePolicy(BaseModel):
    id: UUID
    title: str
    review_due_at: datetime
    days_remaining: int


class DashboardTaskItem(BaseModel):
    id: UUID
    title: str
    priority: str
    status: str
    due_date: datetime | None = None


class DashboardRiskItem(BaseModel):
    id: UUID
    title: str
    residual_score: int | None = None
    inherent_score: int
    status: str


class DashboardVendorHealth(BaseModel):
    total_vendors: int
    signed_dpa_count: int
    missing_dpa_count: int
    critical_vendors: int


class DashboardActivityItem(BaseModel):
    id: UUID
    action: str
    resource_type: str
    actor_type: str
    occurred_at: datetime


class DashboardAdminMetrics(BaseModel):
    total_members: int
    legal_entities: int
    business_units: int
    locations: int
    storage_bytes_used: int
    max_storage_bytes: int
    plan_code: str
    enabled_modules: list[str]


class DashboardSummary(BaseModel):
    readiness_score: int
    controls_summary: DashboardControlsSummary
    frameworks_adopted: list[DashboardFrameworkProgress]
    expiring_evidence: list[DashboardExpiringEvidence]
    review_due_policies: list[DashboardReviewDuePolicy]
    open_tasks: list[DashboardTaskItem]
    top_risks: list[DashboardRiskItem]
    vendor_health: DashboardVendorHealth
    recent_activity: list[DashboardActivityItem]
    is_administrator_view: bool
    admin_metrics: DashboardAdminMetrics | None = None


def get_dashboard_summary(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    request_id: str,
) -> DashboardSummary:
    """Aggregate executive compliance readiness metrics or administrative overview with server-side RLS."""
    set_rls_context(
        database,
        user_id=principal.user_id,
        tenant_id=tenant_context.tenant_id,
        tenant_verified=True,
    )
    now = datetime.now(UTC)
    role = tenant_context.role

    # Tenant Administrator isolation: If administrator, return administrative metrics only
    is_admin = role == Role.ADMINISTRATOR
    if is_admin:
        # Gather Admin Metrics
        total_members = (
            database.scalar(
                select(func.count(Membership.id)).where(
                    Membership.tenant_id == tenant_context.tenant_id,
                    Membership.status == MembershipStatus.ACTIVE,
                )
            )
            or 0
        )
        legal_entities = (
            database.scalar(
                select(func.count(LegalEntity.id)).where(
                    LegalEntity.tenant_id == tenant_context.tenant_id
                )
            )
            or 0
        )
        business_units = (
            database.scalar(
                select(func.count(BusinessUnit.id)).where(
                    BusinessUnit.tenant_id == tenant_context.tenant_id
                )
            )
            or 0
        )
        locations = (
            database.scalar(
                select(func.count(Location.id)).where(
                    Location.tenant_id == tenant_context.tenant_id
                )
            )
            or 0
        )
        entitlement = database.scalar(
            select(TenantEntitlement).where(TenantEntitlement.tenant_id == tenant_context.tenant_id)
        )

        admin_metrics = DashboardAdminMetrics(
            total_members=total_members,
            legal_entities=legal_entities,
            business_units=business_units,
            locations=locations,
            storage_bytes_used=0,
            max_storage_bytes=entitlement.max_storage_bytes if entitlement else 10737418240,
            plan_code=entitlement.plan_code if entitlement else "tier_a",
            enabled_modules=entitlement.enabled_modules if entitlement else [],
        )

        # Recent activity (safe audit events)
        recent_events = database.scalars(
            select(AuditEvent)
            .where(AuditEvent.tenant_id == tenant_context.tenant_id)
            .order_by(AuditEvent.occurred_at.desc())
            .limit(10)
        ).all()

        record_audit_event(
            database,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="dashboard.summary_viewed",
            resource_type="dashboard",
            resource_id=str(tenant_context.tenant_id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"role": "administrator"},
        )

        return DashboardSummary(
            readiness_score=0,
            controls_summary=DashboardControlsSummary(
                total=0, implemented=0, in_progress=0, not_started=0
            ),
            frameworks_adopted=[],
            expiring_evidence=[],
            review_due_policies=[],
            open_tasks=[],
            top_risks=[],
            vendor_health=DashboardVendorHealth(
                total_vendors=0, signed_dpa_count=0, missing_dpa_count=0, critical_vendors=0
            ),
            recent_activity=[
                DashboardActivityItem(
                    id=e.id,
                    action=e.action,
                    resource_type=e.resource_type,
                    actor_type=e.actor_type.value
                    if hasattr(e.actor_type, "value")
                    else str(e.actor_type),
                    occurred_at=e.occurred_at,
                )
                for e in recent_events
            ],
            is_administrator_view=True,
            admin_metrics=admin_metrics,
        )

    # 1. Frameworks & Controls Posture
    active_adoptions = database.scalars(
        select(TenantFrameworkAdoption).where(
            TenantFrameworkAdoption.tenant_id == tenant_context.tenant_id,
            TenantFrameworkAdoption.status == AdoptionStatus.ACTIVE,
        )
    ).all()

    control_statuses = database.scalars(
        select(ControlStatusRecord).where(ControlStatusRecord.tenant_id == tenant_context.tenant_id)
    ).all()
    status_map = {cs.control_id: cs.status for cs in control_statuses}

    framework_progress_list: list[DashboardFrameworkProgress] = []
    all_control_ids: set[UUID] = set()

    for adoption in active_adoptions:
        controls = database.scalars(
            select(CanonicalControl).where(
                CanonicalControl.framework_version_id == adoption.framework_version_id
            )
        ).all()
        f_total = len(controls)
        f_implemented = 0
        for c in controls:
            all_control_ids.add(c.id)
            if status_map.get(c.id) == ControlImplementationStatus.IMPLEMENTED:
                f_implemented += 1
        pct = round((f_implemented / f_total) * 100) if f_total > 0 else 0
        framework_progress_list.append(
            DashboardFrameworkProgress(
                framework_id=adoption.framework_id,
                framework_name=f"Framework {str(adoption.framework_id)[:8]}",
                version_name=None,
                total_controls=f_total,
                implemented_controls=f_implemented,
                progress_percentage=pct,
            )
        )

    total_controls = len(all_control_ids)
    implemented_count = sum(
        1
        for cid in all_control_ids
        if status_map.get(cid) == ControlImplementationStatus.IMPLEMENTED
    )
    in_progress_count = sum(
        1
        for cid in all_control_ids
        if status_map.get(cid) == ControlImplementationStatus.IN_PROGRESS
    )
    not_started_count = total_controls - (implemented_count + in_progress_count)
    readiness_score = round((implemented_count / total_controls) * 100) if total_controls > 0 else 0

    controls_summary = DashboardControlsSummary(
        total=total_controls,
        implemented=implemented_count,
        in_progress=in_progress_count,
        not_started=max(0, not_started_count),
    )

    # 2. Expiring Evidence (<30 days or overdue)
    thirty_days = now + timedelta(days=30)
    expiring_evidence_rows = database.scalars(
        select(EvidenceItem)
        .where(
            EvidenceItem.tenant_id == tenant_context.tenant_id,
            EvidenceItem.valid_until.is_not(None),
            EvidenceItem.valid_until <= thirty_days,
        )
        .order_by(EvidenceItem.valid_until.asc())
        .limit(5)
    ).all()
    expiring_evidence = [
        DashboardExpiringEvidence(
            id=ev.id,
            title=ev.title,
            expires_at=ev.valid_until or now,
            days_remaining=max(0, (ev.valid_until.date() - now.date()).days)
            if ev.valid_until
            else 0,
            classification=ev.classification,
        )
        for ev in expiring_evidence_rows
    ]

    # 3. Review-Due Policies (<30 days or overdue)
    review_due_policy_rows = database.scalars(
        select(Policy)
        .where(
            Policy.tenant_id == tenant_context.tenant_id,
            Policy.next_review_due.is_not(None),
            Policy.next_review_due <= thirty_days,
        )
        .order_by(Policy.next_review_due.asc())
        .limit(5)
    ).all()
    review_due_policies = [
        DashboardReviewDuePolicy(
            id=p.id,
            title=p.title,
            review_due_at=p.next_review_due or now,
            days_remaining=max(0, (p.next_review_due.date() - now.date()).days)
            if p.next_review_due
            else 0,
        )
        for p in review_due_policy_rows
    ]

    # 4. Open Tasks (Pending/In Progress)
    open_task_rows = database.scalars(
        select(ComplianceTask)
        .where(
            ComplianceTask.tenant_id == tenant_context.tenant_id,
            ComplianceTask.status != TaskStatus.COMPLETED,
        )
        .order_by(ComplianceTask.due_date.asc())
        .limit(5)
    ).all()
    open_tasks = [
        DashboardTaskItem(
            id=t.id,
            title=t.title,
            priority=t.priority.value if hasattr(t.priority, "value") else str(t.priority),
            status=t.status.value if hasattr(t.status, "value") else str(t.status),
            due_date=t.due_date,
        )
        for t in open_task_rows
    ]

    # 5. Top Risks by residual score
    risk_rows = database.scalars(
        select(Risk)
        .where(Risk.tenant_id == tenant_context.tenant_id)
        .order_by(Risk.inherent_score.desc())
        .limit(5)
    ).all()
    top_risks = [
        DashboardRiskItem(
            id=r.id,
            title=r.title,
            residual_score=r.residual_score,
            inherent_score=r.inherent_score,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
        )
        for r in risk_rows
    ]

    # 6. Vendor Health
    vendor_rows = database.scalars(
        select(Vendor).where(Vendor.tenant_id == tenant_context.tenant_id)
    ).all()
    total_vendors = len(vendor_rows)
    signed_dpa_count = sum(1 for v in vendor_rows if v.dpa_signed)
    missing_dpa_count = total_vendors - signed_dpa_count
    critical_vendors = sum(1 for v in vendor_rows if v.criticality == VendorCriticality.CRITICAL)

    vendor_health = DashboardVendorHealth(
        total_vendors=total_vendors,
        signed_dpa_count=signed_dpa_count,
        missing_dpa_count=missing_dpa_count,
        critical_vendors=critical_vendors,
    )

    # 7. Recent Activity (Audit Events)
    recent_events = database.scalars(
        select(AuditEvent)
        .where(AuditEvent.tenant_id == tenant_context.tenant_id)
        .order_by(AuditEvent.occurred_at.desc())
        .limit(10)
    ).all()
    recent_activity = [
        DashboardActivityItem(
            id=e.id,
            action=e.action,
            resource_type=e.resource_type,
            actor_type=e.actor_type.value if hasattr(e.actor_type, "value") else str(e.actor_type),
            occurred_at=e.occurred_at,
        )
        for e in recent_events
    ]

    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="dashboard.summary_viewed",
        resource_type="dashboard",
        resource_id=str(tenant_context.tenant_id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"record_count": total_controls},
    )

    return DashboardSummary(
        readiness_score=readiness_score,
        controls_summary=controls_summary,
        frameworks_adopted=framework_progress_list,
        expiring_evidence=expiring_evidence,
        review_due_policies=review_due_policies,
        open_tasks=open_tasks,
        top_risks=top_risks,
        vendor_health=vendor_health,
        recent_activity=recent_activity,
        is_administrator_view=False,
        admin_metrics=None,
    )
