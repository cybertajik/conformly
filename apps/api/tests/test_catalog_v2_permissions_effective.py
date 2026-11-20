"""Unit tests for effective source-use permission evaluation, decisions, and guard serialization."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogCapability,
    CatalogPermissionDeniedError,
    CatalogSecurityError,
)
from conformly.catalog_v2.digest import compute_source_version_digest
from conformly.catalog_v2.models import (
    CatalogPublisher,
    CatalogSource,
    CatalogSourcePermissionGuard,
    CatalogSourcePermissionProposal,
    CatalogSourceProvenance,
    CatalogSourceVersion,
)
from conformly.catalog_v2.permissions import (
    DEFAULT_SCOPE_KEY,
    create_source_permission_decision,
    evaluate_effective_permission,
)
from conformly.db.base import Base


@pytest.fixture
def db_session():
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
    with Session(engine) as session:
        yield session
    engine.dispose()


def make_test_fixture(session: Session):
    pub = CatalogPublisher(publisher_key="pub-test", name="Test Publisher")
    session.add(pub)
    session.flush()

    src = CatalogSource(
        publisher_id=pub.id,
        source_key="src-test",
        title="Test Source",
    )
    session.add(src)
    session.flush()

    guard = CatalogSourcePermissionGuard(source_id=src.id, revision=1, updated_at=datetime.now(UTC))
    session.add(guard)
    session.flush()

    sv_digest = compute_source_version_digest(src.id, "2026", None, "en", None, None, None)
    sv = CatalogSourceVersion(
        source_id=src.id,
        edition="2026",
        content_digest=sv_digest,
    )
    session.add(sv)
    session.flush()

    prov = CatalogSourceProvenance(
        source_version_id=sv.id,
        source_revision=1,
        content_sha256=b"x" * 32,
        content_size=100,
        mime_type="text/plain",
        locator="https://example.com/spec",
        retrieved_at=datetime.now(UTC),
        recorded_by_actor_id=uuid4(),
    )
    session.add(prov)
    session.flush()

    recorder_id = uuid4()
    prop = CatalogSourcePermissionProposal(
        provenance_id=prov.id,
        source_version_id=sv.id,
        use_case="reference",
        scope_key=DEFAULT_SCOPE_KEY,
        sequence=1,
        proposed_outcome="Allowed",
        conditions_state="None",
        recorded_by_actor_id=recorder_id,
    )
    session.add(prop)
    session.flush()

    return {
        "publisher": pub,
        "source": src,
        "guard": guard,
        "source_version": sv,
        "provenance": prov,
        "proposal": prop,
        "recorder_id": recorder_id,
    }


def test_permission_absence_fails_closed(db_session: Session):
    """When no decision exists for exact version/use/scope, access is strictly denied."""
    f = make_test_fixture(db_session)
    now = datetime.now(UTC)

    with pytest.raises(CatalogPermissionDeniedError, match="No permission decision found"):
        evaluate_effective_permission(
            db_session, f["source_version"].id, "reference", DEFAULT_SCOPE_KEY, now
        )


def test_decision_creation_and_evaluation(db_session: Session):
    """A valid Allowed decision allows use, increments guard revision, and sets gap-free sequence."""
    f = make_test_fixture(db_session)
    now = datetime.now(UTC)
    decider_id = uuid4()

    actor_ctx = CatalogActorContext(
        actor_id=decider_id,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=now,
        capabilities=frozenset({CatalogCapability.PERMISSION_DECIDE}),
    )

    dec = create_source_permission_decision(
        session=db_session,
        context=actor_ctx,
        source_id=f["source"].id,
        source_version_id=f["source_version"].id,
        proposal_id=f["proposal"].id,
        use_case="reference",
        scope_key=DEFAULT_SCOPE_KEY,
        decision_type="Allowed",
        valid_from=now - timedelta(minutes=5),
        valid_until=now + timedelta(days=30),
        evidence_reference="LEGAL-REVIEW-101",
        db_time=now,
    )

    assert dec.sequence == 1
    assert dec.predecessor_id is None
    assert dec.guard_revision == 2
    assert f["guard"].revision == 2

    eff = evaluate_effective_permission(
        db_session, f["source_version"].id, "reference", DEFAULT_SCOPE_KEY, now
    )
    assert eff.id == dec.id
    assert eff.decision == "Allowed"


def test_two_person_rule_rejects_same_author(db_session: Session):
    """The actor recording the proposal cannot decide the permission proposal."""
    f = make_test_fixture(db_session)
    now = datetime.now(UTC)

    actor_ctx = CatalogActorContext(
        actor_id=f["recorder_id"],
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=now,
        capabilities=frozenset({CatalogCapability.PERMISSION_DECIDE}),
    )

    with pytest.raises(CatalogSecurityError, match="two-person rule"):
        create_source_permission_decision(
            session=db_session,
            context=actor_ctx,
            source_id=f["source"].id,
            source_version_id=f["source_version"].id,
            proposal_id=f["proposal"].id,
            use_case="reference",
            scope_key=DEFAULT_SCOPE_KEY,
            decision_type="Allowed",
            valid_from=now,
            valid_until=None,
            evidence_reference="SELF-REVIEW",
            db_time=now,
        )


def test_denied_decision_fails_closed(db_session: Session):
    """A Denied decision is explicitly rejected by the evaluator."""
    f = make_test_fixture(db_session)
    now = datetime.now(UTC)
    decider_id = uuid4()

    actor_ctx = CatalogActorContext(
        actor_id=decider_id,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=now,
        capabilities=frozenset({CatalogCapability.PERMISSION_DECIDE}),
    )

    create_source_permission_decision(
        session=db_session,
        context=actor_ctx,
        source_id=f["source"].id,
        source_version_id=f["source_version"].id,
        proposal_id=f["proposal"].id,
        use_case="reference",
        scope_key=DEFAULT_SCOPE_KEY,
        decision_type="Denied",
        valid_from=now - timedelta(minutes=5),
        valid_until=None,
        evidence_reference="DENIAL-RECORD",
        db_time=now,
    )

    with pytest.raises(CatalogPermissionDeniedError, match="Permission decision .* is Denied"):
        evaluate_effective_permission(
            db_session, f["source_version"].id, "reference", DEFAULT_SCOPE_KEY, now
        )


def test_future_and_expired_validity_boundaries(db_session: Session):
    """Decisions that are in the future or expired fail closed."""
    f = make_test_fixture(db_session)
    now = datetime.now(UTC)
    decider_id = uuid4()

    actor_ctx = CatalogActorContext(
        actor_id=decider_id,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=now,
        capabilities=frozenset({CatalogCapability.PERMISSION_DECIDE}),
    )

    dec_future = create_source_permission_decision(
        session=db_session,
        context=actor_ctx,
        source_id=f["source"].id,
        source_version_id=f["source_version"].id,
        proposal_id=f["proposal"].id,
        use_case="reference",
        scope_key=DEFAULT_SCOPE_KEY,
        decision_type="Allowed",
        valid_from=now + timedelta(hours=1),
        valid_until=now + timedelta(days=1),
        evidence_reference="FUTURE-EVIDENCE",
        db_time=now,
    )

    with pytest.raises(CatalogPermissionDeniedError, match="not yet valid"):
        evaluate_effective_permission(
            db_session, f["source_version"].id, "reference", DEFAULT_SCOPE_KEY, now
        )

    dec_future.valid_from = now - timedelta(hours=2)
    dec_future.valid_until = now - timedelta(hours=1)
    db_session.flush()

    with pytest.raises(CatalogPermissionDeniedError, match="has expired"):
        evaluate_effective_permission(
            db_session, f["source_version"].id, "reference", DEFAULT_SCOPE_KEY, now
        )


def test_sequence_allocation_and_revocation(db_session: Session):
    """Subsequent decisions in the same scope increment sequence, set predecessor, and override earlier decisions."""
    f = make_test_fixture(db_session)
    now = datetime.now(UTC)
    decider_id = uuid4()

    actor_ctx = CatalogActorContext(
        actor_id=decider_id,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=now,
        capabilities=frozenset({CatalogCapability.PERMISSION_DECIDE}),
    )

    dec1 = create_source_permission_decision(
        session=db_session,
        context=actor_ctx,
        source_id=f["source"].id,
        source_version_id=f["source_version"].id,
        proposal_id=f["proposal"].id,
        use_case="reference",
        scope_key=DEFAULT_SCOPE_KEY,
        decision_type="Allowed",
        valid_from=now - timedelta(minutes=10),
        valid_until=None,
        evidence_reference="INITIAL-APPROVAL",
        db_time=now,
    )
    assert dec1.sequence == 1
    assert dec1.predecessor_id is None

    eff1 = evaluate_effective_permission(
        db_session, f["source_version"].id, "reference", DEFAULT_SCOPE_KEY, now
    )
    assert eff1.decision == "Allowed"

    dec2 = create_source_permission_decision(
        session=db_session,
        context=actor_ctx,
        source_id=f["source"].id,
        source_version_id=f["source_version"].id,
        proposal_id=f["proposal"].id,
        use_case="reference",
        scope_key=DEFAULT_SCOPE_KEY,
        decision_type="Denied",
        valid_from=now - timedelta(minutes=1),
        valid_until=None,
        evidence_reference="REVOCATION-NOTICE",
        db_time=now,
    )
    assert dec2.sequence == 2
    assert dec2.predecessor_id == dec1.id

    with pytest.raises(CatalogPermissionDeniedError, match="is Denied"):
        evaluate_effective_permission(
            db_session, f["source_version"].id, "reference", DEFAULT_SCOPE_KEY, now
        )
