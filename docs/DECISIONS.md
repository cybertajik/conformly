# Architecture and Product Decisions

This file records decisions that should not be casually reversed during implementation.

## D-001 — Tenancy
**Decision:** Multi-tenant architecture with strict tenant isolation.

## D-002 — Data Classification
**Decision:** Fixed levels: Public, Internal, Confidential, Restricted. Optional tags may supplement them.

## D-003 — Cross-Tenant Analytics
**Decision:** Operational metadata only. Never aggregate tenant content across tenants.

## D-004 — Application-Layer Encryption
**Decision:** Encrypt all files and Restricted fields; encrypt selected Confidential fields.

## D-005 — Core Encryption
**Decision:** AES-256-GCM with server-side envelope encryption.

## D-006 — E2EE
**Decision:** No browser-to-browser E2EE for core compliance data in the MVP because workflows/reports must run server-side.

## D-007 — Crypto Agility
**Decision:** Build crypto-agile interfaces now.

## D-008 — Post-Quantum Readiness
**Decision:** AES-256-GCM now; add standardized hybrid/PQC transport when sufficiently mature.

## D-009 — Backup Confidentiality
**Decision:** Strong encryption is the primary confidentiality control. Storage chunking must not be relied upon as the main security mechanism.

## D-010 — Canonical Framework Ownership
**Decision:** Tenants cannot modify canonical catalog content.

## D-011 — Tenant Extensions
**Decision:** Tenants may add overlays, custom controls, and mappings.

## D-012 — Framework Updates
**Decision:** Show impact analysis and require controlled tenant adoption.

## D-013 — Canonical Release Approval
**Decision:** Legal/compliance review plus independent second-person approval.

## D-014 — Tier A Roles
**Decision:** Fixed six-role set. No custom roles in first paid MVP.

**Open implementation item:** exact public-facing names of the six roles must be taken from the approved product source if available; do not invent without recording a decision.

## D-015 — MVP Automation
**Decision:** Deterministic automation only.

## D-016 — Cancellation Retention
**Decision:** 30-day export period; deletion by day 90.

## D-017 — Cancellation Export
**Decision:** Export includes machine-readable data, original files, audit manifest, and human-readable reports.

## D-018 — Support Coverage
**Decision:** Business-hours support plus 24/7 security intake.

## D-019 — Pilot Response Objectives
**Decision:** 4h / 1d / 2d / 3d.

## D-020 — SLA Positioning
**Decision:** Published objectives, not contractual SLA, during paid pilot.

## D-021 — SLA Readiness
**Decision:** Require six months of evidence plus two recovery tests before contractual service levels.

## D-022 — Future Contractual SLA Scope
**Decision:** Availability + recovery + response.

## D-023 — Future SLA Remedy
**Decision:** 25% credit cap plus exit after 3 affected months.

## D-024 — Credits
**Decision:** Automatic credits with 30-day dispute window.

## D-025 — Whistleblower
**Decision:** Tenant-specific URL, anonymous reporting, secure anonymous tracking, strict privacy and access boundaries.

## D-026 — Product Positioning
**Decision:** Initial product is a pre-audit/compliance operations platform, not an accredited certification body.

## D-027 — Public Profile
**Decision:** Tenant may publish Conformly readiness/pre-audit credentials and customer-provided third-party certifications.

## D-028 — Authentication Integration
**Decision:** Use provider-neutral OpenID Connect (OIDC) for interactive authentication. Conformly
owns tenant membership, authorization, and session revocation state. The application validates
issuer, audience, signature, expiry, and nonce/state as applicable. Tenant access is never derived
directly from untrusted identity-provider claims.

## D-029 — Tier A Role Names
**Decision:** The fixed six tenant roles are `Owner`, `Administrator`, `Compliance Manager`,
`Auditor`, `Contributor`, and `Viewer`.

Role-to-capability mapping is centralized. `Owner` is not a platform administrator, and platform
administration is modeled separately from tenant membership.

## D-030 — Tenant Selection
**Decision:** A signed-in user may select only an active tenant for which they have an active
membership. Verified tenant context is resolved server-side for every request. A client-supplied
tenant identifier is a selector, never authorization evidence.

## D-031 — Identity Security Contract
**Decision:** Authentication must support provider-enforced MFA, OIDC expiry, server-side session
revocation, rate limiting, and security audit events. Account lockout and password reset remain
identity-provider responsibilities while Conformly does not offer local password authentication.

