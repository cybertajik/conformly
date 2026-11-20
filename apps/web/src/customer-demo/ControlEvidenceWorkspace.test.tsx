import "@testing-library/jest-dom/vitest";
import React from "react";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ControlEvidenceWorkspace } from "./ControlEvidenceWorkspace";
import { I18nProvider } from "../i18n/I18nContext";
import * as api from "./control-evidence-api";
import {
  ControlWorkItem,
  OwnerDirectoryResponse,
  WorkListResponse,
} from "./control-evidence-types";

describe("ControlEvidenceWorkspace Component", () => {
  const dummyOwners: OwnerDirectoryResponse = {
    items: [
      { user_id: "u-owner", display_name: "Alice Owner" },
      { user_id: "u-mgr", display_name: "Bob Manager" },
    ],
    total: 2,
  };

  const dummyItem: ControlWorkItem = {
    id: "w-1",
    adoption_id: "adopt-1",
    control_id: "ctrl-1",
    control_version_id: "cv-1",
    title: "Access Control Policy",
    provenance: "Synthetic Baseline Pack",
    pack_version: 1,
    bundle_digest: "digest-12345678",
    requirement_results: [
      {
        requirement_id: "req-1",
        requirement_version_id: "rv-1",
        requirement_identifier: "SYNTH-REQ-001",
        requirement_title: "Role-Based Access Control",
        result: "APPLICABLE",
      },
    ],
    owner_user_id: null,
    owner_display_name: null,
    due_date: null,
    version: 1,
    is_current: true,
    is_stale: false,
    links: [],
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders empty state and allows initializing control work", async () => {
    const emptyList: WorkListResponse = {
      tenant_id: "t-1",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      items: [],
      total: 0,
    };

    vi.spyOn(api, "fetchControlWorkList").mockResolvedValue(emptyList);
    vi.spyOn(api, "fetchOwnerDirectory").mockResolvedValue(dummyOwners);

    const initSpy = vi.spyOn(api, "initializeControlWork").mockResolvedValue({
      ...emptyList,
      items: [dummyItem],
      total: 1,
    });

    render(
      <ControlEvidenceWorkspace
        tenantId="t-1"
        token="tok"
        adoptionId="adopt-1"
        selectionRevision={1}
        answerRevision={1}
        hasUnsavedParentEdits={false}
        isAdoptionStale={false}
      />
    );

    expect(screen.getByTestId("control-work-loading")).toBeDefined();

    await waitFor(() => {
      expect(screen.getByTestId("empty-work-notice")).toBeDefined();
    });

    const initBtn = screen.getByTestId("init-control-work-btn");
    expect(initBtn).toBeDefined();

    fireEvent.click(initBtn);

    await waitFor(() => {
      expect(initSpy).toHaveBeenCalled();
      expect(screen.getByTestId("control-card-w-1")).toBeDefined();
    });
  });

  it("updates control work owner and due date assignment", async () => {
    const workList: WorkListResponse = {
      tenant_id: "t-1",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      items: [dummyItem],
      total: 1,
    };

    vi.spyOn(api, "fetchControlWorkList").mockResolvedValue(workList);
    vi.spyOn(api, "fetchOwnerDirectory").mockResolvedValue(dummyOwners);

    const patchedItem: ControlWorkItem = {
      ...dummyItem,
      owner_user_id: "u-mgr",
      owner_display_name: "Bob Manager",
      due_date: "2026-11-30",
      version: 2,
    };

    const patchSpy = vi.spyOn(api, "patchControlWork").mockResolvedValue({
      operation_id: "op-patch",
      event_id: "ev-patch",
      applied_work_version: 2,
      replayed: false,
      current_work: patchedItem,
    });

    render(
      <ControlEvidenceWorkspace
        tenantId="t-1"
        token="tok"
        adoptionId="adopt-1"
        selectionRevision={1}
        answerRevision={1}
        hasUnsavedParentEdits={false}
        isAdoptionStale={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("control-card-w-1")).toBeDefined();
    });

    const ownerSelect = screen.getByTestId("owner-select-w-1") as HTMLSelectElement;
    fireEvent.change(ownerSelect, { target: { value: "u-mgr" } });

    const dateInput = screen.getByTestId("due-date-w-1") as HTMLInputElement;
    fireEvent.change(dateInput, { target: { value: "2026-11-30" } });

    const saveBtn = screen.getByTestId("save-assignment-btn-w-1");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledWith(
        "t-1",
        "tok",
        "w-1",
        expect.objectContaining({
          owner_user_id: "u-mgr",
          due_date: "2026-11-30",
          expected_work_version: 1,
        })
      );
    });
  });

  it("handles upload, deliberate reuse, and review lifecycle", async () => {
    const itemWithLink: ControlWorkItem = {
      ...dummyItem,
      version: 2,
      links: [
        {
          id: "link-1",
          evidence_id: "ev-1",
          revision_number: 1,
          digest: "a".repeat(64),
          file_ids: ["f-1"],
          filename: "audit_report.pdf",
          file_size: 2048,
          classification: "Restricted",
          validity: "AVAILABLE",
          scan_status: "SCANNED_AT_LINK",
          scan_verified_at: "2026-10-22T14:30:00Z",
          review: "PENDING",
          rationale: "Initial audit report evidence.",
          created_at: new Date().toISOString(),
        },
      ],
    };

    const secondItem: ControlWorkItem = {
      ...dummyItem,
      id: "w-2",
      control_id: "ctrl-2",
      title: "Data Retention Policy",
      links: [],
    };

    const workList: WorkListResponse = {
      tenant_id: "t-1",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      items: [itemWithLink, secondItem],
      total: 2,
    };

    vi.spyOn(api, "fetchControlWorkList").mockResolvedValue(workList);
    vi.spyOn(api, "fetchOwnerDirectory").mockResolvedValue(dummyOwners);

    const reviewSpy = vi.spyOn(api, "createReview").mockResolvedValue({
      operation_id: "op-rev",
      event_id: "ev-rev",
      applied_work_version: 3,
      replayed: false,
      current_work: {
        ...itemWithLink,
        version: 3,
        links: [{ ...itemWithLink.links[0], review: "ACCEPTED" }],
      },
    });

    render(
      <ControlEvidenceWorkspace
        tenantId="t-1"
        token="tok"
        adoptionId="adopt-1"
        selectionRevision={1}
        answerRevision={1}
        hasUnsavedParentEdits={false}
        isAdoptionStale={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("evidence-link-link-1")).toBeDefined();
    });

    // Open review modal
    const reviewBtn = screen.getByTestId("review-link-btn-link-1");
    fireEvent.click(reviewBtn);

    expect(screen.getByTestId("review-evidence-modal")).toBeDefined();

    const rationaleInput = screen.getByTestId("review-rationale-input");
    fireEvent.change(rationaleInput, { target: { value: "Fully compliant and verified." } });

    const submitReviewBtn = screen.getByTestId("submit-review-btn");
    fireEvent.click(submitReviewBtn);

    await waitFor(() => {
      expect(reviewSpy).toHaveBeenCalledWith(
        "t-1",
        "tok",
        "w-1",
        "link-1",
        expect.objectContaining({
          decision: "ACCEPTED",
          rationale: "Fully compliant and verified.",
          expected_work_version: 2,
        })
      );
    });
  });

  it("disables mutations and displays notice when parent edits are unsaved", async () => {
    const workList: WorkListResponse = {
      tenant_id: "t-1",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      items: [dummyItem],
      total: 1,
    };

    vi.spyOn(api, "fetchControlWorkList").mockResolvedValue(workList);
    vi.spyOn(api, "fetchOwnerDirectory").mockResolvedValue(dummyOwners);

    render(
      <ControlEvidenceWorkspace
        tenantId="t-1"
        token="tok"
        adoptionId="adopt-1"
        selectionRevision={1}
        answerRevision={1}
        hasUnsavedParentEdits={true}
        isAdoptionStale={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("stale-work-warning")).toBeDefined();
    });

    const saveBtn = screen.getByTestId("save-assignment-btn-w-1") as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(true);
  });

  it("renders truthful scan status badge and unverified validity badge", async () => {
    const itemWithScanBadges: ControlWorkItem = {
      ...dummyItem,
      version: 2,
      links: [
        {
          id: "link-clean",
          evidence_id: "ev-1",
          revision_number: 1,
          digest: "a".repeat(64),
          file_ids: ["f-1"],
          filename: "clean_audit.pdf",
          file_size: 2048,
          classification: "Restricted",
          validity: "AVAILABLE",
          scan_status: "SCANNED_AT_LINK",
          scan_verified_at: "2026-10-22T14:30:00Z",
          review: "ACCEPTED",
          rationale: "Clean scan proof verified.",
          created_at: new Date().toISOString(),
        },
        {
          id: "link-unverified",
          evidence_id: "ev-2",
          revision_number: 1,
          digest: "b".repeat(64),
          file_ids: ["f-2"],
          filename: "unverified.bin",
          file_size: 1024,
          classification: "Restricted",
          validity: "UNVERIFIED",
          scan_status: "UNVERIFIED",
          scan_verified_at: null,
          review: "PENDING",
          rationale: "Unverified historic proof.",
          created_at: new Date().toISOString(),
        },
      ],
    };

    const workList: WorkListResponse = {
      tenant_id: "t-1",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      items: [itemWithScanBadges],
      total: 1,
    };

    vi.spyOn(api, "fetchControlWorkList").mockResolvedValue(workList);
    vi.spyOn(api, "fetchOwnerDirectory").mockResolvedValue(dummyOwners);

    render(
      <ControlEvidenceWorkspace
        tenantId="t-1"
        token="tok"
        adoptionId="adopt-1"
        selectionRevision={1}
        answerRevision={1}
        hasUnsavedParentEdits={false}
        isAdoptionStale={false}
        userRole="owner"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Clean scan proof verified/)).toBeDefined();
    });

    // Check scan status badges
    expect(screen.getByText("Scanned at Link")).toBeDefined();
    expect(screen.getByText("Unverified")).toBeDefined();
    expect(screen.getByText("Unverified Scan Proof")).toBeDefined();
  });

  // --- B03 Repair 2 Regressions: Section C Pending Navigation ---

  it("pending navigation intent for nonfirst control survives initial pending promise load without premature not-found", async () => {
    let resolveCtrlList: (val: WorkListResponse) => void;
    const ctrlListPromise = new Promise((resolve) => {
      resolveCtrlList = resolve;
    });

    vi.spyOn(api, "fetchControlWorkList").mockImplementation(() => ctrlListPromise as unknown as Promise<WorkListResponse>);
    vi.spyOn(api, "fetchOwnerDirectory").mockResolvedValue(dummyOwners);

    const nonFirstItem: ControlWorkItem = {
      ...dummyItem,
      id: "w-target-nonfirst",
      control_id: "ctrl-target",
      title: "Nonfirst Target Control",
    };

    render(
      <ControlEvidenceWorkspace
        tenantId="t-1"
        token="tok"
        adoptionId="adopt-1"
        selectionRevision={1}
        answerRevision={1}
        hasUnsavedParentEdits={false}
        isAdoptionStale={false}
        navTarget={{ workId: "w-target-nonfirst", targetTab: "evidence", nonce: 887766 }}
      />
    );

    // While list is pending, target-not-found MUST NOT be displayed prematurely
    expect(screen.queryByTestId("control-nav-target-not-found")).not.toBeInTheDocument();

    // Now resolve list with both dummyItem and nonFirstItem
    resolveCtrlList!({
      tenant_id: "t-1",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      items: [dummyItem, nonFirstItem],
      total: 2,
    });

    // Target card should be rendered and selected/focused, not showing not-found
    await waitFor(() => {
      expect(screen.getByTestId("control-card-w-target-nonfirst")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("control-nav-target-not-found")).not.toBeInTheDocument();
  });

  it("authoritative loaded missing target displays safe fallback notice with dismiss button once", async () => {
    const workList: WorkListResponse = {
      tenant_id: "t-1",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      items: [dummyItem],
      total: 1,
    };

    vi.spyOn(api, "fetchControlWorkList").mockResolvedValue(workList);
    vi.spyOn(api, "fetchOwnerDirectory").mockResolvedValue(dummyOwners);

    render(
      <ControlEvidenceWorkspace
        tenantId="t-1"
        token="tok"
        adoptionId="adopt-1"
        selectionRevision={1}
        answerRevision={1}
        hasUnsavedParentEdits={false}
        isAdoptionStale={false}
        navTarget={{ workId: "w-missing-target", nonce: 554433 }}
      />
    );

    // After authoritative load completes and target is absent, fallback notice is shown
    await waitFor(() => {
      expect(screen.getByTestId("control-nav-target-not-found")).toBeInTheDocument();
    });

    // User can dismiss the notice
    const dismissBtn = screen.getByTestId("dismiss-control-nav-target-btn");
    fireEvent.click(dismissBtn);
    expect(screen.queryByTestId("control-nav-target-not-found")).not.toBeInTheDocument();
  });

  it("obsolete tenant or adoption target does not apply to replacement context", async () => {
    const workList: WorkListResponse = {
      tenant_id: "t-1",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      items: [dummyItem],
      total: 1,
    };

    vi.spyOn(api, "fetchControlWorkList").mockResolvedValue(workList);
    vi.spyOn(api, "fetchOwnerDirectory").mockResolvedValue(dummyOwners);

    const { rerender } = render(
      <ControlEvidenceWorkspace
        tenantId="t-1"
        token="tok"
        adoptionId="adopt-1"
        selectionRevision={1}
        answerRevision={1}
        hasUnsavedParentEdits={false}
        isAdoptionStale={false}
        navTarget={{ workId: "w-1", tenantId: "t-1", nonce: 112233 }}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("control-card-w-1")).toBeInTheDocument();
    });

    // Now switch tenant to t-2 with old target carrying tenant t-1
    rerender(
      <ControlEvidenceWorkspace
        tenantId="t-2"
        token="tok"
        adoptionId="adopt-1"
        selectionRevision={1}
        answerRevision={1}
        hasUnsavedParentEdits={false}
        isAdoptionStale={false}
        navTarget={{ workId: "w-1", tenantId: "t-1", nonce: 112233 }}
      />
    );

    // Obsolete target with t-1 should be rejected / not applied in t-2
    expect(screen.queryByTestId("control-nav-target-not-found")).not.toBeInTheDocument();
  });
  it("preserves navigation target across failed load and applies it after subsequent successful retry", async () => {
    vi.spyOn(api, "fetchOwnerDirectory").mockResolvedValue(dummyOwners);
    let callCount = 0;
    vi.spyOn(api, "fetchControlWorkList").mockImplementation(async () => {
      callCount++;
      if (callCount === 1) {
        throw new Error("503 Service Unavailable");
      }
      return {
        tenant_id: "tenant-1",
        adoption_id: "adopt-1",
        selection_revision: 1,
        answer_revision: 1,
        is_current: true,
        is_stale: false,
        total: 1,
        items: [
          {
            ...dummyItem,
            id: "ctrl-target-1",
          },
        ],
      };
    });

    const { rerender } = render(
      <I18nProvider>
        <ControlEvidenceWorkspace
          tenantId="tenant-1"
          token="token-abc"
          adoptionId="adopt-1"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          navTarget={{ workId: "ctrl-target-1", nonce: 999 }}
        />
      </I18nProvider>
    );

    // Initial load fails
    await waitFor(() => {
      expect(screen.getByText(/503 Service Unavailable/i)).toBeInTheDocument();
    });

    // Target should NOT be consumed as not found
    expect(screen.queryByTestId("nav-target-not-found-notice")).not.toBeInTheDocument();

    // Rerender or trigger retry (simulated by re-providing token/tenant or prop re-eval)
    rerender(
      <I18nProvider>
        <ControlEvidenceWorkspace
          tenantId="tenant-1"
          token="token-retry"
          adoptionId="adopt-1"
          selectionRevision={1}
          answerRevision={1}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          navTarget={{ workId: "ctrl-target-1", nonce: 999 }}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("control-card-ctrl-target-1")).toBeInTheDocument();
    });
    // Target is present, still no not found banner
    expect(screen.queryByTestId("nav-target-not-found-notice")).not.toBeInTheDocument();
  });
});
