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
    TaskPriority,
    TaskStatus,
)
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.notifications.models import NotificationOutbox
from conformly.notifications.service import enqueue_encrypted_notification
from conformly.tenancy.rls import set_system_tenant_rls_context
from conformly.vendors.models import Vendor, VendorCriticality, VendorStatus


@dataclass(frozen=True, slots=True)
class ContinuousComplianceResult:
    tenant_id: UUID
    expired_evidence_count: int
    expiring_evidence_warnings: int
    overdue_tasks_escalated: int
    policy_reviews_due: int
    vendor_reviews_due: int
    missing_dpas_flagged: int
    tasks_created: int
    notifications_enqueued: int
    executed_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "tenant_id": str(self.tenant_id),
            "expired_evidence_count": self.expired_evidence_count,
            "expiring_evidence_warnings": self.expiring_evidence_warnings,
            "overdue_tasks_escalated": self.overdue_tasks_escalated,
            "policy_reviews_due": self.policy_reviews_due,
            "vendor_reviews_due": self.vendor_reviews_due,
            "missing_dpas_flagged": self.missing_dpas_flagged,
            "tasks_created": self.tasks_created,
            "notifications_enqueued": self.notifications_enqueued,
            "executed_at": self.executed_at.isoformat(),
        }


def _has_active_task_for_evidence(session: Session, tenant_id: UUID, evidence_id: UUID) -> bool:
    statement = select(ComplianceTask.id).where(
        ComplianceTask.tenant_id == tenant_id,
        ComplianceTask.evidence_id == evidence_id,
        ComplianceTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.OVERDUE]),
    )
    return session.scalar(statement) is not None


def _has_active_task_for_policy(session: Session, tenant_id: UUID, policy_id: UUID) -> bool:
    statement = select(ComplianceTask.id).where(
        ComplianceTask.tenant_id == tenant_id,
        ComplianceTask.policy_id == policy_id,
        ComplianceTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.OVERDUE]),
    )
    return session.scalar(statement) is not None


def _has_active_task_by_title_prefix(
    session: Session, tenant_id: UUID, title_prefix: str
) -> bool:
    statement = select(ComplianceTask.id).where(
        ComplianceTask.tenant_id == tenant_id,
        ComplianceTask.title.startswith(title_prefix),
        ComplianceTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.OVERDUE]),
    )
    return session.scalar(statement) is not None


def check_expiring_evidence(
    session: Session,
    codec: EncryptedFieldCodec,
    tenant_id: UUID,
    now: datetime,
    horizon_days: int = 30,
) -> tuple[int, int, int]:
    """Flag evidence expiring within horizon_days, enqueue advance warning, and create task."""
    cutoff = now + timedelta(days=horizon_days)
    query = select(EvidenceItem).where(
        EvidenceItem.tenant_id == tenant_id,
        EvidenceItem.status == EvidenceStatus.VALID,
        EvidenceItem.valid_until.is_not(None),
        EvidenceItem.valid_until > now,
        EvidenceItem.valid_until <= cutoff,
    )
    items = list(session.scalars(query.order_by(EvidenceItem.valid_until)))
    warnings_count = len(items)
    alerts_enqueued = 0
    tasks_created = 0

    for item in items:
        if not item.valid_until:
            continue
        valid_until_str = item.valid_until.date().isoformat()
        idempotency_ref = f"evidence_expiring_soon:{item.id}:{valid_until_str}"

        exists = session.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.idempotency_key == idempotency_ref
            )
        )
        if not exists:
            enqueue_encrypted_notification(
                session,
                codec,
                message_id=uuid4(),
                tenant_id=tenant_id,
                kind="evidence.expiring_soon",
                idempotency_key=idempotency_ref,
                payload={
                    "evidence_id": str(item.id),
                    "title": item.title,
                    "valid_until": valid_until_str,
                    "event": "evidence_expiring_soon",
                },
                available_at=now,
            )
            alerts_enqueued += 1

        if not _has_active_task_for_evidence(session, tenant_id, item.id):
            task = ComplianceTask(
                id=uuid4(),
                tenant_id=tenant_id,
                title=f"Renew Expiring Evidence: {item.title}",
                description=f"Evidence '{item.title}' is valid until {valid_until_str}. Please collect updated evidence before it expires.",
                due_date=item.valid_until,
                priority=TaskPriority.HIGH,
                status=TaskStatus.PENDING,
                assignee_user_id=item.owner_user_id,
                evidence_id=item.id,
                version=1,
            )
            session.add(task)
            session.flush()
            tasks_created += 1

    return warnings_count, alerts_enqueued, tasks_created


