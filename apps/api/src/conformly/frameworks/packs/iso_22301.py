"""ISO 22301:2019 Business Continuity Management Systems (BCMS) Pack Definition.

Covers:
- BCMS management clauses 4 to 10 for operational resilience
- Business Impact Analysis (BIA), Maximum Tolerable Period of Disruption (MTPD), RTO/RPO
- Incident response structures, business continuity procedures, and exercise programmes
- Complete coverage ledger accounting for all 10 requirements with IMPLEMENTED disposition
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

ISO22301_AUTHORITY = "International Organization for Standardization (ISO)"
ISO22301_EDITION = "ISO 22301:2019 (Security and resilience — Business continuity management systems — Requirements)"
ISO22301_RIGHTS = "Copyright ISO. Citations and titles used for reference; proprietary standard text not redistributed verbatim. Guidance and procedures by Conformly."
ISO22301_URL = "https://www.iso.org/standard/75106.html"

ISO22301_CLAUSES: list[tuple[str, str, str, str, str]] = [
    (
        "4.1",
        "Understanding Context of the Organization & BCMS Scope",
        "Determine external and internal factors, legal and regulatory requirements, and critical dependencies establishing the operational boundaries of the Business Continuity Management System.",
        "Context & Scope",
        "Annual review",
    ),
    (
        "5.1",
        "Leadership Commitment & Business Continuity Policy",
        "Top management demonstrates leadership by establishing a formal business continuity policy, allocating adequate resources, and assigning incident command authorities.",
        "Leadership & Governance",
        "Annual review",
    ),
    (
        "6.1",
        "Actions to Address Risks, Opportunities & Continuity Objectives",
        "Systematically identify and assess risks of operational disruption, defining measurable continuity objectives and mitigation programs across cloud, data center, and workforce pillars.",
        "Risk Planning",
        "Semi-annual / Major architecture change",
    ),
    (
        "8.2.2",
        "Business Impact Analysis (BIA) & Activity Prioritization",
        "Conduct a formal BIA to evaluate the impact over time of disruptions to business activities, establishing Maximum Tolerable Periods of Disruption (MTPD) and prioritized recovery order.",
        "Business Impact Analysis",
        "Annual review / Upon service launch",
    ),
    (
        "8.3",
        "Business Continuity Strategies & Recovery Targets (RTO / RPO)",
        "Select and implement continuity strategies and technical architectures to meet documented Recovery Time Objectives (RTO) and Recovery Point Objectives (RPO) for critical data and services.",
        "Continuity Strategies",
        "Annual strategy review",
    ),
    (
        "8.4.2",
        "Incident Response Structure & Crisis Management Teams",
        "Establish an incident command structure and emergency communication chain with clear authority to declare disruptions, execute escalations, and manage crisis response.",
        "Incident Response",
        "Annual review / Upon staffing change",
    ),
    (
        "8.4.3",
        "Business Continuity & Disaster Recovery Procedures (BCP / DRP)",
        "Document, maintain, and publish step-by-step business continuity and technical disaster recovery plans detailing manual workarounds, failover triggers, and system restoration steps.",
        "Continuity Procedures",
        "Semi-annual plan review",
    ),
    (
        "8.5",
        "Exercise Programme, Tabletop Drills & Failover Testing",
        "Conduct scheduled continuity exercises, crisis simulation tabletops, and live multi-region technical failover drills to validate that plans function effectively under disaster scenarios.",
        "Testing & Exercises",
        "Semi-annual drill / Annual live failover",
    ),
    (
        "9.1",
        "BCMS Monitoring, Measurement, Analysis & Evaluation",
        "Monitor key resilience metrics, disaster recovery test results, backup integrity verifications, and operational readiness to evaluate BCMS performance.",
        "Performance Evaluation",
        "Quarterly metrics review",
    ),
    (
        "10.1",
        "Post-Incident Review, Corrective Actions & Continual Improvement",
        "Conduct formal post-incident debriefs following exercises or real-world disruptions, tracking corrective actions to closure and continually improving organizational resilience.",
        "Continual Improvement",
        "Event-driven within 14 days of drill/incident",
    ),
]

ISO22301_CONTROLS: list[PackControlDefinition] = []
ISO22301_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
ISO22301_MAPPINGS: list[PackMappingDefinition] = []
ISO22301_EVIDENCE: list[PackEvidenceDefinition] = []
ISO22301_COVERAGE: list[PackCoverageDefinition] = []

for idx, (clause_id, title, desc, cat, cadence) in enumerate(ISO22301_CLAUSES, start=1):
    ctrl_id = f"ISO22301-{clause_id.replace('.', '-')}"
    src_ref = f"ISO 22301:2019 Clause {clause_id}"

    guidance = (
        f"**Implementation Guidance:** Implement organizational resilience policies, operational continuity procedures, and testing evidence to satisfy {title} under {src_ref}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented BCMS policy, approved BIA reports, crisis escalation matrices, disaster recovery runbooks, drill results, or post-incident action trackers satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Business Continuity & Disaster Recovery Management Policy\n"
        f"**Standard Citation:** {src_ref}"
    )

    ISO22301_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    ISO22301_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.CLAUSE,
            source_authority=ISO22301_AUTHORITY,
            edition_or_amendment=ISO22301_EDITION,
            source_text=desc,
            content_rights=ISO22301_RIGHTS,
            source_url=ISO22301_URL,
            conformly_guidance=f"Implement business continuity controls satisfying {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    ISO22301_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Conformly control {ctrl_id} directly satisfies {src_ref}.",
        )
    )

    ISO22301_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-ISO22301-{clause_id.replace('.', '_')}",
            title=f"Evidence for {title}",
            description=f"Auditor-ready artifacts, test reports, BIA documents, and recovery evidence verifying compliance with {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    ISO22301_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Fully implemented by canonical control {ctrl_id} and verified by disaster recovery exercises.",
        )
    )

ISO_22301_PACK = FrameworkPackDefinition(
    slug="iso-22301",
    name="ISO 22301:2019 Business Continuity Management Systems (BCMS)",
    version="v2019",
    description="International standard for Business Continuity Management Systems specifying requirements to implement, maintain, and continually improve operational resilience against disruptive incidents.",
    release_notes="Production release of ISO 22301:2019 BCMS pre-audit framework pack.",
    legal_review_notes="Reviewed against ISO 22301:2019 clauses and international resilience standards.",
    approval_notes="Approved for Module B active framework catalog.",
    controls=ISO22301_CONTROLS,
    source_requirements=ISO22301_SOURCE_REQS,
    mappings=ISO22301_MAPPINGS,
    evidence_specifications=ISO22301_EVIDENCE,
    coverage_ledger=ISO22301_COVERAGE,
)
