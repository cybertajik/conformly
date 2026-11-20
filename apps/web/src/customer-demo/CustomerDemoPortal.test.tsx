import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { I18nProvider } from "../i18n/I18nContext";
import { CustomerDemoPortal } from "./CustomerDemoPortal";
import * as api from "./api";
import * as controlApi from "./control-evidence-api";
import * as assessmentApi from "./assessment-api";
import type { WorkspaceData, EvaluationData, AdoptionReceipt } from "./types";
import type { ControlEvidenceLink, ControlWorkItem, OwnerDirectoryResponse } from "./control-evidence-types";
import type { AssessmentWorkItem, Procedure, ReadinessSummary } from "./assessment-types";

const mockWorkspace: WorkspaceData = {
  tenant_id: "11111111-1111-1111-1111-111111111111",
  current_revision: 1,
  selection_revision: 0,
  manifest: {
    disclaimer: "Synthetic customer onboarding demonstration. Not legal or compliance advice.",
    evaluator_version: "wp09-synthetic-v1",
    companies: [
      { code: "ALPHA", display_name: "Fictional Alpha (Cloud-First)" },
      { code: "BETA", display_name: "Fictional Beta (Hybrid/Regional)" },
    ],
    fact_definitions: [
      {
        id: "fact-cloud-def",
        version_id: "e0000000-0000-0000-0000-000000000001",
        key: "synthetic_wp09_uses_cloud",
        label: "Uses Cloud Infrastructure",
        description: "Whether the workload runs in cloud environments",
        value_type: "boolean",
      },
      {
        id: "fact-region-def",
        version_id: "e0000000-0000-0000-0000-000000000002",
        key: "synthetic_wp09_operating_region",
        label: "Primary Operating Region",
        description: "Primary geographic region of operation",
        value_type: "enum",
        enum_options: [
          { code: "EU", label: "European Union" },
          { code: "OTHER", label: "Other Global Regions" },
        ],
      },
    ],
    packs: [
      {
        pack_id: "pack-v1",
        pack_version_id: "pack-v1-id",
        version: "1.0.0",
        name: "Synthetic Customer Baseline Pack",
        description: "Initial synthetic baseline pack",
        bundle_digest: "65d0f766" + "0".repeat(56),
        requirement_count: 2,
        requirements: [
          {
            id: "req-1",
            version_id: "req-1-v1",
            identifier: "SYNTH-REQ-001",
            title: "Synthetic Cloud Architecture Governance",
            description: "Cloud baseline requirement",
            rule_id: "rule-1",
            rule_version_id: "rule-1-v1",
            control_id: "ctrl-1",
            control_version_id: "ctrl-1-v1",
            control_identifier: "SYNTH-CTRL-001",
            control_title: "Cloud Configuration & Access Baseline",
          },
          {
            id: "req-2",
            version_id: "req-2-v1",
            identifier: "SYNTH-REQ-002",
            title: "Synthetic EU Regional Data Isolation",
            description: "EU isolation requirement",
            rule_id: "rule-2",
            rule_version_id: "rule-2-v1",
            control_id: "ctrl-2",
            control_version_id: "ctrl-2-v1",
            control_identifier: "SYNTH-CTRL-002",
            control_title: "Sovereign Boundary Encryption & Residency",
          },
        ],
      },
    ],
  },
  answers: {
    tenant_id: "11111111-1111-1111-1111-111111111111",
    revision: 1,
    company_code: "ALPHA",
    answers: {
      synthetic_wp09_uses_cloud: true,
      synthetic_wp09_operating_region: "EU",
    },
    content_digest: "digest-1",
    created_at: "2026-10-22T08:00:00Z",
  },
  selected_pack: null,
  latest_evaluation: null,
  history_summary: [],
};

