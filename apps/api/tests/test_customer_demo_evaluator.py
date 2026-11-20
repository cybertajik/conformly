"""Unit tests for customer demo pure evaluator, truth tables, operators and digests."""

import copy
from uuid import uuid4

import pytest

from conformly.customer_demo.evaluator import (
    EvaluatorError,
    compute_answers_digest,
    compute_evaluation_digest,
    evaluate_bundle,
    evaluate_node,
    normalize_answers,
)
from conformly.customer_demo.fixture import (
    BUNDLE_V1_DIGEST,
    BUNDLE_V1_PAYLOAD,
    BUNDLE_V2_DIGEST,
    FACT_CLOUD_V1_ID,
    FACT_REGION_V1_ID,
    PACK_VERSION_V1_ID,
    PACK_VERSION_V2_ID,
    _verify_fixtures,
    get_bundle_by_version_id,
    get_bundle_digest,
    get_demo_manifest,
)


def test_fixture_manifest_and_bundles():
    """Verify fixed synthetic manifest and bundle contents."""
    manifest = get_demo_manifest()
    assert "disclaimer" in manifest
    assert "source_provenance_disclaimer" in manifest
    assert (
        "non-legal" in manifest["disclaimer"].lower()
        or "not legal" in manifest["disclaimer"].lower()
    )
    assert len(manifest["packs"]) == 4
    assert len({p["pack_id"] for p in manifest["packs"]}) == 2
    assert len(manifest["companies"]) == 2
    assert len(manifest["fact_definitions"]) == 2

    b1 = get_bundle_by_version_id(PACK_VERSION_V1_ID)
    assert len(b1["requirements"]) == 2
    assert get_bundle_digest(PACK_VERSION_V1_ID) == BUNDLE_V1_DIGEST

    b2 = get_bundle_by_version_id(PACK_VERSION_V2_ID)
    assert len(b2["requirements"]) == 3
    assert get_bundle_digest(PACK_VERSION_V2_ID) == BUNDLE_V2_DIGEST

    with pytest.raises(ValueError, match="Unknown customer demo pack version ID"):
        get_bundle_by_version_id(uuid4())


def test_fixture_deep_copy_isolation():
    """Verify get_bundle_by_version_id and get_demo_manifest return deep copies (R4)."""
    b1 = get_bundle_by_version_id(PACK_VERSION_V1_ID)
    b1["name"] = "Mutated Name"
    b1["requirements"][0]["title"] = "Mutated Title"

    fresh_b1 = get_bundle_by_version_id(PACK_VERSION_V1_ID)
    assert fresh_b1["name"] == "Synthetic Customer Baseline Pack"
    assert fresh_b1["requirements"][0]["title"] == "Synthetic Cloud Architecture Governance"

    manifest = get_demo_manifest()
    manifest["companies"][0]["display_name"] = "Mutated Company"
    fresh_manifest = get_demo_manifest()
    assert fresh_manifest["companies"][0]["display_name"] == "Fictional Alpha (Cloud-First)"


