import base64
import io
import os
import zipfile
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from conformly.auth.dependencies import get_current_principal, get_tenant_context
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.db.base import Base
from conformly.db.session import get_db
from conformly.identity.models import (
    Membership,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
)
from conformly.main import app
from conformly.storage.providers import MemoryStorageProvider
from conformly.storage.service import StorageService, get_storage_service


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


@pytest.fixture
def storage_service(db_session):
    raw_key = os.urandom(32)
    b64_key = base64.b64encode(raw_key).decode("ascii")
    enc = EnvelopeEncryptionService(
        AES256GCMProvider(), LocalKeyManagementProvider({"v1": b64_key}, "v1")
    )
    return StorageService(db_session, MemoryStorageProvider(), enc)


@pytest.fixture
def test_data(db_session):
    tenant = Tenant(name="Cyberdyne Systems", slug="cyberdyne", status=TenantStatus.ACTIVE)
    db_session.add(tenant)
    db_session.flush()

    owner_user = User(
        id=uuid4(),
        oidc_issuer="https://issuer.test",
        oidc_subject="owner-sub",
        email="owner@cyberdyne.com",
        display_name="Owner User",
    )
    compliance_user = User(
        id=uuid4(),
        oidc_issuer="https://issuer.test",
        oidc_subject="comp-sub",
        email="compliance@cyberdyne.com",
        display_name="Compliance Manager",
    )
    db_session.add_all([owner_user, compliance_user])
    db_session.flush()

    m_owner = Membership(
        tenant_id=tenant.id,
        user_id=owner_user.id,
        role=Role.OWNER.value,
        status=MembershipStatus.ACTIVE,
    )
    m_comp = Membership(
        tenant_id=tenant.id,
        user_id=compliance_user.id,
        role=Role.COMPLIANCE_MANAGER.value,
        status=MembershipStatus.ACTIVE,
    )
    db_session.add_all([m_owner, m_comp])
    db_session.flush()

    return {
        "tenant": tenant,
        "owner_user": owner_user,
        "compliance_user": compliance_user,
    }


@pytest.fixture
def client(db_session, test_data, storage_service):
    tenant = test_data["tenant"]
    owner = test_data["owner_user"]

    def override_db():
        yield db_session

    def override_storage():
        return storage_service

    def override_principal():
        return Principal(user_id=owner.id, is_platform_admin=False)

    def override_context():
        return TenantContext(tenant_id=tenant.id, user_id=owner.id, role=Role.OWNER)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_storage_service] = override_storage
    app.dependency_overrides[get_current_principal] = override_principal
    app.dependency_overrides[get_tenant_context] = override_context

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_export_lifecycle_api(client: TestClient, test_data: dict) -> None:
    tenant_id = str(test_data["tenant"].id)

    # 1. Create an export
    resp = client.post(f"/v1/tenants/{tenant_id}/exports", json={"scope": "full"})
    assert resp.status_code == 201
    job_data = resp.json()
    assert job_data["status"] == "completed"
    assert job_data["records_count"] > 0
    export_id = job_data["id"]

    # 2. List exports
    list_resp = client.get(f"/v1/tenants/{tenant_id}/exports")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["id"] == export_id

    # 3. Get export details with manifest
    detail_resp = client.get(f"/v1/tenants/{tenant_id}/exports/{export_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["manifest"] is not None
    assert "tenant" in detail["manifest"]["record_counts"]

    # 4. Download export ZIP archive
    dl_resp = client.get(f"/v1/tenants/{tenant_id}/exports/{export_id}/download")
    assert dl_resp.status_code == 200
    assert dl_resp.headers["Content-Type"] == "application/zip"
    assert "conformly-export-" in dl_resp.headers["Content-Disposition"]

    zf = zipfile.ZipFile(io.BytesIO(dl_resp.content))
    assert "manifest.json" in zf.namelist()
    assert "data/tenant.json" in zf.namelist()


def test_cancellation_and_legal_hold_api(client: TestClient, test_data: dict) -> None:
    tenant_id = str(test_data["tenant"].id)

    # 1. Check initial status
    status_resp = client.get(f"/v1/tenants/{tenant_id}/cancellation")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "active"
    assert status_resp.json()["legal_hold"] is False

    # 2. Set legal hold
    hold_resp = client.post(
        f"/v1/tenants/{tenant_id}/legal-hold",
        json={"enabled": True, "reason": "SEC inquiry"},
    )
    assert hold_resp.status_code == 200
    assert hold_resp.json()["legal_hold"] is True

    # 3. Cancellation request with legal hold active should fail (409)
    fail_cancel = client.post(
        f"/v1/tenants/{tenant_id}/cancellation",
        json={"reason": "Moving off cloud", "confirm_slug": "cyberdyne"},
    )
    assert fail_cancel.status_code == 409

    # 4. Release legal hold
    release_hold = client.post(
        f"/v1/tenants/{tenant_id}/legal-hold",
        json={"enabled": False, "reason": "Inquiry completed"},
    )
    assert release_hold.status_code == 200
    assert release_hold.json()["legal_hold"] is False

    # 5. Request cancellation with slug mismatch fails (400)
    slug_fail = client.post(
        f"/v1/tenants/{tenant_id}/cancellation",
        json={"reason": "Moving off cloud", "confirm_slug": "wrong"},
    )
    assert slug_fail.status_code == 400

    # 6. Request cancellation succeeds
    cancel_resp = client.post(
        f"/v1/tenants/{tenant_id}/cancellation",
        json={"reason": "Moving off cloud", "confirm_slug": "cyberdyne"},
    )
    assert cancel_resp.status_code == 200
    cancelled = cancel_resp.json()
    assert cancelled["status"] == "cancelling"
    assert cancelled["is_export_window_active"] is True
    assert cancelled["days_remaining_in_export_window"] == 30
