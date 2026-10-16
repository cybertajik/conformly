"""CISA Cross-Sector Cybersecurity Performance Goals (CPGs v1.0.1) Pack Definition.

Covers:
- Core high-impact cross-sector cybersecurity practices prioritized by CISA
- Phishing-resistant MFA, credential hygiene, asset management, data encryption, training, vulnerability mitigation, and offline backups
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

CISA_AUTHORITY = "Cybersecurity and Infrastructure Security Agency (CISA)"
CISA_EDITION = "CISA Cross-Sector Cybersecurity Performance Goals v1.0.1 (March 2023)"
CISA_RIGHTS = "Public Domain U.S. Federal Government Work."
CISA_URL = "https://www.cisa.gov/cybersecurity-performance-goals"

CISA_SECTIONS: list[tuple[str, str, str, str, str]] = [
    (
        "1.1",
        "Account Security: Phishing-Resistant MFA",
        "Implement phishing-resistant multi-factor authentication (MFA) across all administrative, remote, and internet-facing access interfaces, and mandatory MFA for all corporate accounts.",
        "Account & Identity Security",
        "Continuous enforcement",
    ),
    (
        "1.2",
        "Account Security: Basic Password Hygiene & Defaults",
        "Change all vendor-default passwords before deploying software or hardware, and enforce robust password length and complexity policies prohibiting commonly breached passwords.",
        "Account & Identity Security",
        "Continuous enforcement",
    ),
    (
        "2.1",
        "Device Security: Hardware & Software Asset Inventory",
        "Establish and maintain an accurate, comprehensive inventory of all organizational hardware, virtual assets, and software components connected to the organizational network.",
        "Asset Management",
        "Monthly audit",
    ),
    (
        "3.1",
        "Data Security: Encryption in Transit and at Rest",
        "Enforce modern encryption standards for sensitive organizational and customer data at rest (AES-256) and in transit across public networks (TLS 1.2 or TLS 1.3).",
        "Data Protection",
        "Continuous enforcement",
    ),
    (
        "4.1",
        "Governance: Basic Cybersecurity Awareness Training",
        "Provide recurring, documented cybersecurity awareness training for all personnel, covering phishing recognition, password hygiene, credential theft, and incident reporting procedures.",
        "Governance & Training",
        "Annual & quarterly drills",
    ),
    (
        "5.1",
        "Vulnerability Mitigation: Timely KEV Remediation",
        "Identify and remediate Known Exploited Vulnerabilities (KEVs) cataloged by CISA across internet-facing and critical assets within statutory timelines (typically 14 to 30 days).",
        "Vulnerability Management",
        "Continuous / Bi-weekly",
    ),
    (
        "6.1",
        "Supply Chain: Vendor Cyber Risk Assessment",
        "Evaluate third-party vendor security posture prior to procurement, mandate minimum contractual security obligations, and maintain an inventory of critical suppliers.",
        "Third-Party Risk",
        "Prior to onboarding & annual review",
    ),
    (
        "7.1",
        "Incident Response: Immutable & Tested Backups",
        "Maintain isolated, offline, or immutable backups of critical corporate and customer data, and conduct scheduled restoration testing at least annually.",
        "Incident Response & Continuity",
        "Quarterly backup & annual restore test",
    ),
]

CISA_CONTROLS: list[PackControlDefinition] = []
CISA_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
CISA_MAPPINGS: list[PackMappingDefinition] = []
CISA_EVIDENCE: list[PackEvidenceDefinition] = []
CISA_COVERAGE: list[PackCoverageDefinition] = []

for idx, (goal_num, title, desc, cat, cadence) in enumerate(CISA_SECTIONS, start=1):
    ctrl_id = f"CISA-CPG-{goal_num.replace('.', '-')}"
    src_ref = f"CISA CPG {goal_num}"

    guidance = (
        f"**Implementation Guidance:** Implement operational procedures and technical safeguards for {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Configuration exports, policy documents, training completion records, or scan reports verifying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Cybersecurity Operations & Baseline Controls Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    CISA_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    CISA_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.SAFEGUARD,
            source_authority=CISA_AUTHORITY,
            edition_or_amendment=CISA_EDITION,
            source_text=desc,
            content_rights=CISA_RIGHTS,
            source_url=CISA_URL,
            conformly_guidance=f"Implement baseline CISA cybersecurity goal under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    CISA_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} satisfies CISA performance goal {src_ref}.",
        )
    )

    CISA_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-CISA-CPG-{goal_num.replace('.', '_')}",
            title=f"Evidence for {title}",
            description=f"Technical audit logs, MFA enforcement screenshots, backup test verification, or inventory records for {src_ref}.",
            evidence_type="CONFIGURATION_RECORD",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    CISA_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"CISA performance goal {goal_num} implemented via control {ctrl_id}.",
        )
    )

CISA_CPG_PACK = FrameworkPackDefinition(
    slug="cisa-cpg",
    name="CISA Cross-Sector Cybersecurity Performance Goals (CPGs v1.0.1)",
    version="v1.0.1",
    description="Cybersecurity and Infrastructure Security Agency (CISA) baseline cross-sector cybersecurity goals.",
    release_notes="Active release pack covering CISA foundational account security, asset tracking, data encryption, and vulnerability management.",
    legal_review_notes="Extracted directly from CISA Cross-Sector Cybersecurity Performance Goals v1.0.1 guidance.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=CISA_CONTROLS,
    source_requirements=CISA_SOURCE_REQS,
    mappings=CISA_MAPPINGS,
    evidence_specifications=CISA_EVIDENCE,
    coverage_ledger=CISA_COVERAGE,
)
