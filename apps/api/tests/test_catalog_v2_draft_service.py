"""Comprehensive unit tests for CatalogDraftService operations, concurrency, and audit."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogCapability,
    CatalogConflictError,
    CatalogNotFoundError,
    CatalogPermissionDeniedError,
    CatalogSecurityError,
    CatalogValidationError,
)
from conformly.catalog_v2.audit import DatabaseCommittedDeniedAuditSink, LoggingDeniedAuditSink
from conformly.catalog_v2.models import (
    CatalogAuditEvent,
    CatalogMappingVersion,
    CatalogMutationReceipt,
    CatalogRequirementVersion,
    CatalogSourcePermissionGuard,
    CatalogSourcePermissionProposal,
    CatalogSourceProvenance,
)
from conformly.catalog_v2.service import CatalogDraftService
from conformly.db.base import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(
        engine,
        tables=[
            table for name, table in Base.metadata.tables.items() if name.startswith("catalog_")
        ],
    )
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def denied_sink():
    return LoggingDeniedAuditSink()


@pytest.fixture
def service(db_session: Session, denied_sink: LoggingDeniedAuditSink):
    return CatalogDraftService(session=db_session, denied_audit_sink=denied_sink)


@pytest.fixture
def admin_context():
    return CatalogActorContext(
        actor_id=uuid4(),
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC),
        capabilities=frozenset(
            {
                CatalogCapability.DRAFT_READ,
                CatalogCapability.DRAFT_WRITE,
                CatalogCapability.PERMISSION_DECIDE,
            }
        ),
    )


# -----------------------------------------------------------------------------
# 1. Actor Verification Tests
# -----------------------------------------------------------------------------


def test_actor_missing_context(service: CatalogDraftService, denied_sink: LoggingDeniedAuditSink):
    """Missing actor context is denied and logged to denied sink."""
    with pytest.raises(CatalogSecurityError, match="Missing catalog actor context"):
        service.create_publisher(None, "req-1", "pub-1", "Publisher 1")  # type: ignore


def test_actor_missing_mfa(
    service: CatalogDraftService,
    admin_context: CatalogActorContext,
    denied_sink: LoggingDeniedAuditSink,
):
    """Actor without verified MFA is denied and recorded in the denial sink."""
    no_mfa = CatalogActorContext(
        actor_id=admin_context.actor_id,
        is_platform_admin=True,
        mfa_verified=False,
        authenticated_at=datetime.now(UTC),
        capabilities=admin_context.capabilities,
    )
    with pytest.raises(CatalogSecurityError, match="Verified MFA required"):
        service.create_publisher(no_mfa, "req-2", "pub-2", "Publisher 2")

    assert len(denied_sink.recorded_denials) == 1
    assert denied_sink.recorded_denials[0]["operation"] == "create_publisher"
    assert denied_sink.recorded_denials[0]["reason_code"] == "CatalogSecurityError"


def test_actor_stale_authentication(
    service: CatalogDraftService, admin_context: CatalogActorContext
):
    """Authentication older than 15 minutes is rejected."""
    stale = CatalogActorContext(
        actor_id=admin_context.actor_id,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC) - timedelta(minutes=16),
        capabilities=admin_context.capabilities,
    )
    with pytest.raises(CatalogSecurityError, match="age exceeds 15 minutes"):
        service.create_publisher(stale, "req-3", "pub-3", "Publisher 3")


def test_actor_future_authentication(
    service: CatalogDraftService, admin_context: CatalogActorContext
):
    """Authentication in the future is rejected."""
    future = CatalogActorContext(
        actor_id=admin_context.actor_id,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC) + timedelta(minutes=5),
        capabilities=admin_context.capabilities,
    )
    with pytest.raises(CatalogSecurityError, match="cannot be in the future"):
        service.create_publisher(future, "req-4", "pub-4", "Publisher 4")


def test_actor_missing_capability(service: CatalogDraftService, admin_context: CatalogActorContext):
    """Actor missing DRAFT_WRITE cannot perform mutations."""
    read_only = CatalogActorContext(
        actor_id=admin_context.actor_id,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC),
        capabilities=frozenset({CatalogCapability.DRAFT_READ}),
    )
    with pytest.raises(CatalogSecurityError, match="Missing required capability"):
        service.create_publisher(read_only, "req-5", "pub-5", "Publisher 5")


# -----------------------------------------------------------------------------
# 2. Publisher and Source Lifecycle with Guard and Atomicity
# -----------------------------------------------------------------------------


def test_create_publisher_and_source_atomic(
    service: CatalogDraftService, db_session: Session, admin_context: CatalogActorContext
):
    """Creating publisher and source creates domain rows, guard, audit event, intent, and receipt."""
    pub = service.create_publisher(admin_context, "req-pub-1", "pub-soc2", "SOC2 Publisher")
    assert pub.publisher_key == "pub-soc2"

    src = service.create_source(
        admin_context, "req-src-1", pub.id, "src-soc2-tsc", "SOC2 Trust Services Criteria"
    )
    assert src.source_key == "src-soc2-tsc"

    # Verify source permission guard was created in the same transaction
    guard = db_session.get(CatalogSourcePermissionGuard, src.id)
    assert guard is not None
    assert guard.revision == 1

    # Verify audit events
    audit_events = db_session.execute(select(CatalogAuditEvent)).scalars().all()
    assert len(audit_events) == 2
    assert audit_events[0].action == "publisher.created"
    assert audit_events[1].action == "source.created"

    # Verify receipts
    receipts = db_session.execute(select(CatalogMutationReceipt)).scalars().all()
    assert len(receipts) == 2


# -----------------------------------------------------------------------------
# 3. Source Version Optimistic Concurrency and Digests
# -----------------------------------------------------------------------------


def test_source_version_create_and_update_concurrency(
    service: CatalogDraftService, db_session: Session, admin_context: CatalogActorContext
):
    """Updating a source version requires store permission, matching expected revision and digest; conflicts are rejected."""
    pub = service.create_publisher(admin_context, "req-p", "p-iso", "ISO Publisher")
    src = service.create_source(admin_context, "req-s", pub.id, "s-iso27001", "ISO 27001")

    sv1 = service.create_source_version(
        admin_context, "req-sv-1", src.id, edition="2022", language="en"
    )
    assert sv1.revision == 1
    assert len(sv1.content_digest) == 32
    initial_digest = sv1.content_digest

    # 0. Update without permission fails closed (P1 Finding 5)
    with pytest.raises(CatalogPermissionDeniedError):
        service.update_source_version(
            admin_context,
            "req-sv-u0",
            sv1.id,
            expected_revision=1,
            expected_digest=initial_digest,
            edition="2022-amend",
        )

    # Add provenance, proposal, and Allowed decision for use_case='store'
    now = datetime.now(UTC)
    prov = CatalogSourceProvenance(
        source_version_id=sv1.id,
        source_revision=1,
        content_sha256=initial_digest,
        content_size=100,
        mime_type="application/pdf",
        locator="https://iso.org/standards/27001",
        retrieved_at=now,
        recorded_by_actor_id=uuid4(),
    )
    db_session.add(prov)
    db_session.flush()

    prop = CatalogSourcePermissionProposal(
        provenance_id=prov.id,
        source_version_id=sv1.id,
        use_case="store",
        scope_key="global",
        sequence=1,
        proposed_outcome="Allowed",
        conditions_state="None",
        recorded_by_actor_id=uuid4(),
    )
    db_session.add(prop)
    db_session.flush()

    service.create_permission_decision(
        admin_context,
        "req-dec-store",
        src.id,
        sv1.id,
        prop.id,
        use_case="store",
        scope_key="global",
        decision_type="Allowed",
        valid_from=now - timedelta(minutes=5),
        valid_until=None,
        evidence_reference="STORE-PERMITTED",
    )

    # 1. Update with wrong revision -> conflict
    with pytest.raises(CatalogConflictError, match="revision conflict"):
        service.update_source_version(
            admin_context,
            "req-sv-u1",
            sv1.id,
            expected_revision=99,
            expected_digest=initial_digest,
            edition="2022-amend",
        )

    # 2. Update with wrong digest -> conflict
    with pytest.raises(CatalogConflictError, match="content digest conflict"):
        service.update_source_version(
            admin_context,
            "req-sv-u2",
            sv1.id,
            expected_revision=1,
            expected_digest=b"0" * 32,
            edition="2022-amend",
        )

    # 3. Valid update
    sv_updated = service.update_source_version(
        admin_context,
        "req-sv-u3",
        sv1.id,
        expected_revision=1,
        expected_digest=initial_digest,
        edition="2022-amend",
    )
    assert sv_updated.revision == 2
    assert sv_updated.edition == "2022-amend"
    assert sv_updated.content_digest != initial_digest


# -----------------------------------------------------------------------------
# 4. Requirement and Control with Permission Matrix and References
# -----------------------------------------------------------------------------


def test_requirement_version_source_permission_enforcement(
    service: CatalogDraftService, db_session: Session, admin_context: CatalogActorContext
):
    """Creating a requirement version requires effective source permission on referenced sources."""
    pub = service.create_publisher(admin_context, "req-p2", "p-nist", "NIST")
    src = service.create_source(admin_context, "req-s2", pub.id, "s-800-53", "NIST SP 800-53")
    sv = service.create_source_version(admin_context, "req-sv2", src.id, edition="Rev 5")
    req = service.create_requirement(admin_context, "req-r1", src.id, "req-ac-1", "Access Control")
    db_session.commit()

    ref_payload = [
        {
            "source_version_id": sv.id,
            "locator_kind": "section",
            "locator_value": "AC-1",
            "sequence": 1,
        }
    ]

    # Without an Allowed permission decision, creating the requirement version fails closed
    with pytest.raises(CatalogPermissionDeniedError):
        service.create_requirement_version(
            admin_context,
            "req-rv-fail",
            req.id,
            sv.id,
            "v1.0",
            normalized_outcome="Must establish policy",
            requirement_type="mandatory",
            obligated_actor="Admin",
            text_origin="reference_only",
            source_references=ref_payload,
        )

    # Add proposal and decision
    now = datetime.now(UTC)
    prov = CatalogSourceProvenance(
        source_version_id=sv.id,
        source_revision=1,
        content_sha256=b"1" * 32,
        content_size=10,
        mime_type="text/plain",
        locator="https://csrc.nist.gov",
        retrieved_at=now,
        recorded_by_actor_id=uuid4(),
    )
    db_session.add(prov)
    db_session.flush()

    prop = CatalogSourcePermissionProposal(
        provenance_id=prov.id,
        source_version_id=sv.id,
        use_case="reference",
        scope_key="global",
        sequence=1,
        proposed_outcome="Allowed",
        conditions_state="None",
        recorded_by_actor_id=uuid4(),
    )
    db_session.add(prop)
    db_session.flush()

    service.create_permission_decision(
        admin_context,
        "req-dec-1",
        src.id,
        sv.id,
        prop.id,
        use_case="reference",
        scope_key="global",
        decision_type="Allowed",
        valid_from=now - timedelta(minutes=5),
        valid_until=None,
        evidence_reference="PUBLIC-DOMAIN-DETERMINATION",
    )

    # Now creating the requirement version succeeds
    rv = service.create_requirement_version(
        admin_context,
        "req-rv-ok",
        req.id,
        sv.id,
        "v1.0",
        normalized_outcome="Must establish policy",
        requirement_type="mandatory",
        obligated_actor="Admin",
        text_origin="reference_only",
        source_references=ref_payload,
    )
    assert rv.revision == 1
    assert len(rv.content_digest) == 32


# -----------------------------------------------------------------------------
# 5. Mapping Version Pin Invariants
# -----------------------------------------------------------------------------


def test_mapping_version_endpoint_pins(
    service: CatalogDraftService, db_session: Session, admin_context: CatalogActorContext
):
    """Mapping version pins exact requirement and control version revision and digest."""
    pub = service.create_publisher(admin_context, "p-map", "pub-m", "M Pub")
    src = service.create_source(admin_context, "s-map", pub.id, "src-m", "M Source")
    sv = service.create_source_version(admin_context, "sv-map", src.id, edition="1")

    # Add permission decision for reference & map
    now = datetime.now(UTC)
    prov = CatalogSourceProvenance(
        source_version_id=sv.id,
        source_revision=1,
        content_sha256=b"2" * 32,
        content_size=10,
        mime_type="text/plain",
        locator="https://loc",
        retrieved_at=now,
        recorded_by_actor_id=uuid4(),
    )
    db_session.add(prov)
    db_session.flush()
    prop_ref = CatalogSourcePermissionProposal(
        provenance_id=prov.id,
        source_version_id=sv.id,
        use_case="reference",
        scope_key="global",
        sequence=1,
        proposed_outcome="Allowed",
        conditions_state="None",
        recorded_by_actor_id=uuid4(),
    )
    prop_map = CatalogSourcePermissionProposal(
        provenance_id=prov.id,
        source_version_id=sv.id,
        use_case="map",
        scope_key="global",
        sequence=1,
        proposed_outcome="Allowed",
        conditions_state="None",
        recorded_by_actor_id=uuid4(),
    )
    db_session.add(prop_ref)
    db_session.add(prop_map)
    db_session.flush()

    service.create_permission_decision(
        admin_context,
        "dec-ref",
        src.id,
        sv.id,
        prop_ref.id,
        "reference",
        "global",
        "Allowed",
        now - timedelta(minutes=5),
        None,
        "REF-APPROVAL",
    )
    service.create_permission_decision(
        admin_context,
        "dec-map",
        src.id,
        sv.id,
        prop_map.id,
        "map",
        "global",
        "Allowed",
        now - timedelta(minutes=5),
        None,
        "MAP-APPROVAL",
    )

    req = service.create_requirement(admin_context, "r-map", src.id, "req-m-1", "Domain A")
    rv = service.create_requirement_version(
        admin_context,
        "rv-map",
        req.id,
        sv.id,
        "v1",
        "Outcome",
        "mandatory",
        "User",
        "reference_only",
        [
            {
                "source_version_id": sv.id,
                "locator_kind": "section",
                "locator_value": "1",
                "sequence": 1,
            }
        ],
    )

    ctrl = service.create_common_control(admin_context, "ctrl-map", "CC-AC-001", "Access Control")
    cv = service.create_control_version(
        admin_context, "cv-map", ctrl.id, "v1", "Control Title", "Objective"
    )

    mapping = service.create_mapping(admin_context, "map-create", req.id, ctrl.id)

    # 1. Pinned requirement revision mismatch
    with pytest.raises(CatalogConflictError, match="Pinned requirement version revision mismatch"):
        service.create_mapping_version(
            admin_context,
            "mv-pin-fail-1",
            mapping.id,
            rv.id,
            cv.id,
            expected_req_revision=99,
            expected_req_digest=rv.content_digest,
            expected_ctrl_revision=1,
            expected_ctrl_digest=cv.content_digest,
            version_label="v1",
            mapping_type="Full",
            rationale="Test",
            source_basis="expert_analysis",
            confidence="high",
        )

    # 2. Pinned requirement digest mismatch
    with pytest.raises(CatalogConflictError, match="Pinned requirement version digest mismatch"):
        service.create_mapping_version(
            admin_context,
            "mv-pin-fail-2",
            mapping.id,
            rv.id,
            cv.id,
            expected_req_revision=1,
            expected_req_digest=b"x" * 32,
            expected_ctrl_revision=1,
            expected_ctrl_digest=cv.content_digest,
            version_label="v1",
            mapping_type="Full",
            rationale="Test",
            source_basis="expert_analysis",
            confidence="high",
        )

    # 3. Successful mapping with correct pins
    mv = service.create_mapping_version(
        admin_context,
        "mv-pin-ok",
        mapping.id,
        rv.id,
        cv.id,
        expected_req_revision=1,
        expected_req_digest=rv.content_digest,
        expected_ctrl_revision=1,
        expected_ctrl_digest=cv.content_digest,
        version_label="v1",
        mapping_type="Full",
        rationale="Test",
        source_basis="expert_analysis",
        confidence="high",
    )
    assert mv.revision == 1
    assert len(mv.content_digest) == 32


# -----------------------------------------------------------------------------
# 6. Idempotency and Exact Retries
# -----------------------------------------------------------------------------


def test_mutation_idempotency_and_conflict(
    service: CatalogDraftService, admin_context: CatalogActorContext
):
    """Exact retry returns cached result idempotently; changed parameters cause conflict."""
    # First attempt: succeeds
    p1 = service.create_publisher(admin_context, "req-idem-1", "pub-idem", "Idempotent Publisher")

    # Exact retry with same request_key and parameters: succeeds idempotently
    p2 = service.create_publisher(admin_context, "req-idem-1", "pub-idem", "Idempotent Publisher")
    assert p1.id == p2.id

    # Retry with same request_key but different name: raises ConflictError
    with pytest.raises(CatalogConflictError, match="conflicting request parameters"):
        service.create_publisher(admin_context, "req-idem-1", "pub-idem", "Different Name")


# -----------------------------------------------------------------------------
# 7. Bounded Queries and Inaccessible Objects
# -----------------------------------------------------------------------------


def test_bounded_queries(
    service: CatalogDraftService,
    admin_context: CatalogActorContext,
    db_session: Session,
):
    """List operations cap results at 100 max and default to 50, filtering by permitted versions."""
    pub = service.create_publisher(
        admin_context, "req-pub-bounded", "pub-bounded", "Publisher Bounded"
    )
    now = datetime.now(UTC)

    # Create 3 permitted sources with versions and allowed reference decisions
    for i in range(3):
        src = service.create_source(
            admin_context,
            f"req-src-bounded-{i}",
            pub.id,
            f"src-bounded-{i}",
            f"Source Bounded {i}",
        )
        sv = service.create_source_version(
            admin_context, f"req-sv-bounded-{i}", src.id, edition=f"ed-{i}"
        )
        prov = CatalogSourceProvenance(
            source_version_id=sv.id,
            source_revision=1,
            content_sha256=sv.content_digest,
            content_size=50,
            mime_type="text/plain",
            locator=f"https://example.com/bounded-{i}",
            retrieved_at=now,
            recorded_by_actor_id=uuid4(),
        )
        db_session.add(prov)
        db_session.flush()

        prop = CatalogSourcePermissionProposal(
            provenance_id=prov.id,
            source_version_id=sv.id,
            use_case="reference",
            scope_key="global",
            sequence=1,
            proposed_outcome="Allowed",
            review_state="Draft",
            conditions_state="None",
            recorded_by_actor_id=uuid4(),
        )
        db_session.add(prop)
        db_session.flush()

        service.create_permission_decision(
            admin_context,
            f"req-dec-bounded-{i}",
            src.id,
            sv.id,
            prop.id,
            use_case="reference",
            scope_key="global",
            decision_type="Allowed",
            valid_from=now - timedelta(minutes=5),
            valid_until=None,
            evidence_reference=f"EV-BOUNDED-{i}",
        )

    sources = service.list_sources(admin_context, limit=2)
    assert len(sources) == 2
    offset_sources = service.list_sources(admin_context, limit=2, offset=2)
    assert len(offset_sources) >= 1


def test_source_and_requirement_permission_filtering(
    service: CatalogDraftService,
    admin_context: CatalogActorContext,
    db_session: Session,
):
    """Stable source and requirement getters and lists filter unauthorized records before returning."""
    pub = service.create_publisher(
        admin_context, "req-pub-filter", "pub-filter", "Publisher Filter"
    )
    now = datetime.now(UTC)

    # 1. Source with absent decision
    src_absent = service.create_source(
        admin_context, "req-s-absent", pub.id, "src-absent", "Source Absent"
    )
    sv_absent = service.create_source_version(
        admin_context, "req-sv-absent", src_absent.id, edition="v1"
    )

    # 2. Source with Denied decision
    src_denied = service.create_source(
        admin_context, "req-s-denied", pub.id, "src-denied", "Source Denied"
    )
    sv_denied = service.create_source_version(
        admin_context, "req-sv-denied", src_denied.id, edition="v1"
    )
    prov_denied = CatalogSourceProvenance(
        source_version_id=sv_denied.id,
        source_revision=1,
        content_sha256=sv_denied.content_digest,
        content_size=10,
        mime_type="text/plain",
        locator="https://example.com/denied",
        retrieved_at=now,
        recorded_by_actor_id=uuid4(),
    )
    db_session.add(prov_denied)
    db_session.flush()
    prop_denied = CatalogSourcePermissionProposal(
        provenance_id=prov_denied.id,
        source_version_id=sv_denied.id,
        use_case="reference",
        scope_key="global",
        sequence=1,
        proposed_outcome="Denied",
        review_state="Draft",
        conditions_state="None",
        recorded_by_actor_id=uuid4(),
    )
    db_session.add(prop_denied)
    db_session.flush()
    service.create_permission_decision(
        admin_context,
        "req-dec-denied",
        src_denied.id,
        sv_denied.id,
        prop_denied.id,
        use_case="reference",
        scope_key="global",
        decision_type="Denied",
        valid_from=now - timedelta(days=1),
        valid_until=None,
        evidence_reference="EV-DENIED",
    )

    # 3. Source with Expired decision
    src_expired = service.create_source(
        admin_context, "req-s-expired", pub.id, "src-expired", "Source Expired"
    )
    sv_expired = service.create_source_version(
        admin_context, "req-sv-expired", src_expired.id, edition="v1"
    )
    prov_expired = CatalogSourceProvenance(
        source_version_id=sv_expired.id,
        source_revision=1,
        content_sha256=sv_expired.content_digest,
        content_size=10,
        mime_type="text/plain",
        locator="https://example.com/expired",
        retrieved_at=now,
        recorded_by_actor_id=uuid4(),
    )
    db_session.add(prov_expired)
    db_session.flush()
    prop_expired = CatalogSourcePermissionProposal(
        provenance_id=prov_expired.id,
        source_version_id=sv_expired.id,
        use_case="reference",
        scope_key="global",
        sequence=1,
        proposed_outcome="Allowed",
        review_state="Draft",
        conditions_state="None",
        recorded_by_actor_id=uuid4(),
    )
    db_session.add(prop_expired)
    db_session.flush()
    service.create_permission_decision(
        admin_context,
        "req-dec-expired",
        src_expired.id,
        sv_expired.id,
        prop_expired.id,
        use_case="reference",
        scope_key="global",
        decision_type="Allowed",
        valid_from=now - timedelta(days=2),
        valid_until=now - timedelta(days=1),
        evidence_reference="EV-EXPIRED",
    )

    # 4. Source with Allowed, active decision
    src_allowed = service.create_source(
        admin_context, "req-s-allowed", pub.id, "src-allowed", "Source Allowed"
    )
    sv_allowed = service.create_source_version(
        admin_context, "req-sv-allowed", src_allowed.id, edition="v1"
    )
    prov_allowed = CatalogSourceProvenance(
        source_version_id=sv_allowed.id,
        source_revision=1,
        content_sha256=sv_allowed.content_digest,
        content_size=10,
        mime_type="text/plain",
        locator="https://example.com/allowed",
        retrieved_at=now,
        recorded_by_actor_id=uuid4(),
    )
    db_session.add(prov_allowed)
    db_session.flush()
    prop_allowed = CatalogSourcePermissionProposal(
        provenance_id=prov_allowed.id,
        source_version_id=sv_allowed.id,
        use_case="reference",
        scope_key="global",
        sequence=1,
        proposed_outcome="Allowed",
        review_state="Draft",
        conditions_state="None",
        recorded_by_actor_id=uuid4(),
    )
    db_session.add(prop_allowed)
    db_session.flush()
    service.create_permission_decision(
        admin_context,
        "req-dec-allowed",
        src_allowed.id,
        sv_allowed.id,
        prop_allowed.id,
        use_case="reference",
        scope_key="global",
        decision_type="Allowed",
        valid_from=now - timedelta(minutes=5),
        valid_until=None,
        evidence_reference="EV-ALLOWED",
    )

    # Verify get_source permission filtering
    with pytest.raises(CatalogNotFoundError, match="Source not found"):
        service.get_source(admin_context, src_absent.id)

    with pytest.raises(CatalogNotFoundError, match="Source not found"):
        service.get_source(admin_context, src_denied.id)

    with pytest.raises(CatalogNotFoundError, match="Source not found"):
        service.get_source(admin_context, src_expired.id)

    # Allowed source is successfully retrieved
    retrieved_src = service.get_source(admin_context, src_allowed.id)
    assert retrieved_src.id == src_allowed.id

    # Verify list_sources filtering
    listed_sources = service.list_sources(admin_context, limit=50)
    listed_ids = {s.id for s in listed_sources}
    assert src_allowed.id in listed_ids
    assert src_absent.id not in listed_ids
    assert src_denied.id not in listed_ids
    assert src_expired.id not in listed_ids

    # --- Requirements filtering ---
    # Create requirements under each source
    req_no_version = service.create_requirement(
        admin_context, "req-r-no-ver", src_allowed.id, "req-no-version"
    )
    req_absent = service.create_requirement(
        admin_context, "req-r-absent", src_absent.id, "req-absent"
    )
    req_denied = service.create_requirement(
        admin_context, "req-r-denied", src_denied.id, "req-denied"
    )
    req_expired = service.create_requirement(
        admin_context, "req-r-expired", src_expired.id, "req-expired"
    )
    req_allowed = service.create_requirement(
        admin_context, "req-r-allowed", src_allowed.id, "req-allowed"
    )

    # Create requirement versions
    # For absent/denied/expired, insert requirement version directly to test filtering
    rv_absent = CatalogRequirementVersion(
        id=uuid4(),
        requirement_id=req_absent.id,
        source_id=src_absent.id,
        source_version_id=sv_absent.id,
        version_label="v1.0",
        normalized_outcome="outcome",
        requirement_type="mandatory",
        obligated_actor="Admin",
        text_origin="reference_only",
        revision=1,
    )
    rv_denied = CatalogRequirementVersion(
        id=uuid4(),
        requirement_id=req_denied.id,
        source_id=src_denied.id,
        source_version_id=sv_denied.id,
        version_label="v1.0",
        normalized_outcome="outcome",
        requirement_type="mandatory",
        obligated_actor="Admin",
        text_origin="reference_only",
        revision=1,
    )
    rv_expired = CatalogRequirementVersion(
        id=uuid4(),
        requirement_id=req_expired.id,
        source_id=src_expired.id,
        source_version_id=sv_expired.id,
        version_label="v1.0",
        normalized_outcome="outcome",
        requirement_type="mandatory",
        obligated_actor="Admin",
        text_origin="reference_only",
        revision=1,
    )
    db_session.add_all([rv_absent, rv_denied, rv_expired])
    db_session.flush()

    # Allowed requirement version created through service
    ref_allowed = [
        {
            "source_version_id": sv_allowed.id,
            "locator_kind": "section",
            "locator_value": "1.1",
            "sequence": 1,
        }
    ]
    service.create_requirement_version(
        admin_context,
        "req-rv-allowed",
        req_allowed.id,
        sv_allowed.id,
        "v1.0",
        "Allowed requirement outcome",
        "mandatory",
        "Admin",
        "reference_only",
        ref_allowed,
    )

    # Verify get_requirement permission filtering
    with pytest.raises(CatalogNotFoundError, match="Requirement not found"):
        service.get_requirement(admin_context, req_no_version.id)

    with pytest.raises(CatalogNotFoundError, match="Requirement not found"):
        service.get_requirement(admin_context, req_absent.id)

    with pytest.raises(CatalogNotFoundError, match="Requirement not found"):
        service.get_requirement(admin_context, req_denied.id)

    with pytest.raises(CatalogNotFoundError, match="Requirement not found"):
        service.get_requirement(admin_context, req_expired.id)

    # Allowed requirement is successfully retrieved
    retrieved_req = service.get_requirement(admin_context, req_allowed.id)
    assert retrieved_req.id == req_allowed.id

    # Verify list_requirements filtering
    listed_reqs = service.list_requirements(admin_context, limit=50)
    listed_req_ids = {r.id for r in listed_reqs}
    assert req_allowed.id in listed_req_ids
    assert req_no_version.id not in listed_req_ids
    assert req_absent.id not in listed_req_ids
    assert req_denied.id not in listed_req_ids
    assert req_expired.id not in listed_req_ids

    # Verify list_requirements with source_id
    scoped_allowed = service.list_requirements(admin_context, source_id=src_allowed.id, limit=50)
    assert [r.id for r in scoped_allowed] == [req_allowed.id]

    scoped_denied = service.list_requirements(admin_context, source_id=src_denied.id, limit=50)
    assert len(scoped_denied) == 0


def test_replace_requirement_source_references(
    service: CatalogDraftService,
    admin_context: CatalogActorContext,
    db_session: Session,
):
    """Replacing requirement source references updates revision and digest atomically."""
    pub = service.create_publisher(admin_context, "req-pub-rep", "pub-rep", "Publisher Rep")
    src = service.create_source(admin_context, "req-src-rep", pub.id, "src-rep", "Source Rep")
    sv1 = service.create_source_version(admin_context, "req-sv-rep1", src.id, edition="1.0")
    sv2 = service.create_source_version(admin_context, "req-sv-rep2", src.id, edition="2.0")

    now = datetime.now(UTC)
    for sv_item in (sv1, sv2):
        prov = CatalogSourceProvenance(
            source_version_id=sv_item.id,
            source_revision=1,
            content_sha256=sv_item.content_digest,
            content_size=20,
            mime_type="text/plain",
            locator=f"https://example.com/rep-{sv_item.edition}",
            retrieved_at=now,
            recorded_by_actor_id=uuid4(),
        )
        db_session.add(prov)
        db_session.flush()
        prop = CatalogSourcePermissionProposal(
            provenance_id=prov.id,
            source_version_id=sv_item.id,
            use_case="reference",
            scope_key="global",
            sequence=1,
            proposed_outcome="Allowed",
            review_state="Draft",
            conditions_state="None",
            recorded_by_actor_id=uuid4(),
        )
        db_session.add(prop)
        db_session.flush()
        service.create_permission_decision(
            admin_context,
            f"req-dec-rep-{sv_item.edition}",
            src.id,
            sv_item.id,
            prop.id,
            use_case="reference",
            scope_key="global",
            decision_type="Allowed",
            valid_from=now - timedelta(minutes=5),
            valid_until=None,
            evidence_reference=f"EV-REP-{sv_item.edition}",
        )

    req = service.create_requirement(admin_context, "req-r-rep", src.id, "req-rep-key")
    initial_refs = [
        {
            "source_version_id": sv1.id,
            "locator_kind": "section",
            "locator_value": "1.0",
            "sequence": 1,
        }
    ]
    rv = service.create_requirement_version(
        admin_context,
        "req-rv-rep-init",
        req.id,
        sv1.id,
        "v1.0",
        "Initial outcome",
        "mandatory",
        "Admin",
        "reference_only",
        initial_refs,
    )
    assert rv.revision == 1
    old_digest = rv.content_digest

    # Replace with new references
    new_refs = [
        {
            "source_version_id": sv1.id,
            "locator_kind": "section",
            "locator_value": "2.0",
            "sequence": 1,
        },
        {
            "source_version_id": sv1.id,
            "locator_kind": "paragraph",
            "locator_value": "p3",
            "sequence": 2,
        },
    ]
    updated_rv = service.replace_requirement_source_references(
        admin_context,
        "req-replace-success",
        rv.id,
        expected_revision=1,
        expected_digest=old_digest,
        new_source_references=new_refs,
    )
    assert updated_rv.revision == 2
    assert updated_rv.content_digest != old_digest

    # Empty source references raises CatalogValidationError
    with pytest.raises(CatalogValidationError, match="At least one source reference is required"):
        service.replace_requirement_source_references(
            admin_context,
            "req-replace-empty",
            rv.id,
            expected_revision=2,
            expected_digest=updated_rv.content_digest,
            new_source_references=[],
        )

    # Stale revision conflict check
    with pytest.raises(CatalogConflictError, match="revision conflict"):
        service.replace_requirement_source_references(
            admin_context,
            "req-replace-stale",
            rv.id,
            expected_revision=1,
            expected_digest=old_digest,
            new_source_references=new_refs,
        )


def test_exact_and_mapping_queries_sql_filtering_and_durable_denial_audit(
    service: CatalogDraftService,
    admin_context: CatalogActorContext,
    db_session: Session,
):
    """Exact source, requirement, and mapping version getters and lists enforce SQL pre-filtering; durable denial auditing separately commits."""
    pub = service.create_publisher(
        admin_context, "req-pub-exact-filter", "pub-exact-filter", "Publisher Exact Filter"
    )
    now = datetime.now(UTC)

    # Setup source and 5 source versions:
    # 1. absent decision
    # 2. denied decision
    # 3. expired decision
    # 4. superseded decision (sequence 1 Allowed, sequence 2 Denied)
    # 5. active allowed decision
    src = service.create_source(admin_context, "req-s-exact", pub.id, "src-exact", "Source Exact")
    sv_absent = service.create_source_version(
        admin_context, "req-sv-e-absent", src.id, edition="v-absent"
    )
    sv_denied = service.create_source_version(
        admin_context, "req-sv-e-denied", src.id, edition="v-denied"
    )
    sv_expired = service.create_source_version(
        admin_context, "req-sv-e-expired", src.id, edition="v-expired"
    )
    sv_superseded = service.create_source_version(
        admin_context, "req-sv-e-superseded", src.id, edition="v-superseded"
    )
    sv_allowed = service.create_source_version(
        admin_context, "req-sv-e-allowed", src.id, edition="v-allowed"
    )

    # Helper to create proposal and decision
    def _create_dec(sv, seq, dec_type, uc="reference", valid_from=None, valid_until=None):
        vf = valid_from or (now - timedelta(minutes=5))
        prov = db_session.execute(
            select(CatalogSourceProvenance).where(
                CatalogSourceProvenance.source_version_id == sv.id
            )
        ).scalar_one_or_none()
        if prov is None:
            prov = CatalogSourceProvenance(
                source_version_id=sv.id,
                source_revision=1,
                content_sha256=sv.content_digest,
                content_size=10,
                mime_type="text/plain",
                locator=f"https://example.com/{sv.edition}",
                retrieved_at=now,
                recorded_by_actor_id=uuid4(),
            )
            db_session.add(prov)
            db_session.flush()
        prior_prop = None
        if seq > 1:
            prior_prop = db_session.execute(
                select(CatalogSourcePermissionProposal).where(
                    CatalogSourcePermissionProposal.source_version_id == sv.id,
                    CatalogSourcePermissionProposal.use_case == uc,
                    CatalogSourcePermissionProposal.scope_key == "global",
                    CatalogSourcePermissionProposal.sequence == seq - 1,
                )
            ).scalar_one()

        prop = CatalogSourcePermissionProposal(
            provenance_id=prov.id,
            source_version_id=sv.id,
            use_case=uc,
            scope_key="global",
            sequence=seq,
            supersedes_id=prior_prop.id if prior_prop else None,
            supersedes_sequence=seq - 1 if prior_prop else None,
            proposed_outcome=dec_type,
            review_state="Draft",
            conditions_state="None",
            recorded_by_actor_id=uuid4(),
        )
        db_session.add(prop)
        db_session.flush()
        return service.create_permission_decision(
            admin_context,
            f"req-dec-{sv.edition}-{uc}-{seq}",
            src.id,
            sv.id,
            prop.id,
            use_case=uc,
            scope_key="global",
            decision_type=dec_type,
            valid_from=vf,
            valid_until=valid_until,
            evidence_reference=f"EV-{sv.edition}-{uc}-{seq}",
        )

    # Denied
    _create_dec(sv_denied, 1, "Denied")
    # Expired
    _create_dec(
        sv_expired,
        1,
        "Allowed",
        valid_from=now - timedelta(days=2),
        valid_until=now - timedelta(days=1),
    )
    # Superseded (seq 1 Allowed, seq 2 Denied)
    _create_dec(sv_superseded, 1, "Allowed")
    _create_dec(sv_superseded, 2, "Denied")
    # Allowed
    _create_dec(sv_allowed, 1, "Allowed")

    db_session.commit()

    # 1. Test get_source_version SQL filtering
    with pytest.raises(CatalogNotFoundError, match="Source version not found"):
        service.get_source_version(admin_context, sv_absent.id)
    with pytest.raises(CatalogNotFoundError, match="Source version not found"):
        service.get_source_version(admin_context, sv_denied.id)
    with pytest.raises(CatalogNotFoundError, match="Source version not found"):
        service.get_source_version(admin_context, sv_expired.id)
    with pytest.raises(CatalogNotFoundError, match="Source version not found"):
        service.get_source_version(admin_context, sv_superseded.id)

    retrieved_sv = service.get_source_version(admin_context, sv_allowed.id)
    assert retrieved_sv.id == sv_allowed.id

    # 2. Test list_source_versions SQL filtering
    listed_svs = service.list_source_versions(admin_context, src.id, limit=50)
    listed_sv_ids = {v.id for v in listed_svs}
    assert sv_allowed.id in listed_sv_ids
    assert sv_absent.id not in listed_sv_ids
    assert sv_denied.id not in listed_sv_ids
    assert sv_expired.id not in listed_sv_ids
    assert sv_superseded.id not in listed_sv_ids

    # 3. Setup Requirements and Requirement Versions
    req = service.create_requirement(admin_context, "req-r-exact-all", src.id, "req-exact-key")

    rv_absent = CatalogRequirementVersion(
        id=uuid4(),
        requirement_id=req.id,
        source_id=src.id,
        source_version_id=sv_absent.id,
        version_label="v-absent",
        normalized_outcome="outcome",
        requirement_type="mandatory",
        obligated_actor="Admin",
        text_origin="reference_only",
        revision=1,
    )
    rv_denied = CatalogRequirementVersion(
        id=uuid4(),
        requirement_id=req.id,
        source_id=src.id,
        source_version_id=sv_denied.id,
        version_label="v-denied",
        normalized_outcome="outcome",
        requirement_type="mandatory",
        obligated_actor="Admin",
        text_origin="reference_only",
        revision=1,
    )
    rv_expired = CatalogRequirementVersion(
        id=uuid4(),
        requirement_id=req.id,
        source_id=src.id,
        source_version_id=sv_expired.id,
        version_label="v-expired",
        normalized_outcome="outcome",
        requirement_type="mandatory",
        obligated_actor="Admin",
        text_origin="reference_only",
        revision=1,
    )
    rv_superseded = CatalogRequirementVersion(
        id=uuid4(),
        requirement_id=req.id,
        source_id=src.id,
        source_version_id=sv_superseded.id,
        version_label="v-superseded",
        normalized_outcome="outcome",
        requirement_type="mandatory",
        obligated_actor="Admin",
        text_origin="reference_only",
        revision=1,
    )
    db_session.add_all([rv_absent, rv_denied, rv_expired, rv_superseded])
    db_session.flush()

    rv_allowed = service.create_requirement_version(
        admin_context,
        "req-rv-exact-allowed",
        req.id,
        sv_allowed.id,
        "v-allowed",
        "outcome",
        "mandatory",
        "Admin",
        "reference_only",
        [
            {
                "source_version_id": sv_allowed.id,
                "locator_kind": "section",
                "locator_value": "1.0",
                "sequence": 1,
            }
        ],
    )
    db_session.commit()

    # Test get_requirement_version SQL filtering
    with pytest.raises(CatalogNotFoundError, match="Requirement version not found"):
        service.get_requirement_version(admin_context, rv_absent.id)
    with pytest.raises(CatalogNotFoundError, match="Requirement version not found"):
        service.get_requirement_version(admin_context, rv_denied.id)
    with pytest.raises(CatalogNotFoundError, match="Requirement version not found"):
        service.get_requirement_version(admin_context, rv_expired.id)
    with pytest.raises(CatalogNotFoundError, match="Requirement version not found"):
        service.get_requirement_version(admin_context, rv_superseded.id)

    retrieved_rv = service.get_requirement_version(admin_context, rv_allowed.id)
    assert retrieved_rv.id == rv_allowed.id

    # Test list_requirement_versions SQL filtering
    listed_rvs = service.list_requirement_versions(admin_context, req.id, limit=50)
    listed_rv_ids = {r.id for r in listed_rvs}
    assert rv_allowed.id in listed_rv_ids
    assert rv_absent.id not in listed_rv_ids
    assert rv_denied.id not in listed_rv_ids
    assert rv_expired.id not in listed_rv_ids
    assert rv_superseded.id not in listed_rv_ids

    # 4. Setup Common Control, Control Version, Mapping, and Mapping Versions
    ctrl = service.create_common_control(admin_context, "req-cc-1", "CC-SEC-001", "security")
    cv = service.create_control_version(
        admin_context, "req-cv-1", ctrl.id, "v1.0", "Statement", "guidance"
    )
    mapping = service.create_mapping(admin_context, "req-map-1", req.id, ctrl.id, "req-cc-map")

    # Mappings require "map" use case on the requirement's source version
    _create_dec(sv_denied, 1, "Denied", uc="map")
    _create_dec(
        sv_expired,
        1,
        "Allowed",
        uc="map",
        valid_from=now - timedelta(days=2),
        valid_until=now - timedelta(days=1),
    )
    _create_dec(sv_superseded, 1, "Allowed", uc="map")
    _create_dec(sv_superseded, 2, "Denied", uc="map")
    _create_dec(sv_allowed, 1, "Allowed", uc="map")

    db_session.commit()

    mv_absent = CatalogMappingVersion(
        id=uuid4(),
        mapping_id=mapping.id,
        requirement_id=req.id,
        control_id=ctrl.id,
        requirement_version_id=rv_absent.id,
        control_version_id=cv.id,
        version_label="1.0.0-absent",
        mapping_type="Full",
        rationale="Mapping rationale",
        source_basis="direct_text",
        confidence="high",
        review_state="Draft",
        revision=1,
    )
    mv_denied = CatalogMappingVersion(
        id=uuid4(),
        mapping_id=mapping.id,
        requirement_id=req.id,
        control_id=ctrl.id,
        requirement_version_id=rv_denied.id,
        control_version_id=cv.id,
        version_label="1.0.0-denied",
        mapping_type="Full",
        rationale="Mapping rationale",
        source_basis="direct_text",
        confidence="high",
        review_state="Draft",
        revision=1,
    )
    mv_expired = CatalogMappingVersion(
        id=uuid4(),
        mapping_id=mapping.id,
        requirement_id=req.id,
        control_id=ctrl.id,
        requirement_version_id=rv_expired.id,
        control_version_id=cv.id,
        version_label="1.0.0-expired",
        mapping_type="Full",
        rationale="Mapping rationale",
        source_basis="direct_text",
        confidence="high",
        review_state="Draft",
        revision=1,
    )
    mv_superseded = CatalogMappingVersion(
        id=uuid4(),
        mapping_id=mapping.id,
        requirement_id=req.id,
        control_id=ctrl.id,
        requirement_version_id=rv_superseded.id,
        control_version_id=cv.id,
        version_label="1.0.0-superseded",
        mapping_type="Full",
        rationale="Mapping rationale",
        source_basis="direct_text",
        confidence="high",
        review_state="Draft",
        revision=1,
    )
    db_session.add_all([mv_absent, mv_denied, mv_expired, mv_superseded])
    db_session.flush()

    mv_allowed = service.create_mapping_version(
        admin_context,
        "req-mv-exact-allowed",
        mapping.id,
        rv_allowed.id,
        cv.id,
        expected_req_revision=rv_allowed.revision,
        expected_req_digest=rv_allowed.content_digest,
        expected_ctrl_revision=cv.revision,
        expected_ctrl_digest=cv.content_digest,
        version_label="1.0.0-allowed",
        mapping_type="Full",
        rationale="Control satisfies requirement",
        source_basis="direct_text",
        confidence="high",
    )
    db_session.commit()

    # Test get_mapping_version SQL filtering
    with pytest.raises(CatalogNotFoundError, match="Mapping version not found"):
        service.get_mapping_version(admin_context, mv_absent.id)
    with pytest.raises(CatalogNotFoundError, match="Mapping version not found"):
        service.get_mapping_version(admin_context, mv_denied.id)
    with pytest.raises(CatalogNotFoundError, match="Mapping version not found"):
        service.get_mapping_version(admin_context, mv_expired.id)
    with pytest.raises(CatalogNotFoundError, match="Mapping version not found"):
        service.get_mapping_version(admin_context, mv_superseded.id)

    retrieved_mv = service.get_mapping_version(admin_context, mv_allowed.id)
    assert retrieved_mv.id == mv_allowed.id

    # Test list_mapping_versions SQL filtering
    listed_mvs = service.list_mapping_versions(admin_context, mapping.id, limit=50)
    listed_mv_ids = {m.id for m in listed_mvs}
    assert mv_allowed.id in listed_mv_ids
    assert mv_absent.id not in listed_mv_ids
    assert mv_denied.id not in listed_mv_ids
    assert mv_expired.id not in listed_mv_ids
    assert mv_superseded.id not in listed_mv_ids

    # 5. Test DatabaseCommittedDeniedAuditSink durable recording and diagnostics
    durable_sink = DatabaseCommittedDeniedAuditSink(db_session.bind)
    audited_service = CatalogDraftService(db_session, denied_audit_sink=durable_sink)

    unauth_context = CatalogActorContext(
        actor_id=uuid4(),
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=now,
        capabilities=frozenset({CatalogCapability.DRAFT_READ}),
    )

    with pytest.raises(CatalogSecurityError, match="Missing required capability"):
        audited_service.create_source(
            unauth_context, "req-denial-test-key", pub.id, "src-denial", "Denied Source"
        )

    # Verify that the denial event was written to catalog_audit_events
    denial_ev = db_session.execute(
        select(CatalogAuditEvent).where(CatalogAuditEvent.request_key == "req-denial-test-key")
    ).scalar_one_or_none()
    assert denial_ev is not None
    assert denial_ev.outcome == "Denied"
    assert denial_ev.actor_id == unauth_context.actor_id
    assert denial_ev.action == "create_source"
    assert denial_ev.metadata_json == {"reason_code": "CatalogSecurityError"}

    # Test sink failure diagnostics: sink that raises exception does NOT convert denial to success
    class FailingSink:
        def record_denial(self, *args, **kwargs):
            raise RuntimeError("Database disconnected or disk full in audit sink")

    fragile_service = CatalogDraftService(db_session, denied_audit_sink=FailingSink())
    with pytest.raises(CatalogSecurityError, match="Missing required capability"):
        fragile_service.create_source(
            unauth_context, "req-denial-fragile-key", pub.id, "src-fragile", "Fragile Source"
        )
    assert fragile_service.last_denial_audit_error is not None
    assert isinstance(fragile_service.last_denial_audit_error, RuntimeError)
    assert "Database disconnected" in str(fragile_service.last_denial_audit_error)
