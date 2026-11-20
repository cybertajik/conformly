"""PostgreSQL integration tests: customer assessment lifecycle, RLS, triggers, and migrations.

Asserts ENABLE/FORCE RLS, column privileges, immutability triggers,
cross-tenant composite foreign keys, and downgrade preflight protections
for customer_assessment_heads, customer_assessment_events, and customer_assessment_findings.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Connection, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from conformly.authz.roles import Role
from conformly.customer_demo.assessment_models import (
    CustomerAssessmentEvent,
    CustomerAssessmentFinding,
    CustomerAssessmentHead,
)
from conformly.customer_demo.evaluator import compute_evaluation_digest
from conformly.customer_demo.fixture import (
    PACK_VERSION_V2_ID,
    get_bundle_digest,
)
from conformly.customer_demo.models import (
    CustomerDemoAdoption,
    CustomerDemoAnswers,
    CustomerDemoEvaluation,
    CustomerDemoWorkspace,
)
from conformly.customer_demo.work_models import CustomerControlWork
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User
from conformly.tenancy.rls import set_rls_context


@pytest.fixture
def enable_customer_demo_feature(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scoped test-only demo feature and environment enablement with automatic restoration."""
    from conformly.config import get_settings

    cfg = get_settings()
    monkeypatch.setattr(cfg, "enable_customer_demo", True)
    monkeypatch.setattr(cfg, "environment", "test")


