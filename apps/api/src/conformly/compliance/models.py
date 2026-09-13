from datetime import datetime
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from conformly.frameworks.models import ControlEntityType


class EvidenceStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    VALID = "valid"
    EXPIRED = "expired"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class PolicyStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RemediationStatus(StrEnum):
    OPEN = "open"
    IN_REMEDIATION = "in_remediation"
    RESOLVED = "resolved"
    ACCEPTED_RISK = "accepted_risk"


class ControlImplementationStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    ASSESSED = "assessed"


class DigestFrequency(StrEnum):
    IMMEDIATE = "immediate"
    DAILY = "daily"
    WEEKLY = "weekly"
    NEVER = "never"


class EvidenceItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-scoped compliance evidence record with lifecycle states and classification."""

    __tablename__ = "evidence_items"
    __table_args__ = (
        Index("ix_evidence_items_tenant_status", "tenant_id", "status"),
        Index("ix_evidence_items_tenant_valid_until", "tenant_id", "valid_until"),
        Index("ix_evidence_items_tenant_owner", "tenant_id", "owner_user_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str] = mapped_column(String(32), default="Internal", nullable=False)
    status: Mapped[EvidenceStatus] = mapped_column(
        Enum(EvidenceStatus, native_enum=False, length=32),
        default=EvidenceStatus.DRAFT,
        nullable=False,
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}
    restricted_notes_encrypted: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    file_links: Mapped[list["EvidenceFileLink"]] = relationship(
        back_populates="evidence", cascade="all, delete-orphan"
    )
    control_links: Mapped[list["EvidenceControlLink"]] = relationship(
        back_populates="evidence", cascade="all, delete-orphan"
    )
    revisions: Mapped[list["EvidenceRevision"]] = relationship(
        back_populates="evidence", cascade="all, delete-orphan"
    )


class EvidenceFileLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Link joining an EvidenceItem to an encrypted StoredFile."""

    __tablename__ = "evidence_file_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "evidence_id", "file_id", name="uq_evidence_file_links_file"),
        Index("ix_evidence_file_links_tenant_evidence", "tenant_id", "evidence_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("evidence_items.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("stored_files.id", ondelete="RESTRICT"), nullable=False
    )
    attached_by_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    evidence: Mapped["EvidenceItem"] = relationship(back_populates="file_links")


class EvidenceControlLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Link associating an EvidenceItem with a canonical or custom control."""

    __tablename__ = "evidence_control_links"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "evidence_id",
            "control_type",
            "control_id",
            name="uq_evidence_control_links_control",
        ),
        Index("ix_evidence_control_links_tenant_control", "tenant_id", "control_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("evidence_items.id", ondelete="CASCADE"), nullable=False
    )
    control_type: Mapped[ControlEntityType] = mapped_column(
        Enum(ControlEntityType, native_enum=False, length=32), nullable=False
    )
    control_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    linked_by_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    evidence: Mapped["EvidenceItem"] = relationship(back_populates="control_links")


class Policy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-scoped versioned governance policy with review and approval tracking."""

    __tablename__ = "policies"
    __table_args__ = (
        Index("ix_policies_tenant_status", "tenant_id", "status"),
        Index("ix_policies_tenant_review_due", "tenant_id", "next_review_due"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    version_string: Mapped[str] = mapped_column(String(50), default="1.0", nullable=False)
    status: Mapped[PolicyStatus] = mapped_column(
        Enum(PolicyStatus, native_enum=False, length=32),
        default=PolicyStatus.DRAFT,
        nullable=False,
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_cycle_days: Mapped[int] = mapped_column(Integer, default=365, nullable=False)
    next_review_due: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}
    content: Mapped[str | None] = mapped_column(Text)
    classification: Mapped[str] = mapped_column(String(32), default="Internal", nullable=False)
    restricted_content_encrypted: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    control_links: Mapped[list["PolicyControlLink"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan"
    )
    revisions: Mapped[list["PolicyRevision"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan"
    )
    acknowledgements: Mapped[list["PolicyAcknowledgement"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan"
    )


class PolicyControlLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Link associating a Policy with a canonical or custom control."""

    __tablename__ = "policy_control_links"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "policy_id",
            "control_type",
            "control_id",
            name="uq_policy_control_links_control",
        ),
        Index("ix_policy_control_links_tenant_control", "tenant_id", "control_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )
    control_type: Mapped[ControlEntityType] = mapped_column(
        Enum(ControlEntityType, native_enum=False, length=32), nullable=False
    )
    control_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    linked_by_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    policy: Mapped["Policy"] = relationship(back_populates="control_links")


class EvidenceRevision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable snapshot of an evidence item at a point in time."""

    __tablename__ = "evidence_revisions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "evidence_id", "revision_number", name="uq_evidence_revisions_number"
        ),
        Index("ix_evidence_revisions_tenant_evidence", "tenant_id", "evidence_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("evidence_items.id", ondelete="CASCADE"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[EvidenceStatus] = mapped_column(
        Enum(EvidenceStatus, native_enum=False, length=32), nullable=False
    )
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    file_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    control_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    change_summary: Mapped[str | None] = mapped_column(Text)

    evidence: Mapped["EvidenceItem"] = relationship(back_populates="revisions")


class PolicyRevision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable snapshot of a policy revision."""

    __tablename__ = "policy_revisions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "policy_id", "revision_number", name="uq_policy_revisions_number"
        ),
        Index("ix_policy_revisions_tenant_policy", "tenant_id", "policy_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_string: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[PolicyStatus] = mapped_column(
        Enum(PolicyStatus, native_enum=False, length=32), nullable=False
    )
    restricted_content_encrypted: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_summary: Mapped[str | None] = mapped_column(Text)

    policy: Mapped["Policy"] = relationship(back_populates="revisions")


class PolicyTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Canonical baseline or tenant-specific policy template."""

    __tablename__ = "policy_templates"
    __table_args__ = (
        Index("ix_policy_templates_tenant_slug", "tenant_id", "slug"),
        Index("ix_policy_templates_category", "category"),
    )

    tenant_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    content_template: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_classification: Mapped[str] = mapped_column(
        String(32), default="Internal", nullable=False
    )
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PolicyAcknowledgement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Workforce acknowledgement of a published policy."""

    __tablename__ = "policy_acknowledgements"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "policy_id",
            "user_id",
            "policy_revision_id",
            name="uq_policy_acknowledgements_user_rev",
        ),
        Index("ix_policy_acknowledgements_tenant_policy", "tenant_id", "policy_id"),
        Index("ix_policy_acknowledgements_tenant_user", "tenant_id", "user_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )
    policy_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("policy_revisions.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))

    policy: Mapped["Policy"] = relationship(back_populates="acknowledgements")


class ComplianceTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-scoped actionable task assigned to maintain or verify compliance."""

    __tablename__ = "compliance_tasks"
    __table_args__ = (
        Index("ix_compliance_tasks_tenant_status", "tenant_id", "status"),
        Index("ix_compliance_tasks_tenant_due", "tenant_id", "due_date"),
        Index("ix_compliance_tasks_tenant_assignee", "tenant_id", "assignee_user_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False, length=32),
        default=TaskStatus.PENDING,
        nullable=False,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, native_enum=False, length=32),
        default=TaskPriority.MEDIUM,
        nullable=False,
    )
    assignee_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    control_type: Mapped[ControlEntityType | None] = mapped_column(
        Enum(ControlEntityType, native_enum=False, length=32)
    )
    control_id: Mapped[UUID | None] = mapped_column(Uuid)
    evidence_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("evidence_items.id", ondelete="SET NULL")
    )
    policy_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("policies.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )


class Finding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-scoped compliance finding, gap, or audit observation requiring remediation."""

    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_findings_tenant_status", "tenant_id", "remediation_status"),
        Index("ix_findings_tenant_severity", "tenant_id", "severity"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(FindingSeverity, native_enum=False, length=32),
        default=FindingSeverity.MEDIUM,
        nullable=False,
    )
    remediation_status: Mapped[RemediationStatus] = mapped_column(
        Enum(RemediationStatus, native_enum=False, length=32),
        default=RemediationStatus.OPEN,
        nullable=False,
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    control_type: Mapped[ControlEntityType | None] = mapped_column(
        Enum(ControlEntityType, native_enum=False, length=32)
    )
    control_id: Mapped[UUID | None] = mapped_column(Uuid)
    remediation_plan: Mapped[str | None] = mapped_column(Text)
    remediation_summary: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}


class ControlStatusRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Aggregated posture and implementation status for a canonical or custom control."""

    __tablename__ = "control_status_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "control_type",
            "control_id",
            name="uq_control_status_records_control",
        ),
        Index("ix_control_status_records_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    control_type: Mapped[ControlEntityType] = mapped_column(
        Enum(ControlEntityType, native_enum=False, length=32), nullable=False
    )
    control_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[ControlImplementationStatus] = mapped_column(
        Enum(ControlImplementationStatus, native_enum=False, length=32),
        default=ControlImplementationStatus.NOT_STARTED,
        nullable=False,
    )
    assigned_owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    last_assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assessed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}


class UserNotificationPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-scoped user preferences for compliance notification digests and alerts."""

    __tablename__ = "user_notification_preferences"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_user_notification_preferences_user"),
        Index("ix_user_notification_preferences_tenant", "tenant_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    digest_frequency: Mapped[DigestFrequency] = mapped_column(
        Enum(DigestFrequency, native_enum=False, length=32),
        default=DigestFrequency.IMMEDIATE,
        nullable=False,
    )
    notify_task_assigned: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_task_due: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_evidence_expired: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_policy_review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_finding_raised: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
