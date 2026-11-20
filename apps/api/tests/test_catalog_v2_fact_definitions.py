"""Tests for WP-07B dormant FactDefinition schema foundation and digest vectors."""

from datetime import date
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conformly.catalog_v2.digest import canonical_json, compute_content_digest
from conformly.catalog_v2.models import (
    CatalogFactDefinition,
    CatalogFactDefinitionEnumValue,
    CatalogFactDefinitionScope,
    CatalogFactDefinitionVersion,
)
from conformly.db.base import Base

# ---------------------------------------------------------------------------
# Appendix A: Fixed synthetic digest vectors
# ---------------------------------------------------------------------------


def test_appendix_a_boolean_fixed_digest_vector() -> None:
    expected_raw = (
        '{"allowed_scopes":[{"scope_type":"tenant","sequence":1}],'
        '"collection_guidance":null,'
        '"description":"Invented Boolean input for schema tests.",'
        '"effective_from":null,'
        '"effective_until":null,'
        '"enum_values":[],'
        '"fact_definition_id":"00000000-0000-0000-0000-000000000001",'
        '"fact_key":"synthetic_condition_met",'
        '"kind":"FactDefinitionVersion",'
        '"label":"Synthetic condition met",'
        '"predecessor_id":null,'
        '"predecessor_revision":null,'
        '"revision":1,'
        '"sensitivity":"Internal",'
        '"status":"Draft",'
        '"value_type":"boolean",'
        '"version_label":"1.0.0"}'
    )
    expected_hash = "c0e72a2416eaf7e730a3758f0f9bc06e28fb78a1b776f40dab0aba2bcd4a17f9"

    b_dict = {
        "allowed_scopes": [{"scope_type": "tenant", "sequence": 1}],
        "collection_guidance": None,
        "description": "Invented Boolean input for schema tests.",
        "effective_from": None,
        "effective_until": None,
        "enum_values": [],
        "fact_definition_id": "00000000-0000-0000-0000-000000000001",
        "fact_key": "synthetic_condition_met",
        "kind": "FactDefinitionVersion",
        "label": "Synthetic condition met",
        "predecessor_id": None,
        "predecessor_revision": None,
        "revision": 1,
        "sensitivity": "Internal",
        "status": "Draft",
        "value_type": "boolean",
        "version_label": "1.0.0",
    }

    raw = canonical_json(b_dict)
    assert raw == expected_raw
    h = compute_content_digest(b_dict).hex()
    assert h == expected_hash

    # Verify mutation changes digest
    for field, mut in [
        ("label", "Synthetic condition altered"),
        ("sensitivity", "Confidential"),
        ("revision", 2),
        ("version_label", "1.0.1"),
        ("value_type", "integer"),
        ("description", "Altered description."),
        ("collection_guidance", "Guidance added."),
        ("effective_from", "2026-01-01"),
        ("effective_until", "2026-12-31"),
    ]:
        mutated: dict[str, Any] = dict(b_dict)
        mutated[field] = mut
        assert canonical_json(mutated) != expected_raw
        m_hash = compute_content_digest(mutated).hex()
        assert m_hash != expected_hash


