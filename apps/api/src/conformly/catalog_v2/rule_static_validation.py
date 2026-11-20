"""Pure static AST and predicate validator for inert applicability rules.

This module provides pure static validation of Catalog V2 applicability rule ASTs
and caller-supplied pinned fact-definition metadata. It is strictly inert: it performs
no database access, filesystem IO, network IO, clock reading, environment access,
or rule evaluation.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from conformly.catalog_v2.digest import canonical_json

MAX_RAW_BYTES = 16384
MAX_DEPTH = 8
MAX_TOTAL_NODES = 64
MAX_CHILDREN = 16
MIN_CHILDREN = 2
MAX_IN_VALUES = 16
MIN_IN_VALUES = 1

VALID_OPS = frozenset({"ALL", "ANY", "NOT", "EXISTS", "EQUALS", "IN"})

VALID_VALUE_TYPES = frozenset(
    {
        "boolean",
        "integer",
        "decimal",
        "string",
        "date",
        "enum",
        "entity_reference",
    }
)

VALID_SCOPE_TYPES = frozenset(
    {
        "tenant",
        "legal_entity",
        "service",
        "processing_activity",
        "system",
        "location",
    }
)


@dataclass(frozen=True)
class FactVersionMetadata:
    """Metadata for a pinned fact definition version."""

    fact_definition_id: UUID
    value_type: str
    scope_types: frozenset[str]
    enum_codes: frozenset[str]


@dataclass(frozen=True)
class ValidatedRuleAst:
    """Result of static rule AST validation."""

    ast: dict[str, object]
    canonical_bytes: bytes
    fact_version_ids: tuple[UUID, ...]


class RuleValidationError(ValueError):
    """Validation error with stable error code and non-content-bearing message."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code
        self.__cause__ = None
        self.__suppress_context__ = True


def _parse_canonical_uuid(val: Any) -> UUID:
    """Validate canonical lower-case hyphenated 36-char UUID string."""
    if not isinstance(val, str) or len(val) != 36:
        raise RuleValidationError("Invalid UUID format", code="AST_SCHEMA")
    parsed: UUID | None = None
    try:
        parsed = UUID(val)
    except ValueError:
        pass
    if parsed is None:
        raise RuleValidationError("Invalid UUID format", code="AST_SCHEMA")
    if str(parsed) != val:
        raise RuleValidationError("UUID is not canonical lower-case format", code="AST_SCHEMA")
    return parsed


def _validate_metadata_entry(meta: FactVersionMetadata) -> None:
    """Validate that a referenced metadata entry conforms to schema requirements."""
    if not isinstance(meta.fact_definition_id, UUID):
        raise RuleValidationError("Invalid fact definition ID in metadata", code="FACT_METADATA")
    if type(meta.value_type) is not str or meta.value_type not in VALID_VALUE_TYPES:
        raise RuleValidationError("Invalid value type in metadata", code="FACT_METADATA")
    if (
        not isinstance(meta.scope_types, (set, frozenset))
        or len(meta.scope_types) == 0
        or any(type(s) is not str for s in meta.scope_types)
        or not meta.scope_types.issubset(VALID_SCOPE_TYPES)
    ):
        raise RuleValidationError("Invalid scope types in metadata", code="FACT_METADATA")
    if not isinstance(meta.enum_codes, (set, frozenset)) or any(
        type(c) is not str for c in meta.enum_codes
    ):
        raise RuleValidationError("Invalid enum codes in metadata", code="FACT_METADATA")
    if meta.value_type != "enum" and len(meta.enum_codes) > 0:
        raise RuleValidationError(
            "Enum codes must be empty for non-enum fact in metadata", code="FACT_METADATA"
        )


