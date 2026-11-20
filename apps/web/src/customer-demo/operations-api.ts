/**
 * Typed, cancellable API client for Operations Workspace: Policies, Risks, Assets, and Vendors.
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
  Asset,
  AssetCreateInput,
  AssetReviewInput,
  AssetUpdateInput,
  Policy,
  PolicyAcknowledgement,
  PolicyCreateInput,
  PolicyRevision,
  PolicyStatus,
  PolicyUpdateInput,
  Risk,
  RiskCreateInput,
  RiskReviewInput,
  RiskTreatment,
  RiskTreatmentCreateInput,
  RiskTreatmentUpdateInput,
  RiskUpdateInput,
  Vendor,
  VendorCreateInput,
  VendorReviewInput,
  VendorUpdateInput,
  VersionedActionInput,
} from "./operations-types";

async function handleOpsResponse<T>(res: Response): Promise<T> {
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


function validateOpsArray<T extends { tenant_id?: string }>(data: unknown, expectedTenantId: string, entityName: string): T[] {
  if (!Array.isArray(data)) {
    throw new Error(`Invalid response format for ${entityName} list`);
  }
  for (const item of data) {
    if (!item || typeof item !== "object") {
      throw new Error(`Malformed item in ${entityName} list`);
    }
    if ("tenant_id" in item && (item as { tenant_id?: string }).tenant_id !== expectedTenantId) {
      throw new Error(`Cross-tenant data rejected in ${entityName} list`);
    }
  }
  return data as T[];
}

function validateOpsItem<T extends { tenant_id?: string }>(item: unknown, expectedTenantId: string, entityName: string): T {
  if (!item || typeof item !== "object") {
    throw new Error(`Malformed response for ${entityName}`);
  }
  if ("tenant_id" in item && (item as { tenant_id?: string }).tenant_id !== expectedTenantId) {
    throw new Error(`Cross-tenant data rejected for ${entityName}`);
  }
  return item as T;
}

// ── Policies API ──────────────────────────────────────────────────────────────

export async function fetchPolicies(
  tenantId: string,
  token: string,
  status?: PolicyStatus,
  signal?: AbortSignal
): Promise<Policy[]> {
  const url = new URL(`${getApiBaseUrl()}/v1/tenants/${tenantId}/compliance/policies`);
  if (status) {
    url.searchParams.set("status", status);
  }
  const res = await fetch(url.toString(), {
    method: "GET",
    headers: authHeaders(token),
    signal,
  });
  const data = await handleOpsResponse<Policy[]>(res);
  return validateOpsArray<Policy>(data, tenantId, "policies");
}

export async function fetchPolicy(
  tenantId: string,
  token: string,
  policyId: string,
  signal?: AbortSignal
): Promise<Policy> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/compliance/policies/${policyId}`;
  const res = await fetch(url, {
    method: "GET",
    headers: authHeaders(token),
    signal,
  });
  const item = await handleOpsResponse<Policy>(res);
  return validateOpsItem<Policy>(item, tenantId, "policy");
}

export async function createPolicy(
  tenantId: string,
  token: string,
  input: PolicyCreateInput,
  signal?: AbortSignal
): Promise<Policy> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/compliance/policies`;
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<Policy>(res);
}

export async function updatePolicy(
  tenantId: string,
  token: string,
  policyId: string,
  input: PolicyUpdateInput,
  signal?: AbortSignal
): Promise<Policy> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/compliance/policies/${policyId}`;
  const res = await fetch(url, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<Policy>(res);
}

export async function submitPolicyReview(
  tenantId: string,
  token: string,
  policyId: string,
  input: VersionedActionInput,
  signal?: AbortSignal
): Promise<Policy> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/compliance/policies/${policyId}/submit-review`;
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<Policy>(res);
}

export async function approvePolicy(
  tenantId: string,
  token: string,
  policyId: string,
  input: VersionedActionInput,
  signal?: AbortSignal
): Promise<Policy> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/compliance/policies/${policyId}/approve`;
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<Policy>(res);
}

export async function publishPolicy(
  tenantId: string,
  token: string,
  policyId: string,
  input: VersionedActionInput,
  signal?: AbortSignal
): Promise<Policy> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/compliance/policies/${policyId}/publish`;
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<Policy>(res);
}

export async function archivePolicy(
  tenantId: string,
  token: string,
  policyId: string,
  input: VersionedActionInput,
  signal?: AbortSignal
): Promise<Policy> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/compliance/policies/${policyId}/archive`;
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<Policy>(res);
}

export async function fetchPolicyRevisions(
  tenantId: string,
  token: string,
  policyId: string,
  signal?: AbortSignal
): Promise<PolicyRevision[]> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/compliance/policies/${policyId}/revisions`;
  const res = await fetch(url, {
    method: "GET",
    headers: authHeaders(token),
    signal,
  });
  const data = await handleOpsResponse<PolicyRevision[]>(res);
  if (!Array.isArray(data)) {
    throw new Error("Invalid response format for policy revisions");
  }
  return data;
}

export async function acknowledgePolicy(
  tenantId: string,
  token: string,
  policyId: string,
  signal?: AbortSignal
): Promise<PolicyAcknowledgement> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/compliance/policies/${policyId}/acknowledge`;
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({}),
    signal,
  });
  return handleOpsResponse<PolicyAcknowledgement>(res);
}

export async function fetchPolicyAcknowledgements(
  tenantId: string,
  token: string,
  policyId: string,
  signal?: AbortSignal
): Promise<PolicyAcknowledgement[]> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/compliance/policies/${policyId}/acknowledgements`;
  const res = await fetch(url, {
    method: "GET",
    headers: authHeaders(token),
    signal,
  });
  const data = await handleOpsResponse<PolicyAcknowledgement[]>(res);
  if (!Array.isArray(data)) {
    throw new Error("Invalid response format for policy acknowledgements");
  }
  return data;
}

// ── Risks API ─────────────────────────────────────────────────────────────────

export async function fetchRisks(
  tenantId: string,
  token: string,
  signal?: AbortSignal
): Promise<Risk[]> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/risks`;
  const res = await fetch(url, {
    method: "GET",
    headers: authHeaders(token),
    signal,
  });
  const data = await handleOpsResponse<Risk[]>(res);
  return validateOpsArray<Risk>(data, tenantId, "risks");
}

export async function fetchRisk(
  tenantId: string,
  token: string,
  riskId: string,
  signal?: AbortSignal
): Promise<Risk> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/risks/${riskId}`;
  const res = await fetch(url, {
    method: "GET",
    headers: authHeaders(token),
    signal,
  });
  const item = await handleOpsResponse<Risk>(res);
  return validateOpsItem<Risk>(item, tenantId, "risk");
}

export async function createRisk(
  tenantId: string,
  token: string,
  input: RiskCreateInput,
  signal?: AbortSignal
): Promise<Risk> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/risks`;
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<Risk>(res);
}

export async function updateRisk(
  tenantId: string,
  token: string,
  riskId: string,
  input: RiskUpdateInput,
  signal?: AbortSignal
): Promise<Risk> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/risks/${riskId}`;
  const res = await fetch(url, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<Risk>(res);
}

export async function reviewRisk(
  tenantId: string,
  token: string,
  riskId: string,
  input: RiskReviewInput = {},
  signal?: AbortSignal
): Promise<Risk> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/risks/${riskId}/review`;
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<Risk>(res);
}

export async function createRiskTreatment(
  tenantId: string,
  token: string,
  riskId: string,
  input: RiskTreatmentCreateInput,
  signal?: AbortSignal
): Promise<RiskTreatment> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/risks/${riskId}/treatments`;
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<RiskTreatment>(res);
}

export async function updateRiskTreatment(
  tenantId: string,
  token: string,
  treatmentId: string,
  input: RiskTreatmentUpdateInput,
  signal?: AbortSignal
): Promise<RiskTreatment> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/risks/treatments/${treatmentId}`;
  const res = await fetch(url, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<RiskTreatment>(res);
}

// ── Assets API ────────────────────────────────────────────────────────────────

export async function fetchAssets(
  tenantId: string,
  token: string,
  signal?: AbortSignal
): Promise<Asset[]> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/assets`;
  const res = await fetch(url, {
    method: "GET",
    headers: authHeaders(token),
    signal,
  });
  const data = await handleOpsResponse<Asset[]>(res);
  return validateOpsArray<Asset>(data, tenantId, "assets");
}

export async function fetchAsset(
  tenantId: string,
  token: string,
  assetId: string,
  signal?: AbortSignal
): Promise<Asset> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/assets/${assetId}`;
  const res = await fetch(url, {
    method: "GET",
    headers: authHeaders(token),
    signal,
  });
  const item = await handleOpsResponse<Asset>(res);
  return validateOpsItem<Asset>(item, tenantId, "asset");
}

export async function createAsset(
  tenantId: string,
  token: string,
  input: AssetCreateInput,
  signal?: AbortSignal
): Promise<Asset> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/assets`;
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<Asset>(res);
}

export async function updateAsset(
  tenantId: string,
  token: string,
  assetId: string,
  input: AssetUpdateInput,
  signal?: AbortSignal
): Promise<Asset> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/assets/${assetId}`;
  const res = await fetch(url, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<Asset>(res);
}

export async function reviewAsset(
  tenantId: string,
  token: string,
  assetId: string,
  input: AssetReviewInput = {},
  signal?: AbortSignal
): Promise<Asset> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/assets/${assetId}/review`;
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<Asset>(res);
}

// ── Vendors API ───────────────────────────────────────────────────────────────

export async function fetchVendors(
  tenantId: string,
  token: string,
  signal?: AbortSignal
): Promise<Vendor[]> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/vendors`;
  const res = await fetch(url, {
    method: "GET",
    headers: authHeaders(token),
    signal,
  });
  const data = await handleOpsResponse<Vendor[]>(res);
  return validateOpsArray<Vendor>(data, tenantId, "vendors");
}

export async function fetchVendor(
  tenantId: string,
  token: string,
  vendorId: string,
  signal?: AbortSignal
): Promise<Vendor> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/vendors/${vendorId}`;
  const res = await fetch(url, {
    method: "GET",
    headers: authHeaders(token),
    signal,
  });
  const item = await handleOpsResponse<Vendor>(res);
  return validateOpsItem<Vendor>(item, tenantId, "vendor");
}

export async function createVendor(
  tenantId: string,
  token: string,
  input: VendorCreateInput,
  signal?: AbortSignal
): Promise<Vendor> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/vendors`;
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<Vendor>(res);
}

export async function updateVendor(
  tenantId: string,
  token: string,
  vendorId: string,
  input: VendorUpdateInput,
  signal?: AbortSignal
): Promise<Vendor> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/vendors/${vendorId}`;
  const res = await fetch(url, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<Vendor>(res);
}

export async function reviewVendor(
  tenantId: string,
  token: string,
  vendorId: string,
  input: VendorReviewInput = {},
  signal?: AbortSignal
): Promise<Vendor> {
  const url = `${getApiBaseUrl()}/v1/tenants/${tenantId}/vendors/${vendorId}/review`;
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(input),
    signal,
  });
  return handleOpsResponse<Vendor>(res);
}
