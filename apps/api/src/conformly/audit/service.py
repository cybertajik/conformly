import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditEvent, AuditOutcome

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
        "adoption_id",
        "affected_controls_count",
        "already_revoked",
        "asset_id",
        "asset_type",
        "assigned_by_user_id",
        "assignee_user_id",
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
        "content_type",
        "control_id",
        "control_identifier",
        "control_status",
        "control_type",
        "count",
        "country",
        "criticality",
        "custom_control_id",
        "days_remaining",
        "deleted_tables_count",
        "deletion_due_at",
        "deletion_id",
        "deletion_proof_hash",
        "deletion_state",
        "display_name",
        "due_date",
        "enabled_modules",
        "error_code",
        "evidence_id",
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
        "portal_id",
        "portal_slug",
        "pre_audit_id",
        "preference_id",
        "previous_role",
        "previous_status",
        "priority",
        "profile_id",
        "public_case_id",
        "reason",
        "record_count",
        "records_count",
        "release_state",
        "remediation_status",
        "report_id",
        "report_type",
        "review_cycle_days",
        "revoked_reason",
        "risk_id",
        "role",
        "rule_version",
        "scope_id",
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
        "target_version_id",
        "task_id",
        "title",
        "treatment_id",
        "valid_until",
        "vendor_id",
        "version",
        "version_id",
        "version_number",
        "version_string",
        "will_retry",
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
    event_record = AuditEvent(
        tenant_id=tenant_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        occurred_at=occurred_at or datetime.now(UTC),
        request_id=request_id,
        outcome=outcome,
        safe_metadata=validate_safe_metadata(metadata or {}),
    )
    session.add(event_record)
    session.flush()
    return event_record


def _reject_audit_mutation(_mapper: object, _connection: object, _target: AuditEvent) -> None:
    raise ImmutableAuditEventError("audit events are append-only")


event.listen(AuditEvent, "before_update", _reject_audit_mutation)
event.listen(AuditEvent, "before_delete", _reject_audit_mutation)
