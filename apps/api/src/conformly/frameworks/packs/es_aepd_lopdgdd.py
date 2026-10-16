"""Spain Ley Orgánica 3/2018 (LOPDGDD) Pack Definition.

Covers:
- 6 core statutory provisions under Ley Orgánica 3/2018 (LOPDGDD)
- Digital consent threshold for minors (Art 7 - Age 14)
- Mandatory Data Protection Officer (DPO / DPD) designations across statutory sectors (Art 34)
- Digital rights in the workplace: Right to digital disconnection (Art 87)
- Workplace digital device privacy rights (Art 88)
- Workplace video surveillance and sound recording safeguards (Art 89)
- Workplace geolocation privacy safeguards (Art 90)
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

ES_AEPD_AUTHORITY = "Agencia Española de Protección de Datos (AEPD)"
ES_AEPD_EDITION = "Ley Orgánica 3/2018, de 5 de diciembre, de Protección de Datos Personales y garantía de los derechos digitales (LOPDGDD)"
ES_AEPD_RIGHTS = "Public Domain Statute (Reino de España)."
ES_AEPD_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2018-16673"

ES_AEPD_SECTIONS: list[tuple[str, str, str, str, str]] = [
    (
        "Art-7",
        "Digital Consent Age for Minors (Age 14 Threshold)",
        "Under Spanish law, the processing of personal data of a minor may only be based on their consent when they are older than 14 years of age; processing of data of persons under 14 requires the consent of parents or legal guardians.",
        "Consent & Child Protection",
        "At point of onboarding / Continuous",
    ),
    (
        "Art-34",
        "Mandatory Data Protection Officer (DPD) Designation",
        "Designate a Data Protection Officer (Delegado de Protección de Datos - DPD) and communicate the appointment to the AEPD within 10 days if operating in statutorily listed sectors (educational institutions, health clinics, financial entities, insurers, telecoms, security firms).",
        "Governance & DPO Oversight",
        "Within 10 days of appointment / Annual review",
    ),
    (
        "Art-87",
        "Right to Digital Disconnection in the Workplace",
        "Establish an organizational policy guaranteeing workers the right to digital disconnection outside established working hours, protecting rest periods, leaves, vacations, and personal privacy.",
        "Workplace Privacy & Digital Rights",
        "Annual policy review / Continuous enforcement",
    ),
    (
        "Art-88",
        "Privacy Safeguards in the Use of Digital Devices at Work",
        "Define clear internal criteria for the use and monitoring of employer-provided digital devices, ensuring workers are informed in advance of permitted uses and monitoring parameters, with participation of workers' legal representatives.",
        "Workplace Privacy & Digital Rights",
        "Prior to device rollout / Annual review",
    ),
    (
        "Art-89",
        "Workplace Video Surveillance & Audio Recording Restrictions",
        "Restrict video surveillance to safety and labor control purposes with prior clear notice to workers; prohibit cameras in rest areas, dining rooms, changing rooms, and toilets; and strictly limit audio recording to exceptional verified security risks.",
        "Surveillance & Physical Security",
        "Continuous / Camera placement audits",
    ),
    (
        "Art-90",
        "Workplace Geolocation Safeguards & Prior Notice",
        "Limit geolocation systems on employee vehicles or mobile devices to legitimate employment duties, ensuring workers and their representatives are explicitly, clearly, and unequivocally informed beforehand of device tracking and employee rights.",
        "Workplace Privacy & Geolocation",
        "Prior to geolocation activation / Continuous",
    ),
]

ES_AEPD_CONTROLS: list[PackControlDefinition] = []
ES_AEPD_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
ES_AEPD_MAPPINGS: list[PackMappingDefinition] = []
ES_AEPD_EVIDENCE: list[PackEvidenceDefinition] = []
ES_AEPD_COVERAGE: list[PackCoverageDefinition] = []

for idx, (sec_num, title, desc, cat, cadence) in enumerate(ES_AEPD_SECTIONS, start=1):
    ctrl_id = f"ES-AEPD-{sec_num.replace('.', '-')}"
    src_ref = f"LOPDGDD {sec_num.replace('-', ' ')}"

    guidance = (
        f"**Implementation Guidance:** Operationalize workflows, workplace policies, and technical controls to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented policy, digital disconnection protocol, DPD notification receipt from AEPD, or workplace monitoring agreement satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Spanish National Privacy & LOPDGDD Workplace Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    ES_AEPD_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    ES_AEPD_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=ES_AEPD_AUTHORITY,
            edition_or_amendment=ES_AEPD_EDITION,
            source_text=desc,
            content_rights=ES_AEPD_RIGHTS,
            source_url=ES_AEPD_URL,
            conformly_guidance=f"Operationalize compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    ES_AEPD_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly operationalizes statutory requirement {src_ref}.",
        )
    )

    ES_AEPD_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-ES-AEPD-{sec_num.replace('.', '_').replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"Operational policy, DPD communication receipt, digital disconnection protocol, or notice records for {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    ES_AEPD_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Spanish LOPDGDD requirement {sec_num} covered by control {ctrl_id}.",
        )
    )

ES_AEPD_LOPDGDD_PACK = FrameworkPackDefinition(
    slug="es-aepd-lopdgdd",
    name="Spain Data Protection Act (LOPDGDD)",
    version="v2018",
    description="Spain Ley Orgánica 3/2018 (LOPDGDD) national GDPR overlay covering minor consent (age 14), mandatory DPD sectors, and workplace digital rights.",
    release_notes="Active release pack covering Spanish national privacy overlays and workplace digital rights.",
    legal_review_notes="Provisions extracted directly from Ley Orgánica 3/2018 (BOE-A-2018-16673).",
    approval_notes="Approved for Module A active framework catalog.",
    controls=ES_AEPD_CONTROLS,
    source_requirements=ES_AEPD_SOURCE_REQS,
    mappings=ES_AEPD_MAPPINGS,
    evidence_specifications=ES_AEPD_EVIDENCE,
    coverage_ledger=ES_AEPD_COVERAGE,
)
