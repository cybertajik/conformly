"""Whistleblower anonymous reporting module with RLS.

Revision ID: 20260912_0015_whistleblower
Revises: 20260912_0014_pre_audit
Create Date: 2026-09-12

Creates five whistleblower tables:
- whistleblower_portals
- whistleblower_cases
- whistleblower_messages
- whistleblower_attachments
- whistleblower_case_assignments

All tables include tenant_id, PostgreSQL Row Level Security policies, and
FORCE ROW LEVEL SECURITY.  whistleblower_portals includes a public SELECT policy
for active portals.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260912_0015_whistleblower"
down_revision = "20260912_0014_pre_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── whistleblower_portals ─────────────────────────────────────────────
    op.create_table(
        "whistleblower_portals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("welcome_text", sa.Text(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
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
    )
    op.create_index(
        "ix_whistleblower_portals_tenant_id",
        "whistleblower_portals",
        ["tenant_id"],
    )
    op.create_index(
        "ix_whistleblower_portals_slug",
        "whistleblower_portals",
        ["slug"],
    )
    op.create_index(
        "ix_whistleblower_portals_is_active",
        "whistleblower_portals",
        ["is_active"],
    )
    op.create_index(
        "ix_whistleblower_portals_tenant_active",
        "whistleblower_portals",
        ["tenant_id", "is_active"],
    )

    # ── whistleblower_cases ───────────────────────────────────────────────
    op.create_table(
        "whistleblower_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "portal_id",
            sa.Uuid(),
            sa.ForeignKey("whistleblower_portals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("public_case_id", sa.String(32), unique=True, nullable=False),
        sa.Column("return_secret_salt", sa.String(64), nullable=False),
        sa.Column("return_secret_hash", sa.String(128), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="submitted",
        ),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("encrypted_summary", sa.JSON(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_reason", sa.Text(), nullable=True),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
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
    )
    op.create_index(
        "ix_whistleblower_cases_tenant_id",
        "whistleblower_cases",
        ["tenant_id"],
    )
    op.create_index(
        "ix_whistleblower_cases_portal_id",
        "whistleblower_cases",
        ["portal_id"],
    )
    op.create_index(
        "ix_whistleblower_cases_public_case_id",
        "whistleblower_cases",
        ["public_case_id"],
    )
    op.create_index(
        "ix_whistleblower_cases_status",
        "whistleblower_cases",
        ["status"],
    )
    op.create_index(
        "ix_whistleblower_cases_tenant_status",
        "whistleblower_cases",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_whistleblower_cases_tenant_created",
        "whistleblower_cases",
        ["tenant_id", "created_at"],
    )

    # ── whistleblower_messages ────────────────────────────────────────────
    op.create_table(
        "whistleblower_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.Uuid(),
            sa.ForeignKey("whistleblower_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender_type", sa.String(32), nullable=False),
        sa.Column("encrypted_body", sa.JSON(), nullable=False),
        sa.Column(
            "sent_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
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
    )
    op.create_index(
        "ix_whistleblower_messages_tenant_id",
        "whistleblower_messages",
        ["tenant_id"],
    )
    op.create_index(
        "ix_whistleblower_messages_case_id",
        "whistleblower_messages",
        ["case_id"],
    )
    op.create_index(
        "ix_whistleblower_messages_sent_by_user_id",
        "whistleblower_messages",
        ["sent_by_user_id"],
    )
    op.create_index(
        "ix_whistleblower_messages_case_created",
        "whistleblower_messages",
        ["case_id", "created_at"],
    )

    # ── whistleblower_attachments ─────────────────────────────────────────
    op.create_table(
        "whistleblower_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.Uuid(),
            sa.ForeignKey("whistleblower_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            sa.Uuid(),
            sa.ForeignKey("whistleblower_messages.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "file_id",
            sa.Uuid(),
            sa.ForeignKey("stored_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("uploaded_by", sa.String(32), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
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
    )
    op.create_index(
        "ix_whistleblower_attachments_tenant_id",
        "whistleblower_attachments",
        ["tenant_id"],
    )
    op.create_index(
        "ix_whistleblower_attachments_case_id",
        "whistleblower_attachments",
        ["case_id"],
    )
    op.create_index(
        "ix_whistleblower_attachments_message_id",
        "whistleblower_attachments",
        ["message_id"],
    )
    op.create_index(
        "ix_whistleblower_attachments_file_id",
        "whistleblower_attachments",
        ["file_id"],
    )

    # ── whistleblower_case_assignments ────────────────────────────────────
    op.create_table(
        "whistleblower_case_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.Uuid(),
            sa.ForeignKey("whistleblower_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "handler_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assigned_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_whistleblower_case_assignments_tenant_id",
        "whistleblower_case_assignments",
        ["tenant_id"],
    )
    op.create_index(
        "ix_whistleblower_case_assignments_case_id",
        "whistleblower_case_assignments",
        ["case_id"],
    )
    op.create_index(
        "ix_whistleblower_case_assignments_handler_user_id",
        "whistleblower_case_assignments",
        ["handler_user_id"],
    )
    op.create_index(
        "ix_whistleblower_assignments_case_handler",
        "whistleblower_case_assignments",
        ["case_id", "handler_user_id"],
    )

    # ── RLS policies (PostgreSQL only) ────────────────────────────────────
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        all_tables = [
            "whistleblower_portals",
            "whistleblower_cases",
            "whistleblower_messages",
            "whistleblower_attachments",
            "whistleblower_case_assignments",
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

        # Allow unauthenticated public discovery of active portals by slug
        op.execute(
            """
            CREATE POLICY whistleblower_portals_public_read ON whistleblower_portals
            FOR SELECT
            USING (is_active = true)
            """
        )


def downgrade() -> None:
    tables = [
        "whistleblower_case_assignments",
        "whistleblower_attachments",
        "whistleblower_messages",
        "whistleblower_cases",
        "whistleblower_portals",
    ]
    conn = op.get_bind()
    for tbl in tables:
        if conn.dialect.name == "postgresql":
            safe = tbl.replace("-", "_")
            if tbl == "whistleblower_portals":
                op.execute(
                    "DROP POLICY IF EXISTS whistleblower_portals_public_read "
                    "ON whistleblower_portals"
                )
            op.execute(f"DROP POLICY IF EXISTS {safe}_tenant_isolation ON {tbl}")
        op.drop_table(tbl)
