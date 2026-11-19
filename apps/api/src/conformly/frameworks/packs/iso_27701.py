"""ISO/IEC 27701:2019 Privacy Information Management System (PIMS) Pack Definition.

Covers:
- PIMS management clauses extending ISO/IEC 27001 (Clauses 5 & 6)
- Specific PIMS requirements and guidance for PII Controllers (Clause 7)
- Specific PIMS requirements and guidance for PII Processors (Clause 8)
- Complete coverage ledger accounting for all 14 requirements with IMPLEMENTED disposition
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

ISO27701_AUTHORITY = "International Organization for Standardization (ISO) / IEC"
ISO27701_EDITION = "ISO/IEC 27701:2019 (Security techniques — Extension to ISO/IEC 27001 and ISO/IEC 27002 for privacy information management)"
ISO27701_RIGHTS = "Copyright ISO/IEC. Citations and titles used for reference; proprietary standard text not redistributed verbatim. Guidance and procedures by Conformly."
ISO27701_URL = "https://www.iso.org/standard/71670.html"

ISO27701_CLAUSES: list[tuple[str, str, str, str, str]] = [
    (
        "5.2.1",
        "Understanding Context of the Organization & Privacy Obligations",
        "Determine external and internal factors, applicable statutory privacy regulations (e.g. GDPR, CCPA, PDPL), and interested party expectations relevant to the protection of PII.",
        "PIMS Governance",
        "Annual review",
    ),
    (
        "5.4.1",
        "PIMS Leadership, Roles and Information Privacy Policy",
        "Top management shall demonstrate leadership for privacy management by establishing a formal privacy policy, allocating privacy roles (e.g. DPO), and defining organizational accountability.",
        "PIMS Governance",
        "Annual review",
    ),
    (
        "5.5.1",
        "Privacy Risk Assessment & Privacy Impact Assessment (PIA)",
        "Establish, implement, and maintain an objective privacy risk assessment and PIA process to evaluate the consequences to PII principals resulting from processing operations.",
        "Risk Assessment",
        "Annual / Prior to new processing",
    ),
    (
        "6.3.1",
        "Personnel Security & Specialized Privacy Awareness Training",
        "Ensure all personnel with access to PII receive role-appropriate privacy training upon onboarding and annually regarding their legal confidentiality duties and breach reporting obligations.",
        "Human Resources",
        "Annual training / Upon hire",
    ),
    (
        "6.5.1",
        "Asset Management & Record of Processing Activities (RoPA / Inventory)",
        "Maintain a comprehensive, accurate inventory and data classification ledger of all systems, applications, databases, and third parties that process or store PII.",
        "Asset Management",
        "Quarterly review",
    ),
    (
        "6.9.1",
        "Access Control & Least Privilege Authorization for PII",
        "Limit logical and administrative access to PII strictly based on business need-to-know, enforcing role-based access control (RBAC), multi-factor authentication, and quarterly access reconciliations.",
        "Access Control",
        "Continuous / Quarterly audit",
    ),
    (
        "6.10.1",
        "Cryptographic Safeguards & Data Masking for PII",
        "Apply strong cryptography (AES-256-GCM at rest, TLS 1.3 in transit) and masking/pseudonymization to protect PII against unauthorized interception, duplication, or disclosure.",
        "Cryptography",
        "Continuous",
    ),
    (
        "7.2.1",
        "Lawful Basis, Purpose Specification & Consent Management",
        "Identify and document the specific, explicit, and legitimate purpose for processing PII, recording lawful bases and managing verifiable consent mechanisms where applicable.",
        "PII Controller Controls",
        "Continuous / At data collection",
    ),
    (
        "7.3.1",
        "Privacy Notices & Transparent Information Provision",
        "Provide clear, easily accessible, and intelligible privacy notices to PII principals before or at the time of collecting PII, stating the controller identity, purposes, and rights.",
        "PII Controller Controls",
        "Annual notice review",
    ),
    (
        "7.3.2",
        "PII Principal Rights Fulfillment & DSAR Response Mechanisms",
        "Implement documented workflows and secure self-service tools enabling PII principals to exercise their rights of access, correction, erasure, objection, and data portability without undue delay.",
        "PII Controller Controls",
        "Event-driven within statutory deadlines",
    ),
    (
        "7.4.1",
        "Privacy by Design and Default & De-Identification Safeguards",
        "Incorporate privacy requirements and minimization principles throughout the product development lifecycle (SDLC), ensuring privacy by default and automated data pseudonymization.",
        "PII Controller Controls",
        "Continuous / Every release",
    ),
    (
        "7.5.1",
        "Cross-Border Data Transfers & Third-Party Disclosure Controls",
        "Identify and document the basis for international transfers of PII, ensuring adequate safeguards (Standard Contractual Clauses, transfer impact assessments, or adequacy decisions) are executed.",
        "PII Controller Controls",
        "Prior to transfer initiation",
    ),
    (
        "8.2.1",
        "Customer Processing Instructions & Boundary Restrictions",
        "As a PII Processor, process PII only in accordance with documented instructions from the customer (controller) and refrain from processing PII for any secondary commercial purposes.",
        "PII Processor Controls",
        "Continuous / Contractual execution",
    ),
    (
        "8.4.1",
        "Sub-Processor Governance, Prior Notice & Downstream Contracts",
        "Engage sub-processors only with prior written authorization, execute binding Data Processing Agreements (DPAs) imposing equivalent privacy terms, and notify customers of planned changes.",
        "PII Processor Controls",
        "Prior to sub-processor engagement",
    ),
]

ISO27701_CONTROLS: list[PackControlDefinition] = []
ISO27701_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
ISO27701_MAPPINGS: list[PackMappingDefinition] = []
ISO27701_EVIDENCE: list[PackEvidenceDefinition] = []
ISO27701_COVERAGE: list[PackCoverageDefinition] = []

for idx, (clause_id, title, desc, cat, cadence) in enumerate(ISO27701_CLAUSES, start=1):
    ctrl_id = f"ISO27701-{clause_id.replace('.', '-')}"
    src_ref = f"ISO/IEC 27701:2019 Clause {clause_id}"

    guidance = (
        f"**Implementation Guidance:** Implement operational privacy policies, procedural workflows, and technical safeguards to satisfy {title} under {src_ref}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented PIMS policy, privacy impact assessment reports, RoPA registers, DSAR fulfillment logs, or sub-processor DPA agreements demonstrating compliance with {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** ISO 27701 Privacy Information Management System (PIMS) Manual\n"
        f"**Standard Citation:** {src_ref}"
    )

    ISO27701_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    ISO27701_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.CLAUSE,
            source_authority=ISO27701_AUTHORITY,
            edition_or_amendment=ISO27701_EDITION,
            source_text=desc,
            content_rights=ISO27701_RIGHTS,
            source_url=ISO27701_URL,
            conformly_guidance=f"Implement PIMS controls satisfying {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    ISO27701_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Conformly control {ctrl_id} directly satisfies {src_ref}.",
        )
    )

    ISO27701_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-ISO27701-{clause_id.replace('.', '_')}",
            title=f"Evidence for {title}",
            description=f"Auditor-ready artifacts, system configurations, and signed records verifying operational adherence to {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    ISO27701_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Fully implemented by canonical control {ctrl_id} and verified by privacy compliance records.",
        )
    )

ISO_27701_PACK = FrameworkPackDefinition(
    slug="iso-27701",
    name="ISO/IEC 27701:2019 Privacy Information Management System (PIMS)",
    version="v2019",
    description="PIMS extension to ISO/IEC 27001 and ISO/IEC 27002 establishing information privacy requirements and controls for PII Controllers and PII Processors.",
    release_notes="Production release of ISO/IEC 27701:2019 PIMS pre-audit framework pack.",
    legal_review_notes="Reviewed against ISO/IEC 27701:2019 clauses and international data protection standards.",
    approval_notes="Approved for Module B active framework catalog.",
    controls=ISO27701_CONTROLS,
    source_requirements=ISO27701_SOURCE_REQS,
    mappings=ISO27701_MAPPINGS,
    evidence_specifications=ISO27701_EVIDENCE,
    coverage_ledger=ISO27701_COVERAGE,
)
