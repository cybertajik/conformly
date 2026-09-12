# Conformly — Codex Instructions

This repository is for **Conformly**, a multi-tenant compliance SaaS platform.

This file is the highest-level coding instruction for Codex. Read this file first. Then read
`docs/PRODUCT_SOURCE_OF_TRUTH.md` before every product, architecture, scope, entitlement, tier,
module, or roadmap decision, followed by the remaining documents under `docs/`.

The Conformly DEU Trello board is the canonical product authority.
`docs/PRODUCT_SOURCE_OF_TRUTH.md` is its required repository-local execution mirror. If Trello
DEU, the mirror, another local document, the build plan, or existing code conflict, stop product
implementation and reconcile the source of truth. Never infer that existing code or a checked
task overrides the product authority.

## Core Rule

Do not silently redesign product, security, tenancy, encryption, retention, framework, whistleblower, or service-level requirements that are already documented here.

If implementation details are missing, prefer:
1. secure defaults,
2. simple architecture,
3. explicit interfaces,
4. testability,
5. future extensibility without premature complexity.

If a technical conflict is discovered, document it in `docs/DECISIONS.md` before changing direction.

## Product Direction

Conformly is initially a **pre-audit and compliance operations platform**. It is not initially presented as an accredited certification body.

The first paid MVP should help organizations:
- prepare for compliance audits,
- manage compliance evidence,
- track controls and requirements,
- manage policies and tasks,
- run deterministic compliance workflows,
- operate an anonymous whistleblower reporting channel,
- complete pre-audit readiness checks,
- receive a Conformly-issued pre-audit certificate/badge where appropriate,
- publish a public compliance profile,
- display third-party certifications on that public profile.

## Mandatory Security Principles

- Multi-tenant by design.
- Strict tenant isolation.
- Strict module-level authorization boundaries where needed.
- Never rely on UI filtering for authorization.
- Every tenant-scoped database access must be tenant-scoped server-side.
- Files and `Restricted` data fields require application-layer encryption.
- Selected `Confidential` fields may also require application-layer encryption.
- Use AES-256-GCM for application-layer encryption.
- Use server-side envelope encryption.
- Keep cryptography behind crypto-agile interfaces.
- Do not use browser-to-browser end-to-end encryption for core compliance data because server-side workflows, reporting, and automation must remain possible.
- Transport encryption remains mandatory.
- Storage-level encryption remains mandatory but is not a substitute for application-layer encryption.
- Do not use storage chunking as the primary confidentiality mechanism for distributed backups.
- Cross-tenant analytics may use operational metadata only; tenant content must never be aggregated across tenants.

## Data Classification

The MVP uses these fixed levels:
- Public
- Internal
- Confidential
- Restricted

Optional tags may be added in addition to the fixed classification.

## Tenant Roles

Tier A uses a fixed six-role model. Do not add tenant-defined custom roles in the first paid MVP.

Until role names are finalized in implementation, keep role handling centralized and configurable in code. Do not spread raw string comparisons throughout the application.

Suggested implementation pattern:
- `Role` enum
- capability/permission mapping
- policy checks at service/API boundary

If exact role labels are not yet specified elsewhere in the repository, do not invent product-facing names without documenting the decision first.

## Automation

The first paid MVP includes **deterministic automation only**.

Do not add autonomous AI agents, generative policy decisions, or AI-based compliance scoring into production workflows unless the product documentation is explicitly updated.

AI may later assist with drafting, classification, retrieval, or explanation, but deterministic workflows remain the MVP baseline.

## Canonical Framework Catalog

- Tenants may not modify canonical framework content.
- Tenants may create overlays.
- Tenants may create custom controls.
- Tenants may create mappings.
- New framework versions require impact analysis before tenant adoption.
- Tenant adoption of new versions is controlled, not automatic.
- Canonical framework releases require legal/compliance review plus independent second-person approval.

## Whistleblower Module

The whistleblower module requires stronger privacy boundaries.

Requirements:
- Separate tenant-specific reporting URL.
- Anonymous reporter flow.
- Reporter identity must not be required.
- Reporter must receive a secure way to return to the case and track progress.
- Case content must be preserved according to retention requirements.
- Anonymous tracking must not expose identity.
- Never log secrets or identifiers that would deanonymize the reporter.
- Authorization around case handling must be especially strict.
- Audit access to whistleblower data.

Do not implement identity reconstruction mechanisms for anonymous reporters.

## Cancellation and Data Exit

On normal cancellation:
- provide a 30-day export period,
- delete customer content by day 90.

Export must contain:
- machine-readable data,
- original files,
- audit manifest,
- human-readable reports.

Deletion must be auditable and must include active systems and defined backup lifecycle handling.

## Service Objectives

Initial Tier A support:
- business-hours support,
- 24/7 security intake.

Pilot response objectives:
- 4 hours,
- 1 day,
- 2 days,
- 3 days,
depending on severity/classification.

These are published objectives during the paid pilot, not contractual SLAs.

Contractual service levels should only be introduced after:
- at least six months of evidence,
- two successful recovery tests.

Future contractual scope:
- availability,
- recovery,
- response.

Future remedy:
- service credit cap of 25%,
- exit right after 3 affected months.

Credits:
- automatic credit,
- 30-day dispute window.

## Coding Standards

Prefer:
- TypeScript for frontend,
- Python for backend,
- PostgreSQL as system of record,
- explicit migrations,
- typed API contracts,
- structured logging,
- request correlation IDs,
- audit events,
- deterministic jobs,
- idempotent background tasks,
- dependency injection for security-sensitive services,
- testable service boundaries.

Do not hard-code secrets.

Use environment variables or secret-manager abstractions.

## Repository Expectations

Before implementing major features, ensure these concerns have explicit modules:
- authentication,
- authorization,
- tenancy,
- audit,
- encryption,
- storage,
- framework catalog,
- evidence,
- pre-audit,
- whistleblower,
- public profiles,
- exports,
- retention/deletion,
- background jobs.

## Testing Requirements

Security-sensitive functions require tests.

At minimum test:
- tenant isolation,
- authorization boundaries,
- encrypted field round trips,
- envelope key rotation interfaces,
- export scoping,
- whistleblower anonymous access flow,
- framework version adoption,
- audit event creation,
- deletion scheduling.

## First Coding Milestone

Build only the foundation first:
1. repository layout,
2. local development environment,
3. backend skeleton,
4. frontend skeleton,
5. PostgreSQL,
6. migrations,
7. tenant-aware database foundation,
8. authentication/authorization foundation,
9. encryption interfaces,
10. audit subsystem foundation,
11. tests/lint/type-check,
12. CI.

Do not begin polishing dashboards before the security and tenancy foundation exists.
