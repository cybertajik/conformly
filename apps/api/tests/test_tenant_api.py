import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditEvent, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.auth.session import hash_session_id
from conformly.auth.tokens import TokenClaims, TokenVerifier, get_token_verifier
from conformly.authz.roles import Role
from conformly.db.session import get_db
from conformly.identity.models import AuthSession, Membership, MembershipStatus, Tenant, User
from conformly.main import app


class FakeTokenVerifier(TokenVerifier):
    def __init__(self, claims: TokenClaims) -> None:
        self._claims = claims

    def verify(self, token: str) -> TokenClaims:
        assert token == "opaque-test-token"
        return self._claims


def seed_access(session: Session) -> tuple[User, Tenant, TokenClaims]:
    session_id = "api-test-session"
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject=str(uuid4()),
        email=f"{uuid4()}@example.test",
        display_name="API Test User",
    )
    tenant = Tenant(name="Authorized Tenant", slug=f"authorized-{uuid4()}")
    session.add_all([user, tenant])
    session.flush()
    session.add_all(
        [
            Membership(
                tenant_id=tenant.id,
                user_id=user.id,
                role=Role.AUDITOR,
                status=MembershipStatus.ACTIVE,
            ),
            AuthSession(
                user_id=user.id,
                session_id_hash=hash_session_id(session_id),
                expires_at=expires_at,
            ),
        ]
    )
    session.commit()
    claims = TokenClaims(
        issuer=user.oidc_issuer,
        subject=user.oidc_subject,
        session_id=session_id,
        expires_at=int(expires_at.timestamp()),
    )
    return user, tenant, claims


def client_for(session: Session, claims: TokenClaims) -> TestClient:
    def override_database() -> Session:
        return session

    app.dependency_overrides[get_db] = override_database
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(claims)
    return TestClient(app)


