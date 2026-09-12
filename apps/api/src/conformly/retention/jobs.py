from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.identity.models import Tenant, TenantStatus
from conformly.retention.models import DeletionJob, DeletionJobState
from conformly.retention.service import LegalHoldActiveError, RetentionService
from conformly.storage.service import StorageService
from conformly.tenancy.rls import set_system_tenant_rls_context


@dataclass(frozen=True, slots=True)
class RetentionJobResult:
    suspended_tenants: int
    completed_deletions: int
    held_deletions: int
    failed_deletions: int


def run_retention_lifecycle(
    session: Session,
    storage_service: StorageService,
    *,
    tenant_id: UUID,
    now: datetime | None = None,
) -> RetentionJobResult:
    """Advance one tenant's cancellation lifecycle deterministically.

    The caller must enumerate tenant IDs from a privileged control-plane source.
    Processing remains explicitly tenant-scoped so worker execution does not
    create a cross-tenant query path through application tables.
    """

    current_time = now or datetime.now(UTC)
    set_system_tenant_rls_context(session, tenant_id=tenant_id)

    tenant = session.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
    if tenant is None:
        return RetentionJobResult(0, 0, 0, 0)

    suspended = 0
    if (
        tenant.status == TenantStatus.CANCELLING
        and tenant.export_until is not None
        and _as_utc(tenant.export_until) < current_time
    ):
        tenant.status = TenantStatus.SUSPENDED
        session.flush()
        record_audit_event(
            session,
            tenant_id=tenant.id,
            actor_type=AuditActorType.SYSTEM,
            actor_id=None,
            action="tenant.export_window_closed",
            resource_type="tenant",
            resource_id=str(tenant.id),
            request_id=f"job:retention:suspend:{tenant.id}:{tenant.export_until.isoformat()}",
            outcome=AuditOutcome.SUCCESS,
            metadata={"reason": "export_window_elapsed"},
            occurred_at=current_time,
        )
        suspended = 1

    due_jobs = list(
        session.scalars(
            select(DeletionJob)
            .where(
                DeletionJob.tenant_id == tenant_id,
                DeletionJob.state.in_([DeletionJobState.SCHEDULED, DeletionJobState.ON_HOLD]),
                DeletionJob.scheduled_at <= current_time,
            )
            .order_by(DeletionJob.scheduled_at, DeletionJob.id)
        )
    )
    service = RetentionService(session, storage_service)
    completed = 0
    held = 0
    failed = 0
    for job in due_jobs:
        if job.state == DeletionJobState.ON_HOLD or tenant.legal_hold:
            held += 1
            continue
        try:
            service.execute_deletion_job(
                job.id,
                request_id=f"job:retention:delete:{job.id}",
                now=current_time,
            )
            completed += 1
        except LegalHoldActiveError:
            held += 1
        except Exception:
            failed += 1

    return RetentionJobResult(suspended, completed, held, failed)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
