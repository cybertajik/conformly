"""Tests for WP-07C2 dormant applicability rule persistence, models, constraints, and digest vectors."""

from datetime import date
from typing import Any
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conformly.catalog_v2.digest import canonical_json, compute_content_digest
from conformly.catalog_v2.models import (
    CatalogApplicabilityRule,
    CatalogApplicabilityRuleFactRef,
    CatalogApplicabilityRuleSourceRef,
    CatalogApplicabilityRuleVersion,
    CatalogFactDefinition,
    CatalogFactDefinitionVersion,
    CatalogPublisher,
    CatalogRequirement,
    CatalogRequirementVersion,
    CatalogSource,
    CatalogSourceVersion,
)
from conformly.catalog_v2.rule_static_validation import (
    FactVersionMetadata,
    RuleValidationError,
    validate_rule_ast,
)
from conformly.db.base import Base


def u(n: int) -> str:
    """Format an integer as a synthetic canonical 36-char lower-case UUID string."""
    return f"00000000-0000-0000-0000-{n:012d}"


# ---------------------------------------------------------------------------
# Section 4: Fixed synthetic digest vectors (not a trust assertion)
# ---------------------------------------------------------------------------


def test_fixed_digest_vector_1() -> None:
    """Vector 1: revision 1, label 1.0.0, null predecessor, target snapshot 0x11*32."""
    ast_1 = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": u(5),
            "op": "EXISTS",
            "scope_type": "tenant",
        },
    }
    can_bytes_1 = canonical_json(ast_1).encode("utf-8")

    payload_1: dict[str, Any] = {
        "kind": "ApplicabilityRuleVersion",
        "rule_id": u(1),
        "rule_key": "synthetic_applicability",
        "requirement_id": u(2),
        "revision": 1,
        "version_label": "1.0.0",
        "predecessor_id": None,
        "predecessor_revision": None,
        "requirement_version_id": u(3),
        "requirement_version_digest": (b"\x11" * 32).hex(),
        "expression_ast_version": 1,
        "expression_canonical_hex": can_bytes_1.hex(),
        "effective_from": None,
        "effective_until": None,
        "status": "Draft",
        "fact_refs": [
            {
                "sequence": 1,
                "fact_definition_version_id": u(5),
                "content_digest": (b"\x22" * 32).hex(),
            }
        ],
        "source_refs": [
            {
                "sequence": 1,
                "source_version_id": u(7),
                "content_digest": (b"\x33" * 32).hex(),
            }
        ],
    }

    digest_1 = compute_content_digest(payload_1)
    expected_1 = "d08cbc02dd81e5ed5f4446bd147140e4a9c47dbb76fa358953e58d257206d3ff"
    assert digest_1.hex() == expected_1

    # Meaning-bearing mutations must change the digest
    for field, mut in [
        ("status", "Active"),
        ("revision", 2),
        ("version_label", "1.0.1"),
        ("rule_key", "synthetic_applicability_mutated"),
        ("requirement_version_digest", (b"\x12" * 32).hex()),
        ("expression_canonical_hex", b'{"ast_version":1,"root":{}}'.hex()),
        ("effective_from", "2026-01-01"),
        ("effective_until", "2026-12-31"),
    ]:
        mutated = dict(payload_1)
        mutated[field] = mut
        assert compute_content_digest(mutated).hex() != expected_1

    # Mutate fact ref and source ref
    mut_fact = dict(payload_1)
    mut_fact["fact_refs"] = [
        {
            "sequence": 1,
            "fact_definition_version_id": u(5),
            "content_digest": (b"\x23" * 32).hex(),
        }
    ]
    assert compute_content_digest(mut_fact).hex() != expected_1

    mut_source = dict(payload_1)
    mut_source["source_refs"] = [
        {
            "sequence": 1,
            "source_version_id": u(7),
            "content_digest": (b"\x34" * 32).hex(),
        }
    ]
    assert compute_content_digest(mut_source).hex() != expected_1


