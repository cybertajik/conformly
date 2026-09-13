from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conformly.authz.policy import Principal
from conformly.frameworks.models import (
    CoverageDisposition,
    MappingType,
    ReleaseState,
    SourceRequirementType,
)
from conformly.frameworks.service import (
    CoverageLedgerError,
    FrameworkService,
    InvalidCoverageMappingError,
    ReleaseBlockedError,
    SourceRequirementNotFoundError,
    compute_version_content_digest,
)
from conformly.identity.models import User, UserStatus


@pytest.fixture
def test_principals(session: Session) -> dict[str, Principal]:
    author = User(
        oidc_issuer="https://id.example.com",
        oidc_subject=f"sub-{uuid4()}",
        email="schema_author@example.com",
        display_name="Schema Author",
        is_platform_admin=True,
        status=UserStatus.ACTIVE,
    )
    legal = User(
        oidc_issuer="https://id.example.com",
        oidc_subject=f"sub-{uuid4()}",
        email="schema_legal@example.com",
        display_name="Legal Reviewer",
        is_platform_admin=True,
        status=UserStatus.ACTIVE,
    )
    approver = User(
        oidc_issuer="https://id.example.com",
        oidc_subject=f"sub-{uuid4()}",
        email="schema_approver@example.com",
        display_name="Second Approver",
        is_platform_admin=True,
        status=UserStatus.ACTIVE,
    )
    session.add_all([author, legal, approver])
    session.flush()

    return {
        "author": Principal(
            user_id=author.id,
            is_platform_admin=True,
            mfa_verified=True,
        ),
        "legal": Principal(
            user_id=legal.id,
            is_platform_admin=True,
            mfa_verified=True,
        ),
        "approver": Principal(
            user_id=approver.id,
            is_platform_admin=True,
            mfa_verified=True,
        ),
    }


def test_source_requirement_traceability_and_provenance(
    session: Session, test_principals: dict[str, Principal]
) -> None:
    service = FrameworkService(session)
    author = test_principals["author"]

    fw = service.create_framework(author, "ISO 27001", "iso-27001-trace", "ISMS", "req-1")
    v = service.create_version_draft(author, fw.id, "2022", "Draft edition", "req-2")

    retrieval_dt = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    req = service.add_source_requirement(
        principal=author,
        version_id=v.id,
        source_reference="Clause 4.1",
        title="Understanding the organization and its context",
        source_text="The organization shall determine external and internal issues relevant to its purpose.",
        source_authority="ISO/IEC",
        edition_or_amendment="ISO/IEC 27001:2022",
        content_rights="Fair use / functional index under compliance research terms",
        request_id="req-3",
        requirement_type=SourceRequirementType.CLAUSE,
        source_url="https://www.iso.org/standard/27001",
        retrieval_date=retrieval_dt,
        language="en",
        effective_date="2022-10-25",
        permitted_use="Commercial compliance tracking and assessment indexing",
        conformly_guidance="Maintain an organizational context register reviewed annually by leadership.",
        suggested_operating_targets={
            "annual_context_review": True,
            "target_type": "suggested_guideline",
            "statutory_mandate": False,
        },
        assessment_procedure="Inspect leadership minutes and context register for external/internal issues.",
        default_owner_role="Compliance Officer",
        review_cadence="annual",
        applicability_conditions={"all_tenants": True},
        reporting_limitations="Readiness observation only; not an official accredited certification.",
        sort_order=10,
    )

    assert req.id is not None
    assert req.source_reference == "Clause 4.1"
    assert req.requirement_type == SourceRequirementType.CLAUSE
    assert req.source_authority == "ISO/IEC"
    assert req.source_url == "https://www.iso.org/standard/27001"
    assert req.retrieval_date == retrieval_dt
    assert req.suggested_operating_targets is not None
    assert req.suggested_operating_targets["statutory_mandate"] is False

    # Unique constraint check on (framework_version_id, source_reference)
    with pytest.raises(IntegrityError):
        service.add_source_requirement(
            principal=author,
            version_id=v.id,
            source_reference="Clause 4.1",
            title="Duplicate reference",
            source_text="Duplicate",
            source_authority="ISO/IEC",
            edition_or_amendment="2022",
            content_rights="Fair use",
            request_id="req-dup",
        )
    session.rollback()


