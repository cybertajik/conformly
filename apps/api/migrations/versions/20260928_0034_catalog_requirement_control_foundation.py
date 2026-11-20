"""Add dormant requirement and Common Control foundation tables."""

import sqlalchemy as sa
from alembic import op

revision = "20260928_0034"
down_revision = "20260928_0033"
branch_labels = None
depends_on = None

TABLES = (
    "catalog_requirements",
    "catalog_requirement_versions",
    "catalog_requirement_source_references",
    "catalog_common_controls",
    "catalog_control_versions",
)


def upgrade() -> None:
    # 1. catalog_requirements
    op.create_table(
        "catalog_requirements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), server_default="Draft", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["source_id"], ["catalog_sources.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "source_id", "requirement_key", name="uq_catalog_requirements_source_key"
        ),
        sa.UniqueConstraint("id", "source_id", name="uq_catalog_requirements_id_source"),
        sa.CheckConstraint(
            "length(requirement_key) BETWEEN 1 AND 128", name="requirement_key_length"
        ),
        sa.CheckConstraint("status = 'Draft'", name="req_draft_only"),
    )

    # 2. catalog_requirement_versions
    op.create_table(
        "catalog_requirement_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column("version_label", sa.String(64), nullable=False),
        sa.Column("predecessor_id", sa.Uuid(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("normalized_outcome", sa.String(4096), nullable=False),
        sa.Column("requirement_type", sa.String(32), nullable=False),
        sa.Column("obligated_actor", sa.String(64), nullable=False),
        sa.Column("text_origin", sa.String(32), nullable=False),
        sa.Column("customer_display_text", sa.String(4096), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("status", sa.String(16), server_default="Draft", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id", "source_id"],
            ["catalog_requirements.id", "catalog_requirements.source_id"],
            name="fk_catalog_req_versions_requirement_lineage",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id", "source_id"],
            ["catalog_source_versions.id", "catalog_source_versions.source_id"],
            name="fk_catalog_req_versions_source_version_lineage",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_id", "requirement_id"],
            ["catalog_requirement_versions.id", "catalog_requirement_versions.requirement_id"],
            name="fk_catalog_req_versions_predecessor_lineage",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "requirement_id", "version_label", name="uq_catalog_req_versions_version"
        ),
        sa.UniqueConstraint(
            "id", "source_version_id", name="uq_catalog_req_versions_id_source_version"
        ),
        sa.UniqueConstraint("id", "requirement_id", name="uq_catalog_req_versions_id_requirement"),
        sa.CheckConstraint(
            "predecessor_id IS NULL OR predecessor_id <> id", name="not_self_predecessor_req"
        ),
        sa.CheckConstraint(
            "length(version_label) BETWEEN 1 AND 64", name="req_version_label_length"
        ),
        sa.CheckConstraint("revision >= 1", name="positive_req_revision"),
        sa.CheckConstraint(
            "length(normalized_outcome) BETWEEN 1 AND 4096", name="normalized_outcome_length"
        ),
        sa.CheckConstraint(
            "requirement_type IN ('mandatory', 'conditional', 'recommendation', 'prohibition', 'permission')",
            name="known_requirement_type",
        ),
        sa.CheckConstraint(
            "length(obligated_actor) BETWEEN 1 AND 64", name="obligated_actor_length"
        ),
        sa.CheckConstraint(
            "text_origin IN ('verbatim_source', 'authorized_excerpt', 'conformly_paraphrase', 'official_translation', 'reference_only')",
            name="known_text_origin",
        ),
        sa.CheckConstraint(
            "customer_display_text IS NULL OR length(customer_display_text) BETWEEN 1 AND 4096",
            name="customer_display_text_length",
        ),
        sa.CheckConstraint(
            "effective_from IS NULL OR effective_until IS NULL OR effective_until >= effective_from",
            name="req_effective_date_order",
        ),
        sa.CheckConstraint("status = 'Draft'", name="req_version_draft_only"),
    )

    # 3. catalog_requirement_source_references
    op.create_table(
        "catalog_requirement_source_references",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("requirement_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column("locator_kind", sa.String(32), nullable=False),
        sa.Column("locator_value", sa.String(512), nullable=False),
        sa.Column("sequence", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["requirement_version_id", "source_version_id"],
            ["catalog_requirement_versions.id", "catalog_requirement_versions.source_version_id"],
            name="fk_catalog_req_source_ref_lineage",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "requirement_version_id",
            "locator_kind",
            "locator_value",
            name="uq_catalog_req_source_ref_value",
        ),
        sa.UniqueConstraint(
            "requirement_version_id",
            "sequence",
            name="uq_catalog_req_source_ref_sequence",
        ),
        sa.CheckConstraint(
            "locator_kind IN ('article', 'section', 'paragraph', 'clause', 'criterion', 'table', 'annex', 'page')",
            name="known_locator_kind",
        ),
        sa.CheckConstraint("length(locator_value) BETWEEN 1 AND 512", name="locator_value_length"),
        sa.CheckConstraint("sequence >= 1", name="positive_ref_sequence"),
    )

    # 4. catalog_common_controls
    op.create_table(
        "catalog_common_controls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("control_key", sa.String(32), nullable=False),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), server_default="Draft", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("control_key", name="uq_catalog_common_controls_key"),
        sa.UniqueConstraint("id", "control_key", name="uq_catalog_common_controls_id_key"),
        sa.CheckConstraint("control_key ~ '^CC-[A-Z]{2,4}-[0-9]{3}$'", name="cc_key_format"),
        sa.CheckConstraint("length(domain) BETWEEN 1 AND 64", name="domain_length"),
        sa.CheckConstraint("status = 'Draft'", name="ctrl_draft_only"),
    )

    # 5. catalog_control_versions
    op.create_table(
        "catalog_control_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("version_label", sa.String(64), nullable=False),
        sa.Column("predecessor_id", sa.Uuid(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("objective", sa.String(4096), nullable=False),
        sa.Column("guidance", sa.String(4096), nullable=True),
        sa.Column("control_type", sa.String(32), nullable=False),
        sa.Column("frequency", sa.String(64), nullable=False),
        sa.Column("automation_level", sa.String(32), nullable=False),
        sa.Column("suggested_owner_role", sa.String(64), nullable=False),
        sa.Column("assurance_level", sa.String(32), nullable=False),
        sa.Column("tags_state", sa.String(32), server_default="Unknown", nullable=False),
        sa.Column("tags", sa.String(1024), nullable=True),
        sa.Column("status", sa.String(16), server_default="Draft", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["control_id"],
            ["catalog_common_controls.id"],
            name="fk_catalog_control_versions_control",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_id", "control_id"],
            ["catalog_control_versions.id", "catalog_control_versions.control_id"],
            name="fk_catalog_control_versions_predecessor_lineage",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "control_id", "version_label", name="uq_catalog_control_versions_version"
        ),
        sa.UniqueConstraint("id", "control_id", name="uq_catalog_control_versions_id_control"),
        sa.CheckConstraint(
            "predecessor_id IS NULL OR predecessor_id <> id", name="not_self_predecessor_ctrl"
        ),
        sa.CheckConstraint(
            "length(version_label) BETWEEN 1 AND 64", name="ctrl_version_label_length"
        ),
        sa.CheckConstraint("revision >= 1", name="positive_ctrl_revision"),
        sa.CheckConstraint("length(title) BETWEEN 1 AND 512", name="control_title_length"),
        sa.CheckConstraint("length(objective) BETWEEN 1 AND 4096", name="control_objective_length"),
        sa.CheckConstraint(
            "guidance IS NULL OR length(guidance) BETWEEN 1 AND 4096",
            name="control_guidance_length",
        ),
        sa.CheckConstraint(
            "control_type IN ('governance', 'preventive', 'detective', 'corrective', 'compensating')",
            name="known_control_type",
        ),
        sa.CheckConstraint("length(frequency) BETWEEN 1 AND 64", name="control_frequency_length"),
        sa.CheckConstraint(
            "automation_level IN ('manual', 'partially_automated', 'automated')",
            name="known_automation_level",
        ),
        sa.CheckConstraint(
            "length(suggested_owner_role) BETWEEN 1 AND 64", name="owner_role_length"
        ),
        sa.CheckConstraint(
            "assurance_level IN ('foundational', 'conditional', 'enhanced')",
            name="known_assurance_level",
        ),
        sa.CheckConstraint("tags_state IN ('Unknown', 'None', 'Provided')", name="tags_state_enum"),
        sa.CheckConstraint(
            "(tags_state IN ('Unknown', 'None') AND tags IS NULL) OR (tags_state = 'Provided' AND tags IS NOT NULL)",
            name="tags_shape",
        ),
        sa.CheckConstraint("status = 'Draft'", name="ctrl_version_draft_only"),
    )

    # PostgreSQL constraint trigger enforcing that RequirementVersion has at least one source reference
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_requirement_version_check_source_references()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM public.catalog_requirement_source_references
                WHERE requirement_version_id = NEW.id
            ) THEN
                RAISE EXCEPTION 'RequirementVersion % must have at least one source reference', NEW.id;
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION public.catalog_requirement_version_check_source_references() FROM PUBLIC"
    )
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_catalog_requirement_version_has_reference
        AFTER INSERT OR UPDATE ON public.catalog_requirement_versions
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION public.catalog_requirement_version_check_source_references()
    """)

    # PostgreSQL append-only immutability and truncate guards for catalog_requirement_source_references
    op.execute("""
        CREATE FUNCTION public.catalog_requirement_source_references_append_only()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$ BEGIN RAISE EXCEPTION 'catalog requirement source references are append-only'; END; $$
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION public.catalog_requirement_source_references_append_only() FROM PUBLIC"
    )
    op.execute("""
        CREATE TRIGGER "catalog_requirement_source_references_immutable"
        BEFORE UPDATE OR DELETE ON public."catalog_requirement_source_references"
        FOR EACH ROW EXECUTE FUNCTION public.catalog_requirement_source_references_append_only()
    """)
    op.execute("""
        CREATE TRIGGER "catalog_requirement_source_references_no_truncate"
        BEFORE TRUNCATE ON public."catalog_requirement_source_references"
        FOR EACH STATEMENT EXECUTE FUNCTION public.catalog_requirement_source_references_append_only()
    """)

    # PostgreSQL triggers enforcing acyclic predecessor chains for requirement versions and control versions
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_check_requirement_version_acyclic()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        DECLARE
            curr_id uuid := NEW.predecessor_id;
            visited uuid[] := ARRAY[NEW.id];
        BEGIN
            WHILE curr_id IS NOT NULL LOOP
                IF curr_id = ANY(visited) THEN
                    RAISE EXCEPTION 'Cycle detected in requirement version predecessor chain: %', curr_id;
                END IF;
                visited := array_append(visited, curr_id);
                SELECT predecessor_id INTO curr_id
                FROM public.catalog_requirement_versions
                WHERE id = curr_id;
            END LOOP;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION public.catalog_check_requirement_version_acyclic() FROM PUBLIC"
    )
    op.execute("""
        CREATE TRIGGER trg_catalog_requirement_version_acyclic
        BEFORE INSERT OR UPDATE OF predecessor_id ON public.catalog_requirement_versions
        FOR EACH ROW
        WHEN (NEW.predecessor_id IS NOT NULL)
        EXECUTE FUNCTION public.catalog_check_requirement_version_acyclic()
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_check_control_version_acyclic()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        DECLARE
            curr_id uuid := NEW.predecessor_id;
            visited uuid[] := ARRAY[NEW.id];
        BEGIN
            WHILE curr_id IS NOT NULL LOOP
                IF curr_id = ANY(visited) THEN
                    RAISE EXCEPTION 'Cycle detected in control version predecessor chain: %', curr_id;
                END IF;
                visited := array_append(visited, curr_id);
                SELECT predecessor_id INTO curr_id
                FROM public.catalog_control_versions
                WHERE id = curr_id;
            END LOOP;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION public.catalog_check_control_version_acyclic() FROM PUBLIC")
    op.execute("""
        CREATE TRIGGER trg_catalog_control_version_acyclic
        BEFORE INSERT OR UPDATE OF predecessor_id ON public.catalog_control_versions
        FOR EACH ROW
        WHEN (NEW.predecessor_id IS NOT NULL)
        EXECUTE FUNCTION public.catalog_check_control_version_acyclic()
    """)

    # Security: RLS, deny-all, revoke from PUBLIC and conformly_app
    for table in TABLES:
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE public."{table}" FORCE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL PRIVILEGES ON TABLE public."{table}" FROM PUBLIC')
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_app') "
            f'THEN REVOKE ALL PRIVILEGES ON TABLE public."{table}" FROM conformly_app; '
            "END IF; END $$"
        )


def downgrade() -> None:
    op.execute("SET LOCAL row_security = off")
    op.execute(
        "LOCK TABLE public.catalog_requirements, "
        "public.catalog_requirement_versions, "
        "public.catalog_requirement_source_references, "
        "public.catalog_common_controls, "
        "public.catalog_control_versions IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN IF EXISTS (SELECT 1 FROM public.catalog_requirements)
        OR EXISTS (SELECT 1 FROM public.catalog_requirement_versions)
        OR EXISTS (SELECT 1 FROM public.catalog_requirement_source_references)
        OR EXISTS (SELECT 1 FROM public.catalog_common_controls)
        OR EXISTS (SELECT 1 FROM public.catalog_control_versions) THEN
        RAISE EXCEPTION 'V2 requirement and control foundation is populated; forward recovery required';
        END IF; END $$
    """)
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_control_version_acyclic ON public.catalog_control_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS public.catalog_check_control_version_acyclic()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_requirement_version_acyclic ON public.catalog_requirement_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS public.catalog_check_requirement_version_acyclic()")
    op.execute(
        'DROP TRIGGER IF EXISTS "catalog_requirement_source_references_no_truncate" ON public."catalog_requirement_source_references"'
    )
    op.execute(
        'DROP TRIGGER IF EXISTS "catalog_requirement_source_references_immutable" ON public."catalog_requirement_source_references"'
    )
    op.execute("DROP FUNCTION IF EXISTS public.catalog_requirement_source_references_append_only()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_requirement_version_has_reference ON public.catalog_requirement_versions"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.catalog_requirement_version_check_source_references()"
    )
    for table in reversed(TABLES):
        op.drop_table(table)
