"""Unit tests for deterministic canonical JSON encoding and SHA-256 draft content digest calculation."""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest

from conformly.catalog_v2.digest import (
    canonical_json,
    compute_assessment_procedure_version_digest,
    compute_content_digest,
    compute_control_version_digest,
    compute_evidence_requirement_version_digest,
    compute_mapping_version_digest,
    compute_pack_version_digest,
    compute_requirement_version_digest,
    compute_source_version_digest,
    format_canonical_datetime,
)


def test_dict_key_ordering_invariance():
    """Different insertion orders of map keys produce identical canonical JSON and digest."""
    d1 = {"z": 100, "a": "hello", "m": [1, 2, 3]}
    d2 = {"a": "hello", "m": [1, 2, 3], "z": 100}
    d3 = {"m": [1, 2, 3], "z": 100, "a": "hello"}

    assert canonical_json(d1) == canonical_json(d2) == canonical_json(d3)
    assert compute_content_digest(d1) == compute_content_digest(d2) == compute_content_digest(d3)
    assert canonical_json(d1) == '{"a":"hello","m":[1,2,3],"z":100}'


def test_missing_vs_null_vs_empty_distinction():
    """Missing key, null value, and empty string produce distinct canonical JSON and digests."""
    d_missing = {"other": 1}
    d_null = {"key": None, "other": 1}
    d_empty = {"key": "", "other": 1}

    j_missing = canonical_json(d_missing)
    j_null = canonical_json(d_null)
    j_empty = canonical_json(d_empty)

    assert j_missing != j_null
    assert j_null != j_empty
    assert j_missing != j_empty

    h_missing = compute_content_digest(d_missing)
    h_null = compute_content_digest(d_null)
    h_empty = compute_content_digest(d_empty)

    assert len({h_missing, h_null, h_empty}) == 3


def test_list_order_preservation():
    """List elements preserve exact sequential order; different orders yield different digests."""
    l1 = ["item1", "item2"]
    l2 = ["item2", "item1"]

    assert canonical_json(l1) != canonical_json(l2)
    assert compute_content_digest(l1) != compute_content_digest(l2)


def test_nan_infinity_rejection():
    """Floating point NaN and Infinity are strictly rejected."""
    with pytest.raises(ValueError):
        canonical_json({"val": float("nan")})

    with pytest.raises(ValueError):
        canonical_json({"val": float("inf")})

    with pytest.raises(ValueError):
        canonical_json({"val": float("-inf")})


def test_uuid_lowercase_formatting():
    """UUIDs are formatted as lowercase hyphenated strings."""
    uid = UUID("12345678-1234-5678-1234-567812345678")
    assert canonical_json({"id": uid}) == '{"id":"12345678-1234-5678-1234-567812345678"}'


def test_datetime_and_date_canonical_formatting():
    """Datetimes are formatted in ISO-8601 with explicit UTC Z suffix and trimmed zero microseconds."""
    dt_zero_micro = datetime(2026, 9, 30, 12, 0, 0, 0, tzinfo=UTC)
    assert format_canonical_datetime(dt_zero_micro) == "2026-09-30T12:00:00Z"
    assert canonical_json({"dt": dt_zero_micro}) == '{"dt":"2026-09-30T12:00:00Z"}'

    dt_micro = datetime(2026, 9, 30, 12, 0, 0, 123450, tzinfo=UTC)
    assert format_canonical_datetime(dt_micro) == "2026-09-30T12:00:00.12345Z"

    d = date(2026, 9, 30)
    assert canonical_json({"d": d}) == '{"d":"2026-09-30"}'


