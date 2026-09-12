"""Pre-audit readiness assessment service.

All operations are tenant-scoped, capability-guarded, and audited.
Readiness evaluations are deterministic and reproducible.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize
from conformly.authz.roles import Capability
from conformly.compliance.models import (
    ControlStatusRecord,
    EvidenceControlLink,
    EvidenceItem,
    EvidenceStatus,
    Finding,
    FindingSeverity,
    PolicyControlLink,
    RemediationStatus,
)
from conformly.frameworks.models import (
    CanonicalControl,
    ControlEntityType,
    TenantControlOverlay,
    TenantFrameworkAdoption,
)
from conformly.identity.models import Membership, MembershipStatus
from conformly.preaudit.models import (
    PRE_AUDIT_TRANSITIONS,
    CertificateStatus,
    CheckResult,
    PreAudit,
    PreAuditCertificate,
    PreAuditCheck,
    PreAuditFinding,
    PreAuditManifest,
    PreAuditReport,
    PreAuditScope,
    PreAuditStatus,
)
from conformly.preaudit.rules import (
    CURRENT_RULE_VERSION,
    CheckInput,
    compute_overall_score,
    evaluate_control_readiness,
    get_rule_for_category,
    snapshot_input,
)
from conformly.tenancy.rls import set_rls_context

# ── Exceptions ────────────────────────────────────────────────────────────


class PreAuditError(Exception):
    """Base exception for pre-audit operations."""


class PreAuditNotFoundError(PreAuditError):
    """Raised when a pre-audit is not found."""


class PreAuditFindingNotFoundError(PreAuditError):
    """Raised when a pre-audit finding is not found."""


class InvalidPreAuditTransitionError(PreAuditError):
    """Raised when a state transition is disallowed."""


class PreAuditOptimisticLockError(PreAuditError):
    """Raised when an update conflicts with the current entity version."""


class CertificateIssuanceBlockedError(PreAuditError):
    """Raised when certificate issuance prerequisites are not met."""


class CertificateNotFoundError(PreAuditError):
    """Raised when a certificate is not found."""


class InvalidAdoptionReferenceError(PreAuditError):
    """Raised when the referenced adoption does not belong to this tenant."""


class ReviewerConflictError(PreAuditError):
    """Raised when reviewer is the same as lead."""


# ── Service ───────────────────────────────────────────────────────────────


class PreAuditService:
    """Core domain service for pre-audit readiness assessments."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Helpers ───────────────────────────────────────────────────────────

    def _set_rls(self, principal: Principal, tenant_context: TenantContext) -> None:
        set_rls_context(
            self._session,
            user_id=principal.user_id,
            tenant_id=tenant_context.tenant_id,
            tenant_verified=True,
        )

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
            raise InvalidAdoptionReferenceError("Member unavailable in this tenant")

    def _get_pre_audit(
        self,
        tenant_id: UUID,
        pre_audit_id: UUID,
        *,
        eager: bool = False,
    ) -> PreAudit:
        stmt = select(PreAudit).where(
            PreAudit.id == pre_audit_id,
            PreAudit.tenant_id == tenant_id,
        )
        if eager:
            stmt = stmt.options(
                selectinload(PreAudit.scopes).selectinload(PreAuditScope.checks),
                selectinload(PreAudit.findings),
                selectinload(PreAudit.reports),
                selectinload(PreAudit.manifests),
                selectinload(PreAudit.certificates),
            )
        pa = self._session.scalar(stmt)
        if pa is None:
            raise PreAuditNotFoundError("Pre-audit not found")
        return pa

    def _transition(self, pa: PreAudit, target: PreAuditStatus) -> None:
        allowed = PRE_AUDIT_TRANSITIONS.get(pa.status, frozenset())
        if target not in allowed:
            raise InvalidPreAuditTransitionError(f"Cannot transition from {pa.status} to {target}")
        pa.status = target

    # ── CRUD ──────────────────────────────────────────────────────────────

    def create_pre_audit(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        *,
        title: str,
        description: str = "",
        framework_adoption_id: UUID,
        lead_user_id: UUID,
    ) -> PreAudit:
        authorize(principal, tenant_context, Capability.PREAUDIT_MANAGE)
        self._set_rls(principal, tenant_context)
        self._validate_member(tenant_context, lead_user_id)

        adoption = self._session.scalar(
            select(TenantFrameworkAdoption).where(
                TenantFrameworkAdoption.id == framework_adoption_id,
                TenantFrameworkAdoption.tenant_id == tenant_context.tenant_id,
            )
        )
        if adoption is None:
            raise InvalidAdoptionReferenceError("Framework adoption not found in this tenant")

        pa = PreAudit(
            tenant_id=tenant_context.tenant_id,
            title=title,
            description=description,
            status=PreAuditStatus.PLANNING,
            framework_adoption_id=framework_adoption_id,
            lead_user_id=lead_user_id,
            rule_version=CURRENT_RULE_VERSION,
            version=1,
        )
        self._session.add(pa)
        self._session.flush()

        # Create scope for the adopted framework version
        control_count = (
            self._session.scalar(
                select(func.count(CanonicalControl.id)).where(
                    CanonicalControl.framework_version_id == adoption.framework_version_id,
                )
            )
            or 0
        )

        scope = PreAuditScope(
            tenant_id=tenant_context.tenant_id,
            pre_audit_id=pa.id,
            framework_version_id=adoption.framework_version_id,
            control_count=control_count,
            checked_count=0,
        )
        self._session.add(scope)
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="preaudit.create",
            resource_type="pre_audit",
            resource_id=str(pa.id),
            request_id=f"preaudit:create:{pa.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "pre_audit_id": str(pa.id),
                "rule_version": CURRENT_RULE_VERSION,
                "status": pa.status.value,
            },
        )
        return pa

    def list_pre_audits(
        self,
        principal: Principal,
        tenant_context: TenantContext,
    ) -> list[PreAudit]:
        authorize(principal, tenant_context, Capability.PREAUDIT_READ)
        self._set_rls(principal, tenant_context)
        return list(
            self._session.scalars(
                select(PreAudit)
                .where(PreAudit.tenant_id == tenant_context.tenant_id)
                .order_by(PreAudit.created_at.desc())
            )
        )

    def get_pre_audit(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        pre_audit_id: UUID,
    ) -> PreAudit:
        authorize(principal, tenant_context, Capability.PREAUDIT_READ)
        self._set_rls(principal, tenant_context)
        return self._get_pre_audit(tenant_context.tenant_id, pre_audit_id, eager=True)

    # ── Run deterministic checks ──────────────────────────────────────────

    def run_checks(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        pre_audit_id: UUID,
    ) -> PreAudit:
        """Evaluate all in-scope controls against current compliance state."""
        authorize(principal, tenant_context, Capability.PREAUDIT_MANAGE)
        self._set_rls(principal, tenant_context)
        pa = self._get_pre_audit(tenant_context.tenant_id, pre_audit_id, eager=True)

        if pa.status == PreAuditStatus.PLANNING:
            self._transition(pa, PreAuditStatus.IN_PROGRESS)
        elif pa.status not in (
            PreAuditStatus.IN_PROGRESS,
            PreAuditStatus.IN_REVIEW,
        ):
            raise InvalidPreAuditTransitionError(
                "Checks can only run when planning, in progress, or in review"
            )

        all_results: list[tuple[CheckResult, float]] = []

        for scope in pa.scopes:
            # Delete old checks for re-evaluation
            for old_check in list(scope.checks):
                self._session.delete(old_check)
            scope.checks.clear()
            self._session.flush()

            controls = list(
                self._session.scalars(
                    select(CanonicalControl).where(
                        CanonicalControl.framework_version_id == scope.framework_version_id,
                    )
                )
            )

            # Check overlay applicability
            overlays_map: dict[UUID, TenantControlOverlay] = {}
            if controls:
                overlays = list(
                    self._session.scalars(
                        select(TenantControlOverlay).where(
                            TenantControlOverlay.tenant_id == tenant_context.tenant_id,
                            TenantControlOverlay.canonical_control_id.in_([c.id for c in controls]),
                        )
                    )
                )
                for ov in overlays:
                    overlays_map[ov.canonical_control_id] = ov

            checked = 0
            for control in controls:
                overlay = overlays_map.get(control.id)
                if overlay is not None and overlay.applicability == "not_applicable":
                    check = PreAuditCheck(
                        tenant_id=tenant_context.tenant_id,
                        scope=scope,
                        control_type=ControlEntityType.CANONICAL,
                        control_id=control.id,
                        result=CheckResult.NOT_APPLICABLE,
                        rule_version=CURRENT_RULE_VERSION,
                        score=0.0,
                        evaluated_at=datetime.now(UTC),
                    )
                    self._session.add(check)
                    all_results.append((CheckResult.NOT_APPLICABLE, 0.0))
                    checked += 1
                    continue

                inp = self._gather_check_input(
                    tenant_context.tenant_id,
                    ControlEntityType.CANONICAL,
                    control.id,
                )
                rule = get_rule_for_category(control.category)
                result, score = evaluate_control_readiness(rule, inp)

                check = PreAuditCheck(
                    tenant_id=tenant_context.tenant_id,
                    scope=scope,
                    control_type=ControlEntityType.CANONICAL,
                    control_id=control.id,
                    result=result,
                    rule_version=CURRENT_RULE_VERSION,
                    evidence_count=inp.evidence_count,
                    policy_count=inp.policy_count,
                    open_findings_count=(inp.open_critical_findings + inp.open_high_findings),
                    implementation_status=inp.implementation_status,
                    score=score,
                    evaluated_at=datetime.now(UTC),
                    snapshot_json=json.dumps(snapshot_input(inp), separators=(",", ":")),
                )
                self._session.add(check)
                all_results.append((result, score))
                checked += 1

            scope.control_count = len(controls)
            scope.checked_count = checked

        self._session.flush()

        overall = compute_overall_score(all_results)
        pa.overall_score = overall
        pa.version += 1
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="preaudit.run_checks",
            resource_type="pre_audit",
            resource_id=str(pa.id),
            request_id=f"preaudit:run_checks:{pa.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "pre_audit_id": str(pa.id),
                "rule_version": CURRENT_RULE_VERSION,
                "overall_score": str(round(overall, 2)),
            },
        )
        return self._get_pre_audit(tenant_context.tenant_id, pa.id, eager=True)

    def _gather_check_input(
        self,
        tenant_id: UUID,
        control_type: ControlEntityType,
        control_id: UUID,
    ) -> CheckInput:
        """Gather current compliance state for one control."""

        # Count only valid/submitted evidence
        valid_evidence = (
            self._session.scalar(
                select(func.count(EvidenceControlLink.id))
                .join(
                    EvidenceItem,
                    EvidenceItem.id == EvidenceControlLink.evidence_id,
                )
                .where(
                    EvidenceControlLink.tenant_id == tenant_id,
                    EvidenceControlLink.control_type == control_type,
                    EvidenceControlLink.control_id == control_id,
                    EvidenceItem.status.in_([EvidenceStatus.VALID, EvidenceStatus.SUBMITTED]),
                )
            )
            or 0
        )

        policy_count = (
            self._session.scalar(
                select(func.count(PolicyControlLink.id))
                .join(
                    PolicyControlLink.policy,
                )
                .where(
                    PolicyControlLink.tenant_id == tenant_id,
                    PolicyControlLink.control_type == control_type,
                    PolicyControlLink.control_id == control_id,
                )
            )
            or 0
        )

        open_critical = (
            self._session.scalar(
                select(func.count(Finding.id)).where(
                    Finding.tenant_id == tenant_id,
                    Finding.control_type == control_type,
                    Finding.control_id == control_id,
                    Finding.severity == FindingSeverity.CRITICAL,
                    Finding.remediation_status.in_(
                        [
                            RemediationStatus.OPEN,
                            RemediationStatus.IN_REMEDIATION,
                        ]
                    ),
                )
            )
            or 0
        )
        open_high = (
            self._session.scalar(
                select(func.count(Finding.id)).where(
                    Finding.tenant_id == tenant_id,
                    Finding.control_type == control_type,
                    Finding.control_id == control_id,
                    Finding.severity == FindingSeverity.HIGH,
                    Finding.remediation_status.in_(
                        [
                            RemediationStatus.OPEN,
                            RemediationStatus.IN_REMEDIATION,
                        ]
                    ),
                )
            )
            or 0
        )

        impl_record = self._session.scalar(
            select(ControlStatusRecord).where(
                ControlStatusRecord.tenant_id == tenant_id,
                ControlStatusRecord.control_type == control_type,
                ControlStatusRecord.control_id == control_id,
            )
        )
        impl_status = impl_record.status if impl_record else None

        return CheckInput(
            evidence_count=valid_evidence,
            policy_count=policy_count,
            open_critical_findings=open_critical,
            open_high_findings=open_high,
            implementation_status=impl_status,
        )

    # ── Findings ──────────────────────────────────────────────────────────

    def add_finding(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        pre_audit_id: UUID,
        *,
        title: str,
        description: str,
        severity: FindingSeverity = FindingSeverity.MEDIUM,
        recommendation: str | None = None,
        check_id: UUID | None = None,
    ) -> PreAuditFinding:
        authorize(principal, tenant_context, Capability.PREAUDIT_MANAGE)
        self._set_rls(principal, tenant_context)
        pa = self._get_pre_audit(tenant_context.tenant_id, pre_audit_id)
        if pa.status in (PreAuditStatus.COMPLETED, PreAuditStatus.CANCELLED):
            raise InvalidPreAuditTransitionError(
                "Cannot add findings to a completed or cancelled pre-audit"
            )

        finding = PreAuditFinding(
            tenant_id=tenant_context.tenant_id,
            pre_audit_id=pre_audit_id,
            check_id=check_id,
            title=title,
            description=description,
            severity=severity,
            recommendation=recommendation,
            remediation_status=RemediationStatus.OPEN,
            version=1,
        )
        self._session.add(finding)
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="preaudit.finding.add",
            resource_type="pre_audit_finding",
            resource_id=str(finding.id),
            request_id=f"preaudit:finding:add:{finding.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "pre_audit_id": str(pre_audit_id),
                "severity": severity.value,
            },
        )
        return finding

    def update_finding(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        pre_audit_id: UUID,
        finding_id: UUID,
        *,
        expected_version: int,
        title: str | None = None,
        description: str | None = None,
        severity: FindingSeverity | None = None,
        recommendation: str | None = None,
        remediation_status: RemediationStatus | None = None,
    ) -> PreAuditFinding:
        authorize(principal, tenant_context, Capability.PREAUDIT_MANAGE)
        self._set_rls(principal, tenant_context)
        self._get_pre_audit(tenant_context.tenant_id, pre_audit_id)

        finding = self._session.scalar(
            select(PreAuditFinding).where(
                PreAuditFinding.id == finding_id,
                PreAuditFinding.tenant_id == tenant_context.tenant_id,
                PreAuditFinding.pre_audit_id == pre_audit_id,
            )
        )
        if finding is None:
            raise PreAuditFindingNotFoundError("Pre-audit finding not found")

        if finding.version != expected_version:
            raise PreAuditOptimisticLockError("Finding changed; reload and retry")

        if title is not None:
            finding.title = title
        if description is not None:
            finding.description = description
        if severity is not None:
            finding.severity = severity
        if recommendation is not None:
            finding.recommendation = recommendation
        if remediation_status is not None:
            finding.remediation_status = remediation_status

        finding.version += 1
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="preaudit.finding.update",
            resource_type="pre_audit_finding",
            resource_id=str(finding.id),
            request_id=f"preaudit:finding:update:{finding.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "pre_audit_id": str(pre_audit_id),
                "severity": finding.severity.value,
                "remediation_status": finding.remediation_status.value,
            },
        )
        return finding

    # ── Review workflow ───────────────────────────────────────────────────

    def submit_for_review(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        pre_audit_id: UUID,
        *,
        reviewer_user_id: UUID,
        expected_version: int,
    ) -> PreAudit:
        authorize(principal, tenant_context, Capability.PREAUDIT_MANAGE)
        self._set_rls(principal, tenant_context)
        self._validate_member(tenant_context, reviewer_user_id)
        pa = self._get_pre_audit(tenant_context.tenant_id, pre_audit_id)

        if pa.version != expected_version:
            raise PreAuditOptimisticLockError("Pre-audit changed; reload and retry")

        if reviewer_user_id == pa.lead_user_id:
            raise ReviewerConflictError("Reviewer must be different from the assessment lead")

        self._transition(pa, PreAuditStatus.IN_REVIEW)
        pa.reviewer_user_id = reviewer_user_id
        pa.version += 1
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="preaudit.submit_review",
            resource_type="pre_audit",
            resource_id=str(pa.id),
            request_id=f"preaudit:submit_review:{pa.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "pre_audit_id": str(pa.id),
                "status": pa.status.value,
            },
        )
        return pa

    def complete_review(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        pre_audit_id: UUID,
        *,
        expected_version: int,
    ) -> PreAudit:
        authorize(principal, tenant_context, Capability.PREAUDIT_MANAGE)
        self._set_rls(principal, tenant_context)
        pa = self._get_pre_audit(tenant_context.tenant_id, pre_audit_id)

        if pa.version != expected_version:
            raise PreAuditOptimisticLockError("Pre-audit changed; reload and retry")

        if pa.reviewer_user_id is None:
            raise InvalidPreAuditTransitionError("No reviewer assigned")

        if pa.reviewer_user_id != principal.user_id:
            raise InvalidPreAuditTransitionError(
                "Only the assigned reviewer can complete the review"
            )

        self._transition(pa, PreAuditStatus.COMPLETED)
        pa.reviewed_at = datetime.now(UTC)
        pa.version += 1
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="preaudit.complete_review",
            resource_type="pre_audit",
            resource_id=str(pa.id),
            request_id=f"preaudit:complete_review:{pa.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "pre_audit_id": str(pa.id),
                "status": pa.status.value,
                "overall_score": str(round(pa.overall_score, 2) if pa.overall_score else "0"),
            },
        )
        return pa

    def cancel_pre_audit(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        pre_audit_id: UUID,
        *,
        expected_version: int,
    ) -> PreAudit:
        authorize(principal, tenant_context, Capability.PREAUDIT_MANAGE)
        self._set_rls(principal, tenant_context)
        pa = self._get_pre_audit(tenant_context.tenant_id, pre_audit_id)

        if pa.version != expected_version:
            raise PreAuditOptimisticLockError("Pre-audit changed; reload and retry")

        self._transition(pa, PreAuditStatus.CANCELLED)
        pa.version += 1
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="preaudit.cancel",
            resource_type="pre_audit",
            resource_id=str(pa.id),
            request_id=f"preaudit:cancel:{pa.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "pre_audit_id": str(pa.id),
                "status": pa.status.value,
            },
        )
        return pa

    # ── Artifact generation ───────────────────────────────────────────────

    def generate_report(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        pre_audit_id: UUID,
        *,
        file_id: UUID,
        report_type: str = "readiness_summary",
    ) -> PreAuditReport:
        """Record a generated report artifact.

        The caller is responsible for creating the encrypted stored file
        via the file service and passing its ``file_id`` here.
        """
        authorize(principal, tenant_context, Capability.PREAUDIT_MANAGE)
        self._set_rls(principal, tenant_context)
        pa = self._get_pre_audit(tenant_context.tenant_id, pre_audit_id)

        report = PreAuditReport(
            tenant_id=tenant_context.tenant_id,
            pre_audit_id=pa.id,
            file_id=file_id,
            report_type=report_type,
            rule_version=pa.rule_version,
            generated_at=datetime.now(UTC),
        )
        self._session.add(report)
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="preaudit.generate_report",
            resource_type="pre_audit_report",
            resource_id=str(report.id),
            request_id=f"preaudit:report:{report.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "pre_audit_id": str(pa.id),
                "report_id": str(report.id),
                "report_type": report_type,
                "rule_version": pa.rule_version,
            },
        )
        return report

    def generate_manifest(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        pre_audit_id: UUID,
        *,
        file_id: UUID,
        manifest_content: str,
    ) -> PreAuditManifest:
        """Record a generated manifest artifact with integrity hash.

        The caller creates the encrypted stored file via the file service
        and passes its ``file_id`` plus the raw ``manifest_content`` (JSON)
        for hashing.
        """
        authorize(principal, tenant_context, Capability.PREAUDIT_MANAGE)
        self._set_rls(principal, tenant_context)
        pa = self._get_pre_audit(tenant_context.tenant_id, pre_audit_id, eager=True)

        manifest_hash = hashlib.sha256(manifest_content.encode("utf-8")).hexdigest()

        total_checks = sum(len(s.checks) for s in pa.scopes)

        manifest = PreAuditManifest(
            tenant_id=tenant_context.tenant_id,
            pre_audit_id=pa.id,
            file_id=file_id,
            manifest_hash_sha256=manifest_hash,
            record_count=total_checks,
            rule_version=pa.rule_version,
            generated_at=datetime.now(UTC),
        )
        self._session.add(manifest)
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="preaudit.generate_manifest",
            resource_type="pre_audit_manifest",
            resource_id=str(manifest.id),
            request_id=f"preaudit:manifest:{manifest.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "pre_audit_id": str(pa.id),
                "manifest_id": str(manifest.id),
                "manifest_hash": manifest_hash,
                "rule_version": pa.rule_version,
            },
        )
        return manifest

    # ── Certificate issuance ──────────────────────────────────────────────

    def issue_certificate(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        pre_audit_id: UUID,
        *,
        validity_days: int = 365,
    ) -> PreAuditCertificate:
        """Issue a readiness credential.

        Prerequisites:
        - Pre-audit status must be COMPLETED.
        - Reviewer must have approved (reviewed_at set).
        - All checks must pass (no FAIL results).
        """
        authorize(principal, tenant_context, Capability.PREAUDIT_MANAGE)
        self._set_rls(principal, tenant_context)
        pa = self._get_pre_audit(tenant_context.tenant_id, pre_audit_id, eager=True)

        if pa.status != PreAuditStatus.COMPLETED:
            raise CertificateIssuanceBlockedError(
                "Pre-audit must be completed before issuing a readiness credential"
            )

        if pa.reviewed_at is None:
            raise CertificateIssuanceBlockedError(
                "Pre-audit must be reviewed before issuing a readiness credential"
            )

        all_checks = [c for s in pa.scopes for c in s.checks]
        failed = [c for c in all_checks if c.result == CheckResult.FAIL]
        if failed:
            raise CertificateIssuanceBlockedError(
                f"{len(failed)} check(s) failed; resolve all failures"
                " before issuing a readiness credential"
            )

        if not all_checks:
            raise CertificateIssuanceBlockedError("No checks have been evaluated")

        now = datetime.now(UTC)
        cert_number = f"CONF-RA-{now.strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"

        cert = PreAuditCertificate(
            tenant_id=tenant_context.tenant_id,
            pre_audit_id=pa.id,
            certificate_number=cert_number,
            status=CertificateStatus.ACTIVE,
            issued_at=now,
            expires_at=now + timedelta(days=validity_days),
        )
        self._session.add(cert)
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="preaudit.certificate.issue",
            resource_type="pre_audit_certificate",
            resource_id=str(cert.id),
            request_id=f"preaudit:cert:issue:{cert.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "pre_audit_id": str(pa.id),
                "certificate_id": str(cert.id),
                "certificate_number": cert_number,
                "expires_at": cert.expires_at.isoformat(),
                "issued_at": cert.issued_at.isoformat(),
            },
        )
        return cert

    def revoke_certificate(
        self,
        principal: Principal,
        tenant_context: TenantContext,
        pre_audit_id: UUID,
        certificate_id: UUID,
        *,
        reason: str,
    ) -> PreAuditCertificate:
        authorize(principal, tenant_context, Capability.PREAUDIT_MANAGE)
        self._set_rls(principal, tenant_context)
        self._get_pre_audit(tenant_context.tenant_id, pre_audit_id)

        cert = self._session.scalar(
            select(PreAuditCertificate).where(
                PreAuditCertificate.id == certificate_id,
                PreAuditCertificate.tenant_id == tenant_context.tenant_id,
                PreAuditCertificate.pre_audit_id == pre_audit_id,
            )
        )
        if cert is None:
            raise CertificateNotFoundError("Certificate not found")

        if cert.status == CertificateStatus.REVOKED:
            raise InvalidPreAuditTransitionError("Certificate is already revoked")

        cert.status = CertificateStatus.REVOKED
        cert.revoked_at = datetime.now(UTC)
        cert.revoked_reason = reason
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="preaudit.certificate.revoke",
            resource_type="pre_audit_certificate",
            resource_id=str(cert.id),
            request_id=f"preaudit:cert:revoke:{cert.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "pre_audit_id": str(pre_audit_id),
                "certificate_id": str(cert.id),
                "certificate_number": cert.certificate_number,
                "revoked_reason": reason[:255],
            },
        )
        return cert

    # ── Score summary ─────────────────────────────────────────────────────

    def compute_score_summary(self, pa: PreAudit) -> dict[str, Any]:
        """Compute a readiness score summary from a fully-loaded pre-audit."""
        all_checks = [c for s in pa.scopes for c in s.checks]
        passed = sum(1 for c in all_checks if c.result == CheckResult.PASS)
        failed = sum(1 for c in all_checks if c.result == CheckResult.FAIL)
        na = sum(1 for c in all_checks if c.result == CheckResult.NOT_APPLICABLE)
        pending = sum(1 for c in all_checks if c.result == CheckResult.PENDING)
        open_findings = sum(
            1
            for f in pa.findings
            if f.remediation_status in (RemediationStatus.OPEN, RemediationStatus.IN_REMEDIATION)
        )
        return {
            "overall_score": pa.overall_score or 0.0,
            "total_checks": len(all_checks),
            "passed_checks": passed,
            "failed_checks": failed,
            "not_applicable_checks": na,
            "pending_checks": pending,
            "open_findings": open_findings,
        }
