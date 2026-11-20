"""Tests for LMS access control, role admission, and entitlement enforcement."""

from datetime import UTC, datetime, timedelta
from typing import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conformly.auth.dependencies import get_current_principal, get_tenant_context
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.db.session import get_db
from conformly.entitlements.models import TenantEntitlement
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User
from conformly.main import app


def make_test_codec() -> EncryptedFieldCodec:
    import base64

    b64_key = base64.b64encode(b"\x07" * 32).decode("ascii")
    kms = LocalKeyManagementProvider({"v1": b64_key}, "v1")
    envelope = EnvelopeEncryptionService(AES256GCMProvider(), kms)
    return EncryptedFieldCodec(envelope)


def create_tenant_user(
    session: Session,
    role: Role = Role.COMPLIANCE_MANAGER,
    mfa: bool = True,
    membership_status: MembershipStatus = MembershipStatus.ACTIVE,
    tenant_status: TenantStatus = TenantStatus.ACTIVE,
    legal_entity_id: UUID | None = None,
    business_unit_id: UUID | None = None,
    is_workforce: bool = False,
    is_external_advisor: bool = False,
) -> tuple[User, Tenant, Principal, TenantContext]:
    tenant = Tenant(
        name="LMS Access Tenant",
        slug=f"lms-acc-{uuid4().hex[:8]}",
        status=tenant_status,
    )
    user = User(
        oidc_issuer="https://identity.conformly.de",
        oidc_subject=str(uuid4()),
        email=f"user-{uuid4().hex[:8]}@example.com",
        display_name="Test User",
    )
    session.add_all([tenant, user])
    session.flush()

    membership = Membership(
        tenant_id=tenant.id,
        user_id=user.id,
        role=role,
        status=membership_status,
    )
    session.add(membership)

    # Entitlement with 'lms' module enabled
    entitlement = TenantEntitlement(
        tenant_id=tenant.id,
        plan_code="tier_a",
        enabled_modules=["frameworks", "evidence", "tasks", "lms"],
        effective_from=datetime.now(UTC) - timedelta(days=1),
        effective_until=datetime.now(UTC) + timedelta(days=365),
    )
    session.add(entitlement)
    session.commit()

    principal = Principal(user_id=user.id, mfa_verified=mfa)
    context = TenantContext(
        tenant_id=tenant.id,
        user_id=user.id,
        role=role,
        legal_entity_id=legal_entity_id,
        business_unit_id=business_unit_id,
        is_workforce=is_workforce,
        is_external_advisor=is_external_advisor,
    )
    return user, tenant, principal, context


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    test_codec = make_test_codec()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_encrypted_field_codec] = lambda: test_codec
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_lms_role_admission(session: Session, client: TestClient) -> None:
    # 1. OWNER is admitted
    _, tenant_owner, princ_owner, ctx_owner = create_tenant_user(session, role=Role.OWNER)
    app.dependency_overrides[get_current_principal] = lambda: princ_owner
    app.dependency_overrides[get_tenant_context] = lambda: ctx_owner

    resp = client.get(f"/v1/tenants/{tenant_owner.id}/lms/courses")
    assert resp.status_code == 200

    # 2. COMPLIANCE_MANAGER is admitted
    _, tenant_cm, princ_cm, ctx_cm = create_tenant_user(session, role=Role.COMPLIANCE_MANAGER)
    app.dependency_overrides[get_current_principal] = lambda: princ_cm
    app.dependency_overrides[get_tenant_context] = lambda: ctx_cm

    resp = client.get(f"/v1/tenants/{tenant_cm.id}/lms/courses")
    assert resp.status_code == 200

    # 3. ADMINISTRATOR is denied (infrastructure role)
    _, tenant_admin, princ_admin, ctx_admin = create_tenant_user(session, role=Role.ADMINISTRATOR)
    app.dependency_overrides[get_current_principal] = lambda: princ_admin
    app.dependency_overrides[get_tenant_context] = lambda: ctx_admin

    resp = client.get(f"/v1/tenants/{tenant_admin.id}/lms/courses")
    assert resp.status_code == 403

    # 4. EMPLOYEE is denied
    _, tenant_emp, princ_emp, ctx_emp = create_tenant_user(session, role=Role.EMPLOYEE)
    app.dependency_overrides[get_current_principal] = lambda: princ_emp
    app.dependency_overrides[get_tenant_context] = lambda: ctx_emp

    resp = client.get(f"/v1/tenants/{tenant_emp.id}/lms/courses")
    assert resp.status_code == 403

    # 5. VIEWER is denied
    _, tenant_view, princ_view, ctx_view = create_tenant_user(session, role=Role.VIEWER)
    app.dependency_overrides[get_current_principal] = lambda: princ_view
    app.dependency_overrides[get_tenant_context] = lambda: ctx_view

    resp = client.get(f"/v1/tenants/{tenant_view.id}/lms/courses")
    assert resp.status_code == 403


