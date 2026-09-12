import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PreAuditWorkspace } from "./PreAuditWorkspace";

const { mockPreAudits, mockAdoptions, mockPreAuditDetail } = vi.hoisted(() => {
  const mockAdoptions = [
    {
      id: "adp-1",
      tenant_id: "t-1",
      framework_id: "fw-1",
      framework_version_id: "fv-1",
      status: "active",
      adopted_at: "2026-01-01T00:00:00Z",
      adopted_by_user_id: "u-1",
    },
  ];

  const mockPreAudits = [
    {
      id: "pa-1",
      tenant_id: "t-1",
      title: "SOC 2 Type II Readiness Assessment",
      description: "Pre-audit readiness check for Q4",
      status: "in_progress" as const,
      framework_adoption_id: "adp-1",
      lead_user_id: "u-lead",
      reviewer_user_id: null,
      reviewed_at: null,
      rule_version: "v1.0.0",
      overall_score: 0.85,
      version: 2,
      created_at: "2026-09-01T00:00:00Z",
      updated_at: "2026-09-01T00:00:00Z",
    },
  ];

  const mockPreAuditDetail = {
    id: "pa-1",
    tenant_id: "t-1",
    title: "SOC 2 Type II Readiness Assessment",
    description: "Pre-audit readiness check for Q4",
    status: "in_progress" as const,
    framework_adoption_id: "adp-1",
    lead_user_id: "u-lead",
    reviewer_user_id: null,
    reviewed_at: null,
    rule_version: "v1.0.0",
    overall_score: 0.85,
    version: 2,
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    scopes: [
      {
        id: "scope-1",
        tenant_id: "t-1",
        pre_audit_id: "pa-1",
        framework_version_id: "fv-1",
        control_count: 1,
        checked_count: 1,
        created_at: "2026-09-01T00:00:00Z",
      },
    ],
    checks: [
      {
        id: "chk-1",
        tenant_id: "t-1",
        scope_id: "scope-1",
        control_type: "canonical" as const,
        control_id: "ctrl-cc1-1",
        result: "pass" as const,
        rule_version: "v1.0.0",
        evidence_count: 2,
        policy_count: 1,
        open_findings_count: 0,
        implementation_status: "implemented" as const,
        score: 1.0,
        evaluated_at: "2026-09-01T00:00:00Z",
        created_at: "2026-09-01T00:00:00Z",
      },
    ],
    findings: [
      {
        id: "fnd-1",
        tenant_id: "t-1",
        pre_audit_id: "pa-1",
        check_id: null,
        title: "Missing Disaster Recovery Drill Evidence",
        description: "Annual failover test has not been executed",
        severity: "high" as const,
        recommendation: "Execute simulated database failover",
        remediation_status: "open" as const,
        version: 1,
        created_at: "2026-09-01T00:00:00Z",
        updated_at: "2026-09-01T00:00:00Z",
      },
    ],
    reports: [],
    manifests: [
      {
        id: "man-1",
        tenant_id: "t-1",
        pre_audit_id: "pa-1",
        file_id: "f-man-1",
        manifest_hash_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        record_count: 1,
        rule_version: "v1.0.0",
        generated_at: "2026-09-01T00:00:00Z",
        created_at: "2026-09-01T00:00:00Z",
      },
    ],
    certificates: [],
    score_summary: {
      overall_score: 0.85,
      total_checks: 1,
      passed_checks: 1,
      failed_checks: 0,
      not_applicable_checks: 0,
      pending_checks: 0,
      open_findings: 1,
    },
  };

  return { mockPreAudits, mockAdoptions, mockPreAuditDetail };
});

