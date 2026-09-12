from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class StoredFileStatus(StrEnum):
    ACTIVE = "active"
    DELETE_PENDING = "delete_pending"
    DELETED = "deleted"


class StoredFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Metadata for an application-layer encrypted object in storage."""

    __tablename__ = "stored_files"
    __table_args__ = (
        Index("ix_stored_files_tenant_created", "tenant_id", "created_at"),
        Index("ix_stored_files_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    plaintext_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    ciphertext_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    plaintext_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    ciphertext_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    encryption_algorithm: Mapped[str] = mapped_column(
        String(32), default="AES-256-GCM", nullable=False
    )
    context_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    key_version: Mapped[str] = mapped_column(String(64), nullable=False)
    wrapped_dek_nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    wrapped_dek: Mapped[str] = mapped_column(Text, nullable=False)
    ciphertext_nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[StoredFileStatus] = mapped_column(
        Enum(StoredFileStatus, native_enum=False, length=32),
        default=StoredFileStatus.ACTIVE,
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
