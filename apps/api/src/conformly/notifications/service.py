import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.types import EncryptionContext
from conformly.notifications.models import NotificationOutbox


def enqueue_encrypted_notification(
    session: Session,
    codec: EncryptedFieldCodec,
    *,
    message_id: UUID,
    tenant_id: UUID,
    kind: str,
    idempotency_key: str,
    payload: dict[str, str],
    available_at: datetime | None = None,
) -> NotificationOutbox:
    context = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="notification_outbox",
        resource_id=str(message_id),
        field_name="payload",
    )
    encrypted_payload = codec.encrypt_text(
        json.dumps(payload, separators=(",", ":"), sort_keys=True), context
    )
    message = NotificationOutbox(
        id=message_id,
        tenant_id=tenant_id,
        kind=kind,
        encrypted_payload=encrypted_payload,
        idempotency_key=idempotency_key,
        available_at=available_at or datetime.now(UTC),
    )
    session.add(message)
    return message


def decrypt_notification_payload(
    codec: EncryptedFieldCodec, message: NotificationOutbox
) -> dict[str, str]:
    context = EncryptionContext(
        tenant_id=message.tenant_id,
        resource_type="notification_outbox",
        resource_id=str(message.id),
        field_name="payload",
    )
    decoded = json.loads(codec.decrypt_text(message.encrypted_payload, context))
    if not isinstance(decoded, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in decoded.items()
    ):
        raise ValueError("notification payload has an invalid shape")
    return decoded
