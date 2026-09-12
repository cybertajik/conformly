from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.compliance.models import (
    ControlImplementationStatus,
    DigestFrequency,
    EvidenceStatus,
    FindingSeverity,
    PolicyStatus,
    RemediationStatus,
    TaskPriority,
    TaskStatus,
)
from conformly.compliance.service import (
    ComplianceService,
    IndependentPolicyApprovalRequiredError,
    InvalidFileReferenceError,
    InvalidStateTransitionError,
    OptimisticLockConflictError,
)
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.policy import DataClassification
from conformly.frameworks.models import (
    ControlEntityType,
    CustomControl,
    CustomControlStatus,
)
from conformly.identity.models import (
    Membership,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
    UserStatus,
)
from conformly.storage.models import StoredFile, StoredFileStatus


def make_tenant_context(
    session: Session, role: Role = Role.COMPLIANCE_MANAGER
) -> tuple[Tenant, User, Principal, TenantContext]:
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

    session.add(
        Membership(tenant_id=tenant.id, user_id=user.id, role=role, status=MembershipStatus.ACTIVE)
    )
    session.flush()
    principal = Principal(user_id=user.id, is_platform_admin=False)
    tenant_context = TenantContext(tenant_id=tenant.id, user_id=user.id, role=role)
    return tenant, user, principal, tenant_context


