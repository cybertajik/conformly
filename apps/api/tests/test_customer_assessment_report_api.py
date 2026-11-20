from __future__ import annotations

import hashlib
import json
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from conformly.audit.models import AuditEvent
from conformly.auth.dependencies import get_current_principal
from conformly.authz.policy import Principal
from conformly.authz.roles import Role
from conformly.customer_demo.assessment_report_archive import verify_report_archive
from conformly.customer_demo.models import CustomerDemoWorkspace
from tests import test_customer_assessment_api as fixtures

enable_demo_env = fixtures.enable_demo_env
env_fixture = fixtures.env_fixture
test_app = fixtures.test_app


@pytest.fixture
def report_client(test_app: FastAPI, env_fixture):
    fixtures._set_auth(test_app, env_fixture["owner_id"], env_fixture["tenant_id"], Role.OWNER)
    with TestClient(test_app, raise_server_exceptions=False) as client:
        yield client


def path(env):
    return f"/v2/tenants/{env['tenant_id']}/customer-demo/assessment-reports/download"


def body(env):
    return {
        "adoption_id": str(env["work"].adoption_id),
        "expected_answer_revision": 1,
        "expected_selection_revision": 1,
    }


def events(session):
    return list(
        session.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "customer_assessment.report_download_prepared"
            )
        ).all()
    )


def test_download_commits_safe_audit_and_returns_matching_archive(
    report_client, env_fixture, session
):
    response = report_client.post(path(env_fixture), json=body(env_fixture))
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="conformly-assessment-report.zip"'
    )
    assert "private" in response.headers["cache-control"]
    assert "no-store" in response.headers["cache-control"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-report-tenant-id"] == str(env_fixture["tenant_id"])
    assert response.headers["x-report-sha256"] == hashlib.sha256(response.content).hexdigest()
    bundle = verify_report_archive(
        response.content,
        tenant_id=env_fixture["tenant_id"],
        adoption_id=env_fixture["work"].adoption_id,
    )
    audit = events(session)
    assert len(audit) == 1
    assert audit[0].safe_metadata["sha256"] == response.headers["x-report-sha256"]
    assert (
        audit[0].safe_metadata["manifest_hash"] == hashlib.sha256(bundle.manifest_json).hexdigest()
    )
    assert audit[0].actor_id == env_fixture["owner_id"]
    assert set(audit[0].safe_metadata) == {
        "adoption_id",
        "report_type",
        "sha256",
        "manifest_hash",
        "size_bytes",
        "files_count",
    }
    assert b"rationale" not in bundle.report_json
    session.rollback()  # event has already been committed, not waiting on request cleanup
    assert len(events(session)) == 1


@pytest.mark.parametrize(
    "case", ["revision", "selection", "adoption", "extra", "boolean", "string", "negative"]
)
def test_scope_and_shape_errors_return_no_artifact_or_success_audit(
    report_client, env_fixture, session, case
):
    payload = body(env_fixture)
    expected = 409
    if case == "revision":
        payload["expected_answer_revision"] = 99
    elif case == "selection":
        payload["expected_selection_revision"] = 99
    elif case == "adoption":
        payload["adoption_id"] = str(uuid4())
    else:
        expected = 422
        if case == "extra":
            payload["captured_at"] = "2000-01-01"
        else:
            payload["expected_answer_revision"] = {"boolean": True, "string": "1", "negative": -1}[
                case
            ]
    response = report_client.post(path(env_fixture), json=payload)
    assert response.status_code == expected
    assert "no-store" in response.headers["cache-control"]
    assert "content-disposition" not in response.headers
    assert not response.content.startswith(b"PK")
    assert not events(session)


@pytest.mark.parametrize("denial", ["route_tenant", "role", "mfa", "unauthenticated"])
def test_denials_are_private_and_audit_no_success(
    report_client, test_app, env_fixture, session, denial
):
    url = path(env_fixture)
    if denial == "route_tenant":
        url = url.replace(str(env_fixture["tenant_id"]), str(uuid4()))
    elif denial == "role":
        fixtures._set_auth(
            test_app, env_fixture["owner_id"], env_fixture["tenant_id"], Role.EMPLOYEE
        )
    elif denial == "mfa":
        test_app.dependency_overrides[get_current_principal] = lambda: Principal(
            user_id=env_fixture["owner_id"], mfa_verified=False
        )
    else:

        def reject():
            raise HTTPException(status_code=401, detail="PRIVATE-CLIENT-SECRET")

        test_app.dependency_overrides[get_current_principal] = reject
    response = report_client.post(url, json=body(env_fixture))
    assert response.status_code == (401 if denial == "unauthenticated" else 403)
    assert "no-store" in response.headers["cache-control"]
    assert "PRIVATE-CLIENT-SECRET" not in response.text
    assert not events(session)


def test_failed_audit_commit_rolls_back_and_never_releases_bytes(
    report_client, env_fixture, session
):
    with patch.object(session, "commit", side_effect=SQLAlchemyError("PRIVATE-DB-SECRET")):
        response = report_client.post(path(env_fixture), json=body(env_fixture))
    assert response.status_code == 503
    assert "PRIVATE-DB-SECRET" not in response.text
    assert "no-store" in response.headers["cache-control"]
    assert "content-disposition" not in response.headers
    assert not events(session)


def test_failed_audit_record_never_returns_download(report_client, env_fixture, session):
    with patch(
        "conformly.customer_demo.assessment_report_api.record_audit_event",
        side_effect=SQLAlchemyError("PRIVATE-DB-SECRET"),
    ):
        response = report_client.post(path(env_fixture), json=body(env_fixture))
    assert response.status_code == 503
    assert "PRIVATE-DB-SECRET" not in response.text
    assert not events(session)


def test_updated_workspace_revision_requires_explicit_refresh(report_client, env_fixture, session):
    workspace = session.scalar(
        select(CustomerDemoWorkspace).where(
            CustomerDemoWorkspace.tenant_id == env_fixture["tenant_id"]
        )
    )
    workspace.current_revision = 2
    session.commit()
    response = report_client.post(path(env_fixture), json=body(env_fixture))
    assert response.status_code == 409
    assert not events(session)


def test_body_limit_and_no_get_download(report_client, env_fixture, session):
    response = report_client.post(path(env_fixture), content=b"x" * (16 * 1024 + 1))
    assert response.status_code == 413
    assert "no-store" in response.headers["cache-control"]
    assert report_client.get(path(env_fixture)).status_code == 405
    assert not events(session)


def test_each_explicit_request_prepares_and_audits_a_new_capture(
    report_client, env_fixture, session
):
    first = report_client.post(path(env_fixture), json=body(env_fixture))
    second = report_client.post(path(env_fixture), json=body(env_fixture))
    assert first.status_code == second.status_code == 200
    assert len(events(session)) == 2
    assert first.headers["x-correlation-id"] != second.headers["x-correlation-id"]
    assert (
        json.loads(
            verify_report_archive(
                second.content,
                tenant_id=env_fixture["tenant_id"],
                adoption_id=env_fixture["work"].adoption_id,
            ).report_json
        )["purpose"]
        == "SYNTHETIC_INTERNAL_OPERATIONAL_SNAPSHOT"
    )
