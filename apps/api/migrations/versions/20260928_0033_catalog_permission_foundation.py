"""Add inaccessible, append-only provenance and Draft permission proposals."""

import sqlalchemy as sa
from alembic import op

revision = "20260928_0033"
down_revision = "20260927_0032"
branch_labels = None
depends_on = None

TABLES = ("catalog_source_provenance", "catalog_source_permission_proposals")


def upgrade() -> None:
    op.create_table(
        "catalog_source_provenance",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.LargeBinary(), nullable=False),
        sa.Column("content_size", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(255), nullable=False),
        sa.Column("locator", sa.String(4096), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by_actor_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"], ["catalog_source_versions.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("source_version_id"),
        sa.UniqueConstraint("id", "source_version_id", name="uq_catalog_provenance_id_version"),
        sa.CheckConstraint("source_revision >= 1", name="positive_source_revision"),
        sa.CheckConstraint("length(content_sha256) = 32", name="sha256_bytes"),
        sa.CheckConstraint("content_size >= 0", name="nonnegative_size"),
        sa.CheckConstraint("length(mime_type) BETWEEN 1 AND 255", name="mime_type_length"),
        sa.CheckConstraint("length(locator) BETWEEN 1 AND 4096", name="locator_length"),
    )
    op.create_table(
        "catalog_source_permission_proposals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column("provenance_id", sa.Uuid(), nullable=False),
        sa.Column("use_case", sa.String(32), nullable=False),
        sa.Column("scope_key", sa.String(128), nullable=False),
        sa.Column("sequence", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("supersedes_sequence", sa.Integer(), nullable=True),
        sa.Column("proposed_outcome", sa.String(16), server_default="Unknown", nullable=False),
        sa.Column("review_state", sa.String(16), server_default="Draft", nullable=False),
        sa.Column("conditions_state", sa.String(32), server_default="Unknown", nullable=False),
        sa.Column("conditions_reference", sa.Uuid(), nullable=True),
        sa.Column("evidence_reference", sa.Uuid(), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_by_actor_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["provenance_id", "source_version_id"],
            ["catalog_source_provenance.id", "catalog_source_provenance.source_version_id"],
            name="fk_catalog_permission_provenance_lineage",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "source_version_id",
            "use_case",
            "scope_key",
            "sequence",
            name="uq_catalog_permission_scope_sequence",
        ),
        sa.UniqueConstraint(
            "id",
            "source_version_id",
            "use_case",
            "scope_key",
            "sequence",
            name="uq_catalog_permission_predecessor_identity",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id", "source_version_id", "use_case", "scope_key", "supersedes_sequence"],
            [
                "catalog_source_permission_proposals.id",
                "catalog_source_permission_proposals.source_version_id",
                "catalog_source_permission_proposals.use_case",
                "catalog_source_permission_proposals.scope_key",
                "catalog_source_permission_proposals.sequence",
            ],
            name="fk_catalog_permission_predecessor_context",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "use_case IN ('reference','store','excerpt','paraphrase','translate','map','ui','api','export','search','ai')",
            name="known_use_case",
        ),
        sa.CheckConstraint("length(scope_key) BETWEEN 1 AND 128", name="scope_key_length"),
        sa.CheckConstraint(
            "proposed_outcome IN ('Unknown','Denied','Allowed')", name="known_outcome"
        ),
        sa.CheckConstraint("review_state = 'Draft'", name="draft_only"),
        sa.CheckConstraint(
            "(conditions_state IN ('Unknown','None') AND conditions_reference IS NULL) OR "
            "(conditions_state = 'ExternalReference' AND conditions_reference IS NOT NULL)",
            name="conditions_shape",
        ),
        sa.CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_until > valid_from",
            name="valid_time_order",
        ),
        sa.CheckConstraint(
            "(sequence = 1 AND supersedes_id IS NULL AND supersedes_sequence IS NULL) OR "
            "(sequence > 1 AND supersedes_id IS NOT NULL AND supersedes_sequence IS NOT NULL "
            "AND supersedes_sequence >= 1 AND sequence = supersedes_sequence + 1)",
            name="successor_sequence",
        ),
    )
    op.execute("""
        CREATE FUNCTION public.catalog_source_history_append_only()
        RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$ BEGIN RAISE EXCEPTION 'catalog source history is append-only'; END; $$
    """)
    op.execute("REVOKE ALL ON FUNCTION public.catalog_source_history_append_only() FROM PUBLIC")
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
            f'CREATE TRIGGER "{table}_immutable" BEFORE UPDATE OR DELETE ON public."{table}" '
            "FOR EACH ROW EXECUTE FUNCTION public.catalog_source_history_append_only()"
        )
        op.execute(
            f'CREATE TRIGGER "{table}_no_truncate" BEFORE TRUNCATE ON public."{table}" '
            "FOR EACH STATEMENT EXECUTE FUNCTION public.catalog_source_history_append_only()"
        )


def downgrade() -> None:
    op.execute("SET LOCAL row_security = off")
    op.execute(
        "LOCK TABLE public.catalog_source_provenance, public.catalog_source_permission_proposals "
        "IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN IF EXISTS (SELECT 1 FROM public.catalog_source_provenance)
        OR EXISTS (SELECT 1 FROM public.catalog_source_permission_proposals) THEN
        RAISE EXCEPTION 'V2 permission history is populated; forward recovery required';
        END IF; END $$
    """)
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute("DROP FUNCTION public.catalog_source_history_append_only()")
