from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conformly.auth.session import hash_session_id
from conformly.auth.tokens import TokenClaims, TokenVerifier, get_token_verifier
from conformly.authz.roles import Role
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
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
    session: Session, is_admin: bool = False, role: Role = Role.COMPLIANCE_MANAGER
) -> tuple[User, Tenant, TokenClaims]:
    session_id = f"session-{uuid4().hex[:8]}"
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    user = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject=str(uuid4()),
        email=f"user-{uuid4().hex[:8]}@example.test",
        display_name="API Compliance User",
        is_platform_admin=is_admin,
    )
    tenant = Tenant(name="Compliance Tenant", slug=f"tenant-{uuid4().hex[:8]}")
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
def client(session: Session, test_codec: EncryptedFieldCodec) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_encrypted_field_codec] = lambda: test_codec
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_evidence_api_lifecycle(client: TestClient, session: Session) -> None:
    user, tenant, claims = seed_user(session, role=Role.COMPLIANCE_MANAGER)
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(claims)
    headers = {"Authorization": "Bearer fake-token"}

    # 1. Create Evidence
    create_payload = {
        "title": "AWS IAM Credentials Report",
        "description": "Quarterly root and IAM credential report",
        "classification": "Confidential",
        "owner_user_id": str(user.id),
        "restricted_notes": "Root account has active MFA hardware key 12345",
    }
    res = client.post(
        f"/v1/tenants/{tenant.id}/compliance/evidence",
        json=create_payload,
        headers=headers,
    )
    assert res.status_code == 201
    evidence_data = res.json()
    evidence_id = evidence_data["id"]
    assert evidence_data["title"] == "AWS IAM Credentials Report"
    assert evidence_data["version"] == 1
    assert evidence_data["restricted_notes"] == "Root account has active MFA hardware key 12345"

    # 2. Get Evidence
    get_res = client.get(
        f"/v1/tenants/{tenant.id}/compliance/evidence/{evidence_id}",
        headers=headers,
    )
    assert get_res.status_code == 200
    assert get_res.json()["restricted_notes"] == "Root account has active MFA hardware key 12345"

    # 3. Update Evidence with matching version
    update_res = client.patch(
        f"/v1/tenants/{tenant.id}/compliance/evidence/{evidence_id}",
        json={"expected_version": 1, "title": "AWS IAM Credentials Report (Updated)"},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["version"] == 2
    assert update_res.json()["title"] == "AWS IAM Credentials Report (Updated)"

    # 4. Update with stale version returns 409 Conflict
    conflict_res = client.patch(
        f"/v1/tenants/{tenant.id}/compliance/evidence/{evidence_id}",
        json={"expected_version": 1, "title": "Stale Update"},
        headers=headers,
    )
    assert conflict_res.status_code == 409

    # 5. Transition Evidence Status
    trans_res = client.post(
        f"/v1/tenants/{tenant.id}/compliance/evidence/{evidence_id}/transition",
        json={"expected_version": 2, "target_status": "submitted", "reason": "Ready for auditor"},
        headers=headers,
    )
    assert trans_res.status_code == 200
    assert trans_res.json()["status"] == "submitted"
    assert trans_res.json()["version"] == 3


def test_evidence_tenant_isolation_api(client: TestClient, session: Session) -> None:
    user_a, tenant_a, claims_a = seed_user(session, role=Role.COMPLIANCE_MANAGER)
    _, tenant_b, claims_b = seed_user(session, role=Role.COMPLIANCE_MANAGER)

    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(claims_a)
    headers_a = {"Authorization": "Bearer token-a"}

    # Tenant A creates evidence
    create_res = client.post(
        f"/v1/tenants/{tenant_a.id}/compliance/evidence",
        json={
            "title": "Tenant A Secret Evidence",
            "description": "Confidential A",
            "owner_user_id": str(user_a.id),
        },
        headers=headers_a,
    )
    assert create_res.status_code == 201
    evidence_id = create_res.json()["id"]

    # Tenant B tries to access Tenant A's evidence
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(claims_b)
    headers_b = {"Authorization": "Bearer token-b"}

    res_cross = client.get(
        f"/v1/tenants/{tenant_b.id}/compliance/evidence/{evidence_id}",
        headers=headers_b,
    )
    assert res_cross.status_code == 404

    # Tenant B tries to access via Tenant A's URL (forbidden: user B has no membership in tenant A)
    res_forbidden = client.get(
        f"/v1/tenants/{tenant_a.id}/compliance/evidence/{evidence_id}",
        headers=headers_b,
    )
    assert res_forbidden.status_code in (401, 403)


def test_policy_approval_workflow_api(client: TestClient, session: Session) -> None:
    author_user, tenant, author_claims = seed_user(session, role=Role.COMPLIANCE_MANAGER)
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(author_claims)
    author_headers = {"Authorization": "Bearer author-token"}

    # 1. Author creates policy
    create_res = client.post(
        f"/v1/tenants/{tenant.id}/compliance/policies",
        json={
            "title": "Data Retention Policy",
            "description": "Rules for retaining and deleting customer data",
            "version_string": "1.0",
            "review_cycle_days": 365,
            "content": "Active customer data preserved; 30d export/90d deletion.",
        },
        headers=author_headers,
    )
    assert create_res.status_code == 201
    policy_id = create_res.json()["id"]
    assert create_res.json()["status"] == "draft"

    # 2. Submit for review
    submit_res = client.post(
        f"/v1/tenants/{tenant.id}/compliance/policies/{policy_id}/submit-review",
        json={"expected_version": 1},
        headers=author_headers,
    )
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == "in_review"

    # 3. Author cannot approve own policy (independent approval rule)
    self_approve_res = client.post(
        f"/v1/tenants/{tenant.id}/compliance/policies/{policy_id}/approve",
        json={"expected_version": 2},
        headers=author_headers,
    )
    assert self_approve_res.status_code == 400
    assert "2-person approval required" in self_approve_res.json()["detail"]

    # 4. Another user (Administrator) approves policy
    approver = User(
        oidc_issuer="https://identity.example.test",
        oidc_subject="approver-sub",
        email="admin-approver@example.test",
        display_name="Admin Approver",
    )
    session.add(approver)
    session.flush()

    approver_session_id = "session-approver"
    session.add_all(
        [
            Membership(
                tenant_id=tenant.id,
                user_id=approver.id,
                role=Role.ADMINISTRATOR,
                status=MembershipStatus.ACTIVE,
            ),
            AuthSession(
                user_id=approver.id,
                session_id_hash=hash_session_id(approver_session_id),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            ),
        ]
    )
    session.commit()

    approver_claims = TokenClaims(
        issuer=approver.oidc_issuer,
        subject=approver.oidc_subject,
        session_id=approver_session_id,
        expires_at=int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        email=approver.email,
        email_verified=True,
        display_name=approver.display_name,
    )
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(approver_claims)
    approver_headers = {"Authorization": "Bearer approver-token"}

    approve_res = client.post(
        f"/v1/tenants/{tenant.id}/compliance/policies/{policy_id}/approve",
        json={"expected_version": 2},
        headers=approver_headers,
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"
    assert approve_res.json()["approved_by_user_id"] == str(approver.id)

    # 5. Publish policy
    publish_res = client.post(
        f"/v1/tenants/{tenant.id}/compliance/policies/{policy_id}/publish",
        json={"expected_version": 3},
        headers=approver_headers,
    )
    assert publish_res.status_code == 200
    assert publish_res.json()["status"] == "published"
    assert publish_res.json()["next_review_due"] is not None


def test_tasks_and_findings_api(client: TestClient, session: Session) -> None:
    user, tenant, claims = seed_user(session, role=Role.COMPLIANCE_MANAGER)
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(claims)
    headers = {"Authorization": "Bearer fake-token"}

    # Tasks
    due = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    create_task_res = client.post(
        f"/v1/tenants/{tenant.id}/compliance/tasks",
        json={
            "title": "Quarterly User Access Review",
            "description": "Audit inactive accounts in production VPC",
            "due_date": due,
            "priority": "high",
            "assignee_user_id": str(user.id),
        },
        headers=headers,
    )
    assert create_task_res.status_code == 201
    task_id = create_task_res.json()["id"]

    complete_res = client.post(
        f"/v1/tenants/{tenant.id}/compliance/tasks/{task_id}/complete",
        json={"expected_version": 1},
        headers=headers,
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["status"] == "completed"

    # Findings
    create_finding_res = client.post(
        f"/v1/tenants/{tenant.id}/compliance/findings",
        json={
            "title": "TLS 1.0 Enabled on Ingress",
            "description": "Vulnerability scanner identified TLS 1.0 support",
            "severity": "medium",
            "remediation_plan": "Update ingress TLS profile to require TLS 1.2 minimum",
        },
        headers=headers,
    )
    assert create_finding_res.status_code == 201
    finding_id = create_finding_res.json()["id"]

    remediation_res = client.post(
        f"/v1/tenants/{tenant.id}/compliance/findings/{finding_id}/remediation",
        json={
            "expected_version": 1,
            "remediation_status": "resolved",
            "remediation_summary": "Reconfigured Ingress controller and re-scanned",
        },
        headers=headers,
    )
    assert remediation_res.status_code == 200
    assert remediation_res.json()["remediation_status"] == "resolved"


def test_control_posture_and_preferences_api(client: TestClient, session: Session) -> None:
    user, tenant, claims = seed_user(session, role=Role.COMPLIANCE_MANAGER)
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(claims)
    headers = {"Authorization": "Bearer fake-token"}

    # Canonical control setup
    fw = Framework(name="SOC 2", slug="soc-2")
    session.add(fw)
    session.flush()

    fw_v = FrameworkVersion(
        framework_id=fw.id,
        version="2017",
        release_state=ReleaseState.RELEASED,
        created_by_user_id=user.id,
    )
    session.add(fw_v)
    session.flush()

    ctrl = CanonicalControl(
        framework_version_id=fw_v.id,
        identifier="CC6.1",
        title="Logical Access Controls",
        description="Access controls to prevent unauthorized access",
        category="Security",
        sort_order=1,
    )
    session.add(ctrl)
    session.commit()

    # Upsert control status
    upsert_res = client.put(
        f"/v1/tenants/{tenant.id}/compliance/control-statuses/canonical/{ctrl.id}",
        json={
            "status": "implemented",
            "notes": "Okta SSO with enforced WebAuthn",
            "assigned_owner_user_id": str(user.id),
        },
        headers=headers,
    )
    assert upsert_res.status_code == 200
    assert upsert_res.json()["status"] == "implemented"

    # Get matrix
    matrix_res = client.get(
        f"/v1/tenants/{tenant.id}/compliance/control-statuses",
        headers=headers,
    )
    assert matrix_res.status_code == 200
    assert len(matrix_res.json()) == 1

    # Preferences
    pref_res = client.get(f"/v1/tenants/{tenant.id}/compliance/preferences", headers=headers)
    assert pref_res.status_code == 200
    assert pref_res.json()["digest_frequency"] == "immediate"

    put_pref_res = client.put(
        f"/v1/tenants/{tenant.id}/compliance/preferences",
        json={"digest_frequency": "daily", "email_enabled": True},
        headers=headers,
    )
    assert put_pref_res.status_code == 200
    assert put_pref_res.json()["digest_frequency"] == "daily"


def test_jobs_trigger_api(client: TestClient, session: Session) -> None:
    _, tenant, claims = seed_user(session, role=Role.COMPLIANCE_MANAGER)
    app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(claims)
    headers = {"Authorization": "Bearer fake-token"}

    job_res = client.post(
        f"/v1/tenants/{tenant.id}/compliance/jobs/run-expirations",
        headers=headers,
    )
    assert job_res.status_code == 200
    data = job_res.json()
    assert "expired_evidence" in data
    assert "overdue_tasks" in data
    assert "policy_alerts" in data
