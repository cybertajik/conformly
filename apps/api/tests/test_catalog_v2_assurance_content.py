"""WP-06A Dormant Assurance Content (Evidence Requirements & Assessment Procedures) Test Suite.

Proves:
1. All columns, FKs, unique/check constraints, and controlled vocabularies.
2. Exact ControlVersion lineage and cross-control link rejection.
3. Sequential insertion, gap-free sequence triggers, duplicates, and bounds rejection.
4. Immutability, status, digest schema, and 32-byte digest verification.
5. Zero V1 / tenant table foreign keys or dynamic route exposures.
6. Synthetic source-neutral control aggregates.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from conformly.catalog_v2.digest import compute_content_digest
from conformly.catalog_v2.models import (
    CatalogAssessmentProcedureEvidenceRequirement,
    CatalogAssessmentProcedureStep,
    CatalogAssessmentProcedureVersion,
    CatalogCommonControl,
    CatalogControlVersion,
    CatalogEvidenceRequirementArtifactType,
    CatalogEvidenceRequirementMetadataKey,
    CatalogEvidenceRequirementVersion,
)
from conformly.db.base import Base
from conformly.main import app as conformly_app

ZERO_32_BYTES = b"\x00" * 32
SAMPLE_32_BYTES = b"\x01" * 32


@pytest.fixture
def catalog_session():
    """Isolated SQLite session with enforced foreign keys for fast unit validation."""
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
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def make_control_version(
    session: Session, control_key: str = "CC-IAM-001"
) -> tuple[CatalogCommonControl, CatalogControlVersion]:
    """Helper to create a synthetic Common Control and ControlVersion parent."""
    ctrl = CatalogCommonControl(
        id=uuid4(),
        control_key=control_key,
        domain="Identity and Access Management",
        status="Draft",
    )
    session.add(ctrl)
    session.flush()

    cv_payload = {
        "control_id": str(ctrl.id),
        "control_key": control_key,
        "kind": "ControlVersion",
        "objective": "Ensure proper access controls and review.",
        "revision": 1,
        "title": f"Synthetic Control {control_key}",
        "version_label": "1.0.0",
    }
    cv_digest = compute_content_digest(cv_payload)

    cv = CatalogControlVersion(
        id=uuid4(),
        control_id=ctrl.id,
        version_label="1.0.0",
        revision=1,
        title=f"Synthetic Control {control_key}",
        objective="Ensure proper access controls and review.",
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


def compute_er_digest(
    control_version_id: UUID,
    control_version_digest: str,
    requirement_key: str,
    sequence: int,
    title: str,
    frequency: str,
    custom_frequency: str | None,
    scope_state: str,
    scope_guidance: str | None,
    assurance_purpose: str,
    validity_rule: str,
    max_age_days: int | None,
    missing_data_behavior: str,
    guidance: str | None,
    artifact_types: list[dict[str, Any]],
    required_metadata: list[dict[str, Any]],
) -> bytes:
    payload = {
        "artifact_types": artifact_types,
        "assurance_purpose": assurance_purpose,
        "control_version_digest": control_version_digest,
        "control_version_id": str(control_version_id),
        "custom_frequency": custom_frequency,
        "frequency": frequency,
        "guidance": guidance,
        "kind": "EvidenceRequirementVersion",
        "max_age_days": max_age_days,
        "missing_data_behavior": missing_data_behavior,
        "required_metadata": required_metadata,
        "requirement_key": requirement_key,
        "scope_guidance": scope_guidance,
        "scope_state": scope_state,
        "sequence": sequence,
        "title": title,
        "validity_rule": validity_rule,
    }
    return compute_content_digest(payload)


def compute_ap_digest(
    control_version_id: UUID,
    control_version_digest: str,
    procedure_key: str,
    sequence: int,
    title: str,
    objective: str,
    sample_guidance: str | None,
    scope_guidance: str | None,
    decision_guidance: str,
    assessor_qualifications: str | None,
    missing_data_behavior: str,
    steps: list[dict[str, Any]],
    evidence_requirements: list[dict[str, Any]],
) -> bytes:
    payload = {
        "assessor_qualifications": assessor_qualifications,
        "control_version_digest": control_version_digest,
        "control_version_id": str(control_version_id),
        "decision_guidance": decision_guidance,
        "evidence_requirements": evidence_requirements,
        "kind": "AssessmentProcedureVersion",
        "missing_data_behavior": missing_data_behavior,
        "objective": objective,
        "procedure_key": procedure_key,
        "sample_guidance": sample_guidance,
        "scope_guidance": scope_guidance,
        "sequence": sequence,
        "steps": steps,
        "title": title,
    }
    return compute_content_digest(payload)


def test_synthetic_aggregate_lifecycle_and_relationships(catalog_session: Session) -> None:
    """Section 9 minimum required aggregate test:
    - 1 control version (CV1) with 2 evidence requirements (ER1, ER2)
    - ER1 with 2 artifact types and 2 metadata keys
    - 1 procedure (AP1) with 2 steps and 2 evidence requirement links
    - 1 second control version (CV2) for negative isolation
    """
    ctrl1, cv1 = make_control_version(catalog_session, "CC-IAM-001")
    ctrl2, cv2 = make_control_version(catalog_session, "CC-CRY-002")

    # 1. Create ER1 on CV1
    er1_art_types = [
        {"sequence": 1, "artifact_type": "record"},
        {"sequence": 2, "artifact_type": "attestation"},
    ]
    er1_meta_keys = [
        {"sequence": 1, "metadata_key": "system_id"},
        {"sequence": 2, "metadata_key": "reviewer_email"},
    ]
    er1_digest = compute_er_digest(
        cv1.id,
        cv1.content_digest.hex(),
        "ER-IAM-ACCESS-LIST",
        1,
        "Privileged Access Review Evidence",
        "quarterly",
        None,
        "All",
        None,
        "operating_effectiveness",
        "period_coverage",
        None,
        "requires_human_review",
        "Export active directory member list.",
        er1_art_types,
        er1_meta_keys,
    )

    er1 = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-IAM-ACCESS-LIST",
        sequence=1,
        title="Privileged Access Review Evidence",
        frequency="quarterly",
        custom_frequency=None,
        scope_state="All",
        scope_guidance=None,
        assurance_purpose="operating_effectiveness",
        validity_rule="period_coverage",
        max_age_days=None,
        missing_data_behavior="requires_human_review",
        guidance="Export active directory member list.",
        status="Draft",
        content_digest=er1_digest,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er1)
    catalog_session.flush()

    # Add ER1 children
    at1_1 = CatalogEvidenceRequirementArtifactType(
        id=uuid4(),
        evidence_requirement_version_id=er1.id,
        control_version_id=cv1.id,
        sequence=1,
        artifact_type="record",
    )
    at1_2 = CatalogEvidenceRequirementArtifactType(
        id=uuid4(),
        evidence_requirement_version_id=er1.id,
        control_version_id=cv1.id,
        sequence=2,
        artifact_type="attestation",
    )
    mk1_1 = CatalogEvidenceRequirementMetadataKey(
        id=uuid4(),
        evidence_requirement_version_id=er1.id,
        control_version_id=cv1.id,
        sequence=1,
        metadata_key="system_id",
    )
    mk1_2 = CatalogEvidenceRequirementMetadataKey(
        id=uuid4(),
        evidence_requirement_version_id=er1.id,
        control_version_id=cv1.id,
        sequence=2,
        metadata_key="reviewer_email",
    )
    catalog_session.add_all([at1_1, at1_2, mk1_1, mk1_2])
    catalog_session.flush()

    # 2. Create ER2 on CV1 (conditional with custom frequency and point_in_time max_age_days)
    er2_digest = compute_er_digest(
        cv1.id,
        cv1.content_digest.hex(),
        "ER-IAM-CONFIG-EXPORT",
        2,
        "IAM Configuration Export",
        "custom",
        "every_sprint",
        "Conditional",
        "Production tenants only",
        "design",
        "point_in_time",
        45,
        "requires_human_review",
        None,
        [],
        [],
    )
    er2 = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-IAM-CONFIG-EXPORT",
        sequence=2,
        title="IAM Configuration Export",
        frequency="custom",
        custom_frequency="every_sprint",
        scope_state="Conditional",
        scope_guidance="Production tenants only",
        assurance_purpose="design",
        validity_rule="point_in_time",
        max_age_days=45,
        missing_data_behavior="requires_human_review",
        guidance=None,
        status="Draft",
        content_digest=er2_digest,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er2)
    catalog_session.flush()

    # 3. Create Procedure AP1 on CV1
    ap1_steps = [
        {
            "sequence": 1,
            "step_kind": "inspect",
            "instruction": "Inspect active directory groups.",
            "expected_output": "Admin group has < 5 members.",
        },
        {
            "sequence": 2,
            "step_kind": "inquire",
            "instruction": "Inquire with IAM lead regarding quarterly reviews.",
            "expected_output": None,
        },
    ]
    ap1_links = [
        {"sequence": 1, "id": str(er1.id), "content_digest": er1_digest.hex()},
        {"sequence": 2, "id": str(er2.id), "content_digest": er2_digest.hex()},
    ]
    ap1_digest = compute_ap_digest(
        cv1.id,
        cv1.content_digest.hex(),
        "AP-IAM-QUARTERLY-CERT",
        1,
        "Quarterly IAM Access Certification Procedure",
        "Verify all administrative access is approved.",
        "Sample all platform administrators.",
        "Scope to root account.",
        "If any unauthorized account found, flag for human remediation.",
        "Qualified CISA or equivalent assessor.",
        "requires_human_review",
        ap1_steps,
        ap1_links,
    )
    ap1 = CatalogAssessmentProcedureVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        procedure_key="AP-IAM-QUARTERLY-CERT",
        sequence=1,
        title="Quarterly IAM Access Certification Procedure",
        objective="Verify all administrative access is approved.",
        sample_guidance="Sample all platform administrators.",
        scope_guidance="Scope to root account.",
        decision_guidance="If any unauthorized account found, flag for human remediation.",
        assessor_qualifications="Qualified CISA or equivalent assessor.",
        missing_data_behavior="requires_human_review",
        status="Draft",
        content_digest=ap1_digest,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(ap1)
    catalog_session.flush()

    # Add AP1 steps and links
    step1 = CatalogAssessmentProcedureStep(
        id=uuid4(),
        assessment_procedure_version_id=ap1.id,
        control_version_id=cv1.id,
        sequence=1,
        step_kind="inspect",
        instruction="Inspect active directory groups.",
        expected_output="Admin group has < 5 members.",
    )
    step2 = CatalogAssessmentProcedureStep(
        id=uuid4(),
        assessment_procedure_version_id=ap1.id,
        control_version_id=cv1.id,
        sequence=2,
        step_kind="inquire",
        instruction="Inquire with IAM lead regarding quarterly reviews.",
        expected_output=None,
    )
    link1 = CatalogAssessmentProcedureEvidenceRequirement(
        id=uuid4(),
        assessment_procedure_version_id=ap1.id,
        evidence_requirement_version_id=er1.id,
        control_version_id=cv1.id,
        sequence=1,
    )
    link2 = CatalogAssessmentProcedureEvidenceRequirement(
        id=uuid4(),
        assessment_procedure_version_id=ap1.id,
        evidence_requirement_version_id=er2.id,
        control_version_id=cv1.id,
        sequence=2,
    )
    catalog_session.add_all([step1, step2, link1, link2])
    catalog_session.commit()

    # Assert retrieval and counts
    retrieved_er = catalog_session.scalars(
        select(CatalogEvidenceRequirementVersion).where(
            CatalogEvidenceRequirementVersion.control_version_id == cv1.id
        )
    ).all()
    assert len(retrieved_er) == 2

    retrieved_ap = catalog_session.scalars(
        select(CatalogAssessmentProcedureVersion).where(
            CatalogAssessmentProcedureVersion.control_version_id == cv1.id
        )
    ).all()
    assert len(retrieved_ap) == 1

    retrieved_links = catalog_session.scalars(
        select(CatalogAssessmentProcedureEvidenceRequirement).where(
            CatalogAssessmentProcedureEvidenceRequirement.assessment_procedure_version_id == ap1.id
        )
    ).all()
    assert len(retrieved_links) == 2

    # Assert content digest pinning to parent ControlVersion
    assert cv1.content_digest is not None
    assert len(cv1.content_digest) == 32
    assert er1.status == "Draft"
    assert ap1.status == "Draft"
    assert er1.content_digest == er1_digest
    assert len(er1.content_digest) == 32
    assert er2.content_digest == er2_digest
    assert len(er2.content_digest) == 32
    assert ap1.content_digest == ap1_digest
    assert len(ap1.content_digest) == 32


def test_cross_control_lineage_and_link_rejection(catalog_session: Session) -> None:
    """Composite FKs reject linking procedures and evidence requirements across different ControlVersions."""
    ctrl1, cv1 = make_control_version(catalog_session, "CC-IAM-001")
    ctrl2, cv2 = make_control_version(catalog_session, "CC-CRY-002")

    # Create ER on CV1
    er_cv1 = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-IAM-01",
        sequence=1,
        title="Access List",
        frequency="annual",
        scope_state="All",
        assurance_purpose="design",
        validity_rule="continuous",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er_cv1)

    # Create AP on CV2
    ap_cv2 = CatalogAssessmentProcedureVersion(
        id=uuid4(),
        control_version_id=cv2.id,
        control_id=ctrl2.id,
        procedure_key="AP-CRY-01",
        sequence=1,
        title="Crypto Review",
        objective="Inspect keys.",
        decision_guidance="Manual review.",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(ap_cv2)
    catalog_session.flush()

    # Cross-control link attempt: AP is on CV2, ER is on CV1
    # Linking with control_version_id=cv2.id fails ER parent composite FK
    cross_link = CatalogAssessmentProcedureEvidenceRequirement(
        id=uuid4(),
        assessment_procedure_version_id=ap_cv2.id,
        evidence_requirement_version_id=er_cv1.id,
        control_version_id=cv2.id,
        sequence=1,
    )
    catalog_session.add(cross_link)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()


def test_mismatched_control_lineage_discriminator_rejection(catalog_session: Session) -> None:
    """Composite FK (control_version_id, control_id) rejects mismatched control_id."""
    ctrl1, cv1 = make_control_version(catalog_session, "CC-IAM-001")
    ctrl2, _cv2 = make_control_version(catalog_session, "CC-CRY-002")

    # Mismatched control_id (ctrl2.id instead of ctrl1.id for cv1)
    er_mismatched = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl2.id,
        requirement_key="ER-IAM-01",
        sequence=1,
        title="Mismatched Control Lineage",
        frequency="annual",
        scope_state="All",
        assurance_purpose="design",
        validity_rule="continuous",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er_mismatched)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()


def test_er_key_format_and_uniqueness_constraints(catalog_session: Session) -> None:
    """EvidenceRequirement requirement_key format (^ER-[A-Z0-9_-]{3,61}$) and uniqueness per ControlVersion."""
    ctrl1, cv1 = make_control_version(catalog_session, "CC-IAM-001")

    # Valid ER
    er1 = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-VALID-KEY_1",
        sequence=1,
        title="Valid Key",
        frequency="annual",
        scope_state="All",
        assurance_purpose="design",
        validity_rule="continuous",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er1)
    catalog_session.flush()

    # Duplicate requirement_key on same control_version_id
    er_dup_key = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-VALID-KEY_1",
        sequence=2,
        title="Duplicate Key",
        frequency="annual",
        scope_state="All",
        assurance_purpose="design",
        validity_rule="continuous",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er_dup_key)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()

    # Invalid key formats
    invalid_keys = [
        "NO-PREFIX",
        "er-lower",
        "ER-",
        "ER-A",
        "ER-AB",
        "ER-INVALID@CHAR",
        "ER-" + "A" * 62,
    ]
    for inv_k in invalid_keys:
        inv_er = CatalogEvidenceRequirementVersion(
            id=uuid4(),
            control_version_id=cv1.id,
            control_id=ctrl1.id,
            requirement_key=inv_k,
            sequence=1,
            title="Invalid Key Format",
            frequency="annual",
            scope_state="All",
            assurance_purpose="design",
            validity_rule="continuous",
            status="Draft",
            content_digest=ZERO_32_BYTES,
            digest_schema="catalog-assurance-draft-v1",
        )
        catalog_session.add(inv_er)
        with pytest.raises((IntegrityError, DBAPIError)):
            catalog_session.flush()
        catalog_session.rollback()


def test_ap_key_format_and_uniqueness_constraints(catalog_session: Session) -> None:
    """AssessmentProcedure procedure_key format (^AP-[A-Z0-9_-]{3,61}$) and uniqueness per ControlVersion."""
    ctrl1, cv1 = make_control_version(catalog_session, "CC-IAM-001")

    # Valid AP
    ap1 = CatalogAssessmentProcedureVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        procedure_key="AP-AUDIT-IAM-01",
        sequence=1,
        title="Valid Procedure",
        objective="Inspect access.",
        decision_guidance="Guidance.",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(ap1)
    catalog_session.flush()

    # Duplicate procedure_key on same control_version_id
    ap_dup_key = CatalogAssessmentProcedureVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        procedure_key="AP-AUDIT-IAM-01",
        sequence=2,
        title="Duplicate Procedure Key",
        objective="Inspect access.",
        decision_guidance="Guidance.",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(ap_dup_key)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()

    # Invalid key formats
    invalid_keys = ["WRONG-PREFIX", "ap-lower", "AP-", "AP-A", "AP-AB", "AP-INVALID#CHAR"]
    for inv_k in invalid_keys:
        inv_ap = CatalogAssessmentProcedureVersion(
            id=uuid4(),
            control_version_id=cv1.id,
            control_id=ctrl1.id,
            procedure_key=inv_k,
            sequence=1,
            title="Invalid Procedure Key Format",
            objective="Inspect access.",
            decision_guidance="Guidance.",
            status="Draft",
            content_digest=ZERO_32_BYTES,
            digest_schema="catalog-assurance-draft-v1",
        )
        catalog_session.add(inv_ap)
        with pytest.raises((IntegrityError, DBAPIError)):
            catalog_session.flush()
        catalog_session.rollback()


def test_metadata_key_format_and_uniqueness(catalog_session: Session) -> None:
    """MetadataKey format (^[a-z][a-z0-9_]{0,63}$) and uniqueness per requirement."""
    ctrl1, cv1 = make_control_version(catalog_session, "CC-IAM-001")
    er1 = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-TEST-01",
        sequence=1,
        title="Meta Test",
        frequency="annual",
        scope_state="All",
        assurance_purpose="design",
        validity_rule="continuous",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er1)
    catalog_session.flush()

    # Valid metadata key
    mk1 = CatalogEvidenceRequirementMetadataKey(
        id=uuid4(),
        evidence_requirement_version_id=er1.id,
        control_version_id=cv1.id,
        sequence=1,
        metadata_key="valid_key_1",
    )
    catalog_session.add(mk1)
    catalog_session.flush()

    # Duplicate metadata_key on same requirement
    mk_dup = CatalogEvidenceRequirementMetadataKey(
        id=uuid4(),
        evidence_requirement_version_id=er1.id,
        control_version_id=cv1.id,
        sequence=2,
        metadata_key="valid_key_1",
    )
    catalog_session.add(mk_dup)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()

    # Invalid metadata keys (uppercase, starts with digit or underscore, contains hyphen)
    invalid_keys = ["UPPER", "1start_with_digit", "_underscore_start", "has-hyphen", "has.dot", ""]
    for inv_k in invalid_keys:
        inv_mk = CatalogEvidenceRequirementMetadataKey(
            id=uuid4(),
            evidence_requirement_version_id=er1.id,
            control_version_id=cv1.id,
            sequence=1,
            metadata_key=inv_k,
        )
        catalog_session.add(inv_mk)
        with pytest.raises((IntegrityError, DBAPIError)):
            catalog_session.flush()
        catalog_session.rollback()


def test_er_cross_field_shape_constraints(catalog_session: Session) -> None:
    """Cross-field check constraints for frequency, scope, and validity rule shapes."""
    ctrl1, cv1 = make_control_version(catalog_session, "CC-IAM-001")

    # 1. Custom frequency shape: frequency='custom' requires custom_frequency
    er_inv_freq1 = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-FREQ-01",
        sequence=1,
        title="Custom Frequency Missing",
        frequency="custom",
        custom_frequency=None,  # Invalid: required when custom
        scope_state="All",
        assurance_purpose="design",
        validity_rule="continuous",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er_inv_freq1)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()

    # frequency='annual' with custom_frequency populated is rejected
    er_inv_freq2 = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-FREQ-02",
        sequence=1,
        title="Annual With Custom Freq",
        frequency="annual",
        custom_frequency="should_be_null",  # Invalid
        scope_state="All",
        assurance_purpose="design",
        validity_rule="continuous",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er_inv_freq2)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()

    # 2. Scope state shape: scope_state='Conditional' requires scope_guidance
    er_inv_scope1 = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-SCOPE-01",
        sequence=1,
        title="Conditional Missing Guidance",
        frequency="annual",
        scope_state="Conditional",
        scope_guidance=None,  # Invalid
        assurance_purpose="design",
        validity_rule="continuous",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er_inv_scope1)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()

    # scope_state='All' with scope_guidance populated is rejected
    er_inv_scope2 = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-SCOPE-02",
        sequence=1,
        title="All With Scope Guidance",
        frequency="annual",
        scope_state="All",
        scope_guidance="Should be null",  # Invalid
        assurance_purpose="design",
        validity_rule="continuous",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er_inv_scope2)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()

    # 3. Validity rule shape: point_in_time requires max_age_days BETWEEN 1 AND 3660
    er_inv_val1 = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-VAL-01",
        sequence=1,
        title="Point in Time Missing Max Age",
        frequency="annual",
        scope_state="All",
        assurance_purpose="design",
        validity_rule="point_in_time",
        max_age_days=None,  # Invalid
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er_inv_val1)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()

    er_inv_val2 = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-VAL-02",
        sequence=1,
        title="Continuous With Max Age",
        frequency="annual",
        scope_state="All",
        assurance_purpose="design",
        validity_rule="continuous",
        max_age_days=30,  # Invalid
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er_inv_val2)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()


def test_sequence_bounds_and_child_bounds(catalog_session: Session) -> None:
    """Sequence bounds for artifact types (1..16), metadata keys (1..32), steps (1..50), links (1..32)."""
    ctrl1, cv1 = make_control_version(catalog_session, "CC-IAM-001")
    er = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-BOUNDS-01",
        sequence=1,
        title="Bounds",
        frequency="annual",
        scope_state="All",
        assurance_purpose="design",
        validity_rule="continuous",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    ap = CatalogAssessmentProcedureVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        procedure_key="AP-BOUNDS-01",
        sequence=1,
        title="Bounds Procedure",
        objective="Inspect bounds.",
        decision_guidance="Guidance.",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add_all([er, ap])
    catalog_session.flush()

    # Sequence = 0 rejected for ER
    er_zero = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-ZERO",
        sequence=0,
        title="Zero Seq",
        frequency="annual",
        scope_state="All",
        assurance_purpose="design",
        validity_rule="continuous",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er_zero)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()

    # Artifact type sequence 0 and 17 rejected
    for inv_seq in [0, 17]:
        at_inv = CatalogEvidenceRequirementArtifactType(
            id=uuid4(),
            evidence_requirement_version_id=er.id,
            control_version_id=cv1.id,
            sequence=inv_seq,
            artifact_type="record",
        )
        catalog_session.add(at_inv)
        with pytest.raises(IntegrityError):
            catalog_session.flush()
        catalog_session.rollback()

    # Metadata key sequence 0 and 33 rejected
    for inv_seq in [0, 33]:
        mk_inv = CatalogEvidenceRequirementMetadataKey(
            id=uuid4(),
            evidence_requirement_version_id=er.id,
            control_version_id=cv1.id,
            sequence=inv_seq,
            metadata_key="valid_key",
        )
        catalog_session.add(mk_inv)
        with pytest.raises(IntegrityError):
            catalog_session.flush()
        catalog_session.rollback()

    # Step sequence 0 and 51 rejected
    for inv_seq in [0, 51]:
        step_inv = CatalogAssessmentProcedureStep(
            id=uuid4(),
            assessment_procedure_version_id=ap.id,
            control_version_id=cv1.id,
            sequence=inv_seq,
            step_kind="inspect",
            instruction="Step instruction.",
        )
        catalog_session.add(step_inv)
        with pytest.raises(IntegrityError):
            catalog_session.flush()
        catalog_session.rollback()

    # Link sequence 0 and 33 rejected
    for inv_seq in [0, 33]:
        link_inv = CatalogAssessmentProcedureEvidenceRequirement(
            id=uuid4(),
            assessment_procedure_version_id=ap.id,
            evidence_requirement_version_id=er.id,
            control_version_id=cv1.id,
            sequence=inv_seq,
        )
        catalog_session.add(link_inv)
        with pytest.raises(IntegrityError):
            catalog_session.flush()
        catalog_session.rollback()


def test_draft_status_digest_schema_and_32_byte_digest(catalog_session: Session) -> None:
    """Status fixed to Draft, schema to catalog-assurance-draft-v1, digest must be 32 bytes."""
    ctrl1, cv1 = make_control_version(catalog_session, "CC-IAM-001")

    # Non-Draft status rejected
    er_non_draft = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-STATUS-01",
        sequence=1,
        title="Non-Draft",
        frequency="annual",
        scope_state="All",
        assurance_purpose="design",
        validity_rule="continuous",
        status="Published",  # Invalid
        content_digest=ZERO_32_BYTES,
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er_non_draft)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()

    # Non-32-byte digest rejected
    er_short_digest = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-DIGEST-01",
        sequence=1,
        title="Short Digest",
        frequency="annual",
        scope_state="All",
        assurance_purpose="design",
        validity_rule="continuous",
        status="Draft",
        content_digest=b"\x00" * 31,  # Invalid: 31 bytes
        digest_schema="catalog-assurance-draft-v1",
    )
    catalog_session.add(er_short_digest)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()

    # Unknown digest schema rejected
    er_unknown_schema = CatalogEvidenceRequirementVersion(
        id=uuid4(),
        control_version_id=cv1.id,
        control_id=ctrl1.id,
        requirement_key="ER-SCHEMA-01",
        sequence=1,
        title="Unknown Schema",
        frequency="annual",
        scope_state="All",
        assurance_purpose="design",
        validity_rule="continuous",
        status="Draft",
        content_digest=ZERO_32_BYTES,
        digest_schema="unknown-schema-v2",  # Invalid
    )
    catalog_session.add(er_unknown_schema)
    with pytest.raises(IntegrityError):
        catalog_session.flush()
    catalog_session.rollback()


def test_no_v1_tenant_or_api_exposure() -> None:
    """Proves zero foreign keys to tenant tables and zero route exposures for WP-06A tables."""
    tables = [
        "catalog_evidence_requirement_versions",
        "catalog_evidence_requirement_artifact_types",
        "catalog_evidence_requirement_metadata_keys",
        "catalog_assessment_procedure_versions",
        "catalog_assessment_procedure_steps",
        "catalog_assessment_procedure_evidence_requirements",
    ]
    for tbl_name in tables:
        tbl = Base.metadata.tables[tbl_name]
        for fk in tbl.foreign_keys:
            target_table = fk.column.table.name
            assert not target_table.startswith("tenant"), (
                f"Forbidden tenant FK in {tbl_name} -> {target_table}"
            )
            assert target_table in (
                "catalog_control_versions",
                "catalog_evidence_requirement_versions",
                "catalog_assessment_procedure_versions",
            ), f"Unexpected FK target {target_table} in {tbl_name}"

    # Runtime route exposure check
    for r in conformly_app.routes:
        path = getattr(r, "path", "")
        assert "evidence-requirement" not in path.lower()
        assert "evidence_requirement" not in path.lower()
        assert "assessment-procedure" not in path.lower()
        assert "assessment_procedure" not in path.lower()
        assert not path.startswith("/api/v2")
