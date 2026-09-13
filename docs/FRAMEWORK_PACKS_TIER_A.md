# Conformly — Tier A Framework Packs & Content Specifications (Drafts Pending Review)

This document defines the canonical Tier A compliance framework pack specifications for Conformly, detailing their legal provenance, content rights, scope, categories, controls, evidence requirements, and deterministic applicability evaluation rules.

---

## 1. Scope & Framework Catalog Distinction

Conformly operates on a disciplined two-tier framework model:
1. **Tier A Core Framework Packs (Active Scope):** The finite set of five core framework packs (`iso-27001`, `gdpr-bdsg`, `nist-csf`, `cis-controls-ig1`, `mvsp`) that have reached 100% technical implementation, declarative applicability rules, structured evidence generation, and acceptance test coverage (`ENGINEERING_COMPLETE`). Their formal release status is `CONTENT_REVIEW_PENDING` awaiting human legal/compliance review and explicit Product Owner release approval before production customer issuance.
2. **Global Framework Catalog Backlog (Planning):** The broader candidate library documented in [`GLOBAL_FRAMEWORK_CATALOG.md`](file:///c:/Users/AD/Desktop/conformly/docs/GLOBAL_FRAMEWORK_CATALOG.md), covering proposed Tier B (SOC 2, ISO 27701, ISO 22301), Tier C (NIS2, DORA, EU AI Act), and Tier D (FedRAMP, CMMC, HITRUST) which remain an unreleased roadmap backlog.

---

## 2. Content Rights, Licensing & Provenance

Conformly enforces strict content rights compliance:

| Framework Pack | Slug | Version | Owner / Authority | Legal Provenance & License Terms | Conformly Rights Model | Engineering Status | Release Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **ISO/IEC 27001:2022** | `iso-27001` | `2022` | ISO / IEC | Copyrighted standard by ISO/IEC. | **Proprietary Pre-Audit Taxonomy:** Conformly authors its own requirements, control descriptions, implementation guidance, and evidence collection requests aligned with the 2022 clause and Annex A structure. No paywalled or proprietary ISO text is copied verbatim. | `ENGINEERING_COMPLETE` | `CONTENT_REVIEW_PENDING` |
| **EU GDPR & German BDSG** | `gdpr-bdsg` | `2024` | European Parliament, EU Council & German Federal Legislature | Official EU Regulation (EU 2016/679) & Federal Data Protection Act (BDSG n.F.). | **Official Public Domain Works:** Statutory legal enactments under German § 5 Abs. 1 UrhG and EU official journal public access. Free for compliance operations and operational guidance. | `ENGINEERING_COMPLETE` | `CONTENT_REVIEW_PENDING` |
| **NIST CSF 2.0** | `nist-csf` | `2.0` | National Institute of Standards and Technology (US DOC) | Public domain US Federal Government work (17 U.S.C. § 105). | **Public Domain:** NIST Special Publications and Frameworks are freely reusable, adaptable, and distributable without license fees. | `ENGINEERING_COMPLETE` | `CONTENT_REVIEW_PENDING` |
| **CIS Controls v8 IG1** | `cis-controls-ig1` | `8.0` | Center for Internet Security (CIS) | CIS Controls v8 basic cyber hygiene taxonomy. | **Implementation Guidance Fair-Use:** Essential cyber hygiene safeguards provided for operational posture assessment and internal evaluation. | `ENGINEERING_COMPLETE` | `CONTENT_REVIEW_PENDING` |
| **MVSP 2.0** | `mvsp` | `2.0` | Minimum Viable Secure Product Working Group | Creative Commons Attribution 4.0 International (CC BY 4.0). | **Open Standard (CC BY 4.0):** Freely sharable and adaptable with attribution for vendor risk assessment. | `ENGINEERING_COMPLETE` | `CONTENT_REVIEW_PENDING` |

> [!IMPORTANT]
> **Pre-Audit Readiness Disclaimer:**
> Conformly is an operational compliance and pre-audit readiness platform. Conformly framework scores, readiness assessments, and badges verify operational preparedness and evidence completeness against defined criteria. They do **not** represent or substitute for an accredited third-party certification (e.g. ISO/IEC 17021 audit) or formal CPA attestation (AICPA SOC 2). In accordance with Module A rules, no AI may impersonate a reviewer or mark packs `BETA_READY` without genuine human sign-off.

---

## 3. Tier A Framework Pack Catalog

### 1. ISO/IEC 27001:2022 ISMS Pre-Audit Readiness (`iso-27001` v`2022`)
- **Focus:** Information Security Management System (ISMS) context, risk treatment, and operational safeguards.
- **Domains & Categories:**
  - `ISMS Context & Scope`: Clause 4 (Context, Interested Parties, Scope)
  - `Leadership & Governance`: Clause 5 (Policy, Roles, Responsibilities)
  - `Planning & Risk Treatment`: Clause 6 (Risk Assessment, Treatment, Objectives)
  - `Support & Competence`: Clause 7 (Resources, Awareness, Documentation)
  - `Operational Planning`: Clause 8 (Execution of Risk Treatments)
  - `Performance Evaluation`: Clause 9 (Internal Audit, Management Review)
  - `Continuous Improvement`: Clause 10 (Nonconformity, Corrective Actions)
  - `Organizational Controls`: Annex A.5 (Policies, Asset Management, Remote Work)
  - `People Controls`: Annex A.6 (Screening, Terms, Training)
  - `Physical Controls`: Annex A.7 (Physical Perimeter, Clean Desk, Equipment)
  - `Technological Controls`: Annex A.8 (Access Control, Cryptography, Secure Config, Vulnerabilities)
- **Key Required Evidence:**
  - Signed Information Security Policy
  - Statement of Applicability (SoA)
  - Risk Register with Residual Risk Treatments
  - Annual Internal Audit Report & Management Review Minutes
  - Penetration Test Report (conducted within past 12 months)
  - Incident Response & Business Continuity Drill Reports

---

### 2. EU GDPR & German BDSG Privacy Operations (`gdpr-bdsg` v`2024`)
- **Focus:** Complete European and German data privacy operations for SaaS controllers and processors.
- **Domains & Categories:**
  - `Data Protection Principles`: Art. 5 (Lawfulness, Purpose Limitation, Minimization)
  - `Lawful Basis & Consent`: Art. 6 (Contract, Legitimate Interest, Consent Records)
  - `Transparency & Privacy Notices`: Art. 12–14 (Customer & Website Privacy Notices)
  - `Data Subject Rights (DSAR)`: Art. 15–22 (Access, Rectification, Erasure, Portability)
  - `Record of Processing Activities (VVT)`: Art. 30 (Article 30 processing register)
  - `Technical & Organizational Measures (TOMs)`: Art. 32 (Encryption, Resilience, Testing)
  - `Breach Management`: Art. 33–34 (72-hour Supervisory Authority notification procedures)
  - `Data Protection Impact Assessment (DPIA)`: Art. 35 (High-risk processing risk assessments)
  - `Data Protection Officer (DPO)`: Art. 37–39 & BDSG § 38 (DPO appointment & contact)
  - `Processor Agreements & Transfers`: Art. 28 & Chapter V (DPA, Sub-processors, EU SCCs, TIA)
  - `German National Overlay (BDSG)`: § 26 BDSG (Employee Data), § 22 BDSG (Special Category Data)
- **Key Required Evidence:**
  - Article 30 Record of Processing Activities (Verzeichnis von Verarbeitungstätigkeiten)
  - Technical and Organizational Measures (TOMs) Documentation
  - Data Processing Agreements (DPAs) with Sub-processors
  - Transfer Impact Assessment (TIA) & EU Standard Contractual Clauses (SCCs)
  - 72-Hour Breach Incident Response Procedure & Notification Log
  - DPO Appointment Notice (or documented justification under § 38 BDSG if < 20 persons)

---

### 3. NIST Cybersecurity Framework 2.0 (`nist-csf` v`2.0`)
- **Focus:** Comprehensive cybersecurity risk governance, detection, and resilience.
- **Domains & Categories:**
  - `GOVERN (GV)`: Governance, Organizational Context, Risk Strategy, Roles & Supply Chain
  - `IDENTIFY (ID)`: Asset Management, Risk Assessment, Improvement
  - `PROTECT (PR)`: Identity & Access Management, Awareness, Data Security, Platform Security
  - `DETECT (DE)`: Continuous Monitoring, Adverse Event Analysis, Log Correlation
  - `RESPOND (RS)`: Incident Management, Analysis, Mitigation, Communication
  - `RECOVER (RC)`: Incident Recovery, Plan Execution, Post-Incident Updates
- **Key Required Evidence:**
  - Organizational Cybersecurity Risk Strategy Document
  - Enterprise Hardware and Software Asset Inventory
  - Multi-Factor Authentication (MFA) Enforcement Configuration Exports
  - Centralized Audit Logging and Retention Policies
  - Incident Response Plan & Annual Simulation Results

---

### 4. CIS Critical Security Controls v8 - Implementation Group 1 (`cis-controls-ig1` v`8.0`)
- **Focus:** Essential cyber hygiene baseline to prevent the most pervasive cyber attacks.
- **Domains & Categories:**
  - `CIS 1: Inventory & Control of Enterprise Assets`
  - `CIS 2: Inventory & Control of Software Assets`
  - `CIS 3: Data Protection & Encryption`
  - `CIS 4: Secure Configuration of Assets & Software`
  - `CIS 5: Account Management`
  - `CIS 6: Access Control Management`
  - `CIS 7: Continuous Vulnerability Management`
  - `CIS 8: Audit Log Management`
  - `CIS 9: Email & Web Browser Protections`
  - `CIS 10: Malware Defenses`
  - `CIS 11: Data Recovery & Backups`
  - `CIS 12: Network Infrastructure Management`
  - `CIS 14: Security Awareness & Skills Training`
  - `CIS 17: Incident Response Management`
- **Key Required Evidence:**
  - Automated Device and Software Inventories
  - Workstation Endpoint Configuration Baseline (BitLocker/FileVault, auto-updates)
  - Automated Patching Schedule and Scan Reports
  - Encrypted Backup Logs and Offsite Redundancy Verification
  - Annual Workforce Security Awareness Training Records

---

### 5. Minimum Viable Secure Product v2.0 (`mvsp` v`2.0`)
- **Focus:** Lean, practical B2B SaaS security checklist expected by enterprise buyers.
- **Domains & Categories:**
  - `Business Controls`: Vulnerability Disclosure Policy, Vendor Management, Background Checks
  - `Application Security`: HTTPS Everywhere, SSO/SAML, Dependency Scanning, Secrets Hygiene
  - `Operational Security`: Access Control, Centralized Logging, Incident Response, Backups
  - `Physical Security`: Data Center Security, Clean Desk Policy, Device Decommissioning
- **Key Required Evidence:**
  - Public `security.txt` and Vulnerability Disclosure Program
  - Automated Dependency & Container Vulnerability Scan Reports
  - SAML 2.0 / OIDC Enterprise Single Sign-On Architecture
  - Third-Party Datacenter SOC 2 Type II / ISO 27001 Certifications (AWS, GCP, Azure, Hetzner)

---

## 4. Deterministic Applicability Evaluation Engine

Framework applicability is not static. Conformly provides a questionnaire-driven applicability evaluation engine:

### Profile Context Parameters:
1. `entity_role`: `"controller"` | `"processor"` | `"both"`
2. `deployment_model`: `"cloud_saas"` | `"hybrid"` | `"on_premise"`
3. `employee_count`: integer (triggers BDSG § 38(1) Satz 1 DPO obligation when `>= 20` and processing personal data)
4. `processes_personal_data`: boolean
5. `processes_special_category_data`: boolean (triggers Art. 9 GDPR and § 22 BDSG enhanced controls)
6. `dpo_trigger_reasons`: list of statutory appointment triggers (e.g. `LARGE_SCALE_MONITORING`, `SPECIAL_CATEGORY_CORE`, `COMMERCIAL_TRANSFER`). DPO obligation cannot be decided from total employee count alone; any statutory trigger makes DPO appointment mandatory regardless of head count.
7. `remote_work_model`: `"fully_remote"` | `"hybrid"` | `"office_centric"`. Remote work does not automatically remove all physical safeguards; endpoint security, clean desk, screen privacy, and device disposal remain mandatory.
8. `has_physical_offices`: boolean (if `false`, office perimeter safeguards are `SCOPED_OUT`, but endpoint/remote safeguards remain active)
9. `operates_own_datacenter`: boolean (if `false`, physical datacenter controls are inherited with mandatory supplier assurance)
10. `eea_storage_only`: boolean (EEA storage alone does not settle remote-access, onward-transfer, or vendor-support transfer mechanism obligations)
11. `involves_international_transfers`: boolean (triggers Chapter V transfer controls and TIA)
12. `uses_subprocessors`: boolean (triggers Art. 28 processor vetting and DPA requirements; strictly distinguished from general suppliers)
13. `uses_suppliers`: boolean (triggers general third-party security and supply-chain risk governance)

### Output Overlays:
- `OverlayApplicability.APPLICABLE`: Requirement applies to tenant operations.
- `OverlayApplicability.NOT_APPLICABLE`: Requirement does not apply based on business model or regulatory threshold (with automated audit rationale).
- `OverlayApplicability.SCOPED_OUT`: Safeguard is intentionally excluded from the operational boundary with mandatory authorized justification and impact tracking.
- `OverlayApplicability.UNKNOWN`: Insufficient profile facts; defaults to review-required and strictly blocks 100% readiness evaluation until resolved.
