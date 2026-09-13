from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize, authorize_resource
from conformly.authz.roles import Capability, Role
from conformly.compliance.models import (
    ComplianceTask,
    ControlImplementationStatus,
    ControlStatusRecord,
    DigestFrequency,
    EvidenceControlLink,
    EvidenceFileLink,
    EvidenceItem,
    EvidenceRevision,
    EvidenceStatus,
    Finding,
    FindingSeverity,
    Policy,
    PolicyAcknowledgement,
    PolicyControlLink,
    PolicyRevision,
    PolicyStatus,
    PolicyTemplate,
    RemediationStatus,
    TaskPriority,
    TaskStatus,
    UserNotificationPreference,
)
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.policy import DataClassification, requires_application_encryption
from conformly.crypto.types import EncryptionContext
from conformly.frameworks.models import (
    CanonicalControl,
    ControlEntityType,
    CustomControl,
)
from conformly.identity.models import Membership, MembershipStatus
from conformly.storage.models import StoredFile, StoredFileStatus
from conformly.tenancy.rls import set_rls_context


class ComplianceWorkspaceError(Exception):
    """Base exception for compliance workspace operations."""


class EvidenceNotFoundError(ComplianceWorkspaceError):
    """Raised when an evidence item is not found."""


class PolicyNotFoundError(ComplianceWorkspaceError):
    """Raised when a policy is not found."""


class TaskNotFoundError(ComplianceWorkspaceError):
    """Raised when a task is not found."""


class FindingNotFoundError(ComplianceWorkspaceError):
    """Raised when a finding is not found."""


class PolicyRevisionNotFoundError(ComplianceWorkspaceError):
    """Raised when a policy revision is not found."""


class PolicyTemplateNotFoundError(ComplianceWorkspaceError):
    """Raised when a policy template is not found."""


class EvidenceRevisionNotFoundError(ComplianceWorkspaceError):
    """Raised when an evidence revision is not found."""


class ComplianceLegalHoldActiveError(ComplianceWorkspaceError):
    """Raised when an operation is blocked due to active legal hold."""


LegalHoldActiveError = ComplianceLegalHoldActiveError


class ControlStatusRecordNotFoundError(ComplianceWorkspaceError):
    """Raised when a control status record is not found."""


class OptimisticLockConflictError(ComplianceWorkspaceError):
    """Raised when an update conflicts with the current entity version."""


class InvalidStateTransitionError(ComplianceWorkspaceError):
    """Raised when an entity lifecycle state transition is disallowed."""


class IndependentPolicyApprovalRequiredError(ComplianceWorkspaceError):
    """Raised when an author/owner attempts to approve their own policy."""


class InvalidControlReferenceError(ComplianceWorkspaceError):
    """Raised when referencing a nonexistent canonical or custom control."""


class InvalidFileReferenceError(ComplianceWorkspaceError):
    """Raised when referencing a nonexistent or inactive stored file."""


class InvalidTenantReferenceError(ComplianceWorkspaceError):
    """A reference is not available within this tenant."""


CANONICAL_POLICY_TEMPLATES: list[dict[str, Any]] = [
    {
        "slug": "information-security-policy",
        "title": "Information Security Policy",
        "category": "Governance",
        "description": "Foundational information security policy defining organizational commitments, security roles, risk assessments, and asset protection.",
        "content_template": "# Information Security Policy\n\n## 1. Objective\nThis policy defines the core principles and standards for safeguarding the organization's information assets...\n\n## 2. Scope\nApplies to all employees, contractors, systems, and third-party environments...\n\n## 3. Policy Statements\n- All assets must be classified and handled according to sensitivity.\n- Access is granted on a least-privilege basis.\n- Security incidents must be reported promptly.\n",
        "suggested_classification": "Internal",
    },
    {
        "slug": "access-control-policy",
        "title": "Access Control & Authentication Policy",
        "category": "Access Management",
        "description": "Defines credential complexity, multi-factor authentication, least privilege, and role-based access standards.",
        "content_template": "# Access Control & Authentication Policy\n\n## 1. Purpose\nEnsure that access to systems and sensitive data is restricted to authorized workforce members...\n\n## 2. Standards\n- Multi-factor authentication (MFA) is required for all administrative access and remote logins.\n- Passwords must meet minimum complexity guidelines.\n- Access reviews must be conducted at least quarterly.\n",
        "suggested_classification": "Internal",
    },
    {
        "slug": "data-protection-retention-policy",
        "title": "Data Protection & Retention Policy",
        "category": "Data Privacy",
        "description": "Governs data classification, handling, customer privacy, encryption at rest/transit, and retention/disposal schedules.",
        "content_template": "# Data Protection & Retention Policy\n\n## 1. Overview\nEstablishes rules for classifying, securing, retaining, and safely purging customer and organizational data...\n\n## 2. Classification Levels\n- Public\n- Internal\n- Confidential\n- Restricted\n\n## 3. Retention & Legal Hold\nData subject to active legal hold must never be deleted until the hold is formally released.\n",
        "suggested_classification": "Internal",
    },
    {
        "slug": "incident-response-policy",
        "title": "Incident Response & Breach Notification Policy",
        "category": "Operations",
        "description": "Standard operating procedure for detecting, reporting, containing, remediating security incidents and notifying stakeholders.",
        "content_template": "# Incident Response & Breach Notification Policy\n\n## 1. Policy\nAll security and privacy events must be reported and investigated immediately in accordance with our CIRT process...\n\n## 2. Severity Classification\n- Low / Medium / High / Critical\n\n## 3. Timelines\nRegulatory and tenant notifications must occur within required statutory windows (e.g., 72 hours under GDPR).\n",
        "suggested_classification": "Internal",
    },
    {
        "slug": "vendor-risk-management-policy",
        "title": "Vendor & Third-Party Risk Management Policy",
        "category": "Third-Party",
        "description": "Framework for evaluating, onboarding, monitoring, and offboarding third-party vendors and sub-processors.",
        "content_template": "# Vendor & Third-Party Risk Management Policy\n\n## 1. Purpose\nMitigate security and operational risks associated with third-party suppliers, SaaS providers, and contractors...\n\n## 2. Assessment Requirements\nAll vendors handling Confidential or Restricted data must undergo security review and execute a DPA prior to engagement.\n",
        "suggested_classification": "Internal",
    },
    {
        "slug": "whistleblower-protection-policy",
        "title": "Whistleblower Reporting & Non-Retaliation Policy",
        "category": "Compliance",
        "description": "Guarantees safe, confidential, and anonymous reporting channels for ethical, financial, or compliance misconduct with strict non-retaliation protection.",
        "content_template": "# Whistleblower Reporting & Non-Retaliation Policy\n\n## 1. Commitment\nThe organization guarantees that reports made in good faith may be submitted anonymously through our secure reporting channel...\n\n## 2. Non-Retaliation\nRetaliation of any kind against an individual reporting misconduct is strictly prohibited and subject to immediate disciplinary action.\n",
        "suggested_classification": "Public",
    },
]


