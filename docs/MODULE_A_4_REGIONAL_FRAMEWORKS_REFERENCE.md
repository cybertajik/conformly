# Conformly — Module A Regional Frameworks Reference (4 Frameworks)

This document provides a complete, copy-paste ready reference for the 4 regional privacy frameworks admitted to **Module A** per Product Owner decision (ADR D-060):

1. **California Consumer Privacy Act (CCPA / CPRA)** (`us-ca-ccpa-cpra`) — United States (California)
2. **Saudi Arabia Personal Data Protection Law (PDPL)** (`sa-pdpl`) — Kingdom of Saudi Arabia
3. **Japan Act on the Protection of Personal Information (APPI)** (`jp-appi`) — Japan
4. **Australia Privacy Act 1988 & Australian Privacy Principles (APPs)** (`au-privacy-act`) — Australia

---

## Copy-Paste Block: All 4 Frameworks Summary

```json
[
  {
    "slug": "us-ca-ccpa-cpra",
    "name": "California Consumer Privacy Act (CCPA / CPRA)",
    "version": "v2023",
    "jurisdiction": "United States - California (US-CA)",
    "authority": "State of California / California Privacy Protection Agency (CPPA)",
    "source_edition": "Cal. Civ. Code § 1798.100 et seq. & CPPA Regulations (11 CCR § 7000 et seq.)",
    "controls_count": 8,
    "evidence_count": 8
  },
  {
    "slug": "sa-pdpl",
    "name": "Saudi Arabia Personal Data Protection Law (PDPL)",
    "version": "v2023",
    "jurisdiction": "Kingdom of Saudi Arabia (SA)",
    "authority": "Saudi Data & AI Authority (SDAIA)",
    "source_edition": "Royal Decree No. M/19 & Implementing Regulations",
    "controls_count": 6,
    "evidence_count": 6
  },
  {
    "slug": "jp-appi",
    "name": "Japan Act on the Protection of Personal Information (APPI)",
    "version": "v2022",
    "jurisdiction": "Japan (JP)",
    "authority": "Personal Information Protection Commission (PPC) Japan",
    "source_edition": "Act No. 57 of 2003 (as amended through 2020/2022) & PPC Guidelines",
    "controls_count": 6,
    "evidence_count": 6
  },
  {
    "slug": "au-privacy-act",
    "name": "Australia Privacy Act 1988 & APPs",
    "version": "v1988",
    "jurisdiction": "Australia (AU)",
    "authority": "Office of the Australian Information Commissioner (OAIC)",
    "source_edition": "Privacy Act 1988 (Cth) incorporating 13 APPs & NDB Scheme",
    "controls_count": 9,
    "evidence_count": 9
  }
]
```

---

## 1. California Consumer Privacy Act (CCPA / CPRA)

- **Pack Slug:** `us-ca-ccpa-cpra`
- **Framework Version:** `v2023`
- **Jurisdiction:** United States — California (US-CA)
- **Source Authority:** California Privacy Protection Agency (CPPA) / Office of the Attorney General
- **Statutory Citation:** California Civil Code § 1798.100 et seq. (incorporating CPRA amendments)
- **Implementation File:** `apps/api/src/conformly/frameworks/packs/us_ca_ccpa_cpra.py`

### Controls & Statutory Requirements

