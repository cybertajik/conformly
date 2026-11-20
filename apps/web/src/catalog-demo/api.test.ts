import { afterEach, describe, expect, it, vi } from "vitest";

import {
  bootstrapSession,
  CatalogApiError,
  fetchCatalogGraph,
  getApiBaseUrl,
  revokeSession,
  verifySession,
} from "./api";
import { CatalogDemoGraphResponse, CatalogDemoSessionResponse } from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("catalog demo API client", () => {
  describe("getApiBaseUrl", () => {
    it("returns default http://localhost:8000/v2 when no env configured", () => {
      expect(getApiBaseUrl()).toBe("http://localhost:8000/v2");
    });

    it("appends /v2 exactly once to VITE_API_BASE_URL", () => {
      vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000");
      expect(getApiBaseUrl()).toBe("http://localhost:8000/v2");
    });

    it("does not duplicate /v2 if VITE_API_BASE_URL already ends with /v2", () => {
      vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000/v2");
      expect(getApiBaseUrl()).toBe("http://localhost:8000/v2");
    });

    it("prefers VITE_CATALOG_DEMO_API_BASE_URL as explicit /v2 root", () => {
      vi.stubEnv("VITE_CATALOG_DEMO_API_BASE_URL", "https://api.conformly.example.com/v2");
      vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000");
      expect(getApiBaseUrl()).toBe("https://api.conformly.example.com/v2");
    });
  });

  it("bootstraps staff session via POST /v2/catalog-demo/session with bearer auth and signal", async () => {
    const mockSession: CatalogDemoSessionResponse = {
      user_id: "u-1",
      display_name: "Staff Admin",
      authenticated_at: new Date().toISOString(),
      expires_at: new Date().toISOString(),
      capabilities: ["DRAFT_READ"],
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockSession), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const controller = new AbortController();
    const res = await bootstrapSession("valid.workforce.jwt", controller.signal);
    expect(res.user_id).toBe("u-1");
    expect(res.capabilities).toContain("DRAFT_READ");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/v2/catalog-demo/session");
    expect(init.method).toBe("POST");
    expect(init.headers["Authorization"]).toBe("Bearer valid.workforce.jwt");
    expect(init.signal).toBe(controller.signal);
  });

  it("maps 401 authentication rejection to CatalogApiError(401)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() =>
        Promise.resolve(
          new Response(JSON.stringify({ detail: "Token expired or signature invalid" }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          })
        )
      )
    );

    await expect(bootstrapSession("bad.jwt")).rejects.toBeInstanceOf(CatalogApiError);
    await expect(bootstrapSession("bad.jwt")).rejects.toMatchObject({
      name: "CatalogApiError",
      status: 401,
      message: "Token expired or signature invalid",
    });
  });

  it("maps 403 authorization denial when user is not platform admin", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ detail: "Staff user is not an active platform administrator" }),
          {
            status: 403,
            headers: { "Content-Type": "application/json" },
          }
        )
      )
    );

    await expect(bootstrapSession("non-admin.jwt")).rejects.toMatchObject({
      name: "CatalogApiError",
      status: 403,
      message: "Staff user is not an active platform administrator",
    });
  });

  it("maps 404 when catalog demo endpoint is unavailable or not found", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("Not Found", {
          status: 404,
          statusText: "Not Found",
        })
      )
    );

    await expect(fetchCatalogGraph("token-abc")).rejects.toMatchObject({
      name: "CatalogApiError",
      status: 404,
      message: "Catalog demo graph unavailable or endpoint not found",
    });
  });

  it("maps 503 audit persistence or infrastructure failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ detail: "Audit event persistence failed" }),
          {
            status: 503,
            headers: { "Content-Type": "application/json" },
          }
        )
      )
    );

    await expect(fetchCatalogGraph("token-abc")).rejects.toMatchObject({
      name: "CatalogApiError",
      status: 503,
    });
  });

  it("verifies and revokes session with bearer auth headers and handles 204 No Content", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user_id: "u-1",
            display_name: "Staff",
            authenticated_at: new Date().toISOString(),
            expires_at: new Date().toISOString(),
            capabilities: ["DRAFT_READ"],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }
        )
      )
      .mockResolvedValueOnce(
        new Response(null, {
          status: 204,
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const controller = new AbortController();
    const check = await verifySession("token-1", controller.signal);
    expect(check.user_id).toBe("u-1");

    await revokeSession("token-1", controller.signal);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [, initGet] = fetchMock.mock.calls[0];
    expect(initGet.headers["Authorization"]).toBe("Bearer token-1");
    expect(initGet.signal).toBe(controller.signal);

    const [, initDel] = fetchMock.mock.calls[1];
    expect(initDel.method).toBe("DELETE");
    expect(initDel.headers["Authorization"]).toBe("Bearer token-1");
    expect(initDel.signal).toBe(controller.signal);
  });

  it("fetches synthetic catalog graph with correct headers and DTO structure", async () => {
    const mockGraph: CatalogDemoGraphResponse = {
      demo_id: "catalog-demo-v1",
      synthetic: true,
      status: "Draft",
      source: {
        id: "src-1",
        source_key: "DEMO08-SOURCE",
        title: "Synthetic Conformly catalog demo",
        status: "Draft",
      },
      source_version: {
        id: "sv-1",
        source_id: "src-1",
        edition: "1.0.0",
        language: "en",
        official_locator: "https://demo.synthetic.conformly.invalid/sources/demo08-source-v1.pdf",
        publication_date: "2026-01-01",
        revision: 1,
        status: "Draft",
        content_digest: "digest123",
      },
      requirements: [],
      controls: [
        {
          id: "c-1",
          control_key: "CC-DEMO-001",
          domain: "DEMO",
          version_id: "cv-1",
          version_label: "1.0.0",
          revision: 1,
          title: "Privileged Access Review",
          objective: "Quarterly review of administrative accounts.",
          guidance: "Examine active admin list quarterly.",
          control_type: "preventive",
          frequency: "quarterly",
          automation_level: "manual",
          suggested_owner_role: "Security Officer",
          assurance_level: "substantial",
          tags_state: "None",
          status: "Draft",
          content_digest: "cdigest1",
        },
      ],
      mappings: [],
      evidence_requirements: [],
      assessment_procedures: [],
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockGraph), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const controller = new AbortController();
    const res = await fetchCatalogGraph("token-active-123", controller.signal);
    expect(res.demo_id).toBe("catalog-demo-v1");
    expect(res.synthetic).toBe(true);
    expect(res.source.source_key).toBe("DEMO08-SOURCE");
    expect(res.controls[0].control_key).toBe("CC-DEMO-001");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/v2/catalog-demo/catalog");
    expect(init.headers["Authorization"]).toBe("Bearer token-active-123");
    expect(init.signal).toBe(controller.signal);
  });
});
