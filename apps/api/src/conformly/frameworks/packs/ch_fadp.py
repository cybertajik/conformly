"""Swiss Federal Act on Data Protection (nFADP / revDSG 2023) Pack Definition.

Covers:
- Modernized Swiss Federal Act on Data Protection (FADP / DSG, SR 235.1) in force September 1, 2023
- Principles of processing, privacy by design/default, data security safeguards, processor outsourcing, cross-border disclosure abroad, duty to inform, DPIA, and rapid breach reporting to the FDPIC (EDÖB)
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

FADP_AUTHORITY = "Federal Data Protection and Information Commissioner (FDPIC / EDÖB)"
FADP_EDITION = (
    "Swiss Federal Act on Data Protection (FADP, SR 235.1) of 25 Sept 2020 (in force 1 Sept 2023)"
)
FADP_RIGHTS = "Official Federal Swiss Statute (Swiss Confederation)."
FADP_URL = "https://www.edoeb.admin.ch/edoeb/en/home/datenschutz/grundlagen/revidiertes-datenschutzgesetz.html"

FADP_ARTICLES: list[tuple[str, str, str, str, str]] = [
    (
        "6",
        "Principles of Processing & Good Faith",
        "Personal data must be processed lawfully, fairly, and proportionately. Data must only be collected for a specific purpose recognizable to the data subject and processed in a manner compatible with that purpose.",
        "General Principles",
        "Continuous compliance",
    ),
    (
        "7",
        "Privacy by Design and Privacy by Default",
        "The controller must design data processing systems to comply with data protection principles from inception (by design) and ensure that, by default, only data strictly necessary for the intended purpose are processed (by default).",
        "System Design & Governance",
        "Prior to system launch",
    ),
    (
        "8",
        "Data Security & Protective Safeguards",
        "The controller and processor must ensure an adequate level of data security through appropriate technical and organizational measures to prevent unauthorized processing, modification, or data loss.",
        "Information Security",
        "Continuous enforcement",
    ),
    (
        "9",
        "Entrusting Processing to Third Parties (Outsourcing)",
        "Processing of personal data may be assigned to a third party by contract or law only if the data are processed in the same manner as the controller is permitted, and no statutory confidentiality duty is breached.",
        "Vendor & Processor Management",
        "Prior to entrustment & annual review",
    ),
    (
        "16",
        "Disclosure of Personal Data Abroad (Cross-Border Transfers)",
        "Personal data may only be disclosed outside Switzerland if the receiving state provides adequate data protection (Federal Council list) or if adequate safeguards (such as standard clauses approved by FDPIC) are established.",
        "International Transfers",
        "Prior to transfer & annual review",
    ),
    (
        "19",
        "Duty to Inform Data Subjects (Transparency)",
        "The controller must inform the data subject appropriately of the collection of personal data, including the controller's identity, contact details, the processing purposes, and any foreign recipient jurisdictions.",
        "Transparency & Notice",
        "At data collection",
    ),
    (
        "22",
        "Data Protection Impact Assessment (DPIA)",
        "If a planned processing operation may lead to a high risk to the personality or fundamental rights of the data subject, the controller must carry out a data protection impact assessment in advance.",
        "Risk Assessment & DPIA",
        "Prior to high-risk processing",
    ),
    (
        "24",
        "Data Security Breach Notification to the FDPIC",
        "The controller must notify the Federal Data Protection and Information Commissioner (FDPIC / EDÖB) as quickly as possible of any data security breach that is likely to result in a high risk to the data subject.",
        "Incident Management",
        "As quickly as possible upon awareness",
    ),
]

FADP_CONTROLS: list[PackControlDefinition] = []
FADP_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
FADP_MAPPINGS: list[PackMappingDefinition] = []
FADP_EVIDENCE: list[PackEvidenceDefinition] = []
FADP_COVERAGE: list[PackCoverageDefinition] = []

for idx, (art_num, title, desc, cat, cadence) in enumerate(FADP_ARTICLES, start=1):
    ctrl_id = f"CH-FADP-Art-{art_num}"
    src_ref = f"Swiss FADP Article {art_num}"

    guidance = (
        f"**Implementation Guidance:** Implement operational policies and technical safeguards for {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Policy documents, system design reviews, processor agreements, transfer mechanisms, or DPIA records for {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Swiss Federal Data Protection & Privacy Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    FADP_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    FADP_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=FADP_AUTHORITY,
            edition_or_amendment=FADP_EDITION,
            source_text=desc,
            content_rights=FADP_RIGHTS,
            source_url=FADP_URL,
            conformly_guidance=f"Ensure Swiss FADP compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    FADP_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} satisfies Swiss FADP statutory obligation {src_ref}.",
        )
    )

    FADP_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-CH-FADP-Art-{art_num}",
            title=f"Evidence for {title}",
            description=f"Operational policy, privacy notice, third-party contract, DPIA assessment, or FDPIC incident procedure for {src_ref}.",
            evidence_type="POLICY_DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    FADP_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Swiss FADP Article {art_num} covered by control {ctrl_id}.",
        )
    )

CH_FADP_PACK = FrameworkPackDefinition(
    slug="ch-fadp",
    name="Swiss Federal Act on Data Protection (nFADP / revDSG)",
    version="v2023",
    description="Swiss Federal Act on Data Protection (nFADP / revDSG, SR 235.1) in force September 1, 2023.",
    release_notes="Active release pack covering Swiss data processing principles, privacy by design/default, outsourcing, cross-border data transfer, and FDPIC breach reporting.",
    legal_review_notes="Statutory requirements extracted directly from the Swiss Federal Act on Data Protection (SR 235.1).",
    approval_notes="Approved for Module A active framework catalog.",
    controls=FADP_CONTROLS,
    source_requirements=FADP_SOURCE_REQS,
    mappings=FADP_MAPPINGS,
    evidence_specifications=FADP_EVIDENCE,
    coverage_ledger=FADP_COVERAGE,
)
