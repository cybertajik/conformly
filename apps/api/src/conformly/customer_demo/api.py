"""FastAPI router and route registration for WP-09 Customer Onboarding Demo."""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.config import Settings, get_settings
from conformly.customer_demo.policy import (
    CustomerDemoAdmissionError,
    CustomerDemoDisabledError,
    verify_customer_demo_admission,
    verify_feature_enabled,
)
from conformly.customer_demo.schemas import (
    AdoptionResponse,
    AnswersResponse,
    CreateAdoptionRequest,
    CreateEvaluationRequest,
    EvaluationResponse,
    RequirementEvaluationResultDTO,
    SaveAnswersRequest,
    WorkspaceResponse,
)
from conformly.customer_demo.service import (
    adopt_evaluation,
    evaluate_answers,
    get_workspace_data,
)
from conformly.customer_demo.service import (
    save_answers as service_save_answers,
)
from conformly.db.session import get_db

MAX_REQUEST_BODY_BYTES = 16 * 1024  # 16 KiB

SAFE_KNOWN_PREFIXES = (
    "Customer demo",
    "Conflict:",
    "MFA",
    "Whole-tenant",
    "Workforce",
    "External advisor",
    "Role not admitted",
    "Tenant not found",
    "Tenant lifecycle",
    "Payload exceeds",
    "Malformed",
    "Mismatched",
    "Cannot evaluate",
    "Unknown pack",
    "Referenced",
    "Evaluation",
    "Pack version mismatch",
    "Incompatible evaluator",
    "Invalid bundle digest",
    "Corrupted",
    "Explicit acknowledgement",
    "Invalid answers payload",
    "Unauthorized",
    "Not Found",
    "Malware scan unavailable",
    "Selected owner is not an eligible",
    "Adoption not found",
    "Control work item not found",
    "Stored file not found",
    "Evidence item not found",
    "Evidence revision not found",
    "Evidence link not found",
    "File is not part of this pinned",
)


def _is_customer_demo_path(path: str) -> bool:
    """Check if request path exactly matches customer demo route segments."""
    parts = [p for p in path.strip("/").split("/") if p]
    if (
        len(parts) >= 4
        and parts[0] == "v2"
        and parts[1] == "tenants"
        and parts[3] == "customer-demo"
    ):
        try:
            UUID(parts[2])
            return True
        except ValueError:
            return False
    return False


def _sanitize_error_detail(status_code: int, detail: Any) -> str:
    """Sanitize error messages to prevent echoing of client-submitted keys or values."""
    if isinstance(detail, str):
        if "<" in detail or ">" in detail or "{" in detail or "}" in detail or len(detail) > 200:
            return "Request processing failed"
        for prefix in SAFE_KNOWN_PREFIXES:
            if detail.startswith(prefix):
                return detail
    if status_code == status.HTTP_404_NOT_FOUND:
        return "Not Found"
    if status_code == status.HTTP_401_UNAUTHORIZED:
        return "Unauthorized"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "Customer demo access denied"
    if status_code == status.HTTP_409_CONFLICT:
        return "Conflict: Workspace state conflict"
    if status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
        return "Payload exceeds 16 KiB limit"
    if status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
        return "Request validation failed"
    return "Request processing failed"


