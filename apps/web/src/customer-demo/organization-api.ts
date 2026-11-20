/**
 * Typed, cancellable API client for Organization, Memberships, and Entitlements.
 * Conforms strictly to existing backend API endpoints and validates response envelopes.
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
  BusinessUnit,
  BusinessUnitCreateInput,
  LegalEntity,
  LegalEntityCreateInput,
  Location,
  LocationCreateInput,
  Membership,
  TenantEntitlement,
} from "./organization-types";

async function handleOrgResponse<T>(res: Response): Promise<T> {
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
    if (res.status === 422) {
      throw new ValidationError(detail);
    }
    throw new CustomerDemoApiError(detail, res.status, detail);
  }

  try {
    return (await res.json()) as T;
  } catch (err: unknown) {
    throw new CustomerDemoApiError(
      `Malformed JSON response from server: ${err instanceof Error ? err.message : String(err)}`,
      res.status,
      "MALFORMED_JSON"
    );
  }
}

function assertObject(data: unknown, context: string): Record<string, unknown> {
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new CustomerDemoApiError(
      `Expected JSON object for ${context}, got ${data === null ? "null" : Array.isArray(data) ? "array" : typeof data}`,
      502,
      "INVALID_RESPONSE_SHAPE"
    );
  }
  return data as Record<string, unknown>;
}

function assertArray(data: unknown, context: string): unknown[] {
  if (!Array.isArray(data)) {
    throw new CustomerDemoApiError(
      `Expected JSON array for ${context}, got ${data === null ? "null" : typeof data}`,
      502,
      "INVALID_RESPONSE_SHAPE"
    );
  }
  return data;
}

function validateLegalEntity(item: unknown, expectedTenantId: string, context = "legal entity"): LegalEntity {
  const obj = assertObject(item, context);
  if (typeof obj.id !== "string" || !obj.id.trim()) {
    throw new CustomerDemoApiError(`Missing or invalid id in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (typeof obj.tenant_id !== "string") {
    throw new CustomerDemoApiError(`Missing or invalid tenant_id in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (obj.tenant_id !== expectedTenantId) {
    throw new CustomerDemoApiError(
      `Cross-tenant data violation in ${context}: expected tenant ${expectedTenantId}, got ${obj.tenant_id}`,
      502,
      "CROSS_TENANT_VIOLATION"
    );
  }
  if (typeof obj.name !== "string" || !obj.name.trim()) {
    throw new CustomerDemoApiError(`Missing or invalid name in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (typeof obj.country !== "string") {
    throw new CustomerDemoApiError(`Missing or invalid country in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (typeof obj.is_primary !== "boolean") {
    throw new CustomerDemoApiError(`Missing or invalid is_primary in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }

  return {
    id: obj.id,
    tenant_id: obj.tenant_id,
    name: obj.name,
    registration_number: typeof obj.registration_number === "string" ? obj.registration_number : null,
    country: obj.country,
    is_primary: obj.is_primary,
    created_at: typeof obj.created_at === "string" ? obj.created_at : undefined,
  };
}

function validateBusinessUnit(
  item: unknown,
  expectedTenantId: string,
  expectedLegalEntityId?: string,
  context = "business unit"
): BusinessUnit {
  const obj = assertObject(item, context);
  if (typeof obj.id !== "string" || !obj.id.trim()) {
    throw new CustomerDemoApiError(`Missing or invalid id in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (typeof obj.tenant_id !== "string") {
    throw new CustomerDemoApiError(`Missing or invalid tenant_id in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (obj.tenant_id !== expectedTenantId) {
    throw new CustomerDemoApiError(
      `Cross-tenant data violation in ${context}: expected tenant ${expectedTenantId}, got ${obj.tenant_id}`,
      502,
      "CROSS_TENANT_VIOLATION"
    );
  }
  if (typeof obj.legal_entity_id !== "string" || !obj.legal_entity_id.trim()) {
    throw new CustomerDemoApiError(`Missing or invalid legal_entity_id in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (expectedLegalEntityId && obj.legal_entity_id !== expectedLegalEntityId) {
    throw new CustomerDemoApiError(
      `Entity mismatch in ${context}: expected entity ${expectedLegalEntityId}, got ${obj.legal_entity_id}`,
      502,
      "ENTITY_MISMATCH"
    );
  }
  if (typeof obj.name !== "string" || !obj.name.trim()) {
    throw new CustomerDemoApiError(`Missing or invalid name in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }

  return {
    id: obj.id,
    tenant_id: obj.tenant_id,
    legal_entity_id: obj.legal_entity_id,
    name: obj.name,
    code: typeof obj.code === "string" ? obj.code : null,
    created_at: typeof obj.created_at === "string" ? obj.created_at : undefined,
  };
}

function validateLocation(
  item: unknown,
  expectedTenantId: string,
  expectedLegalEntityId?: string,
  context = "location"
): Location {
  const obj = assertObject(item, context);
  if (typeof obj.id !== "string" || !obj.id.trim()) {
    throw new CustomerDemoApiError(`Missing or invalid id in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (typeof obj.tenant_id !== "string") {
    throw new CustomerDemoApiError(`Missing or invalid tenant_id in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (obj.tenant_id !== expectedTenantId) {
    throw new CustomerDemoApiError(
      `Cross-tenant data violation in ${context}: expected tenant ${expectedTenantId}, got ${obj.tenant_id}`,
      502,
      "CROSS_TENANT_VIOLATION"
    );
  }
  if (typeof obj.legal_entity_id !== "string" || !obj.legal_entity_id.trim()) {
    throw new CustomerDemoApiError(`Missing or invalid legal_entity_id in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (expectedLegalEntityId && obj.legal_entity_id !== expectedLegalEntityId) {
    throw new CustomerDemoApiError(
      `Entity mismatch in ${context}: expected entity ${expectedLegalEntityId}, got ${obj.legal_entity_id}`,
      502,
      "ENTITY_MISMATCH"
    );
  }
  if (typeof obj.name !== "string" || !obj.name.trim()) {
    throw new CustomerDemoApiError(`Missing or invalid name in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (typeof obj.country !== "string") {
    throw new CustomerDemoApiError(`Missing or invalid country in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (typeof obj.city !== "string" || !obj.city.trim()) {
    throw new CustomerDemoApiError(`Missing or invalid city in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }

  return {
    id: obj.id,
    tenant_id: obj.tenant_id,
    legal_entity_id: obj.legal_entity_id,
    name: obj.name,
    country: obj.country,
    city: obj.city,
    address: typeof obj.address === "string" ? obj.address : null,
    created_at: typeof obj.created_at === "string" ? obj.created_at : undefined,
  };
}

function validateMembership(item: unknown, context = "membership"): Membership {
  const obj = assertObject(item, context);
  if (typeof obj.id !== "string" || !obj.id.trim()) {
    throw new CustomerDemoApiError(`Missing or invalid id in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (typeof obj.user_id !== "string" || !obj.user_id.trim()) {
    throw new CustomerDemoApiError(`Missing or invalid user_id in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (typeof obj.email !== "string" || !obj.email.trim()) {
    throw new CustomerDemoApiError(`Missing or invalid email in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (typeof obj.role !== "string") {
    throw new CustomerDemoApiError(`Missing or invalid role in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }
  if (typeof obj.status !== "string") {
    throw new CustomerDemoApiError(`Missing or invalid status in ${context}`, 502, "INVALID_RESPONSE_SHAPE");
  }

  return {
    id: obj.id,
    user_id: obj.user_id,
    email: obj.email,
    display_name: typeof obj.display_name === "string" ? obj.display_name : obj.email,
    role: obj.role,
    status: obj.status,
    tenant_id: typeof obj.tenant_id === "string" ? obj.tenant_id : undefined,
    created_at: typeof obj.created_at === "string" ? obj.created_at : undefined,
  };
}

function validateTenantEntitlement(data: unknown, expectedTenantId: string): TenantEntitlement {
  const obj = assertObject(data, "tenant entitlement");
  if (typeof obj.id !== "string" || !obj.id.trim()) {
    throw new CustomerDemoApiError("Missing or invalid id in tenant entitlement", 502, "INVALID_RESPONSE_SHAPE");
  }
  if (typeof obj.tenant_id !== "string") {
    throw new CustomerDemoApiError("Missing or invalid tenant_id in tenant entitlement", 502, "INVALID_RESPONSE_SHAPE");
  }
  if (obj.tenant_id !== expectedTenantId) {
    throw new CustomerDemoApiError(
      `Cross-tenant data violation in entitlement: expected tenant ${expectedTenantId}, got ${obj.tenant_id}`,
      502,
      "CROSS_TENANT_VIOLATION"
    );
  }
  if (typeof obj.plan_code !== "string" || !obj.plan_code.trim()) {
    throw new CustomerDemoApiError("Missing or invalid plan_code in tenant entitlement", 502, "INVALID_RESPONSE_SHAPE");
  }
  if (!Array.isArray(obj.enabled_modules)) {
    throw new CustomerDemoApiError("Missing or invalid enabled_modules in tenant entitlement", 502, "INVALID_RESPONSE_SHAPE");
  }
  if (typeof obj.max_members !== "number") {
    throw new CustomerDemoApiError("Missing or invalid max_members in tenant entitlement", 502, "INVALID_RESPONSE_SHAPE");
  }
  if (typeof obj.max_storage_bytes !== "number") {
    throw new CustomerDemoApiError("Missing or invalid max_storage_bytes in tenant entitlement", 502, "INVALID_RESPONSE_SHAPE");
  }

  return {
    id: obj.id,
    tenant_id: obj.tenant_id,
    plan_code: obj.plan_code,
    enabled_modules: obj.enabled_modules.map(String),
    max_members: obj.max_members,
    max_storage_bytes: obj.max_storage_bytes,
    allowed_framework_slugs: Array.isArray(obj.allowed_framework_slugs) ? obj.allowed_framework_slugs.map(String) : [],
    effective_from: typeof obj.effective_from === "string" ? obj.effective_from : new Date().toISOString(),
    effective_until: typeof obj.effective_until === "string" ? obj.effective_until : null,
  };
}

export async function fetchLegalEntities(
  tenantId: string,
  token: string,
  signal?: AbortSignal
): Promise<LegalEntity[]> {
  const url = `${getApiBaseUrl()}/v1/tenants/${encodeURIComponent(tenantId)}/organization/legal-entities`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
    signal,
  });
  const raw = await handleOrgResponse<unknown>(res);
  const arr = assertArray(raw, "legal entities list");
  return arr.map((item, idx) => validateLegalEntity(item, tenantId, `legal entity item [${idx}]`));
}

export async function createLegalEntity(
  tenantId: string,
  token: string,
  input: LegalEntityCreateInput,
  signal?: AbortSignal
): Promise<LegalEntity> {
  const url = `${getApiBaseUrl()}/v1/tenants/${encodeURIComponent(tenantId)}/organization/legal-entities`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      name: input.name.trim(),
      registration_number: input.registration_number?.trim() || null,
      country: (input.country?.trim() || "DE").toUpperCase(),
      is_primary: Boolean(input.is_primary),
    }),
    signal,
  });
  const raw = await handleOrgResponse<unknown>(res);
  return validateLegalEntity(raw, tenantId, "created legal entity");
}

export async function fetchBusinessUnits(
  tenantId: string,
  token: string,
  legalEntityId?: string,
  signal?: AbortSignal
): Promise<BusinessUnit[]> {
  const query = legalEntityId ? `?legal_entity_id=${encodeURIComponent(legalEntityId)}` : "";
  const url = `${getApiBaseUrl()}/v1/tenants/${encodeURIComponent(tenantId)}/organization/business-units${query}`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
    signal,
  });
  const raw = await handleOrgResponse<unknown>(res);
  const arr = assertArray(raw, "business units list");
  return arr.map((item, idx) => validateBusinessUnit(item, tenantId, legalEntityId, `business unit item [${idx}]`));
}

export async function createBusinessUnit(
  tenantId: string,
  token: string,
  input: BusinessUnitCreateInput,
  signal?: AbortSignal
): Promise<BusinessUnit> {
  const url = `${getApiBaseUrl()}/v1/tenants/${encodeURIComponent(tenantId)}/organization/business-units`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      legal_entity_id: input.legal_entity_id,
      name: input.name.trim(),
      code: input.code?.trim() || null,
    }),
    signal,
  });
  const raw = await handleOrgResponse<unknown>(res);
  return validateBusinessUnit(raw, tenantId, input.legal_entity_id, "created business unit");
}

export async function fetchLocations(
  tenantId: string,
  token: string,
  legalEntityId?: string,
  signal?: AbortSignal
): Promise<Location[]> {
  const query = legalEntityId ? `?legal_entity_id=${encodeURIComponent(legalEntityId)}` : "";
  const url = `${getApiBaseUrl()}/v1/tenants/${encodeURIComponent(tenantId)}/organization/locations${query}`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
    signal,
  });
  const raw = await handleOrgResponse<unknown>(res);
  const arr = assertArray(raw, "locations list");
  return arr.map((item, idx) => validateLocation(item, tenantId, legalEntityId, `location item [${idx}]`));
}

export async function createLocation(
  tenantId: string,
  token: string,
  input: LocationCreateInput,
  signal?: AbortSignal
): Promise<Location> {
  const url = `${getApiBaseUrl()}/v1/tenants/${encodeURIComponent(tenantId)}/organization/locations`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      legal_entity_id: input.legal_entity_id,
      name: input.name.trim(),
      country: (input.country?.trim() || "DE").toUpperCase(),
      city: input.city.trim(),
      address: input.address?.trim() || null,
    }),
    signal,
  });
  const raw = await handleOrgResponse<unknown>(res);
  return validateLocation(raw, tenantId, input.legal_entity_id, "created location");
}

export async function fetchMemberships(
  tenantId: string,
  token: string,
  signal?: AbortSignal
): Promise<Membership[]> {
  const url = `${getApiBaseUrl()}/v1/tenants/${encodeURIComponent(tenantId)}/memberships`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
    signal,
  });
  const raw = await handleOrgResponse<unknown>(res);
  const arr = assertArray(raw, "memberships list");
  return arr.map((item, idx) => validateMembership(item, `membership item [${idx}]`));
}

export async function fetchEntitlements(
  tenantId: string,
  token: string,
  signal?: AbortSignal
): Promise<TenantEntitlement> {
  const url = `${getApiBaseUrl()}/v1/tenants/${encodeURIComponent(tenantId)}/entitlements`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
    signal,
  });
  const raw = await handleOrgResponse<unknown>(res);
  return validateTenantEntitlement(raw, tenantId);
}
