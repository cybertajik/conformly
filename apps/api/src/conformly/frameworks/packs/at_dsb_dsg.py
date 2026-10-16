"""Austria Data Protection Act (Datenschutzgesetz - DSG) Pack Definition.

Covers:
- 6 core statutory provisions under Austrian Datenschutzgesetz (DSG - BGBl. I Nr. 165/1999 as amended)
- Constitutional fundamental right to data protection (§ 1 DSG)
- Digital consent threshold for minors (§ 4 DSG - Age 14)
- Video surveillance permissibility and spatial restrictions (§ 12 DSG)
- Mandatory logging and 72-hour maximum retention for video surveillance (§ 13 DSG)
- Austrian Data Protection Authority (DSB) complaint and investigation procedures (§ 24 DSG)
- Administrative liability and penalty frameworks (§ 62 DSG)
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

AT_DSB_AUTHORITY = "Österreichische Datenschutzbehörde (DSB)"
AT_DSB_EDITION = "Datenschutzgesetz (DSG - BGBl. I Nr. 165/1999 idF BGBl. I Nr. 120/2017)"
AT_DSB_RIGHTS = "Public Domain Statute (Republik Österreich)."
AT_DSB_URL = "https://www.dsb.gv.at/gesetze-und-urteile/national.html"

AT_DSB_SECTIONS: list[tuple[str, str, str, str, str]] = [
    (
        "Sec-1",
        "Constitutional Fundamental Right to Data Protection",
        "Every person has a constitutional fundamental right to secrecy regarding personal data concerning them, demanding that any interference is strictly justified on statutory grounds of national security, economic well-being, or rights protection.",
        "Fundamental Rights & Governance",
        "Continuous / Policy governance",
    ),
    (
        "Sec-4",
        "Digital Consent Age for Minors (Age 14 Threshold)",
        "Under Austrian law, a minor who has reached the age of 14 years may independently consent to the processing of personal data for information society services; minors under 14 require the consent of a parent or guardian.",
        "Consent & Child Protection",
        "At registration point / Continuous",
    ),
    (
        "Sec-12",
        "Video Surveillance Permissibility & Spatial Restrictions",
        "Restrict optical surveillance (Bildaufnahmen) to strictly defined security purposes; clearly signpost all monitored areas prior to camera entry; and prohibit camera installation in private sanctum areas (changing rooms, restrooms).",
        "Surveillance & Physical Security",
        "Prior to installation / Annual review",
    ),
    (
        "Sec-13",
        "Video Surveillance Access Logging & 72-Hour Deletion",
        "Maintain tamper-evident audit logs documenting every viewing, processing, or extraction of video surveillance footage; automatically delete recorded video footage within a maximum of 72 hours unless specific evidence preservation is required.",
        "Logging & Data Retention",
        "Automatic 72-hour retention cycle / Quarterly log review",
    ),
    (
        "Sec-24",
        "Datenschutzbehörde (DSB) Complaint & Remedies Procedure",
        "Establish internal operational procedures to promptly review and defend complaints submitted to the Austrian Data Protection Authority (Datenschutzbehörde), ensuring all evidence is preserved and submitted within statutory deadlines.",
        "Regulatory Oversight & Remedies",
        "Event-driven / Within deadlines set by DSB",
    ),
    (
        "Sec-62",
        "Administrative Penalties & Compliance Remediation",
        "Implement internal controls to prevent intentional or gross negligence violations of statutory data secrecy, maintaining complete technical registers of processing activities subject to Austrian administrative review.",
        "Compliance Governance & Sanctions",
        "Annual compliance review",
    ),
]

AT_DSB_CONTROLS: list[PackControlDefinition] = []
AT_DSB_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
AT_DSB_MAPPINGS: list[PackMappingDefinition] = []
AT_DSB_EVIDENCE: list[PackEvidenceDefinition] = []
AT_DSB_COVERAGE: list[PackCoverageDefinition] = []

for idx, (sec_num, title, desc, cat, cadence) in enumerate(AT_DSB_SECTIONS, start=1):
    ctrl_id = f"AT-DSB-{sec_num.replace('.', '-')}"
    src_ref = f"DSG § {sec_num.replace('Sec-', '')}"

    guidance = (
        f"**Implementation Guidance:** Operationalize workflows, CCTV controls, and governance policies to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented policy, age verification records, video surveillance signage photos, 72-hour automated deletion configuration, or DSB inquiry files satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Austrian National Privacy & DSG Compliance Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    AT_DSB_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    AT_DSB_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=AT_DSB_AUTHORITY,
            edition_or_amendment=AT_DSB_EDITION,
            source_text=desc,
            content_rights=AT_DSB_RIGHTS,
            source_url=AT_DSB_URL,
            conformly_guidance=f"Operationalize compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    AT_DSB_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly operationalizes statutory requirement {src_ref}.",
        )
    )

    AT_DSB_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-AT-DSB-{sec_num.replace('.', '_').replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"Operational policy, CCTV deletion timers, access logs, or DSB compliance records for {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    AT_DSB_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Austrian DSG requirement {sec_num} covered by control {ctrl_id}.",
        )
    )

AT_DSB_DSG_PACK = FrameworkPackDefinition(
    slug="at-dsb-dsg",
    name="Austria Data Protection Act (Datenschutzgesetz - DSG)",
    version="v2018",
    description="Austria Datenschutzgesetz (DSG) national GDPR overlay covering constitutional secrecy rights, minor consent (age 14), and strict 72-hour video surveillance rules.",
    release_notes="Active release pack covering Austrian national privacy overlays and optical surveillance rules.",
    legal_review_notes="Provisions extracted from the Datenschutzgesetz (BGBl. I Nr. 165/1999 as amended).",
    approval_notes="Approved for Module A active framework catalog.",
    controls=AT_DSB_CONTROLS,
    source_requirements=AT_DSB_SOURCE_REQS,
    mappings=AT_DSB_MAPPINGS,
    evidence_specifications=AT_DSB_EVIDENCE,
    coverage_ledger=AT_DSB_COVERAGE,
)
