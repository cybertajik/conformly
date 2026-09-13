"""Tenant applicability profiles and scope decisions.

Adds tenant_applicability_profiles table to persist profile facts, sources,
evaluator version, contradictions, review status, and evaluation summaries.

Revision ID: 20260913_0027
Revises: 20260913_0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0027"
down_revision: str | None = "20260913_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_applicability_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("adoption_id", sa.Uuid(), nullable=False),
        sa.Column("evaluator_version", sa.String(length=64), nullable=False),
        sa.Column("profile_answers_json", sa.Text(), nullable=False),
        sa.Column("sources_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("contradictions_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("evaluation_summary_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("evaluated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "review_status", sa.String(length=32), server_default="EVALUATED", nullable=False
        ),
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
            ["adoption_id"],
            ["tenant_framework_adoptions.id"],
            name=op.f("fk_tenant_applicability_profiles_adoption_id_tenant_framework_adoptions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evaluated_by_user_id"],
            ["users.id"],
            name=op.f("fk_tenant_applicability_profiles_evaluated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["users.id"],
            name=op.f("fk_tenant_applicability_profiles_reviewed_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tenant_applicability_profiles_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_applicability_profiles")),
    )
    op.create_index(
        "ix_tenant_applicability_profiles_tenant",
        "tenant_applicability_profiles",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_tenant_applicability_profiles_adoption",
        "tenant_applicability_profiles",
        ["adoption_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tenant_applicability_profiles_adoption",
        table_name="tenant_applicability_profiles",
    )
    op.drop_index(
        "ix_tenant_applicability_profiles_tenant",
        table_name="tenant_applicability_profiles",
    )
    op.drop_table("tenant_applicability_profiles")