def enforce_expired_evidence(
    session: Session,
    codec: EncryptedFieldCodec,
    tenant_id: UUID,
    now: datetime,
) -> tuple[int, int, int]:
    """Transition past-validity evidence to EXPIRED, enqueue notification, and ensure task exists."""
    query = select(EvidenceItem).where(
        EvidenceItem.tenant_id == tenant_id,
        EvidenceItem.status == EvidenceStatus.VALID,
        EvidenceItem.valid_until.is_not(None),
        EvidenceItem.valid_until <= now,
    )
    items = list(session.scalars(query.order_by(EvidenceItem.valid_until)))
    expired_count = len(items)
    alerts_enqueued = 0
    tasks_created = 0

    for item in items:
        previous_status = str(item.status)
        item.status = EvidenceStatus.EXPIRED
        item.version += 1
        session.flush()

        record_audit_event(
            session,
            tenant_id=tenant_id,
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
                "status": str(item.status),
                "version_number": item.version,
            },
            occurred_at=now,
        )

        valid_until_str = (
            item.valid_until.date().isoformat() if item.valid_until else "unknown"
        )
        idempotency_ref = f"evidence_expired:{item.id}:{valid_until_str}"

        exists = session.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.idempotency_key == idempotency_ref
            )
        )
        if not exists:
            enqueue_encrypted_notification(
                session,
                codec,
                message_id=uuid4(),
                tenant_id=tenant_id,
                kind="evidence.expired",
                idempotency_key=idempotency_ref,
                payload={
                    "evidence_id": str(item.id),
                    "title": item.title,
                    "valid_until": valid_until_str,
                    "event": "evidence_expired",
                },
                available_at=now,
            )
            alerts_enqueued += 1

        if not _has_active_task_for_evidence(session, tenant_id, item.id):
            task = ComplianceTask(
                id=uuid4(),
                tenant_id=tenant_id,
                title=f"Replace Expired Evidence: {item.title}",
                description=f"Evidence '{item.title}' expired on {valid_until_str}. Controls relying on this evidence are now degraded.",
                due_date=now + timedelta(days=7),
                priority=TaskPriority.CRITICAL,
                status=TaskStatus.PENDING,
                assignee_user_id=item.owner_user_id,
                evidence_id=item.id,
                version=1,
            )
            session.add(task)
            session.flush()
            tasks_created += 1

    return expired_count, alerts_enqueued, tasks_created


def escalate_overdue_tasks(
    session: Session,
    codec: EncryptedFieldCodec,
    tenant_id: UUID,
    now: datetime,
) -> tuple[int, int]:
    """Transition pending/in_progress tasks past due_date to OVERDUE and enqueue alert."""
    query = select(ComplianceTask).where(
        ComplianceTask.tenant_id == tenant_id,
        ComplianceTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
        ComplianceTask.due_date < now,
    )
    tasks = list(session.scalars(query.order_by(ComplianceTask.due_date)))
    escalated_count = len(tasks)
    alerts_enqueued = 0

    for task in tasks:
        previous_status = str(task.status)
        task.status = TaskStatus.OVERDUE
        task.version += 1
        session.flush()

        record_audit_event(
            session,
            tenant_id=tenant_id,
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
                "status": str(task.status),
                "version_number": task.version,
            },
            occurred_at=now,
        )

        due_date_str = task.due_date.date().isoformat()
        idempotency_ref = f"task_overdue:{task.id}:{due_date_str}"

        exists = session.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.idempotency_key == idempotency_ref
            )
        )
        if not exists:
            enqueue_encrypted_notification(
                session,
                codec,
                message_id=uuid4(),
                tenant_id=tenant_id,
                kind="task.overdue",
                idempotency_key=idempotency_ref,
                payload={
                    "task_id": str(task.id),
                    "title": task.title,
                    "due_date": due_date_str,
                    "priority": str(task.priority),
                    "event": "task_overdue",
                },
                available_at=now,
            )
            alerts_enqueued += 1

    return escalated_count, alerts_enqueued


