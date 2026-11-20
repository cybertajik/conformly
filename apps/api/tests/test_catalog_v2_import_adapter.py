"""Canonical integration tests for FIX-01 through FIX-12 and SCALE-01."""

import time
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogCapability,
    CatalogConflictError,
    CatalogSecurityError,
)
from conformly.catalog_v2.import_adapter import (
    ImportDisposition,
    ImportItem,
    PreviewContext,
    load_fixture,
    preview_batch,
)
from conformly.catalog_v2.models import (
    CatalogAuditEvent,
    CatalogCommonControl,
    CatalogControlVersion,
    CatalogEventIntent,
    CatalogPackMembership,
    CatalogRequirement,
    CatalogRequirementVersion,
    CatalogSource,
    CatalogSourcePermissionProposal,
    CatalogSourceProvenance,
    CatalogSourceVersion,
)
from conformly.catalog_v2.models_import import (
    CatalogImportBatch,
    CatalogImportInput,
    CatalogImportReuseLedger,
)
from conformly.catalog_v2.service import CatalogDraftService
from conformly.catalog_v2.services_import import ConservativeImportService
from conformly.db.base import Base


class _SqlStateError(Exception):
    code: str


@pytest.fixture
def full_db_session():
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


def admin_actor():
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


def tenant_actor():
    return CatalogActorContext(
        actor_id=uuid4(),
        is_platform_admin=False,
        mfa_verified=False,
        authenticated_at=datetime.now(UTC),
        capabilities=frozenset(),
    )


def setup_source_with_permissions(
    service: CatalogDraftService,
    session: Session,
    context: CatalogActorContext,
    source_key: str = "src-canonical",
    version_key: str = "2026-v1",
    use_cases: list[str] | None = None,
    scope_key: str = "global",
) -> tuple[CatalogSource, CatalogSourceVersion]:
    if use_cases is None:
        use_cases = ["reference", "paraphrase", "store", "excerpt", "map"]
    pub = service.create_publisher(
        context, f"pub-{uuid4().hex[:8]}", f"pub-{uuid4().hex[:8]}", "Canonical Publisher"
    )
    src = service.create_source(
        context, f"src-{uuid4().hex[:8]}", pub.id, source_key, "Canonical Source"
    )
    sv = service.create_source_version(
        context, f"sv-{uuid4().hex[:8]}", src.id, edition=version_key
    )

    now = datetime.now(UTC)
    prov = CatalogSourceProvenance(
        source_version_id=sv.id,
        source_revision=sv.revision,
        content_sha256=sv.content_digest,
        content_size=100,
        mime_type="application/pdf",
        locator="https://standards.org/spec",
        retrieved_at=now,
        recorded_by_actor_id=context.actor_id,
    )
    session.add(prov)
    session.flush()

    proposer_id = uuid4()
    for uc in use_cases:
        prop = CatalogSourcePermissionProposal(
            provenance_id=prov.id,
            source_version_id=sv.id,
            use_case=uc,
            scope_key=scope_key,
            sequence=1,
            proposed_outcome="Allowed",
            conditions_state="None",
            recorded_by_actor_id=proposer_id,
        )
        session.add(prop)
        session.flush()

        service.create_permission_decision(
            context,
            f"dec-{uuid4().hex[:8]}",
            src.id,
            sv.id,
            prop.id,
            use_case=uc,
            scope_key=scope_key,
            decision_type="Allowed",
            valid_from=now - timedelta(minutes=5),
            valid_until=None,
            evidence_reference="CANONICAL-GRANT",
        )
    return src, sv


# ---------------------------------------------------------------------------
# VS01-FIX-01: Dry-Run Six-Input Conservation (Preview write-free)
# ---------------------------------------------------------------------------
def test_vs01_fix01_dry_run_conservation(full_db_session: Session):
    items = load_fixture("fix01_dry_run_conservation.json")
    context = PreviewContext(
        available_sources=frozenset({"src-ver-ok"}),
        permitted_origins=frozenset({"map-unresolved"}),
    )
    results = preview_batch(items, context)

    assert len(results) == 6
    assert [r.disposition for r in results] == [
        ImportDisposition.IMPORTED_DRAFT,
        ImportDisposition.IMPORTED_DRAFT,
        ImportDisposition.NEEDS_PERMISSION,
        ImportDisposition.NEEDS_SOURCE,
        ImportDisposition.NEEDS_MAPPING_REVIEW,
        ImportDisposition.REJECTED,
    ]
    # Count conservation: sum of dispositions == 6
    assert sum(1 for _ in results) == 6

    # Verify zero database rows are committed
    assert full_db_session.scalars(select(CatalogImportBatch)).all() == []
    assert full_db_session.scalars(select(CatalogImportInput)).all() == []