def test_versioned_requirement_control_mappings(
    session: Session, test_principals: dict[str, Principal]
) -> None:
    service = FrameworkService(session)
    author = test_principals["author"]

    fw = service.create_framework(author, "NIST CSF", "nist-csf-trace", "Cybersecurity", "req-1")
    v = service.create_version_draft(author, fw.id, "2.0", "Draft v2.0", "req-2")

    # Add 2 source requirements
    req1 = service.add_source_requirement(
        principal=author,
        version_id=v.id,
        source_reference="GV.OC-01",
        title="Organizational Context",
        source_text="The organizational mission is understood and informs cybersecurity.",
        source_authority="NIST",
        edition_or_amendment="NIST CSF 2.0",
        content_rights="Public Domain / U.S. Government Work",
        request_id="req-r1",
        requirement_type=SourceRequirementType.OUTCOME,
    )
    req2 = service.add_source_requirement(
        principal=author,
        version_id=v.id,
        source_reference="PR.AA-01",
        title="Identity & Access Management",
        source_text="Identities and credentials for authorized users are managed.",
        source_authority="NIST",
        edition_or_amendment="NIST CSF 2.0",
        content_rights="Public Domain / U.S. Government Work",
        request_id="req-r2",
        requirement_type=SourceRequirementType.OUTCOME,
    )

    # Add 2 canonical controls
    ctrl1 = service.add_canonical_control(
        principal=author,
        version_id=v.id,
        identifier="NIST-GV-01",
        title="Context & Mission Alignment",
        description="Align security roadmap to mission objectives.",
        category="GOVERN",
        guidance="Conduct annual stakeholder alignment.",
        sort_order=1,
        request_id="req-c1",
    )
    ctrl2 = service.add_canonical_control(
        principal=author,
        version_id=v.id,
        identifier="NIST-PR-01",
        title="Centralized Access Control",
        description="Enforce RBAC and MFA across critical services.",
        category="PROTECT",
        guidance="Use IdP with WebAuthn/TOTP.",
        sort_order=2,
        request_id="req-c2",
    )

    # Map them
    map1 = service.add_requirement_control_mapping(
        principal=author,
        version_id=v.id,
        source_requirement_id=req1.id,
        canonical_control_id=ctrl1.id,
        mapping_type=MappingType.SATISFIES,
        request_id="req-m1",
        rationale="NIST-GV-01 establishes mission-aligned context documentation.",
    )
    map2 = service.add_requirement_control_mapping(
        principal=author,
        version_id=v.id,
        source_requirement_id=req2.id,
        canonical_control_id=ctrl2.id,
        mapping_type=MappingType.SATISFIES,
        request_id="req-m2",
        rationale="NIST-PR-01 implements identity and access controls.",
    )

    assert map1.mapping_type == MappingType.SATISFIES
    assert map2.mapping_type == MappingType.SATISFIES

    # Cross-version isolation: attempt mapping to a control in another version
    v_other = service.create_version_draft(author, fw.id, "3.0-draft", "Other draft", "req-v3")
    with pytest.raises(SourceRequirementNotFoundError):
        service.add_requirement_control_mapping(
            principal=author,
            version_id=v_other.id,
            source_requirement_id=req1.id,  # belongs to v, not v_other
            canonical_control_id=ctrl1.id,
            mapping_type=MappingType.SATISFIES,
            request_id="req-m-bad",
        )


