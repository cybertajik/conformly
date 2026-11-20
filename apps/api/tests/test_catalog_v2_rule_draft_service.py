"""Unit and service tests for CatalogApplicabilityRuleDraftService (WP-07E)."""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogActorKind,
    CatalogCapability,
    CatalogConflictError,
    CatalogInvariantError,
    CatalogNotFoundError,
    CatalogValidationError,
)
from conformly.catalog_v2.audit import (
    DeniedAuditSink,
)
from conformly.catalog_v2.digest import (
    canonical_json,
    compute_content_digest,
    compute_requirement_version_digest,
    compute_source_version_digest,
)
from conformly.catalog_v2.models import (
    CatalogApplicabilityRule,
    CatalogApplicabilityRuleVersion,
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
from conformly.catalog_v2.rule_static_validation import RuleValidationError
from conformly.catalog_v2.service_applicability_rules import (
    CatalogApplicabilityRuleDraftService,
)
from conformly.db.base import Base


@pytest.fixture
def sqlite_session():
    """In-memory SQLite session with all tables initialized."""
    engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture(autouse=True)
def stub_postgres_admission_for_sqlite(monkeypatch):
    """Stub real PostgreSQL role admission check for unit test SQLite fixtures."""
    monkeypatch.setattr(
        CatalogApplicabilityRuleDraftService,
        "_verify_postgres_connection_admission",
        lambda self: None,
    )


@pytest.fixture
def valid_actor_context():
    """Valid platform admin actor context with DRAFT_WRITE and DRAFT_READ."""
    return CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
        authenticated_at=datetime.now(UTC),
    )


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
    # Compute canonical source version digest (R2: use protected canonical function over full persisted scalars)
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
    # Compute canonical requirement version digest (R2: use protected canonical function over full persisted scalars + locators)
    # Source references for this requirement version (matches req_src_ref added below)
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


# ==============================================================================
# 1. Frozen Digest Vectors (WP-07C2 Section 4)
# ==============================================================================


def test_frozen_vector_1_and_meaning_bearing_mutation():
    """Verify WP-07C2 Vector 1 frozen digest and that any modification changes the digest."""
    ast1 = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": "00000000-0000-0000-0000-000000000005",
            "op": "EXISTS",
            "scope_type": "tenant",
        },
    }
    ast1_bytes = canonical_json(ast1).encode("utf-8")
    p1 = {
        "effective_from": None,
        "effective_until": None,
        "expression_ast_version": 1,
        "expression_canonical_hex": ast1_bytes.hex(),
        "fact_refs": [
            {
                "content_digest": (b"\x22" * 32).hex(),
                "fact_definition_version_id": "00000000-0000-0000-0000-000000000005",
                "sequence": 1,
            }
        ],
        "kind": "ApplicabilityRuleVersion",
        "predecessor_id": None,
        "predecessor_revision": None,
        "requirement_id": "00000000-0000-0000-0000-000000000002",
        "requirement_version_digest": (b"\x11" * 32).hex(),
        "requirement_version_id": "00000000-0000-0000-0000-000000000003",
        "revision": 1,
        "rule_id": "00000000-0000-0000-0000-000000000001",
        "rule_key": "synthetic_applicability",
        "source_refs": [
            {
                "content_digest": (b"\x33" * 32).hex(),
                "sequence": 1,
                "source_version_id": "00000000-0000-0000-0000-000000000007",
            }
        ],
        "status": "Draft",
        "version_label": "1.0.0",
    }
    digest1 = compute_content_digest(p1).hex()
    assert digest1 == "d08cbc02dd81e5ed5f4446bd147140e4a9c47dbb76fa358953e58d257206d3ff"

    # Meaning-bearing mutation changes digest
    p1_mutated = copy.deepcopy(p1)
    p1_mutated["version_label"] = "1.0.1"
    digest1_mut = compute_content_digest(p1_mutated).hex()
    assert digest1_mut != digest1


