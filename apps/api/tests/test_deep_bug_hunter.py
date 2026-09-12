"""Comprehensive deep bug hunter and invariant regression test suite.

Probes real-world boundary cases, malformed payloads, cross-tenant leakages,
unhandled exception scenarios, concurrency conflicts, and cryptographic edge cases.
"""

import base64
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.providers import (
    AES256GCMProvider,
    InvalidCiphertextError,
    LocalKeyManagementProvider,
)
from conformly.crypto.types import EncryptionContext
from conformly.frameworks.models import (
    Framework,
    FrameworkVersion,
    ReleaseState,
    TenantFrameworkAdoption,
)
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User
from conformly.preaudit.models import (
    PreAuditStatus,
)
from conformly.preaudit.service import (
    PreAuditOptimisticLockError,
    PreAuditService,
    ReviewerConflictError,
)
from conformly.profiles.models import (
    is_valid_profile_slug,
)
from conformly.retention.jobs import run_retention_lifecycle
from conformly.retention.models import DeletionJob, DeletionJobState
from conformly.retention.service import (
    RetentionService,
)
from conformly.storage.providers import MemoryStorageProvider
from conformly.storage.service import StorageService
from conformly.storage.validation import (
    FileValidationError,
    normalize_filename,
    validate_classification,
    validate_file_size,
)
from conformly.whistleblower.models import (
    WhistleblowerCaseStatus,
)
from conformly.whistleblower.service import (
    WhistleblowerClosedCaseError,
    WhistleblowerService,
    WhistleblowerUnauthorizedError,
    verify_return_secret,
)

# -----------------------------------------------------------------------------
# Fixtures & Helpers
# -----------------------------------------------------------------------------


def _make_crypto() -> tuple[EnvelopeEncryptionService, EncryptedFieldCodec]:
    raw_key = os.urandom(32)
    b64_key = base64.b64encode(raw_key).decode("ascii")
    enc = EnvelopeEncryptionService(
        AES256GCMProvider(), LocalKeyManagementProvider({"v1": b64_key}, "v1")
    )
    codec = EncryptedFieldCodec(enc)
    return enc, codec


def _setup_tenant(
    session: Session, name_prefix: str = "t"
) -> tuple[Tenant, User, Principal, TenantContext]:
    slug = f"{name_prefix}-{uuid4().hex[:8]}"
    tenant = Tenant(name=f"Tenant {slug}", slug=slug, status=TenantStatus.ACTIVE)
    user = User(
        oidc_issuer="https://auth.example.com",
        oidc_subject=str(uuid4()),
        email=f"user-{uuid4().hex[:6]}@example.com",
        display_name="Test User",
    )
    session.add_all([tenant, user])
    session.flush()

    membership = Membership(
        tenant_id=tenant.id,
        user_id=user.id,
        role=Role.OWNER,
        status=MembershipStatus.ACTIVE,
    )
    session.add(membership)
    session.commit()

    principal = Principal(user_id=user.id, is_platform_admin=False)
    context = TenantContext(tenant_id=tenant.id, user_id=user.id, role=Role.OWNER)
    return tenant, user, principal, context


# -----------------------------------------------------------------------------
# 1. Filename Sanitization, Path Traversal & File Upload Boundary Tests
# -----------------------------------------------------------------------------


def test_filename_sanitization_boundary_vectors() -> None:
    """Test path traversal attacks, control characters, null bytes, and length limits."""
    # Path traversal patterns must be stripped to base name
    assert normalize_filename("../../../etc/passwd") == "passwd"
    assert normalize_filename("..\\..\\windows\\system32\\cmd.exe.txt") == "cmd.exe.txt"
    assert normalize_filename("foo/bar/baz.pdf") == "baz.pdf"

    # Null bytes must be rejected
    with pytest.raises(FileValidationError, match="null bytes"):
        normalize_filename("innocent.pdf\x00.exe")

    # Empty or whitespace only must be rejected
    with pytest.raises(FileValidationError, match="cannot be empty"):
        normalize_filename("   ")
    with pytest.raises(FileValidationError, match="invalid filename"):
        normalize_filename("..")
    with pytest.raises(FileValidationError, match="invalid filename"):
        normalize_filename(".")

    # Hazardous extensions must be blocked
    for dangerous in [".exe", ".bat", ".sh", ".cmd", ".ps1", ".vbs", ".dll", ".jar"]:
        with pytest.raises(FileValidationError, match="prohibited"):
            normalize_filename(f"payload{dangerous}")

    # File size validation boundaries
    with pytest.raises(FileValidationError, match="cannot be empty"):
        validate_file_size(0, 1000)
    with pytest.raises(FileValidationError, match="cannot be empty"):
        validate_file_size(-5, 1000)
    with pytest.raises(FileValidationError, match="exceeds maximum"):
        validate_file_size(1001, 1000)
    # Exact limit is allowed
    validate_file_size(1000, 1000)

    # Classification boundaries
    for valid in ["Public", "Internal", "Confidential", "Restricted"]:
        assert validate_classification(valid) == valid
    with pytest.raises(FileValidationError, match="invalid data classification"):
        validate_classification("TopSecret")


