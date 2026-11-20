"""Actual migrated PostgreSQL denies all catalog runtime access in WP-03."""

import pytest
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import DBAPIError

from conformly.db.base import Base

TABLES_WP06A = (
    "catalog_evidence_requirement_versions",
    "catalog_evidence_requirement_artifact_types",
    "catalog_evidence_requirement_metadata_keys",
    "catalog_assessment_procedure_versions",
    "catalog_assessment_procedure_steps",
    "catalog_assessment_procedure_evidence_requirements",
)

TABLES = (
    "catalog_publishers",
    "catalog_sources",
    "catalog_source_versions",
    "catalog_source_provenance",
    "catalog_source_permission_proposals",
    "catalog_source_permission_guards",
    "catalog_source_permission_decisions",
    "catalog_requirements",
    "catalog_requirement_versions",
    "catalog_requirement_source_references",
    "catalog_common_controls",
    "catalog_control_versions",
    "catalog_packs",
    "catalog_pack_versions",
    "catalog_pack_memberships",
    "catalog_requirement_control_mappings",
    "catalog_mapping_versions",
    "catalog_audit_heads",
    "catalog_audit_events",
    "catalog_event_intents",
    "catalog_mutation_receipts",
    "catalog_evidence_requirement_versions",
    "catalog_evidence_requirement_artifact_types",
    "catalog_evidence_requirement_metadata_keys",
    "catalog_assessment_procedure_versions",
    "catalog_assessment_procedure_steps",
    "catalog_assessment_procedure_evidence_requirements",
)


@pytest.mark.parametrize("table_name", TABLES)
def test_migrated_constraint_inventory_matches_models(postgres_connection, table_name):
    # Alembic's default comparison does not prove CHECK-constraint coverage.
    # Compare actual constraint identities too; behavioral tests remain necessary.
    preparer = postgresql.dialect().identifier_preparer
    expected = {
        preparer.format_constraint(constraint)
        for constraint in Base.metadata.tables[table_name].constraints
    }
    assert None not in expected  # Include PostgreSQL's deterministic name shortening.
    with postgres_connection.begin():
        actual = set(
            postgres_connection.scalars(
                text(
                    "SELECT conname FROM pg_constraint WHERE conrelid = CAST(:table AS regclass) AND contype <> 't'"
                ),
                {"table": f"public.{table_name}"},
            )
        )
        assert actual == expected


@pytest.mark.parametrize("table_name", TABLES)
def test_catalog_rls_is_forced_without_policies(postgres_connection, table_name):
    with postgres_connection.begin():
        row = postgres_connection.execute(
            text(
                "SELECT c.relrowsecurity, c.relforcerowsecurity, "
                "(SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid "
                " AND (p.polroles = '{0}' OR EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname = 'conformly_app' AND r.oid = ANY(p.polroles)))) AS app_policies, "
                "(SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid "
                " AND EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname = 'conformly_catalog' AND r.oid = ANY(p.polroles))) AS catalog_policies "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = :table"
            ),
            {"table": table_name},
        ).one()
        assert row.relrowsecurity is True
        assert row.relforcerowsecurity is True
        assert row.app_policies == 0
        assert row.catalog_policies == 1


@pytest.mark.parametrize("table_name", TABLES)
@pytest.mark.parametrize(
    "privilege", ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]
)
def test_catalog_runtime_has_no_effective_privileges(postgres_connection, table_name, privilege):
    with postgres_connection.begin():
        assert (
            postgres_connection.scalar(
                text("SELECT has_table_privilege(current_user, :table, :privilege)"),
                {"table": f"public.{table_name}", "privilege": privilege},
            )
            is False
        )


@pytest.mark.parametrize("table_name", TABLES)
def test_catalog_has_no_public_acl(postgres_connection, table_name):
    with postgres_connection.begin():
        assert (
            postgres_connection.scalar(
                text(
                    "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl, acldefault('r', c.relowner))) a "
                    "WHERE n.nspname = 'public' AND c.relname = :table AND a.grantee = 0"
                ),
                {"table": table_name},
            )
            == 0
        )


