"""SOC 1 / SSAE 18 (Internal Control over Financial Reporting) Pack Definition.

Covers:
- SSAE No. 18 / AT-C Section 320 control objectives for service organizations
- Core IT General Controls (ITGC) impacting customer financial systems: Access, Change Management, Operations
- Segregation of Duties (SoD), interface reconciliations, and subservice organization oversight
- Auditor-ready evidence requests, review cadences, and coverage ledger
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

SOC1_AUTHORITY = "American Institute of Certified Public Accountants (AICPA)"
SOC1_EDITION = "SSAE No. 18 / AT-C Section 320 (SOC 1: Reporting on Controls Relevant to User Entities' Internal Control over Financial Reporting)"
SOC1_RIGHTS = "Copyright AICPA. Citations and titles used for reference; proprietary standard text not redistributed verbatim. Guidance and procedures by Conformly."
SOC1_URL = "https://www.aicpa-cima.com/resources/landing/system-and-organization-controls-soc-1"

SOC1_OBJECTIVES: list[tuple[str, str, str, str, str]] = [
    (
        "CO-01",
        "Control Environment & Financial Integrity Governance",
        "Management establishes and enforces formal organizational structures, ethical standards, job descriptions, and supervisory reviews to ensure internal control over services impacting financial data.",
        "Governance & Environment",
        "Annual review",
    ),
    (
        "CO-02",
        "User Access Authorization & Role-Based Provisioning",
        "Controls provide reasonable assurance that user access to financial systems, databases, and application functions is appropriately authorized, provisioned according to least privilege, and documented.",
        "Logical Access",
        "Continuous / Quarterly access review",
    ),
    (
        "CO-03",
        "Privileged Access Management & Segregation of Incompatible Duties",
        "Controls provide reasonable assurance that privileged administrative access is strictly restricted, monitored, and segregated so that no individual has end-to-end control over transaction processing or financial adjustments.",
        "Logical Access",
        "Continuous / Monthly review of admin actions",
    ),
    (
        "CO-04",
        "User Authentication, Password Controls & Multi-Factor Enforcement",
        "Controls provide reasonable assurance that access to applications and systems supporting financial processes requires unique user identification, strong authentication, and enforced multi-factor authentication.",
        "Logical Access",
        "Continuous",
    ),
    (
        "CO-05",
        "Application and Infrastructure Change Management & Gating",
        "Controls provide reasonable assurance that changes to financial applications, transaction engines, and hosting infrastructure are formally requested, tested in staging, independently reviewed, and approved prior to production deployment.",
        "Change Management",
        "Continuous / Every release",
    ),
    (
        "CO-06",
        "Batch Job Scheduling, Processing Integrity & Exception Handling",
        "Controls provide reasonable assurance that batch processing jobs, ledger interface synchronizations, and data pipelines execute completely, accurately, and without unauthorized alteration, with job failure alerting.",
        "Computer Operations",
        "Continuous / Real-time alerts",
    ),
    (
        "CO-07",
        "Data Backup Integrity, Offsite Replication & Disaster Recovery",
        "Controls provide reasonable assurance that transaction data, database snapshots, and system configurations are backed up on a scheduled basis, encrypted, replicated to separate regions, and tested for recoverability.",
        "Computer Operations",
        "Daily automated backups / Annual recovery drill",
    ),
    (
        "CO-08",
        "Physical Facility Security & Environmental Safeguards",
        "Controls provide reasonable assurance that physical access to primary data centers, hosting facilities, and networking infrastructure is restricted to authorized personnel and protected against environmental hazards.",
        "Physical Security",
        "Continuous / Semi-annual badge audit",
    ),
    (
        "CO-09",
        "Subservice Organization Due Diligence & Vendor Oversight",
        "Controls provide reasonable assurance that subservice organizations (e.g. cloud hosting providers) are periodically evaluated via SOC 1 / SOC 2 type examination reports and complementary user entity controls (CUECs).",
        "Vendor Management",
        "Annual review per subservice provider",
    ),
    (
        "CO-10",
        "Operational Incident Escalation & Financial Anomaly Management",
        "Controls provide reasonable assurance that operational exceptions, data transmission failures, and security incidents with potential financial reporting impact are promptly identified, escalated, investigated, and remediated.",
        "Incident Management",
        "Event-driven within 4 hours / Annual drill",
    ),
]

SOC1_CONTROLS: list[PackControlDefinition] = []
SOC1_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
SOC1_MAPPINGS: list[PackMappingDefinition] = []
SOC1_EVIDENCE: list[PackEvidenceDefinition] = []
SOC1_COVERAGE: list[PackCoverageDefinition] = []

for idx, (obj_id, title, desc, cat, cadence) in enumerate(SOC1_OBJECTIVES, start=1):
    ctrl_id = f"SOC1-{obj_id}"
    src_ref = f"SSAE 18 AT-C 320 {obj_id}"

    guidance = (
        f"**Implementation Guidance:** Establish policies, IT general controls, and operational audit evidence to satisfy {title} under {src_ref}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented policies, change tickets, access review signoffs, backup restoration logs, or SOC 1 bridge letters demonstrating operational effectiveness for {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** SOC 1 / Financial ITGC & Internal Controls Policy\n"
        f"**Auditor Citation:** {src_ref}"
    )

    SOC1_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    SOC1_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.REQUIREMENT,
            source_authority=SOC1_AUTHORITY,
            edition_or_amendment=SOC1_EDITION,
            source_text=desc,
            content_rights=SOC1_RIGHTS,
            source_url=SOC1_URL,
            conformly_guidance=f"Implement controls satisfying {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    SOC1_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Conformly control {ctrl_id} directly satisfies {src_ref}.",
        )
    )

    SOC1_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-SOC1-{obj_id.replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"Auditor-ready artifacts, system logs, approval records, and sampling evidence demonstrating compliance with {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    SOC1_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Fully implemented by canonical control {ctrl_id} and verified by internal control documentation.",
        )
    )

SOC_1_PACK = FrameworkPackDefinition(
    slug="soc-1",
    name="SOC 1 / SSAE 18 (Internal Control over Financial Reporting)",
    version="v2017",
    description="SOC 1 Type I & Type II examination readiness framework for service organizations whose systems process, store, or transmit financial transactions impacting customer internal controls.",
    release_notes="Production release of SOC 1 / SSAE 18 (AT-C Section 320) examination pack.",
    legal_review_notes="Reviewed against AICPA SSAE No. 18 / AT-C Section 320 and PCAOB attestation standards.",
    approval_notes="Approved for Module B active framework catalog.",
    controls=SOC1_CONTROLS,
    source_requirements=SOC1_SOURCE_REQS,
    mappings=SOC1_MAPPINGS,
    evidence_specifications=SOC1_EVIDENCE,
    coverage_ledger=SOC1_COVERAGE,
)
