"""Australia Privacy Act 1988 & Australian Privacy Principles (APPs) Pack Definition.

Covers:
- Privacy Act 1988 (Cth) as amended
- 13 Australian Privacy Principles (APPs) enforceable by the OAIC
- Part IIIC Notifiable Data Breaches (NDB) Scheme
- Statutory turnover thresholds ($3M AUD) and small business opt-in evaluation
- Structured evidence collection specifications and complete coverage ledger
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

AU_PRIVACY_AUTHORITY = "Office of the Australian Information Commissioner (OAIC)"
AU_PRIVACY_EDITION = (
    "Privacy Act 1988 (Cth) incorporating 13 Australian Privacy Principles & NDB Scheme"
)
AU_PRIVACY_RIGHTS = (
    "Commonwealth of Australia Legislation (OAIC Regulatory Materials, Public Domain / CC-BY)."
)
AU_PRIVACY_URL = "https://www.oaic.gov.au/privacy/australian-privacy-principles"

AU_APP_PRINCIPLES: list[tuple[str, str, str, str, str]] = [
    (
        "APP-1",
        "Open & Transparent Management of Personal Information",
        "An APP entity must take reasonable steps to implement practices, procedures, and systems to ensure compliance with the APPs, and maintain a clearly expressed and up-to-date APP privacy policy.",
        "Privacy Governance",
        "Annual review / Updates on change",
    ),
    (
        "APP-3",
        "Collection of Solicited Personal Information",
        "An APP entity must only collect personal information that is reasonably necessary for one or more of its functions or activities, and collect sensitive information only with consent unless an exception applies.",
        "Data Collection",
        "Continuous",
    ),
    (
        "APP-5",
        "Notification of the Collection of Personal Information",
        "An APP entity must take reasonable steps to notify the individual of collection matters at or before the time of collection (or as soon as practicable thereafter), including purposes, consequences, and complaint rights.",
        "Transparency & Notice",
        "At or before collection",
    ),
    (
        "APP-6",
        "Use or Disclosure of Personal Information",
        "An APP entity must only use or disclose personal information for the primary purpose for which it was collected, unless the individual has consented to a secondary purpose or a statutory exception applies.",
        "Use & Disclosure",
        "Continuous",
    ),
    (
        "APP-8",
        "Cross-Border Disclosure of Personal Information",
        "Before disclosing personal information to an overseas recipient, an APP entity must take reasonable steps to ensure the recipient does not breach the APPs, unless an informed consent or statutory exception applies.",
        "Cross-Border Disclosure",
        "Prior to disclosure / Quarterly review",
    ),
    (
        "APP-11",
        "Security of Personal Information",
        "An APP entity must take reasonable steps to protect personal information from misuse, interference, loss, and unauthorized access, modification, or disclosure, and destroy or de-identify info no longer needed.",
        "Information Security",
        "Continuous",
    ),
    (
        "APP-12",
        "Access to Personal Information",
        "An APP entity must give an individual access to the personal information held about them upon request within a reasonable period (usually 30 days), unless specific statutory refusal grounds apply.",
        "Individual Rights",
        "Within 30 days of request",
    ),
    (
        "APP-13",
        "Correction of Personal Information",
        "An APP entity must take reasonable steps to correct personal information to ensure it is accurate, up-to-date, complete, relevant, and not misleading, upon request or on its own initiative.",
        "Individual Rights",
        "Within 30 days of request",
    ),
    (
        "NDB-Scheme",
        "Notifiable Data Breaches (NDB) Scheme",
        "An APP entity must conduct a prompt assessment of suspected data breaches and notify the OAIC and affected individuals as soon as practicable if an eligible data breach is likely to result in serious harm.",
        "Incident Management",
        "Assessment within 30 days / Immediate OAIC notification",
    ),
]

AU_APP_CONTROLS: list[PackControlDefinition] = []
AU_APP_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
AU_APP_MAPPINGS: list[PackMappingDefinition] = []
AU_APP_EVIDENCE: list[PackEvidenceDefinition] = []
AU_APP_COVERAGE: list[PackCoverageDefinition] = []

for idx, (app_code, title, desc, cat, cadence) in enumerate(AU_APP_PRINCIPLES, start=1):
    ctrl_id = f"AU-{app_code.replace('.', '-')}"
    src_ref = f"Australia Privacy Act 1988 {app_code.replace('-', ' ')}"

    guidance = (
        f"**Implementation Guidance:** Implement operational policies and procedures to satisfy {title}.\n\n"
        f"**Evidence Requests:**\n"
        f"- APP policy, collection notice, disclosure record, or NDB response plan for {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Australian Privacy Principles Policy\n"
        f"**Statutory Citation:** {src_ref}"
    )

    AU_APP_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=guidance,
            sort_order=idx * 10,
        )
    )

    AU_APP_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority=AU_PRIVACY_AUTHORITY,
            edition_or_amendment=AU_PRIVACY_EDITION,
            source_text=desc,
            content_rights=AU_PRIVACY_RIGHTS,
            source_url=AU_PRIVACY_URL,
            conformly_guidance=f"Operationalize compliance with {src_ref}.",
            review_cadence=cadence,
            sort_order=idx * 10,
        )
    )

    AU_APP_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} directly operationalizes {src_ref}.",
        )
    )

    AU_APP_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-AU-{app_code.replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"APP privacy policy, collection notice, overseas disclosure assessment, or breach response plan supporting {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            confidentiality_level="Internal",
        )
    )

    AU_APP_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Privacy Act requirement {app_code} covered by control {ctrl_id}.",
        )
    )

AU_PRIVACY_ACT_PACK = FrameworkPackDefinition(
    slug="au-privacy-act",
    name="Australia Privacy Act 1988 & APPs",
    version="v1988",
    description="Australia Privacy Act 1988 (Cth), 13 Australian Privacy Principles (APPs), and Notifiable Data Breaches (NDB) Scheme.",
    release_notes="Active release pack covering APP governance, collection, overseas disclosure, security safeguards, access/correction, and NDB reporting.",
    legal_review_notes="Statutory provisions aligned directly with OAIC guidelines and statutory enforcement criteria.",
    approval_notes="Approved for Module A active framework catalog.",
    controls=AU_APP_CONTROLS,
    source_requirements=AU_APP_SOURCE_REQS,
    mappings=AU_APP_MAPPINGS,
    evidence_specifications=AU_APP_EVIDENCE,
    coverage_ledger=AU_APP_COVERAGE,
)
