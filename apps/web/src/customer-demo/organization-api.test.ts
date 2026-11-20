import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ConflictError,
  CustomerDemoApiError,
  ForbiddenError,
  NotFoundError,
  UnauthorizedError,
  ValidationError,
} from "./api";
import {
  createBusinessUnit,
  createLegalEntity,
  createLocation,
  fetchBusinessUnits,
  fetchEntitlements,
  fetchLegalEntities,
  fetchLocations,
  fetchMemberships,
} from "./organization-api";

describe("organization-api client", () => {
  const originalFetch = globalThis.fetch;
  const tenantId = "11111111-1111-4111-8111-111111111111";
  const token = "test-token-xyz";

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  describe("Legal Entities API", () => {
    it("fetchLegalEntities sends GET with auth headers and validates matching tenant_id", async () => {
      const mockEntities = [
        {
          id: "ent-1",
          tenant_id: tenantId,
          name: "Acme Corp DE",
          registration_number: "HRB 12345",
          country: "DE",
          is_primary: true,
        },
      ];

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockEntities,
      } as Response);

      const res = await fetchLegalEntities(tenantId, token);

      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/v1/tenants/${tenantId}/organization/legal-entities`),
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
          }),
        })
      );
      expect(res).toHaveLength(1);
      expect(res[0].id).toBe("ent-1");
      expect(res[0].name).toBe("Acme Corp DE");
    });

    it("fetchLegalEntities rejects cross-tenant items with CustomerDemoApiError", async () => {
      const crossTenantEntities = [
        {
          id: "ent-1",
          tenant_id: tenantId,
          name: "Acme Corp DE",
          registration_number: null,
          country: "DE",
          is_primary: true,
        },
        {
          id: "ent-foreign",
          tenant_id: "foreign-tenant-id",
          name: "Rogue Foreign Corp",
          registration_number: null,
          country: "US",
          is_primary: false,
        },
      ];

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => crossTenantEntities,
      } as Response);

      await expect(fetchLegalEntities(tenantId, token)).rejects.toThrow(CustomerDemoApiError);
    });

    it("fetchLegalEntities rejects malformed non-array response", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ unexpected: "object" }),
      } as Response);

      await expect(fetchLegalEntities(tenantId, token)).rejects.toThrow(CustomerDemoApiError);
    });

    it("createLegalEntity sends POST with formatted JSON body and validates response", async () => {
      const mockCreated = {
        id: "ent-2",
        tenant_id: tenantId,
        name: "Acme France SAS",
        registration_number: "RCS 98765",
        country: "FR",
        is_primary: false,
      };

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 201,
        json: async () => mockCreated,
      } as Response);

      const res = await createLegalEntity(tenantId, token, {
        name: "  Acme France SAS  ",
        registration_number: " RCS 98765 ",
        country: "fr",
        is_primary: false,
      });

      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/v1/tenants/${tenantId}/organization/legal-entities`),
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          }),
          body: JSON.stringify({
            name: "Acme France SAS",
            registration_number: "RCS 98765",
            country: "FR",
            is_primary: false,
          }),
        })
      );
      expect(res).toEqual(mockCreated);
    });

    it("createLegalEntity rejects cross-tenant response payload", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 201,
        json: async () => ({
          id: "ent-2",
          tenant_id: "wrong-tenant",
          name: "Acme Corp",
          registration_number: null,
          country: "DE",
          is_primary: false,
        }),
      } as Response);

      await expect(
        createLegalEntity(tenantId, token, { name: "Acme Corp" })
      ).rejects.toThrow(CustomerDemoApiError);
    });

    it("throws ForbiddenError on 403 response", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({ detail: "missing organization:read capability" }),
      } as Response);

      await expect(fetchLegalEntities(tenantId, token)).rejects.toThrow(ForbiddenError);
    });

    it("throws UnauthorizedError on 401 response", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: "token expired" }),
      } as Response);

      await expect(fetchLegalEntities(tenantId, token)).rejects.toThrow(UnauthorizedError);
    });

    it("throws ValidationError on 422 response", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({ detail: "Name must be at least 1 character" }),
      } as Response);

      await expect(
        createLegalEntity(tenantId, token, { name: "" })
      ).rejects.toThrow(ValidationError);
    });
  });

  describe("Business Units API", () => {
    it("fetchBusinessUnits includes legal_entity_id query parameter and validates response", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => [
          {
            id: "bu-1",
            tenant_id: tenantId,
            legal_entity_id: "ent-1",
            name: "IT Infrastructure",
            code: "IT-INFRA",
          },
        ],
      } as Response);

      const res = await fetchBusinessUnits(tenantId, token, "ent-1");

      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/v1/tenants/${tenantId}/organization/business-units?legal_entity_id=ent-1`),
        expect.any(Object)
      );
      expect(res).toHaveLength(1);
      expect(res[0].name).toBe("IT Infrastructure");
    });

    it("fetchBusinessUnits throws on cross-tenant or entity mismatch", async () => {
      // Entity mismatch
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => [
          {
            id: "bu-1",
            tenant_id: tenantId,
            legal_entity_id: "different-entity",
            name: "IT Infrastructure",
            code: null,
          },
        ],
      } as Response);

      await expect(fetchBusinessUnits(tenantId, token, "ent-1")).rejects.toThrow(CustomerDemoApiError);
    });

    it("createBusinessUnit sends trimmed payload and validates returned response", async () => {
      const mockBU = {
        id: "bu-2",
        tenant_id: tenantId,
        legal_entity_id: "ent-1",
        name: "Cybersecurity",
        code: "SEC",
      };

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 201,
        json: async () => mockBU,
      } as Response);

      const res = await createBusinessUnit(tenantId, token, {
        legal_entity_id: "ent-1",
        name: "  Cybersecurity  ",
        code: " SEC ",
      });

      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/v1/tenants/${tenantId}/organization/business-units`),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            legal_entity_id: "ent-1",
            name: "Cybersecurity",
            code: "SEC",
          }),
        })
      );
      expect(res).toEqual(mockBU);
    });

    it("throws NotFoundError on 404 response", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: "Legal entity not found" }),
      } as Response);

      await expect(
        createBusinessUnit(tenantId, token, { legal_entity_id: "missing-id", name: "BU" })
      ).rejects.toThrow(NotFoundError);
    });
  });

  describe("Locations API", () => {
    it("fetchLocations sends GET and validates matching tenant and entity", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => [
          {
            id: "loc-1",
            tenant_id: tenantId,
            legal_entity_id: "ent-1",
            name: "Berlin Office",
            country: "DE",
            city: "Berlin",
            address: "Unter den Linden 1",
          },
        ],
      } as Response);

      const res = await fetchLocations(tenantId, token, "ent-1");
      expect(res).toHaveLength(1);
      expect(res[0].city).toBe("Berlin");
    });

    it("createLocation formats uppercase country and trimmed strings", async () => {
      const mockLoc = {
        id: "loc-2",
        tenant_id: tenantId,
        legal_entity_id: "ent-1",
        name: "Munich Data Center",
        country: "DE",
        city: "Munich",
        address: null,
      };

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 201,
        json: async () => mockLoc,
      } as Response);

      const res = await createLocation(tenantId, token, {
        legal_entity_id: "ent-1",
        name: "Munich Data Center",
        country: "de",
        city: "Munich",
      });

      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/v1/tenants/${tenantId}/organization/locations`),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            legal_entity_id: "ent-1",
            name: "Munich Data Center",
            country: "DE",
            city: "Munich",
            address: null,
          }),
        })
      );
      expect(res).toEqual(mockLoc);
    });

    it("createLocation throws CustomerDemoApiError on cross-tenant response", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 201,
        json: async () => ({
          id: "loc-2",
          tenant_id: "foreign-tenant",
          legal_entity_id: "ent-1",
          name: "Munich DC",
          country: "DE",
          city: "Munich",
          address: null,
        }),
      } as Response);

      await expect(
        createLocation(tenantId, token, {
          legal_entity_id: "ent-1",
          name: "Munich DC",
          city: "Munich",
        })
      ).rejects.toThrow(CustomerDemoApiError);
    });
  });

  describe("Memberships API", () => {
    it("fetchMemberships returns directory of users and roles", async () => {
      const mockMembers = [
        {
          id: "m-1",
          user_id: "u-1",
          email: "admin@example.com",
          display_name: "Admin User",
          role: "administrator",
          status: "ACTIVE",
        },
      ];

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockMembers,
      } as Response);

      const res = await fetchMemberships(tenantId, token);
      expect(res).toHaveLength(1);
      expect(res[0].email).toBe("admin@example.com");
      expect(res[0].role).toBe("administrator");
    });

    it("throws ForbiddenError when membership read capability is denied", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({ detail: "capability denied" }),
      } as Response);

      await expect(fetchMemberships(tenantId, token)).rejects.toThrow(ForbiddenError);
    });

    it("throws CustomerDemoApiError on malformed memberships array", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => [{ invalid: "membership" }],
      } as Response);

      await expect(fetchMemberships(tenantId, token)).rejects.toThrow(CustomerDemoApiError);
    });
  });

  describe("Entitlements API", () => {
    it("fetchEntitlements returns active tenant plan, modules and limits", async () => {
      const mockEntitlement = {
        id: "ent-rec-1",
        tenant_id: tenantId,
        plan_code: "growth",
        enabled_modules: ["frameworks", "audit", "organization"],
        max_members: 25,
        max_storage_bytes: 524288000,
        allowed_framework_slugs: ["*"],
        effective_from: "2026-01-01T00:00:00Z",
        effective_until: null,
      };

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockEntitlement,
      } as Response);

      const res = await fetchEntitlements(tenantId, token);
      expect(res.plan_code).toBe("growth");
      expect(res.max_members).toBe(25);
      expect(res.enabled_modules).toContain("organization");
    });

    it("throws ForbiddenError when entitlement:read capability is denied", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({ detail: "Forbidden: missing entitlement:read capability" }),
      } as Response);

      await expect(fetchEntitlements(tenantId, token)).rejects.toThrow(ForbiddenError);
    });

    it("throws CustomerDemoApiError when cross-tenant entitlement is returned", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          id: "ent-rec-1",
          tenant_id: "other-tenant",
          plan_code: "enterprise",
          enabled_modules: ["all"],
          max_members: 100,
          max_storage_bytes: 1000000,
          allowed_framework_slugs: ["*"],
          effective_from: "2026-01-01T00:00:00Z",
          effective_until: null,
        }),
      } as Response);

      await expect(fetchEntitlements(tenantId, token)).rejects.toThrow(CustomerDemoApiError);
    });

    it("throws ConflictError on 409 and generic CustomerDemoApiError on 500", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({ detail: "Conflict revision mismatch" }),
      } as Response);

      await expect(fetchEntitlements(tenantId, token)).rejects.toThrow(ConflictError);

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ detail: "Internal Server Error" }),
      } as Response);

      await expect(fetchEntitlements(tenantId, token)).rejects.toThrow(CustomerDemoApiError);
    });
  });

  describe("Cancellation & AbortSignal", () => {
    it("passes AbortSignal to fetch and rejects on abort", async () => {
      const ac = new AbortController();
      ac.abort();

      globalThis.fetch = vi.fn().mockImplementation((_url, options) => {
        if (options?.signal?.aborted) {
          const err = new Error("The operation was aborted");
          err.name = "AbortError";
          return Promise.reject(err);
        }
        return Promise.resolve({ ok: true, json: async () => [] });
      });

      await expect(fetchLegalEntities(tenantId, token, ac.signal)).rejects.toThrow(/aborted/i);
    });
  });
});
