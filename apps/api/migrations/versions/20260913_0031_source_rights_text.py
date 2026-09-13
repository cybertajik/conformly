"""Preserve full framework rights notices without PostgreSQL varchar truncation."""

import sqlalchemy as sa
from alembic import op

revision = "20260913_0031"
down_revision = "20260913_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("source_requirements") as batch:
        batch.alter_column("content_rights", existing_type=sa.String(255), type_=sa.Text())


def downgrade() -> None:
    # PostgreSQL rejects overlong values instead of silently truncating legal notices.
    with op.batch_alter_table("source_requirements") as batch:
        batch.alter_column("content_rights", existing_type=sa.Text(), type_=sa.String(255))
