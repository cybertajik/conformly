import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.db.session import get_db
from conformly.entitlements.service import is_module_enabled
from conformly.identity.models import Tenant, TenantStatus
from conformly.integrations.models import CredentialStatus, InboundWebhookEvent
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
from conformly.lms.policy import verify_lms_access
from conformly.lms.service import (
    create_training_assignment,
    create_training_course,
    list_training_assignments,
    list_training_completions,
    list_training_courses,
    record_training_completion,
)

lms_router = APIRouter(prefix="/v1/tenants/{tenant_id}/lms", tags=["LMS & Training Integration"])


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
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> Any:
    """Register or update a training course in the catalog."""
    verify_lms_access(database, tenant_id=tenant_id, principal=principal, tenant=tenant, operation="mutate")
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
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> Any:
    """List all registered courses for this tenant."""
    verify_lms_access(database, tenant_id=tenant_id, principal=principal, tenant=tenant, operation="read")
    courses = list_training_courses(database, tenant_id=tenant.tenant_id)
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
def create_assignment(
    tenant_id: UUID,
    request: CreateAssignmentRequest,
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> Any:
    """Assign a training course to a workforce member."""
    verify_lms_access(database, tenant_id=tenant_id, principal=principal, tenant=tenant, operation="mutate")
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
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
    status: str | None = None,
    user_id: UUID | None = None,
) -> Any:
    """List training assignments with optional status/user filtering."""
    verify_lms_access(database, tenant_id=tenant_id, principal=principal, tenant=tenant, operation="read")
    parsed_status = None
    if status is not None:
        try:
            parsed_status = AssignmentStatus(status)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid assignment status: {status}",
            ) from exc

    assignments = list_training_assignments(
        database,
        tenant_id=tenant.tenant_id,
        status=parsed_status,
        user_id=user_id,
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
    principal: CurrentPrincipal,
    tenant: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> Any:
    """List all verified training completions for this tenant."""
    verify_lms_access(database, tenant_id=tenant_id, principal=principal, tenant=tenant, operation="read")
    completions = list_training_completions(database, tenant_id=tenant.tenant_id)
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


@lms_router.post(
    "/webhooks/completion",
    status_code=status.HTTP_200_OK,
)
async def intake_lms_completion(
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
    # 1. Module entitlement check
    if not is_module_enabled(database, tenant_id, "lms"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="LMS module is not enabled for this tenant",
        )

    # 2. Tenant lifecycle check
    tenant_record = database.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    if tenant_record.status != TenantStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tenant status '{tenant_record.status.value}' prohibits LMS operations",
        )

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
    if len(raw_body) > 65536:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload exceeds maximum permitted size of 64KB",
        )

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
        payload_dict = json.loads(raw_body.decode("utf-8")) if raw_body else None
        if not isinstance(payload_dict, dict):
            raise ValueError("Payload must be a JSON object")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from exc

    if len(payload_dict) > 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload contains too many fields",
        )

    # Event ID must originate from signed body
    body_event_id = payload_dict.get("event_id") or payload_dict.get("idempotency_key")
    if not body_event_id or not isinstance(body_event_id, str) or not body_event_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Signed completion payload must contain a non-empty event_id string",
        )
    event_id = body_event_id.strip()

    # Reject unsigned header override / mismatch
    if x_conformly_idempotency_key is not None:
        if x_conformly_idempotency_key.strip() != event_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Conformly-Idempotency-Key header does not match signed event_id",
            )

    # Route and body tenant agreement
    body_tenant_id = payload_dict.get("tenant_id")
    if not body_tenant_id or not isinstance(body_tenant_id, str) or body_tenant_id.strip() != str(tenant_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload tenant_id does not match route tenant_id",
        )

    # Strict type checking: passed must be exact boolean True
    passed_raw = payload_dict.get("passed")
    if not isinstance(passed_raw, bool):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'passed' is required and must be an exact boolean",
        )
    if passed_raw is not True:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Training completion indicates failed status; only passed completions can be recorded as compliance evidence",
        )

    course_id_raw = payload_dict.get("course_id")
    if not course_id_raw or not isinstance(course_id_raw, str) or not course_id_raw.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'course_id' is required and must be a non-empty string",
        )
    course_id = course_id_raw.strip()

    course_version_raw = payload_dict.get("course_version")
    if not course_version_raw or not isinstance(course_version_raw, str) or not course_version_raw.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'course_version' is required and must be a non-empty string",
        )
    course_version = course_version_raw.strip()

    learner_email_raw = payload_dict.get("learner_email")
    if not learner_email_raw or not isinstance(learner_email_raw, str) or not learner_email_raw.strip() or "@" not in learner_email_raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'learner_email' is required and must be a valid email address",
        )
    learner_email = learner_email_raw.strip().lower()

    completed_at_raw = payload_dict.get("completed_at")
    if not completed_at_raw or not isinstance(completed_at_raw, str) or not completed_at_raw.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'completed_at' is required and must be an ISO 8601 datetime string",
        )
    try:
        completed_dt = datetime.fromisoformat(completed_at_raw)
        if completed_dt.tzinfo is None:
            raise ValueError("Timezone offset required")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Field 'completed_at' must be a valid ISO 8601 datetime with timezone: {exc}",
        ) from exc

    score_raw = payload_dict.get("score")
    score: float | None = None
    if score_raw is not None:
        if isinstance(score_raw, bool) or not isinstance(score_raw, (int, float)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Field 'score' must be a finite numeric value if provided",
            )
        import math
        if math.isnan(score_raw) or math.isinf(score_raw):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Field 'score' must be finite",
            )
        score = float(score_raw)

    assignment_id_raw = payload_dict.get("assignment_id")
    assignment_id: str | None = None
    if assignment_id_raw is not None:
        if not isinstance(assignment_id_raw, str) or not assignment_id_raw.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Field 'assignment_id' must be a valid non-empty UUID string if provided",
            )
        assignment_id = assignment_id_raw.strip()

    certificate_id_raw = payload_dict.get("certificate_id")
    certificate_id: str | None = None
    if certificate_id_raw is not None:
        if not isinstance(certificate_id_raw, str):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Field 'certificate_id' must be a string if provided",
            )
        certificate_id = certificate_id_raw.strip() or None

    completion_payload = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant_id),
        course_id=course_id,
        course_version=course_version,
        learner_email=learner_email,
        completed_at=completed_at_raw,
        passed=True,
        assignment_id=assignment_id,
        score=score,
        certificate_id=certificate_id,
    )

    # Check for idempotent replay
    import hashlib
    payload_sha256 = hashlib.sha256(raw_body).hexdigest()

    existing_event = database.scalar(
        select(InboundWebhookEvent).where(
            InboundWebhookEvent.tenant_id == tenant_id,
            InboundWebhookEvent.idempotency_key == event_id,
        )
    )
    if existing_event is not None:
        if existing_event.payload_sha256 and existing_event.payload_sha256 != payload_sha256:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Webhook event with this ID already processed with different payload",
            )
        return {
            "status": "idempotent_replay",
            "event_id": event_id,
            "cached_response": existing_event.response_payload,
        }

    try:
        # Record completion & evidence linkage (validates course, version, learner, assignment)
        completion, evidence, is_new = record_training_completion(
            database,
            codec,
            tenant_id=tenant_id,
            payload=completion_payload,
            raw_event_payload=payload_dict,
            verified_via=VerificationMethod.WEBHOOK,
        )

        response_data = {
            "status": "completed",
            "event_id": event_id,
            "completion_id": str(completion.id),
            "course_id": completion.course_id,
            "learner_email": completion.workforce_email,
            "evidence_id": str(evidence.id) if evidence else None,
            "verified": True,
        }

        event, _ = check_and_record_inbound_idempotency(
            database,
            tenant_id=tenant_id,
            idempotency_key=event_id,
            event_topic="lms.course_completion",
            raw_body=raw_body,
            credential_id=matched.id,
        )
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
