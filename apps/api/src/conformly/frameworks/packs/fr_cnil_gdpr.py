"""France Data Protection Act (Loi Informatique et Libertés as amended) Pack Definition.

Covers:
- 6 core statutory provisions under Loi n° 78-17 du 6 janvier 1978 modifiée
- Digital consent threshold for minors (Art 45 - Age 15)
- Post-mortem digital privacy rights & directives (Art 48 & Art 85)
- CNIL compliance frameworks & health data research declarations (Art 57 & Art 87)
- Technical data security obligations and confidentiality safeguards (Art 121)
- Structured evidence requests and coverage ledger
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

FR_CNIL_AUTHORITY = "Commission Nationale de l'Informatique et des Libertés (CNIL)"
FR_CNIL_EDITION = "Loi n° 78-17 du 6 janvier 1978 relative à l'informatique, aux fichiers et aux libertés (modifiée)"
FR_CNIL_RIGHTS = "Public Domain Statute (République Française)."
FR_CNIL_URL = "https://www.legifrance.gouv.fr/loda/id/JORFTEXT000000886460/"

FR_CNIL_SECTIONS: list[tuple[str, str, str, str, str]] = [
    (
        "Art-45",
        "Digital Consent Age for Minors (Age 15 Threshold)",
        "Under French law, minors under the age of 15 cannot independently consent to the processing of personal data for information society services; processing requires joint authorization from the minor and parental authority holders.",
        "Consent & Child Protection",
        "At point of registration / Continuous",
    ),
    (
        "Art-48",
        "Post-Mortem Digital Privacy Rights & Heir Protections",
        "Enable individuals to issue general or specific directives concerning the retention, erasure, and communication of their personal data after their death, and designate trusted third parties registered with CNIL or heirs to execute these directives.",
        "Consumer Rights & Requests",
        "Upon receipt of estate or post-mortem directive",
    ),
    (
        "Art-57",
        "CNIL Reference Methodologies & Standard Compliance Frameworks",
        "Comply with CNIL published standard frameworks, standard regulations, and reference methodologies (méthodologies de référence) for sensitive processing operations, including biometric workplace access and commercial data management.",
        "Regulatory Compliance & Methodologies",
        "Annual audit / Before new processing",
    ),
    (
        "Art-85",
        "Operational Execution of Post-Mortem Data Directives",
        "Operationalize internal procedures to promptly identify, preserve, transfer, or permanently delete personal data upon notification of a data subject's death in accordance with registered post-mortem instructions.",
        "Data Retention & Deletion",
        "Event-driven / Within 30 days of death notice",
    ),
    (
        "Art-87",
        "Health and Medical Data Research Safeguards",
        "Enforce strict technical safeguards, access restrictions, and prior CNIL or Health Data Hub (HDH) compliance declarations before conducting processing of health data for medical evaluation, research, or public health purposes.",
        "Special Category Data",
        "Prior to initiating health data processing",
    ),
    (
        "Art-121",
        "Technical Security Measures & Confidentiality Protections",
        "Implement reasonable and appropriate technical and organizational measures to prevent personal data from being distorted, damaged, or accessed by unauthorized third parties, with periodic review against CNIL security guides.",
        "Information Security",
        "Continuous / Semi-annual review",
    ),
]

FR_CNIL_CONTROLS: list[PackControlDefinition] = []
FR_CNIL_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
FR_CNIL_MAPPINGS: list[PackMappingDefinition] = []
FR_CNIL_EVIDENCE: list[PackEvidenceDefinition] = []
FR_CNIL_COVERAGE: list[PackCoverageDefinition] = []

for idx, (sec_num, title, desc, cat, cadence) in enumerate(FR_CNIL_SECTIONS, start=1):
    ctrl_id = f"FR-CNIL-{sec_num.replace('.', '-')}"
    src_ref = f"Loi 78-17 {sec_num.replace('-', ' ')}"

    guidance = (
        f"**Implementation Guidance:** Operationalize workflows, technical controls, and governance documentation to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented policy, parental consent workflows, CNIL methodology adherence records, or post-mortem directive register satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** French National Privacy & CNIL Compliance Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    FR_CNIL_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    FR_CNIL_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=FR_CNIL_AUTHORITY,
            edition_or_amendment=FR_CNIL_EDITION,
            source_text=desc,
            content_rights=FR_CNIL_RIGHTS,
            source_url=FR_CNIL_URL,
            conformly_guidance=f"Operationalize compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    FR_CNIL_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly operationalizes statutory requirement {src_ref}.",
        )
    )

    FR_CNIL_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-FR-CNIL-{sec_num.replace('.', '_').replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"Operational procedures, age verification records, CNIL conformity checklists, or security logs for {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    FR_CNIL_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"French statutory requirement {sec_num} covered by control {ctrl_id}.",
        )
    )

FR_CNIL_GDPR_PACK = FrameworkPackDefinition(
    slug="fr-cnil-gdpr",
    name="France Data Protection Act (Loi Informatique et Libertés)",
    version="v2019",
    description="France Data Protection Act (Loi n° 78-17 modifiée) national GDPR overlay covering minor consent, post-mortem directives, and CNIL reference methodologies.",
    release_notes="Active release pack covering French national privacy overlays to GDPR.",
    legal_review_notes="Provisions extracted from Loi n° 78-17 as amended by Order 2018-1125 and Decree 2019-536.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=FR_CNIL_CONTROLS,
    source_requirements=FR_CNIL_SOURCE_REQS,
    mappings=FR_CNIL_MAPPINGS,
    evidence_specifications=FR_CNIL_EVIDENCE,
    coverage_ledger=FR_CNIL_COVERAGE,
)
