"""Synthetic staff catalog demo dataset and guarded fixture loader."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from conformly.catalog_v2.digest import (
    compute_assessment_procedure_version_digest,
    compute_control_version_digest,
    compute_evidence_requirement_version_digest,
    compute_mapping_version_digest,
    compute_requirement_version_digest,
    compute_source_version_digest,
)
from conformly.catalog_v2.models import (
    CatalogAssessmentProcedureEvidenceRequirement,
    CatalogAssessmentProcedureStep,
    CatalogAssessmentProcedureVersion,
    CatalogCommonControl,
    CatalogControlVersion,
    CatalogEvidenceRequirementArtifactType,
    CatalogEvidenceRequirementMetadataKey,
    CatalogEvidenceRequirementVersion,
    CatalogMappingVersion,
    CatalogPublisher,
    CatalogRequirement,
    CatalogRequirementControlMapping,
    CatalogRequirementSourceReference,
    CatalogRequirementVersion,
    CatalogSource,
    CatalogSourcePermissionDecision,
    CatalogSourcePermissionGuard,
    CatalogSourcePermissionProposal,
    CatalogSourceProvenance,
    CatalogSourceVersion,
)

# Deterministic UUID5 namespace per contract
DEMO_NAMESPACE = uuid.UUID("5b4fac43-152a-4b84-9a68-43066d856921")

# Actors for provenance and dual-actor permission decisions
ACTOR_A_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:actor:a")
ACTOR_B_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:actor:b")

# Publisher & Source
PUBLISHER_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:publisher")
PUBLISHER_KEY = "DEMO08-PUBLISHER"
PUBLISHER_NAME = "Demo Authoritative Publisher 08"

SOURCE_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:source")
SOURCE_KEY = "DEMO08-SOURCE"
SOURCE_TITLE = "Synthetic Conformly catalog demo"

SOURCE_VERSION_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:source-version")
SOURCE_EDITION = "1.0.0"
SOURCE_LANGUAGE = "en"
SOURCE_LOCATOR = "https://demo.synthetic.conformly.invalid/sources/demo08-source-v1.pdf"
SOURCE_PUB_DATE = date(2026, 1, 1)
SOURCE_RETRIEVED_AT = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

PROVENANCE_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:provenance")
PROPOSAL_REF_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:proposal:reference")
PROPOSAL_MAP_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:proposal:map")
DECISION_REF_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:decision:reference")
DECISION_MAP_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:decision:map")

# Requirements
REQ_1_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:requirement:1")
REQ_1_KEY = "DEMO08-REQ-01"
REQ_1_VER_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:requirement-version:1")
REQ_1_OUTCOME = "Review privileged access at a defined interval."

REQ_2_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:requirement:2")
REQ_2_KEY = "DEMO08-REQ-02"
REQ_2_VER_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:requirement-version:2")
REQ_2_OUTCOME = "Maintain backups and test restoration."

# Common Controls (Corrected per D-V2-019 to 4-letter domain "DEMO")
CONTROL_1_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:control:1")
CONTROL_1_KEY = "CC-DEMO-001"
CONTROL_1_DOMAIN = "DEMO"
CONTROL_1_VER_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:control-version:1")
CONTROL_1_TITLE = "Privileged Access Review"
CONTROL_1_OBJECTIVE = "Ensure that privileged user accounts and access grants are periodically reviewed and validated."
CONTROL_1_GUIDANCE = "Conduct periodic audits of administrator and elevated roles to identify and revoke unneeded privileges."

CONTROL_2_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:control:2")
CONTROL_2_KEY = "CC-DEMO-002"
CONTROL_2_DOMAIN = "DEMO"
CONTROL_2_VER_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:control-version:2")
CONTROL_2_TITLE = "Backup Restore Exercise"
CONTROL_2_OBJECTIVE = (
    "Ensure data restoration procedures are periodically tested against validated backups."
)
CONTROL_2_GUIDANCE = "Simulate data loss recovery and verify data integrity following restoration from backup storage."

# Mappings
MAPPING_1_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:mapping:1")
MAPPING_1_KEY = "MAP-DEMO08-REQ01-CCDEMO001"
MAPPING_1_VER_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:mapping-version:1")
MAPPING_1_RATIONALE = "Full mapping of the stated synthetic outcome only. Does not equate Full mapping with implementation/effectiveness."
MAPPING_1_COVERED = "periodic review of privileged access"

MAPPING_2_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:mapping:2")
MAPPING_2_KEY = "MAP-DEMO08-REQ02-CCDEMO002"
MAPPING_2_VER_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:mapping-version:2")
MAPPING_2_RATIONALE = "Partial mapping covers restoration testing and explicitly leaves backup protection/retention work outside its coverage."
MAPPING_2_COVERED = "restoration testing"
MAPPING_2_EXCLUDED = "backup protection and retention schedules"

# Evidence Requirements
EVID_1_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:evidence:1")
EVID_1_VER_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:evidence-version:1")
EVID_1_KEY = "ER-DEMO-001"
EVID_1_TITLE = "Quarterly Privileged Access Review Log"

EVID_2_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:evidence:2")
EVID_2_VER_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:evidence-version:2")
EVID_2_KEY = "ER-DEMO-002"
EVID_2_TITLE = "Backup Restoration Test Record"

# Assessment Procedures
PROC_1_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:procedure:1")
PROC_1_VER_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:procedure-version:1")
PROC_1_KEY = "AP-DEMO-001"
PROC_1_TITLE = "Inspect Privileged Access Review"
PROC_1_OBJECTIVE = (
    "Verify that privileged access reviews took place within the required quarterly cadence."
)

PROC_2_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:procedure:2")
PROC_2_VER_ID = uuid.uuid5(DEMO_NAMESPACE, "catalog-demo-v1:procedure-version:2")
PROC_2_KEY = "AP-DEMO-002"
PROC_2_TITLE = "Inspect Restoration Exercise"
PROC_2_OBJECTIVE = "Verify that restoration test records demonstrate successful data recovery."

# Compute immutable canonical content digests
SOURCE_VERSION_DIGEST = compute_source_version_digest(
    source_id=SOURCE_ID,
    edition=SOURCE_EDITION,
    predecessor_id=None,
    language=SOURCE_LANGUAGE,
    official_locator=SOURCE_LOCATOR,
    publication_date=SOURCE_PUB_DATE,
    retrieved_at=SOURCE_RETRIEVED_AT,
    status="Draft",
)

REQ_1_DIGEST = compute_requirement_version_digest(
    requirement_id=REQ_1_ID,
    source_id=SOURCE_ID,
    source_version_id=SOURCE_VERSION_ID,
    version_label="1.0.0",
    predecessor_id=None,
    revision=1,
    normalized_outcome=REQ_1_OUTCOME,
    requirement_type="mandatory",
    obligated_actor="organization",
    text_origin="conformly_paraphrase",
    customer_display_text=None,
    effective_from=date(2026, 1, 1),
    effective_until=None,
    source_references=[
        {
            "locator_kind": "section",
            "locator_value": "1.1",
            "sequence": 1,
            "source_version_id": SOURCE_VERSION_ID,
        }
    ],
    status="Draft",
)

REQ_2_DIGEST = compute_requirement_version_digest(
    requirement_id=REQ_2_ID,
    source_id=SOURCE_ID,
    source_version_id=SOURCE_VERSION_ID,
    version_label="1.0.0",
    predecessor_id=None,
    revision=1,
    normalized_outcome=REQ_2_OUTCOME,
    requirement_type="recommendation",
    obligated_actor="organization",
    text_origin="conformly_paraphrase",
    customer_display_text=None,
    effective_from=date(2026, 1, 1),
    effective_until=None,
    source_references=[
        {
            "locator_kind": "section",
            "locator_value": "1.2",
            "sequence": 1,
            "source_version_id": SOURCE_VERSION_ID,
        }
    ],
    status="Draft",
)

CTRL_1_DIGEST = compute_control_version_digest(
    control_id=CONTROL_1_ID,
    version_label="1.0.0",
    predecessor_id=None,
    revision=1,
    title=CONTROL_1_TITLE,
    objective=CONTROL_1_OBJECTIVE,
    guidance=CONTROL_1_GUIDANCE,
    control_type="preventive",
    frequency="quarterly",
    automation_level="manual",
    suggested_owner_role="Security Operations",
    assurance_level="foundational",
    tags_state="None",
    tags=None,
    status="Draft",
)

CTRL_2_DIGEST = compute_control_version_digest(
    control_id=CONTROL_2_ID,
    version_label="1.0.0",
    predecessor_id=None,
    revision=1,
    title=CONTROL_2_TITLE,
    objective=CONTROL_2_OBJECTIVE,
    guidance=CONTROL_2_GUIDANCE,
    control_type="corrective",
    frequency="semiannual",
    automation_level="manual",
    suggested_owner_role="Infrastructure Engineering",
    assurance_level="foundational",
    tags_state="None",
    tags=None,
    status="Draft",
)

MAP_1_DIGEST = compute_mapping_version_digest(
    mapping_id=MAPPING_1_ID,
    requirement_id=REQ_1_ID,
    control_id=CONTROL_1_ID,
    requirement_version_id=REQ_1_VER_ID,
    control_version_id=CONTROL_1_VER_ID,
    requirement_version_revision=1,
    requirement_version_digest=REQ_1_DIGEST,
    control_version_revision=1,
    control_version_digest=CTRL_1_DIGEST,
    version_label="1.0.0",
    predecessor_id=None,
    revision=1,
    mapping_type="Full",
    rationale=MAPPING_1_RATIONALE,
    covered_dimensions=MAPPING_1_COVERED,
    excluded_dimensions=None,
    conditions=None,
    source_basis="expert_analysis",
    confidence="high",
    review_state="Draft",
    status="Draft",
)

MAP_2_DIGEST = compute_mapping_version_digest(
    mapping_id=MAPPING_2_ID,
    requirement_id=REQ_2_ID,
    control_id=CONTROL_2_ID,
    requirement_version_id=REQ_2_VER_ID,
    control_version_id=CONTROL_2_VER_ID,
    requirement_version_revision=1,
    requirement_version_digest=REQ_2_DIGEST,
    control_version_revision=1,
    control_version_digest=CTRL_2_DIGEST,
    version_label="1.0.0",
    predecessor_id=None,
    revision=1,
    mapping_type="Partial",
    rationale=MAPPING_2_RATIONALE,
    covered_dimensions=MAPPING_2_COVERED,
    excluded_dimensions=MAPPING_2_EXCLUDED,
    conditions=None,
    source_basis="expert_analysis",
    confidence="medium",
    review_state="Draft",
    status="Draft",
)

EVID_1_DIGEST = compute_evidence_requirement_version_digest(
    control_version_id=CONTROL_1_VER_ID,
    control_version_digest=CTRL_1_DIGEST,
    requirement_key=EVID_1_KEY,
    sequence=1,
    title=EVID_1_TITLE,
    frequency="quarterly",
    custom_frequency=None,
    scope_state="All",
    scope_guidance=None,
    assurance_purpose="operating_effectiveness",
    validity_rule="point_in_time",
    max_age_days=90,
    guidance="Signed export or ticket showing review of elevated permissions.",
    artifact_types=[{"artifact_type": "report", "sequence": 1}],
    required_metadata=[{"metadata_key": "reviewer_name", "sequence": 1}],
    missing_data_behavior="requires_human_review",
)

EVID_2_DIGEST = compute_evidence_requirement_version_digest(
    control_version_id=CONTROL_2_VER_ID,
    control_version_digest=CTRL_2_DIGEST,
    requirement_key=EVID_2_KEY,
    sequence=1,
    title=EVID_2_TITLE,
    frequency="semiannual",
    custom_frequency=None,
    scope_state="All",
    scope_guidance=None,
    assurance_purpose="operating_effectiveness",
    validity_rule="point_in_time",
    max_age_days=180,
    guidance="Log or ticket documenting test recovery from backup.",
    artifact_types=[{"artifact_type": "log", "sequence": 1}],
    required_metadata=[{"metadata_key": "backup_timestamp", "sequence": 1}],
    missing_data_behavior="requires_human_review",
)

PROC_1_DIGEST = compute_assessment_procedure_version_digest(
    control_version_id=CONTROL_1_VER_ID,
    control_version_digest=CTRL_1_DIGEST,
    procedure_key=PROC_1_KEY,
    sequence=1,
    title=PROC_1_TITLE,
    objective=PROC_1_OBJECTIVE,
    sample_guidance=None,
    scope_guidance=None,
    decision_guidance="Confirm all privileged accounts have recorded approvals.",
    assessor_qualifications="Security Auditor",
    steps=[
        {
            "sequence": 1,
            "instruction": "Inspect quarterly review records for unapproved privilege grants.",
            "step_kind": "inspect",
            "expected_output": "All grants are approved and documented.",
        }
    ],
    evidence_requirements=[{"id": EVID_1_VER_ID, "sequence": 1, "content_digest": EVID_1_DIGEST}],
    missing_data_behavior="requires_human_review",
)

PROC_2_DIGEST = compute_assessment_procedure_version_digest(
    control_version_id=CONTROL_2_VER_ID,
    control_version_digest=CTRL_2_DIGEST,
    procedure_key=PROC_2_KEY,
    sequence=1,
    title=PROC_2_TITLE,
    objective=PROC_2_OBJECTIVE,
    sample_guidance=None,
    scope_guidance=None,
    decision_guidance="Confirm recovery verification completed successfully within RTO.",
    assessor_qualifications="Systems Auditor",
    steps=[
        {
            "sequence": 1,
            "instruction": "Inspect restore logs to verify checksum match and RTO.",
            "step_kind": "inspect",
            "expected_output": "Restoration verified complete and matching source data.",
        }
    ],
    evidence_requirements=[{"id": EVID_2_VER_ID, "sequence": 1, "content_digest": EVID_2_DIGEST}],
    missing_data_behavior="requires_human_review",
)


def is_database_disposable(
    session: Session,
    expected_database: str | None = None,
    expected_data_directory: str | None = None,
) -> bool:
    """Strictly verify that target database is an admitted disposable runner/test connection."""
    try:
        bind = session.get_bind()
        if bind is None:
            return False
        if bind.dialect.name == "sqlite":
            url = getattr(bind, "url", None)
            if url is None and hasattr(bind, "engine"):
                url = getattr(bind.engine, "url", None)
            db_name = (url.database if url else "") or ""
            return db_name in (":memory:", "", None)

        if bind.dialect.name == "postgresql":
            if not expected_database or not expected_data_directory:
                return False
            url = getattr(bind, "url", None)
            if url is None and hasattr(bind, "engine"):
                url = getattr(bind.engine, "url", None)
            host = getattr(url, "host", None) if url else None
            if host not in ("127.0.0.1", "localhost", "::1"):
                return False
            curr_db = session.execute(text("SELECT current_database()")).scalar()
            if not curr_db or not curr_db.startswith("conformly_disposable_"):
                return False
            if curr_db in ("conformly_disposable_", "postgres", "template0", "template1"):
                return False
            if curr_db != expected_database:
                return False

            data_dir = session.execute(text("SHOW data_directory")).scalar()
            if not data_dir:
                return False
            actual_str = str(data_dir).strip().replace("\\", "/").rstrip("/").lower()
            expected_str = (
                str(expected_data_directory).strip().replace("\\", "/").rstrip("/").lower()
            )
            if actual_str != expected_str:
                try:
                    import pathlib

                    if (
                        pathlib.Path(str(data_dir)).resolve()
                        != pathlib.Path(str(expected_data_directory)).resolve()
                    ):
                        return False
                except Exception:
                    return False
            return True

        return False
    except Exception:
        return False


def setup_catalog_demo_fixture(
    session: Session,
    expected_database: str | None = None,
    expected_data_directory: str | None = None,
) -> None:
    """Guarded idempotent fixture setup helper. Refuses non-disposable databases and validates complete reuse."""
    if not is_database_disposable(
        session,
        expected_database=expected_database,
        expected_data_directory=expected_data_directory,
    ):
        raise RuntimeError("setup_catalog_demo_fixture refused: target database is not disposable")

    # Check if fixture exists and validate complete fixed graph
    existing_source = session.scalar(select(CatalogSource).where(CatalogSource.id == SOURCE_ID))
    if existing_source is not None:
        # Full validation of every fixture entity before accepting as idempotent reuse
        pub = session.scalar(select(CatalogPublisher).where(CatalogPublisher.id == PUBLISHER_ID))
        if (
            not pub
            or pub.publisher_key != PUBLISHER_KEY
            or pub.name != PUBLISHER_NAME
            or pub.status != "Draft"
        ):
            raise ValueError("Catalog demo fixture conflict: publisher mismatch")

        if (
            existing_source.publisher_id != PUBLISHER_ID
            or existing_source.source_key != SOURCE_KEY
            or existing_source.title != SOURCE_TITLE
            or existing_source.status != "Draft"
        ):
            raise ValueError("Catalog demo fixture conflict: source mismatch")

        guard = session.scalar(
            select(CatalogSourcePermissionGuard).where(
                CatalogSourcePermissionGuard.source_id == SOURCE_ID
            )
        )
        if not guard or guard.source_id != SOURCE_ID or guard.revision != 2:
            raise ValueError("Catalog demo fixture conflict: permission guard mismatch")

        sv = session.scalar(
            select(CatalogSourceVersion).where(CatalogSourceVersion.id == SOURCE_VERSION_ID)
        )
        if (
            not sv
            or sv.source_id != SOURCE_ID
            or sv.edition != SOURCE_EDITION
            or sv.language != SOURCE_LANGUAGE
            or sv.official_locator != SOURCE_LOCATOR
            or sv.publication_date != SOURCE_PUB_DATE
            or sv.revision != 1
            or sv.status != "Draft"
            or sv.content_digest != SOURCE_VERSION_DIGEST
            or sv.digest_schema != "catalog-draft-v1"
        ):
            raise ValueError("Catalog demo fixture conflict: source version mismatch")

        calc_sv_digest = compute_source_version_digest(
            source_id=sv.source_id,
            edition=sv.edition,
            predecessor_id=sv.predecessor_id,
            language=sv.language,
            official_locator=sv.official_locator,
            publication_date=sv.publication_date,
            retrieved_at=sv.retrieved_at,
            status=sv.status,
        )
        if calc_sv_digest != sv.content_digest or calc_sv_digest != SOURCE_VERSION_DIGEST:
            raise ValueError("Catalog demo fixture conflict: source version digest mismatch")

        prov_rows = session.scalars(
            select(CatalogSourceProvenance).where(
                CatalogSourceProvenance.source_version_id == SOURCE_VERSION_ID
            )
        ).all()
        if len(prov_rows) != 1:
            raise ValueError("Catalog demo fixture conflict: provenance cardinality mismatch")
        prov = prov_rows[0]
        if (
            prov.id != PROVENANCE_ID
            or prov.source_revision != 1
            or prov.mime_type != "application/pdf"
            or prov.locator != SOURCE_LOCATOR
            or prov.content_size != 1024
            or prov.recorded_by_actor_id != ACTOR_A_ID
        ):
            raise ValueError("Catalog demo fixture conflict: provenance mismatch")

        proposals = session.scalars(
            select(CatalogSourcePermissionProposal).where(
                CatalogSourcePermissionProposal.source_version_id == SOURCE_VERSION_ID
            )
        ).all()
        if len(proposals) != 2:
            raise ValueError("Catalog demo fixture conflict: proposal cardinality mismatch")
        prop_map = {p.id: p for p in proposals}
        p_ref = prop_map.get(PROPOSAL_REF_ID)
        p_map = prop_map.get(PROPOSAL_MAP_ID)
        if (
            not p_ref
            or p_ref.use_case != "reference"
            or p_ref.recorded_by_actor_id != ACTOR_A_ID
            or p_ref.proposed_outcome != "Allowed"
        ):
            raise ValueError("Catalog demo fixture conflict: reference proposal mismatch")
        if (
            not p_map
            or p_map.use_case != "map"
            or p_map.recorded_by_actor_id != ACTOR_A_ID
            or p_map.proposed_outcome != "Allowed"
        ):
            raise ValueError("Catalog demo fixture conflict: map proposal mismatch")

        decisions = session.scalars(
            select(CatalogSourcePermissionDecision).where(
                CatalogSourcePermissionDecision.source_version_id == SOURCE_VERSION_ID
            )
        ).all()
        if len(decisions) != 2:
            raise ValueError("Catalog demo fixture conflict: decision cardinality mismatch")
        dec_map = {d.id: d for d in decisions}
        d_ref = dec_map.get(DECISION_REF_ID)
        d_map = dec_map.get(DECISION_MAP_ID)
        if (
            not d_ref
            or d_ref.proposal_id != PROPOSAL_REF_ID
            or d_ref.use_case != "reference"
            or d_ref.decision != "Allowed"
            or d_ref.decided_by_actor_id != ACTOR_B_ID
            or d_ref.guard_revision != 1
        ):
            raise ValueError("Catalog demo fixture conflict: reference decision mismatch")
        if (
            not d_map
            or d_map.proposal_id != PROPOSAL_MAP_ID
            or d_map.use_case != "map"
            or d_map.decision != "Allowed"
            or d_map.decided_by_actor_id != ACTOR_B_ID
            or d_map.guard_revision != 2
        ):
            raise ValueError("Catalog demo fixture conflict: map decision mismatch")

        # Requirements
        r1 = session.scalar(select(CatalogRequirement).where(CatalogRequirement.id == REQ_1_ID))
        rv1 = session.scalar(
            select(CatalogRequirementVersion).where(CatalogRequirementVersion.id == REQ_1_VER_ID)
        )
        if (
            not r1
            or not rv1
            or r1.source_id != SOURCE_ID
            or r1.requirement_key != REQ_1_KEY
            or r1.status != "Draft"
            or rv1.requirement_id != REQ_1_ID
            or rv1.source_id != SOURCE_ID
            or rv1.source_version_id != SOURCE_VERSION_ID
            or rv1.version_label != "1.0.0"
            or rv1.revision != 1
            or rv1.normalized_outcome != REQ_1_OUTCOME
            or rv1.requirement_type != "mandatory"
            or rv1.obligated_actor != "organization"
            or rv1.text_origin != "conformly_paraphrase"
            or rv1.customer_display_text is not None
            or rv1.effective_from != date(2026, 1, 1)
            or rv1.effective_until is not None
            or rv1.content_digest != REQ_1_DIGEST
            or rv1.status != "Draft"
        ):
            raise ValueError("Catalog demo fixture conflict: requirement 1 mismatch")

        ref1 = session.scalars(
            select(CatalogRequirementSourceReference).where(
                CatalogRequirementSourceReference.requirement_version_id == REQ_1_VER_ID
            )
        ).all()
        if (
            len(ref1) != 1
            or ref1[0].locator_kind != "section"
            or ref1[0].locator_value != "1.1"
            or ref1[0].sequence != 1
            or ref1[0].source_version_id != SOURCE_VERSION_ID
        ):
            raise ValueError(
                "Catalog demo fixture conflict: requirement 1 source reference mismatch"
            )

        calc_rv1_digest = compute_requirement_version_digest(
            requirement_id=rv1.requirement_id,
            source_id=rv1.source_id,
            source_version_id=rv1.source_version_id,
            version_label=rv1.version_label,
            predecessor_id=rv1.predecessor_id,
            revision=rv1.revision,
            normalized_outcome=rv1.normalized_outcome,
            requirement_type=rv1.requirement_type,
            obligated_actor=rv1.obligated_actor,
            text_origin=rv1.text_origin,
            customer_display_text=rv1.customer_display_text,
            effective_from=rv1.effective_from,
            effective_until=rv1.effective_until,
            source_references=[
                {
                    "locator_kind": ref1[0].locator_kind,
                    "locator_value": ref1[0].locator_value,
                    "sequence": ref1[0].sequence,
                    "source_version_id": ref1[0].source_version_id,
                }
            ],
            status=rv1.status,
        )
        if calc_rv1_digest != rv1.content_digest or calc_rv1_digest != REQ_1_DIGEST:
            raise ValueError("Catalog demo fixture conflict: requirement 1 digest mismatch")

        r2 = session.scalar(select(CatalogRequirement).where(CatalogRequirement.id == REQ_2_ID))
        rv2 = session.scalar(
            select(CatalogRequirementVersion).where(CatalogRequirementVersion.id == REQ_2_VER_ID)
        )
        if (
            not r2
            or not rv2
            or r2.source_id != SOURCE_ID
            or r2.requirement_key != REQ_2_KEY
            or r2.status != "Draft"
            or rv2.requirement_id != REQ_2_ID
            or rv2.source_id != SOURCE_ID
            or rv2.source_version_id != SOURCE_VERSION_ID
            or rv2.version_label != "1.0.0"
            or rv2.revision != 1
            or rv2.normalized_outcome != REQ_2_OUTCOME
            or rv2.requirement_type != "recommendation"
            or rv2.obligated_actor != "organization"
            or rv2.text_origin != "conformly_paraphrase"
            or rv2.customer_display_text is not None
            or rv2.effective_from != date(2026, 1, 1)
            or rv2.effective_until is not None
            or rv2.content_digest != REQ_2_DIGEST
            or rv2.status != "Draft"
        ):
            raise ValueError("Catalog demo fixture conflict: requirement 2 mismatch")

        ref2 = session.scalars(
            select(CatalogRequirementSourceReference).where(
                CatalogRequirementSourceReference.requirement_version_id == REQ_2_VER_ID
            )
        ).all()
        if (
            len(ref2) != 1
            or ref2[0].locator_kind != "section"
            or ref2[0].locator_value != "1.2"
            or ref2[0].sequence != 1
            or ref2[0].source_version_id != SOURCE_VERSION_ID
        ):
            raise ValueError(
                "Catalog demo fixture conflict: requirement 2 source reference mismatch"
            )

        calc_rv2_digest = compute_requirement_version_digest(
            requirement_id=rv2.requirement_id,
            source_id=rv2.source_id,
            source_version_id=rv2.source_version_id,
            version_label=rv2.version_label,
            predecessor_id=rv2.predecessor_id,
            revision=rv2.revision,
            normalized_outcome=rv2.normalized_outcome,
            requirement_type=rv2.requirement_type,
            obligated_actor=rv2.obligated_actor,
            text_origin=rv2.text_origin,
            customer_display_text=rv2.customer_display_text,
            effective_from=rv2.effective_from,
            effective_until=rv2.effective_until,
            source_references=[
                {
                    "locator_kind": ref2[0].locator_kind,
                    "locator_value": ref2[0].locator_value,
                    "sequence": ref2[0].sequence,
                    "source_version_id": ref2[0].source_version_id,
                }
            ],
            status=rv2.status,
        )
        if calc_rv2_digest != rv2.content_digest or calc_rv2_digest != REQ_2_DIGEST:
            raise ValueError("Catalog demo fixture conflict: requirement 2 digest mismatch")

        # Controls
        c1 = session.scalar(
            select(CatalogCommonControl).where(CatalogCommonControl.id == CONTROL_1_ID)
        )
        cv1 = session.scalar(
            select(CatalogControlVersion).where(CatalogControlVersion.id == CONTROL_1_VER_ID)
        )
        if (
            not c1
            or not cv1
            or c1.control_key != CONTROL_1_KEY
            or c1.domain != CONTROL_1_DOMAIN
            or c1.status != "Draft"
            or cv1.control_id != CONTROL_1_ID
            or cv1.version_label != "1.0.0"
            or cv1.revision != 1
            or cv1.title != CONTROL_1_TITLE
            or cv1.objective != CONTROL_1_OBJECTIVE
            or cv1.guidance != CONTROL_1_GUIDANCE
            or cv1.control_type != "preventive"
            or cv1.frequency != "quarterly"
            or cv1.automation_level != "manual"
            or cv1.suggested_owner_role != "Security Operations"
            or cv1.assurance_level != "foundational"
            or cv1.tags_state != "None"
            or cv1.tags is not None
            or cv1.content_digest != CTRL_1_DIGEST
            or cv1.status != "Draft"
        ):
            raise ValueError("Catalog demo fixture conflict: control 1 mismatch")

        calc_cv1_digest = compute_control_version_digest(
            control_id=cv1.control_id,
            version_label=cv1.version_label,
            predecessor_id=cv1.predecessor_id,
            revision=cv1.revision,
            title=cv1.title,
            objective=cv1.objective,
            guidance=cv1.guidance,
            control_type=cv1.control_type,
            frequency=cv1.frequency,
            automation_level=cv1.automation_level,
            suggested_owner_role=cv1.suggested_owner_role,
            assurance_level=cv1.assurance_level,
            tags_state=cv1.tags_state,
            tags=cv1.tags,
            status=cv1.status,
        )
        if calc_cv1_digest != cv1.content_digest or calc_cv1_digest != CTRL_1_DIGEST:
            raise ValueError("Catalog demo fixture conflict: control 1 digest mismatch")

        c2 = session.scalar(
            select(CatalogCommonControl).where(CatalogCommonControl.id == CONTROL_2_ID)
        )
        cv2 = session.scalar(
            select(CatalogControlVersion).where(CatalogControlVersion.id == CONTROL_2_VER_ID)
        )
        if (
            not c2
            or not cv2
            or c2.control_key != CONTROL_2_KEY
            or c2.domain != CONTROL_2_DOMAIN
            or c2.status != "Draft"
            or cv2.control_id != CONTROL_2_ID
            or cv2.version_label != "1.0.0"
            or cv2.revision != 1
            or cv2.title != CONTROL_2_TITLE
            or cv2.objective != CONTROL_2_OBJECTIVE
            or cv2.guidance != CONTROL_2_GUIDANCE
            or cv2.control_type != "corrective"
            or cv2.frequency != "semiannual"
            or cv2.automation_level != "manual"
            or cv2.suggested_owner_role != "Infrastructure Engineering"
            or cv2.assurance_level != "foundational"
            or cv2.tags_state != "None"
            or cv2.tags is not None
            or cv2.content_digest != CTRL_2_DIGEST
            or cv2.status != "Draft"
        ):
            raise ValueError("Catalog demo fixture conflict: control 2 mismatch")

        calc_cv2_digest = compute_control_version_digest(
            control_id=cv2.control_id,
            version_label=cv2.version_label,
            predecessor_id=cv2.predecessor_id,
            revision=cv2.revision,
            title=cv2.title,
            objective=cv2.objective,
            guidance=cv2.guidance,
            control_type=cv2.control_type,
            frequency=cv2.frequency,
            automation_level=cv2.automation_level,
            suggested_owner_role=cv2.suggested_owner_role,
            assurance_level=cv2.assurance_level,
            tags_state=cv2.tags_state,
            tags=cv2.tags,
            status=cv2.status,
        )
        if calc_cv2_digest != cv2.content_digest or calc_cv2_digest != CTRL_2_DIGEST:
            raise ValueError("Catalog demo fixture conflict: control 2 digest mismatch")

        # Mappings
        m1_parent = session.scalar(
            select(CatalogRequirementControlMapping).where(
                CatalogRequirementControlMapping.id == MAPPING_1_ID
            )
        )
        m1 = session.scalar(
            select(CatalogMappingVersion).where(CatalogMappingVersion.id == MAPPING_1_VER_ID)
        )
        if (
            not m1_parent
            or not m1
            or m1_parent.mapping_key != MAPPING_1_KEY
            or m1_parent.requirement_id != REQ_1_ID
            or m1_parent.control_id != CONTROL_1_ID
            or m1_parent.status != "Draft"
            or m1.mapping_id != MAPPING_1_ID
            or m1.requirement_id != REQ_1_ID
            or m1.control_id != CONTROL_1_ID
            or m1.requirement_version_id != REQ_1_VER_ID
            or m1.control_version_id != CONTROL_1_VER_ID
            or m1.requirement_version_revision != 1
            or m1.requirement_version_digest != REQ_1_DIGEST
            or m1.control_version_revision != 1
            or m1.control_version_digest != CTRL_1_DIGEST
            or m1.version_label != "1.0.0"
            or m1.revision != 1
            or m1.mapping_type != "Full"
            or m1.rationale != MAPPING_1_RATIONALE
            or m1.covered_dimensions != MAPPING_1_COVERED
            or m1.excluded_dimensions is not None
            or m1.conditions is not None
            or m1.source_basis != "expert_analysis"
            or m1.confidence != "high"
            or m1.review_state != "Draft"
            or m1.content_digest != MAP_1_DIGEST
            or m1.status != "Draft"
        ):
            raise ValueError("Catalog demo fixture conflict: mapping 1 mismatch")

        calc_m1_digest = compute_mapping_version_digest(
            mapping_id=m1.mapping_id,
            requirement_id=m1.requirement_id,
            control_id=m1.control_id,
            requirement_version_id=m1.requirement_version_id,
            control_version_id=m1.control_version_id,
            requirement_version_revision=m1.requirement_version_revision,
            requirement_version_digest=m1.requirement_version_digest,
            control_version_revision=m1.control_version_revision,
            control_version_digest=m1.control_version_digest,
            version_label=m1.version_label,
            predecessor_id=m1.predecessor_id,
            revision=m1.revision,
            mapping_type=m1.mapping_type,
            rationale=m1.rationale,
            covered_dimensions=m1.covered_dimensions,
            excluded_dimensions=m1.excluded_dimensions,
            conditions=m1.conditions,
            source_basis=m1.source_basis,
            confidence=m1.confidence,
            review_state=m1.review_state,
            status=m1.status,
        )
        if calc_m1_digest != m1.content_digest or calc_m1_digest != MAP_1_DIGEST:
            raise ValueError("Catalog demo fixture conflict: mapping 1 digest mismatch")

        m2_parent = session.scalar(
            select(CatalogRequirementControlMapping).where(
                CatalogRequirementControlMapping.id == MAPPING_2_ID
            )
        )
        m2 = session.scalar(
            select(CatalogMappingVersion).where(CatalogMappingVersion.id == MAPPING_2_VER_ID)
        )
        if (
            not m2_parent
            or not m2
            or m2_parent.mapping_key != MAPPING_2_KEY
            or m2_parent.requirement_id != REQ_2_ID
            or m2_parent.control_id != CONTROL_2_ID
            or m2_parent.status != "Draft"
            or m2.mapping_id != MAPPING_2_ID
            or m2.requirement_id != REQ_2_ID
            or m2.control_id != CONTROL_2_ID
            or m2.requirement_version_id != REQ_2_VER_ID
            or m2.control_version_id != CONTROL_2_VER_ID
            or m2.requirement_version_revision != 1
            or m2.requirement_version_digest != REQ_2_DIGEST
            or m2.control_version_revision != 1
            or m2.control_version_digest != CTRL_2_DIGEST
            or m2.version_label != "1.0.0"
            or m2.revision != 1
            or m2.mapping_type != "Partial"
            or m2.rationale != MAPPING_2_RATIONALE
            or m2.covered_dimensions != MAPPING_2_COVERED
            or m2.excluded_dimensions != MAPPING_2_EXCLUDED
            or m2.conditions is not None
            or m2.source_basis != "expert_analysis"
            or m2.confidence != "medium"
            or m2.review_state != "Draft"
            or m2.content_digest != MAP_2_DIGEST
            or m2.status != "Draft"
        ):
            raise ValueError("Catalog demo fixture conflict: mapping 2 mismatch")

        calc_m2_digest = compute_mapping_version_digest(
            mapping_id=m2.mapping_id,
            requirement_id=m2.requirement_id,
            control_id=m2.control_id,
            requirement_version_id=m2.requirement_version_id,
            control_version_id=m2.control_version_id,
            requirement_version_revision=m2.requirement_version_revision,
            requirement_version_digest=m2.requirement_version_digest,
            control_version_revision=m2.control_version_revision,
            control_version_digest=m2.control_version_digest,
            version_label=m2.version_label,
            predecessor_id=m2.predecessor_id,
            revision=m2.revision,
            mapping_type=m2.mapping_type,
            rationale=m2.rationale,
            covered_dimensions=m2.covered_dimensions,
            excluded_dimensions=m2.excluded_dimensions,
            conditions=m2.conditions,
            source_basis=m2.source_basis,
            confidence=m2.confidence,
            review_state=m2.review_state,
            status=m2.status,
        )
        if calc_m2_digest != m2.content_digest or calc_m2_digest != MAP_2_DIGEST:
            raise ValueError("Catalog demo fixture conflict: mapping 2 digest mismatch")

        # Evidence requirements
        ev1 = session.scalar(
            select(CatalogEvidenceRequirementVersion).where(
                CatalogEvidenceRequirementVersion.id == EVID_1_VER_ID
            )
        )
        if (
            not ev1
            or ev1.control_id != CONTROL_1_ID
            or ev1.control_version_id != CONTROL_1_VER_ID
            or ev1.requirement_key != EVID_1_KEY
            or ev1.sequence != 1
            or ev1.title != EVID_1_TITLE
            or ev1.frequency != "quarterly"
            or ev1.custom_frequency is not None
            or ev1.scope_state != "All"
            or ev1.scope_guidance is not None
            or ev1.assurance_purpose != "operating_effectiveness"
            or ev1.validity_rule != "point_in_time"
            or ev1.max_age_days != 90
            or ev1.guidance != "Signed export or ticket showing review of elevated permissions."
            or ev1.missing_data_behavior != "requires_human_review"
            or ev1.content_digest != EVID_1_DIGEST
            or ev1.status != "Draft"
        ):
            raise ValueError("Catalog demo fixture conflict: evidence 1 mismatch")

        art1 = session.scalars(
            select(CatalogEvidenceRequirementArtifactType).where(
                CatalogEvidenceRequirementArtifactType.evidence_requirement_version_id
                == EVID_1_VER_ID
            )
        ).all()
        if len(art1) != 1 or art1[0].artifact_type != "report" or art1[0].sequence != 1:
            raise ValueError("Catalog demo fixture conflict: evidence 1 artifact type mismatch")

        meta1 = session.scalars(
            select(CatalogEvidenceRequirementMetadataKey).where(
                CatalogEvidenceRequirementMetadataKey.evidence_requirement_version_id
                == EVID_1_VER_ID
            )
        ).all()
        if len(meta1) != 1 or meta1[0].metadata_key != "reviewer_name" or meta1[0].sequence != 1:
            raise ValueError("Catalog demo fixture conflict: evidence 1 metadata key mismatch")

        calc_ev1_digest = compute_evidence_requirement_version_digest(
            control_version_id=ev1.control_version_id,
            control_version_digest=CTRL_1_DIGEST,
            requirement_key=ev1.requirement_key,
            sequence=ev1.sequence,
            title=ev1.title,
            frequency=ev1.frequency,
            custom_frequency=ev1.custom_frequency,
            scope_state=ev1.scope_state,
            scope_guidance=ev1.scope_guidance,
            assurance_purpose=ev1.assurance_purpose,
            validity_rule=ev1.validity_rule,
            max_age_days=ev1.max_age_days,
            guidance=ev1.guidance,
            artifact_types=[
                {"artifact_type": a.artifact_type, "sequence": a.sequence} for a in art1
            ],
            required_metadata=[
                {"metadata_key": m.metadata_key, "sequence": m.sequence} for m in meta1
            ],
            missing_data_behavior=ev1.missing_data_behavior,
        )
        if calc_ev1_digest != ev1.content_digest or calc_ev1_digest != EVID_1_DIGEST:
            raise ValueError("Catalog demo fixture conflict: evidence 1 digest mismatch")

        ev2 = session.scalar(
            select(CatalogEvidenceRequirementVersion).where(
                CatalogEvidenceRequirementVersion.id == EVID_2_VER_ID
            )
        )
        if (
            not ev2
            or ev2.control_id != CONTROL_2_ID
            or ev2.control_version_id != CONTROL_2_VER_ID
            or ev2.requirement_key != EVID_2_KEY
            or ev2.sequence != 1
            or ev2.title != EVID_2_TITLE
            or ev2.frequency != "semiannual"
            or ev2.custom_frequency is not None
            or ev2.scope_state != "All"
            or ev2.scope_guidance is not None
            or ev2.assurance_purpose != "operating_effectiveness"
            or ev2.validity_rule != "point_in_time"
            or ev2.max_age_days != 180
            or ev2.guidance != "Log or ticket documenting test recovery from backup."
            or ev2.missing_data_behavior != "requires_human_review"
            or ev2.content_digest != EVID_2_DIGEST
            or ev2.status != "Draft"
        ):
            raise ValueError("Catalog demo fixture conflict: evidence 2 mismatch")

        art2 = session.scalars(
            select(CatalogEvidenceRequirementArtifactType).where(
                CatalogEvidenceRequirementArtifactType.evidence_requirement_version_id
                == EVID_2_VER_ID
            )
        ).all()
        if len(art2) != 1 or art2[0].artifact_type != "log" or art2[0].sequence != 1:
            raise ValueError("Catalog demo fixture conflict: evidence 2 artifact type mismatch")

        meta2 = session.scalars(
            select(CatalogEvidenceRequirementMetadataKey).where(
                CatalogEvidenceRequirementMetadataKey.evidence_requirement_version_id
                == EVID_2_VER_ID
            )
        ).all()
        if len(meta2) != 1 or meta2[0].metadata_key != "backup_timestamp" or meta2[0].sequence != 1:
            raise ValueError("Catalog demo fixture conflict: evidence 2 metadata key mismatch")

        calc_ev2_digest = compute_evidence_requirement_version_digest(
            control_version_id=ev2.control_version_id,
            control_version_digest=CTRL_2_DIGEST,
            requirement_key=ev2.requirement_key,
            sequence=ev2.sequence,
            title=ev2.title,
            frequency=ev2.frequency,
            custom_frequency=ev2.custom_frequency,
            scope_state=ev2.scope_state,
            scope_guidance=ev2.scope_guidance,
            assurance_purpose=ev2.assurance_purpose,
            validity_rule=ev2.validity_rule,
            max_age_days=ev2.max_age_days,
            guidance=ev2.guidance,
            artifact_types=[
                {"artifact_type": a.artifact_type, "sequence": a.sequence} for a in art2
            ],
            required_metadata=[
                {"metadata_key": m.metadata_key, "sequence": m.sequence} for m in meta2
            ],
            missing_data_behavior=ev2.missing_data_behavior,
        )
        if calc_ev2_digest != ev2.content_digest or calc_ev2_digest != EVID_2_DIGEST:
            raise ValueError("Catalog demo fixture conflict: evidence 2 digest mismatch")

        # Procedures
        ap1 = session.scalar(
            select(CatalogAssessmentProcedureVersion).where(
                CatalogAssessmentProcedureVersion.id == PROC_1_VER_ID
            )
        )
        if (
            not ap1
            or ap1.control_id != CONTROL_1_ID
            or ap1.control_version_id != CONTROL_1_VER_ID
            or ap1.procedure_key != PROC_1_KEY
            or ap1.sequence != 1
            or ap1.title != PROC_1_TITLE
            or ap1.objective != PROC_1_OBJECTIVE
            or ap1.sample_guidance is not None
            or ap1.scope_guidance is not None
            or ap1.decision_guidance != "Confirm all privileged accounts have recorded approvals."
            or ap1.assessor_qualifications != "Security Auditor"
            or ap1.missing_data_behavior != "requires_human_review"
            or ap1.content_digest != PROC_1_DIGEST
            or ap1.status != "Draft"
        ):
            raise ValueError("Catalog demo fixture conflict: procedure 1 mismatch")

        st1 = session.scalars(
            select(CatalogAssessmentProcedureStep).where(
                CatalogAssessmentProcedureStep.assessment_procedure_version_id == PROC_1_VER_ID
            )
        ).all()
        if (
            len(st1) != 1
            or st1[0].sequence != 1
            or st1[0].step_kind != "inspect"
            or st1[0].instruction
            != "Inspect quarterly review records for unapproved privilege grants."
            or st1[0].expected_output != "All grants are approved and documented."
        ):
            raise ValueError("Catalog demo fixture conflict: procedure 1 step mismatch")

        lk1 = session.scalars(
            select(CatalogAssessmentProcedureEvidenceRequirement).where(
                CatalogAssessmentProcedureEvidenceRequirement.assessment_procedure_version_id
                == PROC_1_VER_ID
            )
        ).all()
        if (
            len(lk1) != 1
            or lk1[0].sequence != 1
            or lk1[0].evidence_requirement_version_id != EVID_1_VER_ID
        ):
            raise ValueError("Catalog demo fixture conflict: procedure 1 evidence link mismatch")

        calc_ap1_digest = compute_assessment_procedure_version_digest(
            control_version_id=ap1.control_version_id,
            control_version_digest=CTRL_1_DIGEST,
            procedure_key=ap1.procedure_key,
            sequence=ap1.sequence,
            title=ap1.title,
            objective=ap1.objective,
            sample_guidance=ap1.sample_guidance,
            scope_guidance=ap1.scope_guidance,
            decision_guidance=ap1.decision_guidance,
            assessor_qualifications=ap1.assessor_qualifications,
            steps=[
                {
                    "expected_output": st1[0].expected_output,
                    "instruction": st1[0].instruction,
                    "sequence": st1[0].sequence,
                    "step_kind": st1[0].step_kind,
                }
            ],
            evidence_requirements=[
                {
                    "content_digest": EVID_1_DIGEST,
                    "id": lk1[0].evidence_requirement_version_id,
                    "sequence": lk1[0].sequence,
                }
            ],
            missing_data_behavior=ap1.missing_data_behavior,
        )
        if calc_ap1_digest != ap1.content_digest or calc_ap1_digest != PROC_1_DIGEST:
            raise ValueError("Catalog demo fixture conflict: procedure 1 digest mismatch")

        ap2 = session.scalar(
            select(CatalogAssessmentProcedureVersion).where(
                CatalogAssessmentProcedureVersion.id == PROC_2_VER_ID
            )
        )
        if (
            not ap2
            or ap2.control_id != CONTROL_2_ID
            or ap2.control_version_id != CONTROL_2_VER_ID
            or ap2.procedure_key != PROC_2_KEY
            or ap2.sequence != 1
            or ap2.title != PROC_2_TITLE
            or ap2.objective != PROC_2_OBJECTIVE
            or ap2.sample_guidance is not None
            or ap2.scope_guidance is not None
            or ap2.decision_guidance
            != "Confirm recovery verification completed successfully within RTO."
            or ap2.assessor_qualifications != "Systems Auditor"
            or ap2.missing_data_behavior != "requires_human_review"
            or ap2.content_digest != PROC_2_DIGEST
            or ap2.status != "Draft"
        ):
            raise ValueError("Catalog demo fixture conflict: procedure 2 mismatch")

        st2 = session.scalars(
            select(CatalogAssessmentProcedureStep).where(
                CatalogAssessmentProcedureStep.assessment_procedure_version_id == PROC_2_VER_ID
            )
        ).all()
        if (
            len(st2) != 1
            or st2[0].sequence != 1
            or st2[0].step_kind != "inspect"
            or st2[0].instruction != "Inspect restore logs to verify checksum match and RTO."
            or st2[0].expected_output != "Restoration verified complete and matching source data."
        ):
            raise ValueError("Catalog demo fixture conflict: procedure 2 step mismatch")

        lk2 = session.scalars(
            select(CatalogAssessmentProcedureEvidenceRequirement).where(
                CatalogAssessmentProcedureEvidenceRequirement.assessment_procedure_version_id
                == PROC_2_VER_ID
            )
        ).all()
        if (
            len(lk2) != 1
            or lk2[0].sequence != 1
            or lk2[0].evidence_requirement_version_id != EVID_2_VER_ID
        ):
            raise ValueError("Catalog demo fixture conflict: procedure 2 evidence link mismatch")

        calc_ap2_digest = compute_assessment_procedure_version_digest(
            control_version_id=ap2.control_version_id,
            control_version_digest=CTRL_2_DIGEST,
            procedure_key=ap2.procedure_key,
            sequence=ap2.sequence,
            title=ap2.title,
            objective=ap2.objective,
            sample_guidance=ap2.sample_guidance,
            scope_guidance=ap2.scope_guidance,
            decision_guidance=ap2.decision_guidance,
            assessor_qualifications=ap2.assessor_qualifications,
            steps=[
                {
                    "expected_output": st2[0].expected_output,
                    "instruction": st2[0].instruction,
                    "sequence": st2[0].sequence,
                    "step_kind": st2[0].step_kind,
                }
            ],
            evidence_requirements=[
                {
                    "content_digest": EVID_2_DIGEST,
                    "id": lk2[0].evidence_requirement_version_id,
                    "sequence": lk2[0].sequence,
                }
            ],
            missing_data_behavior=ap2.missing_data_behavior,
        )
        if calc_ap2_digest != ap2.content_digest or calc_ap2_digest != PROC_2_DIGEST:
            raise ValueError("Catalog demo fixture conflict: procedure 2 digest mismatch")

        # Verified identical reusable fixture
        return

    past_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    # 1. Publisher
    session.add(
        CatalogPublisher(
            id=PUBLISHER_ID,
            publisher_key=PUBLISHER_KEY,
            name=PUBLISHER_NAME,
            status="Draft",
        )
    )
    session.flush()

    # 2. Source
    session.add(
        CatalogSource(
            id=SOURCE_ID,
            publisher_id=PUBLISHER_ID,
            source_key=SOURCE_KEY,
            title=SOURCE_TITLE,
            status="Draft",
        )
    )
    session.flush()

    # 3. Source Permission Guard
    session.add(
        CatalogSourcePermissionGuard(
            source_id=SOURCE_ID,
            revision=2,
            updated_at=past_dt,
        )
    )
    session.flush()

    # 4. Source Version
    session.add(
        CatalogSourceVersion(
            id=SOURCE_VERSION_ID,
            source_id=SOURCE_ID,
            edition=SOURCE_EDITION,
            language=SOURCE_LANGUAGE,
            official_locator=SOURCE_LOCATOR,
            publication_date=SOURCE_PUB_DATE,
            retrieved_at=SOURCE_RETRIEVED_AT,
            predecessor_id=None,
            revision=1,
            status="Draft",
            content_digest=SOURCE_VERSION_DIGEST,
            digest_schema="catalog-draft-v1",
        )
    )
    session.flush()

    # 5. Source Provenance
    session.add(
        CatalogSourceProvenance(
            id=PROVENANCE_ID,
            source_version_id=SOURCE_VERSION_ID,
            source_revision=1,
            content_sha256=b"\xaa" * 32,
            content_size=1024,
            mime_type="application/pdf",
            locator=SOURCE_LOCATOR,
            retrieved_at=SOURCE_RETRIEVED_AT,
            recorded_by_actor_id=ACTOR_A_ID,
        )
    )
    session.flush()

    # 6. Source Permission Proposals (reference & map, recorded by ACTOR_A_ID)
    session.add(
        CatalogSourcePermissionProposal(
            id=PROPOSAL_REF_ID,
            source_version_id=SOURCE_VERSION_ID,
            provenance_id=PROVENANCE_ID,
            use_case="reference",
            scope_key="global",
            sequence=1,
            proposed_outcome="Allowed",
            review_state="Draft",
            conditions_state="None",
            recorded_by_actor_id=ACTOR_A_ID,
            created_at=past_dt,
        )
    )
    session.add(
        CatalogSourcePermissionProposal(
            id=PROPOSAL_MAP_ID,
            source_version_id=SOURCE_VERSION_ID,
            provenance_id=PROVENANCE_ID,
            use_case="map",
            scope_key="global",
            sequence=1,
            proposed_outcome="Allowed",
            review_state="Draft",
            conditions_state="None",
            recorded_by_actor_id=ACTOR_A_ID,
            created_at=past_dt,
        )
    )
    session.flush()

    # 7. Source Permission Decisions (reference & map, approved by ACTOR_B_ID - dual-actor separation)
    session.add(
        CatalogSourcePermissionDecision(
            id=DECISION_REF_ID,
            source_id=SOURCE_ID,
            source_version_id=SOURCE_VERSION_ID,
            proposal_id=PROPOSAL_REF_ID,
            use_case="reference",
            scope_key="global",
            sequence=1,
            predecessor_id=None,
            decision="Allowed",
            conditions_state="None",
            valid_from=past_dt,
            valid_until=None,
            decided_by_actor_id=ACTOR_B_ID,
            decided_at=past_dt,
            evidence_reference="SYNTHETIC-REF-EVIDENCE",
            policy_version="catalog-permission-v1",
            guard_revision=1,
        )
    )
    session.add(
        CatalogSourcePermissionDecision(
            id=DECISION_MAP_ID,
            source_id=SOURCE_ID,
            source_version_id=SOURCE_VERSION_ID,
            proposal_id=PROPOSAL_MAP_ID,
            use_case="map",
            scope_key="global",
            sequence=1,
            predecessor_id=None,
            decision="Allowed",
            conditions_state="None",
            valid_from=past_dt,
            valid_until=None,
            decided_by_actor_id=ACTOR_B_ID,
            decided_at=past_dt,
            evidence_reference="SYNTHETIC-MAP-EVIDENCE",
            policy_version="catalog-permission-v1",
            guard_revision=2,
        )
    )
    session.flush()

    # 6. Requirements
    session.add(
        CatalogRequirement(
            id=REQ_1_ID,
            source_id=SOURCE_ID,
            requirement_key=REQ_1_KEY,
            status="Draft",
        )
    )
    session.add(
        CatalogRequirement(
            id=REQ_2_ID,
            source_id=SOURCE_ID,
            requirement_key=REQ_2_KEY,
            status="Draft",
        )
    )
    session.flush()

    # 7. Requirement Versions
    session.add(
        CatalogRequirementVersion(
            id=REQ_1_VER_ID,
            requirement_id=REQ_1_ID,
            source_id=SOURCE_ID,
            source_version_id=SOURCE_VERSION_ID,
            version_label="1.0.0",
            predecessor_id=None,
            revision=1,
            normalized_outcome=REQ_1_OUTCOME,
            requirement_type="mandatory",
            obligated_actor="organization",
            text_origin="conformly_paraphrase",
            customer_display_text=None,
            effective_from=date(2026, 1, 1),
            effective_until=None,
            status="Draft",
            content_digest=REQ_1_DIGEST,
            digest_schema="catalog-draft-v1",
        )
    )
    session.add(
        CatalogRequirementVersion(
            id=REQ_2_VER_ID,
            requirement_id=REQ_2_ID,
            source_id=SOURCE_ID,
            source_version_id=SOURCE_VERSION_ID,
            version_label="1.0.0",
            predecessor_id=None,
            revision=1,
            normalized_outcome=REQ_2_OUTCOME,
            requirement_type="recommendation",
            obligated_actor="organization",
            text_origin="conformly_paraphrase",
            customer_display_text=None,
            effective_from=date(2026, 1, 1),
            effective_until=None,
            status="Draft",
            content_digest=REQ_2_DIGEST,
            digest_schema="catalog-draft-v1",
        )
    )
    session.flush()

    # 8. Requirement Source References
    session.add(
        CatalogRequirementSourceReference(
            requirement_version_id=REQ_1_VER_ID,
            source_version_id=SOURCE_VERSION_ID,
            locator_kind="section",
            locator_value="1.1",
            sequence=1,
        )
    )
    session.add(
        CatalogRequirementSourceReference(
            requirement_version_id=REQ_2_VER_ID,
            source_version_id=SOURCE_VERSION_ID,
            locator_kind="section",
            locator_value="1.2",
            sequence=1,
        )
    )
    session.flush()

    # 9. Common Controls
    session.add(
        CatalogCommonControl(
            id=CONTROL_1_ID,
            control_key=CONTROL_1_KEY,
            domain=CONTROL_1_DOMAIN,
            status="Draft",
        )
    )
    session.add(
        CatalogCommonControl(
            id=CONTROL_2_ID,
            control_key=CONTROL_2_KEY,
            domain=CONTROL_2_DOMAIN,
            status="Draft",
        )
    )
    session.flush()

    # 10. Control Versions
    session.add(
        CatalogControlVersion(
            id=CONTROL_1_VER_ID,
            control_id=CONTROL_1_ID,
            version_label="1.0.0",
            predecessor_id=None,
            revision=1,
            title=CONTROL_1_TITLE,
            objective=CONTROL_1_OBJECTIVE,
            guidance=CONTROL_1_GUIDANCE,
            control_type="preventive",
            frequency="quarterly",
            automation_level="manual",
            suggested_owner_role="Security Operations",
            assurance_level="foundational",
            tags_state="None",
            tags=None,
            status="Draft",
            content_digest=CTRL_1_DIGEST,
            digest_schema="catalog-draft-v1",
        )
    )
    session.add(
        CatalogControlVersion(
            id=CONTROL_2_VER_ID,
            control_id=CONTROL_2_ID,
            version_label="1.0.0",
            predecessor_id=None,
            revision=1,
            title=CONTROL_2_TITLE,
            objective=CONTROL_2_OBJECTIVE,
            guidance=CONTROL_2_GUIDANCE,
            control_type="corrective",
            frequency="semiannual",
            automation_level="manual",
            suggested_owner_role="Infrastructure Engineering",
            assurance_level="foundational",
            tags_state="None",
            tags=None,
            status="Draft",
            content_digest=CTRL_2_DIGEST,
            digest_schema="catalog-draft-v1",
        )
    )
    session.flush()

    # 11. Mappings
    session.add(
        CatalogRequirementControlMapping(
            id=MAPPING_1_ID,
            mapping_key=MAPPING_1_KEY,
            requirement_id=REQ_1_ID,
            control_id=CONTROL_1_ID,
            status="Draft",
        )
    )
    session.add(
        CatalogRequirementControlMapping(
            id=MAPPING_2_ID,
            mapping_key=MAPPING_2_KEY,
            requirement_id=REQ_2_ID,
            control_id=CONTROL_2_ID,
            status="Draft",
        )
    )
    session.flush()

    # 11b. Mapping Versions
    session.add(
        CatalogMappingVersion(
            id=MAPPING_1_VER_ID,
            mapping_id=MAPPING_1_ID,
            requirement_id=REQ_1_ID,
            control_id=CONTROL_1_ID,
            requirement_version_id=REQ_1_VER_ID,
            control_version_id=CONTROL_1_VER_ID,
            requirement_version_revision=1,
            requirement_version_digest=REQ_1_DIGEST,
            control_version_revision=1,
            control_version_digest=CTRL_1_DIGEST,
            version_label="1.0.0",
            predecessor_id=None,
            revision=1,
            mapping_type="Full",
            rationale=MAPPING_1_RATIONALE,
            covered_dimensions=MAPPING_1_COVERED,
            excluded_dimensions=None,
            conditions=None,
            source_basis="expert_analysis",
            confidence="high",
            review_state="Draft",
            status="Draft",
            content_digest=MAP_1_DIGEST,
            digest_schema="catalog-draft-v1",
        )
    )
    session.add(
        CatalogMappingVersion(
            id=MAPPING_2_VER_ID,
            mapping_id=MAPPING_2_ID,
            requirement_id=REQ_2_ID,
            control_id=CONTROL_2_ID,
            requirement_version_id=REQ_2_VER_ID,
            control_version_id=CONTROL_2_VER_ID,
            requirement_version_revision=1,
            requirement_version_digest=REQ_2_DIGEST,
            control_version_revision=1,
            control_version_digest=CTRL_2_DIGEST,
            version_label="1.0.0",
            predecessor_id=None,
            revision=1,
            mapping_type="Partial",
            rationale=MAPPING_2_RATIONALE,
            covered_dimensions=MAPPING_2_COVERED,
            excluded_dimensions=MAPPING_2_EXCLUDED,
            conditions=None,
            source_basis="expert_analysis",
            confidence="medium",
            review_state="Draft",
            status="Draft",
            content_digest=MAP_2_DIGEST,
            digest_schema="catalog-draft-v1",
        )
    )
    session.flush()

    # 12. Evidence Requirements
    session.add(
        CatalogEvidenceRequirementVersion(
            id=EVID_1_VER_ID,
            control_version_id=CONTROL_1_VER_ID,
            control_id=CONTROL_1_ID,
            requirement_key=EVID_1_KEY,
            sequence=1,
            title=EVID_1_TITLE,
            frequency="quarterly",
            custom_frequency=None,
            scope_state="All",
            scope_guidance=None,
            assurance_purpose="operating_effectiveness",
            validity_rule="point_in_time",
            max_age_days=90,
            guidance="Signed export or ticket showing review of elevated permissions.",
            missing_data_behavior="requires_human_review",
            status="Draft",
            content_digest=EVID_1_DIGEST,
            digest_schema="catalog-assurance-draft-v1",
        )
    )
    session.add(
        CatalogEvidenceRequirementVersion(
            id=EVID_2_VER_ID,
            control_version_id=CONTROL_2_VER_ID,
            control_id=CONTROL_2_ID,
            requirement_key=EVID_2_KEY,
            sequence=1,
            title=EVID_2_TITLE,
            frequency="semiannual",
            custom_frequency=None,
            scope_state="All",
            scope_guidance=None,
            assurance_purpose="operating_effectiveness",
            validity_rule="point_in_time",
            max_age_days=180,
            guidance="Log or ticket documenting test recovery from backup.",
            missing_data_behavior="requires_human_review",
            status="Draft",
            content_digest=EVID_2_DIGEST,
            digest_schema="catalog-assurance-draft-v1",
        )
    )
    session.flush()

    # 12b. Evidence Requirement Artifact Types & Metadata Keys
    session.add(
        CatalogEvidenceRequirementArtifactType(
            evidence_requirement_version_id=EVID_1_VER_ID,
            control_version_id=CONTROL_1_VER_ID,
            sequence=1,
            artifact_type="report",
        )
    )
    session.add(
        CatalogEvidenceRequirementMetadataKey(
            evidence_requirement_version_id=EVID_1_VER_ID,
            control_version_id=CONTROL_1_VER_ID,
            sequence=1,
            metadata_key="reviewer_name",
        )
    )
    session.add(
        CatalogEvidenceRequirementArtifactType(
            evidence_requirement_version_id=EVID_2_VER_ID,
            control_version_id=CONTROL_2_VER_ID,
            sequence=1,
            artifact_type="log",
        )
    )
    session.add(
        CatalogEvidenceRequirementMetadataKey(
            evidence_requirement_version_id=EVID_2_VER_ID,
            control_version_id=CONTROL_2_VER_ID,
            sequence=1,
            metadata_key="backup_timestamp",
        )
    )
    session.flush()

    # 13. Assessment Procedures
    session.add(
        CatalogAssessmentProcedureVersion(
            id=PROC_1_VER_ID,
            control_version_id=CONTROL_1_VER_ID,
            control_id=CONTROL_1_ID,
            procedure_key=PROC_1_KEY,
            sequence=1,
            title=PROC_1_TITLE,
            objective=PROC_1_OBJECTIVE,
            decision_guidance="Confirm all privileged accounts have recorded approvals.",
            assessor_qualifications="Security Auditor",
            missing_data_behavior="requires_human_review",
            status="Draft",
            content_digest=PROC_1_DIGEST,
            digest_schema="catalog-assurance-draft-v1",
        )
    )
    session.add(
        CatalogAssessmentProcedureVersion(
            id=PROC_2_VER_ID,
            control_version_id=CONTROL_2_VER_ID,
            control_id=CONTROL_2_ID,
            procedure_key=PROC_2_KEY,
            sequence=1,
            title=PROC_2_TITLE,
            objective=PROC_2_OBJECTIVE,
            decision_guidance="Confirm recovery verification completed successfully within RTO.",
            assessor_qualifications="Systems Auditor",
            missing_data_behavior="requires_human_review",
            status="Draft",
            content_digest=PROC_2_DIGEST,
            digest_schema="catalog-assurance-draft-v1",
        )
    )
    session.flush()

    # 13b. Steps and AP-ER Links
    session.add(
        CatalogAssessmentProcedureStep(
            assessment_procedure_version_id=PROC_1_VER_ID,
            control_version_id=CONTROL_1_VER_ID,
            sequence=1,
            step_kind="inspect",
            instruction="Inspect quarterly review records for unapproved privilege grants.",
            expected_output="All grants are approved and documented.",
        )
    )
    session.add(
        CatalogAssessmentProcedureEvidenceRequirement(
            assessment_procedure_version_id=PROC_1_VER_ID,
            evidence_requirement_version_id=EVID_1_VER_ID,
            control_version_id=CONTROL_1_VER_ID,
            sequence=1,
        )
    )
    session.add(
        CatalogAssessmentProcedureStep(
            assessment_procedure_version_id=PROC_2_VER_ID,
            control_version_id=CONTROL_2_VER_ID,
            sequence=1,
            step_kind="inspect",
            instruction="Inspect restore logs to verify checksum match and RTO.",
            expected_output="Restoration verified complete and matching source data.",
        )
    )
    session.add(
        CatalogAssessmentProcedureEvidenceRequirement(
            assessment_procedure_version_id=PROC_2_VER_ID,
            evidence_requirement_version_id=EVID_2_VER_ID,
            control_version_id=CONTROL_2_VER_ID,
            sequence=1,
        )
    )
    session.flush()
