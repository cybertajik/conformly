import base64
import io
import json
import os
import zipfile
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.authz.policy import AuthorizationDeniedError, Principal, TenantContext
from conformly.authz.roles import Role
from conformly.compliance.models import ComplianceTask, EvidenceFileLink, EvidenceItem, Policy
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.crypto.types import EncryptionContext
from conformly.exports.models import ExportJob, ExportJobStatus, ExportScope
from conformly.exports.service import (
    ExportExpiredError,
    ExportNotFoundError,
    ExportProcessingError,
    ExportService,
)
from conformly.identity.models import (
    Membership,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
)
from conformly.preaudit.models import PreAudit, PreAuditStatus
from conformly.profiles.models import PublicProfile
from conformly.storage.providers import MemoryStorageProvider
from conformly.storage.service import StorageService


def make_storage_service(session: Session) -> StorageService:
    raw_key = os.urandom(32)
    b64_key = base64.b64encode(raw_key).decode("ascii")
    enc = EnvelopeEncryptionService(
        AES256GCMProvider(), LocalKeyManagementProvider({"v1": b64_key}, "v1")
    )
    return StorageService(session, MemoryStorageProvider(), enc)


def create_test_tenant(
    session: Session, name: str, slug: str
) -> tuple[Tenant, User, Principal, TenantContext]:
    tenant = Tenant(
        id=uuid4(),
        name=name,
        slug=slug,
        status=TenantStatus.ACTIVE,
    )
    user = User(
        id=uuid4(),
        email=f"admin@{slug}.com",
        display_name="Admin User",
        oidc_issuer="https://issuer.example.com",
        oidc_subject=f"sub-{slug}",
    )
    membership = Membership(
        id=uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        role=Role.OWNER,
        status=MembershipStatus.ACTIVE,
    )
    session.add_all([tenant, user, membership])
    session.flush()

    principal = Principal(user_id=user.id, is_platform_admin=False)
    tenant_context = TenantContext(tenant_id=tenant.id, user_id=user.id, role=Role.OWNER)
    return tenant, user, principal, tenant_context