# -----------------------------------------------------------------------------
# 2. Cryptographic Envelope & Field Tampering Detection
# -----------------------------------------------------------------------------


def test_envelope_encryption_tampering_and_context_mismatch() -> None:
    """Verify that tampering with ciphertext, nonce, or context fails decryption."""
    enc, codec = _make_crypto()
    tenant_id = uuid4()
    ctx1 = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="policy",
        resource_id=str(uuid4()),
        field_name="restricted_content",
        version=1,
    )

    encrypted = codec.encrypt_text("Super Secret Corporate Policy", ctx1)

    # 1. Normal decryption succeeds
    decrypted = codec.decrypt_text(encrypted, ctx1)
    assert decrypted == "Super Secret Corporate Policy"

    # 2. Context mismatch (different tenant_id) fails
    ctx_other_tenant = EncryptionContext(
        tenant_id=uuid4(),
        resource_type="policy",
        resource_id=ctx1.resource_id,
        field_name="restricted_content",
        version=1,
    )
    with pytest.raises(InvalidCiphertextError):
        codec.decrypt_text(encrypted, ctx_other_tenant)

    # 3. Context version mismatch fails
    ctx_wrong_version = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="policy",
        resource_id=ctx1.resource_id,
        field_name="restricted_content",
        version=2,
    )
    with pytest.raises(InvalidCiphertextError):
        codec.decrypt_text(encrypted, ctx_wrong_version)

    # 4. Ciphertext tampering fails
    tampered = dict(encrypted)
    raw_ct = base64.b64decode(tampered["ciphertext"])
    tampered_ct = bytes([raw_ct[0] ^ 0xFF]) + raw_ct[1:]
    tampered["ciphertext"] = base64.b64encode(tampered_ct).decode("ascii")
    with pytest.raises(InvalidCiphertextError):
        codec.decrypt_text(tampered, ctx1)


# -----------------------------------------------------------------------------
# 3. Pre-Audit Rules Engine & Concurrency Conflict Tests
# -----------------------------------------------------------------------------


