import hashlib
import secrets
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import AuthorizationDeniedError, Principal, TenantContext, authorize
from conformly.authz.roles import Capability
from conformly.config import get_settings
from conformly.crypto.envelope import EnvelopeEncryptionService, get_envelope_encryption_service
from conformly.crypto.types import EncryptedPayload, EncryptionContext
from conformly.db.session import get_db
from conformly.storage.models import StoredFile, StoredFileStatus
from conformly.storage.providers import StorageProvider, get_storage_provider
from conformly.storage.validation import (
    MalwareDetectedError,
    MalwareScanner,
    ProductionMalwareScanner,
    normalize_content_type,
    normalize_filename,
    validate_classification,
    validate_file_size,
)
from conformly.tenancy.rls import set_rls_context


class StorageIntegrityError(Exception):
    """Raised when stored file ciphertext or plaintext hash fails integrity verification."""


class StorageFileNotFoundError(Exception):
    """Raised when a file cannot be found in the current tenant scope."""


class LegalHoldActiveError(Exception):
    """Raised when an operation is blocked due to an active legal hold."""


class FileQuarantinedError(MalwareDetectedError):
    """Raised when an operation is attempted on a quarantined file."""


class StorageService:
    """Manages encrypted file lifecycle, metadata persistence, and access audits."""

    def __init__(
        self,
        session: Session,
        storage_provider: StorageProvider,
        encryption_service: EnvelopeEncryptionService,
        malware_scanner: MalwareScanner | None = None,
        max_file_size_bytes: int | None = None,
    ) -> None:
        self.session = session
        self.storage_provider = storage_provider
        self.encryption = encryption_service
        self.malware_scanner = malware_scanner or ProductionMalwareScanner()
        self.max_file_size = max_file_size_bytes or get_settings().max_file_size_bytes

    def upload_file(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        filename: str,
        content: bytes | None = None,
        data_stream: Any | None = None,
        classification: str,
        content_type: str | None,
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> StoredFile:
        current_time = now or datetime.now(UTC)
        req_id = request_id or str(uuid4())

        if content is None:
            if data_stream is not None:
                content = data_stream.read()
            else:
                content = b""

        try:
            authorize(principal, tenant_context, Capability.FILE_WRITE)
        except AuthorizationDeniedError:
            record_audit_event(
                self.session,
                tenant_id=tenant_context.tenant_id,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="file.upload_denied",
                resource_type="stored_file",
                resource_id=None,
                request_id=req_id,
                outcome=AuditOutcome.DENIED,
                metadata={"reason": "capability_denied"},
                occurred_at=current_time,
            )
            raise

        clean_filename = normalize_filename(filename)
        validate_file_size(len(content), self.max_file_size)
        clean_classification = validate_classification(classification)
        clean_content_type = normalize_content_type(content_type)

        try:
            self.malware_scanner.scan(content, clean_filename)
        except MalwareDetectedError as exc:
            file_id = uuid4()
            plaintext_sha256 = hashlib.sha256(content).hexdigest()
            context = EncryptionContext(
                tenant_id=tenant_context.tenant_id,
                resource_type="stored_file",
                resource_id=str(file_id),
                field_name="quarantine_content",
                version=1,
            )
            payload = self.encryption.encrypt(content, context)
            ciphertext_sha256 = hashlib.sha256(payload.ciphertext).hexdigest()
            random_token = secrets.token_hex(16)
            object_key = (
                f"tenants/{tenant_context.tenant_id}/quarantine/{file_id}/{random_token}.enc"
            )
            self.storage_provider.put_object(
                object_key, payload.ciphertext, content_type="application/octet-stream"
            )
            settings = get_settings()
            stored_file = StoredFile(
                id=file_id,
                tenant_id=tenant_context.tenant_id,
                created_by_user_id=principal.user_id,
                original_filename=clean_filename,
                content_type=clean_content_type,
                classification=clean_classification,
                plaintext_size_bytes=len(content),
                ciphertext_size_bytes=len(payload.ciphertext),
                plaintext_sha256=plaintext_sha256,
                ciphertext_sha256=ciphertext_sha256,
                storage_backend=settings.storage_backend,
                object_key=object_key,
                encryption_algorithm=payload.algorithm,
                context_version=payload.context_version,
                key_version=payload.key_version,
                wrapped_dek_nonce=payload.wrapped_dek_nonce.hex(),
                wrapped_dek=payload.wrapped_dek.hex(),
                ciphertext_nonce=payload.nonce.hex(),
                status=StoredFileStatus.QUARANTINED,
                quarantine_reason=str(exc),
            )
            set_rls_context(
                self.session,
                tenant_id=tenant_context.tenant_id,
                user_id=principal.user_id,
                tenant_verified=True,
            )
            self.session.add(stored_file)
            self.session.flush()

            record_audit_event(
                self.session,
                tenant_id=tenant_context.tenant_id,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="file.quarantined",
                resource_type="stored_file",
                resource_id=str(file_id),
                request_id=req_id,
                outcome=AuditOutcome.DENIED,
                metadata={
                    "file_id": str(file_id),
                    "filename": clean_filename,
                    "quarantine_reason": str(exc),
                },
                occurred_at=current_time,
            )
            raise FileQuarantinedError(str(exc)) from exc

        file_id = uuid4()
        plaintext_sha256 = hashlib.sha256(content).hexdigest()

        context = EncryptionContext(
            tenant_id=tenant_context.tenant_id,
            resource_type="stored_file",
            resource_id=str(file_id),
            field_name="file_content",
            version=1,
        )

        payload = self.encryption.encrypt(content, context)
        ciphertext_sha256 = hashlib.sha256(payload.ciphertext).hexdigest()

        from conformly.entitlements.service import check_storage_limit

        check_storage_limit(
            self.session, tenant_context.tenant_id, additional_bytes=len(payload.ciphertext)
        )

        random_token = secrets.token_hex(16)
        object_key = f"tenants/{tenant_context.tenant_id}/files/{file_id}/{random_token}.enc"

        # Store ciphertext in storage provider
        self.storage_provider.put_object(
            object_key, payload.ciphertext, content_type="application/octet-stream"
        )

        settings = get_settings()
        stored_file = StoredFile(
            id=file_id,
            tenant_id=tenant_context.tenant_id,
            created_by_user_id=principal.user_id,
            original_filename=clean_filename,
            content_type=clean_content_type,
            classification=clean_classification,
            plaintext_size_bytes=len(content),
            ciphertext_size_bytes=len(payload.ciphertext),
            plaintext_sha256=plaintext_sha256,
            ciphertext_sha256=ciphertext_sha256,
            storage_backend=settings.storage_backend,
            object_key=object_key,
            encryption_algorithm=payload.algorithm,
            context_version=payload.context_version,
            key_version=payload.key_version,
            wrapped_dek_nonce=payload.wrapped_dek_nonce.hex(),
            wrapped_dek=payload.wrapped_dek.hex(),
            ciphertext_nonce=payload.nonce.hex(),
            status=StoredFileStatus.ACTIVE,
        )

        try:
            set_rls_context(
                self.session,
                tenant_id=tenant_context.tenant_id,
                user_id=principal.user_id,
                tenant_verified=True,
            )
            self.session.add(stored_file)
            self.session.flush()

            record_audit_event(
                self.session,
                tenant_id=tenant_context.tenant_id,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="file.uploaded",
                resource_type="stored_file",
                resource_id=str(file_id),
                request_id=req_id,
                outcome=AuditOutcome.SUCCESS,
                metadata={
                    "classification": clean_classification,
                    "content_type": clean_content_type,
                    "file_id": str(file_id),
                    "filename": clean_filename,
                    "sha256": plaintext_sha256,
                    "size_bytes": len(content),
                },
                occurred_at=current_time,
            )
        except Exception:
            # Idempotently clean up uploaded object to prevent orphaned storage
            self.storage_provider.delete_object(object_key)
            raise

        return stored_file

    def get_file_metadata(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        file_id: UUID,
    ) -> StoredFile:
        authorize(principal, tenant_context, Capability.FILE_READ)
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )
        file = self.session.scalar(
            select(StoredFile).where(
                StoredFile.tenant_id == tenant_context.tenant_id,
                StoredFile.id == file_id,
            )
        )
        if file is None or file.status == StoredFileStatus.DELETED:
            raise StorageFileNotFoundError(f"file not found: {file_id}")
        if file.status == StoredFileStatus.QUARANTINED:
            raise FileQuarantinedError("file is quarantined due to detected malware")
        if file.status != StoredFileStatus.ACTIVE:
            raise StorageFileNotFoundError(f"file not found: {file_id}")
        return file

    def download_file(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        file_id: UUID,
        request_id: str,
        now: datetime | None = None,
    ) -> tuple[StoredFile, bytes]:
        current_time = now or datetime.now(UTC)

        try:
            authorize(principal, tenant_context, Capability.FILE_READ)
        except AuthorizationDeniedError:
            record_audit_event(
                self.session,
                tenant_id=tenant_context.tenant_id,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="file.download_denied",
                resource_type="stored_file",
                resource_id=str(file_id),
                request_id=request_id,
                outcome=AuditOutcome.DENIED,
                metadata={"file_id": str(file_id), "reason": "capability_denied"},
                occurred_at=current_time,
            )
            raise

        stored_file = self.get_file_metadata(principal, tenant_context, file_id=file_id)

        ciphertext = self.storage_provider.get_object(stored_file.object_key)

        # Integrity check: verify ciphertext hash
        if hashlib.sha256(ciphertext).hexdigest() != stored_file.ciphertext_sha256:
            raise StorageIntegrityError("ciphertext hash mismatch; possible tampering detected")

        # Decrypt payload
        context = EncryptionContext(
            tenant_id=tenant_context.tenant_id,
            resource_type="stored_file",
            resource_id=str(file_id),
            field_name="file_content",
            version=stored_file.context_version,
        )

        payload = EncryptedPayload(
            algorithm="AES-256-GCM",
            context_version=stored_file.context_version,
            key_version=stored_file.key_version,
            wrapped_dek_nonce=bytes.fromhex(stored_file.wrapped_dek_nonce),
            wrapped_dek=bytes.fromhex(stored_file.wrapped_dek),
            nonce=bytes.fromhex(stored_file.ciphertext_nonce),
            ciphertext=ciphertext,
        )

        plaintext = self.encryption.decrypt(payload, context)

        # Integrity check: verify plaintext hash
        if hashlib.sha256(plaintext).hexdigest() != stored_file.plaintext_sha256:
            raise StorageIntegrityError("decrypted plaintext hash mismatch")

        record_audit_event(
            self.session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="file.downloaded",
            resource_type="stored_file",
            resource_id=str(file_id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "file_id": str(file_id),
                "filename": stored_file.original_filename,
                "size_bytes": stored_file.plaintext_size_bytes,
            },
            occurred_at=current_time,
        )

        return stored_file, plaintext

    def delete_file(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        file_id: UUID | None = None,
        *,
        request_id: str | None = None,
        now: datetime | None = None,
        **kwargs: Any,
    ) -> None:
        target_file_id = file_id or kwargs.get("file_id")
        if target_file_id is None:
            raise ValueError("file_id is required")
        current_time = now or datetime.now(UTC)
        req_id = request_id or str(uuid4())

        try:
            authorize(principal, tenant_context, Capability.FILE_DELETE)
        except AuthorizationDeniedError:
            record_audit_event(
                self.session,
                tenant_id=tenant_context.tenant_id,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="file.delete_denied",
                resource_type="stored_file",
                resource_id=str(target_file_id),
                request_id=req_id,
                outcome=AuditOutcome.DENIED,
                metadata={"file_id": str(target_file_id), "reason": "capability_denied"},
                occurred_at=current_time,
            )
            raise

        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )
        stored_file = self.session.scalar(
            select(StoredFile)
            .where(
                StoredFile.id == target_file_id,
                StoredFile.tenant_id == tenant_context.tenant_id,
                StoredFile.status.in_([StoredFileStatus.ACTIVE, StoredFileStatus.DELETE_PENDING]),
            )
            .with_for_update()
        )
        if stored_file is None:
            raise StorageFileNotFoundError("file not found")
        if stored_file.status == StoredFileStatus.DELETE_PENDING:
            return

        from conformly.compliance.models import EvidenceFileLink, EvidenceItem

        held = self.session.scalar(
            select(EvidenceItem.id)
            .join(EvidenceFileLink, EvidenceFileLink.evidence_id == EvidenceItem.id)
            .where(
                EvidenceFileLink.file_id == target_file_id,
                EvidenceFileLink.tenant_id == tenant_context.tenant_id,
                EvidenceItem.legal_hold.is_(True),
            )
            .limit(1)
        )
        if held is not None:
            raise LegalHoldActiveError(
                "Cannot delete file attached to evidence under active legal hold"
            )

        # Commit this durable intent before irreversible object deletion.
        stored_file.status = StoredFileStatus.DELETE_PENDING
        stored_file.deleted_at = current_time
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="file.deletion_requested",
            resource_type="stored_file",
            resource_id=str(target_file_id),
            request_id=req_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "file_id": str(target_file_id),
                "filename": stored_file.original_filename,
            },
            occurred_at=current_time,
        )

    def finalize_pending_deletions(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        request_id: str,
        file_id: UUID | None = None,
    ) -> int:
        """Retry durable deletion intents; caller commits completion or rolls back on failure."""
        if self.session.in_transaction():
            raise RuntimeError("Commit deletion intents before removing objects")
        authorize(principal, tenant_context, Capability.FILE_DELETE)
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )
        query = select(StoredFile).where(
            StoredFile.tenant_id == tenant_context.tenant_id,
            StoredFile.status == StoredFileStatus.DELETE_PENDING,
        )
        if file_id is not None:
            query = query.where(StoredFile.id == file_id)
        files = list(self.session.scalars(query.with_for_update(skip_locked=True).limit(100)))
        for stored_file in files:
            self.storage_provider.delete_object(stored_file.object_key)
            stored_file.status = StoredFileStatus.DELETED
            record_audit_event(
                self.session,
                tenant_id=tenant_context.tenant_id,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="file.deleted",
                resource_type="stored_file",
                resource_id=str(stored_file.id),
                request_id=request_id,
                outcome=AuditOutcome.SUCCESS,
                metadata={"file_id": str(stored_file.id)},
            )
        self.session.flush()
        return len(files)

    def quarantine_file(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        file_id: UUID,
        reason: str,
        request_id: str,
    ) -> StoredFile:
        authorize(principal, tenant_context, Capability.FILE_WRITE)
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )
        file = self.session.scalar(
            select(StoredFile).where(
                StoredFile.id == file_id,
                StoredFile.tenant_id == tenant_context.tenant_id,
            )
        )
        if file is None:
            raise StorageFileNotFoundError("file not found")

        file.status = StoredFileStatus.QUARANTINED
        file.quarantine_reason = reason
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="file.quarantined",
            resource_type="stored_file",
            resource_id=str(file_id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"file_id": str(file_id), "reason": reason},
        )
        return file

    def list_files(
        self,
        principal: Principal,
        tenant_context: TenantContext,
    ) -> list[StoredFile]:
        authorize(principal, tenant_context, Capability.FILE_READ)
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )
        return list(
            self.session.scalars(
                select(StoredFile)
                .where(
                    StoredFile.tenant_id == tenant_context.tenant_id,
                    StoredFile.status == StoredFileStatus.ACTIVE,
                )
                .order_by(StoredFile.created_at.desc())
            ).all()
        )


def get_storage_service(
    session: Annotated[Session, Depends(get_db)],
    storage_provider: Annotated[StorageProvider, Depends(get_storage_provider)],
    encryption_service: Annotated[
        EnvelopeEncryptionService, Depends(get_envelope_encryption_service)
    ],
) -> StorageService:
    settings = get_settings()
    scanner = ProductionMalwareScanner(
        clamav_host=settings.clamav_host,
        clamav_port=settings.clamav_port,
    )
    return StorageService(
        session=session,
        storage_provider=storage_provider,
        encryption_service=encryption_service,
        malware_scanner=scanner,
        max_file_size_bytes=settings.max_file_size_bytes,
    )
