"""FastAPI routes for anonymous whistleblower reporting and internal case handling.

Public endpoints provide zero-knowledge anonymous intake and case tracking.
Authenticated endpoints are strictly guarded by WHISTLEBLOWER_* capabilities.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError, authorize
from conformly.authz.roles import Capability
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.db.session import get_db
from conformly.entitlements.dependencies import require_module
from conformly.whistleblower.models import WhistleblowerCaseStatus
from conformly.whistleblower.rate_limit import (
    WhistleblowerRateLimitExceeded,
    anonymous_whistleblower_rate_limiter,
)
from conformly.whistleblower.service import (
    WhistleblowerCaseNotFoundError,
    WhistleblowerClosedCaseError,
    WhistleblowerConcurrencyConflictError,
    WhistleblowerInvalidHandlerError,
    WhistleblowerInvalidTransitionError,
    WhistleblowerPortalNotFoundError,
    WhistleblowerService,
    WhistleblowerSlugConflictError,
    WhistleblowerUnauthorizedError,
)

public_whistleblower_router = APIRouter(
    prefix="/v1/public/whistleblower",
    tags=["public_whistleblower"],
)

whistleblower_router = APIRouter(
    prefix="/v1/tenants/{tenant_id}/whistleblower",
    tags=["whistleblower"],
    dependencies=[Depends(require_module("whistleblower"))],
)


def get_whistleblower_service(
    database: Annotated[Session, Depends(get_db)],
    codec: Annotated[EncryptedFieldCodec, Depends(get_encrypted_field_codec)],
) -> WhistleblowerService:
    return WhistleblowerService(database, codec=codec)


# ── Pydantic Schemas ────────────────────────────────────────────────────────


class PublicPortalResponse(BaseModel):
    id: UUID
    slug: str
    title: str
    welcome_text: str
    is_active: bool


class SubmitReportRequest(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1)


class SubmitReportResponse(BaseModel):
    public_case_id: str
    return_secret: str
    portal_title: str
    created_at: datetime


class AccessCaseRequest(BaseModel):
    public_case_id: str = Field(min_length=1)
    return_secret: str = Field(min_length=1)


class PublicMessageResponse(BaseModel):
    id: str
    case_id: str
    sender_type: str
    body: str
    created_at: str


class PublicCaseResponse(BaseModel):
    public_case_id: str
    status: str
    category: str
    title: str
    closed_at: datetime | None
    created_at: datetime
    messages: list[PublicMessageResponse]


class AddReporterMessageRequest(BaseModel):
    public_case_id: str = Field(min_length=1)
    return_secret: str = Field(min_length=1)
    body: str = Field(min_length=1)


class SetupPortalRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    welcome_text: str = Field(min_length=1)
    is_active: bool = True
    expected_version: int | None = None


class PortalResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    slug: str
    title: str
    welcome_text: str
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class CaseSummaryResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    portal_id: UUID
    public_case_id: str
    status: str
    category: str
    title: str
    summary: str | None = None
    closed_at: datetime | None = None
    closed_reason: str | None = None
    version: int
    messages_count: int = 0
    created_at: datetime
    updated_at: datetime


class CaseListResponse(BaseModel):
    items: list[CaseSummaryResponse]
    total: int


class CaseAssignmentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    case_id: UUID
    handler_user_id: UUID
    assigned_by_user_id: UUID
    assigned_at: datetime


class CaseDetailResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    portal_id: UUID
    public_case_id: str
    status: str
    category: str
    title: str
    summary: str | None = None
    closed_at: datetime | None = None
    closed_reason: str | None = None
    version: int
    messages: list[PublicMessageResponse]
    assignments: list[CaseAssignmentResponse]
    created_at: datetime
    updated_at: datetime


class HandlerMessageRequest(BaseModel):
    body: str = Field(min_length=1)


class UpdateCaseStatusRequest(BaseModel):
    status: WhistleblowerCaseStatus
    closed_reason: str | None = None
    expected_version: int | None = None


class AssignHandlerRequest(BaseModel):
    handler_user_id: UUID


# ── Public Anonymous Endpoints ─────────────────────────────────────────────


@public_whistleblower_router.get(
    "/{slug}",
    response_model=PublicPortalResponse,
)
def get_public_portal(
    slug: str,
    svc: Annotated[WhistleblowerService, Depends(get_whistleblower_service)],
) -> PublicPortalResponse:
    try:
        portal = svc.get_public_portal(slug)
        return PublicPortalResponse(
            id=portal.id,
            slug=portal.slug,
            title=portal.title,
            welcome_text=portal.welcome_text,
            is_active=portal.is_active,
        )
    except WhistleblowerPortalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@public_whistleblower_router.post(
    "/{slug}/submit",
    response_model=SubmitReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_report(
    slug: str,
    body: SubmitReportRequest,
    svc: Annotated[WhistleblowerService, Depends(get_whistleblower_service)],
) -> SubmitReportResponse:
    try:
        anonymous_whistleblower_rate_limiter.check("submit", slug, limit=20)
        case, secret = svc.submit_report(
            slug=slug,
            category=body.category,
            title=body.title,
            summary=body.summary,
        )
        return SubmitReportResponse(
            public_case_id=case.public_case_id,
            return_secret=secret,
            portal_title=case.portal.title,
            created_at=case.created_at,
        )
    except WhistleblowerPortalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WhistleblowerRateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@public_whistleblower_router.post(
    "/{slug}/access",
    response_model=PublicCaseResponse,
)
def access_case_public(
    slug: str,
    body: AccessCaseRequest,
    svc: Annotated[WhistleblowerService, Depends(get_whistleblower_service)],
) -> PublicCaseResponse:
    try:
        anonymous_whistleblower_rate_limiter.check(
            "access", f"{slug}:{body.public_case_id}", limit=10
        )
        case, messages = svc.access_case_public(
            slug=slug,
            public_case_id=body.public_case_id,
            return_secret=body.return_secret,
        )
        category, title = svc.decrypt_case_metadata(case)
        return PublicCaseResponse(
            public_case_id=case.public_case_id,
            status=case.status.value,
            category=category,
            title=title,
            closed_at=case.closed_at,
            created_at=case.created_at,
            messages=[PublicMessageResponse(**m) for m in messages],
        )
    except WhistleblowerPortalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WhistleblowerUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except WhistleblowerRateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc


@public_whistleblower_router.post(
    "/{slug}/messages",
    response_model=PublicMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_reporter_message(
    slug: str,
    body: AddReporterMessageRequest,
    svc: Annotated[WhistleblowerService, Depends(get_whistleblower_service)],
) -> PublicMessageResponse:
    try:
        anonymous_whistleblower_rate_limiter.check(
            "message", f"{slug}:{body.public_case_id}", limit=20
        )
        msg = svc.add_reporter_message(
            slug=slug,
            public_case_id=body.public_case_id,
            return_secret=body.return_secret,
            body=body.body,
        )
        return PublicMessageResponse(
            id=str(msg.id),
            case_id=str(msg.case_id),
            sender_type=msg.sender_type.value,
            body=body.body,
            created_at=msg.created_at.isoformat(),
        )
    except WhistleblowerRateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except WhistleblowerPortalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WhistleblowerUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except WhistleblowerClosedCaseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


# ── Authenticated Handler Endpoints ────────────────────────────────────────


@whistleblower_router.get(
    "/portal",
    response_model=PortalResponse,
)
def get_tenant_portal(
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[WhistleblowerService, Depends(get_whistleblower_service)],
) -> PortalResponse:
    try:
        authorize(principal, tenant_ctx, Capability.WHISTLEBLOWER_CASE_READ)
    except AuthorizationDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="whistleblower access denied",
        ) from exc

    portal = svc.get_tenant_portal(tenant_ctx)
    if portal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="whistleblower portal not configured",
        )
    return PortalResponse(
        id=portal.id,
        tenant_id=portal.tenant_id,
        slug=portal.slug,
        title=portal.title,
        welcome_text=portal.welcome_text,
        is_active=portal.is_active,
        version=portal.version,
        created_at=portal.created_at,
        updated_at=portal.updated_at,
    )


@whistleblower_router.put(
    "/portal",
    response_model=PortalResponse,
)
def setup_or_update_portal(
    body: SetupPortalRequest,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[WhistleblowerService, Depends(get_whistleblower_service)],
) -> PortalResponse:
    try:
        authorize(principal, tenant_ctx, Capability.WHISTLEBLOWER_PORTAL_MANAGE)
    except AuthorizationDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="whistleblower portal management denied",
        ) from exc

    try:
        portal = svc.setup_or_update_portal(
            tenant_context=tenant_ctx,
            slug=body.slug,
            title=body.title,
            welcome_text=body.welcome_text,
            is_active=body.is_active,
            expected_version=body.expected_version,
        )
        return PortalResponse(
            id=portal.id,
            tenant_id=portal.tenant_id,
            slug=portal.slug,
            title=portal.title,
            welcome_text=portal.welcome_text,
            is_active=portal.is_active,
            version=portal.version,
            created_at=portal.created_at,
            updated_at=portal.updated_at,
        )
    except WhistleblowerSlugConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WhistleblowerConcurrencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@whistleblower_router.get(
    "/cases",
    response_model=CaseListResponse,
)
def list_cases(
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[WhistleblowerService, Depends(get_whistleblower_service)],
    case_status: Annotated[WhistleblowerCaseStatus | None, Query(alias="status")] = None,
    category: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CaseListResponse:
    try:
        authorize(principal, tenant_ctx, Capability.WHISTLEBLOWER_CASE_READ)
    except AuthorizationDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="whistleblower case access denied",
        ) from exc

    cases, total = svc.list_cases(
        tenant_context=tenant_ctx,
        status=case_status,
        category=category,
        limit=limit,
        offset=offset,
    )
    items = []
    for case in cases:
        decrypted_category, decrypted_title = svc.decrypt_case_metadata(case)
        items.append(
            CaseSummaryResponse(
                id=case.id,
                tenant_id=case.tenant_id,
                portal_id=case.portal_id,
                public_case_id=case.public_case_id,
                status=case.status.value,
                category=decrypted_category,
                title=decrypted_title,
                summary=None,
                closed_at=case.closed_at,
                closed_reason=case.closed_reason,
                version=case.version,
                messages_count=len(case.messages),
                created_at=case.created_at,
                updated_at=case.updated_at,
            )
        )
    return CaseListResponse(items=items, total=total)


@whistleblower_router.get(
    "/cases/{case_id}",
    response_model=CaseDetailResponse,
)
def get_case_detail(
    case_id: UUID,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[WhistleblowerService, Depends(get_whistleblower_service)],
) -> CaseDetailResponse:
    try:
        authorize(principal, tenant_ctx, Capability.WHISTLEBLOWER_CASE_READ)
    except AuthorizationDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="whistleblower case access denied",
        ) from exc

    try:
        case, summary, messages = svc.get_case(tenant_ctx, case_id)
        category, title = svc.decrypt_case_metadata(case)
        assignments = [
            CaseAssignmentResponse(
                id=a.id,
                tenant_id=a.tenant_id,
                case_id=a.case_id,
                handler_user_id=a.handler_user_id,
                assigned_by_user_id=a.assigned_by_user_id,
                assigned_at=a.assigned_at,
            )
            for a in (case.assignments or [])
        ]
        return CaseDetailResponse(
            id=case.id,
            tenant_id=case.tenant_id,
            portal_id=case.portal_id,
            public_case_id=case.public_case_id,
            status=case.status.value,
            category=category,
            title=title,
            summary=summary,
            closed_at=case.closed_at,
            closed_reason=case.closed_reason,
            version=case.version,
            messages=[PublicMessageResponse(**m) for m in messages],
            assignments=assignments,
            created_at=case.created_at,
            updated_at=case.updated_at,
        )
    except WhistleblowerCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@whistleblower_router.post(
    "/cases/{case_id}/messages",
    response_model=PublicMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_handler_message(
    case_id: UUID,
    body: HandlerMessageRequest,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[WhistleblowerService, Depends(get_whistleblower_service)],
) -> PublicMessageResponse:
    try:
        authorize(principal, tenant_ctx, Capability.WHISTLEBLOWER_CASE_MANAGE)
    except AuthorizationDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="whistleblower case management denied",
        ) from exc

    try:
        msg = svc.add_handler_message(
            tenant_context=tenant_ctx,
            case_id=case_id,
            body=body.body,
        )
        return PublicMessageResponse(
            id=str(msg.id),
            case_id=str(msg.case_id),
            sender_type=msg.sender_type.value,
            body=body.body,
            created_at=msg.created_at.isoformat(),
        )
    except WhistleblowerCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WhistleblowerClosedCaseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@whistleblower_router.post(
    "/cases/{case_id}/status",
    response_model=CaseSummaryResponse,
)
def update_case_status(
    case_id: UUID,
    body: UpdateCaseStatusRequest,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[WhistleblowerService, Depends(get_whistleblower_service)],
) -> CaseSummaryResponse:
    try:
        authorize(principal, tenant_ctx, Capability.WHISTLEBLOWER_CASE_MANAGE)
    except AuthorizationDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="whistleblower case management denied",
        ) from exc

    try:
        case = svc.update_case_status(
            tenant_context=tenant_ctx,
            case_id=case_id,
            new_status=body.status,
            closed_reason=body.closed_reason,
            expected_version=body.expected_version,
        )
        category, title = svc.decrypt_case_metadata(case)
        return CaseSummaryResponse(
            id=case.id,
            tenant_id=case.tenant_id,
            portal_id=case.portal_id,
            public_case_id=case.public_case_id,
            status=case.status.value,
            category=category,
            title=title,
            summary=None,
            closed_at=case.closed_at,
            closed_reason=case.closed_reason,
            version=case.version,
            messages_count=len(case.messages) if case.messages else 0,
            created_at=case.created_at,
            updated_at=case.updated_at,
        )
    except WhistleblowerCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WhistleblowerConcurrencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WhistleblowerInvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@whistleblower_router.post(
    "/cases/{case_id}/assign",
    response_model=CaseAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_handler(
    case_id: UUID,
    body: AssignHandlerRequest,
    principal: CurrentPrincipal,
    tenant_ctx: CurrentTenant,
    svc: Annotated[WhistleblowerService, Depends(get_whistleblower_service)],
) -> CaseAssignmentResponse:
    try:
        authorize(principal, tenant_ctx, Capability.WHISTLEBLOWER_CASE_MANAGE)
    except AuthorizationDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="whistleblower case management denied",
        ) from exc

    try:
        assignment = svc.assign_handler(
            tenant_context=tenant_ctx,
            case_id=case_id,
            handler_user_id=body.handler_user_id,
        )
        return CaseAssignmentResponse(
            id=assignment.id,
            tenant_id=assignment.tenant_id,
            case_id=assignment.case_id,
            handler_user_id=assignment.handler_user_id,
            assigned_by_user_id=assignment.assigned_by_user_id,
            assigned_at=assignment.assigned_at,
        )
    except WhistleblowerCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WhistleblowerInvalidHandlerError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