def test_fixture_tamper_rejection(monkeypatch):
    """Verify that tampering with AST literal, fact definition, or bundle payload is rejected (R4)."""
    # 1. Tamper with AST_1 in BUNDLE_V1_PAYLOAD (AST mismatch check)
    orig_reqs = copy.deepcopy(BUNDLE_V1_PAYLOAD["requirements"])
    try:
        tampered_reqs = copy.deepcopy(orig_reqs)
        tampered_reqs[0]["rule_ast"]["root"]["value"] = False
        monkeypatch.setitem(BUNDLE_V1_PAYLOAD, "requirements", tampered_reqs)
        with pytest.raises(RuntimeError, match="Rule AST mismatch in fixture linkage"):
            _verify_fixtures()
    finally:
        BUNDLE_V1_PAYLOAD["requirements"] = orig_reqs

    # 1b. Tamper with requirement title (digest mismatch check)
    try:
        tampered_reqs = copy.deepcopy(orig_reqs)
        tampered_reqs[0]["title"] = "Tampered Title"
        monkeypatch.setitem(BUNDLE_V1_PAYLOAD, "requirements", tampered_reqs)
        with pytest.raises(RuntimeError, match="fixture digests corrupted"):
            _verify_fixtures()
    finally:
        BUNDLE_V1_PAYLOAD["requirements"] = orig_reqs

    # 2. Tamper with fact definitions in BUNDLE_V1_PAYLOAD
    orig_facts = copy.deepcopy(BUNDLE_V1_PAYLOAD["fact_definitions"])
    try:
        tampered_facts = copy.deepcopy(orig_facts)
        tampered_facts[0]["label"] = "Tampered Cloud Label"
        monkeypatch.setitem(BUNDLE_V1_PAYLOAD, "fact_definitions", tampered_facts)
        with pytest.raises(RuntimeError, match="fixture digests corrupted"):
            _verify_fixtures()
    finally:
        BUNDLE_V1_PAYLOAD["fact_definitions"] = orig_facts


def test_normalize_answers_strict_types_and_conflicts():
    """Verify strict type normalization and conflicting duplicate rejection (R2, R8)."""
    # Valid normalization using aliases
    norm = normalize_answers(
        {
            "synthetic_wp09_uses_cloud": True,
            "synthetic_wp09_operating_region": "EU",
        }
    )
    assert norm[str(FACT_CLOUD_V1_ID)] is True
    assert norm[str(FACT_REGION_V1_ID)] == "EU"

    # Valid normalization using UUIDs
    norm_uuid = normalize_answers(
        {
            str(FACT_CLOUD_V1_ID): False,
            str(FACT_REGION_V1_ID): "OTHER",
        }
    )
    assert norm_uuid[str(FACT_CLOUD_V1_ID)] is False
    assert norm_uuid[str(FACT_REGION_V1_ID)] == "OTHER"

    # Consistent duplicate inputs succeed
    norm_dup = normalize_answers(
        {
            "synthetic_wp09_uses_cloud": True,
            str(FACT_CLOUD_V1_ID): True,
            "synthetic_wp09_operating_region": "EU",
            str(FACT_REGION_V1_ID): "EU",
        }
    )
    assert norm_dup[str(FACT_CLOUD_V1_ID)] is True
    assert norm_dup[str(FACT_REGION_V1_ID)] == "EU"

    # Conflicting duplicate inputs are strictly rejected (R2)
    with pytest.raises(EvaluatorError, match="Conflicting duplicate inputs for cloud fact"):
        normalize_answers(
            {
                "synthetic_wp09_uses_cloud": True,
                str(FACT_CLOUD_V1_ID): False,
            }
        )

    with pytest.raises(EvaluatorError, match="Conflicting duplicate inputs for region fact"):
        normalize_answers(
            {
                "synthetic_wp09_operating_region": "EU",
                str(FACT_REGION_V1_ID): "OTHER",
            }
        )

    # Strict boolean rejection
    with pytest.raises(EvaluatorError, match="must be a strict boolean literal"):
        normalize_answers({"synthetic_wp09_uses_cloud": "true"})

    with pytest.raises(EvaluatorError, match="must be a strict boolean literal"):
        normalize_answers({"synthetic_wp09_uses_cloud": 1})

    # Strict enum rejection
    with pytest.raises(EvaluatorError, match="must be 'EU' or 'OTHER'"):
        normalize_answers({"synthetic_wp09_operating_region": "US"})

    # Hostile marker key must NOT be echoed in the error message (R8)
    hostile_key = "<script>alert('xss')</script>"
    with pytest.raises(EvaluatorError) as exc_info:
        normalize_answers({hostile_key: "val"})
    assert hostile_key not in str(exc_info.value)
    assert "Unexpected or undeclared fact key" in str(exc_info.value)


