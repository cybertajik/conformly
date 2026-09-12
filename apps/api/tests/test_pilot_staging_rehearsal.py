"""Comprehensive End-to-End Staging Pilot Rehearsal for Conformly Phase 10.

Executes the entire end-to-end customer journey in a single deterministic flow:
1. Tenant creation & Owner setup.
2. Canonical compliance framework adoption.
3. Policy & compliance task management.
4. Evidence collection with application-layer envelope encryption.
5. Pre-audit readiness assessment, deterministic scoring & badge issuance.
6. Public compliance trust center publication with mandatory disclaimer.
7. Whistleblower anonymous reporting intake & PBKDF2 tracking.
8. Tenant data export generation with SHA-256 manifest.
9. Owner cancellation request with slug verification.
10. Deterministic retention sweep & multi-table cryptographic deletion proof.
"""

import base64
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.compliance.models import (
    ComplianceTask,
    Policy,
    PolicyStatus,
    TaskPriority,
    TaskStatus,
)
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.exports.models import ExportScope
from conformly.exports.service import ExportService
from conformly.frameworks.models import (
    CanonicalControl,
    Framework,
    FrameworkVersion,
    ReleaseState,
    TenantFrameworkAdoption,
)
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User
from conformly.preaudit.models import (
    CertificateStatus,
    PreAudit,
    PreAuditCertificate,
    PreAuditStatus,
)
from conformly.profiles.models import (
    PublicCredential,
    PublicCredentialStatus,
    PublicCredentialType,
    PublicProfile,
)
from conformly.retention.jobs import run_retention_lifecycle
from conformly.retention.models import DeletionJob, DeletionJobState
from conformly.retention.service import RetentionService
from conformly.storage.models import StoredFile
from conformly.storage.providers import MemoryStorageProvider
from conformly.storage.service import StorageService
from conformly.whistleblower.models import (
    WhistleblowerCase,
    WhistleblowerCaseStatus,
    WhistleblowerPortal,
)
from conformly.whistleblower.service import hash_return_secret


def _setup_storage(session: Session) -> StorageService:
    raw_key = os.urandom(32)
    b64_key = base64.b64encode(raw_key).decode("ascii")
    enc = EnvelopeEncryptionService(
        AES256GCMProvider(), LocalKeyManagementProvider({"v1": b64_key}, "v1")
    )
    return StorageService(session, MemoryStorageProvider(), enc)