describe("CustomerDemoPortal", () => {
  beforeEach(() => {
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(JSON.parse(JSON.stringify(mockWorkspace)));
    window.location.hash = "";
  });

  afterEach(() => {
    vi.restoreAllMocks();
    cleanup();
    if (typeof window !== "undefined") {
      try {
        window.history.replaceState(null, "", window.location.pathname);
      } catch {
        // ignore
      }
      window.location.hash = "";
    }
  });

  const defaultTenants = [
    { tenant_id: "11111111-1111-1111-1111-111111111111", tenant_name: "Acme Corp", role: "owner" as const, tenant_slug: "acme" },
    { tenant_id: "22222222-2222-2222-2222-222222222222", tenant_name: "Beta Ltd", role: "owner" as const, tenant_slug: "beta" },
  ];

  it("renders the Apple-inspired application shell with branding and user details", async () => {
    render(
      <I18nProvider>
        <CustomerDemoPortal
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          tenantName="Acme Corp"
          userRole="compliance_manager"
          tenants={defaultTenants}
        />
      </I18nProvider>
    );

    expect(screen.getByTestId("conformly-portal-shell")).toBeInTheDocument();
    expect(screen.getByTestId("portal-sidebar")).toBeInTheDocument();
    expect(screen.getByText("Conformly Portal")).toBeInTheDocument();
    expect(screen.getByTestId("topbar-tenant-badge")).toHaveTextContent("Acme Corp");
    expect(screen.getByTestId("topbar-role-badge")).toHaveTextContent("compliance manager");

    // Wait for workspace load
    await waitFor(() => expect(api.fetchWorkspace).toHaveBeenCalledTimes(1));
  });

  it("defaults to the Overview view as the landing screen with truthful metrics", async () => {
    render(
      <I18nProvider>
        <CustomerDemoPortal
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          tenantName="Acme Corp"
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => expect(screen.getByTestId("portal-overview-view")).toBeInTheDocument());
    expect(screen.getByTestId("portal-page-title")).toHaveTextContent("Overview");
    expect(screen.getByTestId("breadcrumb-active-view")).toHaveTextContent("Overview");

    // Truthful metric cards
    expect(screen.getByTestId("metric-framework-card")).toBeInTheDocument();
    expect(screen.getByTestId("metric-controls-card")).toBeInTheDocument();
    expect(screen.getByTestId("metric-evidence-card")).toBeInTheDocument();
    expect(screen.getByTestId("metric-assessments-card")).toBeInTheDocument();

    // Recommended Next Action banner
    expect(screen.getByTestId("portal-next-action-banner")).toBeInTheDocument();
    expect(screen.getByTestId("next-action-btn")).toBeInTheDocument();
  });

  it("navigates cleanly between dedicated views via the sidebar navigation", async () => {
    render(
      <I18nProvider>
        <CustomerDemoPortal
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          tenantName="Acme Corp"
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => expect(screen.getByTestId("portal-overview-view")).toBeInTheDocument());

    // Navigate to Company Setup
    fireEvent.click(screen.getByTestId("nav-view-company_setup"));
    expect(screen.getByTestId("portal-setup-view")).toBeInTheDocument();
    expect(screen.getByTestId("portal-page-title")).toHaveTextContent("Company Setup");
    expect(screen.getByTestId("profile-section")).toBeInTheDocument();

    // Navigate to Available Frameworks
    fireEvent.click(screen.getByTestId("nav-view-frameworks"));
    expect(screen.getByTestId("portal-frameworks-view")).toBeInTheDocument();
    expect(screen.getByTestId("portal-page-title")).toHaveTextContent("Available Frameworks");
    expect(screen.getByTestId("eval-section")).toBeInTheDocument();

    // Navigate to Controls & Evidence
    fireEvent.click(screen.getByTestId("nav-view-controls_evidence"));
    expect(screen.getByTestId("portal-controls-view")).toBeInTheDocument();
    expect(screen.getByTestId("portal-page-title")).toHaveTextContent("Controls & Evidence");

    // Navigate to Assessments & Findings
    fireEvent.click(screen.getByTestId("nav-view-assessments_findings"));
    expect(screen.getByTestId("portal-assessments-view")).toBeInTheDocument();
    expect(screen.getByTestId("portal-page-title")).toHaveTextContent("Assessments & Findings");

    // Navigate back to Overview
    fireEvent.click(screen.getByTestId("nav-view-overview"));
    expect(screen.getByTestId("portal-overview-view")).toBeInTheDocument();
  });

  it("preserves unsaved answers in Company Setup across view changes without data loss", async () => {
    render(
      <I18nProvider>
        <CustomerDemoPortal
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          tenantName="Acme Corp"
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => expect(screen.getByTestId("portal-overview-view")).toBeInTheDocument());

    // Go to Company Setup
    fireEvent.click(screen.getByTestId("nav-view-company_setup"));
    expect(screen.getByTestId("portal-setup-view")).toBeInTheDocument();

    // Change cloud usage to 'no'
    const cloudNoRadio = screen.getByTestId("cloud-no") as HTMLInputElement;
    fireEvent.click(cloudNoRadio);
    expect(cloudNoRadio.checked).toBe(true);

    // Unsaved changes banner appears
    expect(screen.getByTestId("unsaved-changes-banner")).toBeInTheDocument();

    // Navigate to Frameworks view
    fireEvent.click(screen.getByTestId("nav-view-frameworks"));
    expect(screen.getByTestId("portal-frameworks-view")).toBeInTheDocument();
    expect(screen.getByTestId("unsaved-changes-banner")).toBeInTheDocument();

    // Navigate back to Company Setup
    fireEvent.click(screen.getByTestId("nav-view-company_setup"));
    expect(screen.getByTestId("portal-setup-view")).toBeInTheDocument();

    // Verify unsaved selection is intact
    const restoredCloudNo = screen.getByTestId("cloud-no") as HTMLInputElement;
    expect(restoredCloudNo.checked).toBe(true);
  });

  it("handles inline validation in Company Setup when inputs require attention", async () => {
    render(
      <I18nProvider>
        <CustomerDemoPortal
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          tenantName="Acme Corp"
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => expect(screen.getByTestId("portal-overview-view")).toBeInTheDocument());

    // Go to Company Setup
    fireEvent.click(screen.getByTestId("nav-view-company_setup"));
    expect(screen.getByTestId("portal-setup-view")).toBeInTheDocument();

    // Select unknown for cloud and region
    fireEvent.click(screen.getByTestId("cloud-unknown"));
    fireEvent.click(screen.getByTestId("region-unknown"));

    // Click validate button
    fireEvent.click(screen.getByTestId("validate-setup-btn"));

    // Inline errors appear with accessible alerts
    expect(screen.getByTestId("cloud-usage-error")).toBeInTheDocument();
    expect(screen.getByTestId("operating-region-error")).toBeInTheDocument();
  });

  it("triggers tenant switch callback when selecting another organization", async () => {
    const selectTenantSpy = vi.fn();
    render(
      <I18nProvider>
        <CustomerDemoPortal
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          tenantName="Acme Corp"
          userRole="owner"
          tenants={defaultTenants}
          onSelectTenant={selectTenantSpy}
        />
      </I18nProvider>
    );

    await waitFor(() => expect(screen.getByTestId("portal-overview-view")).toBeInTheDocument());

    const tenantSelect = screen.getByTestId("portal-tenant-select");
    fireEvent.change(tenantSelect, { target: { value: "22222222-2222-2222-2222-222222222222" } });

    expect(selectTenantSpy).toHaveBeenCalledWith("22222222-2222-2222-2222-222222222222");
  });

  it("supports responsive mobile drawer menu toggle and keyboard dismiss", async () => {
    render(
      <I18nProvider>
        <CustomerDemoPortal
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          tenantName="Acme Corp"
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => expect(screen.getByTestId("portal-overview-view")).toBeInTheDocument());

    const sidebar = screen.getByTestId("portal-sidebar");
    expect(sidebar).not.toHaveClass("open");

    // Toggle menu button
    const toggleBtn = screen.getByTestId("portal-mobile-menu-toggle");
    fireEvent.click(toggleBtn);
    expect(sidebar).toHaveClass("open");

    // Dismiss with Escape key
    fireEvent.keyDown(window, { key: "Escape" });
    expect(sidebar).not.toHaveClass("open");
  });

  it("handles sign out and session expiry callbacks correctly", async () => {
    const signOutSpy = vi.fn();
    const sessionExpiredSpy = vi.fn();

    vi.spyOn(api, "fetchWorkspace").mockRejectedValue(new api.UnauthorizedError("Token expired"));

    render(
      <I18nProvider>
        <CustomerDemoPortal
          tenantId="11111111-1111-1111-1111-111111111111"
          token="expired-token"
          tenantName="Acme Corp"
          userRole="owner"
          onSignOut={signOutSpy}
          onSessionExpired={sessionExpiredSpy}
        />
      </I18nProvider>
    );

    // Click sign out
    const signOutBtn = screen.getByTestId("portal-signout-btn");
    fireEvent.click(signOutBtn);
    expect(signOutSpy).toHaveBeenCalledTimes(1);

    // Session expired callback on 401
    await waitFor(() => expect(sessionExpiredSpy).toHaveBeenCalledTimes(1));
  });

  it("supports hash-based deep linking without touching search parameters", async () => {
    window.location.hash = "#frameworks";

    render(
      <I18nProvider>
        <CustomerDemoPortal
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          tenantName="Acme Corp"
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => expect(screen.getByTestId("portal-frameworks-view")).toBeInTheDocument());
    expect(screen.getByTestId("portal-page-title")).toHaveTextContent("Available Frameworks");
  });
  it("enforces mobile drawer accessibility attributes, focus trap, and Escape focus restoration", async () => {
    render(
      <I18nProvider>
        <CustomerDemoPortal
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          tenantName="Acme Corp"
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => expect(screen.getByTestId("portal-overview-view")).toBeInTheDocument());

    const toggleBtn = screen.getByTestId("portal-mobile-menu-toggle");
    const sidebar = screen.getByTestId("portal-sidebar");

    expect(toggleBtn).toHaveAttribute("aria-expanded", "false");
    expect(toggleBtn).toHaveAttribute("aria-controls", "portal-sidebar-nav");
    expect(sidebar).toHaveAttribute("id", "portal-sidebar-nav");
    expect(sidebar).toHaveAttribute("aria-label", "Portal Navigation");

    // Open drawer
    toggleBtn.focus();
    fireEvent.click(toggleBtn);
    expect(toggleBtn).toHaveAttribute("aria-expanded", "true");
    expect(sidebar).toHaveClass("open");

    // Test Escape key closes drawer and returns focus to toggle button
    fireEvent.keyDown(window, { key: "Escape" });
    expect(sidebar).not.toHaveClass("open");
    expect(toggleBtn).toHaveAttribute("aria-expanded", "false");
    expect(document.activeElement).toBe(toggleBtn);
  });

  it("renders non-English (German) navigation labels, skip link, and view titles cleanly", async () => {
    localStorage.setItem("conformly.locale", "de");
    render(
      <I18nProvider>
        <CustomerDemoPortal
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          tenantName="Acme Corp"
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => expect(screen.getByTestId("portal-overview-view")).toBeInTheDocument());

    // Skip link in German
    const skipLink = screen.getByText("Zum Hauptinhalt springen");
    expect(skipLink).toBeInTheDocument();

    // Nav items in German
    expect(screen.getByTestId("nav-view-overview")).toHaveTextContent("Übersicht");
    expect(screen.getByTestId("nav-view-company_setup")).toHaveTextContent("Unternehmenseinrichtung");
    expect(screen.getByTestId("nav-view-frameworks")).toHaveTextContent("Verfügbare Rahmenwerke");
    expect(screen.getByTestId("nav-view-controls_evidence")).toHaveTextContent("Kontrollen & Nachweise");
    expect(screen.getByTestId("nav-view-assessments_findings")).toHaveTextContent("Bewertungen & Feststellungen");
    localStorage.removeItem("conformly.locale");
  });

  it("journey: stateful real-component journey: setup -> adoption -> control initialization -> owner assignment -> evidence/review -> assessment -> finding/remediation/retest -> overview", async () => {
    let currentWorkspaceState: WorkspaceData = JSON.parse(JSON.stringify(mockWorkspace));

    vi.spyOn(api, "fetchWorkspace").mockImplementation(async () => {
      return JSON.parse(JSON.stringify(currentWorkspaceState));
    });

    // 1. Setup view: change answers and save
    const saveSpy = vi.spyOn(api, "saveAnswers").mockImplementation(async (_tenant, _token, input) => {
      const compCode = currentWorkspaceState.answers?.company_code || "ALPHA";
      currentWorkspaceState = {
        ...currentWorkspaceState,
        current_revision: currentWorkspaceState.current_revision + 1,
        answers: {
          tenant_id: currentWorkspaceState.tenant_id,
          revision: currentWorkspaceState.current_revision + 1,
          company_code: compCode,
          answers: input.answers as Record<string, boolean | string | null>,
          content_digest: "digest-rev-2",
          created_at: new Date().toISOString(),
        },
      };
      return {
        tenant_id: currentWorkspaceState.tenant_id,
        revision: currentWorkspaceState.current_revision,
        company_code: compCode,
        answers: input.answers,
        content_digest: "digest-rev-2",
        created_at: new Date().toISOString(),
      };
    });

    // 2. Frameworks view: evaluate and adopt pack
    const evalSpy = vi.spyOn(api, "evaluateAnswers").mockImplementation(async () => {
      const evalRes: EvaluationData = {
        id: "eval-journey-1",
        tenant_id: currentWorkspaceState.tenant_id,
        bundle_digest: "digest-pack-v1",
        evaluator_version: "wp09-synthetic-v1",
        content_digest: "digest-eval",
        created_at: new Date().toISOString(),
        answer_revision: currentWorkspaceState.current_revision,
        pack_version_id: "pack-v1-id",
        results: [
          {
            requirement_id: "req-1",
            requirement_version_id: "req-1-v1",
            identifier: "SYNTH-REQ-001",
            title: "Cloud Architecture Baseline",
            rule_id: "rule-1",
            rule_version_id: "rule-1-v1",
            result: "APPLICABLE",
            missing_fact_version_ids: [],
            explanation_tree: {
              op: "AND",
              path: "synthetic_wp09_uses_cloud",
              result: "APPLICABLE",
              message: "Cloud Baseline Rule passed",
              missing_fact_version_ids: [],
              children: [],
            },
          },
        ],
      };
      currentWorkspaceState = {
        ...currentWorkspaceState,
        latest_evaluation: evalRes,
      };
      return evalRes;
    });

    const adoptSpy = vi.spyOn(api, "adoptEvaluation").mockImplementation(async () => {
      const adoptReceipt = {
        id: "rcpt-journey-1",
        tenant_id: currentWorkspaceState.tenant_id,
        adoption_id: "adopt-journey-1",
        pack_id: "pack-v1",
        pack_version_id: "pack-v1-id",
        evaluation_id: "eval-journey-1",
        selection_revision: 1,
        answer_revision: currentWorkspaceState.current_revision,
        bundle_digest: "digest-pack-v1",
        adopted_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
        receipt_digest: "adopt-digest-1234",
      };
      currentWorkspaceState = {
        ...currentWorkspaceState,
        selection_revision: 1,
        selected_pack: {
          selection_revision: 1,
          evaluation_id: "eval-journey-1",
          pack_version_id: "pack-v1-id",
          bundle_digest: "digest-pack-v1",
          created_at: new Date().toISOString(),
          is_stale: false,
        },
      };
      return adoptReceipt as unknown as AdoptionReceipt;
    });

    // 3. Control items & owner directory
    const dummyOwners: OwnerDirectoryResponse = {
      items: [
        { user_id: "u-owner", display_name: "Alice Owner" },
        { user_id: "u-mgr", display_name: "Bob Manager" },
      ],
      total: 2,
    };
    vi.spyOn(controlApi, "fetchOwnerDirectory").mockResolvedValue(dummyOwners);

    let controlWorkItems: ControlWorkItem[] = [];
    vi.spyOn(controlApi, "fetchControlWorkList").mockImplementation(async () => ({
      tenant_id: currentWorkspaceState.tenant_id,
      adoption_id: "adopt-journey-1",
      selection_revision: currentWorkspaceState.selection_revision,
      answer_revision: currentWorkspaceState.current_revision,
      is_current: true,
      is_stale: false,
      items: JSON.parse(JSON.stringify(controlWorkItems)),
      total: controlWorkItems.length,
    }));

    const dummyControlItem: ControlWorkItem = {
      id: "w-journey-1",
      adoption_id: "adopt-journey-1",
      control_id: "ctrl-1",
      control_version_id: "cv-1",
      title: "Cloud Configuration & Access Baseline",
      provenance: "Synthetic Baseline Pack",
      pack_version: 1,
      bundle_digest: "digest-12345678",
      requirement_results: [
        {
          requirement_id: "req-1",
          requirement_version_id: "rv-1",
          requirement_identifier: "SYNTH-REQ-001",
          requirement_title: "Cloud baseline requirement",
          result: "APPLICABLE",
        },
      ],
      owner_user_id: null,
      owner_display_name: null,
      due_date: null,
      version: 1,
      is_current: true,
      is_stale: false,
      links: [],
    };

    const uploadFileSpy = vi.spyOn(controlApi, "uploadEvidenceFile").mockImplementation(async (_tenant, _token, file) => {
      return {
        id: "f-j1",
        original_filename: file.name,
        plaintext_size_bytes: file.size,
      };
    });

    const createEvidenceSpy = vi.spyOn(controlApi, "createEvidence").mockImplementation(async (_tenant, _token, workId, input) => {
      const idx = controlWorkItems.findIndex((c) => c.id === workId);
      const newLink: ControlEvidenceLink = {
        id: "link-j1",
        evidence_id: "ev-j1",
        revision_number: 1,
        digest: "c".repeat(64),
        file_ids: [input.file_id],
        filename: "architecture_diagram.pdf",
        file_size: 4096,
        classification: "Restricted",
        validity: "AVAILABLE",
        scan_status: "SCANNED_AT_LINK",
        scan_verified_at: new Date().toISOString(),
        review: "PENDING",
        rationale: input.rationale,
        created_at: new Date().toISOString(),
      };
      if (idx >= 0) {
        controlWorkItems[idx] = {
          ...controlWorkItems[idx],
          version: controlWorkItems[idx].version + 1,
          links: [...controlWorkItems[idx].links, newLink],
        };
      }
      return {
        operation_id: input.operation_id,
        event_id: "ev-upload-j1",
        applied_work_version: controlWorkItems[idx].version,
        replayed: false,
        current_work: controlWorkItems[idx],
      };
    });

    const initControlSpy = vi.spyOn(controlApi, "initializeControlWork").mockImplementation(async () => {
      controlWorkItems = [JSON.parse(JSON.stringify(dummyControlItem))];
      return {
        tenant_id: currentWorkspaceState.tenant_id,
        adoption_id: "adopt-journey-1",
        selection_revision: 1,
        answer_revision: 2,
        is_current: true,
        is_stale: false,
        items: controlWorkItems,
        total: 1,
      };
    });

    const patchControlSpy = vi.spyOn(controlApi, "patchControlWork").mockImplementation(async (_tenant, _token, workId, input) => {
      const idx = controlWorkItems.findIndex((c) => c.id === workId);
      if (idx >= 0) {
        controlWorkItems[idx] = {
          ...controlWorkItems[idx],
          owner_user_id: input.owner_user_id ?? controlWorkItems[idx].owner_user_id,
          due_date: input.due_date ?? controlWorkItems[idx].due_date,
          version: controlWorkItems[idx].version + 1,
        };
      }
      return {
        operation_id: "op-patch-j1",
        event_id: "ev-patch-j1",
        applied_work_version: controlWorkItems[idx].version,
        replayed: false,
        current_work: controlWorkItems[idx],
      };
    });

    const reviewSpy = vi.spyOn(controlApi, "createReview").mockImplementation(async (_tenant, _token, workId, linkId, input) => {
      const idx = controlWorkItems.findIndex((c) => c.id === workId);
      if (idx >= 0) {
        controlWorkItems[idx] = {
          ...controlWorkItems[idx],
          version: controlWorkItems[idx].version + 1,
          links: controlWorkItems[idx].links.map((lnk) =>
            lnk.id === linkId ? { ...lnk, review: input.decision } : lnk
          ),
        };
      }
      return {
        operation_id: input.operation_id,
        event_id: "ev-rev-j1",
        applied_work_version: controlWorkItems[idx].version,
        replayed: false,
        current_work: controlWorkItems[idx],
      };
    });

    // 4. Assessment items & procedures
    const dummyProcedure: Procedure = {
      id: "proc-j1",
      version: "1.0.0",
      digest: "b".repeat(64),
      criteria: [
        {
          id: "crit-impl",
          title: "Architecture Implementation",
          description: "Verify AWS/GCP cloud boundaries",
          sequence: 1,
        },
      ],
      disclaimer: "Synthetic audit procedure disclaimer",
    };
    vi.spyOn(assessmentApi, "fetchProcedure").mockResolvedValue(dummyProcedure);

    let dummyAssessmentItem: AssessmentWorkItem = {
      work_id: "w-journey-1",
      control_version_id: "cv-1",
      work_version: 1,
      assessment_revision: 1,
      procedure: dummyProcedure,
      latest_assessment: null,
      primary_state: "INSUFFICIENT_EVIDENCE",
      blockers: [],
      findings: [
        {
          id: "find-j1",
          source_event_id: "ev-f1",
          current_event_id: "ev-f1",
          severity: "MEDIUM",
          status: "OPEN",
          owner_user_id: "u-mgr",
          owner_display_name: "Bob Manager",
          due_date: "2026-11-20",
          version: 1,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      history: [],
      requirement_results: [{ requirement_id: "req-1", status: "EVALUATED" }],
    };

    let readinessSummary: ReadinessSummary = {
      total_controls: 1,
      stale_work: 0,
      needs_information: 0,
      not_applicable: 0,
      unassessed: 0,
      unavailable_evidence: 0,
      stale_assessment: 0,
      insufficient_evidence: 1,
      fail: 0,
      partial: 0,
      pass_with_open_findings: 0,
      pass_count: 0,
      open_findings: 1,
      in_remediation_findings: 0,
      resolved_findings: 0,
      blocked_control_ids: [],
      reason_codes: ["OPEN_FINDINGS"],
    };

    vi.spyOn(assessmentApi, "fetchAssessmentWorkList").mockImplementation(async () => ({
      tenant_id: currentWorkspaceState.tenant_id,
      adoption_id: "adopt-journey-1",
      selection_revision: 1,
      answer_revision: 2,
      is_current: true,
      is_stale: false,
      items: [JSON.parse(JSON.stringify(dummyAssessmentItem))],
      summary: JSON.parse(JSON.stringify(readinessSummary)),
      total: 1,
    }));

    const recordAssessSpy = vi.spyOn(assessmentApi, "recordAssessment").mockImplementation(async () => {
      dummyAssessmentItem = {
        ...dummyAssessmentItem,
        primary_state: "PASS",
        latest_assessment: {
          event_id: "ev-assess-j1",
          revision: 2,
          result: "PASS",
          actor_id: "u-owner",
          created_at: new Date().toISOString(),
          rationale: "Cloud configuration confirmed compliant",
          criterion_results: [{ criterion_id: "crit-impl", result: "PASS", notes: null }],
          evidence_pins: [
            {
              link_id: "link-j1",
              evidence_id: "ev-j1",
              revision_number: 1,
              revision_digest: "c".repeat(64),
              latest_review_event_id: "ev-rev-j1",
              file_id: "f-j1",
              file_hash: "f".repeat(64),
              scan_verified: true,
              quarantine_cleared: true,
              validity: "AVAILABLE",
              review: "ACCEPTED",
            },
          ],
          is_stale: false,
          stale_reasons: [],
        },
      };
      readinessSummary = {
        ...readinessSummary,
        insufficient_evidence: 0,
        pass_count: 1,
      };
      return {
        operation_id: "op-assess-j1",
        event_id: "ev-assess-j1",
        applied_revision: 2,
        replayed: false,
        current_item: dummyAssessmentItem,
        summary: readinessSummary,
      };
    });

    const updateFindingSpy = vi.spyOn(assessmentApi, "updateFinding").mockImplementation(async () => {
      dummyAssessmentItem = {
        ...dummyAssessmentItem,
        findings: [
          {
            ...dummyAssessmentItem.findings[0],
            status: "IN_REMEDIATION",
            version: 2,
          },
        ],
      };
      readinessSummary = {
        ...readinessSummary,
        open_findings: 0,
        in_remediation_findings: 1,
      };
      return {
        operation_id: "op-find-j1",
        event_id: "ev-find-j1",
        applied_revision: 2,
        replayed: false,
        current_item: dummyAssessmentItem,
        summary: readinessSummary,
      };
    });

    const recordRetestSpy = vi.spyOn(assessmentApi, "recordRetest").mockImplementation(async () => {
      dummyAssessmentItem = {
        ...dummyAssessmentItem,
        findings: [
          {
            ...dummyAssessmentItem.findings[0],
            status: "RESOLVED",
            version: 3,
          },
        ],
      };
      readinessSummary = {
        ...readinessSummary,
        in_remediation_findings: 0,
        resolved_findings: 1,
      };
      return {
        operation_id: "op-retest-j1",
        event_id: "ev-retest-j1",
        applied_revision: 3,
        replayed: false,
        current_item: dummyAssessmentItem,
        summary: readinessSummary,
      };
    });

    // ── RENDER PORTAL ──
    render(
      <I18nProvider>
        <CustomerDemoPortal
          tenantId="11111111-1111-1111-1111-111111111111"
          token="test-token"
          tenantName="Acme Corp"
          userRole="owner"
        />
      </I18nProvider>
    );

    // Initial Overview landing
    await waitFor(() => expect(screen.getByTestId("portal-overview-view")).toBeInTheDocument());

    // ── STEP 1: Company Setup ──
    fireEvent.click(screen.getByTestId("nav-view-company_setup"));
    await waitFor(() => expect(screen.getByTestId("portal-view-container-company_setup")).toBeInTheDocument());

    // Switch cloud usage to yes and save
    fireEvent.click(screen.getByTestId("cloud-yes"));
    fireEvent.click(screen.getByTestId("save-answers-btn"));
    await waitFor(() => expect(saveSpy).toHaveBeenCalled());

    // ── STEP 2: Frameworks & Adoption ──
    fireEvent.click(screen.getByTestId("nav-view-frameworks"));
    await waitFor(() => expect(screen.getByTestId("portal-frameworks-view")).toBeInTheDocument());

    // Evaluate
    fireEvent.click(screen.getByTestId("evaluate-btn"));
    await waitFor(() => {
      expect(evalSpy).toHaveBeenCalled();
      expect(screen.getByTestId("open-adopt-modal-btn")).toBeInTheDocument();
    });

    // Adopt pack
    fireEvent.click(screen.getByTestId("open-adopt-modal-btn"));
    expect(screen.getByTestId("adopt-pack-modal")).toBeInTheDocument();

    // Confirm checkboxes in modal
    fireEvent.click(screen.getByTestId("ack-synthetic-checkbox"));
    const missingCheck = screen.queryByTestId("ack-missing-checkbox");
    if (missingCheck) fireEvent.click(missingCheck);
    fireEvent.click(screen.getByTestId("confirm-adopt-btn"));
    await waitFor(() => expect(adoptSpy).toHaveBeenCalled());

    // ── STEP 3: Control Initialization ──
    fireEvent.click(screen.getByTestId("nav-view-controls_evidence"));
    await waitFor(() => {
      expect(screen.getByTestId("portal-controls-view")).toBeInTheDocument();
      expect(screen.getByTestId("init-control-work-btn")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("init-control-work-btn"));
    await waitFor(() => {
      expect(initControlSpy).toHaveBeenCalled();
      expect(screen.getByTestId("control-card-w-journey-1")).toBeInTheDocument();
    });

    // ── STEP 4: Owner Assignment ──
    const ownerSelect = screen.getByTestId("owner-select-w-journey-1");
    fireEvent.change(ownerSelect, { target: { value: "u-mgr" } });
    fireEvent.click(screen.getByTestId("save-assignment-btn-w-journey-1"));
    await waitFor(() => expect(patchControlSpy).toHaveBeenCalled());

    // ── STEP 5: Real Simulated Evidence Upload & Review ──
    // 5a. Open upload modal
    const openUploadBtn = screen.getByTestId("open-upload-modal-btn-w-journey-1");
    fireEvent.click(openUploadBtn);
    expect(screen.getByTestId("upload-evidence-modal")).toBeInTheDocument();

    // 5b. Simulate file input selection
    const file = new File(["cloud baseline architecture binary proof"], "architecture_diagram.pdf", { type: "application/pdf" });
    const fileInput = screen.getByTestId("evidence-file-input");
    fireEvent.change(fileInput, { target: { files: [file] } });

    // 5c. Fill rationale and submit upload
    const uploadRationaleInput = screen.getByTestId("evidence-rationale-input");
    fireEvent.change(uploadRationaleInput, { target: { value: "Cloud baseline architecture proof" } });

    fireEvent.click(screen.getByTestId("submit-evidence-upload-btn"));
    await waitFor(() => {
      expect(uploadFileSpy).toHaveBeenCalled();
      expect(createEvidenceSpy).toHaveBeenCalled();
      expect(screen.getByTestId("review-link-btn-link-j1")).toBeInTheDocument();
    });

    // 5d. Review the newly uploaded and pinned evidence link
    const reviewBtn = screen.getByTestId("review-link-btn-link-j1");
    fireEvent.click(reviewBtn);
    expect(screen.getByTestId("review-evidence-modal")).toBeInTheDocument();

    const rationaleInput = screen.getByTestId("review-rationale-input");
    fireEvent.change(rationaleInput, { target: { value: "Architecture evidence verified" } });
    fireEvent.click(screen.getByTestId("submit-review-btn"));
    await waitFor(() => expect(reviewSpy).toHaveBeenCalled());

    // ── STEP 6: Human Assessment ──
    fireEvent.click(screen.getByTestId("nav-view-assessments_findings"));
    await waitFor(() => {
      expect(screen.getByTestId("portal-assessments-view")).toBeInTheDocument();
      expect(screen.getByTestId("assessment-card-w-journey-1")).toBeInTheDocument();
    });

    // Fill assessment form: select PASS result, select criterion, select evidence, submit
    const assessSelect = screen.getByLabelText("Assessment Decision");
    fireEvent.change(assessSelect, { target: { value: "PASS" } });

    const critSelect = screen.getByLabelText("Criterion Architecture Implementation");
    fireEvent.change(critSelect, { target: { value: "PASS" } });

    const evCheck = screen.getByLabelText("Evidence architecture_diagram.pdf");
    fireEvent.click(evCheck);

    const assessRationale = screen.getByLabelText("Assessment Rationale");
    fireEvent.change(assessRationale, { target: { value: "Cloud configuration confirmed compliant" } });

    fireEvent.click(screen.getByTestId("record-assessment-submit-w-journey-1"));
    await waitFor(() => expect(recordAssessSpy).toHaveBeenCalled());

    // ── STEP 7: Finding / Remediation / Retest ──
    // Switch to Findings tab
    fireEvent.click(screen.getByTestId("tab-findings-w-journey-1"));
    await waitFor(() => expect(screen.getByTestId("finding-row-find-j1")).toBeInTheDocument());

    // Click Update Finding
    fireEvent.click(screen.getByTestId("edit-finding-btn-find-j1"));
    expect(screen.getByTestId("remediation-form")).toBeInTheDocument();

    const noteInput = document.getElementById("remediation-note") as HTMLTextAreaElement;
    fireEvent.change(noteInput, { target: { value: "Boundary policies applied" } });
    fireEvent.click(screen.getByTestId("save-remediation-btn"));
    await waitFor(() => expect(updateFindingSpy).toHaveBeenCalled());

    // Switch to Retest tab and record retest
    fireEvent.click(screen.getByTestId("tab-retest-w-journey-1"));
    await waitFor(() => expect(document.getElementById("retest-finding-select-w-journey-1")).toBeInTheDocument());

    const retestFindingSelect = document.getElementById("retest-finding-select-w-journey-1") as HTMLSelectElement;
    fireEvent.change(retestFindingSelect, { target: { value: "find-j1" } });

    const retestResultSelect = document.getElementById("retest-res-w-journey-1") as HTMLSelectElement;
    fireEvent.change(retestResultSelect, { target: { value: "PASS" } });

    const retestCritSelect = screen.getByLabelText("Retest criterion Architecture Implementation");
    fireEvent.change(retestCritSelect, { target: { value: "PASS" } });

    const retestEvCheck = screen.getByLabelText("Retest evidence architecture_diagram.pdf");
    fireEvent.click(retestEvCheck);

    const retestRationaleInput = document.getElementById("retest-rat-w-journey-1") as HTMLTextAreaElement;
    fireEvent.change(retestRationaleInput, { target: { value: "Retest confirmed passing" } });

    fireEvent.click(screen.getByTestId("record-retest-submit-w-journey-1"));
    await waitFor(() => expect(recordRetestSpy).toHaveBeenCalled());

    // ── STEP 8: Overview Return & Verification ──
    fireEvent.click(screen.getByTestId("nav-view-overview"));
    await waitFor(() => expect(screen.getByTestId("portal-overview-view")).toBeInTheDocument());

    // Verify overview landing is fully populated
    expect(screen.getByTestId("portal-page-title")).toHaveTextContent("Overview");

    // ── STEP 9: Work Queue in Connected Journey ──
    fireEvent.click(screen.getByTestId("nav-view-work_queue"));
    await waitFor(() => {
      expect(screen.getByTestId("portal-work-queue-view")).toBeInTheDocument();
      expect(screen.getByTestId("work-queue-title")).toBeInTheDocument();
      expect(screen.getByTestId("queue-row-ctrl-w-journey-1")).toBeInTheDocument();
    });
    expect(screen.getByTestId("bucket-findings-btn")).toHaveTextContent("Open Findings (0)");
  }, 15000);

  it("navigates to Organization view and preserves unsaved answers in Company Setup", async () => {
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(mockWorkspace);

    render(
      <I18nProvider>
        <CustomerDemoPortal
          tenantId="11111111-1111-1111-1111-111111111111"
          token="token-xyz"
          userRole="owner"
          initialView="company_setup"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("portal-setup-view")).toBeInTheDocument();
    });

    // Make an unsaved edit
    const cloudNoRadio = screen.getByTestId("cloud-no") as HTMLInputElement;
    fireEvent.click(cloudNoRadio);
    expect(cloudNoRadio.checked).toBe(true);

    // Navigate to Organization view
    fireEvent.click(screen.getByTestId("nav-view-organization"));

    await waitFor(() => {
      expect(screen.getByTestId("portal-organization-view")).toBeInTheDocument();
      expect(screen.getByTestId("portal-page-title")).toHaveTextContent("Organization");
    });

    // Navigate back to Company Setup
    fireEvent.click(screen.getByTestId("nav-view-company_setup"));

    await waitFor(() => {
      expect(screen.getByTestId("portal-setup-view")).toBeInTheDocument();
    });

    // Verify unsaved edit was preserved (draft not lost)
    const restoredCloudNo = screen.getByTestId("cloud-no") as HTMLInputElement;
    expect(restoredCloudNo.checked).toBe(true);
  });
  it("navigates to Work Queue view and preserves unsaved answers in Company Setup", async () => {
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(mockWorkspace);

    render(
      <I18nProvider>
        <CustomerDemoPortal
          tenantId="11111111-1111-1111-1111-111111111111"
          token="token-xyz"
          userRole="owner"
          initialView="company_setup"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("portal-setup-view")).toBeInTheDocument();
    });

    // Make an unsaved edit
    const cloudNoRadio = screen.getByTestId("cloud-no") as HTMLInputElement;
    fireEvent.click(cloudNoRadio);
    expect(cloudNoRadio.checked).toBe(true);

    // Navigate to Work Queue view
    fireEvent.click(screen.getByTestId("nav-view-work_queue"));

    await waitFor(() => {
      expect(screen.getByTestId("portal-work-queue-view")).toBeInTheDocument();
      expect(screen.getByTestId("portal-page-title")).toHaveTextContent("Work Queue");
    });

    // Navigate back to Company Setup
    fireEvent.click(screen.getByTestId("nav-view-company_setup"));

    await waitFor(() => {
      expect(screen.getByTestId("portal-setup-view")).toBeInTheDocument();
    });

    // Verify unsaved edit was preserved (draft not lost)
    const restoredCloudNo = screen.getByTestId("cloud-no") as HTMLInputElement;
    expect(restoredCloudNo.checked).toBe(true);
  });

  it("proves direct hash #preaudit falls back to overview when feature is OFF", async () => {
    vi.spyOn(api, "fetchWorkspace").mockResolvedValue(mockWorkspace);
    window.location.hash = "#preaudit";

    render(
      <I18nProvider>
        <CustomerDemoPortal
          tenantId="11111111-1111-1111-1111-111111111111"
          token="token-xyz"
          userRole="owner"
        />
      </I18nProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("portal-overview-view")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("nav-view-preaudit")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portal-preaudit-view")).not.toBeInTheDocument();
  });
});