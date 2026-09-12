from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize
from conformly.authz.roles import Capability
from conformly.risks.models import Risk, RiskCategory, RiskStatus, RiskTreatment, RiskTreatmentStrategy


class RiskNotFoundError(Exception):
    """Raised when a risk is not found in the tenant."""


def list_risks(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    request_id: str,
) -> list[Risk]:
    authorize(principal, tenant_context, Capability.RISK_READ)
    stmt = (
        select(Risk)
        .where(Risk.tenant_id == tenant_context.tenant_id)
        .order_by(Risk.inherent_score.desc(), Risk.created_at.desc())
    )
    risks = list(database.scalars(stmt).all())
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="risk.list",
        resource_type="risk",
        resource_id=None,
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"count": len(risks)},
    )
    return risks


def create_risk(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    title: str,
    description: str,
    category: RiskCategory,
    likelihood: int,
    impact: int,
    owner_user_id: UUID | None,
    control_id: UUID | None,
    request_id: str,
) -> Risk:
    authorize(principal, tenant_context, Capability.RISK_MANAGE)
    if not (1 <= likelihood <= 5) or not (1 <= impact <= 5):
        raise ValueError("Likelihood and impact must be between 1 and 5")
    inherent_score = likelihood * impact
    risk = Risk(
        tenant_id=tenant_context.tenant_id,
        title=title.strip(),
        description=description.strip(),
        category=category,
        likelihood=likelihood,
        impact=impact,
        inherent_score=inherent_score,
        residual_score=inherent_score,
        status=RiskStatus.IDENTIFIED,
        owner_user_id=owner_user_id,
        control_id=control_id,
    )
    database.add(risk)
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="risk.create",
        resource_type="risk",
        resource_id=str(risk.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"title": risk.title, "inherent_score": inherent_score},
    )
    return risk


def add_risk_treatment(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    risk_id: UUID,
    strategy: RiskTreatmentStrategy,
    treatment_plan: str,
    target_date: datetime | None,
    request_id: str,
) -> RiskTreatment:
    authorize(principal, tenant_context, Capability.RISK_MANAGE)
    risk = database.scalar(
        select(Risk).where(Risk.id == risk_id, Risk.tenant_id == tenant_context.tenant_id)
    )
    if risk is None:
        raise RiskNotFoundError("Risk not found in tenant")
    treatment = RiskTreatment(
        tenant_id=tenant_context.tenant_id,
        risk_id=risk_id,
        strategy=strategy,
        treatment_plan=treatment_plan.strip(),
        target_date=target_date,
        status="planned",
    )
    risk.status = RiskStatus.TREATING
    database.add(treatment)
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="risk.treatment.create",
        resource_type="risk_treatment",
        resource_id=str(treatment.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"risk_id": str(risk_id), "strategy": strategy.value},
    )
    return treatment
