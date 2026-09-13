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

## D-049 — Audit Hash Chaining and Immutable Sealing (Trello Section 12)

1. **Deterministic SHA-256 Hash Chaining:**
   - Every tenant audit event is sequentially numbered per tenant (`sequence_number`) and bound cryptographically to its direct predecessor (`prev_hash`) using SHA-256 over normalized canonical attributes (`sequence_number`, `occurred_at`, `tenant_id`, `actor_type`, `actor_id`, `action`, `resource_type`, `resource_id`, `request_id`, `outcome`, `metadata`, `prev_hash`).
   - The first tenant record links to the genesis zero hash (`0000000000000000000000000000000000000000000000000000000000000000`).
2. **Immutable Audit Seals & Merkle Tree Rooting:**
   - Introduced `AuditSeal` model with PostgreSQL Row-Level Security. Seals group sequences of audit events into tamper-evident batches with calculated Merkle roots and cryptographic signature digests.
   - Seals verify both backward event-hash chains and batch Merkle integrity.
3. **Immutability Enforcement:**
   - Registered SQLAlchemy ORM listeners (`before_update`, `before_delete`) to reject mutation or deletion of committed `AuditEvent` and `AuditSeal` rows with `AuditImmutabilityError`.
   - Any manual or out-of-band SQL tampering invalidates the cryptographic verification function `verify_audit_chain`.

## D-050 — Production Key Management Service Provider (Vault / OpenBao)

1. **Vault / OpenBao Transit Engine Provider:**
   - Implemented `VaultKmsProvider` implementing the `KeyManagementProvider` protocol, supporting remote envelope key wrapping (`transit/encrypt`) and unwrapping (`transit/decrypt`) with base64 ciphertext and context-bound authenticated encryption.
   - Provider factory `get_kms_provider(settings)` dynamically selects between `LocalKeyManagementProvider` (dev/test) and `VaultKmsProvider` (production) based on `CONFORMLY_KMS_PROVIDER`.
2. **Key Lifecycle & Crypto-Agility:**
   - Key rotation occurs via Vault key-version advancement (`vault_key_name: str = "conformly-master-key"`). Envelope decryption supports multiple key versions without requiring immediate re-encryption of existing ciphertext.

## D-051 — Keycloak Customer and Workforce Realms & Privileged MFA Enforcement

1. **Dual-Realm Keycloak Topology:**
   - `customer-realm.json`: Configured for multi-tenant customer users with configurable OTP policies, PKCE authentication, OIDC client definitions, and AMR/ACR claim mappers.
   - `workforce-realm.json`: Configured for internal workforce personnel with mandatory TOTP execution, break-glass admin accounts, and strict session limits.
2. **Privileged Role Multi-Factor Authentication Enforcement:**
   - Privileged roles (`Role.OWNER`, `Role.ADMINISTRATOR`, `Role.COMPLIANCE_MANAGER`) must possess verified MFA in their token claims (`amr` containing `otp`, `totp`, `mfa`, or `webauthn`, or ACR equivalent).
   - Privileged requests lacking verified MFA are rejected at `get_tenant_context` with HTTP 403 `MFA enforcement: privileged role requires multi-factor authentication`. Non-privileged roles (`EMPLOYEE`, `REVIEWER`, `CONTROL_OWNER`) can access their assigned scope without mandatory MFA.

## D-052 — Complete Production Deployment Topology (compose.yaml, Prometheus, Grafana)

1. **Full 14-Service Stack:**
   - Fully expanded `compose.yaml` with production-grade topology: `postgres` (primary with WAL archiving and replication privileges), `postgres-replica` (streaming standby HA), `redis` (task and cache broker), `minio` + `minio-init` (S3 storage), `keycloak` (identity), `openbao` (KMS transit engine), `mailpit` (mock SMTP), `clamav` (malware scanning), `prometheus` (metrics scraping), `grafana` (SLO dashboard), `migrate` (alembic), `api` (FastAPI), `worker` (Celery background tasks), and `web` (React/Vite).
2. **Continuous Monitoring & Metric Collection:**
   - API exposes `/metrics` Prometheus endpoint tracking HTTP request totals, latency distributions, active database connections, and backup timestamps.
   - Preconfigured `prometheus.yml` scrape configuration and Grafana SLO dashboard (`conformly-slo.json`) displaying latency p99, error rates, and backup status.

