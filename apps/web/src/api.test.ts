import { afterEach, describe, expect, it, vi } from "vitest";

import { AccessDeniedError, SessionExpiredError, listMyTenants, verifyTenant } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("typed API client", () => {
  it("maps expired sessions without exposing response details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    await expect(listMyTenants("secret-token")).rejects.toBeInstanceOf(SessionExpiredError);
  });

  it("maps server-side tenant authorization denial", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 403 })));
    await expect(verifyTenant("secret-token", "tenant-id")).rejects.toBeInstanceOf(
      AccessDeniedError,
    );
  });
});
