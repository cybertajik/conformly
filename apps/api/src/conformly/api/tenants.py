from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError
from conformly.authz.roles import Role
from conformly.db.session import get_db
from conformly.identity.models import MembershipStatus
from conformly.identity.service import (
    MembershipInvariantError,
    MembershipNotFoundError,
    change_membership_role,
    list_tenant_memberships,
    revoke_membership,
)

router = APIRouter(prefix="/v1/tenants", tags=["tenants"])


class TenantContextResponse(BaseModel):
    tenant_id: str
    role: Role


class MembershipResponse(BaseModel):
    id: UUID
    user_id: UUID
    email: str
    display_name: str
    role: Role
    status: MembershipStatus


class MembershipRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role


@router.get("/{tenant_id}/context", response_model=TenantContextResponse)
def read_tenant_context(tenant_context: CurrentTenant) -> TenantContextResponse:
    """Prove the caller's active membership in the selected tenant."""

    return TenantContextResponse(
        tenant_id=str(tenant_context.tenant_id),
        role=tenant_context.role,
    )


@router.get("/{tenant_id}/memberships", response_model=list[MembershipResponse])
def read_memberships(
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> list[MembershipResponse] | Response:
    try:
        memberships = list_tenant_memberships(
            database, principal, tenant_context, request.state.request_id
        )
    except AuthorizationDeniedError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "capability denied"},
        )
    return [
        MembershipResponse(
            id=membership.id,
            user_id=membership.user_id,
            email=membership.user.email,
            display_name=membership.user.display_name,
            role=membership.role,
            status=membership.status,
        )
        for membership in memberships
    ]


@router.patch(
    "/{tenant_id}/memberships/{membership_id}/role",
    response_model=MembershipResponse,
)
def update_membership_role(
    membership_id: UUID,
    update: MembershipRoleUpdate,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> MembershipResponse | Response:
    try:
        membership = change_membership_role(
            database,
            principal,
            tenant_context,
            membership_id,
            update.role,
            request.state.request_id,
        )
    except AuthorizationDeniedError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "capability denied"},
        )
    except MembershipNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "membership not found"},
        )
    except MembershipInvariantError as error:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(error)},
        )
    return MembershipResponse(
        id=membership.id,
        user_id=membership.user_id,
        email=membership.user.email,
        display_name=membership.user.display_name,
        role=membership.role,
        status=membership.status,
    )


@router.delete(
    "/{tenant_id}/memberships/{membership_id}",
    response_model=MembershipResponse,
)
def delete_membership(
    membership_id: UUID,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> MembershipResponse | Response:
    try:
        membership = revoke_membership(
            database,
            principal,
            tenant_context,
            membership_id,
            request.state.request_id,
        )
    except AuthorizationDeniedError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "capability denied"},
        )
    except MembershipNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "membership not found"},
        )
    except MembershipInvariantError as error:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(error)},
        )
    return MembershipResponse(
        id=membership.id,
        user_id=membership.user_id,
        email=membership.user.email,
        display_name=membership.user.display_name,
        role=membership.role,
        status=membership.status,
    )
