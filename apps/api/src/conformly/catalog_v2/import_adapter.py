"""Pure validation and preview primitives for the conservative import adapter.

This module deliberately performs no database writes. Durable execution lives in
``services_import`` so dry-run behavior can be proven write-free.
"""

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from conformly.catalog_v2.digest import compute_content_digest

ADAPTER_VERSION = "catalog-import-v1"
MAX_BATCH_INPUTS = 5_000
MAX_BATCH_BYTES = 25 * 1024 * 1024
MAX_STRING_LENGTH = 4_096
MAX_HIERARCHY_DEPTH = 8
ILLEGAL_SENTINELS = ("UNRELEASED_SECRET", "PROHIBITED_TOKEN")

RE_ER_KEY = re.compile(r"^ER-[A-Z0-9_-]{3,61}$")
RE_AP_KEY = re.compile(r"^AP-[A-Z0-9_-]{3,61}$")
RE_METADATA_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

KNOWN_ER_FREQUENCIES = frozenset(
    {
        "continuous",
        "event_driven",
        "monthly",
        "quarterly",
        "semiannual",
        "annual",
        "custom",
    }
)
KNOWN_ER_SCOPE_STATES = frozenset({"All", "Conditional"})
KNOWN_ASSURANCE_PURPOSES = frozenset(
    {"design", "implementation", "operating_effectiveness", "combined"}
)
KNOWN_VALIDITY_RULES = frozenset({"point_in_time", "period_coverage", "continuous", "event_driven"})
KNOWN_ARTIFACT_TYPES = frozenset(
    {
        "document",
        "record",
        "configuration",
        "log",
        "ticket",
        "report",
        "attestation",
        "observation",
        "interview",
        "other",
    }
)
KNOWN_STEP_KINDS = frozenset({"inspect", "inquire", "observe", "reperform", "analyze"})

ALLOWED_ER_PAYLOAD_KEYS = frozenset(
    {
        "control_version_id",
        "parent_control_sequence",
        "parent_control_origin_namespace",
        "parent_control_origin_id",
        "expected_control_digest",
        "requirement_key",
        "title",
        "frequency",
        "custom_frequency",
        "scope_state",
        "scope_guidance",
        "assurance_purpose",
        "validity_rule",
        "max_age_days",
        "guidance",
        "artifact_types",
        "required_metadata",
        "source_version_id",
    }
)

ALLOWED_AP_PAYLOAD_KEYS = frozenset(
    {
        "control_version_id",
        "parent_control_sequence",
        "parent_control_origin_namespace",
        "parent_control_origin_id",
        "expected_control_digest",
        "procedure_key",
        "title",
        "objective",
        "sample_guidance",
        "scope_guidance",
        "decision_guidance",
        "assessor_qualifications",
        "steps",
        "evidence_requirements",
        "source_version_id",
    }
)


class ImportDisposition(StrEnum):
    PENDING = "Pending"
    IMPORTED_DRAFT = "ImportedDraft"
    REUSED_EXACT = "ReusedExact"
    NEEDS_PERMISSION = "NeedsPermission"
    NEEDS_SOURCE = "NeedsSource"
    NEEDS_MAPPING_REVIEW = "NeedsMappingReview"
    NEEDS_CONFLICT_REVIEW = "NeedsConflictReview"
    NEEDS_DEPENDENCY = "NeedsDependency"
    DEFERRED_BY_SCOPE = "DeferredByScope"
    REJECTED = "Rejected"


SUPPORTED_INPUT_TYPES = frozenset(
    {
        "Requirement",
        "CommonControl",
        "Mapping",
        "Pack",
        "PackMembership",
        "EvidenceRequirement",
        "AssessmentProcedure",
    }
)
DEFERRED_INPUT_TYPES: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ImportItem:
    sequence: int
    input_type: str
    origin_namespace: str
    origin_id: str
    payload: dict[str, Any]

    @property
    def fingerprint(self) -> bytes:
        return compute_content_digest(
            {
                "input_type": self.input_type,
                "origin_id": self.origin_id,
                "origin_namespace": self.origin_namespace,
                "payload": self.payload,
            }
        )


