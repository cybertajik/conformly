"""Pydantic schemas and DTOs for MVP-B Customer Control Work and Evidence Pinning."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from conformly.customer_demo.schemas import RequirementEvaluationResultDTO


class StrictBaseModel(BaseModel):
    """Base model forbidding unexpected extra fields."""

    model_config = ConfigDict(extra="forbid")


def _validate_strict_int(v: Any, field_name: str, allow_zero: bool = False) -> int:
    if type(v) is not int:
        raise ValueError(f"{field_name} must be a strict integer")
    if allow_zero:
        if v < 0:
            raise ValueError(f"{field_name} must be >= 0")
    else:
        if v <= 0:
            raise ValueError(f"{field_name} must be > 0")
    return v


class InitializeWorkRequest(StrictBaseModel):
    """Request body for initializing control work for an adopted pack."""

    operation_id: UUID
    adoption_id: UUID
    expected_selection_revision: int
    expected_answer_revision: int

    @field_validator("expected_selection_revision", mode="before")
    @classmethod
    def check_sel_rev(cls, v: Any) -> int:
        return _validate_strict_int(v, "expected_selection_revision", allow_zero=True)

    @field_validator("expected_answer_revision", mode="before")
    @classmethod
    def check_ans_rev(cls, v: Any) -> int:
        return _validate_strict_int(v, "expected_answer_revision", allow_zero=False)


class PatchWorkRequest(StrictBaseModel):
    """Request body for updating control work assignment (owner and due date)."""

    operation_id: UUID
    expected_selection_revision: int
    expected_answer_revision: int
    expected_work_version: int
    owner_user_id: UUID | None = None
    due_date: date | None = None

    @field_validator("expected_selection_revision", mode="before")
    @classmethod
    def check_sel_rev(cls, v: Any) -> int:
        return _validate_strict_int(v, "expected_selection_revision", allow_zero=True)

    @field_validator("expected_answer_revision", mode="before")
    @classmethod
    def check_ans_rev(cls, v: Any) -> int:
        return _validate_strict_int(v, "expected_answer_revision", allow_zero=False)

    @field_validator("expected_work_version", mode="before")
    @classmethod
    def check_work_ver(cls, v: Any) -> int:
        return _validate_strict_int(v, "expected_work_version", allow_zero=False)


class CreateEvidenceRequest(StrictBaseModel):
    """Request body for creating and pinning new evidence from an uploaded file."""

    operation_id: UUID
    expected_selection_revision: int
    expected_answer_revision: int
    expected_work_version: int
    file_id: UUID
    valid_until: datetime | None = None
    rationale: str = Field(min_length=1, max_length=2000)

    @field_validator("expected_selection_revision", mode="before")
    @classmethod
    def check_sel_rev(cls, v: Any) -> int:
        return _validate_strict_int(v, "expected_selection_revision", allow_zero=True)

    @field_validator("expected_answer_revision", mode="before")
    @classmethod
    def check_ans_rev(cls, v: Any) -> int:
        return _validate_strict_int(v, "expected_answer_revision", allow_zero=False)

    @field_validator("expected_work_version", mode="before")
    @classmethod
    def check_work_ver(cls, v: Any) -> int:
        return _validate_strict_int(v, "expected_work_version", allow_zero=False)


class CreateLinkRequest(StrictBaseModel):
    """Request body for deliberately reusing an existing evidence revision snapshot."""

    operation_id: UUID
    expected_selection_revision: int
    expected_answer_revision: int
    expected_work_version: int
    evidence_id: UUID
    evidence_revision_number: int
    evidence_revision_digest: str = Field(min_length=64, max_length=64)
    rationale: str = Field(min_length=1, max_length=2000)

    @field_validator("expected_selection_revision", mode="before")
    @classmethod
    def check_sel_rev(cls, v: Any) -> int:
        return _validate_strict_int(v, "expected_selection_revision", allow_zero=True)

    @field_validator("expected_answer_revision", mode="before")
    @classmethod
    def check_ans_rev(cls, v: Any) -> int:
        return _validate_strict_int(v, "expected_answer_revision", allow_zero=False)

    @field_validator("expected_work_version", mode="before")
    @classmethod
    def check_work_ver(cls, v: Any) -> int:
        return _validate_strict_int(v, "expected_work_version", allow_zero=False)

    @field_validator("evidence_revision_number", mode="before")
    @classmethod
    def check_rev_num(cls, v: Any) -> int:
        return _validate_strict_int(v, "evidence_revision_number", allow_zero=False)


class CreateReviewRequest(StrictBaseModel):
    """Request body for recording an evidence suitability review decision."""

    operation_id: UUID
    expected_selection_revision: int
    expected_answer_revision: int
    expected_work_version: int
    decision: Literal["ACCEPTED", "REJECTED"]
    rationale: str = Field(min_length=1, max_length=2000)

    @field_validator("expected_selection_revision", mode="before")
    @classmethod
    def check_sel_rev(cls, v: Any) -> int:
        return _validate_strict_int(v, "expected_selection_revision", allow_zero=True)

    @field_validator("expected_answer_revision", mode="before")
    @classmethod
    def check_ans_rev(cls, v: Any) -> int:
        return _validate_strict_int(v, "expected_answer_revision", allow_zero=False)

    @field_validator("expected_work_version", mode="before")
    @classmethod
    def check_work_ver(cls, v: Any) -> int:
        return _validate_strict_int(v, "expected_work_version", allow_zero=False)


class OwnerDirectoryItemDTO(StrictBaseModel):
    """Sanitized directory entry for eligible control owner."""

    user_id: UUID
    display_name: str


class OwnerDirectoryResponse(StrictBaseModel):
    """Bounded eligible owner directory response."""

    items: list[OwnerDirectoryItemDTO]
    total: int


class LinkDTO(StrictBaseModel):
    """Representation of an exact evidence revision linkage."""

    id: UUID
    evidence_id: UUID
    revision_number: int
    digest: str
    file_ids: list[UUID]
    filename: str
    file_size: int
    classification: str
    validity: Literal[
        "MISSING",
        "AVAILABLE",
        "NOT_YET_VALID",
        "EXPIRED",
        "QUARANTINED",
        "UNAVAILABLE",
        "UNVERIFIED",
    ]
    scan_status: Literal["SCANNED_AT_LINK", "UNVERIFIED"] = "UNVERIFIED"
    scan_verified_at: datetime | None = None
    review: Literal["PENDING", "ACCEPTED", "REJECTED"]
    rationale: str
    created_at: datetime


class EventDTO(StrictBaseModel):
    """Audit and state progression event for control work history."""

    revision: int
    type: str
    actor_id: UUID
    time: datetime
    link_id: UUID | None = None
    decision: str | None = None
    details: dict[str, Any]


class WorkDTO(StrictBaseModel):
    """Comprehensive work item DTO for one pinned synthetic control."""

    id: UUID
    adoption_id: UUID
    control_id: UUID
    control_version_id: UUID
    title: str
    provenance: str
    pack_version: int
    bundle_digest: str
    requirement_results: list[RequirementEvaluationResultDTO]
    owner_user_id: UUID | None = None
    owner_display_name: str | None = None
    due_date: date | None = None
    version: int
    is_current: bool
    is_stale: bool
    links: list[LinkDTO] = Field(default_factory=list)


class WorkListResponse(StrictBaseModel):
    """Common control work list response."""

    tenant_id: UUID
    adoption_id: UUID | None = None
    selection_revision: int
    answer_revision: int
    is_current: bool
    is_stale: bool
    items: list[WorkDTO]
    total: int


class MutationReceipt(StrictBaseModel):
    """Receipt returned after state-mutating control work operations."""

    operation_id: UUID
    event_id: UUID
    applied_work_version: int
    replayed: bool
    current_work: WorkDTO


class WorkHistoryResponse(StrictBaseModel):
    """Ordered event history for a control work item."""

    items: list[EventDTO]
    total: int
