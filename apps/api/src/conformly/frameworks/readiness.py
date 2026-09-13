"""Private, deterministic structured evidence evaluation; no customer narrative in snapshots."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.frameworks.models import (
    AdoptionStatus,
    CoverageDisposition,
    CoverageLedgerEntry,
    EvidenceSpecification,
    FrameworkVersion,
    MappingType,
    OverlayApplicability,
    ReleaseState,
    RequirementControlMapping,
    SourceRequirement,
    TenantControlOverlay,
    TenantFrameworkAdoption,
)
from conformly.frameworks.service import compute_version_content_digest
from conformly.frameworks.workflow import FrameworkEvidenceRequest, request_evidence_problem, utc

STRUCTURED_RULE_VERSION = "structured-evidence-v1"


def evaluate_specifications(
    session: Session, tenant_id: UUID, adoption_id: UUID, version_id: UUID
) -> dict[str, Any]:
    now = datetime.now(UTC)
    specs = list(
        session.scalars(
            select(EvidenceSpecification)
            .where(
                EvidenceSpecification.framework_version_id == version_id,
            )
            .order_by(EvidenceSpecification.identifier)
        )
    )
    requirements = list(
        session.scalars(
            select(SourceRequirement).where(
                SourceRequirement.framework_version_id == version_id,
            )
        )
    )
    if not specs and not requirements:
        return {}  # Legacy catalogs retain their existing rules; no invented source coverage.
    adoption = session.scalar(
        select(TenantFrameworkAdoption).where(
            TenantFrameworkAdoption.id == adoption_id,
            TenantFrameworkAdoption.tenant_id == tenant_id,
        )
    )
    version = session.get(FrameworkVersion, version_id)
    blockers: list[str] = []
    for requirement in requirements:
        ledger = session.scalar(
            select(CoverageLedgerEntry).where(
                CoverageLedgerEntry.framework_version_id == version_id,
                CoverageLedgerEntry.source_requirement_id == requirement.id,
            )
        )
        if ledger is None or ledger.disposition == CoverageDisposition.BLOCKED:
            blockers.append(f"{requirement.source_reference}:coverage_incomplete")
            continue
        if ledger.disposition != CoverageDisposition.IMPLEMENTED:
            if ledger.reviewed_at is None or ledger.reviewed_by_user_id is None:
                blockers.append(f"{requirement.source_reference}:coverage_review_required")
            continue
        mapped_ids = set(
            session.scalars(
                select(RequirementControlMapping.canonical_control_id).where(
                    RequirementControlMapping.framework_version_id == version_id,
                    RequirementControlMapping.source_requirement_id == requirement.id,
                    RequirementControlMapping.mapping_type == MappingType.SATISFIES,
                )
            )
        )
        if not mapped_ids or not any(
            spec.source_requirement_id == requirement.id or spec.canonical_control_id in mapped_ids
            for spec in specs
        ):
            blockers.append(f"{requirement.source_reference}:requirement_evidence_mapping_missing")
    if (
        adoption is None
        or adoption.framework_version_id != version_id
        or adoption.status != AdoptionStatus.ACTIVE
        or version is None
        or version.release_state != ReleaseState.RELEASED
    ):
        blockers.append("adoption_or_release_unavailable")
    requests = {
        r.specification_id: r
        for r in session.scalars(
            select(FrameworkEvidenceRequest).where(
                FrameworkEvidenceRequest.tenant_id == tenant_id,
                FrameworkEvidenceRequest.adoption_id == adoption_id,
            )
        )
    }
    overlays = {
        o.canonical_control_id: o
        for o in session.scalars(
            select(TenantControlOverlay).where(
                TenantControlOverlay.tenant_id == tenant_id,
                TenantControlOverlay.adoption_id == adoption_id,
            )
        )
    }
    details = []
    for spec in specs:
        control_ids = {spec.canonical_control_id} if spec.canonical_control_id else set()
        if spec.source_requirement_id:
            mappings = list(
                session.scalars(
                    select(RequirementControlMapping).where(
                        RequirementControlMapping.framework_version_id == version_id,
                        RequirementControlMapping.source_requirement_id
                        == spec.source_requirement_id,
                        RequirementControlMapping.mapping_type == MappingType.SATISFIES,
                    )
                )
            )
            control_ids.update(m.canonical_control_id for m in mappings)
            if not mappings:
                blockers.append(f"{spec.identifier}:full_requirement_mapping_missing")
        # Exclusion review is intentionally fail-closed until its explicit approval boundary exists.
        if not control_ids or any(
            cid not in overlays or overlays[cid].applicability != OverlayApplicability.APPLICABLE
            for cid in control_ids
        ):
            blockers.append(f"{spec.identifier}:applicability_review_required")
        row = requests.get(spec.id)
        problem = (
            "request_missing"
            if row is None
            else request_evidence_problem(session, row, spec, now=now)
        )
        if problem:
            blockers.append(f"{spec.identifier}:{problem}")
        details.append(
            {
                "specification_id": str(spec.id),
                "request_id": str(row.id) if row else None,
                "evidence_id": str(row.evidence_id) if row and row.evidence_id else None,
                "evidence_version": row.evidence_version if row else None,
                "accepted_by": str(row.accepted_by_user_id)
                if row and row.accepted_by_user_id
                else None,
                "accepted_at": utc(row.accepted_at).isoformat()
                if row and row.accepted_at
                else None,
                "observation_start": utc(row.observation_start).isoformat()
                if row and row.observation_start
                else None,
                "observation_end": utc(row.observation_end).isoformat()
                if row and row.observation_end
                else None,
                "problem": problem,
            }
        )
    return {
        "rule_version": STRUCTURED_RULE_VERSION,
        "framework_version_id": str(version_id),
        "content_digest": compute_version_content_digest(version) if version else None,
        "specifications": details,
        "applicability": [
            {
                "control_id": str(cid),
                "status": o.applicability.value,
                "overlay_id": str(o.id),
                "updated_at": utc(o.updated_at).isoformat(),
            }
            for cid, o in sorted(overlays.items(), key=lambda item: str(item[0]))
        ],
        "blockers": sorted(blockers),
    }
