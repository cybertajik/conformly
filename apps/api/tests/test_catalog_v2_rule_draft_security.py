"""Security, admission, privilege, and audit probes for WP-07E ApplicabilityRule authoring."""

import hashlib
import threading
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogActorKind,
    CatalogCapability,
    CatalogPermissionDeniedError,
    CatalogSecurityError,
    CatalogValidationError,
)
from conformly.catalog_v2.audit import DeniedAuditSink
from conformly.catalog_v2.digest import (
    canonical_json,
    compute_content_digest,
    compute_requirement_version_digest,
    compute_source_version_digest,
)
from conformly.catalog_v2.models import (
    CatalogApplicabilityRule,
    CatalogApplicabilityRuleVersion,
    CatalogAuditEvent,
    CatalogEventIntent,
    CatalogFactDefinition,
    CatalogFactDefinitionScope,
    CatalogFactDefinitionVersion,
    CatalogMutationReceipt,
    CatalogPublisher,
    CatalogRequirement,
    CatalogRequirementSourceReference,
    CatalogRequirementVersion,
    CatalogSource,
    CatalogSourcePermissionDecision,
    CatalogSourcePermissionGuard,
    CatalogSourcePermissionProposal,
    CatalogSourceProvenance,
    CatalogSourceVersion,
)
from conformly.catalog_v2.service_applicability_rules import (
    ADVISORY_LOCK_ID,
    APPLICABILITY_RULE_DRAFT_CHAIN_KEY,
    SERVICE_POSTGRES_ROLE,
    UNKNOWN_SYSTEM_ACTOR_ID,
    CatalogApplicabilityRuleDraftService,
)
from conformly.db.base import Base

REAL_ADMISSION_GUARD = CatalogApplicabilityRuleDraftService._verify_postgres_connection_admission


