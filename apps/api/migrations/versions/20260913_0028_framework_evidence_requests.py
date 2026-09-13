"""Adoption-bound evidence requests; no changes to existing releases or customer evidence."""

import sqlalchemy as sa
from alembic import op

revision = "20260913_0028"
down_revision = "20260913_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "framework_evidence_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "adoption_id", sa.Uuid(), sa.ForeignKey("tenant_framework_adoptions.id"), nullable=False
        ),
        sa.Column(
            "specification_id",
            sa.Uuid(),
            sa.ForeignKey("evidence_specifications.id"),
            nullable=False,
        ),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("compliance_tasks.id"), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), sa.ForeignKey("evidence_items.id")),
        sa.Column("evidence_version", sa.Integer()),
        sa.Column("observation_start", sa.DateTime(timezone=True)),
        sa.Column("observation_end", sa.DateTime(timezone=True)),
        sa.Column("accepted_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "tenant_id", "adoption_id", "specification_id", name="uq_framework_request_spec"
        ),
    )
    op.create_index(
        "ix_framework_requests_tenant_adoption",
        "framework_evidence_requests",
        ["tenant_id", "adoption_id"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE framework_evidence_requests ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE framework_evidence_requests FORCE ROW LEVEL SECURITY")
        op.execute("""CREATE POLICY framework_requests_tenant ON framework_evidence_requests
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)""")
        op.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON framework_evidence_requests TO conformly_app"
        )


def downgrade() -> None:
    op.drop_table("framework_evidence_requests")
