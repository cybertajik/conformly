"""SQLAlchemy models for V2 Customer Readiness Verification Lifecycle (MVP-E)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from conformly.db.base import Base


class CustomerReadinessVerification(Base):
    """Tenant-isolated synthetic readiness verification record issued from approved pre-audit review."""

    __tablename__ = "customer_readiness_verifications"

    tenant_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
    )
    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    preaudit_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    snapshot_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
    )
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    valid_through: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    payload_encrypted: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(postgresql.JSONB, "postgresql"),
        nullable=False,
    )
    digest: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    current_event_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    superseded_by_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    supersedes_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_customer_verifications_rev_pos"),
        CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'REVOKED', 'EXPIRED', 'SUPERSEDED')",
            name="ck_customer_verifications_status",
        ),
        CheckConstraint("issued_at <= valid_through", name="ck_customer_verifications_validity_order"),
        CheckConstraint("length(digest) = 64", name="ck_customer_verifications_digest"),
        UniqueConstraint("tenant_id", "snapshot_id", name="uq_customer_verifications_snapshot"),
        ForeignKeyConstraint(
            ["tenant_id", "preaudit_id"],
            ["customer_preaudits.tenant_id", "customer_preaudits.id"],
            name="fk_customer_verifications_preaudit",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "preaudit_id", "snapshot_id"],
            [
                "customer_preaudit_snapshots.tenant_id",
                "customer_preaudit_snapshots.preaudit_id",
                "customer_preaudit_snapshots.id",
            ],
            name="fk_customer_verifications_snapshot",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "superseded_by_id"],
            ["customer_readiness_verifications.tenant_id", "customer_readiness_verifications.id"],
            name="fk_customer_verifications_superseded_by",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "supersedes_id"],
            ["customer_readiness_verifications.tenant_id", "customer_readiness_verifications.id"],
            name="fk_customer_verifications_supersedes",
            ondelete="RESTRICT",
        ),
    )


class CustomerReadinessVerificationEvent(Base):
    """Immutable audit ledger of verification lifecycle state transitions."""

    __tablename__ = "customer_readiness_verification_events"

    tenant_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
    )
    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    verification_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    operation_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    actor_role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    prior_status: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    new_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(
        String(4096),
        nullable=True,
    )
    payload_encrypted: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(postgresql.JSONB, "postgresql"),
        nullable=False,
    )
    request_digest: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        CheckConstraint("sequence >= 1", name="ck_customer_verification_events_seq_pos"),
        CheckConstraint(
            "event_type IN ('ISSUED', 'SUSPENDED', 'REVOKED', 'CORRECTED', 'SUPERSEDED', 'RECONCILED')",
            name="ck_customer_verification_events_type",
        ),
        CheckConstraint("length(request_digest) = 64", name="ck_customer_verification_events_req_digest"),
        UniqueConstraint("tenant_id", "operation_id", name="uq_customer_verification_events_op"),
        UniqueConstraint(
            "tenant_id",
            "verification_id",
            "sequence",
            name="uq_customer_verification_events_seq",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "verification_id"],
            ["customer_readiness_verifications.tenant_id", "customer_readiness_verifications.id"],
            name="fk_customer_verification_events_verification",
            ondelete="CASCADE",
        ),
    )
