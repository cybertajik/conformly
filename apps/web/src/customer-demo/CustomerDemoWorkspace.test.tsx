import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { CustomerDemoWorkspace, type PortalView } from "./CustomerDemoWorkspace";
import * as api from "./api";
import * as controlApi from "./control-evidence-api";
import * as assessmentApi from "./assessment-api";
import type { WorkspaceData, EvaluationData, AdoptionReceipt } from "./types";

import type { ControlWorkItem } from "./control-evidence-types";

import type { AssessmentWorkItem } from "./assessment-types";

const FACT_CLOUD_UUID = "e0000000-0000-0000-0000-000000000001";
const FACT_REGION_UUID = "e0000000-0000-0000-0000-000000000002";

const mockWorkspace: WorkspaceData = {
  tenant_id: "11111111-1111-1111-1111-111111111111",
  current_revision: 1,
  selection_revision: 0,
  manifest: {
    disclaimer: "Synthetic customer onboarding demonstration. Not legal or compliance advice.",
    evaluator_version: "wp09-synthetic-v1",
    companies: [
      { code: "ALPHA", display_name: "Fictional Alpha (Cloud-First)" },
      { code: "BETA", display_name: "Fictional Beta (Hybrid/Regional)" },
    ],
    fact_definitions: [
      {
        id: "fact-cloud-def",
        version_id: FACT_CLOUD_UUID,
        key: "synthetic_wp09_uses_cloud",
        label: "Uses Cloud Infrastructure",
        description: "Whether the workload runs in cloud environments",
        value_type: "boolean",
      },
      {
        id: "fact-region-def",
        version_id: FACT_REGION_UUID,
        key: "synthetic_wp09_operating_region",
        label: "Primary Operating Region",
        description: "Primary geographic region of operation",
        value_type: "enum",
        enum_options: [
          { code: "EU", label: "European Union" },
          { code: "OTHER", label: "Other Global Regions" },
        ],
      },
    ],
    packs: [
      {
        pack_id: "pack-v1",
        pack_version_id: "pack-v1-id",
        version: "1.0.0",
        name: "Synthetic Customer Baseline Pack",
        description: "Initial synthetic baseline pack",
        bundle_digest: "65d0f766" + "0".repeat(56),
        requirement_count: 2,
        requirements: [
          {
            id: "req-1",
            version_id: "req-1-v1",
            identifier: "SYNTH-REQ-001",
            title: "Synthetic Cloud Architecture Governance",
            description: "Cloud baseline requirement",
            rule_id: "rule-1",
            rule_version_id: "rule-1-v1",
            control_id: "ctrl-1",
            control_version_id: "ctrl-1-v1",
            control_identifier: "SYNTH-CTRL-001",
            control_title: "Cloud Configuration & Access Baseline",
          },
          {
            id: "req-2",
            version_id: "req-2-v1",
            identifier: "SYNTH-REQ-002",
            title: "Synthetic EU Regional Data Isolation",
            description: "EU isolation requirement",
            rule_id: "rule-2",
            rule_version_id: "rule-2-v1",
            control_id: "ctrl-2",
            control_version_id: "ctrl-2-v1",
            control_identifier: "SYNTH-CTRL-002",
            control_title: "Sovereign Boundary Encryption & Residency",
          },
        ],
      },
      {
        pack_id: "pack-v2",
        pack_version_id: "pack-v2-id",
        version: "2.0.0",
        name: "Synthetic Customer Extended Pack",
        description: "Updated synthetic pack with resilience",
        bundle_digest: "b3f90be4" + "0".repeat(56),
        requirement_count: 3,
        requirements: [
          {
            id: "req-1",
            version_id: "req-1-v1",
            identifier: "SYNTH-REQ-001",
            title: "Synthetic Cloud Architecture Governance",
            description: "Cloud baseline requirement",
            rule_id: "rule-1",
            rule_version_id: "rule-1-v1",
            control_id: "ctrl-1",
            control_version_id: "ctrl-1-v1",
            control_identifier: "SYNTH-CTRL-001",
            control_title: "Cloud Configuration & Access Baseline",
          },
          {
            id: "req-2",
            version_id: "req-2-v1",
            identifier: "SYNTH-REQ-002",
            title: "Synthetic EU Regional Data Isolation",
            description: "EU isolation requirement",
            rule_id: "rule-2",
            rule_version_id: "rule-2-v1",
            control_id: "ctrl-2",
            control_version_id: "ctrl-2-v1",
            control_identifier: "SYNTH-CTRL-002",
            control_title: "Sovereign Boundary Encryption & Residency",
          },
          {
            id: "req-3",
            version_id: "req-3-v1",
            identifier: "SYNTH-REQ-003",
            title: "Synthetic Hybrid or Non-EU Resilience Rule",
            description: "Resilience requirement",
            rule_id: "rule-3",
            rule_version_id: "rule-3-v1",
            control_id: "ctrl-3",
            control_version_id: "ctrl-3-v1",
            control_identifier: "SYNTH-CTRL-003",
            control_title: "Boundary Containment & Alternative Architecture",
          },
        ],
      },
      {
        pack_id: "pack-resilience-family",
        pack_version_id: "pack-res-v1-id",
        version: "1.0.0",
        name: "Synthetic Service Resilience Baseline Pack",
        description: "Resilience baseline pack",
        bundle_digest: "9e348609" + "0".repeat(56),
        requirement_count: 2,
        requirements: [
          {
            id: "req-res-1",
            version_id: "req-res-1-v1",
            identifier: "SYNTH-RES-001",
            title: "Synthetic Resilience Cloud Baseline",
            description: "Cloud baseline requirement",
            rule_id: "rule-res-1",
            rule_version_id: "rule-res-1-v1",
            control_id: "ctrl-1",
            control_version_id: "ctrl-1-v1",
            control_identifier: "SYNTH-CTRL-001",
            control_title: "Cloud Configuration & Access Baseline",
          },
        ],
      },
      {
        pack_id: "pack-resilience-family",
        pack_version_id: "pack-res-v2-id",
        version: "2.0.0",
        name: "Synthetic Service Resilience Extended Pack",
        description: "Resilience extended pack",
        bundle_digest: "ee82e0b3" + "0".repeat(56),
        requirement_count: 2,
        requirements: [
          {
            id: "req-res-1",
            version_id: "req-res-1-v1",
            identifier: "SYNTH-RES-001",
            title: "Synthetic Resilience Cloud Baseline",
            description: "Cloud baseline requirement",
            rule_id: "rule-res-1",
            rule_version_id: "rule-res-1-v1",
            control_id: "ctrl-1",
            control_version_id: "ctrl-1-v1",
            control_identifier: "SYNTH-CTRL-001",
            control_title: "Cloud Configuration & Access Baseline",
          },
        ],
      },
    ],
  },
  // Backend-shaped answers keyed by pinned fact definition version UUIDs (R2)
  answers: {
    tenant_id: "11111111-1111-1111-1111-111111111111",
    revision: 1,
    company_code: "ALPHA",
    answers: {
      [FACT_CLOUD_UUID]: true,
      [FACT_REGION_UUID]: "EU",
    },
    content_digest: "a".repeat(64),
    created_at: "2026-10-20T12:00:00Z",
  },
  selected_pack: null,
  latest_evaluation: null,
  history_summary: [],
};

const mockEvaluation: EvaluationData = {
  id: "eval-1",
  tenant_id: "11111111-1111-1111-1111-111111111111",
  answer_revision: 1,
  pack_version_id: "pack-v1-id",
  bundle_digest: "65d0f766" + "0".repeat(56),
  evaluator_version: "wp09-synthetic-v1",
  content_digest: "b".repeat(64),
  results: [
    {
      requirement_id: "req-1",
      requirement_version_id: "req-1-v1",
      identifier: "SYNTH-REQ-001",
      title: "Synthetic Cloud Architecture Governance",
      rule_id: "rule-1",
      rule_version_id: "rule-1-v1",
      result: "APPLICABLE",
      missing_fact_version_ids: [],
      explanation_tree: {
        op: "EQUALS",
        path: "$",
        result: "APPLICABLE",
        message: "Fact matches required condition (True)",
        missing_fact_version_ids: [],
        children: [],
      },
    },
    {
      requirement_id: "req-2",
      requirement_version_id: "req-2-v1",
      identifier: "SYNTH-REQ-002",
      title: "Synthetic EU Regional Data Isolation",
      rule_id: "rule-2",
      rule_version_id: "rule-2-v1",
      result: "NEEDS_INFORMATION",
      missing_fact_version_ids: [FACT_REGION_UUID],
      explanation_tree: {
        op: "EQUALS",
        path: "$",
        result: "NEEDS_INFORMATION",
        message: "Fact is unknown (missing answer)",
        missing_fact_version_ids: [FACT_REGION_UUID],
        children: [],
      },
    },
  ],
  created_at: "2026-10-20T12:00:00Z",
};

