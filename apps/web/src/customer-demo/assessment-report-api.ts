import { getApiBaseUrl } from "./api";

export const MAX_REPORT_BYTES = 8 * 1024 * 1024;
export type ReportErrorCode = "invalid" | "unauthorized" | "forbidden" | "conflict" | "unavailable" | "integrity" | "crypto";
export class AssessmentReportError extends Error {
  constructor(public readonly code: ReportErrorCode) {
    super(code);
    this.name = "AssessmentReportError";
  }
}
export interface ReportContext {
  tenantId: string;
  adoptionId: string;
  answerRevision: number;
  selectionRevision: number;
}
export interface DownloadedAssessmentReport {
  blob: Blob;
  sha256: string;
  filename: "conformly-assessment-report.zip";
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function validReportContext(context: ReportContext): boolean {
  return uuid.test(context.tenantId) && uuid.test(context.adoptionId)
    && Number.isSafeInteger(context.answerRevision) && context.answerRevision > 0
    && Number.isSafeInteger(context.selectionRevision) && context.selectionRevision > 0;
}

function checkAbort(signal?: AbortSignal) {
  if (signal?.aborted) throw new DOMException("Request cancelled", "AbortError");
}

async function boundedBody(response: Response, signal?: AbortSignal): Promise<Uint8Array<ArrayBuffer>> {
  const length = response.headers.get("Content-Length");
  if (length !== null && (!/^[0-9]+$/.test(length) || Number(length) > MAX_REPORT_BYTES)) {
    throw new AssessmentReportError("integrity");
  }
  if (!response.body) throw new AssessmentReportError("integrity");
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  const cancel = () => { void reader.cancel().catch(() => undefined); };
  signal?.addEventListener("abort", cancel, { once: true });
  try {
    while (true) {
      checkAbort(signal);
      const next = await reader.read();
      checkAbort(signal);
      if (next.done) break;
      size += next.value.byteLength;
      if (size > MAX_REPORT_BYTES) throw new AssessmentReportError("integrity");
      chunks.push(next.value);
    }
  } finally {
    signal?.removeEventListener("abort", cancel);
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
  if (!size || (length !== null && Number(length) !== size)) throw new AssessmentReportError("integrity");
  const result = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.byteLength; }
  return result;
}

export async function downloadAssessmentReport(
  context: ReportContext, token: string, signal?: AbortSignal,
): Promise<DownloadedAssessmentReport> {
  if (!validReportContext(context) || !token.trim()) throw new AssessmentReportError("invalid");
  checkAbort(signal);
  if (!globalThis.crypto?.subtle) throw new AssessmentReportError("crypto");
  const response = await fetch(
    `${getApiBaseUrl()}/v2/tenants/${encodeURIComponent(context.tenantId)}/customer-demo/assessment-reports/download`,
    {
      method: "POST", signal, cache: "no-store", credentials: "omit", redirect: "error",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", Accept: "application/zip" },
      body: JSON.stringify({
        adoption_id: context.adoptionId, expected_answer_revision: context.answerRevision,
        expected_selection_revision: context.selectionRevision,
      }),
    },
  );
  try {
  checkAbort(signal);
  if (!response.ok) {
    const codes: Record<number, ReportErrorCode> = { 401: "unauthorized", 403: "forbidden", 409: "conflict" };
    // Never display arbitrary server bodies, authentication diagnostics or narratives.
    throw new AssessmentReportError(codes[response.status] ?? "unavailable");
  }
  const matches = response.headers.get("X-Report-Tenant-ID") === context.tenantId.toLowerCase()
    && response.headers.get("X-Report-Adoption-ID") === context.adoptionId.toLowerCase()
    && response.headers.get("X-Report-Answer-Revision") === String(context.answerRevision)
    && response.headers.get("X-Report-Selection-Revision") === String(context.selectionRevision);
  const digest = response.headers.get("X-Report-SHA256");
  if (!matches || !digest || !/^[a-f0-9]{64}$/.test(digest)
    || response.headers.get("Content-Type")?.split(";")[0].trim().toLowerCase() !== "application/zip"
    || response.headers.get("Content-Disposition") !== 'attachment; filename="conformly-assessment-report.zip"'
    || !response.headers.get("Cache-Control")?.includes("no-store")) {
    throw new AssessmentReportError("integrity");
  }
  const bytes = await boundedBody(response, signal);
  checkAbort(signal);
  const hash = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  checkAbort(signal);
  const actual = Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, "0")).join("");
  if (actual !== digest) throw new AssessmentReportError("integrity");
  return { blob: new Blob([bytes], { type: "application/zip" }), sha256: actual, filename: "conformly-assessment-report.zip" };
  } catch (error) {
    // Stop consuming a rejected response, including errors before body validation.
    await response.body?.cancel().catch(() => undefined);
    throw error;
  }
}

