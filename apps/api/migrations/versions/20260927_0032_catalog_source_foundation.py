"""Add dormant V2 source identities without enabling runtime access."""

import sqlalchemy as sa
from alembic import op

revision = "20260927_0032"
down_revision = "20260913_0031"
branch_labels = None
depends_on = None

TABLES = ("catalog_publishers", "catalog_sources", "catalog_source_versions")


def _identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("status", sa.String(16), server_default="Draft", nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "catalog_publishers",
        *_identity_columns(),
        sa.Column("publisher_key", sa.String(128), nullable=False),
        sa.Column("name", sa.String(1024), nullable=False),
        sa.UniqueConstraint("publisher_key"),
        sa.CheckConstraint("length(publisher_key) BETWEEN 1 AND 128", name="publisher_key_length"),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 1024", name="name_length"),
        sa.CheckConstraint("status = 'Draft'", name="draft_only"),
    )
    op.create_table(
        "catalog_sources",
        *_identity_columns(),
        sa.Column("publisher_id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.String(128), nullable=False),
        sa.Column("title", sa.String(1024), nullable=False),
        sa.ForeignKeyConstraint(["publisher_id"], ["catalog_publishers.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("publisher_id", "source_key"),
        sa.CheckConstraint("length(source_key) BETWEEN 1 AND 128", name="source_key_length"),
        sa.CheckConstraint("length(title) BETWEEN 1 AND 1024", name="title_length"),
        sa.CheckConstraint("status = 'Draft'", name="draft_only"),
    )
    op.create_table(
        "catalog_source_versions",
        *_identity_columns(),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("edition", sa.String(128), nullable=False),
        sa.Column("predecessor_id", sa.Uuid(), nullable=True),
        sa.Column("language", sa.String(35), nullable=True),
        sa.Column("official_locator", sa.String(4096), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["catalog_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["predecessor_id", "source_id"],
            ["catalog_source_versions.id", "catalog_source_versions.source_id"],
            name="fk_catalog_source_versions_predecessor_lineage",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("source_id", "edition"),
        sa.UniqueConstraint("id", "source_id", name="uq_catalog_source_versions_id_source"),
        sa.CheckConstraint(
            "predecessor_id IS NULL OR predecessor_id <> id", name="not_self_predecessor"
        ),
        sa.CheckConstraint("length(edition) BETWEEN 1 AND 128", name="edition_length"),
        sa.CheckConstraint(
            "language IS NULL OR length(language) BETWEEN 1 AND 35", name="language_length"
        ),
        sa.CheckConstraint(
            "official_locator IS NULL OR length(official_locator) BETWEEN 1 AND 4096",
            name="official_locator_length",
        ),
        sa.CheckConstraint("revision >= 1", name="positive_revision"),
        sa.CheckConstraint("status = 'Draft'", name="draft_only"),
    )
    # These are literal migration-owned identifiers, never user input. No policies
    # means deny-all, even if an unexpected default ACL granted a non-owner DML.
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
    # Run as a reviewed migration identity. No CASCADE and no silent data loss.
    # Lock all three before checking; concurrent inserts cannot race the check.
    op.execute("SET LOCAL row_security = off")
    op.execute(
        "LOCK TABLE public.catalog_publishers, public.catalog_sources, "
        "public.catalog_source_versions IN ACCESS EXCLUSIVE MODE"
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM public.catalog_publishers) "
        "OR EXISTS (SELECT 1 FROM public.catalog_sources) "
        "OR EXISTS (SELECT 1 FROM public.catalog_source_versions) THEN "
        "RAISE EXCEPTION 'V2 source foundation is populated; forward recovery required'; "
        "END IF; END $$"
    )
    for table in reversed(TABLES):
        op.drop_table(table)
