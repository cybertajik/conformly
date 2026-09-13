"""Step 5 Acceptance Tests: Repair Applicability and Scope Decisions.

Validates:
- Versioned declarative rules engine bound to stable requirement IDs (no substring heuristics).
- DPO appointment obligations evaluated from processing facts and triggers (§ 38 BDSG, Art. 37 GDPR).
- Remote work and physical controls: perimeter access vs. endpoint safeguards vs. inherited cloud assurance.
- Disambiguation: suppliers vs. personal-data subprocessors (A.5.19 unaffected by uses_subprocessors=False).
- International data transfers: non-EEA remote access, onward transfers, and EEA storage limitations.
- Contradictory answers and unknown facts: never default to exempt; flags REVIEW_REQUIRED.
- Persistence of profile answers, sources, evaluator version, contradictions, and summary metrics.
- Scope changes trigger impact diffs and audit logging.
- Manual overrides require substantive auditable justifications.
- RBAC role differences: restricted roles denied; tenant isolation enforced.
"""

import json
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditEvent
from conformly.authz.policy import AuthorizationDeniedError, Principal, TenantContext
from conformly.authz.roles import Role
from conformly.frameworks.applicability import (
    EVALUATOR_VERSION,
    TenantProfileContext,
    evaluate_and_apply_adoption_applicability,
    evaluate_control_applicability,
    override_control_applicability,
)
from conformly.frameworks.models import (
    CanonicalControl,
    Framework,
    FrameworkVersion,
    OverlayApplicability,
    TenantApplicabilityProfile,
    TenantFrameworkAdoption,
)
from conformly.frameworks.seed_packs import seed_tier_a_test_fixtures
from conformly.identity.models import Membership, Tenant, User, UserStatus


@pytest.fixture(autouse=True)
def seeded_frameworks(session: Session) -> None:
    """Ensure Tier A framework catalog is seeded for tests."""
    seed_tier_a_test_fixtures(session)


def create_tenant_and_principal(
    session: Session,
    *,
    role: Role = Role.OWNER,
    tenant_name: str = "Step 5 Test Org",
) -> tuple[Tenant, User, Principal, TenantContext]:
    tenant_id = uuid4()
    tenant = Tenant(id=tenant_id, name=tenant_name, slug=f"org-{uuid4().hex[:8]}")
    session.add(tenant)

    user_id = uuid4()
    user = User(
        id=user_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject=f"sub-{uuid4().hex[:8]}",
        email=f"user-{uuid4().hex[:8]}@example.com",
        display_name="Applicability Tester",
        status=UserStatus.ACTIVE,
    )
    session.add(user)

    membership = Membership(
        tenant_id=tenant_id,
        user_id=user_id,
        role=role,
    )
    session.add(membership)
    session.flush()

    principal = Principal(user_id=user_id, is_platform_admin=False, mfa_verified=True)
    tenant_context = TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        role=role,
        is_workforce=False,
    )
    return tenant, user, principal, tenant_context


# -----------------------------------------------------------------------------
# Test 5A: Pure Declarative Rule Binding (No Substring Heuristics)
# -----------------------------------------------------------------------------
def test_pure_declarative_rule_binding_and_no_substring_heuristics(session: Session) -> None:
    """Ensure controls are bound strictly by stable ID, not by substring matching in title/description."""
    # Create a synthetic control whose title contains trigger words ("physical perimeter", "20 persons")
    # but whose identifier is unrelated
    synthetic_version = session.scalar(select(FrameworkVersion))
    assert synthetic_version is not None

    unrelated_ctrl = CanonicalControl(
        framework_version_id=synthetic_version.id,
        identifier="CUSTOM-CTRL-999",
        title="Physical perimeter access monitoring with 20 persons in special categories",
        description="A control containing trigger phrases in prose.",
        category="General Security",
        sort_order=999,
    )
    session.add(unrelated_ctrl)
    session.flush()

    remote_profile = TenantProfileContext(
        has_physical_offices=False,
        operates_own_datacenter=False,
        employee_count=10,
        processes_special_category_data=False,
    )

    ev = evaluate_control_applicability(unrelated_ctrl, remote_profile)
    # Must NOT be scoped out or not applicable simply because the title contained substrings!
    assert ev.applicability == OverlayApplicability.APPLICABLE
    assert ev.evaluator_version == EVALUATOR_VERSION


