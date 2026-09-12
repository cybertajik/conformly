from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditEvent, AuditOutcome
from conformly.audit.service import (
    ImmutableAuditEventError,
    UnsafeAuditMetadataError,
    record_audit_event,
    validate_safe_metadata,
)


def test_records_tenant_scoped_audit_event(session: Session) -> None:
    tenant_id = uuid4()
    actor_id = uuid4()

    event = record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=actor_id,
        action="membership.listed",
        resource_type="membership",
        resource_id=None,
        request_id="request-123",
        outcome=AuditOutcome.SUCCESS,
        metadata={"record_count": 2},
    )
    session.commit()

    persisted = session.get(AuditEvent, event.id)
    assert persisted is not None
    assert persisted.tenant_id == tenant_id
    assert persisted.actor_id == actor_id
    assert persisted.safe_metadata == {"record_count": 2}


def test_audit_event_participates_in_caller_transaction(session: Session) -> None:
    record_audit_event(
        session,
        tenant_id=uuid4(),
        actor_type=AuditActorType.USER,
        actor_id=uuid4(),
        action="membership.listed",
        resource_type="membership",
        resource_id=None,
        request_id="request-rollback",
        outcome=AuditOutcome.SUCCESS,
    )

    session.rollback()

    assert session.scalar(select(AuditEvent)) is None


@pytest.mark.parametrize(
    "metadata",
    [
        {"access_token": "value"},
        {"nested": {"password_hash": "value"}},
        {"encryption-key-version": "value"},
        {"unreviewed_note": "restricted plaintext could hide here"},
    ],
)
def test_sensitive_metadata_keys_are_rejected(metadata: dict[str, object]) -> None:
    with pytest.raises(UnsafeAuditMetadataError):
        validate_safe_metadata(metadata)


def test_oversized_metadata_is_rejected() -> None:
    with pytest.raises(UnsafeAuditMetadataError):
        validate_safe_metadata({"safe_detail": "x" * 9_000})


def test_unsupported_metadata_value_is_rejected() -> None:
    with pytest.raises(UnsafeAuditMetadataError):
        validate_safe_metadata({"safe_detail": object()})


def test_audit_event_update_is_rejected(session: Session) -> None:
    event = record_audit_event(
        session,
        tenant_id=None,
        actor_type=AuditActorType.SYSTEM,
        actor_id=None,
        action="system.started",
        resource_type="system",
        resource_id=None,
        request_id="request-update",
        outcome=AuditOutcome.SUCCESS,
    )
    session.commit()
    event.action = "system.changed"

    with pytest.raises(ImmutableAuditEventError):
        session.commit()


def test_audit_event_delete_is_rejected(session: Session) -> None:
    event = record_audit_event(
        session,
        tenant_id=None,
        actor_type=AuditActorType.SYSTEM,
        actor_id=None,
        action="system.started",
        resource_type="system",
        resource_id=None,
        request_id="request-delete",
        outcome=AuditOutcome.SUCCESS,
    )
    session.commit()
    session.delete(event)

    with pytest.raises(ImmutableAuditEventError):
        session.commit()
