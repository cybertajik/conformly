"""External integrations, webhooks, and LMS training models with RLS.

Revision ID: 20260913_0025
Revises: 20260913_0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0025"
down_revision: str | None = "20260913_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Integration credentials table
    op.create_table(
        "integration_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("key_id", sa.String(length=64), nullable=False),
        sa.Column("secret_hash", sa.String(length=255), nullable=False),
        sa.Column("encrypted_signing_secret", sa.JSON(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_id", name="uq_integration_credentials_key_id"),
    )
    op.create_index(
        "ix_integration_credentials_tenant_status",
        "integration_credentials",
        ["tenant_id", "status"],
    )

    # 2. Webhook subscriptions table
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("target_url", sa.String(length=1024), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("encrypted_secret", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_webhook_subscriptions_tenant_active",
        "webhook_subscriptions",
        ["tenant_id", "is_active"],
    )

    # 3. Inbound webhook events (replay & idempotency)
    op.create_table(
        "inbound_webhook_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("credential_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("event_topic", sa.String(length=128), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="processing", nullable=False),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["credential_id"], ["integration_credentials.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_inbound_webhook_events_tenant_idempotency"
        ),
    )
    op.create_index(
        "ix_inbound_webhook_events_tenant_created",
        "inbound_webhook_events",
        ["tenant_id", "created_at"],
    )

    # 4. Training courses table
    op.create_table(
        "training_courses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=32), server_default="1.0", nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=128), server_default="lms", nullable=False),
        sa.Column("duration_minutes", sa.Integer(), server_default="30", nullable=False),
        sa.Column("validity_period_days", sa.Integer(), server_default="365", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "course_id", "version", name="uq_training_courses_tenant_course_version"
        ),
    )
    op.create_index(
        "ix_training_courses_tenant_course",
        "training_courses",
        ["tenant_id", "course_id"],
    )

    # 5. Training assignments table
    op.create_table(
        "training_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("workforce_email", sa.String(length=320), nullable=False),
        sa.Column("assigned_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="assigned", nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=True),
        sa.Column("control_type", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_training_assignments_tenant_status",
        "training_assignments",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_training_assignments_tenant_user",
        "training_assignments",
        ["tenant_id", "user_id"],
    )
    op.create_index(
        "ix_training_assignments_tenant_control",
        "training_assignments",
        ["tenant_id", "control_id"],
    )

    # 6. Training completions table
    op.create_table(
        "training_completions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=True),
        sa.Column("course_id", sa.String(length=128), nullable=False),
        sa.Column("course_version", sa.String(length=32), server_default="1.0", nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("workforce_email", sa.String(length=320), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("certificate_id", sa.String(length=255), nullable=True),
        sa.Column("evidence_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("verified_via", sa.String(length=32), server_default="webhook", nullable=False),
        sa.Column("raw_payload_encrypted", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["assignment_id"], ["training_assignments.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_training_completions_tenant_idempotency"
        ),
    )
    op.create_index(
        "ix_training_completions_tenant_course",
        "training_completions",
        ["tenant_id", "course_id"],
    )
    op.create_index(
        "ix_training_completions_tenant_user",
        "training_completions",
        ["tenant_id", "user_id"],
    )

    # 7. PostgreSQL Row-Level Security
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        rls_tables = [
            "integration_credentials",
            "webhook_subscriptions",
            "inbound_webhook_events",
            "training_courses",
            "training_assignments",
            "training_completions",
        ]
        for tbl in rls_tables:
            op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
            op.execute(
                f"""
                CREATE POLICY {tbl}_tenant_isolation ON {tbl}
                FOR ALL
                USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
                """
            )


def downgrade() -> None:
    op.drop_index("ix_training_completions_tenant_user", table_name="training_completions")
    op.drop_index("ix_training_completions_tenant_course", table_name="training_completions")
    op.drop_table("training_completions")

    op.drop_index("ix_training_assignments_tenant_control", table_name="training_assignments")
    op.drop_index("ix_training_assignments_tenant_user", table_name="training_assignments")
    op.drop_index("ix_training_assignments_tenant_status", table_name="training_assignments")
    op.drop_table("training_assignments")

    op.drop_index("ix_training_courses_tenant_course", table_name="training_courses")
    op.drop_table("training_courses")

    op.drop_index("ix_inbound_webhook_events_tenant_created", table_name="inbound_webhook_events")
    op.drop_table("inbound_webhook_events")

    op.drop_index("ix_webhook_subscriptions_tenant_active", table_name="webhook_subscriptions")
    op.drop_table("webhook_subscriptions")

    op.drop_index("ix_integration_credentials_tenant_status", table_name="integration_credentials")
    op.drop_table("integration_credentials")
