"""Ireland Data Protection Act 2018 Pack Definition.

Covers:
- 6 core statutory provisions under Irish Data Protection Act 2018 (Act 7 of 2018)
- Digital consent threshold for minors (Section 31 - Age 16)
- Legal professional privilege protections from subject access disclosures (Section 41)
- Electoral and political communication processing rules (Section 55)
- Direct marketing opt-out safeguards (Section 59)
- Lawful restrictions on data subject rights to protect legal proceedings (Section 60)
- Data Protection Commission (DPC) enforcement, inquiries, and judicial remedies (Section 69)
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

IE_DPC_AUTHORITY = "Data Protection Commission (DPC)"
IE_DPC_EDITION = "Data Protection Act 2018 (Act No. 7 of 2018)"
IE_DPC_RIGHTS = "Public Domain Statute (Ireland / Oireachtas)."
IE_DPC_URL = "https://www.dataprotection.ie/en/legislation/data-protection-act-2018"

IE_DPC_SECTIONS: list[tuple[str, str, str, str, str]] = [
    (
        "Sec-31",
        "Digital Consent Age for Minors (Age 16 Threshold)",
        "Under Irish law, the age of digital consent for the direct provision of information society services to a child is 16 years; consent for a child under 16 is lawful only if given or authorized by a parent or legal guardian.",
        "Consent & Child Protection",
        "At point of registration / Continuous",
    ),
    (
        "Sec-41",
        "Legal Professional Privilege Protections from Access Requests",
        "Protect legal professional privilege by ensuring data subject access rights (DSARs) under GDPR Article 15 do not compel disclosure of confidential communications between clients and professional legal advisers.",
        "Consumer Rights & Legal Privilege",
        "Upon receipt of DSAR / Legal review",
    ),
    (
        "Sec-55",
        "Electoral & Public Purpose Processing Safeguards",
        "Ensure personal data processed for electoral activities, political opinions, or public office representation complies with strict statutory registration and transparency rules under Irish law.",
        "Special Category Data",
        "Annual review / Campaign execution",
    ),
    (
        "Sec-59",
        "Direct Marketing Opt-Out & Statutory Communications Safeguards",
        "Enforce prompt and permanent cessation of electronic communications or profiling for direct marketing purposes immediately upon receipt of a data subject's objection without charging any fee.",
        "Consumer Choice & Marketing",
        "Immediate / Continuous",
    ),
    (
        "Sec-60",
        "Restrictions on Data Subject Rights for Legal Defense",
        "Apply permitted statutory restrictions on GDPR rights (Articles 12-22 and 34) where necessary to prevent prejudice to legal claims, criminal investigations, taxation assessments, or regulatory proceedings.",
        "Consumer Rights & Exclusions",
        "Case-by-case legal determination",
    ),
    (
        "Sec-69",
        "Data Protection Commission (DPC) Compliance & Inquiries",
        "Cooperate fully with statutory inquiries, compliance notices, and enforcement notices served by the Irish Data Protection Commission (DPC), maintaining comprehensive audit logs of all processing operations.",
        "Regulatory Oversight & DPC Cooperation",
        "Within timeframes specified in DPC notices",
    ),
]

IE_DPC_CONTROLS: list[PackControlDefinition] = []
IE_DPC_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
IE_DPC_MAPPINGS: list[PackMappingDefinition] = []
IE_DPC_EVIDENCE: list[PackEvidenceDefinition] = []
IE_DPC_COVERAGE: list[PackCoverageDefinition] = []

for idx, (sec_num, title, desc, cat, cadence) in enumerate(IE_DPC_SECTIONS, start=1):
    ctrl_id = f"IE-DPC-{sec_num.replace('.', '-')}"
    src_ref = f"Data Protection Act 2018 {sec_num.replace('-', ' ')}"

    guidance = (
        f"**Implementation Guidance:** Operationalize workflows, DSAR privilege screening, and governance documentation to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented policy, age gating records, legal privilege exemption review checklists, marketing opt-out logs, or DPC correspondence records satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Irish National Privacy & DPC Compliance Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    IE_DPC_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    IE_DPC_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=IE_DPC_AUTHORITY,
            edition_or_amendment=IE_DPC_EDITION,
            source_text=desc,
            content_rights=IE_DPC_RIGHTS,
            source_url=IE_DPC_URL,
            conformly_guidance=f"Operationalize compliance under {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    IE_DPC_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly operationalizes statutory requirement {src_ref}.",
        )
    )

    IE_DPC_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-IE-DPC-{sec_num.replace('.', '_').replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"Operational procedures, age verification records, legal privilege determination memos, or DPC compliance logs for {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    IE_DPC_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Irish Data Protection Act requirement {sec_num} covered by control {ctrl_id}.",
        )
    )

IE_DPC_DPA_PACK = FrameworkPackDefinition(
    slug="ie-dpc-dpa",
    name="Ireland Data Protection Act 2018",
    version="v2018",
    description="Ireland Data Protection Act 2018 (Act 7 of 2018) national GDPR overlay covering minor consent (age 16), legal privilege protections, and DPC enforcement.",
    release_notes="Active release pack covering Irish national privacy overlays and statutory exception frameworks.",
    legal_review_notes="Provisions extracted from the Data Protection Act 2018 (Act 7 of 2018).",
    approval_notes="Approved for Module A active framework catalog.",
    controls=IE_DPC_CONTROLS,
    source_requirements=IE_DPC_SOURCE_REQS,
    mappings=IE_DPC_MAPPINGS,
    evidence_specifications=IE_DPC_EVIDENCE,
    coverage_ledger=IE_DPC_COVERAGE,
)