def test_fixed_digest_vector_2() -> None:
    """Vector 2: revision 2, label 2.0.0, predecessor ...0004 rev 1, target snapshot 0x44*32."""
    ast_2 = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": u(6),
            "op": "IN",
            "scope_type": "service",
            "values": ["beta", "alpha"],
        },
    }
    can_bytes_2 = canonical_json(ast_2).encode("utf-8")

    payload_2: dict[str, Any] = {
        "kind": "ApplicabilityRuleVersion",
        "rule_id": u(1),
        "rule_key": "synthetic_applicability",
        "requirement_id": u(2),
        "revision": 2,
        "version_label": "2.0.0",
        "predecessor_id": u(4),
        "predecessor_revision": 1,
        "requirement_version_id": u(8),
        "requirement_version_digest": (b"\x44" * 32).hex(),
        "expression_ast_version": 1,
        "expression_canonical_hex": can_bytes_2.hex(),
        "effective_from": None,
        "effective_until": None,
        "status": "Draft",
        "fact_refs": [
            {
                "sequence": 1,
                "fact_definition_version_id": u(6),
                "content_digest": (b"\x55" * 32).hex(),
            }
        ],
        "source_refs": [
            {
                "sequence": 1,
                "source_version_id": u(9),
                "content_digest": (b"\x66" * 32).hex(),
            }
        ],
    }

    digest_2 = compute_content_digest(payload_2)
    expected_2 = "4fd166f706e9070e6b3386bc752a7fd7e1d490a26d0d32c0a7eee86b08f2a86e"
    assert digest_2.hex() == expected_2

    # Meaning-bearing mutations must change digest
    mutated = dict(payload_2)
    mutated["version_label"] = "2.0.1"
    assert compute_content_digest(mutated).hex() != expected_2


# ---------------------------------------------------------------------------
# Model and Schema Metadata Inspection
# ---------------------------------------------------------------------------


