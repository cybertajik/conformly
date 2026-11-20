"""Deterministic canonical JSON encoding and SHA-256 draft content digest calculation."""

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

DIGEST_SCHEMA_V1 = "catalog-draft-v1"


def format_canonical_datetime(dt: datetime) -> str:
    """Format timezone-aware datetime to ISO-8601 with UTC Z suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    if dt.microsecond == 0:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    micro = f"{dt.microsecond:06d}".rstrip("0")
    return dt.strftime(f"%Y-%m-%dT%H:%M:%S.{micro}Z")


def format_canonical_date(d: date) -> str:
    """Format date to YYYY-MM-DD."""
    return d.isoformat()


def canonical_json(val: Any) -> str:
    """Encode object to deterministic UTF-8 JSON."""

    def default_serializer(o: Any) -> Any:
        if isinstance(o, UUID):
            return str(o).lower()
        if isinstance(o, (bytes, bytearray)):
            return bytes(o).hex()
        if isinstance(o, datetime):
            return format_canonical_datetime(o)
        if isinstance(o, date):
            return format_canonical_date(o)
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    return json.dumps(
        val,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=default_serializer,
        allow_nan=False,
    )


def compute_content_digest(data: Any) -> bytes:
    """Compute 32-byte SHA-256 digest from canonical JSON representation."""
    encoded = canonical_json(data).encode("utf-8")
    return hashlib.sha256(encoded).digest()


def compute_source_version_digest(
    source_id: UUID,
    edition: str,
    predecessor_id: UUID | None,
    language: str | None,
    official_locator: str | None,
    publication_date: date | None,
    retrieved_at: datetime | None,
    status: str = "Draft",
) -> bytes:
    payload = {
        "edition": edition,
        "language": language,
        "official_locator": official_locator,
        "predecessor_id": predecessor_id,
        "publication_date": publication_date,
        "retrieved_at": retrieved_at,
        "source_id": source_id,
        "status": status,
    }
    return compute_content_digest(payload)


def compute_requirement_version_digest(
    requirement_id: UUID,
    source_id: UUID,
    source_version_id: UUID,
    version_label: str,
    predecessor_id: UUID | None,
    revision: int,
    normalized_outcome: str,
    requirement_type: str,
    obligated_actor: str,
    text_origin: str,
    customer_display_text: str | None,
    effective_from: date | None,
    effective_until: date | None,
    source_references: list[dict[str, Any]],
    status: str = "Draft",
) -> bytes:
    sorted_refs = [
        {
            "locator_kind": ref.get("locator_kind"),
            "locator_value": ref.get("locator_value"),
            "sequence": ref.get("sequence"),
            "source_version_id": ref.get("source_version_id"),
        }
        for ref in source_references
    ]
    payload = {
        "customer_display_text": customer_display_text,
        "effective_from": effective_from,
        "effective_until": effective_until,
        "normalized_outcome": normalized_outcome,
        "obligated_actor": obligated_actor,
        "predecessor_id": predecessor_id,
        "requirement_id": requirement_id,
        "requirement_type": requirement_type,
        "revision": revision,
        "source_id": source_id,
        "source_references": sorted_refs,
        "source_version_id": source_version_id,
        "status": status,
        "text_origin": text_origin,
        "version_label": version_label,
    }
    return compute_content_digest(payload)


def compute_control_version_digest(
    control_id: UUID,
    version_label: str,
    predecessor_id: UUID | None,
    revision: int,
    title: str,
    objective: str,
    guidance: str | None,
    control_type: str,
    frequency: str,
    automation_level: str,
    suggested_owner_role: str,
    assurance_level: str,
    tags_state: str,
    tags: str | None,
    status: str = "Draft",
) -> bytes:
    payload = {
        "assurance_level": assurance_level,
        "automation_level": automation_level,
        "control_id": control_id,
        "control_type": control_type,
        "frequency": frequency,
        "guidance": guidance,
        "objective": objective,
        "predecessor_id": predecessor_id,
        "revision": revision,
        "status": status,
        "suggested_owner_role": suggested_owner_role,
        "tags": tags,
        "tags_state": tags_state,
        "title": title,
        "version_label": version_label,
    }
    return compute_content_digest(payload)


def compute_mapping_version_digest(
    mapping_id: UUID,
    requirement_id: UUID,
    control_id: UUID,
    requirement_version_id: UUID,
    control_version_id: UUID,
    requirement_version_revision: int,
    requirement_version_digest: bytes,
    control_version_revision: int,
    control_version_digest: bytes,
    version_label: str,
    predecessor_id: UUID | None,
    revision: int,
    mapping_type: str,
    rationale: str,
    covered_dimensions: str | None,
    excluded_dimensions: str | None,
    conditions: str | None,
    source_basis: str,
    confidence: str,
    review_state: str = "Draft",
    status: str = "Draft",
) -> bytes:
    payload = {
        "conditions": conditions,
        "confidence": confidence,
        "control_id": control_id,
        "control_version_digest": control_version_digest,
        "control_version_id": control_version_id,
        "control_version_revision": control_version_revision,
        "covered_dimensions": covered_dimensions,
        "excluded_dimensions": excluded_dimensions,
        "mapping_id": mapping_id,
        "mapping_type": mapping_type,
        "predecessor_id": predecessor_id,
        "rationale": rationale,
        "requirement_id": requirement_id,
        "requirement_version_digest": requirement_version_digest,
        "requirement_version_id": requirement_version_id,
        "requirement_version_revision": requirement_version_revision,
        "review_state": review_state,
        "revision": revision,
        "source_basis": source_basis,
        "status": status,
        "version_label": version_label,
    }
    return compute_content_digest(payload)


def compute_pack_version_digest(
    pack_id: UUID,
    version_label: str,
    predecessor_id: UUID | None,
    revision: int,
    description: str | None,
    status: str = "Draft",
) -> bytes:
    payload = {
        "description": description,
        "pack_id": pack_id,
        "predecessor_id": predecessor_id,
        "revision": revision,
        "status": status,
        "version_label": version_label,
    }
    return compute_content_digest(payload)


DIGEST_SCHEMA_ASSURANCE_V1 = "catalog-assurance-draft-v1"


def compute_evidence_requirement_version_digest(
    control_version_id: UUID,
    control_version_digest: bytes | str,
    requirement_key: str,
    sequence: int,
    title: str,
    frequency: str,
    custom_frequency: str | None,
    scope_state: str,
    scope_guidance: str | None,
    assurance_purpose: str,
    validity_rule: str,
    max_age_days: int | None,
    guidance: str | None,
    artifact_types: list[dict[str, Any]],
    required_metadata: list[dict[str, Any]],
    missing_data_behavior: str = "requires_human_review",
) -> bytes:
    cv_digest = (
        control_version_digest.hex()
        if isinstance(control_version_digest, (bytes, bytearray))
        else str(control_version_digest)
    )
    formatted_artifact_types = [
        {"artifact_type": item["artifact_type"], "sequence": item["sequence"]}
        for item in artifact_types
    ]
    formatted_metadata = [
        {"metadata_key": item["metadata_key"], "sequence": item["sequence"]}
        for item in required_metadata
    ]
    payload = {
        "artifact_types": formatted_artifact_types,
        "assurance_purpose": assurance_purpose,
        "control_version_digest": cv_digest,
        "control_version_id": str(control_version_id).lower(),
        "custom_frequency": custom_frequency,
        "frequency": frequency,
        "guidance": guidance,
        "kind": "EvidenceRequirementVersion",
        "max_age_days": max_age_days,
        "missing_data_behavior": missing_data_behavior,
        "required_metadata": formatted_metadata,
        "requirement_key": requirement_key,
        "scope_guidance": scope_guidance,
        "scope_state": scope_state,
        "sequence": sequence,
        "title": title,
        "validity_rule": validity_rule,
    }
    return compute_content_digest(payload)


def compute_assessment_procedure_version_digest(
    control_version_id: UUID,
    control_version_digest: bytes | str,
    procedure_key: str,
    sequence: int,
    title: str,
    objective: str,
    sample_guidance: str | None,
    scope_guidance: str | None,
    decision_guidance: str,
    assessor_qualifications: str | None,
    steps: list[dict[str, Any]],
    evidence_requirements: list[dict[str, Any]],
    missing_data_behavior: str = "requires_human_review",
) -> bytes:
    cv_digest = (
        control_version_digest.hex()
        if isinstance(control_version_digest, (bytes, bytearray))
        else str(control_version_digest)
    )
    formatted_steps = [
        {
            "expected_output": s.get("expected_output"),
            "instruction": s["instruction"],
            "sequence": s["sequence"],
            "step_kind": s["step_kind"],
        }
        for s in steps
    ]
    formatted_er_links = [
        {
            "content_digest": (
                r["content_digest"].hex()
                if isinstance(r["content_digest"], (bytes, bytearray))
                else str(r["content_digest"])
            ),
            "id": str(r["id"]).lower(),
            "sequence": r["sequence"],
        }
        for r in evidence_requirements
    ]
    payload = {
        "assessor_qualifications": assessor_qualifications,
        "control_version_digest": cv_digest,
        "control_version_id": str(control_version_id).lower(),
        "decision_guidance": decision_guidance,
        "evidence_requirements": formatted_er_links,
        "kind": "AssessmentProcedureVersion",
        "missing_data_behavior": missing_data_behavior,
        "objective": objective,
        "procedure_key": procedure_key,
        "sample_guidance": sample_guidance,
        "scope_guidance": scope_guidance,
        "sequence": sequence,
        "steps": formatted_steps,
        "title": title,
    }
    return compute_content_digest(payload)