def test_appendix_a_enum_fixed_digest_vector() -> None:
    expected_raw = (
        '{"allowed_scopes":[{"scope_type":"legal_entity","sequence":1},{"scope_type":"service","sequence":2}],'
        '"collection_guidance":"Use invented values only.",'
        '"description":"Invented enum input for schema tests.",'
        '"effective_from":null,'
        '"effective_until":null,'
        '"enum_values":[{"code":"alpha","label":"Alpha","sequence":1},{"code":"beta","label":"Beta","sequence":2}],'
        '"fact_definition_id":"00000000-0000-0000-0000-000000000002",'
        '"fact_key":"synthetic_entity_state",'
        '"kind":"FactDefinitionVersion",'
        '"label":"Synthetic entity state",'
        '"predecessor_id":null,'
        '"predecessor_revision":null,'
        '"revision":1,'
        '"sensitivity":"Confidential",'
        '"status":"Draft",'
        '"value_type":"enum",'
        '"version_label":"1.0.0"}'
    )
    expected_hash = "9f2ecfd7827b3d2bd555ecc1aeef39fc49652f990b9ebd9173e78e88a22f3d36"

    e_dict = {
        "allowed_scopes": [
            {"scope_type": "legal_entity", "sequence": 1},
            {"scope_type": "service", "sequence": 2},
        ],
        "collection_guidance": "Use invented values only.",
        "description": "Invented enum input for schema tests.",
        "effective_from": None,
        "effective_until": None,
        "enum_values": [
            {"code": "alpha", "label": "Alpha", "sequence": 1},
            {"code": "beta", "label": "Beta", "sequence": 2},
        ],
        "fact_definition_id": "00000000-0000-0000-0000-000000000002",
        "fact_key": "synthetic_entity_state",
        "kind": "FactDefinitionVersion",
        "label": "Synthetic entity state",
        "predecessor_id": None,
        "predecessor_revision": None,
        "revision": 1,
        "sensitivity": "Confidential",
        "status": "Draft",
        "value_type": "enum",
        "version_label": "1.0.0",
    }

    raw = canonical_json(e_dict)
    assert raw == expected_raw
    h = compute_content_digest(e_dict).hex()
    assert h == expected_hash

    # Verify mutation changes digest
    mutated: dict[str, Any] = dict(e_dict)
    mutated["enum_values"] = [
        {"code": "alpha", "label": "Alpha", "sequence": 1},
        {"code": "gamma", "label": "Gamma", "sequence": 2},
    ]
    assert compute_content_digest(mutated).hex() != expected_hash


# ---------------------------------------------------------------------------
# SQLite Fixture & Table Creation
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Positive Round Trip with Persisted Dynamic Recomputation
# ---------------------------------------------------------------------------