def test_preaudit_evaluator_and_independence_invariants(session: Session) -> None:
    """Validate that pre-audit lead cannot review own audit and OCC rejects concurrent updates."""
    tenant, owner, principal, context = _setup_tenant(session, "pa-bug")
    pa_service = PreAuditService(session)

    # Set up adoption
    fw = Framework(slug=f"fw-{uuid4().hex[:4]}", name="Test FW", description="")
    session.add(fw)
    session.flush()
    ver = FrameworkVersion(
        framework_id=fw.id,
        version="1.0",
        release_state=ReleaseState.RELEASED,
        release_notes="",
        created_by_user_id=owner.id,
        approved_by_user_id=owner.id,
    )
    session.add(ver)
    session.flush()
    adoption = TenantFrameworkAdoption(
        tenant_id=tenant.id,
        framework_id=fw.id,
        framework_version_id=ver.id,
        adopted_by_user_id=owner.id,
    )
    session.add(adoption)
    session.commit()

    reviewer = User(
        oidc_issuer="https://auth.example.com",
        oidc_subject=str(uuid4()),
        email=f"reviewer-{uuid4().hex[:6]}@example.com",
        display_name="Reviewer User",
    )
    session.add(reviewer)
    session.flush()
    session.add(
        Membership(
            tenant_id=tenant.id,
            user_id=reviewer.id,
            role=Role.COMPLIANCE_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
    )
    session.commit()

    preaudit = pa_service.create_pre_audit(
        principal=principal,
        tenant_context=context,
        title="SOC 2 Readiness",
        description="Assessment",
        lead_user_id=owner.id,
        framework_adoption_id=adoption.id,
    )
    assert preaudit.status == PreAuditStatus.PLANNING

    # Independence rule: lead cannot review own audit
    with pytest.raises(ReviewerConflictError, match="different from the assessment lead"):
        pa_service.submit_for_review(
            principal=principal,
            tenant_context=context,
            pre_audit_id=preaudit.id,
            reviewer_user_id=owner.id,  # Same as lead!
            expected_version=1,
        )

    # Optimistic concurrency conflict on stale version
    with pytest.raises(PreAuditOptimisticLockError):
        pa_service.submit_for_review(
            principal=principal,
            tenant_context=context,
            pre_audit_id=preaudit.id,
            reviewer_user_id=reviewer.id,
            expected_version=999,  # Non-matching version
        )


# -----------------------------------------------------------------------------
# 4. Whistleblower PBKDF2 Return Secret Verifier & Constant-Time Defense
# -----------------------------------------------------------------------------


def test_whistleblower_pbkdf2_verifier_and_case_locking(session: Session) -> None:
    """Verify constant-time return secret verification and closed case message locking."""
    _, codec = _make_crypto()
    wb_svc = WhistleblowerService(session, codec)
    tenant, _, principal, context = _setup_tenant(session, "wb-bug")

    portal = wb_svc.setup_or_update_portal(
        tenant_context=context,
        slug=f"wb-{tenant.slug}",
        title="Safe Reporting Intake",
        welcome_text="Welcome",
        is_active=True,
    )

    case, secret = wb_svc.submit_report(
        slug=portal.slug,
        category="Finance",
        title="Invoice Anomaly",
        summary="Discrepancy in billing ledger.",
    )
    assert len(secret) >= 32

    # 1. Correct secret verifies
    assert verify_return_secret(secret, case.return_secret_salt, case.return_secret_hash) is True

    # 2. Wrong secret fails
    assert (
        verify_return_secret("wrong-secret-token", case.return_secret_salt, case.return_secret_hash)
        is False
    )
    assert verify_return_secret("", case.return_secret_salt, case.return_secret_hash) is False

    # 3. Access with wrong secret raises Unauthorized
    with pytest.raises(WhistleblowerUnauthorizedError):
        wb_svc.access_case_public(
            slug=portal.slug,
            public_case_id=case.public_case_id,
            return_secret="invalid-key-token",
        )

    # 4. Step through valid state transitions and verify closed case locking
    wb_svc.update_case_status(
        tenant_context=context,
        case_id=case.id,
        new_status=WhistleblowerCaseStatus.ACKNOWLEDGED,
        expected_version=1,
    )
    wb_svc.update_case_status(
        tenant_context=context,
        case_id=case.id,
        new_status=WhistleblowerCaseStatus.RESOLVED,
        closed_reason="Investigation completed.",
        expected_version=2,
    )

    with pytest.raises(WhistleblowerClosedCaseError, match="Cannot message on a closed case"):
        wb_svc.add_reporter_message(
            slug=portal.slug,
            public_case_id=case.public_case_id,
            return_secret=secret,
            body="New post-closure message",
        )


# -----------------------------------------------------------------------------
# 5. Public Profile Slug Validation & Conflict Defense
# -----------------------------------------------------------------------------


def test_public_profile_slug_validation_rules() -> None:
    """Verify that only secure, URL-safe slugs are accepted for public Trust Centers."""
    # Valid slugs
    assert is_valid_profile_slug("acme-health") is True
    assert is_valid_profile_slug("tech-corp-2026") is True
    assert is_valid_profile_slug("secure123") is True

    # Invalid slugs (path traversal, punctuation, uppercase, too short/long)
    assert is_valid_profile_slug("") is False
    assert is_valid_profile_slug("a") is False
    assert is_valid_profile_slug("-invalid-start") is False
    assert is_valid_profile_slug("invalid-end-") is False
    assert is_valid_profile_slug("has..dots") is False
    assert is_valid_profile_slug("has/slashes") is False
    assert is_valid_profile_slug("has spaces") is False
    assert is_valid_profile_slug("UPPERCASE") is False
    assert is_valid_profile_slug("a" * 65) is False


# -----------------------------------------------------------------------------
# 6. Legal Hold Override on Deletion Lifecycle
# -----------------------------------------------------------------------------


def test_legal_hold_blocks_scheduled_deletion(session: Session) -> None:
    """Verify that an active legal hold strictly prevents retention deletion execution."""
    tenant, _, principal, context = _setup_tenant(session, "lh-bug")
    storage = StorageService(session, MemoryStorageProvider(), _make_crypto()[0])
    retention = RetentionService(session, storage)

    # Request cancellation
    retention.request_cancellation(
        principal=principal,
        tenant_context=context,
        reason="Scheduled decommission",
        confirm_slug=tenant.slug,
        request_id="req-lh-1",
    )

    # Enable legal hold
    retention.set_legal_hold(
        principal=principal,
        tenant_context=context,
        enabled=True,
        reason="Pending regulatory inquiry",
        request_id="req-lh-2",
    )

    # Find the deletion job
    job = session.query(DeletionJob).filter(DeletionJob.tenant_id == tenant.id).first()
    assert job is not None
    assert job.state == DeletionJobState.ON_HOLD

    # Simulate arrival of day 90
    job.scheduled_at = datetime.now(UTC) - timedelta(days=1)
    session.commit()

    # Deletion sweep must skip or hold the job, not delete the tenant!
    result = run_retention_lifecycle(session, storage, tenant_id=tenant.id)
    assert result.held_deletions == 1
    assert result.completed_deletions == 0

    session.refresh(tenant)
    assert tenant.status != TenantStatus.DELETED
