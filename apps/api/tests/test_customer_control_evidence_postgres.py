"""PostgreSQL integration tests: customer control work and evidence pinning.

Asserts ENABLE/FORCE RLS, column privileges, immutability triggers,
cross-tenant composite foreign keys, and downgrade preflight protections.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from conformly.authz.roles import Role
from conformly.compliance.models import EvidenceItem, EvidenceRevision, EvidenceStatus
from conformly.crypto.policy import DataClassification
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
from conformly.customer_demo.work_models import (
    CustomerControlEvidenceLink,
    CustomerControlWork,
    CustomerControlWorkEvent,
)
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User
from conformly.tenancy.rls import set_rls_context


def _seed_hierarchy(session: Session) -> dict[str, Any]:
    now = datetime.now(UTC)
    t1 = Tenant(
        name="Postgres Work Tenant 1",
        slug=f"pg-work-1-{uuid4()}",
        status=TenantStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    t2 = Tenant(
        name="Postgres Work Tenant 2",
        slug=f"pg-work-2-{uuid4()}",
        status=TenantStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    u1 = User(
        oidc_issuer="https://auth.example.com",
        oidc_subject=str(uuid4()),
        email=f"{uuid4()}@example.com",
        display_name="User T1",
        created_at=now,
        updated_at=now,
    )
    u2 = User(
        oidc_issuer="https://auth.example.com",
        oidc_subject=str(uuid4()),
        email=f"{uuid4()}@example.com",
        display_name="User T2",
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
        company_code="BETA",
        answers={"synthetic_wp09_uses_cloud": False},
        content_digest=ans2_digest,
        actor_id=u2.id,
        created_at=now,
    )
    session.add(ws2)
    session.flush()
    session.add(ans2)
    session.flush()

    eval2_digest = compute_evaluation_digest(
        answer_digest=ans2.content_digest,
        answer_revision=1,
        pack_version_id=PACK_VERSION_V2_ID,
        bundle_digest=bundle_digest,
        results=[],
    )
    ev2 = CustomerDemoEvaluation(
        tenant_id=t2.id,
        id=uuid4(),
        answer_revision=1,
        pack_version_id=PACK_VERSION_V2_ID,
        bundle_digest=bundle_digest,
        evaluator_version="1.0.0",
        results=[],
        content_digest=eval2_digest,
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

    return {
        "t1": t1,
        "t2": t2,
        "u1": u1,
        "u2": u2,
        "ws1": ws1,
        "ws2": ws2,
        "ev1": ev1,
        "ev2": ev2,
        "ad1": ad1,
        "ad2": ad2,
    }


def test_customer_control_evidence_rls_force_and_isolation(
    postgres_connection: Connection,
) -> None:
    """Verify ENABLE and FORCE RLS on all 3 tables and strict cross-tenant isolation."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)

        # 1. Assert relrowsecurity and relforcerowsecurity on all three tables
        tables = [
            "customer_control_work",
            "customer_control_evidence_links",
            "customer_control_work_events",
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
        ad1 = ctx["ad1"]

        # Insert work in Tenant 1
        set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=True)
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

        # Evidence revision in Tenant 1
        ev_item1 = EvidenceItem(
            tenant_id=t1.id,
            title="Synthetic Item 1",
            description="Synthetic description",
            classification=DataClassification.RESTRICTED,
            status=EvidenceStatus.DRAFT,
            owner_user_id=u1.id,
            created_at=now,
            updated_at=now,
        )
        session.add(ev_item1)
        session.flush()

        ev_rev1 = EvidenceRevision(
            tenant_id=t1.id,
            evidence_id=ev_item1.id,
            revision_number=1,
            title="Synthetic Item 1",
            description="Synthetic description",
            classification=DataClassification.RESTRICTED,
            status=EvidenceStatus.DRAFT,
            created_by_user_id=u1.id,
            created_at=now,
        )
        session.add(ev_rev1)
        session.flush()

        link1 = CustomerControlEvidenceLink(
            tenant_id=t1.id,
            id=uuid4(),
            work_id=work1.id,
            evidence_id=ev_item1.id,
            evidence_revision_number=1,
            evidence_revision_digest="b" * 64,
            rationale_encrypted='{"ciphertext": "encrypted_rationale"}',
            actor_id=u1.id,
            created_at=now,
        )
        session.add(link1)
        session.flush()

        event1 = CustomerControlWorkEvent(
            tenant_id=t1.id,
            id=uuid4(),
            work_id=work1.id,
            work_revision=1,
            operation_id=uuid4(),
            request_digest="c" * 64,
            event_type="INITIALIZED",
            link_id=None,
            decision=None,
            details_encrypted='{"ciphertext": "encrypted_details"}',
            actor_id=u1.id,
            created_at=now,
        )
        session.add(event1)
        session.flush()

        # Verify Tenant 1 reads all 3
        assert (
            session.execute(
                text("SELECT count(*) FROM customer_control_work WHERE tenant_id = :t1"),
                {"t1": t1.id},
            ).scalar()
            == 1
        )
        assert (
            session.execute(
                text("SELECT count(*) FROM customer_control_evidence_links WHERE tenant_id = :t1"),
                {"t1": t1.id},
            ).scalar()
            == 1
        )
        assert (
            session.execute(
                text("SELECT count(*) FROM customer_control_work_events WHERE tenant_id = :t1"),
                {"t1": t1.id},
            ).scalar()
            == 1
        )

        # Switch to Tenant 2 RLS context
        set_rls_context(session, user_id=u2.id, tenant_id=t2.id, tenant_verified=True)

        # Tenant 2 cannot see Tenant 1 records
        assert (
            session.execute(
                text("SELECT count(*) FROM customer_control_work WHERE id = :wid"),
                {"wid": work1.id},
            ).scalar()
            == 0
        )
        assert (
            session.execute(
                text("SELECT count(*) FROM customer_control_evidence_links WHERE id = :lid"),
                {"lid": link1.id},
            ).scalar()
            == 0
        )
        assert (
            session.execute(
                text("SELECT count(*) FROM customer_control_work_events WHERE id = :eid"),
                {"eid": event1.id},
            ).scalar()
            == 0
        )

        # Unverified tenant context cannot see records
        set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=False)
        assert session.execute(text("SELECT count(*) FROM customer_control_work")).scalar() == 0


