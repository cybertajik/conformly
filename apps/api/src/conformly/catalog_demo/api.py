"""FastAPI endpoints for the bounded synthetic staff catalog demo."""

import logging
import re
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.catalog_demo.auth import (
    WorkforceTokenVerifier,
    create_staff_session,
    extract_bearer_token,
    get_current_staff_actor,
    get_current_staff_session_data,
    get_workforce_verifier,
    revoke_staff_session,
)
from conformly.catalog_demo.db import AppAuditDeniedSink, AuditPersistenceError, get_catalog_db
from conformly.catalog_demo.projection import project_catalog_demo_graph
from conformly.catalog_demo.schemas import (
    CatalogDemoGraphResponse,
    CatalogDemoSessionResponse,
)
from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogNotFoundError,
    CatalogPermissionDeniedError,
)
from conformly.config import Settings, get_settings, validate_catalog_demo_settings
from conformly.db.session import get_db
from conformly.identity.models import User

logger = logging.getLogger(__name__)


def sanitize_request_id(req_id: str | None) -> str:
    """Validate and bound correlation request identifier."""
    if not req_id or not isinstance(req_id, str):
        return str(uuid4())
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", req_id.strip())[:64]
    return cleaned or str(uuid4())


def apply_preview_security_headers(res: Response) -> Response:
    """Enforce mandatory security headers across all preview responses."""
    res.headers["Cache-Control"] = "no-store"
    existing_vary = res.headers.get("Vary")
    if existing_vary:
        tokens = [v.strip() for v in existing_vary.split(",")]
        if "Authorization" not in tokens:
            res.headers["Vary"] = f"{existing_vary}, Authorization"
    else:
        res.headers["Vary"] = "Authorization"
    return res


_audit_session_factory: Callable[[], Session] | None = None
_audit_engine_cache: dict[str, sessionmaker[Session]] = {}


def set_audit_session_factory(factory: Callable[[], Session] | None) -> None:
    """Configure isolated audit session factory (useful for isolated in-memory test setups)."""
    global _audit_session_factory
    _audit_session_factory = factory


def get_audit_session() -> Session:
    """Yield a new session from the configured audit session factory."""
    if _audit_session_factory is not None:
        return _audit_session_factory()
    url = get_settings().database_url
    if url not in _audit_engine_cache:
        eng = create_engine(url, pool_pre_ping=True)
        _audit_engine_cache[url] = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    return _audit_engine_cache[url]()


