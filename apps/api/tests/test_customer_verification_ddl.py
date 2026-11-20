"""Offline DDL and Alembic migration safety tests for Customer Readiness Verification (MVP-E).

Asserts offline SQL rendering, RLS policies, role grants, triggers,
foreign keys, and SQLite memory metadata compatibility without executing
against live PostgreSQL databases.
"""

from __future__ import annotations

import io
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import conformly.customer_demo.verification_models as verification_models
from conformly.customer_demo.models import CustomerDemoAdoption
from conformly.customer_demo.preaudit_models import CustomerPreaudit, CustomerPreauditSnapshot
from conformly.customer_demo.verification_models import CustomerReadinessVerification
from conformly.db.base import Base


def test_migration_revision_identifiers():
    import importlib.util

    migration_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "migrations",
        "versions",
        "20261102_0049_customer_verification.py",
    )
    spec = importlib.util.spec_from_file_location("migration_0049", migration_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.revision == "20261102_0049"
    assert mod.down_revision == "20261101_0048"
    assert hasattr(mod, "upgrade")
    assert hasattr(mod, "downgrade")


def test_offline_alembic_ddl_generation():
    import importlib.util

    migration_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "migrations",
        "versions",
        "20261102_0049_customer_verification.py",
    )
    spec = importlib.util.spec_from_file_location("migration_0049", migration_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Use a dummy PostgreSQL engine for offline SQL generation
    pg_engine = create_engine("postgresql+psycopg://user:pass@localhost/dummy")
    buf = io.StringIO()

    ctx = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": buf},
    )

    with Operations.context(ctx):
        mod.upgrade()

    sql_output = buf.getvalue().lower()

    # Verify expected tables, constraints, functions, triggers, and RLS policies in generated DDL
    assert "create table customer_readiness_verifications" in sql_output
    assert "create table customer_readiness_verification_events" in sql_output
    assert "ck_customer_verifications_rev_pos" in sql_output
    assert "ck_customer_verifications_status" in sql_output
    assert "ck_customer_verifications_validity_order" in sql_output
    assert "uq_customer_verifications_snapshot" in sql_output
    assert "uq_customer_verification_events_op" in sql_output
    assert "uq_customer_verification_events_seq" in sql_output
    assert "fk_customer_verifications_snapshot" in sql_output
    assert "customer_preaudit_snapshots" in sql_output
    assert "enable row level security" in sql_output
    assert "force row level security" in sql_output
    assert "customer_verifications_protect" in sql_output
    assert "customer_verification_events_immutable" in sql_output
    assert "grant select, insert on customer_readiness_verifications" in sql_output
    assert "grant update (status, revision, current_event_id, superseded_by_id, updated_at)" in sql_output


def test_sqlite_in_memory_metadata_creation():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    insp = inspect(engine)
    table_names = insp.get_table_names()
    assert "customer_readiness_verifications" in table_names
    assert "customer_readiness_verification_events" in table_names

    cols = {c["name"] for c in insp.get_columns("customer_readiness_verifications")}
    assert "tenant_id" in cols
    assert "id" in cols
    assert "preaudit_id" in cols
    assert "snapshot_id" in cols
    assert "status" in cols
    assert "revision" in cols
    assert "issued_at" in cols
    assert "valid_through" in cols
    assert "payload_encrypted" in cols
    assert "digest" in cols
    assert "superseded_by_id" in cols
    assert "supersedes_id" in cols