## D-032 — OIDC Email Trust and Session Bootstrap
**Decision:** The public web client uses Authorization Code with PKCE and submits the resulting
access token to Conformly's session-bootstrap endpoint. Conformly independently validates the
token and requires the trusted provider to assert `email_verified=true` before creating or linking
an application identity. A matching email from a different issuer/subject is never linked
automatically. Tenant authorization continues to come only from Conformly membership records.

## D-033 — Tenant Audit Access
**Decision:** `Owner`, `Administrator`, and `Compliance Manager` may search and export tenant audit
events. `Auditor` may search but not export. `Contributor` and `Viewer` have no audit access.
Synchronous exports are tenant-scoped, JSON Lines formatted, audited, and capped at 10,000 records;
larger exports require a future bounded background-export workflow.

## D-034 — Encrypted Object Storage Architecture
**Decision:** Application-layer encrypted object storage with pluggable backends (Memory, Filesystem,
and S3-compatible including MinIO/AWS S3). Every uploaded file is validated, normalized, scanned for
malware, and encrypted using AES-256-GCM envelope encryption with a unique DEK before persistence.
Ciphertext is stored under non-guessable, tenant-namespaced keys
(`tenants/{tenant_id}/files/{file_id}/{random_token}.enc`). No plaintext is ever written to object
storage. Cryptographic/integrity metadata (both plaintext SHA-256 and ciphertext SHA-256, wrapped
DEKs, nonces, classification) is stored in PostgreSQL under tenant Row Level Security. File
download verifies ciphertext hash, decrypts payload, verifies plaintext hash, and streams bytes to
authorized callers. File operations are protected by capability checks (`file:read`, `file:write`,
`file:delete`) and audited without exposing secret or plaintext data.

## D-035 — Canonical Framework Catalog and Tenant Overlay Architecture
**Decision:** System-scoped canonical frameworks, versions, and controls are platform-owned,
strictly immutable once released, and have no `tenant_id`. Only platform administrators may
manage canonical content. Version releases require legal/compliance review plus independent
second-person approval (`approver != creator`). Tenants can never mutate canonical content, but
may create `TenantControlOverlay`, `CustomControl`, and `ControlMapping` entities, all strictly
partitioned and enforced by PostgreSQL Row Level Security (RLS). Framework version upgrades
calculate deterministic impact reports (added, removed, modified, and unchanged controls along
with tenant warning flags) and require explicit tenant adoption without automatic compliance state
rewriting.

## D-036 — Compliance Workspace Architecture
**Decision:** Compliance operations models (`EvidenceItem`, `Policy`, `ComplianceTask`, `Finding`,
`ControlStatusRecord`, `UserNotificationPreference`, and associated linking tables) are strictly
multi-tenant, tenant-partitioned in PostgreSQL, and protected by PostgreSQL Row Level Security (RLS)
with `FORCE ROW LEVEL SECURITY` enabled.
1. **Application-Layer Field Encryption:** `Restricted` and sensitive `Confidential` fields (e.g.
   `restricted_notes`, `restricted_content`) require AES-256-GCM envelope encryption via
   `EncryptedFieldCodec` before database persistence. Plaintext is never stored in database columns.
2. **Optimistic Concurrency Control:** All mutable compliance entities maintain an integer `version`
   column incremented on every state transition or update. Callers must pass `expected_version`;
   mismatches immediately raise HTTP 409 Conflict.
3. **Independent 2-Person Policy Approval:** Self-approval of policies is strictly forbidden. The
   approver must be a distinct authorized user from the policy author/owner
   (`approver_user_id != owner_user_id`).
4. **Deterministic Automation & Notification Outbox:** Compliance automation jobs (evidence expiration,
   overdue task scanning, policy review alerts) run purely deterministic, idempotent logic without
   autonomous AI agents. Notifications are enqueued in `NotificationOutbox` using stable, SHA-256-based
   idempotency keys preventing duplicate alerts.

## D-037 — Bugbot concurrency, references, and deletion hardening

- Compliance version columns participate in each ORM UPDATE predicate, not only a
  read-time comparison. A stale database write returns HTTP 409; existing control
  status records require an expected version. Background ORM updates receive the
  same database protection.
- Assignable users must have active membership in the referenced tenant. Linked
  evidence, policies, and custom controls must belong to that tenant. Canonical
  mapping endpoints must belong to released or retired versions. Comparison requires
  authentication and only platform administrators may compare unpublished versions.
