import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { AssessmentWorkItem } from "./assessment-types";
import { ControlWorkItem } from "./control-evidence-types";
import { ControlTraceabilityPanel } from "./ControlTraceabilityPanel";

const mockControl: ControlWorkItem = {
  id: "work-1",
  adoption_id: "adopt-1",
  control_id: "AC-1",
  control_version_id: "cv-101",
  title: "Access Control Policy and Procedures",
  provenance: "synthetic_nist_csf",
  pack_version: 2,
  bundle_digest: "sha256:bundle1234567890",
  requirement_results: [
    {
      requirement_id: "req-1",
      requirement_version_id: "rv-1",
      requirement_identifier: "PR.AC-1",
      requirement_title: "Identities and credentials are managed",
      result: "APPLICABLE",
    },
  ],
  owner_user_id: "usr-1",
  owner_display_name: "Alice Security",
  due_date: "2026-11-15",
  version: 3,
  is_current: true,
  is_stale: false,
  links: [
    {
      id: "link-1",
      evidence_id: "ev-10",
      revision_number: 2,
      digest: "sha256:ev10digest",
      file_ids: ["f-1"],
      filename: "access-policy-v2.pdf",
      file_size: 4096,
      classification: "CONFIDENTIAL",
      validity: "AVAILABLE",
      scan_status: "SCANNED_AT_LINK",
      scan_verified_at: "2026-10-25T10:00:00Z",
      review: "ACCEPTED",
      rationale: "Reviewed and approved by CISO",
      created_at: "2026-10-25T10:00:00Z",
    },
  ],
};

const mockAssessment: AssessmentWorkItem = {
  work_id: "work-1",
  control_version_id: "cv-101",
  work_version: 3,
  assessment_revision: 2,
  procedure: {
    id: "proc-101",
    version: "2.1",
    digest: "sha256:procdigest101",
    criteria: [],
    disclaimer: "Synthetic demonstration procedure",
  },
  latest_assessment: {
    event_id: "evt-99",
    revision: 2,
    result: "PASS",
    actor_id: "usr-auditor",
    created_at: "2026-10-26T14:00:00Z",
    rationale: "All controls verified",
    criterion_results: [],
    evidence_pins: [],
    is_stale: true,
    stale_reasons: ["Evidence revision updated since last assessment"],
  },
  primary_state: "PASS",
  blockers: [],
  findings: [
    {
      id: "fnd-1",
      source_event_id: "evt-1",
      current_event_id: "evt-2",
      severity: "MEDIUM",
      status: "IN_REMEDIATION",
      owner_user_id: "usr-1",
      owner_display_name: "Alice Security",
      due_date: "2026-11-01",
      version: 2,
      created_at: "2026-10-20T00:00:00Z",
      updated_at: "2026-10-26T00:00:00Z",
    },
  ],
  history: [
    {
      event_id: "evt-1",
      revision: 1,
      operation_id: "op-1",
      event_type: "ASSESSMENT",
      result: "FAIL",
      observed_work_version: 2,
      actor_id: "usr-auditor",
      created_at: "2026-10-20T00:00:00Z",
      details: {},
    },
    {
      event_id: "evt-2",
      revision: 2,
      operation_id: "op-2",
      event_type: "FINDING_UPDATED",
      result: null,
      observed_work_version: 3,
      actor_id: "usr-1",
      created_at: "2026-10-26T00:00:00Z",
      details: {},
    },
  ],
};

function renderWithI18n(ui: React.ReactElement) {
  return render(<I18nProvider>{ui}</I18nProvider>);
}

