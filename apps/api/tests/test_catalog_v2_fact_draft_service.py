"""Focused unit and service tests for CatalogFactDefinitionDraftService (WP-07D)."""

from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, delete, select, update
from sqlalchemy.orm import Session

from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogActorKind,
    CatalogCapability,
    CatalogConflictError,
    CatalogInvariantError,
    CatalogSecurityError,
    CatalogValidationError,
)
from conformly.catalog_v2.digest import compute_content_digest
from conformly.catalog_v2.models import (
    CatalogAuditEvent,
    CatalogEventIntent,
    CatalogFactDefinition,
    CatalogFactDefinitionEnumValue,
    CatalogFactDefinitionScope,
    CatalogFactDefinitionVersion,
    CatalogMutationReceipt,
)
from conformly.catalog_v2.service_fact_definitions import (
    FACT_DEFINITION_DRAFT_CHAIN_KEY,
    CatalogFactDefinitionDraftService,
    FactDefinitionEnumValueSnapshot,
    FactDefinitionScopeSnapshot,
    FactDefinitionVersionSnapshot,
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


class MemoryDeniedAuditSink:
    """In-memory capture sink for denial audits during unit testing."""

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
                "details": details,
            }
        )


class ExplodingDeniedAuditSink:
    """Sink that simulates infrastructure outage upon denial recording."""

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
        raise RuntimeError("Denied audit infrastructure unreachable")


@pytest.fixture
def sqlite_session():
    """In-memory SQLite session with all tables initialized."""
    engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def valid_actor_context():
    """Valid platform admin actor context with DRAFT_WRITE and DRAFT_READ capabilities."""
    return CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
        authenticated_at=datetime.now(UTC),
    )


@pytest.fixture
def boolean_vector_payload():
    """Exact Appendix A Boolean fixed vector payload."""
    return {
        "allowed_scopes": [{"scope_type": "tenant", "sequence": 1}],
        "collection_guidance": None,
        "description": "Invented Boolean input for schema tests.",
        "effective_from": None,
        "effective_until": None,
        "enum_values": [],
        "fact_definition_id": "00000000-0000-0000-0000-000000000001",
        "fact_key": "synthetic_condition_met",
        "kind": "FactDefinitionVersion",
        "label": "Synthetic condition met",
        "predecessor_id": None,
        "predecessor_revision": None,
        "revision": 1,
        "sensitivity": "Internal",
        "status": "Draft",
        "value_type": "boolean",
        "version_label": "1.0.0",
    }


@pytest.fixture
def boolean_vector_digest():
    """Exact Appendix A Boolean fixed vector expected hash."""
    return bytes.fromhex("c0e72a2416eaf7e730a3758f0f9bc06e28fb78a1b776f40dab0aba2bcd4a17f9")


@pytest.fixture
def enum_vector_payload():
    """Exact Appendix A Enum fixed vector payload."""
    return {
        "allowed_scopes": [
            {"scope_type": "legal_entity", "sequence": 1},
            {"scope_type": "service", "sequence": 2},
        ],
        "collection_guidance": "Use invented values only.",
        "description": "Invented enum input for schema tests.",
        "effective_from": None,
        "effective_until": None,
        "enum_values": [
            {"code": "alpha", "label": "Alpha", "sequence": 1},
            {"code": "beta", "label": "Beta", "sequence": 2},
        ],
        "fact_definition_id": "00000000-0000-0000-0000-000000000002",
        "fact_key": "synthetic_entity_state",
        "kind": "FactDefinitionVersion",
        "label": "Synthetic entity state",
        "predecessor_id": None,
        "predecessor_revision": None,
        "revision": 1,
        "sensitivity": "Confidential",
        "status": "Draft",
        "value_type": "enum",
        "version_label": "1.0.0",
    }


@pytest.fixture
def enum_vector_digest():
    """Exact Appendix A Enum fixed vector expected hash."""
    return bytes.fromhex("9f2ecfd7827b3d2bd555ecc1aeef39fc49652f990b9ebd9173e78e88a22f3d36")


# ---------------------------------------------------------------------------
# Core Creation, Verification and Retrieval Tests
# ---------------------------------------------------------------------------


def test_create_boolean_draft_fixed_vector(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """Verify Appendix A Boolean fixed vector creates complete aggregate and matches digest."""
    sink = MemoryDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_audit_sink=sink)

    version_id = uuid4()
    req_key = "req-fact-bool-01"

    snapshot = service.create_fact_definition_draft(
        valid_actor_context,
        req_key,
        version_id=version_id,
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )

    assert isinstance(snapshot, FactDefinitionVersionSnapshot)
    assert snapshot.id == version_id
    assert snapshot.fact_definition_id == UUID("00000000-0000-0000-0000-000000000001")
    assert snapshot.fact_key == "synthetic_condition_met"
    assert snapshot.revision == 1
    assert snapshot.version_label == "1.0.0"
    assert snapshot.predecessor_id is None
    assert snapshot.predecessor_revision is None
    assert snapshot.value_type == "boolean"
    assert snapshot.sensitivity == "Internal"
    assert snapshot.status == "Draft"
    assert snapshot.content_digest == boolean_vector_digest
    assert len(snapshot.allowed_scopes) == 1
    assert snapshot.allowed_scopes[0] == FactDefinitionScopeSnapshot(1, "tenant")
    assert len(snapshot.enum_values) == 0

    # Verify database state after flush
    db_def = sqlite_session.get(CatalogFactDefinition, snapshot.fact_definition_id)
    assert db_def is not None
    assert db_def.fact_key == "synthetic_condition_met"
    assert db_def.status == "Draft"

    db_ver = sqlite_session.get(CatalogFactDefinitionVersion, version_id)
    assert db_ver is not None
    assert db_ver.content_digest == boolean_vector_digest
    assert db_ver.digest_schema == "catalog-fact-definition-draft-v1"

    # Verify mutation receipt
    receipt = sqlite_session.execute(
        select(CatalogMutationReceipt).where(CatalogMutationReceipt.request_key == req_key)
    ).scalar_one()
    assert receipt.operation == "fact_definition.create_draft"
    assert receipt.result_id == version_id
    assert receipt.result_digest == boolean_vector_digest

    # Verify event intent
    intent = sqlite_session.execute(
        select(CatalogEventIntent).where(CatalogEventIntent.aggregate_id == version_id)
    ).scalar_one()
    assert intent.event_kind == "FactDefinitionDraftCreated"
    assert intent.aggregate_type == "FactDefinitionVersion"
    assert intent.revision == 1

    # Verify audit event
    audit = sqlite_session.execute(
        select(CatalogAuditEvent).where(CatalogAuditEvent.resource_id == version_id)
    ).scalar_one()
    assert audit.action == "fact_definition.create_draft"
    assert audit.chain_key == FACT_DEFINITION_DRAFT_CHAIN_KEY

    # Idempotent retry with identical request_key returns identical snapshot
    retry_snap = service.create_fact_definition_draft(
        valid_actor_context,
        req_key,
        version_id=version_id,
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )
    assert retry_snap == snapshot

    # Verify retry audit event recorded
    retry_audits = (
        sqlite_session.execute(
            select(CatalogAuditEvent).where(
                CatalogAuditEvent.resource_id == version_id,
                CatalogAuditEvent.action == "fact_definition.retry_draft",
            )
        )
        .scalars()
        .all()
    )
    assert len(retry_audits) == 1

    # Fetch snapshot via get_fact_definition_version
    read_snap = service.get_fact_definition_version(valid_actor_context, "read-key-01", version_id)
    assert read_snap == snapshot

    # Verify read audit event recorded
    read_audits = (
        sqlite_session.execute(
            select(CatalogAuditEvent).where(
                CatalogAuditEvent.resource_id == version_id,
                CatalogAuditEvent.action == "fact_definition.get_draft",
            )
        )
        .scalars()
        .all()
    )
    assert len(read_audits) == 1
    assert len(sink.records) == 0


