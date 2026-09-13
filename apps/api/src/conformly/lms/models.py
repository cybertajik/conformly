from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
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
from sqlalchemy.orm import Mapped, mapped_column

from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AssignmentStatus(StrEnum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    EXPIRED = "expired"


class VerificationMethod(StrEnum):
    WEBHOOK = "webhook"
    API = "api"
    MANUAL = "manual"


class TrainingCourse(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Course catalog item synchronized from or configured for external LMS."""

    __tablename__ = "training_courses"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "course_id", "version", name="uq_training_courses_tenant_course_version"
        ),
        Index("ix_training_courses_tenant_course", "tenant_id", "course_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(128), default="lms", nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    validity_period_days: Mapped[int] = mapped_column(Integer, default=365, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TrainingAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Training assignment linking a user/workforce member to a course and compliance control."""

    __tablename__ = "training_assignments"
    __table_args__ = (
        Index("ix_training_assignments_tenant_status", "tenant_id", "status"),
        Index("ix_training_assignments_tenant_user", "tenant_id", "user_id"),
        Index("ix_training_assignments_tenant_control", "tenant_id", "control_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    workforce_email: Mapped[str] = mapped_column(String(320), nullable=False)
    assigned_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, native_enum=False, length=32),
        default=AssignmentStatus.ASSIGNED,
        nullable=False,
    )
    control_id: Mapped[UUID | None] = mapped_column(Uuid)
    control_type: Mapped[str | None] = mapped_column(String(32))


class TrainingCompletion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Verified training completion record that serves as continuous compliance evidence."""

    __tablename__ = "training_completions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_training_completions_tenant_idempotency"
        ),
        Index("ix_training_completions_tenant_course", "tenant_id", "course_id"),
        Index("ix_training_completions_tenant_user", "tenant_id", "user_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    assignment_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("training_assignments.id", ondelete="SET NULL")
    )
    course_id: Mapped[str] = mapped_column(String(128), nullable=False)
    course_version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    workforce_email: Mapped[str] = mapped_column(String(320), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    certificate_id: Mapped[str | None] = mapped_column(String(255))
    evidence_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("evidence_items.id", ondelete="SET NULL")
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    verified_via: Mapped[VerificationMethod] = mapped_column(
        Enum(VerificationMethod, native_enum=False, length=32),
        default=VerificationMethod.WEBHOOK,
        nullable=False,
    )
    raw_payload_encrypted: Mapped[dict[str, Any] | None] = mapped_column(JSON)
