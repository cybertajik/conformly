"""Synthetic constraint checks; SQLite does not establish PostgreSQL isolation."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conformly.catalog_v2.models import CatalogPublisher, CatalogSource, CatalogSourceVersion
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
            Base.metadata.tables["catalog_publishers"],
            Base.metadata.tables["catalog_sources"],
            Base.metadata.tables["catalog_source_versions"],
        ],
    )
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def make_source(session, key="synthetic", publisher=None):
    if publisher is None:
        publisher = CatalogPublisher(publisher_key=str(uuid4()), name="Synthetic publisher")
        session.add(publisher)
        session.flush()
    source = CatalogSource(publisher_id=publisher.id, source_key=key, title="Synthetic source")
    session.add(source)
    session.flush()
    return source


def test_draft_defaults_preserve_unknown_provenance(catalog_session):
    source = make_source(catalog_session)
    version = CatalogSourceVersion(source_id=source.id, edition="1")
    catalog_session.add(version)
    catalog_session.flush()
    assert source.status == version.status == "Draft"
    assert version.revision == 1
    assert version.retrieved_at is None
    assert version.publication_date is None
    assert version.language is None
    assert version.official_locator is None
    assert not hasattr(version, "licensed")
    assert not hasattr(version, "tenant_id")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("publisher_key", ""),
        ("publisher_key", "x" * 129),
        ("name", ""),
        ("name", "x" * 1025),
        ("status", "Published"),
    ],
)
def test_publisher_rejects_invalid_metadata(catalog_session, field, value):
    publisher = CatalogPublisher(publisher_key="synthetic", name="Synthetic")
    setattr(publisher, field, value)
    catalog_session.add(publisher)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_key", ""),
        ("source_key", "x" * 129),
        ("title", ""),
        ("title", "x" * 1025),
        ("status", "Published"),
    ],
)
def test_source_rejects_invalid_metadata(catalog_session, field, value):
    source = make_source(catalog_session)
    setattr(source, field, value)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("edition", ""),
        ("edition", "x" * 129),
        ("language", ""),
        ("language", "x" * 36),
        ("official_locator", ""),
        ("official_locator", "x" * 4097),
        ("revision", 0),
        ("revision", -1),
        ("status", "Published"),
        ("status", "ApprovedForPublication"),
    ],
)
def test_version_rejects_invalid_metadata(catalog_session, field, value):
    source = make_source(catalog_session)
    version = CatalogSourceVersion(source_id=source.id, edition="1")
    setattr(version, field, value)
    catalog_session.add(version)
    with pytest.raises(IntegrityError):
        catalog_session.flush()


def test_publisher_key_is_unique(catalog_session):
    catalog_session.add_all(
        [
            CatalogPublisher(publisher_key="same", name="A"),
            CatalogPublisher(publisher_key="same", name="B"),
        ]
    )
    with pytest.raises(IntegrityError):
        catalog_session.flush()


def test_source_key_namespace_is_publisher(catalog_session):
    first = make_source(catalog_session, "same")
    second = make_source(catalog_session, "same")
    assert first.publisher_id != second.publisher_id
    catalog_session.add(
        CatalogSource(
            publisher_id=first.publisher_id,
            source_key="same",
            title="Duplicate",
        )
    )
    with pytest.raises(IntegrityError):
        catalog_session.flush()


def test_edition_uniqueness_does_not_make_locator_unique(catalog_session):
    source = make_source(catalog_session)
    for edition in ("1", "2"):
        catalog_session.add(
            CatalogSourceVersion(
                source_id=source.id,
                edition=edition,
                official_locator="https://example.invalid/source",
            )
        )
    catalog_session.flush()
    catalog_session.add(CatalogSourceVersion(source_id=source.id, edition="1"))
    with pytest.raises(IntegrityError):
        catalog_session.flush()


def test_same_source_predecessor_and_date_precision(catalog_session):
    source = make_source(catalog_session)
    first = CatalogSourceVersion(source_id=source.id, edition="1")
    catalog_session.add(first)
    catalog_session.flush()
    second = CatalogSourceVersion(
        source_id=source.id,
        edition="2",
        predecessor_id=first.id,
        publication_date=date(2026, 9, 27),
    )
    catalog_session.add(second)
    catalog_session.commit()
    catalog_session.expire_all()
    persisted = catalog_session.scalar(
        select(CatalogSourceVersion).where(CatalogSourceVersion.id == second.id)
    )
    assert persisted is not None
    assert persisted.publication_date == date(2026, 9, 27)


@pytest.mark.parametrize("invalid_lineage", ["different-source", "missing", "self"])
def test_invalid_predecessor_is_rejected(catalog_session, invalid_lineage):
    first_source = make_source(catalog_session)
    second_source = make_source(catalog_session)
    previous = CatalogSourceVersion(source_id=first_source.id, edition="1")
    catalog_session.add(previous)
    catalog_session.flush()
    version_id = uuid4()
    predecessor = {"different-source": previous.id, "missing": uuid4(), "self": version_id}
    catalog_session.add(
        CatalogSourceVersion(
            id=version_id,
            source_id=second_source.id,
            edition="2",
            predecessor_id=predecessor[invalid_lineage],
        )
    )
    with pytest.raises(IntegrityError):
        catalog_session.flush()


@pytest.mark.parametrize("target", ["publisher", "source", "predecessor"])
def test_history_foreign_keys_restrict_deletion(catalog_session, target):
    source = make_source(catalog_session)
    version = CatalogSourceVersion(source_id=source.id, edition="1")
    catalog_session.add(version)
    catalog_session.flush()
    catalog_session.add(
        CatalogSourceVersion(
            source_id=source.id,
            edition="2",
            predecessor_id=version.id,
        )
    )
    catalog_session.flush()
    targets = {
        "publisher": catalog_session.get(CatalogPublisher, source.publisher_id),
        "source": source,
        "predecessor": version,
    }
    catalog_session.delete(targets[target])
    with pytest.raises(IntegrityError):
        catalog_session.flush()
