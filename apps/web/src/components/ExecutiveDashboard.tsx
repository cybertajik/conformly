import { useCallback, useEffect, useState } from "react";
import type { ContinuousComplianceResult, DashboardSummary, TenantRole } from "@conformly/shared";
import { getDashboardSummary, runContinuousComplianceCycle } from "../api";

export interface ExecutiveDashboardProps {
  token: string;
  tenantId: string;
  tenantName: string;
  tenantSlug: string;
  userRole: TenantRole;
  onNavigate: (tab: string) => void;
}

export function ExecutiveDashboard({
  token,
  tenantId,
  tenantName,
  tenantSlug,
  userRole,
  onNavigate,
}: ExecutiveDashboardProps) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<
    "readiness" | "expiring" | "tasks" | "registers" | "activity"
  >("readiness");
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [runningCycle, setRunningCycle] = useState(false);
  const [cycleResult, setCycleResult] = useState<ContinuousComplianceResult | null>(null);

  const fetchSummary = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getDashboardSummary(token, tenantId);
      setSummary(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard metrics");
    } finally {
      setLoading(false);
    }
  }, [token, tenantId]);

  const handleRunCycle = useCallback(async () => {
    try {
      setRunningCycle(true);
      setError(null);
      const res = await runContinuousComplianceCycle(token, tenantId);
      setCycleResult(res);
      const updated = await getDashboardSummary(token, tenantId);
      setSummary(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to execute continuous compliance check");
    } finally {
      setRunningCycle(false);
    }
  }, [token, tenantId]);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getDashboardSummary(token, tenantId);
        if (active) setSummary(data);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "Failed to load dashboard metrics");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [token, tenantId]);

  if (loading) {
    return (
      <div style={{ padding: "3rem 2rem", textAlign: "center" }}>
        <div
          style={{
            display: "inline-block",
            width: "36px",
            height: "36px",
            border: "3px solid var(--border-default)",
            borderTopColor: "var(--accent)",
            borderRadius: "50%",
            animation: "spin 1s linear infinite",
          }}
        />
        <p style={{ color: "var(--text-secondary)", marginTop: "1rem" }}>
          Aggregating live compliance posture and readiness data...
        </p>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div style={{ padding: "2rem" }}>
        <div
          style={{
            padding: "1.5rem",
            background: "var(--color-danger-bg)",
            border: "1px solid var(--color-danger)",
            borderRadius: "var(--radius-md)",
            color: "var(--text-primary)",
          }}
        >
          <h3 style={{ color: "var(--color-danger)", margin: "0 0 0.5rem" }}>
            Failed to Load Executive Dashboard
          </h3>
          <p style={{ margin: "0 0 1rem" }}>{error ?? "No data returned from service."}</p>
          <button className="btn-primary" onClick={() => void fetchSummary()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const isAuditReady = summary.readiness_score >= 80;
  const isActionRequired = summary.readiness_score < 50;

  return (
    <div style={{ padding: "1.5rem 2rem", maxWidth: "1400px", margin: "0 auto" }}>
      {/* ── Top Header ── */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "1.5rem",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.25rem" }}>
            <h1 style={{ fontSize: "1.75rem", fontWeight: 800 }}>Executive Compliance Dashboard</h1>
            <span
              style={{
                fontSize: "0.75rem",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                padding: "0.2rem 0.6rem",
                borderRadius: "var(--radius-sm)",
                background: "var(--accent-subtle)",
                color: "var(--accent)",
                border: "1px solid var(--border-accent)",
                fontWeight: 600,
              }}
            >
              {userRole.replace(/_/g, " ")}
            </span>
          </div>
          <p style={{ color: "var(--text-secondary)", margin: 0, fontSize: "0.95rem" }}>
            Operational readiness command center for <strong style={{ color: "var(--text-primary)" }}>{tenantName}</strong> ({tenantSlug}).
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          {!summary.is_administrator_view && (userRole === "owner" || userRole === "compliance_manager") && (
            <button
              className="btn-secondary"
              style={{ fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.4rem" }}
              onClick={() => void handleRunCycle()}
              disabled={runningCycle}
              title="Trigger automated check for expiring evidence, overdue tasks, review-due policies, and vendor DPAs"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {runningCycle ? "Evaluating..." : "Run Continuous Check"}
            </button>
          )}
          <button
            className="btn-secondary"
            style={{ fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.4rem" }}
            onClick={() => setShowOnboarding(!showOnboarding)}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
            </svg>
            {showOnboarding ? "Hide Guide" : "Onboarding Guide"}
          </button>
          <button
            className="btn-primary"
            style={{ fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.4rem" }}
            onClick={() => onNavigate("preaudit")}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            Run Pre-Audit Check
          </button>
        </div>
      </div>

      {/* ── Continuous Compliance Cycle Result Banner ── */}
      {cycleResult && (
        <div
          style={{
            padding: "1rem 1.25rem",
            marginBottom: "1.5rem",
            background: "rgba(16, 185, 129, 0.08)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            borderRadius: "var(--radius-md)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "1rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <span style={{ fontSize: "1.25rem" }}>⚡</span>
            <div>
              <div style={{ fontWeight: 600, color: "var(--color-success)", fontSize: "0.95rem" }}>
                Continuous Compliance Evaluation Completed
              </div>
              <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                {cycleResult.tasks_created} remediation task(s) created • {cycleResult.notifications_enqueued} notification(s) queued • {cycleResult.overdue_tasks_escalated} overdue task(s) escalated • {cycleResult.missing_dpas_flagged} missing DPA(s) flagged
              </div>
            </div>
          </div>
          <button
            className="btn-secondary"
            style={{ fontSize: "0.8rem", padding: "0.25rem 0.6rem" }}
            onClick={() => setCycleResult(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* ── Administrator Isolation Notice (if applicable) ── */}
      {summary.is_administrator_view && (
        <div
          style={{
            padding: "1rem 1.25rem",
            marginBottom: "1.5rem",
            background: "rgba(59, 130, 246, 0.08)",
            border: "1px solid rgba(59, 130, 246, 0.3)",
            borderRadius: "var(--radius-md)",
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
          }}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--color-info)" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <div>
            <strong style={{ color: "var(--color-info)", fontSize: "0.95rem" }}>
              Tenant Administrator Separation of Duties
            </strong>
            <p style={{ margin: "0.2rem 0 0", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              Per product governance policy, administrative roles are segregated from compliance evidence, policies, and findings.
              Organizational hierarchy, memberships, and storage quotas are shown below.
            </p>
          </div>
        </div>
      )}

      {/* ── Top Metric Cards Strip ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: "1rem",
          marginBottom: "1.5rem",
        }}
      >
        {/* Metric 1: Readiness Score or Member Count */}
        <div
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-lg)",
            padding: "1.25rem",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: 500 }}>
              {summary.is_administrator_view ? "Active Members" : "Pre-Audit Readiness"}
            </span>
            <span
              style={{
                fontSize: "0.75rem",
                padding: "0.2rem 0.5rem",
                borderRadius: "var(--radius-sm)",
                background: summary.is_administrator_view
                  ? "var(--accent-subtle)"
                  : isAuditReady
                  ? "var(--color-success-bg)"
                  : isActionRequired
                  ? "var(--color-danger-bg)"
                  : "var(--color-warning-bg)",
                color: summary.is_administrator_view
                  ? "var(--accent)"
                  : isAuditReady
                  ? "var(--color-success)"
                  : isActionRequired
                  ? "var(--color-danger)"
                  : "var(--color-warning)",
                fontWeight: 600,
              }}
            >
              {summary.is_administrator_view
                ? "Active"
                : isAuditReady
                ? "Audit Ready"
                : isActionRequired
                ? "Gaps Found"
                : "In Progress"}
            </span>
          </div>
          <div style={{ marginTop: "0.75rem", display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
            <span style={{ fontSize: "2.25rem", fontWeight: 900, color: "var(--text-primary)" }}>
              {summary.is_administrator_view
                ? summary.admin_metrics?.total_members ?? 1
                : `${summary.readiness_score}%`}
            </span>
            {!summary.is_administrator_view && (
              <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                {summary.controls_summary.implemented} of {summary.controls_summary.total} controls
              </span>
            )}
          </div>
        </div>

        {/* Metric 2: Controls Coverage or Legal Entities */}
        <div
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-lg)",
            padding: "1.25rem",
          }}
        >
          <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: 500 }}>
            {summary.is_administrator_view ? "Organization Scopes" : "Controls Implemented"}
          </span>
          <div style={{ marginTop: "0.75rem", display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
            <span style={{ fontSize: "2.25rem", fontWeight: 900, color: "var(--color-success)" }}>
              {summary.is_administrator_view
                ? summary.admin_metrics?.legal_entities ?? 0
                : summary.controls_summary.implemented}
            </span>
            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              {summary.is_administrator_view
                ? `${summary.admin_metrics?.business_units ?? 0} Units • ${summary.admin_metrics?.locations ?? 0} Locs`
                : `${summary.controls_summary.in_progress} in progress`}
            </span>
          </div>
        </div>

        {/* Metric 3: Expiring & Overdue Action Items */}
        <div
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-lg)",
            padding: "1.25rem",
          }}
        >
          <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: 500 }}>
            {summary.is_administrator_view ? "Active Plan" : "Items Needing Action (<30d)"}
          </span>
          <div style={{ marginTop: "0.75rem", display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
            <span
              style={{
                fontSize: "2.25rem",
                fontWeight: 900,
                color: summary.is_administrator_view
                  ? "var(--accent)"
                  : summary.expiring_evidence.length + summary.review_due_policies.length > 0
                  ? "var(--color-warning)"
                  : "var(--color-success)",
              }}
            >
              {summary.is_administrator_view
                ? (summary.admin_metrics?.plan_code ?? "tier_a").toUpperCase()
                : summary.expiring_evidence.length + summary.review_due_policies.length}
            </span>
            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              {summary.is_administrator_view
                ? `${summary.admin_metrics?.enabled_modules.length ?? 0} modules`
                : `${summary.expiring_evidence.length} evidence • ${summary.review_due_policies.length} policies`}
            </span>
          </div>
        </div>

        {/* Metric 4: Operational Health (Risks / Vendors / Storage) */}
        <div
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-lg)",
            padding: "1.25rem",
          }}
        >
          <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: 500 }}>
            {summary.is_administrator_view ? "Storage Quota" : "Vendor DPA & Risk Health"}
          </span>
          <div style={{ marginTop: "0.75rem", display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
            <span
              style={{
                fontSize: "2.25rem",
                fontWeight: 900,
                color: summary.is_administrator_view
                  ? "var(--text-primary)"
                  : summary.vendor_health.missing_dpa_count > 0
                  ? "var(--color-danger)"
                  : "var(--color-success)",
              }}
            >
              {summary.is_administrator_view
                ? `${Math.round((summary.admin_metrics?.max_storage_bytes ?? 10737418240) / (1024 * 1024 * 1024))} GB`
                : `${summary.vendor_health.signed_dpa_count}/${summary.vendor_health.total_vendors}`}
            </span>
            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              {summary.is_administrator_view
                ? "AES-256-GCM encrypted"
                : `${summary.vendor_health.missing_dpa_count} missing DPAs`}
            </span>
          </div>
        </div>
      </div>

      {/* ── Sub-navigation Tabs ── */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--border-default)",
          marginBottom: "1.5rem",
          gap: "0.5rem",
          overflowX: "auto",
        }}
      >
        <button
          onClick={() => setActiveSubTab("readiness")}
          style={{
            padding: "0.6rem 1rem",
            background: "transparent",
            border: "none",
            borderBottom: activeSubTab === "readiness" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeSubTab === "readiness" ? "var(--accent)" : "var(--text-secondary)",
            fontWeight: 600,
            cursor: "pointer",
            fontSize: "0.9rem",
          }}
        >
          Are We Ready?
        </button>
        <button
          onClick={() => setActiveSubTab("expiring")}
          style={{
            padding: "0.6rem 1rem",
            background: "transparent",
            border: "none",
            borderBottom: activeSubTab === "expiring" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeSubTab === "expiring" ? "var(--accent)" : "var(--text-secondary)",
            fontWeight: 600,
            cursor: "pointer",
            fontSize: "0.9rem",
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
          }}
        >
          What Expires Next?
          {summary.expiring_evidence.length + summary.review_due_policies.length > 0 && (
            <span
              style={{
                fontSize: "0.7rem",
                padding: "0.1rem 0.45rem",
                borderRadius: "var(--radius-full)",
                background: "var(--color-warning-bg)",
                color: "var(--color-warning)",
              }}
            >
              {summary.expiring_evidence.length + summary.review_due_policies.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveSubTab("tasks")}
          style={{
            padding: "0.6rem 1rem",
            background: "transparent",
            border: "none",
            borderBottom: activeSubTab === "tasks" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeSubTab === "tasks" ? "var(--accent)" : "var(--text-secondary)",
            fontWeight: 600,
            cursor: "pointer",
            fontSize: "0.9rem",
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
          }}
        >
          Who Owns What?
          {summary.open_tasks.length > 0 && (
            <span
              style={{
                fontSize: "0.7rem",
                padding: "0.1rem 0.45rem",
                borderRadius: "var(--radius-full)",
                background: "var(--accent-subtle)",
                color: "var(--accent)",
              }}
            >
              {summary.open_tasks.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveSubTab("registers")}
          style={{
            padding: "0.6rem 1rem",
            background: "transparent",
            border: "none",
            borderBottom: activeSubTab === "registers" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeSubTab === "registers" ? "var(--accent)" : "var(--text-secondary)",
            fontWeight: 600,
            cursor: "pointer",
            fontSize: "0.9rem",
          }}
        >
          Operational Health
        </button>
        <button
          onClick={() => setActiveSubTab("activity")}
          style={{
            padding: "0.6rem 1rem",
            background: "transparent",
            border: "none",
            borderBottom: activeSubTab === "activity" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeSubTab === "activity" ? "var(--accent)" : "var(--text-secondary)",
            fontWeight: 600,
            cursor: "pointer",
            fontSize: "0.9rem",
          }}
        >
          What Changed? (Audit)
        </button>
      </div>

      {/* ── Sub-tab 1: Are We Ready? ── */}
      {activeSubTab === "readiness" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg)",
              padding: "1.5rem",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <div>
                <h3 style={{ fontSize: "1.1rem", margin: 0 }}>Adopted Compliance Frameworks</h3>
                <p style={{ color: "var(--text-secondary)", margin: "0.2rem 0 0", fontSize: "0.85rem" }}>
                  Real-time control implementation posture across active canonical frameworks.
                </p>
              </div>
              <button className="btn-secondary" style={{ fontSize: "0.8rem" }} onClick={() => onNavigate("frameworks")}>
                Manage Frameworks
              </button>
            </div>

            {summary.frameworks_adopted.length === 0 ? (
              <div
                style={{
                  padding: "2rem",
                  textAlign: "center",
                  background: "var(--bg-elevated)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <p style={{ color: "var(--text-secondary)", margin: "0 0 1rem" }}>
                  No compliance frameworks currently adopted. Adopt ISO/IEC 27001, SOC 2, or HIPAA to begin tracking readiness.
                </p>
                <button className="btn-primary" onClick={() => onNavigate("frameworks")}>
                  Browse Framework Catalog
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                {summary.frameworks_adopted.map((f) => (
                  <div
                    key={f.framework_id}
                    style={{
                      padding: "1rem",
                      background: "var(--bg-elevated)",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid var(--border-subtle)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                      <strong style={{ color: "var(--text-primary)" }}>{f.framework_name}</strong>
                      <span style={{ fontWeight: 700, color: "var(--accent)" }}>{f.progress_percentage}% Ready</span>
                    </div>
                    <div
                      style={{
                        height: "8px",
                        background: "rgba(255,255,255,0.06)",
                        borderRadius: "var(--radius-full)",
                        overflow: "hidden",
                        marginBottom: "0.4rem",
                      }}
                    >
                      <div
                        style={{
                          height: "100%",
                          width: `${f.progress_percentage}%`,
                          background: "linear-gradient(90deg, var(--accent) 0%, #34d399 100%)",
                          borderRadius: "var(--radius-full)",
                        }}
                      />
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      <span>{f.implemented_controls} implemented</span>
                      <span>{f.total_controls - f.implemented_controls} remaining</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Verification Badge & Public Proof Card */}
          <div
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg)",
              padding: "1.5rem",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "1rem",
            }}
          >
            <div>
              <h3 style={{ fontSize: "1.1rem", margin: "0 0 0.3rem" }}>What Can We Prove to Auditors & Customers?</h3>
              <p style={{ color: "var(--text-secondary)", margin: 0, fontSize: "0.85rem", maxWidth: "600px" }}>
                Generate SHA-256 frozen audit manifests, issue time-stamped Pre-Audit readiness badges, or share an
                isolated public security profile to showcase certified controls.
              </p>
            </div>
            <div style={{ display: "flex", gap: "0.75rem" }}>
              <button className="btn-secondary" style={{ fontSize: "0.85rem" }} onClick={() => onNavigate("public_profile")}>
                View Trust Center
              </button>
              <button className="btn-primary" style={{ fontSize: "0.85rem" }} onClick={() => onNavigate("preaudit")}>
                Generate Audit Manifest
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Sub-tab 2: What Expires Next? ── */}
      {activeSubTab === "expiring" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* Expiring Evidence */}
          <div
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg)",
              padding: "1.5rem",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <div>
                <h3 style={{ fontSize: "1.1rem", margin: 0 }}>Evidence Approaching Expiry (&lt; 30 Days)</h3>
                <p style={{ color: "var(--text-secondary)", margin: "0.2rem 0 0", fontSize: "0.85rem" }}>
                  Ensure continuous compliance by refreshing time-bound evidence before validity lapses.
                </p>
              </div>
              <button className="btn-secondary" style={{ fontSize: "0.8rem" }} onClick={() => onNavigate("compliance")}>
                Evidence Vault
              </button>
            </div>

            {summary.expiring_evidence.length === 0 ? (
              <p style={{ color: "var(--text-muted)", fontStyle: "italic", margin: 0 }}>
                No evidence items expiring in the next 30 days. All evidence valid!
              </p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border-default)", color: "var(--text-muted)", textAlign: "left" }}>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Title</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Classification</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Expires</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Days Remaining</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.expiring_evidence.map((ev) => (
                      <tr key={ev.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                        <td style={{ padding: "0.7rem 0.8rem", fontWeight: 600 }}>{ev.title}</td>
                        <td style={{ padding: "0.7rem 0.8rem" }}>
                          <span
                            style={{
                              fontSize: "0.75rem",
                              padding: "0.15rem 0.5rem",
                              borderRadius: "var(--radius-sm)",
                              background: "rgba(59, 130, 246, 0.1)",
                              color: "var(--color-info)",
                            }}
                          >
                            {ev.classification}
                          </span>
                        </td>
                        <td style={{ padding: "0.7rem 0.8rem", color: "var(--text-secondary)" }}>
                          {new Date(ev.expires_at).toLocaleDateString()}
                        </td>
                        <td style={{ padding: "0.7rem 0.8rem" }}>
                          <span
                            style={{
                              fontSize: "0.75rem",
                              padding: "0.2rem 0.5rem",
                              borderRadius: "var(--radius-sm)",
                              background: ev.days_remaining <= 7 ? "var(--color-danger-bg)" : "var(--color-warning-bg)",
                              color: ev.days_remaining <= 7 ? "var(--color-danger)" : "var(--color-warning)",
                              fontWeight: 700,
                            }}
                          >
                            {ev.days_remaining} days
                          </span>
                        </td>
                        <td style={{ padding: "0.7rem 0.8rem" }}>
                          <button
                            className="btn-secondary"
                            style={{ fontSize: "0.75rem", padding: "0.25rem 0.6rem" }}
                            onClick={() => onNavigate("compliance")}
                          >
                            Upload Version
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Policies Due for Review */}
          <div
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg)",
              padding: "1.5rem",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <div>
                <h3 style={{ fontSize: "1.1rem", margin: 0 }}>Governance Policies Due for Review</h3>
                <p style={{ color: "var(--text-secondary)", margin: "0.2rem 0 0", fontSize: "0.85rem" }}>
                  Annual and periodic reviews required to satisfy framework audit controls.
                </p>
              </div>
              <button className="btn-secondary" style={{ fontSize: "0.8rem" }} onClick={() => onNavigate("compliance")}>
                Policy Manager
              </button>
            </div>

            {summary.review_due_policies.length === 0 ? (
              <p style={{ color: "var(--text-muted)", fontStyle: "italic", margin: 0 }}>
                No policies due for review. All policies up to date.
              </p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border-default)", color: "var(--text-muted)", textAlign: "left" }}>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Policy Title</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Due Date</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Status</th>
                      <th style={{ padding: "0.6rem 0.8rem" }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.review_due_policies.map((p) => (
                      <tr key={p.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                        <td style={{ padding: "0.7rem 0.8rem", fontWeight: 600 }}>{p.title}</td>
                        <td style={{ padding: "0.7rem 0.8rem", color: "var(--text-secondary)" }}>
                          {new Date(p.review_due_at).toLocaleDateString()}
                        </td>
                        <td style={{ padding: "0.7rem 0.8rem" }}>
                          <span
                            style={{
                              fontSize: "0.75rem",
                              padding: "0.2rem 0.5rem",
                              borderRadius: "var(--radius-sm)",
                              background: p.days_remaining <= 0 ? "var(--color-danger-bg)" : "var(--color-warning-bg)",
                              color: p.days_remaining <= 0 ? "var(--color-danger)" : "var(--color-warning)",
                              fontWeight: 700,
                            }}
                          >
                            {p.days_remaining <= 0 ? "Overdue" : `${p.days_remaining} days left`}
                          </span>
                        </td>
                        <td style={{ padding: "0.7rem 0.8rem" }}>
                          <button
                            className="btn-secondary"
                            style={{ fontSize: "0.75rem", padding: "0.25rem 0.6rem" }}
                            onClick={() => onNavigate("compliance")}
                          >
                            Review & Approve
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Sub-tab 3: Who Owns What? (Tasks) ── */}
      {activeSubTab === "tasks" && (
        <div
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-lg)",
            padding: "1.5rem",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <div>
              <h3 style={{ fontSize: "1.1rem", margin: 0 }}>High-Priority Compliance Action Items</h3>
              <p style={{ color: "var(--text-secondary)", margin: "0.2rem 0 0", fontSize: "0.85rem" }}>
                Assigned operational tasks preventing compliance drift.
              </p>
            </div>
            <button className="btn-secondary" style={{ fontSize: "0.8rem" }} onClick={() => onNavigate("compliance")}>
              View All Tasks
            </button>
          </div>

          {summary.open_tasks.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontStyle: "italic", margin: 0 }}>
              All assigned tasks are completed! Great job maintaining zero task backlog.
            </p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border-default)", color: "var(--text-muted)", textAlign: "left" }}>
                    <th style={{ padding: "0.6rem 0.8rem" }}>Task Title</th>
                    <th style={{ padding: "0.6rem 0.8rem" }}>Priority</th>
                    <th style={{ padding: "0.6rem 0.8rem" }}>Status</th>
                    <th style={{ padding: "0.6rem 0.8rem" }}>Due Date</th>
                    <th style={{ padding: "0.6rem 0.8rem" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.open_tasks.map((t) => (
                    <tr key={t.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                      <td style={{ padding: "0.7rem 0.8rem", fontWeight: 600 }}>{t.title}</td>
                      <td style={{ padding: "0.7rem 0.8rem" }}>
                        <span
                          style={{
                            fontSize: "0.75rem",
                            padding: "0.15rem 0.5rem",
                            borderRadius: "var(--radius-sm)",
                            background:
                              t.priority.toLowerCase() === "critical"
                                ? "var(--color-danger-bg)"
                                : t.priority.toLowerCase() === "high"
                                ? "var(--color-warning-bg)"
                                : "rgba(255,255,255,0.08)",
                            color:
                              t.priority.toLowerCase() === "critical"
                                ? "var(--color-danger)"
                                : t.priority.toLowerCase() === "high"
                                ? "var(--color-warning)"
                                : "var(--text-primary)",
                            fontWeight: 700,
                            textTransform: "uppercase",
                          }}
                        >
                          {t.priority}
                        </span>
                      </td>
                      <td style={{ padding: "0.7rem 0.8rem", color: "var(--text-secondary)" }}>
                        {t.status.replace(/_/g, " ")}
                      </td>
                      <td style={{ padding: "0.7rem 0.8rem", color: "var(--text-secondary)" }}>
                        {t.due_date ? new Date(t.due_date).toLocaleDateString() : "—"}
                      </td>
                      <td style={{ padding: "0.7rem 0.8rem" }}>
                        <button
                          className="btn-secondary"
                          style={{ fontSize: "0.75rem", padding: "0.25rem 0.6rem" }}
                          onClick={() => onNavigate("compliance")}
                        >
                          Complete Task
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Sub-tab 4: Operational Registers ── */}
      {activeSubTab === "registers" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.5rem" }}>
          {/* Top Risks */}
          <div
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg)",
              padding: "1.5rem",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h3 style={{ fontSize: "1.1rem", margin: 0 }}>Top Residual Risks</h3>
              <button className="btn-secondary" style={{ fontSize: "0.8rem" }} onClick={() => onNavigate("risks")}>
                Risk Register
              </button>
            </div>

            {summary.top_risks.length === 0 ? (
              <p style={{ color: "var(--text-muted)", fontStyle: "italic", margin: 0 }}>
                No active risks recorded in the Risk Register.
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {summary.top_risks.map((r) => (
                  <div
                    key={r.id}
                    style={{
                      padding: "0.75rem 1rem",
                      background: "var(--bg-elevated)",
                      borderRadius: "var(--radius-md)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <strong style={{ fontSize: "0.9rem", color: "var(--text-primary)" }}>{r.title}</strong>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
                        Status: {r.status}
                      </div>
                    </div>
                    <span
                      style={{
                        fontSize: "0.85rem",
                        padding: "0.2rem 0.6rem",
                        borderRadius: "var(--radius-sm)",
                        background:
                          (r.residual_score ?? r.inherent_score) >= 15
                            ? "var(--color-danger-bg)"
                            : (r.residual_score ?? r.inherent_score) >= 8
                            ? "var(--color-warning-bg)"
                            : "var(--color-success-bg)",
                        color:
                          (r.residual_score ?? r.inherent_score) >= 15
                            ? "var(--color-danger)"
                            : (r.residual_score ?? r.inherent_score) >= 8
                            ? "var(--color-warning)"
                            : "var(--color-success)",
                        fontWeight: 800,
                      }}
                    >
                      Score: {r.residual_score ?? r.inherent_score}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Vendor DPA Health */}
          <div
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg)",
              padding: "1.5rem",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h3 style={{ fontSize: "1.1rem", margin: 0 }}>Vendor DPA & Third-Party Risk</h3>
              <button className="btn-secondary" style={{ fontSize: "0.8rem" }} onClick={() => onNavigate("vendors")}>
                Vendor Register
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div
                style={{
                  padding: "1rem",
                  background: "var(--bg-elevated)",
                  borderRadius: "var(--radius-md)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span>Total Vendors Evaluated</span>
                <strong style={{ fontSize: "1.2rem", color: "var(--text-primary)" }}>
                  {summary.vendor_health.total_vendors}
                </strong>
              </div>

              <div
                style={{
                  padding: "1rem",
                  background: "var(--bg-elevated)",
                  borderRadius: "var(--radius-md)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span>Executed Data Processing Agreements (DPA)</span>
                <strong style={{ fontSize: "1.2rem", color: "var(--color-success)" }}>
                  {summary.vendor_health.signed_dpa_count}
                </strong>
              </div>

              <div
                style={{
                  padding: "1rem",
                  background:
                    summary.vendor_health.missing_dpa_count > 0 ? "var(--color-danger-bg)" : "var(--bg-elevated)",
                  border:
                    summary.vendor_health.missing_dpa_count > 0 ? "1px solid var(--color-danger)" : "none",
                  borderRadius: "var(--radius-md)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span
                  style={{
                    color: summary.vendor_health.missing_dpa_count > 0 ? "var(--color-danger)" : "var(--text-primary)",
                  }}
                >
                  Missing DPAs Requiring Action
                </span>
                <strong
                  style={{
                    fontSize: "1.2rem",
                    color: summary.vendor_health.missing_dpa_count > 0 ? "var(--color-danger)" : "var(--text-primary)",
                  }}
                >
                  {summary.vendor_health.missing_dpa_count}
                </strong>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Sub-tab 5: What Changed? (Live Activity Feed) ── */}
      {activeSubTab === "activity" && (
        <div
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-lg)",
            padding: "1.5rem",
          }}
        >
          <h3 style={{ fontSize: "1.1rem", margin: "0 0 0.5rem" }}>What Changed? (Audit Trail Activity Stream)</h3>
          <p style={{ color: "var(--text-secondary)", margin: "0 0 1rem", fontSize: "0.85rem" }}>
            Append-only record of security and compliance state changes within the tenant.
          </p>

          {summary.recent_activity.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontStyle: "italic", margin: 0 }}>No recent audit events logged.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
              {summary.recent_activity.map((ev) => (
                <div
                  key={ev.id}
                  style={{
                    padding: "0.75rem 1rem",
                    background: "var(--bg-elevated)",
                    borderRadius: "var(--radius-md)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    fontSize: "0.85rem",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <span
                      style={{
                        padding: "0.2rem 0.5rem",
                        borderRadius: "var(--radius-sm)",
                        background: "rgba(255,255,255,0.06)",
                        fontSize: "0.75rem",
                        fontFamily: "monospace",
                        color: "var(--accent)",
                      }}
                    >
                      {ev.action}
                    </span>
                    <span style={{ color: "var(--text-secondary)" }}>
                      Resource: <strong style={{ color: "var(--text-primary)" }}>{ev.resource_type}</strong>
                    </span>
                  </div>
                  <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                    {new Date(ev.occurred_at).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Collapsible Getting Started Guide (Onboarding Drawer) ── */}
      {showOnboarding && (
        <div
          style={{
            marginTop: "2rem",
            background: "var(--bg-card)",
            border: "1px solid var(--border-accent)",
            borderRadius: "var(--radius-lg)",
            padding: "1.5rem",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h3 style={{ fontSize: "1.1rem", margin: 0 }}>Compliance Onboarding Checklist</h3>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Step-by-step readiness guide</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem" }}>
            <div
              style={{
                padding: "1rem",
                background: "var(--bg-elevated)",
                borderRadius: "var(--radius-md)",
                cursor: "pointer",
              }}
              onClick={() => onNavigate("frameworks")}
            >
              <span style={{ fontWeight: 800, color: "var(--accent)", display: "block", marginBottom: "0.25rem" }}>
                Step 1
              </span>
              <strong style={{ fontSize: "0.9rem", color: "var(--text-primary)" }}>Adopt Canonical Frameworks</strong>
              <p style={{ margin: "0.4rem 0 0", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                Select ISO 27001, SOC 2, or HIPAA to establish your baseline requirements.
              </p>
            </div>

            <div
              style={{
                padding: "1rem",
                background: "var(--bg-elevated)",
                borderRadius: "var(--radius-md)",
                cursor: "pointer",
              }}
              onClick={() => onNavigate("compliance")}
            >
              <span style={{ fontWeight: 800, color: "var(--accent)", display: "block", marginBottom: "0.25rem" }}>
                Step 2
              </span>
              <strong style={{ fontSize: "0.9rem", color: "var(--text-primary)" }}>Map Controls & Evidence</strong>
              <p style={{ margin: "0.4rem 0 0", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                Upload AES-256-GCM encrypted evidence files and approve governance policies.
              </p>
            </div>

            <div
              style={{
                padding: "1rem",
                background: "var(--bg-elevated)",
                borderRadius: "var(--radius-md)",
                cursor: "pointer",
              }}
              onClick={() => onNavigate("risks")}
            >
              <span style={{ fontWeight: 800, color: "var(--accent)", display: "block", marginBottom: "0.25rem" }}>
                Step 3
              </span>
              <strong style={{ fontSize: "0.9rem", color: "var(--text-primary)" }}>Populate Registers</strong>
              <p style={{ margin: "0.4rem 0 0", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                Document organizational risks, assets, and vendor DPAs to fulfill audit requirements.
              </p>
            </div>

            <div
              style={{
                padding: "1rem",
                background: "var(--bg-elevated)",
                borderRadius: "var(--radius-md)",
                cursor: "pointer",
              }}
              onClick={() => onNavigate("preaudit")}
            >
              <span style={{ fontWeight: 800, color: "var(--accent)", display: "block", marginBottom: "0.25rem" }}>
                Step 4
              </span>
              <strong style={{ fontSize: "0.9rem", color: "var(--text-primary)" }}>Run Pre-Audit Check</strong>
              <p style={{ margin: "0.4rem 0 0", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                Generate deterministic scoring, cryptographic manifests, and readiness badges.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
