"""Platform-only catalog actor context and verification."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID


class CatalogActorKind(StrEnum):
    PLATFORM_USER = "PlatformUser"


class CatalogCapability(StrEnum):
    DRAFT_READ = "DRAFT_READ"
    DRAFT_WRITE = "DRAFT_WRITE"
    PERMISSION_DECIDE = "PERMISSION_DECIDE"


class CatalogError(Exception):
    """Base error for all catalog V2 exceptions."""


class CatalogSecurityError(CatalogError):
    """Raised when actor context or authorization checks fail."""


class CatalogPermissionDeniedError(CatalogError):
    """Raised when source-use effective permission is absent, expired, or denied."""


class CatalogConflictError(CatalogError):
    """Raised when optimistic concurrency, digest mismatch, or duplicate request conflict occurs."""


class CatalogNotFoundError(CatalogError):
    """Raised when a requested aggregate is missing or inaccessible."""


class CatalogValidationError(CatalogError):
    """Raised when input validation fails."""


class CatalogInvariantError(CatalogError):
    """Raised when an internal system invariant (e.g. missing guard) is violated."""


@dataclass(frozen=True)
class CatalogActorContext:
    """Immutable catalog platform actor execution context."""

    actor_id: UUID
    is_platform_admin: bool
    mfa_verified: bool
    authenticated_at: datetime
    capabilities: frozenset[CatalogCapability]
    actor_kind: CatalogActorKind = CatalogActorKind.PLATFORM_USER

    def __post_init__(self) -> None:
        if not isinstance(self.actor_id, UUID):
            raise CatalogSecurityError("actor_id must be a UUID")
        if self.actor_kind != CatalogActorKind.PLATFORM_USER:
            raise CatalogSecurityError("actor_kind must be PlatformUser")
        if self.authenticated_at.tzinfo is None:
            raise CatalogSecurityError("authenticated_at must be timezone-aware")


def verify_catalog_actor(
    context: CatalogActorContext | None,
    required_capability: CatalogCapability,
    db_time: datetime,
) -> None:
    """Verify platform admin actor context against database time and required capability."""
    if context is None:
        raise CatalogSecurityError("Missing catalog actor context")
    if not isinstance(context, CatalogActorContext):
        raise CatalogSecurityError("Invalid catalog actor context type")

    if context.actor_kind != CatalogActorKind.PLATFORM_USER:
        raise CatalogSecurityError("Actor kind must be PlatformUser")
    if not context.is_platform_admin:
        raise CatalogSecurityError("Platform admin status required")
    if not context.mfa_verified:
        raise CatalogSecurityError("Verified MFA required")
    if required_capability not in context.capabilities:
        raise CatalogSecurityError(f"Missing required capability: {required_capability.value}")

    # Time normalization
    if db_time.tzinfo is None:
        db_time = db_time.replace(tzinfo=UTC)
    auth_time = context.authenticated_at
    if auth_time.tzinfo is None:
        raise CatalogSecurityError("authenticated_at must be timezone-aware")

    # Reject future authentication time
    if auth_time > db_time + timedelta(seconds=5):
        raise CatalogSecurityError("Authentication timestamp cannot be in the future")

    # Reject authentication older than 15 minutes (900 seconds)
    age_seconds = (db_time - auth_time).total_seconds()
    if age_seconds > 900.0:
        raise CatalogSecurityError("Authentication expired: age exceeds 15 minutes")