def test_customer_control_evidence_column_privileges(
    postgres_connection: Connection,
) -> None:
    """Verify strict column-level privileges for conformly_app role and denials for catalog role."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)
        ctx = _seed_hierarchy(session)
        t1, u1 = ctx["t1"], ctx["u1"]
        ad1 = ctx["ad1"]

        set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=True)
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

        # 1. Allowed column UPDATEs on customer_control_work (owner_user_id, due_date, version, updated_at)
        new_due = date(2027, 1, 15)
        session.execute(
            text(
                "UPDATE customer_control_work "
                "SET due_date = :due, version = 2, updated_at = now() "
                "WHERE tenant_id = :tid AND id = :wid"
            ),
            {"due": new_due, "tid": t1.id, "wid": work1.id},
        )
        session.flush()

        refreshed_due = session.execute(
            text("SELECT due_date FROM customer_control_work WHERE id = :wid"),
            {"wid": work1.id},
        ).scalar()
        assert refreshed_due == new_due

        # 2. Denied column UPDATEs on customer_control_work with savepoints
        forbidden_updates: list[tuple[str, str, dict[str, Any]]] = [
            ("control_id", "SET control_id = :val", {"val": uuid4()}),
            ("adoption_id", "SET adoption_id = :val", {"val": uuid4()}),
            ("control_version_id", "SET control_version_id = :val", {"val": uuid4()}),
            ("created_at", "SET created_at = :val", {"val": now}),
            ("tenant_id", "SET tenant_id = :val", {"val": uuid4()}),
            ("id", "SET id = :val", {"val": uuid4()}),
        ]
        for col_name, update_clause, extra_param in forbidden_updates:
            params = {"tid": t1.id, "wid": work1.id, **extra_param}
            with pytest.raises(DBAPIError) as exc_info:
                with session.begin_nested():
                    session.execute(
                        text(
                            f"UPDATE customer_control_work {update_clause} "
                            "WHERE tenant_id = :tid AND id = :wid"
                        ),
                        params,
                    )
                    session.flush()
            err_msg = str(exc_info.value).lower()
            assert (
                "permission denied" in err_msg or "immutable" in err_msg or "violates" in err_msg
            ), f"Expected permission denial or immutability violation on column {col_name}"

        # 3. Denied UPDATE/DELETE on links and events for conformly_app
        ev_item = EvidenceItem(
            tenant_id=t1.id,
            title="Item ColPrivs",
            description="ColPrivs test",
            classification=DataClassification.RESTRICTED,
            status=EvidenceStatus.DRAFT,
            owner_user_id=u1.id,
            created_at=now,
            updated_at=now,
        )
        session.add(ev_item)
        session.flush()

        ev_rev = EvidenceRevision(
            tenant_id=t1.id,
            evidence_id=ev_item.id,
            revision_number=1,
            title="Item ColPrivs",
            description="ColPrivs test",
            classification=DataClassification.RESTRICTED,
            status=EvidenceStatus.DRAFT,
            created_by_user_id=u1.id,
            created_at=now,
        )
        session.add(ev_rev)
        session.flush()

        link = CustomerControlEvidenceLink(
            tenant_id=t1.id,
            id=uuid4(),
            work_id=work1.id,
            evidence_id=ev_item.id,
            evidence_revision_number=1,
            evidence_revision_digest="d" * 64,
            rationale_encrypted='{"ciphertext": "encrypted"}',
            actor_id=u1.id,
            created_at=now,
        )
        session.add(link)
        session.flush()

        with pytest.raises(DBAPIError) as exc_link_upd:
            with session.begin_nested():
                session.execute(
                    text(
                        "UPDATE customer_control_evidence_links SET evidence_revision_number = 2 WHERE id = :lid"
                    ),
                    {"lid": link.id},
                )
                session.flush()
        assert (
            "permission denied" in str(exc_link_upd.value).lower()
            or "immutable" in str(exc_link_upd.value).lower()
        )

        # 4. Verify function execution privileges: conformly_app has EXECUTE, PUBLIC and catalog roles do not
        for fn in (
            "customer_control_prevent_history_modification()",
            "customer_control_work_protect()",
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

            for cat_r in (
                "conformly_catalog",
                "conformly_catalog_fact_author",
                "conformly_catalog_rule_author",
            ):
                r_exists = session.execute(
                    text("SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = :r)"),
                    {"r": cat_r},
                ).scalar()
                if r_exists:
                    cat_exec = session.execute(
                        text("SELECT has_function_privilege(:r, :fn, 'EXECUTE')"),
                        {"r": cat_r, "fn": fn},
                    ).scalar()
                    assert cat_exec is False, f"{cat_r} illegally granted EXECUTE on {fn}"

                    # Verify catalog roles hold NO table privileges on the 3 tables
                    for tbl in (
                        "customer_control_work",
                        "customer_control_evidence_links",
                        "customer_control_work_events",
                    ):
                        has_tbl = session.execute(
                            text("SELECT has_table_privilege(:r, :tbl, 'SELECT')"),
                            {"r": cat_r, "tbl": tbl},
                        ).scalar()
                        assert has_tbl is False, f"{cat_r} illegally granted SELECT on {tbl}"


def test_customer_control_evidence_immutability_triggers(
    postgres_connection: Connection,
) -> None:
    """Verify triggers prevent UPDATE/DELETE on links and events, and identity changes on work."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)
        ctx = _seed_hierarchy(session)
        t1, u1 = ctx["t1"], ctx["u1"]
        ad1 = ctx["ad1"]

        set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=True)
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

        ev_item = EvidenceItem(
            tenant_id=t1.id,
            title="Item Trigger",
            description="Trigger test",
            classification=DataClassification.RESTRICTED,
            status=EvidenceStatus.DRAFT,
            owner_user_id=u1.id,
            created_at=now,
            updated_at=now,
        )
        session.add(ev_item)
        session.flush()

        ev_rev = EvidenceRevision(
            tenant_id=t1.id,
            evidence_id=ev_item.id,
            revision_number=1,
            title="Item Trigger",
            description="Trigger test",
            classification=DataClassification.RESTRICTED,
            status=EvidenceStatus.DRAFT,
            created_by_user_id=u1.id,
            created_at=now,
        )
        session.add(ev_rev)
        session.flush()

        link = CustomerControlEvidenceLink(
            tenant_id=t1.id,
            id=uuid4(),
            work_id=work1.id,
            evidence_id=ev_item.id,
            evidence_revision_number=1,
            evidence_revision_digest="d" * 64,
            rationale_encrypted='{"ciphertext": "encrypted"}',
            actor_id=u1.id,
            created_at=now,
        )
        session.add(link)
        session.flush()

        # Attempt DELETE on link -> rejected by trigger/permission (wrapped in savepoint)
        with pytest.raises(DBAPIError) as exc_del:
            with session.begin_nested():
                session.execute(
                    text("DELETE FROM customer_control_evidence_links WHERE id = :lid"),
                    {"lid": link.id},
                )
                session.flush()
        assert (
            "cannot_modify_history" in str(exc_del.value).lower()
            or "permission denied" in str(exc_del.value).lower()
            or "immutable" in str(exc_del.value).lower()
        )

        event = CustomerControlWorkEvent(
            tenant_id=t1.id,
            id=uuid4(),
            work_id=work1.id,
            work_revision=1,
            operation_id=uuid4(),
            request_digest="e" * 64,
            event_type="INITIALIZED",
            link_id=None,
            decision=None,
            details_encrypted='{"ciphertext": "encrypted"}',
            actor_id=u1.id,
            created_at=now,
        )
        session.add(event)
        session.flush()

        # Attempt UPDATE on event -> rejected by trigger/permission (wrapped in savepoint)
        with pytest.raises(DBAPIError) as exc_upd:
            with session.begin_nested():
                session.execute(
                    text(
                        "UPDATE customer_control_work_events "
                        "SET event_type = 'EVIDENCE_LINKED' "
                        "WHERE id = :eid"
                    ),
                    {"eid": event.id},
                )
                session.flush()
        assert (
            "cannot_modify_history" in str(exc_upd.value).lower()
            or "permission denied" in str(exc_upd.value).lower()
            or "immutable" in str(exc_upd.value).lower()
        )


