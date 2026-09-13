import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.notifications.models import NotificationOutbox, OutboxState
from conformly.notifications.service import decrypt_notification_payload

logger = structlog.get_logger(__name__)

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


_RUNNING = True


def _handle_signal(signum: int, frame: Any) -> None:
    global _RUNNING
    logger.info("notification_worker_stopping", signal=signum)
    _RUNNING = False


def run_worker_tick(
    session_factory: sessionmaker[Session],
    codec: EncryptedFieldCodec,
    provider: NotificationProvider,
    *,
    now: datetime | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    run_compliance: bool = False,
) -> dict[str, Any]:
    """Execute one worker tick delivering outbox messages and optionally triggering compliance/retention jobs."""
    current_time = now or datetime.now(UTC)

    with session_factory() as session:
        batch_result = process_notification_batch(
            session,
            codec,
            provider,
            now=current_time,
            batch_size=batch_size,
        )
        session.commit()

    summary: dict[str, Any] = {
        "claimed": batch_result.claimed,
        "delivered": batch_result.delivered,
        "retried": batch_result.retried,
        "failed": batch_result.failed,
        "executed_at": current_time.isoformat(),
        "compliance_run": False,
    }

    if run_compliance:
        try:
            from conformly.compliance.worker import run_compliance_worker_tick
            from conformly.crypto.envelope import get_envelope_encryption_service
            from conformly.identity.models import Tenant, TenantStatus
            from conformly.retention.jobs import run_retention_lifecycle
            from conformly.storage.providers import get_storage_provider
            from conformly.storage.service import StorageService

            compliance_summary = run_compliance_worker_tick(
                session_factory,
                codec,
                notification_provider=provider,
                now=current_time,
            )
            with session_factory() as retention_session:
                storage_svc = StorageService(
                    session=retention_session,
                    storage_provider=get_storage_provider(),
                    encryption_service=get_envelope_encryption_service(),
                )
                cancelling_tenants = retention_session.scalars(
                    select(Tenant.id).where(
                        Tenant.status.in_([TenantStatus.CANCELLING, TenantStatus.SUSPENDED])
                    )
                ).all()
                suspended_total = 0
                completed_total = 0
                held_total = 0
                failed_total = 0
                for tid in cancelling_tenants:
                    res = run_retention_lifecycle(
                        retention_session,
                        storage_svc,
                        tenant_id=tid,
                        now=current_time,
                    )
                    suspended_total += res.suspended_tenants
                    completed_total += res.completed_deletions
                    held_total += res.held_deletions
                    failed_total += res.failed_deletions
                retention_session.commit()
                retention_summary = {
                    "tenants_checked": len(cancelling_tenants),
                    "suspended_tenants": suspended_total,
                    "completed_deletions": completed_total,
                    "held_deletions": held_total,
                    "failed_deletions": failed_total,
                }

            summary["compliance_run"] = True
            summary["compliance_summary"] = compliance_summary
            summary["retention_summary"] = retention_summary
        except Exception as error:
            logger.error("worker_compliance_cycle_error", error=str(error))
            summary["compliance_error"] = str(error)

    if batch_result.claimed > 0 or summary["compliance_run"]:
        logger.info("worker_tick_completed", **summary)

    return summary


def run_worker_loop(
    session_factory: sessionmaker[Session],
    codec: EncryptedFieldCodec,
    provider: NotificationProvider,
    *,
    poll_interval: float = 5.0,
    compliance_interval: int = 3600,
    batch_size: int = DEFAULT_BATCH_SIZE,
    once: bool = False,
) -> None:
    """Continuous worker execution loop with signal handling and periodic compliance checks."""
    import time

    global _RUNNING
    _RUNNING = True

    logger.info(
        "notification_worker_started",
        poll_interval=poll_interval,
        compliance_interval=compliance_interval,
        batch_size=batch_size,
        once=once,
    )

    last_compliance_time = 0.0

    while _RUNNING:
        current_monotonic = time.monotonic()
        run_compliance = (current_monotonic - last_compliance_time) >= compliance_interval

        run_worker_tick(
            session_factory,
            codec,
            provider,
            batch_size=batch_size,
            run_compliance=run_compliance,
        )

        if run_compliance:
            last_compliance_time = current_monotonic

        if once or not _RUNNING:
            break

        sleep_until = time.monotonic() + poll_interval
        while _RUNNING and time.monotonic() < sleep_until:
            time.sleep(0.2)

    logger.info("notification_worker_exited_cleanly")


def main() -> None:
    import argparse
    import signal
    import sys

    from conformly.config import get_settings
    from conformly.crypto.fields import get_encrypted_field_codec
    from conformly.db.session import SessionLocal
    from conformly.notifications.providers import get_notification_provider

    settings = get_settings()

    parser = argparse.ArgumentParser(
        description="Conformly Background Notification and Compliance Worker"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=settings.worker_poll_interval_seconds,
        help="Seconds between outbox polling ticks (default: 5.0)",
    )
    parser.add_argument(
        "--compliance-interval",
        type=int,
        default=settings.worker_compliance_interval_seconds,
        help="Seconds between continuous compliance cycles (default: 3600)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=settings.worker_batch_size,
        help="Max notification messages processed per tick (default: 25)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process a single tick and exit immediately",
    )
    parser.add_argument(
        "--celery",
        action="store_true",
        help="Launch the Celery worker process instead of the standalone polling loop",
    )

    args = parser.parse_args()

    if args.celery:
        logger.info("launching_celery_worker")
        from conformly.jobs.celery import celery_app

        celery_app.worker_main(argv=["worker", "--loglevel=info"])
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    codec = get_encrypted_field_codec()
    provider = get_notification_provider(settings)

    run_worker_loop(
        SessionLocal,
        codec,
        provider,
        poll_interval=args.interval,
        compliance_interval=args.compliance_interval,
        batch_size=args.batch_size,
        once=args.once,
    )


if __name__ == "__main__":
    main()
