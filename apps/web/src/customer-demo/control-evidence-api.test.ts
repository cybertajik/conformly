import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ConflictError,
  ForbiddenError,
  NotFoundError,
  UnauthorizedError,
  ValidationError,
} from "./api";
import {
  createEvidence,
  fetchControlWorkList,
  fetchOwnerDirectory,
  initializeControlWork,
  patchControlWork,
  PayloadTooLargeError,
  ServiceUnavailableError,
  uploadEvidenceFile,
} from "./control-evidence-api";
import {
  MutationReceipt,
  OwnerDirectoryResponse,
  WorkListResponse,
} from "./control-evidence-types";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("control evidence API client", () => {
  it("fetches control work list with Bearer token and optional adoption_id", async () => {
    const mockRes: WorkListResponse = {
      tenant_id: "tenant-1",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      items: [],
      total: 0,
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockRes), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchControlWorkList("tenant-1", "test-token", "adopt-1");
    expect(result).toEqual(mockRes);

    const call = fetchMock.mock.calls[0];
    expect(call[0]).toContain("/v2/tenants/tenant-1/customer-demo/control-work?adoption_id=adopt-1");
    expect(call[1].headers.Authorization).toBe("Bearer test-token");
  });

  it("fetches owner directory with Bearer token", async () => {
    const mockRes: OwnerDirectoryResponse = {
      items: [{ user_id: "u-1", display_name: "Alice Owner" }],
      total: 1,
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockRes), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchOwnerDirectory("tenant-1", "test-token");
    expect(result).toEqual(mockRes);
    expect(fetchMock.mock.calls[0][0]).toContain("/v2/tenants/tenant-1/customer-demo/control-work/owners");
  });

  it("initializes control work via POST", async () => {
    const mockRes: WorkListResponse = {
      tenant_id: "tenant-1",
      adoption_id: "adopt-1",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      items: [],
      total: 0,
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockRes), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const payload = {
      operation_id: "op-1",
      adoption_id: "adopt-1",
      expected_selection_revision: 1,
      expected_answer_revision: 1,
    };

    const result = await initializeControlWork("tenant-1", "test-token", payload);
    expect(result).toEqual(mockRes);
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(payload);
  });

  it("patches control work assignment via PATCH", async () => {
    const mockReceipt: MutationReceipt = {
      operation_id: "op-2",
      event_id: "ev-1",
      applied_work_version: 2,
      replayed: false,
      current_work: {
        id: "w-1",
        adoption_id: "adopt-1",
        control_id: "c-1",
        control_version_id: "cv-1",
        title: "Test Control",
        provenance: "Synthetic Pack",
        pack_version: 1,
        bundle_digest: "digest",
        requirement_results: [],
        owner_user_id: "u-1",
        owner_display_name: "Alice Owner",
        due_date: "2026-12-31",
        version: 2,
        is_current: true,
        is_stale: false,
        links: [],
      },
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockReceipt), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const payload = {
      operation_id: "op-2",
      expected_selection_revision: 1,
      expected_answer_revision: 1,
      expected_work_version: 1,
      owner_user_id: "u-1",
      due_date: "2026-12-31",
    };

    const result = await patchControlWork("tenant-1", "test-token", "w-1", payload);
    expect(result).toEqual(mockReceipt);
    expect(fetchMock.mock.calls[0][1].method).toBe("PATCH");
  });

  it("uploads evidence file to /v1/tenants/{tenant_id}/files", async () => {
    const fileRes = { id: "file-1", original_filename: "test.txt", plaintext_size_bytes: 100 };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(fileRes), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const dummyFile = new File(["dummy content"], "test.txt", { type: "text/plain" });
    const result = await uploadEvidenceFile("tenant-1", "test-token", dummyFile);
    expect(result).toEqual(fileRes);
    expect(fetchMock.mock.calls[0][0]).toContain("/v1/tenants/tenant-1/files");
  });

  it("creates and pins evidence via POST", async () => {
    const mockReceipt: MutationReceipt = {
      operation_id: "op-3",
      event_id: "ev-2",
      applied_work_version: 3,
      replayed: false,
      current_work: {
        id: "w-1",
        adoption_id: "adopt-1",
        control_id: "c-1",
        control_version_id: "cv-1",
        title: "Test Control",
        provenance: "Synthetic Pack",
        pack_version: 1,
        bundle_digest: "digest",
        requirement_results: [],
        owner_user_id: "u-1",
        owner_display_name: "Alice Owner",
        due_date: "2026-12-31",
        version: 3,
        is_current: true,
        is_stale: false,
        links: [],
      },
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockReceipt), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const payload = {
      operation_id: "op-3",
      expected_selection_revision: 1,
      expected_answer_revision: 1,
      expected_work_version: 2,
      file_id: "file-1",
      valid_until: null,
      rationale: "Valid rationale",
    };

    const result = await createEvidence("tenant-1", "test-token", "w-1", payload);
    expect(result).toEqual(mockReceipt);
    expect(fetchMock.mock.calls[0][0]).toContain("/v2/tenants/tenant-1/customer-demo/control-work/w-1/evidence");
  });

  it("handles error statuses correctly (401, 403, 404, 409, 413, 422, 503)", async () => {
    const makeErrorMock = (status: number, detail: string) =>
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail }), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
      );

    vi.stubGlobal("fetch", makeErrorMock(401, "Token expired"));
    await expect(fetchControlWorkList("t-1", "tok")).rejects.toThrow(UnauthorizedError);

    vi.stubGlobal("fetch", makeErrorMock(403, "Forbidden"));
    await expect(fetchControlWorkList("t-1", "tok")).rejects.toThrow(ForbiddenError);

    vi.stubGlobal("fetch", makeErrorMock(404, "Not Found"));
    await expect(fetchControlWorkList("t-1", "tok")).rejects.toThrow(NotFoundError);

    vi.stubGlobal("fetch", makeErrorMock(409, "Version mismatch"));
    await expect(fetchControlWorkList("t-1", "tok")).rejects.toThrow(ConflictError);

    vi.stubGlobal("fetch", makeErrorMock(413, "File too large"));
    await expect(fetchControlWorkList("t-1", "tok")).rejects.toThrow(PayloadTooLargeError);

    vi.stubGlobal("fetch", makeErrorMock(422, "Malformed payload"));
    await expect(fetchControlWorkList("t-1", "tok")).rejects.toThrow(ValidationError);

    vi.stubGlobal("fetch", makeErrorMock(503, "ClamAV scanner unavailable"));
    await expect(fetchControlWorkList("t-1", "tok")).rejects.toThrow(ServiceUnavailableError);
  });
});