| Control ID | Statutory Reference | Title | Category | Operating Cadence | Description |
|---|---|---|---|---|---|
| `CCPA-1798-100` | Cal. Civ. Code § 1798.100 | Notice at Collection & Purpose Limitation | Consumer Transparency | At collection point | Inform consumers at or before collection regarding personal info categories collected and business purposes. |
| `CCPA-1798-105` | Cal. Civ. Code § 1798.105 | Consumer Right to Delete Personal Information | Consumer Rights & Requests | Within 45 days | Process consumer requests to delete personal information collected by the business, subject to statutory retention exceptions. |
| `CCPA-1798-106` | Cal. Civ. Code § 1798.106 | Consumer Right to Correct Inaccurate Information | Consumer Rights & Requests | Within 45 days | Rectify inaccurate personal information maintained about the consumer upon receipt of a verifiable consumer request. |
| `CCPA-1798-110` | Cal. Civ. Code § 1798.110 | Consumer Right to Know Personal Information Collected | Consumer Rights & Requests | Within 45 days | Disclose categories, sources, commercial purposes, and specific pieces of personal information collected upon verifiable request. |
| `CCPA-1798-120` | Cal. Civ. Code § 1798.120 | Consumer Right to Opt-Out of Sale or Sharing | Consumer Choice & Opt-Out | Immediate / Continuous | Provide clear 'Do Not Sell or Share My Personal Information' mechanism and respect opt-out preference signals (GPC). |
| `CCPA-1798-121` | Cal. Civ. Code § 1798.121 | Consumer Right to Limit Use of Sensitive Personal Info | Consumer Choice & Opt-Out | Immediate / Continuous | Provide 'Limit the Use of My Sensitive Personal Information' link and restrict sensitive data processing to necessary service purposes. |
| `CCPA-1798-125` | Cal. Civ. Code § 1798.125 | Non-Discrimination for Exercising Consumer Rights | Consumer Protection | Continuous | Prohibit retaliatory discrimination, denial of services, quality degradation, or unjustified financial penalties for exercising privacy rights. |
| `CCPA-1798-140` | Cal. Civ. Code § 1798.140 | Business Scope, Thresholds & Service Provider Terms | Governance & Vendor Management | Annual review | Establish statutory applicability ($25M revenue, 100k consumers, or 50%+ sales) and enforce mandatory § 1798.140(ag) vendor contract terms. |

---

## 2. Saudi Arabia Personal Data Protection Law (PDPL)

- **Pack Slug:** `sa-pdpl`
- **Framework Version:** `v2023`
- **Jurisdiction:** Kingdom of Saudi Arabia (SA)
- **Source Authority:** Saudi Data & AI Authority (SDAIA)
- **Statutory Citation:** Royal Decree No. M/19 of 9/2/1443H (as amended by Royal Decree M/148 of 5/9/1444H)
- **Implementation File:** `apps/api/src/conformly/frameworks/packs/sa_pdpl.py`

### Controls & Statutory Requirements

| Control ID | Statutory Reference | Title | Category | Operating Cadence | Description |
|---|---|---|---|---|---|
| `SA-PDPL-Art-4` | Saudi Arabia PDPL Art 4 | Data Subject Rights & Request Management | Data Subject Rights | Within 30 days | Operationalize data subject rights: right to know, right to access/copy, right to correct/update, and right to request destruction. |
| `SA-PDPL-Art-5` | Saudi Arabia PDPL Art 5 | Lawful Processing Bases & Consent | Lawfulness & Governance | Prior to processing | Mandate valid consent before personal data processing, except where statutory contract performance or legal exemptions apply. |
| `SA-PDPL-Art-12` | Saudi Arabia PDPL Art 12 | Privacy Policy & Public Transparency | Transparency & Notice | Annual review | Publish and maintain an accessible privacy policy specifying purposes, collected categories, storage methods, and data subject rights. |
| `SA-PDPL-Art-18` | Saudi Arabia PDPL Art 18 | Technical & Organizational Security Safeguards | Information Security | Continuous | Enforce necessary organizational, administrative, and technical safeguards to prevent leakage, loss, or unauthorized access to personal data. |
| `SA-PDPL-Art-24` | Saudi Arabia PDPL Art 24 | Mandatory Breach Notification to SDAIA | Incident Response | Within 72 hours | Notify SDAIA immediately (within 72 hours of becoming aware) of any personal data breach or leakage, and notify affected data subjects. |
| `SA-PDPL-Art-29` | Saudi Arabia PDPL Art 29 | Cross-Border Personal Data Transfer Controls | International Transfers | Prior to transfer | Restrict overseas transfers of personal data unless transferring to SDAIA-approved adequate jurisdictions or under approved standard clauses. |

---

## 3. Japan Act on the Protection of Personal Information (APPI)

- **Pack Slug:** `jp-appi`
- **Framework Version:** `v2022`
- **Jurisdiction:** Japan (JP)
- **Source Authority:** Personal Information Protection Commission (PPC) Japan
- **Statutory Citation:** Act No. 57 of 2003 (as amended through 2020 and 2022 statutory reforms)
- **Implementation File:** `apps/api/src/conformly/frameworks/packs/jp_appi.py`

### Controls & Statutory Requirements

