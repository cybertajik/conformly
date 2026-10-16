import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import type { ContinuousComplianceResult, DashboardSummary, TenantRole } from "@conformly/shared";
import { ArrowRight, ArrowUpRight, Check, CheckCheck, CircleCheck, Clock3, FileCheck2, Flag, Layers3, ListTodo, RefreshCw, ShieldCheck, Users } from "lucide-react";
import { getDashboardSummary, runContinuousComplianceCycle } from "../api";
import { canReadPreAudit, canReadFrameworks, canReadEvidence, canReadPolicies, canReadRisks, canReadVendors } from "../permissions";
import { useTranslation } from "../i18n/I18nContext";

export interface ExecutiveDashboardProps {
  token: string;
  tenantId: string;
  tenantName: string;
  tenantSlug: string;
  userRole: TenantRole;
  onNavigate: (tab: string) => void;
}

type View = "readiness" | "expiring" | "tasks" | "registers" | "activity";

const translatePriority = (priority: string, t: (key: string) => string) => {
  const key = priority.toLowerCase();
  const map: Record<string, string> = {
    critical: t("dashboard.priorityCritical"),
    high: t("dashboard.priorityHigh"),
    medium: t("dashboard.priorityMedium"),
    low: t("dashboard.priorityLow"),
  };
  return map[key] ?? t("dashboard.priorityMedium");
};

const translateTaskStatus = (status: string, t: (key: string) => string) => {
  const key = status.toLowerCase();
  const map: Record<string, string> = {
    pending: t("dashboard.statusPending"),
    in_progress: t("dashboard.statusInProgress"),
    completed: t("dashboard.statusCompleted"),
    overdue: t("dashboard.statusOverdue"),
    cancelled: t("dashboard.statusCancelled"),
    closed: t("dashboard.statusClosed"),
  };
  return map[key] ?? t("dashboard.statusPending");
};

const translateRiskStatus = (status: string, t: (key: string) => string) => {
  const key = status.toLowerCase();
  const map: Record<string, string> = {
    identified: t("dashboard.riskIdentified"),
    assessed: t("dashboard.riskAssessed"),
    treating: t("dashboard.riskTreating"),
    treated: t("dashboard.riskTreated"),
    monitored: t("dashboard.riskMonitored"),
    closed: t("dashboard.riskClosed"),
    accepted: t("dashboard.riskAccepted"),
    mitigated: t("dashboard.riskMitigated"),
  };
  return map[key] ?? t("dashboard.riskIdentified");
};

