import React from "react";
import { createRoot } from "react-dom/client";
import { I18nProvider } from "../src/i18n/I18nContext";
import { CustomerDemoWorkspace } from "../src/customer-demo/CustomerDemoWorkspace";
import {
  AdoptionReceipt,
  AnswersData,
  EvaluationData,
  RequirementEvaluationResult,
  WorkspaceData,
} from "../src/customer-demo/types";

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
    disclaimer: "Demonstration environment only. Evaluator results and compliance profiles are synthetic and non-binding.",
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
        pack_id: "pack-synthetic-v1",
        pack_version_id: "pack-v1-ver-id",
        version: "1.0.0",
        name: "Synthetic Security Baseline",
        description: "Core cloud architecture and data isolation governance.",
        bundle_digest: "65d0f76600000000000000000000000000000000000000000000000000000000",
        requirement_count: 2,
        requirements: [
          {
            id: "req-1",
            version_id: "req-1-v1",
            identifier: "SYNTH-REQ-001",
            title: "Cloud Architecture Governance",
            description: "Requires secure architecture review and baseline controls for all hosted components.",
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
            title: "EU Regional Data Residency",
            description: "Confidential data stored strictly within certified European availability zones.",
            rule_id: "rule-2",
            rule_version_id: "rule-2-v1",
            control_id: "ctrl-2",
            control_version_id: "ctrl-2-v1",
            control_identifier: "SYNTH-CTRL-002",
            control_title: "Regional Storage & Cryptographic Boundaries",
          },
        ],
      },
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
            description: "Extended zero-trust cloud boundaries, mandatory telemetry and telemetry review.",
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
    pack_version_id: "pack-v1-ver-id",
    bundle_digest: "65d0f76600000000000000000000000000000000000000000000000000000000",
    created_at: "2026-10-22T10:00:00Z",
    is_stale: false,
  },
  latest_evaluation: {
    id: "eval-init-001",
    tenant_id: "11111111-1111-1111-1111-111111111111",
    answer_revision: 1,
    pack_version_id: "pack-v1-ver-id",
    bundle_digest: "65d0f76600000000000000000000000000000000000000000000000000000000",
    evaluator_version: "wp09-synthetic-v1",
    content_digest: "cd-eval-001",
    created_at: "2026-10-22T10:05:00Z",
    results: [
      {
        requirement_id: "req-1",
        requirement_version_id: "req-1-v1",
        identifier: "SYNTH-REQ-001",
        title: "Cloud Architecture Governance",
        rule_id: "rule-1",
        rule_version_id: "rule-1-v1",
        result: "APPLICABLE",
        missing_fact_version_ids: [],
        explanation_tree: {
          op: "EQUALS",
          path: "facts.synthetic_wp09_uses_cloud",
          result: "APPLICABLE",
          message: "Organization confirms active cloud deployment (Alpha profile preset).",
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
          message: "Primary operating region confirmed as European Economic Area (EU).",
          missing_fact_version_ids: [],
          children: [],
        },
      },
    ],
  },
  history_summary: [
    {
      selection_revision: 1,
      pack_version_id: "pack-v1-ver-id",
      bundle_digest: "65d0f76600000000000000000000000000000000000000000000000000000000",
      created_at: "2026-10-22T10:00:00Z",
    },
  ],
};

let currentWorkspace: WorkspaceData = JSON.parse(JSON.stringify(initialPreviewWorkspace));

