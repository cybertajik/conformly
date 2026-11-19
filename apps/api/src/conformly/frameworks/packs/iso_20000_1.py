"""ISO/IEC 20000-1:2018 IT Service Management System (SMS) Pack Definition.

Covers:
- Service management system requirements under ISO/IEC 20000-1:2018
- Service catalog, Service Level Agreements (SLAs), capacity & availability planning
- Incident management, service requests, problem resolution, and release management
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

ISO20000_1_AUTHORITY = "International Organization for Standardization (ISO) / IEC"
ISO20000_1_EDITION = "ISO/IEC 20000-1:2018 (Information technology — Service management — Part 1: Service management system requirements)"
ISO20000_1_RIGHTS = "Copyright ISO/IEC. Citations and titles used for reference; proprietary standard text not redistributed verbatim. Guidance and procedures by Conformly."
ISO20000_1_URL = "https://www.iso.org/standard/70636.html"

ISO20000_1_CLAUSES: list[tuple[str, str, str, str, str]] = [
    (
        "4.1",
        "Context of the Organization & Service Management Scope",
        "Determine external and internal factors, service portfolio dependencies, customer expectations, and statutory obligations defining the boundaries of the Service Management System.",
        "SMS Context & Scope",
        "Annual review",
    ),
    (
        "5.1",
        "Leadership, Service Management Policy & Authority",
        "Top management demonstrates commitment by establishing the service management policy, assigning service ownership roles, and ensuring resource allocation to meet service requirements.",
        "Leadership & Governance",
        "Annual review",
    ),
    (
        "8.2.2",
        "Service Portfolio & Customer Service Catalog Management",
        "Maintain an accurate, accessible service catalog detailing all active, planned, and retired services, including service descriptions, target user groups, and dependencies.",
        "Service Portfolio",
        "Quarterly review",
    ),
    (
        "8.3.2",
        "Service Level Agreements (SLAs) & Contractual Commitments",
        "Negotiate, agree, and document formal SLAs for each service provided, monitoring performance against committed uptime, response times, and resolution targets with regular reporting.",
        "Relationship Management",
        "Monthly SLA reporting / Annual review",
    ),
    (
        "8.4.1",
        "Service Availability & Capacity Management Planning",
        "Plan, monitor, and optimize infrastructure capacity, network bandwidth, and compute resources to ensure agreed service availability targets are consistently met.",
        "Supply & Demand",
        "Quarterly capacity review",
    ),
    (
        "8.5.1",
        "Service Design, Build & Production Transition",
        "Establish standardized processes to design, test in non-production environments, and transition new or modified services to live operations with rollback capabilities.",
        "Service Design & Transition",
        "Continuous / Per service release",
    ),
    (
        "8.6.1",
        "Incident Management & Service Request Fulfillment",
        "Implement a structured service desk ticketing system to log, prioritize, categorize, escalate, and resolve incidents and fulfill user service requests within defined SLA timeframes.",
        "Resolution & Fulfillment",
        "Continuous / Real-time queue monitoring",
    ),
    (
        "8.7.1",
        "Problem Management & Root Cause Analysis (RCA)",
        "Identify recurring incidents, perform root cause analyses (RCA), and implement permanent workarounds or structural code/infrastructure fixes to eliminate known errors.",
        "Service Assurance",
        "Event-driven / Monthly problem review",
    ),
    (
        "8.7.2",
        "Configuration Management & Configuration Item (CI) Database",
        "Maintain an accurate Configuration Management Database (CMDB) tracking all hardware, software, and service configuration items (CIs), versions, and interdependencies.",
        "Service Assurance",
        "Continuous / Automated inventory scan",
    ),
    (
        "9.1",
        "Service Performance Evaluation & Continual Service Improvement",
        "Conduct periodic customer satisfaction surveys, analyze service metrics and SLA attainment, and maintain a Continual Service Improvement (CSI) register to enhance service delivery.",
        "Continual Improvement",
        "Semi-annual survey / Monthly metrics",
    ),
]

ISO20000_1_CONTROLS: list[PackControlDefinition] = []
ISO20000_1_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
ISO20000_1_MAPPINGS: list[PackMappingDefinition] = []
ISO20000_1_EVIDENCE: list[PackEvidenceDefinition] = []
ISO20000_1_COVERAGE: list[PackCoverageDefinition] = []

for idx, (clause_id, title, desc, cat, cadence) in enumerate(ISO20000_1_CLAUSES, start=1):
    ctrl_id = f"ISO20000-1-{clause_id.replace('.', '-')}"
    src_ref = f"ISO/IEC 20000-1:2018 Clause {clause_id}"

    guidance = (
        f"**Implementation Guidance:** Implement operational ITSM procedures, ticketing workflows, and service management evidence to satisfy {title} under {src_ref}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented SMS policy, published service catalog, customer SLAs, monthly SLA performance reports, RCA documents, or CMDB export satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** IT Service Management (ITSM) & SLA Operations Policy\n"
        f"**Standard Citation:** {src_ref}"
    )

    ISO20000_1_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    ISO20000_1_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.CLAUSE,
            source_authority=ISO20000_1_AUTHORITY,
            edition_or_amendment=ISO20000_1_EDITION,
            source_text=desc,
            content_rights=ISO20000_1_RIGHTS,
            source_url=ISO20000_1_URL,
            conformly_guidance=f"Implement service management controls satisfying {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    ISO20000_1_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Conformly control {ctrl_id} directly satisfies {src_ref}.",
        )
    )

    ISO20000_1_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-ISO20000_1-{clause_id.replace('.', '_')}",
            title=f"Evidence for {title}",
            description=f"Auditor-ready artifacts, SLA attainment reports, CMDB snapshots, and change tickets verifying compliance with {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    ISO20000_1_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Fully implemented by canonical control {ctrl_id} and verified by ITSM reporting telemetry.",
        )
    )

ISO_20000_1_PACK = FrameworkPackDefinition(
    slug="iso-20000-1",
    name="ISO/IEC 20000-1:2018 IT Service Management System (SMS)",
    version="v2018",
    description="International standard for Information Technology Service Management specifying requirements to establish, implement, maintain, and continually improve an IT service management system.",
    release_notes="Production release of ISO/IEC 20000-1:2018 ITSM pre-audit framework pack.",
    legal_review_notes="Reviewed against ISO/IEC 20000-1:2018 clauses and international service delivery standards.",
    approval_notes="Approved for Module B active framework catalog.",
    controls=ISO20000_1_CONTROLS,
    source_requirements=ISO20000_1_SOURCE_REQS,
    mappings=ISO20000_1_MAPPINGS,
    evidence_specifications=ISO20000_1_EVIDENCE,
    coverage_ledger=ISO20000_1_COVERAGE,
)
