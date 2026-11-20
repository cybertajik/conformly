"""Controlled internal Draft catalog service implementing authorized platform operations."""

import logging
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CursorResult, and_, func, or_, select, text, update
from sqlalchemy.orm import Session, aliased

from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogCapability,
    CatalogConflictError,
    CatalogError,
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
    check_or_record_mutation_receipt,
    record_catalog_event_intent,
)
from conformly.catalog_v2.digest import (
    DIGEST_SCHEMA_V1,
    compute_content_digest,
    compute_control_version_digest,
    compute_mapping_version_digest,
    compute_pack_version_digest,
    compute_requirement_version_digest,
    compute_source_version_digest,
)
from conformly.catalog_v2.models import (
    CatalogCommonControl,
    CatalogControlVersion,
    CatalogMappingVersion,
    CatalogPack,
    CatalogPackMembership,
    CatalogPackVersion,
    CatalogPublisher,
    CatalogRequirement,
    CatalogRequirementControlMapping,
    CatalogRequirementSourceReference,
    CatalogRequirementVersion,
    CatalogSource,
    CatalogSourcePermissionDecision,
    CatalogSourcePermissionGuard,
    CatalogSourceVersion,
)
from conformly.catalog_v2.permissions import (
    DEFAULT_SCOPE_KEY,
    create_source_permission_decision,
    evaluate_effective_permission,
    lock_source_guard,
    lock_source_guards_sorted,
)

logger = logging.getLogger(__name__)


def _effective_permission_sql_filter(
    source_version_id_expr: Any,
    use_case: str,
    db_time: datetime,
    scope_key: str = DEFAULT_SCOPE_KEY,
) -> Any:
    """Build an EXISTS condition verifying active, effective Allowed permission in SQL."""
    d = aliased(CatalogSourcePermissionDecision)
    d2 = aliased(CatalogSourcePermissionDecision)
    max_seq_subq = (
        select(func.max(d2.sequence))
        .where(
            d2.source_version_id == d.source_version_id,
            d2.use_case == d.use_case,
            d2.scope_key == d.scope_key,
        )
        .correlate(d)
        .scalar_subquery()
    )
    active_cond = and_(
        d.source_version_id == source_version_id_expr,
        d.use_case == use_case,
        d.scope_key == scope_key,
        d.decision == "Allowed",
        d.conditions_state == "None",
        d.valid_from <= db_time,
        or_(d.valid_until.is_(None), d.valid_until > db_time),
        d.sequence == max_seq_subq,
    )
    return select(1).select_from(d).where(active_cond).exists()


