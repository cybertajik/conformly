import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response

from conformly.audit.models import AuditActorType, AuditEvent, AuditOutcome
from conformly.audit.query import (
    AuditExportTooLargeError,
    InvalidAuditCursorError,
    export_audit_events,
    search_audit_events,
)
from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError
from conformly.db.session import get_db

router = APIRouter(prefix="/v1/tenants/{tenant_id}/audit-events", tags=["audit"])


class AuditEventResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    actor_type: AuditActorType
    actor_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    occurred_at: datetime
    request_id: str
    outcome: AuditOutcome
    metadata: dict[str, Any]


class AuditSearchResponse(BaseModel):
    records: list[AuditEventResponse]
    next_cursor: str | None


def _response(event: AuditEvent) -> AuditEventResponse:
    if event.tenant_id is None:
        raise ValueError("tenant audit response cannot contain a system event")
    return AuditEventResponse(
        id=event.id,
        tenant_id=event.tenant_id,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        occurred_at=event.occurred_at,
        request_id=event.request_id,
        outcome=event.outcome,
        metadata=event.safe_metadata,
    )


@router.get("", response_model=AuditSearchResponse)
def read_audit_events(
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    action: Annotated[str | None, Query(max_length=120)] = None,
    outcome: AuditOutcome | None = None,
) -> AuditSearchResponse | Response:
    try:
        result = search_audit_events(
            database,
            principal,
            tenant_context,
            request_id=request.state.request_id,
            limit=limit,
            cursor=cursor,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            action_filter=action,
            outcome=outcome,
        )
    except AuthorizationDeniedError:
        return JSONResponse(status_code=403, content={"detail": "capability denied"})
    except InvalidAuditCursorError:
        return JSONResponse(status_code=400, content={"detail": "invalid audit cursor"})
    return AuditSearchResponse(
        records=[_response(event) for event in result.records],
        next_cursor=result.next_cursor,
    )


@router.get("/export")
def download_audit_events(
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
) -> Response:
    try:
        records = export_audit_events(
            database,
            principal,
            tenant_context,
            request_id=request.state.request_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        )
    except AuthorizationDeniedError:
        return JSONResponse(status_code=403, content={"detail": "capability denied"})
    except AuditExportTooLargeError:
        return JSONResponse(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            content={"detail": "audit export requires a narrower date range"},
        )
    content = "".join(
        json.dumps(_response(event).model_dump(mode="json"), separators=(",", ":")) + "\n"
        for event in records
    )
    return Response(
        content=content,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="conformly-audit.jsonl"'},
    )
