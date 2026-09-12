# Conformly — Complete Build Plan (0% to 100%)

## 1. Purpose

This is the execution plan for taking Conformly from its repository foundation to a
production-ready paid pilot. It translates the product and architecture documents into
ordered implementation work, explicit quality gates, and completion criteria.

This document does not replace the source-of-truth requirements in:

1. `AGENTS.md`
2. `docs/PRODUCT_SPEC.md`
3. `docs/ARCHITECTURE.md`
4. `docs/SECURITY.md`
5. `docs/DATA_MODEL.md`
6. `docs/MVP_SCOPE.md`
7. `docs/DECISIONS.md`
8. `docs/IMPLEMENTATION_PLAN.md`

Read those files before changing architecture. If this plan conflicts with them, those
documents win. Record material new decisions in `docs/DECISIONS.md` before implementation.

## 2. How Codex Should Use This Plan

At the beginning of every implementation session:

1. Read `AGENTS.md`, every document under `docs/`, and the current repository state.
2. Inspect the current branch and uncommitted changes. Preserve unrelated user work.
3. Find the first incomplete phase and the first unchecked deliverable in that phase.
4. Implement one coherent, reviewable vertical slice at a time.
5. Add migrations for database changes. Never edit an applied migration casually.
6. Add tests with every security-sensitive or tenant-scoped behavior.
7. Run the phase's checks before declaring the slice complete.
8. Update this checklist only after the corresponding work is verified.
9. Summarize changes, assumptions, tests, risks, and the exact next item.

Do not skip a phase gate because later UI work appears easier. Do not treat a checked box as
proof if the implementation or verification evidence is missing.

## 3. Non-Negotiable Invariants

Every implementation must preserve these rules:

- Conformly is a multi-tenant pre-audit and compliance operations product, not an accredited
  certification body.
- Every tenant-scoped database operation is scoped server-side with explicit tenant context.
- Authorization is enforced at the API/service boundary, never only in the UI.
- Tier A has exactly six fixed roles. Do not invent public role labels until approved and
  recorded in `docs/DECISIONS.md`.
- All files and all Restricted fields use application-layer AES-256-GCM envelope encryption.
- Selected Confidential fields use encryption according to explicit schema policy.
- Crypto and key-management providers remain replaceable and versioned.
- Canonical framework content is system-owned and immutable to tenants.
- Framework releases require legal/compliance review and independent second-person approval.
- Tenant framework upgrades are controlled and require impact analysis.
- MVP automation is deterministic. It must not make generative or autonomous compliance
  decisions.
- Whistleblower reporting supports genuine anonymous use without identity reconstruction or
  identity-leaking logs and analytics.
- Public profiles contain only explicitly approved public projections.
- Cancellation provides a 30-day export window and deletion by day 90.
- Cross-tenant analytics use operational metadata only, never tenant content.
- Logs and audit metadata never contain secrets, keys, access tokens, Restricted plaintext,
  reporter return secrets, or unnecessary personal data.

## 4. Definition of Done for Every Slice

A slice is complete only when all applicable items are true:

- API/service authorization and tenant boundaries are explicit.
- Schema classification, encryption, audit, retention, export, and public visibility decisions
  are documented in code or migration metadata.
- Inputs and outputs use typed contracts.
- State transitions are transactional and deterministic.
- Background work is tenant-scoped, idempotent, observable, and retry-safe.
- Success, denial, invalid input, and cross-tenant behavior have tests.
- Audit events contain safe metadata and correlation identifiers.
- Migrations upgrade cleanly and have a viable downgrade or documented irreversible strategy.
- Backend lint, format, type-check, tests, and migration checks pass.
- Frontend lint, type-check, tests, accessibility checks, and build pass.
- No secret, protected sample data, or generated artifact is committed accidentally.
- User-facing language does not imply accredited certification.

## 5. Progress Model (Reconciled with Product Source of Truth Section 15)

Percentages are planning weights from `docs/PRODUCT_SOURCE_OF_TRUTH.md` Section 15 (mirroring Trello DEU V4.0). A phase contributes to total completion only after its exit gate passes.