@dataclass(frozen=True)
class PreviewResult:
    sequence: int
    origin_namespace: str
    origin_id: str
    disposition: ImportDisposition
    reason_code: str
    input_fingerprint: bytes


@dataclass(frozen=True)
class PreviewContext:
    available_sources: frozenset[str] = frozenset()
    permitted_origins: frozenset[str] = frozenset()
    resolvable_dependencies: frozenset[str] = frozenset()


class ImportPayloadError(ValueError):
    """Raised when the batch envelope itself is unsafe or non-canonical."""


def _walk(value: Any, *, depth: int = 0) -> None:
    if depth > MAX_HIERARCHY_DEPTH:
        raise ImportPayloadError("PAYLOAD_HIERARCHY_TOO_DEEP")
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            raise ImportPayloadError("PAYLOAD_STRING_TOO_LONG")
        if any(token in value for token in ILLEGAL_SENTINELS):
            raise ImportPayloadError("MALFORMED_INPUT_PROHIBITED_TOKEN")
    elif isinstance(value, dict):
        for key, child in value.items():
            _walk(key, depth=depth + 1)
            _walk(child, depth=depth + 1)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _walk(child, depth=depth + 1)


def _validate_parent_control_locators(payload: dict[str, Any]) -> None:
    has_uuid = bool(payload.get("control_version_id"))
    has_seq = payload.get("parent_control_sequence") is not None
    has_origin = bool(
        payload.get("parent_control_origin_namespace") and payload.get("parent_control_origin_id")
    )
    if not (has_uuid or has_seq or has_origin):
        raise ImportPayloadError("PARENT_CONTROL_LOCATOR_REQUIRED")


def _validate_evidence_requirement_payload(payload: dict[str, Any]) -> None:
    unknown_keys = set(payload.keys()) - ALLOWED_ER_PAYLOAD_KEYS
    if unknown_keys:
        raise ImportPayloadError(f"UNKNOWN_PAYLOAD_FIELDS:{','.join(sorted(unknown_keys))}")

    if payload.get("source_version_id") is not None:
        raise ImportPayloadError("SYNTHETIC_ASSURANCE_SOURCE_VERSION_FORBIDDEN")

    _validate_parent_control_locators(payload)

    req_key = payload.get("requirement_key")
    if (
        not isinstance(req_key, str)
        or not (6 <= len(req_key) <= 64)
        or not RE_ER_KEY.match(req_key)
    ):
        raise ImportPayloadError("INVALID_REQUIREMENT_KEY_FORMAT")

    title = payload.get("title")
    if not isinstance(title, str) or not (1 <= len(title) <= 512):
        raise ImportPayloadError("INVALID_TITLE")

    freq = payload.get("frequency")
    if freq not in KNOWN_ER_FREQUENCIES:
        raise ImportPayloadError("INVALID_FREQUENCY")

    custom_freq = payload.get("custom_frequency")
    if freq == "custom":
        if not isinstance(custom_freq, str) or not (1 <= len(custom_freq) <= 256):
            raise ImportPayloadError("INVALID_CUSTOM_FREQUENCY")
    elif custom_freq is not None:
        raise ImportPayloadError("UNEXPECTED_CUSTOM_FREQUENCY")

    scope_state = payload.get("scope_state")
    if scope_state not in KNOWN_ER_SCOPE_STATES:
        raise ImportPayloadError("INVALID_SCOPE_STATE")

    scope_guidance = payload.get("scope_guidance")
    if scope_state == "Conditional":
        if not isinstance(scope_guidance, str) or not (1 <= len(scope_guidance) <= 2048):
            raise ImportPayloadError("INVALID_SCOPE_GUIDANCE")
    elif scope_guidance is not None:
        raise ImportPayloadError("UNEXPECTED_SCOPE_GUIDANCE")

    assurance_purpose = payload.get("assurance_purpose")
    if assurance_purpose not in KNOWN_ASSURANCE_PURPOSES:
        raise ImportPayloadError("INVALID_ASSURANCE_PURPOSE")

    validity_rule = payload.get("validity_rule")
    if validity_rule not in KNOWN_VALIDITY_RULES:
        raise ImportPayloadError("INVALID_VALIDITY_RULE")

    max_age_days = payload.get("max_age_days")
    if validity_rule == "point_in_time":
        if (
            not isinstance(max_age_days, int)
            or isinstance(max_age_days, bool)
            or not (1 <= max_age_days <= 3660)
        ):
            raise ImportPayloadError("INVALID_MAX_AGE_DAYS")
    elif max_age_days is not None:
        raise ImportPayloadError("UNEXPECTED_MAX_AGE_DAYS")

    guidance = payload.get("guidance")
    if guidance is not None and (not isinstance(guidance, str) or not (1 <= len(guidance) <= 4096)):
        raise ImportPayloadError("INVALID_GUIDANCE")

    artifact_types = payload.get("artifact_types")
    if not isinstance(artifact_types, list) or not (1 <= len(artifact_types) <= 16):
        raise ImportPayloadError("INVALID_ARTIFACT_TYPES_COUNT")
    seen_types: set[str] = set()
    for idx, entry in enumerate(artifact_types, start=1):
        if not isinstance(entry, dict) or set(entry.keys()) != {"artifact_type", "sequence"}:
            raise ImportPayloadError("INVALID_ARTIFACT_TYPE_PAYLOAD")
        if entry.get("sequence") != idx:
            raise ImportPayloadError("INVALID_ARTIFACT_TYPE_SEQUENCE")
        atype = entry.get("artifact_type")
        if atype not in KNOWN_ARTIFACT_TYPES or atype in seen_types:
            raise ImportPayloadError("INVALID_ARTIFACT_TYPE")
        seen_types.add(atype)

    required_metadata = payload.get("required_metadata", [])
    if required_metadata is not None:
        if not isinstance(required_metadata, list) or len(required_metadata) > 32:
            raise ImportPayloadError("INVALID_REQUIRED_METADATA_COUNT")
        seen_meta: set[str] = set()
        for idx, entry in enumerate(required_metadata, start=1):
            if not isinstance(entry, dict) or set(entry.keys()) != {"metadata_key", "sequence"}:
                raise ImportPayloadError("INVALID_METADATA_KEY_PAYLOAD")
            if entry.get("sequence") != idx:
                raise ImportPayloadError("INVALID_METADATA_KEY_SEQUENCE")
            mkey = entry.get("metadata_key")
            if not isinstance(mkey, str) or not RE_METADATA_KEY.match(mkey) or mkey in seen_meta:
                raise ImportPayloadError("INVALID_METADATA_KEY")
            seen_meta.add(mkey)


