"""Dedicated serialized catalog audit journal, event intents, and mutation receipts."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from conformly.catalog_v2.actor import (
    CatalogConflictError,
)
from conformly.catalog_v2.digest import (
    compute_content_digest,
    format_canonical_datetime,
)
from conformly.catalog_v2.models import (
    CatalogAuditEvent,
    CatalogAuditHead,
    CatalogEventIntent,
    CatalogMutationReceipt,
)

logger = logging.getLogger(__name__)

CHAIN_KEY_DRAFT_V1 = "draft-catalog-v1"
ZERO_HEAD_HASH = b"\x00" * 32


class DeniedAuditSink(Protocol):
    """Protocol for safely recording authorization or permission denials."""

    def record_denial(
        self,
        actor_id: UUID,
        operation: str,
        reason_code: str,
        request_key: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> None: ...


class LoggingDeniedAuditSink:
    """Default non-failing sink that records sanitized denial events via structured logging."""

    def __init__(self) -> None:
        self.recorded_denials: list[dict[str, Any]] = []

    def record_denial(
        self,
        actor_id: UUID,
        operation: str,
        reason_code: str,
        request_key: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> None:
        record = {
            "actor_id": str(actor_id),
            "operation": operation,
            "reason_code": reason_code,
            "request_key": request_key,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
        }
        self.recorded_denials.append(record)
        logger.warning("Catalog access denied: %s", record)


class DatabaseCommittedDeniedAuditSink:
    """Separately committed audit sink that persists sanitized denial events to the database."""

    def __init__(self, session_factory_or_bind: Any, chain_key: str = CHAIN_KEY_DRAFT_V1) -> None:
        self._target = session_factory_or_bind
        self.chain_key = chain_key

    def _create_session(self) -> Session:
        if callable(self._target):
            sess = self._target()
            if isinstance(sess, Session):
                return sess
        return Session(bind=self._target)

    def record_denial(
        self,
        actor_id: UUID,
        operation: str,
        reason_code: str,
        request_key: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> None:
        sanitized_resource_type = resource_type or "catalog"
        sanitized_metadata = {
            "reason_code": reason_code,
        }
        with self._create_session() as audit_session:
            try:
                dialect = audit_session.bind.dialect.name if audit_session.bind else ""
                db_time: datetime
                if dialect == "sqlite":
                    raw = audit_session.execute(
                        text("SELECT strftime('%Y-%m-%d %H:%M:%f', 'now')")
                    ).scalar()
                    if isinstance(raw, str):
                        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                        db_time = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
                    elif isinstance(raw, datetime):
                        db_time = raw if raw.tzinfo else raw.replace(tzinfo=UTC)
                    else:
                        db_time = datetime.now(UTC)
                else:
                    val = audit_session.execute(text("SELECT clock_timestamp()")).scalar()
                    if isinstance(val, datetime):
                        db_time = val if val.tzinfo else val.replace(tzinfo=UTC)
                    else:
                        db_time = datetime.now(UTC)

                append_catalog_audit_event(
                    session=audit_session,
                    actor_id=actor_id,
                    action=operation,
                    resource_type=sanitized_resource_type,
                    resource_id=resource_id,
                    request_key=request_key,
                    outcome="Denied",
                    metadata=sanitized_metadata,
                    db_time=db_time,
                    chain_key=self.chain_key,
                )
                audit_session.commit()
            except Exception:
                audit_session.rollback()
                raise


CatalogDeniedAuditSink = DatabaseCommittedDeniedAuditSink


def lock_or_init_audit_head(
    session: Session, chain_key: str = CHAIN_KEY_DRAFT_V1, db_time: datetime | None = None
) -> CatalogAuditHead:
    """Lock the audit head FOR UPDATE, initializing the chain if empty."""
    if db_time is None:
        db_time = datetime.now(UTC)
    elif db_time.tzinfo is None:
        db_time = db_time.replace(tzinfo=UTC)

    stmt = select(CatalogAuditHead).where(CatalogAuditHead.chain_key == chain_key).with_for_update()
    head = session.execute(stmt).scalar_one_or_none()

    if head is None:
        head = CatalogAuditHead(
            chain_key=chain_key,
            current_sequence=0,
            head_hash=ZERO_HEAD_HASH,
            updated_at=db_time,
        )
        session.add(head)
        session.flush()

    return head


def append_catalog_audit_event(
    session: Session,
    actor_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID | None,
    request_key: str,
    outcome: str,
    metadata: dict[str, Any],
    db_time: datetime,
    chain_key: str = CHAIN_KEY_DRAFT_V1,
) -> CatalogAuditEvent:
    """Append an event to the serialized catalog audit journal."""
    if db_time.tzinfo is None:
        db_time = db_time.replace(tzinfo=UTC)

    head = lock_or_init_audit_head(session, chain_key=chain_key, db_time=db_time)

    next_sequence = head.current_sequence + 1
    previous_hash = head.head_hash

    payload = {
        "action": action,
        "actor_id": actor_id,
        "chain_key": chain_key,
        "metadata": metadata,
        "occurred_at": format_canonical_datetime(db_time),
        "outcome": outcome,
        "previous_hash": previous_hash.hex(),
        "request_key": request_key,
        "resource_id": resource_id,
        "resource_type": resource_type,
        "sequence": next_sequence,
    }
    event_hash = compute_content_digest(payload)

    head.current_sequence = next_sequence
    head.head_hash = event_hash
    head.updated_at = db_time

    event = CatalogAuditEvent(
        chain_key=chain_key,
        sequence=next_sequence,
        previous_hash=previous_hash,
        event_hash=event_hash,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_key=request_key,
        outcome=outcome,
        occurred_at=db_time,
        metadata_json=metadata,
    )
    session.add(event)
    session.flush()
    return event


def record_catalog_event_intent(
    session: Session,
    request_key: str,
    event_kind: str,
    aggregate_id: UUID,
    aggregate_type: str,
    revision: int,
    content_digest: bytes,
    db_time: datetime,
) -> CatalogEventIntent:
    """Record an immutable internal catalog event intent."""
    if db_time.tzinfo is None:
        db_time = db_time.replace(tzinfo=UTC)

    intent = CatalogEventIntent(
        request_key=request_key,
        event_kind=event_kind,
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        revision=revision,
        content_digest=content_digest,
        created_at=db_time,
    )
    session.add(intent)
    session.flush()
    return intent


def check_or_record_mutation_receipt(
    session: Session,
    actor_id: UUID,
    operation: str,
    request_key: str,
    request_data: Any,
    result_provider: Callable[[], tuple[UUID, str, int, bytes]],
    db_time: datetime,
) -> tuple[bool, CatalogMutationReceipt]:
    """Check for existing mutation receipt or record a new receipt.

    Returns (is_retry, receipt).
    Raises CatalogConflictError if request_key is reused with different request data.
    """
    if db_time.tzinfo is None:
        db_time = db_time.replace(tzinfo=UTC)

    request_fingerprint = compute_content_digest(request_data)

    stmt = (
        select(CatalogMutationReceipt)
        .where(
            CatalogMutationReceipt.actor_id == actor_id,
            CatalogMutationReceipt.operation == operation,
            CatalogMutationReceipt.request_key == request_key,
        )
        .with_for_update()
    )
    existing = session.execute(stmt).scalar_one_or_none()

    if existing is not None:
        if existing.request_fingerprint != request_fingerprint:
            raise CatalogConflictError(
                f"Request key '{request_key}' reused with conflicting request parameters"
            )
        return (True, existing)

    result_id, result_type, result_revision, result_digest = result_provider()

    receipt = CatalogMutationReceipt(
        actor_id=actor_id,
        operation=operation,
        request_key=request_key,
        request_fingerprint=request_fingerprint,
        result_id=result_id,
        result_type=result_type,
        result_revision=result_revision,
        result_digest=result_digest,
        created_at=db_time,
    )
    session.add(receipt)
    session.flush()
    return (False, receipt)
