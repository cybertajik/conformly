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
from conformly.vendors.models import Vendor, VendorCriticality, VendorStatus

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
    owner_user_id: UUID | None = None
    control_id: UUID | None = None
    finding_id: UUID | None = None
    legal_entity_id: UUID | None = None
    business_unit_id: UUID | None = None
    status: VendorStatus
    created_at: datetime


def _to_vendor_response(v: Vendor) -> VendorResponse:
    return VendorResponse(
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
        owner_user_id=v.owner_user_id,
        control_id=v.control_id,
        finding_id=v.finding_id,
        legal_entity_id=v.legal_entity_id,
        business_unit_id=v.business_unit_id,
        status=v.status,
        created_at=v.created_at,
    )


class VendorCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    service_description: str = Field(min_length=1)
    criticality: VendorCriticality = Field(default=VendorCriticality.MEDIUM)
    data_classification_accessed: str = Field(default="Confidential")
    country_residency: str = Field(default="DE")
    dpa_signed: bool = Field(default=False)
    security_reviewed_at: datetime | None = Field(default=None)
    next_review_due_at: datetime | None = Field(default=None)
    owner_user_id: UUID | None = Field(default=None)
    control_id: UUID | None = Field(default=None)
    finding_id: UUID | None = Field(default=None)
    legal_entity_id: UUID | None = Field(default=None)
    business_unit_id: UUID | None = Field(default=None)


class VendorUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    service_description: str = Field(min_length=1)
    criticality: VendorCriticality = Field(default=VendorCriticality.MEDIUM)
    data_classification_accessed: str = Field(default="Confidential")
    country_residency: str = Field(default="DE")
    dpa_signed: bool = Field(default=False)
    status: VendorStatus = Field(default=VendorStatus.ACTIVE)
    owner_user_id: UUID | None = Field(default=None)
    control_id: UUID | None = Field(default=None)
    finding_id: UUID | None = Field(default=None)
    legal_entity_id: UUID | None = Field(default=None)
    business_unit_id: UUID | None = Field(default=None)


class VendorReviewRequest(BaseModel):
    next_review_due_at: datetime | None = Field(default=None)


@router.get("", response_model=list[VendorResponse])
def list_vendors_endpoint(
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
    criticality: VendorCriticality | None = None,
    status_filter: VendorStatus | None = None,
) -> list[VendorResponse]:
    request_id = getattr(request.state, "request_id", "req-vendor-list")
    try:
        vendors = service.list_vendors(
            database,
            principal,
            tenant_context,
            request_id,
            criticality=criticality,
            status=status_filter,
        )
        return [_to_vendor_response(v) for v in vendors]
    except AuthorizationDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing vendor:read capability")


@router.get("/{vendor_id}", response_model=VendorResponse)
def get_vendor_endpoint(
    vendor_id: UUID,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> VendorResponse:
    request_id = getattr(request.state, "request_id", "req-vendor-get")
    try:
        vendor = service.get_vendor(database, principal, tenant_context, vendor_id, request_id)
        return _to_vendor_response(vendor)
    except AuthorizationDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing vendor:read capability")
    except service.VendorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


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
            owner_user_id=payload.owner_user_id,
            control_id=payload.control_id,
            finding_id=payload.finding_id,
            legal_entity_id=payload.legal_entity_id,
            business_unit_id=payload.business_unit_id,
        )
        database.commit()
        return _to_vendor_response(vendor)
    except AuthorizationDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing vendor:manage capability")


@router.put("/{vendor_id}", response_model=VendorResponse)
def update_vendor_endpoint(
    vendor_id: UUID,
    payload: VendorUpdateRequest,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> VendorResponse:
    request_id = getattr(request.state, "request_id", "req-vendor-update")
    try:
        vendor = service.update_vendor(
            database,
            principal,
            tenant_context,
            vendor_id=vendor_id,
            name=payload.name,
            service_description=payload.service_description,
            criticality=payload.criticality,
            data_classification_accessed=payload.data_classification_accessed,
            country_residency=payload.country_residency,
            dpa_signed=payload.dpa_signed,
            status=payload.status,
            owner_user_id=payload.owner_user_id,
            control_id=payload.control_id,
            finding_id=payload.finding_id,
            request_id=request_id,
            legal_entity_id=payload.legal_entity_id,
            business_unit_id=payload.business_unit_id,
        )
        database.commit()
        return _to_vendor_response(vendor)
    except AuthorizationDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing vendor:manage capability")
    except service.VendorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{vendor_id}/review", response_model=VendorResponse)
def complete_vendor_review_endpoint(
    vendor_id: UUID,
    payload: VendorReviewRequest,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> VendorResponse:
    request_id = getattr(request.state, "request_id", "req-vendor-review")
    try:
        vendor = service.complete_vendor_review(
            database,
            principal,
            tenant_context,
            vendor_id=vendor_id,
            next_review_due_at=payload.next_review_due_at,
            request_id=request_id,
        )
        database.commit()
        return _to_vendor_response(vendor)
    except AuthorizationDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing vendor:manage capability")
    except service.VendorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vendor_endpoint(
    vendor_id: UUID,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> None:
    request_id = getattr(request.state, "request_id", "req-vendor-delete")
    try:
        service.delete_vendor(database, principal, tenant_context, vendor_id, request_id)
        database.commit()
    except AuthorizationDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing vendor:manage capability")
    except service.VendorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

