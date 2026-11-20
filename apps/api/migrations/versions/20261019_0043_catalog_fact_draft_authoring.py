"""catalog fact draft authoring permissions and RLS policies (WP-07D)

Revision ID: 20261019_0043
Revises: 20261017_0042
Create Date: 2026-10-19 20:20:00.000000+00:00

WP-07D Consolidated Repair 1:
- Configures column-scoped privileges for conformly_catalog_fact_author.
- Enforces RLS policies restricting author to synthetic_-prefixed identities and versions.
- Safe offline SQL execution (R5): executes identical guarded logic via PL/pgSQL blocks.
- Explicit column-grant revocation on downgrade (R7).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261019_0043"
down_revision: str | Sequence[str] | None = "20261017_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_NAME = "conformly_catalog_fact_author"

UPGRADE_SQL = """
DO $$
DECLARE
    role_exists boolean;
    role_flags record;
    membership_cnt integer;
    owned_cnt integer;
    has_create boolean;
BEGIN
    SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'conformly_catalog_fact_author') INTO role_exists;
    IF NOT role_exists THEN
        RAISE NOTICE 'Role conformly_catalog_fact_author does not exist, skipping author permissions and policies.';
        RETURN;
    END IF;

    -- Verify role safety attributes
    SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolinherit, rolreplication
    INTO role_flags
    FROM pg_catalog.pg_roles WHERE rolname = 'conformly_catalog_fact_author';

    IF role_flags.rolsuper OR role_flags.rolbypassrls OR role_flags.rolcreatedb 
       OR role_flags.rolcreaterole OR role_flags.rolinherit OR role_flags.rolreplication THEN
        RAISE EXCEPTION 'Unsafe role conformly_catalog_fact_author: possesses elevated attributes';
    END IF;

    SELECT count(*) INTO membership_cnt FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles r ON r.oid = m.member WHERE r.rolname = 'conformly_catalog_fact_author';
    IF membership_cnt > 0 THEN
        RAISE EXCEPTION 'Unsafe role conformly_catalog_fact_author: has role memberships';
    END IF;

    SELECT count(*) INTO owned_cnt FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_roles r ON r.oid = c.relowner WHERE r.rolname = 'conformly_catalog_fact_author';
    IF owned_cnt > 0 THEN
        RAISE EXCEPTION 'Unsafe role conformly_catalog_fact_author: owns objects';
    END IF;

    SELECT pg_catalog.has_schema_privilege('conformly_catalog_fact_author', 'public', 'CREATE') INTO has_create;
    IF has_create THEN
        RAISE EXCEPTION 'Unsafe role conformly_catalog_fact_author: has CREATE on public schema';
    END IF;

    -- 1. Exact Column Grants on Fact Tables
    GRANT SELECT, INSERT ON public.catalog_fact_definitions TO "conformly_catalog_fact_author";
    GRANT UPDATE(updated_at) ON public.catalog_fact_definitions TO "conformly_catalog_fact_author";

    GRANT SELECT, INSERT ON public.catalog_fact_definition_versions TO "conformly_catalog_fact_author";
    GRANT UPDATE(updated_at) ON public.catalog_fact_definition_versions TO "conformly_catalog_fact_author";

    GRANT SELECT, INSERT ON public.catalog_fact_definition_scopes TO "conformly_catalog_fact_author";
    GRANT SELECT, INSERT ON public.catalog_fact_definition_enum_values TO "conformly_catalog_fact_author";

    -- 2. Trigger functions EXECUTE grants
    GRANT EXECUTE ON FUNCTION public.catalog_fact_definition_append_only() TO "conformly_catalog_fact_author";
    GRANT EXECUTE ON FUNCTION public.catalog_fact_definition_version_sequence_guard() TO "conformly_catalog_fact_author";
    GRANT EXECUTE ON FUNCTION public.catalog_fact_definition_scope_sequence_guard() TO "conformly_catalog_fact_author";
    GRANT EXECUTE ON FUNCTION public.catalog_fact_definition_enum_value_sequence_guard() TO "conformly_catalog_fact_author";

    -- 3. Exact Column Grants on Support Tables
    GRANT SELECT, INSERT ON public.catalog_audit_heads TO "conformly_catalog_fact_author";
    GRANT UPDATE(current_sequence, head_hash, updated_at) ON public.catalog_audit_heads TO "conformly_catalog_fact_author";

    GRANT SELECT, INSERT ON public.catalog_audit_events TO "conformly_catalog_fact_author";

    GRANT SELECT, INSERT ON public.catalog_mutation_receipts TO "conformly_catalog_fact_author";
    GRANT UPDATE(created_at) ON public.catalog_mutation_receipts TO "conformly_catalog_fact_author";

    GRANT SELECT, INSERT ON public.catalog_event_intents TO "conformly_catalog_fact_author";

    -- 4. 8 Named RLS Policies (wp07d_fact_author_*)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07d_fact_author_definitions' AND tablename = 'catalog_fact_definitions') THEN
        CREATE POLICY wp07d_fact_author_definitions ON public.catalog_fact_definitions
        FOR ALL TO "conformly_catalog_fact_author"
        USING (left(fact_key, 10) = 'synthetic_')
        WITH CHECK (left(fact_key, 10) = 'synthetic_');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07d_fact_author_versions' AND tablename = 'catalog_fact_definition_versions') THEN
        CREATE POLICY wp07d_fact_author_versions ON public.catalog_fact_definition_versions
        FOR ALL TO "conformly_catalog_fact_author"
        USING (EXISTS (
            SELECT 1 FROM public.catalog_fact_definitions d
            WHERE d.id = catalog_fact_definition_versions.fact_definition_id
            AND left(d.fact_key, 10) = 'synthetic_'
        ))
        WITH CHECK (EXISTS (
            SELECT 1 FROM public.catalog_fact_definitions d
            WHERE d.id = catalog_fact_definition_versions.fact_definition_id
            AND left(d.fact_key, 10) = 'synthetic_'
        ));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07d_fact_author_scopes' AND tablename = 'catalog_fact_definition_scopes') THEN
        CREATE POLICY wp07d_fact_author_scopes ON public.catalog_fact_definition_scopes
        FOR ALL TO "conformly_catalog_fact_author"
        USING (EXISTS (
            SELECT 1 FROM public.catalog_fact_definition_versions v
            JOIN public.catalog_fact_definitions d ON d.id = v.fact_definition_id
            WHERE v.id = catalog_fact_definition_scopes.fact_definition_version_id
            AND left(d.fact_key, 10) = 'synthetic_'
        ))
        WITH CHECK (EXISTS (
            SELECT 1 FROM public.catalog_fact_definition_versions v
            JOIN public.catalog_fact_definitions d ON d.id = v.fact_definition_id
            WHERE v.id = catalog_fact_definition_scopes.fact_definition_version_id
            AND left(d.fact_key, 10) = 'synthetic_'
        ));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07d_fact_author_enum_values' AND tablename = 'catalog_fact_definition_enum_values') THEN
        CREATE POLICY wp07d_fact_author_enum_values ON public.catalog_fact_definition_enum_values
        FOR ALL TO "conformly_catalog_fact_author"
        USING (EXISTS (
            SELECT 1 FROM public.catalog_fact_definition_versions v
            JOIN public.catalog_fact_definitions d ON d.id = v.fact_definition_id
            WHERE v.id = catalog_fact_definition_enum_values.fact_definition_version_id
            AND left(d.fact_key, 10) = 'synthetic_'
        ))
        WITH CHECK (EXISTS (
            SELECT 1 FROM public.catalog_fact_definition_versions v
            JOIN public.catalog_fact_definitions d ON d.id = v.fact_definition_id
            WHERE v.id = catalog_fact_definition_enum_values.fact_definition_version_id
            AND left(d.fact_key, 10) = 'synthetic_'
        ));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07d_fact_author_audit_heads' AND tablename = 'catalog_audit_heads') THEN
        CREATE POLICY wp07d_fact_author_audit_heads ON public.catalog_audit_heads
        FOR ALL TO "conformly_catalog_fact_author"
        USING (chain_key = 'fact-definition-draft-v1')
        WITH CHECK (chain_key = 'fact-definition-draft-v1');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07d_fact_author_audit_events' AND tablename = 'catalog_audit_events') THEN
        CREATE POLICY wp07d_fact_author_audit_events ON public.catalog_audit_events
        FOR ALL TO "conformly_catalog_fact_author"
        USING (chain_key = 'fact-definition-draft-v1')
        WITH CHECK (chain_key = 'fact-definition-draft-v1');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07d_fact_author_mutation_receipts' AND tablename = 'catalog_mutation_receipts') THEN
        CREATE POLICY wp07d_fact_author_mutation_receipts ON public.catalog_mutation_receipts
        FOR ALL TO "conformly_catalog_fact_author"
        USING (operation = 'fact_definition.create_draft' AND result_type = 'FactDefinitionVersion')
        WITH CHECK (operation = 'fact_definition.create_draft' AND result_type = 'FactDefinitionVersion');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07d_fact_author_event_intents' AND tablename = 'catalog_event_intents') THEN
        CREATE POLICY wp07d_fact_author_event_intents ON public.catalog_event_intents
        FOR ALL TO "conformly_catalog_fact_author"
        USING (aggregate_type = 'FactDefinitionVersion' AND event_kind = 'FactDefinitionDraftCreated')
        WITH CHECK (aggregate_type = 'FactDefinitionVersion' AND event_kind = 'FactDefinitionDraftCreated');
    END IF;
