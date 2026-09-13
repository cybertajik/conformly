from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from conformly.compliance.models import (
    ControlImplementationStatus,
    FindingSeverity,
    RemediationStatus,
)
from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from conformly.frameworks.models import ControlEntityType


class PreAuditStatus(StrEnum):
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CheckResult(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"


class CertificateStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"
    SUPERSEDED = "superseded"


# ── Valid state transitions ───────────────────────────────────────────────

PRE_AUDIT_TRANSITIONS: dict[PreAuditStatus, frozenset[PreAuditStatus]] = {
    PreAuditStatus.PLANNING: frozenset({PreAuditStatus.IN_PROGRESS, PreAuditStatus.CANCELLED}),
    PreAuditStatus.IN_PROGRESS: frozenset({PreAuditStatus.IN_REVIEW, PreAuditStatus.CANCELLED}),
    PreAuditStatus.IN_REVIEW: frozenset(
        {PreAuditStatus.COMPLETED, PreAuditStatus.IN_PROGRESS, PreAuditStatus.CANCELLED}
    ),
    PreAuditStatus.COMPLETED: frozenset(),
    PreAuditStatus.CANCELLED: frozenset(),
}


# ── Domain models ─────────────────────────────────────────────────────────


class PreAudit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-scoped pre-audit readiness assessment."""

    __tablename__ = "pre_audits"
    __table_args__ = (
        Index("ix_pre_audits_tenant_status", "tenant_id", "status"),
        Index("ix_pre_audits_tenant_adoption", "tenant_id", "framework_adoption_id"),
        Index("ix_pre_audits_tenant_legal_entity", "tenant_id", "legal_entity_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    legal_entity_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("legal_entities.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[PreAuditStatus] = mapped_column(
        Enum(PreAuditStatus, native_enum=False, length=32),
        default=PreAuditStatus.PLANNING,
        nullable=False,
    )
    framework_adoption_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("tenant_framework_adoptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    lead_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reviewer_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tenant_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tenant_approved_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    rule_version: Mapped[str] = mapped_column(String(50), nullable=False)
    overall_score: Mapped[float | None] = mapped_column(Float)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__: dict[str, Any] = {
        "version_id_col": version,
        "version_id_generator": False,
    }

    scopes: Mapped[list["PreAuditScope"]] = relationship(
        back_populates="pre_audit", cascade="all, delete-orphan"
    )
    findings: Mapped[list["PreAuditFinding"]] = relationship(
        back_populates="pre_audit", cascade="all, delete-orphan"
    )
    reports: Mapped[list["PreAuditReport"]] = relationship(
        back_populates="pre_audit", cascade="all, delete-orphan"
    )
    manifests: Mapped[list["PreAuditManifest"]] = relationship(
        back_populates="pre_audit", cascade="all, delete-orphan"
    )
    certificates: Mapped[list["PreAuditCertificate"]] = relationship(
        back_populates="pre_audit", cascade="all, delete-orphan"
    )


class PreAuditScope(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Framework version scope included in a pre-audit assessment."""

    __tablename__ = "pre_audit_scopes"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "pre_audit_id",
            "framework_version_id",
            name="uq_pre_audit_scopes_version",
        ),
        Index("ix_pre_audit_scopes_tenant_audit", "tenant_id", "pre_audit_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    pre_audit_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("pre_audits.id", ondelete="CASCADE"), nullable=False
    )
    framework_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("framework_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    control_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    pre_audit: Mapped["PreAudit"] = relationship(back_populates="scopes")
    checks: Mapped[list["PreAuditCheck"]] = relationship(
        back_populates="scope", cascade="all, delete-orphan"
    )


class PreAuditCheck(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Individual control readiness check within a pre-audit scope."""

    __tablename__ = "pre_audit_checks"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "scope_id",
            "control_type",
            "control_id",
            name="uq_pre_audit_checks_control",
        ),
        Index("ix_pre_audit_checks_tenant_scope", "tenant_id", "scope_id"),
        Index("ix_pre_audit_checks_tenant_result", "tenant_id", "result"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    scope_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("pre_audit_scopes.id", ondelete="CASCADE"), nullable=False
    )
    control_type: Mapped[ControlEntityType] = mapped_column(
        Enum(ControlEntityType, native_enum=False, length=32), nullable=False
    )
    control_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    result: Mapped[CheckResult] = mapped_column(
        Enum(CheckResult, native_enum=False, length=32),
        default=CheckResult.PENDING,
        nullable=False,
    )
    rule_version: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    policy_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    open_findings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    implementation_status: Mapped[ControlImplementationStatus | None] = mapped_column(
        Enum(ControlImplementationStatus, native_enum=False, length=32)
    )
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot_json: Mapped[str | None] = mapped_column(Text)

    scope: Mapped["PreAuditScope"] = relationship(back_populates="checks")


class PreAuditFinding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Readiness gap identified during a pre-audit check or reviewer assessment."""

    __tablename__ = "pre_audit_findings"
    __table_args__ = (
        Index(
            "ix_pre_audit_findings_tenant_audit",
            "tenant_id",
            "pre_audit_id",
        ),
        Index(
            "ix_pre_audit_findings_tenant_status",
            "tenant_id",
            "remediation_status",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    pre_audit_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("pre_audits.id", ondelete="CASCADE"), nullable=False
    )
    check_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("pre_audit_checks.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(FindingSeverity, native_enum=False, length=32),
        default=FindingSeverity.MEDIUM,
        nullable=False,
    )
    recommendation: Mapped[str | None] = mapped_column(Text)
    remediation_status: Mapped[RemediationStatus] = mapped_column(
        Enum(RemediationStatus, native_enum=False, length=32),
        default=RemediationStatus.OPEN,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__: dict[str, Any] = {
        "version_id_col": version,
        "version_id_generator": False,
    }

    pre_audit: Mapped["PreAudit"] = relationship(back_populates="findings")


class PreAuditReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Human-readable report artifact generated from a pre-audit."""

    __tablename__ = "pre_audit_reports"
    __table_args__ = (
        Index(
            "ix_pre_audit_reports_tenant_audit",
            "tenant_id",
            "pre_audit_id",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    pre_audit_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("pre_audits.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("stored_files.id", ondelete="RESTRICT"), nullable=False
    )
    report_type: Mapped[str] = mapped_column(
        String(50), default="readiness_summary", nullable=False
    )
    rule_version: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    pre_audit: Mapped["PreAudit"] = relationship(back_populates="reports")


class PreAuditManifest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Machine-readable audit manifest generated from a pre-audit."""

    __tablename__ = "pre_audit_manifests"
    __table_args__ = (
        Index(
            "ix_pre_audit_manifests_tenant_audit",
            "tenant_id",
            "pre_audit_id",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    pre_audit_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("pre_audits.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("stored_files.id", ondelete="RESTRICT"), nullable=False
    )
    manifest_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_version: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    pre_audit: Mapped["PreAudit"] = relationship(back_populates="manifests")


class PreAuditCertificate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Conformly-issued pre-audit readiness credential."""

    __tablename__ = "pre_audit_certificates"
    __table_args__ = (
        UniqueConstraint("certificate_number", name="uq_pre_audit_certificates_number"),
        Index(
            "ix_pre_audit_certificates_tenant_audit",
            "tenant_id",
            "pre_audit_id",
        ),
        Index(
            "ix_pre_audit_certificates_tenant_status",
            "tenant_id",
            "status",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    pre_audit_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("pre_audits.id", ondelete="CASCADE"), nullable=False
    )
    certificate_number: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[CertificateStatus] = mapped_column(
        Enum(CertificateStatus, native_enum=False, length=32),
        default=CertificateStatus.ACTIVE,
        nullable=False,
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(Text)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_reason: Mapped[str | None] = mapped_column(Text)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_by_certificate_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("pre_audit_certificates.id", ondelete="SET NULL")
    )
    issuance_package_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    pre_audit: Mapped["PreAudit"] = relationship(back_populates="certificates")