| Control ID | Statutory Reference | Title | Category | Operating Cadence | Description |
|---|---|---|---|---|---|
| `JP-APPI-Art-17` | Japan APPI Art 17 | Specification & Notice of Purpose of Use | Purpose Limitation & Transparency | At acquisition | Explicitly define the purpose of use of personal information and promptly notify or publicly announce the purpose upon acquisition. |
| `JP-APPI-Art-20` | Japan APPI Art 20 | Safety Control Measures (System Security) | Security Safeguards | Continuous | Implement organizational, personnel, physical, and technical safety control measures to prevent leakage, loss, or unauthorized modification. |
| `JP-APPI-Art-21` | Japan APPI Art 21 | Supervision of Personnel & Employees | Internal Governance | Annual training | Supervise employees handling personal data, including establishing security procedures, mandatory training, and access controls. |
| `JP-APPI-Art-22` | Japan APPI Art 22 | Supervision of Trustees & Subcontractors | Vendor Management | Prior to entrustment | Supervise third-party trustees and cloud service providers handling entrusted personal data through contractual covenants and audits. |
| `JP-APPI-Art-26` | Japan APPI Art 26 | Mandatory Leak Reporting to PPC & Notice to Individuals | Incident Management | Prompt initial notice | Report significant personal data leak incidents to the PPC without delay and notify affected individuals pursuant to statutory timelines. |
| `JP-APPI-Art-28` | Japan APPI Art 28 | Cross-Border Transfer Restrictions & Foreign Safeguards | International Transfers | Prior to transfer | Restrict providing personal data to foreign third parties without individual consent or verification of equivalent safety management systems. |

---

## 4. Australia Privacy Act 1988 & APPs

- **Pack Slug:** `au-privacy-act`
- **Framework Version:** `v1988`
- **Jurisdiction:** Australia (AU)
- **Source Authority:** Office of the Australian Information Commissioner (OAIC)
- **Statutory Citation:** Privacy Act 1988 (Cth) incorporating 13 Australian Privacy Principles & Part IIIC NDB Scheme
- **Implementation File:** `apps/api/src/conformly/frameworks/packs/au_privacy_act.py`

### Controls & Statutory Requirements

| Control ID | Statutory Reference | Title | Category | Operating Cadence | Description |
|---|---|---|---|---|---|
| `AU-APP-1` | Australia Privacy Act 1988 APP 1 | Open & Transparent Management of Personal Info | Privacy Governance | Annual review | Implement practices, procedures, and systems to ensure APP compliance and maintain an up-to-date APP privacy policy. |
| `AU-APP-3` | Australia Privacy Act 1988 APP 3 | Collection of Solicited Personal Information | Data Collection | Continuous | Collect personal information only where reasonably necessary for organizational functions, collecting sensitive info only with consent. |
| `AU-APP-5` | Australia Privacy Act 1988 APP 5 | Notification of the Collection of Personal Info | Transparency & Notice | At or before collection | Take reasonable steps to notify individuals of collection matters, including purposes, disclosure practices, and complaint mechanisms. |
| `AU-APP-6` | Australia Privacy Act 1988 APP 6 | Use or Disclosure of Personal Information | Use & Disclosure | Continuous | Use or disclose personal information only for the primary purpose of collection, unless secondary consent or statutory exceptions apply. |
| `AU-APP-8` | Australia Privacy Act 1988 APP 8 | Cross-Border Disclosure of Personal Information | Cross-Border Disclosure | Prior to disclosure | Take reasonable steps to ensure overseas recipients do not breach the APPs before disclosing personal info across borders. |
| `AU-APP-11` | Australia Privacy Act 1988 APP 11 | Security of Personal Information | Information Security | Continuous | Protect personal information from misuse, interference, loss, and unauthorized access, and destroy/de-identify info when no longer needed. |
| `AU-APP-12` | Australia Privacy Act 1988 APP 12 | Access to Personal Information | Individual Rights | Within 30 days | Provide individuals access to personal information held about them upon request within a reasonable period, subject to statutory exceptions. |
| `AU-APP-13` | Australia Privacy Act 1988 APP 13 | Correction of Personal Information | Individual Rights | Within 30 days | Take reasonable steps to correct personal information to ensure it is accurate, up-to-date, complete, relevant, and not misleading. |
| `AU-NDB-Scheme` | Australia Privacy Act 1988 NDB Scheme | Notifiable Data Breaches (NDB) Scheme | Incident Management | Assessment in 30 days | Assess suspected breaches promptly and notify the OAIC and affected individuals if an eligible data breach is likely to result in serious harm. |
