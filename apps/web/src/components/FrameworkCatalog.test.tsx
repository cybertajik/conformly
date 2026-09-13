import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { canManageFrameworks, canReadFrameworks } from "../permissions";
import { FrameworkCatalog } from "./FrameworkCatalog";

vi.mock("../api", () => ({
  listCanonicalFrameworks: vi.fn().mockResolvedValue([
    {
      id: "fw-1",
      name: "ISO/IEC 27001",
      slug: "iso-27001",
      description: "Information security management",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      versions: [
        {
          id: "v-1",
          framework_id: "fw-1",
          version: "2022",
          release_state: "released",
          created_by_user_id: "u-1",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    },
  ]),
  listTenantAdoptions: vi.fn().mockResolvedValue([
    {
      id: "adp-1",
      tenant_id: "t-1",
      framework_id: "fw-1",
      framework_version_id: "v-1",
      status: "active",
      adopted_at: "2026-01-02T00:00:00Z",
      adopted_by_user_id: "u-1",
    },
  ]),
  listCustomControls: vi.fn().mockResolvedValue([
    {
      id: "cc-1",
      tenant_id: "t-1",
      identifier: "CUST-01",
      title: "Key Rotation",
      description: "Keys rotated every 90 days",
      category: "Crypto",
      status: "active",
      created_at: "2026-01-01T00:00:00Z",
    },
  ]),
  listControlMappings: vi.fn().mockResolvedValue([]),
  listTenantOverlays: vi.fn().mockResolvedValue([]),
  deleteTenantOverlay: vi.fn().mockResolvedValue(undefined),
  evaluateAdoptionApplicability: vi.fn().mockResolvedValue([]),
  getCanonicalVersionDetails: vi.fn().mockResolvedValue({
    id: "v-1",
    framework_id: "fw-1",
    version: "2022",
    release_state: "released",
    created_by_user_id: "u-1",
    created_at: "2026-01-01T00:00:00Z",
    controls: [
      {
        id: "ctrl-1",
        framework_version_id: "v-1",
        identifier: "A.5.1",
        title: "Policies for information security",
        description: "Policies shall be defined and approved",
        category: "Organizational",
        sort_order: 1,
        created_at: "2026-01-01T00:00:00Z",
      },
    ],
  }),
}));

vi.mock("../auth", () => ({
  getAccessToken: vi.fn().mockReturnValue("mock-token"),
}));

describe("FrameworkCatalog", () => {
  it("renders catalog header and loaded frameworks", async () => {
    render(<FrameworkCatalog tenantId="t-1" userRole="compliance_manager" />);
    expect(
      await screen.findByRole("heading", { name: "Framework Catalog & Overlays" })
    ).toBeInTheDocument();
    const fwElements = await screen.findAllByText("ISO/IEC 27001");
    expect(fwElements.length).toBeGreaterThanOrEqual(1);
    expect(await screen.findByText("CUST-01")).toBeInTheDocument();
  });


  it("checks framework management permissions correctly", () => {
    expect(canManageFrameworks("owner")).toBe(true);
    expect(canManageFrameworks("administrator")).toBe(false);
    expect(canManageFrameworks("compliance_manager")).toBe(true);
    expect(canManageFrameworks("control_owner")).toBe(true);
    expect(canManageFrameworks("contributor")).toBe(true);
    expect(canManageFrameworks("auditor")).toBe(false);
    expect(canManageFrameworks("viewer")).toBe(false);
    expect(canManageFrameworks("employee")).toBe(false);

    expect(canReadFrameworks("auditor")).toBe(true);
    expect(canReadFrameworks("reviewer")).toBe(true);
    expect(canReadFrameworks("viewer")).toBe(true);
    expect(canReadFrameworks("administrator")).toBe(false);
    expect(canReadFrameworks("employee")).toBe(false);
  });

  it("renders applicability evaluation action and filter tabs", async () => {
    render(<FrameworkCatalog tenantId="t-1" userRole="compliance_manager" />);
    expect(
      await screen.findByRole("button", { name: /Evaluate Applicability Rules/i })
    ).toBeInTheDocument();
    expect(screen.getAllByText(/All Controls/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Applicable/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Scoped Out/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Not Applicable/).length).toBeGreaterThan(0);
  });
});