# ---------------------------------------------------------------------------
# VS01-FIX-02: Exact Retry Plus Changed-Input Conflict
# ---------------------------------------------------------------------------
def test_vs01_fix02_exact_retry_conflict(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()
    items = load_fixture("fix02_exact_retry_conflict.json")

    # 1. First admission & execution
    adm1 = service.admit_batch(actor, "batch-fix02", items)
    assert adm1.replayed is False
    manifest1 = service.execute_batch(actor, adm1.batch.id, items)
    assert manifest1.reconciled_inputs == 2
    assert manifest1.counts_by_disposition.get("ImportedDraft") == 2

    # 2. Re-submitting identical batch replays results without duplicate inputs
    adm2 = service.admit_batch(actor, "batch-fix02", items)
    assert adm2.replayed is True
    assert adm2.batch.id == adm1.batch.id

    manifest2 = service.execute_batch(actor, adm2.batch.id, items)
    assert manifest2.batch_id == manifest1.batch_id

    # 3. Altering an input triggers conflict
    altered_items = [
        ImportItem(
            items[0].sequence,
            items[0].input_type,
            items[0].origin_namespace,
            items[0].origin_id,
            {"title": "Modified Title"},
        ),
        items[1],
    ]
    with pytest.raises(CatalogConflictError, match="CONFLICT_CHANGED_BATCH_CONTENT"):
        service.admit_batch(actor, "batch-fix02", altered_items)


# ---------------------------------------------------------------------------
# VS01-FIX-03: Two Writers on One Draft Revision
# ---------------------------------------------------------------------------
def test_vs01_fix03_two_writers_one_draft(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()
    items = load_fixture("fix03_two_writers_one_draft.json")

    # Writer 1 executes
    adm1 = service.admit_batch(actor, "batch-fix03-w1", items)
    service.execute_batch(actor, adm1.batch.id, items)

    # Verify 1 control version created
    ctrls = full_db_session.scalars(select(CatalogControlVersion)).all()
    assert len(ctrls) == 1

    # Writer 2 executes batch containing the same origin item
    adm2 = service.admit_batch(actor, "batch-fix03-w2", items)
    service.execute_batch(actor, adm2.batch.id, items)

    # Writer 2 reused exact from ledger; no second version created
    ctrls_after = full_db_session.scalars(select(CatalogControlVersion)).all()
    assert len(ctrls_after) == 1

    inputs_w2 = full_db_session.scalars(
        select(CatalogImportInput).where(CatalogImportInput.batch_id == adm2.batch.id)
    ).all()
    assert inputs_w2[0].disposition == ImportDisposition.REUSED_EXACT


# ---------------------------------------------------------------------------
# VS01-FIX-04: Injected Failure Before Commit
# ---------------------------------------------------------------------------
def test_vs01_fix04_injected_commit_failure(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()
    items = load_fixture("fix04_injected_commit_failure.json")

    adm = service.admit_batch(actor, "batch-fix04", items)

    # In a nested savepoint, simulate exception before commit
    with pytest.raises(RuntimeError, match="INJECTED_FAILURE"):
        with full_db_session.begin_nested():
            # Process first item
            input_row = full_db_session.scalar(
                select(CatalogImportInput).where(
                    CatalogImportInput.batch_id == adm.batch.id,
                    CatalogImportInput.sequence == 1,
                )
            )
            assert input_row is not None
            draft_svc = CatalogDraftService(full_db_session)
            service._process_single_input(actor, adm.batch, input_row, items[0], draft_svc)
            # Simulated catastrophic crash before transaction commits
            raise RuntimeError("INJECTED_FAILURE")

    # Verify input row remains in Pending and entities are uncommitted
    input_row = full_db_session.scalar(
        select(CatalogImportInput).where(
            CatalogImportInput.batch_id == adm.batch.id,
            CatalogImportInput.sequence == 1,
        )
    )
    assert input_row is not None
    assert input_row.disposition == ImportDisposition.PENDING
    assert full_db_session.scalars(select(CatalogControlVersion)).all() == []


# ---------------------------------------------------------------------------
# VS01-FIX-05: Lost Acknowledgement Recovery
# ---------------------------------------------------------------------------
def test_vs01_fix05_lost_ack_recovery(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()
    items = load_fixture("fix05_lost_ack_recovery.json")

    adm = service.admit_batch(actor, "batch-fix05", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)
    assert manifest.reconciled_inputs == 1

    # Lost-ack client re-invokes execute_batch
    recovered_manifest = service.execute_batch(actor, adm.batch.id, items)
    assert recovered_manifest.batch_id == manifest.batch_id
    assert recovered_manifest.manifest_hash == manifest.manifest_hash

    # Zero duplicate entities
    controls = full_db_session.scalars(select(CatalogCommonControl)).all()
    assert len(controls) == 1


# ---------------------------------------------------------------------------
# VS01-FIX-06: Permission-Blocked Sentinel Storage
# ---------------------------------------------------------------------------
def test_vs01_fix06_permission_blocked_sentinel(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()
    items = load_fixture("fix06_permission_blocked_sentinel.json")

    # Preview rejects sentinel
    preview_res = preview_batch(items, PreviewContext())[0]
    assert preview_res.disposition == ImportDisposition.REJECTED
    assert preview_res.reason_code == "MALFORMED_INPUT_PROHIBITED_TOKEN"

    # Execution routes to Rejected without persisting sentinel
    adm = service.admit_batch(actor, "batch-fix06", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)
    assert manifest.reconciled_inputs == 1
    assert manifest.counts_by_disposition.get("Rejected") == 1

    # Verify no sentinel in database audit logs or entity tables
    audit_events = full_db_session.scalars(select(CatalogAuditEvent)).all()
    for ev in audit_events:
        assert "UNRELEASED_SECRET" not in str(ev.metadata)
    assert full_db_session.scalars(select(CatalogRequirement)).all() == []


# ---------------------------------------------------------------------------
# VS01-FIX-07: Same Locator with Independent Outcomes
# ---------------------------------------------------------------------------
def test_vs01_fix07_same_locator_outcomes(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    draft_svc = CatalogDraftService(full_db_session)
    actor = admin_actor()

    # Create two separate sources and versions
    src_a, sv_a = setup_source_with_permissions(
        draft_svc, full_db_session, actor, source_key="src-a"
    )
    src_b, sv_b = setup_source_with_permissions(
        draft_svc, full_db_session, actor, source_key="src-b"
    )

    items = load_fixture("fix07_same_locator_outcomes.json")
    # Bind source version IDs
    items[0].payload["source_version_id"] = str(sv_a.id)
    items[1].payload["source_version_id"] = str(sv_b.id)

    adm = service.admit_batch(actor, "batch-fix07", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)
    assert manifest.reconciled_inputs == 2
    assert manifest.counts_by_disposition.get("ImportedDraft") == 2

    # Verify two distinct requirement entities tied to their respective sources
    reqs = full_db_session.scalars(select(CatalogRequirement)).all()
    assert len(reqs) == 2
    source_ids = {r.source_id for r in reqs}
    assert source_ids == {src_a.id, src_b.id}


# ---------------------------------------------------------------------------
# VS01-FIX-08: Temporal Precision
# ---------------------------------------------------------------------------
def test_vs01_fix08_temporal_precision(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    draft_svc = CatalogDraftService(full_db_session)
    actor = admin_actor()

    _, sv = setup_source_with_permissions(draft_svc, full_db_session, actor)
    items = load_fixture("fix08_temporal_precision.json")
    items[0].payload["source_version_id"] = str(sv.id)

    adm = service.admit_batch(actor, "batch-fix08", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)
    assert manifest.reconciled_inputs == 1

    req_v = full_db_session.scalar(select(CatalogRequirementVersion))
    assert req_v is not None
    assert req_v.effective_from == date(2026, 1, 1)
    assert req_v.effective_until == date(2026, 12, 31)


# ---------------------------------------------------------------------------
# VS01-FIX-09: Published Content Rejection
# ---------------------------------------------------------------------------
def test_vs01_fix09_published_content_rejection(full_db_session: Session):
    draft_svc = CatalogDraftService(full_db_session)
    actor = admin_actor()

    ctrl = draft_svc.create_common_control(
        actor, "req-ctrl-pub", control_key="CC-PUB-001", domain="governance"
    )
    draft_svc.create_control_version(
        actor,
        "req-ver-pub",
        control_id=ctrl.id,
        version_label="1.0.0",
        title="Published",
        objective="Obj",
    )

    # Attempting to set status to Published directly fails the DB draft-only check constraint
    ctrl.status = "Published"
    with pytest.raises(IntegrityError):
        full_db_session.flush()
    full_db_session.rollback()


# ---------------------------------------------------------------------------
# VS01-FIX-10: Invalid Endpoints & Deferred Children
# ---------------------------------------------------------------------------
def test_vs01_fix10_invalid_endpoints_deferred(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()
    items = load_fixture("fix10_invalid_endpoints_deferred.json")

    adm = service.admit_batch(actor, "batch-fix10", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)

    assert manifest.reconciled_inputs == 3
    assert manifest.counts_by_disposition.get("Rejected") == 2
    assert manifest.counts_by_disposition.get("NeedsMappingReview") == 1


# ---------------------------------------------------------------------------
# VS01-FIX-11: Tenant Actor Rejection
# ---------------------------------------------------------------------------
def test_vs01_fix11_tenant_actor_rejection(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    t_actor = tenant_actor()
    items = load_fixture("fix11_tenant_actor_rejection.json")

    with pytest.raises(CatalogSecurityError):
        service.admit_batch(t_actor, "batch-fix11", items)


# ---------------------------------------------------------------------------
# VS01-FIX-12: Stale / Revoked Permission Invalidation
# ---------------------------------------------------------------------------
def test_vs01_fix12_stale_permission_invalidation(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    draft_svc = CatalogDraftService(full_db_session)
    actor = admin_actor()

    # Setup source WITHOUT granting permission
    pub = draft_svc.create_publisher(actor, "pub-unperm", "pub-unperm", "Unpermitted Pub")
    src = draft_svc.create_source(actor, "src-unperm", pub.id, "src-unperm", "Unpermitted Source")
    sv = draft_svc.create_source_version(actor, "sv-unperm", src.id, edition="1.0")

    items = load_fixture("fix12_stale_permission_invalidation.json")
    items[0].payload["source_version_id"] = str(sv.id)

    adm = service.admit_batch(actor, "batch-fix12", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)

    assert manifest.reconciled_inputs == 1
    assert manifest.counts_by_disposition.get("NeedsPermission") == 1
    input_row = full_db_session.scalar(select(CatalogImportInput))
    assert input_row is not None
    assert input_row.disposition == ImportDisposition.NEEDS_PERMISSION
    assert input_row.reason_code in (
        "PERMISSION_PARAPHRASE_DENIED",
        "PERMISSION_DENIED_REFERENCE",
        "PERMISSION_REFERENCE_DENIED",
    )


# ---------------------------------------------------------------------------
# SCALE-01: Synthetic Tier A Scale Pack (156 inputs)
# ---------------------------------------------------------------------------
def test_scale01_synthetic_tier_a_scale_pack(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    draft_svc = CatalogDraftService(full_db_session)
    actor = admin_actor()

    # Setup source version with full permissions
    _, sv = setup_source_with_permissions(draft_svc, full_db_session, actor, source_key="src-scale")

    items = load_fixture("synthetic_tier_a_scale_pack.json")
    assert len(items) == 156

    # Update requirement source_version_id
    for it in items:
        if it.input_type == "Requirement":
            it.payload["source_version_id"] = str(sv.id)

    adm = service.admit_batch(actor, "batch-scale01", items)
    assert adm.batch.total_inputs == 156

    manifest = service.execute_batch(actor, adm.batch.id, items)
    assert manifest.reconciled_inputs == 156
    assert manifest.counts_by_disposition.get("ImportedDraft") == 156

    # Verify pack memberships are sequenced 1..30 without gaps
    memberships = full_db_session.scalars(
        select(CatalogPackMembership).order_by(CatalogPackMembership.sequence.asc())
    ).all()
    assert len(memberships) == 30
    assert [m.sequence for m in memberships] == list(range(1, 31))


# ---------------------------------------------------------------------------
# Envelope, Digest, and Foundation Unit Regressions
# ---------------------------------------------------------------------------
def test_fingerprint_is_stable_across_payload_key_order():
    left = ImportItem(1, "Pack", "synthetic", "pack", {"alpha": 1, "beta": 2})
    right = ImportItem(1, "Pack", "synthetic", "pack", {"beta": 2, "alpha": 1})
    assert left.fingerprint == right.fingerprint


def test_synthetic_assurance_preview_and_validation():
    # Valid items preview as WOULD_IMPORT_DRAFT
    items = load_fixture("synthetic_assurance_fixture.json", validate=True)
    preview_results = preview_batch(items, PreviewContext())
    assert len(preview_results) == 3
    for res in preview_results:
        assert res.disposition == ImportDisposition.IMPORTED_DRAFT
        assert res.reason_code == "WOULD_IMPORT_DRAFT"


def test_synthetic_assurance_payload_rejections():
    from conformly.catalog_v2.import_adapter import ImportPayloadError, _validate_item

    # 1. Non-null source_version_id rejected
    with pytest.raises(ImportPayloadError, match="SYNTHETIC_ASSURANCE_SOURCE_VERSION_FORBIDDEN"):
        _validate_item(
            ImportItem(
                1,
                "EvidenceRequirement",
                "conformly.synthetic",
                "ER-01",
                {
                    "parent_control_sequence": 1,
                    "requirement_key": "ER-TEST-001",
                    "title": "Test Title",
                    "frequency": "annual",
                    "scope_state": "All",
                    "assurance_purpose": "design",
                    "validity_rule": "continuous",
                    "artifact_types": [{"artifact_type": "report", "sequence": 1}],
                    "source_version_id": "0192e2c5-7f12-7890-a1b2-c3d4e5f60001",
                },
            )
        )

    # 2. Key regex bounds (ER)
    with pytest.raises(ImportPayloadError, match="INVALID_REQUIREMENT_KEY_FORMAT"):
        _validate_item(
            ImportItem(
                1,
                "EvidenceRequirement",
                "conformly.synthetic",
                "ER-01",
                {
                    "parent_control_sequence": 1,
                    "requirement_key": "er-invalid-lowercase",
                    "title": "Test",
                    "frequency": "annual",
                    "scope_state": "All",
                    "assurance_purpose": "design",
                    "validity_rule": "continuous",
                    "artifact_types": [{"artifact_type": "report", "sequence": 1}],
                },
            )
        )

    # 3. Key regex bounds (AP)
    with pytest.raises(ImportPayloadError, match="INVALID_PROCEDURE_KEY_FORMAT"):
        _validate_item(
            ImportItem(
                1,
                "AssessmentProcedure",
                "conformly.synthetic",
                "AP-01",
                {
                    "parent_control_sequence": 1,
                    "procedure_key": "INVALID-NO-PREFIX",
                    "title": "Test",
                    "objective": "Objective",
                    "decision_guidance": "Pass/Fail",
                    "steps": [{"sequence": 1, "step_kind": "inspect", "instruction": "Test"}],
                },
            )
        )

    # 4. Unsupported step kind
    with pytest.raises(ImportPayloadError, match="UNSUPPORTED_STEP_KIND"):
        _validate_item(
            ImportItem(
                1,
                "AssessmentProcedure",
                "conformly.synthetic",
                "AP-01",
                {
                    "parent_control_sequence": 1,
                    "procedure_key": "AP-TEST-001",
                    "title": "Test",
                    "objective": "Objective",
                    "decision_guidance": "Pass/Fail",
                    "steps": [{"sequence": 1, "step_kind": "examine", "instruction": "Test"}],
                },
            )
        )

    # 5. Missing parent control locator
    with pytest.raises(ImportPayloadError, match="PARENT_CONTROL_LOCATOR_REQUIRED"):
        _validate_item(
            ImportItem(
                1,
                "EvidenceRequirement",
                "conformly.synthetic",
                "ER-01",
                {
                    "requirement_key": "ER-TEST-001",
                    "title": "Test",
                    "frequency": "annual",
                    "scope_state": "All",
                    "assurance_purpose": "design",
                    "validity_rule": "continuous",
                    "artifact_types": [{"artifact_type": "report", "sequence": 1}],
                },
            )
        )

    # 6. Evidence requirements count bound (> 32)
    with pytest.raises(ImportPayloadError, match="EVIDENCE_REQUIREMENTS_COUNT_EXCEEDED"):
        _validate_item(
            ImportItem(
                1,
                "AssessmentProcedure",
                "conformly.synthetic",
                "AP-01",
                {
                    "parent_control_sequence": 1,
                    "procedure_key": "AP-TEST-001",
                    "title": "Test",
                    "objective": "Objective",
                    "decision_guidance": "Pass/Fail",
                    "steps": [{"sequence": 1, "step_kind": "inspect", "instruction": "Test"}],
                    "evidence_requirements": [
                        {"sequence": i, "evidence_requirement_sequence": i} for i in range(1, 34)
                    ],
                },
            )
        )

    # 7. Unknown top-level fields rejected (ER)
    with pytest.raises(ImportPayloadError, match="UNKNOWN_PAYLOAD_FIELDS"):
        _validate_item(
            ImportItem(
                1,
                "EvidenceRequirement",
                "conformly.synthetic",
                "ER-01",
                {
                    "parent_control_sequence": 1,
                    "requirement_key": "ER-TEST-001",
                    "title": "Test Title",
                    "frequency": "annual",
                    "scope_state": "All",
                    "assurance_purpose": "design",
                    "validity_rule": "continuous",
                    "artifact_types": [{"artifact_type": "report", "sequence": 1}],
                    "unknown_field_extra": "unexpected",
                },
            )
        )

    # 8. Unknown top-level fields rejected (AP)
    with pytest.raises(ImportPayloadError, match="UNKNOWN_PAYLOAD_FIELDS"):
        _validate_item(
            ImportItem(
                1,
                "AssessmentProcedure",
                "conformly.synthetic",
                "AP-01",
                {
                    "parent_control_sequence": 1,
                    "procedure_key": "AP-TEST-001",
                    "title": "Test",
                    "objective": "Objective",
                    "decision_guidance": "Pass/Fail",
                    "steps": [{"sequence": 1, "step_kind": "inspect", "instruction": "Test"}],
                    "unexpected_extra_field": 12345,
                },
            )
        )


@pytest.mark.parametrize(
    "items,reason",
    [
        ([], "BATCH_INPUT_COUNT_OUT_OF_RANGE"),
        (
            [
                ImportItem(1, "Pack", "synthetic", "same", {}),
                ImportItem(1, "Pack", "synthetic", "other", {}),
            ],
            "DUPLICATE_INPUT_SEQUENCE",
        ),
        (
            [
                ImportItem(1, "Pack", "synthetic", "same", {}),
                ImportItem(3, "Pack", "synthetic", "other", {}),
            ],
            "NON_CONTIGUOUS_INPUT_SEQUENCE",
        ),
        (
            [
                ImportItem(1, "Pack", "synthetic", "same", {}),
                ImportItem(2, "Pack", "synthetic", "same", {}),
            ],
            "DUPLICATE_INPUT_ORIGIN",
        ),
    ],
)
def test_batch_envelope_rejects_ambiguous_identity(items, reason):
    with pytest.raises(Exception, match=reason):
        preview_batch(items, PreviewContext())


def test_preview_rejects_duplicate_origin_before_classification():
    items = [
        ImportItem(1, "Pack", "synthetic", "same", {}),
        ImportItem(2, "Pack", "synthetic", "same", {}),
    ]
    with pytest.raises(Exception, match="DUPLICATE_INPUT_ORIGIN"):
        preview_batch(items, PreviewContext())


def test_import_models_enforce_digest_and_count_bounds(full_db_session: Session):
    batch = CatalogImportBatch(
        batch_key="batch-bounds",
        batch_fingerprint=b"x" * 31,
        adapter_version="catalog-import-v1",
        total_inputs=1,
        payload_digest=b"y" * 32,
    )
    full_db_session.add(batch)
    with pytest.raises(IntegrityError):
        full_db_session.flush()
    full_db_session.rollback()


def test_input_rejects_unknown_disposition(full_db_session: Session):
    batch = CatalogImportBatch(
        batch_key="batch-disp",
        batch_fingerprint=b"x" * 32,
        adapter_version="catalog-import-v1",
        total_inputs=1,
        payload_digest=b"y" * 32,
    )
    full_db_session.add(batch)
    full_db_session.flush()
    full_db_session.add(
        CatalogImportInput(
            batch_id=batch.id,
            sequence=1,
            input_type="Pack",
            origin_namespace="synthetic",
            origin_id=str(uuid4()),
            input_fingerprint=b"z" * 32,
            disposition="MadeUp",
        )
    )
    with pytest.raises(IntegrityError):
        full_db_session.flush()
    full_db_session.rollback()


def test_reuse_resolution_distinguishes_exact_from_changed_content(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    original = ImportItem(1, "Pack", "synthetic", "pack-1", {"title": "A"})
    ledger = CatalogImportReuseLedger(
        origin_namespace=original.origin_namespace,
        origin_id=original.origin_id,
        adapter_version="catalog-import-v1",
        input_fingerprint=original.fingerprint,
        target_entity_type="PackVersion",
        target_version_id=uuid4(),
        target_revision=1,
        target_digest=b"d" * 32,
    )
    full_db_session.add(ledger)
    full_db_session.flush()

    exact = service.resolve_reuse(original)
    changed = service.resolve_reuse(ImportItem(1, "Pack", "synthetic", "pack-1", {"title": "B"}))

    assert exact is not None and exact.disposition == ImportDisposition.REUSED_EXACT
    assert changed is not None
    assert changed.disposition == ImportDisposition.NEEDS_CONFLICT_REVIEW


# ---------------------------------------------------------------------------
# Dedicated Bugbot Remediation Tests (Findings 1 through 7)
# ---------------------------------------------------------------------------
def test_payload_substitution_rejected_against_admitted_fingerprint(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()
    items = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-sub-01",
            {"control_key": "CC-SEC-001", "title": "Original Control"},
        ),
    ]
    adm = service.admit_batch(actor, "batch-sub-01", items)

    # Substituted item with altered payload (different fingerprint)
    substituted_items = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-sub-01",
            {"control_key": "CC-SEC-001", "title": "Substituted Malicious Title"},
        ),
    ]

    with pytest.raises(CatalogConflictError, match="CONFLICT_CHANGED_BATCH_CONTENT"):
        service.execute_batch(actor, adm.batch.id, substituted_items)

    # Verify input row in DB was never mutated to ImportedDraft
    row = full_db_session.scalar(
        select(CatalogImportInput).where(CatalogImportInput.batch_id == adm.batch.id)
    )
    assert row is not None
    assert row.disposition == ImportDisposition.PENDING


def test_requirement_import_store_permission_enforcement(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    draft_svc = CatalogDraftService(full_db_session)
    actor = admin_actor()

    # Setup source version with only 'reference' and 'paraphrase' (lacking 'store')
    _, sv = setup_source_with_permissions(
        draft_svc,
        full_db_session,
        actor,
        source_key="src-no-store",
        use_cases=["reference", "paraphrase"],
    )

    items = [
        ImportItem(
            1,
            "Requirement",
            "synthetic",
            "req-store-01",
            {
                "source_version_id": str(sv.id),
                "requirement_key": "REQ-STORE-001",
                "text_origin": "conformly_paraphrase",
                "version_label": "1.0.0",
            },
        )
    ]

    adm = service.admit_batch(actor, "batch-store-01", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)

    assert manifest.counts_by_disposition.get("NeedsPermission") == 1
    row = full_db_session.scalar(
        select(CatalogImportInput).where(CatalogImportInput.batch_id == adm.batch.id)
    )
    assert row is not None
    assert row.disposition == ImportDisposition.NEEDS_PERMISSION
    assert row.reason_code == "PERMISSION_DENIED_STORE"


def test_dependency_lookup_origin_namespace_and_adapter_version_isolation(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    draft_svc = CatalogDraftService(full_db_session)
    actor = admin_actor()

    # Pre-populate reuse ledger with a requirement version from a different namespace 'foreign-ns'
    _, sv = setup_source_with_permissions(draft_svc, full_db_session, actor, source_key="src-iso")
    req = draft_svc.create_requirement(actor, "req-iso", sv.source_id, "REQ-ISO-001")
    req_v = draft_svc.create_requirement_version(
        actor,
        "req-v-iso",
        requirement_id=req.id,
        source_version_id=sv.id,
        version_label="1.0.0",
        normalized_outcome="Shall pass",
        requirement_type="mandatory",
        obligated_actor="organization",
        text_origin="conformly_paraphrase",
        source_references=[
            {"source_version_id": sv.id, "reference_type": "primary", "location": "1"}
        ],
    )
    foreign_reuse = CatalogImportReuseLedger(
        origin_namespace="foreign-ns",
        origin_id="dep-target-01",
        adapter_version="catalog-import-v1",
        input_fingerprint=b"f" * 32,
        target_entity_type="RequirementVersion",
        target_version_id=req_v.id,
        target_revision=req_v.revision,
        target_digest=req_v.content_digest,
        created_at=datetime.now(UTC),
    )
    full_db_session.add(foreign_reuse)
    full_db_session.commit()

    ctrl = draft_svc.create_common_control(
        actor, "ctrl-iso", control_key="CC-ISO-001", domain="governance"
    )
    ctrl_v = draft_svc.create_control_version(
        actor,
        "ctrl-v-iso",
        control_id=ctrl.id,
        version_label="1.0.0",
        title="Iso Control",
        objective="Iso Objective",
    )

    # Item in namespace 'primary-ns' attempts to reference 'dep-target-01'
    items = [
        ImportItem(
            1,
            "Mapping",
            "primary-ns",
            "map-iso-01",
            {
                "requirement_origin": "dep-target-01",
                "control_version_id": str(ctrl_v.id),
                "mapping_type": "Full",
                "rationale": "Mapping rationale",
            },
        )
    ]
    adm = service.admit_batch(actor, "batch-iso-01", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)

    # Cross-namespace reuse MUST NOT match: routes to NeedsMappingReview
    assert manifest.counts_by_disposition.get("NeedsMappingReview") == 1
    row = full_db_session.scalar(
        select(CatalogImportInput).where(CatalogImportInput.batch_id == adm.batch.id)
    )
    assert row is not None
    assert row.disposition == ImportDisposition.NEEDS_MAPPING_REVIEW
    assert row.reason_code == "MAPPING_ENDPOINT_UNRESOLVED"


def test_unexpected_failure_leaves_retryable_pending_work(full_db_session: Session, monkeypatch):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()

    items = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-rec-01",
            {"control_key": "CC-REC-001", "title": "Control 1"},
        ),
        ImportItem(
            2,
            "CommonControl",
            "synthetic",
            "cc-rec-02",
            {"control_key": "CC-REC-002", "title": "Control 2"},
        ),
    ]

    adm = service.admit_batch(actor, "batch-rec-01", items)

    # Monkeypatch _process_common_control to fail on the second item
    original_pcc = service._process_common_control

    def failing_pcc(context, req_key, input_row, item, draft_service, db_time):
        if item.origin_id == "cc-rec-02":
            raise RuntimeError("CATASTROPHIC_STORAGE_FAILURE")
        return original_pcc(context, req_key, input_row, item, draft_service, db_time)

    monkeypatch.setattr(service, "_process_common_control", failing_pcc)

    # Execution fails on second item and transitions batch to Interrupted
    with pytest.raises(RuntimeError, match="CATASTROPHIC_STORAGE_FAILURE"):
        service.execute_batch(actor, adm.batch.id, items)

    # Verify batch is Interrupted
    batch = full_db_session.get(CatalogImportBatch, adm.batch.id)
    assert batch is not None
    assert batch.status == "Interrupted"

    # Verify item 1 was committed as ImportedDraft, item 2 rolled back to Pending (NOT Rejected)
    rows = full_db_session.scalars(
        select(CatalogImportInput)
        .where(CatalogImportInput.batch_id == adm.batch.id)
        .order_by(CatalogImportInput.sequence.asc())
    ).all()
    assert rows[0].disposition == ImportDisposition.IMPORTED_DRAFT
    assert rows[1].disposition == ImportDisposition.PENDING

    # Restore unpatched method and resume batch execution
    monkeypatch.undo()
    manifest = service.execute_batch(actor, adm.batch.id, items)
    assert manifest.reconciled_inputs == 2
    assert manifest.counts_by_disposition.get("ImportedDraft") == 2


def test_atomic_audit_and_event_intents_persisted(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()

    items = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-audit-01",
            {"control_key": "CC-AUD-001", "title": "Control Audit"},
        ),
    ]
    adm = service.admit_batch(actor, "batch-audit-01", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)

    # Verify audit events for input evaluated and batch sealed
    events = full_db_session.scalars(
        select(CatalogAuditEvent).where(
            CatalogAuditEvent.action.in_(
                ["catalog.import.input_evaluated", "catalog.import.batch_sealed"]
            )
        )
    ).all()
    actions = {e.action for e in events}
    assert "catalog.import.input_evaluated" in actions
    assert "catalog.import.batch_sealed" in actions

    # Verify event intents for input evaluated and batch sealed
    intents = full_db_session.scalars(
        select(CatalogEventIntent).where(
            CatalogEventIntent.event_kind.in_(
                ["catalog.import.input_evaluated", "catalog.import.batch_sealed"]
            )
        )
    ).all()
    intent_kinds = {i.event_kind for i in intents}
    assert "catalog.import.input_evaluated" in intent_kinds
    assert "catalog.import.batch_sealed" in intent_kinds

    # Verify seal intent content digest matches manifest hash
    seal_intent = next(i for i in intents if i.event_kind == "catalog.import.batch_sealed")
    assert seal_intent.content_digest == manifest.manifest_hash


def test_batch_execution_deadline_interrupted(full_db_session: Session, monkeypatch):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()

    items = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-time-01",
            {"control_key": "CC-TIM-001", "title": "Control 1"},
        ),
        ImportItem(
            2,
            "CommonControl",
            "synthetic",
            "cc-time-02",
            {"control_key": "CC-TIM-002", "title": "Control 2"},
        ),
    ]
    adm = service.admit_batch(actor, "batch-time-01", items)

    # Simulate deadline expiring after input 1
    call_count = 0

    def fake_monotonic():
        nonlocal call_count
        call_count += 1
        if call_count > 2:
            return 999999999.0
        return 1.0

    monkeypatch.setattr(time, "monotonic", fake_monotonic)

    with pytest.raises(CatalogConflictError, match="BATCH_EXECUTION_DEADLINE_EXCEEDED"):
        service.execute_batch(actor, adm.batch.id, items)

    batch = full_db_session.get(CatalogImportBatch, adm.batch.id)
    assert batch is not None
    assert batch.status == "Interrupted"

    rows = full_db_session.scalars(
        select(CatalogImportInput)
        .where(CatalogImportInput.batch_id == adm.batch.id)
        .order_by(CatalogImportInput.sequence.asc())
    ).all()
    assert rows[0].disposition == ImportDisposition.IMPORTED_DRAFT
    assert rows[1].disposition == ImportDisposition.PENDING

    # Resuming with deadline restored finishes execution
    monkeypatch.undo()
    manifest = service.execute_batch(actor, adm.batch.id, items)
    assert manifest.reconciled_inputs == 2


def test_retry_backoff_releases_locks_on_serialization_failure(
    full_db_session: Session, monkeypatch
):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()

    items = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-retry-01",
            {"control_key": "CC-RET-001", "title": "Control Retry"},
        ),
    ]
    adm = service.admit_batch(actor, "batch-retry-01", items)

    # Simulate transient 40001 serialization failure on attempt 1, succeeding on attempt 2
    attempts = 0
    orig_pcc = service._process_single_input

    def flaky_pcc(context, batch, input_row, item, draft_service):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            err = _SqlStateError("serialization_failure")
            err.code = "40001"
            raise err
        return orig_pcc(context, batch, input_row, item, draft_service)

    monkeypatch.setattr(service, "_process_single_input", flaky_pcc)

    manifest = service.execute_batch(actor, adm.batch.id, items)
    assert manifest.reconciled_inputs == 1
    assert attempts == 2


# ---------------------------------------------------------------------------
# Bugbot Batch 2 Remediation Tests
# ---------------------------------------------------------------------------


def test_reconciled_replay_validates_fingerprints_before_manifest_return(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()

    items = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-rec-01",
            {"control_key": "CC-REC-001", "title": "Orig Title"},
        ),
    ]
    adm = service.admit_batch(actor, "batch-rec-replay-01", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)
    assert manifest.reconciled_inputs == 1

    # Attempt to replay with altered content on the reconciled batch
    altered_items = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-rec-01",
            {"control_key": "CC-REC-001", "title": "MODIFIED Title"},
        ),
    ]
    with pytest.raises(CatalogConflictError, match="CONFLICT_CHANGED_BATCH_CONTENT"):
        service.execute_batch(actor, adm.batch.id, altered_items)

    # Identical replay succeeds idempotently
    replayed_manifest = service.execute_batch(actor, adm.batch.id, items)
    assert replayed_manifest.batch_id == adm.batch.id
    assert replayed_manifest.reconciled_inputs == 1


def test_stale_exact_reuse_target_routes_to_conflict_review(full_db_session: Session, monkeypatch):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()

    items = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-stale-01",
            {
                "control_key": "CC-STAL-001",
                "title": "Existing Control",
                "statement": "Original statement",
            },
        ),
    ]
    # Batch 1 imports and creates the control draft
    adm1 = service.admit_batch(actor, "batch-stale-init", items)
    manifest1 = service.execute_batch(actor, adm1.batch.id, items)
    assert manifest1.reconciled_inputs == 1

    # Batch 2 admits same items for exact reuse
    adm2 = service.admit_batch(actor, "batch-stale-02", items)

    # Mock _verify_reuse_target to simulate stale target (e.g. target deleted or mutated concurrently)
    monkeypatch.setattr(service, "_verify_reuse_target", lambda ledger: False)

    manifest2 = service.execute_batch(actor, adm2.batch.id, items)
    assert manifest2.reconciled_inputs == 1

    row = full_db_session.scalars(
        select(CatalogImportInput).where(CatalogImportInput.batch_id == adm2.batch.id)
    ).one()
    assert row.disposition == ImportDisposition.NEEDS_CONFLICT_REVIEW
    assert row.reason_code == "CONFLICT_STALE_REUSE_TARGET"