def test_version_digest_calculators():
    """All version digest helper functions return valid 32-byte digests."""
    src_id = uuid4()
    sv_id = uuid4()
    req_id = uuid4()
    ctrl_id = uuid4()
    pack_id = uuid4()
    map_id = uuid4()

    d_src = compute_source_version_digest(
        source_id=src_id,
        edition="2026",
        predecessor_id=None,
        language="en",
        official_locator="https://example.com",
        publication_date=date(2026, 1, 1),
        retrieved_at=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC),
    )
    assert len(d_src) == 32

    d_req = compute_requirement_version_digest(
        requirement_id=req_id,
        source_id=src_id,
        source_version_id=sv_id,
        version_label="v1.0",
        predecessor_id=None,
        revision=1,
        normalized_outcome="Must encrypt data",
        requirement_type="mandatory",
        obligated_actor="Data Controller",
        text_origin="conformly_paraphrase",
        customer_display_text="Data encryption requirement",
        effective_from=date(2026, 1, 1),
        effective_until=None,
        source_references=[
            {
                "locator_kind": "section",
                "locator_value": "4.1",
                "sequence": 1,
                "source_version_id": sv_id,
            }
        ],
    )
    assert len(d_req) == 32

    d_ctrl = compute_control_version_digest(
        control_id=ctrl_id,
        version_label="v1.0",
        predecessor_id=None,
        revision=1,
        title="Encryption at Rest",
        objective="Ensure confidentiality of stored data",
        guidance="Use AES-256-GCM",
        control_type="preventive",
        frequency="continuous",
        automation_level="automated",
        suggested_owner_role="Security Officer",
        assurance_level="foundational",
        tags_state="None",
        tags=None,
    )
    assert len(d_ctrl) == 32

    d_map = compute_mapping_version_digest(
        mapping_id=map_id,
        requirement_id=req_id,
        control_id=ctrl_id,
        requirement_version_id=uuid4(),
        control_version_id=uuid4(),
        requirement_version_revision=1,
        requirement_version_digest=d_req,
        control_version_revision=1,
        control_version_digest=d_ctrl,
        version_label="v1.0",
        predecessor_id=None,
        revision=1,
        mapping_type="Exact",
        rationale="Direct fulfillment",
        covered_dimensions="confidentiality",
        excluded_dimensions=None,
        conditions=None,
        source_basis="expert_analysis",
        confidence="high",
    )
    assert len(d_map) == 32

    d_pack = compute_pack_version_digest(
        pack_id=pack_id,
        version_label="v1.0",
        predecessor_id=None,
        revision=1,
        description="Core security baseline pack",
    )
    assert len(d_pack) == 32

    d_er = compute_evidence_requirement_version_digest(
        control_version_id=ctrl_id,
        control_version_digest=d_ctrl,
        requirement_key="ER-SEC-001",
        sequence=1,
        title="Evidence Requirement 1",
        frequency="monthly",
        custom_frequency=None,
        scope_state="All",
        scope_guidance=None,
        assurance_purpose="operating_effectiveness",
        validity_rule="period_coverage",
        max_age_days=None,
        guidance="Guidance text",
        artifact_types=[{"sequence": 1, "artifact_type": "record"}],
        required_metadata=[{"sequence": 1, "metadata_key": "system_id"}],
    )
    assert len(d_er) == 32

    d_ap = compute_assessment_procedure_version_digest(
        control_version_id=ctrl_id,
        control_version_digest=d_ctrl,
        procedure_key="AP-SEC-001",
        sequence=1,
        title="Assessment Procedure 1",
        objective="Objective text",
        sample_guidance=None,
        scope_guidance=None,
        decision_guidance="Decision guidance",
        assessor_qualifications=None,
        steps=[
            {
                "sequence": 1,
                "step_kind": "inspect",
                "instruction": "Inspect logs",
                "expected_output": None,
            }
        ],
        evidence_requirements=[{"sequence": 1, "id": uuid4(), "content_digest": d_er}],
    )
    assert len(d_ap) == 32


def test_assurance_version_digest_frozen_vectors():
    """Frozen test vectors verify exact deterministic hash stability for assurance content."""
    cv_id = UUID("00000000-0000-0000-0000-000000000001")
    cv_digest = b"\xaa" * 32

    er_digest = compute_evidence_requirement_version_digest(
        control_version_id=cv_id,
        control_version_digest=cv_digest,
        requirement_key="ER-FROZEN-001",
        sequence=1,
        title="Frozen Evidence Requirement",
        frequency="monthly",
        custom_frequency=None,
        scope_state="All",
        scope_guidance=None,
        assurance_purpose="operating_effectiveness",
        validity_rule="period_coverage",
        max_age_days=None,
        guidance="Frozen test guidance.",
        artifact_types=[
            {"sequence": 1, "artifact_type": "record"},
            {"sequence": 2, "artifact_type": "report"},
        ],
        required_metadata=[{"sequence": 1, "metadata_key": "system_id"}],
    )
    assert er_digest.hex() == "04dbae0175edc750a3d618b4c08235c6eeab37ba3baf43485314cc532b18a32e"

    ap_digest = compute_assessment_procedure_version_digest(
        control_version_id=cv_id,
        control_version_digest=cv_digest,
        procedure_key="AP-FROZEN-001",
        sequence=1,
        title="Frozen Assessment Procedure",
        objective="Test frozen objective.",
        sample_guidance="Sample all.",
        scope_guidance=None,
        decision_guidance="Review carefully.",
        assessor_qualifications="Lead Assessor",
        steps=[
            {
                "sequence": 1,
                "step_kind": "inspect",
                "instruction": "Inspect logs",
                "expected_output": "No anomalies",
            }
        ],
        evidence_requirements=[
            {
                "sequence": 1,
                "id": UUID("00000000-0000-0000-0000-000000000002"),
                "content_digest": er_digest,
            }
        ],
    )
    assert ap_digest.hex() == "06065029dff511babad7cc269547a1f04dd7b1ad79581ff6ffac94471c26a0b3"
