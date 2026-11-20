"""Backend unit tests for synthetic catalog demo projection, service enforcement, and fixture loader."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from conformly.catalog_demo.dataset import (
    ACTOR_A_ID,
    CONTROL_1_ID,
    CONTROL_2_ID,
    CTRL_1_DIGEST,
    CTRL_2_DIGEST,
    DECISION_REF_ID,
    EVID_1_DIGEST,
    EVID_2_DIGEST,
    MAP_1_DIGEST,
    MAP_2_DIGEST,
    MAPPING_1_ID,
    PROC_1_DIGEST,
    PROC_2_DIGEST,
    PROVENANCE_ID,
    REQ_1_DIGEST,
    REQ_1_ID,
    REQ_2_DIGEST,
    REQ_2_ID,
    SOURCE_ID,
    SOURCE_VERSION_DIGEST,
    is_database_disposable,
    setup_catalog_demo_fixture,
)
from conformly.catalog_demo.db import AuditPersistenceError
from conformly.catalog_demo.projection import project_catalog_demo_graph
from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogCapability,
    CatalogNotFoundError,
    CatalogSecurityError,
)
from conformly.catalog_v2.models import (
    CatalogAssessmentProcedureStep,
    CatalogRequirementControlMapping,
    CatalogRequirementSourceReference,
    CatalogSource,
    CatalogSourcePermissionDecision,
    CatalogSourceProvenance,
)
from conformly.db.base import Base


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        setup_catalog_demo_fixture(session)
        session.commit()
        yield session


def test_fixture_setup_idempotent_and_conflict(memory_db):
    # Second call should safely succeed as verified complete reuse
    setup_catalog_demo_fixture(memory_db)
    memory_db.commit()
    source = memory_db.get(CatalogSource, SOURCE_ID)
    assert source is not None
    assert source.source_key == "DEMO08-SOURCE"

    # Tampering with an entity causes reuse to fail with conflict error
    source.title = "Tampered Title"
    memory_db.commit()
    with pytest.raises(ValueError, match="Catalog demo fixture conflict"):
        setup_catalog_demo_fixture(memory_db)


def test_fixture_setup_refuses_non_disposable():
    # File-based SQLite database not named memory or disposable runner database
    mock_engine = create_engine("sqlite:///prod_db.sqlite")
    Base.metadata.create_all(mock_engine)
    with Session(mock_engine) as session:
        with pytest.raises(RuntimeError, match="is not disposable"):
            setup_catalog_demo_fixture(session)


def test_project_catalog_demo_graph_exact_top_level(memory_db):
    now_dt = datetime.now(UTC)
    actor_ctx = CatalogActorContext(
        actor_id=ACTOR_A_ID,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=now_dt,
        capabilities=frozenset({CatalogCapability.DRAFT_READ}),
    )

    graph = project_catalog_demo_graph(memory_db, actor_ctx)

    # 1. Top-level exact schema
    assert graph.demo_id == "catalog-demo-v1"
    assert graph.synthetic is True
    assert graph.status == "Draft"
    assert graph.source.source_key == "DEMO08-SOURCE"
    assert graph.source.title == "Synthetic Conformly catalog demo"
    assert graph.source_version.edition == "1.0.0"
    assert (
        graph.source_version.official_locator
        == "https://demo.synthetic.conformly.invalid/sources/demo08-source-v1.pdf"
    )
    assert graph.source_version.content_digest == SOURCE_VERSION_DIGEST.hex()

    # 2. Requirements (exactly 2)
    assert len(graph.requirements) == 2
    req1 = next(r for r in graph.requirements if r.id == str(REQ_1_ID))
    req2 = next(r for r in graph.requirements if r.id == str(REQ_2_ID))
    assert req1.requirement_key == "DEMO08-REQ-01"
    assert req1.content_digest == REQ_1_DIGEST.hex()
    assert len(req1.source_references) == 1
    assert req1.source_references[0].locator_value == "1.1"

    assert req2.requirement_key == "DEMO08-REQ-02"
    assert req2.content_digest == REQ_2_DIGEST.hex()

    # 3. Controls (2, corrected keys per D-V2-019)
    assert len(graph.controls) == 2
    c1 = next(c for c in graph.controls if c.control_key == "CC-DEMO-001")
    c2 = next(c for c in graph.controls if c.control_key == "CC-DEMO-002")
    assert c1.domain == "DEMO"
    assert c1.title == "Privileged Access Review"
    assert c1.content_digest == CTRL_1_DIGEST.hex()
    assert c2.domain == "DEMO"
    assert c2.title == "Backup Restore Exercise"
    assert c2.content_digest == CTRL_2_DIGEST.hex()

    # 4. Evidence Requirements (2 top-level)
    assert len(graph.evidence_requirements) == 2
    er1 = next(e for e in graph.evidence_requirements if e.requirement_key == "ER-DEMO-001")
    er2 = next(e for e in graph.evidence_requirements if e.requirement_key == "ER-DEMO-002")
    assert er1.content_digest == EVID_1_DIGEST.hex()
    assert er1.control_id == str(CONTROL_1_ID)
    assert er2.content_digest == EVID_2_DIGEST.hex()
    assert er2.control_id == str(CONTROL_2_ID)

    # 5. Assessment Procedures (2 top-level)
    assert len(graph.assessment_procedures) == 2
    ap1 = next(p for p in graph.assessment_procedures if p.procedure_key == "AP-DEMO-001")
    ap2 = next(p for p in graph.assessment_procedures if p.procedure_key == "AP-DEMO-002")
    assert ap1.content_digest == PROC_1_DIGEST.hex()
    assert ap1.control_id == str(CONTROL_1_ID)
    assert ap2.content_digest == PROC_2_DIGEST.hex()
    assert ap2.control_id == str(CONTROL_2_ID)

    # 6. Mappings (2)
    assert len(graph.mappings) == 2
    map1 = next(m for m in graph.mappings if m.mapping_type == "Full")
    map2 = next(m for m in graph.mappings if m.mapping_type == "Partial")
    assert map1.content_digest == MAP_1_DIGEST.hex()
    assert map2.content_digest == MAP_2_DIGEST.hex()
    assert map2.excluded_dimensions == "backup protection and retention schedules"


def test_projection_denial_when_permission_missing(memory_db):
    now_dt = datetime.now(UTC)
    actor_ctx = CatalogActorContext(
        actor_id=ACTOR_A_ID,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=now_dt,
        capabilities=frozenset({CatalogCapability.DRAFT_READ}),
    )

    # Revoke effective reference permission on source
    dec = memory_db.get(CatalogSourcePermissionDecision, DECISION_REF_ID)
    assert dec is not None
    dec.decision = "Denied"
    memory_db.commit()

    with pytest.raises(CatalogNotFoundError):
        project_catalog_demo_graph(memory_db, actor_ctx)


def test_projection_requires_draft_read_capability(memory_db):
    now_dt = datetime.now(UTC)
    bad_ctx = CatalogActorContext(
        actor_id=ACTOR_A_ID,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=now_dt,
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE}),
    )
    with pytest.raises(CatalogSecurityError, match="Missing required capability"):
        project_catalog_demo_graph(memory_db, bad_ctx)


def test_projection_rejects_stale_actor(memory_db):
    stale_dt = datetime.now(UTC) - timedelta(minutes=20)
    stale_ctx = CatalogActorContext(
        actor_id=ACTOR_A_ID,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=stale_dt,
        capabilities=frozenset({CatalogCapability.DRAFT_READ}),
    )
    with pytest.raises(CatalogSecurityError, match="Authentication expired"):
        project_catalog_demo_graph(memory_db, stale_ctx)


def test_fixture_reuse_refuses_on_tampered_children_and_permissions(memory_db):
    """Verify that tampering with child records or permissions strictly refuses reuse."""
    # 1. Tamper procedure step instruction
    step = memory_db.query(CatalogAssessmentProcedureStep).first()
    assert step is not None
    orig_instruction = step.instruction
    step.instruction = "Tampered unauthorized instruction"
    memory_db.commit()

    with pytest.raises(ValueError, match="Catalog demo fixture conflict"):
        setup_catalog_demo_fixture(memory_db)

    step.instruction = orig_instruction
    memory_db.commit()

    # Reuse now passes again
    setup_catalog_demo_fixture(memory_db)


def test_projection_refuses_tampered_provenance_ref_mapping_with_unchanged_parent_digest(memory_db):
    """Verify projection verifies immutable child records even when stored parent digests match."""
    now_dt = datetime.now(UTC)
    actor_ctx = CatalogActorContext(
        actor_id=ACTOR_A_ID,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=now_dt,
        capabilities=frozenset({CatalogCapability.DRAFT_READ}),
    )

    # 1. Tamper provenance row locator while source version digest is unchanged
    prov = memory_db.get(CatalogSourceProvenance, PROVENANCE_ID)
    assert prov is not None
    orig_locator = prov.locator
    prov.locator = "https://malicious.synthetic.invalid/evil.pdf"
    memory_db.commit()

    with pytest.raises(CatalogNotFoundError, match="provenance"):
        project_catalog_demo_graph(memory_db, actor_ctx)

    prov.locator = orig_locator
    memory_db.commit()

    # 2. Tamper requirement source reference locator
    ref = memory_db.query(CatalogRequirementSourceReference).first()
    assert ref is not None
    orig_ref_loc = ref.locator_value
    ref.locator_value = "99.99"
    memory_db.commit()

    with pytest.raises(CatalogNotFoundError, match="source reference"):
        project_catalog_demo_graph(memory_db, actor_ctx)

    ref.locator_value = orig_ref_loc
    memory_db.commit()

    # 3. Tamper stable mapping entity key
    m_entity = memory_db.get(CatalogRequirementControlMapping, MAPPING_1_ID)
    assert m_entity is not None
    orig_map_key = m_entity.mapping_key
    m_entity.mapping_key = "TAMPERED-MAP-KEY"
    memory_db.commit()

    with pytest.raises(CatalogNotFoundError, match="Mapping parent entity"):
        project_catalog_demo_graph(memory_db, actor_ctx)

    m_entity.mapping_key = orig_map_key
    memory_db.commit()

    # Verified clean
    assert project_catalog_demo_graph(memory_db, actor_ctx) is not None


def test_database_disposable_and_exact_target_admission():
    """Verify is_database_disposable enforces exact admitted target, loopback, and rejects prefix matching."""
    from unittest.mock import MagicMock

    from sqlalchemy.dialects import postgresql, sqlite

    # 1. SQLite in-memory accepted, file-based rejected
    session_sqlite_mem = MagicMock()
    session_sqlite_mem.get_bind.return_value.dialect = sqlite.dialect()
    session_sqlite_mem.get_bind.return_value.url.database = ":memory:"
    assert is_database_disposable(session_sqlite_mem) is True

    session_sqlite_file = MagicMock()
    session_sqlite_file.get_bind.return_value.dialect = sqlite.dialect()
    session_sqlite_file.get_bind.return_value.url.database = "production.sqlite"
    assert is_database_disposable(session_sqlite_file) is False

    # 2. PostgreSQL tests
    session_pg = MagicMock()
    session_pg.get_bind.return_value.dialect = postgresql.dialect()

    # Non-loopback host rejected
    session_pg.get_bind.return_value.url.host = "pg.internal.cloud"
    session_pg.execute.return_value.scalar.return_value = "conformly_disposable_wp08_run53"
    assert (
        is_database_disposable(session_pg, expected_database="conformly_disposable_wp08_run53")
        is False
    )

    # Loopback host accepted
    session_pg.get_bind.return_value.url.host = "127.0.0.1"

    # System database rejected
    session_pg.execute.return_value.scalar.return_value = "postgres"
    assert is_database_disposable(session_pg, expected_database="postgres") is False

    # Prefix-only match rejected
    session_pg.execute.return_value.scalar.return_value = "conformly_disposable_"
    assert is_database_disposable(session_pg) is False

    # Non-matching expected_database rejected
    session_pg.execute.return_value.scalar.return_value = "conformly_disposable_wp08_run52"
    assert (
        is_database_disposable(session_pg, expected_database="conformly_disposable_wp08_run53")
        is False
    )

    # Exact expected_database match without data directory refuses
    session_pg.execute.return_value.scalar.return_value = "conformly_disposable_wp08_run53"
    assert (
        is_database_disposable(session_pg, expected_database="conformly_disposable_wp08_run53")
        is False
    )

    # Exact expected_database match with data directory succeeds
    def mock_exec_admit(query, *args, **kwargs):
        res = MagicMock()
        if "current_database()" in str(query):
            res.scalar.return_value = "conformly_disposable_wp08_run53"
        elif "data_directory" in str(query):
            res.scalar.return_value = "/var/lib/pg/data"
        return res

    session_pg.execute.side_effect = mock_exec_admit
    assert (
        is_database_disposable(
            session_pg,
            expected_database="conformly_disposable_wp08_run53",
            expected_data_directory="/var/lib/pg/data",
        )
        is True
    )


def test_service_swallowed_audit_error_surfaces_as_503(memory_db):
    """Verify that if protected service exposes last_denial_audit_error, projection raises AuditPersistenceError."""
    from unittest.mock import patch

    now_dt = datetime.now(UTC)
    actor_ctx = CatalogActorContext(
        actor_id=ACTOR_A_ID,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=now_dt,
        capabilities=frozenset({CatalogCapability.DRAFT_READ}),
    )

    with patch(
        "conformly.catalog_demo.projection.CatalogAssuranceDraftService"
    ) as mock_service_cls:
        mock_svc = mock_service_cls.return_value
        mock_svc.last_denial_audit_error = RuntimeError(
            "Underlying audit database dropped connection"
        )
        mock_svc.get_source_version.side_effect = CatalogNotFoundError("Source version not found")

        with pytest.raises(AuditPersistenceError, match="audit persistence failure"):
            project_catalog_demo_graph(memory_db, actor_ctx)


@pytest.mark.parametrize(
    "tamper_entity,tamper_field,tamper_val",
    [
        ("control_version", "guidance", "Tampered guidance text"),
        ("control_version", "frequency", "annually"),
        ("control_version", "automation_level", "automated"),
        ("requirement_version", "normalized_outcome", "Tampered outcome text"),
        ("mapping_version", "covered_dimensions", "Tampered dimensions"),
        ("evidence_version", "title", "Tampered evidence title"),
        ("evidence_version", "guidance", "Tampered evidence guidance"),
        ("evidence_version", "missing_data_behavior", "skip"),
        ("procedure_version", "title", "Tampered procedure title"),
        ("provenance", "mime_type", "application/json"),
    ],
)
def test_parameterized_tampering_with_unchanged_digest_refuses(
    memory_db, tamper_entity, tamper_field, tamper_val
):
    from conformly.catalog_demo.dataset import (
        CONTROL_1_VER_ID,
        EVID_1_VER_ID,
        MAPPING_1_VER_ID,
        PROC_1_VER_ID,
        PROVENANCE_ID,
        REQ_1_VER_ID,
        setup_catalog_demo_fixture,
    )
    from conformly.catalog_demo.projection import project_catalog_demo_graph
    from conformly.catalog_v2.models import (
        CatalogAssessmentProcedureVersion,
        CatalogControlVersion,
        CatalogEvidenceRequirementVersion,
        CatalogMappingVersion,
        CatalogRequirementVersion,
        CatalogSourceProvenance,
    )

    now_dt = datetime.now(UTC)
    actor_ctx = CatalogActorContext(
        actor_id=ACTOR_A_ID,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=now_dt,
        capabilities=frozenset({CatalogCapability.DRAFT_READ}),
    )

    model_map = {
        "control_version": (CatalogControlVersion, CONTROL_1_VER_ID),
        "requirement_version": (CatalogRequirementVersion, REQ_1_VER_ID),
        "mapping_version": (CatalogMappingVersion, MAPPING_1_VER_ID),
        "evidence_version": (CatalogEvidenceRequirementVersion, EVID_1_VER_ID),
        "procedure_version": (CatalogAssessmentProcedureVersion, PROC_1_VER_ID),
        "provenance": (CatalogSourceProvenance, PROVENANCE_ID),
    }

    model_cls, entity_id = model_map[tamper_entity]
    entity = memory_db.get(model_cls, entity_id)
    assert entity is not None
    setattr(entity, tamper_field, tamper_val)

    # Use no_autoflush so that in-memory validation runs before any DB constraint checks
    with memory_db.no_autoflush:
        # Fixture reuse must detect altered data and refuse before writes
        with pytest.raises(ValueError, match="Catalog demo fixture conflict"):
            setup_catalog_demo_fixture(memory_db)

        # Projection must detect altered fields/digest mismatch and refuse safely
        with pytest.raises(CatalogNotFoundError):
            project_catalog_demo_graph(memory_db, actor_ctx)


def test_mock_postgresql_admission_requires_both_expected_database_and_directory():
    from unittest.mock import MagicMock

    from conformly.catalog_demo.dataset import is_database_disposable

    session_pg = MagicMock(spec=Session)
    bind = MagicMock()
    bind.dialect.name = "postgresql"
    bind.url.host = "127.0.0.1"
    session_pg.get_bind.return_value = bind

    # 1. Omitted expected_database refuses
    assert (
        is_database_disposable(
            session_pg, expected_database=None, expected_data_directory="/var/lib/pg/data"
        )
        is False
    )

    # 2. Omitted expected_data_directory refuses
    assert (
        is_database_disposable(
            session_pg, expected_database="conformly_disposable_run54", expected_data_directory=None
        )
        is False
    )

    # 3. Both provided, but host is non-loopback refuses
    bind.url.host = "192.168.1.50"
    assert (
        is_database_disposable(
            session_pg,
            expected_database="conformly_disposable_run54",
            expected_data_directory="/var/lib/pg/data",
        )
        is False
    )
    bind.url.host = "127.0.0.1"

    # Helper to mock db query
    def mock_exec_test(query, *args, **kwargs):
        q = str(query)
        res = MagicMock()
        if "current_database()" in q:
            res.scalar.return_value = "conformly_disposable_run54"
        elif "data_directory" in q:
            res.scalar.return_value = "/var/lib/pg/data"
        else:
            res.scalar.return_value = None
        return res

    session_pg.execute.side_effect = mock_exec_test

    # 4. Exact match succeeds
    assert (
        is_database_disposable(
            session_pg,
            expected_database="conformly_disposable_run54",
            expected_data_directory="/var/lib/pg/data",
        )
        is True
    )

    # 5. Non-matching database refuses
    def mock_exec_other(query, *args, **kwargs):
        q = str(query)
        res = MagicMock()
        if "current_database()" in q:
            res.scalar.return_value = "conformly_disposable_other"
        else:
            res.scalar.return_value = "/var/lib/pg/data"
        return res

    session_pg.execute.side_effect = mock_exec_other
    assert (
        is_database_disposable(
            session_pg,
            expected_database="conformly_disposable_run54",
            expected_data_directory="/var/lib/pg/data",
        )
        is False
    )

    # 6. Correct DB but wrong directory refuses
    def mock_exec_wrong_dir(query, *args, **kwargs):
        q = str(query)
        res = MagicMock()
        if "current_database()" in q:
            res.scalar.return_value = "conformly_disposable_run54"
        else:
            res.scalar.return_value = "/var/lib/pg/wrong_data"
        return res

    session_pg.execute.side_effect = mock_exec_wrong_dir
    assert (
        is_database_disposable(
            session_pg,
            expected_database="conformly_disposable_run54",
            expected_data_directory="/var/lib/pg/data",
        )
        is False
    )

    # 7. Identity query failure refuses (fail-closed)
    session_pg.execute.side_effect = RuntimeError("Database query failure")
    assert (
        is_database_disposable(
            session_pg,
            expected_database="conformly_disposable_run54",
            expected_data_directory="/var/lib/pg/data",
        )
        is False
    )


def test_projection_trusted_clock_broken_pipe_preserves_security_error_not_404(memory_db):
    """Verify that BrokenPipeError on trusted-clock read preserves CatalogSecurityError
    and is strictly NOT converted to CatalogNotFoundError."""

    now_dt = datetime.now(UTC)
    actor_ctx = CatalogActorContext(
        actor_id=ACTOR_A_ID,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=now_dt,
        capabilities=frozenset({CatalogCapability.DRAFT_READ}),
    )

    orig_execute = memory_db.execute

    def mock_execute(statement, *args, **kwargs):
        stmt_str = str(statement)
        if (
            "clock_timestamp" in stmt_str
            or "strftime" in stmt_str
            or "CURRENT_TIMESTAMP" in stmt_str
        ):
            raise BrokenPipeError("Broken pipe")
        return orig_execute(statement, *args, **kwargs)

    memory_db.execute = mock_execute

    with pytest.raises(CatalogSecurityError) as exc_info:
        project_catalog_demo_graph(memory_db, actor_ctx)

    assert not isinstance(exc_info.value, CatalogNotFoundError)
    assert isinstance(exc_info.value.__cause__, BrokenPipeError)
    assert "Unable to establish trusted database time" in str(exc_info.value)


def test_projection_connection_failure_with_digest_or_mismatch_diagnostic_not_404(memory_db):
    """Verify that DB connection/operational errors containing 'mismatch' or 'digest' keywords
    are NOT misclassified as CatalogNotFoundError."""
    from sqlalchemy.exc import OperationalError

    now_dt = datetime.now(UTC)
    actor_ctx = CatalogActorContext(
        actor_id=ACTOR_A_ID,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=now_dt,
        capabilities=frozenset({CatalogCapability.DRAFT_READ}),
    )

    orig_execute = memory_db.execute

    def mock_execute(statement, *args, **kwargs):
        stmt_str = str(statement)
        if (
            "clock_timestamp" in stmt_str
            or "strftime" in stmt_str
            or "CURRENT_TIMESTAMP" in stmt_str
        ):
            raise OperationalError(
                "SSL SYSCALL error: handshake digest mismatch", {}, Exception("diagnostic")
            )
        return orig_execute(statement, *args, **kwargs)

    memory_db.execute = mock_execute

    with pytest.raises(Exception) as exc_info:
        project_catalog_demo_graph(memory_db, actor_ctx)

    assert not isinstance(exc_info.value, CatalogNotFoundError)


def test_projection_trusted_clock_invalid_result_preserves_security_error_not_404(memory_db):
    """Verify that invalid/null return from trusted clock read preserves CatalogSecurityError
    and is strictly NOT converted to CatalogNotFoundError."""
    from unittest.mock import MagicMock

    now_dt = datetime.now(UTC)
    actor_ctx = CatalogActorContext(
        actor_id=ACTOR_A_ID,
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=now_dt,
        capabilities=frozenset({CatalogCapability.DRAFT_READ}),
    )

    orig_execute = memory_db.execute

    def mock_execute(statement, *args, **kwargs):
        stmt_str = str(statement)
        if (
            "clock_timestamp" in stmt_str
            or "strftime" in stmt_str
            or "CURRENT_TIMESTAMP" in stmt_str
        ):
            mock_res = MagicMock()
            mock_res.scalar.return_value = None
            return mock_res
        return orig_execute(statement, *args, **kwargs)

    memory_db.execute = mock_execute

    with pytest.raises(CatalogSecurityError) as exc_info:
        project_catalog_demo_graph(memory_db, actor_ctx)

    assert not isinstance(exc_info.value, CatalogNotFoundError)
    assert "Unable to establish trusted database time" in str(exc_info.value)
