import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.types import EncryptionContext
from conformly.integrations.models import (
    CredentialStatus,
    InboundEventStatus,
    InboundWebhookEvent,
    IntegrationCredential,
    WebhookSubscription,
)


class WebhookVerificationError(Exception):
    """Base exception for inbound webhook verification failures."""


class WebhookReplayError(WebhookVerificationError):
    """Raised when an inbound webhook timestamp falls outside the tolerance window."""


class WebhookSignatureError(WebhookVerificationError):
    """Raised when an inbound webhook signature fails cryptographic verification."""


class WebhookIdempotencyConflictError(WebhookVerificationError):
    """Raised when an event with the same idempotency key is already processing."""


@dataclass(frozen=True, slots=True)
class IssuedCredentialResult:
    credential: IntegrationCredential
    client_secret: str
    signing_secret: str


def _hash_client_secret(secret: str, salt: str) -> str:
    """Hash client secret using PBKDF2-HMAC-SHA256 with 100,000 rounds."""
    derived = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"pbkdf2:sha256:100000${salt}${derived.hex()}"


def _verify_client_secret(secret: str, stored_hash: str) -> bool:
    try:
        parts = stored_hash.split("$")
        if len(parts) != 3:
            return False
        salt = parts[1]
        expected_hex = parts[2]
        derived = hashlib.pbkdf2_hmac(
            "sha256", secret.encode("utf-8"), salt.encode("utf-8"), 100_000
        )
        return hmac.compare_digest(derived.hex(), expected_hex)
    except Exception:
        return False


def create_integration_credential(
    session: Session,
    codec: EncryptedFieldCodec,
    *,
    tenant_id: UUID,
    name: str,
    scopes: list[str],
    valid_until: datetime | None = None,
    actor_id: UUID | None = None,
) -> IssuedCredentialResult:
    """Issue a new tenant-scoped integration credential with unique key_id, secret, and signing secret."""
    credential_id = uuid4()
    key_id = f"cf_live_{secrets.token_hex(16)}"
    raw_secret = f"cfs_{secrets.token_urlsafe(32)}"
    salt = secrets.token_hex(16)
    secret_hash = _hash_client_secret(raw_secret, salt)
    signing_secret = secrets.token_hex(32)

    enc_context = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="integration_credential",
        resource_id=str(credential_id),
        field_name="signing_secret",
    )
    encrypted_signing_secret = codec.encrypt_text(signing_secret, enc_context)

    credential = IntegrationCredential(
        id=credential_id,
        tenant_id=tenant_id,
        name=name,
        key_id=key_id,
        secret_hash=secret_hash,
        encrypted_signing_secret=encrypted_signing_secret,
        scopes=scopes,
        status=CredentialStatus.ACTIVE,
        valid_until=valid_until,
        created_by_user_id=actor_id,
    )
    session.add(credential)
    session.flush()

    record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER if actor_id else AuditActorType.SYSTEM,
        actor_id=actor_id,
        action="credential.create",
        resource_type="integration_credential",
        resource_id=str(credential_id),
        request_id=f"cred-create:{credential_id}",
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "title": name,
            "status": str(CredentialStatus.ACTIVE),
        },
    )

    return IssuedCredentialResult(
        credential=credential,
        client_secret=raw_secret,
        signing_secret=signing_secret,
    )


def authenticate_integration_credential(
    session: Session,
    *,
    key_id: str,
    client_secret: str,
) -> IntegrationCredential | None:
    """Authenticate integration credential via key_id and client_secret."""
    stmt = select(IntegrationCredential).where(
        IntegrationCredential.key_id == key_id,
        IntegrationCredential.status == CredentialStatus.ACTIVE,
    )
    cred = session.scalar(stmt)
    if cred is None:
        return None

    if cred.valid_until is not None and cred.valid_until < datetime.now(UTC):
        return None

    if not _verify_client_secret(client_secret, cred.secret_hash):
        return None

    return cred


def get_credential_signing_secret(
    codec: EncryptedFieldCodec,
    credential: IntegrationCredential,
) -> str:
    """Decrypt the application-layer envelope-encrypted signing secret."""
    enc_context = EncryptionContext(
        tenant_id=credential.tenant_id,
        resource_type="integration_credential",
        resource_id=str(credential.id),
        field_name="signing_secret",
    )
    return codec.decrypt_text(credential.encrypted_signing_secret, enc_context)


def revoke_integration_credential(
    session: Session,
    *,
    tenant_id: UUID,
    credential_id: UUID,
    actor_id: UUID | None = None,
) -> IntegrationCredential:
    """Revoke an active integration credential."""
    stmt = select(IntegrationCredential).where(
        IntegrationCredential.id == credential_id,
        IntegrationCredential.tenant_id == tenant_id,
    )
    cred = session.scalar(stmt)
    if cred is None:
        raise ValueError(f"Integration credential {credential_id} not found")

    cred.status = CredentialStatus.REVOKED
    cred.revoked_at = datetime.now(UTC)
    session.flush()

    record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER if actor_id else AuditActorType.SYSTEM,
        actor_id=actor_id,
        action="credential.revoke",
        resource_type="integration_credential",
        resource_id=str(credential_id),
        request_id=f"cred-revoke:{credential_id}",
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "status": str(CredentialStatus.REVOKED),
        },
    )
    return cred