# -----------------------------------------------------------------------------
# Test 5B: Regression: DPO Obligations Beyond Naive Headcount (§ 38 BDSG / Art. 37 GDPR)
# -----------------------------------------------------------------------------
def test_regression_dpo_obligations_beyond_headcount(session: Session) -> None:
    """Under § 38 BDSG / Art. 37 GDPR, DPO appointment cannot be decided by headcount < 20 alone."""
    ctrl_bdsg_38 = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "BDSG-SEC-38")
    )
    assert ctrl_bdsg_38 is not None

    # Case 1: Headcount < 20 (12 employees), but DPIA required (§ 38(1) sent. 2 BDSG) -> APPLICABLE
    p_dpia = TenantProfileContext(
        employee_count=12,
        requires_dpia=True,
    )
    ev_dpia = evaluate_control_applicability(ctrl_bdsg_38, p_dpia)
    assert ev_dpia.applicability == OverlayApplicability.APPLICABLE
    assert "impact assessment" in ev_dpia.justification.lower()

    # Case 2: Headcount < 20 (14 employees), but commercial transfer / credit scoring (§ 38(1) sent. 2) -> APPLICABLE
    p_comm = TenantProfileContext(
        employee_count=14,
        processes_data_commercially_for_transfer_or_market_research=True,
    )
    ev_comm = evaluate_control_applicability(ctrl_bdsg_38, p_comm)
    assert ev_comm.applicability == OverlayApplicability.APPLICABLE
    assert "commercially" in ev_comm.justification.lower()

    # Case 3: Headcount < 20, but regular systematic monitoring large scale (Art. 37(1)(b) GDPR) -> APPLICABLE
    p_mon = TenantProfileContext(
        employee_count=8,
        regular_systematic_monitoring_large_scale=True,
    )
    ev_mon = evaluate_control_applicability(ctrl_bdsg_38, p_mon)
    assert ev_mon.applicability == OverlayApplicability.APPLICABLE

    # Case 4: Headcount < 20, but large-scale special category processing (Art. 37(1)(c) GDPR) -> APPLICABLE
    p_spec = TenantProfileContext(
        employee_count=5,
        large_scale_special_category_processing=True,
    )
    ev_spec = evaluate_control_applicability(ctrl_bdsg_38, p_spec)
    assert ev_spec.applicability == OverlayApplicability.APPLICABLE

    # Case 5: Headcount threshold boundary: 19 vs 20
    p_19 = TenantProfileContext(
        employee_count=19,
        requires_dpia=False,
        processes_data_commercially_for_transfer_or_market_research=False,
    )
    ev_19 = evaluate_control_applicability(ctrl_bdsg_38, p_19)
    assert ev_19.applicability == OverlayApplicability.NOT_APPLICABLE
    assert "below the statutory threshold" in ev_19.justification.lower()

    p_20 = TenantProfileContext(
        employee_count=20,
    )
    ev_20 = evaluate_control_applicability(ctrl_bdsg_38, p_20)
    assert ev_20.applicability == OverlayApplicability.APPLICABLE
    assert "20 persons" in ev_20.justification.lower()

    # Case 6: Total headcount is 50, but automated processing personnel is only 15 and no triggers
    p_split = TenantProfileContext(
        employee_count=50,
        automated_processing_personnel_count=15,
        requires_dpia=False,
        processes_data_commercially_for_transfer_or_market_research=False,
    )
    ev_split = evaluate_control_applicability(ctrl_bdsg_38, p_split)
    assert ev_split.applicability == OverlayApplicability.NOT_APPLICABLE
    assert "15 persons in automated data processing" in ev_split.justification.lower()

    # Case 7: Unknown headcount (None) -> REVIEW_REQUIRED
    p_unknown = TenantProfileContext(
        employee_count=None,
    )
    ev_unknown = evaluate_control_applicability(ctrl_bdsg_38, p_unknown)
    assert ev_unknown.applicability == OverlayApplicability.REVIEW_REQUIRED