def test_frozen_vector_2_and_meaning_bearing_mutation():
    """Verify WP-07C2 Vector 2 frozen digest and that any modification changes the digest."""
    ast2 = {
        "ast_version": 1,
        "root": {
            "fact_definition_version_id": "00000000-0000-0000-0000-000000000006",
            "op": "IN",
            "scope_type": "service",
            "values": ["beta", "alpha"],
        },
    }
    ast2_bytes = canonical_json(ast2).encode("utf-8")
    p2 = {
        "effective_from": None,
        "effective_until": None,
        "expression_ast_version": 1,
        "expression_canonical_hex": ast2_bytes.hex(),
        "fact_refs": [
            {
                "content_digest": (b"\x55" * 32).hex(),
                "fact_definition_version_id": "00000000-0000-0000-0000-000000000006",
                "sequence": 1,
            }
        ],
        "kind": "ApplicabilityRuleVersion",
        "predecessor_id": "00000000-0000-0000-0000-000000000004",
        "predecessor_revision": 1,
        "requirement_id": "00000000-0000-0000-0000-000000000002",
        "requirement_version_digest": (b"\x44" * 32).hex(),
        "requirement_version_id": "00000000-0000-0000-0000-000000000008",
        "revision": 2,
        "rule_id": "00000000-0000-0000-0000-000000000001",
        "rule_key": "synthetic_applicability",
        "source_refs": [
            {
                "content_digest": (b"\x66" * 32).hex(),
                "sequence": 1,
                "source_version_id": "00000000-0000-0000-0000-000000000009",
            }
        ],
        "status": "Draft",
        "version_label": "2.0.0",
    }
    digest2 = compute_content_digest(p2).hex()
    assert digest2 == "4fd166f706e9070e6b3386bc752a7fd7e1d490a26d0d32c0a7eee86b08f2a86e"

    p2_mutated = copy.deepcopy(p2)
    p2_mutated["revision"] = 3
    digest2_mut = compute_content_digest(p2_mutated).hex()
    assert digest2_mut != digest2


# ==============================================================================
# 2. Complete Round-Trip Create and Get
# ==============================================================================


def test_create_rule_draft_revision_1_and_get(
    sqlite_session, valid_actor_context, synthetic_prereqs
):
    """Successfully create a revision 1 rule draft and retrieve it via get_rule_version."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    rule_id = uuid4()
    ver_id = uuid4()
    payload, digest = make_valid_rule_payload(synthetic_prereqs, rule_id=rule_id)

    snap = service.create_rule_draft(
        context=valid_actor_context,
        request_key="req-create-rule-1",
        version_id=ver_id,
        content_digest=digest,
        payload=payload,
    )

    assert snap.id == ver_id
    assert snap.rule_id == rule_id
    assert snap.rule_key == "synthetic_rule_sample"
    assert snap.revision == 1
    assert snap.version_label == "1.0.0"
    assert snap.predecessor_id is None
    assert snap.predecessor_revision is None
    assert snap.content_digest == digest
    assert snap.status == "Draft"
    assert len(snap.fact_refs) == 1
    assert len(snap.source_refs) == 1
    assert snap.expression_canonical_hex == payload["expression_canonical_hex"]

    # Verify get_rule_version returns identical snapshot
    got_snap = service.get_rule_version(
        context=valid_actor_context,
        request_key="req-get-rule-1",
        version_id=ver_id,
    )
    assert got_snap.id == snap.id
    assert got_snap.content_digest == snap.content_digest
    assert got_snap.rule_key == snap.rule_key


def test_create_rule_draft_revision_2_lineage(
    sqlite_session, valid_actor_context, synthetic_prereqs
):
    """Successfully append revision 2 pinning revision 1 as predecessor."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    rule_id = uuid4()
    v1_id = uuid4()
    p1, d1 = make_valid_rule_payload(synthetic_prereqs, rule_id=rule_id)

    service.create_rule_draft(
        context=valid_actor_context,
        request_key="req-v1",
        version_id=v1_id,
        content_digest=d1,
        payload=p1,
    )

    # Revision 2 payload
    v2_id = uuid4()
    p2 = copy.deepcopy(p1)
    p2["revision"] = 2
    p2["version_label"] = "2.0.0"
    p2["predecessor_id"] = str(v1_id).lower()
    p2["predecessor_revision"] = 1
    d2 = compute_content_digest(p2)

    snap2 = service.create_rule_draft(
        context=valid_actor_context,
        request_key="req-v2",
        version_id=v2_id,
        content_digest=d2,
        payload=p2,
    )

    assert snap2.id == v2_id
    assert snap2.revision == 2
    assert snap2.predecessor_id == v1_id
    assert snap2.predecessor_revision == 1


# ==============================================================================
# 3. Idempotency & Retries
# ==============================================================================


