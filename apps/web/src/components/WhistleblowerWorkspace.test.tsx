import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WhistleblowerWorkspace } from "./WhistleblowerWorkspace";
import type {
  WhistleblowerCaseSummary,
  WhistleblowerPortalSummary,
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

const mockCase: WhistleblowerCaseSummary = {
  id: "case-1",
  tenant_id: "tenant-1",
  portal_id: "portal-1",
  public_case_id: "WB-ABCD-1234",
  status: "submitted",
  category: "financial_fraud",
  title: "Accounting ledger discrepancy",
  summary: "Suspicious accounting ledger discrepancies observed in Q2",
  closed_reason: null,
  closed_at: null,
  version: 1,
  messages_count: 1,
  created_at: "2026-09-02T10:00:00Z",
  updated_at: "2026-09-02T10:00:00Z",
  assignments: [],
  messages: [
    {
      id: "msg-1",
      tenant_id: "tenant-1",
      case_id: "case-1",
      sender_type: "reporter",
      sent_by_user_id: null,
      body: "Here are the specific invoice numbers involved.",
      created_at: "2026-09-02T10:00:00Z",
    },
  ],
};

vi.mock("../api", () => ({
  getTenantWhistleblowerPortal: vi.fn().mockImplementation(() => Promise.resolve(mockPortal)),
  setupOrUpdateWhistleblowerPortal: vi.fn().mockImplementation((_token, _tid, payload) =>
    Promise.resolve({
      ...mockPortal,
      ...payload,
    }),
  ),
  listWhistleblowerCases: vi.fn().mockImplementation(() =>
    Promise.resolve({
      items: [mockCase],
      total: 1,
      page: 1,
      page_size: 50,
    }),
  ),
  getWhistleblowerCaseDetail: vi.fn().mockImplementation(() => Promise.resolve(mockCase)),
  updateWhistleblowerCaseStatus: vi.fn().mockImplementation((_token, _tid, _cid, payload) =>
    Promise.resolve({
      ...mockCase,
      status: payload.status,
      closed_reason: payload.closed_reason ?? null,
    }),
  ),
  addWhistleblowerHandlerMessage: vi.fn().mockImplementation((_token, _tid, _cid, payload) =>
    Promise.resolve({
      id: "msg-handler-1",
      tenant_id: "tenant-1",
      case_id: "case-1",
      sender_type: "handler",
      sent_by_user_id: "user-cm",
      body: payload.body,
      created_at: "2026-09-02T11:00:00Z",
    }),
  ),
  assignWhistleblowerHandler: vi.fn().mockImplementation((_token, _tid, _cid, payload) =>
    Promise.resolve({
      id: "assign-1",
      tenant_id: "tenant-1",
      case_id: "case-1",
      handler_user_id: payload.handler_user_id,
      assigned_by_user_id: "user-cm",
      assigned_at: "2026-09-02T11:00:00Z",
    }),
  ),
}));

describe("WhistleblowerWorkspace", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("blocks unauthorized roles with clear compliance boundary message", () => {
    render(
      <WhistleblowerWorkspace
        token="test-token"
        tenantContext={{
          tenant_id: "tenant-1",
          role: "auditor",
        }}
        onOpenPublicPortal={vi.fn()}
      />,
    );

    expect(
      screen.getByText(/Whistleblower reports are confidential/i),
    ).toBeInTheDocument();
  });

  it("renders case triage workspace for authorized compliance manager", async () => {
    render(
      <WhistleblowerWorkspace
        token="test-token"
        tenantContext={{
          tenant_id: "tenant-1",
          role: "compliance_manager",
        }}
        onOpenPublicPortal={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Whistleblower & Ethics Channel")).toBeInTheDocument();
    });

    expect(screen.getByText("WB-ABCD-1234")).toBeInTheDocument();
    expect(
      screen.getByText("Accounting ledger discrepancy"),
    ).toBeInTheDocument();
  });

  it("selects a case, views decrypted thread, and sends handler message", async () => {
    const { addWhistleblowerHandlerMessage } = await import("../api");

    render(
      <WhistleblowerWorkspace
        token="test-token"
        tenantContext={{
          tenant_id: "tenant-1",
          role: "compliance_manager",
        }}
        onOpenPublicPortal={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("WB-ABCD-1234")).toBeInTheDocument();
    });

    // Click on Manage button
    const manageButton = screen.getByRole("button", { name: "Manage →" });
    fireEvent.click(manageButton);

    await waitFor(() => {
      expect(screen.getByText("Suspicious accounting ledger discrepancies observed in Q2")).toBeInTheDocument();
      expect(screen.getByText("Here are the specific invoice numbers involved.")).toBeInTheDocument();
    });

    // Enter handler reply
    const replyInput = screen.getByPlaceholderText(
      /Message will be encrypted and visible when the reporter checks their case key.../i,
    );
    fireEvent.change(replyInput, {
      target: { value: "Thank you for the additional information. We are investigating." },
    });

    const sendBtn = screen.getByRole("button", { name: "Send Reply" });
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(addWhistleblowerHandlerMessage).toHaveBeenCalledWith(
        "test-token",
        "tenant-1",
        "case-1",
        { body: "Thank you for the additional information. We are investigating." },
      );
    });
  });

  it("updates case status through lifecycle transitions", async () => {
    const { updateWhistleblowerCaseStatus } = await import("../api");

    render(
      <WhistleblowerWorkspace
        token="test-token"
        tenantContext={{
          tenant_id: "tenant-1",
          role: "compliance_manager",
        }}
        onOpenPublicPortal={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("WB-ABCD-1234")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Manage →" }));

    await waitFor(() => {
      expect(screen.getByText("Lifecycle Status Actions")).toBeInTheDocument();
    });

    // Click Start Investigation
    const investBtn = screen.getByRole("button", { name: "Start Investigation" });
    fireEvent.click(investBtn);

    await waitFor(() => {
      expect(updateWhistleblowerCaseStatus).toHaveBeenCalledWith(
        "test-token",
        "tenant-1",
        "case-1",
        {
          status: "under_investigation",
          closed_reason: null,
          expected_version: 1,
        },
      );
    });
  });

  it("allows administrator to configure portal settings", async () => {
    const { setupOrUpdateWhistleblowerPortal } = await import("../api");
    const mockOpenPortal = vi.fn();

    render(
      <WhistleblowerWorkspace
        token="test-token"
        tenantContext={{
          tenant_id: "tenant-1",
          role: "compliance_manager",
        }}
        onOpenPublicPortal={mockOpenPortal}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Whistleblower & Ethics Channel")).toBeInTheDocument();
    });

    // Switch to portal settings tab
    const portalTab = screen.getByRole("button", { name: "Public Portal Settings" });
    fireEvent.click(portalTab);

    await waitFor(() => {
      expect(screen.getByDisplayValue("secure-reports")).toBeInTheDocument();
      expect(screen.getByDisplayValue("Anonymous Integrity Line")).toBeInTheDocument();
    });

    // Update portal title
    const titleInput = screen.getByDisplayValue("Anonymous Integrity Line");
    fireEvent.change(titleInput, { target: { value: "Updated Trust Hotline" } });

    // Save changes
    const saveBtn = screen.getByRole("button", { name: "Save Portal Settings" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(setupOrUpdateWhistleblowerPortal).toHaveBeenCalledWith(
        "test-token",
        "tenant-1",
        expect.objectContaining({
          title: "Updated Trust Hotline",
        }),
      );
    });
  });
});
