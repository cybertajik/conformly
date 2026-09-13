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
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CredentialStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class InboundEventStatus(StrEnum):
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class IntegrationCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-scoped API key and HMAC webhook signing credential."""

    __tablename__ = "integration_credentials"
    __table_args__ = (
        UniqueConstraint("key_id", name="uq_integration_credentials_key_id"),
        Index("ix_integration_credentials_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_signing_secret: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    status: Mapped[CredentialStatus] = mapped_column(
        Enum(CredentialStatus, native_enum=False, length=32),
        default=CredentialStatus.ACTIVE,
        nullable=False,
    )
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Outbound webhook subscription destination configured for a tenant."""

    __tablename__ = "webhook_subscriptions"
    __table_args__ = (Index("ix_webhook_subscriptions_tenant_active", "tenant_id", "is_active"),)

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    target_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    topics: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    encrypted_secret: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )


class InboundWebhookEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Replay-protection and idempotency log for inbound signed webhooks."""

    __tablename__ = "inbound_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_inbound_webhook_events_tenant_idempotency"
        ),
        Index("ix_inbound_webhook_events_tenant_created", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    credential_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("integration_credentials.id", ondelete="SET NULL")
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    event_topic: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[InboundEventStatus] = mapped_column(
        Enum(InboundEventStatus, native_enum=False, length=32),
        default=InboundEventStatus.PROCESSING,
        nullable=False,
    )
    response_status_code: Mapped[int | None] = mapped_column(Integer)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
