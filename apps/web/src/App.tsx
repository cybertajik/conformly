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
import { ComplianceWorkspace } from "./components/ComplianceWorkspace";
import { DataLifecycleWorkspace } from "./components/DataLifecycleWorkspace";
import { FrameworkCatalog } from "./components/FrameworkCatalog";
import { OnboardingOverview } from "./components/OnboardingOverview";
import { PreAuditWorkspace } from "./components/PreAuditWorkspace";
import { PublicProfileView } from "./components/PublicProfileView";
import { PublicProfileWorkspace } from "./components/PublicProfileWorkspace";
import { WhistleblowerPublicPortal } from "./components/WhistleblowerPublicPortal";
import { WhistleblowerWorkspace } from "./components/WhistleblowerWorkspace";
import {
  canManageMemberships,
  canReadExport,
  canReadPublicProfile,
  canReadWhistleblowerCases,
} from "./permissions";

type Tab =
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

  return (
    <main>
      <section className="workspace" aria-labelledby="page-title">
        <header>
          <div>
            <p className="eyebrow">Secure compliance operations</p>
            <h1 id="page-title">Conformly</h1>
          </div>
          <button className="secondary" onClick={() => void signOut()}>
            Sign out
          </button>
        </header>
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
        <nav aria-label="Primary navigation">
          <a
            href="#overview"
            onClick={(e) => {
              e.preventDefault();
              setTab("overview");
            }}
          >
            Overview
          </a>
          <a
            href="#frameworks"
            onClick={(e) => {
              e.preventDefault();
              setTab("frameworks");
            }}
          >
            Frameworks & Overlays
          </a>
          <a
            href="#compliance"
            onClick={(e) => {
              e.preventDefault();
              setTab("compliance");
            }}
          >
            Compliance Workspace
          </a>
          <a
            href="#preaudit"
            onClick={(e) => {
              e.preventDefault();
              setTab("preaudit");
            }}
          >
            Pre-Audit Readiness
          </a>
          {canReadWhistleblowerCases(selected.role) && (
            <a
              href="#whistleblower"
              onClick={(e) => {
                e.preventDefault();
                setTab("whistleblower");
              }}
            >
              Whistleblower
            </a>
          )}
          {canReadPublicProfile(selected.role) && (
            <a
              href="#public-profile"
              onClick={(e) => {
                e.preventDefault();
                setTab("public_profile");
              }}
            >
              Trust Center
            </a>
          )}
          {canReadExport(selected.role) && (
            <a
              href="#lifecycle"
              onClick={(e) => {
                e.preventDefault();
                setTab("lifecycle");
              }}
            >
              Export & Retention
            </a>
          )}
          {canManageMemberships(selected.role) && (
            <a
              href="#members"
              onClick={(e) => {
                e.preventDefault();
                setTab("members");
              }}
            >
              Members
            </a>
          )}
        </nav>
        {tab === "overview" && (
          <OnboardingOverview
            tenantName={selected.tenant_name}
            tenantSlug={selected.tenant_slug}
            userRole={selected.role}
            onNavigate={(newTab) => setTab(newTab)}
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
          <p>Member management is restricted to tenant administrators.</p>
        )}
      </section>
    </main>
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
    <main>
      <section aria-labelledby="page-title">
        <p className="eyebrow">Secure compliance operations</p>
        <h1 id="page-title">{title}</h1>
        {detail && <p>{detail}</p>}
        {children}
      </section>
    </main>
  );
}
