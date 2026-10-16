"""Saudi Arabia Personal Data Protection Law (PDPL) Pack Definition.

Covers:
- Royal Decree No. M/19 of 9/2/1443H as amended by Royal Decree No. M/148 of 5/9/1444H
- Official Saudi Data & AI Authority (SDAIA) Implementing Regulations
- Data subject rights, lawful processing, mandatory privacy policies, security controls, breach notification to SDAIA, and cross-border transfer rules
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

SA_PDPL_AUTHORITY = "Saudi Data & AI Authority (SDAIA)"
SA_PDPL_EDITION = (
    "Personal Data Protection Law (Royal Decree M/19 amended by M/148) & Implementing Regulations"
)
SA_PDPL_RIGHTS = "Statutory Law of the Kingdom of Saudi Arabia (SDAIA Public Regulatory Portal)."
SA_PDPL_URL = "https://sdaia.gov.sa/en/SDAIA/about/Pages/RegulationsAndPolicies.aspx"

SA_PDPL_ARTICLES: list[tuple[str, str, str, str, str]] = [
    (
        "Art-4",
        "Data Subject Rights & Request Management",
        "Data subjects have the right to be informed, the right to access their personal data, the right to request a copy, the right to request correction or updating, and the right to request destruction when no longer required.",
        "Data Subject Rights",
        "Within 30 days of request",
    ),
    (
        "Art-5",
        "Lawful Processing Bases & Consent",
        "Personal data may not be processed without the consent of the data subject, except where processing achieves an explicit statutory purpose, is necessary for contract performance, or complies with another lawful basis recognized by SDAIA regulations.",
        "Lawfulness & Governance",
        "Prior to processing / Continuous",
    ),
    (
        "Art-12",
        "Privacy Policy & Public Transparency",
        "The controller must adopt a privacy policy and make it available to data subjects prior to collecting their personal data, specifying the purpose, collected categories, storage methods, data subject rights, and contact information.",
        "Transparency & Notice",
        "Annual review / Updates on change",
    ),
    (
        "Art-18",
        "Technical & Organizational Security Safeguards",
        "The controller must implement all necessary organizational, administrative, and technical measures to protect personal data from leakage, unauthorized access, destruction, or misuse, ensuring data confidentiality and integrity.",
        "Information Security",
        "Continuous",
    ),
    (
        "Art-24",
        "Mandatory Breach Notification to SDAIA",
        "The controller must notify SDAIA immediately (within 72 hours of becoming aware) of any data breach, leakage, or unauthorized access, and notify affected data subjects if the incident may cause them significant harm.",
        "Incident Response",
        "Within 72 hours of incident detection",
    ),
    (
        "Art-29",
        "Cross-Border Personal Data Transfer Controls",
        "A controller may transfer personal data outside the Kingdom only if the destination provides an adequate level of protection approved by SDAIA, or pursuant to standard contractual clauses, binding corporate rules, or statutory exceptions.",
        "International Transfers",
        "Prior to transfer / Quarterly review",
    ),
]

SA_PDPL_CONTROLS: list[PackControlDefinition] = []
SA_PDPL_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
SA_PDPL_MAPPINGS: list[PackMappingDefinition] = []
SA_PDPL_EVIDENCE: list[PackEvidenceDefinition] = []
SA_PDPL_COVERAGE: list[PackCoverageDefinition] = []

for idx, (art_num, title, desc, cat, cadence) in enumerate(SA_PDPL_ARTICLES, start=1):
    ctrl_id = f"SA-PDPL-{art_num.replace('.', '-')}"
    src_ref = f"Saudi Arabia PDPL {art_num.replace('-', ' ')}"

    guidance = (
        f"**Implementation Guidance:** Implement operational policies and workflows to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Policy disclosure, consent log, security report, or transfer assessment for {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Saudi Data Protection Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    SA_PDPL_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    SA_PDPL_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=SA_PDPL_AUTHORITY,
            edition_or_amendment=SA_PDPL_EDITION,
            source_text=desc,
            content_rights=SA_PDPL_RIGHTS,
            source_url=SA_PDPL_URL,
            conformly_guidance=f"Operationalize SDAIA PDPL compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    SA_PDPL_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly satisfies {src_ref}.",
        )
    )

    SA_PDPL_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-SA-PDPL-{art_num.replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"Policy disclosure, consent log, security safeguard report, or transfer assessment supporting {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    SA_PDPL_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"PDPL provision {art_num} covered by control {ctrl_id}.",
        )
    )

SA_PDPL_PACK = FrameworkPackDefinition(
    slug="sa-pdpl",
    name="Saudi Arabia Personal Data Protection Law (PDPL)",
    version="v2023",
    description="Saudi Arabia Personal Data Protection Law (Royal Decree M/19 amended by M/148) & SDAIA Implementing Regulations.",
    release_notes="Active release pack covering Saudi data subject rights, consent rules, security measures, breach reporting, and cross-border transfers.",
    legal_review_notes="Statutory requirements aligned with SDAIA implementing regulations and Royal Decree M/19.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=SA_PDPL_CONTROLS,
    source_requirements=SA_PDPL_SOURCE_REQS,
    mappings=SA_PDPL_MAPPINGS,
    evidence_specifications=SA_PDPL_EVIDENCE,
    coverage_ledger=SA_PDPL_COVERAGE,
)
