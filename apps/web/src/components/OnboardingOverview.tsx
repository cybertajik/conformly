import type { TenantRole } from "@conformly/shared";
import { useEffect, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";

export type Tab =
  | "overview"
  | "onboarding"
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

const STORAGE_PREFIX = "conformly.onboarding_progress.";

export function OnboardingOverview({
  tenantName,
  tenantSlug,
  userRole,
  onNavigate,
}: OnboardingOverviewProps) {
  const { t } = useTranslation();
  const formattedRole = userRole.replaceAll("_", " ");

  const storageKey = `${STORAGE_PREFIX}${tenantSlug || tenantName}`;

  // Saved progress state: step -> boolean
  const [completedSteps, setCompletedSteps] = useState<Record<number, boolean>>(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        return JSON.parse(saved) as Record<number, boolean>;
      }
    } catch {
      // Ignore parse/storage errors
    }
    return {};
  });

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(completedSteps));
    } catch {
      // Ignore storage write errors
    }
  }, [completedSteps, storageKey]);

  const toggleStep = (step: number) => {
    setCompletedSteps((prev) => ({
      ...prev,
      [step]: !prev[step],
    }));
  };

  const resetProgress = () => {
    setCompletedSteps({});
    try {
      localStorage.removeItem(storageKey);
    } catch {
      // Ignore storage error
    }
  };

  const checklistItems = [
    {
      step: 1,
      title: t("onboarding.step1Title"),
      desc: t("onboarding.step1Desc"),
      tab: "frameworks" as Tab,
      btnLabel: t("onboarding.step1Btn"),
      icon: "M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10",
    },
    {
      step: 2,
      title: t("onboarding.step2Title"),
      desc: t("onboarding.step2Desc"),
      tab: "compliance" as Tab,
      btnLabel: t("onboarding.step2Btn"),
      icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
    },
    {
      step: 3,
      title: t("onboarding.step3Title"),
      desc: t("onboarding.step3Desc"),
      tab: "preaudit" as Tab,
      btnLabel: t("onboarding.step3Btn"),
      icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4",
    },
    {
      step: 4,
      title: t("onboarding.step4Title"),
      desc: t("onboarding.step4Desc"),
      tab: "public_profile" as Tab,
      btnLabel: t("onboarding.step4Btn"),
      icon: "M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064",
    },
    {
      step: 5,
      title: t("onboarding.step5Title"),
      desc: t("onboarding.step5Desc"),
      tab: "whistleblower" as Tab,
      btnLabel: t("onboarding.step5Btn"),
      icon: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z",
    },
  ];

  const totalSteps = checklistItems.length;
  const completedCount = checklistItems.filter((i) => completedSteps[i.step]).length;
  const progressPercent = Math.round((completedCount / totalSteps) * 100);
  const isAllComplete = completedCount === totalSteps;

  const securityFeatures = [
    {
      title: t("onboarding.securityRlsTitle"),
      desc: t("onboarding.securityRlsDesc"),
      color: "var(--color-success)",
    },
    {
      title: t("onboarding.securityAesTitle"),
      desc: t("onboarding.securityAesDesc"),
      color: "var(--color-info)",
    },
    {
      title: t("onboarding.securityWhistleTitle"),
      desc: t("onboarding.securityWhistleDesc"),
      color: "var(--color-warning)",
    },
    {
      title: t("onboarding.securityExitTitle"),
      desc: t("onboarding.securityExitDesc"),
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
            <span className="eyebrow">{t("onboarding.eyebrow")}</span>
            <h2 style={{ margin: "0.5rem 0", fontSize: "1.625rem" }}>{tenantName}</h2>
            <p style={{ margin: 0, fontSize: "0.875rem" }}>
              {t("onboarding.orgSlug")}: <code>{tenantSlug}</code> &bull; {t("onboarding.role")}:{" "}
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
              {t("onboarding.pilotOperational")}
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
          <strong style={{ fontSize: "0.875rem", flexShrink: 0 }}>⚠ {t("disclaimer.badge")}:</strong>
          <p style={{ margin: 0, fontSize: "0.8125rem", lineHeight: "1.5", color: "var(--text-secondary)" }}>
            <strong style={{ color: "#fbbf24" }}>{t("disclaimer.title")}</strong>{" "}
            {t("disclaimer.text")}
          </p>
        </div>
      </div>

      {/* Readiness Onboarding Checklist */}
      <section aria-labelledby="readiness-checklist-title" style={{ marginBottom: "2.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: "1rem", marginBottom: "0.75rem" }}>
          <div>
            <h3 id="readiness-checklist-title" style={{ fontSize: "1.25rem", marginBottom: "0.35rem" }}>
              {t("onboarding.title")}
            </h3>
            <p style={{ marginTop: 0, marginBottom: 0, fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              {t("onboarding.subtitle")}
            </p>
          </div>
          {completedCount > 0 && (
            <button
              type="button"
              className="ghost"
              style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem", color: "var(--text-muted)" }}
              onClick={resetProgress}
            >
              {t("onboarding.resetProgress")}
            </button>
          )}
        </div>

        {/* Saved Progress Bar */}
        <div
          className="card"
          style={{
            padding: "1rem 1.25rem",
            marginBottom: "1.25rem",
            background: "var(--bg-card)",
            border: "1px solid var(--border-default)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
            <span style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)" }}>
              {t("onboarding.stepsCompleted", {
                completed: completedCount,
                total: totalSteps,
                percent: progressPercent,
              })}
            </span>
            <span
              style={{
                fontSize: "0.8rem",
                fontWeight: 700,
                color: isAllComplete ? "var(--color-success)" : "var(--accent)",
              }}
            >
              {progressPercent}%
            </span>
          </div>
          <div
            role="progressbar"
            aria-valuenow={progressPercent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={t("onboarding.progressBarLabel")}
            style={{
              width: "100%",
              height: "8px",
              background: "rgba(255, 255, 255, 0.08)",
              borderRadius: "var(--radius-full)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${progressPercent}%`,
                height: "100%",
                background: isAllComplete
                  ? "linear-gradient(90deg, #10b981, #059669)"
                  : "linear-gradient(90deg, #10b981, #3b82f6)",
                borderRadius: "var(--radius-full)",
                transition: "width 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
              }}
            />
          </div>
        </div>

        {/* Celebration Banner when all milestones are finished */}
        {isAllComplete && (
          <div
            className="card"
            style={{
              background: "rgba(16, 185, 129, 0.1)",
              border: "1px solid rgba(16, 185, 129, 0.35)",
              padding: "1.25rem",
              marginBottom: "1.25rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "1rem",
            }}
          >
            <div>
              <div style={{ fontWeight: 700, fontSize: "1rem", color: "var(--color-success)" }}>
                {t("onboarding.allMilestonesComplete")}
              </div>
              <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                {t("onboarding.allMilestonesCompleteSub")}
              </div>
            </div>
            <button
              type="button"
              className="primary"
              style={{ padding: "0.45rem 1rem", fontSize: "0.85rem" }}
              onClick={() => onNavigate("preaudit")}
            >
              {t("onboarding.step3Btn")} →
            </button>
          </div>
        )}

        {/* Checklist Milestones */}
        <div style={{ display: "grid", gap: "0.75rem" }}>
          {checklistItems.map((item) => {
            const isCompleted = !!completedSteps[item.step];
            return (
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
                  borderLeft: isCompleted
                    ? "3px solid var(--color-success)"
                    : "3px solid var(--border-default)",
                  background: isCompleted
                    ? "rgba(16, 185, 129, 0.03)"
                    : "var(--bg-card)",
                }}
              >
                <div style={{ display: "flex", gap: "1rem", alignItems: "flex-start", flex: 1, minWidth: 0 }}>
                  <button
                    type="button"
                    onClick={() => toggleStep(item.step)}
                    aria-label={
                      isCompleted
                        ? `${item.title} - ${t("onboarding.markIncomplete")}`
                        : `${item.title} - ${t("onboarding.markCompleted")}`
                    }
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: "var(--radius-sm)",
                      border: isCompleted
                        ? "1px solid var(--color-success)"
                        : "1px solid var(--border-default)",
                      background: isCompleted ? "var(--color-success)" : "var(--bg-elevated)",
                      color: isCompleted ? "#0b0f14" : "transparent",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      cursor: "pointer",
                      padding: 0,
                      flexShrink: 0,
                      marginTop: "0.2rem",
                      transition: "var(--transition-fast)",
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  </button>

                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: "var(--radius-md)",
                      background: isCompleted ? "var(--color-success-bg)" : "var(--accent-subtle)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <svg
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke={isCompleted ? "var(--color-success)" : "var(--accent)"}
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d={item.icon} />
                    </svg>
                  </div>

                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                      <span style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "0.9rem" }}>
                        {item.step}. {item.title}
                      </span>
                      {isCompleted ? (
                        <span
                          style={{
                            fontSize: "0.72rem",
                            fontWeight: 700,
                            padding: "0.15rem 0.5rem",
                            borderRadius: "var(--radius-full)",
                            background: "var(--color-success-bg)",
                            color: "var(--color-success)",
                            border: "1px solid rgba(16, 185, 129, 0.2)",
                          }}
                        >
                          ✓ {t("common.completed")}
                        </span>
                      ) : (
                        <span
                          style={{
                            fontSize: "0.72rem",
                            fontWeight: 600,
                            padding: "0.15rem 0.5rem",
                            borderRadius: "var(--radius-full)",
                            background: "rgba(148, 163, 184, 0.08)",
                            color: "var(--text-muted)",
                          }}
                        >
                          {t("common.pending")}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                      {item.desc}
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <button
                    type="button"
                    className="secondary"
                    style={{ minHeight: "2rem", padding: "0.35rem 0.85rem", fontSize: "0.8125rem" }}
                    onClick={() => onNavigate(item.tab)}
                  >
                    {item.btnLabel} →
                  </button>
                </div>
              </div>
            );
          })}
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
            {t("onboarding.supportTitle")}
          </h3>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            {t("onboarding.supportSubtitle")}
          </span>
        </div>

        <p style={{ fontSize: "0.8125rem", margin: "0 0 1.25rem 0", color: "var(--text-secondary)" }}>
          {t("onboarding.supportNotice")}
        </p>

        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("onboarding.thSeverity")}</th>
                <th>{t("onboarding.thClassification")}</th>
                <th>{t("onboarding.thResponse")}</th>
                <th>{t("onboarding.thChannel")}</th>
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
