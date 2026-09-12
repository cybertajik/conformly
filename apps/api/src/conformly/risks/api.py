from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError
from conformly.db.session import get_db
from conformly.entitlements.dependencies import require_module
from conformly.risks import service
from conformly.risks.models import RiskCategory, RiskStatus, RiskTreatmentStrategy

router = APIRouter(
    prefix="/v1/tenants/{tenant_id}/risks",
    tags=["risks"],
    dependencies=[Depends(require_module("risks"))],
)


class RiskTreatmentResponse(BaseModel):
    id: UUID
    strategy: RiskTreatmentStrategy
    treatment_plan: str
    target_date: datetime | None
    status: str
    created_at: datetime


class RiskResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    description: str
    category: RiskCategory
    likelihood: int
    impact: int
    inherent_score: int
    residual_score: int | None
    status: RiskStatus
    owner_user_id: UUID | None
    control_id: UUID | None
    created_at: datetime
    treatments: list[RiskTreatmentResponse] = []


class RiskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    category: RiskCategory = Field(default=RiskCategory.SECURITY)
    likelihood: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    owner_user_id: UUID | None = Field(default=None)
    control_id: UUID | None = Field(default=None)


class RiskTreatmentCreateRequest(BaseModel):
    strategy: RiskTreatmentStrategy = Field(default=RiskTreatmentStrategy.MITIGATE)
    treatment_plan: str = Field(min_length=1)
    target_date: datetime | None = Field(default=None)


@router.get("", response_model=list[RiskResponse])
def list_risks_endpoint(
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> list[RiskResponse]:
    request_id = getattr(request.state, "request_id", "req-risk-list")
    try:
        risks = service.list_risks(database, principal, tenant_context, request_id)
        return [
            RiskResponse(
                id=r.id,
                tenant_id=r.tenant_id,
                title=r.title,
                description=r.description,
                category=r.category,
                likelihood=r.likelihood,
                impact=r.impact,
                inherent_score=r.inherent_score,
                residual_score=r.residual_score,
                status=r.status,
                owner_user_id=r.owner_user_id,
                control_id=r.control_id,
                created_at=r.created_at,
                treatments=[
                    RiskTreatmentResponse(
                        id=t.id,
                        strategy=t.strategy,
                        treatment_plan=t.treatment_plan,
                        target_date=t.target_date,
                        status=t.status,
                        created_at=t.created_at,
                    )
                    for t in r.treatments
                ],
            )
            for r in risks
        ]
    except AuthorizationDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing risk:read capability")


@router.post("", response_model=RiskResponse, status_code=status.HTTP_201_CREATED)
def create_risk_endpoint(
    payload: RiskCreateRequest,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> RiskResponse:
    request_id = getattr(request.state, "request_id", "req-risk-create")
    try:
        risk = service.create_risk(
            database,
            principal,
            tenant_context,
            title=payload.title,
            description=payload.description,
            category=payload.category,
            likelihood=payload.likelihood,
            impact=payload.impact,
            owner_user_id=payload.owner_user_id,
            control_id=payload.control_id,
            request_id=request_id,
        )
        database.commit()
        return RiskResponse(
            id=risk.id,
            tenant_id=risk.tenant_id,
            title=risk.title,
            description=risk.description,
            category=risk.category,
            likelihood=risk.likelihood,
            impact=risk.impact,
            inherent_score=risk.inherent_score,
            residual_score=risk.residual_score,
            status=risk.status,
            owner_user_id=risk.owner_user_id,
            control_id=risk.control_id,
            created_at=risk.created_at,
            treatments=[],
        )
    except AuthorizationDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing risk:manage capability")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.post("/{risk_id}/treatments", response_model=RiskTreatmentResponse, status_code=status.HTTP_201_CREATED)
def add_treatment_endpoint(
    risk_id: UUID,
    payload: RiskTreatmentCreateRequest,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> RiskTreatmentResponse:
    request_id = getattr(request.state, "request_id", "req-treatment-create")
    try:
        treatment = service.add_risk_treatment(
            database,
            principal,
            tenant_context,
            risk_id=risk_id,
            strategy=payload.strategy,
            treatment_plan=payload.treatment_plan,
            target_date=payload.target_date,
            request_id=request_id,
        )
        database.commit()
        return RiskTreatmentResponse(
            id=treatment.id,
            strategy=treatment.strategy,
            treatment_plan=treatment.treatment_plan,
            target_date=treatment.target_date,
            status=treatment.status,
            created_at=treatment.created_at,
        )
    except AuthorizationDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing risk:manage capability")
    except service.RiskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
