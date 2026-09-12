import re
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SAFE_NAMESPACE = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")


class TenantJobPayload(BaseModel):
    """Base contract for every tenant-scoped deterministic background job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=255)


class TenantJobHandler(Protocol):
    def __call__(self, payload: TenantJobPayload) -> Any: ...


def tenant_cache_key(tenant_id: UUID, namespace: str, identifier: str) -> str:
    """Construct a cache key that cannot omit the tenant boundary."""
    if not SAFE_NAMESPACE.fullmatch(namespace):
        raise ValueError("invalid cache namespace")
    if not identifier or len(identifier) > 255:
        raise ValueError("invalid cache identifier")
    return f"tenant:{tenant_id}:{namespace}:{identifier}"
