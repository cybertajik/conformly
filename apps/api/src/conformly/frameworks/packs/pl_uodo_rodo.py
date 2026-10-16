"""Poland Personal Data Protection Act (Ustawa o ochronie danych osobowych) Pack Definition.

Covers:
- 6 core statutory provisions under the Act of 10 May 2018 (Dz.U. 2018 poz. 1000) & Polish Labor Code
- Mandatory notification of DPO (IOD) appointment to UODO within 14 days (Art 10)
- Designation, qualification, and independence standards for DPOs (Art 11)
- Workplace data collection and employee consent rules under Polish Labor Code (Art 22-1a)
- Workplace video surveillance and electronic email monitoring restrictions (Art 22-2)
- UODO administrative inspections and audit compliance protocols (Art 60)
- Enforcement measures, financial sanctions, and rectification orders (Art 78)
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

PL_UODO_AUTHORITY = "Urząd Ochrony Danych Osobowych (UODO)"
PL_UODO_EDITION = (
    "Ustawa z dnia 10 maja 2018 r. o ochronie danych osobowych (Dz.U. 2018 poz. 1000 z późn. zm.)"
)
PL_UODO_RIGHTS = "Public Domain Statute (Rzeczpospolita Polska)."
PL_UODO_URL = "https://uodo.gov.pl/pl/p/prawo"

PL_UODO_SECTIONS: list[tuple[str, str, str, str, str]] = [
    (
        "Art-10",
        "Mandatory 14-Day DPO Notification to UODO",
        "Notify the President of the Personal Data Protection Office (Prezes UODO) of the appointment of a Data Protection Officer (Inspektor Ochrony Danych - IOD) within 14 days of appointment, submitting verified contact details electronically.",
        "Governance & DPO Oversight",
        "Within 14 days of appointment / Upon change",
    ),
    (
        "Art-11",
        "IOD Designation, Independence & Resource Guarantee",
        "Ensure the appointed IOD directly reports to the highest management level, operates with functional independence without conflict of interest, and is provided adequate resources and access to all processing operations.",
        "Governance & DPO Oversight",
        "Annual review & organizational audit",
    ),
    (
        "KP-Art-22-1a",
        "Workplace Data Collection & Employee Consent Boundaries",
        "In accordance with Article 22-1a of the Polish Labor Code, ensure lack of employee consent or refusal to grant consent cannot result in adverse treatment or disadvantage in hiring, promotion, or employment conditions.",
        "Workplace Privacy & Consent",
        "Continuous / HR policy audit",
    ),
    (
        "KP-Art-22-2",
        "Workplace Video & Email Monitoring Restrictions",
        "Restrict workplace CCTV and electronic communication (email/internet) monitoring to safety and asset protection; prohibit cameras in trade union premises and sanitary facilities; and inform employees in writing at least 14 days before activation.",
        "Surveillance & Workplace Privacy",
        "14 days prior to activation / Continuous signage",
    ),
    (
        "Art-60",
        "UODO Administrative Inspection & Audit Cooperation",
        "Maintain documented registers, system architectures, and technical personnel ready to cooperate with inspectors of the President of UODO during announced or unannounced compliance audits.",
        "Regulatory Oversight & Inspections",
        "Continuous readiness / Event-driven inspection response",
    ),
    (
        "Art-78",
        "UODO Enforcement Remediation & Fine Mitigation",
        "Establish internal mechanisms to document and prove proactive compliance, immediate remediation of identified infractions, and full cooperation to mitigate potential UODO administrative fines.",
        "Compliance Governance & Sanctions",
        "Annual compliance review",
    ),
]

PL_UODO_CONTROLS: list[PackControlDefinition] = []
PL_UODO_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
PL_UODO_MAPPINGS: list[PackMappingDefinition] = []
PL_UODO_EVIDENCE: list[PackEvidenceDefinition] = []
PL_UODO_COVERAGE: list[PackCoverageDefinition] = []

for idx, (sec_num, title, desc, cat, cadence) in enumerate(PL_UODO_SECTIONS, start=1):
    ctrl_id = f"PL-UODO-{sec_num.replace('.', '-')}"
    src_ref = f"UODO/KP {sec_num.replace('-', ' ')}"

    guidance = (
        f"**Implementation Guidance:** Operationalize workflows, workplace monitoring notices, and governance policies to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented policy, UODO electronic notification receipt (ePUAP confirmation), 14-day prior monitoring notice letters, or inspection logs satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Polish National Privacy & UODO Compliance Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    PL_UODO_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    PL_UODO_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=PL_UODO_AUTHORITY,
            edition_or_amendment=PL_UODO_EDITION,
            source_text=desc,
            content_rights=PL_UODO_RIGHTS,
            source_url=PL_UODO_URL,
            conformly_guidance=f"Operationalize compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    PL_UODO_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly operationalizes statutory requirement {src_ref}.",
        )
    )

    PL_UODO_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-PL-UODO-{sec_num.replace('.', '_').replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"Operational policy, UODO filing receipt, workplace monitoring regulations, or inspection responses for {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    PL_UODO_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Polish UODO/KP requirement {sec_num} covered by control {ctrl_id}.",
        )
    )

PL_UODO_RODO_PACK = FrameworkPackDefinition(
    slug="pl-uodo-rodo",
    name="Poland Personal Data Protection Act (RODO / UODO)",
    version="v2018",
    description="Poland Personal Data Protection Act of 10 May 2018 (Dz.U. 2018 poz. 1000) national GDPR overlay covering 14-day IOD notification, workplace monitoring under Labor Code, and UODO audit procedures.",
    release_notes="Active release pack covering Polish national privacy overlays and workplace surveillance constraints.",
    legal_review_notes="Provisions extracted from the Act of 10 May 2018 and the Polish Labor Code.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=PL_UODO_CONTROLS,
    source_requirements=PL_UODO_SOURCE_REQS,
    mappings=PL_UODO_MAPPINGS,
    evidence_specifications=PL_UODO_EVIDENCE,
    coverage_ledger=PL_UODO_COVERAGE,
)
