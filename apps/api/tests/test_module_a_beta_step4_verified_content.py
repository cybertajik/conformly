"""Module A Beta Step 4 Test Suite: Complete Source-Verified Framework Content.

Validates:
- 4A: ISO/IEC 27001:2022 ISMS Clauses 4-10 and Annex A themes (A.5, A.6, A.7, A.8) with SoA support
- 4B: EU GDPR & German BDSG with Controller/Processor duties and authority disposition in ledger
- 4C: NIST CSF 2.0 Core Functions (GV, ID, PR, DE, RS, RC) and categories
- 4D: CIS Controls v8 IG1: Exactly 56 official IG1 safeguards verified against independent inventory
- 4E: MVSP v2.0: All 24 checklist items with CC-BY-4.0 attribution and cloud responsibility
- 4F: Reviewable draft definitions for OWNER_DECISION_REQUIRED candidate frameworks
"""

from uuid import uuid4

from sqlalchemy.orm import Session

from conformly.authz.policy import Principal
from conformly.frameworks.models import (
    CoverageDisposition,
    ReleaseState,
)
from conformly.frameworks.packs_data import (
    CIS_CONTROLS_IG1_PACK,
    GDPR_BDSG_PACK,
    ISO_9001_PACK,
    ISO_27001_PACK,
    MVSP_PACK,
    NIST_CSF_PACK,
    OWNER_DECISION_DRAFT_PACKS,
)
from conformly.frameworks.seed_packs import (
    import_framework_pack_draft,
    seed_tier_a_test_fixtures,
)
from conformly.frameworks.service import FrameworkService

# Official independent inventory of the 56 CIS v8 IG1 safeguards
EXPECTED_CIS_V8_IG1_SAFEGUARDS = {
    "1.1",
    "1.2",
    "2.1",
    "2.2",
    "2.3",
    "3.1",
    "3.2",
    "3.3",
    "3.4",
    "3.5",
    "3.6",
    "4.1",
    "4.2",
    "4.3",
    "4.4",
    "4.5",
    "4.6",
    "4.7",
    "5.1",
    "5.2",
    "5.3",
    "5.4",
    "6.1",
    "6.2",
    "6.3",
    "6.4",
    "6.5",
    "7.1",
    "7.2",
    "7.3",
    "7.4",
    "8.1",
    "8.2",
    "8.3",
    "9.1",
    "9.2",
    "10.1",
    "10.2",
    "10.3",
    "11.1",
    "11.2",
    "11.3",
    "11.4",
    "12.1",
    "14.1",
    "14.2",
    "14.3",
    "14.4",
    "14.5",
    "14.6",
    "15.1",
    "16.1",
    "16.2",
    "17.1",
    "17.2",
    "17.3",
}


def test_iso_27001_source_verified_content(session: Session) -> None:
    """4A: ISO 27001:2022 covers Clauses 4-10 and Annex A themes with SoA and 100% ledger coverage."""
    service = FrameworkService(session)
    author = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)

    version = import_framework_pack_draft(service, ISO_27001_PACK, author, "req-iso-test")

    # 1. Management clauses verification (Clauses 4 through 10)
    req_refs = {r.source_reference for r in version.source_requirements}
    assert "ISO/IEC 27001:2022 Clause 4.1" in req_refs
    assert "ISO/IEC 27001:2022 Clause 4.3" in req_refs
    assert "ISO/IEC 27001:2022 Clause 5.1" in req_refs
    assert "ISO/IEC 27001:2022 Clause 6.1.2" in req_refs
    assert "ISO/IEC 27001:2022 Clause 6.1.3" in req_refs  # SoA clause
    assert "ISO/IEC 27001:2022 Clause 9.2.1" in req_refs  # Internal audit
    assert "ISO/IEC 27001:2022 Clause 9.3.1" in req_refs  # Management review
    assert "ISO/IEC 27001:2022 Clause 10.1" in req_refs

    # 2. Annex A reference controls across all 4 themes
    assert "ISO/IEC 27001:2022 Annex A.5.1" in req_refs  # Organizational
    assert "ISO/IEC 27001:2022 Annex A.6.1" in req_refs  # People
    assert "ISO/IEC 27001:2022 Annex A.7.1" in req_refs  # Physical
    assert "ISO/IEC 27001:2022 Annex A.8.1" in req_refs  # Technological

    # 3. Verify total requirement count
    assert len(version.source_requirements) == 123
    assert len(version.controls) == 123
    assert len(version.requirement_control_mappings) == 123

    # 4. Coverage ledger validation report
    report = service.validate_coverage_ledger(version.id)
    assert report.is_valid
    assert report.total_requirements == 123
    assert report.accounted_requirements == 123
    assert report.unaccounted_count == 0
    assert len(report.blocked_references) == 0
    assert report.disposition_summary.get(CoverageDisposition.IMPLEMENTED) == 123


