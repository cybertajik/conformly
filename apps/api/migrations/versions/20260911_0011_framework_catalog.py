"""Add Framework Catalog, Canonical Controls, Tenant Adoptions, Overlays,
Custom Controls, and Mappings with RLS.

Revision ID: 20260911_0011
Revises: 20260911_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0011"
down_revision: str | None = "20260911_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Canonical Frameworks
    op.create_table(
        "frameworks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_frameworks")),
        sa.UniqueConstraint("slug", name=op.f("uq_frameworks_slug")),
    )

    # 2. Framework Versions
    op.create_table(
        "framework_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("framework_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("release_state", sa.String(length=32), nullable=False),
        sa.Column("release_notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("legal_reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("legal_review_notes", sa.Text(), nullable=True),
        sa.Column("legal_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("approval_notes", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
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
            ["approved_by_user_id"],
            ["users.id"],
            name=op.f("fk_framework_versions_approved_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_framework_versions_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["framework_id"],
            ["frameworks.id"],
            name=op.f("fk_framework_versions_framework_id_frameworks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["legal_reviewed_by_user_id"],
            ["users.id"],
            name=op.f("fk_framework_versions_legal_reviewed_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_framework_versions")),
        sa.UniqueConstraint(
            "framework_id", "version", name="uq_framework_versions_framework_version"
        ),
    )
    op.create_index(
        "ix_framework_versions_state",
        "framework_versions",
        ["release_state"],
        unique=False,
    )

    # 3. Canonical Controls
    op.create_table(
        "canonical_controls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("framework_version_id", sa.Uuid(), nullable=False),
        sa.Column("identifier", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("guidance", sa.Text(), nullable=True),
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
            name=op.f("fk_canonical_controls_framework_version_id_framework_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_canonical_controls")),
        sa.UniqueConstraint(
            "framework_version_id",
            "identifier",
            name="uq_canonical_controls_version_identifier",
        ),
    )
    op.create_index(
        "ix_canonical_controls_category",
        "canonical_controls",
        ["category"],
        unique=False,
    )

    # 4. Tenant Framework Adoptions
    op.create_table(
        "tenant_framework_adoptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("framework_id", sa.Uuid(), nullable=False),
        sa.Column("framework_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("adopted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("adopted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "impact_analysis_acknowledged_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("impact_summary_json", sa.Text(), nullable=True),
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
            ["adopted_by_user_id"],
            ["users.id"],
            name=op.f("fk_tenant_framework_adoptions_adopted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["framework_id"],
            ["frameworks.id"],
            name=op.f("fk_tenant_framework_adoptions_framework_id_frameworks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["framework_version_id"],
            ["framework_versions.id"],
            name=op.f("fk_tenant_framework_adoptions_framework_version_id_framework_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tenant_framework_adoptions_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_framework_adoptions")),
    )
    op.create_index(
        "ix_tenant_adoptions_tenant_framework",
        "tenant_framework_adoptions",
        ["tenant_id", "framework_id", "status"],
        unique=False,
    )

    # 5. Tenant Control Overlays
    op.create_table(
        "tenant_control_overlays",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("adoption_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_control_id", sa.Uuid(), nullable=False),
        sa.Column("applicability", sa.String(length=32), nullable=False),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("custom_guidance", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
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
            name=op.f("fk_tenant_control_overlays_adoption_id_tenant_framework_adoptions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_control_id"],
            ["canonical_controls.id"],
            name=op.f("fk_tenant_control_overlays_canonical_control_id_canonical_controls"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_tenant_control_overlays_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tenant_control_overlays_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_control_overlays")),
        sa.UniqueConstraint(
            "tenant_id",
            "adoption_id",
            "canonical_control_id",
            name="uq_tenant_control_overlays_control",
        ),
    )
    op.create_index(
        "ix_tenant_control_overlays_tenant",
        "tenant_control_overlays",
        ["tenant_id"],
        unique=False,
    )

    # 6. Custom Controls
    op.create_table(
        "custom_controls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("identifier", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("guidance", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
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
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_custom_controls_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_custom_controls_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_custom_controls")),
        sa.UniqueConstraint("tenant_id", "identifier", name="uq_custom_controls_tenant_identifier"),
    )
    op.create_index(
        "ix_custom_controls_tenant_status",
        "custom_controls",
        ["tenant_id", "status"],
        unique=False,
    )

    # 7. Control Mappings
    op.create_table(
        "control_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_control_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_control_id", sa.Uuid(), nullable=False),
        sa.Column("mapping_type", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
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
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_control_mappings_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_control_mappings_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_control_mappings")),
    )
    op.create_index(
        "ix_control_mappings_tenant_source",
        "control_mappings",
        ["tenant_id", "source_control_id"],
        unique=False,
    )
    op.create_index(
        "ix_control_mappings_tenant_target",
        "control_mappings",
        ["tenant_id", "target_control_id"],
        unique=False,
    )

    # PostgreSQL Row-Level Security on tenant-scoped tables
    tenant_tables = [
        "tenant_framework_adoptions",
        "tenant_control_overlays",
        "custom_controls",
        "control_mappings",
    ]
    for tbl in tenant_tables:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {tbl}_tenant_read ON {tbl}
            FOR SELECT
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                AND current_setting('app.tenant_verified', true) = 'true'
            )
            """
        )
        op.execute(
            f"""
            CREATE POLICY {tbl}_tenant_insert ON {tbl}
            FOR INSERT
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                AND current_setting('app.tenant_verified', true) = 'true'
            )
            """
        )
        op.execute(
            f"""
            CREATE POLICY {tbl}_tenant_update ON {tbl}
            FOR UPDATE
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                AND current_setting('app.tenant_verified', true) = 'true'
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                AND current_setting('app.tenant_verified', true) = 'true'
            )
            """
        )
        op.execute(
            f"""
            CREATE POLICY {tbl}_tenant_delete ON {tbl}
            FOR DELETE
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                AND current_setting('app.tenant_verified', true) = 'true'
            )
            """
        )


def downgrade() -> None:
    tenant_tables = [
        "control_mappings",
        "custom_controls",
        "tenant_control_overlays",
        "tenant_framework_adoptions",
    ]
    for tbl in tenant_tables:
        op.execute(f"DROP POLICY IF EXISTS {tbl}_tenant_delete ON {tbl}")
        op.execute(f"DROP POLICY IF EXISTS {tbl}_tenant_update ON {tbl}")
        op.execute(f"DROP POLICY IF EXISTS {tbl}_tenant_insert ON {tbl}")
        op.execute(f"DROP POLICY IF EXISTS {tbl}_tenant_read ON {tbl}")
        op.execute(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_control_mappings_tenant_target", table_name="control_mappings")
    op.drop_index("ix_control_mappings_tenant_source", table_name="control_mappings")
    op.drop_table("control_mappings")

    op.drop_index("ix_custom_controls_tenant_status", table_name="custom_controls")
    op.drop_table("custom_controls")

    op.drop_index("ix_tenant_control_overlays_tenant", table_name="tenant_control_overlays")
    op.drop_table("tenant_control_overlays")

    op.drop_index("ix_tenant_adoptions_tenant_framework", table_name="tenant_framework_adoptions")
    op.drop_table("tenant_framework_adoptions")

    op.drop_index("ix_canonical_controls_category", table_name="canonical_controls")
    op.drop_table("canonical_controls")

    op.drop_index("ix_framework_versions_state", table_name="framework_versions")
    op.drop_table("framework_versions")

    op.drop_table("frameworks")