@pytest.fixture(autouse=True)
def stub_postgres_admission_for_sqlite_fixture(monkeypatch):
    """Pure validation/unit tests on in-memory SQLite explicitly stub connection admission.
    Negative tests for the admission guard explicitly invoke the real guard."""
    monkeypatch.setattr(
        CatalogApplicabilityRuleDraftService,
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
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def synthetic_prereqs(sqlite_session):
    """Create a complete set of valid synthetic prerequisite entities in sqlite_session."""
    db_now = datetime.now(UTC)

    # 0. Publisher
    pub_id = uuid4()
    pub = CatalogPublisher(
        id=pub_id,
        publisher_key="synthetic_demo_pub",
        name="Synthetic Demo Publisher",
        status="Draft",
        created_at=db_now,
        updated_at=db_now,
    )
    sqlite_session.add(pub)

    # 1. Source & Version
    source_id = uuid4()
    source = CatalogSource(
        id=source_id,
        publisher_id=pub_id,
        source_key="synthetic_rule_demo_source_1",
        title="Synthetic Demo Source",
        status="Draft",
        created_at=db_now,
        updated_at=db_now,
    )
    sqlite_session.add(source)

    guard = CatalogSourcePermissionGuard(
        source_id=source_id,
        revision=1,
        updated_at=db_now,
    )
    sqlite_session.add(guard)

    source_ver_id = uuid4()
    s_digest = compute_source_version_digest(
        source_id=source_id,
        edition="2026-v1",
        predecessor_id=None,
        language=None,
        official_locator=None,
        publication_date=None,
        retrieved_at=None,
        status="Draft",
    )
    source_ver = CatalogSourceVersion(
        id=source_ver_id,
        source_id=source_id,
        revision=1,
        edition="2026-v1",
        content_digest=s_digest,
        status="Draft",
        created_at=db_now,
        updated_at=db_now,
    )
    sqlite_session.add(source_ver)

    prov_id = uuid4()
    prov = CatalogSourceProvenance(
        id=prov_id,
        source_version_id=source_ver_id,
        source_revision=1,
        content_sha256=b"x" * 32,
        content_size=100,
        mime_type="text/plain",
        locator="https://example.com/spec",
        retrieved_at=db_now,
        recorded_by_actor_id=uuid4(),
    )
    sqlite_session.add(prov)

    # Permissions: reference and store
    for use_case in ["reference", "store"]:
        prop_id = uuid4()
        prop = CatalogSourcePermissionProposal(
            id=prop_id,
            provenance_id=prov_id,
            source_version_id=source_ver_id,
            use_case=use_case,
            scope_key="global",
            sequence=1,
            proposed_outcome="Allowed",
            conditions_state="None",
            recorded_by_actor_id=uuid4(),
        )
        sqlite_session.add(prop)

        p_dec = CatalogSourcePermissionDecision(
            id=uuid4(),
            source_id=source_id,
            source_version_id=source_ver_id,
            proposal_id=prop_id,
            use_case=use_case,
            scope_key="global",
            sequence=1,
            decision="Allowed",
            conditions_state="None",
            valid_from=db_now - timedelta(days=1),
            valid_until=db_now + timedelta(days=365),
            decided_by_actor_id=uuid4(),
            decided_at=db_now,
            evidence_reference="test-evidence",
            policy_version="catalog-permission-v1",
            guard_revision=1,
            created_at=db_now,
        )
        sqlite_session.add(p_dec)

    # 2. Requirement & Version
    req_id = uuid4()
    req = CatalogRequirement(
        id=req_id,
        source_id=source_id,
        requirement_key="synthetic_rule_demo_req_1",
        status="Draft",
        created_at=db_now,
        updated_at=db_now,
    )
    sqlite_session.add(req)

    req_ver_id = uuid4()
    _req_locators = [
        {
            "locator_kind": "section",
            "locator_value": "1.1",
            "sequence": 1,
            "source_version_id": source_ver_id,
        }
    ]
    r_digest = compute_requirement_version_digest(
        requirement_id=req_id,
        source_id=source_id,
        source_version_id=source_ver_id,
        version_label="1.0.0",
        predecessor_id=None,
        revision=1,
        normalized_outcome="Outcome",
        requirement_type="mandatory",
        obligated_actor="controller",
        text_origin="conformly_paraphrase",
        customer_display_text="Display",
        effective_from=None,
        effective_until=None,
        source_references=_req_locators,
        status="Draft",
    )
    req_ver = CatalogRequirementVersion(
        id=req_ver_id,
        requirement_id=req_id,
        source_id=source_id,
        revision=1,
        version_label="1.0.0",
        source_version_id=source_ver_id,
        normalized_outcome="Outcome",
        requirement_type="mandatory",
        obligated_actor="controller",
        text_origin="conformly_paraphrase",
        customer_display_text="Display",
        content_digest=r_digest,
        status="Draft",
        created_at=db_now,
        updated_at=db_now,
    )
    sqlite_session.add(req_ver)

    req_src_ref = CatalogRequirementSourceReference(
        id=uuid4(),
        requirement_version_id=req_ver_id,
        sequence=1,
        source_version_id=source_ver_id,
        locator_kind="section",
        locator_value="1.1",
        created_at=db_now,
    )
    sqlite_session.add(req_src_ref)

    # 3. Fact Definition & Version (Boolean)
    fact_id = uuid4()
    fact_def = CatalogFactDefinition(
        id=fact_id,
        fact_key="synthetic_boolean_fact",
        status="Draft",
        created_at=db_now,
        updated_at=db_now,
    )
    sqlite_session.add(fact_def)

    fact_ver_id = uuid4()
    f_payload = {
        "allowed_scopes": [{"scope_type": "tenant", "sequence": 1}],
        "collection_guidance": None,
        "description": "Synthetic boolean fact for rule authoring tests.",
        "effective_from": None,
        "effective_until": None,
        "enum_values": [],
        "fact_definition_id": str(fact_id).lower(),
        "fact_key": "synthetic_boolean_fact",
        "kind": "FactDefinitionVersion",
        "label": "Synthetic Boolean Fact",
        "predecessor_id": None,
        "predecessor_revision": None,
        "revision": 1,
        "sensitivity": "Internal",
        "status": "Draft",
        "value_type": "boolean",
        "version_label": "1.0.0",
    }
    f_digest = compute_content_digest(f_payload)
    fact_ver = CatalogFactDefinitionVersion(
        id=fact_ver_id,
        fact_definition_id=fact_id,
        revision=1,
        version_label="1.0.0",
        label="Synthetic Boolean Fact",
        description="Synthetic boolean fact for rule authoring tests.",
        value_type="boolean",
        sensitivity="Internal",
        status="Draft",
        content_digest=f_digest,
        digest_schema="catalog-fact-definition-draft-v1",
        created_at=db_now,
        updated_at=db_now,
    )
    sqlite_session.add(fact_ver)

    f_scope = CatalogFactDefinitionScope(
        id=uuid4(),
        fact_definition_version_id=fact_ver_id,
        sequence=1,
        scope_type="tenant",
        created_at=db_now,
    )
    sqlite_session.add(f_scope)

    sqlite_session.commit()

    return {
        "source_id": source_id,
        "source_version_id": source_ver_id,
        "source_digest": s_digest,
        "requirement_id": req_id,
        "requirement_version_id": req_ver_id,
        "requirement_digest": r_digest,
        "fact_definition_id": fact_id,
        "fact_definition_version_id": fact_ver_id,
        "fact_digest": f_digest,
    }


def make_valid_rule_payload(
    prereqs: dict[str, Any], rule_id: UUID | None = None
) -> tuple[dict[str, Any], bytes]:
    """Helper to construct a valid canonical rule payload matching the prerequisites."""
    rid = rule_id or uuid4()
    ast = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": str(prereqs["fact_definition_version_id"]).lower(),
            "op": "EXISTS",
            "scope_type": "tenant",
        },
    }
    ast_canonical_bytes = canonical_json(ast).encode("utf-8")

    payload = {
        "effective_from": None,
        "effective_until": None,
        "expression_ast_version": 1,
        "expression_canonical_hex": ast_canonical_bytes.hex(),
        "fact_refs": [
            {
                "content_digest": prereqs["fact_digest"].hex(),
                "fact_definition_version_id": str(prereqs["fact_definition_version_id"]).lower(),
                "sequence": 1,
            }
        ],
        "kind": "ApplicabilityRuleVersion",
        "predecessor_id": None,
        "predecessor_revision": None,
        "requirement_id": str(prereqs["requirement_id"]).lower(),
        "requirement_version_digest": prereqs["requirement_digest"].hex(),
        "requirement_version_id": str(prereqs["requirement_version_id"]).lower(),
        "revision": 1,
        "rule_id": str(rid).lower(),
        "rule_key": "synthetic_rule_sample",
        "source_refs": [
            {
                "content_digest": prereqs["source_digest"].hex(),
                "sequence": 1,
                "source_version_id": str(prereqs["source_version_id"]).lower(),
            }
        ],
        "status": "Draft",
        "version_label": "1.0.0",
    }
    digest = compute_content_digest(payload)
    return payload, digest