# -----------------------------------------------------------------------------
# Test 5C: Regression: Remote Work & Inherited Infrastructure Assurance
# -----------------------------------------------------------------------------
def test_regression_remote_work_and_outsourced_infrastructure(session: Session) -> None:
    """Remote work does not eliminate endpoint safeguards; cloud hosting requires inherited assurance."""
    ctrl_perimeter = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "A.7.1")
    )
    ctrl_clear_desk = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "A.7.7")
    )
    ctrl_endpoint = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "A.8.1")
    )
    ctrl_mvsp_datacenter = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier.in_(["MVSP-1-6", "MVSP-4.1"]))
    )
    assert ctrl_perimeter and ctrl_clear_desk and ctrl_endpoint and ctrl_mvsp_datacenter

    # 100% remote organization
    remote_profile = TenantProfileContext(
        has_physical_offices=False,
        operates_own_datacenter=False,
        uses_cloud_infrastructure=True,
    )

    # Physical perimeter of office is SCOPED_OUT
    ev_perimeter = evaluate_control_applicability(ctrl_perimeter, remote_profile)
    assert ev_perimeter.applicability == OverlayApplicability.SCOPED_OUT

    # BUT endpoint and clear desk controls remain APPLICABLE
    ev_desk = evaluate_control_applicability(ctrl_clear_desk, remote_profile)
    assert ev_desk.applicability == OverlayApplicability.APPLICABLE

    ev_ep = evaluate_control_applicability(ctrl_endpoint, remote_profile)
    assert ev_ep.applicability == OverlayApplicability.APPLICABLE

    # Cloud datacenter is NOT_APPLICABLE with inherited assurance requirement
    ev_dc = evaluate_control_applicability(ctrl_mvsp_datacenter, remote_profile)
    assert ev_dc.applicability == OverlayApplicability.NOT_APPLICABLE
    assert "inherited" in ev_dc.justification.lower()
    assert "soc 2" in ev_dc.justification.lower() or "iso 27001" in ev_dc.justification.lower()

    # Unknown physical office status -> REVIEW_REQUIRED
    p_unconfirmed = TenantProfileContext(has_physical_offices=None)
    assert (
        evaluate_control_applicability(ctrl_perimeter, p_unconfirmed).applicability
        == OverlayApplicability.REVIEW_REQUIRED
    )


# -----------------------------------------------------------------------------
# Test 5D: Regression: Suppliers Are Not Synonymous With Subprocessors
# -----------------------------------------------------------------------------
def test_regression_suppliers_not_synonymous_with_subprocessors(session: Session) -> None:
    """Organization without personal-data subprocessors still has general suppliers."""
    ctrl_subprocessor = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "GDPR-ART-28")
    )
    ctrl_supplier_iso = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "A.5.19")
    )
    ctrl_supplier_nist = session.scalar(
        select(CanonicalControl).where(
            CanonicalControl.identifier.in_(["NIST-GV-SC-01", "GV.SC-01"])
        )
    )
    ctrl_supplier_mvsp = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier.in_(["MVSP-1-7", "MVSP-1.2"]))
    )
    assert ctrl_subprocessor and ctrl_supplier_iso and ctrl_supplier_nist and ctrl_supplier_mvsp

    # Tenant has NO personal data subprocessors, but HAS general suppliers (cloud, hardware, SaaS)
    profile = TenantProfileContext(
        uses_subprocessors=False,
        uses_suppliers=True,
    )

    # GDPR Art. 28 is NOT_APPLICABLE
    ev_sub = evaluate_control_applicability(ctrl_subprocessor, profile)
    assert ev_sub.applicability == OverlayApplicability.NOT_APPLICABLE

    # General supplier controls REMAIN APPLICABLE!
    ev_iso = evaluate_control_applicability(ctrl_supplier_iso, profile)
    assert ev_iso.applicability == OverlayApplicability.APPLICABLE

    ev_nist = evaluate_control_applicability(ctrl_supplier_nist, profile)
    assert ev_nist.applicability == OverlayApplicability.APPLICABLE

    ev_mvsp = evaluate_control_applicability(ctrl_supplier_mvsp, profile)
    assert ev_mvsp.applicability == OverlayApplicability.APPLICABLE


