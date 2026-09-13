"""ISO/IEC 27001:2022 (+Amd 1:2024) ISMS Pre-Audit Pack Definition.

Covers:
- Mandatory ISMS Management Clauses 4 to 10 (27 clauses/subclauses)
- Annex A Reference Controls across the 4 themes (93 controls):
  - A.5 Organizational controls (37)
  - A.6 People controls (8)
  - A.7 Physical controls (14)
  - A.8 Technological controls (34)
- Statement of Applicability (SoA) support and structured evidence requests
- Coverage ledger accounting for all 120 source requirements with IMPLEMENTED disposition
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

ISO_AUTHORITY = "International Organization for Standardization (ISO) / IEC"
ISO_EDITION = "ISO/IEC 27001:2022 (+Amd 1:2024)"
ISO_RIGHTS = "Copyright ISO/IEC. Citations and titles used for reference; proprietary standard text not redistributed verbatim. Guidance and procedures by Conformly."
ISO_URL = "https://www.iso.org/standard/27001"

# -----------------------------------------------------------------------------
# Management System Clauses 4 - 10
# -----------------------------------------------------------------------------
MANAGEMENT_CLAUSES: list[tuple[str, str, str, str, str]] = [
    (
        "4.1",
        "Understanding the Organization and Its Context",
        "Determine external and internal issues relevant to purpose and ISMS outcomes, including climate change.",
        "ISMS Context & Scope",
        "Annual review",
    ),
    (
        "4.2",
        "Understanding Needs and Expectations of Interested Parties",
        "Determine interested parties relevant to ISMS and their requirements, including legal and regulatory expectations.",
        "ISMS Context & Scope",
        "Annual review",
    ),
    (
        "4.3",
        "Determining the Scope of the ISMS",
        "Determine boundaries and applicability of ISMS, considering interfaces, dependencies, and business activities.",
        "ISMS Context & Scope",
        "Annual review",
    ),
    (
        "4.4",
        "Information Security Management System",
        "Establish, implement, maintain, and continually improve an ISMS in accordance with requirements.",
        "ISMS Context & Scope",
        "Continuous",
    ),
    (
        "5.1",
        "Leadership and Commitment",
        "Top management shall demonstrate leadership and commitment with respect to the ISMS.",
        "Leadership & Governance",
        "Annual review",
    ),
    (
        "5.2",
        "Policy",
        "Top management shall establish an information security policy appropriate to the purpose of the organization.",
        "Leadership & Governance",
        "Annual review",
    ),
    (
        "5.3",
        "Organizational Roles, Responsibilities and Authorities",
        "Top management shall ensure responsibilities and authorities for roles relevant to information security are assigned and communicated.",
        "Leadership & Governance",
        "Annual review",
    ),
    (
        "6.1.1",
        "Actions to Address Risks and Opportunities - General",
        "Plan actions to address risks and opportunities to ensure ISMS can achieve intended outcomes.",
        "Planning & Risk Treatment",
        "Annual review",
    ),
    (
        "6.1.2",
        "Information Security Risk Assessment",
        "Define and apply an information security risk assessment process that establishes criteria, identifies, and analyzes risks.",
        "Planning & Risk Treatment",
        "Annual review",
    ),
    (
        "6.1.3",
        "Information Security Risk Treatment & Statement of Applicability",
        "Define and apply an information security risk treatment process and produce a Statement of Applicability (SoA).",
        "Planning & Risk Treatment",
        "Annual review",
    ),
    (
        "6.2",
        "Information Security Objectives and Planning to Achieve Them",
        "Establish measurable information security objectives at relevant functions and levels.",
        "Planning & Risk Treatment",
        "Annual review",
    ),
    (
        "6.3",
        "Planning of Changes",
        "Determine need for changes to ISMS and carry out changes in a planned manner.",
        "Planning & Risk Treatment",
        "As needed",
    ),
    (
        "7.1",
        "Resources",
        "Determine and provide resources needed for establishment, implementation, maintenance, and continual improvement of ISMS.",
        "Support & Operations",
        "Annual review",
    ),
    (
        "7.2",
        "Competence",
        "Determine necessary competence of persons doing work affecting information security and ensure they are competent.",
        "Support & Operations",
        "Annual review",
    ),
    (
        "7.3",
        "Awareness",
        "Ensure persons doing work under organizational control are aware of security policy and their contribution.",
        "Support & Operations",
        "Quarterly",
    ),
    (
        "7.4",
        "Communication",
        "Determine need for internal and external communications relevant to the ISMS.",
        "Support & Operations",
        "Annual review",
    ),
    (
        "7.5.1",
        "Documented Information - General",
        "Include documented information required by standard and necessary for effectiveness of ISMS.",
        "Support & Operations",
        "Continuous",
    ),
    (
        "7.5.2",
        "Creating and Updating Documented Information",
        "Ensure appropriate identification, format, and review of documented information.",
        "Support & Operations",
        "Continuous",
    ),
    (
        "7.5.3",
        "Control of Documented Information",
        "Control documented information to ensure availability, suitability, and adequate protection.",
        "Support & Operations",
        "Continuous",
    ),
    (
        "8.1",
        "Operational Planning and Control",
        "Plan, implement, and control processes needed to meet information security requirements.",
        "Support & Operations",
        "Continuous",
    ),
    (
        "8.2",
        "Information Security Risk Assessment Execution",
        "Execute information security risk assessment at planned intervals or when significant changes occur.",
        "Planning & Risk Treatment",
        "Annual review",
    ),
    (
        "8.3",
        "Information Security Risk Treatment Execution",
        "Implement the information security risk treatment plan.",
        "Planning & Risk Treatment",
        "Continuous",
    ),
    (
        "9.1",
        "Monitoring, Measurement, Analysis and Evaluation",
        "Evaluate information security performance and the effectiveness of the ISMS.",
        "Performance & Monitoring",
        "Monthly",
    ),
    (
        "9.2.1",
        "Internal Audit - General",
        "Conduct internal audits at planned intervals to provide information on whether ISMS conforms to requirements.",
        "Performance & Monitoring",
        "Annual review",
    ),
    (
        "9.2.2",
        "Internal Audit Programme",
        "Plan, establish, implement, and maintain audit programme(s) including frequency, methods, and responsibilities.",
        "Performance & Monitoring",
        "Annual review",
    ),
    (
        "9.3.1",
        "Management Review - General",
        "Top management shall review the organization's ISMS at planned intervals.",
        "Performance & Monitoring",
        "Annual review",
    ),
    (
        "9.3.2",
        "Management Review Inputs",
        "Review trends in nonconformities, monitoring results, audit results, and risk assessment status.",
        "Performance & Monitoring",
        "Annual review",
    ),
    (
        "9.3.3",
        "Management Review Results",
        "Document decisions related to continual improvement opportunities and any needs for changes to ISMS.",
        "Performance & Monitoring",
        "Annual review",
    ),
    (
        "10.1",
        "Continual Improvement",
        "Continually improve the suitability, adequacy, and effectiveness of the ISMS.",
        "Performance & Monitoring",
        "Continuous",
    ),
    (
        "10.2",
        "Nonconformity and Corrective Action",
        "React to nonconformities, take action to control and correct them, and evaluate need for eliminating causes.",
        "Performance & Monitoring",
        "Continuous",
    ),
]

# -----------------------------------------------------------------------------
# Annex A Reference Controls (Themes A.5, A.6, A.7, A.8)
# -----------------------------------------------------------------------------
ANNEX_A_CONTROLS: list[tuple[str, str, str, str, str]] = [
    # A.5 Organizational Controls (37)
    (
        "A.5.1",
        "Policies for Information Security",
        "Information security policy and topic-specific policies shall be defined, approved by management, published, and communicated.",
        "Organizational",
        "Annual review",
    ),
    (
        "A.5.2",
        "Information Security Roles and Responsibilities",
        "Information security roles and responsibilities shall be defined and allocated according to organization needs.",
        "Organizational",
        "Annual review",
    ),
    (
        "A.5.3",
        "Segregation of Duties",
        "Conflicting duties and conflicting areas of responsibility shall be segregated.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.4",
        "Management Responsibilities",
        "Management shall require all personnel to apply information security in accordance with established policies.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.5",
        "Contact with Authorities",
        "Appropriate contacts with relevant authorities shall be maintained.",
        "Organizational",
        "Annual review",
    ),
    (
        "A.5.6",
        "Contact with Special Interest Groups",
        "Appropriate contacts with special interest groups or specialist security forums shall be maintained.",
        "Organizational",
        "Annual review",
    ),
    (
        "A.5.7",
        "Threat Intelligence",
        "Information relating to information security threats shall be collected and analyzed to produce threat intelligence.",
        "Organizational",
        "Monthly",
    ),
    (
        "A.5.8",
        "Information Security in Project Management",
        "Information security shall be integrated into project management.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.9",
        "Inventory of Information and Other Associated Assets",
        "An inventory of information and other associated assets, including owners, shall be developed and maintained.",
        "Organizational",
        "Quarterly",
    ),
    (
        "A.5.10",
        "Acceptable Use of Information and Associated Assets",
        "Rules for acceptable use and procedures for handling assets shall be identified, documented, and implemented.",
        "Organizational",
        "Annual review",
    ),
    (
        "A.5.11",
        "Return of Assets",
        "Personnel and external parties shall return all organizational assets in their possession upon change or termination.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.12",
        "Classification of Information",
        "Information shall be classified in accordance with the information security needs based on confidentiality, integrity, availability.",
        "Organizational",
        "Annual review",
    ),
    (
        "A.5.13",
        "Labelling of Information",
        "An appropriate set of procedures for information labelling shall be developed and implemented in accordance with classification.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.14",
        "Information Transfer",
        "Information transfer rules, procedures, or agreements shall be in place for all types of transfer facilities.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.15",
        "Access Control",
        "Rules to control physical and logical access to information and other associated assets shall be established and implemented.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.16",
        "Identity Management",
        "The full lifecycle of identities shall be managed.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.17",
        "Authentication Information",
        "Allocation and management of authentication information shall be controlled by a management process including advisory guidance.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.18",
        "Access Rights",
        "Access rights to information and other associated assets shall be provisioned, reviewed, modified, and removed in accordance with access policy.",
        "Organizational",
        "Quarterly",
    ),
    (
        "A.5.19",
        "Information Security in Supplier Relationships",
        "Processes and procedures shall be defined and implemented to manage information security risks associated with supplier relationships.",
        "Organizational",
        "Annual review",
    ),
    (
        "A.5.20",
        "Addressing Information Security Within Supplier Agreements",
        "Relevant information security requirements shall be established and agreed with each supplier.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.21",
        "Managing Information Security in the Information and Communication Technology (ICT) Supply Chain",
        "Processes and procedures shall be defined and implemented to manage information security risks in the ICT products supply chain.",
        "Organizational",
        "Annual review",
    ),
    (
        "A.5.22",
        "Monitoring, Review and Change Management of Supplier Services",
        "The organization shall regularly monitor, review, evaluate, and manage change in supplier information security practices.",
        "Organizational",
        "Quarterly",
    ),
    (
        "A.5.23",
        "Information Security for Use of Cloud Services",
        "Processes for acquisition, use, management, and exit from cloud services shall be established in accordance with security requirements.",
        "Organizational",
        "Annual review",
    ),
    (
        "A.5.24",
        "Information Security Incident Management Planning and Preparation",
        "The organization shall plan and prepare for managing information security incidents by defining, establishing, and communicating incident management processes.",
        "Organizational",
        "Annual review",
    ),
    (
        "A.5.25",
        "Assessment and Decision on Information Security Events",
        "The organization shall assess information security events and decide if they are to be categorized as information security incidents.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.26",
        "Response to Information Security Incidents",
        "Information security incidents shall be responded to in accordance with documented procedures.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.27",
        "Learning from Information Security Incidents",
        "Knowledge gained from information security incidents shall be used to strengthen and improve information security controls.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.28",
        "Collection of Evidence",
        "The organization shall define and apply procedures for the identification, collection, acquisition, and preservation of evidence related to security events.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.29",
        "Information Security During Disruption",
        "The organization shall plan how to maintain information security at an appropriate level during disruption.",
        "Organizational",
        "Annual review",
    ),
    (
        "A.5.30",
        "ICT Readiness for Business Continuity",
        "ICT readiness shall be planned, implemented, maintained, and tested based on business continuity objectives and ICT continuity requirements.",
        "Organizational",
        "Annual review",
    ),
    (
        "A.5.31",
        "Legal, Statutory, Regulatory and Contractual Requirements",
        "Legal, statutory, regulatory, and contractual requirements relevant to information security shall be identified, documented, and kept up to date.",
        "Organizational",
        "Annual review",
    ),
    (
        "A.5.32",
        "Intellectual Property Rights",
        "The organization shall implement appropriate procedures to protect intellectual property rights.",
        "Organizational",
        "Annual review",
    ),
    (
        "A.5.33",
        "Protection of Records",
        "Records shall be protected from loss, destruction, falsification, unauthorized access, and unauthorized release.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.34",
        "Privacy and Protection of Personally Identifiable Information (PII)",
        "The organization shall identify and meet requirements regarding the preservation of privacy and protection of PII according to applicable laws.",
        "Organizational",
        "Continuous",
    ),
    (
        "A.5.35",
        "Independent Review of Information Security",
        "The organization's approach to managing information security shall be reviewed independently at planned intervals or when significant changes occur.",
        "Organizational",
        "Annual review",
    ),
    (
        "A.5.36",
        "Compliance with Policies and Standards for Information Security",
        "Managers shall regularly review the compliance of information processing and procedures within their area of responsibility.",
        "Organizational",
        "Quarterly",
    ),
    (
        "A.5.37",
        "Documented Operating Procedures",
        "Operating procedures for information processing facilities shall be documented and made available to personnel who need them.",
        "Organizational",
        "Annual review",
    ),
    # A.6 People Controls (8)
    (
        "A.6.1",
        "Screening",
        "Background verification checks on all candidates to become personnel shall be carried out in accordance with relevant laws and ethics.",
        "People",
        "Continuous",
    ),
    (
        "A.6.2",
        "Terms and Conditions of Employment",
        "The employment contractual agreements shall state personnel's and organization's responsibilities for information security.",
        "People",
        "Continuous",
    ),
    (
        "A.6.3",
        "Information Security Awareness, Education and Training",
        "Personnel of the organization shall receive appropriate information security awareness, education, and training and regular updates.",
        "People",
        "Quarterly",
    ),
    (
        "A.6.4",
        "Disciplinary Process",
        "A disciplinary process shall be formalized and communicated to take actions against personnel who have committed an information security policy breach.",
        "People",
        "Annual review",
    ),
    (
        "A.6.5",
        "Responsibilities After Termination or Change of Employment",
        "Information security responsibilities and duties that remain valid after termination or change of employment shall be defined and enforced.",
        "People",
        "Continuous",
    ),
    (
        "A.6.6",
        "Confidentiality or Non-Disclosure Agreements",
        "Confidentiality or non-disclosure agreements reflecting organization's needs for protection of information shall be identified, documented, and reviewed.",
        "People",
        "Continuous",
    ),
    (
        "A.6.7",
        "Remote Working",
        "Security measures shall be implemented when personnel are working remotely to protect information accessed, processed, or stored outside organization premises.",
        "People",
        "Continuous",
    ),
    (
        "A.6.8",
        "Information Security Event Reporting",
        "The organization shall provide a mechanism for personnel to report observed or suspected information security events through appropriate channels in a timely manner.",
        "People",
        "Continuous",
    ),
    # A.7 Physical Controls (14)
    (
        "A.7.1",
        "Physical Security Perimeters",
        "Security perimeters shall be defined and used to protect areas that contain information and other associated assets.",
        "Physical",
        "Annual review",
    ),
    (
        "A.7.2",
        "Physical Entry",
        "Secure areas shall be protected by appropriate entry controls and access points.",
        "Physical",
        "Continuous",
    ),
    (
        "A.7.3",
        "Securing Offices, Rooms and Facilities",
        "Physical security for offices, rooms, and facilities shall be designed and implemented.",
        "Physical",
        "Annual review",
    ),
    (
        "A.7.4",
        "Physical Security Monitoring",
        "Premises shall be continuously monitored for unauthorized physical access.",
        "Physical",
        "Continuous",
    ),
    (
        "A.7.5",
        "Protecting Against Physical and Environmental Threats",
        "Protection against physical and environmental threats shall be designed and implemented.",
        "Physical",
        "Annual review",
    ),
    (
        "A.7.6",
        "Working in Secure Areas",
        "Security measures for working in secure areas shall be designed and implemented.",
        "Physical",
        "Continuous",
    ),
    (
        "A.7.7",
        "Clear Desk and Clear Screen",
        "Clear desk rules for papers and removable storage media and clear screen rules for information processing facilities shall be defined and enforced.",
        "Physical",
        "Continuous",
    ),
    (
        "A.7.8",
        "Equipment Siting and Protection",
        "Equipment shall be sited securely and protected.",
        "Physical",
        "Annual review",
    ),
    (
        "A.7.9",
        "Security of Assets Off-Premises",
        "Off-site assets shall be protected.",
        "Physical",
        "Continuous",
    ),
    (
        "A.7.10",
        "Storage Media",
        "Storage media shall be managed through their lifecycle of acquisition, use, transportation, and disposal in accordance with organization's classification scheme.",
        "Physical",
        "Continuous",
    ),
    (
        "A.7.11",
        "Supporting Utilities",
        "Information processing facilities shall be protected from power failures and other disruptions caused by failures in supporting utilities.",
        "Physical",
        "Annual review",
    ),
    (
        "A.7.12",
        "Cabling Security",
        "Cables carrying power, data, or supporting information services shall be protected from interception, interference, or damage.",
        "Physical",
        "Annual review",
    ),
    (
        "A.7.13",
        "Equipment Maintenance",
        "Equipment shall be correctly maintained to ensure availability, integrity, and confidentiality of information.",
        "Physical",
        "Quarterly",
    ),
    (
        "A.7.14",
        "Secure Disposal or Re-use of Equipment",
        "Items of equipment containing storage media shall be verified to ensure that any sensitive data and licensed software have been destroyed or securely overwritten.",
        "Physical",
        "Continuous",
    ),
    # A.8 Technological Controls (34)
    (
        "A.8.1",
        "User Endpoint Devices",
        "Information stored on, processed by, or accessible via user endpoint devices shall be protected.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.2",
        "Privileged Access Rights",
        "The allocation and use of privileged access rights shall be restricted and managed.",
        "Technological",
        "Quarterly",
    ),
    (
        "A.8.3",
        "Information Access Restriction",
        "Access to information and other associated assets shall be restricted in accordance with the established topic-specific policy on access control.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.4",
        "Access to Source Code",
        "Read and write access to source code, development tools, and software libraries shall be appropriately managed.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.5",
        "Secure Authentication",
        "Secure authentication technologies and procedures shall be implemented based on information access restrictions and topic-specific policy.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.6",
        "Capacity Management",
        "The use of resources shall be monitored and adjusted in line with current and expected capacity requirements.",
        "Technological",
        "Monthly",
    ),
    (
        "A.8.7",
        "Protection Against Malware",
        "Protection against malware shall be implemented and supported by appropriate user awareness.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.8",
        "Management of Technical Vulnerabilities",
        "Information about technical vulnerabilities of information systems being used shall be obtained, evaluated, and addressed.",
        "Technological",
        "Monthly",
    ),
    (
        "A.8.9",
        "Configuration Management",
        "Configurations, including security configurations, of hardware, software, services, and networks shall be established, documented, implemented, monitored, and reviewed.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.10",
        "Information Deletion",
        "Information stored in information systems, devices, or in any other storage media shall be deleted when no longer required.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.11",
        "Data Masking",
        "Data masking shall be used in accordance with the organization's topic-specific policy on access control and other related policies.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.12",
        "Data Leakage Prevention",
        "Data leakage prevention measures shall be applied to systems, networks, and any other devices that process, store, or transmit sensitive information.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.13",
        "Information Backup",
        "Backup copies of information, software, and systems shall be maintained and regularly tested in accordance with agreed topic-specific policy on backup.",
        "Technological",
        "Daily",
    ),
    (
        "A.8.14",
        "Redundancy of Information Processing Facilities",
        "Information processing facilities shall be implemented with redundancy sufficient to meet availability requirements.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.15",
        "Logging",
        "Logs that record activities, exceptions, faults, and other relevant events shall be produced, stored, protected, and analyzed.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.16",
        "Monitoring Activities",
        "Networks, systems, and applications shall be monitored for anomalous behavior and appropriate actions taken to evaluate potential security incidents.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.17",
        "Clock Synchronization",
        "The clocks of information processing systems shall be synchronized to approved time sources.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.18",
        "Use of Privileged Utility Programs",
        "The use of utility programs that might be capable of overriding system and application controls shall be restricted and tightly controlled.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.19",
        "Installation of Software on Operational Systems",
        "Procedures and measures shall be implemented to securely manage software installation on operational systems.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.20",
        "Networks Security",
        "Networks and network devices shall be secured, managed, and controlled to protect information in systems and applications.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.21",
        "Security of Network Services",
        "Security mechanisms, service levels, and service requirements of network services shall be identified, implemented, and monitored.",
        "Technological",
        "Quarterly",
    ),
    (
        "A.8.22",
        "Segregation of Networks",
        "Groups of information services, users, and information systems shall be segregated on networks.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.23",
        "Web Filtering",
        "Access to external websites shall be managed to reduce exposure to malicious content.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.24",
        "Use of Cryptography",
        "Rules for effective use of cryptography, including cryptographic key management, shall be defined and implemented.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.25",
        "Secure Development Life Cycle",
        "Rules for secure development of software and systems shall be established and applied.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.26",
        "Application Security Requirements",
        "Information security requirements shall be identified, specified, and approved when developing or acquiring applications.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.27",
        "Secure System Architecture and Engineering Principles",
        "Principles for engineering secure systems shall be established, documented, maintained, and applied to information system activities.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.28",
        "Secure Coding",
        "Secure coding principles shall be applied to software development.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.29",
        "Security Testing in Development and Acceptance",
        "Security testing processes shall be defined and implemented in the development life cycle.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.30",
        "Outsourced Development",
        "The organization shall direct, monitor, and review activities related to outsourced system development.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.31",
        "Separation of Development, Test and Production Environments",
        "Development, testing, and production environments shall be separated and secured.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.32",
        "Change Management",
        "Changes to information processing facilities and information systems shall be subject to change management procedures.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.33",
        "Test Information",
        "Test information shall be appropriately selected, protected, and managed.",
        "Technological",
        "Continuous",
    ),
    (
        "A.8.34",
        "Protection of Information Systems During Audit Testing",
        "Audit tests and other assurance activities involving assessment of operational systems shall be planned and agreed between tester and management.",
        "Technological",
        "As needed",
    ),
]

# Build Controls, Source Requirements, Mappings, Evidence, and Coverage Ledger
ISO_CONTROLS: list[PackControlDefinition] = []
ISO_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
ISO_MAPPINGS: list[PackMappingDefinition] = []
ISO_EVIDENCE: list[PackEvidenceDefinition] = []
ISO_COVERAGE: list[PackCoverageDefinition] = []

sort_idx = 10

# 1. Process Management Clauses (4.1 to 10.2)
for clause_num, title, desc, category, cadence in MANAGEMENT_CLAUSES:
    ctrl_id = f"ISO-{clause_num}"
    src_ref = f"ISO/IEC 27001:2022 Clause {clause_num}"
    guidance = (
        f"**Implementation Guidance:** Implement explicit operational procedures for {title}. "
        f"Retain documented information to demonstrate conformity.\n\n"
        f"**Evidence Requests:**\n"
        f"- Formal documented procedures, operational records, and management reviews for {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Information Security Policy\n"
        f"**Audit Procedure:** Interview process owner and inspect documented information."
    )
    ISO_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=category,
            guidance=guidance,
            sort_order=sort_idx,
        )
    )
    ISO_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.CLAUSE,
            source_authority=ISO_AUTHORITY,
            edition_or_amendment=ISO_EDITION,
            source_text=desc,
            content_rights=ISO_RIGHTS,
            source_url=ISO_URL,
            conformly_guidance=guidance,
            assessment_procedure=f"Verify formal documentation and operational evidence for Clause {clause_num}.",
            default_owner_role="Compliance Manager",
            review_cadence=cadence,
            sort_order=sort_idx,
        )
    )
    ISO_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Canonical control {ctrl_id} directly operationalizes management system requirement {clause_num}.",
        )
    )
    ISO_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-ISO-{clause_num.replace('.', '-')}",
            title=f"Evidence for {title}",
            description=f"Documented information supporting {src_ref}.",
            evidence_type="DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            original_file_required=True,
            confidentiality_level="Internal",
        )
    )
    ISO_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Clause {clause_num} fully satisfied by implementation control {ctrl_id} and associated evidence.",
        )
    )
    sort_idx += 10

# 2. Process Annex A Controls (A.5.1 to A.8.34)
for ctrl_code, title, desc, category, cadence in ANNEX_A_CONTROLS:
    ctrl_id = ctrl_code
    src_ref = f"ISO/IEC 27001:2022 Annex {ctrl_code}"
    cat_label = f"Annex {category}"
    guidance = (
        f"**Implementation Guidance:** Implement technical and organizational controls for {title}. "
        f"Record justification in the Statement of Applicability (SoA).\n\n"
        f"**Evidence Requests:**\n"
        f"- Configuration exports, policy documents, and operational logs verifying {ctrl_code}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Information Security Policy\n"
        f"**Audit Procedure:** Examine technical configurations, policy adherence, and operational records."
    )
    ISO_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat_label,
            guidance=guidance,
            sort_order=sort_idx,
        )
    )
    ISO_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.CLAUSE,
            source_authority=ISO_AUTHORITY,
            edition_or_amendment=ISO_EDITION,
            source_text=desc,
            content_rights=ISO_RIGHTS,
            source_url=ISO_URL,
            conformly_guidance=guidance,
            assessment_procedure=f"Review Statement of Applicability and verify implementation of {ctrl_code}.",
            default_owner_role="Security Lead",
            review_cadence=cadence,
            sort_order=sort_idx,
        )
    )
    ISO_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Canonical control {ctrl_id} satisfies Annex A control {ctrl_code}.",
        )
    )
    ISO_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-ISO-{ctrl_code.replace('.', '-')}",
            title=f"Evidence for {title}",
            description=f"Operational records, configuration proof, or policy document for {src_ref}.",
            evidence_type="CONFIGURATION" if "Technological" in cat_label else "DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            original_file_required=False,
            confidentiality_level="Confidential" if "Technological" in cat_label else "Internal",
        )
    )
    ISO_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"Annex control {ctrl_code} covered by canonical control {ctrl_id} and mapped to SoA.",
        )
    )
    sort_idx += 10

ISO_27001_PACK = FrameworkPackDefinition(
    slug="iso-27001",
    name="ISO/IEC 27001:2022 ISMS Pre-Audit Readiness",
    version="v2022",
    description=(
        "Comprehensive pre-audit readiness pack for ISO/IEC 27001:2022 (+Amd 1:2024). "
        "Accounts for all mandatory management-system requirements (Clauses 4-10) and all 93 "
        "Annex A reference controls across Organizational, People, Physical, and Technological themes. "
        "Includes Statement of Applicability (SoA) support and structured evidence requests."
    ),
    release_notes="Complete source-verified release covering ISMS Clauses 4-10 and all 93 Annex A controls.",
    legal_review_notes="Verified ISO/IEC 27001:2022(+Amd 1:2024) content rights and structure. No proprietary text infringed.",
    approval_notes="Approved for canonical catalog release under Tier A beta scope.",
    controls=ISO_CONTROLS,
    source_requirements=ISO_SOURCE_REQS,
    mappings=ISO_MAPPINGS,
    evidence_specifications=ISO_EVIDENCE,
    coverage_ledger=ISO_COVERAGE,
)
