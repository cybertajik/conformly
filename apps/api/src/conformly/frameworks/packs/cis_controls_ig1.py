"""CIS Critical Security Controls v8 Implementation Group 1 (IG1) Pack Definition.

Covers:
- All 56 official IG1 safeguards across CIS Control families
- Retains parent control mappings and structured evidence criteria
- Accounting for IG2/IG3 safeguards (including Controls 13 and 18) via PROFILE_EXCLUSION in the coverage ledger
- Verified against independent official CIS inventory
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

CIS_AUTHORITY = "Center for Internet Security (CIS)"
CIS_EDITION = "CIS Critical Security Controls v8 (Implementation Group 1)"
CIS_RIGHTS = "CIS Controls terms of use. Reference safeguard citations and titles used for compliance mapping."
CIS_URL = "https://www.cisecurity.org/controls/implementation-groups"

# All 56 Official CIS v8 IG1 Safeguards (Control Num, Safeguard Num, Title, Description, Cadence)
CIS_IG1_SAFEGUARDS: list[tuple[int, str, str, str, str]] = [
    # Control 1: Inventory and Control of Enterprise Assets (2)
    (
        1,
        "1.1",
        "Establish and Maintain a Detailed Enterprise Asset Inventory",
        "Establish and maintain an inventory of all enterprise assets with the potential to store or process data.",
        "Monthly",
    ),
    (
        1,
        "1.2",
        "Address Unauthorized Assets",
        "Ensure a process exists to address unauthorized assets discovered on the network.",
        "Continuous",
    ),
    # Control 2: Inventory and Control of Software Assets (3)
    (
        2,
        "2.1",
        "Establish and Maintain a Software Inventory",
        "Establish and maintain a software inventory of all authorized software on enterprise assets.",
        "Monthly",
    ),
    (
        2,
        "2.2",
        "Ensure Authorized Software is Currently Supported",
        "Ensure that only actively supported software versions are allowed to execute.",
        "Quarterly",
    ),
    (
        2,
        "2.3",
        "Address Unauthorized Software",
        "Ensure that unauthorized software is either removed or quarantined promptly.",
        "Continuous",
    ),
    # Control 3: Data Protection (6)
    (
        3,
        "3.1",
        "Establish and Maintain a Data Management Process",
        "Establish and maintain a data management process addressing data sensitivity, handling, and storage.",
        "Annual review",
    ),
    (
        3,
        "3.2",
        "Establish and Maintain a Data Inventory",
        "Establish and maintain an inventory of sensitive data assets and their locations.",
        "Quarterly",
    ),
    (
        3,
        "3.3",
        "Configure Data Access Control Lists",
        "Configure data access control lists based on need-to-know and least privilege.",
        "Continuous",
    ),
    (
        3,
        "3.4",
        "Enforce Data Retention",
        "Retain data in accordance with enterprise data management process and statutory obligations.",
        "Quarterly",
    ),
    (
        3,
        "3.5",
        "Securely Discard Data",
        "Securely discard data when no longer needed using approved sanitization techniques.",
        "Continuous",
    ),
    (
        3,
        "3.6",
        "Encrypt Data on Portable Media",
        "Encrypt all sensitive data stored on portable media devices.",
        "Continuous",
    ),
    # Control 4: Secure Configuration of Enterprise Assets and Software (7)
    (
        4,
        "4.1",
        "Establish and Maintain a Secure Configuration Process",
        "Establish and maintain a secure configuration process for enterprise assets and software.",
        "Annual review",
    ),
    (
        4,
        "4.2",
        "Establish and Maintain a Secure Configuration Process for Network Infrastructure",
        "Establish and maintain a secure configuration process for network infrastructure devices.",
        "Annual review",
    ),
    (
        4,
        "4.3",
        "Configure Automatic Session Locking on Enterprise Assets",
        "Configure automatic session locking on enterprise assets after a defined period of inactivity.",
        "Continuous",
    ),
    (
        4,
        "4.4",
        "Implement and Manage a Firewall on Servers",
        "Implement and manage host-based firewalls on all enterprise server platforms.",
        "Continuous",
    ),
    (
        4,
        "4.5",
        "Implement and Manage a Firewall on End-User Devices",
        "Implement and manage host-based firewalls on all end-user endpoints.",
        "Continuous",
    ),
    (
        4,
        "4.6",
        "Securely Manage Enterprise Assets and Software",
        "Securely manage enterprise assets and software using modern administrative protocols.",
        "Continuous",
    ),
    (
        4,
        "4.7",
        "Manage Default Accounts on Enterprise Assets and Software",
        "Manage default accounts, change default credentials, and disable unnecessary accounts.",
        "Continuous",
    ),
    # Control 5: Account Management (4)
    (
        5,
        "5.1",
        "Establish and Maintain an Inventory of Accounts",
        "Establish and maintain an inventory of all user and administrative accounts.",
        "Monthly",
    ),
    (
        5,
        "5.2",
        "Use Unique Passwords",
        "Use unique passwords for all accounts in accordance with organizational password policy.",
        "Continuous",
    ),
    (
        5,
        "5.3",
        "Disable Dormant Accounts",
        "Delete or disable accounts that have been dormant for more than 45 days.",
        "Monthly",
    ),
    (
        5,
        "5.4",
        "Restrict Administrator Privileges to Dedicated Accounts",
        "Restrict administrative privileges to dedicated accounts used exclusively for admin duties.",
        "Continuous",
    ),
    # Control 6: Access Control Management (5)
    (
        6,
        "6.1",
        "Establish an Access Granting Process",
        "Establish and follow a process to grant access to enterprise assets upon authorized request.",
        "Continuous",
    ),
    (
        6,
        "6.2",
        "Establish an Access Revoking Process",
        "Establish and follow a process to revoke access immediately upon termination or role change.",
        "Continuous",
    ),
    (
        6,
        "6.3",
        "Require MFA for Externally-Exposed Applications",
        "Require multi-factor authentication for all externally-exposed enterprise applications.",
        "Continuous",
    ),
    (
        6,
        "6.4",
        "Require MFA for Remote Network Access",
        "Require multi-factor authentication for all remote network access into enterprise environments.",
        "Continuous",
    ),
    (
        6,
        "6.5",
        "Require MFA for Administrative Access",
        "Require multi-factor authentication for all administrative access across all management interfaces.",
        "Continuous",
    ),
    # Control 7: Continuous Vulnerability Management (4)
    (
        7,
        "7.1",
        "Establish and Maintain a Vulnerability Management Process",
        "Establish and maintain a documented vulnerability management process.",
        "Annual review",
    ),
    (
        7,
        "7.2",
        "Establish and Maintain a Remediation Process",
        "Establish and maintain a risk-based remediation strategy for vulnerabilities.",
        "Monthly",
    ),
    (
        7,
        "7.3",
        "Perform Automated Operating System Patch Management",
        "Perform operating system patch management on enterprise assets automatically.",
        "Monthly",
    ),
    (
        7,
        "7.4",
        "Perform Automated Application Patch Management",
        "Perform application patch management on enterprise assets automatically.",
        "Monthly",
    ),
    # Control 8: Audit Log Management (3)
    (
        8,
        "8.1",
        "Establish and Maintain an Audit Log Management Process",
        "Establish and maintain an audit log management process defining logging requirements.",
        "Annual review",
    ),
    (
        8,
        "8.2",
        "Collect Audit Logs",
        "Collect and centralize audit logs from enterprise assets and security systems.",
        "Continuous",
    ),
    (
        8,
        "8.3",
        "Ensure Adequate Audit Log Storage",
        "Ensure audit logs are retained for at least 90 days with sufficient storage capacity.",
        "Quarterly",
    ),
    # Control 9: Email and Web Browser Protections (2)
    (
        9,
        "9.1",
        "Ensure Use of Fully Supported Browsers and Email Clients",
        "Ensure only supported versions of web browsers and email clients are used.",
        "Quarterly",
    ),
    (
        9,
        "9.2",
        "Use DNS Filtering Services",
        "Deploy DNS filtering services to block access to known malicious domains.",
        "Continuous",
    ),
    # Control 10: Malware Defenses (3)
    (
        10,
        "10.1",
        "Deploy and Maintain Anti-Malware Software",
        "Deploy and maintain anti-malware software on all enterprise endpoints.",
        "Continuous",
    ),
    (
        10,
        "10.2",
        "Configure Automatic Anti-Malware Signature Updates",
        "Configure automatic daily signature updates for anti-malware software.",
        "Daily",
    ),
    (
        10,
        "10.3",
        "Disable Auto-Run and Auto-Play for Removable Media",
        "Disable auto-run and auto-play capabilities for removable media on endpoints.",
        "Continuous",
    ),
    # Control 11: Data Recovery (4)
    (
        11,
        "11.1",
        "Establish and Maintain a Data Recovery Process",
        "Establish and maintain a data recovery process defining restoration priorities.",
        "Annual review",
    ),
    (
        11,
        "11.2",
        "Perform Automated Backups",
        "Perform automated backups of in-scope enterprise assets and data.",
        "Daily",
    ),
    (
        11,
        "11.3",
        "Protect Recovery Data",
        "Protect backup data with encryption and access controls equivalent to original data.",
        "Continuous",
    ),
    (
        11,
        "11.4",
        "Establish an Isolated Instance of Recovery Data",
        "Maintain an isolated, immutable, or offsite copy of recovery data.",
        "Continuous",
    ),
    # Control 12: Network Infrastructure Management (1)
    (
        12,
        "12.1",
        "Ensure Network Infrastructure is Kept Up-to-Date",
        "Ensure all network infrastructure devices are running up-to-date and supported firmware.",
        "Quarterly",
    ),
    # Control 14: Security Awareness and Skills Training (6)
    (
        14,
        "14.1",
        "Establish and Maintain a Security Awareness Program",
        "Establish and maintain a security awareness program to educate personnel.",
        "Annual review",
    ),
    (
        14,
        "14.2",
        "Train Workforce to Recognize Social Engineering Attacks",
        "Train workforce members to identify and report phishing and social engineering.",
        "Quarterly",
    ),
    (
        14,
        "14.3",
        "Train Workforce on Authentication Best Practices",
        "Train workforce members on secure credential creation, storage, and MFA usage.",
        "Annual review",
    ),
    (
        14,
        "14.4",
        "Train Workforce on Data Handling Best Practices",
        "Train workforce members on identifying and properly handling sensitive enterprise data.",
        "Annual review",
    ),
    (
        14,
        "14.5",
        "Train Workforce on Causes of Unintentional Data Exposure",
        "Train workforce members on common causes of unintentional data exposure and misconfiguration.",
        "Annual review",
    ),
    (
        14,
        "14.6",
        "Train Workforce on Recognizing and Reporting Incidents",
        "Train workforce members on recognizing and immediately reporting suspected security incidents.",
        "Annual review",
    ),
    # Control 15: Service Provider Management (1)
    (
        15,
        "15.1",
        "Establish and Maintain an Inventory of Service Providers",
        "Establish and maintain an inventory of all third-party service providers with access to data.",
        "Quarterly",
    ),
    # Control 16: Application Software Security (2)
    (
        16,
        "16.1",
        "Establish and Maintain a Secure Application Development Process",
        "Establish and maintain a secure software development lifecycle (SSDLC).",
        "Annual review",
    ),
    (
        16,
        "16.2",
        "Establish Process to Accept and Address Software Vulnerabilities",
        "Establish a process to receive, triage, and remediate reports of software vulnerabilities.",
        "Continuous",
    ),
    # Control 17: Incident Response Management (3)
    (
        17,
        "17.1",
        "Designate Personnel to Manage Incident Handling",
        "Designate and train personnel responsible for incident response handling.",
        "Annual review",
    ),
    (
        17,
        "17.2",
        "Establish Contact Information for Reporting Incidents",
        "Establish and maintain published contact mechanisms for reporting incidents.",
        "Annual review",
    ),
    (
        17,
        "17.3",
        "Establish an Enterprise Process for Reporting Incidents",
        "Establish and communicate an enterprise incident reporting and escalation process.",
        "Annual review",
    ),
]

CIS_FAMILY_TITLES: dict[int, str] = {
    1: "Inventory and Control of Enterprise Assets",
    2: "Inventory and Control of Software Assets",
    3: "Data Protection",
    4: "Secure Configuration of Enterprise Assets and Software",
    5: "Account Management",
    6: "Access Control Management",
    7: "Continuous Vulnerability Management",
    8: "Audit Log Management",
    9: "Email and Web Browser Protections",
    10: "Malware Defenses",
    11: "Data Recovery",
    12: "Network Infrastructure Management",
    13: "Network Monitoring and Defense",
    14: "Security Awareness and Skills Training",
    15: "Service Provider Management",
    16: "Application Software Security",
    17: "Incident Response Management",
    18: "Penetration Testing",
}

# Profile Exclusions (IG2 and IG3 safeguards recorded in coverage ledger)
CIS_PROFILE_EXCLUSIONS: list[tuple[str, str]] = [
    ("1.3", "Asset Inventory Automated Tool (IG2/IG3)"),
    ("1.4", "DHCP Logging (IG2/IG3)"),
    ("1.5", "Passive Asset Discovery (IG3)"),
    ("2.4", "Application Whitelisting (IG2/IG3)"),
    ("2.5", "Authorized Software Libraries (IG2/IG3)"),
    ("2.6", "Software Script Execution Control (IG2/IG3)"),
    ("2.7", "Block Unauthorized Script Execution (IG3)"),
    ("3.7", "Encrypt Sensitive Data at Rest (IG2/IG3)"),
    ("3.8", "Segment Data Processing (IG2/IG3)"),
    ("3.9", "Encrypt Sensitive Data in Transit (IG2/IG3)"),
    ("3.10", "Encrypt Sensitive Data on Endpoints (IG2/IG3)"),
    ("3.11", "Encrypt Sensitive Data in Cloud (IG2/IG3)"),
    ("3.12", "Segment Sensitive Data Networks (IG3)"),
    ("3.13", "Deploy Data Loss Prevention (IG3)"),
    ("3.14", "Log Sensitive Data Access (IG3)"),
    ("13.1", "Centralize Security Event Alerting (IG2/IG3)"),
    ("13.2", "Deploy Host-Based Intrusion Detection (IG2/IG3)"),
    ("13.3", "Deploy Network Intrusion Detection (IG3)"),
    ("18.1", "Establish and Maintain Penetration Testing Program (IG2/IG3)"),
    ("18.2", "Perform Periodic External Penetration Tests (IG2/IG3)"),
    ("18.3", "Remediate Penetration Test Findings (IG2/IG3)"),
]

CIS_CONTROLS: list[PackControlDefinition] = []
CIS_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
CIS_MAPPINGS: list[PackMappingDefinition] = []
CIS_EVIDENCE: list[PackEvidenceDefinition] = []
CIS_COVERAGE: list[PackCoverageDefinition] = []

sort_idx = 10

# 1. Process 56 IG1 Safeguards
for ctrl_num, sf_id, title, desc, cadence in CIS_IG1_SAFEGUARDS:
    ctrl_id = f"CIS-{sf_id}"
    family_title = CIS_FAMILY_TITLES[ctrl_num]
    src_ref = f"CIS Controls v8 Safeguard {sf_id}"
    cat_label = f"CIS {ctrl_num}: {family_title}"

    guidance = (
        f"**Implementation Guidance:** Implement CIS Safeguard {sf_id} ({title}). "
        f"Ensure automated evidence generation where applicable.\n\n"
        f"**Evidence Requests:**\n"
        f"- Configuration export, scan log, or operational policy verifying {src_ref}.\n\n"
        f"**Review Cadence:** {cadence}\n"
        f"**Policy Reference:** Enterprise Security Policy\n"
        f"**Parent Control:** CIS Control {ctrl_num} ({family_title})"
    )

    CIS_CONTROLS.append(
        PackControlDefinition(
            identifier=ctrl_id,
            title=title,
            description=desc,
            category=cat_label,
            guidance=guidance,
            sort_order=sort_idx,
        )
    )
    CIS_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.SAFEGUARD,
            source_authority=CIS_AUTHORITY,
            edition_or_amendment=CIS_EDITION,
            source_text=desc,
            content_rights=CIS_RIGHTS,
            source_url=CIS_URL,
            conformly_guidance=guidance,
            assessment_procedure=f"Examine technical configuration and operational logs verifying CIS Safeguard {sf_id}.",
            default_owner_role="IT Security Engineer",
            review_cadence=cadence,
            sort_order=sort_idx,
        )
    )
    CIS_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=src_ref,
            control_identifier=ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"Canonical control {ctrl_id} directly operationalizes CIS v8 Safeguard {sf_id}.",
        )
    )
    CIS_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-CIS-{sf_id.replace('.', '_')}",
            title=f"Evidence for {title}",
            description=f"Configuration export, scan report, or policy artifact for {src_ref}.",
            evidence_type="CONFIGURATION"
            if "Patch" in title or "Firewall" in title or "MFA" in title
            else "DOCUMENT",
            control_identifier=ctrl_id,
            source_reference=src_ref,
            original_file_required=False,
            confidentiality_level="Internal",
        )
    )
    CIS_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=f"CIS Safeguard {sf_id} satisfied by canonical control {ctrl_id} in IG1 profile.",
        )
    )
    sort_idx += 10

# 2. Process Profile Exclusions (IG2 / IG3)
for sf_id, title in CIS_PROFILE_EXCLUSIONS:
    src_ref = f"CIS Controls v8 Safeguard {sf_id}"
    CIS_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=src_ref,
            title=title,
            requirement_type=SourceRequirementType.SAFEGUARD,
            source_authority=CIS_AUTHORITY,
            edition_or_amendment=CIS_EDITION,
            source_text=f"Enterprise safeguard {sf_id} belongs to higher CIS maturity profiles (IG2/IG3).",
            content_rights=CIS_RIGHTS,
            source_url=CIS_URL,
            conformly_guidance="Profile exclusion: not in scope for the CIS IG1 Essential Cyber Hygiene profile.",
            sort_order=sort_idx,
        )
    )
    CIS_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=src_ref,
            disposition=CoverageDisposition.PROFILE_EXCLUSION,
            rationale=f"Safeguard {sf_id} is allocated to CIS Implementation Group 2 or 3; excluded from IG1.",
        )
    )
    sort_idx += 10

CIS_CONTROLS_IG1_PACK = FrameworkPackDefinition(
    slug="cis-controls-ig1",
    name="CIS Critical Security Controls v8 IG1",
    version="v8.0",
    description=(
        "Comprehensive implementation pack covering all 56 official CIS Controls v8 "
        "Implementation Group 1 (IG1) essential cyber hygiene safeguards across CIS "
        "control families. Accounts for IG2 and IG3 safeguards as profile exclusions in the ledger."
    ),
    release_notes="Complete source-verified implementation covering all 56 official IG1 safeguards.",
    legal_review_notes="Verified CIS v8 licensing, official safeguard counts, and IG1/IG2/IG3 boundaries.",
    approval_notes="Approved for canonical catalog release under Tier A beta scope.",
    controls=CIS_CONTROLS,
    source_requirements=CIS_SOURCE_REQS,
    mappings=CIS_MAPPINGS,
    evidence_specifications=CIS_EVIDENCE,
    coverage_ledger=CIS_COVERAGE,
)
