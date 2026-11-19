"""Japan Act on the Protection of Personal Information (APPI) Pack Definition.

Covers:
- Act No. 57 of 2003 as amended through 2020 and 2022 statutory reforms
- Personal Information Protection Commission (PPC) Guidelines
- Specification of purpose of use, safety management measures, employee & trustee supervision, mandatory breach reporting to PPC, and cross-border transfer requirements
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

JP_APPI_AUTHORITY = "Personal Information Protection Commission (PPC) Japan"
JP_APPI_EDITION = (
    "Act on the Protection of Personal Information (Act No. 57 of 2003 as amended) & PPC Guidelines"
)
JP_APPI_RIGHTS = "Japanese Statutory Public Domain (PPC Regulatory Framework)."
JP_APPI_URL = "https://www.ppc.go.jp/en/"

JP_APPI_ARTICLES: list[tuple[str, str, str, str, str]] = [
    (
        "Art-17",
        "Specification & Notice of Purpose of Use",
        "A Personal Information Handling Business Operator (PIHBO) must specify the purpose of use of personal information as explicitly as possible, and notify or publicly announce the purpose upon acquiring personal information.",
        "Purpose Limitation & Transparency",
        "At acquisition / Continuous",
    ),
    (
        "Art-20",
        "Safety Control Measures (System Security)",
        "A PIHBO must take necessary and appropriate measures for the security control of personal data, including organizational, personnel, physical, and technical safety control measures to prevent leakage, loss, or damage.",
        "Security Safeguards",
        "Continuous",
    ),
    (
        "Art-21",
        "Supervision of Personnel & Employees",
        "A PIHBO must exercise necessary and appropriate supervision over its employees to ensure the proper security control of personal data, including establishing security rules, training, and access logging.",
        "Internal Governance",
        "Annual training / Access review",
    ),
    (
        "Art-22",
        "Supervision of Trustees & Subcontractors",
        "When a PIHBO entrusts the handling of personal data to a third party in whole or in part, it must exercise necessary and appropriate supervision over the entrusted party, including contractual terms and security audits.",
        "Vendor Management",
        "Prior to entrustment / Annual review",
    ),
    (
        "Art-26",
        "Mandatory Leak Reporting to PPC & Notice to Individuals",
        "A PIHBO must report significant personal data leak incidents (or suspected leaks) to the PPC without delay, and notify affected individuals, in accordance with PPC reporting criteria and statutory deadlines.",
        "Incident Management",
        "Prompt preliminary notice / Formal 30-day report",
    ),
    (
        "Art-28",
        "Cross-Border Transfer Restrictions & Foreign Safeguards",
        "When providing personal data to a third party in a foreign country, a PIHBO must obtain prior consent with required information disclosures, or ensure the recipient maintains equivalent safety systems under PPC rules.",
        "International Transfers",
        "Prior to transfer / Regular review",
    ),
]

JP_APPI_CONTROLS: list[PackControlDefinition] = []
JP_APPI_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
JP_APPI_MAPPINGS: list[PackMappingDefinition] = []
JP_APPI_EVIDENCE: list[PackEvidenceDefinition] = []
JP_APPI_COVERAGE: list[PackCoverageDefinition] = []

for idx, (art_num, title, desc, cat, cadence) in enumerate(JP_APPI_ARTICLES, start=1):
    ctrl_id = f"JP-APPI-{art_num.replace('.', '-')}"
    src_ref = f"Japan APPI {art_num.replace('-', ' ')}"

    guidance = (
        f"**Implementation Guidance:** Implement operational policies and technical safeguards to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- PPC compliance procedure, security rule, or supervision record for {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Japanese Personal Information Protection Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    JP_APPI_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    JP_APPI_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=JP_APPI_AUTHORITY,
            edition_or_amendment=JP_APPI_EDITION,
            source_text=desc,
            content_rights=JP_APPI_RIGHTS,
            source_url=JP_APPI_URL,
            conformly_guidance=f"Operationalize Japanese PPC APPI compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    JP_APPI_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly operationalizes {src_ref}.",
        )
    )

    JP_APPI_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-JP-APPI-{art_num.replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"PPC compliance documentation, purpose notice, security rules, trustee agreement, or leak log supporting {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    JP_APPI_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"APPI requirement {art_num} covered by control {ctrl_id}.",
        )
    )

JP_APPI_PACK = FrameworkPackDefinition(
    slug="jp-appi",
    name="Japan Act on the Protection of Personal Information (APPI)",
    version="v2022",
    description="Japan Act on the Protection of Personal Information (APPI Act No. 57 of 2003 as amended) & PPC Guidelines.",
    release_notes="Active release pack covering Japanese PIHBO obligations, safety management measures, trustee supervision, breach reporting, and cross-border transfers.",
    legal_review_notes="Statutory provisions aligned with current Japanese PPC enforcement standards.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=JP_APPI_CONTROLS,
    source_requirements=JP_APPI_SOURCE_REQS,
    mappings=JP_APPI_MAPPINGS,
    evidence_specifications=JP_APPI_EVIDENCE,
    coverage_ledger=JP_APPI_COVERAGE,
)