def test_identical_retry_returns_same_snapshot(
    sqlite_session, valid_actor_context, synthetic_prereqs
):
    """Same actor/key/operation identical retry returns freshly validated version."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    ver_id = uuid4()
    payload, digest = make_valid_rule_payload(synthetic_prereqs)

    snap1 = service.create_rule_draft(
        context=valid_actor_context,
        request_key="req-retry-key",
        version_id=ver_id,
        content_digest=digest,
        payload=payload,
    )

    snap2 = service.create_rule_draft(
        context=valid_actor_context,
        request_key="req-retry-key",
        version_id=ver_id,
        content_digest=digest,
        payload=payload,
    )

    assert snap1.id == snap2.id
    assert snap1.content_digest == snap2.content_digest

    # Exactly one version, one receipt, one event intent
    assert len(sqlite_session.execute(select(CatalogApplicabilityRuleVersion)).scalars().all()) == 1
    assert len(sqlite_session.execute(select(CatalogMutationReceipt)).scalars().all()) == 1
    assert len(sqlite_session.execute(select(CatalogEventIntent)).scalars().all()) == 1


def test_conflicting_retry_fails_with_conflict(
    sqlite_session, valid_actor_context, synthetic_prereqs
):
    """Same actor and request key with conflicting payload raises CatalogConflictError."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    ver_id = uuid4()
    p1, d1 = make_valid_rule_payload(synthetic_prereqs)

    service.create_rule_draft(
        context=valid_actor_context,
        request_key="req-conflict-key",
        version_id=ver_id,
        content_digest=d1,
        payload=p1,
    )

    p2 = copy.deepcopy(p1)
    p2["version_label"] = "1.0.1-conflicting"
    d2 = compute_content_digest(p2)

    with pytest.raises(CatalogConflictError):
        service.create_rule_draft(
            context=valid_actor_context,
            request_key="req-conflict-key",
            version_id=ver_id,
            content_digest=d2,
            payload=p2,
        )


def test_distinct_actors_sharing_raw_request_key_succeed(sqlite_session, synthetic_prereqs):
    """Two distinct actors submitting different drafts sharing same raw key succeed without intent collision."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    actor_a = CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
        authenticated_at=datetime.now(UTC),
    )
    actor_b = CatalogActorContext(
        actor_id=uuid4(),
        actor_kind=CatalogActorKind.PLATFORM_USER,
        is_platform_admin=True,
        mfa_verified=True,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
        authenticated_at=datetime.now(UTC),
    )

    shared_key = "shared-request-key-123"

    p_a, d_a = make_valid_rule_payload(synthetic_prereqs)
    snap_a = service.create_rule_draft(
        context=actor_a,
        request_key=shared_key,
        version_id=uuid4(),
        content_digest=d_a,
        payload=p_a,
    )

    p_b, d_b = make_valid_rule_payload(synthetic_prereqs)
    p_b["rule_key"] = "synthetic_rule_b_shared"
    d_b = compute_content_digest(p_b)
    snap_b = service.create_rule_draft(
        context=actor_b,
        request_key=shared_key,
        version_id=uuid4(),
        content_digest=d_b,
        payload=p_b,
    )

    assert snap_a.id != snap_b.id
    assert len(sqlite_session.execute(select(CatalogEventIntent)).scalars().all()) == 2


# ==============================================================================
# 4. Strict Input & Bounds Validation
# ==============================================================================


def test_invalid_rule_key_bounds(sqlite_session, valid_actor_context, synthetic_prereqs):
    """rule_key must start with synthetic_ and be between 11 and 64 characters."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    payload, digest = make_valid_rule_payload(synthetic_prereqs)

    # 1. Missing synthetic_ prefix
    p_bad = copy.deepcopy(payload)
    p_bad["rule_key"] = "plain_rule_key"
    d_bad = compute_content_digest(p_bad)
    with pytest.raises(CatalogValidationError, match="synthetic_"):
        service.create_rule_draft(
            context=valid_actor_context,
            request_key="req-k1",
            version_id=uuid4(),
            content_digest=d_bad,
            payload=p_bad,
        )

    # 2. Too short (<=10)
    p_short = copy.deepcopy(payload)
    p_short["rule_key"] = "synthetic_"
    d_short = compute_content_digest(p_short)
    with pytest.raises(CatalogValidationError, match="between 11 and 64"):
        service.create_rule_draft(
            context=valid_actor_context,
            request_key="req-k2",
            version_id=uuid4(),
            content_digest=d_short,
            payload=p_short,
        )

    # 3. Too long (>64)
    p_long = copy.deepcopy(payload)
    p_long["rule_key"] = "synthetic_" + "x" * 55  # 65 chars
    d_long = compute_content_digest(p_long)
    with pytest.raises(CatalogValidationError, match="between 11 and 64"):
        service.create_rule_draft(
            context=valid_actor_context,
            request_key="req-k3",
            version_id=uuid4(),
            content_digest=d_long,
            payload=p_long,
        )


