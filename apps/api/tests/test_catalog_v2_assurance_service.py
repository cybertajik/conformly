"""Unit tests for CatalogAssuranceDraftService lifecycle, boundaries, pins, and audit."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogCapability,
    CatalogConflictError,
    CatalogNotFoundError,
    CatalogSecurityError,
    CatalogValidationError,
)
from conformly.catalog_v2.audit import (
    LoggingDeniedAuditSink,
)
from conformly.catalog_v2.digest import compute_control_version_digest
from conformly.catalog_v2.models import (
    CatalogAssessmentProcedureStep,
    CatalogAuditEvent,
    CatalogCommonControl,
    CatalogControlVersion,
    CatalogEventIntent,
    CatalogEvidenceRequirementArtifactType,
    CatalogEvidenceRequirementVersion,
    CatalogMutationReceipt,
)
from conformly.catalog_v2.service_assurance import CatalogAssuranceDraftService
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
    return CatalogAssuranceDraftService(session=db_session, denied_audit_sink=denied_sink)


@pytest.fixture
def writer_context():
    return CatalogActorContext(
        actor_id=uuid4(),
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC),
        capabilities=frozenset({CatalogCapability.DRAFT_WRITE, CatalogCapability.DRAFT_READ}),
    )


@pytest.fixture
def reader_context():
    return CatalogActorContext(
        actor_id=uuid4(),
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC),
        capabilities=frozenset({CatalogCapability.DRAFT_READ}),
    )


@pytest.fixture
def unauthorized_context():
    return CatalogActorContext(
        actor_id=uuid4(),
        is_platform_admin=True,
        mfa_verified=True,
        authenticated_at=datetime.now(UTC),
        capabilities=frozenset(),
    )


def make_test_control_version(session: Session, control_key: str = "CC-TEST-001"):
    ctrl = CatalogCommonControl(
        id=uuid4(),
        control_key=control_key,
        domain="Security Operations",
        status="Draft",
    )
    session.add(ctrl)
    session.flush()

    cv_digest = compute_control_version_digest(
        control_id=ctrl.id,
        version_label="1.0.0",
        predecessor_id=None,
        revision=1,
        title=f"Test Control {control_key}",
        objective="Ensure baseline controls.",
        guidance=None,
        control_type="preventive",
        frequency="continuous",
        automation_level="automated",
        suggested_owner_role="Security Lead",
        assurance_level="foundational",
        tags_state="None",
        tags=None,
    )

    cv = CatalogControlVersion(
        id=uuid4(),
        control_id=ctrl.id,
        version_label="1.0.0",
        revision=1,
        title=f"Test Control {control_key}",
        objective="Ensure baseline controls.",
        control_type="preventive",
        frequency="continuous",
        automation_level="automated",
        suggested_owner_role="Security Lead",
        assurance_level="foundational",
        status="Draft",
        content_digest=cv_digest,
        digest_schema="catalog-draft-v1",
    )
    session.add(cv)
    session.flush()
    return ctrl, cv


def test_actor_authorization_and_denial_audit_writes(
    service: CatalogAssuranceDraftService,
    unauthorized_context: CatalogActorContext,
    denied_sink: LoggingDeniedAuditSink,
    db_session: Session,
):
    _, cv = make_test_control_version(db_session, "CC-ATH-001")

    # 1. Deny ER creation
    with pytest.raises(CatalogSecurityError):
        service.create_evidence_requirement_version(
            context=unauthorized_context,
            request_key="req-auth-er",
            control_version_id=cv.id,
            expected_control_digest=cv.content_digest,
            requirement_key="ER-AUTH-001",
            title="Unauthorized ER",
            frequency="monthly",
            custom_frequency=None,
            scope_state="All",
            scope_guidance=None,
            assurance_purpose="operating_effectiveness",
            validity_rule="period_coverage",
            max_age_days=None,
            guidance=None,
            artifact_types=["record"],
            required_metadata=[],
        )

    # 2. Deny AP creation
    with pytest.raises(CatalogSecurityError):
        service.create_assessment_procedure_version(
            context=unauthorized_context,
            request_key="req-auth-ap",
            control_version_id=cv.id,
            expected_control_digest=cv.content_digest,
            procedure_key="AP-AUTH-001",
            title="Unauthorized AP",
            objective="Objective",
            sample_guidance=None,
            scope_guidance=None,
            decision_guidance="Decision guidance",
            assessor_qualifications=None,
            steps=[{"step_kind": "inspect", "instruction": "Inspect", "expected_output": None}],
            evidence_requirements=[],
        )

    # Verify denied audit sink records
    assert len(denied_sink.recorded_denials) == 2
    assert denied_sink.recorded_denials[0]["operation"] == "create_evidence_requirement_version"
    assert denied_sink.recorded_denials[1]["operation"] == "create_assessment_procedure_version"

    # Verify domain tables have no partial rows
    ers = db_session.execute(select(CatalogEvidenceRequirementVersion)).scalars().all()
    assert len(ers) == 0


def test_actor_authorization_and_denial_audit_reads(
    service: CatalogAssuranceDraftService,
    unauthorized_context: CatalogActorContext,
    denied_sink: LoggingDeniedAuditSink,
):
    dummy_id = uuid4()
    with pytest.raises(CatalogSecurityError):
        service.get_evidence_requirement_version(unauthorized_context, dummy_id)

    with pytest.raises(CatalogSecurityError):
        service.get_assessment_procedure_version(unauthorized_context, dummy_id)

    with pytest.raises(CatalogSecurityError):
        service.list_evidence_requirement_versions(unauthorized_context, dummy_id)

    with pytest.raises(CatalogSecurityError):
        service.list_assessment_procedure_versions(unauthorized_context, dummy_id)

    assert len(denied_sink.recorded_denials) == 4


def test_create_and_get_evidence_requirement_lifecycle(
    service: CatalogAssuranceDraftService,
    writer_context: CatalogActorContext,
    reader_context: CatalogActorContext,
    db_session: Session,
):
    _, cv = make_test_control_version(db_session, "CC-OPS-001")

    # Create ER with 2 artifact types and 2 metadata keys
    snap = service.create_evidence_requirement_version(
        context=writer_context,
        request_key="req-er-001",
        control_version_id=cv.id,
        expected_control_digest=cv.content_digest,
        requirement_key="ER-ACCESS-REVIEW",
        title="Access Review Artifacts",
        frequency="quarterly",
        custom_frequency=None,
        scope_state="Conditional",
        scope_guidance="Production only",
        assurance_purpose="operating_effectiveness",
        validity_rule="point_in_time",
        max_age_days=90,
        guidance="Provide export file.",
        artifact_types=["record", "report"],
        required_metadata=["system_id", "reviewer_email"],
    )

    assert snap.sequence == 1
    assert snap.status == "Draft"
    assert snap.digest_schema == "catalog-assurance-draft-v1"
    assert len(snap.content_digest) == 32
    assert len(snap.artifact_types) == 2
    assert snap.artifact_types[0].sequence == 1
    assert snap.artifact_types[0].artifact_type == "record"
    assert snap.artifact_types[1].sequence == 2
    assert snap.artifact_types[1].artifact_type == "report"
    assert len(snap.required_metadata) == 2
    assert snap.required_metadata[0].sequence == 1
    assert snap.required_metadata[0].metadata_key == "system_id"
    assert snap.required_metadata[1].sequence == 2
    assert snap.required_metadata[1].metadata_key == "reviewer_email"

    # Get by ID as reader
    fetched = service.get_evidence_requirement_version(reader_context, snap.id)
    assert fetched.id == snap.id
    assert fetched.content_digest == snap.content_digest
    assert fetched.title == snap.title

    # Verify atomic audit event, intent, receipt
    receipt = db_session.execute(
        select(CatalogMutationReceipt).where(CatalogMutationReceipt.request_key == "req-er-001")
    ).scalar_one()
    assert receipt.result_id == snap.id
    assert receipt.result_type == "CatalogEvidenceRequirementVersion"
    assert receipt.result_revision == 1

    intent = db_session.execute(
        select(CatalogEventIntent).where(CatalogEventIntent.request_key == "req-er-001")
    ).scalar_one()
    assert intent.event_kind == "evidence_requirement_version.created"
    assert intent.aggregate_id == snap.id

    audit = db_session.execute(
        select(CatalogAuditEvent).where(CatalogAuditEvent.request_key == "req-er-001")
    ).scalar_one()
    assert audit.action == "evidence_requirement_version.created"
    assert audit.resource_id == snap.id
    assert audit.metadata_json["artifact_type_count"] == 2
    assert audit.metadata_json["metadata_key_count"] == 2


def test_create_and_get_assessment_procedure_lifecycle(
    service: CatalogAssuranceDraftService,
    writer_context: CatalogActorContext,
    reader_context: CatalogActorContext,
    db_session: Session,
):
    _, cv = make_test_control_version(db_session, "CC-OPS-002")

    # Create linked ER first
    er_snap = service.create_evidence_requirement_version(
        context=writer_context,
        request_key="req-er-for-ap",
        control_version_id=cv.id,
        expected_control_digest=cv.content_digest,
        requirement_key="ER-PASSWORDS",
        title="Password Policy Evidence",
        frequency="continuous",
        custom_frequency=None,
        scope_state="All",
        scope_guidance=None,
        assurance_purpose="design",
        validity_rule="continuous",
        max_age_days=None,
        guidance=None,
        artifact_types=["configuration"],
        required_metadata=[],
    )

    # Create AP linking to the ER
    ap_snap = service.create_assessment_procedure_version(
        context=writer_context,
        request_key="req-ap-001",
        control_version_id=cv.id,
        expected_control_digest=cv.content_digest,
        procedure_key="AP-PASSWORDS-VERIFY",
        title="Password Configuration Inspection",
        objective="Verify password complexity is enforced.",
        sample_guidance="Inspect all domains.",
        scope_guidance="Enterprise systems.",
        decision_guidance="Ensure 14+ characters.",
        assessor_qualifications="Certified Information Security Auditor",
        steps=[
            {
                "step_kind": "inspect",
                "instruction": "Open identity management console.",
                "expected_output": "Configuration console accessible.",
            },
            {
                "step_kind": "inquire",
                "instruction": "Interview IAM admin.",
                "expected_output": None,
            },
        ],
        evidence_requirements=[{"id": er_snap.id, "content_digest": er_snap.content_digest}],
    )

    assert ap_snap.sequence == 1
    assert ap_snap.status == "Draft"
    assert len(ap_snap.steps) == 2
    assert ap_snap.steps[0].sequence == 1
    assert ap_snap.steps[0].step_kind == "inspect"
    assert ap_snap.steps[1].sequence == 2
    assert ap_snap.steps[1].expected_output is None
    assert len(ap_snap.evidence_requirements) == 1
    assert ap_snap.evidence_requirements[0].sequence == 1
    assert ap_snap.evidence_requirements[0].evidence_requirement_version_id == er_snap.id
    assert ap_snap.evidence_requirements[0].content_digest == er_snap.content_digest

    # Read AP back
    fetched = service.get_assessment_procedure_version(reader_context, ap_snap.id)
    assert fetched.id == ap_snap.id
    assert fetched.content_digest == ap_snap.content_digest
    assert len(fetched.steps) == 2
    assert len(fetched.evidence_requirements) == 1


def test_boundary_validations_evidence_requirement(
    service: CatalogAssuranceDraftService,
    writer_context: CatalogActorContext,
    db_session: Session,
):
    _, cv = make_test_control_version(db_session, "CC-BND-001")

    base_args = {
        "context": writer_context,
        "request_key": "req-bound-er",
        "control_version_id": cv.id,
        "expected_control_digest": cv.content_digest,
        "requirement_key": "ER-BOUND-001",
        "title": "Valid Title",
        "frequency": "monthly",
        "custom_frequency": None,
        "scope_state": "All",
        "scope_guidance": None,
        "assurance_purpose": "operating_effectiveness",
        "validity_rule": "period_coverage",
        "max_age_days": None,
        "guidance": None,
        "artifact_types": ["record"],
        "required_metadata": [],
    }

    # 1. Invalid requirement_key
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(**(base_args | {"requirement_key": "INVALID"}))
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(**(base_args | {"requirement_key": "ER-ab"}))
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(
            **(base_args | {"requirement_key": "ER-lowercase-not-allowed"})
        )

    # 2. Leading/trailing whitespace
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(**(base_args | {"title": " Leading space"}))
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(**(base_args | {"guidance": "Trailing space "}))

    # 3. Frequency / custom_frequency mismatch
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(
            **(base_args | {"frequency": "custom", "custom_frequency": None})
        )
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(
            **(base_args | {"frequency": "monthly", "custom_frequency": "Every week"})
        )

    # 4. Scope state / guidance mismatch
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(
            **(base_args | {"scope_state": "Conditional", "scope_guidance": None})
        )
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(
            **(base_args | {"scope_state": "All", "scope_guidance": "Unneeded"})
        )

    # 5. Validity rule / max_age_days mismatch
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(
            **(base_args | {"validity_rule": "point_in_time", "max_age_days": None})
        )
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(
            **(base_args | {"validity_rule": "period_coverage", "max_age_days": 30})
        )
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(
            **(base_args | {"validity_rule": "point_in_time", "max_age_days": 0})
        )
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(
            **(base_args | {"validity_rule": "point_in_time", "max_age_days": 3661})
        )

    # 6. Artifact types: 0 (min 1), > 16 (max 16), duplicates
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(**(base_args | {"artifact_types": []}))
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(
            **(base_args | {"artifact_types": ["record", "record"]})
        )

    # 7. Metadata keys: > 32 (max 32), duplicates, invalid format
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(
            **(base_args | {"required_metadata": ["UPPERCASE_KEY"]})
        )
    with pytest.raises(CatalogValidationError):
        service.create_evidence_requirement_version(
            **(base_args | {"required_metadata": ["dup_key", "dup_key"]})
        )


def test_parent_pin_and_digest_validation(
    service: CatalogAssuranceDraftService,
    writer_context: CatalogActorContext,
    db_session: Session,
):
    _, cv1 = make_test_control_version(db_session, "CC-PIN-001")
    _, cv2 = make_test_control_version(db_session, "CC-PIN-002")

    # 1. Missing parent ControlVersion
    with pytest.raises(CatalogNotFoundError):
        service.create_evidence_requirement_version(
            context=writer_context,
            request_key="req-missing-parent",
            control_version_id=uuid4(),
            expected_control_digest=cv1.content_digest,
            requirement_key="ER-PIN-001",
            title="Title",
            frequency="monthly",
            custom_frequency=None,
            scope_state="All",
            scope_guidance=None,
            assurance_purpose="operating_effectiveness",
            validity_rule="period_coverage",
            max_age_days=None,
            guidance=None,
            artifact_types=["record"],
            required_metadata=[],
        )

    # 2. Control digest mismatch
    with pytest.raises(CatalogConflictError):
        service.create_evidence_requirement_version(
            context=writer_context,
            request_key="req-wrong-digest",
            control_version_id=cv1.id,
            expected_control_digest=b"\x00" * 32,
            requirement_key="ER-PIN-002",
            title="Title",
            frequency="monthly",
            custom_frequency=None,
            scope_state="All",
            scope_guidance=None,
            assurance_purpose="operating_effectiveness",
            validity_rule="period_coverage",
            max_age_days=None,
            guidance=None,
            artifact_types=["record"],
            required_metadata=[],
        )

    # 3. Cross-control evidence requirement link in procedure
    er_cv2 = service.create_evidence_requirement_version(
        context=writer_context,
        request_key="req-er-cv2",
        control_version_id=cv2.id,
        expected_control_digest=cv2.content_digest,
        requirement_key="ER-PIN-CV2",
        title="Title CV2",
        frequency="monthly",
        custom_frequency=None,
        scope_state="All",
        scope_guidance=None,
        assurance_purpose="operating_effectiveness",
        validity_rule="period_coverage",
        max_age_days=None,
        guidance=None,
        artifact_types=["record"],
        required_metadata=[],
    )

    with pytest.raises(CatalogValidationError):
        # Attempting to link CV2 ER into a CV1 Procedure
        service.create_assessment_procedure_version(
            context=writer_context,
            request_key="req-ap-cross-cv",
            control_version_id=cv1.id,
            expected_control_digest=cv1.content_digest,
            procedure_key="AP-PIN-CROSS",
            title="Procedure Title",
            objective="Objective",
            sample_guidance=None,
            scope_guidance=None,
            decision_guidance="Decision guidance",
            assessor_qualifications=None,
            steps=[{"step_kind": "inspect", "instruction": "Inspect", "expected_output": None}],
            evidence_requirements=[{"id": er_cv2.id, "content_digest": er_cv2.content_digest}],
        )


def test_idempotent_retry_and_conflict(
    service: CatalogAssuranceDraftService,
    writer_context: CatalogActorContext,
    db_session: Session,
):
    _, cv = make_test_control_version(db_session, "CC-RET-001")

    req_args = {
        "context": writer_context,
        "request_key": "req-idempotent-001",
        "control_version_id": cv.id,
        "expected_control_digest": cv.content_digest,
        "requirement_key": "ER-IDEMP-001",
        "title": "Idempotent Title",
        "frequency": "monthly",
        "custom_frequency": None,
        "scope_state": "All",
        "scope_guidance": None,
        "assurance_purpose": "operating_effectiveness",
        "validity_rule": "period_coverage",
        "max_age_days": None,
        "guidance": None,
        "artifact_types": ["record"],
        "required_metadata": [],
    }

    snap1 = service.create_evidence_requirement_version(**req_args)

    # Retry with exact same arguments and request_key
    snap2 = service.create_evidence_requirement_version(**req_args)

    assert snap1.id == snap2.id
    assert snap1.content_digest == snap2.content_digest
    assert snap1.sequence == snap2.sequence

    # Only 1 mutation receipt, 1 event intent, 1 audit event
    receipts = (
        db_session.execute(
            select(CatalogMutationReceipt).where(
                CatalogMutationReceipt.request_key == "req-idempotent-001"
            )
        )
        .scalars()
        .all()
    )
    assert len(receipts) == 1

    intents = (
        db_session.execute(
            select(CatalogEventIntent).where(CatalogEventIntent.request_key == "req-idempotent-001")
        )
        .scalars()
        .all()
    )
    assert len(intents) == 1

    audits = (
        db_session.execute(
            select(CatalogAuditEvent).where(CatalogAuditEvent.request_key == "req-idempotent-001")
        )
        .scalars()
        .all()
    )
    assert len(audits) == 1

    # Conflict: reusing request_key with changed arguments
    conflict_args = req_args | {"title": "Different Title"}
    with pytest.raises(CatalogConflictError):
        service.create_evidence_requirement_version(**conflict_args)


def test_digest_tampering_and_corruption_detection(
    service: CatalogAssuranceDraftService,
    writer_context: CatalogActorContext,
    reader_context: CatalogActorContext,
    db_session: Session,
):
    _, cv = make_test_control_version(db_session, "CC-TMP-001")

    snap = service.create_evidence_requirement_version(
        context=writer_context,
        request_key="req-tamper-001",
        control_version_id=cv.id,
        expected_control_digest=cv.content_digest,
        requirement_key="ER-TAMPER-001",
        title="Tamper Test",
        frequency="monthly",
        custom_frequency=None,
        scope_state="All",
        scope_guidance=None,
        assurance_purpose="operating_effectiveness",
        validity_rule="period_coverage",
        max_age_days=None,
        guidance=None,
        artifact_types=["record"],
        required_metadata=[],
    )

    # 1. Tamper child row: insert extra artifact type directly into DB
    extra_art = CatalogEvidenceRequirementArtifactType(
        id=uuid4(),
        evidence_requirement_version_id=snap.id,
        control_version_id=cv.id,
        sequence=2,
        artifact_type="report",
    )
    db_session.add(extra_art)
    db_session.flush()

    # Reading should detect digest mismatch with recomputed aggregate
    with pytest.raises(CatalogSecurityError):
        service.get_evidence_requirement_version(reader_context, snap.id)


def test_list_evidence_requirements_and_procedures(
    service: CatalogAssuranceDraftService,
    writer_context: CatalogActorContext,
    reader_context: CatalogActorContext,
    db_session: Session,
):
    _, cv1 = make_test_control_version(db_session, "CC-LST-001")
    _, cv2 = make_test_control_version(db_session, "CC-LST-002")

    # Create 2 ERs on CV1
    er1 = service.create_evidence_requirement_version(
        context=writer_context,
        request_key="req-list-er1",
        control_version_id=cv1.id,
        expected_control_digest=cv1.content_digest,
        requirement_key="ER-LIST-001",
        title="ER 1",
        frequency="monthly",
        custom_frequency=None,
        scope_state="All",
        scope_guidance=None,
        assurance_purpose="operating_effectiveness",
        validity_rule="period_coverage",
        max_age_days=None,
        guidance=None,
        artifact_types=["record"],
        required_metadata=[],
    )
    er2 = service.create_evidence_requirement_version(
        context=writer_context,
        request_key="req-list-er2",
        control_version_id=cv1.id,
        expected_control_digest=cv1.content_digest,
        requirement_key="ER-LIST-002",
        title="ER 2",
        frequency="annual",
        custom_frequency=None,
        scope_state="All",
        scope_guidance=None,
        assurance_purpose="design",
        validity_rule="continuous",
        max_age_days=None,
        guidance=None,
        artifact_types=["report"],
        required_metadata=[],
    )

    # List for CV1
    items = service.list_evidence_requirement_versions(reader_context, cv1.id)
    assert len(items) == 2
    assert [i.id for i in items] == [er1.id, er2.id]
    assert [i.sequence for i in items] == [1, 2]

    # CV2 has 0
    items_cv2 = service.list_evidence_requirement_versions(reader_context, cv2.id)
    assert len(items_cv2) == 0

    # Pagination bounds
    with pytest.raises(CatalogValidationError):
        service.list_evidence_requirement_versions(reader_context, cv1.id, offset=-1)
    with pytest.raises(CatalogValidationError):
        service.list_evidence_requirement_versions(reader_context, cv1.id, limit=0)
    with pytest.raises(CatalogValidationError):
        service.list_evidence_requirement_versions(reader_context, cv1.id, limit=101)


def test_payload_byte_limit_rejection(
    service: CatalogAssuranceDraftService,
    writer_context: CatalogActorContext,
    db_session: Session,
):
    _, cv = make_test_control_version(db_session, "CC-BND-002")

    # Over 262144 bytes by repeated metadata keys / links
    huge_steps = [
        {
            "step_kind": "inspect",
            "instruction": "I" * 4000,
            "expected_output": "E" * 2000,
        }
        for _ in range(50)
    ]

    with pytest.raises(CatalogValidationError, match="canonical UTF-8 bytes"):
        service.create_assessment_procedure_version(
            context=writer_context,
            request_key="req-huge",
            control_version_id=cv.id,
            expected_control_digest=cv.content_digest,
            procedure_key="AP-HUGE-001",
            title="Huge procedure",
            objective="O" * 4000,
            sample_guidance="S" * 2000,
            scope_guidance="G" * 2000,
            decision_guidance="D" * 4000,
            assessor_qualifications="Q" * 2000,
            steps=huge_steps,
            evidence_requirements=[],
        )


def test_idempotent_retry_sequence_and_digest_validation(
    service: CatalogAssuranceDraftService,
    writer_context: CatalogActorContext,
    db_session: Session,
):
    _, cv = make_test_control_version(db_session, "CC-RTR-001")

    # 1. Evidence Requirement retry sequence and digest check
    req_args = {
        "context": writer_context,
        "request_key": "req-retry-er-001",
        "control_version_id": cv.id,
        "expected_control_digest": cv.content_digest,
        "requirement_key": "ER-RETRY-001",
        "title": "Retry ER",
        "frequency": "quarterly",
        "custom_frequency": None,
        "scope_state": "All",
        "scope_guidance": None,
        "assurance_purpose": "design",
        "validity_rule": "continuous",
        "max_age_days": None,
        "guidance": None,
        "artifact_types": ["document"],
        "required_metadata": [],
    }
    er_snap = service.create_evidence_requirement_version(**req_args)
    # Valid retry works
    retry_snap = service.create_evidence_requirement_version(**req_args)
    assert retry_snap.id == er_snap.id

    receipt = db_session.execute(
        select(CatalogMutationReceipt).where(
            CatalogMutationReceipt.request_key == "req-retry-er-001"
        )
    ).scalar_one()

    # Tamper receipt sequence
    original_seq = receipt.result_revision
    receipt.result_revision = 99
    db_session.flush()

    with pytest.raises(CatalogConflictError, match="Receipt sequence mismatch"):
        service.create_evidence_requirement_version(**req_args)

    # Restore sequence, tamper receipt digest
    receipt.result_revision = original_seq
    original_digest = receipt.result_digest
    receipt.result_digest = b"\x00" * 32
    db_session.flush()

    with pytest.raises(CatalogConflictError, match="Receipt digest mismatch"):
        service.create_evidence_requirement_version(**req_args)

    receipt.result_digest = original_digest
    db_session.flush()

    # 2. Assessment Procedure retry sequence and digest check
    ap_args = {
        "context": writer_context,
        "request_key": "req-retry-ap-001",
        "control_version_id": cv.id,
        "expected_control_digest": cv.content_digest,
        "procedure_key": "AP-RETRY-001",
        "title": "Retry AP",
        "objective": "Verify retry safeguards",
        "sample_guidance": None,
        "scope_guidance": None,
        "decision_guidance": "Pass if retry checks match",
        "assessor_qualifications": None,
        "steps": [{"step_kind": "inspect", "instruction": "Check receipt verification"}],
        "evidence_requirements": [],
    }
    ap_snap = service.create_assessment_procedure_version(**ap_args)
    retry_ap_snap = service.create_assessment_procedure_version(**ap_args)
    assert retry_ap_snap.id == ap_snap.id

    receipt_ap = db_session.execute(
        select(CatalogMutationReceipt).where(
            CatalogMutationReceipt.request_key == "req-retry-ap-001"
        )
    ).scalar_one()

    # Tamper AP receipt sequence
    original_ap_seq = receipt_ap.result_revision
    receipt_ap.result_revision = 99
    db_session.flush()

    with pytest.raises(CatalogConflictError, match="Receipt sequence mismatch"):
        service.create_assessment_procedure_version(**ap_args)

    # Restore AP sequence, tamper receipt digest
    receipt_ap.result_revision = original_ap_seq
    original_ap_digest = receipt_ap.result_digest
    receipt_ap.result_digest = b"\x00" * 32
    db_session.flush()

    with pytest.raises(CatalogConflictError, match="Receipt digest mismatch"):
        service.create_assessment_procedure_version(**ap_args)

    receipt_ap.result_digest = original_ap_digest
    db_session.flush()


def test_structured_inputs_extra_fields_and_alias_conflicts(
    service: CatalogAssuranceDraftService,
    writer_context: CatalogActorContext,
    db_session: Session,
):
    _, cv = make_test_control_version(db_session, "CC-STR-001")

    base_er_args = {
        "context": writer_context,
        "control_version_id": cv.id,
        "expected_control_digest": cv.content_digest,
        "requirement_key": "ER-STRUCT-001",
        "title": "Structured ER",
        "frequency": "annual",
        "custom_frequency": None,
        "scope_state": "All",
        "scope_guidance": None,
        "assurance_purpose": "design",
        "validity_rule": "continuous",
        "max_age_days": None,
        "guidance": None,
        "artifact_types": ["document"],
        "required_metadata": [],
    }

    # ER artifact_types extra fields
    with pytest.raises(CatalogValidationError, match="contains unrecognized extra fields"):
        service.create_evidence_requirement_version(
            **(
                base_er_args
                | {
                    "request_key": "req-bad-art-extra",
                    "artifact_types": [{"artifact_type": "document", "extra_field": "disallowed"}],
                }
            )
        )

    # ER artifact_types sequence mismatch
    with pytest.raises(CatalogValidationError, match="sequence mismatch"):
        service.create_evidence_requirement_version(
            **(
                base_er_args
                | {
                    "request_key": "req-bad-art-seq",
                    "artifact_types": [{"artifact_type": "document", "sequence": 2}],
                }
            )
        )

    # ER required_metadata extra fields
    with pytest.raises(CatalogValidationError, match="contains unrecognized extra fields"):
        service.create_evidence_requirement_version(
            **(
                base_er_args
                | {
                    "request_key": "req-bad-meta-extra",
                    "required_metadata": [{"metadata_key": "owner", "extra_field": "disallowed"}],
                }
            )
        )

    # ER required_metadata sequence mismatch
    with pytest.raises(CatalogValidationError, match="sequence mismatch"):
        service.create_evidence_requirement_version(
            **(
                base_er_args
                | {
                    "request_key": "req-bad-meta-seq",
                    "required_metadata": [{"metadata_key": "owner", "sequence": 2}],
                }
            )
        )

    # Create a valid ER for linking
    valid_er = service.create_evidence_requirement_version(
        **(base_er_args | {"request_key": "req-valid-er-for-link"})
    )

    base_ap_args = {
        "context": writer_context,
        "control_version_id": cv.id,
        "expected_control_digest": cv.content_digest,
        "procedure_key": "AP-STRUCT-001",
        "title": "Structured AP",
        "objective": "Verify input constraints",
        "sample_guidance": None,
        "scope_guidance": None,
        "decision_guidance": "Pass if structured constraints enforced",
        "assessor_qualifications": None,
        "steps": [{"step_kind": "inspect", "instruction": "Check inputs"}],
        "evidence_requirements": [],
    }

    # AP steps extra fields
    with pytest.raises(CatalogValidationError, match="contains unrecognized extra fields"):
        service.create_assessment_procedure_version(
            **(
                base_ap_args
                | {
                    "request_key": "req-bad-step-extra",
                    "steps": [{"step_kind": "inspect", "instruction": "Check", "extra_param": 123}],
                }
            )
        )

    # AP steps sequence mismatch
    with pytest.raises(CatalogValidationError, match="sequence mismatch"):
        service.create_assessment_procedure_version(
            **(
                base_ap_args
                | {
                    "request_key": "req-bad-step-seq",
                    "steps": [{"step_kind": "inspect", "instruction": "Check", "sequence": 5}],
                }
            )
        )

    # AP evidence_requirements extra fields
    with pytest.raises(CatalogValidationError, match="contains unrecognized extra fields"):
        service.create_assessment_procedure_version(
            **(
                base_ap_args
                | {
                    "request_key": "req-bad-link-extra",
                    "evidence_requirements": [
                        {
                            "id": valid_er.id,
                            "content_digest": valid_er.content_digest,
                            "unrecognized_field": True,
                        }
                    ],
                }
            )
        )

    # AP evidence_requirements conflicting ID aliases
    with pytest.raises(CatalogValidationError, match="conflicting id aliases"):
        service.create_assessment_procedure_version(
            **(
                base_ap_args
                | {
                    "request_key": "req-conflict-alias",
                    "evidence_requirements": [
                        {
                            "id": valid_er.id,
                            "evidence_requirement_version_id": uuid4(),
                            "content_digest": valid_er.content_digest,
                        }
                    ],
                }
            )
        )

    # AP evidence_requirements matching ID aliases should be accepted
    ap_matching_alias = service.create_assessment_procedure_version(
        **(
            base_ap_args
            | {
                "request_key": "req-matching-alias",
                "evidence_requirements": [
                    {
                        "id": valid_er.id,
                        "evidence_requirement_version_id": valid_er.id,
                        "content_digest": valid_er.content_digest,
                    }
                ],
            }
        )
    )
    assert len(ap_matching_alias.evidence_requirements) == 1

    # AP evidence_requirements sequence mismatch
    with pytest.raises(CatalogValidationError, match="sequence mismatch"):
        service.create_assessment_procedure_version(
            **(
                base_ap_args
                | {
                    "request_key": "req-bad-link-seq",
                    "procedure_key": "AP-STRUCT-002",
                    "evidence_requirements": [
                        {
                            "id": valid_er.id,
                            "content_digest": valid_er.content_digest,
                            "sequence": 9,
                        }
                    ],
                }
            )
        )


def test_aggregate_reads_reject_zero_artifacts_or_steps(
    service: CatalogAssuranceDraftService,
    writer_context: CatalogActorContext,
    reader_context: CatalogActorContext,
    db_session: Session,
):
    _, cv = make_test_control_version(db_session, "CC-INC-001")

    # 1. Evidence Requirement with 0 artifact types
    er = service.create_evidence_requirement_version(
        context=writer_context,
        request_key="req-er-zero-art",
        control_version_id=cv.id,
        expected_control_digest=cv.content_digest,
        requirement_key="ER-ZERO-ART",
        title="Zero Artifacts ER",
        frequency="annual",
        custom_frequency=None,
        scope_state="All",
        scope_guidance=None,
        assurance_purpose="design",
        validity_rule="continuous",
        max_age_days=None,
        guidance=None,
        artifact_types=["document"],
        required_metadata=[],
    )

    # Manually delete artifact types to simulate incomplete / corrupted state
    for row in (
        db_session.execute(
            select(CatalogEvidenceRequirementArtifactType).where(
                CatalogEvidenceRequirementArtifactType.evidence_requirement_version_id == er.id
            )
        )
        .scalars()
        .all()
    ):
        db_session.delete(row)
    db_session.flush()

    with pytest.raises(
        CatalogSecurityError, match="corrupt aggregate: expected 1..16 artifact types, got 0"
    ):
        service.get_evidence_requirement_version(reader_context, er.id)

    with pytest.raises(
        CatalogSecurityError, match="corrupt aggregate: expected 1..16 artifact types, got 0"
    ):
        service.list_evidence_requirement_versions(reader_context, cv.id)

    er_db = db_session.get(CatalogEvidenceRequirementVersion, er.id)
    assert er_db is not None
    with pytest.raises(
        CatalogSecurityError, match="corrupt aggregate: expected 1..16 artifact types, got 0"
    ):
        service._recompute_er_digest(er_db, cv.content_digest)

    # 2. Assessment Procedure with 0 steps
    # Create another ER for AP link
    er_for_ap = service.create_evidence_requirement_version(
        context=writer_context,
        request_key="req-er-for-zero-step-ap",
        control_version_id=cv.id,
        expected_control_digest=cv.content_digest,
        requirement_key="ER-FOR-AP",
        title="ER for AP",
        frequency="annual",
        custom_frequency=None,
        scope_state="All",
        scope_guidance=None,
        assurance_purpose="design",
        validity_rule="continuous",
        max_age_days=None,
        guidance=None,
        artifact_types=["report"],
        required_metadata=[],
    )

    ap = service.create_assessment_procedure_version(
        context=writer_context,
        request_key="req-ap-zero-step",
        control_version_id=cv.id,
        expected_control_digest=cv.content_digest,
        procedure_key="AP-ZERO-STEP",
        title="Zero Steps AP",
        objective="Verify zero steps rejection",
        sample_guidance=None,
        scope_guidance=None,
        decision_guidance="Pass if rejected",
        assessor_qualifications=None,
        steps=[{"step_kind": "inspect", "instruction": "Check zero steps"}],
        evidence_requirements=[{"id": er_for_ap.id, "content_digest": er_for_ap.content_digest}],
    )

    # Manually delete steps to simulate incomplete / corrupted state
    for step_row in (
        db_session.execute(
            select(CatalogAssessmentProcedureStep).where(
                CatalogAssessmentProcedureStep.assessment_procedure_version_id == ap.id
            )
        )
        .scalars()
        .all()
    ):
        db_session.delete(step_row)
    db_session.flush()

    with pytest.raises(
        CatalogSecurityError, match="corrupt aggregate: expected 1..50 steps, got 0"
    ):
        service.get_assessment_procedure_version(reader_context, ap.id)

    with pytest.raises(
        CatalogSecurityError, match="corrupt aggregate: expected 1..50 steps, got 0"
    ):
        service.list_assessment_procedure_versions(reader_context, cv.id)
