from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.compliance.models import (
    ComplianceTask,
    EvidenceItem,
    EvidenceStatus,
    Policy,
    PolicyStatus,
    TaskStatus,
)
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.notifications.models import NotificationOutbox
from conformly.notifications.service import enqueue_encrypted_notification


@dataclass(frozen=True, slots=True)
class ComplianceJobResult:
    processed_count: int
    alerts_enqueued: int


def run_evidence_expiration_check(
    session: Session,
    codec: EncryptedFieldCodec,
    *,
    tenant_id: UUID | None = None,
    now: datetime | None = None,
) -> ComplianceJobResult:
    """Deterministic job that expires valid evidence past its valid_until date."""
    current_time = now or datetime.now(UTC)
    query = select(EvidenceItem).where(
        EvidenceItem.status == EvidenceStatus.VALID,
        EvidenceItem.valid_until <= current_time,
    )
    if tenant_id:
        query = query.where(EvidenceItem.tenant_id == tenant_id)

    expired_items = list(session.scalars(query.order_by(EvidenceItem.valid_until)))
    alerts = 0

    for item in expired_items:
        previous_status = item.status
        item.status = EvidenceStatus.EXPIRED
        item.version += 1
        session.flush()

        record_audit_event(
            session,
            tenant_id=item.tenant_id,
            actor_type=AuditActorType.SYSTEM,
            actor_id=None,
            action="evidence.expire",
            resource_type="evidence_item",
            resource_id=str(item.id),
            request_id=f"job:evidence_expire:{item.id}:{item.version}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "evidence_id": str(item.id),
                "previous_status": previous_status,
                "status": item.status,
                "version_number": item.version,
            },
        )

        valid_until_date = item.valid_until.date().isoformat() if item.valid_until else "unknown"
        idempotency_ref = f"evidence_expired:{item.id}:{valid_until_date}"

        exists = session.scalar(
            select(NotificationOutbox).where(NotificationOutbox.idempotency_key == idempotency_ref)
        )
        if not exists:
            enqueue_encrypted_notification(
                session,
                codec,
                message_id=uuid4(),
                tenant_id=item.tenant_id,
                kind="evidence.expired",
                idempotency_key=idempotency_ref,
                payload={
                    "evidence_id": str(item.id),
                    "title": item.title,
                    "valid_until": valid_until_date,
                    "event": "evidence_expired",
                },
                available_at=current_time,
            )
            alerts += 1

    return ComplianceJobResult(processed_count=len(expired_items), alerts_enqueued=alerts)


def run_overdue_tasks_check(
    session: Session,
    codec: EncryptedFieldCodec,
    *,
    tenant_id: UUID | None = None,
    now: datetime | None = None,
) -> ComplianceJobResult:
    """Deterministic job that flags pending/in_progress tasks past their due_date as overdue."""
    current_time = now or datetime.now(UTC)
    query = select(ComplianceTask).where(
        ComplianceTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
        ComplianceTask.due_date < current_time,
    )
    if tenant_id:
        query = query.where(ComplianceTask.tenant_id == tenant_id)

    overdue_tasks = list(session.scalars(query.order_by(ComplianceTask.due_date)))
    alerts = 0

    for task in overdue_tasks:
        previous_status = task.status
        task.status = TaskStatus.OVERDUE
        task.version += 1
        session.flush()

        record_audit_event(
            session,
            tenant_id=task.tenant_id,
            actor_type=AuditActorType.SYSTEM,
            actor_id=None,
            action="task.overdue",
            resource_type="compliance_task",
            resource_id=str(task.id),
            request_id=f"job:task_overdue:{task.id}:{task.version}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "task_id": str(task.id),
                "previous_status": previous_status,
                "status": task.status,
                "version_number": task.version,
            },
        )

        due_date_str = task.due_date.date().isoformat()
        idempotency_ref = f"task_overdue:{task.id}:{due_date_str}"

        exists = session.scalar(
            select(NotificationOutbox).where(NotificationOutbox.idempotency_key == idempotency_ref)
        )
        if not exists:
            enqueue_encrypted_notification(
                session,
                codec,
                message_id=uuid4(),
                tenant_id=task.tenant_id,
                kind="task.overdue",
                idempotency_key=idempotency_ref,
                payload={
                    "task_id": str(task.id),
                    "title": task.title,
                    "due_date": due_date_str,
                    "priority": task.priority,
                    "event": "task_overdue",
                },
                available_at=current_time,
            )
            alerts += 1

    return ComplianceJobResult(processed_count=len(overdue_tasks), alerts_enqueued=alerts)


def run_policy_review_alerts(
    session: Session,
    codec: EncryptedFieldCodec,
    *,
    tenant_id: UUID | None = None,
    now: datetime | None = None,
    horizon_days: int = 30,
) -> ComplianceJobResult:
    """Deterministic job that enqueues reminders for published policies approaching review."""
    current_time = now or datetime.now(UTC)
    cutoff_time = current_time + timedelta(days=horizon_days)

    query = select(Policy).where(
        Policy.status == PolicyStatus.PUBLISHED,
        Policy.next_review_due.is_not(None),
        Policy.next_review_due <= cutoff_time,
    )
    if tenant_id:
        query = query.where(Policy.tenant_id == tenant_id)

    policies = list(session.scalars(query.order_by(Policy.next_review_due)))
    alerts = 0

    for policy in policies:
        if not policy.next_review_due:
            continue
        due_date_str = policy.next_review_due.date().isoformat()
        idempotency_ref = f"policy_review:{policy.id}:{due_date_str}"

        exists = session.scalar(
            select(NotificationOutbox).where(NotificationOutbox.idempotency_key == idempotency_ref)
        )
        if not exists:
            enqueue_encrypted_notification(
                session,
                codec,
                message_id=uuid4(),
                tenant_id=policy.tenant_id,
                kind="policy.review_due",
                idempotency_key=idempotency_ref,
                payload={
                    "policy_id": str(policy.id),
                    "title": policy.title,
                    "version_string": policy.version_string,
                    "next_review_due": due_date_str,
                    "event": "policy_review_due",
                },
                available_at=current_time,
            )
            alerts += 1

    return ComplianceJobResult(processed_count=len(policies), alerts_enqueued=alerts)
