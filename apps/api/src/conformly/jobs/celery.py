"""Celery application and asynchronous background task definitions for Conformly.

Handles:
1. Transactional outbox notification delivery (SMTP & Webhook) with exponential backoff.
2. Recurring continuous compliance cycle evaluation across active tenants.
3. Retention lifecycle sweeps (data exit windows, legal hold enforcement, 90-day purge).
"""

import logging
from typing import Any

from celery import Celery  # type: ignore[import-untyped]
from celery.schedules import crontab  # type: ignore[import-untyped]
from sqlalchemy import select

from conformly.config import get_settings
from conformly.crypto.fields import get_encrypted_field_codec
from conformly.db.session import SessionLocal

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "conformly",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    beat_schedule={
        "deliver-notifications-every-10s": {
            "task": "conformly.deliver_notifications",
            "schedule": 10.0,
        },
        "continuous-compliance-cycle-hourly": {
            "task": "conformly.continuous_compliance_cycle",
            "schedule": float(settings.worker_compliance_interval_seconds),
        },
        "retention-sweep-daily": {
            "task": "conformly.retention_sweep",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)


@celery_app.task(name="conformly.deliver_notifications", bind=True, max_retries=3)  # type: ignore[untyped-decorator]
def deliver_notifications_task(self: Any, batch_size: int = 25) -> dict[str, int]:
    """Celery task to deliver a batch of pending encrypted notifications from the outbox."""
    from conformly.notifications.providers import get_notification_provider
    from conformly.notifications.worker import process_notification_batch

    codec = get_encrypted_field_codec()
    provider = get_notification_provider(settings)

    with SessionLocal() as session:
        result = process_notification_batch(
            session,
            codec,
            provider,
            batch_size=batch_size,
        )
        session.commit()
        return {
            "claimed": result.claimed,
            "delivered": result.delivered,
            "retried": result.retried,
            "failed": result.failed,
        }


@celery_app.task(name="conformly.continuous_compliance_cycle", bind=True)  # type: ignore[untyped-decorator]
def continuous_compliance_cycle_task(self: Any) -> dict[str, Any]:
    """Celery task executing continuous compliance automation across all active tenants."""
    from conformly.compliance.worker import run_compliance_worker_tick
    from conformly.notifications.providers import get_notification_provider

    codec = get_encrypted_field_codec()
    provider = get_notification_provider(settings)

    return run_compliance_worker_tick(
        SessionLocal,
        codec,
        notification_provider=provider,
    )


@celery_app.task(name="conformly.retention_sweep", bind=True)  # type: ignore[untyped-decorator]
def retention_sweep_task(self: Any) -> dict[str, Any]:
    """Celery task executing retention lifecycle and automated deletion sweeps."""
    from conformly.crypto.envelope import get_envelope_encryption_service
    from conformly.identity.models import Tenant, TenantStatus
    from conformly.retention.jobs import run_retention_lifecycle
    from conformly.storage.providers import get_storage_provider
    from conformly.storage.service import StorageService

    with SessionLocal() as session:
        storage_svc = StorageService(
            session=session,
            storage_provider=get_storage_provider(),
            encryption_service=get_envelope_encryption_service(),
        )
        cancelling_tenants = session.scalars(
            select(Tenant.id).where(
                Tenant.status.in_([TenantStatus.CANCELLING, TenantStatus.SUSPENDED])
            )
        ).all()
        suspended_total = 0
        completed_total = 0
        held_total = 0
        failed_total = 0
        for tid in cancelling_tenants:
            res = run_retention_lifecycle(session, storage_svc, tenant_id=tid)
            suspended_total += res.suspended_tenants
            completed_total += res.completed_deletions
            held_total += res.held_deletions
            failed_total += res.failed_deletions
        session.commit()
        return {
            "tenants_checked": len(cancelling_tenants),
            "suspended_tenants": suspended_total,
            "completed_deletions": completed_total,
            "held_deletions": held_total,
            "failed_deletions": failed_total,
        }
