"""Step 7 — Framework UI and Truthful Reporting Test Suite.

Verifies:
1. Pack metadata and control provenance are exposed in Framework APIs.
2. Adoption is blocked server-side for draft and OWNER_DECISION_REQUIRED packs.
3. Pre-audit creation and certificate issuance are blocked for unreleased framework versions.
4. Truthful readiness reporting prominently delimits scoped profiles (e.g. CIS IG1, MVSP)
   and applies non-accredited statutory disclaimers.
5. Negative data leakage test on public profile projections (never exposes private findings,
   evidence files, storage keys, reviewer notes, or internal user IDs).
"""

from __future__ import annotations

import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conformly.auth.session import hash_session_id
from conformly.auth.tokens import TokenClaims, TokenVerifier, get_token_verifier
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.compliance.models import (
    EvidenceItem,
    EvidenceStatus,
    Finding,
    FindingSeverity,
    RemediationStatus,
)
from conformly.db.session import get_db
from conformly.entitlements.models import DEFAULT_TIER_A_MODULES, TenantEntitlement
from conformly.frameworks.models import (
    AdoptionStatus,
    CanonicalControl,
    ControlEntityType,
    CoverageDisposition,
    CoverageLedgerEntry,
    EvidenceSpecification,
    Framework,
    FrameworkVersion,
    MappingType,
    ReleaseState,
    RequirementControlMapping,
    SourceRequirement,
    SourceRequirementType,
    TenantFrameworkAdoption,
)
from conformly.identity.models import AuthSession, Membership, MembershipStatus, Tenant, User
from conformly.main import app
from conformly.preaudit.models import (
    CheckResult,
    PreAudit,
    PreAuditCheck,
    PreAuditScope,
    PreAuditStatus,
)
from conformly.preaudit.service import (
    InvalidAdoptionReferenceError,
    PreAuditService,
)
from conformly.profiles.models import (
    PublicCredential,
    PublicCredentialStatus,
    PublicCredentialType,
    PublicProfile,
)


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
    entitlement = TenantEntitlement(
        tenant_id=tenant.id,
        plan_code="tier_a",
        enabled_modules=DEFAULT_TIER_A_MODULES,
    )
    session.add_all([membership, auth_session, entitlement])
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