class ComplianceService:
    """Core domain service for compliance operations, governance, tasks, and posture."""

    def __init__(self, session: Session, codec: EncryptedFieldCodec) -> None:
        self._session = session
        self._codec = codec

    def _validate_member(self, context: TenantContext, user_id: UUID | None) -> None:
        if (
            user_id is not None
            and self._session.scalar(
                select(Membership.id).where(
                    Membership.tenant_id == context.tenant_id,
                    Membership.user_id == user_id,
                    Membership.status == MembershipStatus.ACTIVE,
                )
            )
            is None
        ):
            raise InvalidTenantReferenceError("Member unavailable in this tenant")

    def _set_rls(self, principal: Principal, tenant_context: TenantContext) -> None:
        set_rls_context(
            self._session,
            user_id=principal.user_id,
            tenant_id=tenant_context.tenant_id,
            tenant_verified=True,
        )

    # =========================================================================
    # EVIDENCE MANAGEMENT
    # =========================================================================

    def create_evidence(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        title: str,
        description: str,
        classification: str = DataClassification.INTERNAL,
        owner_user_id: UUID,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        restricted_notes: str | None = None,
    ) -> EvidenceItem:
        authorize(principal, tenant_context, Capability.EVIDENCE_MANAGE)
        self._set_rls(principal, tenant_context)
        self._validate_member(tenant_context, owner_user_id)

        evidence = EvidenceItem(
            tenant_id=tenant_context.tenant_id,
            title=title,
            description=description,
            classification=classification,
            status=EvidenceStatus.DRAFT,
            owner_user_id=owner_user_id,
            valid_from=valid_from,
            valid_until=valid_until,
            version=1,
        )
        self._session.add(evidence)
        self._session.flush()

        if restricted_notes and requires_application_encryption(
            DataClassification(classification), confidential_field_selected=True
        ):
            ctx = EncryptionContext(
                tenant_id=tenant_context.tenant_id,
                resource_type="evidence_item",
                resource_id=str(evidence.id),
                field_name="restricted_notes",
            )
            evidence.restricted_notes_encrypted = self._codec.encrypt_text(restricted_notes, ctx)
            self._session.flush()

        self._record_evidence_revision(evidence, principal.user_id, "Initial evidence creation")

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="evidence.create",
            resource_type="evidence_item",
            resource_id=str(evidence.id),
            request_id=f"evidence:create:{evidence.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "evidence_id": str(evidence.id),
                "classification": classification,
                "status": evidence.status,
                "owner_user_id": str(owner_user_id),
            },
        )
        return evidence

    def get_evidence(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        evidence_id: UUID,
    ) -> tuple[EvidenceItem, str | None]:
        authorize(principal, tenant_context, Capability.EVIDENCE_READ)
        self._set_rls(principal, tenant_context)

        evidence = self._session.scalar(
            select(EvidenceItem)
            .where(
                EvidenceItem.id == evidence_id,
                EvidenceItem.tenant_id == tenant_context.tenant_id,
            )
            .options(
                selectinload(EvidenceItem.file_links),
                selectinload(EvidenceItem.control_links),
            )
        )
        if evidence is None:
            raise EvidenceNotFoundError(f"Evidence item {evidence_id} not found")

        authorize_resource(
            principal,
            tenant_context,
            Capability.EVIDENCE_READ,
            owner_user_id=evidence.owner_user_id,
        )

        decrypted_notes: str | None = None
        if evidence.restricted_notes_encrypted:
            ctx = EncryptionContext(
                tenant_id=tenant_context.tenant_id,
                resource_type="evidence_item",
                resource_id=str(evidence.id),
                field_name="restricted_notes",
            )
            decrypted_notes = self._codec.decrypt_text(evidence.restricted_notes_encrypted, ctx)

        return evidence, decrypted_notes

    def list_evidence(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        status: EvidenceStatus | None = None,
        classification: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EvidenceItem]:
        authorize(principal, tenant_context, Capability.EVIDENCE_READ)
        self._set_rls(principal, tenant_context)

        query = select(EvidenceItem).where(EvidenceItem.tenant_id == tenant_context.tenant_id)
        if tenant_context.role in (Role.REVIEWER, Role.AUDITOR):
            query = query.where(EvidenceItem.owner_user_id == principal.user_id)
        if status:
            query = query.where(EvidenceItem.status == status)
        if classification:
            query = query.where(EvidenceItem.classification == classification)

        query = (
            query.order_by(EvidenceItem.created_at.desc())
            .options(
                selectinload(EvidenceItem.file_links),
                selectinload(EvidenceItem.control_links),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(query))

    def update_evidence(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        evidence_id: UUID,
        *,
        expected_version: int,
        title: str | None = None,
        description: str | None = None,
        classification: str | None = None,
        owner_user_id: UUID | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        restricted_notes: str | None = None,
    ) -> EvidenceItem:
        authorize(principal, tenant_context, Capability.EVIDENCE_MANAGE)
        self._set_rls(principal, tenant_context)
        self._validate_member(tenant_context, owner_user_id)

        evidence = self._session.scalar(
            select(EvidenceItem).where(
                EvidenceItem.id == evidence_id,
                EvidenceItem.tenant_id == tenant_context.tenant_id,
            )
        )
        if evidence is None:
            raise EvidenceNotFoundError(f"Evidence item {evidence_id} not found")

        if evidence.version != expected_version:
            raise OptimisticLockConflictError(
                f"Version mismatch: expected {expected_version}, found {evidence.version}"
            )

        if title is not None:
            evidence.title = title
        if description is not None:
            evidence.description = description
        if classification is not None:
            evidence.classification = classification
        if owner_user_id is not None:
            evidence.owner_user_id = owner_user_id
        if valid_from is not None:
            evidence.valid_from = valid_from
        if valid_until is not None:
            evidence.valid_until = valid_until

        if restricted_notes is not None:
            ctx = EncryptionContext(
                tenant_id=tenant_context.tenant_id,
                resource_type="evidence_item",
                resource_id=str(evidence.id),
                field_name="restricted_notes",
            )
            evidence.restricted_notes_encrypted = self._codec.encrypt_text(restricted_notes, ctx)

        evidence.version += 1
        self._session.flush()

        self._record_evidence_revision(evidence, principal.user_id, "Evidence details updated")

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="evidence.update",
            resource_type="evidence_item",
            resource_id=str(evidence.id),
            request_id=f"evidence:update:{evidence.id}:{evidence.version}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "evidence_id": str(evidence.id),
                "classification": evidence.classification,
                "status": evidence.status,
                "version_number": evidence.version,
            },
        )
        return evidence

    def transition_evidence_status(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        evidence_id: UUID,
        *,
        target_status: EvidenceStatus,
        expected_version: int,
        reason: str | None = None,
    ) -> EvidenceItem:
        authorize(principal, tenant_context, Capability.EVIDENCE_MANAGE)
        self._set_rls(principal, tenant_context)

        evidence = self._session.scalar(
            select(EvidenceItem).where(
                EvidenceItem.id == evidence_id,
                EvidenceItem.tenant_id == tenant_context.tenant_id,
            )
        )
        if evidence is None:
            raise EvidenceNotFoundError(f"Evidence item {evidence_id} not found")

        if evidence.version != expected_version:
            raise OptimisticLockConflictError(
                f"Version mismatch: expected {expected_version}, found {evidence.version}"
            )

        valid_transitions: dict[EvidenceStatus, set[EvidenceStatus]] = {
            EvidenceStatus.DRAFT: {EvidenceStatus.SUBMITTED, EvidenceStatus.ARCHIVED},
            EvidenceStatus.SUBMITTED: {
                EvidenceStatus.VALID,
                EvidenceStatus.REJECTED,
                EvidenceStatus.DRAFT,
            },
            EvidenceStatus.VALID: {EvidenceStatus.EXPIRED, EvidenceStatus.ARCHIVED},
            EvidenceStatus.EXPIRED: {EvidenceStatus.DRAFT, EvidenceStatus.ARCHIVED},
            EvidenceStatus.REJECTED: {EvidenceStatus.DRAFT, EvidenceStatus.ARCHIVED},
            EvidenceStatus.ARCHIVED: {EvidenceStatus.DRAFT},
        }

        if target_status == EvidenceStatus.ARCHIVED and evidence.legal_hold:
            raise ComplianceLegalHoldActiveError(
                "Cannot archive evidence item while under active legal hold"
            )

        if target_status not in valid_transitions.get(evidence.status, set()):
            raise InvalidStateTransitionError(
                f"Cannot transition evidence from {evidence.status} to {target_status}"
            )

        previous_status = evidence.status
        evidence.status = target_status
        evidence.version += 1
        self._session.flush()

        metadata: dict[str, Any] = {
            "evidence_id": str(evidence.id),
            "previous_status": previous_status,
            "status": target_status,
            "version_number": evidence.version,
        }
        if reason:
            metadata["reason"] = reason[:255]

        self._record_evidence_revision(
            evidence, principal.user_id, f"Transitioned to {target_status}: {reason or ''}".strip()
        )

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="evidence.transition_status",
            resource_type="evidence_item",
            resource_id=str(evidence.id),
            request_id=f"evidence:transition:{evidence.id}:{evidence.version}",
            outcome=AuditOutcome.SUCCESS,
            metadata=metadata,
        )
        return evidence

    def attach_file_to_evidence(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        evidence_id: UUID,
        file_id: UUID,
    ) -> EvidenceFileLink:
        authorize(principal, tenant_context, Capability.EVIDENCE_MANAGE)
        self._set_rls(principal, tenant_context)

        evidence = self._session.scalar(
            select(EvidenceItem).where(
                EvidenceItem.id == evidence_id,
                EvidenceItem.tenant_id == tenant_context.tenant_id,
            )
        )
        if evidence is None:
            raise EvidenceNotFoundError(f"Evidence item {evidence_id} not found")

        stored_file = self._session.scalar(
            select(StoredFile).where(
                StoredFile.id == file_id,
                StoredFile.tenant_id == tenant_context.tenant_id,
                StoredFile.status == StoredFileStatus.ACTIVE,
            )
        )
        if stored_file is None:
            raise InvalidFileReferenceError(
                f"Active file {file_id} not found in tenant {tenant_context.tenant_id}"
            )

        existing = self._session.scalar(
            select(EvidenceFileLink).where(
                EvidenceFileLink.tenant_id == tenant_context.tenant_id,
                EvidenceFileLink.evidence_id == evidence_id,
                EvidenceFileLink.file_id == file_id,
            )
        )
        if existing:
            return existing

        link = EvidenceFileLink(
            tenant_id=tenant_context.tenant_id,
            evidence_id=evidence_id,
            file_id=file_id,
            attached_by_user_id=principal.user_id,
        )
        self._session.add(link)
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="evidence.attach_file",
            resource_type="evidence_file_link",
            resource_id=str(link.id),
            request_id=f"evidence:attach_file:{link.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "evidence_id": str(evidence_id),
                "file_id": str(file_id),
                "link_id": str(link.id),
            },
        )
        return link

    def remove_file_from_evidence(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        evidence_id: UUID,
        file_id: UUID,
    ) -> None:
        authorize(principal, tenant_context, Capability.EVIDENCE_MANAGE)
        self._set_rls(principal, tenant_context)

        link = self._session.scalar(
            select(EvidenceFileLink).where(
                EvidenceFileLink.tenant_id == tenant_context.tenant_id,
                EvidenceFileLink.evidence_id == evidence_id,
                EvidenceFileLink.file_id == file_id,
            )
        )
        if link:
            self._session.delete(link)
            self._session.flush()

            record_audit_event(
                self._session,
                tenant_id=tenant_context.tenant_id,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="evidence.remove_file",
                resource_type="evidence_file_link",
                resource_id=str(link.id),
                request_id=f"evidence:remove_file:{link.id}",
                outcome=AuditOutcome.SUCCESS,
                metadata={
                    "evidence_id": str(evidence_id),
                    "file_id": str(file_id),
                    "link_id": str(link.id),
                },
            )

    def link_control_to_evidence(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        evidence_id: UUID,
        control_type: ControlEntityType,
        control_id: UUID,
    ) -> EvidenceControlLink:
        authorize(principal, tenant_context, Capability.EVIDENCE_MANAGE)
        self._set_rls(principal, tenant_context)

        evidence = self._session.scalar(
            select(EvidenceItem).where(
                EvidenceItem.id == evidence_id,
                EvidenceItem.tenant_id == tenant_context.tenant_id,
            )
        )
        if evidence is None:
            raise EvidenceNotFoundError(f"Evidence item {evidence_id} not found")

        self._validate_control_reference(tenant_context.tenant_id, control_type, control_id)

        existing = self._session.scalar(
            select(EvidenceControlLink).where(
                EvidenceControlLink.tenant_id == tenant_context.tenant_id,
                EvidenceControlLink.evidence_id == evidence_id,
                EvidenceControlLink.control_type == control_type,
                EvidenceControlLink.control_id == control_id,
            )
        )
        if existing:
            return existing

        link = EvidenceControlLink(
            tenant_id=tenant_context.tenant_id,
            evidence_id=evidence_id,
            control_type=control_type,
            control_id=control_id,
            linked_by_user_id=principal.user_id,
        )
        self._session.add(link)
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="evidence.link_control",
            resource_type="evidence_control_link",
            resource_id=str(link.id),
            request_id=f"evidence:link_control:{link.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "evidence_id": str(evidence_id),
                "control_id": str(control_id),
                "control_type": str(control_type),
                "link_id": str(link.id),
            },
        )
        return link

    def unlink_control_from_evidence(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        evidence_id: UUID,
        control_type: ControlEntityType,
        control_id: UUID,
    ) -> None:
        authorize(principal, tenant_context, Capability.EVIDENCE_MANAGE)
        self._set_rls(principal, tenant_context)

        link = self._session.scalar(
            select(EvidenceControlLink).where(
                EvidenceControlLink.tenant_id == tenant_context.tenant_id,
                EvidenceControlLink.evidence_id == evidence_id,
                EvidenceControlLink.control_type == control_type,
                EvidenceControlLink.control_id == control_id,
            )
        )
        if link:
            self._session.delete(link)
            self._session.flush()

            record_audit_event(
                self._session,
                tenant_id=tenant_context.tenant_id,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="evidence.unlink_control",
                resource_type="evidence_control_link",
                resource_id=str(link.id),
                request_id=f"evidence:unlink_control:{link.id}",
                outcome=AuditOutcome.SUCCESS,
                metadata={
                    "evidence_id": str(evidence_id),
                    "control_id": str(control_id),
                    "control_type": str(control_type),
                    "link_id": str(link.id),
                },
            )

    def _record_evidence_revision(
        self,
        evidence: EvidenceItem,
        created_by_user_id: UUID,
        change_summary: str | None = None,
    ) -> EvidenceRevision:
        max_rev = self._session.scalar(
            select(func.max(EvidenceRevision.revision_number)).where(
                EvidenceRevision.tenant_id == evidence.tenant_id,
                EvidenceRevision.evidence_id == evidence.id,
            )
        )
        next_rev = (max_rev or 0) + 1

        file_ids = [str(fl.file_id) for fl in evidence.file_links] if evidence.file_links else []
        control_ids = (
            [str(cl.control_id) for cl in evidence.control_links] if evidence.control_links else []
        )

        rev = EvidenceRevision(
            tenant_id=evidence.tenant_id,
            evidence_id=evidence.id,
            revision_number=next_rev,
            title=evidence.title,
            description=evidence.description,
            classification=evidence.classification,
            status=evidence.status,
            valid_from=evidence.valid_from,
            valid_until=evidence.valid_until,
            file_ids=file_ids,
            control_ids=control_ids,
            created_by_user_id=created_by_user_id,
            change_summary=change_summary,
        )
        self._session.add(rev)
        self._session.flush()
        return rev

    def list_evidence_revisions(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        evidence_id: UUID,
    ) -> list[EvidenceRevision]:
        authorize(principal, tenant_context, Capability.EVIDENCE_READ)
        self._set_rls(principal, tenant_context)
        return list(
            self._session.scalars(
                select(EvidenceRevision)
                .where(
                    EvidenceRevision.tenant_id == tenant_context.tenant_id,
                    EvidenceRevision.evidence_id == evidence_id,
                )
                .order_by(EvidenceRevision.revision_number.desc())
            ).all()
        )

    def set_evidence_legal_hold(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        evidence_id: UUID,
        *,
        legal_hold: bool,
        reason: str,
    ) -> EvidenceItem:
        authorize(principal, tenant_context, Capability.EVIDENCE_MANAGE)
        self._set_rls(principal, tenant_context)
        evidence = self._session.scalar(
            select(EvidenceItem).where(
                EvidenceItem.id == evidence_id,
                EvidenceItem.tenant_id == tenant_context.tenant_id,
            )
        )
        if evidence is None:
            raise EvidenceNotFoundError(f"Evidence item {evidence_id} not found")

        evidence.legal_hold = legal_hold
        evidence.version += 1
        self._session.flush()

        self._record_evidence_revision(
            evidence,
            principal.user_id,
            f"Legal hold {'enabled' if legal_hold else 'released'}: {reason}",
        )

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="evidence.legal_hold.set" if legal_hold else "evidence.legal_hold.released",
            resource_type="evidence_item",
            resource_id=str(evidence.id),
            request_id=f"evidence:legal_hold:{evidence.id}:{evidence.version}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "evidence_id": str(evidence.id),
                "legal_hold": legal_hold,
                "reason": reason[:255],
            },
        )
        return evidence

    # =========================================================================
    # POLICY LIFECYCLE
    # =========================================================================

    def create_policy(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        title: str,
        description: str,
        version_string: str = "1.0",
        review_cycle_days: int = 365,
        content: str | None = None,
        classification: str = DataClassification.INTERNAL,
        restricted_content: str | None = None,
    ) -> Policy:
        authorize(principal, tenant_context, Capability.POLICY_MANAGE)
        self._set_rls(principal, tenant_context)

        policy = Policy(
            tenant_id=tenant_context.tenant_id,
            title=title,
            description=description,
            version_string=version_string,
            status=PolicyStatus.DRAFT,
            owner_user_id=principal.user_id,
            review_cycle_days=review_cycle_days,
            content=content,
            classification=classification,
            version=1,
        )
        self._session.add(policy)
        self._session.flush()

        if restricted_content and requires_application_encryption(
            DataClassification(classification), confidential_field_selected=True
        ):
            ctx = EncryptionContext(
                tenant_id=tenant_context.tenant_id,
                resource_type="policy",
                resource_id=str(policy.id),
                field_name="restricted_content",
            )
            policy.restricted_content_encrypted = self._codec.encrypt_text(restricted_content, ctx)
            self._session.flush()

        self._record_policy_revision(policy, principal.user_id, "Initial policy creation")

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="policy.create",
            resource_type="policy",
            resource_id=str(policy.id),
            request_id=f"policy:create:{policy.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "policy_id": str(policy.id),
                "classification": classification,
                "status": policy.status,
                "version_string": version_string,
                "owner_user_id": str(principal.user_id),
            },
        )
        return policy

    def get_policy(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        policy_id: UUID,
    ) -> tuple[Policy, str | None]:
        authorize(principal, tenant_context, Capability.POLICY_READ)
        self._set_rls(principal, tenant_context)

        policy = self._session.scalar(
            select(Policy)
            .where(
                Policy.id == policy_id,
                Policy.tenant_id == tenant_context.tenant_id,
            )
            .options(selectinload(Policy.control_links))
        )
        if policy is None:
            raise PolicyNotFoundError(f"Policy {policy_id} not found")

        decrypted: str | None = None
        if policy.restricted_content_encrypted:
            ctx = EncryptionContext(
                tenant_id=tenant_context.tenant_id,
                resource_type="policy",
                resource_id=str(policy.id),
                field_name="restricted_content",
            )
            decrypted = self._codec.decrypt_text(policy.restricted_content_encrypted, ctx)

        return policy, decrypted

    def list_policies(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        status: PolicyStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Policy]:
        authorize(principal, tenant_context, Capability.POLICY_READ)
        self._set_rls(principal, tenant_context)

        query = select(Policy).where(Policy.tenant_id == tenant_context.tenant_id)
        if status:
            query = query.where(Policy.status == status)

        query = (
            query.order_by(Policy.created_at.desc())
            .options(selectinload(Policy.control_links))
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(query))

    def update_policy(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        policy_id: UUID,
        *,
        expected_version: int,
        title: str | None = None,
        description: str | None = None,
        version_string: str | None = None,
        review_cycle_days: int | None = None,
        content: str | None = None,
        classification: str | None = None,
        restricted_content: str | None = None,
    ) -> Policy:
        authorize(principal, tenant_context, Capability.POLICY_MANAGE)
        self._set_rls(principal, tenant_context)

        policy = self._session.scalar(
            select(Policy).where(
                Policy.id == policy_id,
                Policy.tenant_id == tenant_context.tenant_id,
            )
        )
        if policy is None:
            raise PolicyNotFoundError(f"Policy {policy_id} not found")

        if policy.version != expected_version:
            raise OptimisticLockConflictError(
                f"Policy {policy_id} mismatch: expected {expected_version}, found {policy.version}"
            )

        if title is not None:
            policy.title = title
        if description is not None:
            policy.description = description
        if version_string is not None:
            policy.version_string = version_string
        if review_cycle_days is not None:
            policy.review_cycle_days = review_cycle_days
        if content is not None:
            policy.content = content
        if classification is not None:
            policy.classification = classification

        if restricted_content is not None:
            ctx = EncryptionContext(
                tenant_id=tenant_context.tenant_id,
                resource_type="policy",
                resource_id=str(policy.id),
                field_name="restricted_content",
            )
            policy.restricted_content_encrypted = self._codec.encrypt_text(restricted_content, ctx)

        policy.version += 1
        self._session.flush()

        self._record_policy_revision(policy, principal.user_id, "Policy details updated")

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="policy.update",
            resource_type="policy",
            resource_id=str(policy.id),
            request_id=f"policy:update:{policy.id}:{policy.version}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "policy_id": str(policy.id),
                "classification": policy.classification,
                "status": policy.status,
                "version_number": policy.version,
            },
        )
        return policy

    def submit_policy_for_review(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        policy_id: UUID,
        *,
        expected_version: int,
    ) -> Policy:
        authorize(principal, tenant_context, Capability.POLICY_MANAGE)
        self._set_rls(principal, tenant_context)

        policy = self._session.scalar(
            select(Policy).where(
                Policy.id == policy_id,
                Policy.tenant_id == tenant_context.tenant_id,
            )
        )
        if policy is None:
            raise PolicyNotFoundError(f"Policy {policy_id} not found")

        if policy.version != expected_version:
            raise OptimisticLockConflictError("Policy version mismatch")

        if policy.status not in (PolicyStatus.DRAFT, PolicyStatus.PUBLISHED):
            raise InvalidStateTransitionError(
                f"Cannot submit policy {policy_id} in state {policy.status} for review"
            )

        policy.status = PolicyStatus.IN_REVIEW
        policy.version += 1
        self._session.flush()

        self._record_policy_revision(policy, principal.user_id, "Submitted for review")

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="policy.submit_review",
            resource_type="policy",
            resource_id=str(policy.id),
            request_id=f"policy:submit:{policy.id}:{policy.version}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "policy_id": str(policy.id),
                "status": policy.status,
                "version_number": policy.version,
            },
        )
        return policy

    def approve_policy(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        policy_id: UUID,
        *,
        expected_version: int,
    ) -> Policy:
        authorize(principal, tenant_context, Capability.POLICY_MANAGE)
        self._set_rls(principal, tenant_context)

        policy = self._session.scalar(
            select(Policy).where(
                Policy.id == policy_id,
                Policy.tenant_id == tenant_context.tenant_id,
            )
        )
        if policy is None:
            raise PolicyNotFoundError(f"Policy {policy_id} not found")

        if policy.version != expected_version:
            raise OptimisticLockConflictError("Policy version mismatch")

        if policy.status != PolicyStatus.IN_REVIEW:
            raise InvalidStateTransitionError(
                f"Cannot approve policy {policy_id} in state {policy.status}"
            )

        # Independent 2-person approval: author/owner cannot approve their own policy
        if principal.user_id == policy.owner_user_id:
            raise IndependentPolicyApprovalRequiredError(
                "Policy owner cannot approve their own policy; 2-person approval required"
            )

        now = datetime.now(UTC)
        policy.status = PolicyStatus.APPROVED
        policy.approved_by_user_id = principal.user_id
        policy.approved_at = now
        policy.version += 1
        self._session.flush()

        self._record_policy_revision(policy, principal.user_id, "Policy approved")

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="policy.approve",
            resource_type="policy",
            resource_id=str(policy.id),
            request_id=f"policy:approve:{policy.id}:{policy.version}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "policy_id": str(policy.id),
                "status": policy.status,
                "version_number": policy.version,
            },
        )
        return policy

    def publish_policy(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        policy_id: UUID,
        *,
        expected_version: int,
    ) -> Policy:
        authorize(principal, tenant_context, Capability.POLICY_MANAGE)
        self._set_rls(principal, tenant_context)

        policy = self._session.scalar(
            select(Policy).where(
                Policy.id == policy_id,
                Policy.tenant_id == tenant_context.tenant_id,
            )
        )
        if policy is None:
            raise PolicyNotFoundError(f"Policy {policy_id} not found")

        if policy.version != expected_version:
            raise OptimisticLockConflictError("Policy version mismatch")

        if policy.status != PolicyStatus.APPROVED:
            raise InvalidStateTransitionError(
                f"Cannot publish policy {policy_id}: status must be approved, not {policy.status}"
            )

        now = datetime.now(UTC)
        policy.status = PolicyStatus.PUBLISHED
        policy.next_review_due = now + timedelta(days=policy.review_cycle_days)
        policy.version += 1
        self._session.flush()

        self._record_policy_revision(policy, principal.user_id, "Policy published")

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="policy.publish",
            resource_type="policy",
            resource_id=str(policy.id),
            request_id=f"policy:publish:{policy.id}:{policy.version}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "policy_id": str(policy.id),
                "status": policy.status,
                "review_cycle_days": policy.review_cycle_days,
                "version_number": policy.version,
            },
        )
        return policy

    def archive_policy(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        policy_id: UUID,
        *,
        expected_version: int,
    ) -> Policy:
        authorize(principal, tenant_context, Capability.POLICY_MANAGE)
        self._set_rls(principal, tenant_context)

        policy = self._session.scalar(
            select(Policy).where(
                Policy.id == policy_id,
                Policy.tenant_id == tenant_context.tenant_id,
            )
        )
        if policy is None:
            raise PolicyNotFoundError(f"Policy {policy_id} not found")

        if policy.version != expected_version:
            raise OptimisticLockConflictError("Policy version mismatch")

        policy.status = PolicyStatus.ARCHIVED
        policy.version += 1
        self._session.flush()

        self._record_policy_revision(policy, principal.user_id, "Policy archived")

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="policy.archive",
            resource_type="policy",
            resource_id=str(policy.id),
            request_id=f"policy:archive:{policy.id}:{policy.version}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "policy_id": str(policy.id),
                "status": policy.status,
                "version_number": policy.version,
            },
        )
        return policy

    def link_control_to_policy(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        policy_id: UUID,
        control_type: ControlEntityType,
        control_id: UUID,
    ) -> PolicyControlLink:
        authorize(principal, tenant_context, Capability.POLICY_MANAGE)
        self._set_rls(principal, tenant_context)

        policy = self._session.scalar(
            select(Policy).where(
                Policy.id == policy_id,
                Policy.tenant_id == tenant_context.tenant_id,
            )
        )
        if policy is None:
            raise PolicyNotFoundError(f"Policy {policy_id} not found")

        self._validate_control_reference(tenant_context.tenant_id, control_type, control_id)

        existing = self._session.scalar(
            select(PolicyControlLink).where(
                PolicyControlLink.tenant_id == tenant_context.tenant_id,
                PolicyControlLink.policy_id == policy_id,
                PolicyControlLink.control_type == control_type,
                PolicyControlLink.control_id == control_id,
            )
        )
        if existing:
            return existing

        link = PolicyControlLink(
            tenant_id=tenant_context.tenant_id,
            policy_id=policy_id,
            control_type=control_type,
            control_id=control_id,
            linked_by_user_id=principal.user_id,
        )
        self._session.add(link)
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="policy.link_control",
            resource_type="policy_control_link",
            resource_id=str(link.id),
            request_id=f"policy:link_control:{link.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "policy_id": str(policy_id),
                "control_id": str(control_id),
                "control_type": str(control_type),
                "link_id": str(link.id),
            },
        )
        return link

    def unlink_control_from_policy(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        policy_id: UUID,
        control_type: ControlEntityType,
        control_id: UUID,
    ) -> None:
        authorize(principal, tenant_context, Capability.POLICY_MANAGE)
        self._set_rls(principal, tenant_context)

        link = self._session.scalar(
            select(PolicyControlLink).where(
                PolicyControlLink.tenant_id == tenant_context.tenant_id,
                PolicyControlLink.policy_id == policy_id,
                PolicyControlLink.control_type == control_type,
                PolicyControlLink.control_id == control_id,
            )
        )
        if link:
            self._session.delete(link)
            self._session.flush()

            record_audit_event(
                self._session,
                tenant_id=tenant_context.tenant_id,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="policy.unlink_control",
                resource_type="policy_control_link",
                resource_id=str(link.id),
                request_id=f"policy:unlink_control:{link.id}",
                outcome=AuditOutcome.SUCCESS,
                metadata={
                    "policy_id": str(policy_id),
                    "control_id": str(control_id),
                    "control_type": str(control_type),
                    "link_id": str(link.id),
                },
            )

    def _record_policy_revision(
        self,
        policy: Policy,
        created_by_user_id: UUID,
        change_summary: str | None = None,
    ) -> PolicyRevision:
        max_rev = self._session.scalar(
            select(func.max(PolicyRevision.revision_number)).where(
                PolicyRevision.tenant_id == policy.tenant_id,
                PolicyRevision.policy_id == policy.id,
            )
        )
        next_rev = (max_rev or 0) + 1

        rev = PolicyRevision(
            tenant_id=policy.tenant_id,
            policy_id=policy.id,
            revision_number=next_rev,
            version_string=policy.version_string,
            title=policy.title,
            description=policy.description,
            content=policy.content,
            classification=policy.classification,
            status=policy.status,
            restricted_content_encrypted=policy.restricted_content_encrypted,
            created_by_user_id=created_by_user_id,
            approved_by_user_id=policy.approved_by_user_id,
            approved_at=policy.approved_at,
            change_summary=change_summary,
        )
        self._session.add(rev)
        self._session.flush()
        return rev

    def list_policy_revisions(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        policy_id: UUID,
    ) -> list[PolicyRevision]:
        authorize(principal, tenant_context, Capability.POLICY_READ)
        self._set_rls(principal, tenant_context)
        return list(
            self._session.scalars(
                select(PolicyRevision)
                .where(
                    PolicyRevision.tenant_id == tenant_context.tenant_id,
                    PolicyRevision.policy_id == policy_id,
                )
                .order_by(PolicyRevision.revision_number.desc())
            ).all()
        )

    def get_policy_revision(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        policy_id: UUID,
        revision_number: int,
    ) -> tuple[PolicyRevision, str | None]:
        authorize(principal, tenant_context, Capability.POLICY_READ)
        self._set_rls(principal, tenant_context)
        rev = self._session.scalar(
            select(PolicyRevision).where(
                PolicyRevision.tenant_id == tenant_context.tenant_id,
                PolicyRevision.policy_id == policy_id,
                PolicyRevision.revision_number == revision_number,
            )
        )
        if rev is None:
            raise PolicyRevisionNotFoundError(
                f"Policy revision {revision_number} for policy {policy_id} not found"
            )

        decrypted: str | None = None
        if rev.restricted_content_encrypted:
            ctx = EncryptionContext(
                tenant_id=tenant_context.tenant_id,
                resource_type="policy",
                resource_id=str(policy_id),
                field_name="restricted_content",
            )
            decrypted = self._codec.decrypt_text(rev.restricted_content_encrypted, ctx)
        return rev, decrypted

    # =========================================================================
    # POLICY TEMPLATES
    # =========================================================================

    def seed_canonical_policy_templates(self) -> int:
        """Seed global canonical policy templates if they do not already exist."""
        count = 0
        for item in CANONICAL_POLICY_TEMPLATES:
            existing = self._session.scalar(
                select(PolicyTemplate).where(
                    PolicyTemplate.tenant_id.is_(None),
                    PolicyTemplate.slug == item["slug"],
                )
            )
            if existing is None:
                tmpl = PolicyTemplate(
                    tenant_id=None,
                    slug=item["slug"],
                    title=item["title"],
                    category=item["category"],
                    description=item["description"],
                    content_template=item["content_template"],
                    suggested_classification=item.get("suggested_classification", "Internal"),
                    is_canonical=True,
                )
                self._session.add(tmpl)
                count += 1
        if count > 0:
            self._session.flush()
        return count

    def list_policy_templates(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        category: str | None = None,
    ) -> list[PolicyTemplate]:
        authorize(principal, tenant_context, Capability.POLICY_READ)
        self._set_rls(principal, tenant_context)

        query = select(PolicyTemplate).where(
            or_(
                PolicyTemplate.tenant_id.is_(None),
                PolicyTemplate.tenant_id == tenant_context.tenant_id,
            )
        )
        if category:
            query = query.where(PolicyTemplate.category == category)
        query = query.order_by(PolicyTemplate.is_canonical.desc(), PolicyTemplate.title.asc())
        return list(self._session.scalars(query).all())

    def get_policy_template(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        template_id: UUID,
    ) -> PolicyTemplate:
        authorize(principal, tenant_context, Capability.POLICY_READ)
        self._set_rls(principal, tenant_context)
        tmpl = self._session.scalar(
            select(PolicyTemplate).where(
                PolicyTemplate.id == template_id,
                or_(
                    PolicyTemplate.tenant_id.is_(None),
                    PolicyTemplate.tenant_id == tenant_context.tenant_id,
                ),
            )
        )
        if tmpl is None:
            raise PolicyTemplateNotFoundError(f"Policy template {template_id} not found")
        return tmpl

    def instantiate_policy_from_template(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        template_id: UUID,
        *,
        title: str | None = None,
        description: str | None = None,
        classification: str | None = None,
    ) -> Policy:
        authorize(principal, tenant_context, Capability.POLICY_MANAGE)
        tmpl = self.get_policy_template(principal, tenant_context, template_id)

        policy = self.create_policy(
            principal,
            tenant_context,
            title=title or tmpl.title,
            description=description or tmpl.description,
            content=tmpl.content_template,
            classification=classification or tmpl.suggested_classification,
            version_string="1.0",
        )
        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="policy.instantiate_from_template",
            resource_type="policy",
            resource_id=str(policy.id),
            request_id=f"policy:instantiate:{policy.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "template_id": str(tmpl.id),
                "template_slug": tmpl.slug,
                "policy_id": str(policy.id),
            },
        )
        return policy

    def create_custom_policy_template(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        slug: str,
        title: str,
        category: str,
        description: str,
        content_template: str,
        suggested_classification: str = "Internal",
    ) -> PolicyTemplate:
        authorize(principal, tenant_context, Capability.POLICY_MANAGE)
        self._set_rls(principal, tenant_context)

        tmpl = PolicyTemplate(
            tenant_id=tenant_context.tenant_id,
            slug=slug,
            title=title,
            category=category,
            description=description,
            content_template=content_template,
            suggested_classification=suggested_classification,
            is_canonical=False,
        )
        self._session.add(tmpl)
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="policy_template.create",
            resource_type="policy_template",
            resource_id=str(tmpl.id),
            request_id=f"policy_template:create:{tmpl.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={"template_id": str(tmpl.id), "slug": slug},
        )
        return tmpl

    # =========================================================================
    # POLICY ACKNOWLEDGEMENTS
    # =========================================================================

    def acknowledge_policy(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        policy_id: UUID,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> PolicyAcknowledgement:
        self._set_rls(principal, tenant_context)

        policy = self._session.scalar(
            select(Policy).where(
                Policy.id == policy_id,
                Policy.tenant_id == tenant_context.tenant_id,
            )
        )
        if policy is None:
            raise PolicyNotFoundError(f"Policy {policy_id} not found")

        if policy.status != PolicyStatus.PUBLISHED:
            raise InvalidStateTransitionError(
                f"Cannot acknowledge policy {policy_id} in state {policy.status}; must be published"
            )

        latest_rev = self._session.scalar(
            select(PolicyRevision)
            .where(
                PolicyRevision.tenant_id == tenant_context.tenant_id,
                PolicyRevision.policy_id == policy_id,
            )
            .order_by(PolicyRevision.revision_number.desc())
        )

        existing = self._session.scalar(
            select(PolicyAcknowledgement).where(
                PolicyAcknowledgement.tenant_id == tenant_context.tenant_id,
                PolicyAcknowledgement.policy_id == policy_id,
                PolicyAcknowledgement.user_id == principal.user_id,
                PolicyAcknowledgement.policy_revision_id == (latest_rev.id if latest_rev else None),
            )
        )
        if existing:
            return existing

        now = datetime.now(UTC)
        ack = PolicyAcknowledgement(
            tenant_id=tenant_context.tenant_id,
            policy_id=policy.id,
            policy_revision_id=latest_rev.id if latest_rev else None,
            user_id=principal.user_id,
            acknowledged_at=now,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._session.add(ack)
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="policy.acknowledge",
            resource_type="policy_acknowledgement",
            resource_id=str(ack.id),
            request_id=f"policy:ack:{ack.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "policy_id": str(policy.id),
                "policy_revision_id": str(latest_rev.id) if latest_rev else None,
                "revision_number": latest_rev.revision_number if latest_rev else None,
            },
            occurred_at=now,
        )
        return ack

    def list_policy_acknowledgements(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        policy_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PolicyAcknowledgement]:
        authorize(principal, tenant_context, Capability.POLICY_READ)
        self._set_rls(principal, tenant_context)
        return list(
            self._session.scalars(
                select(PolicyAcknowledgement)
                .where(
                    PolicyAcknowledgement.tenant_id == tenant_context.tenant_id,
                    PolicyAcknowledgement.policy_id == policy_id,
                )
                .order_by(PolicyAcknowledgement.acknowledged_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )

    def get_my_acknowledgements(
        self,
        principal: Principal,
        tenant_context: TenantContext,
    ) -> list[PolicyAcknowledgement]:
        self._set_rls(principal, tenant_context)
        return list(
            self._session.scalars(
                select(PolicyAcknowledgement)
                .where(
                    PolicyAcknowledgement.tenant_id == tenant_context.tenant_id,
                    PolicyAcknowledgement.user_id == principal.user_id,
                )
                .order_by(PolicyAcknowledgement.acknowledged_at.desc())
            ).all()
        )

    # =========================================================================
    # COMPLIANCE TASKS
    # =========================================================================

    def create_task(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        title: str,
        description: str,
        due_date: datetime,
        priority: TaskPriority = TaskPriority.MEDIUM,
        assignee_user_id: UUID | None = None,
        control_type: ControlEntityType | None = None,
        control_id: UUID | None = None,
        evidence_id: UUID | None = None,
        policy_id: UUID | None = None,
    ) -> ComplianceTask:
        authorize(principal, tenant_context, Capability.TASK_MANAGE)
        self._set_rls(principal, tenant_context)
        self._validate_member(tenant_context, assignee_user_id)
        for model, reference in ((EvidenceItem, evidence_id), (Policy, policy_id)):
            if (
                reference is not None
                and self._session.scalar(
                    select(model.id).where(
                        model.id == reference, model.tenant_id == tenant_context.tenant_id
                    )
                )
                is None
            ):
                raise InvalidTenantReferenceError("Reference unavailable in this tenant")

        if (control_type is None) != (control_id is None):
            raise InvalidControlReferenceError("Control type and ID must be provided together")
        if control_type and control_id:
            self._validate_control_reference(tenant_context.tenant_id, control_type, control_id)

        task = ComplianceTask(
            tenant_id=tenant_context.tenant_id,
            title=title,
            description=description,
            due_date=due_date,
            status=TaskStatus.PENDING,
            priority=priority,
            assignee_user_id=assignee_user_id,
            control_type=control_type,
            control_id=control_id,
            evidence_id=evidence_id,
            policy_id=policy_id,
            version=1,
        )
        self._session.add(task)
        self._session.flush()

        metadata: dict[str, Any] = {
            "task_id": str(task.id),
            "status": task.status,
            "priority": task.priority,
        }
        if assignee_user_id:
            metadata["assignee_user_id"] = str(assignee_user_id)

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="task.create",
            resource_type="compliance_task",
            resource_id=str(task.id),
            request_id=f"task:create:{task.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata=metadata,
        )
        return task

    def get_task(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        task_id: UUID,
    ) -> ComplianceTask:
        authorize(principal, tenant_context, Capability.TASK_READ)
        self._set_rls(principal, tenant_context)

        task = self._session.scalar(
            select(ComplianceTask).where(
                ComplianceTask.id == task_id,
                ComplianceTask.tenant_id == tenant_context.tenant_id,
            )
        )
        if task is None:
            raise TaskNotFoundError(f"Task {task_id} not found")
        authorize_resource(
            principal,
            tenant_context,
            Capability.TASK_READ,
            assigned_user_ids=[task.assignee_user_id] if task.assignee_user_id else None,
        )
        return task

    def list_tasks(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ComplianceTask]:
        authorize(principal, tenant_context, Capability.TASK_READ)
        self._set_rls(principal, tenant_context)

        query = select(ComplianceTask).where(ComplianceTask.tenant_id == tenant_context.tenant_id)
        if tenant_context.role in (Role.REVIEWER, Role.AUDITOR):
            query = query.where(ComplianceTask.assignee_user_id == principal.user_id)
        if status:
            query = query.where(ComplianceTask.status == status)
        if priority:
            query = query.where(ComplianceTask.priority == priority)

        query = query.order_by(ComplianceTask.due_date.asc()).limit(limit).offset(offset)
        return list(self._session.scalars(query))

    def update_task(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        task_id: UUID,
        *,
        expected_version: int,
        title: str | None = None,
        description: str | None = None,
        due_date: datetime | None = None,
        priority: TaskPriority | None = None,
        assignee_user_id: UUID | None = None,
        status: TaskStatus | None = None,
    ) -> ComplianceTask:
        authorize(principal, tenant_context, Capability.TASK_MANAGE)
        self._set_rls(principal, tenant_context)
        self._validate_member(tenant_context, assignee_user_id)

        task = self._session.scalar(
            select(ComplianceTask).where(
                ComplianceTask.id == task_id,
                ComplianceTask.tenant_id == tenant_context.tenant_id,
            )
        )
        if task is None:
            raise TaskNotFoundError(f"Task {task_id} not found")

        if task.version != expected_version:
            raise OptimisticLockConflictError("Task version mismatch")

        if status is not None:
            self._transition_task(task, status, principal)
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if due_date is not None:
            task.due_date = due_date
        if priority is not None:
            task.priority = priority
        if assignee_user_id is not None:
            task.assignee_user_id = assignee_user_id
        task.version += 1
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="task.update",
            resource_type="compliance_task",
            resource_id=str(task.id),
            request_id=f"task:update:{task.id}:{task.version}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "task_id": str(task.id),
                "status": task.status,
                "priority": task.priority,
                "version_number": task.version,
            },
        )
        return task

    @staticmethod
    def _transition_task(task: ComplianceTask, target: TaskStatus, principal: Principal) -> None:
        active = {TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.OVERDUE}
        allowed = {
            TaskStatus.PENDING: {
                TaskStatus.IN_PROGRESS,
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
            },
            TaskStatus.IN_PROGRESS: {
                TaskStatus.PENDING,
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
            },
            TaskStatus.OVERDUE: {
                TaskStatus.IN_PROGRESS,
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
            },
            TaskStatus.COMPLETED: {TaskStatus.PENDING},
            TaskStatus.CANCELLED: {TaskStatus.PENDING},
        }
        if target not in allowed[task.status]:
            raise InvalidStateTransitionError("Invalid task status transition")
        task.status = target
        if target == TaskStatus.COMPLETED:
            task.completed_at = datetime.now(UTC)
            task.completed_by_user_id = principal.user_id
        elif target in active:
            task.completed_at = None
            task.completed_by_user_id = None

    def complete_task(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        task_id: UUID,
        *,
        expected_version: int,
    ) -> ComplianceTask:
        authorize(principal, tenant_context, Capability.TASK_MANAGE)
        self._set_rls(principal, tenant_context)

        task = self._session.scalar(
            select(ComplianceTask).where(
                ComplianceTask.id == task_id,
                ComplianceTask.tenant_id == tenant_context.tenant_id,
            )
        )
        if task is None:
            raise TaskNotFoundError(f"Task {task_id} not found")

        if task.version != expected_version:
            raise OptimisticLockConflictError("Task version mismatch")

        self._transition_task(task, TaskStatus.COMPLETED, principal)
        task.version += 1
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="task.complete",
            resource_type="compliance_task",
            resource_id=str(task.id),
            request_id=f"task:complete:{task.id}:{task.version}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "task_id": str(task.id),
                "status": task.status,
                "version_number": task.version,
            },
        )
        return task

    # =========================================================================
    # FINDINGS & REMEDIATION
    # =========================================================================

    def create_finding(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        title: str,
        description: str,
        severity: FindingSeverity = FindingSeverity.MEDIUM,
        due_date: datetime | None = None,
        owner_user_id: UUID | None = None,
        control_type: ControlEntityType | None = None,
        control_id: UUID | None = None,
        remediation_plan: str | None = None,
    ) -> Finding:
        authorize(principal, tenant_context, Capability.FINDING_MANAGE)
        self._set_rls(principal, tenant_context)
        self._validate_member(tenant_context, owner_user_id)

        if (control_type is None) != (control_id is None):
            raise InvalidControlReferenceError("Control type and ID must be provided together")
        if control_type and control_id:
            self._validate_control_reference(tenant_context.tenant_id, control_type, control_id)

        finding = Finding(
            tenant_id=tenant_context.tenant_id,
            title=title,
            description=description,
            severity=severity,
            remediation_status=RemediationStatus.OPEN,
            due_date=due_date,
            owner_user_id=owner_user_id,
            control_type=control_type,
            control_id=control_id,
            remediation_plan=remediation_plan,
            version=1,
        )
        self._session.add(finding)
        self._session.flush()

        if severity in (FindingSeverity.HIGH, FindingSeverity.CRITICAL) and control_id:
            from conformly.preaudit.service import auto_suspend_active_certificates

            auto_suspend_active_certificates(
                self._session,
                tenant_context.tenant_id,
                control_id=control_id,
                reason=f"{severity.value} finding raised on control {control_id}",
            )

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="finding.create",
            resource_type="finding",
            resource_id=str(finding.id),
            request_id=f"finding:create:{finding.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "finding_id": str(finding.id),
                "severity": finding.severity,
                "remediation_status": finding.remediation_status,
            },
        )
        return finding

    def get_finding(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        finding_id: UUID,
    ) -> Finding:
        authorize(principal, tenant_context, Capability.FINDING_READ)
        self._set_rls(principal, tenant_context)

        finding = self._session.scalar(
            select(Finding).where(
                Finding.id == finding_id,
                Finding.tenant_id == tenant_context.tenant_id,
            )
        )
        if finding is None:
            raise FindingNotFoundError(f"Finding {finding_id} not found")
        authorize_resource(
            principal,
            tenant_context,
            Capability.FINDING_READ,
            owner_user_id=finding.owner_user_id,
        )
        return finding

    def list_findings(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        severity: FindingSeverity | None = None,
        remediation_status: RemediationStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Finding]:
        authorize(principal, tenant_context, Capability.FINDING_READ)
        self._set_rls(principal, tenant_context)

        query = select(Finding).where(Finding.tenant_id == tenant_context.tenant_id)
        if tenant_context.role in (Role.REVIEWER, Role.AUDITOR):
            query = query.where(Finding.owner_user_id == principal.user_id)
        if severity:
            query = query.where(Finding.severity == severity)
        if remediation_status:
            query = query.where(Finding.remediation_status == remediation_status)

        query = query.order_by(Finding.created_at.desc()).limit(limit).offset(offset)
        return list(self._session.scalars(query))

    def update_finding(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        finding_id: UUID,
        *,
        expected_version: int,
        title: str | None = None,
        description: str | None = None,
        severity: FindingSeverity | None = None,
        due_date: datetime | None = None,
        owner_user_id: UUID | None = None,
        remediation_plan: str | None = None,
    ) -> Finding:
        authorize(principal, tenant_context, Capability.FINDING_MANAGE)
        self._set_rls(principal, tenant_context)
        self._validate_member(tenant_context, owner_user_id)

        finding = self._session.scalar(
            select(Finding).where(
                Finding.id == finding_id,
                Finding.tenant_id == tenant_context.tenant_id,
            )
        )
        if finding is None:
            raise FindingNotFoundError(f"Finding {finding_id} not found")

        if finding.version != expected_version:
            raise OptimisticLockConflictError("Finding version mismatch")

        if title is not None:
            finding.title = title
        if description is not None:
            finding.description = description
        if severity is not None:
            finding.severity = severity
        if due_date is not None:
            finding.due_date = due_date
        if owner_user_id is not None:
            finding.owner_user_id = owner_user_id
        if remediation_plan is not None:
            finding.remediation_plan = remediation_plan

        finding.version += 1
        self._session.flush()

        if severity in (FindingSeverity.HIGH, FindingSeverity.CRITICAL) and finding.control_id:
            from conformly.preaudit.service import auto_suspend_active_certificates

            auto_suspend_active_certificates(
                self._session,
                tenant_context.tenant_id,
                control_id=finding.control_id,
                reason=f"Finding on control {finding.control_id} escalated to {severity.value}",
            )

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="finding.update",
            resource_type="finding",
            resource_id=str(finding.id),
            request_id=f"finding:update:{finding.id}:{finding.version}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "finding_id": str(finding.id),
                "severity": finding.severity,
                "version_number": finding.version,
            },
        )
        return finding

    def update_remediation_status(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        finding_id: UUID,
        *,
        expected_version: int,
        remediation_status: RemediationStatus,
        remediation_summary: str | None = None,
    ) -> Finding:
        authorize(principal, tenant_context, Capability.FINDING_MANAGE)
        self._set_rls(principal, tenant_context)

        finding = self._session.scalar(
            select(Finding).where(
                Finding.id == finding_id,
                Finding.tenant_id == tenant_context.tenant_id,
            )
        )
        if finding is None:
            raise FindingNotFoundError(f"Finding {finding_id} not found")

        if finding.version != expected_version:
            raise OptimisticLockConflictError("Finding version mismatch")

        previous_status = finding.remediation_status
        finding.remediation_status = remediation_status
        if remediation_summary is not None:
            finding.remediation_summary = remediation_summary

        if remediation_status == RemediationStatus.RESOLVED:
            finding.resolved_at = datetime.now(UTC)
            finding.resolved_by_user_id = principal.user_id

        finding.version += 1
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="finding.update_remediation",
            resource_type="finding",
            resource_id=str(finding.id),
            request_id=f"finding:remediate:{finding.id}:{finding.version}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "finding_id": str(finding.id),
                "previous_status": previous_status,
                "remediation_status": remediation_status,
                "version_number": finding.version,
            },
        )
        return finding

    # =========================================================================
    # CONTROL IMPLEMENTATION STATUS POSTURE
    # =========================================================================

    def upsert_control_status(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        control_type: ControlEntityType,
        control_id: UUID,
        status: ControlImplementationStatus,
        assigned_owner_user_id: UUID | None = None,
        notes: str | None = None,
        expected_version: int | None = None,
    ) -> ControlStatusRecord:
        authorize(principal, tenant_context, Capability.CONTROL_STATUS_MANAGE)
        self._set_rls(principal, tenant_context)
        self._validate_member(tenant_context, assigned_owner_user_id)

        self._validate_control_reference(tenant_context.tenant_id, control_type, control_id)

        record = self._session.scalar(
            select(ControlStatusRecord).where(
                ControlStatusRecord.tenant_id == tenant_context.tenant_id,
                ControlStatusRecord.control_type == control_type,
                ControlStatusRecord.control_id == control_id,
            )
        )

        now = datetime.now(UTC)
        if record is None:
            record = ControlStatusRecord(
                tenant_id=tenant_context.tenant_id,
                control_type=control_type,
                control_id=control_id,
                status=status,
                assigned_owner_user_id=assigned_owner_user_id,
                notes=notes,
                last_assessed_at=now,
                assessed_by_user_id=principal.user_id,
                version=1,
            )
            self._session.add(record)
        else:
            if expected_version is None or record.version != expected_version:
                raise OptimisticLockConflictError("Control status version mismatch")
            record.status = status
            if assigned_owner_user_id is not None:
                record.assigned_owner_user_id = assigned_owner_user_id
            if notes is not None:
                record.notes = notes
            record.last_assessed_at = now
            record.assessed_by_user_id = principal.user_id
            record.version += 1

        self._session.flush()

        if status == ControlImplementationStatus.NOT_STARTED:
            from conformly.preaudit.service import auto_suspend_active_certificates

            auto_suspend_active_certificates(
                self._session,
                tenant_context.tenant_id,
                control_id=control_id,
                reason=f"Control {control_id} status regressed to NOT_STARTED",
            )

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="control_status.upsert",
            resource_type="control_status_record",
            resource_id=str(record.id),
            request_id=f"control_status:{record.id}:{record.version}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "control_id": str(control_id),
                "control_type": str(control_type),
                "control_status": str(status),
                "version_number": record.version,
            },
        )
        return record

    def get_control_status_matrix(
        self,
        principal: Principal,
        tenant_context: TenantContext,
    ) -> list[ControlStatusRecord]:
        authorize(principal, tenant_context, Capability.EVIDENCE_READ)
        self._set_rls(principal, tenant_context)

        query = select(ControlStatusRecord).where(
            ControlStatusRecord.tenant_id == tenant_context.tenant_id
        )
        if tenant_context.role in (Role.REVIEWER, Role.AUDITOR):
            query = query.where(
                or_(
                    ControlStatusRecord.assigned_owner_user_id == principal.user_id,
                    ControlStatusRecord.assessed_by_user_id == principal.user_id,
                )
            )
        return list(self._session.scalars(query.order_by(ControlStatusRecord.updated_at.desc())))

    # =========================================================================
    # USER NOTIFICATION PREFERENCES
    # =========================================================================

    def get_or_create_user_preferences(
        self,
        principal: Principal,
        tenant_context: TenantContext,
    ) -> UserNotificationPreference:
        self._set_rls(principal, tenant_context)

        pref = self._session.scalar(
            select(UserNotificationPreference).where(
                UserNotificationPreference.tenant_id == tenant_context.tenant_id,
                UserNotificationPreference.user_id == principal.user_id,
            )
        )
        if pref is None:
            pref = UserNotificationPreference(
                tenant_id=tenant_context.tenant_id,
                user_id=principal.user_id,
                email_enabled=True,
                digest_frequency=DigestFrequency.IMMEDIATE,
            )
            self._session.add(pref)
            self._session.flush()

        return pref

    def update_user_preferences(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        email_enabled: bool | None = None,
        digest_frequency: DigestFrequency | None = None,
        notify_task_assigned: bool | None = None,
        notify_task_due: bool | None = None,
        notify_evidence_expired: bool | None = None,
        notify_policy_review: bool | None = None,
        notify_finding_raised: bool | None = None,
    ) -> UserNotificationPreference:
        pref = self.get_or_create_user_preferences(principal, tenant_context)

        if email_enabled is not None:
            pref.email_enabled = email_enabled
        if digest_frequency is not None:
            pref.digest_frequency = digest_frequency
        if notify_task_assigned is not None:
            pref.notify_task_assigned = notify_task_assigned
        if notify_task_due is not None:
            pref.notify_task_due = notify_task_due
        if notify_evidence_expired is not None:
            pref.notify_evidence_expired = notify_evidence_expired
        if notify_policy_review is not None:
            pref.notify_policy_review = notify_policy_review
        if notify_finding_raised is not None:
            pref.notify_finding_raised = notify_finding_raised

        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="preferences.update",
            resource_type="user_notification_preference",
            resource_id=str(pref.id),
            request_id=f"preferences:update:{pref.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={"preference_id": str(pref.id)},
        )
        return pref

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _validate_control_reference(
        self, tenant_id: UUID, control_type: ControlEntityType, control_id: UUID
    ) -> None:
        if control_type == ControlEntityType.CANONICAL:
            canonical = self._session.scalar(
                select(CanonicalControl).where(CanonicalControl.id == control_id)
            )
            if canonical is None:
                raise InvalidControlReferenceError(
                    f"Canonical control {control_id} does not exist in framework catalog"
                )
        elif control_type == ControlEntityType.CUSTOM:
            custom = self._session.scalar(
                select(CustomControl).where(
                    CustomControl.id == control_id,
                    CustomControl.tenant_id == tenant_id,
                )
            )
            if custom is None:
                raise InvalidControlReferenceError(
                    f"Custom control {control_id} does not exist in tenant {tenant_id}"
                )
