from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditEvent
from conformly.auth.session import hash_session_id
from conformly.auth.tokens import TokenClaims, TokenVerifier, get_token_verifier
from conformly.authz.roles import Role
from conformly.compliance.automation import (
    check_expiring_evidence,
    check_policy_reviews,
    check_vendor_cadence,
    enforce_expired_evidence,
    escalate_overdue_tasks,
    run_continuous_compliance_cycle,
)
from conformly.compliance.models import (
    ComplianceTask,
    EvidenceItem,
    EvidenceStatus,
    Policy,
    PolicyStatus,
    TaskPriority,
    TaskStatus,
)
from conformly.compliance.worker import run_compliance_worker_tick
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.db.session import get_db
from conformly.identity.models import (
    AuthSession,
    Membership,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
    UserStatus,
)
from conformly.main import app
from conformly.vendors.models import Vendor, VendorCriticality, VendorStatus


class FakeTokenVerifier(TokenVerifier):
    def __init__(self, claims: TokenClaims) -> None:
        self._claims = claims

    def verify(self, token: str) -> TokenClaims:
        return self._claims


@pytest.fixture
def client(session: Session, test_codec: EncryptedFieldCodec) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_encrypted_field_codec] = lambda: test_codec
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _seed_tenant_user(
    session: Session, role: Role = Role.OWNER
) -> tuple[User, Tenant, TokenClaims]:
    session_id = f"session-{uuid4().hex[:8]}"
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject=str(uuid4()),
        email=f"user-{uuid4().hex[:8]}@example.test",
        display_name="Automation Test User",
        status=UserStatus.ACTIVE,
    )
    tenant = Tenant(
        name="Automation Tenant",
        slug=f"tenant-{uuid4().hex[:8]}",
        status=TenantStatus.ACTIVE,
    )
    session.add_all([user, tenant])
    session.flush()

    membership = Membership(
        tenant_id=tenant.id,
        user_id=user.id,
        role=role,
        status=MembershipStatus.ACTIVE,
    )
    auth_session = AuthSession(
        user_id=user.id,
        session_id_hash=hash_session_id(session_id),
        expires_at=expires_at,
    )
    session.add_all([membership, auth_session])
    session.flush()

    claims = TokenClaims(
        issuer=user.oidc_issuer,
        subject=user.oidc_subject,
        session_id=session_id,
        expires_at=int(expires_at.timestamp()),
        email=user.email,
        email_verified=True,
        display_name=user.display_name,
    )
    return user, tenant, claims


