"""Synthetic unit tests for pure static rule AST validator (WP-07C1).

Tests every positive construct, negative syntax/type error, boundary limit,
reference consistency rule, import boundary, and non-content-bearing error messages.
"""

import json
import sys
import traceback
from typing import Any
from uuid import UUID, uuid4

import pytest

from conformly.catalog_v2.digest import canonical_json
from conformly.catalog_v2.rule_static_validation import (
    FactVersionMetadata,
    RuleValidationError,
    ValidatedRuleAst,
    validate_rule_ast,
)


def _canonical_bytes(obj: object) -> bytes:
    """Encode object to canonical UTF-8 JSON bytes."""
    return canonical_json(obj).encode("utf-8")


def _make_meta(
    fact_def_id: UUID | None = None,
    value_type: str = "boolean",
    scope_types: frozenset[str] | None = None,
    enum_codes: frozenset[str] | None = None,
) -> FactVersionMetadata:
    """Create a synthetic FactVersionMetadata for testing."""
    return FactVersionMetadata(
        fact_definition_id=fact_def_id or uuid4(),
        value_type=value_type,
        scope_types=scope_types if scope_types is not None else frozenset({"tenant"}),
        enum_codes=enum_codes if enum_codes is not None else frozenset(),
    )


# ---------------------------------------------------------------------------
# Positive tests
# ---------------------------------------------------------------------------


def test_positive_exists_boolean_leaf() -> None:
    """Admit one canonical EXISTS Boolean leaf."""
    fv_id = uuid4()
    meta = _make_meta(value_type="boolean", scope_types=frozenset({"tenant"}))
    ast = {
        "ast_version": 1,
        "root": {
            "op": "EXISTS",
            "fact_definition_version_id": str(fv_id).lower(),
            "scope_type": "tenant",
        },
    }
    raw = _canonical_bytes(ast)
    res = validate_rule_ast(raw, {fv_id: meta}, [fv_id])
    assert isinstance(res, ValidatedRuleAst)
    assert res.canonical_bytes == raw
    assert res.fact_version_ids == (fv_id,)
    assert res.ast["ast_version"] == 1


def test_positive_all_exists_equals_true_tree() -> None:
    """Admit one canonical ALL(EXISTS, EQUALS true) tree with exact reference order."""
    fv_id1 = uuid4()
    fv_id2 = uuid4()
    meta1 = _make_meta(value_type="boolean", scope_types=frozenset({"tenant"}))
    meta2 = _make_meta(value_type="boolean", scope_types=frozenset({"system"}))

    ast = {
        "ast_version": 1,
        "root": {
            "op": "ALL",
            "children": [
                {
                    "op": "EXISTS",
                    "fact_definition_version_id": str(fv_id1).lower(),
                    "scope_type": "tenant",
                },
                {
                    "op": "EQUALS",
                    "fact_definition_version_id": str(fv_id2).lower(),
                    "scope_type": "system",
                    "value": True,
                },
            ],
        },
    }
    raw = _canonical_bytes(ast)
    meta_map = {fv_id1: meta1, fv_id2: meta2}
    refs = [fv_id1, fv_id2]
    res = validate_rule_ast(raw, meta_map, refs)
    assert res.fact_version_ids == (fv_id1, fv_id2)


def test_positive_in_enum_leaf_authored_order() -> None:
    """Admit an enum IN leaf with two declared codes in authored order."""
    fv_id = uuid4()
    meta = _make_meta(
        value_type="enum",
        scope_types=frozenset({"tenant"}),
        enum_codes=frozenset({"code_a", "code_b", "code_c"}),
    )
    ast = {
        "ast_version": 1,
        "root": {
            "op": "IN",
            "fact_definition_version_id": str(fv_id).lower(),
            "scope_type": "tenant",
            "values": ["code_b", "code_a"],
        },
    }
    raw = _canonical_bytes(ast)
    res = validate_rule_ast(raw, {fv_id: meta}, [fv_id])
    assert res.fact_version_ids == (fv_id,)


def test_positive_distinct_in_orders_produce_distinct_canonical_bytes() -> None:
    """Reordering IN values produces different canonical bytes but both remain valid."""
    fv_id = uuid4()
    meta = _make_meta(
        value_type="enum",
        scope_types=frozenset({"tenant"}),
        enum_codes=frozenset({"code_a", "code_b"}),
    )
    ast1 = {
        "ast_version": 1,
        "root": {
            "op": "IN",
            "fact_definition_version_id": str(fv_id).lower(),
            "scope_type": "tenant",
            "values": ["code_a", "code_b"],
        },
    }
    ast2 = {
        "ast_version": 1,
        "root": {
            "op": "IN",
            "fact_definition_version_id": str(fv_id).lower(),
            "scope_type": "tenant",
            "values": ["code_b", "code_a"],
        },
    }
    raw1 = _canonical_bytes(ast1)
    raw2 = _canonical_bytes(ast2)
    assert raw1 != raw2

    res1 = validate_rule_ast(raw1, {fv_id: meta}, [fv_id])
    res2 = validate_rule_ast(raw2, {fv_id: meta}, [fv_id])
    assert res1.canonical_bytes == raw1
    assert res2.canonical_bytes == raw2


def test_positive_any_and_not_operators() -> None:
    """Admit valid ANY and NOT operators."""
    fv_id1 = uuid4()
    fv_id2 = uuid4()
    meta1 = _make_meta(value_type="boolean", scope_types=frozenset({"service"}))
    meta2 = _make_meta(value_type="boolean", scope_types=frozenset({"location"}))

    ast = {
        "ast_version": 1,
        "root": {
            "op": "ANY",
            "children": [
                {
                    "op": "NOT",
                    "child": {
                        "op": "EXISTS",
                        "fact_definition_version_id": str(fv_id1).lower(),
                        "scope_type": "service",
                    },
                },
                {
                    "op": "EXISTS",
                    "fact_definition_version_id": str(fv_id2).lower(),
                    "scope_type": "location",
                },
            ],
        },
    }
    raw = _canonical_bytes(ast)
    res = validate_rule_ast(raw, {fv_id1: meta1, fv_id2: meta2}, [fv_id1, fv_id2])
    assert res.fact_version_ids == (fv_id1, fv_id2)


