import base64
import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conformly.auth.session import hash_session_id
from conformly.auth.tokens import TokenClaims, TokenVerifier, get_token_verifier
from conformly.authz.roles import Role
from conformly.crypto.envelope import EnvelopeEncryptionService, get_envelope_encryption_service
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.db.session import get_db
from conformly.identity.models import AuthSession, Membership, MembershipStatus, Tenant, User
from conformly.main import app
from conformly.storage.providers import MemoryStorageProvider, StorageProvider, get_storage_provider


class FakeTokenVerifier(TokenVerifier):
    def __init__(self, claims: TokenClaims) -> None:
        self._claims = claims

    def verify(self, token: str) -> TokenClaims:
        return self._claims


def make_test_encryption() -> EnvelopeEncryptionService:
    raw_key = os.urandom(32)
    b64_key = base64.b64encode(raw_key).decode("ascii")
    return EnvelopeEncryptionService(
        AES256GCMProvider(), LocalKeyManagementProvider({"v1": b64_key}, "v1")
    )


def seed_user_and_tenant(
    session: Session, role: Role = Role.OWNER
) -> tuple[User, Tenant, TokenClaims]:
    session_id = f"session-{uuid4().hex[:8]}"
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject=str(uuid4()),
        email=f"user-{uuid4().hex[:8]}@example.test",
        display_name="API Test User",
    )
    tenant = Tenant(name="Test Tenant", slug=f"tenant-{uuid4().hex[:8]}")
    session.add_all([user, tenant])
    session.flush()

    membership = Membership(
        tenant_id=tenant.id,
        user_id=user.id,
        role=role,
        status=MembershipStatus.ACTIVE,
    )
    auth_session = AuthSession(
        user_id=user.id,
        session_id_hash=hash_session_id(session_id),
        expires_at=expires_at,
    )
    session.add_all([membership, auth_session])
    session.commit()

    claims = TokenClaims(
        issuer=user.oidc_issuer,
        subject=user.oidc_subject,
        session_id=session_id,
        expires_at=int(expires_at.timestamp()),
        email=user.email,
        email_verified=True,
        display_name=user.display_name,
    )
    return user, tenant, claims


@pytest.fixture
def client_and_storage(
    session: Session,
) -> Generator[tuple[TestClient, MemoryStorageProvider, EnvelopeEncryptionService], None, None]:
    storage = MemoryStorageProvider()
    encryption = make_test_encryption()

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_storage_provider] = lambda: storage
    app.dependency_overrides[get_envelope_encryption_service] = lambda: encryption

    client = TestClient(app)
    try:
        yield client, storage, encryption
    finally:
        app.dependency_overrides.clear()


