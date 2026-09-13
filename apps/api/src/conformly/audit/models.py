from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from conformly.db.base import Base, UUIDPrimaryKeyMixin


class AuditActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"
    ANONYMOUS_REPORTER = "anonymous_reporter"


class AuditOutcome(StrEnum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILURE = "failure"


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    """Immutable record containing identifiers, hash chain, and explicitly safe metadata only."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_tenant_occurred", "tenant_id", "occurred_at"),
        Index("ix_audit_events_tenant_seq", "tenant_id", "sequence_number"),
        Index("ix_audit_events_resource", "tenant_id", "resource_type", "resource_id"),
        Index("ix_audit_events_actor", "actor_type", "actor_id", "occurred_at"),
    )

    tenant_id: Mapped[UUID | None] = mapped_column(nullable=True)
    sequence_number: Mapped[int] = mapped_column(nullable=False, default=1)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="0" * 64)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    actor_type: Mapped[AuditActorType] = mapped_column(
        Enum(AuditActorType, native_enum=False, length=32), nullable=False
    )
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[AuditOutcome] = mapped_column(
        Enum(AuditOutcome, native_enum=False, length=16), nullable=False
    )
    safe_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)


class AuditSeal(UUIDPrimaryKeyMixin, Base):
    """Periodic cryptographic seal over an audit log sequence window."""

    __tablename__ = "audit_seals"
    __table_args__ = (Index("ix_audit_seals_tenant_seq", "tenant_id", "end_sequence"),)

    tenant_id: Mapped[UUID | None] = mapped_column(nullable=True)
    start_sequence: Mapped[int] = mapped_column(nullable=False)
    end_sequence: Mapped[int] = mapped_column(nullable=False)
    record_count: Mapped[int] = mapped_column(nullable=False)
    head_event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    merkle_root: Mapped[str] = mapped_column(String(64), nullable=False)
    sealed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sealed_by_user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    seal_signature_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_object_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
