"""FastAPI and Pydantic schemas for MVP-C Customer Assessment, Retest and Findings."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssessmentCriterionResultDto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    criterion_id: Literal["implementation", "evidence", "operation"]
    result: Literal["PASS", "FAIL", "INSUFFICIENT_EVIDENCE"]


class FindingCreateSpecificationDto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    owner_user_id: UUID | None = None
    due_date: date | None = None


class AssessmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: UUID
    expected_answer_revision: int = Field(..., gt=0, strict=True)
    expected_selection_revision: int = Field(..., gt=0, strict=True)
    expected_work_version: int = Field(..., gt=0, strict=True)
    expected_assessment_revision: int = Field(..., ge=0, strict=True)
    procedure_id: UUID
    procedure_version: str
    procedure_digest: str = Field(..., min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    result: Literal["PASS", "PARTIAL", "FAIL", "INSUFFICIENT_EVIDENCE"]
    rationale: str = Field(..., min_length=1, max_length=2000)
    criterion_results: list[AssessmentCriterionResultDto]
    evidence_link_ids: list[UUID] = Field(default_factory=list, max_length=10)
    finding: FindingCreateSpecificationDto | None = None

    @field_validator("rationale")
    @classmethod
    def validate_nonblank_rationale(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Rationale must not be empty or whitespace-only")
        return v

    @field_validator("criterion_results")
    @classmethod
    def validate_exact_three_criteria(
        cls, v: list[AssessmentCriterionResultDto]
    ) -> list[AssessmentCriterionResultDto]:
        ids = {c.criterion_id for c in v}
        if len(v) != 3 or ids != {"implementation", "evidence", "operation"}:
            raise ValueError(
                "criterion_results must contain exactly the 3 unique criteria: implementation, evidence, operation"
            )
        return v

    @field_validator("evidence_link_ids")
    @classmethod
    def validate_unique_evidence_links(cls, v: list[UUID]) -> list[UUID]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate evidence_link_ids submitted")
        return v


class RetestFindingReferenceDto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    expected_version: int = Field(..., gt=0, strict=True)


class RetestCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: UUID
    expected_answer_revision: int = Field(..., gt=0, strict=True)
    expected_selection_revision: int = Field(..., gt=0, strict=True)
    expected_work_version: int = Field(..., gt=0, strict=True)
    expected_assessment_revision: int = Field(..., ge=0, strict=True)
    procedure_id: UUID
    procedure_version: str
    procedure_digest: str = Field(..., min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    result: Literal["PASS", "PARTIAL", "FAIL", "INSUFFICIENT_EVIDENCE"]
    rationale: str = Field(..., min_length=1, max_length=2000)
    criterion_results: list[AssessmentCriterionResultDto]
    evidence_link_ids: list[UUID] = Field(default_factory=list, max_length=10)
    findings: list[RetestFindingReferenceDto] = Field(..., min_length=1, max_length=20)

    @field_validator("rationale")
    @classmethod
    def validate_nonblank_rationale(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Rationale must not be empty or whitespace-only")
        return v

    @field_validator("criterion_results")
    @classmethod
    def validate_exact_three_criteria(
        cls, v: list[AssessmentCriterionResultDto]
    ) -> list[AssessmentCriterionResultDto]:
        ids = {c.criterion_id for c in v}
        if len(v) != 3 or ids != {"implementation", "evidence", "operation"}:
            raise ValueError(
                "criterion_results must contain exactly the 3 unique criteria: implementation, evidence, operation"
            )
        return v

    @field_validator("evidence_link_ids")
    @classmethod
    def validate_unique_evidence_links(cls, v: list[UUID]) -> list[UUID]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate evidence_link_ids submitted")
        return v

    @field_validator("findings")
    @classmethod
    def validate_distinct_findings(
        cls, v: list[RetestFindingReferenceDto]
    ) -> list[RetestFindingReferenceDto]:
        ids = {f.id for f in v}
        if len(ids) != len(v):
            raise ValueError("Duplicate finding IDs submitted for retest")
        return v


class FindingPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: UUID
    expected_answer_revision: int = Field(..., gt=0, strict=True)
    expected_selection_revision: int = Field(..., gt=0, strict=True)
    expected_work_version: int = Field(..., gt=0, strict=True)
    expected_assessment_revision: int = Field(..., ge=0, strict=True)
    expected_finding_version: int = Field(..., gt=0, strict=True)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    owner_user_id: UUID | None = Field(...)
    due_date: date | None = Field(...)
    status: Literal["OPEN", "IN_REMEDIATION"]
    remediation_note: str = Field(..., min_length=1, max_length=2000)

    @field_validator("remediation_note")
    @classmethod
    def validate_nonblank_remediation_note(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("remediation_note must not be empty or whitespace-only")
        return v


# Responses and DTOs


class ProcedureCriterionDto(BaseModel):
    id: str
    title: str
    description: str
    sequence: int


class ProcedureDto(BaseModel):
    id: UUID
    version: str
    digest: str
    criteria: list[ProcedureCriterionDto]
    disclaimer: str


class FindingDto(BaseModel):
    id: UUID
    source_event_id: UUID
    current_event_id: UUID
    severity: str
    owner_user_id: UUID | None
    owner_display_name: str | None
    due_date: date | None
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class PinnedEvidenceDto(BaseModel):
    link_id: UUID
    evidence_id: UUID
    revision_number: int
    revision_digest: str
    latest_review_event_id: UUID
    file_id: UUID
    file_hash: str
    scan_verified_at: datetime | None


class LatestAssessmentDto(BaseModel):
    event_id: UUID
    revision: int
    result: str
    actor_id: UUID
    created_at: datetime
    rationale: str
    criterion_results: list[dict[str, Any]]
    evidence_pins: list[PinnedEvidenceDto]
    is_stale: bool
    stale_reasons: list[str]


class AssessmentHistoryItemDto(BaseModel):
    event_id: UUID
    revision: int
    operation_id: UUID
    event_type: str
    result: str | None
    observed_work_version: int
    actor_id: UUID
    created_at: datetime
    details: dict[str, Any]


class AssessmentWorkItemDto(BaseModel):
    work_id: UUID
    control_version_id: UUID
    work_version: int
    assessment_revision: int
    procedure: ProcedureDto
    latest_assessment: LatestAssessmentDto | None
    primary_state: str
    blockers: list[str]
    findings: list[FindingDto]
    history: list[AssessmentHistoryItemDto]
    requirement_results: list[dict[str, Any]] = Field(default_factory=list)


class ReadinessSummaryDto(BaseModel):
    total_controls: int
    stale_work: int
    needs_information: int
    not_applicable: int
    unassessed: int
    unavailable_evidence: int
    stale_assessment: int
    insufficient_evidence: int
    fail: int
    partial: int
    pass_with_open_findings: int
    pass_count: int
    open_findings: int
    in_remediation_findings: int
    resolved_findings: int
    blocked_control_ids: list[UUID]
    reason_codes: list[str]


class AssessmentWorkListResponse(BaseModel):
    tenant_id: UUID
    adoption_id: UUID | None
    answer_revision: int
    selection_revision: int
    is_stale: bool
    summary: ReadinessSummaryDto
    items: list[AssessmentWorkItemDto]


class AssessmentOperationReceiptDto(BaseModel):
    operation_id: UUID
    event_id: UUID
    applied_revision: int
    replayed: bool
    current_item: AssessmentWorkItemDto
    summary: ReadinessSummaryDto


class AssessmentHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    work_id: UUID
    items: list[AssessmentHistoryItemDto]
    total: int
    limit: int
    offset: int


# Aliases for API/contract compatibility
AssessmentProcedureDTO = ProcedureDto
AssessmentReceiptDTO = AssessmentOperationReceiptDto
CreateAssessmentRequest = AssessmentCreateRequest
CreateRetestRequest = RetestCreateRequest
PatchFindingRequest = FindingPatchRequest
