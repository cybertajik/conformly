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

export function OnboardingOverview({
  tenantName,
  tenantSlug,
  userRole,
  onNavigate,
}: OnboardingOverviewProps) {
  const formattedRole = userRole.replaceAll("_", " ");

  return (
    <div className="onboarding-overview">
      <div className="overview-header-card" style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <span className="eyebrow">Operational Readiness &bull; Active Pilot</span>
            <h2 style={{ margin: "0.25rem 0 0.5rem 0", fontSize: "1.75rem" }}>{tenantName}</h2>
            <p style={{ margin: 0, color: "#4b6358" }}>
              Organization Slug: <code>{tenantSlug}</code> &bull; Role: <strong style={{ textTransform: "capitalize" }}>{formattedRole}</strong>
            </p>
          </div>
          <div style={{ textAlign: "right" }}>
            <span
              style={{
                display: "inline-block",
                padding: "0.35rem 0.85rem",
                borderRadius: "2rem",
                backgroundColor: "#e3f5eb",
                color: "#106346",
                fontWeight: 700,
                fontSize: "0.85rem",
                border: "1px solid #99d8b8",
              }}
            >
              &bull; Pilot Operational
            </span>
          </div>
        </div>
      </div>

      {/* Mandatory Platform Disclaimer */}
      <div
        role="region"
        aria-label="Compliance disclaimer"
        style={{
          backgroundColor: "#fef9e7",
          border: "1px solid #f0cf65",
          borderRadius: "0.75rem",
          padding: "1rem 1.25rem",
          marginBottom: "1.5rem",
          color: "#6b4f00",
        }}
      >
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "baseline" }}>
          <strong style={{ fontSize: "1rem" }}>Notice:</strong>
          <p style={{ margin: 0, fontSize: "0.92rem", lineHeight: "1.45" }}>
            <strong>Conformly is an audit-readiness and compliance operations platform, not an accredited certification body.</strong>{" "}
            Pre-audit assessments, readiness scores, and Conformly-issued badges reflect deterministic evidence checks and internal readiness posture; they do not constitute official accredited third-party certifications.
          </p>
        </div>
      </div>

      {/* Readiness Onboarding Checklist */}
      <section aria-labelledby="readiness-checklist-title" style={{ marginBottom: "2rem" }}>
        <h3 id="readiness-checklist-title" style={{ fontSize: "1.25rem", marginBottom: "0.75rem" }}>
          Pre-Audit Readiness Onboarding
        </h3>
        <p style={{ color: "#4b6358", marginTop: 0, marginBottom: "1rem" }}>
          Complete these foundational milestones to prepare your organization for third-party compliance audits.
        </p>

        <div style={{ display: "grid", gap: "0.85rem" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "1rem 1.25rem",
              border: "1px solid #cad8d1",
              borderRadius: "0.5rem",
              background: "#fff",
              flexWrap: "wrap",
              gap: "0.75rem",
            }}
          >
            <div>
              <div style={{ fontWeight: 700, color: "#10251f" }}>1. Adopt Canonical Compliance Framework</div>
              <div style={{ fontSize: "0.88rem", color: "#546e62" }}>
                Select official frameworks (ISO/IEC 27001, SOC 2, HIPAA) or define custom overlays.
              </div>
            </div>
            <button
              type="button"
              className="secondary"
              style={{ minHeight: "2.25rem", padding: "0.4rem 0.85rem", fontSize: "0.88rem" }}
              onClick={() => onNavigate("frameworks")}
            >
              View Catalog &rarr;
            </button>
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "1rem 1.25rem",
              border: "1px solid #cad8d1",
              borderRadius: "0.5rem",
              background: "#fff",
              flexWrap: "wrap",
              gap: "0.75rem",
            }}
          >
            <div>
              <div style={{ fontWeight: 700, color: "#10251f" }}>2. Implement Controls & Collect Evidence</div>
              <div style={{ fontSize: "0.88rem", color: "#546e62" }}>
                Upload evidence with AES-256-GCM envelope encryption and map controls to policies.
              </div>
            </div>
            <button
              type="button"
              className="secondary"
              style={{ minHeight: "2.25rem", padding: "0.4rem 0.85rem", fontSize: "0.88rem" }}
              onClick={() => onNavigate("compliance")}
            >
              Open Compliance &rarr;
            </button>
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "1rem 1.25rem",
              border: "1px solid #cad8d1",
              borderRadius: "0.5rem",
              background: "#fff",
              flexWrap: "wrap",
              gap: "0.75rem",
            }}
          >
            <div>
              <div style={{ fontWeight: 700, color: "#10251f" }}>3. Run Pre-Audit Readiness Check</div>
              <div style={{ fontSize: "0.88rem", color: "#546e62" }}>
                Execute deterministic scoring, generate SHA-256 audit manifests, and issue readiness credentials.
              </div>
            </div>
            <button
              type="button"
              className="secondary"
              style={{ minHeight: "2.25rem", padding: "0.4rem 0.85rem", fontSize: "0.88rem" }}
              onClick={() => onNavigate("preaudit")}
            >
              Start Pre-Audit &rarr;
            </button>
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "1rem 1.25rem",
              border: "1px solid #cad8d1",
              borderRadius: "0.5rem",
              background: "#fff",
              flexWrap: "wrap",
              gap: "0.75rem",
            }}
          >
            <div>
              <div style={{ fontWeight: 700, color: "#10251f" }}>4. Publish Public Trust Center</div>
              <div style={{ fontSize: "0.88rem", color: "#546e62" }}>
                Showcase security commitments, verified readiness credentials, and third-party certifications.
              </div>
            </div>
            <button
              type="button"
              className="secondary"
              style={{ minHeight: "2.25rem", padding: "0.4rem 0.85rem", fontSize: "0.88rem" }}
              onClick={() => onNavigate("public_profile")}
            >
              Trust Center &rarr;
            </button>
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "1rem 1.25rem",
              border: "1px solid #cad8d1",
              borderRadius: "0.5rem",
              background: "#fff",
              flexWrap: "wrap",
              gap: "0.75rem",
            }}
          >
            <div>
              <div style={{ fontWeight: 700, color: "#10251f" }}>5. Configure Anonymous Whistleblower Channel</div>
              <div style={{ fontSize: "0.88rem", color: "#546e62" }}>
                Provide confidential reporting protected by PBKDF2 hash tracking and zero IP logging.
              </div>
            </div>
            <button
              type="button"
              className="secondary"
              style={{ minHeight: "2.25rem", padding: "0.4rem 0.85rem", fontSize: "0.88rem" }}
              onClick={() => onNavigate("whistleblower")}
            >
              Whistleblower Portal &rarr;
            </button>
          </div>
        </div>
      </section>

      {/* Pilot Support & Operations Intake */}
      <section
        aria-labelledby="pilot-support-title"
        style={{
          border: "1px solid #cad8d1",
          borderRadius: "0.75rem",
          padding: "1.25rem",
          backgroundColor: "#fafdface",
          marginBottom: "1.5rem",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap" }}>
          <h3 id="pilot-support-title" style={{ margin: 0, fontSize: "1.2rem", color: "#10251f" }}>
            Pilot Service & Support Intake
          </h3>
          <span style={{ fontSize: "0.82rem", color: "#546e62" }}>
            24/7 Security Intake &bull; Business-Hours Operations (09:00 - 18:00 CET)
          </span>
        </div>

        <p style={{ fontSize: "0.9rem", color: "#4b6358", margin: "0.5rem 0 1rem 0" }}>
          During the paid pilot program, service targets represent operational response guidelines (not contractual SLAs). Contractual SLAs are phased in following six months of production telemetry.
        </p>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.88rem" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #cad8d1", textAlign: "left", color: "#147356" }}>
                <th style={{ padding: "0.5rem" }}>Severity Level</th>
                <th style={{ padding: "0.5rem" }}>Classification</th>
                <th style={{ padding: "0.5rem" }}>Response Objective</th>
                <th style={{ padding: "0.5rem" }}>Intake Channel</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: "1px solid #e1e9e4" }}>
                <td style={{ padding: "0.5rem", fontWeight: 700, color: "#a82020" }}>Critical (P1)</td>
                <td style={{ padding: "0.5rem" }}>Security incident, data exposure, total service outage</td>
                <td style={{ padding: "0.5rem", fontWeight: 700 }}>4 Hours (24/7 intake)</td>
                <td style={{ padding: "0.5rem" }}><code>security-intake@conformly.com</code></td>
              </tr>
              <tr style={{ borderBottom: "1px solid #e1e9e4" }}>
                <td style={{ padding: "0.5rem", fontWeight: 700, color: "#d97706" }}>High (P2)</td>
                <td style={{ padding: "0.5rem" }}>Core workflow degraded (evidence upload, pre-audit)</td>
                <td style={{ padding: "0.5rem" }}>1 Business Day</td>
                <td style={{ padding: "0.5rem" }}><code>support@conformly.com</code></td>
              </tr>
              <tr style={{ borderBottom: "1px solid #e1e9e4" }}>
                <td style={{ padding: "0.5rem", fontWeight: 700, color: "#2563eb" }}>Medium (P3)</td>
                <td style={{ padding: "0.5rem" }}>Non-critical feature issue, UI defect</td>
                <td style={{ padding: "0.5rem" }}>2 Business Days</td>
                <td style={{ padding: "0.5rem" }}><code>support@conformly.com</code></td>
              </tr>
              <tr>
                <td style={{ padding: "0.5rem", fontWeight: 700, color: "#4b6358" }}>Low (P4)</td>
                <td style={{ padding: "0.5rem" }}>General inquiry, onboarding advisory</td>
                <td style={{ padding: "0.5rem" }}>3 Business Days</td>
                <td style={{ padding: "0.5rem" }}><code>support@conformly.com</code></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Security Invariants & Isolation */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(14rem, 1fr))",
          gap: "1rem",
          fontSize: "0.85rem",
          color: "#546e62",
        }}
      >
        <div style={{ padding: "0.75rem 1rem", border: "1px solid #cad8d1", borderRadius: "0.5rem", background: "#f8fbf9" }}>
          <strong style={{ color: "#10251f" }}>Row-Level Security (RLS)</strong>
          <p style={{ margin: "0.25rem 0 0 0" }}>Strict kernel-enforced tenant boundaries on every SQL query.</p>
        </div>
        <div style={{ padding: "0.75rem 1rem", border: "1px solid #cad8d1", borderRadius: "0.5rem", background: "#f8fbf9" }}>
          <strong style={{ color: "#10251f" }}>AES-256-GCM Envelope Encryption</strong>
          <p style={{ margin: "0.25rem 0 0 0" }}>Unique DEK per file; zero unencrypted evidence at rest.</p>
        </div>
        <div style={{ padding: "0.75rem 1rem", border: "1px solid #cad8d1", borderRadius: "0.5rem", background: "#f8fbf9" }}>
          <strong style={{ color: "#10251f" }}>Anonymous Whistleblower Flow</strong>
          <p style={{ margin: "0.25rem 0 0 0" }}>PBKDF2 return keys with zero IP address or telemetry logging.</p>
        </div>
        <div style={{ padding: "0.75rem 1rem", border: "1px solid #cad8d1", borderRadius: "0.5rem", background: "#f8fbf9" }}>
          <strong style={{ color: "#10251f" }}>Auditable Data Exit</strong>
          <p style={{ margin: "0.25rem 0 0 0" }}>30-day export window, 90-day multi-table cryptographic deletion proof.</p>
        </div>
      </div>
    </div>
  );
}
