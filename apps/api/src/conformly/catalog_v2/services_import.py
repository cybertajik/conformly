"""Durable import adapter ledger, reconciliation lifecycle, and concurrency protocol.

Implements the physical contract from DOC-V2-031 / D-V2-007:
- Admission of sanitized ImportItem inventories into catalog_import_batches / catalog_import_inputs.
- Strict validation against immutable admitted fingerprints on execute_batch.
- Exact-reuse matching via catalog_import_reuse_ledger (and routing stale/changed to NeedsConflictReview).
- Controlled reconciliation sealing via public.catalog_seal_import_batch on PostgreSQL.
- Idempotent concurrent admission and idempotent concurrent sealing.
- Comprehensive lock discipline (DOC-V2-031 Section 31 order) with rollback-before-sleep.
- Pure deterministic workflow without autonomous agent decisions.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogCapability,
    CatalogConflictError,
    CatalogNotFoundError,
    CatalogPermissionDeniedError,
    CatalogSecurityError,
    CatalogValidationError,
    verify_catalog_actor,
)
from conformly.catalog_v2.audit import (
    DatabaseCommittedDeniedAuditSink,
    DeniedAuditSink,
    LoggingDeniedAuditSink,
    append_catalog_audit_event,
    record_catalog_event_intent,
)
from conformly.catalog_v2.digest import compute_content_digest
from conformly.catalog_v2.import_adapter import (
    ADAPTER_VERSION,
    DEFERRED_INPUT_TYPES,
    ImportDisposition,
    ImportItem,
    ImportPayloadError,
    _validate_batch_envelope,
    _validate_item,
)
from conformly.catalog_v2.models import (
    CatalogCommonControl,
    CatalogControlVersion,
    CatalogEventIntent,
    CatalogEvidenceRequirementVersion,
    CatalogMappingVersion,
    CatalogPack,
    CatalogPackVersion,
    CatalogRequirement,
    CatalogRequirementControlMapping,
    CatalogRequirementVersion,
    CatalogSourceVersion,
)
from conformly.catalog_v2.models_import import (
    CatalogImportBatch,
    CatalogImportInput,
    CatalogImportReconciliationManifest,
    CatalogImportReuseLedger,
)
from conformly.catalog_v2.permissions import (
    DEFAULT_SCOPE_KEY,
    has_effective_permission,
)
from conformly.catalog_v2.service import CatalogDraftService
from conformly.catalog_v2.service_assurance import (
    AssessmentProcedureVersionSnapshot,
    CatalogAssuranceDraftService,
    EvidenceRequirementVersionSnapshot,
    _normalize_digest,
)

BATCH_EXECUTION_DEADLINE_SECONDS = 300.0
ALLOWED_LOCATOR_KINDS = frozenset(
    {"article", "section", "paragraph", "clause", "criterion", "table", "annex", "page"}
)


# ImportPayloadError is imported from conformly.catalog_v2.import_adapter


@dataclass(frozen=True)
class AdmissionResult:
    batch: CatalogImportBatch
    replayed: bool


@dataclass(frozen=True)
class ReuseResult:
    disposition: ImportDisposition
    ledger: CatalogImportReuseLedger | None


class ConservativeImportService:
    """Durable execution service for the conservative catalog import adapter."""

    def __init__(
        self,
        session: Session,
        denied_audit_sink: DeniedAuditSink | None = None,
    ) -> None:
        self.session = session
        if denied_audit_sink is not None:
            self.denied_sink = denied_audit_sink
        elif session.bind is not None:
            self.denied_sink = DatabaseCommittedDeniedAuditSink(session.bind)
        else:
            self.denied_sink = LoggingDeniedAuditSink()

    def _record_denial_safe(
        self,
        actor_id: UUID | None,
        operation: str,
        reason: str,
        request_key: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> None:
        try:
            self.session.rollback()
        except Exception:
            pass
        if actor_id is not None:
            try:
                self.denied_sink.record_denial(
                    actor_id=actor_id,
                    operation=operation,
                    reason_code=reason,
                    request_key=request_key,
                    resource_type=resource_type,
                    resource_id=resource_id,
                )
            except Exception:
                pass

    def _db_time(self) -> datetime:
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            row = self.session.execute(text("SELECT clock_timestamp()")).first()
            if row and row[0]:
                return cast(datetime, row[0]).astimezone(UTC)
        return datetime.now(UTC)

    # -----------------------------------------------------------------------
    # Admission
    # -----------------------------------------------------------------------

    def admit_batch(
        self,
        context: CatalogActorContext,
        batch_key: str,
        items: list[ImportItem],
    ) -> AdmissionResult:
        db_time = self._db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogSecurityError as exc:
            self._record_denial_safe(
                context.actor_id if context else None,
                "admit_batch_capability_preflight",
                type(exc).__name__,
                f"import:batch_key:{batch_key}",
            )
            raise
        _validate_batch_envelope(items)
        if not batch_key or len(batch_key) > 128:
            raise ValueError("INVALID_BATCH_KEY")

        sorted_items = sorted(items, key=lambda entry: entry.sequence)
        payload = [
            {
                "fingerprint": item.fingerprint,
                "input_type": item.input_type,
                "origin_id": item.origin_id,
                "origin_namespace": item.origin_namespace,
                "sequence": item.sequence,
            }
            for item in sorted_items
        ]
        payload_digest = compute_content_digest(payload)
        batch_fingerprint = compute_content_digest(
            {
                "adapter_version": ADAPTER_VERSION,
                "batch_key": batch_key,
                "payload_digest": payload_digest,
            }
        )

        existing = self.session.scalar(
            select(CatalogImportBatch)
            .where(CatalogImportBatch.batch_key == batch_key)
            .with_for_update()
        )
        if existing is not None:
            if (
                existing.batch_fingerprint != batch_fingerprint
                or existing.payload_digest != payload_digest
            ):
                raise CatalogConflictError("CONFLICT_CHANGED_BATCH_CONTENT")
            return AdmissionResult(existing, replayed=True)

        # Finding 6: Entire batch insertion is wrapped in try-except IntegrityError
        # ensuring concurrent first admission replays idempotently without unique key errors
        try:
            batch = CatalogImportBatch(
                batch_key=batch_key,
                batch_fingerprint=batch_fingerprint,
                adapter_version=ADAPTER_VERSION,
                total_inputs=len(items),
                payload_digest=payload_digest,
            )
            self.session.add(batch)
            self.session.flush()
            self.session.add_all(
                [
                    CatalogImportInput(
                        batch_id=batch.id,
                        sequence=item.sequence,
                        input_type=item.input_type,
                        origin_namespace=item.origin_namespace,
                        origin_id=item.origin_id,
                        input_fingerprint=item.fingerprint,
                    )
                    for item in items
                ]
            )
            self.session.commit()
            return AdmissionResult(batch, replayed=False)
        except IntegrityError:
            self.session.rollback()
            existing = self.session.scalar(
                select(CatalogImportBatch).where(CatalogImportBatch.batch_key == batch_key)
            )
            if existing is not None:
                if (
                    existing.batch_fingerprint != batch_fingerprint
                    or existing.payload_digest != payload_digest
                ):
                    raise CatalogConflictError("CONFLICT_CHANGED_BATCH_CONTENT")
                return AdmissionResult(existing, replayed=True)
            raise

    # -----------------------------------------------------------------------
    # Reuse Resolution
    # -----------------------------------------------------------------------

    def resolve_reuse(self, item: ImportItem) -> ReuseResult | None:
        """Resolve exact match or changed origin content from reuse ledger."""
        target_entity_type = {
            "Requirement": "RequirementVersion",
            "CommonControl": "ControlVersion",
            "Mapping": "MappingVersion",
            "Pack": "PackVersion",
            "EvidenceRequirement": "EvidenceRequirementVersion",
            "AssessmentProcedure": "AssessmentProcedureVersion",
        }.get(item.input_type)
        if not target_entity_type:
            return None

        ledger = self.session.scalar(
            select(CatalogImportReuseLedger).where(
                CatalogImportReuseLedger.origin_namespace == item.origin_namespace,
                CatalogImportReuseLedger.origin_id == item.origin_id,
                CatalogImportReuseLedger.adapter_version == ADAPTER_VERSION,
                CatalogImportReuseLedger.target_entity_type == target_entity_type,
            )
        )
        if ledger is None:
            return None

        if ledger.input_fingerprint == item.fingerprint:
            return ReuseResult(ImportDisposition.REUSED_EXACT, ledger)
        return ReuseResult(ImportDisposition.NEEDS_CONFLICT_REVIEW, ledger)

    def _verify_and_record_assurance_reuse(
        self,
        context: CatalogActorContext,
        batch: CatalogImportBatch,
        input_row: CatalogImportInput,
        item: ImportItem,
        ledger: CatalogImportReuseLedger,
        assurance_service: CatalogAssuranceDraftService,
        db_time: datetime,
    ) -> None:
        parent_res = self._resolve_parent_control(batch.id, input_row.sequence, item.payload)
        if isinstance(parent_res[0], ImportDisposition):
            disp, reason = parent_res
            self._record_input_disposition(
                context,
                input_row,
                disp,
                reason,
                db_time,
                target_entity_type=ledger.target_entity_type,
                target_version_id=ledger.target_version_id,
                target_revision=ledger.target_revision,
                target_digest=ledger.target_digest,
            )
            return

        resolved_ctrl_id, _ = parent_res

        # Call WP-06B aggregate read
        # Strict Exception Separation: CatalogSecurityError propagates unhandled to abort/interrupt
        snapshot: EvidenceRequirementVersionSnapshot | AssessmentProcedureVersionSnapshot | None = (
            None
        )
        try:
            if ledger.target_entity_type == "EvidenceRequirementVersion":
                snapshot = assurance_service.get_evidence_requirement_version(
                    context, ledger.target_version_id
                )
            elif ledger.target_entity_type == "AssessmentProcedureVersion":
                snapshot = assurance_service.get_assessment_procedure_version(
                    context, ledger.target_version_id
                )
            else:
                self._record_input_disposition(
                    context,
                    input_row,
                    ImportDisposition.NEEDS_CONFLICT_REVIEW,
                    "CONFLICT_STALE_REUSE_TARGET",
                    db_time,
                    target_entity_type=ledger.target_entity_type,
                    target_version_id=ledger.target_version_id,
                    target_revision=ledger.target_revision,
                    target_digest=ledger.target_digest,
                )
                return
        except (CatalogNotFoundError, CatalogValidationError):
            self._record_input_disposition(
                context,
                input_row,
                ImportDisposition.NEEDS_CONFLICT_REVIEW,
                "CONFLICT_STALE_REUSE_TARGET",
                db_time,
                target_entity_type=ledger.target_entity_type,
                target_version_id=ledger.target_version_id,
                target_revision=ledger.target_revision,
                target_digest=ledger.target_digest,
            )
            return

        if snapshot is None:
            self._record_input_disposition(
                context,
                input_row,
                ImportDisposition.NEEDS_CONFLICT_REVIEW,
                "CONFLICT_STALE_REUSE_TARGET",
                db_time,
                target_entity_type=ledger.target_entity_type,
                target_version_id=ledger.target_version_id,
                target_revision=ledger.target_revision,
                target_digest=ledger.target_digest,
            )
            return

        # Snapshot invariant checks
        if snapshot.control_version_id != resolved_ctrl_id:
            self._record_input_disposition(
                context,
                input_row,
                ImportDisposition.NEEDS_CONFLICT_REVIEW,
                "CONFLICT_REUSE_PARENT_MISMATCH",
                db_time,
                target_entity_type=ledger.target_entity_type,
                target_version_id=ledger.target_version_id,
                target_revision=ledger.target_revision,
                target_digest=ledger.target_digest,
            )
            return

        if (
            snapshot.id != ledger.target_version_id
            or snapshot.sequence != ledger.target_revision
            or snapshot.content_digest != ledger.target_digest
        ):
            self._record_input_disposition(
                context,
                input_row,
                ImportDisposition.NEEDS_CONFLICT_REVIEW,
                "CONFLICT_STALE_REUSE_TARGET",
                db_time,
                target_entity_type=ledger.target_entity_type,
                target_version_id=ledger.target_version_id,
                target_revision=ledger.target_revision,
                target_digest=ledger.target_digest,
            )
            return

        # Exact match verified
        self._record_input_disposition(
            context,
            input_row,
            ImportDisposition.REUSED_EXACT,
            "REUSE_EXACT_MATCH",
            db_time,
            target_entity_type=ledger.target_entity_type,
            target_version_id=ledger.target_version_id,
            target_revision=ledger.target_revision,
            target_digest=ledger.target_digest,
        )

    def _resolve_parent_control(
        self,
        batch_id: UUID,
        current_sequence: int,
        payload: dict[str, Any],
    ) -> tuple[UUID, bytes] | tuple[ImportDisposition, str]:
        loc_uuid_raw = payload.get("control_version_id")
        loc_uuid: UUID | None = None
        if loc_uuid_raw:
            try:
                loc_uuid = UUID(str(loc_uuid_raw))
            except ValueError:
                return (ImportDisposition.REJECTED, "INVALID_PARENT_TARGET_PIN")

        loc_seq = payload.get("parent_control_sequence")
        ns = payload.get("parent_control_origin_namespace")
        oid = payload.get("parent_control_origin_id")
        has_origin = bool(ns and oid)

        if not (loc_uuid or loc_seq is not None or has_origin):
            return (ImportDisposition.REJECTED, "PARENT_CONTROL_LOCATOR_REQUIRED")

        resolved_from_seq: UUID | None = None
        if loc_seq is not None:
            row = self.session.scalar(
                select(CatalogImportInput).where(
                    CatalogImportInput.batch_id == batch_id,
                    CatalogImportInput.sequence == loc_seq,
                )
            )
            if row is None or row.disposition == ImportDisposition.PENDING:
                return (ImportDisposition.NEEDS_DEPENDENCY, "DEPENDENCY_ORDERING_VIOLATION")
            if row.target_entity_type != "ControlVersion" or row.target_version_id is None:
                return (ImportDisposition.REJECTED, "INVALID_PARENT_TARGET_PIN")
            resolved_from_seq = row.target_version_id

        resolved_from_origin: UUID | None = None
        if has_origin:
            earlier_input = self.session.scalar(
                select(CatalogImportInput).where(
                    CatalogImportInput.batch_id == batch_id,
                    CatalogImportInput.origin_namespace == ns,
                    CatalogImportInput.origin_id == oid,
                    CatalogImportInput.sequence < current_sequence,
                )
            )
            if earlier_input is not None:
                if earlier_input.disposition == ImportDisposition.PENDING:
                    return (ImportDisposition.NEEDS_DEPENDENCY, "DEPENDENCY_ORDERING_VIOLATION")
                if (
                    earlier_input.target_entity_type != "ControlVersion"
                    or earlier_input.target_version_id is None
                ):
                    return (ImportDisposition.REJECTED, "INVALID_PARENT_TARGET_PIN")
                resolved_from_origin = earlier_input.target_version_id
            else:
                ledger_row = self.session.scalar(
                    select(CatalogImportReuseLedger).where(
                        CatalogImportReuseLedger.origin_namespace == ns,
                        CatalogImportReuseLedger.origin_id == oid,
                        CatalogImportReuseLedger.adapter_version == ADAPTER_VERSION,
                        CatalogImportReuseLedger.target_entity_type == "ControlVersion",
                    )
                )
                if ledger_row is None:
                    return (ImportDisposition.NEEDS_DEPENDENCY, "PARENT_CONTROL_ORIGIN_NOT_FOUND")
                resolved_from_origin = ledger_row.target_version_id

        # Contradiction checks
        if loc_uuid and resolved_from_seq and loc_uuid != resolved_from_seq:
            return (ImportDisposition.REJECTED, "CONFLICT_PARENT_CONTROL_LOCATOR_MISMATCH")
        if loc_uuid and resolved_from_origin and loc_uuid != resolved_from_origin:
            return (ImportDisposition.REJECTED, "CONFLICT_PARENT_CONTROL_LOCATOR_MISMATCH")
        if resolved_from_seq and resolved_from_origin and resolved_from_seq != resolved_from_origin:
            return (ImportDisposition.REJECTED, "CONFLICT_PARENT_CONTROL_LOCATOR_MISMATCH")

        resolved_ctrl_id = loc_uuid or resolved_from_seq or resolved_from_origin
        if resolved_ctrl_id is None:
            return (ImportDisposition.REJECTED, "PARENT_CONTROL_LOCATOR_REQUIRED")

        parent_ctrl = self.session.get(CatalogControlVersion, resolved_ctrl_id)
        if parent_ctrl is None:
            return (ImportDisposition.NEEDS_DEPENDENCY, "PARENT_CONTROL_NOT_FOUND")
        if parent_ctrl.status != "Draft":
            return (ImportDisposition.REJECTED, "PARENT_CONTROL_NOT_DRAFT")

        expected_digest = payload.get("expected_control_digest")
        if expected_digest is not None:
            try:
                norm_exp = _normalize_digest(expected_digest, "expected_control_digest")
            except CatalogValidationError:
                return (ImportDisposition.REJECTED, "CONFLICT_PARENT_CONTROL_DIGEST_MISMATCH")
            if norm_exp != parent_ctrl.content_digest:
                return (ImportDisposition.REJECTED, "CONFLICT_PARENT_CONTROL_DIGEST_MISMATCH")
            derived_ctrl_digest = norm_exp
        else:
            derived_ctrl_digest = parent_ctrl.content_digest

        return (resolved_ctrl_id, derived_ctrl_digest)

    def _resolve_linked_evidence_requirements(
        self,
        batch_id: UUID,
        current_sequence: int,
        parent_control_id: UUID,
        evidence_requirements_payload: list[dict[str, Any]],
    ) -> list[dict[str, Any]] | tuple[ImportDisposition, str]:
        cleaned_links: list[dict[str, Any]] = []
        for idx, link in enumerate(evidence_requirements_payload, start=1):
            loc_id_raw = link.get("id") or link.get("evidence_requirement_version_id")
            loc_uuid: UUID | None = None
            if loc_id_raw:
                try:
                    loc_uuid = UUID(str(loc_id_raw))
                except ValueError:
                    return (ImportDisposition.REJECTED, "INVALID_LINKED_ER_TARGET_PIN")

            loc_seq = link.get("evidence_requirement_sequence")
            ns = link.get("evidence_requirement_origin_namespace")
            oid = link.get("evidence_requirement_origin_id")
            has_origin = bool(ns and oid)

            resolved_from_seq: UUID | None = None
            if loc_seq is not None:
                row = self.session.scalar(
                    select(CatalogImportInput).where(
                        CatalogImportInput.batch_id == batch_id,
                        CatalogImportInput.sequence == loc_seq,
                    )
                )
                if row is None or row.disposition == ImportDisposition.PENDING:
                    return (ImportDisposition.NEEDS_DEPENDENCY, "DEPENDENCY_ORDERING_VIOLATION")
                if (
                    row.target_entity_type != "EvidenceRequirementVersion"
                    or row.target_version_id is None
                ):
                    return (ImportDisposition.REJECTED, "INVALID_LINKED_ER_TARGET_PIN")
                resolved_from_seq = row.target_version_id

            resolved_from_origin: UUID | None = None
            if has_origin:
                earlier_input = self.session.scalar(
                    select(CatalogImportInput).where(
                        CatalogImportInput.batch_id == batch_id,
                        CatalogImportInput.origin_namespace == ns,
                        CatalogImportInput.origin_id == oid,
                        CatalogImportInput.sequence < current_sequence,
                    )
                )
                if earlier_input is not None:
                    if earlier_input.disposition == ImportDisposition.PENDING:
                        return (ImportDisposition.NEEDS_DEPENDENCY, "DEPENDENCY_ORDERING_VIOLATION")
                    if (
                        earlier_input.target_entity_type != "EvidenceRequirementVersion"
                        or earlier_input.target_version_id is None
                    ):
                        return (ImportDisposition.REJECTED, "INVALID_LINKED_ER_TARGET_PIN")
                    resolved_from_origin = earlier_input.target_version_id
                else:
                    ledger_row = self.session.scalar(
                        select(CatalogImportReuseLedger).where(
                            CatalogImportReuseLedger.origin_namespace == ns,
                            CatalogImportReuseLedger.origin_id == oid,
                            CatalogImportReuseLedger.adapter_version == ADAPTER_VERSION,
                            CatalogImportReuseLedger.target_entity_type
                            == "EvidenceRequirementVersion",
                        )
                    )
                    if ledger_row is None:
                        return (
                            ImportDisposition.NEEDS_DEPENDENCY,
                            "LINKED_EVIDENCE_REQUIREMENT_UNRESOLVED",
                        )
                    resolved_from_origin = ledger_row.target_version_id

            # Contradiction checks
            if loc_uuid and resolved_from_seq and loc_uuid != resolved_from_seq:
                return (ImportDisposition.REJECTED, "CONFLICT_LINKED_ER_LOCATOR_MISMATCH")
            if loc_uuid and resolved_from_origin and loc_uuid != resolved_from_origin:
                return (ImportDisposition.REJECTED, "CONFLICT_LINKED_ER_LOCATOR_MISMATCH")
            if (
                resolved_from_seq
                and resolved_from_origin
                and resolved_from_seq != resolved_from_origin
            ):
                return (ImportDisposition.REJECTED, "CONFLICT_LINKED_ER_LOCATOR_MISMATCH")

            resolved_er_id = loc_uuid or resolved_from_seq or resolved_from_origin
            if resolved_er_id is None:
                return (ImportDisposition.REJECTED, "LINKED_EVIDENCE_REQUIREMENT_LOCATOR_REQUIRED")

            er_ver = self.session.get(CatalogEvidenceRequirementVersion, resolved_er_id)
            if er_ver is None:
                return (
                    ImportDisposition.NEEDS_DEPENDENCY,
                    "LINKED_EVIDENCE_REQUIREMENT_UNRESOLVED",
                )

            # Parent alignment check
            if er_ver.control_version_id != parent_control_id:
                return (ImportDisposition.REJECTED, "CROSS_CONTROL_LINK_FORBIDDEN")

            # Digest derivation / verification
            supp_digest = link.get("content_digest")
            if supp_digest is not None:
                try:
                    norm_supp = _normalize_digest(supp_digest, "content_digest")
                except CatalogValidationError:
                    return (
                        ImportDisposition.NEEDS_CONFLICT_REVIEW,
                        "LINKED_EVIDENCE_REQUIREMENT_DIGEST_MISMATCH",
                    )
                if norm_supp != er_ver.content_digest:
                    return (
                        ImportDisposition.NEEDS_CONFLICT_REVIEW,
                        "LINKED_EVIDENCE_REQUIREMENT_DIGEST_MISMATCH",
                    )
                er_digest = norm_supp
            else:
                er_digest = er_ver.content_digest

            cleaned_links.append(
                {
                    "id": resolved_er_id,
                    "content_digest": er_digest,
                    "sequence": idx,
                }
            )
        return cleaned_links

    def _process_evidence_requirement(
        self,
        context: CatalogActorContext,
        req_key: str,
        batch: CatalogImportBatch,
        input_row: CatalogImportInput,
        item: ImportItem,
        assurance_service: CatalogAssuranceDraftService,
        db_time: datetime,
    ) -> None:
        parent_res = self._resolve_parent_control(batch.id, input_row.sequence, item.payload)
        if isinstance(parent_res[0], ImportDisposition):
            disp, reason = parent_res
            self._record_input_disposition(context, input_row, disp, reason, db_time)
            return

        resolved_ctrl_id, derived_ctrl_digest = parent_res

        snapshot = assurance_service.create_evidence_requirement_version(
            context=context,
            request_key=f"import:{batch.id}:{item.sequence}",
            control_version_id=resolved_ctrl_id,
            expected_control_digest=derived_ctrl_digest,
            requirement_key=item.payload["requirement_key"],
            title=item.payload["title"],
            frequency=item.payload["frequency"],
            custom_frequency=item.payload.get("custom_frequency"),
            scope_state=item.payload["scope_state"],
            scope_guidance=item.payload.get("scope_guidance"),
            assurance_purpose=item.payload["assurance_purpose"],
            validity_rule=item.payload["validity_rule"],
            max_age_days=item.payload.get("max_age_days"),
            guidance=item.payload.get("guidance"),
            artifact_types=item.payload["artifact_types"],
            required_metadata=item.payload.get("required_metadata", []),
        )

        reuse = CatalogImportReuseLedger(
            origin_namespace=item.origin_namespace,
            origin_id=item.origin_id,
            adapter_version=ADAPTER_VERSION,
            input_fingerprint=item.fingerprint,
            target_entity_type="EvidenceRequirementVersion",
            target_version_id=snapshot.id,
            target_revision=snapshot.sequence,
            target_digest=snapshot.content_digest,
            created_at=db_time,
        )
        self.session.add(reuse)

        self._record_input_disposition(
            context,
            input_row,
            ImportDisposition.IMPORTED_DRAFT,
            "DRAFT_CREATED_SUCCESS",
            db_time,
            target_entity_type="EvidenceRequirementVersion",
            target_version_id=snapshot.id,
            target_revision=snapshot.sequence,
            target_digest=snapshot.content_digest,
        )

    def _process_assessment_procedure(
        self,
        context: CatalogActorContext,
        req_key: str,
        batch: CatalogImportBatch,
        input_row: CatalogImportInput,
        item: ImportItem,
        assurance_service: CatalogAssuranceDraftService,
        db_time: datetime,
    ) -> None:
        parent_res = self._resolve_parent_control(batch.id, input_row.sequence, item.payload)
        if isinstance(parent_res[0], ImportDisposition):
            disp, reason = parent_res
            self._record_input_disposition(context, input_row, disp, reason, db_time)
            return

        resolved_ctrl_id, derived_ctrl_digest = parent_res

        raw_er_links = item.payload.get("evidence_requirements", [])
        cleaned_links = self._resolve_linked_evidence_requirements(
            batch.id, input_row.sequence, resolved_ctrl_id, raw_er_links
        )
        if not isinstance(cleaned_links, list):
            disp, reason = cleaned_links
            self._record_input_disposition(context, input_row, disp, reason, db_time)
            return

        cleaned_steps = [
            {
                "sequence": step["sequence"],
                "step_kind": step["step_kind"],
                "instruction": step["instruction"],
                "expected_output": step.get("expected_output"),
            }
            for step in item.payload.get("steps", [])
        ]

        snapshot = assurance_service.create_assessment_procedure_version(
            context=context,
            request_key=f"import:{batch.id}:{item.sequence}",
            control_version_id=resolved_ctrl_id,
            expected_control_digest=derived_ctrl_digest,
            procedure_key=item.payload["procedure_key"],
            title=item.payload["title"],
            objective=item.payload["objective"],
            sample_guidance=item.payload.get("sample_guidance"),
            scope_guidance=item.payload.get("scope_guidance"),
            decision_guidance=item.payload["decision_guidance"],
            assessor_qualifications=item.payload.get("assessor_qualifications"),
            steps=cleaned_steps,
            evidence_requirements=cleaned_links,
        )

        reuse = CatalogImportReuseLedger(
            origin_namespace=item.origin_namespace,
            origin_id=item.origin_id,
            adapter_version=ADAPTER_VERSION,
            input_fingerprint=item.fingerprint,
            target_entity_type="AssessmentProcedureVersion",
            target_version_id=snapshot.id,
            target_revision=snapshot.sequence,
            target_digest=snapshot.content_digest,
            created_at=db_time,
        )
        self.session.add(reuse)

        self._record_input_disposition(
            context,
            input_row,
            ImportDisposition.IMPORTED_DRAFT,
            "DRAFT_CREATED_SUCCESS",
            db_time,
            target_entity_type="AssessmentProcedureVersion",
            target_version_id=snapshot.id,
            target_revision=snapshot.sequence,
            target_digest=snapshot.content_digest,
        )

    def _verify_reuse_target(self, ledger: CatalogImportReuseLedger) -> bool:
        ent: Any = None
        if ledger.target_entity_type == "RequirementVersion":
            ent = self.session.get(CatalogRequirementVersion, ledger.target_version_id)
        elif ledger.target_entity_type == "ControlVersion":
            ent = self.session.get(CatalogControlVersion, ledger.target_version_id)
        elif ledger.target_entity_type == "MappingVersion":
            ent = self.session.get(CatalogMappingVersion, ledger.target_version_id)
        elif ledger.target_entity_type == "PackVersion":
            ent = self.session.get(CatalogPackVersion, ledger.target_version_id)
        else:
            return False
        if ent is None:
            return False
        return bool(
            ent.revision == ledger.target_revision and ent.content_digest == ledger.target_digest
        )

    # -----------------------------------------------------------------------
    # Disposition & Telemetry Recording
    # -----------------------------------------------------------------------

    def _record_input_disposition(
        self,
        context: CatalogActorContext,
        input_row: CatalogImportInput,
        disposition: ImportDisposition,
        reason_code: str,
        db_time: datetime,
        *,
        target_entity_type: str | None = None,
        target_version_id: UUID | None = None,
        target_revision: int | None = None,
        target_digest: bytes | None = None,
    ) -> None:
        """Atomically set disposition and record audit event & event intent."""
        input_row.disposition = disposition
        input_row.reason_code = reason_code
        input_row.target_entity_type = target_entity_type
        input_row.target_version_id = target_version_id
        input_row.target_revision = target_revision
        input_row.target_digest = target_digest
        input_row.processed_at = db_time

        req_key = f"import:{input_row.batch_id}:{input_row.sequence}"

        # Finding 3: ReusedExact emits catalog.import.input_reused per contract Section 7
        if disposition == ImportDisposition.IMPORTED_DRAFT:
            event_kind = "catalog.import.input_evaluated"
            outcome = "Success"
        elif disposition == ImportDisposition.REUSED_EXACT:
            event_kind = "catalog.import.input_reused"
            outcome = "Success"
        elif disposition in (
            ImportDisposition.NEEDS_PERMISSION,
            ImportDisposition.NEEDS_SOURCE,
            ImportDisposition.NEEDS_MAPPING_REVIEW,
            ImportDisposition.NEEDS_CONFLICT_REVIEW,
            ImportDisposition.NEEDS_DEPENDENCY,
            ImportDisposition.DEFERRED_BY_SCOPE,
        ):
            event_kind = "catalog.import.input_flagged"
            outcome = "Denied" if disposition == ImportDisposition.NEEDS_PERMISSION else "Conflict"
        else:  # Rejected
            event_kind = "catalog.import.input_flagged"
            outcome = "Denied"

        disp_str = disposition.value if hasattr(disposition, "value") else str(disposition)
        detail: dict[str, Any] = {
            "disposition": disp_str,
            "reason": reason_code,
        }
        if target_entity_type:
            detail["target_type"] = target_entity_type
        if target_version_id:
            detail["target_id"] = str(target_version_id)

        append_catalog_audit_event(
            self.session,
            context.actor_id,
            event_kind,
            "CatalogImportInput",
            input_row.id,
            req_key,
            outcome,
            detail,
            db_time,
        )

        record_catalog_event_intent(
            self.session,
            req_key,
            event_kind,
            input_row.id,
            "CatalogImportInput",
            target_revision if target_revision is not None else 1,
            target_digest if target_digest is not None else input_row.input_fingerprint,
            db_time,
        )
        self.session.flush()

    # -----------------------------------------------------------------------
    # Execution
    # -----------------------------------------------------------------------

    def execute_batch(
        self,
        context: CatalogActorContext,
        batch_id: UUID,
        items: list[ImportItem],
    ) -> CatalogImportReconciliationManifest:
        """Execute pending items in an admitted batch through CatalogDraftService."""
        db_time = self._db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
            verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        except CatalogSecurityError as exc:
            self._record_denial_safe(
                context.actor_id if context else None,
                "execute_batch_capability_preflight",
                type(exc).__name__,
                f"import:batch:{batch_id}",
                resource_type="CatalogImportBatch",
                resource_id=batch_id,
            )
            raise
        batch_deadline = time.monotonic() + BATCH_EXECUTION_DEADLINE_SECONDS

        batch = self.session.scalar(
            select(CatalogImportBatch).where(CatalogImportBatch.id == batch_id).with_for_update()
        )
        if batch is None:
            raise CatalogNotFoundError(f"Batch {batch_id} not found")

        if batch.status in ("Cancelled", "Aborted"):
            raise CatalogConflictError(f"BATCH_TERMINAL_STATE_{batch.status}")

        # Finding 1: Strict validation of supplied content before checking Reconciled
        _validate_batch_envelope(items)
        if len(items) != batch.total_inputs:
            raise CatalogConflictError("CONFLICT_CHANGED_BATCH_CONTENT")

        sorted_items = sorted(items, key=lambda entry: entry.sequence)
        items_by_seq: dict[int, ImportItem] = {}
        for item in sorted_items:
            if item.sequence in items_by_seq:
                raise CatalogConflictError("CONFLICT_CHANGED_BATCH_CONTENT")
            items_by_seq[item.sequence] = item

        # Verify payload digest matches admitted batch payload_digest
        supplied_payload = [
            {
                "fingerprint": item.fingerprint,
                "input_type": item.input_type,
                "origin_id": item.origin_id,
                "origin_namespace": item.origin_namespace,
                "sequence": item.sequence,
            }
            for item in sorted_items
        ]
        supplied_digest = compute_content_digest(supplied_payload)
        if supplied_digest != batch.payload_digest:
            raise CatalogConflictError("CONFLICT_CHANGED_BATCH_CONTENT")

        input_rows = self.session.scalars(
            select(CatalogImportInput)
            .where(CatalogImportInput.batch_id == batch_id)
            .order_by(CatalogImportInput.sequence.asc())
        ).all()
        if len(input_rows) != batch.total_inputs:
            raise CatalogConflictError("CONFLICT_CHANGED_BATCH_CONTENT")

        # Strict verification against immutable admitted fingerprints
        for input_row in input_rows:
            candidate = items_by_seq.get(input_row.sequence)
            if (
                candidate is None
                or candidate.fingerprint != input_row.input_fingerprint
                or candidate.origin_namespace != input_row.origin_namespace
                or candidate.origin_id != input_row.origin_id
                or candidate.input_type != input_row.input_type
            ):
                raise CatalogConflictError("CONFLICT_CHANGED_BATCH_CONTENT")

        # Finding 1: Reconciled replay check ONLY AFTER strict supplied-content validation
        if batch.status == "Reconciled":
            manifest = self.session.scalar(
                select(CatalogImportReconciliationManifest).where(
                    CatalogImportReconciliationManifest.batch_id == batch_id
                )
            )
            if manifest is not None:
                return manifest

        batch.status = "Running"
        batch.updated_at = db_time
        self.session.commit()

        draft_service = CatalogDraftService(self.session, denied_audit_sink=self.denied_sink)

        # Process each pending input individually with lock discipline and retry
        for input_row in input_rows:
            fresh_status = self.session.scalar(
                select(CatalogImportInput.disposition).where(CatalogImportInput.id == input_row.id)
            )
            if fresh_status != ImportDisposition.PENDING:
                continue

            # Finding 4: Batch deadline check (300 seconds)
            if time.monotonic() >= batch_deadline:
                batch = self.session.scalar(
                    select(CatalogImportBatch)
                    .where(CatalogImportBatch.id == batch_id)
                    .with_for_update()
                )
                if batch is not None:
                    batch.status = "Interrupted"
                    batch.updated_at = self._db_time()
                    self.session.commit()
                raise CatalogConflictError("BATCH_EXECUTION_DEADLINE_EXCEEDED")

            item = items_by_seq[input_row.sequence]
            try:
                self._execute_input_with_retry(
                    context, batch_id, input_row.id, item, draft_service, batch_deadline
                )
            except Exception as exc:
                batch = self.session.scalar(
                    select(CatalogImportBatch)
                    .where(CatalogImportBatch.id == batch_id)
                    .with_for_update()
                )
                if batch is not None:
                    batch.status = "Interrupted"
                    batch.updated_at = self._db_time()
                    self.session.commit()
                raise exc

        # Finding 4: Batch deadline check before final sealing
        if time.monotonic() >= batch_deadline:
            batch = self.session.scalar(
                select(CatalogImportBatch)
                .where(CatalogImportBatch.id == batch_id)
                .with_for_update()
            )
            if batch is not None:
                batch.status = "Interrupted"
                batch.updated_at = self._db_time()
                self.session.commit()
            raise CatalogConflictError("BATCH_EXECUTION_DEADLINE_EXCEEDED")

        return self.seal_batch(context, batch_id)

    def _execute_input_with_retry(
        self,
        context: CatalogActorContext,
        batch_id: UUID,
        input_id: UUID,
        item: ImportItem,
        draft_service: CatalogDraftService,
        batch_deadline: float,
    ) -> None:
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            if attempt > 1 and time.monotonic() >= batch_deadline:
                raise CatalogConflictError("BATCH_EXECUTION_DEADLINE_EXCEEDED")

            try:
                # Per-input statement timeout on PostgreSQL
                if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
                    self.session.execute(text("SET LOCAL statement_timeout = '15s'"))

                # 1. Batch Lock: SELECT ... FOR UPDATE on catalog_import_batches
                batch = self.session.scalar(
                    select(CatalogImportBatch)
                    .where(CatalogImportBatch.id == batch_id)
                    .with_for_update()
                )
                if batch is None:
                    raise CatalogNotFoundError(f"Batch {batch_id} not found")
                if batch.status in ("Cancelled", "Aborted"):
                    raise CatalogConflictError(f"BATCH_TERMINAL_STATE_{batch.status}")

                # 2. Input Item Lock: SELECT ... FOR UPDATE on catalog_import_inputs
                input_row = self.session.scalar(
                    select(CatalogImportInput)
                    .where(CatalogImportInput.id == input_id)
                    .with_for_update()
                )
                if input_row is None or input_row.disposition != ImportDisposition.PENDING:
                    self.session.commit()
                    return

                # 3. Origin Advisory / Reuse Lock: PostgreSQL transaction-level advisory lock
                if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
                    origin_key = f"{item.origin_namespace}:{item.origin_id}:{ADAPTER_VERSION}"
                    lock_id = (
                        int.from_bytes(sha256(origin_key.encode()).digest()[:8], "big")
                        & 0x7FFFFFFFFFFFFFFF
                    )
                    self.session.execute(
                        text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id}
                    )

                # Re-verify fingerprint inside transaction to prevent payload substitution
                if (
                    item.fingerprint != input_row.input_fingerprint
                    or item.origin_namespace != input_row.origin_namespace
                    or item.origin_id != input_row.origin_id
                    or item.input_type != input_row.input_type
                ):
                    raise CatalogConflictError("CONFLICT_CHANGED_BATCH_CONTENT")

                input_row.attempt_count = attempt

                self._process_single_input(context, batch, input_row, item, draft_service)
                self.session.commit()
                return
            except Exception as exc:
                # Full rollback releases input-level locks and releases the connection
                self.session.rollback()

                sqlstate = getattr(exc, "pgcode", None) or getattr(exc, "code", None)
                if sqlstate is None and hasattr(exc, "orig"):
                    sqlstate = getattr(exc.orig, "pgcode", None) or getattr(
                        exc.orig, "sqlstate", None
                    )

                is_retryable = sqlstate in ("40001", "40P01", "55P03")

                # Finding 4: Deadline check during retry backoff
                if is_retryable:
                    if attempt < max_retries:
                        delay = min(2.0, 0.1 * (2**attempt) + random.uniform(0, 0.05))
                        if time.monotonic() + delay >= batch_deadline:
                            raise CatalogConflictError("BATCH_EXECUTION_DEADLINE_EXCEEDED")
                        time.sleep(delay)
                        if time.monotonic() >= batch_deadline:
                            raise CatalogConflictError("BATCH_EXECUTION_DEADLINE_EXCEEDED")
                        continue
                    raise CatalogConflictError(
                        f"CONCURRENCY_CONFLICT_RETRY_EXHAUSTED:{sqlstate}"
                    ) from exc

                if sqlstate == "57014":  # Statement timeout (query_canceled)
                    db_time = self._db_time()
                    batch = self.session.scalar(
                        select(CatalogImportBatch)
                        .where(CatalogImportBatch.id == batch_id)
                        .with_for_update()
                    )
                    input_row = self.session.scalar(
                        select(CatalogImportInput)
                        .where(CatalogImportInput.id == input_id)
                        .with_for_update()
                    )
                    if input_row is not None and input_row.disposition == ImportDisposition.PENDING:
                        self._record_input_disposition(
                            context,
                            input_row,
                            ImportDisposition.REJECTED,
                            "STATEMENT_TIMEOUT_EXCEEDED",
                            db_time,
                        )
                        self.session.commit()
                    else:
                        # A concurrent executor may have finalized the row after the
                        # timeout rollback released its original lock. Preserve that
                        # terminal result and release this recovery transaction.
                        self.session.commit()
                    return

                # Unexpected failures roll back cleanly and leave input_row.disposition == PENDING
                raise

    def _process_single_input(
        self,
        context: CatalogActorContext,
        batch: CatalogImportBatch,
        input_row: CatalogImportInput,
        item: ImportItem,
        draft_service: CatalogDraftService,
        assurance_service: CatalogAssuranceDraftService | None = None,
    ) -> None:
        if assurance_service is None:
            assurance_service = CatalogAssuranceDraftService(
                self.session, denied_audit_sink=self.denied_sink
            )
        assert assurance_service is not None
        db_time = self._db_time()
        req_key = f"import:{batch.id}:{item.sequence}"

        # 1. Deferred Child Check
        if item.input_type in DEFERRED_INPUT_TYPES:
            self._record_input_disposition(
                context,
                input_row,
                ImportDisposition.DEFERRED_BY_SCOPE,
                "SCOPE_CHILD_DEFERRED",
                db_time,
            )
            return

        # 2. Envelope & Item Validation
        try:
            _validate_item(item)
        except ImportPayloadError as exc:
            self._record_input_disposition(
                context,
                input_row,
                ImportDisposition.REJECTED,
                str(exc),
                db_time,
            )
            return

        # 3. Check Reuse Ledger for Reusable Types
        # Finding 2: Invalid exact-reuse pins route to NeedsConflictReview, NEVER falling into draft creation
        if item.input_type in (
            "Requirement",
            "CommonControl",
            "Mapping",
            "Pack",
            "EvidenceRequirement",
            "AssessmentProcedure",
        ):
            reuse_res = self.resolve_reuse(item)
            if reuse_res is not None:
                if (
                    reuse_res.disposition == ImportDisposition.REUSED_EXACT
                    and reuse_res.ledger is not None
                ):
                    if item.input_type in ("EvidenceRequirement", "AssessmentProcedure"):
                        self._verify_and_record_assurance_reuse(
                            context,
                            batch,
                            input_row,
                            item,
                            reuse_res.ledger,
                            assurance_service,
                            db_time,
                        )
                        return
                    else:
                        valid = self._verify_reuse_target(reuse_res.ledger)
                        if valid:
                            self._record_input_disposition(
                                context,
                                input_row,
                                ImportDisposition.REUSED_EXACT,
                                "REUSE_EXACT_MATCH",
                                db_time,
                                target_entity_type=reuse_res.ledger.target_entity_type,
                                target_version_id=reuse_res.ledger.target_version_id,
                                target_revision=reuse_res.ledger.target_revision,
                                target_digest=reuse_res.ledger.target_digest,
                            )
                            return
                        else:
                            # Stale or invalid reuse pin: route to NeedsConflictReview instead of draft creation
                            self._record_input_disposition(
                                context,
                                input_row,
                                ImportDisposition.NEEDS_CONFLICT_REVIEW,
                                "CONFLICT_STALE_REUSE_TARGET",
                                db_time,
                                target_entity_type=reuse_res.ledger.target_entity_type,
                                target_version_id=reuse_res.ledger.target_version_id,
                                target_revision=reuse_res.ledger.target_revision,
                                target_digest=reuse_res.ledger.target_digest,
                            )
                            return
                elif (
                    reuse_res.disposition == ImportDisposition.NEEDS_CONFLICT_REVIEW
                    and reuse_res.ledger is not None
                ):
                    self._record_input_disposition(
                        context,
                        input_row,
                        ImportDisposition.NEEDS_CONFLICT_REVIEW,
                        "CONFLICT_CHANGED_ORIGIN_CONTENT",
                        db_time,
                        target_entity_type=reuse_res.ledger.target_entity_type,
                        target_version_id=reuse_res.ledger.target_version_id,
                        target_revision=reuse_res.ledger.target_revision,
                        target_digest=reuse_res.ledger.target_digest,
                    )
                    return
                else:
                    self._record_input_disposition(
                        context,
                        input_row,
                        ImportDisposition.NEEDS_CONFLICT_REVIEW,
                        "CONFLICT_INVALID_REUSE_PIN",
                        db_time,
                    )
                    return

        # 4. Domain Construction via CatalogDraftService / CatalogAssuranceDraftService
        try:
            if item.input_type == "CommonControl":
                self._process_common_control(
                    context, req_key, input_row, item, draft_service, db_time
                )
            elif item.input_type == "Requirement":
                self._process_requirement(context, req_key, input_row, item, draft_service, db_time)
            elif item.input_type == "Mapping":
                self._process_mapping(context, req_key, input_row, item, draft_service, db_time)
            elif item.input_type == "Pack":
                self._process_pack(context, req_key, input_row, item, draft_service, db_time)
            elif item.input_type == "PackMembership":
                self._process_pack_membership(
                    context, req_key, input_row, item, draft_service, db_time
                )
            elif item.input_type == "EvidenceRequirement":
                self._process_evidence_requirement(
                    context, req_key, batch, input_row, item, assurance_service, db_time
                )
            elif item.input_type == "AssessmentProcedure":
                self._process_assessment_procedure(
                    context, req_key, batch, input_row, item, assurance_service, db_time
                )
            else:
                self._record_input_disposition(
                    context,
                    input_row,
                    ImportDisposition.REJECTED,
                    "UNSUPPORTED_INPUT_TYPE",
                    db_time,
                )
        except CatalogPermissionDeniedError:
            self._record_input_disposition(
                context,
                input_row,
                ImportDisposition.NEEDS_PERMISSION,
                "PERMISSION_DENIED",
                db_time,
            )
        except CatalogConflictError as exc:
            self._record_input_disposition(
                context,
                input_row,
                ImportDisposition.NEEDS_CONFLICT_REVIEW,
                str(exc),
                db_time,
            )
        except CatalogValidationError as exc:
            self._record_input_disposition(
                context,
                input_row,
                ImportDisposition.REJECTED,
                str(exc),
                db_time,
            )

    def _process_common_control(
        self,
        context: CatalogActorContext,
        req_key: str,
        input_row: CatalogImportInput,
        item: ImportItem,
        draft_service: CatalogDraftService,
        db_time: datetime,
    ) -> None:
        control_key = item.payload.get("control_key")
        if not control_key:
            raise ImportPayloadError("CONTROL_KEY_REQUIRED")

        title = item.payload.get("title", control_key)
        objective = item.payload.get("statement", item.payload.get("description", title))
        version_label = item.payload.get("version_label", "1.0.0")

        domain = item.payload.get("domain", "General")
        ctrl = self.session.scalar(
            select(CatalogCommonControl).where(CatalogCommonControl.control_key == control_key)
        )
        if ctrl is None:
            ctrl = draft_service.create_common_control(
                context, f"{req_key}:ctrl", control_key=control_key, domain=domain
            )

        v = draft_service.create_control_version(
            context,
            f"{req_key}:ver",
            control_id=ctrl.id,
            version_label=version_label,
            title=title,
            objective=objective,
        )

        reuse = CatalogImportReuseLedger(
            origin_namespace=item.origin_namespace,
            origin_id=item.origin_id,
            adapter_version=ADAPTER_VERSION,
            input_fingerprint=item.fingerprint,
            target_entity_type="ControlVersion",
            target_version_id=v.id,
            target_revision=v.revision,
            target_digest=v.content_digest,
            created_at=db_time,
        )
        self.session.add(reuse)

        self._record_input_disposition(
            context,
            input_row,
            ImportDisposition.IMPORTED_DRAFT,
            "DRAFT_CREATED_SUCCESS",
            db_time,
            target_entity_type="ControlVersion",
            target_version_id=v.id,
            target_revision=v.revision,
            target_digest=v.content_digest,
        )

    def _process_requirement(
        self,
        context: CatalogActorContext,
        req_key: str,
        input_row: CatalogImportInput,
        item: ImportItem,
        draft_service: CatalogDraftService,
        db_time: datetime,
    ) -> None:
        raw_sv_id = item.payload.get("source_version_id")
        if not raw_sv_id:
            self._record_input_disposition(
                context,
                input_row,
                ImportDisposition.NEEDS_SOURCE,
                "SOURCE_UNAVAILABLE",
                db_time,
            )
            return

        try:
            sv_id = UUID(str(raw_sv_id))
        except (ValueError, AttributeError):
            self._record_input_disposition(
                context,
                input_row,
                ImportDisposition.NEEDS_SOURCE,
                "SOURCE_UNAVAILABLE",
                db_time,
            )
            return

        sv = self.session.get(CatalogSourceVersion, sv_id)
        if sv is None:
            self._record_input_disposition(
                context,
                input_row,
                ImportDisposition.NEEDS_SOURCE,
                "SOURCE_UNAVAILABLE",
                db_time,
            )
            return

        text_origin = item.payload.get("text_origin", "conformly_paraphrase")
        needed_ops = ["reference", "store"]
        if text_origin == "conformly_paraphrase":
            needed_ops.append("paraphrase")
        elif text_origin == "authorized_excerpt":
            needed_ops.append("excerpt")
        elif text_origin == "verbatim_source":
            pass
        elif text_origin == "reference_only":
            needed_ops = ["reference"]

        scope_key = item.payload.get("scope_key", DEFAULT_SCOPE_KEY)
        for op in needed_ops:
            if not has_effective_permission(self.session, sv.id, op, scope_key, db_time):
                self._record_input_disposition(
                    context,
                    input_row,
                    ImportDisposition.NEEDS_PERMISSION,
                    f"PERMISSION_DENIED_{op.upper()}",
                    db_time,
                )
                return

        req_key_name = item.payload.get("requirement_key", item.origin_id)
        req = self.session.scalar(
            select(CatalogRequirement).where(
                CatalogRequirement.source_id == sv.source_id,
                CatalogRequirement.requirement_key == req_key_name,
            )
        )
        if req is None:
            req = draft_service.create_requirement(
                context, f"{req_key}:req", source_id=sv.source_id, requirement_key=req_key_name
            )

        # Finding 5: Preserve locator fields matching draft service parameter consumption
        refs = item.payload.get("source_references")
        if not refs:
            loc_val = (
                item.payload.get("locator_value")
                or item.payload.get("locator")
                or item.payload.get("location")
                or "Section 1"
            )
            loc_kind = item.payload.get("locator_kind") or "section"
            if loc_kind not in ALLOWED_LOCATOR_KINDS:
                loc_kind = "section"
            refs = [
                {
                    "source_version_id": sv.id,
                    "locator_kind": loc_kind,
                    "locator_value": str(loc_val),
                    "locator": str(loc_val),
                    "sequence": 1,
                }
            ]
        else:
            normalized_refs = []
            for i, ref in enumerate(refs):
                ref_sv_id = ref.get("source_version_id", sv.id)
                loc_val = (
                    ref.get("locator_value")
                    or ref.get("locator")
                    or ref.get("location")
                    or "Section 1"
                )
                loc_kind = ref.get("locator_kind") or "section"
                if loc_kind not in ALLOWED_LOCATOR_KINDS:
                    loc_kind = "section"
                normalized_refs.append(
                    {
                        "source_version_id": ref_sv_id,
                        "locator_kind": loc_kind,
                        "locator_value": str(loc_val),
                        "locator": str(loc_val),
                        "sequence": ref.get("sequence", i + 1),
                    }
                )
            refs = normalized_refs

        effective_from = None
        if item.payload.get("effective_from"):
            effective_from = date.fromisoformat(item.payload["effective_from"])
        effective_until = None
        if item.payload.get("effective_until"):
            effective_until = date.fromisoformat(item.payload["effective_until"])

        v = draft_service.create_requirement_version(
            context,
            f"{req_key}:ver",
            requirement_id=req.id,
            source_version_id=sv.id,
            version_label=item.payload.get("version_label", "1.0.0"),
            normalized_outcome=item.payload.get("normalized_outcome", "Shall comply"),
            requirement_type=item.payload.get("requirement_type", "mandatory"),
            obligated_actor=item.payload.get("obligated_actor", "organization"),
            text_origin=text_origin,
            source_references=refs,
            effective_from=effective_from,
            effective_until=effective_until,
        )

        reuse = CatalogImportReuseLedger(
            origin_namespace=item.origin_namespace,
            origin_id=item.origin_id,
            adapter_version=ADAPTER_VERSION,
            input_fingerprint=item.fingerprint,
            target_entity_type="RequirementVersion",
            target_version_id=v.id,
            target_revision=v.revision,
            target_digest=v.content_digest,
            created_at=db_time,
        )
        self.session.add(reuse)

        self._record_input_disposition(
            context,
            input_row,
            ImportDisposition.IMPORTED_DRAFT,
            "DRAFT_CREATED_SUCCESS",
            db_time,
            target_entity_type="RequirementVersion",
            target_version_id=v.id,
            target_revision=v.revision,
            target_digest=v.content_digest,
        )

    def _process_mapping(
        self,
        context: CatalogActorContext,
        req_key: str,
        input_row: CatalogImportInput,
        item: ImportItem,
        draft_service: CatalogDraftService,
        db_time: datetime,
    ) -> None:
        req_v_id = item.payload.get("requirement_version_id")
        req_origin = item.payload.get("requirement_origin")
        req_origin_ns = item.payload.get("requirement_origin_namespace", item.origin_namespace)
        req_v = None
        if req_v_id:
            try:
                req_v = self.session.get(CatalogRequirementVersion, UUID(str(req_v_id)))
            except (ValueError, AttributeError):
                pass
        elif req_origin:
            reuse_req = self.session.scalar(
                select(CatalogImportReuseLedger).where(
                    CatalogImportReuseLedger.origin_namespace == req_origin_ns,
                    CatalogImportReuseLedger.origin_id == req_origin,
                    CatalogImportReuseLedger.adapter_version == ADAPTER_VERSION,
                    CatalogImportReuseLedger.target_entity_type == "RequirementVersion",
                )
            )
            if reuse_req and self._verify_reuse_target(reuse_req):
                req_v = self.session.get(CatalogRequirementVersion, reuse_req.target_version_id)

        ctrl_v_id = item.payload.get("control_version_id")
        ctrl_origin = item.payload.get("control_origin")
        ctrl_origin_ns = item.payload.get("control_origin_namespace", item.origin_namespace)
        ctrl_v = None
        if ctrl_v_id:
            try:
                ctrl_v = self.session.get(CatalogControlVersion, UUID(str(ctrl_v_id)))
            except (ValueError, AttributeError):
                pass
        elif ctrl_origin:
            reuse_ctrl = self.session.scalar(
                select(CatalogImportReuseLedger).where(
                    CatalogImportReuseLedger.origin_namespace == ctrl_origin_ns,
                    CatalogImportReuseLedger.origin_id == ctrl_origin,
                    CatalogImportReuseLedger.adapter_version == ADAPTER_VERSION,
                    CatalogImportReuseLedger.target_entity_type == "ControlVersion",
                )
            )
            if reuse_ctrl and self._verify_reuse_target(reuse_ctrl):
                ctrl_v = self.session.get(CatalogControlVersion, reuse_ctrl.target_version_id)

        if req_v is None or ctrl_v is None:
            self._record_input_disposition(
                context,
                input_row,
                ImportDisposition.NEEDS_MAPPING_REVIEW,
                "MAPPING_ENDPOINT_UNRESOLVED",
                db_time,
            )
            return

        scope_key = item.payload.get("scope_key", DEFAULT_SCOPE_KEY)
        if not has_effective_permission(
            self.session, req_v.source_version_id, "map", scope_key, db_time
        ):
            self._record_input_disposition(
                context,
                input_row,
                ImportDisposition.NEEDS_PERMISSION,
                "PERMISSION_MAPPING_DENIED",
                db_time,
            )
            return

        map_key = item.payload.get("mapping_key", f"{req_v.id}:{ctrl_v.id}")
        mapping = self.session.scalar(
            select(CatalogRequirementControlMapping).where(
                CatalogRequirementControlMapping.mapping_key == map_key
            )
        )
        if mapping is None:
            mapping = draft_service.create_mapping(
                context,
                f"{req_key}:map",
                mapping_key=map_key,
                requirement_id=req_v.requirement_id,
                control_id=ctrl_v.control_id,
            )

        raw_type = item.payload.get("mapping_type", "Full")
        if raw_type in ("Full", "Partial", "Supporting"):
            mapping_type = raw_type
        elif str(raw_type).lower() in ("direct_coverage", "full"):
            mapping_type = "Full"
        elif str(raw_type).lower() in ("partial_coverage", "partial"):
            mapping_type = "Partial"
        else:
            mapping_type = "Supporting"

        excluded_dims = item.payload.get("excluded_dimensions")
        if mapping_type == "Partial" and not excluded_dims:
            excluded_dims = "Scope delta"

        confidence = str(item.payload.get("confidence", "high")).lower()
        if confidence not in ("low", "medium", "high"):
            confidence = "high"

        source_basis = str(item.payload.get("source_basis", "expert_analysis")).lower()
        if source_basis not in (
            "direct_text",
            "authoritative_guidance",
            "expert_analysis",
            "regulatory_precedent",
        ):
            source_basis = "expert_analysis"

        v = draft_service.create_mapping_version(
            context,
            f"{req_key}:ver",
            mapping_id=mapping.id,
            requirement_version_id=req_v.id,
            control_version_id=ctrl_v.id,
            expected_req_revision=req_v.revision,
            expected_req_digest=req_v.content_digest,
            expected_ctrl_revision=ctrl_v.revision,
            expected_ctrl_digest=ctrl_v.content_digest,
            version_label=item.payload.get("version_label", "1.0.0"),
            mapping_type=mapping_type,
            rationale=item.payload.get("rationale", "Imported mapping"),
            source_basis=source_basis,
            confidence=confidence,
            excluded_dimensions=excluded_dims,
        )

        reuse = CatalogImportReuseLedger(
            origin_namespace=item.origin_namespace,
            origin_id=item.origin_id,
            adapter_version=ADAPTER_VERSION,
            input_fingerprint=item.fingerprint,
            target_entity_type="MappingVersion",
            target_version_id=v.id,
            target_revision=v.revision,
            target_digest=v.content_digest,
            created_at=db_time,
        )
        self.session.add(reuse)

        self._record_input_disposition(
            context,
            input_row,
            ImportDisposition.IMPORTED_DRAFT,
            "DRAFT_CREATED_SUCCESS",
            db_time,
            target_entity_type="MappingVersion",
            target_version_id=v.id,
            target_revision=v.revision,
            target_digest=v.content_digest,
        )

    def _process_pack(
        self,
        context: CatalogActorContext,
        req_key: str,
        input_row: CatalogImportInput,
        item: ImportItem,
        draft_service: CatalogDraftService,
        db_time: datetime,
    ) -> None:
        pack_key = item.payload.get("pack_key")
        if not pack_key:
            raise ImportPayloadError("PACK_KEY_REQUIRED")
        name = item.payload.get("name", pack_key)
        pack_type = item.payload.get("pack_type", "baseline").lower()
        if pack_type not in ("regulatory", "certification", "contractual", "baseline"):
            pack_type = "baseline"
        version_label = item.payload.get("version_label", "1.0.0")

        pack = self.session.scalar(select(CatalogPack).where(CatalogPack.pack_key == pack_key))
        if pack is None:
            pack = draft_service.create_pack(
                context, f"{req_key}:pack", pack_key=pack_key, name=name, pack_type=pack_type
            )

        v = draft_service.create_pack_version(
            context,
            f"{req_key}:ver",
            pack_id=pack.id,
            version_label=version_label,
            description=item.payload.get("description", name),
        )

        reuse = CatalogImportReuseLedger(
            origin_namespace=item.origin_namespace,
            origin_id=item.origin_id,
            adapter_version=ADAPTER_VERSION,
            input_fingerprint=item.fingerprint,
            target_entity_type="PackVersion",
            target_version_id=v.id,
            target_revision=v.revision,
            target_digest=v.content_digest,
            created_at=db_time,
        )
        self.session.add(reuse)

        self._record_input_disposition(
            context,
            input_row,
            ImportDisposition.IMPORTED_DRAFT,
            "DRAFT_CREATED_SUCCESS",
            db_time,
            target_entity_type="PackVersion",
            target_version_id=v.id,
            target_revision=v.revision,
            target_digest=v.content_digest,
        )

    def _process_pack_membership(
        self,
        context: CatalogActorContext,
        req_key: str,
        input_row: CatalogImportInput,
        item: ImportItem,
        draft_service: CatalogDraftService,
        db_time: datetime,
    ) -> None:
        pack_origin = item.payload.get("pack_origin")
        pack_origin_ns = item.payload.get("pack_origin_namespace", item.origin_namespace)
        pack_v_id = item.payload.get("pack_version_id")
        pack_v = None
        if pack_v_id:
            try:
                pack_v = self.session.get(CatalogPackVersion, UUID(str(pack_v_id)))
            except (ValueError, AttributeError):
                pass
        elif pack_origin:
            reuse_pack = self.session.scalar(
                select(CatalogImportReuseLedger).where(
                    CatalogImportReuseLedger.origin_namespace == pack_origin_ns,
                    CatalogImportReuseLedger.origin_id == pack_origin,
                    CatalogImportReuseLedger.adapter_version == ADAPTER_VERSION,
                    CatalogImportReuseLedger.target_entity_type == "PackVersion",
                )
            )
            if reuse_pack and self._verify_reuse_target(reuse_pack):
                pack_v = self.session.get(CatalogPackVersion, reuse_pack.target_version_id)

        req_origin = item.payload.get("requirement_origin")
        req_origin_ns = item.payload.get("requirement_origin_namespace", item.origin_namespace)
        req_v_id = item.payload.get("requirement_version_id")
        req_v = None
        if req_v_id:
            try:
                req_v = self.session.get(CatalogRequirementVersion, UUID(str(req_v_id)))
            except (ValueError, AttributeError):
                pass
        elif req_origin:
            reuse_req = self.session.scalar(
                select(CatalogImportReuseLedger).where(
                    CatalogImportReuseLedger.origin_namespace == req_origin_ns,
                    CatalogImportReuseLedger.origin_id == req_origin,
                    CatalogImportReuseLedger.adapter_version == ADAPTER_VERSION,
                    CatalogImportReuseLedger.target_entity_type == "RequirementVersion",
                )
            )
            if reuse_req and self._verify_reuse_target(reuse_req):
                req_v = self.session.get(CatalogRequirementVersion, reuse_req.target_version_id)

        if pack_v is None or req_v is None:
            self._record_input_disposition(
                context,
                input_row,
                ImportDisposition.NEEDS_DEPENDENCY,
                "DEPENDENCY_UNRESOLVED",
                db_time,
            )
            return

        mem = draft_service.append_pack_membership(
            context,
            f"{req_key}:mem",
            pack_version_id=pack_v.id,
            requirement_version_id=req_v.id,
            expected_req_revision=req_v.revision,
            expected_req_digest=req_v.content_digest,
        )

        self._record_input_disposition(
            context,
            input_row,
            ImportDisposition.IMPORTED_DRAFT,
            "DRAFT_CREATED_SUCCESS",
            db_time,
            target_entity_type="PackMembership",
            target_version_id=mem.id,
            target_revision=mem.sequence,
            target_digest=mem.requirement_version_digest,
        )

    # -----------------------------------------------------------------------
    # Reconciliation Sealing
    # -----------------------------------------------------------------------

    def seal_batch(
        self, context: CatalogActorContext, batch_id: UUID
    ) -> CatalogImportReconciliationManifest:
        """Seal a completed import batch and persist its reconciliation manifest."""
        db_time = self._db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogSecurityError as exc:
            self._record_denial_safe(
                context.actor_id if context else None,
                "seal_batch_capability_preflight",
                type(exc).__name__,
                f"import:batch:{batch_id}:seal",
                resource_type="CatalogImportBatch",
                resource_id=batch_id,
            )
            raise

        # Finding 7: Lock the batch FOR UPDATE to serialize concurrent sealers
        batch = self.session.scalar(
            select(CatalogImportBatch).where(CatalogImportBatch.id == batch_id).with_for_update()
        )
        if batch is None:
            raise CatalogNotFoundError(f"Batch {batch_id} not found")

        # Finding 7: If already reconciled, return manifest immediately without emitting duplicate audit or event side effects.
        # Commit cleanly to release the transaction and FOR UPDATE row lock before returning.
        if batch.status == "Reconciled":
            manifest = self.session.scalar(
                select(CatalogImportReconciliationManifest).where(
                    CatalogImportReconciliationManifest.batch_id == batch_id
                )
            )
            self.session.commit()
            if manifest is not None:
                return manifest
            raise CatalogNotFoundError("RECONCILIATION_MANIFEST_NOT_FOUND")

        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            self.session.execute(
                text("SELECT public.catalog_seal_import_batch(:batch_id, :actor_id)"),
                {"batch_id": batch_id, "actor_id": context.actor_id},
            )
            manifest = self.session.scalar(
                select(CatalogImportReconciliationManifest).where(
                    CatalogImportReconciliationManifest.batch_id == batch_id
                )
            )
            if manifest is None:
                raise ValueError("SEAL_MANIFEST_NOT_FOUND")

            # Check if seal event already recorded by concurrent execution
            existing_intent = self.session.scalar(
                select(CatalogEventIntent).where(
                    CatalogEventIntent.request_key == f"batch:{batch.batch_key}:sealed",
                    CatalogEventIntent.event_kind == "catalog.import.batch_sealed",
                )
            )
            if existing_intent is None:
                try:
                    with self.session.begin_nested():
                        append_catalog_audit_event(
                            self.session,
                            context.actor_id,
                            "catalog.import.batch_sealed",
                            "CatalogImportBatch",
                            batch_id,
                            f"batch:{batch.batch_key}:sealed",
                            "Success",
                            {
                                "batch_key": batch.batch_key,
                                "total_inputs": manifest.total_inputs,
                                "reconciled_inputs": manifest.reconciled_inputs,
                                "manifest_hash": manifest.manifest_hash.hex(),
                            },
                            db_time,
                        )
                        record_catalog_event_intent(
                            self.session,
                            f"batch:{batch.batch_key}:sealed",
                            "catalog.import.batch_sealed",
                            batch_id,
                            "CatalogImportBatch",
                            1,
                            manifest.manifest_hash,
                            db_time,
                        )
                except IntegrityError:
                    pass

            self.session.commit()
            return manifest

        # Fallback for SQLite in unit tests
        pending_count = self.session.scalar(
            select(func.count(CatalogImportInput.id)).where(
                CatalogImportInput.batch_id == batch_id,
                CatalogImportInput.disposition == "Pending",
            )
        )
        if pending_count and pending_count > 0:
            raise ValueError(f"IMPORT_BATCH_NOT_RECONCILED: {pending_count} pending inputs")

        rows = self.session.execute(
            select(CatalogImportInput.disposition, func.count(CatalogImportInput.id))
            .where(
                CatalogImportInput.batch_id == batch_id,
                CatalogImportInput.disposition != "Pending",
            )
            .group_by(CatalogImportInput.disposition)
        ).all()
        counts = {disp: cnt for disp, cnt in rows}
        reconciled = sum(counts.values())
        if reconciled != batch.total_inputs:
            raise ValueError(f"IMPORT_BATCH_NOT_RECONCILED: {reconciled} != {batch.total_inputs}")

        counts_json = json.dumps(counts, sort_keys=True)
        seal_raw = f"{batch.batch_key}:{batch.payload_digest.hex()}:{counts_json}".encode()
        manifest_hash = sha256(seal_raw).digest()

        manifest = CatalogImportReconciliationManifest(
            batch_id=batch_id,
            manifest_hash=manifest_hash,
            total_inputs=batch.total_inputs,
            reconciled_inputs=reconciled,
            counts_by_disposition=counts,
            sealed_by_actor_id=context.actor_id,
            sealed_at=db_time,
        )
        self.session.add(manifest)
        batch.status = "Reconciled"
        batch.reconciled_inputs = reconciled
        batch.updated_at = db_time

        # Check if seal event already recorded by concurrent execution
        existing_intent = self.session.scalar(
            select(CatalogEventIntent).where(
                CatalogEventIntent.request_key == f"batch:{batch.batch_key}:sealed",
                CatalogEventIntent.event_kind == "catalog.import.batch_sealed",
            )
        )
        if existing_intent is None:
            try:
                with self.session.begin_nested():
                    append_catalog_audit_event(
                        self.session,
                        context.actor_id,
                        "catalog.import.batch_sealed",
                        "CatalogImportBatch",
                        batch_id,
                        f"batch:{batch.batch_key}:sealed",
                        "Success",
                        {
                            "batch_key": batch.batch_key,
                            "total_inputs": manifest.total_inputs,
                            "reconciled_inputs": manifest.reconciled_inputs,
                            "manifest_hash": manifest.manifest_hash.hex(),
                        },
                        db_time,
                    )
                    record_catalog_event_intent(
                        self.session,
                        f"batch:{batch.batch_key}:sealed",
                        "catalog.import.batch_sealed",
                        batch_id,
                        "CatalogImportBatch",
                        1,
                        manifest.manifest_hash,
                        db_time,
                    )
            except IntegrityError:
                pass

        self.session.commit()
        return manifest