## D-053 — Measured Disaster Recovery & Streaming HA Standby (RTO/RPO Verification)

1. **Physical Storage Rehearsal:**
   - Upgraded disaster recovery drill (`test_backup_restore_rehearsal.py`) to run against actual disk storage (`FilesystemStorageProvider`), removing the previous mock `MemoryStorageProvider`.
2. **Measured Recovery Metrics:**
   - Validated end-to-end physical backup creation, file encryption, ZIP bundle export, and full restoration with measured Recovery Time Objective (RTO <= 4 hours) and Recovery Point Objective (RPO <= 1 hour) asserting against pilot objectives.
   - Reconstructed tenant verifies manifest SHA-256 digest, original file byte matching, and cryptographic audit hash chain integrity after restoration.

## D-054 — Background Jobs, Delivery Providers, Celery Integration & Failed-Job Remediation

1. **Dual-Mode Worker Runtime:**
   - Worker entry point `conformly.notifications.worker` (`python -m conformly.notifications.worker`) runs either as a standalone tick-based polling loop with signal handling (`SIGINT`/`SIGTERM`) or as a Celery worker daemon (`--celery`).
   - Integrated with Compose stack: `compose.yaml` executes `python -m conformly.notifications.worker` with dependency on healthy `postgres`, `redis`, and `mailpit`.
2. **Actual Delivery Providers & Routing:**
   - RFC 5322 MIME message formatting via `SmtpNotificationProvider` delivering to Mailpit in development and authenticated TLS SMTP in production.
   - HMAC-SHA256 signed HTTP delivery via `WebhookNotificationProvider` with timestamp, signature, and idempotency headers.
   - `CompositeNotificationProvider` routes to SMTP or Webhooks dynamically based on payload contents (`recipient_email`/`email` vs `webhook_url`), with `LoggingNotificationProvider` fallback.
3. **Deterministic Exponential Backoff & Terminal Failure:**
   - Transient errors (connection refused, timeouts) retry up to `MAX_DELIVERY_ATTEMPTS = 5` with bounded exponential delays (`1m`, `2m`, `4m`, `8m`, `16m`).
   - Terminal errors (recipient refused, authentication failure) immediately transition to `FAILED` status with an error code and failure audit event.
4. **Failed-Job Visibility & Management API:**
   - Dedicated REST endpoints under `/v1/tenants/{tenant_id}/jobs`:
     - `GET /v1/tenants/{tenant_id}/jobs/failed`: returns failure counts and recent failures.
     - `GET /v1/tenants/{tenant_id}/jobs/outbox`: lists messages with pagination and state filtering.
     - `GET /v1/tenants/{tenant_id}/jobs/outbox/{message_id}`: message status detail.
     - `POST /v1/tenants/{tenant_id}/jobs/outbox/{message_id}/retry`: privileged manual retry resetting state to `PENDING` and logging `notification.retry` audit events.
   - Access restricted to privileged tenant roles (`Role.OWNER`, `Role.ADMINISTRATOR`, `Role.COMPLIANCE_MANAGER`).
5. **Celery & Redis Architecture:**
   - `conformly.jobs.celery` defines `celery_app` backed by Redis broker/result-backend.
   - Celery tasks: `conformly.deliver_notifications` (outbox batch), `conformly.continuous_compliance_cycle` (periodic compliance checks), and `conformly.retention_sweep` (tenant cancellation and deletion lifecycle).
   - Celery Beat schedule configures recurring delivery (every 10s), continuous compliance checks (hourly), and daily retention sweeps.

## D-055 — External Integration Layer, Signed Webhooks & LMS Training Contract

1. **External Integration Architecture & Security Boundaries:**
   - Multi-tenant integration credentials (`IntegrationCredential`) with PBKDF2-HMAC-SHA256 client secret hashing (100,000 rounds) and AES-256-GCM application-layer envelope encryption for signing secrets.
   - Credentials strictly tenant-scoped with PostgreSQL Row-Level Security (RLS) enforcement.
   - Plaintext credentials and signing secrets returned only once upon generation; secrets never logged or stored unencrypted.