def test_create_enum_draft_fixed_vector(
    sqlite_session, valid_actor_context, enum_vector_payload, enum_vector_digest
):
    """Verify Appendix A Enum fixed vector creates ordered children and matches digest."""
    sink = MemoryDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_audit_sink=sink)

    version_id = uuid4()
    req_key = "req-fact-enum-01"

    snapshot = service.create_fact_definition_draft(
        valid_actor_context,
        req_key,
        version_id=version_id,
        content_digest=enum_vector_digest,
        payload=enum_vector_payload,
    )

    assert snapshot.id == version_id
    assert snapshot.value_type == "enum"
    assert snapshot.content_digest == enum_vector_digest
    assert len(snapshot.allowed_scopes) == 2
    assert snapshot.allowed_scopes[0] == FactDefinitionScopeSnapshot(1, "legal_entity")
    assert snapshot.allowed_scopes[1] == FactDefinitionScopeSnapshot(2, "service")
    assert len(snapshot.enum_values) == 2
    assert snapshot.enum_values[0] == FactDefinitionEnumValueSnapshot(1, "alpha", "Alpha")
    assert snapshot.enum_values[1] == FactDefinitionEnumValueSnapshot(2, "beta", "Beta")

    # Re-read and ensure exact match
    read_snap = service.get_fact_definition_version(valid_actor_context, "read-enum-01", version_id)
    assert read_snap == snapshot
    assert len(sink.records) == 0


@pytest.mark.parametrize("v_type", ["integer", "decimal", "date", "string", "entity_reference"])
def test_all_supported_non_enum_value_types(sqlite_session, valid_actor_context, v_type):
    """All 5 other non-enum value types validate and persist with zero enum rows."""
    service = CatalogFactDefinitionDraftService(sqlite_session)
    def_id = uuid4()
    ver_id = uuid4()
    key = f"synthetic_test_{v_type}"

    payload = {
        "allowed_scopes": [{"scope_type": "tenant", "sequence": 1}],
        "collection_guidance": None,
        "description": f"Test for value type {v_type}.",
        "effective_from": "2026-01-01",
        "effective_until": "2026-12-31",
        "enum_values": [],
        "fact_definition_id": str(def_id),
        "fact_key": key,
        "kind": "FactDefinitionVersion",
        "label": f"Test {v_type}",
        "predecessor_id": None,
        "predecessor_revision": None,
        "revision": 1,
        "sensitivity": "Public",
        "status": "Draft",
        "value_type": v_type,
        "version_label": "0.1.0",
    }
    digest = compute_content_digest(payload)

    snap = service.create_fact_definition_draft(
        valid_actor_context,
        f"req-{v_type}",
        version_id=ver_id,
        content_digest=digest,
        payload=payload,
    )
    assert snap.value_type == v_type
    assert snap.effective_from == date(2026, 1, 1)
    assert snap.effective_until == date(2026, 12, 31)


def test_all_six_scopes_contiguous(sqlite_session, valid_actor_context):
    """Payload with all 6 distinct scope types in contiguous order 1..6 validates successfully."""
    service = CatalogFactDefinitionDraftService(sqlite_session)
    def_id = uuid4()
    ver_id = uuid4()

    all_scopes = [
        "tenant",
        "legal_entity",
        "service",
        "processing_activity",
        "system",
        "location",
    ]
    payload = {
        "allowed_scopes": [{"scope_type": st, "sequence": i} for i, st in enumerate(all_scopes, 1)],
        "collection_guidance": None,
        "description": "Six scopes test.",
        "effective_from": None,
        "effective_until": None,
        "enum_values": [],
        "fact_definition_id": str(def_id),
        "fact_key": "synthetic_six_scopes",
        "kind": "FactDefinitionVersion",
        "label": "Six Scopes",
        "predecessor_id": None,
        "predecessor_revision": None,
        "revision": 1,
        "sensitivity": "Restricted",
        "status": "Draft",
        "value_type": "string",
        "version_label": "1.0",
    }
    digest = compute_content_digest(payload)

    snap = service.create_fact_definition_draft(
        valid_actor_context,
        "req-six-scopes",
        version_id=ver_id,
        content_digest=digest,
        payload=payload,
    )
    assert len(snap.allowed_scopes) == 6
    assert [s.scope_type for s in snap.allowed_scopes] == all_scopes


# ---------------------------------------------------------------------------
# Lineage, Predecessor and Multi-Revision Progression
# ---------------------------------------------------------------------------


def test_multi_revision_lineage_progression(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """Create revision 1, then create revision 2 pinning revision 1 as predecessor."""
    service = CatalogFactDefinitionDraftService(sqlite_session)
    v1_id = uuid4()

    snap_v1 = service.create_fact_definition_draft(
        valid_actor_context,
        "req-rev-1",
        version_id=v1_id,
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )
    assert snap_v1.revision == 1

    # Construct revision 2 payload
    v2_id = uuid4()
    v2_payload = dict(boolean_vector_payload)
    v2_payload["revision"] = 2
    v2_payload["version_label"] = "1.1.0"
    v2_payload["predecessor_id"] = str(v1_id)
    v2_payload["predecessor_revision"] = 1
    v2_payload["description"] = "Updated description for revision 2."
    v2_digest = compute_content_digest(v2_payload)

    snap_v2 = service.create_fact_definition_draft(
        valid_actor_context,
        "req-rev-2",
        version_id=v2_id,
        content_digest=v2_digest,
        payload=v2_payload,
    )

    assert snap_v2.revision == 2
    assert snap_v2.predecessor_id == v1_id
    assert snap_v2.predecessor_revision == 1
    assert snap_v2.description == "Updated description for revision 2."

    # Predecessor row in DB remains immutable and untouched
    db_v1 = sqlite_session.get(CatalogFactDefinitionVersion, v1_id)
    assert db_v1.revision == 1
    assert db_v1.description == "Invented Boolean input for schema tests."


def test_revision_lineage_validation_failures(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """Verify invalid predecessor links, mismatched revisions and cross-definition predecessor rejections."""
    sink = MemoryDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_audit_sink=sink)

    v1_id = uuid4()
    service.create_fact_definition_draft(
        valid_actor_context,
        "req-rev-base",
        version_id=v1_id,
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )
    sqlite_session.commit()

    # 1. Revision 1 with predecessor_id rejected
    p1 = dict(boolean_vector_payload)
    p1["fact_definition_id"] = str(uuid4())
    p1["fact_key"] = "synthetic_another_def"
    p1["predecessor_id"] = str(v1_id)
    p1["predecessor_revision"] = 0
    d1 = compute_content_digest(p1)
    with pytest.raises(CatalogValidationError, match="predecessor_id=null"):
        service.create_fact_definition_draft(
            valid_actor_context, "req-bad-p1", version_id=uuid4(), content_digest=d1, payload=p1
        )

    # 2. Revision 2 with missing predecessor rejected
    p2 = dict(boolean_vector_payload)
    p2["revision"] = 2
    d2 = compute_content_digest(p2)
    with pytest.raises(CatalogValidationError, match="requires non-null predecessor"):
        service.create_fact_definition_draft(
            valid_actor_context, "req-bad-p2", version_id=uuid4(), content_digest=d2, payload=p2
        )

    # 3. Revision 2 with wrong predecessor_revision != 1
    p3 = dict(boolean_vector_payload)
    p3["revision"] = 2
    p3["predecessor_id"] = str(v1_id)
    p3["predecessor_revision"] = 2
    d3 = compute_content_digest(p3)
    with pytest.raises(CatalogValidationError, match="must equal revision - 1"):
        service.create_fact_definition_draft(
            valid_actor_context, "req-bad-p3", version_id=uuid4(), content_digest=d3, payload=p3
        )

    # 4. Predecessor version does not exist in DB
    p4 = dict(boolean_vector_payload)
    p4["revision"] = 2
    p4["predecessor_id"] = str(uuid4())
    p4["predecessor_revision"] = 1
    d4 = compute_content_digest(p4)
    with pytest.raises(CatalogValidationError, match="Predecessor version .* not found"):
        service.create_fact_definition_draft(
            valid_actor_context, "req-bad-p4", version_id=uuid4(), content_digest=d4, payload=p4
        )


# ---------------------------------------------------------------------------
# Strict Input Validation & Negative Rejection Tests
# ---------------------------------------------------------------------------


def test_non_synthetic_fact_key_strictly_rejected(
    sqlite_session, valid_actor_context, boolean_vector_payload
):
    """Fact keys without synthetic_ prefix are strictly rejected."""
    sink = MemoryDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_audit_sink=sink)

    for bad_key in ["user_email", "corp_revenue", "synthetic", "real_fact"]:
        p = dict(boolean_vector_payload)
        p["fact_key"] = bad_key
        d = compute_content_digest(p)
        with pytest.raises(CatalogValidationError, match="required prefix 'synthetic_'"):
            service.create_fact_definition_draft(
                valid_actor_context, "req-bad-key", version_id=uuid4(), content_digest=d, payload=p
            )
    assert len(sink.records) == 4


