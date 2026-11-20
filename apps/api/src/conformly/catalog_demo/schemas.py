"""Pydantic DTOs for the synthetic catalog demo with extra="forbid"."""

from pydantic import BaseModel, ConfigDict, Field


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CatalogDemoSessionResponse(StrictBaseModel):
    user_id: str
    display_name: str
    authenticated_at: str
    expires_at: str
    capabilities: list[str]


class SourceReferenceDTO(StrictBaseModel):
    locator_kind: str
    locator_value: str
    sequence: int


class ArtifactTypeDTO(StrictBaseModel):
    artifact_type: str
    sequence: int


class MetadataKeyDTO(StrictBaseModel):
    metadata_key: str
    sequence: int


class ProcedureStepDTO(StrictBaseModel):
    sequence: int
    step_kind: str
    instruction: str
    expected_output: str | None = None


class CatalogSourceDTO(StrictBaseModel):
    id: str
    source_key: str
    title: str
    status: str


class CatalogSourceVersionDTO(StrictBaseModel):
    id: str
    source_id: str
    edition: str
    language: str | None
    official_locator: str | None
    publication_date: str | None
    revision: int
    status: str
    content_digest: str
    provenance_id: str | None = None


class CatalogRequirementDTO(StrictBaseModel):
    id: str
    source_id: str
    requirement_key: str
    version_id: str
    version_label: str
    revision: int
    normalized_outcome: str
    requirement_type: str
    obligated_actor: str
    text_origin: str
    effective_from: str | None
    content_digest: str
    status: str
    source_references: list[SourceReferenceDTO]


class CatalogEvidenceRequirementDTO(StrictBaseModel):
    id: str
    control_id: str
    control_version_id: str
    requirement_key: str
    sequence: int
    title: str
    frequency: str
    scope_state: str
    assurance_purpose: str
    validity_rule: str
    max_age_days: int | None
    guidance: str | None
    missing_data_behavior: str
    artifact_types: list[ArtifactTypeDTO]
    required_metadata: list[MetadataKeyDTO]
    content_digest: str
    status: str


class CatalogAssessmentProcedureDTO(StrictBaseModel):
    id: str
    control_id: str
    control_version_id: str
    procedure_key: str
    sequence: int
    title: str
    objective: str
    decision_guidance: str
    assessor_qualifications: str | None
    missing_data_behavior: str
    steps: list[ProcedureStepDTO]
    evidence_requirement_ids: list[str]
    content_digest: str
    status: str


class CatalogControlDTO(StrictBaseModel):
    id: str
    control_key: str
    domain: str
    version_id: str
    version_label: str
    revision: int
    title: str
    objective: str
    guidance: str | None
    control_type: str
    frequency: str
    automation_level: str
    suggested_owner_role: str
    assurance_level: str
    tags_state: str
    content_digest: str
    status: str
    evidence_requirements: list[CatalogEvidenceRequirementDTO] = Field(default_factory=list)
    assessment_procedures: list[CatalogAssessmentProcedureDTO] = Field(default_factory=list)


class CatalogMappingDTO(StrictBaseModel):
    id: str
    mapping_key: str
    requirement_id: str
    control_id: str
    requirement_version_id: str
    control_version_id: str
    version_label: str
    revision: int
    mapping_type: str
    rationale: str
    covered_dimensions: str | None
    excluded_dimensions: str | None
    conditions: str | None
    source_basis: str
    confidence: str
    review_state: str
    content_digest: str
    status: str


class CatalogDemoGraphResponse(StrictBaseModel):
    demo_id: str = "catalog-demo-v1"
    synthetic: bool = True
    status: str = "Draft"
    source: CatalogSourceDTO
    source_version: CatalogSourceVersionDTO
    requirements: list[CatalogRequirementDTO]
    controls: list[CatalogControlDTO]
    mappings: list[CatalogMappingDTO]
    evidence_requirements: list[CatalogEvidenceRequirementDTO]
    assessment_procedures: list[CatalogAssessmentProcedureDTO]
