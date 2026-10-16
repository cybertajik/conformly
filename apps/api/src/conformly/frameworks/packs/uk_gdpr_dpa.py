"""UK GDPR & Data Protection Act 2018 Pack Definition.

Covers:
- Post-Brexit United Kingdom data protection regime (retained EU Regulation 2016/679 & DPA 2018)
- Data protection principles, lawful basis, privacy notices, DSARs, processor contracts, security of processing, breach notification to ICO, and UK international transfers (IDTA / Addendum)
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

UK_GDPR_AUTHORITY = "Information Commissioner's Office (ICO) / UK Parliament"
UK_GDPR_EDITION = "Data Protection Act 2018 (c. 12) & Retained UK GDPR (SI 2019/419 as amended)"
UK_GDPR_RIGHTS = (
    "Contains public sector information licensed under the Open Government Licence v3.0."
)
UK_GDPR_URL = "https://ico.org.uk/for-organisations/data-protection-and-the-eu/"

UK_GDPR_ARTICLES: list[tuple[str, str, str, str, str]] = [
    (
        "5",
        "UK GDPR Principles Relating to Processing",
        "Personal data shall be processed lawfully, fairly, and transparently; collected for specified, explicit purposes; adequate, relevant, limited; accurate; kept no longer than necessary; and secured with appropriate integrity and confidentiality.",
        "Data Protection Governance",
        "Continuous compliance",
    ),
    (
        "6",
        "Lawful Bases for Processing Personal Data",
        "Processing shall be lawful only if and to the extent that at least one statutory legal basis applies: consent, contract performance, legal obligation, vital interests, public task, or legitimate interests.",
        "Lawful Basis & Consent",
        "Prior to processing & annual review",
    ),
    (
        "13",
        "Information to be Provided (Privacy Notice)",
        "Where personal data are collected from the data subject, the controller shall provide the identity of the controller, DPO details, processing purposes, legal bases, retention periods, and data subject rights.",
        "Transparency & Notice",
        "At collection & annual review",
    ),
    (
        "15",
        "Right of Access by the Data Subject (UK DSAR)",
        "The data subject shall have the right to obtain confirmation as to whether personal data concerning them are being processed, access to the personal data, and statutory disclosure details without undue delay and at the latest within one month.",
        "Data Subject Rights",
        "Within 1 month of request",
    ),
    (
        "28",
        "Processor Contracts & Written Terms",
        "Where processing is carried out on behalf of a controller, the controller shall use only processors providing sufficient guarantees and govern processing with a binding written contract setting out statutory Article 28(3) terms.",
        "Vendor & Processor Management",
        "Prior to engagement & annual review",
    ),
    (
        "32",
        "Security of Processing (Technical & Organizational Measures)",
        "Implement appropriate technical and organizational measures to ensure a level of security appropriate to the risk, including encryption of personal data, ongoing confidentiality and resilience, and regular security testing.",
        "Information Security",
        "Continuous enforcement",
    ),
    (
        "33",
        "Notification of a Personal Data Breach to the ICO",
        "In the case of a personal data breach likely to result in a risk to individuals' rights and freedoms, notify the Information Commissioner's Office (ICO) without undue delay and, where feasible, not later than 72 hours after becoming aware.",
        "Incident Management",
        "Within 72 hours of awareness",
    ),
    (
        "44",
        "Transfers of Personal Data to Third Countries (UK IDTA)",
        "Any transfer of personal data to a third country shall take place only where the territory ensures an adequate level of protection, or subject to appropriate safeguards such as the UK International Data Transfer Agreement (IDTA) or UK Addendum to EU SCCs.",
        "International Transfers",
        "Prior to transfer & periodic review",
    ),
]

UK_GDPR_CONTROLS: list[PackControlDefinition] = []
UK_GDPR_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
UK_GDPR_MAPPINGS: list[PackMappingDefinition] = []
UK_GDPR_EVIDENCE: list[PackEvidenceDefinition] = []
UK_GDPR_COVERAGE: list[PackCoverageDefinition] = []

for idx, (art_num, title, desc, cat, cadence) in enumerate(UK_GDPR_ARTICLES, start=1):
    ctrl_id = f"UK-GDPR-Art-{art_num}"
    src_ref = f"UK GDPR Article {art_num}"

    guidance = (
        f"**Implementation Guidance:** Implement operational policies and technical safeguards for {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Policy documents, privacy notices, DSAR logs, processor agreements, or breach procedures for {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** UK Data Protection & Privacy Operations Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    UK_GDPR_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    UK_GDPR_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=UK_GDPR_AUTHORITY,
            edition_or_amendment=UK_GDPR_EDITION,
            source_text=desc,
            content_rights=UK_GDPR_RIGHTS,
            source_url=UK_GDPR_URL,
            conformly_guidance=f"Ensure UK GDPR and DPA 2018 compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    UK_GDPR_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} satisfies UK GDPR statutory obligation {src_ref}.",
        )
    )

    UK_GDPR_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-UK-GDPR-Art-{art_num}",
            title=f"Evidence for {title}",
            description=f"Record of processing activity, privacy notice, DPA contract, or ICO notification record for {src_ref}.",
            evidence_type="POLICY_DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    UK_GDPR_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"UK GDPR Article {art_num} covered by control {ctrl_id}.",
        )
    )

UK_GDPR_DPA_PACK = FrameworkPackDefinition(
    slug="uk-gdpr-dpa",
    name="UK GDPR & Data Protection Act 2018",
    version="v2021",
    description="United Kingdom General Data Protection Regulation and Data Protection Act 2018 post-Brexit regime.",
    release_notes="Active release pack covering UK privacy principles, lawful processing, DSARs, vendor contracts, ICO breach reporting, and UK IDTA international transfers.",
    legal_review_notes="Statutory requirements extracted directly from Retained UK GDPR and Data Protection Act 2018.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=UK_GDPR_CONTROLS,
    source_requirements=UK_GDPR_SOURCE_REQS,
    mappings=UK_GDPR_MAPPINGS,
    evidence_specifications=UK_GDPR_EVIDENCE,
    coverage_ledger=UK_GDPR_COVERAGE,
)