def test_fact_definition_round_trip(sqlite_session: Session) -> None:
    # 1. Boolean FactDefinition + Version 1 + Scope
    bool_def_id = UUID("00000000-0000-0000-0000-000000000001")
    bool_expected_hash = "c0e72a2416eaf7e730a3758f0f9bc06e28fb78a1b776f40dab0aba2bcd4a17f9"
    bool_digest = bytes.fromhex(bool_expected_hash)

    # Derive canonical JSON and digest from complete aggregate payload BEFORE insert
    bool_pre_insert_payload = {
        "allowed_scopes": [{"scope_type": "tenant", "sequence": 1}],
        "collection_guidance": None,
        "description": "Invented Boolean input for schema tests.",
        "effective_from": None,
        "effective_until": None,
        "enum_values": [],
        "fact_definition_id": str(bool_def_id).lower(),
        "fact_key": "synthetic_condition_met",
        "kind": "FactDefinitionVersion",
        "label": "Synthetic condition met",
        "predecessor_id": None,
        "predecessor_revision": None,
        "revision": 1,
        "sensitivity": "Internal",
        "status": "Draft",
        "value_type": "boolean",
        "version_label": "1.0.0",
    }
    assert compute_content_digest(bool_pre_insert_payload) == bool_digest

    bool_def = CatalogFactDefinition(
        id=bool_def_id,
        fact_key="synthetic_condition_met",
        status="Draft",
    )
    sqlite_session.add(bool_def)
    sqlite_session.flush()

    bool_v1_id = uuid4()
    bool_v1 = CatalogFactDefinitionVersion(
        id=bool_v1_id,
        fact_definition_id=bool_def_id,
        revision=1,
        version_label="1.0.0",
        predecessor_id=None,
        predecessor_revision=None,
        label="Synthetic condition met",
        description="Invented Boolean input for schema tests.",
        collection_guidance=None,
        value_type="boolean",
        sensitivity="Internal",
        effective_from=None,
        effective_until=None,
        status="Draft",
        content_digest=bool_digest,
        digest_schema="catalog-fact-definition-draft-v1",
    )
    sqlite_session.add(bool_v1)
    sqlite_session.flush()

    bool_scope = CatalogFactDefinitionScope(
        id=uuid4(),
        fact_definition_version_id=bool_v1_id,
        sequence=1,
        scope_type="tenant",
    )
    sqlite_session.add(bool_scope)
    sqlite_session.flush()

    # Query persisted parent and ordered children from database
    loaded_def = sqlite_session.get(CatalogFactDefinition, bool_def_id)
    assert loaded_def is not None
    assert loaded_def.fact_key == "synthetic_condition_met"
    assert loaded_def.status == "Draft"

    loaded_v1 = sqlite_session.get(CatalogFactDefinitionVersion, bool_v1_id)
    assert loaded_v1 is not None
    assert loaded_v1.revision == 1
    assert loaded_v1.version_label == "1.0.0"
    assert loaded_v1.predecessor_id is None
    assert loaded_v1.content_digest == bool_digest

    loaded_bool_scopes = (
        sqlite_session.query(CatalogFactDefinitionScope)
        .filter_by(fact_definition_version_id=bool_v1_id)
        .order_by(CatalogFactDefinitionScope.sequence)
        .all()
    )
    assert len(loaded_bool_scopes) == 1
    loaded_bool_enums = (
        sqlite_session.query(CatalogFactDefinitionEnumValue)
        .filter_by(fact_definition_version_id=bool_v1_id)
        .order_by(CatalogFactDefinitionEnumValue.sequence)
        .all()
    )
    assert len(loaded_bool_enums) == 0

    # Reconstruct canonical payload strictly from selected persisted database values
    reconstructed_bool = {
        "allowed_scopes": [
            {"scope_type": s.scope_type, "sequence": s.sequence} for s in loaded_bool_scopes
        ],
        "collection_guidance": loaded_v1.collection_guidance,
        "description": loaded_v1.description,
        "effective_from": loaded_v1.effective_from,
        "effective_until": loaded_v1.effective_until,
        "enum_values": [
            {"code": ev.code, "label": ev.label, "sequence": ev.sequence}
            for ev in loaded_bool_enums
        ],
        "fact_definition_id": str(loaded_def.id).lower(),
        "fact_key": loaded_def.fact_key,
        "kind": "FactDefinitionVersion",
        "label": loaded_v1.label,
        "predecessor_id": str(loaded_v1.predecessor_id).lower()
        if loaded_v1.predecessor_id
        else None,
        "predecessor_revision": loaded_v1.predecessor_revision,
        "revision": loaded_v1.revision,
        "sensitivity": loaded_v1.sensitivity,
        "status": loaded_v1.status,
        "value_type": loaded_v1.value_type,
        "version_label": loaded_v1.version_label,
    }
    recomputed_bool_digest = compute_content_digest(reconstructed_bool)
    assert recomputed_bool_digest == loaded_v1.content_digest
    assert recomputed_bool_digest == bool_digest
    assert recomputed_bool_digest.hex() == bool_expected_hash

    # Meaningful-field mutation negative on reconstructed aggregate
    mutated_reconstructed_bool = dict(reconstructed_bool)
    mutated_reconstructed_bool["label"] = "Altered Label"
    assert compute_content_digest(mutated_reconstructed_bool) != bool_digest

    # 2. Enum FactDefinition + Version 1 + Scopes + EnumValues (Appendix A vector: null effective dates)
    enum_def_id = UUID("00000000-0000-0000-0000-000000000002")
    enum_expected_hash = "9f2ecfd7827b3d2bd555ecc1aeef39fc49652f990b9ebd9173e78e88a22f3d36"
    enum_digest = bytes.fromhex(enum_expected_hash)

    # Derive canonical JSON and digest from complete aggregate payload BEFORE insert
    enum_pre_insert_payload = {
        "allowed_scopes": [
            {"scope_type": "legal_entity", "sequence": 1},
            {"scope_type": "service", "sequence": 2},
        ],
        "collection_guidance": "Use invented values only.",
        "description": "Invented enum input for schema tests.",
        "effective_from": None,
        "effective_until": None,
        "enum_values": [
            {"code": "alpha", "label": "Alpha", "sequence": 1},
            {"code": "beta", "label": "Beta", "sequence": 2},
        ],
        "fact_definition_id": str(enum_def_id).lower(),
        "fact_key": "synthetic_entity_state",
        "kind": "FactDefinitionVersion",
        "label": "Synthetic entity state",
        "predecessor_id": None,
        "predecessor_revision": None,
        "revision": 1,
        "sensitivity": "Confidential",
        "status": "Draft",
        "value_type": "enum",
        "version_label": "1.0.0",
    }
    assert compute_content_digest(enum_pre_insert_payload) == enum_digest

    enum_def = CatalogFactDefinition(
        id=enum_def_id,
        fact_key="synthetic_entity_state",
        status="Draft",
    )
    sqlite_session.add(enum_def)
    sqlite_session.flush()

    enum_v1_id = uuid4()
    enum_v1 = CatalogFactDefinitionVersion(
        id=enum_v1_id,
        fact_definition_id=enum_def_id,
        revision=1,
        version_label="1.0.0",
        predecessor_id=None,
        predecessor_revision=None,
        label="Synthetic entity state",
        description="Invented enum input for schema tests.",
        collection_guidance="Use invented values only.",
        value_type="enum",
        sensitivity="Confidential",
        effective_from=None,
        effective_until=None,
        status="Draft",
        content_digest=enum_digest,
        digest_schema="catalog-fact-definition-draft-v1",
    )
    sqlite_session.add(enum_v1)
    sqlite_session.flush()

    sqlite_session.add(
        CatalogFactDefinitionScope(
            id=uuid4(),
            fact_definition_version_id=enum_v1_id,
            sequence=1,
            scope_type="legal_entity",
        )
    )
    sqlite_session.add(
        CatalogFactDefinitionScope(
            id=uuid4(),
            fact_definition_version_id=enum_v1_id,
            sequence=2,
            scope_type="service",
        )
    )
    sqlite_session.add(
        CatalogFactDefinitionEnumValue(
            id=uuid4(),
            fact_definition_version_id=enum_v1_id,
            sequence=1,
            code="alpha",
            label="Alpha",
        )
    )
    sqlite_session.add(
        CatalogFactDefinitionEnumValue(
            id=uuid4(),
            fact_definition_version_id=enum_v1_id,
            sequence=2,
            code="beta",
            label="Beta",
        )
    )
    sqlite_session.flush()

    # Query persisted parent and ordered children from database
    loaded_enum_def = sqlite_session.get(CatalogFactDefinition, enum_def_id)
    assert loaded_enum_def is not None
    assert loaded_enum_def.fact_key == "synthetic_entity_state"

    loaded_enum_v1 = sqlite_session.get(CatalogFactDefinitionVersion, enum_v1_id)
    assert loaded_enum_v1 is not None
    assert loaded_enum_v1.revision == 1
    assert loaded_enum_v1.version_label == "1.0.0"
    assert loaded_enum_v1.content_digest == enum_digest
    assert loaded_enum_v1.effective_from is None
    assert loaded_enum_v1.effective_until is None

    loaded_enum_scopes = (
        sqlite_session.query(CatalogFactDefinitionScope)
        .filter_by(fact_definition_version_id=enum_v1_id)
        .order_by(CatalogFactDefinitionScope.sequence)
        .all()
    )
    assert len(loaded_enum_scopes) == 2
    assert [s.sequence for s in loaded_enum_scopes] == [1, 2]
    assert [s.scope_type for s in loaded_enum_scopes] == ["legal_entity", "service"]

    loaded_enum_vals = (
        sqlite_session.query(CatalogFactDefinitionEnumValue)
        .filter_by(fact_definition_version_id=enum_v1_id)
        .order_by(CatalogFactDefinitionEnumValue.sequence)
        .all()
    )
    assert len(loaded_enum_vals) == 2
    assert [ev.sequence for ev in loaded_enum_vals] == [1, 2]
    assert [ev.code for ev in loaded_enum_vals] == ["alpha", "beta"]

    # Reconstruct canonical payload strictly from selected persisted database values
    reconstructed_enum = {
        "allowed_scopes": [
            {"scope_type": s.scope_type, "sequence": s.sequence} for s in loaded_enum_scopes
        ],
        "collection_guidance": loaded_enum_v1.collection_guidance,
        "description": loaded_enum_v1.description,
        "effective_from": loaded_enum_v1.effective_from,
        "effective_until": loaded_enum_v1.effective_until,
        "enum_values": [
            {"code": ev.code, "label": ev.label, "sequence": ev.sequence} for ev in loaded_enum_vals
        ],
        "fact_definition_id": str(loaded_enum_def.id).lower(),
        "fact_key": loaded_enum_def.fact_key,
        "kind": "FactDefinitionVersion",
        "label": loaded_enum_v1.label,
        "predecessor_id": str(loaded_enum_v1.predecessor_id).lower()
        if loaded_enum_v1.predecessor_id
        else None,
        "predecessor_revision": loaded_enum_v1.predecessor_revision,
        "revision": loaded_enum_v1.revision,
        "sensitivity": loaded_enum_v1.sensitivity,
        "status": loaded_enum_v1.status,
        "value_type": loaded_enum_v1.value_type,
        "version_label": loaded_enum_v1.version_label,
    }
    recomputed_enum_digest = compute_content_digest(reconstructed_enum)
    assert recomputed_enum_digest == loaded_enum_v1.content_digest
    assert recomputed_enum_digest == enum_digest
    assert recomputed_enum_digest.hex() == enum_expected_hash

    # Meaningful-field mutation negative on reconstructed enum aggregate
    mutated_reconstructed_enum = dict(reconstructed_enum)
    mutated_reconstructed_enum["enum_values"] = [
        {"code": "alpha", "label": "Alpha", "sequence": 1},
        {"code": "gamma", "label": "Gamma", "sequence": 2},
    ]
    assert compute_content_digest(mutated_reconstructed_enum) != enum_digest

    # 3. Revision 2 on Boolean Definition (Distinct synthetic aggregate with its own computed digest)
    bool_v2_id = uuid4()
    bool_v2_payload = {
        "allowed_scopes": [{"scope_type": "tenant", "sequence": 1}],
        "collection_guidance": None,
        "description": "Second revision of invented Boolean input.",
        "effective_from": None,
        "effective_until": None,
        "enum_values": [],
        "fact_definition_id": str(bool_def_id).lower(),
        "fact_key": "synthetic_condition_met",
        "kind": "FactDefinitionVersion",
        "label": "Synthetic condition met v2",
        "predecessor_id": str(bool_v1_id).lower(),
        "predecessor_revision": 1,
        "revision": 2,
        "sensitivity": "Internal",
        "status": "Draft",
        "value_type": "boolean",
        "version_label": "1.1.0",
    }
    bool_v2_digest = compute_content_digest(bool_v2_payload)
    assert bool_v2_digest != bool_digest

    bool_v2 = CatalogFactDefinitionVersion(
        id=bool_v2_id,
        fact_definition_id=bool_def_id,
        revision=2,
        version_label="1.1.0",
        predecessor_id=bool_v1_id,
        predecessor_revision=1,
        label="Synthetic condition met v2",
        description="Second revision of invented Boolean input.",
        collection_guidance=None,
        value_type="boolean",
        sensitivity="Internal",
        effective_from=None,
        effective_until=None,
        status="Draft",
        content_digest=bool_v2_digest,
        digest_schema="catalog-fact-definition-draft-v1",
    )
    sqlite_session.add(bool_v2)
    sqlite_session.flush()

    bool_v2_scope = CatalogFactDefinitionScope(
        id=uuid4(),
        fact_definition_version_id=bool_v2_id,
        sequence=1,
        scope_type="tenant",
    )
    sqlite_session.add(bool_v2_scope)
    sqlite_session.flush()

    loaded_v2 = sqlite_session.get(CatalogFactDefinitionVersion, bool_v2_id)
    assert loaded_v2 is not None
    assert loaded_v2.revision == 2
    assert loaded_v2.predecessor_id == bool_v1_id
    assert loaded_v2.predecessor_revision == 1
    assert loaded_v2.content_digest == bool_v2_digest

    loaded_v2_scopes = (
        sqlite_session.query(CatalogFactDefinitionScope)
        .filter_by(fact_definition_version_id=bool_v2_id)
        .order_by(CatalogFactDefinitionScope.sequence)
        .all()
    )
    reconstructed_v2 = {
        "allowed_scopes": [
            {"scope_type": s.scope_type, "sequence": s.sequence} for s in loaded_v2_scopes
        ],
        "collection_guidance": loaded_v2.collection_guidance,
        "description": loaded_v2.description,
        "effective_from": loaded_v2.effective_from,
        "effective_until": loaded_v2.effective_until,
        "enum_values": [],
        "fact_definition_id": str(loaded_def.id).lower(),
        "fact_key": loaded_def.fact_key,
        "kind": "FactDefinitionVersion",
        "label": loaded_v2.label,
        "predecessor_id": str(loaded_v2.predecessor_id).lower()
        if loaded_v2.predecessor_id
        else None,
        "predecessor_revision": loaded_v2.predecessor_revision,
        "revision": loaded_v2.revision,
        "sensitivity": loaded_v2.sensitivity,
        "status": loaded_v2.status,
        "value_type": loaded_v2.value_type,
        "version_label": loaded_v2.version_label,
    }
    recomputed_v2_digest = compute_content_digest(reconstructed_v2)
    assert recomputed_v2_digest == loaded_v2.content_digest
    assert recomputed_v2_digest == bool_v2_digest


