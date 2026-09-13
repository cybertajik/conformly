from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from conformly.assets import service
from conformly.assets.models import Asset, AssetClassification, AssetStatus, AssetType
from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError
from conformly.db.session import get_db
from conformly.entitlements.dependencies import require_module

router = APIRouter(
    prefix="/v1/tenants/{tenant_id}/assets",
    tags=["assets"],
    dependencies=[Depends(require_module("assets"))],
)


class AssetResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    asset_type: AssetType
    classification: AssetClassification
    description: str | None
    owner_user_id: UUID | None
    control_id: UUID | None = None
    finding_id: UUID | None = None
    legal_entity_id: UUID | None = None
    business_unit_id: UUID | None = None
    status: AssetStatus
    last_reviewed_at: datetime | None = None
    next_review_due_at: datetime | None = None
    created_at: datetime


def _to_asset_response(a: Asset) -> AssetResponse:
    desc = service.resolve_asset_description(a)
    return AssetResponse(
        id=a.id,
        tenant_id=a.tenant_id,
        name=a.name,
        asset_type=a.asset_type,
        classification=a.classification,
        description=desc,
        owner_user_id=a.owner_user_id,
        control_id=a.control_id,
        finding_id=a.finding_id,
        legal_entity_id=a.legal_entity_id,
        business_unit_id=a.business_unit_id,
        status=a.status,
        last_reviewed_at=a.last_reviewed_at,
        next_review_due_at=a.next_review_due_at,
        created_at=a.created_at,
    )


class AssetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    asset_type: AssetType = Field(default=AssetType.SOFTWARE)
    classification: AssetClassification = Field(default=AssetClassification.INTERNAL)
    description: str | None = Field(default=None)
    owner_user_id: UUID | None = Field(default=None)
    control_id: UUID | None = Field(default=None)
    finding_id: UUID | None = Field(default=None)
    legal_entity_id: UUID | None = Field(default=None)
    business_unit_id: UUID | None = Field(default=None)


class AssetUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    asset_type: AssetType = Field(default=AssetType.SOFTWARE)
    classification: AssetClassification = Field(default=AssetClassification.INTERNAL)
    description: str | None = Field(default=None)
    owner_user_id: UUID | None = Field(default=None)
    status: AssetStatus = Field(default=AssetStatus.ACTIVE)
    control_id: UUID | None = Field(default=None)
    finding_id: UUID | None = Field(default=None)
    legal_entity_id: UUID | None = Field(default=None)
    business_unit_id: UUID | None = Field(default=None)


class AssetReviewRequest(BaseModel):
    next_review_due_at: datetime | None = Field(default=None)


@router.get("", response_model=list[AssetResponse])
def list_assets_endpoint(
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
    asset_type: AssetType | None = None,
    classification: AssetClassification | None = None,
    status_filter: AssetStatus | None = None,
) -> list[AssetResponse]:
    request_id = getattr(request.state, "request_id", "req-asset-list")
    try:
        assets = service.list_assets(
            database,
            principal,
            tenant_context,
            request_id,
            asset_type=asset_type,
            classification=classification,
            status=status_filter,
        )
        return [_to_asset_response(a) for a in assets]
    except AuthorizationDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing asset:read capability"
        )


@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset_endpoint(
    asset_id: UUID,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> AssetResponse:
    request_id = getattr(request.state, "request_id", "req-asset-get")
    try:
        asset = service.get_asset(database, principal, tenant_context, asset_id, request_id)
        return _to_asset_response(asset)
    except AuthorizationDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing asset:read capability"
        )
    except service.AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset_endpoint(
    payload: AssetCreateRequest,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> AssetResponse:
    request_id = getattr(request.state, "request_id", "req-asset-create")
    try:
        asset = service.create_asset(
            database,
            principal,
            tenant_context,
            name=payload.name,
            asset_type=payload.asset_type,
            classification=payload.classification,
            description=payload.description,
            owner_user_id=payload.owner_user_id,
            request_id=request_id,
            control_id=payload.control_id,
            finding_id=payload.finding_id,
            legal_entity_id=payload.legal_entity_id,
            business_unit_id=payload.business_unit_id,
        )
        database.commit()
        return _to_asset_response(asset)
    except AuthorizationDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: missing asset:manage capability",
        )


@router.put("/{asset_id}", response_model=AssetResponse)
def update_asset_endpoint(
    asset_id: UUID,
    payload: AssetUpdateRequest,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> AssetResponse:
    request_id = getattr(request.state, "request_id", "req-asset-update")
    try:
        asset = service.update_asset(
            database,
            principal,
            tenant_context,
            asset_id=asset_id,
            name=payload.name,
            asset_type=payload.asset_type,
            classification=payload.classification,
            description=payload.description,
            owner_user_id=payload.owner_user_id,
            status=payload.status,
            control_id=payload.control_id,
            finding_id=payload.finding_id,
            request_id=request_id,
            legal_entity_id=payload.legal_entity_id,
            business_unit_id=payload.business_unit_id,
        )
        database.commit()
        return _to_asset_response(asset)
    except AuthorizationDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: missing asset:manage capability",
        )
    except service.AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{asset_id}/review", response_model=AssetResponse)
def complete_asset_review_endpoint(
    asset_id: UUID,
    payload: AssetReviewRequest,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> AssetResponse:
    request_id = getattr(request.state, "request_id", "req-asset-review")
    try:
        asset = service.complete_asset_review(
            database,
            principal,
            tenant_context,
            asset_id=asset_id,
            next_review_due_at=payload.next_review_due_at,
            request_id=request_id,
        )
        database.commit()
        return _to_asset_response(asset)
    except AuthorizationDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: missing asset:manage capability",
        )
    except service.AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset_endpoint(
    asset_id: UUID,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> None:
    request_id = getattr(request.state, "request_id", "req-asset-delete")
    try:
        service.delete_asset(database, principal, tenant_context, asset_id, request_id)
        database.commit()
    except AuthorizationDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: missing asset:manage capability",
        )
    except service.AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