def test_check_expiring_evidence_warnings_and_task(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    user, tenant, _ = _seed_tenant_user(session, Role.OWNER)
    now = datetime.now(UTC)

    evidence = EvidenceItem(
        id=uuid4(),
        tenant_id=tenant.id,
        title="Expiring ISO Cert",
        description="Will expire soon",
        classification="Internal",
        status=EvidenceStatus.VALID,
        owner_user_id=user.id,
        valid_until=now + timedelta(days=15),
        version=1,
    )
    session.add(evidence)
    session.flush()

    # First run
    warnings, alerts, tasks = check_expiring_evidence(session, test_codec, tenant.id, now)
    assert warnings == 1
    assert alerts == 1
    assert tasks == 1

    # Verify task created
    created_task = session.scalar(
        select(ComplianceTask).where(
            ComplianceTask.tenant_id == tenant.id,
            ComplianceTask.evidence_id == evidence.id,
        )
    )
    assert created_task is not None
    assert "Renew Expiring Evidence" in created_task.title
    assert created_task.priority == TaskPriority.HIGH
    assert created_task.status == TaskStatus.PENDING
    assert created_task.assignee_user_id == user.id

    # Second run (idempotent)
    warnings2, alerts2, tasks2 = check_expiring_evidence(session, test_codec, tenant.id, now)
    assert warnings2 == 1
    assert alerts2 == 0
    assert tasks2 == 0


def test_enforce_expired_evidence_and_task(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    user, tenant, _ = _seed_tenant_user(session, Role.OWNER)
    now = datetime.now(UTC)

    evidence = EvidenceItem(
        id=uuid4(),
        tenant_id=tenant.id,
        title="Old Pen Test Report",
        description="Expired yesterday",
        classification="Internal",
        status=EvidenceStatus.VALID,
        owner_user_id=user.id,
        valid_until=now - timedelta(days=1),
        version=1,
    )
    session.add(evidence)
    session.flush()

    expired_count, alerts, tasks = enforce_expired_evidence(session, test_codec, tenant.id, now)
    assert expired_count == 1
    assert alerts == 1
    assert tasks == 1

    session.refresh(evidence)
    assert evidence.status == EvidenceStatus.EXPIRED
    assert evidence.version == 2

    # Verify task created with CRITICAL priority
    created_task = session.scalar(
        select(ComplianceTask).where(
            ComplianceTask.tenant_id == tenant.id,
            ComplianceTask.evidence_id == evidence.id,
        )
    )
    assert created_task is not None
    assert "Replace Expired Evidence" in created_task.title
    assert created_task.priority == TaskPriority.CRITICAL


def test_escalate_overdue_tasks(session: Session, test_codec: EncryptedFieldCodec) -> None:
    user, tenant, _ = _seed_tenant_user(session, Role.OWNER)
    now = datetime.now(UTC)

    task = ComplianceTask(
        id=uuid4(),
        tenant_id=tenant.id,
        title="Patch OpenSSH vulnerability",
        description="Fix immediately",
        due_date=now - timedelta(days=2),
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        assignee_user_id=user.id,
        version=1,
    )
    session.add(task)
    session.flush()

    escalated, alerts = escalate_overdue_tasks(session, test_codec, tenant.id, now)
    assert escalated == 1
    assert alerts == 1

    session.refresh(task)
    assert task.status == TaskStatus.OVERDUE
    assert task.version == 2


def test_check_policy_reviews_and_task(session: Session, test_codec: EncryptedFieldCodec) -> None:
    user, tenant, _ = _seed_tenant_user(session, Role.OWNER)
    now = datetime.now(UTC)

    policy = Policy(
        id=uuid4(),
        tenant_id=tenant.id,
        title="Access Control Policy",
        description="IAM governance",
        version_string="2.0",
        status=PolicyStatus.PUBLISHED,
        owner_user_id=user.id,
        next_review_due=now + timedelta(days=10),
    )
    session.add(policy)
    session.flush()

    reviews_due, alerts, tasks = check_policy_reviews(session, test_codec, tenant.id, now)
    assert reviews_due == 1
    assert alerts == 1
    assert tasks == 1

    created_task = session.scalar(
        select(ComplianceTask).where(
            ComplianceTask.tenant_id == tenant.id,
            ComplianceTask.policy_id == policy.id,
        )
    )
    assert created_task is not None
    assert "Annual Policy Review" in created_task.title
    assert created_task.assignee_user_id == user.id


def test_check_vendor_cadence_and_dpa(session: Session, test_codec: EncryptedFieldCodec) -> None:
    user, tenant, _ = _seed_tenant_user(session, Role.OWNER)
    now = datetime.now(UTC)

    # Vendor 1: High criticality, missing DPA
    v1 = Vendor(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Cloudflare",
        service_description="Edge CDN",
        criticality=VendorCriticality.HIGH,
        dpa_signed=False,
        status=VendorStatus.ACTIVE,
    )
    # Vendor 2: Critical, review due in 5 days, DPA signed
    v2 = Vendor(
        id=uuid4(),
        tenant_id=tenant.id,
        name="AWS EU",
        service_description="Cloud IaaS",
        criticality=VendorCriticality.CRITICAL,
        dpa_signed=True,
        next_review_due_at=now + timedelta(days=5),
        status=VendorStatus.ACTIVE,
    )
    session.add_all([v1, v2])
    session.flush()

    reviews_due, missing_dpas, alerts, tasks = check_vendor_cadence(
        session, test_codec, tenant.id, now
    )
    assert reviews_due == 1
    assert missing_dpas == 1
    assert alerts == 2
    assert tasks == 2

    # Check tasks
    dpa_task = session.scalar(
        select(ComplianceTask).where(
            ComplianceTask.tenant_id == tenant.id,
            ComplianceTask.title.startswith("Execute Missing DPA: Cloudflare"),
        )
    )
    assert dpa_task is not None
    assert dpa_task.priority == TaskPriority.HIGH

    review_task = session.scalar(
        select(ComplianceTask).where(
            ComplianceTask.tenant_id == tenant.id,
            ComplianceTask.title.startswith("Vendor Security Review: AWS EU"),
        )
    )
    assert review_task is not None
    assert review_task.priority == TaskPriority.HIGH


def test_run_continuous_compliance_cycle_complete(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    user, tenant, _ = _seed_tenant_user(session, Role.OWNER)
    now = datetime.now(UTC)

    # 1. Expiring evidence (<30 days)
    e1 = EvidenceItem(
        id=uuid4(),
        tenant_id=tenant.id,
        title="Firewall Logs",
        description="Logs",
        status=EvidenceStatus.VALID,
        owner_user_id=user.id,
        valid_until=now + timedelta(days=10),
    )
    # 2. Expired evidence
    e2 = EvidenceItem(
        id=uuid4(),
        tenant_id=tenant.id,
        title="Old Backup Audit",
        description="Logs",
        status=EvidenceStatus.VALID,
        owner_user_id=user.id,
        valid_until=now - timedelta(days=5),
    )
    # 3. Overdue task
    t1 = ComplianceTask(
        id=uuid4(),
        tenant_id=tenant.id,
        title="Perform Risk Review",
        description="Do review",
        due_date=now - timedelta(days=1),
        status=TaskStatus.PENDING,
    )
    # 4. Review-due policy
    p1 = Policy(
        id=uuid4(),
        tenant_id=tenant.id,
        title="Data Retention Policy",
        description="Retention",
        status=PolicyStatus.PUBLISHED,
        owner_user_id=user.id,
        next_review_due=now + timedelta(days=20),
    )
    # 5. Missing DPA vendor
    v1 = Vendor(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Payment Gateway",
        service_description="Payments",
        criticality=VendorCriticality.CRITICAL,
        dpa_signed=False,
        status=VendorStatus.ACTIVE,
    )
    session.add_all([e1, e2, t1, p1, v1])
    session.flush()

    result = run_continuous_compliance_cycle(session, test_codec, tenant_id=tenant.id, now=now)

    assert result.expired_evidence_count == 1
    assert result.expiring_evidence_warnings == 1
    assert result.overdue_tasks_escalated == 1
    assert result.policy_reviews_due == 1
    assert result.missing_dpas_flagged == 1
    assert result.tasks_created == 4  # e1, e2, p1, v1
    assert result.notifications_enqueued == 5  # e1, e2, t1, p1, v1

    # Verify audit event
    audit_event = session.scalar(
        select(AuditEvent).where(
            AuditEvent.tenant_id == tenant.id,
            AuditEvent.action == "compliance.continuous_cycle_executed",
        )
    )
    assert audit_event is not None
    assert audit_event.safe_metadata.get("record_count") == 4


def test_cycle_api_endpoint_permissions(
    client: TestClient,
    session: Session,
) -> None:
    # 1. Owner can trigger cycle
    owner_user, owner_tenant, owner_claims = _seed_tenant_user(session, Role.OWNER)
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(owner_claims)
    response = client.post(
        f"/v1/tenants/{owner_tenant.id}/compliance/cycle",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "tasks_created" in data
    assert "executed_at" in data

    # 2. Compliance Manager can trigger cycle
    mgr_user, mgr_tenant, mgr_claims = _seed_tenant_user(session, Role.COMPLIANCE_MANAGER)
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(mgr_claims)
    response_mgr = client.post(
        f"/v1/tenants/{mgr_tenant.id}/compliance/cycle",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response_mgr.status_code == status.HTTP_200_OK

    # 3. Tenant Administrator is STRICTLY BLOCKED (Compliance barrier per Card 11 & D-047)
    admin_user, admin_tenant, admin_claims = _seed_tenant_user(session, Role.ADMINISTRATOR)
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(admin_claims)
    response_admin = client.post(
        f"/v1/tenants/{admin_tenant.id}/compliance/cycle",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response_admin.status_code == status.HTTP_403_FORBIDDEN

    # 4. Employee is BLOCKED
    emp_user, emp_tenant, emp_claims = _seed_tenant_user(session, Role.EMPLOYEE)
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(emp_claims)
    response_emp = client.post(
        f"/v1/tenants/{emp_tenant.id}/compliance/cycle",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response_emp.status_code == status.HTTP_403_FORBIDDEN


def test_worker_tick_runs_across_tenants(session: Session, test_codec: EncryptedFieldCodec) -> None:
    u1, t1, _ = _seed_tenant_user(session, Role.OWNER)
    u2, t2, _ = _seed_tenant_user(session, Role.OWNER)

    # Seed an overdue task in tenant 1
    now = datetime.now(UTC)
    task1 = ComplianceTask(
        id=uuid4(),
        tenant_id=t1.id,
        title="T1 Task",
        description="Overdue",
        due_date=now - timedelta(days=1),
        status=TaskStatus.PENDING,
    )
    session.add(task1)
    session.flush()

    # Create dummy session factory yielding the test session
    from unittest.mock import MagicMock

    session_factory_mock = MagicMock()
    session_factory_mock.return_value.__enter__.return_value = session

    summary = run_compliance_worker_tick(session_factory_mock, test_codec, now=now)
    assert summary["tenants_checked"] >= 2
    assert summary["total_alerts_enqueued"] >= 1
