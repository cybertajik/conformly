from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.policy import AuthorizationDeniedError
from conformly.compliance.automation import run_continuous_compliance_cycle
from conformly.compliance.jobs import (
    ComplianceJobResult,
    run_evidence_expiration_check,
    run_overdue_tasks_check,
    run_policy_review_alerts,
)
from conformly.compliance.models import (
    ControlImplementationStatus,
    DigestFrequency,
    EvidenceStatus,
    FindingSeverity,
    PolicyStatus,
    RemediationStatus,
    TaskPriority,
    TaskStatus,
)
from conformly.compliance.service import (
    ComplianceService,
    EvidenceNotFoundError,
    FindingNotFoundError,
    IndependentPolicyApprovalRequiredError,
    InvalidControlReferenceError,
    InvalidFileReferenceError,
    InvalidStateTransitionError,
    OptimisticLockConflictError,
    PolicyNotFoundError,
    TaskNotFoundError,
)
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.db.session import get_db
from conformly.frameworks.models import ControlEntityType
from conformly.entitlements.dependencies import require_module

require_evidence = Depends(require_module("evidence"))
require_policies = Depends(require_module("policies"))
require_tasks = Depends(require_module("tasks"))
require_findings = Depends(require_module("findings"))
require_frameworks = Depends(require_module("frameworks"))

compliance_router = APIRouter(
    prefix="/v1/tenants/{tenant_id}/compliance", tags=["compliance_workspace"]
)


def get_compliance_service(
    database: Annotated[Session, Depends(get_db)],
    codec: Annotated[EncryptedFieldCodec, Depends(get_encrypted_field_codec)],
) -> ComplianceService:
    return ComplianceService(database, codec)


# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------


class EvidenceFileLinkResponse(BaseModel):
    id: UUID
    evidence_id: UUID
    file_id: UUID
    attached_by_user_id: UUID
    created_at: datetime


class EvidenceControlLinkResponse(BaseModel):
    id: UUID
    evidence_id: UUID
    control_type: ControlEntityType
    control_id: UUID
    linked_by_user_id: UUID
    created_at: datetime


class EvidenceResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    description: str
    classification: str
    status: EvidenceStatus
    owner_user_id: UUID
    valid_from: datetime | None
    valid_until: datetime | None
    version: int
    restricted_notes: str | None = None
    file_links: list[EvidenceFileLinkResponse] = []
    control_links: list[EvidenceControlLinkResponse] = []
    created_at: datetime
    updated_at: datetime


class CreateEvidenceRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    classification: str = Field("Internal", max_length=32)
    owner_user_id: UUID
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    restricted_notes: str | None = None


class UpdateEvidenceRequest(BaseModel):
    expected_version: int
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    classification: str | None = Field(None, max_length=32)
    owner_user_id: UUID | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    restricted_notes: str | None = None


class TransitionEvidenceRequest(BaseModel):
    target_status: EvidenceStatus
    expected_version: int
    reason: str | None = None


class AttachFileRequest(BaseModel):
    file_id: UUID


class LinkControlRequest(BaseModel):
    control_type: ControlEntityType
    control_id: UUID


class PolicyControlLinkResponse(BaseModel):
    id: UUID
    policy_id: UUID
    control_type: ControlEntityType
    control_id: UUID
    linked_by_user_id: UUID
    created_at: datetime


class PolicyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    description: str
    version_string: str
    status: PolicyStatus
    owner_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    review_cycle_days: int
    next_review_due: datetime | None
    version: int
    content: str | None
    classification: str
    restricted_content: str | None = None
    control_links: list[PolicyControlLinkResponse] = []
    created_at: datetime
    updated_at: datetime


class CreatePolicyRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    version_string: str = Field("1.0", max_length=50)
    review_cycle_days: int = Field(365, ge=1)
    content: str | None = None
    classification: str = Field("Internal", max_length=32)
    restricted_content: str | None = None


class UpdatePolicyRequest(BaseModel):
    expected_version: int
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    version_string: str | None = Field(None, max_length=50)
    review_cycle_days: int | None = Field(None, ge=1)
    content: str | None = None
    classification: str | None = Field(None, max_length=32)
    restricted_content: str | None = None


