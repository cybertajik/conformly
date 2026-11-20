"""LMS and Training compliance integration service."""

from datetime import UTC, datetime, timedelta, timezone
import json
import math
import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.compliance.models import (
    ControlEntityType,
    EvidenceControlLink,
    EvidenceItem,
    EvidenceStatus,
)
from conformly.crypto.fields import EncryptedFieldCodec, EncryptionContext
from conformly.identity.models import Membership, MembershipStatus, User, UserStatus
from conformly.frameworks.models import (
    AdoptionStatus,
    CanonicalControl,
    CustomControl,
    TenantFrameworkAdoption,
)
from conformly.lms.contract import (
    LmsAssignmentPayload,
    LmsCompletionPayload,
)
from conformly.lms.models import (
    AssignmentStatus,
    TrainingAssignment,
    TrainingCompletion,
    TrainingCourse,
    VerificationMethod,
)

logger = logging.getLogger(__name__)


def list_training_courses(
    session: Session,
    tenant_id: UUID,
    *,
    is_active_only: bool = True,
) -> list[TrainingCourse]:
    stmt = select(TrainingCourse).where(TrainingCourse.tenant_id == tenant_id)
    if is_active_only:
        stmt = stmt.where(TrainingCourse.is_active == True)
    stmt = stmt.order_by(TrainingCourse.created_at.desc())
    return list(session.scalars(stmt).all())


def create_training_course(
    session: Session,
    *,
    tenant_id: UUID,
    course_id: str,
    title: str,
    description: str,
    version: str = "1.0",
    provider: str = "lms",
    duration_minutes: int | None = None,
    validity_period_days: int = 365,
    request_id: str | None = None,
) -> TrainingCourse:
    existing = session.scalar(
        select(TrainingCourse).where(
            TrainingCourse.tenant_id == tenant_id,
            TrainingCourse.course_id == course_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Course with ID '{course_id}' already registered for this tenant",
        )

    course = TrainingCourse(
        id=uuid4(),
        tenant_id=tenant_id,
        course_id=course_id,
        version=version,
        title=title,
        description=description,
        provider=provider,
        duration_minutes=duration_minutes,
        validity_period_days=validity_period_days,
        is_active=True,
    )
    session.add(course)
    session.flush()

    record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=None,
        action="training_course.register",
        resource_type="training_course",
        resource_id=str(course.id),
        request_id=request_id or f"course-reg:{course.id}",
        outcome=AuditOutcome.SUCCESS,
        metadata={"course_id": course_id, "title": title},
    )
    return course


def list_training_assignments(
    session: Session,
    tenant_id: UUID,
    *,
    status: AssignmentStatus | None = None,
    status_filter: AssignmentStatus | None = None,
    user_id: UUID | None = None,
    workforce_email: str | None = None,
) -> list[TrainingAssignment]:
    eff_status = status or status_filter
    stmt = select(TrainingAssignment).where(TrainingAssignment.tenant_id == tenant_id)
    if eff_status is not None:
        stmt = stmt.where(TrainingAssignment.status == eff_status)
    if user_id is not None:
        stmt = stmt.where(TrainingAssignment.user_id == user_id)
    if workforce_email is not None:
        stmt = stmt.where(
            TrainingAssignment.workforce_email == workforce_email.strip().casefold()
        )
    stmt = stmt.order_by(TrainingAssignment.due_date.asc())
    return list(session.scalars(stmt).all())



def validate_control_reference(
    session: Session,
    tenant_id: UUID,
    control_id: UUID | None,
    control_type: str | None,
) -> tuple[UUID | None, ControlEntityType | None]:
    """Validate control_id/control_type optional pair against legacy canonical/custom catalogs."""
    if control_id is None and control_type is None:
        return None, None
    if (control_id is None) != (control_type is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Both control_id and control_type must be provided together or omitted",
        )
    assert control_type is not None and control_id is not None
    ctype_norm = control_type.strip().lower()
    if ctype_norm not in ("canonical", "custom"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown control_type '{control_type}'. Only 'canonical' or 'custom' are permitted",
        )
    if ctype_norm == "custom":
        custom = session.scalar(
            select(CustomControl).where(
                CustomControl.id == control_id,
                CustomControl.tenant_id == tenant_id,
            )
        )
        if custom is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Custom control '{control_id}' does not exist or does not belong to tenant",
            )
        return control_id, ControlEntityType.CUSTOM
    else:
        canonical = session.scalar(
            select(CanonicalControl).where(CanonicalControl.id == control_id)
        )
        if canonical is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Canonical control '{control_id}' does not exist in framework catalog",
            )
        adoption = session.scalar(
            select(TenantFrameworkAdoption).where(
                TenantFrameworkAdoption.tenant_id == tenant_id,
                TenantFrameworkAdoption.framework_version_id == canonical.framework_version_id,
                TenantFrameworkAdoption.status == AdoptionStatus.ACTIVE,
            )
        )
        if adoption is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Canonical control '{control_id}' does not belong to an active framework adoption in this tenant",
            )
        return control_id, ControlEntityType.CANONICAL