def test_fact_definition_with_effective_dates_distinct_digest(sqlite_session: Session) -> None:
    """Positive test for non-null effective dates with separately computed non-vector digest."""
    dated_def_id = uuid4()
    dated_def = CatalogFactDefinition(
        id=dated_def_id,
        fact_key="synthetic_dated_item",
        status="Draft",
    )
    sqlite_session.add(dated_def)
    sqlite_session.flush()

    dated_v_id = uuid4()
    dated_payload = {
        "allowed_scopes": [{"scope_type": "tenant", "sequence": 1}],
        "collection_guidance": None,
        "description": "Dated item with non-null effective window.",
        "effective_from": "2026-01-01",
        "effective_until": "2026-12-31",
        "enum_values": [],
        "fact_definition_id": str(dated_def_id).lower(),
        "fact_key": "synthetic_dated_item",
        "kind": "FactDefinitionVersion",
        "label": "Synthetic dated item",
        "predecessor_id": None,
        "predecessor_revision": None,
        "revision": 1,
        "sensitivity": "Internal",
        "status": "Draft",
        "value_type": "string",
        "version_label": "1.0.0",
    }
    dated_digest = compute_content_digest(dated_payload)

    dated_v = CatalogFactDefinitionVersion(
        id=dated_v_id,
        fact_definition_id=dated_def_id,
        revision=1,
        version_label="1.0.0",
        predecessor_id=None,
        predecessor_revision=None,
        label="Synthetic dated item",
        description="Dated item with non-null effective window.",
        collection_guidance=None,
        value_type="string",
        sensitivity="Internal",
        effective_from=date(2026, 1, 1),
        effective_until=date(2026, 12, 31),
        status="Draft",
        content_digest=dated_digest,
        digest_schema="catalog-fact-definition-draft-v1",
    )
    sqlite_session.add(dated_v)
    sqlite_session.flush()

    sqlite_session.add(
        CatalogFactDefinitionScope(
            id=uuid4(),
            fact_definition_version_id=dated_v_id,
            sequence=1,
            scope_type="tenant",
        )
    )
    sqlite_session.flush()

    loaded_v = sqlite_session.get(CatalogFactDefinitionVersion, dated_v_id)
    assert loaded_v is not None
    assert loaded_v.effective_from == date(2026, 1, 1)
    assert loaded_v.effective_until == date(2026, 12, 31)

    loaded_scopes = (
        sqlite_session.query(CatalogFactDefinitionScope)
        .filter_by(fact_definition_version_id=dated_v_id)
        .order_by(CatalogFactDefinitionScope.sequence)
        .all()
    )
    reconstructed_dated = {
        "allowed_scopes": [
            {"scope_type": s.scope_type, "sequence": s.sequence} for s in loaded_scopes
        ],
        "collection_guidance": loaded_v.collection_guidance,
        "description": loaded_v.description,
        "effective_from": loaded_v.effective_from.isoformat() if loaded_v.effective_from else None,
        "effective_until": loaded_v.effective_until.isoformat()
        if loaded_v.effective_until
        else None,
        "enum_values": [],
        "fact_definition_id": str(dated_def_id).lower(),
        "fact_key": "synthetic_dated_item",
        "kind": "FactDefinitionVersion",
        "label": loaded_v.label,
        "predecessor_id": None,
        "predecessor_revision": None,
        "revision": 1,
        "sensitivity": loaded_v.sensitivity,
        "status": loaded_v.status,
        "value_type": loaded_v.value_type,
        "version_label": loaded_v.version_label,
    }
    assert compute_content_digest(reconstructed_dated) == loaded_v.content_digest


