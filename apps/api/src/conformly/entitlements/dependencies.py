from typing import Annotated, Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentTenant
from conformly.db.session import get_db
from conformly.entitlements.service import is_module_enabled


def require_module(module_name: str) -> Callable[..., None]:
    """Dependency factory ensuring a module is enabled in the tenant entitlement."""

    def _dependency(
        tenant_context: CurrentTenant,
        database: Annotated[Session, Depends(get_db)],
    ) -> None:
        if not is_module_enabled(database, tenant_context.tenant_id, module_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Module '{module_name}' is not enabled for this tenant",
            )

    return _dependency