def create_training_assignment(
    session: Session,
    *,
    tenant_id: UUID,
    course_id: str,
    workforce_email: str,
    due_date: datetime,
    user_id: UUID | None = None,
    control_id: UUID | None = None,
    control_type: str | None = None,
    assigned_by_user_id: UUID | None = None,
    request_id: str | None = None,
) -> TrainingAssignment:
    # Validate control reference optional pair
    valid_ctrl_id, valid_ctrl_type_enum = validate_control_reference(
        session, tenant_id, control_id, control_type
    )

    active_courses = list(session.scalars(
        select(TrainingCourse).where(
            TrainingCourse.tenant_id == tenant_id,
            TrainingCourse.course_id == course_id,
            TrainingCourse.is_active == True,
        )
    ).all())
    if len(active_courses) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course '{course_id}' not found in active catalog",
        )
    if len(active_courses) > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Multiple active versions found for course '{course_id}'; active course version is ambiguous",
        )
    course = active_courses[0]

    email_clean = workforce_email.strip().casefold()
    member_stmt = (
        select(User, Membership)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.tenant_id == tenant_id,
            Membership.status == MembershipStatus.ACTIVE,
            User.status == UserStatus.ACTIVE,
            User.email == email_clean,
        )
    )
    member_res = session.execute(member_stmt).first()
    if not member_res:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Learner email '{workforce_email}' does not belong to an active user and member of this organization",
        )
    active_user, _ = member_res
    if user_id is not None and user_id != active_user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Explicit user_id does not match active learner user ID",
        )
    effective_user_id = active_user.id

    assignment = TrainingAssignment(
        id=uuid4(),
        tenant_id=tenant_id,
        course_id=course_id,
        user_id=effective_user_id,
        workforce_email=email_clean,
        due_date=due_date,
        status=AssignmentStatus.ASSIGNED,
        control_id=valid_ctrl_id,
        control_type=control_type.strip().lower() if control_type else None,
    )
    session.add(assignment)
    session.flush()

    record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=assigned_by_user_id or effective_user_id,
        action="training_assignment.create",
        resource_type="training_assignment",
        resource_id=str(assignment.id),
        request_id=request_id or f"assign:{assignment.id}",
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "course_id": course_id,
            "due_date": due_date.isoformat(),
        },
    )
    return assignment


def list_training_completions(
    session: Session,
    tenant_id: UUID,
) -> list[TrainingCompletion]:
    stmt = (
        select(TrainingCompletion)
        .where(TrainingCompletion.tenant_id == tenant_id)
        .order_by(TrainingCompletion.completed_at.desc())
    )
    return list(session.scalars(stmt).all())


