"""Customer assessment vertical slice tables, constraints, RLS and triggers (MVP-C)

Revision ID: 20261025_0047
Revises: 20261022_0046
Create Date: 2026-10-25 08:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20261025_0047"
down_revision: str | Sequence[str] | None = "20261022_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"

    def digest_ck(col: str) -> str:
        if is_pg:
            return f"length({col}) = 64 AND {col} ~ '^[0-9a-f]{{64}}$'"
        return f"length({col}) = 64 AND NOT ({col} GLOB '*[^0-9a-f]*')"

    # 1. customer_assessment_heads
    op.create_table(
        "customer_assessment_heads",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "work_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "current_revision",
            sa.Integer(),
            nullable=False,
            server_default="0",
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
        sa.CheckConstraint(
            "current_revision >= 0",
            name="ck_customer_assessment_heads_rev_nonneg",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "work_id"],
            ["customer_control_work.tenant_id", "customer_control_work.id"],
            ondelete="RESTRICT",
            name="fk_customer_assessment_heads_work",
        ),
    )

    # 2. customer_assessment_events
    op.create_table(
        "customer_assessment_events",
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
            "revision",
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
            "result",
            sa.String(32),
            nullable=True,
        ),
        sa.Column(
            "observed_work_version",
            sa.Integer(),
            nullable=False,
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
        sa.CheckConstraint("revision > 0", name="ck_customer_assessment_events_rev_pos"),
        sa.CheckConstraint(
            digest_ck("request_digest"),
            name="ck_customer_assessment_events_req_digest",
        ),
        sa.CheckConstraint(
            "event_type IN ('ASSESSMENT', 'RETEST', 'FINDING_UPDATED')",
            name="ck_customer_assessment_events_type",
        ),
        sa.CheckConstraint(
            "result IS NULL OR result IN ('PASS', 'PARTIAL', 'FAIL', 'INSUFFICIENT_EVIDENCE')",
            name="ck_customer_assessment_events_res",
        ),
        sa.CheckConstraint(
            "(event_type IN ('ASSESSMENT', 'RETEST') AND result IS NOT NULL) OR "
            "(event_type = 'FINDING_UPDATED' AND result IS NULL)",
            name="ck_customer_assessment_events_type_res",
        ),
        sa.CheckConstraint(
            "observed_work_version > 0",
            name="ck_customer_assessment_events_work_ver_pos",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "work_id",
            "revision",
            name="uq_customer_assessment_events_work_rev",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "operation_id",
            name="uq_customer_assessment_events_op",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            "work_id",
            name="uq_customer_assessment_events_tenant_id_work",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "work_id"],
            ["customer_assessment_heads.tenant_id", "customer_assessment_heads.work_id"],
            ondelete="RESTRICT",
            name="fk_customer_assessment_events_head",
        ),
    )
    op.create_index(
        "ix_customer_assessment_events_work_rev",
        "customer_assessment_events",
        ["tenant_id", "work_id", "revision"],
    )

    # 3. customer_assessment_findings
    op.create_table(
        "customer_assessment_findings",
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
            "source_event_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "current_event_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.String(32),
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
            "status",
            sa.String(32),
            nullable=False,
            server_default="OPEN",
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
        sa.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_customer_assessment_findings_severity",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'IN_REMEDIATION', 'RESOLVED')",
            name="ck_customer_assessment_findings_status",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_customer_assessment_findings_ver_pos",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "source_event_id",
            name="uq_customer_assessment_findings_source_event",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "work_id"],
            ["customer_assessment_heads.tenant_id", "customer_assessment_heads.work_id"],
            ondelete="RESTRICT",
            name="fk_customer_assessment_findings_head",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_event_id", "work_id"],
            [
                "customer_assessment_events.tenant_id",
                "customer_assessment_events.id",
                "customer_assessment_events.work_id",
            ],
            ondelete="RESTRICT",
            name="fk_customer_assessment_findings_source_event",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "current_event_id", "work_id"],
            [
                "customer_assessment_events.tenant_id",
                "customer_assessment_events.id",
                "customer_assessment_events.work_id",
            ],
            ondelete="RESTRICT",
            name="fk_customer_assessment_findings_current_event",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "owner_user_id"],
            ["memberships.tenant_id", "memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_customer_assessment_findings_owner",
        ),
    )
    op.create_index(
        "ix_customer_assessment_findings_work_status",
        "customer_assessment_findings",
        ["tenant_id", "work_id", "status"],
    )

    if is_pg:
        # Enable and force RLS on all 3 tables
        for tbl in [
            "customer_assessment_heads",
            "customer_assessment_events",
            "customer_assessment_findings",
        ]:
            op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")

        # Trigger for events immutability
        op.execute("""
        CREATE OR REPLACE FUNCTION customer_assessment_prevent_history_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION '% rows are immutable and cannot be updated or deleted', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """)

        op.execute("""
        CREATE TRIGGER trg_customer_assessment_events_immutable
        BEFORE UPDATE OR DELETE ON customer_assessment_events
        FOR EACH ROW EXECUTE FUNCTION customer_assessment_prevent_history_modification();
        """)

        # Trigger for heads protection
        op.execute("""
        CREATE OR REPLACE FUNCTION customer_assessment_heads_protect()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'customer_assessment_heads rows cannot be deleted';
            END IF;
            IF NEW.tenant_id <> OLD.tenant_id OR NEW.work_id <> OLD.work_id OR NEW.created_at <> OLD.created_at THEN
                RAISE EXCEPTION 'customer_assessment_heads identity columns are immutable';
            END IF;
            IF NEW.current_revision <> OLD.current_revision + 1 THEN
                RAISE EXCEPTION 'customer_assessment_heads current_revision must increment by exactly one';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)

        op.execute("""
        CREATE TRIGGER trg_customer_assessment_heads_protect
        BEFORE UPDATE OR DELETE ON customer_assessment_heads
        FOR EACH ROW EXECUTE FUNCTION customer_assessment_heads_protect();
        """)

        # Trigger for findings protection & lifecycle
        op.execute("""
        CREATE OR REPLACE FUNCTION customer_assessment_findings_protect()
        RETURNS TRIGGER AS $$
        DECLARE
            v_ev_type text;
            v_ev_res text;
            v_ev_work uuid;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'customer_assessment_findings rows cannot be deleted';
            END IF;

            IF TG_OP = 'INSERT' THEN
                SELECT event_type, result, work_id INTO v_ev_type, v_ev_res, v_ev_work
                FROM customer_assessment_events
                WHERE tenant_id = NEW.tenant_id AND id = NEW.source_event_id;

                IF v_ev_type <> 'ASSESSMENT' OR v_ev_res NOT IN ('PARTIAL', 'FAIL') THEN
                    RAISE EXCEPTION 'Finding source_event must be an ASSESSMENT with PARTIAL or FAIL result';
                END IF;
                IF v_ev_work <> NEW.work_id THEN
                    RAISE EXCEPTION 'Finding source_event work_id mismatch';
                END IF;
                IF NEW.current_event_id <> NEW.source_event_id THEN
                    RAISE EXCEPTION 'Initial finding current_event_id must equal source_event_id';
                END IF;
                IF NEW.status <> 'OPEN' THEN
                    RAISE EXCEPTION 'Initial finding status must be OPEN';
                END IF;
                IF NEW.version <> 1 THEN
                    RAISE EXCEPTION 'Initial finding version must be 1';
                END IF;
                RETURN NEW;
            END IF;

            IF TG_OP = 'UPDATE' THEN
                IF NEW.tenant_id <> OLD.tenant_id OR NEW.id <> OLD.id OR NEW.work_id <> OLD.work_id OR NEW.source_event_id <> OLD.source_event_id OR NEW.created_at <> OLD.created_at THEN
                    RAISE EXCEPTION 'Finding identity and source columns are immutable';
                END IF;
                IF NEW.version <> OLD.version + 1 THEN
                    RAISE EXCEPTION 'Finding version must increment by exactly one';
                END IF;

                SELECT event_type, result, work_id INTO v_ev_type, v_ev_res, v_ev_work
                FROM customer_assessment_events
                WHERE tenant_id = NEW.tenant_id AND id = NEW.current_event_id;

                IF v_ev_work <> NEW.work_id THEN
                    RAISE EXCEPTION 'Finding current_event work_id mismatch';
                END IF;

                IF NEW.status = 'RESOLVED' THEN
                    IF v_ev_type <> 'RETEST' OR v_ev_res <> 'PASS' THEN
                        RAISE EXCEPTION 'Finding can only be RESOLVED by a RETEST event with PASS result';
                    END IF;
                END IF;

                RETURN NEW;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)

        op.execute("""
        CREATE TRIGGER trg_customer_assessment_findings_protect
        BEFORE INSERT OR UPDATE OR DELETE ON customer_assessment_findings
        FOR EACH ROW EXECUTE FUNCTION customer_assessment_findings_protect();
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
            REVOKE ALL ON public.customer_assessment_heads, public.customer_assessment_events, public.customer_assessment_findings FROM PUBLIC;

            -- Revoke all function privileges from PUBLIC
            REVOKE ALL ON FUNCTION public.customer_assessment_prevent_history_modification() FROM PUBLIC;
            REVOKE ALL ON FUNCTION public.customer_assessment_heads_protect() FROM PUBLIC;
            REVOKE ALL ON FUNCTION public.customer_assessment_findings_protect() FROM PUBLIC;

            IF has_catalog_role THEN
                REVOKE ALL PRIVILEGES ON public.customer_assessment_heads, public.customer_assessment_events, public.customer_assessment_findings FROM "conformly_catalog";
                REVOKE ALL ON FUNCTION public.customer_assessment_prevent_history_modification() FROM "conformly_catalog";
                REVOKE ALL ON FUNCTION public.customer_assessment_heads_protect() FROM "conformly_catalog";
                REVOKE ALL ON FUNCTION public.customer_assessment_findings_protect() FROM "conformly_catalog";
            END IF;

            IF has_fact_role THEN
                REVOKE ALL PRIVILEGES ON public.customer_assessment_heads, public.customer_assessment_events, public.customer_assessment_findings FROM "conformly_catalog_fact_author";
                REVOKE ALL ON FUNCTION public.customer_assessment_prevent_history_modification() FROM "conformly_catalog_fact_author";
                REVOKE ALL ON FUNCTION public.customer_assessment_heads_protect() FROM "conformly_catalog_fact_author";
                REVOKE ALL ON FUNCTION public.customer_assessment_findings_protect() FROM "conformly_catalog_fact_author";
            END IF;

            IF has_rule_role THEN
                REVOKE ALL PRIVILEGES ON public.customer_assessment_heads, public.customer_assessment_events, public.customer_assessment_findings FROM "conformly_catalog_rule_author";
                REVOKE ALL ON FUNCTION public.customer_assessment_prevent_history_modification() FROM "conformly_catalog_rule_author";
                REVOKE ALL ON FUNCTION public.customer_assessment_heads_protect() FROM "conformly_catalog_rule_author";
                REVOKE ALL ON FUNCTION public.customer_assessment_findings_protect() FROM "conformly_catalog_rule_author";
            END IF;

            IF has_app_role THEN
                REVOKE ALL PRIVILEGES ON public.customer_assessment_heads, public.customer_assessment_events, public.customer_assessment_findings FROM "conformly_app";

                GRANT SELECT, INSERT ON public.customer_assessment_heads TO "conformly_app";
                GRANT UPDATE (current_revision, updated_at) ON public.customer_assessment_heads TO "conformly_app";

                GRANT SELECT, INSERT ON public.customer_assessment_events TO "conformly_app";

                GRANT SELECT, INSERT ON public.customer_assessment_findings TO "conformly_app";
                GRANT UPDATE (current_event_id, severity, owner_user_id, due_date, status, version, updated_at) ON public.customer_assessment_findings TO "conformly_app";

                GRANT EXECUTE ON FUNCTION public.customer_assessment_prevent_history_modification() TO "conformly_app";
                GRANT EXECUTE ON FUNCTION public.customer_assessment_heads_protect() TO "conformly_app";
                GRANT EXECUTE ON FUNCTION public.customer_assessment_findings_protect() TO "conformly_app";

                EXECUTE $pol$CREATE POLICY wp09c_customer_assessment_heads ON customer_assessment_heads TO conformly_app USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true') WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true')$pol$;

                EXECUTE $pol$CREATE POLICY wp09c_customer_assessment_events ON customer_assessment_events TO conformly_app USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true') WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true')$pol$;

                EXECUTE $pol$CREATE POLICY wp09c_customer_assessment_findings ON customer_assessment_findings TO conformly_app USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true') WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true')$pol$;
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
            cnt_heads integer := 0;
            cnt_events integer := 0;
            cnt_findings integer := 0;
        BEGIN
            SELECT count(*) INTO cnt_heads FROM customer_assessment_heads;
            SELECT count(*) INTO cnt_events FROM customer_assessment_events;
            SELECT count(*) INTO cnt_findings FROM customer_assessment_findings;

            IF (cnt_heads + cnt_events + cnt_findings) > 0 THEN
                RAISE EXCEPTION 'CANNOT_DOWNGRADE_CUSTOMER_ASSESSMENT_DATA_EXISTS';
            END IF;
        END $$;
        """)
    else:
        conn = op.get_bind()
        total_rows = 0
        for tbl in [
            "customer_assessment_heads",
            "customer_assessment_events",
            "customer_assessment_findings",
        ]:
            res = conn.execute(sa.text(f"SELECT count(*) FROM {tbl}")).scalar() or 0
            total_rows += res
        if total_rows > 0:
            raise RuntimeError("CANNOT_DOWNGRADE_CUSTOMER_ASSESSMENT_DATA_EXISTS")

    if is_pg:
        op.execute(
            "DROP TRIGGER IF EXISTS trg_customer_assessment_findings_protect ON customer_assessment_findings"
        )
        op.execute("DROP FUNCTION IF EXISTS customer_assessment_findings_protect")
        op.execute(
            "DROP TRIGGER IF EXISTS trg_customer_assessment_heads_protect ON customer_assessment_heads"
        )
        op.execute("DROP FUNCTION IF EXISTS customer_assessment_heads_protect")
        op.execute(
            "DROP TRIGGER IF EXISTS trg_customer_assessment_events_immutable ON customer_assessment_events"
        )
        op.execute("DROP FUNCTION IF EXISTS customer_assessment_prevent_history_modification")

    op.drop_table("customer_assessment_findings")
    op.drop_table("customer_assessment_events")
    op.drop_table("customer_assessment_heads")