@pytest.mark.parametrize("table_name", TABLES)
@pytest.mark.parametrize("operation", ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"])
def test_catalog_runtime_operations_fail_closed(postgres_connection, table_name, operation):
    # Both axes are literal test constants, never user-controlled identifiers.
    col = (
        "source_id"
        if table_name == "catalog_source_permission_guards"
        else ("chain_key" if table_name == "catalog_audit_heads" else "id")
    )
    statements = {
        "SELECT": f'SELECT * FROM public."{table_name}"',
        "INSERT": f'INSERT INTO public."{table_name}" DEFAULT VALUES',
        "UPDATE": f'UPDATE public."{table_name}" SET {col} = {col}',
        "DELETE": f'DELETE FROM public."{table_name}"',
        "TRUNCATE": f'TRUNCATE public."{table_name}"',
    }
    with postgres_connection.begin() as transaction:
        with pytest.raises(DBAPIError) as failure:
            postgres_connection.execute(text(statements[operation]))
        assert getattr(failure.value.orig, "sqlstate", None) == "42501"
        transaction.rollback()
    with postgres_connection.begin():
        assert postgres_connection.scalar(text("SELECT 1")) == 1


@pytest.mark.parametrize(
    "table_name", ["catalog_source_provenance", "catalog_source_permission_proposals"]
)
def test_history_has_enabled_mutation_and_truncate_guards(postgres_connection, table_name):
    with postgres_connection.begin():
        rows = postgres_connection.execute(
            text(
                "SELECT t.tgname, t.tgenabled, pg_get_triggerdef(t.oid) AS definition, "
                "p.proname, p.prosecdef FROM pg_trigger t "
                "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_proc p ON p.oid=t.tgfoid "
                "WHERE n.nspname='public' AND c.relname=:table AND NOT t.tgisinternal"
            ),
            {"table": table_name},
        ).all()
        guards = {row.tgname: row for row in rows}
        assert set(guards) == {f"{table_name}_immutable", f"{table_name}_no_truncate"}
        for guard in guards.values():
            assert guard.tgenabled == "O"
            assert guard.proname == "catalog_source_history_append_only"
            assert guard.prosecdef is False
            assert "BEFORE" in guard.definition
        mutation = guards[f"{table_name}_immutable"].definition
        assert "UPDATE" in mutation and "DELETE" in mutation and "FOR EACH ROW" in mutation
        truncate = guards[f"{table_name}_no_truncate"].definition
        assert "TRUNCATE" in truncate and "FOR EACH STATEMENT" in truncate


def test_history_trigger_function_is_not_a_runtime_entry_point(postgres_connection):
    with postgres_connection.begin():
        row = postgres_connection.execute(
            text(
                "SELECT p.prosecdef, p.proconfig, "
                "has_function_privilege(current_user, p.oid, 'EXECUTE') AS can_execute "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='public' AND p.proname='catalog_source_history_append_only' "
                "AND p.pronargs=0"
            )
        ).one()
        assert row.prosecdef is False
        assert row.proconfig == ["search_path=pg_catalog"]
        assert row.can_execute is False


def test_requirement_version_has_reference_constraint_trigger_exists(postgres_connection):
    with postgres_connection.begin():
        assert (
            postgres_connection.scalar(
                text(
                    "SELECT count(*) FROM pg_constraint "
                    "WHERE conrelid = 'public.catalog_requirement_versions'::regclass "
                    "AND contype = 't' AND conname = 'trg_catalog_requirement_version_has_reference'"
                )
            )
            == 1
        )


def test_requirement_source_references_has_enabled_mutation_and_truncate_guards(
    postgres_connection,
):
    table_name = "catalog_requirement_source_references"
    with postgres_connection.begin():
        rows = postgres_connection.execute(
            text(
                "SELECT t.tgname, t.tgenabled, pg_get_triggerdef(t.oid) AS definition, "
                "p.proname, p.prosecdef FROM pg_trigger t "
                "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_proc p ON p.oid=t.tgfoid "
                "WHERE n.nspname='public' AND c.relname=:table AND NOT t.tgisinternal"
            ),
            {"table": table_name},
        ).all()
        guards = {row.tgname: row for row in rows}
        assert set(guards) == {f"{table_name}_immutable", f"{table_name}_no_truncate"}
        for guard in guards.values():
            assert guard.tgenabled == "O"
            assert guard.proname == "catalog_requirement_source_references_append_only"
            assert guard.prosecdef is False
            assert "BEFORE" in guard.definition
        mutation = guards[f"{table_name}_immutable"].definition
        assert "UPDATE" in mutation and "DELETE" in mutation and "FOR EACH ROW" in mutation
        truncate = guards[f"{table_name}_no_truncate"].definition
        assert "TRUNCATE" in truncate and "FOR EACH STATEMENT" in truncate


def test_requirement_source_references_trigger_function_is_not_a_runtime_entry_point(
    postgres_connection,
):
    with postgres_connection.begin():
        row = postgres_connection.execute(
            text(
                "SELECT p.prosecdef, p.proconfig, "
                "has_function_privilege(current_user, p.oid, 'EXECUTE') AS can_execute "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='public' AND p.proname='catalog_requirement_source_references_append_only' "
                "AND p.pronargs=0"
            )
        ).one()
        assert row.prosecdef is False
        assert row.proconfig == ["search_path=pg_catalog"]
        assert row.can_execute is False


def test_catalog_version_acyclic_triggers_exist(postgres_connection):
    with postgres_connection.begin():
        req_trg = postgres_connection.scalar(
            text(
                "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = 'catalog_requirement_versions' "
                "AND t.tgname = 'trg_catalog_requirement_version_acyclic'"
            )
        )
        ctrl_trg = postgres_connection.scalar(
            text(
                "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = 'catalog_control_versions' "
                "AND t.tgname = 'trg_catalog_control_version_acyclic'"
            )
        )
        pack_trg = postgres_connection.scalar(
            text(
                "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = 'catalog_pack_versions' "
                "AND t.tgname = 'trg_catalog_pack_version_acyclic'"
            )
        )
        map_trg = postgres_connection.scalar(
            text(
                "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = 'catalog_mapping_versions' "
                "AND t.tgname = 'trg_catalog_mapping_version_acyclic'"
            )
        )
        assert req_trg == 1
        assert ctrl_trg == 1
        assert pack_trg == 1
        assert map_trg == 1


def test_pack_memberships_has_enabled_mutation_and_truncate_guards(postgres_connection):
    table_name = "catalog_pack_memberships"
    with postgres_connection.begin():
        rows = postgres_connection.execute(
            text(
                "SELECT t.tgname, t.tgenabled, pg_get_triggerdef(t.oid) AS definition, "
                "p.proname, p.prosecdef FROM pg_trigger t "
                "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_proc p ON p.oid=t.tgfoid "
                "WHERE n.nspname='public' AND c.relname=:table AND NOT t.tgisinternal"
            ),
            {"table": table_name},
        ).all()
        guards = {row.tgname: row for row in rows}
        assert set(guards) == {
            f"{table_name}_immutable",
            f"{table_name}_no_truncate",
            "trg_catalog_pack_membership_sequence",
        }
        for guard_name in (f"{table_name}_immutable", f"{table_name}_no_truncate"):
            guard = guards[guard_name]
            assert guard.tgenabled == "O"
            assert guard.proname == "catalog_pack_memberships_append_only"
            assert guard.prosecdef is False
            assert "BEFORE" in guard.definition
        mutation = guards[f"{table_name}_immutable"].definition
        assert "UPDATE" in mutation and "DELETE" in mutation and "FOR EACH ROW" in mutation
        truncate = guards[f"{table_name}_no_truncate"].definition
        assert "TRUNCATE" in truncate and "FOR EACH STATEMENT" in truncate

        seq_guard = guards["trg_catalog_pack_membership_sequence"]
        assert seq_guard.tgenabled == "O"
        assert seq_guard.proname == "catalog_pack_membership_check_sequence"
        assert seq_guard.prosecdef is False
        assert "BEFORE INSERT" in seq_guard.definition and "FOR EACH ROW" in seq_guard.definition


def test_pack_memberships_trigger_functions_are_not_runtime_entry_points(postgres_connection):
    with postgres_connection.begin():
        for func_name in (
            "catalog_pack_memberships_append_only",
            "catalog_pack_membership_check_sequence",
        ):
            row = postgres_connection.execute(
                text(
                    "SELECT p.prosecdef, p.proconfig, "
                    "has_function_privilege(current_user, p.oid, 'EXECUTE') AS can_execute "
                    "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                    "WHERE n.nspname='public' AND p.proname=:func_name "
                    "AND p.pronargs=0"
                ),
                {"func_name": func_name},
            ).one()
            assert row.prosecdef is False
            assert row.proconfig == ["search_path=pg_catalog"]
            assert row.can_execute is False


@pytest.mark.parametrize(
    "table_name",
    [
        "catalog_source_permission_decisions",
        "catalog_audit_events",
        "catalog_event_intents",
        "catalog_mutation_receipts",
    ],
)
def test_support_tables_have_enabled_mutation_and_truncate_guards(postgres_connection, table_name):
    with postgres_connection.begin():
        rows = postgres_connection.execute(
            text(
                "SELECT t.tgname, t.tgenabled, pg_get_triggerdef(t.oid) AS definition, "
                "p.proname, p.prosecdef FROM pg_trigger t "
                "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_proc p ON p.oid=t.tgfoid "
                "WHERE n.nspname='public' AND c.relname=:table AND NOT t.tgisinternal"
            ),
            {"table": table_name},
        ).all()
        guards = {row.tgname: row for row in rows}
        expected = {f"{table_name}_immutable", f"{table_name}_no_truncate"}
        if table_name == "catalog_source_permission_decisions":
            expected.add("trg_catalog_permission_decision_validate")
        assert set(guards) == expected
        for guard_name in (f"{table_name}_immutable", f"{table_name}_no_truncate"):
            guard = guards[guard_name]
            assert guard.tgenabled == "O"
            assert (
                guard.proname == "catalog_support_append_only"
                if "immutable" in guard_name
                else "catalog_support_no_truncate"
            )
            assert guard.prosecdef is False
            assert "BEFORE" in guard.definition


def test_support_trigger_functions_are_not_runtime_entry_points(postgres_connection):
    with postgres_connection.begin():
        for func_name in (
            "catalog_support_append_only",
            "catalog_support_no_truncate",
            "catalog_source_permission_decision_validate",
        ):
            row = postgres_connection.execute(
                text(
                    "SELECT p.prosecdef, p.proconfig, "
                    "has_function_privilege(current_user, p.oid, 'EXECUTE') AS can_execute "
                    "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                    "WHERE n.nspname='public' AND p.proname=:func_name "
                    "AND p.pronargs=0"
                ),
                {"func_name": func_name},
            ).one()
            assert row.prosecdef is False
            assert row.proconfig == ["search_path=pg_catalog"]
            assert row.can_execute is False


@pytest.mark.parametrize("table_name", TABLES_WP06A)
def test_assurance_content_tables_have_enabled_mutation_and_truncate_guards(
    postgres_connection, table_name
):
    with postgres_connection.begin():
        rows = postgres_connection.execute(
            text(
                "SELECT t.tgname, t.tgenabled, pg_get_triggerdef(t.oid) AS definition, "
                "p.proname, p.prosecdef FROM pg_trigger t "
                "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_proc p ON p.oid=t.tgfoid "
                "WHERE n.nspname='public' AND c.relname=:table AND NOT t.tgisinternal"
            ),
            {"table": table_name},
        ).all()
        guards = {row.tgname: row for row in rows}
        assert f"{table_name}_immutable" in guards
        assert f"{table_name}_no_truncate" in guards
        imm = guards[f"{table_name}_immutable"]
        assert imm.tgenabled == "O"
        assert imm.proname == "catalog_assurance_content_append_only"
        assert imm.prosecdef is False
        assert "BEFORE" in imm.definition
        assert "UPDATE" in imm.definition and "DELETE" in imm.definition
        trunc = guards[f"{table_name}_no_truncate"]
        assert trunc.tgenabled == "O"
        assert trunc.proname == "catalog_assurance_content_append_only"
        assert trunc.prosecdef is False
        assert "BEFORE" in trunc.definition and "TRUNCATE" in trunc.definition


def test_assurance_content_trigger_functions_are_not_runtime_entry_points(postgres_connection):
    functions = (
        "catalog_assurance_content_append_only",
        "catalog_evidence_requirement_version_sequence_guard",
        "catalog_er_artifact_type_sequence_guard",
        "catalog_er_metadata_key_sequence_guard",
        "catalog_assessment_procedure_version_sequence_guard",
        "catalog_ap_step_sequence_guard",
        "catalog_ap_evidence_req_sequence_guard",
        "catalog_control_version_assurance_freeze",
    )
    with postgres_connection.begin():
        for func_name in functions:
            row = postgres_connection.execute(
                text(
                    "SELECT p.prosecdef, p.proconfig, "
                    "has_function_privilege(current_user, p.oid, 'EXECUTE') AS can_execute "
                    "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                    "WHERE n.nspname='public' AND p.proname=:func_name "
                    "AND p.pronargs=0"
                ),
                {"func_name": func_name},
            ).one()
            assert row.prosecdef is False
            assert row.proconfig == ["search_path=pg_catalog"]
            assert row.can_execute is False


ROOT_TABLES_WP06A = (
    "catalog_evidence_requirement_versions",
    "catalog_assessment_procedure_versions",
)


@pytest.mark.parametrize("table_name", TABLES_WP06A)
@pytest.mark.parametrize(
    "privilege", ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]
)
def test_catalog_role_privileges_on_wp06a_tables(postgres_connection, table_name, privilege):
    with postgres_connection.begin():
        has_role = postgres_connection.scalar(
            text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_catalog')")
        )
        if has_role:
            has_priv = postgres_connection.scalar(
                text("SELECT has_table_privilege('conformly_catalog', :table, :privilege)"),
                {"table": f"public.{table_name}", "privilege": privilege},
            )
            if privilege in ("SELECT", "INSERT"):
                assert has_priv is True
            elif privilege == "UPDATE" and table_name in ROOT_TABLES_WP06A:
                assert has_priv is True
            else:
                assert has_priv is False