def validate_rule_ast(
    raw: bytes,
    fact_metadata: Mapping[UUID, FactVersionMetadata],
    ordered_fact_refs: Sequence[UUID],
) -> ValidatedRuleAst:
    """Validate raw applicability-rule AST bytes against pinned fact metadata."""
    # 1. Input type and size checks
    if type(raw) is not bytes:
        raise RuleValidationError("Raw rule AST input must be bytes", code="INPUT_TYPE")
    if len(raw) == 0 or len(raw) > MAX_RAW_BYTES:
        raise RuleValidationError("Raw rule AST size outside allowed bounds", code="INPUT_SIZE")

    # 2. Strict UTF-8 decoding and rejection of BOM
    if raw.startswith(b"\xef\xbb\xbf"):
        raise RuleValidationError("UTF-8 BOM is not permitted", code="JSON_INVALID")
    decoded_text: str | None = None
    try:
        decoded_text = raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    if decoded_text is None:
        raise RuleValidationError("Malformed UTF-8 encoding", code="JSON_INVALID")

    # 3. JSON parsing with duplicate key rejection and NaN/Infinity rejection
    def _object_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen = set()
        res = {}
        for k, v in pairs:
            if not isinstance(k, str):
                raise RuleValidationError("JSON object key must be string", code="JSON_INVALID")
            if k in seen:
                raise RuleValidationError("Duplicate key in JSON object", code="JSON_DUPLICATE_KEY")
            seen.add(k)
            res[k] = v
        return res

    def _reject_constant(_: str) -> None:
        raise RuleValidationError("JSON constants are not permitted", code="JSON_INVALID")

    parsed: Any = None
    json_error_code: str | None = None
    json_error_msg: str | None = None
    try:
        parsed = json.loads(
            decoded_text,
            object_pairs_hook=_object_pairs_hook,
            parse_constant=_reject_constant,
        )
    except RuleValidationError:
        raise
    except RecursionError:
        json_error_code = "AST_LIMIT"
        json_error_msg = "JSON parser recursion limit exceeded"
    except (json.JSONDecodeError, ValueError):
        json_error_code = "JSON_INVALID"
        json_error_msg = "Malformed JSON document"

    if json_error_code is not None and json_error_msg is not None:
        raise RuleValidationError(json_error_msg, code=json_error_code)

    # 4. Canonical byte equality
    canonical_bytes: bytes | None = None
    try:
        canonical_str = canonical_json(parsed)
        canonical_bytes = canonical_str.encode("utf-8")
    except Exception:
        pass

    if canonical_bytes is None:
        raise RuleValidationError(
            "Failed to compute canonical JSON representation", code="JSON_NONCANONICAL"
        )

    if raw != canonical_bytes:
        raise RuleValidationError(
            "Raw input bytes do not equal canonical JSON encoding", code="JSON_NONCANONICAL"
        )

    # 5. Metadata and ordered refs container validation
    if not isinstance(fact_metadata, Mapping):
        raise RuleValidationError("fact_metadata must be a mapping", code="FACT_METADATA")
    for meta_key, meta_val in fact_metadata.items():
        if not isinstance(meta_key, UUID):
            raise RuleValidationError("fact_metadata keys must be UUID", code="FACT_METADATA")
        if not isinstance(meta_val, FactVersionMetadata):
            raise RuleValidationError(
                "fact_metadata values must be FactVersionMetadata", code="FACT_METADATA"
            )

    if not isinstance(ordered_fact_refs, Sequence) or isinstance(ordered_fact_refs, (str, bytes)):
        raise RuleValidationError("ordered_fact_refs must be a sequence", code="FACT_REFERENCE")
    for ref in ordered_fact_refs:
        if not isinstance(ref, UUID):
            raise RuleValidationError("ordered_fact_refs items must be UUID", code="FACT_REFERENCE")

    # 6. Top-level AST document structure
    if not isinstance(parsed, dict):
        raise RuleValidationError("Top-level AST must be an object", code="AST_SCHEMA")
    if set(parsed.keys()) != {"ast_version", "root"}:
        raise RuleValidationError(
            "Top-level AST must have exactly ast_version and root", code="AST_SCHEMA"
        )
    if type(parsed["ast_version"]) is not int or parsed["ast_version"] != 1:
        raise RuleValidationError("ast_version must be integer 1", code="AST_SCHEMA")
    if not isinstance(parsed["root"], dict):
        raise RuleValidationError("root node must be an object", code="AST_SCHEMA")

    # 7. AST traversal and validation
    total_nodes = 0
    ordered_leaves: list[UUID] = []
    seen_leaves: set[UUID] = set()
    stable_fact_map: dict[UUID, UUID] = {}

    def _traverse_node(node: dict[str, Any], depth: int) -> None:
        nonlocal total_nodes
        if depth > MAX_DEPTH:
            raise RuleValidationError("AST depth limit exceeded", code="AST_LIMIT")
        if not isinstance(node, dict):
            raise RuleValidationError("AST node must be an object", code="AST_SCHEMA")
        total_nodes += 1
        if total_nodes > MAX_TOTAL_NODES:
            raise RuleValidationError("AST node count limit exceeded", code="AST_LIMIT")

        op = node.get("op")
        if not isinstance(op, str) or op not in VALID_OPS:
            raise RuleValidationError("Invalid or missing op in AST node", code="AST_SCHEMA")

        if op in ("ALL", "ANY"):
            if set(node.keys()) != {"op", "children"}:
                raise RuleValidationError("Invalid fields for ALL/ANY node", code="AST_SCHEMA")
            children = node["children"]
            if not isinstance(children, list) or isinstance(children, (str, bytes, dict)):
                raise RuleValidationError("ALL/ANY children must be an array", code="AST_SCHEMA")
            if not (MIN_CHILDREN <= len(children) <= MAX_CHILDREN):
                raise RuleValidationError(
                    "ALL/ANY children count must be between 2 and 16", code="AST_SCHEMA"
                )
            for child in children:
                if not isinstance(child, dict):
                    raise RuleValidationError("Child node must be an object", code="AST_SCHEMA")
                _traverse_node(child, depth + 1)

        elif op == "NOT":
            if set(node.keys()) != {"op", "child"}:
                raise RuleValidationError("Invalid fields for NOT node", code="AST_SCHEMA")
            child = node["child"]
            if not isinstance(child, dict):
                raise RuleValidationError("NOT child must be an object", code="AST_SCHEMA")
            _traverse_node(child, depth + 1)

        elif op == "EXISTS":
            if set(node.keys()) != {"op", "fact_definition_version_id", "scope_type"}:
                raise RuleValidationError("Invalid fields for EXISTS node", code="AST_SCHEMA")
            leaf_uuid = _parse_canonical_uuid(node["fact_definition_version_id"])
            scope_type = node["scope_type"]
            if not isinstance(scope_type, str) or scope_type not in VALID_SCOPE_TYPES:
                raise RuleValidationError("Invalid scope_type in EXISTS node", code="AST_SCHEMA")

            if leaf_uuid not in fact_metadata:
                raise RuleValidationError(
                    "Referenced fact version ID unknown in metadata", code="FACT_REFERENCE"
                )
            meta = fact_metadata[leaf_uuid]
            _validate_metadata_entry(meta)

            if scope_type not in meta.scope_types:
                raise RuleValidationError(
                    "scope_type not declared for fact version", code="AST_SCHEMA"
                )

            if meta.fact_definition_id in stable_fact_map:
                if stable_fact_map[meta.fact_definition_id] != leaf_uuid:
                    raise RuleValidationError(
                        "Multiple versions of same stable fact definition in rule",
                        code="FACT_REFERENCE",
                    )
            else:
                stable_fact_map[meta.fact_definition_id] = leaf_uuid

            if leaf_uuid not in seen_leaves:
                seen_leaves.add(leaf_uuid)
                ordered_leaves.append(leaf_uuid)

        elif op == "EQUALS":
            if set(node.keys()) != {"op", "fact_definition_version_id", "scope_type", "value"}:
                raise RuleValidationError("Invalid fields for EQUALS node", code="AST_SCHEMA")
            leaf_uuid = _parse_canonical_uuid(node["fact_definition_version_id"])
            scope_type = node["scope_type"]
            if not isinstance(scope_type, str) or scope_type not in VALID_SCOPE_TYPES:
                raise RuleValidationError("Invalid scope_type in EQUALS node", code="AST_SCHEMA")

            if leaf_uuid not in fact_metadata:
                raise RuleValidationError(
                    "Referenced fact version ID unknown in metadata", code="FACT_REFERENCE"
                )
            meta = fact_metadata[leaf_uuid]
            _validate_metadata_entry(meta)

            if scope_type not in meta.scope_types:
                raise RuleValidationError(
                    "scope_type not declared for fact version", code="AST_SCHEMA"
                )

            if meta.fact_definition_id in stable_fact_map:
                if stable_fact_map[meta.fact_definition_id] != leaf_uuid:
                    raise RuleValidationError(
                        "Multiple versions of same stable fact definition in rule",
                        code="FACT_REFERENCE",
                    )
            else:
                stable_fact_map[meta.fact_definition_id] = leaf_uuid

            if meta.value_type not in ("boolean", "enum"):
                raise RuleValidationError(
                    "EQUALS only supports boolean and enum value types", code="AST_SCHEMA"
                )
            value = node["value"]
            if meta.value_type == "boolean":
                if type(value) is not bool:
                    raise RuleValidationError(
                        "EQUALS on boolean fact requires boolean literal", code="AST_SCHEMA"
                    )
            elif meta.value_type == "enum":
                if not isinstance(value, str):
                    raise RuleValidationError(
                        "EQUALS on enum fact requires string value", code="AST_SCHEMA"
                    )
                if value not in meta.enum_codes:
                    raise RuleValidationError(
                        "EQUALS value is not a declared enum code", code="AST_SCHEMA"
                    )

            if leaf_uuid not in seen_leaves:
                seen_leaves.add(leaf_uuid)
                ordered_leaves.append(leaf_uuid)

        elif op == "IN":
            if set(node.keys()) != {"op", "fact_definition_version_id", "scope_type", "values"}:
                raise RuleValidationError("Invalid fields for IN node", code="AST_SCHEMA")
            leaf_uuid = _parse_canonical_uuid(node["fact_definition_version_id"])
            scope_type = node["scope_type"]
            if not isinstance(scope_type, str) or scope_type not in VALID_SCOPE_TYPES:
                raise RuleValidationError("Invalid scope_type in IN node", code="AST_SCHEMA")

            if leaf_uuid not in fact_metadata:
                raise RuleValidationError(
                    "Referenced fact version ID unknown in metadata", code="FACT_REFERENCE"
                )
            meta = fact_metadata[leaf_uuid]
            _validate_metadata_entry(meta)

            if scope_type not in meta.scope_types:
                raise RuleValidationError(
                    "scope_type not declared for fact version", code="AST_SCHEMA"
                )

            if meta.fact_definition_id in stable_fact_map:
                if stable_fact_map[meta.fact_definition_id] != leaf_uuid:
                    raise RuleValidationError(
                        "Multiple versions of same stable fact definition in rule",
                        code="FACT_REFERENCE",
                    )
            else:
                stable_fact_map[meta.fact_definition_id] = leaf_uuid

            if meta.value_type != "enum":
                raise RuleValidationError("IN only supports enum value type", code="AST_SCHEMA")

            values = node["values"]
            if not isinstance(values, list) or isinstance(values, (str, bytes, dict)):
                raise RuleValidationError("IN values must be an array", code="AST_SCHEMA")
            if not (MIN_IN_VALUES <= len(values) <= MAX_IN_VALUES):
                raise RuleValidationError(
                    "IN values count must be between 1 and 16", code="AST_SCHEMA"
                )

            seen_in_values = set()
            for val in values:
                if not isinstance(val, str):
                    raise RuleValidationError("IN values element must be string", code="AST_SCHEMA")
                if val in seen_in_values:
                    raise RuleValidationError("Duplicate enum code in IN values", code="AST_SCHEMA")
                seen_in_values.add(val)
                if val not in meta.enum_codes:
                    raise RuleValidationError(
                        "IN value is not a declared enum code", code="AST_SCHEMA"
                    )

            if leaf_uuid not in seen_leaves:
                seen_leaves.add(leaf_uuid)
                ordered_leaves.append(leaf_uuid)

    traversal_recursion_error = False
    try:
        _traverse_node(parsed["root"], depth=1)
    except RecursionError:
        traversal_recursion_error = True

    if traversal_recursion_error:
        raise RuleValidationError("AST depth limit exceeded by recursion", code="AST_LIMIT")

    # 8. Reference order checks
    if len(set(ordered_fact_refs)) != len(ordered_fact_refs):
        raise RuleValidationError("Duplicate UUID in ordered_fact_refs", code="FACT_REFERENCE")
    if list(ordered_fact_refs) != ordered_leaves:
        raise RuleValidationError(
            "ordered_fact_refs does not match preorder first-use references in AST",
            code="FACT_REFERENCE",
        )

    return ValidatedRuleAst(
        ast=parsed,
        canonical_bytes=canonical_bytes,
        fact_version_ids=tuple(ordered_leaves),
    )


__all__ = [
    "FactVersionMetadata",
    "ValidatedRuleAst",
    "RuleValidationError",
    "validate_rule_ast",
]
