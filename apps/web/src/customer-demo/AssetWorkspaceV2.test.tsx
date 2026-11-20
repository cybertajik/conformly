import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { AssetWorkspaceV2 } from "./AssetWorkspaceV2";
import * as api from "./operations-api";
import { Asset } from "./operations-types";

describe("AssetWorkspaceV2 Component", () => {
  const dummyAsset: Asset = {
    id: "asset-1",
    tenant_id: "ten-1",
    name: "Production PostgreSQL Database",
    asset_type: "data",
    classification: "restricted",
    description: "Primary database cluster",
    owner_user_id: null,
    status: "active",
    last_reviewed_at: null,
    next_review_due_at: null,
    created_at: "2026-10-29T10:00:00Z",
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders asset inventory and filters by type", () => {
    const hardwareAsset: Asset = {
      ...dummyAsset,
      id: "asset-2",
      name: "Office Edge Router",
      asset_type: "hardware",
      classification: "internal",
    };

    render(
      <I18nProvider>
        <AssetWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="compliance_manager"
          assets={[dummyAsset, hardwareAsset]}
        />
      </I18nProvider>
    );

    expect(screen.getByTestId("asset-workspace")).toBeInTheDocument();
    expect(screen.getByText("Production PostgreSQL Database")).toBeInTheDocument();
    expect(screen.getByText("Office Edge Router")).toBeInTheDocument();

    // Filter by data
    fireEvent.change(screen.getByTestId("asset-type-filter"), { target: { value: "data" } });
    expect(screen.getByText("Production PostgreSQL Database")).toBeInTheDocument();
    expect(screen.queryByText("Office Edge Router")).not.toBeInTheDocument();
  });

  it("handles asset creation, update, and review recording", async () => {
    const onAssetCreated = vi.fn();
    const onAssetMutated = vi.fn();

    vi.spyOn(api, "createAsset").mockResolvedValue({
      ...dummyAsset,
      id: "asset-new",
      name: "Kubernetes Cluster",
      asset_type: "cloud_service",
    });

    render(
      <I18nProvider>
        <AssetWorkspaceV2
          tenantId="ten-1"
          token="token-abc"
          userRole="owner"
          assets={[dummyAsset]}
          onAssetCreated={onAssetCreated}
          onAssetMutated={onAssetMutated}
        />
      </I18nProvider>
    );

    // Create asset
    fireEvent.click(screen.getByTestId("new-asset-btn"));
    fireEvent.change(screen.getByTestId("new-asset-name-input"), {
      target: { value: "Kubernetes Cluster" },
    });
    fireEvent.click(screen.getByTestId("submit-create-asset-btn"));

    await waitFor(() => {
      expect(onAssetCreated).toHaveBeenCalled();
    });

    // Select existing asset
    fireEvent.click(screen.getByTestId("asset-row-asset-1"));
    expect(screen.getByTestId("detail-asset-type")).toHaveTextContent("data");

    // Edit and save
    vi.spyOn(api, "updateAsset").mockResolvedValue({
      ...dummyAsset,
      classification: "confidential",
    });

    fireEvent.change(screen.getByTestId("edit-asset-classification-select"), {
      target: { value: "confidential" },
    });
    fireEvent.click(screen.getByTestId("save-asset-draft-btn"));

    await waitFor(() => {
      expect(onAssetMutated).toHaveBeenCalled();
    });

    // Record review
    vi.spyOn(api, "reviewAsset").mockResolvedValue({
      ...dummyAsset,
      last_reviewed_at: "2026-10-29T12:00:00Z",
    });

    fireEvent.click(screen.getByTestId("review-asset-btn"));
    await waitFor(() => {
      expect(onAssetMutated).toHaveBeenCalled();
      expect(screen.getByTestId("asset-action-success")).toHaveTextContent(/review recorded/i);
    });
  });
});

