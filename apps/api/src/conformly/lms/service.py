from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.compliance.models import (
    EvidenceControlLink,
    EvidenceItem,
    EvidenceStatus,
)
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.types import EncryptionContext
from conformly.frameworks.models import ControlEntityType
from conformly.identity.models import Membership, MembershipStatus
from conformly.lms.contract import LmsCompletionPayload
from conformly.lms.models import (
    AssignmentStatus,
    TrainingAssignment,
    TrainingCompletion,
    TrainingCourse,
    VerificationMethod,
)


def create_training_course(
    session: Session,
    *,
    tenant_id: UUID,
    course_id: str,
    title: str,
    description: str,
    version: str = "1.0",
    provider: str = "lms",
    duration_minutes: int = 30,
    validity_period_days: int = 365,
) -> TrainingCourse:
    """Register or synchronize a training course in the catalog."""
    stmt = select(TrainingCourse).where(
        TrainingCourse.tenant_id == tenant_id,
        TrainingCourse.course_id == course_id,
        TrainingCourse.version == version,
    )
    existing = session.scalar(stmt)
    if existing is not None:
        existing.title = title
        existing.description = description
        existing.provider = provider
        existing.duration_minutes = duration_minutes
        existing.validity_period_days = validity_period_days
        session.flush()
        return existing

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
    return course


def list_training_courses(
    session: Session,
    tenant_id: UUID,
) -> list[TrainingCourse]:
    """List all available training courses for a tenant."""
    stmt = (
        select(TrainingCourse)
        .where(TrainingCourse.tenant_id == tenant_id)
        .order_by(TrainingCourse.course_id.asc(), TrainingCourse.version.desc())
    )
    return list(session.scalars(stmt).all())


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
) -> TrainingAssignment:
    """Create a new training assignment linking a learner to a course and compliance control."""
    # Find matching user if not provided
    if user_id is None:
        from conformly.identity.models import User

        matched_user = session.scalar(
            select(User).where(User.email == workforce_email.strip().casefold())
        )
        if matched_user:
            user_id = matched_user.id

    assignment = TrainingAssignment(
        id=uuid4(),
        tenant_id=tenant_id,
        course_id=course_id,
        user_id=user_id,
        workforce_email=workforce_email.strip().casefold(),
        assigned_by_user_id=assigned_by_user_id,
        due_date=due_date,
        status=AssignmentStatus.ASSIGNED,
        control_id=control_id,
        control_type=control_type,
    )
    session.add(assignment)
    session.flush()

    record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER if assigned_by_user_id else AuditActorType.SYSTEM,
        actor_id=assigned_by_user_id,
        action="training.assigned",
        resource_type="training_assignment",
        resource_id=str(assignment.id),
        request_id=f"assign:{assignment.id}",
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "assignment_id": str(assignment.id),
            "course_id": course_id,
            "workforce_email": workforce_email.strip().casefold(),
            "status": str(AssignmentStatus.ASSIGNED),
        },
    )
    return assignment


def list_training_assignments(
    session: Session,
    tenant_id: UUID,
    *,
    status: AssignmentStatus | None = None,
    user_id: UUID | None = None,
) -> list[TrainingAssignment]:
    """List training assignments with optional status and user filtering."""
    stmt = select(TrainingAssignment).where(TrainingAssignment.tenant_id == tenant_id)
    if status is not None:
        stmt = stmt.where(TrainingAssignment.status == status)
    if user_id is not None:
        stmt = stmt.where(TrainingAssignment.user_id == user_id)
    stmt = stmt.order_by(TrainingAssignment.due_date.asc())
    return list(session.scalars(stmt).all())


