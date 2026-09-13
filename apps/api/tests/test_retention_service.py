import base64
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.assets.models import Asset, AssetClassification, AssetType
from conformly.authz.policy import AuthorizationDeniedError, Principal, TenantContext
from conformly.authz.roles import Role
from conformly.compliance.models import ComplianceTask, Policy, UserNotificationPreference
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.entitlements.models import TenantEntitlement
from conformly.exports.service import ExportService
from conformly.identity.models import (
    Membership,
    MembershipInvitation,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
)
from conformly.notifications.models import NotificationOutbox
from conformly.organization.models import BusinessUnit, LegalEntity, Location
from conformly.preaudit.models import PreAudit, PreAuditStatus
from conformly.profiles.models import PublicProfile
from conformly.retention.jobs import run_retention_lifecycle
from conformly.retention.models import DeletionJob, DeletionJobState, DeletionReason
from conformly.retention.service import (
    CancellationError,
    DeletionJobNotFoundError,
    LegalHoldActiveError,
    RetentionService,
)
from conformly.risks.models import (
    Risk,
    RiskCategory,
    RiskStatus,
    RiskTreatment,
    RiskTreatmentStrategy,
)
from conformly.storage.models import StoredFile
from conformly.storage.providers import MemoryStorageProvider
from conformly.storage.service import StorageService
from conformly.vendors.models import Vendor, VendorCriticality


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
        email=f"owner@{slug}.com",
        display_name="Owner User",
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


def test_request_cancellation_success(session: Session) -> None:
    storage = make_storage_service(session)
    export_svc = ExportService(session, storage)
    retention_svc = RetentionService(session, storage, export_svc)

    tenant, user, principal, context = create_test_tenant(session, "Cancel Corp", "cancel-corp")
    now = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)

    updated_tenant = retention_svc.request_cancellation(
        principal=principal,
        tenant_context=context,
        reason="Migrating to custom on-premise infrastructure",
        confirm_slug="cancel-corp",
        request_id="req-cancel-1",
        now=now,
    )

    assert updated_tenant.status == TenantStatus.CANCELLING
    assert updated_tenant.cancellation_requested_at == now
    assert updated_tenant.export_until == now + timedelta(days=30)
    assert updated_tenant.deletion_due_at == now + timedelta(days=90)

    # Check scheduled deletion job
    job = session.scalar(select(DeletionJob).where(DeletionJob.tenant_id == tenant.id))
    assert job is not None
    assert job.reason == DeletionReason.CANCELLATION
    assert job.state == DeletionJobState.SCHEDULED
    assert job.scheduled_at == now + timedelta(days=90) or job.scheduled_at.replace(
        tzinfo=UTC
    ) == now + timedelta(days=90)

    # Check cancellation status
    status_info = retention_svc.get_cancellation_status(principal, context, now=now)
    assert status_info["status"] == "cancelling"
    assert status_info["is_export_window_active"] is True
    assert status_info["days_remaining_in_export_window"] == 30


def test_cancellation_slug_mismatch_rejected(session: Session) -> None:
    storage = make_storage_service(session)
    retention_svc = RetentionService(session, storage)

    tenant, _, principal, context = create_test_tenant(session, "Safe Corp", "safe-corp")

    with pytest.raises(CancellationError, match="Confirmation slug mismatch"):
        retention_svc.request_cancellation(
            principal=principal,
            tenant_context=context,
            reason="Accidental trigger",
            confirm_slug="wrong-slug",
            request_id="req-wrong",
        )


def test_cancellation_requires_owner_role(session: Session) -> None:
    storage = make_storage_service(session)
    retention_svc = RetentionService(session, storage)

    tenant, user, _, _ = create_test_tenant(session, "Role Corp", "role-corp")
    admin_context = TenantContext(tenant_id=tenant.id, user_id=user.id, role=Role.ADMINISTRATOR)
    admin_principal = Principal(user_id=user.id, is_platform_admin=False)

    with pytest.raises(AuthorizationDeniedError):
        retention_svc.request_cancellation(
            principal=admin_principal,
            tenant_context=admin_context,
            reason="Admin trying to cancel",
            confirm_slug="role-corp",
            request_id="req-admin-denied",
        )


