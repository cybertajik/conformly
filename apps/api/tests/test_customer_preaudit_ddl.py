"""Offline DDL and Alembic migration safety tests for Customer Pre-audit (MVP-D).

Asserts offline SQL rendering, RLS policies, role grants, triggers,
foreign keys, and SQLite memory metadata compatibility without executing
against live PostgreSQL databases.
"""

from __future__ import annotations

import io
import os
from contextlib import redirect_stdout
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from conformly.db.base import Base
import conformly.customer_demo.preaudit_models as preaudit_models


def test_migration_revision_identifiers():
    import importlib.util

    migration_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "migrations",
        "versions",
        "20261101_0048_customer_preaudit.py",
    )
    spec = importlib.util.spec_from_file_location("migration_0048", migration_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.revision == "20261101_0048"
    assert mod.down_revision == "20261025_0047"
    assert hasattr(mod, "upgrade")
    assert hasattr(mod, "downgrade")


def test_offline_alembic_ddl_generation():
    import importlib.util
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "migrations",
        "versions",
        "20261101_0048_customer_preaudit.py",
    )
    spec = importlib.util.spec_from_file_location("migration_0048", migration_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    buf = io.StringIO()
    ctx = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": buf, "literal_binds": True},
    )
    with Operations.context(ctx):
        mod.upgrade()

    sql = buf.getvalue()

    # Tables
    assert "CREATE TABLE customer_preaudits" in sql
    assert "CREATE TABLE customer_preaudit_snapshots" in sql
    assert "CREATE TABLE customer_preaudit_events" in sql

    # RLS & Force RLS
    assert "ALTER TABLE customer_preaudits ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE customer_preaudits FORCE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE customer_preaudit_snapshots ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE customer_preaudit_snapshots FORCE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE customer_preaudit_events ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE customer_preaudit_events FORCE ROW LEVEL SECURITY" in sql

    # Policies
    assert "wp09d_customer_preaudits" in sql
    assert "wp09d_customer_preaudit_snapshots" in sql
    assert "wp09d_customer_preaudit_events" in sql

    # Grants
    assert 'GRANT SELECT, INSERT ON public.customer_preaudits TO "conformly_app"' in sql
    assert 'GRANT UPDATE (status, revision, current_scope_snapshot_id, current_review_snapshot_id, updated_at) ON public.customer_preaudits TO "conformly_app"' in sql
    assert 'GRANT SELECT, INSERT ON public.customer_preaudit_snapshots TO "conformly_app"' in sql
    assert 'GRANT SELECT, INSERT ON public.customer_preaudit_events TO "conformly_app"' in sql

    # Triggers
    assert "trg_customer_preaudit_snapshots_immutable" in sql
    assert "trg_customer_preaudit_events_immutable" in sql
    assert "trg_customer_preaudits_protect" in sql