class CatalogDraftService:
    """Internal platform-only service for managing Draft catalog aggregates."""

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
        self.last_denial_audit_error: Exception | None = None

    def _get_db_time(self) -> datetime:
        """Fetch current database clock_timestamp with timezone. Fails closed."""
        try:
            dialect = self.session.bind.dialect.name if self.session.bind else ""
            if dialect == "sqlite":
                raw = self.session.execute(
                    text("SELECT strftime('%Y-%m-%d %H:%M:%f', 'now')")
                ).scalar()
                if isinstance(raw, str):
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
                elif isinstance(raw, datetime):
                    return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
            else:
                val = self.session.execute(text("SELECT clock_timestamp()")).scalar()
                if isinstance(val, datetime):
                    return val if val.tzinfo else val.replace(tzinfo=UTC)
        except Exception as e:
            raise CatalogSecurityError(
                f"Unable to establish trusted database time for catalog operation: {e}"
            ) from e
        raise CatalogSecurityError(
            "Unable to establish trusted database time for catalog operation"
        )

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
        except Exception as rb_err:
            logger.warning("Failed to rollback domain session prior to denial audit: %s", rb_err)
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
            except Exception as audit_err:
                self.last_denial_audit_error = audit_err
                logger.error("Denial audit sink failure: %s", audit_err, exc_info=True)

    # -------------------------------------------------------------------------
    # Publishers and Sources
    # -------------------------------------------------------------------------

    def create_publisher(
        self,
        context: CatalogActorContext,
        request_key: str,
        publisher_key: str,
        name: str,
        *args: Any,
        **kwargs: Any,
    ) -> CatalogPublisher:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "create_publisher",
                type(e).__name__,
                request_key,
            )
            raise

        req_data = {
            "name": name,
            "publisher_key": publisher_key,
        }

        def _do_write() -> tuple[UUID, str, int, bytes]:
            pub = CatalogPublisher(
                publisher_key=publisher_key,
                name=name,
                status="Draft",
            )
            self.session.add(pub)
            self.session.flush()
            digest = compute_content_digest({"name": name, "publisher_key": publisher_key})
            return (pub.id, "CatalogPublisher", 1, digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "create_publisher",
            request_key,
            req_data,
            _do_write,
            db_time,
        )
        if is_retry:
            pub = self.session.get(CatalogPublisher, receipt.result_id)
            if pub is None:
                raise CatalogNotFoundError("Publisher not found on retry")
            return pub

        pub = self.session.get(CatalogPublisher, receipt.result_id)
        assert pub is not None

        record_catalog_event_intent(
            self.session,
            request_key,
            "publisher.created",
            pub.id,
            "CatalogPublisher",
            1,
            receipt.result_digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "publisher.created",
            "CatalogPublisher",
            pub.id,
            request_key,
            "Success",
            {"publisher_key": publisher_key},
            db_time,
        )
        self.session.flush()
        return pub

    def create_source(
        self,
        context: CatalogActorContext,
        request_key: str,
        publisher_id: UUID,
        source_key: str,
        title: str,
        *args: Any,
        **kwargs: Any,
    ) -> CatalogSource:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "create_source",
                type(e).__name__,
                request_key,
            )
            raise

        pub = self.session.get(CatalogPublisher, publisher_id)
        if pub is None:
            raise CatalogValidationError(f"Publisher {publisher_id} does not exist")

        req_data = {
            "publisher_id": publisher_id,
            "source_key": source_key,
            "title": title,
        }

        def _do_write() -> tuple[UUID, str, int, bytes]:
            src = CatalogSource(
                publisher_id=publisher_id,
                source_key=source_key,
                title=title,
                status="Draft",
            )
            self.session.add(src)
            self.session.flush()

            # Create source permission guard in the same transaction
            guard = CatalogSourcePermissionGuard(source_id=src.id, revision=1, updated_at=db_time)
            self.session.add(guard)
            self.session.flush()

            digest = compute_content_digest(
                {"publisher_id": publisher_id, "source_key": source_key, "title": title}
            )
            return (src.id, "CatalogSource", 1, digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "create_source",
            request_key,
            req_data,
            _do_write,
            db_time,
        )
        if is_retry:
            src = self.session.get(CatalogSource, receipt.result_id)
            if src is None:
                raise CatalogNotFoundError("Source not found on retry")
            return src

        src = self.session.get(CatalogSource, receipt.result_id)
        assert src is not None

        record_catalog_event_intent(
            self.session,
            request_key,
            "source.created",
            src.id,
            "CatalogSource",
            1,
            receipt.result_digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "source.created",
            "CatalogSource",
            src.id,
            request_key,
            "Success",
            {"source_key": source_key},
            db_time,
        )
        self.session.flush()
        return src

    def create_source_version(
        self,
        context: CatalogActorContext,
        request_key: str,
        source_id: UUID,
        edition: str,
        predecessor_id: UUID | None = None,
        language: str | None = None,
        official_locator: str | None = None,
        publication_date: date | None = None,
        retrieved_at: datetime | None = None,
    ) -> CatalogSourceVersion:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "create_source_version",
                type(e).__name__,
                request_key,
            )
            raise

        src = self.session.get(CatalogSource, source_id)
        if src is None:
            raise CatalogValidationError(f"Source {source_id} does not exist")

        req_data = {
            "edition": edition,
            "language": language,
            "official_locator": official_locator,
            "predecessor_id": predecessor_id,
            "publication_date": publication_date,
            "retrieved_at": retrieved_at,
            "source_id": source_id,
        }

        # Lock source guard
        lock_source_guard(self.session, source_id)

        digest = compute_source_version_digest(
            source_id=source_id,
            edition=edition,
            predecessor_id=predecessor_id,
            language=language,
            official_locator=official_locator,
            publication_date=publication_date,
            retrieved_at=retrieved_at,
            status="Draft",
        )

        def _do_write() -> tuple[UUID, str, int, bytes]:
            ver = CatalogSourceVersion(
                source_id=source_id,
                edition=edition,
                predecessor_id=predecessor_id,
                language=language,
                official_locator=official_locator,
                publication_date=publication_date,
                retrieved_at=retrieved_at,
                content_digest=digest,
                digest_schema=DIGEST_SCHEMA_V1,
                status="Draft",
            )
            self.session.add(ver)
            self.session.flush()
            return (ver.id, "CatalogSourceVersion", ver.revision, digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "create_source_version",
            request_key,
            req_data,
            _do_write,
            db_time,
        )
        if is_retry:
            ver = self.session.get(CatalogSourceVersion, receipt.result_id)
            if ver is None:
                raise CatalogNotFoundError("Source version not found on retry")
            return ver

        ver = self.session.get(CatalogSourceVersion, receipt.result_id)
        assert ver is not None

        record_catalog_event_intent(
            self.session,
            request_key,
            "source_version.created",
            ver.id,
            "CatalogSourceVersion",
            ver.revision,
            digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "source_version.created",
            "CatalogSourceVersion",
            ver.id,
            request_key,
            "Success",
            {"edition": edition, "source_id": str(source_id)},
            db_time,
        )
        self.session.flush()
        return ver

    def update_source_version(
        self,
        context: CatalogActorContext,
        request_key: str,
        version_id: UUID,
        expected_revision: int,
        expected_digest: bytes,
        edition: str,
        language: str | None = None,
        official_locator: str | None = None,
        publication_date: date | None = None,
        retrieved_at: datetime | None = None,
    ) -> CatalogSourceVersion:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "update_source_version",
                type(e).__name__,
                request_key,
                "CatalogSourceVersion",
                version_id,
            )
            raise

        ver = self.session.get(CatalogSourceVersion, version_id)
        if ver is None:
            raise CatalogNotFoundError(f"Source version {version_id} not found")

        lock_source_guard(self.session, ver.source_id)

        # Permission verification for mutating source version content
        evaluate_effective_permission(self.session, ver.id, "store", DEFAULT_SCOPE_KEY, db_time)

        # Concurrency verification
        if ver.revision != expected_revision:
            raise CatalogConflictError(
                f"Source version revision conflict: expected {expected_revision}, current {ver.revision}"
            )
        if ver.content_digest != expected_digest:
            raise CatalogConflictError("Source version content digest conflict")

        req_data = {
            "edition": edition,
            "expected_digest": expected_digest,
            "expected_revision": expected_revision,
            "language": language,
            "official_locator": official_locator,
            "publication_date": publication_date,
            "retrieved_at": retrieved_at,
            "version_id": version_id,
        }

        new_digest = compute_source_version_digest(
            source_id=ver.source_id,
            edition=edition,
            predecessor_id=ver.predecessor_id,
            language=language,
            official_locator=official_locator,
            publication_date=publication_date,
            retrieved_at=retrieved_at,
            status=ver.status,
        )

        def _do_write() -> tuple[UUID, str, int, bytes]:
            res = self.session.execute(
                update(CatalogSourceVersion)
                .where(
                    CatalogSourceVersion.id == version_id,
                    CatalogSourceVersion.revision == expected_revision,
                    CatalogSourceVersion.content_digest == expected_digest,
                )
                .values(
                    edition=edition,
                    language=language,
                    official_locator=official_locator,
                    publication_date=publication_date,
                    retrieved_at=retrieved_at,
                    revision=expected_revision + 1,
                    content_digest=new_digest,
                    updated_at=db_time,
                )
            )
            rowcount = (
                res.rowcount if isinstance(res, CursorResult) else getattr(res, "rowcount", 0)
            )
            if rowcount != 1:
                raise CatalogConflictError(
                    f"Source version update conflict for {version_id}: revision/digest mismatch or concurrent update"
                )
            self.session.flush()
            return (ver.id, "CatalogSourceVersion", expected_revision + 1, new_digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "update_source_version",
            request_key,
            req_data,
            _do_write,
            db_time,
        )
        if is_retry:
            return ver

        record_catalog_event_intent(
            self.session,
            request_key,
            "source_version.updated",
            ver.id,
            "CatalogSourceVersion",
            ver.revision,
            new_digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "source_version.updated",
            "CatalogSourceVersion",
            ver.id,
            request_key,
            "Success",
            {"edition": edition, "revision": ver.revision},
            db_time,
        )
        self.session.flush()
        return ver

    # -------------------------------------------------------------------------
    # Requirements and Controls
    # -------------------------------------------------------------------------

    def create_requirement(
        self,
        context: CatalogActorContext,
        request_key: str,
        source_id: UUID,
        requirement_key: str,
        *args: Any,
        **kwargs: Any,
    ) -> CatalogRequirement:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "create_requirement",
                type(e).__name__,
                request_key,
            )
            raise

        src = self.session.get(CatalogSource, source_id)
        if src is None:
            raise CatalogValidationError(f"Source {source_id} does not exist")

        req_data = {
            "requirement_key": requirement_key,
            "source_id": source_id,
        }

        def _do_write() -> tuple[UUID, str, int, bytes]:
            req = CatalogRequirement(
                source_id=source_id,
                requirement_key=requirement_key,
                status="Draft",
            )
            self.session.add(req)
            self.session.flush()
            digest = compute_content_digest(
                {"requirement_key": requirement_key, "source_id": source_id}
            )
            return (req.id, "CatalogRequirement", 1, digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "create_requirement",
            request_key,
            req_data,
            _do_write,
            db_time,
        )
        if is_retry:
            req = self.session.get(CatalogRequirement, receipt.result_id)
            if req is None:
                raise CatalogNotFoundError("Requirement not found on retry")
            return req

        req = self.session.get(CatalogRequirement, receipt.result_id)
        assert req is not None

        record_catalog_event_intent(
            self.session,
            request_key,
            "requirement.created",
            req.id,
            "CatalogRequirement",
            1,
            receipt.result_digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "requirement.created",
            "CatalogRequirement",
            req.id,
            request_key,
            "Success",
            {"requirement_key": requirement_key},
            db_time,
        )
        self.session.flush()
        return req

    def create_requirement_version(
        self,
        context: CatalogActorContext,
        request_key: str,
        requirement_id: UUID,
        source_version_id: UUID,
        version_label: str,
        normalized_outcome: str,
        requirement_type: str,
        obligated_actor: str,
        text_origin: str,
        source_references: list[dict[str, Any]],
        predecessor_id: UUID | None = None,
        customer_display_text: str | None = None,
        effective_from: date | None = None,
        effective_until: date | None = None,
    ) -> CatalogRequirementVersion:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "create_requirement_version",
                type(e).__name__,
                request_key,
            )
            raise

        if not source_references:
            raise CatalogValidationError(
                "RequirementVersion requires at least one source reference"
            )

        req = self.session.get(CatalogRequirement, requirement_id)
        if req is None:
            raise CatalogValidationError(f"Requirement {requirement_id} does not exist")

        sv_owner = self.session.get(CatalogSourceVersion, source_version_id)
        if sv_owner is None:
            raise CatalogValidationError(f"Source version {source_version_id} does not exist")
        if sv_owner.source_id != req.source_id:
            raise CatalogValidationError(
                "Source version does not match requirement's source_id lineage"
            )

        # Verify permissions on each source reference
        source_ids = {req.source_id}
        for ref in source_references:
            sv_id = ref.get("source_version_id")
            if not sv_id:
                raise CatalogValidationError("source_version_id required in reference")
            sv = self.session.get(CatalogSourceVersion, sv_id)
            if sv is None:
                raise CatalogValidationError(f"Source version {sv_id} does not exist")
            source_ids.add(sv.source_id)

        # Lock source guards
        lock_source_guards_sorted(self.session, source_ids)

        try:
            for ref in source_references:
                sv_id = ref["source_version_id"]
                needed = ["reference"]
                if ref.get("verbatim_text"):
                    needed.extend(["store", "excerpt"])
                if ref.get("normalized_text"):
                    needed.extend(["store", "paraphrase"])

                for uc in needed:
                    evaluate_effective_permission(
                        self.session, sv_id, uc, DEFAULT_SCOPE_KEY, db_time
                    )
        except CatalogPermissionDeniedError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "create_requirement_version",
                type(e).__name__,
                request_key,
                resource_type="requirement_version",
            )
            raise

        req_data = {
            "customer_display_text": customer_display_text,
            "effective_from": effective_from,
            "effective_until": effective_until,
            "normalized_outcome": normalized_outcome,
            "obligated_actor": obligated_actor,
            "predecessor_id": predecessor_id,
            "requirement_id": requirement_id,
            "requirement_type": requirement_type,
            "source_references": source_references,
            "source_version_id": source_version_id,
            "text_origin": text_origin,
            "version_label": version_label,
        }

        digest = compute_requirement_version_digest(
            requirement_id=requirement_id,
            source_id=req.source_id,
            source_version_id=source_version_id,
            version_label=version_label,
            predecessor_id=predecessor_id,
            revision=1,
            normalized_outcome=normalized_outcome,
            requirement_type=requirement_type,
            obligated_actor=obligated_actor,
            text_origin=text_origin,
            customer_display_text=customer_display_text,
            effective_from=effective_from,
            effective_until=effective_until,
            source_references=source_references,
            status="Draft",
        )

        def _do_write() -> tuple[UUID, str, int, bytes]:
            rv = CatalogRequirementVersion(
                requirement_id=requirement_id,
                source_id=req.source_id,
                source_version_id=source_version_id,
                version_label=version_label,
                predecessor_id=predecessor_id,
                revision=1,
                normalized_outcome=normalized_outcome,
                requirement_type=requirement_type,
                obligated_actor=obligated_actor,
                text_origin=text_origin,
                customer_display_text=customer_display_text,
                effective_from=effective_from,
                effective_until=effective_until,
                content_digest=digest,
                digest_schema=DIGEST_SCHEMA_V1,
                status="Draft",
            )
            self.session.add(rv)
            self.session.flush()

            for i, ref in enumerate(source_references):
                ref_obj = CatalogRequirementSourceReference(
                    requirement_version_id=rv.id,
                    source_version_id=ref["source_version_id"],
                    locator_kind=ref.get("locator_kind", "section"),
                    locator_value=ref.get("locator_value", ref.get("locator", "Section 1")),
                    sequence=ref.get("sequence", i + 1),
                )
                self.session.add(ref_obj)

            self.session.flush()
            return (rv.id, "CatalogRequirementVersion", 1, digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "create_requirement_version",
            request_key,
            req_data,
            _do_write,
            db_time,
        )
        if is_retry:
            rv = self.session.get(CatalogRequirementVersion, receipt.result_id)
            if rv is None:
                raise CatalogNotFoundError("Requirement version not found on retry")
            return rv

        rv = self.session.get(CatalogRequirementVersion, receipt.result_id)
        assert rv is not None

        record_catalog_event_intent(
            self.session,
            request_key,
            "requirement_version.created",
            rv.id,
            "CatalogRequirementVersion",
            1,
            digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "requirement_version.created",
            "CatalogRequirementVersion",
            rv.id,
            request_key,
            "Success",
            {"requirement_id": str(requirement_id), "version_label": version_label},
            db_time,
        )
        self.session.flush()
        return rv

    def replace_requirement_source_references(
        self,
        context: CatalogActorContext,
        request_key: str,
        version_id: UUID,
        expected_revision: int,
        expected_digest: bytes,
        new_source_references: list[dict[str, Any]],
    ) -> CatalogRequirementVersion:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "replace_requirement_source_references",
                type(e).__name__,
                request_key,
                "CatalogRequirementVersion",
                version_id,
            )
            raise

        if not new_source_references:
            raise CatalogValidationError("At least one source reference is required")

        rv = self.session.get(CatalogRequirementVersion, version_id)
        if rv is None:
            raise CatalogNotFoundError(f"Requirement version {version_id} not found")

        # Concurrency verification
        if rv.revision != expected_revision:
            raise CatalogConflictError(
                f"Requirement version revision conflict: expected {expected_revision}, current {rv.revision}"
            )
        if rv.content_digest != expected_digest:
            raise CatalogConflictError("Requirement version content digest conflict")

        # Lock guards and evaluate permissions for new references
        source_ids = {rv.source_id}
        for ref in new_source_references:
            sv_id = ref.get("source_version_id")
            if not sv_id:
                raise CatalogValidationError("source_version_id required in reference")
            sv = self.session.get(CatalogSourceVersion, sv_id)
            if sv is None:
                raise CatalogValidationError(f"Source version {sv_id} does not exist")
            source_ids.add(sv.source_id)

        lock_source_guards_sorted(self.session, source_ids)

        try:
            for ref in new_source_references:
                sv_id = ref["source_version_id"]
                needed = ["reference"]
                if ref.get("verbatim_text"):
                    needed.extend(["store", "excerpt"])
                if ref.get("normalized_text"):
                    needed.extend(["store", "paraphrase"])
                for uc in needed:
                    evaluate_effective_permission(
                        self.session, sv_id, uc, DEFAULT_SCOPE_KEY, db_time
                    )
        except CatalogPermissionDeniedError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "replace_requirement_source_references",
                type(e).__name__,
                request_key,
                resource_type="requirement_version",
                resource_id=version_id,
            )
            raise

        req_data = {
            "expected_digest": expected_digest,
            "expected_revision": expected_revision,
            "new_source_references": new_source_references,
            "version_id": version_id,
        }

        new_digest = compute_requirement_version_digest(
            requirement_id=rv.requirement_id,
            source_id=rv.source_id,
            source_version_id=rv.source_version_id,
            version_label=rv.version_label,
            predecessor_id=rv.predecessor_id,
            revision=rv.revision + 1,
            normalized_outcome=rv.normalized_outcome,
            requirement_type=rv.requirement_type,
            obligated_actor=rv.obligated_actor,
            text_origin=rv.text_origin,
            customer_display_text=rv.customer_display_text,
            effective_from=rv.effective_from,
            effective_until=rv.effective_until,
            source_references=new_source_references,
            status=rv.status,
        )

        def _do_write() -> tuple[UUID, str, int, bytes]:
            bind = self.session.get_bind()
            if bind is not None and bind.dialect.name == "postgresql":
                self.session.execute(
                    text("SELECT public.catalog_delete_requirement_source_references(:vid)"),
                    {"vid": version_id},
                )
            else:
                existing_refs = (
                    self.session.execute(
                        select(CatalogRequirementSourceReference).where(
                            CatalogRequirementSourceReference.requirement_version_id == version_id
                        )
                    )
                    .scalars()
                    .all()
                )
                for er in existing_refs:
                    self.session.delete(er)
                self.session.flush()

            for i, ref in enumerate(new_source_references):
                ref_obj = CatalogRequirementSourceReference(
                    requirement_version_id=version_id,
                    source_version_id=ref["source_version_id"],
                    locator_kind=ref.get("locator_kind", "section"),
                    locator_value=ref.get("locator_value", ref.get("locator", "Section 1")),
                    sequence=ref.get("sequence", i + 1),
                )
                self.session.add(ref_obj)

            res = self.session.execute(
                update(CatalogRequirementVersion)
                .where(
                    CatalogRequirementVersion.id == version_id,
                    CatalogRequirementVersion.revision == expected_revision,
                    CatalogRequirementVersion.content_digest == expected_digest,
                )
                .values(
                    revision=expected_revision + 1,
                    content_digest=new_digest,
                    updated_at=db_time,
                )
            )
            rowcount = (
                res.rowcount if isinstance(res, CursorResult) else getattr(res, "rowcount", 0)
            )
            if rowcount != 1:
                raise CatalogConflictError(
                    f"Requirement version references update conflict for {version_id}: revision/digest mismatch or concurrent update"
                )
            self.session.flush()
            return (rv.id, "CatalogRequirementVersion", expected_revision + 1, new_digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "replace_requirement_source_references",
            request_key,
            req_data,
            _do_write,
            db_time,
        )
        if is_retry:
            return rv

        record_catalog_event_intent(
            self.session,
            request_key,
            "requirement_version.references_replaced",
            rv.id,
            "CatalogRequirementVersion",
            rv.revision,
            new_digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "requirement_version.references_replaced",
            "CatalogRequirementVersion",
            rv.id,
            request_key,
            "Success",
            {"revision": rv.revision},
            db_time,
        )
        self.session.flush()
        return rv

    def create_common_control(
        self,
        context: CatalogActorContext,
        request_key: str,
        control_key: str,
        domain: str,
        *args: Any,
        **kwargs: Any,
    ) -> CatalogCommonControl:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "create_common_control",
                type(e).__name__,
                request_key,
            )
            raise

        req_data = {
            "control_key": control_key,
            "domain": domain,
        }

        def _do_write() -> tuple[UUID, str, int, bytes]:
            ctrl = CatalogCommonControl(
                control_key=control_key,
                domain=domain,
                status="Draft",
            )
            self.session.add(ctrl)
            self.session.flush()
            digest = compute_content_digest({"control_key": control_key, "domain": domain})
            return (ctrl.id, "CatalogCommonControl", 1, digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "create_common_control",
            request_key,
            req_data,
            _do_write,
            db_time,
        )
        if is_retry:
            ctrl = self.session.get(CatalogCommonControl, receipt.result_id)
            if ctrl is None:
                raise CatalogNotFoundError("Common control not found on retry")
            return ctrl

        ctrl = self.session.get(CatalogCommonControl, receipt.result_id)
        assert ctrl is not None

        record_catalog_event_intent(
            self.session,
            request_key,
            "common_control.created",
            ctrl.id,
            "CatalogCommonControl",
            1,
            receipt.result_digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "common_control.created",
            "CatalogCommonControl",
            ctrl.id,
            request_key,
            "Success",
            {"control_key": control_key},
            db_time,
        )
        self.session.flush()
        return ctrl

    def create_control_version(
        self,
        context: CatalogActorContext,
        request_key: str,
        control_id: UUID,
        version_label: str,
        title: str,
        objective: str,
        control_type: str = "preventive",
        frequency: str = "continuous",
        automation_level: str = "automated",
        suggested_owner_role: str = "Compliance Officer",
        assurance_level: str = "foundational",
        predecessor_id: UUID | None = None,
        guidance: str | None = None,
        tags_state: str = "None",
        tags: str | None = None,
    ) -> CatalogControlVersion:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "create_control_version",
                type(e).__name__,
                request_key,
            )
            raise

        ctrl = self.session.get(CatalogCommonControl, control_id)
        if ctrl is None:
            raise CatalogValidationError(f"Common control {control_id} does not exist")

        req_data = {
            "assurance_level": assurance_level,
            "automation_level": automation_level,
            "control_id": control_id,
            "control_type": control_type,
            "frequency": frequency,
            "guidance": guidance,
            "objective": objective,
            "predecessor_id": predecessor_id,
            "suggested_owner_role": suggested_owner_role,
            "tags": tags,
            "tags_state": tags_state,
            "title": title,
            "version_label": version_label,
        }

        digest = compute_control_version_digest(
            control_id=control_id,
            version_label=version_label,
            predecessor_id=predecessor_id,
            revision=1,
            title=title,
            objective=objective,
            guidance=guidance,
            control_type=control_type,
            frequency=frequency,
            automation_level=automation_level,
            suggested_owner_role=suggested_owner_role,
            assurance_level=assurance_level,
            tags_state=tags_state,
            tags=tags,
            status="Draft",
        )

        def _do_write() -> tuple[UUID, str, int, bytes]:
            cv = CatalogControlVersion(
                control_id=control_id,
                version_label=version_label,
                predecessor_id=predecessor_id,
                revision=1,
                title=title,
                objective=objective,
                guidance=guidance,
                control_type=control_type,
                frequency=frequency,
                automation_level=automation_level,
                suggested_owner_role=suggested_owner_role,
                assurance_level=assurance_level,
                tags_state=tags_state,
                tags=tags,
                content_digest=digest,
                digest_schema=DIGEST_SCHEMA_V1,
                status="Draft",
            )
            self.session.add(cv)
            self.session.flush()
            return (cv.id, "CatalogControlVersion", 1, digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "create_control_version",
            request_key,
            req_data,
            _do_write,
            db_time,
        )
        if is_retry:
            cv = self.session.get(CatalogControlVersion, receipt.result_id)
            if cv is None:
                raise CatalogNotFoundError("Control version not found on retry")
            return cv

        cv = self.session.get(CatalogControlVersion, receipt.result_id)
        assert cv is not None

        record_catalog_event_intent(
            self.session,
            request_key,
            "control_version.created",
            cv.id,
            "CatalogControlVersion",
            1,
            digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "control_version.created",
            "CatalogControlVersion",
            cv.id,
            request_key,
            "Success",
            {"control_id": str(control_id), "version_label": version_label},
            db_time,
        )
        self.session.flush()
        return cv

    # -------------------------------------------------------------------------
    # Mappings
    # -------------------------------------------------------------------------

    def create_mapping(
        self,
        context: CatalogActorContext,
        request_key: str,
        requirement_id: UUID,
        control_id: UUID,
        mapping_key: str | None = None,
    ) -> CatalogRequirementControlMapping:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "create_mapping",
                type(e).__name__,
                request_key,
            )
            raise

        req = self.session.get(CatalogRequirement, requirement_id)
        if req is None:
            raise CatalogValidationError(f"Requirement {requirement_id} does not exist")
        ctrl = self.session.get(CatalogCommonControl, control_id)
        if ctrl is None:
            raise CatalogValidationError(f"Control {control_id} does not exist")

        effective_key = mapping_key or f"map-{req.requirement_key}-{ctrl.control_key}".lower()

        req_data = {
            "control_id": control_id,
            "mapping_key": effective_key,
            "requirement_id": requirement_id,
        }

        def _do_write() -> tuple[UUID, str, int, bytes]:
            m = CatalogRequirementControlMapping(
                mapping_key=effective_key,
                requirement_id=requirement_id,
                control_id=control_id,
                status="Draft",
            )
            self.session.add(m)
            self.session.flush()
            digest = compute_content_digest({"mapping_key": effective_key})
            return (m.id, "CatalogRequirementControlMapping", 1, digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "create_mapping",
            request_key,
            req_data,
            _do_write,
            db_time,
        )
        if is_retry:
            m = self.session.get(CatalogRequirementControlMapping, receipt.result_id)
            if m is None:
                raise CatalogNotFoundError("Mapping not found on retry")
            return m

        m = self.session.get(CatalogRequirementControlMapping, receipt.result_id)
        assert m is not None

        record_catalog_event_intent(
            self.session,
            request_key,
            "mapping.created",
            m.id,
            "CatalogRequirementControlMapping",
            1,
            receipt.result_digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "mapping.created",
            "CatalogRequirementControlMapping",
            m.id,
            request_key,
            "Success",
            {"mapping_key": effective_key},
            db_time,
        )
        self.session.flush()
        return m

    def create_mapping_version(
        self,
        context: CatalogActorContext,
        request_key: str,
        mapping_id: UUID,
        requirement_version_id: UUID,
        control_version_id: UUID,
        expected_req_revision: int,
        expected_req_digest: bytes,
        expected_ctrl_revision: int,
        expected_ctrl_digest: bytes,
        version_label: str,
        mapping_type: str,
        rationale: str,
        source_basis: str,
        confidence: str,
        predecessor_id: UUID | None = None,
        covered_dimensions: str | None = None,
        excluded_dimensions: str | None = None,
        conditions: str | None = None,
    ) -> CatalogMappingVersion:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "create_mapping_version",
                type(e).__name__,
                request_key,
            )
            raise

        m = self.session.get(CatalogRequirementControlMapping, mapping_id)
        if m is None:
            raise CatalogValidationError(f"Mapping {mapping_id} does not exist")

        # Verify requirement version pin
        rv = self.session.get(CatalogRequirementVersion, requirement_version_id)
        if rv is None or rv.requirement_id != m.requirement_id:
            raise CatalogValidationError("Requirement version mismatch")
        if rv.revision != expected_req_revision:
            raise CatalogConflictError(
                f"Pinned requirement version revision mismatch: expected {expected_req_revision}, got {rv.revision}"
            )
        if rv.content_digest != expected_req_digest:
            raise CatalogConflictError("Pinned requirement version digest mismatch")

        # Verify control version pin
        cv = self.session.get(CatalogControlVersion, control_version_id)
        if cv is None or cv.control_id != m.control_id:
            raise CatalogValidationError("Control version mismatch")
        if cv.revision != expected_ctrl_revision:
            raise CatalogConflictError(
                f"Pinned control version revision mismatch: expected {expected_ctrl_revision}, got {cv.revision}"
            )
        if cv.content_digest != expected_ctrl_digest:
            raise CatalogConflictError("Pinned control version digest mismatch")

        # Check permission: mapping a requirement requires ['reference', 'map'] on requirement's source versions
        req_obj = self.session.get(CatalogRequirement, m.requirement_id)
        assert req_obj is not None
        lock_source_guard(self.session, req_obj.source_id)

        # Evaluate effective permission for each source version referenced
        refs = (
            self.session.execute(
                select(CatalogRequirementSourceReference).where(
                    CatalogRequirementSourceReference.requirement_version_id
                    == requirement_version_id
                )
            )
            .scalars()
            .all()
        )
        try:
            for ref in refs:
                evaluate_effective_permission(
                    self.session, ref.source_version_id, "reference", DEFAULT_SCOPE_KEY, db_time
                )
                evaluate_effective_permission(
                    self.session, ref.source_version_id, "map", DEFAULT_SCOPE_KEY, db_time
                )
        except CatalogPermissionDeniedError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "create_mapping_version",
                type(e).__name__,
                request_key,
                resource_type="mapping_version",
            )
            raise

        req_data = {
            "conditions": conditions,
            "confidence": confidence,
            "control_version_id": control_version_id,
            "covered_dimensions": covered_dimensions,
            "excluded_dimensions": excluded_dimensions,
            "expected_ctrl_digest": expected_ctrl_digest,
            "expected_ctrl_revision": expected_ctrl_revision,
            "expected_req_digest": expected_req_digest,
            "expected_req_revision": expected_req_revision,
            "mapping_id": mapping_id,
            "mapping_type": mapping_type,
            "predecessor_id": predecessor_id,
            "rationale": rationale,
            "requirement_version_id": requirement_version_id,
            "source_basis": source_basis,
            "version_label": version_label,
        }

        digest = compute_mapping_version_digest(
            mapping_id=mapping_id,
            requirement_id=m.requirement_id,
            control_id=m.control_id,
            requirement_version_id=requirement_version_id,
            control_version_id=control_version_id,
            requirement_version_revision=expected_req_revision,
            requirement_version_digest=expected_req_digest,
            control_version_revision=expected_ctrl_revision,
            control_version_digest=expected_ctrl_digest,
            version_label=version_label,
            predecessor_id=predecessor_id,
            revision=1,
            mapping_type=mapping_type,
            rationale=rationale,
            covered_dimensions=covered_dimensions,
            excluded_dimensions=excluded_dimensions,
            conditions=conditions,
            source_basis=source_basis,
            confidence=confidence,
            review_state="Draft",
            status="Draft",
        )

        def _do_write() -> tuple[UUID, str, int, bytes]:
            mv = CatalogMappingVersion(
                mapping_id=mapping_id,
                requirement_id=m.requirement_id,
                control_id=m.control_id,
                requirement_version_id=requirement_version_id,
                control_version_id=control_version_id,
                requirement_version_revision=expected_req_revision,
                requirement_version_digest=expected_req_digest,
                control_version_revision=expected_ctrl_revision,
                control_version_digest=expected_ctrl_digest,
                version_label=version_label,
                predecessor_id=predecessor_id,
                revision=1,
                mapping_type=mapping_type,
                rationale=rationale,
                covered_dimensions=covered_dimensions,
                excluded_dimensions=excluded_dimensions,
                conditions=conditions,
                source_basis=source_basis,
                confidence=confidence,
                content_digest=digest,
                digest_schema=DIGEST_SCHEMA_V1,
                review_state="Draft",
                status="Draft",
            )
            self.session.add(mv)
            self.session.flush()
            return (mv.id, "CatalogMappingVersion", 1, digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "create_mapping_version",
            request_key,
            req_data,
            _do_write,
            db_time,
        )
        if is_retry:
            mv = self.session.get(CatalogMappingVersion, receipt.result_id)
            if mv is None:
                raise CatalogNotFoundError("Mapping version not found on retry")
            return mv

        mv = self.session.get(CatalogMappingVersion, receipt.result_id)
        assert mv is not None

        record_catalog_event_intent(
            self.session,
            request_key,
            "mapping_version.created",
            mv.id,
            "CatalogMappingVersion",
            1,
            digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "mapping_version.created",
            "CatalogMappingVersion",
            mv.id,
            request_key,
            "Success",
            {"mapping_id": str(mapping_id), "version_label": version_label},
            db_time,
        )
        self.session.flush()
        return mv

    # -------------------------------------------------------------------------
    # Packs and Memberships
    # -------------------------------------------------------------------------

    def create_pack(
        self,
        context: CatalogActorContext,
        request_key: str,
        pack_key: str,
        name: str,
        pack_type: str,
        jurisdiction: str | None = None,
    ) -> CatalogPack:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None, "create_pack", type(e).__name__, request_key
            )
            raise

        req_data = {
            "jurisdiction": jurisdiction,
            "name": name,
            "pack_key": pack_key,
            "pack_type": pack_type,
        }

        def _do_write() -> tuple[UUID, str, int, bytes]:
            p = CatalogPack(
                pack_key=pack_key,
                name=name,
                pack_type=pack_type,
                jurisdiction=jurisdiction,
                status="Draft",
            )
            self.session.add(p)
            self.session.flush()
            digest = compute_content_digest(
                {"name": name, "pack_key": pack_key, "pack_type": pack_type}
            )
            return (p.id, "CatalogPack", 1, digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session, context.actor_id, "create_pack", request_key, req_data, _do_write, db_time
        )
        if is_retry:
            p = self.session.get(CatalogPack, receipt.result_id)
            if p is None:
                raise CatalogNotFoundError("Pack not found on retry")
            return p

        p = self.session.get(CatalogPack, receipt.result_id)
        assert p is not None

        record_catalog_event_intent(
            self.session,
            request_key,
            "pack.created",
            p.id,
            "CatalogPack",
            1,
            receipt.result_digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "pack.created",
            "CatalogPack",
            p.id,
            request_key,
            "Success",
            {"pack_key": pack_key},
            db_time,
        )
        self.session.flush()
        return p

    def create_pack_version(
        self,
        context: CatalogActorContext,
        request_key: str,
        pack_id: UUID,
        version_label: str,
        predecessor_id: UUID | None = None,
        description: str | None = None,
    ) -> CatalogPackVersion:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "create_pack_version",
                type(e).__name__,
                request_key,
            )
            raise

        p = self.session.get(CatalogPack, pack_id)
        if p is None:
            raise CatalogValidationError(f"Pack {pack_id} does not exist")

        req_data = {
            "description": description,
            "pack_id": pack_id,
            "predecessor_id": predecessor_id,
            "version_label": version_label,
        }

        digest = compute_pack_version_digest(
            pack_id=pack_id,
            version_label=version_label,
            predecessor_id=predecessor_id,
            revision=1,
            description=description,
            status="Draft",
        )

        def _do_write() -> tuple[UUID, str, int, bytes]:
            pv = CatalogPackVersion(
                pack_id=pack_id,
                version_label=version_label,
                predecessor_id=predecessor_id,
                revision=1,
                title=f"{p.name} {version_label}",
                description=description,
                content_digest=digest,
                digest_schema=DIGEST_SCHEMA_V1,
                status="Draft",
            )
            self.session.add(pv)
            self.session.flush()
            return (pv.id, "CatalogPackVersion", 1, digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "create_pack_version",
            request_key,
            req_data,
            _do_write,
            db_time,
        )
        if is_retry:
            pv = self.session.get(CatalogPackVersion, receipt.result_id)
            if pv is None:
                raise CatalogNotFoundError("Pack version not found on retry")
            return pv

        pv = self.session.get(CatalogPackVersion, receipt.result_id)
        assert pv is not None

        record_catalog_event_intent(
            self.session,
            request_key,
            "pack_version.created",
            pv.id,
            "CatalogPackVersion",
            1,
            digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "pack_version.created",
            "CatalogPackVersion",
            pv.id,
            request_key,
            "Success",
            {"pack_id": str(pack_id), "version_label": version_label},
            db_time,
        )
        self.session.flush()
        return pv

    def append_pack_membership(
        self,
        context: CatalogActorContext,
        request_key: str,
        pack_version_id: UUID,
        requirement_version_id: UUID,
        expected_req_revision: int,
        expected_req_digest: bytes,
    ) -> CatalogPackMembership:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "append_pack_membership",
                type(e).__name__,
                request_key,
            )
            raise

        pv = self.session.get(CatalogPackVersion, pack_version_id)
        if pv is None:
            raise CatalogValidationError(f"Pack version {pack_version_id} does not exist")

        rv = self.session.get(CatalogRequirementVersion, requirement_version_id)
        if rv is None:
            raise CatalogValidationError(
                f"Requirement version {requirement_version_id} does not exist"
            )

        if rv.revision != expected_req_revision:
            raise CatalogConflictError(
                f"Requirement version revision mismatch: expected {expected_req_revision}, got {rv.revision}"
            )
        if rv.content_digest != expected_req_digest:
            raise CatalogConflictError("Requirement version digest mismatch")

        # Lock parent pack version for membership sequence
        self.session.execute(
            select(CatalogPackVersion)
            .where(CatalogPackVersion.id == pack_version_id)
            .with_for_update()
        )

        max_seq = (
            self.session.execute(
                select(func.coalesce(func.max(CatalogPackMembership.sequence), 0)).where(
                    CatalogPackMembership.pack_version_id == pack_version_id
                )
            ).scalar()
            or 0
        )
        next_seq = max_seq + 1

        req_data = {
            "expected_req_digest": expected_req_digest,
            "expected_req_revision": expected_req_revision,
            "pack_version_id": pack_version_id,
            "requirement_version_id": requirement_version_id,
        }

        digest = compute_content_digest(
            {
                "pack_version_id": pack_version_id,
                "requirement_version_id": requirement_version_id,
                "sequence": next_seq,
            }
        )

        def _do_write() -> tuple[UUID, str, int, bytes]:
            mem = CatalogPackMembership(
                pack_version_id=pack_version_id,
                requirement_version_id=requirement_version_id,
                sequence=next_seq,
                requirement_version_revision=expected_req_revision,
                requirement_version_digest=expected_req_digest,
            )
            self.session.add(mem)
            self.session.flush()
            return (mem.id, "CatalogPackMembership", next_seq, digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "append_pack_membership",
            request_key,
            req_data,
            _do_write,
            db_time,
        )
        if is_retry:
            mem = self.session.get(CatalogPackMembership, receipt.result_id)
            if mem is None:
                raise CatalogNotFoundError("Membership not found on retry")
            return mem

        mem = self.session.get(CatalogPackMembership, receipt.result_id)
        assert mem is not None

        record_catalog_event_intent(
            self.session,
            request_key,
            "pack_membership.appended",
            mem.id,
            "CatalogPackMembership",
            next_seq,
            digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "pack_membership.appended",
            "CatalogPackMembership",
            mem.id,
            request_key,
            "Success",
            {"pack_version_id": str(pack_version_id), "sequence": next_seq},
            db_time,
        )
        self.session.flush()
        return mem

    # -------------------------------------------------------------------------
    # Permission Decisions
    # -------------------------------------------------------------------------

    def create_permission_decision(
        self,
        context: CatalogActorContext,
        request_key: str,
        source_id: UUID,
        source_version_id: UUID,
        proposal_id: UUID,
        use_case: str,
        scope_key: str,
        decision_type: str,
        valid_from: datetime,
        valid_until: datetime | None,
        evidence_reference: str,
    ) -> CatalogSourcePermissionDecision:
        db_time = self._get_db_time()
        try:
            verify_catalog_actor(context, CatalogCapability.PERMISSION_DECIDE, db_time)
        except CatalogError as e:
            self._record_denial_safe(
                context.actor_id if context else None,
                "create_permission_decision",
                type(e).__name__,
                request_key,
            )
            raise

        req_data = {
            "decision_type": decision_type,
            "evidence_reference": evidence_reference,
            "proposal_id": proposal_id,
            "scope_key": scope_key,
            "source_id": source_id,
            "source_version_id": source_version_id,
            "use_case": use_case,
            "valid_from": valid_from,
            "valid_until": valid_until,
        }

        def _do_write() -> tuple[UUID, str, int, bytes]:
            dec = create_source_permission_decision(
                session=self.session,
                context=context,
                source_id=source_id,
                source_version_id=source_version_id,
                proposal_id=proposal_id,
                use_case=use_case,
                scope_key=scope_key,
                decision_type=decision_type,
                valid_from=valid_from,
                valid_until=valid_until,
                evidence_reference=evidence_reference,
                db_time=db_time,
            )
            digest = compute_content_digest(
                {
                    "decision": decision_type,
                    "evidence_reference": evidence_reference,
                    "scope_key": scope_key,
                    "sequence": dec.sequence,
                    "source_version_id": source_version_id,
                    "use_case": use_case,
                }
            )
            return (dec.id, "CatalogSourcePermissionDecision", dec.sequence, digest)

        is_retry, receipt = check_or_record_mutation_receipt(
            self.session,
            context.actor_id,
            "create_permission_decision",
            request_key,
            req_data,
            _do_write,
            db_time,
        )
        if is_retry:
            dec = self.session.get(CatalogSourcePermissionDecision, receipt.result_id)
            if dec is None:
                raise CatalogNotFoundError("Decision not found on retry")
            return dec

        dec = self.session.get(CatalogSourcePermissionDecision, receipt.result_id)
        assert dec is not None

        record_catalog_event_intent(
            self.session,
            request_key,
            "permission_decision.created",
            dec.id,
            "CatalogSourcePermissionDecision",
            dec.sequence,
            receipt.result_digest,
            db_time,
        )
        append_catalog_audit_event(
            self.session,
            context.actor_id,
            "permission_decision.created",
            "CatalogSourcePermissionDecision",
            dec.id,
            request_key,
            "Success",
            {"decision": decision_type, "sequence": dec.sequence, "use_case": use_case},
            db_time,
        )
        self.session.flush()
        return dec

    # -------------------------------------------------------------------------

    # Reads and Bounded Queries (DRAFT_READ)
    # -------------------------------------------------------------------------

    def get_source(self, context: CatalogActorContext, source_id: UUID) -> CatalogSource:
        db_time = self._get_db_time()
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        permitted_source_cond = (
            select(1)
            .select_from(CatalogSourceVersion)
            .where(
                CatalogSourceVersion.source_id == CatalogSource.id,
                _effective_permission_sql_filter(CatalogSourceVersion.id, "reference", db_time),
            )
            .exists()
        )
        stmt = select(CatalogSource).where(
            CatalogSource.id == source_id,
            permitted_source_cond,
        )
        src = self.session.execute(stmt).scalar_one_or_none()
        if src is None:
            raise CatalogNotFoundError("Source not found")
        return src

    def get_source_version(
        self, context: CatalogActorContext, version_id: UUID
    ) -> CatalogSourceVersion:
        db_time = self._get_db_time()
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        stmt = select(CatalogSourceVersion).where(
            CatalogSourceVersion.id == version_id,
            _effective_permission_sql_filter(CatalogSourceVersion.id, "reference", db_time),
        )
        ver = self.session.execute(stmt).scalar_one_or_none()
        if ver is None:
            raise CatalogNotFoundError("Source version not found")
        return ver

    def list_source_versions(
        self,
        context: CatalogActorContext,
        source_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CatalogSourceVersion]:
        """Bounded list of source versions (max 100, default 50) filtered by effective permission in SQL."""
        db_time = self._get_db_time()
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        effective_limit = min(max(1, limit), 100)
        stmt = (
            select(CatalogSourceVersion)
            .where(
                CatalogSourceVersion.source_id == source_id,
                _effective_permission_sql_filter(CatalogSourceVersion.id, "reference", db_time),
            )
            .order_by(CatalogSourceVersion.created_at.desc())
            .offset(offset)
            .limit(effective_limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_requirement(
        self, context: CatalogActorContext, requirement_id: UUID
    ) -> CatalogRequirement:
        db_time = self._get_db_time()
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        permitted_req_cond = (
            select(1)
            .select_from(CatalogRequirementVersion)
            .where(
                CatalogRequirementVersion.requirement_id == CatalogRequirement.id,
                _effective_permission_sql_filter(
                    CatalogRequirementVersion.source_version_id, "reference", db_time
                ),
            )
            .exists()
        )
        stmt = select(CatalogRequirement).where(
            CatalogRequirement.id == requirement_id,
            permitted_req_cond,
        )
        req = self.session.execute(stmt).scalar_one_or_none()
        if req is None:
            raise CatalogNotFoundError("Requirement not found")
        return req

    def get_requirement_version(
        self, context: CatalogActorContext, version_id: UUID
    ) -> CatalogRequirementVersion:
        db_time = self._get_db_time()
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        stmt = select(CatalogRequirementVersion).where(
            CatalogRequirementVersion.id == version_id,
            _effective_permission_sql_filter(
                CatalogRequirementVersion.source_version_id, "reference", db_time
            ),
        )
        rv = self.session.execute(stmt).scalar_one_or_none()
        if rv is None:
            raise CatalogNotFoundError("Requirement version not found")
        return rv

    def list_requirement_versions(
        self,
        context: CatalogActorContext,
        requirement_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CatalogRequirementVersion]:
        """Bounded list of requirement versions filtered by effective permission in SQL."""
        db_time = self._get_db_time()
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        effective_limit = min(max(1, limit), 100)
        stmt = (
            select(CatalogRequirementVersion)
            .where(
                CatalogRequirementVersion.requirement_id == requirement_id,
                _effective_permission_sql_filter(
                    CatalogRequirementVersion.source_version_id, "reference", db_time
                ),
            )
            .order_by(CatalogRequirementVersion.created_at.desc())
            .offset(offset)
            .limit(effective_limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_common_control(
        self, context: CatalogActorContext, control_id: UUID
    ) -> CatalogCommonControl:
        db_time = self._get_db_time()
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        ctrl = self.session.get(CatalogCommonControl, control_id)
        if ctrl is None:
            raise CatalogNotFoundError("Common control not found")
        return ctrl

    def get_control_version(
        self, context: CatalogActorContext, version_id: UUID
    ) -> CatalogControlVersion:
        db_time = self._get_db_time()
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        cv = self.session.get(CatalogControlVersion, version_id)
        if cv is None:
            raise CatalogNotFoundError("Control version not found")
        return cv

    def get_mapping_version(
        self, context: CatalogActorContext, version_id: UUID
    ) -> CatalogMappingVersion:
        db_time = self._get_db_time()
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        req_ver = aliased(CatalogRequirementVersion)
        permitted_mapping_cond = (
            select(1)
            .select_from(req_ver)
            .where(
                req_ver.id == CatalogMappingVersion.requirement_version_id,
                _effective_permission_sql_filter(req_ver.source_version_id, "map", db_time),
            )
            .exists()
        )
        stmt = select(CatalogMappingVersion).where(
            CatalogMappingVersion.id == version_id,
            permitted_mapping_cond,
        )
        mv = self.session.execute(stmt).scalar_one_or_none()
        if mv is None:
            raise CatalogNotFoundError("Mapping version not found")
        return mv

    def list_mapping_versions(
        self,
        context: CatalogActorContext,
        mapping_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CatalogMappingVersion]:
        """Bounded list of mapping versions filtered by effective permission in SQL."""
        db_time = self._get_db_time()
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        effective_limit = min(max(1, limit), 100)
        req_ver = aliased(CatalogRequirementVersion)
        permitted_mapping_cond = (
            select(1)
            .select_from(req_ver)
            .where(
                req_ver.id == CatalogMappingVersion.requirement_version_id,
                _effective_permission_sql_filter(req_ver.source_version_id, "map", db_time),
            )
            .exists()
        )
        stmt = (
            select(CatalogMappingVersion)
            .where(
                CatalogMappingVersion.mapping_id == mapping_id,
                permitted_mapping_cond,
            )
            .order_by(CatalogMappingVersion.created_at.desc())
            .offset(offset)
            .limit(effective_limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_pack_version(
        self, context: CatalogActorContext, version_id: UUID
    ) -> CatalogPackVersion:
        db_time = self._get_db_time()
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        pv = self.session.get(CatalogPackVersion, version_id)
        if pv is None:
            raise CatalogNotFoundError("Pack version not found")
        return pv

    def list_sources(
        self,
        context: CatalogActorContext,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CatalogSource]:
        """Bounded list of sources (max 100, default 50) filtered by effective permission in SQL."""
        db_time = self._get_db_time()
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        effective_limit = min(max(1, limit), 100)
        permitted_source_cond = (
            select(1)
            .select_from(CatalogSourceVersion)
            .where(
                CatalogSourceVersion.source_id == CatalogSource.id,
                _effective_permission_sql_filter(CatalogSourceVersion.id, "reference", db_time),
            )
            .exists()
        )
        stmt = (
            select(CatalogSource)
            .where(permitted_source_cond)
            .order_by(CatalogSource.created_at.desc())
            .offset(offset)
            .limit(effective_limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_requirements(
        self,
        context: CatalogActorContext,
        source_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CatalogRequirement]:
        """Bounded list of requirements (max 100, default 50) filtered by effective permission in SQL."""
        db_time = self._get_db_time()
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        effective_limit = min(max(1, limit), 100)
        permitted_req_cond = (
            select(1)
            .select_from(CatalogRequirementVersion)
            .where(
                CatalogRequirementVersion.requirement_id == CatalogRequirement.id,
                _effective_permission_sql_filter(
                    CatalogRequirementVersion.source_version_id, "reference", db_time
                ),
            )
            .exists()
        )
        stmt = select(CatalogRequirement).where(permitted_req_cond)
        if source_id is not None:
            stmt = stmt.where(CatalogRequirement.source_id == source_id)
        stmt = (
            stmt.order_by(CatalogRequirement.created_at.desc())
            .offset(offset)
            .limit(effective_limit)
        )
        return list(self.session.execute(stmt).scalars().all())
