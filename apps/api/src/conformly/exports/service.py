import hashlib
import io
import json
import re
import zipfile
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.assets.models import Asset
from conformly.audit.models import AuditActorType, AuditEvent, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import AuthorizationDeniedError, Principal, TenantContext, authorize
from conformly.authz.roles import Capability
from conformly.compliance.models import (
    ComplianceTask,
    ControlStatusRecord,
    EvidenceControlLink,
    EvidenceFileLink,
    EvidenceItem,
    EvidenceRevision,
    Finding,
    Policy,
    PolicyAcknowledgement,
    PolicyControlLink,
    PolicyRevision,
    PolicyTemplate,
    UserNotificationPreference,
)
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.types import EncryptionContext
from conformly.entitlements.models import TenantEntitlement
from conformly.exports.models import (
    ExportJob,
    ExportJobStatus,
    ExportManifest,
    ExportScope,
)
from conformly.frameworks.models import (
    ControlMapping,
    CustomControl,
    TenantApplicabilityProfile,
    TenantControlOverlay,
    TenantFrameworkAdoption,
)
from conformly.frameworks.workflow import FrameworkEvidenceRequest, serialize_request
from conformly.identity.models import Membership, MembershipInvitation, Tenant, TenantStatus, User
from conformly.organization.models import BusinessUnit, LegalEntity, Location
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
from conformly.risks.models import Risk, RiskTreatment
from conformly.storage.models import StoredFile, StoredFileStatus
from conformly.storage.service import StorageService
from conformly.tenancy.rls import set_rls_context
from conformly.vendors.models import Vendor
from conformly.whistleblower.models import WhistleblowerCase, WhistleblowerPortal


class ExportNotFoundError(Exception):
    """Raised when an export job cannot be found in the current tenant scope."""


class ExportExpiredError(Exception):
    """Raised when an export archive is expired and no longer downloadable."""


class ExportProcessingError(Exception):
    """Raised when data aggregation or export packaging fails."""


SAFE_FILE_NAME = re.compile(r"[^a-zA-Z0-9_.-]")


def _sanitize_filename(name: str) -> str:
    cleaned = SAFE_FILE_NAME.sub("_", name)
    return cleaned[:100] or "unnamed_file"


def _json_value(value: Any) -> Any:
    if isinstance(value, (UUID, datetime)):
        return value.isoformat() if isinstance(value, datetime) else str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def _row_data(row: Any, *, exclude: frozenset[str] = frozenset()) -> dict[str, Any]:
    return {
        column.name: _json_value(getattr(row, column.name))
        for column in row.__table__.columns
        if column.name not in exclude
    }


