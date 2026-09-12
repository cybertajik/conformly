"""Public profile & compliance trust center models.

Public profiles are projection entities specifically designed to expose only
explicitly approved compliance data without path to internal entities.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from conformly.db.base import Base


class PublicCredentialType(StrEnum):
    """Class of public compliance credential."""

    CONFORMLY_READINESS = "conformly_readiness"
    THIRD_PARTY = "third_party"


class PublicCredentialStatus(StrEnum):
    """Lifecycle status of a public compliance credential."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")


def is_valid_profile_slug(slug: str) -> bool:
    """Validate public profile URL slug."""
    return bool(SLUG_PATTERN.match(slug.lower()))


class PublicProfile(Base):
    """Explicit public profile projection for a tenant.

    Only published profiles (is_published=True) are visible to unauthenticated users.
    """

    __tablename__ = "public_profiles"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    primary_contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    credentials: Mapped[list[PublicCredential]] = relationship(
        "PublicCredential",
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="PublicCredential.display_order",
    )
    statements: Mapped[list[PublicStatement]] = relationship(
        "PublicStatement",
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="PublicStatement.display_order",
    )


class PublicCredential(Base):
    """Public credential or badge displayed on a public compliance profile."""

    __tablename__ = "public_credentials"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("public_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    credential_type: Mapped[PublicCredentialType] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_description: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[PublicCredentialStatus] = mapped_column(
        String(32),
        default=PublicCredentialStatus.ACTIVE,
        nullable=False,
    )
    verification_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_certificate_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("pre_audit_certificates.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_publicly_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    profile: Mapped[PublicProfile] = relationship("PublicProfile", back_populates="credentials")


class PublicStatement(Base):
    """Public compliance statement or pledge on the trust center profile."""

    __tablename__ = "public_statements"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("public_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    statement_content: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_publicly_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    profile: Mapped[PublicProfile] = relationship("PublicProfile", back_populates="statements")
