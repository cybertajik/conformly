import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import TenantContext
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.crypto.types import EncryptionContext
from conformly.identity.models import Membership
from conformly.tenancy.rls import set_anonymous_tenant_rls_context
from conformly.whistleblower.models import (
    WHISTLEBLOWER_CASE_TRANSITIONS,
    WhistleblowerCase,
    WhistleblowerCaseAssignment,
    WhistleblowerCaseStatus,
    WhistleblowerMessage,
    WhistleblowerMessageSender,
    WhistleblowerPortal,
)


class WhistleblowerError(Exception):
    """Base exception for Whistleblower module errors."""


class WhistleblowerPortalNotFoundError(WhistleblowerError):
    """Raised when a requested whistleblower portal is not found."""


class WhistleblowerCaseNotFoundError(WhistleblowerError):
    """Raised when a requested case is not found."""


class WhistleblowerUnauthorizedError(WhistleblowerError):
    """Raised when return credentials or handler permissions are invalid."""


class WhistleblowerSlugConflictError(WhistleblowerError):
    """Raised when a portal slug is already taken."""


class WhistleblowerConcurrencyConflictError(WhistleblowerError):
    """Raised when an expected version check fails."""


class WhistleblowerInvalidTransitionError(WhistleblowerError):
    """Raised when attempting an invalid case state transition."""


class WhistleblowerClosedCaseError(WhistleblowerError):
    """Raised when attempting to add messages to a closed case."""


class WhistleblowerInvalidHandlerError(WhistleblowerError):
    """Raised when assigning a non-member as handler."""


# ── Cryptographic Helpers ──────────────────────────────────────────────────


def generate_return_secret() -> str:
    """Generate a 256-bit CSPRNG return secret token."""
    return f"wb_{secrets.token_urlsafe(32)}"


def hash_return_secret(
    secret: str, salt: bytes | None = None, iterations: int = 100_000
) -> tuple[str, str]:
    """Derive a salted PBKDF2-HMAC-SHA256 hash. Returns (salt_hex, hash_hex)."""
    if salt is None:
        salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations)
    return salt.hex(), derived.hex()


def verify_return_secret(
    secret: str, salt_hex: str, hash_hex: str, iterations: int = 100_000
) -> bool:
    """Verify a secret against the salted PBKDF2 hash using constant-time comparison."""
    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, TypeError):
        return False
    derived = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(derived, expected)


def generate_public_case_id() -> str:
    """Generate a human-readable high-entropy case identifier (e.g. WB-2026-A1B2C3)."""
    year = datetime.now(UTC).year
    suffix = secrets.token_hex(4).upper()
    return f"WB-{year}-{suffix}"


# ── Whistleblower Service ──────────────────────────────────────────────────