def _apply_privacy_headers(response: Response, request: Request) -> None:
    """Apply strict privacy and caching headers to every response (success and error)."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"

    vary = response.headers.get("Vary")
    if vary:
        tokens = [t.strip() for t in vary.split(",") if t.strip()]
        if "Authorization" not in tokens:
            tokens.append("Authorization")
        response.headers["Vary"] = ", ".join(tokens)
    else:
        response.headers["Vary"] = "Authorization"

    req_id = getattr(request.state, "request_id", None) or request.headers.get("X-Correlation-ID")
    if req_id:
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", str(req_id))[:64]
        if sanitized:
            response.headers["X-Correlation-ID"] = sanitized


class CustomerDemoRoute(APIRoute):
    """Custom APIRoute enforcing pre-parse body size bounding and privacy headers on every outcome."""

    def get_route_handler(self) -> Callable[..., Any]:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            # Pre-parse body size bounding (R7)
            if request.method in ("POST", "PUT", "PATCH"):
                cl = request.headers.get("content-length")
                if cl is not None:
                    if cl == "":
                        resp = JSONResponse(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            content={"detail": "Malformed Content-Length header"},
                        )
                        _apply_privacy_headers(resp, request)
                        return resp
                    try:
                        cl_int = int(cl)
                        if cl_int < 0 or cl_int > MAX_REQUEST_BODY_BYTES:
                            resp = JSONResponse(
                                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                content={"detail": "Payload exceeds 16 KiB limit"},
                            )
                            _apply_privacy_headers(resp, request)
                            return resp
                    except ValueError:
                        resp = JSONResponse(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            content={"detail": "Malformed Content-Length header"},
                        )
                        _apply_privacy_headers(resp, request)
                        return resp

                chunks = []
                total = 0
                async for chunk in request.stream():
                    total += len(chunk)
                    if total > MAX_REQUEST_BODY_BYTES:
                        resp = JSONResponse(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            content={"detail": "Payload exceeds 16 KiB limit"},
                        )
                        _apply_privacy_headers(resp, request)
                        return resp
                    chunks.append(chunk)

                body_bytes = b"".join(chunks)

                if cl is not None and len(body_bytes) != int(cl):
                    resp = JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"detail": "Mismatched Content-Length header"},
                    )
                    _apply_privacy_headers(resp, request)
                    return resp

                async def receive() -> dict[str, Any]:
                    return {"type": "http.request", "body": body_bytes, "more_body": False}

                request = Request(request.scope, receive=receive)

            # Do NOT catch exceptions here - let them propagate out so that
            # get_db executes session.rollback() before error rendering!
            response = await original_route_handler(request)
            _apply_privacy_headers(response, request)
            return response

        return custom_route_handler


router = APIRouter(
    prefix="/v2/tenants/{tenant_id}/customer-demo",
    tags=["customer-demo"],
    route_class=CustomerDemoRoute,
)


@router.get(
    "/workspace",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
)
def get_workspace(
    tenant_id: UUID,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> WorkspaceResponse:
    """Authorized read of customer demo workspace state."""
    verify_customer_demo_admission(principal, tenant_context, operation="read", session=db)
    req_id = getattr(request.state, "request_id", None) or "req-customer-demo-read"
    data = get_workspace_data(
        db,
        principal=principal,
        tenant_context=tenant_context,
        request_id=req_id,
    )
    return WorkspaceResponse(**data)


@router.put(
    "/answers",
    response_model=AnswersResponse,
    status_code=status.HTTP_200_OK,
)
def save_answers(
    tenant_id: UUID,
    body: SaveAnswersRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> AnswersResponse:
    """Atomically save immutable answers revision for fictional company."""
    verify_customer_demo_admission(principal, tenant_context, operation="mutate", session=db)
    req_id = getattr(request.state, "request_id", None) or "req-customer-demo-save"
    saved = service_save_answers(
        session=db,
        principal=principal,
        tenant_context=tenant_context,
        expected_revision=body.expected_revision,
        company_code=body.company_code,
        raw_answers=body.answers,
        request_id=req_id,
    )
    return AnswersResponse(
        tenant_id=saved.tenant_id,
        revision=saved.revision,
        company_code=saved.company_code,
        answers=saved.answers,
        content_digest=saved.content_digest,
        created_at=saved.created_at,
    )


@router.post(
    "/evaluations",
    response_model=EvaluationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_evaluation(
    tenant_id: UUID,
    body: CreateEvaluationRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> EvaluationResponse:
    """Evaluate current answers against specified demo pack version."""
    verify_customer_demo_admission(principal, tenant_context, operation="mutate", session=db)
    req_id = getattr(request.state, "request_id", None) or "req-customer-demo-eval"
    eval_record = evaluate_answers(
        session=db,
        principal=principal,
        tenant_context=tenant_context,
        expected_revision=body.expected_revision,
        pack_version_id=body.pack_version_id,
        request_id=req_id,
    )
    return EvaluationResponse(
        id=eval_record.id,
        tenant_id=eval_record.tenant_id,
        answer_revision=eval_record.answer_revision,
        pack_version_id=eval_record.pack_version_id,
        bundle_digest=eval_record.bundle_digest,
        evaluator_version=eval_record.evaluator_version,
        content_digest=eval_record.content_digest,
        results=[RequirementEvaluationResultDTO.model_validate(r) for r in eval_record.results],
        created_at=eval_record.created_at,
    )


@router.post(
    "/adoptions",
    response_model=AdoptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def adopt_pack(
    tenant_id: UUID,
    body: CreateAdoptionRequest,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> AdoptionResponse:
    """Explicitly adopt evaluated demo pack version with acknowledgement."""
    verify_customer_demo_admission(principal, tenant_context, operation="mutate", session=db)
    req_id = getattr(request.state, "request_id", None) or "req-customer-demo-adopt"
    result = adopt_evaluation(
        session=db,
        principal=principal,
        tenant_context=tenant_context,
        expected_revision=body.expected_revision,
        evaluation_id=body.evaluation_id,
        pack_version_id=body.pack_version_id,
        acknowledge_synthetic=body.acknowledge_synthetic,
        acknowledge_missing_information=body.acknowledge_missing_information,
        request_id=req_id,
    )
    return AdoptionResponse(**result)


def register_customer_demo_routes(app: FastAPI, settings: Settings | None = None) -> None:
    """Register customer demo routes if enabled and in permitted environment."""
    cfg = settings or get_settings()
    if cfg.enable_customer_demo:
        verify_feature_enabled(cfg)

        existing_exc_handler = app.exception_handlers.get(Exception)
        existing_500_handler = app.exception_handlers.get(500)

        async def _demo_http_exc_handler(request: Request, exc: Exception) -> Response:
            if not isinstance(exc, HTTPException):
                raise exc
            if _is_customer_demo_path(request.url.path):
                resp = JSONResponse(
                    status_code=exc.status_code,
                    content={"detail": _sanitize_error_detail(exc.status_code, exc.detail)},
                )
                _apply_privacy_headers(resp, request)
                return resp
            return await http_exception_handler(request, exc)

        async def _demo_val_exc_handler(request: Request, exc: Exception) -> Response:
            if not isinstance(exc, RequestValidationError):
                raise exc
            if _is_customer_demo_path(request.url.path):
                resp = JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": "Request validation failed"},
                )
                _apply_privacy_headers(resp, request)
                return resp
            return await request_validation_exception_handler(request, exc)

        async def _demo_admission_exc_handler(request: Request, exc: Exception) -> Response:
            if not isinstance(exc, CustomerDemoAdmissionError):
                raise exc
            resp = JSONResponse(
                status_code=exc.status_code,
                content={"detail": _sanitize_error_detail(exc.status_code, exc.detail)},
            )
            _apply_privacy_headers(resp, request)
            return resp

        async def _demo_disabled_exc_handler(request: Request, exc: Exception) -> Response:
            if not isinstance(exc, CustomerDemoDisabledError):
                raise exc
            resp = JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "Not Found"},
            )
            _apply_privacy_headers(resp, request)
            return resp

        async def _demo_unexpected_exc_handler(request: Request, exc: Exception) -> Response:
            if isinstance(
                exc,
                (
                    HTTPException,
                    RequestValidationError,
                    CustomerDemoAdmissionError,
                    CustomerDemoDisabledError,
                ),
            ):
                raise exc
            if _is_customer_demo_path(request.url.path):
                resp = JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "Internal server error"},
                )
                _apply_privacy_headers(resp, request)
                return resp
            if existing_exc_handler is not None:
                res = existing_exc_handler(request, exc)
                if inspect.isawaitable(res):
                    return await res
                return res
            if existing_500_handler is not None:
                res = existing_500_handler(request, exc)
                if inspect.isawaitable(res):
                    return await res
                return res
            return PlainTextResponse(
                "Internal Server Error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        app.add_exception_handler(HTTPException, _demo_http_exc_handler)
        app.add_exception_handler(RequestValidationError, _demo_val_exc_handler)
        app.add_exception_handler(CustomerDemoAdmissionError, _demo_admission_exc_handler)
        app.add_exception_handler(CustomerDemoDisabledError, _demo_disabled_exc_handler)
        app.add_exception_handler(Exception, _demo_unexpected_exc_handler)

        from conformly.customer_demo.assessment_api import assessment_router
        from conformly.customer_demo.assessment_report_api import report_router
        from conformly.customer_demo.work_api import work_router

        app.include_router(router)
        app.include_router(work_router)
        app.include_router(assessment_router)
        app.include_router(report_router)

        if (
            cfg.enable_customer_preaudit
            and cfg.enable_customer_demo
            and cfg.environment in ("local", "development", "test")
        ):
            from conformly.customer_demo.preaudit_api import preaudit_router

            app.include_router(preaudit_router)

        if (
            cfg.enable_customer_readiness_verification
            and cfg.enable_customer_preaudit
            and cfg.enable_customer_demo
            and cfg.environment in ("local", "development", "test")
        ):
            from conformly.customer_demo.verification_api import verification_router

            app.include_router(verification_router)