def record_training_completion(
    session: Session,
    codec: EncryptedFieldCodec,
    *,
    tenant_id: UUID,
    payload: LmsCompletionPayload,
    raw_event_payload: dict[str, Any] | None = None,
    verified_via: VerificationMethod = VerificationMethod.WEBHOOK,
) -> tuple[TrainingCompletion, EvidenceItem | None, bool]:
    """Process an LMS course completion event with strict correlation and evidence minting.

    Returns (completion, evidence_item, is_new).
    Raises HTTPException on validation or correlation failure.
    """
    # 0. Strict runtime payload validation before any lookup/writes
    if not isinstance(payload.tenant_id, str) or not payload.tenant_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload tenant_id must be a non-empty string",
        )
    if payload.tenant_id.strip() != str(tenant_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload tenant_id does not match service tenant_id",
        )

    if not isinstance(payload.passed, bool) or payload.passed is not True:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Training completion indicates failed status; only passed completions can be recorded as compliance evidence",
        )

    for field_name, val in [
        ("event_id", payload.event_id),
        ("course_id", payload.course_id),
        ("course_version", payload.course_version),
        ("learner_email", payload.learner_email),
    ]:
        if not isinstance(val, str) or not val.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Payload {field_name} must be a non-empty string",
            )

    if payload.score is not None:
        if (
            isinstance(payload.score, bool)
            or not isinstance(payload.score, (int, float))
            or not math.isfinite(payload.score)
            or payload.score < 0.0
            or payload.score > 100.0
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid score value: must be a finite float between 0 and 100",
            )

    try:
        completed_dt = datetime.fromisoformat(payload.completed_at)
        if completed_dt.tzinfo is None:
            raise ValueError("Timezone offset required")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid completed_at datetime format: {exc}",
        ) from exc

    # 1. Deduplicate on event_id idempotency and verify all persisted event semantics
    existing_stmt = select(TrainingCompletion).where(
        TrainingCompletion.tenant_id == tenant_id,
        TrainingCompletion.idempotency_key == payload.event_id,
    )
    existing = session.scalar(existing_stmt)
    if existing is not None:
        # Normalize timestamps for equivalent instant comparison
        existing_dt = existing.completed_at if existing.completed_at.tzinfo is not None else existing.completed_at.replace(tzinfo=timezone.utc)
        existing_utc = existing_dt.astimezone(timezone.utc)
        incoming_utc = completed_dt.astimezone(timezone.utc)
        time_diff = abs((existing_utc - incoming_utc).total_seconds())

        # Check score nullability and value
        score_conflict = False
        if (existing.score is None) != (payload.score is None):
            score_conflict = True
        elif existing.score is not None and payload.score is not None:
            if abs(float(existing.score) - float(payload.score)) > 1e-6:
                score_conflict = True

        # Check certificate_id
        existing_cert = (existing.certificate_id or "").strip() or None
        incoming_cert = (payload.certificate_id or "").strip() or None
        cert_conflict = existing_cert != incoming_cert

        # Check assignment intent
        assignment_conflict = False
        if payload.assignment_id:
            if existing.assignment_id is None or str(existing.assignment_id) != payload.assignment_id.strip():
                assignment_conflict = True
        else:
            if existing.raw_payload_encrypted and codec is not None:
                try:
                    enc_ctx = EncryptionContext(
                        tenant_id=tenant_id,
                        resource_type="training_completion",
                        resource_id=payload.event_id,
                        field_name="raw_payload",
                    )
                    dec_str = codec.decrypt_text(existing.raw_payload_encrypted, enc_ctx)
                    orig_dict = json.loads(dec_str)
                    if orig_dict.get("assignment_id"):
                        assignment_conflict = True
                except Exception:
                    pass

        if (
            existing.course_id != payload.course_id
            or existing.course_version != payload.course_version
            or existing.workforce_email.casefold() != payload.learner_email.strip().casefold()
            or assignment_conflict
            or time_diff > 0.001
            or score_conflict
            or cert_conflict
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reused event_id with altered course, learner, assignment, timestamp, score, or certificate semantics",
            )
        evidence = session.get(EvidenceItem, existing.evidence_id) if existing.evidence_id else None
        return existing, evidence, False

    # 2. Resolve learner in same tenant (must be active user AND active member)
    email_clean = payload.learner_email.strip().casefold()
    user_stmt = select(User).where(func.lower(User.email) == email_clean)
    user = session.scalar(user_stmt)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Learner '{payload.learner_email}' is not an active member of this tenant",
        )
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Learner '{payload.learner_email}' is not an active user",
        )
    user_id = user.id

    membership_stmt = select(Membership).where(
        Membership.tenant_id == tenant_id,
        Membership.user_id == user_id,
        Membership.status == MembershipStatus.ACTIVE,
    )
    membership = session.scalar(membership_stmt)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Learner '{payload.learner_email}' is not an active member of this tenant",
        )

    # 3. Resolve assignment
    assignment: TrainingAssignment | None = None
    if payload.assignment_id:
        try:
            assign_uuid = UUID(payload.assignment_id.strip())
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid assignment_id format: {payload.assignment_id}",
            ) from exc

        assign_stmt = select(TrainingAssignment).where(
            TrainingAssignment.id == assign_uuid,
            TrainingAssignment.tenant_id == tenant_id,
        )
        assignment = session.scalar(assign_stmt)
        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Referenced assignment not found in this tenant: {payload.assignment_id}",
            )
        if assignment.course_id != payload.course_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Assignment course_id does not match callback course: '{assignment.course_id}' != '{payload.course_id}'",
            )
        if assignment.workforce_email.casefold() != email_clean:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Assignment workforce_email does not match callback learner",
            )
        if assignment.user_id is not None and assignment.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Assignment user does not match validated learner",
            )
        if assignment.status not in (
            AssignmentStatus.ASSIGNED,
            AssignmentStatus.IN_PROGRESS,
            AssignmentStatus.OVERDUE,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Assignment status '{assignment.status.value}' is not eligible for completion",
            )

    # 4. Validate active registered course & version with ambiguity rejection
    active_courses = list(session.scalars(
        select(TrainingCourse).where(
            TrainingCourse.tenant_id == tenant_id,
            TrainingCourse.course_id == payload.course_id,
            TrainingCourse.is_active == True,
        )
    ).all())
    if len(active_courses) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course '{payload.course_id}' not found or inactive in this tenant",
        )
    if len(active_courses) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Multiple active versions found for course '{payload.course_id}'. Ambiguous course reference",
        )
    course = active_courses[0]
    if course.version != payload.course_version:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Course version mismatch: registered version '{course.version}' != callback version '{payload.course_version}'",
        )
    validity_days = course.validity_period_days or 365
    course_title = course.title

    # 5. Implicit match if assignment was omitted
    if assignment is None:
        active_assignments = list(session.scalars(
            select(TrainingAssignment)
            .where(
                TrainingAssignment.tenant_id == tenant_id,
                TrainingAssignment.course_id == payload.course_id,
                TrainingAssignment.workforce_email == email_clean,
                TrainingAssignment.status.in_(
                    [AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS, AssignmentStatus.OVERDUE]
                ),
            )
        ).all())
        if len(active_assignments) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No active assignment found for learner '{payload.learner_email}' and course '{payload.course_id}'",
            )
        if len(active_assignments) > 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Multiple active assignments found for this course and learner; explicit assignment_id required",
            )
        assignment = active_assignments[0]
        if assignment.user_id is not None and assignment.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Assignment user does not match validated learner",
            )

    # 6. Pre-validate assignment control reference BEFORE any EvidenceItem creation or flush!
    valid_ctrl_id, valid_ctrl_type = validate_control_reference(
        session, tenant_id, assignment.control_id, assignment.control_type
    )

    # 7. Mint EvidenceItem for passed completion (ONLY after all validations pass)
    evidence_id = uuid4()
    evidence_item = EvidenceItem(
        id=evidence_id,
        tenant_id=tenant_id,
        title=f"LMS Training Completion: {course_title} ({payload.learner_email})",
        description=(
            f"Automated compliance evidence verified via signed LMS completion webhook. "
            f"Course ID: {payload.course_id} v{payload.course_version}. "
            f"Score: {payload.score if payload.score is not None else 'N/A'}. "
            f"Certificate: {payload.certificate_id or 'N/A'}."
        ),
        classification="Internal",
        status=EvidenceStatus.VALID,
        owner_user_id=user_id,
        valid_from=completed_dt,
        valid_until=completed_dt + timedelta(days=validity_days),
        version=1,
    )
    session.add(evidence_item)
    session.flush()

    # Link to mapped control if assignment has a valid control mapped
    if valid_ctrl_id and valid_ctrl_type:
        link = EvidenceControlLink(
            id=uuid4(),
            tenant_id=tenant_id,
            evidence_id=evidence_id,
            control_type=valid_ctrl_type,
            control_id=valid_ctrl_id,
            linked_by_user_id=user_id,
        )
        session.add(link)

    record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.SYSTEM,
        actor_id=None,
        action="evidence.create",
        resource_type="evidence_item",
        resource_id=str(evidence_id),
        request_id=f"evidence-lms:{payload.event_id}",
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "evidence_id": str(evidence_id),
        },
    )

    assignment.status = AssignmentStatus.COMPLETED
    assignment.completed_at = completed_dt

    # 8. Encrypt raw payload for audit and legal preservation
    enc_context = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="training_completion",
        resource_id=payload.event_id,
        field_name="raw_payload",
    )
    raw_encrypted = None
    if raw_event_payload:
        raw_json_str = json.dumps(raw_event_payload, sort_keys=True)
        raw_encrypted = codec.encrypt_text(raw_json_str, enc_context)

    # 9. Create TrainingCompletion record
    completion_id = uuid4()
    completion = TrainingCompletion(
        id=completion_id,
        tenant_id=tenant_id,
        assignment_id=assignment.id,
        course_id=payload.course_id,
        course_version=payload.course_version,
        user_id=user_id,
        workforce_email=email_clean,
        completed_at=completed_dt,
        score=payload.score,
        certificate_id=payload.certificate_id,
        evidence_id=evidence_id,
        idempotency_key=payload.event_id,
        verified_via=verified_via,
        raw_payload_encrypted=raw_encrypted,
    )
    session.add(completion)
    session.flush()

    record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.SYSTEM,
        actor_id=None,
        action="training_completion.verify",
        resource_type="training_completion",
        resource_id=str(completion.id),
        request_id=f"verify-lms:{payload.event_id}",
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "completion_id": str(completion.id),
            "course_id": payload.course_id,
            "evidence_id": str(evidence_id),
        },
    )

    return completion, evidence_item, True
