import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { ForbiddenError } from "./api";
import { JobStatusPanel } from "./JobStatusPanel";
import * as taskApi from "./task-api";
import { FailedJobsResponse, OutboxMessageResponse } from "./task-types";

describe("JobStatusPanel Component", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  const dummyFailedResponse: FailedJobsResponse = {
    total_failed: 2,
    recent_failures: [
      {
        job_id: "job-101",
        job_name: "compliance_policy_reminder",
        error_code: "SMTP_CONNECT_TIMEOUT",
        attempts: 3,
        failed_at: "2026-10-29T08:30:00Z",
      },
      {
        job_id: "job-102",
        job_name: "risk_assessment_scheduler",
        error_code: "LOCK_TIMEOUT",
        attempts: 2,
        failed_at: "2026-10-29T09:15:00Z",
      },
    ],
  };

  const dummyOutboxResponse: OutboxMessageResponse[] = [
    {
      id: "msg-1",
      tenant_id: "ten-1",
      kind: "policy_review_reminder",
      message_type: "policy_review_reminder",
      state: "delivered",
      attempts: 1,
      available_at: "2026-10-29T08:00:00Z",
      last_attempt_at: "2026-10-29T08:00:00Z",
      created_at: "2026-10-29T07:55:00Z",
      updated_at: "2026-10-29T08:00:00Z",
    },
    {
      id: "msg-2",
      tenant_id: "ten-1",
      kind: "task_due_alert",
      message_type: "task_due_alert",
      state: "pending",
      attempts: 0,
      available_at: "2026-10-29T12:00:00Z",
      last_attempt_at: null,
      created_at: "2026-10-29T10:00:00Z",
      updated_at: "2026-10-29T10:00:00Z",
    },
  ];

  it("renders failed jobs count, recent failures, and outbox messages for authorized manager", async () => {
    vi.spyOn(taskApi, "fetchFailedJobs").mockResolvedValue(dummyFailedResponse);
    vi.spyOn(taskApi, "fetchOutboxMessages").mockResolvedValue(dummyOutboxResponse);

    render(
      <I18nProvider>
        <JobStatusPanel
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("job-status-panel")).toBeInTheDocument();
      expect(screen.getByTestId("metric-failed-jobs")).toHaveTextContent("2");
      expect(screen.getByTestId("metric-outbox-total")).toHaveTextContent("2");
    });

    // Check failed jobs details
    expect(screen.getByText("compliance_policy_reminder")).toBeInTheDocument();
    expect(screen.getByText("SMTP_CONNECT_TIMEOUT")).toBeInTheDocument();

    // Check outbox messages
    expect(screen.getByText("policy_review_reminder")).toBeInTheDocument();
    expect(screen.getByTestId("outbox-state-msg-1")).toHaveTextContent(/delivered/i);
    expect(screen.getByTestId("outbox-state-msg-2")).toHaveTextContent(/pending/i);
  });

  it("denies access to unauthorized roles honestly without crashing", () => {
    render(
      <I18nProvider>
        <JobStatusPanel
          tenantId="ten-1"
          token="token-abc"
          userRole="employee"
        />
      </I18nProvider>
    );

    expect(screen.getByTestId("job-status-denied")).toBeInTheDocument();
    expect(screen.queryByTestId("job-status-panel")).not.toBeInTheDocument();
  });

  it("handles 403 Forbidden API response independently and shows denied notice", async () => {
    vi.spyOn(taskApi, "fetchFailedJobs").mockRejectedValue(
      new ForbiddenError("Role unauthorized to access job status")
    );
    vi.spyOn(taskApi, "fetchOutboxMessages").mockResolvedValue(dummyOutboxResponse);

    render(
      <I18nProvider>
        <JobStatusPanel
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("job-status-denied")).toBeInTheDocument();
      expect(screen.queryByTestId("job-status-panel")).not.toBeInTheDocument();
    });
  });

  it("filters outbox messages by state and updates pagination offset", async () => {
    vi.spyOn(taskApi, "fetchFailedJobs").mockResolvedValue({ total_failed: 0, recent_failures: [] });
    const outboxSpy = vi.spyOn(taskApi, "fetchOutboxMessages").mockResolvedValue(dummyOutboxResponse);

    render(
      <I18nProvider>
        <JobStatusPanel
          tenantId="ten-1"
          token="token-abc"
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("outbox-state-filter")).toBeInTheDocument();
    });

    // Change state filter to "pending"
    fireEvent.change(screen.getByTestId("outbox-state-filter"), {
      target: { value: "pending" },
    });

    await waitFor(() => {
      expect(outboxSpy).toHaveBeenCalledWith(
        "ten-1",
        "token-abc",
        expect.objectContaining({ state: "pending", offset: 0 }),
        expect.any(AbortSignal)
      );
    });
  });
  it("implements honest has-more pagination for 11+ rows and navigates across pages", async () => {
    vi.spyOn(taskApi, "fetchFailedJobs").mockResolvedValue({ total_failed: 0, recent_failures: [] });
    
    // Page 1: returns 10 items (PAGE_SIZE = 10, meaning hasMore = true)
    const page1Items: OutboxMessageResponse[] = Array.from({ length: 10 }, (_, i) => ({
      id: `msg-${i + 1}`,
      tenant_id: "ten-1",
      kind: "task_due_alert",
      message_type: "task_due_alert",
      state: "pending",
      attempts: 0,
      available_at: "2026-10-29T12:00:00Z",
      last_attempt_at: null,
      created_at: "2026-10-29T10:00:00Z",
      updated_at: "2026-10-29T10:00:00Z",
    }));

    // Page 2: returns 1 item (meaning hasMore = false)
    const page2Items: OutboxMessageResponse[] = [
      {
        id: "msg-11",
        tenant_id: "ten-1",
        kind: "task_due_alert",
        message_type: "task_due_alert",
        state: "pending",
        attempts: 0,
        available_at: "2026-10-29T12:00:00Z",
        last_attempt_at: null,
        created_at: "2026-10-29T10:00:00Z",
        updated_at: "2026-10-29T10:00:00Z",
      },
    ];

    const outboxSpy = vi.spyOn(taskApi, "fetchOutboxMessages")
      .mockResolvedValueOnce(page1Items)
      .mockResolvedValueOnce(page2Items);

    render(
      <I18nProvider>
        <JobStatusPanel
          tenantId="ten-1"
          token="token-abc"
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("job-status-panel")).toBeInTheDocument();
      // On page 1 with 10 loaded and hasMore true:
      expect(screen.getByTestId("metric-outbox-total")).toHaveTextContent("10+");
      expect(screen.getByTestId("outbox-prev-btn")).toBeDisabled();
      expect(screen.getByTestId("outbox-next-btn")).not.toBeDisabled();
    });

    // Click Next to navigate to offset 10 (Page 2)
    fireEvent.click(screen.getByTestId("outbox-next-btn"));

    await waitFor(() => {
      expect(outboxSpy).toHaveBeenCalledWith(
        "ten-1",
        "token-abc",
        expect.objectContaining({ offset: 10, limit: 10 }),
        expect.any(AbortSignal)
      );
      expect(screen.getByTestId("outbox-page-indicator")).toHaveTextContent("Page 2");
      // On page 2 with 1 item and hasMore false:
      expect(screen.getByTestId("outbox-prev-btn")).not.toBeDisabled();
      expect(screen.getByTestId("outbox-next-btn")).toBeDisabled();
    });
  });

  it("handles empty terminal page with active Previous button and disabled Next button", async () => {
    vi.spyOn(taskApi, "fetchFailedJobs").mockResolvedValue({ total_failed: 0, recent_failures: [] });
    
    // Page 1: 10 items
    const page1Items: OutboxMessageResponse[] = Array.from({ length: 10 }, (_, i) => ({
      id: `msg-${i + 1}`,
      tenant_id: "ten-1",
      kind: "task_due_alert",
      message_type: "task_due_alert",
      state: "pending",
      attempts: 0,
      available_at: "2026-10-29T12:00:00Z",
      last_attempt_at: null,
      created_at: "2026-10-29T10:00:00Z",
      updated_at: "2026-10-29T10:00:00Z",
    }));

    // Page 2: empty terminal page (0 items)
    vi.spyOn(taskApi, "fetchOutboxMessages")
      .mockResolvedValueOnce(page1Items)
      .mockResolvedValueOnce([]);

    render(
      <I18nProvider>
        <JobStatusPanel
          tenantId="ten-1"
          token="token-abc"
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("outbox-next-btn")).not.toBeDisabled();
    });

    // Advance to terminal page
    fireEvent.click(screen.getByTestId("outbox-next-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("empty-outbox-state")).toBeInTheDocument();
      expect(screen.getByTestId("outbox-prev-btn")).not.toBeDisabled();
      expect(screen.getByTestId("outbox-next-btn")).toBeDisabled();
    });
  });
});