def test_structured_evidence_specifications(
    session: Session, test_principals: dict[str, Principal]
) -> None:
    service = FrameworkService(session)
    author = test_principals["author"]

    fw = service.create_framework(author, "CIS Controls", "cis-controls-trace", "IG1", "req-1")
    v = service.create_version_draft(author, fw.id, "v8-ig1", "Draft IG1", "req-2")

    req = service.add_source_requirement(
        principal=author,
        version_id=v.id,
        source_reference="1.1",
        title="Establish and Maintain a Detailed Enterprise Asset Inventory",
        source_text="Establish and maintain an accurate, detailed, and up-to-date inventory of all enterprise assets.",
        source_authority="Center for Internet Security",
        edition_or_amendment="CIS Controls v8",
        content_rights="Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International",
        request_id="req-cis-1",
        requirement_type=SourceRequirementType.SAFEGUARD,
    )
    ctrl = service.add_canonical_control(
        principal=author,
        version_id=v.id,
        identifier="CIS-1.1",
        title="Enterprise Asset Inventory System",
        description="Automated hardware and cloud asset inventory.",
        category="Inventory",
        guidance="Run discovery weekly.",
        sort_order=1,
        request_id="req-cis-ctrl",
    )

    spec = service.add_evidence_specification(
        principal=author,
        version_id=v.id,
        identifier="EVID-CIS-1.1-EXPORT",
        title="Monthly Asset Inventory Export",
        description="Original CSV/JSON export from the asset management database or cloud inventory.",
        evidence_type="configuration_export",
        request_id="req-spec-1",
        canonical_control_id=ctrl.id,
        source_requirement_id=req.id,
        original_file_required=True,
        observation_period_days=30,
        validity_period_days=90,
        review_cadence_days=30,
        confidentiality_level="Confidential",
        suggested_storage_format="text/csv",
    )

    assert spec.id is not None
    assert spec.identifier == "EVID-CIS-1.1-EXPORT"
    assert spec.original_file_required is True
    assert spec.observation_period_days == 30
    assert spec.validity_period_days == 90
    assert spec.review_cadence_days == 30
    assert spec.confidentiality_level == "Confidential"
    assert spec.suggested_storage_format == "text/csv"