const getResourceMap = (t: (key: string) => string): Record<string, string> => ({
  compliance_task: t("dashboard.resourceComplianceTask"),
  task: t("dashboard.resourceTask"),
  evidence_item: t("dashboard.resourceEvidenceItem"),
  evidence: t("dashboard.resourceEvidence"),
  evidence_file_link: t("dashboard.resourceEvidenceFileLink"),
  evidence_control_link: t("dashboard.resourceEvidenceControlLink"),
  policy_control_link: t("dashboard.resourcePolicyControlLink"),
  policy_template: t("dashboard.resourcePolicyTemplate"),
  policy_acknowledgement: t("dashboard.resourcePolicyAcknowledgement"),
  policy: t("dashboard.resourcePolicy"),
  risk_treatment: t("dashboard.resourceRiskTreatment"),
  risk: t("dashboard.resourceRisk"),
  vendor: t("dashboard.resourceVendor"),
  asset: t("dashboard.resourceAsset"),
  finding: t("dashboard.resourceFinding"),
  control_status_record: t("dashboard.resourceControlStatus"),
  control_status: t("dashboard.resourceControlStatus"),
  control: t("dashboard.resourceControl"),
  canonical_control: t("dashboard.resourceControl"),
  custom_control: t("dashboard.resourceControl"),
  whistleblower_case: t("dashboard.resourceWhistleblowerCase"),
  whistleblower_portal: t("dashboard.resourceWhistleblower"),
  whistleblower_message: t("dashboard.resourceWhistleblower"),
  whistleblower: t("dashboard.resourceWhistleblower"),
  preaudit: t("dashboard.resourcePreaudit"),
  pre_audit: t("dashboard.resourcePreaudit"),
  pre_audit_certificate: t("dashboard.resourcePreaudit"),
  pre_audit_finding: t("dashboard.resourceFinding"),
  pre_audit_report: t("dashboard.resourcePreaudit"),
  pre_audit_manifest: t("dashboard.resourcePreaudit"),
  dashboard: t("dashboard.resourceDashboard"),
  file: t("dashboard.resourceFile"),
  stored_file: t("dashboard.resourceFile"),
  user: t("dashboard.resourceUser"),
  member: t("dashboard.resourceMember"),
  membership: t("dashboard.resourceMember"),
  membership_invitation: t("dashboard.resourceMember"),
  tenant_membership: t("dashboard.resourceMember"),
  tenant: t("dashboard.resourceTenant"),
  framework: t("dashboard.resourceFramework"),
  framework_version: t("dashboard.resourceFramework"),
  framework_adoption: t("dashboard.resourceFramework"),
  tenant_framework_adoption: t("dashboard.resourceFramework"),
  organization: t("dashboard.resourceOrganization"),
  business_unit: t("dashboard.resourceBusinessUnit"),
  legal_entity: t("dashboard.resourceLegalEntity"),
  location: t("dashboard.resourceLocation"),
  audit: t("dashboard.resourceAudit"),
  audit_event: t("dashboard.resourceAudit"),
  credential: t("dashboard.resourceCredential"),
  public_credential: t("dashboard.resourceCredential"),
  public_profile: t("dashboard.resourcePublicProfile"),
  export: t("dashboard.resourceExport"),
  export_job: t("dashboard.resourceExport"),
  notification: t("dashboard.resourceNotification"),
  notification_outbox: t("dashboard.resourceNotification"),
  training: t("dashboard.resourceTraining"),
  training_assignment: t("dashboard.resourceTraining"),
  training_completion: t("dashboard.resourceTraining"),
  webhook: t("dashboard.resourceWebhook"),
  webhook_subscription: t("dashboard.resourceWebhook"),
  preference: t("dashboard.resourcePreferences"),
  preferences: t("dashboard.resourcePreferences"),
  user_notification_preference: t("dashboard.resourcePreferences"),
  auth: t("dashboard.resourceAuth"),
  session: t("dashboard.resourceSession"),
  auth_session: t("dashboard.resourceSession"),
});

const getVerbMap = (t: (key: string) => string): Record<string, string> => ({
  create: t("dashboard.verbCreate"),
  created: t("dashboard.verbCreate"),
  update: t("dashboard.verbUpdate"),
  updated: t("dashboard.verbUpdate"),
  delete: t("dashboard.verbDelete"),
  deleted: t("dashboard.verbDelete"),
  upload: t("dashboard.verbUpload"),
  uploaded: t("dashboard.verbUpload"),
  transition_status: t("dashboard.verbTransitionStatus"),
  complete: t("dashboard.verbComplete"),
  completed: t("dashboard.verbComplete"),
  approve: t("dashboard.verbApprove"),
  approved: t("dashboard.verbApprove"),
  review: t("dashboard.verbReview"),
  reviewed: t("dashboard.verbReview"),
  publish: t("dashboard.verbPublish"),
  published: t("dashboard.verbPublish"),
  archive: t("dashboard.verbArchive"),
  archived: t("dashboard.verbArchive"),
  acknowledge: t("dashboard.verbAcknowledge"),
  acknowledged: t("dashboard.verbAcknowledge"),
  adopt: t("dashboard.verbAdopt"),
  adopted: t("dashboard.verbAdopt"),
  invite: t("dashboard.verbInvite"),
  invited: t("dashboard.verbInvite"),
  revoke: t("dashboard.verbRevoke"),
  revoked: t("dashboard.verbRevoke"),
  accept: t("dashboard.verbAccept"),
  accepted: t("dashboard.verbAccept"),
  invitation_accept: t("dashboard.verbAccept"),
  role_change: t("dashboard.verbUpdate"),
  scopes_update: t("dashboard.verbUpdate"),
  assign: t("dashboard.verbAssign"),
  assigned: t("dashboard.verbAssign"),
  send: t("dashboard.verbSend"),
  sent: t("dashboard.verbSend"),
  export: t("dashboard.verbExport"),
  exported: t("dashboard.verbExport"),
  download: t("dashboard.verbDownload"),
  downloaded: t("dashboard.verbDownload"),
  cancel: t("dashboard.verbCancel"),
  cancelled: t("dashboard.verbCancel"),
  execute: t("dashboard.verbExecute"),
  executed: t("dashboard.verbExecute"),
  run_checks: t("dashboard.verbExecute"),
  assess: t("dashboard.verbAssess"),
  assessed: t("dashboard.verbAssess"),
  configure: t("dashboard.verbConfigure"),
  configured: t("dashboard.verbConfigure"),
  issue: t("dashboard.verbIssue"),
  issued: t("dashboard.verbIssue"),
  suspend: t("dashboard.verbSuspend"),
  suspended: t("dashboard.verbSuspend"),
  reinstate: t("dashboard.verbReinstate"),
  reinstated: t("dashboard.verbReinstate"),
  list: t("dashboard.verbReview"),
});

