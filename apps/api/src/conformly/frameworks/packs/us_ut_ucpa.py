"""Utah Consumer Privacy Act (UCPA) Pack Definition.

Covers:
- 6 core statutory requirements under Utah Code Ann. § 13-61-101 et seq.
- Dual applicability threshold under § 13-61-102
- Consumer personal data rights under § 13-61-201
- Controller response timelines and verification protocols under § 13-61-203
- Processor responsibilities and written contracts under § 13-61-301
- Controller duties (privacy notice, data security practices) under § 13-61-302(1)
- Sensitive data processing disclosure and opt-out rights under § 13-61-302(2)
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

UCPA_AUTHORITY = "State of Utah / Utah Department of Commerce & Office of the Attorney General"
UCPA_EDITION = "Utah Consumer Privacy Act (Utah Code Ann. § 13-61-101 et seq.)"
UCPA_RIGHTS = "Public Domain State Statute (State of Utah)."
UCPA_URL = "https://le.utah.gov/xcode/Title13/Chapter61/"

UCPA_SECTIONS: list[tuple[str, str, str, str, str]] = [
    (
        "13-61-102",
        "UCPA Scope & Dual Applicability Thresholds",
        "Establish statutory applicability under UCPA (entities conducting business in Utah or producing products/services targeted to Utah residents that have annual revenue of $100,000,000 or more, and control/process personal data of 100,000+ consumers, or derive 50%+ gross revenue from selling personal data and control/process personal data of 25,000+ consumers).",
        "Governance & Scope",
        "Annual review & assessment",
    ),
    (
        "13-61-201",
        "Utah Consumer Personal Data Rights",
        "Provide Utah consumers the right to confirm whether a controller processes personal data and access that personal data; delete personal data that the consumer provided to the controller; obtain a copy of the personal data in a portable format; and opt out of targeted advertising and the sale of personal data.",
        "Consumer Rights & Requests",
        "Within 45 days of request",
    ),
    (
        "13-61-203",
        "Controller Response Timelines & Request Verification",
        "Authenticate consumer requests using commercially reasonable efforts; respond within 45 days of receiving the request (with a single 45-day extension when reasonably necessary); provide information free of charge once per consumer per 12-month period; and notify consumers of any inability to authenticate.",
        "Consumer Rights & Requests",
        "Within 45 days of request",
    ),
    (
        "13-61-301",
        "Processor Responsibilities & Written Contracts",
        "Ensure data processing by processors is governed by written contracts that set forth instructions for processing, the nature and purpose of processing, duration, duty of confidentiality, security safeguards, and requirement that sub-processors enter into equivalent agreements.",
        "Vendor & Third-Party Management",
        "Prior to vendor engagement / Annual review",
    ),
    (
        "13-61-302-1",
        "Controller Transparency Notices & Reasonable Security Practices",
        "Provide consumers with a reasonably accessible and clear privacy notice specifying categories of personal data processed, purposes, categories shared with third parties, and how consumers can exercise rights; establish, implement, and maintain reasonable administrative, technical, and physical data security practices.",
        "Data Protection Safeguards",
        "Continuous / Quarterly review",
    ),
    (
        "13-61-302-2",
        "Sensitive Data Clear Notice & Opt-Out Opportunity",
        "Prohibit the processing of sensitive personal data without first presenting the consumer with clear notice and an opportunity to opt out of the processing, or, in the case of personal data concerning a known child, processing in compliance with COPPA.",
        "Consent & Sensitive Data",
        "Prior to collection or processing",
    ),
]

UCPA_CONTROLS: list[PackControlDefinition] = []
UCPA_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
UCPA_MAPPINGS: list[PackMappingDefinition] = []
UCPA_EVIDENCE: list[PackEvidenceDefinition] = []
UCPA_COVERAGE: list[PackCoverageDefinition] = []

for idx, (sec_num, title, desc, cat, cadence) in enumerate(UCPA_SECTIONS, start=1):
    ctrl_id = f"UCPA-{sec_num.replace('.', '-')}"
    src_ref = f"Utah Code Ann. § {sec_num.replace('-', '.')}"

    guidance = (
        f"**Implementation Guidance:** Operationalize workflows, transparency notices, and security controls to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented applicability assessment, privacy notices, request authentication records, opt-out mechanisms, or processor contracts satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Utah Consumer Privacy Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    UCPA_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    UCPA_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=UCPA_AUTHORITY,
            edition_or_amendment=UCPA_EDITION,
            source_text=desc,
            content_rights=UCPA_RIGHTS,
            source_url=UCPA_URL,
            conformly_guidance=f"Operationalize compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    UCPA_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly operationalizes statutory requirement {src_ref}.",
        )
    )

    UCPA_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-UCPA-{sec_num.replace('.', '_').replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"Operational documentation, verification logs, privacy notice copies, or contracts for {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    UCPA_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"UCPA statutory requirement {sec_num} covered by control {ctrl_id}.",
        )
    )

US_UT_UCPA_PACK = FrameworkPackDefinition(
    slug="us-ut-ucpa",
    name="Utah Consumer Privacy Act (UCPA)",
    version="v2023",
    description="Utah Consumer Privacy Act (Utah Code Ann. § 13-61-101 et seq.) establishing business applicability thresholds, consumer rights, and sensitive data opt-out notices.",
    release_notes="Active release pack covering Utah consumer rights, sensitive data opt-out disclosures, and controller-processor contracting.",
    legal_review_notes="Statutory provisions extracted directly from Utah Code Ann. § 13-61-101 et seq.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=UCPA_CONTROLS,
    source_requirements=UCPA_SOURCE_REQS,
    mappings=UCPA_MAPPINGS,
    evidence_specifications=UCPA_EVIDENCE,
    coverage_ledger=UCPA_COVERAGE,
)
