export const DATA_CLASSIFICATIONS = [
  "Public",
  "Internal",
  "Confidential",
  "Restricted",
] as const;

export type DataClassification = (typeof DATA_CLASSIFICATIONS)[number];

export const TENANT_ROLES = [
  "owner",
  "administrator",
  "compliance_manager",
  "auditor",
  "contributor",
  "viewer",
] as const;

export type TenantRole = (typeof TENANT_ROLES)[number];

export interface SessionIdentity {
  user_id: string;
  email: string;
  display_name: string;
}

export interface TenantMembershipSummary {
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  role: TenantRole;
}

export interface TenantContext {
  tenant_id: string;
  role: TenantRole;
}

export interface StoredFileSummary {
  id: string;
  tenant_id: string;
  created_by_user_id: string;
  original_filename: string;
  content_type: string;
  classification: DataClassification;
  plaintext_size_bytes: number;
  plaintext_sha256: string;
  created_at: string;
}

export type ReleaseState = "draft" | "in_review" | "approved" | "released" | "retired";
export type AdoptionStatus = "active" | "superseded" | "archived";
export type OverlayApplicability = "applicable" | "not_applicable" | "scoped_out";
export type CustomControlStatus = "active" | "deprecated";
export type MappingType = "satisfies" | "partially_satisfies" | "related";
export type ControlEntityType = "canonical" | "custom";

export interface CanonicalControlSummary {
  id: string;
  framework_version_id: string;
  identifier: string;
  title: string;
  description: string;
  category: string;
  guidance?: string | null;
  sort_order: number;
  created_at: string;
}

export interface FrameworkVersionSummary {
  id: string;
  framework_id: string;
  version: string;
  release_state: ReleaseState;
  release_notes?: string | null;
  created_by_user_id: string;
  legal_reviewed_by_user_id?: string | null;
  legal_reviewed_at?: string | null;
  approved_by_user_id?: string | null;
  approved_at?: string | null;
  released_at?: string | null;
  retired_at?: string | null;
  created_at: string;
  controls?: CanonicalControlSummary[];
}

export interface FrameworkSummary {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
  versions?: FrameworkVersionSummary[];
}

export interface TenantFrameworkAdoptionSummary {
  id: string;
  tenant_id: string;
  framework_id: string;
  framework_version_id: string;
  status: AdoptionStatus;
  adopted_at: string;
  adopted_by_user_id: string;
  impact_analysis_acknowledged_at?: string | null;
  impact_summary?: Record<string, unknown> | null;
}

export interface TenantControlOverlaySummary {
  id: string;
  tenant_id: string;
  adoption_id: string;
  canonical_control_id: string;
  applicability: OverlayApplicability;
  justification?: string | null;
  internal_notes?: string | null;
  custom_guidance?: string | null;
  created_at: string;
}

export interface CustomControlSummary {
  id: string;
  tenant_id: string;
  identifier: string;
  title: string;
  description: string;
  category: string;
  guidance?: string | null;
  status: CustomControlStatus;
  created_at: string;
}

export interface ControlMappingSummary {
  id: string;
  tenant_id: string;
  source_type: ControlEntityType;
  source_control_id: string;
  target_type: ControlEntityType;
  target_control_id: string;
  mapping_type: MappingType;
  rationale?: string | null;
  created_at: string;
}

export interface ImpactReportSummary {
  framework_id: string;
  source_version_id: string;
  source_version_string: string;
  target_version_id: string;
  target_version_string: string;
  total_source_controls: number;
  total_target_controls: number;
  added_controls: Array<{
    id: string;
    identifier: string;
    title: string;
    category: string;
    description: string;
    guidance?: string | null;
  }>;
  removed_controls: Array<{
    id: string;
    identifier: string;
    title: string;
    category: string;
    description: string;
    guidance?: string | null;
  }>;
  modified_controls: Array<{
    identifier: string;
    source_title: string;
    target_title: string;
    source_category: string;
    target_category: string;
    changed_fields: string[];
    field_diffs: Array<{
      field_name: string;
      source_value?: string | null;
      target_value?: string | null;
    }>;
  }>;
  unchanged_count: number;
  tenant_warnings: Array<{
    severity: string;
    control_identifier: string;
    item_type: string;
    message: string;
    recommendation: string;
  }>;
  overall_impact_level: string;
}

