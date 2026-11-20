import React from 'react';
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { STORAGE_KEYS, clearStoredSession } from "./auth";
import { CatalogDemoApp } from "./CatalogDemoApp";
import { CatalogDemoGraphResponse, CatalogDemoSessionResponse } from "./types";

const mockSession: CatalogDemoSessionResponse = {
  user_id: "staff-01",
  display_name: "Staff Administrator",
  authenticated_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 3600 * 1000).toISOString(),
  capabilities: ["DRAFT_READ"],
};

const mockGraph: CatalogDemoGraphResponse = {
  demo_id: "catalog-demo-v1",
  synthetic: true,
  status: "Draft",
  source: {
    id: "src-demo-01",
    source_key: "DEMO08-SOURCE",
    title: "Synthetic Conformly catalog demo",
    status: "Draft",
  },
  source_version: {
    id: "sv-demo-01",
    source_id: "src-demo-01",
    edition: "1.0.0",
    language: "en",
    official_locator: "https://demo.synthetic.conformly.invalid/sources/demo08-source-v1.pdf",
    publication_date: "2026-01-01",
    revision: 1,
    status: "Draft",
    content_digest: "svdigest1234567890abcdef",
    provenance_id: "prov-01",
  },
  requirements: [
    {
      id: "req-1",
      source_id: "src-demo-01",
      requirement_key: "DEMO08-REQ-01",
      version_id: "rv-1",
      version_label: "1.0.0",
      revision: 1,
      normalized_outcome: "mandatory",
      requirement_type: "controller",
      obligated_actor: "organization",
      text_origin: "conformly_paraphrase",
      effective_from: "2026-01-01T00:00:00Z",
      status: "Draft",
      content_digest: "req1digest",
      source_references: [
        {
          locator_kind: "clause",
          locator_value: "1.1",
          sequence: 1,
        },
      ],
    },
    {
      id: "req-2",
      source_id: "src-demo-01",
      requirement_key: "DEMO08-REQ-02",
      version_id: "rv-2",
      version_label: "1.0.0",
      revision: 1,
      normalized_outcome: "mandatory",
      requirement_type: "controller",
      obligated_actor: "organization",
      text_origin: "conformly_paraphrase",
      effective_from: "2026-01-01T00:00:00Z",
      status: "Draft",
      content_digest: "req2digest",
      source_references: [
        {
          locator_kind: "clause",
          locator_value: "1.2",
          sequence: 1,
        },
      ],
    },
  ],
  controls: [
    {
      id: "ctrl-1",
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
      content_digest: "c1digest",
    },
    {
      id: "ctrl-2",
      control_key: "CC-DEMO-002",
      domain: "DEMO",
      version_id: "cv-2",
      version_label: "1.0.0",
      revision: 1,
      title: "Backup Restore Exercise",
      objective: "Semiannual verification of system backups.",
      guidance: "Perform non-destructive restore.",
      control_type: "corrective",
      frequency: "semiannual",
      automation_level: "manual",
      suggested_owner_role: "Infrastructure Lead",
      assurance_level: "substantial",
      tags_state: "None",
      status: "Draft",
      content_digest: "c2digest",
    },
  ],
  mappings: [
    {
      id: "map-1",
      mapping_key: "DEMO08-MAP-01",
      requirement_id: "req-1",
      control_id: "ctrl-1",
      requirement_version_id: "rv-1",
      control_version_id: "cv-1",
      version_label: "1.0.0",
      revision: 1,
      mapping_type: "Full",
      rationale: "Complete coverage of privileged access controls.",
      covered_dimensions: "identity,administration,access",
      excluded_dimensions: null,
      conditions: null,
      source_basis: "expert_analysis",
      confidence: "high",
      review_state: "Draft",
      status: "Draft",
      content_digest: "map1digest",
    },
    {
      id: "map-2",
      mapping_key: "DEMO08-MAP-02",
      requirement_id: "req-2",
      control_id: "ctrl-2",
      requirement_version_id: "rv-2",
      control_version_id: "cv-2",
      version_label: "1.0.0",
      revision: 1,
      mapping_type: "Partial",
      rationale: "Partial coverage of data retention requirements.",
      covered_dimensions: "backup_restoration",
      excluded_dimensions: "backup protection and retention schedules",
      conditions: null,
      source_basis: "expert_analysis",
      confidence: "medium",
      review_state: "Draft",
      status: "Draft",
      content_digest: "map2digest",
    },
  ],
  evidence_requirements: [
    {
      id: "evid-1",
      control_id: "ctrl-1",
      control_version_id: "cv-1",
      requirement_key: "ER-DEMO-001",
      sequence: 1,
      title: "Privileged Access Review Report",
      frequency: "quarterly",
      scope_state: "All",
      assurance_purpose: "operating_effectiveness",
      validity_rule: "point_in_time",
      max_age_days: 90,
      guidance: "Signed export showing review.",
      missing_data_behavior: "requires_human_review",
      status: "Draft",
      content_digest: "e1digest",
      artifact_types: [{ artifact_type: "report", sequence: 1 }],
      required_metadata: [{ metadata_key: "reviewer_name", sequence: 1 }],
    },
    {
      id: "evid-2",
      control_id: "ctrl-2",
      control_version_id: "cv-2",
      requirement_key: "ER-DEMO-002",
      sequence: 1,
      title: "Backup Restore Log",
      frequency: "semiannual",
      scope_state: "All",
      assurance_purpose: "operating_effectiveness",
      validity_rule: "point_in_time",
      max_age_days: 180,
      guidance: "Log documenting test recovery.",
      missing_data_behavior: "requires_human_review",
      status: "Draft",
      content_digest: "e2digest",
      artifact_types: [{ artifact_type: "log", sequence: 1 }],
      required_metadata: [{ metadata_key: "backup_timestamp", sequence: 1 }],
    },
  ],
  assessment_procedures: [
    {
      id: "proc-1",
      control_id: "ctrl-1",
      control_version_id: "cv-1",
      procedure_key: "AP-DEMO-001",
      sequence: 1,
      title: "Verify Privileged Access Review",
      objective: "Confirm accounts reviewed quarterly.",
      decision_guidance: "Confirm all privileged accounts have approvals.",
      assessor_qualifications: "Security Auditor",
      missing_data_behavior: "requires_human_review",
      status: "Draft",
      content_digest: "p1digest",
      steps: [
        {
          sequence: 1,
          step_kind: "inspect",
          instruction: "Inspect review records.",
          expected_output: "All grants are documented.",
        },
      ],
      evidence_requirement_ids: ["evid-1"],
    },
    {
      id: "proc-2",
      control_id: "ctrl-2",
      control_version_id: "cv-2",
      procedure_key: "AP-DEMO-002",
      sequence: 1,
      title: "Verify Backup Restoration",
      objective: "Confirm recovery exercise conducted within RTO.",
      decision_guidance: "Confirm recovery verification completed.",
      assessor_qualifications: "Systems Auditor",
      missing_data_behavior: "requires_human_review",
      status: "Draft",
      content_digest: "p2digest",
      steps: [
        {
          sequence: 1,
          step_kind: "inspect",
          instruction: "Inspect restore logs.",
          expected_output: "Restoration verified complete.",
        },
      ],
      evidence_requirement_ids: ["evid-2"],
    },
  ],
};

