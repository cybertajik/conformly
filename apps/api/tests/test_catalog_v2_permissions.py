"""Synthetic Draft proposals and provenance constraints, not license approvals."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conformly.catalog_v2.models import (
    CatalogSourcePermissionProposal,
    CatalogSourceProvenance,
    CatalogSourceVersion,
)
from conformly.db.base import Base
from tests.test_catalog_v2_models import make_source


@pytest.fixture
def permission_session():
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


def make_provenance(session):
    source = make_source(session)
    version = CatalogSourceVersion(source_id=source.id, edition="synthetic-1")
    session.add(version)
    session.flush()
    provenance = CatalogSourceProvenance(
        source_version_id=version.id,
        source_revision=version.revision,
        content_sha256=sha256(b"independently authored fixture").digest(),
        content_size=len(b"independently authored fixture"),
        mime_type="text/plain",
        locator="https://example.invalid/synthetic",
        retrieved_at=datetime(2026, 9, 28, tzinfo=UTC),
        recorded_by_actor_id=uuid4(),
    )
    session.add(provenance)
    session.flush()
    return provenance


def proposal_for(provenance, **overrides):
    fields = dict(
        source_version_id=provenance.source_version_id,
        provenance_id=provenance.id,
        use_case="reference",
        scope_key="synthetic-internal",
        recorded_by_actor_id=uuid4(),
    )
    fields.update(overrides)
    return CatalogSourcePermissionProposal(**fields)


def test_defaults_never_claim_effective_permission(permission_session):
    provenance = make_provenance(permission_session)
    proposal = proposal_for(provenance)
    permission_session.add(proposal)
    permission_session.flush()
    assert proposal.sequence == 1
    assert proposal.proposed_outcome == "Unknown"
    assert proposal.review_state == "Draft"
    assert proposal.conditions_state == "Unknown"
    assert proposal.conditions_reference is None
    assert proposal.valid_from is proposal.valid_until is None
    assert proposal.evidence_reference is None
    assert not hasattr(proposal, "approved_at")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("content_sha256", b""),
        ("content_sha256", b"x" * 31),
        ("content_sha256", b"x" * 33),
        ("content_size", -1),
        ("source_revision", 0),
        ("mime_type", ""),
        ("mime_type", "x" * 256),
        ("locator", ""),
        ("locator", "x" * 4097),
        ("recorded_by_actor_id", None),
        ("retrieved_at", None),
    ],
)
def test_provenance_constraints(permission_session, field, value):
    # SQLite has no append-only trigger; use it only to exercise column constraints.
    provenance = make_provenance(permission_session)
    setattr(provenance, field, value)
    with pytest.raises(IntegrityError):
        permission_session.flush()


def test_one_observation_per_source_version(permission_session):
    first = make_provenance(permission_session)
    permission_session.add(
        CatalogSourceProvenance(
            source_version_id=first.source_version_id,
            source_revision=1,
            content_sha256=sha256(b"different synthetic bytes").digest(),
            content_size=25,
            mime_type="text/plain",
            locator=first.locator,
            retrieved_at=first.retrieved_at,
            recorded_by_actor_id=uuid4(),
        )
    )
    with pytest.raises(IntegrityError):
        permission_session.flush()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("use_case", "unknown-operation"),
        ("scope_key", ""),
        ("scope_key", "x" * 129),
        ("proposed_outcome", "Approved"),
        ("review_state", "Approved"),
        ("conditions_state", "Unsupported"),
        ("conditions_state", "ExternalReference"),
        ("conditions_reference", uuid4()),
        ("sequence", 0),
        ("sequence", 2),
        ("supersedes_id", uuid4()),
        ("supersedes_sequence", 1),
        ("recorded_by_actor_id", None),
    ],
)
def test_proposal_constraints(permission_session, field, value):
    provenance = make_provenance(permission_session)
    proposal = proposal_for(provenance)
    setattr(proposal, field, value)
    permission_session.add(proposal)
    with pytest.raises(IntegrityError):
        permission_session.flush()


@pytest.mark.parametrize("offset", [0, -1])
def test_expiry_must_follow_start(permission_session, offset):
    provenance = make_provenance(permission_session)
    start = datetime(2026, 9, 28, tzinfo=UTC)
    permission_session.add(
        proposal_for(
            provenance,
            valid_from=start,
            valid_until=start + timedelta(seconds=offset),
        )
    )
    with pytest.raises(IntegrityError):
        permission_session.flush()


def test_known_empty_conditions_are_not_unknown(permission_session):
    provenance = make_provenance(permission_session)
    proposal = proposal_for(provenance, proposed_outcome="Allowed", conditions_state="None")
    permission_session.add(proposal)
    permission_session.flush()
    assert proposal.review_state == "Draft"  # Allowed is still a proposal, never a grant.
    assert proposal.conditions_state == "None"


def test_provenance_cannot_be_substituted_between_versions(permission_session):
    first = make_provenance(permission_session)
    second = make_provenance(permission_session)
    permission_session.add(proposal_for(first, source_version_id=second.source_version_id))
    with pytest.raises(IntegrityError):
        permission_session.flush()


def test_successor_keeps_history_and_context(permission_session):
    provenance = make_provenance(permission_session)
    first = proposal_for(provenance)
    permission_session.add(first)
    permission_session.flush()
    second = proposal_for(
        provenance,
        sequence=2,
        supersedes_id=first.id,
        supersedes_sequence=1,
        proposed_outcome="Denied",
        conditions_state="ExternalReference",
        conditions_reference=uuid4(),
    )
    permission_session.add(second)
    permission_session.flush()
    assert first.proposed_outcome == "Unknown"
    assert second.sequence == 2


@pytest.mark.parametrize("mismatch", ["scope", "use", "version", "sequence", "missing"])
def test_successor_cannot_cross_context_or_skip_history(permission_session, mismatch):
    provenance = make_provenance(permission_session)
    first = proposal_for(provenance)
    permission_session.add(first)
    permission_session.flush()
    changes = dict(sequence=2, supersedes_sequence=1, supersedes_id=first.id)
    if mismatch == "scope":
        changes["scope_key"] = "different"
    elif mismatch == "use":
        changes["use_case"] = "export"
    elif mismatch == "version":
        provenance = make_provenance(permission_session)
    elif mismatch == "sequence":
        changes.update(sequence=3, supersedes_sequence=2)
    else:
        changes["supersedes_id"] = uuid4()
    permission_session.add(proposal_for(provenance, **changes))
    with pytest.raises(IntegrityError):
        permission_session.flush()


def test_duplicate_scope_sequence_rejected(permission_session):
    provenance = make_provenance(permission_session)
    permission_session.add_all([proposal_for(provenance), proposal_for(provenance)])
    with pytest.raises(IntegrityError):
        permission_session.flush()


def test_use_and_scope_are_separate_namespaces(permission_session):
    provenance = make_provenance(permission_session)
    permission_session.add_all(
        [
            proposal_for(provenance),
            proposal_for(provenance, use_case="export"),
            proposal_for(provenance, scope_key="different"),
        ]
    )
    permission_session.flush()
