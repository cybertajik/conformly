"""Internal service for controlled draft authoring of synthetic ApplicabilityRules (WP-07E).

Provides CatalogApplicabilityRuleDraftService with strict connection admission,
transaction-scoped advisory locking, source permission enforcement, AST static validation,
idempotency receipts, namespaced event intents, append-only audit trail, and durable denial.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from conformly.catalog_v2.actor import (
    CatalogActorContext,
    CatalogCapability,
    CatalogConflictError,
    CatalogError,
    CatalogInvariantError,
    CatalogNotFoundError,
    CatalogPermissionDeniedError,
    CatalogSecurityError,
    CatalogValidationError,
    verify_catalog_actor,
)
from conformly.catalog_v2.audit import (
    DatabaseCommittedDeniedAuditSink,
    DeniedAuditSink,
    append_catalog_audit_event,
    check_or_record_mutation_receipt,
    lock_or_init_audit_head,
    record_catalog_event_intent,
)
from conformly.catalog_v2.digest import (
    canonical_json,
    compute_content_digest,
    compute_requirement_version_digest,
    compute_source_version_digest,
)
from conformly.catalog_v2.fact_definition_snapshots import read_verified_fact_definition_snapshot
from conformly.catalog_v2.models import (
    CatalogApplicabilityRule,
    CatalogApplicabilityRuleFactRef,
    CatalogApplicabilityRuleSourceRef,
    CatalogApplicabilityRuleVersion,
    CatalogRequirement,
    CatalogRequirementSourceReference,
    CatalogRequirementVersion,
    CatalogSource,
    CatalogSourceVersion,
)
from conformly.catalog_v2.permissions import (
    evaluate_effective_permission,
    lock_source_guards_sorted,
)
from conformly.catalog_v2.rule_static_validation import (
    FactVersionMetadata,
    RuleValidationError,
    validate_rule_ast,
)

logger = logging.getLogger(__name__)

SERVICE_POSTGRES_ROLE = "conformly_catalog_rule_author"
APPLICABILITY_RULE_DRAFT_CHAIN_KEY = "applicability-rule-draft-v1"
APPLICABILITY_RULE_DIGEST_SCHEMA = "catalog-applicability-rule-draft-v1"
MAX_PAYLOAD_BYTES = 262144
UNKNOWN_SYSTEM_ACTOR_ID = UUID("00000000-0000-0000-0000-000000000000")

ADVISORY_LOCK_ID = int.from_bytes(
    hashlib.sha256(b"conformly:applicability-rule-draft-v1").digest()[:8],
    byteorder="big",
    signed=True,
)

REQUEST_KEY_PATTERN = re.compile(r"\A[A-Za-z0-9_.:-]+\Z")
DATE_PATTERN = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
RULE_KEY_PATTERN = re.compile(r"\A[a-z][a-z0-9_]*\Z")
HEX_64_PATTERN = re.compile(r"\A[0-9a-f]{64}\Z")

REQUIRED_RULE_PAYLOAD_KEYS = frozenset(
    {
        "kind",
        "rule_id",
        "rule_key",
        "requirement_id",
        "revision",
        "version_label",
        "predecessor_id",
        "predecessor_revision",
        "requirement_version_id",
        "requirement_version_digest",
        "expression_ast_version",
        "expression_canonical_hex",
        "effective_from",
        "effective_until",
        "status",
        "fact_refs",
        "source_refs",
    }
)


@dataclass(frozen=True)
class ApplicabilityRuleFactRefSnapshot:
    sequence: int
    fact_definition_version_id: UUID
    content_digest: bytes


@dataclass(frozen=True)
class ApplicabilityRuleSourceRefSnapshot:
    sequence: int
    source_version_id: UUID
    content_digest: bytes


@dataclass(frozen=True)
class ApplicabilityRuleVersionSnapshot:
    id: UUID
    rule_id: UUID
    rule_key: str
    requirement_id: UUID
    revision: int
    version_label: str
    predecessor_id: UUID | None
    predecessor_revision: int | None
    requirement_version_id: UUID
    requirement_version_digest: bytes
    expression_ast_version: int
    expression_canonical: bytes
    effective_from: date | None
    effective_until: date | None
    status: str
    content_digest: bytes
    digest_schema: str
    fact_refs: tuple[ApplicabilityRuleFactRefSnapshot, ...]
    source_refs: tuple[ApplicabilityRuleSourceRefSnapshot, ...]
    created_at: datetime
    updated_at: datetime

    @property
    def expression_canonical_hex(self) -> str:
        return self.expression_canonical.hex()


class CatalogApplicabilityRuleDraftService:
    """Internal service for controlled draft authoring of synthetic ApplicabilityRules."""

    def __init__(
        self,
        session: Session,
        denied_audit_sink: DeniedAuditSink | None = None,
        denied_sink: DeniedAuditSink | None = None,
    ) -> None:
        self.session = session

        # Validate clean unit of work on session initialization
        def _has_dirty_work(collection: Any) -> bool:
            try:
                return len(collection) > 0
            except (TypeError, AttributeError):
                return False

        if getattr(self.session, "is_active", False) and (
            _has_dirty_work(getattr(self.session, "dirty", ()))
            or _has_dirty_work(getattr(self.session, "new", ()))
            or _has_dirty_work(getattr(self.session, "deleted", ()))
        ):
            raise CatalogSecurityError("Service session must start with a clean unit of work")

        effective_sink = denied_audit_sink or denied_sink
        if effective_sink is not None:
            self.denied_sink: DeniedAuditSink = effective_sink
            if self.session.bind and getattr(self.session.bind.dialect, "name", "") == "postgresql":
                self._ensure_sink_schema_qualified(self.denied_sink)
        else:
            bind = self.session.get_bind()
            if bind:
                if getattr(bind.dialect, "name", "") == "postgresql":
                    qualified_bind = bind.execution_options(schema_translate_map={None: "public"})
                    self.denied_sink = DatabaseCommittedDeniedAuditSink(
                        qualified_bind, chain_key=APPLICABILITY_RULE_DRAFT_CHAIN_KEY
                    )
                else:
                    self.denied_sink = DatabaseCommittedDeniedAuditSink(
                        bind, chain_key=APPLICABILITY_RULE_DRAFT_CHAIN_KEY
                    )
            else:
                self.denied_sink = None  # type: ignore[assignment]

    def _ensure_sink_schema_qualified(self, sink: Any) -> None:
        """Ensure DatabaseCommittedDeniedAuditSink uses public schema qualification."""
        if isinstance(sink, DatabaseCommittedDeniedAuditSink):
            target = getattr(sink, "_target", None)
            if target is not None:
                if hasattr(target, "execution_options"):
                    sink._target = target.execution_options(schema_translate_map={None: "public"})
                elif callable(target):
                    orig_target = target

                    def _qualified_session() -> Any:
                        s = orig_target()
                        s.connection(execution_options={"schema_translate_map": {None: "public"}})
                        return s

                    sink._target = _qualified_session

    def _verify_postgres_connection_admission(self) -> None:
        """Verify PostgreSQL connection adheres to strict role admission."""
        if not self.session.bind:
            raise CatalogSecurityError("Unbound session: database connection required")
        if self.session.bind.dialect.name != "postgresql":
            raise CatalogSecurityError(
                f"Unsupported database dialect '{self.session.bind.dialect.name}': PostgreSQL required"
            )

        try:
            res = self.session.execute(
                text("SELECT pg_catalog.session_user(), pg_catalog.current_user()")
            ).one()
            sess_user, curr_user = res[0], res[1]
        except Exception as e:
            raise CatalogSecurityError(
                f"PostgreSQL connection role admission check failed: {e}"
            ) from e

        if sess_user != SERVICE_POSTGRES_ROLE or curr_user != SERVICE_POSTGRES_ROLE:
            raise CatalogSecurityError(
                f"Unauthorized database connection role: session_user='{sess_user}', current_user='{curr_user}'. "
                f"Expected exact '{SERVICE_POSTGRES_ROLE}'."
            )

        # Check elevated attributes, memberships, ownership, schema CREATE, and transaction isolation
        try:
            role_flags = self.session.execute(
                text(
                    "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolinherit, rolreplication "
                    "FROM pg_catalog.pg_roles WHERE rolname = :rolname"
                ),
                {"rolname": SERVICE_POSTGRES_ROLE},
            ).one()
            if any(role_flags):
                raise CatalogSecurityError(
                    f"Role '{SERVICE_POSTGRES_ROLE}' possesses elevated privileges: {role_flags}"
                )

            # Check memberships
            membership_count = self.session.execute(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_auth_members m "
                    "JOIN pg_catalog.pg_roles r ON r.oid = m.member "
                    "WHERE r.rolname = :rolname"
                ),
                {"rolname": SERVICE_POSTGRES_ROLE},
            ).scalar()
            if membership_count != 0:
                raise CatalogSecurityError(
                    f"Role '{SERVICE_POSTGRES_ROLE}' has unexpected memberships ({membership_count})"
                )

            # Check schema CREATE privilege
            has_create = self.session.execute(
                text("SELECT pg_catalog.has_schema_privilege(:rolname, 'public', 'CREATE')"),
                {"rolname": SERVICE_POSTGRES_ROLE},
            ).scalar()
            if has_create:
                raise CatalogSecurityError(
                    f"Role '{SERVICE_POSTGRES_ROLE}' has unauthorized CREATE privilege on public schema"
                )

            # Check object ownership
            owned_count = self.session.execute(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_class c "
                    "JOIN pg_catalog.pg_roles r ON r.oid = c.relowner "
                    "WHERE r.rolname = :rolname"
                ),
                {"rolname": SERVICE_POSTGRES_ROLE},
            ).scalar()
            if owned_count != 0:
                raise CatalogSecurityError(
                    f"Role '{SERVICE_POSTGRES_ROLE}' owns {owned_count} persistent database objects"
                )

            # Check isolation level is READ COMMITTED
            isolation = self.session.execute(
                text("SELECT current_setting('transaction_isolation')")
            ).scalar()
            if isolation and isolation.lower() != "read committed":
                raise CatalogSecurityError(
                    f"Unsupported transaction isolation '{isolation}': READ COMMITTED required"
                )
        except CatalogSecurityError:
            raise
        except Exception as e:
            raise CatalogSecurityError(f"PostgreSQL role attribute check failed: {e}") from e

    def _ensure_schema_translation(self) -> None:
        """Set a service-connection public schema mapping before the first ORM operation."""
        if not self.session.bind or getattr(self.session.bind.dialect, "name", "") != "postgresql":
            return
        try:
            conn = self.session.connection()
            curr_map = conn.get_execution_options().get("schema_translate_map")
            if curr_map and curr_map.get(None) != "public":
                raise CatalogSecurityError(
                    f"Conflicting schema_translate_map on session connection: {curr_map}"
                )
            conn.execution_options(schema_translate_map={None: "public"})
        except CatalogSecurityError:
            raise
        except Exception as e:
            raise CatalogSecurityError(
                f"PostgreSQL schema translation configuration failed: {e}"
            ) from e

    def _acquire_advisory_lock(self) -> None:
        """Acquire transaction-scoped advisory lock on postgresql."""
        if self.session.bind and getattr(self.session.bind.dialect, "name", "") == "postgresql":
            self.session.execute(
                text("SELECT pg_catalog.pg_advisory_xact_lock(:key)"),
                {"key": ADVISORY_LOCK_ID},
            )

    def _get_db_time(self) -> datetime:
        """Retrieve trusted database clock_timestamp."""
        if self.session.bind and getattr(self.session.bind.dialect, "name", "") == "postgresql":
            try:
                ts = self.session.execute(text("SELECT pg_catalog.clock_timestamp()")).scalar()
                if not isinstance(ts, datetime):
                    raise CatalogSecurityError(
                        f"Failed to retrieve database clock_timestamp: expected datetime, got {type(ts)}"
                    )
                return ts
            except Exception as e:
                if isinstance(e, CatalogSecurityError):
                    raise
                raise CatalogSecurityError(
                    f"Failed to retrieve database clock_timestamp: {e}"
                ) from e
        return datetime.now(UTC)

    def _validate_author_actor(self, context: CatalogActorContext, db_time: datetime) -> None:
        """Validate author actor context has recent auth, MFA, and required capabilities."""
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)
        verify_catalog_actor(context, CatalogCapability.DRAFT_WRITE, db_time)

    def _validate_reader_actor(self, context: CatalogActorContext, db_time: datetime) -> None:
        """Validate reader actor context has recent auth, MFA, and DRAFT_READ capability."""
        verify_catalog_actor(context, CatalogCapability.DRAFT_READ, db_time)

    def _classify_error_code(self, e: Exception) -> str:
        """Map exception to a bounded fixed failure code."""
        if isinstance(e, CatalogSecurityError):
            return "SECURITY_ERROR"
        if isinstance(e, CatalogPermissionDeniedError):
            return "PERMISSION_DENIED"
        if isinstance(e, CatalogConflictError):
            return "CONFLICT"
        if isinstance(e, CatalogNotFoundError):
            return "NOT_FOUND"
        if isinstance(e, (CatalogValidationError, RuleValidationError)):
            return "VALIDATION_ERROR"
        if isinstance(e, CatalogInvariantError):
            return "INVARIANT_ERROR"
        if isinstance(e, CatalogError):
            return "CATALOG_ERROR"
        return "INTERNAL_ERROR"

    def _record_denial_unswallowed(
        self,
        actor_id: UUID | None,
        operation: str,
        reason_code: str,
        request_key: str | None = None,
    ) -> None:
        """Record durable denial without swallowing failures."""
        if not self.denied_sink:
            return

        unknown_actor = UNKNOWN_SYSTEM_ACTOR_ID
        effective_actor_id = actor_id if isinstance(actor_id, UUID) else unknown_actor

        safe_req_key = (
            request_key
            if (
                isinstance(request_key, str)
                and 1 <= len(request_key) <= 128
                and "\n" not in request_key
                and "\r" not in request_key
                and REQUEST_KEY_PATTERN.match(request_key)
            )
            else "[INVALID_REQUEST_KEY]"
        )

        try:
            self.denied_sink.record_denial(
                actor_id=effective_actor_id,
                operation=operation,
                reason_code=reason_code,
                request_key=safe_req_key,
                resource_type="ApplicabilityRuleVersion",
                resource_id=None,
            )
        except Exception as sink_err:
            logger.error("Failed to record denial in sink: %s", sink_err.__class__.__name__)
            raise sink_err

    def _verify_complete_rule_version_aggregate(
        self,
        version_id: UUID,
        expected_digest: bytes | None = None,
        *,
        validate_predecessor: bool = True,
    ) -> ApplicabilityRuleVersionSnapshot:
        """Read and verify complete persisted ApplicabilityRuleVersion aggregate from genuine columns.

        Enforces:
        1. Rule and Version scalar integrity and status.
        2. Child fact_refs and source_refs cardinality and sequence bounds.
        3. Rule content_digest recomputation against genuinely stored payload.
        4. Target RequirementVersion and full Locator aggregate verification via compute_requirement_version_digest.
        5. All referenced sources verification via compute_source_version_digest.
        6. Pinned FactDefinitionVersion aggregates verified via read_verified_fact_definition_snapshot.
        7. Rule AST validation using protected validate_rule_ast with actual fact metadata and ref order.
        8. Immediate predecessor aggregate verification when revision > 1 (non-recursive).
        """
        if not isinstance(version_id, UUID):
            raise CatalogInvariantError(
                f"version_id must be a UUID instance, got {type(version_id)}"
            )

        exec_opts: dict[str, Any] = {"populate_existing": True}
        if self.session.bind and getattr(self.session.bind.dialect, "name", "") == "postgresql":
            exec_opts["schema_translate_map"] = {None: "public"}

        ver_row = self.session.execute(
            select(
                CatalogApplicabilityRuleVersion.id,
                CatalogApplicabilityRuleVersion.rule_id,
                CatalogApplicabilityRuleVersion.requirement_id,
                CatalogApplicabilityRuleVersion.requirement_version_id,
                CatalogApplicabilityRuleVersion.requirement_version_digest_snapshot,
                CatalogApplicabilityRuleVersion.revision,
                CatalogApplicabilityRuleVersion.version_label,
                CatalogApplicabilityRuleVersion.predecessor_id,
                CatalogApplicabilityRuleVersion.predecessor_revision,
                CatalogApplicabilityRuleVersion.expression_ast_version,
                CatalogApplicabilityRuleVersion.expression_canonical,
                CatalogApplicabilityRuleVersion.effective_from,
                CatalogApplicabilityRuleVersion.effective_until,
                CatalogApplicabilityRuleVersion.status,
                CatalogApplicabilityRuleVersion.content_digest,
                CatalogApplicabilityRuleVersion.digest_schema,
                CatalogApplicabilityRuleVersion.created_at,
                CatalogApplicabilityRuleVersion.updated_at,
            )
            .where(CatalogApplicabilityRuleVersion.id == version_id)
            .execution_options(**exec_opts)
        ).one_or_none()

        if ver_row is None:
            raise CatalogNotFoundError(
                f"ApplicabilityRuleVersion '{version_id}' not found in database"
            )

        rule_row = self.session.execute(
            select(
                CatalogApplicabilityRule.id,
                CatalogApplicabilityRule.rule_key,
                CatalogApplicabilityRule.requirement_id,
                CatalogApplicabilityRule.status,
            )
            .where(CatalogApplicabilityRule.id == ver_row.rule_id)
            .execution_options(**exec_opts)
        ).one_or_none()

        if rule_row is None:
            raise CatalogInvariantError(
                f"Parent ApplicabilityRule '{ver_row.rule_id}' not found for version '{version_id}'"
            )

        fact_ref_rows = self.session.execute(
            select(
                CatalogApplicabilityRuleFactRef.sequence,
                CatalogApplicabilityRuleFactRef.fact_definition_version_id,
                CatalogApplicabilityRuleFactRef.content_digest_snapshot,
            )
            .where(CatalogApplicabilityRuleFactRef.rule_version_id == version_id)
            .order_by(CatalogApplicabilityRuleFactRef.sequence.asc())
            .execution_options(**exec_opts)
        ).all()

        source_ref_rows = self.session.execute(
            select(
                CatalogApplicabilityRuleSourceRef.sequence,
                CatalogApplicabilityRuleSourceRef.source_version_id,
                CatalogApplicabilityRuleSourceRef.content_digest_snapshot,
            )
            .where(CatalogApplicabilityRuleSourceRef.rule_version_id == version_id)
            .order_by(CatalogApplicabilityRuleSourceRef.sequence.asc())
            .execution_options(**exec_opts)
        ).all()

        # 1. Parent ApplicabilityRule validation
        if rule_row.id != ver_row.rule_id:
            raise CatalogInvariantError(
                f"Parent rule ID mismatch: rule {rule_row.id} != ver {ver_row.rule_id}"
            )
        if rule_row.requirement_id != ver_row.requirement_id:
            raise CatalogInvariantError(
                f"Requirement ID mismatch: rule {rule_row.requirement_id} != ver {ver_row.requirement_id}"
            )
        if rule_row.status != "Draft":
            raise CatalogInvariantError(
                f"Stored parent ApplicabilityRule status is '{rule_row.status}'; expected 'Draft'"
            )
        if not rule_row.rule_key.startswith("synthetic_"):
            raise CatalogInvariantError(
                f"Stored parent ApplicabilityRule rule_key '{rule_row.rule_key}' missing required 'synthetic_' prefix"
            )
        if not (11 <= len(rule_row.rule_key) <= 64):
            raise CatalogInvariantError(
                f"Stored parent ApplicabilityRule rule_key length {len(rule_row.rule_key)} outside 11..64 bounds"
            )
        if not RULE_KEY_PATTERN.match(rule_row.rule_key):
            raise CatalogInvariantError(
                f"Stored parent ApplicabilityRule rule_key '{rule_row.rule_key}' does not match pattern"
            )

        # 2. ApplicabilityRuleVersion scalar validation
        if ver_row.status != "Draft":
            raise CatalogInvariantError(
                f"Stored ApplicabilityRuleVersion status is '{ver_row.status}'; expected 'Draft'"
            )
        if ver_row.digest_schema != APPLICABILITY_RULE_DIGEST_SCHEMA:
            raise CatalogInvariantError(
                f"Invalid digest schema '{ver_row.digest_schema}': expected '{APPLICABILITY_RULE_DIGEST_SCHEMA}'"
            )
        if not (1 <= ver_row.revision <= 32767):
            raise CatalogInvariantError(
                f"Stored ApplicabilityRuleVersion revision {ver_row.revision} outside 1..32767 bounds"
            )
        if type(ver_row.expression_ast_version) is not int or ver_row.expression_ast_version != 1:
            raise CatalogInvariantError(
                f"Stored ApplicabilityRuleVersion expression_ast_version {ver_row.expression_ast_version} != 1"
            )
        expr_bytes = bytes(ver_row.expression_canonical)
        if not (2 <= len(expr_bytes) <= 16384):
            raise CatalogInvariantError(
                f"Stored expression_canonical length {len(expr_bytes)} outside 2..16384 bytes"
            )
        if (
            not ver_row.version_label
            or ver_row.version_label != ver_row.version_label.strip()
            or not (1 <= len(ver_row.version_label) <= 64)
        ):
            raise CatalogInvariantError("Stored ApplicabilityRuleVersion version_label invalid")
        if ver_row.effective_from and ver_row.effective_until:
            if ver_row.effective_until < ver_row.effective_from:
                raise CatalogInvariantError(
                    "Stored ApplicabilityRuleVersion effective_until precedes effective_from"
                )

        # 3. Children cardinality and sequences
        if not (1 <= len(fact_ref_rows) <= 64):
            raise CatalogInvariantError(
                f"Stored aggregate has invalid fact_refs cardinality: expected 1..64 refs, got {len(fact_ref_rows)}"
            )
        expected_fact_seqs = list(range(1, len(fact_ref_rows) + 1))
        actual_fact_seqs = [r.sequence for r in fact_ref_rows]
        if actual_fact_seqs != expected_fact_seqs:
            raise CatalogInvariantError(
                f"Stored fact_refs sequences {actual_fact_seqs} are not contiguous 1-indexed {expected_fact_seqs}"
            )

        seen_fact_vers = set()
        for fr in fact_ref_rows:
            if fr.fact_definition_version_id in seen_fact_vers:
                raise CatalogInvariantError(
                    f"Duplicate fact_definition_version_id '{fr.fact_definition_version_id}' in stored aggregate"
                )
            seen_fact_vers.add(fr.fact_definition_version_id)
            if len(bytes(fr.content_digest_snapshot)) != 32:
                raise CatalogInvariantError(
                    f"Invalid fact_ref content_digest length: expected 32, got {len(bytes(fr.content_digest_snapshot))}"
                )

        if not (1 <= len(source_ref_rows) <= 64):
            raise CatalogInvariantError(
                f"Stored aggregate has invalid source_refs cardinality: expected 1..64 refs, got {len(source_ref_rows)}"
            )
        expected_src_seqs = list(range(1, len(source_ref_rows) + 1))
        actual_src_seqs = [r.sequence for r in source_ref_rows]
        if actual_src_seqs != expected_src_seqs:
            raise CatalogInvariantError(
                f"Stored source_refs sequences {actual_src_seqs} are not contiguous 1-indexed {expected_src_seqs}"
            )

        seen_src_vers = set()
        for sr in source_ref_rows:
            if sr.source_version_id in seen_src_vers:
                raise CatalogInvariantError(
                    f"Duplicate source_version_id '{sr.source_version_id}' in stored aggregate"
                )
            seen_src_vers.add(sr.source_version_id)
            if len(bytes(sr.content_digest_snapshot)) != 32:
                raise CatalogInvariantError(
                    f"Invalid source_ref content_digest length: expected 32, got {len(bytes(sr.content_digest_snapshot))}"
                )

        # 4. Immediate same-rule predecessor validation
        if ver_row.revision == 1:
            if ver_row.predecessor_id is not None or ver_row.predecessor_revision is not None:
                raise CatalogInvariantError("Revision 1 stored version has non-null predecessor")
        else:
            if ver_row.predecessor_id is None or ver_row.predecessor_revision is None:
                raise CatalogInvariantError(
                    f"Revision {ver_row.revision} stored version missing predecessor"
                )
            if ver_row.predecessor_revision != ver_row.revision - 1:
                raise CatalogInvariantError(
                    f"Revision {ver_row.revision} stored version has predecessor_revision {ver_row.predecessor_revision}; expected {ver_row.revision - 1}"
                )
            if validate_predecessor:
                pred_snap = self._verify_complete_rule_version_aggregate(
                    ver_row.predecessor_id,
                    validate_predecessor=False,
                )
                if pred_snap.rule_id != ver_row.rule_id:
                    raise CatalogInvariantError("Predecessor version belongs to different rule")
                if pred_snap.revision != ver_row.predecessor_revision:
                    raise CatalogInvariantError(
                        f"Predecessor revision mismatch: expected {ver_row.predecessor_revision}, got {pred_snap.revision}"
                    )
                if pred_snap.requirement_id != ver_row.requirement_id:
                    raise CatalogInvariantError(
                        "Predecessor version requirement_id does not match parent rule requirement_id"
                    )

        # 5. Recompute and verify the rule version's own content digest
        reconstructed_payload: dict[str, Any] = {
            "effective_from": ver_row.effective_from.isoformat()
            if ver_row.effective_from
            else None,
            "effective_until": ver_row.effective_until.isoformat()
            if ver_row.effective_until
            else None,
            "expression_ast_version": ver_row.expression_ast_version,
            "expression_canonical_hex": expr_bytes.hex(),
            "fact_refs": [
                {
                    "content_digest": bytes(r.content_digest_snapshot).hex(),
                    "fact_definition_version_id": str(r.fact_definition_version_id).lower(),
                    "sequence": r.sequence,
                }
                for r in fact_ref_rows
            ],
            "kind": "ApplicabilityRuleVersion",
            "predecessor_id": str(ver_row.predecessor_id).lower()
            if ver_row.predecessor_id
            else None,
            "predecessor_revision": ver_row.predecessor_revision,
            "requirement_id": str(rule_row.requirement_id).lower(),
            "requirement_version_digest": bytes(ver_row.requirement_version_digest_snapshot).hex(),
            "requirement_version_id": str(ver_row.requirement_version_id).lower(),
            "revision": ver_row.revision,
            "rule_id": str(rule_row.id).lower(),
            "rule_key": rule_row.rule_key,
            "source_refs": [
                {
                    "content_digest": bytes(r.content_digest_snapshot).hex(),
                    "sequence": r.sequence,
                    "source_version_id": str(r.source_version_id).lower(),
                }
                for r in source_ref_rows
            ],
            "status": ver_row.status,
            "version_label": ver_row.version_label,
        }

        stored_digest = bytes(ver_row.content_digest)
        if len(stored_digest) != 32:
            raise CatalogInvariantError(
                f"Corrupted content digest in database: expected 32 bytes, got {len(stored_digest)}"
            )

        recomputed_digest = compute_content_digest(reconstructed_payload)
        if recomputed_digest != stored_digest:
            raise CatalogInvariantError(
                f"Persisted content digest mismatch: recomputed {recomputed_digest.hex()} != stored {stored_digest.hex()}"
            )

        if expected_digest is not None and recomputed_digest != expected_digest:
            raise CatalogInvariantError(
                f"Persisted digest mismatch against expected: {recomputed_digest.hex()} != {expected_digest.hex()}"
            )

        # 6. Re-read and recompute Target RequirementVersion and full Locator aggregate (R1, R2)
        target_req_ver = self.session.execute(
            select(
                CatalogRequirementVersion.id,
                CatalogRequirementVersion.requirement_id,
                CatalogRequirementVersion.source_id,
                CatalogRequirementVersion.source_version_id,
                CatalogRequirementVersion.version_label,
                CatalogRequirementVersion.predecessor_id,
                CatalogRequirementVersion.revision,
                CatalogRequirementVersion.normalized_outcome,
                CatalogRequirementVersion.requirement_type,
                CatalogRequirementVersion.obligated_actor,
                CatalogRequirementVersion.text_origin,
                CatalogRequirementVersion.customer_display_text,
                CatalogRequirementVersion.effective_from,
                CatalogRequirementVersion.effective_until,
                CatalogRequirementVersion.status,
                CatalogRequirementVersion.content_digest,
            )
            .where(CatalogRequirementVersion.id == ver_row.requirement_version_id)
            .execution_options(**exec_opts)
        ).one_or_none()

        if target_req_ver is None:
            raise CatalogInvariantError(
                f"Target RequirementVersion '{ver_row.requirement_version_id}' not found"
            )
        if target_req_ver.requirement_id != ver_row.requirement_id:
            raise CatalogInvariantError(
                f"Target RequirementVersion requirement_id mismatch: {target_req_ver.requirement_id} != {ver_row.requirement_id}"
            )
        if target_req_ver.status != "Draft":
            raise CatalogInvariantError(
                f"Target RequirementVersion status is '{target_req_ver.status}'; expected 'Draft'"
            )

        # Verify parent requirement and its source
        target_req = self.session.execute(
            select(
                CatalogRequirement.id,
                CatalogRequirement.source_id,
                CatalogRequirement.requirement_key,
                CatalogRequirement.status,
            )
            .where(CatalogRequirement.id == ver_row.requirement_id)
            .execution_options(**exec_opts)
        ).one_or_none()
        if target_req is None:
            raise CatalogInvariantError(f"Target Requirement '{ver_row.requirement_id}' not found")
        if target_req.status != "Draft":
            raise CatalogInvariantError(
                f"Target Requirement status is '{target_req.status}'; expected 'Draft'"
            )
        if not target_req.requirement_key.startswith("synthetic_rule_demo_"):
            raise CatalogSecurityError(
                f"Target Requirement key '{target_req.requirement_key}' does not start with 'synthetic_rule_demo_'"
            )

        req_parent_source = self.session.execute(
            select(CatalogSource.id, CatalogSource.source_key, CatalogSource.status)
            .where(CatalogSource.id == target_req.source_id)
            .execution_options(**exec_opts)
        ).one_or_none()
        if req_parent_source is None:
            raise CatalogInvariantError(
                f"Parent Source '{target_req.source_id}' not found for requirement '{target_req.id}'"
            )
        if req_parent_source.status != "Draft":
            raise CatalogInvariantError(
                f"Parent Source status is '{req_parent_source.status}'; expected 'Draft'"
            )
        if not req_parent_source.source_key.startswith("synthetic_rule_demo_"):
            raise CatalogSecurityError(
                f"Requirement parent source key '{req_parent_source.source_key}' does not start with 'synthetic_rule_demo_'"
            )

        # Requirement locators
        locators = self.session.execute(
            select(
                CatalogRequirementSourceReference.sequence,
                CatalogRequirementSourceReference.source_version_id,
                CatalogRequirementSourceReference.locator_kind,
                CatalogRequirementSourceReference.locator_value,
            )
            .where(CatalogRequirementSourceReference.requirement_version_id == target_req_ver.id)
            .order_by(CatalogRequirementSourceReference.sequence.asc())
            .execution_options(**exec_opts)
        ).all()

        if not (1 <= len(locators) <= 64):
            raise CatalogInvariantError(
                f"Requirement locators count {len(locators)} outside valid 1..64 range"
            )
        expected_loc_seqs = list(range(1, len(locators) + 1))
        actual_loc_seqs = [loc_item.sequence for loc_item in locators]
        if actual_loc_seqs != expected_loc_seqs:
            raise CatalogInvariantError(
                f"Requirement locators sequences {actual_loc_seqs} are not contiguous 1-indexed {expected_loc_seqs}"
            )

        locator_dicts: list[dict[str, Any]] = []
        for loc in locators:
            if not loc.locator_kind or not loc.locator_kind.strip():
                raise CatalogInvariantError("Empty locator_kind in requirement locator")
            if not loc.locator_value or not loc.locator_value.strip():
                raise CatalogInvariantError("Empty locator_value in requirement locator")
            if not isinstance(loc.source_version_id, UUID):
                raise CatalogInvariantError("Invalid source_version_id in requirement locator")
            locator_dicts.append(
                {
                    "locator_kind": loc.locator_kind,
                    "locator_value": loc.locator_value,
                    "sequence": loc.sequence,
                    "source_version_id": loc.source_version_id,
                }
            )

        # Recompute canonical requirement version digest
        recomputed_req_digest = compute_requirement_version_digest(
            requirement_id=target_req_ver.requirement_id,
            source_id=target_req_ver.source_id,
            source_version_id=target_req_ver.source_version_id,
            version_label=target_req_ver.version_label,
            predecessor_id=target_req_ver.predecessor_id,
            revision=target_req_ver.revision,
            normalized_outcome=target_req_ver.normalized_outcome,
            requirement_type=target_req_ver.requirement_type,
            obligated_actor=target_req_ver.obligated_actor,
            text_origin=target_req_ver.text_origin,
            customer_display_text=target_req_ver.customer_display_text,
            effective_from=target_req_ver.effective_from,
            effective_until=target_req_ver.effective_until,
            source_references=locator_dicts,
            status=target_req_ver.status,
        )

        if recomputed_req_digest != bytes(target_req_ver.content_digest):
            raise CatalogInvariantError(
                f"RequirementVersion digest tampering detected: recomputed {recomputed_req_digest.hex()} != stored {bytes(target_req_ver.content_digest).hex()}"
            )
        if recomputed_req_digest != bytes(ver_row.requirement_version_digest_snapshot):
            raise CatalogInvariantError(
                "Rule version snapshot requirement_version_digest does not match recomputed requirement digest"
            )

        # 7. Re-read and recompute All Referenced Sources via compute_source_version_digest (R1, R2)
        all_referenced_source_version_ids: set[UUID] = set()
        if target_req_ver.source_version_id:
            all_referenced_source_version_ids.add(target_req_ver.source_version_id)
        for loc in locators:
            all_referenced_source_version_ids.add(loc.source_version_id)
        for sr in source_ref_rows:
            all_referenced_source_version_ids.add(sr.source_version_id)

        source_version_cache: dict[UUID, bytes] = {}
        for sv_id in all_referenced_source_version_ids:
            s_ver = self.session.execute(
                select(
                    CatalogSourceVersion.id,
                    CatalogSourceVersion.source_id,
                    CatalogSourceVersion.edition,
                    CatalogSourceVersion.predecessor_id,
                    CatalogSourceVersion.language,
                    CatalogSourceVersion.official_locator,
                    CatalogSourceVersion.publication_date,
                    CatalogSourceVersion.retrieved_at,
                    CatalogSourceVersion.status,
                    CatalogSourceVersion.content_digest,
                )
                .where(CatalogSourceVersion.id == sv_id)
                .execution_options(**exec_opts)
            ).one_or_none()

            if s_ver is None:
                raise CatalogInvariantError(f"Referenced SourceVersion '{sv_id}' not found")
            if s_ver.status != "Draft":
                raise CatalogInvariantError(
                    f"Referenced SourceVersion '{sv_id}' status is '{s_ver.status}'; expected 'Draft'"
                )

            s_parent = self.session.execute(
                select(CatalogSource.id, CatalogSource.source_key, CatalogSource.status)
                .where(CatalogSource.id == s_ver.source_id)
                .execution_options(**exec_opts)
            ).one_or_none()
            if s_parent is None:
                raise CatalogInvariantError(
                    f"Parent Source '{s_ver.source_id}' not found for version '{sv_id}'"
                )
            if s_parent.status != "Draft":
                raise CatalogInvariantError(
                    f"Parent Source status is '{s_parent.status}'; expected 'Draft'"
                )
            if not s_parent.source_key.startswith("synthetic_rule_demo_"):
                raise CatalogSecurityError(
                    f"Source key '{s_parent.source_key}' does not start with 'synthetic_rule_demo_'"
                )

            recomputed_src_digest = compute_source_version_digest(
                source_id=s_ver.source_id,
                edition=s_ver.edition,
                predecessor_id=s_ver.predecessor_id,
                language=s_ver.language,
                official_locator=s_ver.official_locator,
                publication_date=s_ver.publication_date,
                retrieved_at=s_ver.retrieved_at,
                status=s_ver.status,
            )
            if recomputed_src_digest != bytes(s_ver.content_digest):
                raise CatalogInvariantError(
                    f"SourceVersion digest tampering detected for '{sv_id}': recomputed {recomputed_src_digest.hex()} != stored {bytes(s_ver.content_digest).hex()}"
                )
            source_version_cache[sv_id] = recomputed_src_digest

        # Check explicit rule source_refs snapshot against canonical digest
        for sr in source_ref_rows:
            actual_src_digest = source_version_cache[sr.source_version_id]
            if bytes(sr.content_digest_snapshot) != actual_src_digest:
                raise CatalogInvariantError(
                    f"Rule source_ref digest snapshot mismatch for '{sr.source_version_id}'"
                )

        # 8. Re-read and verify Pinned Fact Definitions via read_verified_fact_definition_snapshot (R1)
        metadata_dict: dict[UUID, FactVersionMetadata] = {}
        ordered_fact_version_ids: list[UUID] = []

        for fr in fact_ref_rows:
            fact_snap = read_verified_fact_definition_snapshot(
                self.session,
                fr.fact_definition_version_id,
                expected_digest=bytes(fr.content_digest_snapshot),
            )
            if fact_snap.status != "Draft":
                raise CatalogInvariantError(
                    f"Referenced FactDefinitionVersion '{fr.fact_definition_version_id}' status is '{fact_snap.status}'; expected 'Draft'"
                )
            if not fact_snap.fact_key.startswith("synthetic_"):
                raise CatalogSecurityError(
                    f"Referenced fact_key '{fact_snap.fact_key}' does not start with 'synthetic_'"
                )

            ordered_fact_version_ids.append(fr.fact_definition_version_id)
            metadata_dict[fr.fact_definition_version_id] = FactVersionMetadata(
                fact_definition_id=fact_snap.fact_definition_id,
                value_type=fact_snap.value_type,
                scope_types=frozenset(s.scope_type for s in fact_snap.allowed_scopes),
                enum_codes=frozenset(e.code for e in fact_snap.enum_values),
            )

        # 9. Validate Rule AST using protected validate_rule_ast (R1)
        try:
            validated_ast = validate_rule_ast(expr_bytes, metadata_dict, ordered_fact_version_ids)
            if validated_ast.canonical_bytes != expr_bytes:
                raise CatalogInvariantError(
                    "Stored expression_canonical is not canonical AST encoding"
                )
        except RuleValidationError as rve:
            raise CatalogInvariantError(f"Stored rule AST validation failed: {rve.code}") from rve

        # Refresh cached ORM entity in identity map if present
        cached_ver = self.session.get(CatalogApplicabilityRuleVersion, version_id)
        if cached_ver is not None:
            self.session.refresh(cached_ver)

        return ApplicabilityRuleVersionSnapshot(
            id=ver_row.id,
            rule_id=rule_row.id,
            rule_key=rule_row.rule_key,
            requirement_id=rule_row.requirement_id,
            revision=ver_row.revision,
            version_label=ver_row.version_label,
            predecessor_id=ver_row.predecessor_id,
            predecessor_revision=ver_row.predecessor_revision,
            requirement_version_id=ver_row.requirement_version_id,
            requirement_version_digest=bytes(ver_row.requirement_version_digest_snapshot),
            expression_ast_version=ver_row.expression_ast_version,
            expression_canonical=expr_bytes,
            effective_from=ver_row.effective_from,
            effective_until=ver_row.effective_until,
            status=ver_row.status,
            content_digest=stored_digest,
            digest_schema=ver_row.digest_schema,
            fact_refs=tuple(
                ApplicabilityRuleFactRefSnapshot(
                    sequence=r.sequence,
                    fact_definition_version_id=r.fact_definition_version_id,
                    content_digest=bytes(r.content_digest_snapshot),
                )
                for r in fact_ref_rows
            ),
            source_refs=tuple(
                ApplicabilityRuleSourceRefSnapshot(
                    sequence=r.sequence,
                    source_version_id=r.source_version_id,
                    content_digest=bytes(r.content_digest_snapshot),
                )
                for r in source_ref_rows
            ),
            created_at=ver_row.created_at,
            updated_at=ver_row.updated_at,
        )

    def _assemble_and_verify_stored_rule_snapshot(
        self,
        version_id: UUID,
        expected_digest: bytes | None = None,
        *,
        validate_predecessor: bool = True,
    ) -> ApplicabilityRuleVersionSnapshot:
        """Compatibility alias for complete aggregate and AST verification."""
        return self._verify_complete_rule_version_aggregate(
            version_id, expected_digest=expected_digest, validate_predecessor=validate_predecessor
        )

    def create_rule_draft(
        self,
        context: CatalogActorContext,
        request_key: str,
        *,
        version_id: UUID,
        content_digest: bytes,
        payload: dict[str, Any],
    ) -> ApplicabilityRuleVersionSnapshot:
        """Create a new ApplicabilityRule draft version with atomic validation and auditing."""
        try:
            # 1. Connection admission & schema translation
            self._verify_postgres_connection_admission()
            self._ensure_schema_translation()

            # 2. Trusted initial DB clock & actor validation & basic input checks
            db_now_initial = self._get_db_time()
            self._validate_author_actor(context, db_now_initial)

            if (
                not isinstance(request_key, str)
                or not (1 <= len(request_key) <= 128)
                or "\n" in request_key
                or "\r" in request_key
                or not REQUEST_KEY_PATTERN.match(request_key)
            ):
                raise CatalogValidationError(
                    f"request_key outside bounded range or format: '{request_key}'"
                )

            if not isinstance(version_id, UUID):
                raise CatalogValidationError(
                    f"version_id must be a UUID instance, got {type(version_id)}"
                )

            if not isinstance(content_digest, bytes) or len(content_digest) != 32:
                raise CatalogValidationError(
                    f"content_digest must be exactly 32 bytes, got {len(content_digest) if isinstance(content_digest, bytes) else type(content_digest)}"
                )

            if not isinstance(payload, dict):
                raise CatalogValidationError(f"payload must be a dictionary, got {type(payload)}")

            # Check payload byte bound
            payload_canonical_bytes = canonical_json(payload).encode("utf-8")
            if len(payload_canonical_bytes) > MAX_PAYLOAD_BYTES:
                raise CatalogValidationError(
                    f"Payload size {len(payload_canonical_bytes)} exceeds maximum limit of {MAX_PAYLOAD_BYTES} bytes"
                )

            # Check exact payload keys
            if frozenset(payload.keys()) != REQUIRED_RULE_PAYLOAD_KEYS:
                missing = REQUIRED_RULE_PAYLOAD_KEYS - frozenset(payload.keys())
                extra = frozenset(payload.keys()) - REQUIRED_RULE_PAYLOAD_KEYS
                raise CatalogValidationError(
                    f"Payload keys mismatch: missing={sorted(missing)}, extra={sorted(extra)}"
                )

            # Validate payload fields
            if payload["kind"] != "ApplicabilityRuleVersion":
                raise CatalogValidationError(
                    f"Invalid kind '{payload['kind']}'; expected 'ApplicabilityRuleVersion'"
                )
            if payload["status"] != "Draft":
                raise CatalogValidationError(
                    f"Invalid status '{payload['status']}'; expected 'Draft'"
                )

            try:
                rule_id_uuid = UUID(payload["rule_id"])
                if str(rule_id_uuid).lower() != payload["rule_id"]:
                    raise ValueError()
            except Exception:
                raise CatalogValidationError("rule_id must be a valid lower-case UUID string")

            rule_key = payload["rule_key"]
            if (
                not isinstance(rule_key, str)
                or not (11 <= len(rule_key) <= 64)
                or "\n" in rule_key
                or "\r" in rule_key
                or not rule_key.startswith("synthetic_")
                or not RULE_KEY_PATTERN.match(rule_key)
            ):
                raise CatalogValidationError(
                    f"rule_key must start with literal 'synthetic_' and be between 11 and 64 characters: '{rule_key}'"
                )

            try:
                req_id_uuid = UUID(payload["requirement_id"])
                if str(req_id_uuid).lower() != payload["requirement_id"]:
                    raise ValueError()
            except Exception:
                raise CatalogValidationError(
                    "requirement_id must be a valid lower-case UUID string"
                )

            revision = payload["revision"]
            if type(revision) is not int or not (1 <= revision <= 32767):
                raise CatalogValidationError("revision must be an integer between 1 and 32767")

            version_label = payload["version_label"]
            if (
                not isinstance(version_label, str)
                or version_label != version_label.strip()
                or not (1 <= len(version_label) <= 64)
                or "\n" in version_label
                or "\r" in version_label
            ):
                raise CatalogValidationError(
                    "version_label must be trimmed string between 1 and 64 characters without newlines"
                )

            pred_id_val = payload["predecessor_id"]
            pred_rev_val = payload["predecessor_revision"]
            if revision == 1:
                if pred_id_val is not None or pred_rev_val is not None:
                    raise CatalogValidationError("Revision 1 must have null predecessor fields")
                predecessor_id_uuid: UUID | None = None
            else:
                if pred_id_val is None or pred_rev_val is None:
                    raise CatalogValidationError(
                        f"Revision {revision} requires non-null predecessor fields"
                    )
                try:
                    predecessor_id_uuid = UUID(pred_id_val)
                    if str(predecessor_id_uuid).lower() != pred_id_val:
                        raise ValueError()
                except Exception:
                    raise CatalogValidationError(
                        "predecessor_id must be a valid lower-case UUID string"
                    )
                if predecessor_id_uuid == version_id:
                    raise CatalogValidationError("predecessor_id cannot equal version_id")
                if type(pred_rev_val) is not int or pred_rev_val != revision - 1:
                    raise CatalogValidationError(f"predecessor_revision must equal {revision - 1}")

            try:
                req_ver_id_uuid = UUID(payload["requirement_version_id"])
                if str(req_ver_id_uuid).lower() != payload["requirement_version_id"]:
                    raise ValueError()
            except Exception:
                raise CatalogValidationError(
                    "requirement_version_id must be a valid lower-case UUID string"
                )

            req_ver_digest_str = payload["requirement_version_digest"]
            if (
                not isinstance(req_ver_digest_str, str)
                or "\n" in req_ver_digest_str
                or "\r" in req_ver_digest_str
                or not HEX_64_PATTERN.match(req_ver_digest_str)
                or req_ver_digest_str != req_ver_digest_str.lower()
            ):
                raise CatalogValidationError(
                    "requirement_version_digest must be 64 lower-case hex characters"
                )
            req_ver_digest_bytes = bytes.fromhex(req_ver_digest_str)

            if (
                type(payload["expression_ast_version"]) is not int
                or payload["expression_ast_version"] != 1
            ):
                raise CatalogValidationError("expression_ast_version must be exact integer 1")

            ast_hex = payload["expression_canonical_hex"]
            if (
                not isinstance(ast_hex, str)
                or any(c.isspace() for c in ast_hex)
                or ast_hex != ast_hex.lower()
                or not re.fullmatch(r"[0-9a-f]+", ast_hex)
                or len(ast_hex) % 2 != 0
            ):
                raise CatalogValidationError(
                    "expression_canonical_hex must be lowercase canonical hex with no whitespace"
                )
            try:
                raw_ast_bytes = bytes.fromhex(ast_hex)
            except Exception:
                raise CatalogValidationError(
                    "expression_canonical_hex contains invalid hex characters"
                )
            if not (2 <= len(raw_ast_bytes) <= 16384):
                raise CatalogValidationError(
                    f"expression_canonical length {len(raw_ast_bytes)} outside 2..16384 byte limits"
                )

            eff_from_str = payload["effective_from"]
            eff_until_str = payload["effective_until"]
            effective_from_date: date | None = None
            effective_until_date: date | None = None
            if eff_from_str is not None:
                if (
                    not isinstance(eff_from_str, str)
                    or "\n" in eff_from_str
                    or "\r" in eff_from_str
                    or not DATE_PATTERN.match(eff_from_str)
                ):
                    raise CatalogValidationError(
                        "effective_from must be canonical YYYY-MM-DD string"
                    )
                try:
                    effective_from_date = date.fromisoformat(eff_from_str)
                except ValueError:
                    raise CatalogValidationError(f"Invalid effective_from date: '{eff_from_str}'")

            if eff_until_str is not None:
                if (
                    not isinstance(eff_until_str, str)
                    or "\n" in eff_until_str
                    or "\r" in eff_until_str
                    or not DATE_PATTERN.match(eff_until_str)
                ):
                    raise CatalogValidationError(
                        "effective_until must be canonical YYYY-MM-DD string"
                    )
                try:
                    effective_until_date = date.fromisoformat(eff_until_str)
                except ValueError:
                    raise CatalogValidationError(f"Invalid effective_until date: '{eff_until_str}'")

            if effective_from_date and effective_until_date:
                if effective_until_date < effective_from_date:
                    raise CatalogValidationError(
                        "effective_until must be greater than or equal to effective_from"
                    )

            # Validate child ref lists
            fact_refs_list = payload["fact_refs"]
            source_refs_list = payload["source_refs"]
            if not isinstance(fact_refs_list, list) or not (1 <= len(fact_refs_list) <= 64):
                raise CatalogValidationError("fact_refs must be a list of 1 to 64 items")
            if not isinstance(source_refs_list, list) or not (1 <= len(source_refs_list) <= 64):
                raise CatalogValidationError("source_refs must be a list of 1 to 64 items")

            expected_f_seqs = list(range(1, len(fact_refs_list) + 1))
            actual_f_seqs = [
                r.get("sequence") if isinstance(r, dict) else None for r in fact_refs_list
            ]
            if actual_f_seqs != expected_f_seqs:
                raise CatalogValidationError(
                    f"fact_refs sequences {actual_f_seqs} are not contiguous 1-indexed {expected_f_seqs}"
                )

            seen_fact_vers = set()
            for r in fact_refs_list:
                if frozenset(r.keys()) != frozenset(
                    {"sequence", "fact_definition_version_id", "content_digest"}
                ):
                    raise CatalogValidationError("fact_ref dictionary keys mismatch")
                try:
                    fv_id = UUID(r["fact_definition_version_id"])
                    if str(fv_id).lower() != r["fact_definition_version_id"]:
                        raise ValueError()
                except Exception:
                    raise CatalogValidationError(
                        "fact_definition_version_id must be valid lower-case UUID string"
                    )
                if fv_id in seen_fact_vers:
                    raise CatalogValidationError(
                        f"Duplicate fact_definition_version_id '{fv_id}' in fact_refs"
                    )
                seen_fact_vers.add(fv_id)
                dig_str = r["content_digest"]
                if (
                    not isinstance(dig_str, str)
                    or "\n" in dig_str
                    or "\r" in dig_str
                    or not HEX_64_PATTERN.match(dig_str)
                    or dig_str != dig_str.lower()
                ):
                    raise CatalogValidationError(
                        "fact_ref content_digest must be 64 lower-case hex characters"
                    )

            expected_s_seqs = list(range(1, len(source_refs_list) + 1))
            actual_s_seqs = [
                r.get("sequence") if isinstance(r, dict) else None for r in source_refs_list
            ]
            if actual_s_seqs != expected_s_seqs:
                raise CatalogValidationError(
                    f"source_refs sequences {actual_s_seqs} are not contiguous 1-indexed {expected_s_seqs}"
                )

            seen_src_vers = set()
            for r in source_refs_list:
                if frozenset(r.keys()) != frozenset(
                    {"sequence", "source_version_id", "content_digest"}
                ):
                    raise CatalogValidationError("source_ref dictionary keys mismatch")
                try:
                    sv_id = UUID(r["source_version_id"])
                    if str(sv_id).lower() != r["source_version_id"]:
                        raise ValueError()
                except Exception:
                    raise CatalogValidationError(
                        "source_version_id must be valid lower-case UUID string"
                    )
                if sv_id in seen_src_vers:
                    raise CatalogValidationError(
                        f"Duplicate source_version_id '{sv_id}' in source_refs"
                    )
                seen_src_vers.add(sv_id)
                dig_str = r["content_digest"]
                if (
                    not isinstance(dig_str, str)
                    or "\n" in dig_str
                    or "\r" in dig_str
                    or not HEX_64_PATTERN.match(dig_str)
                    or dig_str != dig_str.lower()
                ):
                    raise CatalogValidationError(
                        "source_ref content_digest must be 64 lower-case hex characters"
                    )

            # Check computed content digest against claimed digest
            computed_payload_digest = compute_content_digest(payload)
            if computed_payload_digest != content_digest:
                raise CatalogValidationError(
                    f"Claimed content_digest does not match computed payload digest: claimed={content_digest.hex()}, computed={computed_payload_digest.hex()}"
                )

            # 3. Rule advisory lock (R3)
            self._acquire_advisory_lock()

            # 4. Discover immutable source version union (R3)
            # A. Target requirement version & requirement & target source & locators
            target_req_ver = self.session.execute(
                select(
                    CatalogRequirementVersion.id,
                    CatalogRequirementVersion.requirement_id,
                    CatalogRequirementVersion.source_id,
                    CatalogRequirementVersion.source_version_id,
                    CatalogRequirementVersion.version_label,
                    CatalogRequirementVersion.predecessor_id,
                    CatalogRequirementVersion.revision,
                    CatalogRequirementVersion.normalized_outcome,
                    CatalogRequirementVersion.requirement_type,
                    CatalogRequirementVersion.obligated_actor,
                    CatalogRequirementVersion.text_origin,
                    CatalogRequirementVersion.customer_display_text,
                    CatalogRequirementVersion.effective_from,
                    CatalogRequirementVersion.effective_until,
                    CatalogRequirementVersion.status,
                    CatalogRequirementVersion.content_digest,
                )
                .where(CatalogRequirementVersion.id == req_ver_id_uuid)
                .execution_options(populate_existing=True)
            ).one_or_none()

            if target_req_ver is None:
                raise CatalogNotFoundError(
                    f"Target RequirementVersion '{req_ver_id_uuid}' not found"
                )
            if target_req_ver.requirement_id != req_id_uuid:
                raise CatalogValidationError(
                    f"Target RequirementVersion requirement_id {target_req_ver.requirement_id} != {req_id_uuid}"
                )
            if target_req_ver.status != "Draft":
                raise CatalogValidationError(
                    f"Target RequirementVersion status is '{target_req_ver.status}'; expected 'Draft'"
                )

            target_req = self.session.execute(
                select(
                    CatalogRequirement.id,
                    CatalogRequirement.source_id,
                    CatalogRequirement.requirement_key,
                    CatalogRequirement.status,
                )
                .where(CatalogRequirement.id == req_id_uuid)
                .execution_options(populate_existing=True)
            ).one_or_none()
            if target_req is None:
                raise CatalogInvariantError(f"Target Requirement '{req_id_uuid}' not found")
            if target_req.status != "Draft":
                raise CatalogValidationError(
                    f"Target Requirement status is '{target_req.status}'; expected 'Draft'"
                )
            if not target_req.requirement_key.startswith("synthetic_rule_demo_"):
                raise CatalogSecurityError(
                    f"Target Requirement key '{target_req.requirement_key}' does not start with 'synthetic_rule_demo_'"
                )

            # Target requirement source references (locators)
            req_source_refs = self.session.execute(
                select(
                    CatalogRequirementSourceReference.source_version_id,
                    CatalogRequirementSourceReference.sequence,
                    CatalogRequirementSourceReference.locator_kind,
                    CatalogRequirementSourceReference.locator_value,
                )
                .where(CatalogRequirementSourceReference.requirement_version_id == req_ver_id_uuid)
                .order_by(CatalogRequirementSourceReference.sequence.asc())
                .execution_options(populate_existing=True)
            ).all()

            if not (1 <= len(req_source_refs) <= 64):
                raise CatalogValidationError(
                    f"Target RequirementVersion locators count {len(req_source_refs)} outside 1..64"
                )
            expected_req_loc_seqs = list(range(1, len(req_source_refs) + 1))
            actual_req_loc_seqs = [r.sequence for r in req_source_refs]
            if actual_req_loc_seqs != expected_req_loc_seqs:
                raise CatalogValidationError(
                    f"Target RequirementVersion locators sequences {actual_req_loc_seqs} are not contiguous 1-indexed {expected_req_loc_seqs}"
                )

            loc_dicts: list[dict[str, Any]] = []
            for rsr in req_source_refs:
                if not rsr.locator_kind or not rsr.locator_kind.strip():
                    raise CatalogValidationError("Empty locator_kind in requirement locator")
                if not rsr.locator_value or not rsr.locator_value.strip():
                    raise CatalogValidationError("Empty locator_value in requirement locator")
                loc_dicts.append(
                    {
                        "locator_kind": rsr.locator_kind,
                        "locator_value": rsr.locator_value,
                        "sequence": rsr.sequence,
                        "source_version_id": rsr.source_version_id,
                    }
                )

            # Recompute canonical requirement version digest and verify against claimed and stored (R2)
            recomputed_req_digest = compute_requirement_version_digest(
                requirement_id=target_req_ver.requirement_id,
                source_id=target_req_ver.source_id,
                source_version_id=target_req_ver.source_version_id,
                version_label=target_req_ver.version_label,
                predecessor_id=target_req_ver.predecessor_id,
                revision=target_req_ver.revision,
                normalized_outcome=target_req_ver.normalized_outcome,
                requirement_type=target_req_ver.requirement_type,
                obligated_actor=target_req_ver.obligated_actor,
                text_origin=target_req_ver.text_origin,
                customer_display_text=target_req_ver.customer_display_text,
                effective_from=target_req_ver.effective_from,
                effective_until=target_req_ver.effective_until,
                source_references=loc_dicts,
                status=target_req_ver.status,
            )
            if recomputed_req_digest != bytes(target_req_ver.content_digest):
                raise CatalogValidationError(
                    f"Target RequirementVersion digest tampering detected: recomputed {recomputed_req_digest.hex()} != stored {bytes(target_req_ver.content_digest).hex()}"
                )
            if recomputed_req_digest != req_ver_digest_bytes:
                raise CatalogValidationError(
                    "Target RequirementVersion recomputed digest does not match payload snapshot"
                )

            # B. Union of all source version IDs (including predecessor sources under R3)
            all_source_version_ids: set[UUID] = set()
            if target_req_ver.source_version_id:
                all_source_version_ids.add(target_req_ver.source_version_id)
            for rsr in req_source_refs:
                all_source_version_ids.add(rsr.source_version_id)
            for sr in source_refs_list:
                all_source_version_ids.add(UUID(sr["source_version_id"]))

            # If predecessor is consumed (revision > 1), include predecessor's source union under R3
            if revision > 1:
                assert predecessor_id_uuid is not None
                pred_ver_row = self.session.execute(
                    select(
                        CatalogApplicabilityRuleVersion.requirement_version_id,
                    )
                    .where(CatalogApplicabilityRuleVersion.id == predecessor_id_uuid)
                    .execution_options(populate_existing=True)
                ).one_or_none()
                if pred_ver_row is not None:
                    # Predecessor requirement sources
                    pred_req_ver = self.session.execute(
                        select(CatalogRequirementVersion.source_version_id)
                        .where(CatalogRequirementVersion.id == pred_ver_row.requirement_version_id)
                        .execution_options(populate_existing=True)
                    ).one_or_none()
                    if pred_req_ver and pred_req_ver.source_version_id:
                        all_source_version_ids.add(pred_req_ver.source_version_id)
                    pred_req_locs = (
                        self.session.execute(
                            select(CatalogRequirementSourceReference.source_version_id)
                            .where(
                                CatalogRequirementSourceReference.requirement_version_id
                                == pred_ver_row.requirement_version_id
                            )
                            .execution_options(populate_existing=True)
                        )
                        .scalars()
                        .all()
                    )
                    for s_id in pred_req_locs:
                        all_source_version_ids.add(s_id)
                    # Predecessor explicit rule source_refs
                    pred_rule_srcs = (
                        self.session.execute(
                            select(CatalogApplicabilityRuleSourceRef.source_version_id)
                            .where(
                                CatalogApplicabilityRuleSourceRef.rule_version_id
                                == predecessor_id_uuid
                            )
                            .execution_options(populate_existing=True)
                        )
                        .scalars()
                        .all()
                    )
                    for s_id in pred_rule_srcs:
                        all_source_version_ids.add(s_id)

            # C. Verify all source versions and their parent sources via compute_source_version_digest (R2)
            source_ids_to_lock: set[UUID] = set()
            src_digest_map: dict[UUID, bytes] = {}
            for sv_id in all_source_version_ids:
                s_ver = self.session.execute(
                    select(
                        CatalogSourceVersion.id,
                        CatalogSourceVersion.source_id,
                        CatalogSourceVersion.edition,
                        CatalogSourceVersion.predecessor_id,
                        CatalogSourceVersion.language,
                        CatalogSourceVersion.official_locator,
                        CatalogSourceVersion.publication_date,
                        CatalogSourceVersion.retrieved_at,
                        CatalogSourceVersion.status,
                        CatalogSourceVersion.content_digest,
                    )
                    .where(CatalogSourceVersion.id == sv_id)
                    .execution_options(populate_existing=True)
                ).one_or_none()
                if s_ver is None:
                    raise CatalogNotFoundError(f"Referenced SourceVersion '{sv_id}' not found")
                if s_ver.status != "Draft":
                    raise CatalogValidationError(
                        f"Referenced SourceVersion '{sv_id}' status is '{s_ver.status}'; expected 'Draft'"
                    )

                parent_source = self.session.execute(
                    select(CatalogSource.id, CatalogSource.source_key, CatalogSource.status)
                    .where(CatalogSource.id == s_ver.source_id)
                    .execution_options(populate_existing=True)
                ).one_or_none()
                if parent_source is None:
                    raise CatalogInvariantError(
                        f"Parent Source '{s_ver.source_id}' not found for version '{sv_id}'"
                    )
                if parent_source.status != "Draft":
                    raise CatalogValidationError(
                        f"Parent Source '{parent_source.id}' status is '{parent_source.status}'; expected 'Draft'"
                    )
                if not parent_source.source_key.startswith("synthetic_rule_demo_"):
                    raise CatalogSecurityError(
                        f"Referenced Source key '{parent_source.source_key}' does not start with 'synthetic_rule_demo_'"
                    )

                recomputed_src_digest = compute_source_version_digest(
                    source_id=s_ver.source_id,
                    edition=s_ver.edition,
                    predecessor_id=s_ver.predecessor_id,
                    language=s_ver.language,
                    official_locator=s_ver.official_locator,
                    publication_date=s_ver.publication_date,
                    retrieved_at=s_ver.retrieved_at,
                    status=s_ver.status,
                )
                if recomputed_src_digest != bytes(s_ver.content_digest):
                    raise CatalogValidationError(
                        f"SourceVersion digest tampering detected for '{sv_id}': recomputed {recomputed_src_digest.hex()} != stored {bytes(s_ver.content_digest).hex()}"
                    )
                src_digest_map[sv_id] = recomputed_src_digest
                source_ids_to_lock.add(parent_source.id)

            # Check explicit source_refs content digests against canonical source digests
            for sr in source_refs_list:
                sv_id = UUID(sr["source_version_id"])
                actual_digest = src_digest_map[sv_id]
                if actual_digest.hex() != sr["content_digest"]:
                    raise CatalogValidationError(
                        f"Explicit source_ref digest mismatch for '{sv_id}': actual {actual_digest.hex()} != claimed {sr['content_digest']}"
                    )

            # 5. Lock source permission guards sorted (R3)
            guards = lock_source_guards_sorted(self.session, source_ids_to_lock)
            if len(guards) != len(source_ids_to_lock):
                raise CatalogSecurityError("Missing required source permission guards")

            # 6. Refreshed DB clock & recheck actor freshness & effective permissions (R3)
            db_now = self._get_db_time()
            self._validate_author_actor(context, db_now)

            # Recheck effective permissions (reference and store) for all source versions at db_now
            for sv_id in sorted(all_source_version_ids, key=str):
                evaluate_effective_permission(self.session, sv_id, "reference", "global", db_now)
                evaluate_effective_permission(self.session, sv_id, "store", "global", db_now)

            # 7. Dedicated audit head lock / init (R3)
            lock_or_init_audit_head(
                self.session, chain_key=APPLICABILITY_RULE_DRAFT_CHAIN_KEY, db_time=db_now
            )

            # 8. Check or record mutation receipt (idempotency boundary)
            fingerprint_data: dict[str, Any] = {
                "actor_id": str(context.actor_id),
                "content_digest": content_digest.hex(),
                "operation": "applicability_rule.create_draft",
                "payload": payload,
                "request_key": request_key,
                "version_id": str(version_id),
            }

            def _result_provider() -> tuple[UUID, str, int, bytes]:
                return (
                    version_id,
                    "ApplicabilityRuleVersion",
                    revision,
                    content_digest,
                )

            is_duplicate, existing_receipt = check_or_record_mutation_receipt(
                session=self.session,
                actor_id=context.actor_id,
                operation="applicability_rule.create_draft",
                request_key=request_key,
                request_data=fingerprint_data,
                result_provider=_result_provider,
                db_time=db_now,
            )

            if is_duplicate:
                # Revalidate complete verified aggregate & AST before returning cached snapshot (R1)
                snapshot = self._verify_complete_rule_version_aggregate(
                    version_id, expected_digest=content_digest
                )
                append_catalog_audit_event(
                    session=self.session,
                    actor_id=context.actor_id,
                    action="applicability_rule.retry_draft",
                    resource_type="ApplicabilityRuleVersion",
                    resource_id=version_id,
                    request_key=request_key,
                    outcome="Success",
                    metadata={"status": snapshot.status, "revision": snapshot.revision},
                    db_time=db_now,
                    chain_key=APPLICABILITY_RULE_DRAFT_CHAIN_KEY,
                )
                return snapshot

            # 9. Parent rule identity & predecessor validation
            if revision == 1:
                existing_rule = self.session.execute(
                    select(CatalogApplicabilityRule.id).where(
                        CatalogApplicabilityRule.id == rule_id_uuid
                    )
                ).scalar_one_or_none()
                if existing_rule is not None:
                    raise CatalogConflictError(f"ApplicabilityRule '{rule_id_uuid}' already exists")

                existing_rule_key = self.session.execute(
                    select(CatalogApplicabilityRule.id).where(
                        CatalogApplicabilityRule.rule_key == rule_key
                    )
                ).scalar_one_or_none()
                if existing_rule_key is not None:
                    raise CatalogConflictError(f"ApplicabilityRule key '{rule_key}' already exists")
            else:
                # Lock parent rule row FOR UPDATE
                parent_rule = self.session.execute(
                    select(CatalogApplicabilityRule)
                    .where(CatalogApplicabilityRule.id == rule_id_uuid)
                    .with_for_update()
                ).scalar_one_or_none()

                if parent_rule is None:
                    raise CatalogNotFoundError(
                        f"Parent ApplicabilityRule '{rule_id_uuid}' not found for revision {revision}"
                    )
                if parent_rule.requirement_id != req_id_uuid:
                    raise CatalogValidationError("Cannot relink rule to different requirement")
                if parent_rule.rule_key != rule_key:
                    raise CatalogValidationError(
                        f"rule_key mismatch: expected '{parent_rule.rule_key}', got '{rule_key}'"
                    )

                latest_rev = self.session.execute(
                    select(func.coalesce(func.max(CatalogApplicabilityRuleVersion.revision), 0))
                    .where(CatalogApplicabilityRuleVersion.rule_id == rule_id_uuid)
                    .execution_options(populate_existing=True)
                ).scalar_one()

                if revision != latest_rev + 1:
                    raise CatalogConflictError(
                        f"Revision {revision} conflict for ApplicabilityRule '{rule_id_uuid}'; current maximum revision is {latest_rev}, expected {latest_rev + 1}"
                    )

                # Verify predecessor version using complete verified aggregate (R1)
                assert predecessor_id_uuid is not None
                pred_snap = self._verify_complete_rule_version_aggregate(predecessor_id_uuid)
                if pred_snap.rule_id != rule_id_uuid:
                    raise CatalogInvariantError("Predecessor version belongs to different rule")
                if pred_snap.revision != revision - 1:
                    raise CatalogInvariantError(
                        f"Predecessor revision mismatch: expected {revision - 1}, got {pred_snap.revision}"
                    )
                if pred_snap.requirement_id != req_id_uuid:
                    raise CatalogInvariantError(
                        "Predecessor version requirement_id does not match parent rule requirement_id"
                    )

            # 10. Read verified fact snapshots and validate rule AST (R1)
            metadata_dict: dict[UUID, FactVersionMetadata] = {}
            ordered_fact_version_ids: list[UUID] = []

            for r in fact_refs_list:
                fv_id = UUID(r["fact_definition_version_id"])
                expected_fact_digest = bytes.fromhex(r["content_digest"])

                fact_snap = read_verified_fact_definition_snapshot(
                    self.session, fv_id, expected_digest=expected_fact_digest
                )
                if fact_snap.status != "Draft":
                    raise CatalogValidationError(
                        f"Referenced FactDefinitionVersion '{fv_id}' status is '{fact_snap.status}'; expected 'Draft'"
                    )
                if not fact_snap.fact_key.startswith("synthetic_"):
                    raise CatalogSecurityError(
                        f"Referenced fact_key '{fact_snap.fact_key}' does not start with 'synthetic_'"
                    )

                ordered_fact_version_ids.append(fv_id)
                metadata_dict[fv_id] = FactVersionMetadata(
                    fact_definition_id=fact_snap.fact_definition_id,
                    value_type=fact_snap.value_type,
                    scope_types=frozenset(s.scope_type for s in fact_snap.allowed_scopes),
                    enum_codes=frozenset(e.code for e in fact_snap.enum_values),
                )

            # Validate rule AST
            try:
                validated_ast = validate_rule_ast(
                    raw_ast_bytes, metadata_dict, ordered_fact_version_ids
                )
                if validated_ast.canonical_bytes != raw_ast_bytes:
                    raise CatalogValidationError(
                        "expression_canonical_hex is not canonical AST encoding"
                    )
            except RuleValidationError as rve:
                raise CatalogValidationError(f"Rule AST validation failed: {rve.code}") from rve

            # 11. Insert database rows
            if revision == 1:
                rule_row = CatalogApplicabilityRule(
                    id=rule_id_uuid,
                    requirement_id=req_id_uuid,
                    rule_key=rule_key,
                    status="Draft",
                    created_at=db_now,
                    updated_at=db_now,
                )
                self.session.add(rule_row)
                self.session.flush()

            ver_row = CatalogApplicabilityRuleVersion(
                id=version_id,
                rule_id=rule_id_uuid,
                requirement_id=req_id_uuid,
                requirement_version_id=req_ver_id_uuid,
                requirement_version_digest_snapshot=req_ver_digest_bytes,
                revision=revision,
                version_label=version_label,
                predecessor_id=predecessor_id_uuid,
                predecessor_revision=pred_rev_val,
                expression_ast_version=1,
                expression_canonical=raw_ast_bytes,
                effective_from=effective_from_date,
                effective_until=effective_until_date,
                status="Draft",
                content_digest=content_digest,
                digest_schema=APPLICABILITY_RULE_DIGEST_SCHEMA,
                created_at=db_now,
                updated_at=db_now,
            )
            self.session.add(ver_row)
            try:
                self.session.flush()
            except (IntegrityError, ProgrammingError, OperationalError) as db_err:
                err_str = str(db_err)
                if (
                    "Invalid revision" in err_str
                    or "Invalid sequence" in err_str
                    or "already exists" in err_str
                    or "duplicate key" in err_str
                    or "unique constraint" in err_str
                    or "could not serialize" in err_str
                    or "deadlock detected" in err_str
                ):
                    raise CatalogConflictError(
                        f"Concurrency conflict during rule draft creation: {db_err}"
                    ) from db_err
                raise

            for r in fact_refs_list:
                fref = CatalogApplicabilityRuleFactRef(
                    rule_version_id=version_id,
                    sequence=r["sequence"],
                    fact_definition_version_id=UUID(r["fact_definition_version_id"]),
                    content_digest_snapshot=bytes.fromhex(r["content_digest"]),
                    created_at=db_now,
                )
                self.session.add(fref)

            for r in source_refs_list:
                sref = CatalogApplicabilityRuleSourceRef(
                    rule_version_id=version_id,
                    sequence=r["sequence"],
                    source_version_id=UUID(r["source_version_id"]),
                    content_digest_snapshot=bytes.fromhex(r["content_digest"]),
                    created_at=db_now,
                )
                self.session.add(sref)

            try:
                self.session.flush()
            except (IntegrityError, ProgrammingError, OperationalError) as db_err:
                err_str = str(db_err)
                if (
                    "Invalid revision" in err_str
                    or "Invalid sequence" in err_str
                    or "already exists" in err_str
                    or "duplicate key" in err_str
                    or "unique constraint" in err_str
                    or "could not serialize" in err_str
                    or "deadlock detected" in err_str
                ):
                    raise CatalogConflictError(
                        f"Concurrency conflict during rule draft creation: {db_err}"
                    ) from db_err
                raise

            # 12. Post-flush genuine stored-row reconstruction & digest verification (R1)
            snapshot = self._verify_complete_rule_version_aggregate(
                version_id, expected_digest=content_digest
            )

            # 13. Record event intent with namespaced key
            intent_request_key = hashlib.sha256(
                canonical_json(
                    {
                        "actor_id": str(context.actor_id),
                        "operation": "applicability_rule.create_draft",
                        "request_key": request_key,
                    }
                ).encode("utf-8")
            ).hexdigest()

            record_catalog_event_intent(
                session=self.session,
                request_key=intent_request_key,
                event_kind="ApplicabilityRuleDraftCreated",
                aggregate_id=version_id,
                aggregate_type="ApplicabilityRuleVersion",
                revision=revision,
                content_digest=content_digest,
                db_time=db_now,
            )

            # Append audit event
            append_catalog_audit_event(
                session=self.session,
                actor_id=context.actor_id,
                action="applicability_rule.create_draft",
                resource_type="ApplicabilityRuleVersion",
                resource_id=version_id,
                request_key=request_key,
                outcome="Success",
                metadata={"status": snapshot.status, "revision": snapshot.revision},
                db_time=db_now,
                chain_key=APPLICABILITY_RULE_DRAFT_CHAIN_KEY,
            )

            return snapshot

        except Exception as e:
            self.session.rollback()
            try:
                self._record_denial_unswallowed(
                    actor_id=getattr(context, "actor_id", None)
                    if isinstance(context, CatalogActorContext)
                    else None,
                    operation="applicability_rule.create_draft",
                    reason_code=self._classify_error_code(e),
                    request_key=request_key if isinstance(request_key, str) else None,
                )
            except Exception as sink_err:
                raise sink_err from e
            raise e

    def get_rule_version(
        self,
        context: CatalogActorContext,
        request_key: str,
        version_id: UUID,
    ) -> ApplicabilityRuleVersionSnapshot:
        """Retrieve stored ApplicabilityRuleVersion snapshot with verification and read audit."""
        try:
            # 1. Connection admission & schema translation (R4)
            self._verify_postgres_connection_admission()
            self._ensure_schema_translation()

            # 2. Trusted initial DB clock & actor validation & input checks (R3)
            db_time_initial = self._get_db_time()
            self._validate_reader_actor(context, db_time_initial)

            if (
                not isinstance(request_key, str)
                or not (1 <= len(request_key) <= 128)
                or "\n" in request_key
                or "\r" in request_key
                or not REQUEST_KEY_PATTERN.match(request_key)
            ):
                raise CatalogValidationError(
                    f"request_key outside bounded range or format: '{request_key}'"
                )

            if not isinstance(version_id, UUID):
                raise CatalogValidationError(
                    f"version_id must be a UUID instance, got {type(version_id)}"
                )

            # 3. Rule advisory lock (R3)
            self._acquire_advisory_lock()

            # 4. Discover immutable source version union for this rule version (R3)
            ver_sources_row = self.session.execute(
                select(
                    CatalogApplicabilityRuleVersion.requirement_version_id,
                    CatalogApplicabilityRuleVersion.predecessor_id,
                )
                .where(CatalogApplicabilityRuleVersion.id == version_id)
                .execution_options(populate_existing=True)
            ).one_or_none()

            if ver_sources_row is None:
                raise CatalogNotFoundError(
                    f"ApplicabilityRuleVersion '{version_id}' not found in database"
                )

            req_ver_sources = self.session.execute(
                select(CatalogRequirementVersion.source_version_id)
                .where(CatalogRequirementVersion.id == ver_sources_row.requirement_version_id)
                .execution_options(populate_existing=True)
            ).one_or_none()

            req_loc_sources = (
                self.session.execute(
                    select(CatalogRequirementSourceReference.source_version_id)
                    .where(
                        CatalogRequirementSourceReference.requirement_version_id
                        == ver_sources_row.requirement_version_id
                    )
                    .execution_options(populate_existing=True)
                )
                .scalars()
                .all()
            )

            rule_explicit_sources = (
                self.session.execute(
                    select(CatalogApplicabilityRuleSourceRef.source_version_id)
                    .where(CatalogApplicabilityRuleSourceRef.rule_version_id == version_id)
                    .execution_options(populate_existing=True)
                )
                .scalars()
                .all()
            )

            all_source_version_ids: set[UUID] = set()
            if req_ver_sources and req_ver_sources.source_version_id:
                all_source_version_ids.add(req_ver_sources.source_version_id)
            for s_id in req_loc_sources:
                all_source_version_ids.add(s_id)
            for s_id in rule_explicit_sources:
                all_source_version_ids.add(s_id)

            if ver_sources_row.predecessor_id:
                pred_row = self.session.execute(
                    select(CatalogApplicabilityRuleVersion.requirement_version_id)
                    .where(CatalogApplicabilityRuleVersion.id == ver_sources_row.predecessor_id)
                    .execution_options(populate_existing=True)
                ).one_or_none()
                if pred_row:
                    pred_req_ver = self.session.execute(
                        select(CatalogRequirementVersion.source_version_id)
                        .where(CatalogRequirementVersion.id == pred_row.requirement_version_id)
                        .execution_options(populate_existing=True)
                    ).one_or_none()
                    if pred_req_ver and pred_req_ver.source_version_id:
                        all_source_version_ids.add(pred_req_ver.source_version_id)
                    pred_locs = (
                        self.session.execute(
                            select(CatalogRequirementSourceReference.source_version_id)
                            .where(
                                CatalogRequirementSourceReference.requirement_version_id
                                == pred_row.requirement_version_id
                            )
                            .execution_options(populate_existing=True)
                        )
                        .scalars()
                        .all()
                    )
                    for s_id in pred_locs:
                        all_source_version_ids.add(s_id)
                pred_rule_srcs = (
                    self.session.execute(
                        select(CatalogApplicabilityRuleSourceRef.source_version_id)
                        .where(
                            CatalogApplicabilityRuleSourceRef.rule_version_id
                            == ver_sources_row.predecessor_id
                        )
                        .execution_options(populate_existing=True)
                    )
                    .scalars()
                    .all()
                )
                for s_id in pred_rule_srcs:
                    all_source_version_ids.add(s_id)

            # Discover parent source IDs for locking
            source_ids_to_lock: set[UUID] = set()
            for sv_id in all_source_version_ids:
                s_parent_id = self.session.execute(
                    select(CatalogSourceVersion.source_id)
                    .where(CatalogSourceVersion.id == sv_id)
                    .execution_options(populate_existing=True)
                ).scalar_one_or_none()
                if s_parent_id:
                    source_ids_to_lock.add(s_parent_id)

            # 5. Lock source permission guards sorted (R3)
            guards = lock_source_guards_sorted(self.session, source_ids_to_lock)
            if len(guards) != len(source_ids_to_lock):
                raise CatalogSecurityError("Missing required source permission guards")

            # 6. Refreshed DB clock & recheck reader actor & evaluate effective permissions (R3)
            db_time = self._get_db_time()
            self._validate_reader_actor(context, db_time)

            for sv_id in sorted(all_source_version_ids, key=str):
                evaluate_effective_permission(self.session, sv_id, "reference", "global", db_time)
                evaluate_effective_permission(self.session, sv_id, "store", "global", db_time)

            # 7. Dedicated audit head lock / init (R3)
            lock_or_init_audit_head(
                self.session, chain_key=APPLICABILITY_RULE_DRAFT_CHAIN_KEY, db_time=db_time
            )

            # 8. Query and verify complete stored snapshot & AST (R1)
            snapshot = self._verify_complete_rule_version_aggregate(version_id)

            # 9. Append read audit event
            append_catalog_audit_event(
                session=self.session,
                actor_id=context.actor_id,
                action="applicability_rule.get_draft",
                resource_type="ApplicabilityRuleVersion",
                resource_id=version_id,
                request_key=request_key,
                outcome="Success",
                metadata={"status": snapshot.status, "revision": snapshot.revision},
                db_time=db_time,
                chain_key=APPLICABILITY_RULE_DRAFT_CHAIN_KEY,
            )

            return snapshot

        except Exception as e:
            self.session.rollback()
            try:
                self._record_denial_unswallowed(
                    actor_id=getattr(context, "actor_id", None)
                    if isinstance(context, CatalogActorContext)
                    else None,
                    operation="applicability_rule.get_draft",
                    reason_code=self._classify_error_code(e),
                    request_key=request_key if isinstance(request_key, str) else None,
                )
            except Exception as sink_err:
                raise sink_err from e
            raise e
