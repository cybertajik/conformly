from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError
from conformly.authz.roles import Capability
from conformly.compliance.service import EvidenceNotFoundError, InvalidTenantReferenceError
from conformly.crypto.fields import get_encrypted_field_codec
from conformly.db.session import get_db
from conformly.entitlements.dependencies import require_module
from conformly.frameworks.readiness import evaluate_specifications
from conformly.frameworks.workflow import (
    FrameworkEvidenceRequest,
    FrameworkWorkflowService,
    WorkflowInputError,
    serialize_request,
)

router = APIRouter(
    prefix="/v1/tenants/{tenant_id}/framework-workflow",
    tags=["framework_workflow"],
    dependencies=[Depends(require_module("frameworks"))],
)


class GenerateRequests(BaseModel):
    due_date: datetime
    owner_user_id: UUID


class AcceptEvidence(BaseModel):
    evidence_id: UUID
    observation_start: datetime
    observation_end: datetime


class EvidenceRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    adoption_id: UUID
    specification_id: UUID
    task_id: UUID
    evidence_id: UUID | None
    evidence_version: int | None
    observation_start: datetime | None
    observation_end: datetime | None
    accepted_by_user_id: UUID | None
    accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime


def workflow_service(db: Annotated[Session, Depends(get_db)]) -> FrameworkWorkflowService:
    return FrameworkWorkflowService(db, get_encrypted_field_codec())


@router.post("/{adoption_id}/evidence-requests", response_model=list[EvidenceRequestResponse])
def generate_requests(
    adoption_id: UUID,
    body: GenerateRequests,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    service: Annotated[FrameworkWorkflowService, Depends(workflow_service)],
) -> list[dict[str, Any]]:
    try:
        rows = service.generate(principal, tenant, adoption_id, **body.model_dump())
        result = [serialize_request(row) for row in rows]
        service.session.commit()
        return result
    except AuthorizationDeniedError as error:
        service.session.rollback()
        raise HTTPException(403, str(error)) from error
    except (ValueError, InvalidTenantReferenceError) as error:
        service.session.rollback()
        raise HTTPException(422, str(error)) from error


@router.post(
    "/{adoption_id}/evidence-requests/{request_id}/accept", response_model=EvidenceRequestResponse
)
def accept_evidence(
    adoption_id: UUID,
    request_id: UUID,
    body: AcceptEvidence,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    service: Annotated[FrameworkWorkflowService, Depends(workflow_service)],
) -> dict[str, Any]:
    try:
        row = service.accept(principal, tenant, adoption_id, request_id, **body.model_dump())
        result = serialize_request(row)
        service.session.commit()
        return result
    except AuthorizationDeniedError as error:
        service.session.rollback()
        raise HTTPException(403, str(error)) from error
    except (WorkflowInputError, EvidenceNotFoundError) as error:
        service.session.rollback()
        raise HTTPException(
            422, "Evidence request or evidence unavailable or unsuitable"
        ) from error


@router.get("/{adoption_id}/evidence-requests", response_model=list[EvidenceRequestResponse])
def list_evidence_requests(
    adoption_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    """List all evidence requests for the given adoption, scoped to the authenticated tenant."""
    from conformly.authz.policy import authorize

    try:
        authorize(principal, tenant, Capability.FRAMEWORK_READ)
    except AuthorizationDeniedError as error:
        raise HTTPException(403, str(error)) from error
    rows = list(
        db.scalars(
            select(FrameworkEvidenceRequest).where(
                FrameworkEvidenceRequest.tenant_id == tenant.tenant_id,
                FrameworkEvidenceRequest.adoption_id == adoption_id,
            )
        )
    )
    return [serialize_request(row) for row in rows]


@router.get("/{adoption_id}/readiness")
def get_readiness(
    adoption_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Return the structured readiness evaluation for an adoption including all blockers."""
    from conformly.authz.policy import authorize
    from conformly.frameworks.models import TenantFrameworkAdoption

    try:
        authorize(principal, tenant, Capability.FRAMEWORK_READ)
    except AuthorizationDeniedError as error:
        raise HTTPException(403, str(error)) from error
    adoption = db.scalar(
        select(TenantFrameworkAdoption).where(
            TenantFrameworkAdoption.id == adoption_id,
            TenantFrameworkAdoption.tenant_id == tenant.tenant_id,
        )
    )
    if adoption is None:
        raise HTTPException(404, "Framework adoption not found")
    result = evaluate_specifications(
        db, tenant.tenant_id, adoption_id, adoption.framework_version_id
    )
    return result
