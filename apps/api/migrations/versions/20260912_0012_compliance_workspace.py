"""Add Compliance Workspace models (Evidence, Policies, Tasks, Findings, Control Status,
Preferences) with RLS.

Revision ID: 20260912_0012
Revises: 20260911_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0012"
down_revision: str | None = "20260911_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Evidence Items
    op.create_table(
        "evidence_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("restricted_notes_encrypted", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_evidence_items_owner_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_evidence_items_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_items")),
    )
    op.create_index(
        "ix_evidence_items_tenant_status",
        "evidence_items",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_evidence_items_tenant_valid_until",
        "evidence_items",
        ["tenant_id", "valid_until"],
        unique=False,
    )
    op.create_index(
        "ix_evidence_items_tenant_owner",
        "evidence_items",
        ["tenant_id", "owner_user_id"],
        unique=False,
    )

    # 2. Evidence File Links
    op.create_table(
        "evidence_file_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("attached_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["attached_by_user_id"],
            ["users.id"],
            name=op.f("fk_evidence_file_links_attached_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence_items.id"],
            name=op.f("fk_evidence_file_links_evidence_id_evidence_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["stored_files.id"],
            name=op.f("fk_evidence_file_links_file_id_stored_files"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_evidence_file_links_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_file_links")),
        sa.UniqueConstraint(
            "tenant_id",
            "evidence_id",
            "file_id",
            name=op.f("uq_evidence_file_links_file"),
        ),
    )
    op.create_index(
        "ix_evidence_file_links_tenant_evidence",
        "evidence_file_links",
        ["tenant_id", "evidence_id"],
        unique=False,
    )

    # 3. Evidence Control Links
    op.create_table(
        "evidence_control_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("control_type", sa.String(length=32), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("linked_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence_items.id"],
            name=op.f("fk_evidence_control_links_evidence_id_evidence_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["linked_by_user_id"],
            ["users.id"],
            name=op.f("fk_evidence_control_links_linked_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_evidence_control_links_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_control_links")),
        sa.UniqueConstraint(
            "tenant_id",
            "evidence_id",
            "control_type",
            "control_id",
            name=op.f("uq_evidence_control_links_control"),
        ),
    )
    op.create_index(
        "ix_evidence_control_links_tenant_control",
        "evidence_control_links",
        ["tenant_id", "control_id"],
        unique=False,
    )

    # 4. Policies
    op.create_table(
        "policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("version_string", sa.String(length=50), nullable=False, server_default="1.0"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_cycle_days", sa.Integer(), nullable=False, server_default="365"),
        sa.Column("next_review_due", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("restricted_content_encrypted", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name=op.f("fk_policies_approved_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_policies_owner_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_policies_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policies")),
    )
    op.create_index(
        "ix_policies_tenant_status",
        "policies",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_policies_tenant_review_due",
        "policies",
        ["tenant_id", "next_review_due"],
        unique=False,
    )

    # 5. Policy Control Links
    op.create_table(
        "policy_control_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("control_type", sa.String(length=32), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("linked_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["linked_by_user_id"],
            ["users.id"],
            name=op.f("fk_policy_control_links_linked_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["policies.id"],
            name=op.f("fk_policy_control_links_policy_id_policies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_policy_control_links_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_control_links")),
        sa.UniqueConstraint(
            "tenant_id",
            "policy_id",
            "control_type",
            "control_id",
            name=op.f("uq_policy_control_links_control"),
        ),
    )
    op.create_index(
        "ix_policy_control_links_tenant_control",
        "policy_control_links",
        ["tenant_id", "control_id"],
        unique=False,
    )

    # 6. Compliance Tasks
    op.create_table(
        "compliance_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("assignee_user_id", sa.Uuid(), nullable=True),
        sa.Column("control_type", sa.String(length=32), nullable=True),
        sa.Column("control_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_id", sa.Uuid(), nullable=True),
        sa.Column("policy_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assignee_user_id"],
            ["users.id"],
            name=op.f("fk_compliance_tasks_assignee_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["completed_by_user_id"],
            ["users.id"],
            name=op.f("fk_compliance_tasks_completed_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence_items.id"],
            name=op.f("fk_compliance_tasks_evidence_id_evidence_items"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["policies.id"],
            name=op.f("fk_compliance_tasks_policy_id_policies"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_compliance_tasks_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_compliance_tasks")),
    )
    op.create_index(
        "ix_compliance_tasks_tenant_status",
        "compliance_tasks",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_compliance_tasks_tenant_due",
        "compliance_tasks",
        ["tenant_id", "due_date"],
        unique=False,
    )
    op.create_index(
        "ix_compliance_tasks_tenant_assignee",
        "compliance_tasks",
        ["tenant_id", "assignee_user_id"],
        unique=False,
    )

    # 7. Findings
    op.create_table(
        "findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("remediation_status", sa.String(length=32), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("control_type", sa.String(length=32), nullable=True),
        sa.Column("control_id", sa.Uuid(), nullable=True),
        sa.Column("remediation_plan", sa.Text(), nullable=True),
        sa.Column("remediation_summary", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_findings_owner_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"],
            ["users.id"],
            name=op.f("fk_findings_resolved_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_findings_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_findings")),
    )
    op.create_index(
        "ix_findings_tenant_status",
        "findings",
        ["tenant_id", "remediation_status"],
        unique=False,
    )
    op.create_index(
        "ix_findings_tenant_severity",
        "findings",
        ["tenant_id", "severity"],
        unique=False,
    )

    # 8. Control Status Records
    op.create_table(
        "control_status_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("control_type", sa.String(length=32), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assigned_owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_assessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assessed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assigned_owner_user_id"],
            ["users.id"],
            name=op.f("fk_control_status_records_assigned_owner_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assessed_by_user_id"],
            ["users.id"],
            name=op.f("fk_control_status_records_assessed_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_control_status_records_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_control_status_records")),
        sa.UniqueConstraint(
            "tenant_id",
            "control_type",
            "control_id",
            name=op.f("uq_control_status_records_control"),
        ),
    )
    op.create_index(
        "ix_control_status_records_tenant_status",
        "control_status_records",
        ["tenant_id", "status"],
        unique=False,
    )

    # 9. User Notification Preferences
    op.create_table(
        "user_notification_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "digest_frequency", sa.String(length=32), nullable=False, server_default="immediate"
        ),
        sa.Column("notify_task_assigned", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_task_due", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_evidence_expired", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_policy_review", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_finding_raised", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_user_notification_preferences_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_notification_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_notification_preferences")),
        sa.UniqueConstraint(
            "tenant_id",
            "user_id",
            name=op.f("uq_user_notification_preferences_user"),
        ),
    )
    op.create_index(
        "ix_user_notification_preferences_tenant",
        "user_notification_preferences",
        ["tenant_id"],
        unique=False,
    )

    # PostgreSQL Row-Level Security on all 9 tenant-scoped compliance tables
    tenant_tables = [
        "evidence_items",
        "evidence_file_links",
        "evidence_control_links",
        "policies",
        "policy_control_links",
        "compliance_tasks",
        "findings",
        "control_status_records",
        "user_notification_preferences",
    ]
    for tbl in tenant_tables:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {tbl}_tenant_read ON {tbl}
            FOR SELECT
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                AND current_setting('app.tenant_verified', true) = 'true'
            )
            """
        )
        op.execute(
            f"""
            CREATE POLICY {tbl}_tenant_insert ON {tbl}
            FOR INSERT
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                AND current_setting('app.tenant_verified', true) = 'true'
            )
            """
        )
        op.execute(
            f"""
            CREATE POLICY {tbl}_tenant_update ON {tbl}
            FOR UPDATE
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                AND current_setting('app.tenant_verified', true) = 'true'
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                AND current_setting('app.tenant_verified', true) = 'true'
            )
            """
        )
        op.execute(
            f"""
            CREATE POLICY {tbl}_tenant_delete ON {tbl}
            FOR DELETE
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                AND current_setting('app.tenant_verified', true) = 'true'
            )
            """
        )


