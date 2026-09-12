"""Permit read-only discovery of a user's own memberships.

Revision ID: 20260911_0008
Revises: 20260911_0007
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260911_0008"
down_revision: str | None = "20260911_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE POLICY memberships_own_discovery ON memberships
        FOR SELECT
        USING (
            current_setting('app.tenant_verified', true) = 'false'
            AND user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS memberships_own_discovery ON memberships")
