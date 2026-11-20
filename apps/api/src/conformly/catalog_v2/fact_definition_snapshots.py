"""Shared verified fact snapshot extraction for catalog_v2 (WP-07E).

Provides immutable dataclasses and genuine stored-column aggregate reader for
synthetic FactDefinitionVersion aggregates. Shared between CatalogFactDefinitionDraftService
and CatalogApplicabilityRuleDraftService.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.catalog_v2.actor import (
    CatalogInvariantError,
    CatalogNotFoundError,
    CatalogSecurityError,
)
from conformly.catalog_v2.digest import compute_content_digest
from conformly.catalog_v2.models import (
    CatalogFactDefinition,
    CatalogFactDefinitionEnumValue,
    CatalogFactDefinitionScope,
    CatalogFactDefinitionVersion,
)

FACT_DEFINITION_DIGEST_SCHEMA = "catalog-fact-definition-draft-v1"
FACT_KEY_PATTERN = re.compile(r"\A[a-z][a-z0-9_]*\Z")
ENUM_CODE_PATTERN = re.compile(r"\A[a-z0-9_]+\Z")

VALID_VALUE_TYPES = frozenset(
    {"boolean", "integer", "decimal", "date", "enum", "string", "entity_reference"}
)
VALID_SENSITIVITIES = frozenset({"Public", "Internal", "Confidential", "Restricted"})
VALID_SCOPE_TYPES = frozenset(
    {"tenant", "legal_entity", "service", "processing_activity", "system", "location"}
)


@dataclass(frozen=True)
class FactDefinitionScopeSnapshot:
    sequence: int
    scope_type: str


@dataclass(frozen=True)
class FactDefinitionEnumValueSnapshot:
    sequence: int
    code: str
    label: str


@dataclass(frozen=True)
class FactDefinitionVersionSnapshot:
    id: UUID
    fact_definition_id: UUID
    fact_key: str
    revision: int
    version_label: str
    predecessor_id: UUID | None
    predecessor_revision: int | None
    label: str
    description: str
    collection_guidance: str | None
    value_type: str
    sensitivity: str
    effective_from: date | None
    effective_until: date | None
    status: str
    content_digest: bytes
    digest_schema: str
    allowed_scopes: tuple[FactDefinitionScopeSnapshot, ...]
    enum_values: tuple[FactDefinitionEnumValueSnapshot, ...]
    created_at: datetime
    updated_at: datetime


def read_verified_fact_definition_snapshot(
    session: Session,
    version_id: UUID,
    expected_digest: bytes | None = None,
) -> FactDefinitionVersionSnapshot:
    """Read and verify a complete persisted FactDefinitionVersion aggregate from genuine columns.

    Bypasses ORM cached objects using populate_existing=True.
    Validates complete stored aggregate integrity, bounds, lineage, and digest.
    Refreshes cached identity-map entity if present.
    """
    if not isinstance(version_id, UUID):
        raise CatalogInvariantError(f"version_id must be a UUID instance, got {type(version_id)}")

    # Enforce and verify public schema translation on PostgreSQL connection without swallowing errors
    bind = session.get_bind()
    if bind is not None and getattr(bind.dialect, "name", "") == "postgresql":
        try:
            conn = session.connection()
            curr_map = conn.get_execution_options().get("schema_translate_map")
            if curr_map and curr_map.get(None) != "public":
                raise CatalogSecurityError(
                    f"Conflicting schema_translate_map on session connection: {curr_map}"
                )
            conn.execution_options(schema_translate_map={None: "public"})
        except CatalogSecurityError:
            raise
        except Exception as e:
            raise CatalogSecurityError(
                f"Failed to ensure public schema qualification in fact snapshot reader: {e}"
            ) from e

    exec_opts: dict[str, Any] = {"populate_existing": True}
    if bind is not None and getattr(bind.dialect, "name", "") == "postgresql":
        exec_opts["schema_translate_map"] = {None: "public"}

    ver_row = session.execute(
        select(
            CatalogFactDefinitionVersion.id,
            CatalogFactDefinitionVersion.fact_definition_id,
            CatalogFactDefinitionVersion.revision,
            CatalogFactDefinitionVersion.version_label,
            CatalogFactDefinitionVersion.predecessor_id,
            CatalogFactDefinitionVersion.predecessor_revision,
            CatalogFactDefinitionVersion.label,
            CatalogFactDefinitionVersion.description,
            CatalogFactDefinitionVersion.collection_guidance,
            CatalogFactDefinitionVersion.value_type,
            CatalogFactDefinitionVersion.sensitivity,
            CatalogFactDefinitionVersion.effective_from,
            CatalogFactDefinitionVersion.effective_until,
            CatalogFactDefinitionVersion.status,
            CatalogFactDefinitionVersion.content_digest,
            CatalogFactDefinitionVersion.digest_schema,
            CatalogFactDefinitionVersion.created_at,
            CatalogFactDefinitionVersion.updated_at,
        )
        .where(CatalogFactDefinitionVersion.id == version_id)
        .execution_options(**exec_opts)
    ).one_or_none()

    if ver_row is None:
        raise CatalogNotFoundError(f"FactDefinitionVersion '{version_id}' not found in database")

    def_row = session.execute(
        select(
            CatalogFactDefinition.id,
            CatalogFactDefinition.fact_key,
            CatalogFactDefinition.status,
        )
        .where(CatalogFactDefinition.id == ver_row.fact_definition_id)
        .execution_options(**exec_opts)
    ).one_or_none()

    if def_row is None:
        raise CatalogInvariantError(
            f"Parent FactDefinition '{ver_row.fact_definition_id}' not found for version '{version_id}'"
        )

    scope_rows = session.execute(
        select(
            CatalogFactDefinitionScope.sequence,
            CatalogFactDefinitionScope.scope_type,
        )
        .where(CatalogFactDefinitionScope.fact_definition_version_id == version_id)
        .order_by(CatalogFactDefinitionScope.sequence.asc())
        .execution_options(**exec_opts)
    ).all()

    enum_rows = session.execute(
        select(
            CatalogFactDefinitionEnumValue.sequence,
            CatalogFactDefinitionEnumValue.code,
            CatalogFactDefinitionEnumValue.label,
        )
        .where(CatalogFactDefinitionEnumValue.fact_definition_version_id == version_id)
        .order_by(CatalogFactDefinitionEnumValue.sequence.asc())
        .execution_options(**exec_opts)
    ).all()

    # 1. Parent FactDefinition validation
    if def_row.id != ver_row.fact_definition_id:
        raise CatalogInvariantError(
            f"Parent fact definition ID mismatch: def {def_row.id} != ver {ver_row.fact_definition_id}"
        )
    if def_row.status != "Draft":
        raise CatalogInvariantError(
            f"Stored parent FactDefinition status is '{def_row.status}'; expected 'Draft'"
        )
    if not def_row.fact_key.startswith("synthetic_"):
        raise CatalogInvariantError(
            f"Stored parent FactDefinition fact_key '{def_row.fact_key}' missing required 'synthetic_' prefix"
        )
    if not (11 <= len(def_row.fact_key) <= 64):
        raise CatalogInvariantError(
            f"Stored parent FactDefinition fact_key length {len(def_row.fact_key)} outside 11..64 bounds"
        )
    if not FACT_KEY_PATTERN.match(def_row.fact_key):
        raise CatalogInvariantError(
            f"Stored parent FactDefinition fact_key '{def_row.fact_key}' does not match pattern"
        )

    # 2. FactDefinitionVersion scalar validation
    if ver_row.status != "Draft":
        raise CatalogInvariantError(
            f"Stored FactDefinitionVersion status is '{ver_row.status}'; expected 'Draft'"
        )
    if ver_row.digest_schema != FACT_DEFINITION_DIGEST_SCHEMA:
        raise CatalogInvariantError(
            f"Invalid digest schema '{ver_row.digest_schema}': expected '{FACT_DEFINITION_DIGEST_SCHEMA}'"
        )
    if not (1 <= ver_row.revision <= 32767):
        raise CatalogInvariantError(
            f"Stored FactDefinitionVersion revision {ver_row.revision} outside 1..32767 bounds"
        )
    if ver_row.value_type not in VALID_VALUE_TYPES:
        raise CatalogInvariantError(
            f"Stored value_type '{ver_row.value_type}' not in {sorted(VALID_VALUE_TYPES)}"
        )
    if ver_row.sensitivity not in VALID_SENSITIVITIES:
        raise CatalogInvariantError(
            f"Stored sensitivity '{ver_row.sensitivity}' not in {sorted(VALID_SENSITIVITIES)}"
        )
    if (
        not ver_row.version_label
        or ver_row.version_label != ver_row.version_label.strip()
        or not (1 <= len(ver_row.version_label) <= 64)
    ):
        raise CatalogInvariantError("Stored FactDefinitionVersion version_label invalid")
    if (
        not ver_row.label
        or ver_row.label != ver_row.label.strip()
        or not (1 <= len(ver_row.label) <= 256)
    ):
        raise CatalogInvariantError("Stored FactDefinitionVersion label invalid")
    if (
        not ver_row.description
        or ver_row.description != ver_row.description.strip()
        or not (1 <= len(ver_row.description) <= 4096)
    ):
        raise CatalogInvariantError("Stored FactDefinitionVersion description invalid")
    if ver_row.collection_guidance is not None:
        if ver_row.collection_guidance != ver_row.collection_guidance.strip() or not (
            1 <= len(ver_row.collection_guidance) <= 4096
        ):
            raise CatalogInvariantError("Stored FactDefinitionVersion collection_guidance invalid")
    if ver_row.effective_from and ver_row.effective_until:
        if ver_row.effective_until < ver_row.effective_from:
            raise CatalogInvariantError(
                "Stored FactDefinitionVersion effective_until precedes effective_from"
            )

    # 3. Scope children cardinality, sequence, unique types
    if not (1 <= len(scope_rows) <= 6):
        raise CatalogInvariantError(
            f"Stored aggregate has invalid allowed_scopes cardinality: expected 1..6 scopes, got {len(scope_rows)}"
        )
    expected_scope_seqs = list(range(1, len(scope_rows) + 1))
    actual_scope_seqs = [r.sequence for r in scope_rows]
    if actual_scope_seqs != expected_scope_seqs:
        raise CatalogInvariantError(
            f"Stored allowed_scopes sequences {actual_scope_seqs} are not contiguous 1-indexed {expected_scope_seqs}"
        )
    seen_scope_types = set()
    for sr in scope_rows:
        if sr.scope_type not in VALID_SCOPE_TYPES:
            raise CatalogInvariantError(
                f"Stored scope_type '{sr.scope_type}' not in {sorted(VALID_SCOPE_TYPES)}"
            )
        if sr.scope_type in seen_scope_types:
            raise CatalogInvariantError(
                f"Duplicate scope_type '{sr.scope_type}' in stored aggregate"
            )
        seen_scope_types.add(sr.scope_type)

    # 4. Enum children cardinality, sequence, code format, unique codes
    if ver_row.value_type == "enum":
        if not (1 <= len(enum_rows) <= 64):
            raise CatalogInvariantError(
                f"Stored aggregate with value_type='enum' has {len(enum_rows)} enum_values; expected 1..64"
            )
        expected_enum_seqs = list(range(1, len(enum_rows) + 1))
        actual_enum_seqs = [er.sequence for er in enum_rows]
        if actual_enum_seqs != expected_enum_seqs:
            raise CatalogInvariantError(
                f"Stored enum_values sequences {actual_enum_seqs} are not contiguous 1-indexed {expected_enum_seqs}"
            )
        seen_codes = set()
        for er in enum_rows:
            if not er.code or not ENUM_CODE_PATTERN.match(er.code) or not (1 <= len(er.code) <= 64):
                raise CatalogInvariantError(f"Stored enum code '{er.code}' invalid")
            if er.code in seen_codes:
                raise CatalogInvariantError(f"Duplicate enum code '{er.code}' in stored aggregate")
            seen_codes.add(er.code)
            if not er.label or er.label != er.label.strip() or not (1 <= len(er.label) <= 256):
                raise CatalogInvariantError(f"Stored enum label for code '{er.code}' invalid")
    else:
        if len(enum_rows) != 0:
            raise CatalogInvariantError(
                f"Stored aggregate with non-enum value_type='{ver_row.value_type}' contains {len(enum_rows)} enum_values"
            )

    # 5. Lineage and immediate same-definition predecessor validation
    if ver_row.revision == 1:
        if ver_row.predecessor_id is not None or ver_row.predecessor_revision is not None:
            raise CatalogInvariantError("Revision 1 stored version has non-null predecessor")
    else:
        if ver_row.predecessor_id is None or ver_row.predecessor_revision is None:
            raise CatalogInvariantError(
                f"Revision {ver_row.revision} stored version missing predecessor"
            )
        if ver_row.predecessor_revision != ver_row.revision - 1:
            raise CatalogInvariantError(
                f"Revision {ver_row.revision} stored version has predecessor_revision {ver_row.predecessor_revision}; expected {ver_row.revision - 1}"
            )
        pred_exists = session.execute(
            select(CatalogFactDefinitionVersion.id)
            .where(
                CatalogFactDefinitionVersion.id == ver_row.predecessor_id,
                CatalogFactDefinitionVersion.fact_definition_id == ver_row.fact_definition_id,
                CatalogFactDefinitionVersion.revision == ver_row.predecessor_revision,
            )
            .execution_options(**exec_opts)
        ).scalar_one_or_none()
        if pred_exists is None:
            raise CatalogInvariantError(
                f"Predecessor '{ver_row.predecessor_id}' revision {ver_row.predecessor_revision} does not exist in definition '{ver_row.fact_definition_id}'"
            )

    reconstructed_payload: dict[str, Any] = {
        "allowed_scopes": [
            {"scope_type": r.scope_type, "sequence": r.sequence} for r in scope_rows
        ],
        "collection_guidance": ver_row.collection_guidance,
        "description": ver_row.description,
        "effective_from": ver_row.effective_from.isoformat() if ver_row.effective_from else None,
        "effective_until": ver_row.effective_until.isoformat() if ver_row.effective_until else None,
        "enum_values": [
            {"code": r.code, "label": r.label, "sequence": r.sequence} for r in enum_rows
        ],
        "fact_definition_id": str(def_row.id).lower(),
        "fact_key": def_row.fact_key,
        "kind": "FactDefinitionVersion",
        "label": ver_row.label,
        "predecessor_id": str(ver_row.predecessor_id).lower() if ver_row.predecessor_id else None,
        "predecessor_revision": ver_row.predecessor_revision,
        "revision": ver_row.revision,
        "sensitivity": ver_row.sensitivity,
        "status": ver_row.status,
        "value_type": ver_row.value_type,
        "version_label": ver_row.version_label,
    }

    stored_digest = bytes(ver_row.content_digest)
    if len(stored_digest) != 32:
        raise CatalogInvariantError(
            f"Corrupted content digest in database: expected 32 bytes, got {len(stored_digest)}"
        )

    recomputed_digest = compute_content_digest(reconstructed_payload)
    if recomputed_digest != stored_digest:
        raise CatalogInvariantError(
            f"Persisted content digest mismatch: recomputed {recomputed_digest.hex()} != stored {stored_digest.hex()}"
        )

    if expected_digest is not None and recomputed_digest != expected_digest:
        raise CatalogInvariantError(
            f"Persisted digest mismatch against expected: {recomputed_digest.hex()} != {expected_digest.hex()}"
        )

    # Refresh cached ORM entity in identity map if present
    cached_ver = session.get(CatalogFactDefinitionVersion, version_id)
    if cached_ver is not None:
        session.refresh(cached_ver)

    return FactDefinitionVersionSnapshot(
        id=ver_row.id,
        fact_definition_id=def_row.id,
        fact_key=def_row.fact_key,
        revision=ver_row.revision,
        version_label=ver_row.version_label,
        predecessor_id=ver_row.predecessor_id,
        predecessor_revision=ver_row.predecessor_revision,
        label=ver_row.label,
        description=ver_row.description,
        collection_guidance=ver_row.collection_guidance,
        value_type=ver_row.value_type,
        sensitivity=ver_row.sensitivity,
        effective_from=ver_row.effective_from,
        effective_until=ver_row.effective_until,
        status=ver_row.status,
        content_digest=stored_digest,
        digest_schema=ver_row.digest_schema,
        allowed_scopes=tuple(
            FactDefinitionScopeSnapshot(sequence=r.sequence, scope_type=r.scope_type)
            for r in scope_rows
        ),
        enum_values=tuple(
            FactDefinitionEnumValueSnapshot(sequence=r.sequence, code=r.code, label=r.label)
            for r in enum_rows
        ),
        created_at=ver_row.created_at,
        updated_at=ver_row.updated_at,
    )
