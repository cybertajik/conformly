import React from "react";
import { createRoot } from "react-dom/client";
import { I18nProvider } from "../src/i18n/I18nContext";
import { AssessmentWorkspace } from "../src/customer-demo/AssessmentWorkspace";
import "../src/customer-demo/modern-workspace.css";
import {
  AssessmentHistoryResponse,
  AssessmentReceipt,
  AssessmentWorkItem,
  AssessmentWorkListResponse,
  Procedure,
  ReadinessSummary,
} from "../src/customer-demo/assessment-types";
import { ControlWorkItem, OwnerDirectoryItem, OwnerDirectoryResponse, WorkListResponse } from "../src/customer-demo/control-evidence-types";

// Strict dev guarding per contract
if (!import.meta.env.DEV) {
  throw new Error("UI fixture only available in dev mode");
}

const dummySummary: ReadinessSummary = {
  total_controls: 3,
  stale_work: 0,
  needs_information: 0,
  not_applicable: 0,
  unassessed: 1,
  unavailable_evidence: 0,
  stale_assessment: 0,
  insufficient_evidence: 0,
  fail: 1,
  partial: 0,
  pass_with_open_findings: 0,
  pass_count: 1,
  open_findings: 1,
  in_remediation_findings: 0,
  resolved_findings: 1,
  blocked_control_ids: ["c1111111-1111-4111-8111-111111111111"],
  reason_codes: ["OPEN_FINDINGS"],
};

const dummyProcedure: Procedure = {
  id: "p1111111-1111-4111-8111-111111111111",
  version: "1.0.0",
  digest: "f".repeat(64),
  criteria: [
    {
      id: "implementation",
      title: "Implementation Verification",
      description: "Verify cryptographic identity boundaries and zero-trust configuration.",
      sequence: 1,
    },
    {
      id: "evidence",
      title: "Evidence Validation",
      description: "Confirm uploaded configuration files contain valid cryptographic signatures.",
      sequence: 2,
    },
    {
      id: "operation",
      title: "Operational Effectiveness",
      description: "Inspect continuous automated reconciliation and alert escalation rules.",
      sequence: 3,
    },
  ],
  disclaimer: "Synthetic Evaluation Procedure — Human review required for synthetic readiness demonstration.",
};

const dummyControlWork: ControlWorkItem[] = [
  {
    id: "c1111111-1111-4111-8111-111111111111",
    adoption_id: "ad111111-1111-4111-8111-111111111111",
    control_id: "ctrl-iam-policy",
    control_version_id: "cv111111-1111-4111-8111-111111111111",
    title: "Access Control & Authentication Policy",
    provenance: "Synthetic Security Standard",
    pack_version: 1,
    bundle_digest: "a".repeat(64),
    requirement_results: [
      {
        requirement_id: "req-1",
        requirement_version_id: "rv111111-1111-4111-8111-111111111111",
        requirement_identifier: "REQ-1.1",
        requirement_title: "Administrative Access Authentication",
        result: "APPLICABLE" as const,
      },
    ],
    owner_user_id: "u1111111-1111-4111-8111-111111111111",
    owner_display_name: "Security Lead",
    due_date: "2026-11-15",
    version: 1,
    is_current: true,
    is_stale: false,
    links: [
      {
        id: "l1111111-1111-4111-8111-111111111111",
        evidence_id: "ev111111-1111-4111-8111-111111111111",
        revision_number: 1,
        digest: "b".repeat(64),
        file_ids: ["f1111111-1111-4111-8111-111111111111"],
        filename: "iam_access_policy.pdf",
        file_size: 1024,
        classification: "CONFIDENTIAL",
        validity: "AVAILABLE",
        scan_status: "SCANNED_AT_LINK",
        scan_verified_at: "2026-10-25T08:00:00Z",
        review: "ACCEPTED",
        rationale: "Approved",
        created_at: "2026-10-25T08:00:00Z",
      },
    ],
  },
  {
    id: "c2222222-2222-4222-8222-222222222222",
    adoption_id: "ad111111-1111-4111-8111-111111111111",
    control_id: "ctrl-data-encryption",
    control_version_id: "cv222222-2222-4222-8222-222222222222",
    title: "Data Encryption & Key Management",
    provenance: "Synthetic Security Standard",
    pack_version: 1,
    bundle_digest: "c".repeat(64),
    requirement_results: [],
    owner_user_id: "u2222222-2222-4222-8222-222222222222",
    owner_display_name: "Compliance Officer",
    due_date: "2026-11-30",
    version: 1,
    is_current: true,
    is_stale: false,
    links: [
      {
        id: "l2222222-2222-4222-8222-222222222222",
        evidence_id: "ev222222-2222-4222-8222-222222222222",
        revision_number: 1,
        digest: "d".repeat(64),
        file_ids: ["f2222222-2222-4222-8222-222222222222"],
        filename: "kms_encryption_config.json",
        file_size: 2048,
        classification: "CONFIDENTIAL",
        validity: "AVAILABLE",
        scan_status: "SCANNED_AT_LINK",
        scan_verified_at: "2026-10-25T08:15:00Z",
        review: "ACCEPTED",
        rationale: "Approved",
        created_at: "2026-10-25T08:15:00Z",
      },
    ],
  },
  {
    id: "c3333333-3333-4333-8333-333333333333",
    adoption_id: "ad111111-1111-4111-8111-111111111111",
    control_id: "ctrl-audit-logging",
    control_version_id: "cv333333-3333-4333-8333-333333333333",
    title: "Audit Logging & Incident Response",
    provenance: "Synthetic Security Standard",
    pack_version: 1,
    bundle_digest: "e".repeat(64),
    requirement_results: [],
    owner_user_id: null,
    owner_display_name: null,
    due_date: null,
    version: 1,
    is_current: true,
    is_stale: false,
    links: [],
  },
];

