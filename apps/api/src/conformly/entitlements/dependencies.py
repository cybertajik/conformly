from datetime import UTC, datetime
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentTenant
from conformly.db.session import get_db
from conformly.entitlements.service import get_or_create_tenant_entitlement


def require_module(module_name: str) -> Callable[..., None]:
    """Dependency factory ensuring a module is enabled and active in the tenant entitlement."""

    def _dependency(
        tenant_context: CurrentTenant,
        database: Annotated[Session, Depends(get_db)],
    ) -> None:
        entitlement = get_or_create_tenant_entitlement(database, tenant_context.tenant_id)
        now = datetime.now(UTC)
        if entitlement.effective_from:
            eff_from = (
                entitlement.effective_from
                if entitlement.effective_from.tzinfo
                else entitlement.effective_from.replace(tzinfo=UTC)
            )
            if now < eff_from:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tenant entitlement is not yet active",
                )
        if entitlement.effective_until:
            eff_until = (
                entitlement.effective_until
                if entitlement.effective_until.tzinfo
                else entitlement.effective_until.replace(tzinfo=UTC)
            )
            if now > eff_until:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tenant entitlement has expired",
                )
        if module_name not in entitlement.enabled_modules:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Module '{module_name}' is not enabled for this tenant",
            )

    return _dependency