const translateResourceType = (resourceType: string, t: (key: string) => string) => {
  if (!resourceType) return t("dashboard.genericResource");
  const key = resourceType.toLowerCase().replace(/[-_]/g, "_");
  const map = getResourceMap(t);
  return map[key] ?? t("dashboard.genericResource");
};

const translateActivityAction = (action: string, t: (key: string) => string) => {
  if (!action) return t("dashboard.genericActivity");
  const key = action.toLowerCase().replace(/[-_]/g, "_");
  const map: Record<string, string> = {
    "evidence.create": t("dashboard.actionEvidenceCreate"),
    "evidence.update": t("dashboard.actionEvidenceUpdate"),
    "evidence.transition_status": t("dashboard.actionEvidenceTransitionStatus"),
    "evidence.status_updated": t("dashboard.actionEvidenceTransitionStatus"),
    "evidence.upload": t("dashboard.actionEvidenceUpload"),
    "evidence.uploaded": t("dashboard.actionEvidenceUpload"),
    "evidence.attach_file": t("dashboard.actionEvidenceAttachFile"),
    "evidence.remove_file": t("dashboard.actionEvidenceRemoveFile"),
    "evidence.link_control": t("dashboard.actionEvidenceLinkControl"),
    "evidence.unlink_control": t("dashboard.actionEvidenceUnlinkControl"),
    "evidence.legal_hold.set": t("dashboard.actionEvidenceLegalHoldSet"),
    "evidence.legal_hold.released": t("dashboard.actionEvidenceLegalHoldReleased"),
    "task.create": t("dashboard.actionTaskCreate"),
    "task.update": t("dashboard.actionTaskUpdate"),
    "task.complete": t("dashboard.actionTaskComplete"),
    "task.overdue": t("dashboard.actionTaskOverdue"),
    "policy.create": t("dashboard.actionPolicyCreate"),
    "policy.update": t("dashboard.actionPolicyUpdate"),
    "policy.submit_review": t("dashboard.actionPolicyReview"),
    "policy.approve": t("dashboard.actionPolicyApprove"),
    "policy.publish": t("dashboard.actionPolicyPublish"),
    "policy.archive": t("dashboard.actionPolicyArchive"),
    "policy.acknowledge": t("dashboard.actionPolicyAcknowledge"),
    "policy.link_control": t("dashboard.actionEvidenceLinkControl"),
    "policy.unlink_control": t("dashboard.actionEvidenceUnlinkControl"),
    "risk.create": t("dashboard.actionRiskCreate"),
    "risk.update": t("dashboard.actionRiskUpdate"),
    "risk.delete": t("dashboard.actionRiskDelete"),
    "risk.review.complete": t("dashboard.actionRiskReviewComplete"),
    "risk.treatment.create": t("dashboard.actionRiskTreatmentCreate"),
    "risk.treatment.update": t("dashboard.actionRiskTreatmentUpdate"),
    "vendor.create": t("dashboard.actionVendorCreate"),
    "vendor.update": t("dashboard.actionVendorUpdate"),
    "vendor.delete": t("dashboard.actionVendorDelete"),
    "vendor.review.complete": t("dashboard.actionVendorReviewComplete"),
    "asset.create": t("dashboard.actionAssetCreate"),
    "asset.update": t("dashboard.actionAssetUpdate"),
    "asset.delete": t("dashboard.actionAssetDelete"),
    "finding.create": t("dashboard.actionFindingCreate"),
    "finding.update": t("dashboard.actionFindingUpdate"),
    "preaudit.create": t("dashboard.actionPreauditCreate"),
    "preaudit.run_checks": t("dashboard.actionPreauditRunChecks"),
    "preaudit.submit_review": t("dashboard.actionPreauditSubmitReview"),
    "preaudit.complete_review": t("dashboard.actionPreauditCompleteReview"),
    "preaudit.tenant_approved": t("dashboard.actionPreauditTenantApproved"),
    "framework.adopted": t("dashboard.actionFrameworkAdopted"),
    "compliance.continuous_cycle_executed": t("dashboard.actionComplianceCycleExecuted"),
    "dashboard.summary_viewed": t("dashboard.actionDashboardSummaryViewed"),
    "file.uploaded": t("dashboard.actionFileUploaded"),
    "file.downloaded": t("dashboard.actionFileDownloaded"),
    "file.deleted": t("dashboard.actionFileDeleted"),
    "whistleblower.case_submitted": t("dashboard.actionWhistleblowerSubmitted"),
    "membership.invite": t("dashboard.actionMembershipInvite"),
    "membership.revoke": t("dashboard.actionMembershipRevoke"),
    "membership.role_change": t("dashboard.actionMembershipRoleChange"),
    "membership.invitation_accept": t("dashboard.actionMembershipAccept"),
  };
  if (map[key]) return map[key];

  const resourceMap = getResourceMap(t);
  const verbMap = getVerbMap(t);

  const parts = key.split(".");
  if (parts.length >= 2) {
    const resPart = parts[0];
    const verbPart = parts.slice(1).join("_");
    const lastVerb = parts[parts.length - 1];

    const translatedRes = resourceMap[resPart];
    const translatedVerb = verbMap[verbPart] ?? verbMap[lastVerb];

    if (translatedRes && translatedVerb) {
      return `${translatedRes} · ${translatedVerb}`;
    }
    if (translatedRes) {
      return `${translatedRes} · ${t("dashboard.genericAction")}`;
    }
    if (translatedVerb) {
      return `${t("dashboard.genericResource")} · ${translatedVerb}`;
    }
  } else if (resourceMap[key]) {
    return `${resourceMap[key]} · ${t("dashboard.genericAction")}`;
  }

  return t("dashboard.genericActivity");
};

