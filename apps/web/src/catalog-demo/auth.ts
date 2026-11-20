/**
 * Isolated workforce session management and real OIDC PKCE flow for catalog demo.
 */

import { CatalogDemoSessionResponse } from "./types";

export const STORAGE_KEYS = {
  TOKEN: "conformly.catalog_demo.token",
  SESSION_INFO: "conformly.catalog_demo.session_info",
  PKCE_VERIFIER: "conformly.catalog_demo.pkce_verifier",
  PKCE_STATE: "conformly.catalog_demo.pkce_state",
} as const;

export function isSafeUrl(urlStr: string): boolean {
  try {
    const parsed = new URL(urlStr);
    // Disallow credentials in URL
    if (parsed.username || parsed.password) {
      return false;
    }
    if (parsed.protocol === "https:") {
      return true;
    }
    if (
      parsed.protocol === "http:" &&
      (parsed.hostname === "127.0.0.1" ||
        parsed.hostname === "localhost" ||
        parsed.hostname === "::1" ||
        parsed.hostname === "[::1]")
    ) {
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

export function getExpectedRedirectUri(): string {
  const custom = import.meta.env.VITE_WORKFORCE_REDIRECT_URI || import.meta.env.VITE_WORKFORCE_OIDC_REDIRECT_URI;
  const exact = `${window.location.origin}/catalog-demo`;
  if (custom && custom.trim()) {
    const normalized = custom.trim();
    if (normalized !== exact) {
      throw new Error("Configured workforce redirect URI must match current origin plus /catalog-demo exactly");
    }
    return exact;
  }
  return exact;
}

export function getOidcConfig(): { authUrl: string; tokenUrl: string; clientId: string } {
  const authUrl = (
    import.meta.env.VITE_WORKFORCE_AUTHORIZATION_URL ||
    import.meta.env.VITE_WORKFORCE_OIDC_AUTHORIZATION_URL ||
    ""
  ).trim();
  const tokenUrl = (
    import.meta.env.VITE_WORKFORCE_TOKEN_URL ||
    import.meta.env.VITE_WORKFORCE_OIDC_TOKEN_URL ||
    ""
  ).trim();
  const clientId = (
    import.meta.env.VITE_WORKFORCE_CLIENT_ID ||
    import.meta.env.VITE_WORKFORCE_OIDC_CLIENT_ID ||
    ""
  ).trim();
  return { authUrl, tokenUrl, clientId };
}

export function getStoredToken(): string | null {
  return sessionStorage.getItem(STORAGE_KEYS.TOKEN);
}

export function getStoredSession(): CatalogDemoSessionResponse | null {
  const raw = sessionStorage.getItem(STORAGE_KEYS.SESSION_INFO);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as CatalogDemoSessionResponse;
    if (isSessionExpired(parsed)) {
      clearStoredSession();
      return null;
    }
    return parsed;
  } catch {
    clearStoredSession();
    return null;
  }
}

export function setStoredSession(session: CatalogDemoSessionResponse): void {
  sessionStorage.setItem(STORAGE_KEYS.SESSION_INFO, JSON.stringify(session));
}

export function clearStoredSession(): void {
  sessionStorage.removeItem(STORAGE_KEYS.TOKEN);
  sessionStorage.removeItem(STORAGE_KEYS.SESSION_INFO);
  sessionStorage.removeItem(STORAGE_KEYS.PKCE_VERIFIER);
  sessionStorage.removeItem(STORAGE_KEYS.PKCE_STATE);
}

export function isSessionExpired(session: CatalogDemoSessionResponse | null): boolean {
  if (!session || !session.expires_at) {
    return true;
  }
  try {
    const expTime = new Date(session.expires_at).getTime();
    return Date.now() >= expTime;
  } catch {
    return true;
  }
}

export function generateRandomString(length: number): string {
  const charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";
  const randomValues = new Uint8Array(length);
  crypto.getRandomValues(randomValues);
  let result = "";
  for (let i = 0; i < length; i++) {
    result += charset[randomValues[i] % charset.length];
  }
  return result;
}

export function generateCodeVerifier(length = 64): string {
  const boundedLength = Math.max(43, Math.min(128, length));
  return generateRandomString(boundedLength);
}

export async function generateCodeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);
  const base64 = btoa(String.fromCharCode(...new Uint8Array(digest)));
  return base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export async function startWorkforceLogin(): Promise<void> {
  const { authUrl, clientId } = getOidcConfig();

  if (!authUrl) {
    throw new Error("Missing required OIDC configuration: workforce authorization URL");
  }
  if (!clientId) {
    throw new Error("Missing required OIDC configuration: workforce client ID");
  }

  const redirectUri = getExpectedRedirectUri();

  if (!isSafeUrl(authUrl)) {
    throw new Error("Configured workforce authorization URL must use HTTPS or permitted loopback");
  }

  const verifier = generateCodeVerifier(64);
  const challenge = await generateCodeChallenge(verifier);
  const state = generateRandomString(32);

  sessionStorage.setItem(STORAGE_KEYS.PKCE_VERIFIER, verifier);
  sessionStorage.setItem(STORAGE_KEYS.PKCE_STATE, state);

  const url = new URL(authUrl);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("scope", "openid profile email");
  url.searchParams.set("state", state);
  url.searchParams.set("code_challenge", challenge);
  url.searchParams.set("code_challenge_method", "S256");
  url.searchParams.set("max_age", "900");

  window.location.assign(url.toString());
}

export function parseCallbackMarkers(searchParams?: URLSearchParams): {
  isCallback: boolean;
  valid: boolean;
  code?: string;
  state?: string;
  error?: string;
} {
  try {
    const params = searchParams || new URLSearchParams(window.location.search);
    const hasCode = params.has("code");
    const hasState = params.has("state");
    const hasError = params.has("error");

    if (!hasCode && !hasState && !hasError) {
      return { isCallback: false, valid: false };
    }

    // Reject duplicate code/state/error values
    const codeValues = params.getAll("code");
    const stateValues = params.getAll("state");
    const errorValues = params.getAll("error");

    if (codeValues.length > 1 || stateValues.length > 1 || errorValues.length > 1) {
      return {
        isCallback: true,
        valid: false,
        error: "Workforce authentication failed or was cancelled",
      };
    }

    // Any error marker (including empty error=) means failure
    if (hasError) {
      return {
        isCallback: true,
        valid: false,
        error: "Workforce authentication failed or was cancelled",
      };
    }

    const code = params.get("code")?.trim();
    const state = params.get("state")?.trim();

    // Reject incomplete or empty marker combinations
    if (!code || !state) {
      return {
        isCallback: true,
        valid: false,
        error: "Workforce authentication failed or was cancelled",
      };
    }

    return { isCallback: true, valid: true, code, state };
  } catch {
    return { isCallback: false, valid: false };
  }
}

export function cleanUrlParams(): void {
  try {
    const url = new URL(window.location.href);
    if (url.search) {
      url.search = "";
      window.history.replaceState({}, document.title, url.toString());
    }
  } catch {
    // Non-blocking fallback
  }
}

export async function handleOidcCallback(
  code: string,
  state: string,
  signal?: AbortSignal,
  preloadedVerifier?: string | null
): Promise<string> {
  const storedState = sessionStorage.getItem(STORAGE_KEYS.PKCE_STATE);
  const storedVerifier = preloadedVerifier ?? sessionStorage.getItem(STORAGE_KEYS.PKCE_VERIFIER);

  // Validate state and verifier FIRST before consuming or configuration check
  if (!storedState || storedState !== state) {
    throw new Error("Invalid or mismatched OIDC callback state");
  }

  if (!storedVerifier) {
    throw new Error("Missing PKCE code verifier");
  }

  // Consume PKCE state immediately to prevent replay
  sessionStorage.removeItem(STORAGE_KEYS.PKCE_VERIFIER);
  sessionStorage.removeItem(STORAGE_KEYS.PKCE_STATE);

  const { tokenUrl, clientId } = getOidcConfig();

  if (!tokenUrl) {
    throw new Error("Missing required OIDC configuration: workforce token URL");
  }
  if (!clientId) {
    throw new Error("Missing required OIDC configuration: workforce client ID");
  }

  const redirectUri = getExpectedRedirectUri();

  if (!isSafeUrl(tokenUrl)) {
    throw new Error("Configured workforce token URL must use HTTPS or permitted loopback");
  }

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri,
    client_id: clientId,
    code_verifier: storedVerifier,
  });

  const response = await fetch(tokenUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Accept: "application/json",
    },
    body: body.toString(),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Token exchange failed with HTTP ${response.status}`);
  }

  const data = (await response.json()) as { id_token?: string };
  const idToken = data.id_token;

  if (!idToken || typeof idToken !== "string" || !idToken.trim()) {
    throw new Error("Workforce token response missing valid signed workforce ID token");
  }

  // Crucial: do NOT commit to storage here. The active component fence alone commits credentials.
  return idToken.trim();
}
