"""FastAPI router for V2 Pre-Audit Review Workflow."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.config import Settings, get_settings
from conformly.customer_demo.api import CustomerDemoRoute
from conformly.customer_demo.preaudit_schemas import (
    ApprovePreauditRequest,
    CancelPreauditRequest,
    CreatePreauditRequest,
    DownloadPreauditReportRequest,
    FreezeScopeRequest,
    PreauditActorsResponse,
    PreauditDetailResponse,
    PreauditHistoryResponse,
    PreauditListResponse,
    ReviewDecisionRequest,
    SubmitReviewRequest,
)
from conformly.customer_demo.preaudit_service import CustomerPreauditService
from conformly.db.session import get_db

preaudit_router = APIRouter(
    prefix="/v2/tenants/{tenant_id}/customer-demo/preaudits",
    tags=["customer-demo-preaudit"],
    route_class=CustomerDemoRoute,
)


def verify_preaudit_feature_enabled(
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Ensure pre-audit feature is enabled in permitted development/test environment."""
    if not settings.enable_customer_preaudit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pre-audit review feature is not enabled")
    if not settings.enable_customer_demo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer demo feature is not enabled")
    if settings.environment not in ("local", "development", "test"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pre-audit review prohibited in non-development environments")


def _check_route_tenant(route_tenant_id: UUID, current_tenant: CurrentTenant) -> None:
    if route_tenant_id != current_tenant.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access prohibited")


@preaudit_router.get(
    "/actors",
    response_model=PreauditActorsResponse,
    dependencies=[Depends(verify_preaudit_feature_enabled)],
)
def get_eligible_actors(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> PreauditActorsResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerPreauditService(db)
    actors = service.get_eligible_actors(principal, tenant_context)
    return PreauditActorsResponse(actors=actors)


@preaudit_router.get(
    "",
    response_model=PreauditListResponse,
    dependencies=[Depends(verify_preaudit_feature_enabled)],
)
def list_preaudits(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PreauditListResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerPreauditService(db)
    return service.list_cases(principal, tenant_context, limit=limit, offset=offset)


@preaudit_router.post(
    "",
    response_model=PreauditDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_preaudit_feature_enabled)],
)
def create_preaudit(
    tenant_id: UUID,
    req: CreatePreauditRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> PreauditDetailResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerPreauditService(db)
    res = service.create_case(principal, tenant_context, req)
    db.commit()
    return res


@preaudit_router.get(
    "/{case_id}",
    response_model=PreauditDetailResponse,
    dependencies=[Depends(verify_preaudit_feature_enabled)],
)
def get_preaudit(
    tenant_id: UUID,
    case_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> PreauditDetailResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerPreauditService(db)
    return service.get_case(principal, tenant_context, case_id)


@preaudit_router.get(
    "/{case_id}/history",
    response_model=PreauditHistoryResponse,
    dependencies=[Depends(verify_preaudit_feature_enabled)],
)
def get_preaudit_history(
    tenant_id: UUID,
    case_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> PreauditHistoryResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerPreauditService(db)
    return service.get_case_history(principal, tenant_context, case_id)


@preaudit_router.post(
    "/{case_id}/freeze",
    response_model=PreauditDetailResponse,
    dependencies=[Depends(verify_preaudit_feature_enabled)],
)
def freeze_scope(
    tenant_id: UUID,
    case_id: UUID,
    req: FreezeScopeRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> PreauditDetailResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerPreauditService(db)
    res = service.freeze_scope(principal, tenant_context, case_id, req)
    db.commit()
    return res


@preaudit_router.post(
    "/{case_id}/submit",
    response_model=PreauditDetailResponse,
    dependencies=[Depends(verify_preaudit_feature_enabled)],
)
def submit_review(
    tenant_id: UUID,
    case_id: UUID,
    req: SubmitReviewRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> PreauditDetailResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerPreauditService(db)
    res = service.submit_review(principal, tenant_context, case_id, req)
    db.commit()
    return res


@preaudit_router.post(
    "/{case_id}/review",
    response_model=PreauditDetailResponse,
    dependencies=[Depends(verify_preaudit_feature_enabled)],
)
def review_decision(
    tenant_id: UUID,
    case_id: UUID,
    req: ReviewDecisionRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> PreauditDetailResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerPreauditService(db)
    res = service.review_decision(principal, tenant_context, case_id, req)
    db.commit()
    return res


@preaudit_router.post(
    "/{case_id}/approve",
    response_model=PreauditDetailResponse,
    dependencies=[Depends(verify_preaudit_feature_enabled)],
)
def approve_case(
    tenant_id: UUID,
    case_id: UUID,
    req: ApprovePreauditRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> PreauditDetailResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerPreauditService(db)
    res = service.approve_case(principal, tenant_context, case_id, req)
    db.commit()
    return res


@preaudit_router.post(
    "/{case_id}/cancel",
    response_model=PreauditDetailResponse,
    dependencies=[Depends(verify_preaudit_feature_enabled)],
)
def cancel_case(
    tenant_id: UUID,
    case_id: UUID,
    req: CancelPreauditRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> PreauditDetailResponse:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerPreauditService(db)
    res = service.cancel_case(principal, tenant_context, case_id, req)
    db.commit()
    return res


@preaudit_router.post(
    "/{case_id}/report/download",
    dependencies=[Depends(verify_preaudit_feature_enabled)],
)
def download_preaudit_report(
    tenant_id: UUID,
    case_id: UUID,
    req: DownloadPreauditReportRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    _check_route_tenant(tenant_id, tenant_context)
    service = CustomerPreauditService(db)
    zip_bytes, zip_sha256, case, snapshot = service.download_report(
        principal, tenant_context, case_id, req
    )
    db.commit()

    filename = f"preaudit-report-{str(case_id)[:8]}.zip"
    headers = {
        "Content-Type": "application/zip",
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Preaudit-Id": str(case_id),
        "X-Preaudit-Snapshot-Digest": snapshot.digest,
        "X-Report-SHA256": zip_sha256,
        "Cache-Control": "private, no-store",
    }
    return Response(content=zip_bytes, media_type="application/zip", headers=headers)

