"""Static regression checks for the WP-04 database security boundary."""

from pathlib import Path

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260930_0037_catalog_import_foundation.py"
)


def migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_import_tables_are_forced_rls_and_public_is_revoked():
    source = migration_text()
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM PUBLIC" in source
    assert "REVOKE ALL ON ALL TABLES IN SCHEMA public" not in source


def test_tenant_role_cannot_execute_seal_or_access_ledgers():
    source = migration_text()
    assert "REVOKE ALL ON FUNCTION public.catalog_seal_import_batch" in source
    for table in (
        "catalog_import_batches",
        "catalog_import_inputs",
        "catalog_import_reuse_ledger",
        "catalog_import_reconciliation_manifests",
    ):
        assert f"REVOKE ALL ON public.{table} FROM conformly_app" in source


def test_manifest_creation_is_only_available_through_seal_function():
    source = migration_text()
    assert "SECURITY DEFINER" in source
    assert "GRANT SELECT ON public.catalog_import_reconciliation_manifests" in source
    assert "GRANT SELECT, INSERT ON public.catalog_import_reconciliation_manifests" not in source
    assert "IMPORT_BATCH_NOT_RECONCILED" in source


def test_append_only_tables_reject_update_delete_and_truncate():
    source = migration_text()
    assert '("catalog_import_reuse_ledger", "catalog_import_reconciliation_manifests")' in source
    assert "{table}_no_update BEFORE UPDATE" in source
    assert "_no_delete BEFORE DELETE" in source
    assert "_no_truncate BEFORE TRUNCATE" in source


MIGRATION_0040 = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20261016_0040_catalog_assurance_import_reuse.py"
)


def migration_0040_text() -> str:
    return MIGRATION_0040.read_text(encoding="utf-8")


def test_migration_0040_target_constraints_and_downgrade_refusal():
    source = migration_0040_text()
    assert "EvidenceRequirementVersion" in source
    assert "AssessmentProcedureVersion" in source
    assert "CANNOT_DOWNGRADE_ASSURANCE_REUSE_DATA_EXISTS" in source
    assert "CATALOG_IMPORT_REUSE_TARGET_MISMATCH" in source
    assert "catalog_evidence_requirement_versions" in source
    assert "catalog_assessment_procedure_versions" in source
