"""Unit tests for PublicProfileService domain operations."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from conformly.authz.policy import AuthorizationDeniedError, Principal, TenantContext
from conformly.authz.roles import Role
from conformly.db.base import Base
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User
from conformly.preaudit.models import CertificateStatus, PreAuditCertificate
from conformly.profiles.models import (
    PublicCredential,
    PublicCredentialStatus,
    PublicCredentialType,
)
from conformly.profiles.service import (
    PublicCredentialInvalidSourceError,
    PublicProfileInvalidSlugError,
    PublicProfileNotFoundError,
    PublicProfileService,
    PublicProfileSlugConflictError,
)
from conformly.storage.models import StoredFile  # noqa: F401


@pytest.fixture
def session() -> Generator[Session, None, None]:

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _seed_tenant(session: Session, name: str = "Acme Corp") -> Tenant:
    tenant = Tenant(
        id=uuid4(),
        name=name,
        slug=f"acme-{uuid4().hex[:6]}",
        status=TenantStatus.ACTIVE,
    )
    session.add(tenant)
    session.flush()
    return tenant


def _seed_user(session: Session) -> User:
    user = User(
        id=uuid4(),
        oidc_issuer="https://issuer.test",
        oidc_subject=f"sub-{uuid4().hex[:8]}",
        email=f"user-{uuid4().hex[:6]}@example.com",
        display_name="Test User",
    )
    session.add(user)
    session.flush()
    return user


def _seed_context(
    session: Session, tenant_id: UUID, role: Role = Role.COMPLIANCE_MANAGER
) -> tuple[Principal, TenantContext]:
    user = _seed_user(session)
    membership = Membership(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=user.id,
        role=role,
        status=MembershipStatus.ACTIVE,
    )
    session.add(membership)
    session.flush()
    return Principal(user_id=user.id), TenantContext(
        tenant_id=tenant_id, user_id=user.id, role=role
    )


def _seed_certificate(
    session: Session,
    tenant_id: UUID,
    status: CertificateStatus = CertificateStatus.ACTIVE,
) -> PreAuditCertificate:
    cert = PreAuditCertificate(
        id=uuid4(),
        tenant_id=tenant_id,
        pre_audit_id=uuid4(),
        certificate_number=f"CONF-2026-{uuid4().hex[:6].upper()}",
        status=status,
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=365),
    )
    session.add(cert)
    session.flush()
    return cert


class TestPublicProfileLifecycle:
    def test_get_or_create_default_profile(self, session: Session) -> None:
        tenant = _seed_tenant(session, "Delta Labs")
        principal, ctx = _seed_context(session, tenant.id, Role.COMPLIANCE_MANAGER)
        service = PublicProfileService(session)

        profile = service.get_or_create_tenant_profile(tenant.id, principal, ctx)
        assert profile.id is not None
        assert profile.tenant_id == tenant.id
        assert profile.display_name == "Delta Labs"
        assert profile.is_published is False
        assert profile.version == 1

    def test_configure_profile_attributes_and_slug(self, session: Session) -> None:
        tenant = _seed_tenant(session)
        principal, ctx = _seed_context(session, tenant.id, Role.COMPLIANCE_MANAGER)
        service = PublicProfileService(session)

        profile = service.get_or_create_tenant_profile(tenant.id, principal, ctx)
        updated = service.configure_profile(
            tenant_id=tenant.id,
            display_name="Acme Global Security",
            description="Leading security and cloud compliance.",
            logo_url="https://acme.com/logo.png",
            website_url="https://acme.com",
            primary_contact_email="trust@acme.com",
            slug="acme-global",
            expected_version=profile.version,
            principal=principal,
            context=ctx,
        )

        assert updated.slug == "acme-global"
        assert updated.display_name == "Acme Global Security"
        assert updated.version == 2

    def test_configure_profile_slug_conflict(self, session: Session) -> None:
        tenant1 = _seed_tenant(session)
        tenant2 = _seed_tenant(session)
        p1, ctx1 = _seed_context(session, tenant1.id, Role.OWNER)
        p2, ctx2 = _seed_context(session, tenant2.id, Role.OWNER)
        service = PublicProfileService(session)

        prof1 = service.get_or_create_tenant_profile(tenant1.id, p1, ctx1)
        service.configure_profile(
            tenant_id=tenant1.id,
            display_name="Tenant 1",
            description=None,
            logo_url=None,
            website_url=None,
            primary_contact_email=None,
            slug="shared-slug",
            expected_version=prof1.version,
            principal=p1,
            context=ctx1,
        )

        prof2 = service.get_or_create_tenant_profile(tenant2.id, p2, ctx2)
        with pytest.raises(PublicProfileSlugConflictError):
            service.configure_profile(
                tenant_id=tenant2.id,
                display_name="Tenant 2",
                description=None,
                logo_url=None,
                website_url=None,
                primary_contact_email=None,
                slug="shared-slug",
                expected_version=prof2.version,
                principal=p2,
                context=ctx2,
            )

    def test_configure_profile_invalid_slug(self, session: Session) -> None:
        tenant = _seed_tenant(session)
        principal, ctx = _seed_context(session, tenant.id, Role.ADMINISTRATOR)
        service = PublicProfileService(session)

        prof = service.get_or_create_tenant_profile(tenant.id, principal, ctx)
        with pytest.raises(PublicProfileInvalidSlugError):
            service.configure_profile(
                tenant_id=tenant.id,
                display_name="Acme",
                description=None,
                logo_url=None,
                website_url=None,
                primary_contact_email=None,
                slug="bad_slug!",
                expected_version=prof.version,
                principal=principal,
                context=ctx,
            )

    def test_publish_and_unpublish_flow(self, session: Session) -> None:
        tenant = _seed_tenant(session)
        principal, ctx = _seed_context(session, tenant.id, Role.COMPLIANCE_MANAGER)
        service = PublicProfileService(session)

        prof = service.get_or_create_tenant_profile(tenant.id, principal, ctx)
        assert prof.is_published is False

        # Publish
        published = service.publish_profile(tenant.id, prof.version, principal, ctx)
        assert published.is_published is True
        assert published.published_at is not None

        # Verify public projection lookup succeeds
        view, etag = service.get_public_profile_view(published.slug)
        assert view["display_name"] == published.display_name
        assert etag.startswith('"')

        # Unpublish
        unpublished = service.unpublish_profile(tenant.id, published.version, principal, ctx)
        assert unpublished.is_published is False

        # Verify public projection lookup now returns 404
        with pytest.raises(PublicProfileNotFoundError):
            service.get_public_profile_view(published.slug)


class TestPublicProjectionIsolation:
    def test_public_view_filters_non_public_items(self, session: Session) -> None:
        tenant = _seed_tenant(session)
        principal, ctx = _seed_context(session, tenant.id, Role.OWNER)
        service = PublicProfileService(session)

        prof = service.get_or_create_tenant_profile(tenant.id, principal, ctx)
        service.publish_profile(tenant.id, prof.version, principal, ctx)

        # Add visible credential
        service.add_third_party_credential(
            tenant_id=tenant.id,
            title="SOC 2 Type II",
            issuer_name="Schellman",
            scope_description="Cloud Services",
            issued_at=datetime.now(UTC),
            valid_until=datetime.now(UTC) + timedelta(days=180),
            verification_url=None,
            is_publicly_visible=True,
            display_order=0,
            principal=principal,
            context=ctx,
        )

        # Add hidden credential
        service.add_third_party_credential(
            tenant_id=tenant.id,
            title="Internal Draft ISO 27001",
            issuer_name="Internal",
            scope_description="Draft",
            issued_at=datetime.now(UTC),
            valid_until=None,
            verification_url=None,
            is_publicly_visible=False,
            display_order=1,
            principal=principal,
            context=ctx,
        )

        view, _ = service.get_public_profile_view(prof.slug)
        assert len(view["credentials"]) == 1
        assert view["credentials"][0]["title"] == "SOC 2 Type II"
        assert "Internal Draft" not in str(view)


class TestCredentialManagement:
    def test_link_active_preaudit_certificate(self, session: Session) -> None:
        tenant = _seed_tenant(session)
        principal, ctx = _seed_context(session, tenant.id, Role.COMPLIANCE_MANAGER)
        cert = _seed_certificate(session, tenant.id, CertificateStatus.ACTIVE)
        service = PublicProfileService(session)

        cred = service.link_preaudit_credential(
            tenant_id=tenant.id,
            certificate_id=cert.id,
            is_publicly_visible=True,
            display_order=0,
            principal=principal,
            context=ctx,
        )

        assert cred.credential_type == PublicCredentialType.CONFORMLY_READINESS
        assert cred.source_certificate_id == cert.id
        assert "Conformly Pre-Audit Readiness" in cred.title
        assert cred.status == PublicCredentialStatus.ACTIVE

    def test_link_revoked_preaudit_certificate_fails(self, session: Session) -> None:
        tenant = _seed_tenant(session)
        principal, ctx = _seed_context(session, tenant.id, Role.COMPLIANCE_MANAGER)
        cert = _seed_certificate(session, tenant.id, CertificateStatus.REVOKED)
        service = PublicProfileService(session)

        with pytest.raises(PublicCredentialInvalidSourceError):
            service.link_preaudit_credential(
                tenant_id=tenant.id,
                certificate_id=cert.id,
                is_publicly_visible=True,
                display_order=0,
                principal=principal,
                context=ctx,
            )

    def test_revoke_and_delete_credential(self, session: Session) -> None:
        tenant = _seed_tenant(session)
        principal, ctx = _seed_context(session, tenant.id, Role.COMPLIANCE_MANAGER)
        service = PublicProfileService(session)

        cred = service.add_third_party_credential(
            tenant_id=tenant.id,
            title="HIPAA Attestation",
            issuer_name="HealthCert",
            scope_description="PHI Handling",
            issued_at=datetime.now(UTC),
            valid_until=None,
            verification_url=None,
            is_publicly_visible=True,
            display_order=0,
            principal=principal,
            context=ctx,
        )

        # Revoke
        revoked = service.revoke_credential(
            tenant_id=tenant.id,
            credential_id=cred.id,
            reason="Superseded by new audit",
            principal=principal,
            context=ctx,
        )
        assert revoked.status == PublicCredentialStatus.REVOKED

        # Delete
        service.delete_credential(tenant.id, cred.id, principal, ctx)
        deleted = session.scalar(select(PublicCredential).where(PublicCredential.id == cred.id))
        assert deleted is None


class TestRoleAuthorization:
    def test_viewer_denied_management(self, session: Session) -> None:
        tenant = _seed_tenant(session)
        p_viewer, ctx_viewer = _seed_context(session, tenant.id, Role.VIEWER)
        service = PublicProfileService(session)

        prof = service.get_or_create_tenant_profile(tenant.id, p_viewer, ctx_viewer)

        with pytest.raises(AuthorizationDeniedError):
            service.publish_profile(tenant.id, prof.version, p_viewer, ctx_viewer)

        with pytest.raises(AuthorizationDeniedError):
            service.add_third_party_credential(
                tenant_id=tenant.id,
                title="SOC 2",
                issuer_name="Auditor",
                scope_description="Scope",
                issued_at=datetime.now(UTC),
                valid_until=None,
                verification_url=None,
                is_publicly_visible=True,
                display_order=0,
                principal=p_viewer,
                context=ctx_viewer,
            )
