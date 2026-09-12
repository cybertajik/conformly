from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm.exc import StaleDataError

from conformly.api.audit import router as audit_router
from conformly.api.auth import router as auth_router
from conformly.api.compliance import compliance_router
from conformly.api.files import router as files_router
from conformly.api.frameworks import (
    canonical_router as frameworks_canonical_router,
)
from conformly.api.frameworks import (
    tenant_custom_controls_router as frameworks_custom_controls_router,
)
from conformly.api.frameworks import (
    tenant_mappings_router as frameworks_mappings_router,
)
from conformly.api.frameworks import (
    tenant_router as frameworks_tenant_router,
)
from conformly.api.health import router as health_router
from conformly.api.invitations import router as invitations_router
from conformly.api.lifecycle import lifecycle_router
from conformly.api.me import router as me_router
from conformly.api.preaudit import preaudit_router
from conformly.api.profiles import (
    public_profiles_router,
    tenant_profiles_router,
)
from conformly.api.tenants import router as tenants_router
from conformly.api.whistleblower import (
    public_whistleblower_router,
    whistleblower_router,
)
from conformly.compliance.service import InvalidStateTransitionError, InvalidTenantReferenceError
from conformly.config import get_settings
from conformly.logging import configure_logging
from conformly.storage.upload_limit import UploadLimitMiddleware

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("service_startup", service="conformly-api", environment=settings.environment)
    yield
    logger.info("service_shutdown", service="conformly-api")


app = FastAPI(
    title="Conformly API",
    version="0.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)
app.add_middleware(UploadLimitMiddleware, max_body_bytes=settings.max_file_size_bytes + 1024 * 1024)


@app.exception_handler(StaleDataError)
async def stale_update(request: Request, exc: StaleDataError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "Entity changed; reload and retry"})


@app.exception_handler(InvalidTenantReferenceError)
async def invalid_reference(request: Request, exc: InvalidTenantReferenceError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(InvalidStateTransitionError)
async def invalid_transition(request: Request, exc: InvalidStateTransitionError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Correlation-ID"],
    expose_headers=["X-Request-ID", "X-Correlation-ID"],
)
app.include_router(health_router)
app.include_router(audit_router)
app.include_router(auth_router)
app.include_router(compliance_router)
app.include_router(files_router)
app.include_router(frameworks_canonical_router)
app.include_router(frameworks_tenant_router)
app.include_router(frameworks_custom_controls_router)
app.include_router(frameworks_mappings_router)
app.include_router(invitations_router)
app.include_router(me_router)
app.include_router(preaudit_router)
app.include_router(public_whistleblower_router)
app.include_router(whistleblower_router)
app.include_router(public_profiles_router)
app.include_router(tenant_profiles_router)
app.include_router(tenants_router)
app.include_router(lifecycle_router)


@app.middleware("http")
async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Enforce production security headers on all API responses."""

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
        "magnetometer=(), microphone=(), payment=(), usb=()"
    )
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
    if settings.environment != "development":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Attach a validated correlation identifier to every request and response."""

    correlation_id = (
        request.headers.get("X-Correlation-ID")
        or request.headers.get("X-Request-ID")
        or str(uuid4())
    )
    request.state.request_id = correlation_id
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=correlation_id,
        correlation_id=correlation_id,
    )
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = correlation_id
        response.headers["X-Correlation-ID"] = correlation_id
        logger.info("request_completed", method=request.method, path=request.url.path)
        return response
    finally:
        structlog.contextvars.clear_contextvars()
