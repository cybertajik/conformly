import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DataLifecycleWorkspace } from "./DataLifecycleWorkspace";

const api = vi.hoisted(() => ({
  createExportJob: vi.fn(),
  downloadExportArchive: vi.fn(),
  getCancellationStatus: vi.fn(),
  listDeletionProofs: vi.fn(),
  listExportJobs: vi.fn(),
  requestTenantCancellation: vi.fn(),
  setLegalHold: vi.fn(),
}));

vi.mock("../api", () => api);

describe("DataLifecycleWorkspace", () => {
  beforeEach(() => {
    api.listExportJobs.mockResolvedValue([]);
    api.listDeletionProofs.mockResolvedValue([]);
    api.getCancellationStatus.mockResolvedValue({
      status: "active",
      cancellation_requested_at: null,
      export_until: null,
      deletion_due_at: null,
      days_remaining_in_export_window: null,
      is_export_window_active: false,
      legal_hold: false,
    });
    api.createExportJob.mockResolvedValue({ id: "export-1" });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("loads lifecycle state and generates an authorized export", async () => {
    render(
      <DataLifecycleWorkspace
        token="token"
        tenantId="tenant-1"
        tenantSlug="acme"
        role="owner"
      />,
    );

    expect(await screen.findByText(/Legal hold: not active/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Generate export" }));

    await waitFor(() => {
      expect(api.createExportJob).toHaveBeenCalledWith("token", "tenant-1", "full");
    });
    expect(await screen.findByText("Export generated.")).toBeInTheDocument();
  });

  it("requires the exact tenant slug before enabling cancellation", async () => {
    render(
      <DataLifecycleWorkspace
        token="token"
        tenantId="tenant-1"
        tenantSlug="acme"
        role="owner"
      />,
    );

    const cancel = await screen.findByRole("button", { name: "Schedule cancellation" });
    expect(cancel).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Leaving service" } });
    fireEvent.change(screen.getByLabelText("Type acme to confirm"), {
      target: { value: "wrong" },
    });
    expect(cancel).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Type acme to confirm"), {
      target: { value: "acme" },
    });
    expect(cancel).toBeEnabled();
  });
});