# -----------------------------------------------------------------------------
# Test 5E: Regression: International Transfers & Remote Access
# -----------------------------------------------------------------------------
def test_regression_international_transfers_and_remote_access(session: Session) -> None:
    """EEA storage does not exempt if non-EEA remote access or onward transfers exist."""
    ctrl_transfer = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "GDPR-ART-44")
    )
    assert ctrl_transfer is not None

    # Case 1: Data in EEA, but non-EEA remote engineering access exists -> APPLICABLE
    p_remote_access = TenantProfileContext(
        involves_international_transfers=True,
        has_third_country_remote_access=True,
    )
    ev_ra = evaluate_control_applicability(ctrl_transfer, p_remote_access)
    assert ev_ra.applicability == OverlayApplicability.APPLICABLE

    # Case 2: Claiming NO transfers while having remote access -> CONTRADICTION -> REVIEW_REQUIRED
    p_contradict = TenantProfileContext(
        involves_international_transfers=False,
        has_third_country_remote_access=True,
    )
    ev_conflict = evaluate_control_applicability(ctrl_transfer, p_contradict)
    assert ev_conflict.applicability == OverlayApplicability.REVIEW_REQUIRED
    assert "contradict" in ev_conflict.justification.lower()

    # Case 3: Unknown international transfer facts -> REVIEW_REQUIRED
    p_unknown = TenantProfileContext(
        involves_international_transfers=None,
    )
    ev_unk = evaluate_control_applicability(ctrl_transfer, p_unknown)
    assert ev_unk.applicability == OverlayApplicability.REVIEW_REQUIRED

    # Case 4: Strictly verified EEA storage without non-EEA remote access -> NOT_APPLICABLE
    p_pure_eea = TenantProfileContext(
        involves_international_transfers=False,
        has_third_country_remote_access=False,
        has_third_country_onward_transfers=False,
    )
    ev_eea = evaluate_control_applicability(ctrl_transfer, p_pure_eea)
    assert ev_eea.applicability == OverlayApplicability.NOT_APPLICABLE
    assert "within the european economic area" in ev_eea.justification.lower()


# -----------------------------------------------------------------------------
# Test 5F: Regression: Special Category Contradictions
# -----------------------------------------------------------------------------
def test_regression_special_category_contradiction_handling(session: Session) -> None:
    """Self-reported absence of special category data does not override affirmative facts."""
    ctrl_bdsg_22 = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "BDSG-SEC-22")
    )
    assert ctrl_bdsg_22 is not None

    # Claiming False, but health/biometrics processed -> CONTRADICTION -> REVIEW_REQUIRED
    p_conflict = TenantProfileContext(
        processes_special_category_data=False,
        processes_health_or_biometric_data=True,
    )
    ev = evaluate_control_applicability(ctrl_bdsg_22, p_conflict)
    assert ev.applicability == OverlayApplicability.REVIEW_REQUIRED
    assert "contradict" in ev.justification.lower()

    # Claiming False, but repository discovery found medical evidence -> REVIEW_REQUIRED
    p_disc = TenantProfileContext(
        processes_special_category_data=False,
        special_category_evidence_indicators=True,
    )
    ev_disc = evaluate_control_applicability(ctrl_bdsg_22, p_disc)
    assert ev_disc.applicability == OverlayApplicability.REVIEW_REQUIRED

    # Unknown -> REVIEW_REQUIRED
    p_unk = TenantProfileContext(processes_special_category_data=None)
    assert (
        evaluate_control_applicability(ctrl_bdsg_22, p_unk).applicability
        == OverlayApplicability.REVIEW_REQUIRED
    )


