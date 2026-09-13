# Copy-ready AI task: complete Module A framework content for beta

## Objective and authority

Work in the Conformly repository. Complete the framework-content and supporting workflow gaps
needed for a defensible Module A beta. Implement and verify the software, produce reviewable
content, and assemble release evidence. Do not equate code completion with human approval.

Read AGENTS.md, docs/PRODUCT_SOURCE_OF_TRUTH.md, and the remaining docs before architectural
decisions. Inspect the current worktree first; preserve other agents' work. Existing completion
labels are claims to verify, not evidence. Do not alter applied migrations or rewrite historical
assessments. Do not change Trello, deploy to production, purchase licenses, or manufacture product
decisions without authorization. Record technical conflicts in docs/DECISIONS.md.

The existing LMS is external and independently deployable. Reuse its connector; do not build or
merge an LMS. Modules B–D, whistleblower and additional add-ons are outside this coding task.
Keep all existing security, tenancy, six-role, encryption, retention and deterministic-workflow
requirements. A beta is not permission to weaken security or issue misleading readiness results.

## Starting evidence — recheck before editing

The inspected packs_data.py contains five packs: ISO 27001 (28 entries), GDPR/BDSG (15), NIST CSF
(13), CIS IG1 (10), MVSP (8). These counts describe current data, not complete source coverage.
Five existing pack tests pass but primarily test seeding, fields, immutability and selected
applicability cases. They do not establish exhaustive content correctness.

seed_packs.py currently creates author and approver identities, constructs privileged principals,
records static legal-review notes, approves and releases content automatically. Different UUIDs
are not proof of independent human review. applicability.py uses identifier/title matching and
defaults that can exclude obligations without adequate evidence. Treat these as audit targets.

Important starting files:

- apps/api/src/conformly/frameworks/{packs_data,seed_packs,applicability,models,service}.py
- apps/api/src/conformly/api/frameworks.py
- apps/api/tests/test_tier_a_framework_packs.py
- apps/api/src/conformly/preaudit/ and profiles/
- apps/api/src/conformly/exports/ and retention/
- apps/api/src/conformly/lms/ and integrations/
- apps/web/src/components/FrameworkCatalog.tsx and ComplianceWorkspace.tsx
- docs/FRAMEWORK_PACKS_TIER_A.md and GLOBAL_FRAMEWORK_CATALOG.md

## Step 1 — Establish the exact beta release inventory

Create docs/MODULE_A_BETA_SCOPE.md and a machine-readable release manifest in the repository's
appropriate content/config location. Reconcile the current five-pack launch list with the product
source of truth and the broader global catalog. Do not silently reduce “all Module A” to five packs.

Give EVERY A-labelled candidate a disposition: REQUIRED_BETA, LATER_A, or OWNER_DECISION_REQUIRED.
Include ISO 9001, CISA CPG, national EU privacy overlays, US state/privacy candidates, Arab-country
privacy candidates, Japan APPI and Australia privacy/Essential Eight profiles. Resolve ambiguous
A/B entries explicitly. Preserve country-level coverage records; do not substitute one law for
all countries. Group shared standards once and link jurisdiction overlays.

Working implementation batch: complete the five already coded packs. ISO 9001 and other A entries
must not disappear; request explicit scope confirmation before treating them as either required
beta or deferred. Continue shared engineering and verified five-pack content while that choice is
pending. If the owner chooses all global A packs for beta, each becomes subject to every gate below;
do not declare beta ready with unresolved required jurisdictions.

Manifest fields: pack ID, source edition, Conformly content revision, jurisdiction, declared scope,
profile, required-for-beta status, decision provenance, content state, owner, blockers and evidence.
Exit: a finite reviewed beta inventory, with no unnamed or silently omitted A requirements.

## Step 2 — Remove simulated release approval