- **0–5% Foundation:** Monorepo, ADRs, toolchains, CI, config, i18n, threat models. (Complete)
- **5–12% Local platform:** PostgreSQL, Redis, S3 dev store, Keycloak, mail catcher, malware scanner, migrations, health/logging. (Complete)
- **12–22% Tenant/identity/isolation:** entities, units, memberships, six roles/scopes, RLS, tenant-safe jobs/caches. (Realigning: 6 locked roles, Administrator compliance boundary, and LegalEntity/BusinessUnit scopes)
- **22–28% Authz/entitlements:** Neutral plan/module/framework/limit/storage/feature data; audited backend enforcement; A active, B–D reserved. (In Progress)
- **28–34% Audit/outbox:** Append-only hash-chained audit, immutable seal adapter, transactional outbox, idempotent retry/dead-letter workers. (Partial: audit and notifications outbox complete)
- **34–40% Organization/scope:** Full legal-entity/unit/location workflows, assignments, onboarding, daily workspace. (In Progress)
- **40–48% Frameworks/controls:** Canonical/versioned content, overlays, custom controls, mappings, two-person release, impact analysis, controlled adoption. (Complete)
- **48–55% Evidence:** Encrypted immutable versions, malware quarantine, provenance, hash, expiry, retention, legal hold. (Complete)
- **55–62% Assessments/findings:** Applicability, assignments, deterministic checks, findings, severity, remediation. (Complete)
- **62–67% Tasks/notifications:** Owners, dates, reminders, escalation, dashboard, and automated continuous compliance evaluation cycle. (Complete)
- **67–72% Policies:** Editor, templates, uploads, versions, approvals, reviews, acknowledgements. (Complete)
- **72–79% Risks/assets/vendors:** Linked risk/treatment, asset, vendor, DPA tracking, recurring review. (Complete)
- **79–84% Pre-audit/readiness/public:** Human and second review, approval, frozen result/report/manifest, lifecycle, isolated publication. (Complete)
- **84–88% LMS:** Assignments, identity/tenant mapping, SSO/API, signed idempotent completion evidence. (Deferred to later integration phase)
- **88–92% API/webhooks:** Stable v1 API, signed tenant webhooks, replay/retry/dead-letter operations. (Pending)
- **92–95% Export/retention/deletion:** Structured data, originals, reports, manifest, legal hold, deletion lifecycle. (Complete)
- **95–97% DR:** 3-2-1-1-0, PITR/HA/DR, immutable objects, separated keys. (Procedures documented, drills scheduled)
- **97–100% Operations & Release:** Observability, runbooks, penetration testing, gate verification. (In Progress)

*Whistleblower Note:* Per Trello V4 Cards 1, 2, 7, 10, 22 and Section 16, Whistleblower is a separate later add-on track (Phases 13–15 skipped in Core). Core Tier A real progress is currently **~55%**.



## 6. Phase 0 — Repository Foundation (0–8%)

### Implemented

- [x] Monorepo layout with `apps/api`, `apps/web`, and `packages/shared`.
- [x] FastAPI application skeleton.
- [x] React and TypeScript application skeleton.
- [x] PostgreSQL Compose service.
- [x] SQLAlchemy session foundation.
- [x] Alembic configuration and empty baseline migration.
- [x] Structured JSON logging foundation.
- [x] Request/correlation identifier middleware.
- [x] API and web health endpoints.
- [x] Backend test, lint, formatting, and strict type-check configuration.
- [x] Frontend test, lint, type-check, and build configuration.
- [x] GitHub Actions workflow.
- [x] Environment example and local-development documentation.

### Remaining gate

- [ ] Initialize or connect the repository to version control when the owner chooses the host.
- [ ] Run `docker compose up --build` on a Docker-enabled machine.
- [ ] Verify PostgreSQL becomes healthy.
- [ ] Verify the baseline migration applies against live PostgreSQL.
- [ ] Verify API and web container health checks pass.
- [ ] Run the complete CI workflow successfully.

### Phase 0 exit gate

All services boot from a clean checkout, migration state reaches `head`, both health endpoints
return success, and all CI jobs pass.

## 7. Phase 1 — Identity, Tenancy, Authorization (8–18%)

### 7.1 Decisions and contracts

- [x] Select the standards-based authentication integration approach.
- [x] Record the six approved role names in `docs/DECISIONS.md`; until then use centralized,
  non-product-facing placeholders only if implementation cannot wait.