def test_reused_exact_emits_input_reused_event_kind(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()

    items = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-reuse-kind-01",
            {
                "control_key": "CC-REUS-001",
                "title": "Reusable Control",
                "statement": "Reusable statement",
            },
        ),
    ]
    # Batch 1 imports as draft
    adm1 = service.admit_batch(actor, "batch-reuse-kind-01", items)
    manifest1 = service.execute_batch(actor, adm1.batch.id, items)
    assert manifest1.reconciled_inputs == 1

    # Batch 2 exact-reuses
    adm2 = service.admit_batch(actor, "batch-reuse-kind-02", items)
    manifest2 = service.execute_batch(actor, adm2.batch.id, items)
    assert manifest2.reconciled_inputs == 1

    input_row = full_db_session.scalars(
        select(CatalogImportInput).where(CatalogImportInput.batch_id == adm2.batch.id)
    ).one()
    assert input_row.disposition == ImportDisposition.REUSED_EXACT

    req_key = f"import:{input_row.batch_id}:{input_row.sequence}"

    # Verify event intent kind is catalog.import.input_reused
    intents = full_db_session.scalars(
        select(CatalogEventIntent).where(CatalogEventIntent.request_key == req_key)
    ).all()
    assert len(intents) == 1
    assert intents[0].event_kind == "catalog.import.input_reused"

    # Verify audit event action is catalog.import.input_reused
    audits = full_db_session.scalars(
        select(CatalogAuditEvent).where(CatalogAuditEvent.request_key == req_key)
    ).all()
    assert len(audits) == 1
    assert audits[0].action == "catalog.import.input_reused"