# -----------------------------------------------------------------------------
# Test 5G: Persistence of Profile Answers, Sources, and Evaluator Version
# -----------------------------------------------------------------------------
def test_persistence_of_profile_answers_sources_and_evaluator_version(session: Session) -> None:
    """Batch evaluation must persist TenantApplicabilityProfile with metadata and sources."""
    tenant, user, principal, tenant_context = create_tenant_and_principal(session)

    gdpr_version = session.scalar(
        select(FrameworkVersion).join(Framework).where(Framework.slug == "gdpr-bdsg")
    )
    assert gdpr_version is not None

    adoption = TenantFrameworkAdoption(
        tenant_id=tenant.id,
        framework_id=gdpr_version.framework_id,
        framework_version_id=gdpr_version.id,
        adopted_by_user_id=user.id,
    )
    session.add(adoption)
    session.flush()

    profile = TenantProfileContext(
        employee_count=16,
        requires_dpia=False,
        processes_special_category_data=False,
        involves_international_transfers=False,
        uses_subprocessors=True,
        sources={
            "employee_count": "HR Personio export 2026-09",
            "requires_dpia": "Legal assessment registry v2",
        },
    )

    overlays = evaluate_and_apply_adoption_applicability(
        session,
        tenant_id=tenant.id,
        adoption_id=adoption.id,
        profile=profile,
        principal=principal,
        request_id="req-persist-test",
        tenant_context=tenant_context,
    )
    assert len(overlays) == len(gdpr_version.controls)

    # Verify persisted TenantApplicabilityProfile record
    persisted_profile = session.scalar(
        select(TenantApplicabilityProfile).where(
            TenantApplicabilityProfile.tenant_id == tenant.id,
            TenantApplicabilityProfile.adoption_id == adoption.id,
        )
    )
    assert persisted_profile is not None
    assert persisted_profile.evaluator_version == EVALUATOR_VERSION
    assert persisted_profile.evaluated_by_user_id == user.id

    answers = json.loads(persisted_profile.profile_answers_json)
    assert answers["employee_count"] == 16

    sources = json.loads(persisted_profile.sources_json)
    assert sources["employee_count"] == "HR Personio export 2026-09"

    summary = json.loads(persisted_profile.evaluation_summary_json)
    assert summary["total_controls"] == len(gdpr_version.controls)
    assert summary["applicable_count"] > 0
    assert summary["not_applicable_count"] > 0


# -----------------------------------------------------------------------------
# Test 5H: Scope Change Impact Detection and Audit Events
# -----------------------------------------------------------------------------
def test_scope_change_impact_detection_and_audit(session: Session) -> None:
    """Changes in profile must trigger change impact detection and auditable logs."""
    tenant, user, principal, tenant_context = create_tenant_and_principal(session)

    gdpr_version = session.scalar(
        select(FrameworkVersion).join(Framework).where(Framework.slug == "gdpr-bdsg")
    )
    assert gdpr_version is not None

    adoption = TenantFrameworkAdoption(
        tenant_id=tenant.id,
        framework_id=gdpr_version.framework_id,
        framework_version_id=gdpr_version.id,
        adopted_by_user_id=user.id,
    )
    session.add(adoption)
    session.flush()

    # Initial profile: <20 employees, no special data
    profile_1 = TenantProfileContext(
        employee_count=10,
        processes_special_category_data=False,
        involves_international_transfers=False,
    )
    evaluate_and_apply_adoption_applicability(
        session,
        tenant_id=tenant.id,
        adoption_id=adoption.id,
        profile=profile_1,
        principal=principal,
        request_id="req-scope-1",
        tenant_context=tenant_context,
    )

    # Re-evaluate with modified profile: 50 employees, special category data -> triggers impact!
    profile_2 = TenantProfileContext(
        employee_count=50,
        processes_special_category_data=True,
        involves_international_transfers=True,
    )
    evaluate_and_apply_adoption_applicability(
        session,
        tenant_id=tenant.id,
        adoption_id=adoption.id,
        profile=profile_2,
        principal=principal,
        request_id="req-scope-2",
        tenant_context=tenant_context,
    )

    # Verify impact summary stored on adoption
    assert adoption.impact_summary_json is not None
    impact = json.loads(adoption.impact_summary_json)
    assert len(impact["newly_applicable"]) >= 2  # BDSG-SEC-38, BDSG-SEC-22, GDPR-ART-44
    assert "BDSG-SEC-38" in impact["newly_applicable"]

    # Verify audit events
    audit_events = session.scalars(
        select(AuditEvent).where(
            AuditEvent.tenant_id == tenant.id,
            AuditEvent.action == "framework_adoption.applicability_scope_changed",
        )
    ).all()
    assert len(audit_events) >= 1


