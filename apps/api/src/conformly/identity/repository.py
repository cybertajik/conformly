from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from conformly.identity.models import Membership
from conformly.tenancy.repository import TenantScopedRepository


class MembershipRepository(TenantScopedRepository[Membership]):
    def __init__(self, session: Session, tenant_id: UUID) -> None:
        super().__init__(session, tenant_id)

    def list_memberships(self) -> list[Membership]:
        """List memberships with an unavoidable tenant predicate."""

        statement = (
            select(Membership)
            .options(joinedload(Membership.user))
            .where(Membership.tenant_id == self.tenant_id)
            .order_by(Membership.created_at, Membership.id)
        )
        return list(self._session.scalars(statement).unique())

    def get_membership(self, membership_id: UUID) -> Membership | None:
        return self._session.scalar(
            select(Membership)
            .options(joinedload(Membership.user))
            .where(
                Membership.tenant_id == self.tenant_id,
                Membership.id == membership_id,
            )
        )

    def count_active_role(self, role: object, status: object) -> int:
        count = self._session.scalar(
            select(func.count(Membership.id)).where(
                Membership.tenant_id == self.tenant_id,
                Membership.role == role,
                Membership.status == status,
            )
        )
        return int(count or 0)
