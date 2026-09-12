# Data Model — Initial Domain Model

This document defines domain boundaries, not final SQL.

## 1. System Scope vs Tenant Scope

### System-scoped
Examples:
- canonical frameworks
- canonical framework versions
- canonical controls
- system configuration
- platform release records

### Tenant-scoped
Examples:
- tenant users/memberships
- tenant framework adoption
- overlays
- custom controls
- mappings
- evidence
- policies
- tasks
- findings
- pre-audits
- certificates
- whistleblower cases
- public profile configuration
- exports

## 2. Core Entities

### Tenant
Fields may include:
- id
- name
- slug
- status
- created_at
- updated_at
- cancellation_requested_at
- export_until
- deletion_due_at

### User
Platform identity.

### Membership
Connects user to tenant.

Potential fields:
- user_id
- tenant_id
- role
- status

Tier A roles are fixed in the MVP.

## 3. Framework Catalog

### Framework
Examples:
- ISO-related frameworks
- regulatory frameworks
- internally curated compliance catalogs

### FrameworkVersion
- framework_id
- version identifier
- release state
- effective date
- review approval references

### CanonicalControl
Belongs to a framework version.

Canonical content is system-owned.

## 4. Tenant Framework Layer

### TenantFrameworkAdoption
Tracks:
- tenant
- framework
- adopted version
- adoption status
- adopted_at
- impact analysis reference

### TenantControlOverlay
Adds tenant-specific metadata without modifying canonical control.

### CustomControl
Tenant-created control.

### ControlMapping
Maps:
- canonical-to-custom,
- custom-to-canonical,
- framework-to-framework where supported.

## 5. Evidence

### EvidenceItem
Potential fields:
- tenant_id
- title
- description
- classification
- owner
- status
- valid_from
- valid_until
- created_at
- updated_at

### EvidenceFile
- evidence_id
- tenant_id
- object key
- ciphertext metadata
- wrapped key metadata
- content type
- original filename
- hash
- size

All files are application-layer encrypted.

## 6. Policies

### Policy
- tenant_id
- title
- version
- status
- classification
- owner
- approved_at

### PolicyApproval
- policy_id
- actor
- decision
- timestamp

## 7. Tasks / Remediation

### ComplianceTask
- tenant_id
- title
- due_date
- owner
- control reference
- status

### Finding
- tenant_id
- source
- severity
- description
- remediation status

## 8. Pre-Audit

### PreAudit
- tenant_id
- scope
- framework adoption
- status
- started_at
- completed_at

### PreAuditCheck
- preaudit_id
- control
- reviewer
- status
- finding
- evidence references

### PreAuditReport
- preaudit_id
- report artifact
- generated_at

### Certificate
- tenant_id
- preaudit_id
- status
- issued_at
- expires_at
- public visibility

Certificate language must accurately describe Conformly's readiness/pre-audit role.

## 9. Public Profile

### PublicProfile
- tenant_id
- slug
- published state

### PublicCredential
May represent:
- Conformly-issued readiness certificate,
- third-party certification supplied by tenant.

Only explicitly approved public fields should be projected to public endpoints.

## 10. Whistleblower

### WhistleblowerPortal
- tenant_id
- unique public slug/domain configuration
- status

### WhistleblowerCase
- tenant_id
- public case identifier
- anonymous access verifier
- status
- classification
- created_at

### WhistleblowerMessage
- case_id
- direction
- encrypted body fields where required
- created_at

### WhistleblowerAttachment
- case_id
- encrypted file metadata

### CaseAssignment
- case_id
- authorized handler

Never require a normal user identity for anonymous reporter access.

## 11. Audit

### AuditEvent
- id
- tenant_id nullable for system events
- actor type
- actor id where appropriate
- action
- resource type
- resource id
- timestamp
- request id
- safe metadata
- outcome

Audit metadata must not contain sensitive plaintext unnecessarily.

## 12. Encryption Metadata

Encrypted records should support fields such as:
- algorithm
- key_version
- wrapped_dek
- nonce
- ciphertext
- authenticated context version

Actual representation may vary by storage type.

## 13. Export

### ExportJob
- tenant_id
- requested_by
- scope
- status
- created_at
- completed_at
- expires_at

### ExportManifest
Includes:
- dataset versions
- file hashes
- record counts
- generated reports
- audit references

## 14. Retention

### DeletionJob
- tenant_id
- reason
- scheduled_at
- state
- completed_at
- proof/summary metadata

Deletion proof must not retain the deleted protected content.

## 15. Data Modeling Rule

For every new entity, decide explicitly:
1. system-scoped or tenant-scoped?
2. classification?
3. encryption requirement?
4. audit requirement?
5. retention requirement?
6. export requirement?
7. public visibility possibility?