# ---------------------------------------------------------------------------
# 1. Advisory Lock Derivation Invariant
# ---------------------------------------------------------------------------


def test_advisory_lock_signed_bigint_derivation():
    """Advisory lock bigint must match exact first 8 bytes of sha256(b'conformly:applicability-rule-draft-v1')."""
    expected = int.from_bytes(
        hashlib.sha256(b"conformly:applicability-rule-draft-v1").digest()[:8],
        byteorder="big",
        signed=True,
    )
    assert ADVISORY_LOCK_ID == expected
    assert ADVISORY_LOCK_ID == 7570658326947719977


# ---------------------------------------------------------------------------
# 2. Missing or Invalid Actor Context Probes
# ---------------------------------------------------------------------------


def test_missing_or_invalid_actor_context_denied(sqlite_session, synthetic_prereqs):
    """Missing or non-CatalogActorContext actor fails closed and records UNKNOWN_SYSTEM_ACTOR_ID."""
    sink = SecurityProbeDeniedAuditSink()
    service = CatalogApplicabilityRuleDraftService(sqlite_session, denied_audit_sink=sink)
    payload, digest = make_valid_rule_payload(synthetic_prereqs)
    ver_id = uuid4()

    # 1. None context on create
    with pytest.raises(CatalogSecurityError, match="Missing catalog actor context"):
        service.create_rule_draft(
            context=None,  # type: ignore[arg-type]
            request_key="req-no-actor",
            version_id=ver_id,
            content_digest=digest,
            payload=payload,
        )
    assert len(sink.records) == 1
    assert sink.records[0]["actor_id"] == UNKNOWN_SYSTEM_ACTOR_ID

    # 2. Arbitrary dict context (not CatalogActorContext)
    with pytest.raises(CatalogSecurityError):
        service.create_rule_draft(
            context={"role": "admin"},  # type: ignore[arg-type]
            request_key="req-dict-actor",
            version_id=ver_id,
            content_digest=digest,
            payload=payload,
        )
    assert len(sink.records) == 2
    assert sink.records[1]["actor_id"] == UNKNOWN_SYSTEM_ACTOR_ID


def test_actor_missing_platform_admin_or_mfa(sqlite_session, synthetic_prereqs):
    """Actors without platform admin or MFA are rejected with denial recorded."""
    sink = SecurityProbeDeniedAuditSink()
    service = CatalogApplicabilityRuleDraftService(sqlite_session, denied_audit_sink=sink)
    payload, digest = make_valid_rule_payload(synthetic_prereqs)
    ver_id = uuid4()
    actor_id = uuid4()

    # 1. Non-platform admin
    actor_no_admin = CatalogActorContext(
        actor_id=actor_id,
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=False,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
        authenticated_at=datetime.now(UTC),
    )
    with pytest.raises(CatalogSecurityError, match="Platform admin status required"):
        service.create_rule_draft(
            context=actor_no_admin,
            request_key="req-no-admin",
            version_id=ver_id,
            content_digest=digest,
            payload=payload,
        )
    assert len(sink.records) == 1
    assert sink.records[0]["actor_id"] == actor_id

    # 2. Missing MFA
    actor_no_mfa = CatalogActorContext(
        actor_id=actor_id,
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=False,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
        authenticated_at=datetime.now(UTC),
    )
    with pytest.raises(CatalogSecurityError, match="Verified MFA required"):
        service.create_rule_draft(
            context=actor_no_mfa,
            request_key="req-no-mfa",
            version_id=ver_id,
            content_digest=digest,
            payload=payload,
        )
    assert len(sink.records) == 2