def test_coverage_ledger_dispositions_and_rationales(
    session: Session, test_principals: dict[str, Principal]
) -> None:
    service = FrameworkService(session)
    author = test_principals["author"]

    fw = service.create_framework(author, "GDPR & BDSG", "gdpr-bdsg-trace", "EU Privacy", "req-1")
    v = service.create_version_draft(author, fw.id, "2016-679", "GDPR Draft", "req-2")

    # 1. Statutory controller obligation: Art 30 Records of Processing
    req_art30 = service.add_source_requirement(
        principal=author,
        version_id=v.id,
        source_reference="Art. 30(1)",
        title="Records of processing activities - Controller",
        source_text="Each controller shall maintain a record of processing activities under its responsibility.",
        source_authority="European Parliament & Council",
        edition_or_amendment="Regulation (EU) 2016/679",
        content_rights="EU Official Journal - Public / Crown Copyright Equivalent",
        request_id="req-art30",
        requirement_type=SourceRequirementType.ARTICLE,
    )

    # 2. Supervisory authority obligation: Art 57 Tasks of Supervisory Authority
    req_art57 = service.add_source_requirement(
        principal=author,
        version_id=v.id,
        source_reference="Art. 57(1)",
        title="Tasks of the Supervisory Authority",
        source_text="Each supervisory authority shall on its territory monitor and enforce GDPR application.",
        source_authority="European Parliament & Council",
        edition_or_amendment="Regulation (EU) 2016/679",
        content_rights="EU Official Journal - Public / Crown Copyright Equivalent",
        request_id="req-art57",
        requirement_type=SourceRequirementType.ARTICLE,
    )

    # 3. Scope profile exclusion: BDSG Section 38 (DPO appointment trigger for small micro-entities)
    req_bdsg38 = service.add_source_requirement(
        principal=author,
        version_id=v.id,
        source_reference="BDSG § 38(1)",
        title="Data Protection Officer designation under BDSG",
        source_text="Controller designates DPO if generally at least 20 persons constantly deal with automated processing.",
        source_authority="German Federal Legislature",
        edition_or_amendment="BDSG n.F. 2017/2019",
        content_rights="German Federal Law Gazette - Public Domain (§ 5 UrhG)",
        request_id="req-bdsg38",
        requirement_type=SourceRequirementType.STATUTORY,
    )

    # Attempting to mark Art 30 as IMPLEMENTED without mapped controls MUST FAIL
    with pytest.raises(InvalidCoverageMappingError) as exc:
        service.set_coverage_ledger_entry(
            principal=author,
            version_id=v.id,
            source_requirement_id=req_art30.id,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale="Covered by ROPA register.",
            request_id="req-led-fail",
        )
    assert "cannot be marked IMPLEMENTED with 0 mapped satisfying controls" in str(exc.value)

    # Now add control and map it
    ctrl_ropa = service.add_canonical_control(
        principal=author,
        version_id=v.id,
        identifier="GDPR-ROPA-01",
        title="Record of Processing Activities Register",
        description="Maintain digital ROPA with purpose, categories, recipients, and retention periods.",
        category="ACCOUNTABILITY",
        guidance="Update continuously as data flows change.",
        sort_order=1,
        request_id="req-c-ropa",
    )
    service.add_requirement_control_mapping(
        principal=author,
        version_id=v.id,
        source_requirement_id=req_art30.id,
        canonical_control_id=ctrl_ropa.id,
        mapping_type=MappingType.SATISFIES,
        request_id="req-map-ropa",
        rationale="Dedicated ROPA module satisfies Article 30(1) requirements directly.",
    )

    # Now marking Art 30 as IMPLEMENTED succeeds
    entry_art30 = service.set_coverage_ledger_entry(
        principal=author,
        version_id=v.id,
        source_requirement_id=req_art30.id,
        disposition=CoverageDisposition.IMPLEMENTED,
        rationale="Satisfied by GDPR-ROPA-01 compliant processing activities register.",
        request_id="req-led-art30",
    )
    assert entry_art30.disposition == CoverageDisposition.IMPLEMENTED

    # Disposition NOT_CUSTOMER_OBLIGATION requires substantive rationale
    with pytest.raises(CoverageLedgerError):
        service.set_coverage_ledger_entry(
            principal=author,
            version_id=v.id,
            source_requirement_id=req_art57.id,
            disposition=CoverageDisposition.NOT_CUSTOMER_OBLIGATION,
            rationale="short",  # too short (< 10 chars)
            request_id="req-led-short",
        )

    entry_art57 = service.set_coverage_ledger_entry(
        principal=author,
        version_id=v.id,
        source_requirement_id=req_art57.id,
        disposition=CoverageDisposition.NOT_CUSTOMER_OBLIGATION,
        rationale="Article 57 governs statutory supervisory authority obligations (DPAs), not commercial customer duties.",
        request_id="req-led-art57",
    )
    assert entry_art57.disposition == CoverageDisposition.NOT_CUSTOMER_OBLIGATION

    # Disposition PROFILE_EXCLUSION with justified rationale
    entry_bdsg38 = service.set_coverage_ledger_entry(
        principal=author,
        version_id=v.id,
        source_requirement_id=req_bdsg38.id,
        disposition=CoverageDisposition.PROFILE_EXCLUSION,
        rationale="BDSG Section 38 evaluated via dynamic German jurisdiction overlay applicability rule, not generic EU baseline.",
        request_id="req-led-bdsg38",
    )
    assert entry_bdsg38.disposition == CoverageDisposition.PROFILE_EXCLUSION


