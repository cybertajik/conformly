import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { PreauditCaseDetail } from "./preaudit-types";
import { ReadinessVerificationPanel } from "./ReadinessVerificationPanel";
import * as verificationApi from "./verification-api";
import {
  VerificationDetail,
  VerificationListResponse,
  VerificationListSummary,
  VerificationProjection,
} from "./verification-types";

describe("ReadinessVerificationPanel", () => {
  const tenantId = "11111111-1111-1111-1111-111111111111";
  const caseId = "22222222-2222-2222-2222-222222222222";
  const caseIdB = "22222222-2222-2222-2222-222222222223";
  const snapshotId = "33333333-3333-3333-3333-333333333333";
  const verificationId = "44444444-4444-4444-4444-444444444444";
  const token = "mock-bearer-token-xyz";

  const approvedCase: PreauditCaseDetail = {
    id: caseId,
    tenant_id: tenantId,
    adoption_id: "adopt-1",
    pack_name: "ISO 27001",
    pack_version: "2022",
    lead_user_id: "lead-1",
    reviewer_user_id: "rev-1",
    lead_name: "Alice Lead",
    reviewer_name: "Bob Reviewer",
    status: "APPROVED",
    revision: 4,
    title: "Q4 Compliance Review",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    current_review_snapshot_id: snapshotId,
    current_review_snapshot_digest: "a".repeat(64),
    is_scope_current: true,
    is_review_current: true,
    blockers: [],
  };

  const approvedCaseB: PreauditCaseDetail = {
    ...approvedCase,
    id: caseIdB,
    title: "SOC 2 Compliance Review B",
  };

  const mockActiveVerification: VerificationDetail = {
    id: verificationId,
    preaudit_id: caseId,
    snapshot_id: snapshotId,
    status: "ACTIVE",
    effective_status: "ACTIVE",
    effective_reason: null,
    revision: 1,
    issued_at: "2026-01-01T00:00:00Z",
    valid_through: "2027-01-01T00:00:00Z",
    digest: "d".repeat(64),
    synthetic_marker: "PRIVATE SYNTHETIC INTERNAL TEST RESULT",
    test_qualification: "PRIVATE SYNTHETIC INTERNAL TEST RESULT - NOT AN ACCREDITED CERTIFICATION",
    limitations: ["Internal assessment only", "No production telemetry"],
    issuer_user_id: "owner-1",
    reviewer_user_id: "rev-1",
    approver_user_id: "owner-1",
  };

  beforeEach(() => {
    vi.stubEnv("VITE_ENABLE_CUSTOMER_READINESS_VERIFICATION", "true");
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders nothing when feature flag is disabled", () => {
    vi.stubEnv("VITE_ENABLE_CUSTOMER_READINESS_VERIFICATION", "false");
    const { container } = render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows issue verification prompt when case is APPROVED and no verification exists", async () => {
    vi.spyOn(verificationApi, "listVerifications").mockResolvedValueOnce({
      verifications: [],
      total: 0,
      limit: 50,
      offset: 0,
    });

    render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("readiness-verification-panel")).toBeInTheDocument();
    });

    expect(screen.getByTestId("verification-disclaimer")).toHaveTextContent(
      "PRIVATE SYNTHETIC INTERNAL TEST RESULT - NOT AN ACCREDITED CERTIFICATION",
    );
    expect(screen.getByTestId("issue-verification-btn")).toBeInTheDocument();
  });

  it("calls issueVerification when Owner clicks issue button with valid token", async () => {
    vi.spyOn(verificationApi, "listVerifications").mockResolvedValue({
      verifications: [],
      total: 0,
      limit: 50,
      offset: 0,
    });
    const issueSpy = vi.spyOn(verificationApi, "issueVerification").mockResolvedValueOnce(mockActiveVerification);

    render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("issue-verification-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("issue-verification-btn"));

    await waitFor(() => {
      expect(issueSpy).toHaveBeenCalledWith(
        tenantId,
        expect.objectContaining({
          preaudit_id: caseId,
          snapshot_id: snapshotId,
          expected_case_revision: 4,
        }),
        token,
      );
    });
  });

  it("renders active verification details, status badges, and limitations", async () => {
    vi.spyOn(verificationApi, "listVerifications").mockResolvedValueOnce({
      verifications: [
        {
          id: verificationId,
          preaudit_id: caseId,
          status: "ACTIVE",
          effective_status: "ACTIVE",
          revision: 1,
          issued_at: "2026-01-01T00:00:00Z",
          valid_through: "2027-01-01T00:00:00Z",
          synthetic_marker: "PRIVATE SYNTHETIC INTERNAL TEST RESULT",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
    vi.spyOn(verificationApi, "getVerification").mockResolvedValueOnce(mockActiveVerification);
    vi.spyOn(verificationApi, "getVerificationHistory").mockResolvedValueOnce({
      verification_id: verificationId,
      events: [
        {
          id: "ev-1",
          sequence: 1,
          revision: 1,
          event_type: "ISSUED",
          created_at: "2026-01-01T00:00:00Z",
          actor_user_id: "owner-1",
        },
      ],
    });

    render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("verification-details-card")).toBeInTheDocument();
    });

    expect(screen.getByTestId("verification-status-badge")).toHaveTextContent("ACTIVE");
    expect(screen.getByTestId("verification-effective-badge")).toHaveTextContent("ACTIVE");
    expect(screen.getByText("Internal assessment only")).toBeInTheDocument();
    expect(screen.getByTestId("verification-history-timeline")).toBeInTheDocument();
    expect(screen.getByText("ISSUED")).toBeInTheDocument();
  });

  it("handles suspend action confirmation dialog flow", async () => {
    vi.spyOn(verificationApi, "listVerifications").mockResolvedValue({
      verifications: [
        {
          id: verificationId,
          preaudit_id: caseId,
          status: "ACTIVE",
          effective_status: "ACTIVE",
          revision: 1,
          issued_at: "2026-01-01T00:00:00Z",
          valid_through: "2027-01-01T00:00:00Z",
          synthetic_marker: "PRIVATE SYNTHETIC INTERNAL TEST RESULT",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
    vi.spyOn(verificationApi, "getVerification").mockResolvedValue(mockActiveVerification);
    vi.spyOn(verificationApi, "getVerificationHistory").mockResolvedValue({
      verification_id: verificationId,
      events: [],
    });
    const suspendSpy = vi.spyOn(verificationApi, "suspendVerification").mockResolvedValueOnce({
      ...mockActiveVerification,
      status: "SUSPENDED",
      effective_status: "SUSPENDED",
      revision: 2,
    });

    render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("suspend-verification-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("suspend-verification-btn"));

    const textarea = screen.getByTestId("verification-dialog-textarea");
    fireEvent.change(textarea, { target: { value: "Security audit requires evidence re-evaluation" } });

    fireEvent.click(screen.getByTestId("verification-dialog-confirm-btn"));

    await waitFor(() => {
      expect(suspendSpy).toHaveBeenCalledWith(
        tenantId,
        verificationId,
        expect.objectContaining({
          expected_revision: 1,
          reason: "Security audit requires evidence re-evaluation",
        }),
        token,
      );
    });
  });

  it("toggles and displays allowlisted private projection preview", async () => {
    vi.spyOn(verificationApi, "listVerifications").mockResolvedValue({
      verifications: [
        {
          id: verificationId,
          preaudit_id: caseId,
          status: "ACTIVE",
          effective_status: "ACTIVE",
          revision: 1,
          issued_at: "2026-01-01T00:00:00Z",
          valid_through: "2027-01-01T00:00:00Z",
          synthetic_marker: "PRIVATE SYNTHETIC INTERNAL TEST RESULT",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
    vi.spyOn(verificationApi, "getVerification").mockResolvedValue(mockActiveVerification);
    vi.spyOn(verificationApi, "getVerificationHistory").mockResolvedValue({
      verification_id: verificationId,
      events: [],
    });

    const mockProjection: VerificationProjection = {
      verification_id: verificationId,
      synthetic_marker: "PRIVATE SYNTHETIC INTERNAL TEST RESULT",
      test_qualification: "PRIVATE SYNTHETIC INTERNAL TEST RESULT - NOT AN ACCREDITED CERTIFICATION",
      framework_display_name: "SOC 2 Type II",
      framework_version: "2025",
      organization_display_name: "Acme Compliance Demo",
      scope_summary: { controls_count: 42 },
      controls_count: 42,
      issued_at: "2026-01-01T00:00:00Z",
      valid_through: "2027-01-01T00:00:00Z",
      status: "ACTIVE",
      effective_status: "ACTIVE",
      limitations: [],
    };
    vi.spyOn(verificationApi, "getVerificationProjection").mockResolvedValueOnce(mockProjection);

    render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("toggle-projection-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("toggle-projection-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("verification-projection-section")).toBeInTheDocument();
    });

    expect(screen.getByText("SOC 2 Type II (v2025)")).toBeInTheDocument();
    expect(screen.getByText("Acme Compliance Demo")).toBeInTheDocument();
  });

  it("parent-panel-client: verifies Authorization: Bearer <token> in real fetch request", async () => {
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        verifications: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
    });
    vi.stubGlobal("fetch", fetchSpy);

    render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token="secret-authenticated-token-123"
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining(`/v2/tenants/${tenantId}/customer-demo/readiness-verifications`),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer secret-authenticated-token-123",
          }),
        }),
      );
    });
  });

  it("handles stale vs current 401: current 401 calls onSessionExpired, stale does not", async () => {
    const onSessionExpired = vi.fn();
    const unauthorizedError = { status: 401, message: "Session expired" };

    // Part A: Current 401 triggers onSessionExpired
    vi.spyOn(verificationApi, "listVerifications").mockRejectedValueOnce(unauthorizedError);

    render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
          onSessionExpired={onSessionExpired}
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(onSessionExpired).toHaveBeenCalledTimes(1);
    });

    // Part B: Stale 401 from previous lifetime should NOT call onSessionExpired
    cleanup();
    onSessionExpired.mockClear();

    let rejectStale: (err: unknown) => void = () => {};
    const deferredPromise = new Promise<VerificationListResponse>((_, reject) => {
      rejectStale = reject;
    });

    vi.spyOn(verificationApi, "listVerifications").mockImplementation(async (_t, _tok, _s, _l, _o, filterId) => {
      if (filterId === caseId) {
        return deferredPromise;
      }
      return { verifications: [], total: 0, limit: 50, offset: 0 };
    });

    const { rerender } = render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
          onSessionExpired={onSessionExpired}
        />
      </I18nProvider>,
    );

    // Wait a tick for Case A's effect to run and call listVerifications
    await new Promise((r) => setTimeout(r, 20));

    // Switch to Case B before Case A's request rejects
    rerender(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCaseB}
          isOwner={true}
          token={token}
          onSessionExpired={onSessionExpired}
        />
      </I18nProvider>,
    );

    // Wait for Case B to settle
    await new Promise((r) => setTimeout(r, 20));

    // Now reject Case A's stale promise with 401
    rejectStale(unauthorizedError);

    await new Promise((r) => setTimeout(r, 50));

    // Stale 401 MUST NOT have called onSessionExpired
    expect(onSessionExpired).not.toHaveBeenCalled();
  });

  it("handles A -> B -> A switching with deferred responses without installing retired data", async () => {
    let resolveCaseA1: ((val: VerificationListResponse) => void) | null = null;
    const promiseA1 = new Promise<VerificationListResponse>((res) => {
      resolveCaseA1 = res;
    });

    vi.spyOn(verificationApi, "getVerification").mockResolvedValue(mockActiveVerification);
    vi.spyOn(verificationApi, "getVerificationHistory").mockResolvedValue({
      verification_id: verificationId,
      events: [],
    });

    vi.spyOn(verificationApi, "listVerifications").mockImplementation(
      async (_t, _tok, _sig, _lim, _off, filterId) => {
        if (filterId === caseIdB) {
          return { verifications: [], total: 0, limit: 50, offset: 0 };
        }
        if (filterId === caseId && !resolveCaseA1) {
          return {
            verifications: [
              {
                id: verificationId,
                preaudit_id: caseId,
                status: "ACTIVE",
                effective_status: "ACTIVE",
                revision: 1,
                issued_at: "2026-01-01T00:00:00Z",
                valid_through: "2027-01-01T00:00:00Z",
                synthetic_marker: "PRIVATE SYNTHETIC INTERNAL TEST RESULT",
              },
            ],
            total: 1,
            limit: 50,
            offset: 0,
          };
        }
        return promiseA1;
      },
    );

    const { rerender } = render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    // Switch to Case B
    rerender(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCaseB}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    // Now resolve Case A1 with verification data
    if (resolveCaseA1) {
      (resolveCaseA1 as (val: VerificationListResponse) => void)({
        verifications: [
          {
            id: verificationId,
            preaudit_id: caseId,
            status: "ACTIVE",
            effective_status: "ACTIVE",
            revision: 1,
            issued_at: "2026-01-01T00:00:00Z",
            valid_through: "2027-01-01T00:00:00Z",
            synthetic_marker: "PRIVATE SYNTHETIC INTERNAL TEST RESULT",
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      });
    }

    await waitFor(() => {
      // Must NOT render Case A's verification card while on Case B
      expect(screen.queryByTestId("verification-details-card")).not.toBeInTheDocument();
    });

    // Switch back to Case A (A -> B -> A)
    resolveCaseA1 = null; // Allow next call to return real verifications
    rerender(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("verification-details-card")).toBeInTheDocument();
    });
  });

  it("recovers uncertain operations with exact retry retaining operationId, and supports explicit dismissal", async () => {
    let verificationsList: VerificationListSummary[] = [];
    vi.spyOn(verificationApi, "listVerifications").mockImplementation(async () => ({
      verifications: verificationsList,
      total: verificationsList.length,
      limit: 50,
      offset: 0,
    }));
    vi.spyOn(verificationApi, "getVerification").mockResolvedValue(mockActiveVerification);
    vi.spyOn(verificationApi, "getVerificationHistory").mockResolvedValue({
      verification_id: verificationId,
      events: [],
    });

    // First issue attempt fails with 500 network error
    const issueSpy = vi
      .spyOn(verificationApi, "issueVerification")
      .mockRejectedValueOnce(new Error("Network timeout / uncertain server state"));

    render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("issue-verification-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("issue-verification-btn"));

    // Uncertain operations banner must appear
    await waitFor(() => {
      expect(screen.getByTestId("uncertain-ops-banner")).toBeInTheDocument();
    });

    expect(issueSpy).toHaveBeenCalledTimes(1);
    const originalOpId = issueSpy.mock.calls[0][1].operation_id;
    expect(originalOpId).toBeDefined();

    // Now retry the operation
    issueSpy.mockImplementationOnce(async () => {
      verificationsList = [
        {
          id: verificationId,
          preaudit_id: caseId,
          status: "ACTIVE",
          effective_status: "ACTIVE",
          revision: 1,
          issued_at: "2026-01-01T00:00:00Z",
          valid_through: "2027-01-01T00:00:00Z",
          synthetic_marker: "PRIVATE SYNTHETIC INTERNAL TEST RESULT",
        },
      ];
      return mockActiveVerification;
    });

    const retryBtn = screen.getByTestId(`retry-op-${originalOpId}`);
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(issueSpy).toHaveBeenCalledTimes(2);
      // Retry call MUST preserve the original operation_id
      expect(issueSpy.mock.calls[1][1].operation_id).toBe(originalOpId);
    });

    // Banner should be cleared after successful retry
    await waitFor(() => {
      expect(screen.queryByTestId("uncertain-ops-banner")).not.toBeInTheDocument();
    });

    // Verify card and suspend button are now present
    await waitFor(() => {
      expect(screen.getByTestId("suspend-verification-btn")).toBeInTheDocument();
    });

    // Test dismissal path
    const suspendSpy = vi
      .spyOn(verificationApi, "suspendVerification")
      .mockRejectedValueOnce(new Error("504 Gateway Timeout"));

    fireEvent.click(screen.getByTestId("suspend-verification-btn"));
    fireEvent.change(screen.getByTestId("verification-dialog-textarea"), {
      target: { value: "Test suspension failure" },
    });
    fireEvent.click(screen.getByTestId("verification-dialog-confirm-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("uncertain-ops-banner")).toBeInTheDocument();
    });

    const suspendOpId = suspendSpy.mock.calls[0][2].operation_id;
    const dismissBtn = screen.getByTestId(`dismiss-op-${suspendOpId}`);
    fireEvent.click(dismissBtn);

    await waitFor(() => {
      expect(screen.getByTestId(`disposal-acknowledgement-${suspendOpId}`)).toBeInTheDocument();
    });
    const confirmDismissBtn = screen.getByTestId(`confirm-dismiss-${suspendOpId}`);
    fireEvent.click(confirmDismissBtn);

    await waitFor(() => {
      expect(screen.queryByTestId("uncertain-ops-banner")).not.toBeInTheDocument();
    });
  });

  it("handles supersession form workflow with validation and exact payload", async () => {
    vi.spyOn(verificationApi, "listVerifications").mockResolvedValue({
      verifications: [
        {
          id: verificationId,
          preaudit_id: caseId,
          status: "ACTIVE",
          effective_status: "ACTIVE",
          revision: 1,
          issued_at: "2026-01-01T00:00:00Z",
          valid_through: "2027-01-01T00:00:00Z",
          synthetic_marker: "PRIVATE SYNTHETIC INTERNAL TEST RESULT",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
    vi.spyOn(verificationApi, "getVerification").mockResolvedValue(mockActiveVerification);
    vi.spyOn(verificationApi, "getVerificationHistory").mockResolvedValue({
      verification_id: verificationId,
      events: [],
    });

    const supersedeSpy = vi.spyOn(verificationApi, "supersedeVerification").mockResolvedValueOnce({
      ...mockActiveVerification,
      id: "new-ver-999",
      status: "ACTIVE",
      effective_status: "ACTIVE",
      revision: 1,
    });

    render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("supersede-verification-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("supersede-verification-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("verification-action-modal")).toBeInTheDocument();
    });

    // Fill in supersession form
    fireEvent.change(screen.getByTestId("supersede-case-id-input"), {
      target: { value: "new-approved-case-uuid" },
    });
    fireEvent.change(screen.getByTestId("supersede-case-rev-input"), {
      target: { value: "3" },
    });
    fireEvent.change(screen.getByTestId("supersede-snapshot-id-input"), {
      target: { value: "new-snapshot-uuid" },
    });
    fireEvent.change(screen.getByTestId("supersede-digest-input"), {
      target: { value: "e".repeat(64) },
    });
    fireEvent.change(screen.getByTestId("supersede-limitations-input"), {
      target: { value: "Limitation X, Limitation Y" },
    });
    fireEvent.change(screen.getByTestId("supersede-notes-input"), {
      target: { value: "Superseding prior audit cycle" },
    });

    fireEvent.click(screen.getByTestId("verification-dialog-confirm-btn"));

    await waitFor(() => {
      expect(supersedeSpy).toHaveBeenCalledWith(
        tenantId,
        verificationId,
        expect.objectContaining({
          expected_revision: 1,
          new_preaudit_id: "new-approved-case-uuid",
          new_expected_case_revision: 3,
          new_snapshot_id: "new-snapshot-uuid",
          new_snapshot_digest: "e".repeat(64),
          limitations: ["Limitation X", "Limitation Y"],
          notes: "Superseding prior audit cycle",
        }),
        token,
      );
    });
  });
  it("ignored-abort unmount: late resolving call or 401 does not fire onSessionExpired or callback after unmount", async () => {
    let lateResolve: (val: VerificationListResponse) => void = () => {};
    vi.spyOn(verificationApi, "listVerifications").mockImplementation(
      () =>
        new Promise((resolve) => {
          lateResolve = resolve;
        }),
    );
    const onSessionExpired = vi.fn();
    const onVerificationChange = vi.fn();

    const { unmount } = render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
          onSessionExpired={onSessionExpired}
          onVerificationChange={onVerificationChange}
        />
      </I18nProvider>,
    );

    // Unmount while listVerifications is still pending
    unmount();

    // Now resolve late response with 401 or data
    lateResolve({
      verifications: [],
      total: 0,
      limit: 50,
      offset: 0,
    });

    await new Promise((r) => setTimeout(r, 20));

    expect(onSessionExpired).not.toHaveBeenCalled();
    expect(onVerificationChange).not.toHaveBeenCalled();
  });

  it("pending action then context replacement resets busy state and controls remain usable", async () => {
    vi.spyOn(verificationApi, "listVerifications").mockResolvedValue({
      verifications: [],
      total: 0,
      limit: 50,
      offset: 0,
    });

    let pendingIssueResolve: (val: VerificationDetail) => void = () => {};
    vi.spyOn(verificationApi, "issueVerification").mockImplementation(
      () =>
        new Promise((resolve) => {
          pendingIssueResolve = resolve;
        }),
    );

    const { rerender } = render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("issue-verification-btn")).toBeInTheDocument();
    });

    // Start issue action -> actionLoading becomes true
    fireEvent.click(screen.getByTestId("issue-verification-btn"));
    expect(screen.getByTestId("issue-verification-btn")).toBeDisabled();

    // Context changes: user switches to case B
    const caseB: PreauditCaseDetail = {
      ...approvedCase,
      id: "case-b-uuid",
      title: "Case B",
    };

    rerender(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={caseB}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    // Busy state MUST be reset immediately upon context replacement; controls remain usable!
    await waitFor(() => {
      const btn = screen.getByTestId("issue-verification-btn");
      expect(btn).not.toBeDisabled();
    });

    // Resolve old operation: must NOT affect Case B
    pendingIssueResolve(mockActiveVerification);
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.getByTestId("issue-verification-btn")).not.toBeDisabled();
  });

  it("old finally does not clear a newer busy operation", async () => {
    let currentVerList: VerificationListSummary[] = [];
    vi.spyOn(verificationApi, "listVerifications").mockImplementation(async () => ({
      verifications: currentVerList,
      total: currentVerList.length,
      limit: 50,
      offset: 0,
    }));

    let oldActionReject: (err: unknown) => void = () => {};
    let newActionResolve: (val: VerificationDetail) => void = () => {};
    let callCount = 0;

    vi.spyOn(verificationApi, "issueVerification").mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return new Promise((_, reject) => {
          oldActionReject = reject;
        });
      }
      return new Promise((resolve) => {
        newActionResolve = resolve;
      });
    });

    const { rerender } = render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("issue-verification-btn")).toBeInTheDocument();
    });

    // Operation 1 starts
    fireEvent.click(screen.getByTestId("issue-verification-btn"));

    // Switch case to Case B
    const caseB: PreauditCaseDetail = {
      ...approvedCase,
      id: "case-b-uuid",
      title: "Case B",
    };
    rerender(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={caseB}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("issue-verification-btn")).not.toBeDisabled();
    });

    // Operation 2 starts on Case B -> busy state active
    fireEvent.click(screen.getByTestId("issue-verification-btn"));
    expect(screen.getByTestId("issue-verification-btn")).toBeDisabled();

    // Old Operation 1 rejects / completes its finally block now
    oldActionReject(new Error("Old op timed out"));
    await new Promise((r) => setTimeout(r, 20));

    // Operation 2 is still in progress, so button MUST STILL be disabled (not cleared by old finally!)
    expect(screen.getByTestId("issue-verification-btn")).toBeDisabled();

    // Now complete Operation 2
    const newVerB = {
      ...mockActiveVerification,
      id: "ver-case-b",
      preaudit_id: "case-b-uuid",
    };
    currentVerList = [newVerB];
    vi.spyOn(verificationApi, "getVerification").mockResolvedValue(newVerB);
    newActionResolve(newVerB);
    await waitFor(() => {
      expect(screen.queryByTestId("issue-verification-btn")).not.toBeInTheDocument();
    });
  });

  it("same-context old load arriving last is rejected by monotonic sequence ordering", async () => {
    let resolveFirstLoad: (val: VerificationListResponse) => void = () => {};
    let resolveSecondLoad: (val: VerificationListResponse) => void = () => {};
    let loadCount = 0;

    vi.spyOn(verificationApi, "listVerifications").mockImplementation(() => {
      loadCount++;
      if (loadCount === 1) {
        return new Promise((resolve) => {
          resolveFirstLoad = resolve;
        });
      }
      return new Promise((resolve) => {
        resolveSecondLoad = resolve;
      });
    });

    vi.spyOn(verificationApi, "getVerification").mockResolvedValue(mockActiveVerification);
    vi.spyOn(verificationApi, "getVerificationHistory").mockResolvedValue({
      verification_id: verificationId,
      events: [],
    });

    const { rerender } = render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    // Wait for first load to be dispatched and in flight
    await waitFor(() => {
      expect(loadCount).toBe(1);
    });

    // Trigger second load for the same case (e.g. revision change)
    rerender(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={{ ...approvedCase, revision: 2 }}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(loadCount).toBe(2);
    });

    // Second load arrives FIRST with an active verification
    resolveSecondLoad({
      verifications: [
        {
          id: verificationId,
          preaudit_id: caseId,
          status: "ACTIVE",
          effective_status: "ACTIVE",
          revision: 2,
          issued_at: "2026-01-01T00:00:00Z",
          valid_through: "2027-01-01T00:00:00Z",
          synthetic_marker: "PRIVATE SYNTHETIC INTERNAL TEST RESULT",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });

    await waitFor(() => {
      expect(screen.getByTestId("verification-details-card")).toBeInTheDocument();
    });

    // First load (which had empty results) arrives LAST
    resolveFirstLoad({
      verifications: [],
      total: 0,
      limit: 50,
      offset: 0,
    });

    await new Promise((r) => setTimeout(r, 20));

    // Stale earlier load arriving last must NOT overwrite newer active verification state!
    expect(screen.getByTestId("verification-details-card")).toBeInTheDocument();
  });

  it("tenant or token replacement clears private uncertainty preventing cross-context display or retry", async () => {
    vi.spyOn(verificationApi, "listVerifications").mockResolvedValue({
      verifications: [],
      total: 0,
      limit: 50,
      offset: 0,
    });

    // Issue fails with network timeout -> creates uncertain op
    vi.spyOn(verificationApi, "issueVerification").mockRejectedValueOnce(
      new Error("Gateway timeout - outcome uncertain"),
    );

    const { rerender } = render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId="tenant-alpha"
          preauditCase={approvedCase}
          isOwner={true}
          token="token-alpha"
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("issue-verification-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("issue-verification-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("uncertain-ops-banner")).toBeInTheDocument();
    });

    // User switches token / tenant to tenant-beta
    rerender(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId="tenant-beta"
          preauditCase={approvedCase}
          isOwner={true}
          token="token-beta"
        />
      </I18nProvider>,
    );

    // Private uncertainty from tenant-alpha MUST be cleared and never shown or retried under tenant-beta!
    await waitFor(() => {
      expect(screen.queryByTestId("uncertain-ops-banner")).not.toBeInTheDocument();
    });
  });

  it("lost response then original action click prevents generating a fresh operation ID", async () => {
    vi.spyOn(verificationApi, "listVerifications").mockResolvedValue({
      verifications: [],
      total: 0,
      limit: 50,
      offset: 0,
    });

    const issueSpy = vi
      .spyOn(verificationApi, "issueVerification")
      .mockRejectedValueOnce(new Error("504 Connection reset"));

    render(
      <I18nProvider>
        <ReadinessVerificationPanel
          tenantId={tenantId}
          preauditCase={approvedCase}
          isOwner={true}
          token={token}
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("issue-verification-btn")).toBeInTheDocument();
    });

    // Click issue button
    fireEvent.click(screen.getByTestId("issue-verification-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("uncertain-ops-banner")).toBeInTheDocument();
    });
    expect(issueSpy).toHaveBeenCalledTimes(1);

    // User clicks the original Issue button AGAIN while the earlier intent is uncertain
    fireEvent.click(screen.getByTestId("issue-verification-btn"));

    // Must NOT submit a fresh POST or generate a new operation ID!
    expect(issueSpy).toHaveBeenCalledTimes(1);
    expect(
      screen.getByText(/An issue operation is already pending\/uncertain for this case/i),
    ).toBeInTheDocument();
  });
});
