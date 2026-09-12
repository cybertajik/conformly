from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReleaseState(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    RELEASED = "released"
    RETIRED = "retired"


class AdoptionStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class OverlayApplicability(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    SCOPED_OUT = "scoped_out"


class CustomControlStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class MappingType(StrEnum):
    SATISFIES = "satisfies"
    PARTIALLY_SATISFIES = "partially_satisfies"
    RELATED = "related"


class ControlEntityType(StrEnum):
    CANONICAL = "canonical"
    CUSTOM = "custom"


class Framework(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """System-scoped compliance framework catalog definition."""

    __tablename__ = "frameworks"

    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    versions: Mapped[list["FrameworkVersion"]] = relationship(
        back_populates="framework", cascade="all, delete-orphan"
    )


class FrameworkVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """System-scoped specific version of a framework subject to controlled release."""

    __tablename__ = "framework_versions"
    __table_args__ = (
        UniqueConstraint("framework_id", "version", name="uq_framework_versions_framework_version"),
        Index("ix_framework_versions_state", "release_state"),
    )

    framework_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("frameworks.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    release_state: Mapped[ReleaseState] = mapped_column(
        Enum(ReleaseState, native_enum=False, length=32),
        default=ReleaseState.DRAFT,
        nullable=False,
    )
    release_notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    legal_reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    legal_review_notes: Mapped[str | None] = mapped_column(Text)
    legal_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    approval_notes: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    framework: Mapped["Framework"] = relationship(back_populates="versions")
    controls: Mapped[list["CanonicalControl"]] = relationship(
        back_populates="framework_version",
        cascade="all, delete-orphan",
        order_by="CanonicalControl.sort_order",
    )


class CanonicalControl(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """System-scoped requirement/control defined by a framework version."""

    __tablename__ = "canonical_controls"
    __table_args__ = (
        UniqueConstraint(
            "framework_version_id", "identifier", name="uq_canonical_controls_version_identifier"
        ),
        Index("ix_canonical_controls_category", "category"),
    )

    framework_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("framework_versions.id", ondelete="RESTRICT"), nullable=False
    )
    identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    guidance: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    framework_version: Mapped["FrameworkVersion"] = relationship(back_populates="controls")


class TenantFrameworkAdoption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-scoped active or historical adoption of a framework version."""

    __tablename__ = "tenant_framework_adoptions"
    __table_args__ = (
        Index(
            "uq_tenant_framework_active_adoption",
            "tenant_id",
            "framework_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "ix_tenant_adoptions_tenant_framework",
            "tenant_id",
            "framework_id",
            "status",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    framework_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("frameworks.id", ondelete="RESTRICT"), nullable=False
    )
    framework_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("framework_versions.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[AdoptionStatus] = mapped_column(
        Enum(AdoptionStatus, native_enum=False, length=32),
        default=AdoptionStatus.ACTIVE,
        nullable=False,
    )
    adopted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    adopted_by_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    impact_analysis_acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    impact_summary_json: Mapped[str | None] = mapped_column(Text)

    overlays: Mapped[list["TenantControlOverlay"]] = relationship(
        back_populates="adoption", cascade="all, delete-orphan"
    )


class TenantControlOverlay(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-specific metadata or guidance augmenting a canonical control without mutating it."""

    __tablename__ = "tenant_control_overlays"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "adoption_id",
            "canonical_control_id",
            name="uq_tenant_control_overlays_control",
        ),
        Index("ix_tenant_control_overlays_tenant", "tenant_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    adoption_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenant_framework_adoptions.id", ondelete="CASCADE"), nullable=False
    )
    canonical_control_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("canonical_controls.id", ondelete="RESTRICT"), nullable=False
    )
    applicability: Mapped[OverlayApplicability] = mapped_column(
        Enum(OverlayApplicability, native_enum=False, length=32),
        default=OverlayApplicability.APPLICABLE,
        nullable=False,
    )
    justification: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)
    custom_guidance: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    adoption: Mapped["TenantFrameworkAdoption"] = relationship(back_populates="overlays")


class CustomControl(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-defined custom control operating outside canonical framework catalogs."""

    __tablename__ = "custom_controls"
    __table_args__ = (
        UniqueConstraint("tenant_id", "identifier", name="uq_custom_controls_tenant_identifier"),
        Index("ix_custom_controls_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    guidance: Mapped[str | None] = mapped_column(Text)
    status: Mapped[CustomControlStatus] = mapped_column(
        Enum(CustomControlStatus, native_enum=False, length=32),
        default=CustomControlStatus.ACTIVE,
        nullable=False,
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class ControlMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-scoped mapping linking canonical controls and custom controls."""

    __tablename__ = "control_mappings"
    __table_args__ = (
        Index("ix_control_mappings_tenant_source", "tenant_id", "source_control_id"),
        Index("ix_control_mappings_tenant_target", "tenant_id", "target_control_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[ControlEntityType] = mapped_column(
        Enum(ControlEntityType, native_enum=False, length=32), nullable=False
    )
    source_control_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    target_type: Mapped[ControlEntityType] = mapped_column(
        Enum(ControlEntityType, native_enum=False, length=32), nullable=False
    )
    target_control_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    mapping_type: Mapped[MappingType] = mapped_column(
        Enum(MappingType, native_enum=False, length=32),
        default=MappingType.SATISFIES,
        nullable=False,
    )
    rationale: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
