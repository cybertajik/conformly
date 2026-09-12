# MVP Scope

## 1. Goal

Ship a secure paid pilot that provides recurring compliance value without attempting to solve every governance/compliance category at once.

## 2. In Scope

### Platform Foundation
- tenant creation
- fixed Tier A role model
- authentication
- authorization
- tenant isolation
- audit logging
- classifications
- encrypted files
- encrypted Restricted fields
- crypto abstraction
- object storage abstraction

### Frameworks
- canonical catalog
- framework versions
- tenant adoption
- overlays
- custom controls
- mappings
- impact analysis workflow
- controlled version adoption

### Compliance Workspace
- controls
- evidence
- evidence expiration
- owners
- tasks
- findings
- remediation status

### Pre-Audit
- scope setup
- readiness checks
- evidence review
- findings
- remediation
- report
- audit manifest
- Conformly readiness/pre-audit certificate

### Whistleblower
- tenant-specific reporting URL
- anonymous report submission
- secure anonymous return access
- two-way case communication
- encrypted attachments
- internal case workflow
- audit trail

### Public Profile
- tenant public page
- Conformly-issued readiness credential
- customer-provided third-party certifications
- controlled public visibility

### Lifecycle
- exports
- cancellation export window
- deletion scheduling
- retention workflows

### Deterministic Automation
- reminders
- due dates
- expirations
- reports
- exports
- retention
- notifications
- adoption workflows

## 3. Explicitly Out of Scope for First Paid MVP

Unless separately approved:
- tenant-created custom roles
- autonomous AI agents
- AI-generated authoritative compliance decisions
- browser-to-browser E2EE for core compliance data
- custom modification of canonical framework content
- automatic tenant adoption of framework changes
- accredited certification claims
- complex microservice split
- custom cryptographic algorithms
- storage chunking as primary confidentiality control

## 4. Pilot Service Commitments

Support:
- business hours
- 24/7 security intake

Response objectives:
- 4h / 1d / 2d / 3d by severity.

Pilot positioning:
- objectives, not contractual SLA.

Readiness gate for contractual SLA:
- 6 months evidence
- 2 recovery tests

## 5. MVP Success Criteria

Technical:
- no known tenant breakout path
- encrypted files working end to end
- Restricted-field encryption working
- auditable admin/compliance actions
- repeatable deployment
- reliable migrations
- automated tests
- successful backup/restore exercise

Product:
- tenant can adopt a framework
- tenant can map controls/evidence
- pre-audit can be completed
- report/export can be generated
- whistleblower report can be submitted anonymously and tracked
- public profile can display explicitly approved credentials
- cancellation lifecycle can be executed