def test_legal_hold_blocks_cancellation_and_pauses_deletion(session: Session) -> None:
    storage = make_storage_service(session)
    retention_svc = RetentionService(session, storage)

    tenant, _, principal, context = create_test_tenant(session, "Legal Corp", "legal-corp")

    # Set legal hold
    retention_svc.set_legal_hold(
        principal=principal,
        tenant_context=context,
        enabled=True,
        reason="Pending regulatory compliance inquiry",
        request_id="req-hold",
    )
    assert tenant.legal_hold is True

    # Cancellation should now be blocked
    with pytest.raises(LegalHoldActiveError):
        retention_svc.request_cancellation(
            principal=principal,
            tenant_context=context,
            reason="Trying to delete with hold",
            confirm_slug="legal-corp",
            request_id="req-fail-hold",
        )

    # If a deletion job exists, executing it with legal hold must fail
    job = DeletionJob(
        id=uuid4(),
        tenant_id=tenant.id,
        reason=DeletionReason.CANCELLATION,
        state=DeletionJobState.SCHEDULED,
        scheduled_at=datetime.now(UTC),
    )
    session.add(job)
    session.flush()

    with pytest.raises(LegalHoldActiveError):
        retention_svc.execute_deletion_job(
            job_id=job.id,
            operator_principal=principal,
            tenant_context=context,
        )

    assert job.state == DeletionJobState.ON_HOLD


