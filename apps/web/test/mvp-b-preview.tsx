import React from "react";
import { createRoot } from "react-dom/client";
import { I18nProvider } from "../src/i18n/I18nContext";
import { ControlEvidenceWorkspace } from "../src/customer-demo/ControlEvidenceWorkspace";
import "../src/customer-demo/modern-workspace.css";
import { WorkspaceData } from "../src/customer-demo/types";
import {
  ControlEvidenceLink,
  ControlWorkItem,
  MutationReceipt,
  OwnerDirectoryResponse,
  WorkEvent,
  WorkHistoryResponse,
  WorkListResponse,
} from "../src/customer-demo/control-evidence-types";

// Strict dev guarding per contract
if (!import.meta.env.DEV) {
  throw new Error("UI fixture only available in dev mode");
}

const FACT_CLOUD_UUID = "e2d7e192-3a55-46b5-8eb4-d7586aef0001";
const FACT_REGION_UUID = "e2d7e192-3a55-46b5-8eb4-d7586aef0002";

const initialPreviewWorkspace: WorkspaceData = {
  tenant_id: "11111111-1111-1111-1111-111111111111",
  current_revision: 1,
  selection_revision: 1,
  manifest: {
    disclaimer:
      "Demonstration environment only. Evaluator results and compliance profiles are synthetic and non-binding.",
    evaluator_version: "wp09-synthetic-v1",
    companies: [
      { code: "ALPHA", display_name: "Alpha Cloud Corp" },
      { code: "BETA", display_name: "Beta On-Premises Ltd" },
    ],
    fact_definitions: [
      {
        id: "fact-cloud-id",
        version_id: FACT_CLOUD_UUID,
        key: "synthetic_wp09_uses_cloud",
        label: "Cloud Hosted Architecture",
        description: "Organization utilizes cloud infrastructure for hosting services.",
        value_type: "BOOLEAN",
      },
      {
        id: "fact-region-id",
        version_id: FACT_REGION_UUID,
        key: "synthetic_wp09_operating_region",
        label: "Primary Operating Region",
        description: "Primary geographic operational region for core workloads.",
        value_type: "ENUM",
        enum_options: [
          { code: "EU", label: "European Economic Area" },
          { code: "OTHER", label: "Other Global Region" },
        ],
      },
    ],
    packs: [
      {
        pack_id: "pack-synthetic-v2",
        pack_version_id: "pack-v2-ver-id",
        version: "2.0.0",
        name: "Modern Workspace Security Governance",
        description: "Expanded zero-trust baseline with automated pipeline security scanning.",
        bundle_digest: "98a1b2c300000000000000000000000000000000000000000000000000000000",
        requirement_count: 3,
        requirements: [
          {
            id: "req-1",
            version_id: "req-1-v2",
            identifier: "SYNTH-REQ-001",
            title: "Cloud Architecture Governance (Extended)",
            description: "Extended zero-trust cloud boundaries, mandatory telemetry and review.",
            rule_id: "rule-1",
            rule_version_id: "rule-1-v2",
            control_id: "ctrl-1",
            control_version_id: "ctrl-1-v1",
            control_identifier: "SYNTH-CTRL-001",
            control_title: "Cloud Configuration & Access Baseline",
          },
          {
            id: "req-2",
            version_id: "req-2-v1",
            identifier: "SYNTH-REQ-002",
            title: "EU Regional Data Residency",
            description: "Confidential data stored strictly within certified European availability zones.",
            rule_id: "rule-2",
            rule_version_id: "rule-2-v1",
            control_id: "ctrl-2",
            control_version_id: "ctrl-2-v1",
            control_identifier: "SYNTH-CTRL-002",
            control_title: "Regional Storage & Cryptographic Boundaries",
          },
          {
            id: "req-3",
            version_id: "req-3-v1",
            identifier: "SYNTH-REQ-003",
            title: "Continuous Automated Vulnerability Scanning",
            description: "Automated container and dependency scanning in continuous deployment pipelines.",
            rule_id: "rule-3",
            rule_version_id: "rule-3-v1",
            control_id: "ctrl-3",
            control_version_id: "ctrl-3-v1",
            control_identifier: "SYNTH-CTRL-003",
            control_title: "Automated Pipeline Security Scanning",
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
      [FACT_CLOUD_UUID]: true,
      [FACT_REGION_UUID]: "EU",
    },
    content_digest: "digest-alpha-001",
    created_at: "2026-10-22T10:00:00Z",
  },
  selected_pack: {
    selection_revision: 1,
    evaluation_id: "eval-init-001",
    pack_version_id: "pack-v2-ver-id",
    bundle_digest: "98a1b2c300000000000000000000000000000000000000000000000000000000",
    created_at: "2026-10-22T10:05:00Z",
    is_stale: false,
  },
  latest_evaluation: {
    id: "eval-init-001",
    tenant_id: "11111111-1111-1111-1111-111111111111",
    answer_revision: 1,
    pack_version_id: "pack-v2-ver-id",
    bundle_digest: "98a1b2c300000000000000000000000000000000000000000000000000000000",
    evaluator_version: "wp09-synthetic-v1",
    content_digest: "eval-digest-001",
    created_at: "2026-10-22T10:02:00Z",
    results: [
      {
        requirement_id: "req-1",
        requirement_version_id: "req-1-v2",
        identifier: "SYNTH-REQ-001",
        title: "Cloud Architecture Governance (Extended)",
        rule_id: "rule-1",
        rule_version_id: "rule-1-v2",
        result: "APPLICABLE",
        missing_fact_version_ids: [],
        explanation_tree: {
          op: "EQUALS",
          path: "facts.synthetic_wp09_uses_cloud",
          result: "APPLICABLE",
          message: "Organization utilizes cloud architecture.",
          missing_fact_version_ids: [],
          children: [],
        },
      },
      {
        requirement_id: "req-2",
        requirement_version_id: "req-2-v1",
        identifier: "SYNTH-REQ-002",
        title: "EU Regional Data Residency",
        rule_id: "rule-2",
        rule_version_id: "rule-2-v1",
        result: "APPLICABLE",
        missing_fact_version_ids: [],
        explanation_tree: {
          op: "EQUALS",
          path: "facts.synthetic_wp09_operating_region",
          result: "APPLICABLE",
          message: "Operating region confirmed within European Economic Area (EU).",
          missing_fact_version_ids: [],
          children: [],
        },
      },
      {
        requirement_id: "req-3",
        requirement_version_id: "req-3-v1",
        identifier: "SYNTH-REQ-003",
        title: "Continuous Automated Vulnerability Scanning",
        rule_id: "rule-3",
        rule_version_id: "rule-3-v1",
        result: "APPLICABLE",
        missing_fact_version_ids: [],
        explanation_tree: {
          op: "EQUALS",
          path: "facts.synthetic_wp09_uses_cloud",
          result: "APPLICABLE",
          message: "Automated vulnerability scanning applicable for cloud workloads.",
          missing_fact_version_ids: [],
          children: [],
        },
      },
    ],
  },
  history_summary: [
    {
      selection_revision: 1,
      pack_version_id: "pack-v2-ver-id",
      bundle_digest: "98a1b2c300000000000000000000000000000000000000000000000000000000",
      created_at: "2026-10-22T10:05:00Z",
    },
  ],
};

const initialControlWorkItems: ControlWorkItem[] = [
  {
    id: "work-1",
    adoption_id: "eval-init-001",
    control_id: "ctrl-1",
    control_version_id: "ctrl-1-v1",
    title: "Cloud Configuration & Access Baseline",
    provenance: "Synthetic Security Baseline / ISO-27001 Synthetic Alignment",
    pack_version: 2,
    bundle_digest: "98a1b2c300000000000000000000000000000000000000000000000000000000",
    requirement_results: [
      {
        requirement_id: "req-1",
        requirement_version_id: "req-1-v2",
        requirement_identifier: "SYNTH-REQ-001",
        requirement_title: "Cloud Architecture Governance (Extended)",
        result: "APPLICABLE",
      },
    ],
    owner_user_id: "user-alice",
    owner_display_name: "Alice Compliance Lead",
    due_date: "2026-12-31",
    version: 2,
    is_current: true,
    is_stale: false,
    links: [
      {
        id: "link-1",
        evidence_id: "ev-101",
        revision_number: 1,
        digest: "65d0f76600000000000000000000000000000000000000000000000000000000",
        file_ids: ["file-101"],
        filename: "cloud-baseline-audit.pdf",
        file_size: 40960,
        classification: "Restricted",
        validity: "AVAILABLE",
        scan_status: "SCANNED_AT_LINK",
        scan_verified_at: "2026-10-22T14:30:00Z",
        review: "ACCEPTED",
        rationale: "Verified cryptographic boundaries and IAM lockdown per Q3 architecture review.",
        created_at: "2026-10-22T14:30:00Z",
      },
    ],
  },
  {
    id: "work-2",
    adoption_id: "eval-init-001",
    control_id: "ctrl-2",
    control_version_id: "ctrl-2-v1",
    title: "Regional Storage & Cryptographic Boundaries",
    provenance: "EU GDPR Data Protection Guidelines / Synthetic",
    pack_version: 2,
    bundle_digest: "98a1b2c300000000000000000000000000000000000000000000000000000000",
    requirement_results: [
      {
        requirement_id: "req-2",
        requirement_version_id: "req-2-v1",
        requirement_identifier: "SYNTH-REQ-002",
        requirement_title: "EU Regional Data Residency",
        result: "APPLICABLE",
      },
    ],
    owner_user_id: null,
    owner_display_name: null,
    due_date: null,
    version: 2,
    is_current: true,
    is_stale: false,
    links: [
      {
        id: "link-2",
        evidence_id: "ev-101",
        revision_number: 1,
        digest: "65d0f76600000000000000000000000000000000000000000000000000000000",
        file_ids: ["file-101"],
        filename: "cloud-baseline-audit.pdf",
        file_size: 40960,
        classification: "Restricted",
        validity: "AVAILABLE",
        scan_status: "SCANNED_AT_LINK",
        scan_verified_at: "2026-10-22T15:00:00Z",
        review: "PENDING",
        rationale: "Deliberate reuse: shared European KMS storage boundary verification applied to regional isolation control.",
        created_at: "2026-10-22T15:00:00Z",
      },
    ],
  },
  {
    id: "work-3",
    adoption_id: "eval-init-001",
    control_id: "ctrl-3",
    control_version_id: "ctrl-3-v1",
    title: "Automated Pipeline Security Scanning",
    provenance: "Continuous Compliance Framework v2",
    pack_version: 2,
    bundle_digest: "98a1b2c300000000000000000000000000000000000000000000000000000000",
    requirement_results: [
      {
        requirement_id: "req-3",
        requirement_version_id: "req-3-v1",
        requirement_identifier: "SYNTH-REQ-003",
        requirement_title: "Continuous Automated Vulnerability Scanning",
        result: "APPLICABLE",
      },
    ],
    owner_user_id: "user-bob",
    owner_display_name: "Bob Security Ops",
    due_date: "2026-11-30",
    version: 1,
    is_current: true,
    is_stale: false,
    links: [],
  },
];

let currentWorkspace: WorkspaceData = JSON.parse(
  JSON.stringify(initialPreviewWorkspace)
);

let currentControlWorkItems: ControlWorkItem[] = JSON.parse(
  JSON.stringify(initialControlWorkItems)
);

export async function handlePreviewFetch(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const url = typeof input === "string" ? input : input.toString();
  const method = init?.method ? init.method.toUpperCase() : "GET";

  // 1. GET /customer-demo/workspace
  if (url.includes("/customer-demo/workspace") && method === "GET") {
    return new Response(JSON.stringify(currentWorkspace), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 2. GET /customer-demo/control-work/owners
  if (url.includes("/customer-demo/control-work/owners") && method === "GET") {
    const res: OwnerDirectoryResponse = {
      items: [
        { user_id: "user-alice", display_name: "Alice Compliance Lead" },
        { user_id: "user-bob", display_name: "Bob Security Ops" },
        { user_id: "user-charlie", display_name: "Charlie Auditor" },
      ],
      total: 3,
    };
    return new Response(JSON.stringify(res), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 3. GET /customer-demo/control-work
  if (url.endsWith("/customer-demo/control-work") && method === "GET") {
    const res: WorkListResponse = {
      tenant_id: currentWorkspace.tenant_id,
      adoption_id: currentWorkspace.selected_pack?.evaluation_id || "eval-init-001",
      selection_revision: currentWorkspace.selection_revision,
      answer_revision: currentWorkspace.current_revision,
      is_current: true,
      is_stale: false,
      items: currentControlWorkItems,
      total: currentControlWorkItems.length,
    };
    return new Response(JSON.stringify(res), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 4. POST /customer-demo/control-work/initialize
  if (url.includes("/customer-demo/control-work/initialize") && method === "POST") {
    const res: WorkListResponse = {
      tenant_id: currentWorkspace.tenant_id,
      adoption_id: currentWorkspace.selected_pack?.evaluation_id || "eval-init-001",
      selection_revision: currentWorkspace.selection_revision,
      answer_revision: currentWorkspace.current_revision,
      is_current: true,
      is_stale: false,
      items: currentControlWorkItems,
      total: currentControlWorkItems.length,
    };
    return new Response(JSON.stringify(res), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 5. PATCH /customer-demo/control-work/{work_id}
  if (url.match(/\/customer-demo\/control-work\/[^/]+$/) && method === "PATCH") {
    const parts = url.split("/");
    const workId = parts[parts.length - 1];
    const body = init?.body ? JSON.parse(init.body as string) : {};
    const item = currentControlWorkItems.find((w) => w.id === workId);
    if (!item) {
      return new Response(JSON.stringify({ detail: "Work item not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }

    item.owner_user_id = body.owner_user_id ?? null;
    item.owner_display_name = body.owner_user_id
      ? body.owner_user_id === "user-alice"
        ? "Alice Compliance Lead"
        : "Bob Security Ops"
      : null;
    item.due_date = body.due_date ?? null;
    item.version += 1;

    const receipt: MutationReceipt = {
      operation_id: body.operation_id,
      event_id: "event-" + Date.now(),
      applied_work_version: item.version,
      replayed: false,
      current_work: item,
    };
    return new Response(JSON.stringify(receipt), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 6. POST /customer-demo/control-work/{work_id}/evidence
  if (url.includes("/evidence") && method === "POST") {
    const parts = url.split("/");
    const workId = parts[parts.length - 2];
    const body = init?.body ? JSON.parse(init.body as string) : {};
    const item = currentControlWorkItems.find((w) => w.id === workId);
    if (!item) {
      return new Response(JSON.stringify({ detail: "Work item not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }

    const newLink: ControlEvidenceLink = {
      id: "link-" + Date.now(),
      evidence_id: "ev-" + Date.now(),
      revision_number: 1,
      digest: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      file_ids: [body.file_id || "file-1"],
      filename: "uploaded-evidence.pdf",
      file_size: 40960,
      classification: "Restricted",
      validity: "AVAILABLE",
      scan_status: "SCANNED_AT_LINK",
      scan_verified_at: new Date().toISOString(),
      review: "PENDING",
      rationale: body.rationale,
      created_at: new Date().toISOString(),
    };
    item.links.push(newLink);
    item.version += 1;

    const receipt: MutationReceipt = {
      operation_id: body.operation_id,
      event_id: "event-" + Date.now(),
      applied_work_version: item.version,
      replayed: false,
      current_work: item,
    };
    return new Response(JSON.stringify(receipt), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 7. POST /customer-demo/control-work/{work_id}/links (Reuse)
  if (url.match(/\/control-work\/[^/]+\/links$/) && method === "POST") {
    const parts = url.split("/");
    const workId = parts[parts.length - 2];
    const body = init?.body ? JSON.parse(init.body as string) : {};
    const item = currentControlWorkItems.find((w) => w.id === workId);
    if (!item) {
      return new Response(JSON.stringify({ detail: "Work item not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }

    const reusedLink: ControlEvidenceLink = {
      id: "link-reused-" + Date.now(),
      evidence_id: body.evidence_id,
      revision_number: body.evidence_revision_number,
      digest: body.evidence_revision_digest,
      file_ids: ["file-101"],
      filename: "cloud-baseline-audit.pdf",
      file_size: 40960,
      classification: "Restricted",
      validity: "AVAILABLE",
      scan_status: "SCANNED_AT_LINK",
      scan_verified_at: new Date().toISOString(),
      review: "PENDING",
      rationale: body.rationale,
      created_at: new Date().toISOString(),
    };
    item.links.push(reusedLink);
    item.version += 1;

    const receipt: MutationReceipt = {
      operation_id: body.operation_id,
      event_id: "event-" + Date.now(),
      applied_work_version: item.version,
      replayed: false,
      current_work: item,
    };
    return new Response(JSON.stringify(receipt), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 8. POST /customer-demo/control-work/{work_id}/links/{link_id}/reviews
  if (url.includes("/reviews") && method === "POST") {
    const parts = url.split("/");
    const linkId = parts[parts.length - 2];
    const body = init?.body ? JSON.parse(init.body as string) : {};

    let targetItem: ControlWorkItem | undefined;
    let targetLink: ControlEvidenceLink | undefined;
    for (const w of currentControlWorkItems) {
      const l = w.links.find((lnk) => lnk.id === linkId);
      if (l) {
        targetItem = w;
        targetLink = l;
        break;
      }
    }

    if (!targetItem || !targetLink) {
      return new Response(JSON.stringify({ detail: "Link not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }

    targetLink.review = body.decision;
    targetItem.version += 1;

    const receipt: MutationReceipt = {
      operation_id: body.operation_id,
      event_id: "event-" + Date.now(),
      applied_work_version: targetItem.version,
      replayed: false,
      current_work: targetItem,
    };
    return new Response(JSON.stringify(receipt), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 9. GET /customer-demo/control-work/{work_id}/history
  if (url.includes("/history") && method === "GET") {
    const parts = url.split("/");
    const workId = parts[parts.length - 2];
    const events: WorkEvent[] = [
      {
        revision: 1,
        type: "INITIALIZED",
        actor_id: "user-system",
        time: "2026-10-22T10:05:00Z",
        link_id: null,
        decision: null,
        details: { note: "Work initialized from pack adoption" },
      },
      {
        revision: 2,
        type: "EVIDENCE_LINKED",
        actor_id: "user-alice",
        time: "2026-10-22T14:30:00Z",
        link_id: "link-1",
        decision: null,
        details: { filename: "cloud-baseline-audit.pdf" },
      },
      {
        revision: 3,
        type: "EVIDENCE_REVIEWED",
        actor_id: "user-alice",
        time: "2026-10-22T14:35:00Z",
        link_id: "link-1",
        decision: "ACCEPTED",
        details: { rationale: "Suitability verified for cloud baseline" },
      },
    ];
    const res: WorkHistoryResponse = {
      tenant_id: currentWorkspace.tenant_id,
      work_id: workId,
      items: events,
      total: events.length,
    };
    return new Response(JSON.stringify(res), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 10. POST /v1/tenants/{tenant_id}/files (Upload)
  if (url.includes("/files") && method === "POST") {
    const fileRes = {
      id: "file-uploaded-" + Date.now(),
      tenant_id: currentWorkspace.tenant_id,
      original_filename: "synthetic-evidence.pdf",
      plaintext_size_bytes: 40960,
      classification: "Restricted",
      status: "ACTIVE",
    };
    return new Response(JSON.stringify(fileRes), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 11. GET /customer-demo/control-work/{work_id}/links/{link_id}/files/{file_id} (Download)
  if (url.includes("/files/") && method === "GET") {
    const content = "Synthetic demonstration file content. Not real customer data.";
    return new Response(content, {
      status: 200,
      headers: {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": 'attachment; filename="synthetic-evidence.pdf"',
      },
    });
  }

  // Reject all other network requests
  return new Response(
    JSON.stringify({ detail: "Blocked by synthetic preview sandbox" }),
    {
      status: 403,
      headers: { "Content-Type": "application/json" },
    }
  );
}

export function getPreviewWorkspace(): WorkspaceData {
  return currentWorkspace;
}

export function resetPreviewWorkspace(): void {
  currentWorkspace = JSON.parse(JSON.stringify(initialPreviewWorkspace));
  currentControlWorkItems = JSON.parse(JSON.stringify(initialControlWorkItems));
}

if (typeof window !== "undefined") {
  window.fetch = handlePreviewFetch;
}

const rootEl = document.getElementById("preview-root");
if (rootEl) {
  createRoot(rootEl).render(
    <React.StrictMode>
      <I18nProvider>
        <div className="modern-workspace-root" style={{ minHeight: "100vh", background: "var(--mw-canvas, #f5f5f7)", boxSizing: "border-box" }}>
          <div style={{ maxWidth: "1400px", margin: "0 auto", width: "100%", boxSizing: "border-box" }}>
            <ControlEvidenceWorkspace
              tenantId="11111111-1111-1111-1111-111111111111"
              token="synthetic-fixture-token-no-auth-value"
              selectionRevision={1}
              answerRevision={1}
              hasUnsavedParentEdits={false}
              isAdoptionStale={false}
              userRole="owner"
            />
          </div>
        </div>
      </I18nProvider>
    </React.StrictMode>
  );

  // Automatically expand history for demonstration of evidence workflow actions
  setTimeout(() => {
    const toggleHistoryBtn = document.querySelector('[data-testid^="toggle-history-btn-"]') as HTMLButtonElement | null;
    if (toggleHistoryBtn) {
      toggleHistoryBtn.click();
    }
  }, 400);

  setTimeout(() => {
    const de = document.documentElement;
    const body = document.body;
    const overflowing: Array<{
      tag: string;
      cls: string;
      id: string;
      rectRight: number;
      scrollW: number;
    }> = [];
    document.querySelectorAll("*").forEach((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.right > de.clientWidth + 1) {
        let parent: HTMLElement | null = el.parentElement;
        let isContained = false;
        while (
          parent &&
          parent !== document.body &&
          parent !== document.documentElement
        ) {
          const s = window.getComputedStyle(parent);
          if (
            s.overflowX === "auto" ||
            s.overflowX === "scroll" ||
            s.overflow === "auto" ||
            s.overflow === "scroll"
          ) {
            isContained = true;
            break;
          }
          parent = parent.parentElement;
        }
        if (!isContained) {
          overflowing.push({
            tag: el.tagName,
            cls: el.className,
            id: el.id,
            rectRight: Math.round(rect.right),
            scrollW: el.scrollWidth,
          });
        }
      }
    });

    const panelEl = document.querySelector(".mw-control-work-section, [data-testid='control-cards-container']") as HTMLElement | null;
    const panelRect = panelEl ? panelEl.getBoundingClientRect() : null;
    const panelMetrics = panelEl ? {
      clientWidth: panelEl.clientWidth,
      scrollWidth: panelEl.scrollWidth,
      rectWidth: panelRect ? Math.round(panelRect.width) : 0,
      rectRight: panelRect ? Math.round(panelRect.right) : 0,
      hasOverflow: panelEl.scrollWidth > panelEl.clientWidth,
    } : null;

    const measure = {
      innerWidth: window.innerWidth,
      innerHeight: window.innerHeight,
      docScrollWidth: de.scrollWidth,
      docClientWidth: de.clientWidth,
      bodyScrollWidth: body.scrollWidth,
      bodyClientWidth: body.clientWidth,
      hasOverflow: de.scrollWidth > de.clientWidth,
      overflowingCount: overflowing.length,
      overflowingSample: overflowing.slice(0, 10),
      panelMetrics,
      mediaQueries: {
        isMobile: window.matchMedia("(max-width: 640px)").matches,
        isTablet: window.matchMedia("(max-width: 900px)").matches,
      },
    };
    const measureEl = document.createElement("div");
    measureEl.id = "measured-overflow-results";
    measureEl.setAttribute("data-measure", JSON.stringify(measure));
    document.body.appendChild(measureEl);
  }, 1000);
}
