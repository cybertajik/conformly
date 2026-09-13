from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.compliance.models import (
    ControlImplementationStatus,
    EvidenceControlLink,
    EvidenceItem,
    EvidenceStatus,
    FindingSeverity,
    Policy,
    PolicyControlLink,
    PolicyStatus,
)
from conformly.compliance.service import (
    ComplianceLegalHoldActiveError,
    ComplianceService,
    InvalidStateTransitionError,
)
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.policy import DataClassification
from conformly.frameworks.models import (
    AdoptionStatus,
    CanonicalControl,
    ControlEntityType,
    Framework,
    FrameworkVersion,
    ReleaseState,
    TenantFrameworkAdoption,
)
from conformly.identity.models import (
    Membership,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
    UserStatus,
)
from conformly.preaudit.models import CertificateStatus
from conformly.preaudit.service import (
    CertificateIssuanceBlockedError,
    PreAuditService,
    ReviewerConflictError,
)
from conformly.storage.models import StoredFileStatus
from conformly.storage.providers import MemoryStorageProvider
from conformly.storage.service import FileQuarantinedError, LegalHoldActiveError, StorageService


def make_tenant(
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


def add_member(
    session: Session, tenant: Tenant, role: Role
) -> tuple[User, Principal, TenantContext]:
    user_id = uuid4()
    user = User(
        id=user_id,
        oidc_issuer="https://issuer.example.com",
        oidc_subject=f"sub-{user_id.hex[:8]}",
        email=f"user-{user_id.hex[:8]}@example.com",
        display_name=f"User {user_id.hex[:6]}",
        status=UserStatus.ACTIVE,
    )
    session.add(user)
    session.flush()
    session.add(
        Membership(tenant_id=tenant.id, user_id=user.id, role=role, status=MembershipStatus.ACTIVE)
    )
    session.flush()
    principal = Principal(user_id=user.id, is_platform_admin=False)
    tenant_context = TenantContext(tenant_id=tenant.id, user_id=user.id, role=role)
    return user, principal, tenant_context


# =============================================================================
# 1. Evidence Revisions & Legal Hold
# =============================================================================


def test_evidence_revisions_and_legal_hold(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    service = ComplianceService(session, test_codec)
    tenant, user, principal, tenant_ctx = make_tenant(session, Role.COMPLIANCE_MANAGER)

    evidence = service.create_evidence(
        principal,
        tenant_ctx,
        title="Audit Evidence 2026",
        description="Initial version of audit evidence",
        classification=DataClassification.INTERNAL,
        owner_user_id=user.id,
    )
    assert evidence.version == 1

    revs = service.list_evidence_revisions(principal, tenant_ctx, evidence.id)
    assert len(revs) == 1
    assert revs[0].revision_number == 1
    assert revs[0].title == "Audit Evidence 2026"

    # Update evidence
    updated = service.update_evidence(
        principal,
        tenant_ctx,
        evidence.id,
        expected_version=1,
        title="Audit Evidence 2026 Updated",
    )
    assert updated.version == 2
    revs = service.list_evidence_revisions(principal, tenant_ctx, evidence.id)
    assert len(revs) == 2
    assert revs[0].revision_number == 2
    assert revs[0].title == "Audit Evidence 2026 Updated"

    # Toggle legal hold ON
    held = service.set_evidence_legal_hold(
        principal, tenant_ctx, evidence.id, legal_hold=True, reason="Litigation inquiry"
    )
    assert held.legal_hold is True
    assert held.version == 3

    # Transitioning to ARCHIVED while under legal hold must fail
    with pytest.raises(ComplianceLegalHoldActiveError):
        service.transition_evidence_status(
            principal,
            tenant_ctx,
            evidence.id,
            target_status=EvidenceStatus.ARCHIVED,
            expected_version=3,
        )

    # Release legal hold
    released = service.set_evidence_legal_hold(
        principal, tenant_ctx, evidence.id, legal_hold=False, reason="Inquiry concluded"
    )
    assert released.legal_hold is False
    assert released.version == 4

    # Now archiving is allowed
    archived = service.transition_evidence_status(
        principal,
        tenant_ctx,
        evidence.id,
        target_status=EvidenceStatus.ARCHIVED,
        expected_version=4,
    )
    assert archived.status == EvidenceStatus.ARCHIVED


# =============================================================================
# 2. Production Malware Scanner & Quarantine Integration
# =============================================================================


def test_malware_scanner_quarantines_malicious_and_executables(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    storage_provider = MemoryStorageProvider()
    storage = StorageService(session, storage_provider, test_codec._envelope)
    tenant, user, principal, tenant_ctx = make_tenant(session, Role.COMPLIANCE_MANAGER)

    # Clean file uploads successfully
    clean_content = b"%PDF-1.4\nSome legitimate compliance document\n%%EOF"
    clean_file = storage.upload_file(
        principal,
        tenant_ctx,
        filename="compliance_report.pdf",
        content_type="application/pdf",
        data_stream=BytesIO(clean_content),
        classification=DataClassification.INTERNAL,
    )
    assert clean_file.status == StoredFileStatus.ACTIVE

    # EICAR signature is quarantined
    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    with pytest.raises(FileQuarantinedError):
        storage.upload_file(
            principal,
            tenant_ctx,
            filename="eicar.txt",
            content_type="text/plain",
            data_stream=BytesIO(eicar),
            classification=DataClassification.INTERNAL,
        )

    # Executable header (MZ header disguised as pdf) is quarantined
    fake_pdf = b"MZ\x90\x00\x03\x00\x00\x00" + b"A" * 100
    with pytest.raises(FileQuarantinedError):
        storage.upload_file(
            principal,
            tenant_ctx,
            filename="invoice.pdf",
            content_type="application/pdf",
            data_stream=BytesIO(fake_pdf),
            classification=DataClassification.INTERNAL,
        )

    # Malicious script markup is quarantined
    malicious_svg = b"<svg><script>alert('xss')</script></svg>"
    with pytest.raises(FileQuarantinedError):
        storage.upload_file(
            principal,
            tenant_ctx,
            filename="logo.svg",
            content_type="image/svg+xml",
            data_stream=BytesIO(malicious_svg),
            classification=DataClassification.INTERNAL,
        )


def test_storage_legal_hold_blocks_deletion(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    storage_provider = MemoryStorageProvider()
    storage = StorageService(session, storage_provider, test_codec._envelope)
    compliance = ComplianceService(session, test_codec)
    tenant, user, principal, tenant_ctx = make_tenant(session, Role.COMPLIANCE_MANAGER)

    clean_content = b"Legal compliance evidence file"
    file = storage.upload_file(
        principal,
        tenant_ctx,
        filename="contract.txt",
        content_type="text/plain",
        data_stream=BytesIO(clean_content),
        classification=DataClassification.INTERNAL,
    )

    evidence = compliance.create_evidence(
        principal,
        tenant_ctx,
        title="Contract Evidence",
        description="Signed contract",
        owner_user_id=user.id,
    )
    compliance.attach_file_to_evidence(
        principal, tenant_ctx, evidence_id=evidence.id, file_id=file.id
    )

    # Put evidence under legal hold
    compliance.set_evidence_legal_hold(
        principal, tenant_ctx, evidence.id, legal_hold=True, reason="Department of Justice hold"
    )

    # Attempting to delete the stored file must raise LegalHoldActiveError
    with pytest.raises(LegalHoldActiveError):
        storage.delete_file(principal, tenant_ctx, file.id)

    # Release legal hold
    compliance.set_evidence_legal_hold(
        principal, tenant_ctx, evidence.id, legal_hold=False, reason="Hold released"
    )

    # Now deleting file succeeds
    storage.delete_file(principal, tenant_ctx, file.id)
    assert file.status in (StoredFileStatus.DELETE_PENDING, StoredFileStatus.DELETED)


# =============================================================================
# 3. Policy Revisions, Templates & Workforce Acknowledgements
# =============================================================================


def test_policy_revisions_and_two_person_approval(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    service = ComplianceService(session, test_codec)
    tenant, author, author_p, author_ctx = make_tenant(session, Role.COMPLIANCE_MANAGER)
    approver, approver_p, approver_ctx = add_member(session, tenant, Role.COMPLIANCE_MANAGER)

    policy = service.create_policy(
        author_p,
        author_ctx,
        title="Access Control Policy",
        description="Defines access requirements",
        content="All passwords must be 16 chars minimum.",
    )
    assert policy.version == 1

    revs = service.list_policy_revisions(author_p, author_ctx, policy.id)
    assert len(revs) == 1
    assert revs[0].status == PolicyStatus.DRAFT

    # Update policy
    policy = service.update_policy(
        author_p,
        author_ctx,
        policy.id,
        expected_version=1,
        content="All passwords must be 20 chars minimum and use MFA.",
    )
    assert policy.version == 2
    assert len(service.list_policy_revisions(author_p, author_ctx, policy.id)) == 2

    # Submit for review
    policy = service.submit_policy_for_review(author_p, author_ctx, policy.id, expected_version=2)
    assert policy.status == PolicyStatus.IN_REVIEW
    assert len(service.list_policy_revisions(author_p, author_ctx, policy.id)) == 3

    # Independent approval: author cannot approve own policy
    from conformly.compliance.service import IndependentPolicyApprovalRequiredError

    with pytest.raises(IndependentPolicyApprovalRequiredError):
        service.approve_policy(author_p, author_ctx, policy.id, expected_version=3)

    # Second person approves
    policy = service.approve_policy(approver_p, approver_ctx, policy.id, expected_version=3)
    assert policy.status == PolicyStatus.APPROVED
    assert policy.approved_by_user_id == approver.id
    assert len(service.list_policy_revisions(author_p, author_ctx, policy.id)) == 4

    # Publish
    policy = service.publish_policy(approver_p, approver_ctx, policy.id, expected_version=4)
    assert policy.status == PolicyStatus.PUBLISHED
    assert len(service.list_policy_revisions(author_p, author_ctx, policy.id)) == 5


def test_policy_templates_and_workforce_acknowledgements(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    service = ComplianceService(session, test_codec)
    tenant, author, author_p, author_ctx = make_tenant(session, Role.COMPLIANCE_MANAGER)
    employee, employee_p, employee_ctx = add_member(session, tenant, Role.EMPLOYEE)
    approver, approver_p, approver_ctx = add_member(session, tenant, Role.COMPLIANCE_MANAGER)

    # 1. Seed canonical templates
    count = service.seed_canonical_policy_templates()
    assert count >= 6

    templates = service.list_policy_templates(author_p, author_ctx)
    assert len(templates) >= 6

    # 2. Instantiate policy from template
    tmpl = templates[0]
    policy = service.instantiate_policy_from_template(author_p, author_ctx, tmpl.id)
    assert policy.title == tmpl.title
    assert policy.content == tmpl.content_template

    # Cannot acknowledge un-published policy
    with pytest.raises(InvalidStateTransitionError):
        service.acknowledge_policy(employee_p, employee_ctx, policy.id)

    # Progress to published
    policy = service.submit_policy_for_review(author_p, author_ctx, policy.id, expected_version=1)
    policy = service.approve_policy(approver_p, approver_ctx, policy.id, expected_version=2)
    policy = service.publish_policy(approver_p, approver_ctx, policy.id, expected_version=3)

    # 3. Acknowledge policy
    ack = service.acknowledge_policy(
        employee_p,
        employee_ctx,
        policy.id,
        ip_address="192.168.1.50",
        user_agent="Mozilla/5.0 TestBrowser",
    )
    assert ack.user_id == employee.id
    assert ack.policy_id == policy.id
    assert ack.ip_address == "192.168.1.50"

    # Idempotent re-acknowledgement returns existing
    ack2 = service.acknowledge_policy(employee_p, employee_ctx, policy.id)
    assert ack2.id == ack.id

    # List acknowledgements
    acks = service.list_policy_acknowledgements(author_p, author_ctx, policy.id)
    assert len(acks) == 1
    assert acks[0].user_id == employee.id

    my_acks = service.get_my_acknowledgements(employee_p, employee_ctx)
    assert len(my_acks) == 1
    assert my_acks[0].policy_id == policy.id


# =============================================================================
# 4. Readiness Workflow: Scoped Reviewer, Tenant Approval & Auto-Suspension
# =============================================================================


def _setup_preaudit_env(
    session: Session,
) -> tuple[Tenant, User, User, User, TenantFrameworkAdoption, CanonicalControl]:
    tenant, lead, _, _ = make_tenant(session, Role.COMPLIANCE_MANAGER)
    reviewer, _, _ = add_member(session, tenant, Role.REVIEWER)
    owner, _, _ = add_member(session, tenant, Role.OWNER)

    fw = Framework(slug="soc2-ops", name="SOC 2 Operations")
    session.add(fw)
    session.flush()

    fv = FrameworkVersion(
        framework_id=fw.id,
        version="2026.1",
        release_state=ReleaseState.RELEASED,
        created_by_user_id=lead.id,
    )
    session.add(fv)
    session.flush()

    ctrl = CanonicalControl(
        framework_version_id=fv.id,
        identifier="CC2.1",
        title="Access Control Verification",
        description="Automated access verification control",
        category="access",
    )
    session.add(ctrl)
    session.flush()

    adoption = TenantFrameworkAdoption(
        tenant_id=tenant.id,
        framework_id=fw.id,
        framework_version_id=fv.id,
        status=AdoptionStatus.ACTIVE,
        adopted_at=datetime.now(UTC),
        adopted_by_user_id=lead.id,
    )
    session.add(adoption)
    session.flush()

    evidence = EvidenceItem(
        tenant_id=tenant.id,
        title="Evidence for CC2.1",
        description="Verification logs",
        status=EvidenceStatus.VALID,
        classification=DataClassification.INTERNAL,
        owner_user_id=lead.id,
        version=1,
    )
    session.add(evidence)
    session.flush()

    ecl = EvidenceControlLink(
        tenant_id=tenant.id,
        evidence_id=evidence.id,
        control_type=ControlEntityType.CANONICAL,
        control_id=ctrl.id,
        linked_by_user_id=lead.id,
    )
    session.add(ecl)

    policy = Policy(
        tenant_id=tenant.id,
        title="Policy for CC2.1",
        description="Access policy",
        status=PolicyStatus.PUBLISHED,
        owner_user_id=lead.id,
        version=1,
    )
    session.add(policy)
    session.flush()

    pcl = PolicyControlLink(
        tenant_id=tenant.id,
        policy_id=policy.id,
        control_type=ControlEntityType.CANONICAL,
        control_id=ctrl.id,
        linked_by_user_id=lead.id,
    )
    session.add(pcl)
    session.flush()

    return tenant, lead, reviewer, owner, adoption, ctrl


def test_readiness_assessor_reviewer_tenant_approval_and_auto_suspension(
    session: Session, test_codec: EncryptedFieldCodec
) -> None:
    tenant, lead, reviewer, owner, adoption, ctrl = _setup_preaudit_env(session)
    preaudit_svc = PreAuditService(session)
    compliance_svc = ComplianceService(session, test_codec)

    lead_p = Principal(user_id=lead.id, is_platform_admin=False)
    lead_ctx = TenantContext(tenant_id=tenant.id, user_id=lead.id, role=Role.COMPLIANCE_MANAGER)

    reviewer_p = Principal(user_id=reviewer.id, is_platform_admin=False)
    reviewer_ctx = TenantContext(tenant_id=tenant.id, user_id=reviewer.id, role=Role.REVIEWER)

    owner_p = Principal(user_id=owner.id, is_platform_admin=False)
    owner_ctx = TenantContext(tenant_id=tenant.id, user_id=owner.id, role=Role.OWNER)

    # 1. Set control to IMPLEMENTED so checks pass
    compliance_svc.upsert_control_status(
        lead_p,
        lead_ctx,
        control_type=ControlEntityType.CANONICAL,
        control_id=ctrl.id,
        status=ControlImplementationStatus.IMPLEMENTED,
    )

    # 2. Create PreAudit and run checks
    pa = preaudit_svc.create_pre_audit(
        lead_p,
        lead_ctx,
        title="2026 Q3 Readiness Assessment",
        framework_adoption_id=adoption.id,
        lead_user_id=lead.id,
    )
    pa = preaudit_svc.run_checks(lead_p, lead_ctx, pa.id)

    # 3. Submit for review
    pa = preaudit_svc.submit_for_review(
        lead_p, lead_ctx, pa.id, reviewer_user_id=reviewer.id, expected_version=pa.version
    )

    # 4. Reviewer completes review (verifying canonical Reviewer has PREAUDIT_REVIEW capability)
    pa = preaudit_svc.complete_review(reviewer_p, reviewer_ctx, pa.id, expected_version=pa.version)
    assert pa.reviewed_at is not None

    # Reviewer cannot tenant-approve
    with pytest.raises(ReviewerConflictError):
        preaudit_svc.tenant_approve(reviewer_p, reviewer_ctx, pa.id, expected_version=pa.version)

    # Attempting to issue certificate before tenant approval must fail
    with pytest.raises(CertificateIssuanceBlockedError):
        preaudit_svc.issue_certificate(lead_p, lead_ctx, pa.id)

    # 5. Tenant Owner / Compliance Manager approves readiness
    pa = preaudit_svc.tenant_approve(owner_p, owner_ctx, pa.id, expected_version=pa.version)
    assert pa.tenant_approved_at is not None
    assert pa.tenant_approved_by_user_id == owner.id

    # 6. Issue certificate
    cert = preaudit_svc.issue_certificate(lead_p, lead_ctx, pa.id)
    assert cert.status == CertificateStatus.ACTIVE

    # 7. Material change trigger: Control regresses to NOT_STARTED -> Auto-suspends certificate
    compliance_svc.upsert_control_status(
        lead_p,
        lead_ctx,
        control_type=ControlEntityType.CANONICAL,
        control_id=ctrl.id,
        status=ControlImplementationStatus.NOT_STARTED,
        expected_version=1,
    )

    session.refresh(cert)
    assert cert.status == CertificateStatus.SUSPENDED
    assert "regressed to NOT_STARTED" in (cert.suspended_reason or "")

    # Re-implement control and clear checks to reinstate
    compliance_svc.upsert_control_status(
        lead_p,
        lead_ctx,
        control_type=ControlEntityType.CANONICAL,
        control_id=ctrl.id,
        status=ControlImplementationStatus.IMPLEMENTED,
        expected_version=2,
    )
    cert = preaudit_svc.reinstate_certificate(
        lead_p, lead_ctx, pa.id, cert.id, reason="Remediated control"
    )
    assert cert.status == CertificateStatus.ACTIVE

    # 8. Material change trigger: High severity finding raised on control -> Auto-suspends
    compliance_svc.create_finding(
        lead_p,
        lead_ctx,
        title="Unauthorized Admin Access Logged",
        description="Critical flaw in access control",
        severity=FindingSeverity.HIGH,
        control_type=ControlEntityType.CANONICAL,
        control_id=ctrl.id,
    )

    session.refresh(cert)
    assert cert.status == CertificateStatus.SUSPENDED
    assert "finding raised on control" in (cert.suspended_reason or "")
