# Security Requirements

## 1. Security Baseline

Security is a first-class product requirement.

Conformly stores compliance evidence, whistleblower reports, internal policies, audit findings, and potentially highly sensitive organizational data.

Security controls must therefore exist at:
- application,
- identity,
- authorization,
- encryption,
- transport,
- storage,
- database,
- infrastructure,
- logging,
- backup,
- operations.

## 2. Data Classification

### Public
May be intentionally published.

### Internal
Normal tenant-internal operational data.

### Confidential
Sensitive business/compliance data.

### Restricted
Highest-protection tenant data.

Examples that may fall into Restricted:
- whistleblower case data,
- sensitive investigation records,
- certain identity fields,
- specially classified evidence.

Classification must be explicit in the data model where necessary.

## 3. Encryption

### In transit
Use modern TLS.

### At rest
Use storage/database encryption where available.

### Application layer
Mandatory for:
- all uploaded files,
- Restricted fields.

Also use for selected Confidential fields based on schema policy.

### Algorithm
Initial application-layer AEAD:
- AES-256-GCM.

### Envelope encryption
Data is encrypted with a DEK.
DEK is wrapped by a KEK.
Key version is stored with encrypted data.

### Crypto agility
Code must not assume a single permanent cipher/provider.

Interfaces must support:
- algorithm versioning,
- key versioning,
- key rotation,
- provider replacement.

### Post-quantum readiness
Current data encryption:
- AES-256-GCM.

Architecture:
- crypto-agile interfaces now,
- standardized hybrid/PQC transport when mature and production-ready.

Do not invent custom post-quantum cryptography.

## 4. End-to-End Encryption Decision

Core compliance data should not use browser-to-browser E2EE in the MVP.

Reason:
- server-side workflows,
- reporting,
- compliance logic,
- exports,
- authorized review,
- deterministic automation

must be able to operate.

This does not weaken the requirement for strong server-side application encryption.

## 5. Tenant Isolation

Every protected object must have a clear tenant boundary.

Rules:
- never trust tenant ID from client without validating membership,
- never expose sequential cross-tenant identifiers as authorization,
- tenant-scoped repositories/services must require tenant context,
- authorization must happen server-side,
- caches must include tenant namespace,
- background jobs must carry tenant context,
- exports must enforce tenant scope,
- audit logs must capture tenant context.

## 6. Authorization

Use centralized authorization policy.

Avoid:
```python
if user.role == "admin":
```
scattered throughout the codebase.

Prefer:
```text
authorize(user, tenant, capability, resource)
```

Permissions should be capability-based internally even if the MVP exposes fixed roles.

## 7. Authentication

Use secure, standards-based authentication.

Implementation should support:
- secure password hashing if password auth exists,
- MFA capability,
- session/token revocation,
- rate limiting,
- account lockout / abuse controls,
- secure password reset,
- audit events.

Do not store plaintext passwords.

## 8. Secrets

Never commit secrets.

Use:
- environment injection for local development,
- production secret manager abstraction.

Never log secrets.

## 9. File Security

Every uploaded protected file:
1. validate upload,
2. classify,
3. authorize,
4. generate DEK,
5. encrypt with AES-256-GCM,
6. wrap DEK,
7. store ciphertext,
8. persist cryptographic metadata,
9. log auditable event.

Downloads:
1. authenticate/authorize,
2. fetch ciphertext,
3. unwrap key,
4. decrypt,
5. stream to authorized caller,
6. audit access as appropriate.

## 10. Anonymous Whistleblower Security

The reporting path must minimize identity leakage.

Avoid collecting or storing unnecessary:
- IP addresses,
- browser fingerprints,
- analytics identifiers,
- referrer data,
- marketing cookies.

Infrastructure logs should be configured to minimize deanonymization risk while retaining necessary abuse/security protection.

Reporter return secret:
- high entropy,
- never logged,
- never stored as plaintext if verification can use a one-way verifier.

Internal case data:
- Restricted by default unless a narrower classification is justified.

## 11. Audit Logging

Audit events should be immutable or strongly append-only in normal application operation.

Capture:
- actor,
- tenant,
- action,
- resource,
- timestamp,
- request/correlation ID,
- outcome,
- relevant safe metadata.

Do not put protected plaintext into audit metadata.

## 12. Cross-Tenant Analytics

Only operational metadata.

Never aggregate tenant content across customers.

Any future analytics feature touching customer content requires an explicit product/security decision.

## 13. Backup Security

Backups:
- encrypted,
- access restricted,
- tested,
- inventoried,
- lifecycle managed.

Do not treat 3-way or 3+1 chunking as the main confidentiality layer.

Encryption remains primary.

## 14. Retention / Deletion

Normal cancellation:
- export window: 30 days,
- deletion deadline: day 90.

Deletion must include:
- primary data,
- file objects,
- indexes/caches,
- derived artifacts where appropriate,
- scheduled expiration of backup copies according to defined backup retention.

Maintain deletion evidence without retaining deleted tenant content.

## 15. Secure Development

Required:
- dependency scanning,
- secret scanning,
- linting,
- type checks,
- tests,
- migration checks,
- code review,
- protected main branch,
- environment separation.

Security-sensitive changes should require review.

## 16. Threats to Explicitly Test

- IDOR / tenant breakout
- permission escalation
- insecure direct file access
- anonymous whistleblower correlation
- token replay
- export cross-tenant leakage
- unencrypted Restricted fields
- cryptographic metadata corruption
- SQL injection
- mass assignment
- unsafe file uploads
- insecure logs
- background-job tenant mix-up
