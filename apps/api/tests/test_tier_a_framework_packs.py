from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal
from conformly.frameworks.applicability import (
    TenantProfileContext,
    evaluate_and_apply_adoption_applicability,
    evaluate_control_applicability,
)
from conformly.frameworks.models import (
    CanonicalControl,
    Framework,
    FrameworkVersion,
    OverlayApplicability,
    ReleaseState,
    TenantFrameworkAdoption,
)
from conformly.frameworks.seed_packs import (
    APPROVER_EMAIL,
    APPROVER_USER_ID,
    AUTHOR_USER_ID,
    LEGAL_REVIEWER_EMAIL,
    seed_tier_a_framework_packs,
    seed_tier_a_test_fixtures,
)
from conformly.frameworks.service import (
    FrameworkService,
    ImmutableCanonicalVersionError,
)
from conformly.identity.models import Tenant, User, UserStatus


def test_seed_tier_a_framework_packs_defaults_to_unapproved_drafts_without_synthetic_users(
    session: Session,
) -> None:
    """Default seed_tier_a_framework_packs must create unapproved DRAFTS only.

    It must NOT create synthetic reviewer/approver accounts, must NOT fabricate reviews,
    and must NOT auto-release packs. Separate account IDs do NOT constitute independent human review.
    """
    drafts = seed_tier_a_framework_packs(session)  # Default: as_drafts=True

    assert len(drafts) == 6
    for version in drafts:
        assert version.release_state == ReleaseState.DRAFT
        assert version.legal_reviewed_by_user_id is None
        assert version.legal_reviewed_at is None
        assert version.approved_by_user_id is None
        assert version.approved_at is None
        assert version.released_at is None

    # Verify synthetic legal reviewer and approver were NOT created
    legal_user = session.scalar(select(User).where(User.email == LEGAL_REVIEWER_EMAIL))
    approver_user = session.scalar(select(User).where(User.email == APPROVER_EMAIL))
    assert legal_user is None
    assert approver_user is None


def test_seed_tier_a_framework_packs_independent_approval(session: Session) -> None:
    """Verify synthetic test fixture pipeline enforces independent 2-person approval in automated test harness."""
    released = seed_tier_a_test_fixtures(session)

    assert len(released) == 6
    expected_slugs = {"iso-27001", "gdpr-bdsg", "nist-csf", "cis-controls-ig1", "mvsp", "iso-9001"}
    actual_slugs = {v.framework.slug for v in released}
    assert actual_slugs == expected_slugs

    for version in released:
        # 1. State must be formally RELEASED
        assert version.release_state == ReleaseState.RELEASED
        assert version.released_at is not None

        # 2. Mandatory independent 2-person approval rule:
        assert version.created_by_user_id == AUTHOR_USER_ID
        assert version.approved_by_user_id == APPROVER_USER_ID
        assert version.created_by_user_id != version.approved_by_user_id

        # 3. Legal and compliance review must have occurred
        assert version.legal_reviewed_by_user_id is not None
        assert version.legal_review_notes is not None
        assert len(version.legal_review_notes) > 0

        # 4. Canonical controls must be populated and have required guidance
        assert len(version.controls) > 0
        for ctrl in version.controls:
            assert ctrl.identifier != ""
            assert ctrl.title != ""
            assert ctrl.description != ""
            assert ctrl.category != ""
            assert ctrl.guidance is not None
            assert "**Evidence Requests:**" in ctrl.guidance
            assert "**Policy Reference:**" in ctrl.guidance


def test_tier_a_framework_idempotent_seeding(session: Session) -> None:
    """Running test fixture seed multiple times should be idempotent without duplicate rows or errors."""
    released1 = seed_tier_a_test_fixtures(session)
    released2 = seed_tier_a_test_fixtures(session)

    assert len(released1) == len(released2) == 6

    # Check total frameworks count in DB
    frameworks = session.scalars(select(Framework)).all()
    assert len(frameworks) == 6


def test_released_framework_post_release_immutability(session: Session) -> None:
    """Attempting to mutate controls of released versions must be blocked."""
    seed_tier_a_test_fixtures(session)

    author = Principal(user_id=AUTHOR_USER_ID, is_platform_admin=True, mfa_verified=True)
    service = FrameworkService(session)

    version = session.scalar(
        select(FrameworkVersion).join(Framework).where(Framework.slug == "iso-27001")
    )
    assert version is not None
    assert version.release_state == ReleaseState.RELEASED

    with pytest.raises(ImmutableCanonicalVersionError):
        service.add_canonical_control(
            author,
            version.id,
            "A.99.1",
            "Tampered Control",
            "Illegal edit post release",
            "Testing",
            None,
            999,
            "req-tamper",
        )