@pytest.mark.parametrize("table_name", TABLES_WP06A)
@pytest.mark.parametrize(
    "privilege", ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]
)
def test_app_role_has_no_privileges_on_wp06a_tables(postgres_connection, table_name, privilege):
    with postgres_connection.begin():
        has_role = postgres_connection.scalar(
            text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_app')")
        )
        if has_role:
            assert (
                postgres_connection.scalar(
                    text("SELECT has_table_privilege('conformly_app', :table, :privilege)"),
                    {"table": f"public.{table_name}", "privilege": privilege},
                )
                is False
            )


def test_control_version_assurance_freeze_trigger_exists(postgres_connection):
    with postgres_connection.begin():
        row = postgres_connection.execute(
            text(
                "SELECT t.tgname, t.tgenabled, pg_get_triggerdef(t.oid) AS definition, "
                "p.proname, p.prosecdef FROM pg_trigger t "
                "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_proc p ON p.oid=t.tgfoid "
                "WHERE n.nspname='public' AND c.relname='catalog_control_versions' "
                "AND t.tgname='trg_catalog_control_version_assurance_freeze'"
            )
        ).one()
        assert row.tgenabled == "O"
        assert row.proname == "catalog_control_version_assurance_freeze"
        assert row.prosecdef is False
        assert "BEFORE UPDATE" in row.definition


