/**
 * Customer Demo Control Work & Evidence Pinning API Client.
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
  CreateEvidencePayload,
  CreateLinkPayload,
  CreateReviewPayload,
  InitializeWorkPayload,
  MutationReceipt,
  OwnerDirectoryResponse,
  PatchWorkPayload,
  WorkHistoryResponse,
  WorkListResponse,
} from "./control-evidence-types";

export class ServiceUnavailableError extends CustomerDemoApiError {
  constructor(detail?: string) {
    super(detail || "Service unavailable; scanner verification failed", 503, detail);
    this.name = "ServiceUnavailableError";
  }
}

export class PayloadTooLargeError extends CustomerDemoApiError {
  constructor(detail?: string) {
    super(detail || "Payload too large", 413, detail);
    this.name = "PayloadTooLargeError";
  }
}

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
    if (res.status === 503) {
      throw new ServiceUnavailableError(detail);
    }
    throw new CustomerDemoApiError(`API error: ${detail}`, res.status, detail);
  }
  return res.json() as Promise<T>;
}

export async function fetchControlWorkList(
  tenantId: string,
  token: string,
  adoptionId?: string,
  signal?: AbortSignal,
): Promise<WorkListResponse> {
  const base = getApiBaseUrl();
  const url = new URL(`${base}/v2/tenants/${encodeURIComponent(tenantId)}/customer-demo/control-work`);
  if (adoptionId) {
    url.searchParams.set("adoption_id", adoptionId);
  }

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
    signal,
  });

  return handleResponse<WorkListResponse>(res);
}

export async function fetchOwnerDirectory(
  tenantId: string,
  token: string,
  signal?: AbortSignal,
): Promise<OwnerDirectoryResponse> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v2/tenants/${encodeURIComponent(tenantId)}/customer-demo/control-work/owners`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
      signal,
    },
  );

  return handleResponse<OwnerDirectoryResponse>(res);
}

export async function initializeControlWork(
  tenantId: string,
  token: string,
  payload: InitializeWorkPayload,
  signal?: AbortSignal,
): Promise<WorkListResponse> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v2/tenants/${encodeURIComponent(tenantId)}/customer-demo/control-work/initialize`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
      signal,
    },
  );

  return handleResponse<WorkListResponse>(res);
}

export async function patchControlWork(
  tenantId: string,
  token: string,
  workId: string,
  payload: PatchWorkPayload,
  signal?: AbortSignal,
): Promise<MutationReceipt> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v2/tenants/${encodeURIComponent(tenantId)}/customer-demo/control-work/${encodeURIComponent(workId)}`,
    {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
      signal,
    },
  );

  return handleResponse<MutationReceipt>(res);
}

export async function uploadEvidenceFile(
  tenantId: string,
  token: string,
  file: File,
  signal?: AbortSignal,
): Promise<{ id: string; original_filename: string; plaintext_size_bytes: number }> {
  const base = getApiBaseUrl();
  const formData = new FormData();
  formData.append("file", file);
  formData.append("classification", "Restricted");

  const res = await fetch(
    `${base}/v1/tenants/${encodeURIComponent(tenantId)}/files`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
      signal,
    },
  );

  return handleResponse<{ id: string; original_filename: string; plaintext_size_bytes: number }>(res);
}

export async function createEvidence(
  tenantId: string,
  token: string,
  workId: string,
  payload: CreateEvidencePayload,
  signal?: AbortSignal,
): Promise<MutationReceipt> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v2/tenants/${encodeURIComponent(tenantId)}/customer-demo/control-work/${encodeURIComponent(workId)}/evidence`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
      signal,
    },
  );

  return handleResponse<MutationReceipt>(res);
}

export async function createReuseLink(
  tenantId: string,
  token: string,
  workId: string,
  payload: CreateLinkPayload,
  signal?: AbortSignal,
): Promise<MutationReceipt> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v2/tenants/${encodeURIComponent(tenantId)}/customer-demo/control-work/${encodeURIComponent(workId)}/links`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
      signal,
    },
  );

  return handleResponse<MutationReceipt>(res);
}

export async function createReview(
  tenantId: string,
  token: string,
  workId: string,
  linkId: string,
  payload: CreateReviewPayload,
  signal?: AbortSignal,
): Promise<MutationReceipt> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v2/tenants/${encodeURIComponent(tenantId)}/customer-demo/control-work/${encodeURIComponent(workId)}/links/${encodeURIComponent(linkId)}/reviews`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
      signal,
    },
  );

  return handleResponse<MutationReceipt>(res);
}

export async function fetchWorkHistory(
  tenantId: string,
  token: string,
  workId: string,
  signal?: AbortSignal,
): Promise<WorkHistoryResponse> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v2/tenants/${encodeURIComponent(tenantId)}/customer-demo/control-work/${encodeURIComponent(workId)}/history`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
      signal,
    },
  );

  return handleResponse<WorkHistoryResponse>(res);
}

export async function downloadPinnedFile(
  tenantId: string,
  token: string,
  workId: string,
  linkId: string,
  fileId: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/v2/tenants/${encodeURIComponent(tenantId)}/customer-demo/control-work/${encodeURIComponent(workId)}/links/${encodeURIComponent(linkId)}/files/${encodeURIComponent(fileId)}`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      signal,
    },
  );

  if (!res.ok) {
    let detail: string;
    try {
      const err = await res.json();
      detail = (err && (err.detail || err.message)) || res.statusText || `HTTP ${res.status}`;
    } catch {
      detail = res.statusText || `HTTP ${res.status}`;
    }
    if (res.status === 401) throw new UnauthorizedError(detail);
    if (res.status === 403) throw new ForbiddenError(detail);
    if (res.status === 404) throw new NotFoundError(detail);
    throw new CustomerDemoApiError(`Download failed: ${detail}`, res.status, detail);
  }

  return res.blob();
}
