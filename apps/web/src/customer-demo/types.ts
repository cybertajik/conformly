/**
 * Type definitions for WP-09 customer onboarding demo.
 */

export type CompanyCode = "ALPHA" | "BETA";
export type TriState = "yes" | "no" | "unknown";
export type RegionChoice = "EU" | "OTHER" | "unknown";

export type EvaluationResultStatus = "APPLICABLE" | "NOT_APPLICABLE" | "NEEDS_INFORMATION";

export interface ExplanationTreeNode {
  op: string;
  path: string;
  result: EvaluationResultStatus;
  message: string;
  fact_definition_version_id?: string | null;
  missing_fact_version_ids: string[];
  children: ExplanationTreeNode[];
}

export interface RequirementEvaluationResult {
  requirement_id: string;
  requirement_version_id: string;
  identifier: string;
  title: string;
  rule_id: string;
  rule_version_id: string;
  result: EvaluationResultStatus;
  missing_fact_version_ids: string[];
  explanation_tree: ExplanationTreeNode;
}

export interface AnswersData {
  tenant_id: string;
  revision: number;
  company_code: string;
  answers: Record<string, unknown>;
  content_digest: string;
  created_at: string;
}

export interface SelectedPackSummary {
  selection_revision: number;
  evaluation_id: string;
  pack_version_id: string;
  bundle_digest: string;
  created_at: string;
  is_stale: boolean;
}

export interface EvaluationData {
  id: string;
  tenant_id: string;
  answer_revision: number;
  pack_version_id: string;
  bundle_digest: string;
  evaluator_version: string;
  content_digest: string;
  results: RequirementEvaluationResult[];
  created_at: string;
}

export interface DemoPackRequirement {
  id: string;
  version_id: string;
  identifier: string;
  title: string;
  description: string;
  rule_id: string;
  rule_version_id: string;
  control_id: string;
  control_version_id: string;
  control_identifier: string;
  control_title: string;
}

export interface DemoPack {
  pack_id: string;
  pack_version_id: string;
  version: string;
  name: string;
  description: string;
  bundle_digest: string;
  requirement_count: number;
  requirements: DemoPackRequirement[];
}

export interface DemoManifest {
  disclaimer: string;
  evaluator_version: string;
  companies: Array<{ code: string; display_name: string }>;
  fact_definitions: Array<{
    id: string;
    version_id: string;
    key: string;
    label: string;
    description: string;
    value_type: string;
    enum_options?: Array<{ code: string; label: string }>;
  }>;
  packs: DemoPack[];
}

export interface WorkspaceData {
  tenant_id: string;
  current_revision: number;
  selection_revision: number;
  manifest: DemoManifest;
  answers: AnswersData | null;
  selected_pack: SelectedPackSummary | null;
  latest_evaluation: EvaluationData | null;
  history_summary: Array<{
    selection_revision: number;
    pack_version_id: string;
    bundle_digest: string;
    created_at: string;
  }>;
}

export interface AdoptionReceipt {
  id: string;
  tenant_id: string;
  selection_revision: number;
  evaluation_id: string;
  pack_version_id: string;
  bundle_digest: string;
  created_at: string;
  is_current: boolean;
  current_selection_revision: number;
  current_pack_version_id: string;
}

export interface SaveAnswersInput {
  expected_revision: number;
  company_code: CompanyCode;
  answers: {
    synthetic_wp09_uses_cloud: boolean | null;
    synthetic_wp09_operating_region: "EU" | "OTHER" | null;
  };
}

export interface EvaluateInput {
  expected_revision: number;
  pack_version_id: string;
}

export interface AdoptInput {
  expected_revision: number;
  evaluation_id: string;
  pack_version_id: string;
  acknowledge_synthetic: boolean;
  acknowledge_missing_information: boolean;
}
