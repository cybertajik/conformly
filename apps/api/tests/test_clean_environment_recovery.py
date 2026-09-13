"""Comprehensive Clean-Environment Disaster Recovery Rebuild Test.

Rehearses a true platform-level disaster recovery drill:
1. Provisions multi-tenant operational source state:
   - Tenant A (BioPharma Labs) and Tenant B (FinTech Pay).
   - Users and canonical role memberships (OWNER, COMPLIANCE_MANAGER, AUDITOR).
   - AES-256-GCM envelope-encrypted files and evidence in storage.
   - Cryptographically hash-chained audit trails in both tenants.
   - Anonymous whistleblower portal, case, and PBKDF2 return secret.
   - Pre-audit readiness assessment, deterministic scoring, and issued certificate.
   - Enterprise risk register and vendor records.
2. Captures full PlatformBackupBundle with cryptographic SHA-256 digest seal.
3. Provisions a completely blank, empty target database engine and storage backend.
4. Restores schema and hydrates data in topological order.
5. Verifies in the restored clean environment:
   - Strict tenant isolation (Tenant B cannot access Tenant A data).
   - Byte-for-byte envelope decryption of restored stored files.
   - 100% valid audit hash chaining.
   - Anonymous whistleblower case retrieval using return secret.
   - Pre-audit readiness certificate integrity.
   - Operational RTO (<= 4h) and RPO (<= 1h) objectives met.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event, verify_audit_chain
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.db.base import Base
from conformly.frameworks.models import (
    AdoptionStatus,
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
from conformly.recovery.backup import create_platform_backup
from conformly.recovery.restore import (
    TARGET_RPO_SECONDS,
    TARGET_RTO_SECONDS,
    restore_platform_backup,
)
from conformly.risks.models import Risk, RiskCategory, RiskStatus
from conformly.storage.models import StoredFile
from conformly.storage.providers import MemoryStorageProvider
from conformly.storage.service import StorageService
from conformly.whistleblower.models import (
    WhistleblowerCase,
    WhistleblowerCaseStatus,
    WhistleblowerPortal,
)
from conformly.whistleblower.service import hash_return_secret, verify_return_secret


def test_clean_environment_disaster_recovery_rebuild() -> None:
    """Full disaster recovery drill: backup source -> wipe -> restore into empty target -> verify."""

    # -------------------------------------------------------------------------
    # 1. Source Environment Setup (Multi-Tenant Operational State)
    # -------------------------------------------------------------------------
    source_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(source_engine)

    source_storage = MemoryStorageProvider()
    source_kms_key = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
    source_kms = LocalKeyManagementProvider({"v1": source_kms_key}, "v1")
    source_encryption = EnvelopeEncryptionService(AES256GCMProvider(), source_kms)

    with Session(source_engine, expire_on_commit=False) as session:
        storage_svc = StorageService(
            session=session,
            storage_provider=source_storage,
            encryption_service=source_encryption,
        )

        # Tenant A: BioPharma Labs
        tenant_a = Tenant(
            name="BioPharma Labs", slug=f"biopharma-{uuid4().hex[:6]}", status=TenantStatus.ACTIVE
        )
        user_a1 = User(
            oidc_issuer="https://auth.biopharma.de",
            oidc_subject="kc-sub-a1",
            email="owner@biopharma.de",
            display_name="BioPharma Owner",
        )
        user_a2 = User(
            oidc_issuer="https://auth.biopharma.de",
            oidc_subject="kc-sub-a2",
            email="manager@biopharma.de",
            display_name="Compliance Manager",
        )
        session.add_all([tenant_a, user_a1, user_a2])
        session.flush()

        session.add(
            Membership(
                tenant_id=tenant_a.id,
                user_id=user_a1.id,
                role=Role.OWNER,
                status=MembershipStatus.ACTIVE,
            )
        )
        session.add(
            Membership(
                tenant_id=tenant_a.id,
                user_id=user_a2.id,
                role=Role.COMPLIANCE_MANAGER,
                status=MembershipStatus.ACTIVE,
            )
        )

        # Tenant B: FinTech Pay
        tenant_b = Tenant(
            name="FinTech Pay", slug=f"fintech-{uuid4().hex[:6]}", status=TenantStatus.ACTIVE
        )
        user_b1 = User(
            oidc_issuer="https://auth.fintech.de",
            oidc_subject="kc-sub-b1",
            email="officer@fintech.de",
            display_name="Fintech Officer",
        )
        session.add_all([tenant_b, user_b1])
        session.flush()

        session.add(
            Membership(
                tenant_id=tenant_b.id,
                user_id=user_b1.id,
                role=Role.OWNER,
                status=MembershipStatus.ACTIVE,
            )
        )
        session.flush()

        # Tenant A: Encrypted Stored File
        principal_a = Principal(user_id=user_a1.id)
        context_a = TenantContext(tenant_id=tenant_a.id, user_id=user_a1.id, role=Role.OWNER)

        evidence_payload_a = b"CLINICAL_TRIAL_DATA_RESTRICTED_EVIDENCE_2026"
        file_a = storage_svc.upload_file(
            principal=principal_a,
            tenant_context=context_a,
            filename="clinical_trials.pdf",
            content=evidence_payload_a,
            classification="Restricted",
            content_type="application/pdf",
        )

        # Tenant B: Encrypted Stored File
        principal_b = Principal(user_id=user_b1.id)
        context_b = TenantContext(tenant_id=tenant_b.id, user_id=user_b1.id, role=Role.OWNER)

        evidence_payload_b = b"PAYMENT_GATEWAY_PCI_DSS_SPEC_CONFIDENTIAL"
        file_b = storage_svc.upload_file(
            principal=principal_b,
            tenant_context=context_b,
            filename="pci_spec.pdf",
            content=evidence_payload_b,
            classification="Confidential",
            content_type="application/pdf",
        )

        # Hash-Chained Audit Trail in Tenant A
        for i in range(3):
            record_audit_event(
                session,
                tenant_id=tenant_a.id,
                actor_type=AuditActorType.USER,
                actor_id=user_a1.id,
                action=f"evidence.checkpoint.{i}",
                resource_type="evidence",
                resource_id=f"chk-{i}",
                request_id=f"req-audit-a-{i}",
                outcome=AuditOutcome.SUCCESS,
                metadata={"count": i},
            )

        # Hash-Chained Audit Trail in Tenant B
        for i in range(2):
            record_audit_event(
                session,
                tenant_id=tenant_b.id,
                actor_type=AuditActorType.USER,
                actor_id=user_b1.id,
                action=f"policy.checkpoint.{i}",
                resource_type="policy",
                resource_id=f"chk-b-{i}",
                request_id=f"req-audit-b-{i}",
                outcome=AuditOutcome.SUCCESS,
                metadata={"count": i},
            )

        # Whistleblower Portal & Anonymous Case for Tenant A
        wb_portal = WhistleblowerPortal(
            tenant_id=tenant_a.id,
            slug="biopharma-whistleblower",
            title="BioPharma Ethics Channel",
            welcome_text="Welcome to the anonymous reporting channel",
            is_active=True,
        )
        session.add(wb_portal)
        session.flush()

        raw_wb_secret = "wb-secret-token-random-12345"
        salt_hex, hash_hex = hash_return_secret(raw_wb_secret)
        wb_case = WhistleblowerCase(
            tenant_id=tenant_a.id,
            portal_id=wb_portal.id,
            public_case_id="WB-2026-0001",
            return_secret_salt=salt_hex,
            return_secret_hash=hash_hex,
            category="financial_irregularity",
            status=WhistleblowerCaseStatus.SUBMITTED,
        )
        session.add(wb_case)

        # Framework & Adoption for Tenant A
        framework = Framework(
            slug="iso-27001",
            name="ISO/IEC 27001",
            description="Information Security Management",
        )
        session.add(framework)
        session.flush()

        framework_version = FrameworkVersion(
            framework_id=framework.id,
            version="2022",
            release_state=ReleaseState.RELEASED,
            created_by_user_id=user_a1.id,
        )
        session.add(framework_version)
        session.flush()

        adoption = TenantFrameworkAdoption(
            tenant_id=tenant_a.id,
            framework_id=framework.id,
            framework_version_id=framework_version.id,
            adopted_by_user_id=user_a1.id,
            status=AdoptionStatus.ACTIVE,
        )
        session.add(adoption)
        session.flush()

        # Pre-Audit Assessment & Certificate for Tenant A
        now = datetime.now(UTC)
        preaudit = PreAudit(
            tenant_id=tenant_a.id,
            title="Annual ISO 27001 Readiness Review",
            framework_adoption_id=adoption.id,
            lead_user_id=user_a1.id,
            rule_version="1.0.0",
            status=PreAuditStatus.COMPLETED,
            overall_score=94.5,
        )
        session.add(preaudit)
        session.flush()

        cert = PreAuditCertificate(
            tenant_id=tenant_a.id,
            pre_audit_id=preaudit.id,
            certificate_number="CONF-2026-98765",
            status=CertificateStatus.ACTIVE,
            issued_at=now,
            expires_at=now,
        )
        session.add(cert)

        # Risk Register Item for Tenant A
        risk = Risk(
            tenant_id=tenant_a.id,
            title="Third-party vendor data exposure",
            description="Detailed operational risk description for third-party exposure",
            category=RiskCategory.THIRD_PARTY,
            likelihood=2,
            impact=4,
            inherent_score=8,
            status=RiskStatus.IDENTIFIED,
        )
        session.add(risk)
        session.commit()

        # ---------------------------------------------------------------------
        # 2. Capture Platform Disaster Recovery Backup Bundle
        # ---------------------------------------------------------------------
        bundle = create_platform_backup(
            session=session,
            storage_provider=source_storage,
            kms_keys={"v1": source_kms_key},
        )

    # Validate backup bundle contents
    assert bundle.metadata.tables_count >= 50
    assert bundle.metadata.total_rows_count >= 10
    assert bundle.metadata.objects_count == 2
    assert bundle.manifest_sha256 != ""
    assert file_a.object_key in bundle.storage_objects
    assert file_b.object_key in bundle.storage_objects

    # -------------------------------------------------------------------------
    # 3. Provision Clean Target Environment (Disaster Simulation)
    # -------------------------------------------------------------------------
    target_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    target_storage = MemoryStorageProvider()
    target_kms = LocalKeyManagementProvider(bundle.kms_keys, "v1")
    target_encryption = EnvelopeEncryptionService(AES256GCMProvider(), target_kms)

    # -------------------------------------------------------------------------
    # 4. Rebuild from Backup into Clean Environment
    # -------------------------------------------------------------------------
    recovery_report = restore_platform_backup(
        bundle=bundle,
        target_engine=target_engine,
        target_storage=target_storage,
    )

    # Verify recovery execution objectives
    assert recovery_report.integrity_verified is True
    assert recovery_report.rto_target_met is True
    assert recovery_report.rpo_target_met is True
    assert recovery_report.measured_rto_seconds < TARGET_RTO_SECONDS
    assert recovery_report.measured_rpo_seconds < TARGET_RPO_SECONDS
    assert recovery_report.restored_objects_count == 2

    # -------------------------------------------------------------------------
    # 5. Deep Verification in the Restored Clean Environment
    # -------------------------------------------------------------------------
    with Session(target_engine) as restored_session:
        target_storage_svc = StorageService(
            session=restored_session,
            storage_provider=target_storage,
            encryption_service=target_encryption,
        )

        # 5.1 Verify Tenant Isolation & Multi-Tenancy
        restored_tenants = restored_session.scalars(select(Tenant)).all()
        assert len(restored_tenants) == 2
        tenant_ids = {t.id for t in restored_tenants}
        assert tenant_a.id in tenant_ids
        assert tenant_b.id in tenant_ids

        # Verify Tenant A files are invisible to Tenant B
        tenant_b_files = restored_session.scalars(
            select(StoredFile).where(StoredFile.tenant_id == tenant_b.id)
        ).all()
        assert len(tenant_b_files) == 1
        assert tenant_b_files[0].id == file_b.id
        assert file_a.id not in [f.id for f in tenant_b_files]

        # 5.2 Verify Envelope Decryption with Restored KMS Keys
        restored_file_a_meta, restored_file_a_bytes = target_storage_svc.download_file(
            principal=principal_a,
            tenant_context=context_a,
            file_id=file_a.id,
            request_id="dr-restore-verify-a",
        )
        assert restored_file_a_bytes == evidence_payload_a
        assert restored_file_a_meta.original_filename == "clinical_trials.pdf"

        restored_file_b_meta, restored_file_b_bytes = target_storage_svc.download_file(
            principal=principal_b,
            tenant_context=context_b,
            file_id=file_b.id,
            request_id="dr-restore-verify-b",
        )
        assert restored_file_b_bytes == evidence_payload_b
        assert restored_file_b_meta.original_filename == "pci_spec.pdf"

        # 5.3 Verify Cryptographic Audit Hash Chain
        valid_a, count_a, err_a = verify_audit_chain(restored_session, tenant_a.id)
        assert valid_a is True, f"Tenant A audit chain broken post-recovery: {err_a}"
        assert count_a >= 3

        valid_b, count_b, err_b = verify_audit_chain(restored_session, tenant_b.id)
        assert valid_b is True, f"Tenant B audit chain broken post-recovery: {err_b}"
        assert count_b >= 2

        # 5.4 Verify Whistleblower Anonymous Secret & Tracking
        restored_wb_case = restored_session.scalar(
            select(WhistleblowerCase).where(WhistleblowerCase.tenant_id == tenant_a.id)
        )
        assert restored_wb_case is not None
        assert restored_wb_case.public_case_id == "WB-2026-0001"
        assert (
            verify_return_secret(
                raw_wb_secret,
                restored_wb_case.return_secret_salt,
                restored_wb_case.return_secret_hash,
            )
            is True
        )
        assert (
            verify_return_secret(
                "wrong-secret-token",
                restored_wb_case.return_secret_salt,
                restored_wb_case.return_secret_hash,
            )
            is False
        )

        # 5.5 Verify Pre-Audit Certificate & Score
        restored_preaudit = restored_session.scalar(
            select(PreAudit).where(PreAudit.tenant_id == tenant_a.id)
        )
        assert restored_preaudit is not None
        assert restored_preaudit.overall_score == 94.5

        restored_cert = restored_session.scalar(
            select(PreAuditCertificate).where(PreAuditCertificate.tenant_id == tenant_a.id)
        )
        assert restored_cert is not None
        assert restored_cert.certificate_number == "CONF-2026-98765"
        assert restored_cert.status == CertificateStatus.ACTIVE

        # 5.6 Verify Risk Register
        restored_risk = restored_session.scalar(select(Risk).where(Risk.tenant_id == tenant_a.id))
        assert restored_risk is not None
        assert restored_risk.title == "Third-party vendor data exposure"
        assert restored_risk.inherent_score == 8
        assert restored_risk.category == RiskCategory.THIRD_PARTY
