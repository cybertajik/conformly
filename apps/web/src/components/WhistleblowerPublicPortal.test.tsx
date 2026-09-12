import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WhistleblowerPublicPortal } from "./WhistleblowerPublicPortal";
import type {
  WhistleblowerPortalSummary,
  WhistleblowerPublicCaseSummary,
  WhistleblowerSubmissionResult,
} from "@conformly/shared";

const mockPortal: WhistleblowerPortalSummary = {
  id: "portal-1",
  tenant_id: "tenant-1",
  slug: "secure-reports",
  title: "Anonymous Integrity Line",
  welcome_text: "Submit confidential ethics concerns.",
  is_active: true,
  version: 1,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

const mockSubmissionResult: WhistleblowerSubmissionResult = {
  public_case_id: "WB-TEST-9999",
  return_secret: "sec_abc123def456_super_secret_return_key_256",
  portal_title: "Anonymous Integrity Line",
  created_at: "2026-09-02T10:00:00Z",
};

const mockCaseView: WhistleblowerPublicCaseSummary = {
  public_case_id: "WB-TEST-9999",
  status: "acknowledged",
  category: "fraud",
  title: "Accounting Anomaly",
  closed_at: null,
  created_at: "2026-09-02T10:00:00Z",
  messages: [
    {
      id: "msg-1",
      tenant_id: "tenant-1",
      case_id: "case-1",
      sender_type: "reporter",
      body: "Original report details submitted.",
      created_at: "2026-09-02T10:00:00Z",
    },
    {
      id: "msg-2",
      tenant_id: "tenant-1",
      case_id: "case-1",
      sender_type: "handler",
      body: "We have acknowledged your report and assigned an investigator.",
      created_at: "2026-09-02T10:30:00Z",
    },
  ],
};

vi.mock("../api", () => ({
  getPublicWhistleblowerPortal: vi.fn().mockImplementation(() => Promise.resolve(mockPortal)),
  submitWhistleblowerReport: vi.fn().mockImplementation(() => Promise.resolve(mockSubmissionResult)),
  accessWhistleblowerCasePublic: vi.fn().mockImplementation(() => Promise.resolve(mockCaseView)),
  addWhistleblowerReporterMessage: vi.fn().mockImplementation(() => Promise.resolve({ success: true })),
}));

describe("WhistleblowerPublicPortal", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("loads and displays the anonymous reporting portal", async () => {
    render(<WhistleblowerPublicPortal slug="secure-reports" />);

    await waitFor(() => {
      expect(screen.getByText("Anonymous Integrity Line")).toBeInTheDocument();
      expect(screen.getByText("Submit confidential ethics concerns.")).toBeInTheDocument();
    });

    expect(screen.getByText(/100% Anonymous • Zero Identity Tracking/i)).toBeInTheDocument();
  });

  it("submits an anonymous report and presents one-way return secret key", async () => {
    const { submitWhistleblowerReport } = await import("../api");

    render(<WhistleblowerPublicPortal slug="secure-reports" />);

    await waitFor(() => {
      expect(screen.getByText("Anonymous Integrity Line")).toBeInTheDocument();
    });

    // Fill title and summary
    const titleInput = screen.getByPlaceholderText(/Concise overview of the concern/i);
    const summaryInput = screen.getByPlaceholderText(/Provide specific dates, departments, names, or transaction details/i);

    fireEvent.change(titleInput, { target: { value: "Suspected kickbacks on supplier contract" } });
    fireEvent.change(summaryInput, { target: { value: "Contract vendor X was chosen without bidding process." } });

    const submitBtn = screen.getByRole("button", { name: "Submit Report Anonymously" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(submitWhistleblowerReport).toHaveBeenCalledWith("secure-reports", {
        category: "fraud",
        title: "Suspected kickbacks on supplier contract",
        summary: "Contract vendor X was chosen without bidding process.",
      });
    });

    // Confirm that public_case_id and return_secret are displayed with warning
    await waitFor(() => {
      expect(screen.getByText("Report Successfully Submitted")).toBeInTheDocument();
      expect(screen.getByText("WB-TEST-9999")).toBeInTheDocument();
      expect(screen.getByDisplayValue("sec_abc123def456_super_secret_return_key_256")).toBeInTheDocument();
      expect(
        screen.getByText(/⚠️ CRITICAL: Save your Secret Return Key now/i),
      ).toBeInTheDocument();
    });
  });

  it("tracks case status with return secret key and allows sending anonymous reply", async () => {
    const { accessWhistleblowerCasePublic, addWhistleblowerReporterMessage } = await import("../api");

    render(<WhistleblowerPublicPortal slug="secure-reports" />);

    await waitFor(() => {
      expect(screen.getByText("Anonymous Integrity Line")).toBeInTheDocument();
    });

    // Switch to track tab
    const trackTab = screen.getByRole("button", { name: "Track Existing Report" });
    fireEvent.click(trackTab);

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/e\.g\. WB-2026-A1B2C3/i)).toBeInTheDocument();
    });

    const caseIdInput = screen.getByPlaceholderText(/e\.g\. WB-2026-A1B2C3/i);
    const secretInput = screen.getByPlaceholderText(/wb_\.\.\./i);

    fireEvent.change(caseIdInput, { target: { value: "WB-TEST-9999" } });
    fireEvent.change(secretInput, { target: { value: "sec_abc123def456_super_secret_return_key_256" } });

    const trackBtn = screen.getByRole("button", { name: "Access Case" });
    fireEvent.click(trackBtn);

    await waitFor(() => {
      expect(accessWhistleblowerCasePublic).toHaveBeenCalledWith("secure-reports", {
        public_case_id: "WB-TEST-9999",
        return_secret: "sec_abc123def456_super_secret_return_key_256",
      });
    });

    // Verify case messages
    await waitFor(() => {
      expect(
        screen.getByText("We have acknowledged your report and assigned an investigator."),
      ).toBeInTheDocument();
    });

    // Send anonymous follow-up message
    const replyInput = screen.getByPlaceholderText(/Add additional facts, clarify questions, or reply to compliance committee\.\.\./i);
    fireEvent.change(replyInput, { target: { value: "Here is additional context regarding vendor X." } });

    const sendReplyBtn = screen.getByRole("button", { name: "Send Message" });
    fireEvent.click(sendReplyBtn);

    await waitFor(() => {
      expect(addWhistleblowerReporterMessage).toHaveBeenCalledWith("secure-reports", {
        public_case_id: "WB-TEST-9999",
        return_secret: "sec_abc123def456_super_secret_return_key_256",
        body: "Here is additional context regarding vendor X.",
      });
    });
  });
});
