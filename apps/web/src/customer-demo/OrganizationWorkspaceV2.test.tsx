import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { ForbiddenError, UnauthorizedError } from "./api";
import * as orgApi from "./organization-api";
import { BusinessUnit, LegalEntity, Location, Membership, TenantEntitlement } from "./organization-types";
import { OrganizationWorkspaceV2 } from "./OrganizationWorkspaceV2";

vi.mock("./organization-api", () => ({
  fetchLegalEntities: vi.fn(),
  createLegalEntity: vi.fn(),
  fetchBusinessUnits: vi.fn(),
  createBusinessUnit: vi.fn(),
  fetchLocations: vi.fn(),
  createLocation: vi.fn(),
  fetchMemberships: vi.fn(),
  fetchEntitlements: vi.fn(),
}));

const mockEntities: LegalEntity[] = [
  {
    id: "le-1",
    tenant_id: "tenant-alpha",
    name: "Alpha Corp Europe GmbH",
    registration_number: "HRB 123456",
    country: "DE",
    is_primary: true,
    created_at: "2026-10-01T10:00:00Z",
  },
  {
    id: "le-2",
    tenant_id: "tenant-alpha",
    name: "Alpha US Inc",
    registration_number: "DEL-7890",
    country: "US",
    is_primary: false,
    created_at: "2026-10-02T10:00:00Z",
  },
];

const mockUnits: BusinessUnit[] = [
  {
    id: "bu-1",
    tenant_id: "tenant-alpha",
    legal_entity_id: "le-1",
    name: "Cloud Security",
    code: "SEC-CLOUD",
    created_at: "2026-10-01T11:00:00Z",
  },
];

const mockLocations: Location[] = [
  {
    id: "loc-1",
    tenant_id: "tenant-alpha",
    legal_entity_id: "le-1",
    name: "Frankfurt DC 1",
    country: "DE",
    city: "Frankfurt",
    address: "Mainzer Landstr. 100",
    created_at: "2026-10-01T11:00:00Z",
  },
];

const mockMemberships: Membership[] = [
  {
    id: "mem-1",
    tenant_id: "tenant-alpha",
    user_id: "usr-1",
    email: "admin@alphacorp.example",
    display_name: "Alice Admin",
    role: "owner",
    status: "ACTIVE",
    created_at: "2026-10-01T09:00:00Z",
  },
  {
    id: "mem-2",
    tenant_id: "tenant-alpha",
    user_id: "usr-2",
    email: "auditor@alphacorp.example",
    display_name: "Bob Auditor",
    role: "auditor",
    status: "ACTIVE",
    created_at: "2026-10-05T09:00:00Z",
  },
];

const mockEntitlement: TenantEntitlement = {
  id: "ent-1",
  tenant_id: "tenant-alpha",
  plan_code: "enterprise_scale",
  max_members: 100,
  max_storage_bytes: 10 * 1024 * 1024 * 1024,
  enabled_modules: ["catalog_v2", "assurance", "customer_demo", "assessments", "organization"],
  allowed_framework_slugs: ["iso_9001_2015"],
  effective_from: "2026-01-01T00:00:00Z",
  effective_until: null,
};

function renderWithI18n(ui: React.ReactElement) {
  return render(<I18nProvider>{ui}</I18nProvider>);
}

