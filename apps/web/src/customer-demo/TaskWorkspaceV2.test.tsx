import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { ConflictError, UnauthorizedError } from "./api";
import * as api from "./task-api";
import { ComplianceTask } from "./task-types";
import { TaskWorkspaceV2 } from "./TaskWorkspaceV2";

describe("TaskWorkspaceV2 Component", () => {
  const dummyTask: ComplianceTask = {
    id: "task-1",
    tenant_id: "ten-1",
    title: "Quarterly Firewall Review",
    description: "Verify egress rules and policy exceptions",
    due_date: "2026-11-20T00:00:00Z",
    status: "pending",
    priority: "high",
    assignee_user_id: "user-alice",
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
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders tasks list, priority, status and filters correctly", async () => {
    const task2: ComplianceTask = {
      ...dummyTask,
      id: "task-2",
      title: "Data Backup Verification",
      status: "completed",
      priority: "low",
    };

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="owner"
          tasks={[dummyTask, task2]}
        />
      </I18nProvider>
    );

    expect(screen.getByTestId("task-workspace")).toBeInTheDocument();
    expect(screen.getByText("Quarterly Firewall Review")).toBeInTheDocument();
    expect(screen.getByText("Data Backup Verification")).toBeInTheDocument();

    // Filter by completed
    fireEvent.change(screen.getByTestId("task-status-filter"), { target: { value: "completed" } });
    expect(screen.queryByText("Quarterly Firewall Review")).not.toBeInTheDocument();
    expect(screen.getByText("Data Backup Verification")).toBeInTheDocument();

    // Filter by priority
    fireEvent.change(screen.getByTestId("task-status-filter"), { target: { value: "all" } });
    fireEvent.change(screen.getByTestId("task-priority-filter"), { target: { value: "high" } });
    expect(screen.getByText("Quarterly Firewall Review")).toBeInTheDocument();
    expect(screen.queryByText("Data Backup Verification")).not.toBeInTheDocument();
  });

  it("denies access to administrator and unauthorized roles honestly", () => {
    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="administrator"
          tasks={[dummyTask]}
        />
      </I18nProvider>
    );

    expect(screen.getByTestId("task-workspace-denied")).toBeInTheDocument();
    expect(screen.queryByTestId("tasks-table")).not.toBeInTheDocument();
  });

  it("executes lifecycle: select task -> load detail -> edit draft -> complete task", async () => {
    vi.spyOn(api, "fetchTask").mockResolvedValue(dummyTask);
    const updateSpy = vi.spyOn(api, "updateTask").mockResolvedValue({
      ...dummyTask,
      title: "Quarterly Firewall Review (Updated)",
      version: 2,
    });
    const completeSpy = vi.spyOn(api, "completeTask").mockResolvedValue({
      ...dummyTask,
      title: "Quarterly Firewall Review (Updated)",
      status: "completed",
      version: 3,
      completed_at: "2026-10-29T11:00:00Z",
    });

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          tasks={[dummyTask]}
        />
      </I18nProvider>
    );

    fireEvent.click(screen.getByTestId("task-row-task-1"));

    await waitFor(() => {
      expect(screen.getByTestId("edit-task-title")).toHaveValue("Quarterly Firewall Review");
    });

    // Edit title
    fireEvent.change(screen.getByTestId("edit-task-title"), {
      target: { value: "Quarterly Firewall Review (Updated)" },
    });
    fireEvent.click(screen.getByTestId("save-task-draft-btn"));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(
        "ten-1",
        "token-abc",
        "task-1",
        expect.objectContaining({
          expected_version: 1,
          title: "Quarterly Firewall Review (Updated)",
        })
      );
      expect(screen.getByTestId("task-action-success")).toBeInTheDocument();
    });

    // Complete task
    fireEvent.click(screen.getByTestId("complete-task-btn"));
    await waitFor(() => {
      expect(completeSpy).toHaveBeenCalledWith("ten-1", "token-abc", "task-1", 2);
    });
  });

  it("handles 409 conflict and preserves user edits on task update", async () => {
    vi.spyOn(api, "fetchTask").mockResolvedValue(dummyTask);
    vi.spyOn(api, "updateTask").mockRejectedValue(new ConflictError("Task version mismatch"));

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          tasks={[dummyTask]}
        />
      </I18nProvider>
    );

    fireEvent.click(screen.getByTestId("task-row-task-1"));

    await waitFor(() => {
      expect(screen.getByTestId("edit-task-title")).toHaveValue("Quarterly Firewall Review");
    });

    fireEvent.change(screen.getByTestId("edit-task-title"), {
      target: { value: "Concurrent Title Edit" },
    });
    fireEvent.click(screen.getByTestId("save-task-draft-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("conflict-reload-banner")).toBeInTheDocument();
      // Draft remains intact
      expect(screen.getByTestId("edit-task-title")).toHaveValue("Concurrent Title Edit");
    });
  });

  it("guards against dirty record switch and preserves draft on cancel", async () => {
    const task2: ComplianceTask = {
      ...dummyTask,
      id: "task-2",
      title: "Second Task",
    };

    vi.spyOn(api, "fetchTask")
      .mockResolvedValueOnce(dummyTask)
      .mockResolvedValueOnce(task2);

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          tasks={[dummyTask, task2]}
        />
      </I18nProvider>
    );

    fireEvent.click(screen.getByTestId("task-row-task-1"));
    await waitFor(() => {
      expect(screen.getByTestId("edit-task-title")).toHaveValue("Quarterly Firewall Review");
    });

    // Make dirty edit
    fireEvent.change(screen.getByTestId("edit-task-title"), {
      target: { value: "Dirty Unsaved Changes" },
    });

    // Try switching to task-2
    fireEvent.click(screen.getByTestId("task-row-task-2"));
    expect(screen.getByTestId("task-dirty-switch-guard")).toBeInTheDocument();

    // Cancel keep editing
    fireEvent.click(screen.getByTestId("cancel-discard-switch-btn"));
    expect(screen.queryByTestId("task-dirty-switch-guard")).not.toBeInTheDocument();
    expect(screen.getByTestId("edit-task-title")).toHaveValue("Dirty Unsaved Changes");
  });
  it("preserves exact non-midnight due_date timestamp on metadata-only edits", async () => {
    const nonMidnightTask: ComplianceTask = {
      ...dummyTask,
      id: "task-non-midnight",
      due_date: "2026-11-20T16:45:30Z",
      version: 5,
    };

    vi.spyOn(api, "fetchTask").mockResolvedValue(nonMidnightTask);
    const updateSpy = vi.spyOn(api, "updateTask").mockResolvedValue({
      ...nonMidnightTask,
      title: "Title Changed Only",
      version: 6,
    });

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          tasks={[nonMidnightTask]}
        />
      </I18nProvider>
    );

    fireEvent.click(screen.getByTestId("task-row-task-non-midnight"));

    await waitFor(() => {
      expect(screen.getByTestId("edit-task-title")).toHaveValue("Quarterly Firewall Review");
      expect(screen.getByTestId("edit-task-duedate")).toHaveValue("2026-11-20");
    });

    // Edit title only, leaving due_date input untouched
    fireEvent.change(screen.getByTestId("edit-task-title"), {
      target: { value: "Title Changed Only" },
    });
    fireEvent.click(screen.getByTestId("save-task-draft-btn"));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(
        "ten-1",
        "token-abc",
        "task-non-midnight",
        expect.objectContaining({
          expected_version: 5,
          title: "Title Changed Only",
          due_date: "2026-11-20T16:45:30Z", // EXACT timestamp preserved, not truncated to midnight!
        })
      );
    });
  });

  it("handles explicit due date change and pinned version", async () => {
    const taskWithTime: ComplianceTask = {
      ...dummyTask,
      id: "task-time-change",
      due_date: "2026-11-20T16:45:30Z",
      version: 4,
    };

    vi.spyOn(api, "fetchTask").mockResolvedValue(taskWithTime);
    const updateSpy = vi.spyOn(api, "updateTask").mockResolvedValue({
      ...taskWithTime,
      due_date: "2026-11-25T16:45:30Z",
      version: 5,
    });

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          tasks={[taskWithTime]}
        />
      </I18nProvider>
    );

    fireEvent.click(screen.getByTestId("task-row-task-time-change"));

    await waitFor(() => {
      expect(screen.getByTestId("edit-task-duedate")).toHaveValue("2026-11-20");
    });

    // Explicitly change the date input
    fireEvent.change(screen.getByTestId("edit-task-duedate"), {
      target: { value: "2026-11-25" },
    });
    fireEvent.click(screen.getByTestId("save-task-draft-btn"));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(
        "ten-1",
        "token-abc",
        "task-time-change",
        expect.objectContaining({
          expected_version: 4,
          due_date: "2026-11-25T16:45:30Z",
        })
      );
    });
  });

  it("renders bounded range notice and handles pagination for 101+ tasks", async () => {
    const manyTasks: ComplianceTask[] = Array.from({ length: 105 }, (_, i) => ({
      ...dummyTask,
      id: `task-${i + 1}`,
      title: `Compliance Task ${i + 1}`,
    }));

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          tasks={manyTasks}
        />
      </I18nProvider>
    );

    expect(screen.getByTestId("tasks-bounded-range-notice")).toBeInTheDocument();
    expect(screen.getByTestId("tasks-page-info")).toHaveTextContent("Showing 1–50 of 105 loaded");

    // Click Next
    fireEvent.click(screen.getByTestId("tasks-next-page-btn"));
    expect(screen.getByTestId("tasks-page-info")).toHaveTextContent("Showing 51–100 of 105 loaded");

    // Click Next again to page 3
    fireEvent.click(screen.getByTestId("tasks-next-page-btn"));
    expect(screen.getByTestId("tasks-page-info")).toHaveTextContent("Showing 101–105 of 105 loaded");
    expect(screen.getByTestId("tasks-next-page-btn")).toBeDisabled();

    // Click Prev back to page 2
    fireEvent.click(screen.getByTestId("tasks-prev-page-btn"));
    expect(screen.getByTestId("tasks-page-info")).toHaveTextContent("Showing 51–100 of 105 loaded");
  });

  it("selects record from targetTaskId prop and honors dirty switch guard", async () => {
    const taskA = { ...dummyTask, id: "task-a", title: "Task Alpha" };
    const taskB = { ...dummyTask, id: "task-b", title: "Task Beta" };

    vi.spyOn(api, "fetchTask")
      .mockResolvedValueOnce(taskA)
      .mockResolvedValueOnce(taskB);

    const { rerender } = render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          tasks={[taskA, taskB]}
          targetTaskId="task-a"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("edit-task-title")).toHaveValue("Task Alpha");
    });

    // Make dirty edit
    fireEvent.change(screen.getByTestId("edit-task-title"), {
      target: { value: "Unsaved Changes in Alpha" },
    });

    // Target navigation to task-b arrives while dirty
    rerender(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          tasks={[taskA, taskB]}
          targetTaskId="task-b"
        />
      </I18nProvider>
    );

    // Guard dialog appears
    await waitFor(() => {
      expect(screen.getByTestId("task-dirty-switch-guard")).toBeInTheDocument();
    });
  });
  it("implements server-backed limit and offset pagination reaching task 101 and beyond", async () => {
    // Generate pages of tasks
    const page1Tasks: ComplianceTask[] = Array.from({ length: 50 }, (_, i) => ({
      ...dummyTask,
      id: `task-${i + 1}`,
      title: `Server Task ${i + 1}`,
    }));
    const page2Tasks: ComplianceTask[] = Array.from({ length: 50 }, (_, i) => ({
      ...dummyTask,
      id: `task-${i + 51}`,
      title: `Server Task ${i + 51}`,
    }));
    const page3Tasks: ComplianceTask[] = Array.from({ length: 5 }, (_, i) => ({
      ...dummyTask,
      id: `task-${i + 101}`,
      title: `Server Task ${i + 101}`,
    }));

    const fetchTasksSpy = vi.spyOn(api, "fetchTasks").mockImplementation(async (_tenant, _token, opts) => {
      if (opts?.offset === 0) return page1Tasks;
      if (opts?.offset === 50) return page2Tasks;
      if (opts?.offset === 100) return page3Tasks;
      return [];
    });

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
        />
      </I18nProvider>
    );

    // Page 1 initial load
    await waitFor(() => {
      expect(fetchTasksSpy).toHaveBeenCalledWith("ten-1", "token-abc", expect.objectContaining({ limit: 50, offset: 0 }), expect.anything());
      expect(screen.getByText("Server Task 1")).toBeInTheDocument();
      expect(screen.getByTestId("tasks-page-info")).toHaveTextContent("Showing 1–50 of 50+ loaded");
    });

    // Navigate to page 2 (offset 50)
    fireEvent.click(screen.getByTestId("tasks-next-page-btn"));

    await waitFor(() => {
      expect(fetchTasksSpy).toHaveBeenCalledWith("ten-1", "token-abc", expect.objectContaining({ limit: 50, offset: 50 }), expect.anything());
      expect(screen.getByText("Server Task 51")).toBeInTheDocument();
      expect(screen.getByTestId("tasks-page-info")).toHaveTextContent("Showing 51–100 of 100+ loaded");
    });

    // Navigate to page 3 (offset 100) reaching task 101 and beyond
    fireEvent.click(screen.getByTestId("tasks-next-page-btn"));

    await waitFor(() => {
      expect(fetchTasksSpy).toHaveBeenCalledWith("ten-1", "token-abc", expect.objectContaining({ limit: 50, offset: 100 }), expect.anything());
      expect(screen.getByText("Server Task 101")).toBeInTheDocument();
      expect(screen.getByText("Server Task 105")).toBeInTheDocument();
      expect(screen.getByTestId("tasks-page-info")).toHaveTextContent("Showing 101–105 of 105 loaded");
      expect(screen.getByTestId("tasks-next-page-btn")).toBeDisabled();
    });
  });

  it("selects and loads off-page target record without corrupting loaded result counts", async () => {
    const page1Tasks: ComplianceTask[] = Array.from({ length: 50 }, (_, i) => ({
      ...dummyTask,
      id: `task-${i + 1}`,
      title: `Server Task ${i + 1}`,
    }));

    const offPageTask: ComplianceTask = {
      ...dummyTask,
      id: "task-105",
      title: "Off-page Task 105",
      description: "Detailed description of task 105",
      version: 2,
    };

    vi.spyOn(api, "fetchTasks").mockResolvedValue(page1Tasks);
    const fetchTaskSpy = vi.spyOn(api, "fetchTask").mockResolvedValue(offPageTask);

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          targetTaskId="task-105"
        />
      </I18nProvider>
    );

    // Detail for task-105 is fetched and displayed
    await waitFor(() => {
      expect(fetchTaskSpy).toHaveBeenCalledWith("ten-1", "token-abc", "task-105", expect.anything());
      expect(screen.getByTestId("edit-task-title")).toHaveValue("Off-page Task 105");
    });

    // Result count in table pagination is not falsely increased
    expect(screen.getByTestId("tasks-page-info")).toHaveTextContent("Showing 1–50 of 50+ loaded");
  });


  it("ignores out-of-order reverse query completions when filter changes", async () => {
    let resolveReqA!: (val: ComplianceTask[]) => void;
    let resolveReqB!: (val: ComplianceTask[]) => void;
    const promiseA = new Promise<ComplianceTask[]>((res) => { resolveReqA = res; });
    const promiseB = new Promise<ComplianceTask[]>((res) => { resolveReqB = res; });

    const taskA: ComplianceTask = { ...dummyTask, id: "task-A", title: "Pending Task A", status: "pending" };
    const taskB: ComplianceTask = { ...dummyTask, id: "task-B", title: "Completed Task B", status: "completed" };

    let callCount = 0;
    vi.spyOn(api, "fetchTasks").mockImplementation(() => {
      callCount++;
      if (callCount === 1) return promiseA;
      return promiseB;
    });

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
        />
      </I18nProvider>
    );

    // Wait for first query A to be initiated
    await waitFor(() => {
      expect(callCount).toBe(1);
    });

    // Now change filter to completed (query B)
    const statusSelect = screen.getByTestId("task-status-filter");
    fireEvent.change(statusSelect, { target: { value: "completed" } });

    await waitFor(() => {
      expect(callCount).toBe(2);
    });

    // Query B finishes first with taskB
    resolveReqB([taskB]);
    await waitFor(() => {
      expect(screen.getByText("Completed Task B")).toBeInTheDocument();
    });

    // Older Query A finishes later with taskA
    resolveReqA([taskA]);

    // Query A response must be ignored and not overwrite taskB
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getByText("Completed Task B")).toBeInTheDocument();
    expect(screen.queryByText("Pending Task A")).not.toBeInTheDocument();
  });

  it("discards stale 401 from previous tenant/token session without calling onSessionExpired", async () => {
    let rejectReq1!: (err: unknown) => void;
    const promise1 = new Promise<ComplianceTask[]>((_, rej) => { rejectReq1 = rej; });
    const pendingPromise2 = new Promise<ComplianceTask[]>(() => {});

    let call = 0;
    const fetchTasksSpy = vi.spyOn(api, "fetchTasks").mockImplementation(() => {
      call++;
      if (call === 1) return promise1;
      return pendingPromise2;
    });
    const onSessionExpiredSpy = vi.fn();

    const { rerender } = render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-1"
          userRole="compliance_manager"
          onSessionExpired={onSessionExpiredSpy}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(fetchTasksSpy).toHaveBeenCalledWith("ten-1", "token-1", expect.anything(), expect.anything());
    });

    // Context changes to tenant-2 / token-2
    rerender(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-2"
          token="token-2"
          userRole="compliance_manager"
          onSessionExpired={onSessionExpiredSpy}
        />
      </I18nProvider>
    );

    // Older request from token-1 fails with 401
    rejectReq1(new UnauthorizedError("Old session expired"));

    await new Promise((r) => setTimeout(r, 50));
    // Must NOT expire the new session
    expect(onSessionExpiredSpy).not.toHaveBeenCalled();
  });

  it("invalidates pending list read when a task mutation occurs", async () => {
    let resolveListReq!: (val: ComplianceTask[]) => void;
    const listPromise = new Promise<ComplianceTask[]>((res) => { resolveListReq = res; });

    const initialTask: ComplianceTask = { ...dummyTask, id: "task-1", title: "Task 1", version: 1 };
    vi.spyOn(api, "fetchTasks").mockReturnValue(listPromise);
    vi.spyOn(api, "fetchTask").mockResolvedValue(initialTask);

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          initialSelectedTaskId="task-1"
        />
      </I18nProvider>
    );

    // Wait for task detail to load
    await waitFor(() => {
      expect(screen.getByTestId("complete-task-btn")).toBeInTheDocument();
    });

    // Complete task triggers mutation
    const mutatedTask: ComplianceTask = { ...dummyTask, id: "task-1", title: "Task 1", status: "completed", version: 2 };
    vi.spyOn(api, "completeTask").mockResolvedValue(mutatedTask);

    const completeBtn = screen.getByTestId("complete-task-btn");
    fireEvent.click(completeBtn);

    await waitFor(() => {
      expect(screen.getByText("Task completed successfully.")).toBeInTheDocument();
    });

    // Older pending list response resolves with obsolete status
    resolveListReq([{ ...dummyTask, id: "task-1", title: "Task 1", status: "pending", version: 1 }]);

    await new Promise((r) => setTimeout(r, 50));
    // Mutation result must remain intact
    expect(screen.getByText("Task completed successfully.")).toBeInTheDocument();
  });

  it("reloads current visible page and coordinates parent calendar refresh on Refresh click while preserving dirty edits", async () => {
    const page2Tasks: ComplianceTask[] = [{ ...dummyTask, id: "task-51", title: "Server Task 51" }];
    const fetchTasksSpy = vi.spyOn(api, "fetchTasks").mockResolvedValue(page2Tasks);
    vi.spyOn(api, "fetchTask").mockResolvedValue(page2Tasks[0]);
    const onRefreshSpy = vi.fn();

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          onRefresh={onRefreshSpy}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Server Task 51")).toBeInTheDocument();
    });

    // Select row to load details
    fireEvent.click(screen.getByTestId("task-row-task-51"));
    await waitFor(() => {
      expect(screen.getByTestId("edit-task-title")).toHaveValue("Server Task 51");
    });

    // Make dirty edits in the form
    const titleInput = screen.getByTestId("edit-task-title");
    fireEvent.change(titleInput, { target: { value: "Dirty Draft Title Not Saved" } });
    expect(titleInput).toHaveValue("Dirty Draft Title Not Saved");

    // Click Refresh button
    fetchTasksSpy.mockClear();
    const updatedPage2Tasks: ComplianceTask[] = [{ ...dummyTask, id: "task-51", title: "Updated Server Task 51" }];
    fetchTasksSpy.mockResolvedValue(updatedPage2Tasks);

    const refreshBtn = screen.getByTestId("refresh-tasks-btn");
    fireEvent.click(refreshBtn);

    await waitFor(() => {
      // Must call fetchTasks to reload the child table
      expect(fetchTasksSpy).toHaveBeenCalled();
      // Must coordinate parent calendar refresh
      expect(onRefreshSpy).toHaveBeenCalled();
    });

    // Dirty draft must be preserved and not overwritten!
    expect(titleInput).toHaveValue("Dirty Draft Title Not Saved");
  });


  it("does not call onSessionExpired when unmounted TaskWorkspace receives 401 from pending list or detail request", async () => {
    let rejectListReq!: (err: unknown) => void;
    const listPromise = new Promise<ComplianceTask[]>((_, rej) => { rejectListReq = rej; });
    let rejectDetailReq!: (err: unknown) => void;
    const detailPromise = new Promise<ComplianceTask>((_, rej) => { rejectDetailReq = rej; });

    const fetchTasksSpy = vi.spyOn(api, "fetchTasks").mockReturnValue(listPromise);
    const fetchTaskSpy = vi.spyOn(api, "fetchTask").mockReturnValue(detailPromise);

    const onSessionExpiredSpy = vi.fn();

    const { unmount } = render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-1"
          userRole="compliance_manager"
          initialSelectedTaskId="task-1"
          onSessionExpired={onSessionExpiredSpy}
        />
      </I18nProvider>
    );

    // Wait for initial list and detail requests to start
    await waitFor(() => {
      expect(fetchTasksSpy).toHaveBeenCalled();
      expect(fetchTaskSpy).toHaveBeenCalled();
    });

    // Unmount before requests settle
    unmount();

    // Now old requests reject with 401 Unauthorized
    rejectListReq(new UnauthorizedError("List expired"));
    rejectDetailReq(new UnauthorizedError("Detail expired"));

    await new Promise((r) => setTimeout(r, 50));
    expect(onSessionExpiredSpy).not.toHaveBeenCalled();
  });

  it("aborts in-flight list and detail requests on unmount or session replacement", async () => {
    let listSignal: AbortSignal | undefined;
    let detailSignal: AbortSignal | undefined;

    vi.spyOn(api, "fetchTasks").mockImplementation((_tenant, _token, _opts, signal) => {
      listSignal = signal;
      return new Promise(() => {});
    });
    vi.spyOn(api, "fetchTask").mockImplementation((_tenant, _token, _id, signal) => {
      detailSignal = signal;
      return new Promise(() => {});
    });

    const { unmount } = render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-1"
          userRole="compliance_manager"
          initialSelectedTaskId="task-1"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(listSignal).toBeDefined();
      expect(detailSignal).toBeDefined();
    });

    expect(listSignal?.aborted).toBe(false);
    expect(detailSignal?.aborted).toBe(false);

    unmount();

    expect(listSignal?.aborted).toBe(true);
    expect(detailSignal?.aborted).toBe(true);
  });

  it("does not leave Task B action buttons disabled when Task A has pending complete and user switches to Task B", async () => {
    const taskA: ComplianceTask = {
      id: "task-1",
      tenant_id: "ten-1",
      title: "Task A",
      description: "Desc A",
      priority: "medium",
      status: "pending",
      due_date: "2026-11-20T00:00:00Z",
      assignee_user_id: null,
      control_type: null,
      control_id: null,
      evidence_id: null,
      policy_id: null,
      version: 1,
      completed_at: null,
      completed_by_user_id: null,
      created_at: "2026-10-26T10:00:00Z",
      updated_at: "2026-10-26T10:00:00Z",
    };
    const taskB: ComplianceTask = {
      id: "task-2",
      tenant_id: "ten-1",
      title: "Task B",
      description: "Desc B",
      priority: "high",
      status: "pending",
      due_date: "2026-11-25T00:00:00Z",
      assignee_user_id: null,
      control_type: null,
      control_id: null,
      evidence_id: null,
      policy_id: null,
      version: 1,
      completed_at: null,
      completed_by_user_id: null,
      created_at: "2026-10-26T10:00:00Z",
      updated_at: "2026-10-26T10:00:00Z",
    };

    vi.spyOn(api, "fetchTasks").mockResolvedValue([taskA, taskB]);

    vi.spyOn(api, "fetchTask").mockImplementation(async (_tenant, _token, id) => {
      if (id === "task-1") return taskA;
      if (id === "task-2") return taskB;
      throw new Error("Not found");
    });

    let resolveCompleteA: (val: ComplianceTask) => void = () => {};
    const completePromiseA = new Promise((r) => {
      resolveCompleteA = r;
    });

    vi.spyOn(api, "completeTask").mockImplementation(async (_tenant, _token, id) => {
      if (id === "task-1") {
        return completePromiseA as Promise<ComplianceTask>;
      }
      return { ...taskB, status: "completed", version: 2 };
    });

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-1"
          userRole="compliance_manager"
          tasks={[taskA, taskB]}
          initialSelectedTaskId="task-1"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByDisplayValue("Task A")).toBeInTheDocument();
    });

    const completeBtn = screen.getByRole("button", { name: /Complete Task/i });
    expect(completeBtn).toBeInTheDocument();
    expect((completeBtn as HTMLButtonElement).disabled).toBe(false);

    // Trigger Complete on Task A
    fireEvent.click(completeBtn);

    // Complete on Task A is now loading
    expect(screen.getByText(/Completing\.\.\./i)).toBeInTheDocument();

    // Now user switches to Task B while Task A is completing
    const taskBRow = screen.getByText("Task B");
    fireEvent.click(taskBRow);

    // Wait for Task B to be selected
    await waitFor(() => {
      expect(screen.getByDisplayValue("Task B")).toBeInTheDocument();
    });

    // In unfixed code: Task B complete button is stuck disabled because actionLoading='complete' is shared!
    const completeBtnB = screen.getByRole("button", { name: /Complete Task/i });
    expect(completeBtnB).toBeInTheDocument();
    expect((completeBtnB as HTMLButtonElement).disabled).toBe(false);

    // Resolve Task A's complete
    resolveCompleteA({ ...taskA, status: "completed", version: 2 });
    await new Promise((r) => setTimeout(r, 50));

    // Task B remains enabled and usable
    expect((completeBtnB as HTMLButtonElement).disabled).toBe(false);
  });

  it("does not leave Task B action buttons disabled when Task A has pending save draft, user confirms dirty switch, and Task A finishes", async () => {
    const taskA: ComplianceTask = {
      id: "task-1",
      tenant_id: "ten-1",
      title: "Task A",
      description: "Desc A",
      priority: "medium",
      status: "pending",
      due_date: "2026-11-20T00:00:00Z",
      assignee_user_id: null,
      control_type: null,
      control_id: null,
      evidence_id: null,
      policy_id: null,
      version: 1,
      completed_at: null,
      completed_by_user_id: null,
      created_at: "2026-10-26T10:00:00Z",
      updated_at: "2026-10-26T10:00:00Z",
    };
    const taskB: ComplianceTask = {
      id: "task-2",
      tenant_id: "ten-1",
      title: "Task B",
      description: "Desc B",
      priority: "high",
      status: "pending",
      due_date: "2026-11-25T00:00:00Z",
      assignee_user_id: null,
      control_type: null,
      control_id: null,
      evidence_id: null,
      policy_id: null,
      version: 1,
      completed_at: null,
      completed_by_user_id: null,
      created_at: "2026-10-26T10:00:00Z",
      updated_at: "2026-10-26T10:00:00Z",
    };

    vi.spyOn(api, "fetchTasks").mockResolvedValue([taskA, taskB]);

    vi.spyOn(api, "fetchTask").mockImplementation(async (_tenant, _token, id) => {
      if (id === "task-1") return taskA;
      if (id === "task-2") return taskB;
      throw new Error("Not found");
    });

    let resolveSaveA: (val: ComplianceTask) => void = () => {};
    const savePromiseA = new Promise((r) => {
      resolveSaveA = r;
    });

    vi.spyOn(api, "updateTask").mockImplementation(async (_tenant, _token, id) => {
      if (id === "task-1") {
        return savePromiseA as Promise<ComplianceTask>;
      }
      return { ...taskB, title: "Updated Task B", version: 2 };
    });

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-1"
          userRole="compliance_manager"
          tasks={[taskA, taskB]}
          initialSelectedTaskId="task-1"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByDisplayValue("Task A")).toBeInTheDocument();
    });

    // Make Task A dirty
    const titleInput = screen.getByDisplayValue("Task A");
    fireEvent.change(titleInput, { target: { value: "Task A Edited" } });

    const saveBtn = screen.getByRole("button", { name: /Save Draft/i });
    expect((saveBtn as HTMLButtonElement).disabled).toBe(false);

    // Click Save on Task A
    fireEvent.click(saveBtn);
    expect(screen.getByText(/Saving\.\.\./i)).toBeInTheDocument();

    // Now click Task B row -> triggers dirty switch guard modal
    const taskBRow = screen.getByText("Task B");
    fireEvent.click(taskBRow);

    // Confirm dirty switch
    await waitFor(() => {
      expect(screen.getByText(/You have unsaved changes/i)).toBeInTheDocument();
    });
    const confirmSwitchBtn = screen.getByRole("button", { name: /Switch Record|Switch/i });
    fireEvent.click(confirmSwitchBtn);

    // Task B detail should load
    await waitFor(() => {
      expect(screen.getByDisplayValue("Task B")).toBeInTheDocument();
    });

    // In unfixed code: Task B complete button is stuck disabled because actionLoading='save' is shared!
    const completeBtnB = screen.getByRole("button", { name: /Complete Task/i });
    expect((completeBtnB as HTMLButtonElement).disabled).toBe(false);

    // Resolve Task A save
    resolveSaveA({ ...taskA, title: "Task A Edited", version: 2 });
    await new Promise((r) => setTimeout(r, 50));

    // Task B remains enabled
    expect((completeBtnB as HTMLButtonElement).disabled).toBe(false);
  });

  it("dirty-switch cancel preserves Task A edit and does not switch to Task B", async () => {
    const taskA: ComplianceTask = {
      id: "task-1",
      tenant_id: "ten-1",
      title: "Task A",
      description: "Desc A",
      priority: "medium",
      status: "pending",
      due_date: "2026-11-20T00:00:00Z",
      assignee_user_id: null,
      control_type: null,
      control_id: null,
      evidence_id: null,
      policy_id: null,
      version: 1,
      completed_at: null,
      completed_by_user_id: null,
      created_at: "2026-10-26T10:00:00Z",
      updated_at: "2026-10-26T10:00:00Z",
    };
    const taskB: ComplianceTask = {
      id: "task-2",
      tenant_id: "ten-1",
      title: "Task B",
      description: "Desc B",
      priority: "high",
      status: "pending",
      due_date: "2026-11-25T00:00:00Z",
      assignee_user_id: null,
      control_type: null,
      control_id: null,
      evidence_id: null,
      policy_id: null,
      version: 1,
      completed_at: null,
      completed_by_user_id: null,
      created_at: "2026-10-26T10:00:00Z",
      updated_at: "2026-10-26T10:00:00Z",
    };

    vi.spyOn(api, "fetchTasks").mockResolvedValue([taskA, taskB]);
    vi.spyOn(api, "fetchTask").mockImplementation(async (_tenant, _token, id) => {
      if (id === "task-1") return taskA;
      if (id === "task-2") return taskB;
      throw new Error("Not found");
    });

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-1"
          userRole="compliance_manager"
          tasks={[taskA, taskB]}
          initialSelectedTaskId="task-1"
        />
      </I18nProvider>
    );

    // Make dirty - await actual detail editor input before firing user change
    const titleInput = await screen.findByDisplayValue("Task A");
    fireEvent.change(titleInput, { target: { value: "Task A Dirty" } });

    // Try switching to Task B
    fireEvent.click(screen.getByText("Task B"));

    // Modal appears
    await waitFor(() => {
      expect(screen.getByText(/You have unsaved changes/i)).toBeInTheDocument();
    });

    // Cancel switch
    const cancelBtn = screen.getByTestId("cancel-discard-switch-btn");
    fireEvent.click(cancelBtn);

    // Still on Task A with dirty title
    expect(screen.getByDisplayValue("Task A Dirty")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("Task B")).not.toBeInTheDocument();
  });

  it("recovers actionState and does not leak errors across tasks when pending operation fails after record switch", async () => {
    const taskA: ComplianceTask = {
      id: "task-1",
      tenant_id: "ten-1",
      title: "Task A",
      description: "Desc A",
      priority: "medium",
      status: "pending",
      due_date: "2026-11-20T00:00:00Z",
      assignee_user_id: null,
      control_type: null,
      control_id: null,
      evidence_id: null,
      policy_id: null,
      version: 1,
      completed_at: null,
      completed_by_user_id: null,
      created_at: "2026-10-26T10:00:00Z",
      updated_at: "2026-10-26T10:00:00Z",
    };
    const taskB: ComplianceTask = {
      id: "task-2",
      tenant_id: "ten-1",
      title: "Task B",
      description: "Desc B",
      priority: "high",
      status: "pending",
      due_date: "2026-11-25T00:00:00Z",
      assignee_user_id: null,
      control_type: null,
      control_id: null,
      evidence_id: null,
      policy_id: null,
      version: 1,
      completed_at: null,
      completed_by_user_id: null,
      created_at: "2026-10-26T10:00:00Z",
      updated_at: "2026-10-26T10:00:00Z",
    };

    vi.spyOn(api, "fetchTasks").mockResolvedValue([taskA, taskB]);
    vi.spyOn(api, "fetchTask").mockImplementation(async (_tenant, _token, id) => {
      if (id === "task-1") return taskA;
      if (id === "task-2") return taskB;
      throw new Error("Not found");
    });

    let rejectCompleteA: (err: Error) => void = () => {};
    const completePromiseA = new Promise((_, rej) => {
      rejectCompleteA = rej;
    });

    vi.spyOn(api, "completeTask").mockImplementation(async (_tenant, _token, id) => {
      if (id === "task-1") {
        return completePromiseA as Promise<ComplianceTask>;
      }
      return { ...taskB, status: "completed", version: 2 };
    });

    render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-1"
          userRole="compliance_manager"
          tasks={[taskA, taskB]}
          initialSelectedTaskId="task-1"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByDisplayValue("Task A")).toBeInTheDocument();
    });

    const completeBtn = screen.getByRole("button", { name: /Complete Task/i });
    fireEvent.click(completeBtn);

    // Switch to Task B
    fireEvent.click(screen.getByText("Task B"));
    await waitFor(() => {
      expect(screen.getByDisplayValue("Task B")).toBeInTheDocument();
    });

    // Reject Task A
    rejectCompleteA(new Error("Task A Network Failed"));
    await new Promise((r) => setTimeout(r, 50));

    // Task B does NOT show Task A's error banner
    expect(screen.queryByText(/Task A Network Failed/i)).not.toBeInTheDocument();

    // Task B's complete button is enabled and functional
    const completeBtnB = screen.getByRole("button", { name: /Complete Task/i });
    expect((completeBtnB as HTMLButtonElement).disabled).toBe(false);
  });

  it("retires actionState and clears action messages on session replacement", async () => {
    const taskA: ComplianceTask = {
      id: "task-1",
      tenant_id: "ten-1",
      title: "Task A",
      description: "Desc A",
      priority: "medium",
      status: "pending",
      due_date: "2026-11-20T00:00:00Z",
      assignee_user_id: null,
      control_type: null,
      control_id: null,
      evidence_id: null,
      policy_id: null,
      version: 1,
      completed_at: null,
      completed_by_user_id: null,
      created_at: "2026-10-26T10:00:00Z",
      updated_at: "2026-10-26T10:00:00Z",
    };

    vi.spyOn(api, "fetchTasks").mockResolvedValue([taskA]);
    vi.spyOn(api, "fetchTask").mockResolvedValue(taskA);

    const { rerender } = render(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-1"
          token="token-1"
          userRole="compliance_manager"
          tasks={[taskA]}
          initialSelectedTaskId="task-1"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Task A")).toBeInTheDocument();
    });

    // Session replacement: new tenant / token
    rerender(
      <I18nProvider>
        <TaskWorkspaceV2
          tenantId="ten-2"
          token="token-2"
          userRole="compliance_manager"
          tasks={[taskA]}
          initialSelectedTaskId="task-1"
        />
      </I18nProvider>
    );

    // Detail reloads cleanly for new session
    await waitFor(() => {
      expect(screen.getByDisplayValue("Task A")).toBeInTheDocument();
    });

    const completeBtn = screen.getByRole("button", { name: /Complete Task/i });
    expect((completeBtn as HTMLButtonElement).disabled).toBe(false);
  });
});
