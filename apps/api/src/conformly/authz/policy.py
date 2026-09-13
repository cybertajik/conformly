from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from conformly.authz.roles import ROLE_CAPABILITIES, Capability, Role


class AuthorizationDeniedError(Exception):
    """Raised when a principal lacks a required tenant capability or resource scope."""


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: UUID
    is_platform_admin: bool = False
    mfa_verified: bool = True


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: UUID
    user_id: UUID
    role: Role
    legal_entity_id: UUID | None = None
    business_unit_id: UUID | None = None
    is_external_advisor: bool = False
    expires_at: datetime | None = None
    is_workforce: bool = False


_EVIDENCE_MUTATION_CAPABILITIES: frozenset[Capability] = frozenset(
    {
        Capability.EVIDENCE_MANAGE,
        Capability.FILE_WRITE,
        Capability.FILE_DELETE,
        Capability.CONTROL_STATUS_MANAGE,
        Capability.POLICY_MANAGE,
    }
)


def authorize(
    principal: Principal,
    tenant_context: TenantContext,
    capability: Capability,
    *,
    now: datetime | None = None,
) -> None:
    if principal.user_id != tenant_context.user_id:
        raise AuthorizationDeniedError("principal does not own tenant context")

    current_time = now or datetime.now(UTC)

    # Enforce engagement expiration if timestamp is set
    if tenant_context.expires_at is not None:
        exp = (
            tenant_context.expires_at
            if tenant_context.expires_at.tzinfo is not None
            else tenant_context.expires_at.replace(tzinfo=UTC)
        )
        if current_time >= exp:
            raise AuthorizationDeniedError("membership engagement has expired")

    # Workforce members have no standing access: must have an active expiring engagement
    if tenant_context.is_workforce:
        if tenant_context.expires_at is None:
            raise AuthorizationDeniedError(
                "workforce members must have an active expiring engagement"
            )

    # External advisors must have a time-limited engagement
    if tenant_context.is_external_advisor and tenant_context.expires_at is None:
        raise AuthorizationDeniedError(
            "external advisors must have a time-limited engagement with an expiration timestamp"
        )

    # Assessors / External advisors / Reviewers can NEVER mutate customer evidence or controls
    if tenant_context.is_external_advisor or tenant_context.role in (Role.REVIEWER, Role.AUDITOR):
        if capability in _EVIDENCE_MUTATION_CAPABILITIES:
            raise AuthorizationDeniedError(
                "assessors and external advisors cannot modify customer evidence or controls"
            )

    if capability not in ROLE_CAPABILITIES[tenant_context.role]:
        raise AuthorizationDeniedError("capability denied")


def authorize_resource(
    principal: Principal,
    tenant_context: TenantContext,
    capability: Capability,
    *,
    legal_entity_id: UUID | None = None,
    business_unit_id: UUID | None = None,
    owner_user_id: UUID | None = None,
    assigned_user_ids: Sequence[UUID] | set[UUID] | None = None,
    now: datetime | None = None,
) -> None:
    """Authorize a capability against a specific scoped resource.

    Enforces:
    1. Base role capability and engagement validity.
    2. Tenant legal-entity and business-unit boundary scopes.
    3. Assigned-material access for Reviewers.
    """
    authorize(principal, tenant_context, capability, now=now)

    # 1. Enforce organizational legal-entity scope
    if tenant_context.legal_entity_id is not None:
        if legal_entity_id is not None and legal_entity_id != tenant_context.legal_entity_id:
            raise AuthorizationDeniedError("resource outside assigned legal entity scope")

    # 2. Enforce organizational business-unit scope
    if tenant_context.business_unit_id is not None:
        if business_unit_id is not None and business_unit_id != tenant_context.business_unit_id:
            raise AuthorizationDeniedError("resource outside assigned business unit scope")

    # 3. Enforce Reviewer assigned-material access
    if tenant_context.role in (Role.REVIEWER, Role.AUDITOR):
        assigned: set[UUID] = set(assigned_user_ids or ())
        if owner_user_id is not None:
            assigned.add(owner_user_id)
        if principal.user_id not in assigned:
            raise AuthorizationDeniedError("reviewer may only access assigned material")
