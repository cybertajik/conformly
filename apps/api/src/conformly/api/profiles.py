"""FastAPI routes for public compliance profiles and trust centers.

Public endpoints provide projected, non-confidential compliance profiles with ETag caching.
Authenticated endpoints provide tenant administration of branding, credentials, and publication.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError
from conformly.db.session import get_db
from conformly.entitlements.dependencies import require_module
from conformly.profiles.service import (
    PublicCredentialInvalidSourceError,
    PublicCredentialNotFoundError,
    PublicProfileConcurrencyConflictError,
    PublicProfileInvalidSlugError,
    PublicProfileNotFoundError,
    PublicProfileService,
    PublicProfileSlugConflictError,
)

public_profiles_router = APIRouter(
    prefix="/v1/public/profiles",
    tags=["public_profiles"],
)

tenant_profiles_router = APIRouter(
    prefix="/v1/tenants/{tenant_id}/public-profile",
    tags=["public_profiles"],
    dependencies=[Depends(require_module("profiles"))],
)


def get_profile_service(
    database: Annotated[Session, Depends(get_db)],
) -> PublicProfileService:
    return PublicProfileService(database)


# ── Pydantic Request & Response Schemas ─────────────────────────────────────


class PublicCredentialItem(BaseModel):
    id: UUID
    credential_type: str
    title: str
    issuer_name: str
    scope_description: str
    issued_at: datetime
    valid_until: datetime | None = None
    status: str
    verification_url: str | None = None
    source_certificate_id: UUID | None = None
    display_order: int


class PublicStatementItem(BaseModel):
    id: UUID
    title: str
    statement_content: str
    display_order: int


class PublicProfileViewResponse(BaseModel):
    id: UUID
    slug: str
    display_name: str
    description: str | None = None
    logo_url: str | None = None
    website_url: str | None = None
    primary_contact_email: str | None = None
    published_at: datetime | None = None
    credentials: list[PublicCredentialItem]
    statements: list[PublicStatementItem]
    conformly_verified: bool
    disclaimer: str


class PublicCredentialDetailResponse(BaseModel):
    id: UUID
    profile_id: UUID
    tenant_id: UUID
    credential_type: str
    title: str
    issuer_name: str
    scope_description: str
    issued_at: datetime
    valid_until: datetime | None = None
    status: str
    verification_url: str | None = None
    source_certificate_id: UUID | None = None
    is_publicly_visible: bool
    display_order: int
    created_at: datetime
    updated_at: datetime


class PublicStatementDetailResponse(BaseModel):
    id: UUID
    profile_id: UUID
    tenant_id: UUID
    title: str
    statement_content: str
    display_order: int
    is_publicly_visible: bool
    created_at: datetime
    updated_at: datetime


class TenantProfileDetailResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    slug: str
    display_name: str
    description: str | None = None
    logo_url: str | None = None
    website_url: str | None = None
    primary_contact_email: str | None = None
    is_published: bool
    published_at: datetime | None = None
    version: int
    created_at: datetime
    updated_at: datetime
    credentials: list[PublicCredentialDetailResponse]
    statements: list[PublicStatementDetailResponse]


class ConfigureProfileRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    logo_url: str | None = Field(default=None, max_length=1024)
    website_url: str | None = Field(default=None, max_length=1024)
    primary_contact_email: str | None = Field(default=None, max_length=255)
    slug: str | None = Field(default=None, min_length=3, max_length=64)
    expected_version: int = Field(ge=1)


class LifecycleActionRequest(BaseModel):
    expected_version: int = Field(ge=1)


class CreateThirdPartyCredentialRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    issuer_name: str = Field(min_length=2, max_length=255)
    scope_description: str = Field(min_length=5, max_length=5000)
    issued_at: datetime
    valid_until: datetime | None = None
    verification_url: str | None = Field(default=None, max_length=1024)
    is_publicly_visible: bool = True
    display_order: int = Field(default=0, ge=0)


class LinkPreAuditCredentialRequest(BaseModel):
    certificate_id: UUID
    is_publicly_visible: bool = True
    display_order: int = Field(default=0, ge=0)


class UpdateCredentialRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    issuer_name: str = Field(min_length=2, max_length=255)
    scope_description: str = Field(min_length=5, max_length=5000)
    valid_until: datetime | None = None
    verification_url: str | None = Field(default=None, max_length=1024)
    is_publicly_visible: bool = True
    display_order: int = Field(default=0, ge=0)


class RevokeCredentialRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class CreateStatementRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    statement_content: str = Field(min_length=5, max_length=10000)
    display_order: int = Field(default=0, ge=0)
    is_publicly_visible: bool = True


# ── Public Endpoints ─────────────────────────────────────────────────────────


@public_profiles_router.get(
    "/{slug}",
    response_model=PublicProfileViewResponse,
    responses={
        200: {"description": "Public profile projection."},
        304: {"description": "Profile unchanged (ETag matched)."},
        404: {"description": "Profile not found or unpublished."},
    },
)
def get_public_profile(
    slug: str,
    response: Response,
    service: Annotated[PublicProfileService, Depends(get_profile_service)],
    if_none_match: Annotated[str | None, Header()] = None,
) -> Any:
    """Fetch an explicitly published public profile view with ETag caching."""
    try:
        data, etag = service.get_public_profile_view(slug)
    except PublicProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public compliance profile not found.",
        ) from exc

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=300, must-revalidate"

    if if_none_match and if_none_match.strip() == etag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=response.headers)

    return data


# ── Authenticated Tenant Endpoints ───────────────────────────────────────────


@tenant_profiles_router.get(
    "",
    response_model=TenantProfileDetailResponse,
)
def get_tenant_public_profile(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    context: CurrentTenant,
    service: Annotated[PublicProfileService, Depends(get_profile_service)],
) -> Any:
    """Get or initialize the tenant's public profile draft."""
    if context.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied."
        )

    try:
        return service.get_or_create_tenant_profile(tenant_id, principal, context)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@tenant_profiles_router.put(
    "",
    response_model=TenantProfileDetailResponse,
)
def configure_tenant_public_profile(
    tenant_id: UUID,
    request: ConfigureProfileRequest,
    principal: CurrentPrincipal,
    context: CurrentTenant,
    service: Annotated[PublicProfileService, Depends(get_profile_service)],
) -> Any:
    """Update public profile configuration attributes and slug."""
    if context.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied."
        )

    try:
        return service.configure_profile(
            tenant_id=tenant_id,
            display_name=request.display_name,
            description=request.description,
            logo_url=request.logo_url,
            website_url=request.website_url,
            primary_contact_email=request.primary_contact_email,
            slug=request.slug,
            expected_version=request.expected_version,
            principal=principal,
            context=context,
        )
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except PublicProfileSlugConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except PublicProfileInvalidSlugError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except PublicProfileConcurrencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@tenant_profiles_router.post(
    "/publish",
    response_model=TenantProfileDetailResponse,
)
def publish_tenant_public_profile(
    tenant_id: UUID,
    request: LifecycleActionRequest,
    principal: CurrentPrincipal,
    context: CurrentTenant,
    service: Annotated[PublicProfileService, Depends(get_profile_service)],
) -> Any:
    """Publish profile to public endpoints."""
    if context.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied."
        )

    try:
        return service.publish_profile(
            tenant_id=tenant_id,
            expected_version=request.expected_version,
            principal=principal,
            context=context,
        )
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except PublicProfileConcurrencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@tenant_profiles_router.post(
    "/unpublish",
    response_model=TenantProfileDetailResponse,
)
def unpublish_tenant_public_profile(
    tenant_id: UUID,
    request: LifecycleActionRequest,
    principal: CurrentPrincipal,
    context: CurrentTenant,
    service: Annotated[PublicProfileService, Depends(get_profile_service)],
) -> Any:
    """Unpublish profile, immediately hiding it from public endpoints."""
    if context.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied."
        )

    try:
        return service.unpublish_profile(
            tenant_id=tenant_id,
            expected_version=request.expected_version,
            principal=principal,
            context=context,
        )
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except PublicProfileConcurrencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@tenant_profiles_router.post(
    "/credentials",
    response_model=PublicCredentialDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_third_party_credential(
    tenant_id: UUID,
    request: CreateThirdPartyCredentialRequest,
    principal: CurrentPrincipal,
    context: CurrentTenant,
    service: Annotated[PublicProfileService, Depends(get_profile_service)],
) -> Any:
    """Add a customer-supplied third-party certification."""
    if context.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied."
        )

    try:
        return service.add_third_party_credential(
            tenant_id=tenant_id,
            title=request.title,
            issuer_name=request.issuer_name,
            scope_description=request.scope_description,
            issued_at=request.issued_at,
            valid_until=request.valid_until,
            verification_url=request.verification_url,
            is_publicly_visible=request.is_publicly_visible,
            display_order=request.display_order,
            principal=principal,
            context=context,
        )
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@tenant_profiles_router.post(
    "/credentials/link-preaudit",
    response_model=PublicCredentialDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def link_preaudit_credential(
    tenant_id: UUID,
    request: LinkPreAuditCredentialRequest,
    principal: CurrentPrincipal,
    context: CurrentTenant,
    service: Annotated[PublicProfileService, Depends(get_profile_service)],
) -> Any:
    """Project an existing active PreAuditCertificate as a public readiness badge."""
    if context.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied."
        )

    try:
        return service.link_preaudit_credential(
            tenant_id=tenant_id,
            certificate_id=request.certificate_id,
            is_publicly_visible=request.is_publicly_visible,
            display_order=request.display_order,
            principal=principal,
            context=context,
        )
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except PublicCredentialInvalidSourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@tenant_profiles_router.put(
    "/credentials/{credential_id}",
    response_model=PublicCredentialDetailResponse,
)
def update_credential(
    tenant_id: UUID,
    credential_id: UUID,
    request: UpdateCredentialRequest,
    principal: CurrentPrincipal,
    context: CurrentTenant,
    service: Annotated[PublicProfileService, Depends(get_profile_service)],
) -> Any:
    """Update public credential attributes."""
    if context.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied."
        )

    try:
        return service.update_credential(
            tenant_id=tenant_id,
            credential_id=credential_id,
            title=request.title,
            issuer_name=request.issuer_name,
            scope_description=request.scope_description,
            valid_until=request.valid_until,
            verification_url=request.verification_url,
            is_publicly_visible=request.is_publicly_visible,
            display_order=request.display_order,
            principal=principal,
            context=context,
        )
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except PublicCredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@tenant_profiles_router.post(
    "/credentials/{credential_id}/revoke",
    response_model=PublicCredentialDetailResponse,
)
def revoke_credential(
    tenant_id: UUID,
    credential_id: UUID,
    request: RevokeCredentialRequest,
    principal: CurrentPrincipal,
    context: CurrentTenant,
    service: Annotated[PublicProfileService, Depends(get_profile_service)],
) -> Any:
    """Revoke a public credential."""
    if context.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied."
        )

    try:
        return service.revoke_credential(
            tenant_id=tenant_id,
            credential_id=credential_id,
            reason=request.reason,
            principal=principal,
            context=context,
        )
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except PublicCredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@tenant_profiles_router.delete(
    "/credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_credential(
    tenant_id: UUID,
    credential_id: UUID,
    principal: CurrentPrincipal,
    context: CurrentTenant,
    service: Annotated[PublicProfileService, Depends(get_profile_service)],
) -> Response:
    """Delete a public credential."""
    if context.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied."
        )

    try:
        service.delete_credential(
            tenant_id=tenant_id,
            credential_id=credential_id,
            principal=principal,
            context=context,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except PublicCredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@tenant_profiles_router.post(
    "/statements",
    response_model=PublicStatementDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_statement(
    tenant_id: UUID,
    request: CreateStatementRequest,
    principal: CurrentPrincipal,
    context: CurrentTenant,
    service: Annotated[PublicProfileService, Depends(get_profile_service)],
) -> Any:
    """Add a public compliance statement."""
    if context.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied."
        )

    try:
        return service.add_statement(
            tenant_id=tenant_id,
            title=request.title,
            statement_content=request.statement_content,
            display_order=request.display_order,
            is_publicly_visible=request.is_publicly_visible,
            principal=principal,
            context=context,
        )
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@tenant_profiles_router.delete(
    "/statements/{statement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_statement(
    tenant_id: UUID,
    statement_id: UUID,
    principal: CurrentPrincipal,
    context: CurrentTenant,
    service: Annotated[PublicProfileService, Depends(get_profile_service)],
) -> Response:
    """Delete a public compliance statement."""
    if context.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied."
        )

    try:
        service.delete_statement(
            tenant_id=tenant_id,
            statement_id=statement_id,
            principal=principal,
            context=context,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