def test_execute_deletion_job_purges_all_tables_and_generates_proof(session: Session) -> None:
    storage = make_storage_service(session)
    retention_svc = RetentionService(session, storage)

    tenant, user, principal, context = create_test_tenant(session, "Purge Corp", "purge-corp")

    # Upload file
    storage.upload_file(
        principal=principal,
        tenant_context=context,
        filename="to_purge.pdf",
        content=b"Delete me completely on day 90",
        classification="Restricted",
        content_type="application/pdf",
        request_id="req-upload",
    )

    # Seed records across multiple tables
    policy = Policy(
        id=uuid4(),
        tenant_id=tenant.id,
        title="Purge Policy",
        description="Policy to purge",
        owner_user_id=user.id,
    )
    task = ComplianceTask(
        id=uuid4(),
        tenant_id=tenant.id,
        assignee_user_id=user.id,
        title="Purge Task",
        description="Task to purge",
        due_date=datetime.now(UTC) + timedelta(days=30),
    )
    pre_audit = PreAudit(
        id=uuid4(),
        tenant_id=tenant.id,
        title="Purge PreAudit",
        description="Pre-audit scope",
        status=PreAuditStatus.IN_PROGRESS,
        framework_adoption_id=uuid4(),
        lead_user_id=user.id,
        rule_version="1.0.0",
    )
    pub_profile = PublicProfile(
        id=uuid4(),
        tenant_id=tenant.id,
        slug="purge-trust",
        display_name="Purge Trust",
    )
    invitation = MembershipInvitation(
        tenant_id=tenant.id,
        email="invitee@purge-corp.com",
        role=Role.CONTRIBUTOR,
        token_digest="a" * 64,
        invited_by_user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    preference = UserNotificationPreference(tenant_id=tenant.id, user_id=user.id)
    notification = NotificationOutbox(
        tenant_id=tenant.id,
        kind="retention.test",
        encrypted_payload={"ciphertext": "protected"},
        idempotency_key="retention-purge-test",
        available_at=datetime.now(UTC),
    )
    # Organization
    legal_entity = LegalEntity(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Purge Legal Entity",
        country="DE",
        is_primary=True,
    )
    business_unit = BusinessUnit(
        id=uuid4(),
        tenant_id=tenant.id,
        legal_entity_id=legal_entity.id,
        name="Purge Unit",
        code="PURGE",
    )
    location = Location(
        id=uuid4(),
        tenant_id=tenant.id,
        legal_entity_id=legal_entity.id,
        name="Purge Location",
        country="DE",
        city="Munich",
    )
    # Risk & Treatment
    risk = Risk(
        id=uuid4(),
        tenant_id=tenant.id,
        title="Purge Risk",
        description="Risk to be purged",
        category=RiskCategory.SECURITY,
        likelihood=3,
        impact=3,
        inherent_score=9,
        status=RiskStatus.IDENTIFIED,
        owner_user_id=user.id,
        legal_entity_id=legal_entity.id,
        business_unit_id=business_unit.id,
    )
    treatment = RiskTreatment(
        id=uuid4(),
        tenant_id=tenant.id,
        risk_id=risk.id,
        strategy=RiskTreatmentStrategy.MITIGATE,
        treatment_plan="Mitigate before purge",
        status="planned",
        owner_user_id=user.id,
    )
    # Asset & Vendor
    asset = Asset(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Purge Database Asset",
        asset_type=AssetType.DATA,
        classification=AssetClassification.RESTRICTED,
        encrypted_description={"algorithm": "AES-256-GCM", "ciphertext": "dummy"},
        owner_user_id=user.id,
        legal_entity_id=legal_entity.id,
        business_unit_id=business_unit.id,
    )
    vendor = Vendor(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Purge Vendor Inc.",
        service_description="Purge service provider",
        criticality=VendorCriticality.LOW,
        data_classification_accessed="Internal",
        country_residency="DE",
        dpa_signed=True,
        owner_user_id=user.id,
        legal_entity_id=legal_entity.id,
        business_unit_id=business_unit.id,
    )
    entitlement = session.scalar(
        select(TenantEntitlement).where(TenantEntitlement.tenant_id == tenant.id)
    )
    if entitlement is None:
        entitlement = TenantEntitlement(
            tenant_id=tenant.id,
            enabled_modules=["compliance"],
            allowed_framework_slugs=["*"],
        )
        session.add(entitlement)

    session.add_all(
        [
            policy,
            task,
            pre_audit,
            pub_profile,
            invitation,
            preference,
            notification,
            legal_entity,
            business_unit,
            location,
            risk,
            treatment,
            asset,
            vendor,
        ]
    )
    session.flush()

    job = DeletionJob(
        id=uuid4(),
        tenant_id=tenant.id,
        reason=DeletionReason.CANCELLATION,
        state=DeletionJobState.SCHEDULED,
        scheduled_at=datetime.now(UTC),
    )
    session.add(job)
    session.flush()

    # Execute permanent deletion
    proof = retention_svc.execute_deletion_job(
        job_id=job.id,
        operator_principal=principal,
        tenant_context=context,
        request_id="req-purge-exec",
    )

    assert proof is not None
    assert proof.tenant_id == tenant.id
    assert proof.deletion_job_id == job.id
    assert proof.storage_objects_purged >= 1
    assert len(proof.proof_manifest_sha256) == 64
    assert job.state == DeletionJobState.COMPLETED
    assert tenant.status == TenantStatus.DELETED

    # Verify proof receipts for all register, org, and entitlement tables
    assert proof.tables_purged["risk_treatments"] == 1
    assert proof.tables_purged["risks"] == 1
    assert proof.tables_purged["assets"] == 1
    assert proof.tables_purged["vendors"] == 1
    assert proof.tables_purged["locations"] == 1
    assert proof.tables_purged["business_units"] == 1
    assert proof.tables_purged["legal_entities"] == 1
    assert proof.tables_purged["tenant_entitlements"] >= 1

    # Verify operational records are completely purged
    assert session.scalar(select(Policy).where(Policy.tenant_id == tenant.id)) is None
    assert (
        session.scalar(select(ComplianceTask).where(ComplianceTask.tenant_id == tenant.id)) is None
    )
    assert session.scalar(select(PreAudit).where(PreAudit.tenant_id == tenant.id)) is None
    assert session.scalar(select(PublicProfile).where(PublicProfile.tenant_id == tenant.id)) is None
    assert session.scalar(select(StoredFile).where(StoredFile.tenant_id == tenant.id)) is None
    assert (
        session.scalar(
            select(MembershipInvitation).where(MembershipInvitation.tenant_id == tenant.id)
        )
        is None
    )
    assert (
        session.scalar(
            select(UserNotificationPreference).where(
                UserNotificationPreference.tenant_id == tenant.id
            )
        )
        is None
    )
    assert (
        session.scalar(select(NotificationOutbox).where(NotificationOutbox.tenant_id == tenant.id))
        is None
    )
    assert session.scalar(select(RiskTreatment).where(RiskTreatment.tenant_id == tenant.id)) is None
    assert session.scalar(select(Risk).where(Risk.tenant_id == tenant.id)) is None
    assert session.scalar(select(Asset).where(Asset.tenant_id == tenant.id)) is None
    assert session.scalar(select(Vendor).where(Vendor.tenant_id == tenant.id)) is None
    assert session.scalar(select(Location).where(Location.tenant_id == tenant.id)) is None
    assert session.scalar(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id)) is None
    assert session.scalar(select(LegalEntity).where(LegalEntity.tenant_id == tenant.id)) is None
    assert (
        session.scalar(select(TenantEntitlement).where(TenantEntitlement.tenant_id == tenant.id))
        is None
    )
    assert session.scalar(select(Membership).where(Membership.tenant_id == tenant.id)) is None