def test_coverage_ledger_validation_and_release_gate(
    session: Session, test_principals: dict[str, Principal]
) -> None:
    service = FrameworkService(session)
    author = test_principals["author"]
    legal = test_principals["legal"]
    approver = test_principals["approver"]

    fw = service.create_framework(author, "MVSP", "mvsp-trace", "Minimum Viable Security", "req-1")
    v = service.create_version_draft(author, fw.id, "2.0", "MVSP v2.0", "req-2")

    req1 = service.add_source_requirement(
        principal=author,
        version_id=v.id,
        source_reference="2.1",
        title="Self-assessment / Penetration testing",
        source_text="Perform annual penetration testing by independent testers.",
        source_authority="MVSP Coalition",
        edition_or_amendment="v2.0",
        content_rights="Open Web Foundation Agreement / CC-BY-4.0",
        request_id="req-mvsp-1",
        requirement_type=SourceRequirementType.REQUIREMENT,
    )
    req2 = service.add_source_requirement(
        principal=author,
        version_id=v.id,
        source_reference="2.2",
        title="Vulnerability Disclosure Program",
        source_text="Maintain a public vulnerability disclosure policy.",
        source_authority="MVSP Coalition",
        edition_or_amendment="v2.0",
        content_rights="Open Web Foundation Agreement / CC-BY-4.0",
        request_id="req-mvsp-2",
        requirement_type=SourceRequirementType.REQUIREMENT,
    )

    ctrl1 = service.add_canonical_control(
        principal=author,
        version_id=v.id,
        identifier="MVSP-2.1",
        title="Annual Pentest Execution",
        description="Execute annual grey-box pentest.",
        category="TESTING",
        guidance="Conduct annual testing.",
        sort_order=1,
        request_id="req-c-mvsp1",
    )
    service.add_requirement_control_mapping(
        principal=author,
        version_id=v.id,
        source_requirement_id=req1.id,
        canonical_control_id=ctrl1.id,
        mapping_type=MappingType.SATISFIES,
        request_id="req-map-mvsp1",
        rationale="MVSP-2.1 directly requires annual pentests.",
    )
    service.set_coverage_ledger_entry(
        principal=author,
        version_id=v.id,
        source_requirement_id=req1.id,
        disposition=CoverageDisposition.IMPLEMENTED,
        rationale="Implemented by control MVSP-2.1.",
        request_id="req-led-mvsp1",
    )

    # req2 is still UNACCOUNTED (no ledger entry)!
    report = service.validate_coverage_ledger(v.id)
    assert report.is_complete is False
    assert "2.2" in report.unaccounted_references

    # Mark req2 as BLOCKED
    service.set_coverage_ledger_entry(
        principal=author,
        version_id=v.id,
        source_requirement_id=req2.id,
        disposition=CoverageDisposition.BLOCKED,
        rationale="Pending legal template for public disclosure reporting policy.",
        request_id="req-led-mvsp2-blocked",
    )
    report_blocked = service.validate_coverage_ledger(v.id)
    assert report_blocked.is_complete is False
    assert "2.2" in report_blocked.blocked_references

    # Go through review lifecycle with BLOCKED item
    service.submit_version_for_review(author, v.id, "req-sub")
    d1 = compute_version_content_digest(v)
    service.record_legal_review(
        legal, v.id, "Reviewed with blocked note", "req-rev", content_digest=d1
    )
    d2 = compute_version_content_digest(v)
    service.approve_version(approver, v.id, "Approved provisionally", "req-app", content_digest=d2)

    # Release MUST BE BLOCKED due to incomplete coverage ledger / BLOCKED requirement
    d3 = compute_version_content_digest(v)
    with pytest.raises(ReleaseBlockedError) as exc:
        service.release_version(approver, v.id, "req-rel", content_digest=d3)
    assert "incomplete coverage ledger" in str(exc.value)

    # Approved content must explicitly return to draft before revision.
    service.return_version_to_draft(author, v.id, "Resolve blocked coverage", "req-return-draft")
    assert v.legal_reviewed_by_user_id is None
    assert v.approved_by_user_id is None
    # Now unblock req2: add control, map, and set ledger to IMPLEMENTED
    ctrl2 = service.add_canonical_control(
        principal=author,
        version_id=v.id,
        identifier="MVSP-2.2",
        title="Vulnerability Disclosure Handling",
        description="Public security.txt and response workflow.",
        category="DISCLOSURE",
        guidance="Publish security.txt file.",
        sort_order=2,
        request_id="req-c-mvsp2",
    )
    service.add_requirement_control_mapping(
        principal=author,
        version_id=v.id,
        source_requirement_id=req2.id,
        canonical_control_id=ctrl2.id,
        mapping_type=MappingType.SATISFIES,
        request_id="req-map-mvsp2",
        rationale="Satisfies 2.2 via published policy.",
    )
    service.set_coverage_ledger_entry(
        principal=author,
        version_id=v.id,
        source_requirement_id=req2.id,
        disposition=CoverageDisposition.IMPLEMENTED,
        rationale="Fully implemented by MVSP-2.2 control.",
        request_id="req-led-mvsp2-impl",
    )

    # Approvals were invalidated when content modified back in DRAFT state
    assert v.release_state == ReleaseState.DRAFT
    report_complete = service.validate_coverage_ledger(v.id)
    assert report_complete.is_complete is True
    assert report_complete.total_requirements == 2
    assert report_complete.implemented_count == 2
    assert report_complete.blocked_count == 0

    # Review, approve, release now succeeds cleanly
    service.submit_version_for_review(author, v.id, "req-sub-2")
    d4 = compute_version_content_digest(v)
    service.record_legal_review(legal, v.id, "Full ledger verified", "req-rev-2", content_digest=d4)
    d5 = compute_version_content_digest(v)
    service.approve_version(
        approver, v.id, "Approved for production", "req-app-2", content_digest=d5
    )
    d6 = compute_version_content_digest(v)
    released = service.release_version(approver, v.id, "req-rel-2", content_digest=d6)
    assert released.release_state == ReleaseState.RELEASED


