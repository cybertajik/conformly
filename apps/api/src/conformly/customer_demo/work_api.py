"""FastAPI router and endpoints for MVP-B Customer Control Work and Evidence Pinning."""

from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.customer_demo.api import CustomerDemoRoute
from conformly.customer_demo.work_schemas import (
    CreateEvidenceRequest,
    CreateLinkRequest,
    CreateReviewRequest,
    InitializeWorkRequest,
    MutationReceipt,
    OwnerDirectoryResponse,
    PatchWorkRequest,
    WorkHistoryResponse,
    WorkListResponse,
)
from conformly.customer_demo.work_service import CustomerControlWorkService
from conformly.db.session import get_db

work_router = APIRouter(
    prefix="/v2/tenants/{tenant_id}/customer-demo/control-work",
    tags=["customer-demo-control-work"],
    route_class=CustomerDemoRoute,
)


def _check_tenant_match(route_tenant_id: UUID, tenant_context: CurrentTenant) -> None:
    if route_tenant_id != tenant_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer demo access denied: route tenant_id does not match authenticated tenant context",
        )


def _sanitize_filename(filename: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "_", filename)
    return cleaned or "evidence.bin"


@work_router.get(
    "",
    response_model=WorkListResponse,
    status_code=status.HTTP_200_OK,
)
def get_control_work_list(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
    adoption_id: Annotated[UUID | None, Query()] = None,
) -> WorkListResponse:
    """Read control work items for current or historical customer demo pack adoption."""
    _check_tenant_match(tenant_id, tenant_context)
    service = CustomerControlWorkService(db)
    return service.get_control_work_list(
        principal,
        tenant_context,
        adoption_id=adoption_id,
    )


@work_router.get(
    "/owners",
    response_model=OwnerDirectoryResponse,
    status_code=status.HTTP_200_OK,
)
def get_owners(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> OwnerDirectoryResponse:
    """Read bounded directory of eligible same-tenant control owners."""
    _check_tenant_match(tenant_id, tenant_context)
    service = CustomerControlWorkService(db)
    return service.get_owners(
        principal,
        tenant_context,
        limit=limit,
        offset=offset,
    )


@work_router.post(
    "/initialize",
    response_model=WorkListResponse,
    status_code=status.HTTP_200_OK,
)
def initialize_work(
    tenant_id: UUID,
    body: InitializeWorkRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> WorkListResponse:
    """Initialize control work items from adopted pack requirements."""
    _check_tenant_match(tenant_id, tenant_context)
    req_id = getattr(request.state, "request_id", None) or "req-ctrl-init"
    service = CustomerControlWorkService(db)
    return service.initialize_work(
        principal,
        tenant_context,
        body,
        request_id=req_id,
    )


@work_router.patch(
    "/{work_id}",
    response_model=MutationReceipt,
    status_code=status.HTTP_200_OK,
)
def patch_work(
    tenant_id: UUID,
    work_id: UUID,
    body: PatchWorkRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> MutationReceipt:
    """Update owner assignment and due date of a control work item."""
    _check_tenant_match(tenant_id, tenant_context)
    req_id = getattr(request.state, "request_id", None) or "req-ctrl-patch"
    service = CustomerControlWorkService(db)
    return service.patch_work(
        principal,
        tenant_context,
        work_id,
        body,
        request_id=req_id,
    )


@work_router.post(
    "/{work_id}/evidence",
    response_model=MutationReceipt,
    status_code=status.HTTP_201_CREATED,
)
def create_evidence(
    tenant_id: UUID,
    work_id: UUID,
    body: CreateEvidenceRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> MutationReceipt:
    """Create and pin new evidence from an uploaded same-tenant file."""
    _check_tenant_match(tenant_id, tenant_context)
    req_id = getattr(request.state, "request_id", None) or "req-ctrl-ev-create"
    service = CustomerControlWorkService(db)
    return service.create_evidence(
        principal,
        tenant_context,
        work_id,
        body,
        request_id=req_id,
    )


@work_router.post(
    "/{work_id}/links",
    response_model=MutationReceipt,
    status_code=status.HTTP_201_CREATED,
)
def create_link(
    tenant_id: UUID,
    work_id: UUID,
    body: CreateLinkRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> MutationReceipt:
    """Deliberately reuse an existing same-tenant evidence revision snapshot."""
    _check_tenant_match(tenant_id, tenant_context)
    req_id = getattr(request.state, "request_id", None) or "req-ctrl-link-reuse"
    service = CustomerControlWorkService(db)
    return service.create_link(
        principal,
        tenant_context,
        work_id,
        body,
        request_id=req_id,
    )


@work_router.post(
    "/{work_id}/links/{link_id}/reviews",
    response_model=MutationReceipt,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    tenant_id: UUID,
    work_id: UUID,
    link_id: UUID,
    body: CreateReviewRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> MutationReceipt:
    """Record an evidence suitability review decision (ACCEPTED or REJECTED)."""
    _check_tenant_match(tenant_id, tenant_context)
    req_id = getattr(request.state, "request_id", None) or "req-ctrl-review"
    service = CustomerControlWorkService(db)
    return service.create_review(
        principal,
        tenant_context,
        work_id,
        link_id,
        body,
        request_id=req_id,
    )


@work_router.get(
    "/{work_id}/history",
    response_model=WorkHistoryResponse,
    status_code=status.HTTP_200_OK,
)
def get_history(
    tenant_id: UUID,
    work_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> WorkHistoryResponse:
    """Read revision-ordered event history for a control work item."""
    _check_tenant_match(tenant_id, tenant_context)
    service = CustomerControlWorkService(db)
    return service.get_history(
        principal,
        tenant_context,
        work_id,
        limit=limit,
        offset=offset,
    )


@work_router.get(
    "/{work_id}/links/{link_id}/files/{file_id}",
    status_code=status.HTTP_200_OK,
)
def download_pinned_file(
    tenant_id: UUID,
    work_id: UUID,
    link_id: UUID,
    file_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> FastAPIResponse:
    """Download pinned file bytes after validating exact snapshot and strict scan."""
    _check_tenant_match(tenant_id, tenant_context)
    req_id = getattr(request.state, "request_id", None) or "req-ctrl-download"
    service = CustomerControlWorkService(db)
    stored_file, file_bytes = service.download_pinned_file(
        principal,
        tenant_context,
        work_id,
        link_id,
        file_id,
        request_id=req_id,
    )

    safe_name = _sanitize_filename(stored_file.original_filename)
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_name}"',
        "Content-Length": str(len(file_bytes)),
        "Cache-Control": "no-store, no-cache, must-revalidate, private",
        "Pragma": "no-cache",
        "Vary": "Authorization",
    }
    return FastAPIResponse(
        content=file_bytes,
        media_type=stored_file.content_type or "application/octet-stream",
        headers=headers,
    )
