import json
from datetime import UTC, datetime
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
    CustomControl,
    CustomControlStatus,
    Framework,
    FrameworkVersion,
    MappingType,
    OverlayApplicability,
    ReleaseState,
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


class AdoptionNotFoundError(FrameworkCatalogError):
    """Raised when a tenant adoption record is not found."""


class ControlOverlayNotFoundError(FrameworkCatalogError):
    """Raised when a tenant control overlay is not found."""


class CustomControlNotFoundError(FrameworkCatalogError):
    """Raised when a custom control is not found."""


class ControlMappingNotFoundError(FrameworkCatalogError):
    """Raised when a control mapping is not found."""


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

        version = self.session.get(FrameworkVersion, version_id)
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if version.release_state != ReleaseState.DRAFT:
            raise ImmutableCanonicalVersionError(
                f"cannot add controls to version in {version.release_state} state"
            )

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

        control = self.session.get(CanonicalControl, control_id)
        if not control:
            raise CanonicalControlNotFoundError(f"canonical control {control_id} not found")

        version = self.session.get(FrameworkVersion, control.framework_version_id)
        if not version or version.release_state != ReleaseState.DRAFT:
            raise ImmutableCanonicalVersionError(
                "cannot update controls of non-draft canonical version"
            )

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

        control = self.session.get(CanonicalControl, control_id)
        if not control:
            raise CanonicalControlNotFoundError(f"canonical control {control_id} not found")

        version = self.session.get(FrameworkVersion, control.framework_version_id)
        if not version or version.release_state != ReleaseState.DRAFT:
            raise ImmutableCanonicalVersionError(
                "cannot delete controls from non-draft canonical version"
            )

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

    def submit_version_for_review(
        self, principal: Principal, version_id: UUID, request_id: str
    ) -> FrameworkVersion:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can submit versions for review")

        version = self.session.get(
            FrameworkVersion, version_id, options=[selectinload(FrameworkVersion.controls)]
        )
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if version.release_state != ReleaseState.DRAFT:
            raise InvalidStateTransitionError(
                f"cannot submit version in state {version.release_state} for review"
            )
        if len(version.controls) == 0:
            raise InvalidStateTransitionError(
                "cannot submit framework version without any canonical controls"
            )

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
            },
            occurred_at=datetime.now(UTC),
        )
        return version

    def record_legal_review(
        self, principal: Principal, version_id: UUID, notes: str, request_id: str
    ) -> FrameworkVersion:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can record legal reviews")

        version = self.session.get(FrameworkVersion, version_id)
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if version.release_state != ReleaseState.IN_REVIEW:
            raise InvalidStateTransitionError(
                f"cannot record legal review for version in {version.release_state} state"
            )

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
            },
            occurred_at=datetime.now(UTC),
        )
        return version

    def approve_version(
        self, principal: Principal, version_id: UUID, notes: str | None, request_id: str
    ) -> FrameworkVersion:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can approve framework versions")

        version = self.session.get(FrameworkVersion, version_id)
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

        # Independent second-person approval rule:
        if principal.user_id == version.created_by_user_id:
            raise IndependentApprovalRequiredError(
                "version creator cannot perform independent second-person approval"
            )

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
            },
            occurred_at=datetime.now(UTC),
        )
        return version

    def release_version(
        self, principal: Principal, version_id: UUID, request_id: str
    ) -> FrameworkVersion:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can release framework versions")

        version = self.session.get(FrameworkVersion, version_id)
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if version.release_state != ReleaseState.APPROVED:
            raise UnapprovedReleaseError(
                f"cannot release unapproved version (current state: {version.release_state})"
            )

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
            },
            occurred_at=datetime.now(UTC),
        )
        return version

    def retire_version(
        self, principal: Principal, version_id: UUID, request_id: str
    ) -> FrameworkVersion:
        if not principal.is_platform_admin:
            raise PermissionError("only platform administrators can retire framework versions")

        version = self.session.get(FrameworkVersion, version_id)
        if not version:
            raise FrameworkVersionNotFoundError(f"framework version {version_id} not found")
        if version.release_state != ReleaseState.RELEASED:
            raise InvalidStateTransitionError("only released versions can be retired")

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
            },
            occurred_at=datetime.now(UTC),
        )
        return version

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
            from conformly.entitlements.service import FrameworkPackNotEntitledError, is_framework_allowed

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