class VersionedActionRequest(BaseModel):
    expected_version: int


class ComplianceTaskResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    description: str
    due_date: datetime
    status: TaskStatus
    priority: TaskPriority
    assignee_user_id: UUID | None
    control_type: ControlEntityType | None
    control_id: UUID | None
    evidence_id: UUID | None
    policy_id: UUID | None
    version: int
    completed_at: datetime | None
    completed_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    due_date: datetime
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_user_id: UUID | None = None
    control_type: ControlEntityType | None = None
    control_id: UUID | None = None
    evidence_id: UUID | None = None
    policy_id: UUID | None = None


class UpdateTaskRequest(BaseModel):
    expected_version: int
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    due_date: datetime | None = None
    priority: TaskPriority | None = None
    assignee_user_id: UUID | None = None
    status: TaskStatus | None = None


class FindingResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    description: str
    severity: FindingSeverity
    remediation_status: RemediationStatus
    due_date: datetime | None
    owner_user_id: UUID | None
    control_type: ControlEntityType | None
    control_id: UUID | None
    remediation_plan: str | None
    remediation_summary: str | None
    resolved_at: datetime | None
    resolved_by_user_id: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class CreateFindingRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    severity: FindingSeverity = FindingSeverity.MEDIUM
    due_date: datetime | None = None
    owner_user_id: UUID | None = None
    control_type: ControlEntityType | None = None
    control_id: UUID | None = None
    remediation_plan: str | None = None


class UpdateFindingRequest(BaseModel):
    expected_version: int
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    severity: FindingSeverity | None = None
    due_date: datetime | None = None
    owner_user_id: UUID | None = None
    remediation_plan: str | None = None


class RemediationUpdateRequest(BaseModel):
    expected_version: int
    remediation_status: RemediationStatus
    remediation_summary: str | None = None


class ControlStatusRecordResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    control_type: ControlEntityType
    control_id: UUID
    status: ControlImplementationStatus
    assigned_owner_user_id: UUID | None
    notes: str | None
    last_assessed_at: datetime | None
    assessed_by_user_id: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class UpsertControlStatusRequest(BaseModel):
    status: ControlImplementationStatus
    assigned_owner_user_id: UUID | None = None
    notes: str | None = None
    expected_version: int | None = None


class UserNotificationPreferenceResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    email_enabled: bool
    digest_frequency: DigestFrequency
    notify_task_assigned: bool
    notify_task_due: bool
    notify_evidence_expired: bool
    notify_policy_review: bool
    notify_finding_raised: bool
    created_at: datetime
    updated_at: datetime


class UpdatePreferencesRequest(BaseModel):
    email_enabled: bool | None = None
    digest_frequency: DigestFrequency | None = None
    notify_task_assigned: bool | None = None
    notify_task_due: bool | None = None
    notify_evidence_expired: bool | None = None
    notify_policy_review: bool | None = None
    notify_finding_raised: bool | None = None


class JobExecutionResponse(BaseModel):
    expired_evidence: ComplianceJobResult
    overdue_tasks: ComplianceJobResult
    policy_alerts: ComplianceJobResult


class ContinuousComplianceCycleResponse(BaseModel):
    tenant_id: UUID
    expired_evidence_count: int
    expiring_evidence_warnings: int
    overdue_tasks_escalated: int
    policy_reviews_due: int
    vendor_reviews_due: int
    missing_dpas_flagged: int
    tasks_created: int
    notifications_enqueued: int
    executed_at: datetime


# -----------------------------------------------------------------------------
# Evidence Endpoints
# -----------------------------------------------------------------------------


