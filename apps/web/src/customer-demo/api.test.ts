import { afterEach, describe, expect, it, vi } from "vitest";

import {
  adoptEvaluation,
  ConflictError,
  evaluateAnswers,
  fetchWorkspace,
  ForbiddenError,
  getApiBaseUrl,
  saveAnswers,
  ValidationError,
} from "./api";
import {
  AdoptionReceipt,
  AnswersData,
  EvaluationData,
  WorkspaceData,
} from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("customer demo API client", () => {
  it("getApiBaseUrl returns stripped base URL", () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000/");
    expect(getApiBaseUrl()).toBe("http://localhost:8000");
  });

  it("fetches workspace state via GET with Bearer token", async () => {
    const mockData: WorkspaceData = {
      tenant_id: "t-1",
      current_revision: 0,
      selection_revision: 0,
      manifest: {
        disclaimer: "Non-legal demonstration",
        evaluator_version: "wp09-synthetic-v1",
        companies: [],
        fact_definitions: [],
        packs: [],
      },
      answers: null,
      selected_pack: null,
      latest_evaluation: null,
      history_summary: [],
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const controller = new AbortController();
    const result = await fetchWorkspace("t-1", "token-123", controller.signal);

    expect(result.tenant_id).toBe("t-1");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/v2/tenants/t-1/customer-demo/workspace");
    expect(init.headers.Authorization).toBe("Bearer token-123");
  });

  it("saves answers via PUT and handles 409 ConflictError", async () => {
    const mockAnswers: AnswersData = {
      tenant_id: "t-1",
      revision: 1,
      company_code: "ALPHA",
      answers: { synthetic_wp09_uses_cloud: true },
      content_digest: "a".repeat(64),
      created_at: new Date().toISOString(),
    };

    // Positive save
    const fetchMockSuccess = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockAnswers), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMockSuccess);

    const saved = await saveAnswers("t-1", "token-123", {
      expected_revision: 0,
      company_code: "ALPHA",
      answers: {
        synthetic_wp09_uses_cloud: true,
        synthetic_wp09_operating_region: null,
      },
    });
    expect(saved.revision).toBe(1);

    // Conflict 409
    const fetchMockConflict = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Entity changed; reload and retry" }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMockConflict);

    await expect(
      saveAnswers("t-1", "token-123", {
        expected_revision: 0,
        company_code: "ALPHA",
        answers: {
          synthetic_wp09_uses_cloud: true,
          synthetic_wp09_operating_region: null,
        },
      })
    ).rejects.toThrow(ConflictError);
  });

  it("evaluates answers via POST and creates snapshot", async () => {
    const mockEval: EvaluationData = {
      id: "ev-1",
      tenant_id: "t-1",
      answer_revision: 1,
      pack_version_id: "p-1",
      bundle_digest: "b".repeat(64),
      evaluator_version: "wp09-synthetic-v1",
      content_digest: "c".repeat(64),
      results: [],
      created_at: new Date().toISOString(),
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockEval), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await evaluateAnswers("t-1", "token-123", {
      expected_revision: 1,
      pack_version_id: "p-1",
    });
    expect(res.id).toBe("ev-1");
  });

  it("adopts evaluation via POST and handles 422 ValidationError and 403 ForbiddenError", async () => {
    const mockReceipt: AdoptionReceipt = {
      id: "ad-1",
      tenant_id: "t-1",
      selection_revision: 1,
      evaluation_id: "ev-1",
      pack_version_id: "p-1",
      bundle_digest: "b".repeat(64),
      created_at: new Date().toISOString(),
      is_current: true,
      current_selection_revision: 1,
      current_pack_version_id: "p-1",
    };

    const fetchMockSuccess = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockReceipt), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMockSuccess);

    const res = await adoptEvaluation("t-1", "token-123", {
      expected_revision: 1,
      evaluation_id: "ev-1",
      pack_version_id: "p-1",
      acknowledge_synthetic: true,
      acknowledge_missing_information: true,
    });
    expect(res.selection_revision).toBe(1);

    // ValidationError on 422
    const fetchMockValidation = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Explicit acknowledgement required" }), {
        status: 422,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMockValidation);

    await expect(
      adoptEvaluation("t-1", "token-123", {
        expected_revision: 1,
        evaluation_id: "ev-1",
        pack_version_id: "p-1",
        acknowledge_synthetic: false,
        acknowledge_missing_information: false,
      })
    ).rejects.toThrow(ValidationError);

    // ForbiddenError on 403
    const fetchMockForbidden = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Customer demo access denied" }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMockForbidden);

    await expect(
      adoptEvaluation("t-1", "token-123", {
        expected_revision: 1,
        evaluation_id: "ev-1",
        pack_version_id: "p-1",
        acknowledge_synthetic: true,
        acknowledge_missing_information: true,
      })
    ).rejects.toThrow(ForbiddenError);
  });
});
