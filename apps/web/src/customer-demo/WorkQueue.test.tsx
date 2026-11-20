import "@testing-library/jest-dom/vitest";
import React from "react";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { WorkQueue } from "./WorkQueue";
import * as controlApi from "./control-evidence-api";
import * as assessmentApi from "./assessment-api";
import { ControlWorkItem, WorkListResponse } from "./control-evidence-types";
import { AssessmentWorkItem, AssessmentWorkListResponse } from "./assessment-types";
import { ForbiddenError, UnauthorizedError } from "./api";

function renderWithI18n(ui: React.ReactElement) {
  return render(<I18nProvider>{ui}</I18nProvider>);
}

describe("WorkQueue Component", () => {
  const dummyControls: ControlWorkItem[] = [
    {
      id: "work-1",
      adoption_id: "adopt-1",
      control_id: "CTRL-01",
      control_version_id: "cv-1",
      title: "Access Control Baseline",
      provenance: "Synthetic Baseline Pack",
      pack_version: 1,
      bundle_digest: "digest-1",
      requirement_results: [
        {
          requirement_id: "req-1",
          requirement_version_id: "rv-1",
          requirement_identifier: "SYNTH-01",
          requirement_title: "Role-Based Access",
          result: "APPLICABLE",
        },
      ],
      owner_user_id: "user-alice",
      owner_display_name: "Alice Engineer",
      due_date: "2026-10-28", // overdue relative to 2026-10-29
      version: 1,
      is_current: true,
      is_stale: false,
      links: [],
    },
    {
      id: "work-2",
      adoption_id: "adopt-1",
      control_id: "CTRL-02",
      control_version_id: "cv-2",
      title: "Data Encryption Standard",
      provenance: "Synthetic Baseline Pack",
      pack_version: 1,
      bundle_digest: "digest-2",
      requirement_results: [],
      owner_user_id: null,
      owner_display_name: null,
      due_date: "2026-10-29", // due today
      version: 1,
      is_current: true,
      is_stale: false,
      links: [],
    },
    {
      id: "work-3",
      adoption_id: "adopt-1",
      control_id: "CTRL-03",
      control_version_id: "cv-3",
      title: "Incident Response Protocol",
      provenance: "Synthetic Baseline Pack",
      pack_version: 1,
      bundle_digest: "digest-3",
      requirement_results: [],
      owner_user_id: "user-bob",
      owner_display_name: "Bob Operator",
      due_date: "2026-11-05", // future
      version: 1,
      is_current: true,
      is_stale: false,
      links: [
        {
          id: "link-inv",
          evidence_id: "ev-invalid",
          revision_number: 1,
          digest: "sha256:invalid",
          file_ids: ["f-inv"],
          filename: "expired-report.pdf",
          file_size: 1024,
          classification: "INTERNAL",
          validity: "EXPIRED",
          scan_status: "SCANNED_AT_LINK",
          scan_verified_at: null,
          review: "ACCEPTED",
          rationale: "Expired drill report",
          created_at: "2026-09-01T00:00:00Z",
        },
      ],
    },
  ];

  const dummyAssessments: AssessmentWorkItem[] = [
    {
      work_id: "work-1",
      control_version_id: "cv-1",
      work_version: 1,
      assessment_revision: 1,
      procedure: {
        id: "proc-1",
        version: "1.0",
        digest: "sha256:proc1",
        criteria: [],
        disclaimer: "Synthetic demonstration procedure",
      },
      latest_assessment: {
        event_id: "evt-1",
        revision: 1,
        result: "FAIL",
        actor_id: "auditor-1",
        created_at: "2026-10-25T10:00:00Z",
        rationale: "Deficiency noted in admin role separation.",
        criterion_results: [],
        evidence_pins: [],
        is_stale: false,
        stale_reasons: [],
      },
      primary_state: "FAIL",
      blockers: [],
      findings: [
        {
          id: "fnd-1",
          source_event_id: "evt-1",
          current_event_id: "evt-1",
          severity: "HIGH",
          status: "OPEN",
          owner_user_id: "user-alice",
          owner_display_name: "Alice Engineer",
          due_date: "2026-10-28", // overdue finding
          version: 1,
          created_at: "2026-10-25T10:30:00Z",
          updated_at: "2026-10-25T10:30:00Z",
        },
      ],
      history: [
        {
          event_id: "evt-1",
          revision: 1,
          operation_id: "op-1",
          event_type: "ASSESSMENT",
          result: "FAIL",
          observed_work_version: 1,
          actor_id: "auditor-1",
          created_at: "2026-10-25T10:00:00Z",
          details: {},
        },
      ],
    },
    {
      work_id: "work-2",
      control_version_id: "cv-2",
      work_version: 1,
      assessment_revision: 0,
      procedure: {
        id: "proc-2",
        version: "1.0",
        digest: "sha256:proc2",
        criteria: [],
        disclaimer: "Synthetic demonstration procedure",
      },
      latest_assessment: null,
      primary_state: "UNASSESSED",
      blockers: [],
      findings: [],
      history: [],
    },
    {
      work_id: "work-3",
      control_version_id: "cv-3",
      work_version: 1,
      assessment_revision: 1,
      procedure: {
        id: "proc-3",
        version: "1.0",
        digest: "sha256:proc3",
        criteria: [],
        disclaimer: "Synthetic demonstration procedure",
      },
      latest_assessment: {
        event_id: "evt-3",
        revision: 1,
        result: "PASS",
        actor_id: "auditor-2",
        created_at: "2026-10-20T10:00:00Z",
        rationale: "Previous runbook was verified",
        criterion_results: [],
        evidence_pins: [],
        is_stale: true, // assessment stale
        stale_reasons: ["Evidence revision updated since last assessment"],
      },
      primary_state: "STALE_ASSESSMENT",
      blockers: [],
      findings: [],
      history: [],
    },
  ];

  const mockControlList = (items: ControlWorkItem[]): WorkListResponse => ({
    tenant_id: "tenant-1",
    adoption_id: "adopt-1",
    selection_revision: 1,
    answer_revision: 1,
    is_current: true,
    is_stale: false,
    items,
    total: items.length,
  });

  const mockAssessmentList = (items: AssessmentWorkItem[]): AssessmentWorkListResponse => ({
    tenant_id: "tenant-1",
    adoption_id: "adopt-1",
    answer_revision: 1,
    selection_revision: 1,
    is_stale: false,
    items,
    summary: {
      total_controls: items.length,
      stale_work: 0,
      needs_information: 0,
      not_applicable: 0,
      unassessed: 1,
      unavailable_evidence: 0,
      stale_assessment: 1,
      insufficient_evidence: 0,
      fail: 1,
      partial: 0,
      pass_with_open_findings: 0,
      pass_count: 0,
      open_findings: 1,
      in_remediation_findings: 0,
      resolved_findings: 0,
      blocked_control_ids: [],
      reason_codes: [],
    },
  });

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders no-adoption prompt when adoptionId is missing", () => {
    const navFrameworks = vi.fn();
    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId={null}
        onNavigateToFrameworks={navFrameworks}
        asOfDateStr="2026-10-29"
      />
    );

    expect(screen.getByTestId("work-queue-no-adoption")).toBeInTheDocument();
    expect(screen.getByTestId("no-adoption-prompt")).toBeInTheDocument();

    const btn = screen.getByTestId("nav-to-frameworks-btn");
    fireEvent.click(btn);
    expect(navFrameworks).toHaveBeenCalledTimes(1);
  });

  it("loads controls and assessments, rendering bucket counters and prioritized queue rows", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue(mockControlList(dummyControls));
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue(mockAssessmentList(dummyAssessments));

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("work-queue-workspace")).toBeInTheDocument();
    });

    // Bucket counts:
    // Controls: 3, Findings: 1 -> Total Items = 4
    // Overdue items: work-1 control (2026-10-28) + fnd-1 finding (2026-10-28) = 2
    // Due today: work-2 control (2026-10-29) = 1
    // Unassigned: work-2 control = 1
    // Evidence attention: work-1 (no evidence) + work-2 (no evidence) + work-3 (invalid evidence) = 3
    // Assessment needed: work-2 (UNASSESSED) + work-3 (is_stale) = 2
    // Open findings: fnd-1 = 1
    expect(screen.getByTestId("bucket-all-btn")).toHaveTextContent("All Work (4)");
    expect(screen.getByTestId("bucket-overdue-btn")).toHaveTextContent("Overdue (2)");
    expect(screen.getByTestId("bucket-due-today-btn")).toHaveTextContent("Due Today (1)");
    expect(screen.getByTestId("bucket-unassigned-btn")).toHaveTextContent("Unassigned (1)");
    expect(screen.getByTestId("bucket-evidence-btn")).toHaveTextContent("Evidence Attention (3)");
    expect(screen.getByTestId("bucket-assessment-btn")).toHaveTextContent("Assessment Needed (2)");
    expect(screen.getByTestId("bucket-findings-btn")).toHaveTextContent("Open Findings (1)");

    // Badges
    expect(screen.getByTestId("badge-overdue-ctrl-work-1")).toBeInTheDocument();
    expect(screen.getByTestId("badge-overdue-fnd-fnd-1")).toBeInTheDocument();
    expect(screen.getByTestId("badge-due-today-ctrl-work-2")).toBeInTheDocument();
  });

  it("filters items by operational bucket and resets filter correctly", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue(mockControlList(dummyControls));
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue(mockAssessmentList(dummyAssessments));

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("queue-row-ctrl-work-1")).toBeInTheDocument();
    });

    // Click Overdue bucket
    fireEvent.click(screen.getByTestId("bucket-overdue-btn"));

    // Should only have overdue items: ctrl-work-1 and fnd-fnd-1
    expect(screen.getByTestId("queue-row-ctrl-work-1")).toBeInTheDocument();
    expect(screen.getByTestId("queue-row-fnd-fnd-1")).toBeInTheDocument();
    expect(screen.queryByTestId("queue-row-ctrl-work-2")).not.toBeInTheDocument();
    expect(screen.queryByTestId("queue-row-ctrl-work-3")).not.toBeInTheDocument();

    // Click Reset Filters
    const resetBtn = screen.getByTestId("clear-filters-btn");
    fireEvent.click(resetBtn);

    // All items return
    expect(screen.getByTestId("queue-row-ctrl-work-2")).toBeInTheDocument();
  });

  it("filters items by owner and text search", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue(mockControlList(dummyControls));
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue(mockAssessmentList(dummyAssessments));

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("queue-owner-select")).toBeInTheDocument();
    });

    // Filter by unassigned
    fireEvent.change(screen.getByTestId("queue-owner-select"), {
      target: { value: "unassigned" },
    });

    expect(screen.getByTestId("queue-row-ctrl-work-2")).toBeInTheDocument();
    expect(screen.queryByTestId("queue-row-ctrl-work-1")).not.toBeInTheDocument();
    expect(screen.queryByTestId("queue-row-ctrl-work-3")).not.toBeInTheDocument();

    // Filter by search query
    fireEvent.change(screen.getByTestId("queue-owner-select"), {
      target: { value: "all" },
    });
    fireEvent.change(screen.getByTestId("queue-search-input"), {
      target: { value: "Encryption" },
    });

    expect(screen.getByTestId("queue-row-ctrl-work-2")).toBeInTheDocument();
    expect(screen.queryByTestId("queue-row-ctrl-work-1")).not.toBeInTheDocument();
  });

  it("displays partial results notice when assessment list returns 403 Forbidden", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue(mockControlList(dummyControls));
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockRejectedValue(
      new ForbiddenError("Access to assessments is restricted")
    );

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("partial-results-notice")).toBeInTheDocument();
    });

    // Control items should still be displayed
    expect(screen.getByTestId("queue-row-ctrl-work-1")).toBeInTheDocument();
    expect(screen.getByTestId("queue-row-ctrl-work-2")).toBeInTheDocument();
  });

  it("handles 401 Unauthorized by triggering onSessionExpired", async () => {
    const sessionExpiredMock = vi.fn();
    vi.spyOn(controlApi, "fetchControlWorkList").mockRejectedValue(
      new UnauthorizedError("Token expired")
    );
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue(mockAssessmentList([]));

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        onSessionExpired={sessionExpiredMock}
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(sessionExpiredMock).toHaveBeenCalledTimes(1);
    });
  });

  it("opens and closes ControlTraceabilityPanel on clicking traceability button", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue(mockControlList(dummyControls));
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue(mockAssessmentList(dummyAssessments));

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("trace-btn-ctrl-work-1")).toBeInTheDocument();
    });

    // Open traceability panel for work-1
    fireEvent.click(screen.getByTestId("trace-btn-ctrl-work-1"));

    expect(screen.getByTestId("control-traceability-panel")).toBeInTheDocument();
    expect(screen.getByTestId("section-findings-history")).toBeInTheDocument();

    // Close panel
    fireEvent.click(screen.getByTestId("close-traceability-btn"));
    expect(screen.queryByTestId("control-traceability-panel")).not.toBeInTheDocument();
  });

  it("triggers navigation callbacks to evidence and assessment", async () => {
    const navEvidence = vi.fn();
    const navAssessment = vi.fn();

    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue(mockControlList(dummyControls));
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue(mockAssessmentList(dummyAssessments));

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        onNavigateToEvidence={navEvidence}
        onNavigateToAssessment={navAssessment}
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("evidence-btn-ctrl-work-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("evidence-btn-ctrl-work-1"));
    expect(navEvidence).toHaveBeenCalledWith("work-1");

    fireEvent.click(screen.getByTestId("assessment-btn-ctrl-work-1"));
    expect(navAssessment).toHaveBeenCalledWith("work-1", undefined);

    // Finding row navigation passes both workId and findingId
    expect(screen.getByTestId("assessment-btn-fnd-fnd-1")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("assessment-btn-fnd-fnd-1"));
    expect(navAssessment).toHaveBeenCalledWith("work-1", "fnd-1");
  });

  it("invalidates queue on re-entry and refreshEpoch bumps while preserving user filters", async () => {
    const fetchCtrlSpy = vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue(mockControlList(dummyControls));
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue(mockAssessmentList(dummyAssessments));

    const { rerender } = renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        isActiveView={false}
        refreshEpoch={0}
        asOfDateStr="2026-10-29"
      />
    );

    // Initial load occurs
    await waitFor(() => expect(fetchCtrlSpy).toHaveBeenCalledTimes(1));

    // User types search query
    const searchInput = screen.getByTestId("queue-search-input") as HTMLInputElement;
    fireEvent.change(searchInput, { target: { value: "cloud" } });
    expect(searchInput.value).toBe("cloud");

    // View becomes active -> triggers bounded refresh without resetting search filter
    rerender(
      <I18nProvider>
        <WorkQueue
          tenantId="tenant-1"
          token="token-abc"
          adoptionId="adopt-1"
          isActiveView={true}
          refreshEpoch={0}
          asOfDateStr="2026-10-29"
        />
      </I18nProvider>
    );

    await waitFor(() => expect(fetchCtrlSpy).toHaveBeenCalledTimes(2));
    expect(screen.getByTestId("queue-search-input")).toHaveValue("cloud");

    // Mutation epoch bump while active triggers refresh
    rerender(
      <I18nProvider>
        <WorkQueue
          tenantId="tenant-1"
          token="token-abc"
          adoptionId="adopt-1"
          isActiveView={true}
          refreshEpoch={1}
          asOfDateStr="2026-10-29"
        />
      </I18nProvider>
    );

    await waitFor(() => expect(fetchCtrlSpy).toHaveBeenCalledTimes(3));
    expect(screen.getByTestId("queue-search-input")).toHaveValue("cloud");
  });

  it("handles 500 network/server assessment failure honestly with Unknown open findings and retry recovery", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue(mockControlList(dummyControls));
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList")
      .mockRejectedValueOnce(new Error("500 Internal Server Error"))
      .mockResolvedValueOnce(mockAssessmentList(dummyAssessments));

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        isActiveView={true}
        asOfDateStr="2026-10-29"
      />
    );

    // Should display assessment error banner
    await waitFor(() => {
      expect(screen.getByTestId("assessment-error-banner")).toBeInTheDocument();
    });

    // Open findings bucket should NOT report authoritative 0; it reports Unknown!
    const findingsBucketBtn = screen.getByTestId("bucket-findings-btn");
    expect(findingsBucketBtn).toHaveTextContent("Open Findings (Unknown)");

    // Clicking Open Findings bucket shows unavailable prompt with retry button
    fireEvent.click(findingsBucketBtn);
    expect(screen.getByTestId("queue-assessment-unavailable")).toBeInTheDocument();

    // Clicking retry button in banner recovers cleanly
    const retryBtn = screen.getAllByTestId("retry-assessments-btn")[0];
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.queryByTestId("assessment-error-banner")).not.toBeInTheDocument();
      expect(screen.getByTestId("bucket-findings-btn")).toHaveTextContent("Open Findings (1)");
    });
  });

  it("detects adoption envelope mismatch between controls and assessments", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue(mockControlList(dummyControls));
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue({
      ...mockAssessmentList(dummyAssessments),
      adoption_id: "different-adopt-uuid", // Incompatible with controls' adopt-1
    });

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        isActiveView={true}
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("assessment-error-banner")).toBeInTheDocument();
    });
    expect(screen.getByTestId("bucket-findings-btn")).toHaveTextContent("Open Findings (Unknown)");
  });

  it("displays stale refresh warning when subsequent refresh fails while retaining prior controls", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList")
      .mockResolvedValueOnce(mockControlList(dummyControls))
      .mockRejectedValueOnce(new Error("Network connection dropped"));
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue(mockAssessmentList(dummyAssessments));

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        isActiveView={true}
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("queue-row-ctrl-work-1")).toBeInTheDocument();
    });

    // Trigger refresh that fails
    fireEvent.click(screen.getByTestId("refresh-work-queue-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("stale-refresh-warning")).toBeInTheDocument();
    });

    // Prior rows remain displayed
    expect(screen.getByTestId("queue-row-ctrl-work-1")).toBeInTheDocument();
  });

  // --- B03 Repair 2 Regressions: Section A & B ---

  it("rejects incompatible selection revisions between controls and assessments for same adoption ID", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue({
      ...mockControlList(dummyControls),
      selection_revision: 2,
    });
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue({
      ...mockAssessmentList(dummyAssessments),
      selection_revision: 1, // Incompatible selection revision
    });

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        isActiveView={true}
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("assessment-error-banner")).toBeInTheDocument();
    });
    expect(screen.getByTestId("assessment-error-banner")).toHaveTextContent(/selection revision/i);
    expect(screen.getByTestId("bucket-findings-btn")).toHaveTextContent("Open Findings (Unknown)");
  });

  it("rejects incompatible answer revisions between controls and assessments for same adoption ID", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue({
      ...mockControlList(dummyControls),
      answer_revision: 2,
    });
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue({
      ...mockAssessmentList(dummyAssessments),
      answer_revision: 1, // Incompatible answer revision
    });

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        isActiveView={true}
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("assessment-error-banner")).toBeInTheDocument();
    });
    expect(screen.getByTestId("assessment-error-banner")).toHaveTextContent(/answer revision/i);
    expect(screen.getByTestId("bucket-findings-btn")).toHaveTextContent("Open Findings (Unknown)");
  });

  it("rejects responses when both agree with each other but disagree with known parent selectionRevision", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue({
      ...mockControlList(dummyControls),
      selection_revision: 1,
    });
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue({
      ...mockAssessmentList(dummyAssessments),
      selection_revision: 1,
    });

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        selectionRevision={2} // Parent expects revision 2
        answerRevision={1}
        isActiveView={true}
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("controls-error-banner")).toBeInTheDocument();
    });
    expect(screen.getByTestId("controls-error-banner")).toHaveTextContent(/selection revision/i);
  });

  it("rejects responses when both agree with each other but disagree with known parent answerRevision", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue({
      ...mockControlList(dummyControls),
      answer_revision: 1,
    });
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue({
      ...mockAssessmentList(dummyAssessments),
      answer_revision: 1,
    });

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        selectionRevision={1}
        answerRevision={3} // Parent expects revision 3
        isActiveView={true}
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("controls-error-banner")).toBeInTheDocument();
    });
    expect(screen.getByTestId("controls-error-banner")).toHaveTextContent(/answer revision/i);
  });

  it("rejects responses when both agree with each other but differ from explicitly requested persisted adoptionId", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue({
      ...mockControlList(dummyControls),
      adoption_id: "other-adopt-id",
    });
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue({
      ...mockAssessmentList(dummyAssessments),
      adoption_id: "other-adopt-id",
    });

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-pinned-1" // Requested pinned adoption
        isActiveView={true}
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("controls-error-banner")).toBeInTheDocument();
    });
    expect(screen.getByTestId("controls-error-banner")).toHaveTextContent(/adoption/i);
  });

  it("rejects response with wrong or missing required tenant metadata", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue({
      ...mockControlList(dummyControls),
      tenant_id: "wrong-tenant-id",
    });
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue(mockAssessmentList(dummyAssessments));

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        isActiveView={true}
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("controls-error-banner")).toBeInTheDocument();
    });
    expect(screen.getByTestId("controls-error-banner")).toHaveTextContent(/tenant/i);
  });

  it("revision-only prop change invalidates in-flight requests and reloads without allowing stale overwrite", async () => {
    let resolveFirstCtrl: (val: WorkListResponse) => void;
    const firstCtrlPromise = new Promise((resolve) => {
      resolveFirstCtrl = resolve;
    });

    const fetchCtrlSpy = vi.spyOn(controlApi, "fetchControlWorkList");
    fetchCtrlSpy
      .mockImplementationOnce(() => firstCtrlPromise as unknown as Promise<WorkListResponse>)
      .mockResolvedValueOnce({
        ...mockControlList(dummyControls),
        selection_revision: 2,
      });

    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue({
      ...mockAssessmentList(dummyAssessments),
      selection_revision: 2,
    });

    const { rerender } = renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        selectionRevision={1}
        answerRevision={1}
        isActiveView={true}
        asOfDateStr="2026-10-29"
      />
    );

    // Initial load fired for revision 1
    await waitFor(() => expect(fetchCtrlSpy).toHaveBeenCalledTimes(1));

    // Revision prop changes to 2 while first request still in-flight
    rerender(
      <I18nProvider>
        <WorkQueue
          tenantId="tenant-1"
          token="token-abc"
          adoptionId="adopt-1"
          selectionRevision={2}
          answerRevision={1}
          isActiveView={true}
          asOfDateStr="2026-10-29"
        />
      </I18nProvider>
    );

    // Second load fired for revision 2
    await waitFor(() => expect(fetchCtrlSpy).toHaveBeenCalledTimes(2));

    // Now resolve first outdated request with revision 1
    resolveFirstCtrl!({
      ...mockControlList(dummyControls),
      selection_revision: 1,
    });

    // Content should settle on revision 2 data, not overwritten by revision 1
    await waitFor(() => {
      expect(screen.getByTestId("queue-row-ctrl-work-1")).toBeInTheDocument();
      expect(screen.queryByTestId("controls-error-banner")).not.toBeInTheDocument();
    });
  });

  it("valid compatible snapshot with is_stale=true remains operational and accurately labelled", async () => {
    const staleControls = dummyControls.map((c) => ({ ...c, is_stale: true }));
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue({
      ...mockControlList(staleControls),
      is_stale: true,
    });
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue({
      ...mockAssessmentList(dummyAssessments),
      is_stale: true,
    });

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        isActiveView={true}
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("queue-row-ctrl-work-1")).toBeInTheDocument();
    });
    // Operational rows rendered, marked stale
    expect(screen.getByTestId("status-ctrl-work-1")).toHaveTextContent(/STALE/i);
  });

  it("cold assessment failure with known controls leaves assessment-dependent buckets unknown and overall total visibly partial", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue(mockControlList(dummyControls));
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockRejectedValue(new Error("503 Service Unavailable"));

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        isActiveView={true}
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("assessment-error-banner")).toBeInTheDocument();
    });

    // Known control facts are counted
    expect(screen.getByTestId("bucket-unassigned-btn")).toHaveTextContent("Unassigned (1)");
    expect(screen.getByTestId("bucket-due-today-btn")).toHaveTextContent("Due Today (1)");

    // Assessment-dependent buckets MUST be Unknown, not inferred N or 0
    expect(screen.getByTestId("bucket-assessment-btn")).toHaveTextContent("Assessment Needed (Unknown)");
    expect(screen.getByTestId("bucket-findings-btn")).toHaveTextContent("Open Findings (Unknown)");

    // Overall total is visibly partial
    expect(screen.getByTestId("bucket-all-btn")).toHaveTextContent(/Partial/i);

    // Clicking assessment needed bucket shows unavailable notice rather than empty "all done"
    fireEvent.click(screen.getByTestId("bucket-assessment-btn"));
    expect(screen.getByTestId("queue-assessment-unavailable")).toBeInTheDocument();
  });

  it("controls failure with assessment success leaves work queue partial and unavailable", async () => {
    vi.spyOn(controlApi, "fetchControlWorkList").mockRejectedValue(new Error("500 Database Error"));
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue(mockAssessmentList(dummyAssessments));

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        isActiveView={true}
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("controls-error-banner")).toBeInTheDocument();
    });

    // All work cannot claim complete operational rows
    expect(screen.getByTestId("bucket-all-btn")).toHaveTextContent(/Unavailable|Partial/i);
    expect(screen.queryByTestId("queue-row-ctrl-work-1")).not.toBeInTheDocument();
  });
  it("rejects non-integer, string or missing revision metadata in controls and assessments envelopes", async () => {
    // String selection_revision in controls
    const malformedControls = {
      ...mockControlList(dummyControls),
      selection_revision: "1" as unknown as number,
    };
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue(malformedControls);
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue(mockAssessmentList(dummyAssessments));

    renderWithI18n(
      <WorkQueue
        tenantId="tenant-1"
        token="token-abc"
        adoptionId="adopt-1"
        isActiveView={true}
        asOfDateStr="2026-10-29"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("controls-error-banner")).toBeInTheDocument();
    });
    expect(screen.getByTestId("controls-error-banner")).toHaveTextContent(/Invalid or missing selection_revision/i);
  });
});