def test_lms_entitlement_gating(session: Session, client: TestClient) -> None:
    _, tenant, principal, context = create_tenant_user(session, role=Role.COMPLIANCE_MANAGER)
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_tenant_context] = lambda: context

    # Disable lms module
    entitlement = session.query(TenantEntitlement).filter_by(tenant_id=tenant.id).first()
    assert entitlement is not None
    entitlement.enabled_modules = ["frameworks", "evidence"]
    session.commit()

    resp = client.get(f"/v1/tenants/{tenant.id}/lms/courses")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "LMS module is not enabled for this tenant"

    # Expired entitlement
    entitlement.enabled_modules = ["lms"]
    entitlement.effective_until = datetime.now(UTC) - timedelta(days=1)
    session.commit()

    resp = client.get(f"/v1/tenants/{tenant.id}/lms/courses")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "LMS module is not enabled for this tenant"


def test_lms_mfa_and_membership_checks(session: Session, client: TestClient) -> None:
    # Unverified MFA
    _, tenant, principal, context = create_tenant_user(session, role=Role.COMPLIANCE_MANAGER, mfa=False)
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_tenant_context] = lambda: context

    resp = client.get(f"/v1/tenants/{tenant.id}/lms/courses")
    assert resp.status_code == 403
    assert "MFA verification required" in resp.json()["detail"]

    # Inactive membership
    _, tenant2, principal2, context2 = create_tenant_user(
        session, role=Role.COMPLIANCE_MANAGER, mfa=True, membership_status=MembershipStatus.SUSPENDED
    )
    app.dependency_overrides[get_current_principal] = lambda: principal2
    app.dependency_overrides[get_tenant_context] = lambda: context2

    resp = client.get(f"/v1/tenants/{tenant2.id}/lms/courses")
    assert resp.status_code == 403
    assert "Active tenant membership required" in resp.json()["detail"]


def test_lms_scope_boundaries(session: Session, client: TestClient) -> None:
    # Sub-entity scope denied
    _, tenant, principal, context = create_tenant_user(
        session, role=Role.COMPLIANCE_MANAGER, legal_entity_id=uuid4()
    )
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_tenant_context] = lambda: context

    resp = client.get(f"/v1/tenants/{tenant.id}/lms/courses")
    assert resp.status_code == 403
    assert "Whole-tenant scope required" in resp.json()["detail"]

    # Workforce access denied
    _, tenant_wf, princ_wf, ctx_wf = create_tenant_user(
        session, role=Role.COMPLIANCE_MANAGER, is_workforce=True
    )
    app.dependency_overrides[get_current_principal] = lambda: princ_wf
    app.dependency_overrides[get_tenant_context] = lambda: ctx_wf

    resp = client.get(f"/v1/tenants/{tenant_wf.id}/lms/courses")
    assert resp.status_code == 403
    assert "Workforce access denied" in resp.json()["detail"]