# ---------------------------------------------------------------------------
# Negative Constraint Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_key",
    [
        "synthetic.condition_met",  # dot not allowed
        "Synthetic_condition",  # uppercase not allowed
        "1_synthetic",  # starts with digit
        "_synthetic",  # starts with underscore
        "ab",  # length 2 < 3
        "a" * 65,  # length 65 > 64
        "synthetic condition",  # space
        "synthetic-condition",  # hyphen
    ],
)
def test_negative_fact_key_format(sqlite_session: Session, invalid_key: str) -> None:
    fd = CatalogFactDefinition(
        id=uuid4(),
        fact_key=invalid_key,
        status="Draft",
    )
    sqlite_session.add(fd)
    with pytest.raises(IntegrityError):
        sqlite_session.flush()


def test_negative_fact_definition_status(sqlite_session: Session) -> None:
    fd = CatalogFactDefinition(
        id=uuid4(),
        fact_key="valid_key_one",
        status="Published",
    )
    sqlite_session.add(fd)
    with pytest.raises(IntegrityError):
        sqlite_session.flush()


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("version_label", " 1.0.0"),
        ("version_label", "1.0.0 "),
        ("version_label", ""),
        ("label", " Leading whitespace"),
        ("label", "Trailing whitespace "),
        ("label", ""),
        ("description", " Leading whitespace"),
        ("description", "Trailing whitespace "),
        ("description", ""),
        ("collection_guidance", " Untrimmed"),
        ("collection_guidance", "Untrimmed "),
        ("value_type", "invalid_type"),
        ("sensitivity", "TopSecret"),
        ("status", "Review"),
        ("digest_schema", "invalid-schema-v1"),
        ("content_digest", b"\x01" * 31),
        ("content_digest", b"\x01" * 33),
    ],
)
def test_negative_version_field_constraints(
    sqlite_session: Session, field: str, invalid_value: object
) -> None:
    fd_id = uuid4()
    sqlite_session.add(CatalogFactDefinition(id=fd_id, fact_key="valid_key_test", status="Draft"))
    sqlite_session.flush()

    kwargs: dict[str, object] = {
        "id": uuid4(),
        "fact_definition_id": fd_id,
        "revision": 1,
        "version_label": "1.0.0",
        "predecessor_id": None,
        "predecessor_revision": None,
        "label": "Valid Label",
        "description": "Valid Description.",
        "collection_guidance": None,
        "value_type": "boolean",
        "sensitivity": "Internal",
        "effective_from": None,
        "effective_until": None,
        "status": "Draft",
        "content_digest": b"\x00" * 32,
        "digest_schema": "catalog-fact-definition-draft-v1",
    }
    kwargs[field] = invalid_value
    sqlite_session.add(CatalogFactDefinitionVersion(**kwargs))  # type: ignore[arg-type]
    with pytest.raises(IntegrityError):
        sqlite_session.flush()


