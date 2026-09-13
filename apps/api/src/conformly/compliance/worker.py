import argparse
import signal
import sys
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from conformly.compliance.automation import (
    ContinuousComplianceResult,
    run_continuous_compliance_cycle,
)
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.db.session import SessionLocal
from conformly.identity.models import Tenant, TenantStatus
from conformly.notifications.worker import NotificationProvider, process_notification_batch

logger = structlog.get_logger(__name__)

_RUNNING = True


def _handle_signal(signum: int, frame: Any) -> None:
    global _RUNNING
    logger.info("compliance_worker_stopping", signal=signum)
    _RUNNING = False


def run_compliance_worker_tick(
    session_factory: sessionmaker[Session],
    codec: EncryptedFieldCodec,
    *,
    notification_provider: NotificationProvider | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Execute one full tick of continuous compliance monitoring across all active tenants."""
    current_time = now or datetime.now(UTC)

    # 1. Enumerate active tenant IDs from privileged control-plane context
    with session_factory() as control_session:
        active_tenant_ids: list[UUID] = list(
            control_session.scalars(select(Tenant.id).where(Tenant.status == TenantStatus.ACTIVE))
        )

    results: list[ContinuousComplianceResult] = []
    total_tasks_created = 0
    total_alerts_enqueued = 0

    # 2. Process each tenant in an isolated session & RLS scope
    for tenant_id in active_tenant_ids:
        try:
            with session_factory() as session:
                cycle_result = run_continuous_compliance_cycle(
                    session,
                    codec,
                    tenant_id=tenant_id,
                    now=current_time,
                )
                session.commit()
                results.append(cycle_result)
                total_tasks_created += cycle_result.tasks_created
                total_alerts_enqueued += cycle_result.notifications_enqueued
        except Exception as error:
            logger.error(
                "compliance_cycle_tenant_error",
                tenant_id=str(tenant_id),
                error=str(error),
            )

    # 3. Process pending notification delivery outbox if provider is available
    notifications_delivered = 0
    if notification_provider is not None:
        try:
            with session_factory() as session:
                delivery_result = process_notification_batch(
                    session,
                    codec,
                    notification_provider,
                    now=current_time,
                )
                session.commit()
                notifications_delivered = delivery_result.delivered
        except Exception as error:
            logger.error("notification_batch_delivery_error", error=str(error))

    summary = {
        "tenants_checked": len(active_tenant_ids),
        "total_tasks_created": total_tasks_created,
        "total_alerts_enqueued": total_alerts_enqueued,
        "notifications_delivered": notifications_delivered,
        "executed_at": current_time.isoformat(),
    }
    logger.info("compliance_worker_tick_completed", **summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Conformly Continuous Compliance Background Worker"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Seconds between continuous compliance cycles (default: 3600)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single cycle and exit immediately",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    codec = get_encrypted_field_codec()
    logger.info(
        "compliance_worker_started",
        interval=args.interval,
        once=args.once,
    )

    if args.once:
        run_compliance_worker_tick(SessionLocal, codec)
        sys.exit(0)

    while _RUNNING:
        run_compliance_worker_tick(SessionLocal, codec)
        for _ in range(args.interval):
            if not _RUNNING:
                break
            time.sleep(1)

    logger.info("compliance_worker_exited_cleanly")


if __name__ == "__main__":
    main()