def check_policy_reviews(
    session: Session,
    codec: EncryptedFieldCodec,
    tenant_id: UUID,
    now: datetime,
    horizon_days: int = 30,
) -> tuple[int, int, int]:
    """Flag published policies due for annual review, enqueue alert, and create review task."""
    cutoff = now + timedelta(days=horizon_days)
    query = select(Policy).where(
        Policy.tenant_id == tenant_id,
        Policy.status == PolicyStatus.PUBLISHED,
        Policy.next_review_due.is_not(None),
        Policy.next_review_due <= cutoff,
    )
    policies = list(session.scalars(query.order_by(Policy.next_review_due)))
    reviews_due_count = len(policies)
    alerts_enqueued = 0
    tasks_created = 0

    for policy in policies:
        if not policy.next_review_due:
            continue
        due_date_str = policy.next_review_due.date().isoformat()
        idempotency_ref = f"policy_review:{policy.id}:{due_date_str}"

        exists = session.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.idempotency_key == idempotency_ref
            )
        )
        if not exists:
            enqueue_encrypted_notification(
                session,
                codec,
                message_id=uuid4(),
                tenant_id=tenant_id,
                kind="policy.review_due",
                idempotency_key=idempotency_ref,
                payload={
                    "policy_id": str(policy.id),
                    "title": policy.title,
                    "version_string": policy.version_string,
                    "next_review_due": due_date_str,
                    "event": "policy_review_due",
                },
                available_at=now,
            )
            alerts_enqueued += 1

        if not _has_active_task_for_policy(session, tenant_id, policy.id):
            task = ComplianceTask(
                id=uuid4(),
                tenant_id=tenant_id,
                title=f"Annual Policy Review: {policy.title}",
                description=f"Policy '{policy.title}' (v{policy.version_string}) is due for scheduled review on {due_date_str}.",
                due_date=policy.next_review_due,
                priority=TaskPriority.MEDIUM,
                status=TaskStatus.PENDING,
                assignee_user_id=policy.owner_user_id,
                policy_id=policy.id,
                version=1,
            )
            session.add(task)
            session.flush()
            tasks_created += 1

    return reviews_due_count, alerts_enqueued, tasks_created


def check_vendor_cadence(
    session: Session,
    codec: EncryptedFieldCodec,
    tenant_id: UUID,
    now: datetime,
    horizon_days: int = 30,
) -> tuple[int, int, int, int]:
    """Check vendor security review due dates and missing DPAs on critical vendors."""
    cutoff = now + timedelta(days=horizon_days)
    vendors = list(
        session.scalars(
            select(Vendor).where(
                Vendor.tenant_id == tenant_id,
                Vendor.status == VendorStatus.ACTIVE,
            )
        )
    )
    reviews_due_count = 0
    missing_dpas_count = 0
    alerts_enqueued = 0
    tasks_created = 0

    for vendor in vendors:
        # 1. Scheduled Security Review Cadence
        if vendor.next_review_due_at and vendor.next_review_due_at <= cutoff:
            reviews_due_count += 1
            due_str = vendor.next_review_due_at.date().isoformat()
            idempotency_ref = f"vendor_review:{vendor.id}:{due_str}"
            exists = session.scalar(
                select(NotificationOutbox).where(
                    NotificationOutbox.idempotency_key == idempotency_ref
                )
            )
            if not exists:
                enqueue_encrypted_notification(
                    session,
                    codec,
                    message_id=uuid4(),
                    tenant_id=tenant_id,
                    kind="vendor.review_due",
                    idempotency_key=idempotency_ref,
                    payload={
                        "vendor_id": str(vendor.id),
                        "name": vendor.name,
                        "criticality": str(vendor.criticality),
                        "next_review_due_at": due_str,
                        "event": "vendor_review_due",
                    },
                    available_at=now,
                )
                alerts_enqueued += 1

            task_prefix = f"Vendor Security Review: {vendor.name}"
            if not _has_active_task_by_title_prefix(session, tenant_id, task_prefix):
                priority = (
                    TaskPriority.HIGH
                    if vendor.criticality
                    in [VendorCriticality.HIGH, VendorCriticality.CRITICAL]
                    else TaskPriority.MEDIUM
                )
                task = ComplianceTask(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    title=task_prefix,
                    description=f"Annual security assessment due for vendor '{vendor.name}' ({vendor.criticality} criticality). Review SOC reports or ISO certificates.",
                    due_date=vendor.next_review_due_at,
                    priority=priority,
                    status=TaskStatus.PENDING,
                    version=1,
                )
                session.add(task)
                session.flush()
                tasks_created += 1

        # 2. Missing DPA check on High / Critical vendors
        if not vendor.dpa_signed and vendor.criticality in [
            VendorCriticality.HIGH,
            VendorCriticality.CRITICAL,
        ]:
            missing_dpas_count += 1
            idempotency_ref = f"vendor_missing_dpa:{vendor.id}"
            exists = session.scalar(
                select(NotificationOutbox).where(
                    NotificationOutbox.idempotency_key == idempotency_ref
                )
            )
            if not exists:
                enqueue_encrypted_notification(
                    session,
                    codec,
                    message_id=uuid4(),
                    tenant_id=tenant_id,
                    kind="vendor.missing_dpa",
                    idempotency_key=idempotency_ref,
                    payload={
                        "vendor_id": str(vendor.id),
                        "name": vendor.name,
                        "criticality": str(vendor.criticality),
                        "event": "vendor_missing_dpa",
                    },
                    available_at=now,
                )
                alerts_enqueued += 1

            dpa_task_prefix = f"Execute Missing DPA: {vendor.name}"
            if not _has_active_task_by_title_prefix(session, tenant_id, dpa_task_prefix):
                task = ComplianceTask(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    title=dpa_task_prefix,
                    description=f"Vendor '{vendor.name}' processes sensitive data under {vendor.criticality} criticality but has no executed DPA. Execute GDPR Art 28 DPA immediately.",
                    due_date=now + timedelta(days=14),
                    priority=TaskPriority.HIGH,
                    status=TaskStatus.PENDING,
                    version=1,
                )
                session.add(task)
                session.flush()
                tasks_created += 1

    return reviews_due_count, missing_dpas_count, alerts_enqueued, tasks_created