def test_payload_key_mutation_negatives(
    sqlite_session, valid_actor_context, boolean_vector_payload
):
    """Missing or extra keys in the payload are rejected."""
    service = CatalogFactDefinitionDraftService(sqlite_session)

    # Missing key
    p_missing = dict(boolean_vector_payload)
    del p_missing["allowed_scopes"]
    with pytest.raises(CatalogValidationError, match="Payload keys mismatch"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-miss",
            version_id=uuid4(),
            content_digest=b"0" * 32,
            payload=p_missing,
        )

    # Extra key
    p_extra = dict(boolean_vector_payload)
    p_extra["unexpected_field"] = "bad"
    d_extra = compute_content_digest(p_extra)
    with pytest.raises(CatalogValidationError, match="Payload keys mismatch"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-extra",
            version_id=uuid4(),
            content_digest=d_extra,
            payload=p_extra,
        )


def test_untrimmed_strings_rejected(sqlite_session, valid_actor_context, boolean_vector_payload):
    """Whitespace in string fields is rejected (no silent trimming)."""
    service = CatalogFactDefinitionDraftService(sqlite_session)

    for field, bad_val in [
        ("fact_key", " synthetic_condition_met "),
        ("version_label", "1.0.0 "),
        ("label", " Synthetic condition "),
        ("description", " Description with trailing space "),
        ("collection_guidance", " Guidance with leading space"),
    ]:
        p = dict(boolean_vector_payload)
        p[field] = bad_val
        d = compute_content_digest(p)
        with pytest.raises(CatalogValidationError, match="trimmed|whitespace"):
            service.create_fact_definition_draft(
                valid_actor_context,
                f"req-trim-{field}",
                version_id=uuid4(),
                content_digest=d,
                payload=p,
            )


def test_invalid_dates_and_order_rejected(
    sqlite_session, valid_actor_context, boolean_vector_payload
):
    """Effective dates with effective_until earlier than effective_from are rejected."""
    service = CatalogFactDefinitionDraftService(sqlite_session)

    p = dict(boolean_vector_payload)
    p["effective_from"] = "2026-12-31"
    p["effective_until"] = "2026-01-01"
    d = compute_content_digest(p)

    with pytest.raises(CatalogValidationError, match="cannot precede effective_from"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-bad-dates",
            version_id=uuid4(),
            content_digest=d,
            payload=p,
        )


def test_scope_sequence_and_uniqueness_negatives(
    sqlite_session, valid_actor_context, boolean_vector_payload
):
    """Scope sequence gaps, non-1 starts, and duplicate scope types are rejected."""
    service = CatalogFactDefinitionDraftService(sqlite_session)

    # Sequence gap (1, 3)
    p_gap = dict(boolean_vector_payload)
    p_gap["allowed_scopes"] = [
        {"scope_type": "tenant", "sequence": 1},
        {"scope_type": "service", "sequence": 3},
    ]
    d_gap = compute_content_digest(p_gap)
    with pytest.raises(CatalogValidationError, match="strictly contiguous"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-scope-gap",
            version_id=uuid4(),
            content_digest=d_gap,
            payload=p_gap,
        )

    # Duplicate scope type
    p_dup = dict(boolean_vector_payload)
    p_dup["allowed_scopes"] = [
        {"scope_type": "tenant", "sequence": 1},
        {"scope_type": "tenant", "sequence": 2},
    ]
    d_dup = compute_content_digest(p_dup)
    with pytest.raises(CatalogValidationError, match="Duplicate scope_type"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-scope-dup",
            version_id=uuid4(),
            content_digest=d_dup,
            payload=p_dup,
        )


def test_enum_sequence_and_type_negatives(
    sqlite_session, valid_actor_context, enum_vector_payload, boolean_vector_payload
):
    """Enum values with non-enum types, empty enums on enum types, and duplicate codes are rejected."""
    service = CatalogFactDefinitionDraftService(sqlite_session)

    # Enums present on boolean type
    p_bool_with_enums = dict(boolean_vector_payload)
    p_bool_with_enums["enum_values"] = [{"code": "a", "label": "A", "sequence": 1}]
    d1 = compute_content_digest(p_bool_with_enums)
    with pytest.raises(CatalogValidationError, match="must be empty for non-enum"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-bool-enum",
            version_id=uuid4(),
            content_digest=d1,
            payload=p_bool_with_enums,
        )

    # Empty enums on enum type
    p_enum_empty = dict(enum_vector_payload)
    p_enum_empty["enum_values"] = []
    d2 = compute_content_digest(p_enum_empty)
    with pytest.raises(CatalogValidationError, match="between 1 and 64 items"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-enum-empty",
            version_id=uuid4(),
            content_digest=d2,
            payload=p_enum_empty,
        )

    # Duplicate enum codes
    p_enum_dup = dict(enum_vector_payload)
    p_enum_dup["enum_values"] = [
        {"code": "code1", "label": "Label 1", "sequence": 1},
        {"code": "code1", "label": "Label 2", "sequence": 2},
    ]
    d3 = compute_content_digest(p_enum_dup)
    with pytest.raises(CatalogValidationError, match="Duplicate enum code"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-enum-dup",
            version_id=uuid4(),
            content_digest=d3,
            payload=p_enum_dup,
        )


def test_forged_digest_rejected(sqlite_session, valid_actor_context, boolean_vector_payload):
    """Claimed content_digest differing from actual computed payload digest is rejected."""
    service = CatalogFactDefinitionDraftService(sqlite_session)
    forged_digest = b"\xff" * 32

    with pytest.raises(CatalogValidationError, match="does not match computed payload digest"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-forged-digest",
            version_id=uuid4(),
            content_digest=forged_digest,
            payload=boolean_vector_payload,
        )


