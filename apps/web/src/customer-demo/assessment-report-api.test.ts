import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  AssessmentReportError, downloadAssessmentReport, MAX_REPORT_BYTES, validReportContext,
  type ReportContext,
} from "./assessment-report-api";

const context: ReportContext = {
  tenantId: "00000000-0000-0000-0000-000000000001",
  adoptionId: "00000000-0000-0000-0000-000000000002",
  answerRevision: 1, selectionRevision: 2,
};
const bytes = new Uint8Array([80, 75, 3, 4, 97, 98, 99]);
// Vitest supplies the Node runtime. Avoid adding Node typings to the browser app.
const { webcrypto } = await vi.importActual<{ webcrypto: Crypto }>("node:crypto");
const sha256 = Array.from(new Uint8Array(await webcrypto.subtle.digest("SHA-256", bytes)),
  byte => byte.toString(16).padStart(2, "0")).join("");

function headers(): Record<string, string> {
  return {
    "Content-Type": "application/zip", "Content-Length": String(bytes.length),
    "Content-Disposition": 'attachment; filename="conformly-assessment-report.zip"',
    "Cache-Control": "no-store, private",
    "X-Report-Tenant-ID": context.tenantId, "X-Report-Adoption-ID": context.adoptionId,
    "X-Report-Answer-Revision": "1", "X-Report-Selection-Revision": "2", "X-Report-SHA256": sha256,
  };
}
describe("assessment report download client", () => {
  beforeEach(() => {
    vi.stubGlobal("crypto", webcrypto);
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it("uses explicit authenticated POST with exact revision pins and verifies real SHA-256", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(bytes, { headers: headers() }));
    const result = await downloadAssessmentReport(context, "private-token");
    expect(result.sha256).toBe(sha256);
    expect(result.blob.size).toBe(bytes.length);
    expect(result.filename).toBe("conformly-assessment-report.zip");
    const [url, options] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).not.toContain("private-token");
    expect(String(url)).toContain("/assessment-reports/download");
    expect(options).toMatchObject({
      method: "POST", cache: "no-store", redirect: "error", credentials: "omit",
      headers: { Authorization: "Bearer private-token" },
    });
    expect(JSON.parse(options?.body as string)).toEqual({
      adoption_id: context.adoptionId, expected_answer_revision: 1, expected_selection_revision: 2,
    });
  });

  it.each([
    ["tenantId", "../other"], ["adoptionId", ""], ["answerRevision", 0],
    ["answerRevision", 1.1], ["selectionRevision", Number.MAX_SAFE_INTEGER + 1],
  ])("rejects malformed context %s before fetch", async (key, value) => {
    const bad = { ...context, [key]: value } as ReportContext;
    expect(validReportContext(bad)).toBe(false);
    await expect(downloadAssessmentReport(bad, "token")).rejects.toMatchObject({ code: "invalid" });
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([[401, "unauthorized"], [403, "forbidden"], [409, "conflict"], [500, "unavailable"], [422, "unavailable"]])(
    "maps status %s without exposing response bodies", async (status, code) => {
      vi.mocked(fetch).mockResolvedValue(new Response("PRIVATE-SERVER-SECRET", { status: Number(status) }));
      await expect(downloadAssessmentReport(context, "token")).rejects.toMatchObject({ code, message: code });
    },
  );

  it.each([
    ["X-Report-Tenant-ID", "other"], ["X-Report-Adoption-ID", "other"],
    ["X-Report-Answer-Revision", "2"], ["X-Report-Selection-Revision", "3"],
    ["X-Report-SHA256", "not-a-hash"], ["Content-Type", "text/html"],
    ["Content-Disposition", "inline"], ["Cache-Control", "public"],
    ["Content-Length", "-1"], ["Content-Length", String(MAX_REPORT_BYTES + 1)],
    ["Content-Length", "100"],
  ])("rejects mismatching or unsafe header %s", async (key, value) => {
    vi.mocked(fetch).mockResolvedValue(new Response(bytes, { headers: { ...headers(), [key]: value } }));
    await expect(downloadAssessmentReport(context, "token")).rejects.toMatchObject({ code: "integrity" });
  });

  it("rejects missing context headers", async () => {
    const values = headers();
    delete values["X-Report-Adoption-ID"];
    vi.mocked(fetch).mockResolvedValue(new Response(bytes, { headers: values }));
    await expect(downloadAssessmentReport(context, "token")).rejects.toMatchObject({ code: "integrity" });
  });

  it("rejects an altered body with a valid original digest header", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(new Uint8Array(bytes.length), { headers: headers() }));
    await expect(downloadAssessmentReport(context, "token")).rejects.toMatchObject({ code: "integrity" });
  });

  it("bounds chunked responses without trusting Content-Length", async () => {
    const values = headers();
    delete values["Content-Length"];
    const cancel = vi.fn();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) { controller.enqueue(new Uint8Array(MAX_REPORT_BYTES + 1)); },
      cancel,
    });
    vi.mocked(fetch).mockResolvedValue(new Response(stream, { headers: values }));
    await expect(downloadAssessmentReport(context, "token")).rejects.toMatchObject({ code: "integrity" });
    expect(cancel).toHaveBeenCalled();
  });

  it("accepts a bounded chunked response with valid digest", async () => {
    const values = headers();
    delete values["Content-Length"];
    vi.mocked(fetch).mockResolvedValue(new Response(bytes, { headers: values }));
    expect((await downloadAssessmentReport(context, "token")).sha256).toBe(sha256);
  });

  it("requires crypto before starting a request", async () => {
    vi.stubGlobal("crypto", {});
    await expect(downloadAssessmentReport(context, "token")).rejects.toMatchObject({ code: "crypto" });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("rejects empty tokens before fetch", async () => {
    await expect(downloadAssessmentReport(context, " ")).rejects.toBeInstanceOf(AssessmentReportError);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("does not start an already cancelled request", async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(downloadAssessmentReport(context, "token", controller.signal)).rejects.toMatchObject({ name: "AbortError" });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("cancels an in-progress body and never returns a file", async () => {
    const controller = new AbortController();
    let onPull: (() => void) | undefined;
    const pulled = new Promise<void>(resolve => { onPull = resolve; });
    const cancel = vi.fn();
    const stream = new ReadableStream<Uint8Array>({
      pull() { onPull?.(); }, cancel,
    });
    vi.mocked(fetch).mockResolvedValue(new Response(stream, { headers: headers() }));
    const pending = downloadAssessmentReport(context, "token", controller.signal);
    await pulled;
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
    expect(cancel).toHaveBeenCalled();
  });
});

