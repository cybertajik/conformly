"""Texas Data Privacy and Security Act (TDPSA) Pack Definition.

Covers:
- 6 core statutory requirements under Tex. Bus. & Com. Code Ann. § 541.001 et seq.
- Broad entity applicability and small business carveouts under § 541.002
- Consumer personal data rights and 45-day response timeline under § 541.051
- Controller duties (privacy notice, purpose limitation, security practices) under § 541.101
- Sensitive data consent and statutory disclosure for selling sensitive data under § 541.102
- Data protection assessments (DPAs) for heightened risk processing under § 541.103
- Processor responsibilities and mandatory contractual provisions under § 541.104
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

TDPSA_AUTHORITY = "State of Texas / Office of the Attorney General"
TDPSA_EDITION = "Texas Data Privacy and Security Act (Tex. Bus. & Com. Code Ann. § 541.001 et seq.)"
TDPSA_RIGHTS = "Public Domain State Statute (State of Texas)."
TDPSA_URL = "https://statutes.capitol.texas.gov/Docs/BC/htm/BC.541.htm"

TDPSA_SECTIONS: list[tuple[str, str, str, str, str]] = [
    (
        "541.002",
        "TDPSA Scope, Broad Applicability & Small Business Verification",
        "Establish statutory applicability under TDPSA (persons conducting business in Texas or producing products/services consumed by Texas residents, excluding small businesses as defined by the U.S. Small Business Administration except regarding prohibited sales of sensitive data without consent).",
        "Governance & Scope",
        "Annual review & assessment",
    ),
    (
        "541.051",
        "Texas Consumer Personal Data Rights & 45-Day Response",
        "Operationalize mechanisms for Texas consumers to confirm processing, access personal data, correct inaccuracies, delete personal data, obtain a portable digital copy, and opt out of processing for targeted advertising, sale of personal data, and profiling producing legal effects.",
        "Consumer Rights & Requests",
        "Within 45 days of request (plus 45-day extension if reasonably necessary)",
    ),
    (
        "541.101",
        "Controller Duties, Privacy Notice & Data Security Safeguards",
        "Provide a reasonably accessible, clear, and meaningful privacy notice; limit data collection to adequate and relevant purposes; establish, implement, and maintain reasonable administrative, technical, and physical data security practices; and prohibit discriminatory treatment.",
        "Data Protection Safeguards",
        "Continuous / Quarterly review",
    ),
    (
        "541.102",
        "Sensitive Data Consent & Statutory Sale Disclosures",
        "Prohibit processing of sensitive personal data without affirmative opt-in consent, and publish prominent statutory notices if selling sensitive data ('NOTICE: We may sell your sensitive personal data') or biometric data ('NOTICE: We may sell your biometric personal data').",
        "Consent & Statutory Disclosures",
        "Prior to collection or sale",
    ),
    (
        "541.103",
        "Data Protection Assessments (DPAs)",
        "Conduct and document a formal data protection assessment for activities involving targeted advertising, selling personal data, profiling presenting heightened risk, sensitive data, or any processing presenting reasonably foreseeable risk of substantial injury.",
        "Risk Assessment & DPIA",
        "Prior to initiating high-risk processing / Annual review",
    ),
    (
        "541.104",
        "Processor Responsibilities & Contractual Requirements",
        "Enforce written contracts between controllers and processors specifying processing instructions, duration, nature and purpose, duty of confidentiality, security safeguards, sub-processor obligations, and assistance with audits and compliance.",
        "Vendor & Third-Party Management",
        "Prior to vendor engagement / Annual review",
    ),
]

TDPSA_CONTROLS: list[PackControlDefinition] = []
TDPSA_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
TDPSA_MAPPINGS: list[PackMappingDefinition] = []
TDPSA_EVIDENCE: list[PackEvidenceDefinition] = []
TDPSA_COVERAGE: list[PackCoverageDefinition] = []

for idx, (sec_num, title, desc, cat, cadence) in enumerate(TDPSA_SECTIONS, start=1):
    ctrl_id = f"TDPSA-{sec_num.replace('.', '-')}"
    src_ref = f"Tex. Bus. & Com. Code § {sec_num}"

    guidance = (
        f"**Implementation Guidance:** Operationalize workflows, transparency notices, and technical security controls to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented applicability assessment, privacy notices, request logs, opt-in consent records, statutory sale disclosures, DPA reports, or processor contracts satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Texas Data Privacy and Security Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    TDPSA_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    TDPSA_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=TDPSA_AUTHORITY,
            edition_or_amendment=TDPSA_EDITION,
            source_text=desc,
            content_rights=TDPSA_RIGHTS,
            source_url=TDPSA_URL,
            conformly_guidance=f"Operationalize compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    TDPSA_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly operationalizes statutory requirement {src_ref}.",
        )
    )

    TDPSA_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-TDPSA-{sec_num.replace('.', '_')}",
            title=f"Evidence for {title}",
            description=f"Operational documentation, verification logs, statutory notices, assessment reports, or contracts for {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    TDPSA_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"TDPSA statutory requirement {sec_num} covered by control {ctrl_id}.",
        )
    )

US_TX_TDPSA_PACK = FrameworkPackDefinition(
    slug="us-tx-tdpsa",
    name="Texas Data Privacy and Security Act (TDPSA)",
    version="v2024",
    description="Texas Data Privacy and Security Act (Tex. Bus. & Com. Code Ann. § 541.001 et seq.) establishing comprehensive consumer privacy rights, distinct sensitive data sale notices, and DPAs.",
    release_notes="Active release pack covering Texas consumer rights, statutory sale disclosures, DPAs, and controller-processor contracting.",
    legal_review_notes="Statutory provisions extracted directly from Tex. Bus. & Com. Code Ann. § 541.001 et seq.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=TDPSA_CONTROLS,
    source_requirements=TDPSA_SOURCE_REQS,
    mappings=TDPSA_MAPPINGS,
    evidence_specifications=TDPSA_EVIDENCE,
    coverage_ledger=TDPSA_COVERAGE,
)