def test_compute_answers_digest_deterministic():
    """Verify answer digest canonical hashing and sensitivity to inputs."""
    facts = {str(FACT_CLOUD_V1_ID): True, str(FACT_REGION_V1_ID): "EU"}
    d1 = compute_answers_digest("ALPHA", facts)
    d2 = compute_answers_digest("ALPHA", facts)
    assert d1 == d2
    assert len(d1) == 64

    # Changing company code changes digest
    d_beta = compute_answers_digest("BETA", facts)
    assert d1 != d_beta

    # Changing a fact changes digest
    facts_mod = {str(FACT_CLOUD_V1_ID): False, str(FACT_REGION_V1_ID): "EU"}
    d_mod = compute_answers_digest("ALPHA", facts_mod)
    assert d1 != d_mod

    # Invalid company code rejects without echoing
    with pytest.raises(EvaluatorError, match="Invalid company code"):
        compute_answers_digest("GAMMA", facts)


def test_evaluator_all_six_operators():
    """Test all six operators (EQUALS, IN, EXISTS, NOT, ALL, ANY) across truth cases."""
    fact_id = str(FACT_CLOUD_V1_ID)

    # 1. EQUALS
    node_eq = {"op": "EQUALS", "fact_definition_version_id": fact_id, "value": True}
    assert evaluate_node(node_eq, "$", {fact_id: True})["result"] == "APPLICABLE"
    assert evaluate_node(node_eq, "$", {fact_id: False})["result"] == "NOT_APPLICABLE"
    res_eq_unknown = evaluate_node(node_eq, "$", {})
    assert res_eq_unknown["result"] == "NEEDS_INFORMATION"
    assert res_eq_unknown["missing_fact_version_ids"] == [fact_id]

    # 2. IN
    reg_id = str(FACT_REGION_V1_ID)
    node_in = {"op": "IN", "fact_definition_version_id": reg_id, "values": ["EU"]}
    assert evaluate_node(node_in, "$", {reg_id: "EU"})["result"] == "APPLICABLE"
    assert evaluate_node(node_in, "$", {reg_id: "OTHER"})["result"] == "NOT_APPLICABLE"
    res_in_unknown = evaluate_node(node_in, "$", {})
    assert res_in_unknown["result"] == "NEEDS_INFORMATION"
    assert res_in_unknown["missing_fact_version_ids"] == [reg_id]

    # 3. EXISTS
    node_ex = {"op": "EXISTS", "fact_definition_version_id": fact_id}
    assert evaluate_node(node_ex, "$", {fact_id: True})["result"] == "APPLICABLE"
    assert evaluate_node(node_ex, "$", {fact_id: False})["result"] == "APPLICABLE"
    res_ex_missing = evaluate_node(node_ex, "$", {})
    assert res_ex_missing["result"] == "NEEDS_INFORMATION"
    assert res_ex_missing["missing_fact_version_ids"] == [fact_id]

    # 4. NOT
    node_not_app = {"op": "NOT", "child": node_eq}
    assert evaluate_node(node_not_app, "$", {fact_id: True})["result"] == "NOT_APPLICABLE"
    assert evaluate_node(node_not_app, "$", {fact_id: False})["result"] == "APPLICABLE"
    res_not_unk = evaluate_node(node_not_app, "$", {})
    assert res_not_unk["result"] == "NEEDS_INFORMATION"
    assert res_not_unk["missing_fact_version_ids"] == [fact_id]

    # 5. ALL
    node_all = {"op": "ALL", "children": [node_eq, node_in]}
    assert evaluate_node(node_all, "$", {fact_id: True, reg_id: "EU"})["result"] == "APPLICABLE"
    assert (
        evaluate_node(node_all, "$", {fact_id: False, reg_id: "EU"})["result"] == "NOT_APPLICABLE"
    )
    res_all_f_u = evaluate_node(node_all, "$", {fact_id: False})
    assert res_all_f_u["result"] == "NOT_APPLICABLE"
    assert reg_id in res_all_f_u["missing_fact_version_ids"]
    res_all_t_u = evaluate_node(node_all, "$", {fact_id: True})
    assert res_all_t_u["result"] == "NEEDS_INFORMATION"
    assert res_all_t_u["missing_fact_version_ids"] == [reg_id]

    # 6. ANY
    node_any = {"op": "ANY", "children": [node_eq, node_in]}
    assert evaluate_node(node_any, "$", {fact_id: True, reg_id: "OTHER"})["result"] == "APPLICABLE"
    res_any_t_u = evaluate_node(node_any, "$", {fact_id: True})
    assert res_any_t_u["result"] == "APPLICABLE"
    assert reg_id in res_any_t_u["missing_fact_version_ids"]
    res_any_f_u = evaluate_node(node_any, "$", {fact_id: False})
    assert res_any_f_u["result"] == "NEEDS_INFORMATION"
    assert reg_id in res_any_f_u["missing_fact_version_ids"]
    assert (
        evaluate_node(node_any, "$", {fact_id: False, reg_id: "OTHER"})["result"]
        == "NOT_APPLICABLE"
    )


