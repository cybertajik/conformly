from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from conformly.auth.session import authenticate_claims
from conformly.auth.tokens import AuthenticationError, TokenVerifier, get_token_verifier
from conformly.authz.policy import Principal, TenantContext
from conformly.db.session import get_db
from conformly.tenancy.context import TenantContextError, resolve_tenant_context

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
    database: Annotated[Session, Depends(get_db)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = verifier.verify(credentials.credentials)
        return authenticate_claims(database, claims)
    except AuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid authentication",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


def get_tenant_context(
    tenant_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    database: Annotated[Session, Depends(get_db)],
) -> TenantContext:
    try:
        return resolve_tenant_context(database, principal, tenant_id)
    except TenantContextError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="tenant access denied"
        ) from error


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]
CurrentTenant = Annotated[TenantContext, Depends(get_tenant_context)]
