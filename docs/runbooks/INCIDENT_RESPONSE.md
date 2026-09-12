# Conformly — Incident Response & Pilot Service Objectives Runbook

## 1. Overview & Scope
This runbook establishes the security intake, severity classification, escalation workflow, response objectives, and post-mortem procedures for the **Conformly** platform.

> [!IMPORTANT]
> **Pilot Service Objectives vs Contractual SLAs:**
> The response times defined below are **published operational objectives** during the paid pilot, **not contractual SLAs**. Contractual service levels will only be introduced after at least six (6) months of operational evidence and two (2) documented, successful disaster recovery tests, in strict accordance with [`AGENTS.md`](file:///c:/Users/AD/Desktop/conformly/AGENTS.md).

---

## 2. Intake Channels & Support Availability

- **Tier A Support:** Business-hours operational support (Monday–Friday, 08:00–18:00 UTC).
- **24/7 Security Intake:** Continuous, dedicated security intake channel (`security@conformly.com` and automated PagerDuty/Opsgenie triggers) for critical vulnerabilities, cross-tenant leaks, key compromises, or whistleblower privacy threats.

---

## 3. Severity Classification & Response Objectives

| Severity Level | Definition & Examples | Target Initial Response | Target Resolution / Mitigation |
| :--- | :--- | :--- | :--- |
| **SEV-1 (Critical)** | Suspected tenant data breakout, active key compromise, whistleblower de-anonymization threat, total platform outage, RLS bypass. | **4 hours** (24/7 intake) | 12 hours |
| **SEV-2 (High)** | Core workflow blockage (evidence upload failure, pre-audit calculation failure, export packaging failure), authenticated privilege escalation attempt. | **1 business day** | 2 business days |
| **SEV-3 (Medium)** | Non-blocking functional defect, public profile rendering glitch, background worker delay under 2 hours, minor UI regression. | **2 business days** | 5 business days |
| **SEV-4 (Low)** | Cosmetic UI defects, documentation typos, minor performance optimizations not affecting availability. | **3 business days** | Next planned sprint |

---

## 4. Incident Response Lifecycle

```
[1. Intake & Triage] -> [2. Containment] -> [3. Investigation] -> [4. Remediation] -> [5. Post-Mortem]
```

### Phase 1: Intake & Triage
1. Incident Commander (IC) is designated.
2. Confirm severity using the matrix above.
3. Open a dedicated incident bridge and document all actions with UTC timestamps and correlation IDs (`X-Request-ID` / `X-Correlation-ID`).

### Phase 2: Containment
- **If Cross-Tenant Breakout Suspected:**
  - Instantly isolate the affected tenant or invoke a write freeze.
  - Revoke affected session tokens.
- **If Key Compromise Suspected:**
  - Immediately follow [`KEY_COMPROMISE.md`](./KEY_COMPROMISE.md) to rotate the KEK and isolate compromised envelope keys.
- **If Whistleblower Leak Suspected:**
  - Follow [`WHISTLEBLOWER_PRIVACY_INCIDENT.md`](./WHISTLEBLOWER_PRIVACY_INCIDENT.md) to preserve anonymous reporter safety.

### Phase 3: Investigation & Telemetry Analysis
1. Inspect structured JSON logs filtering by `request_id` or `correlation_id`.
2. Verify that logs do NOT contain decrypted customer plaintext or reporter secrets (scrubbed by design).
3. Review PostgreSQL query logs and `audit_events` for unauthorized access attempts.

### Phase 4: Remediation & Verification
1. Apply targeted hotfix or configuration change following the [Deployment Runbook](./DEPLOYMENT_AND_ROLLBACK.md).
2. Execute automated test suites (`pytest`, `vitest`, security negative tests).
3. Verify `/health/ready` returns healthy.

### Phase 5: Post-Mortem & Corrective Actions
1. Document root cause analysis (5 Whys), timeline, affected scopes, and corrective actions within 72 hours of incident closure.
2. Log improvements into the engineering backlog.
3. If customer data was impacted, prepare a factual, legally reviewed notification for tenant Owners.

---

## 5. Future Contractual SLA Roadmap (Post-Pilot)
Contractual SLAs will be considered only after:
1. At least 6 consecutive months of production operational evidence.
2. Two consecutive successful full-restore recovery rehearsals.
3. Scope: Availability (99.9%), Recovery (RTO 4h, RPO 1h), and Response.
4. Future remedy: Service credit cap of 25% of monthly fees; tenant exit right triggered only after 3 affected months.
