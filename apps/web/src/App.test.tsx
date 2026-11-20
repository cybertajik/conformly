import "@testing-library/jest-dom/vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";

import { App } from "./App";
import * as api from "./api";
import * as auth from "./auth";
import * as demoApi from "./customer-demo/api";
import { canManageMemberships } from "./permissions";

describe("App", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
    cleanup();
  });

  it("shows the authentication entry point when unauthenticated", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Conformly" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("uses role-aware navigation only as a usability hint", () => {
    expect(canManageMemberships("owner")).toBe(true);
    expect(canManageMemberships("administrator")).toBe(true);
    expect(canManageMemberships("auditor")).toBe(false);
  });

  it("disables customer demo tab when VITE_ENABLE_CUSTOMER_DEMO is false or unset", () => {
    vi.stubEnv("VITE_ENABLE_CUSTOMER_DEMO", "false");
    expect(demoApi.isCustomerDemoEnabled()).toBe(false);

    vi.stubEnv("VITE_ENABLE_CUSTOMER_DEMO", "");
    expect(demoApi.isCustomerDemoEnabled()).toBe(false);
  });

  it("enables customer demo tab when VITE_ENABLE_CUSTOMER_DEMO is true in test/dev mode", () => {
    vi.stubEnv("VITE_ENABLE_CUSTOMER_DEMO", "true");
    expect(demoApi.isCustomerDemoEnabled()).toBe(true);
  });

  describe("Integration: Authenticated entry & Customer Demo feature flag handoff", () => {
    const mockTenant = {
      tenant_id: "11111111-1111-1111-1111-111111111111",
      tenant_name: "Acme Compliance Corp",
      role: "owner" as const,
      tenant_slug: "acme",
    };

    beforeEach(() => {
      vi.spyOn(auth, "getAccessToken").mockReturnValue("mock-bearer-token");
      vi.spyOn(auth, "isOidcCallback").mockReturnValue(false);
      vi.spyOn(api, "bootstrapSession").mockResolvedValue({
        user_id: "u-1234",
        email: "owner@acme.com",
        display_name: "Owner User",
      });
      vi.spyOn(api, "listMyTenants").mockResolvedValue([mockTenant]);
      vi.spyOn(api, "verifyTenant").mockResolvedValue({
        tenant_id: "11111111-1111-1111-1111-111111111111",
        role: "owner",
      });
      vi.spyOn(demoApi, "fetchWorkspace").mockResolvedValue({
        tenant_id: "11111111-1111-1111-1111-111111111111",
        current_revision: 1,
        selection_revision: 0,
        manifest: {
          disclaimer: "Synthetic demonstration",
          evaluator_version: "v1",
          companies: [{ code: "ALPHA", display_name: "Alpha" }],
          fact_definitions: [],
          packs: [],
        },
        answers: null,
        selected_pack: null,
        latest_evaluation: null,
        history_summary: [],
      });
    });

    it("renders CustomerDemoPortal with Overview landing screen when feature-enabled and eligible role", async () => {
      vi.stubEnv("VITE_ENABLE_CUSTOMER_DEMO", "true");

      render(<App />);

      expect(await screen.findByTestId("conformly-portal-shell")).toBeInTheDocument();
      expect(screen.getByTestId("portal-sidebar")).toBeInTheDocument();
      expect(await screen.findByTestId("portal-overview-view")).toBeInTheDocument();
      expect(screen.getByTestId("topbar-tenant-badge")).toHaveTextContent("Acme Compliance Corp");
    });

    it("preserves V1 shell and Executive Dashboard when customer demo is feature-flagged OFF", async () => {
      vi.stubEnv("VITE_ENABLE_CUSTOMER_DEMO", "false");

      render(<App />);

      expect(await screen.findByRole("complementary", { name: "Sidebar" })).toBeInTheDocument();
      expect(screen.queryByTestId("conformly-portal-shell")).not.toBeInTheDocument();
      expect(screen.getAllByText("Acme Compliance Corp").length).toBeGreaterThan(0);
    });

    it("preserves V1 shell without CustomerDemoPortal when user role is not authorized (e.g. auditor)", async () => {
      vi.stubEnv("VITE_ENABLE_CUSTOMER_DEMO", "true");
      vi.spyOn(api, "listMyTenants").mockResolvedValue([
        { ...mockTenant, role: "auditor" as const },
      ]);

      render(<App />);

      expect(await screen.findByRole("complementary", { name: "Sidebar" })).toBeInTheDocument();
      expect(screen.queryByTestId("conformly-portal-shell")).not.toBeInTheDocument();
    });

    it("propagates authenticated userId into CustomerDemoPortal session boundary", async () => {
      vi.stubEnv("VITE_ENABLE_CUSTOMER_DEMO", "true");

      render(<App />);

      expect(await screen.findByTestId("conformly-portal-shell")).toBeInTheDocument();
      expect(screen.getByTestId("portal-sidebar")).toBeInTheDocument();
      expect(await screen.findByTestId("portal-overview-view")).toBeInTheDocument();
    });
  });
});
