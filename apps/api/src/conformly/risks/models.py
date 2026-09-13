from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RiskCategory(StrEnum):
    GOVERNANCE = "governance"
    OPERATIONAL = "operational"
    TECHNICAL = "technical"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    THIRD_PARTY = "third_party"
    FINANCIAL = "financial"


class RiskStatus(StrEnum):
    IDENTIFIED = "identified"
    ASSESSED = "assessed"
    TREATING = "treating"
    MONITORED = "monitored"
    CLOSED = "closed"


class RiskTreatmentStrategy(StrEnum):
    MITIGATE = "mitigate"
    ACCEPT = "accept"
    TRANSFER = "transfer"
    AVOID = "avoid"


class Risk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A compliance or operational risk registered by a tenant."""

    __tablename__ = "risks"
    __table_args__ = (
        Index("ix_risks_tenant_id", "tenant_id"),
        Index("ix_risks_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[RiskCategory] = mapped_column(
        Enum(RiskCategory, native_enum=False, length=32),
        default=RiskCategory.SECURITY,
        nullable=False,
    )
    likelihood: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    impact: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    inherent_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-25
    residual_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-25
    status: Mapped[RiskStatus] = mapped_column(
        Enum(RiskStatus, native_enum=False, length=32),
        default=RiskStatus.IDENTIFIED,
        nullable=False,
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    control_id: Mapped[UUID | None] = mapped_column(nullable=True)
    finding_id: Mapped[UUID | None] = mapped_column(nullable=True)
    legal_entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("legal_entities.id", ondelete="SET NULL"), nullable=True
    )
    business_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    treatments: Mapped[list["RiskTreatment"]] = relationship(
        back_populates="risk", cascade="all, delete-orphan"
    )


class RiskTreatment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A planned or active risk treatment action."""

    __tablename__ = "risk_treatments"
    __table_args__ = (
        Index("ix_risk_treatments_tenant_id", "tenant_id"),
        Index("ix_risk_treatments_risk_id", "risk_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    risk_id: Mapped[UUID] = mapped_column(
        ForeignKey("risks.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    strategy: Mapped[RiskTreatmentStrategy] = mapped_column(
        Enum(RiskTreatmentStrategy, native_enum=False, length=32),
        default=RiskTreatmentStrategy.MITIGATE,
        nullable=False,
    )
    treatment_plan: Mapped[str] = mapped_column(Text, nullable=False)
    target_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="planned", nullable=False)

    risk: Mapped[Risk] = relationship(back_populates="treatments")