def test_negative_effective_dates_ordering(sqlite_session: Session) -> None:
    fd_id = uuid4()
    sqlite_session.add(CatalogFactDefinition(id=fd_id, fact_key="valid_key_dates", status="Draft"))
    sqlite_session.flush()

    v = CatalogFactDefinitionVersion(
        id=uuid4(),
        fact_definition_id=fd_id,
        revision=1,
        version_label="1.0.0",
        predecessor_id=None,
        predecessor_revision=None,
        label="Valid Label",
        description="Valid Description.",
        collection_guidance=None,
        value_type="boolean",
        sensitivity="Internal",
        effective_from=date(2026, 12, 31),
        effective_until=date(2026, 1, 1),  # until < from
        status="Draft",
        content_digest=b"\x00" * 32,
        digest_schema="catalog-fact-definition-draft-v1",
    )
    sqlite_session.add(v)
    with pytest.raises(IntegrityError):
        sqlite_session.flush()


def test_negative_predecessor_rules(sqlite_session: Session) -> None:
    fd_id = uuid4()
    sqlite_session.add(CatalogFactDefinition(id=fd_id, fact_key="valid_key_pred", status="Draft"))
    sqlite_session.flush()

    other_id = uuid4()

    # Case 1: Revision 1 with predecessor
    v1_bad = CatalogFactDefinitionVersion(
        id=uuid4(),
        fact_definition_id=fd_id,
        revision=1,
        version_label="1.0.0",
        predecessor_id=other_id,
        predecessor_revision=0,
        label="Label",
        description="Desc",
        value_type="boolean",
        sensitivity="Internal",
        content_digest=b"\x00" * 32,
    )
    sqlite_session.add(v1_bad)
    with pytest.raises(IntegrityError):
        sqlite_session.flush()
    sqlite_session.rollback()

    # Re-add definition after rollback
    sqlite_session.add(CatalogFactDefinition(id=fd_id, fact_key="valid_key_pred", status="Draft"))
    sqlite_session.flush()

    # Case 2: Revision 2 with no predecessor
    v2_bad = CatalogFactDefinitionVersion(
        id=uuid4(),
        fact_definition_id=fd_id,
        revision=2,
        version_label="1.1.0",
        predecessor_id=None,
        predecessor_revision=None,
        label="Label",
        description="Desc",
        value_type="boolean",
        sensitivity="Internal",
        content_digest=b"\x00" * 32,
    )
    sqlite_session.add(v2_bad)
    with pytest.raises(IntegrityError):
        sqlite_session.flush()
    sqlite_session.rollback()

    sqlite_session.add(CatalogFactDefinition(id=fd_id, fact_key="valid_key_pred", status="Draft"))
    sqlite_session.flush()

    # Case 3: Revision 2 with self-predecessor
    self_id = uuid4()
    v_self = CatalogFactDefinitionVersion(
        id=self_id,
        fact_definition_id=fd_id,
        revision=2,
        version_label="1.1.0",
        predecessor_id=self_id,
        predecessor_revision=1,
        label="Label",
        description="Desc",
        value_type="boolean",
        sensitivity="Internal",
        content_digest=b"\x00" * 32,
    )
    sqlite_session.add(v_self)
    with pytest.raises(IntegrityError):
        sqlite_session.flush()
    sqlite_session.rollback()


