"""V2 customer pre-audit workflow tables, constraints, RLS and triggers

Revision ID: 20261101_0048
Revises: 20261025_0047
Create Date: 2026-11-01 17:30:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20261101_0048"
down_revision: str | Sequence[str] | None = "20261025_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"

    def digest_ck(col: str) -> str:
        if is_pg:
            return f"length({col}) = 64 AND {col} ~ '^[0-9a-f]{{64}}$'"
        return f"length({col}) = 64 AND NOT ({col} GLOB '*[^0-9a-f]*')"

    # 1. customer_preaudits (initial table creation without circular snapshot FKs)
    op.create_table(
        "customer_preaudits",
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
            "adoption_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "lead_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "reviewer_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column(
            "revision",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "current_scope_snapshot_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "current_review_snapshot_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
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
            "revision >= 1",
            name="ck_customer_preaudits_rev_pos",
        ),
        sa.CheckConstraint(
            "lead_user_id <> reviewer_user_id",
            name="ck_customer_preaudits_lead_reviewer_diff",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'FROZEN', 'IN_REVIEW', 'CHANGES_REQUESTED', 'REVIEWED', 'APPROVED', 'CANCELLED')",
            name="ck_customer_preaudits_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "adoption_id"],
            ["customer_demo_adoptions.tenant_id", "customer_demo_adoptions.id"],
            ondelete="RESTRICT",
            name="fk_customer_preaudits_adoption",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "lead_user_id"],
            ["memberships.tenant_id", "memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_customer_preaudits_lead",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "reviewer_user_id"],
            ["memberships.tenant_id", "memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_customer_preaudits_reviewer",
        ),
    )
    op.create_index(
        "ix_customer_preaudits_tenant_status",
        "customer_preaudits",
        ["tenant_id", "status"],
    )

    # 2. customer_preaudit_snapshots
    op.create_table(
        "customer_preaudit_snapshots",
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
            "preaudit_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "kind",
            sa.String(16),
            nullable=False,
        ),
        sa.Column(
            "sequence",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "digest",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "payload_encrypted",
            sa.JSON().with_variant(postgresql.JSONB, "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "kind IN ('SCOPE', 'REVIEW')",
            name="ck_customer_preaudit_snapshots_kind",
        ),
        sa.CheckConstraint(
            "sequence > 0",
            name="ck_customer_preaudit_snapshots_seq_pos",
        ),
        sa.CheckConstraint(
            digest_ck("digest"),
            name="ck_customer_preaudit_snapshots_digest_format",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "preaudit_id",
            "kind",
            "sequence",
            name="uq_customer_preaudit_snapshots_kind_seq",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "preaudit_id",
            "id",
            name="uq_customer_preaudit_snapshots_tenant_preaudit_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "preaudit_id"],
            ["customer_preaudits.tenant_id", "customer_preaudits.id"],
            ondelete="RESTRICT",
            name="fk_customer_preaudit_snapshots_preaudit",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["memberships.tenant_id", "memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_customer_preaudit_snapshots_created_by",
        ),
    )
    op.create_index(
        "ix_customer_preaudit_snapshots_preaudit_kind",
        "customer_preaudit_snapshots",
        ["tenant_id", "preaudit_id", "kind"],
    )

    # 3. Add composite head pointer foreign keys to customer_preaudits
    if is_pg:
        op.create_foreign_key(
            "fk_customer_preaudits_scope_snapshot",
            "customer_preaudits",
            "customer_preaudit_snapshots",
            ["tenant_id", "id", "current_scope_snapshot_id"],
            ["tenant_id", "preaudit_id", "id"],
            ondelete="RESTRICT",
        )
        op.create_foreign_key(
            "fk_customer_preaudits_review_snapshot",
            "customer_preaudits",
            "customer_preaudit_snapshots",
            ["tenant_id", "id", "current_review_snapshot_id"],
            ["tenant_id", "preaudit_id", "id"],
            ondelete="RESTRICT",
        )

    # 4. customer_preaudit_events
    op.create_table(
        "customer_preaudit_events",
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
            "preaudit_id",
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
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "prior_status",
            sa.String(32),
            nullable=True,
        ),
        sa.Column(
            "new_status",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "payload_encrypted",
            sa.JSON().with_variant(postgresql.JSONB, "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "revision > 0",
            name="ck_customer_preaudit_events_rev_pos",
        ),
        sa.CheckConstraint(
            digest_ck("request_digest"),
            name="ck_customer_preaudit_events_req_digest",
        ),
        sa.CheckConstraint(
            "event_type IN ('CREATED', 'SCOPE_FROZEN', 'SUBMITTED', 'CHANGES_REQUESTED', 'REVIEWED', 'APPROVED', 'CANCELLED')",
            name="ck_customer_preaudit_events_type",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "operation_id",
            name="uq_customer_preaudit_events_op",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "preaudit_id",
            "revision",
            name="uq_customer_preaudit_events_rev",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "preaudit_id"],
            ["customer_preaudits.tenant_id", "customer_preaudits.id"],
            ondelete="RESTRICT",
            name="fk_customer_preaudit_events_preaudit",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "actor_user_id"],
            ["memberships.tenant_id", "memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_customer_preaudit_events_actor",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "preaudit_id", "snapshot_id"],
            [
                "customer_preaudit_snapshots.tenant_id",
                "customer_preaudit_snapshots.preaudit_id",
                "customer_preaudit_snapshots.id",
            ],
            ondelete="RESTRICT",
            name="fk_customer_preaudit_events_snapshot",
        ),
    )
    op.create_index(
        "ix_customer_preaudit_events_preaudit_rev",
        "customer_preaudit_events",
        ["tenant_id", "preaudit_id", "revision"],
    )

    if is_pg:
        # Enable and force RLS on all 3 tables
        for tbl in [
            "customer_preaudits",
            "customer_preaudit_snapshots",
            "customer_preaudit_events",
        ]:
            op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")

        # Immutability trigger for snapshots and events
        op.execute("""
        CREATE OR REPLACE FUNCTION customer_preaudit_prevent_history_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION '% rows are immutable and cannot be updated or deleted', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """)

        op.execute("""
        CREATE TRIGGER trg_customer_preaudit_snapshots_immutable
        BEFORE UPDATE OR DELETE ON customer_preaudit_snapshots
        FOR EACH ROW EXECUTE FUNCTION customer_preaudit_prevent_history_modification();
        """)

        op.execute("""
        CREATE TRIGGER trg_customer_preaudit_events_immutable
        BEFORE UPDATE OR DELETE ON customer_preaudit_events
        FOR EACH ROW EXECUTE FUNCTION customer_preaudit_prevent_history_modification();
        """)

        # Protection trigger for customer_preaudits head
        op.execute("""
        CREATE OR REPLACE FUNCTION customer_preaudits_protect()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'customer_preaudits rows cannot be deleted';
            END IF;
            IF NEW.tenant_id <> OLD.tenant_id OR NEW.id <> OLD.id OR NEW.adoption_id <> OLD.adoption_id OR NEW.created_at <> OLD.created_at THEN
                RAISE EXCEPTION 'customer_preaudits identity columns are immutable';
            END IF;
            IF NEW.revision <> OLD.revision + 1 THEN
                RAISE EXCEPTION 'customer_preaudits revision must increment by exactly one';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)

        op.execute("""
        CREATE TRIGGER trg_customer_preaudits_protect
        BEFORE UPDATE OR DELETE ON customer_preaudits
        FOR EACH ROW EXECUTE FUNCTION customer_preaudits_protect();
        """)

        # Grants and RLS policies
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
            REVOKE ALL ON public.customer_preaudits, public.customer_preaudit_snapshots, public.customer_preaudit_events FROM PUBLIC;

            -- Revoke all function privileges from PUBLIC
            REVOKE ALL ON FUNCTION public.customer_preaudit_prevent_history_modification() FROM PUBLIC;
            REVOKE ALL ON FUNCTION public.customer_preaudits_protect() FROM PUBLIC;

            IF has_catalog_role THEN
                REVOKE ALL PRIVILEGES ON public.customer_preaudits, public.customer_preaudit_snapshots, public.customer_preaudit_events FROM "conformly_catalog";
                REVOKE ALL ON FUNCTION public.customer_preaudit_prevent_history_modification() FROM "conformly_catalog";
                REVOKE ALL ON FUNCTION public.customer_preaudits_protect() FROM "conformly_catalog";
            END IF;

            IF has_fact_role THEN
                REVOKE ALL PRIVILEGES ON public.customer_preaudits, public.customer_preaudit_snapshots, public.customer_preaudit_events FROM "conformly_catalog_fact_author";
                REVOKE ALL ON FUNCTION public.customer_preaudit_prevent_history_modification() FROM "conformly_catalog_fact_author";
                REVOKE ALL ON FUNCTION public.customer_preaudits_protect() FROM "conformly_catalog_fact_author";
            END IF;

            IF has_rule_role THEN
                REVOKE ALL PRIVILEGES ON public.customer_preaudits, public.customer_preaudit_snapshots, public.customer_preaudit_events FROM "conformly_catalog_rule_author";
                REVOKE ALL ON FUNCTION public.customer_preaudit_prevent_history_modification() FROM "conformly_catalog_rule_author";
                REVOKE ALL ON FUNCTION public.customer_preaudits_protect() FROM "conformly_catalog_rule_author";
            END IF;

            IF has_app_role THEN
                REVOKE ALL PRIVILEGES ON public.customer_preaudits, public.customer_preaudit_snapshots, public.customer_preaudit_events FROM "conformly_app";

                GRANT SELECT, INSERT ON public.customer_preaudits TO "conformly_app";
                GRANT UPDATE (status, revision, current_scope_snapshot_id, current_review_snapshot_id, updated_at) ON public.customer_preaudits TO "conformly_app";

                GRANT SELECT, INSERT ON public.customer_preaudit_snapshots TO "conformly_app";
                GRANT SELECT, INSERT ON public.customer_preaudit_events TO "conformly_app";

                GRANT EXECUTE ON FUNCTION public.customer_preaudit_prevent_history_modification() TO "conformly_app";
                GRANT EXECUTE ON FUNCTION public.customer_preaudits_protect() TO "conformly_app";

                EXECUTE $pol$CREATE POLICY wp09d_customer_preaudits ON customer_preaudits TO conformly_app USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true') WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true')$pol$;

                EXECUTE $pol$CREATE POLICY wp09d_customer_preaudit_snapshots ON customer_preaudit_snapshots TO conformly_app USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true') WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true')$pol$;

                EXECUTE $pol$CREATE POLICY wp09d_customer_preaudit_events ON customer_preaudit_events TO conformly_app USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true') WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true')$pol$;
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
            cnt_cases integer := 0;
            cnt_snaps integer := 0;
            cnt_events integer := 0;
        BEGIN
            SELECT count(*) INTO cnt_cases FROM customer_preaudits;
            SELECT count(*) INTO cnt_snaps FROM customer_preaudit_snapshots;
            SELECT count(*) INTO cnt_events FROM customer_preaudit_events;

            IF (cnt_cases + cnt_snaps + cnt_events) > 0 THEN
                RAISE EXCEPTION 'CANNOT_DOWNGRADE_CUSTOMER_PREAUDIT_DATA_EXISTS';
            END IF;
        END $$;
        """)
    else:
        conn = op.get_bind()
        total_rows = 0
        for tbl in [
            "customer_preaudits",
            "customer_preaudit_snapshots",
            "customer_preaudit_events",
        ]:
            res = conn.execute(sa.text(f"SELECT count(*) FROM {tbl}")).scalar() or 0
            total_rows += res
        if total_rows > 0:
            raise RuntimeError("CANNOT_DOWNGRADE_CUSTOMER_PREAUDIT_DATA_EXISTS")

    if is_pg:
        op.drop_constraint("fk_customer_preaudits_review_snapshot", "customer_preaudits", type_="foreignkey")
        op.drop_constraint("fk_customer_preaudits_scope_snapshot", "customer_preaudits", type_="foreignkey")
        op.execute("DROP TRIGGER IF EXISTS trg_customer_preaudits_protect ON customer_preaudits")
        op.execute("DROP FUNCTION IF EXISTS customer_preaudits_protect")
        op.execute("DROP TRIGGER IF EXISTS trg_customer_preaudit_events_immutable ON customer_preaudit_events")
        op.execute("DROP TRIGGER IF EXISTS trg_customer_preaudit_snapshots_immutable ON customer_preaudit_snapshots")
        op.execute("DROP FUNCTION IF EXISTS customer_preaudit_prevent_history_modification")

    op.drop_table("customer_preaudit_events")
    op.drop_table("customer_preaudit_snapshots")
    op.drop_table("customer_preaudits")

