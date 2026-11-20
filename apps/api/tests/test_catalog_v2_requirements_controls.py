"""Synthetic requirement, source reference, and Common Control constraint tests."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conformly.catalog_v2.models import (
    CatalogCommonControl,
    CatalogControlVersion,
    CatalogPublisher,
    CatalogRequirement,
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


def make_source_hierarchy(session, key="source-1"):
    publisher = CatalogPublisher(publisher_key=str(uuid4()), name="Synthetic publisher")
    session.add(publisher)
    session.flush()
    source = CatalogSource(publisher_id=publisher.id, source_key=key, title="Synthetic source")
    session.add(source)
    session.flush()
    source_version = CatalogSourceVersion(source_id=source.id, edition="edition-1")
    session.add(source_version)
    session.flush()
    return source, source_version


def make_requirement_hierarchy(session, key="REQ-TEST-001"):
    source, source_version = make_source_hierarchy(session, key=f"source-{uuid4().hex[:8]}")
    req = CatalogRequirement(source_id=source.id, requirement_key=key)
    session.add(req)
    session.flush()
    req_version = CatalogRequirementVersion(
        requirement_id=req.id,
        source_id=source.id,
        source_version_id=source_version.id,
        version_label="1.0.0",
        normalized_outcome="Synthetic normalized requirement outcome.",
        requirement_type="mandatory",
        obligated_actor="controller",
        text_origin="conformly_paraphrase",
        customer_display_text="Display text for customer review.",
        effective_from=date(2026, 1, 1),
        effective_until=date(2027, 1, 1),
    )
    session.add(req_version)
    session.flush()
    ref = CatalogRequirementSourceReference(
        requirement_version_id=req_version.id,
        source_version_id=source_version.id,
        locator_kind="article",
        locator_value="Article 5(1)(c)",
        sequence=1,
    )
    session.add(ref)
    session.flush()
    return source, source_version, req, req_version, ref


def make_common_control(session, key="CC-GOV-001"):
    control = CatalogCommonControl(control_key=key, domain="Governance")
    session.add(control)
    session.flush()
    control_version = CatalogControlVersion(
        control_id=control.id,
        version_label="1.0.0",
        title="Accountability and Oversight",
        objective="Ensure executive leadership is assigned for information security governance.",
        guidance="Designate responsible individuals and maintain review records.",
        control_type="governance",
        frequency="Annual and event-driven",
        automation_level="manual",
        suggested_owner_role="Executive Management",
        assurance_level="foundational",
        tags_state="Provided",
        tags="governance,accountability",
    )
    session.add(control_version)
    session.flush()
    return control, control_version


# --- Requirement Tests ---


def test_requirement_and_version_creation(catalog_session):
    _, _, req, req_version, ref = make_requirement_hierarchy(catalog_session)
    assert req.status == "Draft"
    assert req_version.status == "Draft"
    assert req_version.revision == 1
    assert ref.locator_kind == "article"
    assert ref.sequence == 1


def test_requirement_source_lineage_mismatch_rejected(catalog_session):
    source1, sv1 = make_source_hierarchy(catalog_session, key="source-1")
    source2, sv2 = make_source_hierarchy(catalog_session, key="source-2")

    req1 = CatalogRequirement(source_id=source1.id, requirement_key="REQ-MISMATCH")
    catalog_session.add(req1)
    catalog_session.flush()

    # Attempt to attach req1 (source1) to sv2 (source2) using source1 as composite key
    # sv2 does not belong to source1 -> composite FK to source_versions fails
    rv_bad = CatalogRequirementVersion(
        requirement_id=req1.id,
        source_id=source1.id,
        source_version_id=sv2.id,
        version_label="1.0.0",
        normalized_outcome="Lineage mismatch outcome.",
        requirement_type="mandatory",
        obligated_actor="controller",
        text_origin="conformly_paraphrase",
    )
    catalog_session.add(rv_bad)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()


def test_requirement_predecessor_lineage_enforcement(catalog_session):
    source, sv = make_source_hierarchy(catalog_session)
    req1 = CatalogRequirement(source_id=source.id, requirement_key="REQ-1")
    req2 = CatalogRequirement(source_id=source.id, requirement_key="REQ-2")
    catalog_session.add_all([req1, req2])
    catalog_session.flush()

    rv1 = CatalogRequirementVersion(
        requirement_id=req1.id,
        source_id=source.id,
        source_version_id=sv.id,
        version_label="1.0.0",
        normalized_outcome="Original requirement version.",
        requirement_type="mandatory",
        obligated_actor="controller",
        text_origin="conformly_paraphrase",
    )
    catalog_session.add(rv1)
    catalog_session.flush()

    # Cross-requirement predecessor: rv2 under req2 cannot claim rv1 (req1) as predecessor
    rv2_cross = CatalogRequirementVersion(
        requirement_id=req2.id,
        source_id=source.id,
        source_version_id=sv.id,
        version_label="1.0.0",
        predecessor_id=rv1.id,
        normalized_outcome="Cross-predecessor attempt.",
        requirement_type="mandatory",
        obligated_actor="controller",
        text_origin="conformly_paraphrase",
    )
    catalog_session.add(rv2_cross)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()


def test_requirement_self_predecessor_rejected(catalog_session):
    source, sv = make_source_hierarchy(catalog_session)
    req = CatalogRequirement(source_id=source.id, requirement_key="REQ-SELF")
    catalog_session.add(req)
    catalog_session.flush()

    rv_id = uuid4()
    rv_self = CatalogRequirementVersion(
        id=rv_id,
        requirement_id=req.id,
        source_id=source.id,
        source_version_id=sv.id,
        version_label="1.0.0",
        predecessor_id=rv_id,
        normalized_outcome="Self predecessor outcome.",
        requirement_type="mandatory",
        obligated_actor="controller",
        text_origin="conformly_paraphrase",
    )
    catalog_session.add(rv_self)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()


def test_requirement_type_and_text_origin_checks(catalog_session):
    source, sv = make_source_hierarchy(catalog_session)
    req = CatalogRequirement(source_id=source.id, requirement_key="REQ-CHECKS")
    catalog_session.add(req)
    catalog_session.flush()

    # Invalid requirement_type
    rv_invalid_type = CatalogRequirementVersion(
        requirement_id=req.id,
        source_id=source.id,
        source_version_id=sv.id,
        version_label="1.0.0",
        normalized_outcome="Outcome text.",
        requirement_type="unsupported_type",
        obligated_actor="controller",
        text_origin="conformly_paraphrase",
    )
    catalog_session.add(rv_invalid_type)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()

    # Invalid text_origin
    rv_invalid_origin = CatalogRequirementVersion(
        requirement_id=req.id,
        source_id=source.id,
        source_version_id=sv.id,
        version_label="1.0.0",
        normalized_outcome="Outcome text.",
        requirement_type="mandatory",
        obligated_actor="controller",
        text_origin="invented_origin",
    )
    catalog_session.add(rv_invalid_origin)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()


def test_source_reference_lineage_and_multiplicity(catalog_session):
    source, sv, req1, rv1, ref1 = make_requirement_hierarchy(catalog_session, key="REQ-MULTI-1")

    # Second requirement under the SAME source version
    req2 = CatalogRequirement(source_id=source.id, requirement_key="REQ-MULTI-2")
    catalog_session.add(req2)
    catalog_session.flush()
    rv2 = CatalogRequirementVersion(
        requirement_id=req2.id,
        source_id=source.id,
        source_version_id=sv.id,
        version_label="1.0.0",
        normalized_outcome="Second outcome from same locator.",
        requirement_type="mandatory",
        obligated_actor="controller",
        text_origin="conformly_paraphrase",
    )
    catalog_session.add(rv2)
    catalog_session.flush()

    # Many-to-one: The same locator kind & value supports BOTH requirement versions!
    ref2 = CatalogRequirementSourceReference(
        requirement_version_id=rv2.id,
        source_version_id=sv.id,
        locator_kind=ref1.locator_kind,
        locator_value=ref1.locator_value,
        sequence=1,
    )
    catalog_session.add(ref2)
    catalog_session.flush()
    assert ref1.locator_value == ref2.locator_value

    # Duplicate locator within the SAME requirement version is rejected
    ref_dup = CatalogRequirementSourceReference(
        requirement_version_id=rv1.id,
        source_version_id=sv.id,
        locator_kind=ref1.locator_kind,
        locator_value=ref1.locator_value,
        sequence=2,
    )
    catalog_session.add(ref_dup)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()


# --- Common Control Tests ---


def test_common_control_and_version_creation(catalog_session):
    ctrl, cv = make_common_control(catalog_session, key="CC-RSK-001")
    assert ctrl.status == "Draft"
    assert cv.status == "Draft"
    assert cv.revision == 1
    assert cv.assurance_level == "foundational"
    assert cv.tags_state == "Provided"


def test_control_predecessor_lineage_enforcement(catalog_session):
    ctrl1, cv1 = make_common_control(catalog_session, key="CC-IAM-001")
    ctrl2 = CatalogCommonControl(control_key="CC-IAM-002", domain="Identity and Access Management")
    catalog_session.add(ctrl2)
    catalog_session.flush()

    # Predecessor from a different control is rejected by composite FK
    cv_cross = CatalogControlVersion(
        control_id=ctrl2.id,
        version_label="1.0.0",
        predecessor_id=cv1.id,
        title="Access Review",
        objective="Review access periodically.",
        control_type="detective",
        frequency="Quarterly",
        automation_level="partially_automated",
        suggested_owner_role="Security Lead",
        assurance_level="foundational",
    )
    catalog_session.add(cv_cross)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()


def test_control_tags_distinguish_unknown_from_empty(catalog_session):
    ctrl = CatalogCommonControl(control_key="CC-POL-001", domain="Policies")
    catalog_session.add(ctrl)
    catalog_session.flush()

    # tags_state = Unknown with tags = None -> passes
    cv_unknown = CatalogControlVersion(
        control_id=ctrl.id,
        version_label="1.0.0",
        title="Policy Management",
        objective="Manage policy lifecycle.",
        control_type="governance",
        frequency="Annual",
        automation_level="manual",
        suggested_owner_role="Compliance Lead",
        assurance_level="foundational",
        tags_state="Unknown",
        tags=None,
    )
    catalog_session.add(cv_unknown)
    catalog_session.flush()

    # tags_state = None with tags = None (reviewed empty) -> passes
    cv_none = CatalogControlVersion(
        control_id=ctrl.id,
        version_label="1.1.0",
        title="Policy Management",
        objective="Manage policy lifecycle.",
        control_type="governance",
        frequency="Annual",
        automation_level="manual",
        suggested_owner_role="Compliance Lead",
        assurance_level="foundational",
        tags_state="None",
        tags=None,
    )
    catalog_session.add(cv_none)
    catalog_session.flush()

    # Inconsistent shape: tags_state = Unknown but tags provided -> fails check
    cv_inconsistent = CatalogControlVersion(
        control_id=ctrl.id,
        version_label="1.2.0",
        title="Policy Management",
        objective="Manage policy lifecycle.",
        control_type="governance",
        frequency="Annual",
        automation_level="manual",
        suggested_owner_role="Compliance Lead",
        assurance_level="foundational",
        tags_state="Unknown",
        tags="should_not_be_here",
    )
    catalog_session.add(cv_inconsistent)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()


def test_owner_role_is_abstract(catalog_session):
    ctrl, cv = make_common_control(catalog_session, key="CC-BCR-001")
    # suggested_owner_role is an abstract role string, not a user foreign key
    assert cv.suggested_owner_role == "Executive Management"
    assert not hasattr(cv, "owner_user_id")


def test_common_control_key_format_enforcement(catalog_session):
    # Valid control key formats (CC-<2-4 uppercase letters>-<3 digits>)
    valid_keys = ["CC-GOV-001", "CC-IAM-003", "CC-BCR-999", "CC-RS-100", "CC-ABCD-001"]
    for k in valid_keys:
        ctrl = CatalogCommonControl(control_key=k, domain="Test Domain")
        catalog_session.add(ctrl)
        catalog_session.flush()

    # Invalid control key formats
    invalid_keys = [
        "INVALID-KEY",
        "cc-gov-001",  # lowercase
        "CC-G-001",  # domain too short (1 letter)
        "CC-TOOLONG-001",  # domain too long (>4 letters)
        "CC-GOV-12",  # number too short (2 digits)
        "CC-GOV-1234",  # number too long (4 digits)
        "CC-123-001",  # domain with digits
        "CC-GOV-ABC",  # number with letters
    ]
    for bad_key in invalid_keys:
        bad_ctrl = CatalogCommonControl(control_key=bad_key, domain="Test Domain")
        catalog_session.add(bad_ctrl)
        with pytest.raises(IntegrityError):
            catalog_session.flush()
        catalog_session.rollback()


def test_control_self_predecessor_rejected(catalog_session):
    ctrl = CatalogCommonControl(control_key="CC-SELF-001", domain="Self Test")
    catalog_session.add(ctrl)
    catalog_session.flush()

    cv_id = uuid4()
    cv_self = CatalogControlVersion(
        id=cv_id,
        control_id=ctrl.id,
        version_label="1.0.0",
        predecessor_id=cv_id,
        title="Self Predecessor",
        objective="Objective.",
        control_type="governance",
        frequency="Annual",
        automation_level="manual",
        suggested_owner_role="Compliance Lead",
        assurance_level="foundational",
    )
    catalog_session.add(cv_self)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()
