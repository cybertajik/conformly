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
from conformly.vendors import service
from conformly.vendors.models import VendorCriticality, VendorStatus

router = APIRouter(
    prefix="/v1/tenants/{tenant_id}/vendors",
    tags=["vendors"],
    dependencies=[Depends(require_module("vendors"))],
)


class VendorResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    service_description: str
    criticality: VendorCriticality
    data_classification_accessed: str
    country_residency: str
    dpa_signed: bool
    security_reviewed_at: datetime | None
    next_review_due_at: datetime | None
    status: VendorStatus
    created_at: datetime


class VendorCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    service_description: str = Field(min_length=1)
    criticality: VendorCriticality = Field(default=VendorCriticality.MEDIUM)
    data_classification_accessed: str = Field(default="Confidential")
    country_residency: str = Field(default="DE")
    dpa_signed: bool = Field(default=False)
    security_reviewed_at: datetime | None = Field(default=None)
    next_review_due_at: datetime | None = Field(default=None)


@router.get("", response_model=list[VendorResponse])
def list_vendors_endpoint(
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> list[VendorResponse]:
    request_id = getattr(request.state, "request_id", "req-vendor-list")
    try:
        vendors = service.list_vendors(database, principal, tenant_context, request_id)
        return [
            VendorResponse(
                id=v.id,
                tenant_id=v.tenant_id,
                name=v.name,
                service_description=v.service_description,
                criticality=v.criticality,
                data_classification_accessed=v.data_classification_accessed,
                country_residency=v.country_residency,
                dpa_signed=v.dpa_signed,
                security_reviewed_at=v.security_reviewed_at,
                next_review_due_at=v.next_review_due_at,
                status=v.status,
                created_at=v.created_at,
            )
            for v in vendors
        ]
    except AuthorizationDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing vendor:read capability")


@router.post("", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
def create_vendor_endpoint(
    payload: VendorCreateRequest,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> VendorResponse:
    request_id = getattr(request.state, "request_id", "req-vendor-create")
    try:
        vendor = service.create_vendor(
            database,
            principal,
            tenant_context,
            name=payload.name,
            service_description=payload.service_description,
            criticality=payload.criticality,
            data_classification_accessed=payload.data_classification_accessed,
            country_residency=payload.country_residency,
            dpa_signed=payload.dpa_signed,
            security_reviewed_at=payload.security_reviewed_at,
            next_review_due_at=payload.next_review_due_at,
            request_id=request_id,
        )
        database.commit()
        return VendorResponse(
            id=vendor.id,
            tenant_id=vendor.tenant_id,
            name=vendor.name,
            service_description=vendor.service_description,
            criticality=vendor.criticality,
            data_classification_accessed=vendor.data_classification_accessed,
            country_residency=vendor.country_residency,
            dpa_signed=vendor.dpa_signed,
            security_reviewed_at=vendor.security_reviewed_at,
            next_review_due_at=vendor.next_review_due_at,
            status=vendor.status,
            created_at=vendor.created_at,
        )
    except AuthorizationDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing vendor:manage capability")
