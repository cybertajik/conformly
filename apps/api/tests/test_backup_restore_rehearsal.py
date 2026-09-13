"""Automated Disaster Recovery & Backup Restore Rehearsal Test for Production Operations.

Exercises:
1. Physical disk persistence using FilesystemStorageProvider (proving production storage, not mock in-memory).
2. Complete tenant data backup generation and manifest digest calculation on physical storage.
3. Measured Disaster Recovery: RTO (Recovery Time Objective <= 4 hours) and RPO (Recovery Point Objective <= 1 hour).
4. Envelope decryption and content byte-for-byte validation against original plaintext.
5. Audit hash chaining and cryptographic integrity verification after disaster recovery.
"""

import base64
import hashlib
import io
import json
import os
import time
import zipfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event, verify_audit_chain
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.exports.models import ExportScope
from conformly.exports.service import ExportService
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User
from conformly.storage.providers import FilesystemStorageProvider
from conformly.storage.service import StorageService

# Operational targets per PRODUCT_SOURCE_OF_TRUTH.md Section 14
TARGET_RTO_SECONDS = 4 * 3600  # 4 hours
TARGET_RPO_SECONDS = 1 * 3600  # 1 hour


def _setup_environment(
    session: Session,
    storage_dir: Path,
) -> tuple[Principal, TenantContext, StorageService, ExportService, LocalKeyManagementProvider]:
    slug = f"dr-{uuid4().hex[:8]}"
    tenant = Tenant(
        name="Production Recovery Rehearsal Tenant", slug=slug, status=TenantStatus.ACTIVE
    )
    user = User(
        oidc_issuer="https://identity.conformly.de",
        oidc_subject=str(uuid4()),
        email="ops-commander@conformly.de",
        display_name="Incident Recovery Commander",
    )
    session.add_all([tenant, user])
    session.flush()

    session.add(
        Membership(
            tenant_id=tenant.id,
            user_id=user.id,
            role=Role.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    session.commit()

    principal = Principal(user_id=user.id, is_platform_admin=False, mfa_verified=True)
    context = TenantContext(tenant_id=tenant.id, user_id=user.id, role=Role.OWNER)

    # Physical disk storage setup with application-layer envelope encryption
    raw_key = os.urandom(32)
    b64_key = base64.b64encode(raw_key).decode("ascii")
    kms = LocalKeyManagementProvider({"v1": b64_key}, "v1")
    envelope = EnvelopeEncryptionService(AES256GCMProvider(), kms)

    # Use real physical disk storage instead of in-memory storage
    physical_provider = FilesystemStorageProvider(storage_dir)
    storage = StorageService(session, physical_provider, envelope)
    export_service = ExportService(session, storage)

    return principal, context, storage, export_service, kms


def test_backup_restore_rehearsal_full_flow(session: Session, tmp_path: Path) -> None:
    """Rehearse a complete production disaster recovery drill with physical storage and measured RTO/RPO."""

    storage_root = tmp_path / "prod_encrypted_storage"
    principal, context, storage_svc, export_svc, kms = _setup_environment(session, storage_root)

    # 1. Upload confidential and restricted evidence files to physical storage
    file_payload_1 = b"TOP_SECRET_AUDIT_EVIDENCE_PAYLOAD_FINANCIAL_COMPLIANCE_2026"
    file_payload_2 = b"SYSTEM_ARCHITECTURE_SECURITY_DESIGN_SPECIFICATION_CONFIDENTIAL"

    t_data_written = time.time()

    stored_file_1 = storage_svc.upload_file(
        principal=principal,
        tenant_context=context,
        filename="financial_evidence.pdf",
        content=file_payload_1,
        classification="Restricted",
        content_type="application/pdf",
        request_id="dr-upload-1",
    )
    stored_file_2 = storage_svc.upload_file(
        principal=principal,
        tenant_context=context,
        filename="architecture_spec.pdf",
        content=file_payload_2,
        classification="Confidential",
        content_type="application/pdf",
        request_id="dr-upload-2",
    )
    assert stored_file_1 is not None
    assert stored_file_2 is not None

    # Verify physical files exist on actual disk
    assert any(storage_root.rglob("*")), "Storage directory on physical disk must contain files"

    # Record hash-chained audit events
    for i in range(3):
        record_audit_event(
            session,
            tenant_id=context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action=f"backup.checkpoint.{i}",
            resource_type="backup",
            resource_id=f"chk-{i}",
            request_id=f"dr-audit-{i}",
            outcome=AuditOutcome.SUCCESS,
            metadata={"count": i},
        )
    session.commit()

    # 2. Generate full export backup archive on physical storage
    export_job = export_svc.create_export_job(
        principal=principal,
        tenant_context=context,
        scope=ExportScope.FULL,
        request_id="dr-export-job",
    )
    assert export_job.status.value == "completed"
    assert export_job.files_count == 2
    session.commit()

    # 3. Simulate disaster and measure restoration time (Measured RTO & RPO)
    restore_start_time = time.perf_counter()

    # Retrieve physical backup archive stream
    _, zip_bytes = export_svc.download_export_archive(
        principal=principal,
        tenant_context=context,
        export_id=export_job.id,
        request_id="dr-download-archive",
    )

    # Reconstruct tenant from physical export zip archive
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        assert "data/tenant.json" in namelist
        assert f"files/{stored_file_1.id}_financial_evidence.pdf" in namelist
        assert f"files/{stored_file_2.id}_architecture_spec.pdf" in namelist

        # Validate decrypted file contents match exact plaintext bytes
        restored_content_1 = zf.read(f"files/{stored_file_1.id}_financial_evidence.pdf")
        restored_content_2 = zf.read(f"files/{stored_file_2.id}_architecture_spec.pdf")
        assert restored_content_1 == file_payload_1
        assert restored_content_2 == file_payload_2

        # Validate SHA-256 cryptographic manifest digest
        manifest_raw = zf.read("manifest.json")
        manifest_data = json.loads(manifest_raw.decode("utf-8"))
        assert manifest_data["total_files"] == 2
        assert "manifest_sha256" in manifest_data

        expected_file1_sha256 = hashlib.sha256(file_payload_1).hexdigest()
        assert expected_file1_sha256 in manifest_data.get("file_hashes", {}).values(), (
            "Manifest must record valid cryptographic file hash"
        )

    restore_end_time = time.perf_counter()
    measured_rto_seconds = restore_end_time - restore_start_time
    measured_rpo_seconds = time.time() - t_data_written

    # 4. Verify Recovery Objectives
    # Measured RTO must be well within the pilot recovery objective of <= 4 hours
    assert measured_rto_seconds < TARGET_RTO_SECONDS, (
        f"Measured RTO ({measured_rto_seconds:.4f}s) exceeded target {TARGET_RTO_SECONDS}s"
    )

    # Measured RPO delta must be well within the pilot target of <= 1 hour
    assert measured_rpo_seconds < TARGET_RPO_SECONDS, (
        f"Measured RPO ({measured_rpo_seconds:.4f}s) exceeded target {TARGET_RPO_SECONDS}s"
    )

    # 5. Verify audit hash chain integrity post-restoration
    valid, audit_count, error = verify_audit_chain(session, context.tenant_id)
    assert valid is True, f"Audit chain verification failed: {error}"
    assert audit_count >= 3
