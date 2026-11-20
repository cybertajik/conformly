"""SQLAlchemy models for MVP-C Customer Assessment vertical slice."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
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


class CustomerAssessmentHead(Base):
    """Journal head tracking CAS revision for control work assessments."""

    __tablename__ = "customer_assessment_heads"
    __table_args__ = (
        CheckConstraint(
            "current_revision >= 0",
            name="ck_customer_assessment_heads_rev_nonneg",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "work_id"],
            ["customer_control_work.tenant_id", "customer_control_work.id"],
            ondelete="RESTRICT",
            name="fk_customer_assessment_heads_work",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
    )
    work_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
    )
    current_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
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


class CustomerAssessmentEvent(Base):
    """Append-only immutable event journal for assessments, retests, and finding updates."""

    __tablename__ = "customer_assessment_events"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_customer_assessment_events_rev_pos"),
        CheckConstraint(
            HexDigestFormat("request_digest"),
            name="ck_customer_assessment_events_req_digest",
        ),
        CheckConstraint(
            "event_type IN ('ASSESSMENT', 'RETEST', 'FINDING_UPDATED')",
            name="ck_customer_assessment_events_type",
        ),
        CheckConstraint(
            "result IS NULL OR result IN ('PASS', 'PARTIAL', 'FAIL', 'INSUFFICIENT_EVIDENCE')",
            name="ck_customer_assessment_events_res",
        ),
        CheckConstraint(
            "(event_type IN ('ASSESSMENT', 'RETEST') AND result IS NOT NULL) OR "
            "(event_type = 'FINDING_UPDATED' AND result IS NULL)",
            name="ck_customer_assessment_events_type_res",
        ),
        CheckConstraint(
            "observed_work_version > 0",
            name="ck_customer_assessment_events_work_ver_pos",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "work_id"],
            ["customer_assessment_heads.tenant_id", "customer_assessment_heads.work_id"],
            ondelete="RESTRICT",
            name="fk_customer_assessment_events_head",
        ),
        ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name="fk_customer_assessment_events_actor",
        ),
        UniqueConstraint(
            "tenant_id",
            "work_id",
            "revision",
            name="uq_customer_assessment_events_work_rev",
        ),
        UniqueConstraint(
            "tenant_id",
            "operation_id",
            name="uq_customer_assessment_events_op",
        ),
        UniqueConstraint(
            "tenant_id",
            "id",
            "work_id",
            name="uq_customer_assessment_events_tenant_id_work",
        ),
        Index(
            "ix_customer_assessment_events_work_rev",
            "tenant_id",
            "work_id",
            "revision",
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
    result: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    observed_work_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    details_encrypted: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(postgresql.JSONB, "postgresql"),
        nullable=False,
    )
    actor_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class CustomerAssessmentFinding(Base):
    """Narrow projection of human findings identified during assessment."""

    __tablename__ = "customer_assessment_findings"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_customer_assessment_findings_severity",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'IN_REMEDIATION', 'RESOLVED')",
            name="ck_customer_assessment_findings_status",
        ),
        CheckConstraint(
            "version > 0",
            name="ck_customer_assessment_findings_ver_pos",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "work_id"],
            ["customer_assessment_heads.tenant_id", "customer_assessment_heads.work_id"],
            ondelete="RESTRICT",
            name="fk_customer_assessment_findings_head",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "source_event_id", "work_id"],
            [
                "customer_assessment_events.tenant_id",
                "customer_assessment_events.id",
                "customer_assessment_events.work_id",
            ],
            ondelete="RESTRICT",
            name="fk_customer_assessment_findings_source_event",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "current_event_id", "work_id"],
            [
                "customer_assessment_events.tenant_id",
                "customer_assessment_events.id",
                "customer_assessment_events.work_id",
            ],
            ondelete="RESTRICT",
            name="fk_customer_assessment_findings_current_event",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "owner_user_id"],
            ["memberships.tenant_id", "memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_customer_assessment_findings_owner",
        ),
        UniqueConstraint(
            "tenant_id",
            "source_event_id",
            name="uq_customer_assessment_findings_source_event",
        ),
        Index(
            "ix_customer_assessment_findings_work_status",
            "tenant_id",
            "work_id",
            "status",
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
    source_event_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    current_event_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        String(32),
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
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="OPEN",
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