def test_batch_deadline_checked_during_retry_and_before_sealing(
    full_db_session: Session, monkeypatch
):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()

    # Part A: Retry backoff deadline check
    items_retry = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-dl-ret-01",
            {"control_key": "CC-RETR-001", "title": "DL Control"},
        ),
    ]
    adm_retry = service.admit_batch(actor, "batch-dl-retry-01", items_retry)

    def flaky_pcc(context, batch, input_row, item, draft_service):
        err = _SqlStateError("serialization_failure")
        err.code = "40001"
        raise err

    monkeypatch.setattr(service, "_process_single_input", flaky_pcc)

    orig_execute_input = service._execute_input_with_retry

    def wrap_execute_input(context, batch_id, input_id, item, draft_service, batch_deadline):
        return orig_execute_input(
            context, batch_id, input_id, item, draft_service, time.monotonic() - 10.0
        )

    monkeypatch.setattr(service, "_execute_input_with_retry", wrap_execute_input)

    with pytest.raises(CatalogConflictError, match="BATCH_EXECUTION_DEADLINE_EXCEEDED"):
        service.execute_batch(actor, adm_retry.batch.id, items_retry)

    batch_a = full_db_session.get(CatalogImportBatch, adm_retry.batch.id)
    assert batch_a is not None
    assert batch_a.status == "Interrupted"

    # Part B: Deadline before final sealing
    monkeypatch.undo()
    items_seal = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-dl-seal-01",
            {"control_key": "CC-SEAL-001", "title": "DL Seal Control"},
        ),
    ]
    adm_seal = service.admit_batch(actor, "batch-dl-seal-01", items_seal)

    real_time = time.monotonic()
    calls = 0

    def monotonic_expire_before_seal():
        nonlocal calls
        calls += 1
        # Calls 1 (started_at), 2 (loop check): real_time
        if calls <= 2:
            return real_time
        # Before sealing check: expired!
        return real_time + 400.0

    monkeypatch.setattr(time, "monotonic", monotonic_expire_before_seal)

    with pytest.raises(CatalogConflictError, match="BATCH_EXECUTION_DEADLINE_EXCEEDED"):
        service.execute_batch(actor, adm_seal.batch.id, items_seal)

    batch_b = full_db_session.get(CatalogImportBatch, adm_seal.batch.id)
    assert batch_b is not None
    assert batch_b.status == "Interrupted"