def test_deletion_rejects_early_wrong_tenant_and_unauthorized_execution(
    session: Session,
) -> None:
    storage = make_storage_service(session)
    service = RetentionService(session, storage)
    tenant, user, principal, context = create_test_tenant(session, "Due Corp", "due-corp")
    job = DeletionJob(
        tenant_id=tenant.id,
        reason=DeletionReason.CANCELLATION,
        state=DeletionJobState.SCHEDULED,
        scheduled_at=datetime.now(UTC) + timedelta(days=1),
    )
    session.add(job)
    session.flush()

    with pytest.raises(CancellationError, match="not due"):
        service.execute_deletion_job(job.id, operator_principal=principal, tenant_context=context)

    viewer_context = TenantContext(tenant_id=tenant.id, user_id=user.id, role=Role.VIEWER)
    with pytest.raises(AuthorizationDeniedError):
        service.execute_deletion_job(
            job.id, operator_principal=principal, tenant_context=viewer_context
        )

    _, _, foreign_principal, foreign_context = create_test_tenant(
        session, "Foreign Corp", "foreign-corp"
    )
    with pytest.raises(DeletionJobNotFoundError, match="not found"):
        service.execute_deletion_job(
            job.id,
            operator_principal=foreign_principal,
            tenant_context=foreign_context,
            now=datetime.now(UTC) + timedelta(days=2),
        )


def test_storage_failure_preserves_retry_metadata_and_no_proof(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = make_storage_service(session)
    service = RetentionService(session, storage)
    tenant, _, principal, context = create_test_tenant(session, "Retry Corp", "retry-corp")
    stored = storage.upload_file(
        principal,
        context,
        filename="retry.pdf",
        content=b"keep metadata",
        classification="Restricted",
        content_type="application/pdf",
        request_id="upload",
    )
    job = DeletionJob(
        tenant_id=tenant.id,
        reason=DeletionReason.CANCELLATION,
        state=DeletionJobState.SCHEDULED,
        scheduled_at=datetime.now(UTC),
    )
    session.add(job)
    session.flush()

    def fail_delete(_key: str) -> None:
        raise OSError("storage unavailable")

    monkeypatch.setattr(storage.storage_provider, "delete_object", fail_delete)
    with pytest.raises(CancellationError, match="storage unavailable"):
        service.execute_deletion_job(job.id, operator_principal=principal, tenant_context=context)

    assert job.state == DeletionJobState.SCHEDULED
    assert session.get(StoredFile, stored.id) is not None
    assert job.proof_id is None


def test_retention_lifecycle_suspends_then_deletes_idempotently(session: Session) -> None:
    storage = make_storage_service(session)
    service = RetentionService(session, storage)
    tenant, _, principal, context = create_test_tenant(session, "Lifecycle Corp", "lifecycle-corp")
    requested_at = datetime(2026, 1, 1, tzinfo=UTC)
    service.request_cancellation(
        principal,
        context,
        reason="Tenant exit rehearsal",
        confirm_slug=tenant.slug,
        request_id="cancel-lifecycle",
        now=requested_at,
    )

    after_window = run_retention_lifecycle(
        session,
        storage,
        tenant_id=tenant.id,
        now=requested_at + timedelta(days=31),
    )
    assert after_window.suspended_tenants == 1
    assert after_window.completed_deletions == 0
    assert tenant.status == TenantStatus.SUSPENDED

    repeated = run_retention_lifecycle(
        session,
        storage,
        tenant_id=tenant.id,
        now=requested_at + timedelta(days=31),
    )
    assert repeated.suspended_tenants == 0

    due = run_retention_lifecycle(
        session,
        storage,
        tenant_id=tenant.id,
        now=requested_at + timedelta(days=90),
    )
    assert due.completed_deletions == 1
    deleted_tenant = session.get(Tenant, tenant.id)
    assert deleted_tenant is not None
    assert deleted_tenant.status == TenantStatus.DELETED

    final = run_retention_lifecycle(
        session,
        storage,
        tenant_id=tenant.id,
        now=requested_at + timedelta(days=91),
    )
    assert final.completed_deletions == 0
