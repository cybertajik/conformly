/**
 * Type definitions for Conformly Customer Readiness Verification Workspace (MVP-E).
 * Strictly mirrors backend schemas in conformly.customer_demo.verification_schemas.
 */

export type VerificationStatus =
  | "ACTIVE"
  | "SUSPENDED"
  | "REVOKED"
  | "EXPIRED"
  | "SUPERSEDED";

export interface VerificationListSummary {
  id: string;
  preaudit_id: string;
  status: VerificationStatus;
  effective_status: VerificationStatus;
  revision: number;
  issued_at: string;
  valid_through: string;
  framework_display_name?: string | null;
  framework_version?: string | null;
  synthetic_marker: string;
}

export interface VerificationListResponse {
  verifications: VerificationListSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface VerificationDetail {
  id: string;
  preaudit_id: string;
  snapshot_id: string;
  status: VerificationStatus;
  effective_status: VerificationStatus;
  effective_reason?: string | null;
  revision: number;
  issued_at: string;
  valid_through: string;
  digest: string;
  current_event_id?: string | null;
  superseded_by_id?: string | null;
  supersedes_id?: string | null;
  synthetic_marker: string;
  test_qualification: string;
  limitations: string[];
  notes?: string | null;
  issuer_user_id: string;
  reviewer_user_id: string;
  approver_user_id: string;
  framework_display_name?: string | null;
  framework_version?: string | null;
  organization_display_name?: string | null;
  scope_summary?: Record<string, unknown> | null;
  replayed?: boolean;
  applied_event_id?: string | null;
  applied_revision?: number | null;
}

export interface VerificationProjection {
  verification_id: string;
  synthetic_marker: string;
  test_qualification: string;
  framework_display_name: string;
  framework_version: string;
  organization_display_name: string;
  scope_summary: Record<string, unknown>;
  controls_count: number;
  issued_at: string;
  valid_through: string;
  status: VerificationStatus;
  effective_status: VerificationStatus;
  effective_reason?: string | null;
  limitations: string[];
  superseded_by_id?: string | null;
  supersedes_id?: string | null;
}

export interface VerificationEventItem {
  id: string;
  sequence: number;
  revision: number;
  event_type: string;
  created_at: string;
  actor_user_id: string;
  operation_id?: string;
  reason?: string | null;
  notes?: string | null;
  payload_summary?: Record<string, unknown> | null;
}

export interface VerificationUncertainOp {
  operationId: string;
  action: "issue" | "suspend" | "revoke" | "correct" | "supersede";
  targetCaseId: string;
  targetVerificationId?: string;
  payload: unknown;
  label: string;
  errorText: string;
}

export interface VerificationHistoryResponse {
  verification_id: string;
  events: VerificationEventItem[];
}

export interface IssueVerificationPayload {
  operation_id: string;
  preaudit_id: string;
  expected_case_revision: number;
  snapshot_id: string;
  snapshot_digest: string;
  limitations?: string[];
  notes?: string;
}

export interface SuspendVerificationPayload {
  operation_id: string;
  expected_revision: number;
  reason: string;
}

export interface RevokeVerificationPayload {
  operation_id: string;
  expected_revision: number;
  reason: string;
}

export interface CorrectVerificationPayload {
  operation_id: string;
  expected_revision: number;
  correction_notes: string;
}

export interface SupersedeVerificationPayload {
  operation_id: string;
  expected_revision: number;
  new_preaudit_id: string;
  new_expected_case_revision: number;
  new_snapshot_id: string;
  new_snapshot_digest: string;
  limitations?: string[];
  notes?: string;
}

export interface ReconcileVerificationPayload {
  simulated_clock?: string;
}

export interface ReconcileVerificationResultItem {
  id: string;
  old_status: string;
  new_status: string;
  reason: string;
}

export interface ReconcileVerificationResponse {
  reconciled_count: number;
  results: ReconcileVerificationResultItem[];
}