def test_create_export_packages_tenant_data_and_files(session: Session) -> None:
    storage = make_storage_service(session)
    export_service = ExportService(session, storage)

    tenant, user, principal, tenant_context = create_test_tenant(session, "Acme Corp", "acme-corp")

    # Seed data
    # 1. Stored File & Evidence
    original_content = b"Confidential security audit evidence document content 2026."
    stored_file = storage.upload_file(
        principal=principal,
        tenant_context=tenant_context,
        filename="soc2_evidence.pdf",
        content=original_content,
        classification="Restricted",
        content_type="application/pdf",
        request_id="req-upload",
    )
    evidence = EvidenceItem(
        id=uuid4(),
        tenant_id=tenant.id,
        owner_user_id=user.id,
        title="SOC 2 Penetration Test Evidence",
        description="Pen test results",
    )
    codec = EncryptedFieldCodec(storage.encryption)
    evidence.restricted_notes_encrypted = codec.encrypt_text(
        "restricted evidence note",
        EncryptionContext(
            tenant_id=tenant.id,
            resource_type="evidence_item",
            resource_id=str(evidence.id),
            field_name="restricted_notes",
        ),
    )
    link = EvidenceFileLink(
        id=uuid4(),
        tenant_id=tenant.id,
        evidence_id=evidence.id,
        file_id=stored_file.id,
        attached_by_user_id=user.id,
    )
    # 2. Policy
    policy = Policy(
        id=uuid4(),
        tenant_id=tenant.id,
        title="Information Security Policy",
        description="Core governance rules",
        version_string="1.0",
        content="All data must be encrypted with AES-256-GCM.",
        owner_user_id=user.id,
    )
    policy.restricted_content_encrypted = codec.encrypt_text(
        "restricted policy body",
        EncryptionContext(
            tenant_id=tenant.id,
            resource_type="policy",
            resource_id=str(policy.id),
            field_name="restricted_content",
        ),
    )
    # 3. Compliance task
    task = ComplianceTask(
        id=uuid4(),
        tenant_id=tenant.id,
        assignee_user_id=user.id,
        title="Quarterly Access Review",
        description="Verify user access levels",
        due_date=datetime.now(UTC) + timedelta(days=30),
    )
    # 4. Pre-audit
    pre_audit = PreAudit(
        id=uuid4(),
        tenant_id=tenant.id,
        title="ISO 27001 Readiness",
        description="Full ISO 27001 scope",
        status=PreAuditStatus.IN_PROGRESS,
        framework_adoption_id=uuid4(),
        lead_user_id=user.id,
        rule_version="1.0.0",
    )
    # 5. Public Profile
    pub_profile = PublicProfile(
        id=uuid4(),
        tenant_id=tenant.id,
        slug="acme-trust",
        display_name="Acme Security Trust Center",
        is_published=True,
    )
    session.add_all([evidence, link, policy, task, pre_audit, pub_profile])
    session.flush()

    # Trigger export
    job = export_service.create_export_job(
        principal=principal,
        tenant_context=tenant_context,
        scope=ExportScope.FULL,
        request_id="req-export-1",
    )

    assert job.status == ExportJobStatus.COMPLETED
    assert job.records_count > 0
    assert job.files_count == 1
    assert job.stored_file_id is not None
    assert job.sha256_hash is not None
    assert job.manifest is not None
    assert "acme-corp" in job.manifest.manifest_sha256 or len(job.manifest.manifest_sha256) == 64

    # Download and inspect ZIP archive
    _, zip_bytes = export_service.download_export_archive(
        principal=principal,
        tenant_context=tenant_context,
        export_id=job.id,
        request_id="req-dl",
    )

    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    file_list = zf.namelist()

    # Verify presence of all required artifacts
    assert "manifest.json" in file_list
    assert "data/tenant.json" in file_list
    assert "data/policies.json" in file_list
    assert "data/control_statuses.json" in file_list
    assert "data/evidence_control_links.json" in file_list
    assert "data/evidence_file_links.json" in file_list
    assert "data/policy_control_links.json" in file_list
    assert "data/compliance_tasks.json" in file_list
    assert "data/pre_audits.json" in file_list
    assert "data/pre_audit_scopes.json" in file_list
    assert "data/pre_audit_findings.json" in file_list
    assert "data/pre_audit_reports.json" in file_list
    assert "data/pre_audit_manifests.json" in file_list
    assert "data/public_profile.json" in file_list
    assert "data/audit_events.json" in file_list
    assert "reports/compliance_posture_report.md" in file_list
    assert "reports/pre_audit_readiness_report.md" in file_list
    assert "reports/data_inventory_manifest.md" in file_list

    # Verify manifest JSON contents
    manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
    assert manifest_data["tenant_slug"] == "acme-corp"
    assert manifest_data["total_records"] > 0
    assert manifest_data["total_files"] == 1
    assert manifest_data["audit_event_ids"]

    # Verify decrypted file content
    files_in_zip = [f for f in file_list if f.startswith("files/")]
    assert len(files_in_zip) == 1
    decrypted_content = zf.read(files_in_zip[0])
    assert decrypted_content == original_content
    policies = json.loads(zf.read("data/policies.json"))
    evidence_items = json.loads(zf.read("data/evidence_items.json"))
    assert policies[0]["restricted_content"] == "restricted policy body"
    assert evidence_items[0]["restricted_notes"] == "restricted evidence note"


