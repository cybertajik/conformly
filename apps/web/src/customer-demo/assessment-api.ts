/**
 * Customer Demo Assessment & Audit Readiness API Client.
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
  AssessmentCreatePayload,
  AssessmentHistoryResponse,
  AssessmentReceipt,
  AssessmentWorkListResponse,
  FindingPatchPayload,
  Procedure,
  RetestCreatePayload,
} from "./assessment-types";
import { PayloadTooLargeError } from "./control-evidence-api";

async function handleResponse<T>(res: Response): Promise<T> {
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

    if (res.status === 401) {
      throw new UnauthorizedError(detail);
    }
    if (res.status === 403) {
      throw new ForbiddenError(detail);
    }
    if (res.status === 404) {
      throw new NotFoundError(detail);
    }
    if (res.status === 409) {
      throw new ConflictError(detail);
    }
    if (res.status === 413) {
      throw new PayloadTooLargeError(detail);
    }
    if (res.status === 422) {
      throw new ValidationError(detail);
    }
    throw new CustomerDemoApiError(detail, res.status, detail);
  }

  return (await res.json()) as T;
}

export async function fetchAssessmentWorkList(
  tenantId: string,
  token: string,
  signal?: AbortSignal
): Promise<AssessmentWorkListResponse> {
  const base = getApiBaseUrl();
  const res = await fetch(`${base}/v2/tenants/${tenantId}/customer-demo/assessment-work`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
    signal,
  });
  return handleResponse<AssessmentWorkListResponse>(res);
}

export async function fetchProcedure(
  tenantId: string,
  token: string,
  workId: string,
  signal?: AbortSignal
): Promise<Procedure> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v2/tenants/${tenantId}/customer-demo/assessment-work/${workId}/procedure`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
      signal,
    }
  );
  return handleResponse<Procedure>(res);
}

export async function fetchAssessmentHistory(
  tenantId: string,
  token: string,
  workId: string,
  signal?: AbortSignal
): Promise<AssessmentHistoryResponse> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v2/tenants/${tenantId}/customer-demo/assessment-work/${workId}/history`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
      signal,
    }
  );
  return handleResponse<AssessmentHistoryResponse>(res);
}

export async function recordAssessment(
  tenantId: string,
  token: string,
  workId: string,
  payload: AssessmentCreatePayload,
  signal?: AbortSignal
): Promise<AssessmentReceipt> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v2/tenants/${tenantId}/customer-demo/assessment-work/${workId}/assessments`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
      signal,
    }
  );
  return handleResponse<AssessmentReceipt>(res);
}

export async function updateFinding(
  tenantId: string,
  token: string,
  findingId: string,
  payload: FindingPatchPayload,
  signal?: AbortSignal
): Promise<AssessmentReceipt> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v2/tenants/${tenantId}/customer-demo/assessment-work/findings/${findingId}`,
    {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
      signal,
    }
  );
  return handleResponse<AssessmentReceipt>(res);
}

export async function recordRetest(
  tenantId: string,
  token: string,
  workId: string,
  payload: RetestCreatePayload,
  signal?: AbortSignal
): Promise<AssessmentReceipt> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v2/tenants/${tenantId}/customer-demo/assessment-work/${workId}/retests`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
      signal,
    }
  );
  return handleResponse<AssessmentReceipt>(res);
}
