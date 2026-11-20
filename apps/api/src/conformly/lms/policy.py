"""Centralized LMS admission and entitlement policy enforcement."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.entitlements.service import is_module_enabled
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus

# Only Owner and Compliance Manager are admitted for LMS management operations
ADMITTED_LMS_ROLES = frozenset({Role.OWNER, Role.COMPLIANCE_MANAGER})


class LmsAccessDeniedError(HTTPException):
    """Raised when LMS access is denied."""

    def __init__(
        self,
        detail: str = "LMS access denied",
        status_code: int = status.HTTP_403_FORBIDDEN,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)


def verify_lms_access(
    database: Session,
    tenant_id: UUID,
    principal: Principal,
    tenant: TenantContext,
    operation: Literal["read", "mutate"] = "read",
) -> None:
    """Centralized admission policy enforcement for LMS courses, assignments, and completions.

    Requirements:
    1. Tenant must have an active entitlement for the 'lms' module.
    2. Tenant context must match requested tenant_id.
    3. Tenant lifecycle state must be ACTIVE.
    4. Whole-tenant scope required (no sub-entity legal_entity_id or business_unit_id).
    5. No workforce or external advisor access.
    6. Role must be in {OWNER, COMPLIANCE_MANAGER}. Administrator and others denied 403.
    7. Principal must have MFA verified.
    8. Principal must have an active membership in the tenant.
    """
    # 1. Module entitlement check
    if not is_module_enabled(database, tenant_id, "lms"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="LMS module is not enabled for this tenant",
        )

    # 2. Tenant ID match
    if tenant.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context mismatch",
        )

    # 3. Tenant lifecycle check
    tenant_record = database.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    if tenant_record.status != TenantStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tenant status '{tenant_record.status.value}' prohibits LMS operations",
        )

    # 4. Whole-tenant scope check (no legal entity or business unit scoping)
    if getattr(tenant, "legal_entity_id", None) is not None or getattr(tenant, "business_unit_id", None) is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Whole-tenant scope required; sub-entity scope denied",
        )

    # 5. No workforce or external advisor
    if getattr(tenant, "is_workforce", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workforce access denied for LMS management",
        )
    if getattr(tenant, "is_external_advisor", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="External advisor access denied for LMS management",
        )

    # 6. Role check: only OWNER and COMPLIANCE_MANAGER admitted
    if tenant.role not in ADMITTED_LMS_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not authorized for LMS operations",
        )

    # 7. MFA verification
    if not principal.mfa_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA verification required",
        )

    # 8. Active tenant membership check
    stmt = select(Membership).where(
        Membership.tenant_id == tenant_id,
        Membership.user_id == principal.user_id,
        Membership.status == MembershipStatus.ACTIVE,
    )
    membership = database.scalar(stmt)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active tenant membership required",
        )
    if membership.role != tenant.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Membership role mismatch",
        )

