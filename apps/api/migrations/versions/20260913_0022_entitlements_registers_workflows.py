"""Add framework-packs to entitlements, and workflows/scopes to registers.

Revision ID: 20260913_0022
Revises: 20260913_0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0022"
down_revision: str | None = "20260913_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Tenant Entitlements: Framework packs
    with op.batch_alter_table("tenant_entitlements") as batch_op:
        batch_op.add_column(
            sa.Column(
                "allowed_framework_slugs",
                sa.JSON(),
                server_default='["*"]',
                nullable=False,
            )
        )

    # 2. Risks: Scopes, reviews, finding links
    with op.batch_alter_table("risks") as batch_op:
        batch_op.add_column(sa.Column("finding_id", sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "legal_entity_id",
                sa.Uuid(),
                sa.ForeignKey("legal_entities.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "business_unit_id",
                sa.Uuid(),
                sa.ForeignKey("business_units.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("next_review_due_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_risks_legal_entity", ["tenant_id", "legal_entity_id"])
        batch_op.create_index("ix_risks_business_unit", ["tenant_id", "business_unit_id"])

    # 3. Risk Treatments: Owner assignment
    with op.batch_alter_table("risk_treatments") as batch_op:
        batch_op.add_column(
            sa.Column(
                "owner_user_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            )
        )

    # 4. Assets: Scopes, reviews, links, encrypted description
    with op.batch_alter_table("assets") as batch_op:
        batch_op.add_column(sa.Column("encrypted_description", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("control_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("finding_id", sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "legal_entity_id",
                sa.Uuid(),
                sa.ForeignKey("legal_entities.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "business_unit_id",
                sa.Uuid(),
                sa.ForeignKey("business_units.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("next_review_due_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_assets_legal_entity", ["tenant_id", "legal_entity_id"])
        batch_op.create_index("ix_assets_business_unit", ["tenant_id", "business_unit_id"])

    # 5. Vendors: Scopes, reviews, owner, links
    with op.batch_alter_table("vendors") as batch_op:
        batch_op.add_column(
            sa.Column(
                "owner_user_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("control_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("finding_id", sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "legal_entity_id",
                sa.Uuid(),
                sa.ForeignKey("legal_entities.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "business_unit_id",
                sa.Uuid(),
                sa.ForeignKey("business_units.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.create_index("ix_vendors_legal_entity", ["tenant_id", "legal_entity_id"])
        batch_op.create_index("ix_vendors_business_unit", ["tenant_id", "business_unit_id"])


def downgrade() -> None:
    with op.batch_alter_table("vendors") as batch_op:
        batch_op.drop_index("ix_vendors_business_unit")
        batch_op.drop_index("ix_vendors_legal_entity")
        batch_op.drop_column("business_unit_id")
        batch_op.drop_column("legal_entity_id")
        batch_op.drop_column("finding_id")
        batch_op.drop_column("control_id")
        batch_op.drop_column("owner_user_id")

    with op.batch_alter_table("assets") as batch_op:
        batch_op.drop_index("ix_assets_business_unit")
        batch_op.drop_index("ix_assets_legal_entity")
        batch_op.drop_column("next_review_due_at")
        batch_op.drop_column("last_reviewed_at")
        batch_op.drop_column("business_unit_id")
        batch_op.drop_column("legal_entity_id")
        batch_op.drop_column("finding_id")
        batch_op.drop_column("control_id")
        batch_op.drop_column("encrypted_description")

    with op.batch_alter_table("risk_treatments") as batch_op:
        batch_op.drop_column("owner_user_id")

    with op.batch_alter_table("risks") as batch_op:
        batch_op.drop_index("ix_risks_business_unit")
        batch_op.drop_index("ix_risks_legal_entity")
        batch_op.drop_column("next_review_due_at")
        batch_op.drop_column("last_reviewed_at")
        batch_op.drop_column("business_unit_id")
        batch_op.drop_column("legal_entity_id")
        batch_op.drop_column("finding_id")

    with op.batch_alter_table("tenant_entitlements") as batch_op:
        batch_op.drop_column("allowed_framework_slugs")