def test_positive_repeated_fact_leaf_reuses_reference() -> None:
    """Repeated leaf may reuse one reference row; preorder order counts first appearance."""
    fv_id1 = uuid4()
    fv_id2 = uuid4()
    meta1 = _make_meta(value_type="boolean", scope_types=frozenset({"tenant"}))
    meta2 = _make_meta(value_type="boolean", scope_types=frozenset({"tenant"}))

    ast = {
        "ast_version": 1,
        "root": {
            "op": "ALL",
            "children": [
                {
                    "op": "EXISTS",
                    "fact_definition_version_id": str(fv_id1).lower(),
                    "scope_type": "tenant",
                },
                {
                    "op": "EXISTS",
                    "fact_definition_version_id": str(fv_id2).lower(),
                    "scope_type": "tenant",
                },
                {
                    "op": "EQUALS",
                    "fact_definition_version_id": str(fv_id1).lower(),
                    "scope_type": "tenant",
                    "value": True,
                },
            ],
        },
    }
    raw = _canonical_bytes(ast)
    res = validate_rule_ast(raw, {fv_id1: meta1, fv_id2: meta2}, [fv_id1, fv_id2])
    assert res.fact_version_ids == (fv_id1, fv_id2)


def test_positive_extra_unused_metadata_permitted() -> None:
    """Extra unused metadata entries in fact_metadata are permitted."""
    fv_id1 = uuid4()
    fv_unused = uuid4()
    meta1 = _make_meta(value_type="boolean", scope_types=frozenset({"tenant"}))
    meta_unused = _make_meta(value_type="string", scope_types=frozenset({"system"}))

    ast = {
        "ast_version": 1,
        "root": {
            "op": "EXISTS",
            "fact_definition_version_id": str(fv_id1).lower(),
            "scope_type": "tenant",
        },
    }
    raw = _canonical_bytes(ast)
    res = validate_rule_ast(raw, {fv_id1: meta1, fv_unused: meta_unused}, [fv_id1])
    assert res.fact_version_ids == (fv_id1,)


def test_positive_exists_across_all_seven_value_types() -> None:
    """EXISTS may refer to any of WP-07B's seven declared value types."""
    value_types = [
        "boolean",
        "integer",
        "decimal",
        "string",
        "date",
        "enum",
        "entity_reference",
    ]
    meta_map = {}
    refs = []
    children = []
    for vt in value_types:
        fv_id = uuid4()
        enum_codes = frozenset({"alpha"}) if vt == "enum" else frozenset()
        meta = _make_meta(value_type=vt, scope_types=frozenset({"tenant"}), enum_codes=enum_codes)
        meta_map[fv_id] = meta
        refs.append(fv_id)
        children.append(
            {
                "op": "EXISTS",
                "fact_definition_version_id": str(fv_id).lower(),
                "scope_type": "tenant",
            }
        )

    ast = {
        "ast_version": 1,
        "root": {"op": "ALL", "children": children},
    }
    raw = _canonical_bytes(ast)
    res = validate_rule_ast(raw, meta_map, refs)
    assert res.fact_version_ids == tuple(refs)


def test_positive_equals_on_enum_fact() -> None:
    """EQUALS with enum fact and valid declared enum code."""
    fv_id = uuid4()
    meta = _make_meta(
        value_type="enum",
        scope_types=frozenset({"legal_entity"}),
        enum_codes=frozenset({"ACTIVE", "INACTIVE"}),
    )
    ast = {
        "ast_version": 1,
        "root": {
            "op": "EQUALS",
            "fact_definition_version_id": str(fv_id).lower(),
            "scope_type": "legal_entity",
            "value": "ACTIVE",
        },
    }
    raw = _canonical_bytes(ast)
    res = validate_rule_ast(raw, {fv_id: meta}, [fv_id])
    assert res.fact_version_ids == (fv_id,)


def test_positive_boundary_depth_eight() -> None:
    """Tree at boundary depth exactly 8 is admitted."""
    fv_id = uuid4()
    meta = _make_meta()
    leaf = {
        "op": "EXISTS",
        "fact_definition_version_id": str(fv_id).lower(),
        "scope_type": "tenant",
    }
    # Depth 1: NOT, Depth 2: NOT, ..., Depth 7: NOT, Depth 8: leaf
    node: dict[str, Any] = leaf
    for _ in range(7):
        node = {"op": "NOT", "child": node}

    ast = {"ast_version": 1, "root": node}
    raw = _canonical_bytes(ast)
    res = validate_rule_ast(raw, {fv_id: meta}, [fv_id])
    assert res.fact_version_ids == (fv_id,)


def test_positive_boundary_sixty_four_nodes() -> None:
    """Tree with exactly 64 nodes is admitted."""
    fv_id = uuid4()
    meta = _make_meta()
    leaf = {
        "op": "EXISTS",
        "fact_definition_version_id": str(fv_id).lower(),
        "scope_type": "tenant",
    }
    # 1 root ALL with 3 children:
    # Child 0: ALL with 16 leaves (1 + 16 = 17)
    # Child 1: ALL with 16 leaves (1 + 16 = 17)
    # Child 2: ALL with 16 leaves (1 + 16 = 17)
    # Child 3: ALL with 11 leaves (1 + 11 = 12)
    # Total nodes: 1 (root) + (1+16) + (1+16) + (1+16) + (1+11) = 1 + 17 + 17 + 17 + 12 = 64 nodes.
    ast = {
        "ast_version": 1,
        "root": {
            "op": "ALL",
            "children": [
                {"op": "ALL", "children": [leaf for _ in range(16)]},
                {"op": "ALL", "children": [leaf for _ in range(16)]},
                {"op": "ALL", "children": [leaf for _ in range(16)]},
                {"op": "ALL", "children": [leaf for _ in range(11)]},
            ],
        },
    }
    raw = _canonical_bytes(ast)
    res = validate_rule_ast(raw, {fv_id: meta}, [fv_id])
    assert res.fact_version_ids == (fv_id,)