def test_contract_required_examples():
    """Verify specific examples mandated by contract section 2:
    - Alpha cloud=true/region=EU -> applicable/applicable in v1
    - Beta cloud=false/region unknown -> not-applicable/not-applicable and reports missing region leaf
    - cloud=true/region unknown -> applicable/needs-information
    """
    # 1. Alpha in v1
    alpha_facts = {str(FACT_CLOUD_V1_ID): True, str(FACT_REGION_V1_ID): "EU"}
    res_alpha = evaluate_bundle(PACK_VERSION_V1_ID, alpha_facts)
    assert len(res_alpha) == 2
    assert res_alpha[0]["result"] == "APPLICABLE"
    assert res_alpha[1]["result"] == "APPLICABLE"
    assert len(res_alpha[0]["missing_fact_version_ids"]) == 0
    assert len(res_alpha[1]["missing_fact_version_ids"]) == 0

    # 2. Beta in v1
    beta_facts = {str(FACT_CLOUD_V1_ID): False}
    res_beta = evaluate_bundle(PACK_VERSION_V1_ID, beta_facts)
    assert len(res_beta) == 2
    assert res_beta[0]["result"] == "NOT_APPLICABLE"
    assert res_beta[1]["result"] == "NOT_APPLICABLE"
    assert str(FACT_REGION_V1_ID) in res_beta[1]["missing_fact_version_ids"]

    # 3. Partial (cloud=true, region unknown) in v1
    partial_facts = {str(FACT_CLOUD_V1_ID): True}
    res_partial = evaluate_bundle(PACK_VERSION_V1_ID, partial_facts)
    assert len(res_partial) == 2
    assert res_partial[0]["result"] == "APPLICABLE"
    assert res_partial[1]["result"] == "NEEDS_INFORMATION"
    assert str(FACT_REGION_V1_ID) in res_partial[1]["missing_fact_version_ids"]

    # 4. Extended bundle v2 evaluation
    res_v2 = evaluate_bundle(PACK_VERSION_V2_ID, beta_facts)
    assert len(res_v2) == 3
    assert res_v2[2]["result"] == "APPLICABLE"


def test_explanation_tree_paths_and_stability():
    """Verify explanation trees maintain stable node paths and ordering."""
    facts = {str(FACT_CLOUD_V1_ID): True, str(FACT_REGION_V1_ID): "EU"}
    res = evaluate_bundle(PACK_VERSION_V1_ID, facts)

    tree1 = res[0]["explanation_tree"]
    assert tree1["op"] == "EQUALS"
    assert tree1["path"] == "$"
    assert len(tree1["children"]) == 0

    tree2 = res[1]["explanation_tree"]
    assert tree2["op"] == "ALL"
    assert tree2["path"] == "$"
    assert len(tree2["children"]) == 2
    assert tree2["children"][0]["path"] == "$.children[0]"
    assert tree2["children"][0]["op"] == "EQUALS"
    assert tree2["children"][1]["path"] == "$.children[1]"
    assert tree2["children"][1]["op"] == "EQUALS"


