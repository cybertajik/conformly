"""Colorado Privacy Act (CPA) Pack Definition.

Covers:
- 6 core statutory requirements under Colo. Rev. Stat. § 6-1-1301 et seq.
- Scope and applicability thresholds under § 6-1-1304
- Processor duties and binding contracts under § 6-1-1305
- Consumer personal data rights (access, correct, delete, portability) under § 6-1-1306
- Universal opt-out mechanisms and targeted advertising/profiling opt-out under § 6-1-1307
- Controller duties (transparency, data minimization, security, sensitive data consent) under § 6-1-1308
- Data protection assessments (DPAs) for high-risk processing under § 6-1-1309
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

CPA_AUTHORITY = "State of Colorado / Colorado Department of Law (Office of the Attorney General)"
CPA_EDITION = "Colorado Privacy Act (Colo. Rev. Stat. § 6-1-1301 et seq.)"
CPA_RIGHTS = "Public Domain State Statute (State of Colorado)."
CPA_URL = "https://coag.gov/resources/colorado-privacy-act/"

CPA_SECTIONS: list[tuple[str, str, str, str, str]] = [
    (
        "6-1-1304",
        "CPA Scope, Applicability & Consumer Thresholds",
        "Establish statutory applicability under CPA (entities conducting business in Colorado or producing products/services intentionally targeted to Colorado residents that control/process personal data of 100,000+ consumers per calendar year, or derive revenue or discounts from selling personal data of 25,000+ consumers).",
        "Governance & Scope",
        "Annual review & assessment",
    ),
    (
        "6-1-1305",
        "Processor Duties & Mandatory Binding Contracts",
        "Enforce written controller-processor contracts specifying processing details, duty of confidentiality, sub-processor authorization, security measures, and deletion or return of personal data upon contract completion.",
        "Vendor & Third-Party Management",
        "Prior to vendor engagement / Annual review",
    ),
    (
        "6-1-1306",
        "Consumer Personal Data Rights & 45-Day Fulfillment",
        "Provide consumers the right to access personal data, rectify inaccuracies, delete personal data, and obtain personal data in a portable, readily usable format within 45 days of a authenticated consumer request.",
        "Consumer Rights & Requests",
        "Within 45 days of request (with 45-day extension notice)",
    ),
    (
        "6-1-1307",
        "Universal Opt-Out Mechanisms (UOOM) & Targeted Ads Opt-Out",
        "Enable consumers to opt out of the processing of personal data for targeted advertising, sale of personal data, and profiling in furtherance of automated decisions that produce legal or similarly significant effects, including recognizing user-selected universal opt-out mechanisms.",
        "Consumer Choice & Opt-Out",
        "Immediate / Continuous automated signal processing",
    ),
    (
        "6-1-1308",
        "Duties of Controllers: Transparency, Minimization & Sensitive Consent",
        "Maintain accessible, clear, and meaningful privacy notices; limit data collection to adequate, relevant, and necessary purposes; maintain reasonable security practices; and obtain affirmative, freely given opt-in consent prior to processing sensitive data or minor data.",
        "Data Protection Safeguards",
        "Continuous / Quarterly review",
    ),
    (
        "6-1-1309",
        "Data Protection Assessments (DPAs)",
        "Conduct and document a formal data protection assessment before initiating processing that presents a heightened risk of harm (targeted advertising, profiling, selling personal data, and processing sensitive data), weighing benefits against potential consumer harms.",
        "Risk Assessment & DPIA",
        "Prior to initiating high-risk processing / Annual review",
    ),
]

CPA_CONTROLS: list[PackControlDefinition] = []
CPA_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
CPA_MAPPINGS: list[PackMappingDefinition] = []
CPA_EVIDENCE: list[PackEvidenceDefinition] = []
CPA_COVERAGE: list[PackCoverageDefinition] = []

for idx, (sec_num, title, desc, cat, cadence) in enumerate(CPA_SECTIONS, start=1):
    ctrl_id = f"CPA-{sec_num.replace('.', '-')}"
    src_ref = f"Colo. Rev. Stat. § {sec_num}"

    guidance = (
        f"**Implementation Guidance:** Operationalize workflows, technical controls, and governance policies to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented applicability assessment, consumer rights request logs, universal opt-out mechanism tests, DPA records, or processor contracts satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Colorado Privacy Act Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    CPA_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    CPA_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=CPA_AUTHORITY,
            edition_or_amendment=CPA_EDITION,
            source_text=desc,
            content_rights=CPA_RIGHTS,
            source_url=CPA_URL,
            conformly_guidance=f"Operationalize compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    CPA_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly operationalizes statutory requirement {src_ref}.",
        )
    )

    CPA_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-CPA-{sec_num.replace('.', '_')}",
            title=f"Evidence for {title}",
            description=f"Operational documentation, verification logs, assessment reports, or contracts for {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    CPA_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"CPA statutory requirement {sec_num} covered by control {ctrl_id}.",
        )
    )

US_CO_CPA_PACK = FrameworkPackDefinition(
    slug="us-co-cpa",
    name="Colorado Privacy Act (CPA)",
    version="v2023",
    description="Colorado Privacy Act (Colo. Rev. Stat. § 6-1-1301 et seq.) establishing comprehensive consumer privacy rights, universal opt-out mechanisms, and DPAs.",
    release_notes="Active release pack covering Colorado consumer rights, universal opt-out signals, DPAs, and controller duties.",
    legal_review_notes="Statutory provisions extracted directly from Colo. Rev. Stat. § 6-1-1301 et seq.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=CPA_CONTROLS,
    source_requirements=CPA_SOURCE_REQS,
    mappings=CPA_MAPPINGS,
    evidence_specifications=CPA_EVIDENCE,
    coverage_ledger=CPA_COVERAGE,
)
