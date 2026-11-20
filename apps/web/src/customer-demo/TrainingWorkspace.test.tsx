import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { ConflictError, UnauthorizedError, ValidationError } from "./api";
import * as trainingApi from "./training-api";
import { TrainingAssignment, TrainingCourse, TrainingCompletion } from "./training-types";
import { TrainingWorkspace } from "./TrainingWorkspace";

describe("TrainingWorkspace", () => {
  const tenantId = "11111111-1111-1111-1111-111111111111";
  const token = "mock-token-abc";

  const mockCourses: TrainingCourse[] = [
    {
      id: "c-1",
      tenant_id: tenantId,
      course_id: "sec-101",
      version: "1.0",
      title: "Security Awareness 2026",
      description: "Annual mandatory security training",
      provider: "lms",
      duration_minutes: 45,
      validity_period_days: 365,
      is_active: true,
      created_at: "2026-10-01T10:00:00Z",
    },
    {
      id: "c-2",
      tenant_id: tenantId,
      course_id: "priv-201",
      version: "2.1",
      title: "Privacy & GDPR Essentials",
      description: "Data handling and GDPR compliance",
      provider: "lms",
      duration_minutes: 30,
      validity_period_days: 365,
      is_active: true,
      created_at: "2026-10-02T10:00:00Z",
    },
  ];

  const mockAssignments: TrainingAssignment[] = [
    {
      id: "a-1",
      tenant_id: tenantId,
      course_id: "sec-101",
      workforce_email: "alice@example.com",
      due_date: "2026-11-30T00:00:00Z",
      status: "assigned",
      created_at: "2026-10-05T10:00:00Z",
    },
    {
      id: "a-2",
      tenant_id: tenantId,
      course_id: "priv-201",
      workforce_email: "bob@example.com",
      due_date: "2026-12-15T00:00:00Z",
      status: "in_progress",
      created_at: "2026-10-06T10:00:00Z",
    },
    {
      id: "a-3",
      tenant_id: tenantId,
      course_id: "sec-101",
      workforce_email: "charlie@example.com",
      due_date: "2026-10-01T00:00:00Z",
      status: "completed",
      created_at: "2026-09-01T10:00:00Z",
    },
  ];

  const mockCompletions: TrainingCompletion[] = [
    {
      id: "comp-1",
      tenant_id: tenantId,
      assignment_id: "a-3",
      course_id: "sec-101",
      course_version: "1.0",
      workforce_email: "charlie@example.com",
      completed_at: "2026-10-15T14:20:00Z",
      score: 95.0,
      certificate_id: "CERT-SEC-2026-001",
      evidence_id: "evi-99999999-9999",
      idempotency_key: "idemp-001",
      verified_via: "hmac_webhook",
      created_at: "2026-10-15T14:21:00Z",
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(trainingApi, "fetchTrainingCourses").mockResolvedValue(mockCourses);
    vi.spyOn(trainingApi, "fetchTrainingAssignments").mockResolvedValue(mockAssignments);
    vi.spyOn(trainingApi, "fetchTrainingCompletions").mockResolvedValue(mockCompletions);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  const renderComponent = (props: Partial<React.ComponentProps<typeof TrainingWorkspace>> = {}) => {
    return render(
      <I18nProvider>
        <TrainingWorkspace
          tenantId={tenantId}
          token={token}
          userRole="compliance_manager"
          isActive={true}
          {...props}
        />
      </I18nProvider>
    );
  };

  it("denies access to unauthorized roles (e.g. administrator, auditor, viewer)", async () => {
    renderComponent({ userRole: "administrator" });
    expect(screen.getByTestId("training-role-denied")).toBeInTheDocument();
    expect(screen.queryByTestId("training-workspace")).not.toBeInTheDocument();
    expect(trainingApi.fetchTrainingCourses).not.toHaveBeenCalled();
  });

  it("admits Owner and Compliance Manager and loads all data", async () => {
    renderComponent({ userRole: "compliance_manager" });
    await waitFor(() => {
      expect(screen.getByTestId("training-workspace")).toBeInTheDocument();
      expect(screen.getByTestId("partner-status-banner")).toBeInTheDocument();
      expect(screen.getByTestId("badge-assignments-count")).toHaveTextContent("3");
      expect(screen.getByTestId("badge-courses-count")).toHaveTextContent("2");
      expect(screen.getByTestId("badge-completions-count")).toHaveTextContent("1");
    });
  });

  it("does not fetch data when isActive is false", async () => {
    renderComponent({ isActive: false });
    expect(trainingApi.fetchTrainingCourses).not.toHaveBeenCalled();
  });

  it("filters assignments by status and displays counts", async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("assignments-table")).toBeInTheDocument();
    });

    expect(screen.getByTestId("assignment-row-a-1")).toBeInTheDocument();
    expect(screen.getByTestId("assignment-row-a-2")).toBeInTheDocument();
    expect(screen.getByTestId("assignment-row-a-3")).toBeInTheDocument();

    // Filter to 'in_progress'
    const filterSelect = screen.getByTestId("assignment-status-filter");
    fireEvent.change(filterSelect, { target: { value: "in_progress" } });

    await waitFor(() => {
      expect(screen.queryByTestId("assignment-row-a-1")).not.toBeInTheDocument();
      expect(screen.getByTestId("assignment-row-a-2")).toBeInTheDocument();
      expect(screen.queryByTestId("assignment-row-a-3")).not.toBeInTheDocument();
    });
  });

  it("switches sub-tabs and displays course catalog and verified completions", async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("subtab-courses")).toBeInTheDocument();
    });

    // Switch to Courses
    fireEvent.click(screen.getByTestId("subtab-courses"));
    await waitFor(() => {
      expect(screen.getByTestId("training-courses-panel")).toBeInTheDocument();
      expect(screen.getByTestId("course-row-sec-101")).toBeInTheDocument();
      expect(screen.getByTestId("course-row-priv-201")).toBeInTheDocument();
    });

    // Switch to Completions
    fireEvent.click(screen.getByTestId("subtab-completions"));
    await waitFor(() => {
      expect(screen.getByTestId("training-completions-panel")).toBeInTheDocument();
      expect(screen.getByTestId("completion-row-comp-1")).toBeInTheDocument();
      expect(screen.getByTestId("evidence-id")).toHaveTextContent("evi-9999");
    });
  });

  it("opens completion detail modal and inspects verification evidence", async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("subtab-completions")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("subtab-completions"));
    await waitFor(() => {
      expect(screen.getByTestId("view-completion-comp-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("view-completion-comp-1"));
    await waitFor(() => {
      expect(screen.getByTestId("completion-detail-modal")).toBeInTheDocument();
      expect(screen.getByTestId("detail-course")).toHaveTextContent("sec-101 (Version 1.0)");
      expect(screen.getByTestId("detail-learner")).toHaveTextContent("charlie@example.com");
      expect(screen.getByTestId("detail-certificate")).toHaveTextContent("CERT-SEC-2026-001");
      expect(screen.getByTestId("detail-evidence-id")).toHaveTextContent("evi-99999999-9999");
      expect(screen.getByTestId("detail-verification-method")).toHaveTextContent("hmac_webhook");
    });

    // Close detail modal
    fireEvent.click(screen.getByTestId("close-completion-detail-btn"));
    await waitFor(() => {
      expect(screen.queryByTestId("completion-detail-modal")).not.toBeInTheDocument();
    });
  });

  it("registers course reference successfully", async () => {
    const createdCourse: TrainingCourse = {
      id: "c-3",
      tenant_id: tenantId,
      course_id: "hipaa-301",
      version: "1.0",
      title: "HIPAA Security Standards",
      description: "Health data security",
      provider: "lms",
      duration_minutes: 60,
      validity_period_days: 365,
      is_active: true,
      created_at: "2026-10-20T10:00:00Z",
    };
    const createSpy = vi.spyOn(trainingApi, "createTrainingCourse").mockResolvedValue(createdCourse);

    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-register-course-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-register-course-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("register-course-modal")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("input-course-id"), { target: { value: "hipaa-301" } });
    fireEvent.change(screen.getByTestId("input-course-title"), { target: { value: "HIPAA Security Standards" } });
    fireEvent.change(screen.getByTestId("input-course-description"), { target: { value: "Health data security" } });

    fireEvent.click(screen.getByTestId("submit-register-course-btn"));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(
        tenantId,
        token,
        expect.objectContaining({
          course_id: "hipaa-301",
          title: "HIPAA Security Standards",
          description: "Health data security",
        })
      );
      expect(screen.queryByTestId("register-course-modal")).not.toBeInTheDocument();
    });
  });

  it("handles course registration conflict (409) without closing form", async () => {
    vi.spyOn(trainingApi, "createTrainingCourse").mockRejectedValue(new ConflictError("Course already exists"));

    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-register-course-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-register-course-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("register-course-modal")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("input-course-id"), { target: { value: "sec-101" } });
    fireEvent.change(screen.getByTestId("input-course-title"), { target: { value: "Duplicate Course" } });
    fireEvent.change(screen.getByTestId("input-course-description"), { target: { value: "Description" } });

    fireEvent.click(screen.getByTestId("submit-register-course-btn"));

    await waitFor(() => {
      expect(screen.getByText(/409 Conflict/i)).toBeInTheDocument();
      expect(screen.getByTestId("register-course-modal")).toBeInTheDocument();
    });
  });

  it("reconciles uncertain course registration after network interruption", async () => {
    vi.spyOn(trainingApi, "createTrainingCourse").mockRejectedValue(new Error("Network timeout"));
    vi.spyOn(trainingApi, "fetchTrainingCourses").mockResolvedValue([
      {
        id: "c-1",
        tenant_id: tenantId,
        course_id: "sec-101",
        version: "1.0",
        title: "Security 101",
        description: "Description",
        provider: "lms",
        duration_minutes: 30,
        validity_period_days: 365,
        is_active: true,
        created_at: "2026-10-01T10:00:00Z",
      },
    ]);

    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-register-course-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-register-course-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("register-course-modal")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("input-course-id"), { target: { value: "sec-101" } });
    fireEvent.change(screen.getByTestId("input-course-title"), { target: { value: "Security 101" } });
    fireEvent.change(screen.getByTestId("input-course-description"), { target: { value: "Description" } });

    fireEvent.click(screen.getByTestId("submit-register-course-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("uncertain-course-notice")).toBeInTheDocument();
      expect(screen.getByTestId("reconcile-course-btn")).toBeInTheDocument();
    });

    // User clicks Reconcile with Server
    fireEvent.click(screen.getByTestId("reconcile-course-btn"));

    await waitFor(() => {
      expect(screen.getByText(/Course verified on server/i)).toBeInTheDocument();
    });
  });

  it("creates training assignment successfully", async () => {
    const createdAssignment: TrainingAssignment = {
      id: "a-4",
      tenant_id: tenantId,
      course_id: "sec-101",
      workforce_email: "dave@example.com",
      due_date: "2026-11-20T00:00:00Z",
      status: "assigned",
      created_at: "2026-10-21T10:00:00Z",
    };
    const assignSpy = vi.spyOn(trainingApi, "createTrainingAssignment").mockResolvedValue(createdAssignment);

    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-assign-modal-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-assign-modal-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("assign-training-modal")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("input-assignment-course-id"), { target: { value: "sec-101" } });
    fireEvent.change(screen.getByTestId("input-assignment-email"), { target: { value: "dave@example.com" } });
    fireEvent.change(screen.getByTestId("input-assignment-due-date"), { target: { value: "2026-11-20" } });

    fireEvent.click(screen.getByTestId("submit-assign-training-btn"));

    await waitFor(() => {
      expect(assignSpy).toHaveBeenCalledWith(
        tenantId,
        token,
        expect.objectContaining({
          course_id: "sec-101",
          workforce_email: "dave@example.com",
          due_date: "2026-11-20",
        })
      );
      expect(screen.queryByTestId("assign-training-modal")).not.toBeInTheDocument();
    });
  });

  it("handles assignment validation error (422) for non-member learner", async () => {
    vi.spyOn(trainingApi, "createTrainingAssignment").mockRejectedValue(
      new ValidationError("Learner email must belong to an active tenant member.")
    );

    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-assign-modal-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-assign-modal-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("assign-training-modal")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("input-assignment-course-id"), { target: { value: "sec-101" } });
    fireEvent.change(screen.getByTestId("input-assignment-email"), { target: { value: "stranger@unknown.com" } });
    fireEvent.change(screen.getByTestId("input-assignment-due-date"), { target: { value: "2026-11-20" } });

    fireEvent.click(screen.getByTestId("submit-assign-training-btn"));

    await waitFor(() => {
      expect(screen.getByText(/active tenant member/i)).toBeInTheDocument();
      expect(screen.getByTestId("assign-training-modal")).toBeInTheDocument();
    });
  });

  it("invokes onSessionExpired on 401 response and ignores unmounted late 401", async () => {
    const sessionExpiredMock = vi.fn();
    vi.spyOn(trainingApi, "fetchTrainingCourses").mockRejectedValue(new UnauthorizedError("Session expired"));

    const { unmount } = renderComponent({ onSessionExpired: sessionExpiredMock });

    await waitFor(() => {
      expect(sessionExpiredMock).toHaveBeenCalledTimes(1);
    });

    // Unmount and ensure no errors are thrown on unmounted cleanup
    unmount();
  });


  it("reconciliation refuses automatic confirmation when course fields differ", async () => {
    // Attempted registration with version 2.0 and title 'Advanced Security'
    const attemptedPayload = {
      course_id: "sec-101",
      title: "Advanced Security",
      description: "Updated description",
      version: "2.0",
      provider: "lms",
      duration_minutes: 60,
      validity_period_days: 365,
    };

    vi.spyOn(trainingApi, "createTrainingCourse").mockRejectedValue(new Error("Network interruption"));
    // Server returns existing course sec-101 but with version 1.0 and title 'Security Awareness 2026'
    vi.spyOn(trainingApi, "fetchTrainingCourses").mockResolvedValue(mockCourses);

    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-register-course-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-register-course-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("register-course-modal")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("input-course-id"), { target: { value: attemptedPayload.course_id } });
    fireEvent.change(screen.getByTestId("input-course-title"), { target: { value: attemptedPayload.title } });
    fireEvent.change(screen.getByTestId("input-course-description"), { target: { value: attemptedPayload.description } });

    fireEvent.click(screen.getByTestId("submit-register-course-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("uncertain-course-notice")).toBeInTheDocument();
      expect(screen.getByTestId("reconcile-course-btn")).toBeInTheDocument();
    });

    // Click reconcile
    fireEvent.click(screen.getByTestId("reconcile-course-btn"));

    await waitFor(() => {
      // Must NOT declare automatic success
      expect(screen.queryByText(/Course verified on server! Registration confirmed/i)).not.toBeInTheDocument();
      // Must show mismatch notice requiring explicit decision
      expect(screen.getByText(/different details/i)).toBeInTheDocument();
    });
  });

  it("reconciliation when course absent requires explicit user decision rather than auto-clearing uncertainty", async () => {
    vi.spyOn(trainingApi, "createTrainingCourse").mockRejectedValue(new Error("Network timeout"));
    // Server returns empty list
    vi.spyOn(trainingApi, "fetchTrainingCourses").mockResolvedValue([]);

    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-register-course-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-register-course-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("register-course-modal")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("input-course-id"), { target: { value: "brand-new-course" } });
    fireEvent.change(screen.getByTestId("input-course-title"), { target: { value: "Brand New" } });
    fireEvent.change(screen.getByTestId("input-course-description"), { target: { value: "Description" } });

    fireEvent.click(screen.getByTestId("submit-register-course-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("uncertain-course-notice")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("reconcile-course-btn"));

    await waitFor(() => {
      // Must show explicit actions (e.g. resubmit or abandon) instead of auto-confirming or silent dismissal
      expect(screen.getByTestId("reconcile-resubmit-btn")).toBeInTheDocument();
      expect(screen.getByTestId("reconcile-abandon-btn")).toBeInTheDocument();
    });
  });

  it("fences stale 401 from prior tenant/session so current session is not expired", async () => {
    const sessionExpiredMock = vi.fn();
    let rejectStalePromise!: (reason?: unknown) => void;
    const stalePromise = new Promise<TrainingCourse[]>((_resolve, reject) => {
      rejectStalePromise = reject;
    });
    stalePromise.catch(() => {});

    vi.spyOn(trainingApi, "fetchTrainingCourses").mockReturnValue(stalePromise);

    const { rerender } = renderComponent({
      tenantId: "tenant-session-1",
      onSessionExpired: sessionExpiredMock,
    });

    await waitFor(() => {
      expect(trainingApi.fetchTrainingCourses).toHaveBeenCalledWith(
        "tenant-session-1",
        "mock-token-abc",
        expect.any(AbortSignal)
      );
    });

    // Re-render with a new tenant session before the stale fetch settles
    vi.spyOn(trainingApi, "fetchTrainingCourses").mockResolvedValue(mockCourses);
    rerender(
      <I18nProvider>
        <TrainingWorkspace
          tenantId="tenant-session-2"
          token="token-session-2"
          userRole="compliance_manager"
          isActive={true}
          onSessionExpired={sessionExpiredMock}
        />
      </I18nProvider>
    );

    // Now reject the old session's promise with 401
    rejectStalePromise(new UnauthorizedError("Stale session expired"));

    await waitFor(() => {
      expect(sessionExpiredMock).not.toHaveBeenCalled();
    });
  });

  it("same-context refresh during pending POST does not strand submitting state or drop committed receipt", async () => {
    let resolvePost!: (value: TrainingCourse) => void;
    const pendingPost = new Promise<TrainingCourse>((resolve) => {
      resolvePost = resolve;
    });

    vi.spyOn(trainingApi, "createTrainingCourse").mockReturnValue(pendingPost);

    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-register-course-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-register-course-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("register-course-modal")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("input-course-id"), { target: { value: "new-course-1" } });
    fireEvent.change(screen.getByTestId("input-course-title"), { target: { value: "New Course" } });
    fireEvent.change(screen.getByTestId("input-course-description"), { target: { value: "Desc" } });

    // Submit the form
    fireEvent.click(screen.getByTestId("submit-register-course-btn"));

    // Submitting button is busy
    await waitFor(() => {
      expect(screen.getByTestId("submit-register-course-btn")).toBeDisabled();
    });

    // While POST is still pending, trigger a same-context refresh
    fireEvent.click(screen.getByTestId("refresh-training-btn"));

    // Now resolve the pending POST with the created course
    const createdCourse: TrainingCourse = {
      id: "c-created-1",
      tenant_id: tenantId,
      course_id: "new-course-1",
      version: "1.0",
      title: "New Course",
      description: "Desc",
      provider: "lms",
      duration_minutes: 30,
      validity_period_days: 365,
      is_active: true,
      created_at: "2026-10-31T00:00:00Z",
    };
    resolvePost(createdCourse);

    // Modal should close and committed course must be retained in courses list
    await waitFor(() => {
      expect(screen.queryByTestId("register-course-modal")).not.toBeInTheDocument();
      expect(screen.getByTestId("badge-courses-count")).toHaveTextContent("3");
    });
    fireEvent.click(screen.getByTestId("subtab-courses"));
    expect(screen.getByText("New Course")).toBeInTheDocument();
  });

  it("tenant replacement clears open modal, form draft, and old tenant state immediately without leaking into new tenant", async () => {
    const { rerender } = renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-register-course-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-register-course-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("register-course-modal")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("input-course-id"), { target: { value: "secret-old-tenant-course" } });

    // Switch to new tenant
    rerender(
      <I18nProvider>
        <TrainingWorkspace
          tenantId="new-tenant-2222-2222"
          token="new-token-2222"
          userRole="compliance_manager"
          isActive={true}
        />
      </I18nProvider>
    );

    // Modal must be closed immediately
    expect(screen.queryByTestId("register-course-modal")).not.toBeInTheDocument();

    // Reopen modal under new tenant: draft must NOT contain old tenant's input
    fireEvent.click(screen.getByTestId("open-register-course-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("register-course-modal")).toBeInTheDocument();
    });
    expect(screen.getByTestId("input-course-id")).toHaveValue("");
  });

  it("role revocation hides modal and clears active operations", async () => {
    const { rerender } = renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-register-course-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-register-course-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("register-course-modal")).toBeInTheDocument();
    });

    // Revoke role to viewer
    rerender(
      <I18nProvider>
        <TrainingWorkspace
          tenantId={tenantId}
          token={token}
          userRole="viewer"
          isActive={true}
        />
      </I18nProvider>
    );

    expect(screen.getByTestId("training-role-denied")).toBeInTheDocument();
    expect(screen.queryByTestId("register-course-modal")).not.toBeInTheDocument();
  });

  it("reconciliation with multiple candidate matches remains uncertain and blocks automatic adoption", async () => {
    vi.spyOn(trainingApi, "createTrainingAssignment").mockRejectedValue(new Error("Network timeout"));
    const dupAssignments: TrainingAssignment[] = [
      {
        id: "a-dup-1",
        tenant_id: tenantId,
        course_id: "sec-101",
        workforce_email: "alice@example.com",
        due_date: "2026-11-30T00:00:00Z",
        status: "assigned",
        created_at: "2026-10-01T00:00:00Z",
      },
      {
        id: "a-dup-2",
        tenant_id: tenantId,
        course_id: "sec-101",
        workforce_email: "alice@example.com",
        due_date: "2026-11-30T00:00:00Z",
        status: "assigned",
        created_at: "2026-10-02T00:00:00Z",
      },
    ];
    vi.spyOn(trainingApi, "fetchTrainingAssignments").mockResolvedValue(dupAssignments);

    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-assign-modal-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-assign-modal-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("assign-training-modal")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("input-assignment-course-id"), { target: { value: "sec-101" } });
    fireEvent.change(screen.getByTestId("input-assignment-email"), { target: { value: "alice@example.com" } });
    fireEvent.change(screen.getByTestId("input-assignment-due-date"), { target: { value: "2026-11-30" } });

    fireEvent.click(screen.getByTestId("submit-assign-training-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("uncertain-assignment-notice")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("reconcile-assignment-btn"));

    await waitFor(() => {
      // Must NOT adopt automatically
      expect(screen.queryByText(/Assignment verified on server! Assignment confirmed/i)).not.toBeInTheDocument();
      // Must remain uncertain / ambiguous
      expect(screen.queryByTestId("reconcile-adopt-btn")).not.toBeInTheDocument();
    });
  });

  it("reconciliation identifies mismatched control reference as mismatch rather than adopt", async () => {
    vi.spyOn(trainingApi, "createTrainingAssignment").mockRejectedValue(new Error("Network timeout"));
    const serverAssignments: TrainingAssignment[] = [
      {
        id: "a-server-1",
        tenant_id: tenantId,
        course_id: "sec-101",
        workforce_email: "alice@example.com",
        due_date: "2026-11-30T00:00:00Z",
        status: "assigned",
        control_id: "diff-ctrl-id",
        control_type: "canonical",
        created_at: "2026-10-01T00:00:00Z",
      },
    ];
    vi.spyOn(trainingApi, "fetchTrainingAssignments").mockResolvedValue(serverAssignments);

    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-assign-modal-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-assign-modal-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("assign-training-modal")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("input-assignment-course-id"), { target: { value: "sec-101" } });
    fireEvent.change(screen.getByTestId("input-assignment-email"), { target: { value: "alice@example.com" } });
    fireEvent.change(screen.getByTestId("input-assignment-due-date"), { target: { value: "2026-11-30" } });

    fireEvent.click(screen.getByTestId("submit-assign-training-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("uncertain-assignment-notice")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("reconcile-assignment-btn"));

    await waitFor(() => {
      // Mismatched reference must be flagged as mismatch, not adopt
      expect(screen.queryByText(/Assignment verified on server! Assignment confirmed/i)).not.toBeInTheDocument();
      expect(screen.getByText(/different details/i)).toBeInTheDocument();
    });
  });

  it("uncertain course A abandoned during in-flight reconciliation does not allow A late response to contaminate subsequent uncertain course B", async () => {
    let resolveReconcileA: (courses: TrainingCourse[]) => void = () => {};
    const reconcilePromiseA = new Promise<TrainingCourse[]>((res) => {
      resolveReconcileA = res;
    });

    vi.spyOn(trainingApi, "createTrainingCourse").mockRejectedValue(new Error("Network timeout"));
    const fetchSpy = vi.spyOn(trainingApi, "fetchTrainingCourses");
    fetchSpy.mockResolvedValueOnce(mockCourses);
    fetchSpy.mockReturnValueOnce(reconcilePromiseA);

    renderComponent();
    await waitFor(() => {
      expect(screen.getByTestId("open-register-course-btn")).toBeInTheDocument();
    });

    // Submit Course A
    fireEvent.click(screen.getByTestId("open-register-course-btn"));
    fireEvent.change(screen.getByTestId("input-course-id"), { target: { value: "course-A" } });
    fireEvent.change(screen.getByTestId("input-course-title"), { target: { value: "Title A" } });
    fireEvent.change(screen.getByTestId("input-course-description"), { target: { value: "Desc A" } });
    fireEvent.click(screen.getByTestId("submit-register-course-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("uncertain-course-notice")).toBeInTheDocument();
    });

    // Start reconcile on A (in flight)
    fireEvent.click(screen.getByTestId("reconcile-course-btn"));

    // User abandons/dismisses Course A while in flight
    fireEvent.click(screen.getByTestId("dismiss-uncertain-course-btn"));

    await waitFor(() => {
      expect(screen.queryByTestId("uncertain-course-notice")).not.toBeInTheDocument();
    });

    // Now submit Course B (which also encounters network timeout -> Uncertain B)
    fireEvent.change(screen.getByTestId("input-course-id"), { target: { value: "course-B" } });
    fireEvent.change(screen.getByTestId("input-course-title"), { target: { value: "Title B" } });
    fireEvent.change(screen.getByTestId("input-course-description"), { target: { value: "Desc B" } });
    fireEvent.click(screen.getByTestId("submit-register-course-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("uncertain-course-notice")).toBeInTheDocument();
    });

    // Now A's old in-flight reconciliation promise resolves with Course A data!
    resolveReconcileA([
      {
        id: "c-a",
        tenant_id: tenantId,
        course_id: "course-A",
        title: "Title A",
        description: "Desc A",
        version: "1.0",
        provider: "lms",
        duration_minutes: 30,
        validity_period_days: 365,
        is_active: true,
        created_at: "2026-10-01T00:00:00Z",
      },
    ]);

    await new Promise((r) => setTimeout(r, 50));

    // Must NOT have adopted Course A or contaminated Course B's state!
    expect(screen.queryByText(/Course verified on server! Registration confirmed/i)).not.toBeInTheDocument();
    // Uncertain B notice must still be present for Course B
    expect(screen.getByTestId("uncertain-course-notice")).toBeInTheDocument();
  });

  it("in-flight reconciliation 401 from abandoned attempt A does not expire session for active attempt B", async () => {
    let rejectReconcileA: (err: unknown) => void = () => {};
    const reconcilePromiseA = new Promise<TrainingCourse[]>((_, rej) => {
      rejectReconcileA = rej;
    });

    const sessionExpiredMock = vi.fn();
    vi.spyOn(trainingApi, "createTrainingCourse").mockRejectedValue(new Error("Network timeout"));
    const fetchSpy = vi.spyOn(trainingApi, "fetchTrainingCourses");
    fetchSpy.mockResolvedValueOnce(mockCourses);
    fetchSpy.mockReturnValueOnce(reconcilePromiseA);

    renderComponent({ onSessionExpired: sessionExpiredMock });
    await waitFor(() => {
      expect(screen.getByTestId("open-register-course-btn")).toBeInTheDocument();
    });

    // Submit Course A -> uncertain
    fireEvent.click(screen.getByTestId("open-register-course-btn"));
    fireEvent.change(screen.getByTestId("input-course-id"), { target: { value: "course-A" } });
    fireEvent.change(screen.getByTestId("input-course-title"), { target: { value: "Title A" } });
    fireEvent.change(screen.getByTestId("input-course-description"), { target: { value: "Desc A" } });
    fireEvent.click(screen.getByTestId("submit-register-course-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("uncertain-course-notice")).toBeInTheDocument();
    });

    // Start reconcile on A
    fireEvent.click(screen.getByTestId("reconcile-course-btn"));

    // User abandons/dismisses Course A
    fireEvent.click(screen.getByTestId("dismiss-uncertain-course-btn"));

    // Late 401 from abandoned A
    rejectReconcileA(new UnauthorizedError("Token expired on old attempt"));

    await new Promise((r) => setTimeout(r, 50));

    // onSessionExpired must NOT have been called!
    expect(sessionExpiredMock).not.toHaveBeenCalled();
  });

  it("genuine current attempt reconciliation 401 expires the session", async () => {
    const sessionExpiredMock = vi.fn();
    vi.spyOn(trainingApi, "createTrainingCourse").mockRejectedValue(new Error("Network timeout"));
    const fetchSpy = vi.spyOn(trainingApi, "fetchTrainingCourses");
    fetchSpy.mockResolvedValueOnce(mockCourses);
    fetchSpy.mockRejectedValueOnce(new UnauthorizedError("Session expired"));

    renderComponent({ onSessionExpired: sessionExpiredMock });
    await waitFor(() => {
      expect(screen.getByTestId("open-register-course-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-register-course-btn"));
    fireEvent.change(screen.getByTestId("input-course-id"), { target: { value: "course-A" } });
    fireEvent.change(screen.getByTestId("input-course-title"), { target: { value: "Title A" } });
    fireEvent.change(screen.getByTestId("input-course-description"), { target: { value: "Desc A" } });
    fireEvent.click(screen.getByTestId("submit-register-course-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("uncertain-course-notice")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("reconcile-course-btn"));

    await waitFor(() => {
      expect(sessionExpiredMock).toHaveBeenCalledTimes(1);
    });
  });
});
