/**
 * Type definitions for Operations Workspaces: Policies, Risks, Assets, and Vendors.
 * Conforms strictly to existing backend schemas and models.
 */

// ── Policies ──────────────────────────────────────────────────────────────────

export type PolicyStatus = "draft" | "in_review" | "approved" | "published" | "archived";
export type PolicyClassification = "Public" | "Internal" | "Confidential" | "Restricted";

export interface PolicyControlLink {
  id: string;
  policy_id: string;
  control_type: string;
  control_id: string;
  linked_by_user_id: string | null;
  created_at?: string;
}

export interface Policy {
  id: string;
  tenant_id: string;
  title: string;
  description: string;
  version_string: string;
  status: PolicyStatus;
  owner_user_id: string | null;
  approved_by_user_id: string | null;
  approved_at: string | null;
  review_cycle_days: number;
  next_review_due: string | null;
  version: number;
  content: string | null;
  classification: PolicyClassification;
  restricted_content?: string | null;
  control_links?: PolicyControlLink[];
  created_at: string;
  updated_at: string;
}

export interface PolicyCreateInput {
  title: string;
  description: string;
  version_string?: string;
  review_cycle_days?: number;
  content?: string | null;
  classification?: PolicyClassification;
  restricted_content?: string | null;
}

export interface PolicyUpdateInput {
  expected_version: number;
  title?: string;
  description?: string;
  version_string?: string;
  review_cycle_days?: number;
  content?: string | null;
  classification?: PolicyClassification;
  restricted_content?: string | null;
}

export interface VersionedActionInput {
  expected_version: number;
}

export interface PolicyRevision {
  id: string;
  tenant_id: string;
  policy_id: string;
  revision_number: number;
  version_string: string;
  title: string;
  description: string;
  content: string | null;
  classification: PolicyClassification;
  status: PolicyStatus;
  restricted_content?: string | null;
  created_by_user_id: string | null;
  approved_by_user_id: string | null;
  approved_at: string | null;
  change_summary: string | null;
  created_at: string;
}

export interface PolicyAcknowledgement {
  id: string;
  tenant_id: string;
  policy_id: string;
  policy_revision_id: string;
  user_id: string;
  acknowledged_at: string;
  ip_address?: string | null;
  user_agent?: string | null;
}

// ── Risks & Treatments ────────────────────────────────────────────────────────

export type RiskCategory =
  | "governance"
  | "operational"
  | "technical"
  | "security"
  | "compliance"
  | "third_party"
  | "financial";

export type RiskStatus = "identified" | "assessed" | "treating" | "monitored" | "closed";
export type RiskTreatmentStrategy = "mitigate" | "accept" | "transfer" | "avoid";

export interface RiskTreatment {
  id: string;
  strategy: RiskTreatmentStrategy;
  treatment_plan: string;
  target_date: string | null;
  status: string;
  owner_user_id: string | null;
  created_at: string;
}

export interface Risk {
  id: string;
  tenant_id: string;
  title: string;
  description: string;
  category: RiskCategory;
  likelihood: number;
  impact: number;
  inherent_score: number;
  residual_score: number | null;
  status: RiskStatus;
  owner_user_id: string | null;
  control_id: string | null;
  finding_id?: string | null;
  legal_entity_id?: string | null;
  business_unit_id?: string | null;
  treatments: RiskTreatment[];
  last_reviewed_at?: string | null;
  next_review_due_at?: string | null;
  created_at: string;
}

export interface RiskCreateInput {
  title: string;
  description: string;
  category?: RiskCategory;
  likelihood: number;
  impact: number;
  owner_user_id?: string | null;
  control_id?: string | null;
  finding_id?: string | null;
  legal_entity_id?: string | null;
  business_unit_id?: string | null;
}

export interface RiskUpdateInput {
  title: string;
  description: string;
  category?: RiskCategory;
  likelihood: number;
  impact: number;
  residual_score?: number | null;
  status?: RiskStatus;
  owner_user_id?: string | null;
  control_id?: string | null;
  finding_id?: string | null;
  legal_entity_id?: string | null;
  business_unit_id?: string | null;
}

