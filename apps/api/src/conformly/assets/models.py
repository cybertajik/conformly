from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AssetType(StrEnum):
    HARDWARE = "hardware"
    SOFTWARE = "software"
    DATA = "data"
    CLOUD_SERVICE = "cloud_service"
    FACILITY = "facility"
    PERSONNEL = "personnel"


class AssetClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class AssetStatus(StrEnum):
    ACTIVE = "active"
    IN_MAINTENANCE = "in_maintenance"
    DECOMMISSIONED = "decommissioned"


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An informational, hardware, software, or physical asset owned by a tenant."""

    __tablename__ = "assets"
    __table_args__ = (
        Index("ix_assets_tenant_id", "tenant_id"),
        Index("ix_assets_tenant_type", "tenant_id", "asset_type"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, native_enum=False, length=32),
        default=AssetType.SOFTWARE,
        nullable=False,
    )
    classification: Mapped[AssetClassification] = mapped_column(
        Enum(AssetClassification, native_enum=False, length=32),
        default=AssetClassification.INTERNAL,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_description: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    control_id: Mapped[UUID | None] = mapped_column(nullable=True)
    finding_id: Mapped[UUID | None] = mapped_column(nullable=True)
    legal_entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("legal_entities.id", ondelete="SET NULL"), nullable=True
    )
    business_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[AssetStatus] = mapped_column(
        Enum(AssetStatus, native_enum=False, length=32),
        default=AssetStatus.ACTIVE,
        nullable=False,
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
