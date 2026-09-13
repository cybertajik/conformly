"""Evidence and policy lifecycle, malware quarantine, and approved readiness workflow.

Revision ID: 20260913_0023
Revises: 20260913_0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0023"
down_revision: str | None = "20260913_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Evidence items: legal hold & retention
    with op.batch_alter_table("evidence_items") as batch_op:
        batch_op.add_column(
            sa.Column("legal_hold", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(
            sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True)
        )

    # 2. Evidence revisions table
    op.create_table(
        "evidence_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("control_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "evidence_id", "revision_number", name="uq_evidence_revisions_number"),
    )
    op.create_index(
        "ix_evidence_revisions_tenant_evidence",
        "evidence_revisions",
        ["tenant_id", "evidence_id"],
    )

    # 3. Policy revisions table
    op.create_table(
        "policy_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("version_string", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("restricted_content_encrypted", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "policy_id", "revision_number", name="uq_policy_revisions_number"),
    )
    op.create_index(
        "ix_policy_revisions_tenant_policy",
        "policy_revisions",
        ["tenant_id", "policy_id"],
    )

    # 4. Policy templates table
    op.create_table(
        "policy_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("content_template", sa.Text(), nullable=False),
        sa.Column("suggested_classification", sa.String(32), server_default="Internal", nullable=False),
        sa.Column("is_canonical", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_policy_templates_tenant_slug",
        "policy_templates",
        ["tenant_id", "slug"],
    )
    op.create_index(
        "ix_policy_templates_category",
        "policy_templates",
        ["category"],
    )

    # 5. Policy acknowledgements table
    op.create_table(
        "policy_acknowledgements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("policy_revision_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_revision_id"], ["policy_revisions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "policy_id", "user_id", "policy_revision_id",
            name="uq_policy_acknowledgements_user_rev"
        ),
    )
    op.create_index(
        "ix_policy_acknowledgements_tenant_policy",
        "policy_acknowledgements",
        ["tenant_id", "policy_id"],
    )
    op.create_index(
        "ix_policy_acknowledgements_tenant_user",
        "policy_acknowledgements",
        ["tenant_id", "user_id"],
    )

    # 6. Stored files: quarantine reason
    with op.batch_alter_table("stored_files") as batch_op:
        batch_op.add_column(
            sa.Column("quarantine_reason", sa.Text(), nullable=True)
        )

    # 7. Pre-audits: tenant approval
    with op.batch_alter_table("pre_audits") as batch_op:
        batch_op.add_column(
            sa.Column("tenant_approved_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("tenant_approved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
        )

    # 8. Pre-audit certificates: suspension & supersession
    with op.batch_alter_table("pre_audit_certificates") as batch_op:
        batch_op.add_column(
            sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("suspended_reason", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "superseded_by_certificate_id",
                sa.Uuid(),
                sa.ForeignKey("pre_audit_certificates.id", ondelete="SET NULL"),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("pre_audit_certificates") as batch_op:
        batch_op.drop_column("superseded_by_certificate_id")
        batch_op.drop_column("superseded_at")
        batch_op.drop_column("suspended_reason")
        batch_op.drop_column("suspended_at")

    with op.batch_alter_table("pre_audits") as batch_op:
        batch_op.drop_column("tenant_approved_by_user_id")
        batch_op.drop_column("tenant_approved_at")

    with op.batch_alter_table("stored_files") as batch_op:
        batch_op.drop_column("quarantine_reason")

    op.drop_index("ix_policy_acknowledgements_tenant_user", table_name="policy_acknowledgements")
    op.drop_index("ix_policy_acknowledgements_tenant_policy", table_name="policy_acknowledgements")
    op.drop_table("policy_acknowledgements")

    op.drop_index("ix_policy_templates_category", table_name="policy_templates")
    op.drop_index("ix_policy_templates_tenant_slug", table_name="policy_templates")
    op.drop_table("policy_templates")

    op.drop_index("ix_policy_revisions_tenant_policy", table_name="policy_revisions")
    op.drop_table("policy_revisions")

    op.drop_index("ix_evidence_revisions_tenant_evidence", table_name="evidence_revisions")
    op.drop_table("evidence_revisions")

    with op.batch_alter_table("evidence_items") as batch_op:
        batch_op.drop_column("retention_until")
        batch_op.drop_column("legal_hold")
