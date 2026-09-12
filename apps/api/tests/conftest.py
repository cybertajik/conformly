import base64
import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.db.base import Base
import conformly.identity.models  # noqa: F401
import conformly.organization.models  # noqa: F401
import conformly.entitlements.models  # noqa: F401
import conformly.risks.models  # noqa: F401
import conformly.assets.models  # noqa: F401
import conformly.vendors.models  # noqa: F401
import conformly.audit.models  # noqa: F401
import conformly.compliance.models  # noqa: F401
import conformly.frameworks.models  # noqa: F401
import conformly.storage.models  # noqa: F401
import conformly.preaudit.models  # noqa: F401
import conformly.profiles.models  # noqa: F401
import conformly.retention.models  # noqa: F401
import conformly.exports.models  # noqa: F401
import conformly.whistleblower.models  # noqa: F401


@pytest.fixture
def test_codec() -> EncryptedFieldCodec:
    raw_key = os.urandom(32)
    b64_key = base64.b64encode(raw_key).decode("ascii")
    envelope = EnvelopeEncryptionService(
        AES256GCMProvider(), LocalKeyManagementProvider({"v1": b64_key}, "v1")
    )
    return EncryptedFieldCodec(envelope)


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
