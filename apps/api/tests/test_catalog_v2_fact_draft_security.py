"""Security, admission, privilege, and audit probes for WP-07D FactDefinition authoring."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogActorKind,
    CatalogCapability,
    CatalogSecurityError,
)
from conformly.catalog_v2.models import (
    CatalogAuditEvent,
    CatalogEventIntent,
    CatalogMutationReceipt,
)
from conformly.catalog_v2.service_fact_definitions import (
    ADVISORY_LOCK_ID,
    FACT_DEFINITION_DRAFT_CHAIN_KEY,
    SERVICE_POSTGRES_ROLE,
    UNKNOWN_SYSTEM_ACTOR_ID,
    CatalogFactDefinitionDraftService,
)
from conformly.db.base import Base

REAL_ADMISSION_GUARD = CatalogFactDefinitionDraftService._verify_postgres_connection_admission


@pytest.fixture(autouse=True)
def stub_postgres_admission_for_sqlite_fixture(monkeypatch):
    """Pure validation/unit tests on in-memory SQLite explicitly stub connection admission.
    Negative tests for the admission guard explicitly invoke the real guard."""
    monkeypatch.setattr(
        CatalogFactDefinitionDraftService,
        "_verify_postgres_connection_admission",
        lambda self: None,
    )


class SecurityProbeDeniedAuditSink:
    """Audit sink to capture security denial events."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record_denial(
        self,
        actor_id: UUID,
        operation: str,
        reason_code: str,
        request_key: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.records.append(
            {
                "actor_id": actor_id,
                "operation": operation,
                "reason_code": reason_code,
                "request_key": request_key,
                "resource_type": resource_type,
                "resource_id": resource_id,
            }
        )


@pytest.fixture
def sqlite_session():
    """In-memory SQLite session with initialized catalog schema."""
    engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def valid_boolean_payload():
    return {
        "allowed_scopes": [{"scope_type": "tenant", "sequence": 1}],
        "collection_guidance": None,
        "description": "Security probe boolean fact.",
        "effective_from": None,
        "effective_until": None,
        "enum_values": [],
        "fact_definition_id": "00000000-0000-0000-0000-000000000001",
        "fact_key": "synthetic_security_probe",
        "kind": "FactDefinitionVersion",
        "label": "Security Probe",
        "predecessor_id": None,
        "predecessor_revision": None,
        "revision": 1,
        "sensitivity": "Internal",
        "status": "Draft",
        "value_type": "boolean",
        "version_label": "1.0.0",
    }


def test_advisory_lock_signed_bigint_derivation():
    """Advisory lock bigint must match exact first 8 bytes of sha256(b'conformly:fact-definition-draft-v1')."""
    expected = int.from_bytes(
        hashlib.sha256(b"conformly:fact-definition-draft-v1").digest()[:8],
        "big",
        signed=True,
    )
    assert ADVISORY_LOCK_ID == expected
    assert ADVISORY_LOCK_ID == -1797528873377602211


# ---------------------------------------------------------------------------
# Actor Admission Tests
# ---------------------------------------------------------------------------


def test_missing_or_invalid_actor_context_denied(sqlite_session, valid_boolean_payload):
    """Missing or non-CatalogActorContext actor fails closed and records UNKNOWN_SYSTEM_ACTOR_ID."""
    sink = SecurityProbeDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_audit_sink=sink)

    # 1. None context
    with pytest.raises(CatalogSecurityError):
        service.create_fact_definition_draft(
            None,  # type: ignore
            "req-no-actor",
            version_id=uuid4(),
            content_digest=b"0" * 32,
            payload=valid_boolean_payload,
        )
    assert len(sink.records) == 1
    assert sink.records[0]["actor_id"] == UNKNOWN_SYSTEM_ACTOR_ID
    assert sink.records[0]["reason_code"] == "CatalogSecurityError"

    # 2. Arbitrary dict context (not CatalogActorContext)
    with pytest.raises(CatalogSecurityError):
        service.create_fact_definition_draft(
            {"role": "admin"},  # type: ignore
            "req-dict-actor",
            version_id=uuid4(),
            content_digest=b"0" * 32,
            payload=valid_boolean_payload,
        )
    assert len(sink.records) == 2
    assert sink.records[1]["actor_id"] == UNKNOWN_SYSTEM_ACTOR_ID


