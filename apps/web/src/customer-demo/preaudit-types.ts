/**
 * Type definitions for Conformly Customer Pre-audit Workspace (MVP-D).
 * Strictly mirrors backend schemas in conformly.customer_demo.preaudit_schemas.
 */

export type PreauditStatus =
  | "DRAFT"
  | "FROZEN"
  | "IN_REVIEW"
  | "CHANGES_REQUESTED"
  | "REVIEWED"
  | "APPROVED"
  | "CANCELLED";

export interface PreauditActor {
  user_id: string;
  display_name: string;
  email: string;
  role: string;
}

export interface PreauditActorsResponse {
  actors: PreauditActor[];
}

export interface PreauditBlocker {
  code: string;
  description: string;
  work_id?: string | null;
  control_code?: string | null;
}

export interface PreauditSnapshotSummary {
  id: string;
  kind: "SCOPE" | "REVIEW";
  sequence: number;
  digest: string;
  created_by_user_id: string;
  created_at: string;
}

export interface PreauditCaseSummary {
  id: string;
  tenant_id: string;
  adoption_id: string;
  pack_name: string;
  pack_version: string;
  lead_user_id: string;
  reviewer_user_id: string;
  status: PreauditStatus;
  revision: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface PreauditCaseDetail extends PreauditCaseSummary {
  lead_name: string;
  reviewer_name: string;
  current_scope_snapshot_id?: string | null;
  current_scope_snapshot_digest?: string | null;
  current_review_snapshot_id?: string | null;
  current_review_snapshot_digest?: string | null;
  is_scope_current: boolean;
  is_review_current: boolean;
  blockers: PreauditBlocker[];
  description?: string | null;
  replayed?: boolean;
  applied_event_id?: string | null;
  applied_revision?: number | null;
  applied_snapshot_id?: string | null;
}

export type PreauditCase = PreauditCaseDetail;

export interface PreauditListResponse {
  items: PreauditCaseSummary[];
  total: number;
  limit?: number;
  offset?: number;
}

export interface PreauditEvent {
  id: string;
  tenant_id: string;
  preaudit_id: string;
  revision: number;
  operation_id: string;
  event_type: string;
  actor_user_id: string;
  snapshot_id?: string | null;
  prior_status?: string | null;
  new_status: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface PreauditHistoryResponse {
  preaudit_id: string;
  events: PreauditEvent[];
}

export interface CreatePreauditPayload {
  operation_id: string;
  adoption_id: string;
  lead_user_id: string;
  reviewer_user_id: string;
  title?: string;
  description?: string;
}

export interface FreezeScopePayload {
  operation_id: string;
  expected_revision: number;
}

export interface SubmitReviewPayload {
  operation_id: string;
  expected_revision: number;
  submission_notes?: string;
}

export interface ReviewDecisionPayload {
  operation_id: string;
  expected_revision: number;
  snapshot_id: string;
  snapshot_digest: string;
  decision: "ACCEPT" | "REQUEST_CHANGES";
  notes: string;
}

export interface ApprovePreauditPayload {
  operation_id: string;
  expected_revision: number;
  snapshot_id: string;
  snapshot_digest: string;
  approval_notes?: string;
}

export interface CancelPreauditPayload {
  operation_id: string;
  expected_revision: number;
  reason: string;
}

export interface DownloadPreauditReportPayload {
  expected_revision: number;
  snapshot_id: string;
  expected_snapshot_digest: string;
}

export interface PreauditReportDownloadResult {
  blob: Blob;
  filename: string;
  preauditId: string;
  snapshotDigest: string;
  sha256?: string;
}