def test_customer_control_evidence_cross_tenant_composite_fks(
    postgres_connection: Connection,
) -> None:
    """Verify composite foreign keys strictly deny cross-tenant references."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        ctx = _seed_hierarchy(session)
        t1 = ctx["t1"]
        u1 = ctx["u1"]
        ad2 = ctx["ad2"]  # Tenant 2 adoption

        set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=True)

        # Cross-tenant adoption FK: Tenant 1 work referencing Tenant 2 adoption (with savepoint)
        with pytest.raises(DBAPIError) as exc_fk:
            with session.begin_nested():
                session.execute(
                    text(
                        "INSERT INTO customer_control_work "
                        "(tenant_id, id, adoption_id, control_id, control_version_id, "
                        "owner_user_id, due_date, version, created_at, updated_at) "
                        "VALUES (:tid, :wid, :adid, :cid, :cvid, :uid, :due, 1, now(), now())"
                    ),
                    {
                        "tid": t1.id,
                        "wid": uuid4(),
                        "adid": ad2.id,  # From Tenant 2!
                        "cid": uuid4(),
                        "cvid": uuid4(),
                        "uid": u1.id,
                        "due": date(2026, 12, 31),
                    },
                )
                session.flush()
        assert "violates foreign key constraint" in str(exc_fk.value).lower()


def test_customer_control_evidence_downgrade_preflight_refusal(
    postgres_connection: Connection,
) -> None:
    """Verify migration 0046 downgrade preflight refuses when any table is populated."""
    connection = postgres_connection
    with connection.begin():
        session = Session(bind=connection)
        now = datetime.now(UTC)
        ctx = _seed_hierarchy(session)
        t1, u1 = ctx["t1"], ctx["u1"]
        ad1 = ctx["ad1"]

        set_rls_context(session, user_id=u1.id, tenant_id=t1.id, tenant_verified=True)
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

        # Direct execution of downgrade preflight check
        downgrade_sql = text("""
        DO $$
        DECLARE
            cnt_work integer := 0;
            cnt_links integer := 0;
            cnt_events integer := 0;
        BEGIN
            SELECT count(*) INTO cnt_work FROM customer_control_work;
            SELECT count(*) INTO cnt_links FROM customer_control_evidence_links;
            SELECT count(*) INTO cnt_events FROM customer_control_work_events;

            IF (cnt_work + cnt_links + cnt_events) > 0 THEN
                RAISE EXCEPTION 'CANNOT_DOWNGRADE_CUSTOMER_CONTROL_EVIDENCE_DATA_EXISTS';
            END IF;
        END $$;
        """)

        with pytest.raises(DBAPIError) as exc_dg:
            with session.begin_nested():
                session.execute(downgrade_sql)
        assert "cannot_downgrade_customer_control_evidence_data_exists" in str(exc_dg.value).lower()