TABLES_WP07B = (
    "catalog_fact_definitions",
    "catalog_fact_definition_versions",
    "catalog_fact_definition_scopes",
    "catalog_fact_definition_enum_values",
)


@pytest.mark.parametrize("table_name", TABLES_WP07B)
def test_wp07b_migrated_constraint_inventory_matches_models(postgres_connection, table_name):
    preparer = postgresql.dialect().identifier_preparer
    expected = {
        preparer.format_constraint(constraint)
        for constraint in Base.metadata.tables[table_name].constraints
    }
    assert None not in expected
    with postgres_connection.begin():
        actual = set(
            postgres_connection.scalars(
                text(
                    "SELECT conname FROM pg_constraint WHERE conrelid = CAST(:table AS regclass) AND contype <> 't'"
                ),
                {"table": f"public.{table_name}"},
            )
        )
        assert actual == expected


@pytest.mark.parametrize("table_name", TABLES_WP07B)
def test_wp07b_catalog_rls_is_forced_with_zero_policies(postgres_connection, table_name):
    with postgres_connection.begin():
        row = postgres_connection.execute(
            text(
                "SELECT c.relrowsecurity, c.relforcerowsecurity, "
                "(SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid "
                " AND (p.polroles = '{0}' OR EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname = 'conformly_app' AND r.oid = ANY(p.polroles)))) AS app_policies, "
                "(SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid "
                " AND EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname = 'conformly_catalog' AND r.oid = ANY(p.polroles))) AS catalog_policies "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = :table"
            ),
            {"table": table_name},
        ).one()
        assert row.relrowsecurity is True
        assert row.relforcerowsecurity is True
        assert row.app_policies == 0
        assert row.catalog_policies == 0