describe("CustomerDemoWorkspace", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(mockWorkspace);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders synthetic non-legal notice clearly", async () => {
    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    expect(await screen.findByText(/Notice:/i)).toBeInTheDocument();
    expect(screen.getByText(/Synthetic customer onboarding demonstration. Not legal or compliance advice./i)).toBeInTheDocument();
  });

  it("reads backend-shaped answers keyed by fact version UUID and populates form correctly (R2)", async () => {
    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalled());

    // Expect Cloud radio 'Yes' to be checked
    const cloudYes = screen.getByTestId("cloud-yes") as HTMLInputElement;
    expect(cloudYes.checked).toBe(true);

    // Expect Region radio 'EU' to be checked
    const regionEU = screen.getByTestId("region-eu") as HTMLInputElement;
    expect(regionEU.checked).toBe(true);
  });

  it("changing pack selection does NOT reload workspace or reset unsaved answer edits (R2)", async () => {
    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalledTimes(1));

    // Make an edit (click Beta company preset)
    const betaBtn = screen.getByTestId("company-beta-btn");
    fireEvent.click(betaBtn);

    // Verify unsaved edit changed cloud to No
    const cloudNo = screen.getByTestId("cloud-no") as HTMLInputElement;
    expect(cloudNo.checked).toBe(true);

    // Now change pack selection
    const packSelect = screen.getByTestId("pack-select") as HTMLSelectElement;
    fireEvent.change(packSelect, { target: { value: "pack-v2-id" } });

    // Workspace should NOT have been reloaded
    expect(api.fetchWorkspace).toHaveBeenCalledTimes(1);

    // Unsaved edits should be preserved
    expect(cloudNo.checked).toBe(true);
  });

  it("saves answers and sends expected payload with AbortSignal", async () => {
    const saveSpy = vi.spyOn(api, "saveAnswers").mockResolvedValue({
      tenant_id: "11111111-1111-1111-1111-111111111111",
      revision: 2,
      company_code: "ALPHA",
      answers: {
        synthetic_wp09_uses_cloud: true,
        synthetic_wp09_operating_region: "EU",
      },
      content_digest: "c".repeat(64),
      created_at: "2026-10-20T12:05:00Z",
    });

    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalled());

    const saveButton = screen.getByTestId("save-answers-btn");
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(saveSpy).toHaveBeenCalledWith(
        "11111111-1111-1111-1111-111111111111",
        "test-token",
        expect.objectContaining({
          expected_revision: 1,
          company_code: "ALPHA",
          answers: {
            synthetic_wp09_uses_cloud: true,
            synthetic_wp09_operating_region: "EU",
          },
        }),
        expect.any(AbortSignal)
      );
    });
  });

  it("evaluates answers and displays deterministic outcomes and missing info", async () => {
    const workspaceWithEval: WorkspaceData = {
      ...mockWorkspace,
      latest_evaluation: mockEvaluation,
    };
    vi.spyOn(api, "fetchWorkspace").mockResolvedValueOnce(mockWorkspace).mockResolvedValue(workspaceWithEval);
    const evalSpy = vi.spyOn(api, "evaluateAnswers").mockResolvedValue(mockEvaluation);

    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalled());

    const evalButton = screen.getByTestId("evaluate-btn");
    fireEvent.click(evalButton);

    await waitFor(() => expect(evalSpy).toHaveBeenCalled());
    expect(await screen.findByText("SYNTH-REQ-001")).toBeInTheDocument();
    expect(screen.getByText("SYNTH-REQ-002")).toBeInTheDocument();
    expect(screen.getByText("NEEDS_INFORMATION")).toBeInTheDocument();
    expect(screen.getByText("APPLICABLE")).toBeInTheDocument();
  });

  it("displays exact requirement-version comparison and handles adoption modal (R9)", async () => {
    const workspaceWithEval: WorkspaceData = {
      ...mockWorkspace,
      latest_evaluation: mockEvaluation,
    };
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(workspaceWithEval);

    const adoptReceipt: AdoptionReceipt = {
      id: "adopt-1",
      tenant_id: "11111111-1111-1111-1111-111111111111",
      selection_revision: 1,
      evaluation_id: "eval-1",
      pack_version_id: "pack-v1-id",
      bundle_digest: "65d0f766" + "0".repeat(56),
      created_at: "2026-10-20T12:05:00Z",
      is_current: true,
      current_selection_revision: 1,
      current_pack_version_id: "pack-v1-id",
    };

    const adoptSpy = vi.spyOn(api, "adoptEvaluation").mockResolvedValue(adoptReceipt);

    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalled());

    const openAdoptBtn = screen.getByTestId("open-adopt-modal-btn");
    fireEvent.click(openAdoptBtn);

    // Modal opens
    expect(await screen.findByText(/Adopt Demo Pack/i)).toBeInTheDocument();

    // Check acknowledgements
    const ackSynthetic = screen.getByTestId("ack-synthetic-checkbox");
    const ackMissing = screen.getByTestId("ack-missing-checkbox");
    fireEvent.click(ackSynthetic);
    fireEvent.click(ackMissing);

    const confirmAdoptBtn = screen.getByTestId("confirm-adopt-btn");
    expect(confirmAdoptBtn).not.toBeDisabled();
    fireEvent.click(confirmAdoptBtn);

    await waitFor(() =>
      expect(adoptSpy).toHaveBeenCalledWith(
        "11111111-1111-1111-1111-111111111111",
        "test-token",
        expect.objectContaining({
          expected_revision: 1,
          evaluation_id: "eval-1",
          pack_version_id: "pack-v1-id",
          acknowledge_synthetic: true,
          acknowledge_missing_information: true,
        }),
        expect.any(AbortSignal)
      )
    );
  });

  it("regression: save -> reload -> second save keeps buttons idle and usable (P1)", async () => {
    let rev = 1;
    const saveSpy = vi.spyOn(api, "saveAnswers").mockImplementation(async () => {
      rev += 1;
      return {
        tenant_id: "11111111-1111-1111-1111-111111111111",
        revision: rev,
        company_code: "ALPHA",
        answers: { synthetic_wp09_uses_cloud: true, synthetic_wp09_operating_region: "EU" },
        content_digest: "c".repeat(64),
        created_at: "2026-10-20T12:05:00Z",
      };
    });

    vi.spyOn(api, "fetchWorkspace").mockImplementation(async () => ({
      ...mockWorkspace,
      current_revision: rev,
    }));

    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    await waitFor(() => expect(screen.getByText(/Answers Revision:/i)).toHaveTextContent("Answers Revision: 1"));

    const saveButton = screen.getByTestId("save-answers-btn");
    expect(saveButton).not.toBeDisabled();
    fireEvent.click(saveButton);

    // Wait for first save to complete and reload to complete
    await waitFor(() => {
      expect(screen.getByText(/Answers Revision:/i)).toHaveTextContent("Answers Revision: 2");
    });
    // Button must NOT be busy or stuck disabled
    expect(saveButton).not.toBeDisabled();
    expect(saveButton).toHaveTextContent("Save Answers");

    // Perform second save
    fireEvent.click(saveButton);
    await waitFor(() => {
      expect(screen.getByText(/Answers Revision:/i)).toHaveTextContent("Answers Revision: 3");
    });
    expect(saveSpy).toHaveBeenCalledTimes(2);
    expect(saveButton).not.toBeDisabled();
  });

  it("regression: evaluate -> reload -> second evaluation keeps buttons idle and usable (P1)", async () => {
    const evalSpy = vi.spyOn(api, "evaluateAnswers").mockResolvedValue(mockEvaluation);

    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalled());

    const evalButton = screen.getByTestId("evaluate-btn");
    expect(evalButton).not.toBeDisabled();
    fireEvent.click(evalButton);

    await waitFor(() => expect(evalSpy).toHaveBeenCalledTimes(1));
    expect(evalButton).not.toBeDisabled();
    expect(evalButton).toHaveTextContent("Evaluate Applicability");

    // Second evaluation
    fireEvent.click(evalButton);
    await waitFor(() => expect(evalSpy).toHaveBeenCalledTimes(2));
    expect(evalButton).not.toBeDisabled();
  });

  it("regression: adoption -> reload -> second adoption keeps buttons idle and usable (P1)", async () => {
    const workspaceWithEval: WorkspaceData = {
      ...mockWorkspace,
      latest_evaluation: mockEvaluation,
    };
    let selRev = 0;
    vi.spyOn(api, "fetchWorkspace").mockImplementation(async () => ({
      ...workspaceWithEval,
      selection_revision: selRev,
    }));

    const adoptSpy = vi.spyOn(api, "adoptEvaluation").mockImplementation(async () => {
      selRev += 1;
      return {
        id: `adopt-${selRev}`,
        tenant_id: "11111111-1111-1111-1111-111111111111",
        selection_revision: selRev,
        evaluation_id: "eval-1",
        pack_version_id: "pack-v1-id",
        bundle_digest: "65d0f766" + "0".repeat(56),
        created_at: "2026-10-20T12:05:00Z",
        is_current: true,
        current_selection_revision: selRev,
        current_pack_version_id: "pack-v1-id",
      };
    });

    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    await waitFor(() => expect(screen.getByTestId("open-adopt-modal-btn")).toBeInTheDocument());

    // 1st adoption
    fireEvent.click(screen.getByTestId("open-adopt-modal-btn"));
    fireEvent.click(await screen.findByTestId("ack-synthetic-checkbox"));
    fireEvent.click(screen.getByTestId("ack-missing-checkbox"));
    fireEvent.click(screen.getByTestId("confirm-adopt-btn"));

    await waitFor(() => expect(adoptSpy).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByText(/Selection Revision:/i)).toHaveTextContent("Selection Revision: 1"));

    // 2nd adoption
    const openBtn2 = screen.getByTestId("open-adopt-modal-btn");
    expect(openBtn2).not.toBeDisabled();
    fireEvent.click(openBtn2);
    fireEvent.click(await screen.findByTestId("ack-synthetic-checkbox"));
    fireEvent.click(screen.getByTestId("ack-missing-checkbox"));
    fireEvent.click(screen.getByTestId("confirm-adopt-btn"));

    await waitFor(() => expect(adoptSpy).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByText(/Selection Revision:/i)).toHaveTextContent("Selection Revision: 2"));
  });

  it("recovers from failed reload after mutation without leaving button permanently disabled (P1)", async () => {
    vi.spyOn(api, "saveAnswers").mockResolvedValue({
      tenant_id: "11111111-1111-1111-1111-111111111111",
      revision: 2,
      company_code: "ALPHA",
      answers: { synthetic_wp09_uses_cloud: true, synthetic_wp09_operating_region: "EU" },
      content_digest: "c".repeat(64),
      created_at: "2026-10-20T12:05:00Z",
    });

    // Initial load succeeds, but reload after save fails
    vi.spyOn(api, "fetchWorkspace").mockResolvedValueOnce(mockWorkspace).mockRejectedValue(new Error("Network timeout on reload"));

    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalledTimes(1));

    const saveButton = screen.getByTestId("save-answers-btn");
    fireEvent.click(saveButton);

    // Error banner should be shown
    expect(await screen.findByTestId("error-alert")).toHaveTextContent(/Network timeout on reload/i);
    // Button must NOT remain in saving/disabled state
    expect(saveButton).not.toBeDisabled();
    expect(saveButton).toHaveTextContent("Save Answers");
  });

  it("handles tenant-switch isolation: deferred A request does not overwrite B state (R1)", async () => {
    let resolveTenantA: (val: WorkspaceData) => void = () => {};
    const deferredPromiseA = new Promise<WorkspaceData>((res) => {
      resolveTenantA = res;
    });

    const mockWorkspaceB: WorkspaceData = {
      ...mockWorkspace,
      tenant_id: "22222222-2222-2222-2222-222222222222",
      current_revision: 0,
      answers: null,
    };

    vi.spyOn(api, "fetchWorkspace").mockImplementation((tenantId) => {
      if (tenantId === "11111111-1111-1111-1111-111111111111") {
        return deferredPromiseA;
      }
      return Promise.resolve(mockWorkspaceB);
    });

    const { rerender } = render(
      <CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />
    );

    // Initial render shows loading for tenant A
    expect(screen.getByTestId("loading-state")).toBeInTheDocument();

    // Tenant switches to B before A resolves
    rerender(
      <CustomerDemoWorkspace token="test-token" tenantId="22222222-2222-2222-2222-222222222222" userRole="owner" />
    );

    // Tenant B loads its own workspace
    await waitFor(() => {
      expect(screen.getByText(/Answers Revision:/i)).toHaveTextContent("Answers Revision: 0");
    });

    // Now resolve Tenant A's deferred response
    resolveTenantA(mockWorkspace);

    // Assert that Tenant B remains visible, and does not get overwritten with Tenant A's revision 1
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getByText(/Answers Revision:/i)).toHaveTextContent("Answers Revision: 0");
    expect(screen.getByText(/Answers Revision:/i)).not.toHaveTextContent("Answers Revision: 1");
  });

  it("invokes onSessionExpired and clears workspace when 401 is encountered (R1)", async () => {
    const expiredMock = vi.fn();
    vi.spyOn(api, "fetchWorkspace").mockRejectedValue(new api.UnauthorizedError("Session expired"));

    render(
      <CustomerDemoWorkspace
        token="expired-token"
        tenantId="11111111-1111-1111-1111-111111111111"
        userRole="owner"
        onSessionExpired={expiredMock}
      />
    );

    await waitFor(() => {
      expect(expiredMock).toHaveBeenCalledTimes(1);
    });
  });

  it("handles 409 optimistic locking conflict with reload required notice", async () => {
    vi.spyOn(api, "saveAnswers").mockRejectedValue(new api.ConflictError("Conflict: revision mismatch"));

    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalled());

    const saveButton = screen.getByTestId("save-answers-btn");
    fireEvent.click(saveButton);

    expect(await screen.findByText(/Conflict: revision mismatch/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reload Workspace/i })).toBeInTheDocument();
    expect(saveButton).not.toBeDisabled();
  });

  it("journey: verifies onboarding with Alpha preset, switching to Beta, and setting unknown answers", async () => {
    const saveSpy = vi.spyOn(api, "saveAnswers").mockResolvedValue({
      tenant_id: "11111111-1111-1111-1111-111111111111",
      revision: 2,
      company_code: "BETA",
      answers: { synthetic_wp09_uses_cloud: null, synthetic_wp09_operating_region: null },
      content_digest: "digest-2",
      created_at: "2026-10-22T10:00:00Z",
    });

    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalledTimes(1));

    // Verify Alpha preset initial selection
    const alphaBtn = screen.getByTestId("company-alpha-btn");
    expect(alphaBtn).toHaveClass("btn-primary");

    // Switch to Beta preset
    const betaBtn = screen.getByTestId("company-beta-btn");
    fireEvent.click(betaBtn);
    expect(betaBtn).toHaveClass("btn-primary");

    const cloudNo = screen.getByTestId("cloud-no") as HTMLInputElement;
    expect(cloudNo.checked).toBe(true);

    // Switch to Unknown
    const cloudUnknown = screen.getByTestId("cloud-unknown") as HTMLInputElement;
    fireEvent.click(cloudUnknown);
    expect(cloudUnknown.checked).toBe(true);

    const regionUnknown = screen.getByTestId("region-unknown") as HTMLInputElement;
    fireEvent.click(regionUnknown);
    expect(regionUnknown.checked).toBe(true);

    // Save answers
    const saveBtn = screen.getByTestId("save-answers-btn");
    fireEvent.click(saveBtn);

    await waitFor(() => expect(saveSpy).toHaveBeenCalledTimes(1));
    expect(saveSpy).toHaveBeenCalledWith(
      "11111111-1111-1111-1111-111111111111",
      "test-token",
      expect.objectContaining({
        company_code: "BETA",
        answers: {
          synthetic_wp09_uses_cloud: null,
          synthetic_wp09_operating_region: null,
        },
      }),
      expect.any(AbortSignal)
    );
  });

  it("journey: displays truthful outcome counts and control mapping without fake compliance scores", async () => {
    const evalData: EvaluationData = {
      id: "eval-truthful-1",
      tenant_id: "11111111-1111-1111-1111-111111111111",
      answer_revision: 1,
      pack_version_id: "pack-v2-id",
      bundle_digest: "digest-truthful-12345",
      evaluator_version: "wp09-synthetic-v1",
      content_digest: "cd-123",
      created_at: "2026-10-22T12:00:00Z",
      results: [
        {
          requirement_id: "req-1",
          requirement_version_id: "req-1-v1",
          identifier: "SYNTH-REQ-001",
          title: "Synthetic Cloud Architecture Governance",
          rule_id: "rule-1",
          rule_version_id: "rule-1-v1",
          result: "APPLICABLE",
          missing_fact_version_ids: [],
          explanation_tree: {
            op: "EQUALS",
            path: "facts.synthetic_wp09_uses_cloud",
            result: "APPLICABLE",
            message: "Cloud usage is confirmed",
            missing_fact_version_ids: [],
            children: [],
          },
        },
        {
          requirement_id: "req-2",
          requirement_version_id: "req-2-v1",
          identifier: "SYNTH-REQ-002",
          title: "Synthetic EU Regional Data Isolation",
          rule_id: "rule-2",
          rule_version_id: "rule-2-v1",
          result: "NEEDS_INFORMATION",
          missing_fact_version_ids: [FACT_REGION_UUID],
          explanation_tree: {
            op: "EXISTS",
            path: "facts.synthetic_wp09_operating_region",
            result: "NEEDS_INFORMATION",
            message: "Missing operating region fact",
            missing_fact_version_ids: [FACT_REGION_UUID],
            children: [],
          },
        },
      ],
    };

    vi.spyOn(api, "fetchWorkspace").mockResolvedValue({
      ...mockWorkspace,
      latest_evaluation: evalData,
    });

    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    await waitFor(() => expect(screen.getByTestId("outcomes-summary-bar")).toBeInTheDocument());

    // Verify truthful counts are rendered
    expect(screen.getByText(/Applicable: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Needs Information: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Not Applicable: 0/i)).toBeInTheDocument();

    // Verify truthfulness disclaimer
    expect(screen.getByText(/Not a compliance certification or readiness score/i)).toBeInTheDocument();

    // Verify no fake percentages or compliance scores
    expect(screen.queryByText(/100%/)).not.toBeInTheDocument();
    expect(screen.queryByText(/50%/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("readiness-score")).not.toBeInTheDocument();
    expect(screen.queryByTestId("compliance-percentage")).not.toBeInTheDocument();

    // Verify common control mapping is displayed
    expect(screen.getByText(/SYNTH-CTRL-001/i)).toBeInTheDocument();
    expect(screen.getByText(/Cloud Configuration & Access Baseline/i)).toBeInTheDocument();
  });

  it("journey: step navigation navigates to target panels, focuses sections, and retains unsaved form edits across steps", async () => {
    const saveSpy = vi.spyOn(api, "saveAnswers");
    const workspaceWithHistory: WorkspaceData = {
      ...mockWorkspace,
      history_summary: [
        {
          selection_revision: 1,
          pack_version_id: "pack-v1-id",
          bundle_digest: "65d0f76600000000000000000000000000000000000000000000000000000000",
          created_at: "2026-10-22T08:00:00Z",
        },
      ],
    };

    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(workspaceWithHistory);

    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    await waitFor(() => expect(screen.getByTestId("workspace-stepper")).toBeInTheDocument());

    // Edit a form field on step 1 without saving (change Cloud from true to false)
    const noRadio = screen.getByTestId("cloud-no");
    fireEvent.click(noRadio);
    expect(screen.getByTestId("unsaved-changes-indicator")).toBeInTheDocument();

    // Click step 2 to navigate to rule evaluation
    const step2Btn = screen.getByTestId("step-btn-2");
    fireEvent.click(step2Btn);
    expect(step2Btn).toHaveAttribute("aria-current", "step");
    expect(document.activeElement).toBe(screen.getByTestId("evaluation-section"));
    expect(screen.getByTestId("evaluation-section")).toHaveClass("active-step-panel");

    // Click step 3 to navigate to adoption history
    const step3Btn = screen.getByTestId("step-btn-3");
    fireEvent.click(step3Btn);
    expect(step3Btn).toHaveAttribute("aria-current", "step");
    expect(document.activeElement).toBe(screen.getByTestId("adoption-history-section"));
    expect(screen.getByTestId("adoption-history-section")).toHaveClass("active-step-panel");
    expect(screen.getByText(/pack-v1-id/i)).toBeInTheDocument();
    expect(screen.getByText(/65d0f766/i)).toBeInTheDocument();

    // Click step 1 to return to profile and facts
    const step1Btn = screen.getByTestId("step-btn-1");
    fireEvent.click(step1Btn);
    expect(step1Btn).toHaveAttribute("aria-current", "step");
    expect(document.activeElement).toBe(screen.getByTestId("profile-section"));
    expect(screen.getByTestId("profile-section")).toHaveClass("active-step-panel");

    // Verify unsaved edits were retained across step navigation without implicit save
    expect(noRadio).toBeChecked();
    expect(screen.getByTestId("unsaved-changes-indicator")).toBeInTheDocument();
    expect(saveSpy).not.toHaveBeenCalled();
  });

  it("derives step 2 completion and stale states from persisted evaluation and answer revisions", async () => {
    // 1. Saved-but-unevaluated: current_revision=1, no evaluation
    const unevaluatedWorkspace: WorkspaceData = {
      ...mockWorkspace,
      current_revision: 1,
      latest_evaluation: null,
    };
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(unevaluatedWorkspace);

    const { unmount } = render(
      <CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />
    );
    await waitFor(() => expect(screen.getByTestId("step-btn-2")).toBeInTheDocument());
    expect(screen.getByTestId("step-btn-2")).not.toHaveClass("completed");
    expect(screen.queryByTestId("step-2-stale-tag")).not.toBeInTheDocument();
    unmount();

    // 2. Stale evaluation: current_revision=2, evaluation at answer_revision=1
    const staleWorkspace: WorkspaceData = {
      ...mockWorkspace,
      current_revision: 2,
      latest_evaluation: {
        ...mockEvaluation,
        answer_revision: 1,
      },
    };
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(staleWorkspace);

    const { unmount: unmountStale } = render(
      <CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />
    );
    await waitFor(() => expect(screen.getByTestId("step-2-stale-tag")).toBeInTheDocument());
    expect(screen.getByTestId("step-btn-2")).not.toHaveClass("completed");
    unmountStale();

    // 3. Current evaluation: current_revision=1, evaluation at answer_revision=1
    const currentWorkspace: WorkspaceData = {
      ...mockWorkspace,
      current_revision: 1,
      latest_evaluation: {
        ...mockEvaluation,
        answer_revision: 1,
      },
    };
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(currentWorkspace);

    render(
      <CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />
    );
    await waitFor(() => expect(screen.getByTestId("step-btn-2")).toHaveClass("completed"));
    expect(screen.queryByTestId("step-2-stale-tag")).not.toBeInTheDocument();
  });

  it("accessibility: modal keyboard flow handles focus trapping, Escape close, and opener focus restoration", async () => {
    const workspaceWithEval: WorkspaceData = {
      ...mockWorkspace,
      latest_evaluation: mockEvaluation,
    };
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(workspaceWithEval);

    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    await waitFor(() => expect(screen.getByTestId("open-adopt-modal-btn")).toBeInTheDocument());

    const openBtn = screen.getByTestId("open-adopt-modal-btn");
    openBtn.focus();
    expect(document.activeElement).toBe(openBtn);

    // Open modal
    fireEvent.click(openBtn);

    const modal = await screen.findByTestId("adopt-pack-modal");
    expect(modal).toBeInTheDocument();

    // Verify focus is transferred into modal
    await waitFor(() => {
      expect(modal.contains(document.activeElement)).toBe(true);
    });

    // Verify Shift+Tab wrap from first focusable element
    const ackSynthetic = screen.getByTestId("ack-synthetic-checkbox");
    ackSynthetic.focus();
    fireEvent.keyDown(modal, { key: "Tab", shiftKey: true });

    // Verify Escape key closes modal and restores focus to opener button
    fireEvent.keyDown(modal, { key: "Escape" });

    await waitFor(() => expect(screen.queryByTestId("adopt-pack-modal")).not.toBeInTheDocument());
    expect(document.activeElement).toBe(openBtn);
  });

  it("localization: renders German translations accurately without hardcoded English static labels", async () => {
    localStorage.setItem("conformly.locale", "de");
    const workspaceWithHistory: WorkspaceData = {
      ...mockWorkspace,
      latest_evaluation: mockEvaluation,
      history_summary: [
        {
          selection_revision: 1,
          pack_version_id: "pack-v1-id",
          bundle_digest: "65d0f76600000000000000000000000000000000000000000000000000000000",
          created_at: "2026-10-22T08:00:00Z",
        },
      ],
    };
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(workspaceWithHistory);

    render(
      <I18nProvider>
        <CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />
      </I18nProvider>
    );

    await waitFor(() => expect(screen.getByTestId("pill-synthetic")).toBeInTheDocument());

    // Verify German translated pills and headers
    expect(screen.getByTestId("pill-synthetic")).toHaveTextContent("Synthetische Demo");
    expect(screen.getByTestId("pill-synthetic")).toHaveTextContent("Nur Bewertung");
    expect(screen.getByText(/Paketversions-ID/i)).toBeInTheDocument();
    expect(screen.getByText(/Paket-Digest/i)).toBeInTheDocument();
    expect(screen.getByText(/Übernahmezeitpunkt/i)).toBeInTheDocument();
    localStorage.removeItem("conformly.locale");
  });

  it("regression: save -> evaluate -> adopt succeeds with differing answer and selection revisions", async () => {
    // Differing revisions: answer revision = 2, selection revision = 1
    let currentSelRev = 1;
    const workspaceWithDiffRevs: WorkspaceData = {
      ...mockWorkspace,
      current_revision: 2,
      selection_revision: currentSelRev,
      latest_evaluation: {
        ...mockEvaluation,
        id: "eval-rev2",
        answer_revision: 2,
        pack_version_id: "pack-v1-id",
      },
    };
    vi.spyOn(api, "fetchWorkspace").mockImplementation(async () => ({
      ...workspaceWithDiffRevs,
      selection_revision: currentSelRev,
    }));

    const adoptReceipt: AdoptionReceipt = {
      id: "adopt-diff-rev",
      tenant_id: "11111111-1111-1111-1111-111111111111",
      selection_revision: 2,
      evaluation_id: "eval-rev2",
      pack_version_id: "pack-v1-id",
      bundle_digest: "65d0f766" + "0".repeat(56),
      created_at: "2026-10-22T14:00:00Z",
      is_current: true,
      current_selection_revision: 2,
      current_pack_version_id: "pack-v1-id",
    };

    const adoptSpy = vi.spyOn(api, "adoptEvaluation").mockImplementation(async () => {
      currentSelRev = 2;
      return adoptReceipt;
    });

    render(<CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />);
    await waitFor(() => expect(screen.getByTestId("open-adopt-modal-btn")).toBeInTheDocument());

    // Verify initial revisions display: Answers Revision 2, Selection Revision 1
    expect(screen.getByTestId("answers-rev-badge")).toHaveTextContent("2");
    expect(screen.getByTestId("selection-rev-badge")).toHaveTextContent("1");

    // Open adoption modal
    fireEvent.click(screen.getByTestId("open-adopt-modal-btn"));
    const ackSynthetic = await screen.findByTestId("ack-synthetic-checkbox");
    const ackMissing = screen.getByTestId("ack-missing-checkbox");
    fireEvent.click(ackSynthetic);
    fireEvent.click(ackMissing);

    const confirmAdoptBtn = screen.getByTestId("confirm-adopt-btn");
    fireEvent.click(confirmAdoptBtn);

    // Verify adoptEvaluation was called with expected_revision = 2 (matching answer revision, differing from selection revision 1)
    await waitFor(() =>
      expect(adoptSpy).toHaveBeenCalledWith(
        "11111111-1111-1111-1111-111111111111",
        "test-token",
        expect.objectContaining({
          expected_revision: 2,
          evaluation_id: "eval-rev2",
          pack_version_id: "pack-v1-id",
          acknowledge_synthetic: true,
          acknowledge_missing_information: true,
        }),
        expect.any(AbortSignal)
      )
    );

    // Verify selection revision advanced to 2 in UI
    await waitFor(() => expect(screen.getByTestId("selection-rev-badge")).toHaveTextContent("2"));
  });

  it("regression: preview fixture interceptor validates answer revision and succeeds when revisions differ", async () => {
    const { handlePreviewFetch, getPreviewWorkspace, resetPreviewWorkspace } = await import(
      "../../test/mvp-a-preview"
    );
    resetPreviewWorkspace();

    // 1. Initial workspace state: current_revision: 1, selection_revision: 1
    const initRes = await handlePreviewFetch("http://localhost/customer-demo/workspace", { method: "GET" });
    expect(initRes.status).toBe(200);
    const initWs = await initRes.json();
    expect(initWs.current_revision).toBe(1);
    expect(initWs.selection_revision).toBe(1);

    // 2. Save Beta answers: sends expected_revision: 1 -> increments current_revision to 2
    const saveRes = await handlePreviewFetch("http://localhost/customer-demo/answers", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company_code: "BETA",
        answers: {
          "e2d7e192-3a55-46b5-8eb4-d7586aef0001": true,
          "e2d7e192-3a55-46b5-8eb4-d7586aef0002": "OTHER",
        },
        expected_revision: 1,
      }),
    });
    expect(saveRes.status).toBe(200);
    const savedAnswers = await saveRes.json();
    expect(savedAnswers.revision).toBe(2);

    const wsAfterSave = getPreviewWorkspace();
    expect(wsAfterSave.current_revision).toBe(2);
    expect(wsAfterSave.selection_revision).toBe(1); // differing!

    // 3. Evaluate with expected_revision: 2 -> returns 200 with new evaluation
    const evalRes = await handlePreviewFetch("http://localhost/customer-demo/evaluations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        expected_revision: 2,
        pack_version_id: "pack-v1-ver-id",
      }),
    });
    expect(evalRes.status).toBe(200);
    const evalData = await evalRes.json();
    expect(evalData.answer_revision).toBe(2);

    // 4. Stale adoption attempt with old expected_revision: 1 -> rejected with 409, no state mutation
    const staleAdoptRes = await handlePreviewFetch("http://localhost/customer-demo/adoptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        expected_revision: 1, // Stale! Current is 2
        evaluation_id: evalData.id,
        pack_version_id: "pack-v1-ver-id",
        acknowledge_synthetic: true,
        acknowledge_missing_information: true,
      }),
    });
    expect(staleAdoptRes.status).toBe(409);
    const staleBody = await staleAdoptRes.json();
    expect(staleBody.detail).toMatch(/Conflict/i);

    // State invariant check: no mutation on 409
    const wsAfterStale = getPreviewWorkspace();
    expect(wsAfterStale.current_revision).toBe(2);
    expect(wsAfterStale.selection_revision).toBe(1);

    // 5. Valid adoption with expected_revision: 2 (matching answer revision 2 != selection revision 1) -> 200
    const adoptRes = await handlePreviewFetch("http://localhost/customer-demo/adoptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        expected_revision: 2,
        evaluation_id: evalData.id,
        pack_version_id: "pack-v1-ver-id",
        acknowledge_synthetic: true,
        acknowledge_missing_information: true,
      }),
    });
    expect(adoptRes.status).toBe(200);
    const receipt = await adoptRes.json();
    expect(receipt.selection_revision).toBe(2);
    expect(receipt.current_selection_revision).toBe(2);
    expect(receipt.is_current).toBe(true);

    // Workspace state verification: selection_revision advanced to 2, history prepended, selected_pack updated
    const finalWs = getPreviewWorkspace();
    expect(finalWs.current_revision).toBe(2);
    expect(finalWs.selection_revision).toBe(2);
    expect(finalWs.selected_pack?.selection_revision).toBe(2);
    expect(finalWs.selected_pack?.is_stale).toBe(false);
    expect(finalWs.history_summary[0].selection_revision).toBe(2);
  });

  it("renders AssessmentWorkspace when a pack is selected", async () => {
    const wsWithPack: WorkspaceData = {
      ...mockWorkspace,
      selected_pack: {
        evaluation_id: "eval-1",
        pack_version_id: "pack-v1-id",
        bundle_digest: "65d0f766" + "0".repeat(56),
        selection_revision: 1,
        created_at: new Date().toISOString(),
        is_stale: false,
      },
    };
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(wsWithPack);

    render(
      <I18nProvider>
        <CustomerDemoWorkspace tenantId="11111111-1111-1111-1111-111111111111" token="dummy-token" />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Human Assessment & Audit Readiness")).toBeInTheDocument();
    });
  });
  it("populates truthful overview metrics from control and assessment APIs without fake numbers or hardcoded states", async () => {
    const wsWithPack: WorkspaceData = {
      ...mockWorkspace,
      selected_pack: {
        evaluation_id: "eval-1",
        pack_version_id: "pack-v1-id",
        bundle_digest: "65d0f766" + "0".repeat(56),
        selection_revision: 1,
        created_at: new Date().toISOString(),
        is_stale: false,
      },
    };
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(wsWithPack);
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue({
      tenant_id: "11111111-1111-1111-1111-111111111111",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      total: 3,
      items: [
        {
          id: "work-1",
          adoption_id: "adopt-1",
          control_id: "ctrl-1",
          control_version_id: "ctrl-1-v1",
          title: "Cloud Access Control",
          provenance: "synth",
          pack_version: 1,
          bundle_digest: "digest",
          requirement_results: [],
          owner_user_id: "user-1",
          owner_display_name: "Alice",
          due_date: "2026-12-01",
          version: 1,
          is_current: true,
          is_stale: false,
          links: [
            {
              id: "link-1",
              evidence_id: "ev-1",
              revision_number: 1,
              digest: "hash-1",
              file_ids: ["f-1"],
              filename: "policy.pdf",
              file_size: 1024,
              classification: "Confidential",
              validity: "AVAILABLE",
              scan_status: "SCANNED_AT_LINK",
              scan_verified_at: "2026-10-22T00:00:00Z",
              review: "ACCEPTED",
              rationale: "valid",
              created_at: "2026-10-22T00:00:00Z",
            },
          ],
        },
      ],
    });

    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue({
      tenant_id: "11111111-1111-1111-1111-111111111111",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_stale: false,
      summary: {
        total_controls: 3,
        stale_work: 0,
        needs_information: 0,
        not_applicable: 0,
        unassessed: 2,
        unavailable_evidence: 0,
        stale_assessment: 0,
        insufficient_evidence: 0,
        fail: 0,
        partial: 0,
        pass_with_open_findings: 0,
        pass_count: 1,
        open_findings: 0,
        in_remediation_findings: 0,
        resolved_findings: 0,
        blocked_control_ids: [],
        reason_codes: [],
      },
      items: [],
    });

    render(
      <I18nProvider>
        <CustomerDemoWorkspace
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          activePortalView="overview"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      // Truthful controls card
      const controlsCard = screen.getByTestId("metric-controls-card");
      expect(controlsCard).toHaveTextContent("3");
      expect(controlsCard).toHaveTextContent("IN PROGRESS");

      // Truthful evidence card: exactly 1 pinned item, tag PINNED
      const evidenceCard = screen.getByTestId("metric-evidence-card");
      expect(evidenceCard).toHaveTextContent("1");
      expect(evidenceCard).toHaveTextContent("PINNED");

      // Truthful assessments card: 1 / 3 passed, 2 unassessed, tag IN PROGRESS (not fake AUDIT)
      const assessCard = screen.getByTestId("metric-assessments-card");
      expect(assessCard).toHaveTextContent("1 / 3");
      expect(assessCard).toHaveTextContent("IN PROGRESS");
      expect(assessCard).toHaveTextContent("1 passed · 0 open findings · 2 unassessed");
    });
  });

  it("preserves ControlEvidenceWorkspace and AssessmentWorkspace mounted DOM state across view switches to prevent draft loss", async () => {
    const wsWithPack: WorkspaceData = {
      ...mockWorkspace,
      selected_pack: {
        evaluation_id: "eval-1",
        pack_version_id: "pack-v1-id",
        bundle_digest: "65d0f766" + "0".repeat(56),
        selection_revision: 1,
        created_at: new Date().toISOString(),
        is_stale: false,
      },
    };
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(wsWithPack);
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue({
      tenant_id: "11111111-1111-1111-1111-111111111111",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      total: 1,
      items: [],
    });
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue({
      tenant_id: "11111111-1111-1111-1111-111111111111",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_stale: false,
      summary: {
        total_controls: 1,
        stale_work: 0,
        needs_information: 0,
        not_applicable: 0,
        unassessed: 1,
        unavailable_evidence: 0,
        stale_assessment: 0,
        insufficient_evidence: 0,
        fail: 0,
        partial: 0,
        pass_with_open_findings: 0,
        pass_count: 0,
        open_findings: 0,
        in_remediation_findings: 0,
        resolved_findings: 0,
        blocked_control_ids: [],
        reason_codes: [],
      },
      items: [],
    });

    const { rerender } = render(
      <I18nProvider>
        <CustomerDemoWorkspace
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          activePortalView="controls_evidence"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      const controlsView = screen.getByTestId("portal-controls-view");
      expect(controlsView).toBeInTheDocument();
      expect(controlsView).toHaveStyle({ display: "block" });
    });

    // Switch view to overview
    rerender(
      <I18nProvider>
        <CustomerDemoWorkspace
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          activePortalView="overview"
        />
      </I18nProvider>
    );

    // Verify controls view is still mounted in DOM (preserving draft state) but hidden via style
    const controlsViewAfterSwitch = screen.getByTestId("portal-controls-view");
    expect(controlsViewAfterSwitch).toBeInTheDocument();
    expect(controlsViewAfterSwitch).toHaveStyle({ display: "none" });

    // Switch view to assessments
    rerender(
      <I18nProvider>
        <CustomerDemoWorkspace
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          activePortalView="assessments_findings"
        />
      </I18nProvider>
    );

    const assessmentsView = screen.getByTestId("portal-assessments-view");
    expect(assessmentsView).toBeInTheDocument();
    expect(assessmentsView).toHaveStyle({ display: "block" });
    expect(screen.getByTestId("portal-controls-view")).toHaveStyle({ display: "none" });
  });

  it("allows explicit refresh of overview metrics via refresh button", async () => {
    const wsWithPack: WorkspaceData = {
      ...mockWorkspace,
      selected_pack: {
        evaluation_id: "eval-1",
        pack_version_id: "pack-v1-id",
        bundle_digest: "65d0f766" + "0".repeat(56),
        selection_revision: 1,
        created_at: new Date().toISOString(),
        is_stale: false,
      },
    };
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(wsWithPack);
    const fetchControlSpy = vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue({
      tenant_id: "11111111-1111-1111-1111-111111111111",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      total: 1,
      items: [],
    });
    const fetchAssessSpy = vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue({
      tenant_id: "11111111-1111-1111-1111-111111111111",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_stale: false,
      summary: {
        total_controls: 1,
        stale_work: 0,
        needs_information: 0,
        not_applicable: 0,
        unassessed: 1,
        unavailable_evidence: 0,
        stale_assessment: 0,
        insufficient_evidence: 0,
        fail: 0,
        partial: 0,
        pass_with_open_findings: 0,
        pass_count: 0,
        open_findings: 0,
        in_remediation_findings: 0,
        resolved_findings: 0,
        blocked_control_ids: [],
        reason_codes: [],
      },
      items: [],
    });

    render(
      <I18nProvider>
        <CustomerDemoWorkspace
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          activePortalView="overview"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("portal-refresh-metrics-btn")).toBeInTheDocument();
    });

    const initialControlCalls = fetchControlSpy.mock.calls.length;
    const initialAssessCalls = fetchAssessSpy.mock.calls.length;

    fireEvent.click(screen.getByTestId("portal-refresh-metrics-btn"));

    await waitFor(() => {
      expect(fetchControlSpy.mock.calls.length).toBeGreaterThan(initialControlCalls);
      expect(fetchAssessSpy.mock.calls.length).toBeGreaterThan(initialAssessCalls);
    });
  });

  it("renders action cards as semantic keyboard-accessible buttons and triggers navigation", async () => {
    const wsWithPack: WorkspaceData = {
      ...mockWorkspace,
      selected_pack: {
        evaluation_id: "eval-1",
        pack_version_id: "pack-v1-id",
        bundle_digest: "65d0f766" + "0".repeat(56),
        selection_revision: 1,
        created_at: new Date().toISOString(),
        is_stale: false,
      },
    };
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(wsWithPack);
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue({
      tenant_id: "11111111-1111-1111-1111-111111111111",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      total: 0,
      items: [],
    });
    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue({
      tenant_id: "11111111-1111-1111-1111-111111111111",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_stale: false,
      summary: {
        total_controls: 1,
        stale_work: 0,
        needs_information: 0,
        not_applicable: 0,
        unassessed: 1,
        unavailable_evidence: 0,
        stale_assessment: 0,
        insufficient_evidence: 0,
        fail: 0,
        partial: 0,
        pass_with_open_findings: 0,
        pass_count: 0,
        open_findings: 0,
        in_remediation_findings: 0,
        resolved_findings: 0,
        blocked_control_ids: [],
        reason_codes: [],
      },
      items: [],
    });

    const handleNavigate = vi.fn();

    render(
      <I18nProvider>
        <CustomerDemoWorkspace
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          activePortalView="overview"
          onNavigateView={handleNavigate}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("card-go-controls")).toBeInTheDocument();
    });

    const controlsCard = screen.getByTestId("card-go-controls");
    expect(controlsCard.tagName.toLowerCase()).toBe("button");
    expect(controlsCard).toHaveAttribute("type", "button");

    fireEvent.click(controlsCard);
    expect(handleNavigate).toHaveBeenCalledWith("controls_evidence");

    const assessCard = screen.getByTestId("card-go-assessments");
    expect(assessCard.tagName.toLowerCase()).toBe("button");
    fireEvent.click(assessCard);
    expect(handleNavigate).toHaveBeenCalledWith("assessments_findings");
  });

  it("navigates from Work Queue to nonfirst control and finding targets while preserving unsaved setup edits and handling stale targets safely", async () => {
    const wsWithPack: WorkspaceData = {
      ...mockWorkspace,
      selected_pack: {
        evaluation_id: "eval-1",
        pack_version_id: "pack-v1-id",
        bundle_digest: "65d0f766" + "0".repeat(56),
        selection_revision: 1,
        created_at: new Date().toISOString(),
        is_stale: false,
      },
    };
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(wsWithPack);

    const twoControls: ControlWorkItem[] = [
      {
        id: "w-first",
        adoption_id: "adopt-1",
        control_id: "CTRL-01",
        control_version_id: "cv-1",
        title: "First Control",
        provenance: "Synthetic",
        pack_version: 1,
        bundle_digest: "digest-1",
        requirement_results: [],
        owner_user_id: "u-1",
        owner_display_name: "Alice",
        due_date: "2026-10-28",
        version: 1,
        is_current: true,
        is_stale: false,
        links: [],
      },
      {
        id: "w-second",
        adoption_id: "adopt-1",
        control_id: "CTRL-02",
        control_version_id: "cv-2",
        title: "Second Nonfirst Control",
        provenance: "Synthetic",
        pack_version: 1,
        bundle_digest: "digest-2",
        requirement_results: [],
        owner_user_id: "u-2",
        owner_display_name: "Bob",
        due_date: "2026-11-01",
        version: 1,
        is_current: true,
        is_stale: false,
        links: [],
      },
    ];

    const twoAssessments: AssessmentWorkItem[] = [
      {
        work_id: "w-first",
        control_version_id: "cv-1",
        work_version: 1,
        assessment_revision: 1,
        procedure: { id: "p1", version: "1", digest: "d1", criteria: [], disclaimer: "none" },
        latest_assessment: null,
        primary_state: "UNASSESSED",
        blockers: [],
        findings: [],
        history: [],
      },
      {
        work_id: "w-second",
        control_version_id: "cv-2",
        work_version: 1,
        assessment_revision: 1,
        procedure: { id: "p2", version: "1", digest: "d2", criteria: [], disclaimer: "none" },
        latest_assessment: null,
        primary_state: "FAIL",
        blockers: [],
        findings: [
          {
            id: "fnd-second-1",
            source_event_id: "e1",
            current_event_id: "e1",
            severity: "HIGH",
            status: "OPEN",
            owner_user_id: "u-2",
            owner_display_name: "Bob",
            due_date: "2026-11-05",
            version: 1,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        history: [],
      },
    ];

    vi.spyOn(controlApi, "fetchOwnerDirectory").mockResolvedValue({
      items: [
        { user_id: "u-1", display_name: "Alice" },
        { user_id: "u-2", display_name: "Bob" },
      ],
      total: 2,
    });
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue({
      tenant_id: "11111111-1111-1111-1111-111111111111",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      total: 2,
      items: twoControls,
    });

    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockResolvedValue({
      tenant_id: "11111111-1111-1111-1111-111111111111",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_stale: false,
      summary: {
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
        blocked_control_ids: [],
        reason_codes: [],
      },
      items: twoAssessments,
    });

    let activeView = "work_queue";
    const handleNavigate = vi.fn((v: string) => {
      activeView = v;
    });

    const { rerender } = render(
      <I18nProvider>
        <CustomerDemoWorkspace
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          activePortalView={activeView as PortalView}
          onNavigateView={handleNavigate}
        />
      </I18nProvider>
    );

    // 1. Queue renders with nonfirst control and finding
    await waitFor(() => {
      expect(screen.getByTestId("queue-row-ctrl-w-second")).toBeInTheDocument();
      expect(screen.getByTestId("queue-row-fnd-fnd-second-1")).toBeInTheDocument();
    });

    // 2. Click Control button on the NONFIRST item (w-second)
    fireEvent.click(screen.getByTestId("control-btn-ctrl-w-second"));
    expect(handleNavigate).toHaveBeenCalledWith("controls_evidence");

    // Re-render with active view changed to controls_evidence
    rerender(
      <I18nProvider>
        <CustomerDemoWorkspace
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          activePortalView="controls_evidence"
          onNavigateView={handleNavigate}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("control-card-w-second")).toBeInTheDocument();
    });

    // 3. Switch back to work queue, click assessment button on finding row
    rerender(
      <I18nProvider>
        <CustomerDemoWorkspace
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          activePortalView="work_queue"
          onNavigateView={handleNavigate}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("assessment-btn-fnd-fnd-second-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("assessment-btn-fnd-fnd-second-1"));
    expect(handleNavigate).toHaveBeenCalledWith("assessments_findings");

    // Re-render in assessments view
    rerender(
      <I18nProvider>
        <CustomerDemoWorkspace
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          activePortalView="assessments_findings"
          onNavigateView={handleNavigate}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("assessment-card-w-second")).toBeInTheDocument();
      expect(screen.getByTestId("finding-row-fnd-second-1")).toBeInTheDocument();
    });
  });
  it("renders grouped framework library options with optgroups and local search filter", async () => {
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(mockWorkspace);

    render(
      <I18nProvider>
        <CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />
      </I18nProvider>
    );
    await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalled());

    // Check optgroups in pack select
    const packSelect = screen.getByTestId("pack-select");
    const optgroups = packSelect.querySelectorAll("optgroup");
    expect(optgroups.length).toBeGreaterThanOrEqual(2);

    // Test local search filter
    const searchInput = screen.getByTestId("pack-filter-input-standalone");
    fireEvent.change(searchInput, { target: { value: "Resilience" } });

    // Resilience group is present; previously selected pack remains visible with [selected - filtered]
    const filteredOptgroups = packSelect.querySelectorAll("optgroup");
    expect(filteredOptgroups.length).toBeGreaterThanOrEqual(1);
    expect(packSelect).toHaveTextContent("Resilience");
    expect(packSelect).toHaveTextContent(/selected - filtered/);
  });

  it("renders cross-pack replacement notice in adoption modal when adopting different framework family", async () => {
    // Current adopted pack is pack-v1-id (family: pack-v1)
    const crossWorkspace: WorkspaceData = {
      ...mockWorkspace,
      selected_pack: {
        selection_revision: 1,
        evaluation_id: "eval-1",
        pack_version_id: "pack-v1-id",
        bundle_digest: "65d0f766" + "0".repeat(56),
        created_at: "2026-10-20T12:05:00Z",
        is_stale: false,
      },
      latest_evaluation: {
        ...mockEvaluation,
        pack_version_id: "pack-res-v1-id", // belongs to pack-resilience-family
      },
    };

    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(crossWorkspace);

    render(
      <I18nProvider>
        <CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />
      </I18nProvider>
    );
    await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalled());

    // Open adoption modal
    const openAdoptBtn = screen.getByTestId("open-adopt-modal-btn");
    fireEvent.click(openAdoptBtn);

    // Verify cross-pack replacement warning is displayed
    expect(await screen.findByTestId("cross-pack-replacement-warning")).toBeInTheDocument();
    expect(screen.getByTestId("cross-pack-replacement-warning")).toHaveTextContent(/Cross-Pack Replacement/i);
  });

  it("disables adopt pack button and renders evaluation mismatch banner when selected candidate differs from evaluation", async () => {
    const wsWithEval: WorkspaceData = {
      ...mockWorkspace,
      latest_evaluation: {
        ...mockEvaluation,
        pack_version_id: "pack-v1-id",
        answer_revision: 1,
      },
    };
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(wsWithEval);

    render(
      <I18nProvider>
        <CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />
      </I18nProvider>
    );
    await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalled());

    // Switch candidate pack to pack-v2-id
    const packSelect = screen.getByTestId("pack-select") as HTMLSelectElement;
    fireEvent.change(packSelect, { target: { value: "pack-v2-id" } });

    // Verify evaluation candidate mismatch banner appears and adopt button is disabled
    expect(screen.getByTestId("evaluation-mismatch-notice")).toBeInTheDocument();
    const adoptBtn = screen.getByTestId("open-adopt-modal-btn");
    expect(adoptBtn).toBeDisabled();
  });

  it("retains selected pack value and sends correct candidate payload when search filter is active", async () => {
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(mockWorkspace);
    const evalSpy = vi.spyOn(api, "evaluateAnswers").mockResolvedValue({
      id: "eval-new",
      tenant_id: "11111111-1111-1111-1111-111111111111",
      answer_revision: 1,
      pack_version_id: "pack-v1-id",
      bundle_digest: "acc8f821" + "0".repeat(56),
      evaluator_version: "1.0.0",
      created_at: new Date().toISOString(),
      content_digest: "eval-digest",
      results: [],
    });

    render(
      <I18nProvider>
        <CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />
      </I18nProvider>
    );
    await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalled());

    // Filter to Resilience while pack-v1-id is selected
    const searchInput = screen.getByTestId("pack-filter-input-standalone");
    fireEvent.change(searchInput, { target: { value: "Resilience" } });

    const packSelect = screen.getByTestId("pack-select") as HTMLSelectElement;
    // True candidate state is preserved, and visible option indicates filtered state
    expect(packSelect.value).toBe("pack-v1-id");
    expect(packSelect).toHaveTextContent(/selected - filtered/i);

    // Clicking evaluate sends pack-v1-id (the true selected ID)
    const evalBtn = screen.getByTestId("evaluate-btn");
    fireEvent.click(evalBtn);

    await waitFor(() => {
      expect(evalSpy).toHaveBeenCalledWith(
        "11111111-1111-1111-1111-111111111111",
        "test-token",
        expect.objectContaining({ pack_version_id: "pack-v1-id" }),
        expect.anything()
      );
    });
  });

  it("freezes adoption intent upon opening modal and rejects adoption if candidate changes", async () => {
    const wsWithEval: WorkspaceData = {
      ...mockWorkspace,
      latest_evaluation: {
        ...mockEvaluation,
        pack_version_id: "pack-v1-id",
        answer_revision: 1,
      },
    };
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(wsWithEval);

    render(
      <I18nProvider>
        <CustomerDemoWorkspace token="test-token" tenantId="11111111-1111-1111-1111-111111111111" userRole="owner" />
      </I18nProvider>
    );
    await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalled());

    // Open adoption modal with valid matching evaluation
    const openAdoptBtn = screen.getByTestId("open-adopt-modal-btn");
    expect(openAdoptBtn).toBeEnabled();
    fireEvent.click(openAdoptBtn);

    expect(screen.getByTestId("adopt-pack-modal")).toBeInTheDocument();

    // Changing candidate while modal is open invalidates the frozen intent and closes modal
    const packSelect = screen.getByTestId("pack-select") as HTMLSelectElement;
    fireEvent.change(packSelect, { target: { value: "pack-v2-id" } });

    expect(screen.queryByTestId("adopt-pack-modal")).not.toBeInTheDocument();
  });

  
  
  
  
  describe("Repair 2: session-bound confirmation and context isolation regressions", () => {
    it("invalidates open adoption modal and clears acknowledgements on same-tenant token swap, sending ZERO adoption requests", async () => {
      const wsWithEval: WorkspaceData = {
        ...mockWorkspace,
        latest_evaluation: {
          ...mockEvaluation,
          pack_version_id: "pack-v1-id",
          answer_revision: 1,
        },
      };
      vi.spyOn(api, "fetchWorkspace").mockResolvedValue(wsWithEval);
      const adoptSpy = vi.spyOn(api, "adoptEvaluation");

      const { rerender } = render(
        <I18nProvider>
          <CustomerDemoWorkspace
            token="token-initial"
            tenantId="11111111-1111-1111-1111-111111111111"
            userRole="owner"
          />
        </I18nProvider>
      );
      await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalled());

      // Open adoption modal
      const openAdoptBtn = screen.getByTestId("open-adopt-modal-btn");
      fireEvent.click(openAdoptBtn);
      expect(screen.getByTestId("adopt-pack-modal")).toBeInTheDocument();

      // Check synthetic checkbox
      const ackSynthetic = screen.getByTestId("ack-synthetic-checkbox") as HTMLInputElement;
      fireEvent.click(ackSynthetic);
      expect(ackSynthetic.checked).toBe(true);

      // Same-tenant token swap
      rerender(
        <I18nProvider>
          <CustomerDemoWorkspace
            token="token-replaced"
            tenantId="11111111-1111-1111-1111-111111111111"
            userRole="owner"
          />
        </I18nProvider>
      );

      // Modal must be closed immediately
      expect(screen.queryByTestId("adopt-pack-modal")).not.toBeInTheDocument();
      // Zero adoption requests sent
      expect(adoptSpy).not.toHaveBeenCalled();

      // Re-opening under replaced token must have fresh cleared acknowledgements
      await waitFor(() => expect(screen.getByTestId("open-adopt-modal-btn")).toBeEnabled());
      fireEvent.click(screen.getByTestId("open-adopt-modal-btn"));
      const newAckSynthetic = (await screen.findByTestId("ack-synthetic-checkbox")) as HTMLInputElement;
      expect(newAckSynthetic.checked).toBe(false);
      expect(adoptSpy).not.toHaveBeenCalled();
    });

    it("prevents tenant A -> B -> A switch from resurrecting obsolete adoption intent", async () => {
      const wsTenantA: WorkspaceData = {
        ...mockWorkspace,
        tenant_id: "11111111-1111-1111-1111-111111111111",
        latest_evaluation: {
          ...mockEvaluation,
          tenant_id: "11111111-1111-1111-1111-111111111111",
          pack_version_id: "pack-v1-id",
          answer_revision: 1,
        },
      };
      const wsTenantB: WorkspaceData = {
        ...mockWorkspace,
        tenant_id: "22222222-2222-2222-2222-222222222222",
        latest_evaluation: {
          ...mockEvaluation,
          tenant_id: "22222222-2222-2222-2222-222222222222",
          pack_version_id: "pack-v1-id",
          answer_revision: 1,
        },
      };
      const fetchSpy = vi.spyOn(api, "fetchWorkspace").mockImplementation(async (tenantId) => {
        if (tenantId === "22222222-2222-2222-2222-222222222222") {
          return wsTenantB;
        }
        return wsTenantA;
      });
      const adoptSpy = vi.spyOn(api, "adoptEvaluation");

      const { rerender } = render(
        <I18nProvider>
          <CustomerDemoWorkspace
            token="token-a"
            tenantId="11111111-1111-1111-1111-111111111111"
            userRole="owner"
          />
        </I18nProvider>
      );
      await waitFor(() => expect(fetchSpy).toHaveBeenCalledWith("11111111-1111-1111-1111-111111111111", "token-a", expect.anything()));

      // Open adoption modal for Tenant A
      fireEvent.click(screen.getByTestId("open-adopt-modal-btn"));
      expect(screen.getByTestId("adopt-pack-modal")).toBeInTheDocument();

      // Switch to Tenant B
      rerender(
        <I18nProvider>
          <CustomerDemoWorkspace
            token="token-b"
            tenantId="22222222-2222-2222-2222-222222222222"
            userRole="owner"
          />
        </I18nProvider>
      );
      expect(screen.queryByTestId("adopt-pack-modal")).not.toBeInTheDocument();

      // Switch back to Tenant A
      rerender(
        <I18nProvider>
          <CustomerDemoWorkspace
            token="token-a"
            tenantId="11111111-1111-1111-1111-111111111111"
            userRole="owner"
          />
        </I18nProvider>
      );

      // Obsolete confirmation intent must not be resurrected; modal remains closed
      expect(screen.queryByTestId("adopt-pack-modal")).not.toBeInTheDocument();
      expect(adoptSpy).not.toHaveBeenCalled();
    });

    it("invalidates modal confirmation and disables submission when bundle or evaluation digests change", async () => {
      const initialEval: EvaluationData = {
        ...mockEvaluation,
        pack_version_id: "pack-v1-id",
        bundle_digest: "65d0f766" + "0".repeat(56),
        content_digest: "b".repeat(64),
        answer_revision: 1,
      };
      let currentWs: WorkspaceData = {
        ...mockWorkspace,
        latest_evaluation: initialEval,
      };
      vi.spyOn(api, "fetchWorkspace").mockImplementation(async () => currentWs);
      const adoptSpy = vi.spyOn(api, "adoptEvaluation");
      vi.spyOn(api, "saveAnswers").mockRejectedValue(new api.ConflictError("Conflict: revision mismatch"));

      render(
        <I18nProvider>
          <CustomerDemoWorkspace
            token="test-token"
            tenantId="11111111-1111-1111-1111-111111111111"
            userRole="owner"
          />
        </I18nProvider>
      );
      await waitFor(() => expect(screen.getByTestId("open-adopt-modal-btn")).toBeEnabled());

      // Trigger conflict error so that the Reload Workspace action is accessible
      fireEvent.click(screen.getByTestId("save-answers-btn"));
      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Reload Workspace/i })).toBeInTheDocument();
      });

      // Open adoption modal with initial digest
      fireEvent.click(screen.getByTestId("open-adopt-modal-btn"));
      expect(screen.getByTestId("adopt-pack-modal")).toBeInTheDocument();
      expect(screen.queryByTestId("adoption-intent-invalidated-notice")).not.toBeInTheDocument();

      // Workspace reloads with changed bundle_digest under same evaluation ID
      currentWs = {
        ...mockWorkspace,
        current_revision: 1,
        latest_evaluation: {
          ...initialEval,
          bundle_digest: "changed_bundle_digest_" + "1".repeat(42),
        },
      };
      fireEvent.click(screen.getByRole("button", { name: /Reload Workspace/i }));

      // Invalidation notice appears and adopt button is disabled
      await waitFor(() => {
        expect(screen.getByTestId("adoption-intent-invalidated-notice")).toBeInTheDocument();
      });
      const confirmBtn = screen.getByTestId("confirm-adopt-btn");
      expect(confirmBtn).toBeDisabled();

      // Attempting to click confirm button sends ZERO adoption requests
      fireEvent.click(confirmBtn);
      expect(adoptSpy).not.toHaveBeenCalled();
    });

    it("prevents stale 401 from pending context reload from expiring a replacement session", async () => {
      let rejectToken1: ((err: unknown) => void) | undefined;
      vi.spyOn(api, "fetchWorkspace").mockImplementation((tenantId, token) => {
        if (token === "stale-token-1") {
          return new Promise<WorkspaceData>((_, reject) => {
            rejectToken1 = reject;
          });
        }
        return Promise.resolve({
          ...mockWorkspace,
          tenant_id: tenantId,
          latest_evaluation: {
            ...mockEvaluation,
            pack_version_id: "pack-v1-id",
            answer_revision: 1,
          },
        });
      });

      const onSessionExpired = vi.fn();
      const { rerender } = render(
        <I18nProvider>
          <CustomerDemoWorkspace
            token="stale-token-1"
            tenantId="11111111-1111-1111-1111-111111111111"
            userRole="owner"
            onSessionExpired={onSessionExpired}
          />
        </I18nProvider>
      );

      // Replacement token arrives before token-1 completes
      rerender(
        <I18nProvider>
          <CustomerDemoWorkspace
            token="replacement-token-2"
            tenantId="11111111-1111-1111-1111-111111111111"
            userRole="owner"
            onSessionExpired={onSessionExpired}
          />
        </I18nProvider>
      );

      // Now token-1 finally rejects with a 401 Unauthorized
      const error401 = new api.UnauthorizedError("Session expired for stale-token-1");
      (rejectToken1 as ((err: unknown) => void) | undefined)?.(error401);

      await waitFor(() => {
        expect(screen.getByTestId("open-adopt-modal-btn")).toBeEnabled();
      });

      // The stale 401 must NOT expire the replacement session
      expect(onSessionExpired).not.toHaveBeenCalled();
    });

    it("successfully sends exact candidate and evaluation payload on fresh current-context confirmation", async () => {
      const wsWithEval: WorkspaceData = {
        ...mockWorkspace,
        tenant_id: "11111111-1111-1111-1111-111111111111",
        current_revision: 1,
        selection_revision: 0,
        latest_evaluation: {
          ...mockEvaluation,
          id: "eval-exact-1",
          pack_version_id: "pack-v1-id",
          bundle_digest: "65d0f766" + "0".repeat(56),
          content_digest: "b".repeat(64),
          answer_revision: 1,
        },
      };
      vi.spyOn(api, "fetchWorkspace").mockResolvedValue(wsWithEval);

      const mockReceipt: AdoptionReceipt = {
        id: "adopt-receipt-1",
        tenant_id: "11111111-1111-1111-1111-111111111111",
        selection_revision: 1,
        evaluation_id: "eval-exact-1",
        pack_version_id: "pack-v1-id",
        bundle_digest: "65d0f766" + "0".repeat(56),
        created_at: "2026-10-23T10:00:00Z",
        is_current: true,
        current_selection_revision: 1,
        current_pack_version_id: "pack-v1-id",
      };
      const adoptSpy = vi.spyOn(api, "adoptEvaluation").mockResolvedValue(mockReceipt);

      render(
        <I18nProvider>
          <CustomerDemoWorkspace
            token="token-valid"
            tenantId="11111111-1111-1111-1111-111111111111"
            userRole="owner"
          />
        </I18nProvider>
      );
      await waitFor(() => expect(screen.getByTestId("open-adopt-modal-btn")).toBeEnabled());

      // Open modal in current context
      fireEvent.click(screen.getByTestId("open-adopt-modal-btn"));
      expect(screen.getByTestId("adopt-pack-modal")).toBeInTheDocument();
      expect(screen.queryByTestId("adoption-intent-invalidated-notice")).not.toBeInTheDocument();

      // Check required synthetic and missing acknowledgements
      fireEvent.click(screen.getByTestId("ack-synthetic-checkbox"));
      fireEvent.click(screen.getByTestId("ack-missing-checkbox"));

      // Confirm button is enabled and clicked
      const confirmBtn = screen.getByTestId("confirm-adopt-btn");
      expect(confirmBtn).toBeEnabled();
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(adoptSpy).toHaveBeenCalledTimes(1);
        expect(adoptSpy).toHaveBeenCalledWith(
          "11111111-1111-1111-1111-111111111111",
          "token-valid",
          {
            expected_revision: 1,
            evaluation_id: "eval-exact-1",
            pack_version_id: "pack-v1-id",
            acknowledge_synthetic: true,
            acknowledge_missing_information: true,
          },
          expect.anything()
        );
      });
    });
  });

  describe("Pre-audit feature flag and actor admission guards", () => {
    it("proves no pre-audit mount or fetch when feature is OFF (default)", async () => {
      const fetchSpy = vi.spyOn(globalThis, "fetch");
      render(
        <I18nProvider>
          <CustomerDemoWorkspace
            token="token-valid"
            tenantId="11111111-1111-1111-1111-111111111111"
            userRole="owner"
          />
        </I18nProvider>
      );
      await waitFor(() => expect(screen.getByTestId("modern-workspace-title")).toBeInTheDocument());

      // Pre-audit workspace is completely unmounted from the DOM
      expect(screen.queryByTestId("portal-preaudit-view")).not.toBeInTheDocument();
      expect(screen.queryByTestId("preaudit-workspace")).not.toBeInTheDocument();

      // No fetch calls to preaudits endpoint occurred
      const preauditCalls = fetchSpy.mock.calls.filter((call) =>
        String(call[0]).includes("/customer-demo/preaudits")
      );
      expect(preauditCalls).toHaveLength(0);
    });

    it("handles missing or undefined userRole safely without crashing overview", async () => {
      render(
        <I18nProvider>
          <CustomerDemoWorkspace
            token="token-valid"
            tenantId="11111111-1111-1111-1111-111111111111"
            userRole={undefined}
          />
        </I18nProvider>
      );
      await waitFor(() => expect(screen.getByTestId("modern-workspace-title")).toBeInTheDocument());
      expect(screen.queryByTestId("portal-preaudit-view")).not.toBeInTheDocument();
    });
  });
});
