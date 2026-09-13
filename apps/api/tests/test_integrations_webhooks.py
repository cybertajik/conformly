import json
import time
from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conformly.auth.dependencies import (
    get_current_principal,
    get_tenant_context,
)
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.db.session import get_db
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User
from conformly.integrations.models import CredentialStatus, InboundEventStatus
from conformly.integrations.service import (
    WebhookReplayError,
    WebhookSignatureError,
    authenticate_integration_credential,
    check_and_record_inbound_idempotency,
    compute_webhook_signature,
    create_integration_credential,
    finalize_inbound_idempotency,
    get_credential_signing_secret,
    revoke_integration_credential,
    verify_webhook_signature,
)
from conformly.main import app


def make_test_codec() -> EncryptedFieldCodec:
    import base64

    b64_key = base64.b64encode(b"\x07" * 32).decode("ascii")
    kms = LocalKeyManagementProvider({"v1": b64_key}, "v1")
    envelope = EnvelopeEncryptionService(AES256GCMProvider(), kms)
    return EncryptedFieldCodec(envelope)


def create_user_and_tenant(
    session: Session, role: Role = Role.OWNER
) -> tuple[User, Tenant, Principal, TenantContext]:
    tenant = Tenant(
        name="Integrations Test Tenant",
        slug=f"integrations-{uuid4().hex[:8]}",
        status=TenantStatus.ACTIVE,
    )
    user = User(
        oidc_issuer="https://identity.conformly.de",
        oidc_subject=str(uuid4()),
        email=f"user-{uuid4().hex[:8]}@example.com",
        display_name="Integrations Tester",
    )
    session.add_all([tenant, user])
    session.flush()

    membership = Membership(
        tenant_id=tenant.id,
        user_id=user.id,
        role=role,
        status=MembershipStatus.ACTIVE,
    )
    session.add(membership)
    session.commit()

    principal = Principal(user_id=user.id, mfa_verified=True)
    context = TenantContext(tenant_id=tenant.id, user_id=user.id, role=role)
    return user, tenant, principal, context


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    test_codec = make_test_codec()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_encrypted_field_codec] = lambda: test_codec
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_credential_creation_and_authentication(session: Session) -> None:
    _, tenant, _, _ = create_user_and_tenant(session)
    codec = make_test_codec()

    res = create_integration_credential(
        session,
        codec,
        tenant_id=tenant.id,
        name="LMS Integration Key",
        scopes=["lms:write", "webhooks:receive"],
    )
    session.commit()

    assert res.credential.key_id.startswith("cf_live_")
    assert res.client_secret.startswith("cfs_")
    assert len(res.signing_secret) == 64
    assert res.credential.status == CredentialStatus.ACTIVE

    # Verify authentication succeeds with valid credentials
    authenticated = authenticate_integration_credential(
        session,
        key_id=res.credential.key_id,
        client_secret=res.client_secret,
    )
    assert authenticated is not None
    assert authenticated.id == res.credential.id

    # Wrong secret fails authentication
    assert (
        authenticate_integration_credential(
            session,
            key_id=res.credential.key_id,
            client_secret="cfs_invalid_wrong_secret",
        )
        is None
    )

    # Unknown key fails authentication
    assert (
        authenticate_integration_credential(
            session,
            key_id="cf_live_nonexistent",
            client_secret=res.client_secret,
        )
        is None
    )

    # Decrypt signing secret roundtrip
    decrypted_sig_secret = get_credential_signing_secret(codec, res.credential)
    assert decrypted_sig_secret == res.signing_secret


def test_credential_revocation(session: Session) -> None:
    user, tenant, _, _ = create_user_and_tenant(session)
    codec = make_test_codec()

    res = create_integration_credential(
        session,
        codec,
        tenant_id=tenant.id,
        name="Expiring Partner Key",
        scopes=["lms:write"],
    )
    session.commit()

    revoked = revoke_integration_credential(
        session,
        tenant_id=tenant.id,
        credential_id=res.credential.id,
        actor_id=user.id,
    )
    session.commit()
    assert revoked.status == CredentialStatus.REVOKED
    assert revoked.revoked_at is not None

    # Revoked credential fails authentication
    assert (
        authenticate_integration_credential(
            session,
            key_id=res.credential.key_id,
            client_secret=res.client_secret,
        )
        is None
    )


def test_webhook_signature_and_replay_verification() -> None:
    secret = "a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef"
    payload = b'{"event":"test","status":"ok"}'
    now_ts = 1700000000

    sig = compute_webhook_signature(payload, now_ts, secret)

    # 1. Valid signature and timestamp pass
    verify_webhook_signature(
        payload,
        signature_header=sig,
        timestamp_header=now_ts,
        signing_secret=secret,
        tolerance_seconds=300,
        current_timestamp=now_ts + 10,
    )

    # 2. Altered payload fails verification
    with pytest.raises(WebhookSignatureError):
        verify_webhook_signature(
            b'{"event":"test","status":"tampered"}',
            signature_header=sig,
            timestamp_header=now_ts,
            signing_secret=secret,
            tolerance_seconds=300,
            current_timestamp=now_ts + 10,
        )

    # 3. Wrong secret fails verification
    with pytest.raises(WebhookSignatureError):
        verify_webhook_signature(
            payload,
            signature_header=sig,
            timestamp_header=now_ts,
            signing_secret="wrong_secret_wrong_secret_wrong_secret_wrong_secret1234567890",
            tolerance_seconds=300,
            current_timestamp=now_ts + 10,
        )

    # 4. Expired timestamp (> 300s) fails replay check
    with pytest.raises(WebhookReplayError):
        verify_webhook_signature(
            payload,
            signature_header=sig,
            timestamp_header=now_ts,
            signing_secret=secret,
            tolerance_seconds=300,
            current_timestamp=now_ts + 301,
        )

    # 5. Future timestamp (> 300s) fails replay check
    with pytest.raises(WebhookReplayError):
        verify_webhook_signature(
            payload,
            signature_header=sig,
            timestamp_header=now_ts + 500,
            signing_secret=secret,
            tolerance_seconds=300,
            current_timestamp=now_ts,
        )