@pytest.mark.parametrize("table_name", TABLES_WP07B)
@pytest.mark.parametrize(
    "privilege", ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]
)
def test_wp07b_catalog_runtime_has_no_effective_privileges(
    postgres_connection, table_name, privilege
):
    with postgres_connection.begin():
        assert (
            postgres_connection.scalar(
                text("SELECT has_table_privilege(current_user, :table, :privilege)"),
                {"table": f"public.{table_name}", "privilege": privilege},
            )
            is False
        )


@pytest.mark.parametrize("table_name", TABLES_WP07B)
def test_wp07b_catalog_has_no_public_acl(postgres_connection, table_name):
    with postgres_connection.begin():
        assert (
            postgres_connection.scalar(
                text(
                    "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl, acldefault('r', c.relowner))) a "
                    "WHERE n.nspname = 'public' AND c.relname = :table AND a.grantee = 0"
                ),
                {"table": table_name},
            )
            == 0
        )


@pytest.mark.parametrize("table_name", TABLES_WP07B)
@pytest.mark.parametrize("operation", ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"])
def test_wp07b_catalog_runtime_operations_fail_closed(postgres_connection, table_name, operation):
    statements = {
        "SELECT": f'SELECT * FROM public."{table_name}"',
        "INSERT": f'INSERT INTO public."{table_name}" DEFAULT VALUES',
        "UPDATE": f'UPDATE public."{table_name}" SET id = id',
        "DELETE": f'DELETE FROM public."{table_name}"',
        "TRUNCATE": f'TRUNCATE public."{table_name}"',
    }
    with postgres_connection.begin() as transaction:
        with pytest.raises(DBAPIError) as failure:
            postgres_connection.execute(text(statements[operation]))
        assert getattr(failure.value.orig, "sqlstate", None) == "42501"
        transaction.rollback()
    with postgres_connection.begin():
        assert postgres_connection.scalar(text("SELECT 1")) == 1


@pytest.mark.parametrize("table_name", TABLES_WP07B)
def test_wp07b_fact_definition_tables_have_enabled_mutation_and_truncate_guards(
    postgres_connection, table_name
):
    with postgres_connection.begin():
        rows = postgres_connection.execute(
            text(
                "SELECT t.tgname, t.tgenabled, pg_get_triggerdef(t.oid) AS definition, "
                "p.proname, p.prosecdef FROM pg_trigger t "
                "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_proc p ON p.oid=t.tgfoid "
                "WHERE n.nspname='public' AND c.relname=:table AND NOT t.tgisinternal"
            ),
            {"table": table_name},
        ).all()
        guards = {row.tgname: row for row in rows}
        assert f"{table_name}_immutable" in guards
        assert f"{table_name}_no_truncate" in guards
        imm = guards[f"{table_name}_immutable"]
        assert imm.tgenabled == "O"
        assert imm.proname == "catalog_fact_definition_append_only"
        assert imm.prosecdef is False
        assert "BEFORE" in imm.definition
        assert "UPDATE" in imm.definition and "DELETE" in imm.definition
        trunc = guards[f"{table_name}_no_truncate"]
        assert trunc.tgenabled == "O"
        assert trunc.proname == "catalog_fact_definition_append_only"
        assert trunc.prosecdef is False
        assert "BEFORE" in trunc.definition and "TRUNCATE" in trunc.definition


def test_wp07b_fact_definition_trigger_functions_are_not_runtime_entry_points(postgres_connection):
    functions = (
        "catalog_fact_definition_append_only",
        "catalog_fact_definition_version_sequence_guard",
        "catalog_fact_definition_scope_sequence_guard",
        "catalog_fact_definition_enum_value_sequence_guard",
    )
    with postgres_connection.begin():
        for func_name in functions:
            row = postgres_connection.execute(
                text(
                    "SELECT p.prosecdef, p.proconfig, "
                    "has_function_privilege(current_user, p.oid, 'EXECUTE') AS can_execute "
                    "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                    "WHERE n.nspname='public' AND p.proname=:func_name "
                    "AND p.pronargs=0"
                ),
                {"func_name": func_name},
            ).one()
            assert row.prosecdef is False
            assert row.proconfig == ["search_path=pg_catalog"]
            assert row.can_execute is False


@pytest.mark.parametrize("table_name", TABLES_WP07B)
@pytest.mark.parametrize(
    "privilege", ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]
)
def test_catalog_role_has_no_privileges_on_wp07b_tables(postgres_connection, table_name, privilege):
    with postgres_connection.begin():
        has_role = postgres_connection.scalar(
            text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_catalog')")
        )
        if has_role:
            assert (
                postgres_connection.scalar(
                    text("SELECT has_table_privilege('conformly_catalog', :table, :privilege)"),
                    {"table": f"public.{table_name}", "privilege": privilege},
                )
                is False
            )


