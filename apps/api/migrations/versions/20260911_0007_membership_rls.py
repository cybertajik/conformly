"""Add PostgreSQL row-level security for memberships.

Revision ID: 20260911_0007
Revises: 20260909_0006
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260911_0007"
down_revision: str | None = "20260909_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memberships FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY memberships_tenant_isolation ON memberships
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            AND (
                current_setting('app.tenant_verified', true) = 'true'
                OR user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
            )
        )
        WITH CHECK (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            AND current_setting('app.tenant_verified', true) = 'true'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS memberships_tenant_isolation ON memberships")
    op.execute("ALTER TABLE memberships NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memberships DISABLE ROW LEVEL SECURITY")