def test_models_metadata_and_constraints() -> None:
    """Verify table schema, column definitions, and constraint names in SQLAlchemy metadata."""
    tables = Base.metadata.tables

    # 1. catalog_applicability_rules
    assert "catalog_applicability_rules" in tables
    rules_t = tables["catalog_applicability_rules"]
    assert "id" in rules_t.c and rules_t.c["id"].primary_key
    assert "rule_key" in rules_t.c and not rules_t.c["rule_key"].nullable
    assert "requirement_id" in rules_t.c and not rules_t.c["requirement_id"].nullable
    assert "status" in rules_t.c and not rules_t.c["status"].nullable

    rule_c_names = {c.name for c in rules_t.constraints if c.name}
    assert "fk_catalog_app_rules_requirement" in rule_c_names
    assert "uq_catalog_app_rules_id_requirement" in rule_c_names
    assert "uq_catalog_app_rules_key" in rule_c_names
    assert "ck_catalog_applicability_rules_app_rule_key_format" in rule_c_names
    assert "ck_catalog_applicability_rules_app_rule_key_length" in rule_c_names
    assert "ck_catalog_applicability_rules_app_rule_status_draft" in rule_c_names

    # 2. catalog_applicability_rule_versions
    assert "catalog_applicability_rule_versions" in tables
    ver_t = tables["catalog_applicability_rule_versions"]
    assert "id" in ver_t.c and ver_t.c["id"].primary_key
    assert "rule_id" in ver_t.c and not ver_t.c["rule_id"].nullable
    assert "requirement_id" in ver_t.c and not ver_t.c["requirement_id"].nullable
    assert "requirement_version_id" in ver_t.c and not ver_t.c["requirement_version_id"].nullable
    assert (
        "requirement_version_digest_snapshot" in ver_t.c
        and not ver_t.c["requirement_version_digest_snapshot"].nullable
    )
    assert "revision" in ver_t.c and not ver_t.c["revision"].nullable
    assert "version_label" in ver_t.c and not ver_t.c["version_label"].nullable
    assert "predecessor_id" in ver_t.c and ver_t.c["predecessor_id"].nullable
    assert "predecessor_revision" in ver_t.c and ver_t.c["predecessor_revision"].nullable
    assert "expression_ast_version" in ver_t.c and not ver_t.c["expression_ast_version"].nullable
    assert "expression_canonical" in ver_t.c and not ver_t.c["expression_canonical"].nullable
    assert "status" in ver_t.c and not ver_t.c["status"].nullable
    assert "content_digest" in ver_t.c and not ver_t.c["content_digest"].nullable
    assert "digest_schema" in ver_t.c and not ver_t.c["digest_schema"].nullable

    ver_c_names = {c.name for c in ver_t.constraints if c.name}
    assert "fk_catalog_app_rule_versions_rule" in ver_c_names
    assert "fk_catalog_app_rule_versions_req_version" in ver_c_names
    assert "fk_catalog_app_rule_versions_predecessor" in ver_c_names
    assert "uq_catalog_app_rule_versions_rule_rev" in ver_c_names
    assert "uq_catalog_app_rule_versions_rule_label" in ver_c_names
    assert "uq_catalog_app_rule_versions_lineage" in ver_c_names
    assert "ck_catalog_applicability_rule_versions_app_rule_version_revision_bounds" in ver_c_names
    assert (
        "ck_catalog_applicability_rule_versions_app_rule_version_predecessor_shape" in ver_c_names
    )
    assert "ck_catalog_applicability_rule_versions_app_rule_version_label_trim" in ver_c_names
    assert "ck_catalog_applicability_rule_versions_app_rule_version_ast_version" in ver_c_names
    assert "ck_catalog_applicability_rule_versions_app_rule_version_expression_bytes" in ver_c_names
    assert "ck_catalog_applicability_rule_versions_app_rule_version_effective_dates" in ver_c_names
    assert "ck_catalog_applicability_rule_versions_app_rule_version_status_draft" in ver_c_names
    assert "ck_catalog_applicability_rule_versions_app_rule_version_digest_32_bytes" in ver_c_names
    assert "ck_catalog_applicability_rule_versions_app_rule_version_digest_schema" in ver_c_names
    assert (
        "ck_catalog_applicability_rule_versions_app_rule_version_target_digest_32_bytes"
        in ver_c_names
    )

    # 3. catalog_applicability_rule_fact_refs
    assert "catalog_applicability_rule_fact_refs" in tables
    f_ref_t = tables["catalog_applicability_rule_fact_refs"]
    f_ref_names = {c.name for c in f_ref_t.constraints if c.name}
    assert "fk_catalog_app_fact_refs_rule_version" in f_ref_names
    assert "fk_catalog_app_fact_refs_fact_version" in f_ref_names
    assert "uq_catalog_app_fact_refs_version_seq" in f_ref_names
    assert "uq_catalog_app_fact_refs_version_fact" in f_ref_names
    assert "ck_catalog_applicability_rule_fact_refs_app_fact_ref_sequence_bounds" in f_ref_names
    assert "ck_catalog_applicability_rule_fact_refs_app_fact_ref_digest_32_bytes" in f_ref_names

    # 4. catalog_applicability_rule_source_refs
    assert "catalog_applicability_rule_source_refs" in tables
    s_ref_t = tables["catalog_applicability_rule_source_refs"]
    s_ref_names = {c.name for c in s_ref_t.constraints if c.name}
    assert "fk_catalog_app_source_refs_rule_version" in s_ref_names
    assert "fk_catalog_app_source_refs_source_version" in s_ref_names
    assert "uq_catalog_app_source_refs_version_seq" in s_ref_names
    assert "uq_catalog_app_source_refs_version_source" in s_ref_names
    assert "ck_catalog_applicability_rule_source_refs_app_source_ref_sequence_bounds" in s_ref_names
    assert "ck_catalog_applicability_rule_source_refs_app_source_ref_digest_32_bytes" in s_ref_names


