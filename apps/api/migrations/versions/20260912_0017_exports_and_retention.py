"""Exports, retention, and deletion lifecycle with RLS.

Revision ID: 20260912_0017_exports_and_retention
Revises: 20260912_0016_public_profiles
Create Date: 2026-09-12

Creates four export and retention tables:
- export_jobs
- export_manifests
- deletion_jobs
- deletion_proofs

Adds legal_hold column to tenants table.
All new tables include tenant_id, PostgreSQL Row Level Security policies, and
FORCE ROW LEVEL SECURITY for strict multi-tenant isolation.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260912_0017_exports_and_retention"
down_revision = "20260912_0016_public_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        # Alembic defaults version_num to VARCHAR(32), but this historical
        # revision identifier is longer. Widen the column before it is stored.
        op.alter_column(
            "alembic_version",
            "version_num",
            existing_type=sa.String(32),
            type_=sa.String(128),
            existing_nullable=False,
        )

    # ── Add legal_hold to tenants ─────────────────────────────────────────
    op.add_column(
        "tenants",
        sa.Column(
            "legal_hold",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # ── export_jobs ───────────────────────────────────────────────────────
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requested_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "scope",
            sa.String(32),
            nullable=False,
            server_default="full",
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "stored_file_id",
            sa.Uuid(),
            sa.ForeignKey("stored_files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("records_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("files_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sha256_hash", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_export_jobs_tenant_created",
        "export_jobs",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_export_jobs_tenant_status",
        "export_jobs",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_export_jobs_expires_at",
        "export_jobs",
        ["expires_at"],
    )

    # ── export_manifests ──────────────────────────────────────────────────
    op.create_table(
        "export_manifests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "export_job_id",
            sa.Uuid(),
            sa.ForeignKey("export_jobs.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "dataset_versions",
            JSONB().with_variant(sa.Text(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "file_hashes",
            JSONB().with_variant(sa.Text(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "record_counts",
            JSONB().with_variant(sa.Text(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "audit_references",
            JSONB().with_variant(sa.Text(), "sqlite"),
            nullable=False,
        ),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_export_manifests_tenant_job",
        "export_manifests",
        ["tenant_id", "export_job_id"],
    )

    # ── deletion_jobs ─────────────────────────────────────────────────────
    op.create_table(
        "deletion_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.String(32),
            nullable=False,
            server_default="cancellation",
        ),
        sa.Column(
            "state",
            sa.String(32),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("proof_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_deletion_jobs_tenant_scheduled",
        "deletion_jobs",
        ["tenant_id", "scheduled_at"],
    )
    op.create_index(
        "ix_deletion_jobs_state",
        "deletion_jobs",
        ["state"],
    )

    # ── deletion_proofs ───────────────────────────────────────────────────
    op.create_table(
        "deletion_proofs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("deletion_job_id", sa.Uuid(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tables_purged",
            JSONB().with_variant(sa.Text(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "storage_objects_purged",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("proof_manifest_sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_deletion_proofs_tenant",
        "deletion_proofs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_deletion_proofs_deleted_at",
        "deletion_proofs",
        ["deleted_at"],
    )

    # ── Row Level Security (PostgreSQL) ───────────────────────────────────
    if conn.dialect.name == "postgresql":
        all_tables = [
            "export_jobs",
            "export_manifests",
            "deletion_jobs",
            "deletion_proofs",
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


def downgrade() -> None:
    tables = [
        "deletion_proofs",
        "deletion_jobs",
        "export_manifests",
        "export_jobs",
    ]
    conn = op.get_bind()
    for tbl in tables:
        if conn.dialect.name == "postgresql":
            safe = tbl.replace("-", "_")
            op.execute(f"DROP POLICY IF EXISTS {safe}_tenant_isolation ON {tbl}")
        op.drop_table(tbl)

    op.drop_column("tenants", "legal_hold")
