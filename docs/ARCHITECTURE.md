# Architecture

## 1. Architectural Goals

Conformly must optimize for:
- tenant isolation,
- security,
- auditability,
- deterministic behavior,
- maintainability,
- data portability,
- controlled compliance content lifecycle,
- future module growth.

## 2. Recommended Initial Shape

Start as a modular monolith unless scale or regulatory isolation requires a service split.

Reason:
- simpler deployment,
- easier transaction boundaries,
- easier auditing,
- fewer distributed-system failure modes,
- faster MVP implementation.

Internal module boundaries should still be explicit.

Suggested backend modules:

```text
auth
users
tenancy
rbac
audit
crypto
storage
frameworks
controls
evidence
policies
tasks
preaudit
whistleblower
public_profiles
exports
retention
notifications
jobs
admin
```

## 3. Frontend

Recommended:
- React
- TypeScript
- route-based application areas
- strongly typed API client
- authorization-aware UI, but never UI-only authorization

Suggested major areas:
- tenant admin
- compliance workspace
- pre-audit workspace
- whistleblower case management
- public profile configuration
- system admin

Anonymous whistleblower portal should be a logically separated frontend surface.

## 4. Backend

Recommended:
- Python
- FastAPI
- SQLAlchemy 2.x
- Pydantic
- Alembic

Design rules:
- explicit tenant context,
- service layer for business logic,
- authorization policy checks before data access where practical,
- repository/query helpers that require tenant ID,
- transactions around state transitions,
- structured domain events where useful.

## 5. Database

PostgreSQL is the system of record.

Initial tenancy model:
- shared database,
- tenant_id on tenant-scoped tables,
- strict query scoping,
- optional PostgreSQL Row Level Security as defense in depth.

Do not rely exclusively on RLS.

Application logic must still scope queries.

Canonical framework tables should remain system-scoped, separate from tenant-specific overlays and adoption state.

## 6. Object Storage

Use an S3-compatible storage abstraction.

Files:
- must be application-layer encrypted before storage,
- must have tenant ownership metadata in the database,
- should use non-guessable object keys,
- must never use public buckets for protected evidence,
- should use short-lived signed access after authorization.

Storage providers may change without changing higher-level application logic.

## 7. Background Jobs

Use deterministic background jobs.

Possible queue:
- Redis-backed queue/Celery or equivalent.

Use for:
- report generation,
- export generation,
- notifications,
- retention,
- deletion,
- evidence expiry,
- framework adoption impact generation,
- scheduled checks.

Jobs must be:
- idempotent,
- tenant-scoped,
- observable,
- retry-safe.

## 8. Encryption Architecture

Use server-side envelope encryption.

Conceptual flow:

```text
Tenant/User Action
      |
      v
Application Authorization
      |
      v
Data Classification
      |
      v
Crypto Service
      |
      +--> Data Encryption Key (DEK)
      |
      +--> AES-256-GCM encrypt data
      |
      +--> wrap DEK using configured Key Encryption Key (KEK)
      |
      v
Store:
- ciphertext
- nonce
- auth tag / combined AEAD payload
- wrapped DEK
- key version
- algorithm metadata
```

Key-management provider must be abstracted.

MVP may begin with a secure operational provider while keeping interfaces ready for HSM/KMS integration.

## 9. Whistleblower Architecture

Use a dedicated logical boundary.

Public reporting surface:
- tenant-specific URL,
- no normal tenant login required.

Anonymous return access:
- random high-entropy case identifier,
- separate high-entropy secret/passphrase or equivalent,
- secret not stored in recoverable plaintext,
- rate limiting,
- no identifying analytics.

Internal handlers:
- dedicated permissions,
- explicit case authorization,
- audit events,
- restricted data classification.

## 10. Public Profiles

Public profile data should be denormalized or projected from explicitly approved public records.

Never render confidential tenant data directly from generic internal objects without a publication approval boundary.

## 11. Observability

Required:
- structured logs,
- correlation/request ID,
- security events,
- job metrics,
- error tracking,
- audit trail.

Logs must not contain:
- encryption keys,
- passwords,
- access tokens,
- anonymous reporter secrets,
- Restricted plaintext,
- unnecessary PII.

## 12. Deployment

Start with containerized deployment.

Separate at least:
- web,
- API,
- worker,
- PostgreSQL,
- Redis,
- object storage endpoint/provider.

Production should eventually separate managed stateful infrastructure from application containers.

## 13. Backup Principle

Backups must be:
- encrypted,
- access controlled,
- geographically/administratively separated where practical,
- regularly restore-tested.

Distributed backup confidentiality must come from encryption, not from splitting/chunking data and assuming incomplete chunks are safe.

## 14. Future Service Split Candidates

Only split when justified:
- whistleblower service,
- crypto/key service,
- framework catalog,
- reporting/export,
- notifications.

Do not split merely for architectural fashion.