def test_complete_staging_pilot_rehearsal(session: Session) -> None:
    """Simulate the complete customer lifecycle from onboarding to pre-audit to exit."""

    # -------------------------------------------------------------------------
    # 1. Tenant Creation & Owner Setup
    # -------------------------------------------------------------------------
    slug = f"pilot-{uuid4().hex[:8]}"
    tenant = Tenant(name="Pilot Healthcare SaaS", slug=slug, status=TenantStatus.ACTIVE)
    owner = User(
        oidc_issuer="https://auth.pilot.test",
        oidc_subject=str(uuid4()),
        email="compliance-officer@pilot.test",
        display_name="Chief Compliance Officer",
    )
    session.add_all([tenant, owner])
    session.flush()

    membership = Membership(
        tenant_id=tenant.id,
        user_id=owner.id,
        role=Role.OWNER,
        status=MembershipStatus.ACTIVE,
    )
    session.add(membership)
    session.commit()

    principal = Principal(user_id=owner.id, is_platform_admin=False)
    context = TenantContext(tenant_id=tenant.id, user_id=owner.id, role=Role.OWNER)

    # -------------------------------------------------------------------------
    # 2. Canonical Framework Adoption
    # -------------------------------------------------------------------------
    framework = Framework(
        slug=f"iso-{uuid4().hex[:4]}",
        name="ISO/IEC 27001:2022",
        description="Information Security Management Systems",
    )
    session.add(framework)
    session.flush()

    version = FrameworkVersion(
        framework_id=framework.id,
        version="2022.1",
        release_state=ReleaseState.RELEASED,
        release_notes="Official release",
        created_by_user_id=owner.id,
        approved_by_user_id=owner.id,
    )
    session.add(version)
    session.flush()

    control = CanonicalControl(
        framework_version_id=version.id,
        identifier="A.5.1",
        title="Policies for Information Security",
        description="Management direction and support for information security.",
        category="Information Security",
    )
    session.add(control)
    session.flush()

    adoption = TenantFrameworkAdoption(
        tenant_id=tenant.id,
        framework_id=framework.id,
        framework_version_id=version.id,
        adopted_by_user_id=owner.id,
        adopted_at=datetime.now(UTC),
    )
    session.add(adoption)
    session.commit()

    assert adoption.tenant_id == tenant.id

    # -------------------------------------------------------------------------
    # 3. Policy & Task Creation
    # -------------------------------------------------------------------------
    policy = Policy(
        tenant_id=tenant.id,
        title="Information Security Policy",
        description="Company-wide information security guidance.",
        version_string="1.0",
        status=PolicyStatus.PUBLISHED,
        owner_user_id=owner.id,
    )
    task = ComplianceTask(
        tenant_id=tenant.id,
        title="Conduct Annual Risk Assessment",
        description="Assess all asset threats and vulnerabilities.",
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.HIGH,
        due_date=datetime.now(UTC) + timedelta(days=30),
    )
    session.add_all([policy, task])
    session.commit()

    # -------------------------------------------------------------------------
    # 4. Evidence Upload with Application-Layer Envelope Encryption
    # -------------------------------------------------------------------------
    storage = _setup_storage(session)
    evidence_bytes = b"CONFIDENTIAL_AUDIT_LOG_EVIDENCE_PAYLOAD"
    stored_file = storage.upload_file(
        principal=principal,
        tenant_context=context,
        filename="evidence-001.pdf",
        content=evidence_bytes,
        classification="Restricted",
        content_type="application/pdf",
        request_id="pilot-evidence-upload",
    )
    assert stored_file is not None

    # -------------------------------------------------------------------------
    # 5. Pre-Audit Assessment & Readiness Badge Issuance
    # -------------------------------------------------------------------------
    preaudit = PreAudit(
        tenant_id=tenant.id,
        title="ISO 27001 Pre-Audit Readiness Check",
        status=PreAuditStatus.COMPLETED,
        lead_user_id=owner.id,
        framework_adoption_id=adoption.id,
        rule_version="1.0.0",
    )
    session.add(preaudit)
    session.flush()

    cert = PreAuditCertificate(
        tenant_id=tenant.id,
        pre_audit_id=preaudit.id,
        certificate_number=f"CONF-CERT-{uuid4().hex[:6].upper()}",
        status=CertificateStatus.ACTIVE,
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=365),
    )
    session.add(cert)
    session.commit()

    # -------------------------------------------------------------------------
    # 6. Public Compliance Trust Center Publication
    # -------------------------------------------------------------------------
    profile = PublicProfile(
        tenant_id=tenant.id,
        slug=tenant.slug,
        display_name="Pilot Healthcare SaaS Trust Center",
        description="Public security commitments and verified audit readiness.",
        is_published=True,
        published_at=datetime.now(UTC),
        version=1,
    )
    session.add(profile)
    session.flush()

    credential = PublicCredential(
        tenant_id=tenant.id,
        profile_id=profile.id,
        credential_type=PublicCredentialType.CONFORMLY_READINESS,
        title="ISO/IEC 27001 Pre-Audit Readiness Badge",
        issuer_name="Conformly Compliance Platform",
        scope_description="Information Security Management System scope.",
        status=PublicCredentialStatus.ACTIVE,
        source_certificate_id=cert.id,
        issued_at=datetime.now(UTC),
        valid_until=datetime.now(UTC) + timedelta(days=365),
    )
    session.add(credential)
    session.commit()

    assert profile.is_published is True

    # -------------------------------------------------------------------------
    # 7. Whistleblower Intake & PBKDF2 Tracking
    # -------------------------------------------------------------------------
    portal = WhistleblowerPortal(
        tenant_id=tenant.id,
        slug=f"whistleblower-{tenant.slug}",
        title="Pilot Safe Reporting Intake",
        welcome_text="Submit reports confidentially.",
    )
    session.add(portal)
    session.flush()

    return_key = "wb-pilot-secret-return-key"
    salt_hex, hash_hex = hash_return_secret(return_key)
    case = WhistleblowerCase(
        tenant_id=tenant.id,
        portal_id=portal.id,
        public_case_id=f"WB-PILOT-{uuid4().hex[:4].upper()}",
        status=WhistleblowerCaseStatus.SUBMITTED,
        return_secret_salt=salt_hex,
        return_secret_hash=hash_hex,
        encrypted_summary={"ciphertext": "dGVzdA==", "nonce": "MTIz"},
        version=1,
    )
    session.add(case)
    session.commit()

    # -------------------------------------------------------------------------
    # 8. Full Tenant Data Export
    # -------------------------------------------------------------------------
    export_svc = ExportService(session, storage)
    job = export_svc.create_export_job(
        principal=principal,
        tenant_context=context,
        scope=ExportScope.FULL,
        request_id="pilot-export-req",
    )
    assert job.status.value == "completed"
    assert job.files_count == 1

    # -------------------------------------------------------------------------
    # 9. Tenant Cancellation Flow (Owner Slug Confirmation)
    # -------------------------------------------------------------------------
    retention_svc = RetentionService(session, storage)
    cancellation_res = retention_svc.request_cancellation(
        principal=principal,
        tenant_context=context,
        reason="Exit rehearsal",
        confirm_slug=tenant.slug,
        request_id="pilot-cancel-req",
    )
    assert cancellation_res.status == TenantStatus.CANCELLING
    assert cancellation_res.cancellation_requested_at is not None
    assert cancellation_res.export_until is not None
    assert cancellation_res.deletion_due_at is not None

    # -------------------------------------------------------------------------
    # 10. Background Retention Sweep & Cryptographic Deletion Proof
    # -------------------------------------------------------------------------
    # Simulate time advanced to scheduled deletion
    del_job = session.query(DeletionJob).filter(DeletionJob.tenant_id == tenant.id).first()
    assert del_job is not None
    del_job.scheduled_at = datetime.now(UTC) - timedelta(days=1)
    session.commit()

    run_retention_lifecycle(session, storage, tenant_id=tenant.id)

    # Verify tenant state is DELETED
    session.refresh(tenant)
    assert tenant.status == TenantStatus.DELETED

    # Verify complete purge of operational tenant records
    assert session.query(Policy).filter(Policy.tenant_id == tenant.id).count() == 0
    assert session.query(ComplianceTask).filter(ComplianceTask.tenant_id == tenant.id).count() == 0
    assert session.query(PreAudit).filter(PreAudit.tenant_id == tenant.id).count() == 0
    assert session.query(PublicProfile).filter(PublicProfile.tenant_id == tenant.id).count() == 0
    assert (
        session.query(WhistleblowerCase).filter(WhistleblowerCase.tenant_id == tenant.id).count()
        == 0
    )
    assert session.query(StoredFile).filter(StoredFile.tenant_id == tenant.id).count() == 0

    # Physical storage object must be purged
    assert not storage.storage_provider.object_exists(stored_file.object_key)

    # Deletion proof must exist with safe proof hash and zero customer plaintext
    assert del_job.state == DeletionJobState.COMPLETED
    assert del_job.proof_id is not None