# ---------------------------------------------------------------------------
# SQLite Fixture and Test Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_session():
    engine = create_engine("sqlite:///:memory:")

    @sa.event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _create_hierarchy(session: Session):
    """Create parent rows needed for foreign key satisfaction in tests."""
    pub = CatalogPublisher(id=uuid4(), publisher_key=f"pub_{uuid4().hex[:8]}", name="Publisher")
    session.add(pub)
    session.flush()

    src = CatalogSource(
        id=uuid4(), publisher_id=pub.id, source_key=f"src_{uuid4().hex[:8]}", title="Source"
    )
    session.add(src)
    session.flush()

    src_ver = CatalogSourceVersion(id=UUID(u(7)), source_id=src.id, edition="2026-v1")
    session.add(src_ver)
    session.flush()

    req = CatalogRequirement(
        id=UUID(u(2)), source_id=src.id, requirement_key=f"req_{uuid4().hex[:8]}"
    )
    session.add(req)
    session.flush()

    req_ver = CatalogRequirementVersion(
        id=UUID(u(3)),
        requirement_id=req.id,
        source_id=src.id,
        source_version_id=src_ver.id,
        version_label="1.0.0",
        normalized_outcome="Outcome",
        requirement_type="mandatory",
        obligated_actor="controller",
        text_origin="conformly_paraphrase",
        customer_display_text="Display",
        effective_from=date(2026, 1, 1),
        effective_until=date(2027, 1, 1),
    )
    session.add(req_ver)
    session.flush()

    fact_def = CatalogFactDefinition(id=uuid4(), fact_key=f"fact_{uuid4().hex[:8]}", status="Draft")
    session.add(fact_def)
    session.flush()

    fact_ver = CatalogFactDefinitionVersion(
        id=UUID(u(5)),
        fact_definition_id=fact_def.id,
        revision=1,
        version_label="1.0.0",
        label="Fact",
        description="Fact desc",
        value_type="boolean",
        sensitivity="Internal",
        status="Draft",
        content_digest=b"\x22" * 32,
        digest_schema="catalog-fact-definition-draft-v1",
    )
    session.add(fact_ver)
    session.flush()

    return {
        "pub": pub,
        "src": src,
        "src_ver": src_ver,
        "req": req,
        "req_ver": req_ver,
        "fact_def": fact_def,
        "fact_ver": fact_ver,
    }


# ---------------------------------------------------------------------------
# Positive SQLite Lifecycle Round-Trip
# ---------------------------------------------------------------------------


