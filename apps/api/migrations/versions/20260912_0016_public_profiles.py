"""Public profile and compliance trust center with RLS.

Revision ID: 20260912_0016_public_profiles
Revises: 20260912_0015_whistleblower
Create Date: 2026-09-12

Creates three public profile tables:
- public_profiles
- public_credentials
- public_statements

All tables include tenant_id, PostgreSQL Row Level Security policies, and
FORCE ROW LEVEL SECURITY.  Explicit public SELECT policies allow unauthenticated
reading of published profiles, active visible credentials, and visible statements.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260912_0016_public_profiles"
down_revision = "20260912_0015_whistleblower"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── public_profiles ───────────────────────────────────────────────────
    op.create_table(
        "public_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("slug", sa.String(128), unique=True, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.String(1024), nullable=True),
        sa.Column("website_url", sa.String(1024), nullable=True),
        sa.Column("primary_contact_email", sa.String(255), nullable=True),
        sa.Column(
            "is_published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_public_profiles_tenant_id",
        "public_profiles",
        ["tenant_id"],
        unique=True,
    )
    op.create_index(
        "ix_public_profiles_slug",
        "public_profiles",
        ["slug"],
        unique=True,
    )

    # ── public_credentials ────────────────────────────────────────────────
    op.create_table(
        "public_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("public_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("credential_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("issuer_name", sa.String(255), nullable=False),
        sa.Column("scope_description", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="active",
        ),
        sa.Column("verification_url", sa.String(1024), nullable=True),
        sa.Column(
            "source_certificate_id",
            sa.Uuid(),
            sa.ForeignKey("pre_audit_certificates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_publicly_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_public_credentials_profile_id",
        "public_credentials",
        ["profile_id"],
    )
    op.create_index(
        "ix_public_credentials_tenant_id",
        "public_credentials",
        ["tenant_id"],
    )

    # ── public_statements ─────────────────────────────────────────────────
    op.create_table(
        "public_statements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("public_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("statement_content", sa.Text(), nullable=False),
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_publicly_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_public_statements_profile_id",
        "public_statements",
        ["profile_id"],
    )
    op.create_index(
        "ix_public_statements_tenant_id",
        "public_statements",
        ["tenant_id"],
    )

    # ── Row Level Security (PostgreSQL) ───────────────────────────────────
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        all_tables = [
            "public_profiles",
            "public_credentials",
            "public_statements",
        ]
        for tbl in all_tables:
            safe = tbl.replace("-", "_")
            op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"""
                CREATE POLICY {safe}_tenant_isolation ON {tbl}
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

        # Allow unauthenticated public discovery of published profiles
        op.execute(
            """
            CREATE POLICY public_profiles_public_read ON public_profiles
            FOR SELECT
            USING (is_published = true)
            """
        )

        # Allow unauthenticated public reading of active, visible credentials
        op.execute(
            """
            CREATE POLICY public_credentials_public_read ON public_credentials
            FOR SELECT
            USING (is_publicly_visible = true AND status = 'active')
            """
        )

        # Allow unauthenticated public reading of visible statements
        op.execute(
            """
            CREATE POLICY public_statements_public_read ON public_statements
            FOR SELECT
            USING (is_publicly_visible = true)
            """
        )


def downgrade() -> None:
    tables = [
        "public_statements",
        "public_credentials",
        "public_profiles",
    ]
    conn = op.get_bind()
    for tbl in tables:
        if conn.dialect.name == "postgresql":
            safe = tbl.replace("-", "_")
            if tbl == "public_profiles":
                op.execute("DROP POLICY IF EXISTS public_profiles_public_read ON public_profiles")
            elif tbl == "public_credentials":
                op.execute(
                    "DROP POLICY IF EXISTS public_credentials_public_read ON public_credentials"
                )
            elif tbl == "public_statements":
                op.execute(
                    "DROP POLICY IF EXISTS public_statements_public_read ON public_statements"
                )
            op.execute(f"DROP POLICY IF EXISTS {safe}_tenant_isolation ON {tbl}")
        op.drop_table(tbl)
