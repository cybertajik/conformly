from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.auth.dependencies import CurrentPrincipal
from conformly.authz.roles import Role
from conformly.db.session import get_db
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus
from conformly.tenancy.rls import set_user_rls_context

router = APIRouter(prefix="/v1/me", tags=["identity"])


class MyTenantResponse(BaseModel):
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    role: Role


@router.get("/tenants", response_model=list[MyTenantResponse])
def list_my_tenants(
    request: Request,
    principal: CurrentPrincipal,
    database: Annotated[Session, Depends(get_db)],
) -> list[MyTenantResponse]:
    set_user_rls_context(database, user_id=principal.user_id)
    memberships = database.scalars(
        select(Membership)
        .join(Membership.tenant)
        .where(
            Membership.user_id == principal.user_id,
            Membership.status == MembershipStatus.ACTIVE,
            Tenant.status == TenantStatus.ACTIVE,
        )
        .order_by(Tenant.name, Tenant.id)
    ).all()
    record_audit_event(
        database,
        tenant_id=None,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="tenant.memberships_discover",
        resource_type="tenant_membership",
        resource_id=None,
        request_id=request.state.request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"record_count": len(memberships)},
    )
    return [
        MyTenantResponse(
            tenant_id=membership.tenant_id,
            tenant_name=membership.tenant.name,
            tenant_slug=membership.tenant.slug,
            role=membership.role,
        )
        for membership in memberships
    ]