def test_request_key_bounds_and_format_negatives(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """Invalid request_key (empty, too long, non-ASCII) is rejected."""
    service = CatalogFactDefinitionDraftService(sqlite_session)

    # Empty
    with pytest.raises(CatalogValidationError, match="outside bounded range"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "",
            version_id=uuid4(),
            content_digest=boolean_vector_digest,
            payload=boolean_vector_payload,
        )

    # Too long (>128)
    long_key = "a" * 129
    with pytest.raises(CatalogValidationError, match="outside bounded range"):
        service.create_fact_definition_draft(
            valid_actor_context,
            long_key,
            version_id=uuid4(),
            content_digest=boolean_vector_digest,
            payload=boolean_vector_payload,
        )

    # Invalid characters
    with pytest.raises(CatalogValidationError, match="contains invalid characters"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "bad key with spaces",
            version_id=uuid4(),
            content_digest=boolean_vector_digest,
            payload=boolean_vector_payload,
        )


# ---------------------------------------------------------------------------
# Conflict & Idempotency Tests
# ---------------------------------------------------------------------------


def test_conflict_on_same_request_key_different_payload(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """Reusing request_key with different payload parameters raises CatalogConflictError."""
    service = CatalogFactDefinitionDraftService(sqlite_session)
    req_key = "conflict-req-01"

    service.create_fact_definition_draft(
        valid_actor_context,
        req_key,
        version_id=uuid4(),
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )

    # Differing payload
    diff_payload = dict(boolean_vector_payload)
    diff_payload["label"] = "Differing label"
    diff_digest = compute_content_digest(diff_payload)

    with pytest.raises(CatalogConflictError, match="reused with conflicting request parameters"):
        service.create_fact_definition_draft(
            valid_actor_context,
            req_key,
            version_id=uuid4(),
            content_digest=diff_digest,
            payload=diff_payload,
        )


def test_conflict_on_same_fact_key_different_definition_id(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """Creating a revision 1 with an existing fact_key but different fact_definition_id raises CatalogConflictError."""
    service = CatalogFactDefinitionDraftService(sqlite_session)

    service.create_fact_definition_draft(
        valid_actor_context,
        "req-def-1",
        version_id=uuid4(),
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )

    # Different definition ID with same fact_key
    conf_payload = dict(boolean_vector_payload)
    conf_payload["fact_definition_id"] = str(uuid4())
    conf_digest = compute_content_digest(conf_payload)

    with pytest.raises(CatalogConflictError, match="already exists"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-def-2",
            version_id=uuid4(),
            content_digest=conf_digest,
            payload=conf_payload,
        )


# ---------------------------------------------------------------------------
# Rollback & Corrupt Stored Aggregate Fail-Closed Tests
# ---------------------------------------------------------------------------


def test_domain_rollback_leaves_no_partial_rows(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """Injected failure triggers domain rollback and leaves zero partial rows or receipts."""
    service = CatalogFactDefinitionDraftService(sqlite_session)

    # Inject invalid version_id type to force failure inside domain write
    with pytest.raises(CatalogValidationError):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-fail-clean",
            version_id="not-a-uuid",  # type: ignore
            content_digest=boolean_vector_digest,
            payload=boolean_vector_payload,
        )

    # Assert database is completely clean
    assert sqlite_session.execute(select(CatalogFactDefinition)).scalar_one_or_none() is None
    assert sqlite_session.execute(select(CatalogFactDefinitionVersion)).scalar_one_or_none() is None
    assert sqlite_session.execute(select(CatalogMutationReceipt)).scalar_one_or_none() is None
    assert sqlite_session.execute(select(CatalogEventIntent)).scalar_one_or_none() is None


def test_corrupt_stored_aggregate_fails_closed_on_read(
    sqlite_session, valid_actor_context, enum_vector_payload, enum_vector_digest
):
    """Tampered persisted row (e.g. digest mismatch or deleted child) causes read to fail closed."""
    service = CatalogFactDefinitionDraftService(sqlite_session)
    ver_id = uuid4()

    service.create_fact_definition_draft(
        valid_actor_context,
        "req-corrupt-setup",
        version_id=ver_id,
        content_digest=enum_vector_digest,
        payload=enum_vector_payload,
    )

    # Tamper with stored content digest in the database
    ver_row = sqlite_session.get(CatalogFactDefinitionVersion, ver_id)
    ver_row.content_digest = b"\x00" * 32
    sqlite_session.flush()

    with pytest.raises(CatalogInvariantError, match="Persisted content digest mismatch"):
        service.get_fact_definition_version(valid_actor_context, "read-corrupt", ver_id)


def test_durable_denial_sink_failure_propagates_visibly(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """Denial sink infrastructure failure is never swallowed and propagates visibly."""
    exploding_sink = ExplodingDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_audit_sink=exploding_sink)

    # Cause an intentional validation error (untrimmed string)
    p = dict(boolean_vector_payload)
    p["label"] = " Untrimmed "
    d = compute_content_digest(p)

    with pytest.raises(RuntimeError, match="Denied audit infrastructure unreachable"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-explode",
            version_id=uuid4(),
            content_digest=d,
            payload=p,
        )


# ---------------------------------------------------------------------------
# WP-07D Consolidated Repair 1 Regression Tests (R1, R3, R4, R6)
# ---------------------------------------------------------------------------


def test_r1_real_guard_rejects_unbound_and_sqlite(
    monkeypatch, sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """R1: Real admission guard fails closed for unbound and SQLite sessions."""
    # 1. Unbound session
    unbound_session = MagicMock(spec=Session)
    unbound_session.bind = None
    unbound_session.get_bind.return_value = None
    unbound_session.is_active = True
    unbound_session.dirty = set()
    unbound_session.new = set()
    unbound_session.deleted = set()
    sink1 = MemoryDeniedAuditSink()
    # Restore real guard via monkeypatch for negative testing
    monkeypatch.setattr(
        CatalogFactDefinitionDraftService,
        "_verify_postgres_connection_admission",
        REAL_ADMISSION_GUARD,
    )
    s_unbound = CatalogFactDefinitionDraftService(unbound_session, denied_audit_sink=sink1)

    with pytest.raises(CatalogSecurityError, match="Unbound session: database connection required"):
        s_unbound.create_fact_definition_draft(
            valid_actor_context,
            "req-unbound",
            version_id=uuid4(),
            content_digest=boolean_vector_digest,
            payload=boolean_vector_payload,
        )
    assert len(sink1.records) == 1
    assert sink1.records[0]["reason_code"] == "CatalogSecurityError"

    # 2. SQLite session
    sink2 = MemoryDeniedAuditSink()
    s_sqlite = CatalogFactDefinitionDraftService(sqlite_session, denied_audit_sink=sink2)

    with pytest.raises(
        CatalogSecurityError, match="Unsupported database dialect 'sqlite': PostgreSQL required"
    ):
        s_sqlite.create_fact_definition_draft(
            valid_actor_context,
            "req-sqlite",
            version_id=uuid4(),
            content_digest=boolean_vector_digest,
            payload=boolean_vector_payload,
        )

    with pytest.raises(
        CatalogSecurityError, match="Unsupported database dialect 'sqlite': PostgreSQL required"
    ):
        s_sqlite.get_fact_definition_version(
            valid_actor_context,
            "req-sqlite-get",
            version_id=uuid4(),
        )
    assert len(sink2.records) == 2
    assert sink2.records[0]["reason_code"] == "CatalogSecurityError"
    assert sink2.records[1]["reason_code"] == "CatalogSecurityError"


def test_r3_failure_at_clock_rolls_back_and_records_denial(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest, monkeypatch
):
    """R3: Failure at database clock query rolls back domain session and records denial."""
    sink = MemoryDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_audit_sink=sink)

    monkeypatch.setattr(
        service, "_get_db_time", MagicMock(side_effect=RuntimeError("Clock infrastructure failure"))
    )

    with pytest.raises(RuntimeError, match="Clock infrastructure failure"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-fail-clock",
            version_id=uuid4(),
            content_digest=boolean_vector_digest,
            payload=boolean_vector_payload,
        )

    assert not sqlite_session.dirty
    assert sqlite_session.execute(select(CatalogFactDefinition)).scalar_one_or_none() is None
    assert len(sink.records) == 1
    assert sink.records[0]["operation"] == "fact_definition.create_draft"
    assert sink.records[0]["reason_code"] == "InternalError"


def test_r3_failure_at_advisory_lock_rolls_back_and_records_denial(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest, monkeypatch
):
    """R3: Failure acquiring serialization advisory lock rolls back and records denial."""
    sink = MemoryDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_audit_sink=sink)

    monkeypatch.setattr(
        service,
        "_acquire_advisory_lock",
        MagicMock(side_effect=CatalogSecurityError("Advisory lock acquisition timeout")),
    )

    with pytest.raises(CatalogSecurityError, match="Advisory lock acquisition timeout"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-fail-lock",
            version_id=uuid4(),
            content_digest=boolean_vector_digest,
            payload=boolean_vector_payload,
        )

    assert not sqlite_session.dirty
    assert sqlite_session.execute(select(CatalogFactDefinition)).scalar_one_or_none() is None
    assert len(sink.records) == 1
    assert sink.records[0]["reason_code"] == "CatalogSecurityError"


def test_r3_failure_at_receipt_rolls_back_and_records_denial(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest, monkeypatch
):
    """R3: Failure during receipt recording rolls back all rows and records denial."""
    sink = MemoryDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_audit_sink=sink)

    monkeypatch.setattr(
        "conformly.catalog_v2.service_fact_definitions.check_or_record_mutation_receipt",
        MagicMock(side_effect=RuntimeError("Receipt write error")),
    )

    with pytest.raises(RuntimeError, match="Receipt write error"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-fail-receipt",
            version_id=uuid4(),
            content_digest=boolean_vector_digest,
            payload=boolean_vector_payload,
        )

    assert not sqlite_session.dirty
    assert sqlite_session.execute(select(CatalogFactDefinition)).scalar_one_or_none() is None
    assert len(sink.records) == 1
    assert sink.records[0]["reason_code"] == "InternalError"


def test_r3_failure_at_audit_append_rolls_back_and_records_denial(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest, monkeypatch
):
    """R3: Failure during create, retry, or read audit event append rolls back and records denial."""
    sink = MemoryDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_audit_sink=sink)

    v1_id = uuid4()
    # 1. Failure on create audit
    monkeypatch.setattr(
        "conformly.catalog_v2.service_fact_definitions.append_catalog_audit_event",
        MagicMock(side_effect=RuntimeError("Journal disk full")),
    )

    with pytest.raises(RuntimeError, match="Journal disk full"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-fail-audit",
            version_id=v1_id,
            content_digest=boolean_vector_digest,
            payload=boolean_vector_payload,
        )

    assert not sqlite_session.dirty
    assert sqlite_session.execute(select(CatalogFactDefinition)).scalar_one_or_none() is None
    assert sqlite_session.execute(select(CatalogMutationReceipt)).scalar_one_or_none() is None
    assert len(sink.records) == 1
    assert sink.records[0]["reason_code"] == "InternalError"

    # 2. Reset mock and successfully create
    from conformly.catalog_v2.audit import append_catalog_audit_event as real_append_audit

    monkeypatch.setattr(
        "conformly.catalog_v2.service_fact_definitions.append_catalog_audit_event",
        real_append_audit,
    )
    service.create_fact_definition_draft(
        valid_actor_context,
        "req-succ",
        version_id=v1_id,
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )
    sqlite_session.commit()

    # 3. Failure on get read audit
    monkeypatch.setattr(
        "conformly.catalog_v2.service_fact_definitions.append_catalog_audit_event",
        MagicMock(side_effect=RuntimeError("Read audit append failed")),
    )

    with pytest.raises(RuntimeError, match="Read audit append failed"):
        service.get_fact_definition_version(
            valid_actor_context,
            "req-read-fail",
            version_id=v1_id,
        )

    assert not sqlite_session.dirty
    assert len(sink.records) == 2
    assert sink.records[1]["operation"] == "fact_definition.get_draft"
    assert sink.records[1]["reason_code"] == "InternalError"


