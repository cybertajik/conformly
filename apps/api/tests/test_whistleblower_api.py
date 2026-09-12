"""Integration tests for Whistleblower API endpoints: public anonymous reporting,
tracking with one-way secrets, handler case management, and strict role boundaries.
"""

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
from conformly.storage.models import StoredFile  # noqa: F401
from conformly.whistleblower.rate_limit import anonymous_whistleblower_rate_limiter

# ── Fixtures ───────────────────────────────────────────────────────────────


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
    tenant = Tenant(name="Cyberdyne Systems", slug="cyberdyne", status=TenantStatus.ACTIVE)
    db_session.add(tenant)
    db_session.flush()

    compliance_user = User(
        oidc_issuer="https://issuer.test",
        oidc_subject="comp-user",
        email="compliance@cyberdyne.com",
        display_name="Compliance Officer",
    )
    auditor_user = User(
        oidc_issuer="https://issuer.test",
        oidc_subject="auditor-user",
        email="auditor@cyberdyne.com",
        display_name="External Auditor",
    )
    investigator_user = User(
        oidc_issuer="https://issuer.test",
        oidc_subject="investigator-user",
        email="investigator@cyberdyne.com",
        display_name="Internal Investigator",
    )
    db_session.add_all([compliance_user, auditor_user, investigator_user])
    db_session.flush()

    m_comp = Membership(
        tenant_id=tenant.id,
        user_id=compliance_user.id,
        role=Role.COMPLIANCE_MANAGER.value,
        status=MembershipStatus.ACTIVE,
    )
    m_auditor = Membership(
        tenant_id=tenant.id,
        user_id=auditor_user.id,
        role=Role.AUDITOR.value,
        status=MembershipStatus.ACTIVE,
    )
    m_inv = Membership(
        tenant_id=tenant.id,
        user_id=investigator_user.id,
        role=Role.COMPLIANCE_MANAGER.value,
        status=MembershipStatus.ACTIVE,
    )
    db_session.add_all([m_comp, m_auditor, m_inv])
    db_session.flush()

    return {
        "tenant": tenant,
        "compliance_user": compliance_user,
        "auditor_user": auditor_user,
        "investigator_user": investigator_user,
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
            tenant_id=test_data["tenant"].id,
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


# ── Tests ──────────────────────────────────────────────────────────────────


class TestPublicWhistleblowerEndpoints:
    def test_anonymous_endpoints_return_429_when_limited(self, client: TestClient) -> None:
        slug = f"limited-{uuid4().hex}"
        case_id = "WB-2026-TEST"
        for _ in range(20):
            anonymous_whistleblower_rate_limiter.check("submit", slug, limit=20)
            anonymous_whistleblower_rate_limiter.check("message", f"{slug}:{case_id}", limit=20)
        for _ in range(10):
            anonymous_whistleblower_rate_limiter.check("access", f"{slug}:{case_id}", limit=10)

        submit = client.post(
            f"/v1/public/whistleblower/{slug}/submit",
            json={"category": "test", "title": "test", "summary": "test"},
        )
        access = client.post(
            f"/v1/public/whistleblower/{slug}/access",
            json={"public_case_id": case_id, "return_secret": "invalid"},
        )
        message = client.post(
            f"/v1/public/whistleblower/{slug}/messages",
            json={"public_case_id": case_id, "return_secret": "invalid", "body": "test"},
        )

        assert submit.status_code == 429
        assert access.status_code == 429
        assert message.status_code == 429

    def test_public_portal_and_intake_flow(self, client: TestClient, test_data: dict) -> None:
        tenant_id = str(test_data["tenant"].id)

        # 1. Configure portal via handler endpoint
        resp = client.put(
            f"/v1/tenants/{tenant_id}/whistleblower/portal",
            json={
                "slug": "speak-up",
                "title": "Cyberdyne Speak-Up Line",
                "welcome_text": "Submit any concern completely anonymously.",
                "is_active": True,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["slug"] == "speak-up"

        # 2. Public lookup of portal (no auth required)
        pub_resp = client.get("/v1/public/whistleblower/speak-up")
        assert pub_resp.status_code == 200
        portal_data = pub_resp.json()
        assert portal_data["slug"] == "speak-up"
        assert portal_data["title"] == "Cyberdyne Speak-Up Line"

        # 3. Public intake of report (no auth required)
        submit_resp = client.post(
            "/v1/public/whistleblower/speak-up/submit",
            json={
                "category": "bribery",
                "title": "Improper supplier kickback",
                "summary": "Director receives undisclosed payments from supplier Acme.",
            },
        )
        assert submit_resp.status_code == 201
        submission = submit_resp.json()
        case_id = submission["public_case_id"]
        secret = submission["return_secret"]
        assert case_id.startswith("WB-")
        assert secret.startswith("wb_")

        # 4. Reporter accesses case with valid secret
        access_resp = client.post(
            "/v1/public/whistleblower/speak-up/access",
            json={"public_case_id": case_id, "return_secret": secret},
        )
        assert access_resp.status_code == 200
        case_view = access_resp.json()
        assert case_view["status"] == "submitted"
        assert len(case_view["messages"]) == 1
        assert "Director receives undisclosed payments" in case_view["messages"][0]["body"]

        # 5. Access with invalid secret fails with 401
        bad_access = client.post(
            "/v1/public/whistleblower/speak-up/access",
            json={"public_case_id": case_id, "return_secret": "wb_wrong_secret"},
        )
        assert bad_access.status_code == 401

        # 6. Reporter adds follow-up message
        msg_resp = client.post(
            "/v1/public/whistleblower/speak-up/messages",
            json={
                "public_case_id": case_id,
                "return_secret": secret,
                "body": "See invoice reference INV-9988 for evidence.",
            },
        )
        assert msg_resp.status_code == 201

        # 7. Check message thread contains both messages
        access_resp2 = client.post(
            "/v1/public/whistleblower/speak-up/access",
            json={"public_case_id": case_id, "return_secret": secret},
        )
        assert access_resp2.status_code == 200
        assert len(access_resp2.json()["messages"]) == 2


class TestAuthenticatedHandlerEndpoints:
    def test_handler_triage_and_assignment_flow(self, client: TestClient, test_data: dict) -> None:
        tenant_id = str(test_data["tenant"].id)

        # Setup portal
        client.put(
            f"/v1/tenants/{tenant_id}/whistleblower/portal",
            json={
                "slug": "ethics-hotline",
                "title": "Ethics Hotline",
                "welcome_text": "Speak up safely.",
                "is_active": True,
            },
        )

        # Public submit report
        submit_resp = client.post(
            "/v1/public/whistleblower/ethics-hotline/submit",
            json={
                "category": "safety",
                "title": "Safety violation in Sector 7",
                "summary": "Emergency exits blocked by excess inventory.",
            },
        )
        assert submit_resp.status_code == 201
        public_case_id = submit_resp.json()["public_case_id"]

        # Handler lists cases
        list_resp = client.get(f"/v1/tenants/{tenant_id}/whistleblower/cases")
        assert list_resp.status_code == 200
        cases_data = list_resp.json()
        assert cases_data["total"] >= 1
        matched = [c for c in cases_data["items"] if c["public_case_id"] == public_case_id]
        assert len(matched) == 1
        internal_case_id = matched[0]["id"]
        assert matched[0]["status"] == "submitted"

        # Handler gets case detail with decrypted summary and messages
        detail_resp = client.get(f"/v1/tenants/{tenant_id}/whistleblower/cases/{internal_case_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["summary"] == "Emergency exits blocked by excess inventory."
        assert len(detail["messages"]) == 1

        # Handler sends response to reporter
        handler_msg_resp = client.post(
            f"/v1/tenants/{tenant_id}/whistleblower/cases/{internal_case_id}/messages",
            json={"body": "Facility management has been dispatched to clear the exits."},
        )
        assert handler_msg_resp.status_code == 201

        # Handler updates case status
        status_resp = client.post(
            f"/v1/tenants/{tenant_id}/whistleblower/cases/{internal_case_id}/status",
            json={
                "status": "under_investigation",
                "closed_reason": None,
            },
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "under_investigation"

        # Handler assigns investigator
        investigator_id = str(test_data["investigator_user"].id)
        assign_resp = client.post(
            f"/v1/tenants/{tenant_id}/whistleblower/cases/{internal_case_id}/assign",
            json={"handler_user_id": investigator_id},
        )
        assert assign_resp.status_code == 201
        assert assign_resp.json()["handler_user_id"] == investigator_id


class TestWhistleblowerRoleAuthorization:
    def test_auditor_role_denied_access(self, client: TestClient, test_data: dict) -> None:
        tenant_id = str(test_data["tenant"].id)

        # Override principal & tenant to Auditor role
        def override_auditor_principal():
            return Principal(
                user_id=test_data["auditor_user"].id,
                is_platform_admin=False,
            )

        def override_auditor_tenant():
            return TenantContext(
                tenant_id=test_data["tenant"].id,
                user_id=test_data["auditor_user"].id,
                role=Role.AUDITOR,
            )

        app.dependency_overrides[get_current_principal] = override_auditor_principal
        app.dependency_overrides[get_tenant_context] = override_auditor_tenant

        # Case listing denied for Auditor
        list_resp = client.get(f"/v1/tenants/{tenant_id}/whistleblower/cases")
        assert list_resp.status_code == 403

        # Portal get denied for Auditor
        portal_resp = client.get(f"/v1/tenants/{tenant_id}/whistleblower/portal")
        assert portal_resp.status_code == 403

        # Case detail denied for Auditor
        detail_resp = client.get(f"/v1/tenants/{tenant_id}/whistleblower/cases/{uuid4()}")
        assert detail_resp.status_code == 403