def downgrade() -> None:
    tenant_tables = [
        "user_notification_preferences",
        "control_status_records",
        "findings",
        "compliance_tasks",
        "policy_control_links",
        "policies",
        "evidence_control_links",
        "evidence_file_links",
        "evidence_items",
    ]
    for tbl in tenant_tables:
        op.execute(f"DROP POLICY IF EXISTS {tbl}_tenant_delete ON {tbl}")
        op.execute(f"DROP POLICY IF EXISTS {tbl}_tenant_update ON {tbl}")
        op.execute(f"DROP POLICY IF EXISTS {tbl}_tenant_insert ON {tbl}")
        op.execute(f"DROP POLICY IF EXISTS {tbl}_tenant_read ON {tbl}")
        op.execute(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY")

    op.drop_index(
        "ix_user_notification_preferences_tenant", table_name="user_notification_preferences"
    )
    op.drop_table("user_notification_preferences")

    op.drop_index("ix_control_status_records_tenant_status", table_name="control_status_records")
    op.drop_table("control_status_records")

    op.drop_index("ix_findings_tenant_severity", table_name="findings")
    op.drop_index("ix_findings_tenant_status", table_name="findings")
    op.drop_table("findings")

    op.drop_index("ix_compliance_tasks_tenant_assignee", table_name="compliance_tasks")
    op.drop_index("ix_compliance_tasks_tenant_due", table_name="compliance_tasks")
    op.drop_index("ix_compliance_tasks_tenant_status", table_name="compliance_tasks")
    op.drop_table("compliance_tasks")

    op.drop_index("ix_policy_control_links_tenant_control", table_name="policy_control_links")
    op.drop_table("policy_control_links")

    op.drop_index("ix_policies_tenant_review_due", table_name="policies")
    op.drop_index("ix_policies_tenant_status", table_name="policies")
    op.drop_table("policies")

    op.drop_index("ix_evidence_control_links_tenant_control", table_name="evidence_control_links")
    op.drop_table("evidence_control_links")

    op.drop_index("ix_evidence_file_links_tenant_evidence", table_name="evidence_file_links")
    op.drop_table("evidence_file_links")

    op.drop_index("ix_evidence_items_tenant_owner", table_name="evidence_items")
    op.drop_index("ix_evidence_items_tenant_valid_until", table_name="evidence_items")
    op.drop_index("ix_evidence_items_tenant_status", table_name="evidence_items")
    op.drop_table("evidence_items")