def list_training_completions(
    session: Session,
    tenant_id: UUID,
) -> list[TrainingCompletion]:
    """List all verified training completions for a tenant."""
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
    """Idempotently process an LMS course completion event, generating compliance evidence.

    Returns (completion, evidence_item, is_new).
    """
    # 1. Check idempotency
    existing_stmt = select(TrainingCompletion).where(
        TrainingCompletion.tenant_id == tenant_id,
        TrainingCompletion.idempotency_key == payload.event_id,
    )
    existing = session.scalar(existing_stmt)
    if existing is not None:
        evidence = session.get(EvidenceItem, existing.evidence_id) if existing.evidence_id else None
        return existing, evidence, False

    # 2. Find matching assignment
    assignment: TrainingAssignment | None = None
    if payload.assignment_id:
        try:
            assign_uuid = UUID(payload.assignment_id)
            assignment = session.scalar(
                select(TrainingAssignment).where(
                    TrainingAssignment.id == assign_uuid,
                    TrainingAssignment.tenant_id == tenant_id,
                )
            )
        except (ValueError, TypeError):
            pass

    if assignment is None:
        assignment = session.scalar(
            select(TrainingAssignment)
            .where(
                TrainingAssignment.tenant_id == tenant_id,
                TrainingAssignment.course_id == payload.course_id,
                TrainingAssignment.workforce_email == payload.learner_email.strip().casefold(),
                TrainingAssignment.status.in_(
                    [AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS]
                ),
            )
            .order_by(TrainingAssignment.created_at.desc())
        )

    # 3. Determine course metadata
    course = session.scalar(
        select(TrainingCourse).where(
            TrainingCourse.tenant_id == tenant_id,
            TrainingCourse.course_id == payload.course_id,
            TrainingCourse.version == payload.course_version,
        )
    )
    course_title = course.title if course else payload.course_id
    validity_days = course.validity_period_days if course else 365

    try:
        completed_dt = datetime.fromisoformat(payload.completed_at.replace("Z", "+00:00"))
    except Exception:
        completed_dt = datetime.now(UTC)

    # 4. Determine user ownership for evidence item
    user_id = assignment.user_id if assignment else None
    if user_id is None:
        from conformly.identity.models import User

        matched_user = session.scalar(
            select(User).where(User.email == payload.learner_email.strip().casefold())
        )
        if matched_user:
            user_id = matched_user.id

    # Fallback to an active tenant member if no user_id found
    owner_user_id = user_id
    if owner_user_id is None:
        fallback_membership = session.scalar(
            select(Membership).where(
                Membership.tenant_id == tenant_id,
                Membership.status == MembershipStatus.ACTIVE,
            )
        )
        if fallback_membership:
            owner_user_id = fallback_membership.user_id

    evidence_item: EvidenceItem | None = None
    if owner_user_id is not None:
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
            owner_user_id=owner_user_id,
            valid_from=completed_dt,
            valid_until=completed_dt + timedelta(days=validity_days),
            version=1,
        )
        session.add(evidence_item)
        session.flush()

        # Link to mapped control if assignment has a control mapped
        if assignment and assignment.control_id and assignment.control_type:
            c_type = (
                ControlEntityType.CUSTOM
                if assignment.control_type == "custom"
                else ControlEntityType.CANONICAL
            )
            link = EvidenceControlLink(
                id=uuid4(),
                tenant_id=tenant_id,
                evidence_id=evidence_id,
                control_type=c_type,
                control_id=assignment.control_id,
                linked_by_user_id=owner_user_id,
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
                "title": evidence_item.title,
                "status": str(EvidenceStatus.VALID),
            },
        )

    # 5. Encrypt raw payload for audit and legal preservation
    enc_context = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="training_completion",
        resource_id=payload.event_id,
        field_name="raw_payload",
    )
    raw_encrypted = None
    if raw_event_payload:
        import json

        raw_json_str = json.dumps(raw_event_payload, sort_keys=True)
        raw_encrypted = codec.encrypt_text(raw_json_str, enc_context)

    # 6. Create TrainingCompletion record
    completion_id = uuid4()
    completion = TrainingCompletion(
        id=completion_id,
        tenant_id=tenant_id,
        assignment_id=assignment.id if assignment else None,
        course_id=payload.course_id,
        course_version=payload.course_version,
        user_id=user_id,
        workforce_email=payload.learner_email.strip().casefold(),
        completed_at=completed_dt,
        score=payload.score,
        certificate_id=payload.certificate_id,
        evidence_id=evidence_item.id if evidence_item else None,
        idempotency_key=payload.event_id,
        verified_via=verified_via,
        raw_payload_encrypted=raw_encrypted,
    )
    session.add(completion)

    # 7. Update assignment status
    if assignment:
        assignment.status = AssignmentStatus.COMPLETED

    session.flush()

    record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.SYSTEM,
        actor_id=None,
        action="training.completed",
        resource_type="training_completion",
        resource_id=str(completion_id),
        request_id=f"completion:{payload.event_id}",
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "completion_id": str(completion_id),
            "course_id": payload.course_id,
            "workforce_email": payload.learner_email.strip().casefold(),
            "status": "completed",
            "score": payload.score,
            "evidence_id": str(evidence_item.id) if evidence_item else None,
        },
    )

    return completion, evidence_item, True