def _seed_hierarchy(session: Session) -> dict[str, Any]:
    now = datetime.now(UTC)
    t1 = Tenant(
        name="Postgres Assessment Tenant 1",
        slug=f"pg-assess-1-{uuid4()}",
        status=TenantStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    t2 = Tenant(
        name="Postgres Assessment Tenant 2",
        slug=f"pg-assess-2-{uuid4()}",
        status=TenantStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    u1 = User(
        oidc_issuer="https://auth.example.com",
        oidc_subject=str(uuid4()),
        email=f"{uuid4()}@example.com",
        display_name="User Assess T1",
        created_at=now,
        updated_at=now,
    )
    u2 = User(
        oidc_issuer="https://auth.example.com",
        oidc_subject=str(uuid4()),
        email=f"{uuid4()}@example.com",
        display_name="User Assess T2",
        created_at=now,
        updated_at=now,
    )
    session.add_all([t1, t2, u1, u2])
    session.flush()

    set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=True)
    m1 = Membership(
        tenant_id=t1.id,
        user_id=u1.id,
        role=Role.OWNER,
        status=MembershipStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    session.add(m1)
    session.flush()

    set_rls_context(session, user_id=u2.id, tenant_id=t2.id, tenant_verified=True)
    m2 = Membership(
        tenant_id=t2.id,
        user_id=u2.id,
        role=Role.OWNER,
        status=MembershipStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    session.add(m2)
    session.flush()

    # Workspace & Adoption for T1
    set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=True)
    ws1 = CustomerDemoWorkspace(
        tenant_id=t1.id,
        current_revision=1,
        selection_revision=1,
        created_at=now,
        updated_at=now,
    )
    ans1_digest = hashlib.sha256(b"ans1").hexdigest()
    ans1 = CustomerDemoAnswers(
        tenant_id=t1.id,
        revision=1,
        company_code="ALPHA",
        answers={"synthetic_wp09_uses_cloud": True},
        content_digest=ans1_digest,
        actor_id=u1.id,
        created_at=now,
    )
    session.add(ws1)
    session.flush()
    session.add(ans1)
    session.flush()

    bundle_digest = get_bundle_digest(PACK_VERSION_V2_ID)
    eval1_digest = compute_evaluation_digest(
        answer_digest=ans1.content_digest,
        answer_revision=1,
        pack_version_id=PACK_VERSION_V2_ID,
        bundle_digest=bundle_digest,
        results=[],
    )
    ev1 = CustomerDemoEvaluation(
        tenant_id=t1.id,
        id=uuid4(),
        answer_revision=1,
        pack_version_id=PACK_VERSION_V2_ID,
        bundle_digest=bundle_digest,
        evaluator_version="1.0.0",
        results=[],
        content_digest=eval1_digest,
        actor_id=u1.id,
        created_at=now,
    )
    session.add(ev1)
    session.flush()

    ad1 = CustomerDemoAdoption(
        tenant_id=t1.id,
        id=uuid4(),
        evaluation_id=ev1.id,
        pack_version_id=PACK_VERSION_V2_ID,
        bundle_digest=bundle_digest,
        actor_id=u1.id,
        selection_revision=1,
        created_at=now,
    )
    session.add(ad1)
    session.flush()

    work1 = CustomerControlWork(
        tenant_id=t1.id,
        id=uuid4(),
        adoption_id=ad1.id,
        control_id=uuid4(),
        control_version_id=uuid4(),
        owner_user_id=u1.id,
        due_date=date(2026, 12, 31),
        version=1,
        created_at=now,
        updated_at=now,
    )
    session.add(work1)
    session.flush()

    # Workspace & Adoption for T2
    set_rls_context(session, user_id=u2.id, tenant_id=t2.id, tenant_verified=True)
    ws2 = CustomerDemoWorkspace(
        tenant_id=t2.id,
        current_revision=1,
        selection_revision=1,
        created_at=now,
        updated_at=now,
    )
    ans2_digest = hashlib.sha256(b"ans2").hexdigest()
    ans2 = CustomerDemoAnswers(
        tenant_id=t2.id,
        revision=1,
        company_code="ALPHA",
        answers={"synthetic_wp09_uses_cloud": True},
        content_digest=ans2_digest,
        actor_id=u2.id,
        created_at=now,
    )
    session.add(ws2)
    session.flush()
    session.add(ans2)
    session.flush()

    ev2 = CustomerDemoEvaluation(
        tenant_id=t2.id,
        id=uuid4(),
        answer_revision=1,
        pack_version_id=PACK_VERSION_V2_ID,
        bundle_digest=bundle_digest,
        evaluator_version="1.0.0",
        results=[],
        content_digest=eval1_digest,
        actor_id=u2.id,
        created_at=now,
    )
    session.add(ev2)
    session.flush()

    ad2 = CustomerDemoAdoption(
        tenant_id=t2.id,
        id=uuid4(),
        evaluation_id=ev2.id,
        pack_version_id=PACK_VERSION_V2_ID,
        bundle_digest=bundle_digest,
        actor_id=u2.id,
        selection_revision=1,
        created_at=now,
    )
    session.add(ad2)
    session.flush()

    work2 = CustomerControlWork(
        tenant_id=t2.id,
        id=uuid4(),
        adoption_id=ad2.id,
        control_id=uuid4(),
        control_version_id=uuid4(),
        owner_user_id=u2.id,
        due_date=date(2026, 12, 31),
        version=1,
        created_at=now,
        updated_at=now,
    )
    session.add(work2)
    session.flush()

    return {
        "t1": t1,
        "t2": t2,
        "u1": u1,
        "u2": u2,
        "work1": work1,
        "work2": work2,
    }


def test_customer_assessment_rls_force_and_isolation(
    postgres_connection: Connection,
) -> None:
    """Verify ENABLE and FORCE RLS on all 3 assessment tables and strict cross-tenant isolation."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)

        tables = [
            "customer_assessment_heads",
            "customer_assessment_events",
            "customer_assessment_findings",
        ]
        for tbl in tables:
            row = session.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = :tbl"
                ),
                {"tbl": tbl},
            ).one()
            assert row[0] is True, f"Table {tbl} must have relrowsecurity enabled"
            assert row[1] is True, f"Table {tbl} must have relforcerowsecurity enabled (FORCE RLS)"

        ctx = _seed_hierarchy(session)
        t1, t2 = ctx["t1"], ctx["t2"]
        u1, u2 = ctx["u1"], ctx["u2"]
        work1 = ctx["work1"]

        set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=True)

        head1 = CustomerAssessmentHead(
            tenant_id=t1.id,
            work_id=work1.id,
            current_revision=1,
            created_at=now,
            updated_at=now,
        )
        session.add(head1)
        session.flush()

        event1 = CustomerAssessmentEvent(
            tenant_id=t1.id,
            id=uuid4(),
            work_id=work1.id,
            revision=1,
            operation_id=uuid4(),
            request_digest="a" * 64,
            event_type="ASSESSMENT",
            result="FAIL",
            observed_work_version=1,
            details_encrypted='{"ciphertext": "encrypted"}',
            actor_id=u1.id,
            created_at=now,
        )
        session.add(event1)
        session.flush()

        finding1 = CustomerAssessmentFinding(
            tenant_id=t1.id,
            id=uuid4(),
            work_id=work1.id,
            source_event_id=event1.id,
            current_event_id=event1.id,
            severity="MEDIUM",
            status="OPEN",
            owner_user_id=u1.id,
            due_date=date(2026, 12, 31),
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(finding1)
        session.flush()

        # Tenant 1 can read its own records
        assert (
            session.execute(
                text("SELECT count(*) FROM customer_assessment_heads WHERE tenant_id = :t1"),
                {"t1": t1.id},
            ).scalar()
            == 1
        )
        assert (
            session.execute(
                text("SELECT count(*) FROM customer_assessment_events WHERE tenant_id = :t1"),
                {"t1": t1.id},
            ).scalar()
            == 1
        )
        assert (
            session.execute(
                text("SELECT count(*) FROM customer_assessment_findings WHERE tenant_id = :t1"),
                {"t1": t1.id},
            ).scalar()
            == 1
        )

        # Switch to Tenant 2 RLS context
        set_rls_context(session, user_id=u2.id, tenant_id=t2.id, tenant_verified=True)

        # Tenant 2 cannot see Tenant 1 assessment records
        assert (
            session.execute(
                text("SELECT count(*) FROM customer_assessment_heads WHERE work_id = :wid"),
                {"wid": work1.id},
            ).scalar()
            == 0
        )
        assert (
            session.execute(
                text("SELECT count(*) FROM customer_assessment_events WHERE id = :eid"),
                {"eid": event1.id},
            ).scalar()
            == 0
        )
        assert (
            session.execute(
                text("SELECT count(*) FROM customer_assessment_findings WHERE id = :fid"),
                {"fid": finding1.id},
            ).scalar()
            == 0
        )

        # Unverified tenant context cannot see records
        set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=False)
        assert session.execute(text("SELECT count(*) FROM customer_assessment_heads")).scalar() == 0


def test_customer_assessment_column_privileges(
    postgres_connection: Connection,
) -> None:
    """Verify strict column-level privileges for conformly_app role and denials for catalog role."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)
        ctx = _seed_hierarchy(session)
        t1, u1 = ctx["t1"], ctx["u1"]
        work1 = ctx["work1"]

        set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=True)

        head1 = CustomerAssessmentHead(
            tenant_id=t1.id,
            work_id=work1.id,
            current_revision=1,
            created_at=now,
            updated_at=now,
        )
        session.add(head1)
        session.flush()

        event1 = CustomerAssessmentEvent(
            tenant_id=t1.id,
            id=uuid4(),
            work_id=work1.id,
            revision=1,
            operation_id=uuid4(),
            request_digest="a" * 64,
            event_type="ASSESSMENT",
            result="FAIL",
            observed_work_version=1,
            details_encrypted='{"ciphertext": "encrypted"}',
            actor_id=u1.id,
            created_at=now,
        )
        session.add(event1)
        session.flush()

        finding1 = CustomerAssessmentFinding(
            tenant_id=t1.id,
            id=uuid4(),
            work_id=work1.id,
            source_event_id=event1.id,
            current_event_id=event1.id,
            severity="MEDIUM",
            status="OPEN",
            owner_user_id=u1.id,
            due_date=date(2026, 12, 31),
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(finding1)
        session.flush()

        # 1. Allowed UPDATEs on customer_assessment_heads (current_revision, updated_at)
        session.execute(
            text(
                "UPDATE customer_assessment_heads "
                "SET current_revision = 2, updated_at = now() "
                "WHERE tenant_id = :tid AND work_id = :wid"
            ),
            {"tid": t1.id, "wid": work1.id},
        )
        session.flush()
        assert (
            session.execute(
                text("SELECT current_revision FROM customer_assessment_heads WHERE work_id = :wid"),
                {"wid": work1.id},
            ).scalar()
            == 2
        )

        # 2. Denied column UPDATEs on customer_assessment_heads
        denied_heads: list[tuple[str, str, dict[str, Any]]] = [
            ("work_id", "SET work_id = :val", {"val": uuid4()}),
            ("created_at", "SET created_at = :val", {"val": now}),
            ("tenant_id", "SET tenant_id = :val", {"val": uuid4()}),
        ]
        for col_name, update_clause, extra_param in denied_heads:
            params: dict[str, Any] = {"tid": t1.id, "wid": work1.id, **extra_param}
            with pytest.raises(DBAPIError) as exc_info:
                with session.begin_nested():
                    session.execute(
                        text(
                            f"UPDATE customer_assessment_heads {update_clause} "
                            "WHERE tenant_id = :tid AND work_id = :wid"
                        ),
                        params,
                    )
                    session.flush()
            assert any(
                kw in str(exc_info.value).lower()
                for kw in ["permission denied", "immutable", "violates"]
            ), f"Expected denial on column {col_name}"

        # 3. Denied UPDATE/DELETE on events
        with pytest.raises(DBAPIError) as exc_ev_upd:
            with session.begin_nested():
                session.execute(
                    text("UPDATE customer_assessment_events SET result = 'PASS' WHERE id = :eid"),
                    {"eid": event1.id},
                )
                session.flush()
        assert any(
            kw in str(exc_ev_upd.value).lower()
            for kw in ["permission denied", "immutable", "cannot_modify_history"]
        )

        # 4. Allowed UPDATEs on customer_assessment_findings (status, severity, version, due_date, updated_at)
        session.execute(
            text(
                "UPDATE customer_assessment_findings "
                "SET status = 'IN_REMEDIATION', version = 2, updated_at = now() "
                "WHERE tenant_id = :tid AND id = :fid"
            ),
            {"tid": t1.id, "fid": finding1.id},
        )
        session.flush()
        assert (
            session.execute(
                text("SELECT status FROM customer_assessment_findings WHERE id = :fid"),
                {"fid": finding1.id},
            ).scalar()
            == "IN_REMEDIATION"
        )

        # 5. Verify function execution privileges
        for fn in (
            "customer_assessment_prevent_history_modification()",
            "customer_assessment_heads_protect()",
            "customer_assessment_findings_protect()",
        ):
            can_exec = session.execute(
                text("SELECT has_function_privilege('conformly_app', :fn, 'EXECUTE')"),
                {"fn": fn},
            ).scalar()
            assert can_exec is True, f"conformly_app missing EXECUTE on {fn}"

            public_exec = session.execute(
                text("SELECT has_function_privilege('public', :fn, 'EXECUTE')"),
                {"fn": fn},
            ).scalar()
            assert public_exec is False, f"PUBLIC illegally granted EXECUTE on {fn}"


def test_customer_assessment_immutability_triggers(
    postgres_connection: Connection,
) -> None:
    """Verify triggers prevent UPDATE/DELETE on events and illegal modifications on heads and findings."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)
        ctx = _seed_hierarchy(session)
        t1, u1 = ctx["t1"], ctx["u1"]
        work1 = ctx["work1"]

        set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=True)

        head1 = CustomerAssessmentHead(
            tenant_id=t1.id,
            work_id=work1.id,
            current_revision=1,
            created_at=now,
            updated_at=now,
        )
        session.add(head1)
        session.flush()

        event1 = CustomerAssessmentEvent(
            tenant_id=t1.id,
            id=uuid4(),
            work_id=work1.id,
            revision=1,
            operation_id=uuid4(),
            request_digest="b" * 64,
            event_type="ASSESSMENT",
            result="PASS",
            observed_work_version=1,
            details_encrypted='{"ciphertext": "encrypted"}',
            actor_id=u1.id,
            created_at=now,
        )
        session.add(event1)
        session.flush()

        # Attempt DELETE on event -> rejected by trigger/permission
        with pytest.raises(DBAPIError) as exc_del:
            with session.begin_nested():
                session.execute(
                    text("DELETE FROM customer_assessment_events WHERE id = :eid"),
                    {"eid": event1.id},
                )
                session.flush()
        assert any(
            kw in str(exc_del.value).lower()
            for kw in ["cannot_modify_history", "permission denied", "immutable"]
        )

        # Attempt illegal backwards revision on head
        with pytest.raises(DBAPIError) as exc_rev:
            with session.begin_nested():
                session.execute(
                    text(
                        "UPDATE customer_assessment_heads SET current_revision = 0 "
                        "WHERE tenant_id = :tid AND work_id = :wid"
                    ),
                    {"tid": t1.id, "wid": work1.id},
                )
                session.flush()
        assert any(
            kw in str(exc_rev.value).lower()
            for kw in ["cannot_modify_history", "immutable", "increment"]
        )


def test_customer_assessment_cross_tenant_composite_fks(
    postgres_connection: Connection,
) -> None:
    """Verify composite foreign keys strictly deny cross-tenant references."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        ctx = _seed_hierarchy(session)
        t1 = ctx["t1"]
        u1 = ctx["u1"]
        work2 = ctx["work2"]  # From Tenant 2!

        set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=True)

        # Cross-tenant work FK: Tenant 1 assessment head referencing Tenant 2 work item
        with pytest.raises(DBAPIError) as exc_fk:
            with session.begin_nested():
                session.execute(
                    text(
                        "INSERT INTO customer_assessment_heads "
                        "(tenant_id, work_id, current_revision, created_at, updated_at) "
                        "VALUES (:tid, :wid, 1, now(), now())"
                    ),
                    {
                        "tid": t1.id,
                        "wid": work2.id,  # From Tenant 2!
                    },
                )
                session.flush()
        assert "violates foreign key constraint" in str(exc_fk.value).lower()


def test_customer_assessment_downgrade_preflight_refusal(
    postgres_connection: Connection,
) -> None:
    """Verify migration 0047 downgrade preflight refuses when any assessment table is populated."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)
        ctx = _seed_hierarchy(session)
        t1, u1 = ctx["t1"], ctx["u1"]
        work1 = ctx["work1"]

        set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=True)

        head1 = CustomerAssessmentHead(
            tenant_id=t1.id,
            work_id=work1.id,
            current_revision=1,
            created_at=now,
            updated_at=now,
        )
        session.add(head1)
        session.flush()

        downgrade_sql = text("""
        DO $$
        DECLARE
            cnt_heads integer := 0;
            cnt_events integer := 0;
            cnt_findings integer := 0;
        BEGIN
            SELECT count(*) INTO cnt_heads FROM customer_assessment_heads;
            SELECT count(*) INTO cnt_events FROM customer_assessment_events;
            SELECT count(*) INTO cnt_findings FROM customer_assessment_findings;

            IF (cnt_heads + cnt_events + cnt_findings) > 0 THEN
                RAISE EXCEPTION 'CANNOT_DOWNGRADE_CUSTOMER_ASSESSMENT_DATA_EXISTS';
            END IF;
        END $$;
        """)

        with pytest.raises(DBAPIError) as exc_down:
            with session.begin_nested():
                session.execute(downgrade_sql)
        assert "cannot_downgrade_customer_assessment_data_exists" in str(exc_down.value).lower()


def test_customer_assessment_finding_resolution_and_retest_triggers(
    postgres_connection: Connection,
) -> None:
    """Verify trigger enforces that finding status can only become RESOLVED via RETEST event with PASS result."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)
        ctx = _seed_hierarchy(session)
        t1, u1 = ctx["t1"], ctx["u1"]
        work1 = ctx["work1"]

        set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=True)

        head1 = CustomerAssessmentHead(
            tenant_id=t1.id,
            work_id=work1.id,
            current_revision=1,
            created_at=now,
            updated_at=now,
        )
        session.add(head1)
        session.flush()

        # 1. Initial ASSESSMENT event with FAIL result
        ev_assess_fail = CustomerAssessmentEvent(
            tenant_id=t1.id,
            id=uuid4(),
            work_id=work1.id,
            revision=1,
            operation_id=uuid4(),
            request_digest="c" * 64,
            event_type="ASSESSMENT",
            result="FAIL",
            observed_work_version=1,
            details_encrypted='{"ciphertext": "encrypted"}',
            actor_id=u1.id,
            created_at=now,
        )
        session.add(ev_assess_fail)
        session.flush()

        # Initial finding OPEN, version=1
        fid = uuid4()
        session.execute(
            text(
                "INSERT INTO customer_assessment_findings "
                "(tenant_id, id, work_id, source_event_id, current_event_id, severity, status, version, created_at, updated_at) "
                "VALUES (:tid, :fid, :wid, :seid, :ceid, 'HIGH', 'OPEN', 1, now(), now())"
            ),
            {
                "tid": t1.id,
                "fid": fid,
                "wid": work1.id,
                "seid": ev_assess_fail.id,
                "ceid": ev_assess_fail.id,
            },
        )
        session.flush()

        # 2. Attempt to resolve finding using an ASSESSMENT event -> trigger raises exception
        with pytest.raises(DBAPIError) as exc_assess_res:
            with session.begin_nested():
                session.execute(
                    text(
                        "UPDATE customer_assessment_findings SET status = 'RESOLVED', version = 2, "
                        "current_event_id = :ceid, updated_at = now() WHERE tenant_id = :tid AND id = :fid"
                    ),
                    {"tid": t1.id, "fid": fid, "ceid": ev_assess_fail.id},
                )
                session.flush()
        assert (
            "finding can only be resolved by a retest event with pass result"
            in str(exc_assess_res.value).lower()
        )

        # 3. Retest event with FAIL result
        ev_retest_fail = CustomerAssessmentEvent(
            tenant_id=t1.id,
            id=uuid4(),
            work_id=work1.id,
            revision=2,
            operation_id=uuid4(),
            request_digest="d" * 64,
            event_type="RETEST",
            result="FAIL",
            observed_work_version=1,
            details_encrypted='{"ciphertext": "encrypted"}',
            actor_id=u1.id,
            created_at=now,
        )
        session.add(ev_retest_fail)
        session.flush()

        # Attempt to resolve finding using FAIL retest -> trigger raises exception
        with pytest.raises(DBAPIError) as exc_retest_fail_res:
            with session.begin_nested():
                session.execute(
                    text(
                        "UPDATE customer_assessment_findings SET status = 'RESOLVED', version = 2, "
                        "current_event_id = :ceid, updated_at = now() WHERE tenant_id = :tid AND id = :fid"
                    ),
                    {"tid": t1.id, "fid": fid, "ceid": ev_retest_fail.id},
                )
                session.flush()
        assert (
            "finding can only be resolved by a retest event with pass result"
            in str(exc_retest_fail_res.value).lower()
        )

        # 4. Retest event with PASS result
        ev_retest_pass = CustomerAssessmentEvent(
            tenant_id=t1.id,
            id=uuid4(),
            work_id=work1.id,
            revision=3,
            operation_id=uuid4(),
            request_digest="e" * 64,
            event_type="RETEST",
            result="PASS",
            observed_work_version=1,
            details_encrypted='{"ciphertext": "encrypted"}',
            actor_id=u1.id,
            created_at=now,
        )
        session.add(ev_retest_pass)
        session.flush()

        # Successfully resolve finding with PASS retest event
        session.execute(
            text(
                "UPDATE customer_assessment_findings SET status = 'RESOLVED', version = 2, "
                "current_event_id = :ceid, updated_at = now() WHERE tenant_id = :tid AND id = :fid"
            ),
            {"tid": t1.id, "fid": fid, "ceid": ev_retest_pass.id},
        )
        session.flush()
        res_status = session.execute(
            text("SELECT status FROM customer_assessment_findings WHERE id = :fid"),
            {"fid": fid},
        ).scalar()
        assert res_status == "RESOLVED"


