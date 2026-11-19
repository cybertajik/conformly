"""Italy Personal Data Protection Code (Codice della Privacy) Pack Definition.

Covers:
- 6 core statutory provisions under D.Lgs. 196/2003 as amended by D.Lgs. 101/2018
- Digital consent threshold for minors (Art 2-quinquies - Age 14)
- General authorizations and deontological rules for health, genetic, and biometric data (Art 2-septies)
- Workplace privacy safeguards under Statuto dei Lavoratori (Art 113 & Art 4 L. 300/1970)
- Unsolicited commercial communications and spam controls (Art 130)
- Garante corrective measures and inspection compliance (Art 144)
- Mandatory regulatory requests and investigations cooperation (Art 157)
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

IT_GARANTE_AUTHORITY = "Garante per la protezione dei dati personali (Garante Privacy)"
IT_GARANTE_EDITION = "Codice in materia di protezione dei dati personali (D.Lgs. 30 giugno 2003, n. 196 novellato dal D.Lgs. 10 agosto 2018, n. 101)"
IT_GARANTE_RIGHTS = "Public Domain Statute (Repubblica Italiana)."
IT_GARANTE_URL = "https://www.garanteprivacy.it/codice"

IT_GARANTE_SECTIONS: list[tuple[str, str, str, str, str]] = [
    (
        "Art-2-quinquies",
        "Digital Consent Age for Minors (Age 14 Threshold)",
        "In relation to information society services offered directly to a child, processing of personal data is lawful based on the minor's consent if the minor is at least 14 years old; otherwise, processing is lawful only with authorization from parental responsibility holders.",
        "Consent & Child Protection",
        "At registration point / Continuous",
    ),
    (
        "Art-2-septies",
        "Deontological Rules for Genetic, Biometric & Health Data",
        "Comply with general measures and deontological rules issued periodically by the Garante regarding the processing of genetic data, biometric data, and health data, ensuring enhanced encryption, pseudonymization, and separated access logs.",
        "Special Category Data",
        "Prior to processing / Annual review",
    ),
    (
        "Art-113",
        "Workplace Privacy Safeguards & Remote Worker Monitoring",
        "Observe the safeguards provided by Article 4 of Law No. 300 of 20 May 1970 (Workers' Statute / Statuto dei Lavoratori); audiovisual equipment and remote monitoring instruments may only be installed following trade union agreement or Labor Inspectorate authorization.",
        "Workplace Privacy",
        "Prior to monitoring implementation / Annual review",
    ),
    (
        "Art-130",
        "Unsolicited Electronic Communications & Telemarketing Safeguards",
        "Enforce strict prior opt-in consent for automated calling systems, emails, faxes, and SMS marketing; respect the Public Registry of Oppositions (Registro Pubblico delle Opposizioni) before initiating telemarketing activities.",
        "Consumer Choice & Marketing",
        "Prior to outbound campaigns / Continuous registry sync",
    ),
    (
        "Art-144",
        "Garante Corrective Injunctions & Remediation Compliance",
        "Establish operational processes to promptly execute corrective orders, processing bans, temporary limitations, or remediation notices issued by the Garante per la protezione dei dati personali within statutory deadlines.",
        "Regulatory Oversight",
        "Immediate / Event-driven response",
    ),
    (
        "Art-157",
        "Cooperation with Garante Investigations & Inquiries",
        "Furnish information, documents, and records requested by the Garante during inquiries or inspections within specified deadlines, maintaining comprehensive technical access logs and audit trails.",
        "Audit & Regulatory Cooperation",
        "Within deadlines specified in Garante requests",
    ),
]

IT_GARANTE_CONTROLS: list[PackControlDefinition] = []
IT_GARANTE_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
IT_GARANTE_MAPPINGS: list[PackMappingDefinition] = []
IT_GARANTE_EVIDENCE: list[PackEvidenceDefinition] = []
IT_GARANTE_COVERAGE: list[PackCoverageDefinition] = []

for idx, (sec_num, title, desc, cat, cadence) in enumerate(IT_GARANTE_SECTIONS, start=1):
    ctrl_id = f"IT-GARANTE-{sec_num.replace('.', '-')}"
    src_ref = f"D.Lgs. 196/2003 {sec_num.replace('-', ' ')}"

    guidance = (
        f"**Implementation Guidance:** Operationalize workflows, workplace monitoring agreements, and technical controls to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented policy, age gating records, trade union agreements for remote monitoring, opt-in consent records, or Garante inquiry logs satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Italian Privacy Code & Garante Compliance Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    IT_GARANTE_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    IT_GARANTE_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=IT_GARANTE_AUTHORITY,
            edition_or_amendment=IT_GARANTE_EDITION,
            source_text=desc,
            content_rights=IT_GARANTE_RIGHTS,
            source_url=IT_GARANTE_URL,
            conformly_guidance=f"Operationalize compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    IT_GARANTE_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly operationalizes statutory requirement {src_ref}.",
        )
    )

    IT_GARANTE_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-IT-GARANTE-{sec_num.replace('.', '_').replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"Operational policy, union authorization agreements, consent logs, telemarketing screening records, or inquiry responses for {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    IT_GARANTE_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Italian Privacy Code requirement {sec_num} covered by control {ctrl_id}.",
        )
    )

IT_GARANTE_PRIVACY_PACK = FrameworkPackDefinition(
    slug="it-garante-privacy",
    name="Italy Personal Data Protection Code (Codice della Privacy)",
    version="v2018",
    description="Italy Personal Data Protection Code (D.Lgs. 196/2003 novellato dal D.Lgs. 101/2018) national GDPR overlay covering minor consent (age 14), workplace monitoring under Statuto dei Lavoratori, and Garante rules.",
    release_notes="Active release pack covering Italian national privacy overlays and Garante deontological measures.",
    legal_review_notes="Provisions extracted from D.Lgs. 196/2003 as modified by D.Lgs. 101/2018.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=IT_GARANTE_CONTROLS,
    source_requirements=IT_GARANTE_SOURCE_REQS,
    mappings=IT_GARANTE_MAPPINGS,
    evidence_specifications=IT_GARANTE_EVIDENCE,
    coverage_ledger=IT_GARANTE_COVERAGE,
)
