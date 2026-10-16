"""Morocco Personal Data Protection Law (Law No. 09-08) Pack Definition.

Covers:
- Kingdom of Morocco personal data protection regime under Dahir No. 1-09-15 & Law No. 09-08
- Data quality principles, unambiguous consent, right of information, access/rectification/opposition rights, technical security obligations, and CNDP cross-border transfer authorizations
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

MA_CNDP_AUTHORITY = (
    "Commission Nationale de contrôle de la protection des Données à caractère Personnel (CNDP)"
)
MA_CNDP_EDITION = "Dahir No. 1-09-15 promulgating Law No. 09-08 on Personal Data Protection"
MA_CNDP_RIGHTS = "Official Kingdom of Morocco Legislation (CNDP)."
MA_CNDP_URL = "https://www.cndp.ma/textes-et-lois/"

MA_CNDP_ARTICLES: list[tuple[str, str, str, str, str]] = [
    (
        "3",
        "Quality and Purpose Specification Principles",
        "Personal data must be processed fairly and lawfully; collected for specified, explicit, and legitimate purposes; adequate, relevant, and not excessive; accurate and kept up to date; and preserved in identifiable form only as long as necessary.",
        "Data Protection Governance",
        "Continuous compliance",
    ),
    (
        "4",
        "Unambiguous Consent & Lawful Processing",
        "Processing of personal data can only be carried out if the person concerned has unambiguously given their consent, unless processing is necessary for performance of a contract, compliance with a legal obligation, or protection of legitimate interest.",
        "Lawful Basis & Consent",
        "Prior to processing & annual review",
    ),
    (
        "7",
        "Right of Information & Mandatory Notice",
        "The controller must provide the data subject with information regarding the controller's identity, processing purposes, recipients of the data, and whether answers are mandatory, along with rights of access and rectification.",
        "Transparency & Notice",
        "At data collection",
    ),
    (
        "8",
        "Rights of Access, Rectification & Opposition",
        "Guarantee data subject rights: right to obtain verification and copies of personal data without constraint, right to rectify or erase incomplete or inaccurate data, and right to oppose processing on legitimate grounds.",
        "Data Subject Rights",
        "Within 30 days of request",
    ),
    (
        "23",
        "Confidentiality & Technical Security Safeguards",
        "The controller must implement appropriate technical and organizational measures to protect personal data against accidental or unlawful destruction, accidental loss, alteration, or unauthorized access or disclosure.",
        "Information Security",
        "Continuous enforcement",
    ),
    (
        "43",
        "Cross-Border Transfer & CNDP Authorization",
        "Personal data may not be transferred to a foreign state unless that state ensures an adequate level of protection, or transfer has been explicitly authorized by the CNDP under statutory exceptions or approved contractual clauses.",
        "International Transfers",
        "Prior to transfer & periodic review",
    ),
]

MA_CNDP_CONTROLS: list[PackControlDefinition] = []
MA_CNDP_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
MA_CNDP_MAPPINGS: list[PackMappingDefinition] = []
MA_CNDP_EVIDENCE: list[PackEvidenceDefinition] = []
MA_CNDP_COVERAGE: list[PackCoverageDefinition] = []

for idx, (art_num, title, desc, cat, cadence) in enumerate(MA_CNDP_ARTICLES, start=1):
    ctrl_id = f"MA-CNDP-Art-{art_num}"
    src_ref = f"Morocco Law No. 09-08 Article {art_num}"

    guidance = (
        f"**Implementation Guidance:** Implement operational policies and technical safeguards for {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Policy documents, consent records, privacy notices, access control configurations, or CNDP transfer authorization filings for {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Morocco Personal Data Protection & Privacy Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    MA_CNDP_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    MA_CNDP_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=MA_CNDP_AUTHORITY,
            edition_or_amendment=MA_CNDP_EDITION,
            source_text=desc,
            content_rights=MA_CNDP_RIGHTS,
            source_url=MA_CNDP_URL,
            conformly_guidance=f"Ensure compliance with Morocco Law No. 09-08 under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    MA_CNDP_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} satisfies Morocco Law 09-08 statutory obligation {src_ref}.",
        )
    )

    MA_CNDP_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-MA-CNDP-Art-{art_num}",
            title=f"Evidence for {title}",
            description=f"Consent record, privacy disclosure, security safeguards documentation, or CNDP cross-border filing for {src_ref}.",
            evidence_type="POLICY_DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    MA_CNDP_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Morocco Law 09-08 Article {art_num} covered by control {ctrl_id}.",
        )
    )

MA_CNDP_0908_PACK = FrameworkPackDefinition(
    slug="ma-cndp-0908",
    name="Morocco Personal Data Protection Law (Law No. 09-08)",
    version="v2009",
    description="Kingdom of Morocco Law No. 09-08 on Protection of Individuals with regard to the Processing of Personal Data.",
    release_notes="Active release pack covering Moroccan data processing principles, unambiguous consent, data subject rights, security measures, and CNDP cross-border transfer authorizations.",
    legal_review_notes="Statutory requirements extracted directly from Dahir No. 1-09-15 & Law No. 09-08.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=MA_CNDP_CONTROLS,
    source_requirements=MA_CNDP_SOURCE_REQS,
    mappings=MA_CNDP_MAPPINGS,
    evidence_specifications=MA_CNDP_EVIDENCE,
    coverage_ledger=MA_CNDP_COVERAGE,
)
