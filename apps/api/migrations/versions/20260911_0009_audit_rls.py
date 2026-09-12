"""Add tenant isolation RLS to audit events.

Revision ID: 20260911_0009
Revises: 20260911_0008
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260911_0009"
down_revision: str | None = "20260911_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_events_tenant_read ON audit_events
        FOR SELECT
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            AND current_setting('app.tenant_verified', true) = 'true'
        )
        """
    )
    op.execute(
        """
        CREATE POLICY audit_events_append ON audit_events
        FOR INSERT
        WITH CHECK (
            tenant_id IS NULL
            OR (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                AND current_setting('app.tenant_verified', true) = 'true'
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_events_append ON audit_events")
    op.execute("DROP POLICY IF EXISTS audit_events_tenant_read ON audit_events")
    op.execute("ALTER TABLE audit_events NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY")