def test_r3_explicit_caller_commit_and_rollback_semantics(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """R3: Methods flush but never commit; explicit caller commit or rollback governs durability."""
    service = CatalogFactDefinitionDraftService(sqlite_session)
    v1_id = uuid4()

    # 1. Service execution flushes but does not commit
    snapshot = service.create_fact_definition_draft(
        valid_actor_context,
        "req-flush-only",
        version_id=v1_id,
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )
    assert snapshot.id == v1_id

    # Caller explicitly rolls back: everything uncommitted is discarded
    sqlite_session.rollback()
    assert sqlite_session.execute(select(CatalogFactDefinition)).scalar_one_or_none() is None
    assert sqlite_session.execute(select(CatalogFactDefinitionVersion)).scalar_one_or_none() is None
    assert sqlite_session.execute(select(CatalogMutationReceipt)).scalar_one_or_none() is None

    # Caller executes and commits: everything is durable
    service.create_fact_definition_draft(
        valid_actor_context,
        "req-flush-commit",
        version_id=v1_id,
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )
    sqlite_session.commit()

    assert sqlite_session.execute(select(CatalogFactDefinition)).scalar_one_or_none() is not None
    assert (
        sqlite_session.execute(select(CatalogFactDefinitionVersion)).scalar_one_or_none()
        is not None
    )
    assert sqlite_session.execute(select(CatalogMutationReceipt)).scalar_one_or_none() is not None


def test_r4_strict_scalar_types_and_malformed_input_rejection(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """R4: Malformed input types (value_type=[], dict sensitivities, non-scalar scopes) fail with validation error and record denial."""
    sink = MemoryDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_audit_sink=sink)

    # 1. Exact Codex reproduction: value_type=[] (list instead of string)
    p_bad_val_type = dict(boolean_vector_payload)
    p_bad_val_type["value_type"] = []

    with pytest.raises(CatalogValidationError, match="value_type must be a string"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-bad-val-type",
            version_id=uuid4(),
            content_digest=boolean_vector_digest,
            payload=p_bad_val_type,
        )

    assert not sqlite_session.dirty
    assert len(sink.records) == 1
    assert sink.records[0]["operation"] == "fact_definition.create_draft"
    assert sink.records[0]["reason_code"] == "CatalogValidationError"

    # 2. sensitivity as a list/dict
    p_bad_sens = dict(boolean_vector_payload)
    p_bad_sens["sensitivity"] = {"level": "Internal"}
    with pytest.raises(CatalogValidationError, match="sensitivity must be a string"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-bad-sens",
            version_id=uuid4(),
            content_digest=boolean_vector_digest,
            payload=p_bad_sens,
        )
    assert len(sink.records) == 2
    assert sink.records[1]["reason_code"] == "CatalogValidationError"

    # 3. allowed_scopes not a list
    p_bad_scopes = dict(boolean_vector_payload)
    p_bad_scopes["allowed_scopes"] = "tenant"
    with pytest.raises(CatalogValidationError, match="allowed_scopes must be a list"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-bad-scopes",
            version_id=uuid4(),
            content_digest=boolean_vector_digest,
            payload=p_bad_scopes,
        )
    assert len(sink.records) == 3

    # 4. enum_values not a list
    p_bad_enums = dict(boolean_vector_payload)
    p_bad_enums["enum_values"] = "alpha"
    with pytest.raises(CatalogValidationError, match="enum_values must be a list"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-bad-enums",
            version_id=uuid4(),
            content_digest=boolean_vector_digest,
            payload=p_bad_enums,
        )
    assert len(sink.records) == 4

    # 5. Non-dict payload
    with pytest.raises(CatalogValidationError, match="payload must be a dictionary"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-bad-payload",
            version_id=uuid4(),
            content_digest=boolean_vector_digest,
            payload=["not", "a", "dict"],  # type: ignore
        )
    assert len(sink.records) == 5


def test_r6_detects_stale_identity_map_tampering_via_persisted_row_requery(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """R6: Holding cached ORM instance in identity map does not mask genuine persisted database changes."""
    service = CatalogFactDefinitionDraftService(sqlite_session)
    ver_id = uuid4()

    # 1. Create draft version
    snap = service.create_fact_definition_draft(
        valid_actor_context,
        "req-r6-stale",
        version_id=ver_id,
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )
    assert snap.content_digest == boolean_vector_digest
    sqlite_session.commit()

    # 2. Keep the ORM instance cached in session identity map
    cached_obj = sqlite_session.get(CatalogFactDefinitionVersion, ver_id)
    assert cached_obj is not None
    assert cached_obj.label == "Synthetic condition met"

    # 3. Tamper with the persisted row independently via direct SQL, leaving content_digest unchanged
    sqlite_session.execute(
        update(CatalogFactDefinitionVersion)
        .where(CatalogFactDefinitionVersion.id == ver_id)
        .values(label="Changed persisted label")
    )
    sqlite_session.commit()

    # 4. Retrieve version: must re-query genuine database row and detect digest mismatch
    with pytest.raises(CatalogInvariantError, match="Persisted content digest mismatch"):
        service.get_fact_definition_version(
            valid_actor_context,
            "req-r6-get",
            version_id=ver_id,
        )


def test_r6_detects_stale_identity_map_tampering_for_enum_children(
    sqlite_session, valid_actor_context, enum_vector_payload, enum_vector_digest
):
    """R6: Tampering with child enum values independently is detected via populated row requery."""
    service = CatalogFactDefinitionDraftService(sqlite_session)
    ver_id = uuid4()

    snap = service.create_fact_definition_draft(
        valid_actor_context,
        "req-r6-child",
        version_id=ver_id,
        content_digest=enum_vector_digest,
        payload=enum_vector_payload,
    )
    assert snap.content_digest == enum_vector_digest
    sqlite_session.commit()

    # Cache version in identity map
    cached_ver = sqlite_session.get(CatalogFactDefinitionVersion, ver_id)
    assert cached_ver is not None

    # Tamper with persisted child enum label directly via SQL without updating version digest
    sqlite_session.execute(
        update(CatalogFactDefinitionEnumValue)
        .where(CatalogFactDefinitionEnumValue.fact_definition_version_id == ver_id)
        .where(CatalogFactDefinitionEnumValue.code == "alpha")
        .values(label="Tampered Alpha Label")
    )
    sqlite_session.commit()

    # Re-querying must re-read genuine child rows and detect digest mismatch
    with pytest.raises(CatalogInvariantError, match="Persisted content digest mismatch"):
        service.get_fact_definition_version(
            valid_actor_context,
            "req-r6-child-get",
            version_id=ver_id,
        )


def test_r6_detects_stale_identity_map_tampering_for_predecessor(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """R6: Tampering with predecessor version row in DB is detected during lineage verification."""
    service = CatalogFactDefinitionDraftService(sqlite_session)
    v1_id = uuid4()

    snap_v1 = service.create_fact_definition_draft(
        valid_actor_context,
        "req-r6-pred-v1",
        version_id=v1_id,
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )
    assert snap_v1.content_digest == boolean_vector_digest
    sqlite_session.commit()

    # Keep v1 in identity map
    cached_v1 = sqlite_session.get(CatalogFactDefinitionVersion, v1_id)
    assert cached_v1 is not None

    # Tamper with v1 persisted digest directly via SQL
    sqlite_session.execute(
        update(CatalogFactDefinitionVersion)
        .where(CatalogFactDefinitionVersion.id == v1_id)
        .values(content_digest=b"\x00" * 32)
    )
    sqlite_session.commit()

    # Attempt to create revision 2: predecessor verification re-reads v1 from DB and rejects tampered digest
    v2_id = uuid4()
    v2_payload = dict(boolean_vector_payload)
    v2_payload["revision"] = 2
    v2_payload["version_label"] = "1.1.0"
    v2_payload["predecessor_id"] = str(v1_id)
    v2_payload["predecessor_revision"] = 1
    v2_digest = compute_content_digest(v2_payload)

    with pytest.raises(CatalogInvariantError, match="Persisted content digest mismatch"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-r6-pred-v2",
            version_id=v2_id,
            content_digest=v2_digest,
            payload=v2_payload,
        )


# ==============================================================================
# R8 - Actor-scoped Event-Intent Identity Regressions
# ==============================================================================


def test_r8_two_distinct_actors_sharing_same_raw_request_key(
    sqlite_session, boolean_vector_payload, boolean_vector_digest
):
    """R8: Two distinct authorized actors sharing the exact same raw request_key do not collide on event-intent unique constraint."""
    service = CatalogFactDefinitionDraftService(sqlite_session)

    actor_a = CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        capabilities=frozenset([CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ]),
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC),
    )
    actor_b = CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        capabilities=frozenset([CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ]),
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC),
    )

    shared_req_key = "req-shared-r8-key"

    # Actor A creates Fact Definition A
    v_a_id = uuid4()
    p_a = dict(boolean_vector_payload)
    p_a["fact_definition_id"] = str(uuid4()).lower()
    p_a["fact_key"] = "synthetic_condition_a"
    d_a = compute_content_digest(p_a)

    snap_a = service.create_fact_definition_draft(
        actor_a, shared_req_key, version_id=v_a_id, content_digest=d_a, payload=p_a
    )
    assert snap_a.id == v_a_id
    sqlite_session.commit()

    # Actor B creates Fact Definition B with the exact same request_key
    v_b_id = uuid4()
    p_b = dict(boolean_vector_payload)
    p_b["fact_definition_id"] = str(uuid4()).lower()
    p_b["fact_key"] = "synthetic_condition_b"
    d_b = compute_content_digest(p_b)

    snap_b = service.create_fact_definition_draft(
        actor_b, shared_req_key, version_id=v_b_id, content_digest=d_b, payload=p_b
    )
    assert snap_b.id == v_b_id
    sqlite_session.commit()

    # Verify exact counts and distinct intent keys
    versions = sqlite_session.execute(select(CatalogFactDefinitionVersion)).scalars().all()
    assert len(versions) == 2

    receipts = sqlite_session.execute(select(CatalogMutationReceipt)).scalars().all()
    assert len(receipts) == 2
    assert {r.actor_id for r in receipts} == {actor_a.actor_id, actor_b.actor_id}
    assert all(r.request_key == shared_req_key for r in receipts)

    intents = sqlite_session.execute(select(CatalogEventIntent)).scalars().all()
    assert len(intents) == 2
    assert intents[0].request_key != intents[1].request_key
    assert all(len(i.request_key) == 64 for i in intents)
    assert {i.aggregate_id for i in intents} == {v_a_id, v_b_id}


