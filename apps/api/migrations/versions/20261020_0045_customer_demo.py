"""Customer demo onboarding vertical slice tables, constraints, RLS and triggers (WP-09)

Revision ID: 20261020_0045
Revises: 20261020_0044
Create Date: 2026-10-20 18:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20261020_0045"
down_revision: str | Sequence[str] | None = "20261020_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"

    def digest_ck(col: str) -> str:
        if is_pg:
            return f"length({col}) = 64 AND {col} ~ '^[0-9a-f]{{64}}$'"
        return f"length({col}) = 64 AND NOT ({col} GLOB '*[^0-9a-f]*')"

    # 1. customer_demo_workspaces
    op.create_table(
        "customer_demo_workspaces",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("current_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("selection_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("current_revision >= 0", name="ck_customer_demo_workspaces_current_rev"),
        sa.CheckConstraint(
            "selection_revision >= 0", name="ck_customer_demo_workspaces_selection_rev"
        ),
    )

    # 2. customer_demo_answers
    op.create_table(
        "customer_demo_answers",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_demo_workspaces.tenant_id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("company_code", sa.String(32), nullable=False),
        sa.Column(
            "answers", sa.JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=False
        ),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("revision > 0", name="ck_customer_demo_answers_rev_pos"),
        sa.CheckConstraint(
            "company_code IN ('ALPHA', 'BETA')", name="ck_customer_demo_answers_company_code"
        ),
        sa.CheckConstraint(
            digest_ck("content_digest"), name="ck_customer_demo_answers_content_digest_format"
        ),
    )

    # 3. customer_demo_evaluations
    op.create_table(
        "customer_demo_evaluations",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("answer_revision", sa.Integer(), nullable=False),
        sa.Column("pack_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bundle_digest", sa.String(64), nullable=False),
        sa.Column("evaluator_version", sa.String(64), nullable=False),
        sa.Column(
            "results", sa.JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=False
        ),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "answer_revision"],
            ["customer_demo_answers.tenant_id", "customer_demo_answers.revision"],
            ondelete="RESTRICT",
            name="fk_customer_demo_evaluations_answers",
        ),
        sa.CheckConstraint(
            digest_ck("bundle_digest"), name="ck_customer_demo_evaluations_bundle_digest_format"
        ),
        sa.CheckConstraint(
            digest_ck("content_digest"), name="ck_customer_demo_evaluations_content_digest_format"
        ),
    )

    # 4. customer_demo_adoptions
    op.create_table(
        "customer_demo_adoptions",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pack_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bundle_digest", sa.String(64), nullable=False),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("selection_revision", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "evaluation_id"],
            ["customer_demo_evaluations.tenant_id", "customer_demo_evaluations.id"],
            ondelete="RESTRICT",
            name="fk_customer_demo_adoptions_evaluation",
        ),
        sa.UniqueConstraint(
            "tenant_id", "evaluation_id", name="uq_customer_demo_adoptions_tenant_eval"
        ),
        sa.UniqueConstraint(
            "tenant_id", "selection_revision", name="uq_customer_demo_adoptions_tenant_sel_rev"
        ),
        sa.CheckConstraint(
            "selection_revision > 0", name="ck_customer_demo_adoptions_selection_rev_pos"
        ),
        sa.CheckConstraint(
            digest_ck("bundle_digest"), name="ck_customer_demo_adoptions_bundle_digest_format"
        ),
    )

    # PostgreSQL specific: RLS, Triggers, Grants
    if is_pg:
        # Enable and Force RLS
        for tbl in [
            "customer_demo_workspaces",
            "customer_demo_answers",
            "customer_demo_evaluations",
            "customer_demo_adoptions",
        ]:
            op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")

        # Revoke public access
        op.execute(
            "REVOKE ALL ON customer_demo_workspaces, customer_demo_answers, customer_demo_evaluations, customer_demo_adoptions FROM PUBLIC"
        )

        # Immutability triggers for history tables
        op.execute("""
        CREATE OR REPLACE FUNCTION customer_demo_prevent_history_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION '% rows are immutable and cannot be updated or deleted', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """)

        op.execute("""
        CREATE TRIGGER trg_customer_demo_answers_immutable
        BEFORE UPDATE OR DELETE ON customer_demo_answers
        FOR EACH ROW EXECUTE FUNCTION customer_demo_prevent_history_modification();
        """)

        op.execute("""
        CREATE TRIGGER trg_customer_demo_evaluations_immutable
        BEFORE UPDATE OR DELETE ON customer_demo_evaluations
        FOR EACH ROW EXECUTE FUNCTION customer_demo_prevent_history_modification();
        """)

        op.execute("""
        CREATE TRIGGER trg_customer_demo_adoptions_immutable
        BEFORE UPDATE OR DELETE ON customer_demo_adoptions
        FOR EACH ROW EXECUTE FUNCTION customer_demo_prevent_history_modification();
        """)

        # Workspace identity protection trigger
        op.execute("""
        CREATE OR REPLACE FUNCTION customer_demo_workspaces_protect_identity()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.tenant_id <> OLD.tenant_id THEN
                RAISE EXCEPTION 'customer_demo_workspaces tenant_id is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)

        op.execute("""
        CREATE TRIGGER trg_customer_demo_workspaces_protect_identity
        BEFORE UPDATE ON customer_demo_workspaces
        FOR EACH ROW EXECUTE FUNCTION customer_demo_workspaces_protect_identity();
        """)

        # Conditional role-targeted policies and grants for conformly_app
        op.execute("""
        DO $$
        DECLARE
            has_app_role boolean;
            has_catalog_role boolean;
        BEGIN
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'conformly_app') INTO has_app_role;
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'conformly_catalog') INTO has_catalog_role;

            -- Revoke from PUBLIC
            REVOKE ALL ON customer_demo_workspaces, customer_demo_answers, customer_demo_evaluations, customer_demo_adoptions FROM PUBLIC;

            IF has_catalog_role THEN
                REVOKE ALL PRIVILEGES ON customer_demo_workspaces, customer_demo_answers, customer_demo_evaluations, customer_demo_adoptions FROM "conformly_catalog";
            END IF;

            IF has_app_role THEN
                -- Revoke everything first to strip default privileges (DELETE, UPDATE, etc.)
                REVOKE ALL PRIVILEGES ON customer_demo_workspaces, customer_demo_answers, customer_demo_evaluations, customer_demo_adoptions FROM "conformly_app";

                -- Explicit grants for workspaces: SELECT, INSERT, UPDATE
                GRANT SELECT, INSERT ON customer_demo_workspaces TO "conformly_app";
                GRANT UPDATE (current_revision, selection_revision, updated_at) ON customer_demo_workspaces TO "conformly_app";

                -- Explicit grants for history tables: SELECT, INSERT only (NO UPDATE, NO DELETE)
                GRANT SELECT, INSERT ON customer_demo_answers TO "conformly_app";
                GRANT SELECT, INSERT ON customer_demo_evaluations TO "conformly_app";
                GRANT SELECT, INSERT ON customer_demo_adoptions TO "conformly_app";

                -- Policies
                EXECUTE $pol$CREATE POLICY wp09_customer_demo_workspaces ON customer_demo_workspaces TO conformly_app USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true') WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true')$pol$;

                EXECUTE $pol$CREATE POLICY wp09_customer_demo_answers ON customer_demo_answers TO conformly_app USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true') WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true')$pol$;

                EXECUTE $pol$CREATE POLICY wp09_customer_demo_evaluations ON customer_demo_evaluations TO conformly_app USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true') WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true')$pol$;

                EXECUTE $pol$CREATE POLICY wp09_customer_demo_adoptions ON customer_demo_adoptions TO conformly_app USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true') WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true')$pol$;
            END IF;
        END $$;
        """)


def downgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"

    # Refuse downgrade before any DDL if ANY table is populated
    if is_pg:
        op.execute("""
        DO $$
        DECLARE
            cnt_ws integer := 0;
            cnt_ans integer := 0;
            cnt_eval integer := 0;
            cnt_adopt integer := 0;
        BEGIN
            SELECT count(*) INTO cnt_ws FROM customer_demo_workspaces;
            SELECT count(*) INTO cnt_ans FROM customer_demo_answers;
            SELECT count(*) INTO cnt_eval FROM customer_demo_evaluations;
            SELECT count(*) INTO cnt_adopt FROM customer_demo_adoptions;

            IF (cnt_ws + cnt_ans + cnt_eval + cnt_adopt) > 0 THEN
                RAISE EXCEPTION 'CANNOT_DOWNGRADE_CUSTOMER_DEMO_DATA_EXISTS';
            END IF;
        END $$;
        """)
    else:
        conn = op.get_bind()
        total_rows = 0
        for tbl in [
            "customer_demo_workspaces",
            "customer_demo_answers",
            "customer_demo_evaluations",
            "customer_demo_adoptions",
        ]:
            res = conn.execute(sa.text(f"SELECT count(*) FROM {tbl}")).scalar() or 0
            total_rows += res
        if total_rows > 0:
            raise RuntimeError("CANNOT_DOWNGRADE_CUSTOMER_DEMO_DATA_EXISTS")

    if is_pg:
        op.execute(
            "DROP TRIGGER IF EXISTS trg_customer_demo_workspaces_protect_identity ON customer_demo_workspaces"
        )
        op.execute("DROP FUNCTION IF EXISTS customer_demo_workspaces_protect_identity")
        op.execute(
            "DROP TRIGGER IF EXISTS trg_customer_demo_adoptions_immutable ON customer_demo_adoptions"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_customer_demo_evaluations_immutable ON customer_demo_evaluations"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_customer_demo_answers_immutable ON customer_demo_answers"
        )
        op.execute("DROP FUNCTION IF EXISTS customer_demo_prevent_history_modification")

    op.drop_table("customer_demo_adoptions")
    op.drop_table("customer_demo_evaluations")
    op.drop_table("customer_demo_answers")
    op.drop_table("customer_demo_workspaces")
