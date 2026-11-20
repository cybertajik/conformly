"""V2 customer readiness verification lifecycle tables, constraints, RLS and triggers

Revision ID: 20261102_0049
Revises: 20261101_0048
Create Date: 2026-11-02 18:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20261102_0049"
down_revision: str | Sequence[str] | None = "20261101_0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"

    def digest_ck(col: str) -> str:
        if is_pg:
            return f"length({col}) = 64 AND {col} ~ '^[0-9a-f]{{64}}$'"
        return f"length({col}) = 64 AND NOT ({col} GLOB '*[^0-9a-f]*')"

    # 1. customer_readiness_verifications
    op.create_table(
        "customer_readiness_verifications",
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
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "revision",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "valid_through",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "payload_encrypted",
            sa.JSON().with_variant(postgresql.JSONB, "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "digest",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "current_event_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "superseded_by_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "supersedes_id",
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
        sa.CheckConstraint("revision >= 1", name="ck_customer_verifications_rev_pos"),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'REVOKED', 'EXPIRED', 'SUPERSEDED')",
            name="ck_customer_verifications_status",
        ),
        sa.CheckConstraint("issued_at <= valid_through", name="ck_customer_verifications_validity_order"),
        sa.CheckConstraint(digest_ck("digest"), name="ck_customer_verifications_digest"),
        sa.UniqueConstraint("tenant_id", "snapshot_id", name="uq_customer_verifications_snapshot"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "preaudit_id"],
            ["customer_preaudits.tenant_id", "customer_preaudits.id"],
            ondelete="RESTRICT",
            name="fk_customer_verifications_preaudit",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "preaudit_id", "snapshot_id"],
            [
                "customer_preaudit_snapshots.tenant_id",
                "customer_preaudit_snapshots.preaudit_id",
                "customer_preaudit_snapshots.id",
            ],
            ondelete="RESTRICT",
            name="fk_customer_verifications_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "superseded_by_id"],
            ["customer_readiness_verifications.tenant_id", "customer_readiness_verifications.id"],
            ondelete="RESTRICT",
            name="fk_customer_verifications_superseded_by",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "supersedes_id"],
            ["customer_readiness_verifications.tenant_id", "customer_readiness_verifications.id"],
            ondelete="RESTRICT",
            name="fk_customer_verifications_supersedes",
        ),
    )

    op.create_index(
        "ix_customer_verifications_tenant_status",
        "customer_readiness_verifications",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_customer_verifications_tenant_preaudit",
        "customer_readiness_verifications",
        ["tenant_id", "preaudit_id"],
    )

    # 2. customer_readiness_verification_events
    op.create_table(
        "customer_readiness_verification_events",
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
            "verification_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "sequence",
            sa.Integer(),
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
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
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
        sa.CheckConstraint("sequence >= 1", name="ck_customer_verification_events_seq_pos"),
        sa.CheckConstraint("revision >= 1", name="ck_customer_verification_events_rev_pos"),
        sa.CheckConstraint(
            "event_type IN ('ISSUED', 'SUSPENDED', 'REVOKED', 'EXPIRED', 'CORRECTED', 'SUPERSEDED', 'RECONCILED')",
            name="ck_customer_verification_events_type",
        ),
        sa.CheckConstraint(
            "new_status IN ('ACTIVE', 'SUSPENDED', 'REVOKED', 'EXPIRED', 'SUPERSEDED')",
            name="ck_customer_verification_events_new_status",
        ),
        sa.CheckConstraint(digest_ck("request_digest"), name="ck_customer_verification_events_req_digest"),
        sa.UniqueConstraint("tenant_id", "operation_id", name="uq_customer_verification_events_op"),
        sa.UniqueConstraint("tenant_id", "verification_id", "sequence", name="uq_customer_verification_events_seq"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "verification_id"],
            ["customer_readiness_verifications.tenant_id", "customer_readiness_verifications.id"],
            ondelete="RESTRICT",
            name="fk_customer_verification_events_verification",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "actor_user_id"],
            ["memberships.tenant_id", "memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_customer_verification_events_actor",
        ),
    )

    op.create_index(
        "ix_customer_verification_events_tenant_ver",
        "customer_readiness_verification_events",
        ["tenant_id", "verification_id", "occurred_at"],
    )

    # 3. PostgreSQL RLS, triggers, functions, and role grants
    if is_pg:
        op.execute("""
        DO $$
        BEGIN
            ALTER TABLE customer_readiness_verifications ENABLE ROW LEVEL SECURITY;
            ALTER TABLE customer_readiness_verifications FORCE ROW LEVEL SECURITY;

            ALTER TABLE customer_readiness_verification_events ENABLE ROW LEVEL SECURITY;
            ALTER TABLE customer_readiness_verification_events FORCE ROW LEVEL SECURITY;

            -- Trigger function: protect immutable columns on customer_readiness_verifications
            CREATE OR REPLACE FUNCTION public.customer_verifications_protect()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $func$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'CANNOT_DELETE_READINESS_VERIFICATION';
                END IF;

                IF TG_OP = 'UPDATE' THEN
                    IF OLD.tenant_id <> NEW.tenant_id
                       OR OLD.id <> NEW.id
                       OR OLD.preaudit_id <> NEW.preaudit_id
                       OR OLD.snapshot_id <> NEW.snapshot_id
                       OR OLD.issued_at <> NEW.issued_at
                       OR OLD.valid_through <> NEW.valid_through
                       OR OLD.payload_encrypted <> NEW.payload_encrypted
                       OR OLD.digest <> NEW.digest
                       OR OLD.created_at <> NEW.created_at
                       OR OLD.supersedes_id IS NOT DISTINCT FROM NEW.supersedes_id AND OLD.supersedes_id <> NEW.supersedes_id
                    THEN
                        RAISE EXCEPTION 'CANNOT_MUTATE_FROZEN_VERIFICATION_COLUMNS';
                    END IF;

                    IF NEW.revision <= OLD.revision THEN
                        RAISE EXCEPTION 'REVISION_MUST_BE_MONOTONICALLY_INCREASING';
                    END IF;

                    NEW.updated_at := clock_timestamp();
                END IF;

                RETURN NEW;
            END;
            $func$;

            DROP TRIGGER IF EXISTS trg_customer_verifications_protect ON customer_readiness_verifications;
            CREATE TRIGGER trg_customer_verifications_protect
                BEFORE UPDATE OR DELETE ON customer_readiness_verifications
                FOR EACH ROW
                EXECUTE FUNCTION public.customer_verifications_protect();

            -- Trigger function: append-only events immutability
            CREATE OR REPLACE FUNCTION public.customer_verification_events_immutable()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $func$
            BEGIN
                IF TG_OP IN ('UPDATE', 'DELETE') THEN
                    RAISE EXCEPTION 'CANNOT_MUTATE_APPEND_ONLY_VERIFICATION_EVENTS';
                END IF;
                RETURN NEW;
            END;
            $func$;

            DROP TRIGGER IF EXISTS trg_customer_verification_events_immutable ON customer_readiness_verification_events;
            CREATE TRIGGER trg_customer_verification_events_immutable
                BEFORE UPDATE OR DELETE ON customer_readiness_verification_events
                FOR EACH ROW
                EXECUTE FUNCTION public.customer_verification_events_immutable();

            -- Grants and RLS policies for conformly_app
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_app') THEN
                REVOKE ALL ON customer_readiness_verifications FROM "conformly_app";
                REVOKE ALL ON customer_readiness_verification_events FROM "conformly_app";

                GRANT SELECT, INSERT ON customer_readiness_verifications TO "conformly_app";
                GRANT UPDATE (status, revision, current_event_id, superseded_by_id, updated_at)
                    ON customer_readiness_verifications TO "conformly_app";

                GRANT SELECT, INSERT ON customer_readiness_verification_events TO "conformly_app";

                GRANT EXECUTE ON FUNCTION public.customer_verifications_protect() TO "conformly_app";
                GRANT EXECUTE ON FUNCTION public.customer_verification_events_immutable() TO "conformly_app";

                EXECUTE $pol$CREATE POLICY wp09e_customer_verifications ON customer_readiness_verifications TO conformly_app USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true') WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true')$pol$;

                EXECUTE $pol$CREATE POLICY wp09e_customer_verification_events ON customer_readiness_verification_events TO conformly_app USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true') WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid AND current_setting('app.tenant_verified', true) = 'true')$pol$;
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
            cnt_ver integer := 0;
            cnt_events integer := 0;
        BEGIN
            SELECT count(*) INTO cnt_ver FROM customer_readiness_verifications;
            SELECT count(*) INTO cnt_events FROM customer_readiness_verification_events;

            IF (cnt_ver + cnt_events) > 0 THEN
                RAISE EXCEPTION 'CANNOT_DOWNGRADE_CUSTOMER_VERIFICATION_DATA_EXISTS';
            END IF;
        END $$;
        """)
    else:
        conn = op.get_bind()
        total_rows = 0
        for tbl in [
            "customer_readiness_verifications",
            "customer_readiness_verification_events",
        ]:
            res = conn.execute(sa.text(f"SELECT count(*) FROM {tbl}")).scalar() or 0
            total_rows += res
        if total_rows > 0:
            raise RuntimeError("CANNOT_DOWNGRADE_CUSTOMER_VERIFICATION_DATA_EXISTS")

    if is_pg:
        op.drop_constraint("fk_customer_verifications_supersedes", "customer_readiness_verifications", type_="foreignkey")
        op.drop_constraint("fk_customer_verifications_superseded_by", "customer_readiness_verifications", type_="foreignkey")
        op.execute("DROP TRIGGER IF EXISTS trg_customer_verifications_protect ON customer_readiness_verifications")
        op.execute("DROP FUNCTION IF EXISTS customer_verifications_protect")
        op.execute("DROP TRIGGER IF EXISTS trg_customer_verification_events_immutable ON customer_readiness_verification_events")
        op.execute("DROP FUNCTION IF EXISTS customer_verification_events_immutable")

    op.drop_table("customer_readiness_verification_events")
    op.drop_table("customer_readiness_verifications")