def test_requirement_import_preserves_locator_fields_in_draft_service(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    draft_svc = CatalogDraftService(full_db_session)
    actor = admin_actor()

    _, sv = setup_source_with_permissions(draft_svc, full_db_session, actor, source_key="src-loc")

    items = [
        ImportItem(
            sequence=1,
            input_type="Requirement",
            origin_namespace="synthetic",
            origin_id="req-loc-01",
            payload={
                "source_version_id": str(sv.id),
                "requirement_key": "REQ-LOC-001",
                "text_origin": "conformly_paraphrase",
                "version_label": "1.0.0",
                "locator_kind": "section",
                "locator_value": "1.2.3",
            },
        )
    ]
    adm = service.admit_batch(actor, "batch-req-locator-01", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)
    assert manifest.reconciled_inputs == 1

    input_row = full_db_session.scalars(
        select(CatalogImportInput).where(CatalogImportInput.batch_id == adm.batch.id)
    ).one()
    assert input_row.target_version_id is not None

    from conformly.catalog_v2.models import CatalogRequirementSourceReference

    ref_obj = full_db_session.scalars(
        select(CatalogRequirementSourceReference).where(
            CatalogRequirementSourceReference.requirement_version_id == input_row.target_version_id
        )
    ).first()
    assert ref_obj is not None
    assert ref_obj.locator_kind == "section"
    assert ref_obj.locator_value == "1.2.3"


def test_concurrent_first_admission_replays_idempotently_on_unique_constraint(
    full_db_session: Session, monkeypatch
):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()

    items = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-conc-adm-01",
            {"control_key": "CC-CADM-001", "title": "Conc Adm"},
        ),
    ]

    # Pre-insert the batch as if a concurrent worker committed it first
    first_adm = service.admit_batch(actor, "batch-conc-adm-01", items)

    # Simulate race condition: Worker 2 queries before Worker 1's commit is visible,
    # so Worker 2's initial check for existing batch returns None.
    # Worker 2 attempts insert; flush() raises real DB IntegrityError on duplicate batch_key.
    # The except IntegrityError block catches it, rolls back, and replays idempotently.
    orig_scalar = full_db_session.scalar
    initial_check_done = False

    def race_scalar(statement, *args, **kwargs):
        nonlocal initial_check_done
        if not initial_check_done:
            initial_check_done = True
            return None
        return orig_scalar(statement, *args, **kwargs)

    caught_rollback = False
    orig_rollback = full_db_session.rollback

    def spy_rollback():
        nonlocal caught_rollback
        caught_rollback = True
        orig_rollback()

    monkeypatch.setattr(full_db_session, "scalar", race_scalar)
    monkeypatch.setattr(full_db_session, "rollback", spy_rollback)

    second_adm = service.admit_batch(actor, "batch-conc-adm-01", items)
    assert initial_check_done is True, "Worker 2 must have attempted first admission"
    assert caught_rollback is True, "Worker 2 must have caught real IntegrityError and rolled back"
    assert second_adm.replayed is True
    assert second_adm.batch.id == first_adm.batch.id


