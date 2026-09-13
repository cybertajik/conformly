from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.assets.models import Asset, AssetClassification, AssetStatus, AssetType
from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize, authorize_resource
from conformly.authz.roles import Capability
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.crypto.types import EncryptionContext


class AssetNotFoundError(Exception):
    """Raised when an asset is not found in the tenant."""


def resolve_asset_description(
    asset: Asset,
    codec: EncryptedFieldCodec | None = None,
) -> str | None:
    """Return decrypted description if encrypted, or plaintext description."""
    if asset.encrypted_description is not None:
        codec = codec or get_encrypted_field_codec()
        context = EncryptionContext(
            tenant_id=asset.tenant_id,
            resource_type="asset",
            resource_id=str(asset.id),
            field_name="description",
        )
        return codec.decrypt_text(asset.encrypted_description, context)
    return asset.description


def list_assets(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    request_id: str,
    asset_type: AssetType | None = None,
    classification: AssetClassification | None = None,
    status: AssetStatus | None = None,
) -> list[Asset]:
    authorize(principal, tenant_context, Capability.ASSET_READ)
    stmt = select(Asset).where(Asset.tenant_id == tenant_context.tenant_id)
    if tenant_context.legal_entity_id is not None:
        stmt = stmt.where(Asset.legal_entity_id == tenant_context.legal_entity_id)
    if tenant_context.business_unit_id is not None:
        stmt = stmt.where(Asset.business_unit_id == tenant_context.business_unit_id)
    if asset_type is not None:
        stmt = stmt.where(Asset.asset_type == asset_type)
    if classification is not None:
        stmt = stmt.where(Asset.classification == classification)
    if status is not None:
        stmt = stmt.where(Asset.status == status)
    stmt = stmt.order_by(Asset.created_at.desc())
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


def get_asset(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    asset_id: UUID,
    request_id: str,
) -> Asset:
    authorize(principal, tenant_context, Capability.ASSET_READ)
    asset = database.scalar(
        select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_context.tenant_id)
    )
    if asset is None:
        raise AssetNotFoundError("Asset not found in tenant")
    authorize_resource(
        principal,
        tenant_context,
        Capability.ASSET_READ,
        legal_entity_id=asset.legal_entity_id,
        business_unit_id=asset.business_unit_id,
    )
    return asset


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
    control_id: UUID | None = None,
    finding_id: UUID | None = None,
    legal_entity_id: UUID | None = None,
    business_unit_id: UUID | None = None,
    codec: EncryptedFieldCodec | None = None,
) -> Asset:
    effective_legal_entity_id = tenant_context.legal_entity_id or legal_entity_id
    effective_business_unit_id = tenant_context.business_unit_id or business_unit_id
    authorize(principal, tenant_context, Capability.ASSET_MANAGE)
    authorize_resource(
        principal,
        tenant_context,
        Capability.ASSET_MANAGE,
        legal_entity_id=effective_legal_entity_id,
        business_unit_id=effective_business_unit_id,
    )
    asset_id = uuid4()
    encrypted_desc = None
    plain_desc = None

    if description:
        clean_desc = description.strip()
        if classification == AssetClassification.RESTRICTED:
            codec = codec or get_encrypted_field_codec()
            context = EncryptionContext(
                tenant_id=tenant_context.tenant_id,
                resource_type="asset",
                resource_id=str(asset_id),
                field_name="description",
            )
            encrypted_desc = codec.encrypt_text(clean_desc, context)
            plain_desc = None
        else:
            plain_desc = clean_desc

    asset = Asset(
        id=asset_id,
        tenant_id=tenant_context.tenant_id,
        name=name.strip(),
        asset_type=asset_type,
        classification=classification,
        description=plain_desc,
        encrypted_description=encrypted_desc,
        owner_user_id=owner_user_id,
        control_id=control_id,
        finding_id=finding_id,
        legal_entity_id=effective_legal_entity_id,
        business_unit_id=effective_business_unit_id,
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
        metadata={
            "name": asset.name,
            "asset_type": asset.asset_type.value,
            "classification": asset.classification.value,
        },
    )
    return asset


def update_asset(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    asset_id: UUID,
    name: str,
    asset_type: AssetType,
    classification: AssetClassification,
    description: str | None,
    owner_user_id: UUID | None,
    status: AssetStatus,
    control_id: UUID | None,
    finding_id: UUID | None,
    request_id: str,
    legal_entity_id: UUID | None = None,
    business_unit_id: UUID | None = None,
    codec: EncryptedFieldCodec | None = None,
) -> Asset:
    authorize(principal, tenant_context, Capability.ASSET_MANAGE)
    asset = get_asset(database, principal, tenant_context, asset_id, request_id)
    authorize_resource(
        principal,
        tenant_context,
        Capability.ASSET_MANAGE,
        legal_entity_id=asset.legal_entity_id,
        business_unit_id=asset.business_unit_id,
    )

    asset.name = name.strip()
    asset.asset_type = asset_type
    asset.classification = classification
    asset.owner_user_id = owner_user_id
    asset.status = status
    asset.control_id = control_id
    asset.finding_id = finding_id
    if legal_entity_id is not None:
        asset.legal_entity_id = legal_entity_id
    if business_unit_id is not None:
        asset.business_unit_id = business_unit_id

    if description:
        clean_desc = description.strip()
        if classification == AssetClassification.RESTRICTED:
            codec = codec or get_encrypted_field_codec()
            context = EncryptionContext(
                tenant_id=tenant_context.tenant_id,
                resource_type="asset",
                resource_id=str(asset.id),
                field_name="description",
            )
            asset.encrypted_description = codec.encrypt_text(clean_desc, context)
            asset.description = None
        else:
            asset.encrypted_description = None
            asset.description = clean_desc
    else:
        asset.encrypted_description = None
        asset.description = None

    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="asset.update",
        resource_type="asset",
        resource_id=str(asset.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"name": asset.name, "status": asset.status.value},
    )
    return asset


def complete_asset_review(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    asset_id: UUID,
    next_review_due_at: datetime | None,
    request_id: str,
) -> Asset:
    authorize(principal, tenant_context, Capability.ASSET_MANAGE)
    asset = get_asset(database, principal, tenant_context, asset_id, request_id)
    authorize_resource(
        principal,
        tenant_context,
        Capability.ASSET_MANAGE,
        legal_entity_id=asset.legal_entity_id,
        business_unit_id=asset.business_unit_id,
    )
    now = datetime.now(UTC)
    asset.last_reviewed_at = now
    asset.next_review_due_at = next_review_due_at
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="asset.review.complete",
        resource_type="asset",
        resource_id=str(asset.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"last_reviewed_at": now.isoformat()},
    )
    return asset


def delete_asset(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    asset_id: UUID,
    request_id: str,
) -> None:
    authorize(principal, tenant_context, Capability.ASSET_MANAGE)
    asset = get_asset(database, principal, tenant_context, asset_id, request_id)
    authorize_resource(
        principal,
        tenant_context,
        Capability.ASSET_MANAGE,
        legal_entity_id=asset.legal_entity_id,
        business_unit_id=asset.business_unit_id,
    )
    database.delete(asset)
    database.flush()
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="asset.delete",
        resource_type="asset",
        resource_id=str(asset_id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"name": asset.name},
    )
