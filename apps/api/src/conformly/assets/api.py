from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from conformly.assets import service
from conformly.assets.models import AssetClassification, AssetStatus, AssetType
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
    status: AssetStatus
    created_at: datetime


class AssetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    asset_type: AssetType = Field(default=AssetType.SOFTWARE)
    classification: AssetClassification = Field(default=AssetClassification.INTERNAL)
    description: str | None = Field(default=None)
    owner_user_id: UUID | None = Field(default=None)


@router.get("", response_model=list[AssetResponse])
def list_assets_endpoint(
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> list[AssetResponse]:
    request_id = getattr(request.state, "request_id", "req-asset-list")
    try:
        assets = service.list_assets(database, principal, tenant_context, request_id)
        return [
            AssetResponse(
                id=a.id,
                tenant_id=a.tenant_id,
                name=a.name,
                asset_type=a.asset_type,
                classification=a.classification,
                description=a.description,
                owner_user_id=a.owner_user_id,
                status=a.status,
                created_at=a.created_at,
            )
            for a in assets
        ]
    except AuthorizationDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing asset:read capability")


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
        )
        database.commit()
        return AssetResponse(
            id=asset.id,
            tenant_id=asset.tenant_id,
            name=asset.name,
            asset_type=asset.asset_type,
            classification=asset.classification,
            description=asset.description,
            owner_user_id=asset.owner_user_id,
            status=asset.status,
            created_at=asset.created_at,
        )
    except AuthorizationDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing asset:manage capability")
