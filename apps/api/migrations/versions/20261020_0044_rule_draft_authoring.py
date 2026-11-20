"""catalog rule draft authoring permissions and RLS policies (WP-07E)

Revision ID: 20261020_0044
Revises: 20261019_0043
Create Date: 2026-10-20 12:00:00.000000+00:00

WP-07E Synthetic ApplicabilityRule Draft Authoring:
- Narrowly scoped permissions and RLS policies for conformly_catalog_rule_author.
- Enforces strict synthetic-only boundaries: synthetic_rule_demo_ for sources and
  target requirements, synthetic_ for fact definitions and rules.
- Permission-only migration: no schema changes, no tables or columns added/dropped.
- Idempotent upgrade and downgrade with explicit column privilege revocation.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261020_0044"
down_revision: str | Sequence[str] | None = "20261019_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_NAME = "conformly_catalog_rule_author"

UPGRADE_SQL = """
DO $$
DECLARE
    role_exists boolean;
    role_flags record;
    membership_cnt integer;
    owned_cnt integer;
    has_create boolean;
BEGIN
    SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'conformly_catalog_rule_author') INTO role_exists;
    IF NOT role_exists THEN
        RAISE NOTICE 'Role conformly_catalog_rule_author does not exist, skipping rule author permissions and policies.';
        RETURN;
    END IF;

    -- Verify role safety attributes
    SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolinherit, rolreplication
    INTO role_flags
    FROM pg_catalog.pg_roles WHERE rolname = 'conformly_catalog_rule_author';

    IF role_flags.rolsuper OR role_flags.rolbypassrls OR role_flags.rolcreatedb 
       OR role_flags.rolcreaterole OR role_flags.rolinherit OR role_flags.rolreplication THEN
        RAISE EXCEPTION 'Unsafe role conformly_catalog_rule_author: possesses elevated attributes';
    END IF;

    SELECT count(*) INTO membership_cnt FROM pg_catalog.pg_auth_members m
    JOIN pg_catalog.pg_roles r ON r.oid = m.member WHERE r.rolname = 'conformly_catalog_rule_author';
    IF membership_cnt > 0 THEN
        RAISE EXCEPTION 'Unsafe role conformly_catalog_rule_author: has role memberships';
    END IF;

    SELECT count(*) INTO owned_cnt FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_roles r ON r.oid = c.relowner WHERE r.rolname = 'conformly_catalog_rule_author';
    IF owned_cnt > 0 THEN
        RAISE EXCEPTION 'Unsafe role conformly_catalog_rule_author: owns objects';
    END IF;

    SELECT pg_catalog.has_schema_privilege('conformly_catalog_rule_author', 'public', 'CREATE') INTO has_create;
    IF has_create THEN
        RAISE EXCEPTION 'Unsafe role conformly_catalog_rule_author: has CREATE on public schema';
    END IF;

    -- 1. Table Grants
    -- Group A: Read-only on sources, requirements, permissions, and fact definitions
    GRANT SELECT ON public.catalog_sources TO "conformly_catalog_rule_author";
    GRANT SELECT ON public.catalog_source_versions TO "conformly_catalog_rule_author";
    GRANT SELECT ON public.catalog_requirements TO "conformly_catalog_rule_author";
    GRANT SELECT ON public.catalog_requirement_versions TO "conformly_catalog_rule_author";
    GRANT SELECT ON public.catalog_requirement_source_references TO "conformly_catalog_rule_author";
    GRANT SELECT ON public.catalog_source_permission_decisions TO "conformly_catalog_rule_author";
    GRANT SELECT ON public.catalog_fact_definitions TO "conformly_catalog_rule_author";
    GRANT SELECT ON public.catalog_fact_definition_versions TO "conformly_catalog_rule_author";
    GRANT SELECT ON public.catalog_fact_definition_scopes TO "conformly_catalog_rule_author";
    GRANT SELECT ON public.catalog_fact_definition_enum_values TO "conformly_catalog_rule_author";

    -- Group B: Source permission guards (SELECT + UPDATE(updated_at) for row locking)
    GRANT SELECT ON public.catalog_source_permission_guards TO "conformly_catalog_rule_author";
    GRANT UPDATE(updated_at) ON public.catalog_source_permission_guards TO "conformly_catalog_rule_author";

    -- Group C: Applicability rules tables (SELECT, INSERT, and UPDATE(updated_at) on parent/version)
    GRANT SELECT, INSERT ON public.catalog_applicability_rules TO "conformly_catalog_rule_author";
    GRANT UPDATE(updated_at) ON public.catalog_applicability_rules TO "conformly_catalog_rule_author";

    GRANT SELECT, INSERT ON public.catalog_applicability_rule_versions TO "conformly_catalog_rule_author";
    GRANT UPDATE(updated_at) ON public.catalog_applicability_rule_versions TO "conformly_catalog_rule_author";

    GRANT SELECT, INSERT ON public.catalog_applicability_rule_fact_refs TO "conformly_catalog_rule_author";
    GRANT SELECT, INSERT ON public.catalog_applicability_rule_source_refs TO "conformly_catalog_rule_author";

    -- Group D: Support tables (audits, receipts, intents)
    GRANT SELECT, INSERT ON public.catalog_audit_heads TO "conformly_catalog_rule_author";
    GRANT UPDATE(current_sequence, head_hash, updated_at) ON public.catalog_audit_heads TO "conformly_catalog_rule_author";

    GRANT SELECT, INSERT ON public.catalog_audit_events TO "conformly_catalog_rule_author";

    GRANT SELECT, INSERT ON public.catalog_mutation_receipts TO "conformly_catalog_rule_author";
    GRANT UPDATE(created_at) ON public.catalog_mutation_receipts TO "conformly_catalog_rule_author";

    GRANT SELECT, INSERT ON public.catalog_event_intents TO "conformly_catalog_rule_author";

    -- Group E: EXECUTE only on the 4 rule append/sequence trigger functions
    GRANT EXECUTE ON FUNCTION public.catalog_app_rule_append_only() TO "conformly_catalog_rule_author";
    GRANT EXECUTE ON FUNCTION public.catalog_app_rule_version_sequence_guard() TO "conformly_catalog_rule_author";
    GRANT EXECUTE ON FUNCTION public.catalog_app_rule_fact_ref_sequence_guard() TO "conformly_catalog_rule_author";
    GRANT EXECUTE ON FUNCTION public.catalog_app_rule_source_ref_sequence_guard() TO "conformly_catalog_rule_author";

    -- 2. Named RLS Policies (all prefixed wp07e_rule_author_*)
    -- Sources
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_sources' AND tablename = 'catalog_sources') THEN
        CREATE POLICY wp07e_rule_author_sources ON public.catalog_sources
        FOR SELECT TO "conformly_catalog_rule_author"
        USING (left(source_key, 20) = 'synthetic_rule_demo_');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_source_versions' AND tablename = 'catalog_source_versions') THEN
        CREATE POLICY wp07e_rule_author_source_versions ON public.catalog_source_versions
        FOR SELECT TO "conformly_catalog_rule_author"
        USING (EXISTS (
            SELECT 1 FROM public.catalog_sources s
            WHERE s.id = catalog_source_versions.source_id
            AND left(s.source_key, 20) = 'synthetic_rule_demo_'
        ));
    END IF;

    -- Requirements (R5: check requirement_key AND parent source lineage)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_requirements' AND tablename = 'catalog_requirements') THEN
        CREATE POLICY wp07e_rule_author_requirements ON public.catalog_requirements
        FOR SELECT TO "conformly_catalog_rule_author"
        USING (
            left(requirement_key, 20) = 'synthetic_rule_demo_'
            AND EXISTS (
                SELECT 1 FROM public.catalog_sources s
                WHERE s.id = catalog_requirements.source_id
                AND left(s.source_key, 20) = 'synthetic_rule_demo_'
            )
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_requirement_versions' AND tablename = 'catalog_requirement_versions') THEN
        CREATE POLICY wp07e_rule_author_requirement_versions ON public.catalog_requirement_versions
        FOR SELECT TO "conformly_catalog_rule_author"
        USING (EXISTS (
            SELECT 1 FROM public.catalog_requirements r
            JOIN public.catalog_sources s ON s.id = r.source_id
            JOIN public.catalog_source_versions sv ON sv.id = catalog_requirement_versions.source_version_id
            JOIN public.catalog_sources sv_s ON sv_s.id = sv.source_id
            WHERE r.id = catalog_requirement_versions.requirement_id
            AND s.id = catalog_requirement_versions.source_id
            AND left(r.requirement_key, 20) = 'synthetic_rule_demo_'
            AND left(s.source_key, 20) = 'synthetic_rule_demo_'
            AND left(sv_s.source_key, 20) = 'synthetic_rule_demo_'
        ));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_req_source_refs' AND tablename = 'catalog_requirement_source_references') THEN
        CREATE POLICY wp07e_rule_author_req_source_refs ON public.catalog_requirement_source_references
        FOR SELECT TO "conformly_catalog_rule_author"
        USING (EXISTS (
            SELECT 1 FROM public.catalog_requirement_versions rv
            JOIN public.catalog_requirements r ON r.id = rv.requirement_id
            JOIN public.catalog_sources s ON s.id = r.source_id
            JOIN public.catalog_source_versions sv ON sv.id = catalog_requirement_source_references.source_version_id
            JOIN public.catalog_sources sv_s ON sv_s.id = sv.source_id
            WHERE rv.id = catalog_requirement_source_references.requirement_version_id
            AND left(r.requirement_key, 20) = 'synthetic_rule_demo_'
            AND left(s.source_key, 20) = 'synthetic_rule_demo_'
            AND left(sv_s.source_key, 20) = 'synthetic_rule_demo_'
        ));
    END IF;

    -- Permissions
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_permission_decisions' AND tablename = 'catalog_source_permission_decisions') THEN
        CREATE POLICY wp07e_rule_author_permission_decisions ON public.catalog_source_permission_decisions
        FOR SELECT TO "conformly_catalog_rule_author"
        USING (EXISTS (
            SELECT 1 FROM public.catalog_source_versions sv
            JOIN public.catalog_sources s ON s.id = sv.source_id
            WHERE sv.id = catalog_source_permission_decisions.source_version_id
            AND left(s.source_key, 20) = 'synthetic_rule_demo_'
        ));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_permission_guards' AND tablename = 'catalog_source_permission_guards') THEN
        CREATE POLICY wp07e_rule_author_permission_guards ON public.catalog_source_permission_guards
        FOR ALL TO "conformly_catalog_rule_author"
        USING (EXISTS (
            SELECT 1 FROM public.catalog_sources s
            WHERE s.id = catalog_source_permission_guards.source_id
            AND left(s.source_key, 20) = 'synthetic_rule_demo_'
        ))
        WITH CHECK (EXISTS (
            SELECT 1 FROM public.catalog_sources s
            WHERE s.id = catalog_source_permission_guards.source_id
            AND left(s.source_key, 20) = 'synthetic_rule_demo_'
        ));
    END IF;

    -- Fact definitions
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_fact_definitions' AND tablename = 'catalog_fact_definitions') THEN
        CREATE POLICY wp07e_rule_author_fact_definitions ON public.catalog_fact_definitions
        FOR SELECT TO "conformly_catalog_rule_author"
        USING (left(fact_key, 10) = 'synthetic_');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_fact_versions' AND tablename = 'catalog_fact_definition_versions') THEN
        CREATE POLICY wp07e_rule_author_fact_versions ON public.catalog_fact_definition_versions
        FOR SELECT TO "conformly_catalog_rule_author"
        USING (EXISTS (
            SELECT 1 FROM public.catalog_fact_definitions fd
            WHERE fd.id = catalog_fact_definition_versions.fact_definition_id
            AND left(fd.fact_key, 10) = 'synthetic_'
        ));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_fact_scopes' AND tablename = 'catalog_fact_definition_scopes') THEN
        CREATE POLICY wp07e_rule_author_fact_scopes ON public.catalog_fact_definition_scopes
        FOR SELECT TO "conformly_catalog_rule_author"
        USING (EXISTS (
            SELECT 1 FROM public.catalog_fact_definition_versions fv
            JOIN public.catalog_fact_definitions fd ON fd.id = fv.fact_definition_id
            WHERE fv.id = catalog_fact_definition_scopes.fact_definition_version_id
            AND left(fd.fact_key, 10) = 'synthetic_'
        ));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_fact_enum_values' AND tablename = 'catalog_fact_definition_enum_values') THEN
        CREATE POLICY wp07e_rule_author_fact_enum_values ON public.catalog_fact_definition_enum_values
        FOR SELECT TO "conformly_catalog_rule_author"
        USING (EXISTS (
            SELECT 1 FROM public.catalog_fact_definition_versions fv
            JOIN public.catalog_fact_definitions fd ON fd.id = fv.fact_definition_id
            WHERE fv.id = catalog_fact_definition_enum_values.fact_definition_version_id
            AND left(fd.fact_key, 10) = 'synthetic_'
        ));
    END IF;

    -- Applicability rules (R5: require synthetic rule prefix AND synthetic parent requirement with synthetic source)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_rules' AND tablename = 'catalog_applicability_rules') THEN
        CREATE POLICY wp07e_rule_author_rules ON public.catalog_applicability_rules
        FOR ALL TO "conformly_catalog_rule_author"
        USING (
            left(rule_key, 10) = 'synthetic_' AND EXISTS (
                SELECT 1 FROM public.catalog_requirements r
                JOIN public.catalog_sources s ON s.id = r.source_id
                WHERE r.id = catalog_applicability_rules.requirement_id
                AND left(r.requirement_key, 20) = 'synthetic_rule_demo_'
                AND left(s.source_key, 20) = 'synthetic_rule_demo_'
            )
        )
        WITH CHECK (
            left(rule_key, 10) = 'synthetic_' AND EXISTS (
                SELECT 1 FROM public.catalog_requirements r
                JOIN public.catalog_sources s ON s.id = r.source_id
                WHERE r.id = catalog_applicability_rules.requirement_id
                AND left(r.requirement_key, 20) = 'synthetic_rule_demo_'
                AND left(s.source_key, 20) = 'synthetic_rule_demo_'
            )
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_rule_versions' AND tablename = 'catalog_applicability_rule_versions') THEN
        CREATE POLICY wp07e_rule_author_rule_versions ON public.catalog_applicability_rule_versions
        FOR ALL TO "conformly_catalog_rule_author"
        USING (
            EXISTS (
                SELECT 1 FROM public.catalog_applicability_rules r
                WHERE r.id = catalog_applicability_rule_versions.rule_id
                AND left(r.rule_key, 10) = 'synthetic_'
            )
            AND EXISTS (
                SELECT 1 FROM public.catalog_requirement_versions rv
                JOIN public.catalog_requirements req ON req.id = rv.requirement_id
                JOIN public.catalog_sources s ON s.id = req.source_id
                WHERE rv.id = catalog_applicability_rule_versions.requirement_version_id
                AND left(req.requirement_key, 20) = 'synthetic_rule_demo_'
                AND left(s.source_key, 20) = 'synthetic_rule_demo_'
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM public.catalog_applicability_rules r
                WHERE r.id = catalog_applicability_rule_versions.rule_id
                AND left(r.rule_key, 10) = 'synthetic_'
            )
            AND EXISTS (
                SELECT 1 FROM public.catalog_requirement_versions rv
                JOIN public.catalog_requirements req ON req.id = rv.requirement_id
                JOIN public.catalog_sources s ON s.id = req.source_id
                WHERE rv.id = catalog_applicability_rule_versions.requirement_version_id
                AND left(req.requirement_key, 20) = 'synthetic_rule_demo_'
                AND left(s.source_key, 20) = 'synthetic_rule_demo_'
            )
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_rule_fact_refs' AND tablename = 'catalog_applicability_rule_fact_refs') THEN
        CREATE POLICY wp07e_rule_author_rule_fact_refs ON public.catalog_applicability_rule_fact_refs
        FOR ALL TO "conformly_catalog_rule_author"
        USING (
            EXISTS (
                SELECT 1 FROM public.catalog_applicability_rule_versions rv
                JOIN public.catalog_applicability_rules r ON r.id = rv.rule_id
                WHERE rv.id = catalog_applicability_rule_fact_refs.rule_version_id
                AND left(r.rule_key, 10) = 'synthetic_'
            )
            AND EXISTS (
                SELECT 1 FROM public.catalog_fact_definition_versions fv
                JOIN public.catalog_fact_definitions fd ON fd.id = fv.fact_definition_id
                WHERE fv.id = catalog_applicability_rule_fact_refs.fact_definition_version_id
                AND left(fd.fact_key, 10) = 'synthetic_'
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM public.catalog_applicability_rule_versions rv
                JOIN public.catalog_applicability_rules r ON r.id = rv.rule_id
                WHERE rv.id = catalog_applicability_rule_fact_refs.rule_version_id
                AND left(r.rule_key, 10) = 'synthetic_'
            )
            AND EXISTS (
                SELECT 1 FROM public.catalog_fact_definition_versions fv
                JOIN public.catalog_fact_definitions fd ON fd.id = fv.fact_definition_id
                WHERE fv.id = catalog_applicability_rule_fact_refs.fact_definition_version_id
                AND left(fd.fact_key, 10) = 'synthetic_'
            )
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_rule_source_refs' AND tablename = 'catalog_applicability_rule_source_refs') THEN
        CREATE POLICY wp07e_rule_author_rule_source_refs ON public.catalog_applicability_rule_source_refs
        FOR ALL TO "conformly_catalog_rule_author"
        USING (
            EXISTS (
                SELECT 1 FROM public.catalog_applicability_rule_versions rv
                JOIN public.catalog_applicability_rules r ON r.id = rv.rule_id
                WHERE rv.id = catalog_applicability_rule_source_refs.rule_version_id
                AND left(r.rule_key, 10) = 'synthetic_'
            )
            AND EXISTS (
                SELECT 1 FROM public.catalog_source_versions sv
                JOIN public.catalog_sources s ON s.id = sv.source_id
                WHERE sv.id = catalog_applicability_rule_source_refs.source_version_id
                AND left(s.source_key, 20) = 'synthetic_rule_demo_'
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM public.catalog_applicability_rule_versions rv
                JOIN public.catalog_applicability_rules r ON r.id = rv.rule_id
                WHERE rv.id = catalog_applicability_rule_source_refs.rule_version_id
                AND left(r.rule_key, 10) = 'synthetic_'
            )
            AND EXISTS (
                SELECT 1 FROM public.catalog_source_versions sv
                JOIN public.catalog_sources s ON s.id = sv.source_id
                WHERE sv.id = catalog_applicability_rule_source_refs.source_version_id
                AND left(s.source_key, 20) = 'synthetic_rule_demo_'
            )
        );
    END IF;

    -- Audits & support tables
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_audit_heads' AND tablename = 'catalog_audit_heads') THEN
        CREATE POLICY wp07e_rule_author_audit_heads ON public.catalog_audit_heads
        FOR ALL TO "conformly_catalog_rule_author"
        USING (chain_key = 'applicability-rule-draft-v1')
        WITH CHECK (chain_key = 'applicability-rule-draft-v1');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_audit_events' AND tablename = 'catalog_audit_events') THEN
        CREATE POLICY wp07e_rule_author_audit_events ON public.catalog_audit_events
        FOR ALL TO "conformly_catalog_rule_author"
        USING (chain_key = 'applicability-rule-draft-v1')
        WITH CHECK (chain_key = 'applicability-rule-draft-v1');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_mutation_receipts' AND tablename = 'catalog_mutation_receipts') THEN
        CREATE POLICY wp07e_rule_author_mutation_receipts ON public.catalog_mutation_receipts
        FOR ALL TO "conformly_catalog_rule_author"
        USING (operation = 'applicability_rule.create_draft' AND result_type = 'ApplicabilityRuleVersion')
        WITH CHECK (operation = 'applicability_rule.create_draft' AND result_type = 'ApplicabilityRuleVersion');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'wp07e_rule_author_event_intents' AND tablename = 'catalog_event_intents') THEN
        CREATE POLICY wp07e_rule_author_event_intents ON public.catalog_event_intents
        FOR ALL TO "conformly_catalog_rule_author"
        USING (aggregate_type = 'ApplicabilityRuleVersion' AND event_kind = 'ApplicabilityRuleDraftCreated')
        WITH CHECK (aggregate_type = 'ApplicabilityRuleVersion' AND event_kind = 'ApplicabilityRuleDraftCreated');
    END IF;

END $$;
"""

DOWNGRADE_SQL = """
DO $$
DECLARE
    role_exists boolean;
BEGIN
    -- Drop all 19 named policies IF EXISTS
    DROP POLICY IF EXISTS wp07e_rule_author_sources ON public.catalog_sources;
    DROP POLICY IF EXISTS wp07e_rule_author_source_versions ON public.catalog_source_versions;
    DROP POLICY IF EXISTS wp07e_rule_author_requirements ON public.catalog_requirements;
    DROP POLICY IF EXISTS wp07e_rule_author_requirement_versions ON public.catalog_requirement_versions;
    DROP POLICY IF EXISTS wp07e_rule_author_req_source_refs ON public.catalog_requirement_source_references;
    DROP POLICY IF EXISTS wp07e_rule_author_permission_decisions ON public.catalog_source_permission_decisions;
    DROP POLICY IF EXISTS wp07e_rule_author_permission_guards ON public.catalog_source_permission_guards;
    DROP POLICY IF EXISTS wp07e_rule_author_fact_definitions ON public.catalog_fact_definitions;
    DROP POLICY IF EXISTS wp07e_rule_author_fact_versions ON public.catalog_fact_definition_versions;
    DROP POLICY IF EXISTS wp07e_rule_author_fact_scopes ON public.catalog_fact_definition_scopes;
    DROP POLICY IF EXISTS wp07e_rule_author_fact_enum_values ON public.catalog_fact_definition_enum_values;
    DROP POLICY IF EXISTS wp07e_rule_author_rules ON public.catalog_applicability_rules;
    DROP POLICY IF EXISTS wp07e_rule_author_rule_versions ON public.catalog_applicability_rule_versions;
    DROP POLICY IF EXISTS wp07e_rule_author_rule_fact_refs ON public.catalog_applicability_rule_fact_refs;
    DROP POLICY IF EXISTS wp07e_rule_author_rule_source_refs ON public.catalog_applicability_rule_source_refs;
    DROP POLICY IF EXISTS wp07e_rule_author_audit_heads ON public.catalog_audit_heads;
    DROP POLICY IF EXISTS wp07e_rule_author_audit_events ON public.catalog_audit_events;
    DROP POLICY IF EXISTS wp07e_rule_author_mutation_receipts ON public.catalog_mutation_receipts;
    DROP POLICY IF EXISTS wp07e_rule_author_event_intents ON public.catalog_event_intents;

    SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'conformly_catalog_rule_author') INTO role_exists;
    IF role_exists THEN
        -- Explicitly revoke column-level UPDATE grants
        REVOKE UPDATE (updated_at) ON public.catalog_source_permission_guards FROM "conformly_catalog_rule_author";
        REVOKE UPDATE (updated_at) ON public.catalog_applicability_rules FROM "conformly_catalog_rule_author";
        REVOKE UPDATE (updated_at) ON public.catalog_applicability_rule_versions FROM "conformly_catalog_rule_author";
        REVOKE UPDATE (current_sequence, head_hash, updated_at) ON public.catalog_audit_heads FROM "conformly_catalog_rule_author";
        REVOKE UPDATE (created_at) ON public.catalog_mutation_receipts FROM "conformly_catalog_rule_author";

        -- Revoke all table privileges
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_sources FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_source_versions FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_requirements FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_requirement_versions FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_requirement_source_references FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_source_permission_decisions FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_source_permission_guards FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_fact_definitions FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_fact_definition_versions FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_fact_definition_scopes FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_fact_definition_enum_values FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_applicability_rules FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_applicability_rule_versions FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_applicability_rule_fact_refs FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_applicability_rule_source_refs FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_audit_heads FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_audit_events FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_mutation_receipts FROM "conformly_catalog_rule_author";
        REVOKE ALL PRIVILEGES ON TABLE public.catalog_event_intents FROM "conformly_catalog_rule_author";

        -- Revoke execute on the 4 rule functions
        REVOKE ALL ON FUNCTION public.catalog_app_rule_append_only() FROM "conformly_catalog_rule_author";
        REVOKE ALL ON FUNCTION public.catalog_app_rule_version_sequence_guard() FROM "conformly_catalog_rule_author";
        REVOKE ALL ON FUNCTION public.catalog_app_rule_fact_ref_sequence_guard() FROM "conformly_catalog_rule_author";
        REVOKE ALL ON FUNCTION public.catalog_app_rule_source_ref_sequence_guard() FROM "conformly_catalog_rule_author";
    END IF;
END $$;
"""


def upgrade() -> None:
    conn = op.get_bind()
    if conn and getattr(conn.dialect, "name", "") == "postgresql":
        op.execute(UPGRADE_SQL)


def downgrade() -> None:
    conn = op.get_bind()
    if conn and getattr(conn.dialect, "name", "") == "postgresql":
        op.execute(DOWNGRADE_SQL)
