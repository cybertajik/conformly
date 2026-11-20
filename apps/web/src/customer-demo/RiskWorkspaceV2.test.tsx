import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import * as api from "./operations-api";
import { Risk, RiskTreatment } from "./operations-types";
import { RiskWorkspaceV2 } from "./RiskWorkspaceV2";

describe("RiskWorkspaceV2 Component", () => {
  const dummyTreatment: RiskTreatment = {
    id: "treat-1",
    strategy: "mitigate",
    treatment_plan: "Implement MFA everywhere",
    target_date: "2026-12-31",
    status: "planned",
    owner_user_id: null,
    created_at: "2026-10-29T10:00:00Z",
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
    treatments: [dummyTreatment],
    last_reviewed_at: null,
    next_review_due_at: null,
    created_at: "2026-10-29T10:00:00Z",
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders risk register and filters by category", () => {
    const operationalRisk: Risk = {
      ...dummyRisk,
      id: "risk-2",
      title: "Datacenter Power Outage",
      category: "operational",
      inherent_score: 9,
    };

    render(
      <I18nProvider>
        <RiskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          risks={[dummyRisk, operationalRisk]}
        />
      </I18nProvider>
    );

    expect(screen.getByTestId("risk-workspace")).toBeInTheDocument();
    expect(screen.getByText("Unauthorized S3 Access")).toBeInTheDocument();
    expect(screen.getByText("Datacenter Power Outage")).toBeInTheDocument();

    // Filter by security
    fireEvent.change(screen.getByTestId("risk-category-filter"), { target: { value: "security" } });
    expect(screen.getByText("Unauthorized S3 Access")).toBeInTheDocument();
    expect(screen.queryByText("Datacenter Power Outage")).not.toBeInTheDocument();
  });

  it("handles risk creation, update, and review recording", async () => {
    const onRiskCreated = vi.fn();
    const onRiskMutated = vi.fn();

    vi.spyOn(api, "createRisk").mockResolvedValue({
      ...dummyRisk,
      id: "risk-new",
      title: "New Phishing Risk",
      inherent_score: 12,
    });

    render(
      <I18nProvider>
        <RiskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="owner"
          risks={[dummyRisk]}
          onRiskCreated={onRiskCreated}
          onRiskMutated={onRiskMutated}
        />
      </I18nProvider>
    );

    // Open create form
    fireEvent.click(screen.getByTestId("new-risk-btn"));
    fireEvent.change(screen.getByTestId("new-risk-title-input"), {
      target: { value: "New Phishing Risk" },
    });
    fireEvent.click(screen.getByTestId("submit-create-risk-btn"));

    await waitFor(() => {
      expect(onRiskCreated).toHaveBeenCalled();
    });

    // Select existing risk
    fireEvent.click(screen.getByTestId("risk-row-risk-1"));
    expect(screen.getByTestId("detail-inherent-score")).toHaveTextContent("16");

    // Edit and save
    vi.spyOn(api, "updateRisk").mockResolvedValue({
      ...dummyRisk,
      status: "assessed",
      residual_score: 8,
    });

    fireEvent.change(screen.getByTestId("edit-risk-status-select"), {
      target: { value: "assessed" },
    });
    fireEvent.click(screen.getByTestId("save-risk-draft-btn"));

    await waitFor(() => {
      expect(onRiskMutated).toHaveBeenCalled();
    });

    // Record review
    vi.spyOn(api, "reviewRisk").mockResolvedValue({
      ...dummyRisk,
      last_reviewed_at: "2026-10-29T12:00:00Z",
    });

    fireEvent.click(screen.getByTestId("review-risk-btn"));
    await waitFor(() => {
      expect(onRiskMutated).toHaveBeenCalled();
      expect(screen.getByTestId("risk-action-success")).toHaveTextContent(/review recorded/i);
    });
  });

  it("handles adding treatment plan to risk", async () => {
    const onRiskMutated = vi.fn();
    const newTreatment: RiskTreatment = {
      id: "treat-2",
      strategy: "mitigate",
      treatment_plan: "Deploy CloudTrail Alerts",
      target_date: "2026-11-30",
      status: "planned",
      owner_user_id: null,
      created_at: "2026-10-29T12:00:00Z",
    };

    vi.spyOn(api, "createRiskTreatment").mockResolvedValue(newTreatment);

    render(
      <I18nProvider>
        <RiskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          risks={[dummyRisk]}
          onRiskMutated={onRiskMutated}
        />
      </I18nProvider>
    );

    fireEvent.click(screen.getByTestId("risk-row-risk-1"));
    expect(screen.getByText(/Implement MFA everywhere/i)).toBeInTheDocument();

    // Open add treatment subform
    fireEvent.click(screen.getByTestId("open-add-treatment-btn"));
    expect(screen.getByTestId("add-treatment-form")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("treat-plan-input"), {
      target: { value: "Deploy CloudTrail Alerts" },
    });
    fireEvent.click(screen.getByTestId("submit-treatment-btn"));

    await waitFor(() => {
      expect(onRiskMutated).toHaveBeenCalled();
      expect(screen.getByTestId("risk-action-success")).toHaveTextContent(/Treatment plan added/i);
    });
  });

  describe("B04 Repair 2 Risk Regressions", () => {
    it("Priority 3: Guarded risk switch on dirty draft keeps draft on cancel and switches on confirm", async () => {
      const riskTwo: Risk = {
        ...dummyRisk,
        id: "risk-2",
        title: "DDoS on DNS Servers",
      };

      render(
        <I18nProvider>
          <RiskWorkspaceV2
            tenantId="ten-1"
            token="token-abc"
            userRole="compliance_manager"
            risks={[dummyRisk, riskTwo]}
          />
        </I18nProvider>
      );

      // Select risk-1
      fireEvent.click(screen.getByTestId("risk-row-risk-1"));
      expect(screen.getByTestId("edit-risk-status-select")).toHaveValue("identified");

      // Make dirty edit
      fireEvent.change(screen.getByTestId("edit-risk-status-select"), {
        target: { value: "assessed" },
      });

      // Click risk-2
      fireEvent.click(screen.getByTestId("risk-row-risk-2"));

      // Dirty guard banner must appear
      expect(screen.getByTestId("dirty-switch-guard")).toBeInTheDocument();
      expect(screen.getByTestId("edit-risk-status-select")).toHaveValue("assessed");

      // Cancel keeps draft
      fireEvent.click(screen.getByTestId("cancel-switch-btn"));
      expect(screen.queryByTestId("dirty-switch-guard")).not.toBeInTheDocument();
      expect(screen.getByTestId("edit-risk-status-select")).toHaveValue("assessed");

      // Click risk-2 again and confirm discard
      fireEvent.click(screen.getByTestId("risk-row-risk-2"));
      expect(screen.getByTestId("dirty-switch-guard")).toBeInTheDocument();
      fireEvent.click(screen.getByTestId("confirm-discard-switch-btn"));

      // Switched to risk-2
      expect(screen.getAllByText("DDoS on DNS Servers").length).toBeGreaterThanOrEqual(1);
    });

    it("Priority 4: Uncertain create disables submit; full payload match allows adopting record", async () => {
      vi.spyOn(api, "createRisk").mockRejectedValue(new TypeError("Network error"));
      vi.spyOn(api, "fetchRisks").mockResolvedValue([
        {
          ...dummyRisk,
          id: "risk-reconciled",
          title: "API Rate Limiting Failure",
          description: "Missing throttle controls",
          category: "operational",
        },
      ]);

      render(
        <I18nProvider>
          <RiskWorkspaceV2
            tenantId="ten-1"
            token="token-abc"
            userRole="compliance_manager"
            risks={[]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("new-risk-btn"));
      fireEvent.change(screen.getByTestId("new-risk-title-input"), {
        target: { value: "API Rate Limiting Failure" },
      });
      fireEvent.change(screen.getByTestId("new-risk-desc-input"), {
        target: { value: "Missing throttle controls" },
      });
      fireEvent.change(screen.getByTestId("new-risk-category-select"), {
        target: { value: "operational" },
      });

      fireEvent.click(screen.getByTestId("submit-create-risk-btn"));

      // Uncertain banner appears and submit is disabled
      await waitFor(() => {
        expect(screen.getByTestId("risk-uncertain-banner")).toBeInTheDocument();
        expect(screen.getByTestId("submit-create-risk-btn")).toBeDisabled();
      });

      // Reconcile with server
      fireEvent.click(screen.getByTestId("check-reconcile-risk-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("confirm-reconciled-risk-btn")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("confirm-reconciled-risk-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("risk-action-success")).toHaveTextContent(/verified as created|reconciled/i);
      });
    });

    it("Priority 4: Uncertain create with no server match allows acknowledge & resubmit or abandon draft", async () => {
      vi.spyOn(api, "createRisk").mockRejectedValue(new TypeError("Network error"));
      vi.spyOn(api, "fetchRisks").mockResolvedValue([]);

      render(
        <I18nProvider>
          <RiskWorkspaceV2
            tenantId="ten-1"
            token="token-abc"
            userRole="compliance_manager"
            risks={[]}
          />
        </I18nProvider>
      );

      fireEvent.click(screen.getByTestId("new-risk-btn"));
      fireEvent.change(screen.getByTestId("new-risk-title-input"), {
        target: { value: "Unique Risk Title" },
      });

      fireEvent.click(screen.getByTestId("submit-create-risk-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("risk-uncertain-banner")).toBeInTheDocument();
      });

      // Check server - returns empty list (no match)
      fireEvent.click(screen.getByTestId("check-reconcile-risk-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("force-resubmit-btn")).toBeInTheDocument();
      });

      // Acknowledge uncertainty allows submit button again
      fireEvent.click(screen.getByTestId("force-resubmit-btn"));

      expect(screen.queryByTestId("risk-uncertain-banner")).not.toBeInTheDocument();
      expect(screen.getByTestId("submit-create-risk-btn")).not.toBeDisabled();
    });

    it("fences late updateRisk mutation against another record's dirty drafts", async () => {
      const secondRisk: Risk = {
        ...dummyRisk,
        id: "risk-2",
        title: "Vendor Dependency Risk",
      };
      let resolveUpdate: (val: Risk) => void = () => {};
      const pendingPromise = new Promise((res) => {
        resolveUpdate = res;
      });
      vi.spyOn(api, "updateRisk").mockImplementation(() => pendingPromise as Promise<Risk>);

      render(
        <I18nProvider>
          <RiskWorkspaceV2
            tenantId="ten-1"
            token="token-abc"
            userRole="compliance_manager"
            risks={[dummyRisk, secondRisk]}
          />
        </I18nProvider>
      );

      // Select risk 1 and make edit
      fireEvent.click(screen.getByTestId("risk-row-risk-1"));
      fireEvent.change(screen.getByTestId("edit-risk-title-input"), {
        target: { value: "Risk 1 Updated" },
      });

      // Click save - request is inflight
      fireEvent.click(screen.getByTestId("save-risk-draft-btn"));

      // Force select risk 2
      fireEvent.click(screen.getByTestId("risk-row-risk-2"));
      // Confirm switch if dirty switch modal appears
      if (screen.queryByTestId("confirm-discard-switch-btn")) {
        fireEvent.click(screen.getByTestId("confirm-discard-switch-btn"));
      }

      await waitFor(() => {
        expect(screen.getByTestId("edit-risk-title-input")).toHaveValue("Vendor Dependency Risk");
      });

      // Type dirty changes on risk 2
      fireEvent.change(screen.getByTestId("edit-risk-title-input"), {
        target: { value: "Risk 2 Dirty Draft In Progress" },
      });

      // Now inflight mutation for risk 1 resolves late
      resolveUpdate({
        ...dummyRisk,
        title: "Risk 1 Updated",
      });

      // Allow microtasks to run and actionLoading to clear
      await waitFor(() => {
        expect(screen.getByTestId("save-risk-draft-btn")).not.toBeDisabled();
      });

      // Assert risk 2 dirty draft was NOT wiped or marked clean by late risk 1 mutation
      expect(screen.getByTestId("edit-risk-title-input")).toHaveValue("Risk 2 Dirty Draft In Progress");
    });
  });
});
