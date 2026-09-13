from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LegalEntity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A registered legal corporation or entity belonging to a tenant."""

    __tablename__ = "legal_entities"
    __table_args__ = (Index("ix_legal_entities_tenant_id", "tenant_id"),)

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="DE", nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    business_units: Mapped[list["BusinessUnit"]] = relationship(
        back_populates="legal_entity", cascade="all, delete-orphan"
    )
    locations: Mapped[list["Location"]] = relationship(
        back_populates="legal_entity", cascade="all, delete-orphan"
    )


class BusinessUnit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An organizational division, department, or business unit within a legal entity."""

    __tablename__ = "business_units"
    __table_args__ = (
        Index("ix_business_units_tenant_id", "tenant_id"),
        Index("ix_business_units_legal_entity_id", "legal_entity_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    legal_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("legal_entities.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    legal_entity: Mapped[LegalEntity] = relationship(back_populates="business_units")


class Location(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A physical office, data center, or operational facility."""

    __tablename__ = "locations"
    __table_args__ = (
        Index("ix_locations_tenant_id", "tenant_id"),
        Index("ix_locations_legal_entity_id", "legal_entity_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    legal_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("legal_entities.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(2), default="DE", nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)

    legal_entity: Mapped[LegalEntity] = relationship(back_populates="locations")
