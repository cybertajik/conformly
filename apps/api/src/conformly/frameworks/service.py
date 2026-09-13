import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize
from conformly.authz.roles import Capability
from conformly.frameworks.impact import ImpactAnalysisReport, compute_framework_impact
from conformly.frameworks.models import (
    AdoptionStatus,
    CanonicalControl,
    ControlEntityType,
    ControlMapping,
    CoverageDisposition,
    CoverageLedgerEntry,
    CustomControl,
    CustomControlStatus,
    EvidenceSpecification,
    Framework,
    FrameworkVersion,
    MappingType,
    OverlayApplicability,
    ReleaseState,
    RequirementControlMapping,
    SourceRequirement,
    SourceRequirementType,
    TenantControlOverlay,
    TenantFrameworkAdoption,
)
from conformly.tenancy.rls import set_rls_context


class FrameworkCatalogError(Exception):
    """Base exception for framework catalog operations."""


class FrameworkNotFoundError(FrameworkCatalogError):
    """Raised when a framework does not exist."""


class FrameworkVersionNotFoundError(FrameworkCatalogError):
    """Raised when a framework version does not exist."""


class CanonicalControlNotFoundError(FrameworkCatalogError):
    """Raised when a canonical control does not exist."""


class ImmutableCanonicalVersionError(FrameworkCatalogError):
    """Raised when attempting to modify controls or metadata of a non-draft version."""


class IndependentApprovalRequiredError(FrameworkCatalogError):
    """Raised when a version creator attempts to approve their own version draft."""


class UnapprovedReleaseError(FrameworkCatalogError):
    """Raised when attempting to release an unapproved framework version."""


class InvalidStateTransitionError(FrameworkCatalogError):
    """Raised when a version lifecycle state transition is invalid."""


class StaleReviewError(FrameworkCatalogError):
    """Raised when content has been modified since review/approval preparation."""


class ReleaseBlockedError(FrameworkCatalogError):
    """Raised when framework release is blocked by unresolved dependencies or critical checks."""


class VersionRetiredError(FrameworkCatalogError):
    """Raised when attempting an invalid operation on a retired version."""


class AdoptionNotFoundError(FrameworkCatalogError):
    """Raised when a tenant adoption record is not found."""


class ControlOverlayNotFoundError(FrameworkCatalogError):
    """Raised when a tenant control overlay is not found."""


class CustomControlNotFoundError(FrameworkCatalogError):
    """Raised when a custom control is not found."""


class ControlMappingNotFoundError(FrameworkCatalogError):
    """Raised when a control mapping is not found."""


class CoverageLedgerError(FrameworkCatalogError):
    """Base exception for coverage ledger operations."""


class UnaccountedSourceRequirementsError(CoverageLedgerError):
    """Raised when source requirements have no coverage ledger entry."""


class InvalidCoverageMappingError(CoverageLedgerError):
    """Raised when an IMPLEMENTED requirement has no controls or orphan mappings exist."""


class SourceRequirementNotFoundError(FrameworkCatalogError):
    """Raised when a source requirement is not found."""


class EvidenceSpecificationNotFoundError(FrameworkCatalogError):
    """Raised when an evidence specification is not found."""


@dataclass(frozen=True)
class CoverageLedgerValidationReport:
    version_id: UUID
    total_requirements: int
    implemented_count: int
    not_customer_obligation_count: int
    profile_exclusion_count: int
    blocked_count: int
    is_complete: bool
    unaccounted_references: list[str] = field(default_factory=list)
    blocked_references: list[str] = field(default_factory=list)
    disposition_summary: dict[str, int] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return self.is_complete and not self.blocked_references and not self.unaccounted_references

    @property
    def unaccounted_count(self) -> int:
        return len(self.unaccounted_references)

    @property
    def accounted_requirements(self) -> int:
        return (
            self.implemented_count
            + self.not_customer_obligation_count
            + self.profile_exclusion_count
        )


def compute_version_content_digest(version: FrameworkVersion) -> str:
    """Compute a deterministic cryptographic SHA-256 digest over controls, requirements, mappings, evidence specs, and coverage ledger."""
    hasher = hashlib.sha256()
    hasher.update(str(version.framework_id).encode("utf-8"))
    hasher.update(version.version.encode("utf-8"))
    sorted_controls = sorted(version.controls, key=lambda c: c.identifier)
    for c in sorted_controls:
        hasher.update(c.identifier.encode("utf-8"))
        hasher.update(c.title.encode("utf-8"))
        hasher.update(c.description.encode("utf-8"))
        hasher.update(c.category.encode("utf-8"))
        if c.guidance:
            hasher.update(c.guidance.encode("utf-8"))
        hasher.update(str(c.sort_order).encode("utf-8"))

    if hasattr(version, "source_requirements") and version.source_requirements:
        sorted_reqs = sorted(version.source_requirements, key=lambda r: r.source_reference)
        for r in sorted_reqs:
            hasher.update(r.source_reference.encode("utf-8"))
            hasher.update(r.title.encode("utf-8"))
            hasher.update(str(r.requirement_type).encode("utf-8"))
            hasher.update(r.source_authority.encode("utf-8"))
            hasher.update(r.edition_or_amendment.encode("utf-8"))
            hasher.update(r.source_text.encode("utf-8"))
            if r.conformly_guidance:
                hasher.update(r.conformly_guidance.encode("utf-8"))
            hasher.update(r.content_rights.encode("utf-8"))

    if hasattr(version, "requirement_control_mappings") and version.requirement_control_mappings:
        sorted_maps = sorted(
            version.requirement_control_mappings,
            key=lambda m: (str(m.source_requirement_id), str(m.canonical_control_id)),
        )
        for m in sorted_maps:
            hasher.update(str(m.source_requirement_id).encode("utf-8"))
            hasher.update(str(m.canonical_control_id).encode("utf-8"))
            hasher.update(str(m.mapping_type).encode("utf-8"))

    if hasattr(version, "evidence_specifications") and version.evidence_specifications:
        sorted_specs = sorted(version.evidence_specifications, key=lambda s: s.identifier)
        for s in sorted_specs:
            hasher.update(s.identifier.encode("utf-8"))
            hasher.update(s.title.encode("utf-8"))
            hasher.update(s.evidence_type.encode("utf-8"))
            hasher.update(str(s.original_file_required).encode("utf-8"))
            hasher.update(s.confidentiality_level.encode("utf-8"))

    if hasattr(version, "coverage_ledger_entries") and version.coverage_ledger_entries:
        sorted_entries = sorted(
            version.coverage_ledger_entries, key=lambda e: str(e.source_requirement_id)
        )
        for e in sorted_entries:
            hasher.update(str(e.source_requirement_id).encode("utf-8"))
            hasher.update(str(e.disposition).encode("utf-8"))
            hasher.update(e.rationale.encode("utf-8"))

    return hasher.hexdigest()