def test_deterministic_applicability_evaluation_engine(session: Session) -> None:
    """Test deterministic applicability rules against control characteristics."""
    seed_tier_a_test_fixtures(session)

    # 1. 100% remote company (has_physical_offices=False)
    remote_profile = TenantProfileContext(
        has_physical_offices=False,
        operates_own_datacenter=False,
        employee_count=15,
        processes_special_category_data=False,
        involves_international_transfers=False,
        uses_subprocessors=True,
    )

    ctrl_physical = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "A.7.1")
    )
    assert ctrl_physical is not None
    eval_physical = evaluate_control_applicability(ctrl_physical, remote_profile)
    assert eval_physical.applicability == OverlayApplicability.SCOPED_OUT
    assert "remote" in eval_physical.justification.lower()

    # 2. Employee count < 20 (German § 38 BDSG DPO threshold)
    ctrl_dpo_threshold = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "BDSG-SEC-38")
    )
    assert ctrl_dpo_threshold is not None
    eval_dpo = evaluate_control_applicability(ctrl_dpo_threshold, remote_profile)
    assert eval_dpo.applicability == OverlayApplicability.NOT_APPLICABLE
    assert "below the statutory threshold" in eval_dpo.justification.lower()

    # 3. Employee count >= 20 -> DPO threshold becomes APPLICABLE
    enterprise_profile = TenantProfileContext(
        has_physical_offices=True,
        operates_own_datacenter=True,
        employee_count=45,
        processes_special_category_data=True,
        involves_international_transfers=True,
        uses_subprocessors=True,
    )
    eval_dpo_large = evaluate_control_applicability(ctrl_dpo_threshold, enterprise_profile)
    assert eval_dpo_large.applicability == OverlayApplicability.APPLICABLE

    # 4. Special categories of data (§ 22 BDSG)
    ctrl_special_data = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "BDSG-SEC-22")
    )
    assert ctrl_special_data is not None
    eval_special_no = evaluate_control_applicability(ctrl_special_data, remote_profile)
    assert eval_special_no.applicability == OverlayApplicability.NOT_APPLICABLE
    assert "does not process special categories" in eval_special_no.justification.lower()

    eval_special_yes = evaluate_control_applicability(ctrl_special_data, enterprise_profile)
    assert eval_special_yes.applicability == OverlayApplicability.APPLICABLE

    # 5. International data transfers (GDPR Art. 44)
    ctrl_transfers = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "GDPR-ART-44")
    )
    assert ctrl_transfers is not None
    eval_transfers_no = evaluate_control_applicability(ctrl_transfers, remote_profile)
    assert eval_transfers_no.applicability == OverlayApplicability.NOT_APPLICABLE
    assert "within the european economic area" in eval_transfers_no.justification.lower()

    eval_transfers_yes = evaluate_control_applicability(ctrl_transfers, enterprise_profile)
    assert eval_transfers_yes.applicability == OverlayApplicability.APPLICABLE


def test_batch_adoption_applicability_evaluation(session: Session) -> None:
    """Test full batch evaluation of an adopted framework and creation of overlays."""
    seed_tier_a_test_fixtures(session)

    # Create tenant and user
    tenant_id = uuid4()
    tenant = Tenant(id=tenant_id, name="Applicability Test Org", slug="applicability-test-org")
    session.add(tenant)

    user_id = uuid4()
    user = User(
        id=user_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="app-user-1",
        email="app-user-1@example.com",
        display_name="Applicability User",
        status=UserStatus.ACTIVE,
    )
    session.add(user)
    session.flush()

    # Adopt GDPR-BDSG
    gdpr_version = session.scalar(
        select(FrameworkVersion).join(Framework).where(Framework.slug == "gdpr-bdsg")
    )
    assert gdpr_version is not None

    adoption = TenantFrameworkAdoption(
        tenant_id=tenant_id,
        framework_id=gdpr_version.framework_id,
        framework_version_id=gdpr_version.id,
        adopted_by_user_id=user_id,
    )
    session.add(adoption)
    session.flush()

    principal = Principal(user_id=user_id, is_platform_admin=False, mfa_verified=True)

    # Remote profile: <20 employees, no special data, no international transfers
    profile = TenantProfileContext(
        employee_count=12,
        processes_special_category_data=False,
        involves_international_transfers=False,
        uses_subprocessors=True,
    )

    overlays = evaluate_and_apply_adoption_applicability(
        session,
        tenant_id=tenant_id,
        adoption_id=adoption.id,
        profile=profile,
        principal=principal,
        request_id="req-eval-test",
    )

    assert len(overlays) == len(gdpr_version.controls)

    # Verify specific overlays
    overlays_by_id = {o.canonical_control_id: o for o in overlays}

    ctrl_bdsg_38 = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "BDSG-SEC-38")
    )
    assert ctrl_bdsg_38 is not None
    assert overlays_by_id[ctrl_bdsg_38.id].applicability == OverlayApplicability.NOT_APPLICABLE

    ctrl_bdsg_22 = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "BDSG-SEC-22")
    )
    assert ctrl_bdsg_22 is not None
    assert overlays_by_id[ctrl_bdsg_22.id].applicability == OverlayApplicability.NOT_APPLICABLE

    ctrl_gdpr_44 = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "GDPR-ART-44")
    )
    assert ctrl_gdpr_44 is not None
    assert overlays_by_id[ctrl_gdpr_44.id].applicability == OverlayApplicability.NOT_APPLICABLE

    ctrl_gdpr_30 = session.scalar(
        select(CanonicalControl).where(CanonicalControl.identifier == "GDPR-ART-30")
    )
    assert ctrl_gdpr_30 is not None
    assert overlays_by_id[ctrl_gdpr_30.id].applicability == OverlayApplicability.APPLICABLE
