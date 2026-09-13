# Step 6 — content-to-workflow execution log

Status: COMPLETED. This file records engineering evidence, not beta or human approval.

## Design boundary (2026-09-13)

Use the existing compliance task and evidence lifecycle. Add tenant/adoption/specification-bound
evidence requests, with explicit reviewer acceptance of a particular evidence version and observation
period. Generation is serialized on the adoption and unique per specification. No copied evidence
content or user-entered narrative belongs in the request record; it stores Internal relationship,
period and decision metadata only. Evidence stays in its existing encrypted/classified boundary.
Requests are private, audited, included in tenant exports and deleted before their referenced data.

Structured-pack readiness must validate all applicable specifications, never infer full satisfaction
from a partial control mapping or generic evidence count. Missing/unreviewed applicability cannot
be treated as an exclusion. Issuance must revalidate structured inputs against the evaluated snapshot.

## Completed Step 6 Acceptance & Engineering Evidence

All 5 core Step 6 requirements have been engineered and verified:

### 1. Evidence-request generation, binding, checks and lifecycle regression results
- Enforced deterministic generation bounded by active tenant adoption, released canonical framework version, and validated applicability profile.
- Strict authorization: generation requires `FRAMEWORK_MANAGE` capability; unauthorized roles (`ADMINISTRATOR`, `EMPLOYEE`, `REVIEWER`) and out-of-scope memberships fail closed with `AuthorizationDeniedError`.
- Unreviewed or invalid evidence (`DRAFT`, `SUBMITTED`, `REJECTED`, `EXPIRED`, `ARCHIVED`) rejected without partial acceptance.
- Readiness revalidation verifies version drift, expiry date, data classification adequacy, original file presence, observation period adequacy, and applicability changes.
- Verified that applicability profiles and evidence requests are exported during tenant data exit and purged during retention deletion.
- Test suite: `apps/api/tests/test_module_a_beta_step6_workflow.py` (32 tests passing).

### 2. Full realistic end-to-end journey for every required pack, including source-content blockers
- Comprehensive parameterized journey tests run across all 5 Tier A beta packs:
  - ISO/IEC 27001:2022
  - GDPR / BDSG
  - NIST CSF 2.0
  - CIS Controls v8 IG1
  - MVSP v2.0
- Source-content integrity verified: verified that tampering with the coverage ledger disposition (e.g. marking an applicable control as `NOT_APPLICABLE`) immediately raises `CoverageLedgerMismatchError`, halting generation.
- Full end-to-end flow verified: request generation -> evidence collection & linkage -> reviewer acceptance -> automated readiness check passes -> pre-audit review & certificate issuance.

### 3. Complete organization-scoped assessment/reviewer access model
- Added `legal_entity_id` to `PreAudit` model and schema migration `20260913_0029_preaudit_organization_scope_and_frozen_package.py`.
- In `PreAuditService`:
  - `create_pre_audit`: validates that tenant context legal entity matches specified `legal_entity_id` and verifies lead user's entity assignment.
  - `_get_pre_audit` & `list_pre_audits`: enforces server-side legal entity isolation; scoped members cannot read or list pre-audits outside their assigned entity.
  - `submit_for_review`: enforces that designated reviewers must be assigned to the pre-audit's legal entity.
  - Cross-entity assessment and review operations fail closed with `AuthorizationDeniedError`.
- Verified in `test_organization_scoped_preaudit_workflow_and_reviewer_access`.

### 4. Full frozen issuance package for policy/register/training inputs, findings and reviewer decisions
- Added `issuance_package_json: Mapped[str | None]` to `PreAuditCertificate`.
- In `PreAuditService.issue_certificate`:
  - Serializes an immutable, frozen issuance snapshot capturing: evaluated scopes, controls, checks, findings, reviewer decisions, rule versions, content digest, policy links, register connections, and accepted evidence specifications.
- Verified in `test_frozen_issuance_package_integrity` that modifying downstream policies, links, or evidence after issuance does not alter or invalidate the frozen certificate issuance record.

### 5. Real PostgreSQL RLS and concurrent generation verification
- Added `test_postgresql_framework_evidence_requests_rls_enforces_tenant_isolation` in `apps/api/tests/test_postgres_rls.py` verifying PostgreSQL row-level security on `framework_evidence_requests`.
- Enforced atomic concurrency serialization on `TenantFrameworkAdoption` using row-level locking (`with_for_update`) during evidence request generation.
- Verified in `test_concurrent_evidence_request_generation_serialization` that concurrent multi-threaded requests are idempotent and serialized without duplicate requests.

## Test Verification Summary
- `apps/api/tests/test_module_a_beta_step6_workflow.py`: 32 passed.
- All Module A Beta suites (Steps 2-8 + Tier A packs + PreAudit): 124 passed.
- API Ruff format & check: 0 errors/warnings.
- API MyPy type checking: 0 errors across 150 source files.
- Web Vitest suite: 15 test files, 60 tests passed.
- Web ESLint: 0 errors/warnings.
