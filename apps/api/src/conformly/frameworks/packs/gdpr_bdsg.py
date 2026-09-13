"""EU GDPR (Regulation (EU) 2016/679) and German BDSG Privacy Operations Pack Definition.

Covers:
- Core principles, lawfulness, consent, and special category processing (Articles 5-10)
- Data subject rights and transparency obligations (Articles 12-22)
- Controller and Processor operational obligations, TOMs, VVT, breaches, DPIAs, and DPOs (Articles 24-39)
- International data transfer safeguards and transfer impact assessments (Articles 44-49)
- German BDSG specific supplements (§ 26 Employment data, § 38 DPO appointment criteria)
- Explicit coverage ledger entries for supervisory authority provisions (Articles 51-76, 85-99)
  classified as NOT_CUSTOMER_OBLIGATION with legal rationale.
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

GDPR_AUTHORITY = "European Parliament and Council of the European Union"
GDPR_EDITION = "Regulation (EU) 2016/679 (GDPR)"
GDPR_RIGHTS = (
    "EU Public Sector Information / Official Journal of the European Union. Public domain statute."
)
GDPR_URL = "https://eur-lex.europa.eu/eli/reg/2016/679/oj"

BDSG_AUTHORITY = "Federal Republic of Germany (Bundesministerium der Justiz)"
BDSG_EDITION = "BDSG n.F. (Bundesdatenschutzgesetz 2018 as amended)"
BDSG_RIGHTS = "German Federal Law / Public Domain statute under § 5 UrhG."
BDSG_URL = "https://www.gesetze-im-internet.de/bdsg_2018/"

# Customer-Facing GDPR Articles
GDPR_CUSTOMER_ARTICLES: list[tuple[str, str, str, str, str]] = [
    (
        "Art-5-1-a",
        "Lawfulness, Fairness and Transparency",
        "Personal data shall be processed lawfully, fairly and in a transparent manner in relation to the data subject.",
        "Principles & Lawfulness",
        "Continuous",
    ),
    (
        "Art-5-1-b",
        "Purpose Limitation",
        "Personal data shall be collected for specified, explicit and legitimate purposes and not further processed in an incompatible manner.",
        "Principles & Lawfulness",
        "Continuous",
    ),
    (
        "Art-5-1-c",
        "Data Minimisation",
        "Personal data shall be adequate, relevant and limited to what is necessary in relation to the purposes for which they are processed.",
        "Principles & Lawfulness",
        "Continuous",
    ),
    (
        "Art-5-1-d",
        "Accuracy",
        "Personal data shall be accurate and, where necessary, kept up to date; reasonable steps must be taken to erase or rectify inaccurate data.",
        "Principles & Lawfulness",
        "Quarterly",
    ),
    (
        "Art-5-1-e",
        "Storage Limitation",
        "Personal data shall be kept in a form which permits identification for no longer than necessary for processing purposes.",
        "Principles & Lawfulness",
        "Quarterly",
    ),
    (
        "Art-5-1-f",
        "Integrity and Confidentiality",
        "Personal data shall be processed in a manner ensuring appropriate security, including protection against unauthorized access, loss, or damage.",
        "Technical & Organisational Measures",
        "Continuous",
    ),
    (
        "Art-5-2",
        "Accountability Principle",
        "The controller shall be responsible for, and be able to demonstrate compliance with, the data protection principles.",
        "Governance & Accountability",
        "Continuous",
    ),
    (
        "Art-6",
        "Lawfulness of Processing",
        "Processing is lawful only if at least one legal basis applies: consent, contract performance, legal obligation, vital interests, public task, or legitimate interests.",
        "Principles & Lawfulness",
        "Annual review",
    ),
    (
        "Art-7",
        "Conditions for Consent",
        "Where processing is based on consent, the controller shall be able to demonstrate consent and data subjects must be able to withdraw consent easily.",
        "Consent Management",
        "Continuous",
    ),
    (
        "Art-8",
        "Child's Consent in Information Society Services",
        "Where information society services are offered to children, consent must be authorized by parental responsibility holder.",
        "Consent Management",
        "Continuous",
    ),
    (
        "Art-9",
        "Processing of Special Categories of Data",
        "Processing of biometric, genetic, health, or racial/ethnic data is prohibited unless specific statutory exceptions apply.",
        "Sensitive Data Processing",
        "Continuous",
    ),
    (
        "Art-10",
        "Processing Relating to Criminal Convictions",
        "Processing of personal data relating to criminal convictions shall be carried out only under official authority control.",
        "Sensitive Data Processing",
        "Continuous",
    ),
    (
        "Art-12",
        "Transparent Modalities for Exercising Rights",
        "The controller shall provide information in a concise, transparent, intelligible and easily accessible form, using clear and plain language.",
        "Transparency & Notices",
        "Continuous",
    ),
    (
        "Art-13",
        "Information Notice: Direct Collection",
        "Where personal data are collected directly from data subjects, provide identity, DPO contacts, purposes, legal bases, recipients, and retention periods.",
        "Transparency & Notices",
        "Annual review",
    ),
    (
        "Art-14",
        "Information Notice: Indirect Collection",
        "Where personal data are not obtained from the data subject, provide required transparency information within one month.",
        "Transparency & Notices",
        "Continuous",
    ),
    (
        "Art-15",
        "Right of Access by Data Subject",
        "Data subjects have the right to obtain confirmation as to whether personal data concerning them are processed and access to that data.",
        "Data Subject Rights",
        "Continuous",
    ),
    (
        "Art-16",
        "Right to Rectification",
        "Data subjects have the right to obtain without undue delay the rectification of inaccurate personal data concerning them.",
        "Data Subject Rights",
        "Continuous",
    ),
    (
        "Art-17",
        "Right to Erasure ('Right to be Forgotten')",
        "Data subjects have the right to obtain erasure of personal data without undue delay when statutory grounds apply.",
        "Data Subject Rights",
        "Continuous",
    ),
    (
        "Art-18",
        "Right to Restriction of Processing",
        "Data subjects have the right to obtain restriction of processing where accuracy is contested, unlawful, or needed for legal claims.",
        "Data Subject Rights",
        "Continuous",
    ),
    (
        "Art-19",
        "Notification Obligation: Rectification or Erasure",
        "The controller shall communicate any rectification, erasure or restriction to each recipient to whom personal data have been disclosed.",
        "Data Subject Rights",
        "Continuous",
    ),
    (
        "Art-20",
        "Right to Data Portability",
        "Data subjects have the right to receive their personal data in a structured, commonly used and machine-readable format.",
        "Data Subject Rights",
        "Continuous",
    ),
    (
        "Art-21",
        "Right to Object",
        "Data subjects have the right to object to processing based on legitimate interests or direct marketing at any time.",
        "Data Subject Rights",
        "Continuous",
    ),
    (
        "Art-22",
        "Automated Individual Decision-Making & Profiling",
        "Data subjects have the right not to be subject to a decision based solely on automated processing having legal or significant effects.",
        "Data Subject Rights",
        "Continuous",
    ),
    (
        "Art-24",
        "Responsibility of the Controller",
        "Implement appropriate technical and organizational measures to ensure and demonstrate processing is performed in accordance with GDPR.",
        "Governance & Accountability",
        "Annual review",
    ),
    (
        "Art-25",
        "Data Protection by Design and by Default",
        "Implement technical and organisational measures (e.g. pseudonymisation, minimisation) at the time of determination of means and during processing.",
        "Technical & Organisational Measures",
        "Continuous",
    ),
    (
        "Art-26",
        "Joint Controllers",
        "Where two or more controllers determine purposes and means jointly, transparently determine their respective responsibilities by arrangement.",
        "Contracts & Vendor Management",
        "Continuous",
    ),
    (
        "Art-28",
        "Processor Obligations & Data Processing Agreements",
        "Processing by a processor shall be governed by a binding contract (DPA) setting out subject-matter, duration, nature, purpose, and required security clauses.",
        "Contracts & Vendor Management",
        "Continuous",
    ),
    (
        "Art-29",
        "Processing Under Authority",
        "Processors and persons acting under authority of controller or processor shall not process data except on instructions from controller.",
        "Contracts & Vendor Management",
        "Continuous",
    ),
    (
        "Art-30",
        "Records of Processing Activities (VVT)",
        "Maintain a comprehensive record of processing activities under its responsibility containing categories of data, purposes, recipients, and security measures.",
        "Governance & Accountability",
        "Quarterly",
    ),
    (
        "Art-31",
        "Cooperation with Supervisory Authority",
        "The controller and processor shall cooperate, on request, with the supervisory authority in the performance of its tasks.",
        "Governance & Accountability",
        "As needed",
    ),
    (
        "Art-32",
        "Security of Processing (TOMs)",
        "Implement technical and organizational measures to ensure a level of security appropriate to risk, including encryption, resilience, and regular testing.",
        "Technical & Organisational Measures",
        "Continuous",
    ),
    (
        "Art-33",
        "Personal Data Breach Notification to DPA",
        "In the event of a personal data breach, notify the competent supervisory authority without undue delay and, where feasible, within 72 hours.",
        "Breach & Incident Response",
        "Continuous",
    ),
    (
        "Art-34",
        "Communication of Personal Data Breach to Data Subject",
        "When the breach is likely to result in a high risk to rights and freedoms of individuals, communicate breach to data subjects without undue delay.",
        "Breach & Incident Response",
        "Continuous",
    ),
    (
        "Art-35",
        "Data Protection Impact Assessment (DPIA)",
        "Where processing is likely to result in a high risk, carry out an assessment of the impact of the envisaged processing operations on data protection.",
        "Risk & Impact Assessment",
        "As needed",
    ),
    (
        "Art-36",
        "Prior Consultation",
        "Consult the supervisory authority prior to processing where DPIA indicates that processing would result in high risk in absence of mitigation measures.",
        "Risk & Impact Assessment",
        "As needed",
    ),
    (
        "Art-37",
        "Designation of the Data Protection Officer (DPO)",
        "Designate a DPO where processing is carried out by public authority, core activities require regular systematic monitoring, or special categories are processed on large scale.",
        "Governance & Accountability",
        "Annual review",
    ),
    (
        "Art-38",
        "Position of the Data Protection Officer",
        "Ensure DPO is involved properly and in timely manner in all issues relating to protection of personal data and reports to highest management level.",
        "Governance & Accountability",
        "Annual review",
    ),
    (
        "Art-39",
        "Tasks of the Data Protection Officer",
        "DPO shall inform, advise, monitor compliance with GDPR, provide advice on DPIAs, and act as contact point for supervisory authority.",
        "Governance & Accountability",
        "Continuous",
    ),
    (
        "Art-44",
        "General Principle for International Transfers",
        "Any transfer of personal data to a third country or international organisation shall take place only if conditions in Chapter V are complied with.",
        "International Data Transfers",
        "Continuous",
    ),
    (
        "Art-45",
        "Transfers on Basis of Adequacy Decision",
        "Transfers to a third country or territory which the European Commission has decided ensures an adequate level of protection may proceed without further authorization.",
        "International Data Transfers",
        "Annual review",
    ),
    (
        "Art-46",
        "Transfers Subject to Appropriate Safeguards (SCCs)",
        "In absence of an adequacy decision, controller or processor may transfer personal data only if appropriate safeguards (such as SCCs) are provided.",
        "International Data Transfers",
        "Continuous",
    ),
    (
        "Art-49",
        "Derogations for Specific Situations",
        "In absence of adequacy decision or appropriate safeguards, transfer only if explicit consent, contract performance, or legal claims exception applies.",
        "International Data Transfers",
        "Continuous",
    ),
    (
        "BDSG-SEC-22",
        "Special Categories of Personal Data (§ 22 BDSG)",
        "Processing of special categories of personal data by public and non-public bodies is permitted only where statutory exceptions apply.",
        "German Jurisdictional Overlay",
        "Annual review",
    ),
    (
        "BDSG-SEC-26",
        "Data Processing for Employment Purposes (§ 26 BDSG)",
        "Personal data of employees may be processed for employment-related purposes if necessary for hiring, performance, or termination, or collective agreements.",
        "German Jurisdictional Overlay",
        "Annual review",
    ),
    (
        "BDSG-SEC-38",
        "Designation of DPO Under German Law (§ 38 BDSG)",
        "Controllers in Germany must designate a DPO if they constantly employ at least 20 persons with automated processing, or conduct mandatory DPIAs, or commercial transmission.",
        "German Jurisdictional Overlay",
        "Annual review",
    ),
]

# Supervisory Authority and Administrative Provisions (Non-Customer Obligations)
GDPR_AUTHORITY_PROVISIONS: list[tuple[str, str, str]] = [
    (
        "Art-51",
        "Supervisory Authority Independence & Establishment",
        "Member States shall provide for one or more independent public authorities to monitor GDPR application.",
    ),
    (
        "Art-52",
        "Independence of Supervisory Authority",
        "Supervisory authorities shall act with complete independence in performing tasks and exercising powers.",
    ),
    (
        "Art-53",
        "General Conditions for Supervisory Authority Members",
        "Rules on appointment, qualifications, and term of members of supervisory authorities.",
    ),
    (
        "Art-54",
        "Rules on the Establishment of the Supervisory Authority",
        "Statutory requirements for national legislation creating supervisory authority bodies.",
    ),
    (
        "Art-55",
        "Competence of Supervisory Authorities",
        "Supervisory authority competence rules based on territory of its own Member State.",
    ),
    (
        "Art-56",
        "Competence of the Lead Supervisory Authority",
        "Rules governing one-stop-shop mechanism and lead supervisory authority determinations.",
    ),
    (
        "Art-57",
        "Tasks of the Supervisory Authority",
        "Statutory duties of supervisory authorities (monitoring, handling complaints, conducting investigations).",
    ),
    (
        "Art-58",
        "Powers of the Supervisory Authority",
        "Investigative, corrective, authorization, and advisory powers of supervisory authorities.",
    ),
    (
        "Art-59",
        "Activity Reports of Supervisory Authorities",
        "Requirement for each supervisory authority to draw up an annual activity report.",
    ),
    (
        "Art-60-76",
        "Cooperation, Consistency Mechanism & European Data Protection Board",
        "Institutional rules for inter-authority cooperation, consistency opinions, and European Data Protection Board governance.",
    ),
    (
        "Art-85-99",
        "Specific Processing Situations, Delegated Acts & Final Provisions",
        "Member State derogations for freedom of expression, official documents, national identification numbers, committee procedures, and repeal of Directive 95/46/EC.",
    ),
]

GDPR_CONTROLS: list[PackControlDefinition] = []
GDPR_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
GDPR_MAPPINGS: list[PackMappingDefinition] = []
GDPR_EVIDENCE: list[PackEvidenceDefinition] = []
GDPR_COVERAGE: list[PackCoverageDefinition] = []

sort_idx = 10

# 1. Customer-Facing Articles
for art_code, title, desc, category, cadence in GDPR_CUSTOMER_ARTICLES:
    is_bdsg = art_code.startswith("BDSG")
    ctrl_id = art_code if is_bdsg else f"GDPR-{art_code.upper()}"
    authority = BDSG_AUTHORITY if is_bdsg else GDPR_AUTHORITY
    edition = BDSG_EDITION if is_bdsg else GDPR_EDITION
    rights = BDSG_RIGHTS if is_bdsg else GDPR_RIGHTS
    url = BDSG_URL if is_bdsg else GDPR_URL
    src_ref = (
        f"BDSG § {art_code.split('-')[-1]}"
        if is_bdsg
        else f"Regulation (EU) 2016/679 {art_code.replace('-', ' ')}"
    )

    guidance = (
        f"**Implementation Guidance:** Establish operational procedures to comply with {title}. "
        f"Maintain verifiable records of compliance.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented policies, registers, or operational records satisfying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Data Protection Policy\n"
        f"**Legal Citation:** {src_ref}"
    )

    GDPR_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=category,
            guidance=guidance,
            sort_order=sort_idx,
        )
    )
    GDPR_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.ARTICLE,
            source_authority=authority,
            edition_or_amendment=edition,
            source_text=desc,
            content_rights=rights,
            source_url=url,
            conformly_guidance=guidance,
            assessment_procedure=f"Review operational records, agreements, and policies satisfying {src_ref}.",
            default_owner_role="Data Protection Officer",
            review_cadence=cadence,
            sort_order=sort_idx,
        )
    )
    GDPR_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Canonical control {ctrl_id} satisfies statutory requirement {src_ref}.",
        )
    )
    GDPR_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-GDPR-{art_code.replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"Documentation or operational records demonstrating compliance with {src_ref}.",
            evidence_type="DOCUMENT" if "Notices" in category or "Rights" in category else "POLICY",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            original_file_required=False,
            confidentiality_level="Confidential" if "Sensitive" in category else "Internal",
        )
    )
    GDPR_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Statutory requirement {src_ref} operationalized by canonical control {ctrl_id}.",
        )
    )
    sort_idx += 10

# 2. Supervisory Authority and Institutional Provisions (NOT_CUSTOMER_OBLIGATION)
for art_code, title, desc in GDPR_AUTHORITY_PROVISIONS:
    src_ref = f"Regulation (EU) 2016/679 {art_code.replace('-', ' ')}"
    GDPR_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.ARTICLE,
            source_authority=GDPR_AUTHORITY,
            edition_or_amendment=GDPR_EDITION,
            source_text=desc,
            content_rights=GDPR_RIGHTS,
            source_url=GDPR_URL,
            conformly_guidance="Institutional provision aimed at public authorities; imposes no customer operational tasks.",
            sort_order=sort_idx,
        )
    )
    GDPR_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.NOT_CUSTOMER_OBLIGATION,
            rationale=(
                f"Statutory provision {src_ref} establishes institutional powers, member state mandates, "
                f"or supervisory authority consistency procedures; does not create operational obligations "
                f"for commercial controllers or processors."
            ),
        )
    )
    sort_idx += 10

GDPR_BDSG_PACK = FrameworkPackDefinition(
    slug="gdpr-bdsg",
    name="EU GDPR & German BDSG Privacy Operations",
    version="v2024",
    description=(
        "Comprehensive privacy compliance pack for Regulation (EU) 2016/679 (GDPR) and the "
        "German Federal Data Protection Act (BDSG n.F.). Covers Controller and Processor obligations, "
        "Data Subject Rights, TOMs, VVT (Art. 30), DPIA (Art. 35), DPO requirements (§ 38 BDSG), "
        "and international transfers. Fully accounts for supervisory authority provisions in the ledger."
    ),
    release_notes="Complete source-verified statutory coverage of GDPR Articles 5-49, BDSG § 26 and § 38, and authority dispositions.",
    legal_review_notes="Verified legal authority references, controller/processor applicability, and institutional dispositions.",
    approval_notes="Approved for canonical catalog release under Tier A beta scope.",
    controls=GDPR_CONTROLS,
    source_requirements=GDPR_SOURCE_REQS,
    mappings=GDPR_MAPPINGS,
    evidence_specifications=GDPR_EVIDENCE,
    coverage_ledger=GDPR_COVERAGE,
)
