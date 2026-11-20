/**
 * TypeScript type definitions for MVP-B Customer Control Work and Evidence Pinning.
 */

export type LinkValidity =
  | "MISSING"
  | "AVAILABLE"
  | "NOT_YET_VALID"
  | "EXPIRED"
  | "QUARANTINED"
  | "UNAVAILABLE"
  | "UNVERIFIED";

export type ScanStatus = "SCANNED_AT_LINK" | "UNVERIFIED";

export type LinkReviewDecision = "PENDING" | "ACCEPTED" | "REJECTED";

export interface RequirementEvaluationResultSummary {
  requirement_id: string;
  requirement_version_id: string;
  requirement_identifier: string;
  requirement_title: string;
  result: "APPLICABLE" | "NOT_APPLICABLE" | "NEEDS_INFORMATION";
}

export interface ControlEvidenceLink {
  id: string;
  evidence_id: string;
  revision_number: number;
  digest: string;
  file_ids: string[];
  filename: string;
  file_size: number;
  classification: string;
  validity: LinkValidity;
  scan_status: ScanStatus;
  scan_verified_at: string | null;
  review: LinkReviewDecision;
  rationale: string;
  created_at: string;
}

export interface ControlWorkItem {
  id: string;
  adoption_id: string;
  control_id: string;
  control_version_id: string;
  title: string;
  provenance: string;
  pack_version: number;
  bundle_digest: string;
  requirement_results: RequirementEvaluationResultSummary[];
  owner_user_id: string | null;
  owner_display_name: string | null;
  due_date: string | null;
  version: number;
  is_current: boolean;
  is_stale: boolean;
  links: ControlEvidenceLink[];
}

export interface WorkListResponse {
  tenant_id: string;
  adoption_id: string | null;
  selection_revision: number;
  answer_revision: number;
  is_current: boolean;
  is_stale: boolean;
  items: ControlWorkItem[];
  total: number;
}

export interface OwnerDirectoryItem {
  user_id: string;
  display_name: string;
}

export interface OwnerDirectoryResponse {
  items: OwnerDirectoryItem[];
  total: number;
}

export interface MutationReceipt {
  operation_id: string;
  event_id: string;
  applied_work_version: number;
  replayed: boolean;
  current_work: ControlWorkItem;
}

export type EventType =
  | "INITIALIZED"
  | "OWNER_DUE_UPDATED"
  | "EVIDENCE_LINKED"
  | "EVIDENCE_REVIEWED";

export interface WorkEvent {
  revision: number;
  type: EventType;
  actor_id: string;
  time: string;
  link_id: string | null;
  decision: "ACCEPTED" | "REJECTED" | null;
  details: Record<string, unknown>;
}

export interface WorkHistoryResponse {
  tenant_id: string;
  work_id: string;
  items: WorkEvent[];
  total: number;
}

export interface InitializeWorkPayload {
  operation_id: string;
  adoption_id: string;
  expected_selection_revision: number;
  expected_answer_revision: number;
}

export interface PatchWorkPayload {
  operation_id: string;
  expected_selection_revision: number;
  expected_answer_revision: number;
  expected_work_version: number;
  owner_user_id: string | null;
  due_date: string | null;
}

export interface CreateEvidencePayload {
  operation_id: string;
  expected_selection_revision: number;
  expected_answer_revision: number;
  expected_work_version: number;
  file_id: string;
  valid_until: string | null;
  rationale: string;
}

export interface CreateLinkPayload {
  operation_id: string;
  expected_selection_revision: number;
  expected_answer_revision: number;
  expected_work_version: number;
  evidence_id: string;
  evidence_revision_number: number;
  evidence_revision_digest: string;
  rationale: string;
}

export interface CreateReviewPayload {
  operation_id: string;
  expected_selection_revision: number;
  expected_answer_revision: number;
  expected_work_version: number;
  decision: "ACCEPTED" | "REJECTED";
  rationale: string;
}
