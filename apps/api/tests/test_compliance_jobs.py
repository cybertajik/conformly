from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.compliance.jobs import (
    run_evidence_expiration_check,
    run_overdue_tasks_check,
    run_policy_review_alerts,
)
from conformly.compliance.models import (
    ComplianceTask,
    EvidenceItem,
    EvidenceStatus,
    Policy,
    PolicyStatus,
    TaskStatus,
)
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.identity.models import Tenant, TenantStatus, User, UserStatus
from conformly.notifications.models import NotificationOutbox


def create_tenant_and_user(session: Session) -> tuple[Tenant, User]:
    tenant_id = uuid4()
    tenant = Tenant(
        id=tenant_id,
        slug=f"tenant-{tenant_id.hex[:6]}",
        name=f"Tenant {tenant_id.hex[:6]}",
        status=TenantStatus.ACTIVE,
    )
    user_id = uuid4()
    user = User(
        id=user_id,
        oidc_issuer="https://issuer.example.com",
        oidc_subject=f"sub-{user_id.hex[:8]}",
        email=f"user-{user_id.hex[:8]}@example.com",
        display_name=f"User {user_id.hex[:6]}",
        status=UserStatus.ACTIVE,
    )
    session.add_all([tenant, user])
    session.flush()
    return tenant, user


def test_run_evidence_expiration_job_is_idempotent(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    tenant, user = create_tenant_and_user(session)
    now = datetime.now(UTC)

    # 1. Evidence that has expired (valid_until in the past)
    expired_evidence = EvidenceItem(
        tenant_id=tenant.id,
        title="Old SOC2 Evidence",
        description="Expired certificate",
        classification="Internal",
        status=EvidenceStatus.VALID,
        owner_user_id=user.id,
        valid_until=now - timedelta(days=2),
        version=1,
    )
    # 2. Evidence that is still valid (valid_until in the future)
    active_evidence = EvidenceItem(
        tenant_id=tenant.id,
        title="Current SOC2 Evidence",
        description="Active certificate",
        classification="Internal",
        status=EvidenceStatus.VALID,
        owner_user_id=user.id,
        valid_until=now + timedelta(days=60),
        version=1,
    )
    session.add_all([expired_evidence, active_evidence])
    session.flush()

    # First run of job
    res1 = run_evidence_expiration_check(session, test_codec, tenant_id=tenant.id, now=now)
    assert res1.processed_count == 1
    assert res1.alerts_enqueued == 1

    session.refresh(expired_evidence)
    session.refresh(active_evidence)
    assert expired_evidence.status == EvidenceStatus.EXPIRED
    assert active_evidence.status == EvidenceStatus.VALID

    # Check notification outbox
    outbox_entries = list(
        session.scalars(select(NotificationOutbox).where(NotificationOutbox.tenant_id == tenant.id))
    )
    assert len(outbox_entries) == 1
    assert outbox_entries[0].kind == "evidence.expired"

    # Second run of job (idempotent: no new items processed, no new alerts)
    res2 = run_evidence_expiration_check(session, test_codec, tenant_id=tenant.id, now=now)
    assert res2.processed_count == 0
    assert res2.alerts_enqueued == 0

    outbox_entries_after = list(
        session.scalars(select(NotificationOutbox).where(NotificationOutbox.tenant_id == tenant.id))
    )
    assert len(outbox_entries_after) == 1


def test_run_overdue_tasks_job_is_idempotent(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    tenant, user = create_tenant_and_user(session)
    now = datetime.now(UTC)

    # Task with past due_date
    past_task = ComplianceTask(
        tenant_id=tenant.id,
        title="Overdue Audit Task",
        description="Must be completed",
        due_date=now - timedelta(days=1),
        status=TaskStatus.PENDING,
        version=1,
    )
    # Task with future due_date
    future_task = ComplianceTask(
        tenant_id=tenant.id,
        title="Future Task",
        description="Upcoming task",
        due_date=now + timedelta(days=10),
        status=TaskStatus.PENDING,
        version=1,
    )
    session.add_all([past_task, future_task])
    session.flush()

    res1 = run_overdue_tasks_check(session, test_codec, tenant_id=tenant.id, now=now)
    assert res1.processed_count == 1
    assert res1.alerts_enqueued == 1

    session.refresh(past_task)
    session.refresh(future_task)
    assert past_task.status == TaskStatus.OVERDUE
    assert future_task.status == TaskStatus.PENDING

    # Second run: idempotent
    res2 = run_overdue_tasks_check(session, test_codec, tenant_id=tenant.id, now=now)
    assert res2.processed_count == 0
    assert res2.alerts_enqueued == 0


def test_run_policy_review_alerts_is_idempotent(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    tenant, user = create_tenant_and_user(session)
    now = datetime.now(UTC)

    # Policy due for review in 10 days
    policy_due = Policy(
        tenant_id=tenant.id,
        title="Access Control Policy",
        description="Review needed",
        status=PolicyStatus.PUBLISHED,
        owner_user_id=user.id,
        next_review_due=now + timedelta(days=10),
        version=1,
    )
    # Policy due for review in 100 days
    policy_far = Policy(
        tenant_id=tenant.id,
        title="Remote Work Policy",
        description="Review not needed yet",
        status=PolicyStatus.PUBLISHED,
        owner_user_id=user.id,
        next_review_due=now + timedelta(days=100),
        version=1,
    )
    session.add_all([policy_due, policy_far])
    session.flush()

    res1 = run_policy_review_alerts(
        session, test_codec, tenant_id=tenant.id, now=now, horizon_days=30
    )
    assert res1.processed_count == 1
    assert res1.alerts_enqueued == 1

    # Second run: policy is found, but outbox alert is deduplicated by idempotency key!
    res2 = run_policy_review_alerts(
        session, test_codec, tenant_id=tenant.id, now=now, horizon_days=30
    )
    assert res2.processed_count == 1
    assert res2.alerts_enqueued == 0
