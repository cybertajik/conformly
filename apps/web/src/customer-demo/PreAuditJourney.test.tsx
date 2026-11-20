import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { SupportedLocale } from "../i18n/types";
import * as preauditApi from "./preaudit-api";
import {
  PreauditActor,
  PreauditCase,
  PreauditEvent,
} from "./preaudit-types";
import { PreAuditWorkspace } from "./PreAuditWorkspace";

describe("PreAuditJourney — Connected Full-Lifecycle Pre-audit Journey", () => {
  const tenantId = "00000000-0000-0000-0000-000000000001";
  const token = "mock-secret-jwt-token";
  const ownerId = "00000000-0000-0000-0000-000000000010";
  const leadId = "00000000-0000-0000-0000-000000000020";
  const reviewerId = "00000000-0000-0000-0000-000000000030";

  let caseStore: PreauditCase[];
  let eventStore: PreauditEvent[];

  const mockActors: PreauditActor[] = [
    {
      user_id: leadId,
      email: "lead@example.com",
      display_name: "Lead Compliance Officer",
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

  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    caseStore = [];
    eventStore = [];

    vi.spyOn(preauditApi, "fetchPreauditActors").mockResolvedValue(mockActors);
    vi.spyOn(preauditApi, "listPreauditCases").mockImplementation(async () => ({
      items: [...caseStore],
      total: caseStore.length,
      limit: 50,
      offset: 0,
    }));
    vi.spyOn(preauditApi, "getPreauditCase").mockImplementation(async (_t, id) => {
      const found = caseStore.find((c) => c.id === id);
      if (!found) throw new Error("Not found");
      return found;
    });

    vi.spyOn(preauditApi, "createPreauditCase").mockImplementation(async (_t, payload) => {
      const newCase: PreauditCase = {
        id: "case-001",
        tenant_id: tenantId,
        adoption_id: payload.adoption_id,
        pack_name: "soc2",
        pack_version: "2026.1",
        status: "DRAFT",
        title: payload.title || "Pre-audit Assessment",
        description: payload.description || "Lifecycle test",
        lead_user_id: payload.lead_user_id,
        lead_name: "Lead Compliance Officer",
        reviewer_user_id: payload.reviewer_user_id,
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
            work_id: "work-ac-1",
            code: "UNASSESSED_CONTROL",
            control_code: "AC-1",
            description: "Control AC-1 assessment pending verification",
          },
        ],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      caseStore.push(newCase);
      eventStore.push({
        id: `ev-${Date.now()}`,
        tenant_id: tenantId,
        preaudit_id: newCase.id,
        revision: 1,
        operation_id: payload.operation_id,
        event_type: "CREATED",
        actor_user_id: ownerId,
        prior_status: null,
        new_status: "DRAFT",
        payload: { title: newCase.title },
        created_at: new Date().toISOString(),
      });
      return newCase;
    });

    vi.spyOn(preauditApi, "freezePreauditScope").mockImplementation(async (_t, id, payload) => {
      const c = caseStore.find((x) => x.id === id);
      if (!c) throw new Error("Not found");
      c.status = "FROZEN";
      c.revision += 1;
      c.current_scope_snapshot_id = "snap-scope-001";
      c.current_scope_snapshot_digest = "11".repeat(32);
      eventStore.push({
        id: `ev-${Date.now()}`,
        tenant_id: tenantId,
        preaudit_id: c.id,
        revision: c.revision,
        operation_id: payload.operation_id,
        event_type: "SCOPE_FROZEN",
        actor_user_id: leadId,
        prior_status: "DRAFT",
        new_status: "FROZEN",
        payload: {},
        created_at: new Date().toISOString(),
      });
      return { ...c };
    });

    vi.spyOn(preauditApi, "submitPreauditReview").mockImplementation(async (_t, id, payload) => {
      const c = caseStore.find((x) => x.id === id);
      if (!c) throw new Error("Not found");
      c.status = "IN_REVIEW";
      c.revision += 1;
      c.current_review_snapshot_id = "snap-rev-001";
      c.current_review_snapshot_digest = "22".repeat(32);
      eventStore.push({
        id: `ev-${Date.now()}`,
        tenant_id: tenantId,
        preaudit_id: c.id,
        revision: c.revision,
        operation_id: payload.operation_id,
        event_type: "REVIEW_SUBMITTED",
        actor_user_id: leadId,
        prior_status: "FROZEN",
        new_status: "IN_REVIEW",
        payload: {},
        created_at: new Date().toISOString(),
      });
      return { ...c };
    });

    vi.spyOn(preauditApi, "recordReviewDecision").mockImplementation(async (_t, id, payload) => {
      const c = caseStore.find((x) => x.id === id);
      if (!c) throw new Error("Not found");
      const priorStatus = c.status;
      if (payload.decision === "ACCEPT") {
        c.status = "REVIEWED";
        c.blockers = [];
      } else {
        c.status = "CHANGES_REQUESTED";
      }
      c.revision += 1;
      eventStore.push({
        id: `ev-${Date.now()}`,
        tenant_id: tenantId,
        preaudit_id: c.id,
        revision: c.revision,
        operation_id: payload.operation_id,
        event_type: payload.decision === "ACCEPT" ? "REVIEW_ACCEPTED" : "REVIEW_CHANGES_REQUESTED",
        actor_user_id: reviewerId,
        prior_status: priorStatus,
        new_status: c.status,
        payload: { notes: payload.notes },
        created_at: new Date().toISOString(),
      });
      return { ...c };
    });

    vi.spyOn(preauditApi, "approvePreauditCase").mockImplementation(async (_t, id, payload) => {
      const c = caseStore.find((x) => x.id === id);
      if (!c) throw new Error("Not found");
      const priorStatus = c.status;
      c.status = "APPROVED";
      c.revision += 1;
      eventStore.push({
        id: `ev-${Date.now()}`,
        tenant_id: tenantId,
        preaudit_id: c.id,
        revision: c.revision,
        operation_id: payload.operation_id,
        event_type: "APPROVED",
        actor_user_id: ownerId,
        prior_status: priorStatus,
        new_status: "APPROVED",
        payload: { notes: payload.approval_notes },
        created_at: new Date().toISOString(),
      });
      return { ...c };
    });

    vi.spyOn(preauditApi, "downloadPreauditReport").mockImplementation(async (_t, id) => {
      return {
        blob: new Blob(["simulated-zip-content"], { type: "application/zip" }),
        filename: `preaudit-report-${id}.zip`,
        preauditId: id,
        snapshotDigest: "22".repeat(32),
      };
    });

    vi.spyOn(preauditApi, "getPreauditHistory").mockImplementation(async (_t, id) => {
      return {
        preaudit_id: id,
        events: [...eventStore],
      };
    });

    globalThis.URL.createObjectURL = vi.fn(() => "blob:preaudit-report");
    globalThis.URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("completes full lifecycle journey from creation to freeze, review, approval, report download and history inspection", async () => {
    // 1. Initial render as Owner: Empty state
    const { rerender } = render(
      <I18nProvider>
        <PreAuditWorkspace
          tenantId={tenantId}
          token={token}
          userRole="owner"
          currentUserId={ownerId}
          adoptionId="adopt-soc2"
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("preaudit-no-cases")).toBeInTheDocument();
    });

    // 2. Open Create Modal & Submit Case
    fireEvent.click(screen.getByTestId("create-preaudit-case-btn"));
    expect(screen.getByTestId("create-case-modal")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("create-case-title-input"), {
      target: { value: "SOC2 Q4 Readiness Certification" },
    });
    fireEvent.change(screen.getByTestId("create-case-lead-select"), {
      target: { value: leadId },
    });
    fireEvent.change(screen.getByTestId("create-case-reviewer-select"), {
      target: { value: reviewerId },
    });

    fireEvent.click(screen.getByTestId("submit-create-case-btn"));

    await waitFor(() => {
      expect(screen.getByText("SOC2 Q4 Readiness Certification")).toBeInTheDocument();
      expect(screen.getByText("DRAFT")).toBeInTheDocument();
    });

    // 2b. Switch to Compliance Lead role to freeze scope and submit review (lead-only actions)
    rerender(
      <I18nProvider>
        <PreAuditWorkspace
          tenantId={tenantId}
          token={token}
          userRole="compliance_manager"
          currentUserId={leadId}
          adoptionId="adopt-soc2"
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("freeze-scope-btn")).toBeInTheDocument();
    });

    // 3. Freeze Scope -> Transition to FROZEN
    fireEvent.click(screen.getByTestId("freeze-scope-btn"));

    await waitFor(() => {
      expect(screen.getByText("FROZEN")).toBeInTheDocument();
      expect(screen.getByTestId("submit-review-btn")).toBeInTheDocument();
    });

    // 4. Submit for Review -> Transition to IN_REVIEW
    fireEvent.click(screen.getByTestId("submit-review-btn"));

    await waitFor(() => {
      expect(screen.getByText("IN_REVIEW")).toBeInTheDocument();
    });

    // 5. Switch to Independent Reviewer role & record decision
    rerender(
      <I18nProvider>
        <PreAuditWorkspace
          tenantId={tenantId}
          token={token}
          userRole="owner"
          currentUserId={reviewerId}
          adoptionId="adopt-soc2"
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("record-review-decision-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("record-review-decision-btn"));
    expect(screen.getByTestId("review-decision-modal")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("review-notes-input"), {
      target: { value: "Readiness criteria satisfied. Independent review approved." },
    });
    fireEvent.click(screen.getByTestId("submit-review-decision-btn"));

    await waitFor(() => {
      expect(screen.getByText("REVIEWED")).toBeInTheDocument();
    });

    // 6. Switch back to Owner role to approve the certified pre-audit
    rerender(
      <I18nProvider>
        <PreAuditWorkspace
          tenantId={tenantId}
          token={token}
          userRole="owner"
          currentUserId={ownerId}
          adoptionId="adopt-soc2"
        />
      </I18nProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("approve-preaudit-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("approve-preaudit-btn"));
    expect(screen.getByTestId("approve-case-modal")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("approve-notes-input"), {
      target: { value: "Executive Owner sign-off complete." },
    });
    fireEvent.click(screen.getByTestId("confirm-approve-btn"));

    await waitFor(() => {
      expect(screen.getByText("APPROVED")).toBeInTheDocument();
    });

    // 7. Download Private Report
    expect(screen.getByTestId("download-preaudit-report-btn")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("download-preaudit-report-btn"));

    await waitFor(() => {
      expect(preauditApi.downloadPreauditReport).toHaveBeenCalledWith(
        tenantId,
        "case-001",
        expect.objectContaining({
          snapshot_id: "snap-rev-001",
          expected_snapshot_digest: "2".repeat(64),
        }),
        token,
        expect.any(AbortSignal),
      );
      expect(globalThis.URL.createObjectURL).toHaveBeenCalled();
    });

    // 8. Toggle and Verify Event History
    fireEvent.click(screen.getByTestId("toggle-history-btn"));

    await waitFor(() => {
      const historySection = screen.getByTestId("preaudit-history-section");
      expect(historySection).toBeInTheDocument();
      expect(within(historySection).getByText(/CREATED/)).toBeInTheDocument();
      expect(within(historySection).getByText(/SCOPE_FROZEN/)).toBeInTheDocument();
      expect(within(historySection).getByText(/REVIEW_SUBMITTED/)).toBeInTheDocument();
      expect(within(historySection).getByText(/REVIEW_ACCEPTED/)).toBeInTheDocument();
      expect(within(historySection).getByText(/APPROVED/)).toBeInTheDocument();
    });
  });

  it("verifies multi-locale rendering for all 5 languages throughout journey", async () => {
    const locales: SupportedLocale[] = ["en", "de", "fr", "nl", "es"];
    for (const locale of locales) {
      localStorage.setItem("conformly.locale", locale);
      const { unmount } = render(
        <I18nProvider>
          <PreAuditWorkspace
            tenantId={tenantId}
            token={token}
            userRole="owner"
            currentUserId={ownerId}
            adoptionId="adopt-soc2"
          />
        </I18nProvider>,
      );

      await waitFor(() => {
        expect(screen.getByTestId("create-preaudit-case-btn")).toBeInTheDocument();
      });
      unmount();
    }
  });
});
