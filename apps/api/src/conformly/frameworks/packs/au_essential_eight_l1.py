"""Australian Essential Eight (Maturity Level 1) Pack Definition.

Covers:
- All 8 mitigation strategies defined by the Australian Signals Directorate (ASD) / ACSC
- Level 1 baseline maturity requirements for mitigating cyber threats
- Application control, patch management, macro configuration, application hardening, admin privilege restriction, MFA, and backups
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

E8_AUTHORITY = "Australian Cyber Security Centre (ACSC) / Australian Signals Directorate (ASD)"
E8_EDITION = "Essential Eight Maturity Model (Maturity Level 1, November 2023)"
E8_RIGHTS = "Commonwealth of Australia (Creative Commons Attribution 4.0 International)."
E8_URL = (
    "https://www.cyber.gov.au/business-government/asds-cyber-security-frameworks/essential-eight"
)

E8_STRATEGIES: list[tuple[str, str, str, str, str]] = [
    (
        "E8-1",
        "Application Control on Workstations & Servers",
        "Application control is implemented on all workstations and servers to restrict execution of non-approved executables, software installers, scripts, and compiled HTML.",
        "Application Security",
        "Continuous enforcement",
    ),
    (
        "E8-2",
        "Patch Applications (Vulnerability Remediation)",
        "Security vulnerabilities in commercial applications, web browsers, and productivity software are patched within one month of release, or within 48 hours when an exploit exists.",
        "Vulnerability & Patch Management",
        "Monthly / 48h critical",
    ),
    (
        "E8-3",
        "Configure Microsoft Office Macro Settings",
        "Microsoft Office macros are blocked from running in files originating from the internet, and only vetted, digitally signed macros from trusted locations are permitted.",
        "System Hardening",
        "Continuous enforcement",
    ),
    (
        "E8-4",
        "User Application Hardening",
        "Web browsers are configured to block web advertisements and pop-ups; unneeded browser extensions and plugins are disabled or uninstalled across all user systems.",
        "Endpoint Hardening",
        "Quarterly review",
    ),
    (
        "E8-5",
        "Restrict Administrative Privileges",
        "Requests for privileged administrative access are validated with clear justification; privileged accounts are prohibited from performing web browsing, reading email, or general productivity tasks.",
        "Privilege Management",
        "Annual review & re-attestation",
    ),
    (
        "E8-6",
        "Patch Operating Systems",
        "Operating system vulnerabilities on workstations, servers, and network devices are remediated with vendor updates within one month, or within 48 hours for critical vulnerabilities.",
        "Vulnerability & Patch Management",
        "Monthly / 48h critical",
    ),
    (
        "E8-7",
        "Multi-Factor Authentication (MFA)",
        "Multi-factor authentication (MFA) is implemented for all remote access by users, for all cloud services holding sensitive organizational data, and for all administrative logins.",
        "Identity & Access Control",
        "Continuous enforcement",
    ),
    (
        "E8-8",
        "Regular Backups & Restoration Testing",
        "Backups of critical data, applications, and configurations are performed regularly, stored disconnected/immutably to resist tampering, and tested for restoration at least annually.",
        "Data Resilience & Recovery",
        "Daily backup & annual restore test",
    ),
]

E8_CONTROLS: list[PackControlDefinition] = []
E8_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
E8_MAPPINGS: list[PackMappingDefinition] = []
E8_EVIDENCE: list[PackEvidenceDefinition] = []
E8_COVERAGE: list[PackCoverageDefinition] = []

for idx, (strat_id, title, desc, cat, cadence) in enumerate(E8_STRATEGIES, start=1):
    ctrl_id = f"ASD-{strat_id}"
    src_ref = f"ASD Essential Eight ML1 {strat_id}"

    guidance = (
        f"**Implementation Guidance:** Implement technical safeguards and policy controls for {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Configuration profiles, endpoint management policies, patch verification reports, or backup test records for {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Essential Cyber Mitigation Strategies & Endpoint Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    E8_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    E8_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.SAFEGUARD,
            source_authority=E8_AUTHORITY,
            edition_or_amendment=E8_EDITION,
            source_text=desc,
            content_rights=E8_RIGHTS,
            source_url=E8_URL,
            conformly_guidance=f"Enforce ASD Essential Eight mitigation strategy under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    E8_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} satisfies ASD Essential Eight mitigation strategy {strat_id}.",
        )
    )

    E8_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-{ctrl_id.replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"System policy export, EDR/MDM configuration screenshot, patch management log, or restore test record for {src_ref}.",
            evidence_type="CONFIGURATION_RECORD",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    E8_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"ASD Essential Eight strategy {strat_id} implemented via control {ctrl_id}.",
        )
    )

AU_ESSENTIAL_EIGHT_L1_PACK = FrameworkPackDefinition(
    slug="au-essential-eight-l1",
    name="Australian Essential Eight (Maturity Level 1)",
    version="v2023",
    description="Australian Signals Directorate (ASD) Essential Eight baseline mitigation strategies at Maturity Level 1.",
    release_notes="Active release pack covering application control, patch management, macro configuration, MFA, and immutable backups.",
    legal_review_notes="Extracted directly from ASD ACSC Essential Eight Maturity Model (Nov 2023).",
    approval_notes="Approved for Module A active framework catalog.",
    controls=E8_CONTROLS,
    source_requirements=E8_SOURCE_REQS,
    mappings=E8_MAPPINGS,
    evidence_specifications=E8_EVIDENCE,
    coverage_ledger=E8_COVERAGE,
)