- Adoption locks the tenant parent row, including first adoption. Migration
  `20260912_0013` adds a partial unique active-adoption index. Existing duplicates
  cause migration failure and require explicit reconciliation, never silent deletion.
- File deletion first commits `DELETE_PENDING` plus a deletion-request audit event.
  Only committed intents may remove ciphertext. Completion is separately committed
  and audited. Failures retain an inaccessible, retryable pending record. Repeat the
  same DELETE request to retry; authorized maintenance can call
  `finalize_pending_deletions` on a fresh transaction to drain up to 100 tenant intents.
  Provider failures return HTTP 202. Missing objects are safely retried idempotently.
- Upload bodies are bounded before multipart parsing, including chunked requests;
  multipart overhead is limited to 1 MiB above the configured file limit. File reads
  themselves are bounded to the limit plus one byte.
- Task PATCH and completion use the same transition checks and completion metadata.
  Pending, in-progress, and overdue tasks can complete or cancel; completed/cancelled
  tasks must reopen to pending first. Reopening clears completion attribution.
  Overdue remains a deterministic-job transition, not a caller-selected state.

## D-038 — Pre-Audit Readiness Assessment Architecture

Pre-audits are tenant-scoped readiness assessments that evaluate compliance workspace data (evidence items, policies, tasks, findings, control implementation statuses) and generate deterministic readiness scores and gap findings.
1. **Pre-Audit Readiness vs. Certification Body:** Conformly is an audit preparation and operations platform, not an accredited certification body. All customer-facing text, API contracts, generated reports, and badge credentials explicitly use "pre-audit readiness" terminology and deliberately omit certification body claims.
2. **Deterministic Versioned Scoring Engine:** Readiness scores are calculated using a pure-function rules engine versioned by semantic version strings (`CURRENT_RULE_VERSION = "v1.0.0"`). Each check result persists the exact rule version and a JSON snapshot of input criteria (`evidence_count`, `policy_count`, `open_findings`, `implementation_status`) ensuring reproducibility.
3. **Artifact Integrity:** Reports and manifests are generated as cryptographic artifacts. Manifests include a SHA-256 hash digest of all evaluated data.
4. **Readiness Credential Guardrails:** Issuing a Conformly Pre-Audit Readiness Credential requires: (a) pre-audit state is `completed`, (b) independent second-person reviewer approval (`reviewed_at` is set, `reviewer_user_id != lead_user_id`), and (c) all evaluated checks have passed (zero `FAIL` results). Credentials carry validity windows and explicit revocation workflows with auditable justifications.

## D-039 — Pre-Audit State Machine & Multi-Tenant RLS Boundaries

1. **State Machine Transitions:** Pre-audits follow a strict finite-state transition lifecycle:
   - `planning` -> `in_progress`, `cancelled`
   - `in_progress` -> `in_review`, `cancelled`
   - `in_review` -> `completed`, `in_progress` (returned for remediation), `cancelled`
   - `completed`, `cancelled` are terminal states.
2. **Review Independence:** A pre-audit lead cannot act as their own reviewer (`reviewer_user_id != lead_user_id`). Only the designated reviewer can complete the review.
3. **Database Tenant Isolation:** All pre-audit tables (`pre_audits`, `pre_audit_scopes`, `pre_audit_checks`, `pre_audit_findings`, `pre_audit_reports`, `pre_audit_manifests`, `pre_audit_certificates`) have `tenant_id` foreign keys with `CASCADE` delete and PostgreSQL Row Level Security (RLS) with `FORCE ROW LEVEL SECURITY`.

## D-040 — Whistleblower Architecture & One-Way Return Secret Verifier

1. **Anonymous Reporting Path:** A dedicated public route `/v1/public/whistleblower/{slug}` allows submitting reports without requiring user accounts, sessions, OIDC tokens, cookies, email addresses, or personal identity markers.
2. **Zero Identity Tracking:** The API deliberately strips and does not log client IP addresses, browser user-agents, or tracking headers in case records, access logs, or audit metadata.
3. **Cryptographic One-Way Return Secret:** When a case is submitted, a 256-bit CSPRNG return secret is generated and returned to the reporter exactly once. The database stores only a salted PBKDF2-HMAC-SHA256 verifier (100,000 iterations). Plaintext secrets are never persisted and cannot be recovered if lost. Return verification uses constant-time `hmac.compare_digest`.
4. **Application-Layer Envelope Encryption:** Case summaries and message bodies are encrypted at the application layer using AES-256-GCM via `EncryptedFieldCodec` before SQL persistence.

