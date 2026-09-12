from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from conformly.auth.dependencies import CurrentPrincipal, CurrentTenant
from conformly.dashboard import service
from conformly.dashboard.service import DashboardSummary
from conformly.db.session import get_db

router = APIRouter(prefix="/v1/tenants/{tenant_id}/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary_endpoint(
    request: Request,
    principal: CurrentPrincipal,
    tenant_context: CurrentTenant,
    database: Annotated[Session, Depends(get_db)],
) -> DashboardSummary:
    """Return executive readiness scores, expiring items, open tasks, risks, and audit feed."""
    request_id = getattr(request.state, "request_id", "req-dashboard-summary")
    return service.get_dashboard_summary(database, principal, tenant_context, request_id)
