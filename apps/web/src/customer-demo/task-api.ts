/**
 * Typed, cancellable API client for Tasks and Background Job Visibility.
 * Conforms strictly to existing backend endpoints:
 * - GET/POST /v1/tenants/{tenant_id}/compliance/tasks
 * - GET/PATCH /tasks/{task_id}
 * - POST /tasks/{task_id}/complete
 * - GET /v1/tenants/{tenant_id}/jobs/failed
 * - GET /v1/tenants/{tenant_id}/jobs/outbox
 */

import {
  ConflictError,
  CustomerDemoApiError,
  ForbiddenError,
  getApiBaseUrl,
  NotFoundError,
  UnauthorizedError,
  ValidationError,
} from "./api";
import {
  ComplianceTask,
  CreateTaskInput,
  FailedJobsResponse,
  OutboxMessageResponse,
  TaskPriority,
  TaskStatus,
  UpdateTaskInput,
} from "./task-types";

async function handleTaskResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail: string;
    try {
      const err = await res.json();
      if (err && typeof err.detail === "string") {
        detail = err.detail;
      } else if (err && typeof err.message === "string") {
        detail = err.message;
      } else {
        detail = res.statusText || `HTTP ${res.status}`;
      }
    } catch {
      detail = res.statusText || `HTTP ${res.status}`;
    }

    if (res.status === 401) throw new UnauthorizedError(detail);
    if (res.status === 403) throw new ForbiddenError(detail);
    if (res.status === 404) throw new NotFoundError(detail);
    if (res.status === 409) throw new ConflictError(detail);
    if (res.status === 422) throw new ValidationError(detail);
    throw new CustomerDemoApiError(detail, res.status, detail);
  }

  if (res.status === 204) {
    return undefined as unknown as T;
  }
  return res.json() as Promise<T>;
}

function authHeaders(token: string): HeadersInit {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

function validateTaskArray(data: unknown, expectedTenantId: string): ComplianceTask[] {
  if (!Array.isArray(data)) {
    throw new Error("Invalid response format: expected array of tasks");
  }
  for (const item of data) {
    if (!item || typeof item !== "object") {
      throw new Error("Invalid task item shape");
    }
    const t = item as Partial<ComplianceTask>;
    if (!t.tenant_id) {
      throw new Error("ComplianceTask missing required tenant_id");
    }
    if (t.tenant_id !== expectedTenantId) {
      throw new Error(`Tenant mismatch: expected ${expectedTenantId}, got ${t.tenant_id}`);
    }
  }
  return data as ComplianceTask[];
}

function validateSingleTask(item: unknown, expectedTenantId: string, expectedId?: string): ComplianceTask {
  if (!item || typeof item !== "object") {
    throw new Error("Invalid task shape");
  }
  const t = item as Partial<ComplianceTask>;
  if (!t.tenant_id || t.tenant_id !== expectedTenantId) {
    throw new Error(`Tenant mismatch in task response: expected ${expectedTenantId}, got ${t.tenant_id}`);
  }
  if (expectedId && t.id !== expectedId) {
    throw new Error(`ID mismatch in task response: expected ${expectedId}, got ${t.id}`);
  }
  return item as ComplianceTask;
}

// ── Tasks API ─────────────────────────────────────────────────────────────────

export async function fetchTasks(
  tenantId: string,
  token: string,
  options?: {
    status?: TaskStatus;
    priority?: TaskPriority;
    limit?: number;
    offset?: number;
  },
  signal?: AbortSignal
): Promise<ComplianceTask[]> {
  const base = getApiBaseUrl();
  const params = new URLSearchParams();
  if (options?.status) params.set("status", options.status);
  if (options?.priority) params.set("priority", options.priority);
  if (options?.limit !== undefined) params.set("limit", String(options.limit));
  if (options?.offset !== undefined) params.set("offset", String(options.offset));

  const queryStr = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(
    `${base}/v1/tenants/${encodeURIComponent(tenantId)}/compliance/tasks${queryStr}`,
    {
      method: "GET",
      headers: authHeaders(token),
      signal,
    }
  );

  const raw = await handleTaskResponse<ComplianceTask[]>(res);
  return validateTaskArray(raw, tenantId);
}

export async function fetchTask(
  tenantId: string,
  token: string,
  taskId: string,
  signal?: AbortSignal
): Promise<ComplianceTask> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v1/tenants/${encodeURIComponent(tenantId)}/compliance/tasks/${encodeURIComponent(taskId)}`,
    {
      method: "GET",
      headers: authHeaders(token),
      signal,
    }
  );

  const raw = await handleTaskResponse<ComplianceTask>(res);
  return validateSingleTask(raw, tenantId, taskId);
}

export async function createTask(
  tenantId: string,
  token: string,
  input: CreateTaskInput,
  signal?: AbortSignal
): Promise<ComplianceTask> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v1/tenants/${encodeURIComponent(tenantId)}/compliance/tasks`,
    {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify(input),
      signal,
    }
  );

  const raw = await handleTaskResponse<ComplianceTask>(res);
  return validateSingleTask(raw, tenantId);
}