def test_actor_missing_capabilities(sqlite_session, synthetic_prereqs):
    """Missing DRAFT_WRITE on create or DRAFT_READ on get fails closed."""
    sink = SecurityProbeDeniedAuditSink()
    service = CatalogApplicabilityRuleDraftService(sqlite_session, denied_audit_sink=sink)
    payload, digest = make_valid_rule_payload(synthetic_prereqs)
    ver_id = uuid4()

    # Missing DRAFT_WRITE on create
    actor_read_only = CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_READ}),
        authenticated_at=datetime.now(UTC),
    )
    with pytest.raises(CatalogSecurityError, match="Missing required capability: DRAFT_WRITE"):
        service.create_rule_draft(
            context=actor_read_only,
            request_key="req-no-write",
            version_id=ver_id,
            content_digest=digest,
            payload=payload,
        )
    assert len(sink.records) == 1

    # Missing DRAFT_READ on get
    actor_write_only = CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE}),
        authenticated_at=datetime.now(UTC),
    )
    with pytest.raises(CatalogSecurityError, match="Missing required capability: DRAFT_READ"):
        service.get_rule_version(
            context=actor_write_only,
            request_key="req-no-read",
            version_id=ver_id,
        )
    assert len(sink.records) == 2


def test_actor_authentication_expiration_and_future_skew(sqlite_session, synthetic_prereqs):
    """Authentication older than 900 seconds or in the future (>5s) is rejected."""
    sink = SecurityProbeDeniedAuditSink()
    service = CatalogApplicabilityRuleDraftService(sqlite_session, denied_audit_sink=sink)
    payload, digest = make_valid_rule_payload(synthetic_prereqs)
    ver_id = uuid4()
    now = datetime.now(UTC)

    # 1. Stale authentication (>900s)
    stale_actor = CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
        authenticated_at=now - timedelta(seconds=905),
    )
    with pytest.raises(
        CatalogSecurityError, match="Authentication expired: age exceeds 15 minutes"
    ):
        service.create_rule_draft(
            context=stale_actor,
            request_key="req-stale",
            version_id=ver_id,
            content_digest=digest,
            payload=payload,
        )
    assert len(sink.records) == 1

    # 2. Future authentication (>5s)
    future_actor = CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
        authenticated_at=now + timedelta(seconds=15),
    )
    with pytest.raises(
        CatalogSecurityError, match="Authentication timestamp cannot be in the future"
    ):
        service.create_rule_draft(
            context=future_actor,
            request_key="req-future",
            version_id=ver_id,
            content_digest=digest,
            payload=payload,
        )
    assert len(sink.records) == 2


# ---------------------------------------------------------------------------
# 3. PostgreSQL Connection Admission Probes
# ---------------------------------------------------------------------------


def test_postgres_connection_admission_enforcement():
    """Service rejects wrong session_user, current_user, elevated attributes, or memberships."""
    mock_session = MagicMock(spec=Session)
    mock_bind = MagicMock()
    mock_bind.dialect.name = "postgresql"
    mock_session.bind = mock_bind

    service = CatalogApplicabilityRuleDraftService(mock_session)

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

    # 2. SET ROLE mismatch (session_user=conformly_catalog_rule_author, current_user=postgres)
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
        _make_res("read committed"),  # transaction isolation
    ]
    REAL_ADMISSION_GUARD(service)  # No exception raised


# ---------------------------------------------------------------------------
# 4. Audit Chain & Receipt Invariants
# ---------------------------------------------------------------------------


