"""Catalog demo projection builder reading exclusively via accepted catalog services."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.catalog_demo.dataset import (
    ACTOR_A_ID,
    CONTROL_1_DOMAIN,
    CONTROL_1_GUIDANCE,
    CONTROL_1_ID,
    CONTROL_1_KEY,
    CONTROL_1_OBJECTIVE,
    CONTROL_1_TITLE,
    CONTROL_1_VER_ID,
    CONTROL_2_DOMAIN,
    CONTROL_2_GUIDANCE,
    CONTROL_2_ID,
    CONTROL_2_KEY,
    CONTROL_2_OBJECTIVE,
    CONTROL_2_TITLE,
    CONTROL_2_VER_ID,
    CTRL_1_DIGEST,
    CTRL_2_DIGEST,
    EVID_1_DIGEST,
    EVID_1_KEY,
    EVID_1_TITLE,
    EVID_1_VER_ID,
    EVID_2_DIGEST,
    EVID_2_KEY,
    EVID_2_TITLE,
    EVID_2_VER_ID,
    MAP_1_DIGEST,
    MAP_2_DIGEST,
    MAPPING_1_COVERED,
    MAPPING_1_ID,
    MAPPING_1_KEY,
    MAPPING_1_RATIONALE,
    MAPPING_1_VER_ID,
    MAPPING_2_COVERED,
    MAPPING_2_EXCLUDED,
    MAPPING_2_ID,
    MAPPING_2_KEY,
    MAPPING_2_RATIONALE,
    MAPPING_2_VER_ID,
    PROC_1_DIGEST,
    PROC_1_KEY,
    PROC_1_OBJECTIVE,
    PROC_1_TITLE,
    PROC_1_VER_ID,
    PROC_2_DIGEST,
    PROC_2_KEY,
    PROC_2_OBJECTIVE,
    PROC_2_TITLE,
    PROC_2_VER_ID,
    PROVENANCE_ID,
    PUBLISHER_ID,
    REQ_1_DIGEST,
    REQ_1_ID,
    REQ_1_KEY,
    REQ_1_OUTCOME,
    REQ_1_VER_ID,
    REQ_2_DIGEST,
    REQ_2_ID,
    REQ_2_KEY,
    REQ_2_OUTCOME,
    REQ_2_VER_ID,
    SOURCE_EDITION,
    SOURCE_ID,
    SOURCE_KEY,
    SOURCE_LANGUAGE,
    SOURCE_LOCATOR,
    SOURCE_PUB_DATE,
    SOURCE_TITLE,
    SOURCE_VERSION_DIGEST,
    SOURCE_VERSION_ID,
)
from conformly.catalog_demo.db import AuditPersistenceError
from conformly.catalog_demo.schemas import (
    ArtifactTypeDTO,
    CatalogAssessmentProcedureDTO,
    CatalogControlDTO,
    CatalogDemoGraphResponse,
    CatalogEvidenceRequirementDTO,
    CatalogMappingDTO,
    CatalogRequirementDTO,
    CatalogSourceDTO,
    CatalogSourceVersionDTO,
    MetadataKeyDTO,
    ProcedureStepDTO,
    SourceReferenceDTO,
)
from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogNotFoundError,
    CatalogPermissionDeniedError,
    CatalogSecurityError,
)
from conformly.catalog_v2.audit import DeniedAuditSink
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
    CatalogEvidenceRequirementArtifactType,
    CatalogEvidenceRequirementMetadataKey,
    CatalogRequirementControlMapping,
    CatalogRequirementSourceReference,
    CatalogSourcePermissionDecision,
    CatalogSourcePermissionProposal,
    CatalogSourceProvenance,
)
from conformly.catalog_v2.service_assurance import CatalogAssuranceDraftService


def _is_assurance_aggregate_corruption(exc: CatalogSecurityError) -> bool:
    """Identify genuine assurance aggregate-integrity failures.

    Distinguishes stored assurance entity corruption (tampered artifact/step
    sequences, invalid child counts, corrupted content digests, cross-control links)
    from infrastructure errors (trusted-clock, database connection, audit persistence,
    or actor auth failures).
    """
    # Infrastructure, database, or connection failures carry an underlying cause
    if exc.__cause__ is not None:
        return False

    msg = str(exc)

    # Trusted clock failures fail closed as infrastructure errors
    if msg.startswith("Unable to establish trusted database time"):
        return False

    # Check for known assurance entity aggregate failure signatures from service_assurance
    assurance_entity_prefixes = (
        "EvidenceRequirementVersion '",
        "Stored EvidenceRequirementVersion '",
        "AssessmentProcedureVersion '",
        "Corrupt or cross-control evidence requirement link in procedure '",
    )
    if not any(msg.startswith(prefix) for prefix in assurance_entity_prefixes):
        return False

    # Check for specific aggregate-integrity failure patterns
    return (
        "corrupt aggregate:" in msg
        or "sequence broken:" in msg
        or "content digest corrupt or altered" in msg
        or "stored content digest does not match recomputed aggregate" in msg
        or msg.startswith("Corrupt or cross-control evidence requirement link in procedure '")
    )


def project_catalog_demo_graph(
    session: Session,
    actor_context: CatalogActorContext,
    denied_audit_sink: DeniedAuditSink | None = None,
) -> CatalogDemoGraphResponse:
    """Project the complete synthetic catalog demo graph through catalog services."""
    service = CatalogAssuranceDraftService(session, denied_audit_sink=denied_audit_sink)

    try:
        # 1. Source Version & Source (via service reads with permission enforcement)
        sv = service.get_source_version(actor_context, SOURCE_VERSION_ID)
        if (
            sv.id != SOURCE_VERSION_ID
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
            raise CatalogNotFoundError("Source version validation failed")

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
            raise CatalogNotFoundError("Source version digest mismatch")

        source = service.get_source(actor_context, SOURCE_ID)
        if (
            source.id != SOURCE_ID
            or source.source_key != SOURCE_KEY
            or source.title != SOURCE_TITLE
            or source.publisher_id != PUBLISHER_ID
            or source.status != "Draft"
        ):
            raise CatalogNotFoundError("Source validation failed")

        source_dto = CatalogSourceDTO(
            id=str(source.id),
            source_key=source.source_key,
            title=source.title,
            status=source.status,
        )

        prov_rows = session.scalars(
            select(CatalogSourceProvenance).where(
                CatalogSourceProvenance.source_version_id == sv.id
            )
        ).all()
        if len(prov_rows) != 1:
            raise CatalogNotFoundError("Catalog source provenance cardinality mismatch")
        prov = prov_rows[0]
        if (
            prov.id != PROVENANCE_ID
            or prov.source_version_id != SOURCE_VERSION_ID
            or prov.source_revision != 1
            or prov.mime_type != "application/pdf"
            or prov.locator != SOURCE_LOCATOR
            or prov.content_size != 1024
            or prov.recorded_by_actor_id != ACTOR_A_ID
        ):
            raise CatalogNotFoundError("Catalog source provenance validation mismatch")

        # Fixed permission proposals & decisions validation
        proposals = session.scalars(
            select(CatalogSourcePermissionProposal).where(
                CatalogSourcePermissionProposal.source_version_id == SOURCE_VERSION_ID
            )
        ).all()
        if len(proposals) != 2:
            raise CatalogNotFoundError("Catalog permission proposals cardinality mismatch")

        decisions = session.scalars(
            select(CatalogSourcePermissionDecision).where(
                CatalogSourcePermissionDecision.source_version_id == SOURCE_VERSION_ID
            )
        ).all()
        if len(decisions) != 2:
            raise CatalogNotFoundError("Catalog permission decisions cardinality mismatch")

        source_version_dto = CatalogSourceVersionDTO(
            id=str(sv.id),
            source_id=str(sv.source_id),
            edition=sv.edition,
            language=sv.language,
            official_locator=sv.official_locator,
            publication_date=sv.publication_date.isoformat() if sv.publication_date else None,
            revision=sv.revision,
            status=sv.status,
            content_digest=sv.content_digest.hex(),
            provenance_id=str(prov.id),
        )

        # 2. Requirements & Requirement Versions
        requirements_dto: list[CatalogRequirementDTO] = []
        req_defs = [
            (REQ_1_ID, REQ_1_VER_ID, REQ_1_KEY, REQ_1_OUTCOME, REQ_1_DIGEST, "1.1"),
            (REQ_2_ID, REQ_2_VER_ID, REQ_2_KEY, REQ_2_OUTCOME, REQ_2_DIGEST, "1.2"),
        ]

        for r_id, rv_id, expected_key, expected_outcome, expected_digest, expected_loc in req_defs:
            req = service.get_requirement(actor_context, r_id)
            if req.id != r_id or req.source_id != SOURCE_ID or req.requirement_key != expected_key:
                raise CatalogNotFoundError(f"Requirement {expected_key} identity mismatch")

            rv = service.get_requirement_version(actor_context, rv_id)
            if (
                rv.id != rv_id
                or rv.requirement_id != r_id
                or rv.source_id != SOURCE_ID
                or rv.source_version_id != SOURCE_VERSION_ID
                or rv.normalized_outcome != expected_outcome
                or rv.content_digest != expected_digest
                or rv.status != "Draft"
            ):
                raise CatalogNotFoundError(f"Requirement version {expected_key} mismatch")

            # Source references
            ref_rows = (
                session.execute(
                    select(CatalogRequirementSourceReference)
                    .where(CatalogRequirementSourceReference.requirement_version_id == rv_id)
                    .order_by(CatalogRequirementSourceReference.sequence)
                )
                .scalars()
                .all()
            )
            if (
                len(ref_rows) != 1
                or ref_rows[0].locator_kind != "section"
                or ref_rows[0].locator_value != expected_loc
                or ref_rows[0].sequence != 1
            ):
                raise CatalogNotFoundError(f"Requirement {expected_key} source reference mismatch")

            calc_rv_digest = compute_requirement_version_digest(
                requirement_id=rv.requirement_id,
                source_id=rv.source_id,
                source_version_id=rv.source_version_id,
                version_label=rv.version_label,
                predecessor_id=rv.predecessor_id,
                revision=rv.revision,
                normalized_outcome=rv.normalized_outcome,
                requirement_type=rv.requirement_type,
                obligated_actor=rv.obligated_actor,
                text_origin=rv.text_origin,
                customer_display_text=rv.customer_display_text,
                effective_from=rv.effective_from,
                effective_until=rv.effective_until,
                source_references=[
                    {
                        "locator_kind": ref_rows[0].locator_kind,
                        "locator_value": ref_rows[0].locator_value,
                        "sequence": ref_rows[0].sequence,
                        "source_version_id": ref_rows[0].source_version_id,
                    }
                ],
                status=rv.status,
            )
            if calc_rv_digest != rv.content_digest or calc_rv_digest != expected_digest:
                raise CatalogNotFoundError(f"Requirement {expected_key} digest mismatch")

            ref_dtos = [
                SourceReferenceDTO(
                    sequence=r.sequence,
                    locator_kind=r.locator_kind,
                    locator_value=r.locator_value,
                )
                for r in ref_rows
            ]

            requirements_dto.append(
                CatalogRequirementDTO(
                    id=str(req.id),
                    source_id=str(req.source_id),
                    requirement_key=req.requirement_key,
                    version_id=str(rv.id),
                    version_label=rv.version_label,
                    revision=rv.revision,
                    normalized_outcome=rv.normalized_outcome,
                    requirement_type=rv.requirement_type,
                    obligated_actor=rv.obligated_actor,
                    text_origin=rv.text_origin,
                    effective_from=rv.effective_from.isoformat() if rv.effective_from else None,
                    content_digest=rv.content_digest.hex(),
                    status=rv.status,
                    source_references=ref_dtos,
                )
            )

        # 3. Controls & Control Versions
        controls_dto: list[CatalogControlDTO] = []
        ctrl_defs = [
            (
                CONTROL_1_ID,
                CONTROL_1_VER_ID,
                CONTROL_1_KEY,
                CONTROL_1_DOMAIN,
                CONTROL_1_TITLE,
                CONTROL_1_OBJECTIVE,
                CONTROL_1_GUIDANCE,
                "preventive",
                "quarterly",
                "manual",
                "Security Operations",
                "foundational",
                "None",
                CTRL_1_DIGEST,
            ),
            (
                CONTROL_2_ID,
                CONTROL_2_VER_ID,
                CONTROL_2_KEY,
                CONTROL_2_DOMAIN,
                CONTROL_2_TITLE,
                CONTROL_2_OBJECTIVE,
                CONTROL_2_GUIDANCE,
                "corrective",
                "semiannual",
                "manual",
                "Infrastructure Engineering",
                "foundational",
                "None",
                CTRL_2_DIGEST,
            ),
        ]

        for (
            c_id,
            cv_id,
            exp_key,
            exp_domain,
            exp_title,
            exp_obj,
            exp_guidance,
            exp_type,
            exp_freq,
            exp_auto,
            exp_owner,
            exp_assurance,
            exp_tags_state,
            exp_digest,
        ) in ctrl_defs:
            cc = service.get_common_control(actor_context, c_id)
            if cc.id != c_id or cc.control_key != exp_key or cc.domain != exp_domain:
                raise CatalogNotFoundError(f"Control {exp_key} identity mismatch")

            cv = service.get_control_version(actor_context, cv_id)
            if (
                cv.id != cv_id
                or cv.control_id != c_id
                or cv.title != exp_title
                or cv.objective != exp_obj
                or cv.guidance != exp_guidance
                or cv.control_type != exp_type
                or cv.frequency != exp_freq
                or cv.automation_level != exp_auto
                or cv.suggested_owner_role != exp_owner
                or cv.assurance_level != exp_assurance
                or cv.tags_state != exp_tags_state
                or cv.content_digest != exp_digest
                or cv.status != "Draft"
            ):
                raise CatalogNotFoundError(f"Control version {exp_key} mismatch")

            calc_cv_digest = compute_control_version_digest(
                control_id=cv.control_id,
                version_label=cv.version_label,
                predecessor_id=cv.predecessor_id,
                revision=cv.revision,
                title=cv.title,
                objective=cv.objective,
                guidance=cv.guidance,
                control_type=cv.control_type,
                frequency=cv.frequency,
                automation_level=cv.automation_level,
                suggested_owner_role=cv.suggested_owner_role,
                assurance_level=cv.assurance_level,
                tags_state=cv.tags_state,
                tags=cv.tags,
                status=cv.status,
            )
            if calc_cv_digest != cv.content_digest or calc_cv_digest != exp_digest:
                raise CatalogNotFoundError(f"Control {exp_key} digest mismatch")

            controls_dto.append(
                CatalogControlDTO(
                    id=str(cc.id),
                    control_key=cc.control_key,
                    domain=cc.domain,
                    version_id=str(cv.id),
                    version_label=cv.version_label,
                    revision=cv.revision,
                    title=cv.title,
                    objective=cv.objective,
                    guidance=cv.guidance,
                    control_type=cv.control_type,
                    frequency=cv.frequency,
                    automation_level=cv.automation_level,
                    suggested_owner_role=cv.suggested_owner_role,
                    assurance_level=cv.assurance_level,
                    tags_state=cv.tags_state,
                    content_digest=cv.content_digest.hex(),
                    status=cv.status,
                    evidence_requirements=[],
                    assessment_procedures=[],
                )
            )

        # 4. Evidence Requirements
        evidence_dtos: list[CatalogEvidenceRequirementDTO] = []
        er_defs = [
            (
                EVID_1_VER_ID,
                CONTROL_1_ID,
                CONTROL_1_VER_ID,
                EVID_1_KEY,
                EVID_1_TITLE,
                "quarterly",
                "operating_effectiveness",
                "point_in_time",
                90,
                "Signed export or ticket showing review of elevated permissions.",
                "report",
                "reviewer_name",
                CTRL_1_DIGEST,
                EVID_1_DIGEST,
            ),
            (
                EVID_2_VER_ID,
                CONTROL_2_ID,
                CONTROL_2_VER_ID,
                EVID_2_KEY,
                EVID_2_TITLE,
                "semiannual",
                "operating_effectiveness",
                "point_in_time",
                180,
                "Log or ticket documenting test recovery from backup.",
                "log",
                "backup_timestamp",
                CTRL_2_DIGEST,
                EVID_2_DIGEST,
            ),
        ]

        for (
            er_id,
            exp_c_id,
            exp_cv_id,
            exp_key,
            exp_title,
            exp_freq,
            exp_purpose,
            exp_rule,
            exp_age,
            exp_guidance,
            exp_art,
            exp_meta,
            exp_cv_digest,
            exp_digest,
        ) in er_defs:
            er = service.get_evidence_requirement_version(actor_context, er_id)
            if (
                er.id != er_id
                or er.control_id != exp_c_id
                or er.control_version_id != exp_cv_id
                or er.requirement_key != exp_key
                or er.title != exp_title
                or er.frequency != exp_freq
                or er.assurance_purpose != exp_purpose
                or er.validity_rule != exp_rule
                or er.max_age_days != exp_age
                or er.guidance != exp_guidance
                or er.missing_data_behavior != "requires_human_review"
                or er.content_digest != exp_digest
                or er.status != "Draft"
            ):
                raise CatalogNotFoundError(f"Evidence requirement {exp_key} mismatch")

            art_rows = session.scalars(
                select(CatalogEvidenceRequirementArtifactType)
                .where(
                    CatalogEvidenceRequirementArtifactType.evidence_requirement_version_id == er_id
                )
                .order_by(CatalogEvidenceRequirementArtifactType.sequence)
            ).all()
            if (
                len(art_rows) != 1
                or art_rows[0].artifact_type != exp_art
                or art_rows[0].sequence != 1
            ):
                raise CatalogNotFoundError(f"Evidence requirement {exp_key} artifact type mismatch")

            meta_rows = session.scalars(
                select(CatalogEvidenceRequirementMetadataKey)
                .where(
                    CatalogEvidenceRequirementMetadataKey.evidence_requirement_version_id == er_id
                )
                .order_by(CatalogEvidenceRequirementMetadataKey.sequence)
            ).all()
            if (
                len(meta_rows) != 1
                or meta_rows[0].metadata_key != exp_meta
                or meta_rows[0].sequence != 1
            ):
                raise CatalogNotFoundError(f"Evidence requirement {exp_key} metadata key mismatch")

            calc_er_digest = compute_evidence_requirement_version_digest(
                control_version_id=er.control_version_id,
                control_version_digest=exp_cv_digest,
                requirement_key=er.requirement_key,
                sequence=er.sequence,
                title=er.title,
                frequency=er.frequency,
                custom_frequency=er.custom_frequency,
                scope_state=er.scope_state,
                scope_guidance=er.scope_guidance,
                assurance_purpose=er.assurance_purpose,
                validity_rule=er.validity_rule,
                max_age_days=er.max_age_days,
                guidance=er.guidance,
                artifact_types=[
                    {"artifact_type": a.artifact_type, "sequence": a.sequence} for a in art_rows
                ],
                required_metadata=[
                    {"metadata_key": m.metadata_key, "sequence": m.sequence} for m in meta_rows
                ],
                missing_data_behavior=er.missing_data_behavior,
            )
            if calc_er_digest != er.content_digest or calc_er_digest != exp_digest:
                raise CatalogNotFoundError(f"Evidence requirement {exp_key} digest mismatch")

            art_dtos = [
                ArtifactTypeDTO(artifact_type=a.artifact_type, sequence=a.sequence)
                for a in art_rows
            ]
            meta_dtos = [
                MetadataKeyDTO(metadata_key=m.metadata_key, sequence=m.sequence) for m in meta_rows
            ]

            er_dto = CatalogEvidenceRequirementDTO(
                id=str(er.id),
                control_id=str(er.control_id),
                control_version_id=str(er.control_version_id),
                requirement_key=er.requirement_key,
                sequence=er.sequence,
                title=er.title,
                frequency=er.frequency,
                scope_state=er.scope_state,
                assurance_purpose=er.assurance_purpose,
                validity_rule=er.validity_rule,
                max_age_days=er.max_age_days,
                guidance=er.guidance,
                missing_data_behavior=er.missing_data_behavior,
                artifact_types=art_dtos,
                required_metadata=meta_dtos,
                content_digest=er.content_digest.hex(),
                status=er.status,
            )
            evidence_dtos.append(er_dto)

        # Attach evidence requirement to controls
        controls_dto[0].evidence_requirements = [evidence_dtos[0]]
        controls_dto[1].evidence_requirements = [evidence_dtos[1]]

        # 5. Assessment Procedures
        procedure_dtos: list[CatalogAssessmentProcedureDTO] = []
        ap_defs = [
            (
                PROC_1_VER_ID,
                CONTROL_1_ID,
                CONTROL_1_VER_ID,
                PROC_1_KEY,
                PROC_1_TITLE,
                PROC_1_OBJECTIVE,
                "Confirm all privileged accounts have recorded approvals.",
                "Security Auditor",
                "Inspect quarterly review records for unapproved privilege grants.",
                "inspect",
                "All grants are approved and documented.",
                CTRL_1_DIGEST,
                PROC_1_DIGEST,
                EVID_1_VER_ID,
                EVID_1_DIGEST,
            ),
            (
                PROC_2_VER_ID,
                CONTROL_2_ID,
                CONTROL_2_VER_ID,
                PROC_2_KEY,
                PROC_2_TITLE,
                PROC_2_OBJECTIVE,
                "Confirm recovery verification completed successfully within RTO.",
                "Systems Auditor",
                "Inspect restore logs to verify checksum match and RTO.",
                "inspect",
                "Restoration verified complete and matching source data.",
                CTRL_2_DIGEST,
                PROC_2_DIGEST,
                EVID_2_VER_ID,
                EVID_2_DIGEST,
            ),
        ]

        for (
            ap_id,
            exp_c_id,
            exp_cv_id,
            exp_key,
            exp_title,
            exp_obj,
            exp_decision,
            exp_qual,
            exp_step_inst,
            exp_step_kind,
            exp_step_out,
            exp_cv_digest,
            exp_digest,
            exp_er_id,
            exp_er_digest,
        ) in ap_defs:
            ap = service.get_assessment_procedure_version(actor_context, ap_id)
            if (
                ap.id != ap_id
                or ap.control_id != exp_c_id
                or ap.control_version_id != exp_cv_id
                or ap.procedure_key != exp_key
                or ap.title != exp_title
                or ap.objective != exp_obj
                or ap.decision_guidance != exp_decision
                or ap.assessor_qualifications != exp_qual
                or ap.missing_data_behavior != "requires_human_review"
                or ap.content_digest != exp_digest
                or ap.status != "Draft"
            ):
                raise CatalogNotFoundError(f"Assessment procedure {exp_key} mismatch")

            st_rows = session.scalars(
                select(CatalogAssessmentProcedureStep)
                .where(CatalogAssessmentProcedureStep.assessment_procedure_version_id == ap_id)
                .order_by(CatalogAssessmentProcedureStep.sequence)
            ).all()
            if (
                len(st_rows) != 1
                or st_rows[0].sequence != 1
                or st_rows[0].instruction != exp_step_inst
                or st_rows[0].step_kind != exp_step_kind
                or st_rows[0].expected_output != exp_step_out
            ):
                raise CatalogNotFoundError(f"Assessment procedure {exp_key} step mismatch")

            lk_rows = session.scalars(
                select(CatalogAssessmentProcedureEvidenceRequirement)
                .where(
                    CatalogAssessmentProcedureEvidenceRequirement.assessment_procedure_version_id
                    == ap_id
                )
                .order_by(CatalogAssessmentProcedureEvidenceRequirement.sequence)
            ).all()
            if (
                len(lk_rows) != 1
                or lk_rows[0].sequence != 1
                or lk_rows[0].evidence_requirement_version_id != exp_er_id
            ):
                raise CatalogNotFoundError(f"Assessment procedure {exp_key} evidence link mismatch")

            calc_ap_digest = compute_assessment_procedure_version_digest(
                control_version_id=ap.control_version_id,
                control_version_digest=exp_cv_digest,
                procedure_key=ap.procedure_key,
                sequence=ap.sequence,
                title=ap.title,
                objective=ap.objective,
                sample_guidance=ap.sample_guidance,
                scope_guidance=ap.scope_guidance,
                decision_guidance=ap.decision_guidance,
                assessor_qualifications=ap.assessor_qualifications,
                steps=[
                    {
                        "expected_output": st_rows[0].expected_output,
                        "instruction": st_rows[0].instruction,
                        "sequence": st_rows[0].sequence,
                        "step_kind": st_rows[0].step_kind,
                    }
                ],
                evidence_requirements=[
                    {
                        "content_digest": exp_er_digest,
                        "id": lk_rows[0].evidence_requirement_version_id,
                        "sequence": lk_rows[0].sequence,
                    }
                ],
                missing_data_behavior=ap.missing_data_behavior,
            )
            if calc_ap_digest != ap.content_digest or calc_ap_digest != exp_digest:
                raise CatalogNotFoundError(f"Assessment procedure {exp_key} digest mismatch")

            steps_dtos = [
                ProcedureStepDTO(
                    sequence=st.sequence,
                    step_kind=st.step_kind,
                    instruction=st.instruction,
                    expected_output=st.expected_output,
                )
                for st in st_rows
            ]
            er_ids = [str(lk_rows[0].evidence_requirement_version_id)]

            ap_dto = CatalogAssessmentProcedureDTO(
                id=str(ap.id),
                control_id=str(ap.control_id),
                control_version_id=str(ap.control_version_id),
                procedure_key=ap.procedure_key,
                sequence=ap.sequence,
                title=ap.title,
                objective=ap.objective,
                decision_guidance=ap.decision_guidance,
                assessor_qualifications=ap.assessor_qualifications,
                missing_data_behavior=ap.missing_data_behavior,
                steps=steps_dtos,
                evidence_requirement_ids=er_ids,
                content_digest=ap.content_digest.hex(),
                status=ap.status,
            )
            procedure_dtos.append(ap_dto)

        # Attach procedure to control DTOs as well
        controls_dto[0].assessment_procedures = [procedure_dtos[0]]
        controls_dto[1].assessment_procedures = [procedure_dtos[1]]

        # 6. Mappings
        mappings_dto: list[CatalogMappingDTO] = []
        map_defs = [
            (
                MAPPING_1_ID,
                MAPPING_1_VER_ID,
                MAPPING_1_KEY,
                REQ_1_ID,
                CONTROL_1_ID,
                REQ_1_VER_ID,
                CONTROL_1_VER_ID,
                REQ_1_DIGEST,
                CTRL_1_DIGEST,
                MAP_1_DIGEST,
                "Full",
                MAPPING_1_RATIONALE,
                MAPPING_1_COVERED,
                None,
                "high",
            ),
            (
                MAPPING_2_ID,
                MAPPING_2_VER_ID,
                MAPPING_2_KEY,
                REQ_2_ID,
                CONTROL_2_ID,
                REQ_2_VER_ID,
                CONTROL_2_VER_ID,
                REQ_2_DIGEST,
                CTRL_2_DIGEST,
                MAP_2_DIGEST,
                "Partial",
                MAPPING_2_RATIONALE,
                MAPPING_2_COVERED,
                MAPPING_2_EXCLUDED,
                "medium",
            ),
        ]

        for (
            m_id,
            mv_id,
            exp_key,
            exp_req_id,
            exp_c_id,
            exp_rv_id,
            exp_cv_id,
            exp_rv_digest,
            exp_cv_digest,
            exp_digest,
            exp_type,
            exp_rationale,
            exp_covered,
            exp_excluded,
            exp_conf,
        ) in map_defs:
            m_parent = session.scalar(
                select(CatalogRequirementControlMapping).where(
                    CatalogRequirementControlMapping.id == m_id
                )
            )
            if (
                m_parent is None
                or m_parent.mapping_key != exp_key
                or m_parent.requirement_id != exp_req_id
                or m_parent.control_id != exp_c_id
                or m_parent.status != "Draft"
            ):
                raise CatalogNotFoundError(f"Mapping parent entity {exp_key} mismatch")

            mv = service.get_mapping_version(actor_context, mv_id)
            if (
                mv.id != mv_id
                or mv.mapping_id != m_id
                or mv.requirement_id != exp_req_id
                or mv.control_id != exp_c_id
                or mv.requirement_version_id != exp_rv_id
                or mv.control_version_id != exp_cv_id
                or mv.content_digest != exp_digest
                or mv.mapping_type != exp_type
                or mv.rationale != exp_rationale
                or mv.covered_dimensions != exp_covered
                or mv.excluded_dimensions != exp_excluded
                or mv.confidence != exp_conf
                or mv.source_basis != "expert_analysis"
                or mv.status != "Draft"
            ):
                raise CatalogNotFoundError(f"Mapping version {exp_key} mismatch")

            calc_mv_digest = compute_mapping_version_digest(
                mapping_id=mv.mapping_id,
                requirement_id=mv.requirement_id,
                control_id=mv.control_id,
                requirement_version_id=mv.requirement_version_id,
                control_version_id=mv.control_version_id,
                requirement_version_revision=1,
                requirement_version_digest=exp_rv_digest,
                control_version_revision=1,
                control_version_digest=exp_cv_digest,
                version_label="1.0.0",
                predecessor_id=None,
                revision=1,
                mapping_type=mv.mapping_type,
                rationale=mv.rationale,
                covered_dimensions=mv.covered_dimensions,
                excluded_dimensions=mv.excluded_dimensions,
                conditions=None,
                source_basis=mv.source_basis,
                confidence=mv.confidence,
                review_state="Draft",
                status="Draft",
            )
            if calc_mv_digest != mv.content_digest or calc_mv_digest != exp_digest:
                raise CatalogNotFoundError(f"Mapping version {exp_key} digest mismatch")

            mappings_dto.append(
                CatalogMappingDTO(
                    id=str(mv.mapping_id),
                    mapping_key=m_parent.mapping_key,
                    requirement_id=str(mv.requirement_id),
                    control_id=str(mv.control_id),
                    requirement_version_id=str(mv.requirement_version_id),
                    control_version_id=str(mv.control_version_id),
                    version_label=mv.version_label,
                    revision=mv.revision,
                    mapping_type=mv.mapping_type,
                    rationale=mv.rationale,
                    covered_dimensions=mv.covered_dimensions,
                    excluded_dimensions=mv.excluded_dimensions,
                    conditions=mv.conditions,
                    source_basis=mv.source_basis,
                    confidence=mv.confidence,
                    review_state=mv.review_state,
                    content_digest=mv.content_digest.hex(),
                    status=mv.status,
                )
            )

        if getattr(service, "last_denial_audit_error", None) is not None:
            raise AuditPersistenceError("Catalog assurance audit persistence failure")

        return CatalogDemoGraphResponse(
            demo_id="catalog-demo-v1",
            synthetic=True,
            status="Draft",
            source=source_dto,
            source_version=source_version_dto,
            requirements=requirements_dto,
            controls=controls_dto,
            mappings=mappings_dto,
            evidence_requirements=evidence_dtos,
            assessment_procedures=procedure_dtos,
        )

    except AuditPersistenceError:
        raise
    except CatalogPermissionDeniedError as exc:
        if getattr(service, "last_denial_audit_error", None) is not None:
            raise AuditPersistenceError("Catalog assurance audit persistence failure") from exc
        raise
    except CatalogSecurityError as exc:
        if getattr(service, "last_denial_audit_error", None) is not None:
            raise AuditPersistenceError("Catalog assurance audit persistence failure") from exc
        if _is_assurance_aggregate_corruption(exc):
            raise CatalogNotFoundError("Synthetic catalog demo graph is unavailable") from exc
        raise
    except CatalogNotFoundError as exc:
        if getattr(service, "last_denial_audit_error", None) is not None:
            raise AuditPersistenceError("Catalog assurance audit persistence failure") from exc
        raise
    except Exception as exc:
        if getattr(service, "last_denial_audit_error", None) is not None:
            raise AuditPersistenceError("Catalog assurance audit persistence failure") from exc
        raise