def test_upload_file_api_success(
    session: Session,
    client_and_storage: tuple[TestClient, StorageProvider, EnvelopeEncryptionService],
) -> None:
    client, storage, _ = client_and_storage
    _, tenant, claims = seed_user_and_tenant(session, Role.OWNER)
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(claims)

    file_content = b"Content of compliance report"
    response = client.post(
        f"/v1/tenants/{tenant.id}/files",
        headers={"Authorization": "Bearer test-token"},
        files={"file": ("report.pdf", file_content, "application/pdf")},
        data={"classification": "Restricted"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == "report.pdf"
    assert data["classification"] == "Restricted"
    assert data["plaintext_size_bytes"] == len(file_content)
    file_id = data["id"]

    # Verify download API returns the exact decrypted bytes
    dl_response = client.get(
        f"/v1/tenants/{tenant.id}/files/{file_id}/download",
        headers={"Authorization": "Bearer test-token"},
    )
    assert dl_response.status_code == 200
    assert dl_response.content == file_content
    assert dl_response.headers["content-type"] == "application/pdf"
    assert 'attachment; filename="report.pdf"' in dl_response.headers["content-disposition"]


def test_upload_file_prohibited_extension(
    session: Session,
    client_and_storage: tuple[TestClient, StorageProvider, EnvelopeEncryptionService],
) -> None:
    client, _, _ = client_and_storage
    _, tenant, claims = seed_user_and_tenant(session, Role.OWNER)
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(claims)

    response = client.post(
        f"/v1/tenants/{tenant.id}/files",
        headers={"Authorization": "Bearer test-token"},
        files={"file": ("malware.exe", b"binary", "application/x-msdownload")},
        data={"classification": "Public"},
    )
    assert response.status_code == 400
    assert "prohibited" in response.json()["detail"]


def test_role_capability_enforcement_on_files(
    session: Session,
    client_and_storage: tuple[TestClient, StorageProvider, EnvelopeEncryptionService],
) -> None:
    client, _, _ = client_and_storage

    # 1. Owner uploads a file
    _, tenant, owner_claims = seed_user_and_tenant(session, Role.OWNER)
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(owner_claims)
    upload_res = client.post(
        f"/v1/tenants/{tenant.id}/files",
        headers={"Authorization": "Bearer test-token"},
        files={"file": ("doc.txt", b"secret info", "text/plain")},
        data={"classification": "Internal"},
    )
    assert upload_res.status_code == 201
    file_id = upload_res.json()["id"]

    # 2. Contributor can upload and download, but CANNOT delete
    contributor_user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject=str(uuid4()),
        email=f"contrib-{uuid4().hex[:8]}@example.test",
        display_name="Contributor",
    )
    session.add(contributor_user)
    session.flush()
    session.add_all(
        [
            Membership(
                tenant_id=tenant.id,
                user_id=contributor_user.id,
                role=Role.CONTRIBUTOR,
                status=MembershipStatus.ACTIVE,
            ),
            AuthSession(
                user_id=contributor_user.id,
                session_id_hash=hash_session_id("contrib-session"),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            ),
        ]
    )
    session.commit()

    contrib_claims = TokenClaims(
        issuer=contributor_user.oidc_issuer,
        subject=contributor_user.oidc_subject,
        session_id="contrib-session",
        expires_at=int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        email=contributor_user.email,
        email_verified=True,
        display_name=contributor_user.display_name,
    )
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(contrib_claims)

    # Contributor download works
    assert (
        client.get(
            f"/v1/tenants/{tenant.id}/files/{file_id}/download",
            headers={"Authorization": "Bearer test-token"},
        ).status_code
        == 200
    )

    # Contributor delete is 403 Forbidden
    assert (
        client.delete(
            f"/v1/tenants/{tenant.id}/files/{file_id}",
            headers={"Authorization": "Bearer test-token"},
        ).status_code
        == 403
    )

    # 3. Auditor can download, but CANNOT upload
    auditor_user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject=str(uuid4()),
        email=f"auditor-{uuid4().hex[:8]}@example.test",
        display_name="Auditor",
    )
    session.add(auditor_user)
    session.flush()
    session.add_all(
        [
            Membership(
                tenant_id=tenant.id,
                user_id=auditor_user.id,
                role=Role.AUDITOR,
                status=MembershipStatus.ACTIVE,
            ),
            AuthSession(
                user_id=auditor_user.id,
                session_id_hash=hash_session_id("auditor-session"),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            ),
        ]
    )
    session.commit()

    auditor_claims = TokenClaims(
        issuer=auditor_user.oidc_issuer,
        subject=auditor_user.oidc_subject,
        session_id="auditor-session",
        expires_at=int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        email=auditor_user.email,
        email_verified=True,
        display_name=auditor_user.display_name,
    )
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(auditor_claims)

    # Auditor upload is 403 Forbidden
    assert (
        client.post(
            f"/v1/tenants/{tenant.id}/files",
            headers={"Authorization": "Bearer test-token"},
            files={"file": ("audit.txt", b"log", "text/plain")},
            data={"classification": "Internal"},
        ).status_code
        == 403
    )

    # Auditor download succeeds
    assert (
        client.get(
            f"/v1/tenants/{tenant.id}/files/{file_id}/download",
            headers={"Authorization": "Bearer test-token"},
        ).status_code
        == 200
    )


def test_cross_tenant_api_isolation(
    session: Session,
    client_and_storage: tuple[TestClient, StorageProvider, EnvelopeEncryptionService],
) -> None:
    client, _, _ = client_and_storage

    # Tenant A uploads file
    _, tenant_a, claims_a = seed_user_and_tenant(session, Role.OWNER)
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(claims_a)
    upload_res = client.post(
        f"/v1/tenants/{tenant_a.id}/files",
        headers={"Authorization": "Bearer test-token"},
        files={"file": ("tenant_a.pdf", b"tenant a confidential data", "application/pdf")},
        data={"classification": "Restricted"},
    )
    assert upload_res.status_code == 201
    file_a_id = upload_res.json()["id"]

    # Tenant B user tries to access Tenant A's file
    _, tenant_b, claims_b = seed_user_and_tenant(session, Role.OWNER)
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(claims_b)

    # Querying Tenant A's file ID in Tenant B scope -> 404
    meta_res = client.get(
        f"/v1/tenants/{tenant_b.id}/files/{file_a_id}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert meta_res.status_code == 404

    # Downloading Tenant A's file ID in Tenant B scope -> 404
    dl_res = client.get(
        f"/v1/tenants/{tenant_b.id}/files/{file_a_id}/download",
        headers={"Authorization": "Bearer test-token"},
    )
    assert dl_res.status_code == 404

    # Tenant B trying to specify Tenant A in URL path -> 403 Forbidden
    cross_path_res = client.get(
        f"/v1/tenants/{tenant_a.id}/files/{file_a_id}/download",
        headers={"Authorization": "Bearer test-token"},
    )
    assert cross_path_res.status_code == 403
