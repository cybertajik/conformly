"""Traceable content schema and coverage ledger.

Adds source_requirements, requirement_control_mappings, evidence_specifications,
and coverage_ledger_entries tables for canonical framework catalogs.

Revision ID: 20260913_0026
Revises: 20260913_0025
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0026"
down_revision: str | None = "20260913_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Source Requirements
    op.create_table(
        "source_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("framework_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_reference", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("requirement_type", sa.String(length=32), nullable=False),
        sa.Column("source_authority", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("retrieval_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("edition_or_amendment", sa.String(length=100), nullable=False),
        sa.Column("language", sa.String(length=10), server_default="en", nullable=False),
        sa.Column("effective_date", sa.String(length=50), nullable=True),
        sa.Column("content_rights", sa.String(length=255), nullable=False),
        sa.Column("permitted_use", sa.Text(), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("conformly_guidance", sa.Text(), nullable=True),
        sa.Column("suggested_operating_targets", sa.JSON(), nullable=True),
        sa.Column("assessment_procedure", sa.Text(), nullable=True),
        sa.Column("default_owner_role", sa.String(length=64), nullable=True),
        sa.Column("review_cadence", sa.String(length=64), nullable=True),
        sa.Column("applicability_conditions", sa.JSON(), nullable=True),
        sa.Column("reporting_limitations", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["framework_version_id"],
            ["framework_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "framework_version_id",
            "source_reference",
            name="uq_source_requirements_version_ref",
        ),
    )
    op.create_index(
        "ix_source_requirements_version",
        "source_requirements",
        ["framework_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_source_requirements_type",
        "source_requirements",
        ["requirement_type"],
        unique=False,
    )

    # 2. Requirement to Control Mappings
    op.create_table(
        "requirement_control_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("framework_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_requirement_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_control_id", sa.Uuid(), nullable=False),
        sa.Column("mapping_type", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["framework_version_id"],
            ["framework_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_requirement_id"],
            ["source_requirements.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_control_id"],
            ["canonical_controls.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_requirement_id",
            "canonical_control_id",
            name="uq_req_control_mappings_req_ctrl",
        ),
    )
    op.create_index(
        "ix_req_ctrl_mappings_version",
        "requirement_control_mappings",
        ["framework_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_req_ctrl_mappings_req",
        "requirement_control_mappings",
        ["source_requirement_id"],
        unique=False,
    )
    op.create_index(
        "ix_req_ctrl_mappings_ctrl",
        "requirement_control_mappings",
        ["canonical_control_id"],
        unique=False,
    )

    # 3. Structured Evidence Specifications
    op.create_table(
        "evidence_specifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("framework_version_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_control_id", sa.Uuid(), nullable=True),
        sa.Column("source_requirement_id", sa.Uuid(), nullable=True),
        sa.Column("identifier", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column(
            "original_file_required", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("observation_period_days", sa.Integer(), nullable=True),
        sa.Column("validity_period_days", sa.Integer(), nullable=True),
        sa.Column("review_cadence_days", sa.Integer(), nullable=True),
        sa.Column(
            "confidentiality_level", sa.String(length=32), server_default="Internal", nullable=False
        ),
        sa.Column("suggested_storage_format", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["framework_version_id"],
            ["framework_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_control_id"],
            ["canonical_controls.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_requirement_id"],
            ["source_requirements.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "framework_version_id",
            "identifier",
            name="uq_evidence_specifications_version_ident",
        ),
    )
    op.create_index(
        "ix_evidence_specifications_version",
        "evidence_specifications",
        ["framework_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_evidence_specifications_control",
        "evidence_specifications",
        ["canonical_control_id"],
        unique=False,
    )
    op.create_index(
        "ix_evidence_specifications_req",
        "evidence_specifications",
        ["source_requirement_id"],
        unique=False,
    )

    # 4. Coverage Ledger Entries
    op.create_table(
        "coverage_ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("framework_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_requirement_id", sa.Uuid(), nullable=False),
        sa.Column("disposition", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["framework_version_id"],
            ["framework_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_requirement_id"],
            ["source_requirements.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "framework_version_id",
            "source_requirement_id",
            name="uq_coverage_ledger_version_req",
        ),
    )
    op.create_index(
        "ix_coverage_ledger_version_disposition",
        "coverage_ledger_entries",
        ["framework_version_id", "disposition"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_coverage_ledger_version_disposition", table_name="coverage_ledger_entries")
    op.drop_table("coverage_ledger_entries")

    op.drop_index("ix_evidence_specifications_req", table_name="evidence_specifications")
    op.drop_index("ix_evidence_specifications_control", table_name="evidence_specifications")
    op.drop_index("ix_evidence_specifications_version", table_name="evidence_specifications")
    op.drop_table("evidence_specifications")

    op.drop_index("ix_req_ctrl_mappings_ctrl", table_name="requirement_control_mappings")
    op.drop_index("ix_req_ctrl_mappings_req", table_name="requirement_control_mappings")
    op.drop_index("ix_req_ctrl_mappings_version", table_name="requirement_control_mappings")
    op.drop_table("requirement_control_mappings")

    op.drop_index("ix_source_requirements_type", table_name="source_requirements")
    op.drop_index("ix_source_requirements_version", table_name="source_requirements")
    op.drop_table("source_requirements")