export type EvidenceStatus = "draft" | "submitted" | "valid" | "expired" | "rejected" | "archived";
export type PolicyStatus = "draft" | "in_review" | "approved" | "published" | "archived";
export type TaskStatus = "pending" | "in_progress" | "completed" | "overdue" | "cancelled";
export type TaskPriority = "low" | "medium" | "high" | "critical";
export type FindingSeverity = "low" | "medium" | "high" | "critical";
export type RemediationStatus = "open" | "in_remediation" | "resolved" | "accepted_risk";
export type ControlImplementationStatus = "not_started" | "in_progress" | "implemented" | "assessed";
export type DigestFrequency = "immediate" | "daily" | "weekly" | "never";

export interface EvidenceFileLinkSummary {
  id: string;
  evidence_id: string;
  file_id: string;
  attached_by_user_id: string;
  created_at: string;
}

export interface EvidenceControlLinkSummary {
  id: string;
  evidence_id: string;
  control_type: ControlEntityType;
  control_id: string;
  linked_by_user_id: string;
  created_at: string;
}

export interface EvidenceItemSummary {
  id: string;
  tenant_id: string;
  title: string;
  description: string;
  classification: DataClassification;
  status: EvidenceStatus;
  owner_user_id: string;
  valid_from?: string | null;
  valid_until?: string | null;
  version: number;
  restricted_notes?: string | null;
  file_links?: EvidenceFileLinkSummary[];
  control_links?: EvidenceControlLinkSummary[];
  created_at: string;
  updated_at: string;
}

export interface PolicyControlLinkSummary {
  id: string;
  policy_id: string;
  control_type: ControlEntityType;
  control_id: string;
  linked_by_user_id: string;
  created_at: string;
}

export interface PolicySummary {
  id: string;
  tenant_id: string;
  title: string;
  description: string;
  version_string: string;
  status: PolicyStatus;
  owner_user_id: string;
  approved_by_user_id?: string | null;
  approved_at?: string | null;
  review_cycle_days: number;
  next_review_due?: string | null;
  version: number;
  content?: string | null;
  classification: DataClassification;
  restricted_content?: string | null;
  control_links?: PolicyControlLinkSummary[];
  created_at: string;
  updated_at: string;
}