describe("OrganizationWorkspaceV2 Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(orgApi.fetchLegalEntities).mockResolvedValue(mockEntities);
    vi.mocked(orgApi.fetchBusinessUnits).mockResolvedValue(mockUnits);
    vi.mocked(orgApi.fetchLocations).mockResolvedValue(mockLocations);
    vi.mocked(orgApi.fetchMemberships).mockResolvedValue(mockMemberships);
    vi.mocked(orgApi.fetchEntitlements).mockResolvedValue(mockEntitlement);
  });

  afterEach(() => {
    cleanup();
  });

  it("renders workspace sections, legal entities, business units, and locations", async () => {
    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="owner"
      />
    );

    expect(screen.getByTestId("organization-workspace")).toBeInTheDocument();
    expect(screen.getByTestId("org-workspace-title")).toHaveTextContent(/Organization & Structure/i);

    // Wait for entities to load
    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    expect(screen.getByText("Alpha Corp Europe GmbH")).toBeInTheDocument();
    expect(screen.getByTestId("primary-badge-le-1")).toBeInTheDocument();
    expect(screen.getByText("Alpha US Inc")).toBeInTheDocument();

    // Verify Business units loaded for primary entity
    await waitFor(() => {
      expect(screen.getByTestId("bu-card-bu-1")).toBeInTheDocument();
    });
    expect(screen.getByText("Cloud Security")).toBeInTheDocument();

    // Verify Locations loaded for primary entity
    await waitFor(() => {
      expect(screen.getByTestId("loc-card-loc-1")).toBeInTheDocument();
    });
    expect(screen.getByText("Frankfurt DC 1")).toBeInTheDocument();
    expect(screen.getByText(/Frankfurt, DE/i)).toBeInTheDocument();
  });

  it("creates a new legal entity via form and appends to the list", async () => {
    const newEntity: LegalEntity = {
      id: "le-3",
      tenant_id: "tenant-alpha",
      name: "Alpha Asia Pte Ltd",
      registration_number: "SG-9988",
      country: "SG",
      is_primary: false,
      created_at: "2026-10-29T10:00:00Z",
    };
    vi.mocked(orgApi.createLegalEntity).mockResolvedValueOnce(newEntity);

    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="owner"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("entity-name-input"), { target: { value: "Alpha Asia Pte Ltd" } });
    fireEvent.change(screen.getByTestId("entity-reg-input"), { target: { value: "SG-9988" } });
    fireEvent.change(screen.getByTestId("entity-country-input"), { target: { value: "SG" } });

    fireEvent.click(screen.getByTestId("create-entity-btn"));

    await waitFor(() => {
      expect(orgApi.createLegalEntity).toHaveBeenCalledWith(
        "tenant-alpha",
        "token-xyz",
        {
          name: "Alpha Asia Pte Ltd",
          registration_number: "SG-9988",
          country: "SG",
          is_primary: false,
        }
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-3")).toBeInTheDocument();
      expect(screen.getByText("Alpha Asia Pte Ltd")).toBeInTheDocument();
    });
  });

  it("validates legal entity form inputs and prevents submission when name is missing", async () => {
    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="owner"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("entity-name-input"), { target: { value: "   " } });
    fireEvent.click(screen.getByTestId("create-entity-btn"));

    expect(orgApi.createLegalEntity).not.toHaveBeenCalled();
    expect(screen.getByText("Entity name is required")).toBeInTheDocument();
  });

  it("creates a business unit under selected legal entity", async () => {
    const newBu: BusinessUnit = {
      id: "bu-2",
      tenant_id: "tenant-alpha",
      legal_entity_id: "le-1",
      name: "Engineering",
      code: "ENG-CORE",
      created_at: "2026-10-29T10:00:00Z",
    };
    vi.mocked(orgApi.createBusinessUnit).mockResolvedValueOnce(newBu);

    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="owner"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("bu-name-input"), { target: { value: "Engineering" } });
    fireEvent.change(screen.getByTestId("bu-code-input"), { target: { value: "ENG-CORE" } });

    fireEvent.click(screen.getByTestId("create-bu-btn"));

    await waitFor(() => {
      expect(orgApi.createBusinessUnit).toHaveBeenCalledWith(
        "tenant-alpha",
        "token-xyz",
        {
          legal_entity_id: "le-1",
          name: "Engineering",
          code: "ENG-CORE",
        }
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId("bu-card-bu-2")).toBeInTheDocument();
      expect(screen.getByText("Engineering")).toBeInTheDocument();
    });
  });

  it("creates a location under selected legal entity", async () => {
    const newLoc: Location = {
      id: "loc-2",
      tenant_id: "tenant-alpha",
      legal_entity_id: "le-1",
      name: "Munich Branch",
      country: "DE",
      city: "Munich",
      address: "Leopoldstr. 25",
      created_at: "2026-10-29T10:00:00Z",
    };
    vi.mocked(orgApi.createLocation).mockResolvedValueOnce(newLoc);

    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="owner"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("loc-name-input"), { target: { value: "Munich Branch" } });
    fireEvent.change(screen.getByTestId("loc-city-input"), { target: { value: "Munich" } });
    fireEvent.change(screen.getByTestId("loc-country-input"), { target: { value: "DE" } });
    fireEvent.change(screen.getByTestId("loc-address-input"), { target: { value: "Leopoldstr. 25" } });

    fireEvent.click(screen.getByTestId("create-loc-btn"));

    await waitFor(() => {
      expect(orgApi.createLocation).toHaveBeenCalledWith(
        "tenant-alpha",
        "token-xyz",
        {
          legal_entity_id: "le-1",
          name: "Munich Branch",
          country: "DE",
          city: "Munich",
          address: "Leopoldstr. 25",
        }
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId("loc-card-loc-2")).toBeInTheDocument();
      expect(screen.getByText("Munich Branch")).toBeInTheDocument();
    });
  });

  it("renders memberships in read-only section with role and status", async () => {
    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="owner"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("membership-row-mem-1")).toBeInTheDocument();
    });

    expect(screen.getByText("Alice Admin")).toBeInTheDocument();
    expect(screen.getByText("(admin@alphacorp.example)")).toBeInTheDocument();
    expect(screen.getByText("owner")).toBeInTheDocument();
    expect(screen.getByText("Bob Auditor")).toBeInTheDocument();
    expect(screen.getByText("auditor")).toBeInTheDocument();

    // Confirm no grant/invite controls exist
    expect(screen.queryByText(/Invite Member/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Grant Role/i)).not.toBeInTheDocument();
  });

  it("renders memberships 403 Forbidden state without breaking other sections", async () => {
    vi.mocked(orgApi.fetchMemberships).mockRejectedValueOnce(
      new ForbiddenError("Access forbidden to memberships directory")
    );

    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="viewer"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("memberships-denied")).toBeInTheDocument();
    });

    // Legal entities and business units still render successfully
    expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    expect(screen.getByText("Alpha Corp Europe GmbH")).toBeInTheDocument();
  });

  it("renders entitlements in read-only section with limits and enabled modules", async () => {
    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="owner"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entitlement-plan-code")).toBeInTheDocument();
    });

    expect(screen.getByTestId("entitlement-plan-code")).toHaveTextContent("enterprise_scale");
    expect(screen.getByTestId("entitlement-max-members")).toHaveTextContent("100");
    expect(screen.getByTestId("entitlement-storage-limit")).toHaveTextContent("10240 MB");
    expect(screen.getByTestId("entitlement-modules")).toHaveTextContent("catalog_v2");
    expect(screen.getByTestId("entitlement-modules")).toHaveTextContent("organization");

    // Confirm no plan modification controls exist
    expect(screen.queryByText(/Upgrade Plan/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Edit Limits/i)).not.toBeInTheDocument();
  });

  it("renders entitlements 403 Forbidden state without breaking other sections", async () => {
    vi.mocked(orgApi.fetchEntitlements).mockRejectedValueOnce(
      new ForbiddenError("Access forbidden to tenant entitlements")
    );

    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="viewer"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entitlements-denied")).toBeInTheDocument();
    });

    // Legal entities still render successfully
    expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
  });

  it("handles 401 Unauthorized by clearing data and invoking onSessionExpired", async () => {
    const onSessionExpired = vi.fn();
    vi.mocked(orgApi.fetchLegalEntities).mockRejectedValueOnce(
      new UnauthorizedError("Session expired")
    );

    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="stale-token"
        userRole="owner"
        onSessionExpired={onSessionExpired}
      />
    );

    await waitFor(() => {
      expect(onSessionExpired).toHaveBeenCalledTimes(1);
    });

    expect(screen.queryByTestId("entity-card-le-1")).not.toBeInTheDocument();
  });

  it("discards late responses from previous tenant on tenant-switch", async () => {
    let resolveFirstTenant: (val: LegalEntity[]) => void;
    const firstPromise = new Promise<LegalEntity[]>((resolve) => {
      resolveFirstTenant = resolve;
    });

    vi.mocked(orgApi.fetchLegalEntities)
      .mockReturnValueOnce(firstPromise)
      .mockResolvedValueOnce([
        {
          id: "le-beta-1",
          tenant_id: "tenant-beta",
          name: "Beta Global Ltd",
          registration_number: "BETA-01",
          country: "NL",
          is_primary: true,
          created_at: "2026-10-20T10:00:00Z",
        },
      ]);

    const { rerender } = renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="owner"
      />
    );

    // Switch tenant to tenant-beta before first finishes
    rerender(
      <I18nProvider>
        <OrganizationWorkspaceV2
          tenantId="tenant-beta"
          token="token-xyz"
          userRole="owner"
        />
      </I18nProvider>
    );

    // Wait for tenant-beta data to load
    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-beta-1")).toBeInTheDocument();
    });

    // Now resolve first tenant's response (late)
    resolveFirstTenant!(mockEntities);

    // Wait a tick to ensure state didn't get overwritten
    await new Promise((r) => setTimeout(r, 20));

    expect(screen.getByTestId("entity-card-le-beta-1")).toBeInTheDocument();
    expect(screen.queryByTestId("entity-card-le-1")).not.toBeInTheDocument();
  });

  it("discards late business unit create reply if selected entity changed", async () => {
    let resolveCreateBu: (val: BusinessUnit) => void;
    const createPromise = new Promise<BusinessUnit>((resolve) => {
      resolveCreateBu = resolve;
    });
    vi.mocked(orgApi.createBusinessUnit).mockReturnValueOnce(createPromise);

    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="owner"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("bu-name-input"), { target: { value: "Late Unit" } });
    fireEvent.click(screen.getByTestId("create-bu-btn"));

    // Switch selected entity to le-2 while create is pending
    fireEvent.change(screen.getByTestId("bu-entity-select"), { target: { value: "le-2" } });

    // Late resolve the creation under le-1
    resolveCreateBu!({
      id: "bu-late-1",
      tenant_id: "tenant-alpha",
      legal_entity_id: "le-1",
      name: "Late Unit",
      code: "LATE",
      created_at: "2026-10-29T12:00:00Z",
    });

    await new Promise((r) => setTimeout(r, 20));

    // The late response must NOT be appended to le-2's business unit view
    expect(screen.queryByTestId("bu-card-bu-late-1")).not.toBeInTheDocument();
    expect(screen.queryByText("Late Unit")).not.toBeInTheDocument();
  });

  it("discards late location create reply if selected entity changed", async () => {
    let resolveCreateLoc: (val: Location) => void;
    const createPromise = new Promise<Location>((resolve) => {
      resolveCreateLoc = resolve;
    });
    vi.mocked(orgApi.createLocation).mockReturnValueOnce(createPromise);

    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="owner"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("loc-name-input"), { target: { value: "Late Loc" } });
    fireEvent.change(screen.getByTestId("loc-city-input"), { target: { value: "Hamburg" } });
    fireEvent.click(screen.getByTestId("create-loc-btn"));

    // Switch selected entity to le-2 while create is pending
    fireEvent.change(screen.getByTestId("loc-entity-select"), { target: { value: "le-2" } });

    // Late resolve the creation under le-1
    resolveCreateLoc!({
      id: "loc-late-1",
      tenant_id: "tenant-alpha",
      legal_entity_id: "le-1",
      name: "Late Loc",
      city: "Hamburg",
      country: "DE",
      address: null,
      created_at: "2026-10-29T12:00:00Z",
    });

    await new Promise((r) => setTimeout(r, 20));

    // Must NOT be appended to le-2's location view
    expect(screen.queryByTestId("loc-card-loc-late-1")).not.toBeInTheDocument();
    expect(screen.queryByText("Late Loc")).not.toBeInTheDocument();
  });

  it("handles uncertain transport error during POST by displaying ambiguous post banner and preventing immediate duplicate POST", async () => {
    vi.mocked(orgApi.createLegalEntity).mockRejectedValueOnce(
      new Error("Network connection dropped")
    );

    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="owner"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("entity-name-input"), { target: { value: "Ambiguous Entity" } });
    fireEvent.click(screen.getByTestId("create-entity-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("ambiguous-post-banner")).toBeInTheDocument();
    });

    // Form inputs preserved
    expect(screen.getByTestId("entity-name-input")).toHaveValue("Ambiguous Entity");
    // Create button is disabled while ambiguous post is active
    expect(screen.getByTestId("create-entity-btn")).toBeDisabled();
    expect(screen.getByTestId("reconcile-post-btn")).toBeInTheDocument();
    // Dismiss is guarded and not visible before scoped GET check
    expect(screen.queryByTestId("dismiss-ambiguous-btn")).not.toBeInTheDocument();

    // Verify orgApi.createLegalEntity was called only once
    expect(orgApi.createLegalEntity).toHaveBeenCalledTimes(1);

    // Perform scoped GET reconciliation check
    fireEvent.click(screen.getByTestId("reconcile-post-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("dismiss-ambiguous-btn")).toBeInTheDocument();
    });

    // Clicking dismiss after verification clears the ambiguous state and enables editing/retry
    fireEvent.click(screen.getByTestId("dismiss-ambiguous-btn"));
    expect(screen.queryByTestId("ambiguous-post-banner")).not.toBeInTheDocument();
    expect(screen.getByTestId("create-entity-btn")).not.toBeDisabled();
  });

  it("reconciles ambiguous post by fetching updated list without sending a second POST", async () => {
    vi.mocked(orgApi.createLegalEntity).mockRejectedValueOnce(
      new Error("504 Gateway Timeout")
    );

    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="owner"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("entity-name-input"), { target: { value: "Reconciled Corp" } });
    fireEvent.click(screen.getByTestId("create-entity-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("ambiguous-post-banner")).toBeInTheDocument();
    });

    // Mock fetchLegalEntities to return the entity as committed on the server
    const reconciledEntity: LegalEntity = {
      id: "le-rec-1",
      tenant_id: "tenant-alpha",
      name: "Reconciled Corp",
      registration_number: null,
      country: "DE",
      is_primary: false,
      created_at: "2026-10-29T12:00:00Z",
    };
    vi.mocked(orgApi.fetchLegalEntities).mockResolvedValueOnce([...mockEntities, reconciledEntity]);

    fireEvent.click(screen.getByTestId("reconcile-post-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("confirm-match-btn-le-rec-1")).toBeInTheDocument();
    });

    // User explicitly confirms the reconciled server record
    fireEvent.click(screen.getByTestId("confirm-match-btn-le-rec-1"));

    await waitFor(() => {
      expect(screen.queryByTestId("ambiguous-post-banner")).not.toBeInTheDocument();
      expect(screen.getByTestId("entity-card-le-rec-1")).toBeInTheDocument();
    });

    // Still only 1 create call was made (no duplicate POST)
    expect(orgApi.createLegalEntity).toHaveBeenCalledTimes(1);
  });

  it("reconciliation identifies pre-existing same-name row with different details and refuses to declare automatic success", async () => {
    vi.mocked(orgApi.createLegalEntity).mockRejectedValueOnce(
      new Error("Network connection dropped")
    );

    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="owner"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    // Submit with specific details
    fireEvent.change(screen.getByTestId("entity-name-input"), { target: { value: "Alpha Corp Europe GmbH" } });
    fireEvent.change(screen.getByTestId("entity-reg-input"), { target: { value: "DIFFERENT-REG-999" } });
    fireEvent.click(screen.getByTestId("create-entity-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("ambiguous-post-banner")).toBeInTheDocument();
    });

    // Reconcile query returns existing le-1 with different reg (HRB 123456 vs DIFFERENT-REG-999)
    fireEvent.click(screen.getByTestId("reconcile-post-btn"));

    await waitFor(() => {
      expect(screen.getByText(/Differs from attempted payload/i)).toBeInTheDocument();
    });

    // Attempted inputs remain preserved in the form
    expect(screen.getByTestId("entity-name-input")).toHaveValue("Alpha Corp Europe GmbH");
    expect(screen.getByTestId("entity-reg-input")).toHaveValue("DIFFERENT-REG-999");

    // Generic refresh does NOT erase the ambiguity banner
    fireEvent.click(screen.getByTestId("org-refresh-btn"));
    expect(screen.getByTestId("ambiguous-post-banner")).toBeInTheDocument();
  });

  it("handles two independent concurrent form submissions finishing in order A then B without stuck buttons", async () => {
    let resolveEntity: (val: LegalEntity) => void;
    const entityPromise = new Promise<LegalEntity>((res) => {
      resolveEntity = res;
    });
    vi.mocked(orgApi.createLegalEntity).mockReturnValueOnce(entityPromise);

    let resolveBu: (val: BusinessUnit) => void;
    const buPromise = new Promise<BusinessUnit>((res) => {
      resolveBu = res;
    });
    vi.mocked(orgApi.createBusinessUnit).mockReturnValueOnce(buPromise);

    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="owner"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    // Start entity submit
    fireEvent.change(screen.getByTestId("entity-name-input"), { target: { value: "Concurrent Corp" } });
    fireEvent.click(screen.getByTestId("create-entity-btn"));
    expect(screen.getByTestId("create-entity-btn")).toBeDisabled();

    // Start BU submit
    fireEvent.change(screen.getByTestId("bu-name-input"), { target: { value: "Concurrent Unit" } });
    fireEvent.click(screen.getByTestId("create-bu-btn"));
    expect(screen.getByTestId("create-bu-btn")).toBeDisabled();

    // Resolve Entity first
    resolveEntity!({
      id: "le-conc-1",
      tenant_id: "tenant-alpha",
      name: "Concurrent Corp",
      registration_number: null,
      country: "DE",
      is_primary: false,
      created_at: "2026-10-29T12:00:00Z",
    });

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-conc-1")).toBeInTheDocument();
      expect(screen.getByTestId("create-entity-btn")).not.toBeDisabled();
    });

    // BU submit button is still active/pending
    expect(screen.getByTestId("create-bu-btn")).toBeDisabled();

    // Resolve BU second
    resolveBu!({
      id: "bu-conc-1",
      tenant_id: "tenant-alpha",
      legal_entity_id: "le-1",
      name: "Concurrent Unit",
      code: "CONC-1",
      created_at: "2026-10-29T12:00:00Z",
    });

    await waitFor(() => {
      expect(screen.getByTestId("bu-card-bu-conc-1")).toBeInTheDocument();
      expect(screen.getByTestId("create-bu-btn")).not.toBeDisabled();
    });
  });

  it("handles two independent concurrent form submissions finishing in reversed order B then A without stuck buttons", async () => {
    let resolveEntity: (val: LegalEntity) => void;
    const entityPromise = new Promise<LegalEntity>((res) => {
      resolveEntity = res;
    });
    vi.mocked(orgApi.createLegalEntity).mockReturnValueOnce(entityPromise);

    let resolveBu: (val: BusinessUnit) => void;
    const buPromise = new Promise<BusinessUnit>((res) => {
      resolveBu = res;
    });
    vi.mocked(orgApi.createBusinessUnit).mockReturnValueOnce(buPromise);

    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="owner"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    // Start entity submit
    fireEvent.change(screen.getByTestId("entity-name-input"), { target: { value: "Reversed Corp" } });
    fireEvent.click(screen.getByTestId("create-entity-btn"));
    expect(screen.getByTestId("create-entity-btn")).toBeDisabled();

    // Start BU submit
    fireEvent.change(screen.getByTestId("bu-name-input"), { target: { value: "Reversed Unit" } });
    fireEvent.click(screen.getByTestId("create-bu-btn"));
    expect(screen.getByTestId("create-bu-btn")).toBeDisabled();

    // Resolve BU first
    resolveBu!({
      id: "bu-rev-1",
      tenant_id: "tenant-alpha",
      legal_entity_id: "le-1",
      name: "Reversed Unit",
      code: "REV-1",
      created_at: "2026-10-29T12:00:00Z",
    });

    await waitFor(() => {
      expect(screen.getByTestId("bu-card-bu-rev-1")).toBeInTheDocument();
      expect(screen.getByTestId("create-bu-btn")).not.toBeDisabled();
    });

    // Entity submit button is still active/pending
    expect(screen.getByTestId("create-entity-btn")).toBeDisabled();

    // Resolve Entity second
    resolveEntity!({
      id: "le-rev-1",
      tenant_id: "tenant-alpha",
      name: "Reversed Corp",
      registration_number: null,
      country: "DE",
      is_primary: false,
      created_at: "2026-10-29T12:00:00Z",
    });

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-rev-1")).toBeInTheDocument();
      expect(screen.getByTestId("create-entity-btn")).not.toBeDisabled();
    });
  });

  it("renders read-only view without create forms for compliance_manager role", async () => {
    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="compliance_manager"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    // Read-only notices rendered
    const notices = screen.getAllByText(/Organization structure is managed by Owners and Administrators/i);
    expect(notices.length).toBeGreaterThanOrEqual(1);

    // Form inputs and submit buttons NOT rendered
    expect(screen.queryByTestId("create-entity-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("create-bu-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("create-loc-btn")).not.toBeInTheDocument();
  });

  it("renders read-only view without create forms for unrecognized or missing role", async () => {
    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole="some_unknown_role"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    // Read-only notices rendered
    expect(screen.getAllByText(/Organization structure is managed by Owners and Administrators/i).length).toBeGreaterThanOrEqual(1);

    // Form inputs and submit buttons NOT rendered
    expect(screen.queryByTestId("create-entity-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("create-bu-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("create-loc-btn")).not.toBeInTheDocument();
  });

  it("treats omitted and explicitly undefined userRole as read-only", async () => {
    // 1. Omitted role
    const { unmount } = renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    expect(screen.getAllByText(/Organization structure is managed by Owners and Administrators/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByTestId("create-entity-btn")).not.toBeInTheDocument();

    unmount();

    // 2. Explicitly undefined role
    renderWithI18n(
      <OrganizationWorkspaceV2
        tenantId="tenant-alpha"
        token="token-xyz"
        userRole={undefined}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("entity-card-le-1")).toBeInTheDocument();
    });

    expect(screen.getAllByText(/Organization structure is managed by Owners and Administrators/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByTestId("create-entity-btn")).not.toBeInTheDocument();
  });
});