const dummyOwners: OwnerDirectoryItem[] = [
  { user_id: "u1111111-1111-4111-8111-111111111111", display_name: "Security Lead" },
  { user_id: "u2222222-2222-4222-8222-222222222222", display_name: "Compliance Officer" },
];

const dummyItems: AssessmentWorkItem[] = [
  {
    work_id: "c1111111-1111-4111-8111-111111111111",
    control_version_id: "cv111111-1111-4111-8111-111111111111",
    work_version: 1,
    assessment_revision: 1,
    procedure: dummyProcedure,
    latest_assessment: {
      event_id: "e1111111-1111-4111-8111-111111111111",
      revision: 1,
      result: "FAIL",
      actor_id: "u1111111-1111-4111-8111-111111111111",
      created_at: "2026-10-25T08:00:00Z",
      rationale: "IAM policy lacked explicit multi-factor authentication requirement for administrative access.",
      criterion_results: [
        { criterion_id: "implementation", result: "FAIL", notes: "MFA not enforced" },
        { criterion_id: "evidence", result: "PASS", notes: null },
        { criterion_id: "operation", result: "PASS", notes: null },
      ],
      evidence_pins: [],
      is_stale: false,
      stale_reasons: [],
    },
    primary_state: "FAIL",
    blockers: ["OPEN_FINDINGS"],
    findings: [
      {
        id: "f1111111-1111-4111-8111-111111111111",
        source_event_id: "e1111111-1111-4111-8111-111111111111",
        current_event_id: "e1111111-1111-4111-8111-111111111111",
        severity: "HIGH",
        status: "OPEN",
        owner_user_id: "u1111111-1111-4111-8111-111111111111",
        owner_display_name: "Security Lead",
        due_date: "2026-11-15",
        version: 1,
        created_at: "2026-10-25T08:00:00Z",
        updated_at: "2026-10-25T08:00:00Z",
      },
    ],
    history: [
      {
        event_id: "e1111111-1111-4111-8111-111111111111",
        revision: 1,
        operation_id: "op111111-1111-4111-8111-111111111111",
        event_type: "ASSESSMENT",
        result: "FAIL",
        observed_work_version: 1,
        actor_id: "u1111111-1111-4111-8111-111111111111",
        created_at: "2026-10-25T08:00:00Z",
        details: { rationale: "IAM policy lacked explicit multi-factor authentication" },
      },
    ],
    requirement_results: [{ requirement_id: "req-1", status: "APPLICABLE" }],
  },
  {
    work_id: "c2222222-2222-4222-8222-222222222222",
    control_version_id: "cv222222-2222-4222-8222-222222222222",
    work_version: 1,
    assessment_revision: 1,
    procedure: dummyProcedure,
    latest_assessment: {
      event_id: "e2222222-2222-4222-8222-222222222222",
      revision: 1,
      result: "PASS",
      actor_id: "u2222222-2222-4222-8222-222222222222",
      created_at: "2026-10-25T08:15:00Z",
      rationale: "All cryptographic keys rotated and enforced with AES-256-GCM envelope encryption.",
      criterion_results: [
        { criterion_id: "implementation", result: "PASS", notes: null },
        { criterion_id: "evidence", result: "PASS", notes: null },
        { criterion_id: "operation", result: "PASS", notes: null },
      ],
      evidence_pins: [],
      is_stale: false,
      stale_reasons: [],
    },
    primary_state: "PASS",
    blockers: [],
    findings: [],
    history: [],
    requirement_results: [],
  },
  {
    work_id: "c3333333-3333-4333-8333-333333333333",
    control_version_id: "cv333333-3333-4333-8333-333333333333",
    work_version: 1,
    assessment_revision: 0,
    procedure: dummyProcedure,
    latest_assessment: null,
    primary_state: "UNASSESSED",
    blockers: [],
    findings: [],
    history: [],
    requirement_results: [],
  },
];

