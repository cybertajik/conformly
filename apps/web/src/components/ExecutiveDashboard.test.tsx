import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ExecutiveDashboard } from "./ExecutiveDashboard";
import * as api from "../api";
import type { DashboardSummary } from "@conformly/shared";

const mockSummary: DashboardSummary = {
  readiness_score: 85,
  controls_summary: {
    total: 20,
    implemented: 17,
    in_progress: 2,
    not_started: 1,
  },
  frameworks_adopted: [
    {
      framework_id: "fw-iso",
      framework_name: "ISO/IEC 27001:2022",
      total_controls: 20,
      implemented_controls: 17,
      progress_percentage: 85,
    },
  ],
  expiring_evidence: [
    {
      id: "ev-1",
      title: "Annual SOC 2 Type II Report",
      classification: "Confidential",
      expires_at: "2026-09-25T00:00:00Z",
      days_remaining: 13,
    },
  ],
  review_due_policies: [
    {
      id: "pol-1",
      title: "Information Security Policy",
      review_due_at: "2026-09-28T00:00:00Z",
      days_remaining: 16,
    },
  ],
  open_tasks: [
    {
      id: "t-1",
      title: "Quarterly Access Review",
      priority: "critical",
      status: "pending",
      due_date: "2026-09-18T00:00:00Z",
    },
  ],
  top_risks: [
    {
      id: "r-1",
      title: "Ransomware on Backup Cluster",
      inherent_score: 20,
      residual_score: 8,
      status: "treated",
    },
  ],
  vendor_health: {
    total_vendors: 4,
    signed_dpa_count: 3,
    missing_dpa_count: 1,
    critical_vendors: 2,
  },
  recent_activity: [
    {
      id: "act-1",
      action: "evidence.upload",
      resource_type: "evidence_item",
      actor_type: "user",
      occurred_at: "2026-09-12T20:00:00Z",
    },
  ],
  is_administrator_view: false,
  admin_metrics: null,
};

describe("ExecutiveDashboard", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders live readiness metrics, controls progress, and action items", async () => {
    vi.spyOn(api, "getDashboardSummary").mockResolvedValue(mockSummary);
    const handleNavigate = vi.fn();

    render(
      <ExecutiveDashboard
        token="test-token"
        tenantId="t-123"
        tenantName="Acme Security"
        tenantSlug="acme-security"
        userRole="compliance_manager"
        onNavigate={handleNavigate}
      />
    );

    // Initial loading state
    expect(screen.getByText(/Aggregating live compliance posture/i)).toBeInTheDocument();

    // Wait for data load
    await waitFor(() => {
      expect(screen.getByText("85%")).toBeInTheDocument();
    });

    expect(screen.getByText("Audit Ready")).toBeInTheDocument();
    expect(screen.getByText("Acme Security")).toBeInTheDocument();
    expect(screen.getByText("ISO/IEC 27001:2022")).toBeInTheDocument();

    // Trigger pre-audit navigation
    const preauditBtn = screen.getByRole("button", { name: /Run Pre-Audit Check/i });
    fireEvent.click(preauditBtn);
    expect(handleNavigate).toHaveBeenCalledWith("preaudit");

    // Click Expiring tab
    const expiringTab = screen.getByRole("button", { name: /What Expires Next\?/i });
    fireEvent.click(expiringTab);

    expect(screen.getByText("Annual SOC 2 Type II Report")).toBeInTheDocument();
    expect(screen.getByText("Information Security Policy")).toBeInTheDocument();
    expect(screen.getByText("13 days")).toBeInTheDocument();
  });

  it("renders separation-of-duties view for Tenant Administrator", async () => {
    const adminSummary: DashboardSummary = {
      ...mockSummary,
      is_administrator_view: true,
      admin_metrics: {
        total_members: 5,
        legal_entities: 2,
        business_units: 3,
        locations: 2,
        storage_bytes_used: 1048576,
        max_storage_bytes: 10737418240,
        plan_code: "tier_a",
        enabled_modules: ["organization", "frameworks"],
      },
    };

    vi.spyOn(api, "getDashboardSummary").mockResolvedValue(adminSummary);

    render(
      <ExecutiveDashboard
        token="test-token"
        tenantId="t-123"
        tenantName="Acme Security"
        tenantSlug="acme-security"
        userRole="administrator"
        onNavigate={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Tenant Administrator Separation of Duties/i)
      ).toBeInTheDocument();
    });

    expect(screen.getByText("Active Members")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("TIER_A")).toBeInTheDocument();
  });

  it("triggers continuous compliance check and displays results banner", async () => {
    vi.spyOn(api, "getDashboardSummary").mockResolvedValue(mockSummary);
    const mockCycleResult = {
      tenant_id: "t-123",
      expired_evidence_count: 1,
      expiring_evidence_warnings: 2,
      overdue_tasks_escalated: 1,
      policy_reviews_due: 1,
      vendor_reviews_due: 1,
      missing_dpas_flagged: 1,
      tasks_created: 3,
      notifications_enqueued: 4,
      executed_at: "2026-09-12T22:00:00Z",
    };
    const cycleSpy = vi
      .spyOn(api, "runContinuousComplianceCycle")
      .mockResolvedValue(mockCycleResult);

    render(
      <ExecutiveDashboard
        token="test-token"
        tenantId="t-123"
        tenantName="Acme Security"
        tenantSlug="acme-security"
        userRole="compliance_manager"
        onNavigate={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("85%")).toBeInTheDocument();
    });

    const runBtn = screen.getByRole("button", { name: /Run Continuous Check/i });
    expect(runBtn).toBeInTheDocument();
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(cycleSpy).toHaveBeenCalledWith("test-token", "t-123");
    });

    await waitFor(() => {
      expect(
        screen.getByText(/Continuous Compliance Evaluation Completed/i)
      ).toBeInTheDocument();
    });

    expect(
      screen.getByText(/3 remediation task\(s\) created/i)
    ).toBeInTheDocument();
  });
});

