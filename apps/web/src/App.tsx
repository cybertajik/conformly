import type { TenantMembershipSummary } from "@conformly/shared";
import { lazy, Suspense, useEffect, useState } from "react";

import {
  AccessDeniedError,
  SessionExpiredError,
  bootstrapSession,
  listMyTenants,
  revokeSession,
  verifyTenant,
} from "./api";
import {
  beginOidcLogin,
  clearLocalSession,
  completeOidcLogin,
  getAccessToken,
  isOidcCallback,
} from "./auth";
import { AssetWorkspace } from "./components/AssetWorkspace";
const ComplianceWorkspace = lazy(() => import("./components/ComplianceWorkspace").then(module => ({ default: module.ComplianceWorkspace })));
const DataLifecycleWorkspace = lazy(() => import("./components/DataLifecycleWorkspace").then(module => ({ default: module.DataLifecycleWorkspace })));
import { ExecutiveDashboard } from "./components/ExecutiveDashboard";
const FrameworkCatalog = lazy(() => import("./components/FrameworkCatalog").then(module => ({ default: module.FrameworkCatalog })));
import { WorkspaceShell, Brand } from "./components/WorkspaceShell";
import { ArrowUpRight, Check, Layers3, LockKeyhole } from "lucide-react";
import { LanguageSelector } from "./components/LanguageSelector";
import { MembersWorkspace } from "./components/MembersWorkspace";
import { OnboardingOverview } from "./components/OnboardingOverview";
const OrganizationWorkspace = lazy(() => import("./components/OrganizationWorkspace").then(module => ({ default: module.OrganizationWorkspace })));
const PreAuditWorkspace = lazy(() => import("./components/PreAuditWorkspace").then(module => ({ default: module.PreAuditWorkspace })));
const PublicProfileView = lazy(() => import("./components/PublicProfileView").then(module => ({ default: module.PublicProfileView })));
const PublicProfileWorkspace = lazy(() => import("./components/PublicProfileWorkspace").then(module => ({ default: module.PublicProfileWorkspace })));
import { RiskWorkspace } from "./components/RiskWorkspace";
import { VendorWorkspace } from "./components/VendorWorkspace";
import { workspaceCopy } from "./i18n/workspaceCopy";
import { I18nProvider, useTranslation } from "./i18n/I18nContext";
import {
  canManageMemberships,
  canReadAssets,
  canReadEvidence,
  canReadExport,
  canReadFrameworks,
  canReadOrganization,
  canReadPolicies,
  canReadPreAudit,
  canReadPublicProfile,
  canReadRisks,
  canReadVendors,
} from "./permissions";

export type Tab =
  | "overview"
  | "onboarding"
  | "organization"
  | "frameworks"
  | "compliance"
  | "risks"
  | "assets"
  | "vendors"
  | "preaudit"
  | "public_profile"
  | "lifecycle"
  | "members"
  | "trust_center";

type AppState = "loading" | "signed_out" | "ready" | "expired" | "denied" | "error";
const SELECTED_TENANT_KEY = "conformly.selected_tenant";

function AppContent() {
  const { t, locale } = useTranslation();
  const copy = workspaceCopy[locale];
  const [state, setState] = useState<AppState>("loading");
  const [tab, setTab] = useState<Tab>("overview");
  const [message, setMessage] = useState("");
  const [tenants, setTenants] = useState<TenantMembershipSummary[]>([]);
  const [selected, setSelected] = useState<TenantMembershipSummary | null>(null);
  const [userId, setUserId] = useState<string>("");
  const [token, setToken] = useState<string>("");
  const [trustCenterSlug, setTrustCenterSlug] = useState<string>("");

  async function loadSession(loadedToken: string) {
    setToken(loadedToken);
    const identity = await bootstrapSession(loadedToken);
    if (identity?.user_id) setUserId(identity.user_id);
    const memberships = await listMyTenants(loadedToken);
    setTenants(memberships);
    const remembered = sessionStorage.getItem(SELECTED_TENANT_KEY);
    const tenant =
      memberships.find((item) => item.tenant_id === remembered) ?? memberships[0] ?? null;
    if (tenant) {
      await verifyTenant(loadedToken, tenant.tenant_id);
      sessionStorage.setItem(SELECTED_TENANT_KEY, tenant.tenant_id);
    }
    setSelected(tenant);
    setState("ready");
  }

  useEffect(() => {
    let active = true;
    async function initialize() {
      try {
        const queryParams = new URLSearchParams(window.location.search);
        const trustParam = queryParams.get("trust-center");
        if (trustParam) {
          setTrustCenterSlug(trustParam);
          setTab("trust_center");
        }

        const sessionToken = isOidcCallback() ? await completeOidcLogin() : getAccessToken();
        if (!sessionToken) {
          if (active) setState("signed_out");
          return;
        }
        await loadSession(sessionToken);
      } catch (error) {
        if (!active) return;
        if (error instanceof SessionExpiredError) {
          clearLocalSession();
          setState("expired");
        } else if (error instanceof AccessDeniedError) {
          setState("denied");
        } else {
          setMessage(error instanceof Error ? error.message : "Sign-in failed.");
          setState("error");
        }
      }
    }
    void initialize();
    return () => {
      active = false;
    };
  }, []);

  async function chooseTenant(tenantId: string) {
    const activeToken = getAccessToken();
    if (activeToken) setToken(activeToken);
    const tenant = tenants.find((item) => item.tenant_id === tenantId);
    if (!activeToken || !tenant) return;
    try {
      await verifyTenant(activeToken, tenantId);
      sessionStorage.setItem(SELECTED_TENANT_KEY, tenantId);
      setSelected(tenant);
    } catch (error) {
      setState(error instanceof SessionExpiredError ? "expired" : "denied");
    }
  }

  async function signOut() {
    const activeToken = getAccessToken();
    try {
      if (activeToken) await revokeSession(activeToken);
    } finally {
      clearLocalSession();
      sessionStorage.removeItem(SELECTED_TENANT_KEY);
      setToken("");
      setState("signed_out");
    }
  }

  if (tab === "trust_center") {
    return (
      <PublicProfileView
        slug={trustCenterSlug}
        onBackToApp={() => {
          setTab(selected ? "public_profile" : "overview");
        }}
      />
    );
  }

  if (state === "loading") {
    return <Status eyebrow={t("status.eyebrow")} title={t("status.loadingTitle")} />;
  }
  if (state === "signed_out") {
    return (
      <Status eyebrow={t("status.eyebrow")} title={copy.welcome} detail={t("status.signedOutDetail")}>
        <div className="status-actions">
          <button className="primary" onClick={() => void beginOidcLogin().catch(error => { setMessage(error instanceof Error ? error.message : "Sign-in failed. Please try again."); setState("error"); })}>
            {t("status.signInBtn")}
          </button>
        </div>
        <div className="status-lang">
          <LanguageSelector />
        </div>
      </Status>
    );
  }

  if (state === "expired") {
    return <Status eyebrow={t("status.eyebrow")} title={t("status.expiredTitle")} detail={t("status.expiredDetail")}><button className="primary" onClick={() => setState("signed_out")}>{copy.retry}</button></Status>;
  }
  if (state === "denied") {
    return <Status eyebrow={t("status.eyebrow")} title={t("status.deniedTitle")} detail={t("status.deniedDetail")} />;
  }
  if (state === "error") {
    return <Status eyebrow={t("status.eyebrow")} title="Unable to sign in" detail={message}><button className="primary" onClick={() => setState("signed_out")}>{copy.retry}</button></Status>;
  }
  if (!selected) {
    return (
      <Status
        eyebrow={t("status.eyebrow")}
        title={t("status.noTenantTitle")}
        detail={t("status.noTenantDetail")}
      />
    );
  }

  const effectiveToken = token || (getAccessToken() ?? "");

  const navItems: { id: Tab; label: string; check?: () => boolean }[] = [
    { id: "overview", label: t("nav.overview") },
    { id: "onboarding", label: t("nav.onboarding") },
    { id: "organization", label: t("nav.organization"), check: () => canReadOrganization(selected.role) },
    { id: "frameworks", label: t("nav.frameworks"), check: () => canReadFrameworks(selected.role) },
    { id: "compliance", label: t("nav.compliance"), check: () => canReadEvidence(selected.role) || canReadPolicies(selected.role) },
    { id: "risks", label: t("nav.risks"), check: () => canReadRisks(selected.role) },
    { id: "assets", label: t("nav.assets"), check: () => canReadAssets(selected.role) },
    { id: "vendors", label: t("nav.vendors"), check: () => canReadVendors(selected.role) },
    { id: "preaudit", label: t("nav.preaudit"), check: () => canReadPreAudit(selected.role) },
    { id: "public_profile", label: t("nav.trustCenter"), check: () => canReadPublicProfile(selected.role) },
    { id: "lifecycle", label: t("nav.lifecycle"), check: () => canReadExport(selected.role) },
    { id: "members", label: t("nav.members"), check: () => canManageMemberships(selected.role) },
  ];

  const visibleNavItems = navItems.filter((item) => !item.check || item.check());


  return (
    <WorkspaceShell items={visibleNavItems} tab={tab} navigate={setTab} tenants={tenants} selected={selected} chooseTenant={id => void chooseTenant(id)} signOut={() => void signOut()}>
      <Suspense fallback={<div className="loading-state" role="status">{t("common.loading")}</div>}>
        {tab === "overview" && (
          <ExecutiveDashboard
            token={effectiveToken}
            tenantId={selected.tenant_id}
            tenantName={selected.tenant_name}
            tenantSlug={selected.tenant_slug}
            userRole={selected.role}
            onNavigate={(newTab) => setTab(newTab as Tab)}
          />
        )}
        {tab === "onboarding" && (
          <OnboardingOverview
            tenantName={selected.tenant_name}
            tenantSlug={selected.tenant_slug}
            userRole={selected.role}
            onNavigate={(newTab) => setTab(newTab as Tab)}
          />
        )}
        {tab === "organization" && (
          <OrganizationWorkspace
            tenantId={selected.tenant_id}
            userRole={selected.role}
          />
        )}
        {tab === "frameworks" && (
          <FrameworkCatalog tenantId={selected.tenant_id} userRole={selected.role} />
        )}
        {tab === "compliance" && (
          <ComplianceWorkspace
            tenantId={selected.tenant_id}
            userRole={selected.role}
            currentUserId={userId}
          />
        )}
        {tab === "risks" && (
          <RiskWorkspace
            tenantId={selected.tenant_id}
            userRole={selected.role}
          />
        )}
        {tab === "assets" && (
          <AssetWorkspace
            tenantId={selected.tenant_id}
            userRole={selected.role}
          />
        )}
        {tab === "vendors" && (
          <VendorWorkspace
            tenantId={selected.tenant_id}
            userRole={selected.role}
          />
        )}
        {tab === "preaudit" && (
          <PreAuditWorkspace
            tenantId={selected.tenant_id}
            userRole={selected.role}
            currentUserId={userId}
          />
        )}
        {tab === "public_profile" && canReadPublicProfile(selected.role) && (
          <PublicProfileWorkspace
            token={effectiveToken}
            tenantId={selected.tenant_id}
            role={selected.role}
            onOpenPublicView={(s) => {
              setTrustCenterSlug(s);
              setTab("trust_center");
            }}
          />
        )}
        {tab === "lifecycle" && canReadExport(selected.role) && (
          <DataLifecycleWorkspace
            token={effectiveToken}
            tenantId={selected.tenant_id}
            tenantSlug={selected.tenant_slug}
            role={selected.role}
          />
        )}
        {tab === "members" && (
          <MembersWorkspace
            token={effectiveToken}
            tenantId={selected.tenant_id}
            currentUserRole={selected.role}
            currentUserId={userId}
          />
        )}
      </Suspense>
    </WorkspaceShell>
  );
}

export function App() {
  return (
    <I18nProvider>
      <Suspense fallback={<Status title="Loading workspace…" />}><AppContent /></Suspense>
    </I18nProvider>
  );
}

function Status({
  title,
  detail,
  eyebrow,
  children,
}: {
  title: string;
  detail?: string;
  eyebrow?: string;
  children?: React.ReactNode;
}) {
  const { locale } = useTranslation();
  const copy = workspaceCopy[locale];
  return (
    <main className="entry-page">
      <section className="entry-story" aria-label="About Conformly">
        <Brand/>
        <div className="entry-story-copy"><span className="entry-kicker"><span/> {copy.kicker}</span><h2>{copy.less}<br/><em>{copy.more}</em></h2><p>{copy.story}</p></div>
        <div className="entry-illustration" aria-hidden="true"><div className="illustration-label"><Layers3 size={17}/> {copy.connected}</div><div className="illustration-node node-framework">{copy.frameworks} <span>01</span></div><div className="illustration-line"/><div className="illustration-node node-evidence"><Check size={18}/> {copy.evidence} <span>02</span></div><div className="illustration-line"/><div className="illustration-node node-readiness"><ShieldMark/> {copy.readiness} <ArrowUpRight size={20}/></div><div className="illustration-caption">{copy.caption}</div></div>
        <div className="entry-story-footer"><span>{copy.built}</span><span>Conformly © {new Date().getFullYear()}</span></div>
      </section>
      <section className="entry-form" aria-labelledby="page-title"><div className="entry-form-inner"><span className="entry-lock"><LockKeyhole size={23}/></span><p className="eyebrow">{eyebrow || copy.awaits}</p><h1 id="page-title">{title}</h1>{detail && <p className="entry-detail">{detail}</p>}{children}<div className="entry-assurance"><LockKeyhole size={14}/><span>{copy.secure}</span></div></div><p className="entry-disclaimer">{copy.operations}<br/>{copy.disclaimer}</p></section>
    </main>
  );
}
function ShieldMark() { return <span className="illustration-check"><Check size={20}/></span>; }