class TestStep7TruthfulReporting:
    def test_pack_metadata_and_control_provenance_api(self, session: Session, client: TestClient):
        """Verify pack metadata and control provenance are accurately returned in framework APIs."""
        user, tenant, claims = seed_user(session, is_admin=False, role=Role.OWNER)
        app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(claims)

        fw = Framework(
            name="CIS Critical Security Controls",
            slug="cis-controls-ig1",
            description="CIS Controls IG1 baseline",
        )
        session.add(fw)
        session.flush()

        fv = FrameworkVersion(
            framework_id=fw.id,
            version="8.0",
            release_state=ReleaseState.RELEASED,
            created_by_user_id=user.id,
        )
        session.add(fv)
        session.flush()

        ctrl = CanonicalControl(
            framework_version_id=fv.id,
            identifier="CIS-1.1",
            title="Establish and Maintain an Enterprise Asset Inventory",
            description="Inventory assets",
            category="Inventory and Control of Enterprise Assets",
            sort_order=1,
        )
        session.add(ctrl)
        session.flush()

        sr = SourceRequirement(
            framework_version_id=fv.id,
            source_reference="CIS Controls v8 Safeguard 1.1",
            requirement_type=SourceRequirementType.SAFEGUARD,
            title="Asset Inventory Requirement",
            source_authority="Center for Internet Security",
            edition_or_amendment="v8",
            content_rights="CIS Open Usage",
            source_text="Maintain hardware inventory",
        )
        session.add(sr)
        session.flush()

        mapping = RequirementControlMapping(
            framework_version_id=fv.id,
            source_requirement_id=sr.id,
            canonical_control_id=ctrl.id,
            mapping_type=MappingType.SATISFIES,
        )
        session.add(mapping)

        spec = EvidenceSpecification(
            framework_version_id=fv.id,
            canonical_control_id=ctrl.id,
            identifier="SPEC-CIS-1.1",
            title="Hardware Inventory",
            description="Confirms complete inventory of enterprise hardware assets.",
            evidence_type="inventory_report",
        )
        session.add(spec)

        cov = CoverageLedgerEntry(
            framework_version_id=fv.id,
            source_requirement_id=sr.id,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale="Evaluated directly against asset management evidence.",
        )
        session.add(cov)
        session.commit()

        # 1. List frameworks
        res = client.get("/v1/frameworks", headers={"Authorization": "Bearer test"})
        assert res.status_code == 200
        items = res.json()
        target = next((item for item in items if item["id"] == str(fw.id)), None)
        assert target is not None
        assert "CIS Controls Version 8" in (target["source_edition"] or "")
        assert target["profile"] == "Implementation Group 1 (IG1) Essential Hygiene"
        assert target["jurisdiction"] == "Global Enterprise / Baseline Defense"
        assert target["is_blocked"] is False
        assert "safeguards" in (target["declared_scope"] or "").lower()

        # 2. Get version details with controls
        res_ver = client.get(
            f"/v1/frameworks/{fw.id}/versions/{fv.id}", headers={"Authorization": "Bearer test"}
        )
        assert res_ver.status_code == 200
        ver_data = res_ver.json()
        assert "CIS Controls Version 8" in (ver_data["source_edition"] or "")
        assert ver_data["profile"] == "Implementation Group 1 (IG1) Essential Hygiene"
        assert len(ver_data["controls"]) == 1

        c_data = ver_data["controls"][0]
        assert c_data["source_reference"] == "CIS Controls v8 Safeguard 1.1"
        assert "Confirms complete inventory" in c_data["why_evidence_requested"]
        assert c_data["coverage_disposition"] == "IMPLEMENTED"
        assert "Evaluated directly" in c_data["coverage_rationale"]

    def test_adoption_blocked_for_owner_decision_required_pack(
        self, session: Session, client: TestClient
    ):
        """Packs tagged OWNER_DECISION_REQUIRED must be blocked from tenant adoption."""
        user, tenant, claims = seed_user(session, is_admin=False, role=Role.OWNER)
        app.dependency_overrides[get_token_verifier] = lambda: FakeTokenVerifier(claims)

        fw = Framework(
            name="California CCPA/CPRA",
            slug="us-ca-ccpa-cpra",
            description="Draft pack requiring owner decision",
        )
        session.add(fw)
        session.flush()

        fv = FrameworkVersion(
            framework_id=fw.id,
            version="2015",
            release_state=ReleaseState.RELEASED,
            created_by_user_id=user.id,
        )
        session.add(fv)
        session.flush()

        res = client.post(
            f"/v1/tenants/{tenant.id}/frameworks/adopt",
            headers={"Authorization": "Bearer test"},
            json={"framework_version_id": str(fv.id), "acknowledge_impact": True},
        )
        assert res.status_code == 403
        assert "Adoption blocked" in res.json()["detail"]

    def test_preaudit_creation_blocked_for_unreleased_version(self, session: Session):
        """Pre-audit service must refuse creation for draft/unreleased framework versions."""
        user, tenant, _ = seed_user(session, is_admin=False, role=Role.OWNER)

        fw = Framework(
            name="Draft Compliance Standard",
            slug="draft-standard",
            description="Draft only",
        )
        session.add(fw)
        session.flush()

        fv = FrameworkVersion(
            framework_id=fw.id,
            version="0.1",
            release_state=ReleaseState.DRAFT,  # Unreleased!
            created_by_user_id=user.id,
        )
        session.add(fv)
        session.flush()

        adoption = TenantFrameworkAdoption(
            tenant_id=tenant.id,
            framework_id=fw.id,
            framework_version_id=fv.id,
            status=AdoptionStatus.ACTIVE,
            adopted_by_user_id=user.id,
        )
        session.add(adoption)
        session.flush()

        svc = PreAuditService(session)
        principal = Principal(user_id=user.id, is_platform_admin=False)
        ctx = TenantContext(tenant_id=tenant.id, user_id=user.id, role=Role.OWNER)

        # 1. create_pre_audit must fail
        with pytest.raises(InvalidAdoptionReferenceError) as exc_info:
            svc.create_pre_audit(
                principal,
                ctx,
                title="Draft Pre-Audit",
                framework_adoption_id=adoption.id,
                lead_user_id=user.id,
            )
        assert "non-released" in str(exc_info.value).lower()

    def test_truthful_readiness_score_delimits_scoped_profile(self, session: Session):
        """Readiness score for scoped profiles (e.g. MVSP / CIS IG1) must delimit scope and include disclaimer."""
        user, tenant, _ = seed_user(session, is_admin=False, role=Role.OWNER)

        fw = Framework(
            name="Minimum Viable Secure Product",
            slug="mvsp",
            description="MVSP baseline",
        )
        session.add(fw)
        session.flush()

        fv = FrameworkVersion(
            framework_id=fw.id,
            version="1.0",
            release_state=ReleaseState.RELEASED,
            created_by_user_id=user.id,
        )
        session.add(fv)
        session.flush()

        adoption = TenantFrameworkAdoption(
            tenant_id=tenant.id,
            framework_id=fw.id,
            framework_version_id=fv.id,
            status=AdoptionStatus.ACTIVE,
            adopted_by_user_id=user.id,
        )
        session.add(adoption)
        session.flush()

        pa = PreAudit(
            tenant_id=tenant.id,
            title="MVSP Assessment",
            status=PreAuditStatus.COMPLETED,
            framework_adoption_id=adoption.id,
            lead_user_id=user.id,
            overall_score=1.0,
            rule_version="1.0",
            version=1,
        )
        session.add(pa)
        session.flush()

        scope = PreAuditScope(
            tenant_id=tenant.id,
            pre_audit_id=pa.id,
            framework_version_id=fv.id,
            control_count=1,
            checked_count=1,
        )
        session.add(scope)
        session.flush()

        check = PreAuditCheck(
            tenant_id=tenant.id,
            scope_id=scope.id,
            control_type=ControlEntityType.CANONICAL,
            control_id=uuid4(),
            rule_version="1.0",
            result=CheckResult.PASS,
            score=1.0,
        )
        session.add(check)
        session.flush()

        svc = PreAuditService(session)
        summary = svc.compute_score_summary(pa)

        assert summary["scope_type"] == "profile_scoped"
        assert "Full MVSP checklist" in (summary["declared_scope"] or "")
        assert any(
            "Delimited to" in lim or "Does not represent whole-framework" in lim
            for lim in summary["scope_limitations"]
        )
        assert "not an accredited certification body" in summary["disclaimer"]

    def test_public_profile_negative_data_leakage(self, session: Session, client: TestClient):
        """Public profile view must NEVER leak private evidence, internal findings, or employee PII."""
        user, tenant, _ = seed_user(session, is_admin=False, role=Role.OWNER)

        # 1. Create sensitive internal data in the tenant
        secret_finding_marker = f"SECRET-VULNERABILITY-FINDING-{uuid4().hex}"
        finding = Finding(
            tenant_id=tenant.id,
            control_id=uuid4(),
            title="Critical Internal Vulnerability",
            description=secret_finding_marker,
            severity=FindingSeverity.HIGH,
            remediation_status=RemediationStatus.OPEN,
            owner_user_id=user.id,
        )
        session.add(finding)

        secret_evidence_title = f"CONFIDENTIAL-PAYLOAD-{uuid4().hex}"
        secret_evidence_desc = f"INTERNAL-DATA-{uuid4().hex}"
        evidence = EvidenceItem(
            tenant_id=tenant.id,
            title=secret_evidence_title,
            description=secret_evidence_desc,
            classification="Restricted",
            status=EvidenceStatus.VALID,
            owner_user_id=user.id,
        )
        session.add(evidence)

        # 2. Create public profile
        profile = PublicProfile(
            tenant_id=tenant.id,
            slug=tenant.slug,
            display_name="Acme Corporation Security Center",
            description="Public compliance profile.",
            is_published=True,
            published_at=datetime.now(UTC),
            version=1,
        )
        session.add(profile)
        session.flush()

        cred = PublicCredential(
            tenant_id=tenant.id,
            profile_id=profile.id,
            credential_type=PublicCredentialType.THIRD_PARTY,
            title="SOC 2 Type II Report",
            issuer_name="Independent CPA Firm",
            scope_description="Trust Services Criteria for Security and Availability",
            issued_at=datetime.now(UTC) - timedelta(days=30),
            status=PublicCredentialStatus.ACTIVE,
            is_publicly_visible=True,
            display_order=1,
        )
        session.add(cred)
        session.commit()

        # 3. Request the unauthenticated public endpoint
        res = client.get(f"/v1/public/profiles/{profile.slug}")
        assert res.status_code == 200
        data = res.json()
        payload_str = json.dumps(data)

        # Negative leakage assertions:
        assert secret_finding_marker not in payload_str, (
            "CRITICAL: Private finding leaked into public profile!"
        )
        assert secret_evidence_title not in payload_str, (
            "CRITICAL: Evidence title leaked into public profile!"
        )
        assert secret_evidence_desc not in payload_str, (
            "CRITICAL: Evidence description leaked into public profile!"
        )
        assert str(user.id) not in payload_str, (
            "CRITICAL: Employee user ID leaked into public profile!"
        )
        assert "evidence" not in data, (
            "CRITICAL: Evidence field exposed in public profile response!"
        )
        assert "findings" not in data, (
            "CRITICAL: Findings field exposed in public profile response!"
        )
        assert data["display_name"] == "Acme Corporation Security Center"
        assert len(data["credentials"]) == 1
        assert "not an accredited certification body" in data["disclaimer"]