2. **General Signed-Webhook Subsystem:**
   - Inbound webhook authentication via `X-Conformly-Key-Id`, `X-Conformly-Signature`, `X-Conformly-Timestamp`, and `X-Conformly-Idempotency-Key` headers.
   - HMAC-SHA256 signature verification computed over `${timestamp}.${raw_body}`.
   - Replay protection enforcing strict tolerance window (`abs(now - timestamp) <= 300` seconds).
   - Two-phase idempotency tracking (`InboundWebhookEvent`) with atomic duplicate delivery detection, concurrency locking, and cached response replay.
   - Outbound webhook subscriptions (`WebhookSubscription`) supporting tenant isolation, topic filtering, and application-layer encrypted secrets.
3. **LMS Integration Contract & Separation of Responsibilities:**
   - As mandated by `docs/PRODUCT_SOURCE_OF_TRUTH.md` (Items 18 & 22) and Trello DEU, Conformly does not embed or rebuild an LMS runtime.
   - Conformly owns:
     - Course catalog metadata (`TrainingCourse`)
     - Workforce training assignments, role mappings, and due dates (`TrainingAssignment`)
     - Automatic compliance evidence generation (`EvidenceItem`) and control linking (`EvidenceControlLink`) upon completion
     - Audit trail and encrypted raw payload preservation for legal defensibility
   - External LMS owns: SCORM content, lesson tracking, interactive player, quizzes, and learner assessment.
   - Verifiable webhook contract (`LmsContract` / `LmsCompletionPayload` / `LmsPartnerSimulator`) prevents spoofing: no browser redirect can mark compliance controls as satisfied.

## D-056 — Frontend Architecture: React 19 + Vite Static SPA Approval

1. **Resolution of Frontend Framework Baseline:**
   - Evaluated the documented divergence between `Next.js/React/TypeScript` (in earlier Trello baseline) and the active `React 19 + Vite + TypeScript` implementation (`apps/web`).
   - Formally approved **React 19 + Vite + TypeScript Static SPA** served via Nginx containers as the production frontend architecture, closing the repository deviation noted in `docs/PRODUCT_SOURCE_OF_TRUTH.md`.
2. **Security & Zero-Trust Client Model Justification:**
   - Conformly is an authenticated B2B SaaS platform where all API communication is secured via client-side OIDC/PKCE bearer tokens with Keycloak and FastAPI.
   - Deploying pre-compiled static HTML/JS/CSS assets behind Nginx eliminates Node.js server-side execution attack surfaces (e.g. multi-tenant token leakage in SSR process memory, server-side prototype pollution, Node CVEs).
   - Eliminates unnecessary SSR complexity since all compliance operations require authenticated, tenant-isolated API access.
3. **Operational, Performance & Testing Alignment:**
   - Static compilation produces sub-300ms Vite builds and instant client-side routing.
   - Fully unified with the established Vitest + Testing Library test suite (46+ component and journey tests) and Docker multi-stage Nginx production container (`apps/web/Dockerfile`).
   - Supports required WCAG 2.2 AA accessibility standards and client-side multi-lingual localization (DE/EN/FR/NL/ES).

## D-057 — Tier A Framework Packs Selection, Licensing, and Release Model

1. **Initial Tier A Foundation Framework Selection:**
   - Selected five foundational compliance and security framework packs as the initial Tier A core release:
     1. `iso-27001` (ISO/IEC 27001:2022 ISMS Pre-Audit Readiness Pack): Information security management system readiness clauses (4–10) and Annex A controls (A.5 Organizational, A.6 People, A.7 Physical, A.8 Technological).
     2. `gdpr-bdsg` (EU GDPR & German BDSG Privacy Operations Pack): Data protection principles, lawful basis, data subject rights, processing records (VVT Art 30), technical and organizational measures (TOMs Art 32), 72-hour breach notification (Art 33/34), DPIA (Art 35), DPO requirements (Art 37-39, BDSG § 38), and employee data safeguards (BDSG § 26).
     3. `nist-csf` (NIST Cybersecurity Framework 2.0 Pack): Core cybersecurity outcomes structured across Govern (GV), Identify (ID), Protect (PR), Detect (DE), Respond (RS), and Recover (RC).
     4. `cis-controls-ig1` (CIS Critical Security Controls v8 - Implementation Group 1): Foundational cyber hygiene safeguards covering asset/software inventory, data protection, secure configurations, account management, access control, vulnerability management, audit logs, malware defense, backups, awareness training, and incident response.
     5. `mvsp` (Minimum Viable Secure Product v2.0): B2B SaaS application and vendor security baseline across Business controls, Application security, Operational security, and Physical security.