def test_actor_missing_platform_admin_or_mfa(sqlite_session, valid_boolean_payload):
    """Actors without platform admin status or verified MFA are rejected."""
    sink = SecurityProbeDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_audit_sink=sink)
    actor_id = uuid4()

    # Non-admin actor
    non_admin = CatalogActorContext(
        actor_id=actor_id,
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=False,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE}),
        authenticated_at=datetime.now(UTC),
    )
    with pytest.raises(CatalogSecurityError, match="Platform admin status required"):
        service.create_fact_definition_draft(
            non_admin,
            "req-non-admin",
            version_id=uuid4(),
            content_digest=b"0" * 32,
            payload=valid_boolean_payload,
        )
    assert sink.records[-1]["actor_id"] == actor_id

    # Unverified MFA actor
    unverified_mfa = CatalogActorContext(
        actor_id=actor_id,
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=False,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE}),
        authenticated_at=datetime.now(UTC),
    )
    with pytest.raises(CatalogSecurityError, match="Verified MFA required"):
        service.create_fact_definition_draft(
            unverified_mfa,
            "req-no-mfa",
            version_id=uuid4(),
            content_digest=b"0" * 32,
            payload=valid_boolean_payload,
        )


def test_actor_missing_capabilities(sqlite_session, valid_boolean_payload):
    """Actors missing DRAFT_WRITE (for creation) or DRAFT_READ (for read) are rejected."""
    sink = SecurityProbeDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_audit_sink=sink)
    actor_id = uuid4()

    # Read-only actor attempting write
    read_only_actor = CatalogActorContext(
        actor_id=actor_id,
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_READ}),
        authenticated_at=datetime.now(UTC),
    )
    with pytest.raises(CatalogSecurityError, match="Missing required capability: DRAFT_WRITE"):
        service.create_fact_definition_draft(
            read_only_actor,
            "req-ro-write",
            version_id=uuid4(),
            content_digest=b"0" * 32,
            payload=valid_boolean_payload,
        )

    # Write-only actor attempting read
    write_only_actor = CatalogActorContext(
        actor_id=actor_id,
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE}),
        authenticated_at=datetime.now(UTC),
    )
    with pytest.raises(CatalogSecurityError, match="Missing required capability: DRAFT_READ"):
        service.get_fact_definition_version(write_only_actor, "req-wo-read", version_id=uuid4())


def test_actor_authentication_expiration_and_future_skew(sqlite_session, valid_boolean_payload):
    """Authentication older than 900 seconds or in the future (>5s) is rejected."""
    sink = SecurityProbeDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_audit_sink=sink)
    now = datetime.now(UTC)

    # Stale authentication (> 900s)
    stale_actor = CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE}),
        authenticated_at=now - timedelta(seconds=905),
    )
    with pytest.raises(
        CatalogSecurityError, match="Authentication expired: age exceeds 15 minutes"
    ):
        service.create_fact_definition_draft(
            stale_actor,
            "req-stale",
            version_id=uuid4(),
            content_digest=b"0" * 32,
            payload=valid_boolean_payload,
        )

    # Future authentication (> 5s)
    future_actor = CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE}),
        authenticated_at=now + timedelta(seconds=15),
    )
    with pytest.raises(
        CatalogSecurityError, match="Authentication timestamp cannot be in the future"
    ):
        service.create_fact_definition_draft(
            future_actor,
            "req-future",
            version_id=uuid4(),
            content_digest=b"0" * 32,
            payload=valid_boolean_payload,
        )


# ---------------------------------------------------------------------------
# PostgreSQL Connection Role Admission Tests (Mocked Verification)
# ---------------------------------------------------------------------------


