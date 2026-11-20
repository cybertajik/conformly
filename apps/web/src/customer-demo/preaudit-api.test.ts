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
  MAX_PREAUDIT_REPORT_BYTES,
  approvePreauditCase,
  cancelPreauditCase,
  createPreauditCase,
  downloadPreauditReport,
  fetchPreauditActors,
  freezePreauditScope,
  getPreauditCase,
  getPreauditHistory,
  listPreauditCases,
  recordReviewDecision,
  submitPreauditReview,
} from "./preaudit-api";

describe("preaudit-api", () => {
  const tenantId = "11111111-1111-1111-1111-111111111111";
  const caseId = "22222222-2222-2222-2222-222222222222";
  const snapshotId = "33333333-3333-3333-3333-333333333333";
  const token = "mock-token-secret";

  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("fetchPreauditActors", () => {
    it("returns actors array on success", async () => {
      const mockActors = [
        {
          user_id: "u-1",
          email: "owner@test.com",
          display_name: "Test Owner",
          role: "owner",
        },
      ];
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ actors: mockActors }),
      } as Response);

      const res = await fetchPreauditActors(tenantId, token);
      expect(res).toEqual(mockActors);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/v2/tenants/${tenantId}/customer-demo/preaudits/actors`),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
          }),
        }),
      );
    });

    it("throws UnauthorizedError on 401", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: "Unauthorized" }),
      } as Response);

      await expect(fetchPreauditActors(tenantId, token)).rejects.toThrow(UnauthorizedError);
    });
  });

  describe("listPreauditCases", () => {
    it("returns case list on success", async () => {
      const mockList = {
        items: [
          {
            id: caseId,
            tenant_id: tenantId,
            adoption_id: "adopt-1",
            pack_name: "soc2",
            pack_version: "2026.1",
            status: "DRAFT",
            title: "Q4 Audit",
            lead_user_id: "u-1",
            lead_name: "Lead",
            reviewer_user_id: "u-2",
            reviewer_name: "Reviewer",
            revision: 1,
            is_scope_current: true,
            is_review_current: true,
            blockers: [],
            created_at: "2026-11-01T00:00:00Z",
            updated_at: "2026-11-01T00:00:00Z",
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      };
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockList,
      } as Response);

      const res = await listPreauditCases(tenantId, token);
      expect(res).toEqual(mockList);
    });
  });

  describe("getPreauditCase", () => {
    it("returns single case detail", async () => {
      const mockCase = {
        id: caseId,
        tenant_id: tenantId,
        status: "DRAFT",
        revision: 1,
        blockers: [],
      };
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockCase,
      } as Response);

      const res = await getPreauditCase(tenantId, caseId, token);
      expect(res).toEqual(mockCase);
    });

    it("throws NotFoundError on 404", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: "Case not found" }),
      } as Response);

      await expect(getPreauditCase(tenantId, caseId, token)).rejects.toThrow(NotFoundError);
    });
  });

  describe("createPreauditCase", () => {
    it("creates a case with 201 status", async () => {
      const payload = {
        operation_id: "op-1",
        adoption_id: "adopt-1",
        title: "SOC2 Audit",
        description: "Annual readiness",
        lead_user_id: "u-1",
        reviewer_user_id: "u-2",
      };
      const mockCreated = { id: caseId, status: "DRAFT", ...payload };
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => mockCreated,
      } as Response);

      const res = await createPreauditCase(tenantId, payload, token);
      expect(res).toEqual(mockCreated);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/v2/tenants/${tenantId}/customer-demo/preaudits`),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(payload),
        }),
      );
    });

    it("throws ValidationError on 422", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({ detail: "Invalid reviewer" }),
      } as Response);

      await expect(
        createPreauditCase(
          tenantId,
          {
            operation_id: "op-bad",
            adoption_id: "adopt-1",
            lead_user_id: "u-1",
            reviewer_user_id: "u-1",
          },
          token,
        ),
      ).rejects.toThrow(ValidationError);
    });
  });

  describe("freezePreauditScope", () => {
    it("freezes scope and returns updated case", async () => {
      const mockUpdated = { id: caseId, status: "FROZEN", revision: 2 };
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUpdated,
      } as Response);

      const payload = { operation_id: "op-2", expected_revision: 1 };
      const res = await freezePreauditScope(tenantId, caseId, payload, token);
      expect(res).toEqual(mockUpdated);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/v2/tenants/${tenantId}/customer-demo/preaudits/${caseId}/freeze`),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(payload),
        }),
      );
    });

    it("throws ConflictError on 409", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: async () => ({ detail: "Revision conflict" }),
      } as Response);

      await expect(
        freezePreauditScope(tenantId, caseId, { operation_id: "op-2", expected_revision: 1 }, token),
      ).rejects.toThrow(ConflictError);
    });
  });

  describe("submitPreauditReview", () => {
    it("submits for review", async () => {
      const mockUpdated = { id: caseId, status: "IN_REVIEW", revision: 3 };
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUpdated,
      } as Response);

      const payload = { operation_id: "op-3", expected_revision: 2 };
      const res = await submitPreauditReview(tenantId, caseId, payload, token);
      expect(res).toEqual(mockUpdated);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/v2/tenants/${tenantId}/customer-demo/preaudits/${caseId}/submit`),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(payload),
        }),
      );
    });
  });

  describe("recordReviewDecision", () => {
    it("records acceptance decision", async () => {
      const payload = {
        operation_id: "op-4",
        expected_revision: 3,
        decision: "ACCEPT" as const,
        snapshot_id: snapshotId,
        snapshot_digest: "a".repeat(64),
        notes: "Looks good",
      };
      const mockUpdated = { id: caseId, status: "REVIEWED", revision: 4 };
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUpdated,
      } as Response);

      const res = await recordReviewDecision(tenantId, caseId, payload, token);
      expect(res).toEqual(mockUpdated);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/v2/tenants/${tenantId}/customer-demo/preaudits/${caseId}/review`),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(payload),
        }),
      );
    });

    it("throws ForbiddenError on 403 when self-reviewing", async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: "Assigned lead cannot act as reviewer" }),
      } as Response);

      await expect(
        recordReviewDecision(
          tenantId,
          caseId,
          {
            operation_id: "op-5",
            expected_revision: 3,
            decision: "ACCEPT",
            snapshot_id: snapshotId,
            snapshot_digest: "a".repeat(64),
            notes: "Self approval attempt",
          },
          token,
        ),
      ).rejects.toThrow(ForbiddenError);
    });
  });

  describe("approvePreauditCase", () => {
    it("approves preaudit case", async () => {
      const payload = {
        operation_id: "op-6",
        expected_revision: 4,
        snapshot_id: snapshotId,
        snapshot_digest: "a".repeat(64),
        approval_notes: "Approved by Owner",
      };
      const mockUpdated = { id: caseId, status: "APPROVED", revision: 5 };
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUpdated,
      } as Response);

      const res = await approvePreauditCase(tenantId, caseId, payload, token);
      expect(res).toEqual(mockUpdated);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/v2/tenants/${tenantId}/customer-demo/preaudits/${caseId}/approve`),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(payload),
        }),
      );
    });
  });

  describe("cancelPreauditCase", () => {
    it("cancels preaudit case", async () => {
      const payload = {
        operation_id: "op-7",
        expected_revision: 5,
        reason: "Customer requested cancellation",
      };
      const mockUpdated = { id: caseId, status: "CANCELLED", revision: 6 };
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUpdated,
      } as Response);

      const res = await cancelPreauditCase(tenantId, caseId, payload, token);
      expect(res).toEqual(mockUpdated);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/v2/tenants/${tenantId}/customer-demo/preaudits/${caseId}/cancel`),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(payload),
        }),
      );
    });
  });

  describe("getPreauditHistory", () => {
    it("returns history events array", async () => {
      const mockHistory = {
        preaudit_id: caseId,
        events: [
          {
            id: "e-1",
            tenant_id: tenantId,
            preaudit_id: caseId,
            revision: 1,
            operation_id: "op-1",
            event_type: "CREATED",
            actor_user_id: "u-1",
            prior_status: null,
            new_status: "DRAFT",
            payload: {},
            created_at: "2026-11-01T00:00:00Z",
          },
        ],
      };
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockHistory,
      } as Response);

      const res = await getPreauditHistory(tenantId, caseId, token);
      expect(res).toEqual(mockHistory);
    });
  });

  describe("downloadPreauditReport", () => {
    const rawBytes = new Uint8Array([80, 75, 3, 4, 10, 0, 0, 0, 0, 0]);
    const mockSnapshotDigest = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
    let reportSha: string;

    const validPayload = {
      expected_revision: 3,
      snapshot_id: snapshotId,
      expected_snapshot_digest: mockSnapshotDigest,
    };

    beforeEach(async () => {
      const hashBuffer = await globalThis.crypto.subtle.digest("SHA-256", rawBytes.buffer as ArrayBuffer);
      reportSha = Array.from(new Uint8Array(hashBuffer), (b) => b.toString(16).padStart(2, "0")).join("");
    });

    function validReportHeaders(overrides: Record<string, string> = {}): Headers {
      return new Headers({
        "content-type": "application/zip",
        "cache-control": "private, no-store",
        "content-disposition": 'attachment; filename="preaudit-report-custom.zip"',
        "x-preaudit-id": caseId,
        "x-preaudit-snapshot-digest": mockSnapshotDigest,
        "x-report-sha256": reportSha,
        "content-length": String(rawBytes.byteLength),
        ...overrides,
      });
    }

    it("downloads blob and extracts headers and filename", async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response(rawBytes, {
        headers: validReportHeaders(),
      }));

      const res = await downloadPreauditReport(tenantId, caseId, validPayload, token);
      expect(res.filename).toBe("preaudit-report-custom.zip");
      expect(res.snapshotDigest).toBe(mockSnapshotDigest);
      expect(res.sha256).toBe(reportSha);
      expect(res.blob.size).toBe(rawBytes.byteLength);
    });

    it("verifies POST body sent to server contains only expected_revision and snapshot_id (not expected_snapshot_digest)", async () => {
      vi.mocked(fetch).mockResolvedValueOnce(new Response(rawBytes, {
        headers: validReportHeaders(),
      }));

      await downloadPreauditReport(tenantId, caseId, validPayload, token);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/v2/tenants/${tenantId}/customer-demo/preaudits/${caseId}/report/download`),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            expected_revision: validPayload.expected_revision,
            snapshot_id: validPayload.snapshot_id,
          }),
        }),
      );
    });

    it("rejects when missing expected_snapshot_digest in payload before fetch", async () => {
      await expect(
        downloadPreauditReport(
          tenantId,
          caseId,
          { expected_revision: 3, snapshot_id: snapshotId, expected_snapshot_digest: "" },
          token,
        ),
      ).rejects.toThrow("Missing required expected_snapshot_digest for report verification");
      expect(fetch).not.toHaveBeenCalled();
    });

    it("rejects when missing snapshot_id in payload before fetch", async () => {
      await expect(
        downloadPreauditReport(
          tenantId,
          caseId,
          { expected_revision: 3, snapshot_id: "", expected_snapshot_digest: mockSnapshotDigest },
          token,
        ),
      ).rejects.toThrow("Missing required snapshot_id for report download");
      expect(fetch).not.toHaveBeenCalled();
    });

    it("falls back to default filename if content-disposition is absent", async () => {
      const headers = validReportHeaders();
      headers.delete("content-disposition");

      vi.mocked(fetch).mockResolvedValueOnce(new Response(rawBytes, {
        headers,
      }));

      const res = await downloadPreauditReport(tenantId, caseId, validPayload, token);
      expect(res.filename).toBe(`preaudit-report-${caseId.slice(0, 8)}.zip`);
      expect(res.snapshotDigest).toBe(mockSnapshotDigest);
    });

    it("rejects when X-Preaudit-Id response header is missing (never substitutes request case ID)", async () => {
      const headers = validReportHeaders();
      headers.delete("x-preaudit-id");
      vi.mocked(fetch).mockResolvedValueOnce(new Response(rawBytes, { headers }));

      await expect(
        downloadPreauditReport(tenantId, caseId, validPayload, token),
      ).rejects.toThrow("Missing X-Preaudit-Id header in report response");
    });

    it("rejects mismatched case ID in header", async () => {
      const headers = validReportHeaders({ "x-preaudit-id": "other-case-id" });
      vi.mocked(fetch).mockResolvedValueOnce(new Response(rawBytes, { headers }));

      await expect(
        downloadPreauditReport(tenantId, caseId, validPayload, token),
      ).rejects.toThrow(CustomerDemoApiError);
    });

    it("rejects when X-Preaudit-Snapshot-Digest response header is missing", async () => {
      const headers = validReportHeaders();
      headers.delete("x-preaudit-snapshot-digest");
      vi.mocked(fetch).mockResolvedValueOnce(new Response(rawBytes, { headers }));

      await expect(
        downloadPreauditReport(tenantId, caseId, validPayload, token),
      ).rejects.toThrow("Missing X-Preaudit-Snapshot-Digest header in report response");
    });

    it("rejects correctly hashed archive when X-Preaudit-Snapshot-Digest mismatches expected_snapshot_digest", async () => {
      const headers = validReportHeaders({
        "x-preaudit-snapshot-digest": "different-snapshot-digest-from-wrong-snapshot",
      });
      vi.mocked(fetch).mockResolvedValueOnce(new Response(rawBytes, { headers }));

      await expect(
        downloadPreauditReport(tenantId, caseId, validPayload, token),
      ).rejects.toThrow("Mismatched snapshot digest in report header");
    });

    it("rejects invalid content-type", async () => {
      const headers = validReportHeaders({ "content-type": "text/html" });
      vi.mocked(fetch).mockResolvedValueOnce(new Response(rawBytes, { headers }));

      await expect(
        downloadPreauditReport(tenantId, caseId, validPayload, token),
      ).rejects.toThrow("Invalid content type; expected application/zip");
    });

    it("rejects missing no-store cache control", async () => {
      const headers = validReportHeaders({ "cache-control": "public, max-age=3600" });
      vi.mocked(fetch).mockResolvedValueOnce(new Response(rawBytes, { headers }));

      await expect(
        downloadPreauditReport(tenantId, caseId, validPayload, token),
      ).rejects.toThrow("Missing private no-store cache policy");
    });

    it("rejects missing or malformed X-Report-SHA256 header", async () => {
      const headers = validReportHeaders({ "x-report-sha256": "bad-hash" });
      vi.mocked(fetch).mockResolvedValueOnce(new Response(rawBytes, { headers }));

      await expect(
        downloadPreauditReport(tenantId, caseId, validPayload, token),
      ).rejects.toThrow("Missing or malformed X-Report-SHA256 header");
    });

    it("rejects tampered byte payload where hash mismatches", async () => {
      const tamperedBytes = new Uint8Array([80, 75, 3, 4, 99, 99, 99]);
      const headers = validReportHeaders({
        "x-report-sha256": reportSha,
        "content-length": String(tamperedBytes.byteLength),
      });
      vi.mocked(fetch).mockResolvedValueOnce(new Response(tamperedBytes, { headers }));

      await expect(
        downloadPreauditReport(tenantId, caseId, validPayload, token),
      ).rejects.toThrow("Report archive SHA-256 integrity verification failed");
    });

    it("rejects oversized declared Content-Length", async () => {
      const headers = validReportHeaders({ "content-length": String(MAX_PREAUDIT_REPORT_BYTES + 1) });
      vi.mocked(fetch).mockResolvedValueOnce(new Response(rawBytes, { headers }));

      await expect(
        downloadPreauditReport(tenantId, caseId, validPayload, token),
      ).rejects.toThrow("Invalid or excessive report Content-Length");
    });

    it("rejects streamed body exceeding 8 MiB bound", async () => {
      const cancel = vi.fn();
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new Uint8Array(MAX_PREAUDIT_REPORT_BYTES + 1));
        },
        cancel,
      });
      const headers = validReportHeaders();
      headers.delete("content-length");
      vi.mocked(fetch).mockResolvedValueOnce(new Response(stream, { headers }));

      await expect(
        downloadPreauditReport(tenantId, caseId, validPayload, token),
      ).rejects.toThrow("Report archive exceeded finite 8 MiB bound");
    });

    it("rejects unsafe filename containing path traversal", async () => {
      const headers = validReportHeaders({
        "content-disposition": 'attachment; filename="../../etc/passwd.zip"',
      });
      vi.mocked(fetch).mockResolvedValueOnce(new Response(rawBytes, { headers }));

      await expect(
        downloadPreauditReport(tenantId, caseId, validPayload, token),
      ).rejects.toThrow("Unsafe filename in Content-Disposition");
    });

    it("rejects non-attachment Content-Disposition", async () => {
      const headers = validReportHeaders({
        "content-disposition": 'inline; filename="report.zip"',
      });
      vi.mocked(fetch).mockResolvedValueOnce(new Response(rawBytes, { headers }));

      await expect(
        downloadPreauditReport(tenantId, caseId, validPayload, token),
      ).rejects.toThrow("Invalid Content-Disposition; must be attachment");
    });

    it("cancels response body stream when header validation fails", async () => {
      const cancelMock = vi.fn();
      const stream = new ReadableStream<Uint8Array>({
        cancel: cancelMock,
      });
      const headers = validReportHeaders({ "content-type": "text/plain" });
      vi.mocked(fetch).mockResolvedValueOnce(new Response(stream, { headers }));

      await expect(
        downloadPreauditReport(tenantId, caseId, validPayload, token),
      ).rejects.toThrow("Invalid content type; expected application/zip");
      expect(cancelMock).toHaveBeenCalled();
    });

    it("does not start fetch if signal is already aborted", async () => {
      const ac = new AbortController();
      ac.abort();

      await expect(
        downloadPreauditReport(tenantId, caseId, validPayload, token, ac.signal),
      ).rejects.toThrow("Request cancelled");
      expect(fetch).not.toHaveBeenCalled();
    });
  });
});
