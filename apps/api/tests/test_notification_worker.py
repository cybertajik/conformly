import base64
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditEvent, AuditOutcome
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.identity.models import Tenant
from conformly.notifications.models import NotificationOutbox, OutboxState
from conformly.notifications.service import enqueue_encrypted_notification
from conformly.notifications.worker import (
    MAX_DELIVERY_ATTEMPTS,
    NotificationDeliveryError,
    process_notification_batch,
    retry_delay,
)


class RecordingProvider:
    def __init__(self, failure: NotificationDeliveryError | None = None) -> None:
        self.failure = failure
        self.deliveries: list[tuple[str, dict[str, str], str]] = []

    def deliver(
        self,
        *,
        kind: str,
        payload: dict[str, str],
        idempotency_key: str,
    ) -> None:
        if self.failure is not None:
            raise self.failure
        self.deliveries.append((kind, payload, idempotency_key))


def make_codec() -> EncryptedFieldCodec:
    key = base64.b64encode(os.urandom(32)).decode("ascii")
    return EncryptedFieldCodec(
        EnvelopeEncryptionService(
            AES256GCMProvider(), LocalKeyManagementProvider({"v1": key}, "v1")
        )
    )


def enqueue_message(
    session: Session,
    codec: EncryptedFieldCodec,
    *,
    now: datetime,
    available_at: datetime | None = None,
) -> NotificationOutbox:
    tenant = Tenant(name="Worker Tenant", slug=f"worker-{uuid4()}")
    session.add(tenant)
    session.flush()
    return enqueue_encrypted_notification(
        session,
        codec,
        message_id=uuid4(),
        tenant_id=tenant.id,
        kind="membership_invitation",
        idempotency_key=f"invite:{uuid4()}",
        payload={"email": "person@example.test", "invitation_token": "secret-token"},
        available_at=available_at or now,
    )


def test_worker_delivers_decrypted_payload_with_stable_idempotency_key(session: Session) -> None:
    now = datetime.now(UTC)
    codec = make_codec()
    message = enqueue_message(session, codec, now=now)
    provider = RecordingProvider()

    result = process_notification_batch(session, codec, provider, now=now)

    assert result.delivered == 1
    assert result.claimed == 1
    assert provider.deliveries == [
        (
            "membership_invitation",
            {"email": "person@example.test", "invitation_token": "secret-token"},
            message.idempotency_key,
        )
    ]
    assert message.state is OutboxState.DELIVERED
    assert message.delivered_at == now
    audit = session.scalars(select(AuditEvent)).one()
    assert audit.outcome is AuditOutcome.SUCCESS
    assert "secret-token" not in str(audit.safe_metadata)


def test_retryable_failure_uses_deterministic_backoff(session: Session) -> None:
    now = datetime.now(UTC)
    codec = make_codec()
    message = enqueue_message(session, codec, now=now)
    provider = RecordingProvider(NotificationDeliveryError("provider_unavailable"))

    result = process_notification_batch(session, codec, provider, now=now)

    assert result.retried == 1
    assert message.state is OutboxState.PENDING
    assert message.available_at == now + timedelta(minutes=1)
    assert message.error_code == "provider_unavailable"
    audit = session.scalars(select(AuditEvent)).one()
    assert audit.safe_metadata == {
        "attempt": 1,
        "error_code": "provider_unavailable",
        "will_retry": True,
    }


def test_non_retryable_failure_moves_message_to_failed(session: Session) -> None:
    now = datetime.now(UTC)
    codec = make_codec()
    message = enqueue_message(session, codec, now=now)
    provider = RecordingProvider(NotificationDeliveryError("recipient_rejected", retryable=False))

    result = process_notification_batch(session, codec, provider, now=now)

    assert result.failed == 1
    assert message.state is OutboxState.FAILED
    assert message.error_code == "recipient_rejected"


def test_retry_limit_moves_message_to_failed(session: Session) -> None:
    now = datetime.now(UTC)
    codec = make_codec()
    message = enqueue_message(session, codec, now=now)
    message.attempts = MAX_DELIVERY_ATTEMPTS - 1
    provider = RecordingProvider(NotificationDeliveryError("provider_unavailable"))

    result = process_notification_batch(session, codec, provider, now=now)

    assert result.failed == 1
    assert message.attempts == MAX_DELIVERY_ATTEMPTS
    assert message.state is OutboxState.FAILED


def test_not_yet_available_message_is_not_claimed(session: Session) -> None:
    now = datetime.now(UTC)
    codec = make_codec()
    message = enqueue_message(session, codec, now=now, available_at=now + timedelta(minutes=5))

    result = process_notification_batch(session, codec, RecordingProvider(), now=now)

    assert result.claimed == 0
    assert message.state is OutboxState.PENDING
    assert message.attempts == 0


def test_retry_delay_is_bounded() -> None:
    assert retry_delay(1) == timedelta(minutes=1)
    assert retry_delay(2) == timedelta(minutes=2)
    assert retry_delay(99) == timedelta(hours=1)
