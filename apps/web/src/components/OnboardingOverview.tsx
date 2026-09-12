import type { TenantRole } from "@conformly/shared";

export type Tab =
  | "overview"
  | "frameworks"
  | "compliance"
  | "lifecycle"
  | "preaudit"
  | "whistleblower"
  | "public_whistleblower"
  | "public_profile"
  | "trust_center"
  | "members";

interface OnboardingOverviewProps {
  tenantName: string;
  tenantSlug: string;
  userRole: TenantRole;
  onNavigate: (tab: Tab) => void;
}

const checklistItems: {
  step: number;
  title: string;
  desc: string;
  tab: Tab;
  btnLabel: string;
  icon: string;
}[] = [
  {
    step: 1,
    title: "Adopt Canonical Compliance Framework",
    desc: "Select official frameworks (ISO/IEC 27001, SOC 2, HIPAA) or define custom overlays.",
    tab: "frameworks",
    btnLabel: "View Catalog",
    icon: "M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10",
  },
  {
    step: 2,
    title: "Implement Controls & Collect Evidence",
    desc: "Upload evidence with AES-256-GCM envelope encryption and map controls to policies.",
    tab: "compliance",
    btnLabel: "Open Compliance",
    icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
  },
  {
    step: 3,
    title: "Run Pre-Audit Readiness Check",
    desc: "Execute deterministic scoring, generate SHA-256 audit manifests, and issue readiness credentials.",
    tab: "preaudit",
    btnLabel: "Start Pre-Audit",
    icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4",
  },
  {
    step: 4,
    title: "Publish Public Trust Center",
    desc: "Showcase security commitments, verified readiness credentials, and third-party certifications.",
    tab: "public_profile",
    btnLabel: "Trust Center",
    icon: "M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064",
  },
  {
    step: 5,
    title: "Configure Anonymous Whistleblower Channel",
    desc: "Provide confidential reporting protected by PBKDF2 hash tracking and zero IP logging.",
    tab: "whistleblower",
    btnLabel: "Whistleblower Portal",
    icon: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z",
  },
];

const securityFeatures = [
  {
    title: "Row-Level Security",
    desc: "Strict kernel-enforced tenant boundaries on every SQL query.",
    color: "var(--color-success)",
  },
  {
    title: "AES-256-GCM Encryption",
    desc: "Unique DEK per file; zero unencrypted evidence at rest.",
    color: "var(--color-info)",
  },
  {
    title: "Anonymous Whistleblower",
    desc: "PBKDF2 return keys with zero IP address or telemetry logging.",
    color: "var(--color-warning)",
  },
  {
    title: "Auditable Data Exit",
    desc: "30-day export window, 90-day multi-table cryptographic deletion proof.",
    color: "var(--color-purple)",
  },
];

const supportTiers = [
  {
    severity: "Critical (P1)",
    classification: "Security incident, data exposure, total service outage",
    response: "4 Hours (24/7 intake)",
    channel: "security-intake@conformly.com",
    color: "var(--color-danger)",
  },
  {
    severity: "High (P2)",
    classification: "Core workflow degraded (evidence upload, pre-audit)",
    response: "1 Business Day",
    channel: "support@conformly.com",
    color: "var(--color-warning)",
  },
  {
    severity: "Medium (P3)",
    classification: "Non-critical feature issue, UI defect",
    response: "2 Business Days",
    channel: "support@conformly.com",
    color: "var(--color-info)",
  },
  {
    severity: "Low (P4)",
    classification: "General inquiry, onboarding advisory",
    response: "3 Business Days",
    channel: "support@conformly.com",
    color: "var(--text-muted)",
  },
];

