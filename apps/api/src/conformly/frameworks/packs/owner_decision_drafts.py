"""Reviewable draft definitions for OWNER_DECISION_REQUIRED framework candidates.

Covers reviewable drafts for:
1. California Consumer Privacy Act & CPRA (Cal. Civ. Code § 1798.100 et seq.)
2. Saudi Arabia Personal Data Protection Law (Royal Decree M/19 & SDAIA regulations)
3. Japan Act on the Protection of Personal Information (APPI Act No. 57 of 2003)
4. Australia Privacy Act 1988 & Australian Privacy Principles (APPs)

Note: ISO 9001:2015 was promoted from OWNER_DECISION_REQUIRED to a full Tier A pack
(REQUIRED_BETA) per Product Owner decision on 2026-09-13 (ADR D-059). Its implementation
has moved to `packs/iso_9001.py`.

These packs remain in DRAFT status pending formal Product Owner scope confirmation
before being admitted into active release gating.
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

# -----------------------------------------------------------------------------
CCPA_SECTIONS = [
    (
        "1798.100",
        "Notice at Collection",
        "A business that collects a consumer's personal information shall, at or before the point of collection, inform consumers of categories collected and purposes.",
        "Consumer Transparency",
    ),
    (
        "1798.105",
        "Consumer Right to Delete",
        "A consumer shall have the right to request that a business delete any personal information about the consumer which the business has collected.",
        "Consumer Rights",
    ),
    (
        "1798.106",
        "Consumer Right to Correct Inaccurate Information",
        "A consumer shall have the right to request a business correct inaccurate personal information.",
        "Consumer Rights",
    ),
    (
        "1798.110",
        "Consumer Right to Know What Personal Information is Collected",
        "A consumer shall have the right to request that a business disclose categories and specific pieces of personal information collected.",
        "Consumer Rights",
    ),
    (
        "1798.120",
        "Right to Opt-Out of Sale or Sharing",
        "A consumer shall have the right, at any time, to direct a business that sells or shares personal information not to sell or share the information.",
        "Consumer Choice & Opt-Out",
    ),
    (
        "1798.121",
        "Right to Limit Use of Sensitive Personal Information",
        "A consumer shall have the right to direct a business to limit its use of sensitive personal information.",
        "Consumer Choice & Opt-Out",
    ),
    (
        "1798.125",
        "Non-Discrimination",
        "A business shall not discriminate against a consumer because the consumer exercised any of the consumer's rights under this title.",
        "Consumer Rights",
    ),
    (
        "1798.140-T",
        "Statutory Scope & Revenue Thresholds",
        "Applies to for-profit businesses exceeding $25M gross revenue, or buying/selling/sharing 100k consumers, or deriving 50% revenue from selling.",
        "Applicability & Scope",
    ),
]

CCPA_CONTROLS: list[PackControlDefinition] = []
CCPA_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
CCPA_MAPPINGS: list[PackMappingDefinition] = []
CCPA_EVIDENCE: list[PackEvidenceDefinition] = []
CCPA_COVERAGE: list[PackCoverageDefinition] = []

for idx, (sec_num, title, desc, cat) in enumerate(CCPA_SECTIONS, start=1):
    ctrl_id = f"CCPA-{sec_num.replace('.', '-')}"
    src_ref = f"Cal. Civ. Code § {sec_num}"
    CCPA_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=f"**Implementation Guidance:** Implement operational workflows for {title}.\n**Statutory Citation:** {src_ref}",
            sort_order=idx * 10,
        )
    )
    CCPA_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority="State of California / California Privacy Protection Agency (CPPA)",
            edition_or_amendment="California Consumer Privacy Act as amended by CPRA",
            source_text=desc,
            content_rights="Public Domain State Statute.",
            source_url="https://oag.ca.gov/privacy/ccpa",
            conformly_guidance=f"Operationalize CCPA/CPRA requirements under § {sec_num}.",
            sort_order=idx * 10,
        )
    )
    CCPA_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} satisfies {src_ref}.",
        )
    )
    CCPA_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-CCPA-{sec_num.replace('.', '_').replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"Privacy policy notice, opt-out link verification, or request log for {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
        )
    )
    CCPA_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"CCPA requirement {sec_num} covered by draft control {ctrl_id}.",
        )
    )

CCPA_DRAFT_PACK = FrameworkPackDefinition(
    slug="us-ca-ccpa-cpra",
    name="California Consumer Privacy Act (CCPA / CPRA)",
    version="v2023-draft",
    description="Reviewable draft covering California Consumer Privacy Act (CCPA) and CPRA amendments.",
    release_notes="Initial reviewable draft pack prepared for Product Owner scope evaluation.",
    legal_review_notes="Pending Product Owner decision for US regional privacy expansion.",
    approval_notes="Draft only - not approved for production release.",
    controls=CCPA_CONTROLS,
    source_requirements=CCPA_SOURCE_REQS,
    mappings=CCPA_MAPPINGS,
    evidence_specifications=CCPA_EVIDENCE,
    coverage_ledger=CCPA_COVERAGE,
)

# -----------------------------------------------------------------------------
# 3. Saudi Arabia PDPL
# -----------------------------------------------------------------------------
SA_PDPL_ARTICLES = [
    (
        "Art-4",
        "Data Subject Rights",
        "Data subjects have the right to know, right to request access, right to request correction, and right to request destruction.",
        "PDPL Rights",
    ),
    (
        "Art-5",
        "Consent as General Legal Basis",
        "Consent of the data subject is required for personal data processing, subject to statutory exceptions.",
        "PDPL Lawfulness",
    ),
    (
        "Art-12",
        "Privacy Policy & Transparency Notice",
        "Controllers must adopt a privacy policy and make it available to data subjects prior to collecting data.",
        "PDPL Transparency",
    ),
    (
        "Art-18",
        "Security & Protection Measures",
        "Controllers must implement necessary organizational, administrative, and technical measures to protect data.",
        "PDPL Security",
    ),
    (
        "Art-24",
        "Breach Notification",
        "Controllers must notify the competent authority (SDAIA) of data breaches without undue delay.",
        "PDPL Incident Response",
    ),
    (
        "Art-29",
        "Cross-Border Transfer Conditions",
        "Controllers may transfer personal data outside the Kingdom only under SDAIA adequacy or specific exemptions.",
        "PDPL Transfers",
    ),
]

SA_PDPL_CONTROLS: list[PackControlDefinition] = []
SA_PDPL_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
SA_PDPL_MAPPINGS: list[PackMappingDefinition] = []
SA_PDPL_EVIDENCE: list[PackEvidenceDefinition] = []
SA_PDPL_COVERAGE: list[PackCoverageDefinition] = []

for idx, (art_num, title, desc, cat) in enumerate(SA_PDPL_ARTICLES, start=1):
    ctrl_id = f"SA-PDPL-{art_num.replace('.', '-')}"
    src_ref = f"Saudi Arabia PDPL (Royal Decree M/19) {art_num}"
    SA_PDPL_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=f"**Implementation Guidance:** Implement SDAIA PDPL controls for {title}.\n**Citation:** {src_ref}",
            sort_order=idx * 10,
        )
    )
    SA_PDPL_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority="Saudi Data & AI Authority (SDAIA)",
            edition_or_amendment="Royal Decree No. M/19 & Implementing Regulations",
            source_text=desc,
            content_rights="Public Law of the Kingdom of Saudi Arabia.",
            source_url="https://sdaia.gov.sa/",
            conformly_guidance=f"Operationalize SDAIA PDPL {art_num}.",
            sort_order=idx * 10,
        )
    )
    SA_PDPL_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} satisfies {src_ref}.",
        )
    )
    SA_PDPL_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-SA-{art_num.replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"Policy or operational record supporting {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
        )
    )
    SA_PDPL_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"PDPL article {art_num} satisfied by draft control {ctrl_id}.",
        )
    )

SA_PDPL_DRAFT_PACK = FrameworkPackDefinition(
    slug="sa-pdpl",
    name="Saudi Arabia Personal Data Protection Law (PDPL)",
    version="v2023-draft",
    description="Reviewable draft covering Saudi Arabia Personal Data Protection Law (Royal Decree M/19).",
    release_notes="Initial reviewable draft pack prepared for Product Owner scope evaluation.",
    legal_review_notes="Pending Product Owner decision for Middle East regional privacy expansion.",
    approval_notes="Draft only - not approved for production release.",
    controls=SA_PDPL_CONTROLS,
    source_requirements=SA_PDPL_SOURCE_REQS,
    mappings=SA_PDPL_MAPPINGS,
    evidence_specifications=SA_PDPL_EVIDENCE,
    coverage_ledger=SA_PDPL_COVERAGE,
)

# -----------------------------------------------------------------------------
# 4. Japan APPI
# -----------------------------------------------------------------------------
JP_APPI_ARTICLES = [
    (
        "Art-17",
        "Specification of Utilization Purpose",
        "Business operators handling personal information must specify the purpose of use as explicitly as possible.",
        "APPI Purpose",
    ),
    (
        "Art-20",
        "Safety Control Measures",
        "Business operators must take necessary and appropriate measures for the security control of personal data.",
        "APPI Security",
    ),
    (
        "Art-21",
        "Supervision of Employees",
        "Business operators must exercise necessary and appropriate supervision over employees to ensure security.",
        "APPI Governance",
    ),
    (
        "Art-22",
        "Supervision of Trustees / Contractors",
        "When entrusting data handling, business operators must exercise necessary supervision over trustees.",
        "APPI Governance",
    ),
    (
        "Art-26",
        "Breach Reporting to PPC",
        "Business operators must report significant personal data leaks to the Personal Information Protection Commission (PPC).",
        "APPI Breach",
    ),
    (
        "Art-28",
        "Restriction on Provision to Third Parties in Foreign Countries",
        "Provision of personal data to third parties in foreign countries requires consent or equivalent systems.",
        "APPI Transfers",
    ),
]

JP_APPI_CONTROLS: list[PackControlDefinition] = []
JP_APPI_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
JP_APPI_MAPPINGS: list[PackMappingDefinition] = []
JP_APPI_EVIDENCE: list[PackEvidenceDefinition] = []
JP_APPI_COVERAGE: list[PackCoverageDefinition] = []

for idx, (art_num, title, desc, cat) in enumerate(JP_APPI_ARTICLES, start=1):
    ctrl_id = f"JP-APPI-{art_num.replace('.', '-')}"
    src_ref = f"Japan APPI (Act No. 57 of 2003) {art_num}"
    JP_APPI_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=f"**Implementation Guidance:** Implement PPC APPI controls for {title}.\n**Citation:** {src_ref}",
            sort_order=idx * 10,
        )
    )
    JP_APPI_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority="Personal Information Protection Commission (PPC) Japan",
            edition_or_amendment="Act on the Protection of Personal Information (Act No. 57 of 2003 as amended)",
            source_text=desc,
            content_rights="Japanese Statutory Public Domain.",
            source_url="https://www.ppc.go.jp/en/",
            conformly_guidance=f"Operationalize APPI {art_num}.",
            sort_order=idx * 10,
        )
    )
    JP_APPI_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} satisfies {src_ref}.",
        )
    )
    JP_APPI_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-JP-{art_num.replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"Policy or operational record supporting {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
        )
    )
    JP_APPI_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"APPI article {art_num} satisfied by draft control {ctrl_id}.",
        )
    )

JP_APPI_DRAFT_PACK = FrameworkPackDefinition(
    slug="jp-appi",
    name="Japan Act on the Protection of Personal Information (APPI)",
    version="v2022-draft",
    description="Reviewable draft covering Japan APPI (Act No. 57 of 2003 as amended).",
    release_notes="Initial reviewable draft pack prepared for Product Owner scope evaluation.",
    legal_review_notes="Pending Product Owner decision for APAC regional privacy expansion.",
    approval_notes="Draft only - not approved for production release.",
    controls=JP_APPI_CONTROLS,
    source_requirements=JP_APPI_SOURCE_REQS,
    mappings=JP_APPI_MAPPINGS,
    evidence_specifications=JP_APPI_EVIDENCE,
    coverage_ledger=JP_APPI_COVERAGE,
)

# -----------------------------------------------------------------------------
# 5. Australia Privacy Act 1988 & APPs
# -----------------------------------------------------------------------------
AU_APP_PRINCIPLES = [
    (
        "APP-1",
        "Open and Transparent Management of Personal Information",
        "Take reasonable steps to implement practices, procedures and systems ensuring compliance with APPs.",
        "Australian Privacy Principles",
    ),
    (
        "APP-3",
        "Collection of Solicited Personal Information",
        "Only collect personal information that is reasonably necessary for one or more functions or activities.",
        "Australian Privacy Principles",
    ),
    (
        "APP-5",
        "Notification of the Collection of Personal Information",
        "Take reasonable steps to notify individuals of collection matters at or before collection.",
        "Australian Privacy Principles",
    ),
    (
        "APP-6",
        "Use or Disclosure of Personal Information",
        "Only use or disclose personal information for the primary purpose unless an exception applies.",
        "Australian Privacy Principles",
    ),
    (
        "APP-8",
        "Cross-Border Disclosure of Personal Information",
        "Take reasonable steps to ensure overseas recipient does not breach APPs before disclosing personal info.",
        "Australian Privacy Principles",
    ),
    (
        "APP-11",
        "Security of Personal Information",
        "Take reasonable steps to protect personal information from misuse, interference, loss, and unauthorized access.",
        "Australian Privacy Principles",
    ),
    (
        "APP-12",
        "Access to Personal Information",
        "Give individuals access to their personal information upon request unless statutory exceptions apply.",
        "Australian Privacy Principles",
    ),
    (
        "APP-13",
        "Correction of Personal Information",
        "Take reasonable steps to correct personal information to ensure it is accurate, up-to-date, and complete.",
        "Australian Privacy Principles",
    ),
    (
        "NDB-Scheme",
        "Notifiable Data Breaches (NDB) Scheme",
        "Notify OAIC and affected individuals of eligible data breaches likely to result in serious harm.",
        "Australian Privacy Principles",
    ),
]

AU_APP_CONTROLS: list[PackControlDefinition] = []
AU_APP_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
AU_APP_MAPPINGS: list[PackMappingDefinition] = []
AU_APP_EVIDENCE: list[PackEvidenceDefinition] = []
AU_APP_COVERAGE: list[PackCoverageDefinition] = []

for idx, (app_code, title, desc, cat) in enumerate(AU_APP_PRINCIPLES, start=1):
    ctrl_id = f"AU-{app_code.replace('.', '-')}"
    src_ref = f"Australia Privacy Act 1988 {app_code.replace('-', ' ')}"
    AU_APP_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat,
            guidance=f"**Implementation Guidance:** Implement OAIC APP controls for {title}.\n**Citation:** {src_ref}",
            sort_order=idx * 10,
        )
    )
    AU_APP_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.STATUTORY,
            source_authority="Office of the Australian Information Commissioner (OAIC)",
            edition_or_amendment="Privacy Act 1988 (Cth) incorporating 13 APPs & NDB Scheme",
            source_text=desc,
            content_rights="Commonwealth of Australia legislation (Public Domain / CC-BY).",
            source_url="https://www.oaic.gov.au/",
            conformly_guidance=f"Operationalize {src_ref}.",
            sort_order=idx * 10,
        )
    )
    AU_APP_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Control {ctrl_id} satisfies {src_ref}.",
        )
    )
    AU_APP_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-AU-{app_code.replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"APP Privacy Policy, collection notice, or security procedures supporting {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
        )
    )
    AU_APP_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"APP requirement {app_code} satisfied by draft control {ctrl_id}.",
        )
    )

AU_PRIVACY_ACT_DRAFT_PACK = FrameworkPackDefinition(
    slug="au-privacy-act",
    name="Australia Privacy Act 1988 & APPs",
    version="v1988-draft",
    description="Reviewable draft covering Australia Privacy Act 1988, 13 APPs, and NDB Scheme.",
    release_notes="Initial reviewable draft pack prepared for Product Owner scope evaluation.",
    legal_review_notes="Pending Product Owner decision for APAC regional privacy expansion.",
    approval_notes="Draft only - not approved for production release.",
    controls=AU_APP_CONTROLS,
    source_requirements=AU_APP_SOURCE_REQS,
    mappings=AU_APP_MAPPINGS,
    evidence_specifications=AU_APP_EVIDENCE,
    coverage_ledger=AU_APP_COVERAGE,
)

OWNER_DECISION_DRAFT_PACKS: list[FrameworkPackDefinition] = [
    CCPA_DRAFT_PACK,
    SA_PDPL_DRAFT_PACK,
    JP_APPI_DRAFT_PACK,
    AU_PRIVACY_ACT_DRAFT_PACK,
]
