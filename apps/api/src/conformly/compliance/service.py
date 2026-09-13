from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
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
    EvidenceStatus,
    Finding,
    FindingSeverity,
    Policy,
    PolicyControlLink,
    PolicyStatus,
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

        query = (
            select(ControlStatusRecord)
            .where(ControlStatusRecord.tenant_id == tenant_context.tenant_id)
        )
        if tenant_context.role in (Role.REVIEWER, Role.AUDITOR):
            query = query.where(
                or_(
                    ControlStatusRecord.assigned_owner_user_id == principal.user_id,
                    ControlStatusRecord.assessed_by_user_id == principal.user_id,
                )
            )
        return list(
            self._session.scalars(
                query.order_by(ControlStatusRecord.updated_at.desc())
            )
        )

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
