import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cleanUrlParams,
  clearStoredSession,
  generateCodeChallenge,
  generateCodeVerifier,
  generateRandomString,
  getExpectedRedirectUri,
  getStoredSession,
  getStoredToken,
  handleOidcCallback,
  startWorkforceLogin,
  isSafeUrl,
  isSessionExpired,
  parseCallbackMarkers,
  setStoredSession,
  STORAGE_KEYS,
} from "./auth";
import { CatalogDemoSessionResponse } from "./types";

describe("catalog demo auth utilities", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("stores and retrieves active staff session with isolated keys", () => {
    const mockSession: CatalogDemoSessionResponse = {
      user_id: "u-staff-1",
      display_name: "Staff Admin",
      authenticated_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 3600 * 1000).toISOString(),
      capabilities: ["DRAFT_READ"],
    };

    setStoredSession(mockSession);
    sessionStorage.setItem(STORAGE_KEYS.TOKEN, "bearer-jwt-token-123");

    // Verify isolated keys used
    expect(sessionStorage.getItem(STORAGE_KEYS.TOKEN)).toBe("bearer-jwt-token-123");
    expect(sessionStorage.getItem(STORAGE_KEYS.SESSION_INFO)).toContain("Staff Admin");

    // Verify tenant keys are NOT touched
    expect(sessionStorage.getItem("conformly.access_token")).toBeNull();
    expect(sessionStorage.getItem("conformly.oidc_state")).toBeNull();

    // Verify retrieval
    const retrieved = getStoredSession();
    expect(retrieved).not.toBeNull();
    expect(retrieved?.user_id).toBe("u-staff-1");
    expect(retrieved?.display_name).toBe("Staff Admin");
    expect(getStoredToken()).toBe("bearer-jwt-token-123");
  });

  it("automatically clears and ignores expired stored session", () => {
    const expiredSession: CatalogDemoSessionResponse = {
      user_id: "u-staff-2",
      display_name: "Expired Staff",
      authenticated_at: new Date(Date.now() - 50000).toISOString(),
      expires_at: new Date(Date.now() - 1000).toISOString(), // expired
      capabilities: ["DRAFT_READ"],
    };

    setStoredSession(expiredSession);
    expect(getStoredSession()).toBeNull();
    expect(sessionStorage.getItem(STORAGE_KEYS.SESSION_INFO)).toBeNull();
  });

  it("clears all catalog demo storage keys on clearStoredSession", () => {
    sessionStorage.setItem(STORAGE_KEYS.TOKEN, "jwt-token");
    sessionStorage.setItem(STORAGE_KEYS.SESSION_INFO, "{}");
    sessionStorage.setItem(STORAGE_KEYS.PKCE_VERIFIER, "verifier-1");
    sessionStorage.setItem(STORAGE_KEYS.PKCE_STATE, "state-1");

    clearStoredSession();

    expect(sessionStorage.getItem(STORAGE_KEYS.TOKEN)).toBeNull();
    expect(sessionStorage.getItem(STORAGE_KEYS.SESSION_INFO)).toBeNull();
    expect(sessionStorage.getItem(STORAGE_KEYS.PKCE_VERIFIER)).toBeNull();
    expect(sessionStorage.getItem(STORAGE_KEYS.PKCE_STATE)).toBeNull();
  });

  it("evaluates session expiration correctly", () => {
    expect(isSessionExpired(null)).toBe(true);

    const pastSession: CatalogDemoSessionResponse = {
      user_id: "u1",
      display_name: "U1",
      authenticated_at: new Date(Date.now() - 10000).toISOString(),
      expires_at: new Date(Date.now() - 5000).toISOString(),
      capabilities: ["DRAFT_READ"],
    };
    expect(isSessionExpired(pastSession)).toBe(true);

    const futureSession: CatalogDemoSessionResponse = {
      user_id: "u2",
      display_name: "U2",
      authenticated_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 60000).toISOString(),
      capabilities: ["DRAFT_READ"],
    };
    expect(isSessionExpired(futureSession)).toBe(false);
  });

  it("validates safe URLs strictly (HTTPS and loopback HTTP only, rejects credentials)", () => {
    expect(isSafeUrl("https://auth.workforce.example.com/oauth2/auth")).toBe(true);
    expect(isSafeUrl("http://127.0.0.1:8080/oauth2/auth")).toBe(true);
    expect(isSafeUrl("http://localhost:8080/oauth2/auth")).toBe(true);
    expect(isSafeUrl("http://[::1]:8080/oauth2/auth")).toBe(true);

    // Insecure non-loopback HTTP rejected
    expect(isSafeUrl("http://auth.insecure.com/oauth2/auth")).toBe(false);
    expect(isSafeUrl("javascript:alert(1)")).toBe(false);
    expect(isSafeUrl("data:text/html,evil")).toBe(false);

    // Embedded URL credentials rejected
    expect(isSafeUrl("https://user:password@auth.workforce.example.com/oauth2/token")).toBe(false);
    expect(isSafeUrl("http://admin:secret@127.0.0.1:8080/token")).toBe(false);
  });

  it("enforces redirect_uri exactly matching current origin plus /catalog-demo", () => {
    // Other origin redirect rejected
    vi.stubEnv("VITE_WORKFORCE_REDIRECT_URI", "https://other-origin.invalid/callback");
    expect(() => getExpectedRedirectUri()).toThrow(/Redirect URI must match current origin/i);

    // Current origin with wrong path rejected
    vi.stubEnv("VITE_WORKFORCE_REDIRECT_URI", `${window.location.origin}/wrong-path`);
    expect(() => getExpectedRedirectUri()).toThrow(/Redirect URI must match current origin/i);

    // Current origin + /catalog-demo accepted
    vi.stubEnv("VITE_WORKFORCE_REDIRECT_URI", `${window.location.origin}/catalog-demo`);
    expect(getExpectedRedirectUri()).toBe(`${window.location.origin}/catalog-demo`);
  });

  it("constructs authorization query parameters with URL APIs preserving pre-existing params", async () => {
    vi.stubEnv("VITE_WORKFORCE_AUTHORIZATION_URL", "https://auth.example.com/oauth2/auth?prompt=login");
    vi.stubEnv("VITE_WORKFORCE_TOKEN_URL", "https://auth.example.com/oauth2/token");
    vi.stubEnv("VITE_WORKFORCE_CLIENT_ID", "client-xyz");
    vi.stubEnv("VITE_WORKFORCE_REDIRECT_URI", "http://localhost:5173/catalog-demo");

    let navigatedUrl = "";
    const originalLocation = window.location;
    const assignMock = vi.fn().mockImplementation((url: string) => {
      navigatedUrl = url;
    });
    // @ts-expect-error mock window.location for navigation
    delete window.location;
    // @ts-expect-error mock window.location for navigation
    window.location = {
      ...originalLocation,
      origin: "http://localhost:5173",
      assign: assignMock,
    };

    try {
      await startWorkforceLogin();

      expect(navigatedUrl).toBeTruthy();
      const parsed = new URL(navigatedUrl);
      expect(parsed.origin).toBe("https://auth.example.com");
      expect(parsed.pathname).toBe("/oauth2/auth");
      expect(parsed.searchParams.get("prompt")).toBe("login");
      expect(parsed.searchParams.get("client_id")).toBe("client-xyz");
      expect(parsed.searchParams.get("response_type")).toBe("code");
      expect(parsed.searchParams.get("code_challenge_method")).toBe("S256");
      expect(parsed.searchParams.get("max_age")).toBe("900");
      expect(parsed.searchParams.get("redirect_uri")).toBe("http://localhost:5173/catalog-demo");
    } finally {
      // @ts-expect-error test window location reset
      window.location = originalLocation;
    }
  });

  it("generates cryptographic PKCE S256 verifier and challenge", async () => {
    const verifier = generateCodeVerifier(64);
    expect(verifier.length).toBe(64);
    expect(verifier).toMatch(/^[A-Za-z0-9\-._~]+$/);

    const challenge = await generateCodeChallenge(verifier);
    expect(challenge.length).toBeGreaterThan(30);
    expect(challenge).toMatch(/^[A-Za-z0-9\-_]+$/);
    expect(challenge).not.toContain("+");
    expect(challenge).not.toContain("/");
    expect(challenge).not.toContain("=");

    const state = generateRandomString(32);
    expect(state.length).toBe(32);
    expect(state).toMatch(/^[A-Za-z0-9\-._~]+$/);
  });

  it("handleOidcCallback rejects state mismatch or missing verifier", async () => {
    sessionStorage.setItem(STORAGE_KEYS.PKCE_STATE, "expected-state");
    sessionStorage.setItem(STORAGE_KEYS.PKCE_VERIFIER, "expected-verifier");

    await expect(handleOidcCallback("code-123", "wrong-state")).rejects.toThrow(
      "Invalid or mismatched OIDC callback state"
    );

    sessionStorage.setItem(STORAGE_KEYS.PKCE_STATE, "match-state");
    sessionStorage.removeItem(STORAGE_KEYS.PKCE_VERIFIER);

    await expect(handleOidcCallback("code-123", "match-state")).rejects.toThrow(
      "Missing PKCE code verifier"
    );
  });

  it("handleOidcCallback extracts signed id_token from normal exchange and does not commit to storage directly", async () => {
    vi.stubEnv("VITE_WORKFORCE_OIDC_AUTHORIZATION_URL", "https://auth.example.com/auth");
    vi.stubEnv("VITE_WORKFORCE_OIDC_TOKEN_URL", "https://auth.example.com/token");
    vi.stubEnv("VITE_WORKFORCE_OIDC_CLIENT_ID", "client-123");
    vi.stubEnv("VITE_WORKFORCE_OIDC_REDIRECT_URI", `${window.location.origin}/catalog-demo`);

    sessionStorage.setItem(STORAGE_KEYS.PKCE_STATE, "state-valid");
    sessionStorage.setItem(STORAGE_KEYS.PKCE_VERIFIER, "verifier-valid");

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: "opaque-access-token-xyz",
          id_token: "signed.id.token.jwt",
          token_type: "Bearer",
          expires_in: 3600,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const token = await handleOidcCallback("valid-auth-code", "state-valid");
    expect(token).toBe("signed.id.token.jwt");

    // Transient PKCE state cleared
    expect(sessionStorage.getItem(STORAGE_KEYS.PKCE_STATE)).toBeNull();
    expect(sessionStorage.getItem(STORAGE_KEYS.PKCE_VERIFIER)).toBeNull();

    // Crucial: handleOidcCallback must NOT commit token to storage directly
    // Committing is strictly reserved for the active component operation fence
    expect(sessionStorage.getItem(STORAGE_KEYS.TOKEN)).toBeNull();
  });

  it("handleOidcCallback rejects code exchange missing non-empty id_token", async () => {
    vi.stubEnv("VITE_WORKFORCE_OIDC_AUTHORIZATION_URL", "https://auth.example.com/auth");
    vi.stubEnv("VITE_WORKFORCE_OIDC_TOKEN_URL", "https://auth.example.com/token");
    vi.stubEnv("VITE_WORKFORCE_OIDC_CLIENT_ID", "client-123");
    vi.stubEnv("VITE_WORKFORCE_OIDC_REDIRECT_URI", `${window.location.origin}/catalog-demo`);

    sessionStorage.setItem(STORAGE_KEYS.PKCE_STATE, "state-valid");
    sessionStorage.setItem(STORAGE_KEYS.PKCE_VERIFIER, "verifier-valid");

    // Only opaque access_token returned
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            access_token: "opaque-access-token-only",
            token_type: "Bearer",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );

    await expect(handleOidcCallback("code-xyz", "state-valid")).rejects.toThrow(
      /signed workforce ID token/
    );
  });

  it("parseCallbackMarkers detects markers and rejects invalid combinations", () => {
    // Clean params
    expect(parseCallbackMarkers(new URLSearchParams("foo=bar"))).toEqual({
      isCallback: false,
      valid: false,
    });

    // Valid code + state
    const valid = parseCallbackMarkers(new URLSearchParams("code=abc&state=xyz"));
    expect(valid.isCallback).toBe(true);
    expect(valid.valid).toBe(true);
    expect(valid.code).toBe("abc");
    expect(valid.state).toBe("xyz");

    // Code without state -> invalid
    const noState = parseCallbackMarkers(new URLSearchParams("code=abc"));
    expect(noState.isCallback).toBe(true);
    expect(noState.valid).toBe(false);
    expect(noState.error).toContain("failed or was cancelled");

    // Error from provider
    const err = parseCallbackMarkers(new URLSearchParams("error=access_denied&error_description=Denied"));
    expect(err.isCallback).toBe(true);
    expect(err.valid).toBe(false);
    expect(err.error).toContain("failed or was cancelled");

    // Conflict: code AND error -> invalid
    const conflict = parseCallbackMarkers(new URLSearchParams("code=abc&error=access_denied"));
    expect(conflict.isCallback).toBe(true);
    expect(conflict.valid).toBe(false);
  });

  it("cleanUrlParams replaces window state when search params exist", () => {
    window.history.pushState({}, "", "/catalog-demo?code=123&state=abc");
    const replaceStateSpy = vi.spyOn(window.history, "replaceState");
    cleanUrlParams();
    expect(replaceStateSpy).toHaveBeenCalled();
    replaceStateSpy.mockRestore();
    window.history.pushState({}, "", "/");
  });

  it("rejects missing or blank OIDC configuration before redirect or fetch", async () => {
    // 1. Missing authorization URL
    vi.stubEnv("VITE_WORKFORCE_AUTHORIZATION_URL", "");
    vi.stubEnv("VITE_WORKFORCE_OIDC_AUTHORIZATION_URL", "");
    vi.stubEnv("VITE_WORKFORCE_CLIENT_ID", "client-1");
    await expect(startWorkforceLogin()).rejects.toThrow(/Missing required OIDC configuration: workforce authorization URL/);

    // 2. Missing client ID
    vi.stubEnv("VITE_WORKFORCE_AUTHORIZATION_URL", "https://auth.test/auth");
    vi.stubEnv("VITE_WORKFORCE_CLIENT_ID", "  ");
    vi.stubEnv("VITE_WORKFORCE_OIDC_CLIENT_ID", "");
    await expect(startWorkforceLogin()).rejects.toThrow(/Missing required OIDC configuration: workforce client ID/);

    // 3. Missing token URL in handleOidcCallback
    sessionStorage.setItem(STORAGE_KEYS.PKCE_STATE, "state-cfg");
    sessionStorage.setItem(STORAGE_KEYS.PKCE_VERIFIER, "verifier-cfg");
    vi.stubEnv("VITE_WORKFORCE_TOKEN_URL", "");
    vi.stubEnv("VITE_WORKFORCE_OIDC_TOKEN_URL", "");
    vi.stubEnv("VITE_WORKFORCE_CLIENT_ID", "client-1");
    await expect(handleOidcCallback("code-1", "state-cfg")).rejects.toThrow(/Missing required OIDC configuration: workforce token URL/);
  });

  it("parseCallbackMarkers strictly rejects duplicate, empty, and invalid marker combinations", () => {
    // Repeated code query param
    const dupCode = new URLSearchParams("code=c1&code=c2&state=s1");
    expect(parseCallbackMarkers(dupCode)).toEqual({
      isCallback: true,
      valid: false,
      error: "Workforce authentication failed or was cancelled",
    });

    // Repeated state query param
    const dupState = new URLSearchParams("code=c1&state=s1&state=s2");
    expect(parseCallbackMarkers(dupState)).toEqual({
      isCallback: true,
      valid: false,
      error: "Workforce authentication failed or was cancelled",
    });

    // Empty error= marker
    const emptyErr = new URLSearchParams("error=");
    expect(parseCallbackMarkers(emptyErr)).toEqual({
      isCallback: true,
      valid: false,
      error: "Workforce authentication failed or was cancelled",
    });

    // Incomplete markers: code without state
    const missingState = new URLSearchParams("code=c1");
    expect(parseCallbackMarkers(missingState)).toEqual({
      isCallback: true,
      valid: false,
      error: "Workforce authentication failed or was cancelled",
    });

    // Empty code
    const emptyCode = new URLSearchParams("code=&state=s1");
    expect(parseCallbackMarkers(emptyCode)).toEqual({
      isCallback: true,
      valid: false,
      error: "Workforce authentication failed or was cancelled",
    });
  });

  it("handleOidcCallback failure does not clear pre-existing stored session (side-effect-free helper)", async () => {
    vi.stubEnv("VITE_WORKFORCE_TOKEN_URL", "https://auth.example.com/token");
    vi.stubEnv("VITE_WORKFORCE_CLIENT_ID", "client-123");
    vi.stubEnv("VITE_WORKFORCE_REDIRECT_URI", `${window.location.origin}/catalog-demo`);

    sessionStorage.setItem(STORAGE_KEYS.PKCE_STATE, "state-valid");
    sessionStorage.setItem(STORAGE_KEYS.PKCE_VERIFIER, "verifier-valid");

    // Pre-existing active session in storage
    sessionStorage.setItem(STORAGE_KEYS.TOKEN, "newer-active-token");
    sessionStorage.setItem(STORAGE_KEYS.SESSION_INFO, JSON.stringify({ user_id: "u-newer" }));

    // Token endpoint returns 400
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: "invalid_grant" }), {
          status: 400,
          headers: { "Content-Type": "application/json" },
        })
      )
    );

    await expect(handleOidcCallback("code-xyz", "state-valid")).rejects.toThrow(
      /Token exchange failed with HTTP 400/
    );

    // Stored session must NOT be cleared by helper failure!
    expect(sessionStorage.getItem(STORAGE_KEYS.TOKEN)).toBe("newer-active-token");
    expect(sessionStorage.getItem(STORAGE_KEYS.SESSION_INFO)).not.toBeNull();
  });
});
