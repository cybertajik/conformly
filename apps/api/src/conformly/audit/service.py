import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditEvent, AuditOutcome, AuditSeal

SENSITIVE_KEY_PARTS = frozenset(
    {
        "authorization",
        "ciphertext",
        "cookie",
        "credential",
        "dek",
        "key",
        "password",
        "plaintext",
        "secret",
        "token",
    }
)
MAX_METADATA_BYTES = 8_192
SAFE_METADATA_KEYS = frozenset(
    {
        "acknowledgement_id",
        "adoption_id",
        "affected_controls_count",
        "already_revoked",
        "applicability",
        "asset_id",
        "asset_type",
        "assigned_by_user_id",
        "assignee_user_id",
        "assignment_id",
        "attempt",
        "badge_id",
        "badge_type",
        "business_unit_id",
        "cancellation_reason",
        "case_id",
        "case_status",
        "category",
        "certificate_id",
        "certificate_number",
        "check_id",
        "check_result",
        "city",
        "classification",
        "closed_reason",
        "completion_id",
        "content_type",
        "canonical_control_id",
        "control_id",
        "control_identifier",
        "control_status",
        "control_type",
        "count",
        "content_digest",
        "coverage_ledger_id",
        "disposition",
        "evidence_specification_id",
        "requirement_type",
        "source_reference",
        "source_requirement_id",
        "country",
        "course_id",
        "criticality",
        "custom_control_id",
        "days_remaining",
        "deleted_tables_count",
        "deletion_due_at",
        "deletion_id",
        "deletion_proof_hash",
        "deletion_state",
        "delivery_attempts",
        "display_name",
        "due_date",
        "enabled_modules",
        "error_code",
        "evaluator_version",
        "event_id",
        "evidence_id",
        "evidence_ref",
        "evidence_revision_id",
        "expired_count",
        "expires_at",
        "export_id",
        "export_scope",
        "export_until",
        "file_id",
        "filename",
        "files_count",
        "finding_id",
        "framework_id",
        "framework_slug",
        "handler_user_id",
        "impact_level",
        "inherent_score",
        "is_active",
        "is_external_advisor",
        "is_published",
        "is_publicly_visible",
        "is_primary",
        "is_workforce",
        "issued_at",
        "issuer_name",
        "last_reviewed_at",
        "legal_entity_id",
        "legal_hold",
        "link_id",
        "location_id",
        "manifest_hash",
        "manifest_id",
        "mapping_id",
        "mapping_type",
        "max_members",
        "name",
        "new_role",
        "next_review_due_at",
        "notes",
        "overdue_count",
        "overall_score",
        "overlay_id",
        "owner_user_id",
        "plan_code",
        "policy_id",
        "policy_revision_id",
        "portal_id",
        "portal_slug",
        "pre_audit_id",
        "preference_id",
        "previous_applicability",
        "previous_role",
        "previous_status",
        "priority",
        "profile_id",
        "provider",
        "public_case_id",
        "quarantine_reason",
        "reason",
        "record_count",
        "records_count",
        "release_state",
        "remediation_status",
        "report_id",
        "report_type",
        "review_cycle_days",
        "revision_number",
        "revoked_reason",
        "risk_id",
        "role",
        "rule_version",
        "scope_id",
        "score",
        "security_reviewed_at",
        "sender_type",
        "severity",
        "sha256",
        "size_bytes",
        "slug",
        "source_version_id",
        "statement_id",
        "status",
        "storage_objects_purged",
        "strategy",
        "subscription_id",
        "superseded_by_certificate_id",
        "superseding_version_id",
        "suspended_reason",
        "target_version_id",
        "task_id",
        "template_id",
        "template_slug",
        "tenant_approved_at",
        "title",
        "topic",
        "treatment_id",
        "valid_until",
        "vendor_id",
        "verified",
        "version",
        "version_id",
        "version_number",
        "version_string",
        "will_retry",
        "workforce_email",
    }
)


class UnsafeAuditMetadataError(ValueError):
    """Raised when metadata could contain protected or secret material."""


class ImmutableAuditEventError(RuntimeError):
    """Raised when normal ORM usage attempts to mutate an audit event."""