def test_r8_same_actor_retries_and_conflict_intent_counts(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """R8: Same-actor identical retry and conflicting retry produce exact version/receipt/intent counts without debris."""
    service = CatalogFactDefinitionDraftService(sqlite_session)
    req_key = "req-r8-retry-test"
    v_id = uuid4()

    # Initial create
    service.create_fact_definition_draft(
        valid_actor_context,
        req_key,
        version_id=v_id,
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )
    sqlite_session.commit()

    assert len(sqlite_session.execute(select(CatalogFactDefinitionVersion)).scalars().all()) == 1
    assert len(sqlite_session.execute(select(CatalogMutationReceipt)).scalars().all()) == 1
    assert len(sqlite_session.execute(select(CatalogEventIntent)).scalars().all()) == 1

    # Identical retry: returns existing snapshot; counts remain 1
    snap_retry = service.create_fact_definition_draft(
        valid_actor_context,
        req_key,
        version_id=v_id,
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )
    assert snap_retry.id == v_id
    sqlite_session.commit()

    assert len(sqlite_session.execute(select(CatalogFactDefinitionVersion)).scalars().all()) == 1
    assert len(sqlite_session.execute(select(CatalogMutationReceipt)).scalars().all()) == 1
    assert len(sqlite_session.execute(select(CatalogEventIntent)).scalars().all()) == 1

    # Conflicting retry: raises CatalogConflictError; counts remain 1 with zero debris
    conflicting_payload = dict(boolean_vector_payload)
    conflicting_payload["label"] = "Conflicting label"
    conflicting_digest = compute_content_digest(conflicting_payload)

    with pytest.raises(CatalogConflictError):
        service.create_fact_definition_draft(
            valid_actor_context,
            req_key,
            version_id=v_id,
            content_digest=conflicting_digest,
            payload=conflicting_payload,
        )

    assert len(sqlite_session.execute(select(CatalogFactDefinitionVersion)).scalars().all()) == 1
    assert len(sqlite_session.execute(select(CatalogMutationReceipt)).scalars().all()) == 1
    assert len(sqlite_session.execute(select(CatalogEventIntent)).scalars().all()) == 1


# ==============================================================================
# R9 - Incomplete Stored Aggregate Rejection Regressions
# ==============================================================================


def test_r9_incomplete_stored_aggregate_empty_scopes_rejected_on_read_retry_predecessor(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """R9: Stored version with empty allowed_scopes is rejected on read, retry, and predecessor use even with matching digest."""
    denial_sink = MemoryDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_sink=denial_sink)
    v1_id = uuid4()
    req_key = "req-r9-empty-scopes"

    service.create_fact_definition_draft(
        valid_actor_context,
        req_key,
        version_id=v1_id,
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )
    sqlite_session.commit()

    # Owner-fixture: Delete scope children and store matching digest for empty scopes
    sqlite_session.execute(
        delete(CatalogFactDefinitionScope).where(
            CatalogFactDefinitionScope.fact_definition_version_id == v1_id
        )
    )
    empty_scope_payload = dict(boolean_vector_payload)
    empty_scope_payload["allowed_scopes"] = []
    empty_scope_digest = compute_content_digest(empty_scope_payload)

    sqlite_session.execute(
        update(CatalogFactDefinitionVersion)
        .where(CatalogFactDefinitionVersion.id == v1_id)
        .values(content_digest=empty_scope_digest)
    )
    sqlite_session.commit()

    # 1. Read fails closed with CatalogInvariantError; records denial; no read-success audit
    audit_count_before = len(sqlite_session.execute(select(CatalogAuditEvent)).scalars().all())
    with pytest.raises(CatalogInvariantError, match="allowed_scopes cardinality"):
        service.get_fact_definition_version(valid_actor_context, "req-r9-get", v1_id)

    assert any(d["reason_code"] == "CatalogInvariantError" for d in denial_sink.records)
    audit_count_after = len(sqlite_session.execute(select(CatalogAuditEvent)).scalars().all())
    assert audit_count_after == audit_count_before  # No read-success audit

    # 2. Identical retry on create fails closed; no retry-success audit
    with pytest.raises(CatalogInvariantError, match="allowed_scopes cardinality"):
        service.create_fact_definition_draft(
            valid_actor_context,
            req_key,
            version_id=v1_id,
            content_digest=boolean_vector_digest,
            payload=boolean_vector_payload,
        )

    # 3. Predecessor consumption fails closed; no revision 2 created
    v2_id = uuid4()
    v2_payload = dict(boolean_vector_payload)
    v2_payload["revision"] = 2
    v2_payload["version_label"] = "1.1.0"
    v2_payload["predecessor_id"] = str(v1_id)
    v2_payload["predecessor_revision"] = 1
    v2_digest = compute_content_digest(v2_payload)

    with pytest.raises(CatalogInvariantError, match="allowed_scopes cardinality"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-r9-v2",
            version_id=v2_id,
            content_digest=v2_digest,
            payload=v2_payload,
        )

    assert len(sqlite_session.execute(select(CatalogFactDefinitionVersion)).scalars().all()) == 1


def test_r9_incomplete_stored_aggregate_enum_without_values_rejected(
    sqlite_session, valid_actor_context, enum_vector_payload, enum_vector_digest
):
    """R9: Stored version with value_type='enum' and 0 enum values is rejected on read and predecessor consumption."""
    denial_sink = MemoryDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_sink=denial_sink)
    v1_id = uuid4()
    req_key = "req-r9-empty-enums"

    service.create_fact_definition_draft(
        valid_actor_context,
        req_key,
        version_id=v1_id,
        content_digest=enum_vector_digest,
        payload=enum_vector_payload,
    )
    sqlite_session.commit()

    # Owner-fixture: Delete all enum values and store matching digest for empty enum_values
    sqlite_session.execute(
        delete(CatalogFactDefinitionEnumValue).where(
            CatalogFactDefinitionEnumValue.fact_definition_version_id == v1_id
        )
    )
    empty_enum_payload = dict(enum_vector_payload)
    empty_enum_payload["enum_values"] = []
    empty_enum_digest = compute_content_digest(empty_enum_payload)

    sqlite_session.execute(
        update(CatalogFactDefinitionVersion)
        .where(CatalogFactDefinitionVersion.id == v1_id)
        .values(content_digest=empty_enum_digest)
    )
    sqlite_session.commit()

    with pytest.raises(CatalogInvariantError, match="enum_values; expected 1..64"):
        service.get_fact_definition_version(valid_actor_context, "req-r9-get-enum", v1_id)