END $$;
"""

DOWNGRADE_SQL = """
DO $$
DECLARE
    role_exists boolean;
BEGIN
    -- Drop all 8 policies IF EXISTS
    DROP POLICY IF EXISTS wp07d_fact_author_definitions ON public.catalog_fact_definitions;
    DROP POLICY IF EXISTS wp07d_fact_author_versions ON public.catalog_fact_definition_versions;
    DROP POLICY IF EXISTS wp07d_fact_author_scopes ON public.catalog_fact_definition_scopes;
    DROP POLICY IF EXISTS wp07d_fact_author_enum_values ON public.catalog_fact_definition_enum_values;
    DROP POLICY IF EXISTS wp07d_fact_author_audit_heads ON public.catalog_audit_heads;
    DROP POLICY IF EXISTS wp07d_fact_author_audit_events ON public.catalog_audit_events;
    DROP POLICY IF EXISTS wp07d_fact_author_mutation_receipts ON public.catalog_mutation_receipts;
    DROP POLICY IF EXISTS wp07d_fact_author_event_intents ON public.catalog_event_intents;

    SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'conformly_catalog_fact_author') INTO role_exists;
    IF role_exists THEN
        -- R7: Explicitly revoke column-level UPDATE grants
        REVOKE UPDATE (updated_at) ON public.catalog_fact_definitions FROM "conformly_catalog_fact_author";
        REVOKE UPDATE (updated_at) ON public.catalog_fact_definition_versions FROM "conformly_catalog_fact_author";
        REVOKE UPDATE (current_sequence, head_hash, updated_at) ON public.catalog_audit_heads FROM "conformly_catalog_fact_author";
        REVOKE UPDATE (created_at) ON public.catalog_mutation_receipts FROM "conformly_catalog_fact_author";

        -- Revoke all table privileges
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_fact_definitions FROM "conformly_catalog_fact_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_fact_definition_versions FROM "conformly_catalog_fact_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_fact_definition_scopes FROM "conformly_catalog_fact_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_fact_definition_enum_values FROM "conformly_catalog_fact_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_audit_heads FROM "conformly_catalog_fact_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_audit_events FROM "conformly_catalog_fact_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_mutation_receipts FROM "conformly_catalog_fact_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_event_intents FROM "conformly_catalog_fact_author";

        -- Revoke execute on functions
        REVOKE ALL ON FUNCTION public.catalog_fact_definition_append_only() FROM "conformly_catalog_fact_author";
        REVOKE ALL ON FUNCTION public.catalog_fact_definition_version_sequence_guard() FROM "conformly_catalog_fact_author";
        REVOKE ALL ON FUNCTION public.catalog_fact_definition_scope_sequence_guard() FROM "conformly_catalog_fact_author";
        REVOKE ALL ON FUNCTION public.catalog_fact_definition_enum_value_sequence_guard() FROM "conformly_catalog_fact_author";
    END IF;
END $$;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