class FrameworkService:
    """Provides canonical catalog management, impact analysis, and tenant adoption services."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # -------------------------------------------------------------------------
    # Canonical Catalog (System-Scoped, Platform Admin only for mutations)
    # -------------------------------------------------------------------------

    def create_framework(
        self,
        principal: Principal,
        name: str,
        slug: str,
        description: str | None,
        request_id: str,
    ) -> Framework:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can mutate canonical frameworks")

        clean_slug = slug.strip().lower()
        clean_name = name.strip()

        framework = Framework(
            name=clean_name,
            slug=clean_slug,
            description=description.strip() if description else None,
        )
        self.session.add(framework)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="canonical_framework.created",
            resource_type="framework",
            resource_id=str(framework.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"framework_id": str(framework.id), "framework_slug": framework.slug},
            occurred_at=datetime.now(UTC),
        )
        return framework

    def create_version_draft(
        self,
        principal: Principal,
        framework_id: UUID,
        version_str: str,
        release_notes: str | None,
        request_id: str,
    ) -> FrameworkVersion:
        if not principal.is_platform_admin:
            raise PermissionError(
                "only platform administrators can create canonical framework versions"
            )

        framework = self.session.get(Framework, framework_id)
        if not framework:
            raise FrameworkNotFoundError(f"framework {framework_id} not found")

        version = FrameworkVersion(
            framework_id=framework_id,
            version=version_str.strip(),
            release_state=ReleaseState.DRAFT,
            release_notes=release_notes.strip() if release_notes else None,
            created_by_user_id=principal.user_id,
        )
        self.session.add(version)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="canonical_framework_version.created",
            resource_type="framework_version",
            resource_id=str(version.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "framework_id": str(framework.id),
                "framework_slug": framework.slug,
                "version_id": str(version.id),
                "version_string": version.version,
                "release_state": version.release_state,
            },
            occurred_at=datetime.now(UTC),
        )
        return version

    def _invalidate_version_approvals_on_edit(
        self, version: FrameworkVersion, principal: Principal, request_id: str
    ) -> None:
        """Invalidate pending approvals if a draft framework version is edited."""
        if version.legal_reviewed_by_user_id is not None or version.approved_by_user_id is not None:
            version.legal_reviewed_by_user_id = None
            version.legal_reviewed_at = None
            version.legal_review_notes = None
            version.approved_by_user_id = None
            version.approved_at = None
            version.approval_notes = None
            version.release_state = ReleaseState.DRAFT
            record_audit_event(
                self.session,
                tenant_id=None,
                actor_type=AuditActorType.USER,
                actor_id=principal.user_id,
                action="canonical_framework_version.approvals_invalidated",
                resource_type="framework_version",
                resource_id=str(version.id),
                request_id=request_id,
                outcome=AuditOutcome.SUCCESS,
                metadata={
                    "version_id": str(version.id),
                    "reason": "content_modified_in_draft",
                },
                occurred_at=datetime.now(UTC),
            )

    def add_canonical_control(
        self,
        principal: Principal,
        version_id: UUID,
        identifier: str,
        title: str,
        description: str,
        category: str,
        guidance: str | None,
        sort_order: int,
        request_id: str,
    ) -> CanonicalControl:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can mutate canonical controls")
        if not principal.mfa_verified:
            raise PermissionError(
                "multi-factor authentication required to mutate canonical controls"
            )

        version = self.session.get(FrameworkVersion, version_id)
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if version.release_state != ReleaseState.DRAFT:
            raise ImmutableCanonicalVersionError(
                f"cannot add controls to version in {version.release_state} state"
            )

        self._invalidate_version_approvals_on_edit(version, principal, request_id)

        control = CanonicalControl(
            framework_version_id=version_id,
            identifier=identifier.strip(),
            title=title.strip(),
            description=description.strip(),
            category=category.strip(),
            guidance=guidance.strip() if guidance else None,
            sort_order=sort_order,
        )
        self.session.add(control)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="canonical_control.created",
            resource_type="canonical_control",
            resource_id=str(control.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "version_id": str(version.id),
                "control_id": str(control.id),
                "control_identifier": control.identifier,
            },
            occurred_at=datetime.now(UTC),
        )
        return control

    def update_canonical_control(
        self,
        principal: Principal,
        control_id: UUID,
        title: str,
        description: str,
        category: str,
        guidance: str | None,
        sort_order: int,
        request_id: str,
    ) -> CanonicalControl:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can mutate canonical controls")
        if not principal.mfa_verified:
            raise PermissionError(
                "multi-factor authentication required to mutate canonical controls"
            )

        control = self.session.get(CanonicalControl, control_id)
        if not control:
            raise CanonicalControlNotFoundError(f"canonical control {control_id} not found")

        version = self.session.get(FrameworkVersion, control.framework_version_id)
        if not version or version.release_state != ReleaseState.DRAFT:
            raise ImmutableCanonicalVersionError(
                f"cannot update controls of version in {version.release_state if version else 'unknown'} state"
            )

        self._invalidate_version_approvals_on_edit(version, principal, request_id)

        control.title = title.strip()
        control.description = description.strip()
        control.category = category.strip()
        control.guidance = guidance.strip() if guidance else None
        control.sort_order = sort_order
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="canonical_control.updated",
            resource_type="canonical_control",
            resource_id=str(control.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "version_id": str(version.id),
                "control_id": str(control.id),
                "control_identifier": control.identifier,
            },
            occurred_at=datetime.now(UTC),
        )
        return control

    def delete_canonical_control(
        self, principal: Principal, control_id: UUID, request_id: str
    ) -> None:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can delete canonical controls")
        if not principal.mfa_verified:
            raise PermissionError(
                "multi-factor authentication required to delete canonical controls"
            )

        control = self.session.get(CanonicalControl, control_id)
        if not control:
            raise CanonicalControlNotFoundError(f"canonical control {control_id} not found")

        version = self.session.get(FrameworkVersion, control.framework_version_id)
        if not version or version.release_state != ReleaseState.DRAFT:
            raise ImmutableCanonicalVersionError(
                f"cannot delete controls from version in {version.release_state if version else 'unknown'} state"
            )

        self._invalidate_version_approvals_on_edit(version, principal, request_id)

        ident = control.identifier
        version_id = control.framework_version_id
        self.session.delete(control)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="canonical_control.deleted",
            resource_type="canonical_control",
            resource_id=str(control_id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "version_id": str(version_id),
                "control_id": str(control_id),
                "control_identifier": ident,
            },
            occurred_at=datetime.now(UTC),
        )

    # -------------------------------------------------------------------------
    # Traceable Source Requirements, Evidence Specs & Coverage Ledger
    # -------------------------------------------------------------------------

    def add_source_requirement(
        self,
        principal: Principal,
        version_id: UUID,
        source_reference: str,
        title: str,
        source_text: str,
        source_authority: str,
        edition_or_amendment: str,
        content_rights: str,
        request_id: str,
        requirement_type: SourceRequirementType = SourceRequirementType.CLAUSE,
        source_url: str | None = None,
        retrieval_date: datetime | None = None,
        language: str = "en",
        effective_date: str | None = None,
        permitted_use: str | None = None,
        conformly_guidance: str | None = None,
        suggested_operating_targets: dict[str, Any] | None = None,
        assessment_procedure: str | None = None,
        default_owner_role: str | None = None,
        review_cadence: str | None = None,
        applicability_conditions: dict[str, Any] | None = None,
        reporting_limitations: str | None = None,
        sort_order: int = 0,
    ) -> SourceRequirement:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can mutate source requirements")
        if not principal.mfa_verified:
            raise PermissionError(
                "multi-factor authentication required to mutate source requirements"
            )

        version = self.session.get(FrameworkVersion, version_id)
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if version.release_state != ReleaseState.DRAFT:
            raise ImmutableCanonicalVersionError(
                f"cannot add source requirements to version in {version.release_state} state"
            )

        self._invalidate_version_approvals_on_edit(version, principal, request_id)

        req = SourceRequirement(
            framework_version_id=version_id,
            source_reference=source_reference.strip(),
            title=title.strip(),
            requirement_type=requirement_type,
            source_authority=source_authority.strip(),
            source_url=source_url.strip() if source_url else None,
            retrieval_date=retrieval_date,
            edition_or_amendment=edition_or_amendment.strip(),
            language=language.strip(),
            effective_date=effective_date.strip() if effective_date else None,
            content_rights=content_rights.strip(),
            permitted_use=permitted_use.strip() if permitted_use else None,
            source_text=source_text.strip(),
            conformly_guidance=conformly_guidance.strip() if conformly_guidance else None,
            suggested_operating_targets=suggested_operating_targets,
            assessment_procedure=assessment_procedure.strip() if assessment_procedure else None,
            default_owner_role=default_owner_role.strip() if default_owner_role else None,
            review_cadence=review_cadence.strip() if review_cadence else None,
            applicability_conditions=applicability_conditions,
            reporting_limitations=reporting_limitations.strip() if reporting_limitations else None,
            sort_order=sort_order,
        )
        self.session.add(req)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="source_requirement.created",
            resource_type="source_requirement",
            resource_id=str(req.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "version_id": str(version.id),
                "source_requirement_id": str(req.id),
                "source_reference": req.source_reference,
                "requirement_type": str(req.requirement_type),
            },
            occurred_at=datetime.now(UTC),
        )
        return req

    def add_requirement_control_mapping(
        self,
        principal: Principal,
        version_id: UUID,
        source_requirement_id: UUID,
        canonical_control_id: UUID,
        mapping_type: MappingType,
        request_id: str,
        rationale: str | None = None,
    ) -> RequirementControlMapping:
        if not principal.is_platform_admin:
            raise PermissionError(
                "only platform administrators can mutate requirement control mappings"
            )
        if not principal.mfa_verified:
            raise PermissionError("multi-factor authentication required to mutate mappings")

        version = self.session.get(FrameworkVersion, version_id)
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if version.release_state != ReleaseState.DRAFT:
            raise ImmutableCanonicalVersionError(
                f"cannot add mappings to version in {version.release_state} state"
            )

        source_req = self.session.get(SourceRequirement, source_requirement_id)
        if not source_req or source_req.framework_version_id != version_id:
            raise SourceRequirementNotFoundError(
                f"source requirement {source_requirement_id} not found in version {version_id}"
            )

        control = self.session.get(CanonicalControl, canonical_control_id)
        if not control or control.framework_version_id != version_id:
            raise CanonicalControlNotFoundError(
                f"canonical control {canonical_control_id} not found in version {version_id}"
            )

        self._invalidate_version_approvals_on_edit(version, principal, request_id)

        mapping = RequirementControlMapping(
            framework_version_id=version_id,
            source_requirement_id=source_requirement_id,
            canonical_control_id=canonical_control_id,
            mapping_type=mapping_type,
            rationale=rationale.strip() if rationale else None,
        )
        self.session.add(mapping)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="requirement_control_mapping.created",
            resource_type="requirement_control_mapping",
            resource_id=str(mapping.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "version_id": str(version.id),
                "source_requirement_id": str(source_requirement_id),
                "canonical_control_id": str(canonical_control_id),
                "mapping_type": str(mapping_type),
            },
            occurred_at=datetime.now(UTC),
        )
        return mapping

    def add_evidence_specification(
        self,
        principal: Principal,
        version_id: UUID,
        identifier: str,
        title: str,
        description: str,
        evidence_type: str,
        request_id: str,
        canonical_control_id: UUID | None = None,
        source_requirement_id: UUID | None = None,
        original_file_required: bool = False,
        observation_period_days: int | None = None,
        validity_period_days: int | None = None,
        review_cadence_days: int | None = None,
        confidentiality_level: str = "Internal",
        suggested_storage_format: str | None = None,
    ) -> EvidenceSpecification:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can mutate evidence specifications")
        if not principal.mfa_verified:
            raise PermissionError(
                "multi-factor authentication required to mutate evidence specifications"
            )

        version = self.session.get(FrameworkVersion, version_id)
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if version.release_state != ReleaseState.DRAFT:
            raise ImmutableCanonicalVersionError(
                f"cannot add evidence specifications to version in {version.release_state} state"
            )

        if canonical_control_id is not None:
            control = self.session.get(CanonicalControl, canonical_control_id)
            if not control or control.framework_version_id != version_id:
                raise CanonicalControlNotFoundError(
                    f"canonical control {canonical_control_id} not found in version {version_id}"
                )

        if source_requirement_id is not None:
            source_req = self.session.get(SourceRequirement, source_requirement_id)
            if not source_req or source_req.framework_version_id != version_id:
                raise SourceRequirementNotFoundError(
                    f"source requirement {source_requirement_id} not found in version {version_id}"
                )

        self._invalidate_version_approvals_on_edit(version, principal, request_id)

        spec = EvidenceSpecification(
            framework_version_id=version_id,
            canonical_control_id=canonical_control_id,
            source_requirement_id=source_requirement_id,
            identifier=identifier.strip(),
            title=title.strip(),
            description=description.strip(),
            evidence_type=evidence_type.strip(),
            original_file_required=original_file_required,
            observation_period_days=observation_period_days,
            validity_period_days=validity_period_days,
            review_cadence_days=review_cadence_days,
            confidentiality_level=confidentiality_level.strip(),
            suggested_storage_format=suggested_storage_format.strip()
            if suggested_storage_format
            else None,
        )
        self.session.add(spec)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="evidence_specification.created",
            resource_type="evidence_specification",
            resource_id=str(spec.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "version_id": str(version.id),
                "evidence_specification_id": str(spec.id),
            },
            occurred_at=datetime.now(UTC),
        )
        return spec

    def set_coverage_ledger_entry(
        self,
        principal: Principal,
        version_id: UUID,
        source_requirement_id: UUID,
        disposition: CoverageDisposition,
        rationale: str,
        request_id: str,
    ) -> CoverageLedgerEntry:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can mutate coverage ledger entries")
        if not principal.mfa_verified:
            raise PermissionError("multi-factor authentication required to mutate coverage ledger")

        version = self.session.get(FrameworkVersion, version_id)
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if version.release_state != ReleaseState.DRAFT:
            raise ImmutableCanonicalVersionError(
                f"cannot modify coverage ledger for version in {version.release_state} state"
            )

        source_req = self.session.get(SourceRequirement, source_requirement_id)
        if not source_req or source_req.framework_version_id != version_id:
            raise SourceRequirementNotFoundError(
                f"source requirement {source_requirement_id} not found in version {version_id}"
            )

        clean_rationale = rationale.strip()
        if disposition == CoverageDisposition.IMPLEMENTED:
            mappings = (
                self.session.execute(
                    select(RequirementControlMapping).where(
                        RequirementControlMapping.source_requirement_id == source_requirement_id,
                        RequirementControlMapping.mapping_type.in_(
                            [MappingType.SATISFIES, MappingType.PARTIALLY_SATISFIES]
                        ),
                    )
                )
                .scalars()
                .all()
            )
            if not mappings:
                raise InvalidCoverageMappingError(
                    f"Requirement {source_req.source_reference} cannot be marked IMPLEMENTED with 0 mapped satisfying controls"
                )
        else:
            if len(clean_rationale) < 10:
                raise CoverageLedgerError(
                    f"Disposition {disposition} requires substantive source-backed rationale (minimum 10 characters)"
                )

        self._invalidate_version_approvals_on_edit(version, principal, request_id)

        existing = self.session.execute(
            select(CoverageLedgerEntry).where(
                CoverageLedgerEntry.framework_version_id == version_id,
                CoverageLedgerEntry.source_requirement_id == source_requirement_id,
            )
        ).scalar_one_or_none()

        if existing:
            existing.disposition = disposition
            existing.rationale = clean_rationale
            existing.reviewed_by_user_id = principal.user_id
            existing.reviewed_at = datetime.now(UTC)
            entry = existing
        else:
            entry = CoverageLedgerEntry(
                framework_version_id=version_id,
                source_requirement_id=source_requirement_id,
                disposition=disposition,
                rationale=clean_rationale,
                reviewed_by_user_id=principal.user_id,
                reviewed_at=datetime.now(UTC),
            )
            self.session.add(entry)

        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="coverage_ledger_entry.set",
            resource_type="coverage_ledger_entry",
            resource_id=str(entry.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "version_id": str(version.id),
                "source_requirement_id": str(source_requirement_id),
                "disposition": str(disposition),
            },
            occurred_at=datetime.now(UTC),
        )
        return entry

    def validate_coverage_ledger(self, version_id: UUID) -> CoverageLedgerValidationReport:
        version = self.session.get(
            FrameworkVersion,
            version_id,
            options=[
                selectinload(FrameworkVersion.source_requirements),
                selectinload(FrameworkVersion.coverage_ledger_entries),
                selectinload(FrameworkVersion.requirement_control_mappings),
                selectinload(FrameworkVersion.controls),
            ],
        )
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")

        self._refresh_version_content(version)

        reqs_by_id = {r.id: r for r in version.source_requirements}
        ledger_by_req_id = {e.source_requirement_id: e for e in version.coverage_ledger_entries}

        unaccounted_refs: list[str] = []
        for req_id, req in reqs_by_id.items():
            if req_id not in ledger_by_req_id:
                unaccounted_refs.append(req.source_reference)

        blocked_refs: list[str] = []
        counts: dict[str, int] = {
            CoverageDisposition.IMPLEMENTED: 0,
            CoverageDisposition.NOT_CUSTOMER_OBLIGATION: 0,
            CoverageDisposition.PROFILE_EXCLUSION: 0,
            CoverageDisposition.BLOCKED: 0,
        }

        control_ids = {c.id for c in version.controls}
        for entry in version.coverage_ledger_entries:
            counts[entry.disposition] = counts.get(entry.disposition, 0) + 1
            if entry.disposition == CoverageDisposition.BLOCKED:
                source_req = reqs_by_id.get(entry.source_requirement_id)
                blocked_refs.append(
                    source_req.source_reference if source_req else str(entry.source_requirement_id)
                )
            elif entry.disposition == CoverageDisposition.IMPLEMENTED:
                maps = [
                    m
                    for m in version.requirement_control_mappings
                    if m.source_requirement_id == entry.source_requirement_id
                    and m.mapping_type in (MappingType.SATISFIES, MappingType.PARTIALLY_SATISFIES)
                    and m.canonical_control_id in control_ids
                ]
                if not maps:
                    source_req = reqs_by_id.get(entry.source_requirement_id)
                    ref = (
                        source_req.source_reference
                        if source_req
                        else str(entry.source_requirement_id)
                    )
                    raise InvalidCoverageMappingError(
                        f"Requirement {ref} marked IMPLEMENTED but has no valid mapped controls in version"
                    )

        for m in version.requirement_control_mappings:
            if m.source_requirement_id not in reqs_by_id:
                raise InvalidCoverageMappingError(
                    f"Orphan mapping references unknown requirement {m.source_requirement_id}"
                )
            if m.canonical_control_id not in control_ids:
                raise InvalidCoverageMappingError(
                    f"Orphan mapping references unknown control {m.canonical_control_id}"
                )

        is_complete = len(unaccounted_refs) == 0 and len(blocked_refs) == 0

        return CoverageLedgerValidationReport(
            version_id=version_id,
            total_requirements=len(version.source_requirements),
            implemented_count=counts[CoverageDisposition.IMPLEMENTED],
            not_customer_obligation_count=counts[CoverageDisposition.NOT_CUSTOMER_OBLIGATION],
            profile_exclusion_count=counts[CoverageDisposition.PROFILE_EXCLUSION],
            blocked_count=counts[CoverageDisposition.BLOCKED],
            is_complete=is_complete,
            unaccounted_references=sorted(unaccounted_refs),
            blocked_references=sorted(blocked_refs),
            disposition_summary=counts,
        )

    def get_source_requirements(
        self, version_id: UUID, is_platform_admin: bool = False
    ) -> list[SourceRequirement]:
        self.get_version(version_id, is_platform_admin=is_platform_admin)
        stmt = (
            select(SourceRequirement)
            .where(SourceRequirement.framework_version_id == version_id)
            .order_by(SourceRequirement.sort_order, SourceRequirement.source_reference)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_requirement_control_mappings(
        self, version_id: UUID, is_platform_admin: bool = False
    ) -> list[RequirementControlMapping]:
        self.get_version(version_id, is_platform_admin=is_platform_admin)
        stmt = select(RequirementControlMapping).where(
            RequirementControlMapping.framework_version_id == version_id
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_evidence_specifications(
        self, version_id: UUID, is_platform_admin: bool = False
    ) -> list[EvidenceSpecification]:
        self.get_version(version_id, is_platform_admin=is_platform_admin)
        stmt = (
            select(EvidenceSpecification)
            .where(EvidenceSpecification.framework_version_id == version_id)
            .order_by(EvidenceSpecification.identifier)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_coverage_ledger(
        self, version_id: UUID, is_platform_admin: bool = False
    ) -> list[CoverageLedgerEntry]:
        self.get_version(version_id, is_platform_admin=is_platform_admin)
        stmt = select(CoverageLedgerEntry).where(
            CoverageLedgerEntry.framework_version_id == version_id
        )
        return list(self.session.execute(stmt).scalars().all())

    def _refresh_version_content(self, version: FrameworkVersion) -> None:
        self.session.refresh(
            version,
            [
                "controls",
                "source_requirements",
                "coverage_ledger_entries",
                "requirement_control_mappings",
                "evidence_specifications",
            ],
        )

    def submit_version_for_review(
        self, principal: Principal, version_id: UUID, request_id: str
    ) -> FrameworkVersion:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can submit versions for review")
        if not principal.mfa_verified:
            raise PermissionError(
                "multi-factor authentication required to submit versions for review"
            )

        version = self.session.get(
            FrameworkVersion, version_id, options=[selectinload(FrameworkVersion.controls)]
        )
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if version.release_state != ReleaseState.DRAFT:
            raise InvalidStateTransitionError(
                f"cannot submit version in state {version.release_state} for review"
            )
        self._refresh_version_content(version)
        if len(version.controls) == 0:
            raise InvalidStateTransitionError(
                "cannot submit framework version without any canonical controls"
            )

        content_digest = compute_version_content_digest(version)
        version.release_state = ReleaseState.IN_REVIEW
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="canonical_framework_version.review_requested",
            resource_type="framework_version",
            resource_id=str(version.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "framework_id": str(version.framework_id),
                "version_id": str(version.id),
                "version_string": version.version,
                "release_state": version.release_state,
                "content_digest": content_digest,
            },
            occurred_at=datetime.now(UTC),
        )
        return version

    def return_version_to_draft(
        self,
        principal: Principal,
        version_id: UUID,
        reason: str,
        request_id: str,
    ) -> FrameworkVersion:
        """Return an in-review or approved framework version to draft state for content revisions.

        This invalidates any existing legal review or second-person approval and allows
        content mutations in draft state again.
        """
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can return versions to draft")
        if not principal.mfa_verified:
            raise PermissionError(
                "multi-factor authentication required to return versions to draft"
            )

        version = self.session.get(FrameworkVersion, version_id)
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")

        if version.release_state not in (ReleaseState.IN_REVIEW, ReleaseState.APPROVED):
            raise InvalidStateTransitionError(
                f"cannot return version in {version.release_state} state to draft (must be in_review or approved)"
            )

        clean_reason = reason.strip() if reason else "Content revision requested"
        if len(clean_reason) < 3:
            raise ValueError("reason for returning version to draft must be at least 3 characters")

        version.release_state = ReleaseState.DRAFT
        version.legal_reviewed_by_user_id = None
        version.legal_reviewed_at = None
        version.legal_review_notes = None
        version.approved_by_user_id = None
        version.approved_at = None
        version.approval_notes = None
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="canonical_framework_version.returned_to_draft",
            resource_type="framework_version",
            resource_id=str(version.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "framework_id": str(version.framework_id),
                "version_id": str(version.id),
                "version_string": version.version,
                "reason": clean_reason,
            },
            occurred_at=datetime.now(UTC),
        )
        return version

    def record_legal_review(
        self,
        principal: Principal,
        version_id: UUID,
        notes: str,
        request_id: str,
        content_digest: str | None = None,
        evidence_ref: str | None = None,
    ) -> FrameworkVersion:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can record legal reviews")
        if not principal.mfa_verified:
            raise PermissionError("multi-factor authentication required to record legal reviews")

        version = self.session.get(
            FrameworkVersion, version_id, options=[selectinload(FrameworkVersion.controls)]
        )
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if version.release_state != ReleaseState.IN_REVIEW:
            raise InvalidStateTransitionError(
                f"cannot record legal review for version in {version.release_state} state"
            )

        self._refresh_version_content(version)
        actual_digest = compute_version_content_digest(version)
        if content_digest is not None and content_digest != actual_digest:
            raise StaleReviewError("content has been modified since legal review was prepared")

        version.legal_reviewed_by_user_id = principal.user_id
        version.legal_review_notes = notes.strip()
        version.legal_reviewed_at = datetime.now(UTC)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="canonical_framework_version.reviewed",
            resource_type="framework_version",
            resource_id=str(version.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "framework_id": str(version.framework_id),
                "version_id": str(version.id),
                "version_string": version.version,
                "notes": notes.strip()[:100],
                "content_digest": actual_digest,
                "evidence_ref": evidence_ref[:100] if evidence_ref else None,
            },
            occurred_at=datetime.now(UTC),
        )
        return version

    def approve_version(
        self,
        principal: Principal,
        version_id: UUID,
        notes: str | None,
        request_id: str,
        content_digest: str | None = None,
    ) -> FrameworkVersion:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can approve framework versions")
        if not principal.mfa_verified:
            raise PermissionError(
                "multi-factor authentication required to approve framework versions"
            )

        version = self.session.get(
            FrameworkVersion, version_id, options=[selectinload(FrameworkVersion.controls)]
        )
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if version.release_state != ReleaseState.IN_REVIEW:
            raise InvalidStateTransitionError(
                f"cannot approve version in {version.release_state} state"
            )
        if version.legal_reviewed_by_user_id is None:
            raise InvalidStateTransitionError(
                "legal and compliance review must be completed prior to final approval"
            )

        # Mandatory independent second-person approval rules:
        if principal.user_id == version.created_by_user_id:
            raise IndependentApprovalRequiredError(
                "version creator cannot perform independent second-person approval"
            )
        if principal.user_id == version.legal_reviewed_by_user_id:
            raise IndependentApprovalRequiredError(
                "legal reviewer cannot perform final second-person approval"
            )

        self._refresh_version_content(version)
        actual_digest = compute_version_content_digest(version)
        if content_digest is not None and content_digest != actual_digest:
            raise StaleReviewError("content has been modified since approval was prepared")

        version.approved_by_user_id = principal.user_id
        version.approval_notes = notes.strip() if notes else None
        version.approved_at = datetime.now(UTC)
        version.release_state = ReleaseState.APPROVED
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="canonical_framework_version.approved",
            resource_type="framework_version",
            resource_id=str(version.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "framework_id": str(version.framework_id),
                "version_id": str(version.id),
                "version_string": version.version,
                "release_state": version.release_state,
                "content_digest": actual_digest,
            },
            occurred_at=datetime.now(UTC),
        )
        return version

    def release_version(
        self,
        principal: Principal,
        version_id: UUID,
        request_id: str,
        content_digest: str | None = None,
    ) -> FrameworkVersion:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can release framework versions")
        if not principal.mfa_verified:
            raise PermissionError(
                "multi-factor authentication required to release framework versions"
            )

        version = self.session.get(
            FrameworkVersion, version_id, options=[selectinload(FrameworkVersion.controls)]
        )
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if version.release_state != ReleaseState.APPROVED:
            raise UnapprovedReleaseError(
                f"cannot release unapproved version (current state: {version.release_state})"
            )

        self._refresh_version_content(version)
        if len(version.source_requirements) > 0:
            report = self.validate_coverage_ledger(version_id)
            if not report.is_complete:
                raise ReleaseBlockedError(
                    f"cannot release framework version with incomplete coverage ledger: "
                    f"unaccounted={len(report.unaccounted_references)}, blocked={report.blocked_count}"
                )

        actual_digest = compute_version_content_digest(version)
        if content_digest is not None and content_digest != actual_digest:
            raise StaleReviewError("content has been modified since approval was granted")

        version.released_at = datetime.now(UTC)
        version.release_state = ReleaseState.RELEASED
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="canonical_framework_version.released",
            resource_type="framework_version",
            resource_id=str(version.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "framework_id": str(version.framework_id),
                "version_id": str(version.id),
                "version_string": version.version,
                "release_state": version.release_state,
                "content_digest": actual_digest,
            },
            occurred_at=datetime.now(UTC),
        )
        return version

    def retire_version(
        self,
        principal: Principal,
        version_id: UUID,
        request_id: str,
        reason: str = "Retired by platform administration",
        superseding_version_id: UUID | None = None,
    ) -> FrameworkVersion:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can retire framework versions")
        if not principal.mfa_verified:
            raise PermissionError(
                "multi-factor authentication required to retire framework versions"
            )

        version = self.session.get(FrameworkVersion, version_id)
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if version.release_state not in (ReleaseState.RELEASED, ReleaseState.APPROVED):
            raise InvalidStateTransitionError("only released or approved versions can be retired")

        version.retired_at = datetime.now(UTC)
        version.release_state = ReleaseState.RETIRED
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=None,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="canonical_framework_version.retired",
            resource_type="framework_version",
            resource_id=str(version.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "framework_id": str(version.framework_id),
                "version_id": str(version.id),
                "version_string": version.version,
                "release_state": version.release_state,
                "reason": reason[:200],
                "superseding_version_id": str(superseding_version_id)
                if superseding_version_id
                else None,
            },
            occurred_at=datetime.now(UTC),
        )
        return version

    def quarantine_version(
        self, principal: Principal, version_id: UUID, reason: str, request_id: str
    ) -> FrameworkVersion:
        """Quarantine a released version due to audit, legal, or content discrepancies."""
        return self.retire_version(
            principal=principal,
            version_id=version_id,
            request_id=request_id,
            reason=f"QUARANTINED: {reason}",
        )

    def list_adoptions_for_retired_version(
        self, principal: Principal, version_id: UUID
    ) -> list[TenantFrameworkAdoption]:
        """List active tenant adoptions under a retired/quarantined version for human disposition."""
        if not principal.is_platform_admin:
            raise PermissionError(
                "only platform administrators can inspect retired version adoptions"
            )
        stmt = select(TenantFrameworkAdoption).where(
            TenantFrameworkAdoption.framework_version_id == version_id,
            TenantFrameworkAdoption.status == AdoptionStatus.ACTIVE,
        )
        return list(self.session.scalars(stmt).all())

    def list_frameworks(self, is_platform_admin: bool = False) -> list[Framework]:
        stmt = select(Framework).order_by(Framework.name)
        return list(self.session.scalars(stmt).all())

    def get_framework(self, framework_id: UUID, is_platform_admin: bool = False) -> Framework:
        framework = self.session.get(
            Framework, framework_id, options=[selectinload(Framework.versions)]
        )
        if not framework:
            raise FrameworkNotFoundError(f"framework {framework_id} not found")
        return framework

    def get_version(self, version_id: UUID, is_platform_admin: bool = False) -> FrameworkVersion:
        version = self.session.get(
            FrameworkVersion,
            version_id,
            options=[
                selectinload(FrameworkVersion.controls),
                selectinload(FrameworkVersion.framework),
            ],
        )
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if not is_platform_admin and version.release_state not in (
            ReleaseState.RELEASED,
            ReleaseState.RETIRED,
        ):
            raise FrameworkVersionNotFoundError(
                f"released framework version {version_id} not found"
            )
        return version

    def compare_versions(
        self,
        framework_id: UUID,
        source_version_id: UUID,
        target_version_id: UUID,
        *,
        is_platform_admin: bool = False,
    ) -> ImpactAnalysisReport:
        source = self.get_version(source_version_id, is_platform_admin=is_platform_admin)
        target = self.get_version(target_version_id, is_platform_admin=is_platform_admin)

        if source.framework_id != framework_id or target.framework_id != framework_id:
            raise ValueError("both versions must belong to the specified framework")

        return compute_framework_impact(source, target)

    # -------------------------------------------------------------------------
    # Tenant Layer (Tenant-Scoped with Row-Level Security)
    # -------------------------------------------------------------------------

    def list_tenant_adoptions(self, tenant_context: TenantContext) -> list[TenantFrameworkAdoption]:
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=tenant_context.user_id,
            tenant_verified=True,
        )
        stmt = (
            select(TenantFrameworkAdoption)
            .where(TenantFrameworkAdoption.tenant_id == tenant_context.tenant_id)
            .order_by(TenantFrameworkAdoption.adopted_at.desc())
        )
        return list(self.session.scalars(stmt).all())

    def get_tenant_impact_analysis(
        self, tenant_context: TenantContext, framework_id: UUID, target_version_id: UUID
    ) -> ImpactAnalysisReport:
        authorize(
            Principal(user_id=tenant_context.user_id), tenant_context, Capability.FRAMEWORK_READ
        )
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=tenant_context.user_id,
            tenant_verified=True,
        )

        target = self.get_version(target_version_id, is_platform_admin=False)
        if target.framework_id != framework_id:
            raise ValueError("target version does not belong to framework")

        # Find current active adoption
        stmt = select(TenantFrameworkAdoption).where(
            TenantFrameworkAdoption.tenant_id == tenant_context.tenant_id,
            TenantFrameworkAdoption.framework_id == framework_id,
            TenantFrameworkAdoption.status == AdoptionStatus.ACTIVE,
        )
        active_adoption = self.session.scalars(stmt).first()

        if not active_adoption:
            # First-time adoption: compare against itself or baseline
            return compute_framework_impact(target, target)

        source = self.get_version(active_adoption.framework_version_id, is_platform_admin=True)

        # Fetch tenant overlays for this adoption
        overlay_stmt = select(TenantControlOverlay).where(
            TenantControlOverlay.tenant_id == tenant_context.tenant_id,
            TenantControlOverlay.adoption_id == active_adoption.id,
        )
        overlays = list(self.session.scalars(overlay_stmt).all())

        # Fetch tenant mappings
        mapping_stmt = select(ControlMapping).where(
            ControlMapping.tenant_id == tenant_context.tenant_id
        )
        mappings = list(self.session.scalars(mapping_stmt).all())

        return compute_framework_impact(source, target, overlays, mappings)

    def adopt_framework_version(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        framework_version_id: UUID,
        acknowledge_impact: bool,
        request_id: str,
    ) -> TenantFrameworkAdoption:
        authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )

        version = self.get_version(framework_version_id, is_platform_admin=False)
        if version.release_state != ReleaseState.RELEASED:
            raise ValueError(f"cannot adopt version in non-released state: {version.release_state}")

        framework = self.session.get(Framework, version.framework_id)
        if framework is not None:
            from conformly.entitlements.service import (
                FrameworkPackNotEntitledError,
                is_framework_allowed,
            )

            if not is_framework_allowed(self.session, tenant_context.tenant_id, framework.slug):
                raise FrameworkPackNotEntitledError(
                    f"Framework '{framework.slug}' is not included in tenant entitlement framework packs"
                )

        # Serialize first adoption as well as replacements on a stable parent row.
        from conformly.identity.models import Tenant

        self.session.execute(
            select(Tenant.id).where(Tenant.id == tenant_context.tenant_id).with_for_update()
        ).scalar_one()

        # Check existing active adoption
        stmt = select(TenantFrameworkAdoption).where(
            TenantFrameworkAdoption.tenant_id == tenant_context.tenant_id,
            TenantFrameworkAdoption.framework_id == version.framework_id,
            TenantFrameworkAdoption.status == AdoptionStatus.ACTIVE,
        )
        active_adoption = self.session.scalars(
            stmt.execution_options(populate_existing=True)
        ).first()

        impact_summary: str | None = None
        old_overlays: list[TenantControlOverlay] = []

        if active_adoption:
            if active_adoption.framework_version_id == version.id:
                raise ValueError("this framework version is already actively adopted")

            # Run deterministic impact analysis and record summary
            source_version = self.get_version(
                active_adoption.framework_version_id, is_platform_admin=True
            )
            old_overlays_stmt = select(TenantControlOverlay).where(
                TenantControlOverlay.tenant_id == tenant_context.tenant_id,
                TenantControlOverlay.adoption_id == active_adoption.id,
            )
            old_overlays = list(self.session.scalars(old_overlays_stmt).all())
            report = compute_framework_impact(source_version, version, old_overlays)

            impact_summary = json.dumps(
                {
                    "source_version": source_version.version,
                    "target_version": version.version,
                    "overall_impact": report.overall_impact_level,
                    "added_count": len(report.added_controls),
                    "removed_count": len(report.removed_controls),
                    "modified_count": len(report.modified_controls),
                }
            )

            # Mark existing active adoption as superseded
            active_adoption.status = AdoptionStatus.SUPERSEDED
            self.session.flush()

        now = datetime.now(UTC)
        new_adoption = TenantFrameworkAdoption(
            tenant_id=tenant_context.tenant_id,
            framework_id=version.framework_id,
            framework_version_id=version.id,
            status=AdoptionStatus.ACTIVE,
            adopted_at=now,
            adopted_by_user_id=principal.user_id,
            impact_analysis_acknowledged_at=now if acknowledge_impact else None,
            impact_summary_json=impact_summary,
        )
        self.session.add(new_adoption)
        self.session.flush()

        # Migrate compatible overlays to the new adoption if applicable
        if old_overlays:
            old_control_map = {c.id: c.identifier for c in source_version.controls}
            new_control_map = {c.identifier: c.id for c in version.controls}

            for old_overlay in old_overlays:
                ident = old_control_map.get(old_overlay.canonical_control_id)
                if ident and ident in new_control_map:
                    new_control_id = new_control_map[ident]
                    migrated_overlay = TenantControlOverlay(
                        tenant_id=tenant_context.tenant_id,
                        adoption_id=new_adoption.id,
                        canonical_control_id=new_control_id,
                        applicability=old_overlay.applicability,
                        justification=old_overlay.justification,
                        internal_notes=old_overlay.internal_notes,
                        custom_guidance=old_overlay.custom_guidance,
                        created_by_user_id=principal.user_id,
                    )
                    self.session.add(migrated_overlay)
            self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="framework.adopted",
            resource_type="tenant_framework_adoption",
            resource_id=str(new_adoption.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "framework_id": str(version.framework_id),
                "version_id": str(version.id),
                "version_string": version.version,
                "adoption_id": str(new_adoption.id),
            },
            occurred_at=now,
        )
        return new_adoption

    # -------------------------------------------------------------------------
    # Tenant Overlays
    # -------------------------------------------------------------------------

    def manage_overlay(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        adoption_id: UUID,
        canonical_control_id: UUID,
        applicability: OverlayApplicability,
        justification: str | None,
        internal_notes: str | None,
        custom_guidance: str | None,
        request_id: str,
    ) -> TenantControlOverlay:
        authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )

        # Validate adoption belongs to tenant
        adoption = self.session.get(TenantFrameworkAdoption, adoption_id)
        if not adoption or adoption.tenant_id != tenant_context.tenant_id:
            raise AdoptionNotFoundError(f"adoption {adoption_id} not found")

        # Validate canonical control belongs to adopted version
        control = self.session.get(CanonicalControl, canonical_control_id)
        if not control or control.framework_version_id != adoption.framework_version_id:
            raise CanonicalControlNotFoundError(
                "canonical control does not belong to the adopted framework version"
            )

        # Exclusions require substantive auditable justification
        if applicability in (OverlayApplicability.NOT_APPLICABLE, OverlayApplicability.SCOPED_OUT):
            if not justification or len(justification.strip()) < 10:
                raise ValueError(
                    "Exclusion requires an auditable justification of at least 10 characters."
                )

        # Upsert overlay
        stmt = select(TenantControlOverlay).where(
            TenantControlOverlay.tenant_id == tenant_context.tenant_id,
            TenantControlOverlay.adoption_id == adoption_id,
            TenantControlOverlay.canonical_control_id == canonical_control_id,
        )
        overlay = self.session.scalars(stmt).first()

        action = "control_overlay.updated" if overlay else "control_overlay.created"
        if overlay:
            overlay.applicability = applicability
            overlay.justification = justification.strip() if justification else None
            overlay.internal_notes = internal_notes.strip() if internal_notes else None
            overlay.custom_guidance = custom_guidance.strip() if custom_guidance else None
        else:
            overlay = TenantControlOverlay(
                tenant_id=tenant_context.tenant_id,
                adoption_id=adoption_id,
                canonical_control_id=canonical_control_id,
                applicability=applicability,
                justification=justification.strip() if justification else None,
                internal_notes=internal_notes.strip() if internal_notes else None,
                custom_guidance=custom_guidance.strip() if custom_guidance else None,
                created_by_user_id=principal.user_id,
            )
            self.session.add(overlay)

        self.session.flush()

        from conformly.preaudit.service import auto_suspend_active_certificates

        auto_suspend_active_certificates(
            self.session,
            tenant_context.tenant_id,
            framework_adoption_id=adoption_id,
            reason="Control overlay created or updated",
        )

        record_audit_event(
            self.session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action=action,
            resource_type="tenant_control_overlay",
            resource_id=str(overlay.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "adoption_id": str(adoption_id),
                "control_id": str(canonical_control_id),
                "overlay_id": str(overlay.id),
            },
            occurred_at=datetime.now(UTC),
        )
        return overlay

    def list_overlays(
        self, tenant_context: TenantContext, adoption_id: UUID
    ) -> list[TenantControlOverlay]:
        authorize(
            Principal(user_id=tenant_context.user_id), tenant_context, Capability.FRAMEWORK_READ
        )
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=tenant_context.user_id,
            tenant_verified=True,
        )
        stmt = select(TenantControlOverlay).where(
            TenantControlOverlay.tenant_id == tenant_context.tenant_id,
            TenantControlOverlay.adoption_id == adoption_id,
        )
        return list(self.session.scalars(stmt).all())

    def delete_overlay(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        overlay_id: UUID,
        request_id: str,
    ) -> None:
        authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )

        overlay = self.session.get(TenantControlOverlay, overlay_id)
        if not overlay or overlay.tenant_id != tenant_context.tenant_id:
            raise ControlOverlayNotFoundError(f"overlay {overlay_id} not found")

        adoption_id = overlay.adoption_id
        self.session.delete(overlay)
        self.session.flush()

        from conformly.preaudit.service import auto_suspend_active_certificates

        auto_suspend_active_certificates(
            self.session,
            tenant_context.tenant_id,
            framework_adoption_id=adoption_id,
            reason="Control overlay deleted",
        )

        record_audit_event(
            self.session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="control_overlay.deleted",
            resource_type="tenant_control_overlay",
            resource_id=str(overlay_id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"overlay_id": str(overlay_id)},
            occurred_at=datetime.now(UTC),
        )

    # -------------------------------------------------------------------------
    # Custom Controls
    # -------------------------------------------------------------------------

    def create_custom_control(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        identifier: str,
        title: str,
        description: str,
        category: str,
        guidance: str | None,
        request_id: str,
    ) -> CustomControl:
        authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )

        clean_ident = identifier.strip().upper()
        clean_title = title.strip()
        clean_desc = description.strip()
        clean_cat = category.strip()

        # Check for existing identifier within tenant
        stmt = select(CustomControl).where(
            CustomControl.tenant_id == tenant_context.tenant_id,
            CustomControl.identifier == clean_ident,
        )
        if self.session.scalars(stmt).first():
            raise ValueError(f"custom control identifier {clean_ident} already exists in tenant")

        control = CustomControl(
            tenant_id=tenant_context.tenant_id,
            identifier=clean_ident,
            title=clean_title,
            description=clean_desc,
            category=clean_cat,
            guidance=guidance.strip() if guidance else None,
            status=CustomControlStatus.ACTIVE,
            created_by_user_id=principal.user_id,
        )
        self.session.add(control)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="custom_control.created",
            resource_type="custom_control",
            resource_id=str(control.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "custom_control_id": str(control.id),
                "control_identifier": control.identifier,
            },
            occurred_at=datetime.now(UTC),
        )
        return control

    def list_custom_controls(self, tenant_context: TenantContext) -> list[CustomControl]:
        authorize(
            Principal(user_id=tenant_context.user_id), tenant_context, Capability.FRAMEWORK_READ
        )
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=tenant_context.user_id,
            tenant_verified=True,
        )
        stmt = (
            select(CustomControl)
            .where(CustomControl.tenant_id == tenant_context.tenant_id)
            .order_by(CustomControl.identifier)
        )
        return list(self.session.scalars(stmt).all())

    def update_custom_control(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        control_id: UUID,
        title: str,
        description: str,
        category: str,
        guidance: str | None,
        status: CustomControlStatus,
        request_id: str,
    ) -> CustomControl:
        authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )

        control = self.session.get(CustomControl, control_id)
        if not control or control.tenant_id != tenant_context.tenant_id:
            raise CustomControlNotFoundError(f"custom control {control_id} not found")

        control.title = title.strip()
        control.description = description.strip()
        control.category = category.strip()
        control.guidance = guidance.strip() if guidance else None
        control.status = status
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="custom_control.updated",
            resource_type="custom_control",
            resource_id=str(control.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "custom_control_id": str(control.id),
                "control_identifier": control.identifier,
                "status": control.status,
            },
            occurred_at=datetime.now(UTC),
        )
        return control

    # -------------------------------------------------------------------------
    # Control Mappings
    # -------------------------------------------------------------------------

    def create_control_mapping(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        source_type: ControlEntityType,
        source_control_id: UUID,
        target_type: ControlEntityType,
        target_control_id: UUID,
        mapping_type: MappingType,
        rationale: str | None,
        request_id: str,
    ) -> ControlMapping:
        authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )

        for entity_type, control_id in (
            (source_type, source_control_id),
            (target_type, target_control_id),
        ):
            if entity_type == ControlEntityType.CUSTOM:
                found = self.session.scalar(
                    select(CustomControl.id).where(
                        CustomControl.id == control_id,
                        CustomControl.tenant_id == tenant_context.tenant_id,
                    )
                )
            elif entity_type == ControlEntityType.CANONICAL:
                found = self.session.scalar(
                    select(CanonicalControl.id)
                    .join(
                        FrameworkVersion,
                        FrameworkVersion.id == CanonicalControl.framework_version_id,
                    )
                    .where(
                        CanonicalControl.id == control_id,
                        FrameworkVersion.release_state.in_(
                            [ReleaseState.RELEASED, ReleaseState.RETIRED]
                        ),
                    )
                )
            else:
                found = None
            if found is None:
                raise ValueError("control reference is unavailable in this tenant")

        mapping = ControlMapping(
            tenant_id=tenant_context.tenant_id,
            source_type=source_type,
            source_control_id=source_control_id,
            target_type=target_type,
            target_control_id=target_control_id,
            mapping_type=mapping_type,
            rationale=rationale.strip() if rationale else None,
            created_by_user_id=principal.user_id,
        )
        self.session.add(mapping)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="control_mapping.created",
            resource_type="control_mapping",
            resource_id=str(mapping.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"mapping_id": str(mapping.id)},
            occurred_at=datetime.now(UTC),
        )
        return mapping

    def list_control_mappings(self, tenant_context: TenantContext) -> list[ControlMapping]:
        authorize(
            Principal(user_id=tenant_context.user_id), tenant_context, Capability.FRAMEWORK_READ
        )
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=tenant_context.user_id,
            tenant_verified=True,
        )
        stmt = (
            select(ControlMapping)
            .where(ControlMapping.tenant_id == tenant_context.tenant_id)
            .order_by(ControlMapping.created_at.desc())
        )
        return list(self.session.scalars(stmt).all())

    def delete_control_mapping(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        mapping_id: UUID,
        request_id: str,
    ) -> None:
        authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)
        set_rls_context(
            self.session,
            tenant_id=tenant_context.tenant_id,
            user_id=principal.user_id,
            tenant_verified=True,
        )

        mapping = self.session.get(ControlMapping, mapping_id)
        if not mapping or mapping.tenant_id != tenant_context.tenant_id:
            raise ControlMappingNotFoundError(f"control mapping {mapping_id} not found")

        self.session.delete(mapping)
        self.session.flush()

        record_audit_event(
            self.session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="control_mapping.deleted",
            resource_type="control_mapping",
            resource_id=str(mapping_id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"mapping_id": str(mapping_id)},
            occurred_at=datetime.now(UTC),
        )


def get_framework_service(
    database: Session,
) -> FrameworkService:
    return FrameworkService(session=database)
