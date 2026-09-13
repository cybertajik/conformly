import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.roles import Role
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.db.session import get_db
from conformly.integrations.models import CredentialStatus
from conformly.integrations.service import (
    WebhookIdempotencyConflictError,
    WebhookReplayError,
    WebhookSignatureError,
    check_and_record_inbound_idempotency,
    create_integration_credential,
    create_webhook_subscription,
    finalize_inbound_idempotency,
    get_credential_signing_secret,
    list_integration_credentials,
    list_webhook_subscriptions,
    revoke_integration_credential,
    verify_webhook_signature,
)

integrations_router = APIRouter(
    prefix="/v1/tenants/{tenant_id}/integrations", tags=["Integrations & Webhooks"]
)

PRIVILEGED_INTEGRATION_ROLES = frozenset({Role.OWNER, Role.ADMINISTRATOR, Role.COMPLIANCE_MANAGER})


def _check_integration_access(tenant: CurrentTenant) -> None:
    if tenant.role not in PRIVILEGED_INTEGRATION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not authorized to manage external integrations and credentials",
        )


class CreateCredentialRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    scopes: list[str] = Field(default_factory=lambda: ["webhooks:receive", "lms:write"])
    valid_until: datetime | None = None


class CreatedCredentialResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    key_id: str
    client_secret: str  # Only returned once upon creation!
    signing_secret: str  # Only returned once upon creation!
    scopes: list[str]
    status: str
    valid_until: datetime | None = None
    created_at: datetime


class CredentialSummaryResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    key_id: str
    scopes: list[str]
    status: str
    valid_until: datetime | None = None
    created_at: datetime
    revoked_at: datetime | None = None


class CreateWebhookSubscriptionRequest(BaseModel):
    target_url: str = Field(min_length=8, max_length=1024)
    description: str = Field(min_length=2, max_length=255)
    topics: list[str] = Field(min_length=1)


class CreatedWebhookSubscriptionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    target_url: str
    description: str
    topics: list[str]
    signing_secret: str  # Only returned once upon creation
    is_active: bool
    created_at: datetime


class WebhookSubscriptionSummaryResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    target_url: str
    description: str
    topics: list[str]
    is_active: bool
    created_at: datetime