## D-041 — Whistleblower Data Isolation & Handler Role Restrictions

1. **Strict Capability Isolation:** Whistleblower module capabilities (`whistleblower:portal_manage`, `whistleblower:case_read`, `whistleblower:case_manage`) are restricted strictly to `TenantRole.OWNER`, `TenantRole.ADMINISTRATOR`, and `TenantRole.COMPLIANCE_MANAGER`. General compliance roles (`AUDITOR`, `CONTRIBUTOR`, `VIEWER`) are denied with HTTP 403.
2. **PostgreSQL Row Level Security:** All whistleblower tables (`whistleblower_portals`, `whistleblower_cases`, `whistleblower_messages`, `whistleblower_attachments`, `whistleblower_case_assignments`) enforce tenant isolation via PostgreSQL RLS with `FORCE ROW LEVEL SECURITY`.
3. **Public Lookup Policy:** An explicit RLS policy allows unauthenticated public read access to `whistleblower_portals` where `is_active = true` to render the intake interface by slug, while keeping cases, messages, and internal configuration completely isolated.

## D-042 — Public Profile Projection Isolation & Publication Approval Boundary

1. **Projection Isolation:** Public compliance profile endpoints (`GET /v1/public/profiles/{slug}`) must never serialize or query internal operational entities (`tenants`, `users`, `pre_audits`, `policies`, `evidence_items`, `findings`) directly. Instead, public profiles are persisted in dedicated, explicitly projected tables (`public_profiles`, `public_credentials`, `public_statements`).
2. **Explicit Publication Lifecycle:** Profiles remain unpublished (`is_published = false`) by default and require deliberate publication by an authorized role (`TenantRole.OWNER`, `TenantRole.ADMINISTRATOR`, or `TenantRole.COMPLIANCE_MANAGER`). Unpublished profiles return HTTP 404 with no indication of tenant existence.
3. **Collision-Safe Slugs:** Profile slugs are lowercase alphanumeric strings with hyphens (`[a-z0-9-]+`) enforced unique across all tenants.
4. **Cache Control & Freshness:** The public profile endpoint issues strong `ETag` headers and `Cache-Control: public, max-age=300, must-revalidate`. Updates, unpublishing, or credential revocations immediately invalidate cached projections.

## D-043 — Public Credential Verification & Dual Badge Scope

1. **Dual Credential Display:** Public profiles support two distinct classes of credentials:
   - `conformly_readiness`: Derived strictly from an active, verified `PreAuditCertificate`. It carries the clear non-accredited disclaimer: *"Conformly is an audit-readiness and compliance operations platform, not an accredited certification body."*
   - `third_party`: Customer-provided external certifications (e.g. ISO/IEC 27001, SOC 2 Type II, HIPAA, PCI-DSS) with issuer name, scope description, validity dates, and optional external verification URLs.
2. **Revocation & Expiry:** Credential records track active, expired, and revoked states. Revoking an issued pre-audit credential automatically propagates to its linked public credential, setting `status = revoked` and excluding it from active public verification.
3. **Role Authorization:** `public_profile:manage` is restricted to `TenantRole.OWNER`, `TenantRole.ADMINISTRATOR`, and `TenantRole.COMPLIANCE_MANAGER`. All tenant roles have `public_profile:read` to review internal previews and drafts.

## D-044 — Tenant Data Export Packaging, Cryptographic Integrity & Short-Lived Access

1. **Comprehensive Data Exit Packaging:** Every tenant export job packages:
   - Structured machine-readable datasets (`data/*.json`): tenant profile, memberships, framework adoptions, custom controls, control mappings, control posture, policies and versions, evidence item metadata, compliance tasks, findings, pre-audit assessments and check evaluations, public profile records, and sanitized whistleblower case counts/statuses.
   - Decrypted original files (`files/*`): all stored evidence items and attachments are decrypted via `StorageService` envelope encryption, with plaintext SHA-256 hashes re-verified.
   - Audit manifest (`manifest.json`): dataset schema versions, individual file SHA-256 digests, record counts, and a master SHA-256 digest of the manifest.
   - Human-readable compliance reports (`reports/*.md`): Markdown reports summarizing framework posture, pre-audit readiness, and data inventory.
