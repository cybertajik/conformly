import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import AuthorizationDeniedError, Principal, TenantContext, authorize
from conformly.authz.roles import Capability
from conformly.compliance.models import (
    ComplianceTask,
    ControlStatusRecord,
    EvidenceControlLink,
    EvidenceFileLink,
    EvidenceItem,
    Finding,
    Policy,
    PolicyControlLink,
    UserNotificationPreference,
)
from conformly.exports.models import (
    ExportJob,
    ExportManifest,
    ExportScope,
)
from conformly.exports.service import ExportService
from conformly.frameworks.models import (
    ControlMapping,
    CustomControl,
    TenantControlOverlay,
    TenantFrameworkAdoption,
)
from conformly.identity.models import Membership, MembershipInvitation, Tenant, TenantStatus
from conformly.notifications.models import NotificationOutbox
from conformly.preaudit.models import (
    PreAudit,
    PreAuditCertificate,
    PreAuditCheck,
    PreAuditFinding,
    PreAuditManifest,
    PreAuditReport,
    PreAuditScope,
)
from conformly.profiles.models import (
    PublicCredential,
    PublicProfile,
    PublicStatement,
)
from conformly.retention.models import (
    DeletionJob,
    DeletionJobState,
    DeletionProof,
    DeletionReason,
)
from conformly.storage.models import StoredFile
from conformly.storage.service import StorageService
from conformly.tenancy.rls import set_rls_context
from conformly.whistleblower.models import (
    WhistleblowerAttachment,
    WhistleblowerCase,
    WhistleblowerCaseAssignment,
    WhistleblowerMessage,
    WhistleblowerPortal,
)


class CancellationError(Exception):
    """Raised when tenant cancellation validation or execution fails."""


class LegalHoldActiveError(Exception):
    """Raised when an operation is blocked due to an active legal hold."""


class DeletionJobNotFoundError(Exception):
    """Raised when a deletion job cannot be found."""


def _exec_delete(session: Session, statement: Any) -> int:
    r = cast(CursorResult[Any], session.execute(statement))
    return int(r.rowcount or 0)


