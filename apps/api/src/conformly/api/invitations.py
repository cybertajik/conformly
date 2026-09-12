from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError
from conformly.authz.roles import Role
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.db.session import get_db
from conformly.identity.invitation_tokens import (
    InvitationTokenService,
    get_invitation_token_service,
)
from conformly.identity.invitations import (
    InvitationAcceptanceError,
    accept_membership_invitation,
    issue_membership_invitation,
)
from conformly.identity.models import InvitationStatus, normalize_email_address

router = APIRouter(prefix="/v1", tags=["invitations"])


class InvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    role: Role

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email_address(value)


class InvitationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    role: Role
    status: InvitationStatus
    expires_at: datetime


class InvitationAccept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str


class AcceptedMembershipResponse(BaseModel):
    tenant_id: UUID
    role: Role


@router.post(
    "/tenants/{tenant_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_invitation(
    invitation_data: InvitationCreate,
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
    tokens: Annotated[InvitationTokenService, Depends(get_invitation_token_service)],
    codec: Annotated[EncryptedFieldCodec, Depends(get_encrypted_field_codec)],
) -> InvitationResponse | Response:
    try:
        issued = issue_membership_invitation(
            database,
            principal,
            tenant_context,
            email=invitation_data.email,
            role=invitation_data.role,
            request_id=request.state.request_id,
            tokens=tokens,
            codec=codec,
        )
    except AuthorizationDeniedError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "capability denied"},
        )
    invitation = issued.invitation
    return InvitationResponse(
        id=invitation.id,
        tenant_id=invitation.tenant_id,
        email=invitation.email,
        role=invitation.role,
        status=invitation.status,
        expires_at=invitation.expires_at,
    )


@router.post("/invitations/accept", response_model=AcceptedMembershipResponse)
def accept_invitation(
    acceptance: InvitationAccept,
    request: Request,
    principal: CurrentPrincipal,
    database: Annotated[Session, Depends(get_db)],
    tokens: Annotated[InvitationTokenService, Depends(get_invitation_token_service)],
) -> AcceptedMembershipResponse | Response:
    try:
        membership = accept_membership_invitation(
            database,
            principal,
            token=acceptance.token,
            request_id=request.state.request_id,
            tokens=tokens,
        )
    except InvitationAcceptanceError:
        record_audit_event(
            database,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="membership.invitation_accept",
            resource_type="membership_invitation",
            resource_id=None,
            request_id=request.state.request_id,
            outcome=AuditOutcome.DENIED,
            metadata={"reason": "invalid_invitation"},
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "invitation cannot be accepted"},
        )
    return AcceptedMembershipResponse(
        tenant_id=membership.tenant_id,
        role=membership.role,
    )
