import React, { FC, useCallback, useEffect, useRef, useState } from "react";
import type { TenantMembershipSummary } from "@conformly/shared";
import { LanguageSelector } from "../components/LanguageSelector";
import { useTranslation } from "../i18n/I18nContext";
import { CustomerDemoWorkspace, PortalView } from "./CustomerDemoWorkspace";
import { isPreauditEnabled } from "./preaudit-api";
import "./portal.css";

export interface CustomerDemoPortalProps {
  tenantId: string;
  token: string;
  userRole?: string;
  userId?: string;
  tenantName?: string;
  tenantSlug?: string;
  tenants?: TenantMembershipSummary[];
  onSelectTenant?: (tenantId: string) => void;
  onSignOut?: () => void;
  onSessionExpired?: () => void;
  initialView?: PortalView;
}

function parseHashView(hash: string): PortalView | null {
  const clean = hash.replace(/^#/, "");
  if (
    clean === "overview" ||
    clean === "work_queue" ||
    clean === "company_setup" ||
    clean === "frameworks" ||
    clean === "controls_evidence" ||
    clean === "assessments_findings" ||
    clean === "organization" ||
    clean === "operations" ||
    (clean === "preaudit" && isPreauditEnabled())
  ) {
    return clean;
  }
  return null;
}

export const CustomerDemoPortal: FC<CustomerDemoPortalProps> = ({
  tenantId,
  token,
  userRole = "owner",
  userId,
  tenantName = "Conformly Demo",
  tenants = [],
  onSelectTenant,
  onSignOut,
  onSessionExpired,
  initialView = "overview",
}) => {
  const { t } = useTranslation();

  // Parse valid initial view: explicit initialView takes priority if non-default; else hash deep link
  const getInitialView = useCallback((): PortalView => {
    if (initialView && initialView !== "overview") {
      return initialView;
    }
    if (typeof window !== "undefined" && window.location.hash) {
      const parsed = parseHashView(window.location.hash);
      if (parsed) return parsed;
    }
    return initialView;
  }, [initialView]);

  const [activeView, setActiveView] = useState<PortalView>(getInitialView);
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);
  const sidebarRef = useRef<HTMLElement>(null);
  const toggleBtnRef = useRef<HTMLButtonElement>(null);

  // Sync active view with window hash safely without touching query params
  const handleViewChange = (newView: PortalView) => {
    setActiveView(newView);
    setMobileMenuOpen(false);
    if (typeof window !== "undefined") {
      try {
        window.history.replaceState(null, "", `#${newView}`);
      } catch {
        // Fallback for restricted environments
      }
    }
  };

  // Close mobile drawer on Escape and manage focus trapping
  useEffect(() => {
    if (!mobileMenuOpen) return;

    const previousActive = document.activeElement as HTMLElement | null;

    // Focus the first focusable element inside the drawer
    const focusableSelector =
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
    const focusables = sidebarRef.current?.querySelectorAll<HTMLElement>(focusableSelector);
    if (focusables && focusables.length > 0) {
      focusables[0].focus();
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMobileMenuOpen(false);
        toggleBtnRef.current?.focus();
        return;
      }

      if (e.key === "Tab") {
        const currentFocusables = sidebarRef.current?.querySelectorAll<HTMLElement>(focusableSelector);
        if (!currentFocusables || currentFocusables.length === 0) return;
        const first = currentFocusables[0];
        const last = currentFocusables[currentFocusables.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      previousActive?.focus();
    };
  }, [mobileMenuOpen]);

  // Listen to hash changes for browser forward/back and direct navigation
  useEffect(() => {
    const handleHashChange = () => {
      const v = getInitialView();
      setActiveView(v);
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, [getInitialView]);

  const viewLabels: Record<PortalView, string> = {
    overview: t("portal.navOverview"),
    work_queue: t("portal.navWorkQueue"),
    company_setup: t("portal.navCompanySetup"),
    frameworks: t("portal.navFrameworks"),
    controls_evidence: t("portal.navControlsEvidence"),
    assessments_findings: t("portal.navAssessmentsFindings"),
    organization: t("portal.navOrganization"),
    operations: t("portal.navOperations"),
    preaudit: t("portal.navPreaudit"),
  };

  const navItems: { id: PortalView; label: string; icon: React.ReactNode }[] = [
    {
      id: "overview",
      label: t("portal.navOverview"),
      icon: (
        <svg className="portal-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1" />
        </svg>
      ),
    },
    {
      id: "work_queue",
      label: t("portal.navWorkQueue"),
      icon: (
        <svg className="portal-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M9 11l3 3L22 4" />
          <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
        </svg>
      ),
    },
    {
      id: "company_setup",
      label: t("portal.navCompanySetup"),
      icon: (
        <svg className="portal-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
        </svg>
      ),
    },
    {
      id: "frameworks",
      label: t("portal.navFrameworks"),
      icon: (
        <svg className="portal-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
      ),
    },
    {
      id: "controls_evidence",
      label: t("portal.navControlsEvidence"),
      icon: (
        <svg className="portal-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
      ),
    },
    {
      id: "assessments_findings",
      label: t("portal.navAssessmentsFindings"),
      icon: (
        <svg className="portal-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
        </svg>
      ),
    },
    ...(isPreauditEnabled()
      ? [
          {
            id: "preaudit" as PortalView,
            label: t("portal.navPreaudit"),
            icon: (
              <svg className="portal-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            ),
          },
        ]
      : []),
    {
      id: "operations",
      label: t("portal.navOperations"),
      icon: (
        <svg className="portal-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
          <path d="M14 2v6h6" />
          <path d="M16 13H8" />
          <path d="M16 17H8" />
          <path d="M10 9H8" />
        </svg>
      ),
    },
    {
      id: "organization",
      label: t("portal.navOrganization"),
      icon: (
        <svg className="portal-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 00-3-3.87" />
          <path d="M16 3.13a4 4 0 010 7.75" />
        </svg>
      ),
    },
  ];

  const userInitials = (tenantName || "CD").substring(0, 2).toUpperCase();

  return (
    <div className="conformly-portal-root" data-testid="conformly-portal-shell">
      {/* Skip to Content for Keyboard Users */}
      <a href="#portal-main" className="portal-skip-link">
        {t("portal.skipToContent")}
      </a>

      {/* Mobile Drawer Backdrop */}
      <div
        className={`portal-sidebar-backdrop ${mobileMenuOpen ? "open" : ""}`}
        onClick={() => setMobileMenuOpen(false)}
        aria-hidden="true"
      />

      {/* Persistent Sidebar (Desktop & Tablet) / Drawer (Mobile) */}
      <aside
        ref={sidebarRef}
        id="portal-sidebar-nav"
        className={`portal-sidebar ${mobileMenuOpen ? "open" : ""}`}
        aria-label={t("portal.navAriaLabel")}
        data-testid="portal-sidebar"
      >
        <div className="portal-sidebar-brand">
          <div className="portal-brand-logo" aria-hidden="true">
            C
          </div>
          <span className="portal-brand-title">{t("portal.brand")}</span>
        </div>

        {/* Organization / Tenant Switcher */}
        {tenants.length > 0 && onSelectTenant && (
          <div className="portal-org-selector">
            <label htmlFor="portal-tenant-selector" className="portal-org-label">
              {t("portal.tenantLabel")}
            </label>
            <select
              id="portal-tenant-selector"
              className="portal-org-select"
              value={tenantId}
              onChange={(e) => onSelectTenant(e.target.value)}
              data-testid="portal-tenant-select"
            >
              {tenants.map((ten) => (
                <option key={ten.tenant_id} value={ten.tenant_id}>
                  {ten.tenant_name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* View Navigation */}
        <ul className="portal-nav-list" role="navigation">
          {navItems.map((item) => {
            const isActive = activeView === item.id;
            return (
              <li key={item.id} className="portal-nav-item">
                <button
                  type="button"
                  className={`portal-nav-button ${isActive ? "active" : ""}`}
                  onClick={() => handleViewChange(item.id)}
                  aria-current={isActive ? "page" : undefined}
                  data-testid={`nav-view-${item.id}`}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </button>
              </li>
            );
          })}
        </ul>

        {/* Footer: User Profile, Language & Sign Out */}
        <div className="portal-sidebar-footer">
          <div className="portal-user-card">
            <div className="portal-user-avatar" aria-hidden="true">
              {userInitials}
            </div>
            <div className="portal-user-info">
              <div className="portal-user-name" title={tenantName}>
                {tenantName}
              </div>
              <div className="portal-user-role">
                {userRole.replaceAll("_", " ")}
              </div>
            </div>
          </div>

          <div style={{ padding: "4px 0" }}>
            <LanguageSelector compact />
          </div>

          {onSignOut && (
            <button
              type="button"
              className="portal-signout-btn"
              onClick={onSignOut}
              data-testid="portal-signout-btn"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              <span>{t("portal.signOut")}</span>
            </button>
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="portal-main-area">
        {/* Topbar */}
        <header className="portal-topbar">
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <button
              ref={toggleBtnRef}
              type="button"
              className="portal-mobile-menu-btn"
              onClick={() => setMobileMenuOpen((prev) => !prev)}
              aria-label={t("portal.menuToggle")}
              aria-expanded={mobileMenuOpen}
              aria-controls="portal-sidebar-nav"
              data-testid="portal-mobile-menu-toggle"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>

            <nav aria-label="Breadcrumb" className="portal-breadcrumbs">
              <span className="portal-breadcrumb-item">{t("portal.breadcrumbHome")}</span>
              <span className="portal-breadcrumb-sep">/</span>
              <span className="portal-breadcrumb-current" data-testid="breadcrumb-active-view">
                {viewLabels[activeView]}
              </span>
            </nav>
          </div>

          <div className="portal-topbar-actions">
            <span className="portal-badge" data-testid="topbar-tenant-badge">
              {tenantName}
            </span>
            <span className="portal-badge role" data-testid="topbar-role-badge">
              {userRole.replaceAll("_", " ")}
            </span>
          </div>
        </header>

        {/* Content Body with Preserved State & Fencing */}
        <main id="portal-main" className="portal-content-body" tabIndex={-1}>
          <div className="portal-page-header">
            <h1 className="portal-page-title" data-testid="portal-page-title">
              {viewLabels[activeView]}
            </h1>
            <p className="portal-page-subtitle">
              {activeView === "overview" && t("portal.welcomeSubtitle")}
              {activeView === "company_setup" && t("portal.setupSubtitle")}
              {activeView === "frameworks" && t("portal.frameworksSubtitle")}
              {activeView === "controls_evidence" && t("portal.controlsSubtitle")}
              {activeView === "assessments_findings" && t("portal.assessmentsSubtitle")}
              {activeView === "organization" && t("portal.orgSubtitle")}
            {activeView === "operations" && t("portal.operationsSubtitle")}
            {activeView === "preaudit" && t("portal.preauditSubtitle")}
            </p>
          </div>

          {/* Connected Real A-C CustomerDemoWorkspace */}
          <CustomerDemoWorkspace
            key={`${tenantId}:${token}`}
            tenantId={tenantId}
            token={token}
            userRole={userRole}
            userId={userId}
            onSessionExpired={onSessionExpired}
            activePortalView={activeView}
            onNavigateView={handleViewChange}
            hideShellHeader={true}
          />
        </main>
      </div>
    </div>
  );
};
