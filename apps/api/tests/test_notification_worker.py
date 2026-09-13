import base64
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
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


def test_smtp_notification_provider_success(monkeypatch: pytest.MonkeyPatch) -> None:
    import smtplib
    from unittest.mock import MagicMock

    from conformly.notifications.providers import SmtpNotificationProvider

    mock_smtp_instance = MagicMock()
    mock_smtp_class = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__enter__.return_value = mock_smtp_instance

    monkeypatch.setattr(smtplib, "SMTP", mock_smtp_class)

    provider = SmtpNotificationProvider(
        host="mailpit",
        port=1025,
        from_email="compliance@conformly.de",
    )

    payload = {
        "recipient_email": "auditor@example.com",
        "task_title": "Quarterly Access Review",
        "due_date": "2026-09-30",
    }
    provider.deliver(
        kind="compliance_task_reminder",
        payload=payload,
        idempotency_key="idemp-12345",
    )

    mock_smtp_class.assert_called_once_with("mailpit", 1025, timeout=10.0)
    assert mock_smtp_instance.send_message.called
    sent_msg = mock_smtp_instance.send_message.call_args[0][0]
    assert sent_msg["To"] == "auditor@example.com"
    assert sent_msg["From"] == "compliance@conformly.de"
    assert "Quarterly Access Review" in sent_msg["Subject"]
    assert sent_msg["X-Conformly-Idempotency-Key"] == "idemp-12345"


def test_smtp_notification_provider_error_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    import smtplib
    from unittest.mock import MagicMock

    from conformly.notifications.providers import SmtpNotificationProvider

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__.return_value = mock_smtp_instance
    mock_smtp_instance.send_message.side_effect = smtplib.SMTPRecipientsRefused(
        {"test@bad.com": (550, b"User unknown")}
    )

    monkeypatch.setattr(smtplib, "SMTP", MagicMock(return_value=mock_smtp_instance))

    provider = SmtpNotificationProvider(host="mailpit", port=1025)

    with pytest.raises(NotificationDeliveryError) as exc_info:
        provider.deliver(
            kind="membership_invitation",
            payload={"email": "test@bad.com", "invitation_token": "tok"},
            idempotency_key="key-err",
        )
    assert exc_info.value.retryable is False
    assert exc_info.value.error_code == "recipient_refused"

    # Test retryable network error
    mock_smtp_instance.send_message.side_effect = smtplib.SMTPServerDisconnected("Connection reset")
    with pytest.raises(NotificationDeliveryError) as exc_info2:
        provider.deliver(
            kind="membership_invitation",
            payload={"email": "test@good.com", "invitation_token": "tok"},
            idempotency_key="key-err-2",
        )
    assert exc_info2.value.retryable is True
    assert exc_info2.value.error_code == "smtp_connection_failed"


def test_webhook_notification_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    import httpx

    from conformly.notifications.providers import WebhookNotificationProvider

    mock_response = MagicMock(status_code=200)
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    monkeypatch.setattr(httpx, "Client", MagicMock(return_value=mock_client))

    provider = WebhookNotificationProvider(secret="test-secret")
    provider.deliver(
        kind="continuous_compliance_alert",
        payload={
            "webhook_url": "https://api.partner.example/webhook",
            "subject": "Posture change alert",
        },
        idempotency_key="webhook-key-1",
    )

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "https://api.partner.example/webhook"
    assert "X-Conformly-Signature" in call_args[1]["headers"]
    assert call_args[1]["headers"]["X-Conformly-Idempotency-Key"] == "webhook-key-1"


def test_composite_notification_provider_routing() -> None:
    from conformly.notifications.providers import (
        CompositeNotificationProvider,
        LoggingNotificationProvider,
    )

    class SpyProvider:
        def __init__(self) -> None:
            self.delivered: list[dict[str, str]] = []

        def deliver(self, *, kind: str, payload: dict[str, str], idempotency_key: str) -> None:
            self.delivered.append({"kind": kind, "idempotency_key": idempotency_key, **payload})

    smtp_spy = SpyProvider()
    webhook_spy = SpyProvider()
    fallback_log = LoggingNotificationProvider()

    composite = CompositeNotificationProvider(
        smtp_provider=smtp_spy,  # type: ignore[arg-type]
        webhook_provider=webhook_spy,  # type: ignore[arg-type]
        fallback_provider=fallback_log,
    )

    # Deliver email -> goes to smtp
    composite.deliver(
        kind="membership_invitation",
        payload={"email": "user@domain.com"},
        idempotency_key="c1",
    )
    assert len(smtp_spy.delivered) == 1
    assert len(webhook_spy.delivered) == 0

    # Deliver webhook -> goes to webhook
    composite.deliver(
        kind="alert",
        payload={"webhook_url": "https://partner.com/hook"},
        idempotency_key="c2",
    )
    assert len(webhook_spy.delivered) == 1

    # Deliver other -> goes to fallback
    composite.deliver(
        kind="generic",
        payload={"data": "test"},
        idempotency_key="c3",
    )
    assert len(fallback_log.deliveries) == 1


def test_run_worker_tick_and_failed_jobs_summary(session: Session) -> None:
    from sqlalchemy.orm import sessionmaker

    from conformly.notifications.service import (
        get_failed_jobs_summary,
        retry_outbox_message,
    )
    from conformly.notifications.worker import run_worker_tick

    now = datetime.now(UTC)
    codec = make_codec()
    enqueue_message(session, codec, now=now)
    session.commit()

    factory = sessionmaker(bind=session.bind)
    provider = RecordingProvider()

    # 1. Test worker tick delivers message
    summary = run_worker_tick(factory, codec, provider, now=now)
    assert summary["claimed"] == 1
    assert summary["delivered"] == 1
    assert summary["retried"] == 0
    assert summary["failed"] == 0

    # 2. Simulate a failed message
    failed_msg = enqueue_message(session, codec, now=now)
    failed_msg.state = OutboxState.FAILED
    failed_msg.attempts = 5
    failed_msg.error_code = "smtp_auth_failed"
    session.commit()

    failed_summary = get_failed_jobs_summary(session, failed_msg.tenant_id)
    assert failed_summary["total_failed"] == 1
    assert len(failed_summary["recent_failures"]) == 1
    assert failed_summary["recent_failures"][0]["error_code"] == "smtp_auth_failed"

    # 3. Test retry functionality
    retried = retry_outbox_message(session, failed_msg.tenant_id, failed_msg.id)
    session.commit()
    assert retried.state == OutboxState.PENDING
    assert retried.attempts == 0
    assert retried.error_code is None
