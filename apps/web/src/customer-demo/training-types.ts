/**
 * Type definitions for Conformly Training & LMS Management Integration.
 * Conforms strictly to backend models and contract in conformly.lms.api / conformly.lms.models.
 */

export type TrainingSubTab = "assignments" | "courses" | "completions";

export type AssignmentStatusType = "assigned" | "in_progress" | "completed" | "overdue";

export interface TrainingCourse {
  id: string;
  tenant_id: string;
  course_id: string;
  version: string;
  title: string;
  description: string;
  provider: string;
  duration_minutes: number;
  validity_period_days: number;
  is_active: boolean;
  created_at: string;
}

export interface CreateCoursePayload {
  course_id: string;
  title: string;
  description: string;
  version?: string;
  provider?: string;
  duration_minutes?: number;
  validity_period_days?: number;
}

export interface TrainingAssignment {
  id: string;
  tenant_id: string;
  course_id: string;
  user_id?: string | null;
  workforce_email: string;
  due_date: string;
  status: AssignmentStatusType | string;
  control_id?: string | null;
  control_type?: string | null;
  created_at: string;
}

export interface CreateAssignmentPayload {
  course_id: string;
  workforce_email: string;
  due_date: string;
  user_id?: string | null;
  control_id?: string | null;
  control_type?: string | null;
}

export interface TrainingCompletion {
  id: string;
  tenant_id: string;
  assignment_id?: string | null;
  course_id: string;
  course_version: string;
  user_id?: string | null;
  workforce_email: string;
  completed_at: string;
  score?: number | null;
  certificate_id?: string | null;
  evidence_id?: string | null;
  idempotency_key: string;
  verified_via: string;
  created_at: string;
}

export interface PartnerConnectionStatus {
  mode: "contract_simulation" | "connected" | "disconnected";
  providerName: string;
  description: string;
  lastSyncAt: string | null;
}

