"""FastAPI router for V2 Customer Readiness Verification Lifecycle."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.config import Settings, get_settings
from conformly.customer_demo.api import CustomerDemoRoute
from conformly.customer_demo.verification_schemas import (
    CorrectVerificationRequest,
    IssueVerificationRequest,
    ReconcileVerificationRequest,
    RevokeVerificationRequest,
    SupersedeVerificationRequest,
    SuspendVerificationRequest,
    VerificationDetailResponse,
    VerificationHistoryResponse,
    VerificationListResponse,
    VerificationProjectionResponse,
)
from conformly.customer_demo.verification_service import CustomerVerificationService
from conformly.db.session import get_db

verification_router = APIRouter(
    prefix="/v2/tenants/{tenant_id}/customer-demo/readiness-verifications",
    tags=["customer-demo-readiness-verification"],
    route_class=CustomerDemoRoute,
)


def verify_verification_feature_enabled(
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Ensure readiness verification feature is enabled in permitted development/test environment."""
    if not settings.enable_customer_readiness_verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Readiness verification feature is not enabled",
        )
    if not settings.enable_customer_demo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer demo feature is not enabled",
        )
    if not settings.enable_customer_preaudit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pre-audit review feature is not enabled",
        )
    if settings.environment not in ("local", "development", "test"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Readiness verification prohibited in non-development environments",
        )


def _check_route_tenant(route_tenant_id: UUID, current_tenant: CurrentTenant) -> None:
    if route_tenant_id != current_tenant.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access prohibited")


@verification_router.get(
    "",
    response_model=VerificationListResponse,
    dependencies=[Depends(verify_verification_feature_enabled)],
)
def list_verifications(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    preaudit_case_id: Annotated[UUID | None, Query()] = None,
) -> VerificationListResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerVerificationService(db)
    return service.list_verifications(
        principal, tenant_context, limit=limit, offset=offset, preaudit_case_id=preaudit_case_id
    )


@verification_router.post(
    "",
    response_model=VerificationDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_verification_feature_enabled)],
)
def issue_verification(
    tenant_id: UUID,
    req: IssueVerificationRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> VerificationDetailResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerVerificationService(db)
    res = service.issue_verification(principal, tenant_context, req)
    db.commit()
    return res


@verification_router.get(
    "/{verification_id}",
    response_model=VerificationDetailResponse,
    dependencies=[Depends(verify_verification_feature_enabled)],
)
def get_verification(
    tenant_id: UUID,
    verification_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> VerificationDetailResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerVerificationService(db)
    return service.get_verification(principal, tenant_context, verification_id)


@verification_router.get(
    "/{verification_id}/projection",
    response_model=VerificationProjectionResponse,
    dependencies=[Depends(verify_verification_feature_enabled)],
)
def get_verification_projection(
    tenant_id: UUID,
    verification_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> VerificationProjectionResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerVerificationService(db)
    return service.get_verification_projection(principal, tenant_context, verification_id)


@verification_router.get(
    "/{verification_id}/history",
    response_model=VerificationHistoryResponse,
    dependencies=[Depends(verify_verification_feature_enabled)],
)
def get_verification_history(
    tenant_id: UUID,
    verification_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> VerificationHistoryResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerVerificationService(db)
    return service.get_verification_history(principal, tenant_context, verification_id)


@verification_router.post(
    "/{verification_id}/suspend",
    response_model=VerificationDetailResponse,
    dependencies=[Depends(verify_verification_feature_enabled)],
)
def suspend_verification(
    tenant_id: UUID,
    verification_id: UUID,
    req: SuspendVerificationRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> VerificationDetailResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerVerificationService(db)
    res = service.suspend_verification(principal, tenant_context, verification_id, req)
    db.commit()
    return res


@verification_router.post(
    "/{verification_id}/revoke",
    response_model=VerificationDetailResponse,
    dependencies=[Depends(verify_verification_feature_enabled)],
)
def revoke_verification(
    tenant_id: UUID,
    verification_id: UUID,
    req: RevokeVerificationRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> VerificationDetailResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerVerificationService(db)
    res = service.revoke_verification(principal, tenant_context, verification_id, req)
    db.commit()
    return res


@verification_router.post(
    "/{verification_id}/correct",
    response_model=VerificationDetailResponse,
    dependencies=[Depends(verify_verification_feature_enabled)],
)
def correct_verification(
    tenant_id: UUID,
    verification_id: UUID,
    req: CorrectVerificationRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> VerificationDetailResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerVerificationService(db)
    res = service.correct_verification(principal, tenant_context, verification_id, req)
    db.commit()
    return res


@verification_router.post(
    "/{verification_id}/supersede",
    response_model=VerificationDetailResponse,
    dependencies=[Depends(verify_verification_feature_enabled)],
)
def supersede_verification(
    tenant_id: UUID,
    verification_id: UUID,
    req: SupersedeVerificationRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> VerificationDetailResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerVerificationService(db)
    res = service.supersede_verification(principal, tenant_context, verification_id, req)
    db.commit()
    return res


@verification_router.post(
    "/reconcile",
    dependencies=[Depends(verify_verification_feature_enabled)],
)
def reconcile_verifications(
    tenant_id: UUID,
    req: ReconcileVerificationRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerVerificationService(db)
    res = service.reconcile_lifecycle(principal, tenant_context, req)
    db.commit()
    return res

