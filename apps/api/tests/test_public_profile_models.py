"""Unit tests for Public Profile domain models and validation."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from conformly.db.base import Base
from conformly.identity.models import Tenant, TenantStatus
from conformly.preaudit.models import PreAuditCertificate  # noqa: F401
from conformly.profiles.models import (
    PublicCredential,
    PublicCredentialStatus,
    PublicCredentialType,
    PublicProfile,
    PublicStatement,
    is_valid_profile_slug,
)


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


def _create_tenant(session: Session) -> Tenant:
    tenant = Tenant(
        id=uuid4(),
        name="Acme Security",
        slug=f"acme-{uuid4().hex[:6]}",
        status=TenantStatus.ACTIVE,
    )
    session.add(tenant)
    session.flush()
    return tenant


class TestSlugValidation:
    def test_valid_slugs(self) -> None:
        assert is_valid_profile_slug("acme") is True
        assert is_valid_profile_slug("acme-corp") is True
        assert is_valid_profile_slug("trust-center-2026") is True
        assert is_valid_profile_slug("sec-ops-123") is True

    def test_invalid_slugs(self) -> None:
        assert is_valid_profile_slug("a") is False  # too short
        assert is_valid_profile_slug("-acme") is False  # starts with hyphen
        assert is_valid_profile_slug("acme-") is False  # ends with hyphen
        assert is_valid_profile_slug("Acme_Corp") is False  # uppercase / underscore
        assert is_valid_profile_slug("acme.corp") is False  # dot
        assert is_valid_profile_slug("a" * 65) is False  # too long


class TestPublicProfileModel:
    def test_create_public_profile(self, session: Session) -> None:
        tenant = _create_tenant(session)
        profile = PublicProfile(
            id=uuid4(),
            tenant_id=tenant.id,
            slug="acme-trust",
            display_name="Acme Corporation",
            description="Verified trust & security compliance posture.",
            website_url="https://acme.example.com",
            primary_contact_email="security@acme.example.com",
            is_published=False,
            version=1,
        )
        session.add(profile)
        session.flush()

        assert profile.id is not None
        assert profile.slug == "acme-trust"
        assert profile.is_published is False
        assert profile.version == 1
        assert profile.created_at is not None

    def test_credentials_and_statements_relationship(self, session: Session) -> None:
        tenant = _create_tenant(session)
        profile = PublicProfile(
            id=uuid4(),
            tenant_id=tenant.id,
            slug="acme-compliance",
            display_name="Acme",
            is_published=True,
            version=1,
        )
        session.add(profile)
        session.flush()

        now = datetime.now(UTC)
        cred = PublicCredential(
            id=uuid4(),
            profile_id=profile.id,
            tenant_id=tenant.id,
            credential_type=PublicCredentialType.THIRD_PARTY,
            title="ISO/IEC 27001:2022",
            issuer_name="BSI Group",
            scope_description="Information Security Management System",
            issued_at=now - timedelta(days=30),
            valid_until=now + timedelta(days=335),
            status=PublicCredentialStatus.ACTIVE,
            verification_url="https://verify.example.com/cert/123",
            is_publicly_visible=True,
            display_order=0,
        )
        statement = PublicStatement(
            id=uuid4(),
            profile_id=profile.id,
            tenant_id=tenant.id,
            title="Data Residency Pledge",
            statement_content="Customer data is strictly hosted in EU and US regions.",
            display_order=0,
            is_publicly_visible=True,
        )
        session.add_all([cred, statement])
        session.flush()

        session.refresh(profile)
        assert len(profile.credentials) == 1
        assert profile.credentials[0].title == "ISO/IEC 27001:2022"
        assert len(profile.statements) == 1
        assert profile.statements[0].title == "Data Residency Pledge"
