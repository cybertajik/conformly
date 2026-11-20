"""Pydantic schemas and strict DTOs for WP-09 Customer Onboarding Demo."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictBaseModel(BaseModel):
    """Base model forbidding unexpected extra fields."""

    model_config = ConfigDict(extra="forbid")


class ExplanationTreeNodeDTO(StrictBaseModel):
    """Node in deterministic explanation tree."""

    op: str
    path: str
    result: Literal["APPLICABLE", "NOT_APPLICABLE", "NEEDS_INFORMATION"]
    message: str
    fact_definition_version_id: str | None = None
    missing_fact_version_ids: list[str] = Field(default_factory=list)
    children: list[ExplanationTreeNodeDTO] = Field(default_factory=list)


class RequirementEvaluationResultDTO(StrictBaseModel):
    """Result of evaluating one requirement."""

    requirement_id: UUID
    requirement_version_id: UUID
    identifier: str
    title: str
    rule_id: UUID
    rule_version_id: UUID
    result: Literal["APPLICABLE", "NOT_APPLICABLE", "NEEDS_INFORMATION"]
    missing_fact_version_ids: list[str] = Field(default_factory=list)
    explanation_tree: ExplanationTreeNodeDTO


class AnswersDataDTO(StrictBaseModel):
    """Strict typed answers for fictional company facts."""

    synthetic_wp09_uses_cloud: bool | None = None
    synthetic_wp09_operating_region: Literal["EU", "OTHER"] | None = None

    @field_validator("synthetic_wp09_uses_cloud", mode="before")
    @classmethod
    def validate_strict_boolean(cls, v: Any) -> bool | None:
        if v is None:
            return None
        # Must be strictly a Python bool, not int (0/1) or string ("true")
        if type(v) is not bool:
            raise ValueError("synthetic_wp09_uses_cloud must be a strict boolean literal")
        return v

    @field_validator("synthetic_wp09_operating_region", mode="before")
    @classmethod
    def validate_region(cls, v: Any) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str) or v not in ("EU", "OTHER"):
            raise ValueError("synthetic_wp09_operating_region must be 'EU' or 'OTHER'")
        return v


class SaveAnswersRequest(StrictBaseModel):
    """Request body for saving customer demo answers."""

    expected_revision: int = Field(ge=0)
    company_code: Literal["ALPHA", "BETA"]
    answers: dict[str, Any]

    @field_validator("expected_revision")
    @classmethod
    def validate_revision_nonneg(cls, v: int) -> int:
        if v < 0:
            raise ValueError("expected_revision must be >= 0")
        return v


class AnswersResponse(StrictBaseModel):
    """Response containing saved immutable answers."""

    tenant_id: UUID
    revision: int
    company_code: str
    answers: dict[str, Any]
    content_digest: str
    created_at: datetime


class CreateEvaluationRequest(StrictBaseModel):
    """Request body for evaluating answers against a demo pack."""

    expected_revision: int = Field(gt=0)
    pack_version_id: UUID


class EvaluationResponse(StrictBaseModel):
    """Server-computed evaluation snapshot response."""

    id: UUID
    tenant_id: UUID
    answer_revision: int
    pack_version_id: UUID
    bundle_digest: str
    evaluator_version: str
    content_digest: str
    results: list[RequirementEvaluationResultDTO]
    created_at: datetime


class CreateAdoptionRequest(StrictBaseModel):
    """Request body for adopting a demo pack."""

    expected_revision: int = Field(gt=0)
    evaluation_id: UUID
    pack_version_id: UUID
    acknowledge_synthetic: bool
    acknowledge_missing_information: bool = False

    @field_validator("acknowledge_synthetic", "acknowledge_missing_information", mode="before")
    @classmethod
    def validate_strict_bool(cls, v: Any) -> bool:
        if type(v) is not bool:
            raise ValueError("Boolean acknowledgement fields must be strict booleans (true/false)")
        return v

    @field_validator("acknowledge_synthetic")
    @classmethod
    def validate_acknowledge_synthetic(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Explicit acknowledgement of synthetic nature is required")
        return v


class AdoptionResponse(StrictBaseModel):
    """Receipt for demo pack adoption."""

    id: UUID
    tenant_id: UUID
    selection_revision: int
    evaluation_id: UUID
    pack_version_id: UUID
    bundle_digest: str
    created_at: datetime
    is_current: bool
    current_selection_revision: int
    current_pack_version_id: UUID


class SelectedPackSummary(StrictBaseModel):
    """Summary of currently selected pack."""

    selection_revision: int
    evaluation_id: UUID
    pack_version_id: UUID
    bundle_digest: str
    created_at: datetime
    is_stale: bool


class WorkspaceResponse(StrictBaseModel):
    """Aggregated workspace response for customer demo."""

    tenant_id: UUID
    current_revision: int
    selection_revision: int
    manifest: dict[str, Any]
    answers: AnswersResponse | None = None
    selected_pack: SelectedPackSummary | None = None
    latest_evaluation: EvaluationResponse | None = None
    history_summary: list[dict[str, Any]] = Field(default_factory=list)
