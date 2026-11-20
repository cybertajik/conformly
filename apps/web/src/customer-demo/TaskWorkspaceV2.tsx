import type { TenantRole } from "@conformly/shared";
import React, { FC, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { canManageTasks, canReadTasks } from "../permissions";
import { ConflictError, CustomerDemoApiError, ForbiddenError, UnauthorizedError, ValidationError } from "./api";
import { completeTask, createTask, fetchTask, fetchTasks, updateTask } from "./task-api";
import { ComplianceTask, CreateTaskInput, TaskPriority, TaskStatus, UpdateTaskInput } from "./task-types";
import "./modern-workspace.css";

export interface TaskWorkspaceV2Props {
  tenantId: string;
  token: string;
  userRole?: string;
  currentUserId?: string;
  tasks?: ComplianceTask[];
  loading?: boolean;
  onRefresh?: () => Promise<void> | void;
  onSessionExpired?: () => void;
  onTaskMutated?: (task: ComplianceTask) => void;
  onTaskCreated?: (task: ComplianceTask) => void;
  targetTaskId?: string | null;
  initialSelectedTaskId?: string | null;
  targetNonce?: number | null;
  onConsumeTarget?: () => void;
  admittedAssignees?: { user_id: string; display_name: string }[];
}

export const TaskWorkspaceV2: FC<TaskWorkspaceV2Props> = ({
  tenantId,
  token,
  userRole = "owner",
  tasks: propTasks,
  loading: propLoading = false,
  onRefresh,
  onSessionExpired,
  onTaskMutated,
  onTaskCreated,
  targetTaskId = null,
  initialSelectedTaskId = null,
  targetNonce = null,
  onConsumeTarget,
  admittedAssignees = [],
}) => {
  const { t } = useTranslation();

  const isRoleDenied = !canReadTasks(userRole as TenantRole);
  const canManage = canManageTasks(userRole as TenantRole);

  // Loaded tasks & pagination state
  const [internalTasks, setInternalTasks] = useState<ComplianceTask[]>(propTasks || []);
  const [loadingTasks, setLoadingTasks] = useState<boolean>(propLoading);
  const [taskLoadError, setTaskLoadError] = useState<string | null>(null);

  // Sync prop tasks when provided
  useEffect(() => {
    const timer = setTimeout(() => {
      if (propTasks) {
        setInternalTasks(propTasks);
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [propTasks]);

  // Filters
  const [statusFilter, setStatusFilter] = useState<TaskStatus | "all">("all");
  const [priorityFilter, setPriorityFilter] = useState<TaskPriority | "all">("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [taskPage, setTaskPage] = useState<number>(1);
  const [hasMoreTasks, setHasMoreTasks] = useState<boolean>(false);
  const TASK_PAGE_SIZE = 50;

  // Selection & Detail
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(initialSelectedTaskId);
  const [selectedTask, setSelectedTask] = useState<ComplianceTask | null>(null);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // Editing state pinned to version
  const [editTitle, setEditTitle] = useState<string>("");
  const [editDesc, setEditDesc] = useState<string>("");
  const [editDueDate, setEditDueDate] = useState<string>("");
  const [editPriority, setEditPriority] = useState<TaskPriority>("medium");
  const [editAssignee, setEditAssignee] = useState<string>("");
  const [editStatus, setEditStatus] = useState<TaskStatus>("pending");
  const [editorBaseVersion, setEditorBaseVersion] = useState<number>(1);
  const [hasEditChanges, setHasEditChanges] = useState<boolean>(false);

  // Guarded dirty switch
  const [pendingSwitchTaskId, setPendingSwitchTaskId] = useState<string | null>(null);

  // Creation form state
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [newTitle, setNewTitle] = useState<string>("");
  const [newDesc, setNewDesc] = useState<string>("");
  const [newDueDate, setNewDueDate] = useState<string>("");
  const [newPriority, setNewPriority] = useState<TaskPriority>("medium");
  const [newAssignee, setNewAssignee] = useState<string>("");
  const [createSubmitting, setCreateSubmitting] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Uncertain POST create state
  const [uncertainCreate, setUncertainCreate] = useState<{
    payload: CreateTaskInput;
    reconciled?: boolean;
    matchingTask?: ComplianceTask | null;
    attemptId: number;
  } | null>(null);
  const [reconciling, setReconciling] = useState<boolean>(false);
  const [reconcileError, setReconcileError] = useState<string | null>(null);

  // Action status banners
  const [actionState, setActionState] = useState<{ taskId: string; action: "save" | "complete" } | null>(null);
  const actionLoading = (actionState && selectedTask && actionState.taskId === selectedTask.id) ? actionState.action : null;
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [conflictOccurred, setConflictOccurred] = useState<boolean>(false);

  // Generational fencing refs
  const selectedTaskIdRef = useRef<string | null>(selectedTaskId);
  useEffect(() => {
    selectedTaskIdRef.current = selectedTaskId;
  }, [selectedTaskId]);

  const tenantIdRef = useRef(tenantId);
  const tokenRef = useRef(token);
  const taskPageRef = useRef(taskPage);
  const statusFilterRef = useRef(statusFilter);
  const priorityFilterRef = useRef(priorityFilter);

  useEffect(() => {
    taskPageRef.current = taskPage;
    statusFilterRef.current = statusFilter;
    priorityFilterRef.current = priorityFilter;
  }, [taskPage, statusFilter, priorityFilter]);

  const consumedTargetKeyRef = useRef<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      const target = targetTaskId || initialSelectedTaskId;
      if (!target) return;
      if (propLoading || loadingTasks) return;
      const targetKey = `${target}:${targetNonce ?? "static"}`;
      if (targetKey === consumedTargetKeyRef.current) return;
      consumedTargetKeyRef.current = targetKey;
      onConsumeTarget?.();
      if (hasEditChanges && selectedTaskId && selectedTaskId !== target) {
        setPendingSwitchTaskId(target);
      } else {
        setSelectedTaskId(target);
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [targetTaskId, initialSelectedTaskId, targetNonce, onConsumeTarget, propLoading, loadingTasks, hasEditChanges, selectedTaskId]);

  const isMountedRef = useRef<boolean>(true);
  const detailGenRef = useRef<number>(0);
  const detailAbortRef = useRef<AbortController | null>(null);
  const mutationGenRef = useRef<number>(0);
  const listGenRef = useRef<number>(0);
  const listAbortRef = useRef<AbortController | null>(null);
  const createAttemptIdRef = useRef<number>(0);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      listAbortRef.current?.abort();
      detailAbortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    tenantIdRef.current = tenantId;
    tokenRef.current = token;
    listAbortRef.current?.abort();
    detailAbortRef.current?.abort();
    listGenRef.current++;
    detailGenRef.current++;
    mutationGenRef.current++;
    createAttemptIdRef.current++;
    const timer = setTimeout(() => {
      setActionState(null);
      setActionError(null);
      setActionSuccess(null);
    }, 0);
    return () => clearTimeout(timer);
  }, [tenantId, token]);

  // Load Tasks List from API with server-backed pagination and generational fencing
  const loadTaskList = useCallback(async () => {
    if (!tenantId || !token || isRoleDenied) return;
    if (listAbortRef.current) {
      listAbortRef.current.abort();
    }
    const abortCtrl = new AbortController();
    listAbortRef.current = abortCtrl;

    const reqGen = ++listGenRef.current;
    const reqMutationGen = mutationGenRef.current;
    const reqTenantId = tenantId;
    const reqToken = token;
    const reqPage = taskPage;
    const reqStatus = statusFilter;
    const reqPriority = priorityFilter;

    setLoadingTasks(true);
    setTaskLoadError(null);
    try {
      const data = await fetchTasks(
        reqTenantId,
        reqToken,
        {
          limit: TASK_PAGE_SIZE,
          offset: (reqPage - 1) * TASK_PAGE_SIZE,
          status: reqStatus === "all" ? undefined : reqStatus,
          priority: reqPriority === "all" ? undefined : reqPriority,
        },
        abortCtrl.signal
      );

      if (
        !isMountedRef.current ||
        abortCtrl.signal.aborted ||
        reqGen !== listGenRef.current ||
        reqMutationGen !== mutationGenRef.current ||
        reqTenantId !== tenantIdRef.current ||
        reqToken !== tokenRef.current ||
        reqPage !== taskPageRef.current ||
        reqStatus !== statusFilterRef.current ||
        reqPriority !== priorityFilterRef.current
      ) {
        return;
      }

      setInternalTasks(data);
      setHasMoreTasks(data.length === TASK_PAGE_SIZE);
    } catch (err: unknown) {
      if (
        !isMountedRef.current ||
        abortCtrl.signal.aborted ||
        reqGen !== listGenRef.current ||
        reqTenantId !== tenantIdRef.current ||
        reqToken !== tokenRef.current
      ) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        if (
          isMountedRef.current &&
          reqToken === tokenRef.current &&
          reqTenantId === tenantIdRef.current
        ) {
          onSessionExpired?.();
        }
        return;
      }
      if (
        reqMutationGen !== mutationGenRef.current ||
        reqPage !== taskPageRef.current ||
        reqStatus !== statusFilterRef.current ||
        reqPriority !== priorityFilterRef.current
      ) {
        return;
      }
      setTaskLoadError(err instanceof Error ? err.message : "Failed to load tasks");
    } finally {
      if (
        isMountedRef.current &&
        reqGen === listGenRef.current &&
        !abortCtrl.signal.aborted &&
        reqTenantId === tenantIdRef.current &&
        reqToken === tokenRef.current &&
        reqPage === taskPageRef.current &&
        reqStatus === statusFilterRef.current &&
        reqPriority === priorityFilterRef.current
      ) {
        setLoadingTasks(false);
      }
    }
  }, [tenantId, token, isRoleDenied, taskPage, statusFilter, priorityFilter, onSessionExpired]);

  useEffect(() => {
    let ignore = false;
    if (propTasks === undefined) {
      void Promise.resolve().then(() => {
        if (!ignore) {
          void loadTaskList();
        }
      });
    }
    return () => {
      ignore = true;
    };
  }, [propTasks, loadTaskList]);

  // Load Task Detail
  const loadDetail = useCallback(
    async (taskId: string) => {
      if (!tenantId || !token || !taskId) return;
      if (detailAbortRef.current) {
        detailAbortRef.current.abort();
      }
      const abortCtrl = new AbortController();
      detailAbortRef.current = abortCtrl;
      const gen = ++detailGenRef.current;
      const reqTenantId = tenantId;
      const reqToken = token;
      setLoadingDetail(true);
      setDetailError(null);
      setActionError(null);
      setActionSuccess(null);
      try {
        const detail = await fetchTask(reqTenantId, reqToken, taskId, abortCtrl.signal);
        if (
          !isMountedRef.current ||
          abortCtrl.signal.aborted ||
          gen !== detailGenRef.current ||
          taskId !== selectedTaskIdRef.current ||
          reqTenantId !== tenantIdRef.current ||
          reqToken !== tokenRef.current
        ) {
          return;
        }

        setSelectedTask(detail);
        setEditTitle(detail.title);
        setEditDesc(detail.description);
        setEditDueDate(detail.due_date ? detail.due_date.substring(0, 10) : "");
        setEditPriority(detail.priority);
        setEditAssignee(detail.assignee_user_id || "");
        setEditStatus(detail.status);
        setEditorBaseVersion(detail.version);
        setHasEditChanges(false);
        setConflictOccurred(false);
      } catch (err: unknown) {
        if (
          !isMountedRef.current ||
          abortCtrl.signal.aborted ||
          gen !== detailGenRef.current ||
          reqTenantId !== tenantIdRef.current ||
          reqToken !== tokenRef.current
        ) {
          return;
        }
        if (err instanceof UnauthorizedError) {
          if (
            isMountedRef.current &&
            reqToken === tokenRef.current &&
            reqTenantId === tenantIdRef.current
          ) {
            onSessionExpired?.();
          }
          return;
        }
        if (taskId !== selectedTaskIdRef.current) return;
        setDetailError(err instanceof Error ? err.message : "Failed to load task details");
      } finally {
        if (
          isMountedRef.current &&
          !abortCtrl.signal.aborted &&
          gen === detailGenRef.current &&
          reqTenantId === tenantIdRef.current &&
          reqToken === tokenRef.current
        ) {
          setLoadingDetail(false);
        }
      }
    },
    [tenantId, token, onSessionExpired]
  );

  // Trigger detail load on selectedTaskId change
  useEffect(() => {
    const timer = setTimeout(() => {
      if (selectedTaskId) {
        void loadDetail(selectedTaskId);
      } else {
        setSelectedTask(null);
        setEditTitle("");
        setEditDesc("");
        setEditDueDate("");
        setEditPriority("medium");
        setEditAssignee("");
        setEditStatus("pending");
        setHasEditChanges(false);
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [selectedTaskId, loadDetail]);

  // Guarded row selection
  const handleSelectTask = (taskId: string) => {
    if (taskId === selectedTaskId) return;
    if (hasEditChanges) {
      setPendingSwitchTaskId(taskId);
      return;
    }
    setSelectedTaskId(taskId);
  };

  // Filter tasks in memory for search query
  // Reset page when filter or search changes
  useEffect(() => {
    const timer = setTimeout(() => {
      setTaskPage(1);
    }, 0);
    return () => clearTimeout(timer);
  }, [statusFilter, priorityFilter, searchQuery]);

  const filteredTasks = internalTasks.filter((t) => {
    if (statusFilter !== "all" && t.status !== statusFilter) return false;
    if (priorityFilter !== "all" && t.priority !== priorityFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTitle = t.title.toLowerCase().includes(q);
      const matchDesc = t.description.toLowerCase().includes(q);
      if (!matchTitle && !matchDesc) return false;
    }
    return true;
  });

  // Handle Save Draft (Update)
  const handleSaveDraft = async () => {
    if (!selectedTask || !canManage || actionLoading) return;
    setActionState({ taskId: selectedTask.id, action: "save" });
    setActionError(null);
    setActionSuccess(null);

    const mutatingId = selectedTask.id;
    const mutationGen = ++mutationGenRef.current;

    let finalDueDate: string | undefined = undefined;
    if (editDueDate) {
      const origDueDate = selectedTask.due_date;
      const origDateOnly = origDueDate ? origDueDate.substring(0, 10) : "";
      if (origDueDate && editDueDate === origDateOnly) {
        finalDueDate = origDueDate;
      } else if (origDueDate && origDueDate.includes("T")) {
        const timePart = origDueDate.substring(origDueDate.indexOf("T"));
        finalDueDate = `${editDueDate}${timePart}`;
      } else {
        finalDueDate = `${editDueDate}T00:00:00Z`;
      }
    }

    const payload: UpdateTaskInput = {
      expected_version: editorBaseVersion,
      title: editTitle.trim(),
      description: editDesc.trim(),
      due_date: finalDueDate,
      priority: editPriority,
      assignee_user_id: editAssignee || null,
      status: editStatus,
    };

    const reqTenantId = tenantId;
    const reqToken = token;
    try {
      const updated = await updateTask(reqTenantId, reqToken, selectedTask.id, payload);
      if (
        !isMountedRef.current ||
        mutatingId !== selectedTaskIdRef.current ||
        mutationGen !== mutationGenRef.current ||
        reqTenantId !== tenantIdRef.current ||
        reqToken !== tokenRef.current
      ) {
        return;
      }
      onTaskMutated?.(updated);
      setInternalTasks((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));

      setSelectedTask(updated);
      setEditorBaseVersion(updated.version);
      setHasEditChanges(false);
      setConflictOccurred(false);
      setActionSuccess("Task updated successfully.");
    } catch (err: unknown) {
      if (
        !isMountedRef.current ||
        mutatingId !== selectedTaskIdRef.current ||
        mutationGen !== mutationGenRef.current ||
        reqTenantId !== tenantIdRef.current ||
        reqToken !== tokenRef.current
      ) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        if (
          isMountedRef.current &&
          reqToken === tokenRef.current &&
          reqTenantId === tenantIdRef.current
        ) {
          onSessionExpired?.();
        }
        return;
      }
      if (err instanceof ConflictError) {
        setConflictOccurred(true);
        setActionError(t("portal.conflictReloadNotice") || "Version conflict: another user modified this task.");
      } else if (err instanceof ValidationError) {
        setActionError(`Validation error: ${err.message}`);
      } else {
        setActionError(err instanceof Error ? err.message : "Failed to update task.");
      }
    } finally {
      if (isMountedRef.current) {
        setActionState((prev) => (prev && prev.taskId === mutatingId ? null : prev));
      }
    }
  };

  // Handle Complete Task
  const handleCompleteTask = async () => {
    if (!selectedTask || !canManage || actionLoading) return;
    setActionState({ taskId: selectedTask.id, action: "complete" });
    setActionError(null);
    setActionSuccess(null);

    const mutatingId = selectedTask.id;
    const mutationGen = ++mutationGenRef.current;

    const reqTenantId = tenantId;
    const reqToken = token;
    try {
      const updated = await completeTask(reqTenantId, reqToken, selectedTask.id, editorBaseVersion);
      if (
        !isMountedRef.current ||
        mutatingId !== selectedTaskIdRef.current ||
        mutationGen !== mutationGenRef.current ||
        reqTenantId !== tenantIdRef.current ||
        reqToken !== tokenRef.current
      ) {
        return;
      }
      onTaskMutated?.(updated);
      setInternalTasks((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));

      setSelectedTask(updated);
      setEditorBaseVersion(updated.version);
      setEditStatus(updated.status);
      setHasEditChanges(false);
      setConflictOccurred(false);
      setActionSuccess("Task completed successfully.");
    } catch (err: unknown) {
      if (
        !isMountedRef.current ||
        mutatingId !== selectedTaskIdRef.current ||
        mutationGen !== mutationGenRef.current ||
        reqTenantId !== tenantIdRef.current ||
        reqToken !== tokenRef.current
      ) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        if (
          isMountedRef.current &&
          reqToken === tokenRef.current &&
          reqTenantId === tenantIdRef.current
        ) {
          onSessionExpired?.();
        }
        return;
      }
      if (err instanceof ConflictError) {
        setConflictOccurred(true);
        setActionError(t("portal.conflictReloadNotice") || "Version conflict: another user modified this task.");
      } else {
        setActionError(err instanceof Error ? err.message : "Failed to complete task.");
      }
    } finally {
      if (isMountedRef.current) {
        setActionState((prev) => (prev && prev.taskId === mutatingId ? null : prev));
      }
    }
  };

  // Handle Discard Changes
  const handleDiscardChanges = () => {
    if (selectedTask) {
      setEditTitle(selectedTask.title);
      setEditDesc(selectedTask.description);
      setEditDueDate(selectedTask.due_date ? selectedTask.due_date.substring(0, 10) : "");
      setEditPriority(selectedTask.priority);
      setEditAssignee(selectedTask.assignee_user_id || "");
      setEditStatus(selectedTask.status);
      setEditorBaseVersion(selectedTask.version);
      setHasEditChanges(false);
      setConflictOccurred(false);
      setActionError(null);
    }
  };

  // Handle Create Task Submission
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManage || createSubmitting || Boolean(uncertainCreate)) return;

    if (!newTitle.trim()) {
      setCreateError(t("portal.entityNameRequired") || "Title is required.");
      return;
    }
    if (!newDueDate) {
      setCreateError("Due date is required.");
      return;
    }

    setCreateSubmitting(true);
    setCreateError(null);

    const payload: CreateTaskInput = {
      title: newTitle.trim(),
      description: newDesc.trim() || newTitle.trim(),
      due_date: new Date(newDueDate).toISOString(),
      priority: newPriority,
      assignee_user_id: newAssignee || null,
    };

    const reqTenantId = tenantId;
    const reqToken = token;
    const attemptGen = ++createAttemptIdRef.current;
    try {
      const created = await createTask(reqTenantId, reqToken, payload);
      if (
        !isMountedRef.current ||
        attemptGen !== createAttemptIdRef.current ||
        reqTenantId !== tenantIdRef.current ||
        reqToken !== tokenRef.current
      ) {
        return;
      }
      ++mutationGenRef.current;
      onTaskCreated?.(created);
      setInternalTasks((prev) => [created, ...prev]);
      setIsCreating(false);
      setNewTitle("");
      setNewDesc("");
      setNewDueDate("");
      setNewAssignee("");
      setSelectedTaskId(created.id);
      setActionSuccess(`Task created: ${created.title}`);
    } catch (err: unknown) {
      if (
        !isMountedRef.current ||
        attemptGen !== createAttemptIdRef.current ||
        reqTenantId !== tenantIdRef.current ||
        reqToken !== tokenRef.current
      ) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        if (
          isMountedRef.current &&
          reqToken === tokenRef.current &&
          reqTenantId === tenantIdRef.current
        ) {
          onSessionExpired?.();
        }
        return;
      }
      const isDefinite =
        err instanceof ValidationError ||
        err instanceof ForbiddenError ||
        (err instanceof CustomerDemoApiError && [400, 401, 403, 409, 422].includes(err.status));

      if (isDefinite) {
        setCreateError(err instanceof Error ? err.message : "Failed to create task");
      } else {
        setUncertainCreate({
          payload,
          reconciled: false,
          matchingTask: null,
          attemptId: attemptGen,
        });
        setCreateError(
          t("portal.uncertainCreateNotice") ||
            "Create outcome uncertain due to network or server error. Please reconcile with server state before proceeding."
        );
      }
    } finally {
      if (isMountedRef.current && attemptGen === createAttemptIdRef.current) {
        setCreateSubmitting(false);
      }
    }
  };

  // Reconcile Uncertain Create via fresh scoped GET and full payload comparison
  const handleReconcileCreate = async () => {
    if (!uncertainCreate || reconciling) return;
    const attemptId = uncertainCreate.attemptId;

    setReconciling(true);
    setReconcileError(null);
    const reqTenantId = tenantId;
    const reqToken = token;
    try {
      const freshList = await fetchTasks(reqTenantId, reqToken);
      if (
        !isMountedRef.current ||
        attemptId !== createAttemptIdRef.current ||
        reqTenantId !== tenantIdRef.current ||
        reqToken !== tokenRef.current
      ) {
        return;
      }

      const matched = freshList.find(
        (item) =>
          item.title === uncertainCreate.payload.title &&
          item.description === uncertainCreate.payload.description
      );

      setUncertainCreate((prev) => (prev ? { ...prev, reconciled: true, matchingTask: matched || null } : null));
    } catch (err: unknown) {
      if (
        !isMountedRef.current ||
        attemptId !== createAttemptIdRef.current ||
        reqTenantId !== tenantIdRef.current ||
        reqToken !== tokenRef.current
      ) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        if (
          isMountedRef.current &&
          reqToken === tokenRef.current &&
          reqTenantId === tenantIdRef.current
        ) {
          onSessionExpired?.();
        }
        return;
      }
      setReconcileError(err instanceof Error ? err.message : "Failed to reconcile with server state.");
    } finally {
      if (isMountedRef.current && attemptId === createAttemptIdRef.current) {
        setReconciling(false);
      }
    }
  };

  if (isRoleDenied) {
    return (
      <div className="mw-card" data-testid="task-workspace-denied">
        <div className="mw-notice-banner error" role="alert">
          {t("portal.operationsDeniedNotice")}
        </div>
      </div>
    );
  }

  return (
    <div className="mw-operations-tasks" data-testid="task-workspace">
      {/* Read-Only Notice for non-managers */}
      {!canManage && (
        <div
          className="mw-notice-banner"
          data-testid="tasks-readonly-notice"
          style={{ marginBottom: "1rem" }}
          role="status"
        >
          {t("portal.operationsReadOnlyNotice")}
        </div>
      )}

      {/* Action Success / Error Notifications */}
      {actionSuccess && (
        <div
          className="mw-notice-banner success"
          data-testid="task-action-success"
          role="status"
          style={{ marginBottom: "1rem" }}
        >
          {actionSuccess}
        </div>
      )}
      {actionError && (
        <div
          className="mw-notice-banner error"
          data-testid="task-action-error"
          role="alert"
          style={{ marginBottom: "1rem" }}
        >
          {actionError}
        </div>
      )}

      {/* Filter and Action Bar */}
      <div
        className="mw-filter-bar"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1rem",
          gap: "1rem",
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.85rem", color: "#666" }}>Filter:</span>
          <select
            className="mw-select"
            data-testid="task-status-filter"
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value as TaskStatus | "all"); setTaskPage(1); }}
            style={{ fontSize: "0.85rem", padding: "0.25rem 0.5rem" }}
          >
            <option value="all">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="overdue">Overdue</option>
            <option value="cancelled">Cancelled</option>
          </select>

          <select
            className="mw-select"
            data-testid="task-priority-filter"
            value={priorityFilter}
            onChange={(e) => { setPriorityFilter(e.target.value as TaskPriority | "all"); setTaskPage(1); }}
            style={{ fontSize: "0.85rem", padding: "0.25rem 0.5rem" }}
          >
            <option value="all">All Priorities</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>

          <input
            type="text"
            className="mw-input"
            data-testid="task-search-input"
            placeholder="Search tasks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ fontSize: "0.85rem", padding: "0.25rem 0.5rem", width: "180px" }}
          />

          <button
            type="button"
            className="mw-btn mw-btn-secondary"
            data-testid="refresh-tasks-btn"
            onClick={async () => {
              await loadTaskList();
              if (onRefresh) {
                void onRefresh();
              }
              if (selectedTaskId && !hasEditChanges) {
                void loadDetail(selectedTaskId);
              }
            }}
          >
            Refresh
          </button>
        </div>

        {canManage && (
          <button
            type="button"
            className="mw-btn mw-btn-primary"
            data-testid="new-task-btn"
            onClick={() => {
              setIsCreating(!isCreating);
              setCreateError(null);
            }}
          >
            {isCreating ? "Cancel" : t("portal.createRecordBtn")}
          </button>
        )}
      </div>

      {/* Creation Modal / Form */}
      {isCreating && (
        <div
          className="mw-card"
          data-testid="new-task-form-card"
          style={{ marginBottom: "1.5rem", border: "1px solid #0052cc" }}
        >
          <h3>Create New Compliance Task</h3>
          {createError && (
            <div className="mw-notice-banner error" role="alert" style={{ marginBottom: "0.75rem" }}>
              {createError}
            </div>
          )}

          {/* Uncertain Create Banner */}
          {uncertainCreate && (
            <div
              className="mw-notice-banner warning"
              data-testid="task-uncertain-create-banner"
              style={{ marginBottom: "0.75rem" }}
              role="alert"
            >
              <p>
                {t("portal.uncertainCreateNotice") ||
                  "Create outcome uncertain due to network or server error. Please reconcile with server state before proceeding."}
              </p>
              {reconcileError && (
                <p style={{ color: "#b91c1c", fontSize: "0.85rem", margin: "0.25rem 0" }}>{reconcileError}</p>
              )}
              {!uncertainCreate.reconciled ? (
                <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                  <button
                    type="button"
                    className="mw-btn mw-btn-secondary"
                    data-testid="reconcile-task-btn"
                    onClick={handleReconcileCreate}
                    disabled={reconciling}
                  >
                    {reconciling ? "Checking Server..." : "Check Server State"}
                  </button>
                  <button
                    type="button"
                    className="mw-btn mw-btn-secondary"
                    onClick={() => {
                      setUncertainCreate(null);
                      setCreateError(null);
                      setIsCreating(false);
                    }}
                  >
                    Discard Attempt
                  </button>
                </div>
              ) : uncertainCreate.matchingTask ? (
                <div style={{ marginTop: "0.5rem" }}>
                  <p style={{ fontWeight: 600, color: "#155724" }}>
                    Matching task found on server ({uncertainCreate.matchingTask.title}).
                  </p>
                  <button
                    type="button"
                    className="mw-btn mw-btn-primary"
                    data-testid="confirm-reconcile-task-btn"
                    onClick={() => {
                      if (uncertainCreate.matchingTask) {
                        setSelectedTaskId(uncertainCreate.matchingTask.id);
                        setUncertainCreate(null);
                        setIsCreating(false);
                        setActionSuccess(`Reconciled: ${uncertainCreate.matchingTask.title}`);
                      }
                    }}
                  >
                    Adopt Created Task
                  </button>
                </div>
              ) : (
                <div style={{ marginTop: "0.5rem" }}>
                  <p style={{ color: "#666" }}>No matching task found on server. Safe to resubmit.</p>
                  <button
                    type="button"
                    className="mw-btn mw-btn-secondary"
                    onClick={() => {
                      setUncertainCreate(null);
                      setCreateError(null);
                    }}
                  >
                    Dismiss & Retry
                  </button>
                </div>
              )}
            </div>
          )}

          <form onSubmit={handleCreateSubmit}>
            <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: "1rem", marginBottom: "0.75rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>Title *</label>
                <input
                  type="text"
                  className="mw-input"
                  data-testid="new-task-title-input"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Conduct Firewall Audit"
                  disabled={Boolean(uncertainCreate) || createSubmitting}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>Due Date *</label>
                <input
                  type="date"
                  className="mw-input"
                  data-testid="new-task-duedate-input"
                  value={newDueDate}
                  onChange={(e) => setNewDueDate(e.target.value)}
                  disabled={Boolean(uncertainCreate) || createSubmitting}
                />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "0.75rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>Priority</label>
                <select
                  className="mw-input"
                  data-testid="new-task-priority-select"
                  value={newPriority}
                  onChange={(e) => setNewPriority(e.target.value as TaskPriority)}
                  disabled={Boolean(uncertainCreate) || createSubmitting}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>Assignee</label>
                <select
                  className="mw-input"
                  data-testid="new-task-assignee-select"
                  value={newAssignee}
                  onChange={(e) => setNewAssignee(e.target.value)}
                  disabled={Boolean(uncertainCreate) || createSubmitting}
                >
                  <option value="">Unassigned</option>
                  {admittedAssignees.map((a) => (
                    <option key={a.user_id} value={a.user_id}>
                      {a.display_name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ marginBottom: "0.75rem" }}>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>Description</label>
              <textarea
                className="mw-input"
                data-testid="new-task-desc-input"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                rows={3}
                placeholder="Actionable instructions for this task..."
                disabled={Boolean(uncertainCreate) || createSubmitting}
              />
            </div>

            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                type="submit"
                className="mw-btn mw-btn-primary"
                data-testid="submit-create-task-btn"
                disabled={createSubmitting || Boolean(uncertainCreate)}
              >
                {createSubmitting ? "Creating..." : "Save Task"}
              </button>
              <button
                type="button"
                className="mw-btn mw-btn-secondary"
                onClick={() => setIsCreating(false)}
                disabled={createSubmitting}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Two Column Layout: Tasks List and Inspector */}
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "1.5rem" }}>
        {/* Left Column: Tasks Table */}
        <div className="mw-card" style={{ padding: "0.5rem" }}>
          {loadingTasks ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "#666" }}>Loading tasks...</div>
          ) : taskLoadError ? (
            <div className="mw-notice-banner error" role="alert" style={{ margin: "1rem" }}>
              {taskLoadError}
            </div>
          ) : filteredTasks.length === 0 ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "#888" }}>
              {statusFilter !== "all" || priorityFilter !== "all" || searchQuery
                ? "No tasks match the active filters."
                : "No tasks registered. Click 'New Record' to create one."}
            </div>
          ) : (
            <>
              {((propTasks !== undefined ? internalTasks.length >= 100 : (taskPage >= 2 || (taskPage - 1) * TASK_PAGE_SIZE + internalTasks.length >= 100 || hasMoreTasks))) && (
                <div
                  className="mw-notice-banner info"
                  data-testid="tasks-bounded-range-notice"
                  style={{ marginBottom: "0.5rem", padding: "0.5rem 0.75rem", fontSize: "0.8rem" }}
                >
                  Displaying bounded range ({internalTasks.length} loaded). Additional tasks may exist on server.
                </div>
              )}
              <table className="mw-table" data-testid="tasks-table" style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #e0e0e0", textAlign: "left" }}>
                  <th style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem" }}>Title</th>
                  <th style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem" }}>Status</th>
                  <th style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem" }}>Priority</th>
                  <th style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem" }}>Due Date</th>
                </tr>
              </thead>
              <tbody>
                {(propTasks !== undefined
                  ? filteredTasks.slice((Math.min(taskPage, Math.ceil(filteredTasks.length / TASK_PAGE_SIZE) || 1) - 1) * TASK_PAGE_SIZE, Math.min(taskPage, Math.ceil(filteredTasks.length / TASK_PAGE_SIZE) || 1) * TASK_PAGE_SIZE)
                  : filteredTasks
                ).map((t) => {
                  const isSelected = t.id === selectedTaskId;
                  return (
                    <tr
                      key={t.id}
                      data-testid={`task-row-${t.id}`}
                      onClick={() => handleSelectTask(t.id)}
                      style={{
                        cursor: "pointer",
                        background: isSelected ? "#e6f0ff" : "transparent",
                        borderBottom: "1px solid #f0f0f0",
                      }}
                    >
                      <td style={{ padding: "0.6rem 0.75rem", fontWeight: isSelected ? 600 : 400 }}>{t.title}</td>
                      <td style={{ padding: "0.6rem 0.75rem" }}>
                        <span
                          className={`mw-badge status-${t.status}`}
                          data-testid={`task-status-${t.id}`}
                          style={{
                            padding: "0.2rem 0.5rem",
                            borderRadius: "4px",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            textTransform: "uppercase",
                          }}
                        >
                          {t.status}
                        </span>
                      </td>
                      <td style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem", textTransform: "capitalize" }}>
                        {t.priority}
                      </td>
                      <td style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem", color: "#666" }}>
                        {t.due_date ? t.due_date.substring(0, 10) : "No date"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div
              data-testid="tasks-pagination"
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginTop: "0.75rem",
                paddingTop: "0.5rem",
                borderTop: "1px solid #f0f0f0",
              }}
            >
              {(() => {
                const isServerPaged = propTasks === undefined;
                const maxLocalPage = Math.ceil(filteredTasks.length / TASK_PAGE_SIZE) || 1;
                const hasNextPage = isServerPaged ? hasMoreTasks : taskPage < maxLocalPage;
                const hasPrevPage = taskPage > 1;

                const startCount = filteredTasks.length === 0 ? 0 : (taskPage - 1) * TASK_PAGE_SIZE + 1;
                const endCount = isServerPaged
                  ? (taskPage - 1) * TASK_PAGE_SIZE + filteredTasks.length
                  : Math.min(taskPage * TASK_PAGE_SIZE, filteredTasks.length);
                const totalDisplay = isServerPaged
                  ? `${endCount}${hasNextPage ? "+" : ""}`
                  : `${filteredTasks.length}`;

                return (
                  <>
                    <span data-testid="tasks-page-info" style={{ fontSize: "0.8rem", color: "#666" }}>
                      Showing {startCount}–{endCount} of {totalDisplay} loaded
                    </span>
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                      <button
                        type="button"
                        className="mw-btn mw-btn-secondary"
                        data-testid="tasks-prev-page-btn"
                        disabled={!hasPrevPage || propLoading || loadingTasks}
                        onClick={() => setTaskPage((p) => Math.max(1, p - 1))}
                        style={{ padding: "0.2rem 0.5rem", fontSize: "0.8rem" }}
                      >
                        Previous
                      </button>
                      <button
                        type="button"
                        className="mw-btn mw-btn-secondary"
                        data-testid="tasks-next-page-btn"
                        disabled={!hasNextPage || propLoading || loadingTasks}
                        onClick={() => setTaskPage((p) => p + 1)}
                        style={{ padding: "0.2rem 0.5rem", fontSize: "0.8rem" }}
                      >
                        Next
                      </button>
                    </div>
                  </>
                );
              })()}
            </div>
            </>
          )}
        </div>

        {/* Right Column: Selected Task Inspector */}
        <div className="mw-card" data-testid="task-details-panel">

          {loadingDetail && (

            <div data-testid="task-detail-loading" style={{ padding: "0.5rem 1rem", color: "#666", fontSize: "0.85rem" }}>

              Loading task details...

            </div>

          )}

          {detailError && (

            <div data-testid="task-detail-error" className="mw-alert mw-alert-danger" style={{ margin: "0.5rem 1rem" }}>

              {detailError}

            </div>

          )}
          {!selectedTask ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "#888" }}>
              <p>{t("portal.noRecordSelected") || "Select a task to view details"}</p>
            </div>
          ) : (
            <div>
              {/* Conflict Reload Banner */}
              {conflictOccurred && (
                <div
                  className="mw-notice-banner warning"
                  data-testid="conflict-reload-banner"
                  role="alert"
                  style={{
                    fontSize: "0.85rem",
                    marginBottom: "0.75rem",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span>{t("portal.conflictReloadNotice") || "Version conflict: another user modified this task."}</span>
                  <button
                    type="button"
                    className="mw-btn mw-btn-secondary"
                    data-testid="conflict-reload-btn"
                    onClick={() => {
                      if (selectedTask) void loadDetail(selectedTask.id);
                    }}
                  >
                    Reload Latest Version
                  </button>
                </div>
              )}

              {/* Action Buttons */}
              <div
                className="mw-actions-bar"
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  flexWrap: "wrap",
                  marginBottom: "1rem",
                  padding: "0.5rem",
                  background: "#f9f9fb",
                  borderRadius: "6px",
                }}
              >
                {canManage && selectedTask.status !== "completed" && selectedTask.status !== "cancelled" && (
                  <button
                    type="button"
                    className="mw-btn mw-btn-primary"
                    data-testid="complete-task-btn"
                    onClick={handleCompleteTask}
                    disabled={Boolean(actionLoading) || hasEditChanges}
                  >
                    {actionLoading === "complete" ? "Completing..." : "Complete Task"}
                  </button>
                )}
              </div>

              {/* Editable Fields */}
              <div style={{ marginBottom: "1rem" }}>
                <div style={{ marginBottom: "0.5rem" }}>
                  <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600 }}>Title</label>
                  <input
                    type="text"
                    className="mw-input"
                    data-testid="edit-task-title"
                    value={editTitle}
                    disabled={!canManage || selectedTask.status === "completed" || selectedTask.status === "cancelled"}
                    onChange={(e) => {
                      setEditTitle(e.target.value);
                      setHasEditChanges(true);
                    }}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", marginBottom: "0.5rem" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600 }}>Priority</label>
                    <select
                      className="mw-input"
                      data-testid="edit-task-priority"
                      value={editPriority}
                      disabled={!canManage || selectedTask.status === "completed" || selectedTask.status === "cancelled"}
                      onChange={(e) => {
                        setEditPriority(e.target.value as TaskPriority);
                        setHasEditChanges(true);
                      }}
                    >
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600 }}>Status</label>
                    <select
                      className="mw-input"
                      data-testid="edit-task-status"
                      value={editStatus}
                      disabled={!canManage || selectedTask.status === "completed" || selectedTask.status === "cancelled"}
                      onChange={(e) => {
                        setEditStatus(e.target.value as TaskStatus);
                        setHasEditChanges(true);
                      }}
                    >
                      <option value="pending">Pending</option>
                      <option value="in_progress">In Progress</option>
                      <option value="completed">Completed</option>
                      <option value="overdue">Overdue</option>
                      <option value="cancelled">Cancelled</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", marginBottom: "0.5rem" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600 }}>Due Date</label>
                    <input
                      type="date"
                      className="mw-input"
                      data-testid="edit-task-duedate"
                      value={editDueDate}
                      disabled={!canManage || selectedTask.status === "completed" || selectedTask.status === "cancelled"}
                      onChange={(e) => {
                        setEditDueDate(e.target.value);
                        setHasEditChanges(true);
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600 }}>Assignee</label>
                    <select
                      className="mw-input"
                      data-testid="edit-task-assignee"
                      value={editAssignee}
                      disabled={!canManage || selectedTask.status === "completed" || selectedTask.status === "cancelled"}
                      onChange={(e) => {
                        setEditAssignee(e.target.value);
                        setHasEditChanges(true);
                      }}
                    >
                      <option value="">Unassigned</option>
                      {admittedAssignees.map((a) => (
                        <option key={a.user_id} value={a.user_id}>
                          {a.display_name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div style={{ marginBottom: "0.5rem" }}>
                  <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600 }}>Description</label>
                  <textarea
                    className="mw-input"
                    data-testid="edit-task-desc"
                    value={editDesc}
                    rows={3}
                    disabled={!canManage || selectedTask.status === "completed" || selectedTask.status === "cancelled"}
                    onChange={(e) => {
                      setEditDesc(e.target.value);
                      setHasEditChanges(true);
                    }}
                  />
                </div>

                {canManage && selectedTask.status !== "completed" && selectedTask.status !== "cancelled" && (
                  <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                    <button
                      type="button"
                      className="mw-btn mw-btn-primary"
                      data-testid="save-task-draft-btn"
                      onClick={handleSaveDraft}
                      disabled={!hasEditChanges || Boolean(actionLoading)}
                    >
                      {actionLoading === "save" ? "Saving..." : t("portal.saveDraftBtn") || "Save Draft"}
                    </button>
                    {hasEditChanges && (
                      <button
                        type="button"
                        className="mw-btn mw-btn-secondary"
                        data-testid="discard-task-changes-btn"
                        onClick={handleDiscardChanges}
                      >
                        Discard Changes
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Read-Only Context Information */}
              <div
                style={{
                  fontSize: "0.75rem",
                  color: "#666",
                  borderTop: "1px solid #f0f0f0",
                  paddingTop: "0.75rem",
                  marginTop: "1rem",
                }}
              >
                <div>Task ID: {selectedTask.id}</div>
                <div>Tenant ID: {selectedTask.tenant_id}</div>
                <div>Version: {selectedTask.version}</div>
                {selectedTask.policy_id && <div>Linked Policy ID: {selectedTask.policy_id}</div>}
                {selectedTask.evidence_id && <div>Linked Evidence ID: {selectedTask.evidence_id}</div>}
                {selectedTask.completed_at && <div>Completed At: {selectedTask.completed_at}</div>}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Dirty Switch Guard Dialog */}
      {pendingSwitchTaskId && (
        <div
          role="dialog"
          aria-modal="true"
          data-testid="task-dirty-switch-guard"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
          }}
        >
          <div className="mw-card" style={{ maxWidth: "400px", padding: "1.5rem" }}>
            <h4 style={{ marginTop: 0 }}>Unsaved Changes</h4>
            <p>You have unsaved changes on this task. Discard them to switch?</p>
            <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end", marginTop: "1rem" }}>
              <button
                type="button"
                className="mw-btn mw-btn-secondary"
                data-testid="cancel-discard-switch-btn"
                onClick={() => setPendingSwitchTaskId(null)}
              >
                Keep Editing
              </button>
              <button
                type="button"
                className="mw-btn mw-btn-primary"
                data-testid="confirm-discard-switch-btn"
                onClick={() => {
                  const targetId = pendingSwitchTaskId;
                  setPendingSwitchTaskId(null);
                  setHasEditChanges(false);
                  setSelectedTaskId(targetId);
                }}
              >
                Discard & Switch
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
