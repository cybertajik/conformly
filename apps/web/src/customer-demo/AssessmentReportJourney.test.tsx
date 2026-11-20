import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import type { SupportedLocale } from "../i18n/types";
import { reportCopy } from "./assessment-report-copy";
import { AssessmentWorkspace } from "./AssessmentWorkspace";
import * as api from "./assessment-api";
import * as controlApi from "./control-evidence-api";
import type { AssessmentWorkListResponse, Procedure, ReadinessSummary } from "./assessment-types";

// Vitest supplies the Node runtime. Avoid adding Node typings to the browser app.
const { webcrypto } = await vi.importActual<{ webcrypto: Crypto }>("node:crypto");

const TENANT_ID = "00000000-0000-0000-0000-000000000001";
const ADOPTION_ID = "11111111-1111-1111-1111-111111111111";
const ACTOR_ID = "22222222-2222-2222-2222-222222222222";
const TOKEN = "test-token-jwt-secret";

const dummySummary: ReadinessSummary = {
  total_controls: 1,
  stale_work: 0,
  needs_information: 0,
  not_applicable: 0,
  unassessed: 1,
  unavailable_evidence: 0,
  stale_assessment: 0,
  insufficient_evidence: 0,
  fail: 0,
  partial: 0,
  pass_with_open_findings: 0,
  pass_count: 0,
  open_findings: 0,
  in_remediation_findings: 0,
  resolved_findings: 0,
  blocked_control_ids: [],
  reason_codes: [],
};

const dummyProcedure: Procedure = {
  id: "55555555-5555-4555-8555-555555555555",
  version: "1.0.0",
  digest: "a".repeat(64),
  criteria: [
    {
      id: "impl",
      title: "Implementation Verification",
      description: "Verify config",
      sequence: 1,
    },
  ],
  disclaimer: "Synthetic disclaimer",
};

const dummyResponse: AssessmentWorkListResponse = {
  tenant_id: TENANT_ID,
  adoption_id: ADOPTION_ID,
  answer_revision: 3,
  selection_revision: 2,
  is_stale: false,
  summary: dummySummary,
  items: [
    {
      work_id: "33333333-3333-4333-8333-333333333333",
      control_version_id: "44444444-4444-4444-8444-444444444444",
      work_version: 1,
      assessment_revision: 1,
      procedure: dummyProcedure,
      findings: [],
      requirement_results: [],
      primary_state: "UNASSESSED",
      latest_assessment: null,
      blockers: [],
      history: [],
    },
  ],
};

const zipBytes = new Uint8Array([80, 75, 3, 4, 10, 20, 30, 40]);
let zipSha256 = "";

function createZipResponseHeaders(overrides: Record<string, string> = {}): Record<string, string> {
  return {
    "Content-Type": "application/zip",
    "Content-Length": String(zipBytes.length),
    "Content-Disposition": 'attachment; filename="conformly-assessment-report.zip"',
    "Cache-Control": "no-store, private",
    "X-Report-Tenant-ID": TENANT_ID.toLowerCase(),
    "X-Report-Adoption-ID": ADOPTION_ID.toLowerCase(),
    "X-Report-Answer-Revision": "3",
    "X-Report-Selection-Revision": "2",
    "X-Report-SHA256": zipSha256,
    ...overrides,
  };
}