vi.mock("../api", () => ({
  listPreAudits: vi.fn().mockResolvedValue(mockPreAudits),
  listTenantAdoptions: vi.fn().mockResolvedValue(mockAdoptions),
  getPreAudit: vi.fn().mockResolvedValue(mockPreAuditDetail),
  runPreAuditChecks: vi.fn().mockResolvedValue(mockPreAuditDetail),
  createPreAudit: vi.fn().mockResolvedValue(mockPreAuditDetail),
  addPreAuditFinding: vi.fn().mockResolvedValue({}),
  updatePreAuditFinding: vi.fn().mockResolvedValue({}),
  submitPreAuditForReview: vi.fn().mockResolvedValue(mockPreAuditDetail),
  completePreAuditReview: vi.fn().mockResolvedValue(mockPreAuditDetail),
  cancelPreAudit: vi.fn().mockResolvedValue(mockPreAuditDetail),
  generatePreAuditReport: vi.fn().mockResolvedValue({}),
  generatePreAuditManifest: vi.fn().mockResolvedValue({}),
  issuePreAuditCertificate: vi.fn().mockResolvedValue({}),
  revokePreAuditCertificate: vi.fn().mockResolvedValue({}),
}));

vi.mock("../auth", () => ({
  getAccessToken: vi.fn().mockReturnValue("mock-token"),
}));

describe("PreAuditWorkspace", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders the pre-audit assessment list with deterministic compliance notice", async () => {
    render(
      <PreAuditWorkspace
        tenantId="t-1"
        userRole="compliance_manager"
        currentUserId="u-1"
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Pre-Audit Readiness Workspace")).toBeInTheDocument();
    });

    // Wording compliance: verify notice emphasizes pre-audit readiness, not certification body
    expect(screen.getByText(/Conformly is not an accredited certification body/i)).toBeInTheDocument();

    // Verify assessment item in table
    expect(screen.getByText("SOC 2 Type II Readiness Assessment")).toBeInTheDocument();
    expect(screen.getByText("85%")).toBeInTheDocument();
  });

  it("drills down into assessment detail view and switches tabs", async () => {
    render(
      <PreAuditWorkspace
        tenantId="t-1"
        userRole="compliance_manager"
        currentUserId="u-1"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("view-preaudit-pa-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("view-preaudit-pa-1"));

    await waitFor(() => {
      expect(screen.getByText("Readiness Dashboard")).toBeInTheDocument();
      expect(screen.getByText("Passed Checks")).toBeInTheDocument();
      expect(screen.getByText("Open Gaps / Findings")).toBeInTheDocument();
    });

    // Check tabs: Control Checks
    const checksTab = screen.getByRole("tab", { name: /Control Checks/i });
    fireEvent.click(checksTab);

    await waitFor(() => {
      expect(screen.getByTestId("checks-table")).toBeInTheDocument();
      expect(screen.getByText("Pass")).toBeInTheDocument();
    });

    // Check tabs: Gaps & Findings
    const findingsTab = screen.getByRole("tab", { name: /Gaps & Findings/i });
    fireEvent.click(findingsTab);

    await waitFor(() => {
      expect(screen.getByTestId("findings-table")).toBeInTheDocument();
      expect(screen.getByText("Missing Disaster Recovery Drill Evidence")).toBeInTheDocument();
    });
  });

  it("triggers deterministic check execution when clicking Run Checks", async () => {
    const { runPreAuditChecks } = await import("../api");

    render(
      <PreAuditWorkspace
        tenantId="t-1"
        userRole="compliance_manager"
        currentUserId="u-1"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("view-preaudit-pa-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("view-preaudit-pa-1"));

    await waitFor(() => {
      expect(screen.getByTestId("run-checks-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("run-checks-btn"));

    await waitFor(() => {
      expect(runPreAuditChecks).toHaveBeenCalledWith("mock-token", "t-1", "pa-1");
    });
  });

  it("disables administrative management actions for viewer role", async () => {
    render(
      <PreAuditWorkspace
        tenantId="t-1"
        userRole="viewer"
        currentUserId="u-viewer"
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Pre-Audit Readiness Workspace")).toBeInTheDocument();
    });

    // Viewer cannot see "+ New Readiness Assessment"
    expect(screen.queryByTestId("create-preaudit-btn")).not.toBeInTheDocument();
  });
});