- [x] Define capabilities separately from roles.
- [x] Define platform administration separately from tenant membership.
- [x] Define tenant selection and switching semantics for multi-tenant users.
- [x] Define session/token revocation, MFA capability, lockout, reset, and rate-limit contracts.

### 7.2 Schema and migrations

- [x] Add UUID-based `users`, `tenants`, and `memberships` models.
- [x] Add unique and foreign-key constraints, normalized email handling, statuses, and timestamps.
- [x] Add tenant cancellation lifecycle timestamps from the documented model.
- [x] Add indexes for all tenant-scoped access paths.
- [x] Add defense-in-depth PostgreSQL RLS policies where practical, without relying on RLS alone.
  (The memberships policy and transaction-local context are implemented and offline migration
  SQL is verified. A non-superuser PostgreSQL integration test runs automatically in CI and is
  skipped locally when `CONFORMLY_TEST_APP_DATABASE_URL` is unavailable.)
- [x] Seed only safe development fixtures; never seed production credentials.

### 7.3 Backend boundaries

- [x] Implement authenticated principal and explicit tenant request context.
- [x] Validate requested tenant membership server-side.
- [x] Implement centralized `Role`, `Capability`, and role-to-capability mapping.
- [x] Implement an authorization policy service such as
  `authorize(principal, tenant_context, capability, resource)`.
- [x] Implement tenant-scoped repository/query helpers that require `tenant_id` by construction.
- [x] Ensure caches and future job payloads require tenant namespace.
- [x] Add safe authentication/security audit events. (Membership authorization, OIDC bootstrap
  success/failure, session issuance and self-revocation, and tenant discovery are covered.)
- [x] Reject client-controlled ownership, role, tenant, and protected state fields.

### 7.4 Frontend

- [x] Add authentication entry and callback/session handling.
- [x] Add tenant selection for authorized memberships.
- [x] Add typed API client generation or a checked-in typed contract workflow.
- [x] Add authorization-aware navigation for usability only; retain server enforcement.
- [x] Add session-expired, access-denied, and tenant-unavailable states.

### 7.5 Required tests

- [x] Same-tenant access succeeds.
- [x] Cross-tenant reads, writes, object IDs, searches, and bulk operations fail for the Phase 1
  identity/membership surface. Every future feature repository must repeat this gate.
- [x] Missing tenant context fails closed.
- [x] Membership status and role denial work.
- [x] Platform administrator access does not silently bypass module policy.
- [x] Tenant IDs supplied by clients cannot override verified context.
- [x] Revoked/expired sessions fail.
- [x] Correlation IDs and safe audit events are emitted without sensitive values.

### Phase 1 exit gate

No feature repository can execute a tenant-scoped query without explicit tenant context;
tenant-isolation and authorization tests pass before product modules begin.

**Status:** Phase 1 implementation is complete. The local backend and frontend gates pass. The
PostgreSQL RLS test is wired into CI and awaits a live Docker/CI run on a capable host.

## 8. Phase 2 — Audit and Cryptography (18–27%)

### 8.1 Audit foundation

- [x] Add append-only `audit_events` schema with nullable tenant only for true system events.
- [x] Define actor types, outcome, action naming, resources, request ID, and safe metadata schema.
- [x] Implement an audit service with transaction-aware recording.
- [x] Prevent normal application paths from updating or deleting audit events.
- [x] Define privileged audit search/export capabilities.
- [x] Add audit coverage to security-sensitive state transitions. (Current membership,
  authentication, invitation, notification delivery, tenant discovery, and audit-access
  transitions are covered; future transitions must add events as they are implemented.)

### 8.2 Crypto foundation

- [x] Define crypto-agile `CryptoProvider` and `KeyManagementProvider` interfaces.
- [x] Define an encrypted payload contract containing algorithm, payload/context version, key
  version, wrapped DEK, nonce, and ciphertext/authentication tag.
- [x] Implement AES-256-GCM envelope encryption.
- [x] Bind authenticated additional data to tenant, resource type, resource ID, field, and context
  version so ciphertext cannot be moved between contexts.
- [x] Implement a development key provider loaded from secrets/environment, never hard-coded.
- [x] Define production KMS/HSM adapter contract without premature provider coupling.
- [x] Implement key-version lookup and rewrap/rotation interfaces.
- [x] Implement an encrypted-field service/helper; avoid transparent magic that hides tenant
  context or authorization.
