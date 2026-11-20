"""SQLAlchemy ORM models for V2 Pre-Audit Review Workflow."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from conformly.customer_demo.models import HexDigestFormat
from conformly.db.base import Base


class CustomerPreaudit(Base):
    """Case entity tracking tenant pre-audit readiness review."""

    __tablename__ = "customer_preaudits"

    tenant_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
    )
    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    adoption_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    lead_user_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    reviewer_user_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="DRAFT",
    )
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    current_scope_snapshot_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    current_review_snapshot_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_customer_preaudits_rev_pos"),
        CheckConstraint("lead_user_id <> reviewer_user_id", name="ck_customer_preaudits_lead_reviewer_diff"),
        CheckConstraint(
            "status IN ('DRAFT', 'FROZEN', 'IN_REVIEW', 'CHANGES_REQUESTED', 'REVIEWED', 'APPROVED', 'CANCELLED')",
            name="ck_customer_preaudits_status",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "adoption_id"],
            ["customer_demo_adoptions.tenant_id", "customer_demo_adoptions.id"],
            ondelete="RESTRICT",
            name="fk_customer_preaudits_adoption",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "lead_user_id"],
            ["memberships.tenant_id", "memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_customer_preaudits_lead",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reviewer_user_id"],
            ["memberships.tenant_id", "memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_customer_preaudits_reviewer",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "id", "current_scope_snapshot_id"],
            [
                "customer_preaudit_snapshots.tenant_id",
                "customer_preaudit_snapshots.preaudit_id",
                "customer_preaudit_snapshots.id",
            ],
            ondelete="RESTRICT",
            use_alter=True,
            name="fk_customer_preaudits_scope_snapshot",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "id", "current_review_snapshot_id"],
            [
                "customer_preaudit_snapshots.tenant_id",
                "customer_preaudit_snapshots.preaudit_id",
                "customer_preaudit_snapshots.id",
            ],
            ondelete="RESTRICT",
            use_alter=True,
            name="fk_customer_preaudits_review_snapshot",
        ),
    )


class CustomerPreauditSnapshot(Base):
    """Immutable point-in-time encrypted snapshot of pre-audit scope or review state."""

    __tablename__ = "customer_preaudit_snapshots"

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
    kind: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    digest: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    payload_encrypted: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(postgresql.JSONB, "postgresql"),
        nullable=False,
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        CheckConstraint("kind IN ('SCOPE', 'REVIEW')", name="ck_customer_preaudit_snapshots_kind"),
        CheckConstraint("sequence > 0", name="ck_customer_preaudit_snapshots_seq_pos"),
        CheckConstraint(HexDigestFormat("digest"), name="ck_customer_preaudit_snapshots_digest_format"),
        UniqueConstraint(
            "tenant_id", "preaudit_id", "kind", "sequence",
            name="uq_customer_preaudit_snapshots_kind_seq",
        ),
        UniqueConstraint(
            "tenant_id", "preaudit_id", "id",
            name="uq_customer_preaudit_snapshots_tenant_preaudit_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "preaudit_id"],
            ["customer_preaudits.tenant_id", "customer_preaudits.id"],
            ondelete="RESTRICT",
            name="fk_customer_preaudit_snapshots_preaudit",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["memberships.tenant_id", "memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_customer_preaudit_snapshots_created_by",
        ),
    )


class CustomerPreauditEvent(Base):
    """Immutable audit event recording pre-audit state transitions and actions."""

    __tablename__ = "customer_preaudit_events"

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
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    operation_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    request_digest: Mapped[str] = mapped_column(
        String(64),
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
    snapshot_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    prior_status: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    new_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    payload_encrypted: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(postgresql.JSONB, "postgresql"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_customer_preaudit_events_rev_pos"),
        CheckConstraint(HexDigestFormat("request_digest"), name="ck_customer_preaudit_events_req_digest"),
        CheckConstraint(
            "event_type IN ('CREATED', 'SCOPE_FROZEN', 'SUBMITTED', 'CHANGES_REQUESTED', 'REVIEWED', 'APPROVED', 'CANCELLED')",
            name="ck_customer_preaudit_events_type",
        ),
        UniqueConstraint("tenant_id", "operation_id", name="uq_customer_preaudit_events_op"),
        UniqueConstraint("tenant_id", "preaudit_id", "revision", name="uq_customer_preaudit_events_rev"),
        ForeignKeyConstraint(
            ["tenant_id", "preaudit_id"],
            ["customer_preaudits.tenant_id", "customer_preaudits.id"],
            ondelete="RESTRICT",
            name="fk_customer_preaudit_events_preaudit",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "actor_user_id"],
            ["memberships.tenant_id", "memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_customer_preaudit_events_actor",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "preaudit_id", "snapshot_id"],
            [
                "customer_preaudit_snapshots.tenant_id",
                "customer_preaudit_snapshots.preaudit_id",
                "customer_preaudit_snapshots.id",
            ],
            ondelete="RESTRICT",
            name="fk_customer_preaudit_events_snapshot",
        ),
    )

