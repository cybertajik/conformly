from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
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
    REVIEW_REQUIRED = "review_required"


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


class SourceRequirementType(StrEnum):
    CLAUSE = "clause"
    SUBCLAUSE = "subclause"
    SAFEGUARD = "safeguard"
    ARTICLE = "article"
    OUTCOME = "outcome"
    STATUTORY = "statutory"
    REQUIREMENT = "requirement"


class CoverageDisposition(StrEnum):
    IMPLEMENTED = "IMPLEMENTED"
    NOT_CUSTOMER_OBLIGATION = "NOT_CUSTOMER_OBLIGATION"
    PROFILE_EXCLUSION = "PROFILE_EXCLUSION"
    BLOCKED = "BLOCKED"


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
    source_requirements: Mapped[list["SourceRequirement"]] = relationship(
        back_populates="framework_version",
        cascade="all, delete-orphan",
        order_by="SourceRequirement.sort_order",
    )
    coverage_ledger_entries: Mapped[list["CoverageLedgerEntry"]] = relationship(
        back_populates="framework_version",
        cascade="all, delete-orphan",
    )
    requirement_control_mappings: Mapped[list["RequirementControlMapping"]] = relationship(
        back_populates="framework_version",
        cascade="all, delete-orphan",
    )
    evidence_specifications: Mapped[list["EvidenceSpecification"]] = relationship(
        back_populates="framework_version",
        cascade="all, delete-orphan",
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
    requirement_mappings: Mapped[list["RequirementControlMapping"]] = relationship(
        back_populates="canonical_control",
        cascade="all, delete-orphan",
    )
    evidence_specifications: Mapped[list["EvidenceSpecification"]] = relationship(
        back_populates="canonical_control",
    )


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
    adopted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
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
    applicability_profiles: Mapped[list["TenantApplicabilityProfile"]] = relationship(
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


class TenantApplicabilityProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persisted scope evaluation facts, answers, sources, evaluator version, and review records."""

    __tablename__ = "tenant_applicability_profiles"
    __table_args__ = (
        Index("ix_tenant_applicability_profiles_tenant", "tenant_id"),
        Index("ix_tenant_applicability_profiles_adoption", "adoption_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    adoption_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenant_framework_adoptions.id", ondelete="CASCADE"), nullable=False
    )
    evaluator_version: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_answers_json: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    contradictions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    evaluation_summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    evaluated_by_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="EVALUATED", nullable=False)

    adoption: Mapped["TenantFrameworkAdoption"] = relationship(
        back_populates="applicability_profiles"
    )


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


class SourceRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """System-scoped official source requirement (statutory article, standard clause, safeguard)."""

    __tablename__ = "source_requirements"
    __table_args__ = (
        UniqueConstraint(
            "framework_version_id",
            "source_reference",
            name="uq_source_requirements_version_ref",
        ),
        Index("ix_source_requirements_version", "framework_version_id"),
        Index("ix_source_requirements_type", "requirement_type"),
    )

    framework_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("framework_versions.id", ondelete="CASCADE"), nullable=False
    )
    source_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    requirement_type: Mapped[SourceRequirementType] = mapped_column(
        Enum(SourceRequirementType, native_enum=False, length=32),
        default=SourceRequirementType.CLAUSE,
        nullable=False,
    )
    source_authority: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))
    retrieval_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    edition_or_amendment: Mapped[str] = mapped_column(String(100), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    effective_date: Mapped[str | None] = mapped_column(String(50))
    content_rights: Mapped[str] = mapped_column(Text, nullable=False)
    permitted_use: Mapped[str | None] = mapped_column(Text)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    conformly_guidance: Mapped[str | None] = mapped_column(Text)
    suggested_operating_targets: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    assessment_procedure: Mapped[str | None] = mapped_column(Text)
    default_owner_role: Mapped[str | None] = mapped_column(String(64))
    review_cadence: Mapped[str | None] = mapped_column(String(64))
    applicability_conditions: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reporting_limitations: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    framework_version: Mapped["FrameworkVersion"] = relationship(
        back_populates="source_requirements"
    )
    control_mappings: Mapped[list["RequirementControlMapping"]] = relationship(
        back_populates="source_requirement", cascade="all, delete-orphan"
    )
    evidence_specifications: Mapped[list["EvidenceSpecification"]] = relationship(
        back_populates="source_requirement"
    )
    coverage_ledger_entry: Mapped["CoverageLedgerEntry | None"] = relationship(
        back_populates="source_requirement", cascade="all, delete-orphan", uselist=False
    )


class RequirementControlMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """System-scoped mapping linking an official SourceRequirement to a CanonicalControl."""

    __tablename__ = "requirement_control_mappings"
    __table_args__ = (
        UniqueConstraint(
            "source_requirement_id",
            "canonical_control_id",
            name="uq_req_control_mappings_req_ctrl",
        ),
        Index("ix_req_ctrl_mappings_version", "framework_version_id"),
        Index("ix_req_ctrl_mappings_req", "source_requirement_id"),
        Index("ix_req_ctrl_mappings_ctrl", "canonical_control_id"),
    )

    framework_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("framework_versions.id", ondelete="CASCADE"), nullable=False
    )
    source_requirement_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_requirements.id", ondelete="CASCADE"), nullable=False
    )
    canonical_control_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("canonical_controls.id", ondelete="CASCADE"), nullable=False
    )
    mapping_type: Mapped[MappingType] = mapped_column(
        Enum(MappingType, native_enum=False, length=32),
        default=MappingType.SATISFIES,
        nullable=False,
    )
    rationale: Mapped[str | None] = mapped_column(Text)

    framework_version: Mapped["FrameworkVersion"] = relationship(
        back_populates="requirement_control_mappings"
    )
    source_requirement: Mapped["SourceRequirement"] = relationship(
        back_populates="control_mappings"
    )
    canonical_control: Mapped["CanonicalControl"] = relationship(
        back_populates="requirement_mappings"
    )


class EvidenceSpecification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """System-scoped structured specification of evidence expected for a control/requirement."""

    __tablename__ = "evidence_specifications"
    __table_args__ = (
        UniqueConstraint(
            "framework_version_id",
            "identifier",
            name="uq_evidence_specifications_version_ident",
        ),
        Index("ix_evidence_specifications_version", "framework_version_id"),
        Index("ix_evidence_specifications_control", "canonical_control_id"),
        Index("ix_evidence_specifications_req", "source_requirement_id"),
    )

    framework_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("framework_versions.id", ondelete="CASCADE"), nullable=False
    )
    canonical_control_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("canonical_controls.id", ondelete="SET NULL")
    )
    source_requirement_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("source_requirements.id", ondelete="SET NULL")
    )
    identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    original_file_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    observation_period_days: Mapped[int | None] = mapped_column(Integer)
    validity_period_days: Mapped[int | None] = mapped_column(Integer)
    review_cadence_days: Mapped[int | None] = mapped_column(Integer)
    confidentiality_level: Mapped[str] = mapped_column(
        String(32), default="Internal", nullable=False
    )
    suggested_storage_format: Mapped[str | None] = mapped_column(String(64))

    framework_version: Mapped["FrameworkVersion"] = relationship(
        back_populates="evidence_specifications"
    )
    canonical_control: Mapped["CanonicalControl | None"] = relationship(
        back_populates="evidence_specifications"
    )
    source_requirement: Mapped["SourceRequirement | None"] = relationship(
        back_populates="evidence_specifications"
    )


class CoverageLedgerEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """System-scoped ledger entry tracking the explicit disposition of every source requirement."""

    __tablename__ = "coverage_ledger_entries"
    __table_args__ = (
        UniqueConstraint(
            "framework_version_id",
            "source_requirement_id",
            name="uq_coverage_ledger_version_req",
        ),
        Index("ix_coverage_ledger_version_disposition", "framework_version_id", "disposition"),
    )

    framework_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("framework_versions.id", ondelete="CASCADE"), nullable=False
    )
    source_requirement_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_requirements.id", ondelete="CASCADE"), nullable=False
    )
    disposition: Mapped[CoverageDisposition] = mapped_column(
        Enum(CoverageDisposition, native_enum=False, length=32), nullable=False
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    framework_version: Mapped["FrameworkVersion"] = relationship(
        back_populates="coverage_ledger_entries"
    )
    source_requirement: Mapped["SourceRequirement"] = relationship(
        back_populates="coverage_ledger_entry"
    )