def test_dedicated_audit_chain_and_receipt_invariants(sqlite_session, synthetic_prereqs):
    """Creates write only to applicability-rule-draft-v1 chain and ApplicabilityRuleVersion receipts."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    actor = CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
        authenticated_at=datetime.now(UTC),
    )

    ver_id = uuid4()
    payload, digest = make_valid_rule_payload(synthetic_prereqs)

    service.create_rule_draft(
        actor,
        "req-chain-verify",
        version_id=ver_id,
        content_digest=digest,
        payload=payload,
    )

    # 1. Audit events are isolated to applicability-rule-draft-v1
    audit_events = (
        sqlite_session.execute(
            select(CatalogAuditEvent).where(CatalogAuditEvent.resource_id == ver_id)
        )
        .scalars()
        .all()
    )
    assert len(audit_events) == 1
    assert audit_events[0].chain_key == APPLICABILITY_RULE_DRAFT_CHAIN_KEY

    # 2. Mutation receipts are isolated to ApplicabilityRuleVersion
    receipts = (
        sqlite_session.execute(
            select(CatalogMutationReceipt).where(CatalogMutationReceipt.result_id == ver_id)
        )
        .scalars()
        .all()
    )
    assert len(receipts) == 1
    assert receipts[0].operation == "applicability_rule.create_draft"
    assert receipts[0].result_type == "ApplicabilityRuleVersion"

    # 3. Event intents are isolated to ApplicabilityRuleVersion and ApplicabilityRuleDraftCreated
    intents = (
        sqlite_session.execute(
            select(CatalogEventIntent).where(CatalogEventIntent.aggregate_id == ver_id)
        )
        .scalars()
        .all()
    )
    assert len(intents) == 1
    assert intents[0].aggregate_type == "ApplicabilityRuleVersion"
    assert intents[0].event_kind == "ApplicabilityRuleDraftCreated"

    # 4. Reading via get_rule_version adds an audit event but NO receipts or intents
    receipts_before = len(sqlite_session.execute(select(CatalogMutationReceipt)).scalars().all())
    intents_before = len(sqlite_session.execute(select(CatalogEventIntent)).scalars().all())

    service.get_rule_version(actor, "read-audit-only", ver_id)

    read_audits = (
        sqlite_session.execute(
            select(CatalogAuditEvent).where(
                CatalogAuditEvent.resource_id == ver_id,
                CatalogAuditEvent.action == "applicability_rule.get_draft",
            )
        )
        .scalars()
        .all()
    )
    assert len(read_audits) == 1
    assert read_audits[0].chain_key == APPLICABILITY_RULE_DRAFT_CHAIN_KEY

    # Receipts and intents counts unchanged
    all_receipts = sqlite_session.execute(select(CatalogMutationReceipt)).scalars().all()
    all_intents = sqlite_session.execute(select(CatalogEventIntent)).scalars().all()
    assert len(all_receipts) == receipts_before == 1
    assert len(all_intents) == intents_before == 1


# ---------------------------------------------------------------------------
# 5. Unbound, SQLite, and Dirty Unit of Work Probes
# ---------------------------------------------------------------------------


def test_admission_guard_rejects_unbound_and_non_postgres_sessions():
    """Admission guard fails closed on unbound or non-PostgreSQL connections."""
    # 1. Unbound session
    unbound_session = MagicMock(spec=Session)
    unbound_session.bind = None
    unbound_session.is_active = True
    unbound_session.dirty = set()
    unbound_session.new = set()
    unbound_session.deleted = set()

    s1 = CatalogApplicabilityRuleDraftService(unbound_session)
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

    s2 = CatalogApplicabilityRuleDraftService(sqlite_mock_session)
    with pytest.raises(
        CatalogSecurityError, match="Unsupported database dialect 'sqlite': PostgreSQL required"
    ):
        REAL_ADMISSION_GUARD(s2)


def test_service_initialization_rejects_dirty_unit_of_work():
    """Service rejects sessions with uncommitted/dirty unit of work on initialization."""
    dirty_session = MagicMock(spec=Session)
    dirty_session.is_active = True
    dirty_session.dirty = {MagicMock()}
    dirty_session.new = set()
    dirty_session.deleted = set()

    with pytest.raises(
        CatalogSecurityError, match="Service session must start with a clean unit of work"
    ):
        CatalogApplicabilityRuleDraftService(dirty_session)


def test_service_rejects_conflicting_schema_translate_map():
    """Service rejects sessions with conflicting non-public schema translate map."""
    session = MagicMock(spec=Session)
    session.is_active = True
    session.dirty = set()
    session.new = set()
    session.deleted = set()
    mock_bind = MagicMock()
    mock_bind.dialect.name = "postgresql"
    session.bind = mock_bind

    mock_conn = MagicMock()
    mock_conn.get_execution_options.return_value = {"schema_translate_map": {None: "tenant_custom"}}
    session.connection.return_value = mock_conn

    s = CatalogApplicabilityRuleDraftService(session)
    with pytest.raises(CatalogSecurityError, match="Conflicting schema_translate_map"):
        s._ensure_schema_translation()


# ---------------------------------------------------------------------------
# 6. Synthetic Namespace & Prefix Enforcement
# ---------------------------------------------------------------------------


def test_synthetic_namespace_enforcement_sources_and_targets(sqlite_session, synthetic_prereqs):
    """Sources and target requirements must have synthetic_rule_demo_ prefix; rules must have synthetic_ prefix."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    actor = CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
        authenticated_at=datetime.now(UTC),
    )
    db_now = datetime.now(UTC)

    # 1. Non-synthetic source reference (e.g. real GDPR source)
    real_src_id = uuid4()
    real_src = CatalogSource(
        id=real_src_id,
        publisher_id=synthetic_prereqs["source_id"],  # reuse pub
        source_key="gdpr_official_source",
        title="GDPR Regulation",
        status="Draft",
        created_at=db_now,
        updated_at=db_now,
    )
    sqlite_session.add(real_src)

    real_src_ver_id = uuid4()
    real_src_ver_digest = compute_source_version_digest(
        source_id=real_src_id,
        edition="2016-679",
        predecessor_id=None,
        language=None,
        official_locator=None,
        publication_date=None,
        retrieved_at=None,
        status="Draft",
    )
    real_src_ver = CatalogSourceVersion(
        id=real_src_ver_id,
        source_id=real_src_id,
        revision=1,
        edition="2016-679",
        content_digest=real_src_ver_digest,
        status="Draft",
        created_at=db_now,
        updated_at=db_now,
    )
    sqlite_session.add(real_src_ver)
    sqlite_session.commit()

    payload, _ = make_valid_rule_payload(synthetic_prereqs)
    # inject real source version into rule sources
    payload["source_refs"].append(
        {
            "content_digest": real_src_ver_digest.hex(),
            "sequence": 2,
            "source_version_id": str(real_src_ver_id).lower(),
        }
    )
    digest = compute_content_digest(payload)

    with pytest.raises(CatalogSecurityError, match="does not start with 'synthetic_rule_demo_'"):
        service.create_rule_draft(
            context=actor,
            request_key="req-non-synth-src",
            version_id=uuid4(),
            content_digest=digest,
            payload=payload,
        )

    # 2. Non-synthetic rule key
    bad_rule_payload, bad_rule_digest = make_valid_rule_payload(synthetic_prereqs)
    bad_rule_payload["rule_key"] = "commercial_tax_rule_1"
    bad_rule_digest = compute_content_digest(bad_rule_payload)

    with pytest.raises(
        CatalogValidationError, match="rule_key must start with literal 'synthetic_'"
    ):
        service.create_rule_draft(
            context=actor,
            request_key="req-bad-rule-key",
            version_id=uuid4(),
            content_digest=bad_rule_digest,
            payload=bad_rule_payload,
        )


