import base64
import os
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditEvent
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.providers import (
    AES256GCMProvider,
    InvalidCiphertextError,
    LocalKeyManagementProvider,
)
from conformly.crypto.types import EncryptedPayload, EncryptionContext
from conformly.identity.models import (
    Membership,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
    UserStatus,
)
from conformly.storage.models import StoredFile, StoredFileStatus
from conformly.storage.providers import MemoryStorageProvider
from conformly.storage.service import (
    StorageFileNotFoundError,
    StorageIntegrityError,
    StorageService,
)


def make_encryption() -> EnvelopeEncryptionService:
    raw_key = os.urandom(32)
    b64_key = base64.b64encode(raw_key).decode("ascii")
    return EnvelopeEncryptionService(
        AES256GCMProvider(), LocalKeyManagementProvider({"v1": b64_key}, "v1")
    )


def create_tenant_and_user(
    session: Session, role: Role = Role.OWNER
) -> tuple[Tenant, User, TenantContext, Principal]:
    tenant_id = uuid4()
    user_id = uuid4()

    tenant = Tenant(
        id=tenant_id,
        name="Test Tenant",
        slug=f"tenant-{tenant_id.hex[:8]}",
        status=TenantStatus.ACTIVE,
    )
    user = User(
        id=user_id,
        oidc_issuer="https://issuer.example.com",
        oidc_subject=f"sub-{user_id.hex[:8]}",
        email=f"user-{user_id.hex[:8]}@example.com",
        display_name="Test User",
        status=UserStatus.ACTIVE,
    )
    membership = Membership(
        tenant_id=tenant_id,
        user_id=user_id,
        role=role,
        status=MembershipStatus.ACTIVE,
    )
    session.add_all([tenant, user, membership])
    session.commit()

    principal = Principal(user_id=user_id)
    tenant_context = TenantContext(tenant_id=tenant_id, user_id=user_id, role=role)
    return tenant, user, tenant_context, principal


def test_upload_and_download_round_trip(session: Session) -> None:
    _, _, tenant_context, principal = create_tenant_and_user(session, Role.OWNER)
    storage_provider = MemoryStorageProvider()
    encryption = make_encryption()
    service = StorageService(session, storage_provider, encryption)

    plaintext = b"Highly confidential compliance evidence document"
    uploaded = service.upload_file(
        principal,
        tenant_context,
        filename="evidence.pdf",
        content=plaintext,
        classification="Restricted",
        content_type="application/pdf",
        request_id="req-upload-1",
    )
    session.commit()

    assert uploaded.original_filename == "evidence.pdf"
    assert uploaded.classification == "Restricted"
    assert uploaded.plaintext_size_bytes == len(plaintext)
    assert uploaded.status == StoredFileStatus.ACTIVE

    # Verify stored object in storage provider is NEVER plaintext
    stored_bytes = storage_provider.get_object(uploaded.object_key)
    assert stored_bytes != plaintext
    assert plaintext not in stored_bytes
    assert stored_bytes == bytes.fromhex(uploaded.ciphertext_sha256) or len(stored_bytes) > 0

    # Download file and verify decrypted plaintext matches original
    file_record, downloaded_bytes = service.download_file(
        principal, tenant_context, file_id=uploaded.id, request_id="req-dl-1"
    )
    assert downloaded_bytes == plaintext
    assert file_record.id == uploaded.id


def test_ciphertext_tampering_detected(session: Session) -> None:
    _, _, tenant_context, principal = create_tenant_and_user(session, Role.OWNER)
    storage_provider = MemoryStorageProvider()
    encryption = make_encryption()
    service = StorageService(session, storage_provider, encryption)

    plaintext = b"Original document before tampering"
    uploaded = service.upload_file(
        principal,
        tenant_context,
        filename="tamper_test.txt",
        content=plaintext,
        classification="Confidential",
        content_type="text/plain",
        request_id="req-tamper-1",
    )
    session.commit()

    # Tamper with stored object in the storage provider
    stored_bytes = bytearray(storage_provider.get_object(uploaded.object_key))
    stored_bytes[0] ^= 0xFF  # flip bits
    storage_provider.put_object(uploaded.object_key, bytes(stored_bytes))

    # Download must fail integrity verification
    with pytest.raises(StorageIntegrityError, match="tampering detected"):
        service.download_file(
            principal, tenant_context, file_id=uploaded.id, request_id="req-tamper-dl"
        )


def test_aead_tag_and_context_mismatch_detected(session: Session) -> None:
    _, _, tenant_context, principal = create_tenant_and_user(session, Role.OWNER)
    storage_provider = MemoryStorageProvider()
    encryption = make_encryption()
    service = StorageService(session, storage_provider, encryption)

    plaintext = b"Test context binding"
    uploaded = service.upload_file(
        principal,
        tenant_context,
        filename="context_test.txt",
        content=plaintext,
        classification="Internal",
        content_type="text/plain",
        request_id="req-ctx-1",
    )
    session.commit()

    # Attempt decrypting with a different tenant_id context
    wrong_context = EncryptionContext(
        tenant_id=uuid4(),
        resource_type="stored_file",
        resource_id=str(uploaded.id),
        field_name="file_content",
        version=1,
    )
    payload = EncryptedPayload(
        algorithm="AES-256-GCM",
        context_version=1,
        key_version=uploaded.key_version,
        wrapped_dek_nonce=bytes.fromhex(uploaded.wrapped_dek_nonce),
        wrapped_dek=bytes.fromhex(uploaded.wrapped_dek),
        nonce=bytes.fromhex(uploaded.ciphertext_nonce),
        ciphertext=storage_provider.get_object(uploaded.object_key),
    )
    with pytest.raises(InvalidCiphertextError):
        encryption.decrypt(payload, wrong_context)


