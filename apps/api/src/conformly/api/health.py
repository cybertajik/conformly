from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from conformly.db.session import get_db
from conformly.storage.providers import StorageProvider, get_storage_provider

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["conformly-api"]


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: Literal["conformly-api"]
    database: Literal["connected", "unhealthy"]
    storage: Literal["connected", "unhealthy"]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return liveness without exposing configuration or dependency details."""

    return HealthResponse(status="ok", service="conformly-api")


@router.get("/health/live", response_model=HealthResponse)
def health_live() -> HealthResponse:
    """Kubernetes / orchestration lightweight liveness probe."""

    return HealthResponse(status="ok", service="conformly-api")


@router.get("/health/ready", response_model=ReadinessResponse)
def health_ready(
    session: Annotated[Session, Depends(get_db)],
    storage_provider: Annotated[StorageProvider, Depends(get_storage_provider)],
) -> ReadinessResponse:
    """Readiness probe checking database connectivity and storage readiness.

    Does not leak connection details or internal error messages.
    """

    db_ok = False

    storage_ok = False

    try:
        session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    try:
        if storage_provider is not None:
            storage_ok = True
    except Exception:
        storage_ok = False

    if not db_ok or not storage_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "degraded",
                "service": "conformly-api",
                "database": "connected" if db_ok else "unhealthy",
                "storage": "connected" if storage_ok else "unhealthy",
            },
        )

    return ReadinessResponse(
        status="ok",
        service="conformly-api",
        database="connected",
        storage="connected",
    )
