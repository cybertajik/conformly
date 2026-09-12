import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AccessDeniedError,
  SessionExpiredError,
  downloadStoredFile,
  listMyTenants,
  listStoredFiles,
  uploadStoredFile,
  verifyTenant,
} from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("typed API client", () => {
  it("maps expired sessions without exposing response details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    await expect(listMyTenants("secret-token")).rejects.toBeInstanceOf(SessionExpiredError);
  });

  it("maps server-side tenant authorization denial", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 403 })));
    await expect(verifyTenant("secret-token", "tenant-id")).rejects.toBeInstanceOf(
      AccessDeniedError,
    );
  });

  it("handles stored file upload with FormData multipart headers", async () => {
    const mockFileResponse = {
      id: "file-123",
      tenant_id: "t-1",
      created_by_user_id: "u-1",
      original_filename: "policy.pdf",
      content_type: "application/pdf",
      classification: "Confidential",
      plaintext_size_bytes: 1024,
      plaintext_sha256: "abc",
      created_at: new Date().toISOString(),
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockFileResponse), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const blob = new Blob(["dummy content"], { type: "application/pdf" });
    const result = await uploadStoredFile("token-123", "tenant-456", blob, "policy.pdf", "Confidential");

    expect(result.id).toBe("file-123");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/v1/tenants/tenant-456/files");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    // Crucial: Content-Type must not be overridden to application/json on FormData
    expect(init.headers["Content-Type"]).toBeUndefined();
  });

  it("handles stored file download blob", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("binary payload content", {
        status: 200,
        headers: { "Content-Type": "application/octet-stream" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const blob = await downloadStoredFile("token-123", "tenant-456", "file-789");
    expect(blob).toBeDefined();
    expect(blob.size).toBeGreaterThan(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/v1/tenants/tenant-456/files/file-789/download");
  });

  it("handles listing stored files", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([{ id: "file-1" }, { id: "file-2" }]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const files = await listStoredFiles("token-123", "tenant-456");
    expect(files).toHaveLength(2);
    expect(files[0].id).toBe("file-1");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/v1/tenants/tenant-456/files");
  });
});
