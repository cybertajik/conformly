import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.authz.roles import Role
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.db.session import get_db
from conformly.integrations.models import CredentialStatus
from conformly.integrations.service import (
    WebhookIdempotencyConflictError,
    WebhookReplayError,
    WebhookSignatureError,
    check_and_record_inbound_idempotency,
    finalize_inbound_idempotency,
    get_credential_signing_secret,
    list_integration_credentials,
    verify_webhook_signature,
)
from conformly.lms.contract import LmsCompletionPayload
from conformly.lms.models import AssignmentStatus, VerificationMethod
from conformly.lms.service import (
    create_training_assignment,
    create_training_course,
    list_training_assignments,
    list_training_completions,
    list_training_courses,
    record_training_completion,
)

lms_router = APIRouter(prefix="/v1/tenants/{tenant_id}/lms", tags=["LMS & Training Integration"])

PRIVILEGED_LMS_ROLES = frozenset({Role.OWNER, Role.ADMINISTRATOR, Role.COMPLIANCE_MANAGER})


def _check_lms_management(tenant: CurrentTenant) -> None:
    if tenant.role not in PRIVILEGED_LMS_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not authorized to manage training courses and assignments",
        )


class CreateCourseRequest(BaseModel):
    course_id: str = Field(min_length=2, max_length=128)
    title: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=2)
    version: str = Field(default="1.0", max_length=32)
    provider: str = Field(default="lms", max_length=128)
    duration_minutes: int = Field(default=30, ge=1)
    validity_period_days: int = Field(default=365, ge=1)


class CourseResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    course_id: str
    version: str
    title: str
    description: str
    provider: str
    duration_minutes: int
    validity_period_days: int
    is_active: bool
    created_at: datetime


class CreateAssignmentRequest(BaseModel):
    course_id: str = Field(min_length=2, max_length=128)
    workforce_email: str = Field(min_length=3, max_length=320)
    due_date: datetime
    user_id: UUID | None = None
    control_id: UUID | None = None
    control_type: str | None = None


class AssignmentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    course_id: str
    user_id: UUID | None = None
    workforce_email: str
    due_date: datetime
    status: str
    control_id: UUID | None = None
    control_type: str | None = None
    created_at: datetime


class CompletionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    assignment_id: UUID | None = None
    course_id: str
    course_version: str
    user_id: UUID | None = None
    workforce_email: str
    completed_at: datetime
    score: float | None = None
    certificate_id: str | None = None
    evidence_id: UUID | None = None
    idempotency_key: str
    verified_via: str
    created_at: datetime


