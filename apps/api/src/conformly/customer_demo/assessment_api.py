"""FastAPI router and endpoints for MVP-C Customer Assessment and Findings."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.customer_demo.api import CustomerDemoRoute
from conformly.customer_demo.assessment_schemas import (
    AssessmentHistoryResponse,
    AssessmentProcedureDTO,
    AssessmentReceiptDTO,
    AssessmentWorkListResponse,
    CreateAssessmentRequest,
    CreateRetestRequest,
    PatchFindingRequest,
)
from conformly.customer_demo.assessment_service import CustomerAssessmentService
from conformly.db.session import get_db

assessment_router = APIRouter(
    prefix="/v2/tenants/{tenant_id}/customer-demo/assessment-work",
    tags=["customer-demo-assessment-work"],
    route_class=CustomerDemoRoute,
)


def _check_tenant_match(route_tenant_id: UUID, tenant_context: CurrentTenant) -> None:
    if route_tenant_id != tenant_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer demo access denied: route tenant_id does not match authenticated tenant context",
        )


@assessment_router.get(
    "",
    response_model=AssessmentWorkListResponse,
    status_code=status.HTTP_200_OK,
)
def get_assessment_work_list(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
    adoption_id: Annotated[UUID | None, Query()] = None,
) -> AssessmentWorkListResponse:
    """Read assessment work items and readiness summary for current or specified adoption."""
    _check_tenant_match(tenant_id, tenant_context)
    service = CustomerAssessmentService(db)
    return service.get_assessment_work_list(
        principal=principal,
        tenant_context=tenant_context,
        adoption_id=adoption_id,
    )


@assessment_router.get(
    "/{work_id}/procedure",
    response_model=AssessmentProcedureDTO,
    status_code=status.HTTP_200_OK,
)
def get_assessment_procedure(
    tenant_id: UUID,
    work_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> AssessmentProcedureDTO:
    """Read server-pinned synthetic procedure for specified control work item."""
    _check_tenant_match(tenant_id, tenant_context)
    service = CustomerAssessmentService(db)
    return service.get_procedure(
        principal=principal,
        tenant_context=tenant_context,
        work_id=work_id,
    )


@assessment_router.get(
    "/{work_id}/history",
    response_model=AssessmentHistoryResponse,
    status_code=status.HTTP_200_OK,
)
def get_assessment_history(
    tenant_id: UUID,
    work_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AssessmentHistoryResponse:
    """Read chronological assessment and finding history with decrypted narratives for authorized actors."""
    _check_tenant_match(tenant_id, tenant_context)
    service = CustomerAssessmentService(db)
    return service.get_history(
        principal=principal,
        tenant_context=tenant_context,
        work_id=work_id,
        limit=limit,
        offset=offset,
    )


@assessment_router.post(
    "/{work_id}/assessments",
    response_model=AssessmentReceiptDTO,
    status_code=status.HTTP_201_CREATED,
)
def record_assessment(
    tenant_id: UUID,
    work_id: UUID,
    body: CreateAssessmentRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> AssessmentReceiptDTO:
    """Record human assessment decision, updating head and recording immutable journal event."""
    _check_tenant_match(tenant_id, tenant_context)
    service = CustomerAssessmentService(db)
    return service.record_assessment(
        principal=principal,
        tenant_context=tenant_context,
        work_id=work_id,
        body=body,
    )


@assessment_router.post(
    "/{work_id}/retests",
    response_model=AssessmentReceiptDTO,
    status_code=status.HTTP_201_CREATED,
)
def record_retest(
    tenant_id: UUID,
    work_id: UUID,
    body: CreateRetestRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> AssessmentReceiptDTO:
    """Record explicit human retest against open findings for specified control work item."""
    _check_tenant_match(tenant_id, tenant_context)
    service = CustomerAssessmentService(db)
    return service.record_retest(
        principal=principal,
        tenant_context=tenant_context,
        work_id=work_id,
        body=body,
    )


@assessment_router.patch(
    "/findings/{finding_id}",
    response_model=AssessmentReceiptDTO,
    status_code=status.HTTP_200_OK,
)
@assessment_router.patch(
    "/{work_id}/findings/{finding_id}",
    response_model=AssessmentReceiptDTO,
    status_code=status.HTTP_200_OK,
)
def patch_finding(
    tenant_id: UUID,
    finding_id: UUID,
    body: PatchFindingRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
    work_id: UUID | None = None,
) -> AssessmentReceiptDTO:
    """Update finding remediation, owner, due date, or severity with CAS version guard."""
    _check_tenant_match(tenant_id, tenant_context)
    service = CustomerAssessmentService(db)
    return service.patch_finding(
        principal=principal,
        tenant_context=tenant_context,
        finding_id=finding_id,
        body=body,
    )
