import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditEvent, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.roles import Role
from conformly.identity.models import Membership, MembershipStatus, Tenant, User
from conformly.tenancy.rls import set_rls_context, set_user_rls_context


def test_postgresql_membership_rls_enforces_discovery_and_selected_tenant() -> None:
    database_url = os.getenv("CONFORMLY_TEST_APP_DATABASE_URL")
    if not database_url:
        pytest.skip("PostgreSQL app-role integration URL is not configured")

    engine = create_engine(database_url)
    with engine.connect() as connection, connection.begin() as transaction:
        session = Session(bind=connection)
        first_user = User(
            oidc_issuer="https://rls.example.test",
            oidc_subject=str(uuid4()),
            email=f"{uuid4()}@example.test",
            display_name="First User",
        )
        second_user = User(
            oidc_issuer="https://rls.example.test",
            oidc_subject=str(uuid4()),
            email=f"{uuid4()}@example.test",
            display_name="Second User",
        )
        first_tenant = Tenant(name="First RLS Tenant", slug=f"rls-first-{uuid4()}")
        second_tenant = Tenant(name="Second RLS Tenant", slug=f"rls-second-{uuid4()}")
        session.add_all([first_user, second_user, first_tenant, second_tenant])
        session.flush()

        set_rls_context(
            session,
            user_id=first_user.id,
            tenant_id=first_tenant.id,
            tenant_verified=True,
        )
        session.add_all(
            [
                Membership(
                    tenant_id=first_tenant.id,
                    user_id=first_user.id,
                    role=Role.OWNER,
                    status=MembershipStatus.ACTIVE,
                ),
                Membership(
                    tenant_id=first_tenant.id,
                    user_id=second_user.id,
                    role=Role.VIEWER,
                    status=MembershipStatus.ACTIVE,
                ),
            ]
        )
        session.flush()
        set_rls_context(
            session,
            user_id=first_user.id,
            tenant_id=second_tenant.id,
            tenant_verified=True,
        )
        session.add(
            Membership(
                tenant_id=second_tenant.id,
                user_id=first_user.id,
                role=Role.AUDITOR,
                status=MembershipStatus.ACTIVE,
            )
        )
        session.flush()

        set_user_rls_context(session, user_id=first_user.id)
        discovered = session.scalars(select(Membership)).all()
        assert {membership.tenant_id for membership in discovered} == {
            first_tenant.id,
            second_tenant.id,
        }
        assert {membership.user_id for membership in discovered} == {first_user.id}

        set_rls_context(
            session,
            user_id=first_user.id,
            tenant_id=first_tenant.id,
            tenant_verified=True,
        )
        selected = session.scalars(select(Membership)).all()
        assert {membership.tenant_id for membership in selected} == {first_tenant.id}
        assert {membership.user_id for membership in selected} == {
            first_user.id,
            second_user.id,
        }

        record_audit_event(
            session,
            tenant_id=first_tenant.id,
            actor_type=AuditActorType.USER,
            actor_id=first_user.id,
            action="rls.first_tenant",
            resource_type="rls_test",
            resource_id=None,
            request_id="rls-first",
            outcome=AuditOutcome.SUCCESS,
        )
        set_rls_context(
            session,
            user_id=first_user.id,
            tenant_id=second_tenant.id,
            tenant_verified=True,
        )
        record_audit_event(
            session,
            tenant_id=second_tenant.id,
            actor_type=AuditActorType.USER,
            actor_id=first_user.id,
            action="rls.second_tenant",
            resource_type="rls_test",
            resource_id=None,
            request_id="rls-second",
            outcome=AuditOutcome.SUCCESS,
        )
        set_rls_context(
            session,
            user_id=first_user.id,
            tenant_id=first_tenant.id,
            tenant_verified=True,
        )
        visible_audits = session.scalars(select(AuditEvent)).all()
        assert [event.action for event in visible_audits] == ["rls.first_tenant"]
        session.close()
        transaction.rollback()


def test_postgresql_framework_evidence_requests_rls_enforces_tenant_isolation() -> None:
    """PostgreSQL RLS policy framework_requests_tenant strictly isolates framework_evidence_requests across tenants."""
    database_url = os.getenv("CONFORMLY_TEST_APP_DATABASE_URL")
    if not database_url:
        pytest.skip("PostgreSQL app-role integration URL is not configured")

    from conformly.frameworks.workflow import FrameworkEvidenceRequest

    engine = create_engine(database_url)
    with engine.connect() as connection, connection.begin() as transaction:
        session = Session(bind=connection)
        user_1 = User(
            oidc_issuer="https://rls.example.test",
            oidc_subject=str(uuid4()),
            email=f"{uuid4()}@example.test",
            display_name="User 1",
        )
        user_2 = User(
            oidc_issuer="https://rls.example.test",
            oidc_subject=str(uuid4()),
            email=f"{uuid4()}@example.test",
            display_name="User 2",
        )
        tenant_1 = Tenant(name="Tenant 1 RLS", slug=f"t1-rls-{uuid4().hex[:8]}")
        tenant_2 = Tenant(name="Tenant 2 RLS", slug=f"t2-rls-{uuid4().hex[:8]}")
        session.add_all([user_1, user_2, tenant_1, tenant_2])
        session.flush()

        set_rls_context(session, user_id=user_1.id, tenant_id=tenant_1.id, tenant_verified=True)

        req_1 = FrameworkEvidenceRequest(
            tenant_id=tenant_1.id,
            adoption_id=uuid4(),
            specification_id=uuid4(),
            task_id=uuid4(),
        )
        session.add(req_1)
        session.flush()

        set_rls_context(session, user_id=user_2.id, tenant_id=tenant_2.id, tenant_verified=True)

        req_2 = FrameworkEvidenceRequest(
            tenant_id=tenant_2.id,
            adoption_id=uuid4(),
            specification_id=uuid4(),
            task_id=uuid4(),
        )
        session.add(req_2)
        session.flush()

        # Under tenant_2 context, only tenant_2 requests are visible
        t2_visible = session.scalars(select(FrameworkEvidenceRequest)).all()
        assert len(t2_visible) == 1
        assert t2_visible[0].id == req_2.id

        # Switch back to tenant_1 context, only tenant_1 requests are visible
        set_rls_context(session, user_id=user_1.id, tenant_id=tenant_1.id, tenant_verified=True)
        t1_visible = session.scalars(select(FrameworkEvidenceRequest)).all()
        assert len(t1_visible) == 1
        assert t1_visible[0].id == req_1.id

        session.close()
        transaction.rollback()
