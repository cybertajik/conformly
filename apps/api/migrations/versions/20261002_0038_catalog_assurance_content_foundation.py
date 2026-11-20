"""Add dormant assurance content foundation tables (evidence requirements and assessment procedures)."""

import sqlalchemy as sa
from alembic import op

revision = "20261002_0038"
down_revision = "20260930_0037"
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
    # 1. catalog_evidence_requirement_versions
    op.create_table(
        "catalog_evidence_requirement_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("control_version_id", sa.Uuid(), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_key", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("frequency", sa.String(32), nullable=False),
        sa.Column("custom_frequency", sa.String(256), nullable=True),
        sa.Column("scope_state", sa.String(16), nullable=False),
        sa.Column("scope_guidance", sa.String(2048), nullable=True),
        sa.Column("assurance_purpose", sa.String(32), nullable=False),
        sa.Column("validity_rule", sa.String(32), nullable=False),
        sa.Column("max_age_days", sa.Integer(), nullable=True),
        sa.Column(
            "missing_data_behavior",
            sa.String(32),
            server_default="requires_human_review",
            nullable=False,
        ),
        sa.Column("guidance", sa.String(4096), nullable=True),
        sa.Column("status", sa.String(16), server_default="Draft", nullable=False),
        sa.Column("content_digest", sa.LargeBinary(), nullable=False),
        sa.Column(
            "digest_schema",
            sa.String(64),
            server_default="catalog-assurance-draft-v1",
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["control_version_id", "control_id"],
            ["catalog_control_versions.id", "catalog_control_versions.control_id"],
            name="fk_catalog_er_versions_control_version_lineage",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "id", "control_version_id", name="uq_catalog_er_versions_id_control_version"
        ),
        sa.UniqueConstraint(
            "control_version_id",
            "requirement_key",
            name="uq_catalog_er_versions_control_version_key",
        ),
        sa.UniqueConstraint(
            "control_version_id", "sequence", name="uq_catalog_er_versions_control_version_seq"
        ),
        sa.CheckConstraint("requirement_key ~ '^ER-[A-Z0-9_-]{3,61}$'", name="er_key_format"),
        sa.CheckConstraint("length(requirement_key) BETWEEN 6 AND 64", name="er_key_length"),
        sa.CheckConstraint("sequence > 0", name="er_sequence_positive"),
        sa.CheckConstraint("length(trim(title)) BETWEEN 1 AND 512", name="er_title_length"),
        sa.CheckConstraint(
            "frequency IN ('continuous', 'event_driven', 'monthly', 'quarterly', 'semiannual', 'annual', 'custom')",
            name="known_er_frequency",
        ),
        sa.CheckConstraint(
            "(frequency = 'custom' AND custom_frequency IS NOT NULL AND length(trim(custom_frequency)) BETWEEN 1 AND 256) "
            "OR (frequency <> 'custom' AND custom_frequency IS NULL)",
            name="er_frequency_shape",
        ),
        sa.CheckConstraint(
            "scope_state IN ('All', 'Conditional')",
            name="known_er_scope_state",
        ),
        sa.CheckConstraint(
            "(scope_state = 'Conditional' AND scope_guidance IS NOT NULL AND length(trim(scope_guidance)) BETWEEN 1 AND 2048) "
            "OR (scope_state = 'All' AND scope_guidance IS NULL)",
            name="er_scope_shape",
        ),
        sa.CheckConstraint(
            "assurance_purpose IN ('design', 'implementation', 'operating_effectiveness', 'combined')",
            name="known_assurance_purpose",
        ),
        sa.CheckConstraint(
            "validity_rule IN ('point_in_time', 'period_coverage', 'continuous', 'event_driven')",
            name="known_validity_rule",
        ),
        sa.CheckConstraint(
            "(validity_rule = 'point_in_time' AND max_age_days IS NOT NULL AND max_age_days BETWEEN 1 AND 3660) "
            "OR (validity_rule <> 'point_in_time' AND max_age_days IS NULL)",
            name="er_validity_shape",
        ),
        sa.CheckConstraint(
            "missing_data_behavior = 'requires_human_review'",
            name="er_missing_data_behavior",
        ),
        sa.CheckConstraint(
            "guidance IS NULL OR length(trim(guidance)) BETWEEN 1 AND 4096",
            name="er_guidance_length",
        ),
        sa.CheckConstraint("status = 'Draft'", name="er_draft_only"),
        sa.CheckConstraint("length(content_digest) = 32", name="er_digest_32_bytes"),
        sa.CheckConstraint(
            "digest_schema = 'catalog-assurance-draft-v1'", name="er_known_digest_schema"
        ),
    )

    # 2. catalog_evidence_requirement_artifact_types
    op.create_table(
        "catalog_evidence_requirement_artifact_types",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("evidence_requirement_version_id", sa.Uuid(), nullable=False),
        sa.Column("control_version_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["evidence_requirement_version_id", "control_version_id"],
            [
                "catalog_evidence_requirement_versions.id",
                "catalog_evidence_requirement_versions.control_version_id",
            ],
            name="fk_catalog_er_art_types_er_version_lineage",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "evidence_requirement_version_id",
            "sequence",
            name="uq_catalog_er_art_types_version_seq",
        ),
        sa.UniqueConstraint(
            "evidence_requirement_version_id",
            "artifact_type",
            name="uq_catalog_er_art_types_version_type",
        ),
        sa.CheckConstraint("sequence BETWEEN 1 AND 16", name="er_artifact_type_sequence_bounds"),
        sa.CheckConstraint(
            "artifact_type IN ('document', 'record', 'configuration', 'log', 'ticket', 'report', 'attestation', 'observation', 'interview', 'other')",
            name="known_er_artifact_type",
        ),
    )

    # 3. catalog_evidence_requirement_metadata_keys
    op.create_table(
        "catalog_evidence_requirement_metadata_keys",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("evidence_requirement_version_id", sa.Uuid(), nullable=False),
        sa.Column("control_version_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("metadata_key", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["evidence_requirement_version_id", "control_version_id"],
            [
                "catalog_evidence_requirement_versions.id",
                "catalog_evidence_requirement_versions.control_version_id",
            ],
            name="fk_catalog_er_meta_keys_er_version_lineage",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "evidence_requirement_version_id",
            "sequence",
            name="uq_catalog_er_meta_keys_version_seq",
        ),
        sa.UniqueConstraint(
            "evidence_requirement_version_id",
            "metadata_key",
            name="uq_catalog_er_meta_keys_version_key",
        ),
        sa.CheckConstraint("sequence BETWEEN 1 AND 32", name="er_metadata_key_sequence_bounds"),
        sa.CheckConstraint(
            "metadata_key ~ '^[a-z][a-z0-9_]{0,63}$'", name="er_metadata_key_format"
        ),
        sa.CheckConstraint("length(metadata_key) BETWEEN 1 AND 64", name="er_metadata_key_length"),
    )

    # 4. catalog_assessment_procedure_versions
    op.create_table(
        "catalog_assessment_procedure_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("control_version_id", sa.Uuid(), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("procedure_key", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("objective", sa.String(4096), nullable=False),
        sa.Column("sample_guidance", sa.String(2048), nullable=True),
        sa.Column("scope_guidance", sa.String(2048), nullable=True),
        sa.Column("decision_guidance", sa.String(4096), nullable=False),
        sa.Column("assessor_qualifications", sa.String(2048), nullable=True),
        sa.Column(
            "missing_data_behavior",
            sa.String(32),
            server_default="requires_human_review",
            nullable=False,
        ),
        sa.Column("status", sa.String(16), server_default="Draft", nullable=False),
        sa.Column("content_digest", sa.LargeBinary(), nullable=False),
        sa.Column(
            "digest_schema",
            sa.String(64),
            server_default="catalog-assurance-draft-v1",
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["control_version_id", "control_id"],
            ["catalog_control_versions.id", "catalog_control_versions.control_id"],
            name="fk_catalog_ap_versions_control_version_lineage",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "id", "control_version_id", name="uq_catalog_ap_versions_id_control_version"
        ),
        sa.UniqueConstraint(
            "control_version_id", "procedure_key", name="uq_catalog_ap_versions_control_version_key"
        ),
        sa.UniqueConstraint(
            "control_version_id", "sequence", name="uq_catalog_ap_versions_control_version_seq"
        ),
        sa.CheckConstraint("procedure_key ~ '^AP-[A-Z0-9_-]{3,61}$'", name="ap_key_format"),
        sa.CheckConstraint("length(procedure_key) BETWEEN 6 AND 64", name="ap_key_length"),
        sa.CheckConstraint("sequence > 0", name="ap_sequence_positive"),
        sa.CheckConstraint("length(trim(title)) BETWEEN 1 AND 512", name="ap_title_length"),
        sa.CheckConstraint(
            "length(trim(objective)) BETWEEN 1 AND 4096", name="ap_objective_length"
        ),
        sa.CheckConstraint(
            "sample_guidance IS NULL OR length(trim(sample_guidance)) BETWEEN 1 AND 2048",
            name="ap_sample_guidance_length",
        ),
        sa.CheckConstraint(
            "scope_guidance IS NULL OR length(trim(scope_guidance)) BETWEEN 1 AND 2048",
            name="ap_scope_guidance_length",
        ),
        sa.CheckConstraint(
            "length(trim(decision_guidance)) BETWEEN 1 AND 4096",
            name="ap_decision_guidance_length",
        ),
        sa.CheckConstraint(
            "assessor_qualifications IS NULL OR length(trim(assessor_qualifications)) BETWEEN 1 AND 2048",
            name="ap_assessor_qualifications_length",
        ),
        sa.CheckConstraint(
            "missing_data_behavior = 'requires_human_review'",
            name="ap_missing_data_behavior",
        ),
        sa.CheckConstraint("status = 'Draft'", name="ap_draft_only"),
        sa.CheckConstraint("length(content_digest) = 32", name="ap_digest_32_bytes"),
        sa.CheckConstraint(
            "digest_schema = 'catalog-assurance-draft-v1'", name="ap_known_digest_schema"
        ),
    )

    # 5. catalog_assessment_procedure_steps
    op.create_table(
        "catalog_assessment_procedure_steps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("assessment_procedure_version_id", sa.Uuid(), nullable=False),
        sa.Column("control_version_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("step_kind", sa.String(32), nullable=False),
        sa.Column("instruction", sa.String(4096), nullable=False),
        sa.Column("expected_output", sa.String(2048), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["assessment_procedure_version_id", "control_version_id"],
            [
                "catalog_assessment_procedure_versions.id",
                "catalog_assessment_procedure_versions.control_version_id",
            ],
            name="fk_catalog_ap_steps_ap_version_lineage",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "assessment_procedure_version_id",
            "sequence",
            name="uq_catalog_ap_steps_version_seq",
        ),
        sa.CheckConstraint("sequence BETWEEN 1 AND 50", name="ap_step_sequence_bounds"),
        sa.CheckConstraint(
            "step_kind IN ('inspect', 'inquire', 'observe', 'reperform', 'analyze')",
            name="known_ap_step_kind",
        ),
        sa.CheckConstraint(
            "length(trim(instruction)) BETWEEN 1 AND 4096",
            name="ap_step_instruction_length",
        ),
        sa.CheckConstraint(
            "expected_output IS NULL OR length(trim(expected_output)) BETWEEN 1 AND 2048",
            name="ap_step_expected_output_length",
        ),
    )

    # 6. catalog_assessment_procedure_evidence_requirements
    op.create_table(
        "catalog_assessment_procedure_evidence_requirements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("assessment_procedure_version_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_requirement_version_id", sa.Uuid(), nullable=False),
        sa.Column("control_version_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["assessment_procedure_version_id", "control_version_id"],
            [
                "catalog_assessment_procedure_versions.id",
                "catalog_assessment_procedure_versions.control_version_id",
            ],
            name="fk_catalog_ap_er_links_ap_version_lineage",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_requirement_version_id", "control_version_id"],
            [
                "catalog_evidence_requirement_versions.id",
                "catalog_evidence_requirement_versions.control_version_id",
            ],
            name="fk_catalog_ap_er_links_er_version_lineage",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "assessment_procedure_version_id",
            "sequence",
            name="uq_catalog_ap_er_links_version_seq",
        ),
        sa.UniqueConstraint(
            "assessment_procedure_version_id",
            "evidence_requirement_version_id",
            name="uq_catalog_ap_er_links_version_er",
        ),
        sa.CheckConstraint("sequence BETWEEN 1 AND 32", name="ap_er_link_sequence_bounds"),
    )

    # PostgreSQL: Shared append-only immutability and truncate guard functions & triggers
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_assurance_content_append_only()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        BEGIN
            RAISE EXCEPTION 'catalog assurance content is append-only';
        END;
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION public.catalog_assurance_content_append_only() FROM PUBLIC")

    for table in TABLES:
        op.execute(f"""
            CREATE TRIGGER "{table}_immutable"
            BEFORE UPDATE OR DELETE ON public."{table}"
            FOR EACH ROW EXECUTE FUNCTION public.catalog_assurance_content_append_only()
        """)
        op.execute(f"""
            CREATE TRIGGER "{table}_no_truncate"
            BEFORE TRUNCATE ON public."{table}"
            FOR EACH STATEMENT EXECUTE FUNCTION public.catalog_assurance_content_append_only()
        """)

    # PostgreSQL: Concurrency sequence guards locking parents FOR UPDATE
    # 1. Evidence requirement versions (locks catalog_control_versions)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_evidence_requirement_version_sequence_guard()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        DECLARE
            v_locked_id uuid;
            v_expected_seq integer;
        BEGIN
            SELECT id INTO v_locked_id
            FROM public.catalog_control_versions
            WHERE id = NEW.control_version_id
            FOR UPDATE;

            IF v_locked_id IS NULL THEN
                RAISE EXCEPTION 'ControlVersion % not found for sequence allocation', NEW.control_version_id;
            END IF;

            SELECT COALESCE(MAX(sequence), 0) + 1 INTO v_expected_seq
            FROM public.catalog_evidence_requirement_versions
            WHERE control_version_id = NEW.control_version_id;

            IF NEW.sequence <> v_expected_seq THEN
                RAISE EXCEPTION 'Invalid sequence % for EvidenceRequirementVersion; expected %', NEW.sequence, v_expected_seq;
            END IF;

            RETURN NEW;
        END;
        $$;
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION public.catalog_evidence_requirement_version_sequence_guard() FROM PUBLIC"
    )
    op.execute("""
        CREATE TRIGGER trg_catalog_er_version_sequence
        BEFORE INSERT ON public.catalog_evidence_requirement_versions
        FOR EACH ROW EXECUTE FUNCTION public.catalog_evidence_requirement_version_sequence_guard()
    """)

    # 2. Evidence requirement artifact types (locks catalog_evidence_requirement_versions)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_er_artifact_type_sequence_guard()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        DECLARE
            v_locked_id uuid;
            v_expected_seq integer;
        BEGIN
            SELECT id INTO v_locked_id
            FROM public.catalog_evidence_requirement_versions
            WHERE id = NEW.evidence_requirement_version_id
            FOR UPDATE;

            IF v_locked_id IS NULL THEN
                RAISE EXCEPTION 'EvidenceRequirementVersion % not found for sequence allocation', NEW.evidence_requirement_version_id;
            END IF;

            SELECT COALESCE(MAX(sequence), 0) + 1 INTO v_expected_seq
            FROM public.catalog_evidence_requirement_artifact_types
            WHERE evidence_requirement_version_id = NEW.evidence_requirement_version_id;

            IF NEW.sequence <> v_expected_seq THEN
                RAISE EXCEPTION 'Invalid sequence % for artifact type; expected %', NEW.sequence, v_expected_seq;
            END IF;

            RETURN NEW;
        END;
        $$;
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION public.catalog_er_artifact_type_sequence_guard() FROM PUBLIC"
    )
    op.execute("""
        CREATE TRIGGER trg_catalog_er_art_type_sequence
        BEFORE INSERT ON public.catalog_evidence_requirement_artifact_types
        FOR EACH ROW EXECUTE FUNCTION public.catalog_er_artifact_type_sequence_guard()
    """)

    # 3. Evidence requirement metadata keys (locks catalog_evidence_requirement_versions)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_er_metadata_key_sequence_guard()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        DECLARE
            v_locked_id uuid;
            v_expected_seq integer;
        BEGIN
            SELECT id INTO v_locked_id
            FROM public.catalog_evidence_requirement_versions
            WHERE id = NEW.evidence_requirement_version_id
            FOR UPDATE;

            IF v_locked_id IS NULL THEN
                RAISE EXCEPTION 'EvidenceRequirementVersion % not found for sequence allocation', NEW.evidence_requirement_version_id;
            END IF;

            SELECT COALESCE(MAX(sequence), 0) + 1 INTO v_expected_seq
            FROM public.catalog_evidence_requirement_metadata_keys
            WHERE evidence_requirement_version_id = NEW.evidence_requirement_version_id;

            IF NEW.sequence <> v_expected_seq THEN
                RAISE EXCEPTION 'Invalid sequence % for metadata key; expected %', NEW.sequence, v_expected_seq;
            END IF;

            RETURN NEW;
        END;
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION public.catalog_er_metadata_key_sequence_guard() FROM PUBLIC")
    op.execute("""
        CREATE TRIGGER trg_catalog_er_meta_key_sequence
        BEFORE INSERT ON public.catalog_evidence_requirement_metadata_keys
        FOR EACH ROW EXECUTE FUNCTION public.catalog_er_metadata_key_sequence_guard()
    """)

    # 4. Assessment procedure versions (locks catalog_control_versions)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_assessment_procedure_version_sequence_guard()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        DECLARE
            v_locked_id uuid;
            v_expected_seq integer;
        BEGIN
            SELECT id INTO v_locked_id
            FROM public.catalog_control_versions
            WHERE id = NEW.control_version_id
            FOR UPDATE;

            IF v_locked_id IS NULL THEN
                RAISE EXCEPTION 'ControlVersion % not found for sequence allocation', NEW.control_version_id;
            END IF;

            SELECT COALESCE(MAX(sequence), 0) + 1 INTO v_expected_seq
            FROM public.catalog_assessment_procedure_versions
            WHERE control_version_id = NEW.control_version_id;

            IF NEW.sequence <> v_expected_seq THEN
                RAISE EXCEPTION 'Invalid sequence % for AssessmentProcedureVersion; expected %', NEW.sequence, v_expected_seq;
            END IF;

            RETURN NEW;
        END;
        $$;
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION public.catalog_assessment_procedure_version_sequence_guard() FROM PUBLIC"
    )
    op.execute("""
        CREATE TRIGGER trg_catalog_ap_version_sequence
        BEFORE INSERT ON public.catalog_assessment_procedure_versions
        FOR EACH ROW EXECUTE FUNCTION public.catalog_assessment_procedure_version_sequence_guard()
    """)

    # 5. Assessment procedure steps (locks catalog_assessment_procedure_versions)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_ap_step_sequence_guard()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        DECLARE
            v_locked_id uuid;
            v_expected_seq integer;
        BEGIN
            SELECT id INTO v_locked_id
            FROM public.catalog_assessment_procedure_versions
            WHERE id = NEW.assessment_procedure_version_id
            FOR UPDATE;

            IF v_locked_id IS NULL THEN
                RAISE EXCEPTION 'AssessmentProcedureVersion % not found for sequence allocation', NEW.assessment_procedure_version_id;
            END IF;

            SELECT COALESCE(MAX(sequence), 0) + 1 INTO v_expected_seq
            FROM public.catalog_assessment_procedure_steps
            WHERE assessment_procedure_version_id = NEW.assessment_procedure_version_id;

            IF NEW.sequence <> v_expected_seq THEN
                RAISE EXCEPTION 'Invalid sequence % for procedure step; expected %', NEW.sequence, v_expected_seq;
            END IF;

            RETURN NEW;
        END;
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION public.catalog_ap_step_sequence_guard() FROM PUBLIC")
    op.execute("""
        CREATE TRIGGER trg_catalog_ap_step_sequence
        BEFORE INSERT ON public.catalog_assessment_procedure_steps
        FOR EACH ROW EXECUTE FUNCTION public.catalog_ap_step_sequence_guard()
    """)

    # 6. Assessment procedure evidence requirement links (locks catalog_assessment_procedure_versions)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_ap_evidence_req_sequence_guard()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        DECLARE
            v_locked_id uuid;
            v_expected_seq integer;
        BEGIN
            SELECT id INTO v_locked_id
            FROM public.catalog_assessment_procedure_versions
            WHERE id = NEW.assessment_procedure_version_id
            FOR UPDATE;

            IF v_locked_id IS NULL THEN
                RAISE EXCEPTION 'AssessmentProcedureVersion % not found for sequence allocation', NEW.assessment_procedure_version_id;
            END IF;

            SELECT COALESCE(MAX(sequence), 0) + 1 INTO v_expected_seq
            FROM public.catalog_assessment_procedure_evidence_requirements
            WHERE assessment_procedure_version_id = NEW.assessment_procedure_version_id;

            IF NEW.sequence <> v_expected_seq THEN
                RAISE EXCEPTION 'Invalid sequence % for procedure evidence requirement link; expected %', NEW.sequence, v_expected_seq;
            END IF;

            RETURN NEW;
        END;
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION public.catalog_ap_evidence_req_sequence_guard() FROM PUBLIC")
    op.execute("""
        CREATE TRIGGER trg_catalog_ap_er_link_sequence
        BEFORE INSERT ON public.catalog_assessment_procedure_evidence_requirements
        FOR EACH ROW EXECUTE FUNCTION public.catalog_ap_evidence_req_sequence_guard()
    """)

    # Security: Enable and force RLS, revoke privileges from PUBLIC, conformly_app, conformly_catalog
    for table in TABLES:
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE public."{table}" FORCE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL PRIVILEGES ON TABLE public."{table}" FROM PUBLIC')
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_app') "
            f'THEN REVOKE ALL PRIVILEGES ON TABLE public."{table}" FROM conformly_app; '
            "END IF; END $$"
        )
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_catalog') "
            f'THEN REVOKE ALL PRIVILEGES ON TABLE public."{table}" FROM conformly_catalog; '
            "END IF; END $$"
        )


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
            RAISE EXCEPTION 'V2 assurance content foundation is populated; forward recovery required';
        END IF;
        END $$;
    """)

    # Drop sequence triggers and functions
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_ap_er_link_sequence ON public.catalog_assessment_procedure_evidence_requirements"
    )
    op.execute("DROP FUNCTION IF EXISTS public.catalog_ap_evidence_req_sequence_guard()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_ap_step_sequence ON public.catalog_assessment_procedure_steps"
    )
    op.execute("DROP FUNCTION IF EXISTS public.catalog_ap_step_sequence_guard()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_ap_version_sequence ON public.catalog_assessment_procedure_versions"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.catalog_assessment_procedure_version_sequence_guard()"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_er_meta_key_sequence ON public.catalog_evidence_requirement_metadata_keys"
    )
    op.execute("DROP FUNCTION IF EXISTS public.catalog_er_metadata_key_sequence_guard()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_er_art_type_sequence ON public.catalog_evidence_requirement_artifact_types"
    )
    op.execute("DROP FUNCTION IF EXISTS public.catalog_er_artifact_type_sequence_guard()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_er_version_sequence ON public.catalog_evidence_requirement_versions"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.catalog_evidence_requirement_version_sequence_guard()"
    )

    # Drop immutability and no-truncate triggers and function
    for table in reversed(TABLES):
        op.execute(f'DROP TRIGGER IF EXISTS "{table}_no_truncate" ON public."{table}"')
        op.execute(f'DROP TRIGGER IF EXISTS "{table}_immutable" ON public."{table}"')
    op.execute("DROP FUNCTION IF EXISTS public.catalog_assurance_content_append_only()")

    # Drop tables in reverse dependency order
    for table in reversed(TABLES):
        op.drop_table(table)
