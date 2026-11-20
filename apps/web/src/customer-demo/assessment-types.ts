/**
 * TypeScript type definitions for MVP-C Customer Assessment, Remediation, and Audit Readiness.
 */

export type AssessmentPrimaryState =
  | "STALE_WORK"
  | "NEEDS_INFORMATION"
  | "NOT_APPLICABLE"
  | "UNASSESSED"
  | "UNAVAILABLE_EVIDENCE"
  | "STALE_ASSESSMENT"
  | "INSUFFICIENT_EVIDENCE"
  | "FAIL"
  | "PARTIAL"
  | "PASS_WITH_OPEN_FINDINGS"
  | "PASS";

export type AssessmentResult = "PASS" | "PARTIAL" | "FAIL" | "INSUFFICIENT_EVIDENCE";

export type CriterionResult = "PASS" | "PARTIAL" | "FAIL" | "NOT_APPLICABLE";

export type FindingSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type FindingStatus = "OPEN" | "IN_REMEDIATION" | "RESOLVED";

export interface ProcedureCriterion {
  id: string;
  title: string;
  description: string;
  sequence: number;
}

export interface Procedure {
  id: string;
  version: string;
  digest: string;
  criteria: ProcedureCriterion[];
  disclaimer: string;
}

export interface AssessmentFinding {
  id: string;
  source_event_id: string;
  current_event_id: string;
  severity: FindingSeverity;
  status: FindingStatus;
  owner_user_id: string | null;
  owner_display_name?: string | null;
  due_date: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface CriterionResultItem {
  criterion_id: string;
  result: CriterionResult;
  notes?: string | null;
}

export interface PinnedEvidenceItem {
  link_id: string;
  evidence_id: string;
  revision_number: number;
  revision_digest: string;
  latest_review_event_id: string;
  file_id: string;
  file_hash: string;
  scan_verified: boolean;
  quarantine_cleared: boolean;
  validity: string;
  review: string;
}

export interface LatestAssessment {
  event_id: string;
  revision: number;
  result: AssessmentResult;
  actor_id: string;
  created_at: string;
  rationale: string;
  criterion_results: CriterionResultItem[];
  evidence_pins: PinnedEvidenceItem[];
  is_stale: boolean;
  stale_reasons: string[];
}

export interface AssessmentEvent {
  event_id: string;
  revision: number;
  operation_id: string;
  event_type: "ASSESSMENT" | "RETEST" | "FINDING_UPDATED" | string;
  result?: string | null;
  observed_work_version: number;
  actor_id: string;
  created_at: string;
  details: Record<string, unknown>;
}

export interface AssessmentWorkItem {
  work_id: string;
  control_version_id: string;
  work_version: number;
  assessment_revision: number;
  procedure: Procedure;
  latest_assessment: LatestAssessment | null;
  primary_state: AssessmentPrimaryState;
  blockers: string[];
  findings: AssessmentFinding[];
  history: AssessmentEvent[];
  requirement_results?: Array<Record<string, unknown>>;
}

export interface ReadinessSummary {
  total_controls: number;
  stale_work: number;
  needs_information: number;
  not_applicable: number;
  unassessed: number;
  unavailable_evidence: number;
  stale_assessment: number;
  insufficient_evidence: number;
  fail: number;
  partial: number;
  pass_with_open_findings: number;
  pass_count: number;
  open_findings: number;
  in_remediation_findings: number;
  resolved_findings: number;
  blocked_control_ids: string[];
  reason_codes: string[];
}

export interface AssessmentWorkListResponse {
  tenant_id: string;
  adoption_id: string | null;
  answer_revision: number;
  selection_revision: number;
  is_stale: boolean;
  summary: ReadinessSummary;
  items: AssessmentWorkItem[];
}

export interface AssessmentHistoryResponse {
  work_id: string;
  total: number;
  limit?: number;
  offset?: number;
  items: AssessmentEvent[];
}

export interface AssessmentCreatePayload {
  operation_id: string;
  expected_answer_revision: number;
  expected_selection_revision: number;
  expected_work_version: number;
  expected_assessment_revision: number;
  procedure_id: string;
  procedure_version: string;
  procedure_digest: string;
  evidence_link_ids: string[];
  criterion_results: CriterionResultItem[];
  result: "PASS" | "PARTIAL" | "FAIL" | "INSUFFICIENT_EVIDENCE";
  rationale: string;
  finding?: {
    severity: FindingSeverity;
    owner_user_id: string | null;
    due_date: string | null;
  } | null;
}

export interface FindingPatchPayload {
  operation_id: string;
  expected_answer_revision: number;
  expected_selection_revision: number;
  expected_work_version: number;
  expected_assessment_revision: number;
  expected_finding_version: number;
  severity: FindingSeverity;
  owner_user_id: string | null;
  due_date: string | null;
  status: "OPEN" | "IN_REMEDIATION";
  remediation_note: string;
}

export interface RetestCreatePayload {
  operation_id: string;
  expected_answer_revision: number;
  expected_selection_revision: number;
  expected_work_version: number;
  expected_assessment_revision: number;
  procedure_id: string;
  procedure_version: string;
  procedure_digest: string;
  evidence_link_ids: string[];
  criterion_results: CriterionResultItem[];
  result: "PASS" | "PARTIAL" | "FAIL" | "INSUFFICIENT_EVIDENCE";
  rationale: string;
  findings: Array<{
    id: string;
    expected_version: number;
  }>;
}

export interface AssessmentReceipt {
  operation_id: string;
  event_id: string;
  applied_revision: number;
  replayed: boolean;
  current_item: AssessmentWorkItem;
  summary: ReadinessSummary;
}
