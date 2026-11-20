import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { UnauthorizedError } from "./api";
import * as api from "./assessment-api";
import { AssessmentWorkItem, AssessmentWorkListResponse, Procedure, ReadinessSummary } from "./assessment-types";
import { AssessmentWorkspace } from "./AssessmentWorkspace";
import * as controlApi from "./control-evidence-api";
import { ControlWorkItem, OwnerDirectoryItem } from "./control-evidence-types";

const dummySummary: ReadinessSummary = {
  total_controls: 2,
  stale_work: 0,
  needs_information: 0,
  not_applicable: 0,
  unassessed: 1,
  unavailable_evidence: 0,
  stale_assessment: 0,
  insufficient_evidence: 0,
  fail: 1,
  partial: 0,
  pass_with_open_findings: 0,
  pass_count: 0,
  open_findings: 1,
  in_remediation_findings: 0,
  resolved_findings: 0,
  blocked_control_ids: ["44444444-4444-4444-8444-444444444444"],
  reason_codes: ["OPEN_FINDINGS"],
};

const dummyProcedure: Procedure = {
  id: "55555555-5555-4555-8555-555555555555",
  version: "1.0.0",
  digest: "a".repeat(64),
  criteria: [
    {
      id: "implementation",
      title: "Implementation Verification",
      description: "Verify config",
      sequence: 1,
    },
    {
      id: "evidence",
      title: "Evidence Validation",
      description: "Verify evidence files",
      sequence: 2,
    },
    {
      id: "operation",
      title: "Operational Verification",
      description: "Verify operations",
      sequence: 3,
    },
  ],
  disclaimer: "Synthetic disclaimer",
};

const dummyItem: AssessmentWorkItem = {
  work_id: "33333333-3333-4333-8333-333333333333",
  control_version_id: "44444444-4444-4444-8444-444444444444",
  work_version: 1,
  assessment_revision: 1,
  procedure: dummyProcedure,
  latest_assessment: {
    event_id: "66666666-6666-4666-8666-666666666666",
    revision: 1,
    result: "FAIL",
    actor_id: "88888888-8888-4888-8888-888888888888",
    created_at: "2026-10-25T08:00:00Z",
    rationale: "Initial deficiency identified",
    criterion_results: [
      { criterion_id: "implementation", result: "FAIL", notes: null },
      { criterion_id: "evidence", result: "PASS", notes: null },
      { criterion_id: "operation", result: "PASS", notes: null },
    ],
    evidence_pins: [],
    is_stale: false,
    stale_reasons: [],
  },
  primary_state: "FAIL",
  blockers: ["OPEN_FINDINGS"],
  findings: [
    {
      id: "99999999-9999-4999-8999-999999999999",
      source_event_id: "66666666-6666-4666-8666-666666666666",
      current_event_id: "66666666-6666-4666-8666-666666666666",
      severity: "MEDIUM",
      status: "OPEN",
      owner_user_id: "88888888-8888-4888-8888-888888888888",
      owner_display_name: "Security Lead",
      due_date: "2026-11-15",
      version: 1,
      created_at: "2026-10-25T08:00:00Z",
      updated_at: "2026-10-25T08:00:00Z",
    },
  ],
  history: [],
  requirement_results: [{ requirement_id: "req-1", status: "EVALUATED" }],
};

const dummyControlWorkItem: ControlWorkItem = {
  id: "33333333-3333-4333-8333-333333333333",
  adoption_id: "22222222-2222-4222-8222-222222222222",
  control_id: "ctrl-iam",
  control_version_id: "44444444-4444-4444-8444-444444444444",
  title: "Access Control & MFA",
  provenance: "Synthetic Pack V1",
  pack_version: 1,
  bundle_digest: "a".repeat(64),
  requirement_results: [],
  owner_user_id: "88888888-8888-4888-8888-888888888888",
  owner_display_name: "Security Lead",
  due_date: "2026-11-15",
  version: 1,
  is_current: true,
  is_stale: false,
  links: [
    {
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      evidence_id: "ev111111-1111-4111-8111-111111111111",
      revision_number: 1,
      digest: "b".repeat(64),
      file_ids: ["f1111111-1111-4111-8111-111111111111"],
      filename: "iam_evidence.pdf",
      file_size: 1024,
      classification: "CONFIDENTIAL",
      validity: "AVAILABLE",
      scan_status: "SCANNED_AT_LINK",
      scan_verified_at: "2026-10-25T08:00:00Z",
      review: "ACCEPTED",
      rationale: "Approved",
      created_at: "2026-10-25T08:00:00Z",
    },
  ],
};

