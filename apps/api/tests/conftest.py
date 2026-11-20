import base64
import os
from collections.abc import Generator
from contextlib import suppress

import pytest
from sqlalchemy import URL, Connection, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool, StaticPool

from tests.postgres_test_target import (
    RUNTIME_IDENTITY_SQL,
    require_postgres_test_target,
    require_safe_runtime_identity,
)

# Ensure test development KEKs are available for all envelope encryption services
if "CONFORMLY_LOCAL_KEKS" not in os.environ:
    _test_key = base64.b64encode(os.urandom(32)).decode("ascii")
    os.environ["CONFORMLY_LOCAL_KEKS"] = f'{{"v1": "{_test_key}"}}'
if "CONFORMLY_ACTIVE_KEK_VERSION" not in os.environ:
    os.environ["CONFORMLY_ACTIVE_KEK_VERSION"] = "v1"

import conformly.assets.models  # noqa: F401
import conformly.audit.models  # noqa: F401
import conformly.catalog_v2.models  # noqa: F401
import conformly.compliance.models  # noqa: F401
import conformly.customer_demo.assessment_models  # noqa: F401
import conformly.customer_demo.models  # noqa: F401
import conformly.customer_demo.preaudit_models  # noqa: F401
import conformly.customer_demo.verification_models  # noqa: F401
import conformly.customer_demo.work_models  # noqa: F401
import conformly.entitlements.models  # noqa: F401
import conformly.exports.models  # noqa: F401
import conformly.frameworks.models  # noqa: F401
import conformly.identity.models  # noqa: F401
import conformly.notifications.models  # noqa: F401
import conformly.organization.models  # noqa: F401
import conformly.preaudit.models  # noqa: F401
import conformly.profiles.models  # noqa: F401
import conformly.retention.models  # noqa: F401
import conformly.risks.models  # noqa: F401
import conformly.storage.models  # noqa: F401
import conformly.vendors.models  # noqa: F401
import conformly.whistleblower.models  # noqa: F401
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.db.base import Base


@pytest.fixture
def test_codec() -> EncryptedFieldCodec:
    raw_key = os.urandom(32)
    b64_key = base64.b64encode(raw_key).decode("ascii")
    envelope = EnvelopeEncryptionService(
        AES256GCMProvider(), LocalKeyManagementProvider({"v1": b64_key}, "v1")
    )
    return EncryptedFieldCodec(envelope)


@pytest.fixture
def postgres_connection() -> Generator[Connection, None, None]:
    """Admit only an explicitly disposable local runtime-role target, then yield it."""
    __tracebackhide__ = True
    engine = None
    connection = None
    try:
        target = require_postgres_test_target(os.environ)
        engine = create_engine(
            URL.create(
                "postgresql+psycopg",
                username=target.role,
                password=target.password,
                host=target.host,
                port=target.port,
                database=target.database,
            ),
            poolclass=NullPool,
            hide_parameters=True,
            connect_args={"connect_timeout": 5},
        )
        connection = engine.connect()
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            observed = connection.execute(text(RUNTIME_IDENTITY_SQL)).mappings().one()
            require_safe_runtime_identity(target, dict(observed))
    except (ValueError, SQLAlchemyError, OSError):
        if connection is not None:
            with suppress(SQLAlchemyError, OSError):
                connection.close()
        if engine is not None:
            with suppress(SQLAlchemyError, OSError):
                engine.dispose()
        raise pytest.fail.Exception(
            "PostgreSQL test target admission failed. Check the dedicated disposable-test "
            "configuration, runtime role, and harness runbook; no fixture writes were allowed.",
            pytrace=False,
        ) from None
    try:
        yield connection
    finally:
        try:
            connection.close()
        finally:
            engine.dispose()


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
