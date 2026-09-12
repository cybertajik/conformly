"""Enforce case-insensitive user email uniqueness.

Revision ID: 20260909_0004
Revises: 20260909_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0004"
down_revision: str | None = "20260909_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE users SET email = lower(trim(email))")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.create_index("uq_users_normalized_email", "users", [sa.text("lower(email)")], unique=True)


def downgrade() -> None:
    op.drop_index("uq_users_normalized_email", table_name="users")
    op.create_unique_constraint("uq_users_email", "users", ["email"])