def test_positive_round_trip(sqlite_session: Session) -> None:
    """Verify insertion, foreign keys, and query round-trip for all 4 tables."""
    h = _create_hierarchy(sqlite_session)
    rule_id = UUID(u(1))
    req_id = h["req"].id
    req_ver_id = h["req_ver"].id
    fact_ver_id = h["fact_ver"].id
    src_ver_id = h["src_ver"].id

    # 1. Insert Rule
    rule = CatalogApplicabilityRule(
        id=rule_id,
        rule_key="synthetic_applicability",
        requirement_id=req_id,
        status="Draft",
    )
    sqlite_session.add(rule)
    sqlite_session.flush()

    # 2. Insert Rule Version 1
    ast = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(fact_ver_id).lower(),
            "op": "EXISTS",
            "scope_type": "tenant",
        },
    }
    can_bytes = canonical_json(ast).encode("utf-8")
    expected_hash = "d08cbc02dd81e5ed5f4446bd147140e4a9c47dbb76fa358953e58d257206d3ff"
    v1_id = uuid4()
    r_ver1 = CatalogApplicabilityRuleVersion(
        id=v1_id,
        rule_id=rule_id,
        requirement_id=req_id,
        requirement_version_id=req_ver_id,
        requirement_version_digest_snapshot=b"\x11" * 32,
        revision=1,
        version_label="1.0.0",
        predecessor_id=None,
        predecessor_revision=None,
        expression_ast_version=1,
        expression_canonical=can_bytes,
        effective_from=None,
        effective_until=None,
        status="Draft",
        content_digest=bytes.fromhex(expected_hash),
        digest_schema="catalog-applicability-rule-draft-v1",
    )
    sqlite_session.add(r_ver1)
    sqlite_session.flush()

    # 3. Insert Fact Ref
    f_ref = CatalogApplicabilityRuleFactRef(
        id=uuid4(),
        rule_version_id=v1_id,
        sequence=1,
        fact_definition_version_id=fact_ver_id,
        content_digest_snapshot=b"\x22" * 32,
    )
    sqlite_session.add(f_ref)
    sqlite_session.flush()

    # 4. Insert Source Ref
    s_ref = CatalogApplicabilityRuleSourceRef(
        id=uuid4(),
        rule_version_id=v1_id,
        sequence=1,
        source_version_id=src_ver_id,
        content_digest_snapshot=b"\x33" * 32,
    )
    sqlite_session.add(s_ref)
    sqlite_session.flush()

    # 5. Insert Rule Version 2 with predecessor
    v2_id = uuid4()
    r_ver2 = CatalogApplicabilityRuleVersion(
        id=v2_id,
        rule_id=rule_id,
        requirement_id=req_id,
        requirement_version_id=req_ver_id,
        requirement_version_digest_snapshot=b"\x11" * 32,
        revision=2,
        version_label="2.0.0",
        predecessor_id=v1_id,
        predecessor_revision=1,
        expression_ast_version=1,
        expression_canonical=can_bytes,
        effective_from=None,
        effective_until=None,
        status="Draft",
        content_digest=b"\x99" * 32,
        digest_schema="catalog-applicability-rule-draft-v1",
    )
    sqlite_session.add(r_ver2)
    sqlite_session.flush()

    # Query loaded rows
    loaded_rule = sqlite_session.get(CatalogApplicabilityRule, rule_id)
    assert loaded_rule is not None
    assert loaded_rule.rule_key == "synthetic_applicability"

    loaded_v1 = sqlite_session.get(CatalogApplicabilityRuleVersion, v1_id)
    assert loaded_v1 is not None
    assert loaded_v1.revision == 1
    assert loaded_v1.content_digest == bytes.fromhex(expected_hash)

    loaded_v2 = sqlite_session.get(CatalogApplicabilityRuleVersion, v2_id)
    assert loaded_v2 is not None
    assert loaded_v2.predecessor_id == v1_id
    assert loaded_v2.predecessor_revision == 1


# ---------------------------------------------------------------------------
# Negative Tests: Check Constraints and Integrity Errors
# ---------------------------------------------------------------------------


def test_negative_rule_key_format(sqlite_session: Session) -> None:
    """Reject rule_key violating regex ^[a-z][a-z0-9_]{2,63}$."""
    h = _create_hierarchy(sqlite_session)
    for bad_key in ["1rule", "UPPER", "a-b", "ab", "a" * 65]:
        with pytest.raises(IntegrityError):
            sqlite_session.add(
                CatalogApplicabilityRule(
                    id=uuid4(),
                    rule_key=bad_key,
                    requirement_id=h["req"].id,
                    status="Draft",
                )
            )
            sqlite_session.flush()
        sqlite_session.rollback()


def test_negative_rule_status_draft_only(sqlite_session: Session) -> None:
    """Reject non-Draft status on rule table."""
    h = _create_hierarchy(sqlite_session)
    with pytest.raises(IntegrityError):
        sqlite_session.add(
            CatalogApplicabilityRule(
                id=uuid4(),
                rule_key="valid_rule_key",
                requirement_id=h["req"].id,
                status="Active",
            )
        )
        sqlite_session.flush()
    sqlite_session.rollback()


def test_negative_rule_version_cross_requirement_lineage(sqlite_session: Session) -> None:
    """Reject rule version pointing to a different requirement than its parent rule."""
    h = _create_hierarchy(sqlite_session)
    rule = CatalogApplicabilityRule(
        id=uuid4(),
        rule_key="rule_cross_req",
        requirement_id=h["req"].id,
        status="Draft",
    )
    sqlite_session.add(rule)
    sqlite_session.flush()

    # Mismatched requirement_id on version violates fk_catalog_app_rule_versions_rule
    other_req_id = uuid4()
    with pytest.raises(IntegrityError):
        sqlite_session.add(
            CatalogApplicabilityRuleVersion(
                id=uuid4(),
                rule_id=rule.id,
                requirement_id=other_req_id,
                requirement_version_id=h["req_ver"].id,
                requirement_version_digest_snapshot=b"\x11" * 32,
                revision=1,
                version_label="1.0.0",
                expression_ast_version=1,
                expression_canonical=b"{}",
                status="Draft",
                content_digest=b"\x22" * 32,
                digest_schema="catalog-applicability-rule-draft-v1",
            )
        )
        sqlite_session.flush()
    sqlite_session.rollback()