def test_positive_caller_inputs_not_mutated() -> None:
    """Caller metadata and ordered reference sequences are not mutated."""
    fv_id = uuid4()
    meta = _make_meta()
    meta_map = {fv_id: meta}
    refs = [fv_id]

    ast = {
        "ast_version": 1,
        "root": {
            "op": "EXISTS",
            "fact_definition_version_id": str(fv_id).lower(),
            "scope_type": "tenant",
        },
    }
    raw = _canonical_bytes(ast)
    validate_rule_ast(raw, meta_map, refs)
    assert meta_map == {fv_id: meta}
    assert refs == [fv_id]


# ---------------------------------------------------------------------------
# Negative tests: INPUT_TYPE and INPUT_SIZE
# ---------------------------------------------------------------------------


def test_negative_input_type_non_bytes() -> None:
    """Reject non-bytes inputs with INPUT_TYPE."""
    for bad in ["string", 123, {"a": 1}, None, ["bytes"]]:
        with pytest.raises(RuleValidationError) as exc:
            validate_rule_ast(bad, {}, [])  # type: ignore[arg-type]
        assert exc.value.code == "INPUT_TYPE"


def test_negative_input_size_empty() -> None:
    """Reject empty bytes with INPUT_SIZE."""
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(b"", {}, [])
    assert exc.value.code == "INPUT_SIZE"


def test_negative_input_size_exceeds_16384_bytes() -> None:
    """Reject original input longer than 16,384 bytes with INPUT_SIZE."""
    too_large = b" " * 16385
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(too_large, {}, [])
    assert exc.value.code == "INPUT_SIZE"


# ---------------------------------------------------------------------------
# Negative tests: JSON_INVALID and JSON_DUPLICATE_KEY
# ---------------------------------------------------------------------------


def test_negative_json_invalid_malformed_utf8() -> None:
    """Reject malformed UTF-8 with JSON_INVALID."""
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(bytes([0xFF, 0xFE, 0x00, 0x00]), {}, [])
    assert exc.value.code == "JSON_INVALID"


def test_negative_json_invalid_utf8_bom() -> None:
    """Reject UTF-8 BOM with JSON_INVALID."""
    bom_data = bytes([0xEF, 0xBB, 0xBF]) + _canonical_bytes({"ast_version": 1, "root": {}})
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(bom_data, {}, [])
    assert exc.value.code == "JSON_INVALID"


def test_negative_json_invalid_syntax_error() -> None:
    """Reject JSON syntax errors with JSON_INVALID."""
    for bad in [b"{", b"{bad json}", b"not json at all"]:
        with pytest.raises(RuleValidationError) as exc:
            validate_rule_ast(bad, {}, [])
        assert exc.value.code == "JSON_INVALID"


def test_negative_json_invalid_trailing_data() -> None:
    """Reject trailing JSON data with JSON_INVALID."""
    raw = _canonical_bytes({"ast_version": 1, "root": {}}) + b" trailing"
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {}, [])
    assert exc.value.code == "JSON_INVALID"


def test_negative_json_invalid_constants() -> None:
    """Reject NaN, Infinity, -Infinity with JSON_INVALID."""
    for c in [b'{"ast_version":NaN}', b'{"ast_version":Infinity}', b'{"ast_version":-Infinity}']:
        with pytest.raises(RuleValidationError) as exc:
            validate_rule_ast(c, {}, [])
        assert exc.value.code == "JSON_INVALID"


def test_negative_json_duplicate_key_root() -> None:
    """Reject duplicate keys at root with JSON_DUPLICATE_KEY."""
    raw = b'{"ast_version":1,"ast_version":1,"root":{"op":"EXISTS"}}'
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {}, [])
    assert exc.value.code == "JSON_DUPLICATE_KEY"


def test_negative_json_duplicate_key_node() -> None:
    """Reject duplicate keys inside an AST node with JSON_DUPLICATE_KEY."""
    fv_id = uuid4()
    raw = (
        b'{"ast_version":1,"root":{"op":"EXISTS","op":"EXISTS","fact_definition_version_id":"'
        + str(fv_id).encode("utf-8")
        + b'","scope_type":"tenant"}}'
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {}, [])
    assert exc.value.code == "JSON_DUPLICATE_KEY"


# ---------------------------------------------------------------------------
# Negative tests: JSON_NONCANONICAL
# ---------------------------------------------------------------------------


def test_negative_json_noncanonical_whitespace() -> None:
    """Reject alternate whitespace with JSON_NONCANONICAL."""
    fv_id = uuid4()
    meta = _make_meta()
    # Spaces around colons or braces
    raw = (
        b'{"ast_version": 1, "root": {"op": "EXISTS", "fact_definition_version_id": "'
        + str(fv_id).encode("utf-8")
        + b'", "scope_type": "tenant"}}'
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta}, [fv_id])
    assert exc.value.code == "JSON_NONCANONICAL"


def test_negative_json_noncanonical_key_ordering() -> None:
    """Reject unsorted keys with JSON_NONCANONICAL."""
    fv_id = uuid4()
    meta = _make_meta()
    # root before ast_version
    raw = (
        b'{"root":{"fact_definition_version_id":"'
        + str(fv_id).encode("utf-8")
        + b'","op":"EXISTS","scope_type":"tenant"},"ast_version":1}'
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta}, [fv_id])
    assert exc.value.code == "JSON_NONCANONICAL"


def test_negative_json_noncanonical_unicode_escapes() -> None:
    """Reject unnecessary Unicode escapes with JSON_NONCANONICAL."""
    fv_id = uuid4()
    meta = _make_meta()
    raw = (
        b'{"ast_version":1,"root":{"fact_definition_version_id":"'
        + str(fv_id).encode("utf-8")
        + b'","op":"\\u0045XISTS","scope_type":"tenant"}}'
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta}, [fv_id])
    assert exc.value.code == "JSON_NONCANONICAL"


# ---------------------------------------------------------------------------
# Negative tests: AST_LIMIT
# ---------------------------------------------------------------------------


def test_negative_ast_limit_depth_nine() -> None:
    """Reject depth 9 with AST_LIMIT."""
    fv_id = uuid4()
    meta = _make_meta()
    leaf = {
        "op": "EXISTS",
        "fact_definition_version_id": str(fv_id).lower(),
        "scope_type": "tenant",
    }
    # 8 NOT wrappers + 1 leaf = depth 9
    node: dict[str, Any] = leaf
    for _ in range(8):
        node = {"op": "NOT", "child": node}

    raw = _canonical_bytes({"ast_version": 1, "root": node})
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_LIMIT"


