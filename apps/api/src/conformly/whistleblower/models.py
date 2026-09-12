from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WhistleblowerCaseStatus(StrEnum):
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    UNDER_INVESTIGATION = "under_investigation"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


WHISTLEBLOWER_CASE_TRANSITIONS: dict[
    WhistleblowerCaseStatus, frozenset[WhistleblowerCaseStatus]
] = {
    WhistleblowerCaseStatus.SUBMITTED: frozenset(
        {
            WhistleblowerCaseStatus.ACKNOWLEDGED,
            WhistleblowerCaseStatus.UNDER_INVESTIGATION,
            WhistleblowerCaseStatus.DISMISSED,
        }
    ),
    WhistleblowerCaseStatus.ACKNOWLEDGED: frozenset(
        {
            WhistleblowerCaseStatus.UNDER_INVESTIGATION,
            WhistleblowerCaseStatus.RESOLVED,
            WhistleblowerCaseStatus.DISMISSED,
        }
    ),
    WhistleblowerCaseStatus.UNDER_INVESTIGATION: frozenset(
        {
            WhistleblowerCaseStatus.RESOLVED,
            WhistleblowerCaseStatus.DISMISSED,
        }
    ),
    WhistleblowerCaseStatus.RESOLVED: frozenset(),
    WhistleblowerCaseStatus.DISMISSED: frozenset(),
}


class WhistleblowerMessageSender(StrEnum):
    REPORTER = "reporter"
    HANDLER = "handler"


class WhistleblowerPortal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tenant-specific public whistleblower intake configuration."""

    __tablename__ = "whistleblower_portals"

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    welcome_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    cases: Mapped[list["WhistleblowerCase"]] = relationship(
        "WhistleblowerCase",
        back_populates="portal",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_whistleblower_portals_tenant_active", "tenant_id", "is_active"),)


class WhistleblowerCase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Whistleblower case record preserving strict anonymous reporter boundaries."""

    __tablename__ = "whistleblower_cases"

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    portal_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("whistleblower_portals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    public_case_id: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
    )
    return_secret_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    return_secret_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[WhistleblowerCaseStatus] = mapped_column(
        Enum(WhistleblowerCaseStatus, native_enum=False, length=32),
        default=WhistleblowerCaseStatus.SUBMITTED,
        nullable=False,
        index=True,
    )
    # Nullable legacy columns support a controlled encrypted-data migration only.
    # New writes never place reporter-supplied metadata in these columns.
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encrypted_category: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    encrypted_title: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    encrypted_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    portal: Mapped["WhistleblowerPortal"] = relationship(
        "WhistleblowerPortal", back_populates="cases"
    )
    messages: Mapped[list["WhistleblowerMessage"]] = relationship(
        "WhistleblowerMessage",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="WhistleblowerMessage.created_at",
    )
    attachments: Mapped[list["WhistleblowerAttachment"]] = relationship(
        "WhistleblowerAttachment",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list["WhistleblowerCaseAssignment"]] = relationship(
        "WhistleblowerCaseAssignment",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_whistleblower_cases_tenant_status", "tenant_id", "status"),
        Index("ix_whistleblower_cases_tenant_created", "tenant_id", "created_at"),
    )


class WhistleblowerMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Two-way message thread item between anonymous reporter and authorized handler."""

    __tablename__ = "whistleblower_messages"

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("whistleblower_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_type: Mapped[WhistleblowerMessageSender] = mapped_column(
        Enum(WhistleblowerMessageSender, native_enum=False, length=32),
        nullable=False,
    )
    encrypted_body: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    sent_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    case: Mapped["WhistleblowerCase"] = relationship("WhistleblowerCase", back_populates="messages")
    attachments: Mapped[list["WhistleblowerAttachment"]] = relationship(
        "WhistleblowerAttachment",
        back_populates="message",
    )

    __table_args__ = (Index("ix_whistleblower_messages_case_created", "case_id", "created_at"),)


class WhistleblowerAttachment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Encrypted file attachment linked to a whistleblower case or message."""

    __tablename__ = "whistleblower_attachments"

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("whistleblower_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("whistleblower_messages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    file_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("stored_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[WhistleblowerMessageSender] = mapped_column(
        Enum(WhistleblowerMessageSender, native_enum=False, length=32),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)

    case: Mapped["WhistleblowerCase"] = relationship(
        "WhistleblowerCase", back_populates="attachments"
    )
    message: Mapped["WhistleblowerMessage | None"] = relationship(
        "WhistleblowerMessage", back_populates="attachments"
    )


class WhistleblowerCaseAssignment(Base, UUIDPrimaryKeyMixin):
    """Assignment of an authorized internal handler to a whistleblower case."""

    __tablename__ = "whistleblower_case_assignments"

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("whistleblower_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    handler_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_by_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    case: Mapped["WhistleblowerCase"] = relationship(
        "WhistleblowerCase", back_populates="assignments"
    )

    __table_args__ = (
        Index("ix_whistleblower_assignments_case_handler", "case_id", "handler_user_id"),
    )