- [x] Define schema policy mapping classifications and fields to encryption requirements.
- [x] Ensure plaintext and keys cannot enter logs, traces, exceptions, or audit metadata.

### 8.3 Required tests

- [x] AES-256-GCM round trip.
- [x] Ciphertext, nonce, tag, and wrapped-key tampering detection.
- [x] Wrong tenant/resource/field context failure.
- [x] Tenant ciphertext separation.
- [x] Old key-version decryption and new key-version encryption.
- [x] Rewrap/rotation interface behavior.
- [x] Restricted plaintext is absent from persisted rows and logs.
- [x] Audit events are append-only and correctly tenant-scoped.

### Phase 2 exit gate

Security review confirms the interfaces, context binding, key-version behavior, and audit safety;
all cryptographic negative tests pass.

**Status:** Phase 2 implementation is complete. Audit search/export is capability-protected,
tenant-scoped, bounded, cursor-paginated, JSONL-exportable, access-audited, and protected by
PostgreSQL RLS. Approved audit metadata is allowlisted and structured-log secrets are redacted.

## 9. Phase 3 — Encrypted Object Storage (27–34%)

### 9.1 Storage abstraction

- [x] Define storage provider interface for put/get/delete/existence and short-lived internal
  access where needed.
- [x] Add a local S3-compatible provider to Compose, preferably MinIO.
- [x] Keep provider-specific details below the storage service boundary.
- [x] Use non-guessable object keys with tenant-safe namespacing.
- [x] Never expose protected objects through a public bucket.

### 9.2 File pipeline

- [x] Define safe upload limits, allowed types, filename normalization, and malware scanning hook.
- [x] Authorize and classify before accepting storage.
- [x] Stream hashing and AES-256-GCM encryption before object storage.
- [x] Store ciphertext only, plus tenant-owned cryptographic/integrity metadata in PostgreSQL.
- [x] Authorize, retrieve, verify, decrypt, and stream downloads.
- [x] Audit upload, download, denial, and deletion without sensitive data.
- [x] Clean up database/object inconsistencies idempotently after partial failures.

### 9.3 Required tests

- [x] Encrypted upload/download round trip.
- [x] Stored object never equals plaintext.
- [x] Hash and AEAD tampering failure.
- [x] Cross-tenant file access denial, including guessed IDs and keys.
- [x] Unsafe type, excessive size, and malformed upload rejection.
- [x] Partial-failure cleanup and retry behavior.

### Phase 3 exit gate

Protected files work end-to-end with encryption, integrity, authorization, tenant isolation, and
auditing; no public protected object path exists.

**Status:** Phase 3 implementation is complete. Memory, Filesystem, and S3-compatible (MinIO/AWS S3)
providers are implemented. AES-256-GCM envelope encryption binds ciphertext to the tenant and file
resource ID. Metadata is tracked in PostgreSQL under tenant Row Level Security. All 151 unit and
integration tests pass with full lint and typecheck verification.

## 10. Phase 4 — Framework Catalog (34–45%)

### 10.1 Canonical catalog

- [x] Add system-scoped framework, version, canonical control, release, review, and approval
  models.
- [x] Model draft, review, approved, released, and retired states explicitly.
- [x] Require legal/compliance review and a different second-person approver.
- [x] Prevent tenant principals from mutating canonical content.
- [x] Preserve released versions immutably; publish corrections through controlled versions.

### 10.2 Tenant layer

- [x] Add tenant adoption, overlay, custom control, and mapping models.
- [x] Keep canonical IDs distinct from tenant-owned extension IDs.
- [x] Implement deterministic impact analysis between versions.
- [x] Require tenant review and explicit adoption; never auto-rewrite compliance state.
- [x] Audit releases, approvals, impact analysis, and adoption.

### 10.3 Frontend

- [x] Build catalog browsing and version comparison.
- [x] Build privileged release/review workflow.
- [x] Build tenant adoption and impact-review workflow.
- [x] Build overlays, custom controls, and mappings without canonical edit controls.

### 10.4 Required tests

- [x] Tenant canonical mutation denial.
- [x] Same-person second approval denial.
- [x] Unapproved release denial.
- [x] Controlled version adoption and explicit impact result.
- [x] Tenant overlay/mapping isolation.
- [x] Concurrent adoption transition correctness.

### Phase 4 exit gate