Separate content import from authenticated human review and release. Normal import creates drafts
only and must not create/elevate users, assert MFA, fabricate review notes or auto-release.
Synthetic actors/approved fixtures belong exclusively to guarded tests or development fixtures.

Preserve existing service interfaces where safe. Bind reviews to an exact immutable content digest,
revision, declared scope and source manifest. Store real reviewer identity, timestamp, decision,
evidence reference and rationale. Enforce the documented independent author/approver boundary and
legal/compliance review requirements server-side. Content edits invalidate pending approvals.
Unresolved source, licensing, coverage, applicability or critical test blockers prevent release.

Inventory any previously auto-released versions and their adoptions/results. Implement a reviewed
quarantine/retirement and superseding-version path; preserve historical records and audit evidence.
Do not silently overwrite immutable releases, delete user data or automatically revoke customer
results without the authorized lifecycle workflow. Prevent new misleading issuance from affected
versions; surface existing affected results for human disposition.
Exit tests: one actor cannot self-approve; imports cannot manufacture release approval; stale
approvals and unauthorized direct API calls fail; historical assessments remain readable.

## Step 3 — Build a traceable content schema and coverage ledger

Reuse existing models where possible; add explicit migrations for genuine missing concepts.
Separate source requirements, implementation controls and evidence requests with versioned mappings.
Each source clause/subclause/safeguard/outcome needs an explicit disposition, not just a domain heading.

Track source authority/URL, retrieval date, edition/amendment, language, effective dates, content
rights and permitted use. Source text, Conformly-authored guidance and suggested operating targets
must be distinguishable. Do not present suggested training percentages, timeouts or review cadences
as statutory/standard requirements without a verified source.

Each requirement needs a stable source reference, requirement type, applicability conditions,
mapped controls, evidence specifications, assessment procedure, owner role, review cadence where
supported, findings/remediation mapping and reporting limitations. Evidence specifications must
be structured data, not merely bullets hidden in a guidance string. Include original-file links,
observation period, validity/expiry, review and confidentiality requirements.

Coverage ledger dispositions: IMPLEMENTED, NOT_CUSTOMER_OBLIGATION, PROFILE_EXCLUSION or BLOCKED,
with source-backed rationale and reviewer. Tenant-specific non-applicability is separate from
catalog coverage. Never hide a missing requirement by calling it non-applicable globally.
Exit: every source item is accounted for; no duplicates, orphan mappings or unexplained gaps.

## Step 4 — Complete source-verified framework content

Consult current official publishers, not vendor marketing or model memory. Retrieve permitted
sources and build an independently sourced expected-reference inventory before expanding controls.
Store enough provenance for a reviewer to reproduce coverage. A number of entries alone is not a
completeness test: combined controls must explicitly map to every covered source requirement.

Official starting points (verify exact edition and rights):

- ISO: https://www.iso.org/standard/27001 and https://www.iso.org/standards.html
- GDPR: https://eur-lex.europa.eu/eli/reg/2016/679/oj
- BDSG: https://www.gesetze-im-internet.de/bdsg_2018/
- NIST: https://www.nist.gov/publications/nist-cybersecurity-framework-csf-20
- CIS: https://www.cisecurity.org/controls/implementation-groups
- MVSP: https://mvsp.dev/

Do not copy restricted standards or infer commercial reuse permission from public availability,
paraphrasing, or a “fair use” label. If authorized source material is missing, implement the schema,
loader and tests but mark content blocked and request the material. No invented legal approval.

### 4A. ISO/IEC 27001

Account for all management-system requirements and Annex A reference controls for the selected
edition/amendments. Support risk-based selection, Statement of Applicability, justified exclusions,
implementation status and evidence. Cover governance, risk assessment/treatment, competence,
document control, operations, performance evaluation, internal audit, management review and
improvement. Verify numbering/titles and do not substitute an abbreviated cyber checklist for ISMS
readiness. Annex A reference controls and mandatory management-system clauses are not interchangeable.

### 4B. GDPR and German BDSG

