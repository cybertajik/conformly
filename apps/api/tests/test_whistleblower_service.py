"""Unit tests for WhistleblowerService: anonymous intake, cryptography,
anti-deanonymization safeguards, two-way messaging, and handler triage.
"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditEvent
from conformly.authz.policy import TenantContext
from conformly.authz.roles import Role
from conformly.crypto.fields import EncryptedFieldCodec
from conformly.identity.models import (
    Membership,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
)
from conformly.storage.models import StoredFile  # noqa: F401
from conformly.whistleblower.models import (
    WhistleblowerCaseStatus,
    WhistleblowerMessageSender,
    WhistleblowerPortal,
)
from conformly.whistleblower.rate_limit import (
    AnonymousWhistleblowerRateLimiter,
    WhistleblowerRateLimitExceeded,
)
from conformly.whistleblower.service import (
    WhistleblowerCaseNotFoundError,
    WhistleblowerClosedCaseError,
    WhistleblowerConcurrencyConflictError,
    WhistleblowerInvalidHandlerError,
    WhistleblowerInvalidTransitionError,
    WhistleblowerPortalNotFoundError,
    WhistleblowerService,
    WhistleblowerSlugConflictError,
    WhistleblowerUnauthorizedError,
    generate_return_secret,
    hash_return_secret,
    verify_return_secret,
)

# ── Helpers ────────────────────────────────────────────────────────────────


def _setup_service(session: Session, codec: EncryptedFieldCodec) -> WhistleblowerService:
    return WhistleblowerService(session, codec=codec)


def _seed_tenant(session: Session, name: str = "Acme Corp") -> Tenant:
    tenant = Tenant(
        id=uuid4(),
        name=name,
        slug=name.lower().replace(" ", "-"),
        status=TenantStatus.ACTIVE,
    )
    session.add(tenant)
    session.flush()
    return tenant


def _seed_user(session: Session, email: str = "user@acme.com") -> User:
    user = User(
        id=uuid4(),
        email=email,
        display_name="Test User",
        oidc_issuer="https://issuer.example.com",
        oidc_subject=f"sub-{uuid4()}",
    )
    session.add(user)
    session.flush()
    return user


def _seed_membership(
    session: Session, tenant_id: UUID, user_id: UUID, role: Role = Role.COMPLIANCE_MANAGER
) -> Membership:
    mem = Membership(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        role=role.value,
        status=MembershipStatus.ACTIVE,
    )
    session.add(mem)
    session.flush()
    return mem


# ── Tests ──────────────────────────────────────────────────────────────────


class TestReturnSecretCryptography:
    def test_generate_and_verify_secret(self) -> None:
        secret = generate_return_secret()
        assert secret.startswith("wb_")
        assert len(secret) > 30

        salt_hex, hash_hex = hash_return_secret(secret)
        assert len(salt_hex) == 32  # 16 bytes
        assert len(hash_hex) == 64  # SHA-256 32 bytes

        # Constant-time valid verification
        assert verify_return_secret(secret, salt_hex, hash_hex) is True

        # Incorrect secret rejected
        assert verify_return_secret("wb_wrongsecret", salt_hex, hash_hex) is False
        assert verify_return_secret("", salt_hex, hash_hex) is False

        # Corrupted hash or salt
        assert verify_return_secret(secret, "invalid_hex", hash_hex) is False
        assert verify_return_secret(secret, salt_hex, "invalid_hex") is False


class TestAnonymousIntake:
    def test_submit_report_anonymous_success(
        self, session: Session, test_codec: EncryptedFieldCodec
    ) -> None:
        svc = _setup_service(session, test_codec)
        tenant = _seed_tenant(session)

        portal = WhistleblowerPortal(
            id=uuid4(),
            tenant_id=tenant.id,
            slug="acme",
            title="Acme Whistleblower Portal",
            welcome_text="Report in confidence",
            is_active=True,
        )
        session.add(portal)
        session.flush()

        case, secret = svc.submit_report(
            slug="acme",
            category="fraud",
            title="Accounting irregularity",
            summary="Department X is misreporting expenses",
        )

        assert case.id is not None
        assert case.public_case_id.startswith("WB-")
        assert case.status == WhistleblowerCaseStatus.SUBMITTED
        assert secret.startswith("wb_")

        # Invariant 1: Plaintext secret is never stored in DB
        assert case.return_secret_hash != secret
        assert secret not in case.return_secret_hash
        verified = verify_return_secret(secret, case.return_secret_salt, case.return_secret_hash)
        assert verified is True

        # Invariant 2: Report summary is encrypted at application layer
        assert case.encrypted_summary is not None
        assert "ciphertext" in case.encrypted_summary
        assert "misreporting expenses" not in str(case.encrypted_summary)
        assert case.category is None
        assert case.title is None
        assert "fraud" not in str(case.encrypted_category)
        assert "Accounting irregularity" not in str(case.encrypted_title)
        assert svc.decrypt_case_metadata(case) == ("fraud", "Accounting irregularity")

        # Invariant 3: Initial message created with sender REPORTER and encrypted body
        assert len(case.messages) == 1
        msg = case.messages[0]
        assert msg.sender_type == WhistleblowerMessageSender.REPORTER
        assert msg.sent_by_user_id is None
        assert "ciphertext" in msg.encrypted_body

        # Invariant 4: Audit event created without return secrets, plaintext, or IP
        events = list(
            session.scalars(select(AuditEvent).where(AuditEvent.resource_id == str(case.id))).all()
        )
        assert len(events) == 1
        event = events[0]
        assert event.actor_type == AuditActorType.ANONYMOUS_REPORTER
        assert event.actor_id is None
        assert event.action == "whistleblower.case_submitted"
        # Verify no sensitive leakage
        meta = event.safe_metadata or {}
        assert "return_secret" not in meta
        assert "secret" not in meta
        assert "summary" not in meta
        assert "ip" not in meta
        assert "accounting" not in str(meta).lower()
        assert "fraud" not in str(meta).lower()
        assert meta["public_case_id"] == case.public_case_id


def test_anonymous_rate_limiter_bounds_expensive_case_access() -> None:
    limiter = AnonymousWhistleblowerRateLimiter()
    for _ in range(2):
        limiter.check("access", "portal:case", limit=2, now=1.0)
    with pytest.raises(WhistleblowerRateLimitExceeded):
        limiter.check("access", "portal:case", limit=2, now=1.0)
    limiter.check("access", "portal:case", limit=2, now=61.0)

    def test_submit_report_inactive_portal_fails(
        self, session: Session, test_codec: EncryptedFieldCodec
    ) -> None:
        svc = _setup_service(session, test_codec)
        tenant = _seed_tenant(session)

        portal = WhistleblowerPortal(
            id=uuid4(),
            tenant_id=tenant.id,
            slug="disabled-portal",
            title="Disabled",
            welcome_text="Offline",
            is_active=False,
        )
        session.add(portal)
        session.flush()

        with pytest.raises(WhistleblowerPortalNotFoundError):
            svc.submit_report(
                slug="disabled-portal",
                category="safety",
                title="Test",
                summary="Test summary",
            )


class TestAnonymousTrackingAndMessaging:
    def test_access_case_public_and_two_way_messaging(
        self, session: Session, test_codec: EncryptedFieldCodec
    ) -> None:
        svc = _setup_service(session, test_codec)
        tenant = _seed_tenant(session)
        user = _seed_user(session, "compliance@acme.com")
        _seed_membership(session, tenant.id, user.id, Role.COMPLIANCE_MANAGER)
        tenant_ctx = TenantContext(
            tenant_id=tenant.id, user_id=user.id, role=Role.COMPLIANCE_MANAGER
        )

        portal = WhistleblowerPortal(
            id=uuid4(),
            tenant_id=tenant.id,
            slug="acme-ethics",
            title="Ethics Line",
            welcome_text="Welcome",
            is_active=True,
        )
        session.add(portal)
        session.flush()

        # Step 1: Reporter submits report
        case, secret = svc.submit_report(
            slug="acme-ethics",
            category="bribery",
            title="Kickback scheme",
            summary="Vendor payments without POs",
        )

        # Step 2: Reporter accesses case with valid credentials
        fetched_case, messages = svc.access_case_public(
            slug="acme-ethics",
            public_case_id=case.public_case_id,
            return_secret=secret,
        )
        assert fetched_case.id == case.id
        assert len(messages) == 1
        assert messages[0]["body"] == "Vendor payments without POs"
        assert messages[0]["sender_type"] == "reporter"

        # Step 3: Reporter access with invalid secret fails
        with pytest.raises(WhistleblowerUnauthorizedError):
            svc.access_case_public(
                slug="acme-ethics",
                public_case_id=case.public_case_id,
                return_secret="wb_invalid_secret_token",
            )

        # Step 4: Reporter adds follow-up message
        reply_msg = svc.add_reporter_message(
            slug="acme-ethics",
            public_case_id=case.public_case_id,
            return_secret=secret,
            body="Here is additional information: invoice numbers 101 and 102",
        )
        assert reply_msg.sender_type == WhistleblowerMessageSender.REPORTER

        # Step 5: Handler responds to case
        handler_msg = svc.add_handler_message(
            tenant_context=tenant_ctx,
            case_id=case.id,
            body="Thank you. We have initiated an internal review.",
        )
        assert handler_msg.sender_type == WhistleblowerMessageSender.HANDLER
        assert handler_msg.sent_by_user_id == user.id

        # Step 6: Case status automatically transitions from SUBMITTED to ACKNOWLEDGED
        session.refresh(case)
        assert case.status == WhistleblowerCaseStatus.ACKNOWLEDGED

        # Step 7: Reporter retrieves full thread decrypted
        _, updated_messages = svc.access_case_public(
            slug="acme-ethics",
            public_case_id=case.public_case_id,
            return_secret=secret,
        )
        assert len(updated_messages) == 3
        assert updated_messages[0]["body"] == "Vendor payments without POs"
        assert (
            updated_messages[1]["body"]
            == "Here is additional information: invoice numbers 101 and 102"
        )
        assert updated_messages[2]["body"] == "Thank you. We have initiated an internal review."

    def test_messaging_closed_case_rejected(
        self, session: Session, test_codec: EncryptedFieldCodec
    ) -> None:
        svc = _setup_service(session, test_codec)
        tenant = _seed_tenant(session)
        user = _seed_user(session, "officer@acme.com")
        _seed_membership(session, tenant.id, user.id, Role.COMPLIANCE_MANAGER)
        tenant_ctx = TenantContext(
            tenant_id=tenant.id, user_id=user.id, role=Role.COMPLIANCE_MANAGER
        )

        portal = WhistleblowerPortal(
            id=uuid4(),
            tenant_id=tenant.id,
            slug="closed-test",
            title="Closed Test",
            welcome_text="Welcome",
            is_active=True,
        )
        session.add(portal)
        session.flush()

        case, secret = svc.submit_report(
            slug="closed-test",
            category="other",
            title="Test Case",
            summary="Dismiss this case",
        )

        # Handler dismisses the case
        svc.update_case_status(
            tenant_context=tenant_ctx,
            case_id=case.id,
            new_status=WhistleblowerCaseStatus.DISMISSED,
            closed_reason="Insufficient actionable details",
        )

        # Reporter messaging on closed case rejected
        with pytest.raises(WhistleblowerClosedCaseError):
            svc.add_reporter_message(
                slug="closed-test",
                public_case_id=case.public_case_id,
                return_secret=secret,
                body="Wait, I have more info",
            )

        # Handler messaging on closed case rejected
        with pytest.raises(WhistleblowerClosedCaseError):
            svc.add_handler_message(
                tenant_context=tenant_ctx,
                case_id=case.id,
                body="Cannot send on closed case",
            )


class TestPortalManagement:
    def test_setup_and_update_portal(
        self, session: Session, test_codec: EncryptedFieldCodec
    ) -> None:
        svc = _setup_service(session, test_codec)
        tenant = _seed_tenant(session)
        user = _seed_user(session)
        tenant_ctx = TenantContext(tenant_id=tenant.id, user_id=user.id, role=Role.ADMINISTRATOR)

        # Initial setup
        portal = svc.setup_or_update_portal(
            tenant_context=tenant_ctx,
            slug="acme-secure",
            title="Acme Secure Line",
            welcome_text="Submit anonymously here.",
            is_active=True,
        )
        assert portal.slug == "acme-secure"
        assert portal.version == 1

        # Update portal
        updated = svc.setup_or_update_portal(
            tenant_context=tenant_ctx,
            slug="acme-secure",
            title="Acme Whistleblower Channel",
            welcome_text="Updated welcome text.",
            is_active=True,
            expected_version=1,
        )
        assert updated.title == "Acme Whistleblower Channel"
        assert updated.version == 2

        # Optimistic concurrency conflict on stale version
        with pytest.raises(WhistleblowerConcurrencyConflictError):
            svc.setup_or_update_portal(
                tenant_context=tenant_ctx,
                slug="acme-secure",
                title="Stale Update",
                welcome_text="Text",
                is_active=True,
                expected_version=1,
            )

    def test_portal_slug_collision_across_tenants_rejected(
        self, session: Session, test_codec: EncryptedFieldCodec
    ) -> None:
        svc = _setup_service(session, test_codec)
        t1 = _seed_tenant(session, "Tenant One")
        t2 = _seed_tenant(session, "Tenant Two")
        u1 = _seed_user(session, "u1@one.com")
        u2 = _seed_user(session, "u2@two.com")

        ctx1 = TenantContext(tenant_id=t1.id, user_id=u1.id, role=Role.ADMINISTRATOR)
        ctx2 = TenantContext(tenant_id=t2.id, user_id=u2.id, role=Role.ADMINISTRATOR)

        # Tenant 1 takes slug "whistleblower"
        svc.setup_or_update_portal(
            tenant_context=ctx1,
            slug="whistleblower",
            title="T1 Portal",
            welcome_text="W1",
            is_active=True,
        )

        # Tenant 2 attempting to claim "whistleblower" raises conflict
        with pytest.raises(WhistleblowerSlugConflictError):
            svc.setup_or_update_portal(
                tenant_context=ctx2,
                slug="whistleblower",
                title="T2 Portal",
                welcome_text="W2",
                is_active=True,
            )


class TestHandlerCaseManagement:
    def test_list_and_isolate_tenant_cases(
        self, session: Session, test_codec: EncryptedFieldCodec
    ) -> None:
        svc = _setup_service(session, test_codec)
        t1 = _seed_tenant(session, "Tenant 1")
        t2 = _seed_tenant(session, "Tenant 2")
        u1 = _seed_user(session, "u1@t1.com")
        u2 = _seed_user(session, "u2@t2.com")
        ctx1 = TenantContext(tenant_id=t1.id, user_id=u1.id, role=Role.COMPLIANCE_MANAGER)
        ctx2 = TenantContext(tenant_id=t2.id, user_id=u2.id, role=Role.COMPLIANCE_MANAGER)

        p1 = svc.setup_or_update_portal(ctx1, "t1-portal", "T1", "W", True)
        p2 = svc.setup_or_update_portal(ctx2, "t2-portal", "T2", "W", True)

        svc.submit_report(p1.slug, "fraud", "T1 Case 1", "Summary 1")
        svc.submit_report(p1.slug, "safety", "T1 Case 2", "Summary 2")
        svc.submit_report(p2.slug, "fraud", "T2 Case 1", "Summary 3")

        # Tenant 1 only sees their 2 cases
        cases_t1, total_t1 = svc.list_cases(ctx1)
        assert total_t1 == 2
        assert len(cases_t1) == 2
        for c in cases_t1:
            assert c.tenant_id == t1.id

        # Tenant 2 only sees their 1 case
        cases_t2, total_t2 = svc.list_cases(ctx2)
        assert total_t2 == 1
        assert len(cases_t2) == 1
        assert cases_t2[0].tenant_id == t2.id

    def test_get_case_detail_handler_decryption(
        self, session: Session, test_codec: EncryptedFieldCodec
    ) -> None:
        svc = _setup_service(session, test_codec)
        tenant = _seed_tenant(session)
        user = _seed_user(session)
        ctx = TenantContext(tenant_id=tenant.id, user_id=user.id, role=Role.COMPLIANCE_MANAGER)

        portal = svc.setup_or_update_portal(ctx, "handler-portal", "Title", "W", True)
        case, _ = svc.submit_report(
            portal.slug, "fraud", "Confidential Report", "Secret allegations here"
        )

        retrieved_case, summary, messages = svc.get_case(ctx, case.id)
        assert retrieved_case.id == case.id
        assert summary == "Secret allegations here"
        assert len(messages) == 1
        assert messages[0]["body"] == "Secret allegations here"

    def test_cross_tenant_get_case_fails(
        self, session: Session, test_codec: EncryptedFieldCodec
    ) -> None:
        svc = _setup_service(session, test_codec)
        t1 = _seed_tenant(session, "T1")
        t2 = _seed_tenant(session, "T2")
        u1 = _seed_user(session, "u1@t1.com")
        u2 = _seed_user(session, "u2@t2.com")
        ctx1 = TenantContext(tenant_id=t1.id, user_id=u1.id, role=Role.COMPLIANCE_MANAGER)
        ctx2 = TenantContext(tenant_id=t2.id, user_id=u2.id, role=Role.COMPLIANCE_MANAGER)

        p1 = svc.setup_or_update_portal(ctx1, "p1", "Title", "W", True)
        case, _ = svc.submit_report(p1.slug, "fraud", "T1 Case", "Secret")

        # T2 handler trying to access T1 case fails with NotFound
        with pytest.raises(WhistleblowerCaseNotFoundError):
            svc.get_case(ctx2, case.id)

    def test_assign_handler_to_case(
        self, session: Session, test_codec: EncryptedFieldCodec
    ) -> None:
        svc = _setup_service(session, test_codec)
        tenant = _seed_tenant(session)
        lead = _seed_user(session, "lead@acme.com")
        investigator = _seed_user(session, "investigator@acme.com")
        outsider = _seed_user(session, "outsider@other.com")

        _seed_membership(session, tenant.id, lead.id, Role.COMPLIANCE_MANAGER)
        _seed_membership(session, tenant.id, investigator.id, Role.COMPLIANCE_MANAGER)
        ctx = TenantContext(tenant_id=tenant.id, user_id=lead.id, role=Role.COMPLIANCE_MANAGER)

        portal = svc.setup_or_update_portal(ctx, "assign-portal", "Title", "W", True)
        case, _ = svc.submit_report(portal.slug, "safety", "Case", "Summary")

        # Assign active member succeeds
        assignment = svc.assign_handler(ctx, case.id, investigator.id)
        assert assignment.handler_user_id == investigator.id
        assert assignment.assigned_by_user_id == lead.id

        # Assign non-member fails
        with pytest.raises(WhistleblowerInvalidHandlerError):
            svc.assign_handler(ctx, case.id, outsider.id)

    def test_update_case_status_lifecycle(
        self, session: Session, test_codec: EncryptedFieldCodec
    ) -> None:
        svc = _setup_service(session, test_codec)
        tenant = _seed_tenant(session)
        user = _seed_user(session)
        ctx = TenantContext(tenant_id=tenant.id, user_id=user.id, role=Role.COMPLIANCE_MANAGER)

        portal = svc.setup_or_update_portal(ctx, "status-portal", "Title", "W", True)
        case, _ = svc.submit_report(portal.slug, "fraud", "Case", "Summary")

        # SUBMITTED -> UNDER_INVESTIGATION
        svc.update_case_status(ctx, case.id, WhistleblowerCaseStatus.UNDER_INVESTIGATION)
        session.refresh(case)
        assert case.status == WhistleblowerCaseStatus.UNDER_INVESTIGATION

        # UNDER_INVESTIGATION -> RESOLVED
        svc.update_case_status(
            ctx,
            case.id,
            WhistleblowerCaseStatus.RESOLVED,
            closed_reason="Corrective actions taken",
        )
        session.refresh(case)
        assert case.status == WhistleblowerCaseStatus.RESOLVED  # type: ignore[comparison-overlap]
        assert case.closed_at is not None
        assert case.closed_reason == "Corrective actions taken"

        # RESOLVED is terminal; cannot transition to ACKNOWLEDGED
        with pytest.raises(WhistleblowerInvalidTransitionError):
            svc.update_case_status(ctx, case.id, WhistleblowerCaseStatus.ACKNOWLEDGED)
