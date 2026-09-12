# Implementation Plan

## Phase 0 — Repository Foundation

Create:
- backend application
- frontend application
- shared configuration
- Docker Compose
- PostgreSQL
- Redis if background jobs are included immediately
- migration framework
- test framework
- linting
- formatting
- type checking
- CI

Deliverable:
- all services boot locally,
- health checks pass,
- empty migration applies,
- tests run,
- lint/type-check pass.

## Phase 1 — Identity, Tenancy, Authorization

Implement:
- User
- Tenant
- Membership
- fixed roles
- capability policy layer
- tenant request context
- tenant-scoped query helpers

Tests:
- same-tenant access
- cross-tenant denial
- role denial
- system admin boundaries

Do not move ahead until tenant-isolation tests exist.

## Phase 2 — Audit and Crypto Foundation

Implement:
- AuditEvent service
- crypto provider interface
- envelope encryption interface
- encrypted-field type/helper
- encrypted-file service
- key version metadata

Tests:
- AES-256-GCM round trip
- tamper detection
- wrong context failure
- tenant separation
- key version compatibility

## Phase 3 — Storage

Implement:
- S3-compatible storage abstraction
- encrypted file upload
- encrypted download
- file metadata
- hashing/integrity
- short-lived authorized download path

## Phase 4 — Framework Catalog

Implement:
- Framework
- FrameworkVersion
- CanonicalControl
- catalog release state
- two-person approval data model
- tenant adoption
- overlays
- custom controls
- mappings
- impact analysis skeleton

## Phase 5 — Compliance Workspace

Implement:
- evidence
- control status
- owners
- tasks
- findings
- remediation
- expiration workflows

## Phase 6 — Pre-Audit

Implement:
- audit scope
- checks
- evidence review
- findings
- readiness calculation based on deterministic rules
- report generation
- manifest generation
- certificate issuance workflow

## Phase 7 — Whistleblower

Build this as a strongly isolated module.

Implement:
- tenant portal URL
- anonymous case creation
- high-entropy return credentials
- secret verifier
- anonymous message thread
- internal handler access
- encrypted attachments
- audit trail
- anti-abuse rate limiting

Security review before release.

## Phase 8 — Public Profiles

Implement:
- publication boundary
- approved public fields
- Conformly credential display
- third-party certification display
- expiration visibility

## Phase 9 — Export / Retention

Implement:
- export job
- machine-readable dataset
- original files
- audit manifest
- human-readable report
- export expiry
- cancellation lifecycle
- deletion job
- deletion evidence

## Phase 10 — Operational Readiness

Add:
- backup jobs
- restore test process
- structured monitoring
- security intake flow
- support severity mapping
- incident runbooks
- deployment runbook

## First Codex Task

When the repository is first opened in Codex, use this prompt:

> Read `AGENTS.md` and all files under `docs/`. Do not start product feature work yet. Build Phase 0 only: repository foundation, local Docker development stack, backend/frontend skeletons, PostgreSQL migrations, test/lint/type-check configuration, and CI. Then run all checks and summarize what was created, any assumptions made, and the exact next step.
