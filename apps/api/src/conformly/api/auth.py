from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.auth.bootstrap import IdentityBootstrapError, bootstrap_identity_session
from conformly.auth.dependencies import CurrentPrincipal, bearer_scheme
from conformly.auth.lifecycle import SessionLifecycleError, revoke_own_auth_session
from conformly.auth.tokens import (
    DEV_DEFAULT_SECRET,
    AuthenticationError,
    TokenVerifier,
    get_token_verifier,
    mint_dev_token,
)
from conformly.config import get_settings
from conformly.db.session import get_db

router = APIRouter(prefix="/v1/auth", tags=["authentication"])


class SessionBootstrapResponse(BaseModel):
    user_id: str
    email: str
    display_name: str


@router.post("/session", response_model=SessionBootstrapResponse)
def bootstrap_session(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
    database: Annotated[Session, Depends(get_db)],
) -> SessionBootstrapResponse | Response:
    if credentials is None or credentials.scheme.lower() != "bearer":
        record_audit_event(
            database,
            tenant_id=None,
            actor_type=AuditActorType.SYSTEM,
            actor_id=None,
            action="auth.session_bootstrap",
            resource_type="auth_session",
            resource_id=None,
            request_id=request.state.request_id,
            outcome=AuditOutcome.DENIED,
            metadata={"reason": "credentials_missing"},
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "authentication required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = verifier.verify(credentials.credentials)
        user, auth_session = bootstrap_identity_session(
            database, claims, request_id=request.state.request_id
        )
    except (AuthenticationError, IdentityBootstrapError):
        record_audit_event(
            database,
            tenant_id=None,
            actor_type=AuditActorType.SYSTEM,
            actor_id=None,
            action="auth.session_bootstrap",
            resource_type="auth_session",
            resource_id=None,
            request_id=request.state.request_id,
            outcome=AuditOutcome.DENIED,
            metadata={"reason": "invalid_identity"},
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "invalid authentication"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    record_audit_event(
        database,
        tenant_id=None,
        actor_type=AuditActorType.USER,
        actor_id=user.id,
        action="auth.session_bootstrap",
        resource_type="auth_session",
        resource_id=str(auth_session.id),
        request_id=request.state.request_id,
        outcome=AuditOutcome.SUCCESS,
    )
    return SessionBootstrapResponse(
        user_id=str(user.id), email=user.email, display_name=user.display_name
    )


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    request: Request,
    principal: CurrentPrincipal,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
    database: Annotated[Session, Depends(get_db)],
) -> Response:
    if credentials is None:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)
    try:
        claims = verifier.verify(credentials.credentials)
        revoke_own_auth_session(
            database,
            principal,
            session_id=claims.session_id,
            request_id=request.state.request_id,
        )
    except (AuthenticationError, SessionLifecycleError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "invalid authentication"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class DevLoginRequest(BaseModel):
    email: str = "example-user@development.invalid"


class DevLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/dev-login", response_model=DevLoginResponse)
def dev_login(request: Request, body: DevLoginRequest | None = None) -> DevLoginResponse:
    if body is None:
        body = DevLoginRequest()
    settings = get_settings()
    if settings.environment not in ("development", "local", "test"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")

    secret = settings.invitation_token_pepper or DEV_DEFAULT_SECRET
    token = mint_dev_token(
        email=body.email,
        subject="example-user" if body.email == "example-user@development.invalid" else body.email,
        display_name="Example User"
        if body.email == "example-user@development.invalid"
        else body.email.split("@")[0],
        secret=secret,
    )
    return DevLoginResponse(access_token=token)