def test_required_original_failure_marks_export_failed(session: Session) -> None:
    storage = make_storage_service(session)
    export_service = ExportService(session, storage)
    _, _, principal, context = create_test_tenant(session, "Broken Corp", "broken-corp")
    stored = storage.upload_file(
        principal,
        context,
        filename="required.pdf",
        content=b"required",
        classification="Restricted",
        content_type="application/pdf",
        request_id="upload",
    )
    storage.storage_provider.put_object(stored.object_key, b"corrupt")

    with pytest.raises(ExportProcessingError, match="Required original file"):
        export_service.create_export_job(
            principal, context, scope=ExportScope.FULL, request_id="export"
        )

    job = session.scalar(select(ExportJob).where(ExportJob.tenant_id == context.tenant_id))
    assert job is not None
    assert job.status == ExportJobStatus.FAILED
    assert job.stored_file_id is None
    assert str(stored.id) in (job.error_message or "")


def test_export_isolation_cross_tenant_denied(session: Session) -> None:
    storage = make_storage_service(session)
    export_service = ExportService(session, storage)

    tenant_a, _, principal_a, context_a = create_test_tenant(session, "Tenant A", "tenant-a")
    tenant_b, _, principal_b, context_b = create_test_tenant(session, "Tenant B", "tenant-b")

    job_a = export_service.create_export_job(
        principal=principal_a,
        tenant_context=context_a,
        scope=ExportScope.FULL,
        request_id="req-exp-a",
    )

    # Tenant B tries to get Tenant A's export job
    with pytest.raises(ExportNotFoundError):
        export_service.get_export_job(
            principal=principal_b,
            tenant_context=context_b,
            export_id=job_a.id,
        )

    # Tenant B tries to download Tenant A's export archive
    with pytest.raises(ExportNotFoundError):
        export_service.download_export_archive(
            principal=principal_b,
            tenant_context=context_b,
            export_id=job_a.id,
            request_id="req-b-snatch",
        )


def test_export_role_authorization_contributor_denied(session: Session) -> None:
    storage = make_storage_service(session)
    export_service = ExportService(session, storage)

    tenant, user, _, _ = create_test_tenant(session, "Corp", "corp")
    contributor_context = TenantContext(tenant_id=tenant.id, user_id=user.id, role=Role.CONTRIBUTOR)
    contributor_principal = Principal(user_id=user.id, is_platform_admin=False)

    with pytest.raises(AuthorizationDeniedError):
        export_service.create_export_job(
            principal=contributor_principal,
            tenant_context=contributor_context,
            scope=ExportScope.FULL,
            request_id="req-contrib",
        )


def test_expired_export_cannot_be_downloaded(session: Session) -> None:
    storage = make_storage_service(session)
    export_service = ExportService(session, storage)

    tenant, _, principal, context = create_test_tenant(session, "Old Corp", "old-corp")

    job = export_service.create_export_job(
        principal=principal,
        tenant_context=context,
        scope=ExportScope.FULL,
        request_id="req-exp-old",
    )

    # Fast forward beyond expiration
    job.expires_at = datetime.now(UTC) - timedelta(hours=1)
    session.flush()

    with pytest.raises(ExportExpiredError):
        export_service.download_export_archive(
            principal=principal,
            tenant_context=context,
            export_id=job.id,
            request_id="req-dl-late",
        )


def test_export_creation_is_idempotent_per_tenant_and_request(session: Session) -> None:
    storage = make_storage_service(session)
    service = ExportService(session, storage)
    tenant, _, principal, context = create_test_tenant(
        session, "Idempotent Corp", "idempotent-corp"
    )

    first = service.create_export_job(
        principal, context, scope=ExportScope.FULL, request_id="stable-request-id"
    )
    repeated = service.create_export_job(
        principal, context, scope=ExportScope.FULL, request_id="stable-request-id"
    )

    assert repeated.id == first.id
    jobs = session.scalars(select(ExportJob).where(ExportJob.tenant_id == tenant.id)).all()
    assert len(jobs) == 1

    with pytest.raises(ExportProcessingError, match="different export scope"):
        service.create_export_job(
            principal,
            context,
            scope=ExportScope.AUDIT_ONLY,
            request_id="stable-request-id",
        )