def list_integration_credentials(
    session: Session,
    tenant_id: UUID,
) -> list[IntegrationCredential]:
    """List all integration credentials for a tenant."""
    stmt = (
        select(IntegrationCredential)
        .where(IntegrationCredential.tenant_id == tenant_id)
        .order_by(IntegrationCredential.created_at.desc())
    )
    return list(session.scalars(stmt).all())


def compute_webhook_signature(
    raw_body: bytes,
    timestamp: int | str,
    signing_secret: str,
) -> str:
    """Compute HMAC-SHA256 signature over timestamp and raw payload bytes."""
    payload_to_sign = f"{timestamp}.".encode() + raw_body
    return hmac.new(signing_secret.encode("utf-8"), payload_to_sign, hashlib.sha256).hexdigest()


def verify_webhook_signature(
    raw_body: bytes,
    signature_header: str,
    timestamp_header: str | int,
    signing_secret: str,
    *,
    tolerance_seconds: int = 300,
    current_timestamp: int | None = None,
) -> None:
    """Verify HMAC-SHA256 webhook signature and replay timestamp window."""
    try:
        req_time = int(timestamp_header)
    except (ValueError, TypeError) as exc:
        raise WebhookReplayError("Invalid timestamp header") from exc

    now = current_timestamp if current_timestamp is not None else int(time.time())
    if abs(now - req_time) > tolerance_seconds:
        raise WebhookReplayError(
            f"Webhook timestamp {req_time} outside tolerance window (current: {now}, tolerance: {tolerance_seconds}s)"
        )

    expected_sig = compute_webhook_signature(raw_body, req_time, signing_secret)

    # Allow formats: raw hex or "v1=<hex>" or "sha256=<hex>"
    candidate_sig = signature_header.strip()
    if candidate_sig.startswith("v1="):
        candidate_sig = candidate_sig[3:]
    elif candidate_sig.startswith("sha256="):
        candidate_sig = candidate_sig[7:]

    if not hmac.compare_digest(candidate_sig.lower(), expected_sig.lower()):
        raise WebhookSignatureError("Webhook signature verification failed")


def check_and_record_inbound_idempotency(
    session: Session,
    *,
    tenant_id: UUID,
    idempotency_key: str,
    event_topic: str,
    raw_body: bytes,
    credential_id: UUID | None = None,
) -> tuple[InboundWebhookEvent, bool]:
    """Check idempotency record.

    Returns (event, is_new).
    If is_new is False and status is PROCESSED, the caller can return cached response.
    If is_new is False and status is PROCESSING, raises WebhookIdempotencyConflictError.
    """
    payload_sha256 = hashlib.sha256(raw_body).hexdigest()

    stmt = select(InboundWebhookEvent).where(
        InboundWebhookEvent.tenant_id == tenant_id,
        InboundWebhookEvent.idempotency_key == idempotency_key,
    )
    existing = session.scalar(stmt)
    if existing is not None:
        if existing.status == InboundEventStatus.PROCESSING:
            raise WebhookIdempotencyConflictError(
                f"Webhook event with idempotency key '{idempotency_key}' is currently processing"
            )
        return existing, False

    event = InboundWebhookEvent(
        id=uuid4(),
        tenant_id=tenant_id,
        credential_id=credential_id,
        idempotency_key=idempotency_key,
        event_topic=event_topic,
        payload_sha256=payload_sha256,
        status=InboundEventStatus.PROCESSING,
    )
    session.add(event)
    session.flush()
    return event, True


def finalize_inbound_idempotency(
    session: Session,
    event: InboundWebhookEvent,
    *,
    status_code: int = 200,
    response_payload: dict[str, Any] | None = None,
    status: InboundEventStatus = InboundEventStatus.PROCESSED,
) -> InboundWebhookEvent:
    """Finalize processed inbound webhook event with response details."""
    event.status = status
    event.response_status_code = status_code
    event.response_payload = response_payload
    session.flush()
    return event


def create_webhook_subscription(
    session: Session,
    codec: EncryptedFieldCodec,
    *,
    tenant_id: UUID,
    target_url: str,
    description: str,
    topics: list[str],
    actor_id: UUID | None = None,
) -> tuple[WebhookSubscription, str]:
    """Create an outbound webhook subscription and return (subscription, plaintext_signing_secret)."""
    sub_id = uuid4()
    signing_secret = secrets.token_hex(32)

    enc_context = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="webhook_subscription",
        resource_id=str(sub_id),
        field_name="signing_secret",
    )
    encrypted_secret = codec.encrypt_text(signing_secret, enc_context)

    subscription = WebhookSubscription(
        id=sub_id,
        tenant_id=tenant_id,
        target_url=target_url,
        description=description,
        topics=topics,
        encrypted_secret=encrypted_secret,
        is_active=True,
        created_by_user_id=actor_id,
    )
    session.add(subscription)
    session.flush()

    record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER if actor_id else AuditActorType.SYSTEM,
        actor_id=actor_id,
        action="webhook.subscribe",
        resource_type="webhook_subscription",
        resource_id=str(sub_id),
        request_id=f"webhook-sub:{sub_id}",
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "subscription_id": str(sub_id),
            "title": description,
            "status": "active",
        },
    )
    return subscription, signing_secret


def list_webhook_subscriptions(
    session: Session,
    tenant_id: UUID,
) -> list[WebhookSubscription]:
    """List all outbound webhook subscriptions for a tenant."""
    stmt = (
        select(WebhookSubscription)
        .where(WebhookSubscription.tenant_id == tenant_id)
        .order_by(WebhookSubscription.created_at.desc())
    )
    return list(session.scalars(stmt).all())