class ExportService:
    """Manages tenant-scoped cryptographic data export packaging, manifests, and downloads."""

    def __init__(
        self,
        session: Session,
        storage_service: StorageService,
        codec: EncryptedFieldCodec | None = None,
    ) -> None:
        self.session = session
        self.storage_service = storage_service
        self.codec = codec or EncryptedFieldCodec(storage_service.encryption)

    def _decrypt_field(
        self,
        tenant_id: UUID,
        resource_type: str,
        resource_id: UUID,
        field_name: str,
        payload: dict[str, object] | None,
    ) -> str | None:
        if payload is None:
            return None
        return self.codec.decrypt_text(
            payload,
            EncryptionContext(
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_id=str(resource_id),
                field_name=field_name,
            ),
        )

    def create_export_job(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        scope: ExportScope = ExportScope.FULL,
        request_id: str,
        now: datetime | None = None,
    ) -> ExportJob:
        current_time = now or datetime.now(UTC)

        try:
            authorize(principal, tenant_context, Capability.EXPORT_CREATE)
        except AuthorizationDeniedError:
            record_audit_event(
                self.session,
                tenant_id=tenant_context.tenant_id,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="export.create_denied",
                resource_type="export_job",
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
            raise ExportProcessingError("Tenant not found or deleted")

        idempotency_key = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
        existing_job = self.session.scalar(
            select(ExportJob).where(
                ExportJob.tenant_id == tenant_context.tenant_id,
                ExportJob.idempotency_key == idempotency_key,
            )
        )
        if existing_job is not None:
            if existing_job.scope != scope:
                raise ExportProcessingError(
                    "Idempotency key was already used for a different export scope"
                )
            if existing_job.status in {ExportJobStatus.PENDING, ExportJobStatus.FAILED}:
                existing_job.error_message = None
                return self._process_export_job(
                    job=existing_job,
                    principal=principal,
                    tenant_context=tenant_context,
                    tenant=tenant,
                    request_id=request_id,
                    now=current_time,
                )
            return existing_job

        # Expiry: default 7 days, capped at export_until if cancelling
        expires_at = current_time + timedelta(days=7)
        if tenant.status == TenantStatus.CANCELLING and tenant.export_until:
            exp_until = (
                tenant.export_until.replace(tzinfo=UTC)
                if tenant.export_until.tzinfo is None
                else tenant.export_until
            )
            if exp_until < expires_at:
                expires_at = exp_until

        job = ExportJob(
            id=uuid4(),
            tenant_id=tenant_context.tenant_id,
            requested_by_user_id=principal.user_id,
            idempotency_key=idempotency_key,
            scope=scope,
            status=ExportJobStatus.PENDING,
            expires_at=expires_at,
        )
        self.session.add(job)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="export.created",
            resource_type="export_job",
            resource_id=str(job.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "export_id": str(job.id),
                "export_scope": str(scope),
                "expires_at": expires_at.isoformat(),
            },
            occurred_at=current_time,
        )

        # Process export synchronously for deterministic completion
        return self._process_export_job(
            job=job,
            principal=principal,
            tenant_context=tenant_context,
            tenant=tenant,
            request_id=request_id,
            now=current_time,
        )

    def _process_export_job(
        self,
        *,
        job: ExportJob,
        principal: Principal,
        tenant_context: TenantContext,
        tenant: Tenant,
        request_id: str,
        now: datetime,
    ) -> ExportJob:
        job.status = ExportJobStatus.PROCESSING
        self.session.flush()

        try:
            zip_buffer = io.BytesIO()
            dataset_record_counts: dict[str, int] = {}
            file_hashes: dict[str, str] = {}
            total_records = 0

            with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                # ── 1. Structured JSON Datasets ───────────────────────────────
                # Tenant profile
                tenant_data = {
                    "id": str(tenant.id),
                    "name": tenant.name,
                    "slug": tenant.slug,
                    "status": str(tenant.status),
                    "cancellation_requested_at": tenant.cancellation_requested_at.isoformat()
                    if tenant.cancellation_requested_at
                    else None,
                    "export_until": tenant.export_until.isoformat()
                    if tenant.export_until
                    else None,
                    "deletion_due_at": tenant.deletion_due_at.isoformat()
                    if tenant.deletion_due_at
                    else None,
                    "legal_hold": tenant.legal_hold,
                    "created_at": tenant.created_at.isoformat(),
                }
                zf.writestr("data/tenant.json", json.dumps(tenant_data, indent=2))
                dataset_record_counts["tenant"] = 1
                total_records += 1

                # Memberships
                memberships = self.session.scalars(
                    select(Membership).where(Membership.tenant_id == tenant.id)
                ).all()
                memberships_data = [
                    {
                        "id": str(m.id),
                        "user_id": str(m.user_id),
                        "role": str(m.role),
                        "status": str(m.status),
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in memberships
                ]
                zf.writestr("data/memberships.json", json.dumps(memberships_data, indent=2))
                dataset_record_counts["memberships"] = len(memberships_data)
                total_records += len(memberships_data)

                member_ids = [membership.user_id for membership in memberships]
                member_users = (
                    self.session.scalars(select(User).where(User.id.in_(member_ids))).all()
                    if member_ids
                    else []
                )
                users_data = [
                    {
                        "id": str(user.id),
                        "email": user.email,
                        "display_name": user.display_name,
                        "status": str(user.status),
                    }
                    for user in member_users
                ]
                zf.writestr("data/member_users.json", json.dumps(users_data, indent=2))
                dataset_record_counts["member_users"] = len(users_data)
                total_records += len(users_data)

                invitations = self.session.scalars(
                    select(MembershipInvitation).where(MembershipInvitation.tenant_id == tenant.id)
                ).all()
                invitation_data = [
                    _row_data(invitation, exclude=frozenset({"token_digest"}))
                    for invitation in invitations
                ]
                zf.writestr(
                    "data/membership_invitations.json", json.dumps(invitation_data, indent=2)
                )
                dataset_record_counts["membership_invitations"] = len(invitation_data)
                total_records += len(invitation_data)

                preferences = self.session.scalars(
                    select(UserNotificationPreference).where(
                        UserNotificationPreference.tenant_id == tenant.id
                    )
                ).all()
                preference_data = [_row_data(preference) for preference in preferences]
                zf.writestr(
                    "data/notification_preferences.json", json.dumps(preference_data, indent=2)
                )
                dataset_record_counts["notification_preferences"] = len(preference_data)
                total_records += len(preference_data)

                requests = list(
                    self.session.scalars(
                        select(FrameworkEvidenceRequest).where(
                            FrameworkEvidenceRequest.tenant_id == tenant.id,
                        )
                    )
                )
                zf.writestr(
                    "data/framework_evidence_requests.json",
                    json.dumps(
                        [serialize_request(row) for row in requests],
                        indent=2,
                    ),
                )
                dataset_record_counts["framework_evidence_requests"] = len(requests)
                total_records += len(requests)

                # Framework adoptions, overlays, custom controls, mappings
                adoptions = self.session.scalars(
                    select(TenantFrameworkAdoption).where(
                        TenantFrameworkAdoption.tenant_id == tenant.id
                    )
                ).all()
                adoptions_data = [
                    {
                        "id": str(a.id),
                        "framework_id": str(a.framework_id),
                        "framework_version_id": str(a.framework_version_id),
                        "status": str(a.status),
                        "created_at": a.created_at.isoformat(),
                    }
                    for a in adoptions
                ]
                zf.writestr("data/framework_adoptions.json", json.dumps(adoptions_data, indent=2))
                dataset_record_counts["framework_adoptions"] = len(adoptions_data)
                total_records += len(adoptions_data)

                profiles = list(
                    self.session.scalars(
                        select(TenantApplicabilityProfile).where(
                            TenantApplicabilityProfile.tenant_id == tenant.id
                        )
                    )
                )
                profiles_data = [
                    {
                        "id": str(p.id),
                        "adoption_id": str(p.adoption_id),
                        "evaluator_version": p.evaluator_version,
                        "profile_answers": p.profile_answers_json,
                        "sources": p.sources_json,
                        "contradictions": p.contradictions_json,
                        "evaluation_summary": p.evaluation_summary_json,
                        "evaluated_by_user_id": str(p.evaluated_by_user_id),
                        "reviewed_by_user_id": str(p.reviewed_by_user_id)
                        if p.reviewed_by_user_id
                        else None,
                        "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
                        "review_status": p.review_status,
                        "created_at": p.created_at.isoformat(),
                    }
                    for p in profiles
                ]
                zf.writestr(
                    "data/applicability_profiles.json",
                    json.dumps(profiles_data, indent=2),
                )
                dataset_record_counts["applicability_profiles"] = len(profiles_data)
                total_records += len(profiles_data)

                overlays = self.session.scalars(
                    select(TenantControlOverlay).where(TenantControlOverlay.tenant_id == tenant.id)
                ).all()
                overlays_data = [
                    {
                        "id": str(o.id),
                        "adoption_id": str(o.adoption_id),
                        "canonical_control_id": str(o.canonical_control_id),
                        "applicability": str(o.applicability),
                        "justification": o.justification,
                        "internal_notes": o.internal_notes,
                        "custom_guidance": o.custom_guidance,
                        "created_at": o.created_at.isoformat(),
                    }
                    for o in overlays
                ]
                zf.writestr("data/control_overlays.json", json.dumps(overlays_data, indent=2))
                dataset_record_counts["control_overlays"] = len(overlays_data)
                total_records += len(overlays_data)

                custom_controls = self.session.scalars(
                    select(CustomControl).where(CustomControl.tenant_id == tenant.id)
                ).all()
                custom_controls_data = [
                    {
                        "id": str(c.id),
                        "identifier": c.identifier,
                        "title": c.title,
                        "description": c.description,
                        "status": str(c.status),
                        "created_at": c.created_at.isoformat(),
                    }
                    for c in custom_controls
                ]
                zf.writestr("data/custom_controls.json", json.dumps(custom_controls_data, indent=2))
                dataset_record_counts["custom_controls"] = len(custom_controls_data)
                total_records += len(custom_controls_data)

                mappings = self.session.scalars(
                    select(ControlMapping).where(ControlMapping.tenant_id == tenant.id)
                ).all()
                mappings_data = [
                    {
                        "id": str(m.id),
                        "source_type": str(m.source_type),
                        "source_control_id": str(m.source_control_id),
                        "target_type": str(m.target_type),
                        "target_control_id": str(m.target_control_id),
                        "mapping_type": str(m.mapping_type),
                        "rationale": m.rationale,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in mappings
                ]
                zf.writestr("data/control_mappings.json", json.dumps(mappings_data, indent=2))
                dataset_record_counts["control_mappings"] = len(mappings_data)
                total_records += len(mappings_data)

                evidence_control_links = self.session.scalars(
                    select(EvidenceControlLink).where(EvidenceControlLink.tenant_id == tenant.id)
                ).all()
                evidence_control_link_data = [_row_data(link) for link in evidence_control_links]
                zf.writestr(
                    "data/evidence_control_links.json",
                    json.dumps(evidence_control_link_data, indent=2),
                )
                dataset_record_counts["evidence_control_links"] = len(evidence_control_link_data)
                total_records += len(evidence_control_link_data)

                evidence_file_links = self.session.scalars(
                    select(EvidenceFileLink).where(EvidenceFileLink.tenant_id == tenant.id)
                ).all()
                evidence_file_link_data = [_row_data(link) for link in evidence_file_links]
                zf.writestr(
                    "data/evidence_file_links.json", json.dumps(evidence_file_link_data, indent=2)
                )
                dataset_record_counts["evidence_file_links"] = len(evidence_file_link_data)
                total_records += len(evidence_file_link_data)

                policy_control_links = self.session.scalars(
                    select(PolicyControlLink).where(PolicyControlLink.tenant_id == tenant.id)
                ).all()
                policy_control_link_data = [_row_data(link) for link in policy_control_links]
                zf.writestr(
                    "data/policy_control_links.json", json.dumps(policy_control_link_data, indent=2)
                )
                dataset_record_counts["policy_control_links"] = len(policy_control_link_data)
                total_records += len(policy_control_link_data)

                # Compliance policies
                policies = self.session.scalars(
                    select(Policy).where(Policy.tenant_id == tenant.id)
                ).all()
                policies_data = [
                    {
                        "id": str(p.id),
                        "title": p.title,
                        "description": p.description,
                        "version_string": p.version_string,
                        "status": str(p.status),
                        "content": p.content,
                        "restricted_content": self._decrypt_field(
                            tenant.id,
                            "policy",
                            p.id,
                            "restricted_content",
                            p.restricted_content_encrypted,
                        ),
                        "classification": str(p.classification),
                        "review_cycle_days": p.review_cycle_days,
                        "approved_at": p.approved_at.isoformat() if p.approved_at else None,
                        "created_at": p.created_at.isoformat(),
                    }
                    for p in policies
                ]
                zf.writestr("data/policies.json", json.dumps(policies_data, indent=2))
                dataset_record_counts["policies"] = len(policies_data)
                total_records += len(policies_data)

                # Policy revisions, templates, and workforce acknowledgements
                policy_revisions = self.session.scalars(
                    select(PolicyRevision).where(PolicyRevision.tenant_id == tenant.id)
                ).all()
                policy_revisions_data = [
                    {
                        "id": str(pr.id),
                        "policy_id": str(pr.policy_id),
                        "revision_number": pr.revision_number,
                        "version_string": pr.version_string,
                        "title": pr.title,
                        "description": pr.description,
                        "content": pr.content,
                        "classification": str(pr.classification),
                        "status": str(pr.status),
                        "restricted_content": self._decrypt_field(
                            tenant.id,
                            "policy",
                            pr.policy_id,
                            "restricted_content",
                            pr.restricted_content_encrypted,
                        ),
                        "created_by_user_id": str(pr.created_by_user_id),
                        "approved_by_user_id": str(pr.approved_by_user_id)
                        if pr.approved_by_user_id
                        else None,
                        "approved_at": pr.approved_at.isoformat() if pr.approved_at else None,
                        "change_summary": pr.change_summary,
                        "created_at": pr.created_at.isoformat(),
                    }
                    for pr in policy_revisions
                ]
                zf.writestr(
                    "data/policy_revisions.json", json.dumps(policy_revisions_data, indent=2)
                )
                dataset_record_counts["policy_revisions"] = len(policy_revisions_data)
                total_records += len(policy_revisions_data)

                policy_templates = self.session.scalars(
                    select(PolicyTemplate).where(PolicyTemplate.tenant_id == tenant.id)
                ).all()
                policy_templates_data = [
                    {
                        "id": str(pt.id),
                        "slug": pt.slug,
                        "title": pt.title,
                        "category": pt.category,
                        "description": pt.description,
                        "content_template": pt.content_template,
                        "suggested_classification": str(pt.suggested_classification),
                        "created_at": pt.created_at.isoformat(),
                    }
                    for pt in policy_templates
                ]
                zf.writestr(
                    "data/policy_templates.json", json.dumps(policy_templates_data, indent=2)
                )
                dataset_record_counts["policy_templates"] = len(policy_templates_data)
                total_records += len(policy_templates_data)

                policy_acknowledgements = self.session.scalars(
                    select(PolicyAcknowledgement).where(
                        PolicyAcknowledgement.tenant_id == tenant.id
                    )
                ).all()
                policy_acknowledgements_data = [
                    {
                        "id": str(pa.id),
                        "policy_id": str(pa.policy_id),
                        "policy_revision_id": str(pa.policy_revision_id)
                        if pa.policy_revision_id
                        else None,
                        "user_id": str(pa.user_id),
                        "acknowledged_at": pa.acknowledged_at.isoformat(),
                        "ip_address": pa.ip_address,
                        "user_agent": pa.user_agent,
                    }
                    for pa in policy_acknowledgements
                ]
                zf.writestr(
                    "data/policy_acknowledgements.json",
                    json.dumps(policy_acknowledgements_data, indent=2),
                )
                dataset_record_counts["policy_acknowledgements"] = len(policy_acknowledgements_data)
                total_records += len(policy_acknowledgements_data)

                control_statuses = self.session.scalars(
                    select(ControlStatusRecord).where(ControlStatusRecord.tenant_id == tenant.id)
                ).all()
                control_statuses_data = [
                    {
                        "id": str(cs.id),
                        "control_type": str(cs.control_type),
                        "control_id": str(cs.control_id),
                        "status": str(cs.status),
                        "created_at": cs.created_at.isoformat(),
                    }
                    for cs in control_statuses
                ]
                zf.writestr(
                    "data/control_statuses.json", json.dumps(control_statuses_data, indent=2)
                )
                dataset_record_counts["control_statuses"] = len(control_statuses_data)
                total_records += len(control_statuses_data)

                # Evidence items
                evidence_items = self.session.scalars(
                    select(EvidenceItem).where(EvidenceItem.tenant_id == tenant.id)
                ).all()
                evidence_data = [
                    {
                        "id": str(e.id),
                        "title": e.title,
                        "description": e.description,
                        "classification": str(e.classification),
                        "status": str(e.status),
                        "restricted_notes": self._decrypt_field(
                            tenant.id,
                            "evidence_item",
                            e.id,
                            "restricted_notes",
                            e.restricted_notes_encrypted,
                        ),
                        "file_ids": [str(fl.file_id) for fl in e.file_links],
                        "legal_hold": e.legal_hold,
                        "retention_until": e.retention_until.isoformat()
                        if e.retention_until
                        else None,
                        "created_at": e.created_at.isoformat(),
                    }
                    for e in evidence_items
                ]
                zf.writestr("data/evidence_items.json", json.dumps(evidence_data, indent=2))
                dataset_record_counts["evidence_items"] = len(evidence_data)
                total_records += len(evidence_data)

                # Evidence revisions
                evidence_revisions = self.session.scalars(
                    select(EvidenceRevision).where(EvidenceRevision.tenant_id == tenant.id)
                ).all()
                evidence_revisions_data = [
                    {
                        "id": str(er.id),
                        "evidence_id": str(er.evidence_id),
                        "revision_number": er.revision_number,
                        "title": er.title,
                        "description": er.description,
                        "classification": str(er.classification),
                        "status": str(er.status),
                        "valid_from": er.valid_from.isoformat() if er.valid_from else None,
                        "valid_until": er.valid_until.isoformat() if er.valid_until else None,
                        "file_ids": er.file_ids,
                        "control_ids": er.control_ids,
                        "created_by_user_id": str(er.created_by_user_id),
                        "change_summary": er.change_summary,
                        "created_at": er.created_at.isoformat(),
                    }
                    for er in evidence_revisions
                ]
                zf.writestr(
                    "data/evidence_revisions.json", json.dumps(evidence_revisions_data, indent=2)
                )
                dataset_record_counts["evidence_revisions"] = len(evidence_revisions_data)
                total_records += len(evidence_revisions_data)

                # Compliance tasks & findings
                tasks = self.session.scalars(
                    select(ComplianceTask).where(ComplianceTask.tenant_id == tenant.id)
                ).all()
                tasks_data = [
                    {
                        "id": str(t.id),
                        "title": t.title,
                        "description": t.description,
                        "status": str(t.status),
                        "priority": str(t.priority),
                        "due_date": t.due_date.isoformat() if t.due_date else None,
                        "created_at": t.created_at.isoformat(),
                    }
                    for t in tasks
                ]
                zf.writestr("data/compliance_tasks.json", json.dumps(tasks_data, indent=2))
                dataset_record_counts["compliance_tasks"] = len(tasks_data)
                total_records += len(tasks_data)

                findings = self.session.scalars(
                    select(Finding).where(Finding.tenant_id == tenant.id)
                ).all()
                findings_data = [
                    {
                        "id": str(f.id),
                        "title": f.title,
                        "description": f.description,
                        "severity": str(f.severity),
                        "remediation_status": str(f.remediation_status),
                        "created_at": f.created_at.isoformat(),
                    }
                    for f in findings
                ]
                zf.writestr("data/findings.json", json.dumps(findings_data, indent=2))
                dataset_record_counts["findings"] = len(findings_data)
                total_records += len(findings_data)

                # Pre-audits, evaluations, certificates
                pre_audits = self.session.scalars(
                    select(PreAudit).where(PreAudit.tenant_id == tenant.id)
                ).all()
                pre_audits_data = [
                    {
                        "id": str(pa.id),
                        "title": pa.title,
                        "description": pa.description,
                        "status": str(pa.status),
                        "overall_score": pa.overall_score,
                        "rule_version": pa.rule_version,
                        "created_at": pa.created_at.isoformat(),
                    }
                    for pa in pre_audits
                ]
                zf.writestr("data/pre_audits.json", json.dumps(pre_audits_data, indent=2))
                dataset_record_counts["pre_audits"] = len(pre_audits_data)
                total_records += len(pre_audits_data)

                check_evals = self.session.scalars(
                    select(PreAuditCheck).where(PreAuditCheck.tenant_id == tenant.id)
                ).all()
                evals_data = [
                    {
                        "id": str(ce.id),
                        "scope_id": str(ce.scope_id),
                        "snapshot_json": ce.snapshot_json,
                        "control_type": str(ce.control_type),
                        "control_id": str(ce.control_id),
                        "result": str(ce.result),
                        "score": ce.score,
                        "rule_version": ce.rule_version,
                        "created_at": ce.created_at.isoformat(),
                    }
                    for ce in check_evals
                ]
                zf.writestr("data/pre_audit_evaluations.json", json.dumps(evals_data, indent=2))
                dataset_record_counts["pre_audit_evaluations"] = len(evals_data)
                total_records += len(evals_data)

                preaudit_datasets: tuple[tuple[str, Any], ...] = (
                    ("pre_audit_scopes", PreAuditScope),
                    ("pre_audit_findings", PreAuditFinding),
                    ("pre_audit_reports", PreAuditReport),
                    ("pre_audit_manifests", PreAuditManifest),
                )
                for dataset_name, model_type in preaudit_datasets:
                    rows = self.session.scalars(
                        select(model_type).where(model_type.tenant_id == tenant.id)
                    ).all()
                    row_data = [_row_data(row) for row in rows]
                    zf.writestr(f"data/{dataset_name}.json", json.dumps(row_data, indent=2))
                    dataset_record_counts[dataset_name] = len(row_data)
                    total_records += len(row_data)

                certificates = self.session.scalars(
                    select(PreAuditCertificate).where(PreAuditCertificate.tenant_id == tenant.id)
                ).all()
                certs_data = [
                    {
                        "id": str(c.id),
                        "certificate_number": c.certificate_number,
                        "pre_audit_id": str(c.pre_audit_id),
                        "status": str(c.status),
                        "issued_at": c.issued_at.isoformat(),
                        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                        "created_at": c.created_at.isoformat(),
                    }
                    for c in certificates
                ]
                zf.writestr("data/certificates.json", json.dumps(certs_data, indent=2))
                dataset_record_counts["certificates"] = len(certs_data)
                total_records += len(certs_data)

                # Public profile, credentials, statements
                pub_profile = self.session.scalar(
                    select(PublicProfile).where(PublicProfile.tenant_id == tenant.id)
                )
                pub_profile_data = (
                    {
                        "id": str(pub_profile.id),
                        "slug": pub_profile.slug,
                        "display_name": pub_profile.display_name,
                        "description": pub_profile.description,
                        "is_published": pub_profile.is_published,
                        "published_at": pub_profile.published_at.isoformat()
                        if pub_profile.published_at
                        else None,
                    }
                    if pub_profile
                    else None
                )
                zf.writestr("data/public_profile.json", json.dumps(pub_profile_data, indent=2))
                dataset_record_counts["public_profile"] = 1 if pub_profile else 0
                if pub_profile:
                    total_records += 1

                pub_creds = self.session.scalars(
                    select(PublicCredential).where(PublicCredential.tenant_id == tenant.id)
                ).all()
                pub_creds_data = [
                    {
                        "id": str(cr.id),
                        "credential_type": str(cr.credential_type),
                        "title": cr.title,
                        "issuer_name": cr.issuer_name,
                        "status": str(cr.status),
                        "issued_at": cr.issued_at.isoformat(),
                        "valid_until": cr.valid_until.isoformat() if cr.valid_until else None,
                    }
                    for cr in pub_creds
                ]
                zf.writestr("data/public_credentials.json", json.dumps(pub_creds_data, indent=2))
                dataset_record_counts["public_credentials"] = len(pub_creds_data)
                total_records += len(pub_creds_data)

                pub_stmts = self.session.scalars(
                    select(PublicStatement).where(PublicStatement.tenant_id == tenant.id)
                ).all()
                pub_stmts_data = [
                    {
                        "id": str(st.id),
                        "title": st.title,
                        "statement_content": st.statement_content,
                    }
                    for st in pub_stmts
                ]
                zf.writestr("data/public_statements.json", json.dumps(pub_stmts_data, indent=2))
                dataset_record_counts["public_statements"] = len(pub_stmts_data)
                total_records += len(pub_stmts_data)

                # Whistleblower portal & anonymous cases metadata (no plaintext identity)
                wb_portal = self.session.scalar(
                    select(WhistleblowerPortal).where(WhistleblowerPortal.tenant_id == tenant.id)
                )
                wb_portal_data = (
                    {
                        "id": str(wb_portal.id),
                        "portal_slug": wb_portal.slug,
                        "title": wb_portal.title,
                        "is_active": wb_portal.is_active,
                    }
                    if wb_portal
                    else None
                )
                zf.writestr("data/whistleblower_portal.json", json.dumps(wb_portal_data, indent=2))
                dataset_record_counts["whistleblower_portal"] = 1 if wb_portal else 0
                if wb_portal:
                    total_records += 1

                wb_cases = self.session.scalars(
                    select(WhistleblowerCase).where(WhistleblowerCase.tenant_id == tenant.id)
                ).all()
                wb_status_counts: dict[str, int] = {}
                for wb_case in wb_cases:
                    status_key = str(wb_case.status)
                    wb_status_counts[status_key] = wb_status_counts.get(status_key, 0) + 1
                wb_cases_data = {"total": len(wb_cases), "by_status": wb_status_counts}
                zf.writestr("data/whistleblower_cases.json", json.dumps(wb_cases_data, indent=2))
                dataset_record_counts["whistleblower_cases"] = len(wb_cases)
                total_records += len(wb_cases)

                # Tenant entitlements
                entitlements = self.session.scalars(
                    select(TenantEntitlement).where(TenantEntitlement.tenant_id == tenant.id)
                ).all()
                entitlements_data = [_row_data(e) for e in entitlements]
                zf.writestr(
                    "data/tenant_entitlements.json", json.dumps(entitlements_data, indent=2)
                )
                dataset_record_counts["tenant_entitlements"] = len(entitlements_data)
                total_records += len(entitlements_data)

                # Organization structure (legal entities, business units, locations)
                legal_entities = self.session.scalars(
                    select(LegalEntity).where(LegalEntity.tenant_id == tenant.id)
                ).all()
                legal_entities_data = [_row_data(le) for le in legal_entities]
                zf.writestr("data/legal_entities.json", json.dumps(legal_entities_data, indent=2))
                dataset_record_counts["legal_entities"] = len(legal_entities_data)
                total_records += len(legal_entities_data)

                business_units = self.session.scalars(
                    select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id)
                ).all()
                business_units_data = [_row_data(bu) for bu in business_units]
                zf.writestr("data/business_units.json", json.dumps(business_units_data, indent=2))
                dataset_record_counts["business_units"] = len(business_units_data)
                total_records += len(business_units_data)

                locations = self.session.scalars(
                    select(Location).where(Location.tenant_id == tenant.id)
                ).all()
                locations_data = [_row_data(loc) for loc in locations]
                zf.writestr("data/locations.json", json.dumps(locations_data, indent=2))
                dataset_record_counts["locations"] = len(locations_data)
                total_records += len(locations_data)

                # Risks & treatments
                risks = self.session.scalars(select(Risk).where(Risk.tenant_id == tenant.id)).all()
                risks_data = [_row_data(r) for r in risks]
                zf.writestr("data/risks.json", json.dumps(risks_data, indent=2))
                dataset_record_counts["risks"] = len(risks_data)
                total_records += len(risks_data)

                risk_treatments = self.session.scalars(
                    select(RiskTreatment).where(RiskTreatment.tenant_id == tenant.id)
                ).all()
                risk_treatments_data = [_row_data(rt) for rt in risk_treatments]
                zf.writestr("data/risk_treatments.json", json.dumps(risk_treatments_data, indent=2))
                dataset_record_counts["risk_treatments"] = len(risk_treatments_data)
                total_records += len(risk_treatments_data)

                # Assets (with decrypted descriptions)
                assets = self.session.scalars(
                    select(Asset).where(Asset.tenant_id == tenant.id)
                ).all()
                assets_data: list[dict[str, Any]] = []
                for a in assets:
                    row = _row_data(a, exclude=frozenset({"encrypted_description"}))
                    if a.encrypted_description is not None:
                        row["description"] = self._decrypt_field(
                            tenant.id, "asset", a.id, "description", a.encrypted_description
                        )
                    else:
                        row["description"] = a.description
                    assets_data.append(row)
                zf.writestr("data/assets.json", json.dumps(assets_data, indent=2))
                dataset_record_counts["assets"] = len(assets_data)
                total_records += len(assets_data)

                # Vendors
                vendors = self.session.scalars(
                    select(Vendor).where(Vendor.tenant_id == tenant.id)
                ).all()
                vendors_data = [_row_data(v) for v in vendors]
                zf.writestr("data/vendors.json", json.dumps(vendors_data, indent=2))
                dataset_record_counts["vendors"] = len(vendors_data)
                total_records += len(vendors_data)

                audit_events = self.session.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.tenant_id == tenant.id)
                    .order_by(AuditEvent.occurred_at, AuditEvent.id)
                ).all()
                audit_data = [
                    {
                        "id": str(event.id),
                        "actor_type": str(event.actor_type),
                        "actor_id": str(event.actor_id) if event.actor_id else None,
                        "action": event.action,
                        "resource_type": event.resource_type,
                        "resource_id": event.resource_id,
                        "occurred_at": event.occurred_at.isoformat(),
                        "request_id": event.request_id,
                        "outcome": str(event.outcome),
                        "metadata": event.safe_metadata,
                    }
                    for event in audit_events
                ]
                zf.writestr("data/audit_events.json", json.dumps(audit_data, indent=2))
                dataset_record_counts["audit_events"] = len(audit_data)
                total_records += len(audit_data)
                audit_event_ids = [str(event.id) for event in audit_events]

                # ── 2. Decrypted Original Files ───────────────────────────────
                stored_files = self.session.scalars(
                    select(StoredFile).where(
                        StoredFile.tenant_id == tenant.id,
                        StoredFile.status == StoredFileStatus.ACTIVE,
                    )
                ).all()

                files_exported = 0
                for sf in stored_files:
                    # Skip previous export ZIP archives to avoid recursive bundling
                    if (
                        sf.content_type == "application/zip"
                        and "conformly-export-" in sf.original_filename
                    ):
                        continue
                    try:
                        _, plaintext = self.storage_service.download_file(
                            principal=principal,
                            tenant_context=tenant_context,
                            file_id=sf.id,
                            request_id=request_id,
                            now=now,
                        )
                    except Exception as exc:
                        raise ExportProcessingError(
                            f"Required original file {sf.id} could not be exported"
                        ) from exc
                    # Re-verify integrity
                    file_sha256 = hashlib.sha256(plaintext).hexdigest()
                    rel_path = f"files/{sf.id}_{_sanitize_filename(sf.original_filename)}"
                    zf.writestr(rel_path, plaintext)
                    file_hashes[rel_path] = file_sha256
                    files_exported += 1

                # ── 3. Human-Readable Compliance Reports ──────────────────────
                posture_report = (
                    f"# Compliance Posture Summary — {tenant.name}\n\n"
                    f"- **Export Date:** {now.isoformat()}\n"
                    f"- **Tenant Slug:** {tenant.slug}\n"
                    f"- **Tenant Status:** {tenant.status}\n"
                    f"- **Legal Entities:** {len(legal_entities_data)}\n"
                    f"- **Business Units:** {len(business_units_data)}\n"
                    f"- **Locations:** {len(locations_data)}\n"
                    f"- **Identified Risks:** {len(risks_data)}\n"
                    f"- **Risk Treatments:** {len(risk_treatments_data)}\n"
                    f"- **Tracked Assets:** {len(assets_data)}\n"
                    f"- **Third-Party Vendors:** {len(vendors_data)}\n"
                    f"- **Adopted Frameworks:** {len(adoptions_data)}\n"
                    f"- **Active Policies:** {len(policies_data)}\n"
                    f"- **Compliance Tasks:** {len(tasks_data)}\n"
                    f"- **Open Findings:** {len(findings_data)}\n"
                    f"- **Evidence Items:** {len(evidence_data)}\n"
                )
                zf.writestr("reports/compliance_posture_report.md", posture_report)

                preaudit_report = (
                    f"# Pre-Audit Readiness Summary — {tenant.name}\n\n"
                    f"- **Pre-Audits Conducted:** {len(pre_audits_data)}\n"
                    f"- **Evaluated Checkpoints:** {len(evals_data)}\n"
                    f"- **Issued Certificates:** {len(certs_data)}\n\n"
                    "Disclaimer: Conformly is an audit-readiness and compliance operations "
                    "platform, not an accredited certification body.\n"
                )
                zf.writestr("reports/pre_audit_readiness_report.md", preaudit_report)

                inventory_manifest_md = (
                    f"# Data Inventory Manifest — {tenant.name}\n\n"
                    f"- **Total Records Exported:** {total_records}\n"
                    f"- **Total Files Exported:** {files_exported}\n"
                    f"- **Export Scope:** {job.scope}\n"
                    f"- **Timestamp:** {now.isoformat()}\n\n"
                    "## Datasets\n"
                    + "\n".join(f"- **{k}**: {v} records" for k, v in dataset_record_counts.items())
                    + "\n\n## File Hashes (SHA-256)\n"
                    + "\n".join(f"- `{k}`: `{v}`" for k, v in file_hashes.items())
                    + "\n"
                )
                zf.writestr("reports/data_inventory_manifest.md", inventory_manifest_md)

                # ── 4. Audit Manifest ─────────────────────────────────────────
                manifest_dict = {
                    "schema_version": "1.0.0",
                    "export_id": str(job.id),
                    "tenant_id": str(tenant.id),
                    "tenant_slug": tenant.slug,
                    "exported_at": now.isoformat(),
                    "scope": str(job.scope),
                    "dataset_record_counts": dataset_record_counts,
                    "file_hashes": file_hashes,
                    "total_records": total_records,
                    "total_files": files_exported,
                    "audit_event_ids": audit_event_ids,
                }
                manifest_bytes = json.dumps(manifest_dict, sort_keys=True, indent=2).encode("utf-8")
                manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
                manifest_dict["manifest_sha256"] = manifest_sha256

                zf.writestr("manifest.json", json.dumps(manifest_dict, indent=2))

            zip_bytes = zip_buffer.getvalue()
            zip_sha256 = hashlib.sha256(zip_bytes).hexdigest()

            # Store the resulting ZIP archive in StorageService with Restricted classification
            stored_export = self.storage_service.upload_file(
                principal=principal,
                tenant_context=tenant_context,
                filename=f"conformly-export-{tenant.slug}-{job.id.hex[:8]}.zip",
                content=zip_bytes,
                classification="Restricted",
                content_type="application/zip",
                request_id=request_id,
                now=now,
            )

            # Persist ExportManifest
            manifest_entity = ExportManifest(
                id=uuid4(),
                tenant_id=tenant.id,
                export_job_id=job.id,
                dataset_versions={"all": "1.0.0"},
                file_hashes=file_hashes,
                record_counts=dataset_record_counts,
                audit_references={
                    "exported_at": now.isoformat(),
                    "event_ids": audit_event_ids,
                },
                manifest_sha256=manifest_sha256,
            )
            self.session.add(manifest_entity)

            # Update job
            job.status = ExportJobStatus.COMPLETED
            job.stored_file_id = stored_export.id
            job.records_count = total_records
            job.files_count = files_exported
            job.size_bytes = len(zip_bytes)
            job.sha256_hash = zip_sha256
            job.completed_at = now
            self.session.flush()

            record_audit_event(
                self.session,
                tenant_id=tenant_context.tenant_id,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="export.completed",
                resource_type="export_job",
                resource_id=str(job.id),
                request_id=request_id,
                outcome=AuditOutcome.SUCCESS,
                metadata={
                    "export_id": str(job.id),
                    "records_count": total_records,
                    "files_count": files_exported,
                    "size_bytes": len(zip_bytes),
                    "sha256": zip_sha256,
                },
                occurred_at=now,
            )
            return job

        except Exception as exc:
            job.status = ExportJobStatus.FAILED
            job.error_message = str(exc)
            self.session.flush()

            record_audit_event(
                self.session,
                tenant_id=tenant_context.tenant_id,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="export.failed",
                resource_type="export_job",
                resource_id=str(job.id),
                request_id=request_id,
                outcome=AuditOutcome.FAILURE,
                metadata={
                    "export_id": str(job.id),
                    "reason": "processing_failure",
                },
                occurred_at=now,
            )
            raise ExportProcessingError(f"Failed to process export: {exc}") from exc

    def get_export_job(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        export_id: UUID,
    ) -> ExportJob:
        authorize(principal, tenant_context, Capability.EXPORT_READ)
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )
        job = self.session.scalar(
            select(ExportJob).where(
                ExportJob.id == export_id,
                ExportJob.tenant_id == tenant_context.tenant_id,
            )
        )
        if job is None:
            raise ExportNotFoundError("Export job not found")
        return job

    def list_export_jobs(
        self,
        principal: Principal,
        tenant_context: TenantContext,
    ) -> list[ExportJob]:
        authorize(principal, tenant_context, Capability.EXPORT_READ)
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )
        return list(
            self.session.scalars(
                select(ExportJob)
                .where(ExportJob.tenant_id == tenant_context.tenant_id)
                .order_by(ExportJob.created_at.desc())
            ).all()
        )

    def download_export_archive(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        export_id: UUID,
        request_id: str,
        now: datetime | None = None,
    ) -> tuple[ExportJob, bytes]:
        current_time = now or datetime.now(UTC)
        try:
            authorize(principal, tenant_context, Capability.EXPORT_READ)
        except AuthorizationDeniedError:
            record_audit_event(
                self.session,
                tenant_id=tenant_context.tenant_id,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="export.download_denied",
                resource_type="export_job",
                resource_id=str(export_id),
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

        job = self.session.scalar(
            select(ExportJob).where(
                ExportJob.id == export_id,
                ExportJob.tenant_id == tenant_context.tenant_id,
            )
        )
        if job is None:
            raise ExportNotFoundError("Export job not found")

        # Check expiration
        job_expires = (
            job.expires_at.replace(tzinfo=UTC) if job.expires_at.tzinfo is None else job.expires_at
        )
        if job_expires < current_time:
            job.status = ExportJobStatus.EXPIRED
            self.session.flush()
            raise ExportExpiredError("Export archive has expired and is no longer available")

        if job.status != ExportJobStatus.COMPLETED or not job.stored_file_id:
            raise ExportProcessingError("Export archive is not ready for download")

        # Download and decrypt the ZIP file from storage
        _, zip_bytes = self.storage_service.download_file(
            principal=principal,
            tenant_context=tenant_context,
            file_id=job.stored_file_id,
            request_id=request_id,
            now=current_time,
        )

        record_audit_event(
            self.session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="export.downloaded",
            resource_type="export_job",
            resource_id=str(job.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "export_id": str(job.id),
                "size_bytes": len(zip_bytes),
            },
            occurred_at=current_time,
        )

        return job, zip_bytes