def test_postgres_connection_admission_enforcement():
    """Service rejects wrong session_user, current_user, elevated attributes, or memberships."""
    mock_session = MagicMock(spec=Session)
    mock_bind = MagicMock()
    mock_bind.dialect.name = "postgresql"
    mock_session.bind = mock_bind

    service = CatalogFactDefinitionDraftService(mock_session)

    def _make_res(val):
        m = MagicMock()
        m.one.return_value = val
        m.scalar.return_value = val
        return m

    # 1. Wrong session_user / current_user
    mock_session.execute.side_effect = None
    mock_session.execute.return_value.one.return_value = ("conformly_app", "conformly_app")
    with pytest.raises(CatalogSecurityError, match="Unauthorized database connection role"):
        REAL_ADMISSION_GUARD(service)

    # 2. SET ROLE mismatch (session_user=conformly_catalog_fact_author, current_user=postgres)
    mock_session.execute.side_effect = None
    mock_session.execute.return_value.one.return_value = (
        SERVICE_POSTGRES_ROLE,
        "postgres",
    )
    with pytest.raises(CatalogSecurityError, match="Unauthorized database connection role"):
        REAL_ADMISSION_GUARD(service)

    # 3. Correct role names, but elevated attributes (rolsuper=True)
    mock_session.execute.side_effect = [
        _make_res((SERVICE_POSTGRES_ROLE, SERVICE_POSTGRES_ROLE)),  # users
        _make_res((True, False, False, False, False, False)),  # rolflags
    ]
    with pytest.raises(CatalogSecurityError, match="possesses elevated privileges"):
        REAL_ADMISSION_GUARD(service)

    # 3b. Elevated rolreplication=True
    mock_session.execute.side_effect = [
        _make_res((SERVICE_POSTGRES_ROLE, SERVICE_POSTGRES_ROLE)),  # users
        _make_res((False, False, False, False, False, True)),  # rolflags
    ]
    with pytest.raises(CatalogSecurityError, match="possesses elevated privileges"):
        REAL_ADMISSION_GUARD(service)

    # 4. Correct role names, but unexpected memberships
    mock_session.execute.side_effect = [
        _make_res((SERVICE_POSTGRES_ROLE, SERVICE_POSTGRES_ROLE)),  # users
        _make_res((False, False, False, False, False, False)),  # rolflags
        _make_res(1),  # membership count
    ]
    with pytest.raises(CatalogSecurityError, match="unexpected memberships"):
        REAL_ADMISSION_GUARD(service)

    # 5. Correct role names, but schema CREATE privilege
    mock_session.execute.side_effect = [
        _make_res((SERVICE_POSTGRES_ROLE, SERVICE_POSTGRES_ROLE)),  # users
        _make_res((False, False, False, False, False, False)),  # rolflags
        _make_res(0),  # membership count
        _make_res(True),  # has_create
    ]
    with pytest.raises(
        CatalogSecurityError, match="unauthorized CREATE privilege on public schema"
    ):
        REAL_ADMISSION_GUARD(service)

    # 6. Correct role names, but object ownership
    mock_session.execute.side_effect = [
        _make_res((SERVICE_POSTGRES_ROLE, SERVICE_POSTGRES_ROLE)),  # users
        _make_res((False, False, False, False, False, False)),  # rolflags
        _make_res(0),  # membership count
        _make_res(False),  # has_create
        _make_res(2),  # owned objects
    ]
    with pytest.raises(CatalogSecurityError, match="owns 2 persistent database objects"):
        REAL_ADMISSION_GUARD(service)

    # 7. Safe role: all checks pass
    mock_session.execute.side_effect = [
        _make_res((SERVICE_POSTGRES_ROLE, SERVICE_POSTGRES_ROLE)),  # users
        _make_res((False, False, False, False, False, False)),  # rolflags
        _make_res(0),  # membership count
        _make_res(False),  # has_create
        _make_res(0),  # owned objects
    ]
    REAL_ADMISSION_GUARD(service)  # No exception raised


# ---------------------------------------------------------------------------
# Dedicated Audit Chain & Mutation Receipt Security Invariants
# ---------------------------------------------------------------------------