describe("AssessmentReportJourney", () => {
  let clickSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(async () => {
    vi.stubGlobal("crypto", webcrypto);
    vi.stubGlobal("fetch", vi.fn());

    const digestBuffer = await webcrypto.subtle.digest("SHA-256", zipBytes);
    zipSha256 = Array.from(new Uint8Array(digestBuffer), (b) => b.toString(16).padStart(2, "0")).join("");

    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:assessment-report") });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    vi.spyOn(api, "fetchAssessmentWorkList").mockResolvedValue(dummyResponse);
    vi.spyOn(controlApi, "fetchControlWorkList").mockResolvedValue({
      tenant_id: TENANT_ID,
      adoption_id: ADOPTION_ID,
      selection_revision: 2,
      answer_revision: 3,
      is_stale: false,
      is_current: true,
      total: 0,
      items: [],
    });
    vi.spyOn(controlApi, "fetchOwnerDirectory").mockResolvedValue({ items: [], total: 0 });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("completes a verified report download journey for an admitted compliance manager", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(zipBytes, { headers: createZipResponseHeaders() })
    );

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId={TENANT_ID}
          token={TOKEN}
          actorId={ACTOR_ID}
          adoptionId={ADOPTION_ID}
          answerRevision={3}
          selectionRevision={2}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          userRole="compliance_manager"
        />
      </I18nProvider>
    );

    // Verify workspace loaded
    await waitFor(() => {
      expect(screen.getByText("Assessment report")).toBeInTheDocument();
    });

    const downloadButton = screen.getByRole("button", { name: "Download report" });
    expect(downloadButton).not.toBeDisabled();

    // Trigger download
    fireEvent.click(downloadButton);

    // Verify loading state
    expect(screen.getByRole("button", { name: "Preparing and verifying report…" })).toBeDisabled();

    // Wait for completion
    await waitFor(() => {
      expect(clickSpy).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByRole("status")).toHaveTextContent("Download handed to your browser. Check your downloads.");
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:assessment-report");

    // Verify the fetch call had exact options
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, options] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toContain(`/v2/tenants/${TENANT_ID}/customer-demo/assessment-reports/download`);
    expect(options).toMatchObject({
      method: "POST",
      cache: "no-store",
      credentials: "omit",
      headers: {
        Authorization: `Bearer ${TOKEN}`,
        "Content-Type": "application/json",
        Accept: "application/zip",
      },
    });
    expect(JSON.parse(options?.body as string)).toEqual({
      adoption_id: ADOPTION_ID,
      expected_answer_revision: 3,
      expected_selection_revision: 2,
    });
  });

  it("denies report download for non-admitted roles (viewer / employee)", async () => {
    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId={TENANT_ID}
          token={TOKEN}
          actorId={ACTOR_ID}
          adoptionId={ADOPTION_ID}
          answerRevision={3}
          selectionRevision={2}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          userRole="viewer"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Assessment report")).toBeInTheDocument();
    });

    expect(
      screen.getByText("This session cannot download assessment reports.")
    ).toBeInTheDocument();

    const downloadButton = screen.getByRole("button", { name: "Download report" });
    expect(downloadButton).toBeDisabled();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("disables download when parent changes are unsaved", async () => {
    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId={TENANT_ID}
          token={TOKEN}
          actorId={ACTOR_ID}
          adoptionId={ADOPTION_ID}
          answerRevision={3}
          selectionRevision={2}
          hasUnsavedParentEdits={true}
          isAdoptionStale={false}
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("report-unsaved-parent-warning")).toBeInTheDocument();
    });

    expect(screen.getByText("Report download unavailable while parent changes are unsaved.")).toBeInTheDocument();
    expect(screen.getByText("Select a current adopted scope before downloading.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download report" })).toBeDisabled();
  });

  it("disables download when adoption is stale", async () => {
    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId={TENANT_ID}
          token={TOKEN}
          actorId={ACTOR_ID}
          adoptionId={ADOPTION_ID}
          answerRevision={3}
          selectionRevision={2}
          hasUnsavedParentEdits={false}
          isAdoptionStale={true}
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("report-stale-adoption-warning")).toBeInTheDocument();
    });

    expect(screen.getByText("Report download unavailable because framework adoption is stale.")).toBeInTheDocument();
    expect(screen.getByText("Select a current adopted scope before downloading.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download report" })).toBeDisabled();
  });

  it("disables download when adoption UUID is 'current' placeholder or not a valid UUID", async () => {
    vi.spyOn(api, "fetchAssessmentWorkList").mockResolvedValueOnce({
      ...dummyResponse,
      adoption_id: null,
    });

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId={TENANT_ID}
          token={TOKEN}
          actorId={ACTOR_ID}
          adoptionId="current"
          answerRevision={3}
          selectionRevision={2}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Select a current adopted scope before downloading.")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Download report" })).toBeDisabled();
  });

  it("disables download when visible revisions do not match server response context", async () => {
    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId={TENANT_ID}
          token={TOKEN}
          actorId={ACTOR_ID}
          adoptionId={ADOPTION_ID}
          answerRevision={4} // mismatch with server's 3
          selectionRevision={2}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Select a current adopted scope before downloading.")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Download report" })).toBeDisabled();
  });

  it("handles user cancellation of an in-flight report download", async () => {
    let abortControllerCaptured: AbortSignal | undefined;
    vi.mocked(fetch).mockImplementationOnce((_url, options) => {
      abortControllerCaptured = options?.signal as AbortSignal;
      return new Promise(() => {
        // never resolves to simulate pending download
      });
    });

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId={TENANT_ID}
          token={TOKEN}
          actorId={ACTOR_ID}
          adoptionId={ADOPTION_ID}
          answerRevision={3}
          selectionRevision={2}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Download report" })).not.toBeDisabled();
    });

    fireEvent.click(screen.getByRole("button", { name: "Download report" }));

    const cancelButton = screen.getByRole("button", { name: "Cancel" });
    expect(cancelButton).toBeInTheDocument();

    fireEvent.click(cancelButton);

    expect(abortControllerCaptured?.aborted).toBe(true);
    expect(screen.getByRole("button", { name: "Download report" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel" })).toBeNull();
  });

  it("handles 401 Unauthorized by invoking onSessionExpired", async () => {
    const onSessionExpired = vi.fn();
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Unauthorized" }), { status: 401 })
    );

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId={TENANT_ID}
          token={TOKEN}
          actorId={ACTOR_ID}
          adoptionId={ADOPTION_ID}
          answerRevision={3}
          selectionRevision={2}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          userRole="owner"
          onSessionExpired={onSessionExpired}
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Download report" })).not.toBeDisabled();
    });

    fireEvent.click(screen.getByRole("button", { name: "Download report" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Your session expired. Sign in again.");
    });
    expect(onSessionExpired).toHaveBeenCalledTimes(1);
  });

  it("handles 409 Conflict with appropriate error banner", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Conflict" }), { status: 409 })
    );

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId={TENANT_ID}
          token={TOKEN}
          actorId={ACTOR_ID}
          adoptionId={ADOPTION_ID}
          answerRevision={3}
          selectionRevision={2}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Download report" })).not.toBeDisabled();
    });

    fireEvent.click(screen.getByRole("button", { name: "Download report" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("The scope changed or is unavailable. Refresh the workspace before retrying.");
    });
  });

  it("rejects download with integrity error when SHA-256 does not match header", async () => {
    const corruptedHash = "f".repeat(64);
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(zipBytes, { headers: createZipResponseHeaders({ "X-Report-SHA256": corruptedHash }) })
    );

    render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId={TENANT_ID}
          token={TOKEN}
          actorId={ACTOR_ID}
          adoptionId={ADOPTION_ID}
          answerRevision={3}
          selectionRevision={2}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Download report" })).not.toBeDisabled();
    });

    fireEvent.click(screen.getByRole("button", { name: "Download report" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("The report could not be verified. No file was downloaded.");
    });
    expect(clickSpy).not.toHaveBeenCalled();
  });

  it.each([
    ["en", reportCopy.en.title],
    ["de", reportCopy.de.title],
    ["fr", reportCopy.fr.title],
    ["nl", reportCopy.nl.title],
    ["es", reportCopy.es.title],
  ] as const)("renders the report panel correctly in locale %s", async (loc: SupportedLocale, expectedTitle: string) => {
    localStorage.setItem("conformly.locale", loc);
    const { unmount } = render(
      <I18nProvider>
        <AssessmentWorkspace
          tenantId={TENANT_ID}
          token={TOKEN}
          actorId={ACTOR_ID}
          adoptionId={ADOPTION_ID}
          answerRevision={3}
          selectionRevision={2}
          hasUnsavedParentEdits={false}
          isAdoptionStale={false}
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: expectedTitle, level: 2 })).toBeInTheDocument();
    });

    unmount();
  });
});