def test_evidence_lifecycle_and_encryption(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    service = ComplianceService(session, test_codec)
    _, user, principal, tenant_ctx = make_tenant_context(session, Role.COMPLIANCE_MANAGER)

    # 1. Create Evidence with Restricted Notes
    evidence = service.create_evidence(
        principal,
        tenant_ctx,
        title="Firewall Audit Logs",
        description="Raw access logs from gateway firewall",
        classification=DataClassification.RESTRICTED,
        owner_user_id=user.id,
        valid_from=datetime.now(UTC),
        valid_until=datetime.now(UTC) + timedelta(days=90),
        restricted_notes="Secret internal gateway IP: 10.200.0.1",
    )
    assert evidence.id is not None
    assert evidence.status == EvidenceStatus.DRAFT
    assert evidence.restricted_notes_encrypted is not None
    assert "ciphertext" in evidence.restricted_notes_encrypted

    # 2. Get Evidence and verify decryption
    fetched, decrypted_notes = service.get_evidence(principal, tenant_ctx, evidence.id)
    assert fetched.id == evidence.id
    assert decrypted_notes == "Secret internal gateway IP: 10.200.0.1"

    # 3. Update with optimistic locking
    updated = service.update_evidence(
        principal,
        tenant_ctx,
        evidence.id,
        expected_version=1,
        title="Updated Firewall Audit Logs",
    )
    assert updated.title == "Updated Firewall Audit Logs"
    assert updated.version == 2

    # 4. Stale version update should fail with OptimisticLockConflictError
    with pytest.raises(OptimisticLockConflictError):
        service.update_evidence(
            principal,
            tenant_ctx,
            evidence.id,
            expected_version=1,
            title="Stale Update",
        )

    # 5. State transitions: DRAFT -> SUBMITTED -> VALID
    submitted = service.transition_evidence_status(
        principal,
        tenant_ctx,
        evidence.id,
        target_status=EvidenceStatus.SUBMITTED,
        expected_version=2,
    )
    assert submitted.status == EvidenceStatus.SUBMITTED
    assert submitted.version == 3

    valid = service.transition_evidence_status(
        principal,
        tenant_ctx,
        evidence.id,
        target_status=EvidenceStatus.VALID,
        expected_version=3,
    )
    assert valid.status == EvidenceStatus.VALID
    assert valid.version == 4

    # 6. Invalid transition: VALID -> SUBMITTED must fail
    with pytest.raises(InvalidStateTransitionError):
        service.transition_evidence_status(
            principal,
            tenant_ctx,
            evidence.id,
            target_status=EvidenceStatus.SUBMITTED,
            expected_version=4,
        )


def test_evidence_file_attachment_isolation(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    service = ComplianceService(session, test_codec)
    tenant_a, user_a, principal_a, ctx_a = make_tenant_context(session, Role.COMPLIANCE_MANAGER)
    tenant_b, user_b, _, _ = make_tenant_context(session, Role.COMPLIANCE_MANAGER)

    evidence_a = service.create_evidence(
        principal_a,
        ctx_a,
        title="Evidence A",
        description="Desc A",
        owner_user_id=user_a.id,
    )

    # File belonging to Tenant B
    file_b = StoredFile(
        id=uuid4(),
        tenant_id=tenant_b.id,
        created_by_user_id=user_b.id,
        original_filename="secret_b.pdf",
        content_type="application/pdf",
        classification="Internal",
        plaintext_size_bytes=10,
        ciphertext_size_bytes=20,
        plaintext_sha256="123",
        ciphertext_sha256="456",
        storage_backend="memory",
        object_key=f"tenants/{tenant_b.id}/files/f1.enc",
        key_version="v1",
        wrapped_dek_nonce="w1",
        wrapped_dek="wdek",
        ciphertext_nonce="cnonce",
        status=StoredFileStatus.ACTIVE,
    )
    session.add(file_b)
    session.flush()

    # Attempting to attach Tenant B's file to Tenant A's evidence must fail!
    with pytest.raises(InvalidFileReferenceError):
        service.attach_file_to_evidence(
            principal_a, ctx_a, evidence_id=evidence_a.id, file_id=file_b.id
        )

    # File belonging to Tenant A succeeds
    file_a = StoredFile(
        id=uuid4(),
        tenant_id=tenant_a.id,
        created_by_user_id=user_a.id,
        original_filename="doc_a.pdf",
        content_type="application/pdf",
        classification="Internal",
        plaintext_size_bytes=10,
        ciphertext_size_bytes=20,
        plaintext_sha256="123",
        ciphertext_sha256="456",
        storage_backend="memory",
        object_key=f"tenants/{tenant_a.id}/files/f2.enc",
        key_version="v1",
        wrapped_dek_nonce="w1",
        wrapped_dek="wdek",
        ciphertext_nonce="cnonce",
        status=StoredFileStatus.ACTIVE,
    )
    session.add(file_a)
    session.flush()

    link = service.attach_file_to_evidence(
        principal_a, ctx_a, evidence_id=evidence_a.id, file_id=file_a.id
    )
    assert link.id is not None
    assert link.file_id == file_a.id


def test_policy_approval_and_publishing_workflow(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    service = ComplianceService(session, test_codec)
    tenant, author, principal_author, ctx_author = make_tenant_context(
        session, Role.COMPLIANCE_MANAGER
    )

    # 1. Author creates policy
    policy = service.create_policy(
        principal_author,
        ctx_author,
        title="Access Control Policy",
        description="Defines RBAC and credential rotation rules",
        version_string="1.0",
        review_cycle_days=180,
        content="All systems must require MFA and least-privilege RBAC.",
        classification=DataClassification.CONFIDENTIAL,
        restricted_content="Secret break-glass account guidelines",
    )
    assert policy.id is not None
    assert policy.status == PolicyStatus.DRAFT
    assert policy.version == 1

    # 2. Submit for review
    policy_review = service.submit_policy_for_review(
        principal_author, ctx_author, policy.id, expected_version=1
    )
    assert policy_review.status == PolicyStatus.IN_REVIEW
    assert policy_review.version == 2

    # 3. Author cannot approve own policy! Independent 2-person approval check
    with pytest.raises(IndependentPolicyApprovalRequiredError):
        service.approve_policy(principal_author, ctx_author, policy.id, expected_version=2)

    # 4. Another user (e.g. Administrator) approves the policy
    approver = User(
        id=uuid4(),
        oidc_issuer="https://issuer.example.com",
        oidc_subject="sub-approver",
        email="approver@example.com",
        display_name="Approver",
        status=UserStatus.ACTIVE,
    )
    session.add(approver)
    session.flush()

    principal_approver = Principal(user_id=approver.id, is_platform_admin=False)
    ctx_approver = TenantContext(tenant_id=tenant.id, user_id=approver.id, role=Role.ADMINISTRATOR)

    approved = service.approve_policy(
        principal_approver, ctx_approver, policy.id, expected_version=2
    )
    assert approved.status == PolicyStatus.APPROVED
    assert approved.approved_by_user_id == approver.id
    assert approved.approved_at is not None
    assert approved.version == 3

    # 5. Publish policy and check next_review_due is set to now + review_cycle_days
    published = service.publish_policy(
        principal_approver, ctx_approver, policy.id, expected_version=3
    )
    assert published.status == PolicyStatus.PUBLISHED
    assert published.next_review_due is not None
    expected_cutoff = datetime.now(UTC) + timedelta(days=175)
    assert published.next_review_due > expected_cutoff


def test_compliance_tasks_and_findings(session: Session, test_codec: EncryptedFieldCodec) -> None:
    service = ComplianceService(session, test_codec)
    _, user, principal, tenant_ctx = make_tenant_context(session, Role.COMPLIANCE_MANAGER)

    # Task lifecycle
    task = service.create_task(
        principal,
        tenant_ctx,
        title="Perform Annual Penetration Test",
        description="Third-party penetration test of web SaaS API",
        due_date=datetime.now(UTC) + timedelta(days=14),
        priority=TaskPriority.HIGH,
        assignee_user_id=user.id,
    )
    assert task.status == TaskStatus.PENDING
    assert task.version == 1

    updated_task = service.update_task(
        principal,
        tenant_ctx,
        task.id,
        expected_version=1,
        priority=TaskPriority.CRITICAL,
    )
    assert updated_task.priority == TaskPriority.CRITICAL
    assert updated_task.version == 2

    completed_task = service.complete_task(principal, tenant_ctx, task.id, expected_version=2)
    assert completed_task.status == TaskStatus.COMPLETED
    assert completed_task.completed_by_user_id == user.id

    # Finding lifecycle
    finding = service.create_finding(
        principal,
        tenant_ctx,
        title="S3 Bucket Public Read",
        description="Testing bucket was left public during migration",
        severity=FindingSeverity.HIGH,
        remediation_plan="Block public access and enable KMS encryption",
    )
    assert finding.remediation_status == RemediationStatus.OPEN

    remediated = service.update_remediation_status(
        principal,
        tenant_ctx,
        finding.id,
        expected_version=1,
        remediation_status=RemediationStatus.RESOLVED,
        remediation_summary="Public access blocked, verified via AWS Config",
    )
    assert remediated.remediation_status == RemediationStatus.RESOLVED
    assert remediated.resolved_at is not None
    assert remediated.resolved_by_user_id == user.id


def test_control_status_posture_and_preferences(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    service = ComplianceService(session, test_codec)
    tenant, user, principal, tenant_ctx = make_tenant_context(session, Role.COMPLIANCE_MANAGER)

    # Create custom control
    custom_control = CustomControl(
        tenant_id=tenant.id,
        identifier="CC-DATA-01",
        title="Quarterly Key Rotation",
        description="Rotate encryption keys every 90 days",
        category="Cryptography",
        status=CustomControlStatus.ACTIVE,
        created_by_user_id=user.id,
    )
    session.add(custom_control)
    session.flush()

    # Record control implementation status
    status_rec = service.upsert_control_status(
        principal,
        tenant_ctx,
        control_type=ControlEntityType.CUSTOM,
        control_id=custom_control.id,
        status=ControlImplementationStatus.IMPLEMENTED,
        assigned_owner_user_id=user.id,
        notes="Automated KMS rotation enabled",
    )
    assert status_rec.status == ControlImplementationStatus.IMPLEMENTED

    # Get matrix
    matrix = service.get_control_status_matrix(principal, tenant_ctx)
    assert len(matrix) == 1
    assert matrix[0].control_id == custom_control.id

    # Preferences
    pref = service.get_or_create_user_preferences(principal, tenant_ctx)
    assert pref.digest_frequency == DigestFrequency.IMMEDIATE

    updated_pref = service.update_user_preferences(
        principal, tenant_ctx, digest_frequency=DigestFrequency.WEEKLY, email_enabled=False
    )
    assert updated_pref.digest_frequency == DigestFrequency.WEEKLY
    assert not updated_pref.email_enabled
