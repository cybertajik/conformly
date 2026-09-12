"""Encrypt reporter-supplied whistleblower case metadata.

Revision ID: 20260912_0018
Revises: 20260912_0017_exports_and_retention
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260912_0018"
down_revision: str | None = "20260912_0017_exports_and_retention"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    encrypted_json = sa.JSON().with_variant(JSONB(), "postgresql")
    op.add_column(
        "whistleblower_cases",
        sa.Column("encrypted_category", encrypted_json, nullable=True),
    )
    op.add_column(
        "whistleblower_cases",
        sa.Column("encrypted_title", encrypted_json, nullable=True),
    )
    op.alter_column("whistleblower_cases", "category", existing_type=sa.String(100), nullable=True)
    op.alter_column("whistleblower_cases", "title", existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    # Downgrade is safe only before encrypted-only cases exist.
    op.alter_column("whistleblower_cases", "title", existing_type=sa.String(255), nullable=False)
    op.alter_column("whistleblower_cases", "category", existing_type=sa.String(100), nullable=False)
    op.drop_column("whistleblower_cases", "encrypted_title")
    op.drop_column("whistleblower_cases", "encrypted_category")
