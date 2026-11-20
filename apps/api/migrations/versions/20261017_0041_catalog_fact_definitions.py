"""catalog fact definitions foundation (WP-07B)

Revision ID: 20261017_0041
Revises: 20261016_0040
Create Date: 2026-10-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from conformly.catalog_v2.models import FactEnumValueCodeFormat, FactKeyFormat

# revision identifiers, used by Alembic.
revision = "20261017_0041"
down_revision = "20261016_0040"
branch_labels = None
depends_on = None

TABLES = (
    "catalog_fact_definitions",
    "catalog_fact_definition_versions",
    "catalog_fact_definition_scopes",
    "catalog_fact_definition_enum_values",
)


def upgrade() -> None:
    # 1. catalog_fact_definitions
    op.create_table(
        "catalog_fact_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("fact_key", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(16), server_default="Draft", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(FactKeyFormat(sa.column("fact_key")), name="fact_def_key_format"),
        sa.CheckConstraint("length(fact_key) BETWEEN 3 AND 64", name="fact_def_key_length"),
        sa.CheckConstraint("status = 'Draft'", name="fact_def_status_draft"),
    )

    # 2. catalog_fact_definition_versions
    op.create_table(
        "catalog_fact_definition_versions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("fact_definition_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("version_label", sa.String(64), nullable=False),
        sa.Column("predecessor_id", sa.Uuid(), nullable=True),
        sa.Column("predecessor_revision", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(512), nullable=False),
        sa.Column("description", sa.String(4096), nullable=False),
        sa.Column("collection_guidance", sa.String(4096), nullable=True),
        sa.Column("value_type", sa.String(32), nullable=False),
        sa.Column("sensitivity", sa.String(16), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("status", sa.String(16), server_default="Draft", nullable=False),
        sa.Column("content_digest", sa.LargeBinary(), nullable=False),
        sa.Column(
            "digest_schema",
            sa.String(64),
            server_default="catalog-fact-definition-draft-v1",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["fact_definition_id"],
            ["catalog_fact_definitions.id"],
            name="fk_catalog_fact_def_versions_definition",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "fact_definition_id",
            "revision",
            name="uq_catalog_fact_def_versions_def_rev",
        ),
        sa.UniqueConstraint(
            "fact_definition_id",
            "version_label",
            name="uq_catalog_fact_def_versions_def_label",
        ),
        sa.UniqueConstraint(
            "id",
            "fact_definition_id",
            "revision",
            name="uq_catalog_fact_def_versions_lineage",
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_id", "fact_definition_id", "predecessor_revision"],
            [
                "catalog_fact_definition_versions.id",
                "catalog_fact_definition_versions.fact_definition_id",
                "catalog_fact_definition_versions.revision",
            ],
            name="fk_catalog_fact_def_versions_predecessor",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("revision BETWEEN 1 AND 32767", name="fact_def_version_revision_bounds"),
        sa.CheckConstraint(
            "((revision = 1 AND predecessor_id IS NULL AND predecessor_revision IS NULL) OR "
            "(revision > 1 AND predecessor_id IS NOT NULL AND predecessor_revision IS NOT NULL "
            "AND predecessor_revision = revision - 1 AND predecessor_id != id))",
            name="fact_def_version_predecessor_shape",
        ),
        sa.CheckConstraint(
            "version_label = trim(version_label) AND length(version_label) BETWEEN 1 AND 64",
            name="fact_def_version_label_trim",
        ),
        sa.CheckConstraint(
            "label = trim(label) AND length(label) BETWEEN 1 AND 512",
            name="fact_def_version_name_trim",
        ),
        sa.CheckConstraint(
            "description = trim(description) AND length(description) BETWEEN 1 AND 4096",
            name="fact_def_version_desc_trim",
        ),
        sa.CheckConstraint(
            "collection_guidance IS NULL OR (collection_guidance = trim(collection_guidance) AND length(collection_guidance) BETWEEN 1 AND 4096)",
            name="fact_def_version_guidance_trim",
        ),
        sa.CheckConstraint(
            "value_type IN ('boolean', 'integer', 'decimal', 'date', 'enum', 'string', 'entity_reference')",
            name="fact_def_version_value_type_known",
        ),
        sa.CheckConstraint(
            "sensitivity IN ('Public', 'Internal', 'Confidential', 'Restricted')",
            name="fact_def_version_sensitivity_known",
        ),
        sa.CheckConstraint(
            "effective_from IS NULL OR effective_until IS NULL OR effective_until >= effective_from",
            name="fact_def_version_effective_dates",
        ),
        sa.CheckConstraint("status = 'Draft'", name="fact_def_version_status_draft"),
        sa.CheckConstraint(
            "digest_schema = 'catalog-fact-definition-draft-v1'",
            name="fact_def_version_digest_schema_valid",
        ),
        sa.CheckConstraint("length(content_digest) = 32", name="fact_def_version_digest_32_bytes"),
    )

    # 3. catalog_fact_definition_scopes
    op.create_table(
        "catalog_fact_definition_scopes",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("fact_definition_version_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("scope_type", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["fact_definition_version_id"],
            ["catalog_fact_definition_versions.id"],
            name="fk_catalog_fact_def_scopes_version",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "fact_definition_version_id",
            "sequence",
            name="uq_catalog_fact_def_scopes_version_seq",
        ),
        sa.UniqueConstraint(
            "fact_definition_version_id",
            "scope_type",
            name="uq_catalog_fact_def_scopes_version_scope",
        ),
        sa.CheckConstraint("sequence BETWEEN 1 AND 6", name="fact_def_scope_sequence_bounds"),
        sa.CheckConstraint(
            "scope_type IN ('tenant', 'legal_entity', 'service', 'processing_activity', 'system', 'location')",
            name="fact_def_scope_type_known",
        ),
    )

    # 4. catalog_fact_definition_enum_values
    op.create_table(
        "catalog_fact_definition_enum_values",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("fact_definition_version_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(256), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["fact_definition_version_id"],
            ["catalog_fact_definition_versions.id"],
            name="fk_catalog_fact_def_enum_values_version",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "fact_definition_version_id",
            "sequence",
            name="uq_catalog_fact_def_enum_values_version_seq",
        ),
        sa.UniqueConstraint(
            "fact_definition_version_id",
            "code",
            name="uq_catalog_fact_def_enum_values_version_code",
        ),
        sa.CheckConstraint("sequence BETWEEN 1 AND 64", name="fact_def_enum_value_sequence_bounds"),
        sa.CheckConstraint(
            FactEnumValueCodeFormat(sa.column("code")),
            name="fact_def_enum_value_code_format",
        ),
        sa.CheckConstraint("length(code) BETWEEN 1 AND 64", name="fact_def_enum_value_code_length"),
        sa.CheckConstraint(
            "label = trim(label) AND length(label) BETWEEN 1 AND 256",
            name="fact_def_enum_value_label_trim",
        ),
    )

    # PostgreSQL: Security RLS, privileges, append-only triggers, and sequence guards
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # RLS and revocations
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

        # Trigger function 1: catalog_fact_definition_append_only
        op.execute("""
            CREATE OR REPLACE FUNCTION public.catalog_fact_definition_append_only()
            RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
            AS $$
            BEGIN
                RAISE EXCEPTION 'catalog fact definition content is append-only';
            END;
            $$;
        """)
        op.execute(
            "REVOKE ALL ON FUNCTION public.catalog_fact_definition_append_only() FROM PUBLIC"
        )

        for table in TABLES:
            op.execute(f"""
                CREATE TRIGGER "{table}_immutable"
                BEFORE UPDATE OR DELETE ON public."{table}"
                FOR EACH ROW EXECUTE FUNCTION public.catalog_fact_definition_append_only()
            """)
            op.execute(f"""
                CREATE TRIGGER "{table}_no_truncate"
                BEFORE TRUNCATE ON public."{table}"
                FOR EACH STATEMENT EXECUTE FUNCTION public.catalog_fact_definition_append_only()
            """)

        # Trigger function 2: catalog_fact_definition_version_sequence_guard
        op.execute("""
            CREATE OR REPLACE FUNCTION public.catalog_fact_definition_version_sequence_guard()
            RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
            AS $$
            DECLARE
                v_locked_id uuid;
                v_expected_rev integer;
            BEGIN
                SELECT id INTO v_locked_id
                FROM public.catalog_fact_definitions
                WHERE id = NEW.fact_definition_id
                FOR UPDATE;

                IF v_locked_id IS NULL THEN
                    RAISE EXCEPTION 'FactDefinition % not found for revision allocation', NEW.fact_definition_id;
                END IF;

                SELECT COALESCE(MAX(revision), 0) + 1 INTO v_expected_rev
                FROM public.catalog_fact_definition_versions
                WHERE fact_definition_id = NEW.fact_definition_id;

                IF NEW.revision <> v_expected_rev THEN
                    RAISE EXCEPTION 'Invalid revision % for FactDefinitionVersion; expected %', NEW.revision, v_expected_rev;
                END IF;

                RETURN NEW;
            END;
            $$;
        """)
        op.execute(
            "REVOKE ALL ON FUNCTION public.catalog_fact_definition_version_sequence_guard() FROM PUBLIC"
        )
        op.execute("""
            CREATE TRIGGER trg_catalog_fact_def_version_sequence
            BEFORE INSERT ON public.catalog_fact_definition_versions
            FOR EACH ROW EXECUTE FUNCTION public.catalog_fact_definition_version_sequence_guard()
        """)

        # Trigger function 3: catalog_fact_definition_scope_sequence_guard
        op.execute("""
            CREATE OR REPLACE FUNCTION public.catalog_fact_definition_scope_sequence_guard()
            RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
            AS $$
            DECLARE
                v_locked_id uuid;
                v_expected_seq integer;
            BEGIN
                SELECT id INTO v_locked_id
                FROM public.catalog_fact_definition_versions
                WHERE id = NEW.fact_definition_version_id
                FOR UPDATE;

                IF v_locked_id IS NULL THEN
                    RAISE EXCEPTION 'FactDefinitionVersion % not found for scope allocation', NEW.fact_definition_version_id;
                END IF;

                SELECT COALESCE(MAX(sequence), 0) + 1 INTO v_expected_seq
                FROM public.catalog_fact_definition_scopes
                WHERE fact_definition_version_id = NEW.fact_definition_version_id;

                IF NEW.sequence <> v_expected_seq THEN
                    RAISE EXCEPTION 'Invalid sequence % for FactDefinitionScope; expected %', NEW.sequence, v_expected_seq;
                END IF;

                RETURN NEW;
            END;
            $$;
        """)
        op.execute(
            "REVOKE ALL ON FUNCTION public.catalog_fact_definition_scope_sequence_guard() FROM PUBLIC"
        )
        op.execute("""
            CREATE TRIGGER trg_catalog_fact_def_scope_sequence
            BEFORE INSERT ON public.catalog_fact_definition_scopes
            FOR EACH ROW EXECUTE FUNCTION public.catalog_fact_definition_scope_sequence_guard()
        """)

        # Trigger function 4: catalog_fact_definition_enum_value_sequence_guard
        op.execute("""
            CREATE OR REPLACE FUNCTION public.catalog_fact_definition_enum_value_sequence_guard()
            RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
            AS $$
            DECLARE
                v_locked_id uuid;
                v_value_type varchar;
                v_expected_seq integer;
            BEGIN
                SELECT id, value_type INTO v_locked_id, v_value_type
                FROM public.catalog_fact_definition_versions
                WHERE id = NEW.fact_definition_version_id
                FOR UPDATE;

                IF v_locked_id IS NULL THEN
                    RAISE EXCEPTION 'FactDefinitionVersion % not found for enum value allocation', NEW.fact_definition_version_id;
                END IF;

                IF v_value_type <> 'enum' THEN
                    RAISE EXCEPTION 'Cannot add enum value to FactDefinitionVersion % with value_type %', NEW.fact_definition_version_id, v_value_type;
                END IF;

                SELECT COALESCE(MAX(sequence), 0) + 1 INTO v_expected_seq
                FROM public.catalog_fact_definition_enum_values
                WHERE fact_definition_version_id = NEW.fact_definition_version_id;

                IF NEW.sequence <> v_expected_seq THEN
                    RAISE EXCEPTION 'Invalid sequence % for FactDefinitionEnumValue; expected %', NEW.sequence, v_expected_seq;
                END IF;

                RETURN NEW;
            END;
            $$;
        """)
        op.execute(
            "REVOKE ALL ON FUNCTION public.catalog_fact_definition_enum_value_sequence_guard() FROM PUBLIC"
        )
        op.execute("""
            CREATE TRIGGER trg_catalog_fact_def_enum_val_sequence
            BEFORE INSERT ON public.catalog_fact_definition_enum_values
            FOR EACH ROW EXECUTE FUNCTION public.catalog_fact_definition_enum_value_sequence_guard()
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("SET LOCAL row_security = off")
        op.execute(
            "LOCK TABLE "
            "public.catalog_fact_definition_enum_values, "
            "public.catalog_fact_definition_scopes, "
            "public.catalog_fact_definition_versions, "
            "public.catalog_fact_definitions "
            "IN ACCESS EXCLUSIVE MODE"
        )
        op.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM public.catalog_fact_definition_enum_values)
                   OR EXISTS (SELECT 1 FROM public.catalog_fact_definition_scopes)
                   OR EXISTS (SELECT 1 FROM public.catalog_fact_definition_versions)
                   OR EXISTS (SELECT 1 FROM public.catalog_fact_definitions) THEN
                    RAISE EXCEPTION 'CANNOT_DOWNGRADE_FACT_DEFINITION_DATA_EXISTS';
                END IF;
            END $$;
        """)

        # Drop triggers
        for table in reversed(TABLES):
            op.execute(f'DROP TRIGGER IF EXISTS "{table}_no_truncate" ON public."{table}"')
            op.execute(f'DROP TRIGGER IF EXISTS "{table}_immutable" ON public."{table}"')

        op.execute(
            "DROP TRIGGER IF EXISTS trg_catalog_fact_def_enum_val_sequence ON public.catalog_fact_definition_enum_values"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_catalog_fact_def_scope_sequence ON public.catalog_fact_definition_scopes"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_catalog_fact_def_version_sequence ON public.catalog_fact_definition_versions"
        )

        op.execute(
            "DROP FUNCTION IF EXISTS public.catalog_fact_definition_enum_value_sequence_guard()"
        )
        op.execute("DROP FUNCTION IF EXISTS public.catalog_fact_definition_scope_sequence_guard()")
        op.execute(
            "DROP FUNCTION IF EXISTS public.catalog_fact_definition_version_sequence_guard()"
        )
        op.execute("DROP FUNCTION IF EXISTS public.catalog_fact_definition_append_only()")

    # Drop tables in reverse dependency order
    for table in reversed(TABLES):
        op.drop_table(table)
