"""Service layer implementing atomic business logic, concurrency control, admission, and audit logging."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext
from conformly.customer_demo.evaluator import (
    compute_answers_digest,
    compute_evaluation_digest,
    evaluate_bundle,
    normalize_answers,
)
from conformly.customer_demo.fixture import (
    EVALUATOR_VERSION,
    PACK_VERSION_V1_ID,
    PACK_VERSION_V2_ID,
    get_bundle_digest,
    get_demo_manifest,
    is_registered_pack_version,
)
from conformly.customer_demo.models import (
    CustomerDemoAdoption,
    CustomerDemoAnswers,
    CustomerDemoEvaluation,
    CustomerDemoWorkspace,
)
from conformly.customer_demo.policy import verify_customer_demo_admission


def _get_or_create_workspace_locked(session: Session, tenant_id: UUID) -> CustomerDemoWorkspace:
    """Safely initialize or retrieve the tenant workspace row under an exclusive lock."""
    # Attempt lock first
    ws = (
        session.query(CustomerDemoWorkspace)
        .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
        .with_for_update()
        .first()
    )
    if ws is not None:
        return ws

    # Insert initial workspace safely under savepoint in case of concurrent insert race
    savepoint = session.begin_nested()
    try:
        now = datetime.now(UTC)
        new_ws = CustomerDemoWorkspace(
            tenant_id=tenant_id,
            current_revision=0,
            selection_revision=0,
            created_at=now,
            updated_at=now,
        )
        session.add(new_ws)
        session.flush()
        savepoint.commit()
    except Exception:
        savepoint.rollback()

    # Re-query with exclusive lock
    ws = (
        session.query(CustomerDemoWorkspace)
        .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
        .with_for_update()
        .first()
    )
    if ws is None:
        raise RuntimeError("Failed to obtain locked workspace row")
    return ws


def get_workspace_data(
    session: Session,
    principal: Principal,
    tenant_context: TenantContext,
    request_id: str,
) -> dict[str, Any]:
    """Retrieve full workspace state and emit an audit read event after centralized admission."""
    verify_customer_demo_admission(principal, tenant_context, operation="read", session=session)
    tenant_id = tenant_context.tenant_id
    actor_id = principal.user_id

    try:
        manifest = get_demo_manifest()

        ws = (
            session.query(CustomerDemoWorkspace)
            .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
            .first()
        )
        current_rev = ws.current_revision if ws is not None else 0
        selection_rev = ws.selection_revision if ws is not None else 0

        answers_data = None
        if ws is not None and ws.current_revision > 0:
            ans_row = (
                session.query(CustomerDemoAnswers)
                .filter(
                    CustomerDemoAnswers.tenant_id == tenant_id,
                    CustomerDemoAnswers.revision == ws.current_revision,
                )
                .first()
            )
            if ans_row is not None:
                answers_data = {
                    "tenant_id": ans_row.tenant_id,
                    "revision": ans_row.revision,
                    "company_code": ans_row.company_code,
                    "answers": ans_row.answers,
                    "content_digest": ans_row.content_digest,
                    "created_at": ans_row.created_at,
                }

        selected_pack_data = None
        if ws is not None and ws.selection_revision > 0:
            adopt_row = (
                session.query(CustomerDemoAdoption)
                .filter(
                    CustomerDemoAdoption.tenant_id == tenant_id,
                    CustomerDemoAdoption.selection_revision == ws.selection_revision,
                )
                .first()
            )
            if adopt_row is not None:
                # Check if stale relative to current answer revision
                eval_row = (
                    session.query(CustomerDemoEvaluation)
                    .filter(
                        CustomerDemoEvaluation.tenant_id == tenant_id,
                        CustomerDemoEvaluation.id == adopt_row.evaluation_id,
                    )
                    .first()
                )
                is_stale = eval_row is not None and eval_row.answer_revision < ws.current_revision
                selected_pack_data = {
                    "selection_revision": adopt_row.selection_revision,
                    "evaluation_id": adopt_row.evaluation_id,
                    "pack_version_id": adopt_row.pack_version_id,
                    "bundle_digest": adopt_row.bundle_digest,
                    "created_at": adopt_row.created_at,
                    "is_stale": is_stale,
                }

        latest_evaluation_data = None
        latest_eval = (
            session.query(CustomerDemoEvaluation)
            .filter(CustomerDemoEvaluation.tenant_id == tenant_id)
            .order_by(CustomerDemoEvaluation.created_at.desc())
            .first()
        )
        if latest_eval is not None:
            latest_evaluation_data = {
                "id": latest_eval.id,
                "tenant_id": latest_eval.tenant_id,
                "answer_revision": latest_eval.answer_revision,
                "pack_version_id": latest_eval.pack_version_id,
                "bundle_digest": latest_eval.bundle_digest,
                "evaluator_version": latest_eval.evaluator_version,
                "content_digest": latest_eval.content_digest,
                "results": latest_eval.results,
                "created_at": latest_eval.created_at,
            }

        # Bounded history summary (newest 20 adoptions)
        recent_adoptions = (
            session.query(CustomerDemoAdoption)
            .filter(CustomerDemoAdoption.tenant_id == tenant_id)
            .order_by(CustomerDemoAdoption.selection_revision.desc())
            .limit(20)
            .all()
        )
        history_summary = [
            {
                "selection_revision": a.selection_revision,
                "pack_version_id": str(a.pack_version_id),
                "bundle_digest": a.bundle_digest,
                "created_at": a.created_at.isoformat(),
            }
            for a in recent_adoptions
        ]

        # Emit audit read event
        record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER if actor_id is not None else AuditActorType.SYSTEM,
            actor_id=actor_id,
            action="customer_demo.workspace.read",
            resource_type="customer_demo_workspace",
            resource_id=str(tenant_id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"revision_number": current_rev},
        )
        session.commit()

        return {
            "tenant_id": tenant_id,
            "current_revision": current_rev,
            "selection_revision": selection_rev,
            "manifest": manifest,
            "answers": answers_data,
            "selected_pack": selected_pack_data,
            "latest_evaluation": latest_evaluation_data,
            "history_summary": history_summary,
        }
    except Exception:
        session.rollback()
        raise


def save_answers(
    session: Session,
    principal: Principal,
    tenant_context: TenantContext,
    expected_revision: int,
    company_code: str,
    raw_answers: dict[str, Any],
    request_id: str,
) -> CustomerDemoAnswers:
    """Atomically validate, persist, and audit next answers revision after centralized admission."""
    verify_customer_demo_admission(principal, tenant_context, operation="mutate", session=session)
    tenant_id = tenant_context.tenant_id
    actor_id = principal.user_id

    # Validate before database writes where practical (P1)
    if not isinstance(raw_answers, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid answers payload",
        )
    try:
        normalized = normalize_answers(raw_answers)
        digest = compute_answers_digest(company_code, normalized)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid answers payload",
        )

    try:
        ws = _get_or_create_workspace_locked(session, tenant_id)

        if ws.current_revision != expected_revision:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Expected answers revision does not match current workspace revision",
            )

        new_rev = ws.current_revision + 1
        now = datetime.now(UTC)

        answers_record = CustomerDemoAnswers(
            tenant_id=tenant_id,
            revision=new_rev,
            company_code=company_code,
            answers=normalized,
            content_digest=digest,
            actor_id=actor_id,
            created_at=now,
        )
        session.add(answers_record)

        ws.current_revision = new_rev
        ws.updated_at = now

        record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=actor_id,
            action="customer_demo.answers.save",
            resource_type="customer_demo_answers",
            resource_id=str(tenant_id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "revision_number": new_rev,
                "content_digest": digest,
            },
        )
        session.commit()
        return answers_record
    except Exception:
        session.rollback()
        raise


def evaluate_answers(
    session: Session,
    principal: Principal,
    tenant_context: TenantContext,
    expected_revision: int,
    pack_version_id: UUID,
    request_id: str,
) -> CustomerDemoEvaluation:
    """Atomically evaluate the specified answer revision against a demo pack after centralized admission."""
    verify_customer_demo_admission(principal, tenant_context, operation="mutate", session=session)
    tenant_id = tenant_context.tenant_id
    actor_id = principal.user_id

    # Validate pack ID before database writes (P1)
    if not is_registered_pack_version(pack_version_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown pack version ID",
        )

    try:
        ws = _get_or_create_workspace_locked(session, tenant_id)

        if ws.current_revision == 0:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot evaluate without initial answers",
            )

        if ws.current_revision != expected_revision:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Expected answers revision does not match current workspace revision",
            )

        answers_record = (
            session.query(CustomerDemoAnswers)
            .filter(
                CustomerDemoAnswers.tenant_id == tenant_id,
                CustomerDemoAnswers.revision == expected_revision,
            )
            .first()
        )
        if answers_record is None:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Referenced answers revision not found",
            )

        results = evaluate_bundle(pack_version_id, answers_record.answers)
        bundle_digest = get_bundle_digest(pack_version_id)
        eval_digest = compute_evaluation_digest(
            answer_digest=answers_record.content_digest,
            answer_revision=expected_revision,
            pack_version_id=pack_version_id,
            bundle_digest=bundle_digest,
            results=results,
        )

        evaluation = CustomerDemoEvaluation(
            tenant_id=tenant_id,
            answer_revision=expected_revision,
            pack_version_id=pack_version_id,
            bundle_digest=bundle_digest,
            evaluator_version=EVALUATOR_VERSION,
            results=results,
            content_digest=eval_digest,
            actor_id=actor_id,
        )
        session.add(evaluation)
        session.flush()

        record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=actor_id,
            action="customer_demo.evaluation.create",
            resource_type="customer_demo_evaluations",
            resource_id=str(evaluation.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "revision_number": expected_revision,
                "content_digest": eval_digest,
                "target_version_id": str(pack_version_id),
            },
        )
        session.commit()
        return evaluation
    except Exception:
        session.rollback()
        raise


def adopt_evaluation(
    session: Session,
    principal: Principal,
    tenant_context: TenantContext,
    expected_revision: int,
    evaluation_id: UUID,
    pack_version_id: UUID,
    acknowledge_synthetic: bool,
    acknowledge_missing_information: bool,
    request_id: str,
) -> dict[str, Any]:
    """Atomically verify and adopt an evaluated demo pack snapshot under concurrency control."""
    verify_customer_demo_admission(principal, tenant_context, operation="mutate", session=session)
    tenant_id = tenant_context.tenant_id
    actor_id = principal.user_id

    # Pre-validation checks before database transaction
    if not acknowledge_synthetic:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Explicit acknowledgement of synthetic demonstration notice is required",
        )

    if not is_registered_pack_version(pack_version_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown pack version ID",
        )

    try:
        expected_bundle_digest = get_bundle_digest(pack_version_id)

        ws = _get_or_create_workspace_locked(session, tenant_id)

        if ws.current_revision != expected_revision:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: Expected answers revision does not match current workspace revision",
            )

        evaluation = (
            session.query(CustomerDemoEvaluation)
            .filter(
                CustomerDemoEvaluation.tenant_id == tenant_id,
                CustomerDemoEvaluation.id == evaluation_id,
            )
            .first()
        )
        if evaluation is None:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Referenced evaluation not found",
            )

        # R5 Verification: pack version match, evaluator version match, bundle digest match
        if evaluation.pack_version_id != pack_version_id:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pack version mismatch with evaluation",
            )

        if evaluation.evaluator_version != EVALUATOR_VERSION:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Incompatible evaluator version on evaluation snapshot",
            )

        if evaluation.bundle_digest != expected_bundle_digest:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid bundle digest on evaluation snapshot",
            )

        # R5 Verification: check referenced answers and answers content digest
        answers_record = (
            session.query(CustomerDemoAnswers)
            .filter(
                CustomerDemoAnswers.tenant_id == tenant_id,
                CustomerDemoAnswers.revision == evaluation.answer_revision,
            )
            .first()
        )
        if answers_record is None:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Referenced answers revision not found",
            )

        expected_ans_digest = compute_answers_digest(
            answers_record.company_code, answers_record.answers
        )
        if answers_record.content_digest != expected_ans_digest:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Corrupted answers content digest on referenced answers",
            )

        # Re-verify full results against deterministic evaluation of pinned pack and answers (P2)
        expected_results = evaluate_bundle(pack_version_id, answers_record.answers)
        if evaluation.results != expected_results:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Evaluation results mismatch deterministic evaluation of pinned pack and answers",
            )

        # Recompute evaluation content digest to ensure complete lineage integrity
        expected_eval_digest = compute_evaluation_digest(
            answer_digest=answers_record.content_digest,
            answer_revision=evaluation.answer_revision,
            pack_version_id=pack_version_id,
            bundle_digest=expected_bundle_digest,
            results=evaluation.results,
        )
        if evaluation.content_digest != expected_eval_digest:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Corrupted evaluation content digest or invalid lineage",
            )

        if evaluation.answer_revision != expected_revision:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Evaluation does not match current answers revision",
            )

        # Check for missing information acknowledgement requirement
        has_missing = any(r.get("result") == "NEEDS_INFORMATION" for r in evaluation.results)
        if has_missing and not acknowledge_missing_information:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Explicit acknowledgement of NEEDS_INFORMATION requirement states is required",
            )

        # Check for idempotent retry on the same evaluation
        existing = (
            session.query(CustomerDemoAdoption)
            .filter(
                CustomerDemoAdoption.tenant_id == tenant_id,
                CustomerDemoAdoption.evaluation_id == evaluation_id,
            )
            .first()
        )
        if existing is not None:
            # Find authoritative current selection
            current_adopt = (
                session.query(CustomerDemoAdoption)
                .filter(
                    CustomerDemoAdoption.tenant_id == tenant_id,
                    CustomerDemoAdoption.selection_revision == ws.selection_revision,
                )
                .first()
            )
            curr_pack_id = (
                current_adopt.pack_version_id
                if current_adopt is not None
                else existing.pack_version_id
            )
            session.commit()
            return {
                "id": existing.id,
                "tenant_id": existing.tenant_id,
                "selection_revision": existing.selection_revision,
                "evaluation_id": existing.evaluation_id,
                "pack_version_id": existing.pack_version_id,
                "bundle_digest": existing.bundle_digest,
                "created_at": existing.created_at,
                "is_current": existing.selection_revision == ws.selection_revision,
                "current_selection_revision": ws.selection_revision,
                "current_pack_version_id": curr_pack_id,
            }

        # Increment selection revision under workspace lock
        new_selection_rev = ws.selection_revision + 1
        now = datetime.now(UTC)

        adoption = CustomerDemoAdoption(
            tenant_id=tenant_id,
            evaluation_id=evaluation_id,
            pack_version_id=pack_version_id,
            bundle_digest=evaluation.bundle_digest,
            actor_id=actor_id,
            created_at=now,
            selection_revision=new_selection_rev,
        )
        session.add(adoption)

        ws.selection_revision = new_selection_rev
        ws.updated_at = now

        record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=actor_id,
            action="customer_demo.adoption.create",
            resource_type="customer_demo_adoptions",
            resource_id=str(adoption.id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "revision_number": new_selection_rev,
                "content_digest": evaluation.bundle_digest,
                "adoption_id": str(adoption.id),
                "target_version_id": str(pack_version_id),
            },
        )
        session.commit()

        return {
            "id": adoption.id,
            "tenant_id": adoption.tenant_id,
            "selection_revision": new_selection_rev,
            "evaluation_id": adoption.evaluation_id,
            "pack_version_id": adoption.pack_version_id,
            "bundle_digest": adoption.bundle_digest,
            "created_at": adoption.created_at,
            "is_current": True,
            "current_selection_revision": new_selection_rev,
            "current_pack_version_id": pack_version_id,
        }
    except Exception:
        session.rollback()
        raise
