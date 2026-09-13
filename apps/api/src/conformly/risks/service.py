from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize, authorize_resource
from conformly.authz.roles import Capability
from conformly.risks.models import (
    Risk,
    RiskCategory,
    RiskStatus,
    RiskTreatment,
    RiskTreatmentStrategy,
)


class RiskNotFoundError(Exception):
    """Raised when a risk is not found in the tenant."""


class TreatmentNotFoundError(Exception):
    """Raised when a treatment is not found in the tenant."""


def list_risks(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    request_id: str,
    category: RiskCategory | None = None,
    status: RiskStatus | None = None,
) -> list[Risk]:
    authorize(principal, tenant_context, Capability.RISK_READ)
    stmt = select(Risk).where(Risk.tenant_id == tenant_context.tenant_id)
    if tenant_context.legal_entity_id is not None:
        stmt = stmt.where(Risk.legal_entity_id == tenant_context.legal_entity_id)
    if tenant_context.business_unit_id is not None:
        stmt = stmt.where(Risk.business_unit_id == tenant_context.business_unit_id)
    if category is not None:
        stmt = stmt.where(Risk.category == category)
    if status is not None:
        stmt = stmt.where(Risk.status == status)
    stmt = stmt.order_by(Risk.inherent_score.desc(), Risk.created_at.desc())
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


def get_risk(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    risk_id: UUID,
    request_id: str,
) -> Risk:
    authorize(principal, tenant_context, Capability.RISK_READ)
    risk = database.scalar(
        select(Risk).where(Risk.id == risk_id, Risk.tenant_id == tenant_context.tenant_id)
    )
    if risk is None:
        raise RiskNotFoundError("Risk not found in tenant")
    authorize_resource(
        principal,
        tenant_context,
        Capability.RISK_READ,
        legal_entity_id=risk.legal_entity_id,
        business_unit_id=risk.business_unit_id,
    )
    return risk


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
    finding_id: UUID | None = None,
    legal_entity_id: UUID | None = None,
    business_unit_id: UUID | None = None,
) -> Risk:
    effective_legal_entity_id = tenant_context.legal_entity_id or legal_entity_id
    effective_business_unit_id = tenant_context.business_unit_id or business_unit_id
    authorize(principal, tenant_context, Capability.RISK_MANAGE)
    authorize_resource(
        principal,
        tenant_context,
        Capability.RISK_MANAGE,
        legal_entity_id=effective_legal_entity_id,
        business_unit_id=effective_business_unit_id,
    )
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
        finding_id=finding_id,
        legal_entity_id=effective_legal_entity_id,
        business_unit_id=effective_business_unit_id,
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


def update_risk(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    risk_id: UUID,
    title: str,
    description: str,
    category: RiskCategory,
    likelihood: int,
    impact: int,
    residual_score: int | None,
    status: RiskStatus,
    owner_user_id: UUID | None,
    control_id: UUID | None,
    finding_id: UUID | None,
    request_id: str,
    legal_entity_id: UUID | None = None,
    business_unit_id: UUID | None = None,
) -> Risk:
    authorize(principal, tenant_context, Capability.RISK_MANAGE)
    risk = get_risk(database, principal, tenant_context, risk_id, request_id)
    authorize_resource(
        principal,
        tenant_context,
        Capability.RISK_MANAGE,
        legal_entity_id=risk.legal_entity_id,
        business_unit_id=risk.business_unit_id,
    )
    if not (1 <= likelihood <= 5) or not (1 <= impact <= 5):
        raise ValueError("Likelihood and impact must be between 1 and 5")
    risk.title = title.strip()
    risk.description = description.strip()
    risk.category = category
    risk.likelihood = likelihood
    risk.impact = impact
    risk.inherent_score = likelihood * impact
    risk.residual_score = residual_score if residual_score is not None else risk.inherent_score
    risk.status = status
    risk.owner_user_id = owner_user_id
    risk.control_id = control_id
    risk.finding_id = finding_id
    if legal_entity_id is not None:
        risk.legal_entity_id = legal_entity_id
    if business_unit_id is not None:
        risk.business_unit_id = business_unit_id
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="risk.update",
        resource_type="risk",
        resource_id=str(risk.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"title": risk.title, "status": risk.status.value},
    )
    return risk


def complete_risk_review(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    risk_id: UUID,
    next_review_due_at: datetime | None,
    request_id: str,
) -> Risk:
    authorize(principal, tenant_context, Capability.RISK_MANAGE)
    risk = get_risk(database, principal, tenant_context, risk_id, request_id)
    authorize_resource(
        principal,
        tenant_context,
        Capability.RISK_MANAGE,
        legal_entity_id=risk.legal_entity_id,
        business_unit_id=risk.business_unit_id,
    )
    now = datetime.now(UTC)
    risk.last_reviewed_at = now
    risk.next_review_due_at = next_review_due_at
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="risk.review.complete",
        resource_type="risk",
        resource_id=str(risk.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"last_reviewed_at": now.isoformat()},
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
    owner_user_id: UUID | None = None,
) -> RiskTreatment:
    authorize(principal, tenant_context, Capability.RISK_MANAGE)
    risk = get_risk(database, principal, tenant_context, risk_id, request_id)
    authorize_resource(
        principal,
        tenant_context,
        Capability.RISK_MANAGE,
        legal_entity_id=risk.legal_entity_id,
        business_unit_id=risk.business_unit_id,
    )
    treatment = RiskTreatment(
        tenant_id=tenant_context.tenant_id,
        risk_id=risk_id,
        strategy=strategy,
        treatment_plan=treatment_plan.strip(),
        target_date=target_date,
        owner_user_id=owner_user_id,
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


def update_risk_treatment(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    treatment_id: UUID,
    strategy: RiskTreatmentStrategy,
    treatment_plan: str,
    target_date: datetime | None,
    status: str,
    owner_user_id: UUID | None,
    request_id: str,
) -> RiskTreatment:
    authorize(principal, tenant_context, Capability.RISK_MANAGE)
    treatment = database.scalar(
        select(RiskTreatment).where(
            RiskTreatment.id == treatment_id,
            RiskTreatment.tenant_id == tenant_context.tenant_id,
        )
    )
    if treatment is None:
        raise TreatmentNotFoundError("Treatment not found in tenant")
    risk = get_risk(database, principal, tenant_context, treatment.risk_id, request_id)
    authorize_resource(
        principal,
        tenant_context,
        Capability.RISK_MANAGE,
        legal_entity_id=risk.legal_entity_id,
        business_unit_id=risk.business_unit_id,
    )
    treatment.strategy = strategy
    treatment.treatment_plan = treatment_plan.strip()
    treatment.target_date = target_date
    treatment.status = status.strip().lower()
    treatment.owner_user_id = owner_user_id
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="risk.treatment.update",
        resource_type="risk_treatment",
        resource_id=str(treatment.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"risk_id": str(treatment.risk_id), "status": treatment.status},
    )
    return treatment


def delete_risk(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    risk_id: UUID,
    request_id: str,
) -> None:
    authorize(principal, tenant_context, Capability.RISK_MANAGE)
    risk = get_risk(database, principal, tenant_context, risk_id, request_id)
    authorize_resource(
        principal,
        tenant_context,
        Capability.RISK_MANAGE,
        legal_entity_id=risk.legal_entity_id,
        business_unit_id=risk.business_unit_id,
    )
    database.delete(risk)
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="risk.delete",
        resource_type="risk",
        resource_id=str(risk_id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"title": risk.title},
    )