def _validate_metadata(value: Any, path: str = "metadata") -> None:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            normalized_key = str(key).casefold().replace("-", "_")
            if any(part in normalized_key for part in SENSITIVE_KEY_PARTS):
                raise UnsafeAuditMetadataError(f"sensitive audit metadata key at {path}")
            if path == "metadata" and normalized_key not in SAFE_METADATA_KEYS:
                raise UnsafeAuditMetadataError(f"unapproved audit metadata key at {path}")
            if path == "metadata" and isinstance(nested_value, (dict, list)):
                raise UnsafeAuditMetadataError(f"nested audit metadata is not allowed at {path}")
            _validate_metadata(nested_value, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested_value in enumerate(value):
            _validate_metadata(nested_value, f"{path}[{index}]")
    elif value is not None and not isinstance(value, (str, int, float, bool)):
        raise UnsafeAuditMetadataError(f"unsupported audit metadata value at {path}")


def validate_safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    _validate_metadata(metadata)
    if any(isinstance(value, str) and len(value) > 255 for value in metadata.values()):
        raise UnsafeAuditMetadataError("audit metadata string exceeds safe length")
    serialized = json.dumps(metadata, separators=(",", ":"), sort_keys=True)
    if len(serialized.encode("utf-8")) > MAX_METADATA_BYTES:
        raise UnsafeAuditMetadataError("audit metadata exceeds safe size limit")
    return metadata


class TamperedAuditChainError(RuntimeError):
    """Raised when an audit chain gap, hash mismatch, or seal inconsistency is detected."""


def compute_event_hash(
    *,
    sequence_number: int,
    prev_hash: str,
    tenant_id: UUID | None,
    actor_type: AuditActorType,
    actor_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    occurred_at: datetime,
    request_id: str,
    outcome: AuditOutcome,
    safe_metadata: dict[str, Any],
) -> str:
    if occurred_at.tzinfo is None:
        occurred_dt = occurred_at.replace(tzinfo=UTC)
    else:
        occurred_dt = occurred_at.astimezone(UTC)

    payload = {
        "action": action,
        "actor_id": str(actor_id) if actor_id else None,
        "actor_type": str(actor_type),
        "metadata": safe_metadata,
        "occurred_at": occurred_dt.isoformat(),
        "outcome": str(outcome),
        "prev_hash": prev_hash,
        "request_id": request_id,
        "resource_id": resource_id,
        "resource_type": resource_type,
        "sequence_number": sequence_number,
        "tenant_id": str(tenant_id) if tenant_id else None,
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def compute_merkle_root(hashes: list[str]) -> str:
    if not hashes:
        return hashlib.sha256(b"").hexdigest()
    current_level = [bytes.fromhex(h) for h in hashes]
    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            next_level.append(hashlib.sha256(left + right).digest())
        current_level = next_level
    return current_level[0].hex()


def compute_seal_digest(
    *,
    tenant_id: UUID | None,
    start_sequence: int,
    end_sequence: int,
    record_count: int,
    head_event_hash: str,
    merkle_root: str,
    sealed_at: datetime,
) -> str:
    if sealed_at.tzinfo is None:
        sealed_dt = sealed_at.replace(tzinfo=UTC)
    else:
        sealed_dt = sealed_at.astimezone(UTC)

    payload = {
        "end_sequence": end_sequence,
        "head_event_hash": head_event_hash,
        "merkle_root": merkle_root,
        "record_count": record_count,
        "sealed_at": sealed_dt.isoformat(),
        "start_sequence": start_sequence,
        "tenant_id": str(tenant_id) if tenant_id else None,
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def record_audit_event(
    session: Session,
    *,
    tenant_id: UUID | None,
    actor_type: AuditActorType,
    actor_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    request_id: str,
    outcome: AuditOutcome,
    metadata: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> AuditEvent:
    occurred = occurred_at or datetime.now(UTC)
    validated_meta = validate_safe_metadata(metadata or {})

    # Determine sequence_number and prev_hash for this tenant / system chain
    query = session.query(AuditEvent)
    if tenant_id is not None:
        query = query.filter(AuditEvent.tenant_id == tenant_id)
    else:
        query = query.filter(AuditEvent.tenant_id.is_(None))
    last_event = query.order_by(AuditEvent.sequence_number.desc()).first()

    if last_event is not None:
        sequence_number = last_event.sequence_number + 1
        prev_hash = last_event.event_hash
    else:
        sequence_number = 1
        prev_hash = "0" * 64

    event_hash = compute_event_hash(
        sequence_number=sequence_number,
        prev_hash=prev_hash,
        tenant_id=tenant_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        occurred_at=occurred,
        request_id=request_id,
        outcome=outcome,
        safe_metadata=validated_meta,
    )

    event_record = AuditEvent(
        tenant_id=tenant_id,
        sequence_number=sequence_number,
        prev_hash=prev_hash,
        event_hash=event_hash,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        occurred_at=occurred,
        request_id=request_id,
        outcome=outcome,
        safe_metadata=validated_meta,
    )
    session.add(event_record)
    session.flush()
    return event_record


def create_audit_seal(
    session: Session,
    *,
    tenant_id: UUID | None,
    sealed_by_user_id: UUID | None = None,
    storage_object_id: str | None = None,
) -> AuditSeal:
    last_seal = (
        session.query(AuditSeal)
        .filter(AuditSeal.tenant_id == tenant_id)
        .order_by(AuditSeal.end_sequence.desc())
        .first()
    )
    start_sequence = (last_seal.end_sequence + 1) if last_seal else 1

    query = session.query(AuditEvent)
    if tenant_id is not None:
        query = query.filter(AuditEvent.tenant_id == tenant_id)
    else:
        query = query.filter(AuditEvent.tenant_id.is_(None))
    events = (
        query.filter(AuditEvent.sequence_number >= start_sequence)
        .order_by(AuditEvent.sequence_number.asc())
        .all()
    )
    if not events:
        raise ValueError("No unsealed audit events available to seal")

    end_sequence = events[-1].sequence_number
    head_event_hash = events[-1].event_hash
    record_count = len(events)
    merkle_root = compute_merkle_root([e.event_hash for e in events])
    sealed_at = datetime.now(UTC)

    seal_digest = compute_seal_digest(
        tenant_id=tenant_id,
        start_sequence=start_sequence,
        end_sequence=end_sequence,
        record_count=record_count,
        head_event_hash=head_event_hash,
        merkle_root=merkle_root,
        sealed_at=sealed_at,
    )

    seal = AuditSeal(
        tenant_id=tenant_id,
        start_sequence=start_sequence,
        end_sequence=end_sequence,
        record_count=record_count,
        head_event_hash=head_event_hash,
        merkle_root=merkle_root,
        sealed_at=sealed_at,
        sealed_by_user_id=sealed_by_user_id,
        seal_signature_digest=seal_digest,
        storage_object_id=storage_object_id,
    )
    session.add(seal)
    session.flush()
    return seal


def verify_audit_chain(session: Session, tenant_id: UUID | None) -> tuple[bool, int, str | None]:
    query = session.query(AuditEvent)
    if tenant_id is not None:
        query = query.filter(AuditEvent.tenant_id == tenant_id)
    else:
        query = query.filter(AuditEvent.tenant_id.is_(None))
    events = query.order_by(AuditEvent.sequence_number.asc()).all()

    if not events:
        return True, 0, None

    for i, evt in enumerate(events):
        expected_seq = i + 1
        if evt.sequence_number != expected_seq:
            msg = f"Sequence gap: expected {expected_seq}, got {evt.sequence_number}"
            return False, evt.sequence_number, msg

        expected_prev = "0" * 64 if i == 0 else events[i - 1].event_hash
        if evt.prev_hash != expected_prev:
            msg = f"Prev hash mismatch at seq {evt.sequence_number}: expected {expected_prev}, got {evt.prev_hash}"
            return False, evt.sequence_number, msg

        recomputed = compute_event_hash(
            sequence_number=evt.sequence_number,
            prev_hash=evt.prev_hash,
            tenant_id=evt.tenant_id,
            actor_type=evt.actor_type,
            actor_id=evt.actor_id,
            action=evt.action,
            resource_type=evt.resource_type,
            resource_id=evt.resource_id,
            occurred_at=evt.occurred_at,
            request_id=evt.request_id,
            outcome=evt.outcome,
            safe_metadata=evt.safe_metadata,
        )
        if evt.event_hash != recomputed:
            msg = f"Event hash mismatch at seq {evt.sequence_number}: expected {recomputed}, got {evt.event_hash}"
            return False, evt.sequence_number, msg

    # Verify seals
    seal_query = session.query(AuditSeal)
    if tenant_id is not None:
        seal_query = seal_query.filter(AuditSeal.tenant_id == tenant_id)
    else:
        seal_query = seal_query.filter(AuditSeal.tenant_id.is_(None))
    seals = seal_query.order_by(AuditSeal.start_sequence.asc()).all()

    for seal in seals:
        sealed_events = [
            e for e in events if seal.start_sequence <= e.sequence_number <= seal.end_sequence
        ]
        if len(sealed_events) != seal.record_count:
            msg = f"Seal {seal.id} count mismatch: expected {seal.record_count}, got {len(sealed_events)}"
            return False, seal.start_sequence, msg
        if sealed_events[-1].event_hash != seal.head_event_hash:
            msg = f"Seal {seal.id} head hash mismatch"
            return False, seal.end_sequence, msg
        recomputed_root = compute_merkle_root([e.event_hash for e in sealed_events])
        if seal.merkle_root != recomputed_root:
            msg = f"Seal {seal.id} Merkle root mismatch"
            return False, seal.start_sequence, msg
        recomputed_seal_digest = compute_seal_digest(
            tenant_id=seal.tenant_id,
            start_sequence=seal.start_sequence,
            end_sequence=seal.end_sequence,
            record_count=seal.record_count,
            head_event_hash=seal.head_event_hash,
            merkle_root=seal.merkle_root,
            sealed_at=seal.sealed_at,
        )
        if seal.seal_signature_digest != recomputed_seal_digest:
            msg = f"Seal {seal.id} signature digest mismatch"
            return False, seal.start_sequence, msg

    return True, len(events), None


def _reject_audit_mutation(
    _mapper: object, _connection: object, _target: AuditEvent | AuditSeal
) -> None:
    raise ImmutableAuditEventError("audit records are strictly append-only and tamper-evident")


event.listen(AuditEvent, "before_update", _reject_audit_mutation)
event.listen(AuditEvent, "before_delete", _reject_audit_mutation)
event.listen(AuditSeal, "before_update", _reject_audit_mutation)
event.listen(AuditSeal, "before_delete", _reject_audit_mutation)
