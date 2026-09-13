"""Integration tests for background jobs and notification outbox visibility API.

Tests:
1. Failed-job summary and listing endpoints.
2. Role-based capability enforcement (Owner/Admin/Compliance Manager allowed, Reviewer/Employee denied).
3. Manual retry of failed outbox jobs.
4. Celery task definitions and scheduled task configurations.
"""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conformly.auth.dependencies import get_current_principal, get_tenant_context
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.db.session import get_db
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User
from conformly.main import app
from conformly.notifications.models import OutboxState
from conformly.notifications.service import enqueue_encrypted_notification


def make_test_codec() -> EncryptedFieldCodec:
    raw_key = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
    enc = EnvelopeEncryptionService(
        AES256GCMProvider(),
        LocalKeyManagementProvider({"v1": raw_key}, "v1"),
    )
    return EncryptedFieldCodec(enc)


def create_user_and_tenant(
    session: Session, role: Role = Role.OWNER
) -> tuple[User, Tenant, Principal, TenantContext]:
    tenant = Tenant(
        name="Jobs Test Tenant", slug=f"jobs-{uuid4().hex[:8]}", status=TenantStatus.ACTIVE
    )
    user = User(
        oidc_issuer="https://identity.conformly.de",
        oidc_subject=str(uuid4()),
        email=f"user-{uuid4().hex[:8]}@example.test",
        display_name="Jobs User",
    )
    session.add_all([tenant, user])
    session.flush()

    membership = Membership(
        tenant_id=tenant.id,
        user_id=user.id,
        role=role,
        status=MembershipStatus.ACTIVE,
    )
    session.add(membership)
    session.commit()

    principal = Principal(user_id=user.id, mfa_verified=True)
    context = TenantContext(tenant_id=tenant.id, user_id=user.id, role=role)
    return user, tenant, principal, context


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: session
    codec = make_test_codec()
    app.dependency_overrides[get_encrypted_field_codec] = lambda: codec
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_failed_jobs_endpoint_role_enforcement(session: Session, client: TestClient) -> None:
    # 1. Privileged role (COMPLIANCE_MANAGER) should succeed
    _, tenant, principal_cm, ctx_cm = create_user_and_tenant(session, role=Role.COMPLIANCE_MANAGER)
    app.dependency_overrides[get_current_principal] = lambda: principal_cm
    app.dependency_overrides[get_tenant_context] = lambda: ctx_cm

    resp = client.get(f"/v1/tenants/{tenant.id}/jobs/failed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == str(tenant.id)
    assert data["total_failed"] == 0

    # 2. Non-privileged role (EMPLOYEE) should be denied 403
    _, _, principal_emp, ctx_emp = create_user_and_tenant(session, role=Role.EMPLOYEE)
    app.dependency_overrides[get_current_principal] = lambda: principal_emp
    app.dependency_overrides[get_tenant_context] = lambda: ctx_emp

    resp_denied = client.get(f"/v1/tenants/{tenant.id}/jobs/failed")
    assert resp_denied.status_code == 403
    assert "Forbidden" in resp_denied.json()["detail"]


def test_failed_jobs_visibility_and_outbox_listing(session: Session, client: TestClient) -> None:
    _, tenant, principal, context = create_user_and_tenant(session, role=Role.ADMINISTRATOR)
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_tenant_context] = lambda: context

    codec = make_test_codec()
    now = datetime.now(UTC)

    # Enqueue a pending notification
    msg_pending = enqueue_encrypted_notification(
        session,
        codec,
        message_id=uuid4(),
        tenant_id=tenant.id,
        kind="compliance_task_reminder",
        idempotency_key=f"task-remind-{uuid4().hex[:8]}",
        payload={"email": "member@example.com", "task_title": "Annual Review"},
        available_at=now,
    )

    # Enqueue a failed notification
    msg_failed = enqueue_encrypted_notification(
        session,
        codec,
        message_id=uuid4(),
        tenant_id=tenant.id,
        kind="membership_invitation",
        idempotency_key=f"invite-{uuid4().hex[:8]}",
        payload={"email": "reject@example.com", "invitation_token": "secret"},
        available_at=now,
    )
    msg_failed.state = OutboxState.FAILED
    msg_failed.attempts = 5
    msg_failed.error_code = "recipient_refused"
    session.commit()

    # Query /failed endpoint
    resp_failed = client.get(f"/v1/tenants/{tenant.id}/jobs/failed")
    assert resp_failed.status_code == 200
    data_failed = resp_failed.json()
    assert data_failed["total_failed"] == 1
    assert data_failed["total_pending"] == 1
    assert len(data_failed["recent_failures"]) == 1
    assert data_failed["recent_failures"][0]["id"] == str(msg_failed.id)
    assert data_failed["recent_failures"][0]["error_code"] == "recipient_refused"

    # Query /outbox with filter state=pending
    resp_outbox_pending = client.get(f"/v1/tenants/{tenant.id}/jobs/outbox?state=pending")
    assert resp_outbox_pending.status_code == 200
    pending_list = resp_outbox_pending.json()
    assert len(pending_list) == 1
    assert pending_list[0]["id"] == str(msg_pending.id)

    # Query single outbox message
    resp_single = client.get(f"/v1/tenants/{tenant.id}/jobs/outbox/{msg_failed.id}")
    assert resp_single.status_code == 200
    assert resp_single.json()["error_code"] == "recipient_refused"


def test_retry_failed_outbox_job_endpoint(session: Session, client: TestClient) -> None:
    _, tenant, principal, context = create_user_and_tenant(session, role=Role.OWNER)
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_tenant_context] = lambda: context

    codec = make_test_codec()
    now = datetime.now(UTC)

    msg_failed = enqueue_encrypted_notification(
        session,
        codec,
        message_id=uuid4(),
        tenant_id=tenant.id,
        kind="policy_review_reminder",
        idempotency_key=f"policy-remind-{uuid4().hex[:8]}",
        payload={"email": "policy-mgr@example.com", "policy_title": "ISMS Security Policy"},
        available_at=now,
    )
    msg_failed.state = OutboxState.FAILED
    msg_failed.attempts = 5
    msg_failed.error_code = "smtp_connection_failed"
    session.commit()

    # Retry the failed job
    resp_retry = client.post(f"/v1/tenants/{tenant.id}/jobs/outbox/{msg_failed.id}/retry")
    assert resp_retry.status_code == 200
    data_retry = resp_retry.json()
    assert data_retry["state"] == "pending"
    assert data_retry["attempts"] == 0
    assert data_retry["error_code"] is None

    # Check database state
    session.refresh(msg_failed)
    assert msg_failed.state == OutboxState.PENDING
    assert msg_failed.attempts == 0
    assert msg_failed.error_code is None


def test_celery_task_definitions() -> None:
    from conformly.jobs.celery import (
        celery_app,
        continuous_compliance_cycle_task,
        deliver_notifications_task,
        retention_sweep_task,
    )

    registered_task_names = celery_app.tasks.keys()
    assert "conformly.deliver_notifications" in registered_task_names
    assert "conformly.continuous_compliance_cycle" in registered_task_names
    assert "conformly.retention_sweep" in registered_task_names

    assert deliver_notifications_task.name == "conformly.deliver_notifications"
    assert continuous_compliance_cycle_task.name == "conformly.continuous_compliance_cycle"
    assert retention_sweep_task.name == "conformly.retention_sweep"

    # Verify beat schedule configuration
    beat = celery_app.conf.beat_schedule
    assert "deliver-notifications-every-10s" in beat
    assert "continuous-compliance-cycle-hourly" in beat
    assert "retention-sweep-daily" in beat
