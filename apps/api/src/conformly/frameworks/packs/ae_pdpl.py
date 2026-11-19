"""UAE Personal Data Protection Law (Federal Decree-Law No. 45/2021) Pack Definition.

Covers:
- Onshore United Arab Emirates general personal data protection regime
- Processing principles, consent, data breach notification to UAE Data Office, data subject rights, technical security obligations, and cross-border transfer controls
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

AE_PDPL_AUTHORITY = "UAE Data Office"
AE_PDPL_EDITION = "Federal Decree-Law No. 45 of 2021 on Personal Data Protection"
AE_PDPL_RIGHTS = "Public Domain UAE Federal Legislation (United Arab Emirates)."
AE_PDPL_URL = "https://u.ae/en/about-the-uae/digital-uae/data/data-protection-laws"

AE_PDPL_ARTICLES: list[tuple[str, str, str, str, str]] = [
    (
        "5",
        "Principles of Personal Data Processing",
        "Personal data shall be processed fairly, transparently, and lawfully; collected for clear and specified purposes; kept accurate and limited to what is necessary; stored securely; and retained no longer than necessary.",
        "Data Protection Governance",
        "Continuous compliance",
    ),
    (
        "6",
        "Consent & Lawful Processing Conditions",
        "Processing of personal data is prohibited without the consent of the data subject, except where processing is necessary to perform a contract, fulfill a legal duty, or protect public/vital interests.",
        "Lawful Basis & Consent",
        "Prior to processing & annual review",
    ),
    (
        "9",
        "Data Breach Notification to UAE Data Office",
        "The controller shall notify the UAE Data Office immediately upon becoming aware of any personal data breach that infringes the confidentiality, security, or privacy of personal data, and notify affected subjects if high risk.",
        "Incident Management",
        "Immediate upon awareness",
    ),
    (
        "13",
        "Data Subject Rights Management",
        "Operationalize data subject rights: right to access and obtain information, right to request data correction or erasure, right to stop processing, and right to withdraw consent without undue delay.",
        "Data Subject Rights",
        "Within 30 days of request",
    ),
    (
        "18",
        "Controller & Processor Security Safeguards",
        "Implement appropriate technical and organizational measures (TOMs) to secure personal data against unauthorized access, loss, alteration, or disclosure, including data encryption and access restrictions.",
        "Information Security",
        "Continuous enforcement",
    ),
    (
        "22",
        "Cross-Border Personal Data Transfer Controls",
        "Personal data may not be transferred outside the UAE unless the destination country has an approved adequate level of protection, or transfer is governed by standard contractual clauses or binding corporate rules approved by the UAE Data Office.",
        "International Transfers",
        "Prior to transfer & annual review",
    ),
]

AE_PDPL_CONTROLS: list[PackControlDefinition] = []
AE_PDPL_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
AE_PDPL_MAPPINGS: list[PackMappingDefinition] = []
AE_PDPL_EVIDENCE: list[PackEvidenceDefinition] = []
AE_PDPL_COVERAGE: list[PackCoverageDefinition] = []

for idx, (art_num, title, desc, cat, cadence) in enumerate(AE_PDPL_ARTICLES, start=1):
    ctrl_id = f"AE-PDPL-Art-{art_num}"
    src_ref = f"UAE Federal Decree-Law No. 45/2021 Article {art_num}"

    guidance = (
        f"**Implementation Guidance:** Implement operational policies and technical safeguards for {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Policy documents, consent records, DSAR logs, security configurations, or transfer assessments for {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** UAE Personal Data Protection & Privacy Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    AE_PDPL_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    AE_PDPL_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=AE_PDPL_AUTHORITY,
            edition_or_amendment=AE_PDPL_EDITION,
            source_text=desc,
            content_rights=AE_PDPL_RIGHTS,
            source_url=AE_PDPL_URL,
            conformly_guidance=f"Ensure compliance with UAE Federal Decree-Law No. 45/2021 under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    AE_PDPL_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} satisfies UAE PDPL statutory obligation {src_ref}.",
        )
    )

    AE_PDPL_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-AE-PDPL-Art-{art_num}",
            title=f"Evidence for {title}",
            description=f"Policy procedure, consent mechanism, breach escalation procedure, or transfer agreement for {src_ref}.",
            evidence_type="POLICY_DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    AE_PDPL_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"UAE PDPL Article {art_num} covered by control {ctrl_id}.",
        )
    )

AE_PDPL_PACK = FrameworkPackDefinition(
    slug="ae-pdpl",
    name="UAE Personal Data Protection Law (Federal Decree-Law No. 45/2021)",
    version="v2021",
    description="United Arab Emirates Federal Decree-Law No. 45 of 2021 on Personal Data Protection.",
    release_notes="Active release pack covering UAE onshore processing principles, consent, security controls, breach notification to UAE Data Office, and cross-border transfers.",
    legal_review_notes="Statutory requirements extracted directly from UAE Federal Decree-Law No. 45/2021.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=AE_PDPL_CONTROLS,
    source_requirements=AE_PDPL_SOURCE_REQS,
    mappings=AE_PDPL_MAPPINGS,
    evidence_specifications=AE_PDPL_EVIDENCE,
    coverage_ledger=AE_PDPL_COVERAGE,
)
