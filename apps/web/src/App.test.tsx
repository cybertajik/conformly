import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import { canManageMemberships } from "./permissions";

describe("App", () => {
  it("shows the authentication entry point", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Conformly" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("uses role-aware navigation only as a usability hint", () => {
    expect(canManageMemberships("owner")).toBe(true);
    expect(canManageMemberships("administrator")).toBe(true);
    expect(canManageMemberships("auditor")).toBe(false);
  });
});
