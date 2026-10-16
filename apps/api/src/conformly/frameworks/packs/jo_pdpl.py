"""Jordan Personal Data Protection Law No. 24 of 2023 Pack Definition.

Covers:
- Hashemite Kingdom of Jordan Personal Data Protection Law No. 24 of 2023
- Processing legitimacy, prior consent, data subject rights, administrative & technical security, breach notification to the Council within 72 hours, and cross-border transfer requirements
- Structured evidence collection specifications and complete coverage ledger
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

JO_PDPL_AUTHORITY = (
    "Personal Data Protection Council / Ministry of Digital Economy and Entrepreneurship (MoDEE)"
)
JO_PDPL_EDITION = "Law No. 24 of 2023 on the Protection of Personal Data"
JO_PDPL_RIGHTS = "Official Hashemite Kingdom of Jordan Legislation (MoDEE)."
JO_PDPL_URL = "https://www.modee.gov.jo/EN/List/The_law_regulations_and_instructions"

JO_PDPL_ARTICLES: list[tuple[str, str, str, str, str]] = [
    (
        "4",
        "General Principles of Lawful Processing",
        "Personal data must be processed legitimately, fairly, and transparently; collected for specific and explicit lawful purposes; limited to what is necessary; accurate; and kept secure against unauthorized disclosure.",
        "Data Protection Governance",
        "Continuous compliance",
    ),
    (
        "5",
        "Prior Documented Consent Requirements",
        "Processing of personal data is prohibited without obtaining the prior, explicit, written or electronic consent of the data subject, unless processing is necessary to execute a contract, fulfill a legal duty, or protect vital interests.",
        "Lawful Basis & Consent",
        "Prior to processing & annual review",
    ),
    (
        "8",
        "Data Subject Rights & Request Management",
        "Operationalize data subject rights: right of access to personal data, right to request correction or updating, right to object to processing, and right to request data destruction.",
        "Data Subject Rights",
        "Within 30 days of request",
    ),
    (
        "12",
        "Technical & Administrative Security Safeguards",
        "The controller and processor must implement appropriate technical, organizational, and administrative measures to protect personal data from unauthorized destruction, loss, alteration, or unlawful access.",
        "Information Security",
        "Continuous enforcement",
    ),
    (
        "14",
        "Mandatory Breach Notification to Council (72 Hours)",
        "The controller shall notify the Personal Data Protection Council without undue delay and not later than 72 hours after becoming aware of any breach of personal data, and inform affected persons if the breach creates high risk.",
        "Incident Management",
        "Within 72 hours of awareness",
    ),
    (
        "18",
        "Cross-Border Transfer Restrictions & Safeguards",
        "Personal data may not be transferred outside the Kingdom of Jordan unless the destination country provides an equivalent level of protection and complies with standards established by the Personal Data Protection Council.",
        "International Transfers",
        "Prior to transfer & annual review",
    ),
]

JO_PDPL_CONTROLS: list[PackControlDefinition] = []
JO_PDPL_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
JO_PDPL_MAPPINGS: list[PackMappingDefinition] = []
JO_PDPL_EVIDENCE: list[PackEvidenceDefinition] = []
JO_PDPL_COVERAGE: list[PackCoverageDefinition] = []

for idx, (art_num, title, desc, cat, cadence) in enumerate(JO_PDPL_ARTICLES, start=1):
    ctrl_id = f"JO-PDPL-Art-{art_num}"
    src_ref = f"Jordan Law No. 24 of 2023 Article {art_num}"

    guidance = (
        f"**Implementation Guidance:** Implement operational policies and technical safeguards for {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Policy documents, consent records, privacy notices, access control configurations, or 72-hour breach notification procedures for {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Jordan Personal Data Protection & Privacy Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    JO_PDPL_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    JO_PDPL_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=JO_PDPL_AUTHORITY,
            edition_or_amendment=JO_PDPL_EDITION,
            source_text=desc,
            content_rights=JO_PDPL_RIGHTS,
            source_url=JO_PDPL_URL,
            conformly_guidance=f"Ensure compliance with Jordan Law No. 24 of 2023 under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    JO_PDPL_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} satisfies Jordan PDPL statutory obligation {src_ref}.",
        )
    )

    JO_PDPL_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-JO-PDPL-Art-{art_num}",
            title=f"Evidence for {title}",
            description=f"Consent mechanism, privacy policy, security safeguards documentation, or Council breach notification procedure for {src_ref}.",
            evidence_type="POLICY_DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    JO_PDPL_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Jordan PDPL Article {art_num} covered by control {ctrl_id}.",
        )
    )

JO_PDPL_PACK = FrameworkPackDefinition(
    slug="jo-pdpl",
    name="Jordan Personal Data Protection Law No. 24 of 2023",
    version="v2023",
    description="Hashemite Kingdom of Jordan Law No. 24 of 2023 on the Protection of Personal Data.",
    release_notes="Active release pack covering Jordanian data processing principles, consent, subject rights, security safeguards, 72h Council breach reporting, and cross-border transfer controls.",
    legal_review_notes="Statutory requirements extracted directly from Jordan Law No. 24 of 2023.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=JO_PDPL_CONTROLS,
    source_requirements=JO_PDPL_SOURCE_REQS,
    mappings=JO_PDPL_MAPPINGS,
    evidence_specifications=JO_PDPL_EVIDENCE,
    coverage_ledger=JO_PDPL_COVERAGE,
)
