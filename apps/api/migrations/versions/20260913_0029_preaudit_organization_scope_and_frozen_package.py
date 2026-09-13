"""Organization-scoped pre-audits and frozen issuance package on certificates."""

import sqlalchemy as sa
from alembic import op

revision = "20260913_0029"
down_revision = "20260913_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("pre_audits") as batch_op:
        batch_op.add_column(
            sa.Column(
                "legal_entity_id",
                sa.Uuid(),
                sa.ForeignKey("legal_entities.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_pre_audits_tenant_legal_entity",
            ["tenant_id", "legal_entity_id"],
        )

    with op.batch_alter_table("pre_audit_certificates") as batch_op:
        batch_op.add_column(sa.Column("issuance_package_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("pre_audit_certificates") as batch_op:
        batch_op.drop_column("issuance_package_json")

    with op.batch_alter_table("pre_audits") as batch_op:
        batch_op.drop_index("ix_pre_audits_tenant_legal_entity")
        batch_op.drop_column("legal_entity_id")
