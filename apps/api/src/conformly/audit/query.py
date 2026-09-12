import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditEvent, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import AuthorizationDeniedError, Principal, TenantContext, authorize
from conformly.authz.roles import Capability

MAX_SEARCH_LIMIT = 100
MAX_EXPORT_RECORDS = 10_000


class InvalidAuditCursorError(ValueError):
    """Raised when an opaque audit cursor cannot be safely decoded."""


class AuditExportTooLargeError(RuntimeError):
    """Raised when a bounded synchronous export would be exceeded."""


@dataclass(frozen=True, slots=True)
class AuditSearchResult:
    records: list[AuditEvent]
    next_cursor: str | None


def _encode_cursor(event: AuditEvent) -> str:
    payload = json.dumps(
        {"occurred_at": event.occurred_at.isoformat(), "id": str(event.id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.b64decode(padded, altchars=b"-_", validate=True))
        return datetime.fromisoformat(value["occurred_at"]), UUID(value["id"])
    except (binascii.Error, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise InvalidAuditCursorError("invalid audit cursor") from error


def _authorized_query(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    capability: Capability,
    *,
    request_id: str,
    action: str,
) -> Select[tuple[AuditEvent]]:
    try:
        authorize(principal, tenant_context, capability)
    except AuthorizationDeniedError:
        record_audit_event(
            database,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action=action,
            resource_type="audit_event",
            resource_id=None,
            request_id=request_id,
            outcome=AuditOutcome.DENIED,
        )
        raise
    return select(AuditEvent).where(AuditEvent.tenant_id == tenant_context.tenant_id)


def search_audit_events(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    *,
    request_id: str,
    limit: int = 50,
    cursor: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    action_filter: str | None = None,
    outcome: AuditOutcome | None = None,
) -> AuditSearchResult:
    if not 1 <= limit <= MAX_SEARCH_LIMIT:
        raise ValueError("audit search limit is out of bounds")
    query = _authorized_query(
        database,
        principal,
        tenant_context,
        Capability.AUDIT_READ,
        request_id=request_id,
        action="audit.search",
    )
    if occurred_from is not None:
        query = query.where(AuditEvent.occurred_at >= occurred_from)
    if occurred_to is not None:
        query = query.where(AuditEvent.occurred_at < occurred_to)
    if action_filter is not None:
        query = query.where(AuditEvent.action == action_filter)
    if outcome is not None:
        query = query.where(AuditEvent.outcome == outcome)
    if cursor is not None:
        cursor_time, cursor_id = _decode_cursor(cursor)
        query = query.where(
            or_(
                AuditEvent.occurred_at < cursor_time,
                and_(AuditEvent.occurred_at == cursor_time, AuditEvent.id < cursor_id),
            )
        )
    records = list(
        database.scalars(
            query.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(limit + 1)
        )
    )
    has_next = len(records) > limit
    page = records[:limit]
    next_cursor = _encode_cursor(page[-1]) if has_next and page else None
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="audit.search",
        resource_type="audit_event",
        resource_id=None,
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"record_count": len(page)},
    )
    return AuditSearchResult(records=page, next_cursor=next_cursor)


def export_audit_events(
    database: Session,
    principal: Principal,
    tenant_context: TenantContext,
    *,
    request_id: str,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
) -> list[AuditEvent]:
    query = _authorized_query(
        database,
        principal,
        tenant_context,
        Capability.AUDIT_EXPORT,
        request_id=request_id,
        action="audit.export",
    )
    if occurred_from is not None:
        query = query.where(AuditEvent.occurred_at >= occurred_from)
    if occurred_to is not None:
        query = query.where(AuditEvent.occurred_at < occurred_to)
    records = list(
        database.scalars(
            query.order_by(AuditEvent.occurred_at, AuditEvent.id).limit(MAX_EXPORT_RECORDS + 1)
        )
    )
    if len(records) > MAX_EXPORT_RECORDS:
        record_audit_event(
            database,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="audit.export",
            resource_type="audit_event",
            resource_id=None,
            request_id=request_id,
            outcome=AuditOutcome.FAILURE,
            metadata={"reason": "limit_exceeded"},
        )
        raise AuditExportTooLargeError("audit export exceeds synchronous limit")
    record_audit_event(
        database,
        tenant_id=tenant_context.tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="audit.export",
        resource_type="audit_event",
        resource_id=None,
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"record_count": len(records)},
    )
    return records
