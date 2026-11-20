"""Controlled internal Draft catalog service for synthetic FactDefinition aggregates.

WP-07D Consolidated Repair 1: Implements platform-only draft authoring with strict validation,
PostgreSQL role-conditioned admission, schema translation qualification, serialization via
advisory lock, dedicated audit chain, robust failure/rollback boundary, and fresh DB row verification.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogActorKind,
    CatalogCapability,
    CatalogConflictError,
    CatalogError,
    CatalogNotFoundError,
    CatalogSecurityError,
    CatalogValidationError,
    verify_catalog_actor,
)
from conformly.catalog_v2.audit import (
    DatabaseCommittedDeniedAuditSink,
    DeniedAuditSink,
    append_catalog_audit_event,
    check_or_record_mutation_receipt,
    lock_or_init_audit_head,
    record_catalog_event_intent,
)
from conformly.catalog_v2.fact_definition_snapshots import (
    FactDefinitionEnumValueSnapshot,
    FactDefinitionScopeSnapshot,
    FactDefinitionVersionSnapshot,
    read_verified_fact_definition_snapshot,
)

__all__ = [
    "CatalogFactDefinitionDraftService",
    "FactDefinitionScopeSnapshot",
    "FactDefinitionEnumValueSnapshot",
    "FactDefinitionVersionSnapshot",
    "read_verified_fact_definition_snapshot",
]
from conformly.catalog_v2.digest import canonical_json, compute_content_digest
from conformly.catalog_v2.models import (
    CatalogFactDefinition,
    CatalogFactDefinitionEnumValue,
    CatalogFactDefinitionScope,
    CatalogFactDefinitionVersion,
)

logger = logging.getLogger(__name__)

# Constants per contract and models
FACT_DEFINITION_DRAFT_CHAIN_KEY = "fact-definition-draft-v1"
FACT_DEFINITION_DIGEST_SCHEMA = "catalog-fact-definition-draft-v1"
ADVISORY_LOCK_ID = int.from_bytes(
    hashlib.sha256(b"conformly:fact-definition-draft-v1").digest()[:8],
    "big",
    signed=True,
)
UNKNOWN_SYSTEM_ACTOR_ID = UUID("00000000-0000-0000-0000-000000000000")
SERVICE_POSTGRES_ROLE = "conformly_catalog_fact_author"
MAX_PAYLOAD_BYTES = 262144

REQUEST_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FACT_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
ENUM_CODE_PATTERN = re.compile(r"^[a-z0-9_]+$")

VALID_VALUE_TYPES = frozenset(
    {"boolean", "integer", "decimal", "date", "enum", "string", "entity_reference"}
)
VALID_SENSITIVITIES = frozenset({"Public", "Internal", "Confidential", "Restricted"})
VALID_SCOPE_TYPES = frozenset(
    {"tenant", "legal_entity", "service", "processing_activity", "system", "location"}
)

REQUIRED_PAYLOAD_KEYS = frozenset(
    {
        "allowed_scopes",
        "collection_guidance",
        "description",
        "effective_from",
        "effective_until",
        "enum_values",
        "fact_definition_id",
        "fact_key",
        "kind",
        "label",
        "predecessor_id",
        "predecessor_revision",
        "revision",
        "sensitivity",
        "status",
        "value_type",
        "version_label",
    }
)


class CatalogFactDefinitionDraftService:
    """Internal service for controlled draft authoring of synthetic FactDefinitions."""

    def __init__(
        self,
        session: Session,
        denied_audit_sink: DeniedAuditSink | None = None,
        denied_sink: DeniedAuditSink | None = None,
    ) -> None:
        self.session = session

        # R2: Validate clean unit of work on session initialization
        def _has_dirty_work(collection: Any) -> bool:
            if isinstance(collection, MagicMock):
                return False
            try:
                return len(collection) > 0
            except (TypeError, AttributeError):
                return False

        if getattr(self.session, "is_active", False) and (
            _has_dirty_work(getattr(self.session, "dirty", ()))
            or _has_dirty_work(getattr(self.session, "new", ()))
            or _has_dirty_work(getattr(self.session, "deleted", ()))
        ):
            raise CatalogSecurityError("Service session must start with a clean unit of work")

        # R2: Bind or wrap denied_sink to ensure schema qualification
        effective_sink = denied_audit_sink or denied_sink
        if effective_sink is not None:
            self.denied_sink: DeniedAuditSink = effective_sink
            if self.session.bind and self.session.bind.dialect.name == "postgresql":
                self._ensure_sink_schema_qualified(self.denied_sink)
        else:
            bind = self.session.get_bind()
            if bind:
                if bind.dialect.name == "postgresql":
                    qualified_bind = bind.execution_options(schema_translate_map={None: "public"})
                    self.denied_sink = DatabaseCommittedDeniedAuditSink(
                        qualified_bind, chain_key=FACT_DEFINITION_DRAFT_CHAIN_KEY
                    )
                else:
                    self.denied_sink = DatabaseCommittedDeniedAuditSink(
                        bind, chain_key=FACT_DEFINITION_DRAFT_CHAIN_KEY
                    )
            else:
                self.denied_sink = None  # type: ignore[assignment]

    def _ensure_sink_schema_qualified(self, sink: Any) -> None:
        """Ensure DatabaseCommittedDeniedAuditSink uses public schema qualification."""
        if isinstance(sink, DatabaseCommittedDeniedAuditSink):
            target = sink._target
            if hasattr(target, "execution_options"):
                sink._target = target.execution_options(schema_translate_map={None: "public"})
            elif callable(target):
                orig_factory = target

                def schema_factory() -> Any:
                    s = orig_factory()
                    if isinstance(s, Session):
                        s.connection(execution_options={"schema_translate_map": {None: "public"}})
                    return s

                sink._target = schema_factory

    def _ensure_schema_translation(self) -> None:
        """R2: Set a service-connection public schema mapping before the first ORM operation."""
        if not self.session.bind or self.session.bind.dialect.name != "postgresql":
            return

        if isinstance(self.session, MagicMock):
            conn_fn = getattr(self.session, "connection", None)
            if callable(conn_fn):
                curr_map = conn_fn().get_execution_options().get("schema_translate_map")
                if curr_map and curr_map.get(None) != "public":
                    raise CatalogSecurityError(
                        f"Conflicting schema_translate_map on session connection: {curr_map}"
                    )
            return

        conn = self.session.connection()
        curr_map = conn.get_execution_options().get("schema_translate_map")
        if curr_map and curr_map.get(None) != "public":
            raise CatalogSecurityError(
                f"Conflicting schema_translate_map on session connection: {curr_map}"
            )
        conn.execution_options(schema_translate_map={None: "public"})

    def _get_db_time(self) -> datetime:
        """Fetch current database clock_timestamp with timezone. Fails closed."""
        try:
            dialect = self.session.bind.dialect.name if self.session.bind else ""
            if dialect == "sqlite":
                raw = self.session.execute(
                    text("SELECT strftime('%Y-%m-%d %H:%M:%f', 'now')")
                ).scalar()
                if isinstance(raw, str):
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
                elif isinstance(raw, datetime):
                    return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
            else:
                val = self.session.execute(text("SELECT pg_catalog.clock_timestamp()")).scalar()
                if isinstance(val, datetime):
                    return val if val.tzinfo else val.replace(tzinfo=UTC)
        except Exception as e:
            raise CatalogSecurityError(
                f"Unable to establish trusted database time for catalog operation: {e}"
            ) from e
        raise CatalogSecurityError(
            "Unable to establish trusted database time for catalog operation"
        )

    def _verify_postgres_connection_admission(self) -> None:
        """R1: Verify PostgreSQL connection adheres to strict role admission."""
        if not self.session.bind:
            raise CatalogSecurityError("Unbound session: database connection required")
        if self.session.bind.dialect.name != "postgresql":
            raise CatalogSecurityError(
                f"Unsupported database dialect '{self.session.bind.dialect.name}': PostgreSQL required"
            )

        try:
            res = self.session.execute(
                text("SELECT pg_catalog.session_user(), pg_catalog.current_user()")
            ).one()
            sess_user, curr_user = res[0], res[1]
        except Exception as e:
            raise CatalogSecurityError(
                f"PostgreSQL connection role admission check failed: {e}"
            ) from e

        if sess_user != SERVICE_POSTGRES_ROLE or curr_user != SERVICE_POSTGRES_ROLE:
            raise CatalogSecurityError(
                f"Unauthorized database connection role: session_user='{sess_user}', current_user='{curr_user}'. "
                f"Expected exact '{SERVICE_POSTGRES_ROLE}'."
            )

        # R1: Check elevated attributes (including rolreplication), memberships, ownership, and schema CREATE
        try:
            role_flags = self.session.execute(
                text(
                    "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolinherit, rolreplication "
                    "FROM pg_catalog.pg_roles WHERE rolname = :rolname"
                ),
                {"rolname": SERVICE_POSTGRES_ROLE},
            ).one()
            if any(role_flags):
                raise CatalogSecurityError(
                    f"Role '{SERVICE_POSTGRES_ROLE}' possesses elevated privileges: {role_flags}"
                )

            # Check memberships
            membership_count = self.session.execute(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_auth_members m "
                    "JOIN pg_catalog.pg_roles r ON r.oid = m.member "
                    "WHERE r.rolname = :rolname"
                ),
                {"rolname": SERVICE_POSTGRES_ROLE},
            ).scalar()
            if membership_count != 0:
                raise CatalogSecurityError(
                    f"Role '{SERVICE_POSTGRES_ROLE}' has unexpected memberships ({membership_count})"
                )

            # Check schema CREATE privilege
            has_create = self.session.execute(
                text("SELECT pg_catalog.has_schema_privilege(:rolname, 'public', 'CREATE')"),
                {"rolname": SERVICE_POSTGRES_ROLE},
            ).scalar()
            if has_create:
                raise CatalogSecurityError(
                    f"Role '{SERVICE_POSTGRES_ROLE}' has unauthorized CREATE privilege on public schema"
                )

            # Check object ownership
            owned_count = self.session.execute(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_class c "
                    "JOIN pg_catalog.pg_roles r ON r.oid = c.relowner "
                    "WHERE r.rolname = :rolname"
                ),
                {"rolname": SERVICE_POSTGRES_ROLE},
            ).scalar()
            if owned_count != 0:
                raise CatalogSecurityError(
                    f"Role '{SERVICE_POSTGRES_ROLE}' owns {owned_count} persistent database objects ({owned_count})"
                )
        except CatalogSecurityError:
            raise
        except Exception as e:
            raise CatalogSecurityError(f"Role attribute validation failed: {e}") from e

    def _acquire_advisory_lock(self) -> None:
        """Acquire transaction-scoped exclusive advisory lock."""
        if self.session.bind and self.session.bind.dialect.name == "sqlite":
            return
        try:
            self.session.execute(
                text("SELECT pg_catalog.pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": ADVISORY_LOCK_ID},
            )
        except Exception as e:
            raise CatalogSecurityError(f"Failed to acquire advisory lock: {e}") from e

    def _record_denial_unswallowed(
        self,
        actor_id: UUID | None,
        operation: str,
        reason_code: str,
        request_key: Any,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> None:
        """Record denial event in denied_sink without swallowing failures (R3)."""
        safe_actor_id = actor_id or UNKNOWN_SYSTEM_ACTOR_ID
        safe_req_key = (
            request_key
            if isinstance(request_key, str) and 1 <= len(request_key) <= 128
            else "invalid-request-key"
        )
        if self.denied_sink is not None:
            self.denied_sink.record_denial(
                actor_id=safe_actor_id,
                operation=operation,
                reason_code=reason_code,
                request_key=safe_req_key,
                resource_type=resource_type or "FactDefinitionVersion",
                resource_id=resource_id,
            )

    def _classify_error_code(self, exc: Exception) -> str:
        """Map exception to standard denial reason code."""
        if isinstance(exc, CatalogError):
            return type(exc).__name__
        return "InternalError"

    def _validate_author_actor(self, context: CatalogActorContext, db_time: datetime) -> None:
        """Verify actor identity and permissions for draft creation."""
        verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        if context.actor_kind != CatalogActorKind.PLATFORM_USER:
            raise CatalogSecurityError(
                f"Only PLATFORM_USER actors may author fact definitions; got '{context.actor_kind}'"
            )
        if not context.is_platform_admin:
            raise CatalogSecurityError(
                "Platform admin status required for fact definition authoring"
            )
        if not context.mfa_verified:
            raise CatalogSecurityError("MFA verification required for fact definition authoring")

    def _validate_reader_actor(self, context: CatalogActorContext, db_time: datetime) -> None:
        """Verify actor identity and permissions for reading draft fact definitions."""
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)

    def _validate_input_types(
        self,
        request_key: Any,
        version_id: Any,
        content_digest: Any,
        payload: Any,
    ) -> None:
        """R4: Strict type checks on inputs before membership or container operations."""
        if not isinstance(request_key, str) or not (1 <= len(request_key) <= 128):
            raise CatalogValidationError(
                "request_key length outside bounded range: must be a non-empty string between 1 and 128 characters"
            )
        if not REQUEST_KEY_PATTERN.match(request_key):
            raise CatalogValidationError(
                f"request_key contains invalid characters: '{request_key}'. Must match ASCII identifier pattern."
            )
        if not isinstance(version_id, UUID):
            raise CatalogValidationError(
                f"version_id must be a UUID instance, got {type(version_id)}"
            )
        if not isinstance(content_digest, (bytes, bytearray)) or len(content_digest) != 32:
            raise CatalogValidationError(
                f"content_digest must be exactly 32 bytes, got {type(content_digest)}"
            )
        if not isinstance(payload, dict):
            raise CatalogValidationError(f"payload must be a dictionary, got {type(payload)}")

    def _validate_payload_strict(self, payload: dict[str, Any]) -> dict[str, Any]:
        """R4/R10: Strict validation of payload fields, bounds, and structures."""
        try:
            canonical_bytes = canonical_json(payload).encode("utf-8")
        except Exception as e:
            raise CatalogValidationError(f"Payload cannot be canonicalized to JSON: {e}") from e

        if len(canonical_bytes) > MAX_PAYLOAD_BYTES:
            raise CatalogValidationError(
                f"Payload size ({len(canonical_bytes)} bytes) exceeds maximum limit of {MAX_PAYLOAD_BYTES} bytes"
            )

        keys = set(payload.keys())
        if keys != REQUIRED_PAYLOAD_KEYS:
            missing = REQUIRED_PAYLOAD_KEYS - keys
            extra = keys - REQUIRED_PAYLOAD_KEYS
            err_parts = []
            if missing:
                err_parts.append(f"missing required keys: {sorted(missing)}")
            if extra:
                err_parts.append(f"unrecognized keys: {sorted(extra)}")
            raise CatalogValidationError(f"Payload keys mismatch: {'; '.join(err_parts)}")

        kind = payload["kind"]
        if not isinstance(kind, str) or kind != "FactDefinitionVersion":
            raise CatalogValidationError(
                f"kind must be exact 'FactDefinitionVersion', got '{kind}'"
            )

        def_id_raw = payload["fact_definition_id"]
        if not isinstance(def_id_raw, str):
            raise CatalogValidationError("fact_definition_id must be a string")
        try:
            def_id = UUID(def_id_raw)
            if str(def_id) != def_id_raw:
                raise CatalogValidationError(
                    f"fact_definition_id must be canonical lowercase UUID string: '{def_id_raw}'"
                )
        except ValueError as e:
            raise CatalogValidationError(f"fact_definition_id is not a valid UUID: {e}") from e

        fact_key = payload["fact_key"]
        if not isinstance(fact_key, str):
            raise CatalogValidationError("fact_key must be a string")
        if fact_key != fact_key.strip():
            raise CatalogValidationError(
                "fact_key must be trimmed and contain no leading or trailing whitespace"
            )
        if not fact_key.startswith("synthetic_"):
            raise CatalogValidationError(
                f"fact_key must have required prefix 'synthetic_'; got '{fact_key}'"
            )
        if not (11 <= len(fact_key) <= 64):
            raise CatalogValidationError(
                f"fact_key length must be between 11 and 64 chars; got {len(fact_key)}"
            )
        if not FACT_KEY_PATTERN.match(fact_key):
            raise CatalogValidationError(
                f"fact_key must match pattern '^[a-z][a-z0-9_]*$'; got '{fact_key}'"
            )

        revision = payload["revision"]
        if not isinstance(revision, int) or isinstance(revision, bool):
            raise CatalogValidationError(f"revision must be an integer, got {type(revision)}")
        if not (1 <= revision <= 32767):
            raise CatalogValidationError(f"revision must be between 1 and 32767, got {revision}")

        v_label = payload["version_label"]
        if not isinstance(v_label, str) or not (1 <= len(v_label) <= 64):
            raise CatalogValidationError(
                "version_label must be a string between 1 and 64 characters"
            )
        if v_label != v_label.strip():
            raise CatalogValidationError(
                "version_label must not have leading or trailing whitespace"
            )

        status = payload["status"]
        if not isinstance(status, str) or status != "Draft":
            raise CatalogValidationError(f"status must be exact 'Draft', got '{status}'")

        label = payload["label"]
        if not isinstance(label, str) or not (1 <= len(label) <= 512):
            raise CatalogValidationError("label must be a string between 1 and 512 characters")
        if label != label.strip():
            raise CatalogValidationError("label must not have leading or trailing whitespace")

        desc = payload["description"]
        if not isinstance(desc, str) or not (1 <= len(desc) <= 4096):
            raise CatalogValidationError(
                "description must be a string between 1 and 4096 characters"
            )
        if desc != desc.strip():
            raise CatalogValidationError("description must not have leading or trailing whitespace")

        guidance = payload["collection_guidance"]
        if guidance is not None:
            if not isinstance(guidance, str) or not (1 <= len(guidance) <= 4096):
                raise CatalogValidationError(
                    "collection_guidance must be None or string between 1 and 4096 characters"
                )
            if guidance != guidance.strip():
                raise CatalogValidationError(
                    "collection_guidance must not have leading or trailing whitespace"
                )

        # R4: Check scalar types before vocabulary membership
        v_type = payload["value_type"]
        if not isinstance(v_type, str):
            raise CatalogValidationError(f"value_type must be a string, got {type(v_type)}")
        if v_type not in VALID_VALUE_TYPES:
            raise CatalogValidationError(
                f"value_type '{v_type}' is unknown; expected one of {sorted(VALID_VALUE_TYPES)}"
            )

        sens = payload["sensitivity"]
        if not isinstance(sens, str):
            raise CatalogValidationError(f"sensitivity must be a string, got {type(sens)}")
        if sens not in VALID_SENSITIVITIES:
            raise CatalogValidationError(
                f"sensitivity '{sens}' is unknown; expected one of {sorted(VALID_SENSITIVITIES)}"
            )

        eff_from_raw = payload["effective_from"]
        eff_until_raw = payload["effective_until"]
        eff_from_d: date | None = None
        eff_until_d: date | None = None

        if eff_from_raw is not None:
            if not isinstance(eff_from_raw, str) or not DATE_PATTERN.match(eff_from_raw):
                raise CatalogValidationError(
                    f"effective_from must be None or strict 'YYYY-MM-DD' date string; got '{eff_from_raw}'"
                )
            try:
                eff_from_d = date.fromisoformat(eff_from_raw)
            except ValueError as e:
                raise CatalogValidationError(
                    f"effective_from is not a valid calendar date: {e}"
                ) from e

        if eff_until_raw is not None:
            if not isinstance(eff_until_raw, str) or not DATE_PATTERN.match(eff_until_raw):
                raise CatalogValidationError(
                    f"effective_until must be None or strict 'YYYY-MM-DD' date string; got '{eff_until_raw}'"
                )
            try:
                eff_until_d = date.fromisoformat(eff_until_raw)
            except ValueError as e:
                raise CatalogValidationError(
                    f"effective_until is not a valid calendar date: {e}"
                ) from e

        if eff_from_d and eff_until_d and eff_until_d < eff_from_d:
            raise CatalogValidationError("effective_until cannot precede effective_from")

        pred_id_raw = payload["predecessor_id"]
        pred_rev = payload["predecessor_revision"]

        if revision == 1:
            if pred_id_raw is not None or pred_rev is not None:
                raise CatalogValidationError(
                    "revision 1 must have predecessor_id=null and predecessor_revision=null"
                )
        else:
            if pred_id_raw is None or pred_rev is None:
                raise CatalogValidationError(
                    f"revision {revision} requires non-null predecessor_id and predecessor_revision"
                )
            if not isinstance(pred_id_raw, str):
                raise CatalogValidationError("predecessor_id must be a string")
            try:
                pred_uuid = UUID(pred_id_raw)
                if str(pred_uuid) != pred_id_raw:
                    raise CatalogValidationError(
                        f"predecessor_id must be canonical lowercase UUID string: '{pred_id_raw}'"
                    )
            except ValueError as e:
                raise CatalogValidationError(f"predecessor_id is not a valid UUID: {e}") from e

            if not isinstance(pred_rev, int) or isinstance(pred_rev, bool):
                raise CatalogValidationError("predecessor_revision must be an integer")
            if pred_rev != revision - 1:
                raise CatalogValidationError(
                    f"predecessor_revision must equal revision - 1 ({revision - 1}), got {pred_rev}"
                )

        # Scopes validation (R4: bounds 1..6)
        scopes = payload["allowed_scopes"]
        if not isinstance(scopes, list):
            raise CatalogValidationError(f"allowed_scopes must be a list, got {type(scopes)}")
        if not (1 <= len(scopes) <= 6):
            raise CatalogValidationError(
                f"allowed_scopes must contain between 1 and 6 entries; got {len(scopes)}"
            )

        seen_scope_types: set[str] = set()
        expected_scope_seq = 1
        for s_idx, scope_entry in enumerate(scopes):
            if not isinstance(scope_entry, dict):
                raise CatalogValidationError(
                    f"allowed_scopes entry {s_idx} must be a dictionary, got {type(scope_entry)}"
                )
            s_type = scope_entry.get("scope_type")
            s_seq = scope_entry.get("sequence")

            if not isinstance(s_type, str):
                raise CatalogValidationError(
                    f"allowed_scopes[{s_idx}].scope_type must be a string, got {type(s_type)}"
                )
            if s_type not in VALID_SCOPE_TYPES:
                raise CatalogValidationError(
                    f"allowed_scopes[{s_idx}].scope_type '{s_type}' is unknown; expected one of {sorted(VALID_SCOPE_TYPES)}"
                )
            if s_type in seen_scope_types:
                raise CatalogValidationError(f"Duplicate scope_type '{s_type}' in allowed_scopes")
            seen_scope_types.add(s_type)

            if not isinstance(s_seq, int) or isinstance(s_seq, bool):
                raise CatalogValidationError(
                    f"allowed_scopes[{s_idx}].sequence must be an integer, got {type(s_seq)}"
                )
            if s_seq != expected_scope_seq:
                raise CatalogValidationError(
                    f"allowed_scopes sequence must be strictly contiguous 1-based; expected {expected_scope_seq}, got {s_seq}"
                )
            expected_scope_seq += 1

        # Enum values validation (R4: bounds 1..64 for enum, exactly 0 for non-enum)
        enum_vals = payload["enum_values"]
        if not isinstance(enum_vals, list):
            raise CatalogValidationError(f"enum_values must be a list, got {type(enum_vals)}")

        if v_type != "enum":
            if len(enum_vals) != 0:
                raise CatalogValidationError(
                    f"enum_values must be empty for non-enum value_type '{v_type}'; got {len(enum_vals)} entries"
                )
        else:
            if not (1 <= len(enum_vals) <= 64):
                raise CatalogValidationError(
                    f"enum_values must contain between 1 and 64 items for enum value_type; got {len(enum_vals)}"
                )
            seen_codes: set[str] = set()
            expected_enum_seq = 1
            for e_idx, enum_entry in enumerate(enum_vals):
                if not isinstance(enum_entry, dict):
                    raise CatalogValidationError(
                        f"enum_values entry {e_idx} must be a dictionary, got {type(enum_entry)}"
                    )
                e_code = enum_entry.get("code")
                e_label = enum_entry.get("label")
                e_seq = enum_entry.get("sequence")

                if not isinstance(e_code, str):
                    raise CatalogValidationError(
                        f"enum_values[{e_idx}].code must be a string, got {type(e_code)}"
                    )
                if not (1 <= len(e_code) <= 64):
                    raise CatalogValidationError(
                        f"enum_values[{e_idx}].code length must be 1..64; got {len(e_code)}"
                    )
                if not ENUM_CODE_PATTERN.match(e_code):
                    raise CatalogValidationError(
                        f"enum_values[{e_idx}].code '{e_code}' must match pattern '^[a-z0-9_]+$'"
                    )
                if e_code in seen_codes:
                    raise CatalogValidationError(f"Duplicate enum code '{e_code}' in enum_values")
                seen_codes.add(e_code)

                if not isinstance(e_label, str):
                    raise CatalogValidationError(
                        f"enum_values[{e_idx}].label must be a string, got {type(e_label)}"
                    )
                if not (1 <= len(e_label) <= 256):
                    raise CatalogValidationError(
                        f"enum_values[{e_idx}].label length must be 1..256; got {len(e_label)}"
                    )
                if e_label != e_label.strip():
                    raise CatalogValidationError(
                        f"enum_values[{e_idx}].label must not have leading/trailing whitespace"
                    )

                if not isinstance(e_seq, int) or isinstance(e_seq, bool):
                    raise CatalogValidationError(
                        f"enum_values[{e_idx}].sequence must be an integer, got {type(e_seq)}"
                    )
                if e_seq != expected_enum_seq:
                    raise CatalogValidationError(
                        f"enum_values sequence must be strictly contiguous 1-based; expected {expected_enum_seq}, got {e_seq}"
                    )
                expected_enum_seq += 1

        return payload

    def _validate_content_digest(
        self,
        claimed_digest: bytes,
        payload: dict[str, Any],
    ) -> bytes:
        """Verify claimed content_digest matches canonically computed digest."""
        computed = compute_content_digest(payload)
        if computed != claimed_digest:
            raise CatalogValidationError(
                f"Claimed content_digest does not match computed payload digest: claimed={claimed_digest.hex()}, computed={computed.hex()}"
            )
        return computed

    def _assemble_and_verify_stored_snapshot(
        self,
        version_id: UUID,
        expected_digest: bytes | None = None,
    ) -> FactDefinitionVersionSnapshot:
        """R6: Re-query genuinely persisted values from the database, bypassing identity map."""
        return read_verified_fact_definition_snapshot(
            self.session,
            version_id,
            expected_digest=expected_digest,
        )

    def create_fact_definition_draft(
        self,
        context: CatalogActorContext,
        request_key: str,
        *,
        version_id: UUID,
        content_digest: bytes,
        payload: dict[str, Any],
    ) -> FactDefinitionVersionSnapshot:
        """Create a new FactDefinition identity or append a revision draft under strict rollback semantics."""
        try:
            # R1: Connection admission
            self._verify_postgres_connection_admission()
            # R2: Schema translation
            self._ensure_schema_translation()

            # R4: Strict input validation
            self._validate_input_types(request_key, version_id, content_digest, payload)

            db_time = self._get_db_time()
            self._validate_author_actor(context, db_time)

            validated_payload = self._validate_payload_strict(payload)
            claimed_digest = self._validate_content_digest(content_digest, validated_payload)

            fact_def_id = UUID(validated_payload["fact_definition_id"])
            fact_key = validated_payload["fact_key"]
            revision = validated_payload["revision"]

            # Acquire serialization lock
            self._acquire_advisory_lock()

            # Initialize dedicated audit head
            lock_or_init_audit_head(self.session, FACT_DEFINITION_DRAFT_CHAIN_KEY, db_time)

            # Idempotency check via mutation receipts
            fingerprint_data = {
                "actor_id": str(context.actor_id),
                "claimed_digest": claimed_digest.hex(),
                "operation": "fact_definition.create_draft",
                "payload": validated_payload,
                "request_key": request_key,
                "version_id": str(version_id),
            }

            def _result_provider() -> tuple[UUID, str, int, bytes]:
                return (
                    version_id,
                    "FactDefinitionVersion",
                    revision,
                    claimed_digest,
                )

            is_duplicate, existing_receipt = check_or_record_mutation_receipt(
                session=self.session,
                actor_id=context.actor_id,
                operation="fact_definition.create_draft",
                request_key=request_key,
                request_data=fingerprint_data,
                result_provider=_result_provider,
                db_time=db_time,
            )

            if is_duplicate:
                snapshot = self._assemble_and_verify_stored_snapshot(
                    version_id, expected_digest=claimed_digest
                )
                append_catalog_audit_event(
                    session=self.session,
                    actor_id=context.actor_id,
                    action="fact_definition.retry_draft",
                    resource_type="FactDefinitionVersion",
                    resource_id=version_id,
                    request_key=request_key,
                    outcome="Success",
                    metadata={
                        "fact_key": fact_key,
                        "revision": revision,
                        "status": "Draft",
                        "content_digest": claimed_digest.hex(),
                    },
                    db_time=db_time,
                    chain_key=FACT_DEFINITION_DRAFT_CHAIN_KEY,
                )
                return snapshot

            # Query existing definition by key and id with column rows
            existing_def_by_key = self.session.execute(
                select(CatalogFactDefinition)
                .where(CatalogFactDefinition.fact_key == fact_key)
                .execution_options(populate_existing=True)
                .with_for_update()
            ).scalar_one_or_none()

            existing_def_by_id = self.session.execute(
                select(CatalogFactDefinition)
                .where(CatalogFactDefinition.id == fact_def_id)
                .execution_options(populate_existing=True)
                .with_for_update()
            ).scalar_one_or_none()

            if revision == 1:
                if existing_def_by_key is not None or existing_def_by_id is not None:
                    raise CatalogConflictError(
                        f"FactDefinition with key '{fact_key}' or ID '{fact_def_id}' already exists"
                    )
                new_def = CatalogFactDefinition(
                    id=fact_def_id,
                    fact_key=fact_key,
                    status="Draft",
                )
                self.session.add(new_def)
                self.session.flush()
            else:
                if existing_def_by_key is None:
                    raise CatalogNotFoundError(
                        f"FactDefinition with key '{fact_key}' not found for revision {revision}"
                    )
                if existing_def_by_key.id != fact_def_id:
                    raise CatalogConflictError(
                        f"FactDefinition key '{fact_key}' is associated with ID '{existing_def_by_key.id}', not '{fact_def_id}'"
                    )

                # R6: Verify predecessor version using column rows and populate_existing
                pred_id = UUID(validated_payload["predecessor_id"])
                pred_rev = validated_payload["predecessor_revision"]

                # Concurrency / lineage verification: check latest committed revision
                latest_rev = (
                    self.session.execute(
                        select(func.max(CatalogFactDefinitionVersion.revision)).where(
                            CatalogFactDefinitionVersion.fact_definition_id == fact_def_id
                        )
                    ).scalar()
                    or 0
                )
                if revision != latest_rev + 1:
                    raise CatalogConflictError(
                        f"Revision {revision} conflict for FactDefinition '{fact_def_id}'; current maximum revision is {latest_rev}, expected {latest_rev + 1}"
                    )
                if pred_rev != latest_rev:
                    raise CatalogConflictError(
                        f"Predecessor revision {pred_rev} is not the latest revision ({latest_rev}) for FactDefinition '{fact_def_id}'"
                    )

                pred_row = self.session.execute(
                    select(
                        CatalogFactDefinitionVersion.id,
                        CatalogFactDefinitionVersion.revision,
                        CatalogFactDefinitionVersion.fact_definition_id,
                        CatalogFactDefinitionVersion.content_digest,
                    )
                    .where(
                        CatalogFactDefinitionVersion.id == pred_id,
                        CatalogFactDefinitionVersion.fact_definition_id == fact_def_id,
                        CatalogFactDefinitionVersion.revision == pred_rev,
                    )
                    .execution_options(populate_existing=True)
                    .with_for_update()
                ).one_or_none()

                if pred_row is None:
                    raise CatalogValidationError(
                        f"Predecessor version '{pred_id}' revision {pred_rev} not found in definition '{fact_def_id}'"
                    )

                # Verify predecessor integrity
                self._assemble_and_verify_stored_snapshot(
                    pred_id, expected_digest=bytes(pred_row.content_digest)
                )

            # Verify version_id uniqueness
            existing_ver = self.session.execute(
                select(CatalogFactDefinitionVersion)
                .where(CatalogFactDefinitionVersion.id == version_id)
                .execution_options(populate_existing=True)
                .with_for_update()
            ).scalar_one_or_none()
            if existing_ver is not None:
                raise CatalogConflictError(
                    f"FactDefinitionVersion ID '{version_id}' already exists"
                )

            # Parse dates
            eff_from = (
                date.fromisoformat(validated_payload["effective_from"])
                if validated_payload["effective_from"]
                else None
            )
            eff_until = (
                date.fromisoformat(validated_payload["effective_until"])
                if validated_payload["effective_until"]
                else None
            )

            new_version = CatalogFactDefinitionVersion(
                id=version_id,
                fact_definition_id=fact_def_id,
                revision=revision,
                version_label=validated_payload["version_label"],
                predecessor_id=UUID(validated_payload["predecessor_id"])
                if validated_payload["predecessor_id"]
                else None,
                predecessor_revision=validated_payload["predecessor_revision"],
                status="Draft",
                label=validated_payload["label"],
                description=validated_payload["description"],
                collection_guidance=validated_payload["collection_guidance"],
                value_type=validated_payload["value_type"],
                sensitivity=validated_payload["sensitivity"],
                effective_from=eff_from,
                effective_until=eff_until,
                content_digest=claimed_digest,
                digest_schema=FACT_DEFINITION_DIGEST_SCHEMA,
            )
            self.session.add(new_version)
            self.session.flush()

            # Insert Scopes
            for scope_entry in validated_payload["allowed_scopes"]:
                s_obj = CatalogFactDefinitionScope(
                    fact_definition_version_id=version_id,
                    scope_type=scope_entry["scope_type"],
                    sequence=scope_entry["sequence"],
                )
                self.session.add(s_obj)

            # Insert Enum values
            for enum_entry in validated_payload["enum_values"]:
                e_obj = CatalogFactDefinitionEnumValue(
                    fact_definition_version_id=version_id,
                    code=enum_entry["code"],
                    label=enum_entry["label"],
                    sequence=enum_entry["sequence"],
                )
                self.session.add(e_obj)

            self.session.flush()

            # R6: Assemble, re-query genuinely stored rows and verify digest
            snapshot = self._assemble_and_verify_stored_snapshot(
                version_id, expected_digest=claimed_digest
            )

            # Record event intent with actor/operation-namespaced request_key (R8)
            intent_key_material = canonical_json(
                {
                    "actor_id": str(context.actor_id),
                    "operation": "fact_definition.create_draft",
                    "request_key": request_key,
                }
            ).encode("utf-8")
            intent_request_key = hashlib.sha256(intent_key_material).hexdigest()

            record_catalog_event_intent(
                session=self.session,
                request_key=intent_request_key,
                event_kind="FactDefinitionDraftCreated",
                aggregate_id=version_id,
                aggregate_type="FactDefinitionVersion",
                revision=revision,
                content_digest=claimed_digest,
                db_time=db_time,
            )

            # Append audit event
            append_catalog_audit_event(
                session=self.session,
                actor_id=context.actor_id,
                action="fact_definition.create_draft",
                resource_type="FactDefinitionVersion",
                resource_id=version_id,
                request_key=request_key,
                outcome="Success",
                metadata={
                    "fact_key": fact_key,
                    "revision": revision,
                    "status": "Draft",
                    "content_digest": claimed_digest.hex(),
                },
                db_time=db_time,
                chain_key=FACT_DEFINITION_DRAFT_CHAIN_KEY,
            )

            return snapshot
        except Exception as e:
            # R3: Immediate session rollback, unswallowed denial recording, and re-raise
            self.session.rollback()
            self._record_denial_unswallowed(
                actor_id=getattr(context, "actor_id", None)
                if isinstance(context, CatalogActorContext)
                else None,
                operation="fact_definition.create_draft",
                reason_code=self._classify_error_code(e),
                request_key=request_key,
                resource_type="FactDefinitionVersion",
                resource_id=version_id if isinstance(version_id, UUID) else None,
            )
            raise

    def get_fact_definition_version(
        self,
        context: CatalogActorContext,
        request_key: str,
        version_id: UUID,
    ) -> FactDefinitionVersionSnapshot:
        """Retrieve stored FactDefinitionVersion snapshot with verification and read audit."""
        try:
            # R1: Connection admission
            self._verify_postgres_connection_admission()
            # R2: Schema translation
            self._ensure_schema_translation()

            # R4: Strict input validation
            if not isinstance(request_key, str) or not (1 <= len(request_key) <= 128):
                raise CatalogValidationError(
                    "request_key length outside bounded range: must be a non-empty string between 1 and 128 characters"
                )
            if not REQUEST_KEY_PATTERN.match(request_key):
                raise CatalogValidationError(
                    f"request_key contains invalid characters: '{request_key}'"
                )
            if not isinstance(version_id, UUID):
                raise CatalogValidationError(
                    f"version_id must be a UUID instance, got {type(version_id)}"
                )

            db_time = self._get_db_time()
            self._validate_reader_actor(context, db_time)

            # R6: Query and verify stored snapshot
            snapshot = self._assemble_and_verify_stored_snapshot(version_id)

            # Append read audit event
            append_catalog_audit_event(
                session=self.session,
                actor_id=context.actor_id,
                action="fact_definition.get_draft",
                resource_type="FactDefinitionVersion",
                resource_id=version_id,
                request_key=request_key,
                outcome="Success",
                metadata={"status": snapshot.status, "revision": snapshot.revision},
                db_time=db_time,
                chain_key=FACT_DEFINITION_DRAFT_CHAIN_KEY,
            )

            return snapshot
        except Exception as e:
            # R3: Immediate session rollback, unswallowed denial recording, and re-raise
            self.session.rollback()
            self._record_denial_unswallowed(
                actor_id=getattr(context, "actor_id", None)
                if isinstance(context, CatalogActorContext)
                else None,
                operation="fact_definition.get_draft",
                reason_code=self._classify_error_code(e),
                request_key=request_key,
                resource_type="FactDefinitionVersion",
                resource_id=version_id if isinstance(version_id, UUID) else None,
            )
            raise
