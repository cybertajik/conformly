"""Base data types for compliance framework pack definitions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from conformly.frameworks.models import (
    CoverageDisposition,
    MappingType,
    SourceRequirementType,
)


@dataclass(frozen=True, slots=True)
class PackControlDefinition:
    identifier: str
    title: str
    description: str
    category: str
    guidance: str
    sort_order: int
    applicability_criteria: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PackSourceRequirementDefinition:
    source_reference: str
    title: str
    requirement_type: SourceRequirementType
    source_authority: str
    edition_or_amendment: str
    source_text: str
    content_rights: str
    source_url: str | None = None
    retrieval_date: datetime | None = None
    language: str = "en"
    effective_date: str | None = None
    permitted_use: str | None = None
    conformly_guidance: str | None = None
    suggested_operating_targets: dict[str, Any] | None = None
    assessment_procedure: str | None = None
    default_owner_role: str | None = None
    review_cadence: str | None = None
    applicability_conditions: dict[str, Any] | None = None
    reporting_limitations: str | None = None
    sort_order: int = 0


@dataclass(frozen=True, slots=True)
class PackMappingDefinition:
    source_reference: str
    control_identifier: str
    mapping_type: MappingType = MappingType.SATISFIES
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class PackEvidenceDefinition:
    identifier: str
    title: str
    description: str
    evidence_type: str
    control_identifier: str | None = None
    source_reference: str | None = None
    original_file_required: bool = False
    observation_period_days: int | None = None
    validity_period_days: int | None = None
    review_cadence_days: int | None = None
    confidentiality_level: str = "Internal"
    suggested_storage_format: str | None = None


@dataclass(frozen=True, slots=True)
class PackCoverageDefinition:
    source_reference: str
    disposition: CoverageDisposition
    rationale: str


@dataclass(frozen=True, slots=True)
class FrameworkPackDefinition:
    slug: str
    name: str
    version: str
    description: str
    release_notes: str
    legal_review_notes: str
    approval_notes: str
    controls: list[PackControlDefinition]
    source_requirements: list[PackSourceRequirementDefinition] = field(default_factory=list)
    mappings: list[PackMappingDefinition] = field(default_factory=list)
    evidence_specifications: list[PackEvidenceDefinition] = field(default_factory=list)
    coverage_ledger: list[PackCoverageDefinition] = field(default_factory=list)
