/**
 * API client for the synthetic staff catalog demo using bearer authentication.
 */

import { CatalogDemoGraphResponse, CatalogDemoSessionResponse } from "./types";

export class CatalogApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
  ) {
    super(message);
    this.name = "CatalogApiError";
  }
}

/**
 * Determine the explicit /v2 root for catalog demo requests.
 * Uses VITE_CATALOG_DEMO_API_BASE_URL if configured; otherwise appends /v2 exactly once
 * to VITE_API_BASE_URL (defaulting to http://localhost:8000).
 */
export function getApiBaseUrl(): string {
  const customBase = import.meta.env.VITE_CATALOG_DEMO_API_BASE_URL;
  if (customBase && customBase.trim()) {
    return customBase.trim().replace(/\/+$/, "");
  }
  const rawBase = import.meta.env.VITE_API_BASE_URL;
  const apiBase = (rawBase && rawBase.trim() ? rawBase.trim() : "http://localhost:8000").replace(/\/+$/, "");
  if (apiBase.endsWith("/v2")) {
    return apiBase;
  }
  return `${apiBase}/v2`;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = "Request failed";
    let code: string | undefined;
    try {
      const errJson = await res.json();
      if (errJson && typeof errJson.detail === "string") {
        detail = errJson.detail;
      } else if (errJson && typeof errJson.message === "string") {
        detail = errJson.message;
      }
      code = errJson?.code;
    } catch {
      detail = res.statusText || `HTTP ${res.status}`;
    }

    if (res.status === 401) {
      throw new CatalogApiError(detail || "Session expired or authentication failed", 401, code);
    }
    if (res.status === 403) {
      throw new CatalogApiError(detail || "Access denied: Platform administrator status required", 403, code);
    }
    if (res.status === 404) {
      throw new CatalogApiError("Catalog demo graph unavailable or endpoint not found", 404, code);
    }
    if (res.status === 503) {
      throw new CatalogApiError("Catalog service or audit infrastructure temporarily unavailable", 503, code);
    }
    throw new CatalogApiError(detail, res.status, code);
  }
  if (res.status === 204) {
    return undefined as unknown as T;
  }
  return res.json() as Promise<T>;
}

export async function bootstrapSession(token: string, signal?: AbortSignal): Promise<CatalogDemoSessionResponse> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/catalog-demo/session`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token.trim()}`,
    },
    signal,
  });
  return handleResponse<CatalogDemoSessionResponse>(res);
}

export async function verifySession(token: string, signal?: AbortSignal): Promise<CatalogDemoSessionResponse> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/catalog-demo/session`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token.trim()}`,
    },
    signal,
  });
  return handleResponse<CatalogDemoSessionResponse>(res);
}

export async function revokeSession(token?: string | null, signal?: AbortSignal): Promise<void> {
  const cleanToken = (token || "").trim();
  if (!cleanToken) {
    return;
  }
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/catalog-demo/session`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${cleanToken}`,
    },
    signal,
  });
  await handleResponse<void>(res);
}

export async function fetchCatalogGraph(token: string, signal?: AbortSignal): Promise<CatalogDemoGraphResponse> {
  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/catalog-demo/catalog`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token.trim()}`,
    },
    signal,
  });
  return handleResponse<CatalogDemoGraphResponse>(res);
}