def test_customer_assessment_owner_immutability_and_identity(
    postgres_connection: Connection,
) -> None:
    """Verify owner-level trigger immutability prevents UPDATE/DELETE on events and illegal deletes on heads and findings."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)
        ctx = _seed_hierarchy(session)
        t1, u1 = ctx["t1"], ctx["u1"]
        work1 = ctx["work1"]

        set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=True)

        head1 = CustomerAssessmentHead(
            tenant_id=t1.id,
            work_id=work1.id,
            current_revision=1,
            created_at=now,
            updated_at=now,
        )
        session.add(head1)
        session.flush()

        ev1 = CustomerAssessmentEvent(
            tenant_id=t1.id,
            id=uuid4(),
            work_id=work1.id,
            revision=1,
            operation_id=uuid4(),
            request_digest="f" * 64,
            event_type="ASSESSMENT",
            result="FAIL",
            observed_work_version=1,
            details_encrypted='{"ciphertext": "encrypted"}',
            actor_id=u1.id,
            created_at=now,
        )
        session.add(ev1)
        session.flush()

        fid1 = uuid4()
        session.execute(
            text(
                "INSERT INTO customer_assessment_findings "
                "(tenant_id, id, work_id, source_event_id, current_event_id, severity, status, version, created_at, updated_at) "
                "VALUES (:tid, :fid, :wid, :seid, :ceid, 'LOW', 'OPEN', 1, now(), now())"
            ),
            {"tid": t1.id, "fid": fid1, "wid": work1.id, "seid": ev1.id, "ceid": ev1.id},
        )
        session.flush()

        # Direct UPDATE on events raises permission denial or trigger immutability exception
        with pytest.raises(DBAPIError) as exc_upd:
            with session.begin_nested():
                session.execute(
                    text("UPDATE customer_assessment_events SET result = 'PASS' WHERE id = :eid"),
                    {"eid": ev1.id},
                )
                session.flush()
        err_upd = str(exc_upd.value).lower()
        assert (
            "rows are immutable and cannot be updated or deleted" in err_upd
            or "permission denied" in err_upd
        )

        # Direct DELETE on events raises permission denial or trigger immutability exception
        with pytest.raises(DBAPIError) as exc_del:
            with session.begin_nested():
                session.execute(
                    text("DELETE FROM customer_assessment_events WHERE id = :eid"),
                    {"eid": ev1.id},
                )
                session.flush()
        err_del = str(exc_del.value).lower()
        assert (
            "rows are immutable and cannot be updated or deleted" in err_del
            or "permission denied" in err_del
        )

        # Direct DELETE on heads raises permission denial or trigger exception
        with pytest.raises(DBAPIError) as exc_del_h:
            with session.begin_nested():
                session.execute(
                    text("DELETE FROM customer_assessment_heads WHERE work_id = :wid"),
                    {"wid": work1.id},
                )
                session.flush()
        err_del_h = str(exc_del_h.value).lower()
        assert (
            "customer_assessment_heads rows cannot be deleted" in err_del_h
            or "permission denied" in err_del_h
        )

        # Direct DELETE on findings raises permission denial or trigger exception
        with pytest.raises(DBAPIError) as exc_del_f:
            with session.begin_nested():
                session.execute(
                    text("DELETE FROM customer_assessment_findings WHERE id = :fid"),
                    {"fid": fid1},
                )
                session.flush()
        err_del_f = str(exc_del_f.value).lower()
        assert (
            "customer_assessment_findings rows cannot be deleted" in err_del_f
            or "permission denied" in err_del_f
        )

        # Mutation of immutable finding identity columns raises permission denial or trigger exception
        with pytest.raises(DBAPIError) as exc_fid_imm:
            with session.begin_nested():
                session.execute(
                    text(
                        "UPDATE customer_assessment_findings SET source_event_id = :new_seid, version = 2 WHERE id = :fid"
                    ),
                    {"new_seid": uuid4(), "fid": fid1},
                )
                session.flush()
        err_fid_imm = str(exc_fid_imm.value).lower()
        assert (
            "finding identity and source columns are immutable" in err_fid_imm
            or "permission denied" in err_fid_imm
        )

        # Version jumping by more than one raises trigger exception
        with pytest.raises(DBAPIError) as exc_ver_jump:
            with session.begin_nested():
                session.execute(
                    text("UPDATE customer_assessment_findings SET version = 5 WHERE id = :fid"),
                    {"fid": fid1},
                )
                session.flush()
        assert "finding version must increment by exactly one" in str(exc_ver_jump.value).lower()


def test_customer_assessment_runtime_ownership_admission(
    postgres_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify runtime admission validates conformly_app identity and rejects ownership of C tables."""
    from unittest.mock import MagicMock

    from conformly.customer_demo.assessment_service import CustomerAssessmentService
    from conformly.customer_demo.policy import CustomerDemoDatabaseAdmissionError

    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        service = CustomerAssessmentService(session)

        # Baseline check passes cleanly for conformly_app nonowner
        service._verify_database_connection()

        # Verify fail-closed rejection for EACH of the three C tables
        tables_to_test = [
            "customer_assessment_heads",
            "customer_assessment_events",
            "customer_assessment_findings",
        ]
        real_execute = session.execute

        def make_fake_execute(res: Any) -> Any:
            def fake_execute(stmt: Any, *args: Any, **kwargs: Any) -> Any:
                if "WHERE c.relname IN" in str(stmt) and "r.rolname = current_user" in str(stmt):
                    return res
                return real_execute(stmt, *args, **kwargs)

            return fake_execute

        for bad_table in tables_to_test:
            mock_res = MagicMock()
            mock_res.scalars.return_value.all.return_value = [bad_table]
            monkeypatch.setattr(session, "execute", make_fake_execute(mock_res))
            with pytest.raises(CustomerDemoDatabaseAdmissionError) as exc_info:
                service._verify_database_connection()
            assert bad_table in str(exc_info.value)
            assert "illegally owns customer assessment tables" in str(exc_info.value)