@pytest.mark.parametrize("table_name", TABLES_WP07B)
@pytest.mark.parametrize(
    "privilege", ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]
)
def test_app_role_has_no_privileges_on_wp07b_tables(postgres_connection, table_name, privilege):
    with postgres_connection.begin():
        has_role = postgres_connection.scalar(
            text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_app')")
        )
        if has_role:
            assert (
                postgres_connection.scalar(
                    text("SELECT has_table_privilege('conformly_app', :table, :privilege)"),
                    {"table": f"public.{table_name}", "privilege": privilege},
                )
                is False
            )


TABLES_WP07C2 = (
    "catalog_applicability_rules",
    "catalog_applicability_rule_versions",
    "catalog_applicability_rule_fact_refs",
    "catalog_applicability_rule_source_refs",
)


@pytest.mark.parametrize("table_name", TABLES_WP07C2)
def test_wp07c2_migrated_constraint_inventory_matches_models(postgres_connection, table_name):
    preparer = postgresql.dialect().identifier_preparer
    expected = {
        preparer.format_constraint(constraint)
        for constraint in Base.metadata.tables[table_name].constraints
    }
    assert None not in expected
    with postgres_connection.begin():
        actual = set(
            postgres_connection.scalars(
                text(
                    "SELECT conname FROM pg_constraint WHERE conrelid = CAST(:table AS regclass) AND contype <> 't'"
                ),
                {"table": f"public.{table_name}"},
            )
        )
        assert actual == expected