def test_negative_ast_limit_sixty_five_nodes() -> None:
    """Reject 65 nodes with AST_LIMIT."""
    fv_id = uuid4()
    meta = _make_meta()
    leaf = {
        "op": "EXISTS",
        "fact_definition_version_id": str(fv_id).lower(),
        "scope_type": "tenant",
    }
    # Root ALL + 4 children:
    # 3 children with 16 leaves (1+16 = 17 each -> 51)
    # 1 child with 12 leaves (1+12 = 13)
    # Total: 1 + 51 + 13 = 65 nodes.
    ast = {
        "ast_version": 1,
        "root": {
            "op": "ALL",
            "children": [
                {"op": "ALL", "children": [leaf for _ in range(16)]},
                {"op": "ALL", "children": [leaf for _ in range(16)]},
                {"op": "ALL", "children": [leaf for _ in range(16)]},
                {"op": "ALL", "children": [leaf for _ in range(12)]},
            ],
        },
    }
    raw = _canonical_bytes(ast)
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_LIMIT"


def test_negative_ast_limit_parser_recursion_overflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject JSON parser recursion overflow as AST_LIMIT."""

    def mock_loads(*args: object, **kwargs: object) -> object:
        raise RecursionError("maximum recursion depth exceeded")

    monkeypatch.setattr(json, "loads", mock_loads)
    raw = _canonical_bytes({"ast_version": 1, "root": {}})
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {}, [])
    assert exc.value.code == "AST_LIMIT"


# ---------------------------------------------------------------------------
# Negative tests: AST_SCHEMA
# ---------------------------------------------------------------------------


def test_negative_ast_schema_top_level_not_dict() -> None:
    """Reject top-level non-dict JSON document with AST_SCHEMA."""
    for val in [1, "string", [1, 2]]:
        raw = _canonical_bytes(val)
        with pytest.raises(RuleValidationError) as exc:
            validate_rule_ast(raw, {}, [])
        assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_top_level_missing_or_extra_keys() -> None:
    """Reject top-level keys mismatch with AST_SCHEMA."""
    fv_id = uuid4()
    meta = _make_meta()
    leaf = {
        "op": "EXISTS",
        "fact_definition_version_id": str(fv_id).lower(),
        "scope_type": "tenant",
    }
    # Missing root
    raw1 = _canonical_bytes({"ast_version": 1})
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw1, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"

    # Missing ast_version
    raw2 = _canonical_bytes({"root": leaf})
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw2, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"

    # Extra key
    raw3 = _canonical_bytes({"ast_version": 1, "extra": True, "root": leaf})
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw3, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_boolean_ast_version() -> None:
    """Reject boolean True as ast_version with AST_SCHEMA."""
    fv_id = uuid4()
    meta = _make_meta()
    leaf = {
        "op": "EXISTS",
        "fact_definition_version_id": str(fv_id).lower(),
        "scope_type": "tenant",
    }
    raw = _canonical_bytes({"ast_version": True, "root": leaf})
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_wrong_ast_version_integer() -> None:
    """Reject ast_version != 1 with AST_SCHEMA."""
    fv_id = uuid4()
    meta = _make_meta()
    leaf = {
        "op": "EXISTS",
        "fact_definition_version_id": str(fv_id).lower(),
        "scope_type": "tenant",
    }
    raw = _canonical_bytes({"ast_version": 2, "root": leaf})
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_root_not_dict() -> None:
    """Reject non-dict root with AST_SCHEMA."""
    for bad in [None, [1, 2], "leaf", 42]:
        raw = _canonical_bytes({"ast_version": 1, "root": bad})
        with pytest.raises(RuleValidationError) as exc:
            validate_rule_ast(raw, {}, [])
        assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_unknown_or_missing_op() -> None:
    """Reject missing or unknown operator with AST_SCHEMA."""
    fv_id = uuid4()
    meta = _make_meta()
    # Missing op
    raw1 = _canonical_bytes(
        {"ast_version": 1, "root": {"fact_definition_version_id": str(fv_id).lower()}}
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw1, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"

    # Unknown op
    raw2 = _canonical_bytes({"ast_version": 1, "root": {"op": "XOR"}})
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw2, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_extra_script_template_function_fields() -> None:
    """Reject script, template, function, or unknown fields with AST_SCHEMA."""
    fv_id = uuid4()
    meta = _make_meta()
    for field in ["script", "template", "function", "extra_field"]:
        ast = {
            "ast_version": 1,
            "root": {
                "fact_definition_version_id": str(fv_id).lower(),
                "op": "EXISTS",
                "scope_type": "tenant",
                field: "malicious_code",
            },
        }
        raw = _canonical_bytes(ast)
        with pytest.raises(RuleValidationError) as exc:
            validate_rule_ast(raw, {fv_id: meta}, [fv_id])
        assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_all_any_children_limits() -> None:
    """Reject ALL/ANY with 0, 1, or 17 children with AST_SCHEMA."""
    fv_id = uuid4()
    meta = _make_meta()
    leaf = {
        "op": "EXISTS",
        "fact_definition_version_id": str(fv_id).lower(),
        "scope_type": "tenant",
    }

    for op in ["ALL", "ANY"]:
        # 0 children
        raw0 = _canonical_bytes({"ast_version": 1, "root": {"children": [], "op": op}})
        with pytest.raises(RuleValidationError) as exc:
            validate_rule_ast(raw0, {fv_id: meta}, [fv_id])
        assert exc.value.code == "AST_SCHEMA"

        # 1 child
        raw1 = _canonical_bytes({"ast_version": 1, "root": {"children": [leaf], "op": op}})
        with pytest.raises(RuleValidationError) as exc:
            validate_rule_ast(raw1, {fv_id: meta}, [fv_id])
        assert exc.value.code == "AST_SCHEMA"

        # 17 children
        raw17 = _canonical_bytes({"ast_version": 1, "root": {"children": [leaf] * 17, "op": op}})
        with pytest.raises(RuleValidationError) as exc:
            validate_rule_ast(raw17, {fv_id: meta}, [fv_id])
        assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_not_missing_or_extra_child() -> None:
    """Reject NOT with missing child or extra child with AST_SCHEMA."""
    fv_id = uuid4()
    meta = _make_meta()
    leaf = {
        "op": "EXISTS",
        "fact_definition_version_id": str(fv_id).lower(),
        "scope_type": "tenant",
    }

    # Missing child
    raw1 = _canonical_bytes({"ast_version": 1, "root": {"op": "NOT"}})
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw1, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"

    # Extra field
    raw2 = _canonical_bytes({"ast_version": 1, "root": {"child": leaf, "extra": 1, "op": "NOT"}})
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw2, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_non_canonical_uuid() -> None:
    """Reject non-canonical UUID string formats with AST_SCHEMA."""
    meta = _make_meta()
    fv_id = uuid4()
    bad_uuids = [
        str(fv_id).upper(),  # uppercase
        str(fv_id).replace("-", ""),  # 32 chars without hyphens
        f"{{{fv_id}}}",  # curly braces
        "invalid-uuid-format-length-36-xxxxxx",
        "not-a-uuid",
    ]
    for bad in bad_uuids:
        ast = {
            "ast_version": 1,
            "root": {
                "fact_definition_version_id": bad,
                "op": "EXISTS",
                "scope_type": "tenant",
            },
        }
        raw = _canonical_bytes(ast)
        with pytest.raises(RuleValidationError) as exc:
            validate_rule_ast(raw, {fv_id: meta}, [fv_id])
        assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_invalid_scope_type() -> None:
    """Reject scope_type not in the 6 declared scope types with AST_SCHEMA."""
    fv_id = uuid4()
    meta = _make_meta()
    ast = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fv_id).lower(),
            "op": "EXISTS",
            "scope_type": "global_scope",
        },
    }
    raw = _canonical_bytes(ast)
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_undeclared_scope_type() -> None:
    """Reject scope_type that is valid globally but undeclared on this fact version."""
    fv_id = uuid4()
    # Fact version only declared for "tenant"
    meta = _make_meta(scope_types=frozenset({"tenant"}))
    ast = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fv_id).lower(),
            "op": "EXISTS",
            "scope_type": "service",
        },
    }
    raw = _canonical_bytes(ast)
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_equals_unsupported_value_type() -> None:
    """EQUALS only supports boolean and enum; reject others with AST_SCHEMA."""
    for vt in ["string", "integer", "decimal", "date", "entity_reference"]:
        fv_id = uuid4()
        meta = _make_meta(value_type=vt)
        ast = {
            "ast_version": 1,
            "root": {
                "fact_definition_version_id": str(fv_id).lower(),
                "op": "EQUALS",
                "scope_type": "tenant",
                "value": "something",
            },
        }
        raw = _canonical_bytes(ast)
        with pytest.raises(RuleValidationError) as exc:
            validate_rule_ast(raw, {fv_id: meta}, [fv_id])
        assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_equals_boolean_wrong_literal_types() -> None:
    """Reject integer 1, string 'true', etc. for boolean EQUALS with AST_SCHEMA."""
    fv_id = uuid4()
    meta = _make_meta(value_type="boolean")
    for bad_val in [1, 0, "true", "false", None]:
        ast = {
            "ast_version": 1,
            "root": {
                "fact_definition_version_id": str(fv_id).lower(),
                "op": "EQUALS",
                "scope_type": "tenant",
                "value": bad_val,
            },
        }
        raw = _canonical_bytes(ast)
        with pytest.raises(RuleValidationError) as exc:
            validate_rule_ast(raw, {fv_id: meta}, [fv_id])
        assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_equals_enum_wrong_type_or_undeclared_code() -> None:
    """Reject non-string or undeclared enum code for enum EQUALS with AST_SCHEMA."""
    fv_id = uuid4()
    meta = _make_meta(value_type="enum", enum_codes=frozenset({"A", "B"}))

    # Non-string value (int)
    ast1 = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fv_id).lower(),
            "op": "EQUALS",
            "scope_type": "tenant",
            "value": 1,
        },
    }
    raw1 = _canonical_bytes(ast1)
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw1, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"

    # Undeclared code
    ast2 = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fv_id).lower(),
            "op": "EQUALS",
            "scope_type": "tenant",
            "value": "UNKNOWN_CODE",
        },
    }
    raw2 = _canonical_bytes(ast2)
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw2, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_in_on_non_enum() -> None:
    """Reject IN operator on non-enum fact with AST_SCHEMA."""
    fv_id = uuid4()
    meta = _make_meta(value_type="string")
    ast = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fv_id).lower(),
            "op": "IN",
            "scope_type": "tenant",
            "values": ["code1"],
        },
    }
    raw = _canonical_bytes(ast)
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"


def test_negative_ast_schema_in_values_limits_and_duplicates() -> None:
    """Reject IN with 0 values, 17 values, duplicate values, or undeclared code."""
    fv_id = uuid4()
    codes = [f"c{i}" for i in range(20)]
    meta = _make_meta(value_type="enum", enum_codes=frozenset(codes))

    # 0 values
    ast0 = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fv_id).lower(),
            "op": "IN",
            "scope_type": "tenant",
            "values": [],
        },
    }
    raw0 = _canonical_bytes(ast0)
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw0, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"

    # 17 values
    ast17 = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fv_id).lower(),
            "op": "IN",
            "scope_type": "tenant",
            "values": codes[:17],
        },
    }
    raw17 = _canonical_bytes(ast17)
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw17, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"

    # Duplicate enum code
    ast_dup = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fv_id).lower(),
            "op": "IN",
            "scope_type": "tenant",
            "values": ["c0", "c0"],
        },
    }
    raw_dup = _canonical_bytes(ast_dup)
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw_dup, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"

    # Undeclared enum code
    ast_und = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fv_id).lower(),
            "op": "IN",
            "scope_type": "tenant",
            "values": ["c0", "undeclared_code"],
        },
    }
    raw_und = _canonical_bytes(ast_und)
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw_und, {fv_id: meta}, [fv_id])
    assert exc.value.code == "AST_SCHEMA"


# ---------------------------------------------------------------------------
# Negative tests: FACT_METADATA
# ---------------------------------------------------------------------------


def test_negative_fact_metadata_container_types() -> None:
    """Reject non-Mapping, stringly typed keys, or non-FactVersionMetadata values."""
    fv_id = uuid4()
    meta = _make_meta()

    ast = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fv_id).lower(),
            "op": "EXISTS",
            "scope_type": "tenant",
        },
    }
    raw = _canonical_bytes(ast)

    # fact_metadata is list, not Mapping
    bad_list: Any = [meta]
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, bad_list, [fv_id])
    assert exc.value.code == "FACT_METADATA"

    # key is string instead of UUID
    bad_map_key: Any = {str(fv_id): meta}
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, bad_map_key, [fv_id])
    assert exc.value.code == "FACT_METADATA"

    # value is dict instead of FactVersionMetadata
    bad_map_val: Any = {fv_id: {"fact_definition_id": uuid4()}}
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, bad_map_val, [fv_id])
    assert exc.value.code == "FACT_METADATA"


def test_negative_fact_metadata_entry_validation() -> None:
    """Reject invalid fields in referenced metadata entry with FACT_METADATA."""
    fv_id = uuid4()
    ast = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fv_id).lower(),
            "op": "EXISTS",
            "scope_type": "tenant",
        },
    }
    raw = _canonical_bytes(ast)

    # Invalid fact_definition_id (string not UUID)
    meta_bad_id = FactVersionMetadata(
        fact_definition_id="not-a-uuid",  # type: ignore[arg-type]
        value_type="boolean",
        scope_types=frozenset({"tenant"}),
        enum_codes=frozenset(),
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta_bad_id}, [fv_id])
    assert exc.value.code == "FACT_METADATA"

    # Invalid value_type
    meta_bad_vt = FactVersionMetadata(
        fact_definition_id=uuid4(),
        value_type="blob",
        scope_types=frozenset({"tenant"}),
        enum_codes=frozenset(),
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta_bad_vt}, [fv_id])
    assert exc.value.code == "FACT_METADATA"

    # Empty scope_types
    meta_empty_scopes = FactVersionMetadata(
        fact_definition_id=uuid4(),
        value_type="boolean",
        scope_types=frozenset(),
        enum_codes=frozenset(),
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta_empty_scopes}, [fv_id])
    assert exc.value.code == "FACT_METADATA"

    # Non-enum fact with non-empty enum_codes
    meta_bad_codes = FactVersionMetadata(
        fact_definition_id=uuid4(),
        value_type="boolean",
        scope_types=frozenset({"tenant"}),
        enum_codes=frozenset({"code"}),
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta_bad_codes}, [fv_id])
    assert exc.value.code == "FACT_METADATA"


# ---------------------------------------------------------------------------
# Negative tests: FACT_REFERENCE
# ---------------------------------------------------------------------------


def test_negative_fact_reference_container_types() -> None:
    """Reject non-Sequence or stringly typed items in ordered_fact_refs with FACT_REFERENCE."""
    fv_id = uuid4()
    meta = _make_meta()
    ast = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fv_id).lower(),
            "op": "EXISTS",
            "scope_type": "tenant",
        },
    }
    raw = _canonical_bytes(ast)

    # String items instead of UUID
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta}, [str(fv_id)])  # type: ignore[list-item]
    assert exc.value.code == "FACT_REFERENCE"

    # Not a sequence
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta}, 12345)  # type: ignore[arg-type]
    assert exc.value.code == "FACT_REFERENCE"


def test_negative_fact_reference_unknown_fact_version() -> None:
    """Reject referenced fact version ID not present in metadata with FACT_REFERENCE."""
    fv_id = uuid4()
    ast = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fv_id).lower(),
            "op": "EXISTS",
            "scope_type": "tenant",
        },
    }
    raw = _canonical_bytes(ast)
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {}, [fv_id])
    assert exc.value.code == "FACT_REFERENCE"


def test_negative_fact_reference_duplicate_in_ordered_refs() -> None:
    """Reject duplicate UUID in ordered_fact_refs with FACT_REFERENCE."""
    fv_id = uuid4()
    meta = _make_meta()
    ast = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fv_id).lower(),
            "op": "EXISTS",
            "scope_type": "tenant",
        },
    }
    raw = _canonical_bytes(ast)
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta}, [fv_id, fv_id])
    assert exc.value.code == "FACT_REFERENCE"


def test_negative_fact_reference_missing_or_extra_ref() -> None:
    """Reject missing or extra reference rows in ordered_fact_refs with FACT_REFERENCE."""
    fv_id1 = uuid4()
    fv_id2 = uuid4()
    meta1 = _make_meta()
    meta2 = _make_meta()
    ast = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fv_id1).lower(),
            "op": "EXISTS",
            "scope_type": "tenant",
        },
    }
    raw = _canonical_bytes(ast)

    # Missing ref
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id1: meta1}, [])
    assert exc.value.code == "FACT_REFERENCE"

    # Extra ref
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id1: meta1, fv_id2: meta2}, [fv_id1, fv_id2])
    assert exc.value.code == "FACT_REFERENCE"


def test_negative_fact_reference_out_of_order() -> None:
    """Reject ordered_fact_refs out of preorder first-use order with FACT_REFERENCE."""
    fv_id1 = uuid4()
    fv_id2 = uuid4()
    meta1 = _make_meta()
    meta2 = _make_meta()
    ast = {
        "ast_version": 1,
        "root": {
            "op": "ALL",
            "children": [
                {
                    "fact_definition_version_id": str(fv_id1).lower(),
                    "op": "EXISTS",
                    "scope_type": "tenant",
                },
                {
                    "fact_definition_version_id": str(fv_id2).lower(),
                    "op": "EXISTS",
                    "scope_type": "tenant",
                },
            ],
        },
    }
    raw = _canonical_bytes(ast)
    # Supplied in reverse order [fv_id2, fv_id1]
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id1: meta1, fv_id2: meta2}, [fv_id2, fv_id1])
    assert exc.value.code == "FACT_REFERENCE"


def test_negative_fact_reference_two_versions_one_stable_fact() -> None:
    """Reject two different FactDefinitionVersion IDs for the same stable FactDefinition UUID."""
    stable_id = uuid4()
    fv_id1 = uuid4()
    fv_id2 = uuid4()
    meta1 = _make_meta(fact_def_id=stable_id)
    meta2 = _make_meta(fact_def_id=stable_id)

    ast = {
        "ast_version": 1,
        "root": {
            "op": "ALL",
            "children": [
                {
                    "fact_definition_version_id": str(fv_id1).lower(),
                    "op": "EXISTS",
                    "scope_type": "tenant",
                },
                {
                    "fact_definition_version_id": str(fv_id2).lower(),
                    "op": "EXISTS",
                    "scope_type": "tenant",
                },
            ],
        },
    }
    raw = _canonical_bytes(ast)
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id1: meta1, fv_id2: meta2}, [fv_id1, fv_id2])
    assert exc.value.code == "FACT_REFERENCE"


# ---------------------------------------------------------------------------
# Import boundary and security inspection tests
# ---------------------------------------------------------------------------


def test_import_boundary_pure_library() -> None:
    """Verify by static inspection that rule_static_validation imports only allowed modules."""
    import conformly.catalog_v2.rule_static_validation as mod

    # Inspect module imports
    imported_modules = set()
    for name, val in mod.__dict__.items():
        if isinstance(val, type(sys)):
            imported_modules.add(name)

    # Allowed imports: standard library json, and digest function
    assert "sqlalchemy" not in imported_modules
    assert "alembic" not in imported_modules
    assert "fastapi" not in imported_modules
    assert "models" not in imported_modules


def test_error_messages_are_generic_and_non_content_bearing() -> None:
    """Verify that error messages do not leak AST fragments, UUIDs, or tenant data."""
    secret_uuid = uuid4()
    meta = _make_meta()
    ast = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(secret_uuid).lower(),
            "op": "EXISTS",
            "scope_type": "secret_scope_that_is_invalid",
        },
    }
    raw = _canonical_bytes(ast)
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {secret_uuid: meta}, [secret_uuid])

    msg = str(exc.value)
    assert str(secret_uuid) not in msg
    assert "secret_scope" not in msg


# ---------------------------------------------------------------------------
# Regression tests for Bugbot review findings
# ---------------------------------------------------------------------------


def test_regression_p1_entity_reference_accepted_and_entity_ref_rejected() -> None:
    """P1 regression: entity_reference is accepted; legacy/invalid entity_ref is rejected."""
    # Positive: entity_reference is accepted
    fv_valid = uuid4()
    meta_valid = _make_meta(value_type="entity_reference", scope_types=frozenset({"tenant"}))
    ast_valid = {
        "ast_version": 1,
        "root": {
            "op": "EXISTS",
            "fact_definition_version_id": str(fv_valid).lower(),
            "scope_type": "tenant",
        },
    }
    raw_valid = _canonical_bytes(ast_valid)
    res = validate_rule_ast(raw_valid, {fv_valid: meta_valid}, [fv_valid])
    assert res.fact_version_ids == (fv_valid,)

    # Negative: entity_ref spelling is rejected with FACT_METADATA
    fv_bad = uuid4()
    meta_bad = _make_meta(value_type="entity_ref", scope_types=frozenset({"tenant"}))
    ast_bad = {
        "ast_version": 1,
        "root": {
            "op": "EXISTS",
            "fact_definition_version_id": str(fv_bad).lower(),
            "scope_type": "tenant",
        },
    }
    raw_bad = _canonical_bytes(ast_bad)
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw_bad, {fv_bad: meta_bad}, [fv_bad])
    assert exc.value.code == "FACT_METADATA"


def test_regression_p2_unhashable_value_type_in_metadata() -> None:
    """P2 regression: unhashable or non-string value_type in metadata returns FACT_METADATA."""
    fv_id = uuid4()
    ast = {
        "ast_version": 1,
        "root": {
            "op": "EXISTS",
            "fact_definition_version_id": str(fv_id).lower(),
            "scope_type": "tenant",
        },
    }
    raw = _canonical_bytes(ast)

    # Test list (unhashable)
    meta_list: Any = FactVersionMetadata(
        fact_definition_id=uuid4(),
        value_type=["boolean"],  # type: ignore[arg-type]
        scope_types=frozenset({"tenant"}),
        enum_codes=frozenset(),
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta_list}, [fv_id])
    assert exc.value.code == "FACT_METADATA"

    # Test dict (unhashable)
    meta_dict: Any = FactVersionMetadata(
        fact_definition_id=uuid4(),
        value_type={"type": "boolean"},  # type: ignore[arg-type]
        scope_types=frozenset({"tenant"}),
        enum_codes=frozenset(),
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta_dict}, [fv_id])
    assert exc.value.code == "FACT_METADATA"

    # Test integer
    meta_int: Any = FactVersionMetadata(
        fact_definition_id=uuid4(),
        value_type=123,  # type: ignore[arg-type]
        scope_types=frozenset({"tenant"}),
        enum_codes=frozenset(),
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv_id: meta_int}, [fv_id])
    assert exc.value.code == "FACT_METADATA"


def test_regression_p2_json_integer_string_overflow() -> None:
    """P2 regression: 5000-digit integer exceeding int_max_str_digits raises JSON_INVALID."""
    # A document with a 5000-digit number is ~5050 bytes (< 16384 bytes).
    # Python 3.11+ json.loads raises ValueError: Exceeds the limit (4300 digits)
    raw = b'{"ast_version":1,"root":' + b"9" * 5000 + b"}"
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {}, [])
    assert exc.value.code == "JSON_INVALID"


# ---------------------------------------------------------------------------
# Exception sanitization tests (no secret sentinel in message, cause, context, or traceback)
# ---------------------------------------------------------------------------


def _assert_secret_absent(exc: RuleValidationError, sentinel: str) -> None:
    """Assert secret sentinel is absent from message, cause, context, and formatted traceback."""
    assert sentinel not in str(exc), f"Secret sentinel leaked in error message: {exc}"
    assert exc.__cause__ is None, f"Exception cause must be None, got: {exc.__cause__}"
    assert exc.__context__ is None, f"Exception context must be None, got: {exc.__context__}"
    formatted_tb = "".join(traceback.format_exception(exc))
    assert sentinel not in formatted_tb, (
        f"Secret sentinel leaked in formatted traceback:\n{formatted_tb}"
    )


def test_exception_sanitization_json_decode_error() -> None:
    """Secret sentinel in malformed JSON syntax is absent from message, cause, context, and traceback."""
    sentinel = "SECRET_SENTINEL_JSON_TOKEN_88888"
    raw = b'{"ast_version": 1, "root": ' + sentinel.encode("utf-8") + b"}"
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {}, [])
    assert exc.value.code == "JSON_INVALID"
    _assert_secret_absent(exc.value, sentinel)


def test_exception_sanitization_unicode_decode_error() -> None:
    """Secret sentinel in malformed UTF-8 payload is absent from message, cause, context, and traceback."""
    sentinel = "SECRET_SENTINEL_UTF8_TOKEN_77777"
    raw = b'{"ast_version": 1, "root": "' + sentinel.encode("utf-8") + b'\xff"}'
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {}, [])
    assert exc.value.code == "JSON_INVALID"
    _assert_secret_absent(exc.value, sentinel)


def test_exception_sanitization_uuid_parse_error() -> None:
    """Secret sentinel in malformed UUID is absent from message, cause, context, and traceback."""
    sentinel = "SECRET_UUID_SENTINEL_66666"
    bad_uuid = f"00000000-0000-0000-{sentinel[:4]}-{sentinel[4:16]}"
    raw = _canonical_bytes(
        {
            "ast_version": 1,
            "root": {
                "op": "EXISTS",
                "fact_definition_version_id": bad_uuid,
                "scope_type": "tenant",
            },
        }
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {}, [])
    assert exc.value.code == "AST_SCHEMA"
    _assert_secret_absent(exc.value, sentinel)


def test_exception_sanitization_json_integer_overflow() -> None:
    """Secret sentinel in 5000-digit integer overflow is absent from message, cause, context, and traceback."""
    sentinel = "888888888888888"
    raw = b'{"ast_version": 1, "root": ' + b"9" * 4500 + sentinel.encode("utf-8") + b"}"
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {}, [])
    assert exc.value.code == "JSON_INVALID"
    _assert_secret_absent(exc.value, sentinel)


def test_exception_sanitization_duplicate_key() -> None:
    """Secret sentinel in duplicate JSON key is absent from message, cause, context, and traceback."""
    sentinel = "SECRET_DUP_KEY_SENTINEL_55555"
    raw = (
        b'{"ast_version": 1, "'
        + sentinel.encode("utf-8")
        + b'": 1, "'
        + sentinel.encode("utf-8")
        + b'": 2, "root": {"op": "EXISTS"}}'
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {}, [])
    assert exc.value.code == "JSON_DUPLICATE_KEY"
    _assert_secret_absent(exc.value, sentinel)


def test_exception_sanitization_noncanonical_json() -> None:
    """Secret sentinel in non-canonical JSON whitespace/ordering is absent from message, cause, context, and traceback."""
    sentinel = "SECRET_NONCANONICAL_SENTINEL_44444"
    fv = uuid4()
    meta = FactVersionMetadata(
        fact_definition_id=uuid4(),
        value_type="boolean",
        scope_types=frozenset({"tenant"}),
        enum_codes=frozenset(),
    )
    raw = (
        b'{\n  "ast_version": 1,\n  "root": {"op": "EXISTS", "fact_definition_version_id": "'
        + str(fv).encode("utf-8")
        + b'", "scope_type": "tenant", "note": "'
        + sentinel.encode("utf-8")
        + b'"}\n}'
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {fv: meta}, [fv])
    assert exc.value.code == "JSON_NONCANONICAL"
    _assert_secret_absent(exc.value, sentinel)


def test_exception_sanitization_parser_recursion_overflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Secret sentinel in parser RecursionError is absent from message, cause, context, and traceback."""
    sentinel = "SECRET_PARSER_RECURSION_SENTINEL_33333"

    def mock_loads(*args: object, **kwargs: object) -> object:
        raise RecursionError(f"internal depth exceeded with {sentinel}")

    monkeypatch.setattr(json, "loads", mock_loads)
    raw = _canonical_bytes({"ast_version": 1, "root": {}})
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {}, [])
    assert exc.value.code == "AST_LIMIT"
    _assert_secret_absent(exc.value, sentinel)


