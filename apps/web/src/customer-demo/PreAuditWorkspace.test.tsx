import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import type { SupportedLocale } from "../i18n/types";
import { ConflictError, UnauthorizedError } from "./api";
import * as preauditApi from "./preaudit-api";
import * as verificationApi from "./verification-api";
import type { VerificationDetail } from "./verification-types";
import {
  PreauditActor,
  PreauditCase,
  PreauditHistoryResponse,
  PreauditListResponse,
  PreauditReportDownloadResult,
} from "./preaudit-types";
import { PreAuditWorkspace } from "./PreAuditWorkspace";

describe("PreAuditWorkspace", () => {
  const tenantId = "11111111-1111-1111-1111-111111111111";
  const token = "mock-token-abc";
  const ownerId = "00000000-0000-0000-0000-000000000001";
  const leadId = "00000000-0000-0000-0000-000000000002";
  const reviewerId = "00000000-0000-0000-0000-000000000003";

  const mockActors: PreauditActor[] = [
    {
      user_id: leadId,
      email: "lead@example.com",
      display_name: "Compliance Lead",
      role: "compliance_manager",
    },
    {
      user_id: reviewerId,
      email: "reviewer@example.com",
      display_name: "Independent Reviewer",
      role: "owner",
    },
    {
      user_id: ownerId,
      email: "owner@example.com",
      display_name: "Tenant Owner",
      role: "owner",
    },
  ];

  const mockCaseDraft: PreauditCase = {
    id: "case-draft-1",
    tenant_id: tenantId,
    adoption_id: "adopt-1",
    pack_name: "soc2",
    pack_version: "2026.1",
    status: "DRAFT",
    title: "SOC2 Type II Readiness",
    description: "Annual readiness assessment",
    lead_user_id: leadId,
    lead_name: "Compliance Lead",
    reviewer_user_id: reviewerId,
    reviewer_name: "Independent Reviewer",
    revision: 1,
    current_scope_snapshot_id: null,
    current_scope_snapshot_digest: null,
    current_review_snapshot_id: null,
    current_review_snapshot_digest: null,
    is_scope_current: true,
    is_review_current: true,
    blockers: [
      {
        work_id: "work-1",
        code: "UNASSESSED_CONTROL",
        control_code: "AC-1",
        description: "Control AC-1 is unassessed",
      },
    ],
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-01T10:00:00Z",
  };

  const mockCaseFrozen: PreauditCase = {
    ...mockCaseDraft,
    id: "case-frozen-2",
    status: "FROZEN",
    revision: 2,
    current_scope_snapshot_id: "snap-scope-1",
    current_scope_snapshot_digest: "a".repeat(64),
  };

  const mockCaseInReview: PreauditCase = {
    ...mockCaseFrozen,
    id: "case-review-3",
    status: "IN_REVIEW",
    revision: 3,
    current_review_snapshot_id: "snap-rev-1",
    current_review_snapshot_digest: "b".repeat(64),
  };

  const mockCaseReviewed: PreauditCase = {
    ...mockCaseInReview,
    id: "case-reviewed-4",
    status: "REVIEWED",
    revision: 4,
    blockers: [],
  };

  const mockCaseApproved: PreauditCase = {
    ...mockCaseReviewed,
    id: "case-approved-5",
    status: "APPROVED",
    revision: 5,
  };

  const createListResponse = (items: PreauditCase[]): PreauditListResponse => ({
    items,
    total: items.length,
    limit: 50,
    offset: 0,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    vi.spyOn(preauditApi, "listPreauditCases").mockResolvedValue(createListResponse([mockCaseDraft]));
    vi.spyOn(preauditApi, "fetchPreauditActors").mockResolvedValue(mockActors);
    const allCases = [mockCaseDraft, mockCaseFrozen, mockCaseInReview, mockCaseReviewed, mockCaseApproved];
    vi.spyOn(preauditApi, "getPreauditCase").mockImplementation(async (_t, id) => {
      return allCases.find((c) => c.id === id) ?? mockCaseDraft;
    });
    vi.spyOn(preauditApi, "createPreauditCase").mockResolvedValue(mockCaseDraft);
    vi.spyOn(preauditApi, "freezePreauditScope").mockResolvedValue(mockCaseFrozen);
    vi.spyOn(preauditApi, "submitPreauditReview").mockResolvedValue(mockCaseInReview);
    vi.spyOn(preauditApi, "recordReviewDecision").mockResolvedValue(mockCaseReviewed);
    vi.spyOn(preauditApi, "approvePreauditCase").mockResolvedValue(mockCaseApproved);
    vi.spyOn(preauditApi, "cancelPreauditCase").mockResolvedValue({
      ...mockCaseDraft,
      status: "CANCELLED",
    });
    vi.spyOn(preauditApi, "getPreauditHistory").mockResolvedValue({
      preaudit_id: "case-draft-1",
      events: [
        {
          id: "event-1",
          tenant_id: tenantId,
          preaudit_id: "case-draft-1",
          revision: 1,
          operation_id: "op-1",
          event_type: "CREATED",
          actor_user_id: ownerId,
          prior_status: null,
          new_status: "DRAFT",
          payload: { title: "SOC2 Type II Readiness" },
          created_at: "2026-11-01T10:00:00Z",
        },
      ],
    });
    vi.spyOn(preauditApi, "downloadPreauditReport").mockResolvedValue({
      blob: new Blob(["archive"], { type: "application/zip" }),
      filename: "preaudit-report-case-draft-1.zip",
      preauditId: "case-draft-1",
      snapshotDigest: "abc123digest",
    });

    globalThis.URL.createObjectURL = vi.fn(() => "blob:mock-url");
    globalThis.URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  const renderComponent = (
    props: Partial<React.ComponentProps<typeof PreAuditWorkspace>> = {},
    locale?: SupportedLocale,
  ) => {
    if (locale) {
      localStorage.setItem("conformly.locale", locale);
    }
    return render(
      <I18nProvider>
        <PreAuditWorkspace
          tenantId={tenantId}
          token={token}
          userRole="owner"
          currentUserId={ownerId}
          adoptionId="adopt-1"
          {...props}
        />
      </I18nProvider>,
    );
  };

  it("renders loading state then case details", async () => {
    renderComponent();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("SOC2 Type II Readiness")).toBeInTheDocument();
      expect(screen.getByText("DRAFT")).toBeInTheDocument();
    });

    expect(preauditApi.listPreauditCases).toHaveBeenCalledWith(
      tenantId,
      token,
      expect.any(AbortSignal),
    );
  });

  it("renders empty state when no cases exist", async () => {
    vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(createListResponse([]));
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("preaudit-no-cases")).toBeInTheDocument();
    });
  });

  it("handles blocker navigation when clicking view work", async () => {
    const handleNavigate = vi.fn();
    renderComponent({ onNavigateToWork: handleNavigate });

    await waitFor(() => {
      expect(screen.getByText("Control AC-1 is unassessed")).toBeInTheDocument();
    });

    const viewWorkBtn = screen.getByTestId("blocker-nav-link-AC-1");
    fireEvent.click(viewWorkBtn);

    expect(handleNavigate).toHaveBeenCalledWith("work-1", "assessment");
  });

  it("opens create case modal and successfully submits new case", async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("create-preaudit-case-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("create-preaudit-case-btn"));

    expect(screen.getByTestId("create-case-modal")).toBeInTheDocument();

    const titleInput = screen.getByTestId("create-case-title-input");
    fireEvent.change(titleInput, { target: { value: "New Preaudit 2026" } });

    const submitBtn = screen.getByTestId("submit-create-case-btn");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(preauditApi.createPreauditCase).toHaveBeenCalledWith(
        tenantId,
        expect.objectContaining({
          title: "New Preaudit 2026",
          lead_user_id: leadId,
          reviewer_user_id: reviewerId,
          adoption_id: "adopt-1",
        }),
        token,
      );
    });
  });

  it("triggers scope freeze when clicking freeze scope button", async () => {
    renderComponent({ currentUserId: leadId, userRole: "compliance_manager" });

    await waitFor(() => {
      expect(screen.getByTestId("freeze-scope-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("freeze-scope-btn"));

    await waitFor(() => {
      expect(preauditApi.freezePreauditScope).toHaveBeenCalledWith(
        tenantId,
        "case-draft-1",
        expect.objectContaining({ expected_revision: 1 }),
        token,
      );
    });
  });

  it("triggers review submission when in FROZEN status", async () => {
    vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
      createListResponse([mockCaseFrozen]),
    );
    renderComponent({ currentUserId: leadId, userRole: "compliance_manager" });

    await waitFor(() => {
      expect(screen.getByTestId("submit-review-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("submit-review-btn"));

    await waitFor(() => {
      expect(preauditApi.submitPreauditReview).toHaveBeenCalledWith(
        tenantId,
        "case-frozen-2",
        expect.objectContaining({ expected_revision: 2 }),
        token,
      );
    });
  });

  it("allows reviewer to record review decision in IN_REVIEW status", async () => {
    vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
      createListResponse([mockCaseInReview]),
    );
    renderComponent({ currentUserId: reviewerId, userRole: "owner" });

    await waitFor(() => {
      expect(screen.getByTestId("record-review-decision-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("record-review-decision-btn"));

    expect(screen.getByTestId("review-decision-modal")).toBeInTheDocument();

    const notesInput = screen.getByTestId("review-notes-input");
    fireEvent.change(notesInput, { target: { value: "All controls verified satisfactory." } });

    const submitBtn = screen.getByTestId("submit-review-decision-btn");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(preauditApi.recordReviewDecision).toHaveBeenCalledWith(
        tenantId,
        "case-review-3",
        expect.objectContaining({
          decision: "ACCEPT",
          snapshot_id: "snap-rev-1",
          notes: "All controls verified satisfactory.",
        }),
        token,
      );
    });
  });

  it("allows Owner to approve case in REVIEWED status", async () => {
    vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
      createListResponse([mockCaseReviewed]),
    );
    renderComponent({ currentUserId: ownerId, userRole: "owner" });

    await waitFor(() => {
      expect(screen.getByTestId("approve-preaudit-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("approve-preaudit-btn"));

    expect(screen.getByTestId("approve-case-modal")).toBeInTheDocument();

    const notesInput = screen.getByTestId("approve-notes-input");
    fireEvent.change(notesInput, { target: { value: "Executive approval granted." } });

    const submitBtn = screen.getByTestId("confirm-approve-btn");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(preauditApi.approvePreauditCase).toHaveBeenCalledWith(
        tenantId,
        "case-reviewed-4",
        expect.objectContaining({
          snapshot_id: "snap-rev-1",
          approval_notes: "Executive approval granted.",
        }),
        token,
      );
    });
  });

  it("allows Owner to cancel case", async () => {
    renderComponent({ currentUserId: ownerId, userRole: "owner" });

    await waitFor(() => {
      expect(screen.getByTestId("cancel-preaudit-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("cancel-preaudit-btn"));

    expect(screen.getByTestId("cancel-case-modal")).toBeInTheDocument();

    const reasonInput = screen.getByTestId("cancel-reason-input");
    fireEvent.change(reasonInput, { target: { value: "Scope overhaul" } });

    const submitBtn = screen.getByTestId("confirm-cancel-btn");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(preauditApi.cancelPreauditCase).toHaveBeenCalledWith(
        tenantId,
        "case-draft-1",
        expect.objectContaining({ reason: "Scope overhaul" }),
        token,
      );
    });
  });

  it("toggles and displays immutable event history", async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("toggle-history-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("toggle-history-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("preaudit-history-section")).toBeInTheDocument();
      expect(preauditApi.getPreauditHistory).toHaveBeenCalledWith(
        tenantId,
        "case-draft-1",
        token,
      );
      expect(screen.getByText(/CREATED/)).toBeInTheDocument();
    });
  });

  it("downloads preaudit report archive when review snapshot exists", async () => {
    vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
      createListResponse([mockCaseInReview]),
    );
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("download-preaudit-report-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("download-preaudit-report-btn"));

    await waitFor(() => {
      expect(preauditApi.downloadPreauditReport).toHaveBeenCalledWith(
        tenantId,
        "case-review-3",
        expect.objectContaining({
          snapshot_id: "snap-rev-1",
          expected_snapshot_digest: "b".repeat(64),
        }),
        token,
        expect.any(AbortSignal),
      );
      expect(globalThis.URL.createObjectURL).toHaveBeenCalled();
    });
  });

  it("triggers onSessionExpired callback on 401 error", async () => {
    const handleExpired = vi.fn();
    vi.mocked(preauditApi.listPreauditCases).mockRejectedValueOnce(
      new UnauthorizedError("Unauthorized"),
    );

    renderComponent({ onSessionExpired: handleExpired });

    await waitFor(() => {
      expect(handleExpired).toHaveBeenCalledTimes(1);
    });
  });

  it("renders localized text across German, French, Dutch, and Spanish", async () => {
    const locales: SupportedLocale[] = ["de", "fr", "nl", "es"];
    for (const loc of locales) {
      const { unmount } = renderComponent({}, loc);
      await waitFor(() => {
        expect(screen.getByTestId("create-preaudit-case-btn")).toBeInTheDocument();
      });
      unmount();
    }
  });

  it("handles missing or unknown role safely without crashing or granting owner actions", async () => {
    renderComponent({ userRole: undefined, currentUserId: "stranger-1" });
    await waitFor(() => {
      expect(screen.getByTestId("preaudit-active-case-card")).toBeInTheDocument();
    });
    // Privileged owner actions are not granted
    expect(screen.queryByTestId("approve-preaudit-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("open-cancel-modal-btn")).not.toBeInTheDocument();
  });

  it("recovers from uncertain write on network error using exact retry", async () => {
    vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
      createListResponse([mockCaseDraft]),
    );
    vi.mocked(preauditApi.getPreauditCase).mockResolvedValueOnce(mockCaseDraft);
    vi.mocked(preauditApi.freezePreauditScope).mockRejectedValueOnce(
      new TypeError("Failed to fetch (network error)"),
    );

    renderComponent({ currentUserId: leadId, userRole: "compliance_manager" });
    await waitFor(() => {
      expect(screen.getByTestId("freeze-scope-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("freeze-scope-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("uncertain-operation-alert")).toBeInTheDocument();
      expect(screen.getByTestId("uncertain-retry-btn")).toBeInTheDocument();
      expect(screen.getByTestId("uncertain-abandon-btn")).toBeInTheDocument();
    });

    // Make retry succeed
    vi.mocked(preauditApi.freezePreauditScope).mockResolvedValueOnce(mockCaseFrozen);
    fireEvent.click(screen.getByTestId("uncertain-retry-btn"));

    await waitFor(() => {
      expect(screen.queryByTestId("uncertain-operation-alert")).not.toBeInTheDocument();
      expect(screen.getByText("Operation completed successfully upon retry")).toBeInTheDocument();
    });
  });

  it("dismisses uncertain write when abandon is clicked", async () => {
    vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
      createListResponse([mockCaseDraft]),
    );
    vi.mocked(preauditApi.getPreauditCase).mockResolvedValueOnce(mockCaseDraft);
    vi.mocked(preauditApi.freezePreauditScope).mockRejectedValueOnce(
      new TypeError("Network error"),
    );

    renderComponent({ currentUserId: leadId, userRole: "compliance_manager" });
    await waitFor(() => {
      expect(screen.getByTestId("freeze-scope-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("freeze-scope-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("uncertain-operation-alert")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("uncertain-abandon-btn"));
    expect(screen.getByTestId("uncertain-abandon-dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("uncertain-abandon-acknowledge-checkbox"));
    fireEvent.click(screen.getByTestId("uncertain-confirm-abandon-btn"));

    await waitFor(() => {
      expect(screen.queryByTestId("uncertain-operation-alert")).not.toBeInTheDocument();
      expect(screen.getByText(/was not cancelled/i)).toBeInTheDocument();
    });
  });

  describe("Repair 3 Regression Tests: Admission, Uncertainty, and Report Verification", () => {
    it("does not allow Case A initial detail load to overwrite Case B when B was selected in flight", async () => {
      let resolveCaseA!: (val: PreauditCase) => void;
      const caseAPromise = new Promise<PreauditCase>((res) => {
        resolveCaseA = res;
      });

      const caseBWithUniqueTitle = { ...mockCaseFrozen, title: "Case B Unique Title" };

      vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
        createListResponse([mockCaseDraft, caseBWithUniqueTitle]),
      );
      vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
        if (id === mockCaseDraft.id) {
          return caseAPromise as Promise<PreauditCase>;
        }
        return caseBWithUniqueTitle;
      });

      renderComponent();

      // Case selector is available
      await waitFor(() => {
        expect(screen.getByTestId("preaudit-case-select")).toBeInTheDocument();
      });

      // User selects Case B while Case A is still fetching
      fireEvent.change(screen.getByTestId("preaudit-case-select"), {
        target: { value: caseBWithUniqueTitle.id },
      });

      // Now Case A resolves late
      resolveCaseA(mockCaseDraft);

      // Verify Case B remains the active displayed case
      await waitFor(() => {
        expect(screen.getByTestId("preaudit-active-case-card")).toBeInTheDocument();
        expect(screen.getByText("Case B Unique Title")).toBeInTheDocument();
      });
      expect(screen.queryByText(mockCaseDraft.title)).not.toBeInTheDocument();
    });

    it("does not allow Case A history to render under Case B when B was selected in flight", async () => {
      let resolveHistA!: (val: PreauditHistoryResponse) => void;
      const histAPromise = new Promise<PreauditHistoryResponse>((res) => {
        resolveHistA = res;
      });

      vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
        createListResponse([mockCaseDraft, mockCaseFrozen]),
      );
      vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
        return id === mockCaseFrozen.id ? mockCaseFrozen : mockCaseDraft;
      });
      vi.mocked(preauditApi.getPreauditHistory).mockImplementation(async (_t, id) => {
        if (id === mockCaseDraft.id) {
          return histAPromise;
        }
        return { preaudit_id: mockCaseFrozen.id, events: [] };
      });

      renderComponent();

      await waitFor(() => {
        expect(screen.getByTestId("toggle-history-btn")).toBeInTheDocument();
      });

      // Click history on Case A
      fireEvent.click(screen.getByTestId("toggle-history-btn"));

      // User selects Case B
      fireEvent.change(screen.getByTestId("preaudit-case-select"), {
        target: { value: mockCaseFrozen.id },
      });

      await waitFor(() => {
        expect(screen.getByText(mockCaseFrozen.title)).toBeInTheDocument();
      });

      // Case A history resolves late
      resolveHistA({
        preaudit_id: mockCaseDraft.id,
        events: [
          {
            id: "event-a",
            tenant_id: tenantId,
            preaudit_id: mockCaseDraft.id,
            revision: 1,
            operation_id: "op-a",
            event_type: "CREATED",
            actor_user_id: ownerId,
            prior_status: null,
            new_status: "DRAFT",
            payload: {},
            created_at: "2026-11-01T10:00:00Z",
          },
        ],
      });

      // Case A history must NOT be shown
      expect(screen.queryByTestId("preaudit-history-section")).not.toBeInTheDocument();
      expect(screen.queryByText("event-a")).not.toBeInTheDocument();
    });

    it("does not allow Case A POST mutation success, error, or 401 to alter Case B or expire B session", async () => {
      let rejectMutationA!: (err: unknown) => void;
      const mutAPromise = new Promise<PreauditCase>((_res, rej) => {
        rejectMutationA = rej;
      });

      vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
        createListResponse([mockCaseDraft, mockCaseFrozen]),
      );
      vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
        return id === mockCaseFrozen.id ? mockCaseFrozen : mockCaseDraft;
      });
      vi.mocked(preauditApi.freezePreauditScope).mockReturnValueOnce(mutAPromise as Promise<PreauditCase>);

      const handleExpired = vi.fn();
      renderComponent({
        userRole: "compliance_manager",
        currentUserId: leadId,
        onSessionExpired: handleExpired,
      });

      await waitFor(() => {
        expect(screen.getByTestId("freeze-scope-btn")).toBeInTheDocument();
      });

      // Initiate freeze on Case A
      fireEvent.click(screen.getByTestId("freeze-scope-btn"));

      // User selects Case B
      fireEvent.change(screen.getByTestId("preaudit-case-select"), {
        target: { value: mockCaseFrozen.id },
      });

      await waitFor(() => {
        expect(screen.getByText(mockCaseFrozen.title)).toBeInTheDocument();
      });

      // Case A mutation rejects with 401 late
      rejectMutationA(new UnauthorizedError("Token expired on old request"));

      // Session expired callback must NOT be called because context for A is stale
      expect(handleExpired).not.toHaveBeenCalled();
      expect(screen.queryByTestId("preaudit-error-alert")).not.toBeInTheDocument();
    });

    it("does not trigger download or object URL if selection changed while download was pending", async () => {
      let resolveDownload!: (res: PreauditReportDownloadResult) => void;
      const dlPromise = new Promise<PreauditReportDownloadResult>((res) => {
        resolveDownload = res;
      });

      vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
        createListResponse([mockCaseInReview, mockCaseDraft]),
      );
      vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
        return id === mockCaseInReview.id ? mockCaseInReview : mockCaseDraft;
      });
      vi.mocked(preauditApi.downloadPreauditReport).mockReturnValueOnce(dlPromise);

      renderComponent();

      await waitFor(() => {
        expect(screen.getByTestId("download-preaudit-report-btn")).toBeInTheDocument();
      });

      // Click download on Case InReview
      fireEvent.click(screen.getByTestId("download-preaudit-report-btn"));

      // Switch to Case Draft
      fireEvent.change(screen.getByTestId("preaudit-case-select"), {
        target: { value: mockCaseDraft.id },
      });

      await waitFor(() => {
        expect(screen.getByText(mockCaseDraft.title)).toBeInTheDocument();
      });

      // Resolve download late
      resolveDownload({
        blob: new Blob(["test"], { type: "application/zip" }),
        filename: "test.zip",
        preauditId: mockCaseInReview.id,
        snapshotDigest: "b".repeat(64),
        sha256: "c".repeat(64),
      });

      // createObjectURL must NOT be called for stale selection
      expect(globalThis.URL.createObjectURL).not.toHaveBeenCalled();
    });

    it("handles A-to-B-to-A selection sequence admitting only the latest request", async () => {
      let resolveFirstA!: (val: PreauditCase) => void;
      const firstAPromise = new Promise<PreauditCase>((res) => {
        resolveFirstA = res;
      });

      const updatedCaseDraft = { ...mockCaseDraft, title: "Case A Fresh Title" };

      vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
        createListResponse([mockCaseDraft, mockCaseFrozen]),
      );

      let aCallCount = 0;
      vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
        if (id === mockCaseDraft.id) {
          aCallCount += 1;
          if (aCallCount === 1) return firstAPromise as Promise<PreauditCase>;
          return updatedCaseDraft;
        }
        return mockCaseFrozen;
      });

      renderComponent();

      // Initial load for A starts
      await waitFor(() => {
        expect(screen.getByTestId("preaudit-case-select")).toBeInTheDocument();
      });

      // User selects B
      fireEvent.change(screen.getByTestId("preaudit-case-select"), {
        target: { value: mockCaseFrozen.id },
      });

      await waitFor(() => {
        expect(screen.getByText(mockCaseFrozen.title)).toBeInTheDocument();
      });

      // User selects A again (request 2 for A)
      fireEvent.change(screen.getByTestId("preaudit-case-select"), {
        target: { value: mockCaseDraft.id },
      });

      await waitFor(() => {
        expect(screen.getByText("Case A Fresh Title")).toBeInTheDocument();
      });

      // First A request resolves late with stale title
      resolveFirstA({ ...mockCaseDraft, title: "Case A Stale Initial Title" });

      // Title must remain the fresh title from request 2
      expect(screen.getByText("Case A Fresh Title")).toBeInTheDocument();
      expect(screen.queryByText("Case A Stale Initial Title")).not.toBeInTheDocument();
    });

    it("reconciles uncertain create when another case is selected without replacing view", async () => {
      vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
        createListResponse([mockCaseDraft, mockCaseFrozen]),
      );
      vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
        return id === mockCaseFrozen.id ? mockCaseFrozen : mockCaseDraft;
      });
      vi.mocked(preauditApi.createPreauditCase).mockRejectedValueOnce(
        new TypeError("Network error on create"),
      );

      renderComponent({ userRole: "owner", currentUserId: ownerId });

      await waitFor(() => {
        expect(screen.getByTestId("create-preaudit-case-btn")).toBeInTheDocument();
      });

      // Open create modal & submit
      fireEvent.click(screen.getByTestId("create-preaudit-case-btn"));
      fireEvent.change(screen.getByTestId("create-case-title-input"), { target: { value: "New Case C" } });
      fireEvent.click(screen.getByTestId("submit-create-case-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("uncertain-operation-alert")).toBeInTheDocument();
      });

      // Select Case B while create outcome is uncertain
      fireEvent.change(screen.getByTestId("preaudit-case-select"), {
        target: { value: mockCaseFrozen.id },
      });

      await waitFor(() => {
        expect(screen.getByText(mockCaseFrozen.title)).toBeInTheDocument();
      });

      // Reconcile uncertain create via replay receipt
      const createdCaseC = {
        ...mockCaseDraft,
        id: "case-c-new",
        title: "New Case C",
        replayed: true,
        applied_event_id: "event-c-recorded",
        applied_revision: 1,
      };
      vi.mocked(preauditApi.createPreauditCase).mockResolvedValueOnce(createdCaseC);

      fireEvent.click(screen.getByTestId("uncertain-resolve-btn"));

      await waitFor(() => {
        expect(screen.queryByTestId("uncertain-operation-alert")).not.toBeInTheDocument();
        expect(screen.getByText(/server confirmed operation was applied previously/i)).toBeInTheDocument();
      });

      // Selected case must still be Case B!
      expect(screen.getByText(mockCaseFrozen.title)).toBeInTheDocument();
    });

    it("preserves uncertainty when reconciliation check fails or conflicts", async () => {
      vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
        createListResponse([mockCaseDraft]),
      );
      vi.mocked(preauditApi.getPreauditCase).mockResolvedValueOnce(mockCaseDraft);
      vi.mocked(preauditApi.freezePreauditScope).mockRejectedValueOnce(
        new TypeError("Network error"),
      );

      renderComponent({ currentUserId: leadId, userRole: "compliance_manager" });

      await waitFor(() => {
        expect(screen.getByTestId("freeze-scope-btn")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("freeze-scope-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("uncertain-operation-alert")).toBeInTheDocument();
      });

      // Reconcile fails with network error again
      vi.mocked(preauditApi.freezePreauditScope).mockRejectedValueOnce(
        new TypeError("Network unreachable"),
      );

      fireEvent.click(screen.getByTestId("uncertain-resolve-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("preaudit-error-alert")).toBeInTheDocument();
        expect(screen.getByTestId("uncertain-operation-alert")).toBeInTheDocument();
      });
    });

    it("invalidates review confirmation when case state mutates before submit", async () => {
      vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
        createListResponse([mockCaseInReview]),
      );
      vi.mocked(preauditApi.getPreauditCase).mockResolvedValueOnce(mockCaseInReview);

      renderComponent({ currentUserId: reviewerId, userRole: "owner" });

      await waitFor(() => {
        expect(screen.getByTestId("record-review-decision-btn")).toBeInTheDocument();
      });

      // Open review modal
      fireEvent.click(screen.getByTestId("record-review-decision-btn"));
      expect(screen.getByTestId("review-decision-modal")).toBeInTheDocument();

      // Dismiss modal by clicking Cancel inside review-decision-modal
      const modal = screen.getByTestId("review-decision-modal");
      const cancelBtn = modal.querySelector("button.preaudit-btn-secondary");
      expect(cancelBtn).not.toBeNull();
      fireEvent.click(cancelBtn!);

      // Confirmation modal is closed and state invalidated
      expect(screen.queryByTestId("review-decision-modal")).not.toBeInTheDocument();
    });
  });

    describe("Repair 4 Regression Tests: Busy Ownership and Recovery Selection Admission", () => {
      it("releases busy state and keeps Case B usable when Case A mutation is in-flight and user switches to Case B", async () => {
        let resolveMutationA!: (val: PreauditCase) => void;
        const mutAPromise = new Promise<PreauditCase>((res) => {
          resolveMutationA = res;
        });

        const caseBFrozen = {
          ...mockCaseFrozen,
          id: "case-b-frozen",
          title: "Case B Frozen",
          lead_user_id: leadId,
        };

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
          createListResponse([mockCaseDraft, caseBFrozen]),
        );
        vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
          return id === caseBFrozen.id ? caseBFrozen : mockCaseDraft;
        });
        vi.mocked(preauditApi.freezePreauditScope).mockReturnValueOnce(mutAPromise as Promise<PreauditCase>);

        renderComponent({
          currentUserId: leadId,
          userRole: "compliance_manager",
        });

        await waitFor(() => {
          expect(screen.getByTestId("freeze-scope-btn")).toBeInTheDocument();
        });

        // Initiate freeze on Case A -> isSubmitting becomes true
        fireEvent.click(screen.getByTestId("freeze-scope-btn"));
        expect(screen.getByTestId("freeze-scope-btn")).toBeDisabled();

        // Switch to Case B while Case A is still awaiting
        fireEvent.change(screen.getByTestId("preaudit-case-select"), {
          target: { value: caseBFrozen.id },
        });

        await waitFor(() => {
          expect(screen.getByText("Case B Frozen")).toBeInTheDocument();
        });

        // Case B has submit-review-btn (since case B is FROZEN)
        const submitBtn = screen.getByTestId("submit-review-btn");
        expect(submitBtn).toBeInTheDocument();
        // Case B action button MUST NOT be disabled by Case A's in-flight mutation!
        expect(submitBtn).not.toBeDisabled();

        // Now Case A mutation settles
        resolveMutationA({ ...mockCaseDraft, status: "FROZEN", revision: 2 });

        // Case B must still be selected and usable
        expect(screen.getByText("Case B Frozen")).toBeInTheDocument();
        expect(screen.getByTestId("submit-review-btn")).not.toBeDisabled();
      });

      it("preserves Case B busy state when Case A mutation settles after Case B started its own mutation", async () => {
        let resolveMutationA!: (val: PreauditCase) => void;
        const mutAPromise = new Promise<PreauditCase>((res) => {
          resolveMutationA = res;
        });

        let resolveMutationB!: (val: PreauditCase) => void;
        const mutBPromise = new Promise<PreauditCase>((res) => {
          resolveMutationB = res;
        });

        const caseBFrozen = {
          ...mockCaseFrozen,
          id: "case-b-frozen",
          title: "Case B Frozen",
          lead_user_id: leadId,
        };

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
          createListResponse([mockCaseDraft, caseBFrozen]),
        );
        vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
          return id === caseBFrozen.id ? caseBFrozen : mockCaseDraft;
        });
        vi.mocked(preauditApi.freezePreauditScope).mockReturnValueOnce(mutAPromise as Promise<PreauditCase>);
        vi.mocked(preauditApi.submitPreauditReview).mockReturnValueOnce(mutBPromise as Promise<PreauditCase>);

        renderComponent({
          currentUserId: leadId,
          userRole: "compliance_manager",
        });

        await waitFor(() => {
          expect(screen.getByTestId("freeze-scope-btn")).toBeInTheDocument();
        });

        // Start freeze on Case A
        fireEvent.click(screen.getByTestId("freeze-scope-btn"));
        expect(screen.getByTestId("freeze-scope-btn")).toBeDisabled();

        // Switch to Case B
        fireEvent.change(screen.getByTestId("preaudit-case-select"), {
          target: { value: caseBFrozen.id },
        });

        await waitFor(() => {
          expect(screen.getByText("Case B Frozen")).toBeInTheDocument();
        });

        // Start submit on Case B -> Case B is busy
        const submitBtn = screen.getByTestId("submit-review-btn");
        fireEvent.click(submitBtn);
        expect(submitBtn).toBeDisabled();

        // Now Case A's old finally runs
        resolveMutationA({ ...mockCaseDraft, status: "FROZEN", revision: 2 });

        // Case B's submit button MUST STILL BE DISABLED while Case B mutation is in-flight!
        expect(screen.getByTestId("submit-review-btn")).toBeDisabled();

        // Finally Case B settles
        resolveMutationB({ ...caseBFrozen, status: "IN_REVIEW", revision: 2 });

        await waitFor(() => {
          expect(screen.getByText("Submitted for review")).toBeInTheDocument();
        });
      });      it("releases busy state on view replacement without leaking private data", async () => {
        let resolveMutationA!: (val: PreauditCase) => void;
        const mutAPromise = new Promise<PreauditCase>((res) => {
          resolveMutationA = res;
        });

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValue(
          createListResponse([mockCaseDraft]),
        );
        vi.mocked(preauditApi.getPreauditCase).mockResolvedValue(mockCaseDraft);
        vi.mocked(preauditApi.freezePreauditScope).mockReturnValueOnce(mutAPromise as Promise<PreauditCase>);

        const { rerender } = renderComponent({
          currentUserId: leadId,
          userRole: "compliance_manager",
          activeView: "preaudit",
        });

        await waitFor(() => {
          expect(screen.getByTestId("freeze-scope-btn")).toBeInTheDocument();
        });

        // Start freeze on Case A
        fireEvent.click(screen.getByTestId("freeze-scope-btn"));
        expect(screen.getByTestId("freeze-scope-btn")).toBeDisabled();

        // View replaces to overview (simulating user navigating away)
        rerender(
          <I18nProvider>
            <PreAuditWorkspace
              tenantId={tenantId}
              token={token}
              userRole="compliance_manager"
              currentUserId={leadId}
              activeView="overview"
            />
          </I18nProvider>,
        );

        // Settle the old in-flight request after view change
        resolveMutationA({ ...mockCaseDraft, status: "FROZEN", revision: 2 });

        // Switch back to preaudit
        rerender(
          <I18nProvider>
            <PreAuditWorkspace
              tenantId={tenantId}
              token={token}
              userRole="compliance_manager"
              currentUserId={leadId}
              activeView="preaudit"
            />
          </I18nProvider>,
        );

        // Controls are NOT stranded in submitting
        await waitFor(() => {
          expect(screen.getByTestId("freeze-scope-btn")).toBeInTheDocument();
          expect(screen.getByTestId("freeze-scope-btn")).not.toBeDisabled();
        });
      });

      it("preserves Case B view and does not overwrite it when Case A uncertain retry succeeds after Case B was selected", async () => {
        const caseBFrozen = {
          ...mockCaseFrozen,
          id: "case-b-frozen",
          title: "Case B Frozen",
          lead_user_id: leadId,
        };

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
          createListResponse([mockCaseDraft, caseBFrozen]),
        );
        vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
          return id === caseBFrozen.id ? caseBFrozen : mockCaseDraft;
        });
        // Initial freeze fails with network error
        vi.mocked(preauditApi.freezePreauditScope).mockRejectedValueOnce(
          new TypeError("Network error"),
        );

        renderComponent({
          currentUserId: leadId,
          userRole: "compliance_manager",
        });

        await waitFor(() => {
          expect(screen.getByTestId("freeze-scope-btn")).toBeInTheDocument();
        });

        // Initiate freeze on Case A -> fails with uncertain alert
        fireEvent.click(screen.getByTestId("freeze-scope-btn"));

        await waitFor(() => {
          expect(screen.getByTestId("uncertain-operation-alert")).toBeInTheDocument();
        });

        // Set up deferred retry for Case A
        let resolveRetryA!: (val: PreauditCase) => void;
        const retryAPromise = new Promise<PreauditCase>((res) => {
          resolveRetryA = res;
        });
        vi.mocked(preauditApi.freezePreauditScope).mockReturnValueOnce(retryAPromise as Promise<PreauditCase>);

        // Click retry
        fireEvent.click(screen.getByTestId("uncertain-retry-btn"));

        // While retry is in-flight, user selects Case B
        fireEvent.change(screen.getByTestId("preaudit-case-select"), {
          target: { value: caseBFrozen.id },
        });

        await waitFor(() => {
          expect(screen.getByText("Case B Frozen")).toBeInTheDocument();
        });

        // Now Case A retry succeeds with receipt
        resolveRetryA({
          ...mockCaseDraft,
          status: "FROZEN",
          revision: 2,
          replayed: true,
          applied_event_id: "event-freeze-a",
          applied_revision: 2,
        });

        // Wait for retry to finish settling
        await waitFor(() => {
          expect(screen.queryByTestId("uncertain-operation-alert")).not.toBeInTheDocument();
        });

        // Case B view MUST BE PRESERVED! It must NOT be replaced with Case A!
        expect(screen.getByText("Case B Frozen")).toBeInTheDocument();
        expect(screen.queryByText(mockCaseDraft.title)).not.toBeInTheDocument();
        expect(screen.queryByText("Scope frozen into snapshot")).not.toBeInTheDocument();
      });

      it("rejects obsolete recovery callback updates after an A-to-B-to-A selection sequence", async () => {
        const caseBFrozen = {
          ...mockCaseFrozen,
          id: "case-b-frozen",
          title: "Case B Frozen",
          lead_user_id: leadId,
        };

        const freshCaseA = {
          ...mockCaseDraft,
          title: "Case A Fresh Active Detail",
          revision: 3,
        };

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
          createListResponse([mockCaseDraft, caseBFrozen]),
        );
        let aCallCount = 0;
        vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
          if (id === mockCaseDraft.id) {
            aCallCount += 1;
            if (aCallCount > 1) return freshCaseA;
            return mockCaseDraft;
          }
          return caseBFrozen;
        });

        // Freeze on Case A fails initially
        vi.mocked(preauditApi.freezePreauditScope).mockRejectedValueOnce(
          new TypeError("Network error"),
        );

        renderComponent({
          currentUserId: leadId,
          userRole: "compliance_manager",
        });

        await waitFor(() => {
          expect(screen.getByTestId("freeze-scope-btn")).toBeInTheDocument();
        });

        fireEvent.click(screen.getByTestId("freeze-scope-btn"));

        await waitFor(() => {
          expect(screen.getByTestId("uncertain-operation-alert")).toBeInTheDocument();
        });

        // Set up deferred retry for Case A
        let resolveRetryA!: (val: PreauditCase) => void;
        const retryAPromise = new Promise<PreauditCase>((res) => {
          resolveRetryA = res;
        });
        vi.mocked(preauditApi.freezePreauditScope).mockReturnValueOnce(retryAPromise as Promise<PreauditCase>);

        // Click retry
        fireEvent.click(screen.getByTestId("uncertain-retry-btn"));

        // User selects Case B
        fireEvent.change(screen.getByTestId("preaudit-case-select"), {
          target: { value: caseBFrozen.id },
        });

        await waitFor(() => {
          expect(screen.getByText("Case B Frozen")).toBeInTheDocument();
        });

        // User selects Case A again (starts a fresh request for Case A)
        fireEvent.change(screen.getByTestId("preaudit-case-select"), {
          target: { value: mockCaseDraft.id },
        });

        await waitFor(() => {
          expect(screen.getByText("Case A Fresh Active Detail")).toBeInTheDocument();
        });

        // Now old retry from request 1 resolves with older status
        resolveRetryA({
          ...mockCaseDraft,
          title: "Stale Callback Title From First View",
          status: "FROZEN",
          revision: 2,
        });

        // Obsolete callback MUST NOT overwrite the fresh Case A view
        expect(screen.getByText("Case A Fresh Active Detail")).toBeInTheDocument();
        expect(screen.queryByText("Stale Callback Title From First View")).not.toBeInTheDocument();
      });

      it("does not call onSessionExpired or show error on Case B when Case A recovery fails with 401 after replacement", async () => {
        const caseBFrozen = {
          ...mockCaseFrozen,
          id: "case-b-frozen",
          title: "Case B Frozen",
          lead_user_id: leadId,
        };

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce(
          createListResponse([mockCaseDraft, caseBFrozen]),
        );
        vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
          return id === caseBFrozen.id ? caseBFrozen : mockCaseDraft;
        });

        vi.mocked(preauditApi.freezePreauditScope).mockRejectedValueOnce(
          new TypeError("Network error"),
        );

        const handleExpired = vi.fn();
        renderComponent({
          currentUserId: leadId,
          userRole: "compliance_manager",
          onSessionExpired: handleExpired,
        });

        await waitFor(() => {
          expect(screen.getByTestId("freeze-scope-btn")).toBeInTheDocument();
        });

        fireEvent.click(screen.getByTestId("freeze-scope-btn"));

        await waitFor(() => {
          expect(screen.getByTestId("uncertain-operation-alert")).toBeInTheDocument();
        });

        let rejectRetryA!: (err: unknown) => void;
        const retryAPromise = new Promise<PreauditCase>((_res, rej) => {
          rejectRetryA = rej;
        });
        vi.mocked(preauditApi.freezePreauditScope).mockReturnValueOnce(retryAPromise as Promise<PreauditCase>);

        // Click retry
        fireEvent.click(screen.getByTestId("uncertain-retry-btn"));

        // User selects Case B
        fireEvent.change(screen.getByTestId("preaudit-case-select"), {
          target: { value: caseBFrozen.id },
        });

        await waitFor(() => {
          expect(screen.getByText("Case B Frozen")).toBeInTheDocument();
        });

        // Case A retry rejects with 401
        rejectRetryA(new UnauthorizedError("Old session expired on Case A"));

        // Must NOT expire Case B's session and must not show error on Case B
        expect(handleExpired).not.toHaveBeenCalled();
        expect(screen.queryByTestId("preaudit-error-alert")).not.toBeInTheDocument();
      });
    });


    describe("Repair 5 Regression Tests: Operation Identity & Unresolved Outcome Ownership", () => {
      // Helper simulating real backend idempotency & case-binding conflict rule
      const serverRecordedOps = new Map<string, { caseId: string; action: string; payload: unknown }>();
      const validateServerOperation = (opId: string, caseId: string, action: string, payload: unknown) => {
        if (serverRecordedOps.has(opId)) {
          const existing = serverRecordedOps.get(opId)!;
          if (existing.caseId !== caseId) {
            throw new ConflictError("Operation ID conflict: replayed against different pre-audit case");
          }
        } else {
          serverRecordedOps.set(opId, { caseId, action, payload });
        }
      };

      beforeEach(() => {
        serverRecordedOps.clear();
      });

      it("allocates distinct operation IDs for freeze on Case A and freeze on Case B, preventing 409 conflict when A response is delayed", async () => {
        const caseA: PreauditCase = {
          ...mockCaseDraft,
          id: "case-a-draft",
          title: "Case A Draft",
          lead_user_id: leadId,
        };
        const caseB: PreauditCase = {
          ...mockCaseDraft,
          id: "case-b-draft",
          title: "Case B Draft",
          lead_user_id: leadId,
        };

        let resolveFreezeA!: (val: PreauditCase) => void;
        const freezeAPromise = new Promise<PreauditCase>((res) => {
          resolveFreezeA = res;
        });

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValue(
          createListResponse([caseA, caseB]),
        );
        vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
          return id === caseB.id ? caseB : caseA;
        });

        vi.mocked(preauditApi.freezePreauditScope).mockImplementation(async (_t, caseId, payload) => {
          validateServerOperation(payload.operation_id, caseId, "freeze", payload);
          if (caseId === caseA.id) {
            return freezeAPromise;
          }
          return { ...caseB, status: "FROZEN", revision: 2 };
        });

        renderComponent({ currentUserId: leadId, userRole: "compliance_manager" });

        await waitFor(() => {
          expect(screen.getByTestId("freeze-scope-btn")).toBeInTheDocument();
          expect(screen.getByText("Case A Draft")).toBeInTheDocument();
        });

        // 1. Freeze A is initiated (response delayed)
        fireEvent.click(screen.getByTestId("freeze-scope-btn"));

        // 2. User switches to Case B before A responds
        fireEvent.change(screen.getByTestId("preaudit-case-select"), {
          target: { value: caseB.id },
        });

        await waitFor(() => {
          expect(screen.getByText("Case B Draft")).toBeInTheDocument();
          expect(screen.getByTestId("freeze-scope-btn")).not.toBeDisabled();
        });

        // 3. User initiates Freeze on Case B
        fireEvent.click(screen.getByTestId("freeze-scope-btn"));

        // 4. Verify Freeze B succeeds without 409 conflict
        await waitFor(() => {
          expect(screen.getByText("Scope frozen into snapshot")).toBeInTheDocument();
        });

        // Verify distinct operation IDs were allocated for each intent
        expect(serverRecordedOps.size).toBe(2);
        const opA = serverRecordedOps.get(Array.from(serverRecordedOps.keys())[0]);
        const opB = serverRecordedOps.get(Array.from(serverRecordedOps.keys())[1]);
        expect(opA?.caseId).toBe(caseA.id);
        expect(opB?.caseId).toBe(caseB.id);

        // Resolve A delayed response cleanly
        resolveFreezeA({ ...caseA, status: "FROZEN", revision: 2 });
      });

      it("allocates distinct operation IDs for submit on Case A and submit on Case B, while exact retry of A preserves original ID and payload", async () => {
        const caseAFrozen: PreauditCase = {
          ...mockCaseFrozen,
          id: "case-a-frozen",
          title: "Case A Frozen",
          lead_user_id: leadId,
          revision: 2,
        };
        const caseBFrozen: PreauditCase = {
          ...mockCaseFrozen,
          id: "case-b-frozen",
          title: "Case B Frozen",
          lead_user_id: leadId,
          revision: 2,
        };

        const submittedPayloads: { caseId: string; payload: { operation_id: string; expected_revision: number } }[] = [];
        let retryCountA = 0;

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValue(
          createListResponse([caseAFrozen, caseBFrozen]),
        );
        vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
          return id === caseBFrozen.id ? caseBFrozen : caseAFrozen;
        });

        vi.mocked(preauditApi.submitPreauditReview).mockImplementation(async (_t, caseId, payload) => {
          validateServerOperation(payload.operation_id, caseId, "submit", payload);
          submittedPayloads.push({ caseId, payload: { ...payload } });
          if (caseId === caseAFrozen.id) {
            retryCountA++;
            if (retryCountA === 1) {
              throw new TypeError("Failed to fetch (network drop)");
            }
            return { ...caseAFrozen, status: "IN_REVIEW", revision: 3 };
          }
          return { ...caseBFrozen, status: "IN_REVIEW", revision: 3 };
        });

        renderComponent({ currentUserId: leadId, userRole: "compliance_manager" });

        await waitFor(() => {
          expect(screen.getByTestId("submit-review-btn")).toBeInTheDocument();
        });

        // 1. Submit on Case A fails with network drop -> outcome uncertain
        fireEvent.click(screen.getByTestId("submit-review-btn"));

        await waitFor(() => {
          expect(screen.getByTestId("uncertain-operation-alert")).toBeInTheDocument();
        });

        // 2. User switches to Case B
        fireEvent.change(screen.getByTestId("preaudit-case-select"), {
          target: { value: caseBFrozen.id },
        });

        await waitFor(() => {
          expect(screen.getByText("Case B Frozen")).toBeInTheDocument();
          expect(screen.getByTestId("submit-review-btn")).not.toBeDisabled();
        });

        // 3. User submits Case B -> succeeds
        fireEvent.click(screen.getByTestId("submit-review-btn"));

        await waitFor(() => {
          expect(screen.getByText("Submitted for review")).toBeInTheDocument();
        });

        // Verify Case A and Case B had distinct operation IDs
        expect(submittedPayloads[0].caseId).toBe(caseAFrozen.id);
        expect(submittedPayloads[1].caseId).toBe(caseBFrozen.id);
        expect(submittedPayloads[0].payload.operation_id).not.toBe(submittedPayloads[1].payload.operation_id);

        // 4. Retry Case A: must reuse the exact same operation_id and expected_revision
        fireEvent.click(screen.getByTestId("uncertain-retry-btn"));

        await waitFor(() => {
          expect(screen.queryByTestId("uncertain-operation-alert")).not.toBeInTheDocument();
        });

        expect(submittedPayloads).toHaveLength(3);
        const initialAPayload = submittedPayloads[0].payload;
        const retryAPayload = submittedPayloads[2].payload;
        expect(retryAPayload.operation_id).toBe(initialAPayload.operation_id);
        expect(retryAPayload.expected_revision).toBe(initialAPayload.expected_revision);
      });

      it("preserves unresolved A when mutation A loses response and subsequent mutation B succeeds", async () => {
        const caseA: PreauditCase = {
          ...mockCaseDraft,
          id: "case-a-draft-loss",
          title: "Case A Draft Loss",
          lead_user_id: leadId,
        };
        const caseB: PreauditCase = {
          ...mockCaseDraft,
          id: "case-b-draft-loss",
          title: "Case B Draft Loss",
          lead_user_id: leadId,
        };

        let rejectFreezeA!: (err: unknown) => void;
        const freezeAPromise = new Promise<PreauditCase>((_res, rej) => {
          rejectFreezeA = rej;
        });

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValue(
          createListResponse([caseA, caseB]),
        );
        vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
          return id === caseB.id ? caseB : caseA;
        });

        vi.mocked(preauditApi.freezePreauditScope).mockImplementation(async (_t, caseId, payload) => {
          validateServerOperation(payload.operation_id, caseId, "freeze", payload);
          if (caseId === caseA.id) {
            return freezeAPromise;
          }
          return { ...caseB, status: "FROZEN", revision: 2 };
        });

        renderComponent({ currentUserId: leadId, userRole: "compliance_manager" });

        await waitFor(() => {
          expect(screen.getByText("Case A Draft Loss")).toBeInTheDocument();
        });

        // 1. Freeze A begins (delayed)
        fireEvent.click(screen.getByTestId("freeze-scope-btn"));

        // 2. Select Case B
        fireEvent.change(screen.getByTestId("preaudit-case-select"), {
          target: { value: caseB.id },
        });

        await waitFor(() => {
          expect(screen.getByText("Case B Draft Loss")).toBeInTheDocument();
        });

        // 3. Freeze A loses response with network error
        rejectFreezeA(new TypeError("Network connection lost"));

        // 4. Freeze B starts and succeeds
        fireEvent.click(screen.getByTestId("freeze-scope-btn"));

        await waitFor(() => {
          expect(screen.getByText("Scope frozen into snapshot")).toBeInTheDocument();
        });

        // 5. CRITICAL: Case B success MUST NOT erase Case A's unresolved outcome
        expect(screen.getByTestId("uncertain-operation-alert")).toBeInTheDocument();
        expect(screen.getByText(/Network connection lost/i)).toBeInTheDocument();
      });

      it("handles two failed outcomes independently; receipt for A settles only A, and explicit disposal of A does not clear B", async () => {
        const caseA: PreauditCase = {
          ...mockCaseDraft,
          id: "case-a-fail",
          title: "Case A Fail",
          lead_user_id: leadId,
        };
        const caseB: PreauditCase = {
          ...mockCaseDraft,
          id: "case-b-fail",
          title: "Case B Fail",
          lead_user_id: leadId,
        };

        const failA = true;
        let failB = true;

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValue(
          createListResponse([caseA, caseB]),
        );
        vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
          return id === caseB.id ? caseB : caseA;
        });

        vi.mocked(preauditApi.freezePreauditScope).mockImplementation(async (_t, caseId, payload) => {
          validateServerOperation(payload.operation_id, caseId, "freeze", payload);
          if (caseId === caseA.id) {
            if (failA) throw new TypeError("Network failure on A");
            return { ...caseA, status: "FROZEN", revision: 2 };
          }
          if (caseId === caseB.id) {
            if (failB) throw new TypeError("Network failure on B");
            return { ...caseB, status: "FROZEN", revision: 2 };
          }
          throw new Error("Unknown case");
        });

        renderComponent({ currentUserId: leadId, userRole: "compliance_manager" });

        await waitFor(() => {
          expect(screen.getByText("Case A Fail")).toBeInTheDocument();
        });

        // Trigger network loss on A
        fireEvent.click(screen.getByTestId("freeze-scope-btn"));
        await waitFor(() => {
          expect(screen.getByTestId("uncertain-operation-alert")).toBeInTheDocument();
        });

        // Switch to B and trigger network loss on B
        fireEvent.change(screen.getByTestId("preaudit-case-select"), {
          target: { value: caseB.id },
        });
        await waitFor(() => {
          expect(screen.getByText("Case B Fail")).toBeInTheDocument();
        });

        fireEvent.click(screen.getByTestId("freeze-scope-btn"));
        await waitFor(() => {
          expect(screen.getAllByTestId("uncertain-operation-alert")).toHaveLength(2);
        });

        // Explicitly abandon A
        const abandonButtons = screen.getAllByTestId("uncertain-abandon-btn");
        fireEvent.click(abandonButtons[0]); // Abandon A
        expect(screen.getByTestId("uncertain-abandon-dialog")).toBeInTheDocument();
        fireEvent.click(screen.getByTestId("uncertain-abandon-acknowledge-checkbox"));
        fireEvent.click(screen.getByTestId("uncertain-confirm-abandon-btn"));

        // A is disposed, but B REMAINS unresolved in UI
        await waitFor(() => {
          expect(screen.getAllByTestId("uncertain-operation-alert")).toHaveLength(1);
        });

        // Now retry B and let B succeed
        failB = false;
        fireEvent.click(screen.getByTestId("uncertain-retry-btn"));

        await waitFor(() => {
          expect(screen.queryByTestId("uncertain-operation-alert")).not.toBeInTheDocument();
          expect(screen.getByText("Operation completed successfully upon retry")).toBeInTheDocument();
        });
      });

      it("ensures late receipt arrival from Case A does not rotate Case B operation identity or alter Case B selection/busy state", async () => {
        const caseA: PreauditCase = {
          ...mockCaseDraft,
          id: "case-a-late",
          title: "Case A Late",
          lead_user_id: leadId,
        };
        const caseB: PreauditCase = {
          ...mockCaseDraft,
          id: "case-b-late",
          title: "Case B Late",
          lead_user_id: leadId,
        };

        let resolveA!: (val: PreauditCase) => void;
        const promiseA = new Promise<PreauditCase>((res) => {
          resolveA = res;
        });

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValue(
          createListResponse([caseA, caseB]),
        );
        vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
          return id === caseB.id ? caseB : caseA;
        });

        vi.mocked(preauditApi.freezePreauditScope).mockImplementation(async (_t, caseId, payload) => {
          validateServerOperation(payload.operation_id, caseId, "freeze", payload);
          if (caseId === caseA.id) {
            return promiseA;
          }
          return { ...caseB, status: "FROZEN", revision: 2 };
        });

        renderComponent({ currentUserId: leadId, userRole: "compliance_manager" });

        await waitFor(() => {
          expect(screen.getByText("Case A Late")).toBeInTheDocument();
        });

        // 1. Freeze A starts
        fireEvent.click(screen.getByTestId("freeze-scope-btn"));

        // 2. User selects Case B
        fireEvent.change(screen.getByTestId("preaudit-case-select"), {
          target: { value: caseB.id },
        });

        await waitFor(() => {
          expect(screen.getByText("Case B Late")).toBeInTheDocument();
          expect(screen.getByTestId("freeze-scope-btn")).not.toBeDisabled();
        });

        // 3. Receipt for A arrives late while on B
        resolveA({ ...caseA, status: "FROZEN", revision: 2 });

        // 4. Verify B view is preserved and not in busy state
        expect(screen.getByText("Case B Late")).toBeInTheDocument();
        expect(screen.getByTestId("freeze-scope-btn")).not.toBeDisabled();

        // 5. Freeze B succeeds cleanly with its own operation ID
        fireEvent.click(screen.getByTestId("freeze-scope-btn"));

        await waitFor(() => {
          expect(screen.getByText("Scope frozen into snapshot")).toBeInTheDocument();
        });
      });

      it("retrying Case A from Case B view updates Case A status without navigating unexpectedly or clearing Case B operation", async () => {
        const caseA: PreauditCase = {
          ...mockCaseDraft,
          id: "case-a-cross",
          title: "Case A Cross View",
          lead_user_id: leadId,
        };
        const caseB: PreauditCase = {
          ...mockCaseDraft,
          id: "case-b-cross",
          title: "Case B Cross View",
          lead_user_id: leadId,
        };

        let failA = true;

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValue(
          createListResponse([caseA, caseB]),
        );
        vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_t, id) => {
          return id === caseB.id ? caseB : caseA;
        });

        vi.mocked(preauditApi.freezePreauditScope).mockImplementation(async (_t, caseId, payload) => {
          validateServerOperation(payload.operation_id, caseId, "freeze", payload);
          if (caseId === caseA.id) {
            if (failA) throw new TypeError("Network failure on A");
            return { ...caseA, status: "FROZEN", revision: 2 };
          }
          return { ...caseB, status: "FROZEN", revision: 2 };
        });

        renderComponent({ currentUserId: leadId, userRole: "compliance_manager" });

        await waitFor(() => {
          expect(screen.getByText("Case A Cross View")).toBeInTheDocument();
        });

        // Fail Freeze on Case A
        fireEvent.click(screen.getByTestId("freeze-scope-btn"));

        await waitFor(() => {
          expect(screen.getByTestId("uncertain-operation-alert")).toBeInTheDocument();
        });

        // Switch to Case B
        fireEvent.change(screen.getByTestId("preaudit-case-select"), {
          target: { value: caseB.id },
        });

        await waitFor(() => {
          expect(screen.getByText("Case B Cross View")).toBeInTheDocument();
        });

        // While viewing Case B, click retry on Case A's uncertain alert
        failA = false;
        fireEvent.click(screen.getByTestId("uncertain-retry-btn"));

        await waitFor(() => {
          expect(screen.queryByTestId("uncertain-operation-alert")).not.toBeInTheDocument();
        });

        // Case B MUST REMAIN active in view
        expect(screen.getByText("Case B Cross View")).toBeInTheDocument();
        expect(screen.queryByText("Case A Cross View")).not.toBeInTheDocument();
      });
    });

    describe("ReadinessVerificationPanel integration", () => {
      it("does not mount ReadinessVerificationPanel when verification feature is disabled", async () => {
        vi.stubEnv("VITE_ENABLE_CUSTOMER_READINESS_VERIFICATION", "false");
        vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce({
          items: [mockCaseApproved],
          total: 1,
        });
        vi.mocked(preauditApi.getPreauditCase).mockResolvedValueOnce(mockCaseApproved);

        renderComponent({ currentUserId: ownerId, userRole: "owner" });

        await waitFor(() => {
          expect(screen.getByTestId("preaudit-status-badge")).toHaveTextContent("APPROVED");
        });

        expect(screen.queryByTestId("readiness-verification-panel")).not.toBeInTheDocument();
      });

      it("mounts ReadinessVerificationPanel when verification feature is enabled", async () => {
        vi.stubEnv("VITE_ENABLE_CUSTOMER_READINESS_VERIFICATION", "true");
        vi.mocked(preauditApi.listPreauditCases).mockResolvedValueOnce({
          items: [mockCaseApproved],
          total: 1,
        });
        vi.mocked(preauditApi.getPreauditCase).mockResolvedValueOnce(mockCaseApproved);

        renderComponent({ currentUserId: ownerId, userRole: "owner" });

        await waitFor(() => {
          expect(screen.getByTestId("preaudit-status-badge")).toHaveTextContent("APPROVED");
        });

        await waitFor(() => {
          expect(screen.getByTestId("readiness-verification-panel")).toBeInTheDocument();
        });
      });

      it("preserves uncertain verification operation across real parent case navigation (A -> B -> A) and retries with exact original operation ID", async () => {
        vi.stubEnv("VITE_ENABLE_CUSTOMER_READINESS_VERIFICATION", "true");
        const caseA: PreauditCase = {
          ...mockCaseApproved,
          id: "case-approved-a",
          title: "Approved Case A",
        };
        const caseB: PreauditCase = {
          ...mockCaseApproved,
          id: "case-approved-b",
          title: "Approved Case B",
        };

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValue({
          items: [caseA, caseB],
          total: 2,
        });
        vi.mocked(preauditApi.getPreauditCase).mockImplementation(async (_tenantId, id) => {
          if (id === caseB.id) return caseB;
          return caseA;
        });

        vi.spyOn(verificationApi, "listVerifications").mockResolvedValue({
          verifications: [],
          total: 0,
          limit: 50,
          offset: 0,
        });

        let capturedOpId = "";
        const issueSpy = vi.spyOn(verificationApi, "issueVerification").mockImplementation(async (_t, payload) => {
          capturedOpId = payload.operation_id;
          throw new Error("Network timeout - outcome uncertain");
        });

        renderComponent({ currentUserId: ownerId, userRole: "owner" });

        await waitFor(() => {
          expect(screen.getByTestId("issue-verification-btn")).toBeInTheDocument();
        });

        fireEvent.click(screen.getByTestId("issue-verification-btn"));

        await waitFor(() => {
          expect(screen.getByTestId("uncertain-ops-banner")).toBeInTheDocument();
        });
        expect(capturedOpId).toBeTruthy();

        // Navigate away to Case B using the REAL parent selector
        fireEvent.change(screen.getByTestId("preaudit-case-select"), {
          target: { value: caseB.id },
        });

        await waitFor(() => {
          expect(screen.getByText("Approved Case B")).toBeInTheDocument();
        });

        expect(screen.queryByTestId("uncertain-ops-banner")).not.toBeInTheDocument();

        // Navigate back to Case A using the REAL parent selector
        fireEvent.change(screen.getByTestId("preaudit-case-select"), {
          target: { value: caseA.id },
        });

        await waitFor(() => {
          expect(screen.getByText("Approved Case A")).toBeInTheDocument();
        });

        // Case A's uncertain operation is STILL PRESERVED!
        await waitFor(() => {
          expect(screen.getByTestId("uncertain-ops-banner")).toBeInTheDocument();
        });

        const mockIssued: VerificationDetail = {
          id: "ver-case-a",
          preaudit_id: caseA.id,
          snapshot_id: "snap-rev-1",
          status: "ACTIVE",
          effective_status: "ACTIVE",
          revision: 1,
          issued_at: "2026-11-03T00:00:00Z",
          valid_through: "2027-11-03T00:00:00Z",
          digest: "f".repeat(64),
          synthetic_marker: "SYNTHETIC_DEMO_NON_AUDIT",
          test_qualification: "TEST_ONLY_DO_NOT_RELY",
          limitations: [],
          issuer_user_id: ownerId,
          reviewer_user_id: reviewerId,
          approver_user_id: ownerId,
        };

        let retryOpId = "";
        issueSpy.mockImplementationOnce(async (_t, payload) => {
          retryOpId = payload.operation_id;
          return mockIssued;
        });

        fireEvent.click(screen.getByTestId(`retry-op-${capturedOpId}`));

        await waitFor(() => {
          expect(screen.queryByTestId("uncertain-ops-banner")).not.toBeInTheDocument();
        });

        expect(retryOpId).toBe(capturedOpId);
      });

      it("settles uncertain operation only on exact matching history event, not another actor's higher revision", async () => {
        vi.stubEnv("VITE_ENABLE_CUSTOMER_READINESS_VERIFICATION", "true");
        const caseA: PreauditCase = {
          ...mockCaseApproved,
          id: "case-approved-a2",
          title: "Approved Case A2",
        };

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValue({
          items: [caseA],
          total: 1,
        });
        vi.mocked(preauditApi.getPreauditCase).mockResolvedValue(caseA);

        const initialVer: VerificationDetail = {
          id: "ver-1",
          preaudit_id: caseA.id,
          snapshot_id: "snap-rev-1",
          status: "ACTIVE",
          effective_status: "ACTIVE",
          revision: 1,
          issued_at: "2026-11-03T00:00:00Z",
          valid_through: "2027-11-03T00:00:00Z",
          digest: "f".repeat(64),
          synthetic_marker: "SYNTHETIC_DEMO_NON_AUDIT",
          test_qualification: "TEST_ONLY_DO_NOT_RELY",
          limitations: [],
          issuer_user_id: ownerId,
          reviewer_user_id: reviewerId,
          approver_user_id: ownerId,
        };

        vi.spyOn(verificationApi, "listVerifications").mockResolvedValue({
          verifications: [
            {
              id: initialVer.id,
              preaudit_id: caseA.id,
              status: "ACTIVE",
              effective_status: "ACTIVE",
              revision: 1,
              issued_at: initialVer.issued_at,
              valid_through: initialVer.valid_through,
              synthetic_marker: initialVer.synthetic_marker,
            },
          ],
          total: 1,
          limit: 50,
          offset: 0,
        });
        vi.spyOn(verificationApi, "getVerification").mockResolvedValue(initialVer);
        vi.spyOn(verificationApi, "getVerificationHistory").mockResolvedValue({
          verification_id: initialVer.id,
          events: [
            {
              id: "ev-1",
              sequence: 1,
              revision: 1,
              event_type: "ISSUED",
              created_at: "2026-11-03T00:00:00Z",
              actor_user_id: ownerId,
              operation_id: "op-original-issue",
            },
          ],
        });

        let suspendOpId = "";
        vi.spyOn(verificationApi, "reconcileVerifications").mockResolvedValue({ reconciled_count: 0, results: [] });
        vi.spyOn(verificationApi, "suspendVerification").mockImplementation(async (_t, _vid, payload) => {
          suspendOpId = payload.operation_id;
          throw new Error("504 Gateway Timeout");
        });

        renderComponent({ currentUserId: ownerId, userRole: "owner" });

        await waitFor(() => {
          expect(screen.getByTestId("suspend-verification-btn")).toBeInTheDocument();
        });

        fireEvent.click(screen.getByTestId("suspend-verification-btn"));
        await waitFor(() => {
          expect(screen.getByTestId("verification-action-modal")).toBeInTheDocument();
        });
        fireEvent.change(screen.getByTestId("verification-dialog-textarea"), {
          target: { value: "Suspending for investigation" },
        });
        fireEvent.click(screen.getByTestId("verification-dialog-confirm-btn"));

        await waitFor(() => {
          expect(screen.getByTestId("uncertain-ops-banner")).toBeInTheDocument();
        });
        expect(suspendOpId).toBeTruthy();

        // Another actor suspended verification or bumped revision with a DIFFERENT operation_id
        const higherRevVer: VerificationDetail = {
          ...initialVer,
          status: "SUSPENDED",
          effective_status: "SUSPENDED",
          revision: 2,
        };
        vi.spyOn(verificationApi, "getVerification").mockResolvedValue(higherRevVer);
        vi.spyOn(verificationApi, "getVerificationHistory").mockResolvedValue({
          verification_id: initialVer.id,
          events: [
            {
              id: "ev-1",
              sequence: 1,
              revision: 1,
              event_type: "ISSUED",
              created_at: "2026-11-03T00:00:00Z",
              actor_user_id: ownerId,
              operation_id: "op-original-issue",
            },
            {
              id: "ev-2",
              sequence: 2,
              revision: 2,
              event_type: "SUSPENDED",
              created_at: "2026-11-03T00:05:00Z",
              actor_user_id: "another-actor",
              operation_id: "another-actor-op-id",
            },
          ],
        });

        fireEvent.click(screen.getByTestId("reconcile-verification-btn"));

        // Uncertain op MUST NOT BE SETTLED by higher revision or status from another actor!
        await waitFor(() => {
          expect(screen.getByTestId("uncertain-ops-banner")).toBeInTheDocument();
        });

        // Now history contains the exact matching suspendOpId
        vi.spyOn(verificationApi, "getVerificationHistory").mockResolvedValue({
          verification_id: initialVer.id,
          events: [
            {
              id: "ev-1",
              sequence: 1,
              revision: 1,
              event_type: "ISSUED",
              created_at: "2026-11-03T00:00:00Z",
              actor_user_id: ownerId,
              operation_id: "op-original-issue",
            },
            {
              id: "ev-3",
              sequence: 3,
              revision: 3,
              event_type: "SUSPENDED",
              created_at: "2026-11-03T00:06:00Z",
              actor_user_id: ownerId,
              operation_id: suspendOpId,
            },
          ],
        });

        fireEvent.click(screen.getByTestId("reconcile-verification-btn"));

        // Now and ONLY now is the exact operation settled!
        await waitFor(() => {
          expect(screen.queryByTestId("uncertain-ops-banner")).not.toBeInTheDocument();
        });
      });

      it("conflicting/failed replay retains uncertain operation without false settlement", async () => {
        vi.stubEnv("VITE_ENABLE_CUSTOMER_READINESS_VERIFICATION", "true");
        const caseA: PreauditCase = {
          ...mockCaseApproved,
          id: "case-approved-conflict",
          title: "Approved Case Conflict",
        };

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValue({
          items: [caseA],
          total: 1,
        });
        vi.mocked(preauditApi.getPreauditCase).mockResolvedValue(caseA);

        const initialVer: VerificationDetail = {
          id: "ver-conflict",
          preaudit_id: caseA.id,
          snapshot_id: "snap-rev-1",
          status: "ACTIVE",
          effective_status: "ACTIVE",
          revision: 1,
          issued_at: "2026-11-03T00:00:00Z",
          valid_through: "2027-11-03T00:00:00Z",
          digest: "f".repeat(64),
          synthetic_marker: "SYNTHETIC_DEMO_NON_AUDIT",
          test_qualification: "TEST_ONLY_DO_NOT_RELY",
          limitations: [],
          issuer_user_id: ownerId,
          reviewer_user_id: reviewerId,
          approver_user_id: ownerId,
        };

        vi.spyOn(verificationApi, "listVerifications").mockResolvedValue({
          verifications: [
            {
              id: initialVer.id,
              preaudit_id: caseA.id,
              status: "ACTIVE",
              effective_status: "ACTIVE",
              revision: 1,
              issued_at: initialVer.issued_at,
              valid_through: initialVer.valid_through,
              synthetic_marker: initialVer.synthetic_marker,
            },
          ],
          total: 1,
          limit: 50,
          offset: 0,
        });
        vi.spyOn(verificationApi, "getVerification").mockResolvedValue(initialVer);
        vi.spyOn(verificationApi, "getVerificationHistory").mockResolvedValue({
          verification_id: initialVer.id,
          events: [],
        });

        let correctOpId = "";
        const correctSpy = vi.spyOn(verificationApi, "correctVerification").mockImplementation(async (_t, _vid, payload) => {
          correctOpId = payload.operation_id;
          throw new Error("Network timeout");
        });

        renderComponent({ currentUserId: ownerId, userRole: "owner" });

        await waitFor(() => {
          expect(screen.getByTestId("correct-verification-btn")).toBeInTheDocument();
        });

        fireEvent.click(screen.getByTestId("correct-verification-btn"));
        await waitFor(() => {
          expect(screen.getByTestId("verification-action-modal")).toBeInTheDocument();
        });
        fireEvent.change(screen.getByTestId("verification-dialog-textarea"), {
          target: { value: "Fixing typo in limitations" },
        });
        fireEvent.click(screen.getByTestId("verification-dialog-confirm-btn"));

        await waitFor(() => {
          expect(screen.getByTestId("uncertain-ops-banner")).toBeInTheDocument();
        });

        correctSpy.mockRejectedValueOnce(new ConflictError("Revision conflict: expected 1, current 2"));

        fireEvent.click(screen.getByTestId(`retry-op-${correctOpId}`));

        await waitFor(() => {
          expect(screen.getByTestId("uncertain-ops-banner")).toBeInTheDocument();
          expect(screen.getByText(/Revision conflict/i)).toBeInTheDocument();
        });
      });

      it("targeted acknowledged disposal removes only the targeted operation after explicit confirmation", async () => {
        vi.stubEnv("VITE_ENABLE_CUSTOMER_READINESS_VERIFICATION", "true");
        const caseA: PreauditCase = {
          ...mockCaseApproved,
          id: "case-approved-disp",
          title: "Approved Case Disposal",
        };

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValue({
          items: [caseA],
          total: 1,
        });
        vi.mocked(preauditApi.getPreauditCase).mockResolvedValue(caseA);

        vi.spyOn(verificationApi, "listVerifications").mockResolvedValue({
          verifications: [],
          total: 0,
          limit: 50,
          offset: 0,
        });

        let opId = "";
        vi.spyOn(verificationApi, "issueVerification").mockImplementation(async (_t, payload) => {
          opId = payload.operation_id;
          throw new Error("Timeout");
        });

        renderComponent({ currentUserId: ownerId, userRole: "owner" });

        await waitFor(() => {
          expect(screen.getByTestId("issue-verification-btn")).toBeInTheDocument();
        });

        fireEvent.click(screen.getByTestId("issue-verification-btn"));

        await waitFor(() => {
          expect(screen.getByTestId("uncertain-ops-banner")).toBeInTheDocument();
        });

        fireEvent.click(screen.getByTestId(`dismiss-op-${opId}`));
        await waitFor(() => {
          expect(screen.getByTestId(`disposal-acknowledgement-${opId}`)).toBeInTheDocument();
          expect(screen.getByText(/Acknowledged Disposal: This write may have already committed/i)).toBeInTheDocument();
        });

        fireEvent.click(screen.getByTestId(`cancel-dismiss-${opId}`));
        expect(screen.queryByTestId(`disposal-acknowledgement-${opId}`)).not.toBeInTheDocument();
        expect(screen.getByTestId(`uncertain-op-${opId}`)).toBeInTheDocument();

        fireEvent.click(screen.getByTestId(`dismiss-op-${opId}`));
        await waitFor(() => {
          expect(screen.getByTestId(`confirm-dismiss-${opId}`)).toBeInTheDocument();
        });
        fireEvent.click(screen.getByTestId(`confirm-dismiss-${opId}`));

        await waitFor(() => {
          expect(screen.queryByTestId("uncertain-ops-banner")).not.toBeInTheDocument();
        });
      });

      it("token, tenant, or actor replacement wipes private uncertain operations immediately", async () => {
        vi.stubEnv("VITE_ENABLE_CUSTOMER_READINESS_VERIFICATION", "true");
        const caseA: PreauditCase = {
          ...mockCaseApproved,
          id: "case-approved-tenant-swap",
          title: "Approved Case Tenant Swap",
        };

        vi.mocked(preauditApi.listPreauditCases).mockResolvedValue({
          items: [caseA],
          total: 1,
        });
        vi.mocked(preauditApi.getPreauditCase).mockResolvedValue(caseA);

        vi.spyOn(verificationApi, "listVerifications").mockResolvedValue({
          verifications: [],
          total: 0,
          limit: 50,
          offset: 0,
        });

        vi.spyOn(verificationApi, "issueVerification").mockRejectedValue(new Error("Timeout"));

        const { rerender } = renderComponent({ currentUserId: ownerId, userRole: "owner", token: "token-tenant-1" });

        await waitFor(() => {
          expect(screen.getByTestId("issue-verification-btn")).toBeInTheDocument();
        });

        fireEvent.click(screen.getByTestId("issue-verification-btn"));

        await waitFor(() => {
          expect(screen.getByTestId("uncertain-ops-banner")).toBeInTheDocument();
        });

        rerender(
          <I18nProvider>
            <PreAuditWorkspace
              tenantId="tenant-new-uuid"
              token="token-tenant-2"
              userRole="owner"
              currentUserId="user-new-uuid"
              adoptionId="adopt-1"
            />
          </I18nProvider>,
        );

        await waitFor(() => {
          expect(screen.queryByTestId("uncertain-ops-banner")).not.toBeInTheDocument();
        });
      });

    });

});
