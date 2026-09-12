from dataclasses import dataclass
from uuid import UUID

from conformly.authz.roles import ROLE_CAPABILITIES, Capability, Role


class AuthorizationDeniedError(Exception):
    """Raised when a principal lacks a required tenant capability."""


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: UUID
    is_platform_admin: bool = False


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: UUID
    user_id: UUID
    role: Role


def authorize(principal: Principal, tenant_context: TenantContext, capability: Capability) -> None:
    if principal.user_id != tenant_context.user_id:
        raise AuthorizationDeniedError("principal does not own tenant context")
    if capability not in ROLE_CAPABILITIES[tenant_context.role]:
        raise AuthorizationDeniedError("capability denied")
