# Conformly — Module A Beta Scope & Framework Release Inventory

**Document Type:** Formal Beta Scope Definition & Candidate Framework Disposition  
**Status:** **ACTIVE — STEP 1 COMPLETED**  
**Date:** 2026-09-13  
**Machine-Readable Manifest:** [`apps/api/src/conformly/frameworks/manifest.json`](file:///c:/Users/AD/Desktop/conformly/apps/api/src/conformly/frameworks/manifest.json)  
**Authority:** `AGENTS.md`, `docs/PRODUCT_SOURCE_OF_TRUTH.md`, and `docs/GLOBAL_FRAMEWORK_CATALOG.md`  

---

## 1. Executive Intent & Scope Reconciliation

This document establishes the verified scope inventory for the **Module A Beta Release** of Conformly.

In accordance with [`docs/MODULE_A_BETA_IMPLEMENTATION_PROMPT.md`](file:///c:/Users/AD/Desktop/conformly/docs/MODULE_A_BETA_IMPLEMENTATION_PROMPT.md):
1. The release inventory reconciles the current five-pack launch list with the comprehensive candidate backlog defined in [`docs/GLOBAL_FRAMEWORK_CATALOG.md`](file:///c:/Users/AD/Desktop/conformly/docs/GLOBAL_FRAMEWORK_CATALOG.md).
2. "All Module A" is **not** silently reduced to five packs. Every candidate catalog entry carrying an "A" package designation has been retrieved, inventoried, and assigned an explicit, legally and architecturally bounded disposition.
3. Country-level coverage records are strictly preserved; no single law or national template is substituted as a global surrogate. Shared standards (e.g. ISO/IEC 27001, NIST CSF, GDPR) are defined once and mapped to jurisdictional overlays where appropriate.

---

## 2. Beta Disposition Taxonomy

Every Tier A candidate framework pack is classified into one of three strict dispositions:

| Disposition | Definition & Release Boundary |
|:---|:---|
| **`REQUIRED_BETA`** | Mandatory framework pack for the initial Beta launch. Fully coded in the working implementation batch; subject to exhaustive clause decomposition, structured evidence schemas, deterministic applicability rules, negative testing, and second-person review gates. |
| **`OWNER_DECISION_REQUIRED`** | Major A-labelled framework candidate for which explicit Product Owner scope confirmation is required before either adopting into `REQUIRED_BETA` (subject to all release gates) or deferring to `LATER_A`. |
| **`LATER_A`** | Validated Core Tier A candidate framework scheduled for post-beta progressive rollout. Retained in the global catalog and country coverage register; not blocking initial beta deployment. |

---

## 3. Working Implementation Batch (`REQUIRED_BETA`)

The following **six** packs comprise the active implementation batch. ISO 9001:2015 was admitted to this batch per **explicit Product Owner decision on 2026-09-13** (ADR D-059), superseding the prior `OWNER_DECISION_REQUIRED` status:

| Pack ID | Framework Name | Source Edition | Jurisdiction | Declared Scope | Status |
|:---|:---|:---|:---|:---|:---:|
| `iso-27001` | **ISO/IEC 27001:2022 ISMS Pre-Audit** | ISO/IEC 27001:2022 (+Amd 1:2024) | Global | Management System Clauses 4–10 & Annex A Reference Controls (A.5–A.8) | `REQUIRED_BETA` |
| `gdpr-bdsg` | **EU GDPR & German BDSG Privacy** | Reg (EU) 2016/679 & BDSG n.F. | EU & Germany | Controller & Processor obligations, Data Subject Rights, Art 30 VVT, Art 32 TOMs, Breach, DPIA, DPO, § 26 BDSG | `REQUIRED_BETA` |
| `nist-csf` | **NIST Cybersecurity Framework 2.0** | NIST SP 1300 (CSF 2.0) | US / Global | CSF 2.0 Core Functions: Govern (GV), Identify (ID), Protect (PR), Detect (DE), Respond (RS), Recover (RC) | `REQUIRED_BETA` |
| `cis-controls-ig1` | **CIS Critical Security Controls v8 IG1** | CIS Controls v8 (IG1) | Global | 56 Essential Cyber Hygiene Safeguards across 18 Control Families | `REQUIRED_BETA` |
| `mvsp` | **Minimum Viable Secure Product 2.0** | MVSP Working Group v2.0 | Global SaaS | Minimum Security Checklist: Business, Application, Operational, and Physical Security | `REQUIRED_BETA` |
| `iso-9001` | **ISO 9001:2015 QMS Pre-Audit** | ISO 9001:2015 (TC1 errata, confirmed 2021) | Global | All addressable Clauses 4–10: Context, Leadership, Planning, Support, Operation (incl. D&D Clause 8.3, External Providers Clause 8.4), Performance Evaluation, Improvement | `REQUIRED_BETA` |

---

## 4. Product Owner Scope Decisions Required (`OWNER_DECISION_REQUIRED`)

The following **four** candidate frameworks require explicit Product Owner scope confirmation before adoption into `REQUIRED_BETA` or deferral to `LATER_A`. ISO 9001 was removed from this list per the Product Owner's explicit decision on 2026-09-13 (ADR D-059):

| Pack ID | Candidate Framework | Scope & Rationale | Decision Request to Product Owner |
|:---|:---|:---|:---|
| `us-ca-ccpa-cpra` | **California CCPA / CPRA** | California Consumer Privacy Act (Cal. Civ. Code § 1798.100 et seq.). High market demand for US privacy. Requires revenue/consumer threshold rules ($25M / 100k consumers) and opt-out workflows. | **Option A:** Include in initial Beta as first US state overlay.<br>**Option B (Recommended):** Defer to post-beta US privacy pack batch. |
| `sa-pdpl` | **Saudi Arabia PDPL** | Royal Decree M/19 & SDAIA Implementing Regulations. Leading Arab-country privacy regime. Requires SDAIA cross-border rules and controller registers. | **Option A:** Include in initial Beta.<br>**Option B (Recommended):** Defer to post-beta regional expansion. |
| `jp-appi` | **Japan APPI** | Act No. 57 of 2003 as amended & PPC Guidelines. Leading APAC commercial privacy standard. Requires Japanese regulatory analysis and PIHBO safety rules. | **Option A:** Include in initial Beta.<br>**Option B (Recommended):** Defer to post-beta APAC expansion. |
| `au-privacy-act` | **Australia Privacy Act 1988 & APPs** | Privacy Act 1988 (Cth), 13 Australian Privacy Principles, and NDB Scheme. Requires $3M AUD statutory turnover threshold evaluation. | **Option A:** Include in initial Beta.<br>**Option B (Recommended):** Defer to post-beta APAC expansion. |

> [!IMPORTANT]
> **Operational Protocol During Scope Review:**  
> While Product Owner scope confirmation is pending for the above four candidates, shared engineering and exhaustive content verification continues uninterrupted on the six active `REQUIRED_BETA` packs. If the Product Owner elects to require any or all of these four candidates for Beta, they immediately become subject to every content, schema, applicability, independent review, and testing gate defined herein.

---

## 5. Post-Beta Tier A Candidate Inventory (`LATER_A`)

All other candidate frameworks designated as Core Tier A in [`GLOBAL_FRAMEWORK_CATALOG.md`](file:///c:/Users/AD/Desktop/conformly/docs/GLOBAL_FRAMEWORK_CATALOG.md) are classified as `LATER_A`. They remain fully registered in the platform architecture and country coverage registers:

### 5.1 Cyber & Baseline Security Guidance
- **`cisa-cpg`** — CISA Cross-Sector Cybersecurity Performance Goals (v1.0.1). Distinct baseline guidance pack.
- **`au-essential-eight-l1`** — Australian Signals Directorate (ASD) Essential Eight Maturity Level 1 Profile. (Levels 2/3 allocated to Tier B).

### 5.2 European Union Country Overlays (26 Member States)
Conformly maintains separate research and release records for national GDPR transpositions and supervisory authorities across all 26 remaining EU member states (Germany is covered under `gdpr-bdsg`):
- Austria (DSG / DSB)
- Belgium (Loi relative à la protection des personnes physiques / APD-GBA)
- Bulgaria (LPPD / CPDP)
- Croatia (AZOP)
- Cyprus (Law 125(I)/2018 / Commissioner)
- Czechia (Act No. 110/2019 Coll. / UOOU)
- Denmark (Databeskyttelsesloven / Datatilsynet)
- Estonia (Isikuandmete kaitse seadus / AKI)
- Finland (Tietosuojalaki / Tietosuojavaltuutetun toimisto)
- France (Loi Informatique et Libertés / CNIL)
- Greece (Law 4624/2019 / HDPA)
- Hungary (Info Act CXII of 2011 / NAIH)
- Ireland (Data Protection Act 2018 / DPC)
- Italy (Codice della Privacy d.lgs 196/2003 as amended / Garante)
- Latvia (Datu valsts inspekcija)
- Lithuania (VDAI)
- Luxembourg (CNPD)
- Malta (IDPC)
- Netherlands (UAVG / Autoriteit Persoonsgegevens)
- Poland (UODO)
- Portugal (CNPD)
- Romania (ANSPDCP)
- Slovakia (UOO)
- Slovenia (IP-RS)
- Spain (LOPDGDD 3/2018 / AEPD)
- Sweden (Integritetsskyddsmyndigheten - IMY)

*Status:* **RESEARCH_REQUIRED / LATER_A**. No synthetic universal EU template is substituted for national statutes.

### 5.3 European Adjacent Markets (EEA, UK, Switzerland)
- **Iceland, Liechtenstein, Norway** — National EEA implementation overlays (`LATER_A`).
- **United Kingdom** — UK GDPR & Data Protection Act 2018 (`uk-gdpr-dpa`) (`LATER_A`).
- **Switzerland** — Swiss Federal Act on Data Protection (revFADP / DSG) (`swiss-fadp`) (`LATER_A`).

### 5.4 United States State Privacy Register (49 States + DC)
- All 49 US States (excluding California) + District of Columbia tracked in the state coverage ledger (`LATER_A`):
  - Enacted omnibus states (Virginia VCDPA, Colorado CPA, Connecticut CTDPA, Utah UCPA, Texas TDPSA, Florida, Oregon, Montana, etc.)
  - General breach notification laws for remaining states.

### 5.5 Arab League Regional Coverage (21 Countries)
- 21 Arab League jurisdictions (excluding Saudi Arabia):
  - UAE Federal Decree-Law No. 45/2021 (`uae-pdpl`), Qatar Law 13/2016, Bahrain Law 30/2018, Oman RD 6/2022, Kuwait CITRA, Jordan Law 24/2023, Egypt Law 151/2020, Morocco Law 09-08, Algeria, Tunisia, Lebanon, Mauritania, Somalia (`LATER_A`).
  - Explicit research gap countries: Comoros, Djibouti, Iraq, Libya, Palestine, Sudan, Syria, Yemen (`LATER_A` research backlog).

### 5.6 Global International Expansion Candidates
- Canada PIPEDA / Quebec Law 25, Brazil LGPD, Singapore PDPA, South Korea PIPA, India DPDP, New Zealand Privacy Act, South Africa POPIA, Israel Privacy Protection Law (`LATER_A` discovery backlog).

---

## 6. Machine-Readable Manifest Integration

The complete release inventory is codified in machine-readable JSON at [`apps/api/src/conformly/frameworks/manifest.json`](file:///c:/Users/AD/Desktop/conformly/apps/api/src/conformly/frameworks/manifest.json). 

Each entry in the manifest provides:
1. `pack_id`: Canonical system slug.
2. `source_edition`: Precise publisher version/amendment.
3. `conformly_content_revision`: Content version string.
4. `jurisdiction`: Geographical/legal jurisdiction.
5. `declared_scope`: Exact covered boundaries.
6. `profile`: Evaluated operational profile.
7. `required_for_beta_status`: Disposition (`REQUIRED_BETA`, `OWNER_DECISION_REQUIRED`, `LATER_A`).
8. `decision_provenance`: Authoritative origin document/ADR reference.
9. `content_state`: Current development/review status.
10. `owner`: Responsible team / role.
11. `blockers`: Explicit blocking dependencies.
12. `evidence`: Verification links, official publisher URLs, and source files.

---

## 7. Exit Criteria Verification for Step 1

- [x] Every single candidate framework bearing an "A" classification in [`GLOBAL_FRAMEWORK_CATALOG.md`](file:///c:/Users/AD/Desktop/conformly/docs/GLOBAL_FRAMEWORK_CATALOG.md) has an explicit disposition.
- [x] Zero silent reductions or omissions of catalog entries.
- [x] Active implementation batch clearly isolated to the 5 coded packs (`iso-27001`, `gdpr-bdsg`, `nist-csf`, `cis-controls-ig1`, `mvsp`).
- [x] Formal scope confirmation requested from the Product Owner for ISO 9001 and the 4 regional candidates (`us-ca-ccpa-cpra`, `sa-pdpl`, `jp-appi`, `au-privacy-act`).
- [x] Country-level coverage records preserved for all 27 EU member states, 50 US states, and 22 Arab League nations.
- [x] Machine-readable manifest created at [`apps/api/src/conformly/frameworks/manifest.json`](file:///c:/Users/AD/Desktop/conformly/apps/api/src/conformly/frameworks/manifest.json).