2. **Content Rights, Copyright & Licensing Strategy:**
   - **GDPR & BDSG:** Official legislative acts of the European Union (Regulation 2016/679) and the Federal Republic of Germany (Bundesdatenschutzgesetz) are in the public domain (German § 5 Abs. 1 UrhG: "Gesetze, Verordnungen, amtliche Erlasse und Bekanntmachungen... genießen keinen urheberrechtlichen Schutz").
   - **NIST CSF 2.0:** Work of the United States Federal Government, placed into the public domain worldwide (17 U.S.C. § 105).
   - **CIS Controls v8 IG1:** Licensed and utilized under fair-use implementation taxonomy and public cyber hygiene guidance.
   - **MVSP 2.0:** Openly published under the Creative Commons Attribution 4.0 International license (CC BY 4.0).
   - **ISO/IEC 27001:2022:** Conformly respects ISO/IEC intellectual property. Conformly does not reproduce proprietary or paywalled ISO normative text verbatim. Instead, Conformly authors proprietary, actionable pre-audit readiness requirements, operational controls, implementation guidance, and evidence collection requests aligned with standard clause structures.
   - **Positioning Boundary:** Conformly pre-audit readiness scores, badges, and reports strictly state that they assess readiness and compliance operations and do not constitute accredited third-party certification.

3. **Deterministic Applicability Evaluation Rules Engine:**
   - Framework packs are augmented with a deterministic applicability engine (`TenantProfileContext` → `OverlayApplicability`) that evaluates tenant characteristics (Controller vs Processor, 100% remote vs physical facilities, datacenter ownership, employee count >= 20 for German DPO obligations under § 38 BDSG, special category data under Art 9 / § 22 BDSG, and international data transfers).
   - Produces auditable justification records (`TenantControlOverlay`) explaining why specific controls are `APPLICABLE`, `NOT_APPLICABLE`, or `SCOPED_OUT`.

4. **Independent Second-Person Approval & Immutability:**
   - Framework packs are governed by the canonical `FrameworkService` lifecycle:
     - `create_framework()`
     - `create_version_draft()` authored by platform administrator
     - `add_canonical_control()` for all requirements and evidence guidance
     - `submit_version_for_review()` → `IN_REVIEW`
     - `record_legal_review()`
     - `approve_version()` by independent second-person approver (enforcing `approver_id != author_id` and `approver_id != reviewer_id`)
     - `release_version()` → `RELEASED`
   - Non-draft versions (`IN_REVIEW`, `APPROVED`, `RELEASED`, `RETIRED`) are strictly immutable. Content revisions require returning the version to `DRAFT` via `return_version_to_draft()`.

5. **Global Catalog Backlog Scope:**
   - The global catalog (`docs/GLOBAL_FRAMEWORK_CATALOG.md`) formally maintains Tier B (SOC 2, ISO 27701, ISO 22301), Tier C (NIS2, DORA, EU AI Act), and Tier D (FedRAMP, CMMC) as the future planning backlog, preserving clear boundaries between released Tier A core and future packaging proposals.

## D-058 — Framework Content Immutability Enforcement, Return-to-Draft Lifecycle, and Truthful Draft Pack Documentation

1. **Context & Motivation:**
   - Verification highlighted two concerns:
     1. Mutation of canonical framework content while under review (`IN_REVIEW`) or approved (`APPROVED`) must strictly fail closed. In earlier code, `ReleaseState.APPROVED` was omitted from check tuples in several mutation methods, and tests relied on raw ORM attribute manipulation (`ver.release_state = ReleaseState.DRAFT`) rather than an audited service lifecycle transition.
     2. Documentation across `GLOBAL_FRAMEWORK_CATALOG.md` and `FRAMEWORK_PACKS_TIER_A.md` previously claimed launch packs were released/approved, directly contradicting `manifest.json` which designates all five packs as `DRAFT_REVISION_UNDERWAY` / `CONTENT_REVIEW_PENDING` awaiting independent human review.
