# Conformly — Whistleblower Privacy Incident & Anti-De-anonymization Runbook

## 1. Overview & Ethical Mandate

Conformly's Whistleblower module provides an uncompromising **zero-knowledge anonymous reporting intake channel**. In accordance with [`AGENTS.md`](file:///c:/Users/AD/Desktop/conformly/AGENTS.md) and [`docs/WHISTLEBLOWER_THREAT_MODEL.md`](file:///c:/Users/AD/Desktop/conformly/docs/WHISTLEBLOWER_THREAT_MODEL.md):
- Reporters are **never** required to provide personal identity, emails, or phone numbers.
- IP addresses, browser user-agents, and client device fingerprints are **never** stored or linked to case records.
- Case tracking uses a one-way salted `PBKDF2-HMAC-SHA256` verifier (`100,000` iterations). The raw return secret key is presented to the reporter once and is **never** retained in plaintext on Conformly systems.
- Report summaries and message bodies use application-layer AES-256-GCM envelope encryption.

A Whistleblower Privacy Incident is classified as **SEV-1 (Critical)** and triggers an immediate containment and forensic review.

---

## 2. Threat Scenarios & Triage Matrix

| Threat Scenario | Severity | Description | Immediate Action |
| :--- | :--- | :--- | :--- |
| **Telemetry / Log Leakage** | SEV-1 | Return secret key, IP address, or reporter identifiers found in application logs. | Immediate log scrubbing, pipeline filter update, rotation of exposed credentials. |
| **Network Interception** | SEV-1 | Man-in-the-middle suspicion or lack of TLS termination on reporting domain. | Enforce HSTS preloading, DNSSEC validation, certificate renewal. |
| **Unauthorized Case Access** | SEV-1 | Non-handler role (e.g. Member or external user) gaining access to internal case triage. | Revoke compromised user sessions, audit RLS policies, check RBAC capabilities. |
| **Loss of Return Key** | SEV-3 | Reporter loses their raw return secret key. | Inform reporter that return keys are cryptographically non-recoverable by design; reporter must submit a follow-up report referencing previous case date if desired. |

---

## 3. Incident Containment & Scrubbing Procedures

### Procedure A: Telemetry & Log De-contamination
If raw secrets or sensitive reporter metadata are detected in log streams:
1. **Identify Log Records:** Isolate log sinks containing the compromised entries using correlation IDs.
2. **Execute In-Place Log Scrubbing:**
   - In cloud logging (CloudWatch, Datadog), issue targeted deletion for the specific timeframe and stream.
   - Purge cache indices.
3. **Verify Safe Key Whitelist:**
   - Verify `SAFE_METADATA_KEYS` in [`apps/api/src/conformly/audit/service.py`](file:///c:/Users/AD/Desktop/conformly/apps/api/src/conformly/audit/service.py).
   - Ensure neither `return_key`, `secret_key`, `ip_address`, nor `user_agent` can ever be passed to audit event logging.

### Procedure B: Case Access Auditing
To confirm zero unauthorized inspection:
```sql
SELECT 
    id, tenant_id, actor_user_id, action, timestamp, metadata
FROM audit_events
WHERE action LIKE 'whistleblower%'
  AND timestamp >= NOW() - INTERVAL '7 days'
ORDER BY timestamp DESC;
```
Verify that all `actor_user_id` values correspond strictly to authorized handlers (`Role.OWNER`, `Role.ADMINISTRATOR`, `Role.COMPLIANCE_MANAGER`).

---

## 4. No-Identity-Reconstruction Guarantee
Conformly engineers and operators are **strictly forbidden** from attempting to reconstruct or deanonymize any anonymous reporter. Any tool, script, or automated heuristic designed to correlate access times, packet sizes, or writing style is prohibited in both software code and operational runbooks.
