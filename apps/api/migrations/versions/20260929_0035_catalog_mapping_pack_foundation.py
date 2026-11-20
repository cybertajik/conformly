"""Add dormant mapping and pack foundation tables."""

import sqlalchemy as sa
from alembic import op

revision = "20260929_0035"
down_revision = "20260928_0034"
branch_labels = None
depends_on = None

TABLES = (
    "catalog_packs",
    "catalog_pack_versions",
    "catalog_pack_memberships",
    "catalog_requirement_control_mappings",
    "catalog_mapping_versions",
)


def upgrade() -> None:
    # 1. catalog_packs
    op.create_table(
        "catalog_packs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("pack_key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("pack_type", sa.String(32), nullable=False),
        sa.Column("jurisdiction", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), server_default="Draft", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("pack_key", name="uq_catalog_packs_key"),
        sa.UniqueConstraint("id", "pack_key", name="uq_catalog_packs_id_key"),
        sa.CheckConstraint("pack_key ~ '^[A-Z0-9_-]{3,64}$'", name="pack_key_format"),
        sa.CheckConstraint("length(pack_key) BETWEEN 1 AND 64", name="pack_key_length"),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 256", name="pack_name_length"),
        sa.CheckConstraint(
            "pack_type IN ('regulatory', 'certification', 'contractual', 'baseline')",
            name="known_pack_type",
        ),
        sa.CheckConstraint(
            "jurisdiction IS NULL OR length(jurisdiction) BETWEEN 1 AND 64",
            name="jurisdiction_length",
        ),
        sa.CheckConstraint("status = 'Draft'", name="pack_draft_only"),
    )

    # 2. catalog_pack_versions
    op.create_table(
        "catalog_pack_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("pack_id", sa.Uuid(), nullable=False),
        sa.Column("version_label", sa.String(64), nullable=False),
        sa.Column("predecessor_id", sa.Uuid(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.String(4096), nullable=True),
        sa.Column("audience", sa.String(256), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("release_notes", sa.String(4096), nullable=True),
        sa.Column("status", sa.String(16), server_default="Draft", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["pack_id"],
            ["catalog_packs.id"],
            name="fk_catalog_pack_versions_pack",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_id", "pack_id"],
            ["catalog_pack_versions.id", "catalog_pack_versions.pack_id"],
            name="fk_catalog_pack_versions_predecessor_lineage",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("pack_id", "version_label", name="uq_catalog_pack_versions_label"),
        sa.UniqueConstraint("id", "pack_id", name="uq_catalog_pack_versions_id_pack"),
        sa.CheckConstraint(
            "predecessor_id IS NULL OR predecessor_id <> id", name="not_self_predecessor_pack"
        ),
        sa.CheckConstraint(
            "length(version_label) BETWEEN 1 AND 64", name="pack_version_label_length"
        ),
        sa.CheckConstraint("revision >= 1", name="positive_pack_revision"),
        sa.CheckConstraint("length(title) BETWEEN 1 AND 512", name="pack_title_length"),
        sa.CheckConstraint(
            "description IS NULL OR length(description) BETWEEN 1 AND 4096",
            name="pack_description_length",
        ),
        sa.CheckConstraint(
            "audience IS NULL OR length(audience) BETWEEN 1 AND 256",
            name="pack_audience_length",
        ),
        sa.CheckConstraint(
            "effective_from IS NULL OR effective_until IS NULL OR effective_until >= effective_from",
            name="pack_effective_dates_order",
        ),
        sa.CheckConstraint(
            "release_notes IS NULL OR length(release_notes) BETWEEN 1 AND 4096",
            name="pack_release_notes_length",
        ),
        sa.CheckConstraint("status = 'Draft'", name="pack_version_draft_only"),
    )

    # 3. catalog_pack_memberships
    op.create_table(
        "catalog_pack_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("pack_version_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_version_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "inclusion_conditions_state", sa.String(32), server_default="Unknown", nullable=False
        ),
        sa.Column("inclusion_conditions", sa.String(2048), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["pack_version_id"],
            ["catalog_pack_versions.id"],
            name="fk_catalog_pack_memberships_pack_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_version_id"],
            ["catalog_requirement_versions.id"],
            name="fk_catalog_pack_memberships_req_version",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "pack_version_id",
            "requirement_version_id",
            name="uq_catalog_pack_memberships_pair",
        ),
        sa.UniqueConstraint(
            "pack_version_id",
            "sequence",
            name="uq_catalog_pack_memberships_seq",
        ),
        sa.CheckConstraint("sequence >= 1", name="positive_pack_membership_sequence"),
        sa.CheckConstraint(
            "inclusion_conditions_state IN ('Unknown', 'None', 'Provided')",
            name="inclusion_conditions_state_enum",
        ),
        sa.CheckConstraint(
            "(inclusion_conditions_state IN ('Unknown', 'None') AND inclusion_conditions IS NULL) OR (inclusion_conditions_state = 'Provided' AND inclusion_conditions IS NOT NULL)",
            name="inclusion_conditions_shape",
        ),
        sa.CheckConstraint(
            "inclusion_conditions IS NULL OR length(inclusion_conditions) BETWEEN 1 AND 2048",
            name="inclusion_conditions_length",
        ),
    )

    # 4. catalog_requirement_control_mappings
    op.create_table(
        "catalog_requirement_control_mappings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("mapping_key", sa.String(128), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), server_default="Draft", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["catalog_requirements.id"],
            name="fk_catalog_req_ctrl_mappings_requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["control_id"],
            ["catalog_common_controls.id"],
            name="fk_catalog_req_ctrl_mappings_control",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("mapping_key", name="uq_catalog_req_ctrl_mappings_key"),
        sa.UniqueConstraint(
            "requirement_id",
            "control_id",
            name="uq_catalog_req_ctrl_mappings_pair",
        ),
        sa.UniqueConstraint(
            "id",
            "requirement_id",
            "control_id",
            name="uq_catalog_req_ctrl_mappings_composite",
        ),
        sa.CheckConstraint("length(mapping_key) BETWEEN 1 AND 128", name="mapping_key_length"),
        sa.CheckConstraint("status = 'Draft'", name="mapping_draft_only"),
    )

    # 5. catalog_mapping_versions
    op.create_table(
        "catalog_mapping_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("mapping_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_version_id", sa.Uuid(), nullable=False),
        sa.Column("control_version_id", sa.Uuid(), nullable=False),
        sa.Column("version_label", sa.String(64), nullable=False),
        sa.Column("predecessor_id", sa.Uuid(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("mapping_type", sa.String(32), nullable=False),
        sa.Column("rationale", sa.String(4096), nullable=False),
        sa.Column("covered_dimensions", sa.String(2048), nullable=True),
        sa.Column("excluded_dimensions", sa.String(2048), nullable=True),
        sa.Column("conditions", sa.String(2048), nullable=True),
        sa.Column("source_basis", sa.String(64), nullable=False),
        sa.Column("confidence", sa.String(32), nullable=False),
        sa.Column("review_state", sa.String(32), server_default="Draft", nullable=False),
        sa.Column("status", sa.String(16), server_default="Draft", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["mapping_id", "requirement_id", "control_id"],
            [
                "catalog_requirement_control_mappings.id",
                "catalog_requirement_control_mappings.requirement_id",
                "catalog_requirement_control_mappings.control_id",
            ],
            name="fk_catalog_mapping_versions_lineage",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id"],
            [
                "catalog_requirement_versions.id",
                "catalog_requirement_versions.requirement_id",
            ],
            name="fk_catalog_mapping_versions_req_lineage",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["control_version_id", "control_id"],
            [
                "catalog_control_versions.id",
                "catalog_control_versions.control_id",
            ],
            name="fk_catalog_mapping_versions_ctrl_lineage",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_id", "mapping_id"],
            [
                "catalog_mapping_versions.id",
                "catalog_mapping_versions.mapping_id",
            ],
            name="fk_catalog_mapping_versions_predecessor_lineage",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "mapping_id", "version_label", name="uq_catalog_mapping_versions_label"
        ),
        sa.UniqueConstraint(
            "requirement_version_id",
            "control_version_id",
            "version_label",
            name="uq_catalog_mapping_versions_endpoints",
        ),
        sa.UniqueConstraint("id", "mapping_id", name="uq_catalog_mapping_versions_id_mapping"),
        sa.CheckConstraint(
            "predecessor_id IS NULL OR predecessor_id <> id",
            name="not_self_predecessor_mapping",
        ),
        sa.CheckConstraint(
            "length(version_label) BETWEEN 1 AND 64",
            name="mapping_version_label_length",
        ),
        sa.CheckConstraint("revision >= 1", name="positive_mapping_revision"),
        sa.CheckConstraint(
            "mapping_type IN ('Full', 'Partial', 'Supporting')",
            name="known_mapping_type",
        ),
        sa.CheckConstraint("length(rationale) BETWEEN 1 AND 4096", name="mapping_rationale_length"),
        sa.CheckConstraint(
            "covered_dimensions IS NULL OR length(covered_dimensions) BETWEEN 1 AND 2048",
            name="covered_dimensions_length",
        ),
        sa.CheckConstraint(
            "excluded_dimensions IS NULL OR length(excluded_dimensions) BETWEEN 1 AND 2048",
            name="excluded_dimensions_length",
        ),
        sa.CheckConstraint(
            "(mapping_type = 'Partial' AND excluded_dimensions IS NOT NULL) OR (mapping_type != 'Partial')",
            name="partial_mapping_excluded_dims_required",
        ),
        sa.CheckConstraint(
            "conditions IS NULL OR length(conditions) BETWEEN 1 AND 2048",
            name="mapping_conditions_length",
        ),
        sa.CheckConstraint(
            "source_basis IN ('direct_text', 'authoritative_guidance', 'expert_analysis', 'regulatory_precedent')",
            name="known_source_basis",
        ),
        sa.CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="known_mapping_confidence",
        ),
        sa.CheckConstraint(
            "review_state IN ('Draft', 'InReview', 'Approved', 'Rejected')",
            name="known_review_state",
        ),
        sa.CheckConstraint("status = 'Draft'", name="mapping_version_draft_only"),
    )

    # PostgreSQL append-only immutability and truncate guards for catalog_pack_memberships
    op.execute("""
        CREATE FUNCTION public.catalog_pack_memberships_append_only()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$ BEGIN RAISE EXCEPTION 'catalog pack memberships are append-only'; END; $$
    """)
    op.execute("REVOKE ALL ON FUNCTION public.catalog_pack_memberships_append_only() FROM PUBLIC")
    op.execute("""
        CREATE TRIGGER "catalog_pack_memberships_immutable"
        BEFORE UPDATE OR DELETE ON public."catalog_pack_memberships"
        FOR EACH ROW EXECUTE FUNCTION public.catalog_pack_memberships_append_only()
    """)
    op.execute("""
        CREATE TRIGGER "catalog_pack_memberships_no_truncate"
        BEFORE TRUNCATE ON public."catalog_pack_memberships"
        FOR EACH STATEMENT EXECUTE FUNCTION public.catalog_pack_memberships_append_only()
    """)

    # PostgreSQL trigger enforcing gap-free sequence ordering and serializing concurrent allocation
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_pack_membership_check_sequence()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        DECLARE
            curr_max int;
        BEGIN
            -- Serialize membership insertion under the same pack version to prevent race conditions on sequence allocation
            PERFORM 1 FROM public.catalog_pack_versions WHERE id = NEW.pack_version_id FOR UPDATE;

            SELECT COALESCE(MAX(sequence), 0) INTO curr_max
            FROM public.catalog_pack_memberships
            WHERE pack_version_id = NEW.pack_version_id;

            IF NEW.sequence <> curr_max + 1 THEN
                RAISE EXCEPTION 'Pack membership sequence must be gap-free: expected %, got %', curr_max + 1, NEW.sequence;
            END IF;

            RETURN NEW;
        END;
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION public.catalog_pack_membership_check_sequence() FROM PUBLIC")
    op.execute("""
        CREATE TRIGGER trg_catalog_pack_membership_sequence
        BEFORE INSERT ON public.catalog_pack_memberships
        FOR EACH ROW EXECUTE FUNCTION public.catalog_pack_membership_check_sequence()
    """)

    # PostgreSQL trigger enforcing acyclic predecessor chain for pack versions
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_check_pack_version_acyclic()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        DECLARE
            curr_id uuid := NEW.predecessor_id;
            visited uuid[] := ARRAY[NEW.id];
        BEGIN
            -- Serialize predecessor updates within the same pack lineage to prevent concurrent cycle creation
            PERFORM 1 FROM public.catalog_packs WHERE id = NEW.pack_id FOR UPDATE;

            WHILE curr_id IS NOT NULL LOOP
                IF curr_id = ANY(visited) THEN
                    RAISE EXCEPTION 'Cycle detected in pack version predecessor chain: %', curr_id;
                END IF;
                visited := array_append(visited, curr_id);
                SELECT predecessor_id INTO curr_id
                FROM public.catalog_pack_versions
                WHERE id = curr_id;
            END LOOP;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION public.catalog_check_pack_version_acyclic() FROM PUBLIC")
    op.execute("""
        CREATE TRIGGER trg_catalog_pack_version_acyclic
        BEFORE INSERT OR UPDATE OF predecessor_id ON public.catalog_pack_versions
        FOR EACH ROW
        WHEN (NEW.predecessor_id IS NOT NULL)
        EXECUTE FUNCTION public.catalog_check_pack_version_acyclic()
    """)

    # PostgreSQL trigger enforcing acyclic predecessor chain for mapping versions
    op.execute("""
        CREATE OR REPLACE FUNCTION public.catalog_check_mapping_version_acyclic()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        DECLARE
            curr_id uuid := NEW.predecessor_id;
            visited uuid[] := ARRAY[NEW.id];
        BEGIN
            -- Serialize predecessor updates within the same mapping lineage to prevent concurrent cycle creation
            PERFORM 1 FROM public.catalog_requirement_control_mappings WHERE id = NEW.mapping_id FOR UPDATE;

            WHILE curr_id IS NOT NULL LOOP
                IF curr_id = ANY(visited) THEN
                    RAISE EXCEPTION 'Cycle detected in mapping version predecessor chain: %', curr_id;
                END IF;
                visited := array_append(visited, curr_id);
                SELECT predecessor_id INTO curr_id
                FROM public.catalog_mapping_versions
                WHERE id = curr_id;
            END LOOP;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION public.catalog_check_mapping_version_acyclic() FROM PUBLIC")
    op.execute("""
        CREATE TRIGGER trg_catalog_mapping_version_acyclic
        BEFORE INSERT OR UPDATE OF predecessor_id ON public.catalog_mapping_versions
        FOR EACH ROW
        WHEN (NEW.predecessor_id IS NOT NULL)
        EXECUTE FUNCTION public.catalog_check_mapping_version_acyclic()
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
        "LOCK TABLE public.catalog_packs, "
        "public.catalog_pack_versions, "
        "public.catalog_pack_memberships, "
        "public.catalog_requirement_control_mappings, "
        "public.catalog_mapping_versions IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN IF EXISTS (SELECT 1 FROM public.catalog_packs)
        OR EXISTS (SELECT 1 FROM public.catalog_pack_versions)
        OR EXISTS (SELECT 1 FROM public.catalog_pack_memberships)
        OR EXISTS (SELECT 1 FROM public.catalog_requirement_control_mappings)
        OR EXISTS (SELECT 1 FROM public.catalog_mapping_versions) THEN
        RAISE EXCEPTION 'V2 mapping and pack foundation is populated; forward recovery required';
        END IF; END $$
    """)
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_mapping_version_acyclic ON public.catalog_mapping_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS public.catalog_check_mapping_version_acyclic()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_pack_version_acyclic ON public.catalog_pack_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS public.catalog_check_pack_version_acyclic()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_catalog_pack_membership_sequence ON public.catalog_pack_memberships"
    )
    op.execute("DROP FUNCTION IF EXISTS public.catalog_pack_membership_check_sequence()")
    op.execute(
        'DROP TRIGGER IF EXISTS "catalog_pack_memberships_no_truncate" ON public."catalog_pack_memberships"'
    )
    op.execute(
        'DROP TRIGGER IF EXISTS "catalog_pack_memberships_immutable" ON public."catalog_pack_memberships"'
    )
    op.execute("DROP FUNCTION IF EXISTS public.catalog_pack_memberships_append_only()")
    for table in reversed(TABLES):
        op.drop_table(table)