def test_sqlite_in_memory_metadata_creation():
    from datetime import UTC, datetime
    from sqlalchemy import event
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
    import conformly.identity.models as identity_models
    import conformly.customer_demo.models as demo_models

    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_con, con_record):
        cur = dbapi_con.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "customer_preaudits" in tables
    assert "customer_preaudit_snapshots" in tables
    assert "customer_preaudit_events" in tables

    # Check columns on customer_preaudits
    columns = {c["name"]: c for c in inspector.get_columns("customer_preaudits")}
    assert "tenant_id" in columns
    assert "id" in columns
    assert "adoption_id" in columns
    assert "lead_user_id" in columns
    assert "reviewer_user_id" in columns
    assert "status" in columns
    assert "revision" in columns
    assert "current_scope_snapshot_id" in columns
    assert "current_review_snapshot_id" in columns

    # Foreign key enforcement tests in SQLite
    with Session(engine) as session:
        now = datetime.now(UTC)
        t_id = uuid4()
        u1_id = uuid4()
        u2_id = uuid4()
        adopt_id = uuid4()
        eval_id = uuid4()
        pack_vid = uuid4()

        # 1. Negative test: Inserting preaudit without parent tenant/users/adoption fails
        orphan_case = preaudit_models.CustomerPreaudit(
            tenant_id=t_id,
            id=uuid4(),
            adoption_id=adopt_id,
            lead_user_id=u2_id,
            reviewer_user_id=u1_id,
            status="DRAFT",
            revision=1,
        )
        session.add(orphan_case)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # Seed valid parent chain
        tenant = identity_models.Tenant(id=t_id, name="T", slug="t", status="ACTIVE", created_at=now, updated_at=now)
        session.add(tenant)
        u1 = identity_models.User(id=u1_id, oidc_issuer="iss", oidc_subject="sub1", email="u1@e.com", display_name="User 1", status="ACTIVE", created_at=now, updated_at=now)
        u2 = identity_models.User(id=u2_id, oidc_issuer="iss", oidc_subject="sub2", email="u2@e.com", display_name="User 2", status="ACTIVE", created_at=now, updated_at=now)
        session.add_all([u1, u2])
        session.flush()

        m1 = identity_models.Membership(tenant_id=t_id, user_id=u1_id, role="OWNER", status="ACTIVE", created_at=now, updated_at=now)
        m2 = identity_models.Membership(tenant_id=t_id, user_id=u2_id, role="COMPLIANCE_MANAGER", status="ACTIVE", created_at=now, updated_at=now)
        session.add_all([m1, m2])
        ws = demo_models.CustomerDemoWorkspace(tenant_id=t_id, current_revision=1, selection_revision=1, created_at=now, updated_at=now)
        session.add(ws)
        session.flush()

        ans = demo_models.CustomerDemoAnswers(tenant_id=t_id, revision=1, company_code="ALPHA", answers={}, content_digest="0"*64, actor_id=u1_id, created_at=now)
        session.add(ans)
        session.flush()

        ev = demo_models.CustomerDemoEvaluation(
            tenant_id=t_id, id=eval_id, answer_revision=1, pack_version_id=pack_vid,
            bundle_digest="0"*64, evaluator_version="v1", results=[], content_digest="0"*64,
            actor_id=u1_id, created_at=now
        )
        session.add(ev)
        session.flush()

        adopt = demo_models.CustomerDemoAdoption(
            tenant_id=t_id, id=adopt_id, evaluation_id=eval_id, pack_version_id=pack_vid,
            bundle_digest="0"*64, actor_id=u1_id, created_at=now, selection_revision=1
        )
        session.add(adopt)
        session.commit()

        # Create two valid cases
        case1_id = uuid4()
        case2_id = uuid4()
        case1 = preaudit_models.CustomerPreaudit(tenant_id=t_id, id=case1_id, adoption_id=adopt_id, lead_user_id=u2_id, reviewer_user_id=u1_id, status="DRAFT", revision=1)
        case2 = preaudit_models.CustomerPreaudit(tenant_id=t_id, id=case2_id, adoption_id=adopt_id, lead_user_id=u2_id, reviewer_user_id=u1_id, status="DRAFT", revision=1)
        session.add_all([case1, case2])
        session.commit()

        # Create snapshot for case1
        snap1_id = uuid4()
        snap1 = preaudit_models.CustomerPreauditSnapshot(
            tenant_id=t_id, id=snap1_id, preaudit_id=case1_id, kind="SCOPE", sequence=1,
            digest="a"*64, payload_encrypted={"k": "v"}, created_by_user_id=u2_id, created_at=now
        )
        session.add(snap1)
        session.commit()

        # 2. Negative test: Cross-case snapshot reference must be rejected by composite FK constraint
        bad_event = preaudit_models.CustomerPreauditEvent(
            tenant_id=t_id, id=uuid4(), preaudit_id=case2_id, revision=1, operation_id=uuid4(),
            request_digest="b"*64, event_type="SCOPE_FROZEN", actor_user_id=u2_id,
            snapshot_id=snap1_id, prior_status="DRAFT", new_status="FROZEN",
            payload_encrypted={"k": "v"}, created_at=now
        )
        session.add(bad_event)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # 3. Positive test: Same-case snapshot reference succeeds
        good_event = preaudit_models.CustomerPreauditEvent(
            tenant_id=t_id, id=uuid4(), preaudit_id=case1_id, revision=1, operation_id=uuid4(),
            request_digest="b"*64, event_type="SCOPE_FROZEN", actor_user_id=u2_id,
            snapshot_id=snap1_id, prior_status="DRAFT", new_status="FROZEN",
            payload_encrypted={"k": "v"}, created_at=now
        )
        session.add(good_event)
        session.commit()
