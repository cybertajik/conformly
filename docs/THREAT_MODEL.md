# Conformly — Platform Threat Model & Security Architecture Review

## 1. Executive Summary & Methodology
This document provides a systematic STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) threat model review for the **Conformly** multi-tenant SaaS compliance platform.

Conformly operates on strict zero-trust assumptions:
1. Multi-tenant by design with server-side tenant scoping and PostgreSQL Row-Level Security (RLS).
2. Defense-in-depth application-layer envelope encryption (AES-256-GCM).
3. Zero customer plaintext stored in log streams, audit metadata, or deletion proofs.
4. Genuine anonymous intake without identity tracking or reconstruction capabilities.
5. Deterministic automation only — no autonomous or generative compliance decision-making.

---

## 2. STRIDE Analysis by Subsystem

### 2.1 Identity, Tenancy & Authorization (Phases 1 & 2)
- **Spoofing:**
  - *Threat:* Malicious actor submits forged JWT claims or impersonates another tenant.
  - *Mitigation:* Standards-based OIDC token verification with JWKS public keys. Explicit tenant context verification on every request (`resolve_tenant_context`) checking database membership and tenant active status.
- **Elevation of Privilege:**
  - *Threat:* Tenant member attempts to perform administrator or owner actions (e.g. invite users, publish trust center, request cancellation).
  - *Mitigation:* Fixed 6-role model with explicit capability mapping (`RolePolicy.require_capability`). Authorization verified at API/service boundaries, never relying on UI controls.
- **Information Disclosure (Cross-Tenant Data Leakage):**
  - *Threat:* SQL injection or missing `WHERE tenant_id = ...` leaks cross-tenant records.
  - *Mitigation:* Dual enforcement: (1) SQLAlchemy repository queries explicitly filter by `tenant_id`, and (2) PostgreSQL Row-Level Security (RLS) policies enforce `tenant_id = current_setting('app.current_tenant_id')`.

### 2.2 Cryptography & Object Storage (Phases 2 & 3)
- **Information Disclosure (Plaintext at Rest):**
  - *Threat:* Storage volume theft or direct database dump exposes sensitive policies, whistleblower summaries, or stored evidence files.
  - *Mitigation:* Application-layer envelope encryption using AES-256-GCM. Unique Data Encryption Keys (DEKs) per field/file wrapped with master Key Encryption Keys (KEKs). Zero unencrypted files stored in S3/MinIO.
- **Tampering (Ciphertext Alteration):**
  - *Threat:* Attacker modifies encrypted file payload or ciphertext in the database.
  - *Mitigation:* AES-256-GCM is an Authenticated Encryption with Associated Data (AEAD) algorithm. Any tampering invalidates the 128-bit authentication tag, causing immediate decryption rejection.

### 2.3 Framework Catalog & Compliance Workspace (Phases 4 & 5)
- **Tampering (Canonical Framework Alteration):**
  - *Threat:* Malicious tenant attempts to alter canonical regulatory framework definitions (e.g. ISO 27001 requirements).
  - *Mitigation:* Canonical catalog is system-owned, immutable, and strictly isolated from tenant modifications. Framework releases require independent two-person approval. Tenants can only create local overlays and custom controls.
- **Repudiation:**
  - *Threat:* User claims they did not approve a policy or mark a control implemented.
  - *Mitigation:* Comprehensive immutable `audit_events` ledger tracking `actor_user_id`, `action`, UTC timestamp, and safe metadata with request correlation IDs.

### 2.4 Pre-Audit Readiness & Verification Credentials (Phase 6)
- **Spoofing / False Accreditation:**
  - *Threat:* Tenant presents Conformly badges as accredited ISO/SOC 2 certifications.
  - *Mitigation:* Mandatory legal disclaimers burned into all public certificates, badges, and metadata: *"Conformly is an audit-readiness and compliance operations platform, not an accredited certification body."*
- **Tampering (Score Manipulation):**
  - *Threat:* User tampers with pre-audit readiness score to artificially inflate compliance posture.
  - *Mitigation:* Deterministic rules engine (v1.0.0) calculates scores transactionally from verified evidence links and control implementation statuses. Score snapshots are frozen with SHA-256 cryptographic manifests upon evaluation.

### 2.5 Whistleblower Reporting Channel (Phase 7)
- **Information Disclosure (Reporter De-anonymization):**
  - *Threat:* Adversary correlates network headers, timestamps, or IP logs to identify an anonymous reporter.
  - *Mitigation:* Zero client tracking (no IP, user-agent, or device fingerprinting stored). Messages encrypted with AES-256-GCM. Return tracking uses salted PBKDF2-HMAC-SHA256 (100,000 iterations); raw secret key is never stored on the server.
- **Elevation of Privilege:**
  - *Threat:* Unauthorized tenant employee accesses whistleblower case triage.
  - *Mitigation:* Strictly limited to `Role.OWNER`, `Role.ADMINISTRATOR`, and `Role.COMPLIANCE_MANAGER`.

### 2.6 Public Profiles & Trust Center (Phase 8)
- **Information Disclosure (Internal Objects Exposed via Public API):**
  - *Threat:* Unauthenticated public endpoint leaks internal findings, tasks, or policy drafts.
  - *Mitigation:* Public API queries strictly from dedicated public projection tables (`public_profiles`, `public_credentials`, `public_statements`). No database joins or relations reach internal operational tables.

### 2.7 Export, Retention & Deletion Lifecycle (Phase 9)
- **Tampering & Incomplete Deletion:**
  - *Threat:* Customer cancels account, but residual personal data remains in auxiliary tables or storage buckets.
  - *Mitigation:* Complete 33-table transactional cascade purge covering all modules, plus physical storage object deletion. Zero-knowledge `DeletionProof` generated containing only non-PII execution metadata and cryptographic hashes.
- **Denial of Service (Spam Exports):**
  - *Threat:* Attacker requests thousands of export archives to exhaust server storage and CPU.
  - *Mitigation:* Idempotent export deduplication enforced via database unique constraint `(tenant_id, idempotency_key)`, rate limits, and 7-day expiration.

---

## 3. Residual Risks & Review Disposition

All high and critical threat vectors are fully mitigated by architectural controls verified with automated tests:
- **No known tenant breakout paths exist.**
- **No plaintext customer secrets exist in logs, manifests, or proofs.**
- **No automated or AI-based compliance scoring decisions are permitted in production workflows.**
