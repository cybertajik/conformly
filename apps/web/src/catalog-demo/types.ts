/**
 * Type definitions for the synthetic staff catalog demo browser app.
 */

export interface SourceReferenceDTO {
  locator_kind: string;
  locator_value: string;
  sequence: number;
}

export interface ArtifactTypeDTO {
  artifact_type: string;
  sequence: number;
}

export interface MetadataKeyDTO {
  metadata_key: string;
  sequence: number;
}

export interface ProcedureStepDTO {
  sequence: number;
  step_kind: string;
  instruction: string;
  expected_output?: string | null;
}

export interface CatalogSourceDTO {
  id: string;
  source_key: string;
  title: string;
  status: string;
}

export interface CatalogSourceVersionDTO {
  id: string;
  source_id: string;
  edition: string;
  language: string | null;
  official_locator: string | null;
  publication_date: string | null;
  revision: number;
  status: string;
  content_digest: string;
  provenance_id?: string | null;
}

export interface CatalogRequirementDTO {
  id: string;
  source_id: string;
  requirement_key: string;
  version_id: string;
  version_label: string;
  revision: number;
  normalized_outcome: string;
  requirement_type: string;
  obligated_actor: string;
  text_origin: string;
  effective_from: string | null;
  content_digest: string;
  status: string;
  source_references: SourceReferenceDTO[];
}

export interface CatalogEvidenceRequirementDTO {
  id: string;
  control_id: string;
  control_version_id: string;
  requirement_key: string;
  sequence: number;
  title: string;
  frequency: string;
  scope_state: string;
  assurance_purpose: string;
  validity_rule: string;
  max_age_days: number | null;
  guidance: string | null;
  missing_data_behavior: string;
  artifact_types: ArtifactTypeDTO[];
  required_metadata: MetadataKeyDTO[];
  content_digest: string;
  status: string;
}

export interface CatalogAssessmentProcedureDTO {
  id: string;
  control_id: string;
  control_version_id: string;
  procedure_key: string;
  sequence: number;
  title: string;
  objective: string;
  decision_guidance: string;
  assessor_qualifications: string | null;
  missing_data_behavior: string;
  steps: ProcedureStepDTO[];
  evidence_requirement_ids: string[];
  content_digest: string;
  status: string;
}

export interface CatalogControlDTO {
  id: string;
  control_key: string;
  domain: string;
  version_id: string;
  version_label: string;
  revision: number;
  title: string;
  objective: string;
  guidance: string | null;
  control_type: string;
  frequency: string;
  automation_level: string;
  suggested_owner_role: string;
  assurance_level: string;
  tags_state: string;
  content_digest: string;
  status: string;
  evidence_requirements?: CatalogEvidenceRequirementDTO[];
  assessment_procedures?: CatalogAssessmentProcedureDTO[];
}

export interface CatalogMappingDTO {
  id: string;
  mapping_key: string;
  requirement_id: string;
  control_id: string;
  requirement_version_id: string;
  control_version_id: string;
  version_label: string;
  revision: number;
  mapping_type: "Full" | "Partial" | "Supporting" | string;
  rationale: string;
  covered_dimensions: string | null;
  excluded_dimensions: string | null;
  conditions: string | null;
  source_basis: string;
  confidence: string;
  review_state: string;
  content_digest: string;
  status: string;
}

export interface CatalogDemoGraphResponse {
  demo_id: string;
  synthetic: boolean;
  status: string;
  source: CatalogSourceDTO;
  source_version: CatalogSourceVersionDTO;
  requirements: CatalogRequirementDTO[];
  controls: CatalogControlDTO[];
  mappings: CatalogMappingDTO[];
  evidence_requirements: CatalogEvidenceRequirementDTO[];
  assessment_procedures: CatalogAssessmentProcedureDTO[];
}

export interface CatalogDemoSessionResponse {
  user_id: string;
  display_name: string;
  authenticated_at: string;
  expires_at: string;
  capabilities: string[];
}

export type ViewTab =
  | "overview"
  | "requirements"
  | "controls"
  | "evidence";
