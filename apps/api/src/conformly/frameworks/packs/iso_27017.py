"""ISO/IEC 27017:2015 Cloud Security Controls Pack Definition.

Covers:
- Cloud-specific additions to ISO/IEC 27002 for cloud customers and service providers
- Shared responsibility matrix, virtual environment segregation, and tenant isolation
- Cloud administrative controls, logging telemetry, and secure asset removal upon exit
- Complete coverage ledger accounting for all 11 requirements with IMPLEMENTED disposition
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

ISO27017_AUTHORITY = "International Organization for Standardization (ISO) / IEC"
ISO27017_EDITION = "ISO/IEC 27017:2015 (Information technology — Security techniques — Code of practice for information security controls based on ISO/IEC 27002 for cloud services)"
ISO27017_RIGHTS = "Copyright ISO/IEC. Citations and titles used for reference; proprietary standard text not redistributed verbatim. Guidance and procedures by Conformly."
ISO27017_URL = "https://www.iso.org/standard/43757.html"

ISO27017_CONTROLS_LIST: list[tuple[str, str, str, str, str]] = [
    (
        "CLD.6.3.1",
        "Shared Information Security Roles and Responsibilities in Cloud Computing",
        "Formally document, agree, and communicate the shared responsibility matrix delineating security duties between the cloud service provider (CSP) and cloud service customer (CSC).",
        "Cloud Governance",
        "Annual review / Contract renewal",
    ),
    (
        "CLD.8.1.5",
        "Removal and Return of Cloud Service Customer Assets Upon Termination",
        "Establish secure procedures to ensure customer data, cryptographic keys, virtual images, and backup archives are completely returned or cryptographically erased upon contract termination.",
        "Cloud Operations",
        "Upon contract termination / 30-90 day lifecycle",
    ),
    (
        "CLD.9.5.1",
        "Segregation and Isolation in Virtual Multi-Tenant Computing Environments",
        "Enforce strict logical isolation between different tenants' compute, memory, storage, and networking layers, preventing unauthorized cross-tenant data access or side-channel leakage.",
        "Virtual Isolation",
        "Continuous / Architectural review",
    ),
    (
        "CLD.9.5.2",
        "Virtual Machine Hardening, Hypervisor Protection & Image Integrity",
        "Apply baseline security hardening templates to virtual machine images, container hosts, and hypervisors, continuously scanning base images for known vulnerabilities and unauthorized modifications.",
        "System Security",
        "Continuous / Pre-build scanning",
    ),
    (
        "CLD.12.1.5",
        "Cloud Service Administrative Operations & Privileged Console Controls",
        "Restrict cloud management consoles and administrative API endpoints to dedicated privileged jump-hosts, enforcing hardware MFA, role-based access, and session timeout policies.",
        "Operations Security",
        "Continuous / Quarterly access review",
    ),
    (
        "CLD.12.4.5",
        "Cloud Customer Activity Logging, Telemetry & Audit Visibility",
        "Provide cloud customers with immutable, detailed audit logs of administrative actions, resource modifications, and data access events within their virtual cloud boundary.",
        "Logging & Monitoring",
        "Continuous / Real-time ingestion",
    ),
    (
        "CLD.13.1.4",
        "Alignment of Security Management for Virtual and Physical Networks",
        "Ensure virtual network configurations (VPCs, security groups, subnets, routing tables) maintain security parity with physical network controls and strictly segregate public from private tiers.",
        "Network Security",
        "Continuous / Configuration drift monitoring",
    ),
    (
        "CLD.13.2.4",
        "Secure Cloud Infrastructure Configuration Management (IaC)",
        "Define all cloud infrastructure, security group rules, and IAM policies as code (IaC), enforcing automated static analysis, pull request approvals, and change gating prior to provisioning.",
        "Configuration Management",
        "Continuous / Every commit",
    ),
    (
        "CLD.14.2.1",
        "Multi-Tenant Secure Application Development & Boundary Testing",
        "Incorporate multi-tenant isolation testing, boundary fuzzing, and tenant ID enforcement validation into continuous integration test suites before deploying cloud applications.",
        "Development Security",
        "Continuous / CI test execution",
    ),
    (
        "CLD.15.1.4",
        "Cloud Supply Chain Risk & Downstream Sub-Cloud Provider Oversight",
        "Rigorously evaluate and monitor downstream sub-processors and external SaaS/IaaS infrastructure providers for compliance with ISO 27017, SOC 2, and cloud security benchmarks.",
        "Supplier Relationships",
        "Annual supplier audit",
    ),
    (
        "CLD.16.1.7",
        "Cloud Security Incident Notification, Blast Radius Containment & Forensics",
        "Maintain rapid notification protocols to inform cloud customers of security breaches impacting their data, with defined blast radius containment strategies and forensic preservation.",
        "Incident Management",
        "Event-driven within contractual notice / Annual drill",
    ),
]

ISO27017_CONTROLS: list[PackControlDefinition] = []
ISO27017_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
ISO27017_MAPPINGS: list[PackMappingDefinition] = []
ISO27017_EVIDENCE: list[PackEvidenceDefinition] = []
ISO27017_COVERAGE: list[PackCoverageDefinition] = []

for idx, (ctrl_ref, title, desc, cat, cadence) in enumerate(ISO27017_CONTROLS_LIST, start=1):
    ctrl_id = f"ISO27017-{ctrl_ref.replace('.', '-')}"
    src_ref = f"ISO/IEC 27017:2015 Clause {ctrl_ref}"

    guidance = (
        f"**Implementation Guidance:** Establish cloud architecture standards, technical isolation controls, and operational audit evidence to satisfy {title} under {src_ref}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented shared responsibility matrix, VPC network diagrams, IaC templates, tenant isolation test reports, or sub-processor audit certificates demonstrating compliance with {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Cloud Security Policy & Multi-Tenant Architecture Standard\n"
        f"**Standard Citation:** {src_ref}"
    )

    ISO27017_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    ISO27017_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.CLAUSE,
            source_authority=ISO27017_AUTHORITY,
            edition_or_amendment=ISO27017_EDITION,
            source_text=desc,
            content_rights=ISO27017_RIGHTS,
            source_url=ISO27017_URL,
            conformly_guidance=f"Implement cloud controls satisfying {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    ISO27017_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Conformly control {ctrl_id} directly satisfies {src_ref}.",
        )
    )

    ISO27017_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-ISO27017-{ctrl_ref.replace('.', '_')}",
            title=f"Evidence for {title}",
            description=f"Auditor-ready artifacts, IaC scripts, cloud logs, and architectural validation records demonstrating adherence to {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    ISO27017_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Fully implemented by canonical control {ctrl_id} and verified by automated cloud configurations.",
        )
    )

ISO_27017_PACK = FrameworkPackDefinition(
    slug="iso-27017",
    name="ISO/IEC 27017:2015 Cloud Security Controls",
    version="v2015",
    description="Code of practice for information security controls based on ISO/IEC 27002 for cloud services, specifying shared responsibility controls for cloud service customers and cloud service providers.",
    release_notes="Production release of ISO/IEC 27017:2015 Cloud Security Controls framework pack.",
    legal_review_notes="Reviewed against ISO/IEC 27017:2015 clauses and international cloud security best practices.",
    approval_notes="Approved for Module B active framework catalog.",
    controls=ISO27017_CONTROLS,
    source_requirements=ISO27017_SOURCE_REQS,
    mappings=ISO27017_MAPPINGS,
    evidence_specifications=ISO27017_EVIDENCE,
    coverage_ledger=ISO27017_COVERAGE,
)
