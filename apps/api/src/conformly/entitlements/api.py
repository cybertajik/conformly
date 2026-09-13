from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError
from conformly.db.session import get_db
from conformly.entitlements import service

router = APIRouter(prefix="/v1/tenants/{tenant_id}/entitlements", tags=["entitlements"])


class TenantEntitlementResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    plan_code: str
    enabled_modules: list[str]
    max_members: int
    max_storage_bytes: int
    allowed_framework_slugs: list[str]
    effective_from: datetime
    effective_until: datetime | None


class TenantEntitlementUpdateRequest(BaseModel):
    enabled_modules: list[str] = Field(min_length=1)
    max_members: int = Field(ge=1)
    max_storage_bytes: int = Field(ge=1024 * 1024)
    allowed_framework_slugs: list[str] | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None


@router.get("", response_model=TenantEntitlementResponse)
def get_entitlement_endpoint(
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> TenantEntitlementResponse:
    request_id = getattr(request.state, "request_id", "req-entitlement-get")
    try:
        entitlement = service.get_tenant_entitlement(database, principal, tenant_context, request_id)
        return TenantEntitlementResponse(
            id=entitlement.id,
            tenant_id=entitlement.tenant_id,
            plan_code=entitlement.plan_code,
            enabled_modules=entitlement.enabled_modules,
            max_members=entitlement.max_members,
            max_storage_bytes=entitlement.max_storage_bytes,
            allowed_framework_slugs=entitlement.allowed_framework_slugs or ["*"],
            effective_from=entitlement.effective_from,
            effective_until=entitlement.effective_until,
        )
    except AuthorizationDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing entitlement:read capability"
        )


@router.put("", response_model=TenantEntitlementResponse)
def update_entitlement_endpoint(
    payload: TenantEntitlementUpdateRequest,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> TenantEntitlementResponse:
    request_id = getattr(request.state, "request_id", "req-entitlement-update")
    try:
        entitlement = service.update_tenant_entitlement(
            database,
            principal,
            tenant_context,
            enabled_modules=payload.enabled_modules,
            max_members=payload.max_members,
            max_storage_bytes=payload.max_storage_bytes,
            allowed_framework_slugs=payload.allowed_framework_slugs,
            effective_from=payload.effective_from,
            effective_until=payload.effective_until,
            request_id=request_id,
        )
        database.commit()
        return TenantEntitlementResponse(
            id=entitlement.id,
            tenant_id=entitlement.tenant_id,
            plan_code=entitlement.plan_code,
            enabled_modules=entitlement.enabled_modules,
            max_members=entitlement.max_members,
            max_storage_bytes=entitlement.max_storage_bytes,
            allowed_framework_slugs=entitlement.allowed_framework_slugs or ["*"],
            effective_from=entitlement.effective_from,
            effective_until=entitlement.effective_until,
        )
    except AuthorizationDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing entitlement:manage capability"
        )