2. **Encrypted Storage & Short-Lived Access:** The resulting ZIP archive is encrypted at the application layer using AES-256-GCM via `StorageService` (`classification = "Restricted"`). Access is granted only to authorized roles (`Capability.EXPORT_READ`) and subject to an expiration timestamp (`expires_at`, default 7 days for on-demand exports, or up to `export_until` for cancellation exports).
3. **Idempotence & Tenant Isolation:** Export jobs are strictly scoped to the requesting tenant. Cross-tenant reads or joins are prohibited at the database, storage, and service boundaries.

## D-045 — Tenant Cancellation Lifecycle, Deletion Scheduling & Proof Verification

1. **Deterministic Cancellation Timeline:**
   - **Day 0:** `Role.OWNER` initiates cancellation. Tenant transitions to `TenantStatus.CANCELLING`. Normal write operations are blocked. `cancellation_requested_at` is stamped.
   - **Days 1–30:** 30-day export window (`export_until = cancellation_requested_at + 30 days`). Authorized tenant users can generate and download data exports.
   - **Days 31–89:** The export window closes. Tenant sessions are suspended (`TenantStatus.SUSPENDED`), blocking all normal logins.
   - **Day 90:** The automated `DeletionJob` runs at `deletion_due_at = cancellation_requested_at + 90 days`.
2. **Legal Hold Override:** Tenants support a `legal_hold: bool` flag. When active, deletion execution is halted with an `ON_HOLD` state and an audit event, preserving records until the hold is formally released by compliance administrators.
3. **Multi-Table Purge & Verifiable Deletion Proof:**
   - Deletion removes all operational customer records across all 8 tenant-scoped modules (`public_profiles`, `whistleblower_*`, `pre_audit_*`, `compliance_*`, `framework_*`, `stored_files`, `memberships`), and purges underlying objects from the storage provider backend.
   - Upon purge, a cryptographic `DeletionProof` record is created storing the execution timestamp, list of purged tables, count of storage objects removed, and a SHA-256 digest of the deletion manifest. No customer plaintext or protected data is retained in the proof.
   - Tenant status transitions to `TenantStatus.DELETED`.
4. **Cold Backup Expiration:** Active systems purge customer content on day 90. Cold backups adhere to an explicit rolling expiration lifecycle (e.g. 30 days point-in-time retention) without claiming immediate physical erasure of immutable distributed snapshots.

## D-046 — Data-exit and anonymous-report hardening

- Manual deletion execution requires `retention:manage`, an authenticated tenant
  context matching the job, a scheduled job state, and a due timestamp. External
  objects are deleted idempotently before their metadata; any provider failure keeps
  the job scheduled and preserves database metadata for retry. No deletion proof is
  emitted until every required object and row is successfully processed.
- Full data-exit exports include decrypted Restricted policy content and evidence
  notes inside the encrypted export archive. Every required original file is
  fail-closed: one missing, corrupt, or undecryptable original fails the export job.
- New whistleblower case titles and categories are encrypted with the case-bound
  envelope-encryption context. Nullable plaintext columns exist only for migration
  compatibility and are never populated by new submissions. Deployments with legacy
  rows must encrypt those two fields using the application key before clearing them.
- Anonymous whistleblower operations use privacy-preserving fixed-window limits keyed
  by hashed portal/case identifiers. The limiter stores no IP address, user agent,
  secret, or reporter identity. Production deployments with multiple API processes
  must replace the process-local store with a shared implementation using the same
  interface before horizontal scaling.

## D-047 — Alignment with Canonical Product Source of Truth (Trello V4.0)

1. **Product Authority Reconciliation:** Reconcile all local architectures and implementation contracts with `docs/PRODUCT_SOURCE_OF_TRUTH.md` (canonical mirror of Trello DEU V4.0).
2. **Canonical 6 Locked Roles:** Supersede D-029 role names with the locked set from Trello V4 Card 11:
   - `Tenant Owner` (`owner`)
   - `Tenant Administrator` (`administrator`)
   - `Compliance Manager` (`compliance_manager`)
   - `Control Owner` (`control_owner`)
   - `Reviewer` (`reviewer`)
   - `Employee` (`employee`)