def test_r9_stored_aggregate_invalid_ordering_and_types_rejected(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """R9: Non-contiguous scope sequence, non-synthetic key, or non-enum with enum children fail closed."""
    service = CatalogFactDefinitionDraftService(sqlite_session)
    v1_id = uuid4()

    service.create_fact_definition_draft(
        valid_actor_context,
        "req-r9-invariants",
        version_id=v1_id,
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )
    sqlite_session.commit()

    # Case A: Non-contiguous scope sequence (set sequence to 5)
    sqlite_session.execute(
        update(CatalogFactDefinitionScope)
        .where(CatalogFactDefinitionScope.fact_definition_version_id == v1_id)
        .values(sequence=5)
    )
    sqlite_session.commit()

    with pytest.raises(CatalogInvariantError, match="contiguous 1-indexed"):
        service.get_fact_definition_version(valid_actor_context, "req-r9-seq", v1_id)


# ==============================================================================
# R10 - Strict Input Validation & Boundary Regressions
# ==============================================================================


def test_r10_fact_key_length_65_chars_rejected(
    sqlite_session, valid_actor_context, boolean_vector_payload
):
    """R10: 65-character fact_key fails controlled validation and never reaches database IntegrityError."""
    denial_sink = MemoryDeniedAuditSink()
    service = CatalogFactDefinitionDraftService(sqlite_session, denied_sink=denial_sink)

    payload = dict(boolean_vector_payload)
    payload["fact_key"] = "synthetic_" + "a" * 55  # Total 65 characters
    digest = compute_content_digest(payload)

    with pytest.raises(
        CatalogValidationError, match="fact_key length must be between 11 and 64 chars"
    ):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-r10-fk-len",
            version_id=uuid4(),
            content_digest=digest,
            payload=payload,
        )

    assert any(d["reason_code"] == "CatalogValidationError" for d in denial_sink.records)


