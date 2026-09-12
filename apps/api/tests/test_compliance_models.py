from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conformly.compliance.models import (
    ComplianceTask,
    ControlImplementationStatus,
    ControlStatusRecord,
    DigestFrequency,
    EvidenceControlLink,
    EvidenceFileLink,
    EvidenceItem,
    EvidenceStatus,
    Finding,
    FindingSeverity,
    Policy,
    PolicyControlLink,
    PolicyStatus,
    RemediationStatus,
    TaskPriority,
    TaskStatus,
    UserNotificationPreference,
)
from conformly.frameworks.models import ControlEntityType
from conformly.identity.models import Tenant, TenantStatus, User, UserStatus
from conformly.storage.models import StoredFile, StoredFileStatus


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


def test_evidence_models_and_links(session: Session) -> None:
    tenant, user = create_tenant_and_user(session)

    # 1. Create StoredFile
    file_id = uuid4()
    stored_file = StoredFile(
        id=file_id,
        tenant_id=tenant.id,
        created_by_user_id=user.id,
        original_filename="audit_log.csv",
        content_type="text/csv",
        classification="Internal",
        plaintext_size_bytes=100,
        ciphertext_size_bytes=128,
        plaintext_sha256="abc",
        ciphertext_sha256="def",
        storage_backend="memory",
        object_key=f"tenants/{tenant.id}/files/{file_id}/data.enc",
        key_version="v1",
        wrapped_dek_nonce="nonce1",
        wrapped_dek="dek",
        ciphertext_nonce="nonce2",
        status=StoredFileStatus.ACTIVE,
    )
    session.add(stored_file)
    session.flush()

    # 2. Create EvidenceItem
    evidence = EvidenceItem(
        tenant_id=tenant.id,
        title="Q3 Audit Report",
        description="Quarterly SOC2 audit trail evidence",
        classification="Confidential",
        status=EvidenceStatus.DRAFT,
        owner_user_id=user.id,
        valid_from=datetime.now(UTC),
        valid_until=datetime.now(UTC) + timedelta(days=90),
        version=1,
    )
    session.add(evidence)
    session.flush()

    # 3. Create File Link
    file_link = EvidenceFileLink(
        tenant_id=tenant.id,
        evidence_id=evidence.id,
        file_id=stored_file.id,
        attached_by_user_id=user.id,
    )
    session.add(file_link)
    session.flush()

    # 4. Create Control Link
    control_id = uuid4()
    control_link = EvidenceControlLink(
        tenant_id=tenant.id,
        evidence_id=evidence.id,
        control_type=ControlEntityType.CANONICAL,
        control_id=control_id,
        linked_by_user_id=user.id,
    )
    session.add(control_link)
    session.flush()

    assert len(evidence.file_links) == 1
    assert evidence.file_links[0].file_id == stored_file.id
    assert len(evidence.control_links) == 1
    assert evidence.control_links[0].control_id == control_id


def test_duplicate_evidence_file_link_violates_constraint(session: Session) -> None:
    tenant, user = create_tenant_and_user(session)

    stored_file = StoredFile(
        id=uuid4(),
        tenant_id=tenant.id,
        created_by_user_id=user.id,
        original_filename="sample.pdf",
        content_type="application/pdf",
        classification="Internal",
        plaintext_size_bytes=100,
        ciphertext_size_bytes=128,
        plaintext_sha256="abc",
        ciphertext_sha256="def",
        storage_backend="memory",
        object_key=f"tenants/{tenant.id}/files/key.enc",
        key_version="v1",
        wrapped_dek_nonce="nonce1",
        wrapped_dek="dek",
        ciphertext_nonce="nonce2",
        status=StoredFileStatus.ACTIVE,
    )
    session.add(stored_file)
    session.flush()

    evidence = EvidenceItem(
        tenant_id=tenant.id,
        title="Sample",
        description="Sample",
        classification="Internal",
        status=EvidenceStatus.DRAFT,
        owner_user_id=user.id,
        version=1,
    )
    session.add(evidence)
    session.flush()

    link1 = EvidenceFileLink(
        tenant_id=tenant.id,
        evidence_id=evidence.id,
        file_id=stored_file.id,
        attached_by_user_id=user.id,
    )
    session.add(link1)
    session.flush()

    link2 = EvidenceFileLink(
        tenant_id=tenant.id,
        evidence_id=evidence.id,
        file_id=stored_file.id,
        attached_by_user_id=user.id,
    )
    session.add(link2)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_policy_models_and_links(session: Session) -> None:
    tenant, user = create_tenant_and_user(session)

    policy = Policy(
        tenant_id=tenant.id,
        title="Information Security Policy",
        description="Master policy for data protection",
        version_string="1.0",
        status=PolicyStatus.DRAFT,
        owner_user_id=user.id,
        review_cycle_days=365,
        version=1,
        content="All data must be encrypted.",
        classification="Internal",
    )
    session.add(policy)
    session.flush()

    control_id = uuid4()
    link = PolicyControlLink(
        tenant_id=tenant.id,
        policy_id=policy.id,
        control_type=ControlEntityType.CANONICAL,
        control_id=control_id,
        linked_by_user_id=user.id,
    )
    session.add(link)
    session.flush()

    assert len(policy.control_links) == 1
    assert policy.control_links[0].control_id == control_id


def test_compliance_task_and_finding_models(session: Session) -> None:
    tenant, user = create_tenant_and_user(session)

    task = ComplianceTask(
        tenant_id=tenant.id,
        title="Review Access Keys",
        description="Verify developer credentials rotation",
        due_date=datetime.now(UTC) + timedelta(days=7),
        status=TaskStatus.PENDING,
        priority=TaskPriority.HIGH,
        assignee_user_id=user.id,
        version=1,
    )
    session.add(task)

    finding = Finding(
        tenant_id=tenant.id,
        title="MFA Not Enforced on Legacy Service",
        description="Audit revealed legacy portal lacked MFA enforcement",
        severity=FindingSeverity.HIGH,
        remediation_status=RemediationStatus.OPEN,
        due_date=datetime.now(UTC) + timedelta(days=30),
        owner_user_id=user.id,
        remediation_plan="Migrate legacy authentication to centralized OIDC",
        version=1,
    )
    session.add(finding)
    session.flush()

    assert task.id is not None
    assert finding.id is not None
    assert task.status == TaskStatus.PENDING
    assert finding.severity == FindingSeverity.HIGH


def test_control_status_record_and_preferences(session: Session) -> None:
    tenant, user = create_tenant_and_user(session)
    control_id = uuid4()

    record = ControlStatusRecord(
        tenant_id=tenant.id,
        control_type=ControlEntityType.CANONICAL,
        control_id=control_id,
        status=ControlImplementationStatus.IMPLEMENTED,
        assigned_owner_user_id=user.id,
        notes="Validated during Q2 internal test",
        last_assessed_at=datetime.now(UTC),
        assessed_by_user_id=user.id,
        version=1,
    )
    session.add(record)

    pref = UserNotificationPreference(
        tenant_id=tenant.id,
        user_id=user.id,
        email_enabled=True,
        digest_frequency=DigestFrequency.DAILY,
        notify_task_assigned=True,
        notify_task_due=True,
    )
    session.add(pref)
    session.flush()

    assert record.id is not None
    assert record.status == ControlImplementationStatus.IMPLEMENTED
    assert pref.digest_frequency == DigestFrequency.DAILY
