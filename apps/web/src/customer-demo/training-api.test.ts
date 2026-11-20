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
  createTrainingAssignment,
  createTrainingCourse,
  fetchTrainingAssignments,
  fetchTrainingCompletions,
  fetchTrainingCourses,
} from "./training-api";

describe("training-api", () => {
  const tenantId = "11111111-1111-1111-1111-111111111111";
  const token = "mock-token-xyz";

  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("fetchTrainingCourses", () => {
    it("fetches courses and returns array", async () => {
      const mockCourses = [
        {
          id: "c-1",
          tenant_id: tenantId,
          course_id: "sec-101",
          version: "1.0",
          title: "Security Awareness",
          description: "Annual security training",
          provider: "lms",
          duration_minutes: 45,
          validity_period_days: 365,
          is_active: true,
          created_at: "2026-10-01T00:00:00Z",
        },
      ];
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockCourses,
      } as Response);

      const res = await fetchTrainingCourses(tenantId, token);
      expect(res).toEqual(mockCourses);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/v1/tenants/${tenantId}/lms/courses`),
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
          }),
        }),
      );
    });

    it("throws on tenant mismatch", async () => {
      const mockCourses = [
        {
          id: "c-1",
          tenant_id: "22222222-2222-2222-2222-222222222222",
          course_id: "sec-101",
        },
      ];
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockCourses,
      } as Response);

      await expect(fetchTrainingCourses(tenantId, token)).rejects.toThrow("Tenant mismatch");
    });
  });

  describe("createTrainingCourse", () => {
    it("creates course and returns response", async () => {
      const created = {
        id: "c-2",
        tenant_id: tenantId,
        course_id: "priv-201",
        version: "1.0",
        title: "Privacy Essentials",
        description: "GDPR/CCPA privacy overview",
        provider: "lms",
        duration_minutes: 30,
        validity_period_days: 365,
        is_active: true,
        created_at: "2026-10-02T00:00:00Z",
      };
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => created,
      } as Response);

      const res = await createTrainingCourse(tenantId, token, {
        course_id: "priv-201",
        title: "Privacy Essentials",
        description: "GDPR/CCPA privacy overview",
      });
      expect(res).toEqual(created);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/v1/tenants/${tenantId}/lms/courses`),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            course_id: "priv-201",
            title: "Privacy Essentials",
            description: "GDPR/CCPA privacy overview",
          }),
        }),
      );
    });
  });

  describe("fetchTrainingAssignments", () => {
    it("fetches assignments with status and user_id filters", async () => {
      const mockAssignments = [
        {
          id: "a-1",
          tenant_id: tenantId,
          course_id: "sec-101",
          workforce_email: "alice@example.com",
          due_date: "2026-11-15T00:00:00Z",
          status: "assigned",
          created_at: "2026-10-01T00:00:00Z",
        },
      ];
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockAssignments,
      } as Response);

      const res = await fetchTrainingAssignments(tenantId, token, {
        status: "assigned",
        user_id: "user-123",
      });
      expect(res).toEqual(mockAssignments);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("status=assigned&user_id=user-123"),
        expect.any(Object),
      );
    });
  });

  describe("createTrainingAssignment", () => {
    it("posts assignment and returns result", async () => {
      const created = {
        id: "a-2",
        tenant_id: tenantId,
        course_id: "sec-101",
        workforce_email: "bob@example.com",
        due_date: "2026-12-01T00:00:00Z",
        status: "assigned",
        created_at: "2026-10-02T00:00:00Z",
      };
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => created,
      } as Response);

      const res = await createTrainingAssignment(tenantId, token, {
        course_id: "sec-101",
        workforce_email: "bob@example.com",
        due_date: "2026-12-01T00:00:00Z",
      });
      expect(res).toEqual(created);
    });
  });

  describe("fetchTrainingCompletions", () => {
    it("fetches completions", async () => {
      const mockCompletions = [
        {
          id: "comp-1",
          tenant_id: tenantId,
          course_id: "sec-101",
          course_version: "1.0",
          workforce_email: "alice@example.com",
          completed_at: "2026-10-10T14:30:00Z",
          score: 95.0,
          certificate_id: "CERT-999",
          evidence_id: "evi-888",
          idempotency_key: "idemp-777",
          verified_via: "hmac_webhook",
          created_at: "2026-10-10T14:31:00Z",
        },
      ];
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockCompletions,
      } as Response);

      const res = await fetchTrainingCompletions(tenantId, token);
      expect(res).toEqual(mockCompletions);
    });
  });

  describe("Error handling", () => {
    it("translates 401 to UnauthorizedError", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: "Token expired" }),
      } as Response);

      await expect(fetchTrainingCourses(tenantId, token)).rejects.toThrow(UnauthorizedError);
    });

    it("translates 403 to ForbiddenError", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: "Access denied" }),
      } as Response);

      await expect(fetchTrainingCourses(tenantId, token)).rejects.toThrow(ForbiddenError);
    });

    it("translates 404 to NotFoundError", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: "Not found" }),
      } as Response);

      await expect(fetchTrainingCourses(tenantId, token)).rejects.toThrow(NotFoundError);
    });

    it("translates 409 to ConflictError", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: async () => ({ detail: "Course conflict" }),
      } as Response);

      await expect(
        createTrainingCourse(tenantId, token, {
          course_id: "sec-101",
          title: "Title",
          description: "Desc",
        }),
      ).rejects.toThrow(ConflictError);
    });

    it("translates 422 to ValidationError", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({ detail: "Validation failed" }),
      } as Response);

      await expect(
        createTrainingAssignment(tenantId, token, {
          course_id: "sec-101",
          workforce_email: "bad",
          due_date: "invalid-date",
        }),
      ).rejects.toThrow(ValidationError);
    });

    it("translates 500 to CustomerDemoApiError", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => ({ detail: "Database failure" }),
      } as Response);

      await expect(fetchTrainingCourses(tenantId, token)).rejects.toThrow(CustomerDemoApiError);
    });
  });
});