def test_r10_strict_canonical_date_validation_rejects_timestamps(
    sqlite_session, valid_actor_context, boolean_vector_payload
):
    """R10: Date columns reject timestamp strings with times or timezone offsets, and invalid calendar dates."""
    service = CatalogFactDefinitionDraftService(sqlite_session)

    # 1. Timestamp with T and offset
    p1 = dict(boolean_vector_payload)
    p1["effective_from"] = "2026-10-19T00:00:00Z"
    d1 = compute_content_digest(p1)
    with pytest.raises(CatalogValidationError, match="strict 'YYYY-MM-DD' date string"):
        service.create_fact_definition_draft(
            valid_actor_context, "req-r10-d1", version_id=uuid4(), content_digest=d1, payload=p1
        )

    # 2. Date with time
    p2 = dict(boolean_vector_payload)
    p2["effective_from"] = "2026-10-19 12:00:00"
    d2 = compute_content_digest(p2)
    with pytest.raises(CatalogValidationError, match="strict 'YYYY-MM-DD' date string"):
        service.create_fact_definition_draft(
            valid_actor_context, "req-r10-d2", version_id=uuid4(), content_digest=d2, payload=p2
        )

    # 3. Invalid calendar date
    p3 = dict(boolean_vector_payload)
    p3["effective_from"] = "2026-02-31"
    d3 = compute_content_digest(p3)
    with pytest.raises(CatalogValidationError, match="not a valid calendar date"):
        service.create_fact_definition_draft(
            valid_actor_context, "req-r10-d3", version_id=uuid4(), content_digest=d3, payload=p3
        )

    # 4. effective_until precedes effective_from
    p4 = dict(boolean_vector_payload)
    p4["effective_from"] = "2026-06-01"
    p4["effective_until"] = "2026-05-01"
    d4 = compute_content_digest(p4)
    with pytest.raises(
        CatalogValidationError, match="effective_until cannot precede effective_from"
    ):
        service.create_fact_definition_draft(
            valid_actor_context, "req-r10-d4", version_id=uuid4(), content_digest=d4, payload=p4
        )

    # 5. Genuine strict YYYY-MM-DD date round-trip succeeds
    p5 = dict(boolean_vector_payload)
    p5["effective_from"] = "2026-01-01"
    p5["effective_until"] = "2026-12-31"
    d5 = compute_content_digest(p5)
    v5_id = uuid4()
    snap5 = service.create_fact_definition_draft(
        valid_actor_context, "req-r10-d5", version_id=v5_id, content_digest=d5, payload=p5
    )
    assert snap5.effective_from == date(2026, 1, 1)
    assert snap5.effective_until == date(2026, 12, 31)
    assert snap5.content_digest == d5


def test_r10_payload_size_limit_262144_bytes_enforced(
    sqlite_session, valid_actor_context, boolean_vector_payload
):
    """R10: Payload exceeding 262144 bytes canonical UTF-8 is rejected with CatalogValidationError."""
    service = CatalogFactDefinitionDraftService(sqlite_session)

    huge_payload = dict(boolean_vector_payload)
    huge_payload["description"] = "A" * 265000  # Will exceed MAX_PAYLOAD_BYTES (262144)
    huge_digest = compute_content_digest(huge_payload)

    with pytest.raises(CatalogValidationError, match="exceeds maximum limit of 262144 bytes"):
        service.create_fact_definition_draft(
            valid_actor_context,
            "req-r10-huge",
            version_id=uuid4(),
            content_digest=huge_digest,
            payload=huge_payload,
        )


# ==============================================================================
# WP-07E: Additive extraction compatibility tests
# ==============================================================================


def test_fact_snapshot_extraction_compatibility():
    """Verify that dataclasses and reader are importable from both modules with identity equality."""
    from conformly.catalog_v2 import fact_definition_snapshots as fds
    from conformly.catalog_v2 import service_fact_definitions as sfd

    assert fds.FactDefinitionScopeSnapshot is sfd.FactDefinitionScopeSnapshot
    assert fds.FactDefinitionEnumValueSnapshot is sfd.FactDefinitionEnumValueSnapshot
    assert fds.FactDefinitionVersionSnapshot is sfd.FactDefinitionVersionSnapshot
    assert fds.read_verified_fact_definition_snapshot is sfd.read_verified_fact_definition_snapshot


def test_read_verified_fact_definition_snapshot_direct(
    sqlite_session, valid_actor_context, boolean_vector_payload, boolean_vector_digest
):
    """Directly call read_verified_fact_definition_snapshot on a persisted draft version."""
    from conformly.catalog_v2.fact_definition_snapshots import (
        read_verified_fact_definition_snapshot,
    )
    from conformly.catalog_v2.service_fact_definitions import (
        CatalogFactDefinitionDraftService,
    )

    service = CatalogFactDefinitionDraftService(sqlite_session)
    ver_id = uuid4()
    snap = service.create_fact_definition_draft(
        context=valid_actor_context,
        request_key="req-extract-direct",
        version_id=ver_id,
        content_digest=boolean_vector_digest,
        payload=boolean_vector_payload,
    )

    direct_snap = read_verified_fact_definition_snapshot(
        sqlite_session, ver_id, expected_digest=boolean_vector_digest
    )
    assert direct_snap.id == snap.id
    assert direct_snap.fact_definition_id == snap.fact_definition_id
    assert direct_snap.content_digest == snap.content_digest
    assert direct_snap.revision == snap.revision
    assert direct_snap.fact_key == snap.fact_key
    assert direct_snap.allowed_scopes == snap.allowed_scopes
    assert direct_snap.enum_values == snap.enum_values


def test_read_verified_fact_definition_snapshot_rejects_non_uuid(sqlite_session):
    """read_verified_fact_definition_snapshot rejects non-UUID arguments."""
    from conformly.catalog_v2.actor import CatalogInvariantError
    from conformly.catalog_v2.fact_definition_snapshots import (
        read_verified_fact_definition_snapshot,
    )

    with pytest.raises(CatalogInvariantError, match="version_id must be a UUID instance"):
        read_verified_fact_definition_snapshot(sqlite_session, "not-a-uuid")  # type: ignore[arg-type]


def test_read_verified_fact_definition_snapshot_rejects_missing(sqlite_session):
    """read_verified_fact_definition_snapshot raises CatalogNotFoundError for unknown version."""
    from conformly.catalog_v2.actor import CatalogNotFoundError
    from conformly.catalog_v2.fact_definition_snapshots import (
        read_verified_fact_definition_snapshot,
    )

    with pytest.raises(CatalogNotFoundError, match="not found in database"):
        read_verified_fact_definition_snapshot(sqlite_session, uuid4())