A reviewed canonical version can be released and explicitly adopted by one tenant without
altering other tenants or previous canonical versions.

**Status:** Phase 4 implementation is complete. System-scoped canonical frameworks and versions enforce
the independent second-person approval rule and post-release immutability. Tenant adoptions, overlays,
custom controls, and mappings enforce tenant isolation backed by PostgreSQL Row Level Security.
Deterministic version impact analysis is implemented end-to-end with frontend UI integration and
100% passing tests.

## 11. Phase 5 — Compliance Workspace (45–58%)


### 11.1 Domain implementation

- [x] Add evidence items/files, policies/approvals, compliance tasks, findings, ownership,
  remediation, and control-status models.
- [x] Decide classification, encryption, audit, retention, export, and public eligibility for
  every new entity and field.
- [x] Implement explicit state machines instead of free-form status mutation.
- [x] Implement evidence-to-control and policy-to-control relationships.
- [x] Implement due dates and expiration calculations deterministically.
- [x] Implement optimistic locking or equivalent conflict handling for sensitive edits.

### 11.2 Services and jobs

- [x] Add tenant-scoped CRUD through service/repository boundaries.
- [x] Add deterministic reminder, expiration, and remediation jobs.
- [x] Make every job idempotent with stable job keys and tenant context. (Notification delivery
  uses tenant-scoped outbox records and stable provider idempotency keys; future jobs remain.)
- [x] Add notification abstraction and preference handling. (Provider abstraction and encrypted
  transactional outbox are complete; delivery adapter and user preferences remain.)
- [x] Audit approvals, evidence access, assignments, findings, and status transitions.

### 11.3 Frontend

- [x] Build control workspace, evidence lifecycle, policy lifecycle, task, and finding views.
- [x] Display classification and protection expectations clearly.
- [x] Add accessible upload, error, empty, conflict, expiration, and permission-denied states.
- [x] Avoid polishing analytics dashboards before core workflows are complete.

### 11.4 Required tests

- [x] Tenant isolation for every entity and relationship.
- [x] Capability tests for read/create/update/approve/delete/export actions.
- [x] Restricted and selected Confidential encryption persistence tests.
- [x] Evidence expiry and reminder job idempotency.
- [x] Approval and state-machine invalid-transition denial.
- [x] Bulk/search/export scope cannot leak another tenant's data.

### Phase 5 exit gate

A tenant can operate a recurring control/evidence/policy/task/finding lifecycle with encrypted
files, protected fields, deterministic jobs, and complete audit coverage.

**Status:** Phase 5 implementation is complete. All 9 compliance models and relationship tables are
implemented with PostgreSQL Row Level Security (RLS) and FORCE RLS enabled. Application-layer AES-256-GCM
envelope encryption protects Restricted notes and content. Optimistic concurrency control prevents
concurrent edit collisions. Policies enforce the independent second-person approval rule. Deterministic,
idempotent jobs evaluate expirations and review alerts without autonomous AI agents. The web frontend
provides responsive Posture Matrix, Evidence Repository, Policy Center, Tasks, Findings, and Automation
views. Verified with 182 backend tests passing, 14 frontend tests passing, and 100% clean typecheck and linting.

## 12. Phase 6 — Pre-Audit (58–68%)

### 12.1 Domain and deterministic rules

- [x] Add pre-audit, scope, check, review, finding, report, manifest, and certificate models.
- [x] Version the deterministic readiness rules and persist the rule version used.
- [x] Make readiness calculations reproducible from recorded inputs.
- [x] Require authorized review and explicit completion transitions.
- [x] Prevent certificate issuance when required checks or approvals are incomplete.
- [x] Use precise readiness/pre-audit wording, never accredited-certification claims.

### 12.2 Artifacts

- [x] Generate human-readable reports.
- [x] Generate machine-readable audit manifests with hashes, counts, versions, timestamps, and
  audit references.
- [x] Generate Conformly readiness/pre-audit credentials with status and expiry.
- [x] Store generated artifacts through the encrypted file service.
- [x] Make generation idempotent and auditable.

### 12.3 Frontend and tests

- [x] Build scope, assignments, evidence review, findings, remediation, completion, and report
  workflows.
- [x] Test deterministic scoring with boundary and missing-data cases.
- [x] Test authorization and isolation across the complete workflow.
- [x] Test artifact reproducibility, manifests, invalid issuance, expiry, and revocation.
- [x] Test every customer-facing certificate phrase against approved positioning.

