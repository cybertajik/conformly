"""Preserve existing migration objects in ORM metadata; no DB connection needed."""

import pytest
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import postgresql, sqlite

from conformly.catalog_v2 import models as _catalog_v2_models  # noqa: F401
from conformly.catalog_v2 import models_import as _catalog_v2_models_import  # noqa: F401
from conformly.db.base import Base


@pytest.mark.parametrize("table_name", ["assets", "risks", "vendors"])
@pytest.mark.parametrize("scope", ["legal_entity", "business_unit"])
def test_scope_indexes_match_existing_migration(table_name: str, scope: str) -> None:
    table = Base.metadata.tables[table_name]
    index = next(index for index in table.indexes if index.name == f"ix_{table_name}_{scope}")
    assert list(index.columns.keys()) == ["tenant_id", f"{scope}_id"]
    assert not index.unique


@pytest.mark.parametrize(
    ("table_name", "column", "unique_index"),
    [
        ("public_profiles", "tenant_id", True),
        ("public_profiles", "slug", True),
        ("whistleblower_portals", "slug", False),
        ("whistleblower_cases", "public_case_id", False),
    ],
)
def test_uniqueness_remains_enforced_by_existing_constraint(
    table_name: str, column: str, unique_index: bool
) -> None:
    table = Base.metadata.tables[table_name]
    constraints = [item for item in table.constraints if isinstance(item, UniqueConstraint)]
    assert any(
        item.name == f"uq_{table_name}_{column}" and list(item.columns.keys()) == [column]
        for item in constraints
    )
    index = next(item for item in table.indexes if item.name == f"ix_{table_name}_{column}")
    assert list(index.columns.keys()) == [column]
    assert index.unique is unique_index


@pytest.mark.parametrize("column", ["encrypted_category", "encrypted_title"])
def test_encrypted_metadata_uses_migrated_type_per_dialect(column: str) -> None:
    field_type = Base.metadata.tables["whistleblower_cases"].c[column].type
    assert field_type.compile(dialect=postgresql.dialect()) == "JSONB"
    assert field_type.compile(dialect=sqlite.dialect()) == "JSON"


@pytest.mark.parametrize(
    "table_name",
    [
        "catalog_evidence_requirement_versions",
        "catalog_evidence_requirement_artifact_types",
        "catalog_evidence_requirement_metadata_keys",
        "catalog_assessment_procedure_versions",
        "catalog_assessment_procedure_steps",
        "catalog_assessment_procedure_evidence_requirements",
    ],
)
def test_wp06a_assurance_content_tables_in_metadata(table_name: str) -> None:
    assert table_name in Base.metadata.tables
    table = Base.metadata.tables[table_name]
    assert len(table.primary_key.columns) > 0


def test_wp06c_import_check_constraints_in_metadata() -> None:
    inputs_table = Base.metadata.tables["catalog_import_inputs"]
    input_constraint = next(
        c
        for c in inputs_table.constraints
        if getattr(c, "name", "")
        and getattr(c, "name", "").endswith("catalog_import_input_target_type")
    )
    assert "EvidenceRequirementVersion" in str(input_constraint.sqltext)  # type: ignore[attr-defined]
    assert "AssessmentProcedureVersion" in str(input_constraint.sqltext)  # type: ignore[attr-defined]

    reuse_table = Base.metadata.tables["catalog_import_reuse_ledger"]
    reuse_constraint = next(
        c
        for c in reuse_table.constraints
        if getattr(c, "name", "")
        and getattr(c, "name", "").endswith("catalog_import_reuse_target_type")
    )
    assert "EvidenceRequirementVersion" in str(reuse_constraint.sqltext)  # type: ignore[attr-defined]
    assert "AssessmentProcedureVersion" in str(reuse_constraint.sqltext)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "table_name",
    [
        "catalog_fact_definitions",
        "catalog_fact_definition_versions",
        "catalog_fact_definition_scopes",
        "catalog_fact_definition_enum_values",
    ],
)
def test_wp07b_fact_definition_tables_in_metadata(table_name: str) -> None:
    assert table_name in Base.metadata.tables
    table = Base.metadata.tables[table_name]
    assert len(table.primary_key.columns) > 0


@pytest.mark.parametrize(
    "table_name",
    [
        "catalog_applicability_rules",
        "catalog_applicability_rule_versions",
        "catalog_applicability_rule_fact_refs",
        "catalog_applicability_rule_source_refs",
    ],
)
def test_wp07c2_applicability_rule_tables_in_metadata(table_name: str) -> None:
    assert table_name in Base.metadata.tables
    table = Base.metadata.tables[table_name]
    assert len(table.primary_key.columns) > 0