def test_content_digest_and_approval_invalidation_on_requirement_or_ledger_change(
    session: Session, test_principals: dict[str, Principal]
) -> None:
    service = FrameworkService(session)
    author = test_principals["author"]

    fw = service.create_framework(author, "Framework X", "fw-x-digest", "Digest Test", "req-1")
    v = service.create_version_draft(author, fw.id, "1.0", "Draft", "req-2")

    ctrl = service.add_canonical_control(
        principal=author,
        version_id=v.id,
        identifier="X-01",
        title="Control X1",
        description="Desc",
        category="Cat",
        guidance="Guidance",
        sort_order=1,
        request_id="req-c1",
    )
    req = service.add_source_requirement(
        principal=author,
        version_id=v.id,
        source_reference="X.1",
        title="Req X1",
        source_text="Must do X.",
        source_authority="Org X",
        edition_or_amendment="v1",
        content_rights="Public",
        request_id="req-r1",
    )
    service.add_requirement_control_mapping(
        principal=author,
        version_id=v.id,
        source_requirement_id=req.id,
        canonical_control_id=ctrl.id,
        mapping_type=MappingType.SATISFIES,
        request_id="req-m1",
        rationale="Satisfies directly.",
    )
    service.set_coverage_ledger_entry(
        principal=author,
        version_id=v.id,
        source_requirement_id=req.id,
        disposition=CoverageDisposition.IMPLEMENTED,
        rationale="Ledger rationale 1",
        request_id="req-l1",
    )

    initial_digest = compute_version_content_digest(v)

    # Modify coverage ledger entry rationale -> must change digest!
    service.set_coverage_ledger_entry(
        principal=author,
        version_id=v.id,
        source_requirement_id=req.id,
        disposition=CoverageDisposition.IMPLEMENTED,
        rationale="Updated substantive ledger rationale.",
        request_id="req-l2",
    )
    service._refresh_version_content(v)
    modified_digest = compute_version_content_digest(v)
    assert modified_digest != initial_digest

    # Add evidence specification -> must also change digest!
    service.add_evidence_specification(
        principal=author,
        version_id=v.id,
        identifier="EVID-X-1",
        title="Evidence Spec X1",
        description="Evidence description",
        evidence_type="audit_log",
        request_id="req-s1",
        canonical_control_id=ctrl.id,
    )
    service._refresh_version_content(v)
    after_spec_digest = compute_version_content_digest(v)
    assert after_spec_digest != modified_digest