export interface ComplianceTaskSummary {
  id: string;
  tenant_id: string;
  title: string;
  description: string;
  due_date: string;
  status: TaskStatus;
  priority: TaskPriority;
  assignee_user_id?: string | null;
  control_type?: ControlEntityType | null;
  control_id?: string | null;
  evidence_id?: string | null;
  policy_id?: string | null;
  version: number;
  completed_at?: string | null;
  completed_by_user_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface FindingSummary {
  id: string;
  tenant_id: string;
  title: string;
  description: string;
  severity: FindingSeverity;
  remediation_status: RemediationStatus;
  due_date?: string | null;
  owner_user_id?: string | null;
  control_type?: ControlEntityType | null;
  control_id?: string | null;
  remediation_plan?: string | null;
  remediation_summary?: string | null;
  resolved_at?: string | null;
  resolved_by_user_id?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ControlStatusRecordSummary {
  id: string;
  tenant_id: string;
  control_type: ControlEntityType;
  control_id: string;
  status: ControlImplementationStatus;
  assigned_owner_user_id?: string | null;
  notes?: string | null;
  last_assessed_at?: string | null;
  assessed_by_user_id?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface UserNotificationPreferenceSummary {
  id: string;
  tenant_id: string;
  user_id: string;
  email_enabled: boolean;
  digest_frequency: DigestFrequency;
  notify_task_assigned: boolean;
  notify_task_due: boolean;
  notify_evidence_expired: boolean;
  notify_policy_review: boolean;
  notify_finding_raised: boolean;
  created_at: string;
  updated_at: string;
}

export interface JobExecutionSummary {
  expired_evidence: { processed_count: number; alerts_enqueued: number };
  overdue_tasks: { processed_count: number; alerts_enqueued: number };
  policy_alerts: { processed_count: number; alerts_enqueued: number };
}

// ---------------------------------------------------------------------------
// Phase 6 — Pre-Audit
// ---------------------------------------------------------------------------

export type PreAuditStatus =
  | "planning"
  | "in_progress"
  | "in_review"
  | "completed"
  | "cancelled";

export type PreAuditCheckResult = "pass" | "fail" | "not_applicable" | "pending";

export type CertificateStatus = "active" | "expired" | "revoked";

export interface PreAuditScopeSummary {
  id: string;
  tenant_id: string;
  pre_audit_id: string;
  framework_version_id: string;
  control_count: number;
  checked_count: number;
  created_at: string;
}

export interface PreAuditCheckSummary {
  id: string;
  tenant_id: string;
  scope_id: string;
  control_type: ControlEntityType;
  control_id: string;
  result: PreAuditCheckResult;
  rule_version: string;
  evidence_count: number;
  policy_count: number;
  open_findings_count: number;
  implementation_status: ControlImplementationStatus | null;
  score: number;
  evaluated_at: string;
  created_at: string;
}

export interface PreAuditFindingSummary {
  id: string;
  tenant_id: string;
  pre_audit_id: string;
  check_id: string | null;
  title: string;
  description: string;
  severity: FindingSeverity;
  recommendation: string | null;
  remediation_status: RemediationStatus;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface PreAuditReportSummary {
  id: string;
  tenant_id: string;
  pre_audit_id: string;
  file_id: string;
  report_type: string;
  rule_version: string;
  generated_at: string;
  created_at: string;
}

export interface PreAuditManifestSummary {
  id: string;
  tenant_id: string;
  pre_audit_id: string;
  file_id: string;
  manifest_hash_sha256: string;
  record_count: number;
  rule_version: string;
  generated_at: string;
  created_at: string;
}

export interface PreAuditCertificateSummary {
  id: string;
  tenant_id: string;
  pre_audit_id: string;
  certificate_number: string;
  status: CertificateStatus;
  issued_at: string;
  expires_at: string;
  revoked_at: string | null;
  revoked_reason: string | null;
  created_at: string;
}

export interface ReadinessScoreSummary {
  overall_score: number;
  total_checks: number;
  passed_checks: number;
  failed_checks: number;
  not_applicable_checks: number;
  pending_checks: number;
  open_findings: number;
}

export interface PreAuditSummary {
  id: string;
  tenant_id: string;
  title: string;
  description: string;
  status: PreAuditStatus;
  framework_adoption_id: string;
  lead_user_id: string;
  reviewer_user_id: string | null;
  reviewed_at: string | null;
  rule_version: string;
  overall_score: number | null;
  version: number;
  scopes?: PreAuditScopeSummary[];
  checks?: PreAuditCheckSummary[];
  findings?: PreAuditFindingSummary[];
  reports?: PreAuditReportSummary[];
  manifests?: PreAuditManifestSummary[];
  certificates?: PreAuditCertificateSummary[];
  score_summary?: ReadinessScoreSummary;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Phase 7 — Whistleblower
// ---------------------------------------------------------------------------

export type WhistleblowerCaseStatus =
  | "submitted"
  | "acknowledged"
  | "under_investigation"
  | "resolved"
  | "dismissed";

export type WhistleblowerMessageSender = "reporter" | "handler";

export interface WhistleblowerPortalSummary {
  id: string;
  tenant_id: string;
  slug: string;
  title: string;
  welcome_text: string;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface WhistleblowerMessageSummary {
  id: string;
  tenant_id: string;
  case_id: string;
  sender_type: WhistleblowerMessageSender;
  body: string;
  sent_by_user_id?: string | null;
  created_at: string;
}

export interface WhistleblowerAttachmentSummary {
  id: string;
  tenant_id: string;
  case_id: string;
  message_id?: string | null;
  file_id: string;
  uploaded_by: WhistleblowerMessageSender;
  original_filename: string;
  created_at: string;
}

export interface WhistleblowerCaseAssignmentSummary {
  id: string;
  tenant_id: string;
  case_id: string;
  handler_user_id: string;
  assigned_by_user_id: string;
  assigned_at: string;
}

export interface WhistleblowerCaseSummary {
  id: string;
  tenant_id: string;
  portal_id: string;
  public_case_id: string;
  status: WhistleblowerCaseStatus;
  category: string;
  title: string;
  summary?: string | null;
  closed_at?: string | null;
  closed_reason?: string | null;
  version: number;
  messages_count?: number;
  messages?: WhistleblowerMessageSummary[];
  assignments?: WhistleblowerCaseAssignmentSummary[];
  created_at: string;
  updated_at: string;
}

export interface WhistleblowerPublicCaseSummary {
  public_case_id: string;
  status: WhistleblowerCaseStatus;
  category: string;
  title: string;
  closed_at?: string | null;
  created_at: string;
  messages: WhistleblowerMessageSummary[];
}

export interface WhistleblowerSubmissionResult {
  public_case_id: string;
  return_secret: string;
  portal_title: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Phase 8 — Public Profiles
// ---------------------------------------------------------------------------

export type PublicCredentialType = "conformly_readiness" | "third_party";
export type PublicCredentialStatus = "active" | "expired" | "revoked";

export interface PublicProfileSummary {
  id: string;
  tenant_id: string;
  slug: string;
  display_name: string;
  description?: string | null;
  logo_url?: string | null;
  website_url?: string | null;
  primary_contact_email?: string | null;
  is_published: boolean;
  published_at?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface PublicCredentialSummary {
  id: string;
  profile_id: string;
  tenant_id: string;
  credential_type: PublicCredentialType;
  title: string;
  issuer_name: string;
  scope_description: string;
  issued_at: string;
  valid_until?: string | null;
  status: PublicCredentialStatus;
  verification_url?: string | null;
  source_certificate_id?: string | null;
  is_publicly_visible: boolean;
  display_order: number;
  created_at: string;
  updated_at: string;
}

export interface PublicStatementSummary {
  id: string;
  profile_id: string;
  tenant_id: string;
  title: string;
  statement_content: string;
  display_order: number;
  is_publicly_visible: boolean;
  created_at: string;
  updated_at: string;
}

export interface PublicProfileView {
  id: string;
  slug: string;
  display_name: string;
  description?: string | null;
  logo_url?: string | null;
  website_url?: string | null;
  primary_contact_email?: string | null;
  published_at: string;
  credentials: PublicCredentialSummary[];
  statements: PublicStatementSummary[];
  conformly_verified: boolean;
  disclaimer: string;
}

export interface PublicProfileDetailSummary extends PublicProfileSummary {
  credentials: PublicCredentialSummary[];
  statements: PublicStatementSummary[];
}

// ---------------------------------------------------------------------------
// Phase 9: Export, Retention & Deletion Lifecycle
// ---------------------------------------------------------------------------

export const TENANT_STATUSES = [
  "active",
  "cancelling",
  "suspended",
  "deleted",
] as const;
export type TenantStatus = (typeof TENANT_STATUSES)[number];

export const EXPORT_JOB_STATUSES = [
  "pending",
  "processing",
  "completed",
  "failed",
  "expired",
] as const;
export type ExportJobStatus = (typeof EXPORT_JOB_STATUSES)[number];

export const EXPORT_SCOPES = [
  "full",
  "compliance_only",
  "audit_only",
] as const;
export type ExportScope = (typeof EXPORT_SCOPES)[number];

export interface ExportJobSummary {
  id: string;
  tenant_id: string;
  requested_by_user_id: string;
  scope: ExportScope;
  status: ExportJobStatus;
  stored_file_id?: string | null;
  records_count: number;
  files_count: number;
  size_bytes: number;
  sha256_hash?: string | null;
  error_message?: string | null;
  expires_at: string;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
  manifest?: ExportManifestSummary | null;
}

export interface ExportManifestSummary {
  id: string;
  export_job_id: string;
  tenant_id: string;
  dataset_versions: Record<string, string>;
  file_hashes: Record<string, string>;
  record_counts: Record<string, number>;
  audit_references: Record<string, unknown>;
  manifest_sha256: string;
  created_at: string;
}

export const DELETION_JOB_STATES = [
  "scheduled",
  "processing",
  "completed",
  "failed",
  "on_hold",
] as const;
export type DeletionJobState = (typeof DELETION_JOB_STATES)[number];

export const DELETION_REASONS = [
  "cancellation",
  "retention_expired",
  "admin_request",
] as const;
export type DeletionReason = (typeof DELETION_REASONS)[number];

export interface DeletionJobSummary {
  id: string;
  tenant_id: string;
  reason: DeletionReason;
  state: DeletionJobState;
  scheduled_at: string;
  completed_at?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeletionProofSummary {
  id: string;
  tenant_id: string;
  deletion_job_id: string;
  deleted_at: string;
  tables_purged: Record<string, number>;
  storage_objects_purged: number;
  proof_manifest_sha256: string;
  created_at: string;
}

export interface TenantCancellationStatus {
  status: TenantStatus;
  cancellation_requested_at?: string | null;
  export_until?: string | null;
  deletion_due_at?: string | null;
  days_remaining_in_export_window?: number | null;
  is_export_window_active: boolean;
  legal_hold: boolean;
}
