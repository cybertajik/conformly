const ACCESS_TOKEN_KEY = "conformly.access_token";
const OIDC_STATE_KEY = "conformly.oidc_state";
const PKCE_VERIFIER_KEY = "conformly.pkce_verifier";

function base64Url(bytes: Uint8Array): string {
  let binary = "";
  bytes.forEach((value) => (binary += String.fromCharCode(value)));
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function configured(name: string, value: string | undefined): string {
  if (!value) throw new Error(`${name} is not configured.`);
  return value;
}

export function getAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS_TOKEN_KEY);
}

export function clearLocalSession(): void {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(OIDC_STATE_KEY);
  sessionStorage.removeItem(PKCE_VERIFIER_KEY);
}

export async function beginOidcLogin(): Promise<void> {
  const authorizationUrl = configured(
    "OIDC authorization URL",
    import.meta.env.VITE_OIDC_AUTHORIZATION_URL,
  );
  const clientId = configured("OIDC client ID", import.meta.env.VITE_OIDC_CLIENT_ID);
  const redirectUri = configured("OIDC redirect URI", import.meta.env.VITE_OIDC_REDIRECT_URI);
  const verifier = base64Url(crypto.getRandomValues(new Uint8Array(32)));
  const state = base64Url(crypto.getRandomValues(new Uint8Array(24)));
  const challenge = base64Url(
    new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))),
  );
  sessionStorage.setItem(PKCE_VERIFIER_KEY, verifier);
  sessionStorage.setItem(OIDC_STATE_KEY, state);
  const url = new URL(authorizationUrl);
  url.search = new URLSearchParams({
    response_type: "code",
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: import.meta.env.VITE_OIDC_SCOPES ?? "openid profile email",
    state,
    code_challenge: challenge,
    code_challenge_method: "S256",
  }).toString();
  window.location.assign(url);
}

export function isOidcCallback(): boolean {
  const params = new URLSearchParams(window.location.search);
  return params.has("code") || params.has("error");
}

export async function completeOidcLogin(): Promise<string> {
  const params = new URLSearchParams(window.location.search);
  const returnedState = params.get("state");
  const expectedState = sessionStorage.getItem(OIDC_STATE_KEY);
  const verifier = sessionStorage.getItem(PKCE_VERIFIER_KEY);
  const code = params.get("code");
  if (params.has("error") || !code || !expectedState || returnedState !== expectedState || !verifier) {
    clearLocalSession();
    throw new Error("The identity-provider response could not be verified.");
  }
  const tokenUrl = configured("OIDC token URL", import.meta.env.VITE_OIDC_TOKEN_URL);
  const response = await fetch(tokenUrl, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      client_id: configured("OIDC client ID", import.meta.env.VITE_OIDC_CLIENT_ID),
      redirect_uri: configured("OIDC redirect URI", import.meta.env.VITE_OIDC_REDIRECT_URI),
      code_verifier: verifier,
    }),
  });
  const body = (await response.json()) as { access_token?: unknown };
  if (!response.ok || typeof body.access_token !== "string") {
    clearLocalSession();
    throw new Error("Sign-in could not be completed.");
  }
  sessionStorage.setItem(ACCESS_TOKEN_KEY, body.access_token);
  sessionStorage.removeItem(OIDC_STATE_KEY);
  sessionStorage.removeItem(PKCE_VERIFIER_KEY);
  window.history.replaceState({}, document.title, window.location.pathname);
  return body.access_token;
}
