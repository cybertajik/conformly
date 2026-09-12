from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditEvent, AuditOutcome
from conformly.auth.lifecycle import (
    SessionLifecycleError,
    issue_auth_session,
    revoke_own_auth_session,
)
from conformly.auth.session import hash_session_id
from conformly.authz.policy import Principal
from conformly.identity.models import AuthSession, User


def create_user(session: Session) -> User:
    user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject=str(uuid4()),
        email=f"{uuid4()}@example.test",
        display_name="Lifecycle User",
    )
    session.add(user)
    session.flush()
    return user


def test_session_issue_hashes_identifier_and_records_safe_audit(session: Session) -> None:
    user = create_user(session)
    raw_session_id = "high-entropy-session-secret"
    auth_session = issue_auth_session(
        session,
        user=user,
        session_id=raw_session_id,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        request_id="request-issue-session",
    )

    assert auth_session.session_id_hash == hash_session_id(raw_session_id)
    assert raw_session_id not in auth_session.session_id_hash
    event = session.scalars(select(AuditEvent)).one()
    assert event.action == "auth.session_issue"
    assert event.actor_id == user.id
    assert event.outcome is AuditOutcome.SUCCESS
    assert raw_session_id not in str(event.safe_metadata)


def test_principal_can_revoke_only_own_session(session: Session) -> None:
    owner = create_user(session)
    other = create_user(session)
    other_session = AuthSession(
        user_id=other.id,
        session_id_hash=hash_session_id("other-session"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add(other_session)
    session.flush()

    with pytest.raises(SessionLifecycleError):
        revoke_own_auth_session(
            session,
            Principal(user_id=owner.id),
            session_id="other-session",
            request_id="request-cross-user",
        )

    assert other_session.revoked_at is None
    event = session.scalars(select(AuditEvent)).one()
    assert event.outcome is AuditOutcome.DENIED
    assert event.safe_metadata == {"reason": "not_found_for_actor"}


def test_session_revocation_is_idempotent_and_audited(session: Session) -> None:
    user = create_user(session)
    auth_session = AuthSession(
        user_id=user.id,
        session_id_hash=hash_session_id("own-session"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add(auth_session)
    session.flush()
    first = revoke_own_auth_session(
        session,
        Principal(user_id=user.id),
        session_id="own-session",
        request_id="request-first-revoke",
    )
    revoked_at = first.revoked_at
    second = revoke_own_auth_session(
        session,
        Principal(user_id=user.id),
        session_id="own-session",
        request_id="request-second-revoke",
        now=datetime.now(UTC) + timedelta(minutes=1),
    )

    assert second.revoked_at == revoked_at
    events = session.scalars(select(AuditEvent).order_by(AuditEvent.occurred_at)).all()
    assert events[0].safe_metadata == {"already_revoked": False}
    assert events[1].safe_metadata == {"already_revoked": True}