def _validate_assessment_procedure_payload(payload: dict[str, Any]) -> None:
    unknown_keys = set(payload.keys()) - ALLOWED_AP_PAYLOAD_KEYS
    if unknown_keys:
        raise ImportPayloadError(f"UNKNOWN_PAYLOAD_FIELDS:{','.join(sorted(unknown_keys))}")

    if payload.get("source_version_id") is not None:
        raise ImportPayloadError("SYNTHETIC_ASSURANCE_SOURCE_VERSION_FORBIDDEN")

    _validate_parent_control_locators(payload)

    proc_key = payload.get("procedure_key")
    if (
        not isinstance(proc_key, str)
        or not (6 <= len(proc_key) <= 64)
        or not RE_AP_KEY.match(proc_key)
    ):
        raise ImportPayloadError("INVALID_PROCEDURE_KEY_FORMAT")

    title = payload.get("title")
    if not isinstance(title, str) or not (1 <= len(title) <= 512):
        raise ImportPayloadError("INVALID_TITLE")

    objective = payload.get("objective")
    if not isinstance(objective, str) or not (1 <= len(objective) <= 4096):
        raise ImportPayloadError("INVALID_OBJECTIVE")

    sample_guidance = payload.get("sample_guidance")
    if sample_guidance is not None and (
        not isinstance(sample_guidance, str) or not (1 <= len(sample_guidance) <= 2048)
    ):
        raise ImportPayloadError("INVALID_SAMPLE_GUIDANCE")

    scope_guidance = payload.get("scope_guidance")
    if scope_guidance is not None and (
        not isinstance(scope_guidance, str) or not (1 <= len(scope_guidance) <= 2048)
    ):
        raise ImportPayloadError("INVALID_SCOPE_GUIDANCE")

    decision_guidance = payload.get("decision_guidance")
    if not isinstance(decision_guidance, str) or not (1 <= len(decision_guidance) <= 4096):
        raise ImportPayloadError("INVALID_DECISION_GUIDANCE")

    assessor_qual = payload.get("assessor_qualifications")
    if assessor_qual is not None and (
        not isinstance(assessor_qual, str) or not (1 <= len(assessor_qual) <= 2048)
    ):
        raise ImportPayloadError("INVALID_ASSESSOR_QUALIFICATIONS")

    steps = payload.get("steps")
    if not isinstance(steps, list) or not (1 <= len(steps) <= 50):
        raise ImportPayloadError("INVALID_STEPS_COUNT")
    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise ImportPayloadError("INVALID_STEP_PAYLOAD")
        allowed_step_keys = {"sequence", "step_kind", "instruction", "expected_output"}
        if not set(step.keys()).issubset(allowed_step_keys):
            raise ImportPayloadError("INVALID_STEP_PAYLOAD")
        if step.get("sequence") != idx:
            raise ImportPayloadError("INVALID_STEP_SEQUENCE")
        step_kind = step.get("step_kind")
        if step_kind not in KNOWN_STEP_KINDS:
            raise ImportPayloadError("UNSUPPORTED_STEP_KIND")
        instruction = step.get("instruction")
        if not isinstance(instruction, str) or not (1 <= len(instruction) <= 4096):
            raise ImportPayloadError("INVALID_STEP_INSTRUCTION")
        expected_output = step.get("expected_output")
        if expected_output is not None and (
            not isinstance(expected_output, str) or not (1 <= len(expected_output) <= 2048)
        ):
            raise ImportPayloadError("INVALID_STEP_EXPECTED_OUTPUT")

    evidence_requirements = payload.get("evidence_requirements", [])
    if evidence_requirements is not None:
        if not isinstance(evidence_requirements, list) or len(evidence_requirements) > 32:
            raise ImportPayloadError("EVIDENCE_REQUIREMENTS_COUNT_EXCEEDED")
        for idx, link in enumerate(evidence_requirements, start=1):
            if not isinstance(link, dict):
                raise ImportPayloadError("INVALID_LINK_PAYLOAD")
            allowed_link_keys = {
                "sequence",
                "id",
                "evidence_requirement_version_id",
                "evidence_requirement_sequence",
                "evidence_requirement_origin_namespace",
                "evidence_requirement_origin_id",
                "content_digest",
            }
            if not set(link.keys()).issubset(allowed_link_keys):
                raise ImportPayloadError("INVALID_LINK_PAYLOAD")
            if link.get("sequence") != idx:
                raise ImportPayloadError("INVALID_LINK_SEQUENCE")
            has_link_id = bool(link.get("id") or link.get("evidence_requirement_version_id"))
            has_link_seq = link.get("evidence_requirement_sequence") is not None
            has_link_origin = bool(
                link.get("evidence_requirement_origin_namespace")
                and link.get("evidence_requirement_origin_id")
            )
            if not (has_link_id or has_link_seq or has_link_origin):
                raise ImportPayloadError("LINKED_EVIDENCE_REQUIREMENT_LOCATOR_REQUIRED")


