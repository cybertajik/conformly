"""Customer admission and policy enforcement for WP-09 customer onboarding demo."""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal, TenantContext, authorize
from conformly.authz.roles import Capability, Role
from conformly.config import Settings, get_settings
from conformly.identity.models import Tenant, TenantStatus


class CustomerDemoAdmissionError(HTTPException):
    """Raised when customer admission fails."""

    def __init__(
        self,
        detail: str = "Customer demo access denied",
        status_code: int = status.HTTP_403_FORBIDDEN,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)


class CustomerDemoDisabledError(HTTPException):
    """Raised when customer demo feature is disabled."""

    def __init__(self, detail: str = "Not Found") -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class CustomerDemoDatabaseAdmissionError(Exception):
    """Raised when PostgreSQL connection identity is disallowed."""


def verify_feature_enabled(settings: Settings | None = None) -> None:
    """Verify that customer demo feature is enabled and in permitted environment."""
    cfg = settings or get_settings()
    if not cfg.enable_customer_demo:
        raise CustomerDemoDisabledError("Customer demo is not enabled")
    if cfg.environment not in ("local", "development", "test"):
        raise CustomerDemoAdmissionError("Customer demo prohibited in non-development environments")


def verify_customer_demo_admission(
    principal: Principal,
    tenant_context: TenantContext,
    operation: Literal["read", "mutate"],
    session: Session | None = None,
    settings: Settings | None = None,
) -> None:
    """Centralized admission policy enforcement for customer demo.

    Requirements:
    1. Feature must be enabled in permitted environment.
    2. Principal must have MFA verified.
    3. Tenant context must have role in {OWNER, COMPLIANCE_MANAGER}.
    4. Must not have sub-tenant scope (legal_entity_id is None and business_unit_id is None).
    5. Must not be workforce or external advisor.
    6. Must have FRAMEWORK_READ (for read) or FRAMEWORK_MANAGE (for mutate).
    7. For mutations, tenant must be ACTIVE (not CANCELLING, SUSPENDED, DELETED).
    8. Database connection on PostgreSQL must be non-owner conformly_app without superuser/bypassrls.
    """
    # 1. Feature guard check
    verify_feature_enabled(settings)

    # 2. MFA verified
    if not principal.mfa_verified:
        raise CustomerDemoAdmissionError("MFA verification required")

    # 3. Whole-tenant context (no legal entity, no business unit scope)
    if tenant_context.legal_entity_id is not None or tenant_context.business_unit_id is not None:
        raise CustomerDemoAdmissionError("Whole-tenant scope required; sub-entity scope denied")

    # 4. No workforce or external advisor
    if getattr(tenant_context, "is_workforce", False):
        raise CustomerDemoAdmissionError("Workforce access denied for customer demo")
    if getattr(tenant_context, "is_external_advisor", False):
        raise CustomerDemoAdmissionError("External advisor access denied for customer demo")

    # 5. Role check: only OWNER and COMPLIANCE_MANAGER admitted
    allowed_roles = {Role.OWNER, Role.COMPLIANCE_MANAGER}
    if tenant_context.role not in allowed_roles:
        raise CustomerDemoAdmissionError("Role not admitted to customer demo")

    # 6. Capability check
    required_cap = (
        Capability.FRAMEWORK_MANAGE if operation == "mutate" else Capability.FRAMEWORK_READ
    )
    authorize(principal, tenant_context, required_cap)

    # 7. Tenant lifecycle check for mutations
    if operation == "mutate" and session is not None:
        tenant = session.query(Tenant).filter(Tenant.id == tenant_context.tenant_id).first()
        if tenant is None:
            raise CustomerDemoAdmissionError(
                "Tenant not found", status_code=status.HTTP_404_NOT_FOUND
            )
        if tenant.status != TenantStatus.ACTIVE:
            raise CustomerDemoAdmissionError(
                f"Tenant lifecycle state '{tenant.status.value}' prohibits customer demo mutations",
                status_code=status.HTTP_409_CONFLICT,
            )

    # 8. Database connection verification on PostgreSQL
    if session is not None:
        verify_database_connection(session)


def verify_database_connection(session: Session) -> None:
    """Verify runtime database connection is conformly_app non-owner on PostgreSQL."""
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    row = session.execute(
        text(
            "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
    ).first()
    if row is None:
        raise CustomerDemoDatabaseAdmissionError("Unable to verify PostgreSQL runtime identity")

    user_name, is_super, is_bypass = row[0], row[1], row[2]
    if is_super or is_bypass or user_name != "conformly_app":
        raise CustomerDemoDatabaseAdmissionError(
            f"Disallowed PostgreSQL runtime identity: {user_name} (superuser={is_super}, bypassrls={is_bypass})"
        )

    # Table ownership check: current_user must not own customer demo tables
    owned_tables = session.execute(
        text(
            """
            SELECT c.relname
            FROM pg_class c
            JOIN pg_roles r ON r.oid = c.relowner
            WHERE c.relname IN (
                'customer_demo_workspaces',
                'customer_demo_answers',
                'customer_demo_evaluations',
                'customer_demo_adoptions',
                'customer_control_work',
                'customer_control_evidence_links',
                'customer_control_work_events'
            )
            AND r.rolname = current_user
            """
        )
    ).fetchall()
    if owned_tables:
        table_names = [r[0] for r in owned_tables]
        raise CustomerDemoDatabaseAdmissionError(
            f"PostgreSQL user '{user_name}' must not own customer demo tables: {table_names}"
        )
