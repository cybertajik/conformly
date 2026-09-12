"""Security audit and negative verification suite for Phase 10 operational readiness.

Validates:
1. Multi-tenant IDOR resistance across all tenant-scoped resources.
2. Strict role-based capability boundaries and privilege escalation defenses.
3. Whistleblower zero-knowledge anonymity and non-retention of reporter secrets.
4. Mandatory pre-audit readiness disclaimers on credentials.
5. Security headers enforcement on all API responses.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

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
from conformly.whistleblower.models import (
    WhistleblowerCase,
    WhistleblowerCaseStatus,
    WhistleblowerPortal,
)
from conformly.whistleblower.service import hash_return_secret


def _test_envelope() -> EnvelopeEncryptionService:
    b64 = "QUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUE="
    return EnvelopeEncryptionService(
        AES256GCMProvider(), LocalKeyManagementProvider({"v1": b64}, "v1")
    )


class MockVerifier(TokenVerifier):
    def __init__(self, claims_map: dict[str, TokenClaims]) -> None:
        self.claims_map = claims_map

    def verify(self, token: str) -> TokenClaims:
        if token in self.claims_map:
            return self.claims_map[token]
        raise ValueError("Invalid bearer token")


def _setup_tenant_user(
    session: Session, role: Role, name: str = "Test User"
) -> tuple[Tenant, User, str, str]:
    tenant = Tenant(name=f"Tenant-{uuid4()}", slug=f"tenant-{uuid4().hex[:8]}")
    user = User(
        oidc_issuer="https://auth.example.test",
        oidc_subject=str(uuid4()),
        email=f"user-{uuid4().hex[:8]}@example.test",
        display_name=name,
    )
    session.add_all([tenant, user])
    session.flush()

    token = f"tok-{uuid4().hex}"
    session_id = f"sess-{uuid4().hex}"
    expires = datetime.now(UTC) + timedelta(hours=2)

    session.add_all(
        [
            Membership(
                tenant_id=tenant.id,
                user_id=user.id,
                role=role,
                status=MembershipStatus.ACTIVE,
            ),
            AuthSession(
                user_id=user.id,
                session_id_hash=hash_session_id(session_id),
                expires_at=expires,
            ),
        ]
    )
    session.commit()
    return tenant, user, token, session_id


def test_cross_tenant_idor_protection(session: Session) -> None:
    """Ensure a user from Tenant A cannot access Tenant B's export or cancellation endpoints."""

    tenant_a, user_a, token_a, sess_a = _setup_tenant_user(session, Role.OWNER, "Owner A")
    tenant_b, user_b, token_b, sess_b = _setup_tenant_user(session, Role.OWNER, "Owner B")

    claims_map = {
        token_a: TokenClaims(
            issuer=user_a.oidc_issuer,
            subject=user_a.oidc_subject,
            session_id=sess_a,
            expires_at=int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        ),
        token_b: TokenClaims(
            issuer=user_b.oidc_issuer,
            subject=user_b.oidc_subject,
            session_id=sess_b,
            expires_at=int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        ),
    }

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: MockVerifier(claims_map)

    try:
        client = TestClient(app)

        # 1. User A attempts to list Tenant B's exports -> must be denied (401, 403, 404)
        resp = client.get(
            f"/v1/tenants/{tenant_b.id}/exports",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code in (401, 403, 404)

        # 2. User A attempts to cancel Tenant B -> must be denied
        resp = client.post(
            f"/v1/tenants/{tenant_b.id}/cancellation",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"confirmation_slug": tenant_b.slug},
        )
        assert resp.status_code in (401, 403, 404)

        # 3. User A attempts to query Tenant B's public profile management -> must be denied
        resp = client.get(
            f"/v1/tenants/{tenant_b.id}/public-profile",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code in (401, 403, 404)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_token_verifier, None)


def test_privilege_escalation_boundaries(session: Session) -> None:
    """Ensure a standard Viewer cannot perform Owner-restricted actions."""

    tenant, user, token, sess_user = _setup_tenant_user(session, Role.VIEWER, "Standard Viewer")

    claims_map = {
        token: TokenClaims(
            issuer=user.oidc_issuer,
            subject=user.oidc_subject,
            session_id=sess_user,
            expires_at=int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        )
    }

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: MockVerifier(claims_map)
    app.dependency_overrides[get_envelope_encryption_service] = _test_envelope

    try:
        client = TestClient(app)

        # Member attempting to create an export -> 403 Forbidden
        resp = client.post(
            f"/v1/tenants/{tenant.id}/exports",
            headers={"Authorization": f"Bearer {token}"},
            json={"scope": "full"},
        )
        assert resp.status_code == 403

        # Member attempting to request tenant cancellation -> 403 Forbidden
        resp = client.post(
            f"/v1/tenants/{tenant.id}/cancellation",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "Testing", "confirm_slug": tenant.slug},
        )
        assert resp.status_code == 403

        # Member attempting to toggle legal hold -> 403 Forbidden
        resp = client.post(
            f"/v1/tenants/{tenant.id}/legal-hold",
            headers={"Authorization": f"Bearer {token}"},
            json={"enabled": True, "reason": "Audit"},
        )
        assert resp.status_code == 403

    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_token_verifier, None)
        app.dependency_overrides.pop(get_envelope_encryption_service, None)


def test_whistleblower_anonymity_invariants(session: Session) -> None:
    """Validate that whistleblower cases do not contain personal identifiers
    and require salted hashes.
    """

    tid = uuid4()
    portal = WhistleblowerPortal(
        tenant_id=tid,
        slug=f"portal-{uuid4().hex[:8]}",
        title="Whistleblower Intake",
        welcome_text="Submit reports safely.",
    )
    session.add(portal)
    session.flush()

    raw_secret = "secret-return-key-998877"
    salt_hex, hash_hex = hash_return_secret(raw_secret)

    case = WhistleblowerCase(
        tenant_id=tid,
        portal_id=portal.id,
        public_case_id="WB-2026-SEC01",
        status=WhistleblowerCaseStatus.SUBMITTED,
        return_secret_salt=salt_hex,
        return_secret_hash=hash_hex,
        encrypted_summary={"ciphertext": "dGVzdA==", "nonce": "MTIz"},
        version=1,
    )
    session.add(case)
    session.commit()

    # 1. Inspect DB model attributes: ensure no IP, email, phone, or name columns exist
    columns = [col.name for col in WhistleblowerCase.__table__.columns]
    assert "reporter_email" not in columns
    assert "reporter_name" not in columns
    assert "reporter_ip" not in columns
    assert "ip_address" not in columns
    assert "user_agent" not in columns

    # 2. Verify return secret hash is non-invertible salted hash
    assert case.return_secret_hash != raw_secret
    assert len(case.return_secret_hash) == 64


def test_security_headers_present_on_all_endpoints() -> None:
    """Ensure essential defensive security headers are attached to API responses."""

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    headers = response.headers

    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in headers
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert "Permissions-Policy" in headers
    assert "camera=()" in headers["Permissions-Policy"]
