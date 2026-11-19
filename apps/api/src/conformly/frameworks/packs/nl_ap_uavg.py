"""Netherlands GDPR Implementation Act (UAVG) Pack Definition.

Covers:
- 6 core statutory provisions under Uitvoeringswet Algemene verordening gegevensbescherming (UAVG)
- Digital consent threshold for minors (Art 5 - Age 16)
- National identification number (BSN / Burgerservicenummer) restrictions (Art 22)
- Biometric data processing limitations for security and authentication (Art 29)
- Workplace health data processing boundaries (Art 30)
- Research and statistical exemptions (Art 33)
- Autoriteit Persoonsgegevens (AP) enforcement and investigatory compliance (Art 46)
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

NL_AP_AUTHORITY = "Autoriteit Persoonsgegevens (AP)"
NL_AP_EDITION = "Uitvoeringswet Algemene verordening gegevensbescherming (UAVG - Stb. 2018, 144)"
NL_AP_RIGHTS = "Public Domain Statute (Koninkrijk der Nederlanden)."
NL_AP_URL = "https://wetten.overheid.nl/BWBR0040940/"

NL_AP_SECTIONS: list[tuple[str, str, str, str, str]] = [
    (
        "Art-5",
        "Digital Consent Age for Minors (Age 16 Threshold)",
        "Under Dutch law, consent for offering information society services directly to a minor is only valid if the minor has reached 16 years of age; under 16 requires parental responsibility consent.",
        "Consent & Child Protection",
        "At point of registration / Continuous",
    ),
    (
        "Art-22",
        "Citizen Service Number (BSN) Processing Restrictions",
        "Prohibit the collection and processing of the Burgerservicenummer (BSN) or national identification number unless specifically authorized by statute or necessary for statutory public sector obligations.",
        "Identification Data & Statutory Restrictions",
        "Continuous / Architecture design review",
    ),
    (
        "Art-29",
        "Biometric Data Processing Restrictions for Authentication",
        "Restrict the processing of biometric data for uniquely identifying a person to instances where processing is strictly necessary for security or authentication access purposes and disproportionate alternative measures are absent.",
        "Special Category Data & Biometrics",
        "Prior to biometric implementation / Annual review",
    ),
    (
        "Art-30",
        "Workplace Health Data Boundaries & Occupational Health (Arbodienst)",
        "Prohibit employers from asking employees for, or processing, diagnostic medical information, pregnancy status, or illness causes; medical evaluations must remain strictly segregated within certified occupational health services (Arbodienst).",
        "Workplace Privacy & Health Data",
        "Continuous / HR policy audit",
    ),
    (
        "Art-33",
        "Scientific, Historical & Statistical Research Safeguards",
        "Apply Dutch national safeguards when relying on research exemptions, ensuring technical separation of identifying details, encryption, pseudonymization, and confirmation that data subjects cannot be directly re-identified.",
        "Research & Data Minimization",
        "Prior to research project execution",
    ),
    (
        "Art-46",
        "Autoriteit Persoonsgegevens (AP) Regulatory Oversight & Inquiries",
        "Maintain documented records and technical capabilities to promptly cooperate with audits, investigations, and binding administrative decisions issued by the Dutch Data Protection Authority (Autoriteit Persoonsgegevens).",
        "Regulatory Oversight & Audits",
        "Within deadlines specified in AP requests",
    ),
]

NL_AP_CONTROLS: list[PackControlDefinition] = []
NL_AP_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
NL_AP_MAPPINGS: list[PackMappingDefinition] = []
NL_AP_EVIDENCE: list[PackEvidenceDefinition] = []
NL_AP_COVERAGE: list[PackCoverageDefinition] = []

for idx, (sec_num, title, desc, cat, cadence) in enumerate(NL_AP_SECTIONS, start=1):
    ctrl_id = f"NL-AP-{sec_num.replace('.', '-')}"
    src_ref = f"UAVG {sec_num.replace('-', ' ')}"

    guidance = (
        f"**Implementation Guidance:** Operationalize workflows, BSN exclusion policies, and security controls to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented policy, age verification records, BSN restriction architectural reviews, biometric necessity assessments, or AP inquiry files satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Dutch National Privacy & UAVG Compliance Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    NL_AP_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    NL_AP_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=NL_AP_AUTHORITY,
            edition_or_amendment=NL_AP_EDITION,
            source_text=desc,
            content_rights=NL_AP_RIGHTS,
            source_url=NL_AP_URL,
            conformly_guidance=f"Operationalize compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    NL_AP_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly operationalizes statutory requirement {src_ref}.",
        )
    )

    NL_AP_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-NL-AP-{sec_num.replace('.', '_').replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"Operational policy, BSN audit logs, biometric necessity assessments, or Arbodienst segregation records for {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    NL_AP_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Dutch UAVG requirement {sec_num} covered by control {ctrl_id}.",
        )
    )

NL_AP_UAVG_PACK = FrameworkPackDefinition(
    slug="nl-ap-uavg",
    name="Netherlands GDPR Implementation Act (UAVG)",
    version="v2018",
    description="Netherlands Uitvoeringswet Algemene verordening gegevensbescherming (UAVG) national GDPR overlay covering minor consent (age 16), BSN restrictions, and biometric processing rules.",
    release_notes="Active release pack covering Dutch national privacy overlays and BSN processing constraints.",
    legal_review_notes="Provisions extracted from Uitvoeringswet Algemene verordening gegevensbescherming (Stb. 2018, 144).",
    approval_notes="Approved for Module A active framework catalog.",
    controls=NL_AP_CONTROLS,
    source_requirements=NL_AP_SOURCE_REQS,
    mappings=NL_AP_MAPPINGS,
    evidence_specifications=NL_AP_EVIDENCE,
    coverage_ledger=NL_AP_COVERAGE,
)
