/**
 * Typed, cancellable API client for Conformly Customer Pre-audit Workspace (MVP-D).
 * Targets /v2/tenants/{tenant_id}/customer-demo/preaudits
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
  ApprovePreauditPayload,
  CancelPreauditPayload,
  CreatePreauditPayload,
  DownloadPreauditReportPayload,
  FreezeScopePayload,
  PreauditActor,
  PreauditActorsResponse,
  PreauditCase,
  PreauditHistoryResponse,
  PreauditListResponse,
  PreauditReportDownloadResult,
  ReviewDecisionPayload,
  SubmitReviewPayload,
} from "./preaudit-types";

export function isPreauditEnabled(): boolean {
  const flag = import.meta.env.VITE_ENABLE_CUSTOMER_PREAUDIT === "true";
  const isLocalOrDevOrTest =
    Boolean(import.meta.env.DEV) ||
    import.meta.env.MODE === "test" ||
    (typeof window !== "undefined" &&
      (window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1" ||
        window.location.hostname === "::1"));
  return flag && isLocalOrDevOrTest;
}

async function handlePreauditResponse<T>(res: Response): Promise<T> {
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
    throw new CustomerDemoApiError(
      detail || `Request failed with status ${res.status}`,
      res.status,
      detail,
    );
  }

  return (await res.json()) as T;
}

function preauditHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    Accept: "application/json",
  };
}

export async function fetchPreauditActors(
  tenantId: string,
  token: string,
  signal?: AbortSignal,
): Promise<PreauditActor[]> {
  const base = getApiBaseUrl();
  const url = `${base}/v2/tenants/${tenantId}/customer-demo/preaudits/actors`;
  const res = await fetch(url, {
    method: "GET",
    headers: preauditHeaders(token),
    signal,
  });
  const data = await handlePreauditResponse<PreauditActorsResponse>(res);
  return data.actors;
}

export async function listPreauditCases(
  tenantId: string,
  token: string,
  signal?: AbortSignal,
  limit: number = 50,
  offset: number = 0,
): Promise<PreauditListResponse> {
  const base = getApiBaseUrl();
  const safeLimit = Math.min(Math.max(1, limit), 100);
  const safeOffset = Math.max(0, offset);
  const url = `${base}/v2/tenants/${tenantId}/customer-demo/preaudits?limit=${safeLimit}&offset=${safeOffset}`;
  const res = await fetch(url, {
    method: "GET",
    headers: preauditHeaders(token),
    signal,
  });
  return handlePreauditResponse<PreauditListResponse>(res);
}

export async function getPreauditCase(
  tenantId: string,
  caseId: string,
  token: string,
  signal?: AbortSignal,
): Promise<PreauditCase> {
  const base = getApiBaseUrl();
  const url = `${base}/v2/tenants/${tenantId}/customer-demo/preaudits/${caseId}`;
  const res = await fetch(url, {
    method: "GET",
    headers: preauditHeaders(token),
    signal,
  });
  return handlePreauditResponse<PreauditCase>(res);
}

export async function createPreauditCase(
  tenantId: string,
  payload: CreatePreauditPayload,
  token: string,
  signal?: AbortSignal,
): Promise<PreauditCase> {
  const base = getApiBaseUrl();
  const url = `${base}/v2/tenants/${tenantId}/customer-demo/preaudits`;
  const res = await fetch(url, {
    method: "POST",
    headers: preauditHeaders(token),
    body: JSON.stringify(payload),
    signal,
  });
  return handlePreauditResponse<PreauditCase>(res);
}

export async function freezePreauditScope(
  tenantId: string,
  caseId: string,
  payload: FreezeScopePayload,
  token: string,
  signal?: AbortSignal,
): Promise<PreauditCase> {
  const base = getApiBaseUrl();
  const url = `${base}/v2/tenants/${tenantId}/customer-demo/preaudits/${caseId}/freeze`;
  const res = await fetch(url, {
    method: "POST",
    headers: preauditHeaders(token),
    body: JSON.stringify(payload),
    signal,
  });
  return handlePreauditResponse<PreauditCase>(res);
}

export async function submitPreauditReview(
  tenantId: string,
  caseId: string,
  payload: SubmitReviewPayload,
  token: string,
  signal?: AbortSignal,
): Promise<PreauditCase> {
  const base = getApiBaseUrl();
  const url = `${base}/v2/tenants/${tenantId}/customer-demo/preaudits/${caseId}/submit`;
  const res = await fetch(url, {
    method: "POST",
    headers: preauditHeaders(token),
    body: JSON.stringify(payload),
    signal,
  });
  return handlePreauditResponse<PreauditCase>(res);
}

export async function recordReviewDecision(
  tenantId: string,
  caseId: string,
  payload: ReviewDecisionPayload,
  token: string,
  signal?: AbortSignal,
): Promise<PreauditCase> {
  const base = getApiBaseUrl();
  const url = `${base}/v2/tenants/${tenantId}/customer-demo/preaudits/${caseId}/review`;
  const res = await fetch(url, {
    method: "POST",
    headers: preauditHeaders(token),
    body: JSON.stringify(payload),
    signal,
  });
  return handlePreauditResponse<PreauditCase>(res);
}

export async function approvePreauditCase(
  tenantId: string,
  caseId: string,
  payload: ApprovePreauditPayload,
  token: string,
  signal?: AbortSignal,
): Promise<PreauditCase> {
  const base = getApiBaseUrl();
  const url = `${base}/v2/tenants/${tenantId}/customer-demo/preaudits/${caseId}/approve`;
  const res = await fetch(url, {
    method: "POST",
    headers: preauditHeaders(token),
    body: JSON.stringify(payload),
    signal,
  });
  return handlePreauditResponse<PreauditCase>(res);
}

export async function cancelPreauditCase(
  tenantId: string,
  caseId: string,
  payload: CancelPreauditPayload,
  token: string,
  signal?: AbortSignal,
): Promise<PreauditCase> {
  const base = getApiBaseUrl();
  const url = `${base}/v2/tenants/${tenantId}/customer-demo/preaudits/${caseId}/cancel`;
  const res = await fetch(url, {
    method: "POST",
    headers: preauditHeaders(token),
    body: JSON.stringify(payload),
    signal,
  });
  return handlePreauditResponse<PreauditCase>(res);
}

export async function getPreauditHistory(
  tenantId: string,
  caseId: string,
  token: string,
  signal?: AbortSignal,
): Promise<PreauditHistoryResponse> {
  const base = getApiBaseUrl();
  const url = `${base}/v2/tenants/${tenantId}/customer-demo/preaudits/${caseId}/history`;
  const res = await fetch(url, {
    method: "GET",
    headers: preauditHeaders(token),
    signal,
  });
  return handlePreauditResponse<PreauditHistoryResponse>(res);
}

export const MAX_PREAUDIT_REPORT_BYTES = 8 * 1024 * 1024; // 8 MiB bound

async function boundedBody(response: Response, signal?: AbortSignal): Promise<Uint8Array> {
  const length = response.headers.get("content-length");
  if (length !== null && (!/^[0-9]+$/.test(length) || Number(length) > MAX_PREAUDIT_REPORT_BYTES)) {
    throw new CustomerDemoApiError("Invalid or excessive report Content-Length", 422);
  }
  if (!response.body) {
    throw new CustomerDemoApiError("Missing response body stream", 500);
  }
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  const cancel = () => {
    void reader.cancel().catch(() => undefined);
  };
  signal?.addEventListener("abort", cancel, { once: true });
  try {
    while (true) {
      if (signal?.aborted) throw new DOMException("Request cancelled", "AbortError");
      const next = await reader.read();
      if (signal?.aborted) throw new DOMException("Request cancelled", "AbortError");
      if (next.done) break;
      size += next.value.byteLength;
      if (size > MAX_PREAUDIT_REPORT_BYTES) {
        throw new CustomerDemoApiError("Report archive exceeded finite 8 MiB bound", 413);
      }
      chunks.push(next.value);
    }
  } finally {
    signal?.removeEventListener("abort", cancel);
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
  if (!size || (length !== null && Number(length) !== size)) {
    throw new CustomerDemoApiError("Incomplete or zero-length report stream", 422);
  }
  const result = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return result;
}

export async function downloadPreauditReport(
  tenantId: string,
  caseId: string,
  payload: DownloadPreauditReportPayload,
  token: string,
  signal?: AbortSignal,
): Promise<PreauditReportDownloadResult> {
  if (signal?.aborted) throw new DOMException("Request cancelled", "AbortError");
  if (!globalThis.crypto?.subtle) {
    throw new CustomerDemoApiError("Secure cryptography API unavailable for report verification", 500);
  }
  if (!payload.snapshot_id || !payload.snapshot_id.trim()) {
    throw new CustomerDemoApiError("Missing required snapshot_id for report download", 422);
  }
  if (!payload.expected_snapshot_digest || !payload.expected_snapshot_digest.trim()) {
    throw new CustomerDemoApiError("Missing required expected_snapshot_digest for report verification", 422);
  }

  const base = getApiBaseUrl();
  const url = `${base}/v2/tenants/${tenantId}/customer-demo/preaudits/${caseId}/report/download`;

  // Server DTO forbids extra fields (extra="forbid").
  // Send ONLY the server-admitted DTO fields: expected_revision and snapshot_id.
  const serverRequestBody = {
    expected_revision: payload.expected_revision,
    snapshot_id: payload.snapshot_id,
  };

  const res = await fetch(url, {
    method: "POST",
    headers: {
      ...preauditHeaders(token),
      Accept: "application/zip",
    },
    body: JSON.stringify(serverRequestBody),
    cache: "no-store",
    signal,
  });

  if (!res.ok) {
    await handlePreauditResponse(res);
  }

  // Require actual case header; never substitute request values for missing response proof
  const preauditId = res.headers.get("x-preaudit-id");
  if (!preauditId) {
    await res.body?.cancel().catch(() => undefined);
    throw new CustomerDemoApiError("Missing X-Preaudit-Id header in report response", 422);
  }
  if (preauditId.toLowerCase() !== caseId.toLowerCase()) {
    await res.body?.cancel().catch(() => undefined);
    throw new CustomerDemoApiError("Mismatched pre-audit ID in response headers", res.status);
  }

  const contentType = res.headers.get("content-type")?.split(";")[0].trim().toLowerCase();
  if (contentType !== "application/zip") {
    await res.body?.cancel().catch(() => undefined);
    throw new CustomerDemoApiError("Invalid content type; expected application/zip", res.status);
  }

  const cacheControl = res.headers.get("cache-control") || "";
  if (!cacheControl.includes("no-store")) {
    await res.body?.cancel().catch(() => undefined);
    throw new CustomerDemoApiError("Missing private no-store cache policy", res.status);
  }

  const expectedSha = res.headers.get("x-report-sha256");
  if (!expectedSha || !/^[0-9a-f]{64}$/i.test(expectedSha)) {
    await res.body?.cancel().catch(() => undefined);
    throw new CustomerDemoApiError("Missing or malformed X-Report-SHA256 header", res.status);
  }

  // Require actual snapshot digest header; never substitute or skip verification
  const snapshotDigest = res.headers.get("x-preaudit-snapshot-digest");
  if (!snapshotDigest) {
    await res.body?.cancel().catch(() => undefined);
    throw new CustomerDemoApiError("Missing X-Preaudit-Snapshot-Digest header in report response", 422);
  }
  if (snapshotDigest.toLowerCase() !== payload.expected_snapshot_digest.toLowerCase()) {
    await res.body?.cancel().catch(() => undefined);
    throw new CustomerDemoApiError("Mismatched snapshot digest in report header", 422);
  }

  let filename = `preaudit-report-${caseId.slice(0, 8)}.zip`;
  const cd = res.headers.get("content-disposition");
  if (cd) {
    if (!cd.toLowerCase().startsWith("attachment")) {
      await res.body?.cancel().catch(() => undefined);
      throw new CustomerDemoApiError("Invalid Content-Disposition; must be attachment", 422);
    }
    const match = /filename\*?=['"]?(?:UTF-\d['"]*)?([^;\r\n"']*)['"]?/i.exec(cd);
    if (match && match[1]) {
      const decoded = decodeURIComponent(match[1]).trim();
      if (decoded.includes("..") || decoded.includes("/") || decoded.includes("\\")) {
        await res.body?.cancel().catch(() => undefined);
        throw new CustomerDemoApiError("Unsafe filename in Content-Disposition", 422);
      }
      filename = decoded;
    }
  }

  let bytes: Uint8Array;
  try {
    bytes = await boundedBody(res, signal);
  } catch (err) {
    await res.body?.cancel().catch(() => undefined);
    throw err;
  }

  if (signal?.aborted) throw new DOMException("Request cancelled", "AbortError");
  const hashBuffer = await globalThis.crypto.subtle.digest("SHA-256", bytes.buffer as ArrayBuffer);
  const actualSha = Array.from(new Uint8Array(hashBuffer), (b) => b.toString(16).padStart(2, "0")).join("");
  if (actualSha.toLowerCase() !== expectedSha.toLowerCase()) {
    throw new CustomerDemoApiError("Report archive SHA-256 integrity verification failed", 422);
  }

  const blob = new Blob([bytes.buffer as ArrayBuffer], { type: "application/zip" });
  return {
    blob,
    filename,
    preauditId,
    snapshotDigest,
    sha256: actualSha,
  };
}