Use a legally reviewed applicability inventory for controller, processor and joint-controller roles.
Account for rights, transparency, lawful basis, sensitive/criminal-offence data, records, contracts,
security, breach evaluation/notification, DPIAs, DPO requirements, transfers, employment processing
and relevant German supplements. Account for provisions aimed at authorities separately rather
than inventing customer tasks for every article. Do not assert complete privacy coverage from
the current 15 entries. Version legal sources independently from arbitrary pack labels like “2024”.

### 4C. NIST CSF 2.0

Import the complete official Core reference inventory, with every function, category and
subcategory represented or explicitly mapped. Support current/target organizational profiles,
scope, gaps, evidence and improvements. Keep NIST implementation tiers separate from Conformly
packages. Do not invent a NIST certification or a mandatory universal maturity pass threshold.

### 4D. CIS IG1

Confirm edition/profile and commercial content rights. Cover every official IG1 safeguard rather
than ten representative domains. Retain parent-control mappings and evidence criteria. Test the
expected safeguard identifier set from an independent official reference inventory, not an
expected count derived from the same pack list. IG2/IG3 remain outside this profile.

### 4E. MVSP

Verify the actual publisher release/version, full checklist, numbering and licensing/attribution.
Cover each applicable checklist requirement and its evidence. Do not preserve a made-up version
or numbering merely because the database already contains it. Map legacy IDs through a reviewed
migration and content revision. Verify inherited/cloud responsibilities rather than auto-excluding.

### 4F. Additional REQUIRED_BETA A packs

Apply the same source inventory, rights, structured content, applicability, workflow, independent
review and test gates to ISO 9001 and every regional pack selected in Step 1. ISO 9001 requires
quality-management process/customer/operational workflows, not relabelled security controls.
No country is “supported” until its scoped overlay is source-verified and released.
Exit: complete reviewable drafts for every required pack; human review still pending where needed.

## Step 5 — Repair applicability and scope decisions

Replace title/description substring heuristics with versioned declarative rules bound to stable
requirement IDs. Persist profile answers, sources, evaluator version, outcome and rationale.
Unknown answers must remain unknown/review-required, never default to exempt. Require authorized
review and auditable rationale for exclusions; profile changes trigger impact review.

Regression cases to verify with authoritative material and a qualified reviewer:

- DPO obligations cannot be decided from total employee count alone; collect the actual relevant
  processing facts and additional appointment triggers instead of assuming “under 20 = exempt”.
- Remote work does not automatically remove all physical safeguards; outsourced infrastructure
  does not erase inherited-control assurance obligations.
- Suppliers are not synonymous with personal-data subprocessors.
- EEA storage alone does not settle remote-access, onward-transfer and transfer-mechanism facts.
- No reported special-category processing must not override contradictory evidence or missing data.

Tests: applicable, justified exclusion, unknown, contradictory answers, role differences, threshold
boundaries, changes of scope, overrides, tenant isolation and restricted-role denial.

## Step 6 — Connect content to the full Module A workflow

Implement only gaps found in the existing framework adoption -> scope/applicability -> control
ownership -> evidence/policies/registers/training -> assessment/findings -> remediation/recheck ->
independent review -> tenant approval -> readiness report workflow. Reuse completed modules.

Generate structured evidence requests/tasks from adopted content idempotently. Missing, expired,
unreviewed and rejected evidence must affect readiness predictably. Reuse evidence only when scope,
period and mapped requirement criteria match; partial mappings do not imply full satisfaction.
Freeze content revision, applicability, evidence versions, findings, reviewers and rule versions in
issued results. Content upgrades require impact analysis and explicit adoption.

Include new records in tenant export, retention/deletion, audit and legal-hold handling. Preserve
canonical content while deleting tenant-specific content according to its lifecycle. Verify jobs,
caches, webhooks, downloads and search respect roles, organization scope and tenant isolation.

