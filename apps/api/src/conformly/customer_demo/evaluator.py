"""Deterministic 3-valued rule evaluator and explanation tree builder for WP-09 customer demo."""

from __future__ import annotations

import copy
import hashlib
from typing import Any
from uuid import UUID

from conformly.catalog_v2.digest import canonical_json
from conformly.customer_demo.fixture import (
    EVALUATOR_VERSION,
    FACT_CLOUD_V1_ID,
    FACT_REGION_V1_ID,
    RULE_MAP,
    get_bundle_by_version_id,
)


class EvaluatorError(Exception):
    """Raised when evaluation fails due to invalid payload or state."""


def normalize_answers(raw_answers: dict[str, Any]) -> dict[str, Any]:
    """Validate and project raw client-submitted answers into canonical fact definition version IDs.

    Rejects extra fields, strings-as-booleans, numbers-as-booleans, undeclared enum codes,
    caller fact-version substitution, conflicting duplicate inputs, and other fact types.
    Never echoes untrusted keys or values in error diagnostics.
    """
    if not isinstance(raw_answers, dict):
        raise EvaluatorError("Answers must be a JSON object")

    cloud_key_alias = "synthetic_wp09_uses_cloud"
    cloud_key_id = str(FACT_CLOUD_V1_ID)

    region_key_alias = "synthetic_wp09_operating_region"
    region_key_id = str(FACT_REGION_V1_ID)

    allowed_keys = {cloud_key_alias, cloud_key_id, region_key_alias, region_key_id}
    for k in raw_answers.keys():
        if k not in allowed_keys:
            raise EvaluatorError("Unexpected or undeclared fact key in answers")

    # Cloud fact: strict boolean
    cloud_val = None
    if cloud_key_alias in raw_answers and cloud_key_id in raw_answers:
        if raw_answers[cloud_key_alias] != raw_answers[cloud_key_id]:
            raise EvaluatorError("Conflicting duplicate inputs for cloud fact")
        cloud_val = raw_answers[cloud_key_alias]
    elif cloud_key_alias in raw_answers:
        cloud_val = raw_answers[cloud_key_alias]
    elif cloud_key_id in raw_answers:
        cloud_val = raw_answers[cloud_key_id]

    if cloud_val is not None:
        if type(cloud_val) is not bool:
            raise EvaluatorError(
                "Fact 'synthetic_wp09_uses_cloud' must be a strict boolean literal"
            )

    # Region fact: enum EU | OTHER
    region_val = None
    if region_key_alias in raw_answers and region_key_id in raw_answers:
        if raw_answers[region_key_alias] != raw_answers[region_key_id]:
            raise EvaluatorError("Conflicting duplicate inputs for region fact")
        region_val = raw_answers[region_key_alias]
    elif region_key_alias in raw_answers:
        region_val = raw_answers[region_key_alias]
    elif region_key_id in raw_answers:
        region_val = raw_answers[region_key_id]

    if region_val is not None:
        if not isinstance(region_val, str) or region_val not in ("EU", "OTHER"):
            raise EvaluatorError("Fact 'synthetic_wp09_operating_region' must be 'EU' or 'OTHER'")

    return {
        cloud_key_id: cloud_val,
        region_key_id: region_val,
    }