def run_continuous_compliance_cycle(
    session: Session,
    codec: EncryptedFieldCodec,
    *,
    tenant_id: UUID,
    now: datetime | None = None,
) -> ContinuousComplianceResult:
    """Execute complete deterministic continuous compliance automation for a single tenant.

    Enforces server-side tenant isolation with RLS context, evaluates all
    lifecycle boundaries, creates assigned remediation tasks, enqueues alerts,
    and records an audit event.
    """
    current_time = now or datetime.now(UTC)
    set_system_tenant_rls_context(session, tenant_id=tenant_id)

    # 1. Evidence advance warnings (<30 days)
    (
        exp_warn_count,
        exp_warn_alerts,
        exp_warn_tasks,
    ) = check_expiring_evidence(session, codec, tenant_id, current_time)

    # 2. Evidence expiration enforcement
    (
        expired_count,
        expired_alerts,
        expired_tasks,
    ) = enforce_expired_evidence(session, codec, tenant_id, current_time)

    # 3. Overdue tasks escalation
    (
        overdue_count,
        overdue_alerts,
    ) = escalate_overdue_tasks(session, codec, tenant_id, current_time)

    # 4. Policy annual review checks
    (
        policy_rev_count,
        policy_rev_alerts,
        policy_rev_tasks,
    ) = check_policy_reviews(session, codec, tenant_id, current_time)

    # 5. Vendor review cadence & DPA tracking
    (
        vendor_rev_count,
        missing_dpas_count,
        vendor_alerts,
        vendor_tasks,
    ) = check_vendor_cadence(session, codec, tenant_id, current_time)

    total_tasks_created = (
        exp_warn_tasks + expired_tasks + policy_rev_tasks + vendor_tasks
    )
    total_notifications = (
        exp_warn_alerts
        + expired_alerts
        + overdue_alerts
        + policy_rev_alerts
        + vendor_alerts
    )

    session.flush()

    # Emits audit event with SAFE_METADATA_KEYS only
    record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.SYSTEM,
        actor_id=None,
        action="compliance.continuous_cycle_executed",
        resource_type="compliance_cycle",
        resource_id=str(tenant_id),
        request_id=f"cycle:{tenant_id}:{current_time.strftime('%Y%m%d%H%M%S')}",
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "record_count": total_tasks_created,
            "count": total_notifications,
            "expired_count": expired_count,
            "overdue_count": overdue_count,
        },
        occurred_at=current_time,
    )

    return ContinuousComplianceResult(
        tenant_id=tenant_id,
        expired_evidence_count=expired_count,
        expiring_evidence_warnings=exp_warn_count,
        overdue_tasks_escalated=overdue_count,
        policy_reviews_due=policy_rev_count,
        vendor_reviews_due=vendor_rev_count,
        missing_dpas_flagged=missing_dpas_count,
        tasks_created=total_tasks_created,
        notifications_enqueued=total_notifications,
        executed_at=current_time,
    )
