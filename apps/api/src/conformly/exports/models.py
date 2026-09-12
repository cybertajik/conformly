from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExportJobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class ExportScope(StrEnum):
    FULL = "full"
    COMPLIANCE_ONLY = "compliance_only"
    AUDIT_ONLY = "audit_only"


class ExportJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-scoped data export packaging request and status."""

    __tablename__ = "export_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_export_jobs_tenant_idempotency"),
        Index("ix_export_jobs_tenant_created", "tenant_id", "created_at"),
        Index("ix_export_jobs_tenant_status", "tenant_id", "status"),
        Index("ix_export_jobs_expires_at", "expires_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[ExportScope] = mapped_column(
        Enum(ExportScope, native_enum=False, length=32),
        default=ExportScope.FULL,
        nullable=False,
    )
    status: Mapped[ExportJobStatus] = mapped_column(
        Enum(ExportJobStatus, native_enum=False, length=32),
        default=ExportJobStatus.PENDING,
        nullable=False,
    )
    stored_file_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("stored_files.id", ondelete="SET NULL"), nullable=True
    )
    records_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sha256_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    manifest: Mapped["ExportManifest | None"] = relationship(
        back_populates="export_job", cascade="all, delete-orphan", uselist=False
    )


class ExportManifest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Cryptographic audit manifest of datasets, file hashes, and versions in an export."""

    __tablename__ = "export_manifests"
    __table_args__ = (Index("ix_export_manifests_tenant_job", "tenant_id", "export_job_id"),)

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    export_job_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("export_jobs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    dataset_versions: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    file_hashes: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    record_counts: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    audit_references: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    export_job: Mapped[ExportJob] = relationship(back_populates="manifest")
