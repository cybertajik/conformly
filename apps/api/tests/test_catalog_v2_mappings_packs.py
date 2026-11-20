"""Synthetic Framework Pack and Requirement-Control Mapping constraint tests."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conformly.catalog_v2.models import (
    CatalogCommonControl,
    CatalogControlVersion,
    CatalogMappingVersion,
    CatalogPack,
    CatalogPackMembership,
    CatalogPackVersion,
    CatalogPublisher,
    CatalogRequirement,
    CatalogRequirementControlMapping,
    CatalogRequirementSourceReference,
    CatalogRequirementVersion,
    CatalogSource,
    CatalogSourceVersion,
)
from conformly.db.base import Base


@pytest.fixture
def catalog_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(
        engine,
        tables=[
            table for name, table in Base.metadata.tables.items() if name.startswith("catalog_")
        ],
    )
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def make_requirement_hierarchy(session, key="REQ-TEST-001"):
    publisher = CatalogPublisher(publisher_key=str(uuid4()), name="Synthetic publisher")
    session.add(publisher)
    session.flush()
    source = CatalogSource(
        publisher_id=publisher.id, source_key=f"src-{uuid4().hex[:8]}", title="Synthetic source"
    )
    session.add(source)
    session.flush()
    source_version = CatalogSourceVersion(source_id=source.id, edition="edition-1")
    session.add(source_version)
    session.flush()
    req = CatalogRequirement(source_id=source.id, requirement_key=key)
    session.add(req)
    session.flush()
    req_version = CatalogRequirementVersion(
        requirement_id=req.id,
        source_id=source.id,
        source_version_id=source_version.id,
        version_label="1.0.0",
        normalized_outcome="Synthetic requirement outcome.",
        requirement_type="mandatory",
        obligated_actor="controller",
        text_origin="conformly_paraphrase",
    )
    session.add(req_version)
    session.flush()
    ref = CatalogRequirementSourceReference(
        requirement_version_id=req_version.id,
        source_version_id=source_version.id,
        locator_kind="article",
        locator_value="Article 5",
        sequence=1,
    )
    session.add(ref)
    session.flush()
    return req, req_version


def make_common_control(session, key="CC-GOV-001"):
    control = CatalogCommonControl(control_key=key, domain="Governance")
    session.add(control)
    session.flush()
    control_version = CatalogControlVersion(
        control_id=control.id,
        version_label="1.0.0",
        title="Oversight Control",
        objective="Ensure oversight.",
        control_type="governance",
        frequency="Annual",
        automation_level="manual",
        suggested_owner_role="Executive Management",
        assurance_level="foundational",
    )
    session.add(control_version)
    session.flush()
    return control, control_version


def make_pack_hierarchy(session, pack_key="PACK-EU-GDPR"):
    pack = CatalogPack(
        pack_key=pack_key,
        name="EU GDPR Framework Pack",
        pack_type="regulatory",
        jurisdiction="EU",
    )
    session.add(pack)
    session.flush()
    pack_version = CatalogPackVersion(
        pack_id=pack.id,
        version_label="2026.1",
        title="GDPR 2026 Baseline Pack",
        description="Comprehensive pack for GDPR compliance.",
        audience="EU Cloud Providers",
        effective_from=date(2026, 1, 1),
        effective_until=date(2027, 1, 1),
    )
    session.add(pack_version)
    session.flush()
    return pack, pack_version


# ==============================================================================
# 1. Framework Pack & Version Tests
# ==============================================================================


def test_pack_and_version_creation(catalog_session):
    pack, pack_version = make_pack_hierarchy(catalog_session)
    assert pack.status == "Draft"
    assert pack.pack_type == "regulatory"
    assert pack_version.status == "Draft"
    assert pack_version.revision == 1
    assert pack_version.title == "GDPR 2026 Baseline Pack"


@pytest.mark.parametrize("invalid_key", ["pack-lower", "PK", "PACK@INVALID", "A" * 65])
def test_pack_key_format_rejected(catalog_session, invalid_key):
    pack = CatalogPack(
        pack_key=invalid_key,
        name="Invalid Pack",
        pack_type="baseline",
    )
    catalog_session.add(pack)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


def test_pack_key_uniqueness(catalog_session):
    make_pack_hierarchy(catalog_session, pack_key="PACK-UNIQ-001")
    dup = CatalogPack(
        pack_key="PACK-UNIQ-001",
        name="Duplicate Pack",
        pack_type="certification",
    )
    catalog_session.add(dup)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


def test_pack_type_enum_enforcement(catalog_session):
    pack = CatalogPack(
        pack_key="PACK-UNKNOWN-TYPE",
        name="Invalid Type Pack",
        pack_type="unsupported_type",
    )
    catalog_session.add(pack)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


def test_pack_effective_dates_order(catalog_session):
    pack = CatalogPack(
        pack_key="PACK-DATES-TEST",
        name="Dates Pack",
        pack_type="baseline",
    )
    catalog_session.add(pack)
    catalog_session.flush()
    pv = CatalogPackVersion(
        pack_id=pack.id,
        version_label="1.0.0",
        title="Invalid Dates Version",
        effective_from=date(2026, 6, 1),
        effective_until=date(2026, 1, 1),
    )
    catalog_session.add(pv)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


def test_pack_version_label_uniqueness(catalog_session):
    pack, pv = make_pack_hierarchy(catalog_session, pack_key="PACK-VER-UNIQ")
    dup_pv = CatalogPackVersion(
        pack_id=pack.id,
        version_label=pv.version_label,
        title="Duplicate Version Label",
    )
    catalog_session.add(dup_pv)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


def test_pack_version_predecessor_lineage(catalog_session):
    pack1, pv1 = make_pack_hierarchy(catalog_session, pack_key="PACK-LINEAGE-1")
    pack2, _ = make_pack_hierarchy(catalog_session, pack_key="PACK-LINEAGE-2")

    cross_pv = CatalogPackVersion(
        pack_id=pack2.id,
        version_label="2.0.0",
        predecessor_id=pv1.id,
        title="Cross Pack Predecessor",
    )
    catalog_session.add(cross_pv)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


def test_pack_version_self_predecessor_rejected(catalog_session):
    pack, _ = make_pack_hierarchy(catalog_session, pack_key="PACK-SELF-PRED")
    self_id = uuid4()
    pv = CatalogPackVersion(
        id=self_id,
        pack_id=pack.id,
        version_label="1.0.0-self",
        predecessor_id=self_id,
        title="Self Predecessor",
    )
    catalog_session.add(pv)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


# ==============================================================================
# 2. Framework Pack Membership Tests
# ==============================================================================


def test_pack_membership_creation(catalog_session):
    _, pv = make_pack_hierarchy(catalog_session, pack_key="PACK-MEMB-001")
    _, req_v = make_requirement_hierarchy(catalog_session, key="REQ-MEMB-001")

    membership = CatalogPackMembership(
        pack_version_id=pv.id,
        requirement_version_id=req_v.id,
        sequence=1,
        inclusion_conditions_state="Provided",
        inclusion_conditions="Applies only to cloud data processors",
    )
    catalog_session.add(membership)
    catalog_session.flush()
    assert membership.sequence == 1
    assert membership.inclusion_conditions_state == "Provided"


def test_pack_membership_pair_uniqueness(catalog_session):
    _, pv = make_pack_hierarchy(catalog_session, pack_key="PACK-MEMB-PAIR")
    _, req_v = make_requirement_hierarchy(catalog_session, key="REQ-MEMB-PAIR")

    m1 = CatalogPackMembership(
        pack_version_id=pv.id,
        requirement_version_id=req_v.id,
        sequence=1,
        inclusion_conditions_state="None",
    )
    catalog_session.add(m1)
    catalog_session.flush()

    m2 = CatalogPackMembership(
        pack_version_id=pv.id,
        requirement_version_id=req_v.id,
        sequence=2,
        inclusion_conditions_state="None",
    )
    catalog_session.add(m2)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


def test_pack_membership_sequence_uniqueness(catalog_session):
    _, pv = make_pack_hierarchy(catalog_session, pack_key="PACK-MEMB-SEQ")
    _, req_v1 = make_requirement_hierarchy(catalog_session, key="REQ-SEQ-001")
    _, req_v2 = make_requirement_hierarchy(catalog_session, key="REQ-SEQ-002")

    m1 = CatalogPackMembership(
        pack_version_id=pv.id,
        requirement_version_id=req_v1.id,
        sequence=1,
        inclusion_conditions_state="None",
    )
    catalog_session.add(m1)
    catalog_session.flush()

    m2 = CatalogPackMembership(
        pack_version_id=pv.id,
        requirement_version_id=req_v2.id,
        sequence=1,
        inclusion_conditions_state="None",
    )
    catalog_session.add(m2)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


@pytest.mark.parametrize(
    ("state", "cond"),
    [
        ("Unknown", "Some condition string"),
        ("None", "Some condition string"),
        ("Provided", None),
    ],
)
def test_pack_membership_condition_shape_rejected(catalog_session, state, cond):
    _, pv = make_pack_hierarchy(catalog_session, pack_key=f"PACK-SHAPE-{uuid4().hex[:6].upper()}")
    _, req_v = make_requirement_hierarchy(
        catalog_session, key=f"REQ-SHAPE-{uuid4().hex[:6].upper()}"
    )

    membership = CatalogPackMembership(
        pack_version_id=pv.id,
        requirement_version_id=req_v.id,
        sequence=1,
        inclusion_conditions_state=state,
        inclusion_conditions=cond,
    )
    catalog_session.add(membership)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


# ==============================================================================
# 3. Requirement-Control Mapping & Version Tests
# ==============================================================================


def test_mapping_and_version_creation(catalog_session):
    req, req_v = make_requirement_hierarchy(catalog_session, key="REQ-MAP-001")
    ctrl, ctrl_v = make_common_control(catalog_session, key="CC-GOV-001")

    mapping = CatalogRequirementControlMapping(
        mapping_key="MAP-REQ-001--CC-GOV-001",
        requirement_id=req.id,
        control_id=ctrl.id,
    )
    catalog_session.add(mapping)
    catalog_session.flush()
    assert mapping.status == "Draft"

    mv = CatalogMappingVersion(
        mapping_id=mapping.id,
        requirement_id=req.id,
        control_id=ctrl.id,
        requirement_version_id=req_v.id,
        control_version_id=ctrl_v.id,
        version_label="1.0.0",
        mapping_type="Full",
        rationale="Control fully satisfies governance requirement.",
        source_basis="direct_text",
        confidence="high",
        review_state="Draft",
    )
    catalog_session.add(mv)
    catalog_session.flush()
    assert mv.status == "Draft"
    assert mv.revision == 1
    assert mv.mapping_type == "Full"


def test_mapping_pair_uniqueness(catalog_session):
    req, _ = make_requirement_hierarchy(catalog_session, key="REQ-MAP-PAIR")
    ctrl, _ = make_common_control(catalog_session, key="CC-SEC-001")

    m1 = CatalogRequirementControlMapping(
        mapping_key="MAP-PAIR-1",
        requirement_id=req.id,
        control_id=ctrl.id,
    )
    catalog_session.add(m1)
    catalog_session.flush()

    m2 = CatalogRequirementControlMapping(
        mapping_key="MAP-PAIR-2",
        requirement_id=req.id,
        control_id=ctrl.id,
    )
    catalog_session.add(m2)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


def test_mapping_version_lineage_pinning(catalog_session):
    req1, req_v1 = make_requirement_hierarchy(catalog_session, key="REQ-LIN-001")
    req2, _ = make_requirement_hierarchy(catalog_session, key="REQ-LIN-002")
    ctrl, ctrl_v = make_common_control(catalog_session, key="CC-OPS-001")

    mapping = CatalogRequirementControlMapping(
        mapping_key="MAP-LIN-001",
        requirement_id=req1.id,
        control_id=ctrl.id,
    )
    catalog_session.add(mapping)
    catalog_session.flush()

    # Mismatched requirement_id in mapping_version
    mv_bad_req = CatalogMappingVersion(
        mapping_id=mapping.id,
        requirement_id=req2.id,  # mismatch with parent mapping
        control_id=ctrl.id,
        requirement_version_id=req_v1.id,
        control_version_id=ctrl_v.id,
        version_label="1.0.0",
        mapping_type="Full",
        rationale="Lineage test.",
        source_basis="expert_analysis",
        confidence="medium",
    )
    catalog_session.add(mv_bad_req)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


def test_mapping_version_partial_requires_excluded_dims_rejected(catalog_session):
    req, req_v = make_requirement_hierarchy(catalog_session, key="REQ-PARTIAL-001")
    ctrl, ctrl_v = make_common_control(catalog_session, key="CC-DAT-001")

    mapping = CatalogRequirementControlMapping(
        mapping_key="MAP-PARTIAL-001",
        requirement_id=req.id,
        control_id=ctrl.id,
    )
    catalog_session.add(mapping)
    catalog_session.flush()

    # Partial without excluded_dimensions must fail
    mv_invalid = CatalogMappingVersion(
        mapping_id=mapping.id,
        requirement_id=req.id,
        control_id=ctrl.id,
        requirement_version_id=req_v.id,
        control_version_id=ctrl_v.id,
        version_label="1.0.0",
        mapping_type="Partial",
        rationale="Partial mapping without exclusions.",
        excluded_dimensions=None,
        source_basis="expert_analysis",
        confidence="low",
    )
    catalog_session.add(mv_invalid)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


def test_mapping_version_partial_with_excluded_dims_accepted(catalog_session):
    req, req_v = make_requirement_hierarchy(catalog_session, key="REQ-PARTIAL-002")
    ctrl, ctrl_v = make_common_control(catalog_session, key="CC-DAT-002")

    mapping = CatalogRequirementControlMapping(
        mapping_key="MAP-PARTIAL-002",
        requirement_id=req.id,
        control_id=ctrl.id,
    )
    catalog_session.add(mapping)
    catalog_session.flush()

    mv_valid = CatalogMappingVersion(
        mapping_id=mapping.id,
        requirement_id=req.id,
        control_id=ctrl.id,
        requirement_version_id=req_v.id,
        control_version_id=ctrl_v.id,
        version_label="1.0.0",
        mapping_type="Partial",
        rationale="Partial mapping with exclusions.",
        excluded_dimensions="Cross-border transfer restrictions are not addressed by this control.",
        source_basis="expert_analysis",
        confidence="medium",
    )
    catalog_session.add(mv_valid)
    catalog_session.flush()
    assert mv_valid.mapping_type == "Partial"
    assert mv_valid.excluded_dimensions is not None


def test_mapping_version_type_enum(catalog_session):
    req, req_v = make_requirement_hierarchy(catalog_session, key="REQ-TYPE-001")
    ctrl, ctrl_v = make_common_control(catalog_session, key="CC-NET-001")

    mapping = CatalogRequirementControlMapping(
        mapping_key="MAP-TYPE-001",
        requirement_id=req.id,
        control_id=ctrl.id,
    )
    catalog_session.add(mapping)
    catalog_session.flush()

    mv = CatalogMappingVersion(
        mapping_id=mapping.id,
        requirement_id=req.id,
        control_id=ctrl.id,
        requirement_version_id=req_v.id,
        control_version_id=ctrl_v.id,
        version_label="1.0.0",
        mapping_type="InvalidType",
        rationale="Invalid type mapping.",
        source_basis="direct_text",
        confidence="high",
    )
    catalog_session.add(mv)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
