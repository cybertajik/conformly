"""Customer control work and evidence pinning vertical slice tables, constraints, RLS and triggers (MVP-B)

Revision ID: 20261022_0046
Revises: 20261020_0045
Create Date: 2026-10-22 18:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20261022_0046"
down_revision: str | Sequence[str] | None = "20261020_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"

    def digest_ck(col: str) -> str:
        if is_pg:
            return f"length({col}) = 64 AND {col} ~ '^[0-9a-f]{{64}}$'"
        return f"length({col}) = 64 AND NOT ({col} GLOB '*[^0-9a-f]*')"

    # 1. customer_control_work
    op.create_table(
        "customer_control_work",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "adoption_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "control_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "control_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "due_date",
            sa.Date(),
            nullable=True,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("version > 0", name="ck_customer_control_work_version_pos"),
        sa.UniqueConstraint(
            "tenant_id",
            "adoption_id",
            "control_version_id",
            name="uq_customer_control_work_tenant_adoption_ctrl_ver",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "adoption_id"],
            ["customer_demo_adoptions.tenant_id", "customer_demo_adoptions.id"],
            ondelete="RESTRICT",
            name="fk_customer_control_work_adoption",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "owner_user_id"],
            ["memberships.tenant_id", "memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_customer_control_work_owner_membership",
        ),
    )
    op.create_index(
        "ix_customer_control_work_tenant_adoption",
        "customer_control_work",
        ["tenant_id", "adoption_id"],
    )

    # 2. customer_control_evidence_links
    op.create_table(
        "customer_control_evidence_links",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "work_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "evidence_revision_number",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "evidence_revision_digest",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "rationale_encrypted",
            sa.JSON().with_variant(postgresql.JSONB, "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "evidence_revision_number > 0",
            name="ck_customer_control_evidence_links_rev_pos",
        ),
        sa.CheckConstraint(
            digest_ck("evidence_revision_digest"),
            name="ck_customer_control_evidence_links_rev_digest",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "work_id",
            "evidence_id",
            "evidence_revision_number",
            name="uq_customer_control_evidence_links_natural",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            "work_id",
            name="uq_customer_control_evidence_links_tenant_id_work",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "work_id"],
            ["customer_control_work.tenant_id", "customer_control_work.id"],
            ondelete="RESTRICT",
            name="fk_customer_control_evidence_links_work",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "evidence_id", "evidence_revision_number"],
            [
                "evidence_revisions.tenant_id",
                "evidence_revisions.evidence_id",
                "evidence_revisions.revision_number",
            ],
            ondelete="RESTRICT",
            name="fk_customer_control_evidence_links_evidence_rev",
        ),
    )
    op.create_index(
        "ix_customer_control_evidence_links_tenant_evidence",
        "customer_control_evidence_links",
        ["tenant_id", "evidence_id"],
    )

    # 3. customer_control_work_events
    op.create_table(
        "customer_control_work_events",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "work_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "work_revision",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "operation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "request_digest",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "link_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "decision",
            sa.String(16),
            nullable=True,
        ),
        sa.Column(
            "details_encrypted",
            sa.JSON().with_variant(postgresql.JSONB, "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "work_revision > 0",
            name="ck_customer_control_work_events_rev_pos",
        ),
        sa.CheckConstraint(
            digest_ck("request_digest"),
            name="ck_customer_control_work_events_req_digest",
        ),
        sa.CheckConstraint(
            "event_type IN ('INITIALIZED', 'OWNER_DUE_UPDATED', 'EVIDENCE_LINKED', 'EVIDENCE_REVIEWED')",
            name="ck_customer_control_work_events_type",
        ),
        sa.CheckConstraint(
            "decision IS NULL OR decision IN ('ACCEPTED', 'REJECTED')",
            name="ck_customer_control_work_events_decision",
        ),
        sa.CheckConstraint(
            "(event_type = 'EVIDENCE_REVIEWED' AND link_id IS NOT NULL AND decision IS NOT NULL) OR "
            "(event_type = 'EVIDENCE_LINKED' AND link_id IS NOT NULL AND decision IS NULL) OR "
            "(event_type IN ('INITIALIZED', 'OWNER_DUE_UPDATED') AND link_id IS NULL AND decision IS NULL)",
            name="ck_customer_control_work_events_type_coherence",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "work_id",
            "work_revision",
            name="uq_customer_control_work_events_tenant_work_rev",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "operation_id",
            name="uq_customer_control_work_events_tenant_op",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "work_id"],
            ["customer_control_work.tenant_id", "customer_control_work.id"],
            ondelete="RESTRICT",
            name="fk_customer_control_work_events_work",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "link_id", "work_id"],
            [
                "customer_control_evidence_links.tenant_id",
                "customer_control_evidence_links.id",
                "customer_control_evidence_links.work_id",
            ],
            ondelete="RESTRICT",
            name="fk_customer_control_work_events_link",
        ),
    )
    op.create_index(
        "ix_customer_control_work_events_tenant_work_rev",
        "customer_control_work_events",
        ["tenant_id", "work_id", "work_revision"],
    )

    if is_pg:
        # Enable and Force RLS
        for tbl in [
            "customer_control_work",
            "customer_control_evidence_links",
            "customer_control_work_events",
        ]:
            op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")

        # Triggers for immutability of links and events
        op.execute("""
        CREATE OR REPLACE FUNCTION customer_control_prevent_history_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION '% rows are immutable and cannot be updated or deleted', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """)

        op.execute("""
        CREATE TRIGGER trg_customer_control_evidence_links_immutable
        BEFORE UPDATE OR DELETE ON customer_control_evidence_links
        FOR EACH ROW EXECUTE FUNCTION customer_control_prevent_history_modification();
        """)

        op.execute("""
        CREATE TRIGGER trg_customer_control_work_events_immutable
        BEFORE UPDATE OR DELETE ON customer_control_work_events
        FOR EACH ROW EXECUTE FUNCTION customer_control_prevent_history_modification();
        """)

        # Work protection trigger
        op.execute("""
        CREATE OR REPLACE FUNCTION customer_control_work_protect()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'customer_control_work rows cannot be deleted';
            END IF;
            IF NEW.tenant_id <> OLD.tenant_id OR NEW.id <> OLD.id OR NEW.adoption_id <> OLD.adoption_id OR NEW.control_id <> OLD.control_id OR NEW.control_version_id <> OLD.control_version_id OR NEW.created_at <> OLD.created_at THEN
                RAISE EXCEPTION 'customer_control_work identity columns are immutable';
            END IF;
            IF NEW.version <> OLD.version + 1 THEN
                RAISE EXCEPTION 'customer_control_work version must increment by exactly one';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)

        op.execute("""
        CREATE TRIGGER trg_customer_control_work_protect
        BEFORE UPDATE OR DELETE ON customer_control_work
        FOR EACH ROW EXECUTE FUNCTION customer_control_work_protect();
        """)

        # Role grants and RLS policies
        op.execute("""
        DO $$
        DECLARE
            has_app_role boolean;
            has_catalog_role boolean;
            has_fact_role boolean;
            has_rule_role boolean;
        BEGIN
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'conformly_app') INTO has_app_role;
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'conformly_catalog') INTO has_catalog_role;
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'conformly_catalog_fact_author') INTO has_fact_role;
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'conformly_catalog_rule_author') INTO has_rule_role;

            -- Revoke all table privileges from PUBLIC
            REVOKE ALL ON public.customer_control_work, public.customer_control_evidence_links, public.customer_control_work_events FROM PUBLIC;

            -- Revoke all function privileges from PUBLIC
            REVOKE ALL ON FUNCTION public.customer_control_prevent_history_modification() FROM PUBLIC;
            REVOKE ALL ON FUNCTION public.customer_control_work_protect() FROM PUBLIC;

            IF has_catalog_role THEN
                REVOKE ALL PRIVILEGES ON public.customer_control_work, public.customer_control_evidence_links, public.customer_control_work_events FROM "conformly_catalog";
                REVOKE ALL ON FUNCTION public.customer_control_prevent_history_modification() FROM "conformly_catalog";
                REVOKE ALL ON FUNCTION public.customer_control_work_protect() FROM "conformly_catalog";
            END IF;

            IF has_fact_role THEN
                REVOKE ALL PRIVILEGES ON public.customer_control_work, public.customer_control_evidence_links, public.customer_control_work_events FROM "conformly_catalog_fact_author";
                REVOKE ALL ON FUNCTION public.customer_control_prevent_history_modification() FROM "conformly_catalog_fact_author";
                REVOKE ALL ON FUNCTION public.customer_control_work_protect() FROM "conformly_catalog_fact_author";
            END IF;

            IF has_rule_role THEN
                REVOKE ALL PRIVILEGES ON public.customer_control_work, public.customer_control_evidence_links, public.customer_control_work_events FROM "conformly_catalog_rule_author";
                REVOKE ALL ON FUNCTION public.customer_control_prevent_history_modification() FROM "conformly_catalog_rule_author";
                REVOKE ALL ON FUNCTION public.customer_control_work_protect() FROM "conformly_catalog_rule_author";
            END IF;

            IF has_app_role THEN
                REVOKE ALL PRIVILEGES ON public.customer_control_work, public.customer_control_evidence_links, public.customer_control_work_events FROM "conformly_app";

                GRANT SELECT, INSERT ON public.customer_control_work TO "conformly_app";
                GRANT UPDATE (owner_user_id, due_date, version, updated_at) ON public.customer_control_work TO "conformly_app";

                GRANT SELECT, INSERT ON public.customer_control_evidence_links TO "conformly_app";
                GRANT SELECT, INSERT ON public.customer_control_work_events TO "conformly_app";

                -- Clear inherited/default explicit app grants on functions and grant EXECUTE only to conformly_app
                REVOKE ALL ON FUNCTION public.customer_control_prevent_history_modification() FROM "conformly_app";
                REVOKE ALL ON FUNCTION public.customer_control_work_protect() FROM "conformly_app";
                GRANT EXECUTE ON FUNCTION public.customer_control_prevent_history_modification() TO "conformly_app";
                GRANT EXECUTE ON FUNCTION public.customer_control_work_protect() TO "conformly_app";

                EXECUTE $pol$CREATE POLICY wp09b_customer_control_work ON customer_control_work TO conformly_app USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true') WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true')$pol$;

                EXECUTE $pol$CREATE POLICY wp09b_customer_control_evidence_links ON customer_control_evidence_links TO conformly_app USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true') WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true')$pol$;

                EXECUTE $pol$CREATE POLICY wp09b_customer_control_work_events ON customer_control_work_events TO conformly_app USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true') WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true')$pol$;
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
            cnt_work integer := 0;
            cnt_links integer := 0;
            cnt_events integer := 0;
        BEGIN
            SELECT count(*) INTO cnt_work FROM customer_control_work;
            SELECT count(*) INTO cnt_links FROM customer_control_evidence_links;
            SELECT count(*) INTO cnt_events FROM customer_control_work_events;

            IF (cnt_work + cnt_links + cnt_events) > 0 THEN
                RAISE EXCEPTION 'CANNOT_DOWNGRADE_CUSTOMER_CONTROL_EVIDENCE_DATA_EXISTS';
            END IF;
        END $$;
        """)
    else:
        conn = op.get_bind()
        total_rows = 0
        for tbl in [
            "customer_control_work",
            "customer_control_evidence_links",
            "customer_control_work_events",
        ]:
            res = conn.execute(sa.text(f"SELECT count(*) FROM {tbl}")).scalar() or 0
            total_rows += res
        if total_rows > 0:
            raise RuntimeError("CANNOT_DOWNGRADE_CUSTOMER_CONTROL_EVIDENCE_DATA_EXISTS")

    if is_pg:
        op.execute(
            "DROP TRIGGER IF EXISTS trg_customer_control_work_protect ON customer_control_work"
        )
        op.execute("DROP FUNCTION IF EXISTS customer_control_work_protect")
        op.execute(
            "DROP TRIGGER IF EXISTS trg_customer_control_work_events_immutable ON customer_control_work_events"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_customer_control_evidence_links_immutable ON customer_control_evidence_links"
        )
        op.execute("DROP FUNCTION IF EXISTS customer_control_prevent_history_modification")

    op.drop_table("customer_control_work_events")
    op.drop_table("customer_control_evidence_links")
    op.drop_table("customer_control_work")
