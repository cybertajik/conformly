import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.notifications.models import NotificationOutbox, OutboxState
from conformly.notifications.service import decrypt_notification_payload

DEFAULT_BATCH_SIZE = 25
MAX_DELIVERY_ATTEMPTS = 5
BASE_RETRY_DELAY = timedelta(minutes=1)
MAX_RETRY_DELAY = timedelta(hours=1)


class NotificationDeliveryError(Exception):
    """Provider failure containing a safe code and retry classification only."""

    def __init__(self, error_code: str, *, retryable: bool = True) -> None:
        safe_error_code = (
            error_code if re.fullmatch(r"[a-z0-9_]{1,80}", error_code) else "provider_error"
        )
        super().__init__(safe_error_code)
        self.error_code = safe_error_code
        self.retryable = retryable


class NotificationProvider(Protocol):
    def deliver(
        self,
        *,
        kind: str,
        payload: dict[str, str],
        idempotency_key: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class DeliveryBatchResult:
    claimed: int
    delivered: int
    retried: int
    failed: int


def retry_delay(attempt: int) -> timedelta:
    bounded_attempt = max(min(attempt, 7), 1)
    delay = BASE_RETRY_DELAY * (2 ** (bounded_attempt - 1))
    return MAX_RETRY_DELAY if delay > MAX_RETRY_DELAY else delay


def _audit_delivery(
    session: Session,
    message: NotificationOutbox,
    *,
    outcome: AuditOutcome,
    metadata: dict[str, object],
) -> None:
    record_audit_event(
        session,
        tenant_id=message.tenant_id,
        actor_type=AuditActorType.SYSTEM,
        actor_id=None,
        action="notification.deliver",
        resource_type="notification_outbox",
        resource_id=str(message.id),
        request_id=f"job:{message.id}:{message.attempts}",
        outcome=outcome,
        metadata=metadata,
    )


def process_notification_batch(
    session: Session,
    codec: EncryptedFieldCodec,
    provider: NotificationProvider,
    *,
    now: datetime | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> DeliveryBatchResult:
    current_time = now or datetime.now(UTC)
    statement = (
        select(NotificationOutbox)
        .where(
            NotificationOutbox.state == OutboxState.PENDING,
            NotificationOutbox.available_at <= current_time,
        )
        .order_by(NotificationOutbox.available_at, NotificationOutbox.id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    messages = list(session.scalars(statement))
    delivered = 0
    retried = 0
    failed = 0

    for message in messages:
        message.state = OutboxState.PROCESSING
        message.attempts += 1
        session.flush()
        try:
            payload = decrypt_notification_payload(codec, message)
            provider.deliver(
                kind=message.kind,
                payload=payload,
                idempotency_key=message.idempotency_key,
            )
        except NotificationDeliveryError as error:
            message.error_code = error.error_code[:80]
            if error.retryable and message.attempts < MAX_DELIVERY_ATTEMPTS:
                message.state = OutboxState.PENDING
                message.available_at = current_time + retry_delay(message.attempts)
                retried += 1
            else:
                message.state = OutboxState.FAILED
                failed += 1
            _audit_delivery(
                session,
                message,
                outcome=AuditOutcome.FAILURE,
                metadata={
                    "attempt": message.attempts,
                    "error_code": message.error_code,
                    "will_retry": message.state is OutboxState.PENDING,
                },
            )
        except Exception as error:
            raise RuntimeError("notification provider raised an unsafe exception") from error
        else:
            message.state = OutboxState.DELIVERED
            message.delivered_at = current_time
            message.error_code = None
            delivered += 1
            _audit_delivery(
                session,
                message,
                outcome=AuditOutcome.SUCCESS,
                metadata={"attempt": message.attempts},
            )
        session.flush()

    return DeliveryBatchResult(
        claimed=len(messages),
        delivered=delivered,
        retried=retried,
        failed=failed,
    )