3. **Tenant Administrator Compliance Boundary:** Enforce the strict product rule that `Tenant Administrator` manages users, SSO, settings, and memberships, but is explicitly denied access to compliance content (evidence, policies, control status, tasks, findings, pre-audits).
4. **Whistleblower Add-on Decoupling:** Whistleblower is formally decoupled from Core Tier A navigation and core release gates. All whistleblower code is preserved under an add-on boundary and protected with a module entitlement check (`require_module("whistleblower")`).
5. **Organizational Scopes:** Implement `LegalEntity`, `BusinessUnit`, and `Location` models partitioned by tenant with PostgreSQL RLS. Memberships can be scoped to specific organizational entities.
6. **Entitlements Engine:** Implement data-driven module enablement, storage limits, and member limits enforced server-side.
7. **Tier A Operational Registers:** Implement the **Risk Register** (with treatments and control links), **Asset Register**, and **Vendor / Third-Party Register** in Core Tier A.

## D-048 — Organizational Authorization, Scoped Reviewer Access, Assessor Engagements, and Export Separation

1. **Administrator Export Revocation:**
   - Withholding normal compliance content access (evidence, policies, findings, controls) from `Role.ADMINISTRATOR` while permitting full exports would bypass that core separation, as full exports contain decrypted evidence archives, policies, and findings.
   - `Capability.EXPORT_CREATE` and `Capability.EXPORT_READ` are permanently revoked from `Role.ADMINISTRATOR`. Full tenant compliance archives can only be initiated and retrieved by `Role.OWNER` and `Role.COMPLIANCE_MANAGER`.
   - `Capability.EXPORT_READ` is also revoked from `Role.REVIEWER` to prevent bypassing assigned-material scoping through tenant-wide export archives.
2. **Central Organizational Scope Enforcement:**
   - Central authorization policy (`authorize_resource`) explicitly validates `legal_entity_id` and `business_unit_id` boundaries on resources against the caller's active `TenantContext`.
   - Organizational services (`list_legal_entities`, `list_business_units`, `list_locations`, `create_business_unit`, `create_location`) strictly filter and constrain operations to the caller's organizational scope.
3. **Reviewer Assigned-Material Scoping:**
   - `Role.REVIEWER` (and legacy `AUDITOR`) access is restricted to material specifically assigned to or owned by that user (`owner_user_id == user_id` or `user_id in assigned_user_ids`).
   - Direct retrieval of unassigned compliance resources raises `AuthorizationDeniedError`.
   - Listings (`list_evidence`, `list_tasks`, `list_findings`, `get_control_status_matrix`) automatically scope results to the assigned user.
4. **Temporary Assessor Engagements & Workforce Boundaries:**
   - External Advisors / Assessors (`is_external_advisor=True`) must have a time-limited engagement (`expires_at` is required).
   - Assessors and Reviewers can NEVER mutate customer evidence (`EVIDENCE_MANAGE`, `FILE_WRITE`, `FILE_DELETE`, `CONTROL_STATUS_MANAGE`, `POLICY_MANAGE`). Any such attempt is immediately denied at authorization.
   - Staff / Workforce users (`is_workforce=True`) have **no standing access** to customer tenant data. Access requires an active, unexpired engagement (`expires_at > now`).
   - Expired engagements immediately fail closed during tenant context resolution (`TenantContextError`) and central authorization (`AuthorizationDeniedError`).

## Decision Process

### Planning record — 2026-09-13: global framework and add-on expansion

- **Authority:** current explicit Product Owner request; not a new Trello snapshot.
- **Artifact:** `docs/GLOBAL_FRAMEWORK_CATALOG.md`, linked from the product source of truth.
- **Authorized direction:** expand regional coverage and plan basic A / progressively advanced
  B–D framework packages, with whistleblower and LMS add-on planning.
- **Proposed, not approved:** exact pack allocations, initial launch selection, six additional
  add-on families, and any new commercial or deployment arrangements.
- **Preserved baseline:** Tier A Core scope and training-evidence integration, isolated
  whistleblower architecture, universal security requirements, Germany-only hosting, and
  human-reviewed deterministic readiness workflows. Geographic coverage is not hosting approval.
- **Implementation boundary:** no application changes in this planning task. Items 1–4 are being
  implemented elsewhere according to the Product Owner and must still pass their own verification.
- **Gate:** reconcile specific packaging changes on Trello DEU; verify authoritative sources,
  content rights, applicability and versions; obtain legal/compliance and independent approval;
  test packs before marking them released. A discovery entry is not supported framework content.

### Procedure

When Codex encounters a missing architectural choice:
1. inspect existing docs,
2. choose the simplest secure option,
3. avoid irreversible architecture,
4. add the decision here if material,
5. add migration/upgrade notes if applicable.

