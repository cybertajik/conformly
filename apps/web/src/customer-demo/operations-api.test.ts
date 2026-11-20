import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  fetchPolicies,
  createPolicy,
  updatePolicy,
  submitPolicyReview,
  approvePolicy,
  publishPolicy,
  archivePolicy,
  fetchPolicyRevisions,
  acknowledgePolicy,
  fetchPolicyAcknowledgements,
  fetchRisks,
  createRisk,
  updateRisk,
  reviewRisk,
  createRiskTreatment,
  updateRiskTreatment,
  fetchAssets,
  createAsset,
  updateAsset,
  reviewAsset,
  fetchVendors,
  createVendor,
  updateVendor,
  reviewVendor,
} from "./operations-api";
import {
  ConflictError,
  ForbiddenError,
  NotFoundError,
  UnauthorizedError,
  ValidationError,
} from "./api";

describe("operations-api client", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("fetchPolicies returns array and handles 401/403/404 errors", async () => {
    const mockPolicies = [
      {
        id: "pol-1",
        tenant_id: "ten-1",
        title: "Security Policy",
        description: "Test description",
        version_string: "1.0",
        status: "draft",
        owner_user_id: "user-1",
        approved_by_user_id: null,
        approved_at: null,
        review_cycle_days: 365,
        next_review_due: null,
        version: 1,
        content: "Policy text",
        classification: "Internal",
        created_at: "2026-10-29T10:00:00Z",
        updated_at: "2026-10-29T10:00:00Z",
      },
    ];

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockPolicies,
    } as Response);

    const res = await fetchPolicies("ten-1", "token-1");
    expect(res).toEqual(mockPolicies);

    // 401 error
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Unauthorized token" }),
    } as Response);
    await expect(fetchPolicies("ten-1", "token-1")).rejects.toThrow(UnauthorizedError);

    // 403 error
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: "Forbidden role" }),
    } as Response);
    await expect(fetchPolicies("ten-1", "token-1")).rejects.toThrow(ForbiddenError);

    // 404 error
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Tenant not found" }),
    } as Response);
    await expect(fetchPolicies("ten-1", "token-1")).rejects.toThrow(NotFoundError);
  });

  it("handles policy mutations: create, update (409 conflict), and lifecycle transitions", async () => {
    const mockPolicy = {
      id: "pol-1",
      tenant_id: "ten-1",
      title: "Security Policy",
      version: 1,
      status: "draft",
    };

    // Create
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockPolicy,
    } as Response);
    const created = await createPolicy("ten-1", "token-1", {
      title: "Security Policy",
      description: "Test description",
    });
    expect(created.id).toBe("pol-1");

    // Update 409 conflict
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: "Version conflict" }),
    } as Response);
    await expect(
      updatePolicy("ten-1", "token-1", "pol-1", { expected_version: 1, title: "New Title" })
    ).rejects.toThrow(ConflictError);

    // Update 422 validation error
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: "Invalid title length" }),
    } as Response);
    await expect(
      updatePolicy("ten-1", "token-1", "pol-1", { expected_version: 1, title: "" })
    ).rejects.toThrow(ValidationError);

    // Submit review, approve, publish, archive
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...mockPolicy, status: "in_review", version: 2 }),
    } as Response);
    const reviewed = await submitPolicyReview("ten-1", "token-1", "pol-1", { expected_version: 1 });
    expect(reviewed.status).toBe("in_review");

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...mockPolicy, status: "approved", version: 3 }),
    } as Response);
    const approved = await approvePolicy("ten-1", "token-1", "pol-1", { expected_version: 2 });
    expect(approved.status).toBe("approved");

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...mockPolicy, status: "published", version: 4 }),
    } as Response);
    const published = await publishPolicy("ten-1", "token-1", "pol-1", { expected_version: 3 });
    expect(published.status).toBe("published");

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...mockPolicy, status: "archived", version: 5 }),
    } as Response);
    const archived = await archivePolicy("ten-1", "token-1", "pol-1", { expected_version: 4 });
    expect(archived.status).toBe("archived");
  });

  it("handles policy revisions and acknowledgements", async () => {
    const mockRevisions = [
      {
        id: "rev-1",
        policy_id: "pol-1",
        revision_number: 1,
        title: "Rev 1",
        status: "published",
      },
    ];
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockRevisions,
    } as Response);
    const revs = await fetchPolicyRevisions("ten-1", "token-1", "pol-1");
    expect(revs).toHaveLength(1);

    // Acknowledge
    const mockAck = {
      id: "ack-1",
      tenant_id: "ten-1",
      policy_id: "pol-1",
      user_id: "user-1",
      acknowledged_at: "2026-10-29T10:00:00Z",
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockAck,
    } as Response);
    const ack = await acknowledgePolicy("ten-1", "token-1", "pol-1");
    expect(ack.id).toBe("ack-1");

    // Fetch acknowledgements
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [mockAck],
    } as Response);
    const acks = await fetchPolicyAcknowledgements("ten-1", "token-1", "pol-1");
    expect(acks).toHaveLength(1);
  });

  it("handles risks and risk treatments lifecycle", async () => {
    const mockRisk = {
      id: "risk-1",
      tenant_id: "ten-1",
      title: "Data Leak",
      category: "security",
      likelihood: 3,
      impact: 4,
      inherent_score: 12,
      residual_score: null,
      status: "identified",
      treatments: [],
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [mockRisk],
    } as Response);
    const risks = await fetchRisks("ten-1", "token-1");
    expect(risks).toHaveLength(1);

    // Create risk
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockRisk,
    } as Response);
    const newRisk = await createRisk("ten-1", "token-1", {
      title: "Data Leak",
      description: "Loss of customer data",
      likelihood: 3,
      impact: 4,
    });
    expect(newRisk.id).toBe("risk-1");

    // Update risk
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...mockRisk, status: "assessed" }),
    } as Response);
    const updatedRisk = await updateRisk("ten-1", "token-1", "risk-1", {
      title: "Data Leak Updated",
      description: "Loss of customer data",
      likelihood: 2,
      impact: 4,
      status: "assessed",
    });
    expect(updatedRisk.status).toBe("assessed");

    // Review risk
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...mockRisk, last_reviewed_at: "2026-10-29T10:00:00Z" }),
    } as Response);
    const reviewedRisk = await reviewRisk("ten-1", "token-1", "risk-1");
    expect(reviewedRisk.last_reviewed_at).toBeDefined();

    // Create treatment
    const mockTreatment = {
      id: "treat-1",
      strategy: "mitigate",
      treatment_plan: "Deploy DLP",
      target_date: "2026-12-31",
      status: "planned",
      owner_user_id: null,
      created_at: "2026-10-29T10:00:00Z",
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockTreatment,
    } as Response);
    const treat = await createRiskTreatment("ten-1", "token-1", "risk-1", {
      treatment_plan: "Deploy DLP",
      strategy: "mitigate",
    });
    expect(treat.id).toBe("treat-1");

    // Update treatment
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...mockTreatment, status: "completed" }),
    } as Response);
    const updatedTreat = await updateRiskTreatment("ten-1", "token-1", "treat-1", {
      treatment_plan: "Deploy DLP",
      status: "completed",
    });
    expect(updatedTreat.status).toBe("completed");
  });

  it("handles assets lifecycle", async () => {
    const mockAsset = {
      id: "asset-1",
      tenant_id: "ten-1",
      name: "Prod DB",
      asset_type: "data",
      classification: "restricted",
      status: "active",
      created_at: "2026-10-29T10:00:00Z",
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [mockAsset],
    } as Response);
    const assets = await fetchAssets("ten-1", "token-1");
    expect(assets).toHaveLength(1);

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockAsset,
    } as Response);
    const newAsset = await createAsset("ten-1", "token-1", {
      name: "Prod DB",
      asset_type: "data",
      classification: "restricted",
    });
    expect(newAsset.id).toBe("asset-1");

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...mockAsset, name: "Prod DB Updated" }),
    } as Response);
    const updatedAsset = await updateAsset("ten-1", "token-1", "asset-1", {
      name: "Prod DB Updated",
    });
    expect(updatedAsset.name).toBe("Prod DB Updated");

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...mockAsset, last_reviewed_at: "2026-10-29T10:00:00Z" }),
    } as Response);
    const reviewedAsset = await reviewAsset("ten-1", "token-1", "asset-1");
    expect(reviewedAsset.last_reviewed_at).toBeDefined();
  });

  it("handles vendors lifecycle", async () => {
    const mockVendor = {
      id: "ven-1",
      tenant_id: "ten-1",
      name: "Cloud Hosting Ltd",
      service_description: "Core Cloud",
      criticality: "critical",
      data_classification_accessed: "Restricted",
      country_residency: "DE",
      dpa_signed: true,
      security_reviewed_at: null,
      next_review_due_at: null,
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [mockVendor],
    } as Response);
    const vendors = await fetchVendors("ten-1", "token-1");
    expect(vendors).toHaveLength(1);

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockVendor,
    } as Response);
    const newVendor = await createVendor("ten-1", "token-1", {
      name: "Cloud Hosting Ltd",
      service_description: "Core Cloud",
      criticality: "critical",
    });
    expect(newVendor.id).toBe("ven-1");

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...mockVendor, name: "Cloud Hosting Updated" }),
    } as Response);
    const updatedVendor = await updateVendor("ten-1", "token-1", "ven-1", {
      name: "Cloud Hosting Updated",
      service_description: "Core Cloud",
    });
    expect(updatedVendor.name).toBe("Cloud Hosting Updated");

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...mockVendor, security_reviewed_at: "2026-10-29T10:00:00Z" }),
    } as Response);
    const reviewedVendor = await reviewVendor("ten-1", "token-1", "ven-1");
    expect(reviewedVendor.security_reviewed_at).toBeDefined();
  });
});