def test_dedicated_audit_chain_and_receipt_invariants(sqlite_session, valid_boolean_payload):
    """Creates write only to fact-definition-draft-v1 chain and FactDefinitionVersion receipts."""
    from conformly.catalog_v2.digest import compute_content_digest

    service = CatalogFactDefinitionDraftService(sqlite_session)
    actor = CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
        authenticated_at=datetime.now(UTC),
    )

    ver_id = uuid4()
    digest = compute_content_digest(valid_boolean_payload)

    service.create_fact_definition_draft(
        actor,
        "req-chain-verify",
        version_id=ver_id,
        content_digest=digest,
        payload=valid_boolean_payload,
    )

    # 1. Audit events are isolated to fact-definition-draft-v1
    audit_events = (
        sqlite_session.execute(
            select(CatalogAuditEvent).where(CatalogAuditEvent.resource_id == ver_id)
        )
        .scalars()
        .all()
    )
    assert len(audit_events) == 1
    assert audit_events[0].chain_key == FACT_DEFINITION_DRAFT_CHAIN_KEY

    # 2. Mutation receipts are isolated to FactDefinitionVersion
    receipts = (
        sqlite_session.execute(
            select(CatalogMutationReceipt).where(CatalogMutationReceipt.result_id == ver_id)
        )
        .scalars()
        .all()
    )
    assert len(receipts) == 1
    assert receipts[0].operation == "fact_definition.create_draft"
    assert receipts[0].result_type == "FactDefinitionVersion"

    # 3. Event intents are isolated to FactDefinitionVersion and FactDefinitionDraftCreated
    intents = (
        sqlite_session.execute(
            select(CatalogEventIntent).where(CatalogEventIntent.aggregate_id == ver_id)
        )
        .scalars()
        .all()
    )
    assert len(intents) == 1
    assert intents[0].aggregate_type == "FactDefinitionVersion"
    assert intents[0].event_kind == "FactDefinitionDraftCreated"

    # 4. Reading via get_fact_definition_version adds an audit event but NO receipts or intents
    receipts_before = len(sqlite_session.execute(select(CatalogMutationReceipt)).scalars().all())
    intents_before = len(sqlite_session.execute(select(CatalogEventIntent)).scalars().all())

    service.get_fact_definition_version(actor, "read-audit-only", ver_id)

    read_audits = (
        sqlite_session.execute(
            select(CatalogAuditEvent).where(
                CatalogAuditEvent.resource_id == ver_id,
                CatalogAuditEvent.action == "fact_definition.get_draft",
            )
        )
        .scalars()
        .all()
    )
    assert len(read_audits) == 1
    assert read_audits[0].chain_key == FACT_DEFINITION_DRAFT_CHAIN_KEY

    # Receipts and intents counts unchanged
    all_receipts = sqlite_session.execute(select(CatalogMutationReceipt)).scalars().all()
    all_intents = sqlite_session.execute(select(CatalogEventIntent)).scalars().all()
    assert len(all_receipts) == receipts_before == 1
    assert len(all_intents) == intents_before == 1


# ---------------------------------------------------------------------------
# R1 & R2 Consolidated Repair 1 Regression Tests
# ---------------------------------------------------------------------------


def test_admission_guard_rejects_unbound_and_non_postgres_sessions():
    """R1: Admission guard fails closed on unbound or non-PostgreSQL connections."""
    # 1. Unbound session
    unbound_session = MagicMock(spec=Session)
    unbound_session.bind = None
    unbound_session.is_active = True
    unbound_session.dirty = set()
    unbound_session.new = set()
    unbound_session.deleted = set()

    s1 = CatalogFactDefinitionDraftService(unbound_session)
    with pytest.raises(CatalogSecurityError, match="Unbound session: database connection required"):
        REAL_ADMISSION_GUARD(s1)

    # 2. Non-PostgreSQL dialect (SQLite)
    sqlite_mock_session = MagicMock(spec=Session)
    mock_bind = MagicMock()
    mock_bind.dialect.name = "sqlite"
    sqlite_mock_session.bind = mock_bind
    sqlite_mock_session.is_active = True
    sqlite_mock_session.dirty = set()
    sqlite_mock_session.new = set()
    sqlite_mock_session.deleted = set()

    s2 = CatalogFactDefinitionDraftService(sqlite_mock_session)
    with pytest.raises(
        CatalogSecurityError, match="Unsupported database dialect 'sqlite': PostgreSQL required"
    ):
        REAL_ADMISSION_GUARD(s2)


def test_service_initialization_rejects_dirty_unit_of_work():
    """R2: Service rejects sessions with uncommitted/dirty unit of work on initialization."""
    dirty_session = MagicMock(spec=Session)
    dirty_session.is_active = True
    dirty_session.dirty = {MagicMock()}
    dirty_session.new = set()
    dirty_session.deleted = set()

    with pytest.raises(
        CatalogSecurityError, match="Service session must start with a clean unit of work"
    ):
        CatalogFactDefinitionDraftService(dirty_session)


def test_service_rejects_conflicting_schema_translate_map():
    """R2: Service rejects sessions with conflicting non-public schema translate map."""
    session = MagicMock(spec=Session)
    session.is_active = True
    session.dirty = set()
    session.new = set()
    session.deleted = set()
    mock_bind = MagicMock()
    mock_bind.dialect.name = "postgresql"
    session.bind = mock_bind

    mock_conn = MagicMock()
    mock_conn.get_execution_options.return_value = {
        "schema_translate_map": {None: "tenant_isolated_schema"}
    }
    session.connection.return_value = mock_conn

    service = CatalogFactDefinitionDraftService(session)

    with pytest.raises(
        CatalogSecurityError, match="Conflicting schema_translate_map on session connection"
    ):
        service._ensure_schema_translation()
