"""SQLAlchemy ORM models for MVP-B Customer Control Work and Evidence Pinning."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from conformly.customer_demo.models import HexDigestFormat
from conformly.db.base import Base


class CustomerControlWork(Base):
    """Version-pinned control work item for an adopted customer demo pack."""

    __tablename__ = "customer_control_work"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_customer_control_work_version_pos"),
        UniqueConstraint(
            "tenant_id",
            "adoption_id",
            "control_version_id",
            name="uq_customer_control_work_tenant_adoption_ctrl_ver",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "adoption_id"],
            ["customer_demo_adoptions.tenant_id", "customer_demo_adoptions.id"],
            ondelete="RESTRICT",
            name="fk_customer_control_work_adoption",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "owner_user_id"],
            ["memberships.tenant_id", "memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_customer_control_work_owner_membership",
        ),
        Index("ix_customer_control_work_tenant_adoption", "tenant_id", "adoption_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        primary_key=True,
        nullable=False,
    )
    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    adoption_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    control_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    control_version_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
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
    )


class CustomerControlEvidenceLink(Base):
    """Append-only exact revision linkage between control work and evidence."""

    __tablename__ = "customer_control_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "evidence_revision_number > 0",
            name="ck_customer_control_evidence_links_rev_pos",
        ),
        CheckConstraint(
            HexDigestFormat("evidence_revision_digest"),
            name="ck_customer_control_evidence_links_rev_digest",
        ),
        UniqueConstraint(
            "tenant_id",
            "work_id",
            "evidence_id",
            "evidence_revision_number",
            name="uq_customer_control_evidence_links_natural",
        ),
        UniqueConstraint(
            "tenant_id",
            "id",
            "work_id",
            name="uq_customer_control_evidence_links_tenant_id_work",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "work_id"],
            ["customer_control_work.tenant_id", "customer_control_work.id"],
            ondelete="RESTRICT",
            name="fk_customer_control_evidence_links_work",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "evidence_id", "evidence_revision_number"],
            [
                "evidence_revisions.tenant_id",
                "evidence_revisions.evidence_id",
                "evidence_revisions.revision_number",
            ],
            ondelete="RESTRICT",
            name="fk_customer_control_evidence_links_evidence_rev",
        ),
        Index("ix_customer_control_evidence_links_tenant_evidence", "tenant_id", "evidence_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
    )
    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    work_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    evidence_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    evidence_revision_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    evidence_revision_digest: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    rationale_encrypted: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(postgresql.JSONB, "postgresql"),
        nullable=False,
    )
    actor_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class CustomerControlWorkEvent(Base):
    """Append-only audit and state progression events for control work."""

    __tablename__ = "customer_control_work_events"
    __table_args__ = (
        CheckConstraint("work_revision > 0", name="ck_customer_control_work_events_rev_pos"),
        CheckConstraint(
            HexDigestFormat("request_digest"),
            name="ck_customer_control_work_events_req_digest",
        ),
        CheckConstraint(
            "event_type IN ('INITIALIZED', 'OWNER_DUE_UPDATED', 'EVIDENCE_LINKED', 'EVIDENCE_REVIEWED')",
            name="ck_customer_control_work_events_type",
        ),
        CheckConstraint(
            "decision IS NULL OR decision IN ('ACCEPTED', 'REJECTED')",
            name="ck_customer_control_work_events_decision",
        ),
        CheckConstraint(
            "(event_type = 'EVIDENCE_REVIEWED' AND link_id IS NOT NULL AND decision IS NOT NULL) OR "
            "(event_type = 'EVIDENCE_LINKED' AND link_id IS NOT NULL AND decision IS NULL) OR "
            "(event_type IN ('INITIALIZED', 'OWNER_DUE_UPDATED') AND link_id IS NULL AND decision IS NULL)",
            name="ck_customer_control_work_events_type_coherence",
        ),
        UniqueConstraint(
            "tenant_id",
            "work_id",
            "work_revision",
            name="uq_customer_control_work_events_tenant_work_rev",
        ),
        UniqueConstraint(
            "tenant_id",
            "operation_id",
            name="uq_customer_control_work_events_tenant_op",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "work_id"],
            ["customer_control_work.tenant_id", "customer_control_work.id"],
            ondelete="RESTRICT",
            name="fk_customer_control_work_events_work",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "link_id", "work_id"],
            [
                "customer_control_evidence_links.tenant_id",
                "customer_control_evidence_links.id",
                "customer_control_evidence_links.work_id",
            ],
            ondelete="RESTRICT",
            name="fk_customer_control_work_events_link",
        ),
        Index(
            "ix_customer_control_work_events_tenant_work_rev",
            "tenant_id",
            "work_id",
            "work_revision",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
    )
    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    work_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    work_revision: Mapped[int] = mapped_column(
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
    link_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    decision: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )
    details_encrypted: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(postgresql.JSONB, "postgresql"),
        nullable=False,
    )
    actor_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