const dummyHistory: AssessmentHistoryResponse = {
  work_id: "c1111111-1111-4111-8111-111111111111",
  total: 1,
  items: dummyItems[0].history,
};

// Install synthetic fetch interceptor matching contracted endpoints
const originalFetch = window.fetch;
window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;

  // Assessment Work Procedure
  if (url.includes("/customer-demo/assessment-work/") && url.includes("/procedure")) {
    return new Response(JSON.stringify(dummyProcedure), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Assessment Work History
  if (url.includes("/customer-demo/assessment-work/") && url.includes("/history")) {
    return new Response(JSON.stringify(dummyHistory), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Record Assessment
  if (url.includes("/customer-demo/assessment-work/") && url.endsWith("/assessments")) {
    const receipt: AssessmentReceipt = {
      operation_id: "op-assess-live",
      event_id: "e-assess-live",
      applied_revision: 2,
      replayed: false,
      current_item: {
        ...dummyItems[0],
        assessment_revision: 2,
        primary_state: "PASS",
        findings: [],
      },
      summary: {
        ...dummySummary,
        fail: 0,
        pass_count: 2,
        open_findings: 0,
      },
    };
    return new Response(JSON.stringify(receipt), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Update Finding (Remediation)
  if (url.includes("/customer-demo/assessment-work/findings/")) {
    const receipt: AssessmentReceipt = {
      operation_id: "op-finding-live",
      event_id: "e-finding-live",
      applied_revision: 2,
      replayed: false,
      current_item: dummyItems[0],
      summary: dummySummary,
    };
    return new Response(JSON.stringify(receipt), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Record Retest
  if (url.includes("/customer-demo/assessment-work/") && url.endsWith("/retests")) {
    const receipt: AssessmentReceipt = {
      operation_id: "op-retest-live",
      event_id: "e-retest-live",
      applied_revision: 2,
      replayed: false,
      current_item: {
        ...dummyItems[0],
        assessment_revision: 2,
        primary_state: "PASS",
        findings: [],
      },
      summary: {
        ...dummySummary,
        fail: 0,
        pass_count: 2,
        open_findings: 0,
        resolved_findings: 2,
      },
    };
    return new Response(JSON.stringify(receipt), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Assessment Work List
  if (url.includes("/customer-demo/assessment-work")) {
    const resp: AssessmentWorkListResponse = {
      tenant_id: "11111111-1111-4111-8111-111111111111",
      adoption_id: "ad111111-1111-4111-8111-111111111111",
      answer_revision: 1,
      selection_revision: 1,
      is_stale: false,
      summary: dummySummary,
      items: dummyItems,
    };
    return new Response(JSON.stringify(resp), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Control Work List (B integration)
  if (url.includes("/customer-demo/control-work/owners")) {
    const resp: OwnerDirectoryResponse = {
      items: dummyOwners,
      total: dummyOwners.length,
    };
    return new Response(JSON.stringify(resp), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  if (url.includes("/customer-demo/control-work")) {
    const resp: WorkListResponse = {
      tenant_id: "11111111-1111-4111-8111-111111111111",
      adoption_id: "ad111111-1111-4111-8111-111111111111",
      selection_revision: 1,
      answer_revision: 1,
      is_current: true,
      is_stale: false,
      items: dummyControlWork,
      total: dummyControlWork.length,
    };
    return new Response(JSON.stringify(resp), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  throw new Error(`Unexpected unhandled fixture fetch to ${url}`);
};

const rootEl = document.getElementById("preview-root");
if (rootEl) {
  createRoot(rootEl).render(
    <React.StrictMode>
      <I18nProvider>
        <div className="modern-workspace-root" style={{ maxWidth: 1200, margin: "0 auto", padding: "1.5rem" }}>
          <div className="mw-alert-banner notice" style={{ marginBottom: "1rem" }}>
            Synthetic customer onboarding demonstration. Not legal or compliance advice.
          </div>
          <AssessmentWorkspace
            tenantId="11111111-1111-4111-8111-111111111111"
            token="synthetic-preview-token"
            selectionRevision={1}
            answerRevision={1}
            hasUnsavedParentEdits={false}
            isAdoptionStale={false}
          />
        </div>
      </I18nProvider>
    </React.StrictMode>
  );
}