def test_negative_scope_constraints(sqlite_session: Session) -> None:
    fd_id = uuid4()
    v_id = uuid4()
    sqlite_session.add(CatalogFactDefinition(id=fd_id, fact_key="valid_scope_def", status="Draft"))
    sqlite_session.flush()
    sqlite_session.add(
        CatalogFactDefinitionVersion(
            id=v_id,
            fact_definition_id=fd_id,
            revision=1,
            version_label="1.0.0",
            label="Label",
            description="Desc",
            value_type="boolean",
            sensitivity="Internal",
            content_digest=b"\x00" * 32,
        )
    )
    sqlite_session.flush()

    # Invalid sequence: 0
    s_bad_seq = CatalogFactDefinitionScope(
        id=uuid4(), fact_definition_version_id=v_id, sequence=0, scope_type="tenant"
    )
    sqlite_session.add(s_bad_seq)
    with pytest.raises(IntegrityError):
        sqlite_session.flush()
    sqlite_session.rollback()

    # Invalid scope_type
    s_bad_type = CatalogFactDefinitionScope(
        id=uuid4(), fact_definition_version_id=v_id, sequence=1, scope_type="global_all"
    )
    sqlite_session.add(s_bad_type)
    with pytest.raises(IntegrityError):
        sqlite_session.flush()
    sqlite_session.rollback()


