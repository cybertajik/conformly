# Conformly global framework catalog and A–D expansion plan

## 1. Status, authority, and scope

Prepared 2026-09-13 following the Product Owner's request to expand the catalog across the whole EU,
USA, Arab countries, China, Japan, Australia, and specialist cases; organize basic packs into A and
more complex packs into B–D; and plan optional products including whistleblower and LMS.

The expansion direction is user-authorized. The exact assignments below are a proposed product
catalog for review, not previously approved Trello decisions or implemented framework content.
Trello DEU has not been updated by this task. The existing V4 source snapshot remains historical
evidence. Do not represent this draft as a verbatim Trello plan.

This is a broad coverage backlog. It does not assert that all applicable laws in every jurisdiction
have been discovered, that candidate packs are legally validated, or that Conformly already supports
them. Country coverage and production-ready control content are separate deliverables.

Baseline discovery sources: [Vanta catalog](https://www.vanta.com/products/additional-frameworks)
and [Drata catalog](https://drata.com/frameworks). Their catalogs identify market demand; they are
not authorities for legal interpretation and their proprietary controls/templates must not be copied.
Official sources linked below are research starting points. Every release needs clause-level review.

### Work already underway

The Product Owner reports the following four items are being coded elsewhere as of 2026-09-13:

1. Organizational authorization, role separation, assigned access and temporary engagements.
2. Entitlement enforcement, dates, framework-pack access and quantity/storage limits.
3. Organization/risk/asset/vendor workflows and encryption.
4. Export/deletion coverage for those new modules.

Status: IN PROGRESS — USER REPORTED, not independently completed or retested by this catalog task.
This document does not change those implementation files or redefine their acceptance criteria.

## 2. Packaging principles

- A–D denote capability/framework packages. A framework is not a separate application.
- Shared modules remain one tenant-aware compliance engine: organizations, authorization,
  entitlements, catalog, evidence, policies, risks/assets/vendors, findings/tasks, assessments,
  readiness, audit, notifications, exports and retention.
- Country is an applicability dimension, not a reason by itself to charge a higher tier.
- The same ISO or NIST pack must not be duplicated for each region; add linked local overlays.
- A pack is a law, standard, guidance set, assessment scheme, contractual program, or custom
  control set. Store that type explicitly; do not label everything a certification.
- A complete low-tier pack must contain all requirements applicable to its declared scope.
  An introductory checklist for a higher-tier law must say "screening only" and must not yield a
  full-framework readiness result.
- Package selection never changes the law applicable to a tenant. Display unresolved applicable
  obligations even if the tenant has not licensed the corresponding specialist workflow.
- Isolation, encryption, audit, export/deletion and baseline security remain universal.
- A higher package includes access to released lower-package content in this proposal, but actual
  adoption remains explicit. Licensing or specialist-assessor fees are separate, disclosed items.
- Framework access does not imply local hosting. Germany-only production remains the existing
  baseline. A jurisdiction or customer requiring incompatible residency is a deployment blocker,
  not a requirement to bypass by uploading data anyway.

## 3. Proposed A–D packages

### A — Core compliance and common foundations

Audience: general businesses building an initial compliance program.
Includes the full existing Tier A operational platform, plus the **five core Tier A framework packs** (see [FRAMEWORK_PACKS_TIER_A.md](file:///c:/Users/AD/Desktop/conformly/docs/FRAMEWORK_PACKS_TIER_A.md) and [MODULE_A_BETA_RELEASE_EVIDENCE.md](file:///c:/Users/AD/Desktop/conformly/docs/MODULE_A_BETA_RELEASE_EVIDENCE.md)):
1. **ISO/IEC 27001:2022 Pre-Audit Readiness** (`iso-27001` v`2022`) — `ENGINEERING_COMPLETE` (`CONTENT_REVIEW_PENDING`)
2. **EU GDPR & German BDSG Privacy Operations** (`gdpr-bdsg` v`2024`) — `ENGINEERING_COMPLETE` (`CONTENT_REVIEW_PENDING`)
3. **NIST Cybersecurity Framework 2.0** (`nist-csf` v`2.0`) — `ENGINEERING_COMPLETE` (`CONTENT_REVIEW_PENDING`)
4. **CIS Critical Security Controls v8 IG1** (`cis-controls-ig1` v`8.0`) — `ENGINEERING_COMPLETE` (`CONTENT_REVIEW_PENDING`)
5. **Minimum Viable Secure Product v2.0** (`mvsp` v`2.0`) — `ENGINEERING_COMPLETE` (`CONTENT_REVIEW_PENDING`)

*Note on Status:* All five packs have 100% complete schema, coverage ledgers, declarative applicability engines, structured evidence generation, and acceptance tests (`ENGINEERING_COMPLETE`). However, in accordance with Conformly governance rules, production customer issuance remains gated until genuine human legal/compliance review and explicit Product Owner release approval are recorded. No AI may mark packs `BETA_READY` prematurely.

Workflows: scope/applicability evaluation rules, obligations, evidence requests, policies, assignments, risk/asset/vendor
registers, findings, pre-audit, independent review, reports and optional public profile.
Country expansion can add ordinary privacy packs without redesigning this foundation.

### B — Mature assurance and multi-framework operations

Audience: organizations needing buyer assurance, cloud/privacy management and continuity.
Adds released SOC, cloud assurance, privacy-management and business-continuity packs; stronger
observation-period evidence, management-system audits, cross-framework reuse and ongoing reviews.
Advanced workflow depth does not remove existing Tier A controls or pre-audit capabilities.

### C — Regulated sectors and demanding assurance

Audience: finance, health, automotive, critical services, regulated AI and public-sector suppliers.
Adds sector-specific registers, incident/reporting obligations, outsourcing obligations, evidence
periods, specialized assessor collaboration and regulation-specific reports.

### D — Sovereign, defense, industrial and specialist programs

Audience: highly constrained government/defense, industrial systems and complex product assurance.
Adds program-specific boundary definitions, inherited controls, technical assurance artifacts,
specialist assessment outputs and deployment eligibility checks.
Do not promise a government authorization or certification from a Conformly readiness score.

These are packaging proposals. B–D rollout remains future work; it does not expand the currently
running Tier A implementation tasks automatically.

## 4. Cross-region catalog

Notation: A/B/C/D is the proposed minimum package. "Candidate" means current edition, owner,
licensing, applicability and control content still require validation. Named standards are catalog
families; edition numbers and assessment paths are separate release records.

### Foundations and broad business assurance

- A: ISO/IEC 27001 — information-security management readiness; associated ISO/IEC 27002 guidance
  mapped separately, not marketed as another certification.
- A: ISO 9001 — quality-management readiness; process owners, objectives, nonconformities and review.
- A: NIST CSF — profiles and outcomes; keep NIST's own tiers separate from Conformly A–D.
- A: CIS Controls IG1; B: IG2/IG3 as explicit profiles, not independent invented standards.
- A: MVSP and CISA cross-sector Cybersecurity Performance Goals — distinct baseline guidance packs.
- B: SOC 2 Type I/Type II readiness; SOC 1 and SOC 3 as separate candidate reporting-program packs.
- B: ISO/IEC 27701, ISO/IEC 27017, ISO/IEC 27018 — privacy management and cloud guidance.
- B: ISO 22301 — business continuity; ISO/IEC 20000-1 — service management candidate.
- B: CSA CCM/CAIQ and STAR paths — distinguish control catalog, questionnaire and assurance level.
- B: COBIT, AWS Foundational Technical Review, Microsoft SSPA — distinct governance/vendor programs.
- B: ISO 14001, ISO 45001, ISO 50001 — environmental, occupational safety and energy candidates;
  require domain workflows beyond cybersecurity evidence before release.
- B: ISO 37001 and ISO 37301 — anti-bribery and compliance-management candidates.
- B: NIST AI RMF — voluntary AI risk management; C: ISO/IEC 42001 management-system readiness.
- C: AIUC-1 — candidate private AI assurance standard; owner, rights and current edition verification
  required. Its appearance in a vendor catalog is not legal endorsement.
- C: PCI DSS — separate merchant/service-provider scope and SAQ/ROC pathways, no blanket package
  claim; payment-software standards are separate D candidates.
- C: HITRUST e1/i1/r2 — separately licensed assessment paths, not substitutes for HIPAA obligations.
- D: customer/industry custom assurance packs — validated mappings and explicit claim boundaries.

Sources: [ISO 27001](https://www.iso.org/standard/27001),
[ISO management-system catalog](https://www.iso.org/management-system-standards-list.html),
[NIST framework distinctions](https://www.nist.gov/cyberframework/faqs),
[NIST AI RMF](https://airc.nist.gov/airmf-resources/airmf/),
[CISA CPG](https://www.cisa.gov/cybersecurity-performance-goals),
[PCI DSS](https://www.pcisecuritystandards.org/standards/pci-dss/).
Other entries here remain vendor-discovered or research candidates until owner-source validation.

## 5. Europe — every EU member state, plus adjacent markets

### EU-wide packs

- A: GDPR plus country overlays; processing records, rights, controller/processor obligations,
  contracts, incident evidence and applicable transfer/DPIA records. Complex operational automation
  may be an add-on, but required evidence tasks remain available in the base pack.
- B: ePrivacy/national electronic-communications and cookie rules; do not invent a single uniform
  EU cookie law implementation.
- C: NIS2 plus national transpositions, entity classification and relevant implementing acts.
- C: DORA — ICT risk, critical functions, outsourcing/information registers, resilience and incidents.
- C: EU AI Act — role/risk/applicability-specific obligations and staged effective dates.
- C: Cyber Resilience Act — product scope, vulnerability handling, technical documentation and
  reporting; not automatically applicable to every SaaS business.
- C: CER Directive, eIDAS/eIDAS2, EU accessibility obligations, Data Act, DSA and sector-specific
  digital obligations — separate candidate families, each with entity/product applicability.
- C: CSRD/ESRS, CSDDD and supply-chain sustainability — candidate content with amendment and
  timetable review; do not freeze historical thresholds into code.
- C/D: MDR/IVDR and regulated medical-product quality/security — specialist pack family.

Sources: [EU NIS2](https://digital-strategy.ec.europa.eu/en/policies/nis2-directive),
[EU AI Act](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai),
[EU cybersecurity policy index](https://digital-strategy.ec.europa.eu/en/policies/cybersecurity-policies),
[EDPB authorities](https://www.edpb.europa.eu/about-edpb/our-members_en).
These indexes support research; they do not validate every candidate law's current obligations.

### Mandatory country coverage register — 27 EU members

AT Austria; BE Belgium; BG Bulgaria; HR Croatia; CY Cyprus; CZ Czechia; DK Denmark; EE Estonia;
FI Finland; FR France; DE Germany; GR Greece; HU Hungary; IE Ireland; IT Italy; LV Latvia;
LT Lithuania; LU Luxembourg; MT Malta; NL Netherlands; PL Poland; PT Portugal; RO Romania;
SK Slovakia; SI Slovenia; ES Spain; SE Sweden.

For EACH country create separate research/release records for national GDPR supplements, privacy
authority, electronic-communications rules, NIS2 transposition, competent authorities, sector rules,
reporting routes and dates. Status is RESEARCH REQUIRED until that country's reviewed overlay is
released. No "EU complete" badge from a single GDPR template.

### National and adjacent specialist candidates

- Germany: A BDSG overlay; B BSI IT-Grundschutz profile; C BSI C5 and TISAX/VDA ISA; C sector/B3S
  profiles where relevant. Assessments and attestations must retain their actual scheme labels.
- France: C HDS; D SecNumCloud; national privacy/NIS2 overlays.
- Spain: C ENS and national privacy overlay.
- Belgium: B CyberFundamentals profiles; national NIS2 mapping.
- Netherlands: B/C NEN 7510 and public-sector baseline profiles; current versions to verify.
- Italy: C/D public-sector cloud/ACN qualification candidates.
- Other EU states: add procurement/sector schemes when their official owner is identified; do not
  substitute another country's controls for missing local requirements.
- EEA: Iceland, Liechtenstein and Norway — separate country overlays and local implementation dates.
- UK: A/B UK GDPR and Data Protection Act; B Cyber Essentials/Plus; C NHS DSPT and CAF candidates.
- Switzerland: A/B FADP; C FINMA-related outsourcing/cyber requirements candidates.

Sources: [BSI IT-Grundschutz](https://www.bsi.bund.de/SharedDocs/Downloads/EN/BSI/Grundschutz/Webkurs/IT_Grundschutz_Online_Course.html),
[ENX TISAX](https://portal.enx.com/en-US/TISAX/),
[VDA ISA owner](https://portal.enx.com/en-us/TISAX/ISA/).
National schemes without a linked owner in this draft are explicitly discovery candidates.

## 6. United States

- A: NIST CSF/CISA CPG/CIS IG1 and general security foundations (reuse global packs).
- A: ordinary state privacy-law readiness overlays once validated; B: complex multi-state privacy
  operations. California CCPA/CPRA is one amended-law family, not two independent certifications.
- B: SOC 2; B/C SOC 1/SOX ITGC according to financial-reporting scope.
- C: HIPAA/HITECH, GLBA/FTC Safeguards, NYDFS 23 NYCRR 500, FFIEC examination guidance, CRI Profile,
  OFDSS and PCI DSS — distinct sector packs with scope review.
- C: NIST SP 800-171; D: SP 800-172 and demanding CUI/defense profiles.
- C/D: NIST SP 800-53 profiles, CMMC assessment paths and FedRAMP paths. Resolve current program
  rules and transition status before assigning editions or publishing eligibility claims.
- D: CJIS, IRS Publication 1075, StateRAMP/GovRAMP naming/transition research, ITAR/EAR information
  handling, NERC CIP and government/cloud-specific assurance candidates.
- C: COPPA, FERPA, consumer-health and biometric privacy overlays — narrow applicability, not
  automatically covered by a state's general consumer privacy pack.

Coverage target: all 50 states plus DC; territories separately. Create one record per jurisdiction
for general privacy, breach notification and sector-specific overlays. A jurisdiction with no
verified omnibus law stays "research reviewed / no applicable omnibus law identified as of date",
not "no privacy requirements". Puerto Rico, Guam, US Virgin Islands, American Samoa and Northern
Mariana Islands need their own research entries.

State register: Alabama, Alaska, Arizona, Arkansas, California, Colorado, Connecticut, Delaware,
Florida, Georgia, Hawaii, Idaho, Illinois, Indiana, Iowa, Kansas, Kentucky, Louisiana, Maine,
Maryland, Massachusetts, Michigan, Minnesota, Mississippi, Missouri, Montana, Nebraska, Nevada,
New Hampshire, New Jersey, New Mexico, New York, North Carolina, North Dakota, Ohio, Oklahoma,
Oregon, Pennsylvania, Rhode Island, South Carolina, South Dakota, Tennessee, Texas, Utah, Vermont,
Virginia, Washington, West Virginia, Wisconsin and Wyoming; District of Columbia separately.
These entries define the research scope, not a claim that every state has the same privacy law.

Sources: [California laws/regulations](https://cppa.ca.gov/regulations/),
[HHS HIPAA](https://www.hhs.gov/hipaa/for-professionals/security/index.html),
[FTC Safeguards](https://search.ftc.gov/legal-library/browse/rules/safeguards-rule),
[FTC COPPA](https://www.ftc.gov/enforcement/coppa-safe-harbor-program),
[FedRAMP current rules](https://www.fedramp.gov/2026/).
Other sector candidates need their own official owner and version review before implementation.

## 7. Arab-country coverage

Planning coverage uses the 22 Arab League countries. There is no single "Arab GDPR" or universal
GCC framework. Federal, sector, free-zone and territorial regimes require separate applicability.

### Named research targets

- Saudi Arabia: A PDPL general readiness; B/C transfer/sector overlays; C NCA ECC and SAMA
  cybersecurity; D NCA cloud, critical-system, data and operational-technology profiles.
- UAE: A federal PDPL; B DIFC and ADGM separate privacy regimes; C/D UAE information-assurance,
  Dubai security and sector-specific financial/health profiles (owner/source review required).
- Qatar: A/B personal-data privacy law; C National Information Assurance; B/C QFC regime candidate.
- Bahrain: A/B personal-data protection; C financial-sector CBB requirements.
- Oman: A PDPL and implementing rules; C sector-specific cybersecurity candidates.
- Kuwait: A/B CITRA privacy regulation within its actual scope; C financial/cybersecurity candidates.
- Jordan: A personal-data protection plus implementing instruments; C sector overlays.
- Egypt: A/B personal-data protection and executive regulations; C regulated-sector overlays.
- Morocco: A Law 09-08 privacy; C DGSSI/cybersecurity sector candidates.
- Algeria: A/B personal-data protection family; C sector rules, editions/authority to verify.
- Tunisia: A/B personal-data protection family; C sector rules, editions/authority to verify.
- Lebanon: A/B personal-data/electronic-transactions family; C banking/sector rules to verify.
- Mauritania: A/B personal-data protection family, official instruments to verify.
- Somalia: A/B data-protection family, implementation/authority scope to verify.

### Explicit research gaps — included in the coverage backlog

Comoros, Djibouti, Iraq, Libya, Palestine, Sudan, Syria and Yemen each require an individual legal/
sector research record. Do not fabricate a comprehensive privacy law or mark a country supported
because no law was found in a quick search. Iraq and other jurisdictions with multiple applicable
territorial regimes require sub-jurisdiction records when relevant.

Sources: [Saudi PDPL](https://sdaia.gov.sa/en/SDAIA/about/Pages/RegulationsAndPolicies.aspx),
[NCA ECC](https://nca.gov.sa/en/regulatory-documents/controls-list/ecc/),
[NCA cloud dependency mapping](https://nca.gov.sa/ar/ccc_methodology_and_mapping_annex_en.pdf),
[SAMA framework](https://rulebook.sama.gov.sa/en/entiresection/3837),
[UAE privacy overview](https://u.ae/en/about-the-uae/digital-uae/data/data-protection-laws.),
[ADGM guidance](https://www.adgm.com/operating-in-adgm/office-of-data-protection/guidance),
[Qatar NIA](https://assurance.ncsa.gov.qa/sites/default/files/publications/policy/2023/NCSA_CSGA_%20National_Information_Assurance_Standard_En_V2.1_0.pdf),
[Bahrain regulatory index](https://www.cbb.gov.bh/laws-regulations/),
[Oman privacy](https://www.mtcit.gov.om/sectors/governance/personal),
[Kuwait legal index](https://e.gov.kw/sites/kgoenglish/Pages/ApplicationPages/Policies.aspx),
[Jordan laws](https://www.modee.gov.jo/EN/List/The_law_regulations_and_instructions),
[Egypt PDPC](https://www.pdpc.gov.eg/), [Morocco CNDP](https://www.cndp.ma/textes-et-lois/).
Unlinked countries remain unverified discovery targets, even when a law family is named above.

## 8. China

- B: PIPL, Data Security Law and Cybersecurity Law as separate but related obligation families.
- C: Network Data Security Management Regulations; cross-border transfer mechanism workflows;
  security assessment, standard-contract and certification pathways treated separately.
- C/D: MLPS, including GB/T 22239-related controls and applicable assessment levels; CII and
  sector/localization profiles require specialist review.
- D: algorithm/recommendation, deep-synthesis, generative-AI and specialized cryptography candidates.
- B: Hong Kong PDPO and Macau personal-data protection as separate jurisdictions, not mainland
  overlays inheriting PIPL automatically; current official sources to validate.

Conformly may prepare control/evidence registers only where the hosting and data-transfer model is
permitted for the tenant. Chinese-language content, local legal review and any necessary deployment
changes are release dependencies, not fulfilled by translated English templates.

Sources: [CAC cross-border mechanisms](https://www.cac.gov.cn/2024-03/22/c_1712776611649184.htm),
[Network Data Security Management Regulations](https://www.cac.gov.cn/2024-09/30/c_1729384452307680.htm),
[GB/T 22239 record](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=BAFB47E8874764186BDB7865E8344DAF).

## 9. Japan

- A: APPI general privacy readiness, PPC guidance and applicable local overlays.
- B: JIS Q 27001/ISO 27001 relationship and JIS Q 15001/PrivacyMark candidates; avoid duplicated
  control catalogs and verify licensing/assessment requirements.
- C: METI Cyber/Physical Security Framework and financial-sector FISC candidates.
- D: ISMAP/ISMAP-LIU program-specific readiness and government-cloud requirements.
- C/D: medical-information, automotive and industrial security profiles as specialist candidates.

Sources: [PPC legal material](https://www.ppc.go.jp/personalinfo/legal/),
[METI cybersecurity](https://www.meti.go.jp/english/policy/safety_security/cybersecurity/index.html),
[ISMAP overview](https://www.ismap.go.jp/csm?id=kb_article_view&sysparm_article=KB0010301).
JIS/PrivacyMark/FISC and medical profiles need separate owner-source validation.

## 10. Australia

- A: Privacy Act/APP readiness and breach-notification obligations after applicability review.
- A: Essential Eight introductory maturity profile; B: higher maturity profiles. Store the actual
  profile and assessment evidence, not a vague claim to cover all maturity levels.
- C: APRA CPS 234 and CPS 230, with the relevant guidance separately identified.
- D: ISM assessment profiles, IRAP assessment workflows and PSPF candidates.
- C/D: SOCI/critical-infrastructure obligations, healthcare/My Health Record and state/territory
  public-sector privacy/security overlays — specialist legal research required.

Coverage records: Commonwealth, NSW, Victoria, Queensland, Western Australia, South Australia,
Tasmania, ACT and Northern Territory; do not assume APPs replace state public-sector law.

Sources: [OAIC APPs](https://www.oaic.gov.au/privacy/australian-privacy-principles),
[ASD Essential Eight](https://www.cyber.gov.au/business-government/asds-cyber-security-frameworks/essential-eight),
[ISM/cloud assessment](https://www.cyber.gov.au/business-government/protecting-devices-systems/cloud-computing/cloud-assessment-and-authorisation),
[APRA CPS 234](https://www.apra.gov.au/standards/cps-234),
[APRA CPS 230](https://www.apra.gov.au/consultations/operational-risk-management).

## 11. Edge cases and specialist extension backlog

These are named discovery candidates, not legally validated deliverables. Assign C or D only after
scope/complexity review; basic management-system packs may fit B.

- Industrial/OT: ISA/IEC 62443 series, IEC 61508 functional-safety interfaces, energy/NERC CIP,
  transport, water and telecom profiles. Require site/system boundaries and technical testing.
- Automotive: TISAX/VDA ISA, ISO/SAE 21434, UNECE R155/R156, IATF 16949; separate cyber, software-
  update and quality obligations.
- Medical/life sciences: ISO 13485, ISO 14971, IEC 62304, IEC 81001-5-1, MDR/IVDR, FDA cybersecurity,
  21 CFR Part 11 and GxP. Electronic signatures/validation are new capabilities, not ordinary uploads.
- Aerospace/defense: AS9100, DO-326A-related cybersecurity and export-controlled evidence handling.
- Payment/finance: PCI secure software/PIN/P2PE, SWIFT CSP, regional AML/KYC and crypto-asset
  obligations such as MiCA. AML/KYC would need a distinct operational module and data design.
- Product/software supply chain: NIST SSDF, SLSA, OWASP ASVS/SAMM, SBOM/VEX and vulnerability
  disclosure records. A technical checklist is not proof a product passed technical verification.
- AI: ISO 42001, NIST AI RMF and jurisdiction-specific AI laws; no automatic permission to process
  customer content through LLMs.
- Accessibility: WCAG and relevant EN/Section 508 obligations, including tested product scope.
- Sustainability/food/other management systems: ISO 14001/45001/50001, ISO 22000/HACCP and other
  requested quality/environment/safety packs after specialist workflow design.
- International expansion candidates: UK/Swiss already above; Canada PIPEDA/Quebec Law 25,
  Brazil LGPD, Singapore PDPA/MTCS, South Korea PIPA/ISMS-P, India DPDP, New Zealand Privacy Act,
  South Africa POPIA and Israel privacy/security. These extend beyond the specifically requested
  regions and remain optional discovery backlog, with current official sources still required.
- Sensitive edge cases: children, employee monitoring, biometrics, health/genetic data, cross-border
  investigations, legal holds, processor/subprocessor chains, government classified data and
  overlapping jurisdiction duties. Applicability can block a deployment regardless of tier.

Reference for medical/industrial standard relationships:
[IEC preview](https://webstore.iec.ch/en/iec_catalog/product/preview/?id=L3B1Yi9wZGYvcHJldmlldy9pbmZvX2llYzgxMDAxLTUtMXtlZDEuMH1iLnBkZg%3D%3D).
All other candidate standards in this section require their own verified owner/source before release.

## 12. Optional product modules

Two user-requested product families; six additional proposals for discussion. These are business
modules, not eight new mandatory microservices. All require explicit entitlements and export,
retention, audit and authorization integration.

1. **Whistleblower portal and case management — requested.** Separate app/DB/storage/keys/workers;
   anonymous mailbox, safe attachments, handlers/recusal, jurisdiction timers, restricted export and
   retention. Available independently of framework tier when licensed and released. Existing V4
   privacy requirements continue to apply in full.
2. **LMS / training and awareness — requested.** Reuse the existing separate LMS. Proposed scope:
   courses, learning UX, quizzes/SCORM and completion records; verify its actual capabilities before
   promising these features. Tier A retains the integration interface and
   training-evidence records already promised; optional LMS access/content is licensed separately.
   If the intention is to charge for the connector itself, that remains a separate packaging decision.
3. **Privacy operations — proposal.** DSAR intake, identity verification, consent/processing/DPIA/
   transfer workflows and deadlines. Base privacy packs retain manual evidence workflows.
4. **Trust center and questionnaires — proposal.** Controlled document sharing, NDA/access expiry,
   questionnaire library and reviewed answers. Base public profile remains in Tier A.
5. **Evidence connectors — proposal.** Cloud, identity, repository, ticketing and endpoint read-only
   collection; scoped service accounts, signed provenance, synchronization/error records.
6. **Advanced third-party assurance — proposal.** Supplier portal, questionnaires, recurring
   assessments and supplier evidence sharing. Base vendor register remains in Tier A.
7. **Incident and resilience operations — proposal.** Incident casework, jurisdiction deadline
   calculation, recovery exercises and specialist reports. Conformly's own secure operations and
   base customer finding/task workflows are never sold as optional platform security.
8. **Managed assessment service — proposal.** Human assessor engagements, scheduling and independent
   review. This is a service offering using the existing review boundary, not a substitute for an
   accredited external audit or an automated certificate sale.

Each proposed module needs its own lifecycle/state transitions, role matrix, data classification,
tenant boundary, evidence model, API/UI contracts, export/deletion support and release tests before
coding. Whistleblower alone already has a mandated fully separate data plane.

## 13. What a released framework pack must contain

1. Stable framework ID, owner, title, type, version, source language, jurisdiction and sector.
2. Source links, retrieval date, effective/transition/retirement dates, license and redistribution
   permissions. Do not copy paid ISO, AICPA, HITRUST or vendor materials without appropriate rights.
3. Applicability questionnaire: entity role, sector, size where relevant, location, data subjects,
   products, data classes and contractual obligations; record reasons for exclusions.
4. Full applicable requirements with source references, controls, evidence requests, owners,
   cadence, policy references and legal notification/escalation tasks where relevant.
5. Versioned mappings: equivalent, partial or supporting relationships; never assume one framework
   proves another. Shared evidence must still be valid for each scope and observation period.
6. Deterministic rules, human review steps, exceptions, findings and remediation states.
7. Reports that distinguish readiness from certification, attestation, registration and authorization.
8. Framework-version impact analysis, reviewed adoption and immutable historical assessments.
9. Positive/negative applicability tests, authorization/isolation tests, expected evidence/report
   examples, localization review and independent content approval.
10. Published pack status: DISCOVERED → SOURCE_VERIFIED → CONTENT_DRAFT → LEGAL_REVIEW →
    INDEPENDENT_APPROVAL → TESTED → RELEASED → SUPERSEDED/RETIRED.

Only RELEASED packs count toward supported-framework claims. All entries in this file start as
DISCOVERED or SOURCE_VERIFIED; none becomes RELEASED merely because it is listed.

## 14. Implementation handoff and rollout

- Initial Tier A launch packs have complete technical specifications, declarative applicability rules, structured evidence collection requests, and acceptance tests (`iso-27001`, `gdpr-bdsg`, `nist-csf`, `cis-controls-ig1`, `mvsp`). As recorded in the canonical manifest (`apps/api/src/conformly/frameworks/manifest.json`), their content status is **DRAFT_REVISION_UNDERWAY** / **CONTENT_REVIEW_PENDING**, awaiting independent human second-person approval and legal/compliance review prior to production release. See `docs/FRAMEWORK_PACKS_TIER_A.md` and ADR D-058.
- Tier B (SOC 2, ISO 27701, ISO 22301), Tier C (NIS2, DORA, EU AI Act), and Tier D (FedRAMP, CMMC) remain the active planning backlog.
- Their entitlement implementation accepts configurable pack IDs, versions and module IDs without hard-coded package-name branches.
- Implement any missing Tier A workflow needed by those packs (for example, applicability records and privacy evidence). Content release and application release must both pass.
- Expand regional A packs and B assurance packs next; C regulated and D specialist packs follow only when their data, workflow, assessor and hosting dependencies are met.
- Sequence add-ons independently. LMS integration remains in the Tier A finish line; building a new LMS is excluded. Whistleblower remains a separate later release.
- Track progress separately for platform capabilities, individual released packs, jurisdiction overlays and add-ons. There is no honest single "global 100%" until a finite release catalog is agreed, every chosen pack is released, and all deployment gates pass.