@pytest.mark.parametrize("table_name", TABLES_WP07C2)
def test_wp07c2_catalog_rls_is_forced_with_zero_policies(postgres_connection, table_name):
    with postgres_connection.begin():
        row = postgres_connection.execute(
            text(
                "SELECT c.relrowsecurity, c.relforcerowsecurity, "
                "(SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid "
                " AND (p.polroles = '{0}' OR EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname = 'conformly_app' AND r.oid = ANY(p.polroles)))) AS app_policies, "
                "(SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid "
                " AND EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname = 'conformly_catalog' AND r.oid = ANY(p.polroles))) AS catalog_policies "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = :table"
            ),
            {"table": table_name},
        ).one()
        assert row.relrowsecurity is True
        assert row.relforcerowsecurity is True
        assert row.app_policies == 0
        assert row.catalog_policies == 0


@pytest.mark.parametrize("table_name", TABLES_WP07C2)
@pytest.mark.parametrize(
    "privilege", ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]
)
def test_wp07c2_catalog_runtime_has_no_effective_privileges(
    postgres_connection, table_name, privilege
):
    with postgres_connection.begin():
        assert (
            postgres_connection.scalar(
                text("SELECT has_table_privilege(current_user, :table, :privilege)"),
                {"table": f"public.{table_name}", "privilege": privilege},
            )
            is False
        )


@pytest.mark.parametrize("table_name", TABLES_WP07C2)
def test_wp07c2_catalog_has_no_public_acl(postgres_connection, table_name):
    with postgres_connection.begin():
        assert (
            postgres_connection.scalar(
                text(
                    "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl, acldefault('r', c.relowner))) a "
                    "WHERE n.nspname = 'public' AND c.relname = :table AND a.grantee = 0"
                ),
                {"table": table_name},
            )
            == 0
        )


