"""SOC 3 (AICPA Trust Services Criteria for General Use) Pack Definition.

Covers:
- General use public assurance reporting based on AICPA Trust Services Criteria (TSP Section 100)
- Management assertion and public practitioner attestation packaging
- Public system description preparation without exposing confidential technical configurations
- Complete coverage ledger accounting for all 8 criteria with IMPLEMENTED disposition
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

SOC3_AUTHORITY = "American Institute of Certified Public Accountants (AICPA)"
SOC3_EDITION = "AICPA TSP Section 100 / Trust Services Criteria for General Use (SOC 3)"
SOC3_RIGHTS = "Copyright AICPA. Citations and titles used for reference; proprietary criteria text not redistributed verbatim. Guidance and procedures by Conformly."
SOC3_URL = "https://www.aicpa-cima.com/resources/landing/system-and-organization-controls-soc-3"

SOC3_CRITERIA: list[tuple[str, str, str, str, str]] = [
    (
        "SOC3.1",
        "Public Management Assertion of Operational Effectiveness",
        "Executive management prepares and signs a formal assertion that controls over the system were effective throughout the specified period based on the AICPA Trust Services Criteria.",
        "Public Assurance Governance",
        "Annual review / Period end",
    ),
    (
        "SOC3.2",
        "Public System Description & Boundary Disclosures",
        "Prepare a standardized, public-facing system description detailing infrastructure, software, people, procedures, and data boundaries while omitting sensitive internal topology or confidential IP.",
        "System Transparency",
        "Annual update / Major release",
    ),
    (
        "SOC3.3",
        "Security Trust Category Public Validation",
        "Maintain evidence that the system was protected against unauthorized access, unauthorized disclosure, and damage that could compromise the achievement of security commitments.",
        "Trust Services Criteria",
        "Continuous / Annual audit",
    ),
    (
        "SOC3.4",
        "Availability Trust Category Public Validation",
        "Maintain evidence that the system and services were available for operation and use as committed or agreed with external customer agreements and service level targets.",
        "Trust Services Criteria",
        "Continuous / Quarterly review",
    ),
    (
        "SOC3.5",
        "Confidentiality Trust Category Public Validation",
        "Maintain evidence that information designated as confidential was protected in accordance with documented commitments and business partner obligations.",
        "Trust Services Criteria",
        "Continuous",
    ),
    (
        "SOC3.6",
        "Independent Auditor Attestation Packaging",
        "Engage an independent licensed CPA firm to perform an examination under SSAE No. 18 / AT-C Section 205 and issue an unqualified SOC 3 public auditor attestation report.",
        "Independent Attestation",
        "Annual examination",
    ),
    (
        "SOC3.7",
        "Public Compliance Profile & Trust Center Distribution",
        "Publish the SOC 3 practitioner's report, management assertion, and Conformly verified seal to the public compliance profile or Customer Trust Center without requiring non-disclosure agreements (NDAs).",
        "Public Distribution",
        "Continuous / Upon report issuance",
    ),
    (
        "SOC3.8",
        "Continuous Monitoring & Subsequent Period Bridge Attestation",
        "Evaluate significant system changes occurring between examination cycles and issue formal management gap letters (bridge letters) to verify continued control effectiveness.",
        "Continuous Assurance",
        "Event-driven / Semi-annual bridge review",
    ),
]

SOC3_CONTROLS: list[PackControlDefinition] = []
SOC3_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
SOC3_MAPPINGS: list[PackMappingDefinition] = []
SOC3_EVIDENCE: list[PackEvidenceDefinition] = []
SOC3_COVERAGE: list[PackCoverageDefinition] = []

for idx, (crit_id, title, desc, cat, cadence) in enumerate(SOC3_CRITERIA, start=1):
    ctrl_id = f"SOC3-{crit_id.replace('.', '-')}"
    src_ref = f"AICPA SOC 3 Criteria {crit_id}"

    guidance = (
        f"**Implementation Guidance:** Operationalize procedures, public documentation packages, and external attestation evidence to satisfy {title} under {src_ref}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Signed management assertion, public system description draft, CPA firm engagement letter, published SOC 3 report, or bridge letter records demonstrating fulfillment of {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** SOC 3 Public Assurance & Customer Transparency Policy\n"
        f"**Auditor Citation:** {src_ref}"
    )

    SOC3_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    SOC3_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.REQUIREMENT,
            source_authority=SOC3_AUTHORITY,
            edition_or_amendment=SOC3_EDITION,
            source_text=desc,
            content_rights=SOC3_RIGHTS,
            source_url=SOC3_URL,
            conformly_guidance=f"Implement procedures satisfying {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    SOC3_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Conformly control {ctrl_id} directly satisfies {src_ref}.",
        )
    )

    SOC3_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-SOC3-{crit_id.replace('.', '_')}",
            title=f"Evidence for {title}",
            description=f"Auditor-ready artifacts, management signoffs, and published trust materials demonstrating adherence to {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Public",
        )
    )

    SOC3_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Fully implemented by canonical control {ctrl_id} and verified by public assurance workflows.",
        )
    )

SOC_3_PACK = FrameworkPackDefinition(
    slug="soc-3",
    name="SOC 3 (AICPA Trust Services Criteria for General Use)",
    version="v2022",
    description="SOC 3 general use public assurance framework enabling organizations to demonstrate auditor-verified compliance with AICPA Trust Services Criteria publicly without disclosing proprietary system details.",
    release_notes="Production release of SOC 3 general public assurance compliance pack.",
    legal_review_notes="Reviewed against AICPA TSP Section 100 and SSAE No. 18 / AT-C Section 205 public attestation standards.",
    approval_notes="Approved for Module B active framework catalog.",
    controls=SOC3_CONTROLS,
    source_requirements=SOC3_SOURCE_REQS,
    mappings=SOC3_MAPPINGS,
    evidence_specifications=SOC3_EVIDENCE,
    coverage_ledger=SOC3_COVERAGE,
)