def test_evaluation_digest_tampering_detection():
    """Verify that changing any input, answer digest, or outcome alters the evaluation digest."""
    facts = {str(FACT_CLOUD_V1_ID): True, str(FACT_REGION_V1_ID): "EU"}
    ans_digest = compute_answers_digest("ALPHA", facts)
    results = evaluate_bundle(PACK_VERSION_V1_ID, facts)
    b_digest = get_bundle_digest(PACK_VERSION_V1_ID)

    base_eval_digest = compute_evaluation_digest(
        ans_digest, 1, PACK_VERSION_V1_ID, b_digest, results
    )
    assert len(base_eval_digest) == 64

    # Tamper answer digest
    tampered_ans = compute_evaluation_digest("0" * 64, 1, PACK_VERSION_V1_ID, b_digest, results)
    assert base_eval_digest != tampered_ans

    # Tamper revision
    tampered_rev = compute_evaluation_digest(ans_digest, 2, PACK_VERSION_V1_ID, b_digest, results)
    assert base_eval_digest != tampered_rev

    # Tamper pack version
    tampered_pack = compute_evaluation_digest(ans_digest, 1, PACK_VERSION_V2_ID, b_digest, results)
    assert base_eval_digest != tampered_pack

    # Tamper results
    tampered_results = list(results)
    tampered_results[0] = dict(tampered_results[0], result="NOT_APPLICABLE")
    tampered_res = compute_evaluation_digest(
        ans_digest, 1, PACK_VERSION_V1_ID, b_digest, tampered_results
    )
    assert base_eval_digest != tampered_res


def test_evaluation_digest_binds_rule_version_evaluator_version_and_explanation_tree():
    """Verify evaluation hash strictly binds rule_version_id, evaluator_version, and explanation tree (P2)."""
    import copy

    facts = {str(FACT_CLOUD_V1_ID): True, str(FACT_REGION_V1_ID): "EU"}
    ans_digest = compute_answers_digest("ALPHA", facts)
    results = evaluate_bundle(PACK_VERSION_V1_ID, facts)
    b_digest = get_bundle_digest(PACK_VERSION_V1_ID)

    base_eval_digest = compute_evaluation_digest(
        ans_digest, 1, PACK_VERSION_V1_ID, b_digest, results
    )

    # 1. Mutate rule_version_id to a zero UUID
    tampered_rule = [dict(r) for r in results]
    tampered_rule[0]["rule_version_id"] = "00000000-0000-0000-0000-000000000000"
    assert (
        compute_evaluation_digest(ans_digest, 1, PACK_VERSION_V1_ID, b_digest, tampered_rule)
        != base_eval_digest
    )

    # 2. Mutate requirement_version_id
    tampered_req = [dict(r) for r in results]
    tampered_req[0]["requirement_version_id"] = "00000000-0000-0000-0000-000000000000"
    assert (
        compute_evaluation_digest(ans_digest, 1, PACK_VERSION_V1_ID, b_digest, tampered_req)
        != base_eval_digest
    )

    # 3. Mutate explanation message
    tampered_msg = copy.deepcopy(results)
    tampered_msg[0]["explanation_tree"]["message"] = "Tampered explanation message"
    assert (
        compute_evaluation_digest(ans_digest, 1, PACK_VERSION_V1_ID, b_digest, tampered_msg)
        != base_eval_digest
    )

    # 4. Mutate explanation tree node result
    tampered_tree_res = copy.deepcopy(results)
    tampered_tree_res[0]["explanation_tree"]["result"] = "NOT_APPLICABLE"
    assert (
        compute_evaluation_digest(ans_digest, 1, PACK_VERSION_V1_ID, b_digest, tampered_tree_res)
        != base_eval_digest
    )

    # 5. Mutate evaluator version
    assert (
        compute_evaluation_digest(
            ans_digest,
            1,
            PACK_VERSION_V1_ID,
            b_digest,
            results,
            evaluator_version="tampered-evaluator-v2",
        )
        != base_eval_digest
    )
