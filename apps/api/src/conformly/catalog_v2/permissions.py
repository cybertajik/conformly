"""Effective source-use permission evaluation and decision allocation."""

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogCapability,
    CatalogInvariantError,
    CatalogPermissionDeniedError,
    CatalogSecurityError,
    CatalogValidationError,
    verify_catalog_actor,
)
from conformly.catalog_v2.models import (
    CatalogSourcePermissionDecision,
    CatalogSourcePermissionGuard,
    CatalogSourcePermissionProposal,
    CatalogSourceVersion,
)

VALID_USE_CASES = frozenset({"reference", "store", "excerpt", "paraphrase", "map"})
VALID_DECISIONS = frozenset({"Allowed", "Denied"})
DEFAULT_SCOPE_KEY = "global"


def lock_source_guard(session: Session, source_id: UUID) -> CatalogSourcePermissionGuard:
    """Lock single source permission guard FOR UPDATE."""
    stmt = (
        select(CatalogSourcePermissionGuard)
        .where(CatalogSourcePermissionGuard.source_id == source_id)
        .with_for_update()
    )
    guard = session.execute(stmt).scalar_one_or_none()
    if guard is None:
        raise CatalogInvariantError(f"Missing permission guard for source {source_id}")
    return guard


def lock_source_guards_sorted(
    session: Session, source_ids: Iterable[UUID]
) -> list[CatalogSourcePermissionGuard]:
    """Lock source permission guards sorted by UUID to prevent deadlocks."""
    unique_sorted = sorted(set(source_ids), key=lambda u: str(u))
    guards = []
    for sid in unique_sorted:
        guards.append(lock_source_guard(session, sid))
    return guards


def evaluate_effective_permission(
    session: Session,
    source_version_id: UUID,
    use_case: str,
    scope_key: str,
    db_time: datetime,
) -> CatalogSourcePermissionDecision:
    """Evaluate current effective permission decision for exact source version/use/scope.

    Must be called after locking the source guard.
    Fails closed on missing, Denied, expired, future, or non-None conditions.
    """
    if db_time.tzinfo is None:
        db_time = db_time.replace(tzinfo=UTC)

    stmt = (
        select(CatalogSourcePermissionDecision)
        .where(
            CatalogSourcePermissionDecision.source_version_id == source_version_id,
            CatalogSourcePermissionDecision.use_case == use_case,
            CatalogSourcePermissionDecision.scope_key == scope_key,
        )
        .order_by(CatalogSourcePermissionDecision.sequence.desc())
        .limit(1)
    )
    decision = session.execute(stmt).scalar_one_or_none()

    if decision is None:
        raise CatalogPermissionDeniedError(
            f"No permission decision found for version {source_version_id}, use_case '{use_case}', scope '{scope_key}'"
        )

    if decision.decision != "Allowed":
        raise CatalogPermissionDeniedError(
            f"Permission decision for {source_version_id}/{use_case} is {decision.decision}"
        )

    if decision.conditions_state != "None":
        raise CatalogPermissionDeniedError(
            f"Non-executable conditions state '{decision.conditions_state}' for {source_version_id}/{use_case}"
        )

    valid_from = decision.valid_from
    if valid_from.tzinfo is None:
        valid_from = valid_from.replace(tzinfo=UTC)

    if valid_from > db_time:
        raise CatalogPermissionDeniedError(
            f"Permission decision for {source_version_id}/{use_case} is not yet valid (valid_from: {decision.valid_from})"
        )

    if decision.valid_until is not None:
        valid_until = decision.valid_until
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=UTC)
        if db_time >= valid_until:
            raise CatalogPermissionDeniedError(
                f"Permission decision for {source_version_id}/{use_case} has expired (valid_until: {decision.valid_until})"
            )

    return decision


def has_effective_permission(
    session: Session,
    source_version_id: UUID,
    use_case: str,
    scope_key: str,
    db_time: datetime,
) -> bool:
    """Check if effective permission is granted, returning bool without raising."""
    try:
        evaluate_effective_permission(session, source_version_id, use_case, scope_key, db_time)
        return True
    except CatalogPermissionDeniedError:
        return False


