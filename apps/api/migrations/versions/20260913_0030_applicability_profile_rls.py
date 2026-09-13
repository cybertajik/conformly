"""Enforce tenant RLS on applicability profiles added in 0027."""

from alembic import op

revision = "20260913_0030"
down_revision = "20260913_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE tenant_applicability_profiles ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE tenant_applicability_profiles FORCE ROW LEVEL SECURITY")
        op.execute("""CREATE POLICY applicability_profiles_tenant ON tenant_applicability_profiles
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)""")
        op.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_applicability_profiles TO conformly_app"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP POLICY applicability_profiles_tenant ON tenant_applicability_profiles")
        op.execute("ALTER TABLE tenant_applicability_profiles NO FORCE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE tenant_applicability_profiles DISABLE ROW LEVEL SECURITY")
