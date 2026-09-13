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


def test_audit_hash_chaining_and_sealing_verification(session: Session) -> None:
    from conformly.audit.service import create_audit_seal, verify_audit_chain

    tenant_id = uuid4()
    events = []
    for i in range(5):
        evt = record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=uuid4(),
            action=f"action.{i}",
            resource_type="document",
            resource_id=f"doc-{i}",
            request_id=f"req-{i}",
            outcome=AuditOutcome.SUCCESS,
            metadata={"count": i},
        )
        events.append(evt)
    session.commit()

    # Verify sequential numbers and hash chain
    assert events[0].sequence_number == 1
    assert events[0].prev_hash == "0" * 64
    assert len(events[0].event_hash) == 64

    for idx in range(1, len(events)):
        assert events[idx].sequence_number == idx + 1
        assert events[idx].prev_hash == events[idx - 1].event_hash

    # Verify chain passes verification
    valid, count, error = verify_audit_chain(session, tenant_id)
    assert valid is True, f"Verification failed: {error}"
    assert count == 5
    assert error is None

    # Create immutable seal
    seal = create_audit_seal(session, tenant_id=tenant_id)
    session.commit()

    assert seal.start_sequence == 1
    assert seal.end_sequence == 5
    assert seal.record_count == 5
    assert seal.head_event_hash == events[-1].event_hash
    assert len(seal.merkle_root) == 64
    assert len(seal.seal_signature_digest) == 64

    # Verify chain with seal passes
    valid, count, error = verify_audit_chain(session, tenant_id)
    assert valid is True
    assert count == 5
    assert error is None


def test_audit_chain_tamper_detection(session: Session) -> None:
    from conformly.audit.service import verify_audit_chain

    tenant_id = uuid4()
    for i in range(3):
        record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=uuid4(),
            action=f"step.{i}",
            resource_type="record",
            resource_id=str(i),
            request_id=f"req-{i}",
            outcome=AuditOutcome.SUCCESS,
        )
    session.commit()

    # Direct database manipulation to simulate tampering (bypassing ORM event listener via SQL execution)
    from sqlalchemy import text

    # Alter event_hash of event #2
    session.execute(
        text(
            "UPDATE audit_events SET event_hash = 'tampered_hash_000000000000000000000000000000000000000000000000' WHERE sequence_number = 2"
        ),
    )
    session.commit()
    session.expire_all()

    valid, seq, error = verify_audit_chain(session, tenant_id)

    assert valid is False
    assert seq == 2
    assert "Event hash mismatch" in str(error)
