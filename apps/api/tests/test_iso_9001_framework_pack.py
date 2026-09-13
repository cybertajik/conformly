"""Comprehensive test suite for the ISO 9001:2015 QMS framework pack.

Covers:
- Pack structure integrity: clause coverage, identifier uniqueness, guidance richness
- Coverage ledger completeness: every source requirement has IMPLEMENTED disposition
- Applicability engine: D&D, External Providers, Post-Delivery rules
- Seeding: idempotent import of 6-pack Tier A; seed_tier_a_test_fixtures returns 6 versions
- Immutability: ISO 9001 version blocks mutation once released
- Manifest consistency: required_beta_count == 6, iso-9001 REQUIRED_BETA
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal
from conformly.frameworks.applicability import (
    TenantProfileContext,
    evaluate_control_applicability,
)
from conformly.frameworks.manifest import get_required_beta_pack_ids
from conformly.frameworks.models import (
    CanonicalControl,
    Framework,
    FrameworkVersion,
    OverlayApplicability,
    ReleaseState,
)
from conformly.frameworks.packs.iso_9001 import (
    DESIGN_AND_DEVELOPMENT_SUBCLAUSES,
    EXTERNAL_PROVIDER_SUBCLAUSES,
    ISO_9001_PACK,
    POST_DELIVERY_SUBCLAUSES,
    QMS_CLAUSES,
)
from conformly.frameworks.packs_data import TIER_A_FRAMEWORK_PACKS
from conformly.frameworks.seed_packs import (
    APPROVER_USER_ID,
    AUTHOR_USER_ID,
    seed_tier_a_test_fixtures,
)
from conformly.frameworks.service import FrameworkService, ImmutableCanonicalVersionError

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture()
def qms_profile_no_dd_with_ep() -> TenantProfileContext:
    """Service-only org: no D&D, has external providers, no post-delivery."""
    return TenantProfileContext(
        performs_design_and_development=False,
        has_external_providers=True,
        has_post_delivery_activities=False,
    )


@pytest.fixture()
def qms_profile_with_dd_and_ep() -> TenantProfileContext:
    """Product org: performs D&D, has external providers, has post-delivery."""
    return TenantProfileContext(
        performs_design_and_development=True,
        has_external_providers=True,
        has_post_delivery_activities=True,
    )


@pytest.fixture()
def qms_profile_no_ep() -> TenantProfileContext:
    """Fully in-house org: no external providers, no D&D, no post-delivery."""
    return TenantProfileContext(
        performs_design_and_development=False,
        has_external_providers=False,
        has_post_delivery_activities=False,
    )


@pytest.fixture()
def qms_profile_unknown_dd() -> TenantProfileContext:
    """Profile where D&D scope is not yet confirmed."""
    return TenantProfileContext(
        performs_design_and_development=None,
        has_external_providers=True,
        has_post_delivery_activities=None,
    )


# =============================================================================
# 1. Pack structure integrity
# =============================================================================


class TestISO9001PackStructure:
    def test_pack_slug_and_name(self) -> None:
        assert ISO_9001_PACK.slug == "iso-9001"
        assert "ISO 9001" in ISO_9001_PACK.name
        assert "2015" in ISO_9001_PACK.name

    def test_pack_version(self) -> None:
        assert ISO_9001_PACK.version == "v2015"

    def test_control_count_matches_clause_count(self) -> None:
        """Every clause in QMS_CLAUSES must produce exactly one control."""
        assert len(ISO_9001_PACK.controls) == len(QMS_CLAUSES)

    def test_control_count_minimum_threshold(self) -> None:
        """Must have at minimum 50 addressable controls (all subclauses 4–10)."""
        assert len(ISO_9001_PACK.controls) >= 50

    def test_control_identifiers_are_unique(self) -> None:
        ids = [c.identifier for c in ISO_9001_PACK.controls]
        assert len(ids) == len(set(ids)), (
            f"Duplicate identifiers: {[i for i in ids if ids.count(i) > 1]}"
        )

    def test_control_identifier_prefix_format(self) -> None:
        """All control identifiers must follow QMS-N-N (or QMS-N-N-N) pattern."""
        for ctrl in ISO_9001_PACK.controls:
            assert ctrl.identifier.startswith("QMS-"), f"Bad prefix: {ctrl.identifier}"

    def test_all_controls_have_required_fields(self) -> None:
        for ctrl in ISO_9001_PACK.controls:
            assert ctrl.title, f"Empty title: {ctrl.identifier}"
            assert ctrl.description, f"Empty description: {ctrl.identifier}"
            assert ctrl.category, f"Empty category: {ctrl.identifier}"
            assert ctrl.guidance, f"Empty guidance: {ctrl.identifier}"
            assert ctrl.sort_order > 0, f"Non-positive sort_order: {ctrl.identifier}"

    def test_all_controls_guidance_richness(self) -> None:
        """Every control guidance must contain required audit-facing structural markers."""
        for ctrl in ISO_9001_PACK.controls:
            assert "**Evidence Requests:**" in ctrl.guidance, (
                f"Missing '**Evidence Requests:**' in {ctrl.identifier}"
            )
            assert "**Policy Reference:**" in ctrl.guidance, (
                f"Missing '**Policy Reference:**' in {ctrl.identifier}"
            )
            assert "**Audit Procedure:**" in ctrl.guidance, (
                f"Missing '**Audit Procedure:**' in {ctrl.identifier}"
            )

    def test_design_development_controls_marked_with_criteria(self) -> None:
        """Clause 8.3.x controls must carry applicability_criteria flagging D&D."""
        for ctrl in ISO_9001_PACK.controls:
            subclause = ctrl.identifier.replace("QMS-", "").replace("-", ".")
            if subclause in DESIGN_AND_DEVELOPMENT_SUBCLAUSES:
                assert ctrl.applicability_criteria.get("requires_design_and_development") is True, (
                    f"Control {ctrl.identifier} is a D&D clause but lacks applicability_criteria marker."
                )

    def test_external_provider_controls_marked_with_criteria(self) -> None:
        """Clause 8.4.x controls must carry applicability_criteria flagging external providers."""
        for ctrl in ISO_9001_PACK.controls:
            subclause = ctrl.identifier.replace("QMS-", "").replace("-", ".")
            if subclause in EXTERNAL_PROVIDER_SUBCLAUSES:
                assert ctrl.applicability_criteria.get("requires_external_providers") is True, (
                    f"Control {ctrl.identifier} is an external provider clause but lacks criteria marker."
                )

    def test_non_conditional_controls_have_empty_criteria(self) -> None:
        """Non-conditional controls must have empty applicability_criteria."""
        conditional = (
            DESIGN_AND_DEVELOPMENT_SUBCLAUSES
            | EXTERNAL_PROVIDER_SUBCLAUSES
            | POST_DELIVERY_SUBCLAUSES
        )
        for ctrl in ISO_9001_PACK.controls:
            subclause = ctrl.identifier.replace("QMS-", "").replace("-", ".")
            if subclause not in conditional:
                assert not ctrl.applicability_criteria, (
                    f"Control {ctrl.identifier} should not have applicability_criteria."
                )

    def test_all_clauses_4_to_10_represented(self) -> None:
        """Must have controls for each major clause 4 through 10."""
        control_ids = {c.identifier for c in ISO_9001_PACK.controls}
        required_clause_prefixes = [
            "QMS-4-",
            "QMS-5-",
            "QMS-6-",
            "QMS-7-",
            "QMS-8-",
            "QMS-9-",
            "QMS-10-",
        ]
        for prefix in required_clause_prefixes:
            assert any(c.startswith(prefix) for c in control_ids), (
                f"No controls found for clause with prefix {prefix}"
            )

    def test_clause_83_subclauses_all_present(self) -> None:
        """All 6 D&D subclauses (8.3.1–8.3.6) must be in the pack."""
        control_ids = {c.identifier for c in ISO_9001_PACK.controls}
        for subclause in DESIGN_AND_DEVELOPMENT_SUBCLAUSES:
            expected_id = f"QMS-{subclause.replace('.', '-')}"
            assert expected_id in control_ids, f"Missing D&D control: {expected_id}"

    def test_clause_84_subclauses_all_present(self) -> None:
        """All 3 external provider subclauses (8.4.1–8.4.3) must be in the pack."""
        control_ids = {c.identifier for c in ISO_9001_PACK.controls}
        for subclause in EXTERNAL_PROVIDER_SUBCLAUSES:
            expected_id = f"QMS-{subclause.replace('.', '-')}"
            assert expected_id in control_ids, f"Missing external provider control: {expected_id}"


# =============================================================================
# 2. Coverage ledger completeness
# =============================================================================


class TestISO9001CoverageCompleteness:
    def test_source_requirements_match_controls(self) -> None:
        assert len(ISO_9001_PACK.source_requirements) == len(ISO_9001_PACK.controls)

    def test_coverage_ledger_matches_source_requirements(self) -> None:
        req_refs = {r.source_reference for r in ISO_9001_PACK.source_requirements}
        ledger_refs = {e.source_reference for e in ISO_9001_PACK.coverage_ledger}
        assert req_refs == ledger_refs, (
            f"Ledger mismatch. Missing: {req_refs - ledger_refs}. Extra: {ledger_refs - req_refs}"
        )

    def test_all_coverage_ledger_entries_implemented(self) -> None:
        from conformly.frameworks.models import CoverageDisposition

        for entry in ISO_9001_PACK.coverage_ledger:
            assert entry.disposition == CoverageDisposition.IMPLEMENTED, (
                f"Source requirement {entry.source_reference!r} has disposition "
                f"{entry.disposition!r}, expected IMPLEMENTED."
            )

    def test_mappings_reference_valid_controls_and_reqs(self) -> None:
        ctrl_ids = {c.identifier for c in ISO_9001_PACK.controls}
        req_refs = {r.source_reference for r in ISO_9001_PACK.source_requirements}
        for m in ISO_9001_PACK.mappings:
            assert m.control_identifier in ctrl_ids, (
                f"Mapping references unknown control: {m.control_identifier}"
            )
            assert m.source_reference in req_refs, (
                f"Mapping references unknown source requirement: {m.source_reference}"
            )

    def test_evidence_specifications_reference_valid_controls(self) -> None:
        ctrl_ids = {c.identifier for c in ISO_9001_PACK.controls}
        for evid in ISO_9001_PACK.evidence_specifications:
            if evid.control_identifier:
                assert evid.control_identifier in ctrl_ids, (
                    f"Evidence spec {evid.identifier!r} references unknown control: {evid.control_identifier}"
                )

    def test_evidence_identifiers_are_unique(self) -> None:
        ids = [e.identifier for e in ISO_9001_PACK.evidence_specifications]
        assert len(ids) == len(set(ids)), (
            f"Duplicate evidence identifiers: {set(i for i in ids if ids.count(i) > 1)}"
        )

    def test_source_requirements_have_required_metadata(self) -> None:
        for req in ISO_9001_PACK.source_requirements:
            assert req.source_authority, f"Empty source_authority: {req.source_reference}"
            assert req.edition_or_amendment, f"Empty edition: {req.source_reference}"
            assert req.content_rights, f"Empty content_rights: {req.source_reference}"
            assert req.source_url, f"Empty source_url: {req.source_reference}"
            assert req.default_owner_role, f"Empty default_owner_role: {req.source_reference}"


# =============================================================================
# 3. Applicability engine — QMS-specific rules
# =============================================================================


class TestISO9001ApplicabilityEngine:
    """Deterministic applicability evaluation rules for ISO 9001 QMS controls."""

    def _get_dd_control(self) -> CanonicalControl:
        """Return a stub CanonicalControl for a D&D subclause (8.3.1)."""
        # Use a simple mock-like object to exercise evaluate_control_applicability
        from unittest.mock import MagicMock

        ctrl = MagicMock(spec=CanonicalControl)
        ctrl.identifier = "QMS-8-3-1"
        return ctrl

    def _get_ep_control(self) -> CanonicalControl:
        from unittest.mock import MagicMock

        ctrl = MagicMock(spec=CanonicalControl)
        ctrl.identifier = "QMS-8-4-2"
        return ctrl

    def _get_pd_control(self) -> CanonicalControl:
        from unittest.mock import MagicMock

        ctrl = MagicMock(spec=CanonicalControl)
        ctrl.identifier = "QMS-8-5-5"
        return ctrl

    def _get_standard_control(self) -> CanonicalControl:
        from unittest.mock import MagicMock

        ctrl = MagicMock(spec=CanonicalControl)
        ctrl.identifier = "QMS-4-1"
        return ctrl

    # ── D&D Controls (Rule 9) ───────────────────────────────────────────────

    def test_dd_control_not_applicable_when_no_dd(
        self, qms_profile_no_dd_with_ep: TenantProfileContext
    ) -> None:
        ctrl = self._get_dd_control()
        result = evaluate_control_applicability(ctrl, qms_profile_no_dd_with_ep)
        assert result.applicability == OverlayApplicability.NOT_APPLICABLE
        assert "design" in result.justification.lower()

    def test_dd_control_applicable_when_dd_enabled(
        self, qms_profile_with_dd_and_ep: TenantProfileContext
    ) -> None:
        ctrl = self._get_dd_control()
        result = evaluate_control_applicability(ctrl, qms_profile_with_dd_and_ep)
        assert result.applicability == OverlayApplicability.APPLICABLE

    def test_dd_control_review_required_when_dd_unknown(
        self, qms_profile_unknown_dd: TenantProfileContext
    ) -> None:
        ctrl = self._get_dd_control()
        result = evaluate_control_applicability(ctrl, qms_profile_unknown_dd)
        assert result.applicability == OverlayApplicability.REVIEW_REQUIRED

    def test_all_dd_subclauses_excluded_when_no_dd(
        self, qms_profile_no_dd_with_ep: TenantProfileContext
    ) -> None:
        """All 6 D&D clause controls must be NOT_APPLICABLE for a non-D&D org."""
        from unittest.mock import MagicMock

        for subclause in DESIGN_AND_DEVELOPMENT_SUBCLAUSES:
            ctrl = MagicMock(spec=CanonicalControl)
            ctrl.identifier = f"QMS-{subclause.replace('.', '-')}"
            result = evaluate_control_applicability(ctrl, qms_profile_no_dd_with_ep)
            assert result.applicability == OverlayApplicability.NOT_APPLICABLE, (
                f"Expected NOT_APPLICABLE for {ctrl.identifier} but got {result.applicability}"
            )

    # ── External Provider Controls (Rule 10) ───────────────────────────────

    def test_ep_control_not_applicable_when_no_ep(
        self, qms_profile_no_ep: TenantProfileContext
    ) -> None:
        ctrl = self._get_ep_control()
        result = evaluate_control_applicability(ctrl, qms_profile_no_ep)
        assert result.applicability == OverlayApplicability.NOT_APPLICABLE
        assert "external provider" in result.justification.lower()

    def test_ep_control_applicable_when_ep_present(
        self, qms_profile_with_dd_and_ep: TenantProfileContext
    ) -> None:
        ctrl = self._get_ep_control()
        result = evaluate_control_applicability(ctrl, qms_profile_with_dd_and_ep)
        assert result.applicability == OverlayApplicability.APPLICABLE

    def test_ep_control_review_required_when_ep_unknown(self) -> None:
        profile = TenantProfileContext(has_external_providers=None)
        ctrl = self._get_ep_control()
        result = evaluate_control_applicability(ctrl, profile)
        assert result.applicability == OverlayApplicability.REVIEW_REQUIRED

    def test_all_ep_subclauses_excluded_when_no_ep(
        self, qms_profile_no_ep: TenantProfileContext
    ) -> None:
        """All 3 Clause 8.4 controls must be NOT_APPLICABLE for a no-EP org."""
        from unittest.mock import MagicMock

        for subclause in EXTERNAL_PROVIDER_SUBCLAUSES:
            ctrl = MagicMock(spec=CanonicalControl)
            ctrl.identifier = f"QMS-{subclause.replace('.', '-')}"
            result = evaluate_control_applicability(ctrl, qms_profile_no_ep)
            assert result.applicability == OverlayApplicability.NOT_APPLICABLE, (
                f"Expected NOT_APPLICABLE for {ctrl.identifier} but got {result.applicability}"
            )

    # ── Post-Delivery Controls (Rule 11) ───────────────────────────────────

    def test_pd_control_not_applicable_when_no_pd(
        self, qms_profile_no_dd_with_ep: TenantProfileContext
    ) -> None:
        ctrl = self._get_pd_control()
        result = evaluate_control_applicability(ctrl, qms_profile_no_dd_with_ep)
        assert result.applicability == OverlayApplicability.NOT_APPLICABLE

    def test_pd_control_applicable_when_pd_present(
        self, qms_profile_with_dd_and_ep: TenantProfileContext
    ) -> None:
        ctrl = self._get_pd_control()
        result = evaluate_control_applicability(ctrl, qms_profile_with_dd_and_ep)
        assert result.applicability == OverlayApplicability.APPLICABLE

    def test_pd_control_review_required_when_pd_unknown(
        self, qms_profile_unknown_dd: TenantProfileContext
    ) -> None:
        ctrl = self._get_pd_control()
        result = evaluate_control_applicability(ctrl, qms_profile_unknown_dd)
        assert result.applicability == OverlayApplicability.REVIEW_REQUIRED

    # ── Standard controls fall through to default APPLICABLE ────────────────

    def test_standard_qms_control_is_applicable_by_default(
        self, qms_profile_no_dd_with_ep: TenantProfileContext
    ) -> None:
        ctrl = self._get_standard_control()
        result = evaluate_control_applicability(ctrl, qms_profile_no_dd_with_ep)
        assert result.applicability == OverlayApplicability.APPLICABLE


# =============================================================================
# 4. Manifest consistency
# =============================================================================


class TestISO9001ManifestConsistency:
    def test_iso_9001_required_for_beta(self) -> None:
        """ISO 9001 must be in the REQUIRED_BETA set returned by the manifest reader."""
        req_ids = get_required_beta_pack_ids()
        assert "iso-9001" in req_ids, f"iso-9001 not found in required beta packs: {req_ids}"

    def test_six_packs_required_for_beta(self) -> None:
        """Exactly 6 packs must be flagged as REQUIRED_BETA."""
        req_ids = get_required_beta_pack_ids()
        assert len(req_ids) == 6, f"Expected 6 required_beta packs, got {len(req_ids)}: {req_ids}"

    def test_tier_a_packs_list_has_six_entries(self) -> None:
        """TIER_A_FRAMEWORK_PACKS must contain exactly 6 pack definitions."""
        assert len(TIER_A_FRAMEWORK_PACKS) == 6

    def test_iso_9001_in_tier_a_packs(self) -> None:
        slugs = {p.slug for p in TIER_A_FRAMEWORK_PACKS}
        assert "iso-9001" in slugs, f"iso-9001 not found in TIER_A_PACKS slugs: {slugs}"


# =============================================================================
# 5. Database seeding — 6-pack Tier A
# =============================================================================


class TestISO9001Seeding:
    def test_seed_tier_a_test_fixtures_returns_six_packs(self, session: Session) -> None:
        """seed_tier_a_test_fixtures must return exactly 6 RELEASED versions."""
        versions = seed_tier_a_test_fixtures(session)
        assert len(versions) == 6

    def test_iso_9001_pack_is_seeded(self, session: Session) -> None:
        """ISO 9001 framework and version must be present after seeding."""
        seed_tier_a_test_fixtures(session)
        fw = session.scalar(select(Framework).where(Framework.slug == "iso-9001"))
        assert fw is not None, "iso-9001 Framework not found in DB after seeding."
        version = session.scalar(
            select(FrameworkVersion).where(FrameworkVersion.framework_id == fw.id)
        )
        assert version is not None
        assert version.version == "v2015"
        assert version.release_state == ReleaseState.RELEASED

    def test_iso_9001_controls_seeded_correctly(self, session: Session) -> None:
        """Seeded ISO 9001 version must have all expected controls populated."""
        seed_tier_a_test_fixtures(session)
        fw = session.scalar(select(Framework).where(Framework.slug == "iso-9001"))
        assert fw is not None
        version = session.scalar(
            select(FrameworkVersion).where(FrameworkVersion.framework_id == fw.id)
        )
        assert version is not None
        # Must have at least 50 controls
        assert len(version.controls) >= 50
        # Verify 2-person separation invariant
        assert version.created_by_user_id == AUTHOR_USER_ID
        assert version.approved_by_user_id == APPROVER_USER_ID
        assert version.created_by_user_id != version.approved_by_user_id

    def test_iso_9001_seeding_is_idempotent(self, session: Session) -> None:
        """Running seed twice must not create duplicate frameworks or versions."""
        versions1 = seed_tier_a_test_fixtures(session)
        versions2 = seed_tier_a_test_fixtures(session)
        assert len(versions1) == len(versions2) == 6
        # Check for exactly one iso-9001 framework in DB
        frameworks = session.scalars(select(Framework).where(Framework.slug == "iso-9001")).all()
        assert len(frameworks) == 1

    def test_six_frameworks_total_after_seeding(self, session: Session) -> None:
        """Exactly 6 frameworks must exist in the DB after Tier A seeding."""
        seed_tier_a_test_fixtures(session)
        all_frameworks = session.scalars(select(Framework)).all()
        assert len(all_frameworks) == 6


# =============================================================================
# 6. Immutability — released ISO 9001 version blocks mutations
# =============================================================================


class TestISO9001Immutability:
    def test_released_iso9001_blocks_control_addition(self, session: Session) -> None:
        """Adding a canonical control to a released ISO 9001 version must raise ImmutableCanonicalVersionError."""
        seed_tier_a_test_fixtures(session)

        fw = session.scalar(select(Framework).where(Framework.slug == "iso-9001"))
        assert fw is not None
        version = session.scalar(
            select(FrameworkVersion).where(FrameworkVersion.framework_id == fw.id)
        )
        assert version is not None
        assert version.release_state == ReleaseState.RELEASED

        author = Principal(user_id=AUTHOR_USER_ID, is_platform_admin=True, mfa_verified=True)
        service = FrameworkService(session)

        with pytest.raises(ImmutableCanonicalVersionError):
            service.add_canonical_control(
                author,
                version.id,
                "QMS-TAMPER-99",
                "Tampered Control",
                "Illegal post-release edit to ISO 9001",
                "Testing",
                None,
                9999,
                "req-tamper",
            )