Exit: one full realistic journey per required pack works, including negative issuance cases.

## Step 7 — Finish framework UI and truthful reporting

Show pack edition/content revision, jurisdiction/profile, release state, declared scope and
limitations. Hide or disable adoption/issuance for blocked packs server-side as well as in the UI.
Provide source references, why evidence is requested, applicability explanations and exclusion
review, coverage gaps, missing evidence, responsible owners and next actions.

Distinguish whole-framework readiness, a limited profile and incomplete assessment. Never show
100% readiness from only the supplied subset without prominently delimiting that subset. Draft
packs cannot issue production verification/public badges. Keep reports private until authorized
publication; exclude private evidence, findings and employee data from public projections.
Apply existing DE/EN/FR/NL/ES localization and keyboard/accessibility patterns to all new UI.
Exit: reports and screens accurately describe scope, and sensitive-data negative tests pass.

## Step 8 — Replace shallow completeness tests with independent acceptance tests

Maintain versioned expected source inventories separately from generated pack definitions.
Test reference-set coverage, duplicates, required mappings, valid source editions, metadata,
structured evidence, applicability fixtures, licensing/review blockers and stale approval rejection.
Test seed/import idempotency without fake approval; test partial import and retry recovery.

Add realistic pass/fail/incomplete/review-required assessment fixtures for every required pack.
Prove one missing mandatory applicable requirement blocks an otherwise complete result. Test
source-version changes, control supersession, rollback compatibility and old-result reproducibility.
Run DB migrations and tenant/RLS tests against real PostgreSQL, not only SQLite. Test real service
integration separately from mocks. Record skipped tests as unverified gates, never passing evidence.

Run backend lint/type-check/tests, frontend lint/type-check/tests/build, migrations, browser journeys,
accessibility and the relevant security regression suites using the repo's actual commands.
Exit: no unresolved beta-blocking failure; reproducible command logs tied to a revision.

## Step 9 — Reconcile documentation and assemble the beta evidence pack

Update FRAMEWORK_PACKS_TIER_A.md, GLOBAL_FRAMEWORK_CATALOG.md, both build plans and
CODEX_START_HERE.md with verified statuses and links to evidence. Preserve the historical Trello
snapshot; do not claim synchronization or human approval that did not occur. Resolve contradictory
“all released” statements and keep broader A candidates explicitly visible.

Create docs/MODULE_A_BETA_RELEASE_EVIDENCE.md covering: frozen source revision; finite beta manifest;
coverage ledger; source/rights evidence; genuine review decisions; migration/RLS/security results;
per-pack journeys; report/public-projection checks; known risks with owners; deployment validation
and real backup/recovery evidence. Verify existing platform gates rather than reimplementing them.
Preserve the documented RPO <=15 minutes and RTO <=4 hours; an export ZIP test is not proof of full
infrastructure recovery. Sensitive beta data requires the documented independent security review.

## Step 10 — Apply the release decision honestly

Use separate statuses:

- ENGINEERING_COMPLETE: code and technical tests pass for the defined scope.
- CONTENT_REVIEW_PENDING: draft coverage exists but source/rights/human reviews are incomplete.
- BETA_READY: every REQUIRED_BETA pack and platform release gate passes with genuine evidence and
  explicit Product Owner release approval.
- BLOCKED: list exact missing material, decision, test or approval and its responsible owner.

No AI may impersonate a reviewer, self-certify legal sufficiency or mark BETA_READY merely to
finish this task. Continue independent safe work when one pack is blocked, but do not drop that pack
from the required inventory. Do not start B–D or add-on implementation to avoid unfinished A work.

## Required handoff after each step

Report: changes and file paths; requirements addressed; verification commands/results; remaining
gaps; external decisions/material needed; and the exact next step. Keep a checked execution log
linked to evidence. Final handoff must list every required pack individually with coverage,
engineering, rights, human-review and release status. No unsupported overall percentage.
