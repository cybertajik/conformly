"""Catch PostgreSQL varchar bounds even when unit tests use SQLite."""

from conformly.frameworks.models import SourceRequirement
from conformly.frameworks.packs_data import TIER_A_FRAMEWORK_PACKS


def test_source_requirement_pack_strings_fit_database_schema() -> None:
    for pack in TIER_A_FRAMEWORK_PACKS:
        for requirement in pack.source_requirements:
            for column in SourceRequirement.__table__.columns:
                value = getattr(requirement, column.name, None)
                limit = getattr(column.type, "length", None)
                if isinstance(value, str) and limit is not None:
                    assert len(value) <= limit, (
                        pack.slug,
                        requirement.source_reference,
                        column.name,
                    )