def test_gdpr_bdsg_statutory_inventory_and_authority_disposition(session: Session) -> None:
    """4B: GDPR & BDSG covers Articles 5-49, BDSG § 26/§ 38, and marks authority articles NOT_CUSTOMER_OBLIGATION."""
    service = FrameworkService(session)
    author = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)

    version = import_framework_pack_draft(service, GDPR_BDSG_PACK, author, "req-gdpr-test")

    req_refs = {r.source_reference: r for r in version.source_requirements}

    # 1. Principles & Rights
    assert "Regulation (EU) 2016/679 Art 5 1 a" in req_refs
    assert "Regulation (EU) 2016/679 Art 6" in req_refs
    assert "Regulation (EU) 2016/679 Art 15" in req_refs  # Access
    assert "Regulation (EU) 2016/679 Art 17" in req_refs  # Erasure
    assert "Regulation (EU) 2016/679 Art 20" in req_refs  # Portability

    # 2. Operational Obligations (VVT, TOMs, Breach, DPIA, DPO)
    assert "Regulation (EU) 2016/679 Art 28" in req_refs  # DPA
    assert "Regulation (EU) 2016/679 Art 30" in req_refs  # VVT
    assert "Regulation (EU) 2016/679 Art 32" in req_refs  # TOMs
    assert "Regulation (EU) 2016/679 Art 33" in req_refs  # Breach
    assert "Regulation (EU) 2016/679 Art 35" in req_refs  # DPIA
    assert "Regulation (EU) 2016/679 Art 37" in req_refs  # DPO

    # 3. German BDSG Specifics
    assert "BDSG § 22" in req_refs
    assert "BDSG § 26" in req_refs
    assert "BDSG § 38" in req_refs

    # 4. Authority Provisions (Articles 51, 52, 57, 58, 60-76, 85-99)
    assert "Regulation (EU) 2016/679 Art 51" in req_refs
    assert "Regulation (EU) 2016/679 Art 58" in req_refs
    assert "Regulation (EU) 2016/679 Art 60 76" in req_refs

    # 5. Coverage Ledger verification: Authority articles are NOT_CUSTOMER_OBLIGATION
    report = service.validate_coverage_ledger(version.id)
    assert report.is_valid
    assert report.total_requirements == 56
    assert report.accounted_requirements == 56
    assert report.unaccounted_count == 0
    assert report.disposition_summary.get(CoverageDisposition.IMPLEMENTED) == 45
    assert report.disposition_summary.get(CoverageDisposition.NOT_CUSTOMER_OBLIGATION) == 11


def test_nist_csf_core_functions_and_categories(session: Session) -> None:
    """4C: NIST CSF 2.0 covers all 6 Core Functions and official categories with structured evidence."""
    service = FrameworkService(session)
    author = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)

    version = import_framework_pack_draft(service, NIST_CSF_PACK, author, "req-nist-test")

    # Verify functions are represented across controls
    categories = {c.category for c in version.controls}
    assert any("Govern" in c for c in categories)
    assert any("Identify" in c for c in categories)
    assert any("Protect" in c for c in categories)
    assert any("Detect" in c for c in categories)
    assert any("Respond" in c for c in categories)
    assert any("Recover" in c for c in categories)

    # Verify exhaustive 106 official NIST CSF 2.0 subcategories
    assert len(version.controls) == 106
    ctrl_ids = {c.identifier for c in version.controls}
    ctrl_map = {c.identifier: c for c in version.controls}

    # Verify key subcategories across all 6 Core Functions
    assert "NIST-GV-OC-01" in ctrl_ids
    assert "NIST-GV-OC-02" in ctrl_ids
    assert "NIST-GV-OC-03" in ctrl_ids
    assert "NIST-ID-AM-01" in ctrl_ids
    assert "NIST-PR-AA-03" in ctrl_ids  # MFA
    assert "NIST-DE-CM-01" in ctrl_ids
    assert "NIST-RS-MA-01" in ctrl_ids
    assert "NIST-RC-RP-01" in ctrl_ids

    # Verify authoritative distinction between GV.OC-02 (stakeholders) and GV.OC-03 (legal/regulatory)
    assert "stakeholder" in ctrl_map["NIST-GV-OC-02"].description.lower()
    assert "legal, regulatory, and contractual" in ctrl_map["NIST-GV-OC-03"].description.lower()
    assert "privacy and civil liberties" in ctrl_map["NIST-GV-OC-03"].description.lower()

    # Verify coverage ledger is 100% accounted for
    report = service.validate_coverage_ledger(version.id)
    assert report.is_valid
    assert report.total_requirements == 106
    assert report.unaccounted_count == 0


