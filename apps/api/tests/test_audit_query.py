from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.query import InvalidAuditCursorError, export_audit_events, search_audit_events
from conformly.audit.service import record_audit_event
from conformly.authz.policy import AuthorizationDeniedError, Principal, TenantContext
from conformly.authz.roles import Role


def context(role: Role = Role.AUDITOR) -> tuple[Principal, TenantContext]:
    user_id = uuid4()
    tenant_id = uuid4()
    return Principal(user_id=user_id), TenantContext(
        tenant_id=tenant_id, user_id=user_id, role=role
    )


def add_event(session: Session, tenant_id: UUID, *, action: str, occurred_at: datetime) -> None:
    record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=uuid4(),
        action=action,
        resource_type="membership",
        resource_id=str(uuid4()),
        request_id=str(uuid4()),
        outcome=AuditOutcome.SUCCESS,
        occurred_at=occurred_at,
    )


def test_search_is_tenant_scoped_filtered_and_cursor_paginated(session: Session) -> None:
    principal, tenant = context()
    now = datetime.now(UTC) + timedelta(minutes=5)
    add_event(session, tenant.tenant_id, action="membership.first", occurred_at=now)
    add_event(
        session,
        tenant.tenant_id,
        action="membership.second",
        occurred_at=now - timedelta(seconds=1),
    )
    add_event(session, uuid4(), action="other-tenant", occurred_at=now)

    first = search_audit_events(session, principal, tenant, request_id="search-first", limit=1)
    second = search_audit_events(
        session,
        principal,
        tenant,
        request_id="search-second",
        limit=1,
        cursor=first.next_cursor,
    )

    assert [event.action for event in first.records] == ["membership.first"]
    assert first.next_cursor is not None
    assert [event.action for event in second.records] == ["membership.second"]
    assert all(event.tenant_id == tenant.tenant_id for event in first.records + second.records)


def test_invalid_cursor_fails_closed(session: Session) -> None:
    principal, tenant = context()
    with pytest.raises(InvalidAuditCursorError):
        search_audit_events(
            session, principal, tenant, request_id="bad-cursor", cursor="not-a-cursor"
        )


def test_viewer_cannot_search_and_auditor_cannot_export(session: Session) -> None:
    viewer, viewer_context = context(Role.VIEWER)
    with pytest.raises(AuthorizationDeniedError):
        search_audit_events(session, viewer, viewer_context, request_id="viewer-search")

    auditor, auditor_context = context(Role.AUDITOR)
    with pytest.raises(AuthorizationDeniedError):
        export_audit_events(session, auditor, auditor_context, request_id="auditor-export")


def test_compliance_manager_can_export_only_selected_tenant(session: Session) -> None:
    principal, tenant = context(Role.COMPLIANCE_MANAGER)
    add_event(session, tenant.tenant_id, action="included", occurred_at=datetime.now(UTC))
    add_event(session, uuid4(), action="excluded", occurred_at=datetime.now(UTC))

    records = export_audit_events(session, principal, tenant, request_id="manager-export")

    assert [event.action for event in records] == ["included"]
