import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { Asset, Policy, Risk, Vendor } from "./operations-types";
import { ReviewCalendar } from "./ReviewCalendar";
import { ComplianceTask } from "./task-types";

describe("ReviewCalendar Component", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  const baseDate = "2026-10-29T12:00:00Z";

  const samplePolicy: Policy = {
    id: "pol-1",
    tenant_id: "ten-1",
    title: "Access Control Review",
    description: "Annual review",
    version: 1,
    version_string: "1.0",
    review_cycle_days: 365,
    status: "published",
    classification: "Internal",
    content: "RESTRICTED BODY TEXT MUST NOT LEAK",
    owner_user_id: "user-1",
    approved_by_user_id: null,
    approved_at: null,
    next_review_due: "2026-10-20T00:00:00Z", // OVERDUE
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };

  const sampleRisk: Risk = {
    id: "risk-1",
    tenant_id: "ten-1",
    title: "Cloud Misconfiguration Risk",
    description: "Quarterly review",
    category: "technical",
    likelihood: 3,
    impact: 4,
    residual_score: 12,
    status: "identified",
    inherent_score: 12,
    control_id: null,
    treatments: [],
    owner_user_id: "user-1",
    next_review_due_at: "2026-10-29T00:00:00Z", // TODAY
    created_at: "2026-01-01T00:00:00Z",
  };

  const sampleAsset: Asset = {
    id: "asset-1",
    tenant_id: "ten-1",
    name: "Production Kubernetes Cluster",
    asset_type: "cloud_service",
    classification: "restricted",
    description: "Core cluster",
    owner_user_id: "user-1",
    status: "active",
    next_review_due_at: "2026-11-02T00:00:00Z", // NEXT 7 DAYS (+4 days)
    created_at: "2026-01-01T00:00:00Z",
  };

  const sampleVendor: Vendor = {
    id: "vendor-1",
    tenant_id: "ten-1",
    name: "Datadog Monitoring",
    service_description: "APM and log analytics",
    criticality: "high",
    data_classification_accessed: "Confidential",
    country_residency: "US",
    dpa_signed: true,
    security_reviewed_at: "2026-05-01T00:00:00Z",
    next_review_due_at: "2026-11-20T00:00:00Z", // NEXT 30 DAYS (+22 days)
    status: "active",
  };

  const sampleTask: ComplianceTask = {
    id: "task-1",
    tenant_id: "ten-1",
    title: "Bi-Weekly Firewall Audit",
    description: "Audit firewall rule sets",
    due_date: "2026-11-04T00:00:00Z", // NEXT 7 DAYS (+6 days)
    status: "pending",
    priority: "high",
    assignee_user_id: "user-1",
    control_type: null,
    control_id: null,
    evidence_id: null,
    policy_id: null,
    version: 1,
    completed_at: null,
    completed_by_user_id: null,
    created_at: "2026-10-29T10:00:00Z",
    updated_at: "2026-10-29T10:00:00Z",
  };

  it("calculates UTC date buckets correctly and displays badges", () => {
    render(
      <I18nProvider>
        <ReviewCalendar
          tenantId="ten-1"
          token="token-abc"
          currentDate={baseDate}
          policies={[samplePolicy]}
          risks={[sampleRisk]}
          assets={[sampleAsset]}
          vendors={[sampleVendor]}
          tasks={[sampleTask]}
        />
      </I18nProvider>
    );

    // Assert badges
    expect(screen.getByTestId("badge-actionable")).toHaveTextContent("5");
    expect(screen.getByTestId("badge-overdue")).toHaveTextContent("1");
    expect(screen.getByTestId("badge-today")).toHaveTextContent("1");
    expect(screen.getByTestId("badge-next7")).toHaveTextContent("3"); // today + asset(Nov 2) + task(Nov 4)
    expect(screen.getByTestId("badge-next30")).toHaveTextContent("4"); // today + asset + task + vendor(Nov 20)

    // Never leak body text into calendar
    expect(screen.queryByText("RESTRICTED BODY TEXT MUST NOT LEAK")).not.toBeInTheDocument();
  });

  it("excludes completed, archived, and cancelled items from actionable reviews", () => {
    const archivedPolicy: Policy = {
      ...samplePolicy,
      id: "pol-archived",
      status: "archived",
      next_review_due: "2026-10-20T00:00:00Z",
    };
    const completedTask: ComplianceTask = {
      ...sampleTask,
      id: "task-completed",
      status: "completed",
      due_date: "2026-10-20T00:00:00Z",
    };

    render(
      <I18nProvider>
        <ReviewCalendar
          tenantId="ten-1"
          token="token-abc"
          currentDate={baseDate}
          policies={[archivedPolicy]}
          tasks={[completedTask]}
        />
      </I18nProvider>
    );

    // Both should be excluded
    expect(screen.getByTestId("badge-actionable")).toHaveTextContent("0");
    expect(screen.getByTestId("empty-reviews-state")).toBeInTheDocument();
  });

  it("filters review items by bucket and source kind", () => {
    render(
      <I18nProvider>
        <ReviewCalendar
          tenantId="ten-1"
          token="token-abc"
          currentDate={baseDate}
          policies={[samplePolicy]}
          risks={[sampleRisk]}
          assets={[sampleAsset]}
          vendors={[sampleVendor]}
          tasks={[sampleTask]}
        />
      </I18nProvider>
    );

    // Initial all items visible
    expect(screen.getByText("Access Control Review")).toBeInTheDocument();
    expect(screen.getByText("Cloud Misconfiguration Risk")).toBeInTheDocument();
    expect(screen.getByText("Production Kubernetes Cluster")).toBeInTheDocument();

    // Filter by overdue
    fireEvent.change(screen.getByTestId("review-bucket-filter"), { target: { value: "overdue" } });
    expect(screen.getByText("Access Control Review")).toBeInTheDocument();
    expect(screen.queryByText("Cloud Misconfiguration Risk")).not.toBeInTheDocument();
    expect(screen.queryByText("Production Kubernetes Cluster")).not.toBeInTheDocument();

    // Filter by module
    fireEvent.change(screen.getByTestId("review-bucket-filter"), { target: { value: "all" } });
    fireEvent.change(screen.getByTestId("review-source-filter"), { target: { value: "task" } });
    expect(screen.queryByText("Access Control Review")).not.toBeInTheDocument();
    expect(screen.getByText("Bi-Weekly Firewall Audit")).toBeInTheDocument();
  });

  it("navigates to the corresponding module and record upon click", () => {
    const navigateSpy = vi.fn();

    render(
      <I18nProvider>
        <ReviewCalendar
          tenantId="ten-1"
          token="token-abc"
          currentDate={baseDate}
          tasks={[sampleTask]}
          onNavigateToRecord={navigateSpy}
        />
      </I18nProvider>
    );

    const btn = screen.getByTestId("navigate-review-task-1");
    fireEvent.click(btn);

    expect(navigateSpy).toHaveBeenCalledWith("tasks", "task-1");
  });

  it("renders honest partial coverage notice when a module fails to load", () => {
    render(
      <I18nProvider>
        <ReviewCalendar
          tenantId="ten-1"
          token="token-abc"
          currentDate={baseDate}
          policies={[samplePolicy]}
          tasksError="500 Internal Server Error loading tasks"
        />
      </I18nProvider>
    );

    expect(screen.getByTestId("calendar-partial-coverage-notice")).toBeInTheDocument();
    expect(screen.getByText(/500 Internal Server Error loading tasks/i)).toBeInTheDocument();
  });
  it("renders honest partial coverage notice when tasks data is bounded / incomplete", () => {
    render(
      <I18nProvider>
        <ReviewCalendar
          tenantId="ten-1"
          token="token-abc"
          currentDate={baseDate}
          policies={[samplePolicy]}
          tasks={[sampleTask]}
          tasksComplete={false}
        />
      </I18nProvider>
    );

    expect(screen.getByTestId("calendar-partial-coverage-notice")).toBeInTheDocument();
    expect(screen.getByTestId("calendar-tasks-bounded-notice")).toBeInTheDocument();
    expect(screen.getByText(/Tasks review items reflect a bounded range/i)).toBeInTheDocument();
  });

  it("navigates with both source tab and source ID for nonfirst policies, risks, assets, vendors", () => {
    const navigateSpy = vi.fn();
    const policy2: Policy = { ...samplePolicy, id: "pol-2", title: "Second Policy Nonfirst" };
    const risk2: Risk = { ...sampleRisk, id: "risk-2", title: "Second Risk Nonfirst" };
    const asset2: Asset = { ...sampleAsset, id: "asset-2", name: "Second Asset Nonfirst" };
    const vendor2: Vendor = { ...sampleVendor, id: "vendor-2", name: "Second Vendor Nonfirst" };

    render(
      <I18nProvider>
        <ReviewCalendar
          tenantId="ten-1"
          token="token-abc"
          currentDate={baseDate}
          policies={[samplePolicy, policy2]}
          risks={[sampleRisk, risk2]}
          assets={[sampleAsset, asset2]}
          vendors={[sampleVendor, vendor2]}
          onNavigateToRecord={navigateSpy}
        />
      </I18nProvider>
    );

    // Click nonfirst policy
    fireEvent.click(screen.getByTestId("navigate-review-pol-2"));
    expect(navigateSpy).toHaveBeenCalledWith("policies", "pol-2");

    // Click nonfirst risk
    fireEvent.click(screen.getByTestId("navigate-review-risk-2"));
    expect(navigateSpy).toHaveBeenCalledWith("risks", "risk-2");

    // Click nonfirst asset
    fireEvent.click(screen.getByTestId("navigate-review-asset-2"));
    expect(navigateSpy).toHaveBeenCalledWith("assets", "asset-2");

    // Click nonfirst vendor
    fireEvent.click(screen.getByTestId("navigate-review-vendor-2"));
    expect(navigateSpy).toHaveBeenCalledWith("vendors", "vendor-2");
  });
});
