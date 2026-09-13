"""Audit hash chaining and immutable sealing.

Revision ID: 20260913_0024
Revises: 20260913_0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0024"
down_revision: str | None = "20260913_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Extend audit_events with hash chain fields
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.add_column(
            sa.Column("sequence_number", sa.Integer(), server_default="1", nullable=False)
        )
        batch_op.add_column(
            sa.Column("prev_hash", sa.String(length=64), server_default="0" * 64, nullable=False)
        )
        batch_op.add_column(
            sa.Column("event_hash", sa.String(length=64), server_default="", nullable=False)
        )
        batch_op.create_index("ix_audit_events_tenant_seq", ["tenant_id", "sequence_number"])

    # 2. Create audit_seals table
    op.create_table(
        "audit_seals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("start_sequence", sa.Integer(), nullable=False),
        sa.Column("end_sequence", sa.Integer(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("head_event_hash", sa.String(length=64), nullable=False),
        sa.Column("merkle_root", sa.String(length=64), nullable=False),
        sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sealed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("seal_signature_digest", sa.String(length=64), nullable=False),
        sa.Column("storage_object_id", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_seals_tenant_seq", "audit_seals", ["tenant_id", "end_sequence"])

    # 3. RLS policy for audit_seals in PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE audit_seals ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE audit_seals FORCE ROW LEVEL SECURITY;")
        op.execute(
            """
            CREATE POLICY audit_seals_tenant_isolation ON audit_seals
                FOR ALL
                USING (
                    tenant_id IS NULL OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                );
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS audit_seals_tenant_isolation ON audit_seals;")

    op.drop_index("ix_audit_seals_tenant_seq", table_name="audit_seals")
    op.drop_table("audit_seals")

    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.drop_index("ix_audit_events_tenant_seq")
        batch_op.drop_column("event_hash")
        batch_op.drop_column("prev_hash")
        batch_op.drop_column("sequence_number")