def _validate_batch_envelope(items: list[ImportItem]) -> None:
    if not items or len(items) > MAX_BATCH_INPUTS:
        raise ImportPayloadError("BATCH_INPUT_COUNT_OUT_OF_RANGE")
    if len({item.sequence for item in items}) != len(items):
        raise ImportPayloadError("DUPLICATE_INPUT_SEQUENCE")
    if sorted(item.sequence for item in items) != list(range(1, len(items) + 1)):
        raise ImportPayloadError("NON_CONTIGUOUS_INPUT_SEQUENCE")
    if len({(item.origin_namespace, item.origin_id) for item in items}) != len(items):
        raise ImportPayloadError("DUPLICATE_INPUT_ORIGIN")
    if sum(len(repr(item.payload).encode("utf-8")) for item in items) > MAX_BATCH_BYTES:
        raise ImportPayloadError("BATCH_PAYLOAD_TOO_LARGE")


def validate_batch(items: list[ImportItem]) -> None:
    _validate_batch_envelope(items)
    for item in items:
        _validate_item(item)


def _validate_item(item: ImportItem) -> None:
    if item.sequence < 1:
        raise ImportPayloadError("INVALID_INPUT_SEQUENCE")
    if item.input_type not in SUPPORTED_INPUT_TYPES:
        raise ImportPayloadError("UNSUPPORTED_INPUT_TYPE")
    if (
        not item.origin_namespace
        or len(item.origin_namespace) > 64
        or not item.origin_id
        or len(item.origin_id) > 128
    ):
        raise ImportPayloadError("MISSING_ORIGIN_IDENTITY")
    _walk(item.payload)

    if item.input_type == "EvidenceRequirement":
        _validate_evidence_requirement_payload(item.payload)
    elif item.input_type == "AssessmentProcedure":
        _validate_assessment_procedure_payload(item.payload)