export interface RiskReviewInput {
  next_review_due_at?: string | null;
}

export interface RiskTreatmentCreateInput {
  strategy?: RiskTreatmentStrategy;
  treatment_plan: string;
  target_date?: string | null;
  owner_user_id?: string | null;
}

export interface RiskTreatmentUpdateInput {
  strategy?: RiskTreatmentStrategy;
  treatment_plan: string;
  target_date?: string | null;
  status?: string;
  owner_user_id?: string | null;
}

// ── Assets ────────────────────────────────────────────────────────────────────

export type AssetType =
  | "hardware"
  | "software"
  | "data"
  | "cloud_service"
  | "facility"
  | "personnel";

export type AssetClassification = "public" | "internal" | "confidential" | "restricted";
export type AssetStatus = "active" | "in_maintenance" | "decommissioned";

export interface Asset {
  id: string;
  tenant_id: string;
  name: string;
  asset_type: AssetType;
  classification: AssetClassification;
  description: string | null;
  owner_user_id: string | null;
  control_id?: string | null;
  finding_id?: string | null;
  legal_entity_id?: string | null;
  business_unit_id?: string | null;
  status: AssetStatus;
  last_reviewed_at?: string | null;
  next_review_due_at?: string | null;
  created_at: string;
}

export interface AssetCreateInput {
  name: string;
  asset_type?: AssetType;
  classification?: AssetClassification;
  description?: string | null;
  owner_user_id?: string | null;
  control_id?: string | null;
  finding_id?: string | null;
  legal_entity_id?: string | null;
  business_unit_id?: string | null;
}

export interface AssetUpdateInput {
  name: string;
  asset_type?: AssetType;
  classification?: AssetClassification;
  description?: string | null;
  owner_user_id?: string | null;
  status?: AssetStatus;
  control_id?: string | null;
  finding_id?: string | null;
  legal_entity_id?: string | null;
  business_unit_id?: string | null;
}

export interface AssetReviewInput {
  next_review_due_at?: string | null;
}

// ── Vendors ───────────────────────────────────────────────────────────────────

export type VendorCriticality = "low" | "medium" | "high" | "critical";
export type VendorStatus = "active" | "under_review" | "terminated";

export interface Vendor {
  id: string;
  tenant_id: string;
  name: string;
  service_description: string;
  criticality: VendorCriticality;
  data_classification_accessed: string;
  country_residency: string;
  dpa_signed: boolean;
  security_reviewed_at: string | null;
  next_review_due_at: string | null;
  owner_user_id?: string | null;
  control_id?: string | null;
  finding_id?: string | null;
  legal_entity_id?: string | null;
  business_unit_id?: string | null;
  status?: VendorStatus;
}

export interface VendorCreateInput {
  name: string;
  service_description: string;
  criticality?: VendorCriticality;
  data_classification_accessed?: string;
  country_residency?: string;
  dpa_signed?: boolean;
  security_reviewed_at?: string | null;
  next_review_due_at?: string | null;
  owner_user_id?: string | null;
  control_id?: string | null;
  finding_id?: string | null;
  legal_entity_id?: string | null;
  business_unit_id?: string | null;
}

export interface VendorUpdateInput {
  name: string;
  service_description: string;
  criticality?: VendorCriticality;
  data_classification_accessed?: string;
  country_residency?: string;
  dpa_signed?: boolean;
  status?: VendorStatus;
  owner_user_id?: string | null;
  control_id?: string | null;
  finding_id?: string | null;
  legal_entity_id?: string | null;
  business_unit_id?: string | null;
}

export interface VendorReviewInput {
  next_review_due_at?: string | null;
}

// ── Operations Tab & Filter Types ─────────────────────────────────────────────

export type OperationsTab = "policies" | "risks" | "assets" | "vendors" | "tasks" | "reviews" | "jobs" | "training";