def test_concurrent_sealer_intent_idempotency(full_db_session: Session):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()

    items = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-seal-idem-01",
            {"control_key": "CC-SEAL-001", "title": "Seal Idem"},
        ),
    ]
    adm = service.admit_batch(actor, "batch-seal-idem-01", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)
    assert manifest.reconciled_inputs == 1

    # Call seal_batch a second time; it should return the manifest idempotently without error
    manifest2 = service.seal_batch(actor, adm.batch.id)
    assert manifest2.batch_id == adm.batch.id
    assert manifest2.reconciled_inputs == 1


def test_statement_timeout_records_audit_and_event_intent(full_db_session: Session, monkeypatch):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()

    items = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-stmt-to-01",
            {"control_key": "CC-STMT-001", "title": "Stmt Timeout"},
        ),
    ]
    adm = service.admit_batch(actor, "batch-stmt-to-01", items)

    # Injected 57014 statement timeout during single input execution
    def failing_process(context, batch, input_row, item, draft_service):
        err = _SqlStateError("canceling statement due to statement timeout")
        err.code = "57014"
        raise err

    monkeypatch.setattr(service, "_process_single_input", failing_process)

    manifest = service.execute_batch(actor, adm.batch.id, items)
    assert manifest.reconciled_inputs == 1

    input_row = full_db_session.scalars(
        select(CatalogImportInput).where(CatalogImportInput.batch_id == adm.batch.id)
    ).one()
    assert input_row.disposition == ImportDisposition.REJECTED
    assert input_row.reason_code == "STATEMENT_TIMEOUT_EXCEEDED"

    req_key = f"import:{adm.batch.id}:1"
    # Verify atomic audit event was recorded
    audit_event = full_db_session.scalars(
        select(CatalogAuditEvent).where(
            CatalogAuditEvent.request_key == req_key,
        )
    ).first()
    assert audit_event is not None
    assert audit_event.action == "catalog.import.input_flagged"
    assert audit_event.outcome == "Denied"

    # Verify atomic event intent was recorded
    event_intent = full_db_session.scalars(
        select(CatalogEventIntent).where(
            CatalogEventIntent.request_key == req_key,
        )
    ).first()
    assert event_intent is not None
    assert event_intent.event_kind == "catalog.import.input_flagged"
    assert event_intent.aggregate_id == input_row.id


