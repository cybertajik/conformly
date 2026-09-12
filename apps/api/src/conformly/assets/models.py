from enum import StrEnum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, String, Text
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
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[AssetStatus] = mapped_column(
        Enum(AssetStatus, native_enum=False, length=32),
        default=AssetStatus.ACTIVE,
        nullable=False,
    )