export async function updateTask(
  tenantId: string,
  token: string,
  taskId: string,
  input: UpdateTaskInput,
  signal?: AbortSignal
): Promise<ComplianceTask> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v1/tenants/${encodeURIComponent(tenantId)}/compliance/tasks/${encodeURIComponent(taskId)}`,
    {
      method: "PATCH",
      headers: authHeaders(token),
      body: JSON.stringify(input),
      signal,
    }
  );

  const raw = await handleTaskResponse<ComplianceTask>(res);
  return validateSingleTask(raw, tenantId, taskId);
}

export async function completeTask(
  tenantId: string,
  token: string,
  taskId: string,
  expectedVersion: number,
  signal?: AbortSignal
): Promise<ComplianceTask> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v1/tenants/${encodeURIComponent(tenantId)}/compliance/tasks/${encodeURIComponent(taskId)}/complete`,
    {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify({ expected_version: expectedVersion }),
      signal,
    }
  );

  const raw = await handleTaskResponse<ComplianceTask>(res);
  return validateSingleTask(raw, tenantId, taskId);
}

// ── Background Jobs API (Read-Only) ───────────────────────────────────────────

export async function fetchFailedJobs(
  tenantId: string,
  token: string,
  signal?: AbortSignal
): Promise<FailedJobsResponse> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v1/tenants/${encodeURIComponent(tenantId)}/jobs/failed`,
    {
      method: "GET",
      headers: authHeaders(token),
      signal,
    }
  );

  const raw = await handleTaskResponse<FailedJobsResponse>(res);
  if (!raw || typeof raw !== "object" || raw.tenant_id !== tenantId) {
    throw new Error("Invalid failed jobs response shape or tenant mismatch");
  }
  return raw;
}

export async function fetchOutboxMessages(
  tenantId: string,
  token: string,
  options?: {
    state?: string;
    limit?: number;
    offset?: number;
  },
  signal?: AbortSignal
): Promise<OutboxMessageResponse[]> {
  const base = getApiBaseUrl();
  const params = new URLSearchParams();
  if (options?.state) params.set("state", options.state);
  if (options?.limit !== undefined) params.set("limit", String(options.limit));
  if (options?.offset !== undefined) params.set("offset", String(options.offset));

  const queryStr = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(
    `${base}/v1/tenants/${encodeURIComponent(tenantId)}/jobs/outbox${queryStr}`,
    {
      method: "GET",
      headers: authHeaders(token),
      signal,
    }
  );

  const raw = await handleTaskResponse<OutboxMessageResponse[]>(res);
  if (!Array.isArray(raw)) {
    throw new Error("Invalid outbox response format: expected array");
  }
  for (const item of raw) {
    if (!item || typeof item !== "object" || item.tenant_id !== tenantId) {
      throw new Error("Tenant mismatch in outbox item response");
    }
  }
  return raw;
}