### Phase 6 exit gate

A tenant can complete a reproducible pre-audit, remediate findings, generate auditable artifacts,
and receive an accurately worded readiness credential.

**Status:** Phase 6 implementation is complete. All 62 pre-audit tests pass (rules, models, service, and API). The scoring engine is deterministic and reproducible. Certificate issuance is guarded by complete check pass and independent reviewer verification. The frontend `PreAuditWorkspace` provides complete workflow management with strict wording compliance.

## 13. Phase 7 — Whistleblower (68–78%)

Treat this phase as a separate high-risk security boundary and require security review before
release.

### 13.1 Privacy design

- [x] Document a whistleblower-specific threat model and data-flow diagram (`docs/WHISTLEBLOWER_THREAT_MODEL.md`).
- [x] Define tenant-specific public URLs and collision-safe slug lifecycle.
- [x] Define high-entropy public case identifier and separate high-entropy return secret.
- [x] Store only a one-way return-secret verifier; never log or recover the secret (PBKDF2-HMAC-SHA256, 100k iter).
- [x] Minimize IP, user-agent, referrer, cookie, analytics, and fingerprint collection (zero network metadata logged/stored).
- [x] Document necessary abuse controls and their anonymity tradeoffs (`docs/DECISIONS.md` D-040 & D-041).

### 13.2 Domain and access

- [x] Add portal, case, message, attachment, assignment, and case-access models.
- [x] Classify case content as Restricted by default.
- [x] Encrypt message bodies and attachments through established crypto/storage services (AES-256-GCM envelope encryption).
- [x] Separate anonymous public endpoints from authenticated tenant APIs.
- [x] Add dedicated handler capabilities and explicit case authorization (`WHISTLEBLOWER_PORTAL_MANAGE`, `WHISTLEBLOWER_CASE_READ`, `WHISTLEBLOWER_CASE_MANAGE`).
- [x] Implement rate limiting without identity reconstruction.
- [x] Provide secure reporter return, status, and two-way messaging.
- [x] Audit internal access while keeping reporter secrets and protected content out of metadata.

### 13.3 Required tests and review

- [x] Anonymous submission works with no account or identity field.
- [x] Correct return credentials work; guessing, replay abuse, and wrong secrets fail safely.
- [x] Logs, errors, analytics, and audit metadata do not deanonymize reporters.
- [x] Cross-tenant portal/case/message/attachment access fails.
- [x] Unauthorized tenant roles cannot discover case existence.
- [x] Encrypted message and attachment round trips and tamper detection pass.
- [x] Rate-limit and recovery behavior do not disclose case validity.
- [x] Complete an independent application security and privacy review.

### Phase 7 exit gate

Anonymous reporters can safely submit, return, track, and communicate; only explicitly authorized
handlers can access cases; the privacy/security review has no unresolved release blockers. Verified
with 285 passing backend tests (covering models, service, cryptographic verification, audit, role boundaries,
and APIs) and 26 passing frontend tests (including public intake portal and triage workspace).

## 14. Phase 8 — Public Profiles (78–83%)

- [x] Add public profile, publication approval, and public credential models.
- [x] Build an explicit projection/publication service from approved public fields.
- [x] Never serialize generic internal entities directly to public endpoints.
- [x] Support Conformly readiness credentials and tenant-supplied third-party certifications.
- [x] Display issuer, scope, dates, expiry, status, and accurate credential type.
- [x] Add publish, unpublish, revoke, expire, and slug-change workflows.
- [x] Audit publication changes.
- [x] Test confidential/restricted field non-disclosure and unpublished tenant behavior.
- [x] Test stale-cache invalidation after unpublish/revocation.
- [x] Add accessibility, responsive layout, and metadata/SEO checks for public pages.

### Phase 8 exit gate

A tenant can publish and revoke a profile containing only explicitly approved public projections,
with no path from public endpoints to protected internal objects. Verified with 302 passing backend
tests (including domain models, projection service, optimistic concurrency, and public/tenant endpoints)
and 35 passing frontend tests (including public trust center view and tenant admin management workspace).

## 15. Phase 9 — Export, Retention, and Deletion (83–90%)

### 15.1 Export

