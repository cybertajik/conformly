import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import * as api from "./operations-api";
import { Vendor } from "./operations-types";
import { VendorWorkspaceV2 } from "./VendorWorkspaceV2";

describe("VendorWorkspaceV2 Component", () => {
  const dummyVendor: Vendor = {
    id: "ven-1",
    tenant_id: "ten-1",
    name: "Amazon Web Services",
    service_description: "Cloud computing and managed services",
    criticality: "critical",
    data_classification_accessed: "Restricted",
    country_residency: "DE",
    dpa_signed: true,
    security_reviewed_at: null,
    next_review_due_at: null,
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders vendor inventory and filters by criticality", () => {
    const lowVendor: Vendor = {
      ...dummyVendor,
      id: "ven-2",
      name: "Office Supplies Co",
      criticality: "low",
    };

    render(
      <I18nProvider>
        <VendorWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          vendors={[dummyVendor, lowVendor]}
        />
      </I18nProvider>
    );

    expect(screen.getByTestId("vendor-workspace")).toBeInTheDocument();
    expect(screen.getByText("Amazon Web Services")).toBeInTheDocument();
    expect(screen.getByText("Office Supplies Co")).toBeInTheDocument();

    // Filter by critical
    fireEvent.change(screen.getByTestId("vendor-criticality-filter"), {
      target: { value: "critical" },
    });
    expect(screen.getByText("Amazon Web Services")).toBeInTheDocument();
    expect(screen.queryByText("Office Supplies Co")).not.toBeInTheDocument();
  });

  it("handles vendor creation, update, and security review recording", async () => {
    const onVendorCreated = vi.fn();
    const onVendorMutated = vi.fn();

    vi.spyOn(api, "createVendor").mockResolvedValue({
      ...dummyVendor,
      id: "ven-new",
      name: "GitHub Enterprise",
      criticality: "high",
    });

    render(
      <I18nProvider>
        <VendorWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="owner"
          vendors={[dummyVendor]}
          onVendorCreated={onVendorCreated}
          onVendorMutated={onVendorMutated}
        />
      </I18nProvider>
    );

    // Create vendor
    fireEvent.click(screen.getByTestId("new-vendor-btn"));
    fireEvent.change(screen.getByTestId("new-vendor-name-input"), {
      target: { value: "GitHub Enterprise" },
    });
    fireEvent.click(screen.getByTestId("submit-create-vendor-btn"));

    await waitFor(() => {
      expect(onVendorCreated).toHaveBeenCalled();
    });

    // Select existing vendor
    fireEvent.click(screen.getByTestId("vendor-row-ven-1"));
    expect(screen.getByTestId("detail-vendor-criticality")).toHaveTextContent("critical");

    // Edit and save
    vi.spyOn(api, "updateVendor").mockResolvedValue({
      ...dummyVendor,
      service_description: "Updated description with S3 and RDS",
    });

    fireEvent.change(screen.getByTestId("edit-vendor-desc-input"), {
      target: { value: "Updated description with S3 and RDS" },
    });
    fireEvent.click(screen.getByTestId("save-vendor-draft-btn"));

    await waitFor(() => {
      expect(onVendorMutated).toHaveBeenCalled();
    });

    // Record review
    vi.spyOn(api, "reviewVendor").mockResolvedValue({
      ...dummyVendor,
      security_reviewed_at: "2026-10-29T12:00:00Z",
    });

    fireEvent.click(screen.getByTestId("review-vendor-btn"));
    await waitFor(() => {
      expect(onVendorMutated).toHaveBeenCalled();
      expect(screen.getByTestId("vendor-action-success")).toHaveTextContent(/review recorded/i);
    });
  });
});

