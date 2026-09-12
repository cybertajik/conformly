from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.auth.session import hash_session_id
from conformly.authz.policy import Principal
from conformly.identity.models import AuthSession, User, UserStatus


class SessionLifecycleError(Exception):
    """Raised when a session lifecycle transition is invalid or unauthorized."""


def issue_auth_session(
    database: Session,
    *,
    user: User,
    session_id: str,
    expires_at: datetime,
    request_id: str,
    now: datetime | None = None,
) -> AuthSession:
    current_time = now or datetime.now(UTC)
    normalized_expiry = expires_at.replace(tzinfo=UTC) if expires_at.tzinfo is None else expires_at
    if (
        user.status is not UserStatus.ACTIVE
        or not session_id
        or len(session_id) > 512
        or normalized_expiry <= current_time
    ):
        raise SessionLifecycleError("session cannot be issued")

    auth_session = AuthSession(
        id=uuid4(),
        user_id=user.id,
        session_id_hash=hash_session_id(session_id),
        expires_at=normalized_expiry,
    )
    database.add(auth_session)
    record_audit_event(
        database,
        tenant_id=None,
        actor_type=AuditActorType.USER,
        actor_id=user.id,
        action="auth.session_issue",
        resource_type="auth_session",
        resource_id=str(auth_session.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        occurred_at=current_time,
    )
    database.flush()
    return auth_session


def revoke_own_auth_session(
    database: Session,
    principal: Principal,
    *,
    session_id: str,
    request_id: str,
    now: datetime | None = None,
) -> AuthSession:
    current_time = now or datetime.now(UTC)
    auth_session = database.scalar(
        select(AuthSession).where(
            AuthSession.session_id_hash == hash_session_id(session_id),
            AuthSession.user_id == principal.user_id,
        )
    )
    if auth_session is None:
        record_audit_event(
            database,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="auth.session_revoke",
            resource_type="auth_session",
            resource_id=None,
            request_id=request_id,
            outcome=AuditOutcome.DENIED,
            metadata={"reason": "not_found_for_actor"},
            occurred_at=current_time,
        )
        raise SessionLifecycleError("session cannot be revoked")

    already_revoked = auth_session.revoked_at is not None
    if not already_revoked:
        auth_session.revoked_at = current_time
    record_audit_event(
        database,
        tenant_id=None,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="auth.session_revoke",
        resource_type="auth_session",
        resource_id=str(auth_session.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"already_revoked": already_revoked},
        occurred_at=current_time,
    )
    database.flush()
    return auth_session
