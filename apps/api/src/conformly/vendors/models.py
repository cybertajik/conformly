from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class VendorCriticality(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VendorStatus(StrEnum):
    ACTIVE = "active"
    UNDER_REVIEW = "under_review"
    TERMINATED = "terminated"


class Vendor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A third-party supplier, vendor, or subprocessor used by a tenant."""

    __tablename__ = "vendors"
    __table_args__ = (
        Index("ix_vendors_tenant_id", "tenant_id"),
        Index("ix_vendors_tenant_criticality", "tenant_id", "criticality"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    service_description: Mapped[str] = mapped_column(Text, nullable=False)
    criticality: Mapped[VendorCriticality] = mapped_column(
        Enum(VendorCriticality, native_enum=False, length=32),
        default=VendorCriticality.MEDIUM,
        nullable=False,
    )
    data_classification_accessed: Mapped[str] = mapped_column(
        String(50), default="Confidential", nullable=False
    )
    country_residency: Mapped[str] = mapped_column(String(50), default="DE", nullable=False)
    dpa_signed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    security_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    status: Mapped[VendorStatus] = mapped_column(
        Enum(VendorStatus, native_enum=False, length=32),
        default=VendorStatus.ACTIVE,
        nullable=False,
    )
