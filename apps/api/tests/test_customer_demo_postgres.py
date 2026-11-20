"""PostgreSQL integration tests: tenant RLS isolation, immutability triggers, and composite FKs."""

import threading
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from conformly.customer_demo.evaluator import compute_answers_digest, compute_evaluation_digest
from conformly.customer_demo.fixture import (
    BUNDLE_V1_DIGEST,
    EVALUATOR_VERSION,
    FACT_CLOUD_V1_ID,
    FACT_REGION_V1_ID,
    PACK_VERSION_V1_ID,
)
from conformly.customer_demo.models import (
    CustomerDemoAdoption,
    CustomerDemoAnswers,
    CustomerDemoEvaluation,
    CustomerDemoWorkspace,
)
from conformly.identity.models import Tenant, TenantStatus, User
from conformly.tenancy.rls import set_rls_context


def test_customer_demo_tenant_rls_isolation(postgres_connection: Connection) -> None:
    """Verify tenant isolation across all four customer demo tables under conformly_app RLS."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)

        user1 = User(
            oidc_issuer="https://auth.example.com",
            oidc_subject=str(uuid4()),
            email=f"{uuid4()}@example.com",
            display_name="User 1",
            created_at=now,
            updated_at=now,
        )
        user2 = User(
            oidc_issuer="https://auth.example.com",
            oidc_subject=str(uuid4()),
            email=f"{uuid4()}@example.com",
            display_name="User 2",
            created_at=now,
            updated_at=now,
        )
        tenant1 = Tenant(
            name="Demo Tenant 1",
            slug=f"demo-1-{uuid4()}",
            status=TenantStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        tenant2 = Tenant(
            name="Demo Tenant 2",
            slug=f"demo-2-{uuid4()}",
            status=TenantStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        session.add_all([user1, user2, tenant1, tenant2])
        session.flush()

        # Seed data for Tenant 1
        set_rls_context(session, user_id=user1.id, tenant_id=tenant1.id, tenant_verified=True)
        ws1 = CustomerDemoWorkspace(
            tenant_id=tenant1.id,
            current_revision=1,
            selection_revision=1,
            created_at=now,
            updated_at=now,
        )
        ans_digest1 = compute_answers_digest(
            "ALPHA", {str(FACT_CLOUD_V1_ID): True, str(FACT_REGION_V1_ID): "EU"}
        )
        ans1 = CustomerDemoAnswers(
            tenant_id=tenant1.id,
            revision=1,
            company_code="ALPHA",
            answers={"synthetic_wp09_uses_cloud": True},
            content_digest=ans_digest1,
            actor_id=user1.id,
            created_at=now,
        )
        session.add(ws1)
        session.flush()
        session.add(ans1)
        session.flush()

        eval_digest1 = compute_evaluation_digest(
            ans_digest1, 1, PACK_VERSION_V1_ID, BUNDLE_V1_DIGEST, []
        )
        eval1 = CustomerDemoEvaluation(
            tenant_id=tenant1.id,
            answer_revision=1,
            pack_version_id=PACK_VERSION_V1_ID,
            bundle_digest=BUNDLE_V1_DIGEST,
            evaluator_version=EVALUATOR_VERSION,
            results=[],
            content_digest=eval_digest1,
            actor_id=user1.id,
            created_at=now,
        )
        session.add(eval1)
        session.flush()

        adopt1 = CustomerDemoAdoption(
            tenant_id=tenant1.id,
            evaluation_id=eval1.id,
            pack_version_id=PACK_VERSION_V1_ID,
            bundle_digest=BUNDLE_V1_DIGEST,
            actor_id=user1.id,
            created_at=now,
            selection_revision=1,
        )
        session.add(adopt1)
        session.flush()

        # Seed data for Tenant 2
        set_rls_context(session, user_id=user2.id, tenant_id=tenant2.id, tenant_verified=True)
        ws2 = CustomerDemoWorkspace(
            tenant_id=tenant2.id,
            current_revision=1,
            selection_revision=0,
            created_at=now,
            updated_at=now,
        )
        ans_digest2 = compute_answers_digest("BETA", {str(FACT_CLOUD_V1_ID): False})
        ans2 = CustomerDemoAnswers(
            tenant_id=tenant2.id,
            revision=1,
            company_code="BETA",
            answers={"synthetic_wp09_uses_cloud": False},
            content_digest=ans_digest2,
            actor_id=user2.id,
            created_at=now,
        )
        session.add(ws2)
        session.flush()
        session.add(ans2)
        session.flush()

        # Assert Tenant 2 cannot see Tenant 1 records
        assert (
            session.query(CustomerDemoWorkspace)
            .filter(CustomerDemoWorkspace.tenant_id == tenant1.id)
            .count()
            == 0
        )
        assert (
            session.query(CustomerDemoAnswers)
            .filter(CustomerDemoAnswers.tenant_id == tenant1.id)
            .count()
            == 0
        )
        assert (
            session.query(CustomerDemoEvaluation)
            .filter(CustomerDemoEvaluation.tenant_id == tenant1.id)
            .count()
            == 0
        )
        assert (
            session.query(CustomerDemoAdoption)
            .filter(CustomerDemoAdoption.tenant_id == tenant1.id)
            .count()
            == 0
        )

        # Assert Tenant 2 only sees its own records
        assert session.query(CustomerDemoWorkspace).count() == 1
        assert session.query(CustomerDemoAnswers).count() == 1

        # Switch to Tenant 1
        set_rls_context(session, user_id=user1.id, tenant_id=tenant1.id, tenant_verified=True)
        assert (
            session.query(CustomerDemoWorkspace)
            .filter(CustomerDemoWorkspace.tenant_id == tenant2.id)
            .count()
            == 0
        )
        assert (
            session.query(CustomerDemoAnswers)
            .filter(CustomerDemoAnswers.tenant_id == tenant2.id)
            .count()
            == 0
        )
        assert session.query(CustomerDemoEvaluation).count() == 1
        assert session.query(CustomerDemoAdoption).count() == 1

        # Unverified tenant context cannot see any records
        set_rls_context(session, user_id=user1.id, tenant_id=tenant1.id, tenant_verified=False)
        assert session.query(CustomerDemoWorkspace).count() == 0
        assert session.query(CustomerDemoAnswers).count() == 0
        assert session.query(CustomerDemoEvaluation).count() == 0
        assert session.query(CustomerDemoAdoption).count() == 0


def test_customer_demo_immutability_triggers(postgres_connection: Connection) -> None:
    """Verify triggers prevent UPDATE and DELETE on history tables, and prevent workspace identity change."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)

        user = User(
            oidc_issuer="https://auth.example.com",
            oidc_subject=str(uuid4()),
            email=f"{uuid4()}@example.com",
            display_name="Trigger Test User",
            created_at=now,
            updated_at=now,
        )
        tenant = Tenant(
            name="Trigger Tenant",
            slug=f"trig-{uuid4()}",
            status=TenantStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        session.add_all([user, tenant])
        session.flush()

        set_rls_context(session, user_id=user.id, tenant_id=tenant.id, tenant_verified=True)
        ws = CustomerDemoWorkspace(
            tenant_id=tenant.id,
            current_revision=1,
            selection_revision=0,
            created_at=now,
            updated_at=now,
        )
        ans_digest = compute_answers_digest("ALPHA", {str(FACT_CLOUD_V1_ID): True})
        ans = CustomerDemoAnswers(
            tenant_id=tenant.id,
            revision=1,
            company_code="ALPHA",
            answers={"synthetic_wp09_uses_cloud": True},
            content_digest=ans_digest,
            actor_id=user.id,
            created_at=now,
        )
        session.add(ws)
        session.flush()
        session.add(ans)
        session.flush()

        # 1. Attempt UPDATE on customer_demo_answers -> denied by permissions/trigger
        with pytest.raises(DBAPIError, match=r"immutable|permission denied"):
            with session.begin_nested():
                session.execute(
                    text(
                        "UPDATE customer_demo_answers SET company_code = 'BETA' WHERE revision = 1"
                    )
                )

        # 2. Attempt DELETE on customer_demo_answers -> denied by permissions/trigger
        with pytest.raises(DBAPIError, match=r"immutable|permission denied"):
            with session.begin_nested():
                session.execute(text("DELETE FROM customer_demo_answers WHERE revision = 1"))

        # 3. Attempt UPDATE of tenant_id on customer_demo_workspaces -> trigger exception / column permission denied
        with pytest.raises(DBAPIError, match=r"immutable|permission denied"):
            with session.begin_nested():
                new_tenant_id = uuid4()
                session.execute(
                    text(f"UPDATE customer_demo_workspaces SET tenant_id = '{new_tenant_id}'")
                )


def test_customer_demo_cross_tenant_composite_fk_denied(postgres_connection: Connection) -> None:
    """Verify composite foreign keys strictly prevent cross-tenant evaluation and adoption references."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)

        user1 = User(
            oidc_issuer="https://auth.example.com",
            oidc_subject=str(uuid4()),
            email=f"{uuid4()}@example.com",
            display_name="Cross FK User 1",
            created_at=now,
            updated_at=now,
        )
        user2 = User(
            oidc_issuer="https://auth.example.com",
            oidc_subject=str(uuid4()),
            email=f"{uuid4()}@example.com",
            display_name="Cross FK User 2",
            created_at=now,
            updated_at=now,
        )
        tenant1 = Tenant(
            name="Cross FK Tenant 1",
            slug=f"cross-1-{uuid4()}",
            status=TenantStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        tenant2 = Tenant(
            name="Cross FK Tenant 2",
            slug=f"cross-2-{uuid4()}",
            status=TenantStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        session.add_all([user1, user2, tenant1, tenant2])
        session.flush()

        # Seed Tenant 1 data
        set_rls_context(session, user_id=user1.id, tenant_id=tenant1.id, tenant_verified=True)
        ws1 = CustomerDemoWorkspace(
            tenant_id=tenant1.id,
            current_revision=1,
            selection_revision=0,
            created_at=now,
            updated_at=now,
        )
        ans_digest1 = compute_answers_digest("ALPHA", {str(FACT_CLOUD_V1_ID): True})
        ans1 = CustomerDemoAnswers(
            tenant_id=tenant1.id,
            revision=1,
            company_code="ALPHA",
            answers={"synthetic_wp09_uses_cloud": True},
            content_digest=ans_digest1,
            actor_id=user1.id,
            created_at=now,
        )
        session.add(ws1)
        session.flush()
        session.add(ans1)
        session.flush()

        eval_digest1 = compute_evaluation_digest(
            ans_digest1, 1, PACK_VERSION_V1_ID, BUNDLE_V1_DIGEST, []
        )
        eval1 = CustomerDemoEvaluation(
            tenant_id=tenant1.id,
            answer_revision=1,
            pack_version_id=PACK_VERSION_V1_ID,
            bundle_digest=BUNDLE_V1_DIGEST,
            evaluator_version=EVALUATOR_VERSION,
            results=[],
            content_digest=eval_digest1,
            actor_id=user1.id,
            created_at=now,
        )
        session.add(eval1)
        session.flush()

        # Switch to Tenant 2
        set_rls_context(session, user_id=user2.id, tenant_id=tenant2.id, tenant_verified=True)
        ws2 = CustomerDemoWorkspace(
            tenant_id=tenant2.id,
            current_revision=0,
            selection_revision=0,
            created_at=now,
            updated_at=now,
        )
        session.add(ws2)
        session.flush()

        # Attempt: Tenant 2 tries to adopt Tenant 1's evaluation
        with pytest.raises(DBAPIError):
            with session.begin_nested():
                cross_adopt = CustomerDemoAdoption(
                    tenant_id=tenant2.id,
                    evaluation_id=eval1.id,  # belongs to tenant1!
                    pack_version_id=PACK_VERSION_V1_ID,
                    bundle_digest=BUNDLE_V1_DIGEST,
                    actor_id=user2.id,
                    created_at=now,
                    selection_revision=1,
                )
                session.add(cross_adopt)
                session.flush()


def test_customer_demo_column_level_privileges(postgres_connection: Connection) -> None:
    """Verify conformly_app has strict column privileges on customer_demo_workspaces (R6)."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)

        user = User(
            oidc_issuer="https://auth.example.com",
            oidc_subject=str(uuid4()),
            email=f"{uuid4()}@example.com",
            display_name="Priv Test User",
            created_at=now,
            updated_at=now,
        )
        tenant = Tenant(
            name="Priv Tenant",
            slug=f"priv-{uuid4()}",
            status=TenantStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        session.add_all([user, tenant])
        session.flush()

        set_rls_context(session, user_id=user.id, tenant_id=tenant.id, tenant_verified=True)
        ws = CustomerDemoWorkspace(
            tenant_id=tenant.id,
            current_revision=0,
            selection_revision=0,
            created_at=now,
            updated_at=now,
        )
        session.add(ws)
        session.flush()

        # 1. Allowed column UPDATEs (current_revision, selection_revision, updated_at) succeed
        session.execute(
            text(
                "UPDATE customer_demo_workspaces "
                "SET current_revision = 1, selection_revision = 1, updated_at = now() "
                "WHERE tenant_id = :tid"
            ),
            {"tid": tenant.id},
        )

        # 2. Disallowed column UPDATE (created_at) fails with permission denied
        with pytest.raises(
            DBAPIError, match=r"permission denied for table|permission denied for column"
        ):
            with session.begin_nested():
                session.execute(
                    text(
                        "UPDATE customer_demo_workspaces SET created_at = now() WHERE tenant_id = :tid"
                    ),
                    {"tid": tenant.id},
                )


def test_customer_demo_concurrency_workspace_creation_race(postgres_connection: Connection) -> None:
    """Verify concurrent initial workspace creation results in exactly 1 workspace row (R9)."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)
        user = User(
            oidc_issuer="https://auth.example.com",
            oidc_subject=str(uuid4()),
            email=f"{uuid4()}@example.com",
            display_name="Race User 1",
            created_at=now,
            updated_at=now,
        )
        tenant = Tenant(
            name="Race Tenant 1",
            slug=f"race-1-{uuid4()}",
            status=TenantStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        session.add_all([user, tenant])
        session.flush()
        tenant_id = tenant.id
        user_id = user.id

    from conformly.customer_demo.service import _get_or_create_workspace_locked

    barrier = threading.Barrier(2)
    results: list[int] = []
    errors: list[Exception] = []

    def worker():
        try:
            with postgres_connection.engine.connect() as conn:
                with conn.begin():
                    s = Session(bind=conn)
                    set_rls_context(s, user_id=user_id, tenant_id=tenant_id, tenant_verified=True)
                    barrier.wait(timeout=5)
                    ws = _get_or_create_workspace_locked(s, tenant_id)
                    results.append(ws.current_revision)
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not t1.is_alive(), "Worker thread 1 failed to terminate"
    assert not t2.is_alive(), "Worker thread 2 failed to terminate"

    with postgres_connection.begin():
        leaked_locks = postgres_connection.execute(
            text("SELECT count(*) FROM pg_locks WHERE locktype = 'transactionid'")
        ).scalar()
        assert leaked_locks == 0, f"Leaked transaction locks found: {leaked_locks}"

    assert not errors, f"Errors in concurrent workspace creation: {errors}"
    assert len(results) == 2
    assert results == [0, 0]

    with postgres_connection.begin():
        s = Session(bind=postgres_connection)
        set_rls_context(s, user_id=user_id, tenant_id=tenant_id, tenant_verified=True)
        count = (
            s.query(CustomerDemoWorkspace)
            .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
            .count()
        )
        assert count == 1


def test_customer_demo_concurrency_answer_save_race(
    postgres_connection: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify concurrent same-revision answer saves result in exactly 1 winner and 1 409 conflict (R9)."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)
        user = User(
            oidc_issuer="https://auth.example.com",
            oidc_subject=str(uuid4()),
            email=f"{uuid4()}@example.com",
            display_name="Race User 2",
            created_at=now,
            updated_at=now,
        )
        tenant = Tenant(
            name="Race Tenant 2",
            slug=f"race-2-{uuid4()}",
            status=TenantStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        session.add_all([user, tenant])
        session.flush()
        tenant_id = tenant.id
        user_id = user.id

    from conformly.config import get_settings

    monkeypatch.setattr(get_settings(), "enable_customer_demo", True)

    from fastapi import HTTPException

    from conformly.authz.policy import Principal, TenantContext
    from conformly.authz.roles import Role
    from conformly.customer_demo.service import save_answers

    barrier = threading.Barrier(2)
    winners: list[int] = []
    conflicts: list[int] = []
    unexpected_errors: list[Exception] = []

    def worker(req_id: str):
        try:
            with postgres_connection.engine.connect() as conn:
                with conn.begin():
                    s = Session(bind=conn)
                    set_rls_context(s, user_id=user_id, tenant_id=tenant_id, tenant_verified=True)
                    p = Principal(user_id=user_id, mfa_verified=True)
                    tc = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.OWNER)
                    barrier.wait(timeout=5)
                    ans = save_answers(
                        s,
                        p,
                        tc,
                        expected_revision=0,
                        company_code="ALPHA",
                        raw_answers={"synthetic_wp09_uses_cloud": True},
                        request_id=req_id,
                    )
                    winners.append(ans.revision)
        except HTTPException as he:
            if he.status_code == 409:
                conflicts.append(409)
            else:
                unexpected_errors.append(he)
        except Exception as e:
            unexpected_errors.append(e)

    t1 = threading.Thread(target=worker, args=("req-race-1",))
    t2 = threading.Thread(target=worker, args=("req-race-2",))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not t1.is_alive(), "Worker thread 1 failed to terminate"
    assert not t2.is_alive(), "Worker thread 2 failed to terminate"

    with postgres_connection.begin():
        leaked_locks = postgres_connection.execute(
            text("SELECT count(*) FROM pg_locks WHERE locktype = 'transactionid'")
        ).scalar()
        assert leaked_locks == 0, f"Leaked transaction locks found: {leaked_locks}"

    assert not unexpected_errors, f"Unexpected errors: {unexpected_errors}"
    assert len(winners) == 1
    assert winners[0] == 1
    assert len(conflicts) == 1
    assert conflicts[0] == 409

    with postgres_connection.begin():
        s = Session(bind=postgres_connection)
        set_rls_context(s, user_id=user_id, tenant_id=tenant_id, tenant_verified=True)
        count = (
            s.query(CustomerDemoAnswers).filter(CustomerDemoAnswers.tenant_id == tenant_id).count()
        )
        assert count == 1


def test_customer_demo_concurrency_answer_update_vs_adoption_race(
    postgres_connection: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify concurrent answer update vs adoption race never leaves stale current adoption (R9)."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)
        user = User(
            oidc_issuer="https://auth.example.com",
            oidc_subject=str(uuid4()),
            email=f"{uuid4()}@example.com",
            display_name="Race User 3",
            created_at=now,
            updated_at=now,
        )
        tenant = Tenant(
            name="Race Tenant 3",
            slug=f"race-3-{uuid4()}",
            status=TenantStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        session.add_all([user, tenant])
        session.flush()
        tenant_id = tenant.id
        user_id = user.id

    from conformly.config import get_settings

    monkeypatch.setattr(get_settings(), "enable_customer_demo", True)

    from fastapi import HTTPException

    from conformly.authz.policy import Principal, TenantContext
    from conformly.authz.roles import Role
    from conformly.customer_demo.service import adopt_evaluation, evaluate_answers, save_answers

    # Seed revision 1 answers and evaluation
    with postgres_connection.begin():
        s = Session(bind=postgres_connection)
        set_rls_context(s, user_id=user_id, tenant_id=tenant_id, tenant_verified=True)
        p = Principal(user_id=user_id, mfa_verified=True)
        tc = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.OWNER)
        save_answers(
            s,
            p,
            tc,
            expected_revision=0,
            company_code="ALPHA",
            raw_answers={
                "synthetic_wp09_uses_cloud": True,
                "synthetic_wp09_operating_region": "EU",
            },
            request_id="seed-ans-1",
        )
        ev = evaluate_answers(
            s,
            p,
            tc,
            expected_revision=1,
            pack_version_id=PACK_VERSION_V1_ID,
            request_id="seed-eval-1",
        )
        eval_id = ev.id

    barrier = threading.Barrier(2)
    save_result: list[str] = []
    adopt_result: list[str] = []

    def worker_save():
        try:
            with postgres_connection.engine.connect() as conn:
                with conn.begin():
                    s = Session(bind=conn)
                    set_rls_context(s, user_id=user_id, tenant_id=tenant_id, tenant_verified=True)
                    p = Principal(user_id=user_id, mfa_verified=True)
                    tc = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.OWNER)
                    barrier.wait(timeout=5)
                    ans = save_answers(
                        s,
                        p,
                        tc,
                        expected_revision=1,
                        company_code="BETA",
                        raw_answers={"synthetic_wp09_uses_cloud": False},
                        request_id="race-ans-2",
                    )
                    save_result.append(f"saved_rev_{ans.revision}")
        except Exception as e:
            save_result.append(f"error_{type(e).__name__}")

    def worker_adopt():
        try:
            with postgres_connection.engine.connect() as conn:
                with conn.begin():
                    s = Session(bind=conn)
                    set_rls_context(s, user_id=user_id, tenant_id=tenant_id, tenant_verified=True)
                    p = Principal(user_id=user_id, mfa_verified=True)
                    tc = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.OWNER)
                    barrier.wait(timeout=5)
                    adopt_evaluation(
                        s,
                        p,
                        tc,
                        expected_revision=1,
                        evaluation_id=eval_id,
                        pack_version_id=PACK_VERSION_V1_ID,
                        acknowledge_synthetic=True,
                        acknowledge_missing_information=True,
                        request_id="race-adopt",
                    )
                    adopt_result.append("adopted")
        except HTTPException as he:
            adopt_result.append(f"http_{he.status_code}")
        except Exception as e:
            adopt_result.append(f"error_{type(e).__name__}")

    t1 = threading.Thread(target=worker_save)
    t2 = threading.Thread(target=worker_adopt)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not t1.is_alive(), "Worker thread 1 failed to terminate"
    assert not t2.is_alive(), "Worker thread 2 failed to terminate"

    with postgres_connection.begin():
        leaked_locks = postgres_connection.execute(
            text("SELECT count(*) FROM pg_locks WHERE locktype = 'transactionid'")
        ).scalar()
        assert leaked_locks == 0, f"Leaked transaction locks found: {leaked_locks}"

    assert save_result == ["saved_rev_2"]
    assert adopt_result in (["adopted"], ["http_409"])

    with postgres_connection.begin():
        s = Session(bind=postgres_connection)
        set_rls_context(s, user_id=user_id, tenant_id=tenant_id, tenant_verified=True)
        ws = (
            s.query(CustomerDemoWorkspace)
            .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
            .first()
        )
        assert ws is not None
        assert ws.current_revision == 2

        # Verify full current selection/evaluation relationship and STALE presentation (P1)
        from conformly.customer_demo.service import get_workspace_data

        p = Principal(user_id=user_id, mfa_verified=True)
        tc = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.OWNER)
        ws_state = get_workspace_data(s, p, tc, request_id="check-stale-race")
        if adopt_result == ["adopted"]:
            assert ws_state["selected_pack"] is not None
            assert ws_state["selected_pack"]["is_stale"] is True
            assert ws_state["selected_pack"]["evaluation_id"] == eval_id
        else:
            assert ws_state["selection_revision"] == 0


def test_customer_demo_postgres_transaction_rollback_on_errors(
    postgres_connection: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify PostgreSQL transaction rollback on rejected request leaves zero rows and no leaked locks (P1)."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)
        user = User(
            oidc_issuer="https://auth.example.com",
            oidc_subject=str(uuid4()),
            email=f"{uuid4()}@example.com",
            display_name="Rollback User",
            created_at=now,
            updated_at=now,
        )
        tenant = Tenant(
            name="Rollback Tenant",
            slug=f"rollback-{uuid4()}",
            status=TenantStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        session.add_all([user, tenant])
        session.flush()
        tenant_id = tenant.id
        user_id = user.id

    from conformly.config import get_settings

    monkeypatch.setattr(get_settings(), "enable_customer_demo", True)

    from fastapi import HTTPException

    from conformly.authz.policy import Principal, TenantContext
    from conformly.authz.roles import Role
    from conformly.customer_demo.service import save_answers

    p = Principal(user_id=user_id, mfa_verified=True)
    tc = TenantContext(tenant_id=tenant_id, user_id=user_id, role=Role.OWNER)

    # Attempt save_answers with invalid payload under a real transactional connection
    with postgres_connection.engine.connect() as conn:
        with conn.begin():
            s = Session(bind=conn)
            set_rls_context(s, user_id=user_id, tenant_id=tenant_id, tenant_verified=True)
            with pytest.raises(HTTPException) as exc:
                save_answers(
                    s,
                    p,
                    tc,
                    expected_revision=0,
                    company_code="ALPHA",
                    raw_answers={"invalid_fact_uuid": True},
                    request_id="req-rollback-pg",
                )
            assert exc.value.status_code == 422
            # Explicit rollback verifies clean state
            s.rollback()

    # Verify no workspace or answers row was committed in PostgreSQL
    with postgres_connection.begin():
        s = Session(bind=postgres_connection)
        set_rls_context(s, user_id=user_id, tenant_id=tenant_id, tenant_verified=True)
        ws_count = (
            s.query(CustomerDemoWorkspace)
            .filter(CustomerDemoWorkspace.tenant_id == tenant_id)
            .count()
        )
        ans_count = (
            s.query(CustomerDemoAnswers).filter(CustomerDemoAnswers.tenant_id == tenant_id).count()
        )
        assert ws_count == 0
        assert ans_count == 0

        leaked_locks = postgres_connection.execute(
            text("SELECT count(*) FROM pg_locks WHERE locktype = 'transactionid'")
        ).scalar()
        assert leaked_locks == 0


def test_customer_demo_postgres_database_admission_non_owner(
    postgres_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify verify_database_connection enforces non-owner and fails closed (P1)."""
    from conformly.customer_demo.policy import (
        CustomerDemoDatabaseAdmissionError,
        verify_database_connection,
    )

    with postgres_connection.begin():
        s = Session(bind=postgres_connection)
        # 1. Real conformly_app connection should succeed
        verify_database_connection(s)

        # 2. If table ownership query detects ownership, it must raise CustomerDemoDatabaseAdmissionError
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("customer_demo_workspaces",)]

        real_execute = s.execute

        def fake_execute(stmt: Any, *args: Any, **kwargs: Any) -> Any:
            if "relowner" in str(stmt):
                return mock_result
            return real_execute(stmt, *args, **kwargs)

        monkeypatch.setattr(s, "execute", fake_execute)
        with pytest.raises(CustomerDemoDatabaseAdmissionError) as exc:
            verify_database_connection(s)
        assert "must not own customer demo tables" in str(exc.value)
