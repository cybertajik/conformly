/**
 * Type definitions for Tasks, Review Calendar, and Background Job Visibility.
 * Conforms strictly to existing backend models in `conformly.compliance.models` and `conformly.api.jobs`.
 */

export type TaskStatus = "pending" | "in_progress" | "completed" | "overdue" | "cancelled";
export type TaskPriority = "low" | "medium" | "high" | "critical";

export interface ComplianceTask {
  id: string;
  tenant_id: string;
  title: string;
  description: string;
  due_date: string;
  status: TaskStatus;
  priority: TaskPriority;
  assignee_user_id: string | null;
  control_type?: string | null;
  control_id?: string | null;
  evidence_id?: string | null;
  policy_id?: string | null;
  version: number;
  completed_at: string | null;
  completed_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateTaskInput {
  title: string;
  description: string;
  due_date: string;
  priority?: TaskPriority;
  assignee_user_id?: string | null;
  control_type?: string | null;
  control_id?: string | null;
  evidence_id?: string | null;
  policy_id?: string | null;
}

export interface UpdateTaskInput {
  expected_version: number;
  title?: string;
  description?: string;
  due_date?: string;
  priority?: TaskPriority;
  assignee_user_id?: string | null;
  status?: TaskStatus;
}

export interface CompleteTaskInput {
  expected_version: number;
}

export interface TaskFilterOptions {
  status?: TaskStatus | "all";
  priority?: TaskPriority | "all";
  searchQuery?: string;
  limit?: number;
  offset?: number;
}

// ── Job Visibility Models (Read-Only) ──────────────────────────────────────────

export interface FailedJobItem {
  id?: string;
  job_id?: string;
  kind?: string;
  job_name?: string;
  attempts: number;
  error_code: string | null;
  created_at?: string;
  updated_at?: string;
  failed_at?: string;
}

export interface FailedJobsResponse {
  tenant_id?: string;
  total_pending?: number;
  total_processing?: number;
  total_delivered?: number;
  total_failed: number;
  recent_failures: FailedJobItem[];
}

export interface OutboxMessageResponse {
  id: string;
  tenant_id: string;
  kind?: string;
  message_type?: string;
  idempotency_key?: string;
  state: string; // "pending" | "processing" | "delivered" | "failed" | "dead_letter"
  attempts: number;
  available_at?: string;
  delivered_at?: string | null;
  error_code?: string | null;
  last_attempt_at?: string | null;
  created_at: string;
  updated_at: string;
}

export type OutboxMessageItem = OutboxMessageResponse;

// ── Review Calendar Models ───────────────────────────────────────────────────

export type ReviewSourceKind = "policy" | "risk" | "asset" | "vendor" | "task";

export interface ReviewCalendarItem {
  id: string;
  title: string;
  sourceKind: ReviewSourceKind;
  sourceId: string;
  targetDate: string; // ISO date-time string
  status: string;
  isActionable: boolean;
  moduleTab: string; // "policies" | "risks" | "assets" | "vendors" | "tasks"
}

export type ReviewCalendarBucket = "overdue" | "today" | "next7" | "next30" | "all";
