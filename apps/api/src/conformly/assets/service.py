from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.assets.models import Asset, AssetClassification, AssetStatus, AssetType
from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize
from conformly.authz.roles import Capability


def list_assets(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    request_id: str,
) -> list[Asset]:
    authorize(principal, tenant_context, Capability.ASSET_READ)
    stmt = (
        select(Asset)
        .where(Asset.tenant_id == tenant_context.tenant_id)
        .order_by(Asset.created_at.desc())
    )
    assets = list(database.scalars(stmt).all())
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="asset.list",
        resource_type="asset",
        resource_id=None,
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"count": len(assets)},
    )
    return assets


def create_asset(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    name: str,
    asset_type: AssetType,
    classification: AssetClassification,
    description: str | None,
    owner_user_id: UUID | None,
    request_id: str,
) -> Asset:
    authorize(principal, tenant_context, Capability.ASSET_MANAGE)
    asset = Asset(
        tenant_id=tenant_context.tenant_id,
        name=name.strip(),
        asset_type=asset_type,
        classification=classification,
        description=description.strip() if description else None,
        owner_user_id=owner_user_id,
        status=AssetStatus.ACTIVE,
    )
    database.add(asset)
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="asset.create",
        resource_type="asset",
        resource_id=str(asset.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"name": asset.name, "asset_type": asset.asset_type.value},
    )
    return asset
