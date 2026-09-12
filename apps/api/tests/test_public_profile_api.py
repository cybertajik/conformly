"""Integration tests for Public Profiles & Trust Center API endpoints.

Covers:
- Public projection access: GET /v1/public/profiles/{slug}
- ETag caching, If-None-Match 304 response, and 404 for unpublished profiles
- Tenant configuration: GET & PUT /v1/tenants/{tenant_id}/public-profile
- Publication lifecycle: publish / unpublish with OCC versioning
- Credential management: third-party certs, linking pre-audit certificates,
  updating, revoking, deleting
- Compliance statements: adding, deleting
- Authorization boundaries and cross-tenant isolation
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from conformly.auth.dependencies import get_current_principal, get_tenant_context
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.crypto.fields import get_encrypted_field_codec
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
from conformly.preaudit.models import CertificateStatus, PreAuditCertificate


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
def test_data(db_session):
    tenant_a = Tenant(name="Cyberdyne Systems", slug="cyberdyne", status=TenantStatus.ACTIVE)
    tenant_b = Tenant(name="Weyland Corp", slug="weyland", status=TenantStatus.ACTIVE)
    db_session.add_all([tenant_a, tenant_b])
    db_session.flush()

    compliance_user = User(
        oidc_issuer="https://issuer.test",
        oidc_subject="comp-user",
        email="compliance@cyberdyne.com",
        display_name="Compliance Manager",
    )
    auditor_user = User(
        oidc_issuer="https://issuer.test",
        oidc_subject="auditor-user",
        email="auditor@cyberdyne.com",
        display_name="External Auditor",
    )
    db_session.add_all([compliance_user, auditor_user])
    db_session.flush()

    m_comp = Membership(
        tenant_id=tenant_a.id,
        user_id=compliance_user.id,
        role=Role.COMPLIANCE_MANAGER.value,
        status=MembershipStatus.ACTIVE,
    )
    m_auditor = Membership(
        tenant_id=tenant_a.id,
        user_id=auditor_user.id,
        role=Role.AUDITOR.value,
        status=MembershipStatus.ACTIVE,
    )
    db_session.add_all([m_comp, m_auditor])
    db_session.flush()

    # Pre-audit certificate for tenant A
    cert = PreAuditCertificate(
        id=uuid4(),
        tenant_id=tenant_a.id,
        pre_audit_id=uuid4(),
        certificate_number="CONF-2026-TEST99",
        status=CertificateStatus.ACTIVE,
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=365),
    )
    db_session.add(cert)
    db_session.flush()

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "compliance_user": compliance_user,
        "auditor_user": auditor_user,
        "cert": cert,
    }


@pytest.fixture
def client(db_session, test_data, test_codec):
    def override_db():
        yield db_session

    def override_principal():
        return Principal(
            user_id=test_data["compliance_user"].id,
            is_platform_admin=False,
        )

    def override_tenant():
        return TenantContext(
            tenant_id=test_data["tenant_a"].id,
            user_id=test_data["compliance_user"].id,
            role=Role.COMPLIANCE_MANAGER,
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_principal] = override_principal
    app.dependency_overrides[get_tenant_context] = override_tenant
    app.dependency_overrides[get_encrypted_field_codec] = lambda: test_codec

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


class TestPublicProfilesAPI:
    def test_public_profile_full_lifecycle(self, client: TestClient, test_data: dict) -> None:
        tenant_id = str(test_data["tenant_a"].id)
        cert_id = str(test_data["cert"].id)

        # 1. Initially, public lookup for unpublished profile returns 404
        resp = client.get("/v1/public/profiles/cyberdyne")
        assert resp.status_code == 404

        # 2. Get/initialize tenant draft
        resp = client.get(f"/v1/tenants/{tenant_id}/public-profile")
        assert resp.status_code == 200
        profile = resp.json()
        assert profile["slug"] == "cyberdyne"
        assert profile["is_published"] is False
        assert profile["version"] == 1

        # 3. Configure branding and details
        resp = client.put(
            f"/v1/tenants/{tenant_id}/public-profile",
            json={
                "display_name": "Cyberdyne Systems Security & Trust",
                "description": "Leading provider of autonomous compliance infrastructure.",
                "logo_url": "https://cyberdyne.com/logo.png",
                "website_url": "https://cyberdyne.com",
                "primary_contact_email": "security@cyberdyne.com",
                "slug": "cyberdyne-trust",
                "expected_version": 1,
            },
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["display_name"] == "Cyberdyne Systems Security & Trust"
        assert updated["slug"] == "cyberdyne-trust"
        assert updated["version"] == 2

        # 4. OCC conflict on stale version
        resp_conflict = client.put(
            f"/v1/tenants/{tenant_id}/public-profile",
            json={
                "display_name": "Cyberdyne Conflict Test",
                "slug": "cyberdyne-trust",
                "expected_version": 1,  # Version is now 2
            },
        )
        assert resp_conflict.status_code == 409

        # 5. Add third-party credential (ISO 27001)
        resp = client.post(
            f"/v1/tenants/{tenant_id}/public-profile/credentials",
            json={
                "title": "ISO/IEC 27001:2022 Certification",
                "issuer_name": "BSI Group",
                "scope_description": (
                    "Information security management for global SaaS infrastructure."
                ),
                "issued_at": datetime.now(UTC).isoformat(),
                "valid_until": (datetime.now(UTC) + timedelta(days=730)).isoformat(),
                "verification_url": "https://verify.bsigroup.com/cyberdyne",
                "is_publicly_visible": True,
                "display_order": 1,
            },
        )
        assert resp.status_code == 201
        iso_cred = resp.json()
        assert iso_cred["credential_type"] == "third_party"
        iso_id = iso_cred["id"]

        # 6. Link Conformly Pre-Audit certificate
        resp = client.post(
            f"/v1/tenants/{tenant_id}/public-profile/credentials/link-preaudit",
            json={
                "certificate_id": cert_id,
                "is_publicly_visible": True,
                "display_order": 0,
            },
        )
        assert resp.status_code == 201
        preaudit_cred = resp.json()
        assert preaudit_cred["credential_type"] == "conformly_readiness"
        assert preaudit_cred["source_certificate_id"] == cert_id

        # 7. Add public compliance statement
        resp = client.post(
            f"/v1/tenants/{tenant_id}/public-profile/statements",
            json={
                "title": "Data Sovereignty & Encryption",
                "statement_content": (
                    "All tenant data is protected with application-layer AES-256-GCM "
                    "envelope encryption."
                ),
                "display_order": 0,
                "is_publicly_visible": True,
            },
        )
        assert resp.status_code == 201
        stmt = resp.json()
        stmt_id = stmt["id"]

        # 8. Still returns 404 publicly before publication
        resp = client.get("/v1/public/profiles/cyberdyne-trust")
        assert resp.status_code == 404

        # 9. Publish profile
        current_prof = client.get(f"/v1/tenants/{tenant_id}/public-profile").json()
        resp = client.post(
            f"/v1/tenants/{tenant_id}/public-profile/publish",
            json={"expected_version": current_prof["version"]},
        )
        assert resp.status_code == 200
        pub = resp.json()
        assert pub["is_published"] is True

        # 10. Public lookup succeeds
        pub_resp = client.get("/v1/public/profiles/cyberdyne-trust")
        assert pub_resp.status_code == 200
        public_data = pub_resp.json()
        assert public_data["slug"] == "cyberdyne-trust"
        assert public_data["display_name"] == "Cyberdyne Systems Security & Trust"
        assert public_data["conformly_verified"] is True
        assert (
            "Conformly is an audit-readiness and compliance operations platform"
            in public_data["disclaimer"]
        )
        assert len(public_data["credentials"]) == 2
        assert len(public_data["statements"]) == 1

        # Check caching headers
        etag = pub_resp.headers.get("ETag")
        assert etag is not None
        assert "public, max-age=300, must-revalidate" in pub_resp.headers.get("Cache-Control", "")

        # 11. Conditional GET with matching If-None-Match returns 304 Not Modified
        etag_resp = client.get(
            "/v1/public/profiles/cyberdyne-trust", headers={"If-None-Match": etag}
        )
        assert etag_resp.status_code == 304

        # 12. Update credential
        resp = client.put(
            f"/v1/tenants/{tenant_id}/public-profile/credentials/{iso_id}",
            json={
                "title": "ISO/IEC 27001:2022 Certified (Global)",
                "issuer_name": "BSI Group Americas",
                "scope_description": "Updated scope including North America datacenters.",
                "is_publicly_visible": True,
                "display_order": 1,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "ISO/IEC 27001:2022 Certified (Global)"

        # 13. Revoke credential
        resp = client.post(
            f"/v1/tenants/{tenant_id}/public-profile/credentials/{iso_id}/revoke",
            json={"reason": "Superseded by recertification audit."},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "revoked"

        # Revoked credential should no longer appear in public view
        pub_resp_after_revocation = client.get("/v1/public/profiles/cyberdyne-trust")
        assert pub_resp_after_revocation.status_code == 200
        assert len(pub_resp_after_revocation.json()["credentials"]) == 1

        # 14. Delete statement
        del_stmt = client.delete(f"/v1/tenants/{tenant_id}/public-profile/statements/{stmt_id}")
        assert del_stmt.status_code == 204

        # 15. Unpublish profile
        current_prof_before_unpublish = client.get(f"/v1/tenants/{tenant_id}/public-profile").json()
        resp = client.post(
            f"/v1/tenants/{tenant_id}/public-profile/unpublish",
            json={"expected_version": current_prof_before_unpublish["version"]},
        )
        assert resp.status_code == 200
        assert resp.json()["is_published"] is False

        # 16. Public lookup returns 404 again
        resp = client.get("/v1/public/profiles/cyberdyne-trust")
        assert resp.status_code == 404

    def test_cross_tenant_access_denied(self, client: TestClient, test_data: dict) -> None:
        # Context is tenant_a, attempting to access tenant_b
        tenant_b_id = str(test_data["tenant_b"].id)
        resp = client.get(f"/v1/tenants/{tenant_b_id}/public-profile")
        assert resp.status_code == 403
        assert "Cross-tenant access denied" in resp.json()["detail"]

    def test_role_based_access_control(
        self, db_session: Session, test_data: dict, test_codec
    ) -> None:
        tenant_id = str(test_data["tenant_a"].id)

        def override_db():
            yield db_session

        def override_auditor_principal():
            return Principal(
                user_id=test_data["auditor_user"].id,
                is_platform_admin=False,
            )

        def override_auditor_tenant():
            return TenantContext(
                tenant_id=test_data["tenant_a"].id,
                user_id=test_data["auditor_user"].id,
                role=Role.AUDITOR,
            )

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_principal] = override_auditor_principal
        app.dependency_overrides[get_tenant_context] = override_auditor_tenant
        app.dependency_overrides[get_encrypted_field_codec] = lambda: test_codec

        with TestClient(app) as auditor_client:
            # Auditor can read draft
            resp = auditor_client.get(f"/v1/tenants/{tenant_id}/public-profile")
            assert resp.status_code == 200

            # Auditor CANNOT configure profile
            resp = auditor_client.put(
                f"/v1/tenants/{tenant_id}/public-profile",
                json={
                    "display_name": "Auditor Attempt",
                    "expected_version": 1,
                },
            )
            assert resp.status_code == 403

            # Auditor CANNOT publish
            resp = auditor_client.post(
                f"/v1/tenants/{tenant_id}/public-profile/publish",
                json={"expected_version": 1},
            )
            assert resp.status_code == 403

            # Auditor CANNOT add credentials
            resp = auditor_client.post(
                f"/v1/tenants/{tenant_id}/public-profile/credentials",
                json={
                    "title": "Auditor Badge",
                    "issuer_name": "Auditor",
                    "scope_description": "Auditor added credential scope.",
                    "issued_at": datetime.now(UTC).isoformat(),
                },
            )
            assert resp.status_code == 403

        app.dependency_overrides.clear()