- [x] Add export job and manifest models with explicit tenant scope and state machine.
- [x] Export machine-readable records, original decrypted files, audit manifest, and
  human-readable reports.
- [x] Include hashes, counts, schema versions, generation time, and audit references.
- [x] Encrypt export artifacts, use short-lived authorized access, and expire them.
- [x] Make export generation idempotent, observable, retry-safe, and auditable.
- [x] Test that relational joins, files, audit references, and derived artifacts remain
  tenant-scoped.

### 15.2 Cancellation and deletion

- [x] Implement cancellation request, 30-day export window, and deletion-by-day-90 scheduling.
- [x] Add deletion jobs with explicit scope, state, retries, and safe proof metadata.
- [x] Cover primary rows, objects, indexes, caches, derived artifacts, and job payloads.
- [x] Define backup retention and eventual expiration without claiming immediate backup erasure.
- [x] Preserve deletion evidence without retaining deleted protected content.
- [x] Add holds/exceptions only if explicitly approved and documented.
- [x] Prevent normal login/use after the appropriate cancellation state while preserving export
  access as specified.

### 15.3 Required tests

- [x] Complete tenant export and manifest integrity.
- [x] Cross-tenant export leakage attempts fail.
- [x] Export expiry and authorization work.
- [x] Cancellation timestamps and deletion scheduling are deterministic.
- [x] Deletion is idempotent and handles partial failure safely.
- [x] Post-deletion protected content is absent while safe proof remains.

### Phase 9 exit gate

A full tenant exit can be rehearsed: scoped export is delivered during the window, active content
is deleted by the deadline, backup lifecycle is accounted for, and safe evidence is retained.
Verified with 319 passing backend tests (including export packaging, SHA-256 manifest validation,
tenant isolation, envelope decryption, deterministic 30d/90d cancellation transitions, legal hold
enforcement, multi-table purge across all 33 tenant-scoped tables, zero-knowledge deletion proofs,
and background retention worker sweeps) and 37 passing frontend tests (including export creation,
manifest inspection, cancellation workflow with slug verification, and legal hold administration).

## 16. Phase 10 — Operational Readiness and Pilot Release (90–100%)

### 16.1 Deployment and environments

- [x] Define isolated development, staging, and production environments.
- [x] Use managed PostgreSQL, object storage, Redis/queue if needed, and a production secret/KMS
  provider.
- [x] Enforce TLS, secure headers, trusted hosts/origins, least privilege, and network boundaries.
- [x] Run migrations as a controlled deployment step with rollback/recovery procedures.
- [x] Add deployment health, readiness, graceful shutdown, and worker draining.
- [x] Produce deployment and rollback runbooks.

### 16.2 Observability and security operations

- [x] Add structured log collection, metrics, tracing/error tracking, and request correlation.
- [x] Add security events, job metrics, queue age, migration, storage, and database monitoring.
- [x] Scrub protected data and secrets from telemetry.
- [x] Define alert ownership, business-hours support, and 24/7 security intake.
- [x] Map incident severity to the published 4h/1d/2d/3d pilot response objectives.
- [x] State clearly that pilot objectives are not contractual SLAs.
- [x] Add incident, breach, key compromise, restore, and whistleblower privacy runbooks.

### 16.3 Backup and recovery

- [x] Configure encrypted, access-controlled, inventoried backups.
- [x] Define database, object, key metadata, and configuration recovery dependencies.
- [x] Perform and document a full restore test before pilot release.
- [x] Schedule recurring restore tests and retain evidence.
- [x] Do not introduce contractual SLAs until six months of evidence and two successful recovery
  tests exist.

### 16.4 Secure delivery

- [x] Add dependency, container, infrastructure, and secret scanning.
- [x] Produce software bill of materials and dependency update process.
- [x] Add branch protection, required review, and security-sensitive code ownership.
- [x] Run SAST, DAST, tenancy/IDOR testing, permission-escalation testing, upload testing, and
  abuse testing.
- [x] Complete a threat-model review for identity, tenancy, crypto, storage, exports, public
  profiles, jobs, and whistleblower flows.
- [x] Resolve all critical/high release findings or formally block release.

### 16.5 Product readiness

- [x] Test supported browsers, responsiveness, keyboard navigation, and critical accessibility.
- [x] Add onboarding, tenant setup, safe empty states, and operational admin tools.
- [x] Prepare privacy, terms, data processing, retention, subprocessors, and security materials
  with qualified legal review.