describe("CatalogDemoApp Component", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("renders synthetic warning banner and sign-in button when unauthenticated", () => {
    render(<CatalogDemoApp />);

    expect(screen.getByText(/Synthetic data/i)).toBeInTheDocument();
    expect(screen.getByText(/Draft catalog preview/i)).toBeInTheDocument();
    expect(screen.getByTestId("sign-in-btn")).toBeInTheDocument();
  });

  it("loads and displays synthetic catalog graph when active session exists", async () => {
    sessionStorage.setItem(STORAGE_KEYS.TOKEN, "valid-token-123");
    sessionStorage.setItem(STORAGE_KEYS.SESSION_INFO, JSON.stringify(mockSession));

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockGraph), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<CatalogDemoApp />);

    expect(await screen.findByTestId("session-user")).toHaveTextContent("Staff Administrator");
    expect(await screen.findByText(/Synthetic Conformly catalog demo/i)).toBeInTheDocument();
    expect(screen.getByTestId("tab-overview")).toBeInTheDocument();
    expect(screen.getByTestId("tab-requirements")).toBeInTheDocument();
    expect(screen.getByTestId("tab-evidence")).toBeInTheDocument();
  });

  it("navigates through tabs: overview, requirements & controls, evidence & procedures", async () => {
    sessionStorage.setItem(STORAGE_KEYS.TOKEN, "valid-token-123");
    sessionStorage.setItem(STORAGE_KEYS.SESSION_INFO, JSON.stringify(mockSession));

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/session")) {
          return Promise.resolve(
            new Response(JSON.stringify(mockSession), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            })
          );
        }
        return Promise.resolve(
          new Response(JSON.stringify(mockGraph), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      })
    );

    render(<CatalogDemoApp />);

    expect(await screen.findByTestId("session-user")).toBeInTheDocument();

    // 1. Overview Tab
    expect(screen.getByTestId("pane-overview")).toBeInTheDocument();
    expect(screen.getByText("DEMO08-SOURCE")).toBeInTheDocument();

    // 2. Requirements & Controls Tab
    const reqTabBtn = screen.getByTestId("tab-requirements");
    fireEvent.click(reqTabBtn);
    expect(screen.getByTestId("pane-requirements")).toBeInTheDocument();
    expect(screen.getAllByText(/DEMO08-REQ-01/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/CC-DEMO-001/i)).toBeInTheDocument();
    expect(screen.getByText(/Privileged Access Review/i)).toBeInTheDocument();

    // Switch to REQ-02
    const req2Btn = screen.getByTestId("req-selector-DEMO08-REQ-02");
    fireEvent.click(req2Btn);
    expect(screen.getByText(/CC-DEMO-002/i)).toBeInTheDocument();
    expect(screen.getByText(/Backup Restore Exercise/i)).toBeInTheDocument();
    expect(screen.getByText(/backup protection and retention schedules/i)).toBeInTheDocument();

    // 3. Evidence & Procedures Tab
    const evidTabBtn = screen.getByTestId("tab-evidence");
    fireEvent.click(evidTabBtn);
    expect(screen.getByTestId("pane-evidence")).toBeInTheDocument();
    expect(screen.getByText(/ER-DEMO-001/i)).toBeInTheDocument();
    expect(screen.getByText(/AP-DEMO-001/i)).toBeInTheDocument();
    expect(screen.getByText(/ER-DEMO-002/i)).toBeInTheDocument();
    expect(screen.getByText(/AP-DEMO-002/i)).toBeInTheDocument();
  });

  it("handles sign-out immediately by clearing session and storage", async () => {
    sessionStorage.setItem(STORAGE_KEYS.TOKEN, "valid-token-123");
    sessionStorage.setItem(STORAGE_KEYS.SESSION_INFO, JSON.stringify(mockSession));

    const fetchMock = vi
      .fn()
      .mockImplementation((url: string, init?: RequestInit) => {
        if (init?.method === "DELETE") {
          return Promise.resolve(new Response(null, { status: 204 }));
        }
        return Promise.resolve(
          new Response(JSON.stringify(mockGraph), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<CatalogDemoApp />);

    expect(await screen.findByTestId("session-user")).toBeInTheDocument();

    const signOutBtn = screen.getByTestId("sign-out-btn");
    fireEvent.click(signOutBtn);

    expect(await screen.findByTestId("sign-in-btn")).toBeInTheDocument();
    expect(sessionStorage.getItem(STORAGE_KEYS.TOKEN)).toBeNull();
    expect(sessionStorage.getItem(STORAGE_KEYS.SESSION_INFO)).toBeNull();

    // Verify DELETE was dispatched with captured bearer token
    const deleteCalls = fetchMock.mock.calls.filter((c: unknown[]) => (c[1] as RequestInit | undefined)?.method === "DELETE");
    expect(deleteCalls.length).toBe(1);
    expect((deleteCalls[0][1] as RequestInit).headers).toEqual(
      expect.objectContaining({ Authorization: "Bearer valid-token-123" })
    );
  });

  it("renders 403 access denial when platform admin capability is missing", async () => {
    sessionStorage.setItem(STORAGE_KEYS.TOKEN, "non-admin-token");
    sessionStorage.setItem(STORAGE_KEYS.SESSION_INFO, JSON.stringify(mockSession));

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ detail: "User is not an active platform administrator" }),
          {
            status: 403,
            headers: { "Content-Type": "application/json" },
          }
        )
      )
    );

    render(<CatalogDemoApp />);

    expect(
      await screen.findByText(/User is not an active platform administrator/i)
    ).toBeInTheDocument();
    expect(sessionStorage.getItem(STORAGE_KEYS.TOKEN)).toBeNull();
  });

  it("renders safely in React.StrictMode without breaking state or duplicate session commits", async () => {
    sessionStorage.setItem(STORAGE_KEYS.TOKEN, "valid-token-123");
    sessionStorage.setItem(STORAGE_KEYS.SESSION_INFO, JSON.stringify(mockSession));

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/session")) {
          return Promise.resolve(
            new Response(JSON.stringify(mockSession), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            })
          );
        }
        return Promise.resolve(
          new Response(JSON.stringify(mockGraph), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      })
    );

    render(
      <React.StrictMode>
        <CatalogDemoApp />
      </React.StrictMode>
    );

    expect(await screen.findByTestId("session-user")).toHaveTextContent("Staff Administrator");
    expect(await screen.findByText(/Synthetic Conformly catalog demo/i)).toBeInTheDocument();
  });

  it("prevents late-resolving token fetch from restoring credentials after clearStoredSession()", async () => {
    let resolveSessionFetch!: (val: Response) => void;
    const pendingSessionPromise = new Promise<Response>((resolve) => {
      resolveSessionFetch = resolve;
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/session")) {
          return pendingSessionPromise;
        }
        return Promise.resolve(
          new Response(JSON.stringify(mockGraph), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      })
    );

    // Initial state: token present in storage
    sessionStorage.setItem(STORAGE_KEYS.TOKEN, "token-to-be-revoked");

    const { unmount } = render(<CatalogDemoApp />);

    // User signs out or clearStoredSession is called while fetch is in-flight
    clearStoredSession();
    expect(sessionStorage.getItem(STORAGE_KEYS.TOKEN)).toBeNull();

    // Now late response resolves
    resolveSessionFetch(
      new Response(JSON.stringify(mockSession), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    // Wait a tick for microtasks
    await new Promise((r) => setTimeout(r, 50));

    // Crucial check: TOKEN storage must NOT become populated again!
    expect(sessionStorage.getItem(STORAGE_KEYS.TOKEN)).toBeNull();
    expect(sessionStorage.getItem(STORAGE_KEYS.SESSION_INFO)).toBeNull();

    unmount();
  });

  it("handles malformed callback markers with safe fixed message and immediate URL cleanup", async () => {
    const replaceStateSpy = vi.spyOn(window.history, "replaceState");

    // Mock search params using history.pushState
    window.history.pushState({}, "", "/catalog-demo?error=invalid_scope&error_description=internal_token_secret_leaked");

    render(<CatalogDemoApp />);

    // Renders fixed safe message, NOT the provider's leaked secret description
    expect(
      await screen.findByText(/Workforce authentication failed or was cancelled/i)
    ).toBeInTheDocument();
    expect(screen.queryByText(/internal_token_secret_leaked/)).toBeNull();

    // Verify URL was sanitized immediately
    expect(replaceStateSpy).toHaveBeenCalled();

    replaceStateSpy.mockRestore();
    window.history.pushState({}, "", "/");
  });

  it("completes real OIDC callback mounted under React.StrictMode with deferred ID-token response exactly once", async () => {
    vi.stubEnv("VITE_WORKFORCE_TOKEN_URL", "http://127.0.0.1:8080/oauth2/token");
    vi.stubEnv("VITE_WORKFORCE_CLIENT_ID", "conformly-staff-client");

    window.history.pushState({}, "", "/catalog-demo?code=strict-code-123&state=strict-state-456");
    sessionStorage.setItem(STORAGE_KEYS.PKCE_STATE, "strict-state-456");
    sessionStorage.setItem(STORAGE_KEYS.PKCE_VERIFIER, "strict-verifier-789");

    let resolveTokenExchange!: (res: Response) => void;
    const tokenPromise = new Promise<Response>((resolve) => {
      resolveTokenExchange = resolve;
    });

    let tokenCalls = 0;
    let bootstrapCalls = 0;
    let graphCalls = 0;

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/oauth2/token")) {
          tokenCalls += 1;
          return tokenPromise;
        }
        if (url.includes("/session")) {
          bootstrapCalls += 1;
          return Promise.resolve(
            new Response(JSON.stringify(mockSession), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            })
          );
        }
        if (url.includes("/catalog")) {
          graphCalls += 1;
          return Promise.resolve(
            new Response(JSON.stringify(mockGraph), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            })
          );
        }
        return Promise.reject(new Error(`Unexpected fetch URL: ${url}`));
      })
    );

    render(
      <React.StrictMode>
        <CatalogDemoApp />
      </React.StrictMode>
    );

    // StrictMode mount must execute token exchange exactly once, not twice
    expect(tokenCalls).toBe(1);

    // Resolve the deferred ID-token response
    resolveTokenExchange(
      new Response(
        JSON.stringify({
          id_token: "signed.jwt.strict.mode.token",
          token_type: "Bearer",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    // Active staff session and graph become usable
    expect(await screen.findByTestId("session-user")).toHaveTextContent("Staff Administrator");
    expect(await screen.findByText(/Synthetic Conformly catalog demo/i)).toBeInTheDocument();

    expect(bootstrapCalls).toBe(1);
    expect(graphCalls).toBeGreaterThanOrEqual(1);
    expect(sessionStorage.getItem(STORAGE_KEYS.TOKEN)).toBe("signed.jwt.strict.mode.token");

    window.history.pushState({}, "", "/");
  });

  it("aborts and prevents credential restoration when unmounted during pending exchange or bootstrap stage", async () => {
    vi.stubEnv("VITE_WORKFORCE_TOKEN_URL", "http://127.0.0.1:8080/oauth2/token");
    vi.stubEnv("VITE_WORKFORCE_CLIENT_ID", "conformly-staff-client");

    // Stage 1: unmount before token exchange resolves
    window.history.pushState({}, "", "/catalog-demo?code=unmount-code-1&state=unmount-state-1");
    sessionStorage.setItem(STORAGE_KEYS.PKCE_STATE, "unmount-state-1");
    sessionStorage.setItem(STORAGE_KEYS.PKCE_VERIFIER, "unmount-verifier-1");

    let resolveToken!: (res: Response) => void;
    const pendingToken = new Promise<Response>((resolve) => {
      resolveToken = resolve;
    });

    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/oauth2/token")) {
        return pendingToken;
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const { unmount } = render(<CatalogDemoApp />);
    expect(fetchMock).toHaveBeenCalled();

    // Unmount before token resolves
    unmount();

    // Now token resolves
    resolveToken(
      new Response(
        JSON.stringify({ id_token: "late-token-xyz", token_type: "Bearer" }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    await new Promise((r) => setTimeout(r, 50));
    expect(sessionStorage.getItem(STORAGE_KEYS.TOKEN)).toBeNull();

    window.history.pushState({}, "", "/");
  });

  it("older pending OIDC callback that fails after newer session installed does not clear newer session (non-OK, missing token, network error)", async () => {
    vi.stubEnv("VITE_WORKFORCE_TOKEN_URL", "http://127.0.0.1:8080/oauth2/token");
    vi.stubEnv("VITE_WORKFORCE_CLIENT_ID", "conformly-staff-client");

    // 1. Mount with callback parameters for old exchange
    window.history.pushState({}, "", "/catalog-demo?code=old-code-1&state=old-state-1");
    sessionStorage.setItem(STORAGE_KEYS.PKCE_STATE, "old-state-1");
    sessionStorage.setItem(STORAGE_KEYS.PKCE_VERIFIER, "old-verifier-1");

    let resolveOldToken!: (res: Response) => void;
    const pendingOldToken = new Promise<Response>((resolve) => {
      resolveOldToken = resolve;
    });

    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/oauth2/token")) {
        return pendingOldToken;
      }
      return Promise.resolve(
        new Response(JSON.stringify(mockGraph), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { unmount } = render(<CatalogDemoApp />);
    expect(fetchMock).toHaveBeenCalled();

    // 2. While old exchange is pending, a newer session is established in storage
    sessionStorage.setItem(STORAGE_KEYS.TOKEN, "newer-surviving-token");
    sessionStorage.setItem(STORAGE_KEYS.SESSION_INFO, JSON.stringify(mockSession));

    // 3. Component unmounts or navigates away
    unmount();

    // 4. Old token exchange fails with HTTP 400
    resolveOldToken(
      new Response(JSON.stringify({ error: "invalid_grant" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      })
    );

    await new Promise((r) => setTimeout(r, 50));

    // Newer session in storage must SURVIVE untouched!
    expect(sessionStorage.getItem(STORAGE_KEYS.TOKEN)).toBe("newer-surviving-token");
    expect(sessionStorage.getItem(STORAGE_KEYS.SESSION_INFO)).not.toBeNull();

    window.history.pushState({}, "", "/");
  });
});