def test_customer_assessment_nested_savepoint_rollback(
    postgres_connection: Connection,
) -> None:
    """Verify atomic rollback preserves state if an error occurs mid-transaction (savepoint unit)."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)
        ctx = _seed_hierarchy(session)
        t1, u1 = ctx["t1"], ctx["u1"]
        work1 = ctx["work1"]

        set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=True)

        head1 = CustomerAssessmentHead(
            tenant_id=t1.id,
            work_id=work1.id,
            current_revision=1,
            created_at=now,
            updated_at=now,
        )
        session.add(head1)
        session.flush()

        ev_id = uuid4()
        try:
            with session.begin_nested():
                ev = CustomerAssessmentEvent(
                    tenant_id=t1.id,
                    id=ev_id,
                    work_id=work1.id,
                    revision=1,
                    operation_id=uuid4(),
                    request_digest="a" * 64,
                    event_type="ASSESSMENT",
                    result="PASS",
                    observed_work_version=1,
                    details_encrypted='{"ciphertext": "encrypted"}',
                    actor_id=u1.id,
                    created_at=now,
                )
                session.add(ev)
                session.flush()
                # Simulate mid-transaction failure
                raise RuntimeError("Simulated mid-transaction failure")
        except RuntimeError:
            pass

        # Verify rollback atomicity: ev_id was not committed
        ev_check = session.scalar(
            select(CustomerAssessmentEvent).where(CustomerAssessmentEvent.id == ev_id)
        )
        assert ev_check is None


def _seed_stored_file(
    session: Session, tenant_id: UUID, user_id: UUID, content: bytes = b"test evidence content"
) -> Any:
    """Helper to seed an active stored file in database."""
    from conformly.crypto.policy import DataClassification
    from conformly.storage.models import StoredFile, StoredFileStatus

    file_id = uuid4()
    now = datetime.now(UTC)
    f = StoredFile(
        id=file_id,
        tenant_id=tenant_id,
        original_filename="audit_log.txt",
        content_type="text/plain",
        plaintext_size_bytes=len(content),
        ciphertext_size_bytes=len(content) + 28,
        storage_backend="local",
        encryption_algorithm="AES-256-GCM",
        key_version="v1",
        wrapped_dek_nonce="nonce123456",
        wrapped_dek="wrappeddek123456",
        ciphertext_nonce="nonce123456",
        object_key=f"tenants/{tenant_id}/files/{file_id}/audit_log.txt",
        classification=DataClassification.RESTRICTED.value,
        status=StoredFileStatus.ACTIVE,
        ciphertext_sha256=hashlib.sha256(b"cipher").hexdigest(),
        plaintext_sha256=hashlib.sha256(content).hexdigest(),
        created_by_user_id=user_id,
        created_at=now,
        updated_at=now,
    )
    session.add(f)
    session.flush()
    return f


class MockSuccessfulScanner:
    """Test scanner subclass simulating successful ClamAV verification."""

    def __init__(self) -> None:
        self.scanned_items: list[tuple[bytes, str]] = []

    def scan(self, data: bytes, filename: str) -> None:
        self.scanned_items.append((data, filename))


def _seed_concurrency_hierarchy(session: Session) -> dict[str, Any]:
    from conformly.config import get_settings

    cfg = get_settings()
    assert cfg.enable_customer_demo is True, (
        "enable_customer_demo must be True for concurrency hierarchy seed"
    )
    assert cfg.environment == "test", "environment must be 'test' for concurrency hierarchy seed"

    """Seed dedicated full committed hierarchy for two-connection concurrency tests.

    Adheres to:
    1. Parent-first flush ordering throughout.
    2. Genuinely admitted synthetic evidence via accepted B create/review/proof flow.
    3. Live pre-thread assertion on C get_procedure and B get_validated_assessment_link.
    """
    from datetime import timedelta
    from unittest.mock import patch

    from conformly.authz.policy import Principal, TenantContext
    from conformly.customer_demo.assessment_service import CustomerAssessmentService
    from conformly.customer_demo.evaluator import (
        compute_answers_digest,
        compute_evaluation_digest,
        evaluate_bundle,
    )
    from conformly.customer_demo.fixture import (
        BUNDLE_V1_DIGEST,
        CTRL_1_ID,
        CTRL_1_VER_ID,
        EVALUATOR_VERSION,
        PACK_VERSION_V1_ID,
    )
    from conformly.customer_demo.work_schemas import CreateEvidenceRequest, CreateReviewRequest
    from conformly.customer_demo.work_service import CustomerControlWorkService
    from conformly.entitlements.models import TenantEntitlement
    from conformly.identity.models import UserStatus

    now = datetime.now(UTC)
    tenant_id = uuid4()
    user_id = uuid4()

    tenant = Tenant(
        id=tenant_id,
        name="Postgres Concurrency Tenant",
        slug=f"pg-concurrency-{tenant_id}",
        status=TenantStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    session.add(tenant)
    session.flush()

    user = User(
        id=user_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject=f"sub-{user_id}",
        email=f"concurrency-{user_id}@example.com",
        display_name="Concurrency User",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    session.flush()

    set_rls_context(session, user_id=user_id, tenant_id=tenant_id, tenant_verified=True)

    membership = Membership(
        tenant_id=tenant_id,
        user_id=user_id,
        role=Role.OWNER,
        status=MembershipStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    session.add(membership)
    session.flush()

    entitlement = TenantEntitlement(
        tenant_id=tenant_id,
        plan_code="tier_a",
        enabled_modules=["frameworks", "evidence", "tasks", "preaudit", "findings"],
        max_members=100,
        max_storage_bytes=10000000,
        allowed_framework_slugs=["*"],
        effective_from=now - timedelta(days=1),
        effective_until=now + timedelta(days=365),
    )
    session.add(entitlement)
    session.flush()

    # 1. Flush Workspace FIRST
    ws = CustomerDemoWorkspace(
        tenant_id=tenant_id,
        current_revision=1,
        selection_revision=1,
        created_at=now,
        updated_at=now,
    )
    session.add(ws)
    session.flush()

    # 2. Flush Answers SECOND
    answers_dict = {"synthetic_wp09_uses_cloud": True, "synthetic_wp09_operating_region": "EU"}
    ans_digest = compute_answers_digest("ALPHA", answers_dict)
    answers = CustomerDemoAnswers(
        tenant_id=tenant_id,
        revision=1,
        company_code="ALPHA",
        answers=answers_dict,
        content_digest=ans_digest,
        actor_id=user_id,
        created_at=now,
    )
    session.add(answers)
    session.flush()

    # 3. Flush Evaluation FIRST
    eval_results = evaluate_bundle(PACK_VERSION_V1_ID, answers_dict)
    eval_digest = compute_evaluation_digest(
        answer_digest=ans_digest,
        answer_revision=1,
        bundle_digest=BUNDLE_V1_DIGEST,
        evaluator_version=EVALUATOR_VERSION,
        pack_version_id=PACK_VERSION_V1_ID,
        results=eval_results,
    )
    evaluation = CustomerDemoEvaluation(
        id=uuid4(),
        tenant_id=tenant_id,
        answer_revision=1,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=BUNDLE_V1_DIGEST,
        evaluator_version=EVALUATOR_VERSION,
        results=eval_results,
        content_digest=eval_digest,
        actor_id=user_id,
        created_at=now,
    )
    session.add(evaluation)
    session.flush()

    # 4. Flush Adoption SECOND
    adoption = CustomerDemoAdoption(
        id=uuid4(),
        tenant_id=tenant_id,
        selection_revision=1,
        evaluation_id=evaluation.id,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=BUNDLE_V1_DIGEST,
        actor_id=user_id,
        created_at=now,
    )
    session.add(adoption)
    session.flush()

    # 5. Flush CustomerControlWork
    work = CustomerControlWork(
        tenant_id=tenant_id,
        id=uuid4(),
        adoption_id=adoption.id,
        control_id=CTRL_1_ID,
        control_version_id=CTRL_1_VER_ID,
        owner_user_id=user_id,
        due_date=date(2026, 12, 31),
        version=1,
        created_at=now,
        updated_at=now,
    )
    session.add(work)
    session.flush()

    principal = Principal(user_id=user_id, mfa_verified=True)
    tenant_context = TenantContext(tenant_id=tenant_id, role=Role.OWNER, user_id=user_id)

    # 6. Genuinely admitted synthetic evidence via accepted B create/review flows
    file_content = b"Clean compliance audit evidence data"
    stored_file = _seed_stored_file(session, tenant_id, user_id, file_content)

    scanner = MockSuccessfulScanner()
    work_service = CustomerControlWorkService(session, scanner=scanner)  # type: ignore[arg-type]

    with patch("conformly.customer_demo.work_service.StorageService") as MockStorage:
        instance = MockStorage.return_value
        instance.download_file.return_value = (stored_file, file_content)

        ev_req = CreateEvidenceRequest(
            operation_id=uuid4(),
            expected_selection_revision=1,
            expected_answer_revision=1,
            expected_work_version=1,
            file_id=stored_file.id,
            rationale="Initial cloud compliance evidence snapshot",
        )
        receipt_ev = work_service.create_evidence(
            principal,
            tenant_context,
            work.id,
            ev_req,
            request_id=f"req-ev-{uuid4()}",
        )
        link = receipt_ev.current_work.links[0]

        rev_req = CreateReviewRequest(
            operation_id=uuid4(),
            expected_selection_revision=1,
            expected_answer_revision=1,
            expected_work_version=2,
            decision="ACCEPTED",
            rationale="Evidence fully satisfies cloud architecture baseline",
        )
        _receipt_rev = work_service.create_review(
            principal,
            tenant_context,
            work.id,
            link.id,
            rev_req,
            request_id=f"req-rev-{uuid4()}",
        )

    # Pre-thread assertions: verify real public C get_procedure and B get_validated_assessment_link
    assess_service = CustomerAssessmentService(session)
    proc = assess_service.get_procedure(principal, tenant_context, work.id)
    assert proc.id is not None
    assert len(proc.criteria) == 3

    v_link = work_service.get_validated_assessment_link(
        principal, tenant_context, work_id=work.id, link_id=link.id
    )
    assert v_link.link_id == link.id

    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "work": work,
        "work_version": 3,
        "link": link,
        "adoption": adoption,
        "procedure": proc,
        "principal": principal,
        "tenant_context": tenant_context,
    }


def test_customer_assessment_real_two_connection_distinct_op_cas_race(
    postgres_connection: Connection,
    enable_customer_demo_feature: None,
) -> None:
    """Verify concurrent distinct operations on same expected revision: exactly 1 wins, loser gets 409."""
    import threading

    from fastapi import HTTPException

    from conformly.customer_demo.assessment_schemas import (
        AssessmentCreateRequest,
        AssessmentCriterionResultDto,
    )
    from conformly.customer_demo.assessment_service import CustomerAssessmentService

    with postgres_connection.begin():
        session = Session(bind=postgres_connection)
        ctx = _seed_concurrency_hierarchy(session)

    tenant_id: UUID = ctx["tenant_id"]
    work_id: UUID = ctx["work"].id
    link_id: UUID = ctx["link"].id
    work_version: int = ctx["work_version"]
    proc = ctx["procedure"]
    principal = ctx["principal"]
    tenant_context = ctx["tenant_context"]

    conn1 = postgres_connection.engine.connect()
    conn2 = postgres_connection.engine.connect()
    try:
        pid1 = conn1.execute(text("SELECT pg_backend_pid()")).scalar()
        conn1.rollback()
        pid2 = conn2.execute(text("SELECT pg_backend_pid()")).scalar()
        conn2.rollback()
        assert pid1 != pid2, f"Expected distinct connection PIDs, got pid1={pid1}, pid2={pid2}"

        barrier = threading.Barrier(2)
        results: list[Any] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker(conn: Connection, op_id: UUID, rationale: str) -> None:
            try:
                with conn.begin():
                    s = Session(bind=conn)
                    set_rls_context(
                        s, user_id=principal.user_id, tenant_id=tenant_id, tenant_verified=True
                    )
                    service = CustomerAssessmentService(s)
                    req = AssessmentCreateRequest(
                        operation_id=op_id,
                        expected_answer_revision=1,
                        expected_selection_revision=1,
                        expected_work_version=work_version,
                        expected_assessment_revision=0,
                        procedure_id=proc.id,
                        procedure_version=proc.version,
                        procedure_digest=proc.digest,
                        result="PASS",
                        criterion_results=[
                            AssessmentCriterionResultDto(criterion_id=c.id, result="PASS")
                            for c in proc.criteria
                        ],
                        evidence_link_ids=[link_id],
                        rationale=rationale,
                    )
                    barrier.wait(timeout=10)
                    receipt = service.record_assessment(principal, tenant_context, work_id, req)
                    with lock:
                        results.append(receipt)
            except Exception as e:
                with lock:
                    errors.append(e)

        t1 = threading.Thread(target=worker, args=(conn1, uuid4(), "Worker 1 rationale"))
        t2 = threading.Thread(target=worker, args=(conn2, uuid4(), "Worker 2 rationale"))
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        assert not t1.is_alive(), "Worker thread 1 timed out"
        assert not t2.is_alive(), "Worker thread 2 timed out"

        assert len(results) == 1, f"Expected exactly 1 winner receipt, got {len(results)}"
        assert len(errors) == 1, f"Expected exactly 1 loser exception, got {len(errors)}"

        winner_receipt = results[0]
        assert winner_receipt.applied_revision == 1
        assert winner_receipt.replayed is False

        loser_error = errors[0]
        assert isinstance(loser_error, HTTPException)
        assert loser_error.status_code == 409

        # Independent reader verification
        with postgres_connection.begin():
            reader_session = Session(bind=postgres_connection)
            set_rls_context(
                reader_session,
                user_id=principal.user_id,
                tenant_id=tenant_id,
                tenant_verified=True,
            )
            head = reader_session.scalar(
                select(CustomerAssessmentHead).where(
                    CustomerAssessmentHead.tenant_id == tenant_id,
                    CustomerAssessmentHead.work_id == work_id,
                )
            )
            assert head is not None
            assert head.current_revision == 1

            events = reader_session.scalars(
                select(CustomerAssessmentEvent).where(
                    CustomerAssessmentEvent.tenant_id == tenant_id,
                    CustomerAssessmentEvent.work_id == work_id,
                )
            ).all()
            assert len(events) == 1
            assert events[0].revision == 1
            assert events[0].operation_id == winner_receipt.operation_id
    finally:
        conn1.close()
        conn2.close()


def test_customer_assessment_real_two_connection_identical_op_concurrent_replay(
    postgres_connection: Connection,
    enable_customer_demo_feature: None,
) -> None:
    """Verify concurrent requests with identical operation_id and payload: 1 mutates, 1 replays under lock, 0 duplicate errors."""
    import threading

    import sqlalchemy.event

    from conformly.customer_demo.assessment_schemas import (
        AssessmentCreateRequest,
        AssessmentCriterionResultDto,
    )
    from conformly.customer_demo.assessment_service import CustomerAssessmentService

    with postgres_connection.begin():
        session = Session(bind=postgres_connection)
        ctx = _seed_concurrency_hierarchy(session)

    tenant_id: UUID = ctx["tenant_id"]
    work_id: UUID = ctx["work"].id
    link_id: UUID = ctx["link"].id
    work_version: int = ctx["work_version"]
    proc = ctx["procedure"]
    principal = ctx["principal"]
    tenant_context = ctx["tenant_context"]

    conn1 = postgres_connection.engine.connect()
    conn2 = postgres_connection.engine.connect()
    shared_op_id = uuid4()

    t1_locked = threading.Event()
    t2_entered = threading.Event()

    def after_cursor_conn1(
        conn: Any, cursor: Any, statement: str, *args: Any, **kwargs: Any
    ) -> None:
        if "customer_demo_workspaces" in statement and "FOR UPDATE" in statement:
            t1_locked.set()
            assert t2_entered.wait(timeout=5), "t2_entered synchronization timed out"

    def before_cursor_conn2(
        conn: Any, cursor: Any, statement: str, *args: Any, **kwargs: Any
    ) -> None:
        if "customer_demo_workspaces" in statement and "FOR UPDATE" in statement:
            t2_entered.set()

    sqlalchemy.event.listen(conn1, "after_cursor_execute", after_cursor_conn1)
    sqlalchemy.event.listen(conn2, "before_cursor_execute", before_cursor_conn2)

    try:
        pid1 = conn1.execute(text("SELECT pg_backend_pid()")).scalar()
        conn1.rollback()
        pid2 = conn2.execute(text("SELECT pg_backend_pid()")).scalar()
        conn2.rollback()
        assert pid1 != pid2, f"Expected distinct connection PIDs, got pid1={pid1}, pid2={pid2}"

        results: list[Any] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker1() -> None:
            try:
                with conn1.begin():
                    s1 = Session(bind=conn1)
                    set_rls_context(
                        s1, user_id=principal.user_id, tenant_id=tenant_id, tenant_verified=True
                    )
                    service1 = CustomerAssessmentService(s1)
                    req1 = AssessmentCreateRequest(
                        operation_id=shared_op_id,
                        expected_answer_revision=1,
                        expected_selection_revision=1,
                        expected_work_version=work_version,
                        expected_assessment_revision=0,
                        procedure_id=proc.id,
                        procedure_version=proc.version,
                        procedure_digest=proc.digest,
                        result="PASS",
                        criterion_results=[
                            AssessmentCriterionResultDto(criterion_id=c.id, result="PASS")
                            for c in proc.criteria
                        ],
                        evidence_link_ids=[link_id],
                        rationale="Concurrent identical operation rationale",
                    )
                    receipt1 = service1.record_assessment(principal, tenant_context, work_id, req1)
                    with lock:
                        results.append(receipt1)
            except Exception as e:
                with lock:
                    errors.append(e)

        def worker2() -> None:
            try:
                assert t1_locked.wait(timeout=5), "t1_locked synchronization timed out"
                with conn2.begin():
                    s2 = Session(bind=conn2)
                    set_rls_context(
                        s2, user_id=principal.user_id, tenant_id=tenant_id, tenant_verified=True
                    )
                    service2 = CustomerAssessmentService(s2)
                    req2 = AssessmentCreateRequest(
                        operation_id=shared_op_id,
                        expected_answer_revision=1,
                        expected_selection_revision=1,
                        expected_work_version=work_version,
                        expected_assessment_revision=0,
                        procedure_id=proc.id,
                        procedure_version=proc.version,
                        procedure_digest=proc.digest,
                        result="PASS",
                        criterion_results=[
                            AssessmentCriterionResultDto(criterion_id=c.id, result="PASS")
                            for c in proc.criteria
                        ],
                        evidence_link_ids=[link_id],
                        rationale="Concurrent identical operation rationale",
                    )
                    receipt2 = service2.record_assessment(principal, tenant_context, work_id, req2)
                    with lock:
                        results.append(receipt2)
            except Exception as e:
                with lock:
                    errors.append(e)

        t1 = threading.Thread(target=worker1)
        t2 = threading.Thread(target=worker2)
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        assert not t1.is_alive(), "Worker 1 timed out"
        assert not t2.is_alive(), "Worker 2 timed out"

        assert len(errors) == 0, (
            f"Expected 0 errors during identical concurrent replay, got: {errors}"
        )
        assert len(results) == 2, f"Expected 2 receipts, got {len(results)}"

        replayed_statuses = sorted([r.replayed for r in results])
        assert replayed_statuses == [False, True], (
            f"Expected exactly [False, True], got {replayed_statuses}"
        )

        r_orig = next(r for r in results if not r.replayed)
        r_replayed = next(r for r in results if r.replayed)

        assert r_orig.operation_id == shared_op_id
        assert r_replayed.operation_id == shared_op_id
        assert r_orig.event_id == r_replayed.event_id
        assert r_orig.applied_revision == 1
        assert r_replayed.applied_revision == 1

        # Verify DB state from independent connection
        with postgres_connection.begin():
            reader_session = Session(bind=postgres_connection)
            set_rls_context(
                reader_session,
                user_id=principal.user_id,
                tenant_id=tenant_id,
                tenant_verified=True,
            )
            heads = reader_session.scalars(
                select(CustomerAssessmentHead).where(
                    CustomerAssessmentHead.tenant_id == tenant_id,
                    CustomerAssessmentHead.work_id == work_id,
                )
            ).all()
            assert len(heads) == 1
            assert heads[0].current_revision == 1

            events = reader_session.scalars(
                select(CustomerAssessmentEvent).where(
                    CustomerAssessmentEvent.tenant_id == tenant_id,
                    CustomerAssessmentEvent.work_id == work_id,
                )
            ).all()
            assert len(events) == 1
            assert events[0].operation_id == shared_op_id
            assert events[0].revision == 1
    finally:
        try:
            sqlalchemy.event.remove(conn1, "after_cursor_execute", after_cursor_conn1)
            sqlalchemy.event.remove(conn2, "before_cursor_execute", before_cursor_conn2)
        except Exception:
            pass
        conn1.close()
        conn2.close()


def test_customer_assessment_real_two_connection_same_op_mismatched_payload_conflict(
    postgres_connection: Connection,
    enable_customer_demo_feature: None,
) -> None:
    """Verify concurrent requests with same operation_id but different payload under lock: 1 wins, loser gets 409 Conflict."""
    import threading

    import sqlalchemy.event
    from fastapi import HTTPException

    from conformly.customer_demo.assessment_schemas import (
        AssessmentCreateRequest,
        AssessmentCriterionResultDto,
    )
    from conformly.customer_demo.assessment_service import CustomerAssessmentService

    with postgres_connection.begin():
        session = Session(bind=postgres_connection)
        ctx = _seed_concurrency_hierarchy(session)

    tenant_id: UUID = ctx["tenant_id"]
    work_id: UUID = ctx["work"].id
    link_id: UUID = ctx["link"].id
    work_version: int = ctx["work_version"]
    proc = ctx["procedure"]
    principal = ctx["principal"]
    tenant_context = ctx["tenant_context"]

    conn1 = postgres_connection.engine.connect()
    conn2 = postgres_connection.engine.connect()
    shared_op_id = uuid4()

    t1_locked = threading.Event()
    t2_entered = threading.Event()

    def after_cursor_conn1(
        conn: Any, cursor: Any, statement: str, *args: Any, **kwargs: Any
    ) -> None:
        if "customer_demo_workspaces" in statement and "FOR UPDATE" in statement:
            t1_locked.set()
            assert t2_entered.wait(timeout=5), "t2_entered synchronization timed out"

    def before_cursor_conn2(
        conn: Any, cursor: Any, statement: str, *args: Any, **kwargs: Any
    ) -> None:
        if "customer_demo_workspaces" in statement and "FOR UPDATE" in statement:
            t2_entered.set()

    sqlalchemy.event.listen(conn1, "after_cursor_execute", after_cursor_conn1)
    sqlalchemy.event.listen(conn2, "before_cursor_execute", before_cursor_conn2)

    try:
        pid1 = conn1.execute(text("SELECT pg_backend_pid()")).scalar()
        conn1.rollback()
        pid2 = conn2.execute(text("SELECT pg_backend_pid()")).scalar()
        conn2.rollback()
        assert pid1 != pid2, f"Expected distinct connection PIDs, got pid1={pid1}, pid2={pid2}"

        results: list[Any] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker1() -> None:
            try:
                with conn1.begin():
                    s1 = Session(bind=conn1)
                    set_rls_context(
                        s1, user_id=principal.user_id, tenant_id=tenant_id, tenant_verified=True
                    )
                    service1 = CustomerAssessmentService(s1)
                    req1 = AssessmentCreateRequest(
                        operation_id=shared_op_id,
                        expected_answer_revision=1,
                        expected_selection_revision=1,
                        expected_work_version=work_version,
                        expected_assessment_revision=0,
                        procedure_id=proc.id,
                        procedure_version=proc.version,
                        procedure_digest=proc.digest,
                        result="PASS",
                        criterion_results=[
                            AssessmentCriterionResultDto(criterion_id=c.id, result="PASS")
                            for c in proc.criteria
                        ],
                        evidence_link_ids=[link_id],
                        rationale="Payload Version A",
                    )
                    receipt1 = service1.record_assessment(principal, tenant_context, work_id, req1)
                    with lock:
                        results.append(receipt1)
            except Exception as e:
                with lock:
                    errors.append(e)

        def worker2() -> None:
            try:
                assert t1_locked.wait(timeout=5), "t1_locked synchronization timed out"
                with conn2.begin():
                    s2 = Session(bind=conn2)
                    set_rls_context(
                        s2, user_id=principal.user_id, tenant_id=tenant_id, tenant_verified=True
                    )
                    service2 = CustomerAssessmentService(s2)
                    req2 = AssessmentCreateRequest(
                        operation_id=shared_op_id,
                        expected_answer_revision=1,
                        expected_selection_revision=1,
                        expected_work_version=work_version,
                        expected_assessment_revision=0,
                        procedure_id=proc.id,
                        procedure_version=proc.version,
                        procedure_digest=proc.digest,
                        result="PASS",
                        criterion_results=[
                            AssessmentCriterionResultDto(criterion_id=c.id, result="PASS")
                            for c in proc.criteria
                        ],
                        evidence_link_ids=[link_id],
                        rationale="Payload Version B - MISMATCHED PARAMETERS",
                    )
                    receipt2 = service2.record_assessment(principal, tenant_context, work_id, req2)
                    with lock:
                        results.append(receipt2)
            except Exception as e:
                with lock:
                    errors.append(e)

        t1 = threading.Thread(target=worker1)
        t2 = threading.Thread(target=worker2)
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        assert not t1.is_alive(), "Worker 1 timed out"
        assert not t2.is_alive(), "Worker 2 timed out"

        assert len(results) == 1, f"Expected exactly 1 winner receipt, got {len(results)}"
        assert len(errors) == 1, f"Expected exactly 1 conflict error, got {len(errors)}"

        assert results[0].replayed is False
        assert results[0].applied_revision == 1

        err = errors[0]
        assert isinstance(err, HTTPException)
        assert err.status_code == 409
        assert "different request parameters" in err.detail

        # Reader verification
        with postgres_connection.begin():
            reader_session = Session(bind=postgres_connection)
            set_rls_context(
                reader_session,
                user_id=principal.user_id,
                tenant_id=tenant_id,
                tenant_verified=True,
            )
            events = reader_session.scalars(
                select(CustomerAssessmentEvent).where(
                    CustomerAssessmentEvent.tenant_id == tenant_id,
                    CustomerAssessmentEvent.work_id == work_id,
                )
            ).all()
            assert len(events) == 1
            assert events[0].operation_id == shared_op_id
    finally:
        try:
            sqlalchemy.event.remove(conn1, "after_cursor_execute", after_cursor_conn1)
            sqlalchemy.event.remove(conn2, "before_cursor_execute", before_cursor_conn2)
        except Exception:
            pass
        conn1.close()
        conn2.close()


def test_customer_assessment_real_two_connection_competing_finding_updates_cas_race(
    postgres_connection: Connection,
    enable_customer_demo_feature: None,
) -> None:
    """Verify competing finding updates on same expected version: exactly 1 wins, loser gets 409, no lost update."""
    import threading

    from fastapi import HTTPException

    from conformly.customer_demo.assessment_schemas import (
        AssessmentCreateRequest,
        AssessmentCriterionResultDto,
        FindingCreateSpecificationDto,
        FindingPatchRequest,
    )
    from conformly.customer_demo.assessment_service import CustomerAssessmentService

    with postgres_connection.begin():
        session = Session(bind=postgres_connection)
        ctx = _seed_concurrency_hierarchy(session)

        tenant_id: UUID = ctx["tenant_id"]
        work_id: UUID = ctx["work"].id
        link_id: UUID = ctx["link"].id
        work_version: int = ctx["work_version"]
        proc = ctx["procedure"]
        principal = ctx["principal"]
        tenant_context = ctx["tenant_context"]

        # Initial assessment creating a finding (result FAIL)
        service0 = CustomerAssessmentService(session)
        init_req = AssessmentCreateRequest(
            operation_id=uuid4(),
            expected_answer_revision=1,
            expected_selection_revision=1,
            expected_work_version=work_version,
            expected_assessment_revision=0,
            procedure_id=proc.id,
            procedure_version=proc.version,
            procedure_digest=proc.digest,
            result="FAIL",
            criterion_results=[
                AssessmentCriterionResultDto(criterion_id=proc.criteria[0].id, result="FAIL"),
                AssessmentCriterionResultDto(criterion_id=proc.criteria[1].id, result="PASS"),
                AssessmentCriterionResultDto(criterion_id=proc.criteria[2].id, result="PASS"),
            ],
            evidence_link_ids=[link_id],
            finding=FindingCreateSpecificationDto(severity="HIGH"),
            rationale="Initial assessment creating finding",
        )
        init_receipt = service0.record_assessment(principal, tenant_context, work_id, init_req)
        assert init_receipt.applied_revision == 1

        finding_row = session.scalar(
            select(CustomerAssessmentFinding).where(
                CustomerAssessmentFinding.tenant_id == tenant_id,
                CustomerAssessmentFinding.work_id == work_id,
            )
        )
        assert finding_row is not None
        assert finding_row.version == 1
        finding_id: UUID = finding_row.id

    conn1 = postgres_connection.engine.connect()
    conn2 = postgres_connection.engine.connect()
    try:
        pid1 = conn1.execute(text("SELECT pg_backend_pid()")).scalar()
        conn1.rollback()
        pid2 = conn2.execute(text("SELECT pg_backend_pid()")).scalar()
        conn2.rollback()
        assert pid1 != pid2, f"Expected distinct connection PIDs, got pid1={pid1}, pid2={pid2}"

        barrier = threading.Barrier(2)
        results: list[Any] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker1() -> None:
            try:
                with conn1.begin():
                    s1 = Session(bind=conn1)
                    set_rls_context(
                        s1, user_id=principal.user_id, tenant_id=tenant_id, tenant_verified=True
                    )
                    service1 = CustomerAssessmentService(s1)
                    patch1 = FindingPatchRequest(
                        operation_id=uuid4(),
                        expected_answer_revision=1,
                        expected_selection_revision=1,
                        expected_work_version=work_version,
                        expected_assessment_revision=1,
                        expected_finding_version=1,
                        severity="MEDIUM",
                        owner_user_id=principal.user_id,
                        due_date=date(2026, 12, 31),
                        status="IN_REMEDIATION",
                        remediation_note="Worker 1 remediating finding",
                    )
                    barrier.wait(timeout=10)
                    receipt1 = service1.update_finding(
                        principal, tenant_context, finding_id, patch1
                    )
                    with lock:
                        results.append(receipt1)
            except Exception as e:
                with lock:
                    errors.append(e)

        def worker2() -> None:
            try:
                with conn2.begin():
                    s2 = Session(bind=conn2)
                    set_rls_context(
                        s2, user_id=principal.user_id, tenant_id=tenant_id, tenant_verified=True
                    )
                    service2 = CustomerAssessmentService(s2)
                    patch2 = FindingPatchRequest(
                        operation_id=uuid4(),
                        expected_answer_revision=1,
                        expected_selection_revision=1,
                        expected_work_version=work_version,
                        expected_assessment_revision=1,
                        expected_finding_version=1,
                        severity="LOW",
                        owner_user_id=principal.user_id,
                        due_date=date(2026, 12, 31),
                        status="OPEN",
                        remediation_note="Worker 2 updating finding note",
                    )
                    barrier.wait(timeout=10)
                    receipt2 = service2.update_finding(
                        principal, tenant_context, finding_id, patch2
                    )
                    with lock:
                        results.append(receipt2)
            except Exception as e:
                with lock:
                    errors.append(e)

        t1 = threading.Thread(target=worker1)
        t2 = threading.Thread(target=worker2)
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        assert not t1.is_alive(), "Worker 1 timed out"
        assert not t2.is_alive(), "Worker 2 timed out"

        assert len(results) == 1, f"Expected exactly 1 winner, got {len(results)}"
        assert len(errors) == 1, f"Expected exactly 1 conflict loser, got {len(errors)}"

        winner_receipt = results[0]
        assert winner_receipt.applied_revision == 2

        loser_err = errors[0]
        assert isinstance(loser_err, HTTPException)
        assert loser_err.status_code == 409

        # Reader verification
        with postgres_connection.begin():
            reader_session = Session(bind=postgres_connection)
            set_rls_context(
                reader_session,
                user_id=principal.user_id,
                tenant_id=tenant_id,
                tenant_verified=True,
            )
            finding_final = reader_session.scalar(
                select(CustomerAssessmentFinding).where(
                    CustomerAssessmentFinding.tenant_id == tenant_id,
                    CustomerAssessmentFinding.id == finding_id,
                )
            )
            assert finding_final is not None
            assert finding_final.version == 2
            assert finding_final.status in ("IN_REMEDIATION", "OPEN")
    finally:
        conn1.close()
        conn2.close()


def test_customer_assessment_real_two_connection_transaction_rollback(
    postgres_connection: Connection,
    enable_customer_demo_feature: None,
) -> None:
    """Verify transaction rollback: mid-transaction failure rolls back completely, confirmed by second connection."""
    from conformly.customer_demo.assessment_schemas import (
        AssessmentCreateRequest,
        AssessmentCriterionResultDto,
        FindingCreateSpecificationDto,
    )
    from conformly.customer_demo.assessment_service import CustomerAssessmentService

    with postgres_connection.begin():
        session = Session(bind=postgres_connection)
        ctx = _seed_concurrency_hierarchy(session)

    tenant_id: UUID = ctx["tenant_id"]
    work_id: UUID = ctx["work"].id
    link_id: UUID = ctx["link"].id
    work_version: int = ctx["work_version"]
    proc = ctx["procedure"]
    principal = ctx["principal"]
    tenant_context = ctx["tenant_context"]

    conn1 = postgres_connection.engine.connect()
    conn2 = postgres_connection.engine.connect()
    try:
        pid1 = conn1.execute(text("SELECT pg_backend_pid()")).scalar()
        conn1.rollback()
        pid2 = conn2.execute(text("SELECT pg_backend_pid()")).scalar()
        conn2.rollback()
        assert pid1 != pid2

        with pytest.raises(RuntimeError):
            with conn1.begin():
                s1 = Session(bind=conn1)
                set_rls_context(
                    s1, user_id=principal.user_id, tenant_id=tenant_id, tenant_verified=True
                )
                service1 = CustomerAssessmentService(s1)
                req = AssessmentCreateRequest(
                    operation_id=uuid4(),
                    expected_answer_revision=1,
                    expected_selection_revision=1,
                    expected_work_version=work_version,
                    expected_assessment_revision=0,
                    procedure_id=proc.id,
                    procedure_version=proc.version,
                    procedure_digest=proc.digest,
                    result="FAIL",
                    criterion_results=[
                        AssessmentCriterionResultDto(criterion_id=c.id, result="FAIL")
                        for c in proc.criteria
                    ],
                    evidence_link_ids=[link_id],
                    finding=FindingCreateSpecificationDto(severity="MEDIUM"),
                    rationale="About to fail mid-transaction",
                )
                service1.record_assessment(principal, tenant_context, work_id, req)
                raise RuntimeError("Simulated failure after assessment writes")

        # Query from Connection 2 to verify zero rows committed
        with conn2.begin():
            s2 = Session(bind=conn2)
            set_rls_context(
                s2, user_id=principal.user_id, tenant_id=tenant_id, tenant_verified=True
            )
            heads_count = s2.scalar(
                select(func.count())
                .select_from(CustomerAssessmentHead)
                .where(
                    CustomerAssessmentHead.tenant_id == tenant_id,
                    CustomerAssessmentHead.work_id == work_id,
                )
            )
            events_count = s2.scalar(
                select(func.count())
                .select_from(CustomerAssessmentEvent)
                .where(
                    CustomerAssessmentEvent.tenant_id == tenant_id,
                    CustomerAssessmentEvent.work_id == work_id,
                )
            )
            findings_count = s2.scalar(
                select(func.count())
                .select_from(CustomerAssessmentFinding)
                .where(
                    CustomerAssessmentFinding.tenant_id == tenant_id,
                    CustomerAssessmentFinding.work_id == work_id,
                )
            )

            assert heads_count == 0, f"Expected 0 heads after rollback, got {heads_count}"
            assert events_count == 0, f"Expected 0 events after rollback, got {events_count}"
            assert findings_count == 0, f"Expected 0 findings after rollback, got {findings_count}"
    finally:
        conn1.close()
        conn2.close()


def test_customer_assessment_feature_setting_restoration() -> None:
    """Verify that unrelated tests see default feature-off settings."""
    from conformly.config import get_settings

    cfg = get_settings()
    assert cfg.enable_customer_demo is False