export function OnboardingOverview({
  tenantName,
  tenantSlug,
  userRole,
  onNavigate,
}: OnboardingOverviewProps) {
  const formattedRole = userRole.replaceAll("_", " ");

  return (
    <div className="onboarding-overview">
      {/* Header Card */}
      <div
        className="card"
        style={{
          marginBottom: "1.5rem",
          background: "linear-gradient(135deg, rgba(16, 185, 129, 0.08), rgba(59, 130, 246, 0.05))",
          borderColor: "var(--border-accent)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <span className="eyebrow">Operational Readiness &bull; Active Pilot</span>
            <h2 style={{ margin: "0.5rem 0", fontSize: "1.625rem" }}>{tenantName}</h2>
            <p style={{ margin: 0, fontSize: "0.875rem" }}>
              Organization Slug: <code>{tenantSlug}</code> &bull; Role:{" "}
              <strong style={{ textTransform: "capitalize", color: "var(--text-primary)" }}>{formattedRole}</strong>
            </p>
          </div>
          <div>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "0.4rem 0.9rem",
                borderRadius: "var(--radius-full)",
                background: "var(--color-success-bg)",
                color: "var(--color-success)",
                fontWeight: 700,
                fontSize: "0.8rem",
                border: "1px solid rgba(16, 185, 129, 0.25)",
              }}
            >
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--color-success)", display: "inline-block" }} />
              Pilot Operational
            </span>
          </div>
        </div>
      </div>

      {/* Compliance Disclaimer */}
      <div
        role="region"
        aria-label="Compliance disclaimer"
        className="alert"
        style={{
          background: "var(--color-warning-bg)",
          border: "1px solid rgba(245, 158, 11, 0.2)",
          color: "#fbbf24",
          marginBottom: "2rem",
        }}
      >
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "baseline" }}>
          <strong style={{ fontSize: "0.875rem", flexShrink: 0 }}>⚠ Notice:</strong>
          <p style={{ margin: 0, fontSize: "0.8125rem", lineHeight: "1.5", color: "var(--text-secondary)" }}>
            <strong style={{ color: "#fbbf24" }}>Conformly is an audit-readiness and compliance operations platform, not an accredited certification body.</strong>{" "}
            Pre-audit assessments, readiness scores, and Conformly-issued badges reflect deterministic evidence checks and internal readiness posture; they do not constitute official accredited third-party certifications.
          </p>
        </div>
      </div>

      {/* Readiness Onboarding Checklist */}
      <section aria-labelledby="readiness-checklist-title" style={{ marginBottom: "2.5rem" }}>
        <h3 id="readiness-checklist-title" style={{ fontSize: "1.125rem", marginBottom: "0.5rem" }}>
          Pre-Audit Readiness Onboarding
        </h3>
        <p style={{ marginTop: 0, marginBottom: "1.25rem", fontSize: "0.8125rem" }}>
          Complete these foundational milestones to prepare your organization for third-party compliance audits.
        </p>

        <div style={{ display: "grid", gap: "0.75rem" }}>
          {checklistItems.map((item) => (
            <div
              key={item.step}
              className="card"
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "1rem",
                padding: "1rem 1.25rem",
                marginBottom: 0,
              }}
            >
              <div style={{ display: "flex", gap: "1rem", alignItems: "flex-start", flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: "var(--radius-md)",
                    background: "var(--accent-subtle)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d={item.icon} />
                  </svg>
                </div>
                <div>
                  <div style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "0.875rem" }}>
                    {item.step}. {item.title}
                  </div>
                  <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginTop: "0.15rem" }}>
                    {item.desc}
                  </div>
                </div>
              </div>
              <button
                type="button"
                className="secondary"
                style={{ minHeight: "2rem", padding: "0.35rem 0.85rem", fontSize: "0.8125rem" }}
                onClick={() => onNavigate(item.tab)}
              >
                {item.btnLabel} →
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* Pilot Support & Operations */}
      <section
        aria-labelledby="pilot-support-title"
        className="card"
        style={{ marginBottom: "2rem", padding: "1.5rem" }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "0.5rem", marginBottom: "1rem" }}>
          <h3 id="pilot-support-title" style={{ margin: 0, fontSize: "1.125rem" }}>
            Pilot Service & Support Intake
          </h3>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            24/7 Security Intake &bull; Business-Hours Operations
          </span>
        </div>

        <p style={{ fontSize: "0.8125rem", margin: "0 0 1.25rem 0" }}>
          During the paid pilot program, service targets represent operational response guidelines (not contractual SLAs). Contractual SLAs are phased in following six months of production telemetry.
        </p>

        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Severity Level</th>
                <th>Classification</th>
                <th>Response Objective</th>
                <th>Intake Channel</th>
              </tr>
            </thead>
            <tbody>
              {supportTiers.map((tier) => (
                <tr key={tier.severity}>
                  <td style={{ fontWeight: 700, color: tier.color }}>{tier.severity}</td>
                  <td>{tier.classification}</td>
                  <td style={{ fontWeight: 600, color: "var(--text-primary)" }}>{tier.response}</td>
                  <td><code>{tier.channel}</code></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Security Invariants */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(14rem, 1fr))",
          gap: "0.75rem",
        }}
      >
        {securityFeatures.map((feat) => (
          <div
            key={feat.title}
            className="card"
            style={{
              padding: "1rem 1.25rem",
              marginBottom: 0,
              borderLeft: `3px solid ${feat.color}`,
            }}
          >
            <strong style={{ color: "var(--text-primary)", fontSize: "0.8125rem" }}>{feat.title}</strong>
            <p style={{ margin: "0.3rem 0 0 0", fontSize: "0.8125rem" }}>{feat.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