# -----------------------------------------------------------------------------
# Test 5I: Manual Overlay Overrides Require Substantive Justification
# -----------------------------------------------------------------------------
def test_manual_overlay_override_requires_justification(session: Session) -> None:
    """Manually setting NOT_APPLICABLE or SCOPED_OUT without substantive justification must fail."""
    tenant, user, principal, tenant_context = create_tenant_and_principal(session)

    gdpr_version = session.scalar(
        select(FrameworkVersion).join(Framework).where(Framework.slug == "gdpr-bdsg")
    )
    assert gdpr_version is not None
    ctrl = gdpr_version.controls[0]

    adoption = TenantFrameworkAdoption(
        tenant_id=tenant.id,
        framework_id=gdpr_version.framework_id,
        framework_version_id=gdpr_version.id,
        adopted_by_user_id=user.id,
    )
    session.add(adoption)
    session.flush()

    # Attempt exclusion without justification
    with pytest.raises(ValueError, match="Exclusion requires an auditable justification"):
        override_control_applicability(
            session,
            tenant_id=tenant.id,
            adoption_id=adoption.id,
            control_id=ctrl.id,
            applicability=OverlayApplicability.NOT_APPLICABLE,
            justification="",
            principal=principal,
            tenant_context=tenant_context,
            request_id="req-override-fail",
        )

    # Attempt exclusion with trivial short justification
    with pytest.raises(ValueError, match="Exclusion requires an auditable justification"):
        override_control_applicability(
            session,
            tenant_id=tenant.id,
            adoption_id=adoption.id,
            control_id=ctrl.id,
            applicability=OverlayApplicability.SCOPED_OUT,
            justification="none",
            principal=principal,
            tenant_context=tenant_context,
            request_id="req-override-fail-2",
        )

    # Substantive justification succeeds
    valid_justification = (
        "System boundary excludes consumer payment processing; operated by external acquirer."
    )
    overlay = override_control_applicability(
        session,
        tenant_id=tenant.id,
        adoption_id=adoption.id,
        control_id=ctrl.id,
        applicability=OverlayApplicability.NOT_APPLICABLE,
        justification=valid_justification,
        principal=principal,
        tenant_context=tenant_context,
        request_id="req-override-success",
    )
    assert overlay.applicability == OverlayApplicability.NOT_APPLICABLE
    assert overlay.justification == valid_justification


# -----------------------------------------------------------------------------
# Test 5J: RBAC Denial for Restricted Roles & Cross-Tenant Isolation
# -----------------------------------------------------------------------------
def test_rbac_denial_and_cross_tenant_isolation(session: Session) -> None:
    """Restricted roles (Viewer, Employee) cannot evaluate scope; Tenant B cannot evaluate Tenant A."""
    tenant_a, user_a, principal_a, ctx_a = create_tenant_and_principal(
        session, role=Role.OWNER, tenant_name="Tenant Alpha"
    )
    tenant_b, user_b, principal_b, ctx_b = create_tenant_and_principal(
        session, role=Role.OWNER, tenant_name="Tenant Beta"
    )
    tenant_c, user_c, principal_c, ctx_c = create_tenant_and_principal(
        session, role=Role.VIEWER, tenant_name="Tenant Viewer"
    )

    gdpr_version = session.scalar(
        select(FrameworkVersion).join(Framework).where(Framework.slug == "gdpr-bdsg")
    )
    assert gdpr_version is not None

    adoption_a = TenantFrameworkAdoption(
        tenant_id=tenant_a.id,
        framework_id=gdpr_version.framework_id,
        framework_version_id=gdpr_version.id,
        adopted_by_user_id=user_a.id,
    )
    session.add(adoption_a)
    session.flush()

    profile = TenantProfileContext()

    # 1. Restricted role (Viewer) attempting evaluation -> 403 / AuthorizationDeniedError
    with pytest.raises(AuthorizationDeniedError):
        evaluate_and_apply_adoption_applicability(
            session,
            tenant_id=tenant_c.id,
            adoption_id=adoption_a.id,
            profile=profile,
            principal=principal_c,
            request_id="req-viewer-eval",
            tenant_context=ctx_c,
        )

    # 2. Cross-tenant isolation: Tenant B principal attempting evaluation on Tenant A's adoption
    with pytest.raises(ValueError, match="not found for tenant"):
        evaluate_and_apply_adoption_applicability(
            session,
            tenant_id=tenant_b.id,
            adoption_id=adoption_a.id,
            profile=profile,
            principal=principal_b,
            request_id="req-cross-tenant-eval",
            tenant_context=ctx_b,
        )