def test_statement_timeout_preserves_concurrently_finalized_disposition(
    full_db_session: Session, monkeypatch
):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()
    items = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-stmt-race-01",
            {"control_key": "CC-STRC-001", "title": "Statement timeout race"},
        )
    ]
    admission = service.admit_batch(actor, "batch-stmt-race-01", items)
    timeout_raised = False

    def failing_process(context, batch, input_row, item, draft_service):
        nonlocal timeout_raised
        timeout_raised = True
        error = _SqlStateError("canceling statement due to statement timeout")
        error.code = "57014"
        raise error

    original_scalar = full_db_session.scalar
    concurrent_finalization_injected = False

    def scalar_with_concurrent_finalization(statement, *args, **kwargs):
        nonlocal concurrent_finalization_injected
        row = original_scalar(statement, *args, **kwargs)
        if (
            timeout_raised
            and not concurrent_finalization_injected
            and isinstance(row, CatalogImportInput)
        ):
            concurrent_finalization_injected = True
            row.disposition = ImportDisposition.NEEDS_CONFLICT_REVIEW
            row.reason_code = "CONCURRENT_FINAL_RESULT"
            full_db_session.commit()
        return row

    monkeypatch.setattr(service, "_process_single_input", failing_process)
    monkeypatch.setattr(full_db_session, "scalar", scalar_with_concurrent_finalization)

    service.execute_batch(actor, admission.batch.id, items)

    row = full_db_session.scalars(
        select(CatalogImportInput).where(CatalogImportInput.batch_id == admission.batch.id)
    ).one()
    assert concurrent_finalization_injected is True
    assert row.disposition == ImportDisposition.NEEDS_CONFLICT_REVIEW
    assert row.reason_code == "CONCURRENT_FINAL_RESULT"


def test_reconciled_seal_replay_commits_transaction_and_releases_locks(
    full_db_session: Session, monkeypatch
):
    service = ConservativeImportService(full_db_session)
    actor = admin_actor()

    items = [
        ImportItem(
            1,
            "CommonControl",
            "synthetic",
            "cc-seal-rel-01",
            {"control_key": "CC-SREL-001", "title": "Seal Rel"},
        ),
    ]
    adm = service.admit_batch(actor, "batch-seal-rel-01", items)
    manifest = service.execute_batch(actor, adm.batch.id, items)

    committed = False
    orig_commit = full_db_session.commit

    def spy_commit():
        nonlocal committed
        committed = True
        orig_commit()

    monkeypatch.setattr(full_db_session, "commit", spy_commit)

    replayed = service.seal_batch(actor, adm.batch.id)
    assert replayed.manifest_hash == manifest.manifest_hash
    assert committed is True, (
        "Reconciled seal replay must commit cleanly to release FOR UPDATE row lock"
    )