# ---------------------------------------------------------------------------
# 7. Source Permission Enforcement & Anti-Laundering Probes
# ---------------------------------------------------------------------------


def test_source_permission_enforcement_and_anti_laundering(sqlite_session, synthetic_prereqs):
    """Referencing unpermitted sources (directly or via target requirement ancestry) fails closed."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    actor = CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
        authenticated_at=datetime.now(UTC),
    )
    db_now = datetime.now(UTC)

    # Create a synthetic source that lacks 'store' permission
    unpermitted_src_id = uuid4()
    unpermitted_src = CatalogSource(
        id=unpermitted_src_id,
        publisher_id=synthetic_prereqs["source_id"],
        source_key="synthetic_rule_demo_unpermitted",
        title="Unpermitted Synthetic Source",
        status="Draft",
        created_at=db_now,
        updated_at=db_now,
    )
    sqlite_session.add(unpermitted_src)

    guard = CatalogSourcePermissionGuard(
        source_id=unpermitted_src_id,
        revision=1,
        updated_at=db_now,
    )
    sqlite_session.add(guard)

    unpermitted_src_ver_id = uuid4()
    unpermitted_src_digest = compute_source_version_digest(
        source_id=unpermitted_src_id,
        edition="2026-v1",
        predecessor_id=None,
        language=None,
        official_locator=None,
        publication_date=None,
        retrieved_at=None,
        status="Draft",
    )
    unpermitted_src_ver = CatalogSourceVersion(
        id=unpermitted_src_ver_id,
        source_id=unpermitted_src_id,
        revision=1,
        edition="2026-v1",
        content_digest=unpermitted_src_digest,
        status="Draft",
        created_at=db_now,
        updated_at=db_now,
    )
    sqlite_session.add(unpermitted_src_ver)

    prov_id = uuid4()
    prov = CatalogSourceProvenance(
        id=prov_id,
        source_version_id=unpermitted_src_ver_id,
        source_revision=1,
        content_sha256=b"z" * 32,
        content_size=100,
        mime_type="text/plain",
        locator="https://example.com/unpermitted",
        retrieved_at=db_now,
        recorded_by_actor_id=uuid4(),
    )
    sqlite_session.add(prov)

    # Only grant 'reference', do NOT grant 'store'
    prop_id = uuid4()
    prop = CatalogSourcePermissionProposal(
        id=prop_id,
        provenance_id=prov_id,
        source_version_id=unpermitted_src_ver_id,
        use_case="reference",
        scope_key="global",
        sequence=1,
        proposed_outcome="Allowed",
        conditions_state="None",
        recorded_by_actor_id=uuid4(),
    )
    sqlite_session.add(prop)

    p_dec = CatalogSourcePermissionDecision(
        id=uuid4(),
        source_id=unpermitted_src_id,
        source_version_id=unpermitted_src_ver_id,
        proposal_id=prop_id,
        use_case="reference",
        scope_key="global",
        sequence=1,
        decision="Allowed",
        conditions_state="None",
        valid_from=db_now - timedelta(days=1),
        valid_until=db_now + timedelta(days=365),
        decided_by_actor_id=uuid4(),
        decided_at=db_now,
        evidence_reference="test-evidence",
        policy_version="catalog-permission-v1",
        guard_revision=1,
        created_at=db_now,
    )
    sqlite_session.add(p_dec)
    sqlite_session.commit()

    # Rule draft referencing unpermitted source must fail closed because 'store' is missing
    payload, _ = make_valid_rule_payload(synthetic_prereqs)
    payload["source_refs"].append(
        {
            "content_digest": unpermitted_src_digest.hex(),
            "sequence": 2,
            "source_version_id": str(unpermitted_src_ver_id).lower(),
        }
    )
    digest = compute_content_digest(payload)

    with pytest.raises(CatalogPermissionDeniedError, match="No permission decision found"):
        service.create_rule_draft(
            context=actor,
            request_key="req-missing-store-perm",
            version_id=uuid4(),
            content_digest=digest,
            payload=payload,
        )


def test_genuine_concurrent_source_permission_revocation_race(
    sqlite_session, synthetic_prereqs, monkeypatch
):
    """A genuine concurrent revocation race between advisory lock and source guard / time check fails closed."""
    sink = SecurityProbeDeniedAuditSink()
    service = CatalogApplicabilityRuleDraftService(sqlite_session, denied_sink=sink)
    actor = CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
        authenticated_at=datetime.now(UTC),
    )
    payload, digest = make_valid_rule_payload(synthetic_prereqs)
    req_key = "req-concurrent-revocation-race"
    vid = uuid4()

    event_race_triggered = threading.Event()
    event_revocation_committed = threading.Event()

    def concurrent_revoker():
        event_race_triggered.wait(timeout=5.0)
        # Concurrently revoke the permission by expiring valid_until into the past in separate session
        with Session(sqlite_session.bind) as worker_session:
            worker_dec = worker_session.execute(
                select(CatalogSourcePermissionDecision).where(
                    CatalogSourcePermissionDecision.source_version_id
                    == synthetic_prereqs["source_version_id"],
                    CatalogSourcePermissionDecision.use_case == "store",
                )
            ).scalar_one()
            worker_dec.valid_until = datetime.now(UTC) - timedelta(seconds=10)
            worker_session.commit()
        event_revocation_committed.set()

    original_get_db_time = service._get_db_time
    call_count = 0

    def hooked_get_db_time():
        nonlocal call_count
        call_count += 1
        db_t = original_get_db_time()
        # On the second call to _get_db_time (refreshed DB clock after source guards lock)
        if call_count == 2:
            event_race_triggered.set()
            event_revocation_committed.wait(timeout=5.0)
            sqlite_session.expire_all()
        return db_t

    monkeypatch.setattr(service, "_get_db_time", hooked_get_db_time)

    worker = threading.Thread(target=concurrent_revoker)
    worker.start()

    with pytest.raises(CatalogPermissionDeniedError, match="has expired"):
        service.create_rule_draft(
            context=actor,
            request_key=req_key,
            version_id=vid,
            content_digest=digest,
            payload=payload,
        )

    worker.join(timeout=5.0)

    # Prove complete rollback: no draft rule or rule version persisted
    stored_rule = sqlite_session.execute(
        select(CatalogApplicabilityRule).where(
            CatalogApplicabilityRule.rule_key == "synthetic_rule_sample"
        )
    ).scalar_one_or_none()
    assert stored_rule is None, "Rule must be rolled back on concurrent revocation"

    stored_ver = sqlite_session.execute(
        select(CatalogApplicabilityRuleVersion).where(CatalogApplicabilityRuleVersion.id == vid)
    ).scalar_one_or_none()
    assert stored_ver is None, "Rule version must be rolled back on concurrent revocation"

    # Prove denial recorded in sink
    assert len(sink.records) == 1
    assert sink.records[0]["operation"] == "applicability_rule.create_draft"
    assert sink.records[0]["reason_code"] == "PERMISSION_DENIED"
    assert sink.records[0]["request_key"] == req_key


def test_wrong_role_admission_with_failing_sink_propagates_visibly_with_cause(monkeypatch):
    monkeypatch.setattr(
        CatalogApplicabilityRuleDraftService,
        "_verify_postgres_connection_admission",
        REAL_ADMISSION_GUARD,
    )
    """When admission rejects an unauthorized role and the denial sink fails, the sink error is visibly propagated with chained cause."""
    mock_session = MagicMock(spec=Session)
    mock_bind = MagicMock()
    mock_bind.dialect.name = "postgresql"
    mock_session.bind = mock_bind
    mock_conn = MagicMock()
    mock_conn.get_execution_options.return_value = {"schema_translate_map": {None: "public"}}
    mock_session.connection.return_value = mock_conn

    def mock_execute(stmt, *args, **kwargs):
        sql_str = str(stmt)
        m = MagicMock()
        if "clock_timestamp" in sql_str:
            m.scalar.return_value = datetime.now(UTC)
            return m
        if "session_user" in sql_str or "current_user" in sql_str:
            m.one.return_value = ("conformly_app", "conformly_app")
            return m
        return m

    mock_session.execute.side_effect = mock_execute

    class ExplodingSink(DeniedAuditSink):
        def record_denial(
            self,
            actor_id: UUID,
            operation: str,
            reason_code: str,
            request_key: str,
            resource_type: str | None = None,
            resource_id: UUID | None = None,
        ) -> None:
            raise RuntimeError("AUDIT_STORAGE_UNAVAILABLE")

    exploding_sink = ExplodingSink()
    service = CatalogApplicabilityRuleDraftService(mock_session, denied_audit_sink=exploding_sink)

    actor_ctx = CatalogActorContext(
        actor_id=uuid4(),
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC),
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
        actor_kind=CatalogActorKind.PLATFORM_USER,
    )

    # 1. On create_rule_draft: sink failure is propagated, chained from CatalogSecurityError
    with pytest.raises(RuntimeError, match="AUDIT_STORAGE_UNAVAILABLE") as exc_create:
        service.create_rule_draft(
            context=actor_ctx,
            request_key="req-wrong-role-sink-fail",
            version_id=uuid4(),
            content_digest=b"\x00" * 32,
            payload={"rule_key": "synthetic_rule_dummy"},
        )
    assert exc_create.value.__cause__ is not None
    assert isinstance(exc_create.value.__cause__, CatalogSecurityError)
    assert "Unauthorized database connection role" in str(exc_create.value.__cause__)
    assert mock_session.rollback.called

    # 2. On get_rule_version: sink failure is propagated, chained from CatalogSecurityError
    with pytest.raises(RuntimeError, match="AUDIT_STORAGE_UNAVAILABLE") as exc_get:
        service.get_rule_version(
            context=actor_ctx,
            request_key="req-wrong-role-sink-fail-get",
            version_id=uuid4(),
        )
    assert exc_get.value.__cause__ is not None
    assert isinstance(exc_get.value.__cause__, CatalogSecurityError)
    assert "Unauthorized database connection role" in str(exc_get.value.__cause__)
    assert mock_session.rollback.called


def test_wrong_role_admission_with_working_sink_records_denial_and_raises_admission_error(
    monkeypatch,
):
    monkeypatch.setattr(
        CatalogApplicabilityRuleDraftService,
        "_verify_postgres_connection_admission",
        REAL_ADMISSION_GUARD,
    )
    """When admission rejects an unauthorized role and the sink works, denial is recorded and CatalogSecurityError raised."""
    mock_session = MagicMock(spec=Session)
    mock_bind = MagicMock()
    mock_bind.dialect.name = "postgresql"
    mock_session.bind = mock_bind
    mock_conn = MagicMock()
    mock_conn.get_execution_options.return_value = {"schema_translate_map": {None: "public"}}
    mock_session.connection.return_value = mock_conn

    def mock_execute(stmt, *args, **kwargs):
        sql_str = str(stmt)
        m = MagicMock()
        if "clock_timestamp" in sql_str:
            m.scalar.return_value = datetime.now(UTC)
            return m
        if "session_user" in sql_str or "current_user" in sql_str:
            m.one.return_value = ("conformly_app", "conformly_app")
            return m
        return m

    mock_session.execute.side_effect = mock_execute

    class RecordingSink(DeniedAuditSink):
        def __init__(self):
            self.denials = []

        def record_denial(
            self,
            actor_id: UUID,
            operation: str,
            reason_code: str,
            request_key: str,
            resource_type: str | None = None,
            resource_id: UUID | None = None,
        ) -> None:
            self.denials.append((actor_id, operation, reason_code, request_key))

    recording_sink = RecordingSink()
    service = CatalogApplicabilityRuleDraftService(mock_session, denied_audit_sink=recording_sink)

    actor_ctx = CatalogActorContext(
        actor_id=uuid4(),
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC),
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
        actor_kind=CatalogActorKind.PLATFORM_USER,
    )

    # 1. create_rule_draft
    with pytest.raises(CatalogSecurityError, match="Unauthorized database connection role"):
        service.create_rule_draft(
            context=actor_ctx,
            request_key="req-wrong-role-ok-sink",
            version_id=uuid4(),
            content_digest=b"\x00" * 32,
            payload={"rule_key": "synthetic_rule_dummy"},
        )
    assert len(recording_sink.denials) == 1
    assert recording_sink.denials[0][1] == "applicability_rule.create_draft"
    assert recording_sink.denials[0][2] == "SECURITY_ERROR"
    assert recording_sink.denials[0][3] == "req-wrong-role-ok-sink"

    # 2. get_rule_version
    with pytest.raises(CatalogSecurityError, match="Unauthorized database connection role"):
        service.get_rule_version(
            context=actor_ctx,
            request_key="req-wrong-role-ok-sink-get",
            version_id=uuid4(),
        )
    assert len(recording_sink.denials) == 2
    assert recording_sink.denials[1][1] == "applicability_rule.get_draft"
    assert recording_sink.denials[1][2] == "SECURITY_ERROR"
    assert recording_sink.denials[1][3] == "req-wrong-role-ok-sink-get"
