from typing import TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

TenantModel = TypeVar("TenantModel")


class TenantScopedRepository[TenantModel]:
    """Base requiring tenant context for every repository instance."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    @property
    def tenant_id(self) -> UUID:
        return self._tenant_id
