"""SQLAlchemy ORM models for WP-09 Customer Onboarding Demo."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.expression import ColumnElement

from conformly.db.base import Base


class HexDigestFormat(ColumnElement[bool]):
    """Portable 64 lower-case hex character check constraint."""

    inherit_cache = True

    def __init__(self, column: str) -> None:
        self.column = column


@compiles(HexDigestFormat, "postgresql")
def compile_hex_digest_format_pg(element: HexDigestFormat, compiler: Any, **kw: Any) -> str:
    col = element.column
    return f"length({col}) = 64 AND {col} ~ '^[0-9a-f]{{64}}$'"


@compiles(HexDigestFormat, "sqlite")
def compile_hex_digest_format_sqlite(element: HexDigestFormat, compiler: Any, **kw: Any) -> str:
    col = element.column
    return f"length({col}) = 64 AND NOT ({col} GLOB '*[^0-9a-f]*')"


@compiles(HexDigestFormat)
def compile_hex_digest_format_default(element: HexDigestFormat, compiler: Any, **kw: Any) -> str:
    col = element.column
    return f"length({col}) = 64"


class CustomerDemoWorkspace(Base):
    """Head workspace state for a tenant's customer demo journey."""

    __tablename__ = "customer_demo_workspaces"

    tenant_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    current_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    selection_revision: Mapped[int] = mapped_column(
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
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        CheckConstraint("current_revision >= 0", name="ck_customer_demo_workspaces_current_rev"),
        CheckConstraint(
            "selection_revision >= 0", name="ck_customer_demo_workspaces_selection_rev"
        ),
    )


class CustomerDemoAnswers(Base):
    """Immutable revisions of tenant-scoped customer onboarding answers."""

    __tablename__ = "customer_demo_answers"

    tenant_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        ForeignKey("customer_demo_workspaces.tenant_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    revision: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    company_code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    answers: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(postgresql.JSONB, "postgresql"),
        nullable=False,
    )
    content_digest: Mapped[str] = mapped_column(
        String(64),
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

    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_customer_demo_answers_rev_pos"),
        CheckConstraint(
            "company_code IN ('ALPHA', 'BETA')", name="ck_customer_demo_answers_company_code"
        ),
        CheckConstraint(
            HexDigestFormat("content_digest"), name="ck_customer_demo_answers_content_digest_format"
        ),
    )


class CustomerDemoEvaluation(Base):
    """Immutable server-computed evaluation snapshot against a specific answer revision."""

    __tablename__ = "customer_demo_evaluations"

    tenant_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
    )
    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    answer_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    pack_version_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    bundle_digest: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    evaluator_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    results: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(postgresql.JSONB, "postgresql"),
        nullable=False,
    )
    content_digest: Mapped[str] = mapped_column(
        String(64),
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

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "answer_revision"],
            ["customer_demo_answers.tenant_id", "customer_demo_answers.revision"],
            ondelete="RESTRICT",
            name="fk_customer_demo_evaluations_answers",
        ),
        CheckConstraint(
            HexDigestFormat("bundle_digest"),
            name="ck_customer_demo_evaluations_bundle_digest_format",
        ),
        CheckConstraint(
            HexDigestFormat("content_digest"),
            name="ck_customer_demo_evaluations_content_digest_format",
        ),
    )


class CustomerDemoAdoption(Base):
    """Immutable sequence of demo pack adoptions for a tenant."""

    __tablename__ = "customer_demo_adoptions"

    tenant_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
    )
    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    evaluation_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    pack_version_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    bundle_digest: Mapped[str] = mapped_column(
        String(64),
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
    selection_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "evaluation_id"],
            ["customer_demo_evaluations.tenant_id", "customer_demo_evaluations.id"],
            ondelete="RESTRICT",
            name="fk_customer_demo_adoptions_evaluation",
        ),
        UniqueConstraint(
            "tenant_id", "evaluation_id", name="uq_customer_demo_adoptions_tenant_eval"
        ),
        UniqueConstraint(
            "tenant_id", "selection_revision", name="uq_customer_demo_adoptions_tenant_sel_rev"
        ),
        CheckConstraint(
            "selection_revision > 0", name="ck_customer_demo_adoptions_selection_rev_pos"
        ),
        CheckConstraint(
            HexDigestFormat("bundle_digest"), name="ck_customer_demo_adoptions_bundle_digest_format"
        ),
    )
