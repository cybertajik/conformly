import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { I18nProvider } from "../i18n/I18nContext";
import { LanguageSelector } from "./LanguageSelector";
import { OnboardingOverview } from "./OnboardingOverview";

vi.mock("../auth", () => ({
  getAccessToken: () => "mock-jwt-token",
  isOidcCallback: () => false,
  completeOidcLogin: vi.fn(),
  beginOidcLogin: vi.fn(),
  clearLocalSession: vi.fn(),
}));

vi.mock("../api", () => ({
  bootstrapSession: () => Promise.resolve({ user_id: "user-123", email: "audit@example.com" }),
  listMyTenants: () =>
    Promise.resolve([
      {
        tenant_id: "tenant-abc",
        tenant_name: "Acme Compliance Corp",
        tenant_slug: "acme-corp",
        role: "owner",
      },
    ]),
  verifyTenant: () => Promise.resolve({ ok: true }),
  revokeSession: () => Promise.resolve(),
  listFrameworkCatalog: () => Promise.resolve({ frameworks: [] }),
  getExecutiveDashboardSummary: () =>
    Promise.resolve({
      readiness_score: 85,
      overall_readiness_score: 85,
      controls_summary: { total: 10, passing: 8, failing: 2 },
      policies_summary: { total: 5, active: 4, review_required: 1 },
      evidence_summary: { total: 12, valid: 10, expired: 2 },
      action_items: [],
      recent_activity: [],
      is_administrator_view: false,
    }),
  listControls: () => Promise.resolve({ controls: [] }),
  listEvidence: () => Promise.resolve({ evidence: [] }),
  listPolicies: () => Promise.resolve({ policies: [] }),
  listRisks: () => Promise.resolve([]),
  listAssets: () => Promise.resolve([]),
  listVendors: () => Promise.resolve([]),
  listPreAudits: () => Promise.resolve([]),
}));

describe("Customer Journey & Accessibility Verification", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    cleanup();
    localStorage.clear();
    sessionStorage.clear();
  });

  it("verifies accessibility landmark roles and skip-to-content link in App shell", async () => {
    render(<App />);

    // 1. Skip-to-content link
    const skipLink = await screen.findByText(/Skip to main content/i);
    expect(skipLink).toBeInTheDocument();
    expect(skipLink).toHaveAttribute("href", "#main-content");
    expect(skipLink).toHaveClass("skip-to-content");

    // 2. Main content landmark
    const mainContent = document.getElementById("main-content");
    expect(mainContent).toBeInTheDocument();
    expect(mainContent?.tagName.toLowerCase()).toBe("main");

    // 3. Aside / Sidebar landmark
    const sidebar = screen.getByRole("complementary", { name: /Sidebar/i });
    expect(sidebar).toBeInTheDocument();

    // 4. Primary navigation landmark
    const nav = screen.getByRole("navigation", { name: /Primary navigation/i });
    expect(nav).toBeInTheDocument();
  });

  it("verifies language selector accessibility and multi-lingual UI switching", async () => {
    render(
      <I18nProvider>
        <LanguageSelector />
      </I18nProvider>
    );

    const selectorBtn = screen.getByRole("button", { name: /Select language/i });
    expect(selectorBtn).toBeInTheDocument();
    expect(selectorBtn).toHaveAttribute("aria-haspopup", "listbox");
    expect(selectorBtn).toHaveAttribute("aria-expanded", "false");

    // Open dropdown
    fireEvent.click(selectorBtn);
    expect(selectorBtn).toHaveAttribute("aria-expanded", "true");

    const listbox = screen.getByRole("listbox", { name: /Select language/i });
    expect(listbox).toBeInTheDocument();

    const germanOption = screen.getByRole("option", { name: /Deutsch/i });
    expect(germanOption).toBeInTheDocument();

    // Select German
    fireEvent.click(germanOption);
    expect(document.documentElement.lang).toBe("de");
    expect(localStorage.getItem("conformly.locale")).toBe("de");
  });

  it("verifies full onboarding to workspace navigation customer journey", () => {
    const handleNavigate = vi.fn();
    render(
      <I18nProvider>
        <OnboardingOverview
          tenantName="Enterprise Corp"
          tenantSlug="enterprise-corp"
          userRole="owner"
          onNavigate={handleNavigate}
        />
      </I18nProvider>
    );

    // Verify milestones are present
    expect(screen.getByText(/Adopt Canonical Compliance Framework/i)).toBeInTheDocument();
    expect(screen.getByText(/Implement Controls & Collect Evidence/i)).toBeInTheDocument();
    expect(screen.getByText(/Run Pre-Audit Readiness Check/i)).toBeInTheDocument();
    expect(screen.getByText(/Publish Public Trust Center/i)).toBeInTheDocument();
    expect(screen.getByText(/Configure Anonymous Whistleblower Channel/i)).toBeInTheDocument();

    // Complete first milestone
    const step1Btn = screen.getByRole("button", {
      name: /Adopt Canonical Compliance Framework - Mark as Completed/i,
    });
    fireEvent.click(step1Btn);

    // Verify progressbar updated
    const progressBar = screen.getByRole("progressbar");
    expect(progressBar).toHaveAttribute("aria-valuenow", "20");

    // Navigate to frameworks workspace
    const viewCatalogBtn = screen.getByRole("button", { name: /View Catalog/i });
    fireEvent.click(viewCatalogBtn);
    expect(handleNavigate).toHaveBeenCalledWith("frameworks");

    // Navigate to compliance workspace
    const openComplianceBtn = screen.getByRole("button", { name: /Open Compliance/i });
    fireEvent.click(openComplianceBtn);
    expect(handleNavigate).toHaveBeenCalledWith("compliance");

    // Navigate to pre-audit workspace
    const startPreAuditBtn = screen.getByRole("button", { name: /Start Pre-Audit/i });
    fireEvent.click(startPreAuditBtn);
    expect(handleNavigate).toHaveBeenCalledWith("preaudit");
  });
});