def test_exception_sanitization_traversal_recursion_overflow() -> None:
    """Secret sentinel in AST traversal RecursionError is absent from message, cause, context, and traceback."""
    sentinel = "SECRET_TRAVERSAL_RECURSION_SENTINEL_22222"
    fv = uuid4()
    meta = FactVersionMetadata(
        fact_definition_id=uuid4(),
        value_type="boolean",
        scope_types=frozenset({"tenant"}),
        enum_codes=frozenset(),
    )
    raw = _canonical_bytes(
        {
            "ast_version": 1,
            "root": {
                "op": "EXISTS",
                "fact_definition_version_id": str(fv).lower(),
                "scope_type": "tenant",
            },
        }
    )

    class PoisonMapping(dict):
        def __getitem__(self, key: Any) -> Any:
            raise RecursionError(f"traversal recursion poisoned with {sentinel}")

    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, PoisonMapping({fv: meta}), [fv])
    assert exc.value.code == "AST_LIMIT"
    _assert_secret_absent(exc.value, sentinel)


def test_exception_sanitization_canonical_json_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Secret sentinel in canonical_json failure is absent from message, cause, context, and traceback."""
    sentinel = "SECRET_CANONICAL_JSON_SENTINEL_11111"

    def mock_canonical_json(*args: object, **kwargs: object) -> str:
        raise ValueError(f"internal canonicalization error with {sentinel}")

    monkeypatch.setattr(
        "conformly.catalog_v2.rule_static_validation.canonical_json", mock_canonical_json
    )
    raw = b'{"ast_version": 1, "root": {}}'
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(raw, {}, [])
    assert exc.value.code == "JSON_NONCANONICAL"
    _assert_secret_absent(exc.value, sentinel)
