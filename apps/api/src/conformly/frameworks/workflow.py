"""Structured evidence requests for an explicitly adopted framework revision."""

import threading
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint, Uuid, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import AuthorizationDeniedError, Principal, TenantContext, authorize
from conformly.authz.roles import Capability
from conformly.compliance.models import EvidenceFileLink, EvidenceItem, EvidenceStatus
from conformly.compliance.service import ComplianceService
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from conformly.entitlements.service import is_framework_allowed, is_module_enabled
from conformly.frameworks.models import (
    AdoptionStatus,
    EvidenceSpecification,
    Framework,
    FrameworkVersion,
    ReleaseState,
    TenantFrameworkAdoption,
)
from conformly.storage.models import StoredFile, StoredFileStatus
from conformly.tenancy.rls import set_rls_context


class WorkflowInputError(ValueError):
    """Unavailable reference or unsuitable evidence; safe to expose to an authorized caller."""


class FrameworkEvidenceRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "framework_evidence_requests"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "adoption_id", "specification_id", name="uq_framework_request_spec"
        ),
        Index("ix_framework_requests_tenant_adoption", "tenant_id", "adoption_id"),
    )
    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    adoption_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenant_framework_adoptions.id"), nullable=False
    )
    specification_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("evidence_specifications.id"), nullable=False
    )
    task_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("compliance_tasks.id"), nullable=False)
    evidence_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("evidence_items.id"))
    evidence_version: Mapped[int | None] = mapped_column(Integer)
    observation_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observation_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by_user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def request_evidence_problem(
    session: Session,
    request: FrameworkEvidenceRequest,
    spec: EvidenceSpecification,
    *,
    now: datetime,
) -> str | None:
    """Recheck an accepted binding at evaluation/issuance time; never trust a cached status."""
    if request.accepted_at is None or request.accepted_by_user_id is None:
        return "review_required"
    evidence = session.scalar(
        select(EvidenceItem).where(
            EvidenceItem.id == request.evidence_id,
            EvidenceItem.tenant_id == request.tenant_id,
        )
    )
    if evidence is None:
        return "missing_evidence"
    if evidence.version != request.evidence_version:
        return "evidence_changed"
    if evidence.status != EvidenceStatus.VALID:
        return "evidence_not_valid"
    if evidence.valid_from and utc(evidence.valid_from) > now:
        return "evidence_not_yet_valid"
    if evidence.valid_until and utc(evidence.valid_until) <= now:
        return "evidence_expired"
    levels = {"Public": 0, "Internal": 1, "Confidential": 2, "Restricted": 3}
    if (
        spec.confidentiality_level not in levels
        or evidence.classification not in levels
        or levels[evidence.classification] < levels[spec.confidentiality_level]
    ):
        return "classification_insufficient"
    if request.observation_start is None or request.observation_end is None:
        return "observation_period_missing"
    start, end = utc(request.observation_start), utc(request.observation_end)
    if start > end or end > now:
        return "observation_period_invalid"
    if spec.observation_period_days and end - start < timedelta(days=spec.observation_period_days):
        return "observation_period_short"
    if spec.validity_period_days and end + timedelta(days=spec.validity_period_days) <= now:
        return "observation_expired"
    if (
        spec.review_cadence_days
        and utc(request.accepted_at) + timedelta(days=spec.review_cadence_days) <= now
    ):
        return "review_expired"
    if spec.original_file_required:
        file_id = session.scalar(
            select(StoredFile.id)
            .join(
                EvidenceFileLink,
                EvidenceFileLink.file_id == StoredFile.id,
            )
            .where(
                EvidenceFileLink.tenant_id == request.tenant_id,
                EvidenceFileLink.evidence_id == evidence.id,
                StoredFile.tenant_id == request.tenant_id,
                StoredFile.status == StoredFileStatus.ACTIVE,
            )
        )
        if file_id is None:
            return "original_file_missing"
    return None


def serialize_request(row: FrameworkEvidenceRequest) -> dict[str, Any]:
    return {
        column.name: (
            value.isoformat()
            if isinstance(value, datetime)
            else str(value)
            if isinstance(value, UUID)
            else value
        )
        for column in row.__table__.columns
        for value in [getattr(row, column.name)]
    }