@pytest.mark.parametrize("table_name", TABLES_WP07C2)
@pytest.mark.parametrize("operation", ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"])
def test_wp07c2_catalog_runtime_operations_fail_closed(postgres_connection, table_name, operation):
    statements = {
        "SELECT": f'SELECT * FROM public."{table_name}"',
        "INSERT": f'INSERT INTO public."{table_name}" DEFAULT VALUES',
        "UPDATE": f'UPDATE public."{table_name}" SET id = id',
        "DELETE": f'DELETE FROM public."{table_name}"',
        "TRUNCATE": f'TRUNCATE public."{table_name}"',
    }
    with postgres_connection.begin() as transaction:
        with pytest.raises(DBAPIError) as failure:
            postgres_connection.execute(text(statements[operation]))
        assert getattr(failure.value.orig, "sqlstate", None) == "42501"
        transaction.rollback()
    with postgres_connection.begin():
        assert postgres_connection.scalar(text("SELECT 1")) == 1


@pytest.mark.parametrize("table_name", TABLES_WP07C2)
def test_wp07c2_applicability_rule_tables_have_enabled_mutation_and_truncate_guards(
    postgres_connection, table_name
):
    with postgres_connection.begin():
        rows = postgres_connection.execute(
            text(
                "SELECT t.tgname, t.tgenabled, pg_get_triggerdef(t.oid) AS definition, "
                "p.proname, p.prosecdef FROM pg_trigger t "
                "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_proc p ON p.oid=t.tgfoid "
                "WHERE n.nspname='public' AND c.relname=:table AND NOT t.tgisinternal"
            ),
            {"table": table_name},
        ).all()
        guards = {row.tgname: row for row in rows}
        assert f"{table_name}_immutable" in guards
        assert f"{table_name}_no_truncate" in guards
        imm = guards[f"{table_name}_immutable"]
        trunc = guards[f"{table_name}_no_truncate"]
        assert imm.tgenabled == "O"
        assert imm.proname == "catalog_app_rule_append_only"
        assert imm.prosecdef is False
        assert "BEFORE" in imm.definition and (
            "UPDATE" in imm.definition or "DELETE" in imm.definition
        )
        assert trunc.tgenabled == "O"
        assert trunc.proname == "catalog_app_rule_append_only"
        assert trunc.prosecdef is False
        assert "BEFORE" in trunc.definition and "TRUNCATE" in trunc.definition


def test_wp07c2_applicability_rule_trigger_functions_are_not_runtime_entry_points(
    postgres_connection,
):
    functions = (
        "catalog_app_rule_append_only",
        "catalog_app_rule_version_sequence_guard",
        "catalog_app_rule_fact_ref_sequence_guard",
        "catalog_app_rule_source_ref_sequence_guard",
    )
    with postgres_connection.begin():
        for func_name in functions:
            row = postgres_connection.execute(
                text(
                    "SELECT p.prosecdef, p.proconfig, "
                    "has_function_privilege(current_user, p.oid, 'EXECUTE') AS can_execute "
                    "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                    "WHERE n.nspname='public' AND p.proname=:func_name "
                    "AND p.pronargs=0"
                ),
                {"func_name": func_name},
            ).one()
            assert row.prosecdef is False
            assert row.proconfig == ["search_path=pg_catalog"]
            assert row.can_execute is False


@pytest.mark.parametrize("table_name", TABLES_WP07C2)
@pytest.mark.parametrize(
    "privilege", ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]
)
def test_catalog_role_has_no_privileges_on_wp07c2_tables(
    postgres_connection, table_name, privilege
):
    with postgres_connection.begin():
        has_role = postgres_connection.scalar(
            text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_catalog')")
        )
        if has_role:
            assert (
                postgres_connection.scalar(
                    text("SELECT has_table_privilege('conformly_catalog', :table, :privilege)"),
                    {"table": f"public.{table_name}", "privilege": privilege},
                )
                is False
            )


@pytest.mark.parametrize("table_name", TABLES_WP07C2)
@pytest.mark.parametrize(
    "privilege", ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]
)
def test_app_role_has_no_privileges_on_wp07c2_tables(postgres_connection, table_name, privilege):
    with postgres_connection.begin():
        has_role = postgres_connection.scalar(
            text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conformly_app')")
        )
        if has_role:
            assert (
                postgres_connection.scalar(
                    text("SELECT has_table_privilege('conformly_app', :table, :privilege)"),
                    {"table": f"public.{table_name}", "privilege": privilege},
                )
                is False
            )