def test_strict_date_validation_rejects_timestamps(
    sqlite_session, valid_actor_context, synthetic_prereqs
):
    """effective_from / effective_until strictly reject timestamps or non-canonical dates."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    payload, _ = make_valid_rule_payload(synthetic_prereqs)

    p_time = copy.deepcopy(payload)
    p_time["effective_from"] = "2026-10-20T00:00:00Z"
    d_time = compute_content_digest(p_time)
    with pytest.raises(CatalogValidationError, match="canonical YYYY-MM-DD"):
        service.create_rule_draft(
            context=valid_actor_context,
            request_key="req-date-1",
            version_id=uuid4(),
            content_digest=d_time,
            payload=p_time,
        )


def test_payload_size_limit_rejection(sqlite_session, valid_actor_context, synthetic_prereqs):
    """Payload canonical bytes > 262144 bytes is rejected."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    payload, _ = make_valid_rule_payload(synthetic_prereqs)

    p_big = copy.deepcopy(payload)
    p_big["version_label"] = "x" * 64
    # Pad fact_refs or version_label
    d_big = compute_content_digest(p_big)
    # Mock canonical_json to exceed limit
    from unittest.mock import patch

    with patch(
        "conformly.catalog_v2.service_applicability_rules.canonical_json", return_value=" " * 262145
    ):
        with pytest.raises(CatalogValidationError, match="exceeds maximum limit"):
            service.create_rule_draft(
                context=valid_actor_context,
                request_key="req-big",
                version_id=uuid4(),
                content_digest=d_big,
                payload=p_big,
            )


# ==============================================================================
# 5. Stored Aggregate Completeness & Tampering (R9 Parity)
# ==============================================================================


def test_stored_aggregate_tampering_raises_invariant_error(
    sqlite_session, valid_actor_context, synthetic_prereqs
):
    """Tampering with persisted row raises CatalogInvariantError even with stale ORM entity."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    ver_id = uuid4()
    payload, digest = make_valid_rule_payload(synthetic_prereqs)

    service.create_rule_draft(
        context=valid_actor_context,
        request_key="req-tamper",
        version_id=ver_id,
        content_digest=digest,
        payload=payload,
    )
    sqlite_session.commit()

    # Tamper with the database row directly
    sqlite_session.execute(
        update(CatalogApplicabilityRuleVersion)
        .where(CatalogApplicabilityRuleVersion.id == ver_id)
        .values(version_label="tampered")
    )
    sqlite_session.commit()
    sqlite_session.expire_all()

    # Reading with get_rule_version must fail closed with CatalogInvariantError
    with pytest.raises(CatalogInvariantError, match="Persisted content digest mismatch"):
        service.get_rule_version(
            context=valid_actor_context,
            request_key="req-tamper-get",
            version_id=ver_id,
        )


# ==============================================================================
# 6. Rollback Boundary & Durable Denial
# ==============================================================================


def test_failure_rolls_back_cleanly_and_records_denial(
    sqlite_session, valid_actor_context, synthetic_prereqs
):
    """Failed create rolls back completely without leaving orphan rows."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    ver_id = uuid4()
    payload, _ = make_valid_rule_payload(synthetic_prereqs)

    # Bad digest claim
    bad_digest = b"\xff" * 32
    with pytest.raises(CatalogValidationError, match="Claimed content_digest does not match"):
        service.create_rule_draft(
            context=valid_actor_context,
            request_key="req-fail-clean",
            version_id=ver_id,
            content_digest=bad_digest,
            payload=payload,
        )

    # Ensure no rows in rule or support tables
    assert len(sqlite_session.execute(select(CatalogApplicabilityRule)).scalars().all()) == 0
    assert len(sqlite_session.execute(select(CatalogApplicabilityRuleVersion)).scalars().all()) == 0
    assert len(sqlite_session.execute(select(CatalogMutationReceipt)).scalars().all()) == 0
    assert len(sqlite_session.execute(select(CatalogEventIntent)).scalars().all()) == 0


