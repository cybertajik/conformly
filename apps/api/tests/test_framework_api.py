from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conformly.auth.session import hash_session_id
from conformly.auth.tokens import TokenClaims, TokenVerifier, get_token_verifier
from conformly.authz.roles import Role
from conformly.db.session import get_db
from conformly.frameworks.models import (
    CanonicalControl,
    Framework,
    FrameworkVersion,
    ReleaseState,
)
from conformly.identity.models import AuthSession, Membership, MembershipStatus, Tenant, User
from conformly.main import app


class FakeTokenVerifier(TokenVerifier):
    def __init__(self, claims: TokenClaims) -> None:
        self._claims = claims

    def verify(self, token: str) -> TokenClaims:
        return self._claims


def seed_user(
    session: Session, is_admin: bool = False, role: Role = Role.OWNER
) -> tuple[User, Tenant, TokenClaims]:
    session_id = f"session-{uuid4().hex[:8]}"
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject=str(uuid4()),
        email=f"user-{uuid4().hex[:8]}@example.test",
        display_name="API Test User",
        is_platform_admin=is_admin,
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
def client(session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: session
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


def test_canonical_framework_api_lifecycle(session: Session, client: TestClient) -> None:
    admin, _, admin_claims = seed_user(session, is_admin=True)
    approver, _, approver_claims = seed_user(session, is_admin=True)
    user, _, user_claims = seed_user(session, is_admin=False)

    # 1. Non-admin attempting to create canonical framework receives 403
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(user_claims)
    res = client.post(
        "/v1/frameworks",
        headers={"Authorization": "Bearer test"},
        json={"name": "ISO 27001", "slug": "iso-27001"},
    )
    assert res.status_code == 403

    # 2. Platform admin creates framework
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(admin_claims)
    res = client.post(
        "/v1/frameworks",
        headers={"Authorization": "Bearer test"},
        json={"name": "ISO/IEC 27001", "slug": "iso-27001", "description": "ISMS Standard"},
    )
    assert res.status_code == 201
    fw_data = res.json()
    fw_id = fw_data["id"]

    # 3. Create draft version
    res = client.post(
        f"/v1/frameworks/{fw_id}/versions",
        headers={"Authorization": "Bearer test"},
        json={"version": "2022", "release_notes": "2022 revision"},
    )
    assert res.status_code == 201
    v_data = res.json()
    v_id = v_data["id"]

    # 4. Add canonical control
    res = client.post(
        f"/v1/frameworks/{fw_id}/versions/{v_id}/controls",
        headers={"Authorization": "Bearer test"},
        json={
            "identifier": "A.5.1",
            "title": "Policies for information security",
            "description": "Security policies defined",
            "category": "Organizational",
            "guidance": "Management direction",
            "sort_order": 1,
        },
    )
    assert res.status_code == 201
    ctrl_data = res.json()
    assert ctrl_data["identifier"] == "A.5.1"

    # 5. Submit for review
    res = client.post(
        f"/v1/frameworks/{fw_id}/versions/{v_id}/submit-review",
        headers={"Authorization": "Bearer test"},
    )
    assert res.status_code == 200
    assert res.json()["release_state"] == "in_review"

    # 6. Legal review
    res = client.post(
        f"/v1/frameworks/{fw_id}/versions/{v_id}/legal-review",
        headers={"Authorization": "Bearer test"},
        json={"notes": "Legal review complete and verified against published standard."},
    )
    assert res.status_code == 200

    # 7. Creator attempting to approve their own version fails (Independent approval rule)
    res = client.post(
        f"/v1/frameworks/{fw_id}/versions/{v_id}/approve",
        headers={"Authorization": "Bearer test"},
        json={"notes": "Self approval"},
    )
    assert res.status_code == 400

    # 8. Second platform admin approves
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(approver_claims)
    res = client.post(
        f"/v1/frameworks/{fw_id}/versions/{v_id}/approve",
        headers={"Authorization": "Bearer test"},
        json={"notes": "Independent sign-off"},
    )
    assert res.status_code == 200
    assert res.json()["release_state"] == "approved"

    # 9. Release version
    res = client.post(
        f"/v1/frameworks/{fw_id}/versions/{v_id}/release",
        headers={"Authorization": "Bearer test"},
    )
    assert res.status_code == 200
    assert res.json()["release_state"] == "released"

    # 10. Normal user can now see the released version
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(user_claims)
    res = client.get("/v1/frameworks", headers={"Authorization": "Bearer test"})
    assert res.status_code == 200
    fws = res.json()
    assert len(fws) >= 1
    assert any(f["id"] == fw_id for f in fws)


def test_tenant_adoption_and_overlays_api(session: Session, client: TestClient) -> None:
    user, tenant, claims = seed_user(session, role=Role.COMPLIANCE_MANAGER)
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(claims)

    # Seed released framework directly
    admin_id = uuid4()
    fw = Framework(name="SOC 2", slug="soc-2", description="Trust Services")
    session.add(fw)
    session.flush()

    v = FrameworkVersion(
        framework_id=fw.id,
        version="2017",
        release_state=ReleaseState.RELEASED,
        created_by_user_id=admin_id,
        released_at=datetime.now(UTC),
    )
    session.add(v)
    session.flush()

    ctrl = CanonicalControl(
        framework_version_id=v.id,
        identifier="CC1.1",
        title="Ethics and Integrity",
        description="Integrity demonstrated",
        category="Control Environment",
        sort_order=1,
    )
    session.add(ctrl)
    session.commit()

    # 1. Adopt framework version
    res = client.post(
        f"/v1/tenants/{tenant.id}/frameworks/adopt",
        headers={"Authorization": "Bearer test"},
        json={"framework_version_id": str(v.id), "acknowledge_impact": True},
    )
    assert res.status_code == 201
    adopt_data = res.json()
    adopt_id = adopt_data["id"]
    assert adopt_data["status"] == "active"

    # 2. List tenant adoptions
    res = client.get(
        f"/v1/tenants/{tenant.id}/frameworks/adoptions",
        headers={"Authorization": "Bearer test"},
    )
    assert res.status_code == 200
    assert len(res.json()) == 1

    # 3. Add overlay to CC1.1
    res = client.post(
        f"/v1/tenants/{tenant.id}/frameworks/adoptions/{adopt_id}/overlays",
        headers={"Authorization": "Bearer test"},
        json={
            "canonical_control_id": str(ctrl.id),
            "applicability": "applicable",
            "justification": "Applicable to all staff",
            "internal_notes": "Employee handbook acknowledgement",
        },
    )
    assert res.status_code == 201
    overlay_data = res.json()
    assert overlay_data["applicability"] == "applicable"
    overlay_id = overlay_data["id"]

    # 4. List overlays
    res = client.get(
        f"/v1/tenants/{tenant.id}/frameworks/adoptions/{adopt_id}/overlays",
        headers={"Authorization": "Bearer test"},
    )
    assert res.status_code == 200
    assert len(res.json()) == 1

    # 5. Create custom control
    res = client.post(
        f"/v1/tenants/{tenant.id}/custom-controls",
        headers={"Authorization": "Bearer test"},
        json={
            "identifier": "CUSTOM-SEC-01",
            "title": "Hardware Security Keys",
            "description": "FIDO2 required for production access",
            "category": "Authentication",
        },
    )
    assert res.status_code == 201
    cust_data = res.json()
    cust_id = cust_data["id"]
    assert cust_data["identifier"] == "CUSTOM-SEC-01"

    # 6. Create control mapping
    res = client.post(
        f"/v1/tenants/{tenant.id}/control-mappings",
        headers={"Authorization": "Bearer test"},
        json={
            "source_type": "custom",
            "source_control_id": cust_id,
            "target_type": "canonical",
            "target_control_id": str(ctrl.id),
            "mapping_type": "satisfies",
            "rationale": "Hardware keys satisfy authentication control",
        },
    )
    assert res.status_code == 201
    mapping_data = res.json()
    mapping_id = mapping_data["id"]

    # 7. Delete mapping
    res = client.delete(
        f"/v1/tenants/{tenant.id}/control-mappings/{mapping_id}",
        headers={"Authorization": "Bearer test"},
    )
    assert res.status_code == 204

    # 8. Delete overlay
    res = client.delete(
        f"/v1/tenants/{tenant.id}/frameworks/adoptions/{adopt_id}/overlays/{overlay_id}",
        headers={"Authorization": "Bearer test"},
    )
    assert res.status_code == 204
