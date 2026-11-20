import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ConflictError,
  ForbiddenError,
  NotFoundError,
  UnauthorizedError,
  ValidationError,
} from "./api";
import {
  correctVerification,
  getVerification,
  getVerificationHistory,
  getVerificationProjection,
  issueVerification,
  isVerificationEnabled,
  listVerifications,
  reconcileVerifications,
  revokeVerification,
  supersedeVerification,
  suspendVerification,
} from "./verification-api";
import { VerificationDetail } from "./verification-types";

describe("verification-api", () => {
  const tenantId = "11111111-1111-1111-1111-111111111111";
  const verificationId = "22222222-2222-2222-2222-222222222222";
  const preauditId = "33333333-3333-3333-3333-333333333333";
  const snapshotId = "44444444-4444-4444-4444-444444444444";
  const token = "mock-bearer-token-123";

  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("isVerificationEnabled", () => {
    it("returns true when VITE_ENABLE_CUSTOMER_READINESS_VERIFICATION is true", () => {
      vi.stubEnv("VITE_ENABLE_CUSTOMER_READINESS_VERIFICATION", "true");
      expect(isVerificationEnabled()).toBe(true);
    });

    it("returns false when VITE_ENABLE_CUSTOMER_READINESS_VERIFICATION is false", () => {
      vi.stubEnv("VITE_ENABLE_CUSTOMER_READINESS_VERIFICATION", "false");
      expect(isVerificationEnabled()).toBe(false);
    });
  });

  describe("listVerifications", () => {
    it("returns list of verifications on success and includes Bearer token and optional preaudit filter", async () => {
      const mockResponse = {
        verifications: [
          {
            id: verificationId,
            preaudit_id: preauditId,
            status: "ACTIVE",
            effective_status: "ACTIVE",
            revision: 1,
            issued_at: "2026-01-01T00:00:00Z",
            valid_through: "2027-01-01T00:00:00Z",
            synthetic_marker: "PRIVATE SYNTHETIC INTERNAL TEST RESULT",
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      } as Response);

      const res = await listVerifications(
        tenantId,
        token,
        undefined,
        50,
        0,
        preauditId,
      );
      expect(res.verifications).toHaveLength(1);
      expect(res.verifications[0].id).toBe(verificationId);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(
          `/v2/tenants/${tenantId}/customer-demo/readiness-verifications?limit=50&offset=0&preaudit_case_id=${preauditId}`,
        ),
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
            "Cache-Control": expect.stringContaining("no-store"),
          }),
        }),
      );
    });
  });

  describe("getVerification", () => {
    it("returns verification detail on success with Bearer authorization", async () => {
      const mockDetail: VerificationDetail = {
        id: verificationId,
        preaudit_id: preauditId,
        snapshot_id: snapshotId,
        status: "ACTIVE",
        effective_status: "ACTIVE",
        revision: 1,
        issued_at: "2026-01-01T00:00:00Z",
        valid_through: "2027-01-01T00:00:00Z",
        digest: "a".repeat(64),
        synthetic_marker: "PRIVATE SYNTHETIC INTERNAL TEST RESULT",
        test_qualification:
          "PRIVATE SYNTHETIC INTERNAL TEST RESULT - NOT AN ACCREDITED CERTIFICATION",
        limitations: ["Internal test only"],
        issuer_user_id: "user-1",
        reviewer_user_id: "user-2",
        approver_user_id: "user-3",
      };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockDetail,
      } as Response);

      const res = await getVerification(tenantId, verificationId, token);
      expect(res.id).toBe(verificationId);
      expect(res.status).toBe("ACTIVE");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(
          `/v2/tenants/${tenantId}/customer-demo/readiness-verifications/${verificationId}`,
        ),
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
          }),
        }),
      );
    });
  });

  describe("getVerificationProjection", () => {
    it("returns allowlisted projection on success with Bearer authorization", async () => {
      const mockProjection = {
        verification_id: verificationId,
        synthetic_marker: "PRIVATE SYNTHETIC INTERNAL TEST RESULT",
        test_qualification:
          "PRIVATE SYNTHETIC INTERNAL TEST RESULT - NOT AN ACCREDITED CERTIFICATION",
        framework_display_name: "ISO 27001",
        framework_version: "2022",
        organization_display_name: "Test Corp",
        scope_summary: { controls_count: 10 },
        controls_count: 10,
        issued_at: "2026-01-01T00:00:00Z",
        valid_through: "2027-01-01T00:00:00Z",
        status: "ACTIVE",
        effective_status: "ACTIVE",
        limitations: [],
      };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockProjection,
      } as Response);

      const res = await getVerificationProjection(
        tenantId,
        verificationId,
        token,
      );
      expect(res.verification_id).toBe(verificationId);
      expect(res.framework_display_name).toBe("ISO 27001");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(
          `/v2/tenants/${tenantId}/customer-demo/readiness-verifications/${verificationId}/projection`,
        ),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
          }),
        }),
      );
    });
  });

  describe("getVerificationHistory", () => {
    it("returns history events on success with Bearer authorization", async () => {
      const mockHistory = {
        verification_id: verificationId,
        events: [
          {
            id: "ev-1",
            sequence: 1,
            revision: 1,
            event_type: "ISSUED",
            created_at: "2026-01-01T00:00:00Z",
            actor_user_id: "user-1",
          },
        ],
      };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockHistory,
      } as Response);

      const res = await getVerificationHistory(
        tenantId,
        verificationId,
        token,
      );
      expect(res.events).toHaveLength(1);
      expect(res.events[0].event_type).toBe("ISSUED");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(
          `/v2/tenants/${tenantId}/customer-demo/readiness-verifications/${verificationId}/history`,
        ),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
          }),
        }),
      );
    });
  });

  describe("issueVerification", () => {
    it("sends POST request to issue verification with Bearer authorization", async () => {
      const payload = {
        operation_id: "op-1",
        preaudit_id: preauditId,
        expected_case_revision: 2,
        snapshot_id: snapshotId,
        snapshot_digest: "b".repeat(64),
      };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => ({ id: verificationId, status: "ACTIVE" }),
      } as Response);

      const res = await issueVerification(tenantId, payload, token);
      expect(res.id).toBe(verificationId);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(
          `/v2/tenants/${tenantId}/customer-demo/readiness-verifications`,
        ),
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          }),
          body: JSON.stringify(payload),
        }),
      );
    });
  });

  describe("suspendVerification", () => {
    it("sends POST request to suspend verification with Bearer authorization", async () => {
      const payload = {
        operation_id: "op-2",
        expected_revision: 1,
        reason: "Suspended for audit",
      };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: verificationId, status: "SUSPENDED" }),
      } as Response);

      const res = await suspendVerification(
        tenantId,
        verificationId,
        payload,
        token,
      );
      expect(res.status).toBe("SUSPENDED");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(
          `/v2/tenants/${tenantId}/customer-demo/readiness-verifications/${verificationId}/suspend`,
        ),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
          }),
        }),
      );
    });
  });

  describe("revokeVerification", () => {
    it("sends POST request to revoke verification with Bearer authorization", async () => {
      const payload = {
        operation_id: "op-3",
        expected_revision: 2,
        reason: "Material non-conformance",
      };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: verificationId, status: "REVOKED" }),
      } as Response);

      const res = await revokeVerification(
        tenantId,
        verificationId,
        payload,
        token,
      );
      expect(res.status).toBe("REVOKED");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(
          `/v2/tenants/${tenantId}/customer-demo/readiness-verifications/${verificationId}/revoke`,
        ),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
          }),
        }),
      );
    });
  });

  describe("correctVerification", () => {
    it("sends POST request to correct verification metadata with Bearer authorization", async () => {
      const payload = {
        operation_id: "op-4",
        expected_revision: 1,
        correction_notes: "Corrected limitations",
      };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: verificationId, revision: 2 }),
      } as Response);

      const res = await correctVerification(
        tenantId,
        verificationId,
        payload,
        token,
      );
      expect(res.revision).toBe(2);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(
          `/v2/tenants/${tenantId}/customer-demo/readiness-verifications/${verificationId}/correct`,
        ),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
          }),
        }),
      );
    });
  });

  describe("supersedeVerification", () => {
    it("sends POST request to supersede verification with Bearer authorization", async () => {
      const payload = {
        operation_id: "op-5",
        expected_revision: 1,
        new_preaudit_id: "new-preaudit-id",
        new_expected_case_revision: 1,
        new_snapshot_id: "new-snapshot-id",
        new_snapshot_digest: "c".repeat(64),
      };

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => ({ id: "new-verification-id", status: "ACTIVE" }),
      } as Response);

      const res = await supersedeVerification(
        tenantId,
        verificationId,
        payload,
        token,
      );
      expect(res.id).toBe("new-verification-id");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(
          `/v2/tenants/${tenantId}/customer-demo/readiness-verifications/${verificationId}/supersede`,
        ),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
          }),
        }),
      );
    });
  });

  describe("reconcileVerifications", () => {
    it("sends POST request to reconcile verifications with Bearer authorization", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ reconciled_count: 0, results: [] }),
      } as Response);

      const res = await reconcileVerifications(tenantId, {}, token);
      expect(res.reconciled_count).toBe(0);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(
          `/v2/tenants/${tenantId}/customer-demo/readiness-verifications/reconcile`,
        ),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
          }),
        }),
      );
    });
  });

  describe("error handling", () => {
    it("throws ConflictError on 409", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: async () => ({ detail: "Revision conflict" }),
      } as Response);

      await expect(
        suspendVerification(
          tenantId,
          verificationId,
          {
            operation_id: "op",
            expected_revision: 1,
            reason: "test",
          },
          token,
        ),
      ).rejects.toThrow(ConflictError);
    });

    it("throws ForbiddenError on 403", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: "Only Owner can manage verification" }),
      } as Response);

      await expect(
        revokeVerification(
          tenantId,
          verificationId,
          {
            operation_id: "op",
            expected_revision: 1,
            reason: "test",
          },
          token,
        ),
      ).rejects.toThrow(ForbiddenError);
    });

    it("throws NotFoundError on 404", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: "Verification not found" }),
      } as Response);

      await expect(
        getVerification(tenantId, verificationId, token),
      ).rejects.toThrow(NotFoundError);
    });

    it("throws UnauthorizedError on 401", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: "Unauthorized" }),
      } as Response);

      await expect(
        getVerification(tenantId, verificationId, token),
      ).rejects.toThrow(UnauthorizedError);
    });

    it("throws ValidationError on 422", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({ detail: "Invalid request payload" }),
      } as Response);

      await expect(
        correctVerification(
          tenantId,
          verificationId,
          {
            operation_id: "op",
            expected_revision: 1,
            correction_notes: "",
          },
          token,
        ),
      ).rejects.toThrow(ValidationError);
    });
  });
});
