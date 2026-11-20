"""Controlled internal Draft catalog service for assurance content aggregates."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogCapability,
    CatalogConflictError,
    CatalogError,
    CatalogNotFoundError,
    CatalogSecurityError,
    CatalogValidationError,
    verify_catalog_actor,
)
from conformly.catalog_v2.audit import (
    DeniedAuditSink,
    append_catalog_audit_event,
    check_or_record_mutation_receipt,
    record_catalog_event_intent,
)
from conformly.catalog_v2.digest import (
    DIGEST_SCHEMA_ASSURANCE_V1,
    canonical_json,
    compute_assessment_procedure_version_digest,
    compute_evidence_requirement_version_digest,
)
from conformly.catalog_v2.models import (
    CatalogAssessmentProcedureEvidenceRequirement,
    CatalogAssessmentProcedureStep,
    CatalogAssessmentProcedureVersion,
    CatalogControlVersion,
    CatalogEvidenceRequirementArtifactType,
    CatalogEvidenceRequirementMetadataKey,
    CatalogEvidenceRequirementVersion,
)
from conformly.catalog_v2.service import CatalogDraftService

logger = logging.getLogger(__name__)

MAX_CANONICAL_PAYLOAD_BYTES = 262144

ER_KEY_PATTERN = re.compile(r"^ER-[A-Z0-9_-]{3,61}$")
AP_KEY_PATTERN = re.compile(r"^AP-[A-Z0-9_-]{3,61}$")
METADATA_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

KNOWN_ER_FREQUENCIES = {
    "continuous",
    "event_driven",
    "monthly",
    "quarterly",
    "semiannual",
    "annual",
    "custom",
}
KNOWN_ER_SCOPE_STATES = {"All", "Conditional"}
KNOWN_ASSURANCE_PURPOSES = {
    "design",
    "implementation",
    "operating_effectiveness",
    "combined",
}
KNOWN_VALIDITY_RULES = {
    "point_in_time",
    "period_coverage",
    "continuous",
    "event_driven",
}
KNOWN_ARTIFACT_TYPES = {
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
KNOWN_STEP_KINDS = {
    "inspect",
    "inquire",
    "observe",
    "reperform",
    "analyze",
}


@dataclass(frozen=True)
class EvidenceRequirementArtifactTypeSnapshot:
    sequence: int
    artifact_type: str


@dataclass(frozen=True)
class EvidenceRequirementMetadataKeySnapshot:
    sequence: int
    metadata_key: str


@dataclass(frozen=True)
class EvidenceRequirementVersionSnapshot:
    id: UUID
    control_version_id: UUID
    control_id: UUID
    requirement_key: str
    sequence: int
    title: str
    frequency: str
    custom_frequency: str | None
    scope_state: str
    scope_guidance: str | None
    assurance_purpose: str
    validity_rule: str
    max_age_days: int | None
    missing_data_behavior: str
    guidance: str | None
    status: str
    content_digest: bytes
    digest_schema: str
    artifact_types: tuple[EvidenceRequirementArtifactTypeSnapshot, ...]
    required_metadata: tuple[EvidenceRequirementMetadataKeySnapshot, ...]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AssessmentProcedureStepSnapshot:
    sequence: int
    step_kind: str
    instruction: str
    expected_output: str | None


@dataclass(frozen=True)
class AssessmentProcedureEvidenceRequirementSnapshot:
    sequence: int
    evidence_requirement_version_id: UUID
    content_digest: bytes


@dataclass(frozen=True)
class AssessmentProcedureVersionSnapshot:
    id: UUID
    control_version_id: UUID
    control_id: UUID
    procedure_key: str
    sequence: int
    title: str
    objective: str
    sample_guidance: str | None
    scope_guidance: str | None
    decision_guidance: str
    assessor_qualifications: str | None
    missing_data_behavior: str
    status: str
    content_digest: bytes
    digest_schema: str
    steps: tuple[AssessmentProcedureStepSnapshot, ...]
    evidence_requirements: tuple[AssessmentProcedureEvidenceRequirementSnapshot, ...]
    created_at: datetime
    updated_at: datetime


def _check_string_field(
    val: Any,
    field_name: str,
    min_len: int,
    max_len: int,
    nullable: bool = False,
) -> str | None:
    if val is None:
        if nullable:
            return None
        raise CatalogValidationError(f"Field '{field_name}' cannot be None")
    if not isinstance(val, str):
        raise CatalogValidationError(
            f"Field '{field_name}' must be a string, got {type(val).__name__}"
        )
    if val != val.strip():
        raise CatalogValidationError(
            f"Field '{field_name}' must not contain leading or trailing whitespace"
        )
    if len(val) == 0:
        if nullable:
            raise CatalogValidationError(
                f"Field '{field_name}' cannot be empty string; use None for absent optional text"
            )
        raise CatalogValidationError(f"Field '{field_name}' cannot be blank")
    if not (min_len <= len(val) <= max_len):
        raise CatalogValidationError(
            f"Field '{field_name}' length must be between {min_len} and {max_len}, got {len(val)}"
        )
    return val


def _normalize_digest(d: Any, field_name: str) -> bytes:
    if isinstance(d, (bytes, bytearray)):
        b = bytes(d)
        if len(b) != 32:
            raise CatalogValidationError(
                f"Field '{field_name}' must be exactly 32 bytes, got {len(b)}"
            )
        return b
    if isinstance(d, str):
        if len(d) != 64:
            raise CatalogValidationError(
                f"Field '{field_name}' hex string must be 64 characters (32 bytes), got {len(d)}"
            )
        try:
            b = bytes.fromhex(d)
            if len(b) != 32:
                raise CatalogValidationError(f"Field '{field_name}' must be 32 bytes")
            return b
        except ValueError as e:
            raise CatalogValidationError(f"Field '{field_name}' invalid hex: {e}") from e
    raise CatalogValidationError(
        f"Field '{field_name}' must be bytes or hex string, got {type(d).__name__}"
    )


class CatalogAssuranceDraftService(CatalogDraftService):
    """Internal platform-only service for managing Draft assurance content aggregates."""

    def __init__(
        self,
        session: Session,
        denied_audit_sink: DeniedAuditSink | None = None,
    ) -> None:
        super().__init__(session=session, denied_audit_sink=denied_audit_sink)

    # -------------------------------------------------------------------------
    # Evidence Requirements
    # -------------------------------------------------------------------------

    def create_evidence_requirement_version(
        self,
        context: CatalogActorContext,
        request_key: str,
        control_version_id: UUID,
        expected_control_digest: bytes | str,
        requirement_key: str,
        title: str,
        frequency: str,
        custom_frequency: str | None,
        scope_state: str,
        scope_guidance: str | None,
        assurance_purpose: str,
        validity_rule: str,
        max_age_days: int | None,
        guidance: str | None,
        artifact_types: list[Any],
        required_metadata: list[Any],
    ) -> EvidenceRequirementVersionSnapshot:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "create_evidence_requirement_version",
                type(e).__name__,
                request_key,
                resource_type="CatalogControlVersion",
                resource_id=control_version_id,
            )
            raise

        # 1. Validate fields and boundaries
        ctrl_digest_bytes = _normalize_digest(expected_control_digest, "expected_control_digest")
        _check_string_field(request_key, "request_key", 1, 128)
        _check_string_field(requirement_key, "requirement_key", 6, 64)
        if not ER_KEY_PATTERN.match(requirement_key):
            raise CatalogValidationError(
                f"requirement_key '{requirement_key}' does not match format '^ER-[A-Z0-9_-]{{3,61}}$'"
            )
        _check_string_field(title, "title", 1, 512)

        if frequency not in KNOWN_ER_FREQUENCIES:
            raise CatalogValidationError(f"Invalid frequency '{frequency}'")
        if frequency == "custom":
            _check_string_field(custom_frequency, "custom_frequency", 1, 256, nullable=False)
        else:
            if custom_frequency is not None:
                raise CatalogValidationError(
                    f"custom_frequency must be None when frequency is '{frequency}'"
                )

        if scope_state not in KNOWN_ER_SCOPE_STATES:
            raise CatalogValidationError(f"Invalid scope_state '{scope_state}'")
        if scope_state == "Conditional":
            _check_string_field(scope_guidance, "scope_guidance", 1, 2048, nullable=False)
        else:
            if scope_guidance is not None:
                raise CatalogValidationError(
                    f"scope_guidance must be None when scope_state is '{scope_state}'"
                )

        if assurance_purpose not in KNOWN_ASSURANCE_PURPOSES:
            raise CatalogValidationError(f"Invalid assurance_purpose '{assurance_purpose}'")

        if validity_rule not in KNOWN_VALIDITY_RULES:
            raise CatalogValidationError(f"Invalid validity_rule '{validity_rule}'")
        if validity_rule == "point_in_time":
            if (
                max_age_days is None
                or isinstance(max_age_days, bool)
                or not isinstance(max_age_days, int)
            ):
                raise CatalogValidationError(
                    "max_age_days must be an integer between 1 and 3660 when validity_rule is 'point_in_time'"
                )
            if not (1 <= max_age_days <= 3660):
                raise CatalogValidationError(
                    f"max_age_days must be between 1 and 3660, got {max_age_days}"
                )
        else:
            if max_age_days is not None:
                raise CatalogValidationError(
                    f"max_age_days must be None when validity_rule is '{validity_rule}'"
                )

        _check_string_field(guidance, "guidance", 1, 4096, nullable=True)

        # Artifact types (1..16 distinct)
        if not isinstance(artifact_types, list):
            raise CatalogValidationError("artifact_types must be a list")
        if not (1 <= len(artifact_types) <= 16):
            raise CatalogValidationError(
                f"artifact_types count must be between 1 and 16, got {len(artifact_types)}"
            )
        ALLOWED_ART_KEYS = {"artifact_type", "sequence"}
        parsed_art_types: list[dict[str, Any]] = []
        seen_art_types: set[str] = set()
        for idx, item in enumerate(artifact_types, start=1):
            if isinstance(item, dict):
                extra_art_keys = set(item.keys()) - ALLOWED_ART_KEYS
                if extra_art_keys:
                    raise CatalogValidationError(
                        f"artifact_types[{idx}] contains unrecognized extra fields: {sorted(extra_art_keys)}"
                    )
                if "sequence" in item and item["sequence"] is not None and item["sequence"] != idx:
                    raise CatalogValidationError(
                        f"artifact_types[{idx}] sequence mismatch: expected {idx}, got {item['sequence']}"
                    )
                art_type = item.get("artifact_type")
            elif isinstance(item, str):
                art_type = item
            else:
                raise CatalogValidationError(f"artifact_types[{idx}] must be a string or dict")
            _check_string_field(art_type, f"artifact_types[{idx}]", 1, 32)
            assert isinstance(art_type, str)
            if art_type not in KNOWN_ARTIFACT_TYPES:
                raise CatalogValidationError(f"Invalid artifact_type '{art_type}'")
            if art_type in seen_art_types:
                raise CatalogValidationError(f"Duplicate artifact_type '{art_type}' in requirement")
            seen_art_types.add(art_type)
            parsed_art_types.append({"sequence": idx, "artifact_type": art_type})

        # Required metadata (0..32 distinct keys)
        if not isinstance(required_metadata, list):
            raise CatalogValidationError("required_metadata must be a list")
        if not (0 <= len(required_metadata) <= 32):
            raise CatalogValidationError(
                f"required_metadata count must be between 0 and 32, got {len(required_metadata)}"
            )
        ALLOWED_META_KEYS = {"metadata_key", "sequence"}
        parsed_meta_keys: list[dict[str, Any]] = []
        seen_meta_keys: set[str] = set()
        for idx, item in enumerate(required_metadata, start=1):
            if isinstance(item, dict):
                extra_meta_keys = set(item.keys()) - ALLOWED_META_KEYS
                if extra_meta_keys:
                    raise CatalogValidationError(
                        f"required_metadata[{idx}] contains unrecognized extra fields: {sorted(extra_meta_keys)}"
                    )
                if "sequence" in item and item["sequence"] is not None and item["sequence"] != idx:
                    raise CatalogValidationError(
                        f"required_metadata[{idx}] sequence mismatch: expected {idx}, got {item['sequence']}"
                    )
                m_key = item.get("metadata_key")
            elif isinstance(item, str):
                m_key = item
            else:
                raise CatalogValidationError(f"required_metadata[{idx}] must be a string or dict")
            _check_string_field(m_key, f"required_metadata[{idx}]", 1, 64)
            assert isinstance(m_key, str)
            if not METADATA_KEY_PATTERN.match(m_key):
                raise CatalogValidationError(
                    f"required_metadata key '{m_key}' does not match format '^[a-z][a-z0-9_]{{0,63}}$'"
                )
            if m_key in seen_meta_keys:
                raise CatalogValidationError(f"Duplicate metadata_key '{m_key}' in requirement")
            seen_meta_keys.add(m_key)
            parsed_meta_keys.append({"sequence": idx, "metadata_key": m_key})

        # Canonical request payload size limit check
        req_data = {
            "artifact_types": parsed_art_types,
            "assurance_purpose": assurance_purpose,
            "control_version_id": str(control_version_id),
            "custom_frequency": custom_frequency,
            "expected_control_digest": ctrl_digest_bytes.hex(),
            "frequency": frequency,
            "guidance": guidance,
            "max_age_days": max_age_days,
            "required_metadata": parsed_meta_keys,
            "requirement_key": requirement_key,
            "scope_guidance": scope_guidance,
            "scope_state": scope_state,
            "title": title,
            "validity_rule": validity_rule,
        }
        encoded_payload = canonical_json(req_data).encode("utf-8")
        if len(encoded_payload) > MAX_CANONICAL_PAYLOAD_BYTES:
            raise CatalogValidationError(
                f"Request payload exceeds {MAX_CANONICAL_PAYLOAD_BYTES} canonical UTF-8 bytes (got {len(encoded_payload)})"
            )

        # 2. Lock and verify parent ControlVersion
        stmt_cv = (
            select(CatalogControlVersion)
            .where(CatalogControlVersion.id == control_version_id)
            .with_for_update()
        )
        cv = self.session.execute(stmt_cv).scalar_one_or_none()
        if cv is None:
            raise CatalogNotFoundError(f"Parent ControlVersion '{control_version_id}' not found")
        if cv.status != "Draft":
            raise CatalogValidationError(
                f"Parent ControlVersion '{control_version_id}' status must be Draft, got '{cv.status}'"
            )
        if bytes(cv.content_digest) != ctrl_digest_bytes:
            raise CatalogConflictError("Parent ControlVersion content digest mismatch")

        # 3. Mutation receipt and atomic aggregate write
        def _do_write() -> tuple[UUID, str, int, bytes]:
            max_seq = self.session.execute(
                select(
                    func.coalesce(func.max(CatalogEvidenceRequirementVersion.sequence), 0)
                ).where(CatalogEvidenceRequirementVersion.control_version_id == control_version_id)
            ).scalar_one()
            next_seq = int(max_seq) + 1

            digest = compute_evidence_requirement_version_digest(
                control_version_id=control_version_id,
                control_version_digest=cv.content_digest,
                requirement_key=requirement_key,
                sequence=next_seq,
                title=title,
                frequency=frequency,
                custom_frequency=custom_frequency,
                scope_state=scope_state,
                scope_guidance=scope_guidance,
                assurance_purpose=assurance_purpose,
                validity_rule=validity_rule,
                max_age_days=max_age_days,
                guidance=guidance,
                artifact_types=parsed_art_types,
                required_metadata=parsed_meta_keys,
                missing_data_behavior="requires_human_review",
            )

            er = CatalogEvidenceRequirementVersion(
                id=uuid4(),
                control_version_id=control_version_id,
                control_id=cv.control_id,
                requirement_key=requirement_key,
                sequence=next_seq,
                title=title,
                frequency=frequency,
                custom_frequency=custom_frequency,
                scope_state=scope_state,
                scope_guidance=scope_guidance,
                assurance_purpose=assurance_purpose,
                validity_rule=validity_rule,
                max_age_days=max_age_days,
                missing_data_behavior="requires_human_review",
                guidance=guidance,
                status="Draft",
                content_digest=digest,
                digest_schema=DIGEST_SCHEMA_ASSURANCE_V1,
            )
            self.session.add(er)
            self.session.flush()

            for item in parsed_art_types:
                self.session.add(
                    CatalogEvidenceRequirementArtifactType(
                        id=uuid4(),
                        evidence_requirement_version_id=er.id,
                        control_version_id=control_version_id,
                        sequence=item["sequence"],
                        artifact_type=item["artifact_type"],
                    )
                )

            for item in parsed_meta_keys:
                self.session.add(
                    CatalogEvidenceRequirementMetadataKey(
                        id=uuid4(),
                        evidence_requirement_version_id=er.id,
                        control_version_id=control_version_id,
                        sequence=item["sequence"],
                        metadata_key=item["metadata_key"],
                    )
                )

            self.session.flush()
            return (er.id, "CatalogEvidenceRequirementVersion", next_seq, digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "create_evidence_requirement_version",
            request_key,
            req_data,
            _do_write,
            db_time,
        )

        if is_retry:
            if receipt.result_type != "CatalogEvidenceRequirementVersion":
                raise CatalogConflictError(
                    f"Receipt result_type mismatch: expected CatalogEvidenceRequirementVersion, got {receipt.result_type}"
                )
            snapshot = self._build_er_snapshot(
                receipt.result_id, expected_parent_id=control_version_id
            )
            if snapshot.sequence != receipt.result_revision:
                raise CatalogConflictError(
                    f"Receipt sequence mismatch: expected {receipt.result_revision}, got {snapshot.sequence}"
                )
            if snapshot.content_digest != bytes(receipt.result_digest):
                raise CatalogConflictError("Receipt digest mismatch against returned aggregate")
            return snapshot

        # 4. Atomic Event intent and audit log
        record_catalog_event_intent(
            self.session,
            request_key,
            "evidence_requirement_version.created",
            receipt.result_id,
            "CatalogEvidenceRequirementVersion",
            receipt.result_revision,
            receipt.result_digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "evidence_requirement_version.created",
            "CatalogEvidenceRequirementVersion",
            receipt.result_id,
            request_key,
            "Success",
            {
                "artifact_type_count": len(parsed_art_types),
                "control_version_id": str(control_version_id),
                "metadata_key_count": len(parsed_meta_keys),
                "requirement_key": requirement_key,
                "sequence": receipt.result_revision,
            },
            db_time,
        )

        return self._build_er_snapshot(receipt.result_id, expected_parent_id=control_version_id)

    # -------------------------------------------------------------------------
    # Assessment Procedures
    # -------------------------------------------------------------------------

    def create_assessment_procedure_version(
        self,
        context: CatalogActorContext,
        request_key: str,
        control_version_id: UUID,
        expected_control_digest: bytes | str,
        procedure_key: str,
        title: str,
        objective: str,
        sample_guidance: str | None,
        scope_guidance: str | None,
        decision_guidance: str,
        assessor_qualifications: str | None,
        steps: list[Any],
        evidence_requirements: list[Any],
    ) -> AssessmentProcedureVersionSnapshot:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "create_assessment_procedure_version",
                type(e).__name__,
                request_key,
                resource_type="CatalogControlVersion",
                resource_id=control_version_id,
            )
            raise

        # 1. Validate fields and boundaries
        ctrl_digest_bytes = _normalize_digest(expected_control_digest, "expected_control_digest")
        _check_string_field(request_key, "request_key", 1, 128)
        _check_string_field(procedure_key, "procedure_key", 6, 64)
        if not AP_KEY_PATTERN.match(procedure_key):
            raise CatalogValidationError(
                f"procedure_key '{procedure_key}' does not match format '^AP-[A-Z0-9_-]{{3,61}}$'"
            )
        _check_string_field(title, "title", 1, 512)
        _check_string_field(objective, "objective", 1, 4096)
        _check_string_field(sample_guidance, "sample_guidance", 1, 2048, nullable=True)
        _check_string_field(scope_guidance, "scope_guidance", 1, 2048, nullable=True)
        _check_string_field(decision_guidance, "decision_guidance", 1, 4096)
        _check_string_field(
            assessor_qualifications, "assessor_qualifications", 1, 2048, nullable=True
        )

        # Steps (1..50 ordered)
        if not isinstance(steps, list):
            raise CatalogValidationError("steps must be a list")
        if not (1 <= len(steps) <= 50):
            raise CatalogValidationError(f"steps count must be between 1 and 50, got {len(steps)}")
        ALLOWED_STEP_KEYS = {"step_kind", "instruction", "expected_output", "sequence"}
        parsed_steps: list[dict[str, Any]] = []
        for idx, item in enumerate(steps, start=1):
            if not isinstance(item, dict):
                raise CatalogValidationError(f"steps[{idx}] must be a dict")
            extra_step_keys = set(item.keys()) - ALLOWED_STEP_KEYS
            if extra_step_keys:
                raise CatalogValidationError(
                    f"steps[{idx}] contains unrecognized extra fields: {sorted(extra_step_keys)}"
                )
            if "sequence" in item and item["sequence"] is not None and item["sequence"] != idx:
                raise CatalogValidationError(
                    f"steps[{idx}] sequence mismatch: expected {idx}, got {item['sequence']}"
                )
            s_kind = item.get("step_kind")
            s_instruction = item.get("instruction")
            s_expected = item.get("expected_output")

            _check_string_field(s_kind, f"steps[{idx}].step_kind", 1, 32)
            assert isinstance(s_kind, str)
            if s_kind not in KNOWN_STEP_KINDS:
                raise CatalogValidationError(f"Invalid step_kind '{s_kind}' at step {idx}")
            _check_string_field(s_instruction, f"steps[{idx}].instruction", 1, 4096)
            _check_string_field(s_expected, f"steps[{idx}].expected_output", 1, 2048, nullable=True)

            parsed_steps.append(
                {
                    "expected_output": s_expected,
                    "instruction": s_instruction,
                    "sequence": idx,
                    "step_kind": s_kind,
                }
            )

        # Evidence requirements links (0..32 unique)
        if not isinstance(evidence_requirements, list):
            raise CatalogValidationError("evidence_requirements must be a list")
        if not (0 <= len(evidence_requirements) <= 32):
            raise CatalogValidationError(
                f"evidence_requirements count must be between 0 and 32, got {len(evidence_requirements)}"
            )

        ALLOWED_LINK_KEYS = {"id", "evidence_requirement_version_id", "content_digest", "sequence"}
        parsed_links_input: list[dict[str, Any]] = []
        seen_er_ids: set[UUID] = set()
        for idx, item in enumerate(evidence_requirements, start=1):
            if not isinstance(item, dict):
                raise CatalogValidationError(f"evidence_requirements[{idx}] must be a dict")
            extra_link_keys = set(item.keys()) - ALLOWED_LINK_KEYS
            if extra_link_keys:
                raise CatalogValidationError(
                    f"evidence_requirements[{idx}] contains unrecognized extra fields: {sorted(extra_link_keys)}"
                )
            if "id" in item and "evidence_requirement_version_id" in item:
                if (
                    str(item["id"]).strip().lower()
                    != str(item["evidence_requirement_version_id"]).strip().lower()
                ):
                    raise CatalogValidationError(
                        f"evidence_requirements[{idx}] conflicting id aliases: 'id' and 'evidence_requirement_version_id' do not match"
                    )
            raw_id = item.get("id") if "id" in item else item.get("evidence_requirement_version_id")
            if raw_id is None:
                raise CatalogValidationError(f"evidence_requirements[{idx}] missing id")
            if "sequence" in item and item["sequence"] is not None and item["sequence"] != idx:
                raise CatalogValidationError(
                    f"evidence_requirements[{idx}] sequence mismatch: expected {idx}, got {item['sequence']}"
                )
            if isinstance(raw_id, str):
                try:
                    er_id = UUID(raw_id)
                except ValueError as e:
                    raise CatalogValidationError(
                        f"Invalid UUID in evidence_requirements[{idx}]: {e}"
                    ) from e
            elif isinstance(raw_id, UUID):
                er_id = raw_id
            else:
                raise CatalogValidationError(f"Invalid UUID type in evidence_requirements[{idx}]")

            if er_id in seen_er_ids:
                raise CatalogValidationError(
                    f"Duplicate evidence requirement link '{er_id}' in procedure"
                )
            seen_er_ids.add(er_id)

            raw_d = item.get("content_digest")
            if raw_d is None:
                raise CatalogValidationError(f"evidence_requirements[{idx}] missing content_digest")
            er_exp_digest = _normalize_digest(raw_d, f"evidence_requirements[{idx}].content_digest")

            parsed_links_input.append(
                {
                    "content_digest": er_exp_digest,
                    "id": er_id,
                    "sequence": idx,
                }
            )

        # Canonical request payload size limit check
        req_data = {
            "assessor_qualifications": assessor_qualifications,
            "control_version_id": str(control_version_id),
            "decision_guidance": decision_guidance,
            "evidence_requirements": [
                {
                    "content_digest": link["content_digest"].hex(),
                    "id": str(link["id"]),
                    "sequence": link["sequence"],
                }
                for link in parsed_links_input
            ],
            "expected_control_digest": ctrl_digest_bytes.hex(),
            "objective": objective,
            "procedure_key": procedure_key,
            "sample_guidance": sample_guidance,
            "scope_guidance": scope_guidance,
            "steps": parsed_steps,
            "title": title,
        }
        encoded_payload = canonical_json(req_data).encode("utf-8")
        if len(encoded_payload) > MAX_CANONICAL_PAYLOAD_BYTES:
            raise CatalogValidationError(
                f"Request payload exceeds {MAX_CANONICAL_PAYLOAD_BYTES} canonical UTF-8 bytes (got {len(encoded_payload)})"
            )

        # 2. Lock and verify parent ControlVersion
        stmt_cv = (
            select(CatalogControlVersion)
            .where(CatalogControlVersion.id == control_version_id)
            .with_for_update()
        )
        cv = self.session.execute(stmt_cv).scalar_one_or_none()
        if cv is None:
            raise CatalogNotFoundError(f"Parent ControlVersion '{control_version_id}' not found")
        if cv.status != "Draft":
            raise CatalogValidationError(
                f"Parent ControlVersion '{control_version_id}' status must be Draft, got '{cv.status}'"
            )
        if bytes(cv.content_digest) != ctrl_digest_bytes:
            raise CatalogConflictError("Parent ControlVersion content digest mismatch")

        # 3. Verify every linked Evidence Requirement (same exact ControlVersion, Draft, recompute aggregate digest)
        for link in parsed_links_input:
            er_id = link["id"]
            er = self.session.get(CatalogEvidenceRequirementVersion, er_id)
            if er is None:
                raise CatalogNotFoundError(f"Linked EvidenceRequirementVersion '{er_id}' not found")
            if er.control_version_id != control_version_id:
                raise CatalogValidationError(
                    f"Linked EvidenceRequirementVersion '{er_id}' parent '{er.control_version_id}' does not match procedure parent '{control_version_id}'"
                )
            if er.status != "Draft":
                raise CatalogValidationError(
                    f"Linked EvidenceRequirementVersion '{er_id}' status must be Draft, got '{er.status}'"
                )

            # Recompute linked ER aggregate to verify integrity
            recomputed_digest = self._recompute_er_digest(er, cv.content_digest)
            if bytes(er.content_digest) != recomputed_digest:
                raise CatalogSecurityError(
                    f"Stored EvidenceRequirementVersion '{er_id}' content digest corrupt or altered"
                )
            if bytes(er.content_digest) != link["content_digest"]:
                raise CatalogConflictError(
                    f"Expected digest mismatch for linked EvidenceRequirementVersion '{er_id}'"
                )

        # 4. Mutation receipt and atomic aggregate write
        def _do_write() -> tuple[UUID, str, int, bytes]:
            max_seq = self.session.execute(
                select(
                    func.coalesce(func.max(CatalogAssessmentProcedureVersion.sequence), 0)
                ).where(CatalogAssessmentProcedureVersion.control_version_id == control_version_id)
            ).scalar_one()
            next_seq = int(max_seq) + 1

            digest = compute_assessment_procedure_version_digest(
                control_version_id=control_version_id,
                control_version_digest=cv.content_digest,
                procedure_key=procedure_key,
                sequence=next_seq,
                title=title,
                objective=objective,
                sample_guidance=sample_guidance,
                scope_guidance=scope_guidance,
                decision_guidance=decision_guidance,
                assessor_qualifications=assessor_qualifications,
                steps=parsed_steps,
                evidence_requirements=parsed_links_input,
                missing_data_behavior="requires_human_review",
            )

            ap = CatalogAssessmentProcedureVersion(
                id=uuid4(),
                control_version_id=control_version_id,
                control_id=cv.control_id,
                procedure_key=procedure_key,
                sequence=next_seq,
                title=title,
                objective=objective,
                sample_guidance=sample_guidance,
                scope_guidance=scope_guidance,
                decision_guidance=decision_guidance,
                assessor_qualifications=assessor_qualifications,
                missing_data_behavior="requires_human_review",
                status="Draft",
                content_digest=digest,
                digest_schema=DIGEST_SCHEMA_ASSURANCE_V1,
            )
            self.session.add(ap)
            self.session.flush()

            for s in parsed_steps:
                self.session.add(
                    CatalogAssessmentProcedureStep(
                        id=uuid4(),
                        assessment_procedure_version_id=ap.id,
                        control_version_id=control_version_id,
                        sequence=s["sequence"],
                        step_kind=s["step_kind"],
                        instruction=s["instruction"],
                        expected_output=s["expected_output"],
                    )
                )

            for link in parsed_links_input:
                self.session.add(
                    CatalogAssessmentProcedureEvidenceRequirement(
                        id=uuid4(),
                        assessment_procedure_version_id=ap.id,
                        evidence_requirement_version_id=link["id"],
                        control_version_id=control_version_id,
                        sequence=link["sequence"],
                    )
                )

            self.session.flush()
            return (ap.id, "CatalogAssessmentProcedureVersion", next_seq, digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "create_assessment_procedure_version",
            request_key,
            req_data,
            _do_write,
            db_time,
        )

        if is_retry:
            if receipt.result_type != "CatalogAssessmentProcedureVersion":
                raise CatalogConflictError(
                    f"Receipt result_type mismatch: expected CatalogAssessmentProcedureVersion, got {receipt.result_type}"
                )
            snapshot = self._build_ap_snapshot(
                receipt.result_id, expected_parent_id=control_version_id
            )
            if snapshot.sequence != receipt.result_revision:
                raise CatalogConflictError(
                    f"Receipt sequence mismatch: expected {receipt.result_revision}, got {snapshot.sequence}"
                )
            if snapshot.content_digest != bytes(receipt.result_digest):
                raise CatalogConflictError("Receipt digest mismatch against returned aggregate")
            return snapshot

        # 5. Atomic Event intent and audit log
        record_catalog_event_intent(
            self.session,
            request_key,
            "assessment_procedure_version.created",
            receipt.result_id,
            "CatalogAssessmentProcedureVersion",
            receipt.result_revision,
            receipt.result_digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "assessment_procedure_version.created",
            "CatalogAssessmentProcedureVersion",
            receipt.result_id,
            request_key,
            "Success",
            {
                "control_version_id": str(control_version_id),
                "evidence_requirement_count": len(parsed_links_input),
                "procedure_key": procedure_key,
                "sequence": receipt.result_revision,
                "step_count": len(parsed_steps),
            },
            db_time,
        )

        return self._build_ap_snapshot(receipt.result_id, expected_parent_id=control_version_id)

    # -------------------------------------------------------------------------
    # Get and List Queries
    # -------------------------------------------------------------------------

    def get_evidence_requirement_version(
        self,
        context: CatalogActorContext,
        version_id: UUID,
    ) -> EvidenceRequirementVersionSnapshot:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "get_evidence_requirement_version",
                type(e).__name__,
                request_key="",
                resource_type="CatalogEvidenceRequirementVersion",
                resource_id=version_id,
            )
            raise

        return self._build_er_snapshot(version_id)

    def get_assessment_procedure_version(
        self,
        context: CatalogActorContext,
        version_id: UUID,
    ) -> AssessmentProcedureVersionSnapshot:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "get_assessment_procedure_version",
                type(e).__name__,
                request_key="",
                resource_type="CatalogAssessmentProcedureVersion",
                resource_id=version_id,
            )
            raise

        return self._build_ap_snapshot(version_id)

    def list_evidence_requirement_versions(
        self,
        context: CatalogActorContext,
        control_version_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EvidenceRequirementVersionSnapshot]:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "list_evidence_requirement_versions",
                type(e).__name__,
                request_key="",
                resource_type="CatalogControlVersion",
                resource_id=control_version_id,
            )
            raise

        if offset < 0:
            raise CatalogValidationError(f"Offset must be nonnegative, got {offset}")
        if not (1 <= limit <= 100):
            raise CatalogValidationError(f"Limit must be between 1 and 100, got {limit}")

        stmt = (
            select(CatalogEvidenceRequirementVersion.id)
            .where(CatalogEvidenceRequirementVersion.control_version_id == control_version_id)
            .order_by(
                CatalogEvidenceRequirementVersion.sequence.asc(),
                CatalogEvidenceRequirementVersion.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        er_ids = self.session.execute(stmt).scalars().all()
        return [
            self._build_er_snapshot(vid, expected_parent_id=control_version_id) for vid in er_ids
        ]

    def list_assessment_procedure_versions(
        self,
        context: CatalogActorContext,
        control_version_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AssessmentProcedureVersionSnapshot]:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "list_assessment_procedure_versions",
                type(e).__name__,
                request_key="",
                resource_type="CatalogControlVersion",
                resource_id=control_version_id,
            )
            raise

        if offset < 0:
            raise CatalogValidationError(f"Offset must be nonnegative, got {offset}")
        if not (1 <= limit <= 100):
            raise CatalogValidationError(f"Limit must be between 1 and 100, got {limit}")

        stmt = (
            select(CatalogAssessmentProcedureVersion.id)
            .where(CatalogAssessmentProcedureVersion.control_version_id == control_version_id)
            .order_by(
                CatalogAssessmentProcedureVersion.sequence.asc(),
                CatalogAssessmentProcedureVersion.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        ap_ids = self.session.execute(stmt).scalars().all()
        return [
            self._build_ap_snapshot(vid, expected_parent_id=control_version_id) for vid in ap_ids
        ]

    # -------------------------------------------------------------------------
    # Internal Snapshot Builders and Recomputation
    # -------------------------------------------------------------------------

    def _recompute_er_digest(
        self, er: CatalogEvidenceRequirementVersion, parent_digest: bytes
    ) -> bytes:
        stmt_arts = (
            select(CatalogEvidenceRequirementArtifactType)
            .where(CatalogEvidenceRequirementArtifactType.evidence_requirement_version_id == er.id)
            .order_by(CatalogEvidenceRequirementArtifactType.sequence.asc())
        )
        art_rows = self.session.execute(stmt_arts).scalars().all()
        if not (1 <= len(art_rows) <= 16):
            raise CatalogSecurityError(
                f"EvidenceRequirementVersion '{er.id}' corrupt aggregate: expected 1..16 artifact types, got {len(art_rows)}"
            )

        stmt_keys = (
            select(CatalogEvidenceRequirementMetadataKey)
            .where(CatalogEvidenceRequirementMetadataKey.evidence_requirement_version_id == er.id)
            .order_by(CatalogEvidenceRequirementMetadataKey.sequence.asc())
        )
        key_rows = self.session.execute(stmt_keys).scalars().all()
        if not (0 <= len(key_rows) <= 32):
            raise CatalogSecurityError(
                f"EvidenceRequirementVersion '{er.id}' corrupt aggregate: expected 0..32 metadata keys, got {len(key_rows)}"
            )

        for expected_seq, a in enumerate(art_rows, start=1):
            if a.sequence != expected_seq:
                raise CatalogSecurityError(
                    f"EvidenceRequirementVersion '{er.id}' artifact sequence broken: expected {expected_seq}, got {a.sequence}"
                )
        for expected_seq, k in enumerate(key_rows, start=1):
            if k.sequence != expected_seq:
                raise CatalogSecurityError(
                    f"EvidenceRequirementVersion '{er.id}' metadata sequence broken: expected {expected_seq}, got {k.sequence}"
                )

        art_payload = [{"artifact_type": a.artifact_type, "sequence": a.sequence} for a in art_rows]
        meta_payload = [{"metadata_key": k.metadata_key, "sequence": k.sequence} for k in key_rows]

        return compute_evidence_requirement_version_digest(
            control_version_id=er.control_version_id,
            control_version_digest=parent_digest,
            requirement_key=er.requirement_key,
            sequence=er.sequence,
            title=er.title,
            frequency=er.frequency,
            custom_frequency=er.custom_frequency,
            scope_state=er.scope_state,
            scope_guidance=er.scope_guidance,
            assurance_purpose=er.assurance_purpose,
            validity_rule=er.validity_rule,
            max_age_days=er.max_age_days,
            guidance=er.guidance,
            artifact_types=art_payload,
            required_metadata=meta_payload,
            missing_data_behavior=er.missing_data_behavior,
        )

    def _build_er_snapshot(
        self, version_id: UUID, expected_parent_id: UUID | None = None
    ) -> EvidenceRequirementVersionSnapshot:
        er = self.session.get(CatalogEvidenceRequirementVersion, version_id)
        if er is None:
            raise CatalogNotFoundError(f"EvidenceRequirementVersion '{version_id}' not found")
        if expected_parent_id is not None and er.control_version_id != expected_parent_id:
            raise CatalogValidationError(
                f"EvidenceRequirementVersion parent mismatch: expected '{expected_parent_id}', got '{er.control_version_id}'"
            )

        cv = self.session.get(CatalogControlVersion, er.control_version_id)
        if cv is None:
            raise CatalogNotFoundError(
                f"Parent ControlVersion '{er.control_version_id}' for requirement '{version_id}' not found"
            )

        stmt_arts = (
            select(CatalogEvidenceRequirementArtifactType)
            .where(CatalogEvidenceRequirementArtifactType.evidence_requirement_version_id == er.id)
            .order_by(CatalogEvidenceRequirementArtifactType.sequence.asc())
        )
        art_rows = self.session.execute(stmt_arts).scalars().all()
        if not (1 <= len(art_rows) <= 16):
            raise CatalogSecurityError(
                f"EvidenceRequirementVersion '{version_id}' corrupt aggregate: expected 1..16 artifact types, got {len(art_rows)}"
            )

        stmt_keys = (
            select(CatalogEvidenceRequirementMetadataKey)
            .where(CatalogEvidenceRequirementMetadataKey.evidence_requirement_version_id == er.id)
            .order_by(CatalogEvidenceRequirementMetadataKey.sequence.asc())
        )
        key_rows = self.session.execute(stmt_keys).scalars().all()
        if not (0 <= len(key_rows) <= 32):
            raise CatalogSecurityError(
                f"EvidenceRequirementVersion '{version_id}' corrupt aggregate: expected 0..32 metadata keys, got {len(key_rows)}"
            )

        for expected_seq, a in enumerate(art_rows, start=1):
            if a.sequence != expected_seq:
                raise CatalogSecurityError(
                    f"EvidenceRequirementVersion '{version_id}' artifact sequence broken: expected {expected_seq}, got {a.sequence}"
                )
        for expected_seq, k in enumerate(key_rows, start=1):
            if k.sequence != expected_seq:
                raise CatalogSecurityError(
                    f"EvidenceRequirementVersion '{version_id}' metadata sequence broken: expected {expected_seq}, got {k.sequence}"
                )

        art_payload = [{"artifact_type": a.artifact_type, "sequence": a.sequence} for a in art_rows]
        meta_payload = [{"metadata_key": k.metadata_key, "sequence": k.sequence} for k in key_rows]

        recomputed = compute_evidence_requirement_version_digest(
            control_version_id=er.control_version_id,
            control_version_digest=cv.content_digest,
            requirement_key=er.requirement_key,
            sequence=er.sequence,
            title=er.title,
            frequency=er.frequency,
            custom_frequency=er.custom_frequency,
            scope_state=er.scope_state,
            scope_guidance=er.scope_guidance,
            assurance_purpose=er.assurance_purpose,
            validity_rule=er.validity_rule,
            max_age_days=er.max_age_days,
            guidance=er.guidance,
            artifact_types=art_payload,
            required_metadata=meta_payload,
            missing_data_behavior=er.missing_data_behavior,
        )
        if bytes(er.content_digest) != recomputed:
            raise CatalogSecurityError(
                f"EvidenceRequirementVersion '{version_id}' stored content digest does not match recomputed aggregate"
            )

        art_snapshots = tuple(
            EvidenceRequirementArtifactTypeSnapshot(
                sequence=a.sequence,
                artifact_type=a.artifact_type,
            )
            for a in art_rows
        )
        meta_snapshots = tuple(
            EvidenceRequirementMetadataKeySnapshot(
                sequence=k.sequence,
                metadata_key=k.metadata_key,
            )
            for k in key_rows
        )

        return EvidenceRequirementVersionSnapshot(
            id=er.id,
            control_version_id=er.control_version_id,
            control_id=er.control_id,
            requirement_key=er.requirement_key,
            sequence=er.sequence,
            title=er.title,
            frequency=er.frequency,
            custom_frequency=er.custom_frequency,
            scope_state=er.scope_state,
            scope_guidance=er.scope_guidance,
            assurance_purpose=er.assurance_purpose,
            validity_rule=er.validity_rule,
            max_age_days=er.max_age_days,
            missing_data_behavior=er.missing_data_behavior,
            guidance=er.guidance,
            status=er.status,
            content_digest=bytes(er.content_digest),
            digest_schema=er.digest_schema,
            artifact_types=art_snapshots,
            required_metadata=meta_snapshots,
            created_at=er.created_at,
            updated_at=er.updated_at,
        )

    def _build_ap_snapshot(
        self, version_id: UUID, expected_parent_id: UUID | None = None
    ) -> AssessmentProcedureVersionSnapshot:
        ap = self.session.get(CatalogAssessmentProcedureVersion, version_id)
        if ap is None:
            raise CatalogNotFoundError(f"AssessmentProcedureVersion '{version_id}' not found")
        if expected_parent_id is not None and ap.control_version_id != expected_parent_id:
            raise CatalogValidationError(
                f"AssessmentProcedureVersion parent mismatch: expected '{expected_parent_id}', got '{ap.control_version_id}'"
            )

        cv = self.session.get(CatalogControlVersion, ap.control_version_id)
        if cv is None:
            raise CatalogNotFoundError(
                f"Parent ControlVersion '{ap.control_version_id}' for procedure '{version_id}' not found"
            )

        stmt_steps = (
            select(CatalogAssessmentProcedureStep)
            .where(CatalogAssessmentProcedureStep.assessment_procedure_version_id == ap.id)
            .order_by(CatalogAssessmentProcedureStep.sequence.asc())
        )
        step_rows = self.session.execute(stmt_steps).scalars().all()
        if not (1 <= len(step_rows) <= 50):
            raise CatalogSecurityError(
                f"AssessmentProcedureVersion '{version_id}' corrupt aggregate: expected 1..50 steps, got {len(step_rows)}"
            )

        stmt_links = (
            select(CatalogAssessmentProcedureEvidenceRequirement)
            .where(
                CatalogAssessmentProcedureEvidenceRequirement.assessment_procedure_version_id
                == ap.id
            )
            .order_by(CatalogAssessmentProcedureEvidenceRequirement.sequence.asc())
        )
        link_rows = self.session.execute(stmt_links).scalars().all()
        if not (0 <= len(link_rows) <= 32):
            raise CatalogSecurityError(
                f"AssessmentProcedureVersion '{version_id}' corrupt aggregate: expected 0..32 links, got {len(link_rows)}"
            )

        for expected_seq, s in enumerate(step_rows, start=1):
            if s.sequence != expected_seq:
                raise CatalogSecurityError(
                    f"AssessmentProcedureVersion '{version_id}' step sequence broken: expected {expected_seq}, got {s.sequence}"
                )
        for expected_seq, lnk in enumerate(link_rows, start=1):
            if lnk.sequence != expected_seq:
                raise CatalogSecurityError(
                    f"AssessmentProcedureVersion '{version_id}' link sequence broken: expected {expected_seq}, got {lnk.sequence}"
                )

        links_payload: list[dict[str, Any]] = []
        link_snapshots: list[AssessmentProcedureEvidenceRequirementSnapshot] = []
        for lnk in link_rows:
            er = self.session.get(
                CatalogEvidenceRequirementVersion, lnk.evidence_requirement_version_id
            )
            if er is None or er.control_version_id != ap.control_version_id:
                raise CatalogSecurityError(
                    f"Corrupt or cross-control evidence requirement link in procedure '{version_id}'"
                )
            links_payload.append(
                {
                    "content_digest": bytes(er.content_digest),
                    "id": lnk.evidence_requirement_version_id,
                    "sequence": lnk.sequence,
                }
            )
            link_snapshots.append(
                AssessmentProcedureEvidenceRequirementSnapshot(
                    sequence=lnk.sequence,
                    evidence_requirement_version_id=lnk.evidence_requirement_version_id,
                    content_digest=bytes(er.content_digest),
                )
            )

        steps_payload = [
            {
                "expected_output": s.expected_output,
                "instruction": s.instruction,
                "sequence": s.sequence,
                "step_kind": s.step_kind,
            }
            for s in step_rows
        ]

        recomputed = compute_assessment_procedure_version_digest(
            control_version_id=ap.control_version_id,
            control_version_digest=cv.content_digest,
            procedure_key=ap.procedure_key,
            sequence=ap.sequence,
            title=ap.title,
            objective=ap.objective,
            sample_guidance=ap.sample_guidance,
            scope_guidance=ap.scope_guidance,
            decision_guidance=ap.decision_guidance,
            assessor_qualifications=ap.assessor_qualifications,
            steps=steps_payload,
            evidence_requirements=links_payload,
            missing_data_behavior=ap.missing_data_behavior,
        )
        if bytes(ap.content_digest) != recomputed:
            raise CatalogSecurityError(
                f"AssessmentProcedureVersion '{version_id}' stored content digest does not match recomputed aggregate"
            )

        step_snapshots = tuple(
            AssessmentProcedureStepSnapshot(
                sequence=s.sequence,
                step_kind=s.step_kind,
                instruction=s.instruction,
                expected_output=s.expected_output,
            )
            for s in step_rows
        )

        return AssessmentProcedureVersionSnapshot(
            id=ap.id,
            control_version_id=ap.control_version_id,
            control_id=ap.control_id,
            procedure_key=ap.procedure_key,
            sequence=ap.sequence,
            title=ap.title,
            objective=ap.objective,
            sample_guidance=ap.sample_guidance,
            scope_guidance=ap.scope_guidance,
            decision_guidance=ap.decision_guidance,
            assessor_qualifications=ap.assessor_qualifications,
            missing_data_behavior=ap.missing_data_behavior,
            status=ap.status,
            content_digest=bytes(ap.content_digest),
            digest_schema=ap.digest_schema,
            steps=step_snapshots,
            evidence_requirements=tuple(link_snapshots),
            created_at=ap.created_at,
            updated_at=ap.updated_at,
        )