def preview_batch(items: list[ImportItem], context: PreviewContext) -> list[PreviewResult]:
    """Evaluate conservative outcomes without a Session or persistence side effects."""
    _validate_batch_envelope(items)
    results: list[PreviewResult] = []
    for item in items:
        try:
            _validate_item(item)
            disposition, reason = _preview_item(item, context)
        except ImportPayloadError as exc:
            disposition, reason = ImportDisposition.REJECTED, str(exc)
        results.append(
            PreviewResult(
                sequence=item.sequence,
                origin_namespace=item.origin_namespace,
                origin_id=item.origin_id,
                disposition=disposition,
                reason_code=reason,
                input_fingerprint=item.fingerprint,
            )
        )
    return results


def _preview_item(item: ImportItem, context: PreviewContext) -> tuple[ImportDisposition, str]:
    if item.input_type in DEFERRED_INPUT_TYPES:
        return ImportDisposition.DEFERRED_BY_SCOPE, "SCOPE_CHILD_DEFERRED"
    if item.input_type in {"EvidenceRequirement", "AssessmentProcedure"}:
        return ImportDisposition.IMPORTED_DRAFT, "WOULD_IMPORT_DRAFT"
    source_key = item.payload.get("source_version_id")
    if item.input_type in {"Requirement", "Mapping"}:
        if not isinstance(source_key, str) or source_key not in context.available_sources:
            return ImportDisposition.NEEDS_SOURCE, "SOURCE_UNAVAILABLE"
        if item.origin_id not in context.permitted_origins:
            return ImportDisposition.NEEDS_PERMISSION, "PERMISSION_DENIED_REQUIRED_USE"
    if item.input_type in {"Mapping", "PackMembership"}:
        dependencies = item.payload.get("dependencies", [])
        if not isinstance(dependencies, list) or not all(
            isinstance(dep, str) and dep in context.resolvable_dependencies for dep in dependencies
        ):
            disposition = (
                ImportDisposition.NEEDS_MAPPING_REVIEW
                if item.input_type == "Mapping"
                else ImportDisposition.NEEDS_DEPENDENCY
            )
            reason = (
                "MAPPING_ENDPOINT_UNRESOLVED"
                if item.input_type == "Mapping"
                else "DEPENDENCY_UNRESOLVED"
            )
            return disposition, reason
    return ImportDisposition.IMPORTED_DRAFT, "WOULD_IMPORT_DRAFT"


def load_fixture(fixture_name: str, *, validate: bool = False) -> list[ImportItem]:
    """Load canonical fixture JSON into validated ImportItem list."""
    candidates = [
        Path(__file__).parents[3] / "tests" / "fixtures" / "catalog_v2_import" / fixture_name,
        Path(__file__).parents[2] / "tests" / "fixtures" / "catalog_v2_import" / fixture_name,
    ]
    target_path = None
    for cand in candidates:
        if cand.exists():
            target_path = cand
            break
    if target_path is None:
        raise FileNotFoundError(f"Fixture {fixture_name} not found in expected locations")

    raw_data = json.loads(target_path.read_text(encoding="utf-8"))
    items = [
        ImportItem(
            sequence=d["sequence"],
            input_type=d["input_type"],
            origin_namespace=d["origin_namespace"],
            origin_id=d["origin_id"],
            payload=d["payload"],
        )
        for d in raw_data
    ]
    if validate:
        validate_batch(items)
    return items