const formatDate = (value?: string | null, locale = "en", noDueDateLabel = "No due date") => {
  if (!value) return noDueDateLabel;
  try {
    return new Date(value).toLocaleDateString(locale, { month: "short", day: "numeric" });
  } catch {
    return new Date(value).toLocaleDateString("en", { month: "short", day: "numeric" });
  }
};

export function ExecutiveDashboard({ token, tenantId, tenantName, userRole, onNavigate }: ExecutiveDashboardProps) {
  const { t, locale } = useTranslation();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState("");
  const [view, setView] = useState<View>("readiness");
  const [retry, setRetry] = useState(0);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ContinuousComplianceResult | null>(null);

  useEffect(() => {
    let active = true;
    getDashboardSummary(token, tenantId)
      .then(data => {
        if (active) {
          setSummary(data);
          setError("");
        }
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Unable to load your workspace.");
      });
    return () => {
      active = false;
    };
  }, [token, tenantId, retry]);

  async function runCycle() {
    setRunning(true);
    try {
      setResult(await runContinuousComplianceCycle(token, tenantId));
      setSummary(await getDashboardSummary(token, tenantId));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Check failed. Please try again.");
    } finally {
      setRunning(false);
    }
  }

  const date = (value?: string | null) => formatDate(value, locale, t("dashboard.noDueDate"));

  if (!summary && !error) {
    return (
      <div className="dashboard-page" role="status">
        <div className="skeleton skeleton-title" />
        <p>{t("dashboard.loadingPosture")}</p>
        <div className="skeleton skeleton-hero" />
        <div className="metric-grid">
          {[1, 2, 3, 4].map(n => (
            <div key={n} className="skeleton skeleton-metric" />
          ))}
        </div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="dashboard-page">
        <div className="error-banner" role="alert">{error}</div>
        <button className="primary" onClick={() => setRetry(n => n + 1)}>{t("dashboard.retry")}</button>
      </div>
    );
  }

  const admin = summary.is_administrator_view;
  const metrics = summary.admin_metrics;
  const score = Math.max(0, Math.min(100, Math.round(summary.readiness_score)));
  const deadlines = [
    ...summary.expiring_evidence.map(item => ({ ...item, kind: t("dashboard.kindEvidence"), due: item.expires_at })),
    ...summary.review_due_policies.map(item => ({ ...item, kind: t("dashboard.kindPolicy"), due: item.review_due_at })),
  ].sort((a, b) => a.days_remaining - b.days_remaining);
  const controls = summary.controls_summary;
  const tabs: { id: View; label: string; count?: number }[] = [
    { id: "readiness", label: t("dashboard.tabOverview") },
    { id: "expiring", label: t("dashboard.tabExpiring"), count: deadlines.length },
    { id: "tasks", label: t("dashboard.tabTasks"), count: summary.open_tasks.length },
    { id: "registers", label: t("dashboard.tabRegisters") },
    { id: "activity", label: t("dashboard.tabActivity") },
  ];

  const allowed = (page: string) => ({
    preaudit: canReadPreAudit(userRole),
    frameworks: canReadFrameworks(userRole),
    compliance: canReadEvidence(userRole) || canReadPolicies(userRole),
    risks: canReadRisks(userRole),
    vendors: canReadVendors(userRole),
  })[page] ?? false;

  const link = (page: string, label: string) =>
    allowed(page) ? (
      <button className="text-button" onClick={() => onNavigate(page)}>
        {label}<ArrowUpRight size={15} />
      </button>
    ) : null;

  const programPanel = (
    <section className="surface">
      <div className="section-heading">
        <div>
          <h2>{t("dashboard.programsTitle")}</h2>
          <p>{t("dashboard.programsSubtitle")}</p>
        </div>
        {link("frameworks", t("dashboard.viewAll"))}
      </div>
      {summary.frameworks_adopted.length ? (
        <div className="program-list">
          {summary.frameworks_adopted.map((framework, index) => (
            <div className="program-row" key={framework.framework_id}>
              <span className={"program-icon tone-" + (index % 3)}><ShieldCheck size={22} /></span>
              <div className="program-details">
                <h3>{framework.framework_name}</h3>
                <span>{t("dashboard.frameworkProgress", { implemented: framework.implemented_controls, total: framework.total_controls })}</span>
                <progress aria-label={t("dashboard.frameworkProgressAria", { name: framework.framework_name })} max={100} value={framework.progress_percentage} />
              </div>
              <strong>{Math.round(framework.progress_percentage)}<small>%</small></strong>
            </div>
          ))}
        </div>
      ) : (
        <Empty title={t("dashboard.emptyFrameworkTitle")} detail={t("dashboard.emptyFrameworkDetail")} />
      )}
    </section>
  );

  const reviewPanel = (
    <section className="surface">
      <div className="section-heading">
        <div>
          <h2>{view === "readiness" ? t("dashboard.nextUp") : t("dashboard.upcomingReviewsTitle")}</h2>
          <p>{t("dashboard.nearestDeadlines")}</p>
        </div>
        {view === "readiness" ? (
          <button className="text-button" onClick={() => setView("expiring")}>
            {t("dashboard.viewAll")}<ArrowUpRight size={15} />
          </button>
        ) : (
          link("compliance", t("dashboard.openCompliance"))
        )}
      </div>
      {deadlines.length ? (
        deadlines.slice(0, view === "readiness" ? 3 : undefined).map(item => (
          <div className="deadline-row" key={item.id}>
            <span className="deadline-icon"><Clock3 size={19} /></span>
            <div>
              <strong>{item.title}</strong>
              <small>{item.kind} · {date(item.due)}</small>
            </div>
            <span className={"badge " + (item.days_remaining < 7 ? "badge-warning" : "badge-neutral")}>
              {t("dashboard.daysRemaining", { count: item.days_remaining })}
            </span>
          </div>
        ))
      ) : (
        <Empty title={t("dashboard.emptyReviewsTitle")} detail={t("dashboard.emptyReviewsDetail")} />
      )}
    </section>
  );

  return (
    <div className="dashboard-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">{t("dashboard.workspaceEyebrow")}</p>
          <h1>{t("dashboard.clarityTitle")}</h1>
          <p>{t("dashboard.claritySubtitle")} <strong>{tenantName}</strong>.</p>
        </div>
        <div className="page-heading-actions">
          <button className="secondary" onClick={() => onNavigate("onboarding")}>
            {t("dashboard.setupGuide")}<ArrowUpRight size={15} />
          </button>
          {!admin && allowed("preaudit") && (
            <button className="primary" onClick={() => onNavigate("preaudit")}>
              <ShieldCheck size={17} /> {t("dashboard.runPreAuditBtn")}
            </button>
          )}
        </div>
      </header>

      {error && <div role="alert" className="error-banner">{error}</div>}

      {result && (
        <div role="status" className="success-banner">
          <CircleCheck size={19} />
          <div>
            <strong>{t("dashboard.continuousTitle")}</strong>
            <p>{t("dashboard.continuousSummary", { tasks: result.tasks_created, notifications: result.notifications_enqueued })}</p>
          </div>
          <button className="text-button" onClick={() => setResult(null)}>{t("common.dismiss")}</button>
        </div>
      )}

      {admin ? (
        <>
          <div className="admin-intro">
            <Users size={26} />
            <div>
              <h2>{t("dashboard.adminFocusTitle")}</h2>
              <p>{t("dashboard.adminSodDescription")}</p>
            </div>
          </div>
          {metrics && (
            <>
              <div className="metric-grid">
                <Metric label={t("dashboard.activeMembers")} value={metrics.total_members} caption={t("dashboard.peopleInWorkspace")} icon={<Users />} />
                <Metric label={t("dashboard.legalEntities")} value={metrics.legal_entities} caption={t("dashboard.businessUnits", { count: metrics.business_units })} icon={<Layers3 />} />
                <Metric label={t("dashboard.locations")} value={metrics.locations} caption={t("dashboard.organizationFootprint")} icon={<Flag />} />
                <Metric label={t("dashboard.workspaceConfig")} value={metrics.plan_code.toUpperCase()} caption={t("dashboard.enabledModules", { count: metrics.enabled_modules.length })} icon={<ShieldCheck />} />
              </div>
              <section className="surface">
                <div className="section-heading">
                  <h2>{t("dashboard.storageUsage")}</h2>
                  <span>{t("dashboard.storageUsedMb", { count: (metrics.storage_bytes_used / 1048576).toFixed(1) })}</span>
                </div>
                <progress max={metrics.max_storage_bytes || 1} value={metrics.storage_bytes_used} />
                <p>{t("dashboard.storageAllowanceGb", { count: (metrics.max_storage_bytes / 1073741824).toFixed(1) })}</p>
              </section>
            </>
          )}
        </>
      ) : (
        <>
          <div className="overview-hero">
            <section className="readiness-feature">
              <div className="readiness-copy">
                <span className="hero-label"><ShieldCheck size={17} /> {t("dashboard.compliancePostureEyebrow")}</span>
                <h2>{t("dashboard.pathTitle")}</h2>
                <p>{controls.total ? t("dashboard.controlsProgress", { implemented: controls.implemented, total: controls.total }) : t("dashboard.chooseFrameworkBaseline")}</p>
                {link("frameworks", t("dashboard.exploreFrameworks"))}
              </div>
              <div className="readiness-chart">
                <div className="readiness-ring" style={{ "--progress": score + "%" } as CSSProperties}>
                  <div>
                    <strong>{score}%</strong>
                    <span>{t("dashboard.readinessScore")}</span>
                  </div>
                </div>
                <span className="readiness-note">{controls.total ? t("dashboard.basedOnScope") : t("dashboard.noControlsAssessed")}</span>
              </div>
            </section>
            <section className="priority-feature">
              <span className="eyebrow">{t("dashboard.focusTodayEyebrow")}</span>
              <div className="priority-number">
                {summary.open_tasks.length}<span>{t("dashboard.openActionItems")}</span>
              </div>
              <p>{t("dashboard.focusProgressDetail")}</p>
              <button className="priority-link" onClick={() => setView("tasks")}>
                {t("dashboard.reviewActionItems")}<ArrowRight size={19} />
              </button>
              <div className="priority-foot">
                <Clock3 size={16} />{t("dashboard.reviewsApproaching", { count: deadlines.length })}
              </div>
            </section>
          </div>

          <div className="metric-grid">
            <Metric label={t("dashboard.controlsImplemented")} value={controls.implemented} caption={t("dashboard.controlsInScope", { count: controls.total })} icon={<CheckCheck />} />
            <Metric label={t("dashboard.frameworksAdopted")} value={summary.frameworks_adopted.length} caption={t("dashboard.activePrograms")} icon={<Layers3 />} />
            <Metric label={t("dashboard.upcomingReviews")} value={deadlines.length} caption={t("dashboard.evidencePolicyDeadlines")} icon={<Clock3 />} />
            <Metric label={t("dashboard.vendorAgreements")} value={summary.vendor_health.signed_dpa_count + "/" + summary.vendor_health.total_vendors} caption={t("dashboard.missingDpaCount", { count: summary.vendor_health.missing_dpa_count })} icon={<FileCheck2 />} />
          </div>

          <div className="dashboard-viewbar">
            <nav className="view-tabs" aria-label={t("dashboard.sectionsAriaLabel")}>
              {tabs.map(item => (
                <button
                  key={item.id}
                  aria-current={view === item.id ? "page" : undefined}
                  className={view === item.id ? "selected" : ""}
                  onClick={() => setView(item.id)}
                >
                  {item.label}{item.count !== undefined && <span>{item.count}</span>}
                </button>
              ))}
            </nav>
            {(userRole === "owner" || userRole === "compliance_manager") && (
              <button className="text-button cycle-button" disabled={running} onClick={() => void runCycle()}>
                <RefreshCw size={15} className={running ? "spinning" : "" } />
                {running ? t("dashboard.checking") : t("dashboard.runContinuousCheck")}
              </button>
            )}
          </div>

          {view === "readiness" && (
            <>
              <div className="dashboard-columns">{programPanel}{reviewPanel}</div>
              <div className="dashboard-columns">
                <section className="surface">
                  <div className="section-heading">
                    <div>
                      <h2>{t("dashboard.recentActivity")}</h2>
                      <p>{t("dashboard.traceableRecord")}</p>
                    </div>
                    <button className="text-button" onClick={() => setView("activity")}>
                      {t("dashboard.viewActivity")}<ArrowUpRight size={15} />
                    </button>
                  </div>
                  <Activity
                    items={summary.recent_activity.slice(0, 4)}
                    locale={locale}
                    noDueDateLabel={t("dashboard.noDueDate")}
                    emptyTitle={t("dashboard.emptyActivityTitle")}
                    emptyDetail={t("dashboard.emptyActivityDetail")}
                  />
                </section>
                <section className="next-step-card">
                  <span className="next-step-icon"><ShieldCheck size={26} /></span>
                  <p className="eyebrow">{t("dashboard.turnPrepEyebrow")}</p>
                  <h2>{t("dashboard.readyForReviewTitle")}</h2>
                  <p>{t("dashboard.readyForReviewDetail")}</p>
                  {link("preaudit", t("dashboard.openPreAudit"))}
                </section>
              </div>
            </>
          )}

          {view === "expiring" && reviewPanel}

          {view === "tasks" && (
            <section className="surface">
              <div className="section-heading">
                <div>
                  <h2>{t("dashboard.actionItemsTitle")}</h2>
                  <p>{t("dashboard.actionItemsSubtitle")}</p>
                </div>
                {link("compliance", t("dashboard.manageTasks"))}
              </div>
              {summary.open_tasks.length ? (
                <div className="table-wrapper">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t("dashboard.tableTask")}</th>
                        <th>{t("dashboard.tablePriority")}</th>
                        <th>{t("dashboard.tableStatus")}</th>
                        <th>{t("dashboard.tableDueDate")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {summary.open_tasks.map(task => (
                        <tr key={task.id}>
                          <td><span className="task-title"><ListTodo size={17} /><strong>{task.title}</strong></span></td>
                          <td><span className={"badge " + (task.priority === "critical" ? "badge-danger" : "badge-info")}>{translatePriority(task.priority, t)}</span></td>
                          <td>{translateTaskStatus(task.status, t)}</td>
                          <td>{date(task.due_date)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty title={t("dashboard.emptyTasksTitle")} detail={t("dashboard.emptyTasksDetail")} />
              )}
            </section>
          )}

          {view === "registers" && (
            <div className="dashboard-columns">
              <section className="surface">
                <div className="section-heading">
                  <h2>{t("dashboard.priorityRisksTitle")}</h2>
                  {link("risks", t("dashboard.viewRegister"))}
                </div>
                {summary.top_risks.map(risk => (
                  <div className="deadline-row" key={risk.id}>
                    <span className="deadline-icon"><Flag size={19} /></span>
                    <div><strong>{risk.title}</strong><small>{translateRiskStatus(risk.status, t)}</small></div>
                    <span className="badge badge-warning">{risk.residual_score ?? risk.inherent_score}</span>
                  </div>
                ))}
                {!summary.top_risks.length && <Empty title={t("dashboard.emptyRisksTitle")} detail={t("dashboard.emptyRisksDetail")} />}
              </section>
              <section className="surface">
                <div className="section-heading">
                  <h2>{t("dashboard.vendorAssuranceTitle")}</h2>
                  {link("vendors", t("dashboard.viewVendors"))}
                </div>
                <div className="vendor-stat">
                  <strong>{summary.vendor_health.signed_dpa_count}<span> / {summary.vendor_health.total_vendors}</span></strong>
                  <p>{t("dashboard.vendorsWithSignedDpa")}</p>
                </div>
                <progress value={summary.vendor_health.signed_dpa_count} max={summary.vendor_health.total_vendors || 1} />
                <div className="vendor-detail"><span>{t("dashboard.missingAgreements")}</span><strong>{summary.vendor_health.missing_dpa_count}</strong></div>
                <div className="vendor-detail"><span>{t("dashboard.criticalVendors")}</span><strong>{summary.vendor_health.critical_vendors}</strong></div>
              </section>
            </div>
          )}

          {view === "activity" && (
            <section className="surface">
              <div className="section-heading">
                <div>
                  <h2>{t("dashboard.workspaceActivityTitle")}</h2>
                  <p>{t("dashboard.workspaceActivitySubtitle")}</p>
                </div>
              </div>
              <Activity
                items={summary.recent_activity}
                locale={locale}
                noDueDateLabel={t("dashboard.noDueDate")}
                emptyTitle={t("dashboard.emptyActivityTitle")}
                emptyDetail={t("dashboard.emptyActivityDetail")}
              />
            </section>
          )}
        </>
      )}
    </div>
  );
}

function Metric({ label, value, caption, icon }: { label: string; value: string | number; caption: string; icon: ReactNode }) {
  return (
    <article className="overview-metric">
      <div>
        <span>{label}</span>
        <span className="metric-glyph">{icon}</span>
      </div>
      <strong>{value}</strong>
      <p>{caption}</p>
    </article>
  );
}

function Empty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="designed-empty">
      <CircleCheck size={27} />
      <h3>{title}</h3>
      <p>{detail}</p>
    </div>
  );
}

function Activity({
  items,
  locale,
  noDueDateLabel,
  emptyTitle,
  emptyDetail,
}: {
  items: DashboardSummary["recent_activity"];
  locale?: string;
  noDueDateLabel?: string;
  emptyTitle: string;
  emptyDetail: string;
}) {
  const { t } = useTranslation();
  return items.length ? (
    <div className="activity-list">
      {items.map(item => (
        <div className="activity-row" key={item.id}>
          <span className="activity-marker"><Check size={13} /></span>
          <div><strong>{translateActivityAction(item.action, t)}</strong><small>{translateResourceType(item.resource_type, t)}</small></div>
          <time dateTime={item.occurred_at}>{formatDate(item.occurred_at, locale, noDueDateLabel)}</time>
        </div>
      ))}
    </div>
  ) : (
    <Empty title={emptyTitle} detail={emptyDetail} />
  );
}
