import inspect
import os
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from tests import conftest
from tests.test_postgres_target_safety import disposable_environment, safe_identity


@pytest.fixture
def admitted_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("PG") or key.startswith("CONFORMLY_TEST_"):
            monkeypatch.delenv(key)
    for key, value in disposable_environment().items():
        monkeypatch.setenv(key, value)


def mocked_engine(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock, MagicMock]:
    factory = MagicMock()
    engine = factory.return_value
    connection = engine.connect.return_value
    connection.execute.return_value.mappings.return_value.one.return_value = safe_identity()
    monkeypatch.setattr(conftest, "create_engine", factory)
    return factory, engine, connection


def test_missing_configuration_fails_before_engine_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CONFORMLY_TEST_APP_DATABASE_URL", raising=False)
    factory, _, _ = mocked_engine(monkeypatch)
    generator = inspect.unwrap(conftest.postgres_connection)()
    with pytest.raises(pytest.fail.Exception, match="admission failed"):
        next(generator)
    factory.assert_not_called()


def test_readonly_preflight_precedes_yield_and_resources_close(
    admitted_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory, engine, connection = mocked_engine(monkeypatch)
    generator = inspect.unwrap(conftest.postgres_connection)()
    assert next(generator) is connection
    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert statements[0] == "SET TRANSACTION READ ONLY"
    assert len(statements) == 2
    connection.begin.return_value.__exit__.assert_called_once()
    url = factory.call_args.args[0]
    assert url.host == "127.0.0.1"
    assert url.database == "conformly"
    assert factory.call_args.kwargs["connect_args"] == {"connect_timeout": 5}
    generator.close()
    connection.close.assert_called_once()
    engine.dispose.assert_called_once()


def test_privileged_role_never_yields_a_fixture_connection(
    admitted_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, engine, connection = mocked_engine(monkeypatch)
    identity = safe_identity()
    identity["owns_relations"] = True
    connection.execute.return_value.mappings.return_value.one.return_value = identity
    with pytest.raises(pytest.fail.Exception, match="admission failed"):
        next(inspect.unwrap(conftest.postgres_connection)())
    connection.close.assert_called_once()
    engine.dispose.assert_called_once()


@pytest.mark.parametrize(
    "driver_error",
    [OperationalError("", {}, RuntimeError("test-only-secret")), ValueError("test-only-secret")],
    ids=["sqlalchemy-error", "driver-value-error"],
)
def test_connection_error_is_sanitized_and_engine_disposed(
    admitted_environment: None, monkeypatch: pytest.MonkeyPatch, driver_error: Exception
) -> None:
    _, engine, _ = mocked_engine(monkeypatch)
    engine.connect.side_effect = driver_error
    with pytest.raises(pytest.fail.Exception) as failure:
        next(inspect.unwrap(conftest.postgres_connection)())
    assert "test-only-secret" not in str(failure.value)
    assert failure.value.pytrace is False
    assert failure.value.__suppress_context__ is True
    engine.dispose.assert_called_once()


def test_admission_cleanup_failure_does_not_expose_driver_error(
    admitted_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, engine, connection = mocked_engine(monkeypatch)
    connection.execute.side_effect = OperationalError("", {}, RuntimeError("query-secret"))
    connection.close.side_effect = OperationalError("", {}, RuntimeError("close-secret"))
    with pytest.raises(pytest.fail.Exception) as failure:
        next(inspect.unwrap(conftest.postgres_connection)())
    assert failure.value.__suppress_context__ is True
    assert "secret" not in str(failure.value)
    engine.dispose.assert_called_once()
