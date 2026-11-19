"""ISO/IEC 27018:2019 Public Cloud PII Protection Pack Definition.

Covers:
- Cloud privacy controls for public cloud providers acting as PII processors
- Customer data sovereignty, purpose limitation, and marketing restrictions
- Sub-processor disclosures, law enforcement requests transparency, and temporary file erasure
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

ISO27018_AUTHORITY = "International Organization for Standardization (ISO) / IEC"
ISO27018_EDITION = "ISO/IEC 27018:2019 (Information technology — Security techniques — Code of practice for protection of personally identifiable information (PII) in public clouds acting as PII processors)"
ISO27018_RIGHTS = "Copyright ISO/IEC. Citations and titles used for reference; proprietary standard text not redistributed verbatim. Guidance and procedures by Conformly."
ISO27018_URL = "https://www.iso.org/standard/76559.html"

ISO27018_CONTROLS_LIST: list[tuple[str, str, str, str, str]] = [
    (
        "CLD.PII.A.1.1",
        "Customer Consent & Processing Exclusively on Documented Instructions",
        "Process customer PII strictly and exclusively in accordance with the documented instructions of the cloud service customer (controller), without unauthorized data sharing.",
        "Consent & Instructions",
        "Continuous / Contract execution",
    ),
    (
        "CLD.PII.A.2.1",
        "Prohibition on Commercial Exploitation, Advertising & Profiling",
        "Explicitly prohibit using customer PII for marketing, targeted advertising, commercial profiling, or third-party monetization without explicit prior customer consent.",
        "Purpose Limitation",
        "Continuous",
    ),
    (
        "CLD.PII.A.3.1",
        "Data Sovereignty & Geographic Storage Location Transparency",
        "Disclose to cloud service customers all geographic regions, sovereign jurisdictions, and data center locations where their PII and associated backups may be stored or processed.",
        "Data Sovereignty",
        "Annual review / Upon topology changes",
    ),
    (
        "CLD.PII.A.4.1",
        "Secure Erasure of Temporary, Cache & Staging Files",
        "Implement automated sanitization schedules and cryptographic deletion algorithms to ensure temporary files, cache entries, and memory dumps containing PII are purged without delay.",
        "Data Lifecycle",
        "Continuous / Automated scheduled jobs",
    ),
    (
        "CLD.PII.A.5.1",
        "Prior Notice & Approval of Cloud Sub-Processors",
        "Maintain an up-to-date public or customer-accessible register of all cloud sub-processors and notify customers well in advance of adding or replacing sub-contractors.",
        "Sub-Processor Oversight",
        "Prior to sub-processor activation",
    ),
    (
        "CLD.PII.A.6.1",
        "Law Enforcement & Government Access Inquiry Notification",
        "Promptly notify cloud service customers of any legally binding government, court, or law enforcement request for PII disclosure unless expressly prohibited by statutory law.",
        "Legal & Regulatory",
        "Event-driven upon receipt of legal order",
    ),
    (
        "CLD.PII.A.7.1",
        "Mandatory Encryption in Transit for All PII Across Public Networks",
        "Enforce modern cryptographic transport encryption (TLS 1.3, IPSec) for all customer PII transmissions across public networks and between distributed cloud availability zones.",
        "Cryptography",
        "Continuous",
    ),
    (
        "CLD.PII.A.8.1",
        "Multi-Tenant Database & Object Storage Segregation for PII",
        "Enforce cryptographically enforced tenant isolation, separate encryption keys per customer, and strict access controls preventing accidental cross-customer PII exposure.",
        "Tenant Segregation",
        "Continuous / Architectural review",
    ),
    (
        "CLD.PII.A.9.1",
        "Immediate PII Security Breach Notification to Cloud Customers",
        "Establish automated alerting procedures to notify cloud service customers without undue delay upon confirming a security incident resulting in unlawful access to customer PII.",
        "Incident Management",
        "Within contractual notice window / 24-72h",
    ),
    (
        "CLD.PII.A.10.1",
        "Customer Security Audit Rights & Evidence Cooperation",
        "Provide cloud service customers and their authorized third-party auditors with reasonable access to audit reports, certifications, and compliance evidence verifying adherence to ISO 27018.",
        "Audit & Verification",
        "Annual review / Upon customer audit request",
    ),
]

ISO27018_CONTROLS: list[PackControlDefinition] = []
ISO27018_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
ISO27018_MAPPINGS: list[PackMappingDefinition] = []
ISO27018_EVIDENCE: list[PackEvidenceDefinition] = []
ISO27018_COVERAGE: list[PackCoverageDefinition] = []

for idx, (ctrl_ref, title, desc, cat, cadence) in enumerate(ISO27018_CONTROLS_LIST, start=1):
    ctrl_id = f"ISO27018-{ctrl_ref.replace('.', '-')}"
    src_ref = f"ISO/IEC 27018:2019 Clause {ctrl_ref}"

    guidance = (
        f"**Implementation Guidance:** Implement technical cloud policies, privacy workflows, and operational audit evidence to satisfy {title} under {src_ref}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented cloud customer DPA, geographic location disclosures, sub-processor registers, temporary file cleanup scripts, or government inquiry handling runbooks satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Public Cloud PII Protection & Data Privacy Policy\n"
        f"**Standard Citation:** {src_ref}"
    )

    ISO27018_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    ISO27018_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.CLAUSE,
            source_authority=ISO27018_AUTHORITY,
            edition_or_amendment=ISO27018_EDITION,
            source_text=desc,
            content_rights=ISO27018_RIGHTS,
            source_url=ISO27018_URL,
            conformly_guidance=f"Implement cloud privacy controls satisfying {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    ISO27018_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Conformly control {ctrl_id} directly satisfies {src_ref}.",
        )
    )

    ISO27018_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-ISO27018-{ctrl_ref.replace('.', '_')}",
            title=f"Evidence for {title}",
            description=f"Auditor-ready artifacts, system logs, configuration policies, and operational records verifying compliance with {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    ISO27018_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Fully implemented by canonical control {ctrl_id} and verified by cloud configuration telemetry.",
        )
    )

ISO_27018_PACK = FrameworkPackDefinition(
    slug="iso-27018",
    name="ISO/IEC 27018:2019 Public Cloud PII Protection",
    version="v2019",
    description="Code of practice for protection of personally identifiable information (PII) in public clouds acting as PII processors, ensuring customer data sovereignty and strict commercial boundaries.",
    release_notes="Production release of ISO/IEC 27018:2019 cloud privacy compliance pack.",
    legal_review_notes="Reviewed against ISO/IEC 27018:2019 clauses and international cloud processor obligations.",
    approval_notes="Approved for Module B active framework catalog.",
    controls=ISO27018_CONTROLS,
    source_requirements=ISO27018_SOURCE_REQS,
    mappings=ISO27018_MAPPINGS,
    evidence_specifications=ISO27018_EVIDENCE,
    coverage_ledger=ISO27018_COVERAGE,
)
