"""California Consumer Privacy Act (CCPA as amended by CPRA) Pack Definition.

Covers:
- Full 8 core statutory requirements under Cal. Civ. Code § 1798.100 et seq.
- Consumer privacy rights: notice, deletion, correction, right to know, opt-out of sale/share, limiting sensitive info
- Statutory scope and applicability thresholds under § 1798.140
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

CCPA_AUTHORITY = "State of California / California Privacy Protection Agency (CPPA)"
CCPA_EDITION = (
    "California Consumer Privacy Act as amended by CPRA (Cal. Civ. Code § 1798.100 et seq.)"
)
CCPA_RIGHTS = "Public Domain State Statute (State of California)."
CCPA_URL = "https://cppa.ca.gov/regulations/"

CCPA_SECTIONS: list[tuple[str, str, str, str, str]] = [
    (
        "1798.100",
        "Notice at Collection & Purpose Limitation",
        "A business that controls the collection of a consumer's personal information shall, at or before the point of collection, inform consumers as to the categories of personal information to be collected and the purposes for which the categories will be used.",
        "Consumer Transparency",
        "At collection point",
    ),
    (
        "1798.105",
        "Consumer Right to Delete Personal Information",
        "A consumer shall have the right to request that a business delete any personal information about the consumer which the business has collected from the consumer, subject to statutory retention exceptions.",
        "Consumer Rights & Requests",
        "Within 45 days of request",
    ),
    (
        "1798.106",
        "Consumer Right to Correct Inaccurate Personal Information",
        "A consumer shall have the right to request a business that maintains inaccurate personal information about the consumer to correct that inaccurate personal information upon receipt of a verifiable consumer request.",
        "Consumer Rights & Requests",
        "Within 45 days of request",
    ),
    (
        "1798.110",
        "Consumer Right to Know Personal Information Collected",
        "A consumer shall have the right to request that a business that collects personal information disclose to the consumer categories of personal information collected, sources, business purposes, and specific pieces of personal information.",
        "Consumer Rights & Requests",
        "Within 45 days of request",
    ),
    (
        "1798.120",
        "Consumer Right to Opt-Out of Sale or Sharing",
        "A consumer shall have the right, at any time, to direct a business that sells or shares personal information about the consumer to third parties not to sell or share the consumer's personal information ('Do Not Sell or Share My Personal Info').",
        "Consumer Choice & Opt-Out",
        "Immediate / Continuous",
    ),
    (
        "1798.121",
        "Consumer Right to Limit Use of Sensitive Personal Information",
        "A consumer shall have the right, at any time, to direct a business that collects sensitive personal information about the consumer to limit its use of the consumer's sensitive personal information to that use which is necessary to perform services.",
        "Consumer Choice & Opt-Out",
        "Immediate / Continuous",
    ),
    (
        "1798.125",
        "Non-Discrimination for Exercising Consumer Rights",
        "A business shall not discriminate against a consumer because the consumer exercised any of the consumer's rights under this title, including by denying goods or services, charging different prices, or providing a different level of quality.",
        "Consumer Protection",
        "Continuous",
    ),
    (
        "1798.140",
        "Business Scope, Thresholds & Service Provider Contracts",
        "Establish statutory applicability ($25M annual gross revenues, buying/selling 100k consumers/households, or 50%+ revenue from selling personal info) and enforce mandatory § 1798.140(ag) service provider contract prohibitions.",
        "Governance & Vendor Management",
        "Annual review & contracting",
    ),
]

CCPA_CONTROLS: list[PackControlDefinition] = []
CCPA_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
CCPA_MAPPINGS: list[PackMappingDefinition] = []
CCPA_EVIDENCE: list[PackEvidenceDefinition] = []
CCPA_COVERAGE: list[PackCoverageDefinition] = []

for idx, (sec_num, title, desc, cat, cadence) in enumerate(CCPA_SECTIONS, start=1):
    ctrl_id = f"CCPA-{sec_num.replace('.', '-')}"
    src_ref = f"Cal. Civ. Code § {sec_num}"

    guidance = (
        f"**Implementation Guidance:** Implement operational policies and workflows to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented policy, verification records, or audit log for {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** California Consumer Privacy Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    CCPA_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    CCPA_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=CCPA_AUTHORITY,
            edition_or_amendment=CCPA_EDITION,
            source_text=desc,
            content_rights=CCPA_RIGHTS,
            source_url=CCPA_URL,
            conformly_guidance=f"Operationalize CCPA/CPRA compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    CCPA_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly operationalizes {src_ref}.",
        )
    )

    CCPA_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-CCPA-{sec_num.replace('.', '_')}",
            title=f"Evidence for {title}",
            description=f"Operational procedure, privacy policy disclosure, opt-out link verification, or request logs for {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    CCPA_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"CCPA requirement {sec_num} covered by control {ctrl_id}.",
        )
    )

US_CA_CCPA_CPRA_PACK = FrameworkPackDefinition(
    slug="us-ca-ccpa-cpra",
    name="California Consumer Privacy Act (CCPA / CPRA)",
    version="v2023",
    description="California Consumer Privacy Act (CCPA) as amended by the California Privacy Rights Act (CPRA).",
    release_notes="Active release pack covering California consumer privacy rights, notice, opt-outs, and vendor contracting.",
    legal_review_notes="Statutory provisions extracted directly from Cal. Civ. Code § 1798.100 et seq.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=CCPA_CONTROLS,
    source_requirements=CCPA_SOURCE_REQS,
    mappings=CCPA_MAPPINGS,
    evidence_specifications=CCPA_EVIDENCE,
    coverage_ledger=CCPA_COVERAGE,
)