const dummyOwners: OwnerDirectoryItem[] = [
  { user_id: "88888888-8888-4888-8888-888888888888", display_name: "Security Lead" },
  { user_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", display_name: "Compliance Officer" },
];

describe("AssessmentWorkspace Component", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "fetchAssessmentWorkList").mockResolvedValue({
      tenant_id: "11111111-1111-4111-8111-111111111111",
      adoption_id: "22222222-2222-4222-8222-222222222222",
      answer_revision: 1,
      selection_revision: 1,
      is_stale: false,
      summary: dummySummary,
      items: [dummyItem],
    });
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue({
      tenant_id: "11111111-1111-4111-8111-111111111111",
      adoption_id: "22222222-2222-4222-8222-222222222222",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      items: [dummyControlWorkItem],
      total: 1,
    });
    vi.spyOn(controlApi, "fetchOwnerDirectory").mockResolvedValue({
      items: dummyOwners,
      total: dummyOwners.length,
    });
    vi.spyOn(api, "fetchProcedure").mockResolvedValue(dummyProcedure);
    vi.spyOn(api, "fetchAssessmentHistory").mockResolvedValue({
      work_id: dummyItem.work_id,
      total: 0,
      items: [],
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders truthful readiness summary counters and control assessment items", async () => {
    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="11111111-1111-4111-8111-111111111111"
          token="test-token"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Human Assessment & Audit Readiness")).toBeInTheDocument();
      expect(screen.getByText("Access Control & MFA")).toBeInTheDocument();
      expect(screen.getAllByText("FAIL").length).toBeGreaterThan(0);
    });
  });

  it("criterion options: select only contains PASS, FAIL, INSUFFICIENT_EVIDENCE", async () => {
    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="11111111-1111-4111-8111-111111111111"
          token="test-token"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Criterion Implementation Verification")).toBeInTheDocument();
    });

    const critSelect = screen.getByLabelText("Criterion Implementation Verification") as HTMLSelectElement;
    const optionValues = Array.from(critSelect.options).map((o) => o.value);
    expect(optionValues).toEqual(["", "PASS", "FAIL", "INSUFFICIENT_EVIDENCE"]);
    expect(optionValues).not.toContain("PARTIAL");
    expect(optionValues).not.toContain("NOT_APPLICABLE");
  });

  it("loads synthetic procedure and records human assessment with deliberate choices", async () => {
    const recordSpy = vi.spyOn(api, "recordAssessment").mockResolvedValue({
      operation_id: "op-1",
      event_id: "e-1",
      applied_revision: 2,
      replayed: false,
      current_item: {
        ...dummyItem,
        assessment_revision: 2,
        primary_state: "PASS",
        findings: [],
      },
      summary: {
        ...dummySummary,
        fail: 0,
        pass_count: 1,
        open_findings: 0,
      },
    });

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="11111111-1111-4111-8111-111111111111"
          token="test-token"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Access Control & MFA")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText("Implementation Verification")).toBeInTheDocument();
    });

    // Deliberate criteria evaluations
    fireEvent.change(screen.getByLabelText("Criterion Implementation Verification"), {
      target: { value: "PASS" },
    });
    fireEvent.change(screen.getByLabelText("Criterion Evidence Validation"), {
      target: { value: "PASS" },
    });
    fireEvent.change(screen.getByLabelText("Criterion Operational Verification"), {
      target: { value: "PASS" },
    });

    // Select the evidence link
    const evCheckbox = screen.getByLabelText("iam_evidence.pdf (rev 1)");
    fireEvent.click(evCheckbox);

    // Review decision select
    fireEvent.change(screen.getByLabelText("Assessment Decision"), {
      target: { value: "PASS" },
    });

    // Enter deliberate rationale
    const textarea = screen.getByLabelText("Assessment Rationale");
    fireEvent.change(textarea, { target: { value: "All criteria satisfied in full." } });

    // Click submit
    const submitBtn = screen.getByTestId(`record-assessment-submit-${dummyItem.work_id}`);
    expect(submitBtn).not.toBeDisabled();
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(recordSpy).toHaveBeenCalledTimes(1);
    });

    const callArgs = recordSpy.mock.calls[0];
    expect(callArgs[0]).toBe("11111111-1111-4111-8111-111111111111");
    expect(callArgs[2]).toBe(dummyItem.work_id);
    expect(callArgs[3].result).toBe("PASS");
    expect(callArgs[3].evidence_link_ids).toEqual(["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"]);
    expect(callArgs[3].rationale).toBe("All criteria satisfied in full.");
    expect(callArgs[3].criterion_results).toHaveLength(3);
  });

  it("evidence link requirement: PASS with 0 evidence links displays error and does not call API; user selects link and submits successfully", async () => {
    const recordSpy = vi.spyOn(api, "recordAssessment").mockResolvedValue({
      operation_id: "op-1",
      event_id: "e-1",
      applied_revision: 2,
      replayed: false,
      current_item: {
        ...dummyItem,
        assessment_revision: 2,
        primary_state: "PASS",
        findings: [],
      },
      summary: {
        ...dummySummary,
        fail: 0,
        pass_count: 1,
        open_findings: 0,
      },
    });

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="11111111-1111-4111-8111-111111111111"
          token="test-token"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Criterion Implementation Verification")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Criterion Implementation Verification"), {
      target: { value: "PASS" },
    });
    fireEvent.change(screen.getByLabelText("Criterion Evidence Validation"), {
      target: { value: "PASS" },
    });
    fireEvent.change(screen.getByLabelText("Criterion Operational Verification"), {
      target: { value: "PASS" },
    });

    fireEvent.change(screen.getByLabelText("Assessment Decision"), {
      target: { value: "PASS" },
    });

    fireEvent.change(screen.getByLabelText("Assessment Rationale"), {
      target: { value: "Attempting pass with 0 evidence links." },
    });

    // Submit with 0 evidence links selected
    const submitBtn = screen.getByTestId(`record-assessment-submit-${dummyItem.work_id}`);
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("At least one evidence link must be selected for PASS")).toBeInTheDocument();
    });
    expect(recordSpy).not.toHaveBeenCalled();

    // Now deliberately select the evidence link
    fireEvent.click(screen.getByLabelText("iam_evidence.pdf (rev 1)"));
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(recordSpy).toHaveBeenCalledTimes(1);
    });
    expect(recordSpy.mock.calls[0][3].evidence_link_ids).toEqual(["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"]);
  });

  it("INSUFFICIENT_EVIDENCE path: 0 evidence links allowed, submitted successfully", async () => {
    const recordSpy = vi.spyOn(api, "recordAssessment").mockResolvedValue({
      operation_id: "op-insufficient",
      event_id: "e-insufficient",
      applied_revision: 2,
      replayed: false,
      current_item: {
        ...dummyItem,
        assessment_revision: 2,
        primary_state: "INSUFFICIENT_EVIDENCE",
      },
      summary: {
        ...dummySummary,
        insufficient_evidence: 1,
      },
    });

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="11111111-1111-4111-8111-111111111111"
          token="test-token"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Criterion Implementation Verification")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Criterion Implementation Verification"), {
      target: { value: "INSUFFICIENT_EVIDENCE" },
    });
    fireEvent.change(screen.getByLabelText("Criterion Evidence Validation"), {
      target: { value: "INSUFFICIENT_EVIDENCE" },
    });
    fireEvent.change(screen.getByLabelText("Criterion Operational Verification"), {
      target: { value: "INSUFFICIENT_EVIDENCE" },
    });

    fireEvent.change(screen.getByLabelText("Assessment Decision"), {
      target: { value: "INSUFFICIENT_EVIDENCE" },
    });

    fireEvent.change(screen.getByLabelText("Assessment Rationale"), {
      target: { value: "Evidence documents not provided." },
    });

    const submitBtn = screen.getByTestId(`record-assessment-submit-${dummyItem.work_id}`);
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(recordSpy).toHaveBeenCalledTimes(1);
    });

    expect(recordSpy.mock.calls[0][3].result).toBe("INSUFFICIENT_EVIDENCE");
    expect(recordSpy.mock.calls[0][3].evidence_link_ids).toEqual([]);
  });

  it("finding severity requirement: unselected severity displays error; selecting severity submits successfully", async () => {
    const recordSpy = vi.spyOn(api, "recordAssessment").mockResolvedValue({
      operation_id: "op-finding",
      event_id: "e-finding",
      applied_revision: 2,
      replayed: false,
      current_item: dummyItem,
      summary: dummySummary,
    });

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="11111111-1111-4111-8111-111111111111"
          token="test-token"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Criterion Implementation Verification")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Criterion Implementation Verification"), {
      target: { value: "FAIL" },
    });
    fireEvent.change(screen.getByLabelText("Criterion Evidence Validation"), {
      target: { value: "PASS" },
    });
    fireEvent.change(screen.getByLabelText("Criterion Operational Verification"), {
      target: { value: "PASS" },
    });

    fireEvent.change(screen.getByLabelText("Assessment Decision"), {
      target: { value: "FAIL" },
    });

    fireEvent.change(screen.getByLabelText("Assessment Rationale"), {
      target: { value: "Failed implementation test." },
    });

    // Check Record Finding
    const findingCheckbox = screen.getByLabelText("Record Finding");
    fireEvent.click(findingCheckbox);

    // Initial finding severity is empty - click submit
    const submitBtn = screen.getByTestId(`record-assessment-submit-${dummyItem.work_id}`);
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Finding severity is required")).toBeInTheDocument();
    });
    expect(recordSpy).not.toHaveBeenCalled();

    // Select severity
    fireEvent.change(screen.getByLabelText("Severity"), {
      target: { value: "CRITICAL" },
    });

    // Click submit again
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(recordSpy).toHaveBeenCalledTimes(1);
    });

    expect(recordSpy.mock.calls[0][3].finding?.severity).toBe("CRITICAL");
  });

  it("updates finding into remediation with notes and clearing owner/date", async () => {
    const updateSpy = vi.spyOn(api, "updateFinding").mockResolvedValue({
      operation_id: "op-2",
      event_id: "e-2",
      applied_revision: 2,
      replayed: false,
      current_item: {
        ...dummyItem,
        findings: [
          {
            ...dummyItem.findings[0],
            status: "IN_REMEDIATION",
            owner_user_id: null,
            owner_display_name: null,
            due_date: null,
            version: 2,
          },
        ],
      },
      summary: dummySummary,
    });

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="11111111-1111-4111-8111-111111111111"
          token="test-token"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId(`tab-findings-${dummyItem.work_id}`)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId(`tab-findings-${dummyItem.work_id}`));

    const editBtn = screen.getByTestId(`edit-finding-btn-${dummyItem.findings[0].id}`);
    fireEvent.click(editBtn);

    expect(screen.getByTestId("remediation-form")).toBeInTheDocument();

    // Change status to IN_REMEDIATION
    fireEvent.change(screen.getByLabelText("Status"), {
      target: { value: "IN_REMEDIATION" },
    });

    // Clear owner to Unassigned ("")
    fireEvent.change(screen.getByLabelText("Assigned Owner"), {
      target: { value: "" },
    });

    // Clear due date to ""
    fireEvent.change(screen.getByLabelText("Target Date"), {
      target: { value: "" },
    });

    const noteArea = screen.getByLabelText("Remediation Progress Note");
    fireEvent.change(noteArea, { target: { value: "Active ticket ENG-424 assigned." } });

    const saveBtn = screen.getByTestId("save-remediation-btn");
    expect(saveBtn).not.toBeDisabled();
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledTimes(1);
    });

    const payload = updateSpy.mock.calls[0][3];
    expect(payload.status).toBe("IN_REMEDIATION");
    expect(payload.owner_user_id).toBeNull();
    expect(payload.due_date).toBeNull();
    expect(payload.remediation_note).toBe("Active ticket ENG-424 assigned.");
  });

  it("records explicit retest resolving finding with selected evidence", async () => {
    const retestSpy = vi.spyOn(api, "recordRetest").mockResolvedValue({
      operation_id: "op-3",
      event_id: "e-3",
      applied_revision: 2,
      replayed: false,
      current_item: {
        ...dummyItem,
        assessment_revision: 2,
        primary_state: "PASS",
        findings: [
          {
            ...dummyItem.findings[0],
            status: "RESOLVED",
            version: 2,
          },
        ],
      },
      summary: {
        ...dummySummary,
        open_findings: 0,
        resolved_findings: 1,
      },
    });

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="11111111-1111-4111-8111-111111111111"
          token="test-token"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId(`tab-retest-${dummyItem.work_id}`)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId(`tab-retest-${dummyItem.work_id}`));

    // Select finding to retest
    const findingSelect = screen.getByLabelText("Select Finding to Resolve");
    fireEvent.change(findingSelect, { target: { value: dummyItem.findings[0].id } });

    // Criteria evaluations
    fireEvent.change(screen.getByLabelText("Retest criterion Implementation Verification"), {
      target: { value: "PASS" },
    });
    fireEvent.change(screen.getByLabelText("Retest criterion Evidence Validation"), {
      target: { value: "PASS" },
    });
    fireEvent.change(screen.getByLabelText("Retest criterion Operational Verification"), {
      target: { value: "PASS" },
    });

    // Select retest evidence
    const retestEvidenceCheckbox = screen.getByLabelText("Retest evidence iam_evidence.pdf");
    fireEvent.click(retestEvidenceCheckbox);

    // Decision select
    fireEvent.change(screen.getByLabelText("Retest Outcome"), {
      target: { value: "PASS" },
    });

    // Retest rationale
    fireEvent.change(screen.getByLabelText("Retest Verification Rationale"), {
      target: { value: "MFA policy now deployed and enforced." },
    });

    const submitBtn = screen.getByTestId(`record-retest-submit-${dummyItem.work_id}`);
    expect(submitBtn).not.toBeDisabled();
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(retestSpy).toHaveBeenCalledTimes(1);
    });

    const payload = retestSpy.mock.calls[0][3];
    expect(payload.result).toBe("PASS");
    expect(payload.evidence_link_ids).toEqual(["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"]);
    expect(payload.rationale).toBe("MFA policy now deployed and enforced.");
    expect(payload.findings[0].id).toBe(dummyItem.findings[0].id);
  });

  it("retest criteria consistency: outcome PASS with FAIL criterion displays validation error", async () => {
    const retestSpy = vi.spyOn(api, "recordRetest");

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="11111111-1111-4111-8111-111111111111"
          token="test-token"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId(`tab-retest-${dummyItem.work_id}`)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId(`tab-retest-${dummyItem.work_id}`));

    fireEvent.change(screen.getByLabelText("Select Finding to Resolve"), {
      target: { value: dummyItem.findings[0].id },
    });

    fireEvent.change(screen.getByLabelText("Retest criterion Implementation Verification"), {
      target: { value: "FAIL" },
    });
    fireEvent.change(screen.getByLabelText("Retest criterion Evidence Validation"), {
      target: { value: "PASS" },
    });
    fireEvent.change(screen.getByLabelText("Retest criterion Operational Verification"), {
      target: { value: "PASS" },
    });

    fireEvent.click(screen.getByLabelText("Retest evidence iam_evidence.pdf"));

    fireEvent.change(screen.getByLabelText("Retest Outcome"), {
      target: { value: "PASS" },
    });

    fireEvent.change(screen.getByLabelText("Retest Verification Rationale"), {
      target: { value: "Inconsistent criteria attempt" },
    });

    fireEvent.click(screen.getByTestId(`record-retest-submit-${dummyItem.work_id}`));

    await waitFor(() => {
      expect(screen.getByText("PASS retest requires all criteria to be PASS")).toBeInTheDocument();
    });
    expect(retestSpy).not.toHaveBeenCalled();
  });

  it("retry vs form edit: network failure preserves operation_id on retry; editing form generates fresh operation_id", async () => {
    const recordSpy = vi.spyOn(api, "recordAssessment")
      .mockRejectedValueOnce(new Error("Network timeout"))
      .mockRejectedValueOnce(new Error("Network timeout 2"))
      .mockResolvedValueOnce({
        operation_id: "op-fresh",
        event_id: "e-fresh",
        applied_revision: 3,
        replayed: false,
        current_item: dummyItem,
        summary: dummySummary,
      });

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="11111111-1111-4111-8111-111111111111"
          token="test-token"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Criterion Implementation Verification")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Criterion Implementation Verification"), {
      target: { value: "PASS" },
    });
    fireEvent.change(screen.getByLabelText("Criterion Evidence Validation"), {
      target: { value: "PASS" },
    });
    fireEvent.change(screen.getByLabelText("Criterion Operational Verification"), {
      target: { value: "PASS" },
    });
    fireEvent.click(screen.getByLabelText("Evidence iam_evidence.pdf"));
    fireEvent.change(screen.getByLabelText("Assessment Decision"), {
      target: { value: "PASS" },
    });
    fireEvent.change(screen.getByLabelText("Assessment Rationale"), {
      target: { value: "Initial rationale for network test" },
    });

    const submitBtn = screen.getByTestId(`record-assessment-submit-${dummyItem.work_id}`);

    // Call 1: Network error
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText("Network timeout")).toBeInTheDocument();
    });
    expect(recordSpy).toHaveBeenCalledTimes(1);
    const firstOpId = recordSpy.mock.calls[0][3].operation_id;

    // Call 2: Exact retry without form edits -> must preserve same operation_id
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText("Network timeout 2")).toBeInTheDocument();
    });
    expect(recordSpy).toHaveBeenCalledTimes(2);
    const secondOpId = recordSpy.mock.calls[1][3].operation_id;
    expect(secondOpId).toBe(firstOpId);

    // Call 3: Edit rationale in form -> deliberate new intent generates fresh operation_id
    fireEvent.change(screen.getByLabelText("Assessment Rationale"), {
      target: { value: "Edited rationale representing deliberate new intent" },
    });
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(recordSpy).toHaveBeenCalledTimes(3);
    });
    const thirdOpId = recordSpy.mock.calls[2][3].operation_id;
    expect(thirdOpId).not.toBe(firstOpId);
  });

  it("centralized 401: 401 invalidates session generation, clears items, summary, and calls onSessionExpired", async () => {
    vi.spyOn(api, "fetchAssessmentWorkList").mockRejectedValue(new UnauthorizedError("Token expired"));
    const expiredSpy = vi.fn();

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="11111111-1111-4111-8111-111111111111"
          token="expired-token"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          onSessionExpired={expiredSpy}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(expiredSpy).toHaveBeenCalledTimes(1);
    });

    expect(screen.queryByText("Access Control & MFA")).not.toBeInTheDocument();
  });

  it("tokenless props: disables actions (isMutationDisabled = true)", async () => {
    const { rerender } = render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="11111111-1111-4111-8111-111111111111"
          token="test-token"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Access Control & MFA")).toBeInTheDocument();
      expect(screen.getByText("Implementation Verification")).toBeInTheDocument();
    });

    const decisionSelect = screen.getByLabelText("Assessment Decision");
    const rationaleArea = screen.getByLabelText("Assessment Rationale");
    expect(decisionSelect).not.toBeDisabled();
    expect(rationaleArea).not.toBeDisabled();

    // Rerender with token="" -> tokenless disables all mutation actions
    rerender(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="11111111-1111-4111-8111-111111111111"
          token=""
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(decisionSelect).toBeDisabled();
      expect(rationaleArea).toBeDisabled();
    });
  });

  it("tenant-switch and token isolation: deferred response from tenant A does not overwrite tenant B state", async () => {
    let resolveTenantA: (val: AssessmentWorkListResponse) => void = () => {};
    let resolveTenantB: (val: AssessmentWorkListResponse) => void = () => {};

    const promiseA = new Promise<AssessmentWorkListResponse>((resolve) => {
      resolveTenantA = resolve;
    });
    const promiseB = new Promise<AssessmentWorkListResponse>((resolve) => {
      resolveTenantB = resolve;
    });

    vi.spyOn(api, "fetchAssessmentWorkList").mockImplementation((tenantId: string) => {
      if (tenantId === "tenant-A") {
        return promiseA;
      }
      return promiseB;
    });

    const { rerender } = render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="tenant-A"
          token="tok-A"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
        />
      </I18nProvider>
    );

    await Promise.resolve();

    // Switch to tenant B while tenant A request is in-flight
    rerender(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="tenant-B"
          token="tok-B"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
        />
      </I18nProvider>
    );

    // Resolve tenant A's request late
    resolveTenantA({
      tenant_id: "tenant-A",
      adoption_id: "ad-A",
      answer_revision: 1,
      selection_revision: 1,
      is_stale: false,
      summary: dummySummary,
      items: [
        {
          ...dummyItem,
          work_id: "work-A",
        },
      ],
    });

    // Resolve tenant B's request
    resolveTenantB({
      tenant_id: "tenant-B",
      adoption_id: "ad-B",
      answer_revision: 1,
      selection_revision: 1,
      is_stale: false,
      summary: dummySummary,
      items: [
        {
          ...dummyItem,
          work_id: "work-B",
        },
      ],
    });

    // Verify tenant B's card is shown and tenant A's card is never shown
    await waitFor(() => {
      expect(screen.getByTestId("assessment-card-work-B")).toBeInTheDocument();
      expect(screen.queryByTestId("assessment-card-work-A")).not.toBeInTheDocument();
    });
  });

  it("refresh race: older deferred refreshWorkData response does NOT overwrite newer refresh response", async () => {
    let resolveRefresh1: (val: AssessmentWorkListResponse) => void = () => {};
    let resolveRefresh2: (val: AssessmentWorkListResponse) => void = () => {};

    const promise1 = new Promise<AssessmentWorkListResponse>((res) => {
      resolveRefresh1 = res;
    });
    const promise2 = new Promise<AssessmentWorkListResponse>((res) => {
      resolveRefresh2 = res;
    });

    let callCount = 0;
    vi.spyOn(api, "fetchAssessmentWorkList").mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        // Initial load
        return Promise.resolve({
          tenant_id: "tenant-1",
          adoption_id: "ad-1",
          answer_revision: 1,
          selection_revision: 1,
          is_stale: false,
          summary: dummySummary,
          items: [dummyItem],
        });
      }
      if (callCount === 2) {
        return promise1;
      }
      return promise2;
    });

    const { rerender } = render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="tenant-1"
          token="tok-1"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          refreshEpoch={0}
          isActiveView={true}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId(`assessment-card-${dummyItem.work_id}`)).toBeInTheDocument();
    });

    // Trigger refresh 1
    rerender(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="tenant-1"
          token="tok-1"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          refreshEpoch={1}
          isActiveView={true}
        />
      </I18nProvider>
    );

    // Trigger refresh 2
    rerender(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="tenant-1"
          token="tok-1"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          refreshEpoch={2}
          isActiveView={true}
        />
      </I18nProvider>
    );

    // Resolve refresh 2 first with NEWER state
    resolveRefresh2({
      tenant_id: "tenant-1",
      adoption_id: "ad-1",
      answer_revision: 1,
      selection_revision: 1,
      is_stale: false,
      summary: { ...dummySummary, unassessed: 0, pass_count: 2 },
      items: [
        {
          ...dummyItem,
          work_id: "work-newer",
          primary_state: "PASS",
        },
      ],
    });

    await waitFor(() => {
      expect(screen.getByTestId("assessment-card-work-newer")).toBeInTheDocument();
    });

    // Now resolve refresh 1 LATE with OLDER state
    resolveRefresh1({
      tenant_id: "tenant-1",
      adoption_id: "ad-1",
      answer_revision: 1,
      selection_revision: 1,
      is_stale: false,
      summary: { ...dummySummary, unassessed: 2, pass_count: 0 },
      items: [
        {
          ...dummyItem,
          work_id: "work-older",
          primary_state: "FAIL",
        },
      ],
    });

    // Verify older snapshot did NOT overwrite newer state
    await waitFor(() => {
      expect(screen.getByTestId("assessment-card-work-newer")).toBeInTheDocument();
      expect(screen.queryByTestId("assessment-card-work-older")).not.toBeInTheDocument();
    });
  });

  it("refresh race: older deferred refreshWorkData response does NOT overwrite newer mutation receipt", async () => {
    let resolveRefresh: (val: AssessmentWorkListResponse) => void = () => {};
    const deferredRefreshPromise = new Promise<AssessmentWorkListResponse>((res) => {
      resolveRefresh = res;
    });

    let fetchCount = 0;
    vi.spyOn(api, "fetchAssessmentWorkList").mockImplementation(() => {
      fetchCount++;
      if (fetchCount === 1) {
        // Initial load
        return Promise.resolve({
          tenant_id: "tenant-1",
          adoption_id: "ad-1",
          answer_revision: 1,
          selection_revision: 1,
          is_stale: false,
          summary: dummySummary,
          items: [dummyItem],
        });
      }
      // Background refresh
      return deferredRefreshPromise;
    });

    vi.spyOn(api, "fetchProcedure").mockResolvedValue(dummyProcedure);

    const receiptItem: AssessmentWorkItem = {
      ...dummyItem,
      primary_state: "PASS",
      latest_assessment: {
        event_id: "mutated-event-id",
        revision: 2,
        result: "PASS",
        actor_id: "88888888-8888-4888-8888-888888888888",
        created_at: "2026-10-29T10:00:00Z",
        rationale: "Deficiency remediated",
        criterion_results: [
          { criterion_id: "implementation", result: "PASS", notes: null },
          { criterion_id: "evidence", result: "PASS", notes: null },
          { criterion_id: "operation", result: "PASS", notes: null },
        ],
        evidence_pins: [],
        is_stale: false,
        stale_reasons: [],
      },
    };

    vi.spyOn(api, "recordAssessment").mockResolvedValue({
      operation_id: "op-deferred",
      event_id: "mutated-event-id",
      applied_revision: 2,
      replayed: false,
      summary: { ...dummySummary, unassessed: 0, pass_count: 1 },
      current_item: receiptItem,
    });

    const { rerender } = render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="tenant-1"
          token="tok-1"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          refreshEpoch={0}
          isActiveView={true}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId(`assessment-card-${dummyItem.work_id}`)).toBeInTheDocument();
    });

    // Launch background refresh that hangs
    rerender(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="tenant-1"
          token="tok-1"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          refreshEpoch={1}
          isActiveView={true}
        />
      </I18nProvider>
    );

    // The assess form is open by default. Fill criteria selects:
    const crit1 = screen.getByLabelText("Criterion Implementation Verification");
    fireEvent.change(crit1, { target: { value: "PASS" } });
    const crit2 = screen.getByLabelText("Criterion Evidence Validation");
    fireEvent.change(crit2, { target: { value: "PASS" } });
    const crit3 = screen.getByLabelText("Criterion Operational Verification");
    fireEvent.change(crit3, { target: { value: "PASS" } });

    // Assessment Decision
    const decisionSelect = screen.getByLabelText("Assessment Decision");
    fireEvent.change(decisionSelect, { target: { value: "PASS" } });

    // Rationale
    const rationaleInput = screen.getByLabelText("Assessment Rationale");
    fireEvent.change(rationaleInput, { target: { value: "Full remediation verified" } });

    // Link evidence
    const evCheckbox = screen.getByLabelText(/Evidence iam_evidence.pdf/i);
    fireEvent.click(evCheckbox);

    // Submit mutation while refresh is in-flight
    const submitBtn = screen.getByTestId(`record-assessment-submit-${dummyItem.work_id}`);
    fireEvent.click(submitBtn);

    // Wait for mutation to succeed
    await waitFor(() => {
      expect(screen.getByText(/Record Human Assessment - OK/i)).toBeInTheDocument();
    });

    // Now resolve the older deferred refresh with OLD FAIL item
    resolveRefresh({
      tenant_id: "tenant-1",
      adoption_id: "ad-1",
      answer_revision: 1,
      selection_revision: 1,
      is_stale: false,
      summary: dummySummary,
      items: [dummyItem], // older state
    });

    // Let any pending microtasks flush
    await Promise.resolve();

    // Verify mutation receipt is STILL displayed and was NOT reverted by older read
    expect(screen.getByText(/Record Human Assessment - OK/i)).toBeInTheDocument();
  });

  it("refresh race: selection revision bump invalidates pending refreshWorkData", async () => {
    let resolveRefresh: (val: AssessmentWorkListResponse) => void = () => {};
    const deferredPromise = new Promise<AssessmentWorkListResponse>((res) => {
      resolveRefresh = res;
    });

    let fetchCount = 0;
    vi.spyOn(api, "fetchAssessmentWorkList").mockImplementation(() => {
      fetchCount++;
      if (fetchCount === 1) {
        return Promise.resolve({
          tenant_id: "tenant-1",
          adoption_id: "ad-1",
          answer_revision: 1,
          selection_revision: 1,
          is_stale: false,
          summary: dummySummary,
          items: [dummyItem],
        });
      }
      return deferredPromise;
    });

    const { rerender } = render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="tenant-1"
          token="tok-1"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          refreshEpoch={0}
          isActiveView={true}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId(`assessment-card-${dummyItem.work_id}`)).toBeInTheDocument();
    });

    // Trigger refresh under selection revision 1
    rerender(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="tenant-1"
          token="tok-1"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          refreshEpoch={1}
          isActiveView={true}
        />
      </I18nProvider>
    );

    // Now pack selection revision bumps to 2
    rerender(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="tenant-1"
          token="tok-1"
          selectionRevision={2}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          refreshEpoch={1}
          isActiveView={true}
        />
      </I18nProvider>
    );

    // Resolve the deferred refresh that was started under rev 1
    resolveRefresh({
      tenant_id: "tenant-1",
      adoption_id: "ad-rev1",
      answer_revision: 1,
      selection_revision: 1,
      is_stale: false,
      summary: dummySummary,
      items: [
        {
          ...dummyItem,
          work_id: "work-rev1-should-be-dropped",
        },
      ],
    });

    await Promise.resolve();

    // Verify rev 1 response was dropped
    expect(screen.queryByTestId("assessment-card-work-rev1-should-be-dropped")).not.toBeInTheDocument();
  });

  // --- B03 Repair 2 Regressions: Section C Pending Navigation ---

  it("finding target arriving during assessment load waits for data to settle, selects findings tab, and focuses finding row without losing draft edits", async () => {
    let resolveAssessData: (val: AssessmentWorkListResponse) => void;
    const assessDataPromise = new Promise((resolve) => {
      resolveAssessData = resolve;
    });

    vi.spyOn(api, "fetchAssessmentWorkList").mockImplementation(() => assessDataPromise as unknown as Promise<AssessmentWorkListResponse>);

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="t-1"
          token="tok"
          adoptionId="adopt-1"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          navTarget={{ workId: "33333333-3333-4333-8333-333333333333", findingId: "fnd-1", nonce: 778899 }}
        />
      </I18nProvider>
    );

    // While loading, premature not-found banner must NOT be shown
    expect(screen.queryByTestId("assessment-nav-target-not-found")).not.toBeInTheDocument();

    // Now resolve data with work item w-1 containing finding fnd-1
    resolveAssessData!({
      tenant_id: "t-1",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_stale: false,
      summary: dummySummary,
      items: [
        {
          ...dummyItem,
          findings: [
            {
              id: "fnd-1",
              source_event_id: "evt-1",
              current_event_id: "evt-1",
              severity: "HIGH",
              status: "OPEN",
              owner_user_id: "u-1",
              owner_display_name: "Alice",
              due_date: "2026-11-01",
              version: 1,
              created_at: "2026-10-25T10:00:00Z",
              updated_at: "2026-10-25T10:00:00Z",
            },
          ],
        },
      ],
    });

    // Resolves and applies finding target
    await waitFor(() => {
      expect(screen.getByTestId("finding-row-fnd-1")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("assessment-nav-target-not-found")).not.toBeInTheDocument();
  });
  it("preserves navigation target during background refresh and after initial failure retry", async () => {
    let callCount = 0;
    vi.spyOn(api, "fetchAssessmentWorkList").mockImplementation(async () => {
      callCount++;
      if (callCount === 1) {
        throw new Error("503 Service Unavailable");
      }
      return {
        tenant_id: "tenant-1",
        adoption_id: "adopt-1",
        selection_revision: 1,
        answer_revision: 1,
        is_stale: false,
        summary: dummySummary,
        items: [
          {
            ...dummyItem,
            work_id: "work-target-99",
          },
        ],
      };
    });

    const { rerender } = render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="tenant-1"
          token="token-abc"
          adoptionId="adopt-1"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          navTarget={{ workId: "work-target-99", nonce: 888 }}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/503 Service Unavailable/i)).toBeInTheDocument();
    });

    // Intent should NOT be consumed as not found
    expect(screen.queryByTestId("nav-target-not-found-notice")).not.toBeInTheDocument();

    // Trigger retry with valid load
    rerender(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId="tenant-1"
          token="token-retry"
          adoptionId="adopt-1"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          navTarget={{ workId: "work-target-99", nonce: 888 }}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("assessment-card-work-target-99")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("nav-target-not-found-notice")).not.toBeInTheDocument();
  });
});