def test_cross_tenant_file_access_denied(session: Session) -> None:
    _, _, tenant_a_context, principal_a = create_tenant_and_user(session, Role.OWNER)
    _, _, tenant_b_context, principal_b = create_tenant_and_user(session, Role.OWNER)

    storage_provider = MemoryStorageProvider()
    encryption = make_encryption()
    service = StorageService(session, storage_provider, encryption)

    uploaded_a = service.upload_file(
        principal_a,
        tenant_a_context,
        filename="tenant_a_secret.pdf",
        content=b"Tenant A proprietary data",
        classification="Restricted",
        content_type="application/pdf",
        request_id="req-iso-1",
    )
    session.commit()

    # Tenant B attempts to get metadata of Tenant A's file
    with pytest.raises(StorageFileNotFoundError):
        service.get_file_metadata(principal_b, tenant_b_context, file_id=uploaded_a.id)

    # Tenant B attempts to download Tenant A's file
    with pytest.raises(StorageFileNotFoundError):
        service.download_file(
            principal_b, tenant_b_context, file_id=uploaded_a.id, request_id="req-iso-2"
        )

    # Tenant B attempts to delete Tenant A's file
    with pytest.raises(StorageFileNotFoundError):
        service.delete_file(
            principal_b, tenant_b_context, file_id=uploaded_a.id, request_id="req-iso-3"
        )


def test_file_deletion_and_storage_eviction(session: Session) -> None:
    _, _, tenant_context, principal = create_tenant_and_user(session, Role.OWNER)
    storage_provider = MemoryStorageProvider()
    encryption = make_encryption()
    service = StorageService(session, storage_provider, encryption)

    uploaded = service.upload_file(
        principal,
        tenant_context,
        filename="delete_me.txt",
        content=b"Temporary file content",
        classification="Internal",
        content_type="text/plain",
        request_id="req-del-1",
    )
    session.commit()

    object_key = uploaded.object_key
    assert storage_provider.object_exists(object_key)

    # Delete file
    service.delete_file(principal, tenant_context, file_id=uploaded.id, request_id="req-del-2")
    session.commit()

    service.finalize_pending_deletions(principal, tenant_context, request_id="cleanup")
    session.commit()

    # Verify object evicted from storage provider
    assert not storage_provider.object_exists(object_key)

    # Verify subsequent retrieval fails
    with pytest.raises(StorageFileNotFoundError):
        service.get_file_metadata(principal, tenant_context, file_id=uploaded.id)

    with pytest.raises(StorageFileNotFoundError):
        service.download_file(
            principal, tenant_context, file_id=uploaded.id, request_id="req-del-3"
        )

    # DB record preserved as DELETED for compliance audit
    db_record = session.get(StoredFile, uploaded.id)
    assert db_record is not None
    assert db_record.status == StoredFileStatus.DELETED
    assert db_record.deleted_at is not None


def test_partial_failure_cleans_up_storage_object(session: Session) -> None:
    _, _, tenant_context, principal = create_tenant_and_user(session, Role.OWNER)
    storage_provider = MemoryStorageProvider()
    encryption = make_encryption()
    service = StorageService(session, storage_provider, encryption)

    # Inject DB failure by simulating flush error
    from unittest.mock import patch

    with patch.object(session, "flush", side_effect=RuntimeError("DB write failed")):
        with pytest.raises(RuntimeError, match="DB write failed"):
            service.upload_file(
                principal,
                tenant_context,
                filename="failed_upload.txt",
                content=b"data that should not remain stored",
                classification="Public",
                content_type="text/plain",
                request_id="req-fail-1",
            )

    # Assert storage provider has NO orphaned objects
    assert len(storage_provider._store) == 0


def test_audit_events_emitted_without_secrets(session: Session) -> None:
    _, _, tenant_context, principal = create_tenant_and_user(session, Role.OWNER)
    storage_provider = MemoryStorageProvider()
    encryption = make_encryption()
    service = StorageService(session, storage_provider, encryption)

    uploaded = service.upload_file(
        principal,
        tenant_context,
        filename="audit_check.pdf",
        content=b"confidential payload",
        classification="Restricted",
        content_type="application/pdf",
        request_id="req-aud-1",
    )
    service.download_file(principal, tenant_context, file_id=uploaded.id, request_id="req-aud-2")
    service.delete_file(principal, tenant_context, file_id=uploaded.id, request_id="req-aud-3")
    session.commit()

    events = list(
        session.scalars(
            select(AuditEvent)
            .where(AuditEvent.tenant_id == tenant_context.tenant_id)
            .order_by(AuditEvent.occurred_at.asc())
        ).all()
    )

    actions = [e.action for e in events]
    assert "file.uploaded" in actions
    assert "file.downloaded" in actions
    assert "file.deletion_requested" in actions

    for event in events:
        metadata_str = str(event.safe_metadata)
        assert "confidential payload" not in metadata_str
        assert "dek" not in metadata_str
        assert "secret" not in metadata_str
