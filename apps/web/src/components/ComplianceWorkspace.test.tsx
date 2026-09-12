import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  canManageControlStatus,
  canManageEvidence,
  canManageFindings,
  canManagePolicies,
  canManageTasks,
  canReadEvidence,
  canReadPolicies,
} from "../permissions";
import { ComplianceWorkspace } from "./ComplianceWorkspace";

const {
  mockFrameworks,
  mockAdoptions,
  mockCustomControls,
  mockVersionDetails,
  mockControlStatuses,
  mockEvidence,
  mockPolicies,
  mockTasks,
  mockFindings,
  mockUserPrefs,
  mockJobsResult,
} = vi.hoisted(() => {
  const mockFrameworks = [
    {
      id: "fw-1",
      name: "ISO/IEC 27001",
      slug: "iso-27001",
      description: "InfoSec standard",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      versions: [],
    },
  ];

  const mockAdoptions = [
    {
      id: "adp-1",
      tenant_id: "t-1",
      framework_id: "fw-1",
      framework_version_id: "v-1",
      status: "active",
      adopted_at: "2026-01-01T00:00:00Z",
      adopted_by_user_id: "u-1",
    },
  ];

  const mockCustomControls = [
    {
      id: "cc-1",
      tenant_id: "t-1",
      identifier: "CUST-SEC-01",
      title: "Database Encryption at Rest",
      description: "AES-256 encryption required for DB volumes",
      category: "Technical",
      status: "active",
      created_at: "2026-01-01T00:00:00Z",
    },
  ];

  const mockVersionDetails = {
    id: "v-1",
    framework_id: "fw-1",
    version: "2022",
    release_state: "released",
    created_by_user_id: "u-admin",
    created_at: "2026-01-01T00:00:00Z",
    controls: [
      {
        id: "ctrl-iso-1",
        framework_version_id: "v-1",
        identifier: "A.5.1",
        title: "Policies for information security",
        description: "Security policy documentation",
        category: "Organizational",
        sort_order: 1,
        created_at: "2026-01-01T00:00:00Z",
      },
    ],
  };

  const mockControlStatuses = [
    {
      id: "cs-1",
      tenant_id: "t-1",
      control_type: "canonical",
      control_id: "ctrl-iso-1",
      status: "implemented",
      assigned_owner_user_id: "u-sec",
      notes: "Verified in Q3 audit",
      version: 1,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
  ];

  const mockEvidence = [
    {
      id: "ev-1",
      tenant_id: "t-1",
      title: "AWS VPC Security Group Configuration",
      description: "Terraform export and automated drift check results",
      classification: "Restricted" as const,
      status: "valid" as const,
      version: 1,
      owner_user_id: "u-author",
      valid_from: "2026-01-01T00:00:00Z",
      valid_until: "2027-01-01T00:00:00Z",
      restricted_notes: "Bastion host internal IP omitted",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      file_links: [],
      control_links: [],
    },
  ];

  const mockPolicies = [
    {
      id: "pol-1",
      tenant_id: "t-1",
      title: "Access Control & Password Policy",
      description: "MFA and password rotation rules",
      version_string: "1.0",
      version: 1,
      status: "in_review" as const,
      review_cycle_days: 365,
      next_review_due: "2027-01-01T00:00:00Z",
      owner_user_id: "u-author",
      classification: "Internal" as const,
      content: "All users must have MFA enabled.",
      restricted_content: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      control_links: [],
    },
  ];

  const mockTasks = [
    {
      id: "tsk-1",
      tenant_id: "t-1",
      title: "Quarterly Access Review",
      description: "Review IAM roles and offboarded contractors",
      status: "pending" as const,
      priority: "high" as const,
      due_date: "2026-10-01T00:00:00Z",
      assignee_user_id: "u-sec",
      version: 1,
      control_type: null,
      control_id: null,
      evidence_id: null,
      policy_id: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
  ];

  const mockFindings = [
    {
      id: "fnd-1",
      tenant_id: "t-1",
      title: "Overly Permissive S3 Bucket Policy",
      description: "Bucket permits public read access",
      severity: "critical" as const,
      remediation_status: "open" as const,
      due_date: "2026-09-30T00:00:00Z",
      owner_user_id: "u-sec",
      remediation_plan: "Apply restrictive bucket policy",
      remediation_summary: null,
      version: 1,
      control_type: null,
      control_id: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
  ];

  const mockUserPrefs = {
    id: "pref-1",
    tenant_id: "t-1",
    user_id: "u-me",
    email_enabled: true,
    digest_frequency: "daily" as const,
    notify_task_assigned: true,
    notify_task_due: true,
    notify_evidence_expired: true,
    notify_policy_review: true,
    notify_finding_raised: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };

  const mockJobsResult = {
    expired_evidence: { processed_count: 5, alerts_enqueued: 1 },
    overdue_tasks: { processed_count: 8, alerts_enqueued: 2 },
    policy_alerts: { processed_count: 3, alerts_enqueued: 1 },
  };

  return {
    mockFrameworks,
    mockAdoptions,
    mockCustomControls,
    mockVersionDetails,
    mockControlStatuses,
    mockEvidence,
    mockPolicies,
    mockTasks,
    mockFindings,
    mockUserPrefs,
    mockJobsResult,
  };
});

vi.mock("../api", () => ({
  listCanonicalFrameworks: vi.fn().mockResolvedValue(mockFrameworks),
  listTenantAdoptions: vi.fn().mockResolvedValue(mockAdoptions),
  listCustomControls: vi.fn().mockResolvedValue(mockCustomControls),
  getCanonicalVersionDetails: vi.fn().mockResolvedValue(mockVersionDetails),
  listControlStatuses: vi.fn().mockResolvedValue(mockControlStatuses),
  listEvidence: vi.fn().mockResolvedValue(mockEvidence),
  listPolicies: vi.fn().mockResolvedValue(mockPolicies),
  listTasks: vi.fn().mockResolvedValue(mockTasks),
  listFindings: vi.fn().mockResolvedValue(mockFindings),
  getUserPreferences: vi.fn().mockResolvedValue(mockUserPrefs),
  updateUserPreferences: vi.fn().mockResolvedValue(mockUserPrefs),
  upsertControlStatus: vi.fn().mockResolvedValue({
    ...mockControlStatuses[0],
    status: "assessed",
    version: 2,
  }),
  createEvidence: vi.fn(),
  updateEvidence: vi.fn(),
  transitionEvidence: vi.fn(),
  attachFileToEvidence: vi.fn(),
  removeFileFromEvidence: vi.fn(),
  linkControlToEvidence: vi.fn(),
  unlinkControlFromEvidence: vi.fn(),
  createPolicy: vi.fn(),
  updatePolicy: vi.fn(),
  submitPolicyReview: vi.fn(),
  approvePolicy: vi.fn(),
  publishPolicy: vi.fn(),
  archivePolicy: vi.fn(),
  linkControlToPolicy: vi.fn(),
  unlinkControlFromPolicy: vi.fn(),
  createTask: vi.fn(),
  updateTask: vi.fn(),
  completeTask: vi.fn().mockResolvedValue({
    ...mockTasks[0],
    status: "completed",
    version: 2,
  }),
  createFinding: vi.fn(),
  updateFinding: vi.fn(),
  remediateFinding: vi.fn(),
  runComplianceJobs: vi.fn().mockResolvedValue(mockJobsResult),
}));

vi.mock("../auth", () => ({
  getAccessToken: vi.fn().mockReturnValue("mock-access-token"),
}));

describe("ComplianceWorkspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders workspace header, posture metrics, and controls matrix", async () => {
    render(
      <ComplianceWorkspace
        tenantId="t-1"
        userRole="compliance_manager"
        currentUserId="u-me"
      />
    );

    expect(await screen.findByRole("heading", { name: "Compliance Workspace" })).toBeInTheDocument();
    expect(screen.getByText("Control Posture Matrix (2)")).toBeInTheDocument();
    expect(screen.getByText("A.5.1")).toBeInTheDocument();
    expect(screen.getByText("Policies for information security")).toBeInTheDocument();
    expect(screen.getByText("CUST-SEC-01")).toBeInTheDocument();
    expect(screen.getByText("Database Encryption at Rest")).toBeInTheDocument();
    expect(screen.getByText("Readiness Score")).toBeInTheDocument();
  });

  it("switches to Evidence Repository and displays evidence items", async () => {
    render(
      <ComplianceWorkspace
        tenantId="t-1"
        userRole="compliance_manager"
        currentUserId="u-me"
      />
    );

    const evidenceTab = await screen.findByRole("tab", { name: /Evidence Repository/i });
    fireEvent.click(evidenceTab);

    expect(await screen.findByText("AWS VPC Security Group Configuration")).toBeInTheDocument();
    expect(screen.getByText("Restricted")).toBeInTheDocument();
    expect(screen.getByText("valid")).toBeInTheDocument();
  });

  it("switches to Policy Center and displays versioned policies", async () => {
    render(
      <ComplianceWorkspace
        tenantId="t-1"
        userRole="compliance_manager"
        currentUserId="u-me"
      />
    );

    const policyTab = await screen.findByRole("tab", { name: /Policy Center/i });
    fireEvent.click(policyTab);

    expect(await screen.findByText("Access Control & Password Policy")).toBeInTheDocument();
    expect(screen.getByText("v1.0 (rev 1)")).toBeInTheDocument();
    expect(screen.getByText("in review")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Approve \(2-Person\)/i })).toBeInTheDocument();
  });

  it("enforces independent 2-person approval rule: author cannot approve own policy", async () => {
    render(
      <ComplianceWorkspace
        tenantId="t-1"
        userRole="compliance_manager"
        currentUserId="u-author" // Same as policy owner_user_id
      />
    );

    const policyTab = await screen.findByRole("tab", { name: /Policy Center/i });
    fireEvent.click(policyTab);

    const approveBtn = await screen.findByRole("button", { name: /Approve \(2-Person\)/i });
    fireEvent.click(approveBtn);

    expect(
      await screen.findByText(/Independent 2-Person Approval Required/i)
    ).toBeInTheDocument();
  });

  it("switches to Tasks and completes a task", async () => {
    render(
      <ComplianceWorkspace
        tenantId="t-1"
        userRole="compliance_manager"
        currentUserId="u-me"
      />
    );

    const tasksTab = await screen.findByRole("tab", { name: /Tasks & Actions/i });
    fireEvent.click(tasksTab);

    expect(await screen.findByText("Quarterly Access Review")).toBeInTheDocument();
    const completeBtn = screen.getByRole("button", { name: /Mark Complete/i });
    fireEvent.click(completeBtn);

    await waitFor(() => {
      expect(screen.getByText(/marked as completed/i)).toBeInTheDocument();
    });
  });

  it("switches to Deterministic Automation and executes checks", async () => {
    render(
      <ComplianceWorkspace
        tenantId="t-1"
        userRole="compliance_manager"
        currentUserId="u-me"
      />
    );

    const autoTab = await screen.findByRole("tab", { name: /Preferences & Deterministic Automation/i });
    fireEvent.click(autoTab);

    expect(await screen.findByRole("heading", { name: "Deterministic Automation Jobs" })).toBeInTheDocument();
    const runBtn = screen.getByRole("button", { name: /Run Compliance Checks Now/i });
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByText(/Deterministic jobs executed successfully/i)).toBeInTheDocument();
      expect(screen.getByText("Last Run Summary:")).toBeInTheDocument();
      expect(screen.getByText("Total Notifications Queued:")).toBeInTheDocument();
    });
  });

  it("checks role permissions for compliance capabilities accurately", () => {
    expect(canReadEvidence("viewer")).toBe(true);
    expect(canReadEvidence("auditor")).toBe(true);
    expect(canManageEvidence("contributor")).toBe(true);
    expect(canManageEvidence("compliance_manager")).toBe(true);
    expect(canManageEvidence("auditor")).toBe(false);

    expect(canReadPolicies("viewer")).toBe(true);
    expect(canManagePolicies("compliance_manager")).toBe(true);
    expect(canManagePolicies("contributor")).toBe(false);

    expect(canManageTasks("contributor")).toBe(true);
    expect(canManageTasks("auditor")).toBe(false);

    expect(canManageFindings("contributor")).toBe(true);
    expect(canManageFindings("viewer")).toBe(false);

    expect(canManageControlStatus("compliance_manager")).toBe(true);
    expect(canManageControlStatus("contributor")).toBe(false);
  });
});