def test_negative_enum_value_constraints(sqlite_session: Session) -> None:
    fd_id = uuid4()
    v_id = uuid4()
    sqlite_session.add(CatalogFactDefinition(id=fd_id, fact_key="valid_enum_def", status="Draft"))
    sqlite_session.flush()
    sqlite_session.add(
        CatalogFactDefinitionVersion(
            id=v_id,
            fact_definition_id=fd_id,
            revision=1,
            version_label="1.0.0",
            label="Label",
            description="Desc",
            value_type="enum",
            sensitivity="Internal",
            content_digest=b"\x00" * 32,
        )
    )
    sqlite_session.flush()

    # Invalid code format (uppercase)
    ev_bad_code = CatalogFactDefinitionEnumValue(
        id=uuid4(), fact_definition_version_id=v_id, sequence=1, code="Alpha", label="Alpha"
    )
    sqlite_session.add(ev_bad_code)
    with pytest.raises(IntegrityError):
        sqlite_session.flush()
    sqlite_session.rollback()

    # Untrimmed label
    ev_bad_label = CatalogFactDefinitionEnumValue(
        id=uuid4(), fact_definition_version_id=v_id, sequence=1, code="alpha", label=" Alpha "
    )
    sqlite_session.add(ev_bad_label)
    with pytest.raises(IntegrityError):
        sqlite_session.flush()
    sqlite_session.rollback()