class WhistleblowerService:
    """Core domain service for anonymous whistleblower reporting and case handling."""

    def __init__(
        self,
        session: Session,
        codec: EncryptedFieldCodec | None = None,
    ) -> None:
        self._session = session
        self._codec = codec or get_encrypted_field_codec()

    def _encrypt_text(
        self,
        tenant_id: UUID,
        resource_type: str,
        resource_id: str,
        field_name: str,
        plaintext: str,
    ) -> dict[str, Any]:
        ctx = EncryptionContext(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            field_name=field_name,
        )
        return self._codec.encrypt_text(plaintext, ctx)

    def _decrypt_text(
        self,
        tenant_id: UUID,
        resource_type: str,
        resource_id: str,
        field_name: str,
        ciphertext_dict: dict[str, Any] | None,
    ) -> str | None:
        if ciphertext_dict is None:
            return None
        ctx = EncryptionContext(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            field_name=field_name,
        )
        return self._codec.decrypt_text(ciphertext_dict, ctx)

    def decrypt_case_metadata(self, case: WhistleblowerCase) -> tuple[str, str]:
        """Decrypt protected case category/title, with legacy read compatibility."""
        category = self._decrypt_text(
            case.tenant_id,
            "whistleblower_case",
            str(case.id),
            "category",
            case.encrypted_category,
        )
        title = self._decrypt_text(
            case.tenant_id,
            "whistleblower_case",
            str(case.id),
            "title",
            case.encrypted_title,
        )
        return category or case.category or "", title or case.title or ""

    # ── Public Portal & Anonymous Intake ───────────────────────────────────

    def get_public_portal(self, slug: str) -> WhistleblowerPortal:
        """Fetch active portal by slug for public anonymous intake."""
        stmt = select(WhistleblowerPortal).where(
            WhistleblowerPortal.slug == slug,
            WhistleblowerPortal.is_active.is_(True),
        )
        portal = self._session.scalar(stmt)
        if portal is None:
            raise WhistleblowerPortalNotFoundError(f"Portal '{slug}' not found")
        return portal

    def submit_report(
        self,
        slug: str,
        category: str,
        title: str,
        summary: str,
    ) -> tuple[WhistleblowerCase, str]:
        """Submit an anonymous whistleblower report.

        Returns the created case and the plaintext return secret (generated ONCE).
        Plaintext secret is never stored in DB and never written to audit logs.
        """
        portal = self.get_public_portal(slug)
        set_anonymous_tenant_rls_context(self._session, tenant_id=portal.tenant_id)

        clean_category = category.strip().lower()
        clean_title = title.strip()
        clean_summary = summary.strip()

        if not clean_title:
            raise ValueError("Title is required")
        if not clean_summary:
            raise ValueError("Summary is required")

        # Generate unique public case id
        while True:
            public_case_id = generate_public_case_id()
            existing = self._session.scalar(
                select(WhistleblowerCase.id).where(
                    WhistleblowerCase.public_case_id == public_case_id
                )
            )
            if not existing:
                break

        # Generate 256-bit return secret and salted verifier
        return_secret = generate_return_secret()
        salt_hex, hash_hex = hash_return_secret(return_secret)

        case_id = uuid4()
        encrypted_summary = self._encrypt_text(
            tenant_id=portal.tenant_id,
            resource_type="whistleblower_case",
            resource_id=str(case_id),
            field_name="summary",
            plaintext=clean_summary,
        )
        encrypted_category = self._encrypt_text(
            portal.tenant_id,
            "whistleblower_case",
            str(case_id),
            "category",
            clean_category,
        )
        encrypted_title = self._encrypt_text(
            portal.tenant_id,
            "whistleblower_case",
            str(case_id),
            "title",
            clean_title,
        )

        case = WhistleblowerCase(
            id=case_id,
            tenant_id=portal.tenant_id,
            portal_id=portal.id,
            public_case_id=public_case_id,
            return_secret_salt=salt_hex,
            return_secret_hash=hash_hex,
            status=WhistleblowerCaseStatus.SUBMITTED,
            category=None,
            title=None,
            encrypted_category=encrypted_category,
            encrypted_title=encrypted_title,
            encrypted_summary=encrypted_summary,
            version=1,
        )
        self._session.add(case)
        self._session.flush()

        # Add initial reporter message containing the full summary
        msg_id = uuid4()
        encrypted_body = self._encrypt_text(
            tenant_id=portal.tenant_id,
            resource_type="whistleblower_message",
            resource_id=str(msg_id),
            field_name="body",
            plaintext=clean_summary,
        )
        initial_msg = WhistleblowerMessage(
            id=msg_id,
            tenant_id=portal.tenant_id,
            case_id=case.id,
            sender_type=WhistleblowerMessageSender.REPORTER,
            encrypted_body=encrypted_body,
            sent_by_user_id=None,
        )
        self._session.add(initial_msg)
        self._session.flush()

        # Audit event with safe metadata only — zero secrets, zero plaintext, zero IP
        record_audit_event(
            self._session,
            tenant_id=portal.tenant_id,
            actor_type=AuditActorType.ANONYMOUS_REPORTER,
            actor_id=None,
            action="whistleblower.case_submitted",
            resource_type="whistleblower_case",
            resource_id=str(case.id),
            request_id=f"wb:submit:{case.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "portal_id": str(portal.id),
                "portal_slug": portal.slug,
                "case_id": str(case.id),
                "public_case_id": case.public_case_id,
                "case_status": case.status.value,
            },
        )

        return case, return_secret

    def access_case_public(
        self,
        slug: str,
        public_case_id: str,
        return_secret: str,
    ) -> tuple[WhistleblowerCase, list[dict[str, Any]]]:
        """Verify anonymous return credentials and retrieve case details & decrypted messages."""
        portal = self.get_public_portal(slug)
        set_anonymous_tenant_rls_context(self._session, tenant_id=portal.tenant_id)

        stmt = (
            select(WhistleblowerCase)
            .where(
                WhistleblowerCase.portal_id == portal.id,
                WhistleblowerCase.public_case_id == public_case_id.strip(),
            )
            .options(selectinload(WhistleblowerCase.messages))
        )
        case = self._session.scalar(stmt)
        if case is None:
            raise WhistleblowerUnauthorizedError("Invalid case ID or return secret")

        # Constant-time PBKDF2 verification
        if not verify_return_secret(
            return_secret.strip(), case.return_secret_salt, case.return_secret_hash
        ):
            raise WhistleblowerUnauthorizedError("Invalid case ID or return secret")

        # Query messages directly to avoid stale relationship cache
        msg_stmt = (
            select(WhistleblowerMessage)
            .where(WhistleblowerMessage.case_id == case.id)
            .order_by(WhistleblowerMessage.created_at.asc())
        )
        case_messages = list(self._session.scalars(msg_stmt).all())

        # Decrypt messages for reporter
        decrypted_messages: list[dict[str, Any]] = []
        for msg in case_messages:
            body = self._decrypt_text(
                tenant_id=case.tenant_id,
                resource_type="whistleblower_message",
                resource_id=str(msg.id),
                field_name="body",
                ciphertext_dict=msg.encrypted_body,
            )
            decrypted_messages.append(
                {
                    "id": str(msg.id),
                    "tenant_id": str(msg.tenant_id),
                    "case_id": str(msg.case_id),
                    "sender_type": msg.sender_type.value,
                    "body": body or "",
                    "created_at": msg.created_at.isoformat(),
                }
            )

        return case, decrypted_messages

    def add_reporter_message(
        self,
        slug: str,
        public_case_id: str,
        return_secret: str,
        body: str,
    ) -> WhistleblowerMessage:
        """Post a follow-up message from an anonymous reporter."""
        case, _ = self.access_case_public(slug, public_case_id, return_secret)

        if case.status in (
            WhistleblowerCaseStatus.RESOLVED,
            WhistleblowerCaseStatus.DISMISSED,
        ):
            raise WhistleblowerClosedCaseError("Cannot message on a closed case")

        clean_body = body.strip()
        if not clean_body:
            raise ValueError("Message body is required")

        msg_id = uuid4()
        encrypted_body = self._encrypt_text(
            tenant_id=case.tenant_id,
            resource_type="whistleblower_message",
            resource_id=str(msg_id),
            field_name="body",
            plaintext=clean_body,
        )

        msg = WhistleblowerMessage(
            id=msg_id,
            tenant_id=case.tenant_id,
            case_id=case.id,
            sender_type=WhistleblowerMessageSender.REPORTER,
            encrypted_body=encrypted_body,
            sent_by_user_id=None,
        )
        msg.case = case
        self._session.add(msg)
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=case.tenant_id,
            actor_type=AuditActorType.ANONYMOUS_REPORTER,
            actor_id=None,
            action="whistleblower.message_sent",
            resource_type="whistleblower_case",
            resource_id=str(case.id),
            request_id=f"wb:msg:{msg.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "case_id": str(case.id),
                "public_case_id": case.public_case_id,
                "sender_type": WhistleblowerMessageSender.REPORTER.value,
            },
        )

        return msg

    # ── Authenticated Handler Operations ───────────────────────────────────

    def get_tenant_portal(self, tenant_context: TenantContext) -> WhistleblowerPortal | None:
        """Get the whistleblower portal configuration for the current tenant."""
        stmt = select(WhistleblowerPortal).where(
            WhistleblowerPortal.tenant_id == tenant_context.tenant_id
        )
        return self._session.scalar(stmt)

    def setup_or_update_portal(
        self,
        tenant_context: TenantContext,
        slug: str,
        title: str,
        welcome_text: str,
        is_active: bool,
        expected_version: int | None = None,
    ) -> WhistleblowerPortal:
        """Configure or update the whistleblower portal for a tenant."""
        clean_slug = slug.strip().lower()
        clean_title = title.strip()
        clean_welcome = welcome_text.strip()

        if not clean_slug:
            raise ValueError("Portal slug is required")
        if not clean_title:
            raise ValueError("Portal title is required")

        portal = self.get_tenant_portal(tenant_context)

        # Check slug collision across other tenants
        slug_check_stmt = select(WhistleblowerPortal).where(WhistleblowerPortal.slug == clean_slug)
        if portal is not None:
            slug_check_stmt = slug_check_stmt.where(WhistleblowerPortal.id != portal.id)
        if self._session.scalar(slug_check_stmt) is not None:
            raise WhistleblowerSlugConflictError(f"Slug '{clean_slug}' is already taken")

        if portal is None:
            portal = WhistleblowerPortal(
                id=uuid4(),
                tenant_id=tenant_context.tenant_id,
                slug=clean_slug,
                title=clean_title,
                welcome_text=clean_welcome,
                is_active=is_active,
                version=1,
            )
            self._session.add(portal)
            action = "whistleblower.portal_created"
        else:
            if expected_version is not None and portal.version != expected_version:
                raise WhistleblowerConcurrencyConflictError(
                    f"Version conflict: expected {expected_version}, got {portal.version}"
                )
            portal.slug = clean_slug
            portal.title = clean_title
            portal.welcome_text = clean_welcome
            portal.is_active = is_active
            portal.version += 1
            action = "whistleblower.portal_updated"

        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=tenant_context.user_id,
            action=action,
            resource_type="whistleblower_portal",
            resource_id=str(portal.id),
            request_id=f"wb:portal:{portal.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "portal_id": str(portal.id),
                "portal_slug": portal.slug,
                "is_active": portal.is_active,
            },
        )

        return portal

    def list_cases(
        self,
        tenant_context: TenantContext,
        status: WhistleblowerCaseStatus | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[WhistleblowerCase], int]:
        """List tenant whistleblower cases with optional filtering and pagination."""
        base_stmt = select(WhistleblowerCase).where(
            WhistleblowerCase.tenant_id == tenant_context.tenant_id
        )
        if status is not None:
            base_stmt = base_stmt.where(WhistleblowerCase.status == status)

        stmt = base_stmt.options(
            selectinload(WhistleblowerCase.messages),
            selectinload(WhistleblowerCase.assignments),
        ).order_by(WhistleblowerCase.created_at.desc())
        cases = list(self._session.scalars(stmt).all())
        if category is not None:
            requested_category = category.strip().lower()
            cases = [c for c in cases if self.decrypt_case_metadata(c)[0] == requested_category]
        total = len(cases)
        return cases[offset : offset + limit], total

    def get_case(
        self,
        tenant_context: TenantContext,
        case_id: UUID,
    ) -> tuple[WhistleblowerCase, str | None, list[dict[str, Any]]]:
        """Retrieve case with decrypted summary and messages for an authorized handler."""
        stmt = (
            select(WhistleblowerCase)
            .where(
                WhistleblowerCase.id == case_id,
                WhistleblowerCase.tenant_id == tenant_context.tenant_id,
            )
            .options(
                selectinload(WhistleblowerCase.messages),
                selectinload(WhistleblowerCase.assignments),
            )
        )
        case = self._session.scalar(stmt)
        if case is None:
            raise WhistleblowerCaseNotFoundError(f"Case '{case_id}' not found")

        decrypted_summary = self._decrypt_text(
            tenant_id=case.tenant_id,
            resource_type="whistleblower_case",
            resource_id=str(case.id),
            field_name="summary",
            ciphertext_dict=case.encrypted_summary,
        )

        # Query messages directly to avoid stale relationship cache
        msg_stmt = (
            select(WhistleblowerMessage)
            .where(WhistleblowerMessage.case_id == case.id)
            .order_by(WhistleblowerMessage.created_at.asc())
        )
        case_messages = list(self._session.scalars(msg_stmt).all())

        decrypted_messages: list[dict[str, Any]] = []
        for msg in case_messages:
            body = self._decrypt_text(
                tenant_id=case.tenant_id,
                resource_type="whistleblower_message",
                resource_id=str(msg.id),
                field_name="body",
                ciphertext_dict=msg.encrypted_body,
            )
            decrypted_messages.append(
                {
                    "id": str(msg.id),
                    "tenant_id": str(msg.tenant_id),
                    "case_id": str(msg.case_id),
                    "sender_type": msg.sender_type.value,
                    "body": body or "",
                    "sent_by_user_id": str(msg.sent_by_user_id) if msg.sent_by_user_id else None,
                    "created_at": msg.created_at.isoformat(),
                }
            )

        return case, decrypted_summary, decrypted_messages

    def update_case_status(
        self,
        tenant_context: TenantContext,
        case_id: UUID,
        new_status: WhistleblowerCaseStatus,
        closed_reason: str | None = None,
        expected_version: int | None = None,
    ) -> WhistleblowerCase:
        """Transition case status adhering to valid state machine transitions."""
        stmt = select(WhistleblowerCase).where(
            WhistleblowerCase.id == case_id,
            WhistleblowerCase.tenant_id == tenant_context.tenant_id,
        )
        case = self._session.scalar(stmt)
        if case is None:
            raise WhistleblowerCaseNotFoundError(f"Case '{case_id}' not found")

        if expected_version is not None and case.version != expected_version:
            raise WhistleblowerConcurrencyConflictError(
                f"Version conflict: expected {expected_version}, got {case.version}"
            )

        allowed_targets = WHISTLEBLOWER_CASE_TRANSITIONS.get(case.status, frozenset())
        if new_status not in allowed_targets:
            raise WhistleblowerInvalidTransitionError(
                f"Cannot transition from {case.status.value} to {new_status.value}"
            )

        old_status = case.status
        case.status = new_status
        case.version += 1

        if new_status in (
            WhistleblowerCaseStatus.RESOLVED,
            WhistleblowerCaseStatus.DISMISSED,
        ):
            case.closed_at = datetime.now(UTC)
            case.closed_reason = closed_reason.strip() if closed_reason else None

        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=tenant_context.user_id,
            action="whistleblower.case_status_updated",
            resource_type="whistleblower_case",
            resource_id=str(case.id),
            request_id=f"wb:status:{case.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "case_id": str(case.id),
                "public_case_id": case.public_case_id,
                "previous_status": old_status.value,
                "case_status": new_status.value,
                "closed_reason": case.closed_reason,
            },
        )

        return case

    def add_handler_message(
        self,
        tenant_context: TenantContext,
        case_id: UUID,
        body: str,
    ) -> WhistleblowerMessage:
        """Authorized handler sends a message back to the anonymous reporter."""
        stmt = select(WhistleblowerCase).where(
            WhistleblowerCase.id == case_id,
            WhistleblowerCase.tenant_id == tenant_context.tenant_id,
        )
        case = self._session.scalar(stmt)
        if case is None:
            raise WhistleblowerCaseNotFoundError(f"Case '{case_id}' not found")

        if case.status in (
            WhistleblowerCaseStatus.RESOLVED,
            WhistleblowerCaseStatus.DISMISSED,
        ):
            raise WhistleblowerClosedCaseError("Cannot send message on a closed case")

        clean_body = body.strip()
        if not clean_body:
            raise ValueError("Message body is required")

        msg_id = uuid4()
        encrypted_body = self._encrypt_text(
            tenant_id=case.tenant_id,
            resource_type="whistleblower_message",
            resource_id=str(msg_id),
            field_name="body",
            plaintext=clean_body,
        )

        msg = WhistleblowerMessage(
            id=msg_id,
            tenant_id=case.tenant_id,
            case_id=case.id,
            sender_type=WhistleblowerMessageSender.HANDLER,
            encrypted_body=encrypted_body,
            sent_by_user_id=tenant_context.user_id,
        )
        msg.case = case
        self._session.add(msg)

        # Auto-acknowledge if case was in SUBMITTED state
        if case.status == WhistleblowerCaseStatus.SUBMITTED:
            case.status = WhistleblowerCaseStatus.ACKNOWLEDGED
            case.version += 1

        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=tenant_context.user_id,
            action="whistleblower.handler_message_sent",
            resource_type="whistleblower_case",
            resource_id=str(case.id),
            request_id=f"wb:handler_msg:{msg.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "case_id": str(case.id),
                "public_case_id": case.public_case_id,
                "sender_type": WhistleblowerMessageSender.HANDLER.value,
            },
        )

        return msg

    def assign_handler(
        self,
        tenant_context: TenantContext,
        case_id: UUID,
        handler_user_id: UUID,
    ) -> WhistleblowerCaseAssignment:
        """Assign an authorized internal handler to investigate a case."""
        stmt = select(WhistleblowerCase).where(
            WhistleblowerCase.id == case_id,
            WhistleblowerCase.tenant_id == tenant_context.tenant_id,
        )
        case = self._session.scalar(stmt)
        if case is None:
            raise WhistleblowerCaseNotFoundError(f"Case '{case_id}' not found")

        # Verify assigned user is an active member of this tenant
        member_stmt = select(Membership).where(
            Membership.tenant_id == tenant_context.tenant_id,
            Membership.user_id == handler_user_id,
        )
        if self._session.scalar(member_stmt) is None:
            raise WhistleblowerInvalidHandlerError(
                f"User {handler_user_id} is not a member of this tenant"
            )

        assignment = WhistleblowerCaseAssignment(
            id=uuid4(),
            tenant_id=tenant_context.tenant_id,
            case_id=case.id,
            handler_user_id=handler_user_id,
            assigned_by_user_id=tenant_context.user_id,
            assigned_at=datetime.now(UTC),
        )
        self._session.add(assignment)
        self._session.flush()

        record_audit_event(
            self._session,
            tenant_id=tenant_context.tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=tenant_context.user_id,
            action="whistleblower.handler_assigned",
            resource_type="whistleblower_case",
            resource_id=str(case.id),
            request_id=f"wb:assign:{assignment.id}",
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "case_id": str(case.id),
                "public_case_id": case.public_case_id,
                "handler_user_id": str(handler_user_id),
                "assigned_by_user_id": str(tenant_context.user_id),
            },
        )

        return assignment
