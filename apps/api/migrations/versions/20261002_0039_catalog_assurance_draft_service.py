"""Catalog assurance draft service foundation, role permissions, and parent freeze.

Revision ID: 20261002_0039
Revises: 20261002_0038
Create Date: 2026-10-16 00:30:00.000000+00:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20261002_0039"
down_revision = "20261002_0038"
branch_labels = None
depends_on = None

TABLES = (
    "catalog_evidence_requirement_versions",
    "catalog_evidence_requirement_artifact_types",
    "catalog_evidence_requirement_metadata_keys",
    "catalog_assessment_procedure_versions",
    "catalog_assessment_procedure_steps",
    "catalog_assessment_procedure_evidence_requirements",
)


def upgrade() -> None:
    # 1. Forward-recovery refusal if any assurance content table is already populated
    op.execute("""
        DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM public.catalog_assessment_procedure_evidence_requirements)
           OR EXISTS (SELECT 1 FROM public.catalog_assessment_procedure_steps)
           OR EXISTS (SELECT 1 FROM public.catalog_assessment_procedure_versions)
           OR EXISTS (SELECT 1 FROM public.catalog_evidence_requirement_metadata_keys)
           OR EXISTS (SELECT 1 FROM public.catalog_evidence_requirement_artifact_types)
           OR EXISTS (SELECT 1 FROM public.catalog_evidence_requirement_versions) THEN
            RAISE EXCEPTION 'V2 assurance content foundation contains rows before service grant; forward recovery required';
        END IF;
        END $$;
    """)

    # 2. Role boundary: conformly_catalog execution role
    # When role conformly_catalog exists, grant reviewed privileges, RLS policies, and trigger function execution
    op.execute("""
        DO $$
        DECLARE
            tbl text;
            root_tbls text[] := ARRAY[
                'catalog_evidence_requirement_versions',
                'catalog_assessment_procedure_versions'
            ];
            child_tbls text[] := ARRAY[
                'catalog_evidence_requirement_artifact_types',
                'catalog_evidence_requirement_metadata_keys',
                'catalog_assessment_procedure_steps',
                'catalog_assessment_procedure_evidence_requirements'
            ];
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_catalog') THEN
                -- Root tables: SELECT, INSERT, UPDATE (UPDATE needed for parent row locking and superseded_by_version_id)
                FOREACH tbl IN ARRAY root_tbls LOOP
                    EXECUTE format('GRANT SELECT, INSERT, UPDATE ON TABLE public.%I TO conformly_catalog', tbl);
                    EXECUTE format('DROP POLICY IF EXISTS catalog_role_access ON public.%I', tbl);
                    EXECUTE format('CREATE POLICY catalog_role_access ON public.%I TO conformly_catalog USING (true) WITH CHECK (true)', tbl);
                END LOOP;

                -- Child tables: SELECT, INSERT only
                FOREACH tbl IN ARRAY child_tbls LOOP
                    EXECUTE format('GRANT SELECT, INSERT ON TABLE public.%I TO conformly_catalog', tbl);
                    EXECUTE format('DROP POLICY IF EXISTS catalog_role_access ON public.%I', tbl);
                    EXECUTE format('CREATE POLICY catalog_role_access ON public.%I TO conformly_catalog USING (true) WITH CHECK (true)', tbl);
                END LOOP;

                -- Trigger functions: EXECUTE on 7 WP-06A trigger functions
                EXECUTE 'GRANT EXECUTE ON FUNCTION public.catalog_assurance_content_append_only() TO conformly_catalog';
                EXECUTE 'GRANT EXECUTE ON FUNCTION public.catalog_evidence_requirement_version_sequence_guard() TO conformly_catalog';
                EXECUTE 'GRANT EXECUTE ON FUNCTION public.catalog_er_artifact_type_sequence_guard() TO conformly_catalog';
                EXECUTE 'GRANT EXECUTE ON FUNCTION public.catalog_er_metadata_key_sequence_guard() TO conformly_catalog';
                EXECUTE 'GRANT EXECUTE ON FUNCTION public.catalog_assessment_procedure_version_sequence_guard() TO conformly_catalog';
                EXECUTE 'GRANT EXECUTE ON FUNCTION public.catalog_ap_step_sequence_guard() TO conformly_catalog';
                EXECUTE 'GRANT EXECUTE ON FUNCTION public.catalog_ap_evidence_req_sequence_guard() TO conformly_catalog';
            END IF;
        END $$;
    """)

    # 3. Parent ControlVersion freeze trigger
    # Reconstructible digest pin: reject UPDATE on catalog_control_versions if any assurance root references it
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_control_version_assurance_freeze()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog
        AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.catalog_evidence_requirement_versions
                WHERE control_version_id = OLD.id
            ) OR EXISTS (
                SELECT 1 FROM public.catalog_assessment_procedure_versions
                WHERE control_version_id = OLD.id
            ) THEN
                RAISE EXCEPTION 'Cannot modify control version %: assurance content is frozen', OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION public.catalog_control_version_assurance_freeze() FROM PUBLIC"
    )
    op.execute("""
        DROP TRIGGER IF EXISTS trg_catalog_control_version_assurance_freeze ON public.catalog_control_versions;
        CREATE TRIGGER trg_catalog_control_version_assurance_freeze
        BEFORE UPDATE ON public.catalog_control_versions
        FOR EACH ROW EXECUTE FUNCTION public.catalog_control_version_assurance_freeze();
    """)
    op.execute("""
        DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_catalog') THEN
            GRANT EXECUTE ON FUNCTION public.catalog_control_version_assurance_freeze() TO conformly_catalog;
        END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("SET LOCAL row_security = off")
    op.execute(
        "LOCK TABLE "
        "public.catalog_assessment_procedure_evidence_requirements, "
        "public.catalog_assessment_procedure_steps, "
        "public.catalog_assessment_procedure_versions, "
        "public.catalog_evidence_requirement_metadata_keys, "
        "public.catalog_evidence_requirement_artifact_types, "
        "public.catalog_evidence_requirement_versions "
        "IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM public.catalog_assessment_procedure_evidence_requirements)
           OR EXISTS (SELECT 1 FROM public.catalog_assessment_procedure_steps)
           OR EXISTS (SELECT 1 FROM public.catalog_assessment_procedure_versions)
           OR EXISTS (SELECT 1 FROM public.catalog_evidence_requirement_metadata_keys)
           OR EXISTS (SELECT 1 FROM public.catalog_evidence_requirement_artifact_types)
           OR EXISTS (SELECT 1 FROM public.catalog_evidence_requirement_versions) THEN
            RAISE EXCEPTION 'V2 assurance draft service foundation is populated; forward recovery required';
        END IF;
        END $$;
    """)

    # Drop parent control version freeze trigger and function
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_control_version_assurance_freeze ON public.catalog_control_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS public.catalog_control_version_assurance_freeze()")

    # Remove catalog role policies and privileges if conformly_catalog exists
    op.execute("""
        DO $$
        DECLARE
            tbl text;
            tables text[] := ARRAY[
                'catalog_evidence_requirement_versions',
                'catalog_evidence_requirement_artifact_types',
                'catalog_evidence_requirement_metadata_keys',
                'catalog_assessment_procedure_versions',
                'catalog_assessment_procedure_steps',
                'catalog_assessment_procedure_evidence_requirements'
            ];
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_catalog') THEN
                FOREACH tbl IN ARRAY tables LOOP
                    EXECUTE format('DROP POLICY IF EXISTS catalog_role_access ON public.%I', tbl);
                    EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.%I FROM conformly_catalog', tbl);
                END LOOP;

                REVOKE EXECUTE ON FUNCTION public.catalog_assurance_content_append_only() FROM conformly_catalog;
                REVOKE EXECUTE ON FUNCTION public.catalog_evidence_requirement_version_sequence_guard() FROM conformly_catalog;
                REVOKE EXECUTE ON FUNCTION public.catalog_er_artifact_type_sequence_guard() FROM conformly_catalog;
                REVOKE EXECUTE ON FUNCTION public.catalog_er_metadata_key_sequence_guard() FROM conformly_catalog;
                REVOKE EXECUTE ON FUNCTION public.catalog_assessment_procedure_version_sequence_guard() FROM conformly_catalog;
                REVOKE EXECUTE ON FUNCTION public.catalog_ap_step_sequence_guard() FROM conformly_catalog;
                REVOKE EXECUTE ON FUNCTION public.catalog_ap_evidence_req_sequence_guard() FROM conformly_catalog;
            END IF;
        END $$;
    """)