def compute_answers_digest(company_code: str, normalized_facts: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 content digest over company code and normalized facts."""
    if company_code not in ("ALPHA", "BETA"):
        raise EvaluatorError("Invalid company code")

    payload = {
        "company_code": company_code,
        "facts": {
            str(FACT_CLOUD_V1_ID): normalized_facts.get(str(FACT_CLOUD_V1_ID)),
            str(FACT_REGION_V1_ID): normalized_facts.get(str(FACT_REGION_V1_ID)),
        },
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def evaluate_node(node: dict[str, Any], path: str, facts: dict[str, Any]) -> dict[str, Any]:
    """Recursively evaluate an AST node using pure 3-valued logic and build explanation tree.

    Truth values:
      true -> APPLICABLE
      false -> NOT_APPLICABLE
      unknown -> NEEDS_INFORMATION

    Rules:
      EQUALS / IN with missing answer -> NEEDS_INFORMATION
      EXISTS with known answer (including false) -> APPLICABLE; missing/null -> NEEDS_INFORMATION
      NOT unknown -> NEEDS_INFORMATION; NOT true -> false; NOT false -> true
      ALL false dominates, otherwise unknown dominates, otherwise true
      ANY true dominates, otherwise unknown dominates, otherwise false
      Evaluate all nodes in stable AST order without short-circuiting.
    """
    op = node.get("op")

    if op == "EQUALS":
        fact_id = node["fact_definition_version_id"]
        target_val = node["value"]
        actual_val = facts.get(fact_id)

        if actual_val is None:
            res = "NEEDS_INFORMATION"
            msg = f"Fact {fact_id} is unknown (missing answer)"
            missing = [fact_id]
        elif actual_val == target_val:
            res = "APPLICABLE"
            msg = f"Fact {fact_id} matches required condition ({target_val})"
            missing = []
        else:
            res = "NOT_APPLICABLE"
            msg = f"Fact {fact_id} does not match required condition ({target_val})"
            missing = []

        return {
            "op": "EQUALS",
            "path": path,
            "result": res,
            "message": msg,
            "fact_definition_version_id": fact_id,
            "missing_fact_version_ids": missing,
            "children": [],
        }

    if op == "IN":
        fact_id = node["fact_definition_version_id"]
        target_values = node["values"]
        actual_val = facts.get(fact_id)

        if actual_val is None:
            res = "NEEDS_INFORMATION"
            msg = f"Fact {fact_id} is unknown (missing answer)"
            missing = [fact_id]
        elif actual_val in target_values:
            res = "APPLICABLE"
            msg = f"Fact {fact_id} is contained in allowed set {target_values}"
            missing = []
        else:
            res = "NOT_APPLICABLE"
            msg = f"Fact {fact_id} is not contained in allowed set {target_values}"
            missing = []

        return {
            "op": "IN",
            "path": path,
            "result": res,
            "message": msg,
            "fact_definition_version_id": fact_id,
            "missing_fact_version_ids": missing,
            "children": [],
        }

    if op == "EXISTS":
        fact_id = node["fact_definition_version_id"]
        actual_val = facts.get(fact_id)

        if actual_val is not None:
            res = "APPLICABLE"
            msg = f"Fact {fact_id} is provided"
            missing = []
        else:
            res = "NEEDS_INFORMATION"
            msg = f"Fact {fact_id} is missing"
            missing = [fact_id]

        return {
            "op": "EXISTS",
            "path": path,
            "result": res,
            "message": msg,
            "fact_definition_version_id": fact_id,
            "missing_fact_version_ids": missing,
            "children": [],
        }

    if op == "NOT":
        child_node = node["child"]
        child_res = evaluate_node(child_node, f"{path}.child", facts)

        if child_res["result"] == "APPLICABLE":
            res = "NOT_APPLICABLE"
            msg = "Negation of APPLICABLE is NOT_APPLICABLE"
        elif child_res["result"] == "NOT_APPLICABLE":
            res = "APPLICABLE"
            msg = "Negation of NOT_APPLICABLE is APPLICABLE"
        else:
            res = "NEEDS_INFORMATION"
            msg = "Negation of NEEDS_INFORMATION is NEEDS_INFORMATION"

        return {
            "op": "NOT",
            "path": path,
            "result": res,
            "message": msg,
            "fact_definition_version_id": None,
            "missing_fact_version_ids": list(child_res["missing_fact_version_ids"]),
            "children": [child_res],
        }

    if op == "ALL":
        children_nodes = node.get("children", [])
        child_results = [
            evaluate_node(c, f"{path}.children[{i}]", facts) for i, c in enumerate(children_nodes)
        ]

        missing_acc: set[str] = set()
        for c in child_results:
            missing_acc.update(c["missing_fact_version_ids"])

        # ALL 3-valued truth table:
        # If ANY child is NOT_APPLICABLE -> NOT_APPLICABLE dominates
        # Else if ANY child is NEEDS_INFORMATION -> NEEDS_INFORMATION dominates
        # Else -> APPLICABLE
        if any(c["result"] == "NOT_APPLICABLE" for c in child_results):
            res = "NOT_APPLICABLE"
            msg = "At least one condition in conjunction evaluated to NOT_APPLICABLE"
        elif any(c["result"] == "NEEDS_INFORMATION" for c in child_results):
            res = "NEEDS_INFORMATION"
            msg = "Conjunction requires additional information"
        else:
            res = "APPLICABLE"
            msg = "All conditions in conjunction evaluated to APPLICABLE"

        return {
            "op": "ALL",
            "path": path,
            "result": res,
            "message": msg,
            "fact_definition_version_id": None,
            "missing_fact_version_ids": sorted(missing_acc),
            "children": child_results,
        }

    if op == "ANY":
        children_nodes = node.get("children", [])
        child_results = [
            evaluate_node(c, f"{path}.children[{i}]", facts) for i, c in enumerate(children_nodes)
        ]

        any_missing_acc: set[str] = set()
        for c in child_results:
            any_missing_acc.update(c["missing_fact_version_ids"])

        # ANY 3-valued truth table:
        # If ANY child is APPLICABLE -> APPLICABLE dominates
        # Else if ANY child is NEEDS_INFORMATION -> NEEDS_INFORMATION dominates
        # Else -> NOT_APPLICABLE
        if any(c["result"] == "APPLICABLE" for c in child_results):
            res = "APPLICABLE"
            msg = "At least one condition in disjunction evaluated to APPLICABLE"
        elif any(c["result"] == "NEEDS_INFORMATION" for c in child_results):
            res = "NEEDS_INFORMATION"
            msg = "Disjunction requires additional information"
        else:
            res = "NOT_APPLICABLE"
            msg = "All conditions in disjunction evaluated to NOT_APPLICABLE"

        return {
            "op": "ANY",
            "path": path,
            "result": res,
            "message": msg,
            "fact_definition_version_id": None,
            "missing_fact_version_ids": sorted(any_missing_acc),
            "children": child_results,
        }

    raise EvaluatorError("Unsupported operator in rule AST")


def evaluate_bundle(pack_version_id: UUID, raw_facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate all requirements in specified pack version and return deterministically ordered results."""
    bundle = get_bundle_by_version_id(pack_version_id)
    normalized = normalize_answers(raw_facts)

    results = []
    # Requirements in bundle have deterministic order
    for req in bundle["requirements"]:
        req_id = UUID(req["id"])
        req_version_id = UUID(req["version_id"])
        rule_version_id, ast = RULE_MAP[req_version_id]
        root_node = ast.get("root", ast) if isinstance(ast, dict) else ast
        tree = evaluate_node(root_node, "$", normalized)
        res = {
            "requirement_id": str(req_id),
            "requirement_version_id": str(req_version_id),
            "identifier": req["identifier"],
            "title": req["title"],
            "rule_id": str(req["rule_id"]),
            "rule_version_id": str(rule_version_id),
            "result": tree["result"],
            "missing_fact_version_ids": tree["missing_fact_version_ids"],
            "explanation_tree": tree,
        }
        results.append(res)

    return copy.deepcopy(results)


def _canonicalize_explanation_node(node: dict[str, Any] | None) -> dict[str, Any] | None:
    """Recursively canonicalize explanation AST node."""
    if not isinstance(node, dict):
        return None
    children = [
        _canonicalize_explanation_node(c) for c in node.get("children", []) if isinstance(c, dict)
    ]
    return {
        "op": node.get("op"),
        "path": node.get("path"),
        "result": node.get("result"),
        "message": node.get("message"),
        "fact_definition_version_id": (
            str(node["fact_definition_version_id"])
            if node.get("fact_definition_version_id") is not None
            else None
        ),
        "missing_fact_version_ids": sorted(
            str(fid) for fid in node.get("missing_fact_version_ids", [])
        ),
        "children": [c for c in children if c is not None],
    }


def compute_evaluation_digest(
    answer_digest: str,
    answer_revision: int,
    pack_version_id: UUID,
    bundle_digest: str,
    results: list[dict[str, Any]],
    evaluator_version: str = EVALUATOR_VERSION,
) -> str:
    """Compute canonical content digest binding evaluator version and complete ordered results snapshot."""
    canonical_results = []
    for r in results:
        expl = _canonicalize_explanation_node(r.get("explanation_tree") or r.get("explanation"))
        canonical_results.append(
            {
                "requirement_id": str(r["requirement_id"]),
                "requirement_version_id": str(r["requirement_version_id"]),
                "identifier": r.get("identifier"),
                "title": r.get("title"),
                "rule_id": str(r["rule_id"]) if r.get("rule_id") else None,
                "rule_version_id": str(r["rule_version_id"]) if r.get("rule_version_id") else None,
                "result": r["result"],
                "missing_fact_version_ids": sorted(
                    str(fid) for fid in r.get("missing_fact_version_ids", [])
                ),
                "explanation_tree": expl,
            }
        )

    payload = {
        "evaluator_version": evaluator_version,
        "answer_digest": answer_digest,
        "answer_revision": answer_revision,
        "pack_version_id": str(pack_version_id),
        "bundle_digest": bundle_digest,
        "results": canonical_results,
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
