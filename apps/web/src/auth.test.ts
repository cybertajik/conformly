import { beforeEach, describe, expect, it } from "vitest";

import { completeOidcLogin } from "./auth";

describe("OIDC callback", () => {
  beforeEach(() => {
    sessionStorage.clear();
    window.history.replaceState({}, "", "/?code=code&state=untrusted-state");
  });

  it("fails closed when callback state does not match", async () => {
    sessionStorage.setItem("conformly.oidc_state", "expected-state");
    sessionStorage.setItem("conformly.pkce_verifier", "verifier");
    await expect(completeOidcLogin()).rejects.toThrow(
      "The identity-provider response could not be verified.",
    );
    expect(sessionStorage.getItem("conformly.oidc_state")).toBeNull();
    expect(sessionStorage.getItem("conformly.pkce_verifier")).toBeNull();
  });
});
