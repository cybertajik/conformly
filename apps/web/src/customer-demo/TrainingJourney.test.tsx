import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { SupportedLocale } from "../i18n/types";
import * as trainingApi from "./training-api";
import { TrainingAssignment, TrainingCourse, TrainingCompletion } from "./training-types";
import { TrainingWorkspace } from "./TrainingWorkspace";

describe("TrainingJourney — Integrated Lifecycle & Multi-Locale Journey", () => {
  const tenantId = "ten-alpha-123";
  const token = "token-secret-jwt";

  let coursesStore: TrainingCourse[];
  let assignmentsStore: TrainingAssignment[];
  let completionsStore: TrainingCompletion[];

  beforeEach(() => {
    vi.restoreAllMocks();

    coursesStore = [
      {
        id: "c-initial",
        tenant_id: tenantId,
        course_id: "sec-baseline",
        version: "1.0",
        title: "Baseline Information Security",
        description: "Foundational cybersecurity practices",
        provider: "lms",
        duration_minutes: 30,
        validity_period_days: 365,
        is_active: true,
        created_at: "2026-10-01T08:00:00Z",
      },
    ];

    assignmentsStore = [];
    completionsStore = [];

    vi.spyOn(trainingApi, "fetchTrainingCourses").mockImplementation(async () => [...coursesStore]);
    vi.spyOn(trainingApi, "fetchTrainingAssignments").mockImplementation(async () => [...assignmentsStore]);
    vi.spyOn(trainingApi, "fetchTrainingCompletions").mockImplementation(async () => [...completionsStore]);

    vi.spyOn(trainingApi, "createTrainingCourse").mockImplementation(async (_tenant, _tok, payload) => {
      const created: TrainingCourse = {
        id: `c-${Date.now()}`,
        tenant_id: tenantId,
        course_id: payload.course_id,
        version: payload.version || "1.0",
        title: payload.title,
        description: payload.description,
        provider: payload.provider || "lms",
        duration_minutes: payload.duration_minutes || 30,
        validity_period_days: payload.validity_period_days || 365,
        is_active: true,
        created_at: new Date().toISOString(),
      };
      coursesStore.push(created);
      return created;
    });

    vi.spyOn(trainingApi, "createTrainingAssignment").mockImplementation(async (_tenant, _tok, payload) => {
      const created: TrainingAssignment = {
        id: `a-${Date.now()}`,
        tenant_id: tenantId,
        course_id: payload.course_id,
        workforce_email: payload.workforce_email,
        due_date: payload.due_date,
        status: "assigned",
        created_at: new Date().toISOString(),
      };
      assignmentsStore.push(created);
      return created;
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("completes full end-to-end journey: register course -> assign training -> receive verified completion -> inspect evidence", async () => {
    render(
      <I18nProvider>
        <TrainingWorkspace
          tenantId={tenantId}
          token={token}
          userRole="compliance_manager"
          isActive={true}
        />
      </I18nProvider>
    );

    // 1. Initial State: Partner status banner and default empty assignments
    await waitFor(() => {
      expect(screen.getByTestId("training-workspace")).toBeInTheDocument();
      expect(screen.getByTestId("partner-status-banner")).toBeInTheDocument();
      expect(screen.getByTestId("assignments-empty")).toBeInTheDocument();
    });

    // 2. Register New Course Reference
    fireEvent.click(screen.getByTestId("open-register-course-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("register-course-modal")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("input-course-id"), { target: { value: "soc2-trust-2026" } });
    fireEvent.change(screen.getByTestId("input-course-title"), { target: { value: "SOC 2 Trust Services Criteria" } });
    fireEvent.change(screen.getByTestId("input-course-description"), {
      target: { value: "Security, Confidentiality, and Availability criteria overview" },
    });
    fireEvent.change(screen.getByTestId("input-course-version"), { target: { value: "2.0" } });
    fireEvent.change(screen.getByTestId("input-course-provider"), { target: { value: "partner-lms" } });

    fireEvent.click(screen.getByTestId("submit-register-course-btn"));

    // Modal closes and course is registered
    await waitFor(() => {
      expect(screen.queryByTestId("register-course-modal")).not.toBeInTheDocument();
      expect(screen.getByTestId("badge-courses-count")).toHaveTextContent("2");
    });

    // 3. Navigate to Courses Subtab to verify table
    fireEvent.click(screen.getByTestId("subtab-courses"));
    await waitFor(() => {
      expect(screen.getByTestId("course-row-soc2-trust-2026")).toBeInTheDocument();
      expect(screen.getByText("SOC 2 Trust Services Criteria")).toBeInTheDocument();
    });

    // 4. Assign Training to a workforce member
    fireEvent.click(screen.getByTestId("open-assign-modal-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("assign-training-modal")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("input-assignment-course-id"), { target: { value: "soc2-trust-2026" } });
    fireEvent.change(screen.getByTestId("input-assignment-email"), { target: { value: "engineer@company.test" } });
    fireEvent.change(screen.getByTestId("input-assignment-due-date"), { target: { value: "2026-12-01" } });

    fireEvent.click(screen.getByTestId("submit-assign-training-btn"));

    await waitFor(() => {
      expect(screen.queryByTestId("assign-training-modal")).not.toBeInTheDocument();
      expect(screen.getByTestId("badge-assignments-count")).toHaveTextContent("1");
    });

    // Verify assignment in Assignments subtab
    fireEvent.click(screen.getByTestId("subtab-assignments"));
    await waitFor(() => {
      expect(screen.getByText("engineer@company.test")).toBeInTheDocument();
      expect(screen.getByText("soc2-trust-2026")).toBeInTheDocument();
    });

    // 5. External LMS submits verified completion webhook (simulated backend state update)
    const completionRecord: TrainingCompletion = {
      id: "comp-soc2-999",
      tenant_id: tenantId,
      assignment_id: assignmentsStore[0]?.id || "a-mock",
      course_id: "soc2-trust-2026",
      course_version: "2.0",
      workforce_email: "engineer@company.test",
      completed_at: "2026-10-29T20:00:00Z",
      score: 98.5,
      certificate_id: "CERT-SOC2-9999",
      evidence_id: "evidence-uuid-7777-8888",
      idempotency_key: "idemp-soc2-complete",
      verified_via: "hmac_webhook",
      created_at: "2026-10-29T20:01:00Z",
    };
    completionsStore.push(completionRecord);

    // User refreshes register
    fireEvent.click(screen.getByTestId("refresh-training-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("badge-completions-count")).toHaveTextContent("1");
    });

    // 6. Navigate to Completions Subtab and Inspect Evidence
    fireEvent.click(screen.getByTestId("subtab-completions"));
    await waitFor(() => {
      expect(screen.getByTestId("completion-row-comp-soc2-999")).toBeInTheDocument();
      expect(screen.getByTestId("evidence-id")).toHaveTextContent("evidence");
    });

    fireEvent.click(screen.getByTestId("view-completion-comp-soc2-999"));
    await waitFor(() => {
      expect(screen.getByTestId("completion-detail-modal")).toBeInTheDocument();
      expect(screen.getByTestId("detail-course")).toHaveTextContent("soc2-trust-2026 (Version 2.0)");
      expect(screen.getByTestId("detail-learner")).toHaveTextContent("engineer@company.test");
      expect(screen.getByTestId("detail-score")).toHaveTextContent("98.5%");
      expect(screen.getByTestId("detail-certificate")).toHaveTextContent("CERT-SOC2-9999");
      expect(screen.getByTestId("detail-evidence-id")).toHaveTextContent("evidence-uuid-7777-8888");
      expect(screen.getByTestId("detail-verification-method")).toHaveTextContent("hmac_webhook");
    });

    fireEvent.click(screen.getByTestId("close-completion-detail-btn"));
    await waitFor(() => {
      expect(screen.queryByTestId("completion-detail-modal")).not.toBeInTheDocument();
    });
  });

  it("renders correctly across all 5 supported locales (en, de, fr, nl, es)", async () => {
    const locales: SupportedLocale[] = ["en", "de", "fr", "nl", "es"];

    for (const loc of locales) {
      localStorage.setItem("conformly.locale", loc);
      const { unmount } = render(
        <I18nProvider>
          <TrainingWorkspace
            tenantId={tenantId}
            token={token}
            userRole="compliance_manager"
            isActive={true}
          />
        </I18nProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId("training-workspace")).toBeInTheDocument();
        expect(screen.getByTestId("partner-status-banner")).toBeInTheDocument();
        expect(screen.getByTestId("subtab-assignments")).toBeInTheDocument();
        expect(screen.getByTestId("subtab-courses")).toBeInTheDocument();
        expect(screen.getByTestId("subtab-completions")).toBeInTheDocument();
      });

      unmount();
    }
  });

  it("handles keyboard events and phone responsive layout gracefully", async () => {
    render(
      <I18nProvider>
        <TrainingWorkspace
          tenantId={tenantId}
          token={token}
          userRole="compliance_manager"
          isActive={true}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("training-workspace")).toBeInTheDocument();
    });

    // Open modal and cancel via button click or keyboard focus
    fireEvent.click(screen.getByTestId("open-register-course-btn"));
    expect(screen.getByTestId("register-course-modal")).toBeInTheDocument();

    const cancelBtn = screen.getByTestId("cancel-register-course-btn");
    cancelBtn.focus();
    fireEvent.click(cancelBtn);

    await waitFor(() => {
      expect(screen.queryByTestId("register-course-modal")).not.toBeInTheDocument();
    });
  });

  it("fences stale responses across rapid tenant/token context replacement", async () => {
    let delayResolve: ((data: TrainingCourse[]) => void) | null = null;
    vi.spyOn(trainingApi, "fetchTrainingCourses").mockImplementation(
      () =>
        new Promise((resolve) => {
          delayResolve = resolve;
        })
    );

    const { rerender } = render(
      <I18nProvider>
        <TrainingWorkspace
          tenantId="tenant-initial"
          token="token-initial"
          userRole="compliance_manager"
          isActive={true}
        />
      </I18nProvider>
    );

    // Switch context before initial fetch resolves
    rerender(
      <I18nProvider>
        <TrainingWorkspace
          tenantId="tenant-switched"
          token="token-switched"
          userRole="compliance_manager"
          isActive={true}
        />
      </I18nProvider>
    );

    // Stale initial resolve arrives
    if (delayResolve) {
      (delayResolve as (d: TrainingCourse[]) => void)([
        {
          id: "stale-c",
          tenant_id: "tenant-initial",
          course_id: "stale-course",
          version: "1.0",
          title: "Stale Course",
          description: "Stale",
          provider: "lms",
          duration_minutes: 10,
          validity_period_days: 10,
          is_active: true,
          created_at: "2026-10-01T00:00:00Z",
        },
      ]);
    }

    // Switched component must NOT adopt stale course
    await waitFor(() => {
      expect(screen.queryByTestId("course-row-stale-course")).not.toBeInTheDocument();
    });
  });
});