2. **Fail-Closed Immutability Enforcement:**
   - Standardized all 7 canonical framework mutation methods in `FrameworkService`:
     - `add_canonical_control`
     - `update_canonical_control`
     - `delete_canonical_control`
     - `add_source_requirement`
     - `add_requirement_control_mapping`
     - `add_evidence_specification`
     - `set_coverage_ledger_entry`
   - Every method strictly checks `if version.release_state != ReleaseState.DRAFT: raise ImmutableCanonicalVersionError(...)`. No mutation is permitted when a version is in `IN_REVIEW`, `APPROVED`, `RELEASED`, or `RETIRED`.
3. **Explicit Audited Return-to-Draft Service & API:**
   - Implemented `return_version_to_draft(principal, version_id, reason, request_id)` in `FrameworkService` and exposed `POST /v1/frameworks/{framework_id}/versions/{version_id}/return-draft`:
     - Requires platform administrator privileges and verified MFA.
     - Accepts versions in `IN_REVIEW` or `APPROVED` only (released versions cannot be returned to draft; they must be superseded).
     - Resets `release_state` to `DRAFT`.
     - Completely invalidates existing legal review records (`legal_reviewed_by_user_id`, `legal_reviewed_at`, `legal_review_notes`) and second-person approval records (`approved_by_user_id`, `approved_at`, `approval_notes`).
     - Emits structured audit event `canonical_framework_version.returned_to_draft`.
4. **Documentation & Manifest Truthfulness:**
   - Reconciled documentation across `GLOBAL_FRAMEWORK_CATALOG.md`, `FRAMEWORK_PACKS_TIER_A.md`, and `PILOT_RELEASE_SIGNOFF_2026.md` to truthfully reflect that all five Tier A framework packs (`iso-27001`, `gdpr-bdsg`, `nist-csf`, `cis-controls-ig1`, `mvsp`) are technical engineering drafts in review (`CONTENT_REVIEW_PENDING`), matching `manifest.json`.



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


## D-059 — ISO 9001:2015 Admitted to Module A Beta

**Date:** 2026-09-13  
**Decision Source:** Explicit Product Owner instruction.  
**Prior Status:** `OWNER_DECISION_REQUIRED` (recorded in `manifest.json` and `MODULE_A_BETA_SCOPE.md`, Section 4).

**Decision:** ISO 9001:2015 Quality Management System is promoted from `OWNER_DECISION_REQUIRED` to `REQUIRED_BETA`. It is now a full, production-grade Tier A framework pack subject to all the same content, schema, applicability, independent review, and testing gates as the original five packs.

**Rationale:** Product Owner explicitly instructed engineering to "add ISO 9001 to the module A and code it."

**Implementation:**
- New pack module: `apps/api/src/conformly/frameworks/packs/iso_9001.py`
- All addressable subclauses of Clauses 4–10 implemented (~60+ controls)
- Conditional applicability rules added to `applicability.py`: Clause 8.3 (D&D), Clause 8.4 (External Providers), Clause 8.5.5 (Post-Delivery)
- Three new `TenantProfileContext` fields: `performs_design_and_development`, `has_external_providers`, `has_post_delivery_activities`
- `TIER_A_PACKS` expanded from 5 to 6 entries
- `manifest.json` `required_beta_count` updated from 5 to 6
- Draft skeleton removed from `owner_decision_drafts.py`
- `MODULE_A_BETA_SCOPE.md` Section 3 updated to 6 packs; Section 4 reduced to 4 remaining candidates

**Legal Gate Preserved:** ISO 9001:2015 is a proprietary standard (copyright ISO/TC 176/SC 2). The pack contains original Conformly pre-audit guidance only; no verbatim ISO text is reproduced. Independent IP counsel review is required prior to production customer issuance (same gate as ISO 27001). Pack `approval_notes` records this requirement.

**Default for `performs_design_and_development`:** `False`. Service-only organizations commonly exclude Clause 8.3 from scope. Conservative default requires explicit opt-in for D&D applicability.
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