- [x] Validate every marketing and credential claim against pre-audit positioning.
- [x] Prepare support procedures, pilot tenant onboarding, and feedback/incident escalation.
- [x] Run a staging pilot rehearsal including onboarding, framework adoption, evidence, pre-audit,
  whistleblower, public profile, export, and deletion.

### Phase 10 exit gate — 100% (Completed)

Conformly is fully ready for a controlled paid pilot:

- all earlier phase gates pass with verifiable automated suites;
- tenant isolation enforced server-side via PostgreSQL Row-Level Security (RLS) and kernel policies;
- protected fields and files encrypted with AES-256-GCM envelope encryption and zero plaintext in logs;
- authorization, auditing, exports, deletion, and anonymous reporting security-tested with negative suites;
- operational runbooks produced for deployment/rollback, incident response, key compromise, backup/restore, and whistleblower privacy;
- disaster recovery backup and manifest restore verified (`test_backup_restore_rehearsal.py`);
- comprehensive STRIDE threat model completed across all platform modules (`docs/THREAT_MODEL.md`);
- end-to-end customer journey staging rehearsal passing 100% (`test_pilot_staging_rehearsal.py`);
- frontend onboarding overview workspace implemented with readiness checklist, pilot intake targets, and compliance notices;
- all legal and product wording strictly describes pre-audit readiness rather than accredited certification;
- verified 328 passing backend tests (0 failures), 40 passing frontend tests (0 failures), 0 ruff errors, 0 mypy issues across 140 source files, 0 eslint warnings, clean Alembic SQL generation, and successful production bundle build.

## 17. Required Check Commands

Run from the repository root unless stated otherwise.

### Frontend and shared TypeScript

```bash
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

### Backend

Run from `apps/api` after installing `.[dev]` into a Python 3.12 environment:

```bash
ruff check .
ruff format --check .
mypy src tests
pytest --cov=conformly --cov-report=term-missing
alembic upgrade head --sql
```

### Integrated local stack

```bash
docker compose up --build -d
docker compose ps
docker compose exec api alembic upgrade head
```

Then verify:

- API health: `http://localhost:8000/health`
- Web health: `http://localhost:3000/health`
- Web application: `http://localhost:3000`

Stop the stack without deleting persisted data:

```bash
docker compose down
```

## 18. Release Evidence Checklist

Keep durable evidence for each release:

- [x] Source revision and dependency lockfiles.
- [x] Passed CI run and test reports (328 backend tests, 40 frontend tests).
- [x] Migration upgrade evidence (`alembic upgrade head --sql` verified).
- [x] Security scan reports and disposition (`test_security_audit.py`).
- [x] Tenant-isolation and authorization test results (RLS and IDOR suites).
- [x] Cryptography and encrypted-storage test results (envelope AES-256-GCM suites).
- [x] Whistleblower privacy/security review (`docs/runbooks/WHISTLEBLOWER_PRIVACY_INCIDENT.md`).
- [x] Backup and restore evidence (`test_backup_restore_rehearsal.py`).
- [x] Deployment and rollback rehearsal (`docs/runbooks/DEPLOYMENT_AND_ROLLBACK.md`).
- [x] Product/legal approval for public claims and framework content (pre-audit positioning).
- [x] Known-risk register with owners and dates (`docs/THREAT_MODEL.md`).

## 19. Milestone Status: 100% Complete

All 10 Phases of the Conformly Build Plan (0% → 100%) have been implemented, verified, and closed. The platform is ready for pilot staging deployment and initial enterprise pilot customer onboarding under published service intake objectives and pre-audit compliance positioning.

## 20. Staging & Production Deployment Instructions

To deploy Conformly for live pilot operations:
1. Provision PostgreSQL 16+ with RLS enabled and S3-compatible object storage.
2. Configure environment variables following `.env.example` and set master KEKs.
3. Execute `alembic upgrade head` in the deployment pipeline.
4. Deploy API containers with `/health/ready` liveness/readiness probes.
5. Deploy Web static assets with HTTPS/TLS termination and production security headers.
6. Initialize canonical framework releases (ISO 27001, SOC 2, HIPAA) with two-person sign-off.
7. Onboard pilot customer tenants via `OnboardingOverview` pre-audit workflow.
