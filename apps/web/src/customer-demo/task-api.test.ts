import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  completeTask,
  createTask,
  fetchFailedJobs,
  fetchOutboxMessages,
  fetchTask,
  fetchTasks,
  updateTask,
} from "./task-api";
import {
  ConflictError,
  ForbiddenError,
  NotFoundError,
} from "./api";
import { ComplianceTask, OutboxMessageResponse } from "./task-types";

describe("task-api client", () => {
  const dummyTask: ComplianceTask = {
    id: "task-1",
    tenant_id: "ten-1",
    title: "Review Annual Access Logs",
    description: "Verify quarterly and annual review of IAM roles",
    due_date: "2026-11-15T12:00:00Z",
    status: "pending",
    priority: "medium",
    assignee_user_id: "user-123",
    control_type: null,
    control_id: null,
    evidence_id: null,
    policy_id: null,
    version: 1,
    completed_at: null,
    completed_by_user_id: null,
    created_at: "2026-10-29T10:00:00Z",
    updated_at: "2026-10-29T10:00:00Z",
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchTasks sends correct query parameters and validates tenant envelope", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [dummyTask],
    } as Response);

    const result = await fetchTasks("ten-1", "token-abc", {
      status: "pending",
      priority: "medium",
      limit: 50,
      offset: 10,
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/v1/tenants/ten-1/compliance/tasks?status=pending&priority=medium&limit=50&offset=10"),
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer token-abc" }),
      })
    );
    expect(result).toEqual([dummyTask]);
  });

  it("fetchTasks rejects on tenant mismatch", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [{ ...dummyTask, tenant_id: "ten-foreign" }],
    } as Response);

    await expect(fetchTasks("ten-1", "token-abc")).rejects.toThrow(/Tenant mismatch/);
  });

  it("fetchTask fetches single record by ID and validates shape", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => dummyTask,
    } as Response);

    const res = await fetchTask("ten-1", "token-abc", "task-1");
    expect(res.id).toBe("task-1");
  });

  it("fetchTask rejects on 404 with NotFoundError", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Task task-99 not found" }),
    } as Response);

    await expect(fetchTask("ten-1", "token-abc", "task-99")).rejects.toBeInstanceOf(NotFoundError);
  });

  it("createTask sends payload and validates returned tenant", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => dummyTask,
    } as Response);

    const res = await createTask("ten-1", "token-abc", {
      title: "Review Annual Access Logs",
      description: "Verify quarterly and annual review of IAM roles",
      due_date: "2026-11-15T12:00:00Z",
      priority: "medium",
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/v1/tenants/ten-1/compliance/tasks"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          title: "Review Annual Access Logs",
          description: "Verify quarterly and annual review of IAM roles",
          due_date: "2026-11-15T12:00:00Z",
          priority: "medium",
        }),
      })
    );
    expect(res).toEqual(dummyTask);
  });

  it("updateTask handles 409 conflict appropriately", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: "Task version mismatch" }),
    } as Response);

    await expect(
      updateTask("ten-1", "token-abc", "task-1", {
        expected_version: 1,
        title: "Updated Title",
      })
    ).rejects.toBeInstanceOf(ConflictError);
  });

  it("completeTask sends versioned action request", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        ...dummyTask,
        status: "completed",
        version: 2,
        completed_at: "2026-10-29T11:00:00Z",
        completed_by_user_id: "user-alice",
      }),
    } as Response);

    const res = await completeTask("ten-1", "token-abc", "task-1", 1);
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/v1/tenants/ten-1/compliance/tasks/task-1/complete"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ expected_version: 1 }),
      })
    );
    expect(res.status).toBe("completed");
    expect(res.version).toBe(2);
  });

  it("fetchFailedJobs fetches summary and handles 403 forbidden", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: "Forbidden: background jobs visibility requires Owner" }),
    } as Response);

    await expect(fetchFailedJobs("ten-1", "token-abc")).rejects.toBeInstanceOf(ForbiddenError);
  });

  it("fetchOutboxMessages parses outbox items", async () => {
    const dummyOutbox: OutboxMessageResponse = {
      id: "msg-1",
      tenant_id: "ten-1",
      kind: "task.reminder",
      idempotency_key: "task-rem-1",
      state: "delivered",
      attempts: 1,
      available_at: "2026-10-29T10:00:00Z",
      delivered_at: "2026-10-29T10:01:00Z",
      error_code: null,
      created_at: "2026-10-29T10:00:00Z",
      updated_at: "2026-10-29T10:01:00Z",
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [dummyOutbox],
    } as Response);

    const res = await fetchOutboxMessages("ten-1", "token-abc", { state: "delivered" });
    expect(res).toEqual([dummyOutbox]);
  });
});
