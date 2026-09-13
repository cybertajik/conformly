import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.types import EncryptionContext
from conformly.notifications.models import NotificationOutbox, OutboxState


class OutboxMessageNotFoundError(LookupError):
    """Raised when an outbox message is not found within the tenant scope."""


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


def list_outbox_messages(
    session: Session,
    tenant_id: UUID,
    *,
    state: OutboxState | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[NotificationOutbox]:
    """Retrieve tenant outbox messages with optional state filtering and pagination."""
    from sqlalchemy import select

    stmt = (
        select(NotificationOutbox)
        .where(NotificationOutbox.tenant_id == tenant_id)
        .order_by(NotificationOutbox.created_at.desc())
        .limit(min(limit, 100))
        .offset(offset)
    )
    if state is not None:
        stmt = stmt.where(NotificationOutbox.state == state)
    return list(session.scalars(stmt))


def get_outbox_message(
    session: Session,
    tenant_id: UUID,
    message_id: UUID,
) -> NotificationOutbox | None:
    """Retrieve a single tenant-scoped outbox message."""
    from sqlalchemy import select

    return session.scalar(
        select(NotificationOutbox).where(
            NotificationOutbox.tenant_id == tenant_id,
            NotificationOutbox.id == message_id,
        )
    )


def retry_outbox_message(
    session: Session,
    tenant_id: UUID,
    message_id: UUID,
    *,
    actor_id: UUID | None = None,
) -> NotificationOutbox:
    """Reset a failed or stalled outbox notification message to PENDING for immediate retry."""
    from conformly.audit.models import AuditActorType, AuditOutcome
    from conformly.audit.service import record_audit_event
    from conformly.notifications.models import OutboxState

    message = get_outbox_message(session, tenant_id, message_id)
    if message is None:
        raise OutboxMessageNotFoundError(f"Outbox message {message_id} not found in tenant")

    previous_state = str(message.state)
    message.state = OutboxState.PENDING
    message.attempts = 0
    message.error_code = None
    message.available_at = datetime.now(UTC)
    session.flush()

    record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER if actor_id else AuditActorType.SYSTEM,
        actor_id=actor_id,
        action="notification.retry",
        resource_type="notification_outbox",
        resource_id=str(message.id),
        request_id=f"retry:{message.id}:{int(datetime.now(UTC).timestamp())}",
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "previous_status": previous_state,
            "status": str(message.state),
            "attempt": message.attempts,
        },
    )
    return message


def get_failed_jobs_summary(
    session: Session,
    tenant_id: UUID,
) -> dict[str, Any]:
    """Calculate summary statistics for tenant background outbox messages including failure counts."""
    from sqlalchemy import func, select

    from conformly.notifications.models import OutboxState

    state_rows = session.execute(
        select(NotificationOutbox.state, func.count(NotificationOutbox.id))
        .where(NotificationOutbox.tenant_id == tenant_id)
        .group_by(NotificationOutbox.state)
    ).all()
    counts: dict[OutboxState, int] = {row[0]: int(row[1]) for row in state_rows}

    failed_messages = session.scalars(
        select(NotificationOutbox)
        .where(
            NotificationOutbox.tenant_id == tenant_id,
            NotificationOutbox.state == OutboxState.FAILED,
        )
        .order_by(NotificationOutbox.updated_at.desc())
        .limit(10)
    ).all()

    recent_failures = [
        {
            "id": str(m.id),
            "kind": m.kind,
            "attempts": m.attempts,
            "error_code": m.error_code,
            "created_at": m.created_at.isoformat(),
            "updated_at": m.updated_at.isoformat(),
        }
        for m in failed_messages
    ]

    return {
        "tenant_id": str(tenant_id),
        "total_pending": counts.get(OutboxState.PENDING, 0),
        "total_processing": counts.get(OutboxState.PROCESSING, 0),
        "total_delivered": counts.get(OutboxState.DELIVERED, 0),
        "total_failed": counts.get(OutboxState.FAILED, 0),
        "recent_failures": recent_failures,
    }