def persist_preview_audit(
    actor_id: UUID | None,
    action: str,
    outcome: AuditOutcome,
    req_id: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Persist sanitized audit record via an isolated database session and transaction."""
    try:
        with get_audit_session() as audit_session:
            record_audit_event(
                audit_session,
                tenant_id=None,
                actor_type=AuditActorType.USER if actor_id else AuditActorType.SYSTEM,
                actor_id=actor_id,
                action=action,
                resource_type="catalog_demo",
                resource_id="catalog-demo-v1",
                request_id=req_id,
                outcome=outcome,
                metadata=metadata or {},
                occurred_at=datetime.now(UTC),
            )
            audit_session.commit()
    except Exception as exc:
        logger.error("Audit event persistence failed: %s", exc.__class__.__name__)
        raise AuditPersistenceError("Audit event persistence failed") from exc


class CatalogDemoRoute(APIRoute):
    """Prefix-scoped custom APIRoute guaranteeing fail-closed preview boundary and headers."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original_handler = super().get_route_handler()

        async def preview_boundary_handler(request: Request) -> Response:
            req_id = sanitize_request_id(request.headers.get("X-Request-ID"))
            try:
                res = await original_handler(request)
                return apply_preview_security_headers(res)
            except AuditPersistenceError:
                res = JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "detail": "Catalog service or audit infrastructure temporarily unavailable"
                    },
                )
                return apply_preview_security_headers(res)
            except HTTPException as http_exc:
                staff_user = getattr(request.state, "staff_user", None)
                actor_id = staff_user.id if staff_user else None

                if not getattr(request.state, "audit_recorded", False):
                    if http_exc.status_code == status.HTTP_401_UNAUTHORIZED:
                        reason = (
                            "missing_or_invalid_bearer"
                            if actor_id is None
                            else "session_invalid_or_expired"
                        )
                        action = "catalog.demo_access_denied"
                    elif http_exc.status_code == status.HTTP_403_FORBIDDEN:
                        reason = "insufficient_staff_permissions"
                        action = "catalog.demo_access_denied"
                    elif http_exc.status_code == status.HTTP_404_NOT_FOUND:
                        reason = "graph_unavailable"
                        action = "catalog.demo_preview"
                    else:
                        reason = "request_rejected"
                        action = "catalog.demo_error"

                    outcome = (
                        AuditOutcome.DENIED
                        if http_exc.status_code in (401, 403, 404)
                        else AuditOutcome.FAILURE
                    )
                    try:
                        persist_preview_audit(
                            actor_id=actor_id,
                            action=action,
                            outcome=outcome,
                            req_id=req_id,
                            metadata={"reason": reason},
                        )
                        request.state.audit_recorded = True
                    except AuditPersistenceError:
                        res = JSONResponse(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            content={
                                "detail": "Catalog service or audit infrastructure temporarily unavailable"
                            },
                        )
                        return apply_preview_security_headers(res)

                if http_exc.status_code == status.HTTP_401_UNAUTHORIZED:
                    safe_detail = "Invalid or revoked authentication credentials"
                elif http_exc.status_code == status.HTTP_403_FORBIDDEN:
                    safe_detail = "Insufficient staff permissions"
                elif http_exc.status_code == status.HTTP_404_NOT_FOUND:
                    safe_detail = "Catalog demo graph unavailable"
                elif http_exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
                    safe_detail = "Catalog service or audit infrastructure temporarily unavailable"
                else:
                    safe_detail = (
                        http_exc.detail
                        if isinstance(http_exc.detail, str)
                        else "Request could not be processed"
                    )

                res = JSONResponse(
                    status_code=http_exc.status_code,
                    content={"detail": safe_detail},
                )
                return apply_preview_security_headers(res)
            except RequestValidationError:
                res = JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": "Request validation failed"},
                )
                return apply_preview_security_headers(res)
            except Exception as unhandled_exc:
                logger.error(
                    "Unhandled exception in catalog demo route: %s",
                    unhandled_exc.__class__.__name__,
                )
                staff_user = getattr(request.state, "staff_user", None)
                actor_id = staff_user.id if staff_user else None
                try:
                    persist_preview_audit(
                        actor_id=actor_id,
                        action="catalog.demo_error",
                        outcome=AuditOutcome.FAILURE,
                        req_id=req_id,
                        metadata={"reason": "unhandled_internal_error"},
                    )
                except Exception:
                    pass
                res = JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "detail": "Catalog service or audit infrastructure temporarily unavailable"
                    },
                )
                return apply_preview_security_headers(res)

        return preview_boundary_handler


router = APIRouter(prefix="/v2/catalog-demo", tags=["catalog-demo"], route_class=CatalogDemoRoute)


@router.post(
    "/session",
    response_model=CatalogDemoSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bootstrap a revocable staff demo session using workforce OIDC/MFA credentials",
)
def create_session(
    request: Request,
    response: Response,
    token: Annotated[str, Depends(extract_bearer_token)],
    db: Annotated[Session, Depends(get_db)],
    verifier: Annotated[WorkforceTokenVerifier, Depends(get_workforce_verifier)],
) -> CatalogDemoSessionResponse:
    apply_preview_security_headers(response)
    req_id = sanitize_request_id(request.headers.get("X-Request-ID"))
    session_resp = create_staff_session(db, token, req_id, verifier, request=request)
    staff_user = getattr(request.state, "staff_user", None)
    actor_id = staff_user.id if staff_user else None
    persist_preview_audit(
        actor_id=actor_id,
        action="catalog.demo_session_created",
        outcome=AuditOutcome.SUCCESS,
        req_id=req_id,
    )
    request.state.audit_recorded = True
    return session_resp


@router.get(
    "/session",
    response_model=CatalogDemoSessionResponse,
    summary="Verify current staff demo session status",
)
def get_session(
    request: Request,
    response: Response,
    token: Annotated[str, Depends(extract_bearer_token)],
    db: Annotated[Session, Depends(get_db)],
    verifier: Annotated[WorkforceTokenVerifier, Depends(get_workforce_verifier)],
) -> CatalogDemoSessionResponse:
    apply_preview_security_headers(response)
    user, _auth_session, auth_dt, expires_at = get_current_staff_session_data(
        db, token, verifier, request=request
    )
    req_id = sanitize_request_id(request.headers.get("X-Request-ID"))
    persist_preview_audit(
        actor_id=user.id,
        action="catalog.demo_session_verified",
        outcome=AuditOutcome.SUCCESS,
        req_id=req_id,
    )
    request.state.audit_recorded = True
    return CatalogDemoSessionResponse(
        user_id=str(user.id),
        display_name=user.display_name or user.email,
        authenticated_at=auth_dt.isoformat(),
        expires_at=expires_at.isoformat(),
        capabilities=["DRAFT_READ"],
    )