def test_negative_predecessor_shape(sqlite_session: Session) -> None:
    """Reject invalid revision 1 or revision > 1 predecessor shapes."""
    h = _create_hierarchy(sqlite_session)
    rule = CatalogApplicabilityRule(
        id=uuid4(),
        rule_key="rule_pred_shape",
        requirement_id=h["req"].id,
        status="Draft",
    )
    sqlite_session.add(rule)
    sqlite_session.flush()

    # Rev 1 with non-null predecessor_id
    with pytest.raises(IntegrityError):
        sqlite_session.add(
            CatalogApplicabilityRuleVersion(
                id=uuid4(),
                rule_id=rule.id,
                requirement_id=h["req"].id,
                requirement_version_id=h["req_ver"].id,
                requirement_version_digest_snapshot=b"\x11" * 32,
                revision=1,
                version_label="1.0.0",
                predecessor_id=uuid4(),
                predecessor_revision=None,
                expression_ast_version=1,
                expression_canonical=b"{}",
                status="Draft",
                content_digest=b"\x22" * 32,
                digest_schema="catalog-applicability-rule-draft-v1",
            )
        )
        sqlite_session.flush()
    sqlite_session.rollback()

    # Rev 2 with null predecessor_id
    with pytest.raises(IntegrityError):
        sqlite_session.add(
            CatalogApplicabilityRuleVersion(
                id=uuid4(),
                rule_id=rule.id,
                requirement_id=h["req"].id,
                requirement_version_id=h["req_ver"].id,
                requirement_version_digest_snapshot=b"\x11" * 32,
                revision=2,
                version_label="2.0.0",
                predecessor_id=None,
                predecessor_revision=None,
                expression_ast_version=1,
                expression_canonical=b"{}",
                status="Draft",
                content_digest=b"\x22" * 32,
                digest_schema="catalog-applicability-rule-draft-v1",
            )
        )
        sqlite_session.flush()
    sqlite_session.rollback()

    # Rev 2 with predecessor_id == id
    self_id = uuid4()
    with pytest.raises(IntegrityError):
        sqlite_session.add(
            CatalogApplicabilityRuleVersion(
                id=self_id,
                rule_id=rule.id,
                requirement_id=h["req"].id,
                requirement_version_id=h["req_ver"].id,
                requirement_version_digest_snapshot=b"\x11" * 32,
                revision=2,
                version_label="2.0.0",
                predecessor_id=self_id,
                predecessor_revision=1,
                expression_ast_version=1,
                expression_canonical=b"{}",
                status="Draft",
                content_digest=b"\x22" * 32,
                digest_schema="catalog-applicability-rule-draft-v1",
            )
        )
        sqlite_session.flush()
    sqlite_session.rollback()


