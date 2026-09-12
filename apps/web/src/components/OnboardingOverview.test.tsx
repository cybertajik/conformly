import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OnboardingOverview } from "./OnboardingOverview";

describe("OnboardingOverview", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders organization details, pilot status, and mandatory compliance disclaimer", () => {
    const handleNavigate = vi.fn();
    render(
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
    render(
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
    render(
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
});
