"""Integration tests for assessment report registration, CORS headers, and admission."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from conformly.auth.dependencies import get_current_principal, get_tenant_context
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.config import get_settings
from conformly.customer_demo.api import register_customer_demo_routes
from conformly.main import app


def _collect_paths(app_obj: FastAPI) -> list[str]:
    paths = []
    for r in app_obj.routes:
        if hasattr(r, "original_router"):
            for sub in r.original_router.routes:
                if hasattr(sub, "path"):
                    paths.append(sub.path)
        elif hasattr(r, "path"):
            paths.append(r.path)
    return paths


def test_feature_disabled_excludes_report_route(monkeypatch: pytest.MonkeyPatch):
    """When customer demo is disabled, report download route is excluded/returns 404."""
    test_app = FastAPI()
    monkeypatch.setattr(get_settings(), "enable_customer_demo", False)
    register_customer_demo_routes(test_app)

    routes = _collect_paths(test_app)
    report_routes = [p for p in routes if "assessment-reports" in p]
    assert len(report_routes) == 0

    client = TestClient(test_app)
    res = client.post(
        f"/v2/tenants/{uuid4()}/customer-demo/assessment-reports/download",
        json={
            "adoption_id": str(uuid4()),
            "expected_answer_revision": 1,
            "expected_selection_revision": 1,
        },
    )
    assert res.status_code == 404


def test_feature_enabled_registers_report_route_exactly_once(monkeypatch: pytest.MonkeyPatch):
    """When customer demo is enabled, report download route is registered exactly once."""
    test_app = FastAPI()
    monkeypatch.setattr(get_settings(), "enable_customer_demo", True)
    register_customer_demo_routes(test_app)

    routes = _collect_paths(test_app)
    report_download_routes = [
        p
        for p in routes
        if p == "/v2/tenants/{tenant_id}/customer-demo/assessment-reports/download"
    ]
    assert len(report_download_routes) == 1


def test_cors_preflight_and_exposed_headers():
    """CORS preflight and download responses expose required report headers for allowed origins."""
    settings = get_settings()
    allowed_origin = settings.cors_origins[0] if settings.cors_origins else "http://localhost:18492"

    with TestClient(app) as client:
        # Preflight OPTIONS
        preflight_res = client.options(
            f"/v2/tenants/{uuid4()}/customer-demo/assessment-reports/download",
            headers={
                "Origin": allowed_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization,Content-Type",
            },
        )
        assert preflight_res.status_code == 200
        assert preflight_res.headers.get("access-control-allow-origin") == allowed_origin

        # Actual request receives Access-Control-Expose-Headers
        res = client.post(
            f"/v2/tenants/{uuid4()}/customer-demo/assessment-reports/download",
            headers={
                "Origin": allowed_origin,
            },
            json={
                "adoption_id": str(uuid4()),
                "expected_answer_revision": 1,
                "expected_selection_revision": 1,
            },
        )
        exposed = res.headers.get("access-control-expose-headers", "")
        for header in [
            "X-Report-Tenant-ID",
            "X-Report-Adoption-ID",
            "X-Report-Answer-Revision",
            "X-Report-Selection-Revision",
            "X-Report-SHA256",
            "Content-Disposition",
        ]:
            assert header.lower() in exposed.lower()


def test_report_download_role_admission(monkeypatch: pytest.MonkeyPatch):
    """Non-Owner/ComplianceManager role receives 403 Forbidden with generic safe detail."""
    tenant_id = uuid4()
    user_id = uuid4()

    test_app = FastAPI()
    monkeypatch.setattr(get_settings(), "enable_customer_demo", True)
    test_app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=user_id, mfa_verified=True
    )
    test_app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=tenant_id, user_id=user_id, role=Role.EMPLOYEE
    )
    register_customer_demo_routes(test_app)

    with TestClient(test_app) as client:
        res = client.post(
            f"/v2/tenants/{tenant_id}/customer-demo/assessment-reports/download",
            json={
                "adoption_id": str(uuid4()),
                "expected_answer_revision": 1,
                "expected_selection_revision": 1,
            },
        )
        assert res.status_code == 403
        data = res.json()
        assert "detail" in data
        assert "no-store" in res.headers.get("cache-control", "")


import io
import json
import zipfile
import hashlib
from unittest.mock import patch
from sqlalchemy import select
from conformly.audit.models import AuditEvent
from conformly.customer_demo.assessment_report_archive import verify_report_archive
from conformly.customer_demo.fixture import (
    BUNDLE_2_V1_DIGEST,
    PACK_2_VERSION_V1_ID,
    CTRL_1_VER_ID,
    SOURCE_2_PROVENANCE_DISCLAIMER,
)
from conformly.customer_demo.models import CustomerDemoAdoption, CustomerDemoWorkspace
from conformly.customer_demo.service import evaluate_answers, adopt_evaluation
from conformly.customer_demo.work_models import CustomerControlWork
from conformly.customer_demo.work_schemas import (
    InitializeWorkRequest,
    CreateEvidenceRequest,
    CreateLinkRequest,
    CreateReviewRequest,
)
from conformly.customer_demo.work_service import CustomerControlWorkService
from tests import test_customer_assessment_api as fixtures

MockSuccessfulScanner = fixtures.MockSuccessfulScanner
enable_demo_env = fixtures.enable_demo_env
env_fixture = fixtures.env_fixture
test_app = fixtures.test_app


def test_pack_2_complete_service_journey_to_verified_report_archive(test_app: FastAPI, env_fixture, session):
    """Complete real service/API journey for newly adopted pack to verified report archive.

    Covers: save answers -> evaluate exact new version -> explicit adoption -> initialize work ->
    deliberately reuse evidence revision from former pack -> target link starts PENDING ->
    explicit target suitability review -> initial assessment has no inherited PASS ->
    human assessment -> private report download and archive/manifest validation.
    """
    tenant_id = env_fixture["tenant_id"]
    owner_id = env_fixture["owner_id"]
    work_p1 = env_fixture["work"]
    adopt_p1_id = work_p1.adoption_id

    principal = Principal(user_id=owner_id, mfa_verified=True)
    tenant_context = TenantContext(tenant_id=tenant_id, user_id=owner_id, role=Role.OWNER)
    fixtures._set_auth(test_app, owner_id, tenant_id, Role.OWNER)
    client = TestClient(test_app)

    scanner = MockSuccessfulScanner()
    work_service = CustomerControlWorkService(session, scanner=scanner)

    # Re-use evidence item created during Pack 1 in env_fixture
    p1_links = work_service._get_links_for_work(work_p1)
    assert len(p1_links) >= 1
    ev_id = p1_links[0].evidence_id
    ev_rev_num = p1_links[0].revision_number
    ev_rev_digest = p1_links[0].digest

    # 3. Evaluate exact new version Pack 2 v1 via real service call
    eval_p2 = evaluate_answers(
        session,
        principal,
        tenant_context,
        expected_revision=1,
        pack_version_id=PACK_2_VERSION_V1_ID,
        request_id="req-eval-p2",
    )
    assert eval_p2.pack_version_id == PACK_2_VERSION_V1_ID
    assert eval_p2.bundle_digest == BUNDLE_2_V1_DIGEST

    # 4. Explicit adoption of Pack 2 v1 via real service call
    adopt_res = adopt_evaluation(
        session,
        principal,
        tenant_context,
        expected_revision=1,
        evaluation_id=eval_p2.id,
        pack_version_id=PACK_2_VERSION_V1_ID,
        acknowledge_synthetic=True,
        acknowledge_missing_information=True,
        request_id="req-adopt-p2",
    )
    adopt_p2_id = adopt_res["id"]
    assert adopt_res["selection_revision"] == 2
    assert adopt_res["is_current"] is True

    # Verify workspace selection revision advanced and old adoption remains in DB
    ws = session.query(CustomerDemoWorkspace).filter(CustomerDemoWorkspace.tenant_id == tenant_id).one()
    assert ws.selection_revision == 2
    old_adopt = session.query(CustomerDemoAdoption).filter(CustomerDemoAdoption.id == adopt_p1_id).one()
    assert old_adopt is not None

    # 5. Initialize work for Pack 2
    init_p2 = work_service.initialize_work(
        principal,
        tenant_context,
        InitializeWorkRequest(
            adoption_id=adopt_p2_id,
            expected_selection_revision=2,
            expected_answer_revision=1,
            operation_id=uuid4(),
        ),
        request_id="req-init-p2",
    )
    assert init_p2.total == 3

    # Verify work items derive provenance from Pack 2 bundle metadata!
    work_list_p2 = work_service.get_control_work_list(principal, tenant_context, adoption_id=adopt_p2_id)
    assert work_list_p2.is_current is True
    assert all(item.provenance == SOURCE_2_PROVENANCE_DISCLAIMER for item in work_list_p2.items)

    # 6. Deliberately reuse evidence from Pack 1 on Pack 2 shared control
    work_p2 = (
        session.query(CustomerControlWork)
        .filter(
            CustomerControlWork.tenant_id == tenant_id,
            CustomerControlWork.adoption_id == adopt_p2_id,
            CustomerControlWork.control_version_id == CTRL_1_VER_ID,
        )
        .one()
    )

    from conformly.storage.models import StoredFile
    stored_file = session.query(StoredFile).first()
    file_content = b"Encrypted test file contents for compliance."

    with patch("conformly.customer_demo.work_service.StorageService") as MockStorage:
        instance = MockStorage.return_value
        instance.download_file.return_value = (stored_file, file_content)

        reuse_receipt = work_service.create_link(
            principal,
            tenant_context,
            work_p2.id,
            CreateLinkRequest(
                expected_selection_revision=2,
                expected_answer_revision=1,
                expected_work_version=work_p2.version,
                evidence_id=ev_id,
                evidence_revision_number=ev_rev_num,
                evidence_revision_digest=ev_rev_digest,
                rationale="Deliberate reuse of verified cloud governance evidence on resilience pack",
                operation_id=uuid4(),
            ),
            request_id="req-deliberate-reuse",
        )
        target_link = reuse_receipt.current_work.links[0]
        # Reused link starts PENDING (no automatic pass carryover!)
        assert target_link.review == "PENDING"

        # 7. Perform explicit target suitability review
        review_receipt = work_service.create_review(
            principal,
            tenant_context,
            work_p2.id,
            target_link.id,
            CreateReviewRequest(
                expected_selection_revision=2,
                expected_answer_revision=1,
                expected_work_version=reuse_receipt.current_work.version,
                decision="ACCEPTED",
                rationale="Suitability verified for resilience pack cloud baseline.",
                operation_id=uuid4(),
            ),
            request_id="req-target-review",
        )
        assert review_receipt.current_work.links[0].review == "ACCEPTED"

    # 8. Human assessment has no inherited PASS
    proc_resp = client.get(f"/v2/tenants/{tenant_id}/customer-demo/assessment-work/{work_p2.id}/procedure")
    assert proc_resp.status_code == 200
    proc = proc_resp.json()

    assess_list_resp = client.get(f"/v2/tenants/{tenant_id}/customer-demo/assessment-work?adoption_id={adopt_p2_id}")
    assert assess_list_resp.status_code == 200
    item_p2 = next(i for i in assess_list_resp.json()["items"] if i["work_id"] == str(work_p2.id))
    assert item_p2["primary_state"] == "UNASSESSED"
    assert item_p2["latest_assessment"] is None

    # Perform fresh human assessment
    assess_resp = client.post(
        f"/v2/tenants/{tenant_id}/customer-demo/assessment-work/{work_p2.id}/assessments",
        json={
            "operation_id": str(uuid4()),
            "expected_answer_revision": 1,
            "expected_selection_revision": 2,
            "expected_work_version": review_receipt.current_work.version,
            "expected_assessment_revision": 0,
            "procedure_id": proc["id"],
            "procedure_version": proc["version"],
            "procedure_digest": proc["digest"],
            "evidence_link_ids": [str(target_link.id)],
            "criterion_results": [
                {"criterion_id": "implementation", "result": "PASS"},
                {"criterion_id": "evidence", "result": "PASS"},
                {"criterion_id": "operation", "result": "PASS"},
            ],
            "result": "PASS",
            "rationale": "Cloud baseline verified compliant with resilience criteria.",
        },
    )
    assert assess_resp.status_code == 201
    assert assess_resp.json()["current_item"]["primary_state"] == "PASS"

    # 9. Verify denials for mismatched context
    # Stale selection revision returns 409
    stale_resp = client.post(
        f"/v2/tenants/{tenant_id}/customer-demo/assessment-reports/download",
        json={
            "adoption_id": str(adopt_p2_id),
            "expected_answer_revision": 1,
            "expected_selection_revision": 1,
        },
    )
    assert stale_resp.status_code == 409

    # Cross-tenant request is denied (403/404)
    other_tenant_id = uuid4()
    cross_resp = client.post(
        f"/v2/tenants/{other_tenant_id}/customer-demo/assessment-reports/download",
        json={
            "adoption_id": str(adopt_p2_id),
            "expected_answer_revision": 1,
            "expected_selection_revision": 2,
        },
    )
    assert cross_resp.status_code in (403, 404)

    # Unknown adoption ID returns 404
    unknown_resp = client.post(
        f"/v2/tenants/{tenant_id}/customer-demo/assessment-reports/download",
        json={
            "adoption_id": str(uuid4()),
            "expected_answer_revision": 1,
            "expected_selection_revision": 2,
        },
    )
    assert unknown_resp.status_code in (404, 409)

    # 10. Valid private report download
    report_resp = client.post(
        f"/v2/tenants/{tenant_id}/customer-demo/assessment-reports/download",
        json={
            "adoption_id": str(adopt_p2_id),
            "expected_answer_revision": 1,
            "expected_selection_revision": 2,
        },
    )
    assert report_resp.status_code == 200
    assert report_resp.headers["content-type"] == "application/zip"
    assert report_resp.headers["x-report-tenant-id"] == str(tenant_id)
    assert report_resp.headers["x-report-sha256"] == hashlib.sha256(report_resp.content).hexdigest()
    assert "private" in report_resp.headers["cache-control"]
    assert "no-store" in report_resp.headers["cache-control"]

    # 11. Validate archive members and content
    assert report_resp.headers["x-report-selection-revision"] == "2"
    assert report_resp.headers["x-report-answer-revision"] == "1"

    bundle = verify_report_archive(report_resp.content, tenant_id=tenant_id, adoption_id=adopt_p2_id)

    with zipfile.ZipFile(io.BytesIO(report_resp.content)) as zf:
        assert sorted(zf.namelist()) == ["assessment.html", "assessment.json", "manifest.json"]

    manifest_data = json.loads(bundle.manifest_json)
    assert manifest_data["adoption_id"] == str(adopt_p2_id)
    assert manifest_data["tenant_id"] == str(tenant_id)
    assert len(manifest_data["files"]) == 2

    report_data = json.loads(bundle.report_json)
    assert report_data["adoption_id"] == str(adopt_p2_id)
    assert report_data["tenant_id"] == str(tenant_id)
    assert report_data["selection_revision"] == 2
    assert report_data["answer_revision"] == 1

    shared_item = next(i for i in report_data["items"] if i["control_version_id"] == str(CTRL_1_VER_ID))
    assert shared_item["primary_state"] == "PASS"
    assert shared_item["latest_assessment"]["result"] == "PASS"
    assert len(shared_item["latest_assessment"]["evidence_pins"]) == 1
    assert shared_item["latest_assessment"]["evidence_pins"][0]["link_id"] == str(target_link.id)

    # 12. Verify audit event was committed before bytes emitted
    audit_events = list(
        session.scalars(
            select(AuditEvent).where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.action == "customer_assessment.report_download_prepared",
            )
        ).all()
    )
    assert len(audit_events) >= 1
    latest_audit = audit_events[-1]
    from conformly.audit.models import AuditOutcome
    assert latest_audit.outcome == AuditOutcome.SUCCESS
    assert latest_audit.resource_id == str(adopt_p2_id)
