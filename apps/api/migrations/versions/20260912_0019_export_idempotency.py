"""Add tenant-scoped export idempotency keys.

Revision ID: 20260912_0019
Revises: 20260912_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0019"
down_revision: str | None = "20260912_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("export_jobs") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(64), nullable=True))

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(
            "UPDATE export_jobs SET idempotency_key = "
            "md5(tenant_id::text || '-' || id::text) || md5(id::text || '-export')"
        )
    else:
        op.execute("UPDATE export_jobs SET idempotency_key = lower(hex(randomblob(32)))")

    with op.batch_alter_table("export_jobs") as batch_op:
        batch_op.alter_column("idempotency_key", nullable=False)
        batch_op.create_unique_constraint(
            "uq_export_jobs_tenant_idempotency",
            ["tenant_id", "idempotency_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("export_jobs") as batch_op:
        batch_op.drop_constraint("uq_export_jobs_tenant_idempotency", type_="unique")
        batch_op.drop_column("idempotency_key")