describe("ControlTraceabilityPanel Component", () => {
  afterEach(() => {
    cleanup();
  });
  it("renders traceability landmarks, control details, and synthetic provenance banner", () => {
    renderWithI18n(
      <ControlTraceabilityPanel
        control={mockControl}
        assessment={mockAssessment}
      />
    );

    expect(screen.getByTestId("control-traceability-panel")).toBeInTheDocument();
    expect(screen.getByTestId("synthetic-provenance-banner")).toBeInTheDocument();
    expect(screen.getByText("AC-1")).toBeInTheDocument();
    expect(screen.getByText("Access Control Policy and Procedures")).toBeInTheDocument();
    expect(screen.getByText(/Work ID: work-1/i)).toBeInTheDocument();
    expect(screen.getByText("Alice Security")).toBeInTheDocument();
  });

  it("renders version pins and mapped requirement badges", () => {
    renderWithI18n(
      <ControlTraceabilityPanel
        control={mockControl}
        assessment={mockAssessment}
      />
    );

    expect(screen.getByTestId("section-version-pins")).toBeInTheDocument();
    expect(screen.getByTestId("trace-pack-version")).toHaveTextContent("v2");
    expect(screen.getByText("cv-101")).toBeInTheDocument(); // Control version ID
    expect(screen.getByTestId("req-badge-req-1")).toBeInTheDocument();
    expect(screen.getByText(/PR.AC-1/i)).toBeInTheDocument();
  });

  it("renders pinned evidence items with validity, review, and scan badges", () => {
    renderWithI18n(
      <ControlTraceabilityPanel
        control={mockControl}
        assessment={mockAssessment}
      />
    );

    expect(screen.getByTestId("section-pinned-evidence")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-link-row-link-1")).toBeInTheDocument();
    expect(screen.getByText("access-policy-v2.pdf")).toBeInTheDocument();
    expect(screen.getByTestId("link-validity-link-1")).toHaveTextContent("AVAILABLE");
    expect(screen.getByTestId("link-review-link-1")).toHaveTextContent("ACCEPTED");
    expect(screen.getByTestId("link-scan-link-1")).toHaveTextContent("SCANNED_AT_LINK");
  });

  it("renders assessment result, procedure info, and stale warning", () => {
    renderWithI18n(
      <ControlTraceabilityPanel
        control={mockControl}
        assessment={mockAssessment}
      />
    );

    expect(screen.getByTestId("section-assessment-trace")).toBeInTheDocument();
    expect(screen.getByTestId("trace-primary-state")).toHaveTextContent("PASS");
    expect(screen.getByTestId("trace-latest-result")).toHaveTextContent("PASS");
    expect(screen.getByText("2.1")).toBeInTheDocument(); // Procedure version
    expect(screen.getByTestId("assessment-stale-warning")).toBeInTheDocument();
    expect(screen.getByText(/Evidence revision updated since last assessment/i)).toBeInTheDocument();
  });

  it("renders findings and audit event history", () => {
    renderWithI18n(
      <ControlTraceabilityPanel
        control={mockControl}
        assessment={mockAssessment}
      />
    );

    expect(screen.getByTestId("section-findings-history")).toBeInTheDocument();
    expect(screen.getByTestId("finding-item-fnd-1")).toBeInTheDocument();
    expect(screen.getByText("MEDIUM")).toBeInTheDocument();
    expect(screen.getByText(/IN_REMEDIATION/i)).toBeInTheDocument();
  });

  it("triggers navigation and close callbacks on button clicks", () => {
    const onNavEvidence = vi.fn();
    const onNavAssessment = vi.fn();
    const onClose = vi.fn();

    renderWithI18n(
      <ControlTraceabilityPanel
        control={mockControl}
        assessment={mockAssessment}
        onNavigateToEvidence={onNavEvidence}
        onNavigateToAssessment={onNavAssessment}
        onClose={onClose}
      />
    );

    fireEvent.click(screen.getByTestId("nav-to-evidence-btn"));
    expect(onNavEvidence).toHaveBeenCalledWith("work-1");

    fireEvent.click(screen.getByTestId("nav-to-assessment-btn"));
    expect(onNavAssessment).toHaveBeenCalledWith("work-1");

    fireEvent.click(screen.getByTestId("close-traceability-btn"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("toggles technical hash details on button click", () => {
    renderWithI18n(
      <ControlTraceabilityPanel
        control={mockControl}
        assessment={mockAssessment}
      />
    );

    expect(screen.queryByText(/sha256:bundle1234567890/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("toggle-technical-details-btn"));
    expect(screen.getByText(/sha256:bundle1234567890/i)).toBeInTheDocument();
    expect(screen.getByText(/sha256:procdigest101/i)).toBeInTheDocument();
  });
});
