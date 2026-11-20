export function isCustomerDemoEnabled(): boolean {
  const flag = import.meta.env.VITE_ENABLE_CUSTOMER_DEMO === "true";
  const isLocalOrDevOrTest =
    Boolean(import.meta.env.DEV) ||
    import.meta.env.MODE === "test" ||
    (typeof window !== "undefined" &&
      (window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1" ||
        window.location.hostname === "::1"));
  return flag && isLocalOrDevOrTest;
}

/**
 * Customer Demo API client for WP-09 Customer Onboarding Vertical Slice.
 */

import {
  AdoptInput,
  AdoptionReceipt,
  AnswersData,
  EvaluateInput,
  EvaluationData,
  SaveAnswersInput,
  WorkspaceData,
} from "./types";

export class CustomerDemoApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: string,
  ) {
    super(message);
    this.name = "CustomerDemoApiError";
  }
}

export class ConflictError extends CustomerDemoApiError {
  constructor(detail?: string) {
    super(detail || "Entity changed; reload and retry", 409, detail);
    this.name = "ConflictError";
  }
}

export class ForbiddenError extends CustomerDemoApiError {
  constructor(detail?: string) {
    super(detail || "Customer demo access denied", 403, detail);
    this.name = "ForbiddenError";
  }
}

export class UnauthorizedError extends CustomerDemoApiError {
  constructor(detail?: string) {
    super(detail || "Unauthorized", 401, detail);
    this.name = "UnauthorizedError";
  }
}

export class NotFoundError extends CustomerDemoApiError {
  constructor(detail?: string) {
    super(detail || "Not Found", 404, detail);
    this.name = "NotFoundError";
  }
}

export class ValidationError extends CustomerDemoApiError {
  constructor(detail?: string) {
    super(detail || "Validation Error", 422, detail);
    this.name = "ValidationError";
  }
}

export function getApiBaseUrl(): string {
  const raw = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
  return raw.replace(/\/+$/, "");
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = "";
    try {
      const err = await res.json();
      if (err && typeof err.detail === "string") {
        detail = err.detail;
      } else if (err && typeof err.message === "string") {
        detail = err.message;
      }
    } catch {
      detail = res.statusText || `HTTP ${res.status}`;
    }

    if (res.status === 409) {
      throw new ConflictError(detail);
    }
    if (res.status === 403) {
      throw new ForbiddenError(detail);
    }
    if (res.status === 401) {
      throw new UnauthorizedError(detail);
    }
    if (res.status === 404) {
      throw new NotFoundError(detail);
    }
    if (res.status === 422) {
      throw new ValidationError(detail);
    }
    throw new CustomerDemoApiError(detail || `Request failed with status ${res.status}`, res.status, detail);
  }

  return (await res.json()) as T;
}

export async function fetchWorkspace(
  tenantId: string,
  token: string,
  signal?: AbortSignal,
): Promise<WorkspaceData> {
  const base = getApiBaseUrl();
  const url = `${base}/v2/tenants/${encodeURIComponent(tenantId)}/customer-demo/workspace`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
    signal,
  });
  return handleResponse<WorkspaceData>(res);
}

export async function saveAnswers(
  tenantId: string,
  token: string,
  input: SaveAnswersInput,
  signal?: AbortSignal,
): Promise<AnswersData> {
  const base = getApiBaseUrl();
  const url = `${base}/v2/tenants/${encodeURIComponent(tenantId)}/customer-demo/answers`;
  const bodyStr = JSON.stringify(input);

  const res = await fetch(url, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: bodyStr,
    signal,
  });
  return handleResponse<AnswersData>(res);
}

export async function evaluateAnswers(
  tenantId: string,
  token: string,
  input: EvaluateInput,
  signal?: AbortSignal,
): Promise<EvaluationData> {
  const base = getApiBaseUrl();
  const url = `${base}/v2/tenants/${encodeURIComponent(tenantId)}/customer-demo/evaluations`;
  const bodyStr = JSON.stringify(input);

  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: bodyStr,
    signal,
  });
  return handleResponse<EvaluationData>(res);
}

export async function adoptEvaluation(
  tenantId: string,
  token: string,
  input: AdoptInput,
  signal?: AbortSignal,
): Promise<AdoptionReceipt> {
  const base = getApiBaseUrl();
  const url = `${base}/v2/tenants/${encodeURIComponent(tenantId)}/customer-demo/adoptions`;
  const bodyStr = JSON.stringify(input);

  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: bodyStr,
    signal,
  });
  return handleResponse<AdoptionReceipt>(res);
}
