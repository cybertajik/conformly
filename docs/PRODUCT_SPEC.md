# Product Specification

## 1. Purpose

Conformly helps organizations prepare for audits and operate recurring compliance processes from one platform.

The platform should reduce the common problem of compliance becoming a one-time project that customers abandon immediately after an audit.

The retention strategy is therefore based on ongoing operational value:
- evidence lifecycle,
- recurring controls,
- policy lifecycle,
- training links/integrations,
- whistleblower reporting,
- framework updates,
- issue remediation,
- pre-audit readiness,
- public compliance profile,
- recurring compliance status.

## 2. Initial Product Positioning

Conformly initially provides:
- compliance management,
- pre-audit assessments,
- readiness reports,
- evidence organization,
- deterministic workflows,
- certificates/badges representing Conformly's own pre-audit/readiness result,
- public profile pages.

Conformly must not present those certificates as accredited third-party certification unless that status is actually obtained.

## 3. Multi-Tenant Model

Each customer organization is a tenant.

Core principles:
- tenant data is isolated,
- users may only access tenants they are authorized for,
- tenant context must be enforced server-side,
- all tenant-scoped records should be clearly attributable to a tenant,
- system-level canonical content is separate from tenant content.

## 4. Compliance Frameworks

The platform contains a canonical framework catalog.

Tenants:
- cannot edit canonical framework content,
- may add overlays,
- may create custom controls,
- may create mappings between their controls and canonical controls.

Framework updates:
1. new canonical version is prepared,
2. legal/compliance review occurs,
3. independent second-person approval occurs,
4. impact analysis is generated,
5. tenant reviews impact,
6. tenant adopts the version through a controlled process.

Do not automatically rewrite tenant compliance state when a canonical framework changes.

## 5. Data Classification

Fixed MVP levels:
- Public
- Internal
- Confidential
- Restricted

Optional tags may supplement classification.

Classification must influence:
- encryption requirements,
- logging rules,
- export handling,
- access control,
- display rules.

## 6. Pre-Audit

Pre-audit is a major initial commercial capability.

The workflow should support:
- selecting framework/scope,
- assigning controls,
- evidence requests,
- evidence submission,
- review,
- findings,
- remediation,
- readiness status,
- human-readable report,
- audit manifest,
- certificate/badge where appropriate.

The system should aim to perform substantially the same readiness checks an auditor would expect, while clearly distinguishing readiness/pre-audit from accredited certification.

## 7. Public Compliance Profile

A tenant may have a public profile.

The profile may show:
- Conformly pre-audit/readiness status,
- Conformly-issued badge/certificate,
- customer-provided third-party certifications,
- selected public policy/compliance statements,
- expiry dates where applicable.

Only explicitly public data may appear.

## 8. Whistleblower Module

Each tenant may receive a dedicated whistleblower reporting URL.

Capabilities:
- anonymous report submission,
- optional identified submission if later supported,
- secure reporter return flow,
- secure status tracking,
- two-way communication without exposing identity,
- evidence/file attachments,
- case status,
- protected case access,
- complete audit trail of authorized internal actions.

Anonymous reporters must not need an account.

The system must not require identity in order to track a report.

## 9. Deterministic Automation

The first paid MVP uses deterministic automation.

Examples:
- scheduled reminders,
- due-date calculations,
- evidence expiration alerts,
- framework review tasks,
- retention/deletion jobs,
- report generation,
- approval workflows,
- export generation.

Do not make AI-generated decisions the authoritative compliance decision path in the first paid MVP.

## 10. Cancellation and Export

Normal cancellation:
- export access for 30 days,
- deletion completed by day 90.

Export package must include:
- machine-readable structured data,
- original uploaded files,
- audit manifest,
- human-readable reports.

Exports must be tenant-scoped and auditable.

## 11. Cross-Tenant Analytics

Allowed:
- operational metadata,
- aggregate service health,
- performance metrics,
- usage counts that do not expose or combine tenant content.

Not allowed:
- aggregating customer compliance content across tenants,
- training models on tenant compliance content without a separately defined policy,
- cross-tenant evidence analysis.

## 12. Service Model

Initial Tier A:
- business-hours support,
- 24/7 security intake.

Pilot response objectives:
- 4h / 1d / 2d / 3d, based on issue severity.

These remain objectives during paid pilot.

Contractual SLAs may follow only after:
- six months of evidence,
- two successful recovery tests.

Future contractual metrics:
- availability,
- recovery,
- response.

Future remedies:
- maximum service credit of 25%,
- exit after 3 affected months,
- automatic credits,
- 30-day dispute window.