def test_cis_controls_v8_ig1_exact_56_safeguards(session: Session) -> None:
    """4D: CIS IG1 covers all 56 official IG1 safeguards verified against independent inventory."""
    service = FrameworkService(session)
    author = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)

    version = import_framework_pack_draft(service, CIS_CONTROLS_IG1_PACK, author, "req-cis-test")

    # Extract all safeguard IDs from canonical controls
    actual_safeguard_ids = {c.identifier.replace("CIS-", "") for c in version.controls}

    # Assert exact match against official independent set of 56 safeguards
    assert actual_safeguard_ids == EXPECTED_CIS_V8_IG1_SAFEGUARDS
    assert len(actual_safeguard_ids) == 56

    # Verify that enterprise-only safeguards are accounted for as PROFILE_EXCLUSION in ledger
    report = service.validate_coverage_ledger(version.id)
    assert report.is_valid
    assert report.total_requirements == 77
    assert report.accounted_requirements == 77
    assert report.disposition_summary.get(CoverageDisposition.IMPLEMENTED) == 56
    assert report.disposition_summary.get(CoverageDisposition.PROFILE_EXCLUSION) == 21


def test_mvsp_v2_full_checklist_and_attribution(session: Session) -> None:
    """4E: MVSP v2.0 covers all 24 checklist items with open CC-BY-4.0 attribution."""
    service = FrameworkService(session)
    author = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)

    version = import_framework_pack_draft(service, MVSP_PACK, author, "req-mvsp-test")

    assert len(version.controls) == 24
    assert len(version.source_requirements) == 24

    # Verify domains
    categories = {c.category for c in version.controls}
    assert "Business Security" in categories
    assert "Application Security" in categories
    assert "Operational Security" in categories

    # Verify licensing attribution in source requirements
    for req in version.source_requirements:
        assert "CC-BY-4.0" in req.content_rights
        assert "mvsp.dev" in req.content_rights

    # Verify coverage ledger
    report = service.validate_coverage_ledger(version.id)
    assert report.is_valid
    assert report.total_requirements == 24
    assert report.disposition_summary.get(CoverageDisposition.IMPLEMENTED) == 24


def test_owner_decision_draft_framework_packs(session: Session) -> None:
    """Regional candidates remain drafts; ISO 9001 belongs to the six-pack batch."""
    service = FrameworkService(session)
    author = Principal(user_id=uuid4(), is_platform_admin=True, mfa_verified=True)

    assert len(OWNER_DECISION_DRAFT_PACKS) == 4
    draft_slugs = {p.slug for p in OWNER_DECISION_DRAFT_PACKS}
    assert draft_slugs == {
        "us-ca-ccpa-cpra",
        "sa-pdpl",
        "jp-appi",
        "au-privacy-act",
    }

    # Verify ISO 9001 quality management drafting
    iso_9001 = ISO_9001_PACK
    v_9001 = import_framework_pack_draft(service, iso_9001, author, "req-draft-9001")
    assert v_9001.release_state == ReleaseState.DRAFT
    assert len(v_9001.controls) >= 16
    assert any("Customer Focus" in c.title for c in v_9001.controls)

    # Verify CCPA drafting
    ccpa = next(p for p in OWNER_DECISION_DRAFT_PACKS if p.slug == "us-ca-ccpa-cpra")
    v_ccpa = import_framework_pack_draft(service, ccpa, author, "req-draft-ccpa")
    assert v_ccpa.release_state == ReleaseState.DRAFT
    assert any("Opt-Out" in c.title for c in v_ccpa.controls)

    # Verify SA PDPL drafting
    sa_pdpl = next(p for p in OWNER_DECISION_DRAFT_PACKS if p.slug == "sa-pdpl")
    v_sa = import_framework_pack_draft(service, sa_pdpl, author, "req-draft-sa")
    assert v_sa.release_state == ReleaseState.DRAFT

    # Verify JP APPI drafting
    jp_appi = next(p for p in OWNER_DECISION_DRAFT_PACKS if p.slug == "jp-appi")
    v_jp = import_framework_pack_draft(service, jp_appi, author, "req-draft-jp")
    assert v_jp.release_state == ReleaseState.DRAFT

    # Verify AU Privacy Act drafting
    au_app = next(p for p in OWNER_DECISION_DRAFT_PACKS if p.slug == "au-privacy-act")
    v_au = import_framework_pack_draft(service, au_app, author, "req-draft-au")
    assert v_au.release_state == ReleaseState.DRAFT


def test_seed_tier_a_framework_packs_complete_lifecycle(session: Session) -> None:
    """Verify complete release lifecycle for all six beta packs with valid ledgers."""
    released = seed_tier_a_test_fixtures(session)
    assert len(released) == 6

    service = FrameworkService(session)
    for v in released:
        assert v.release_state == ReleaseState.RELEASED
        report = service.validate_coverage_ledger(v.id)
        assert report.is_valid
        assert report.unaccounted_count == 0
        assert len(report.blocked_references) == 0
