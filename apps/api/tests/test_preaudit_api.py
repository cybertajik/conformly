"""Tests for pre-audit API endpoints."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.db.base import Base
from conformly.db.session import get_db
from conformly.frameworks.models import (
    AdoptionStatus,
    CanonicalControl,
    Framework,
    FrameworkVersion,
    ReleaseState,
    TenantFrameworkAdoption,
)
from conformly.identity.models import (
    Membership,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
)
from conformly.main import app
from conformly.storage.models import StoredFile  # noqa: F401


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
    tenant = Tenant(name="Test Co", slug="test-co", status=TenantStatus.ACTIVE)
    db_session.add(tenant)
    db_session.flush()

    user = User(
        oidc_issuer="https://issuer.test",
        oidc_subject="user-subject",
        email="user@test.co",
        display_name="Test User",
    )
    reviewer = User(
        oidc_issuer="https://issuer.test",
        oidc_subject="reviewer-subject",
        email="reviewer@test.co",
        display_name="Reviewer",
    )
    db_session.add_all([user, reviewer])
    db_session.flush()

    for u in (user, reviewer):
        m = Membership(
            tenant_id=tenant.id,
            user_id=u.id,
            role="compliance_manager",
            status=MembershipStatus.ACTIVE,
        )
        db_session.add(m)
    db_session.flush()

    fw = Framework(slug="soc2", name="SOC 2")
    db_session.add(fw)
    db_session.flush()

    fv = FrameworkVersion(
        framework_id=fw.id,
        version="2024",
        release_state=ReleaseState.RELEASED,
        created_by_user_id=user.id,
    )
    db_session.add(fv)
    db_session.flush()

    ctrl = CanonicalControl(
        framework_version_id=fv.id,
        identifier="CC1.1",
        title="Control Environment",
        description="Test control",
        category="default",
    )
    db_session.add(ctrl)
    db_session.flush()

    adoption = TenantFrameworkAdoption(
        tenant_id=tenant.id,
        framework_id=fw.id,
        framework_version_id=fv.id,
        status=AdoptionStatus.ACTIVE,
        adopted_at=datetime.now(UTC),
        adopted_by_user_id=user.id,
    )
    db_session.add(adoption)
    db_session.flush()

    return {
        "tenant": tenant,
        "user": user,
        "reviewer": reviewer,
        "adoption": adoption,
        "ctrl": ctrl,
    }


@pytest.fixture
def client(db_session, test_data):
    from conformly.auth.dependencies import get_current_principal, get_tenant_context

    def override_db():
        yield db_session

    def override_principal():
        return Principal(
            user_id=test_data["user"].id,
            is_platform_admin=False,
        )

    def override_tenant():
        return TenantContext(
            tenant_id=test_data["tenant"].id,
            user_id=test_data["user"].id,
            role=Role.COMPLIANCE_MANAGER,
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_principal] = override_principal
    app.dependency_overrides[get_tenant_context] = override_tenant
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestCreatePreAuditEndpoint:
    def test_create_success(self, client, test_data):
        resp = client.post(
            f"/v1/tenants/{test_data['tenant'].id}/pre-audits/",
            json={
                "title": "SOC 2 Readiness Assessment",
                "description": "Pre-audit readiness check",
                "framework_adoption_id": str(test_data["adoption"].id),
                "lead_user_id": str(test_data["user"].id),
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "SOC 2 Readiness Assessment"
        assert data["status"] == "planning"
        assert data["rule_version"] == "v1.0.0"

    def test_create_invalid_adoption(self, client, test_data):
        resp = client.post(
            f"/v1/tenants/{test_data['tenant'].id}/pre-audits/",
            json={
                "title": "Bad",
                "framework_adoption_id": str(uuid4()),
                "lead_user_id": str(test_data["user"].id),
            },
        )
        assert resp.status_code == 400


class TestListPreAudits:
    def test_list_empty(self, client, test_data):
        resp = client.get(f"/v1/tenants/{test_data['tenant'].id}/pre-audits/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_items(self, client, test_data):
        client.post(
            f"/v1/tenants/{test_data['tenant'].id}/pre-audits/",
            json={
                "title": "Test",
                "framework_adoption_id": str(test_data["adoption"].id),
                "lead_user_id": str(test_data["user"].id),
            },
        )
        resp = client.get(f"/v1/tenants/{test_data['tenant'].id}/pre-audits/")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestRunChecksEndpoint:
    def test_run_checks(self, client, test_data):
        create = client.post(
            f"/v1/tenants/{test_data['tenant'].id}/pre-audits/",
            json={
                "title": "Test",
                "framework_adoption_id": str(test_data["adoption"].id),
                "lead_user_id": str(test_data["user"].id),
            },
        )
        pa_id = create.json()["id"]

        resp = client.post(f"/v1/tenants/{test_data['tenant'].id}/pre-audits/{pa_id}/run-checks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["overall_score"] is not None


class TestWordingCompliance:
    """Verify customer-facing responses do not use accreditation language."""

    def test_no_certification_language_in_response(self, client, test_data):
        resp = client.post(
            f"/v1/tenants/{test_data['tenant'].id}/pre-audits/",
            json={
                "title": "Readiness Assessment",
                "framework_adoption_id": str(test_data["adoption"].id),
                "lead_user_id": str(test_data["user"].id),
            },
        )
        body = resp.text.lower()
        assert "accredited" not in body
        assert "certified" not in body
        assert "certification body" not in body
