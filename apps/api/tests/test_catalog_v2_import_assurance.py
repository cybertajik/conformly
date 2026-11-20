"""Comprehensive integration tests for WP-06C synthetic assurance import activation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from conformly.catalog_v2 import CatalogConflictError
from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogCapability,
    CatalogSecurityError,
)
from conformly.catalog_v2.audit import DatabaseCommittedDeniedAuditSink
from conformly.catalog_v2.import_adapter import (
    ImportDisposition,
    ImportItem,
    load_fixture,
)
from conformly.catalog_v2.models import (
    CatalogAssessmentProcedureEvidenceRequirement,
    CatalogAssessmentProcedureStep,
    CatalogAssessmentProcedureVersion,
    CatalogAuditEvent,
    CatalogControlVersion,
    CatalogEvidenceRequirementArtifactType,
    CatalogEvidenceRequirementMetadataKey,
    CatalogEvidenceRequirementVersion,
)
from conformly.catalog_v2.models_import import (
    CatalogImportBatch,
    CatalogImportInput,
    CatalogImportReuseLedger,
)
from conformly.catalog_v2.services_import import ConservativeImportService
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


def make_actor(capabilities: frozenset[CatalogCapability] | None = None) -> CatalogActorContext:
    if capabilities is None:
        capabilities = frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ})
    return CatalogActorContext(
        actor_id=uuid4(),
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC),
        capabilities=capabilities,
    )


class _SqlStateError(Exception):
    code: str


class RecordingDeniedAuditSink:
    def __init__(self):
        self.recorded_denials = []

    def record_denial(
        self, actor_id, operation, reason_code, request_key, resource_type=None, resource_id=None
    ):
        self.recorded_denials.append(
            {
                "actor_id": actor_id,
                "operation": operation,
                "reason_code": reason_code,
                "request_key": request_key,
                "resource_type": resource_type,
                "resource_id": resource_id,
            }
        )


# ---------------------------------------------------------------------------
# 1. Full Lifecycle Import of Synthetic Assurance Content
# ---------------------------------------------------------------------------
def test_synthetic_assurance_full_lifecycle(db_session: Session):
    service = ConservativeImportService(db_session)
    actor = make_actor()
    items = load_fixture("synthetic_assurance_fixture.json")

    adm = service.admit_batch(actor, "batch-assurance-lifecycle-01", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)

    assert manifest.total_inputs == 3
    assert manifest.reconciled_inputs == 3
    assert manifest.counts_by_disposition.get("ImportedDraft") == 3

    # Verify database domain objects
    ctrl_v = db_session.scalar(
        select(CatalogControlVersion).where(
            CatalogControlVersion.title == "Synthetic Access Control"
        )
    )
    assert ctrl_v is not None
    assert ctrl_v.status == "Draft"

    er_v = db_session.scalar(
        select(CatalogEvidenceRequirementVersion).where(
            CatalogEvidenceRequirementVersion.requirement_key == "ER-ACC-001"
        )
    )
    assert er_v is not None
    assert er_v.control_version_id == ctrl_v.id
    assert er_v.sequence == 1
    art_types = db_session.scalars(
        select(CatalogEvidenceRequirementArtifactType).where(
            CatalogEvidenceRequirementArtifactType.evidence_requirement_version_id == er_v.id
        )
    ).all()
    assert len(art_types) == 2
    req_meta = db_session.scalars(
        select(CatalogEvidenceRequirementMetadataKey).where(
            CatalogEvidenceRequirementMetadataKey.evidence_requirement_version_id == er_v.id
        )
    ).all()
    assert len(req_meta) == 2

    ap_v = db_session.scalar(
        select(CatalogAssessmentProcedureVersion).where(
            CatalogAssessmentProcedureVersion.procedure_key == "AP-ACC-001"
        )
    )
    assert ap_v is not None
    assert ap_v.control_version_id == ctrl_v.id
    assert ap_v.sequence == 1
    steps = db_session.scalars(
        select(CatalogAssessmentProcedureStep).where(
            CatalogAssessmentProcedureStep.assessment_procedure_version_id == ap_v.id
        )
    ).all()
    assert len(steps) == 2
    er_links = db_session.scalars(
        select(CatalogAssessmentProcedureEvidenceRequirement).where(
            CatalogAssessmentProcedureEvidenceRequirement.assessment_procedure_version_id == ap_v.id
        )
    ).all()
    assert len(er_links) == 1
    assert er_links[0].evidence_requirement_version_id == er_v.id

    # Verify reuse ledger rows
    er_ledger = db_session.scalar(
        select(CatalogImportReuseLedger).where(
            CatalogImportReuseLedger.target_entity_type == "EvidenceRequirementVersion",
            CatalogImportReuseLedger.origin_id == "ER-SYN-001",
        )
    )
    assert er_ledger is not None
    assert er_ledger.target_version_id == er_v.id
    assert er_ledger.target_revision == 1
    assert er_ledger.target_digest == er_v.content_digest

    ap_ledger = db_session.scalar(
        select(CatalogImportReuseLedger).where(
            CatalogImportReuseLedger.target_entity_type == "AssessmentProcedureVersion",
            CatalogImportReuseLedger.origin_id == "AP-SYN-001",
        )
    )
    assert ap_ledger is not None
    assert ap_ledger.target_version_id == ap_v.id
    assert ap_ledger.target_revision == 1
    assert ap_ledger.target_digest == ap_v.content_digest


# ---------------------------------------------------------------------------
# 2. Exact Reuse Verification
# ---------------------------------------------------------------------------
def test_synthetic_assurance_exact_reuse(db_session: Session):
    service = ConservativeImportService(db_session)
    actor = make_actor()
    items = load_fixture("synthetic_assurance_fixture.json")

    # Initial admission & execution
    adm1 = service.admit_batch(actor, "batch-exact-reuse-01", items)
    manifest1 = service.execute_batch(actor, adm1.batch.id, items)
    assert manifest1.counts_by_disposition.get("ImportedDraft") == 3

    # Second batch with identical items
    adm2 = service.admit_batch(actor, "batch-exact-reuse-02", items)
    manifest2 = service.execute_batch(actor, adm2.batch.id, items)

    assert manifest2.total_inputs == 3
    assert manifest2.reconciled_inputs == 3
    assert manifest2.counts_by_disposition.get("ReusedExact") == 3

    # Check input rows have reason_code REUSE_EXACT_MATCH
    rows = db_session.scalars(
        select(CatalogImportInput).where(CatalogImportInput.batch_id == adm2.batch.id)
    ).all()
    for row in rows:
        assert row.disposition == ImportDisposition.REUSED_EXACT
        assert row.reason_code == "REUSE_EXACT_MATCH"


# ---------------------------------------------------------------------------
# 3. Changed Origin Content Conflict Review
# ---------------------------------------------------------------------------
def test_synthetic_assurance_changed_origin_content(db_session: Session):
    service = ConservativeImportService(db_session)
    actor = make_actor()
    items = load_fixture("synthetic_assurance_fixture.json")

    adm1 = service.admit_batch(actor, "batch-changed-content-01", items)
    service.execute_batch(actor, adm1.batch.id, items)

    # Modify the payload of ER item (sequence 2) but keep origin_id the same
    items2 = load_fixture("synthetic_assurance_fixture.json")
    items2[1].payload["title"] = "Modified ER Title For Conflict"

    adm2 = service.admit_batch(actor, "batch-changed-content-02", items2)
    manifest2 = service.execute_batch(actor, adm2.batch.id, items2)

    assert manifest2.counts_by_disposition.get("NeedsConflictReview") == 1
    changed_input = db_session.scalar(
        select(CatalogImportInput).where(
            CatalogImportInput.batch_id == adm2.batch.id,
            CatalogImportInput.sequence == 2,
        )
    )
    assert changed_input is not None
    assert changed_input.disposition == ImportDisposition.NEEDS_CONFLICT_REVIEW
    assert changed_input.reason_code == "CONFLICT_CHANGED_ORIGIN_CONTENT"


# ---------------------------------------------------------------------------
# 4. Preflight Dual Authorization Enforcement & Durable Denial Audit
# ---------------------------------------------------------------------------
def test_preflight_dual_authorization_denials(db_session: Session):
    durable_sink = DatabaseCommittedDeniedAuditSink(db_session.bind)
    service = ConservativeImportService(db_session, denied_audit_sink=durable_sink)
    items = load_fixture("synthetic_assurance_fixture.json")

    admin = make_actor()
    adm = service.admit_batch(admin, "batch-preflight-denials-01", items)

    # Actor with DRAFT_WRITE only (missing DRAFT_READ)
    actor_write_only = make_actor(frozenset({CatalogCapability.DRAFT_WRITE}))
    with pytest.raises(CatalogSecurityError, match="Missing required capability: DRAFT_READ"):
        service.execute_batch(actor_write_only, adm.batch.id, items)

    # Verify durable denial audit event committed in database
    denial_events = db_session.scalars(
        select(CatalogAuditEvent)
        .where(
            CatalogAuditEvent.outcome == "Denied",
            CatalogAuditEvent.action == "execute_batch_capability_preflight",
        )
        .order_by(CatalogAuditEvent.sequence.asc())
    ).all()
    assert len(denial_events) == 1
    assert denial_events[0].actor_id == actor_write_only.actor_id
    assert denial_events[0].metadata_json == {"reason_code": "CatalogSecurityError"}
    assert denial_events[0].resource_id == adm.batch.id

    # Verify zero data disclosure: zero inputs processed, remain Pending
    pending_rows = db_session.scalars(
        select(CatalogImportInput).where(
            CatalogImportInput.batch_id == adm.batch.id,
        )
    ).all()
    assert len(pending_rows) == 3
    for row in pending_rows:
        assert row.disposition == ImportDisposition.PENDING
    assert db_session.scalar(select(CatalogControlVersion)) is None
    assert db_session.scalar(select(CatalogImportReuseLedger)) is None

    # Actor with DRAFT_READ only (missing DRAFT_WRITE)
    actor_read_only = make_actor(frozenset({CatalogCapability.DRAFT_READ}))
    with pytest.raises(CatalogSecurityError, match="Missing required capability: DRAFT_WRITE"):
        service.execute_batch(actor_read_only, adm.batch.id, items)

    denial_events_after = db_session.scalars(
        select(CatalogAuditEvent)
        .where(
            CatalogAuditEvent.outcome == "Denied",
            CatalogAuditEvent.action == "execute_batch_capability_preflight",
        )
        .order_by(CatalogAuditEvent.sequence.asc())
    ).all()
    assert len(denial_events_after) == 2
    assert denial_events_after[1].actor_id == actor_read_only.actor_id
    assert denial_events_after[1].metadata_json == {"reason_code": "CatalogSecurityError"}
    assert denial_events_after[1].resource_id == adm.batch.id


# ---------------------------------------------------------------------------
# 5. Fail-Closed Corrupt Aggregate Abort (SecurityError Propagates Unhandled)
# ---------------------------------------------------------------------------
def test_fail_closed_corrupt_aggregate_abort(db_session: Session, monkeypatch):
    service = ConservativeImportService(db_session)
    actor = make_actor()
    items = load_fixture("synthetic_assurance_fixture.json")

    adm1 = service.admit_batch(actor, "batch-corrupt-abort-01", items)
    service.execute_batch(actor, adm1.batch.id, items)

    # Second execution: inject CatalogSecurityError on aggregate read
    adm2 = service.admit_batch(actor, "batch-corrupt-abort-02", items)

    from conformly.catalog_v2.service_assurance import CatalogAssuranceDraftService

    def failing_get_er(self, context, version_id):
        raise CatalogSecurityError("Corrupt aggregate: child steps out of order")

    monkeypatch.setattr(
        CatalogAssuranceDraftService, "get_evidence_requirement_version", failing_get_er
    )

    # CatalogSecurityError must propagate out unhandled and NOT be converted to CONFLICT_STALE_REUSE_TARGET
    with pytest.raises(CatalogSecurityError, match="Corrupt aggregate"):
        service.execute_batch(actor, adm2.batch.id, items)

    # Batch should be marked Interrupted
    batch = db_session.get(CatalogImportBatch, adm2.batch.id)
    assert batch is not None
    assert batch.status == "Interrupted"


# ---------------------------------------------------------------------------
# 6. Non-Security Target Missing Routes to Conflict Review
# ---------------------------------------------------------------------------
def test_non_security_target_missing_routes_to_conflict_review(db_session: Session):
    service = ConservativeImportService(db_session)
    actor = make_actor()
    items = load_fixture("synthetic_assurance_fixture.json")

    adm1 = service.admit_batch(actor, "batch-stale-target-01", items)
    service.execute_batch(actor, adm1.batch.id, items)

    # Artificially alter the reuse ledger entry target_version_id to a nonexistent UUID
    er_ledger = db_session.scalar(
        select(CatalogImportReuseLedger).where(
            CatalogImportReuseLedger.target_entity_type == "EvidenceRequirementVersion",
            CatalogImportReuseLedger.origin_id == "ER-SYN-001",
        )
    )
    assert er_ledger is not None
    er_ledger.target_version_id = uuid4()
    db_session.commit()

    adm2 = service.admit_batch(actor, "batch-stale-target-02", items)
    manifest2 = service.execute_batch(actor, adm2.batch.id, items)

    assert manifest2.counts_by_disposition.get("NeedsConflictReview") == 1
    input_row = db_session.scalar(
        select(CatalogImportInput).where(
            CatalogImportInput.batch_id == adm2.batch.id,
            CatalogImportInput.sequence == 2,
        )
    )
    assert input_row is not None
    assert input_row.disposition == ImportDisposition.NEEDS_CONFLICT_REVIEW
    assert input_row.reason_code == "CONFLICT_STALE_REUSE_TARGET"


# ---------------------------------------------------------------------------
# 7. Adapter Version Isolation in Origin Lookups
# ---------------------------------------------------------------------------
def test_adapter_version_isolation_in_origin_lookups(db_session: Session):
    service = ConservativeImportService(db_session)
    actor = make_actor()

    # Pre-insert parent control under a different adapter_version
    old_ctrl_v_id = uuid4()
    old_ledger = CatalogImportReuseLedger(
        origin_namespace="conformly.synthetic",
        origin_id="CTRL-SYN-001",
        adapter_version="catalog-import-v0",
        input_fingerprint=b"\x00" * 32,
        target_entity_type="ControlVersion",
        target_version_id=old_ctrl_v_id,
        target_revision=1,
        target_digest=b"\x00" * 32,
        created_at=datetime.now(UTC),
    )
    db_session.add(old_ledger)
    db_session.commit()

    # Create an ER item referencing parent control via origin namespace and ID
    items = [
        ImportItem(
            1,
            "EvidenceRequirement",
            "conformly.synthetic",
            "ER-SYN-001",
            {
                "parent_control_origin_namespace": "conformly.synthetic",
                "parent_control_origin_id": "CTRL-SYN-001",
                "requirement_key": "ER-ACC-001",
                "title": "Access Review Records",
                "frequency": "annual",
                "scope_state": "All",
                "assurance_purpose": "design",
                "validity_rule": "continuous",
                "artifact_types": [{"artifact_type": "report", "sequence": 1}],
            },
        )
    ]

    adm = service.admit_batch(actor, "batch-adapter-isolation-01", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)

    assert manifest.counts_by_disposition.get("NeedsDependency") == 1
    row = db_session.scalar(
        select(CatalogImportInput).where(CatalogImportInput.batch_id == adm.batch.id)
    )
    assert row is not None
    assert row.disposition == ImportDisposition.NEEDS_DEPENDENCY
    assert row.reason_code == "PARENT_CONTROL_ORIGIN_NOT_FOUND"


# ---------------------------------------------------------------------------
# 8. Parent Locator Contradiction Rejection
# ---------------------------------------------------------------------------
def test_parent_locator_contradiction_rejection(db_session: Session):
    service = ConservativeImportService(db_session)
    actor = make_actor()

    items = [
        ImportItem(
            1,
            "CommonControl",
            "conformly.synthetic",
            "CTRL-01",
            {"control_key": "CC-PAR-001", "domain": "security", "title": "Control 1"},
        ),
        ImportItem(
            2,
            "CommonControl",
            "conformly.synthetic",
            "CTRL-02",
            {"control_key": "CC-PAR-002", "domain": "security", "title": "Control 2"},
        ),
        ImportItem(
            3,
            "EvidenceRequirement",
            "conformly.synthetic",
            "ER-01",
            {
                "parent_control_sequence": 1,
                "control_version_id": str(uuid4()),  # Contradicts sequence 1
                "requirement_key": "ER-PAR-001",
                "title": "Contradictory Parent ER",
                "frequency": "annual",
                "scope_state": "All",
                "assurance_purpose": "design",
                "validity_rule": "continuous",
                "artifact_types": [{"artifact_type": "report", "sequence": 1}],
            },
        ),
    ]

    adm = service.admit_batch(actor, "batch-parent-contradiction-01", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)

    assert manifest.counts_by_disposition.get("Rejected") == 1
    er_row = db_session.scalar(
        select(CatalogImportInput).where(
            CatalogImportInput.batch_id == adm.batch.id,
            CatalogImportInput.sequence == 3,
        )
    )
    assert er_row is not None
    assert er_row.disposition == ImportDisposition.REJECTED
    assert er_row.reason_code == "CONFLICT_PARENT_CONTROL_LOCATOR_MISMATCH"


# ---------------------------------------------------------------------------
# 9. Linked ER Locator Contradiction Rejection
# ---------------------------------------------------------------------------
def test_linked_er_locator_contradiction_rejection(db_session: Session):
    service = ConservativeImportService(db_session)
    actor = make_actor()

    items = [
        ImportItem(
            1,
            "CommonControl",
            "conformly.synthetic",
            "CTRL-01",
            {"control_key": "CC-LNK-001", "domain": "security", "title": "Control 1"},
        ),
        ImportItem(
            2,
            "EvidenceRequirement",
            "conformly.synthetic",
            "ER-01",
            {
                "parent_control_sequence": 1,
                "requirement_key": "ER-LNK-001",
                "title": "Linked ER",
                "frequency": "annual",
                "scope_state": "All",
                "assurance_purpose": "design",
                "validity_rule": "continuous",
                "artifact_types": [{"artifact_type": "report", "sequence": 1}],
            },
        ),
        ImportItem(
            3,
            "AssessmentProcedure",
            "conformly.synthetic",
            "AP-01",
            {
                "parent_control_sequence": 1,
                "procedure_key": "AP-LNK-001",
                "title": "Procedure",
                "objective": "Objective",
                "decision_guidance": "Pass/Fail",
                "steps": [{"sequence": 1, "step_kind": "inspect", "instruction": "Check"}],
                "evidence_requirements": [
                    {
                        "sequence": 1,
                        "evidence_requirement_sequence": 2,
                        "id": str(uuid4()),  # Contradicts sequence 2
                    }
                ],
            },
        ),
    ]

    adm = service.admit_batch(actor, "batch-linked-er-contradiction-01", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)

    assert manifest.counts_by_disposition.get("Rejected") == 1
    ap_row = db_session.scalar(
        select(CatalogImportInput).where(
            CatalogImportInput.batch_id == adm.batch.id,
            CatalogImportInput.sequence == 3,
        )
    )
    assert ap_row is not None
    assert ap_row.disposition == ImportDisposition.REJECTED
    assert ap_row.reason_code == "CONFLICT_LINKED_ER_LOCATOR_MISMATCH"


# ---------------------------------------------------------------------------
# 10. Cross-Control Link Denial
# ---------------------------------------------------------------------------
def test_cross_control_link_denial(db_session: Session):
    service = ConservativeImportService(db_session)
    actor = make_actor()

    items = [
        ImportItem(
            1,
            "CommonControl",
            "conformly.synthetic",
            "CTRL-01",
            {"control_key": "CC-CRS-001", "domain": "security", "title": "Control 1"},
        ),
        ImportItem(
            2,
            "CommonControl",
            "conformly.synthetic",
            "CTRL-02",
            {"control_key": "CC-CRS-002", "domain": "security", "title": "Control 2"},
        ),
        ImportItem(
            3,
            "EvidenceRequirement",
            "conformly.synthetic",
            "ER-01",
            {
                "parent_control_sequence": 1,
                "requirement_key": "ER-CRS-001",
                "title": "ER under Control 1",
                "frequency": "annual",
                "scope_state": "All",
                "assurance_purpose": "design",
                "validity_rule": "continuous",
                "artifact_types": [{"artifact_type": "report", "sequence": 1}],
            },
        ),
        ImportItem(
            4,
            "AssessmentProcedure",
            "conformly.synthetic",
            "AP-01",
            {
                "parent_control_sequence": 2,  # Parent is Control 2
                "procedure_key": "AP-CRS-001",
                "title": "Procedure under Control 2",
                "objective": "Objective",
                "decision_guidance": "Pass/Fail",
                "steps": [{"sequence": 1, "step_kind": "inspect", "instruction": "Check"}],
                "evidence_requirements": [
                    {
                        "sequence": 1,
                        "evidence_requirement_sequence": 3,  # References ER under Control 1!
                    }
                ],
            },
        ),
    ]

    adm = service.admit_batch(actor, "batch-cross-control-01", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)

    assert manifest.counts_by_disposition.get("Rejected") == 1
    ap_row = db_session.scalar(
        select(CatalogImportInput).where(
            CatalogImportInput.batch_id == adm.batch.id,
            CatalogImportInput.sequence == 4,
        )
    )
    assert ap_row is not None
    assert ap_row.disposition == ImportDisposition.REJECTED
    assert ap_row.reason_code == "CROSS_CONTROL_LINK_FORBIDDEN"


# ---------------------------------------------------------------------------
# 11. Out-of-Order Batch Dependency
# ---------------------------------------------------------------------------
def test_out_of_order_batch_dependency(db_session: Session):
    service = ConservativeImportService(db_session)
    actor = make_actor()

    # Out of order: ER at seq 1 referencing CommonControl at seq 2
    items = [
        ImportItem(
            1,
            "EvidenceRequirement",
            "conformly.synthetic",
            "ER-01",
            {
                "parent_control_sequence": 2,  # Points to seq 2 which hasn't been executed yet!
                "requirement_key": "ER-ORD-001",
                "title": "Out of Order ER",
                "frequency": "annual",
                "scope_state": "All",
                "assurance_purpose": "design",
                "validity_rule": "continuous",
                "artifact_types": [{"artifact_type": "report", "sequence": 1}],
            },
        ),
        ImportItem(
            2,
            "CommonControl",
            "conformly.synthetic",
            "CTRL-01",
            {"control_key": "CC-ORD-001", "domain": "security", "title": "Control"},
        ),
    ]

    adm = service.admit_batch(actor, "batch-out-of-order-01", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)

    assert manifest.counts_by_disposition.get("NeedsDependency") == 1
    assert manifest.counts_by_disposition.get("ImportedDraft") == 1
    er_row = db_session.scalar(
        select(CatalogImportInput).where(
            CatalogImportInput.batch_id == adm.batch.id,
            CatalogImportInput.sequence == 1,
        )
    )
    assert er_row is not None
    assert er_row.disposition == ImportDisposition.NEEDS_DEPENDENCY
    assert er_row.reason_code == "DEPENDENCY_ORDERING_VIOLATION"


# ---------------------------------------------------------------------------
# 12. Parent Control Digest Mismatch Rejection
# ---------------------------------------------------------------------------
def test_parent_control_digest_mismatch_rejection(db_session: Session):
    service = ConservativeImportService(db_session)
    actor = make_actor()

    items = [
        ImportItem(
            1,
            "CommonControl",
            "conformly.synthetic",
            "CTRL-01",
            {"control_key": "CC-DGT-001", "domain": "security", "title": "Control 1"},
        ),
        ImportItem(
            2,
            "EvidenceRequirement",
            "conformly.synthetic",
            "ER-01",
            {
                "parent_control_sequence": 1,
                "expected_control_digest": "00" * 32,  # Deliberate mismatch
                "requirement_key": "ER-DGT-001",
                "title": "Mismatched Digest ER",
                "frequency": "annual",
                "scope_state": "All",
                "assurance_purpose": "design",
                "validity_rule": "continuous",
                "artifact_types": [{"artifact_type": "report", "sequence": 1}],
            },
        ),
    ]

    adm = service.admit_batch(actor, "batch-digest-mismatch-01", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)

    assert manifest.counts_by_disposition.get("Rejected") == 1
    er_row = db_session.scalar(
        select(CatalogImportInput).where(
            CatalogImportInput.batch_id == adm.batch.id,
            CatalogImportInput.sequence == 2,
        )
    )
    assert er_row is not None
    assert er_row.disposition == ImportDisposition.REJECTED
    assert er_row.reason_code == "CONFLICT_PARENT_CONTROL_DIGEST_MISMATCH"


# ---------------------------------------------------------------------------
# 13. Concurrency Conflict Recovery: Rollback-Before-Sleep and Retry
# ---------------------------------------------------------------------------
def test_concurrency_conflict_rollback_and_retry(db_session: Session, monkeypatch):
    """Verify that a concurrency conflict (e.g. 40001 serialization failure) triggers
    an immediate session rollback before sleep backoff, and retries successfully.
    """
    service = ConservativeImportService(db_session)
    actor = make_actor()
    items = load_fixture("synthetic_assurance_fixture.json")
    adm = service.admit_batch(actor, "batch-concurrency-retry-01", items)

    events: list[str] = []
    sleep_calls: list[float] = []

    orig_rollback = db_session.rollback

    def tracking_rollback():
        events.append("rollback")
        return orig_rollback()

    def tracking_sleep(delay: float):
        events.append(f"sleep_{delay:.3f}")
        sleep_calls.append(delay)

    monkeypatch.setattr(db_session, "rollback", tracking_rollback)
    monkeypatch.setattr("time.sleep", tracking_sleep)

    attempts = 0
    orig_process = service._process_single_input

    def flaky_process(context, batch, input_row, item, draft_service):
        nonlocal attempts
        # Simulate transient concurrency conflict on the EvidenceRequirement item (sequence 2)
        if item.input_type == "EvidenceRequirement":
            attempts += 1
            if attempts == 1:
                err = _SqlStateError("serialization_failure")
                err.code = "40001"
                raise err
        return orig_process(context, batch, input_row, item, draft_service)

    monkeypatch.setattr(service, "_process_single_input", flaky_process)

    manifest = service.execute_batch(actor, adm.batch.id, items)

    # 1. Verification of rollback-before-sleep discipline
    assert "rollback" in events
    assert len(sleep_calls) == 1
    rollback_idx = events.index("rollback")
    sleep_idx = next(i for i, s in enumerate(events) if s.startswith("sleep_"))
    assert rollback_idx < sleep_idx, "Rollback must precede sleep backoff"

    # 2. Verification of successful retry
    assert manifest.reconciled_inputs == 3
    assert manifest.counts_by_disposition.get("ImportedDraft") == 3

    # Check input row attempt count
    er_row = db_session.scalar(
        select(CatalogImportInput).where(
            CatalogImportInput.batch_id == adm.batch.id,
            CatalogImportInput.input_type == "EvidenceRequirement",
        )
    )
    assert er_row is not None
    assert er_row.attempt_count == 2
    assert er_row.disposition == ImportDisposition.IMPORTED_DRAFT


# ---------------------------------------------------------------------------
# 14. Concurrency Conflict Exhaustion: Mark Batch Interrupted
# ---------------------------------------------------------------------------
def test_concurrency_conflict_exhaustion_marks_batch_interrupted(db_session: Session, monkeypatch):
    """Verify that exhausted concurrency retries trigger rollback, mark batch Interrupted, and re-raise."""
    service = ConservativeImportService(db_session)
    actor = make_actor()
    items = load_fixture("synthetic_assurance_fixture.json")
    adm = service.admit_batch(actor, "batch-concurrency-exhaust-01", items)

    monkeypatch.setattr("time.sleep", lambda delay: None)

    attempts = 0

    def always_conflict(context, batch, input_row, item, draft_service):
        nonlocal attempts
        attempts += 1
        err = _SqlStateError("serialization_failure")
        err.code = "40001"
        raise err

    monkeypatch.setattr(service, "_process_single_input", always_conflict)

    with pytest.raises(CatalogConflictError, match="CONCURRENCY_CONFLICT_RETRY_EXHAUSTED"):
        service.execute_batch(actor, adm.batch.id, items)

    assert attempts == 3

    batch = db_session.scalar(
        select(CatalogImportBatch).where(CatalogImportBatch.id == adm.batch.id)
    )
    assert batch is not None
    assert batch.status == "Interrupted"

    # First input remains Pending because transaction was rolled back on all 3 attempts
    input1 = db_session.scalar(
        select(CatalogImportInput).where(
            CatalogImportInput.batch_id == adm.batch.id,
            CatalogImportInput.sequence == 1,
        )
    )
    assert input1 is not None
    assert input1.disposition == ImportDisposition.PENDING


# ---------------------------------------------------------------------------
# 15. Failed Parent Resolution During Exact Reuse Is Not Misclassified
# ---------------------------------------------------------------------------
def test_failed_parent_resolution_during_exact_reuse_not_misclassified(db_session: Session):
    """Verify that failing parent control resolution during exact reuse records the
    actual parent failure disposition/reason rather than misclassifying as parent conflict.
    """
    service = ConservativeImportService(db_session)
    actor = make_actor()
    items = load_fixture("synthetic_assurance_fixture.json")

    # Step 1: Initial import of items
    adm1 = service.admit_batch(actor, "batch-parent-res-base-01", items)
    manifest1 = service.execute_batch(actor, adm1.batch.id, items)
    assert manifest1.reconciled_inputs == 3

    # Step 2: Attempt exact reuse of ER item, but with an unresolved parent sequence (sequence 99)
    # This must record NEEDS_DEPENDENCY (DEPENDENCY_ORDERING_VIOLATION), NOT CONFLICT_REUSE_PARENT_MISMATCH
    er_item_orig = next(i for i in items if i.input_type == "EvidenceRequirement")
    bad_item = ImportItem(
        sequence=1,
        input_type="EvidenceRequirement",
        origin_namespace=er_item_orig.origin_namespace,
        origin_id=er_item_orig.origin_id,
        payload=dict(er_item_orig.payload),
    )

    adm2 = service.admit_batch(actor, "batch-parent-res-fail-02", [bad_item])
    manifest2 = service.execute_batch(actor, adm2.batch.id, [bad_item])
    assert manifest2.counts_by_disposition.get("NeedsDependency") == 1
    input_row = db_session.scalar(
        select(CatalogImportInput).where(
            CatalogImportInput.batch_id == adm2.batch.id,
            CatalogImportInput.sequence == 1,
        )
    )
    assert input_row is not None
    assert input_row.disposition == ImportDisposition.NEEDS_DEPENDENCY
    assert input_row.reason_code == "DEPENDENCY_ORDERING_VIOLATION"


# ---------------------------------------------------------------------------
