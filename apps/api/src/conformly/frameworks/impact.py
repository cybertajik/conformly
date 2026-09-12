from dataclasses import dataclass
from uuid import UUID

from conformly.frameworks.models import (
    CanonicalControl,
    ControlMapping,
    FrameworkVersion,
    TenantControlOverlay,
)


@dataclass(frozen=True, slots=True)
class FieldDiff:
    field_name: str
    source_value: str | None
    target_value: str | None


@dataclass(frozen=True, slots=True)
class ControlModification:
    identifier: str
    source_title: str
    target_title: str
    source_category: str
    target_category: str
    changed_fields: tuple[str, ...]
    field_diffs: tuple[FieldDiff, ...]


@dataclass(frozen=True, slots=True)
class ControlSummaryItem:
    id: str
    identifier: str
    title: str
    category: str
    description: str
    guidance: str | None


@dataclass(frozen=True, slots=True)
class TenantImpactWarning:
    severity: str  # "breaking" | "review_required" | "info"
    control_identifier: str
    item_type: str  # "overlay" | "mapping"
    message: str
    recommendation: str


@dataclass(frozen=True, slots=True)
class ImpactAnalysisReport:
    framework_id: UUID
    source_version_id: UUID
    source_version_string: str
    target_version_id: UUID
    target_version_string: str
    total_source_controls: int
    total_target_controls: int
    added_controls: tuple[ControlSummaryItem, ...]
    removed_controls: tuple[ControlSummaryItem, ...]
    modified_controls: tuple[ControlModification, ...]
    unchanged_count: int
    tenant_warnings: tuple[TenantImpactWarning, ...]
    overall_impact_level: str  # "low" | "medium" | "high"


def compute_framework_impact(
    source_version: FrameworkVersion,
    target_version: FrameworkVersion,
    tenant_overlays: list[TenantControlOverlay] | None = None,
    tenant_mappings: list[ControlMapping] | None = None,
) -> ImpactAnalysisReport:
    """Deterministically analyze the difference between two versions of a framework."""
    source_map: dict[str, CanonicalControl] = {c.identifier: c for c in source_version.controls}
    target_map: dict[str, CanonicalControl] = {c.identifier: c for c in target_version.controls}

    source_ids = set(source_map.keys())
    target_ids = set(target_map.keys())

    added_ids = sorted(target_ids - source_ids)
    removed_ids = sorted(source_ids - target_ids)
    common_ids = sorted(source_ids & target_ids)

    added_controls: list[ControlSummaryItem] = [
        ControlSummaryItem(
            id=str(target_map[i].id),
            identifier=target_map[i].identifier,
            title=target_map[i].title,
            category=target_map[i].category,
            description=target_map[i].description,
            guidance=target_map[i].guidance,
        )
        for i in added_ids
    ]

    removed_controls: list[ControlSummaryItem] = [
        ControlSummaryItem(
            id=str(source_map[i].id),
            identifier=source_map[i].identifier,
            title=source_map[i].title,
            category=source_map[i].category,
            description=source_map[i].description,
            guidance=source_map[i].guidance,
        )
        for i in removed_ids
    ]

    modified_controls: list[ControlModification] = []
    unchanged_count = 0

    for ident in common_ids:
        src = source_map[ident]
        tgt = target_map[ident]

        diffs: list[FieldDiff] = []
        if src.title != tgt.title:
            diffs.append(FieldDiff("title", src.title, tgt.title))
        if src.category != tgt.category:
            diffs.append(FieldDiff("category", src.category, tgt.category))
        if src.description != tgt.description:
            diffs.append(FieldDiff("description", src.description, tgt.description))
        if src.guidance != tgt.guidance:
            diffs.append(FieldDiff("guidance", src.guidance, tgt.guidance))

        if diffs:
            modified_controls.append(
                ControlModification(
                    identifier=ident,
                    source_title=src.title,
                    target_title=tgt.title,
                    source_category=src.category,
                    target_category=tgt.category,
                    changed_fields=tuple(d.field_name for d in diffs),
                    field_diffs=tuple(diffs),
                )
            )
        else:
            unchanged_count += 1

    warnings: list[TenantImpactWarning] = []
    source_control_id_to_ident: dict[UUID, str] = {
        c.id: c.identifier for c in source_version.controls
    }

    # Evaluate tenant overlay impact
    if tenant_overlays:
        for overlay in tenant_overlays:
            overlay_ident = source_control_id_to_ident.get(overlay.canonical_control_id)
            if overlay_ident is None:
                continue
            if overlay_ident in removed_ids:
                warnings.append(
                    TenantImpactWarning(
                        severity="breaking",
                        control_identifier=overlay_ident,
                        item_type="overlay",
                        message=(
                            f"Canonical control {overlay_ident} has an active overlay "
                            f"but is removed in version {target_version.version}."
                        ),
                        recommendation=(
                            "Review whether the requirements of this control have moved "
                            "to a new control or if the overlay should be archived."
                        ),
                    )
                )
            elif overlay_ident in [m.identifier for m in modified_controls]:
                warnings.append(
                    TenantImpactWarning(
                        severity="review_required",
                        control_identifier=overlay_ident,
                        item_type="overlay",
                        message=(
                            f"Canonical control {overlay_ident} has updated requirements "
                            f"in version {target_version.version}."
                        ),
                        recommendation=(
                            "Review custom guidance and applicability against "
                            "the updated canonical definition."
                        ),
                    )
                )

    # Evaluate tenant mapping impact
    if tenant_mappings:
        for mapping in tenant_mappings:
            map_ident = source_control_id_to_ident.get(
                mapping.source_control_id
            ) or source_control_id_to_ident.get(mapping.target_control_id)
            if map_ident is None:
                continue
            if map_ident in removed_ids:
                warnings.append(
                    TenantImpactWarning(
                        severity="breaking",
                        control_identifier=map_ident,
                        item_type="mapping",
                        message=(
                            f"Control mapping references control {map_ident} which is "
                            f"removed in target version {target_version.version}."
                        ),
                        recommendation=(
                            "Update or remove the control mapping to avoid referencing "
                            "obsolete controls."
                        ),
                    )
                )
            elif map_ident in [m.identifier for m in modified_controls]:
                warnings.append(
                    TenantImpactWarning(
                        severity="review_required",
                        control_identifier=map_ident,
                        item_type="mapping",
                        message=(
                            f"Control mapping references control {map_ident} which has "
                            f"modified requirements in target version {target_version.version}."
                        ),
                        recommendation="Verify that the mapping rationale remains valid.",
                    )
                )

    has_breaking = any(w.severity == "breaking" for w in warnings) or len(removed_controls) > 0
    has_review = (
        any(w.severity == "review_required" for w in warnings)
        or len(modified_controls) > 0
        or len(added_controls) > 0
    )

    if has_breaking:
        overall_impact = "high"
    elif has_review:
        overall_impact = "medium"
    else:
        overall_impact = "low"

    return ImpactAnalysisReport(
        framework_id=source_version.framework_id,
        source_version_id=source_version.id,
        source_version_string=source_version.version,
        target_version_id=target_version.id,
        target_version_string=target_version.version,
        total_source_controls=len(source_version.controls),
        total_target_controls=len(target_version.controls),
        added_controls=tuple(added_controls),
        removed_controls=tuple(removed_controls),
        modified_controls=tuple(modified_controls),
        unchanged_count=unchanged_count,
        tenant_warnings=tuple(warnings),
        overall_impact_level=overall_impact,
    )
