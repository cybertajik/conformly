"""Pydantic schemas and DTOs for V2 Pre-Audit Review Workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PreauditBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CreatePreauditRequest(PreauditBaseModel):
    operation_id: UUID
    adoption_id: UUID
    lead_user_id: UUID
    reviewer_user_id: UUID
    title: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=1024)


class FreezeScopeRequest(PreauditBaseModel):
    operation_id: UUID
    expected_revision: int = Field(ge=1, strict=True)


class SubmitReviewRequest(PreauditBaseModel):
    operation_id: UUID
    expected_revision: int = Field(ge=1, strict=True)
    submission_notes: str | None = Field(default=None, max_length=2048)


class ReviewDecisionRequest(PreauditBaseModel):
    operation_id: UUID
    expected_revision: int = Field(ge=1, strict=True)
    snapshot_id: UUID
    snapshot_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    decision: Literal["ACCEPT", "REQUEST_CHANGES"]
    notes: str = Field(min_length=1, max_length=4096)


class ApprovePreauditRequest(PreauditBaseModel):
    operation_id: UUID
    expected_revision: int = Field(ge=1, strict=True)
    snapshot_id: UUID
    snapshot_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    approval_notes: str | None = Field(default=None, max_length=2048)


class CancelPreauditRequest(PreauditBaseModel):
    operation_id: UUID
    expected_revision: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=2048)


class DownloadPreauditReportRequest(PreauditBaseModel):
    expected_revision: int = Field(ge=1, strict=True)
    snapshot_id: UUID


class PreauditActorDTO(PreauditBaseModel):
    user_id: UUID
    role: str
    email: str
    display_name: str


class PreauditActorsResponse(PreauditBaseModel):
    actors: list[PreauditActorDTO]


class PreauditSnapshotSummaryDTO(PreauditBaseModel):
    id: UUID
    kind: str
    sequence: int
    digest: str
    created_by_user_id: UUID
    created_at: datetime


class PreauditBlockerDTO(PreauditBaseModel):
    code: str
    description: str
    work_id: UUID | None = None
    control_code: str | None = None


class PreauditSummaryDTO(PreauditBaseModel):
    id: UUID
    tenant_id: UUID
    adoption_id: UUID
    pack_name: str
    pack_version: str
    lead_user_id: UUID
    reviewer_user_id: UUID
    status: str
    revision: int
    title: str
    created_at: datetime
    updated_at: datetime


class PreauditListResponse(PreauditBaseModel):
    items: list[PreauditSummaryDTO]
    total: int


class PreauditDetailResponse(PreauditBaseModel):
    id: UUID
    tenant_id: UUID
    adoption_id: UUID
    pack_name: str
    pack_version: str
    lead_user_id: UUID
    reviewer_user_id: UUID
    lead_name: str
    reviewer_name: str
    status: str
    revision: int
    current_scope_snapshot_id: UUID | None = None
    current_scope_snapshot_digest: str | None = None
    current_review_snapshot_id: UUID | None = None
    current_review_snapshot_digest: str | None = None
    is_scope_current: bool
    is_review_current: bool
    blockers: list[PreauditBlockerDTO]
    title: str | None = None
    description: str | None = None
    replayed: bool = False
    applied_event_id: UUID | None = None
    applied_revision: int | None = None
    applied_snapshot_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class PreauditEventDTO(PreauditBaseModel):
    id: UUID
    revision: int
    event_type: str
    actor_user_id: UUID
    actor_name: str
    snapshot_id: UUID | None = None
    prior_status: str | None = None
    new_status: str
    notes: str | None = None
    created_at: datetime


class PreauditHistoryResponse(PreauditBaseModel):
    events: list[PreauditEventDTO]

