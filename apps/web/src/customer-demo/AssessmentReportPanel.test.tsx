import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AssessmentReportPanel, type AssessmentReportPanelProps } from "./AssessmentReportPanel";
import * as api from "./assessment-report-api";
import { reportCopy } from "./assessment-report-copy";
import type { SupportedLocale } from "../i18n/types";

vi.mock("./assessment-report-api", async importOriginal => {
  const actual = await importOriginal<typeof import("./assessment-report-api")>();
  return { ...actual, downloadAssessmentReport: vi.fn() };
});
const props: AssessmentReportPanelProps = {
  tenantId: "00000000-0000-0000-0000-000000000001", adoptionId: "00000000-0000-0000-0000-000000000002",
  actorId: "owner-a", token: "token-a", answerRevision: 1, selectionRevision: 2,
  admitted: true, locale: "en",
};
const report: api.DownloadedAssessmentReport = {
  blob: new Blob(["verified"], { type: "application/zip" }), sha256: "a".repeat(64),
  filename: "conformly-assessment-report.zip",
};
function deferred() {
  let resolve!: (value: api.DownloadedAssessmentReport) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<api.DownloadedAssessmentReport>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

describe("AssessmentReportPanel", () => {
  let click: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    vi.mocked(api.downloadAssessmentReport).mockReset();
    vi.mocked(api.downloadAssessmentReport).mockResolvedValue(report);
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:report") });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("requires a user click, downloads once and releases its object URL", async () => {
    render(<AssessmentReportPanel {...props} />);
    expect(api.downloadAssessmentReport).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Download report" }));
    await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
    expect(api.downloadAssessmentReport).toHaveBeenCalledWith({
      tenantId: props.tenantId, adoptionId: props.adoptionId, answerRevision: 1, selectionRevision: 2,
    }, props.token, expect.any(AbortSignal));
    expect(screen.getByRole("status")).toHaveTextContent("handed to your browser");
    await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:report"));
    expect(document.querySelector("a[download]")).toBeNull();
  });

  it("does not submit twice while already in flight", async () => {
    const pending = deferred();
    vi.mocked(api.downloadAssessmentReport).mockReturnValue(pending.promise);
    render(<AssessmentReportPanel {...props} />);
    const button = screen.getByRole("button", { name: "Download report" });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(api.downloadAssessmentReport).toHaveBeenCalledTimes(1);
    await act(async () => pending.resolve(report));
  });

  it.each([
    { tenantId: "00000000-0000-0000-0000-000000000099" },
    { adoptionId: "00000000-0000-0000-0000-000000000099" },
    { answerRevision: 2 }, { selectionRevision: 3 }, { actorId: "owner-b" },
    { token: "token-b" }, { admitted: false },
  ])("discards a late response after context changes: %j", async change => {
    const pending = deferred();
    vi.mocked(api.downloadAssessmentReport).mockReturnValue(pending.promise);
    const view = render(<AssessmentReportPanel {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Download report" }));
    const signal = vi.mocked(api.downloadAssessmentReport).mock.calls[0][2];
    view.rerender(<AssessmentReportPanel {...props} {...change} />);
    expect(signal?.aborted).toBe(true);
    await act(async () => pending.resolve(report));
    expect(click).not.toHaveBeenCalled();
    expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(screen.queryByText(/handed to your browser/)).toBeNull();
  });

  it("ignores an obsolete unauthorized response without expiring the new session", async () => {
    const pending = deferred();
    vi.mocked(api.downloadAssessmentReport).mockReturnValue(pending.promise);
    const expired = vi.fn();
    const view = render(<AssessmentReportPanel {...props} onSessionExpired={expired} />);
    fireEvent.click(screen.getByRole("button", { name: "Download report" }));
    view.rerender(<AssessmentReportPanel {...props} token="new-session" onSessionExpired={expired} />);
    await act(async () => pending.reject(new api.AssessmentReportError("unauthorized")));
    expect(expired).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it.each(["unauthorized", "forbidden", "conflict", "integrity", "unavailable", "crypto"] as const)(
    "shows safe actionable %s errors with no file", async code => {
      vi.mocked(api.downloadAssessmentReport).mockRejectedValue(new api.AssessmentReportError(code));
      const expired = vi.fn();
      render(<AssessmentReportPanel {...props} onSessionExpired={expired} />);
      fireEvent.click(screen.getByRole("button", { name: "Download report" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(reportCopy.en.errors[code]);
      expect(click).not.toHaveBeenCalled();
      expect(expired).toHaveBeenCalledTimes(code === "unauthorized" ? 1 : 0);
    },
  );

  it.each(["en", "de", "fr", "nl", "es"] as SupportedLocale[])("renders complete %s messages", locale => {
    render(<AssessmentReportPanel {...props} locale={locale} />);
    expect(screen.getByRole("heading", { name: reportCopy[locale].title })).toBeVisible();
    expect(screen.getByRole("button", { name: reportCopy[locale].download })).toBeEnabled();
    expect(screen.getByText(reportCopy[locale].contents)).toBeVisible();
  });

  it.each([{ admitted: false }, { adoptionId: "" }, { actorId: "" }, { token: "" }])(
    "disables incomplete or denied contexts: %j", change => {
      render(<AssessmentReportPanel {...props} {...change} />);
      expect(screen.getByRole("button", { name: "Download report" })).toBeDisabled();
      expect(api.downloadAssessmentReport).not.toHaveBeenCalled();
    },
  );

  it("cancels without a false success and permits a fresh explicit request", async () => {
    const pending = deferred();
    vi.mocked(api.downloadAssessmentReport).mockReturnValueOnce(pending.promise);
    render(<AssessmentReportPanel {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Download report" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await act(async () => pending.resolve(report));
    expect(click).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Download report" }));
    await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
  });

  it("aborts on unmount and does not trigger a download afterward", async () => {
    const pending = deferred();
    vi.mocked(api.downloadAssessmentReport).mockReturnValueOnce(pending.promise);
    const view = render(<AssessmentReportPanel {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Download report" }));
    view.unmount();
    await act(async () => pending.resolve(report));
    expect(click).not.toHaveBeenCalled();
  });
});