class RetentionService:
    """Manages tenant cancellation lifecycles, 30-day export windows,
    90-day deletion scheduling, and cryptographic proofs."""

    def __init__(
        self,
        session: Session,
        storage_service: StorageService,
        export_service: ExportService | None = None,
    ) -> None:
        self.session = session
        self.storage_service = storage_service
        self.export_service = export_service

    def request_cancellation(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        reason: str,
        confirm_slug: str,
        request_id: str,
        now: datetime | None = None,
    ) -> Tenant:
        current_time = now or datetime.now(UTC)

        try:
            authorize(principal, tenant_context, Capability.TENANT_CANCEL)
        except AuthorizationDeniedError:
            record_audit_event(
                self.session,
                tenant_id=tenant_context.tenant_id,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="tenant.cancellation_denied",
                resource_type="tenant",
                resource_id=str(tenant_context.tenant_id),
                request_id=request_id,
                outcome=AuditOutcome.DENIED,
                metadata={"reason": "capability_denied"},
                occurred_at=current_time,
            )
            raise

        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )

        tenant = self.session.get(Tenant, tenant_context.tenant_id)
        if tenant is None:
            raise CancellationError("Tenant not found")

        if tenant.status == TenantStatus.DELETED:
            raise CancellationError("Tenant is already deleted")

        # Safety confirmation: must match slug exactly
        if confirm_slug != tenant.slug:
            raise CancellationError(
                f"Confirmation slug mismatch: expected '{tenant.slug}', got '{confirm_slug}'"
            )

        if tenant.legal_hold:
            raise LegalHoldActiveError(
                "Cannot cancel tenant while an active legal hold is enforced"
            )

        export_until = current_time + timedelta(days=30)
        deletion_due_at = current_time + timedelta(days=90)

        tenant.status = TenantStatus.CANCELLING
        tenant.cancellation_requested_at = current_time
        tenant.export_until = export_until
        tenant.deletion_due_at = deletion_due_at

        # Schedule automated deletion job for day 90
        deletion_job = DeletionJob(
            id=uuid4(),
            tenant_id=tenant.id,
            reason=DeletionReason.CANCELLATION,
            state=DeletionJobState.SCHEDULED,
            scheduled_at=deletion_due_at,
        )
        self.session.add(deletion_job)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="tenant.cancellation_requested",
            resource_type="tenant",
            resource_id=str(tenant.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "cancellation_reason": reason[:200],
                "export_until": export_until.isoformat(),
                "deletion_due_at": deletion_due_at.isoformat(),
            },
            occurred_at=current_time,
        )

        # Trigger automatic initial cancellation export if export_service is available
        if self.export_service:
            try:
                self.export_service.create_export_job(
                    principal=principal,
                    tenant_context=tenant_context,
                    scope=ExportScope.FULL,
                    request_id=request_id,
                    now=current_time,
                )
            except Exception:
                # Do not block cancellation if automatic export generation fails
                pass

        return tenant

    def set_legal_hold(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        enabled: bool,
        reason: str,
        request_id: str,
        now: datetime | None = None,
    ) -> Tenant:
        current_time = now or datetime.now(UTC)

        try:
            authorize(principal, tenant_context, Capability.RETENTION_MANAGE)
        except AuthorizationDeniedError:
            record_audit_event(
                self.session,
                tenant_id=tenant_context.tenant_id,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="tenant.legal_hold_denied",
                resource_type="tenant",
                resource_id=str(tenant_context.tenant_id),
                request_id=request_id,
                outcome=AuditOutcome.DENIED,
                metadata={"reason": "capability_denied"},
                occurred_at=current_time,
            )
            raise

        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )

        tenant = self.session.get(Tenant, tenant_context.tenant_id)
        if tenant is None or tenant.status == TenantStatus.DELETED:
            raise CancellationError("Tenant not found or already deleted")

        tenant.legal_hold = enabled

        # Update any scheduled deletion jobs
        jobs = self.session.scalars(
            select(DeletionJob).where(
                DeletionJob.tenant_id == tenant.id,
                DeletionJob.state.in_([DeletionJobState.SCHEDULED, DeletionJobState.ON_HOLD]),
            )
        ).all()
        for j in jobs:
            j.state = DeletionJobState.ON_HOLD if enabled else DeletionJobState.SCHEDULED

        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="tenant.legal_hold_updated",
            resource_type="tenant",
            resource_id=str(tenant.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "legal_hold": enabled,
                "reason": reason[:200],
            },
            occurred_at=current_time,
        )

        return tenant

    def get_cancellation_status(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        authorize(principal, tenant_context, Capability.TENANT_READ)
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )
        tenant = self.session.get(Tenant, tenant_context.tenant_id)
        if tenant is None:
            raise CancellationError("Tenant not found")

        current_time = now or datetime.now(UTC)
        is_window_active = False
        days_remaining = None

        if tenant.status == TenantStatus.CANCELLING and tenant.export_until:
            exp_until = (
                tenant.export_until.replace(tzinfo=UTC)
                if tenant.export_until.tzinfo is None
                else tenant.export_until
            )
            is_window_active = current_time <= exp_until
            diff = (exp_until - current_time).total_seconds()
            days_remaining = max(0, int(diff // 86400))

        return {
            "status": str(tenant.status),
            "cancellation_requested_at": tenant.cancellation_requested_at.isoformat()
            if tenant.cancellation_requested_at
            else None,
            "export_until": tenant.export_until.isoformat() if tenant.export_until else None,
            "deletion_due_at": tenant.deletion_due_at.isoformat()
            if tenant.deletion_due_at
            else None,
            "days_remaining_in_export_window": days_remaining,
            "is_export_window_active": is_window_active,
            "legal_hold": tenant.legal_hold,
        }

    def execute_deletion_job(
        self,
        job_id: UUID,
        *,
        operator_principal: Principal | None = None,
        tenant_context: TenantContext | None = None,
        request_id: str = "scheduled-deletion",
        now: datetime | None = None,
    ) -> DeletionProof:
        """Purges customer records across all 8 modules and storage objects,
        generating an auditable proof receipt."""
        current_time = now or datetime.now(UTC)
        if operator_principal is not None:
            if tenant_context is None:
                raise AuthorizationDeniedError("Tenant context is required for manual deletion")
            authorize(operator_principal, tenant_context, Capability.RETENTION_MANAGE)
            set_rls_context(
                self.session,
                tenant_id=tenant_context.tenant_id,
                user_id=operator_principal.user_id,
                tenant_verified=True,
            )

        job_query = select(DeletionJob).where(DeletionJob.id == job_id)
        if tenant_context is not None:
            job_query = job_query.where(DeletionJob.tenant_id == tenant_context.tenant_id)
        job = self.session.scalar(job_query.with_for_update())
        if job is None:
            raise DeletionJobNotFoundError("Deletion job not found")

        if job.state != DeletionJobState.SCHEDULED:
            raise CancellationError("Deletion job is not scheduled")
        scheduled_at = (
            job.scheduled_at.replace(tzinfo=UTC)
            if job.scheduled_at.tzinfo is None
            else job.scheduled_at
        )
        if scheduled_at > current_time:
            raise CancellationError("Deletion job is not due yet")

        tenant = self.session.get(Tenant, job.tenant_id)
        if tenant is None:
            raise CancellationError("Tenant not found")

        if tenant.legal_hold:
            job.state = DeletionJobState.ON_HOLD
            self.session.flush()
            record_audit_event(
                self.session,
                tenant_id=tenant.id,
                actor_type=AuditActorType.SYSTEM,
                actor_id=operator_principal.user_id if operator_principal else None,
                action="tenant.deletion_blocked_by_hold",
                resource_type="deletion_job",
                resource_id=str(job.id),
                request_id=request_id,
                outcome=AuditOutcome.DENIED,
                metadata={"deletion_id": str(job.id), "legal_hold": True},
                occurred_at=current_time,
            )
            raise LegalHoldActiveError("Cannot execute deletion job while legal hold is active")

        # Keep every database-side purge in a savepoint. External object deletion
        # is idempotent, while a database failure must restore all metadata so a
        # later retry still has the complete deletion inventory.
        purge_savepoint = self.session.begin_nested()
        job.state = DeletionJobState.PROCESSING
        job.error_message = None
        self.session.flush()

        tables_purged: dict[str, int] = {}
        storage_objects_purged = 0

        try:
            tid = tenant.id

            # Delete external objects first while their retry metadata still exists.
            # Provider deletion is idempotent. Any failure leaves all database rows
            # intact so a scheduled retry can use the remaining object keys.
            stored_files = self.session.scalars(
                select(StoredFile).where(StoredFile.tenant_id == tid)
            ).all()
            for stored_file in stored_files:
                self.storage_service.storage_provider.delete_object(stored_file.object_key)
                storage_objects_purged += 1

            # 1. Public profiles
            tables_purged["public_statements"] = _exec_delete(
                self.session, delete(PublicStatement).where(PublicStatement.tenant_id == tid)
            )
            tables_purged["public_credentials"] = _exec_delete(
                self.session, delete(PublicCredential).where(PublicCredential.tenant_id == tid)
            )
            tables_purged["public_profiles"] = _exec_delete(
                self.session, delete(PublicProfile).where(PublicProfile.tenant_id == tid)
            )

            # 2. Whistleblower
            tables_purged["whistleblower_attachments"] = _exec_delete(
                self.session,
                delete(WhistleblowerAttachment).where(WhistleblowerAttachment.tenant_id == tid),
            )
            tables_purged["whistleblower_messages"] = _exec_delete(
                self.session,
                delete(WhistleblowerMessage).where(WhistleblowerMessage.tenant_id == tid),
            )
            tables_purged["whistleblower_case_assignments"] = _exec_delete(
                self.session,
                delete(WhistleblowerCaseAssignment).where(
                    WhistleblowerCaseAssignment.tenant_id == tid
                ),
            )
            tables_purged["whistleblower_cases"] = _exec_delete(
                self.session, delete(WhistleblowerCase).where(WhistleblowerCase.tenant_id == tid)
            )
            tables_purged["whistleblower_portals"] = _exec_delete(
                self.session,
                delete(WhistleblowerPortal).where(WhistleblowerPortal.tenant_id == tid),
            )

            # 3. Pre-audit
            tables_purged["pre_audit_certificates"] = _exec_delete(
                self.session,
                delete(PreAuditCertificate).where(PreAuditCertificate.tenant_id == tid),
            )
            tables_purged["pre_audit_manifests"] = _exec_delete(
                self.session, delete(PreAuditManifest).where(PreAuditManifest.tenant_id == tid)
            )
            tables_purged["pre_audit_reports"] = _exec_delete(
                self.session, delete(PreAuditReport).where(PreAuditReport.tenant_id == tid)
            )
            tables_purged["pre_audit_findings"] = _exec_delete(
                self.session, delete(PreAuditFinding).where(PreAuditFinding.tenant_id == tid)
            )
            tables_purged["pre_audit_checks"] = _exec_delete(
                self.session, delete(PreAuditCheck).where(PreAuditCheck.tenant_id == tid)
            )
            tables_purged["pre_audit_scopes"] = _exec_delete(
                self.session, delete(PreAuditScope).where(PreAuditScope.tenant_id == tid)
            )
            tables_purged["pre_audits"] = _exec_delete(
                self.session, delete(PreAudit).where(PreAudit.tenant_id == tid)
            )

            # 4. Compliance workspace
            tables_purged["compliance_tasks"] = _exec_delete(
                self.session, delete(ComplianceTask).where(ComplianceTask.tenant_id == tid)
            )
            tables_purged["findings"] = _exec_delete(
                self.session, delete(Finding).where(Finding.tenant_id == tid)
            )
            tables_purged["policy_control_links"] = _exec_delete(
                self.session, delete(PolicyControlLink).where(PolicyControlLink.tenant_id == tid)
            )
            tables_purged["policies"] = _exec_delete(
                self.session, delete(Policy).where(Policy.tenant_id == tid)
            )
            tables_purged["evidence_file_links"] = _exec_delete(
                self.session, delete(EvidenceFileLink).where(EvidenceFileLink.tenant_id == tid)
            )
            tables_purged["evidence_control_links"] = _exec_delete(
                self.session,
                delete(EvidenceControlLink).where(EvidenceControlLink.tenant_id == tid),
            )
            tables_purged["evidence_items"] = _exec_delete(
                self.session, delete(EvidenceItem).where(EvidenceItem.tenant_id == tid)
            )
            tables_purged["control_status_records"] = _exec_delete(
                self.session,
                delete(ControlStatusRecord).where(ControlStatusRecord.tenant_id == tid),
            )

            # 5. Frameworks
            tables_purged["control_mappings"] = _exec_delete(
                self.session, delete(ControlMapping).where(ControlMapping.tenant_id == tid)
            )
            tables_purged["custom_controls"] = _exec_delete(
                self.session, delete(CustomControl).where(CustomControl.tenant_id == tid)
            )
            tables_purged["tenant_control_overlays"] = _exec_delete(
                self.session,
                delete(TenantControlOverlay).where(TenantControlOverlay.tenant_id == tid),
            )
            tables_purged["tenant_framework_adoptions"] = _exec_delete(
                self.session,
                delete(TenantFrameworkAdoption).where(TenantFrameworkAdoption.tenant_id == tid),
            )

            # 6. Exports
            tables_purged["export_manifests"] = _exec_delete(
                self.session, delete(ExportManifest).where(ExportManifest.tenant_id == tid)
            )
            tables_purged["export_jobs"] = _exec_delete(
                self.session, delete(ExportJob).where(ExportJob.tenant_id == tid)
            )

            # 7. Stored-file metadata (objects were deleted above).
            tables_purged["stored_files"] = _exec_delete(
                self.session, delete(StoredFile).where(StoredFile.tenant_id == tid)
            )

            # 8. Invitations, preferences, and queued protected payloads
            tables_purged["notification_outbox"] = _exec_delete(
                self.session, delete(NotificationOutbox).where(NotificationOutbox.tenant_id == tid)
            )
            tables_purged["user_notification_preferences"] = _exec_delete(
                self.session,
                delete(UserNotificationPreference).where(
                    UserNotificationPreference.tenant_id == tid
                ),
            )
            tables_purged["membership_invitations"] = _exec_delete(
                self.session,
                delete(MembershipInvitation).where(MembershipInvitation.tenant_id == tid),
            )

            # 9. Memberships
            tables_purged["memberships"] = _exec_delete(
                self.session, delete(Membership).where(Membership.tenant_id == tid)
            )

            # 10. Tenant status -> DELETED
            tenant.status = TenantStatus.DELETED

            # 11. Generate cryptographic deletion proof receipt
            proof_data = {
                "tenant_id": str(tid),
                "deleted_at": current_time.isoformat(),
                "tables_purged": tables_purged,
                "storage_objects_purged": storage_objects_purged,
            }
            proof_bytes = json.dumps(proof_data, sort_keys=True).encode("utf-8")
            proof_hash = hashlib.sha256(proof_bytes).hexdigest()

            proof = DeletionProof(
                id=uuid4(),
                tenant_id=tid,
                deletion_job_id=job.id,
                deleted_at=current_time,
                tables_purged=tables_purged,
                storage_objects_purged=storage_objects_purged,
                proof_manifest_sha256=proof_hash,
            )
            self.session.add(proof)

            job.state = DeletionJobState.COMPLETED
            job.completed_at = current_time
            job.proof_id = proof.id
            self.session.flush()

            record_audit_event(
                self.session,
                tenant_id=tid,
                actor_type=AuditActorType.USER if operator_principal else AuditActorType.SYSTEM,
                actor_id=operator_principal.user_id if operator_principal else None,
                action="tenant.deleted",
                resource_type="tenant",
                resource_id=str(tid),
                request_id=request_id,
                outcome=AuditOutcome.SUCCESS,
                metadata={
                    "deletion_id": str(job.id),
                    "deletion_proof_hash": proof_hash,
                    "deleted_tables_count": len(tables_purged),
                    "storage_objects_purged": storage_objects_purged,
                },
                occurred_at=current_time,
            )
            purge_savepoint.commit()
            return proof

        except Exception as exc:
            purge_savepoint.rollback()
            job = self.session.get(DeletionJob, job_id)
            if job is None:
                raise CancellationError("Deletion job disappeared during rollback") from exc
            # Keep the job retryable. Object deletion is idempotent and metadata
            # remains available when provider deletion fails.
            job.state = DeletionJobState.SCHEDULED
            job.error_message = str(exc)
            self.session.flush()

            record_audit_event(
                self.session,
                tenant_id=tenant.id,
                actor_type=AuditActorType.USER if operator_principal else AuditActorType.SYSTEM,
                actor_id=operator_principal.user_id if operator_principal else None,
                action="tenant.deletion_failed",
                resource_type="deletion_job",
                resource_id=str(job.id),
                request_id=request_id,
                outcome=AuditOutcome.FAILURE,
                metadata={
                    "deletion_id": str(job.id),
                    "reason": "purge_failure",
                },
                occurred_at=current_time,
            )
            raise CancellationError(f"Failed to execute deletion: {exc}") from exc

    def list_deletion_proofs(
        self,
        principal: Principal,
        tenant_context: TenantContext,
    ) -> list[DeletionProof]:
        authorize(principal, tenant_context, Capability.TENANT_READ)
        return list(
            self.session.scalars(
                select(DeletionProof)
                .where(DeletionProof.tenant_id == tenant_context.tenant_id)
                .order_by(DeletionProof.deleted_at.desc())
            ).all()
        )