def test_inbound_idempotency_service(session: Session) -> None:
    _, tenant, _, _ = create_user_and_tenant(session)
    payload_raw = b'{"msg":"hello world"}'
    key = "idem-key-999"

    # First attempt: new event
    event, is_new = check_and_record_inbound_idempotency(
        session,
        tenant_id=tenant.id,
        idempotency_key=key,
        event_topic="test.topic",
        raw_body=payload_raw,
    )
    assert is_new is True
    assert event.status == InboundEventStatus.PROCESSING

    # Finalize event
    finalize_inbound_idempotency(
        session,
        event,
        status_code=200,
        response_payload={"result": "success"},
    )
    session.commit()

    # Second attempt: idempotent replay returns existing record
    event2, is_new2 = check_and_record_inbound_idempotency(
        session,
        tenant_id=tenant.id,
        idempotency_key=key,
        event_topic="test.topic",
        raw_body=payload_raw,
    )
    assert is_new2 is False
    assert event2.id == event.id
    assert event2.status == InboundEventStatus.PROCESSED
    assert event2.response_payload == {"result": "success"}


def test_integration_credentials_api_endpoints(session: Session, client: TestClient) -> None:
    _, tenant, principal, context = create_user_and_tenant(session, role=Role.ADMINISTRATOR)
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_tenant_context] = lambda: context

    # 1. Create integration credential
    create_payload = {
        "name": "Production LMS Webhook Key",
        "scopes": ["lms:write", "webhooks:receive"],
    }
    resp = client.post(
        f"/v1/tenants/{tenant.id}/integrations/credentials",
        json=create_payload,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Production LMS Webhook Key"
    assert data["key_id"].startswith("cf_live_")
    assert "client_secret" in data
    assert "signing_secret" in data
    cred_id = data["id"]

    # 2. List credentials (secrets masked/omitted)
    resp_list = client.get(f"/v1/tenants/{tenant.id}/integrations/credentials")
    assert resp_list.status_code == 200
    items = resp_list.json()
    assert len(items) == 1
    assert items[0]["id"] == cred_id
    assert "client_secret" not in items[0]
    assert "signing_secret" not in items[0]

    # 3. Create outbound webhook subscription
    sub_payload = {
        "target_url": "https://api.external-lms.example.com/webhooks/compliance",
        "description": "Compliance status updates",
        "topics": ["compliance.control_updated", "evidence.created"],
    }
    resp_sub = client.post(
        f"/v1/tenants/{tenant.id}/integrations/webhooks/subscriptions",
        json=sub_payload,
    )
    assert resp_sub.status_code == 201
    assert "signing_secret" in resp_sub.json()

    # 4. Revoke credential
    resp_revoke = client.post(f"/v1/tenants/{tenant.id}/integrations/credentials/{cred_id}/revoke")
    assert resp_revoke.status_code == 200
    assert resp_revoke.json()["status"] == "revoked"


def test_inbound_signed_webhook_endpoint(session: Session, client: TestClient) -> None:
    _, tenant, principal, context = create_user_and_tenant(session, role=Role.OWNER)
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_tenant_context] = lambda: context

    # 1. Issue credential
    cred_resp = client.post(
        f"/v1/tenants/{tenant.id}/integrations/credentials",
        json={"name": "General Inbound Webhook Key", "scopes": ["webhooks:receive"]},
    )
    cred_data = cred_resp.json()
    key_id = cred_data["key_id"]
    signing_secret = cred_data["signing_secret"]

    # 2. Prepare payload & headers
    now = int(time.time())
    payload = {"event_id": f"evt-{uuid4().hex[:8]}", "topic": "asset.scan_completed", "score": 98.5}
    raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = compute_webhook_signature(raw_body, now, signing_secret)

    headers = {
        "Content-Type": "application/json",
        "X-Conformly-Key-Id": key_id,
        "X-Conformly-Signature": sig,
        "X-Conformly-Timestamp": str(now),
        "X-Conformly-Idempotency-Key": payload["event_id"],
    }

    # 3. Post webhook successfully
    post_resp = client.post(
        f"/v1/tenants/{tenant.id}/integrations/webhooks/inbound",
        content=raw_body,
        headers=headers,
    )
    assert post_resp.status_code == 200
    assert post_resp.json()["status"] == "accepted"

    # 4. Replay identical request -> idempotent replay
    replay_resp = client.post(
        f"/v1/tenants/{tenant.id}/integrations/webhooks/inbound",
        content=raw_body,
        headers=headers,
    )
    assert replay_resp.status_code == 200
    assert replay_resp.json()["status"] == "idempotent_replay"

    # 5. Invalid signature rejected
    bad_headers = dict(headers)
    bad_headers["X-Conformly-Signature"] = "0" * 64
    bad_resp = client.post(
        f"/v1/tenants/{tenant.id}/integrations/webhooks/inbound",
        content=raw_body,
        headers=bad_headers,
    )
    assert bad_resp.status_code == 401
