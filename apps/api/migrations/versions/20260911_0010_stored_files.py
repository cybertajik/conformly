"""Add stored_files table with application-layer encryption metadata and tenant RLS.

Revision ID: 20260911_0010
Revises: 20260911_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0010"
down_revision: str | None = "20260911_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stored_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("plaintext_size_bytes", sa.Integer(), nullable=False),
        sa.Column("ciphertext_size_bytes", sa.Integer(), nullable=False),
        sa.Column("plaintext_sha256", sa.String(length=64), nullable=False),
        sa.Column("ciphertext_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_backend", sa.String(length=32), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("encryption_algorithm", sa.String(length=32), nullable=False),
        sa.Column("context_version", sa.Integer(), nullable=False),
        sa.Column("key_version", sa.String(length=64), nullable=False),
        sa.Column("wrapped_dek_nonce", sa.String(length=64), nullable=False),
        sa.Column("wrapped_dek", sa.Text(), nullable=False),
        sa.Column("ciphertext_nonce", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_stored_files_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_stored_files_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stored_files")),
        sa.UniqueConstraint("object_key", name=op.f("uq_stored_files_object_key")),
    )

    op.create_index(
        "ix_stored_files_tenant_created",
        "stored_files",
        ["tenant_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_stored_files_tenant_status",
        "stored_files",
        ["tenant_id", "status"],
        unique=False,
    )

    op.execute("ALTER TABLE stored_files ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE stored_files FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY stored_files_tenant_read ON stored_files
        FOR SELECT
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            AND current_setting('app.tenant_verified', true) = 'true'
        )
        """
    )
    op.execute(
        """
        CREATE POLICY stored_files_tenant_insert ON stored_files
        FOR INSERT
        WITH CHECK (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            AND current_setting('app.tenant_verified', true) = 'true'
        )
        """
    )
    op.execute(
        """
        CREATE POLICY stored_files_tenant_update ON stored_files
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
        """
        CREATE POLICY stored_files_tenant_delete ON stored_files
        FOR DELETE
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            AND current_setting('app.tenant_verified', true) = 'true'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS stored_files_tenant_delete ON stored_files")
    op.execute("DROP POLICY IF EXISTS stored_files_tenant_update ON stored_files")
    op.execute("DROP POLICY IF EXISTS stored_files_tenant_insert ON stored_files")
    op.execute("DROP POLICY IF EXISTS stored_files_tenant_read ON stored_files")
    op.execute("ALTER TABLE stored_files NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE stored_files DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_stored_files_tenant_status", table_name="stored_files")
    op.drop_index("ix_stored_files_tenant_created", table_name="stored_files")
    op.drop_table("stored_files")