@router.delete(
    "/session",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Revoke caller's own active staff demo session",
)
def delete_session(
    request: Request,
    response: Response,
    token: Annotated[str, Depends(extract_bearer_token)],
    db: Annotated[Session, Depends(get_db)],
    verifier: Annotated[WorkforceTokenVerifier, Depends(get_workforce_verifier)],
) -> Response:
    apply_preview_security_headers(response)
    req_id = sanitize_request_id(request.headers.get("X-Request-ID"))
    revoke_staff_session(db, token, req_id, verifier, request=request)
    staff_user = getattr(request.state, "staff_user", None)
    actor_id = staff_user.id if staff_user else None
    persist_preview_audit(
        actor_id=actor_id,
        action="catalog.demo_session_revoked",
        outcome=AuditOutcome.SUCCESS,
        req_id=req_id,
    )
    request.state.audit_recorded = True
    return apply_preview_security_headers(Response(status_code=status.HTTP_204_NO_CONTENT))


@router.get(
    "/catalog",
    response_model=CatalogDemoGraphResponse,
    summary="Retrieve read-only synthetic draft catalog graph",
)
def get_catalog_demo_graph(
    request: Request,
    response: Response,
    staff_info: Annotated[tuple[User, CatalogActorContext], Depends(get_current_staff_actor)],
    catalog_db: Annotated[Session, Depends(get_catalog_db)],
) -> CatalogDemoGraphResponse:
    apply_preview_security_headers(response)
    response.headers["X-Catalog-Synthetic"] = "true"
    response.headers["X-Catalog-Draft-Only"] = "true"

    user, actor_context = staff_info
    req_id = sanitize_request_id(request.headers.get("X-Request-ID"))

    audit_sink = AppAuditDeniedSink(session_factory=get_audit_session)

    try:
        graph = project_catalog_demo_graph(catalog_db, actor_context, denied_audit_sink=audit_sink)

        # Durable success audit via isolated database session
        persist_preview_audit(
            actor_id=user.id,
            action="catalog.demo_preview",
            outcome=AuditOutcome.SUCCESS,
            req_id=req_id,
            metadata={"status": "Draft"},
        )
        request.state.audit_recorded = True

        return graph

    except CatalogPermissionDeniedError as exc:
        persist_preview_audit(
            actor_id=user.id,
            action="catalog.demo_preview",
            outcome=AuditOutcome.DENIED,
            req_id=req_id,
            metadata={"reason": "permission_denied"},
        )
        request.state.audit_recorded = True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient staff permissions",
        ) from exc

    except CatalogNotFoundError as exc:
        persist_preview_audit(
            actor_id=user.id,
            action="catalog.demo_preview",
            outcome=AuditOutcome.DENIED,
            req_id=req_id,
            metadata={"reason": "graph_unavailable"},
        )
        request.state.audit_recorded = True
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Catalog demo graph unavailable",
        ) from exc


def register_catalog_demo_routes(app: FastAPI, settings: Settings | None = None) -> None:
    """Register catalog demo router only when feature flag is active in non-prod environments."""
    effective_settings = settings or get_settings()
    if effective_settings.enable_catalog_demo and effective_settings.environment in (
        "local",
        "development",
        "test",
    ):
        validate_catalog_demo_settings(effective_settings)
        url = effective_settings.database_url
        if url not in _audit_engine_cache:
            eng = create_engine(url, pool_pre_ping=True)
            _audit_engine_cache[url] = sessionmaker(
                bind=eng, autoflush=False, expire_on_commit=False
            )
        for route in app.routes:
            if getattr(route, "path", "").startswith("/v2/catalog-demo"):
                return
        app.include_router(router)
        logger.info(
            "Mounted /v2/catalog-demo router (environment: %s)", effective_settings.environment
        )
    else:
        logger.info(
            "Catalog demo routes disabled (enable_catalog_demo=%s, env=%s)",
            effective_settings.enable_catalog_demo,
            effective_settings.environment,
        )