def test_exploding_denial_sink_propagates_visibly(
    sqlite_session, valid_actor_context, synthetic_prereqs
):
    """Failure in durable denial sink propagates visibly and is never swallowed."""

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
            raise RuntimeError("CRITICAL SINK DISK FULL")

    service = CatalogApplicabilityRuleDraftService(
        sqlite_session, denied_audit_sink=ExplodingSink()
    )
    payload, _ = make_valid_rule_payload(synthetic_prereqs)

    with pytest.raises(RuntimeError, match="CRITICAL SINK DISK FULL"):
        service.create_rule_draft(
            context=valid_actor_context,
            request_key="req-sink-fail",
            version_id=uuid4(),
            content_digest=b"\x00" * 32,
            payload=payload,
        )


def test_durable_denial_sink_failure_on_create_and_get_propagates_visibly_with_cause(
    sqlite_session, valid_actor_context, synthetic_prereqs
):
    """Sink failure on either create or get raises the sink exception chained from the domain error."""

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

    service = CatalogApplicabilityRuleDraftService(
        sqlite_session, denied_audit_sink=ExplodingSink()
    )
    payload, _ = make_valid_rule_payload(synthetic_prereqs)

    # 1. On create with invalid digest: sink explodes, chaining CatalogValidationError
    with pytest.raises(RuntimeError, match="AUDIT_STORAGE_UNAVAILABLE") as exc_info:
        service.create_rule_draft(
            context=valid_actor_context,
            request_key="req-sink-create-fail",
            version_id=uuid4(),
            content_digest=b"\x00" * 32,
            payload=payload,
        )
    assert exc_info.value.__cause__ is not None
    assert isinstance(exc_info.value.__cause__, CatalogValidationError)

    # Verify rollback invariant: no rule version or rule row created
    assert len(sqlite_session.execute(select(CatalogApplicabilityRuleVersion)).scalars().all()) == 0

    # 2. On get with non-existent version: sink explodes, chaining CatalogNotFoundError
    with pytest.raises(RuntimeError, match="AUDIT_STORAGE_UNAVAILABLE") as exc_info_get:
        service.get_rule_version(
            context=valid_actor_context,
            request_key="req-sink-get-fail",
            version_id=uuid4(),
        )
    assert exc_info_get.value.__cause__ is not None
    assert isinstance(exc_info_get.value.__cause__, CatalogNotFoundError)


def test_successful_durable_denial_records_event_and_propagates_original_error_on_create_and_get(
    sqlite_session, valid_actor_context, synthetic_prereqs
):
    """Working sink records denial event cleanly, while service propagates the original domain error."""

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

    sink = RecordingSink()
    service = CatalogApplicabilityRuleDraftService(sqlite_session, denied_audit_sink=sink)
    payload, _ = make_valid_rule_payload(synthetic_prereqs)

    # 1. Create with invalid digest
    with pytest.raises(CatalogValidationError, match="Claimed content_digest does not match"):
        service.create_rule_draft(
            context=valid_actor_context,
            request_key="req-valid-denial-create",
            version_id=uuid4(),
            content_digest=b"\x00" * 32,
            payload=payload,
        )
    assert len(sink.denials) == 1
    assert sink.denials[0][1] == "applicability_rule.create_draft"
    assert sink.denials[0][2] == "VALIDATION_ERROR"
    assert sink.denials[0][3] == "req-valid-denial-create"

    # 2. Get with non-existent version
    with pytest.raises(CatalogNotFoundError, match="not found"):
        service.get_rule_version(
            context=valid_actor_context,
            request_key="req-valid-denial-get",
            version_id=uuid4(),
        )
    assert len(sink.denials) == 2
    assert sink.denials[1][1] == "applicability_rule.get_draft"
    assert sink.denials[1][2] == "NOT_FOUND"
    assert sink.denials[1][3] == "req-valid-denial-get"


