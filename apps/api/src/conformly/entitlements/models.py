from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from conformly.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

DEFAULT_TIER_A_MODULES = [
    "frameworks",
    "evidence",
    "policies",
    "tasks",
    "findings",
    "preaudit",
    "profiles",
    "risks",
    "assets",
    "vendors",
    "organization",
    "audit",
]


class TenantEntitlement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Data-driven activation, feature limits, and framework-pack permissions for a tenant."""

    __tablename__ = "tenant_entitlements"
    __table_args__ = (Index("ix_tenant_entitlements_tenant_id", "tenant_id", unique=True),)

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    plan_code: Mapped[str] = mapped_column(String(50), default="tier_a", nullable=False)
    enabled_modules: Mapped[list[str]] = mapped_column(
        JSON, default=DEFAULT_TIER_A_MODULES, nullable=False
    )
    max_members: Mapped[int] = mapped_column(default=100, nullable=False)
    max_storage_bytes: Mapped[int] = mapped_column(
        BigInteger, default=10 * 1024 * 1024 * 1024, nullable=False
    )  # 10 GB
    allowed_framework_slugs: Mapped[list[str]] = mapped_column(
        JSON, default=lambda: list(["*"]), nullable=False
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