class FrameworkWorkflowService:
    _process_lock = threading.RLock()

    def __init__(self, session: Session, codec: EncryptedFieldCodec):
        self.session = session
        self.compliance = ComplianceService(session, codec)

    def _adoption(
        self,
        principal: Principal,
        context: TenantContext,
        adoption_id: UUID,
        capability: Capability,
    ) -> TenantFrameworkAdoption:
        authorize(principal, context, capability)
        # These existing models represent tenant-wide scope only. Never widen scoped membership.
        if context.legal_entity_id or context.business_unit_id:
            raise AuthorizationDeniedError(
                "Tenant-wide framework workflow requires tenant-wide scope"
            )
        set_rls_context(
            self.session,
            user_id=principal.user_id,
            tenant_id=context.tenant_id,
            tenant_verified=True,
        )
        row = self.session.scalar(
            select(TenantFrameworkAdoption)
            .where(
                TenantFrameworkAdoption.id == adoption_id,
                TenantFrameworkAdoption.tenant_id == context.tenant_id,
            )
            .with_for_update()
        )
        if row is None:
            raise WorkflowInputError("Framework adoption unavailable")
        version = self.session.get(FrameworkVersion, row.framework_version_id)
        framework = self.session.get(Framework, row.framework_id)
        if (
            row.status != AdoptionStatus.ACTIVE
            or version is None
            or version.release_state != ReleaseState.RELEASED
        ):
            raise WorkflowInputError("Active adoption of a released version required")
        if (
            framework is None
            or not is_framework_allowed(self.session, context.tenant_id, framework.slug)
            or not is_module_enabled(self.session, context.tenant_id, "frameworks")
            or not is_module_enabled(self.session, context.tenant_id, "evidence")
            or not is_module_enabled(self.session, context.tenant_id, "tasks")
        ):
            raise AuthorizationDeniedError("Framework workflow not entitled")
        return row

    def generate(
        self,
        principal: Principal,
        context: TenantContext,
        adoption_id: UUID,
        *,
        due_date: datetime,
        owner_user_id: UUID,
    ) -> list[FrameworkEvidenceRequest]:
        with self._process_lock:
            adoption = self._adoption(principal, context, adoption_id, Capability.FRAMEWORK_MANAGE)
            authorize(principal, context, Capability.TASK_MANAGE)
            specs = list(
                self.session.scalars(
                    select(EvidenceSpecification)
                    .where(
                        EvidenceSpecification.framework_version_id == adoption.framework_version_id,
                    )
                    .order_by(EvidenceSpecification.identifier)
                )
            )
            existing = {
                row.specification_id: row
                for row in self.session.scalars(
                    select(FrameworkEvidenceRequest).where(
                        FrameworkEvidenceRequest.tenant_id == context.tenant_id,
                        FrameworkEvidenceRequest.adoption_id == adoption_id,
                    )
                )
            }
            for spec in specs:
                if spec.id in existing:
                    continue
                task = self.compliance.create_task(
                    principal,
                    context,
                    title=spec.title,
                    description=spec.description,
                    due_date=due_date,
                    assignee_user_id=owner_user_id,
                )
                row = FrameworkEvidenceRequest(
                    tenant_id=context.tenant_id,
                    adoption_id=adoption_id,
                    specification_id=spec.id,
                    task_id=task.id,
                )
                self.session.add(row)
                self.session.flush()
                self._audit(principal, context, row, "framework.evidence_request.create")
                existing[spec.id] = row
            return [existing[spec.id] for spec in specs]

    def accept(
        self,
        principal: Principal,
        context: TenantContext,
        adoption_id: UUID,
        request_id: UUID,
        *,
        evidence_id: UUID,
        observation_start: datetime,
        observation_end: datetime,
    ) -> FrameworkEvidenceRequest:
        self._adoption(principal, context, adoption_id, Capability.EVIDENCE_MANAGE)
        row = self.session.scalar(
            select(FrameworkEvidenceRequest)
            .where(
                FrameworkEvidenceRequest.id == request_id,
                FrameworkEvidenceRequest.tenant_id == context.tenant_id,
                FrameworkEvidenceRequest.adoption_id == adoption_id,
            )
            .with_for_update()
        )
        if row is None:
            raise WorkflowInputError("Evidence request unavailable")
        evidence, _ = self.compliance.get_evidence(principal, context, evidence_id)
        spec = self.session.get(EvidenceSpecification, row.specification_id)
        if spec is None:
            raise WorkflowInputError("Evidence specification unavailable")
        # A savepoint ensures validation failure cannot leave a partly accepted binding.
        with self.session.begin_nested():
            row.evidence_id, row.evidence_version = evidence.id, evidence.version
            row.observation_start, row.observation_end = observation_start, observation_end
            row.accepted_by_user_id, row.accepted_at = principal.user_id, datetime.now(UTC)
            problem = request_evidence_problem(self.session, row, spec, now=row.accepted_at)
            if problem:
                raise WorkflowInputError(problem)
            self.session.flush()
            self._audit(principal, context, row, "framework.evidence_request.accept")
        return row

    def _audit(
        self,
        principal: Principal,
        context: TenantContext,
        row: FrameworkEvidenceRequest,
        action: str,
    ) -> None:
        record_audit_event(
            self.session,
            tenant_id=context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action=action,
            resource_type="framework_evidence_request",
            resource_id=str(row.id),
            request_id=f"workflow:{row.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={},
        )
