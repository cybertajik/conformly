import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider, useTranslation } from "../i18n/I18nContext";
import { OnboardingOverview } from "./OnboardingOverview";

function renderWithI18n(ui: React.ReactElement) {
  return render(<I18nProvider>{ui}</I18nProvider>);
}

describe("OnboardingOverview", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    localStorage.clear();
  });

  it("renders organization details, pilot status, and mandatory compliance disclaimer", () => {
    const handleNavigate = vi.fn();
    renderWithI18n(
      <OnboardingOverview
        tenantName="Acme Health"
        tenantSlug="acme-health"
        userRole="owner"
        onNavigate={handleNavigate}
      />
    );

    expect(screen.getByText("Acme Health")).toBeInTheDocument();
    expect(screen.getByText("acme-health")).toBeInTheDocument();
    expect(screen.getByText(/Pilot Operational/i)).toBeInTheDocument();

    // Mandatory disclaimer
    expect(
      screen.getByText(/Conformly is an audit-readiness and compliance operations platform/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/not an accredited certification body/i)
    ).toBeInTheDocument();
  });

  it("renders onboarding checklist steps and triggers navigation callbacks", () => {
    const handleNavigate = vi.fn();
    renderWithI18n(
      <OnboardingOverview
        tenantName="Acme Health"
        tenantSlug="acme-health"
        userRole="compliance_manager"
        onNavigate={handleNavigate}
      />
    );

    expect(screen.getByText(/1\. Adopt Canonical Compliance Framework/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. Implement Controls & Collect Evidence/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. Run Pre-Audit Readiness Check/i)).toBeInTheDocument();
    expect(screen.getByText(/4\. Publish Public Trust Center/i)).toBeInTheDocument();
    expect(screen.getByText(/5\. Configure Anonymous Whistleblower Channel/i)).toBeInTheDocument();

    // Click navigation button
    const frameworkBtn = screen.getByRole("button", { name: /View Catalog/i });
    fireEvent.click(frameworkBtn);
    expect(handleNavigate).toHaveBeenCalledWith("frameworks");

    const complianceBtn = screen.getByRole("button", { name: /Open Compliance/i });
    fireEvent.click(complianceBtn);
    expect(handleNavigate).toHaveBeenCalledWith("compliance");
  });

  it("renders pilot service intake response objectives table", () => {
    renderWithI18n(
      <OnboardingOverview
        tenantName="Acme Health"
        tenantSlug="acme-health"
        userRole="administrator"
        onNavigate={vi.fn()}
      />
    );

    expect(screen.getByText("Pilot Service & Support Intake")).toBeInTheDocument();
    expect(screen.getByText("Critical (P1)")).toBeInTheDocument();
    expect(screen.getByText("4 Hours (24/7 intake)")).toBeInTheDocument();
    expect(screen.getByText("High (P2)")).toBeInTheDocument();
    expect(screen.getByText("1 Business Day")).toBeInTheDocument();
    expect(screen.getByText("security-intake@conformly.com")).toBeInTheDocument();
  });

  it("tracks and saves progress in localStorage when steps are toggled", () => {
    const { unmount } = renderWithI18n(
      <OnboardingOverview
        tenantName="Acme Health"
        tenantSlug="acme-health"
        userRole="owner"
        onNavigate={vi.fn()}
      />
    );

    // Initial progress is 0%
    const progressBar = screen.getByRole("progressbar");
    expect(progressBar).toHaveAttribute("aria-valuenow", "0");
    expect(screen.getByText(/0 of 5 milestones completed \(0%\)/i)).toBeInTheDocument();

    // Toggle step 1
    const toggleStep1 = screen.getByRole("button", {
      name: /Adopt Canonical Compliance Framework - Mark as Completed/i,
    });
    fireEvent.click(toggleStep1);

    // Progress updates to 20%
    expect(progressBar).toHaveAttribute("aria-valuenow", "20");
    expect(screen.getByText(/1 of 5 milestones completed \(20%\)/i)).toBeInTheDocument();

    // Unmount and re-render with same tenant to verify persistence
    unmount();

    renderWithI18n(
      <OnboardingOverview
        tenantName="Acme Health"
        tenantSlug="acme-health"
        userRole="owner"
        onNavigate={vi.fn()}
      />
    );

    // Saved state is restored
    const restoredProgressBar = screen.getByRole("progressbar");
    expect(restoredProgressBar).toHaveAttribute("aria-valuenow", "20");
    expect(screen.getByText(/1 of 5 milestones completed \(20%\)/i)).toBeInTheDocument();
  });

  it("shows celebration banner when all 5 milestones are completed and allows resetting progress", () => {
    renderWithI18n(
      <OnboardingOverview
        tenantName="Acme Health"
        tenantSlug="acme-health"
        userRole="owner"
        onNavigate={vi.fn()}
      />
    );

    const toggleButtons = [
      screen.getByRole("button", { name: /Adopt Canonical Compliance Framework/i }),
      screen.getByRole("button", { name: /Implement Controls & Collect Evidence/i }),
      screen.getByRole("button", { name: /Run Pre-Audit Readiness Check/i }),
      screen.getByRole("button", { name: /Publish Public Trust Center/i }),
      screen.getByRole("button", { name: /Configure Anonymous Whistleblower Channel/i }),
    ];

    // Complete all 5
    for (const btn of toggleButtons) {
      fireEvent.click(btn);
    }

    const progressBar = screen.getByRole("progressbar");
    expect(progressBar).toHaveAttribute("aria-valuenow", "100");
    expect(screen.getByText(/All Onboarding Milestones Complete!/i)).toBeInTheDocument();

    // Reset progress
    const resetBtn = screen.getByRole("button", { name: /Reset Progress/i });
    fireEvent.click(resetBtn);

    expect(progressBar).toHaveAttribute("aria-valuenow", "0");
    expect(screen.queryByText(/All Onboarding Milestones Complete!/i)).not.toBeInTheDocument();
  });

  it("renders in German when locale is set to de", () => {
    function GermanWrapper() {
      const { setLocale } = useTranslation();
      React.useEffect(() => {
        setLocale("de");
      }, [setLocale]);

      return (
        <OnboardingOverview
          tenantName="Acme Health"
          tenantSlug="acme-health"
          userRole="owner"
          onNavigate={vi.fn()}
        />
      );
    }

    render(
      <I18nProvider>
        <GermanWrapper />
      </I18nProvider>
    );

    expect(screen.getByText(/Pilot Betriebsbereit/i)).toBeInTheDocument();
    expect(screen.getByText(/Kanonisches Compliance-Framework übernehmen/i)).toBeInTheDocument();
    expect(screen.getByText(/Pilot Service & Support-Annahme/i)).toBeInTheDocument();
  });
});
