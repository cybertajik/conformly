"""Oman Personal Data Protection Law (Royal Decree No. 6/2022) Pack Definition.

Covers:
- Sultanate of Oman personal data protection regime promulgated by Royal Decree No. 6/2022
- Lawful processing, express consent, data subject rights, transparency & privacy policy, technical security, breach reporting to MTCIT, and cross-border transfer controls
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

OM_PDPL_AUTHORITY = "Ministry of Transport, Communications and Information Technology (MTCIT)"
OM_PDPL_EDITION = "Royal Decree No. 6/2022 Promulgating the Personal Data Protection Law"
OM_PDPL_RIGHTS = "Official Sultanate of Oman Royal Decree (MTCIT)."
OM_PDPL_URL = "https://www.mtcit.gov.om/sectors/governance/personal"

OM_PDPL_ARTICLES: list[tuple[str, str, str, str, str]] = [
    (
        "3",
        "Lawful Processing & Express Written Consent",
        "It is prohibited to process personal data without the prior explicit written consent of the data subject, except in cases where processing is authorized by statutory law or for contract execution.",
        "Lawful Basis & Consent",
        "Prior to processing & annual review",
    ),
    (
        "8",
        "Data Subject Rights & Revocation of Consent",
        "The data subject has the right to access personal data held about them, request correction or updating of inaccurate data, revoke previously granted consent, and request erasure of personal data.",
        "Data Subject Rights",
        "Within 30 days of request",
    ),
    (
        "11",
        "Personal Data Privacy Policy & Transparency",
        "The controller shall provide a clear, accessible privacy policy informing data subjects of the controller's identity, the purpose of processing, categories collected, and procedures for exercising rights.",
        "Transparency & Notice",
        "At data collection & annual review",
    ),
    (
        "14",
        "Technical & Organizational Security Safeguards",
        "The controller and processor must implement necessary organizational, administrative, and technical safeguards to prevent unauthorized access, leakage, damage, or alteration of personal data.",
        "Information Security",
        "Continuous enforcement",
    ),
    (
        "19",
        "Mandatory Breach Notification to MTCIT",
        "The controller must notify the Ministry of Transport, Communications and Information Technology (MTCIT) and affected individuals without delay upon the occurrence of any personal data breach or leakage.",
        "Incident Management",
        "Immediately upon awareness",
    ),
    (
        "23",
        "Cross-Border Personal Data Transfer Restrictions",
        "Personal data may not be transferred outside the Sultanate of Oman unless the recipient country maintains an adequate level of personal data protection and prior approval from MTCIT is obtained.",
        "International Transfers",
        "Prior to transfer & periodic review",
    ),
]

OM_PDPL_CONTROLS: list[PackControlDefinition] = []
OM_PDPL_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
OM_PDPL_MAPPINGS: list[PackMappingDefinition] = []
OM_PDPL_EVIDENCE: list[PackEvidenceDefinition] = []
OM_PDPL_COVERAGE: list[PackCoverageDefinition] = []

for idx, (art_num, title, desc, cat, cadence) in enumerate(OM_PDPL_ARTICLES, start=1):
    ctrl_id = f"OM-PDPL-Art-{art_num}"
    src_ref = f"Oman Royal Decree No. 6/2022 Article {art_num}"

    guidance = (
        f"**Implementation Guidance:** Implement operational policies and technical safeguards for {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Policy documents, consent records, privacy disclosures, security controls, or transfer permits for {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Oman Personal Data Protection & Privacy Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    OM_PDPL_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    OM_PDPL_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=OM_PDPL_AUTHORITY,
            edition_or_amendment=OM_PDPL_EDITION,
            source_text=desc,
            content_rights=OM_PDPL_RIGHTS,
            source_url=OM_PDPL_URL,
            conformly_guidance=f"Ensure compliance with Oman Royal Decree No. 6/2022 under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    OM_PDPL_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} satisfies Oman PDPL statutory obligation {src_ref}.",
        )
    )

    OM_PDPL_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-OM-PDPL-Art-{art_num}",
            title=f"Evidence for {title}",
            description=f"Consent mechanism, privacy notice, security policy, or MTCIT breach notification procedure for {src_ref}.",
            evidence_type="POLICY_DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    OM_PDPL_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Oman PDPL Article {art_num} covered by control {ctrl_id}.",
        )
    )

OM_PDPL_PACK = FrameworkPackDefinition(
    slug="om-pdpl",
    name="Oman Personal Data Protection Law (Royal Decree No. 6/2022)",
    version="v2022",
    description="Sultanate of Oman Personal Data Protection Law promulgated by Royal Decree No. 6/2022.",
    release_notes="Active release pack covering Oman data processing principles, express consent, privacy notices, technical safeguards, MTCIT breach reporting, and cross-border transfer controls.",
    legal_review_notes="Statutory requirements extracted directly from Oman Royal Decree No. 6/2022.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=OM_PDPL_CONTROLS,
    source_requirements=OM_PDPL_SOURCE_REQS,
    mappings=OM_PDPL_MAPPINGS,
    evidence_specifications=OM_PDPL_EVIDENCE,
    coverage_ledger=OM_PDPL_COVERAGE,
)