def test_sqlite_foreign_key_samecase_negative_insert():
    """Enforce negative insert with SQLite foreign_keys=ON: snapshot from a different case rejected."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    t_id = uuid4()
    u_lead = uuid4()
    u_rev = uuid4()
    now = datetime.now(UTC)

    from conformly.authz.roles import Role
    from conformly.customer_demo.models import CustomerDemoAnswers, CustomerDemoEvaluation, CustomerDemoWorkspace
    from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User, UserStatus

    tenant = Tenant(id=t_id, name="Test Tenant", slug="test-tenant", status=TenantStatus.ACTIVE, created_at=now, updated_at=now)
    user_lead = User(id=u_lead, oidc_issuer="iss", oidc_subject="sub1", email="lead@example.com", display_name="Lead", status=UserStatus.ACTIVE, created_at=now, updated_at=now)
    user_rev = User(id=u_rev, oidc_issuer="iss", oidc_subject="sub2", email="rev@example.com", display_name="Rev", status=UserStatus.ACTIVE, created_at=now, updated_at=now)
    m_lead = Membership(tenant_id=t_id, user_id=u_lead, role=Role.OWNER, status=MembershipStatus.ACTIVE, created_at=now, updated_at=now)
    m_rev = Membership(tenant_id=t_id, user_id=u_rev, role=Role.COMPLIANCE_MANAGER, status=MembershipStatus.ACTIVE, created_at=now, updated_at=now)
    ws = CustomerDemoWorkspace(tenant_id=t_id, current_revision=1, selection_revision=1, created_at=now, updated_at=now)
    ans = CustomerDemoAnswers(tenant_id=t_id, revision=1, company_code="ALPHA", answers={}, content_digest="a" * 64, actor_id=u_lead, created_at=now)
    eval_id = uuid4()
    eval_obj = CustomerDemoEvaluation(
        tenant_id=t_id,
        id=eval_id,
        answer_revision=1,
        pack_version_id=uuid4(),
        bundle_digest="b" * 64,
        evaluator_version="1.0",
        results=[],
        content_digest="d" * 64,
        actor_id=u_lead,
        created_at=now,
    )

    # Seed adoption
    adopt = CustomerDemoAdoption(
        tenant_id=t_id,
        id=uuid4(),
        actor_id=u_lead,
        pack_version_id=uuid4(),
        bundle_digest="a" * 64,
        evaluation_id=eval_id,
        selection_revision=1,
        created_at=now,
    )
    for item in [tenant, user_lead, user_rev, m_lead, m_rev, ws, ans, eval_obj, adopt]:
        session.add(item)
        session.flush()

    # Seed case A and snapshot A1
    case_a = CustomerPreaudit(
        tenant_id=t_id,
        id=uuid4(),
        adoption_id=adopt.id,
        status="APPROVED",
        revision=1,
        lead_user_id=u_lead,
        reviewer_user_id=u_rev,
    )
    session.add(case_a)
    session.flush()

    snap_a1 = CustomerPreauditSnapshot(
        tenant_id=t_id,
        id=uuid4(),
        preaudit_id=case_a.id,
        kind="REVIEW",
        sequence=1,
        digest="b" * 64,
        payload_encrypted={"kind": "review"},
        created_by_user_id=u_rev,
    )
    session.add(snap_a1)

    # Seed case B and snapshot B1
    case_b = CustomerPreaudit(
        tenant_id=t_id,
        id=uuid4(),
        adoption_id=adopt.id,
        status="APPROVED",
        revision=1,
        lead_user_id=u_lead,
        reviewer_user_id=u_rev,
    )
    session.add(case_b)
    session.flush()

    snap_b1 = CustomerPreauditSnapshot(
        tenant_id=t_id,
        id=uuid4(),
        preaudit_id=case_b.id,
        kind="REVIEW",
        sequence=1,
        digest="c" * 64,
        payload_encrypted={"kind": "review"},
        created_by_user_id=u_rev,
    )
    session.add(snap_b1)
    session.commit()

    # Negative check: Insert verification for case A but referencing snapshot B1 (belonging to case B)
    # Must fail with IntegrityError due to composite FK (tenant_id, preaudit_id, snapshot_id)
    bad_v = CustomerReadinessVerification(
        tenant_id=t_id,
        id=uuid4(),
        preaudit_id=case_a.id,
        snapshot_id=snap_b1.id,  # Snapshot from Case B!
        status="ACTIVE",
        revision=1,
        issued_at=now,
        valid_through=now,
        payload_encrypted={"marker": "test"},
        digest="d" * 64,
    )
    session.add(bad_v)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    # Positive check: Insert verification for case A with snapshot A1 (same case)
    good_v = CustomerReadinessVerification(
        tenant_id=t_id,
        id=uuid4(),
        preaudit_id=case_a.id,
        snapshot_id=snap_a1.id,
        status="ACTIVE",
        revision=1,
        issued_at=now,
        valid_through=now,
        payload_encrypted={"marker": "test"},
        digest="e" * 64,
    )
    session.add(good_v)
    session.commit()
    assert good_v.id is not None
    session.close()


def test_downgrade_guard_raises_on_existing_data():
    import importlib.util

    migration_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "migrations",
        "versions",
        "20261102_0049_customer_verification.py",
    )
    spec = importlib.util.spec_from_file_location("migration_0049", migration_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()
    t_id = uuid4()
    v_id = uuid4()
    p_id = uuid4()
    s_id = uuid4()

    now = datetime.now(UTC)
    v = CustomerReadinessVerification(
        tenant_id=t_id,
        id=v_id,
        preaudit_id=p_id,
        snapshot_id=s_id,
        status="ACTIVE",
        revision=1,
        issued_at=now,
        valid_through=now,
        payload_encrypted={"data": "test"},
        digest="0" * 64,
    )
    session.add(v)
    session.commit()
    session.close()

    ctx = MigrationContext.configure(connection=engine.connect())
    with Operations.context(ctx):
        with pytest.raises(RuntimeError, match="CANNOT_DOWNGRADE_CUSTOMER_VERIFICATION_DATA_EXISTS"):
            mod.downgrade()
