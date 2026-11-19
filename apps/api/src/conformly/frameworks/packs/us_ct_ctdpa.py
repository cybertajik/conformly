"""Connecticut Data Privacy Act (CTDPA) Pack Definition.

Covers:
- 6 core statutory requirements under Conn. Gen. Stat. § 42-515 et seq.
- Scope and applicability thresholds under § 42-517
- Consumer rights, 45-day response timeline, and mandatory appeals process under § 42-518
- Controller duties (transparency notices, purpose limitation, technical safeguards) under § 42-520
- Sensitive data opt-in consent and heightened teen privacy protections (ages 13-16) under § 42-521
- Data protection assessments (DPAs) for heightened risk processing under § 42-522
- Controller-processor contracting and sub-processor oversight under § 42-523
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

CTDPA_AUTHORITY = "State of Connecticut / Office of the Attorney General"
CTDPA_EDITION = (
    "Connecticut Data Privacy Act (Conn. Gen. Stat. § 42-515 et seq. / Public Act No. 22-15)"
)
CTDPA_RIGHTS = "Public Domain State Statute (State of Connecticut)."
CTDPA_URL = "https://portal.ct.gov/AG/Sections/Privacy/Connecticut-Data-Privacy-Act"

CTDPA_SECTIONS: list[tuple[str, str, str, str, str]] = [
    (
        "42-517",
        "CTDPA Scope, Applicability & Consumer Thresholds",
        "Establish statutory applicability under CTDPA (entities conducting business in Connecticut or producing products/services targeted to Connecticut residents that control/process personal data of 100,000+ consumers, or 25,000+ consumers with 25%+ gross revenue from selling personal data).",
        "Governance & Scope",
        "Annual review & assessment",
    ),
    (
        "42-518",
        "Consumer Personal Data Rights & Appeals Process",
        "Provide consumers the right to access, correct inaccuracies, delete, obtain a copy in portable format, and opt out of targeted advertising, sale of personal data, and profiling; respond within 45 days; and establish an internal appeals process for denied requests with Attorney General referral notice.",
        "Consumer Rights & Requests",
        "Within 45 days of request (plus 60-day appeals turnaround)",
    ),
    (
        "42-520",
        "Controller Duties, Purpose Limitation & Security Safeguards",
        "Maintain accessible and clear privacy notices detailing categories, purposes, and sharing; limit data collection to adequate and necessary purposes; maintain reasonable administrative, technical, and physical security safeguards; and prohibit unlawful discrimination.",
        "Data Protection Safeguards",
        "Continuous / Quarterly review",
    ),
    (
        "42-521",
        "Sensitive Data Consent & Teen Privacy Protections (Ages 13-16)",
        "Prohibit processing sensitive personal data without affirmative opt-in consent, and prohibit processing personal data for targeted advertising or selling personal data of consumers aged 13 to 16 without their explicit consent.",
        "Consent & Minor Protection",
        "Prior to collection or processing",
    ),
    (
        "42-522",
        "Data Protection Assessments (DPAs)",
        "Conduct and document a formal data protection assessment for each processing activity involving targeted advertising, selling personal data, profiling presenting heightened risk of harm, sensitive data, or any processing presenting reasonably foreseeable risk of substantial injury.",
        "Risk Assessment & DPIA",
        "Prior to initiating high-risk processing / Annual review",
    ),
    (
        "42-523",
        "Controller-Processor Binding Contracts & Oversight",
        "Execute and maintain binding written agreements with processors governing processing instructions, duration, nature and purpose of processing, confidentiality, technical security, deletion or return of data, and audit/inspection assistance.",
        "Vendor & Third-Party Management",
        "Prior to vendor engagement / Annual review",
    ),
]

CTDPA_CONTROLS: list[PackControlDefinition] = []
CTDPA_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
CTDPA_MAPPINGS: list[PackMappingDefinition] = []
CTDPA_EVIDENCE: list[PackEvidenceDefinition] = []
CTDPA_COVERAGE: list[PackCoverageDefinition] = []

for idx, (sec_num, title, desc, cat, cadence) in enumerate(CTDPA_SECTIONS, start=1):
    ctrl_id = f"CTDPA-{sec_num.replace('.', '-')}"
    src_ref = f"Conn. Gen. Stat. § {sec_num}"

    guidance = (
        f"**Implementation Guidance:** Operationalize workflows, governance procedures, and security controls to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented applicability assessment, consumer rights request and appeals records, consent logs, teen data safeguards, DPA records, or processor contracts satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Connecticut Data Privacy Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    CTDPA_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    CTDPA_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=CTDPA_AUTHORITY,
            edition_or_amendment=CTDPA_EDITION,
            source_text=desc,
            content_rights=CTDPA_RIGHTS,
            source_url=CTDPA_URL,
            conformly_guidance=f"Operationalize compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    CTDPA_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly operationalizes statutory requirement {src_ref}.",
        )
    )

    CTDPA_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-CTDPA-{sec_num.replace('.', '_')}",
            title=f"Evidence for {title}",
            description=f"Operational documentation, verification logs, assessment reports, appeals documentation, or contracts for {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    CTDPA_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"CTDPA statutory requirement {sec_num} covered by control {ctrl_id}.",
        )
    )

US_CT_CTDPA_PACK = FrameworkPackDefinition(
    slug="us-ct-ctdpa",
    name="Connecticut Data Privacy Act (CTDPA)",
    version="v2023",
    description="Connecticut Data Privacy Act (Conn. Gen. Stat. § 42-515 et seq.) establishing comprehensive consumer privacy rights, appeals mechanisms, and teen privacy protections.",
    release_notes="Active release pack covering Connecticut consumer rights, appeals workflows, DPAs, teen privacy safeguards, and processor contracts.",
    legal_review_notes="Statutory provisions extracted directly from Conn. Gen. Stat. § 42-515 et seq.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=CTDPA_CONTROLS,
    source_requirements=CTDPA_SOURCE_REQS,
    mappings=CTDPA_MAPPINGS,
    evidence_specifications=CTDPA_EVIDENCE,
    coverage_ledger=CTDPA_COVERAGE,
)
