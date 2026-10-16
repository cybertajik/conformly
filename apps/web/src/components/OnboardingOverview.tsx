import type { TenantRole } from "@conformly/shared";
import { useEffect, useState } from "react";
import { ArrowUpRight, Check, CircleCheck, LifeBuoy, ShieldCheck } from "lucide-react";
import { canReadFrameworks, canReadEvidence, canReadPolicies, canReadPreAudit } from "../permissions";
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
    },
    {
      step: 2,
      title: t("onboarding.step2Title"),
      desc: t("onboarding.step2Desc"),
      tab: "compliance" as Tab,
      btnLabel: t("onboarding.step2Btn"),
    },
    {
      step: 3,
      title: t("onboarding.step3Title"),
      desc: t("onboarding.step3Desc"),
      tab: "preaudit" as Tab,
      btnLabel: t("onboarding.step3Btn"),
    },
    {
      step: 4,
      title: t("onboarding.step4Title"),
      desc: t("onboarding.step4Desc"),
      tab: "public_profile" as Tab,
      btnLabel: t("onboarding.step4Btn"),
    },
    {
      step: 5,
      title: t("onboarding.step5Title"),
      desc: t("onboarding.step5Desc"),
      tab: "whistleblower" as Tab,
      btnLabel: t("onboarding.step5Btn"),
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

  return <div className="onboarding-overview">
    <header className="page-heading"><div><p className="eyebrow">{t("onboarding.eyebrow")}</p><h1>{tenantName}</h1><p>{t("onboarding.orgSlug")}: <code>{tenantSlug}</code> · {t("onboarding.role")}: {formattedRole}</p></div><span className="badge badge-success"><CircleCheck size={13}/>{t("onboarding.pilotOperational")}</span></header>
    <div className="setup-grid">
      <section aria-labelledby="readiness-checklist-title"><div className="section-heading"><div><h2 id="readiness-checklist-title">{t("onboarding.title")}</h2><p>{t("onboarding.subtitle")}</p></div></div><div className="surface setup-list">{checklistItems.map(item => {
        const completed = Boolean(completedSteps[item.step]);
        const accessible = item.tab === "frameworks" ? canReadFrameworks(userRole) : item.tab === "compliance" ? canReadEvidence(userRole) || canReadPolicies(userRole) : item.tab === "preaudit" ? canReadPreAudit(userRole) : item.tab === "public_profile";
        return <article className="setup-step" key={item.step}><button className={`step-toggle ${completed ? "complete" : ""}`} aria-pressed={completed} aria-label={`${item.title} - ${t(completed ? "onboarding.markIncomplete" : "onboarding.markCompleted")}`} onClick={() => toggleStep(item.step)}>{completed ? <Check size={16}/> : String(item.step).padStart(2,"0")}</button><div><h3>{item.title}</h3><p>{item.desc}</p><button className="text-button" disabled={!accessible} onClick={() => onNavigate(item.tab)}>{item.btnLabel}<ArrowUpRight size={14}/></button></div></article>;
      })}</div></section>
      <aside><section className="surface setup-progress"><p className="eyebrow">{t("onboarding.progressBarLabel")}</p><strong>{progressPercent}%</strong><progress aria-label={t("onboarding.progressBarLabel")} value={progressPercent} max={100} aria-valuenow={progressPercent} aria-valuemin={0} aria-valuemax={100}/><p>{t("onboarding.stepsCompleted", { completed: completedCount, total: totalSteps, percent: progressPercent })}</p>{completedCount > 0 && <button className="ghost" onClick={resetProgress}>{t("onboarding.resetProgress")}</button>}{isAllComplete && <div className="success-banner">{t("onboarding.allMilestonesComplete")}</div>}</section><section className="surface setup-note" aria-label="Compliance disclaimer"><ShieldCheck size={24}/><h3>{t("disclaimer.title")}</h3><p>{t("disclaimer.text")}</p></section></aside>
    </div>
    <section aria-labelledby="pilot-support-title" className="surface"><div className="section-heading"><div><h2 id="pilot-support-title">{t("onboarding.supportTitle")}</h2><p>{t("onboarding.supportSubtitle")}</p></div><LifeBuoy size={21}/></div><p className="card-subtitle">{t("onboarding.supportNotice")}</p><div className="table-wrapper"><table className="data-table"><thead><tr><th>{t("onboarding.thSeverity")}</th><th>{t("onboarding.thClassification")}</th><th>{t("onboarding.thResponse")}</th><th>{t("onboarding.thChannel")}</th></tr></thead><tbody>{supportTiers.map(tier => <tr key={tier.severity}><td><strong style={{ color: tier.color }}>{tier.severity}</strong></td><td>{tier.classification}</td><td><strong>{tier.response}</strong></td><td><a href={"mailto:" + tier.channel}>{tier.channel}</a></td></tr>)}</tbody></table></div></section>
    <div className="security-principles">{securityFeatures.map(feature => <article className="surface" key={feature.title}><strong>{feature.title}</strong><p>{feature.desc}</p></article>)}</div>
  </div>;
}
