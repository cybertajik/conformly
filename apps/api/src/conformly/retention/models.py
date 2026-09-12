from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DeletionJobState(StrEnum):
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ON_HOLD = "on_hold"


class DeletionReason(StrEnum):
    CANCELLATION = "cancellation"
    RETENTION_EXPIRED = "retention_expired"
    ADMIN_REQUEST = "admin_request"


class DeletionJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Scheduled or executing customer data deletion job."""

    __tablename__ = "deletion_jobs"
    __table_args__ = (
        Index("ix_deletion_jobs_tenant_scheduled", "tenant_id", "scheduled_at"),
        Index("ix_deletion_jobs_state", "state"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[DeletionReason] = mapped_column(
        Enum(DeletionReason, native_enum=False, length=32),
        default=DeletionReason.CANCELLATION,
        nullable=False,
    )
    state: Mapped[DeletionJobState] = mapped_column(
        Enum(DeletionJobState, native_enum=False, length=32),
        default=DeletionJobState.SCHEDULED,
        nullable=False,
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)


class DeletionProof(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Cryptographic receipt proving complete purge of customer records without retained content."""

    __tablename__ = "deletion_proofs"
    __table_args__ = (
        Index("ix_deletion_proofs_tenant", "tenant_id"),
        Index("ix_deletion_proofs_deleted_at", "deleted_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    deletion_job_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tables_purged: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    storage_objects_purged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    proof_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
