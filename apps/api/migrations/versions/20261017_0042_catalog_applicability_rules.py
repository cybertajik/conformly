"""catalog applicability rules foundation (WP-07C2)

Revision ID: 20261017_0042
Revises: 20261017_0041
Create Date: 2026-10-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from conformly.catalog_v2.models import RuleKeyFormat

# revision identifiers, used by Alembic.
revision = "20261017_0042"
down_revision = "20261017_0041"
branch_labels = None
depends_on = None

TABLES = (
    "catalog_applicability_rules",
    "catalog_applicability_rule_versions",
    "catalog_applicability_rule_fact_refs",
    "catalog_applicability_rule_source_refs",
)


def upgrade() -> None:
    # 1. catalog_applicability_rules
    op.create_table(
        "catalog_applicability_rules",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("rule_key", sa.String(64), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["catalog_requirements.id"],
            name="fk_catalog_app_rules_requirement",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "requirement_id", name="uq_catalog_app_rules_id_requirement"),
        sa.UniqueConstraint("rule_key", name="uq_catalog_app_rules_key"),
        sa.CheckConstraint(RuleKeyFormat(sa.column("rule_key")), name="app_rule_key_format"),
        sa.CheckConstraint("length(rule_key) BETWEEN 3 AND 64", name="app_rule_key_length"),
        sa.CheckConstraint("status = 'Draft'", name="app_rule_status_draft"),
    )

    # 2. catalog_applicability_rule_versions
    op.create_table(
        "catalog_applicability_rule_versions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_version_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_version_digest_snapshot", sa.LargeBinary(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("version_label", sa.String(64), nullable=False),
        sa.Column("predecessor_id", sa.Uuid(), nullable=True),
        sa.Column("predecessor_revision", sa.Integer(), nullable=True),
        sa.Column("expression_ast_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("expression_canonical", sa.LargeBinary(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("status", sa.String(16), server_default="Draft", nullable=False),
        sa.Column("content_digest", sa.LargeBinary(), nullable=False),
        sa.Column(
            "digest_schema",
            sa.String(64),
            server_default="catalog-applicability-rule-draft-v1",
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
            ["rule_id", "requirement_id"],
            ["catalog_applicability_rules.id", "catalog_applicability_rules.requirement_id"],
            name="fk_catalog_app_rule_versions_rule",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id"],
            ["catalog_requirement_versions.id", "catalog_requirement_versions.requirement_id"],
            name="fk_catalog_app_rule_versions_req_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_id", "rule_id", "predecessor_revision"],
            [
                "catalog_applicability_rule_versions.id",
                "catalog_applicability_rule_versions.rule_id",
                "catalog_applicability_rule_versions.revision",
            ],
            name="fk_catalog_app_rule_versions_predecessor",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "rule_id",
            "revision",
            name="uq_catalog_app_rule_versions_rule_rev",
        ),
        sa.UniqueConstraint(
            "rule_id",
            "version_label",
            name="uq_catalog_app_rule_versions_rule_label",
        ),
        sa.UniqueConstraint(
            "id",
            "rule_id",
            "revision",
            name="uq_catalog_app_rule_versions_lineage",
        ),
        sa.CheckConstraint("revision BETWEEN 1 AND 32767", name="app_rule_version_revision_bounds"),
        sa.CheckConstraint(
            "((revision = 1 AND predecessor_id IS NULL AND predecessor_revision IS NULL) OR "
            "(revision > 1 AND predecessor_id IS NOT NULL AND predecessor_revision IS NOT NULL "
            "AND predecessor_revision = revision - 1 AND predecessor_id != id))",
            name="app_rule_version_predecessor_shape",
        ),
        sa.CheckConstraint(
            "version_label = trim(version_label) AND length(version_label) BETWEEN 1 AND 64",
            name="app_rule_version_label_trim",
        ),
        sa.CheckConstraint("expression_ast_version = 1", name="app_rule_version_ast_version"),
        sa.CheckConstraint(
            "length(expression_canonical) BETWEEN 2 AND 16384",
            name="app_rule_version_expression_bytes",
        ),
        sa.CheckConstraint(
            "effective_from IS NULL OR effective_until IS NULL OR effective_until >= effective_from",
            name="app_rule_version_effective_dates",
        ),
        sa.CheckConstraint("status = 'Draft'", name="app_rule_version_status_draft"),
        sa.CheckConstraint("length(content_digest) = 32", name="app_rule_version_digest_32_bytes"),
        sa.CheckConstraint(
            "digest_schema = 'catalog-applicability-rule-draft-v1'",
            name="app_rule_version_digest_schema",
        ),
        sa.CheckConstraint(
            "length(requirement_version_digest_snapshot) = 32",
            name="app_rule_version_target_digest_32_bytes",
        ),
    )

    # 3. catalog_applicability_rule_fact_refs
    op.create_table(
        "catalog_applicability_rule_fact_refs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("rule_version_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("fact_definition_version_id", sa.Uuid(), nullable=False),
        sa.Column("content_digest_snapshot", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["rule_version_id"],
            ["catalog_applicability_rule_versions.id"],
            name="fk_catalog_app_fact_refs_rule_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["fact_definition_version_id"],
            ["catalog_fact_definition_versions.id"],
            name="fk_catalog_app_fact_refs_fact_version",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "rule_version_id",
            "sequence",
            name="uq_catalog_app_fact_refs_version_seq",
        ),
        sa.UniqueConstraint(
            "rule_version_id",
            "fact_definition_version_id",
            name="uq_catalog_app_fact_refs_version_fact",
        ),
        sa.CheckConstraint("sequence BETWEEN 1 AND 64", name="app_fact_ref_sequence_bounds"),
        sa.CheckConstraint(
            "length(content_digest_snapshot) = 32",
            name="app_fact_ref_digest_32_bytes",
        ),
    )

    # 4. catalog_applicability_rule_source_refs
    op.create_table(
        "catalog_applicability_rule_source_refs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("rule_version_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column("content_digest_snapshot", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["rule_version_id"],
            ["catalog_applicability_rule_versions.id"],
            name="fk_catalog_app_source_refs_rule_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["catalog_source_versions.id"],
            name="fk_catalog_app_source_refs_source_version",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "rule_version_id",
            "sequence",
            name="uq_catalog_app_source_refs_version_seq",
        ),
        sa.UniqueConstraint(
            "rule_version_id",
            "source_version_id",
            name="uq_catalog_app_source_refs_version_source",
        ),
        sa.CheckConstraint("sequence BETWEEN 1 AND 64", name="app_source_ref_sequence_bounds"),
        sa.CheckConstraint(
            "length(content_digest_snapshot) = 32",
            name="app_source_ref_digest_32_bytes",
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

        # Trigger function 1: catalog_app_rule_append_only
        op.execute("""
            CREATE OR REPLACE FUNCTION public.catalog_app_rule_append_only()
            RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
            AS $$
            BEGIN
                RAISE EXCEPTION 'catalog applicability rule content is append-only';
            END;
            $$;
        """)
        op.execute("REVOKE ALL ON FUNCTION public.catalog_app_rule_append_only() FROM PUBLIC")

        for table in TABLES:
            op.execute(f"""
                CREATE TRIGGER "{table}_immutable"
                BEFORE UPDATE OR DELETE ON public."{table}"
                FOR EACH ROW EXECUTE FUNCTION public.catalog_app_rule_append_only()
            """)
            op.execute(f"""
                CREATE TRIGGER "{table}_no_truncate"
                BEFORE TRUNCATE ON public."{table}"
                FOR EACH STATEMENT EXECUTE FUNCTION public.catalog_app_rule_append_only()
            """)

        # Trigger function 2: catalog_app_rule_version_sequence_guard
        op.execute("""
            CREATE OR REPLACE FUNCTION public.catalog_app_rule_version_sequence_guard()
            RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
            AS $$
            DECLARE
                v_locked_id uuid;
                v_expected_rev integer;
            BEGIN
                SELECT id INTO v_locked_id
                FROM public.catalog_applicability_rules
                WHERE id = NEW.rule_id
                FOR UPDATE;

                IF v_locked_id IS NULL THEN
                    RAISE EXCEPTION 'ApplicabilityRule % not found for revision allocation', NEW.rule_id;
                END IF;

                SELECT COALESCE(MAX(revision), 0) + 1 INTO v_expected_rev
                FROM public.catalog_applicability_rule_versions
                WHERE rule_id = NEW.rule_id;

                IF NEW.revision <> v_expected_rev THEN
                    RAISE EXCEPTION 'Invalid revision % for ApplicabilityRuleVersion; expected %', NEW.revision, v_expected_rev;
                END IF;

                RETURN NEW;
            END;
            $$;
        """)
        op.execute(
            "REVOKE ALL ON FUNCTION public.catalog_app_rule_version_sequence_guard() FROM PUBLIC"
        )
        op.execute("""
            CREATE TRIGGER trg_catalog_app_rule_version_sequence
            BEFORE INSERT ON public.catalog_applicability_rule_versions
            FOR EACH ROW EXECUTE FUNCTION public.catalog_app_rule_version_sequence_guard()
        """)

        # Trigger function 3: catalog_app_rule_fact_ref_sequence_guard
        op.execute("""
            CREATE OR REPLACE FUNCTION public.catalog_app_rule_fact_ref_sequence_guard()
            RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
            AS $$
            DECLARE
                v_locked_id uuid;
                v_expected_seq integer;
            BEGIN
                SELECT id INTO v_locked_id
                FROM public.catalog_applicability_rule_versions
                WHERE id = NEW.rule_version_id
                FOR UPDATE;

                IF v_locked_id IS NULL THEN
                    RAISE EXCEPTION 'ApplicabilityRuleVersion % not found for fact ref allocation', NEW.rule_version_id;
                END IF;

                SELECT COALESCE(MAX(sequence), 0) + 1 INTO v_expected_seq
                FROM public.catalog_applicability_rule_fact_refs
                WHERE rule_version_id = NEW.rule_version_id;

                IF NEW.sequence <> v_expected_seq THEN
                    RAISE EXCEPTION 'Invalid sequence % for ApplicabilityRuleFactRef; expected %', NEW.sequence, v_expected_seq;
                END IF;

                RETURN NEW;
            END;
            $$;
        """)
        op.execute(
            "REVOKE ALL ON FUNCTION public.catalog_app_rule_fact_ref_sequence_guard() FROM PUBLIC"
        )
        op.execute("""
            CREATE TRIGGER trg_catalog_app_rule_fact_ref_sequence
            BEFORE INSERT ON public.catalog_applicability_rule_fact_refs
            FOR EACH ROW EXECUTE FUNCTION public.catalog_app_rule_fact_ref_sequence_guard()
        """)

        # Trigger function 4: catalog_app_rule_source_ref_sequence_guard
        op.execute("""
            CREATE OR REPLACE FUNCTION public.catalog_app_rule_source_ref_sequence_guard()
            RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
            AS $$
            DECLARE
                v_locked_id uuid;
                v_expected_seq integer;
            BEGIN
                SELECT id INTO v_locked_id
                FROM public.catalog_applicability_rule_versions
                WHERE id = NEW.rule_version_id
                FOR UPDATE;

                IF v_locked_id IS NULL THEN
                    RAISE EXCEPTION 'ApplicabilityRuleVersion % not found for source ref allocation', NEW.rule_version_id;
                END IF;

                SELECT COALESCE(MAX(sequence), 0) + 1 INTO v_expected_seq
                FROM public.catalog_applicability_rule_source_refs
                WHERE rule_version_id = NEW.rule_version_id;

                IF NEW.sequence <> v_expected_seq THEN
                    RAISE EXCEPTION 'Invalid sequence % for ApplicabilityRuleSourceRef; expected %', NEW.sequence, v_expected_seq;
                END IF;

                RETURN NEW;
            END;
            $$;
        """)
        op.execute(
            "REVOKE ALL ON FUNCTION public.catalog_app_rule_source_ref_sequence_guard() FROM PUBLIC"
        )
        op.execute("""
            CREATE TRIGGER trg_catalog_app_rule_source_ref_sequence
            BEFORE INSERT ON public.catalog_applicability_rule_source_refs
            FOR EACH ROW EXECUTE FUNCTION public.catalog_app_rule_source_ref_sequence_guard()
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("SET LOCAL row_security = off")
        op.execute(
            "LOCK TABLE "
            "public.catalog_applicability_rule_source_refs, "
            "public.catalog_applicability_rule_fact_refs, "
            "public.catalog_applicability_rule_versions, "
            "public.catalog_applicability_rules "
            "IN ACCESS EXCLUSIVE MODE"
        )
        op.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM public.catalog_applicability_rule_source_refs)
                   OR EXISTS (SELECT 1 FROM public.catalog_applicability_rule_fact_refs)
                   OR EXISTS (SELECT 1 FROM public.catalog_applicability_rule_versions)
                   OR EXISTS (SELECT 1 FROM public.catalog_applicability_rules) THEN
                    RAISE EXCEPTION 'CANNOT_DOWNGRADE_APPLICABILITY_RULE_DATA_EXISTS';
                END IF;
            END $$;
        """)

        # Drop triggers
        for table in reversed(TABLES):
            op.execute(f'DROP TRIGGER IF EXISTS "{table}_no_truncate" ON public."{table}"')
            op.execute(f'DROP TRIGGER IF EXISTS "{table}_immutable" ON public."{table}"')

        op.execute(
            "DROP TRIGGER IF EXISTS trg_catalog_app_rule_source_ref_sequence ON public.catalog_applicability_rule_source_refs"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_catalog_app_rule_fact_ref_sequence ON public.catalog_applicability_rule_fact_refs"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_catalog_app_rule_version_sequence ON public.catalog_applicability_rule_versions"
        )

        op.execute("DROP FUNCTION IF EXISTS public.catalog_app_rule_source_ref_sequence_guard()")
        op.execute("DROP FUNCTION IF EXISTS public.catalog_app_rule_fact_ref_sequence_guard()")
        op.execute("DROP FUNCTION IF EXISTS public.catalog_app_rule_version_sequence_guard()")
        op.execute("DROP FUNCTION IF EXISTS public.catalog_app_rule_append_only()")

    # Drop tables in reverse dependency order
    for table in reversed(TABLES):
        op.drop_table(table)