@integrations_router.post(
    "/credentials",
    response_model=CreatedCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tenant_credential(
    tenant_id: UUID,
    request: CreateCredentialRequest,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
    codec: Annotated[EncryptedFieldCodec, Depends(get_encrypted_field_codec)],
) -> Any:
    """Issue a new tenant-scoped API key and HMAC signing secret."""
    _check_integration_access(tenant)
    result = create_integration_credential(
        database,
        codec,
        tenant_id=tenant.tenant_id,
        name=request.name,
        scopes=request.scopes,
        valid_until=request.valid_until,
        actor_id=principal.user_id,
    )
    database.commit()
    return CreatedCredentialResponse(
        id=result.credential.id,
        tenant_id=result.credential.tenant_id,
        name=result.credential.name,
        key_id=result.credential.key_id,
        client_secret=result.client_secret,
        signing_secret=result.signing_secret,
        scopes=result.credential.scopes,
        status=str(result.credential.status),
        valid_until=result.credential.valid_until,
        created_at=result.credential.created_at,
    )


@integrations_router.get("/credentials", response_model=list[CredentialSummaryResponse])
def list_tenant_credentials(
    tenant_id: UUID,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> Any:
    """List all integration credentials for the tenant (secrets are masked/omitted)."""
    _check_integration_access(tenant)
    creds = list_integration_credentials(database, tenant.tenant_id)
    return [
        CredentialSummaryResponse(
            id=c.id,
            tenant_id=c.tenant_id,
            name=c.name,
            key_id=c.key_id,
            scopes=c.scopes,
            status=str(c.status),
            valid_until=c.valid_until,
            created_at=c.created_at,
            revoked_at=c.revoked_at,
        )
        for c in creds
    ]


@integrations_router.post(
    "/credentials/{credential_id}/revoke", response_model=CredentialSummaryResponse
)
def revoke_tenant_credential(
    tenant_id: UUID,
    credential_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> Any:
    """Revoke an active integration credential."""
    _check_integration_access(tenant)
    try:
        updated = revoke_integration_credential(
            database,
            tenant_id=tenant.tenant_id,
            credential_id=credential_id,
            actor_id=principal.user_id,
        )
        database.commit()
        return CredentialSummaryResponse(
            id=updated.id,
            tenant_id=updated.tenant_id,
            name=updated.name,
            key_id=updated.key_id,
            scopes=updated.scopes,
            status=str(updated.status),
            valid_until=updated.valid_until,
            created_at=updated.created_at,
            revoked_at=updated.revoked_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@integrations_router.post(
    "/webhooks/subscriptions",
    response_model=CreatedWebhookSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_subscription(
    tenant_id: UUID,
    request: CreateWebhookSubscriptionRequest,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
    codec: Annotated[EncryptedFieldCodec, Depends(get_encrypted_field_codec)],
) -> Any:
    """Register an outbound webhook endpoint with generated HMAC secret."""
    _check_integration_access(tenant)
    sub, secret = create_webhook_subscription(
        database,
        codec,
        tenant_id=tenant.tenant_id,
        target_url=request.target_url,
        description=request.description,
        topics=request.topics,
        actor_id=principal.user_id,
    )
    database.commit()
    return CreatedWebhookSubscriptionResponse(
        id=sub.id,
        tenant_id=sub.tenant_id,
        target_url=sub.target_url,
        description=sub.description,
        topics=sub.topics,
        signing_secret=secret,
        is_active=sub.is_active,
        created_at=sub.created_at,
    )


@integrations_router.get(
    "/webhooks/subscriptions",
    response_model=list[WebhookSubscriptionSummaryResponse],
)
def list_subscriptions(
    tenant_id: UUID,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> Any:
    """List all registered outbound webhook subscriptions."""
    _check_integration_access(tenant)
    subs = list_webhook_subscriptions(database, tenant.tenant_id)
    return [
        WebhookSubscriptionSummaryResponse(
            id=s.id,
            tenant_id=s.tenant_id,
            target_url=s.target_url,
            description=s.description,
            topics=s.topics,
            is_active=s.is_active,
            created_at=s.created_at,
        )
        for s in subs
    ]


@integrations_router.post("/webhooks/inbound")
async def receive_inbound_webhook(
    tenant_id: UUID,
    request: Request,
    database: Annotated[Session, Depends(get_db)],
    codec: Annotated[EncryptedFieldCodec, Depends(get_encrypted_field_codec)],
    x_conformly_key_id: Annotated[str | None, Header()] = None,
    x_conformly_signature: Annotated[str | None, Header()] = None,
    x_conformly_timestamp: Annotated[str | None, Header()] = None,
    x_conformly_idempotency_key: Annotated[str | None, Header()] = None,
) -> Any:
    """General inbound webhook intake endpoint with HMAC signature, replay protection, and idempotency."""
    if not x_conformly_key_id or not x_conformly_signature or not x_conformly_timestamp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required webhook security headers: X-Conformly-Key-Id, X-Conformly-Signature, X-Conformly-Timestamp",
        )

    # Find matching credential
    creds = list_integration_credentials(database, tenant_id)
    matched = next(
        (
            c
            for c in creds
            if c.key_id == x_conformly_key_id and c.status == CredentialStatus.ACTIVE
        ),
        None,
    )
    if matched is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown or revoked integration credential",
        )

    raw_body = await request.body()
    signing_secret = get_credential_signing_secret(codec, matched)

    # Verify signature and replay window
    try:
        verify_webhook_signature(
            raw_body,
            signature_header=x_conformly_signature,
            timestamp_header=x_conformly_timestamp,
            signing_secret=signing_secret,
        )
    except WebhookReplayError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Replay protection error: {exc}",
        ) from exc
    except WebhookSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Signature verification failed: {exc}",
        ) from exc

    # Parse payload
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from exc

    idempotency_key = (
        x_conformly_idempotency_key or payload.get("event_id") or payload.get("idempotency_key")
    )
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing idempotency key (header X-Conformly-Idempotency-Key or payload event_id)",
        )

    topic = payload.get("topic", "general.webhook")

    try:
        event, is_new = check_and_record_inbound_idempotency(
            database,
            tenant_id=tenant_id,
            idempotency_key=str(idempotency_key),
            event_topic=topic,
            raw_body=raw_body,
            credential_id=matched.id,
        )
        if not is_new:
            # Idempotent replay: return cached response
            return {
                "status": "idempotent_replay",
                "idempotency_key": idempotency_key,
                "cached_response": event.response_payload,
            }

        # Process general webhook
        response_data = {
            "status": "accepted",
            "topic": topic,
            "idempotency_key": idempotency_key,
            "received_at": datetime.now().isoformat(),
        }
        finalize_inbound_idempotency(
            database,
            event,
            status_code=200,
            response_payload=response_data,
        )
        database.commit()
        return response_data

    except WebhookIdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