@lms_router.post(
    "/courses",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_course(
    tenant_id: UUID,
    request: CreateCourseRequest,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> Any:
    """Register or update a training course in the catalog."""
    _check_lms_management(tenant)
    course = create_training_course(
        database,
        tenant_id=tenant.tenant_id,
        course_id=request.course_id,
        title=request.title,
        description=request.description,
        version=request.version,
        provider=request.provider,
        duration_minutes=request.duration_minutes,
        validity_period_days=request.validity_period_days,
    )
    database.commit()
    return CourseResponse(
        id=course.id,
        tenant_id=course.tenant_id,
        course_id=course.course_id,
        version=course.version,
        title=course.title,
        description=course.description,
        provider=course.provider,
        duration_minutes=course.duration_minutes,
        validity_period_days=course.validity_period_days,
        is_active=course.is_active,
        created_at=course.created_at,
    )


@lms_router.get("/courses", response_model=list[CourseResponse])
def list_courses(
    tenant_id: UUID,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> Any:
    """List all available training courses for the tenant."""
    courses = list_training_courses(database, tenant.tenant_id)
    return [
        CourseResponse(
            id=c.id,
            tenant_id=c.tenant_id,
            course_id=c.course_id,
            version=c.version,
            title=c.title,
            description=c.description,
            provider=c.provider,
            duration_minutes=c.duration_minutes,
            validity_period_days=c.validity_period_days,
            is_active=c.is_active,
            created_at=c.created_at,
        )
        for c in courses
    ]


@lms_router.post(
    "/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_training(
    tenant_id: UUID,
    request: CreateAssignmentRequest,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> Any:
    """Create a training assignment for a user or workforce member."""
    _check_lms_management(tenant)
    assignment = create_training_assignment(
        database,
        tenant_id=tenant.tenant_id,
        course_id=request.course_id,
        workforce_email=request.workforce_email,
        due_date=request.due_date,
        user_id=request.user_id,
        control_id=request.control_id,
        control_type=request.control_type,
        assigned_by_user_id=principal.user_id,
    )
    database.commit()
    return AssignmentResponse(
        id=assignment.id,
        tenant_id=assignment.tenant_id,
        course_id=assignment.course_id,
        user_id=assignment.user_id,
        workforce_email=assignment.workforce_email,
        due_date=assignment.due_date,
        status=str(assignment.status),
        control_id=assignment.control_id,
        control_type=assignment.control_type,
        created_at=assignment.created_at,
    )


@lms_router.get("/assignments", response_model=list[AssignmentResponse])
def list_assignments(
    tenant_id: UUID,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
    status: AssignmentStatus | None = None,
    user_id: UUID | None = None,
) -> Any:
    """List training assignments with optional status and user filter."""
    assignments = list_training_assignments(
        database, tenant.tenant_id, status=status, user_id=user_id
    )
    return [
        AssignmentResponse(
            id=a.id,
            tenant_id=a.tenant_id,
            course_id=a.course_id,
            user_id=a.user_id,
            workforce_email=a.workforce_email,
            due_date=a.due_date,
            status=str(a.status),
            control_id=a.control_id,
            control_type=a.control_type,
            created_at=a.created_at,
        )
        for a in assignments
    ]


@lms_router.get("/completions", response_model=list[CompletionResponse])
def list_completions(
    tenant_id: UUID,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> Any:
    """List verified training completions and linked compliance evidence."""
    completions = list_training_completions(database, tenant.tenant_id)
    return [
        CompletionResponse(
            id=c.id,
            tenant_id=c.tenant_id,
            assignment_id=c.assignment_id,
            course_id=c.course_id,
            course_version=c.course_version,
            user_id=c.user_id,
            workforce_email=c.workforce_email,
            completed_at=c.completed_at,
            score=c.score,
            certificate_id=c.certificate_id,
            evidence_id=c.evidence_id,
            idempotency_key=c.idempotency_key,
            verified_via=str(c.verified_via),
            created_at=c.created_at,
        )
        for c in completions
    ]


@lms_router.post("/webhooks/completion")
async def receive_lms_completion_webhook(
    tenant_id: UUID,
    request: Request,
    database: Annotated[Session, Depends(get_db)],
    codec: Annotated[EncryptedFieldCodec, Depends(get_encrypted_field_codec)],
    x_conformly_key_id: Annotated[str | None, Header()] = None,
    x_conformly_signature: Annotated[str | None, Header()] = None,
    x_conformly_timestamp: Annotated[str | None, Header()] = None,
    x_conformly_idempotency_key: Annotated[str | None, Header()] = None,
) -> Any:
    """Dedicated webhook intake for LMS completion events with signature, replay protection, and evidence mapping."""
    if not x_conformly_key_id or not x_conformly_signature or not x_conformly_timestamp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required webhook security headers: X-Conformly-Key-Id, X-Conformly-Signature, X-Conformly-Timestamp",
        )

    creds = list_integration_credentials(database, tenant_id)
    matched = next(
        (
            c
            for c in creds
            if c.key_id == x_conformly_key_id and c.status == CredentialStatus.ACTIVE
        ),
        None,
    )
    if matched is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown or revoked integration credential",
        )

    raw_body = await request.body()
    signing_secret = get_credential_signing_secret(codec, matched)

    try:
        verify_webhook_signature(
            raw_body,
            signature_header=x_conformly_signature,
            timestamp_header=x_conformly_timestamp,
            signing_secret=signing_secret,
        )
    except WebhookReplayError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Replay protection error: {exc}",
        ) from exc
    except WebhookSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Signature verification failed: {exc}",
        ) from exc

    try:
        payload_dict = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from exc

    event_id = (
        x_conformly_idempotency_key
        or payload_dict.get("event_id")
        or payload_dict.get("idempotency_key")
    )
    if not event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing idempotency event_id",
        )

    try:
        completion_payload = LmsCompletionPayload(
            event_id=str(event_id),
            tenant_id=str(tenant_id),
            course_id=str(payload_dict["course_id"]),
            course_version=str(payload_dict.get("course_version", "1.0")),
            learner_email=str(payload_dict["learner_email"]),
            completed_at=str(payload_dict.get("completed_at", datetime.now().isoformat())),
            passed=bool(payload_dict.get("passed", True)),
            assignment_id=payload_dict.get("assignment_id"),
            score=float(payload_dict["score"]) if payload_dict.get("score") is not None else None,
            certificate_id=payload_dict.get("certificate_id"),
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required field in completion payload: {exc}",
        ) from exc

    # Inbound event record for idempotency tracking
    try:
        event, is_new = check_and_record_inbound_idempotency(
            database,
            tenant_id=tenant_id,
            idempotency_key=str(event_id),
            event_topic="lms.course_completion",
            raw_body=raw_body,
            credential_id=matched.id,
        )
        if not is_new:
            return {
                "status": "idempotent_replay",
                "event_id": str(event_id),
                "cached_response": event.response_payload,
            }

        # Record completion & evidence linkage
        completion, evidence, _ = record_training_completion(
            database,
            codec,
            tenant_id=tenant_id,
            payload=completion_payload,
            raw_event_payload=payload_dict,
            verified_via=VerificationMethod.WEBHOOK,
        )

        response_data = {
            "status": "completed",
            "event_id": str(event_id),
            "completion_id": str(completion.id),
            "course_id": completion.course_id,
            "learner_email": completion.workforce_email,
            "evidence_id": str(evidence.id) if evidence else None,
            "verified": True,
        }
        finalize_inbound_idempotency(
            database,
            event,
            status_code=200,
            response_payload=response_data,
        )
        database.commit()
        return response_data

    except WebhookIdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
