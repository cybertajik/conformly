"""Pydantic schemas and DTOs for V2 Customer Readiness Verification Lifecycle."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SYNTHETIC_MARKER = "PRIVATE SYNTHETIC INTERNAL TEST RESULT"
TEST_QUALIFICATION = "PRIVATE SYNTHETIC INTERNAL TEST RESULT - NOT AN ACCREDITED CERTIFICATION"


class StrictBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IssueVerificationRequest(StrictBase):
    operation_id: UUID
    preaudit_id: UUID
    expected_case_revision: int = Field(ge=1, strict=True)
    snapshot_id: UUID
    snapshot_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    limitations: list[str] = Field(default_factory=list, max_length=50)
    notes: str | None = Field(default=None, max_length=4096)


class SuspendVerificationRequest(StrictBase):
    operation_id: UUID
    expected_revision: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=4096)


class RevokeVerificationRequest(StrictBase):
    operation_id: UUID
    expected_revision: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=4096)


class CorrectVerificationRequest(StrictBase):
    operation_id: UUID
    expected_revision: int = Field(ge=1, strict=True)
    correction_notes: str = Field(min_length=1, max_length=4096)


class SupersedeVerificationRequest(StrictBase):
    operation_id: UUID
    expected_revision: int = Field(ge=1, strict=True)
    new_preaudit_id: UUID
    new_expected_case_revision: int = Field(ge=1, strict=True)
    new_snapshot_id: UUID
    new_snapshot_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    limitations: list[str] = Field(default_factory=list, max_length=50)
    notes: str | None = Field(default=None, max_length=4096)


class ReconcileVerificationRequest(StrictBase):
    pass


class VerificationDetailResponse(StrictBase):
    id: UUID
    preaudit_id: UUID
    snapshot_id: UUID
    status: str
    effective_status: str
    effective_reason: str | None = None
    revision: int
    issued_at: datetime
    valid_through: datetime
    digest: str
    current_event_id: UUID | None = None
    superseded_by_id: UUID | None = None
    supersedes_id: UUID | None = None
    change_reason: str | None = None
    synthetic_marker: str = SYNTHETIC_MARKER
    test_qualification: str = TEST_QUALIFICATION
    framework_id: str | None = None
    framework_version: str | None = None
    framework_display_name: str | None = None
    organization_display_name: str | None = None
    scope_summary: dict[str, Any] | None = None
    limitations: list[str] = Field(default_factory=list)
    notes: str | None = None
    issuer_user_id: UUID | None = None
    reviewer_user_id: UUID | None = None
    approver_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    replayed: bool = False
    applied_event_id: UUID | None = None


class VerificationListSummary(StrictBase):
    id: UUID
    preaudit_id: UUID
    status: str
    effective_status: str
    revision: int
    issued_at: datetime
    valid_through: datetime
    framework_display_name: str | None = None
    framework_version: str | None = None
    synthetic_marker: str = SYNTHETIC_MARKER


class VerificationListResponse(StrictBase):
    verifications: list[VerificationListSummary]
    total: int
    limit: int
    offset: int


class VerificationEventItem(StrictBase):
    id: UUID
    verification_id: UUID
    sequence: int
    operation_id: UUID
    event_type: str
    actor_user_id: UUID
    actor_role: str
    prior_status: str | None = None
    new_status: str
    reason: str | None = None
    notes: str | None = None
    request_digest: str
    created_at: datetime


class VerificationHistoryResponse(StrictBase):
    verification_id: UUID
    events: list[VerificationEventItem]


class VerificationProjectionResponse(StrictBase):
    verification_id: UUID
    synthetic_marker: str
    test_qualification: str
    status: str
    effective_status: str
    effective_reason: str | None = None
    issued_at: datetime
    valid_through: datetime
    framework_id: str | None = None
    framework_version: str | None = None
    framework_display_name: str | None = None
    organization_display_name: str | None = None
    scope_summary: dict[str, Any] = Field(default_factory=dict)
    controls_count: int = 0
    limitations: list[str] = Field(default_factory=list)
    superseded_by_id: UUID | None = None
    supersedes_id: UUID | None = None
    public_disclosure_statement: str
