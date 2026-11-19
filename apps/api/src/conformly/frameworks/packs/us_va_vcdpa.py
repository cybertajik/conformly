"""Virginia Consumer Data Protection Act (VCDPA) Pack Definition.

Covers:
- 6 core statutory requirements under Va. Code Ann. § 59.1-575 et seq.
- Scope and applicability thresholds under § 59.1-577
- Consumer rights (access, correct, delete, portability, opt-out of targeted ads/sale/profiling) under § 59.1-578
- Controller duties (purpose limitation, security safeguards, non-discrimination) under § 59.1-579
- Sensitive data processing and opt-in consent under § 59.1-580
- Mandatory Data Protection Assessments (DPAs) under § 59.1-581
- Controller-processor contracting and oversight under § 59.1-582
"""

from conformly.frameworks.models import (
    CoverageDisposition,
    MappingType,
    SourceRequirementType,
)
from conformly.frameworks.packs.types import (
    FrameworkPackDefinition,
    PackControlDefinition,
    PackCoverageDefinition,
    PackEvidenceDefinition,
    PackMappingDefinition,
    PackSourceRequirementDefinition,
)

VCDPA_AUTHORITY = "Commonwealth of Virginia / Office of the Attorney General"
VCDPA_EDITION = "Virginia Consumer Data Protection Act (Va. Code Ann. § 59.1-575 et seq.)"
VCDPA_RIGHTS = "Public Domain State Statute (Commonwealth of Virginia)."
VCDPA_URL = "https://law.lis.virginia.gov/vacodefull/title59.1/chapter53/"

VCDPA_SECTIONS: list[tuple[str, str, str, str, str]] = [
    (
        "59.1-577",
        "VCDPA Scope, Applicability & Consumer Thresholds",
        "Establish statutory applicability under VCDPA (entities conducting business in Virginia or producing products/services targeted to residents that control/process personal data of 100,000+ consumers, or 25,000+ consumers with 50%+ gross revenue from selling personal data).",
        "Governance & Scope",
        "Annual review & assessment",
    ),
    (
        "59.1-578",
        "Consumer Personal Data Rights & 45-Day Response",
        "Operationalize mechanisms for Virginia consumers to invoke rights to confirm processing, access, correct inaccuracies, delete personal data, obtain a portable copy, and opt out of targeted advertising, sale of personal data, and profiling in furtherance of decisions that produce legal or similarly significant effects.",
        "Consumer Rights & Requests",
        "Within 45 days of request (plus 45-day extension if reasonably necessary)",
    ),
    (
        "59.1-579",
        "Controller Responsibilities, Purpose Limitation & Security Safeguards",
        "Limit collection of personal data to what is adequate, relevant, and reasonably necessary; establish, implement, and maintain reasonable administrative, technical, and physical data security practices to protect personal data; and prohibit discrimination against consumers exercising statutory rights.",
        "Data Protection Safeguards",
        "Continuous / Quarterly review",
    ),
    (
        "59.1-580",
        "Sensitive Data Processing & Opt-In Consent",
        "Prohibit the processing of sensitive personal data (racial/ethnic origin, religious beliefs, mental/physical health diagnosis, sexual orientation, citizenship/immigration status, genetic/biometric data, child data under COPPA, or precise geolocation) without first obtaining consumer opt-in consent.",
        "Consent & Sensitive Data",
        "Prior to collection or processing",
    ),
    (
        "59.1-581",
        "Data Protection Assessments (DPAs)",
        "Conduct and document a data protection assessment for processing activities involving targeted advertising, sale of personal data, profiling presenting heightened risk of harm, sensitive data, or any processing presenting reasonably foreseeable risk of substantial injury.",
        "Risk Assessment & DPIA",
        "Prior to initiating high-risk processing / Annual review",
    ),
    (
        "59.1-582",
        "Controller-Processor Contracts & Oversight",
        "Enforce mandatory written contracts governing data processing between controllers and processors, detailing processing instructions, nature and purpose of processing, duration, duty of confidentiality, sub-processor engagement, and audit or verification rights.",
        "Vendor & Third-Party Management",
        "Prior to vendor engagement / Annual review",
    ),
]

VCDPA_CONTROLS: list[PackControlDefinition] = []
VCDPA_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
VCDPA_MAPPINGS: list[PackMappingDefinition] = []
VCDPA_EVIDENCE: list[PackEvidenceDefinition] = []
VCDPA_COVERAGE: list[PackCoverageDefinition] = []

for idx, (sec_num, title, desc, cat, cadence) in enumerate(VCDPA_SECTIONS, start=1):
    ctrl_id = f"VCDPA-{sec_num.replace('.', '-')}"
    src_ref = f"Va. Code Ann. § {sec_num}"

    guidance = (
        f"**Implementation Guidance:** Operationalize workflows, governance policies, and technical safeguards to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented threshold analysis, consumer request intake records, consent logs, DPA documents, or controller-processor agreements satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Virginia Consumer Data Protection Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    VCDPA_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    VCDPA_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=VCDPA_AUTHORITY,
            edition_or_amendment=VCDPA_EDITION,
            source_text=desc,
            content_rights=VCDPA_RIGHTS,
            source_url=VCDPA_URL,
            conformly_guidance=f"Operationalize compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    VCDPA_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly operationalizes statutory requirement {src_ref}.",
        )
    )

    VCDPA_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-VCDPA-{sec_num.replace('.', '_')}",
            title=f"Evidence for {title}",
            description=f"Operational documentation, verification logs, consent records, assessment reports, or contracts for {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    VCDPA_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"VCDPA statutory requirement {sec_num} covered by control {ctrl_id}.",
        )
    )

US_VA_VCDPA_PACK = FrameworkPackDefinition(
    slug="us-va-vcdpa",
    name="Virginia Consumer Data Protection Act (VCDPA)",
    version="v2023",
    description="Virginia Consumer Data Protection Act (Va. Code Ann. § 59.1-575 et seq.) establishing comprehensive consumer privacy rights, controller duties, and mandatory DPAs.",
    release_notes="Active release pack covering Virginia consumer rights, opt-in sensitive consent, DPAs, and controller-processor contracting.",
    legal_review_notes="Statutory provisions extracted directly from Va. Code Ann. § 59.1-575 et seq.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=VCDPA_CONTROLS,
    source_requirements=VCDPA_SOURCE_REQS,
    mappings=VCDPA_MAPPINGS,
    evidence_specifications=VCDPA_EVIDENCE,
    coverage_ledger=VCDPA_COVERAGE,
)
