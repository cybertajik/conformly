"""Pre-audit readiness assessment models with RLS.

Revision ID: 0014
Revises: 20260912_0013
Create Date: 2026-09-12

Creates seven pre-audit tables: pre_audits, pre_audit_scopes,
pre_audit_checks, pre_audit_findings, pre_audit_reports,
pre_audit_manifests, and pre_audit_certificates.  All tables
include tenant_id, PostgreSQL Row Level Security policies, and
FORCE ROW LEVEL SECURITY.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260912_0014_pre_audit"
down_revision = "20260912_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── pre_audits ────────────────────────────────────────────────────
    op.create_table(
        "pre_audits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="planning",
        ),
        sa.Column(
            "framework_adoption_id",
            sa.Uuid(),
            sa.ForeignKey("tenant_framework_adoptions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "lead_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("rule_version", sa.String(50), nullable=False),
        sa.Column("overall_score", sa.Float()),
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
    )
    op.create_index("ix_pre_audits_tenant_status", "pre_audits", ["tenant_id", "status"])
    op.create_index(
        "ix_pre_audits_tenant_adoption",
        "pre_audits",
        ["tenant_id", "framework_adoption_id"],
    )

    # ── pre_audit_scopes ──────────────────────────────────────────────
    op.create_table(
        "pre_audit_scopes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pre_audit_id",
            sa.Uuid(),
            sa.ForeignKey("pre_audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "framework_version_id",
            sa.Uuid(),
            sa.ForeignKey("framework_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("control_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checked_count", sa.Integer(), nullable=False, server_default="0"),
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
        sa.UniqueConstraint(
            "tenant_id",
            "pre_audit_id",
            "framework_version_id",
            name="uq_pre_audit_scopes_version",
        ),
    )
    op.create_index(
        "ix_pre_audit_scopes_tenant_audit",
        "pre_audit_scopes",
        ["tenant_id", "pre_audit_id"],
    )

    # ── pre_audit_checks ──────────────────────────────────────────────
    op.create_table(
        "pre_audit_checks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scope_id",
            sa.Uuid(),
            sa.ForeignKey("pre_audit_scopes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("control_type", sa.String(32), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column(
            "result",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("rule_version", sa.String(50), nullable=False),
        sa.Column(
            "evidence_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "policy_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "open_findings_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("implementation_status", sa.String(32)),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evaluated_at", sa.DateTime(timezone=True)),
        sa.Column("snapshot_json", sa.Text()),
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
        sa.UniqueConstraint(
            "tenant_id",
            "scope_id",
            "control_type",
            "control_id",
            name="uq_pre_audit_checks_control",
        ),
    )
    op.create_index(
        "ix_pre_audit_checks_tenant_scope",
        "pre_audit_checks",
        ["tenant_id", "scope_id"],
    )
    op.create_index(
        "ix_pre_audit_checks_tenant_result",
        "pre_audit_checks",
        ["tenant_id", "result"],
    )

    # ── pre_audit_findings ────────────────────────────────────────────
    op.create_table(
        "pre_audit_findings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pre_audit_id",
            sa.Uuid(),
            sa.ForeignKey("pre_audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "check_id",
            sa.Uuid(),
            sa.ForeignKey("pre_audit_checks.id", ondelete="SET NULL"),
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "severity",
            sa.String(32),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("recommendation", sa.Text()),
        sa.Column(
            "remediation_status",
            sa.String(32),
            nullable=False,
            server_default="open",
        ),
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
    )
    op.create_index(
        "ix_pre_audit_findings_tenant_audit",
        "pre_audit_findings",
        ["tenant_id", "pre_audit_id"],
    )
    op.create_index(
        "ix_pre_audit_findings_tenant_status",
        "pre_audit_findings",
        ["tenant_id", "remediation_status"],
    )

    # ── pre_audit_reports ─────────────────────────────────────────────
    op.create_table(
        "pre_audit_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pre_audit_id",
            sa.Uuid(),
            sa.ForeignKey("pre_audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "file_id",
            sa.Uuid(),
            sa.ForeignKey("stored_files.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "report_type",
            sa.String(50),
            nullable=False,
            server_default="readiness_summary",
        ),
        sa.Column("rule_version", sa.String(50), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
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
    )
    op.create_index(
        "ix_pre_audit_reports_tenant_audit",
        "pre_audit_reports",
        ["tenant_id", "pre_audit_id"],
    )

    # ── pre_audit_manifests ───────────────────────────────────────────
    op.create_table(
        "pre_audit_manifests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pre_audit_id",
            sa.Uuid(),
            sa.ForeignKey("pre_audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "file_id",
            sa.Uuid(),
            sa.ForeignKey("stored_files.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("manifest_hash_sha256", sa.String(64), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("rule_version", sa.String(50), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
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
    )
    op.create_index(
        "ix_pre_audit_manifests_tenant_audit",
        "pre_audit_manifests",
        ["tenant_id", "pre_audit_id"],
    )

    # ── pre_audit_certificates ────────────────────────────────────────
    op.create_table(
        "pre_audit_certificates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pre_audit_id",
            sa.Uuid(),
            sa.ForeignKey("pre_audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("certificate_number", sa.String(100), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_reason", sa.Text()),
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
        sa.UniqueConstraint(
            "certificate_number",
            name="uq_pre_audit_certificates_number",
        ),
    )
    op.create_index(
        "ix_pre_audit_certificates_tenant_audit",
        "pre_audit_certificates",
        ["tenant_id", "pre_audit_id"],
    )
    op.create_index(
        "ix_pre_audit_certificates_tenant_status",
        "pre_audit_certificates",
        ["tenant_id", "status"],
    )

    # ── RLS policies (PostgreSQL only) ────────────────────────────────
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        tables = [
            "pre_audits",
            "pre_audit_scopes",
            "pre_audit_checks",
            "pre_audit_findings",
            "pre_audit_reports",
            "pre_audit_manifests",
            "pre_audit_certificates",
        ]
        for tbl in tables:
            safe = tbl.replace("-", "_")
            op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY {safe}_tenant_isolation ON {tbl}"
                f" USING (tenant_id = current_setting("
                f"'app.current_tenant_id')::uuid)"
            )


def downgrade() -> None:
    tables = [
        "pre_audit_certificates",
        "pre_audit_manifests",
        "pre_audit_reports",
        "pre_audit_findings",
        "pre_audit_checks",
        "pre_audit_scopes",
        "pre_audits",
    ]
    conn = op.get_bind()
    for tbl in tables:
        if conn.dialect.name == "postgresql":
            safe = tbl.replace("-", "_")
            op.execute(f"DROP POLICY IF EXISTS {safe}_tenant_isolation ON {tbl}")
        op.drop_table(tbl)