def test_negative_version_field_checks(sqlite_session: Session) -> None:
    """Verify check constraints on version fields: label trim, AST version, bytes length, dates, digests."""
    h = _create_hierarchy(sqlite_session)
    rule = CatalogApplicabilityRule(
        id=uuid4(),
        rule_key="rule_field_checks",
        requirement_id=h["req"].id,
        status="Draft",
    )
    sqlite_session.add(rule)
    sqlite_session.flush()

    base_args = {
        "rule_id": rule.id,
        "requirement_id": h["req"].id,
        "requirement_version_id": h["req_ver"].id,
        "requirement_version_digest_snapshot": b"\x11" * 32,
        "revision": 1,
        "version_label": "1.0.0",
        "predecessor_id": None,
        "predecessor_revision": None,
        "expression_ast_version": 1,
        "expression_canonical": b"{}",
        "effective_from": None,
        "effective_until": None,
        "status": "Draft",
        "content_digest": b"\x22" * 32,
        "digest_schema": "catalog-applicability-rule-draft-v1",
    }

    # Untrimmed version_label
    with pytest.raises(IntegrityError):
        sqlite_session.add(
            CatalogApplicabilityRuleVersion(
                id=uuid4(), **(base_args | {"version_label": " 1.0.0 "})
            )
        )
        sqlite_session.flush()
    sqlite_session.rollback()

    # expression_ast_version != 1
    with pytest.raises(IntegrityError):
        sqlite_session.add(
            CatalogApplicabilityRuleVersion(
                id=uuid4(), **(base_args | {"expression_ast_version": 2})
            )
        )
        sqlite_session.flush()
    sqlite_session.rollback()

    # expression_canonical too short (< 2 bytes)
    with pytest.raises(IntegrityError):
        sqlite_session.add(
            CatalogApplicabilityRuleVersion(
                id=uuid4(), **(base_args | {"expression_canonical": b"{"})
            )
        )
        sqlite_session.flush()
    sqlite_session.rollback()

    # Invalid effective date ordering
    with pytest.raises(IntegrityError):
        sqlite_session.add(
            CatalogApplicabilityRuleVersion(
                id=uuid4(),
                **(
                    base_args
                    | {"effective_from": date(2027, 1, 1), "effective_until": date(2026, 1, 1)}
                ),
            )
        )
        sqlite_session.flush()
    sqlite_session.rollback()

    # Invalid content_digest length (31 bytes)
    with pytest.raises(IntegrityError):
        sqlite_session.add(
            CatalogApplicabilityRuleVersion(
                id=uuid4(), **(base_args | {"content_digest": b"\x22" * 31})
            )
        )
        sqlite_session.flush()
    sqlite_session.rollback()

    # Invalid target digest length (31 bytes)
    with pytest.raises(IntegrityError):
        sqlite_session.add(
            CatalogApplicabilityRuleVersion(
                id=uuid4(), **(base_args | {"requirement_version_digest_snapshot": b"\x11" * 31})
            )
        )
        sqlite_session.flush()
    sqlite_session.rollback()

    # Invalid digest schema
    with pytest.raises(IntegrityError):
        sqlite_session.add(
            CatalogApplicabilityRuleVersion(
                id=uuid4(), **(base_args | {"digest_schema": "wrong-schema"})
            )
        )
        sqlite_session.flush()
    sqlite_session.rollback()


def test_negative_fact_and_source_ref_checks(sqlite_session: Session) -> None:
    """Verify check constraints and duplicate unique constraints on fact and source refs."""
    h = _create_hierarchy(sqlite_session)
    rule = CatalogApplicabilityRule(
        id=uuid4(),
        rule_key="rule_refs_checks",
        requirement_id=h["req"].id,
        status="Draft",
    )
    sqlite_session.add(rule)
    sqlite_session.flush()

    v_id = uuid4()
    r_ver = CatalogApplicabilityRuleVersion(
        id=v_id,
        rule_id=rule.id,
        requirement_id=h["req"].id,
        requirement_version_id=h["req_ver"].id,
        requirement_version_digest_snapshot=b"\x11" * 32,
        revision=1,
        version_label="1.0.0",
        predecessor_id=None,
        predecessor_revision=None,
        expression_ast_version=1,
        expression_canonical=b"{}",
        status="Draft",
        content_digest=b"\x22" * 32,
        digest_schema="catalog-applicability-rule-draft-v1",
    )
    sqlite_session.add(r_ver)
    sqlite_session.flush()

    # Fact ref sequence out of bounds (0)
    with pytest.raises(IntegrityError):
        with sqlite_session.begin_nested():
            sqlite_session.add(
                CatalogApplicabilityRuleFactRef(
                    id=uuid4(),
                    rule_version_id=v_id,
                    sequence=0,
                    fact_definition_version_id=h["fact_ver"].id,
                    content_digest_snapshot=b"\x22" * 32,
                )
            )
            sqlite_session.flush()

    # Fact ref snapshot wrong length (33 bytes)
    with pytest.raises(IntegrityError):
        with sqlite_session.begin_nested():
            sqlite_session.add(
                CatalogApplicabilityRuleFactRef(
                    id=uuid4(),
                    rule_version_id=v_id,
                    sequence=1,
                    fact_definition_version_id=h["fact_ver"].id,
                    content_digest_snapshot=b"\x22" * 33,
                )
            )
            sqlite_session.flush()

    # Source ref sequence out of bounds (65)
    with pytest.raises(IntegrityError):
        with sqlite_session.begin_nested():
            sqlite_session.add(
                CatalogApplicabilityRuleSourceRef(
                    id=uuid4(),
                    rule_version_id=v_id,
                    sequence=65,
                    source_version_id=h["src_ver"].id,
                    content_digest_snapshot=b"\x33" * 32,
                )
            )
            sqlite_session.flush()

    # Duplicate sequence on fact refs
    f1 = CatalogApplicabilityRuleFactRef(
        id=uuid4(),
        rule_version_id=v_id,
        sequence=1,
        fact_definition_version_id=h["fact_ver"].id,
        content_digest_snapshot=b"\x22" * 32,
    )
    sqlite_session.add(f1)
    sqlite_session.flush()

    with pytest.raises(IntegrityError):
        with sqlite_session.begin_nested():
            sqlite_session.add(
                CatalogApplicabilityRuleFactRef(
                    id=uuid4(),
                    rule_version_id=v_id,
                    sequence=1,
                    fact_definition_version_id=uuid4(),
                    content_digest_snapshot=b"\x22" * 32,
                )
            )
            sqlite_session.flush()


