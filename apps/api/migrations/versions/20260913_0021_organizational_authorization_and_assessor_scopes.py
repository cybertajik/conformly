"""Add is_external_advisor, expires_at, and is_workforce to memberships.

Revision ID: 20260913_0021
Revises: 20260912_0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0021"
down_revision: str | None = "20260912_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_external_advisor",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "expires_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "is_workforce",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            )
        )
        batch_op.create_index(
            "ix_memberships_tenant_expires",
            ["tenant_id", "expires_at"],
        )


def downgrade() -> None:
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.drop_index("ix_memberships_tenant_expires")
        batch_op.drop_column("is_workforce")
        batch_op.drop_column("expires_at")
        batch_op.drop_column("is_external_advisor")
