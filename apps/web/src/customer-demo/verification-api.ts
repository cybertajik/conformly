/**
 * Typed, cancellable API client for Conformly Customer Readiness Verification Workspace (MVP-E).
 * Targets /v2/tenants/{tenant_id}/customer-demo/readiness-verifications
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
  CorrectVerificationPayload,
  IssueVerificationPayload,
  ReconcileVerificationPayload,
  ReconcileVerificationResponse,
  RevokeVerificationPayload,
  SupersedeVerificationPayload,
  SuspendVerificationPayload,
  VerificationDetail,
  VerificationHistoryResponse,
  VerificationListResponse,
  VerificationProjection,
} from "./verification-types";

export function isVerificationEnabled(): boolean {
  const flag =
    import.meta.env.VITE_ENABLE_CUSTOMER_READINESS_VERIFICATION === "true";
  const isLocalOrDevOrTest =
    Boolean(import.meta.env.DEV) ||
    import.meta.env.MODE === "test" ||
    (typeof window !== "undefined" &&
      (window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1" ||
        window.location.hostname === "::1"));
  return flag && isLocalOrDevOrTest;
}

async function handleVerificationResponse<T>(res: Response): Promise<T> {
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
    if (res.status === 404) {
      throw new NotFoundError(detail);
    }
    if (res.status === 401) {
      throw new UnauthorizedError(detail);
    }
    if (res.status === 422) {
      throw new ValidationError(detail);
    }
    throw new CustomerDemoApiError(detail, res.status, detail);
  }

  return res.json() as Promise<T>;
}

function getBaseUrl(tenantId: string): string {
  return `${getApiBaseUrl()}/v2/tenants/${encodeURIComponent(tenantId)}/customer-demo/readiness-verifications`;
}

function verificationHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/json",
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    Pragma: "no-cache",
  };
}

export async function listVerifications(
  tenantId: string,
  token: string,
  signal?: AbortSignal,
  limit: number = 50,
  offset: number = 0,
  preauditCaseId?: string,
): Promise<VerificationListResponse> {
  const safeLimit = Math.min(Math.max(1, limit), 100);
  const safeOffset = Math.max(0, offset);
  let url = `${getBaseUrl(tenantId)}?limit=${safeLimit}&offset=${safeOffset}`;
  if (preauditCaseId) {
    url += `&preaudit_case_id=${encodeURIComponent(preauditCaseId)}`;
  }
  const res = await fetch(url, {
    method: "GET",
    headers: verificationHeaders(token),
    signal,
  });
  return handleVerificationResponse<VerificationListResponse>(res);
}

export async function getVerification(
  tenantId: string,
  verificationId: string,
  token: string,
  signal?: AbortSignal,
): Promise<VerificationDetail> {
  const url = `${getBaseUrl(tenantId)}/${encodeURIComponent(verificationId)}`;
  const res = await fetch(url, {
    method: "GET",
    headers: verificationHeaders(token),
    signal,
  });
  return handleVerificationResponse<VerificationDetail>(res);
}

export async function getVerificationProjection(
  tenantId: string,
  verificationId: string,
  token: string,
  signal?: AbortSignal,
): Promise<VerificationProjection> {
  const url = `${getBaseUrl(tenantId)}/${encodeURIComponent(verificationId)}/projection`;
  const res = await fetch(url, {
    method: "GET",
    headers: verificationHeaders(token),
    signal,
  });
  return handleVerificationResponse<VerificationProjection>(res);
}

export async function getVerificationHistory(
  tenantId: string,
  verificationId: string,
  token: string,
  signal?: AbortSignal,
): Promise<VerificationHistoryResponse> {
  const url = `${getBaseUrl(tenantId)}/${encodeURIComponent(verificationId)}/history`;
  const res = await fetch(url, {
    method: "GET",
    headers: verificationHeaders(token),
    signal,
  });
  return handleVerificationResponse<VerificationHistoryResponse>(res);
}

export async function issueVerification(
  tenantId: string,
  payload: IssueVerificationPayload,
  token: string,
  signal?: AbortSignal,
): Promise<VerificationDetail> {
  const url = getBaseUrl(tenantId);
  const res = await fetch(url, {
    method: "POST",
    headers: {
      ...verificationHeaders(token),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });
  return handleVerificationResponse<VerificationDetail>(res);
}

export async function suspendVerification(
  tenantId: string,
  verificationId: string,
  payload: SuspendVerificationPayload,
  token: string,
  signal?: AbortSignal,
): Promise<VerificationDetail> {
  const url = `${getBaseUrl(tenantId)}/${encodeURIComponent(verificationId)}/suspend`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      ...verificationHeaders(token),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });
  return handleVerificationResponse<VerificationDetail>(res);
}

export async function revokeVerification(
  tenantId: string,
  verificationId: string,
  payload: RevokeVerificationPayload,
  token: string,
  signal?: AbortSignal,
): Promise<VerificationDetail> {
  const url = `${getBaseUrl(tenantId)}/${encodeURIComponent(verificationId)}/revoke`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      ...verificationHeaders(token),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });
  return handleVerificationResponse<VerificationDetail>(res);
}

export async function correctVerification(
  tenantId: string,
  verificationId: string,
  payload: CorrectVerificationPayload,
  token: string,
  signal?: AbortSignal,
): Promise<VerificationDetail> {
  const url = `${getBaseUrl(tenantId)}/${encodeURIComponent(verificationId)}/correct`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      ...verificationHeaders(token),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });
  return handleVerificationResponse<VerificationDetail>(res);
}

export async function supersedeVerification(
  tenantId: string,
  verificationId: string,
  payload: SupersedeVerificationPayload,
  token: string,
  signal?: AbortSignal,
): Promise<VerificationDetail> {
  const url = `${getBaseUrl(tenantId)}/${encodeURIComponent(verificationId)}/supersede`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      ...verificationHeaders(token),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });
  return handleVerificationResponse<VerificationDetail>(res);
}

export async function reconcileVerifications(
  tenantId: string,
  payload: ReconcileVerificationPayload = {},
  token: string,
  signal?: AbortSignal,
): Promise<ReconcileVerificationResponse> {
  const url = `${getBaseUrl(tenantId)}/reconcile`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      ...verificationHeaders(token),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });
  return handleVerificationResponse<ReconcileVerificationResponse>(res);
}