def test_corrupted_pinned_fact_rejected_on_get_and_identical_retry(
    sqlite_session, valid_actor_context, synthetic_prereqs
):
    """Corrupted pinned fact definition version is rejected on both get and identical retry."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    ver_id = uuid4()
    payload, digest = make_valid_rule_payload(synthetic_prereqs)

    service.create_rule_draft(
        context=valid_actor_context,
        request_key="req-corrupt-fact",
        version_id=ver_id,
        content_digest=digest,
        payload=payload,
    )
    sqlite_session.commit()

    # Corrupt the pinned fact definition version in SQLite DB
    sqlite_session.execute(
        update(CatalogFactDefinitionVersion)
        .where(CatalogFactDefinitionVersion.id == synthetic_prereqs["fact_definition_version_id"])
        .values(content_digest=b"\x99" * 32)
    )
    sqlite_session.commit()
    sqlite_session.expire_all()

    # get_rule_version must fail closed
    with pytest.raises(CatalogInvariantError, match="digest mismatch|tampering detected"):
        service.get_rule_version(
            context=valid_actor_context,
            request_key="req-corrupt-fact-get",
            version_id=ver_id,
        )

    # Identical retry must also fail closed
    with pytest.raises(
        (CatalogInvariantError, CatalogValidationError), match="digest mismatch|tampering detected"
    ):
        service.create_rule_draft(
            context=valid_actor_context,
            request_key="req-corrupt-fact",
            version_id=ver_id,
            content_digest=digest,
            payload=payload,
        )


def test_matching_digest_malformed_ast_rejected_on_get_and_retry(
    sqlite_session, valid_actor_context, synthetic_prereqs
):
    """Persisted rule version with invalid AST canonical bytes fails closed on get and retry."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    ver_id = uuid4()
    payload, digest = make_valid_rule_payload(synthetic_prereqs)

    service.create_rule_draft(
        context=valid_actor_context,
        request_key="req-bogus-ast",
        version_id=ver_id,
        content_digest=digest,
        payload=payload,
    )
    sqlite_session.commit()

    # Tamper with expression_canonical in DB to an invalid AST structure
    invalid_ast = {"ast_version": 99, "unknown_field": "bogus"}
    invalid_ast_bytes = canonical_json(invalid_ast).encode("utf-8")
    sqlite_session.execute(
        update(CatalogApplicabilityRuleVersion)
        .where(CatalogApplicabilityRuleVersion.id == ver_id)
        .values(expression_canonical=invalid_ast_bytes)
    )
    sqlite_session.commit()
    sqlite_session.expire_all()

    # get_rule_version must fail closed with Invariant or Validation error
    with pytest.raises((CatalogInvariantError, RuleValidationError)):
        service.get_rule_version(
            context=valid_actor_context,
            request_key="req-bogus-ast-get",
            version_id=ver_id,
        )

    # Identical retry must also fail closed
    with pytest.raises((CatalogInvariantError, RuleValidationError)):
        service.create_rule_draft(
            context=valid_actor_context,
            request_key="req-bogus-ast",
            version_id=ver_id,
            content_digest=digest,
            payload=payload,
        )


def test_wrong_canonical_source_and_requirement_digests_rejected(
    sqlite_session, valid_actor_context, synthetic_prereqs
):
    """Tampered source version or requirement version digest is rejected on get and retry."""
    service = CatalogApplicabilityRuleDraftService(sqlite_session)
    ver_id = uuid4()
    payload, digest = make_valid_rule_payload(synthetic_prereqs)

    service.create_rule_draft(
        context=valid_actor_context,
        request_key="req-tampered-src",
        version_id=ver_id,
        content_digest=digest,
        payload=payload,
    )
    sqlite_session.commit()

    # Tamper source version official_locator without recomputing digest
    sqlite_session.execute(
        update(CatalogSourceVersion)
        .where(CatalogSourceVersion.id == synthetic_prereqs["source_version_id"])
        .values(official_locator="tampered_locator")
    )
    sqlite_session.commit()
    sqlite_session.expire_all()

    with pytest.raises(CatalogInvariantError, match="SourceVersion digest tampering detected"):
        service.get_rule_version(
            context=valid_actor_context,
            request_key="req-tampered-src-get",
            version_id=ver_id,
        )

    with pytest.raises(
        (CatalogInvariantError, CatalogValidationError),
        match="SourceVersion digest tampering detected",
    ):
        service.create_rule_draft(
            context=valid_actor_context,
            request_key="req-tampered-src",
            version_id=ver_id,
            content_digest=digest,
            payload=payload,
        )