// In-memory synthetic API interceptor following exact API contract
export async function handlePreviewFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
  const method = init?.method || "GET";

  // 1. GET /customer-demo/workspace
  if (url.includes("/customer-demo/workspace") && method === "GET") {
    return new Response(JSON.stringify(currentWorkspace), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 2. PUT /customer-demo/answers
  if (url.includes("/customer-demo/answers") && method === "PUT") {
    const body = init?.body ? JSON.parse(init.body as string) : {};
    if (body.expected_revision !== currentWorkspace.current_revision) {
      return new Response(JSON.stringify({ detail: "Conflict: Workspace answers revision mismatch." }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      });
    }

    const nextRev = currentWorkspace.current_revision + 1;
    const updatedAnswers: AnswersData = {
      tenant_id: currentWorkspace.tenant_id,
      revision: nextRev,
      company_code: body.company_code || "ALPHA",
      answers: body.answers || {},
      content_digest: `digest-rev-${nextRev}`,
      created_at: new Date().toISOString(),
    };

    currentWorkspace = {
      ...currentWorkspace,
      current_revision: nextRev,
      answers: updatedAnswers,
    };

    return new Response(JSON.stringify(updatedAnswers), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 3. POST /customer-demo/evaluations
  if (url.includes("/customer-demo/evaluations") && method === "POST") {
    const body = init?.body ? JSON.parse(init.body as string) : {};
    if (body.expected_revision !== currentWorkspace.current_revision) {
      return new Response(JSON.stringify({ detail: "Conflict: Answer revision changed before evaluation." }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      });
    }

    const pack = currentWorkspace.manifest.packs.find(
      (p) => p.pack_version_id === body.pack_version_id
    );
    if (!pack) {
      return new Response(JSON.stringify({ detail: "Pack not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }

    const rawFacts = currentWorkspace.answers?.answers || {};
    const usesCloud = rawFacts["synthetic_wp09_uses_cloud"] ?? rawFacts[FACT_CLOUD_UUID];
    const region = rawFacts["synthetic_wp09_operating_region"] ?? rawFacts[FACT_REGION_UUID];

    const results: RequirementEvaluationResult[] = pack.requirements.map((req) => {
      if (req.identifier === "SYNTH-REQ-001") {
        const isApp = usesCloud === true;
        const isNotApp = usesCloud === false;
        const status = isApp ? "APPLICABLE" : isNotApp ? "NOT_APPLICABLE" : "NEEDS_INFORMATION";
        return {
          requirement_id: req.id,
          requirement_version_id: req.version_id,
          identifier: req.identifier,
          title: req.title,
          rule_id: req.rule_id,
          rule_version_id: req.rule_version_id,
          result: status,
          missing_fact_version_ids: status === "NEEDS_INFORMATION" ? [FACT_CLOUD_UUID] : [],
          explanation_tree: {
            op: "EQUALS",
            path: "facts.synthetic_wp09_uses_cloud",
            result: status,
            message:
              status === "APPLICABLE"
                ? "Cloud usage confirmed by profile facts."
                : status === "NOT_APPLICABLE"
                ? "Cloud architecture is not in use."
                : "Cloud architecture fact is unknown/missing.",
            missing_fact_version_ids: status === "NEEDS_INFORMATION" ? [FACT_CLOUD_UUID] : [],
            children: [],
          },
        };
      }

      if (req.identifier === "SYNTH-REQ-002") {
        const isApp = region === "EU";
        const isNotApp = region === "OTHER";
        const status = isApp ? "APPLICABLE" : isNotApp ? "NOT_APPLICABLE" : "NEEDS_INFORMATION";
        return {
          requirement_id: req.id,
          requirement_version_id: req.version_id,
          identifier: req.identifier,
          title: req.title,
          rule_id: req.rule_id,
          rule_version_id: req.rule_version_id,
          result: status,
          missing_fact_version_ids: status === "NEEDS_INFORMATION" ? [FACT_REGION_UUID] : [],
          explanation_tree: {
            op: "EQUALS",
            path: "facts.synthetic_wp09_operating_region",
            result: status,
            message:
              status === "APPLICABLE"
                ? "Operating region confirmed within European Economic Area (EU)."
                : status === "NOT_APPLICABLE"
                ? "Operating region is outside European Economic Area."
                : "Operating region fact is unknown/missing.",
            missing_fact_version_ids: status === "NEEDS_INFORMATION" ? [FACT_REGION_UUID] : [],
            children: [],
          },
        };
      }

      // SYNTH-REQ-003 or other
      const isApp = usesCloud === true;
      const status = isApp ? "APPLICABLE" : "NOT_APPLICABLE";
      return {
        requirement_id: req.id,
        requirement_version_id: req.version_id,
        identifier: req.identifier,
        title: req.title,
        rule_id: req.rule_id,
        rule_version_id: req.rule_version_id,
        result: status,
        missing_fact_version_ids: [],
        explanation_tree: {
          op: "EQUALS",
          path: "facts.synthetic_wp09_uses_cloud",
          result: status,
          message:
            status === "APPLICABLE"
              ? "Automated pipeline vulnerability scanning applicable for cloud workloads."
              : "No cloud infrastructure requiring automated pipeline scanning.",
          missing_fact_version_ids: [],
          children: [],
        },
      };
    });

    const evalData: EvaluationData = {
      id: "eval-" + Date.now(),
      tenant_id: currentWorkspace.tenant_id,
      answer_revision: currentWorkspace.current_revision,
      pack_version_id: pack.pack_version_id,
      bundle_digest: pack.bundle_digest,
      evaluator_version: currentWorkspace.manifest.evaluator_version,
      content_digest: `cd-eval-${Date.now()}`,
      created_at: new Date().toISOString(),
      results,
    };

    currentWorkspace = {
      ...currentWorkspace,
      latest_evaluation: evalData,
    };

    return new Response(JSON.stringify(evalData), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 4. POST /customer-demo/adoptions
  if (url.includes("/customer-demo/adoptions") && method === "POST") {
    const body = init?.body ? JSON.parse(init.body as string) : {};
    if (body.expected_revision !== currentWorkspace.current_revision) {
      return new Response(JSON.stringify({ detail: "Conflict: Expected answers revision does not match current workspace revision" }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (!currentWorkspace.latest_evaluation || currentWorkspace.latest_evaluation.id !== body.evaluation_id) {
      return new Response(JSON.stringify({ detail: "Referenced evaluation not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (!body.acknowledge_synthetic) {
      return new Response(JSON.stringify({ detail: "Synthetic acknowledgement is required." }), {
        status: 422,
        headers: { "Content-Type": "application/json" },
      });
    }

    const pack = currentWorkspace.manifest.packs.find(
      (p) => p.pack_version_id === body.pack_version_id
    ) || currentWorkspace.manifest.packs[0];

    const nextSelectionRev = currentWorkspace.selection_revision + 1;
    const receipt: AdoptionReceipt = {
      id: "receipt-" + Date.now(),
      tenant_id: currentWorkspace.tenant_id,
      selection_revision: nextSelectionRev,
      evaluation_id: body.evaluation_id,
      pack_version_id: body.pack_version_id,
      bundle_digest: pack.bundle_digest,
      created_at: new Date().toISOString(),
      is_current: true,
      current_selection_revision: nextSelectionRev,
      current_pack_version_id: body.pack_version_id,
    };

    currentWorkspace = {
      ...currentWorkspace,
      selection_revision: nextSelectionRev,
      selected_pack: {
        selection_revision: nextSelectionRev,
        evaluation_id: body.evaluation_id,
        pack_version_id: body.pack_version_id,
        bundle_digest: pack.bundle_digest,
        created_at: new Date().toISOString(),
        is_stale: false,
      },
      history_summary: [
        {
          selection_revision: nextSelectionRev,
          pack_version_id: body.pack_version_id,
          bundle_digest: pack.bundle_digest,
          created_at: new Date().toISOString(),
        },
        ...currentWorkspace.history_summary,
      ],
    };

    return new Response(JSON.stringify(receipt), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Reject all other network requests
  return new Response(JSON.stringify({ detail: "Blocked by synthetic preview sandbox" }), {
    status: 403,
    headers: { "Content-Type": "application/json" },
  });
}

export function getPreviewWorkspace(): WorkspaceData {
  return currentWorkspace;
}

export function resetPreviewWorkspace(): void {
  currentWorkspace = JSON.parse(JSON.stringify(initialPreviewWorkspace));
}

if (typeof window !== "undefined") {
  window.fetch = handlePreviewFetch;
}

const rootEl = document.getElementById("preview-root");
if (rootEl) {
  createRoot(rootEl).render(
    <React.StrictMode>
      <I18nProvider>
        <CustomerDemoWorkspace
          tenantId="11111111-1111-1111-1111-111111111111"
          token="synthetic-fixture-token-no-auth-value"
          userRole="owner"
        />
      </I18nProvider>
    </React.StrictMode>
  );

  setTimeout(() => {
    const de = document.documentElement;
    const body = document.body;
    const overflowing: Array<{ tag: string; cls: string; id: string; rectRight: number; scrollW: number }> = [];
    document.querySelectorAll('*').forEach((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.right > de.clientWidth + 1) {
        let parent: HTMLElement | null = el.parentElement;
        let isContained = false;
        while (parent && parent !== document.body && parent !== document.documentElement) {
          const s = window.getComputedStyle(parent);
          if (s.overflowX === 'auto' || s.overflowX === 'scroll' || s.overflow === 'auto' || s.overflow === 'scroll') {
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
    };
    const measureEl = document.createElement("div");
    measureEl.id = "measured-overflow-results";
    measureEl.setAttribute("data-measure", JSON.stringify(measure));
    document.body.appendChild(measureEl);
  }, 1000);
}
