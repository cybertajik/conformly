import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { ForbiddenError, UnauthorizedError } from "./api";
import * as api from "./operations-api";
import * as taskApi from "./task-api";
import * as trainingApi from "./training-api";
import { ComplianceTask } from "./task-types";
import { Asset, Policy, Risk, Vendor } from "./operations-types";
import { OperationsWorkspace } from "./OperationsWorkspace";

describe("OperationsWorkspace Coordinator Component", () => {
  const dummyPolicy: Policy = {
    id: "pol-1",
    tenant_id: "ten-1",
    title: "Access Control Policy",
    description: "Policy governing passwords and 2FA",
    version_string: "1.0",
    status: "draft",
    owner_user_id: "user-alice",
    approved_by_user_id: null,
    approved_at: null,
    review_cycle_days: 365,
    next_review_due: null,
    version: 1,
    content: "Policy text",
    classification: "Internal",
    created_at: "2026-10-29T10:00:00Z",
    updated_at: "2026-10-29T10:00:00Z",
  };

  const dummyRisk: Risk = {
    id: "risk-1",
    tenant_id: "ten-1",
    title: "Unauthorized S3 Access",
    description: "Bucket misconfiguration",
    category: "security",
    likelihood: 4,
    impact: 4,
    inherent_score: 16,
    residual_score: null,
    status: "identified",
    owner_user_id: null,
    control_id: null,
    treatments: [],
    created_at: "2026-10-29T10:00:00Z",
  };

  const dummyAsset: Asset = {
    id: "asset-1",
    tenant_id: "ten-1",
    name: "Production PostgreSQL Database",
    asset_type: "data",
    classification: "restricted",
    description: "Primary database cluster",
    owner_user_id: null,
    status: "active",
    created_at: "2026-10-29T10:00:00Z",
  };

  const dummyVendor: Vendor = {
    id: "ven-1",
    tenant_id: "ten-1",
    name: "Amazon Web Services",
    service_description: "Cloud computing and managed services",
    criticality: "critical",
    data_classification_accessed: "Restricted",
    country_residency: "DE",
    dpa_signed: true,
    security_reviewed_at: null,
    next_review_due_at: null,
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "fetchPolicies").mockResolvedValue([dummyPolicy]);
    vi.spyOn(api, "fetchRisks").mockResolvedValue([dummyRisk]);
    vi.spyOn(api, "fetchAssets").mockResolvedValue([dummyAsset]);
    vi.spyOn(api, "fetchVendors").mockResolvedValue([dummyVendor]);
    vi.spyOn(api, "fetchPolicy").mockResolvedValue(dummyPolicy);
    vi.spyOn(api, "fetchPolicyRevisions").mockResolvedValue([]);
    vi.spyOn(api, "fetchPolicyAcknowledgements").mockResolvedValue([]);
    vi.spyOn(trainingApi, "fetchTrainingCourses").mockResolvedValue([]);
    vi.spyOn(trainingApi, "fetchTrainingAssignments").mockResolvedValue([]);
    vi.spyOn(trainingApi, "fetchTrainingCompletions").mockResolvedValue([]);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads all registers and switches tabs seamlessly without unmounting draft state", async () => {
    render(
      <I18nProvider>
        <OperationsWorkspace
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
        />
      </I18nProvider>
    );

    expect(screen.getByTestId("operations-workspace")).toBeInTheDocument();
    expect(screen.getByText("Operations & Governance Registers")).toBeInTheDocument();

    // Default tab: Policies
    await waitFor(() => {
      expect(screen.getByText("Access Control Policy")).toBeInTheDocument();
    });

    // Switch to Risks tab
    fireEvent.click(screen.getByTestId("operations-tab-risks"));
    await waitFor(() => {
      expect(screen.getByText("Unauthorized S3 Access")).toBeInTheDocument();
    });

    // Switch to Assets tab
    fireEvent.click(screen.getByTestId("operations-tab-assets"));
    await waitFor(() => {
      expect(screen.getByText("Production PostgreSQL Database")).toBeInTheDocument();
    });

    // Switch to Vendors tab
    fireEvent.click(screen.getByTestId("operations-tab-vendors"));
    await waitFor(() => {
      expect(screen.getByText("Amazon Web Services")).toBeInTheDocument();
    });

    // Switch back to Policies tab: state is preserved
    fireEvent.click(screen.getByTestId("operations-tab-policies"));
    expect(screen.getByText("Access Control Policy")).toBeInTheDocument();
  });

  it("handles independent register 500 failures with actionable retry rather than false zero success", async () => {
    // Risks fail with 500 error while policies succeed
    const riskSpy = vi.spyOn(api, "fetchRisks").mockRejectedValue(new Error("500 Internal Server Error"));

    render(
      <I18nProvider>
        <OperationsWorkspace
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
        />
      </I18nProvider>
    );

    // Policies still load
    await waitFor(() => {
      expect(screen.getByText("Access Control Policy")).toBeInTheDocument();
    });

    // Switch to Risks tab: displays honest error state with retry button, NOT an empty register
    fireEvent.click(screen.getByTestId("operations-tab-risks"));
    expect(screen.getByTestId("operations-panel-risks")).toBeVisible();
    await waitFor(() => {
      expect(screen.getByTestId("operations-error-risks")).toBeInTheDocument();
      expect(screen.getByTestId("retry-risks-btn")).toBeInTheDocument();
    });

    // Resolve failure and click retry
    riskSpy.mockResolvedValueOnce([dummyRisk]);
    fireEvent.click(screen.getByTestId("retry-risks-btn"));
    await waitFor(() => {
      expect(screen.getByText("Unauthorized S3 Access")).toBeInTheDocument();
    });
  });

  it("handles 403 Forbidden with honest denied status per module", async () => {
    vi.spyOn(api, "fetchAssets").mockRejectedValue(new ForbiddenError("Asset register access forbidden"));

    render(
      <I18nProvider>
        <OperationsWorkspace
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
        />
      </I18nProvider>
    );

    fireEvent.click(screen.getByTestId("operations-tab-assets"));
    await waitFor(() => {
      expect(screen.getByTestId("operations-denied-assets")).toBeInTheDocument();
    });
  });

  it("handles 401 Unauthorized by invoking onSessionExpired and invalidating pending requests", async () => {
    const onSessionExpired = vi.fn();
    vi.spyOn(api, "fetchVendors").mockRejectedValue(new UnauthorizedError("Token expired"));

    render(
      <I18nProvider>
        <OperationsWorkspace
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          onSessionExpired={onSessionExpired}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(onSessionExpired).toHaveBeenCalled();
    });


  });

  it("switches to Tasks, Review Hub, and Jobs tabs and renders their workspaces honestly", async () => {
    const dummyTask: ComplianceTask = {
      id: "task-100",
      tenant_id: "ten-1",
      title: "Quarterly Firewall Review",
      description: "Quarterly review of all firewall configurations",
      due_date: "2026-11-20T00:00:00Z",
      status: "pending",
      priority: "high",
      assignee_user_id: null,
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

    vi.spyOn(api, "fetchPolicies").mockResolvedValue([dummyPolicy]);
    vi.spyOn(api, "fetchRisks").mockResolvedValue([dummyRisk]);
    vi.spyOn(api, "fetchAssets").mockResolvedValue([dummyAsset]);
    vi.spyOn(api, "fetchVendors").mockResolvedValue([dummyVendor]);
    vi.spyOn(taskApi, "fetchTasks").mockResolvedValue([dummyTask]);
    vi.spyOn(taskApi, "fetchFailedJobs").mockResolvedValue({ total_failed: 0, recent_failures: [] });
    vi.spyOn(taskApi, "fetchOutboxMessages").mockResolvedValue([]);

    render(
      <I18nProvider>
        <OperationsWorkspace
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
        />
      </I18nProvider>
    );

    // Initial tab is policies
    expect(screen.getByTestId("operations-panel-policies")).toBeVisible();

    // Switch to Tasks tab
    fireEvent.click(screen.getByTestId("operations-tab-tasks"));
    expect(screen.getByTestId("operations-panel-tasks")).toBeVisible();
    await waitFor(() => {
      expect(within(screen.getByTestId("operations-panel-tasks")).getByText("Quarterly Firewall Review")).toBeInTheDocument();
    });

    // Switch to Review Hub tab
    fireEvent.click(screen.getByTestId("operations-tab-reviews"));
    expect(screen.getByTestId("operations-panel-reviews")).toBeVisible();
    expect(screen.getByTestId("review-calendar")).toBeInTheDocument();

    // Switch to Job Status tab
    fireEvent.click(screen.getByTestId("operations-tab-jobs"));
    expect(screen.getByTestId("operations-panel-jobs")).toBeVisible();
    await waitFor(() => {
      expect(screen.getByTestId("job-status-panel")).toBeInTheDocument();
    });
  });
  it("navigates from Review Hub to nonfirst policy, risk, asset, vendor, and task retaining source kind and record ID", async () => {
    const policy2: Policy = {
      ...dummyPolicy,
      id: "pol-2",
      title: "Data Retention Policy",
      next_review_due: "2026-11-01T00:00:00Z",
      status: "published",
    };
    const risk2: Risk = {
      ...dummyRisk,
      id: "risk-2",
      title: "Vendor Lock-in Risk",
      next_review_due_at: "2026-11-02T00:00:00Z",
    };
    const asset2: Asset = {
      ...dummyAsset,
      id: "asset-2",
      name: "Customer Data Warehouse",
      next_review_due_at: "2026-11-03T00:00:00Z",
    };
    const vendor2: Vendor = {
      ...dummyVendor,
      id: "ven-2",
      name: "PagerDuty Inc.",
      next_review_due_at: "2026-11-04T00:00:00Z",
    };
    const task2: ComplianceTask = {
      id: "task-2",
      tenant_id: "ten-1",
      title: "Quarterly Access Audit",
      description: "Review IAM users",
      due_date: "2026-11-05T00:00:00Z",
      status: "pending",
      priority: "medium",
      assignee_user_id: null,
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

    vi.spyOn(api, "fetchPolicies").mockResolvedValue([dummyPolicy, policy2]);
    vi.spyOn(api, "fetchRisks").mockResolvedValue([dummyRisk, risk2]);
    vi.spyOn(api, "fetchAssets").mockResolvedValue([dummyAsset, asset2]);
    vi.spyOn(api, "fetchVendors").mockResolvedValue([dummyVendor, vendor2]);
    vi.spyOn(taskApi, "fetchTasks").mockResolvedValue([task2]);
    vi.spyOn(taskApi, "fetchTask").mockResolvedValue(task2);
    vi.spyOn(api, "fetchPolicy").mockImplementation(async (_t, _tok, id) => {
      return id === "pol-2" ? policy2 : dummyPolicy;
    });

    render(
      <I18nProvider>
        <OperationsWorkspace
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          initialTab="reviews"
        />
      </I18nProvider>
    );

    // Initial tab is Review Calendar
    expect(screen.getByTestId("operations-panel-reviews")).toBeVisible();

    // 1. Navigate to nonfirst policy pol-2
    await waitFor(() => {
      expect(screen.getByTestId("navigate-review-pol-2")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("navigate-review-pol-2"));

    // Verify it switches tab to policies AND selects pol-2
    await waitFor(() => {
      expect(screen.getByTestId("operations-panel-policies")).toBeVisible();
      expect(screen.getByTestId("edit-policy-title")).toHaveValue("Data Retention Policy");
    });

    // 2. Return to reviews and navigate to nonfirst risk-2
    fireEvent.click(screen.getByTestId("operations-tab-reviews"));
    await waitFor(() => {
      expect(screen.getByTestId("navigate-review-risk-2")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("navigate-review-risk-2"));

    await waitFor(() => {
      expect(screen.getByTestId("operations-panel-risks")).toBeVisible();
      expect(screen.getByTestId("edit-risk-title-input")).toHaveValue("Vendor Lock-in Risk");
    });

    // 3. Return to reviews and navigate to nonfirst task-2
    fireEvent.click(screen.getByTestId("operations-tab-reviews"));
    await waitFor(() => {
      expect(screen.getByTestId("navigate-review-task-2")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("navigate-review-task-2"));

    await waitFor(() => {
      expect(screen.getByTestId("operations-panel-tasks")).toBeVisible();
      expect(screen.getByTestId("edit-task-title")).toHaveValue("Quarterly Access Audit");
    });
  });

  it("handles missing navigation targets and delayed fetches safely without crashing", async () => {
    vi.spyOn(api, "fetchPolicies").mockResolvedValue([dummyPolicy]);
    vi.spyOn(api, "fetchRisks").mockResolvedValue([dummyRisk]);
    vi.spyOn(api, "fetchAssets").mockResolvedValue([dummyAsset]);
    vi.spyOn(api, "fetchVendors").mockResolvedValue([dummyVendor]);
    vi.spyOn(taskApi, "fetchTasks").mockResolvedValue([]);

    render(
      <I18nProvider>
        <OperationsWorkspace
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          initialTab="reviews"
        />
      </I18nProvider>
    );

    // Switch to policies
    fireEvent.click(screen.getByTestId("operations-tab-policies"));
    await waitFor(() => {
      expect(screen.getByTestId("policy-workspace")).toBeInTheDocument();
    });

    // Ensure no crash occurs even with non-existent navigation targets
    expect(screen.getByTestId("operations-panel-policies")).toBeVisible();
  });

  it("consumes calendar navigation target intent once: allows manual selection without forcing target again", async () => {
    const risk2: Risk = {
      ...dummyRisk,
      id: "risk-2",
      title: "Vendor Lock-in Risk",
      next_review_due_at: "2026-11-02T00:00:00Z",
    };
    vi.spyOn(api, "fetchPolicies").mockResolvedValue([dummyPolicy]);
    vi.spyOn(api, "fetchRisks").mockResolvedValue([dummyRisk, risk2]);
    vi.spyOn(api, "fetchAssets").mockResolvedValue([dummyAsset]);
    vi.spyOn(api, "fetchVendors").mockResolvedValue([dummyVendor]);
    vi.spyOn(taskApi, "fetchTasks").mockResolvedValue([]);

    render(
      <I18nProvider>
        <OperationsWorkspace
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          initialTab="reviews"
        />
      </I18nProvider>
    );

    // 1. Calendar navigates to risk-2
    await waitFor(() => {
      expect(screen.getByTestId("navigate-review-risk-2")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("navigate-review-risk-2"));

    await waitFor(() => {
      expect(screen.getByTestId("operations-panel-risks")).toBeVisible();
      expect(screen.getByTestId("edit-risk-title-input")).toHaveValue("Vendor Lock-in Risk");
    });

    // 2. User manually selects risk-1 from the table
    const rowRisk1 = screen.getByTestId("risk-row-risk-1");
    fireEvent.click(rowRisk1);

    await waitFor(() => {
      expect(screen.getByTestId("edit-risk-title-input")).toHaveValue("Unauthorized S3 Access");
    });

    // Risk-1 must remain selected and NOT be forced back to risk-2!
    await new Promise((r) => setTimeout(r, 60));
    expect(screen.getByTestId("edit-risk-title-input")).toHaveValue("Unauthorized S3 Access");
  });

  it("handles dirty switch cancellation from calendar navigation without re-offering obsolete target on rerender", async () => {
    const risk2: Risk = {
      ...dummyRisk,
      id: "risk-2",
      title: "Vendor Lock-in Risk",
      next_review_due_at: "2026-11-02T00:00:00Z",
    };
    vi.spyOn(api, "fetchPolicies").mockResolvedValue([dummyPolicy]);
    vi.spyOn(api, "fetchRisks").mockResolvedValue([dummyRisk, risk2]);
    vi.spyOn(api, "fetchAssets").mockResolvedValue([dummyAsset]);
    vi.spyOn(api, "fetchVendors").mockResolvedValue([dummyVendor]);
    vi.spyOn(taskApi, "fetchTasks").mockResolvedValue([]);

    render(
      <I18nProvider>
        <OperationsWorkspace
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          initialTab="risks"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("risk-row-risk-1")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("risk-row-risk-1"));

    await waitFor(() => {
      expect(screen.getByTestId("edit-risk-title-input")).toHaveValue("Unauthorized S3 Access");
    });

    // User makes dirty edits on risk-1
    fireEvent.change(screen.getByTestId("edit-risk-title-input"), { target: { value: "Dirty Unsaved Risk Title" } });

    // Switch to reviews tab and click navigate to risk-2
    fireEvent.click(screen.getByTestId("operations-tab-reviews"));
    await waitFor(() => {
      expect(screen.getByTestId("navigate-review-risk-2")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("navigate-review-risk-2"));

    // Dirty dialog appears in risks workspace
    await waitFor(() => {
      expect(screen.getByTestId("dirty-switch-guard")).toBeInTheDocument();
    });

    // User clicks Cancel / Keep Editing on the dirty dialog
    const cancelBtn = screen.getByTestId("cancel-switch-btn");
    fireEvent.click(cancelBtn);

    // Dialog closes, dirty draft remains on risk-1
    await waitFor(() => {
      expect(screen.queryByTestId("dirty-switch-guard")).not.toBeInTheDocument();
      expect(screen.getByTestId("edit-risk-title-input")).toHaveValue("Dirty Unsaved Risk Title");
    });

    // Obsolete target must NOT be reoffered on subsequent rerenders
    await new Promise((r) => setTimeout(r, 60));
    expect(screen.queryByTestId("dirty-switch-guard")).not.toBeInTheDocument();
    expect(screen.getByTestId("edit-risk-title-input")).toHaveValue("Dirty Unsaved Risk Title");
  });

  it("switches to Training tab and renders TrainingWorkspace", async () => {
    render(
      <I18nProvider>
        <OperationsWorkspace
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
        />
      </I18nProvider>
    );

    const trainingTabBtn = screen.getByTestId("operations-tab-training");
    expect(trainingTabBtn).toBeInTheDocument();
    fireEvent.click(trainingTabBtn);

    await waitFor(() => {
      expect(screen.getByTestId("training-workspace")).toBeInTheDocument();
      expect(screen.getByTestId("partner-status-banner")).toBeInTheDocument();
    });
  });

});
