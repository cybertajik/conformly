"""Enforce one active adoption per tenant and framework."""

import sqlalchemy as sa
from alembic import op

revision = "20260912_0013"
down_revision = "20260912_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_tenant_framework_active_adoption",
        "tenant_framework_adoptions",
        ["tenant_id", "framework_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_tenant_framework_active_adoption", table_name="tenant_framework_adoptions")