@compliance_router.post(
    "/evidence", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED, dependencies=[require_evidence]
)
def create_evidence(
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: CreateEvidenceRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        evidence = service.create_evidence(
            principal,
            tenant,
            title=request.title,
            description=request.description,
            classification=request.classification,
            owner_user_id=request.owner_user_id,
            valid_from=request.valid_from,
            valid_until=request.valid_until,
            restricted_notes=request.restricted_notes,
        )
        return EvidenceResponse(
            id=evidence.id,
            tenant_id=evidence.tenant_id,
            title=evidence.title,
            description=evidence.description,
            classification=evidence.classification,
            status=evidence.status,
            owner_user_id=evidence.owner_user_id,
            valid_from=evidence.valid_from,
            valid_until=evidence.valid_until,
            version=evidence.version,
            restricted_notes=request.restricted_notes,
            file_links=[],
            control_links=[],
            created_at=evidence.created_at,
            updated_at=evidence.updated_at,
        )
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.get("/evidence", response_model=list[EvidenceResponse], dependencies=[require_evidence])
def list_evidence(
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
    evidence_status: Annotated[EvidenceStatus | None, Query(alias="status")] = None,
    classification: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    try:
        items = service.list_evidence(
            principal,
            tenant,
            status=evidence_status,
            classification=classification,
            limit=limit,
            offset=offset,
        )
        return [
            EvidenceResponse(
                id=item.id,
                tenant_id=item.tenant_id,
                title=item.title,
                description=item.description,
                classification=item.classification,
                status=item.status,
                owner_user_id=item.owner_user_id,
                valid_from=item.valid_from,
                valid_until=item.valid_until,
                version=item.version,
                restricted_notes=None,
                file_links=[
                    EvidenceFileLinkResponse(
                        id=fl.id,
                        evidence_id=fl.evidence_id,
                        file_id=fl.file_id,
                        attached_by_user_id=fl.attached_by_user_id,
                        created_at=fl.created_at,
                    )
                    for fl in item.file_links
                ],
                control_links=[
                    EvidenceControlLinkResponse(
                        id=cl.id,
                        evidence_id=cl.evidence_id,
                        control_type=cl.control_type,
                        control_id=cl.control_id,
                        linked_by_user_id=cl.linked_by_user_id,
                        created_at=cl.created_at,
                    )
                    for cl in item.control_links
                ],
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ]
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.get("/evidence/{evidence_id}", response_model=EvidenceResponse, dependencies=[require_evidence])
def get_evidence(
    evidence_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        item, notes = service.get_evidence(principal, tenant, evidence_id)
        return EvidenceResponse(
            id=item.id,
            tenant_id=item.tenant_id,
            title=item.title,
            description=item.description,
            classification=item.classification,
            status=item.status,
            owner_user_id=item.owner_user_id,
            valid_from=item.valid_from,
            valid_until=item.valid_until,
            version=item.version,
            restricted_notes=notes,
            file_links=[
                EvidenceFileLinkResponse(
                    id=fl.id,
                    evidence_id=fl.evidence_id,
                    file_id=fl.file_id,
                    attached_by_user_id=fl.attached_by_user_id,
                    created_at=fl.created_at,
                )
                for fl in item.file_links
            ],
            control_links=[
                EvidenceControlLinkResponse(
                    id=cl.id,
                    evidence_id=cl.evidence_id,
                    control_type=cl.control_type,
                    control_id=cl.control_id,
                    linked_by_user_id=cl.linked_by_user_id,
                    created_at=cl.created_at,
                )
                for cl in item.control_links
            ],
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
    except EvidenceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.patch("/evidence/{evidence_id}", response_model=EvidenceResponse, dependencies=[require_evidence])
def update_evidence(
    evidence_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: UpdateEvidenceRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        item = service.update_evidence(
            principal,
            tenant,
            evidence_id,
            expected_version=request.expected_version,
            title=request.title,
            description=request.description,
            classification=request.classification,
            owner_user_id=request.owner_user_id,
            valid_from=request.valid_from,
            valid_until=request.valid_until,
            restricted_notes=request.restricted_notes,
        )
        _, notes = service.get_evidence(principal, tenant, evidence_id)
        return EvidenceResponse(
            id=item.id,
            tenant_id=item.tenant_id,
            title=item.title,
            description=item.description,
            classification=item.classification,
            status=item.status,
            owner_user_id=item.owner_user_id,
            valid_from=item.valid_from,
            valid_until=item.valid_until,
            version=item.version,
            restricted_notes=notes,
            file_links=[
                EvidenceFileLinkResponse(
                    id=fl.id,
                    evidence_id=fl.evidence_id,
                    file_id=fl.file_id,
                    attached_by_user_id=fl.attached_by_user_id,
                    created_at=fl.created_at,
                )
                for fl in item.file_links
            ],
            control_links=[
                EvidenceControlLinkResponse(
                    id=cl.id,
                    evidence_id=cl.evidence_id,
                    control_type=cl.control_type,
                    control_id=cl.control_id,
                    linked_by_user_id=cl.linked_by_user_id,
                    created_at=cl.created_at,
                )
                for cl in item.control_links
            ],
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
    except EvidenceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except OptimisticLockConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.post("/evidence/{evidence_id}/transition", response_model=EvidenceResponse, dependencies=[require_evidence])
def transition_evidence(
    evidence_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: TransitionEvidenceRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        item = service.transition_evidence_status(
            principal,
            tenant,
            evidence_id,
            target_status=request.target_status,
            expected_version=request.expected_version,
            reason=request.reason,
        )
        _, notes = service.get_evidence(principal, tenant, evidence_id)
        return EvidenceResponse(
            id=item.id,
            tenant_id=item.tenant_id,
            title=item.title,
            description=item.description,
            classification=item.classification,
            status=item.status,
            owner_user_id=item.owner_user_id,
            valid_from=item.valid_from,
            valid_until=item.valid_until,
            version=item.version,
            restricted_notes=notes,
            file_links=[],
            control_links=[],
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
    except EvidenceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except OptimisticLockConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except InvalidStateTransitionError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.post("/evidence/{evidence_id}/files", response_model=EvidenceFileLinkResponse, dependencies=[require_evidence])
def attach_file(
    evidence_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: AttachFileRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        link = service.attach_file_to_evidence(
            principal, tenant, evidence_id=evidence_id, file_id=request.file_id
        )
        return EvidenceFileLinkResponse(
            id=link.id,
            evidence_id=link.evidence_id,
            file_id=link.file_id,
            attached_by_user_id=link.attached_by_user_id,
            created_at=link.created_at,
        )
    except EvidenceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except InvalidFileReferenceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.delete(
    "/evidence/{evidence_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[require_evidence]
)
def remove_file(
    evidence_id: UUID,
    file_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> None:
    try:
        service.remove_file_from_evidence(
            principal, tenant, evidence_id=evidence_id, file_id=file_id
        )
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.post(
    "/evidence/{evidence_id}/controls", response_model=EvidenceControlLinkResponse, dependencies=[require_evidence]
)
def link_control_to_evidence(
    evidence_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: LinkControlRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        link = service.link_control_to_evidence(
            principal,
            tenant,
            evidence_id=evidence_id,
            control_type=request.control_type,
            control_id=request.control_id,
        )
        return EvidenceControlLinkResponse(
            id=link.id,
            evidence_id=link.evidence_id,
            control_type=link.control_type,
            control_id=link.control_id,
            linked_by_user_id=link.linked_by_user_id,
            created_at=link.created_at,
        )
    except EvidenceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except InvalidControlReferenceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.delete(
    "/evidence/{evidence_id}/controls/{control_type}/{control_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_evidence],
)
def unlink_control_from_evidence(
    evidence_id: UUID,
    control_type: ControlEntityType,
    control_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> None:
    try:
        service.unlink_control_from_evidence(
            principal,
            tenant,
            evidence_id=evidence_id,
            control_type=control_type,
            control_id=control_id,
        )
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


# -----------------------------------------------------------------------------
# Policy Endpoints
# -----------------------------------------------------------------------------


@compliance_router.post(
    "/policies", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED, dependencies=[require_policies]
)
def create_policy(
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: CreatePolicyRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        policy = service.create_policy(
            principal,
            tenant,
            title=request.title,
            description=request.description,
            version_string=request.version_string,
            review_cycle_days=request.review_cycle_days,
            content=request.content,
            classification=request.classification,
            restricted_content=request.restricted_content,
        )
        return PolicyResponse(
            id=policy.id,
            tenant_id=policy.tenant_id,
            title=policy.title,
            description=policy.description,
            version_string=policy.version_string,
            status=policy.status,
            owner_user_id=policy.owner_user_id,
            approved_by_user_id=policy.approved_by_user_id,
            approved_at=policy.approved_at,
            review_cycle_days=policy.review_cycle_days,
            next_review_due=policy.next_review_due,
            version=policy.version,
            content=policy.content,
            classification=policy.classification,
            restricted_content=request.restricted_content,
            control_links=[],
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.get("/policies", response_model=list[PolicyResponse], dependencies=[require_policies])
def list_policies(
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
    policy_status: Annotated[PolicyStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    try:
        items = service.list_policies(
            principal, tenant, status=policy_status, limit=limit, offset=offset
        )
        return [
            PolicyResponse(
                id=item.id,
                tenant_id=item.tenant_id,
                title=item.title,
                description=item.description,
                version_string=item.version_string,
                status=item.status,
                owner_user_id=item.owner_user_id,
                approved_by_user_id=item.approved_by_user_id,
                approved_at=item.approved_at,
                review_cycle_days=item.review_cycle_days,
                next_review_due=item.next_review_due,
                version=item.version,
                content=item.content,
                classification=item.classification,
                restricted_content=None,
                control_links=[
                    PolicyControlLinkResponse(
                        id=cl.id,
                        policy_id=cl.policy_id,
                        control_type=cl.control_type,
                        control_id=cl.control_id,
                        linked_by_user_id=cl.linked_by_user_id,
                        created_at=cl.created_at,
                    )
                    for cl in item.control_links
                ],
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ]
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.get("/policies/{policy_id}", response_model=PolicyResponse, dependencies=[require_policies])
def get_policy(
    policy_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        policy, content = service.get_policy(principal, tenant, policy_id)
        return PolicyResponse(
            id=policy.id,
            tenant_id=policy.tenant_id,
            title=policy.title,
            description=policy.description,
            version_string=policy.version_string,
            status=policy.status,
            owner_user_id=policy.owner_user_id,
            approved_by_user_id=policy.approved_by_user_id,
            approved_at=policy.approved_at,
            review_cycle_days=policy.review_cycle_days,
            next_review_due=policy.next_review_due,
            version=policy.version,
            content=policy.content,
            classification=policy.classification,
            restricted_content=content,
            control_links=[
                PolicyControlLinkResponse(
                    id=cl.id,
                    policy_id=cl.policy_id,
                    control_type=cl.control_type,
                    control_id=cl.control_id,
                    linked_by_user_id=cl.linked_by_user_id,
                    created_at=cl.created_at,
                )
                for cl in policy.control_links
            ],
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
    except PolicyNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.patch("/policies/{policy_id}", response_model=PolicyResponse, dependencies=[require_policies])
def update_policy(
    policy_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: UpdatePolicyRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        policy = service.update_policy(
            principal,
            tenant,
            policy_id,
            expected_version=request.expected_version,
            title=request.title,
            description=request.description,
            version_string=request.version_string,
            review_cycle_days=request.review_cycle_days,
            content=request.content,
            classification=request.classification,
            restricted_content=request.restricted_content,
        )
        _, content = service.get_policy(principal, tenant, policy_id)
        return PolicyResponse(
            id=policy.id,
            tenant_id=policy.tenant_id,
            title=policy.title,
            description=policy.description,
            version_string=policy.version_string,
            status=policy.status,
            owner_user_id=policy.owner_user_id,
            approved_by_user_id=policy.approved_by_user_id,
            approved_at=policy.approved_at,
            review_cycle_days=policy.review_cycle_days,
            next_review_due=policy.next_review_due,
            version=policy.version,
            content=policy.content,
            classification=policy.classification,
            restricted_content=content,
            control_links=[],
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
    except PolicyNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except OptimisticLockConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.post("/policies/{policy_id}/submit-review", response_model=PolicyResponse, dependencies=[require_policies])
def submit_policy_review(
    policy_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: VersionedActionRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        policy = service.submit_policy_for_review(
            principal, tenant, policy_id, expected_version=request.expected_version
        )
        _, content = service.get_policy(principal, tenant, policy_id)
        return PolicyResponse(
            id=policy.id,
            tenant_id=policy.tenant_id,
            title=policy.title,
            description=policy.description,
            version_string=policy.version_string,
            status=policy.status,
            owner_user_id=policy.owner_user_id,
            approved_by_user_id=policy.approved_by_user_id,
            approved_at=policy.approved_at,
            review_cycle_days=policy.review_cycle_days,
            next_review_due=policy.next_review_due,
            version=policy.version,
            content=policy.content,
            classification=policy.classification,
            restricted_content=content,
            control_links=[],
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
    except PolicyNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except OptimisticLockConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except InvalidStateTransitionError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.post("/policies/{policy_id}/approve", response_model=PolicyResponse, dependencies=[require_policies])
def approve_policy(
    policy_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: VersionedActionRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        policy = service.approve_policy(
            principal, tenant, policy_id, expected_version=request.expected_version
        )
        _, content = service.get_policy(principal, tenant, policy_id)
        return PolicyResponse(
            id=policy.id,
            tenant_id=policy.tenant_id,
            title=policy.title,
            description=policy.description,
            version_string=policy.version_string,
            status=policy.status,
            owner_user_id=policy.owner_user_id,
            approved_by_user_id=policy.approved_by_user_id,
            approved_at=policy.approved_at,
            review_cycle_days=policy.review_cycle_days,
            next_review_due=policy.next_review_due,
            version=policy.version,
            content=policy.content,
            classification=policy.classification,
            restricted_content=content,
            control_links=[],
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
    except PolicyNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except OptimisticLockConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except IndependentPolicyApprovalRequiredError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except InvalidStateTransitionError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.post("/policies/{policy_id}/publish", response_model=PolicyResponse, dependencies=[require_policies])
def publish_policy(
    policy_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: VersionedActionRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        policy = service.publish_policy(
            principal, tenant, policy_id, expected_version=request.expected_version
        )
        _, content = service.get_policy(principal, tenant, policy_id)
        return PolicyResponse(
            id=policy.id,
            tenant_id=policy.tenant_id,
            title=policy.title,
            description=policy.description,
            version_string=policy.version_string,
            status=policy.status,
            owner_user_id=policy.owner_user_id,
            approved_by_user_id=policy.approved_by_user_id,
            approved_at=policy.approved_at,
            review_cycle_days=policy.review_cycle_days,
            next_review_due=policy.next_review_due,
            version=policy.version,
            content=policy.content,
            classification=policy.classification,
            restricted_content=content,
            control_links=[],
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
    except PolicyNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except OptimisticLockConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except InvalidStateTransitionError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.post("/policies/{policy_id}/archive", response_model=PolicyResponse, dependencies=[require_policies])
def archive_policy(
    policy_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: VersionedActionRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        policy = service.archive_policy(
            principal, tenant, policy_id, expected_version=request.expected_version
        )
        _, content = service.get_policy(principal, tenant, policy_id)
        return PolicyResponse(
            id=policy.id,
            tenant_id=policy.tenant_id,
            title=policy.title,
            description=policy.description,
            version_string=policy.version_string,
            status=policy.status,
            owner_user_id=policy.owner_user_id,
            approved_by_user_id=policy.approved_by_user_id,
            approved_at=policy.approved_at,
            review_cycle_days=policy.review_cycle_days,
            next_review_due=policy.next_review_due,
            version=policy.version,
            content=policy.content,
            classification=policy.classification,
            restricted_content=content,
            control_links=[],
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
    except PolicyNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except OptimisticLockConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.post("/policies/{policy_id}/controls", response_model=PolicyControlLinkResponse, dependencies=[require_policies])
def link_control_to_policy(
    policy_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: LinkControlRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        link = service.link_control_to_policy(
            principal,
            tenant,
            policy_id=policy_id,
            control_type=request.control_type,
            control_id=request.control_id,
        )
        return PolicyControlLinkResponse(
            id=link.id,
            policy_id=link.policy_id,
            control_type=link.control_type,
            control_id=link.control_id,
            linked_by_user_id=link.linked_by_user_id,
            created_at=link.created_at,
        )
    except PolicyNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except InvalidControlReferenceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.delete(
    "/policies/{policy_id}/controls/{control_type}/{control_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_policies],
)
def unlink_control_from_policy(
    policy_id: UUID,
    control_type: ControlEntityType,
    control_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> None:
    try:
        service.unlink_control_from_policy(
            principal,
            tenant,
            policy_id=policy_id,
            control_type=control_type,
            control_id=control_id,
        )
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


# -----------------------------------------------------------------------------
# Task Endpoints
# -----------------------------------------------------------------------------


@compliance_router.post(
    "/tasks", response_model=ComplianceTaskResponse, status_code=status.HTTP_201_CREATED, dependencies=[require_tasks]
)
def create_task(
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: CreateTaskRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        return service.create_task(
            principal,
            tenant,
            title=request.title,
            description=request.description,
            due_date=request.due_date,
            priority=request.priority,
            assignee_user_id=request.assignee_user_id,
            control_type=request.control_type,
            control_id=request.control_id,
            evidence_id=request.evidence_id,
            policy_id=request.policy_id,
        )
    except InvalidControlReferenceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.get("/tasks", response_model=list[ComplianceTaskResponse], dependencies=[require_tasks])
def list_tasks(
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority: Annotated[TaskPriority | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    try:
        return service.list_tasks(
            principal, tenant, status=task_status, priority=priority, limit=limit, offset=offset
        )
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.get("/tasks/{task_id}", response_model=ComplianceTaskResponse, dependencies=[require_tasks])
def get_task(
    task_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        return service.get_task(principal, tenant, task_id)
    except TaskNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.patch("/tasks/{task_id}", response_model=ComplianceTaskResponse, dependencies=[require_tasks])
def update_task(
    task_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: UpdateTaskRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        return service.update_task(
            principal,
            tenant,
            task_id,
            expected_version=request.expected_version,
            title=request.title,
            description=request.description,
            due_date=request.due_date,
            priority=request.priority,
            assignee_user_id=request.assignee_user_id,
            status=request.status,
        )
    except TaskNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except OptimisticLockConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.post("/tasks/{task_id}/complete", response_model=ComplianceTaskResponse, dependencies=[require_tasks])
def complete_task(
    task_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: VersionedActionRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        return service.complete_task(
            principal, tenant, task_id, expected_version=request.expected_version
        )
    except TaskNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except OptimisticLockConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


# -----------------------------------------------------------------------------
# Finding Endpoints
# -----------------------------------------------------------------------------


@compliance_router.post(
    "/findings", response_model=FindingResponse, status_code=status.HTTP_201_CREATED, dependencies=[require_findings]
)
def create_finding(
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: CreateFindingRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        return service.create_finding(
            principal,
            tenant,
            title=request.title,
            description=request.description,
            severity=request.severity,
            due_date=request.due_date,
            owner_user_id=request.owner_user_id,
            control_type=request.control_type,
            control_id=request.control_id,
            remediation_plan=request.remediation_plan,
        )
    except InvalidControlReferenceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.get("/findings", response_model=list[FindingResponse], dependencies=[require_findings])
def list_findings(
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
    severity: Annotated[FindingSeverity | None, Query()] = None,
    remediation_status: Annotated[RemediationStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    try:
        return service.list_findings(
            principal,
            tenant,
            severity=severity,
            remediation_status=remediation_status,
            limit=limit,
            offset=offset,
        )
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.get("/findings/{finding_id}", response_model=FindingResponse, dependencies=[require_findings])
def get_finding(
    finding_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        return service.get_finding(principal, tenant, finding_id)
    except FindingNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.patch("/findings/{finding_id}", response_model=FindingResponse, dependencies=[require_findings])
def update_finding(
    finding_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: UpdateFindingRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        return service.update_finding(
            principal,
            tenant,
            finding_id,
            expected_version=request.expected_version,
            title=request.title,
            description=request.description,
            severity=request.severity,
            due_date=request.due_date,
            owner_user_id=request.owner_user_id,
            remediation_plan=request.remediation_plan,
        )
    except FindingNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except OptimisticLockConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.post("/findings/{finding_id}/remediation", response_model=FindingResponse, dependencies=[require_findings])
def update_remediation(
    finding_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: RemediationUpdateRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        return service.update_remediation_status(
            principal,
            tenant,
            finding_id,
            expected_version=request.expected_version,
            remediation_status=request.remediation_status,
            remediation_summary=request.remediation_summary,
        )
    except FindingNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except OptimisticLockConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


# -----------------------------------------------------------------------------
# Control Status Record Posture Endpoints
# -----------------------------------------------------------------------------


@compliance_router.get("/control-statuses", response_model=list[ControlStatusRecordResponse], dependencies=[require_frameworks])
def get_control_statuses(
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        return service.get_control_status_matrix(principal, tenant)
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.put(
    "/control-statuses/{control_type}/{control_id}", response_model=ControlStatusRecordResponse, dependencies=[require_frameworks]
)
def upsert_control_status(
    control_type: ControlEntityType,
    control_id: UUID,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: UpsertControlStatusRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        return service.upsert_control_status(
            principal,
            tenant,
            control_type=control_type,
            control_id=control_id,
            status=request.status,
            assigned_owner_user_id=request.assigned_owner_user_id,
            notes=request.notes,
            expected_version=request.expected_version,
        )
    except InvalidControlReferenceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except OptimisticLockConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


# -----------------------------------------------------------------------------
# User Notification Preferences Endpoints
# -----------------------------------------------------------------------------


@compliance_router.get("/preferences", response_model=UserNotificationPreferenceResponse)
def get_preferences(
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        return service.get_or_create_user_preferences(principal, tenant)
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@compliance_router.put("/preferences", response_model=UserNotificationPreferenceResponse)
def update_preferences(
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    request: UpdatePreferencesRequest,
    service: Annotated[ComplianceService, Depends(get_compliance_service)],
) -> Any:
    try:
        return service.update_user_preferences(
            principal,
            tenant,
            email_enabled=request.email_enabled,
            digest_frequency=request.digest_frequency,
            notify_task_assigned=request.notify_task_assigned,
            notify_task_due=request.notify_task_due,
            notify_evidence_expired=request.notify_evidence_expired,
            notify_policy_review=request.notify_policy_review,
            notify_finding_raised=request.notify_finding_raised,
        )
    except AuthorizationDeniedError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


# -----------------------------------------------------------------------------
# Background Jobs Trigger Endpoint
# -----------------------------------------------------------------------------


@compliance_router.post("/jobs/run-expirations", response_model=JobExecutionResponse, dependencies=[require_frameworks])
def run_jobs(
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
    codec: Annotated[EncryptedFieldCodec, Depends(get_encrypted_field_codec)],
) -> Any:
    # Only Owner, Compliance Manager can trigger compliance batch jobs manually
    if tenant.role not in ("owner", "compliance_manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="job execution capability denied"
        )

    expired_result = run_evidence_expiration_check(database, codec, tenant_id=tenant.tenant_id)
    overdue_result = run_overdue_tasks_check(database, codec, tenant_id=tenant.tenant_id)
    alerts_result = run_policy_review_alerts(database, codec, tenant_id=tenant.tenant_id)

    return JobExecutionResponse(
        expired_evidence=expired_result,
        overdue_tasks=overdue_result,
        policy_alerts=alerts_result,
    )


@compliance_router.post("/cycle", response_model=ContinuousComplianceCycleResponse, dependencies=[require_frameworks])
def trigger_continuous_compliance_cycle(
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
    codec: Annotated[EncryptedFieldCodec, Depends(get_encrypted_field_codec)],
) -> Any:
    """Execute complete deterministic continuous compliance automation cycle for this tenant."""
    if tenant.role not in ("owner", "compliance_manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="compliance cycle execution capability denied",
        )

    result = run_continuous_compliance_cycle(database, codec, tenant_id=tenant.tenant_id)
    database.commit()
    return result

