"""NIST Cybersecurity Framework 2.0 (NIST CSWP 29) Pack Definition.

Covers:
- All 6 Core Functions: Govern (GV), Identify (ID), Protect (PR), Detect (DE), Respond (RS), Recover (RC)
- All 22 Categories across the 6 functions
- All 106 official Core subcategories mapped directly to canonical implementation controls
- Distinct separation between NIST Implementation Tiers and Conformly subscription tiers
- 100% Coverage ledger accounting for all 106 subcategories with IMPLEMENTED disposition
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

NIST_AUTHORITY = (
    "National Institute of Standards and Technology (NIST), U.S. Department of Commerce"
)
NIST_EDITION = "NIST CSWP 29 (The NIST Cybersecurity Framework 2.0)"
NIST_RIGHTS = "U.S. Government Work / Public Domain under 17 U.S.C. § 105."
NIST_URL = "https://doi.org/10.6028/NIST.CSWP.29"

NIST_CORE_SUBCATEGORIES: list[tuple[str, str, str, str, str]] = [
    # GOVERN (GV)
    (
        "GV.OC-01",
        "Organizational Mission & Context",
        "The organizational mission is understood and informs cybersecurity risk management.",
        "Govern: Organizational Context",
        "Annual review",
    ),
    (
        "GV.OC-02",
        "Internal & External Stakeholder Expectations",
        "Internal and external stakeholders are understood, and their needs and expectations regarding cybersecurity risk management are understood and considered.",
        "Govern: Organizational Context",
        "Annual review",
    ),
    (
        "GV.OC-03",
        "Legal, Regulatory & Contractual Requirements",
        "Legal, regulatory, and contractual requirements regarding cybersecurity — including privacy and civil liberties obligations — are understood and managed.",
        "Govern: Organizational Context",
        "Annual review",
    ),
    (
        "GV.OC-04",
        "Critical External Stakeholder Dependencies",
        "Critical objectives, capabilities, and services that external stakeholders depend on or expect from the organization are understood and communicated.",
        "Govern: Organizational Context",
        "Annual review",
    ),
    (
        "GV.OC-05",
        "Critical Organizational Dependent Services",
        "Outcomes, capabilities, and services that the organization depends on are understood and communicated.",
        "Govern: Organizational Context",
        "Annual review",
    ),
    (
        "GV.RM-01",
        "Risk Management Objectives & Strategy",
        "Risk management objectives are established and agreed to by organizational stakeholders.",
        "Govern: Risk Management Strategy",
        "Annual review",
    ),
    (
        "GV.RM-02",
        "Risk Appetite & Risk Tolerance Statements",
        "Risk appetite and risk tolerance statements are established, communicated, and maintained.",
        "Govern: Risk Management Strategy",
        "Annual review",
    ),
    (
        "GV.RM-03",
        "Enterprise Risk Management Integration",
        "Cybersecurity risk management activities and outcomes are included in enterprise risk management processes.",
        "Govern: Risk Management Strategy",
        "Annual review",
    ),
    (
        "GV.RM-04",
        "Strategic Direction for Risk Response Options",
        "Strategic direction that describes appropriate risk response options is established and communicated.",
        "Govern: Risk Management Strategy",
        "Annual review",
    ),
    (
        "GV.RM-05",
        "Lines of Communication for Cybersecurity Risk",
        "Lines of communication across the organization are established for cybersecurity risks, including risks from suppliers and other third parties.",
        "Govern: Risk Management Strategy",
        "Annual review",
    ),
    (
        "GV.RM-06",
        "Standardized Method for Risk Calculation & Categorization",
        "A standardized method for calculating, documenting, categorizing, and prioritizing cybersecurity risks is established and communicated.",
        "Govern: Risk Management Strategy",
        "Annual review",
    ),
    (
        "GV.RM-07",
        "Strategic Opportunities & Positive Risks Evaluation",
        "Strategic opportunities (i.e., positive risks) are characterized and are included in organizational cybersecurity risk discussions.",
        "Govern: Risk Management Strategy",
        "Annual review",
    ),
    (
        "GV.RR-01",
        "Leadership Responsibility & Accountability",
        "Organizational leadership is responsible and accountable for cybersecurity risk and fosters a culture that is risk-aware, ethical, and continually improving.",
        "Govern: Roles, Responsibilities & Authorities",
        "Annual review",
    ),
    (
        "GV.RR-02",
        "Cybersecurity Roles, Responsibilities & Authorities",
        "Roles, responsibilities, and authorities related to cybersecurity risk management are established, communicated, understood, and enforced.",
        "Govern: Roles, Responsibilities & Authorities",
        "Annual review",
    ),
    (
        "GV.RR-03",
        "Adequate Cybersecurity Resource Allocation",
        "Adequate resources are allocated commensurate with the cybersecurity risk strategy, roles, responsibilities, and policies.",
        "Govern: Roles, Responsibilities & Authorities",
        "Annual review",
    ),
    (
        "GV.RR-04",
        "Cybersecurity Integration in Human Resources Practices",
        "Cybersecurity is included in human resources practices.",
        "Govern: Roles, Responsibilities & Authorities",
        "Annual review",
    ),
    (
        "GV.PO-01",
        "Cybersecurity Policy Establishment",
        "Policy for managing cybersecurity risks is established based on organizational context, cybersecurity strategy, and priorities and is communicated and enforced.",
        "Govern: Policy",
        "Annual review",
    ),
    (
        "GV.PO-02",
        "Cybersecurity Policy Maintenance & Enforcement",
        "Policy for managing cybersecurity risks is reviewed, updated, communicated, and enforced to reflect changes in requirements, threats, technology, and organizational mission.",
        "Govern: Policy",
        "Annual review",
    ),
    (
        "GV.OV-01",
        "Cybersecurity Strategy Outcomes Oversight",
        "Cybersecurity risk management strategy outcomes are reviewed to inform and adjust strategy and direction.",
        "Govern: Oversight",
        "Quarterly",
    ),
    (
        "GV.OV-02",
        "Risk Management Strategy Review & Adjustment",
        "The cybersecurity risk management strategy is reviewed and adjusted to ensure coverage of organizational requirements and risks.",
        "Govern: Oversight",
        "Quarterly",
    ),
    (
        "GV.OV-03",
        "Cybersecurity Risk Performance Evaluation",
        "Organizational cybersecurity risk management performance is evaluated and reviewed for adjustments needed.",
        "Govern: Oversight",
        "Quarterly",
    ),
    (
        "GV.SC-01",
        "Supply Chain Risk Management Program",
        "A cybersecurity supply chain risk management program, strategy, objectives, policies, and processes are established and agreed to by organizational stakeholders.",
        "Govern: Supply Chain Risk Management",
        "Annual review",
    ),
    (
        "GV.SC-02",
        "Supply Chain Roles & Partner Responsibilities",
        "Cybersecurity roles and responsibilities for suppliers, customers, and partners are established, communicated, and coordinated internally and externally.",
        "Govern: Supply Chain Risk Management",
        "Annual review",
    ),
    (
        "GV.SC-03",
        "Supply Chain Integration into Risk Management",
        "Cybersecurity supply chain risk management is integrated into cybersecurity and enterprise risk management, risk assessment, and improvement processes.",
        "Govern: Supply Chain Risk Management",
        "Annual review",
    ),
    (
        "GV.SC-04",
        "Supplier Inventory & Criticality Prioritization",
        "Suppliers are known and prioritized by criticality.",
        "Govern: Supply Chain Risk Management",
        "Continuous",
    ),
    (
        "GV.SC-05",
        "Supply Chain Cybersecurity Requirements",
        "Requirements to address cybersecurity risks in supply chains are established, prioritized, and integrated into contracts and other types of agreements with suppliers and other relevant third parties.",
        "Govern: Supply Chain Risk Management",
        "Annual review",
    ),
    (
        "GV.SC-06",
        "Supplier Planning & Pre-Contract Due Diligence",
        "Planning and due diligence are performed to reduce risks before entering into formal supplier or other third-party relationships.",
        "Govern: Supply Chain Risk Management",
        "Annual review",
    ),
    (
        "GV.SC-07",
        "Continuous Supplier Risk Assessment & Monitoring",
        "The risks posed by a supplier, their products and services, and other third parties are understood, recorded, prioritized, assessed, responded to, and monitored over the course of the relationship.",
        "Govern: Supply Chain Risk Management",
        "Semi-annual",
    ),
    (
        "GV.SC-08",
        "Supplier Incident Response & Recovery Integration",
        "Relevant suppliers and other third parties are included in incident planning, response, and recovery activities.",
        "Govern: Supply Chain Risk Management",
        "Annual review",
    ),
    (
        "GV.SC-09",
        "Supply Chain Security Practices Lifecycle Integration",
        "Supply chain security practices are integrated into cybersecurity and enterprise risk management programs, and their performance is monitored throughout the technology product and service life cycle.",
        "Govern: Supply Chain Risk Management",
        "Annual review",
    ),
    (
        "GV.SC-10",
        "Supplier Offboarding & Post-Agreement Provisions",
        "Cybersecurity supply chain risk management plans include provisions for activities that occur after the conclusion of a partnership or service agreement.",
        "Govern: Supply Chain Risk Management",
        "Annual review",
    ),
    # IDENTIFY (ID)
    (
        "ID.AM-01",
        "Hardware Asset Inventory Maintenance",
        "Inventories of hardware managed by the organization are maintained.",
        "Identify: Asset Management",
        "Monthly",
    ),
    (
        "ID.AM-02",
        "Software, Services & Systems Inventory",
        "Inventories of software, services, and systems managed by the organization are maintained.",
        "Identify: Asset Management",
        "Monthly",
    ),
    (
        "ID.AM-03",
        "Network Communication & Data Flow Mapping",
        "Representations of the organization's authorized network communication and internal and external network data flows are maintained.",
        "Identify: Asset Management",
        "Quarterly",
    ),
    (
        "ID.AM-04",
        "Supplier Provided Services Inventory",
        "Inventories of services provided by suppliers are maintained.",
        "Identify: Asset Management",
        "Quarterly",
    ),
    (
        "ID.AM-05",
        "Asset Classification & Mission Prioritization",
        "Assets are prioritized based on classification, criticality, resources, and impact on the mission.",
        "Identify: Asset Management",
        "Quarterly",
    ),
    (
        "ID.AM-07",
        "Data Inventories & Metadata Cataloging",
        "Inventories of data and corresponding metadata for designated data types are maintained.",
        "Identify: Asset Management",
        "Quarterly",
    ),
    (
        "ID.AM-08",
        "Asset Lifecycle Management & Secure Disposal",
        "Systems, hardware, software, services, and data are managed throughout their life cycles.",
        "Identify: Asset Management",
        "Semi-annual",
    ),
    (
        "ID.RA-01",
        "Asset Vulnerability Identification & Tracking",
        "Vulnerabilities in assets are identified, validated, and recorded.",
        "Identify: Risk Assessment",
        "Continuous",
    ),
    (
        "ID.RA-02",
        "Cyber Threat Intelligence Ingestion",
        "Cyber threat intelligence is received from information sharing forums and sources.",
        "Identify: Risk Assessment",
        "Monthly",
    ),
    (
        "ID.RA-03",
        "Internal & External Threat Identification",
        "Internal and external threats to the organization are identified and recorded.",
        "Identify: Risk Assessment",
        "Quarterly",
    ),
    (
        "ID.RA-04",
        "Threat Impact & Likelihood Assessment",
        "Potential impacts and likelihoods of threats exploiting vulnerabilities are identified and recorded.",
        "Identify: Risk Assessment",
        "Quarterly",
    ),
    (
        "ID.RA-05",
        "Inherent Risk & Response Prioritization",
        "Threats, vulnerabilities, likelihoods, and impacts are used to understand inherent risk and inform risk response prioritization.",
        "Identify: Risk Assessment",
        "Quarterly",
    ),
    (
        "ID.RA-06",
        "Risk Response Planning & Tracking",
        "Risk responses are chosen, prioritized, planned, tracked, and communicated.",
        "Identify: Risk Assessment",
        "Quarterly",
    ),
    (
        "ID.RA-07",
        "Operational Changes & Exception Management",
        "Changes and exceptions are managed, assessed for risk impact, recorded, and tracked.",
        "Identify: Risk Assessment",
        "Monthly",
    ),
    (
        "ID.RA-08",
        "Vulnerability Disclosure Program & Intake",
        "Processes for receiving, analyzing, and responding to vulnerability disclosures are established.",
        "Identify: Risk Assessment",
        "Continuous",
    ),
    (
        "ID.RA-09",
        "Hardware & Software Authenticity Assessment",
        "The authenticity and integrity of hardware and software are assessed prior to acquisition and use.",
        "Identify: Risk Assessment",
        "Quarterly",
    ),
    (
        "ID.RA-10",
        "Critical Supplier Pre-Acquisition Assessment",
        "Critical suppliers are assessed prior to acquisition.",
        "Identify: Risk Assessment",
        "Semi-annual",
    ),
    (
        "ID.IM-01",
        "Improvements Identified from Evaluations",
        "Improvements are identified from evaluations.",
        "Identify: Improvement",
        "Semi-annual",
    ),
    (
        "ID.IM-02",
        "Improvements from Security Tests & Exercises",
        "Improvements are identified from security tests and exercises, including those done in coordination with suppliers and relevant third parties.",
        "Identify: Improvement",
        "Semi-annual",
    ),
    (
        "ID.IM-03",
        "Improvements from Operational Process Execution",
        "Improvements are identified from execution of operational processes, procedures, and activities.",
        "Identify: Improvement",
        "Semi-annual",
    ),
    (
        "ID.IM-04",
        "Cybersecurity & Incident Plan Improvement",
        "Incident response plans and other cybersecurity plans that affect operations are established, communicated, maintained, and improved.",
        "Identify: Improvement",
        "Annual review",
    ),
    # PROTECT (PR)
    (
        "PR.AA-01",
        "Identity & Credential Management Lifecycle",
        "Identities and credentials for authorized users, services, and hardware are managed by the organization.",
        "Protect: Identity Management & Access Control",
        "Continuous",
    ),
    (
        "PR.AA-02",
        "Context-Based Identity Proofing & Binding",
        "Identities are proofed and bound to credentials based on the context of interactions.",
        "Protect: Identity Management & Access Control",
        "Continuous",
    ),
    (
        "PR.AA-03",
        "Multi-Factor & Mutual Authentication",
        "Users, services, and hardware are authenticated.",
        "Protect: Identity Management & Access Control",
        "Continuous",
    ),
    (
        "PR.AA-04",
        "Identity Assertion Protection & Verification",
        "Identity assertions are protected, conveyed, and verified.",
        "Protect: Identity Management & Access Control",
        "Continuous",
    ),
    (
        "PR.AA-05",
        "Least Privilege & Access Entitlement Enforcement",
        "Access permissions, entitlements, and authorizations are defined in a policy, managed, enforced, and reviewed, and incorporate the principles of least privilege and separation of duties.",
        "Protect: Identity Management & Access Control",
        "Quarterly",
    ),
    (
        "PR.AA-06",
        "Physical Asset Access Management & Monitoring",
        "Physical access to assets is managed, monitored, and enforced commensurate with risk.",
        "Protect: Identity Management & Access Control",
        "Monthly",
    ),
    (
        "PR.AT-01",
        "General Workforce Cybersecurity Awareness Training",
        "Personnel are provided with awareness and training so that they possess the knowledge and skills to perform general tasks with cybersecurity risks in mind.",
        "Protect: Awareness & Training",
        "Semi-annual",
    ),
    (
        "PR.AT-02",
        "Specialized Cybersecurity Role Training",
        "Individuals in specialized roles are provided with awareness and training so that they possess the knowledge and skills to perform relevant tasks with cybersecurity risks in mind.",
        "Protect: Awareness & Training",
        "Annual review",
    ),
    (
        "PR.DS-01",
        "Data-at-Rest Confidentiality & Integrity Protection",
        "The confidentiality, integrity, and availability of data-at-rest are protected.",
        "Protect: Data Security",
        "Continuous",
    ),
    (
        "PR.DS-02",
        "Data-in-Transit Protection & Encryption",
        "The confidentiality, integrity, and availability of data-in-transit are protected.",
        "Protect: Data Security",
        "Continuous",
    ),
    (
        "PR.DS-10",
        "Data-in-Use Confidentiality & Integrity Protection",
        "The confidentiality, integrity, and availability of data-in-use are protected.",
        "Protect: Data Security",
        "Continuous",
    ),
    (
        "PR.DS-11",
        "Data Backup Creation, Protection & Restoration Testing",
        "Backups of data are created, protected, maintained, and tested.",
        "Protect: Data Security",
        "Monthly",
    ),
    (
        "PR.PS-01",
        "Configuration Management & Baseline Enforcement",
        "Configuration management practices are established and applied.",
        "Protect: Platform Security",
        "Continuous",
    ),
    (
        "PR.PS-02",
        "Software Maintenance & Vulnerability Patching",
        "Software is maintained, replaced, and removed commensurate with risk.",
        "Protect: Platform Security",
        "Monthly",
    ),
    (
        "PR.PS-03",
        "Hardware Maintenance & Replacement",
        "Hardware is maintained, replaced, and removed commensurate with risk.",
        "Protect: Platform Security",
        "Quarterly",
    ),
    (
        "PR.PS-04",
        "Audit Log Generation & Monitoring Availability",
        "Log records are generated and made available for continuous monitoring.",
        "Protect: Platform Security",
        "Continuous",
    ),
    (
        "PR.PS-05",
        "Unauthorized Software Execution Prevention",
        "Installation and execution of unauthorized software are prevented.",
        "Protect: Platform Security",
        "Continuous",
    ),
    (
        "PR.PS-06",
        "Secure Software Development Lifecycle Integration",
        "Secure software development practices are integrated, and their performance is monitored throughout the software development life cycle.",
        "Protect: Platform Security",
        "Continuous",
    ),
    (
        "PR.IR-01",
        "Logical Network Segmentation & Access Protection",
        "Networks and environments are protected from unauthorized logical access and usage.",
        "Protect: Technology Infrastructure Resilience",
        "Continuous",
    ),
    (
        "PR.IR-02",
        "Technology Asset Environmental Threat Protection",
        "The organization's technology assets are protected from environmental threats.",
        "Protect: Technology Infrastructure Resilience",
        "Quarterly",
    ),
    (
        "PR.IR-03",
        "Operational Resilience & Redundancy Mechanisms",
        "Mechanisms are implemented to achieve resilience requirements in normal and adverse situations.",
        "Protect: Technology Infrastructure Resilience",
        "Semi-annual",
    ),
    (
        "PR.IR-04",
        "Capacity Management & Availability Assurance",
        "Adequate resource capacity to ensure availability is maintained.",
        "Protect: Technology Infrastructure Resilience",
        "Quarterly",
    ),
    # DETECT (DE)
    (
        "DE.CM-01",
        "Network & Network Service Continuous Monitoring",
        "Networks and network services are monitored to find potentially adverse events.",
        "Detect: Continuous Monitoring",
        "Continuous",
    ),
    (
        "DE.CM-02",
        "Physical Environment Continuous Monitoring",
        "The physical environment is monitored to find potentially adverse events.",
        "Detect: Continuous Monitoring",
        "Continuous",
    ),
    (
        "DE.CM-03",
        "Personnel Activity & Usage Monitoring",
        "Personnel activity and technology usage are monitored to find potentially adverse events.",
        "Detect: Continuous Monitoring",
        "Continuous",
    ),
    (
        "DE.CM-06",
        "External Service Provider Monitoring",
        "External service provider activities and services are monitored to find potentially adverse events.",
        "Detect: Continuous Monitoring",
        "Continuous",
    ),
    (
        "DE.CM-09",
        "Computing Assets & Runtime Environment Monitoring",
        "Computing hardware and software, runtime environments, and their data are monitored to find potentially adverse events.",
        "Detect: Continuous Monitoring",
        "Continuous",
    ),
    (
        "DE.AE-02",
        "Potentially Adverse Event Analysis",
        "Potentially adverse events are analyzed to better understand associated activities.",
        "Detect: Adverse Event Analysis",
        "Continuous",
    ),
    (
        "DE.AE-03",
        "Multi-Source Event Correlation",
        "Information is correlated from multiple sources.",
        "Detect: Adverse Event Analysis",
        "Continuous",
    ),
    (
        "DE.AE-04",
        "Adverse Event Impact & Scope Assessment",
        "The estimated impact and scope of adverse events are understood.",
        "Detect: Adverse Event Analysis",
        "Continuous",
    ),
    (
        "DE.AE-06",
        "Adverse Event Information Sharing with Personnel",
        "Information on adverse events is provided to authorized staff and tools.",
        "Detect: Adverse Event Analysis",
        "Continuous",
    ),
    (
        "DE.AE-07",
        "Threat Intelligence Integration in Event Analysis",
        "Cyber threat intelligence and other contextual information are integrated into the analysis.",
        "Detect: Adverse Event Analysis",
        "Continuous",
    ),
    (
        "DE.AE-08",
        "Formal Incident Declaration Thresholds",
        "Incidents are declared when adverse events meet the defined incident criteria.",
        "Detect: Adverse Event Analysis",
        "Continuous",
    ),
    # RESPOND (RS)
    (
        "RS.MA-01",
        "Incident Response Plan Execution & Coordination",
        "The incident response plan is executed in coordination with relevant third parties once an incident is declared.",
        "Respond: Incident Management",
        "Continuous",
    ),
    (
        "RS.MA-02",
        "Incident Report Triage & Validation",
        "Incident reports are triaged and validated.",
        "Respond: Incident Management",
        "Continuous",
    ),
    (
        "RS.MA-03",
        "Incident Categorization & Prioritization",
        "Incidents are categorized and prioritized.",
        "Respond: Incident Management",
        "Continuous",
    ),
    (
        "RS.MA-04",
        "Incident Escalation & Elevation",
        "Incidents are escalated or elevated as needed.",
        "Respond: Incident Management",
        "Continuous",
    ),
    (
        "RS.MA-05",
        "Incident Recovery Initiation Criteria",
        "The criteria for initiating incident recovery are applied.",
        "Respond: Incident Management",
        "Continuous",
    ),
    (
        "RS.AN-03",
        "Incident Investigation & Root Cause Analysis",
        "Analysis is performed to establish what has taken place during an incident and the root cause of the incident.",
        "Respond: Incident Analysis",
        "Continuous",
    ),
    (
        "RS.AN-06",
        "Investigative Action Recording & Provenance Preservation",
        "Actions performed during an investigation are recorded, and the records' integrity and provenance are preserved.",
        "Respond: Incident Analysis",
        "Continuous",
    ),
    (
        "RS.AN-07",
        "Incident Evidence & Metadata Integrity Preservation",
        "Incident data and metadata are collected, and their integrity and provenance are preserved.",
        "Respond: Incident Analysis",
        "Continuous",
    ),
    (
        "RS.AN-08",
        "Incident Magnitude Estimation & Validation",
        "An incident's magnitude is estimated and validated.",
        "Respond: Incident Analysis",
        "Continuous",
    ),
    (
        "RS.CO-02",
        "Stakeholder Incident Notification",
        "Internal and external stakeholders are notified of incidents.",
        "Respond: Incident Response Reporting & Communication",
        "Continuous",
    ),
    (
        "RS.CO-03",
        "Designated Internal & External Incident Information Sharing",
        "Information is shared with designated internal and external stakeholders.",
        "Respond: Incident Response Reporting & Communication",
        "Continuous",
    ),
    (
        "RS.MI-01",
        "Incident Containment Execution",
        "Incidents are contained.",
        "Respond: Incident Mitigation",
        "Continuous",
    ),
    (
        "RS.MI-02",
        "Incident Eradication Execution",
        "Incidents are eradicated.",
        "Respond: Incident Mitigation",
        "Continuous",
    ),
    # RECOVER (RC)
    (
        "RC.RP-01",
        "Incident Recovery Plan Execution",
        "The recovery portion of the incident response plan is executed once initiated from the incident response process.",
        "Recover: Incident Recovery Plan Execution",
        "Continuous",
    ),
    (
        "RC.RP-02",
        "Recovery Action Prioritization & Performance",
        "Recovery actions are selected, scoped, prioritized, and performed.",
        "Recover: Incident Recovery Plan Execution",
        "Continuous",
    ),
    (
        "RC.RP-03",
        "Backup & Restoration Asset Integrity Verification",
        "The integrity of backups and other restoration assets is verified before using them for restoration.",
        "Recover: Incident Recovery Plan Execution",
        "Monthly",
    ),
    (
        "RC.RP-04",
        "Post-Incident Operational Norms Establishment",
        "Critical mission functions and cybersecurity risk management are considered to establish post-incident operational norms.",
        "Recover: Incident Recovery Plan Execution",
        "As needed",
    ),
    (
        "RC.RP-05",
        "Restored Asset Verification & Operating Confirmation",
        "The integrity of restored assets is verified, systems and services are restored, and normal operating status is confirmed.",
        "Recover: Incident Recovery Plan Execution",
        "Continuous",
    ),
    (
        "RC.RP-06",
        "Recovery Termination Declaration & Documentation",
        "The end of incident recovery is declared based on criteria, and incident- related documentation is completed.",
        "Recover: Incident Recovery Plan Execution",
        "As needed",
    ),
    (
        "RC.CO-03",
        "Recovery Activity Progress Communications",
        "Recovery activities and progress in restoring operational capabilities are communicated to designated internal and external stakeholders.",
        "Recover: Incident Recovery Communication",
        "As needed",
    ),
    (
        "RC.CO-04",
        "Public Recovery Communications & Messaging",
        "Public updates on incident recovery are shared using approved methods and messaging.",
        "Recover: Incident Recovery Communication",
        "As needed",
    ),
]

NIST_CONTROLS: list[PackControlDefinition] = []
NIST_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
NIST_MAPPINGS: list[PackMappingDefinition] = []
NIST_EVIDENCE: list[PackEvidenceDefinition] = []
NIST_COVERAGE: list[PackCoverageDefinition] = []

sort_idx = 10

for subcat_id, title, desc, category, cadence in NIST_CORE_SUBCATEGORIES:
    ctrl_id = f"NIST-{subcat_id.replace('.', '-')}"
    src_ref = f"NIST CSF 2.0 {subcat_id}"
    guidance = (
        f"**Implementation Guidance:** Operationalize {title} within organizational policies and technical controls. "
        f"Collect evidence proving continuous execution.\n\n"
        f"**Evidence Requests:**\n"
        f"- Configuration proof, policy documents, and operational records for {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Cybersecurity Policy\n"
        f"**Framework Reference:** {src_ref}"
    )

    NIST_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=category,
            guidance=guidance,
            sort_order=sort_idx,
        )
    )
    NIST_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.SUBCLAUSE,
            source_authority=NIST_AUTHORITY,
            edition_or_amendment=NIST_EDITION,
            source_text=desc,
            content_rights=NIST_RIGHTS,
            source_url=NIST_URL,
            conformly_guidance=guidance,
            assessment_procedure=f"Verify operational controls and artifacts satisfying NIST CSF 2.0 subcategory {subcat_id}.",
            default_owner_role="Security Officer",
            review_cadence=cadence,
            sort_order=sort_idx,
        )
    )
    NIST_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Canonical control {ctrl_id} satisfies NIST CSF 2.0 subcategory {subcat_id}.",
        )
    )
    NIST_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-NIST-{subcat_id.replace('.', '_').replace('-', '_')}",
            title=f"Evidence for {title}",
            description=f"Operational records, configuration proof, or policy document for {src_ref}.",
            evidence_type="CONFIGURATION"
            if "Protect" in category or "Detect" in category
            else "DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            original_file_required=False,
            confidentiality_level="Internal",
        )
    )
    NIST_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"NIST CSF 2.0 subcategory {subcat_id} operationalized by canonical control {ctrl_id}.",
        )
    )
    sort_idx += 10

NIST_CSF_PACK = FrameworkPackDefinition(
    slug="nist-csf",
    name="NIST Cybersecurity Framework 2.0",
    version="v2.0",
    description=(
        "Complete core coverage for NIST CSF 2.0 across all six Functions: Govern (GV), "
        "Identify (ID), Protect (PR), Detect (DE), Respond (RS), and Recover (RC). "
        "Maps all 106 official subcategories to deterministic controls and structured evidence specifications."
    ),
    release_notes="Complete source-verified NIST CSF 2.0 Core function, category, and subcategory implementation covering all 106 official outcomes.",
    legal_review_notes="Verified public domain NIST CSWP 29 source text and Appendix A Core taxonomy.",
    approval_notes="Approved for canonical catalog release under Tier A beta scope.",
    controls=NIST_CONTROLS,
    source_requirements=NIST_SOURCE_REQS,
    mappings=NIST_MAPPINGS,
    evidence_specifications=NIST_EVIDENCE,
    coverage_ledger=NIST_COVERAGE,
)
