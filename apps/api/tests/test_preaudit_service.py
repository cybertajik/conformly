"""Tests for pre-audit service: lifecycle, authorization, tenant isolation,
certificate issuance, scoring, and audit events."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from conformly.audit.models import AuditEvent
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.compliance.models import (
    ControlImplementationStatus,
    ControlStatusRecord,
    EvidenceControlLink,
    EvidenceItem,
    EvidenceStatus,
    FindingSeverity,
    Policy,
    PolicyControlLink,
    PolicyStatus,
    RemediationStatus,
)
from conformly.db.base import Base
from conformly.frameworks.models import (
    AdoptionStatus,
    CanonicalControl,
    ControlEntityType,
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
from conformly.preaudit.models import (
    CertificateStatus,
    CheckResult,
    PreAuditStatus,
)
from conformly.preaudit.service import (
    CertificateIssuanceBlockedError,
    InvalidAdoptionReferenceError,
    InvalidPreAuditTransitionError,
    PreAuditNotFoundError,
    PreAuditOptimisticLockError,
    PreAuditService,
    ReviewerConflictError,
)
from conformly.storage.models import StoredFile  # noqa: F401

# ── Fixtures ──────────────────────────────────────────────────────────────


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def _setup_tenant(session: Session) -> tuple:
    """Create a tenant with two users, a framework, adoption, and controls."""
    tenant = Tenant(
        name="Acme Corp",
        slug="acme",
        status=TenantStatus.ACTIVE,
    )
    session.add(tenant)
    session.flush()

    lead_user = User(
        oidc_issuer="https://issuer.test",
        oidc_subject="lead-subject",
        email="lead@acme.test",
        display_name="Lead",
    )
    reviewer_user = User(
        oidc_issuer="https://issuer.test",
        oidc_subject="reviewer-subject",
        email="reviewer@acme.test",
        display_name="Reviewer",
    )
    session.add_all([lead_user, reviewer_user])
    session.flush()

    for user in (lead_user, reviewer_user):
        m = Membership(
            tenant_id=tenant.id,
            user_id=user.id,
            role="compliance_manager",
            status=MembershipStatus.ACTIVE,
        )
        session.add(m)
    session.flush()

    fw = Framework(slug="iso27001", name="ISO 27001")
    session.add(fw)
    session.flush()

    fv = FrameworkVersion(
        framework_id=fw.id,
        version="2022",
        release_state=ReleaseState.RELEASED,
        created_by_user_id=lead_user.id,
    )
    session.add(fv)
    session.flush()

    controls = []
    for i in range(3):
        ctrl = CanonicalControl(
            framework_version_id=fv.id,
            identifier=f"A.5.{i + 1}",
            title=f"Control {i + 1}",
            description=f"Description {i + 1}",
            category="access_control",
            sort_order=i,
        )
        session.add(ctrl)
        controls.append(ctrl)
    session.flush()

    adoption = TenantFrameworkAdoption(
        tenant_id=tenant.id,
        framework_id=fw.id,
        framework_version_id=fv.id,
        status=AdoptionStatus.ACTIVE,
        adopted_at=datetime.now(UTC),
        adopted_by_user_id=lead_user.id,
    )
    session.add(adoption)
    session.flush()

    return tenant, lead_user, reviewer_user, fw, fv, controls, adoption


def _make_principal(user_id: UUID, is_platform_admin: bool = False) -> Principal:
    return Principal(user_id=user_id, is_platform_admin=is_platform_admin)


def _make_tenant_ctx(
    tenant_id: UUID, user_id: UUID, role: Role = Role.COMPLIANCE_MANAGER
) -> TenantContext:
    return TenantContext(tenant_id=tenant_id, user_id=user_id, role=role)


# ── Tests ─────────────────────────────────────────────────────────────────


class TestCreatePreAudit:
    def test_creates_with_scope(self) -> None:
        session = _session()
        t, lead, _, _, _, controls, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        principal = _make_principal(lead.id)
        ctx = _make_tenant_ctx(t.id, lead.id)

        pa = svc.create_pre_audit(
            principal,
            ctx,
            title="Readiness Assessment",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )

        assert pa.status == PreAuditStatus.PLANNING
        assert pa.rule_version == "v1.0.0"
        session.refresh(pa)
        # Scope should be auto-created
        assert len(pa.scopes) == 1
        assert pa.scopes[0].control_count == len(controls)

    def test_invalid_adoption_raises(self) -> None:
        session = _session()
        t, lead, _, _, _, _, _ = _setup_tenant(session)
        svc = PreAuditService(session)
        principal = _make_principal(lead.id)
        ctx = _make_tenant_ctx(t.id, lead.id)

        with pytest.raises(InvalidAdoptionReferenceError):
            svc.create_pre_audit(
                principal,
                ctx,
                title="Bad",
                framework_adoption_id=uuid4(),
                lead_user_id=lead.id,
            )


class TestRunChecks:
    def test_basic_check_evaluation(self) -> None:
        session = _session()
        t, lead, _, _, _, controls, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        principal = _make_principal(lead.id)
        ctx = _make_tenant_ctx(t.id, lead.id)

        pa = svc.create_pre_audit(
            principal,
            ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )

        pa = svc.run_checks(principal, ctx, pa.id)

        assert pa.status == PreAuditStatus.IN_PROGRESS
        assert pa.overall_score is not None
        all_checks = [c for s in pa.scopes for c in s.checks]
        assert len(all_checks) == len(controls)

    def test_checks_with_compliance_data(self) -> None:
        session = _session()
        t, lead, _, _, _, controls, adoption = _setup_tenant(session)

        # Add evidence + policy + control status for first control
        evidence = EvidenceItem(
            tenant_id=t.id,
            title="Evidence 1",
            description="Test evidence",
            status=EvidenceStatus.VALID,
            owner_user_id=lead.id,
            version=1,
        )
        session.add(evidence)
        session.flush()

        link = EvidenceControlLink(
            tenant_id=t.id,
            evidence_id=evidence.id,
            control_type=ControlEntityType.CANONICAL,
            control_id=controls[0].id,
            linked_by_user_id=lead.id,
        )
        session.add(link)

        csr = ControlStatusRecord(
            tenant_id=t.id,
            control_type=ControlEntityType.CANONICAL,
            control_id=controls[0].id,
            status=ControlImplementationStatus.IMPLEMENTED,
            version=1,
        )
        session.add(csr)
        session.flush()

        svc = PreAuditService(session)
        principal = _make_principal(lead.id)
        ctx = _make_tenant_ctx(t.id, lead.id)

        pa = svc.create_pre_audit(
            principal,
            ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )
        pa = svc.run_checks(principal, ctx, pa.id)

        all_checks = [c for s in pa.scopes for c in s.checks]
        ctrl0_check = [c for c in all_checks if c.control_id == controls[0].id][0]
        assert ctrl0_check.evidence_count >= 1
        assert ctrl0_check.score > 0

    def test_cannot_run_checks_on_completed(self) -> None:
        session = _session()
        t, lead, reviewer, _, _, _, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        lead_p = _make_principal(lead.id)
        reviewer_p = _make_principal(reviewer.id)
        lead_ctx = _make_tenant_ctx(t.id, lead.id)
        reviewer_ctx = _make_tenant_ctx(t.id, reviewer.id)

        pa = svc.create_pre_audit(
            lead_p,
            lead_ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )
        pa = svc.run_checks(lead_p, lead_ctx, pa.id)
        pa = svc.submit_for_review(
            lead_p,
            lead_ctx,
            pa.id,
            reviewer_user_id=reviewer.id,
            expected_version=pa.version,
        )
        pa = svc.complete_review(reviewer_p, reviewer_ctx, pa.id, expected_version=pa.version)

        with pytest.raises(InvalidPreAuditTransitionError):
            svc.run_checks(lead_p, lead_ctx, pa.id)


class TestReviewWorkflow:
    def test_submit_and_complete_review(self) -> None:
        session = _session()
        t, lead, reviewer, _, _, _, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        lead_p = _make_principal(lead.id)
        reviewer_p = _make_principal(reviewer.id)
        lead_ctx = _make_tenant_ctx(t.id, lead.id)
        reviewer_ctx = _make_tenant_ctx(t.id, reviewer.id)

        pa = svc.create_pre_audit(
            lead_p,
            lead_ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )
        pa = svc.run_checks(lead_p, lead_ctx, pa.id)
        pa = svc.submit_for_review(
            lead_p,
            lead_ctx,
            pa.id,
            reviewer_user_id=reviewer.id,
            expected_version=pa.version,
        )
        assert pa.status == PreAuditStatus.IN_REVIEW
        assert pa.reviewer_user_id == reviewer.id

        pa = svc.complete_review(reviewer_p, reviewer_ctx, pa.id, expected_version=pa.version)
        assert pa.status == PreAuditStatus.COMPLETED
        assert pa.reviewed_at is not None

    def test_reviewer_cannot_be_lead(self) -> None:
        session = _session()
        t, lead, _, _, _, _, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        principal = _make_principal(lead.id)
        ctx = _make_tenant_ctx(t.id, lead.id)

        pa = svc.create_pre_audit(
            principal,
            ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )
        pa = svc.run_checks(principal, ctx, pa.id)

        with pytest.raises(ReviewerConflictError):
            svc.submit_for_review(
                principal,
                ctx,
                pa.id,
                reviewer_user_id=lead.id,
                expected_version=pa.version,
            )

    def test_only_reviewer_can_complete(self) -> None:
        session = _session()
        t, lead, reviewer, _, _, _, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        lead_p = _make_principal(lead.id)
        ctx = _make_tenant_ctx(t.id, lead.id)

        pa = svc.create_pre_audit(
            lead_p,
            ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )
        pa = svc.run_checks(lead_p, ctx, pa.id)
        pa = svc.submit_for_review(
            lead_p,
            ctx,
            pa.id,
            reviewer_user_id=reviewer.id,
            expected_version=pa.version,
        )

        with pytest.raises(InvalidPreAuditTransitionError):
            svc.complete_review(lead_p, ctx, pa.id, expected_version=pa.version)


class TestOptimisticLocking:
    def test_stale_version_raises(self) -> None:
        session = _session()
        t, lead, reviewer, _, _, _, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        principal = _make_principal(lead.id)
        ctx = _make_tenant_ctx(t.id, lead.id)

        pa = svc.create_pre_audit(
            principal,
            ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )
        pa = svc.run_checks(principal, ctx, pa.id)

        with pytest.raises(PreAuditOptimisticLockError):
            svc.submit_for_review(
                principal,
                ctx,
                pa.id,
                reviewer_user_id=reviewer.id,
                expected_version=1,  # stale
            )


class TestFindings:
    def test_add_and_update_finding(self) -> None:
        session = _session()
        t, lead, _, _, _, _, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        principal = _make_principal(lead.id)
        ctx = _make_tenant_ctx(t.id, lead.id)

        pa = svc.create_pre_audit(
            principal,
            ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )

        finding = svc.add_finding(
            principal,
            ctx,
            pa.id,
            title="Gap in A.5.1",
            description="No evidence linked",
            severity=FindingSeverity.HIGH,
        )
        assert finding.version == 1

        updated = svc.update_finding(
            principal,
            ctx,
            pa.id,
            finding.id,
            expected_version=1,
            remediation_status=RemediationStatus.RESOLVED,
        )
        assert updated.version == 2
        assert updated.remediation_status == RemediationStatus.RESOLVED


class TestCertificateIssuance:
    def _completed_pa(self, session: Session) -> tuple:
        t, lead, reviewer, _, _, controls, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        lead_p = _make_principal(lead.id)
        reviewer_p = _make_principal(reviewer.id)
        lead_ctx = _make_tenant_ctx(t.id, lead.id)
        reviewer_ctx = _make_tenant_ctx(t.id, reviewer.id)

        # Set up passing compliance data for all controls
        for ctrl in controls:
            for ev_i in range(2):
                evidence = EvidenceItem(
                    tenant_id=t.id,
                    title=f"Evidence {ev_i} for {ctrl.identifier}",
                    description="Test",
                    status=EvidenceStatus.VALID,
                    owner_user_id=lead.id,
                    version=1,
                )
                session.add(evidence)
                session.flush()

                ecl = EvidenceControlLink(
                    tenant_id=t.id,
                    evidence_id=evidence.id,
                    control_type=ControlEntityType.CANONICAL,
                    control_id=ctrl.id,
                    linked_by_user_id=lead.id,
                )
                session.add(ecl)

            policy = Policy(
                tenant_id=t.id,
                title=f"Policy for {ctrl.identifier}",
                description="Test",
                status=PolicyStatus.PUBLISHED,
                owner_user_id=lead.id,
                version=1,
            )
            session.add(policy)
            session.flush()

            pcl = PolicyControlLink(
                tenant_id=t.id,
                policy_id=policy.id,
                control_type=ControlEntityType.CANONICAL,
                control_id=ctrl.id,
                linked_by_user_id=lead.id,
            )
            session.add(pcl)

            csr = ControlStatusRecord(
                tenant_id=t.id,
                control_type=ControlEntityType.CANONICAL,
                control_id=ctrl.id,
                status=ControlImplementationStatus.IMPLEMENTED,
                version=1,
            )
            session.add(csr)

        session.flush()

        pa = svc.create_pre_audit(
            lead_p,
            lead_ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )
        pa = svc.run_checks(lead_p, lead_ctx, pa.id)
        pa = svc.submit_for_review(
            lead_p,
            lead_ctx,
            pa.id,
            reviewer_user_id=reviewer.id,
            expected_version=pa.version,
        )
        pa = svc.complete_review(reviewer_p, reviewer_ctx, pa.id, expected_version=pa.version)
        pa = svc.tenant_approve(lead_p, lead_ctx, pa.id, expected_version=pa.version)
        return t, lead, reviewer, pa, svc, lead_p, reviewer_p, lead_ctx

    def test_issue_certificate_on_completed(self) -> None:
        session = _session()
        t, lead, _, pa, svc, lead_p, _, ctx = self._completed_pa(session)

        cert = svc.issue_certificate(lead_p, ctx, pa.id)
        assert cert.status == CertificateStatus.ACTIVE
        assert cert.certificate_number.startswith("CONF-RA-")
        assert cert.expires_at > cert.issued_at

    def test_cannot_issue_before_completion(self) -> None:
        session = _session()
        t, lead, _, _, _, _, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        principal = _make_principal(lead.id)
        ctx = _make_tenant_ctx(t.id, lead.id)

        pa = svc.create_pre_audit(
            principal,
            ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )

        with pytest.raises(CertificateIssuanceBlockedError):
            svc.issue_certificate(principal, ctx, pa.id)

    def test_cannot_issue_with_failed_checks(self) -> None:
        session = _session()
        t, lead, reviewer, _, _, _, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        lead_p = _make_principal(lead.id)
        reviewer_p = _make_principal(reviewer.id)
        lead_ctx = _make_tenant_ctx(t.id, lead.id)
        reviewer_ctx = _make_tenant_ctx(t.id, reviewer.id)

        pa = svc.create_pre_audit(
            lead_p,
            lead_ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )
        pa = svc.run_checks(lead_p, lead_ctx, pa.id)

        # Check if there are failures
        all_checks = [c for s in pa.scopes for c in s.checks]
        has_fail = any(c.result == CheckResult.FAIL for c in all_checks)

        if has_fail:
            pa = svc.submit_for_review(
                lead_p,
                lead_ctx,
                pa.id,
                reviewer_user_id=reviewer.id,
                expected_version=pa.version,
            )
            pa = svc.complete_review(
                reviewer_p,
                reviewer_ctx,
                pa.id,
                expected_version=pa.version,
            )
            with pytest.raises(CertificateIssuanceBlockedError):
                svc.issue_certificate(lead_p, lead_ctx, pa.id)

    def test_revoke_certificate(self) -> None:
        session = _session()
        _, _, _, pa, svc, lead_p, _, ctx = self._completed_pa(session)

        cert = svc.issue_certificate(lead_p, ctx, pa.id)
        revoked = svc.revoke_certificate(lead_p, ctx, pa.id, cert.id, reason="Policy violation")
        assert revoked.status == CertificateStatus.REVOKED
        assert revoked.revoked_reason == "Policy violation"

    def test_suspend_and_reinstate_certificate(self) -> None:
        session = _session()
        _, _, _, pa, svc, lead_p, _, ctx = self._completed_pa(session)

        cert = svc.issue_certificate(lead_p, ctx, pa.id)
        assert cert.status == CertificateStatus.ACTIVE

        suspended = svc.suspend_certificate(lead_p, ctx, pa.id, cert.id, reason="Control under review")
        assert suspended.status == CertificateStatus.SUSPENDED
        assert suspended.suspended_reason == "Control under review"
        assert suspended.suspended_at is not None

        reinstated = svc.reinstate_certificate(lead_p, ctx, pa.id, cert.id, reason="Review cleared")
        assert reinstated.status == CertificateStatus.ACTIVE
        assert reinstated.suspended_at is None
        assert reinstated.suspended_reason is None

    def test_reissue_certificate_auto_supersedes_existing(self) -> None:
        session = _session()
        _, _, _, pa, svc, lead_p, _, ctx = self._completed_pa(session)

        cert1 = svc.issue_certificate(lead_p, ctx, pa.id)
        assert cert1.status == CertificateStatus.ACTIVE

        cert2 = svc.issue_certificate(lead_p, ctx, pa.id)
        assert cert2.status == CertificateStatus.ACTIVE
        assert cert2.id != cert1.id

        # cert1 should be superseded by cert2
        assert cert1.status == CertificateStatus.SUPERSEDED
        assert cert1.superseded_by_certificate_id == cert2.id
        assert cert1.superseded_at is not None

    def test_reviewer_cannot_tenant_approve(self) -> None:
        from conformly.preaudit.service import ReviewerConflictError

        session = _session()
        t, lead, reviewer, _, _, _, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        lead_p = _make_principal(lead.id)
        reviewer_p = _make_principal(reviewer.id)
        lead_ctx = _make_tenant_ctx(t.id, lead.id)
        reviewer_ctx = _make_tenant_ctx(t.id, reviewer.id)

        pa = svc.create_pre_audit(
            lead_p,
            lead_ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )
        pa = svc.run_checks(lead_p, lead_ctx, pa.id)
        pa = svc.submit_for_review(
            lead_p,
            lead_ctx,
            pa.id,
            reviewer_user_id=reviewer.id,
            expected_version=pa.version,
        )
        pa = svc.complete_review(reviewer_p, reviewer_ctx, pa.id, expected_version=pa.version)

        # Reviewer attempting tenant approval must fail with ReviewerConflictError
        with pytest.raises(ReviewerConflictError):
            svc.tenant_approve(reviewer_p, reviewer_ctx, pa.id, expected_version=pa.version)


class TestCancelPreAudit:
    def test_cancel_from_planning(self) -> None:
        session = _session()
        t, lead, _, _, _, _, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        principal = _make_principal(lead.id)
        ctx = _make_tenant_ctx(t.id, lead.id)

        pa = svc.create_pre_audit(
            principal,
            ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )
        pa = svc.cancel_pre_audit(principal, ctx, pa.id, expected_version=pa.version)
        assert pa.status == PreAuditStatus.CANCELLED


class TestTenantIsolation:
    def test_cross_tenant_access_denied(self) -> None:
        session = _session()
        t, lead, _, _, _, _, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        principal = _make_principal(lead.id)
        ctx = _make_tenant_ctx(t.id, lead.id)

        pa = svc.create_pre_audit(
            principal,
            ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )

        other_ctx = _make_tenant_ctx(uuid4(), lead.id)
        with pytest.raises(PreAuditNotFoundError):
            svc.get_pre_audit(principal, other_ctx, pa.id)


class TestScoreSummary:
    def test_score_summary(self) -> None:
        session = _session()
        t, lead, _, _, _, _, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        principal = _make_principal(lead.id)
        ctx = _make_tenant_ctx(t.id, lead.id)

        pa = svc.create_pre_audit(
            principal,
            ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )
        pa = svc.run_checks(principal, ctx, pa.id)
        pa = svc.get_pre_audit(principal, ctx, pa.id)
        summary = svc.compute_score_summary(pa)

        assert "overall_score" in summary
        assert "total_checks" in summary
        assert summary["total_checks"] >= 0


class TestAuditEvents:
    def test_create_generates_audit_event(self) -> None:
        session = _session()
        t, lead, _, _, _, _, adoption = _setup_tenant(session)
        svc = PreAuditService(session)
        principal = _make_principal(lead.id)
        ctx = _make_tenant_ctx(t.id, lead.id)

        svc.create_pre_audit(
            principal,
            ctx,
            title="Test",
            framework_adoption_id=adoption.id,
            lead_user_id=lead.id,
        )

        events = list(
            session.scalars(select(AuditEvent).where(AuditEvent.action == "preaudit.create"))
        )
        assert len(events) == 1
        assert events[0].tenant_id == t.id
