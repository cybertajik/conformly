"""Align models with Product Source of Truth (Trello V4.0).

Adds Legal Entities, Business Units, Locations, Tenant Entitlements,
Risks, Risk Treatments, Assets, Vendors, and updates Membership roles.

Revision ID: 20260912_0020
Revises: 20260912_0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0020"
down_revision: str | None = "20260912_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. legal_entities ──────────────────────────────────────────────────
    op.create_table(
        "legal_entities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("registration_number", sa.String(100), nullable=True),
        sa.Column("country", sa.String(2), server_default="DE", nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_legal_entities_tenant_id", "legal_entities", ["tenant_id"])

    # ── 2. business_units ──────────────────────────────────────────────────
    op.create_table(
        "business_units",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "legal_entity_id",
            sa.Uuid(),
            sa.ForeignKey("legal_entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_business_units_tenant_id", "business_units", ["tenant_id"])
    op.create_index(
        "ix_business_units_legal_entity_id", "business_units", ["legal_entity_id"]
    )

    # ── 3. locations ───────────────────────────────────────────────────────
    op.create_table(
        "locations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "legal_entity_id",
            sa.Uuid(),
            sa.ForeignKey("legal_entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("country", sa.String(2), server_default="DE", nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("address", sa.String(300), nullable=True),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_locations_tenant_id", "locations", ["tenant_id"])
    op.create_index("ix_locations_legal_entity_id", "locations", ["legal_entity_id"])

    # ── 4. update memberships ──────────────────────────────────────────────
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.add_column(
            sa.Column(
                "legal_entity_id",
                sa.Uuid(),
                sa.ForeignKey("legal_entities.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "business_unit_id",
                sa.Uuid(),
                sa.ForeignKey("business_units.id", ondelete="SET NULL"),
                nullable=True,
            )
        )

    # Migrate any legacy role names in memberships
    op.execute("UPDATE memberships SET role = 'reviewer' WHERE role = 'auditor'")
    op.execute("UPDATE memberships SET role = 'control_owner' WHERE role = 'contributor'")
    op.execute("UPDATE memberships SET role = 'employee' WHERE role = 'viewer'")

    # ── 5. tenant_entitlements ─────────────────────────────────────────────
    op.create_table(
        "tenant_entitlements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("plan_code", sa.String(50), server_default="tier_a", nullable=False),
        sa.Column("enabled_modules", sa.JSON(), nullable=False),
        sa.Column("max_members", sa.Integer(), server_default="100", nullable=False),
        sa.Column(
            "max_storage_bytes",
            sa.BigInteger(),
            server_default="10737418240",
            nullable=False,
        ),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_tenant_entitlements_tenant_id", "tenant_entitlements", ["tenant_id"], unique=True
    )

    # ── 6. risks ───────────────────────────────────────────────────────────
    op.create_table(
        "risks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("likelihood", sa.Integer(), nullable=False),
        sa.Column("impact", sa.Integer(), nullable=False),
        sa.Column("inherent_score", sa.Integer(), nullable=False),
        sa.Column("residual_score", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "owner_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("control_id", sa.Uuid(), nullable=True),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_risks_tenant_id", "risks", ["tenant_id"])
    op.create_index("ix_risks_tenant_status", "risks", ["tenant_id", "status"])

    # ── 7. risk_treatments ─────────────────────────────────────────────────
    op.create_table(
        "risk_treatments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "risk_id",
            sa.Uuid(),
            sa.ForeignKey("risks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("strategy", sa.String(32), nullable=False),
        sa.Column("treatment_plan", sa.Text(), nullable=False),
        sa.Column("target_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), server_default="planned", nullable=False),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_risk_treatments_tenant_id", "risk_treatments", ["tenant_id"])
    op.create_index("ix_risk_treatments_risk_id", "risk_treatments", ["risk_id"])

    # ── 8. assets ──────────────────────────────────────────────────────────
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("asset_type", sa.String(32), nullable=False),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "owner_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(32), nullable=False),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_assets_tenant_id", "assets", ["tenant_id"])
    op.create_index("ix_assets_tenant_type", "assets", ["tenant_id", "asset_type"])

    # ── 9. vendors ─────────────────────────────────────────────────────────
    op.create_table(
        "vendors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("service_description", sa.Text(), nullable=False),
        sa.Column("criticality", sa.String(32), nullable=False),
        sa.Column(
            "data_classification_accessed",
            sa.String(50),
            server_default="Confidential",
            nullable=False,
        ),
        sa.Column("country_residency", sa.String(50), server_default="DE", nullable=False),
        sa.Column("dpa_signed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("security_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_vendors_tenant_id", "vendors", ["tenant_id"])
    op.create_index("ix_vendors_tenant_criticality", "vendors", ["tenant_id", "criticality"])

    # ── 10. PostgreSQL RLS Policies ────────────────────────────────────────
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        new_tenant_tables = [
            "legal_entities",
            "business_units",
            "locations",
            "tenant_entitlements",
            "risks",
            "risk_treatments",
            "assets",
            "vendors",
        ]
        for tbl in new_tenant_tables:
            safe = tbl.replace("-", "_")
            op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"""
                CREATE POLICY {safe}_tenant_isolation ON {tbl}
                FOR ALL
                USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
                """
            )


def downgrade() -> None:
    tables = [
        "vendors",
        "assets",
        "risk_treatments",
        "risks",
        "tenant_entitlements",
        "locations",
        "business_units",
        "legal_entities",
    ]
    conn = op.get_bind()
    for tbl in tables:
        if conn.dialect.name == "postgresql":
            safe = tbl.replace("-", "_")
            op.execute(f"DROP POLICY IF EXISTS {safe}_tenant_isolation ON {tbl}")
        op.drop_table(tbl)

    with op.batch_alter_table("memberships") as batch_op:
        batch_op.drop_column("business_unit_id")
        batch_op.drop_column("legal_entity_id")