def test_secured_tenant_context_endpoint(session: Session) -> None:
    _, tenant, claims = seed_access(session)
    client = client_for(session, claims)
    try:
        response = client.get(
            f"/v1/tenants/{tenant.id}/context",
            headers={"Authorization": "Bearer opaque-test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"tenant_id": str(tenant.id), "role": "auditor"}


def test_client_selected_cross_tenant_id_is_denied(session: Session) -> None:
    _, _, claims = seed_access(session)
    other_tenant = Tenant(name="Forbidden Tenant", slug=f"forbidden-{uuid4()}")
    session.add(other_tenant)
    session.commit()
    client = client_for(session, claims)
    try:
        response = client.get(
            f"/v1/tenants/{other_tenant.id}/context",
            headers={"Authorization": "Bearer opaque-test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json() == {"detail": "tenant access denied"}


def test_revoked_application_session_is_denied(session: Session) -> None:
    _, tenant, claims = seed_access(session)
    auth_session = session.query(AuthSession).one()
    auth_session.revoked_at = datetime.now(UTC)
    session.commit()
    client = client_for(session, claims)
    try:
        response = client.get(
            f"/v1/tenants/{tenant.id}/context",
            headers={"Authorization": "Bearer opaque-test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid authentication"}


def test_missing_bearer_credentials_are_denied(session: Session) -> None:
    _, tenant, claims = seed_access(session)
    client = client_for(session, claims)
    try:
        response = client.get(f"/v1/tenants/{tenant.id}/context")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == {"detail": "authentication required"}


def test_membership_list_is_tenant_scoped(session: Session) -> None:
    user, tenant, claims = seed_access(session)
    other_user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject=str(uuid4()),
        email=f"{uuid4()}@example.test",
        display_name="Other Tenant User",
    )
    other_tenant = Tenant(name="Other Tenant", slug=f"other-{uuid4()}")
    session.add_all([other_user, other_tenant])
    session.flush()
    session.add(
        Membership(
            tenant_id=other_tenant.id,
            user_id=other_user.id,
            role=Role.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    session.commit()
    client = client_for(session, claims)
    try:
        response = client.get(
            f"/v1/tenants/{tenant.id}/memberships",
            headers={"Authorization": "Bearer opaque-test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["user_id"] == str(user.id)
    assert response.json()[0]["email"] == user.email
    assert "oidc_subject" not in response.json()[0]
    event = session.query(AuditEvent).one()
    assert event.tenant_id == tenant.id
    assert event.actor_id == user.id
    assert event.outcome is AuditOutcome.SUCCESS
    assert event.request_id == response.headers["X-Request-ID"]
    assert event.safe_metadata == {"record_count": 1}


def test_membership_list_requires_capability(session: Session) -> None:
    _, tenant, claims = seed_access(session)
    membership = session.query(Membership).one()
    membership.role = Role.VIEWER
    session.commit()
    client = client_for(session, claims)
    try:
        response = client.get(
            f"/v1/tenants/{tenant.id}/memberships",
            headers={"Authorization": "Bearer opaque-test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json() == {"detail": "capability denied"}
    event = session.query(AuditEvent).one()
    assert event.tenant_id == tenant.id
    assert event.outcome is AuditOutcome.DENIED
    assert event.safe_metadata == {}


def add_member(session: Session, tenant: Tenant, *, role: Role = Role.CONTRIBUTOR) -> Membership:
    user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject=str(uuid4()),
        email=f"{uuid4()}@example.test",
        display_name="Managed User",
    )
    session.add(user)
    session.flush()
    membership = Membership(
        tenant_id=tenant.id,
        user_id=user.id,
        role=role,
        status=MembershipStatus.ACTIVE,
    )
    session.add(membership)
    session.commit()
    return membership


def test_owner_can_change_role_with_audit_event(session: Session) -> None:
    actor, tenant, claims = seed_access(session)
    session.query(Membership).filter_by(user_id=actor.id).one().role = Role.OWNER
    target = add_member(session, tenant)
    client = client_for(session, claims)
    try:
        response = client.patch(
            f"/v1/tenants/{tenant.id}/memberships/{target.id}/role",
            headers={"Authorization": "Bearer opaque-test-token"},
            json={"role": "auditor"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["role"] == "auditor"
    session.refresh(target)
    assert target.role is Role.AUDITOR
    event = session.query(AuditEvent).one()
    assert event.action == "membership.role_change"
    assert event.outcome is AuditOutcome.SUCCESS
    assert event.safe_metadata == {
        "previous_role": "contributor",
        "new_role": "auditor",
    }


def test_role_change_cannot_target_another_tenant(session: Session) -> None:
    actor, tenant, claims = seed_access(session)
    session.query(Membership).filter_by(user_id=actor.id).one().role = Role.OWNER
    other_tenant = Tenant(name="Other Tenant", slug=f"other-role-{uuid4()}")
    session.add(other_tenant)
    session.commit()
    target = add_member(session, other_tenant)
    client = client_for(session, claims)
    try:
        response = client.patch(
            f"/v1/tenants/{tenant.id}/memberships/{target.id}/role",
            headers={"Authorization": "Bearer opaque-test-token"},
            json={"role": "auditor"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    session.refresh(target)
    assert target.role is Role.CONTRIBUTOR
    event = session.query(AuditEvent).one()
    assert event.outcome is AuditOutcome.DENIED
    assert event.safe_metadata == {"reason": "not_found_in_tenant"}


def test_viewer_cannot_change_role(session: Session) -> None:
    _, tenant, claims = seed_access(session)
    actor_membership = session.query(Membership).one()
    actor_membership.role = Role.VIEWER
    target = add_member(session, tenant)
    client = client_for(session, claims)
    try:
        response = client.patch(
            f"/v1/tenants/{tenant.id}/memberships/{target.id}/role",
            headers={"Authorization": "Bearer opaque-test-token"},
            json={"role": "auditor"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    session.refresh(target)
    assert target.role is Role.CONTRIBUTOR


def test_last_active_owner_cannot_be_demoted(session: Session) -> None:
    actor, tenant, claims = seed_access(session)
    actor_membership = session.query(Membership).one()
    actor_membership.role = Role.OWNER
    session.commit()
    client = client_for(session, claims)
    try:
        response = client.patch(
            f"/v1/tenants/{tenant.id}/memberships/{actor_membership.id}/role",
            headers={"Authorization": "Bearer opaque-test-token"},
            json={"role": "administrator"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {"detail": "tenant must retain an active owner"}
    session.refresh(actor_membership)
    assert actor_membership.role is Role.OWNER
    event = session.query(AuditEvent).one()
    assert event.outcome is AuditOutcome.FAILURE
    assert event.safe_metadata == {"reason": "last_active_owner"}


def test_role_update_rejects_mass_assigned_fields(session: Session) -> None:
    actor, tenant, claims = seed_access(session)
    session.query(Membership).filter_by(user_id=actor.id).one().role = Role.OWNER
    target = add_member(session, tenant)
    client = client_for(session, claims)
    try:
        response = client.patch(
            f"/v1/tenants/{tenant.id}/memberships/{target.id}/role",
            headers={"Authorization": "Bearer opaque-test-token"},
            json={
                "role": "auditor",
                "tenant_id": str(uuid4()),
                "user_id": str(actor.id),
                "status": "active",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    session.refresh(target)
    assert target.role is Role.CONTRIBUTOR


def test_owner_can_revoke_membership_with_audit_event(session: Session) -> None:
    actor, tenant, claims = seed_access(session)
    session.query(Membership).filter_by(user_id=actor.id).one().role = Role.OWNER
    target = add_member(session, tenant)
    client = client_for(session, claims)
    try:
        response = client.delete(
            f"/v1/tenants/{tenant.id}/memberships/{target.id}",
            headers={"Authorization": "Bearer opaque-test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "revoked"
    session.refresh(target)
    assert target.status is MembershipStatus.REVOKED
    event = session.query(AuditEvent).one()
    assert event.action == "membership.revoke"
    assert event.outcome is AuditOutcome.SUCCESS
    assert event.safe_metadata == {"previous_status": "active"}


def test_membership_revocation_is_idempotent(session: Session) -> None:
    actor, tenant, claims = seed_access(session)
    session.query(Membership).filter_by(user_id=actor.id).one().role = Role.OWNER
    target = add_member(session, tenant)
    target.status = MembershipStatus.REVOKED
    session.commit()
    client = client_for(session, claims)
    try:
        response = client.delete(
            f"/v1/tenants/{tenant.id}/memberships/{target.id}",
            headers={"Authorization": "Bearer opaque-test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    event = session.query(AuditEvent).one()
    assert event.outcome is AuditOutcome.SUCCESS
    assert event.safe_metadata == {"already_revoked": True}


def test_membership_revocation_cannot_target_another_tenant(session: Session) -> None:
    actor, tenant, claims = seed_access(session)
    session.query(Membership).filter_by(user_id=actor.id).one().role = Role.OWNER
    other_tenant = Tenant(name="Other Tenant", slug=f"other-revoke-{uuid4()}")
    session.add(other_tenant)
    session.commit()
    target = add_member(session, other_tenant)
    client = client_for(session, claims)
    try:
        response = client.delete(
            f"/v1/tenants/{tenant.id}/memberships/{target.id}",
            headers={"Authorization": "Bearer opaque-test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    session.refresh(target)
    assert target.status is MembershipStatus.ACTIVE
    event = session.query(AuditEvent).one()
    assert event.outcome is AuditOutcome.DENIED
    assert event.safe_metadata == {"reason": "not_found_in_tenant"}


def test_viewer_cannot_revoke_membership(session: Session) -> None:
    actor, tenant, claims = seed_access(session)
    session.query(Membership).filter_by(user_id=actor.id).one().role = Role.VIEWER
    target = add_member(session, tenant)
    client = client_for(session, claims)
    try:
        response = client.delete(
            f"/v1/tenants/{tenant.id}/memberships/{target.id}",
            headers={"Authorization": "Bearer opaque-test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    session.refresh(target)
    assert target.status is MembershipStatus.ACTIVE


def test_last_active_owner_cannot_be_revoked(session: Session) -> None:
    actor, tenant, claims = seed_access(session)
    actor_membership = session.query(Membership).one()
    actor_membership.role = Role.OWNER
    session.commit()
    client = client_for(session, claims)
    try:
        response = client.delete(
            f"/v1/tenants/{tenant.id}/memberships/{actor_membership.id}",
            headers={"Authorization": "Bearer opaque-test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    session.refresh(actor_membership)
    assert actor_membership.status is MembershipStatus.ACTIVE
    event = session.query(AuditEvent).one()
    assert event.outcome is AuditOutcome.FAILURE
    assert event.safe_metadata == {"reason": "last_active_owner"}


def test_auditor_can_search_only_selected_tenant_audit_events(session: Session) -> None:
    user, tenant, claims = seed_access(session)
    record_audit_event(
        session,
        tenant_id=tenant.id,
        actor_type=AuditActorType.USER,
        actor_id=user.id,
        action="membership.test_event",
        resource_type="membership",
        resource_id=None,
        request_id="seed-event",
        outcome=AuditOutcome.SUCCESS,
    )
    record_audit_event(
        session,
        tenant_id=uuid4(),
        actor_type=AuditActorType.SYSTEM,
        actor_id=None,
        action="other_tenant.event",
        resource_type="membership",
        resource_id=None,
        request_id="other-event",
        outcome=AuditOutcome.SUCCESS,
    )
    session.commit()
    client = client_for(session, claims)
    try:
        response = client.get(
            f"/v1/tenants/{tenant.id}/audit-events",
            headers={"Authorization": "Bearer opaque-test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert [item["action"] for item in response.json()["records"]] == ["membership.test_event"]


def test_compliance_manager_can_download_tenant_audit_jsonl(session: Session) -> None:
    user, tenant, claims = seed_access(session)
    session.query(Membership).one().role = Role.COMPLIANCE_MANAGER
    record_audit_event(
        session,
        tenant_id=tenant.id,
        actor_type=AuditActorType.USER,
        actor_id=user.id,
        action="audit.export_fixture",
        resource_type="audit_event",
        resource_id=None,
        request_id="export-fixture",
        outcome=AuditOutcome.SUCCESS,
    )
    session.commit()
    client = client_for(session, claims)
    try:
        response = client.get(
            f"/v1/tenants/{tenant.id}/audit-events/export",
            headers={"Authorization": "Bearer opaque-test-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    records = [json.loads(line) for line in response.text.splitlines()]
    assert [record["action"] for record in records] == ["audit.export_fixture"]