def check_source_version_permissions(
    session: Session,
    source_version_id: UUID,
    use_cases: list[str],
    scope_key: str,
    db_time: datetime,
) -> list[CatalogSourcePermissionDecision]:
    """Check effective permissions for a source version against the required use cases.

    Locks the source guard and evaluates all required use cases.
    """
    version = session.get(CatalogSourceVersion, source_version_id)
    if version is None:
        raise CatalogValidationError(f"Source version {source_version_id} does not exist")

    lock_source_guard(session, version.source_id)

    decisions = []
    for uc in use_cases:
        dec = evaluate_effective_permission(session, source_version_id, uc, scope_key, db_time)
        decisions.append(dec)
    return decisions


def create_source_permission_decision(
    session: Session,
    context: CatalogActorContext,
    source_id: UUID,
    source_version_id: UUID,
    proposal_id: UUID,
    use_case: str,
    scope_key: str,
    decision_type: str,
    valid_from: datetime,
    valid_until: datetime | None,
    evidence_reference: str,
    db_time: datetime,
) -> CatalogSourcePermissionDecision:
    """Create and append an immutable reviewed permission decision."""
    verify_catalog_actor(context, CatalogCapability.PERMISSION_DECIDE, db_time)

    if use_case not in VALID_USE_CASES:
        raise CatalogValidationError(f"Unknown use_case: {use_case}")
    if decision_type not in VALID_DECISIONS:
        raise CatalogValidationError(f"Unknown decision: {decision_type}")
    if not evidence_reference:
        raise CatalogValidationError("evidence_reference is required")
    if valid_until is not None and valid_until <= valid_from:
        raise CatalogValidationError("valid_until must be strictly after valid_from")

    # 1. Lock source guard FOR UPDATE
    guard = lock_source_guard(session, source_id)

    # 2. Reread proposal and verify lineage & author separation
    proposal = session.get(CatalogSourcePermissionProposal, proposal_id)
    if proposal is None:
        raise CatalogValidationError(f"Proposal {proposal_id} does not exist")
    if proposal.source_version_id != source_version_id:
        raise CatalogSecurityError("Proposal source_version_id mismatch")
    if proposal.use_case != use_case:
        raise CatalogValidationError(
            f"Proposal use_case mismatch: expected {use_case}, proposal has {proposal.use_case}"
        )
    if proposal.scope_key != scope_key:
        raise CatalogValidationError(
            f"Proposal scope_key mismatch: expected {scope_key}, proposal has {proposal.scope_key}"
        )

    sv = session.get(CatalogSourceVersion, source_version_id)
    if sv is None or sv.source_id != source_id:
        raise CatalogSecurityError("Source version does not belong to specified source_id")

    if proposal.recorded_by_actor_id == context.actor_id:
        raise CatalogSecurityError(
            "Decision actor cannot be the proposal recorder (two-person rule)"
        )

    # 3. Get latest decision in scope for gap-free sequence allocation
    stmt = (
        select(CatalogSourcePermissionDecision)
        .where(
            CatalogSourcePermissionDecision.source_version_id == source_version_id,
            CatalogSourcePermissionDecision.use_case == use_case,
            CatalogSourcePermissionDecision.scope_key == scope_key,
        )
        .order_by(CatalogSourcePermissionDecision.sequence.desc())
        .limit(1)
    )
    prior = session.execute(stmt).scalar_one_or_none()

    if prior is None:
        next_seq = 1
        predecessor_id = None
    else:
        next_seq = prior.sequence + 1
        predecessor_id = prior.id

    # 4. Increment guard revision
    guard.revision += 1
    guard.updated_at = db_time

    # 5. Create decision row
    decision = CatalogSourcePermissionDecision(
        source_id=source_id,
        source_version_id=source_version_id,
        proposal_id=proposal_id,
        use_case=use_case,
        scope_key=scope_key,
        sequence=next_seq,
        predecessor_id=predecessor_id,
        decision=decision_type,
        conditions_state="None",
        valid_from=valid_from,
        valid_until=valid_until,
        decided_by_actor_id=context.actor_id,
        decided_at=db_time,
        evidence_reference=evidence_reference,
        policy_version="catalog-permission-v1",
        guard_revision=guard.revision,
    )
    session.add(decision)
    session.flush()
    return decision
