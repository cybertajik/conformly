from dataclasses import replace

import pytest

from tests.postgres_test_target import (
    PostgresTestTarget,
    UnsafePostgresTargetError,
    require_postgres_test_target,
    require_safe_runtime_identity,
)


def disposable_environment() -> dict[str, str]:
    return {
        "CONFORMLY_TEST_APP_DATABASE_URL": (
            "postgresql+psycopg://conformly_app:test-only-sentinel@localhost:5432/conformly"
        ),
        "CONFORMLY_TEST_DATABASE_DISPOSABLE": "yes",
        "CONFORMLY_TEST_DATABASE_NAME": "conformly",
        "CONFORMLY_TEST_DATABASE_ROLE": "conformly_app",
    }


def safe_identity() -> dict[str, object]:
    return {
        "database_name": "conformly",
        "runtime_role": "conformly_app",
        "login_role": "conformly_app",
        "is_superuser": False,
        "bypasses_rls": False,
        "can_create_roles": False,
        "can_create_databases": False,
        "can_assume_privileged_role": False,
        "owns_database": False,
        "owns_relations": False,
        "row_security": "on",
    }


def test_accepts_explicit_disposable_target_without_exposing_password() -> None:
    target = require_postgres_test_target(disposable_environment())
    assert target.host == "127.0.0.1"
    assert target.port == 5432
    assert "test-only-sentinel" not in repr(target)
    require_safe_runtime_identity(target, safe_identity())


@pytest.mark.parametrize("key", list(disposable_environment()))
def test_missing_required_configuration_is_an_error(key: str) -> None:
    environment = disposable_environment()
    del environment[key]
    with pytest.raises(UnsafePostgresTargetError):
        require_postgres_test_target(environment)


@pytest.mark.parametrize("acknowledgement", ["", "true", "1", "YES", " yes "])
def test_requires_exact_disposable_acknowledgement(acknowledgement: str) -> None:
    environment = disposable_environment()
    environment["CONFORMLY_TEST_DATABASE_DISPOSABLE"] = acknowledgement
    with pytest.raises(UnsafePostgresTargetError):
        require_postgres_test_target(environment)


@pytest.mark.parametrize("fallback", ["CONFORMLY_DATABASE_URL", "TEST_DATABASE_URL"])
def test_never_uses_an_application_or_generic_fallback(fallback: str) -> None:
    environment = disposable_environment()
    environment[fallback] = environment.pop("CONFORMLY_TEST_APP_DATABASE_URL")
    with pytest.raises(UnsafePostgresTargetError, match="no fallback"):
        require_postgres_test_target(environment)


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///:memory:",
        "postgresql://conformly_app:test-only-sentinel@localhost:5432/conformly",
        "postgresql+psycopg://conformly_app:test-only-sentinel@remote.invalid:5432/conformly",
        "postgresql+psycopg://conformly_app:test-only-sentinel@localhost/conformly",
        "postgresql+psycopg://conformly_app:test-only-sentinel@localhost:0/conformly",
        "postgresql+psycopg://conformly_app:test-only-sentinel@localhost:99999/conformly",
        "postgresql+psycopg://conformly_app:test-only-sentinel@localhost:bad/conformly",
        "postgresql+psycopg://conformly_app:test-only-sentinel@localhost:5432/wrong",
        "postgresql+psycopg://owner:test-only-sentinel@localhost:5432/conformly",
        "postgresql+psycopg://conformly_app:test-only-sentinel@localhost:5432/conformly?host=remote.invalid",
        "postgresql+psycopg://conformly_app:test-only-sentinel@localhost:5432/conformly?service=production",
        "postgresql+psycopg://conformly_app:test-only-sentinel@localhost:5432/conformly#fragment",
        "postgresql+psycopg://conformly_app:test-only-sentinel@[broken:5432/conformly",
        "\npostgresql+psycopg://conformly_app:test-only-sentinel@localhost:5432/conformly",
    ],
    ids=[
        "sqlite",
        "wrong-driver",
        "remote",
        "no-port",
        "zero-port",
        "large-port",
        "bad-port",
        "wrong-database",
        "wrong-role",
        "host-override",
        "service-override",
        "fragment",
        "invalid-ipv6",
        "control-character",
    ],
)
def test_rejects_unsafe_or_ambiguous_urls_without_echoing_them(url: str) -> None:
    environment = disposable_environment()
    environment["CONFORMLY_TEST_APP_DATABASE_URL"] = url
    with pytest.raises(UnsafePostgresTargetError) as failure:
        require_postgres_test_target(environment)
    assert "test-only-sentinel" not in str(failure.value)
    assert url not in str(failure.value)
    assert failure.value.__suppress_context__ or failure.value.__context__ is None


@pytest.mark.parametrize("host", ["127.0.0.1", "[::1]"])
def test_accepts_explicit_loopback_literals(host: str) -> None:
    environment = disposable_environment()
    environment["CONFORMLY_TEST_APP_DATABASE_URL"] = (
        f"postgresql+psycopg://conformly_app:encoded%40password@{host}:15432/conformly"
    )
    target = require_postgres_test_target(environment)
    assert target.password == "encoded@password"
    assert target.port == 15432


@pytest.mark.parametrize(
    "key", ["PGHOST", "PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS", "PGPASSWORD"]
)
def test_rejects_libpq_environment_overrides(key: str) -> None:
    environment = disposable_environment()
    environment[key] = "test-only-sentinel"
    with pytest.raises(UnsafePostgresTargetError, match="overrides"):
        require_postgres_test_target(environment)


@pytest.mark.parametrize("key", list(safe_identity()))
def test_missing_preflight_fields_fail_closed(key: str) -> None:
    observed = safe_identity()
    del observed[key]
    with pytest.raises(UnsafePostgresTargetError):
        require_safe_runtime_identity(
            require_postgres_test_target(disposable_environment()), observed
        )


@pytest.mark.parametrize("key", [key for key, value in safe_identity().items() if value is False])
@pytest.mark.parametrize("value", [True, None, "false", 0])
def test_privileged_or_unverifiable_runtime_flags_are_denied(key: str, value: object) -> None:
    observed = safe_identity()
    observed[key] = value
    with pytest.raises(UnsafePostgresTargetError):
        require_safe_runtime_identity(
            require_postgres_test_target(disposable_environment()), observed
        )


@pytest.mark.parametrize("key", ["database_name", "runtime_role", "login_role", "row_security"])
def test_runtime_identity_or_rls_mismatch_is_denied(key: str) -> None:
    observed = safe_identity()
    observed[key] = "different"
    with pytest.raises(UnsafePostgresTargetError):
        require_safe_runtime_identity(
            require_postgres_test_target(disposable_environment()), observed
        )


def test_url_password_is_not_part_of_target_identity() -> None:
    target = require_postgres_test_target(disposable_environment())
    assert isinstance(target, PostgresTestTarget)
    require_safe_runtime_identity(
        replace(target, password="another-test-only-value"), safe_identity()
    )
