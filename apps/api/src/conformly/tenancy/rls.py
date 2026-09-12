from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def set_rls_context(
    session: Session,
    *,
    user_id: UUID,
    tenant_id: UUID,
    tenant_verified: bool,
) -> None:
    """Set transaction-local PostgreSQL values consumed by tenant RLS policies."""
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return

    values = {
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "tenant_verified": "true" if tenant_verified else "false",
    }
    session.execute(text("SELECT set_config('app.current_user_id', :user_id, true)"), values)
    session.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"), values)
    session.execute(
        text("SELECT set_config('app.tenant_verified', :tenant_verified, true)"), values
    )


def set_user_rls_context(session: Session, *, user_id: UUID) -> None:
    """Allow pre-selection discovery of only the authenticated user's memberships."""
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    values = {"user_id": str(user_id), "tenant_id": "", "tenant_verified": "false"}
    session.execute(text("SELECT set_config('app.current_user_id', :user_id, true)"), values)
    session.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"), values)
    session.execute(
        text("SELECT set_config('app.tenant_verified', :tenant_verified, true)"), values
    )


def set_anonymous_tenant_rls_context(session: Session, *, tenant_id: UUID) -> None:
    """Scope database transaction to a verified tenant for anonymous whistleblower operations."""
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    values = {"user_id": "", "tenant_id": str(tenant_id), "tenant_verified": "true"}
    session.execute(text("SELECT set_config('app.current_user_id', :user_id, true)"), values)
    session.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"), values)
    session.execute(
        text("SELECT set_config('app.tenant_verified', :tenant_verified, true)"), values
    )


def set_system_tenant_rls_context(session: Session, *, tenant_id: UUID) -> None:
    """Scope a trusted background job to exactly one tenant without impersonating a user."""
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    values = {"user_id": "", "tenant_id": str(tenant_id), "tenant_verified": "true"}
    session.execute(text("SELECT set_config('app.current_user_id', :user_id, true)"), values)
    session.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"), values)
    session.execute(
        text("SELECT set_config('app.tenant_verified', :tenant_verified, true)"), values
    )
