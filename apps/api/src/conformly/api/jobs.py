from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.roles import Role
from conformly.db.session import get_db
from conformly.notifications.models import OutboxState
from conformly.notifications.service import (
    OutboxMessageNotFoundError,
    get_failed_jobs_summary,
    get_outbox_message,
    list_outbox_messages,
    retry_outbox_message,
)

jobs_router = APIRouter(prefix="/v1/tenants/{tenant_id}/jobs", tags=["Background Jobs & Outbox"])

PRIVILEGED_JOB_ROLES = frozenset({Role.OWNER, Role.ADMINISTRATOR, Role.COMPLIANCE_MANAGER})


class FailedJobItem(BaseModel):
    id: UUID
    kind: str
    attempts: int
    error_code: str | None = None
    created_at: str
    updated_at: str


class FailedJobsResponse(BaseModel):
    tenant_id: UUID
    total_pending: int
    total_processing: int
    total_delivered: int
    total_failed: int
    recent_failures: list[FailedJobItem]


class OutboxMessageResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    kind: str
    idempotency_key: str
    state: str
    attempts: int
    available_at: datetime
    delivered_at: datetime | None = None
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


def _check_jobs_access(tenant: CurrentTenant) -> None:
    if tenant.role not in PRIVILEGED_JOB_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: background jobs visibility requires Owner, Administrator, or Compliance Manager",
        )


@jobs_router.get("/failed", response_model=FailedJobsResponse)
def get_failed_jobs(
    tenant_id: UUID,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> Any:
    """Retrieve failed background job summary and recent failure records for the tenant."""
    _check_jobs_access(tenant)
    summary = get_failed_jobs_summary(database, tenant.tenant_id)
    return summary


@jobs_router.get("/outbox", response_model=list[OutboxMessageResponse])
def get_outbox_messages(
    tenant_id: UUID,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
    state: OutboxState | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """List tenant notification outbox messages with optional state filtering."""
    _check_jobs_access(tenant)
    messages = list_outbox_messages(
        database,
        tenant.tenant_id,
        state=state,
        limit=limit,
        offset=offset,
    )
    return [
        OutboxMessageResponse(
            id=m.id,
            tenant_id=m.tenant_id,
            kind=m.kind,
            idempotency_key=m.idempotency_key,
            state=str(m.state),
            attempts=m.attempts,
            available_at=m.available_at,
            delivered_at=m.delivered_at,
            error_code=m.error_code,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in messages
    ]


@jobs_router.get("/outbox/{message_id}", response_model=OutboxMessageResponse)
def get_single_outbox_message(
    tenant_id: UUID,
    message_id: UUID,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> Any:
    """Retrieve details for a specific tenant outbox message."""
    _check_jobs_access(tenant)
    message = get_outbox_message(database, tenant.tenant_id, message_id)
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Outbox message {message_id} not found",
        )
    return OutboxMessageResponse(
        id=message.id,
        tenant_id=message.tenant_id,
        kind=message.kind,
        idempotency_key=message.idempotency_key,
        state=str(message.state),
        attempts=message.attempts,
        available_at=message.available_at,
        delivered_at=message.delivered_at,
        error_code=message.error_code,
        created_at=message.created_at,
        updated_at=message.updated_at,
    )


@jobs_router.post("/outbox/{message_id}/retry", response_model=OutboxMessageResponse)
def retry_failed_outbox_message(
    tenant_id: UUID,
    message_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> Any:
    """Reset a failed or stalled outbox notification message to PENDING for immediate retry."""
    _check_jobs_access(tenant)
    try:
        updated = retry_outbox_message(
            database,
            tenant.tenant_id,
            message_id,
            actor_id=principal.user_id,
        )
        database.commit()
    except OutboxMessageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return OutboxMessageResponse(
        id=updated.id,
        tenant_id=updated.tenant_id,
        kind=updated.kind,
        idempotency_key=updated.idempotency_key,
        state=str(updated.state),
        attempts=updated.attempts,
        available_at=updated.available_at,
        delivered_at=updated.delivered_at,
        error_code=updated.error_code,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )
