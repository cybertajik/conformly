import type { TenantMembershipSummary } from "@conformly/shared";
import { useEffect, useState } from "react";

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
import { ComplianceWorkspace } from "./components/ComplianceWorkspace";
import { DataLifecycleWorkspace } from "./components/DataLifecycleWorkspace";
import { FrameworkCatalog } from "./components/FrameworkCatalog";
import { OnboardingOverview } from "./components/OnboardingOverview";
import { OrganizationWorkspace } from "./components/OrganizationWorkspace";
import { PreAuditWorkspace } from "./components/PreAuditWorkspace";
import { PublicProfileView } from "./components/PublicProfileView";
import { PublicProfileWorkspace } from "./components/PublicProfileWorkspace";
import { RiskWorkspace } from "./components/RiskWorkspace";
import { VendorWorkspace } from "./components/VendorWorkspace";
import { WhistleblowerPublicPortal } from "./components/WhistleblowerPublicPortal";
import { WhistleblowerWorkspace } from "./components/WhistleblowerWorkspace";
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
  canReadWhistleblowerCases,
} from "./permissions";

type Tab =
  | "overview"
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
  | "whistleblower"
  | "public_whistleblower"
  | "trust_center";

type AppState = "loading" | "signed_out" | "ready" | "expired" | "denied" | "error";
const SELECTED_TENANT_KEY = "conformly.selected_tenant";

export function App() {
  const [state, setState] = useState<AppState>("loading");
  const [tab, setTab] = useState<Tab>("overview");
  const [message, setMessage] = useState("");
  const [tenants, setTenants] = useState<TenantMembershipSummary[]>([]);
  const [selected, setSelected] = useState<TenantMembershipSummary | null>(null);
  const [userId, setUserId] = useState<string>("");
  const [token, setToken] = useState<string>("");
  const [publicPortalSlug, setPublicPortalSlug] = useState<string>("");
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
        const portalParam = queryParams.get("portal");
        if (portalParam) {
          setPublicPortalSlug(portalParam);
          setTab("public_whistleblower");
        }
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

  if (tab === "public_whistleblower") {
    return (
      <WhistleblowerPublicPortal
        slug={publicPortalSlug}
        onBackToApp={() => {
          setTab("overview");
        }}
      />
    );
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

  if (state === "loading") return <Status title="Loading Conformly" />;
  if (state === "signed_out") {
    return (
      <Status title="Conformly" detail="Secure compliance operations for audit readiness.">
        <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center", marginTop: "1rem" }}>
          <button onClick={() => void beginOidcLogin()}>Sign in</button>
          <button
            className="secondary"
            onClick={() => {
              setTab("public_whistleblower");
            }}
          >
            Whistleblower Intake
          </button>
        </div>
      </Status>
    );
  }
  if (state === "expired") {
    return <Status title="Session expired" detail="Sign in again to continue." />;
  }
  if (state === "denied") {
    return <Status title="Access denied" detail="Your account cannot access that tenant." />;
  }
  if (state === "error") return <Status title="Unable to sign in" detail={message} />;
  if (!selected) {
    return (
      <Status
        title="No tenant available"
        detail="Your account has no active Conformly membership. Ask an administrator for access."
      />
    );
  }

  const effectiveToken = token || (getAccessToken() ?? "");

  const navItems: { id: Tab; label: string; icon: string; check?: () => boolean }[] = [
    { id: "overview", label: "Overview", icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1" },
    { id: "organization", label: "Organization", icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4", check: () => canReadOrganization(selected.role) },
    { id: "frameworks", label: "Frameworks", icon: "M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10", check: () => canReadFrameworks(selected.role) },
    { id: "compliance", label: "Compliance", icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z", check: () => canReadEvidence(selected.role) || canReadPolicies(selected.role) },
    { id: "risks", label: "Risk Register", icon: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z", check: () => canReadRisks(selected.role) },
    { id: "assets", label: "Asset Register", icon: "M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01", check: () => canReadAssets(selected.role) },
    { id: "vendors", label: "Vendor Register", icon: "M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z", check: () => canReadVendors(selected.role) },
    { id: "preaudit", label: "Pre-Audit", icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4", check: () => canReadPreAudit(selected.role) },
    { id: "public_profile", label: "Trust Center", icon: "M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064", check: () => canReadPublicProfile(selected.role) },
    { id: "lifecycle", label: "Export & Data", icon: "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4", check: () => canReadExport(selected.role) },
    { id: "members", label: "Members", icon: "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z", check: () => canManageMemberships(selected.role) },
  ];

  const visibleNavItems = navItems.filter((item) => !item.check || item.check());
  const userInitials = (selected.tenant_name || "U").substring(0, 2).toUpperCase();

  return (
    <div className="app-shell">
      {/* ─── Sidebar ─── */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon">C</div>
          <span className="brand-name">Conformly</span>
        </div>

        <div className="sidebar-org">
          <label htmlFor="tenant-selector">Organization</label>
          <select
            id="tenant-selector"
            value={selected.tenant_id}
            onChange={(event) => void chooseTenant(event.target.value)}
          >
            {tenants.map((tenant) => (
              <option key={tenant.tenant_id} value={tenant.tenant_id}>
                {tenant.tenant_name}
              </option>
            ))}
          </select>
        </div>

        <nav className="sidebar-nav" aria-label="Primary navigation">
          <div className="sidebar-section-label">Platform</div>
          {visibleNavItems.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-item${tab === item.id ? " active" : ""}`}
              onClick={() => setTab(item.id)}
            >
              <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d={item.icon} />
              </svg>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="user-avatar">{userInitials}</div>
            <div className="user-info">
              <div className="user-name">{selected.tenant_name}</div>
              <div className="user-email">{selected.role.replaceAll("_", " ")}</div>
            </div>
            <button
              className="ghost"
              onClick={() => void signOut()}
              title="Sign out"
              style={{ padding: "0.3rem", minHeight: "auto" }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            </button>
          </div>
        </div>
      </aside>

      {/* ─── Main Content ─── */}
      <div className="main-content">
        {tab === "overview" && (
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
        {tab === "whistleblower" && canReadWhistleblowerCases(selected.role) && (
          <WhistleblowerWorkspace
            token={effectiveToken}
            tenantContext={{
              tenant_id: selected.tenant_id,
              role: selected.role,
            }}
            onOpenPublicPortal={(slug) => {
              setPublicPortalSlug(slug);
              setTab("public_whistleblower");
            }}
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
          <div className="card" style={{ marginTop: "1rem" }}>
            <p style={{ color: "var(--text-secondary)" }}>Member management is restricted to tenant administrators.</p>
          </div>
        )}
      </div>
    </div>
  );
}


function Status({
  title,
  detail,
  children,
}: {
  title: string;
  detail?: string;
  children?: React.ReactNode;
}) {
  return (
    <main className="status-page">
      <section aria-labelledby="page-title">
        <p className="eyebrow">Secure compliance operations</p>
        <h1 id="page-title">{title}</h1>
        {detail && <p style={{ fontSize: "1.1rem", marginTop: "0.75rem" }}>{detail}</p>}
        {children}
      </section>
    </main>
  );
}

