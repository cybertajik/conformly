/**
 * Typed, cancellable API client for Conformly LMS & Training Integration.
 * Conforms strictly to backend routes:
 * - GET/POST /v1/tenants/{tenant_id}/lms/courses
 * - GET/POST /v1/tenants/{tenant_id}/lms/assignments
 * - GET /v1/tenants/{tenant_id}/lms/completions
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
  CreateAssignmentPayload,
  CreateCoursePayload,
  TrainingAssignment,
  TrainingCourse,
  TrainingCompletion,
} from "./training-types";

async function handleLmsResponse<T>(res: Response): Promise<T> {
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

const MAX_RESPONSE_ITEMS = 1000;

function validateCourseArray(data: unknown, expectedTenantId: string): TrainingCourse[] {
  if (!Array.isArray(data)) {
    throw new Error("Invalid response format: expected array of courses");
  }
  if (data.length > MAX_RESPONSE_ITEMS) {
    throw new Error(`Response exceeds maximum permitted item count of ${MAX_RESPONSE_ITEMS}`);
  }
  for (const item of data) {
    if (!item || typeof item !== "object") {
      throw new Error("Invalid course item shape");
    }
    const c = item as Partial<TrainingCourse>;
    if (!c.tenant_id) {
      throw new Error("TrainingCourse missing required tenant_id");
    }
    if (c.tenant_id !== expectedTenantId) {
      throw new Error(`Tenant mismatch: expected ${expectedTenantId}, got ${c.tenant_id}`);
    }
    if (!c.id || typeof c.id !== "string" || !c.course_id || typeof c.course_id !== "string") {
      throw new Error("TrainingCourse missing required id or course_id");
    }
  }
  return data as TrainingCourse[];
}

function validateAssignmentArray(data: unknown, expectedTenantId: string): TrainingAssignment[] {
  if (!Array.isArray(data)) {
    throw new Error("Invalid response format: expected array of assignments");
  }
  if (data.length > MAX_RESPONSE_ITEMS) {
    throw new Error(`Response exceeds maximum permitted item count of ${MAX_RESPONSE_ITEMS}`);
  }
  for (const item of data) {
    if (!item || typeof item !== "object") {
      throw new Error("Invalid assignment item shape");
    }
    const a = item as Partial<TrainingAssignment>;
    if (!a.tenant_id) {
      throw new Error("TrainingAssignment missing required tenant_id");
    }
    if (a.tenant_id !== expectedTenantId) {
      throw new Error(`Tenant mismatch: expected ${expectedTenantId}, got ${a.tenant_id}`);
    }
    if (!a.id || typeof a.id !== "string" || !a.course_id || typeof a.course_id !== "string") {
      throw new Error("TrainingAssignment missing required id or course_id");
    }
  }
  return data as TrainingAssignment[];
}

function validateCompletionArray(data: unknown, expectedTenantId: string): TrainingCompletion[] {
  if (!Array.isArray(data)) {
    throw new Error("Invalid response format: expected array of completions");
  }
  if (data.length > MAX_RESPONSE_ITEMS) {
    throw new Error(`Response exceeds maximum permitted item count of ${MAX_RESPONSE_ITEMS}`);
  }
  for (const item of data) {
    if (!item || typeof item !== "object") {
      throw new Error("Invalid completion item shape");
    }
    const c = item as Partial<TrainingCompletion>;
    if (!c.tenant_id) {
      throw new Error("TrainingCompletion missing required tenant_id");
    }
    if (c.tenant_id !== expectedTenantId) {
      throw new Error(`Tenant mismatch: expected ${expectedTenantId}, got ${c.tenant_id}`);
    }
    if (!c.id || typeof c.id !== "string" || !c.course_id || typeof c.course_id !== "string") {
      throw new Error("TrainingCompletion missing required id or course_id");
    }
  }
  return data as TrainingCompletion[];
}

export async function fetchTrainingCourses(
  tenantId: string,
  token: string,
  signal?: AbortSignal,
): Promise<TrainingCourse[]> {
  const url = `${getApiBaseUrl()}/v1/tenants/${encodeURIComponent(tenantId)}/lms/courses`;
  const res = await fetch(url, {
    method: "GET",
    headers: authHeaders(token),
    signal,
  });
  const data = await handleLmsResponse<unknown>(res);
  return validateCourseArray(data, tenantId);
}

export async function createTrainingCourse(
  tenantId: string,
  token: string,
  payload: CreateCoursePayload,
  signal?: AbortSignal,
): Promise<TrainingCourse> {
  const url = `${getApiBaseUrl()}/v1/tenants/${encodeURIComponent(tenantId)}/lms/courses`;
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
    signal,
  });
  const data = await handleLmsResponse<TrainingCourse>(res);
  if (!data || data.tenant_id !== tenantId) {
    throw new Error(`Tenant mismatch on created course: expected ${tenantId}`);
  }
  return data;
}

export async function fetchTrainingAssignments(
  tenantId: string,
  token: string,
  options?: { status?: string; user_id?: string },
  signal?: AbortSignal,
): Promise<TrainingAssignment[]> {
  const queryParams = new URLSearchParams();
  if (options?.status && options.status !== "all") {
    queryParams.set("status", options.status);
  }
  if (options?.user_id) {
    queryParams.set("user_id", options.user_id);
  }
  const queryString = queryParams.toString() ? `?${queryParams.toString()}` : "";
  const url = `${getApiBaseUrl()}/v1/tenants/${encodeURIComponent(tenantId)}/lms/assignments${queryString}`;
  const res = await fetch(url, {
    method: "GET",
    headers: authHeaders(token),
    signal,
  });
  const data = await handleLmsResponse<unknown>(res);
  return validateAssignmentArray(data, tenantId);
}

export async function createTrainingAssignment(
  tenantId: string,
  token: string,
  payload: CreateAssignmentPayload,
  signal?: AbortSignal,
): Promise<TrainingAssignment> {
  const url = `${getApiBaseUrl()}/v1/tenants/${encodeURIComponent(tenantId)}/lms/assignments`;
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
    signal,
  });
  const data = await handleLmsResponse<TrainingAssignment>(res);
  if (!data || data.tenant_id !== tenantId) {
    throw new Error(`Tenant mismatch on created assignment: expected ${tenantId}`);
  }
  return data;
}

export async function fetchTrainingCompletions(
  tenantId: string,
  token: string,
  signal?: AbortSignal,
): Promise<TrainingCompletion[]> {
  const url = `${getApiBaseUrl()}/v1/tenants/${encodeURIComponent(tenantId)}/lms/completions`;
  const res = await fetch(url, {
    method: "GET",
    headers: authHeaders(token),
    signal,
  });
  const data = await handleLmsResponse<unknown>(res);
  return validateCompletionArray(data, tenantId);
}

