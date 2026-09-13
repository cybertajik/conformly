# Conformly — Complete Product Source of Truth

## Product Owner expansion request — 2026-09-13

Read [Global framework catalog and A–D expansion plan](GLOBAL_FRAMEWORK_CATALOG.md) alongside this
document when planning framework packs, tiers, or add-ons. The Product Owner has requested coverage
across the EU, USA, Arab countries, China, Japan, Australia, and specialist cases, with basic packs
in A, more advanced packs in B–D, and optional products including whistleblower and LMS.

That expansion direction is authorized by the current request. The catalog's specific tier
allocations, candidate launch packs, and additional add-on proposals are **DRAFT**, not locked
requirements. They have not been synchronized to or approved on Trello DEU. This request permits
expansion planning; it does not activate B–D, change the existing Tier A release gates, remove its
LMS evidence integration, or authorize incompatible hosting arrangements. Reconcile and approve
specific changes on DEU before implementing changed product packaging.

Sections below retain the V4 snapshot and its original authority/provenance. Statements that no
further tiers/add-ons are defined describe that snapshot, not a prohibition on the newly requested
planning. The catalog records implementation items 1–4 as **in progress, reported by the Product
Owner**; this planning update does not certify their completion.

## 1. Authority and Coverage

This is the repository execution mirror of the complete
[Conformly DEU Trello board](https://trello.com/b/nNnF3o0O/conformly-deu), Version 4.0.

- Canonical product authority: Conformly DEU Trello.
- Snapshot: 2026-09-12; latest included activity: 2026-09-06.
- Coverage: all 30 active cards; they contain no additional comments or checklists.
- Purpose: define the planned product from product intent through architecture, delivery, release,
  and operations so it can be built from 0% to 100%.

Precedence: a newer explicit Product Owner decision on DEU comes first, then this required mirror,
then `AGENTS.md`, specifications, plans, tickets, tests, and code. If they conflict, stop product
implementation and reconcile them. ENG/RUS translations do not create product decisions. Existing
code and checked boxes are implementation evidence, not product authority.

Status language: **LOCKED** requires Product Owner approval to change; **BASELINE** requires an ADR;
**OPEN** must be decided before its gate; **LATER** is deliberately deferred; **MUST** is a release
or security requirement.

OPEN: production provider, exact German regions/subprocessors, final cost and network topology.
PARKED: prices, public plan names, payments, subscriptions, invoices, discounts, service credits,
and contractual SLA calculations.

## 2. Product and Customer Value

Conformly is a security-oriented multi-tenant compliance SaaS for Germany and the EU. The first
paid MVP is a human-reviewed pre-audit/readiness platform—not an accredited certification body,
regulator, law firm, compliance guarantee, generic dashboard, or whistleblower-only portal.

Customers buy: Tier A German/EU framework access; scope/applicability; versioned frameworks and
controls; evidence collection/review; policy lifecycle; risk, asset, and vendor registers; findings,
remediation and tasks; pre-audit and recheck; LMS completion evidence; Readiness Verification and
reports; optional public profile; audit, exports, API/webhook foundations, and deterministic jobs.

Lifecycle: Pre-audit → gaps → remediation → Readiness Verification → continuous compliance →
renewal/reassessment. Continuous value comes from expiring evidence, policy reviews, training,
vendor/risk changes, incidents, recurring controls, and audit history—not artificial lock-in.

The dashboard must answer: Are we ready? What changed? What expires or needs action next? Who owns
it? What can we prove to an auditor/customer?

Never claim accredited certification, regulatory approval, legal advice, guaranteed compliance,
autonomous AI judgment, or “quantum-proof” cryptography.

## 3. Tiers, Entitlements, and Add-ons

### Tier A / Tier 1

Tier A is the only active MVP capability set and means the complete Core scope in this document.
It is not merely a role or support label.

### Tier B–D

B, C, and D are reserved neutral codes. Their names, modules, framework access, limits, prices,
support, and contracts are not approved. Do not invent them, map them to Starter/Compliance/Pro/
Enterprise, publish them, or use imagined packaging in architecture.

### Entitlement foundation—build now

Implement data-driven module activation, framework-pack access, quantity/storage limits, feature
configuration, lifecycle/effective dates, audited changes, and server-side enforcement. Never use
hard-coded plan-name branches or put prices in domain logic. Hidden UI is not authorization.

Tenant/RLS isolation, required encryption, authentication/authorization, audit, safe logging,
export/deletion, backup, and recovery are mandatory in every tier—never premium.

The only specifically approved separate add-on is the later whistleblower system. Do not invent
other add-ons. The exact Tier A framework-pack catalog is still an explicit Product Owner decision.

## 4. Complete Tier A Module Catalog

Platform: tenants, organizations, legal entities, business units, locations, memberships, six
roles/scopes, OIDC/SAML, MFA, authorization/entitlements, notifications, append-only audit, API,
webhooks, dashboard, exports, retention, and deletion.

Compliance: canonical/versioned frameworks, requirements, controls, mappings, applicability,
assessments, encrypted evidence vault, findings, remediation, tasks, cross-framework mappings, and
reproducible history.

Operational: policy editor/templates/uploads/versions/approvals; risk/treatments; asset register;
third-party/vendor register; LMS assignments/completions; expiry/review reminders; recurring
deterministic checks.

Assurance: human pre-audit, recheck, independent review, Readiness Verification, reports, audit
manifest, 12-month lifecycle, suspension/revocation/expiry, and optional public projection.

LATER: custom roles, workflow builder, SCIM, multiple IdPs beyond the MVP broker, native apps,
content benchmarking, tenant-content AI/LLM analysis, autonomous decisions, dedicated deployments,
billing, and contractual SLA logic.

## 5. Architecture and Service Boundaries

System path: User → Edge/TLS/WAF → Next.js Web → FastAPI Modular Core → PostgreSQL/RLS,
Redis/Celery, S3 adapter, and KMS adapter. Keycloak is the identity boundary. Never trust a tenant
identifier supplied arbitrarily by a browser.

LOCKED: Core is one deployable modular monolith with owned modules for tenant/organization/identity;
authz/entitlements; frameworks/controls; evidence/policies/risks/assets/vendors; assessments/
findings/remediation; readiness/public projection; audit/notifications/API/webhooks. Modules use
explicit services, not arbitrary table access. Extract only for measurable security, legal, scale,
deployment, or ownership reasons.

Core owns compliance data. The existing LMS remains independently deployable with no shared DB.
The later whistleblower add-on owns its own app, DB, storage, keys, workers, authorization, cases,
mailbox, messages, attachments, assignments, and restricted audit.

## 6. Organization, Identity, Roles, and Isolation

A person may share one identity across tenants, but every membership has independent roles/scopes.
A tenant contains legal entities, business units, locations, memberships, and explicit resource
scopes. Effective access is fixed role plus legal-entity/business-unit/resource scope.

LOCKED roles: (1) Tenant Owner, (2) Tenant Administrator, (3) Compliance Manager, (4) Control
Owner, (5) Reviewer, (6) Employee. External Advisor is a time-limited account classification with
one of these roles, not a seventh role. Custom roles are not MVP.

Administrator manages users/SSO/settings but does not automatically see compliance content.
Reviewer sees assigned material and cannot alone issue verification. Assessor access is time-limited
and scoped: read/comment/create findings and reports, never modify customer evidence. Staff have no
standing access—only expiring engagement or audited break glass.

Identity: one Keycloak customer realm; memberships/roles in Conformly; one OIDC/SAML broker per
tenant; separate workforce realm; MFA mandatory for privileged roles and optionally all users.

Request path: session → Keycloak identity → validated membership/tenant selection → FastAPI authz
→ PostgreSQL RLS → domain service. Require `tenant_id` on every tenant record/job; runtime DB role
cannot bypass RLS; tenant-safe cache/queue/search/metric/idempotency/object keys; authorized
short-lived file URLs; negative cross-tenant tests for reads/writes/deletes/IDs/filters/exports/jobs/
caches/webhooks/objects; safe failure for missing/forged context.

## 7. Core Data Model and Framework Rules

Organization: Tenant → LegalEntity → BusinessUnit/Location → User/Membership/Role/Scope.

Compliance: Framework → immutable FrameworkVersion → Requirement ↔ Control → Assessment → Evidence
→ Finding → Remediation → Risk.

Registers/entities: Asset; ThirdParty/Vendor; Risk/Treatment; Policy/PolicyVersion;
TrainingAssignment/TrainingCompletion; findings/tasks/state; Plan/Entitlement/framework-pack/limits.

Tenants cannot change canonical frameworks. Overlays, tenant controls, and mappings stay separate.
New canonical versions require legal/compliance review plus independent approval. Give tenants
impact analysis before controlled adoption; never auto-adopt; preserve reproducible history.

Evidence versions are immutable with SHA-256, provenance/time, MIME/size, malware scan, key and
cipher-format metadata, expiry/review, retention/legal hold, and reusable control mappings.
Exports include machine-readable data, original files, readable reports, and verifiable audit
manifest. Public profiles read a separate publication projection, never live evidence.

## 8. Onboarding and Daily UX

Onboarding: create tenant → define entities/units/locations → invite Owner/Admin → roles/scopes →
local auth or OIDC/SAML broker → choose framework/version/scope → applicability → create controls/
owners/deadlines → import/create policies/evidence → fill asset/vendor/risk registers → connect LMS
→ baseline assessment → dashboard/remediation plan. No price/payment choice in current Core coding.

Home view: readiness, open findings, overdue tasks, expiring evidence/policies, training, risk/vendor
changes, and next reassessment action.

UX MUST: wizard, plain language, “why required?”, saved progress, reusable evidence, safe empty/
loading/error states, responsive WCAG 2.2 AA, DE/EN/FR/NL/ES, understandable crypto UX. Native apps
are later.

## 9. Pre-Audit and Readiness Verification

LOCKED flow: freeze framework/version/scope → applicability/controls → evidence requests → customer
evidence → deterministic completeness/gap checks → scoped human assessor → findings/severity/
remediation → recheck → independent second review → explicit tenant approval → result/report.

Versioned deterministic state machines use configurable assignees/deadlines. No workflow builder.
An issued result freezes framework version, scope, controls, evidence references, reviewers,
decisions, timestamps, findings, and limitations. No LLM receives tenant content or concludes
compliance.

Approved name: Conformly Readiness Verification / Conformly Readiness Verified. Valid 12 months;
allow correction, suspension, revocation, expiry, supersession. Material scope/control change
suspends affected verification until targeted reassessment.

Public projection may show organization, framework version, scope, issue/expiry, status, and opaque
verification ID only. External certificates show issuer/title/scope/validity and status: self-
declared, externally issued, checked by Conformly, or Conformly Readiness Result. Use non-guessable
IDs, rate limits, safe caches, and visible revoked/expired/superseded states. Never expose private
evidence, findings, scores, employees, or internal IDs.

## 10. LMS Integration

Do not rebuild/merge the LMS. Conformly owns requirement, tenant/user/group assignment, due date,
control mapping, and normalized completion evidence. LMS owns courses, SCORM/runtime, lessons,
quizzes, learning UX, and completion internals.

Flow: assignment → API/SSO → LMS → signed completion webhook → verify → TrainingCompletion evidence
→ mapped control update. Require identity/tenant mapping, OIDC/SSO where possible, signed replay-
protected callbacks, idempotency, course/version IDs, audited assignment changes, and never trust
a browser redirect saying `completed=true`.

## 11. Whistleblower Add-on — Complete Later Scope

This product is planned but is a separate LATER add-on, not Tier A Core. Existing Core code does
not override this. Keep it unshipped/disabled until separate architecture and release approval.

Reporter flow: dedicated tenant URL → anonymous/identified choice → report and attachments →
client/server privacy checks → encrypt → random case ID plus separate secret credential → receipt/
secure mailbox → account-free return → handler reply → reporter additions → status/closure.

Anonymous use requires no account, email, or identity. Store protected verifier material, never the
plaintext secret. Email only that attention is needed—never report content. Configure legal timers
by jurisdiction; do not hard-code one regime.

Privacy MUST: separate app/DB/storage/keys/workers/authz; no ad/behavior analytics; minimize or
suppress IP/user-agent retention where feasible; no text/tokens/names in logs; strip risky EXIF/
document metadata where appropriate; randomize stored names/keys; application-encrypt messages and
attachments; explicit handlers; no content in email/monitoring/traces/audit; no secret logging;
abuse controls without identity tracking; no plaintext search index; re-identification test before
production and after logging/analytics changes.

Handler flow: new → triage/conflict check → assignments → acknowledge/secure message → investigate
(internal notes, evidence, tasks, state) → outcome/action → reporter feedback → closure/retention.
Data includes case, messages, attachments, internal notes, history, assignments, deadlines, actions,
outcomes, and access audit. Internal notes never reach reporters; reporter messages require explicit
marking. Audit assignments/exports; support export watermark/logging; allow recusal; respect legal
hold. Configurable example states: Received → Triage → Under Review → Action Required → Closed.

## 12. Security, Encryption, and Storage

Layers: Edge/TLS/WAF → Keycloak MFA/SSO → membership/role/scope → deny-by-default FastAPI authz and
entitlement → PostgreSQL RLS → app envelope encryption → disk/storage encryption → encrypted
immutable backups → append-only hash-chained audit.

Classifications: Public, Internal, Confidential, Restricted, plus optional tags. Whistleblower-
restricted content exists only in the add-on. Cross-tenant analytics/logs use content-free metadata;
no tenant content enters benchmarks, LLMs, logs, traces, or training.

Encrypt every file, every Restricted field, and selected Confidential fields. Flow: authorized
plaintext → random DEK → AES-256-GCM → ciphertext in DB/S3 → DEK wrapped by tenant key → record key
version/algorithm/format. Use tenant keys and rotatable file/secret keys; storage never gets reusable
plaintext tenant keys. No browser E2EE in Core. Version crypto formats; only adopt mature reviewed
hybrid/PQ standards. Delete ciphertext, wrapped keys, and metadata under retention/legal hold.

MUST: threat models, SAST, dependency/container/IaC/secrets scans, SBOM, negative isolation tests,
malware quarantine, restore tests, and external security review before sensitive production.

## 13. Locked Software and API Baseline

Web: Next.js/React/TypeScript; responsive WCAG 2.2 AA; DE/EN/FR/NL/ES. API: Python/FastAPI/
SQLAlchemy/Alembic/Pydantic. Data/jobs: PostgreSQL mandatory RLS, Redis, Celery, Transactional
Outbox. Identity: Keycloak. Storage/keys: provider-neutral S3 and KMS/secrets adapters; managed KMS
or OpenBao is deployment choice. Encryption: AES-256-GCM. Edge/ops: containers, TLS/WAF/rate
limits, OpenTelemetry, scrubbed logs/metrics/traces/alerts. Local containers also include mail
catcher and malware scanner. Production data residency is Germany-only; provider is OPEN.

Current React/Vite architecture has been formally approved via ADR D-056 as the production static SPA baseline served via Nginx (reconciling the previous Next.js deviation).

API path: client/integration → HTTPS plus OIDC/service auth → edge → FastAPI → authz, tenant, and
entitlement → domain service → DB/queue/object. Public APIs use `/api/v1`, explicit versions, opaque
IDs, pagination, structured errors, and create idempotency keys where needed.

Event path: domain event → outbox → Celery → signed webhook. Require signature/timestamp, replay
protection, exponential retry, dead-letter visibility, tenant secrets, sender/receiver idempotency,
and no excess personal data. Events include `assessment.completed`, `finding.created`,
`certificate.issued`, `certificate.revoked`, `evidence.expiring`, `training.completed`. Add-on events
use a separate restricted path and never broadcast reports.

## 14. Hardware, Backup, and Disaster Recovery

Expected start: 2–3 companies, about 1,000 combined users, low concurrency, far below 1–2 TB.
Pilot EU server: 8 vCPU, 32 GB RAM, 500+ GB encrypted NVMe and external encrypted backups—not final
resilience. Early production: app/worker 8 vCPU, 16–32 GB RAM, 200+ GB NVMe; DB 8 vCPU, 32 GB RAM,
fast encrypted NVMe; keys 2–4 vCPU, 4–8 GB RAM, isolated network/disk; object storage about 2 TB and
independently scalable. Separate app/DB/key failure boundaries once real data begins. Scale on
resource pressure, latency, queue depth, growth, and backup window.

The 24-TB home Synology may, after approval, be one additional encrypted German off-site copy; it
is never primary storage or the only backup.

Germany-only 3-2-1-1-0: at least 3 copies, 2 systems/media, 1 separate failure domain, 1 immutable/
offline copy, 0 unverified errors. PostgreSQL PITR supports RPO ≤15 minutes, synchronous multi-zone
HA and asynchronous German DR. Objects are versioned/encrypted with an immutable copy. Separate
backup credentials/key recovery. Chunking/erasure coding is resilience, not confidentiality.

RTO ≤4 hours. Restore order: network/edge → identity/keys → PostgreSQL → objects → Core/workers →
integrity/isolation → integrations → traffic. Quarterly and material-change restores prove DB/
object/identity/key coherence, authorized decryption, tenant isolation, audit/verification state,
no duplicate jobs/webhooks, and measured corrective actions. These are engineering objectives,
not contractual SLAs.

## 15. Core Delivery Plan — 0% to 100%

Percentages are tracking weights for Trello's locked sequence, not time estimates. Credit requires
the exit gate.

- **0–5% Foundation:** source governance, monorepo, ADRs, toolchains, CI/config/secrets, i18n, threat
  models.
- **5–12% Local platform:** PostgreSQL, Redis, S3 dev store, Keycloak, mail catcher, malware scanner,
  migrations, health/logging.
- **12–22% Tenant/identity/isolation:** entities, units, memberships, roles/scopes, MFA/SSO, RLS,
  tenant-safe jobs/caches/queues/storage/search/metrics/idempotency, negative tests.
- **22–28% Authz/entitlements:** deny-by-default capabilities; neutral plan/module/framework/limit/
  storage/feature data; audited backend enforcement; A active, B–D reserved.
- **28–34% Audit/outbox:** append-only hash-chained audit, immutable seal adapter, transactional
  outbox, idempotent retry/dead-letter workers.
- **34–40% Organization/scope:** full legal-entity/unit/location workflows, assignments, onboarding,
  daily workspace.
- **40–48% Frameworks/controls:** canonical/versioned content, overlays/custom controls/mappings,
  two-person release, impact analysis, controlled adoption, pack access.
- **48–55% Evidence:** encrypted immutable versions, malware quarantine, provenance/hash/expiry/
  retention/legal hold/review/reuse/download authorization.
- **55–62% Assessments/findings:** applicability, assignments, evidence requests, deterministic checks,
  findings/severity/remediation.
- **62–67% Tasks/notifications:** owners, dates, reminders, escalation, dashboard, privacy-safe jobs.
- **67–72% Policies:** editor/templates/uploads/versions/approvals/reviews/acknowledgements/mappings.
- **72–79% Risks/assets/vendors:** linked risk/treatment, asset, vendor, changes, recurring review.
- **79–84% Pre-audit/readiness/public:** human and second review, approval, frozen result/report/
  manifest, lifecycle, isolated publication.
- **84–88% LMS:** assignments, identity/tenant mapping, SSO/API, signed idempotent completion evidence.
- **88–92% API/webhooks:** stable v1 API, signed tenant webhooks, replay/retry/dead-letter operations.
- **92–95% Export/retention/deletion:** structured data, originals, reports, manifest, legal hold,
  deletion and backup lifecycle.
- **95–97% DR:** 3-2-1-1-0, PITR/HA/DR, immutable objects, separated keys, restore evidence.
- **97–99% Operations/deployment:** telemetry, alerts/runbooks, capacity/patching/rotation, controlled
  deploy/rollback, provider-neutral infrastructure.
- **99–100% Release:** all test/security/accessibility/migration/recovery gates, external penetration
  test, no critical/source conflicts, explicit Product Owner approval.

Old whistleblower Core phases 13–15 are skipped; the add-on follows its own later delivery track.

## 16. Whistleblower Add-on Track — 0% to 100%

Start only with Product Owner approval: 0–10% separate boundary/threat/legal design; 10–25% private
intake; 25–40% account-free mailbox and credentials; 40–60% handler workflow; 60–72% content-free
notifications/export/retention; 72–85% isolation, metadata, logging, enumeration and re-identification
tests; 85–95% separate monitoring/runbooks/backup/restore/incidents; 95–100% independent privacy,
security, penetration, legal/product and release approval.

## 17. Test and Release Gates

Layers: unit → domain/service → API integration → DB/RLS isolation → end-to-end → security
regression.

Test Tenant A cannot read/change/delete/export/download/discover Tenant B data across IDs, filters,
jobs, caches, queues, webhooks and objects; missing/forged context; role matrix; disabled-module API
denial; expiring elevation; MFA/SSO/session expiry; wrong tenant/module decryption; rotation/rewrap;
corrupt ciphertext; no secrets in logs; restore and DB/object loss; queue retry/idempotency; webhook
replay. When the add-on exists, test identity-free reporting, non-enumeration, hidden case metadata,
attachments, and indirect identification.

Release checks: SAST, dependency/container/IaC/secrets scans, SBOM, migration review, restore proof,
accessibility, and external penetration testing before sensitive production and regularly after.
Any cross-tenant disclosure, critical auth bypass, plaintext sensitive backup, failed recovery, or
critical security defect is NO GO.

## 18. Monitoring, Maintenance, and Alerting

Services/DB/workers/edge emit metrics to Prometheus/Grafana, logs to Loki, and errors to GlitchTip.
Monitor HTTP availability/latency/errors; DB connections/locks/replication/backups; Redis/queues;
Celery failures/retries/age; disk/object capacity; OpenBao availability/seal; Keycloak anomalies;
expiry jobs; webhook failures/dead letters; backup completion and last restore age.

Logs use correlation ID, service, and tenant-safe identifiers—never passwords, tokens, DEKs,
whistleblower content, or unnecessary personal data. Review dependencies/OS monthly and patch urgent
issues sooner; maintain DB/capacity; restore quarterly initially; rotate keys/secrets by risk; review
inactive accounts/integrations. Every alert needs an owner/runbook and should reflect impact or
security state, not noise.

## 19. Incident Response and Change Management

Incident: detect/report → classify → contain → preserve evidence → remove root cause → restore/
validate → customer/legal evaluation → post-incident review → improve control/code/runbook.

SEV-1 includes confirmed cross-tenant disclosure, key compromise, major outage, or add-on
confidentiality breach. SEV-2 is significant impact/control failure without confirmed broad exposure.
SEV-3 is limited with workaround.

Require Incident Commander, timestamped decisions, secure incident channel, privacy-safe evidence,
fact/jurisdiction-specific notification assessment, credential rotation/revocation when suspected,
and isolation validation before reopening.

Change: Git review → CI/security → staging → migration/backup review → controlled production → smoke
tests → monitoring → rollback. Prefer backward-compatible migrations; destructive ones need verified
backup and rollback/forward-fix. Document and post-review emergency changes. Production access is
least privilege, time-limited where practical, and audited.

## 20. Known Repository Deviations

- Local docs use Tier A mainly for roles/support rather than the capability set.
- The old roadmap omitted the required early entitlement foundation.
- Whistleblower was built in Core and exposed prominently despite V4's later separate boundary.
- Legal entities, business units, risks, assets, vendors, LMS and API/webhooks are missing or
  underrepresented in the old “100%” claim.
- Frontend is React 19 + Vite + TypeScript static SPA served via Nginx, formally approved via ADR D-056 (resolving the previous Next.js deviation).
- Completion must be recalculated against Section 15.

Do not delete useful code to make documents look aligned. Inventory, preserve, disable where needed,
and migrate/extract through reviewed changes.

## 21. Do Not Guess

Product Owner decisions are required for: meaning and exact contents of B–D; plan/add-on names,
prices, limits and contracts; exact Tier A German/EU framework catalog; any add-on beyond the
whistleblower product; whistleblower timing; production provider/regions/subprocessors/cost/network;
and contractual SLA/service credits.

## 22. Trello DEU Coverage — 30/30

1. [MASTER V4](https://trello.com/c/YnfYbd3h/1-master-conformly-a-z-gesamtplan-version-40)
2. [System map](https://trello.com/c/QQRHD2JS/2-systemkarte-wie-conformly-zusammenspielt)
3. [Board status guide](https://trello.com/c/jF7rsdX1/3-lesehilfe-zum-board-entscheidungen-vs-sp%C3%A4tere-arbeit)
4. [What customers buy](https://trello.com/c/By8SBkxj/4-produkt-was-kunden-tats%C3%A4chlich-kaufen)
5. [Entitlements](https://trello.com/c/3LsG2172/5-entitlements-technische-basis-preise-zahlungen-sp%C3%A4ter)
6. [Retention loop](https://trello.com/c/FYbOGgdn/6-bindungsschleife-vom-pre-audit-zu-wiederkehrendem-umsatz)
7. [Modular monolith](https://trello.com/c/9RQ1dt3U/7-architektur-zuerst-modularer-monolith)
8. [Tenant isolation](https://trello.com/c/Ad17mSLc/8-tenant-isolation-muster-vom-request-bis-zum-speicher)
9. [Core data model](https://trello.com/c/IO7AOn8R/9-kerndatenmodell-wiederverwendbare-compliance-engine)
10. [Module catalog](https://trello.com/c/r5CQXXr9/10-modulkatalog-jetzt-und-sp%C3%A4ter)
11. [Roles and access](https://trello.com/c/R7ADnc7u/11-benutzerrollen-zugriff-sechs-feste-rollen-workforce-grenze)
12. [Onboarding and daily flow](https://trello.com/c/snUGBW3r/12-ablauf-tenant-onboarding-bis-zur-t%C3%A4glichen-nutzung)
13. [Whistleblower reporter flow](https://trello.com/c/Bm9mj4HI/13-hinweisgeber-ablauf-anonymer-zwei-wege-fall)
14. [Whistleblower privacy](https://trello.com/c/lXa6dhiH/14-hinweisgeber-datenschutz-daten-die-wir-nicht-preisgeben-d%C3%BCrfen)
15. [Whistleblower case management](https://trello.com/c/xoou54L2/15-hinweisgeber-fallmanagement-bearbeiter-workflow)
16. [Pre-audit flow](https://trello.com/c/HadUJVMd/16-pre-audit-ablauf-auditor-%C3%A4hnliche-readiness-bewertung)
17. [Readiness and public profile](https://trello.com/c/lcQkMiTq/17-readiness-verification-public-profile-lebenszyklus)
18. [LMS integration](https://trello.com/c/0FOpeokt/18-lms-integration-bestehendes-lms-wiederverwenden-nicht-neu-bauen)
19. [Security model](https://trello.com/c/Xb8jeTNI/19-sicherheitsmodell-defence-in-depth)
20. [Software stack](https://trello.com/c/hQhw10X0/20-software-stack-produktions-baseline)
21. [API/event pattern](https://trello.com/c/h2ECy8Zm/21-api-event-muster-interne-und-externe-integration)
22. [Service boundaries](https://trello.com/c/tvwBqJ3a/22-service-grenzen-core-lms-und-hinweisgebersystem)
23. [Hardware baseline](https://trello.com/c/pIjMGK2s/23-hardware-baseline-pilot-bis-fr%C3%BChe-produktion)
24. [Encryption/storage flow](https://trello.com/c/Ot5t7wHt/24-speicherablauf-verschl%C3%BCsseln-bevor-daten-den-speicher-erreichen)
25. [Backup topology](https://trello.com/c/JzmxpIZ4/25-backup-topologie-3-2-1-mit-unabh%C3%A4ngiger-schl%C3%BCsselwiederherstellung)
26. [Disaster recovery](https://trello.com/c/H5eVb5oO/26-disaster-recovery-wiederherstellungsreihenfolge-und-ziele)
27. [Implementation roadmap](https://trello.com/c/LwHjqg6s/27-implementierungs-roadmap-bau-reihenfolge-von-foundation-bis-produktion)
28. [Test gates](https://trello.com/c/BC44N8ng/28-test-gates-was-vor-produktion-bestehen-muss)
29. [Operations](https://trello.com/c/LzWF9tBw/29-betrieb-monitoring-wartung-und-alerting)
30. [Incident/change management](https://trello.com/c/QHvacQNs/30-incident-response-change-management-sicher-betreiben)

## 23. Synchronization Rule

On every DEU change: verify status/approval; reread all active cards for conflicts; update this file
before code; update affected specs/ADRs/plans/tests; update snapshot/activity and 30/30 inventory;
review ENG/RUS only for drift; block implementation until conflicts are explicitly decided.+

## 24. Verbatim Trello DEU V4 Snapshot

The following is the complete unabridged text of all active cards at the snapshot date. If an implementation summary above accidentally omits a detail, this verbatim text controls.

### 1. MASTER — Conformly A–Z Gesamtplan (Version 4.0)

- Source: https://trello.com/c/YnfYbd3h/1-master-conformly-a-z-gesamtplan-version-40
- List: 01 — HIER STARTEN
- Last activity: 2026-09-06T17:09:11.214Z

STATUS: KERNARCHITEKTUR EINGEFROREN — VERSION 4.0

ZWECK
Conformly ist eine sicherheitsorientierte Multi-Tenant-Compliance-SaaS für Deutschland und die EU. Das erste bezahlte MVP ist eine menschlich geprüfte Pre-Audit-/Readiness-Plattform, keine akkreditierte Zertifizierungsstelle.

KERN-MVP
• Organisation, juristische Einheiten und Geschäftsbereiche
• Sechs feste Rollen mit explizitem Organisations-Scope
• Versionierte deutsche/EU-Frameworks und Kontrollen
• Nachweise, Richtlinien, Risiken, Assets und Lieferanten
• Feststellungen, Maßnahmen, Aufgaben und Dashboard
• Bestehendes LMS über versionierte API + signierte Webhooks
• Conformly Readiness Verification + optionales öffentliches Profil
• Deterministische Automatisierung; keine LLM-Verarbeitung von Tenant-Inhalten

SICHERHEIT
• Shared PostgreSQL mit verpflichtendem RLS
• Tenant-, Modul-, Job-, Cache-, Queue- und Storage-Isolation
• AES-256-GCM Envelope Encryption für alle Dateien, Restricted-Felder und ausgewählte Confidential-Felder
• Append-only Audit-Log, Hash-Kette und unveränderliches Archiv
• Deutschland-only für Produktion, Replikate, Backups, Schlüssel, Logs und DR
• RPO ≤ 15 Minuten; RTO ≤ 4 Stunden

SEPARAT
Das Hinweisgebersystem ist ein späteres Add-on mit eigener Anwendung, Datenbank, Storage, Schlüsseln und Release-Strecke.

PARKEN
Preise, Zahlungen, Abonnements, Rechnungen und vertragliche SLA-Logik werden erst nach dem Plattformkern entschieden.

OFFEN
Der Produktionsprovider bleibt offen. PostgreSQL-, S3-, KMS- und Terraform-Grenzen bleiben providerneutral.

### 2. SYSTEMKARTE — Wie Conformly zusammenspielt

- Source: https://trello.com/c/QQRHD2JS/2-systemkarte-wie-conformly-zusammenspielt
- List: 01 — HIER STARTEN
- Last activity: 2026-09-06T17:09:17.347Z

SYSTEMKARTE — VERSION 4.0

Benutzer
  ▼
Edge / TLS / WAF
  ▼
Next.js Web
  ▼
FastAPI Modular Core
  ├─ Tenant/Organisation/Rollen
  ├─ Frameworks/Kontrollen/Nachweise
  ├─ Richtlinien/Risiken/Assets/Lieferanten
  ├─ Assessments/Feststellungen/Maßnahmen
  ├─ Readiness Verification/Public Profile
  └─ Audit/API/Webhooks
  ▼
PostgreSQL + RLS | Redis/Celery | S3-Adapter | KMS-Adapter

IDENTITÄT
• Ein Keycloak-Kunden-Realm
• Tenant-Mitgliedschaften und Rollen bleiben in Conformly
• Pro Tenant ein OIDC- oder SAML-Broker
• Separater Workforce-Realm für Conformly-Mitarbeiter
• MFA für privilegierte Rollen; Tenant kann MFA für alle verlangen

EXTERN
Bestehendes LMS ↔ versionierte API/signierte Webhooks ↔ Conformly

SEPARATE SICHERHEITSGRENZE
Hinweisgeber-Add-on → eigene Anwendung, DB, Storage, Keys und Autorisierung.

WICHTIG
Tenant-Kontext ausschließlich aus geprüfter Sitzung/Mitgliedschaft. Keine beliebige tenant_id aus URL oder Request Body vertrauen.

### 3. LESEHILFE ZUM BOARD — Entscheidungen vs. spätere Arbeit

- Source: https://trello.com/c/jF7rsdX1/3-lesehilfe-zum-board-entscheidungen-vs-sp%C3%A4tere-arbeit
- List: 01 — HIER STARTEN
- Last activity: 2026-09-06T17:12:40.578Z

BOARD-STATUS — VERSION 4.0

LISTEN
01 Start und verbindliche Grundsätze
02 Produktgrenzen; kommerzielle Details geparkt
03 Architektur/Tenancy/Datenmodell
04 Kernmodule und Benutzerabläufe
05 Hinweisgeber: separates späteres Add-on
06 Pre-Audit/Readiness/LMS
07 Sicherheit/Kryptografie/IAM
08 Software/API/Service-Grenzen
09 Infrastruktur/Backup/DR
10 Coding-Reihenfolge/Tests/Betrieb

STATUSSPRACHE
• LOCKED = entschieden; nicht ohne Product-Owner-Freigabe ändern
• BASELINE = empfohlene technische Wahl; Änderung per ADR
• OPEN = muss vor dem genannten Gate entschieden werden
• LATER = bewusst verschoben
• MUST = Release-/Sicherheitsanforderung

AKTUELL OPEN
Produktionsprovider, konkrete deutsche Standorte/Subprozessoren und finale Kosten-/Netzwerktopologie. Das blockiert Coding nicht, weil PostgreSQL-, S3-, KMS- und Terraform-Adapter providerneutral bleiben.

GE PARKT
Preise, Zahlungen, Abonnements, Rechnungen und vertragliche SLA-Logik.

SPRACHEN
Produkt-MVP: DE/EN/FR/NL/ES. Russische Board-Dokumentation ist keine Zusage für russische MVP-Produktunterstützung.

### 4. PRODUKT — Was Kunden tatsächlich kaufen

- Source: https://trello.com/c/By8SBkxj/4-produkt-was-kunden-tats%C3%A4chlich-kaufen
- List: 02 — PRODUKT & GESCHÄFTSMODELL
- Last activity: 2026-09-06T17:09:23.774Z

ERSTES BEZAHLTES MVP
• Tier A / Tier 1 deutsche und EU-Frameworks
• Scope-/Applicability-Ermittlung
• Kontrollen, Nachweise und Review
• Richtlinien mit Editor, Vorlagen, Versionen und Freigaben
• Risikoregister mit Controls, Findings und Treatments
• Asset- und Lieferantenregister
• Pre-Audit, Findings, Maßnahmen und Recheck
• LMS-Zuweisungen und Abschlussnachweise
• Readiness Verification und optionales öffentliches Profil

NICHT IM BASIS-MVP
• Hinweisgebersystem: separates Add-on
• Benutzerdefinierte Rollen
• Workflow-Builder
• LLM-/KI-Auswertung von Tenant-Inhalten
• Preise, Payment, Rechnungen und vertragliche SLA-Logik

FORTLAUFENDER NUTZEN
Ablaufende Nachweise, Richtlinienreviews, Schulungen, Risiko-/Lieferantenänderungen, wiederkehrende Kontrollen, Audit-Historie und Erneuerung.

CLAIM
Readiness/Pre-Audit, keine akkreditierte Zertifizierung, Regulatorfreigabe, Rechtsberatung oder Compliance-Garantie.

### 5. ENTITLEMENTS — Technische Basis; Preise & Zahlungen später

- Source: https://trello.com/c/3LsG2172/5-entitlements-technische-basis-preise-zahlungen-sp%C3%A4ter
- List: 02 — PRODUKT & GESCHÄFTSMODELL
- Last activity: 2026-09-06T17:09:30.309Z

ENTSCHEIDUNG
Kommerzielle Details werden jetzt nicht umgesetzt. Preise, Abonnements, Zahlungsanbieter, Rechnungen, Rabatte, Service Credits und vertragliche SLA-Berechnung sind geparkt.

JETZT BAUEN
• Neutraler Plan-/Entitlement-Datenkern
• Modulaktivierung
• Framework-Pack-Zugriff
• Mengen-/Speichergrenzen
• Feature-Konfiguration
• Auditierbare Änderungen
• Autorisierung im Backend, nicht nur ausgeblendete UI

REGELN
• Kein Code wie if plan == "Starter".
• Keine Preiswerte im Domänenkern.
• Logische Tenant-Isolation ist immer vorhanden und kein Premium-Feature.
• Tier A / Tier 1 ist der einzige aktive MVP-Capability-Satz.
• Zukünftige B–D-Codes bleiben neutral.
• Hinweisgeber bleibt separates Add-on-Entitlement und eigener Sicherheitsbereich.

SPÄTER
Checkout, Payment Provider, Rechnungserstellung, öffentliche Plan-Namen, Preise und Vertragslogik werden in einer eigenen kommerziellen Phase entschieden.

### 6. BINDUNGSSCHLEIFE — Vom Pre-Audit zu wiederkehrendem Umsatz

- Source: https://trello.com/c/FYbOGgdn/6-bindungsschleife-vom-pre-audit-zu-wiederkehrendem-umsatz
- List: 02 — PRODUKT & GESCHÄFTSMODELL
- Last activity: 2026-09-04T20:40:58.216Z

KUNDENLEBENSZYKLUS

[Pre-Audit]
    │ Lücken gefunden
    ▼
[Maßnahmen]
    │ Kontrollen verbessert
    ▼
[Readiness-Zertifikat]
    │ veröffentlicht
    ▼
[Kontinuierliche Compliance]
    │
    ├─ ablaufende Nachweise
    ├─ Richtlinienprüfungen
    ├─ Mitarbeiterschulungen
    ├─ Lieferanten-/Risikoänderungen
    ├─ Vorfälle/Meldungen
    └─ Kontrollüberwachung
    │
    ▼
[Erneuerung / Wiederholungsprüfung]
    └───────────────► wiederholen

BINDUNGSPRINZIP
Das Dashboard soll jederzeit beantworten:
1. Sind wir aktuell bereit?
2. Was hat sich seit der letzten Bewertung geändert?
3. Was läuft ab oder erfordert als Nächstes eine Aktion?
4. Wer ist für jede Aktion verantwortlich?
5. Was können wir einem Auditor/Kunden nachweisen?

NICHT TUN
Keine künstliche Bindung erzeugen. Kundenbindung soll aus operativem Nutzen, Historie, Automatisierung und wiederkehrenden Pflichten entstehen.

### 7. ARCHITEKTUR — Zuerst modularer Monolith

- Source: https://trello.com/c/9RQ1dt3U/7-architektur-zuerst-modularer-monolith
- List: 03 — ARCHITEKTUR & DATENMODELL
- Last activity: 2026-09-06T17:09:37.148Z

LOCKED — MODULARER MONOLITH

CORE
Eine deploybare Conformly-Core-Anwendung mit strikten internen Modulgrenzen:
• Tenant/Organisation/Identity
• Autorisierung/Entitlements
• Framework/Control Engine
• Evidence/Policy/Risk/Asset/Vendor
• Assessment/Findings/Remediation
• Readiness Verification/Public Projection
• Audit/Notifications/API/Webhooks

SEPARATE SERVICES
• Bestehendes LMS bleibt unabhängig und nutzt eine versionierte API/Webhook-Grenze.
• Das spätere Hinweisgeber-Add-on erhält eigene Anwendung, DB, Storage, Keys, Worker und Autorisierung.

DATEN
Shared PostgreSQL + verpflichtendes RLS. Dedicated Deployments sind nicht Teil des ersten MVP, bleiben durch Tenant-Placement und Infrastrukturadapter später möglich.

INFRASTRUKTUR
Application Container werden von Conformly betrieben. PostgreSQL-, S3-, KMS- und Terraform-Grenzen bleiben providerneutral. Der Produktionsprovider ist noch offen.

REGEL
Ein Modul besitzt seine Logik und Datenzugriffsregeln. Herauslösen nur aus messbarem Sicherheits-, Skalierungs-, Rechts- oder Deployment-Grund.

### 8. TENANT-ISOLATION — Muster vom Request bis zum Speicher

- Source: https://trello.com/c/Ad17mSLc/8-tenant-isolation-muster-vom-request-bis-zum-speicher
- List: 03 — ARCHITEKTUR & DATENMODELL
- Last activity: 2026-09-06T17:10:11.963Z

LOCKED — TENANT- UND ORGANISATIONSISOLATION

IDENTITÄT
Eine Person kann mit einer Identität mehreren Tenants angehören. Jede Mitgliedschaft besitzt getrennte Rollen und Scopes.

ORGANISATION
Ein Tenant kann juristische Einheiten und Geschäftsbereiche enthalten. Rechte = feste Rolle + expliziter Legal-Entity-/Business-Unit-Scope.

REQUEST-PFAD
Sitzung → Keycloak-Identität → geprüfte Membership/Tenant-Auswahl → FastAPI AuthZ → PostgreSQL RLS → Domain-Service.

MUSS
• tenant_id auf jedem tenant-eigenen Datensatz und Job
• Runtime-DB-Rolle kann RLS nicht umgehen
• Tenant-scoped Cache-, Queue-, Search-, Metric- und Idempotency-Keys
• Kurzlebige Datei-URLs erst nach Autorisierung
• Negative Cross-Tenant-Tests für Lesen, Schreiben, Löschen, Export, Jobs und Storage
• Tenant niemals aus ungeprüfter URL oder Request Body ableiten

ADMIN-GRENZE
Tenant Administrator verwaltet Benutzer, SSO und Einstellungen, erhält aber nicht automatisch Zugriff auf Compliance-Inhalte.

STAFF
Kein dauerhafter Kundendatenzugriff. Nur explizites, zeitlich begrenztes Engagement oder vollständig auditierter Break-Glass-Zugriff.

### 9. KERNDATENMODELL — Wiederverwendbare Compliance-Engine

- Source: https://trello.com/c/IO7AOn8R/9-kerndatenmodell-wiederverwendbare-compliance-engine
- List: 03 — ARCHITEKTUR & DATENMODELL
- Last activity: 2026-09-06T17:10:18.660Z

LOCKED — KERNDATENMODELL

ORGANISATION
Tenant → juristische Einheiten → Geschäftsbereiche/Standorte → Benutzer/Mitgliedschaften/Scopes

COMPLIANCE
Framework → unveränderliche FrameworkVersion → Requirement ↔ Control → Assessment → Evidence → Finding → Remediation → Risk

REGISTER
Asset | ThirdParty/Vendor | Risk/Treatment | Policy/PolicyVersion | TrainingAssignment/Completion

FRAMEWORK-REGELN
• Canonical Frameworks können Tenants nicht ändern.
• Tenant-Overlays, eigene Controls und Mappings bleiben getrennt.
• Neue Canonical-Version: Legal-/Compliance-Review + unabhängige zweite Freigabe.
• Vor Adoption erhält der Tenant eine Impact-Analyse.
• Historische Assessments bleiben reproduzierbar.

EVIDENCE
Unveränderliche Versionen, SHA-256, Herkunft, Zeit, MIME/Größe, Scanstatus, Key-Referenz, Ablauf, Review, Retention und Legal Hold.

EXPORT
Maschinenlesbare Daten + Originaldateien + lesbare Berichte + verifizierbares Audit-Manifest.

PUBLIC
Öffentliche Profile lesen aus einer getrennten Publication Projection, niemals direkt aus dem Live-Evidence-Store.

### 10. MODULKATALOG — Jetzt und später

- Source: https://trello.com/c/r5CQXXr9/10-modulkatalog-jetzt-und-sp%C3%A4ter
- List: 04 — MODULE & BENUTZERABLÄUFE
- Last activity: 2026-09-06T17:10:25.110Z

IM BEZAHLTEN KERN-MVP

PLATTFORM
Tenant/Organisation, sechs feste Rollen, OIDC/SAML, MFA, Audit, Benachrichtigungen, API/Webhooks, Dashboard.

COMPLIANCE
Versionierte Frameworks/Controls, Applicability, Assessments, Evidence Vault, Findings, Remediation, Tasks.

OPERATIV
• Policy Editor + Vorlagen + Uploads + Versionen + Freigabe
• Risikoregister mit Controls, Findings und Treatments
• Asset-Register
• Third-Party-/Vendor-Register
• LMS-Zuweisungen und Abschlussnachweise
• Ablauf-/Review-Erinnerungen

ASSURANCE
Conformly Readiness Verification, Reports, 12-Monats-Lebenszyklus, Suspension/Revocation, optionales Public Profile.

SEPARATES ADD-ON SPÄTER
Hinweisgeberportal und Fallbearbeitung mit eigener Anwendung, DB, Storage und Keys.

BEWUSST SPÄTER
Custom Roles, allgemeiner Workflow-Builder, SCIM, mehrere IdPs, native Mobile Apps, Content-Benchmarking und KI-Auswertung.

### 11. BENUTZERROLLEN & ZUGRIFF — Sechs feste Rollen + Workforce-Grenze

- Source: https://trello.com/c/R7ADnc7u/11-benutzerrollen-zugriff-sechs-feste-rollen-workforce-grenze
- List: 04 — MODULE & BENUTZERABLÄUFE
- Last activity: 2026-09-06T17:10:31.655Z

TENANT-ROLLEN — LOCKED
1. Tenant Owner
2. Tenant Administrator
3. Compliance Manager
4. Control Owner
5. Reviewer
6. Employee

SCOPE
Rollen werden mit juristischer Einheit, Geschäftsbereich und unterstützten Ressourcen-Scopes kombiniert. Eine Person kann je Tenant unterschiedliche Rollen besitzen. Custom Roles sind nicht im MVP.

TRENNUNG
• Tenant Administrator verwaltet Benutzer/SSO/Settings, sieht nicht automatisch Compliance-Inhalte.
• Reviewer prüft nur zugewiesenes Material und kann keine Conformly Verification allein ausstellen.
• External Advisor ist eine befristete Account-Klassifizierung mit expliziter Rolle, kein siebter Rollentyp.

IDENTITÄT
• Ein Customer-Realm in Keycloak
• Tenant Memberships/Rollen in Conformly
• Ein OIDC-/SAML-Broker pro Tenant
• Separater Workforce-Realm für Conformly-Mitarbeiter
• MFA verpflichtend für privilegierte Rollen; Tenant kann MFA für alle erzwingen

ASSESSOR
Zeitlich begrenztes Engagement: scoped Evidence lesen, kommentieren, Findings und Reports erstellen; Kundennachweise niemals ändern.

### 12. ABLAUF — Tenant-Onboarding bis zur täglichen Nutzung

- Source: https://trello.com/c/snUGBW3r/12-ablauf-tenant-onboarding-bis-zur-t%C3%A4glichen-nutzung
- List: 04 — MODULE & BENUTZERABLÄUFE
- Last activity: 2026-09-06T17:12:46.898Z

ONBOARDING — KERN-MVP

Tenant erstellen
→ juristische Einheit(en), Geschäftsbereiche und Standorte definieren
→ Owner/Admin einladen
→ Rollen + explizite Organisations-Scopes vergeben
→ lokale Anmeldung oder einen OIDC-/SAML-Broker konfigurieren
→ Framework/Version und Assessment-Scope auswählen
→ Applicability durchführen
→ Controls/Owner/Fristen erzeugen
→ Policies/Nachweise importieren oder erstellen
→ Asset-/Vendor-/Risk-Register füllen
→ LMS verbinden
→ Baseline Assessment
→ Dashboard + Maßnahmenplan

TÄGLICHE HOME-ANSICHT
Readiness, offene Findings, überfällige Tasks, ablaufende Evidence/Policies, Training, Risk/Vendor-Änderungen und nächste Reassessment-Aktion.

UX
• Wizard + Klartext + „Warum erforderlich?“
• gespeicherter Fortschritt
• Evidence mehrfach zuordnen
• sichere Empty/Loading/Error-Zustände
• WCAG 2.2 AA
• Responsive Web; native Apps später
• Kryptografie bleibt hinter verständlicher UI

Keine Plan-/Preis-/Payment-Auswahl im aktuellen Core-Coding-Scope.

### 13. HINWEISGEBER-ABLAUF — Anonymer Zwei-Wege-Fall

- Source: https://trello.com/c/Bm9mj4HI/13-hinweisgeber-ablauf-anonymer-zwei-wege-fall
- List: 05 — HINWEISGEBERSYSTEM & ANONYMITÄT
- Last activity: 2026-09-04T20:43:48.069Z

MELDER-ABLAUF

Dedizierte Tenant-Melde-URL
          ▼
Anonymen / identifizierten Weg wählen
          ▼
Sachverhalt beschreiben + optionale Anhänge
          ▼
Client-/Server-Datenschutzprüfungen
          ▼
Fallinhalt verschlüsseln
          ▼
Zufällige Fall-ID + geheimen Zugangscode erzeugen
          ▼
Empfangsbestätigung/Status-Postfach anzeigen
          │
          ├──── Melder kehrt ohne Konto zurück
          ▼
Case Handler prüft/antwortet
          │
          ▼
Melder liest Antwort / ergänzt Informationen
          ▼
Status + Abschluss

ANONYMITÄTSREGEL
Anonyme Meldungen dürfen kein Mitarbeiterkonto, keine E-Mail und keine Identität voraussetzen.

NACHVERFOLGUNG
Hochentropische Fallkennung plus getrenntes Geheim-/Recovery-Credential verwenden. Nur geschütztes Verifier-Material speichern, nicht das Klartextgeheimnis.

BENACHRICHTIGUNGEN
Meldungsinhalt niemals in normale E-Mails schreiben. Berechtigte Bearbeiter nur darüber informieren, dass ein Fall Aufmerksamkeit benötigt.

FRISTEN
Konfigurierbare rechtsraumspezifische Bestätigungs-/Feedback-Timer verwenden; kein einzelnes Rechtsregime hart in die Geschäftslogik codieren.

### 14. HINWEISGEBER-DATENSCHUTZ — Daten, die wir NICHT preisgeben dürfen

- Source: https://trello.com/c/lXa6dhiH/14-hinweisgeber-datenschutz-daten-die-wir-nicht-preisgeben-d%C3%BCrfen
- List: 05 — HINWEISGEBERSYSTEM & ANONYMITÄT
- Last activity: 2026-09-04T20:44:10.229Z

BEDROHUNGSMODELL
Ein Hinweisgeber kann versehentlich über Logs, Metadaten, Benachrichtigungen, Analytics oder Administratorzugriff identifiziert werden, selbst wenn das Formular „anonym“ sagt.

MUSS
• Separate Hinweisgeber-DB-/Schema-Grenze und separate Verschlüsselungsschlüssel.
• Keine Drittanbieter-Werbung/Verhaltensanalyse im Meldeportal.
• Speicherung von Quell-IP/User-Agent soweit technisch sowie rechtlich-operativ möglich minimieren oder unterdrücken.
• Reverse-Proxy-/Anwendungslogs dürfen Meldungstext, geheime Tokens oder Anhangsnamen nicht unnötig enthalten.
• Riskante Dateimetadaten (z. B. EXIF-/Dokumentmetadaten) vor Download durch Bearbeiter soweit angemessen entfernen; Original nur bei ausdrücklichem Bedarf geschützt erhalten.
• Gespeicherte Dateinamen/Objektschlüssel randomisieren.
• Nachrichten und Anhänge anwendungsseitig verschlüsseln.
• Fallzugriff nur für ausdrücklich autorisierte Bearbeiter.
• Kein Meldungstext in E-Mail, Monitoring, Error Traces oder Audit-Log.
• Geheime Zugangsdaten niemals loggen.
• Rate-Limit-/Missbrauchsschutz darf kein Identitätstracking erzeugen.

DATENSCHUTZTEST
Vor Produktion und nach Änderungen an Logging/Analytics gezielt prüfen: „Können wir die meldende Person indirekt ableiten?“

### 15. HINWEISGEBER-FALLMANAGEMENT — Bearbeiter-Workflow

- Source: https://trello.com/c/xoou54L2/15-hinweisgeber-fallmanagement-bearbeiter-workflow
- List: 05 — HINWEISGEBERSYSTEM & ANONYMITÄT
- Last activity: 2026-09-04T20:44:28.306Z

BEARBEITER-ABLAUF

Neuer Fall
  ▼
Triage / Interessenkonfliktprüfung
  ▼
Autorisierte Bearbeiter zuweisen
  ▼
Bestätigen / sichere Nachricht
  ▼
Untersuchen
  ├─ interne Notizen
  ├─ geschützte Nachweise
  ├─ Aufgaben
  └─ Statusänderungen
  ▼
Ergebnis / Maßnahme
  ▼
Feedback an Melder
  ▼
Abschluss + Aufbewahrungsrichtlinie

FALLDATEN
Fall
Nachrichten (Melder/Bearbeiter)
Anhänge
Interne Notizen
Statushistorie
Zuweisungen
Fristen
Maßnahmen/Ergebnisse
Zugriffs-Audit

SICHERHEIT
• Interne Notizen sind für den Melder niemals sichtbar.
• Melder-sichtbare Nachricht wird vor Versand ausdrücklich markiert.
• Zuweisungsänderungen und Exporte werden auditiert.
• Export ist privilegiert und soweit möglich wasserzeichen-/loggingfähig.
• Konflikt/Recusal des Bearbeiters muss möglich sein.
• Geschlossene Fälle bleiben gemäß konfigurierter Aufbewahrung/Legal Hold geschützt.
• Suchindizes dürfen keine unverschlüsselte Kopie des Meldungsinhalts erzeugen.

STATUSBEISPIEL
Eingegangen → Triage → In Prüfung → Maßnahme erforderlich → Geschlossen. Statuslabels konfigurierbar halten.

### 16. PRE-AUDIT-ABLAUF — Auditor-ähnliche Readiness-Bewertung

- Source: https://trello.com/c/HadUJVMd/16-pre-audit-ablauf-auditor-%C3%A4hnliche-readiness-bewertung
- List: 06 — PRE-AUDIT, ZERTIFIKATE & LMS
- Last activity: 2026-09-06T17:11:35.539Z

LOCKED — HUMAN-REVIEWED PRE-AUDIT

ABLAUF
Framework-Version + Scope einfrieren
→ Applicability und Controls
→ Evidence Requests
→ Kunde liefert Nachweise
→ deterministische Vollständigkeits-/Gap-Prüfung
→ zugewiesener Conformly Assessor prüft
→ Findings + Schweregrad + Remediation
→ Recheck
→ unabhängige zweite Prüfung
→ Tenant-Freigabe
→ Readiness-Ergebnis/Report

ASSESSOR-RECHTE
Zeitlich begrenzt und scoped: Evidence lesen, kommentieren, Findings und Reports erstellen. Kundennachweise niemals verändern.

WORKFLOW
Versionierte feste Zustandsmaschinen mit konfigurierbaren Assignees und Fristen. Kein allgemeiner Workflow-Builder im MVP.

NACHVOLLZIEHBARKEIT
Issued Result friert Framework-Version, Scope, Controls, Evidence-Referenzen, Reviewer, Entscheidungen, Zeitstempel, Findings und Einschränkungen ein.

AUTOMATISIERUNG
Nur deterministische, versionierte, erklärbare Regeln. Kein LLM erhält Tenant-Inhalte und keine KI erzeugt Compliance-Schlüsse.

CLAIM
Readiness/Pre-Audit, keine akkreditierte Zertifizierung, Regulatorfreigabe, Rechtsberatung oder Garantie.

### 17. READINESS VERIFICATION & PUBLIC PROFILE — Lebenszyklus

- Source: https://trello.com/c/lcQkMiTq/17-readiness-verification-public-profile-lebenszyklus
- List: 06 — PRE-AUDIT, ZERTIFIKATE & LMS
- Last activity: 2026-09-06T17:11:41.907Z

NAME
Conformly Readiness Verification / Conformly Readiness Verified.

FREIGABE
Veröffentlichung erst nach:
1. menschlichem Assessment,
2. unabhängiger Zweitprüfung,
3. ausdrücklicher Tenant-Freigabe.

GÜLTIGKEIT
12 Monate ab Ausstellung. Frühere Korrektur, Suspension oder Widerruf möglich. Eine materielle Scope-/Control-Änderung suspendiert die betroffene Verification bis zur gezielten Reassessment-Freigabe.

PUBLIC PROFILE
Zeigt nur ausdrücklich freigegebene Projektionsdaten: Organisation, Framework-Version, Scope, Ausstellungs-/Ablaufdatum, Status und opaque Verification-ID. Kein direkter Zugriff auf den Live-Evidence-Store.

EXTERNE ZERTIFIKATE
Issuer, Titel, Scope, Gültigkeit und Verification-Status klar anzeigen: self-declared, extern ausgestellt, von Conformly geprüft oder Conformly Readiness Result.

SICHERHEIT
Nicht erratbare IDs, Rate Limits, sichere Cache-Abläufe und sichtbarer revoked/expired/superseded-Status. Keine privaten Nachweise, Findings, Scores, Mitarbeiter- oder Tenant-internen IDs veröffentlichen.

DISCLAIMER
Explizit keine akkreditierte Zertifizierung, Regulatorfreigabe, Rechtsberatung oder Compliance-Garantie.

### 18. LMS-INTEGRATION — Bestehendes LMS wiederverwenden, nicht neu bauen

- Source: https://trello.com/c/0FOpeokt/18-lms-integration-bestehendes-lms-wiederverwenden-nicht-neu-bauen
- List: 06 — PRE-AUDIT, ZERTIFIKATE & LMS
- Last activity: 2026-09-04T20:45:40.147Z

ENTSCHEIDUNG
Das bestehende LMS als separaten Training-&-Awareness-Service verwenden. Kein weiteres LMS innerhalb von Conformly bauen und LMS-Tabellen nicht in die Compliance-Datenbank zusammenführen.

CONFORMLY VERANTWORTET
Schulungsanforderung
Zuweisung an Tenant/Benutzer/Gruppe
Fälligkeitsdatum
Compliance-Zuordnung
Abschlussnachweis/-status

LMS VERANTWORTET
Kursinhalte
SCORM/Runtime
Lektionen/Quizze
Learning UX
Details zum Kursabschluss

ABLAUF
Conformly-Zuweisung
      │ API/SSO
      ▼
Bestehendes LMS
      │ signiertes Abschluss-Event/Webhook
      ▼
Conformly verifiziert Event
      │
      ▼
TrainingCompletion-Nachweis
      │
      ▼
Zugeordnete Compliance-Kontrolle wird aktualisiert

INTEGRATIONSANFORDERUNGEN
• Zentrales Identity-/Tenant-Mapping.
• OIDC/SSO soweit möglich.
• Signierte, replay-geschützte Completion-Callbacks.
• Idempotente Event-Verarbeitung.
• Kurs-/Versionskennungen.
• Änderungen an Zuordnungen auditieren.
• Niemals nur einem Browser-Redirect „completed=true“ vertrauen.

So bleibt das LMS unabhängig deploybar, während seine Nachweise Teil der kontinuierlichen Compliance werden.

### 19. SICHERHEITSMODELL — Defence in Depth

- Source: https://trello.com/c/Xb8jeTNI/19-sicherheitsmodell-defence-in-depth
- List: 07 — SICHERHEIT, VERSCHLÜSSELUNG & IAM
- Last activity: 2026-09-06T17:13:05.313Z

LOCKED — DEFENCE IN DEPTH

SCHICHTEN
Edge/TLS/WAF
→ Keycloak + MFA/SSO
→ Membership + feste Rolle + Organisations-Scope
→ FastAPI Deny-by-default AuthZ
→ PostgreSQL RLS
→ App-Layer Envelope Encryption
→ Storage/Disk Encryption
→ verschlüsselte/immutable Backups
→ Append-only/hash-chained Audit

KLASSIFIKATION
Public | Internal | Confidential | Restricted
Optionale Tags. Hinweisgeber-restricted lebt nur im separaten Add-on.

ENCRYPTION
Alle Dateien, alle Restricted-Felder und ausgewählte Confidential-Felder. Tenant-Key + rotierbare File/Secret-DEKs. Kein Core-Browser-E2EE.

STAFF
Kein Standing Access. Nur expiring Engagement oder audited Break Glass. Workforce-Realm getrennt vom Customer-Realm.

ANALYTICS/LOGS
Nur content-freie Cross-Tenant-Betriebsmetadaten. Keine Tenant-Inhalte für Benchmarks, LLMs, Logs, Traces oder Training.

AUDIT
Append-only, Hash-Kette, periodisch in immutable Storage versiegelt.

MUSS
Threat Models, SAST/Dependencies/Container/IaC/Secrets Scans, SBOM, negative Isolationstests, Malware-Quarantäne, Restore-Test und externer Security Review vor sensibler Produktion.

### 20. SOFTWARE-STACK — Produktions-Baseline

- Source: https://trello.com/c/hQhw10X0/20-software-stack-produktions-baseline
- List: 08 — SOFTWARE-STACK & APIs
- Last activity: 2026-09-06T17:12:53.055Z

LOCKED — SOFTWARE-STACK

WEB
Next.js + React + TypeScript; responsive, WCAG 2.2 AA, i18n DE/EN/FR/NL/ES.

API
Python + FastAPI + SQLAlchemy + Alembic + Pydantic.

DATEN
PostgreSQL mit verpflichtendem RLS; Redis + Celery; Transactional Outbox.

IDENTITÄT
Keycloak als OIDC-Grenze:
• ein Customer-Realm
• Tenant-spezifische OIDC-/SAML-Broker
• Memberships/Rollen in Conformly
• separater Workforce-Realm

STORAGE & KEYS
S3-kompatibler Object-Storage-Adapter.
KMS/Secrets-Adapter; Managed KMS oder OpenBao bleibt Deployment-Entscheidung.
AES-256-GCM Envelope Encryption.

EDGE/OBSERVABILITY
Container, TLS/WAF/Rate Limits, OpenTelemetry, privacy-scrubbed Logs, Metrics, Traces und Alerts.

ENTWICKLUNG
Lokale Container für PostgreSQL, Redis, S3-Dev-Store, Keycloak, Mail-Catcher und Malware Scanner.

PRODUKTION
Conformly betreibt App-Container; Managed DB/Storage/KMS ist bevorzugt. Provider bleibt OPEN. Deutschland-only Datenresidenz und providerneutrale Terraform-/Service-Adapter sind verpflichtend.

### 21. API- & EVENT-MUSTER — Interne und externe Integration

- Source: https://trello.com/c/h2ECy8Zm/21-api-event-muster-interne-und-externe-integration
- List: 08 — SOFTWARE-STACK & APIs
- Last activity: 2026-09-04T20:46:34.787Z

API-PRINZIP
Conformly ist intern API-first, aber nur stabile, dokumentierte Endpunkte werden öffentliche APIs.

REQUEST-ABLAUF
Client / Integration
      │ HTTPS + OIDC/Service-Auth
      ▼
Caddy
      ▼
FastAPI-Route
      ▼
AuthZ + Tenant-Kontext + Entitlement
      ▼
Domain-Service
      ▼
DB / Queue / Objektspeicher

ÖFFENTLICHE API
/api/v1/... mit expliziter Versionierung.
Opaque Kennungen, Pagination, Idempotency Keys für Create-Operationen wo nötig und strukturierte Fehlercodes verwenden.

WEBHOOKS
Domain-Event → Outbox-Tabelle → Celery-Zustellung → signierter Webhook

MUSS
• HMAC/Signatur mit Zeitstempel.
• Replay-Schutz.
• Retry mit exponentiellem Backoff.
• Sichtbarkeit für Dead-Letter/fehlgeschlagene Zustellungen.
• Tenant-spezifische Webhook-Secrets.
• Idempotenz bei Empfänger und Sender, soweit relevant.
• Niemals Secrets oder unnötige personenbezogene Daten senden.

INTERNE EVENTS
Transactional Outbox verwenden, damit DB-Commit und Event-Absicht nicht auseinanderlaufen.

BEISPIELE
assessment.completed
finding.created
certificate.issued
certificate.revoked
evidence.expiring
training.completed

Hinweisgeber-Events verwenden einen separaten eingeschränkten Event-Pfad und dürfen niemals Meldungsinhalte broadcasten.

### 22. SERVICE-GRENZEN — Core, LMS und Hinweisgebersystem

- Source: https://trello.com/c/tvwBqJ3a/22-service-grenzen-core-lms-und-hinweisgebersystem
- List: 08 — SOFTWARE-STACK & APIs
- Last activity: 2026-09-06T17:11:48.397Z

LOCKED — SERVICE-GRENZEN

CONFORMLY CORE
Tenant/Organisation, Memberships/Scopes, Frameworks, Controls, Assessments, Evidence, Policies, Risks, Assets, Vendors, Findings, Remediation, Readiness Verification, Public Projection, Audit, API und Webhooks.

BESTEHENDES LMS
Bleibt unabhängig deploybar. Conformly speichert normalisierte Training Assignments und Completion Evidence. Integration über versionierte API und signierte, replay-geschützte, idempotente Webhooks. Keine gemeinsame Datenbank.

HINWEISGEBER-ADD-ON
Später und separat: eigene Anwendung, DB, Storage, Keys, Worker, Autorisierung und Release-Gates. Keine Abfrage über allgemeine Core-, Analytics- oder Admin-Schnittstellen.

IDENTITÄT
Ein Customer-Realm mit Tenant-spezifischen OIDC-/SAML-Brokern; Memberships/Rollen in Conformly. Separater Workforce-Realm für Conformly-Personal.

PUBLIC PROFILE
Separate Publication Projection; niemals direkter öffentlicher Zugriff auf Tenant-/Evidence-Daten.

SPRACHEN MVP
Deutsch, Englisch, Französisch, Niederländisch und Spanisch vollständig geprüft. Weitere Sprachen bleiben technisch vorbereitet.

### 23. HARDWARE-BASELINE — Pilot bis frühe Produktion

- Source: https://trello.com/c/pIjMGK2s/23-hardware-baseline-pilot-bis-fr%C3%BChe-produktion
- List: 09 — HARDWARE, SPEICHER, BACKUPS & DR
- Last activity: 2026-09-04T20:47:16.244Z

ERWARTETE ANFANGSSKALIERUNG
2–3 Firmen / ungefähr 1.000 gemeinsame Benutzer, geringe gleichzeitige Nutzung, anfangs deutlich unter 1–2 TB Kundendaten.

PILOT / VOR KUNDENBETRIEB
Ein EU-gehosteter Server kann den Stack betreiben:
• 8 vCPU
• 32 GB RAM
• 500 GB+ NVMe
• verschlüsselte Volumes
• externe verschlüsselte Backups
Für Entwicklung/Pilot akzeptabel, nicht das endgültige Resilienzmodell.

ZIEL FÜR FRÜHE PRODUKTION
APP-/WORKER-NODE
8 vCPU / 16–32 GB RAM / 200+ GB NVMe

DATENBANK-NODE
8 vCPU / 32 GB RAM / schnelle NVMe / verschlüsselter Speicher

KEY-/SECRETS-NODE
2–4 vCPU / 4–8 GB RAM / kleine verschlüsselte Disk / isoliertes Netzwerk

OBJEKTSPEICHER
Mit ca. 2 TB nutzbar starten, unabhängig vom Compute erweiterbar.

WARUM TRENNEN
Datenbank, Anwendung und Schlüsselsysteme sollten nach Beginn echter Kundendaten nicht dieselbe Ausfall-/Sicherheitsgrenze teilen.

KAPAZITÄTSSIGNALE
Skalieren, wenn CPU/RAM-Druck, DB-Latenz, Queue-Tiefe, Speicherwachstum oder Backup-Fenster den Bedarf zeigen—nicht allein nach Benutzerzahl.

HOME-SYNOLOGY
Die vorhandene 24-TB-Synology mit 300/150-Mbit/s-Glasfaser eignet sich bei frühen Datenmengen als ein verschlüsseltes Off-Site-Backupziel. Sie darf NICHT das einzige Backup oder der primäre Produktionsspeicher sein.

### 24. SPEICHERABLAUF — Verschlüsseln, bevor Daten den Speicher erreichen

- Source: https://trello.com/c/Ot5t7wHt/24-speicherablauf-verschl%C3%BCsseln-bevor-daten-den-speicher-erreichen
- List: 09 — HARDWARE, SPEICHER, BACKUPS & DR
- Last activity: 2026-09-06T17:10:38.554Z

LOCKED — ENVELOPE ENCRYPTION

UMFANG
• Alle Dateien
• Alle Restricted-Felder
• Ausgewählte Confidential-Felder
• Keine Browser-zu-Browser-E2EE im Core, damit autorisierte Workflows, Checks, Exporte und Reports funktionieren

ABLAUF
Klartext im autorisierten Service
→ zufälliger Data Encryption Key (DEK)
→ AES-256-GCM
→ Ciphertext in DB/S3
→ DEK mit Tenant-Key wrappen
→ Key-Version/Algorithmus/Ciphertext-Format speichern

SCHLÜSSEL
Tenant-spezifische Keys plus rotierbare Keys pro Datei/Secret. Der Storage erhält keine wiederverwendbaren Tenant-Schlüssel im Klartext.

KRYPTO-AGILITÄT
Versionierte Algorithmen und Formate. Standardisierte Hybrid-/Post-Quantum-Verfahren erst nach Produktionsreife, Ecosystem-Support und Security Review. Nicht „quantum-proof“ vermarkten.

LÖSCHEN
Ciphertext, gewrappte Keys und Metadaten gemäß Retention/Legal Hold löschen. Storage-/Disk-Verschlüsselung bleibt zusätzliche Schicht.

PROVIDER
KMS-Adapter bleibt austauschbar; OpenBao oder Managed KMS ist eine Deployment-Entscheidung, keine Domänenabhängigkeit.

### 25. BACKUP-TOPOLOGIE — 3-2-1 mit unabhängiger Schlüsselwiederherstellung

- Source: https://trello.com/c/JzmxpIZ4/25-backup-topologie-3-2-1-mit-unabh%C3%A4ngiger-schl%C3%BCsselwiederherstellung
- List: 09 — HARDWARE, SPEICHER, BACKUPS & DR
- Last activity: 2026-09-06T17:12:59.028Z

LOCKED — BACKUP/DR

RESIDENZ
Alle Produktionsdaten, Replikate, Backups, Schlüssel, Logs und DR-Kopien bleiben in Deutschland.

3-2-1-1-0
• mindestens 3 Kopien
• 2 Systeme/Medien
• 1 getrennte Ausfall-Domain
• 1 immutable/offline Kopie
• 0 ungeprüfte Backup-Fehler

DATENBANK
PITR für RPO ≤ 15 Minuten, synchrone Multi-Zone-HA und asynchrone deutsche DR-Kopie.

OBJEKTE
Versionierte, verschlüsselte Replikation/Backups; mindestens eine unveränderliche Kopie.

SCHLÜSSEL
Backup-Credentials und Key-Recovery getrennt von Produktion und Nutzdaten speichern.

SYNOLOGY
Die vorhandene Synology kann nach Freigabe eine zusätzliche verschlüsselte deutsche Off-Site-Kopie sein, niemals primärer Storage oder einziges Backup.

TEST
Vollständiger Restore vierteljährlich und nach wesentlichen Infrastrukturänderungen. RTO ≤ 4 Stunden messen.

CHUNKING
Erasure Coding/Chunking dient nur Resilienz. Vertraulichkeit kommt zuerst aus starker Verschlüsselung und unabhängigen Schlüsseln.

### 26. DISASTER RECOVERY — Wiederherstellungsreihenfolge und Ziele

- Source: https://trello.com/c/H5eVb5oO/26-disaster-recovery-wiederherstellungsreihenfolge-und-ziele
- List: 09 — HARDWARE, SPEICHER, BACKUPS & DR
- Last activity: 2026-09-06T17:11:54.564Z

LOCKED — RECOVERY-ZIELE

RPO ≤ 15 MINUTEN
Maximal tolerierter Verlust bestätigter Produktionsdaten.

RTO ≤ 4 STUNDEN
Ziel bis zur validierten Wiederaufnahme des Kernservices.

TOPOLOGIE
• Synchrone Multi-Zone-PostgreSQL-HA
• Asynchrone DR-Kopie an getrenntem Standort in Deutschland
• Versionierte/immutable Object-Backups
• Separate Backup-Credentials und Schlüssel
• Deutschland-only für DB, Replikate, Objekte, Backups, Keys, Logs und DR

TESTS
Vollständiger Restore vierteljährlich und nach wesentlichen Infrastrukturänderungen.

RESTORE MUSS BEWEISEN
• kohärenter DB-/Objekt-/Identity-/Key-Stand
• korrekte Entschlüsselung autorisierter Testobjekte
• Tenant-A/B-Isolation nach Restore
• korrekte Audit-/Verification-Zustände
• keine doppelten Jobs/Webhooks
• gemessene RPO/RTO und dokumentierte Korrekturmaßnahmen

REIHENFOLGE
Netzwerk/Edge → Identity/Keys → PostgreSQL → Object Storage → Core/Worker → Integritäts-/Isolationstests → Integrationen → Traffic.

Die Ziele sind Engineering Objectives, keine vertraglichen SLA-Zusagen.

### 27. IMPLEMENTIERUNGS-ROADMAP — Bau-Reihenfolge von Foundation bis Produktion

- Source: https://trello.com/c/LwHjqg6s/27-implementierungs-roadmap-bau-reihenfolge-von-foundation-bis-produktion
- List: 10 — AUSLIEFERUNG, TESTS & BETRIEB
- Last activity: 2026-09-06T17:12:00.878Z

AKTUELLE BAUREIHENFOLGE — VERSION 4.0

01 FOUNDATION
Monorepo, ADRs, Toolchains, CI, Config, i18n, Threat Models.

02 LOKALE PLATTFORM
PostgreSQL, Redis, S3-Dev-Storage, Keycloak, Mail-Catcher, Malware Scanner.

03 TENANT/IDENTITY/ISOLATION
Memberships, juristische Einheiten, Geschäftsbereiche, sechs Rollen, Scopes, RLS, MFA/SSO.

04 AUTHZ/ENTITLEMENTS
Neutral und datengetrieben. Keine Preise, Payments, Rechnungen oder SLA-Logik.

05–12 CORE
Audit/Outbox → Organisation/Scope → Frameworks/Controls → Evidence → Assessments/Findings → Tasks/Notifications → Policies → Risks/Assets/Vendors.

13–15 ÜBERSPRINGEN
Hinweisgeber ist separates späteres Add-on.

16–23 ABSCHLUSS
Readiness/Public Profile → LMS → API/Webhooks → Exporte → DR → Observability/Deployment → Release Gate.

REGELN
• Erst ein vollständiger, getesteter vertikaler Slice, dann der nächste.
• Sicherheit, RLS, Encryption, Audit, Accessibility und Fehlerpfade sind keine späteren TODOs.
• Payment-/Subscription-Diskussion bleibt geparkt.
• Produktionsprovider bleibt offen; Adapter verhindern Blockade.
• Kein Production Deployment ohne ausdrückliche Freigabe.

### 28. TEST-GATES — Was vor Produktion bestehen muss

- Source: https://trello.com/c/BC44N8ng/28-test-gates-was-vor-produktion-bestehen-muss
- List: 10 — AUSLIEFERUNG, TESTS & BETRIEB
- Last activity: 2026-09-04T20:48:46.537Z

AUTOMATISIERTE TESTSCHICHTEN
Unit → Domain-/Service-Tests → API-Integration → DB-/RLS-Isolation → End-to-End → Security Regression.

TENANT-ISOLATION
• Benutzer von Tenant A kann Daten von Tenant B nicht lesen/ändern/löschen.
• Für direkte IDs, Filter, Exporte, Jobs, Caches, Webhooks und Objekt-Downloads wiederholen.
• Fehlenden/gefälschten Tenant-Kontext testen.

AUTH / ENTITLEMENTS
• Rollenmatrix-Tests.
• APIs deaktivierter Module liefern Autorisierungsfehler.
• Admin-Rechteerhöhung läuft korrekt ab.
• MFA/SSO/Sitzungsablauf testen.

KRYPTOGRAFIE
• Falscher Tenant-/Modulschlüssel kann nicht entschlüsseln.
• Key Rotation und Re-Wrap testen.
• Beschädigter Ciphertext schlägt sicher fehl.
• Secrets/Tokens erscheinen niemals in Logs.

HINWEISGEBER
• Anonymer Melder benötigt keine Identität.
• Fallgeheimnis kann nicht enumeriert/aus Logs rekonstruiert werden.
• Unberechtigte Benutzer entdecken keine Fallmetadaten.
• Anhangsmetadaten-/Datenschutzprüfungen.

RESILIENZ
• Backup-Restore-Test.
• DB-/Objektverlust simulieren.
• Queue-Retry-/Idempotenz-Test.
• Webhook-Replay-Schutz.

RELEASE-GATES
SAST + Dependency Scan + Container Scan + SBOM + Migration Review + Secrets Scan.
Externer Penetrationstest vor Verarbeitung echter sensibler Produktionsdaten und danach regelmäßig.

NO GO
Jede Cross-Tenant-Offenlegung, sensibles Klartext-Backup, fehlerhafte Recovery oder kritischer Auth-Bypass blockiert das Release.

### 29. BETRIEB — Monitoring, Wartung und Alerting

- Source: https://trello.com/c/LzWF9tBw/29-betrieb-monitoring-wartung-und-alerting
- List: 10 — AUSLIEFERUNG, TESTS & BETRIEB
- Last activity: 2026-09-04T20:49:04.697Z

OBSERVABILITY-ABLAUF

Services / DB / Worker / Edge
          │
          ├─ Metriken ─► Prometheus ─► Grafana
          ├─ Logs ──────► Loki
          └─ Fehler ────► GlitchTip
                            │
                            ▼
                       Alert / Triage

ÜBERWACHEN
• HTTP-Verfügbarkeit und Latenz.
• 4xx-/5xx-Fehlerraten.
• DB-Verbindungen, Locks, Replikations-/Backup-Gesundheit.
• Redis-Speicher und Queue-Tiefe.
• Celery-Fehler/Retry/Alter.
• Disk-/Objektspeicher-Kapazität.
• OpenBao-Verfügbarkeit/Seal-Status.
• Keycloak-Authentifizierungsfehler/Anomalien.
• Zertifikats-/Nachweis-Ablaufjobs.
• Webhook-Fehler-/Dead-Letter-Zahlen.
• Backup-Abschluss + Alter des letzten Restore-Tests.

LOGGING-REGELN
Strukturierte Logs mit Request-/Correlation-ID, Service und tenant-sicheren Kennungen. Niemals Passwörter, Tokens, DEKs, Meldungsinhalte oder unnötige personenbezogene Daten loggen.

WARTUNG
Monatliche Dependency-/OS-Prüfung; dringende Sicherheitspatches früher.
DB-Wartung und Kapazitätsprüfung.
Anfangs vierteljährlicher Restore-Test.
Regelmäßige Key-/Secret-Rotation nach Risiko/Richtlinie.
Inaktive Konten/Integrationen prüfen.

ALERT-QUALITÄT
Auf Benutzerbeeinträchtigung oder sicherheitsrelevante Zustände alarmieren, nicht auf jede Metrikschwankung. Jeder Produktions-Alert benötigt Verantwortlichen und Runbook.

### 30. INCIDENT RESPONSE & CHANGE MANAGEMENT — Sicher betreiben

- Source: https://trello.com/c/QHvacQNs/30-incident-response-change-management-sicher-betreiben
- List: 10 — AUSLIEFERUNG, TESTS & BETRIEB
- Last activity: 2026-09-04T20:49:23.673Z

INCIDENT-ABLAUF

Erkennen / melden
    ▼
Schweregrad klassifizieren
    ▼
Eindämmen
    ▼
Nachweise sichern
    ▼
Root Cause beseitigen
    ▼
Wiederherstellen / validieren
    ▼
Kunden-/rechtliche Bewertung
    ▼
Post-Incident-Review
    ▼
Kontrolle / Code / Runbook verbessern

SCHWEREGRAD-BEISPIELE
SEV-1: bestätigte Cross-Tenant-Offenlegung, Schlüsselkompromittierung, großer Ausfall, Vertraulichkeitsverletzung im Hinweisgebersystem.
SEV-2: erhebliche Servicebeeinträchtigung oder Ausfall einer Sicherheitskontrolle ohne bestätigte breite Offenlegung.
SEV-3: begrenzter Fehler mit Workaround.

MUSS
• Benannter Incident Commander.
• Zeitgestempeltes Entscheidungsprotokoll.
• Separater sicherer Incident-Kanal.
• Logs/Nachweise sichern, ohne unnötige sensible Inhalte zu kopieren.
• Rechtliche/Datenschutz-Meldepflicht anhand tatsächlichen Rechtsraums und Sachverhalts bewerten.
• Zugangsdaten bei vermuteter Kompromittierung rotieren/widerrufen.
• Tenant-Isolation vor Wiederfreigabe des Dienstes validieren.

CHANGE MANAGEMENT
Git-basiertes Review → CI-/Security-Tests → Staging → Migration-/Backup-Prüfung → kontrolliertes Produktions-Deployment → Smoke Tests → Monitoring → Rollback bei Bedarf.

DATENBANK
Möglichst rückwärtskompatible Migrationen; destruktive Migrationen benötigen verifiziertes Backup und Rollback-/Forward-Fix-Plan.

SICHERHEITSREGEL
Notfalländerungen sind bei Bedarf erlaubt, müssen aber dokumentiert und nachträglich geprüft werden. Produktionszugriff erfolgt nach Least Privilege, soweit praktikabel zeitlich begrenzt und vollständig auditiert.