# ---------------------------------------------------------------------------
# Incomplete Draft Persistence (Explicitly Not Usable)
# ---------------------------------------------------------------------------


def test_synthetic_incomplete_draft_persisted_but_not_usable(sqlite_session: Session) -> None:
    """A synthetic incomplete Draft persists in the DB but is rejected by static validation."""
    h = _create_hierarchy(sqlite_session)
    rule = CatalogApplicabilityRule(
        id=uuid4(),
        rule_key="incomplete_rule",
        requirement_id=h["req"].id,
        status="Draft",
    )
    sqlite_session.add(rule)
    sqlite_session.flush()

    # Synthesize an incomplete Draft with empty enum codes on an enum-typed fact reference
    # The database accepts it because the schema only validates row-level bounds.
    raw_invalid_ast = canonical_json(
        {
            "ast_version": 1,
            "root": {
                "op": "EQUALS",
                "fact_definition_version_id": str(h["fact_ver"].id).lower(),
                "scope_type": "tenant",
                "value": "non_existent_code",
            },
        }
    ).encode("utf-8")

    r_ver = CatalogApplicabilityRuleVersion(
        id=uuid4(),
        rule_id=rule.id,
        requirement_id=h["req"].id,
        requirement_version_id=h["req_ver"].id,
        requirement_version_digest_snapshot=b"\x11" * 32,
        revision=1,
        version_label="1.0.0",
        predecessor_id=None,
        predecessor_revision=None,
        expression_ast_version=1,
        expression_canonical=raw_invalid_ast,
        status="Draft",
        content_digest=b"\x77" * 32,
        digest_schema="catalog-applicability-rule-draft-v1",
    )
    sqlite_session.add(r_ver)
    sqlite_session.flush()

    # The incomplete Draft row is persisted in the database
    persisted = sqlite_session.get(CatalogApplicabilityRuleVersion, r_ver.id)
    assert persisted is not None

    # But static validation (WP-07C1) rejects it: enum EQUALS on a boolean fact or empty enum metadata
    meta = FactVersionMetadata(
        fact_definition_id=h["fact_def"].id,
        value_type="boolean",
        scope_types=frozenset({"tenant"}),
        enum_codes=frozenset(),
    )
    with pytest.raises(RuleValidationError) as exc:
        validate_rule_ast(
            persisted.expression_canonical, {h["fact_ver"].id: meta}, [h["fact_ver"].id]
        )
    assert exc.value.code == "AST_SCHEMA"
