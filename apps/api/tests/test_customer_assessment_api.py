"""FastAPI integration and endpoint security tests for Customer Assessment API (MVP-C).

Tests endpoints under /v2/tenants/{tenant_id}/customer-demo/assessment-work:
- GET assessment-work (list & summary)
- GET assessment-work/{work_id}/procedure
- GET assessment-work/{work_id}/history
- POST assessment-work/{work_id}/assessments (create assessment)
- PATCH assessment-work/findings/{finding_id} (update finding)
- POST assessment-work/{work_id}/retests (record retest)
- Security guards: 16KiB body limit, route tenant mismatch, role/entitlement denials, replay.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conformly.auth.dependencies import get_current_principal, get_tenant_context
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.config import get_settings
from conformly.crypto.policy import DataClassification
from conformly.customer_demo.api import register_customer_demo_routes
from conformly.customer_demo.evaluator import (
    compute_answers_digest,
    compute_evaluation_digest,
    evaluate_bundle,
)
from conformly.customer_demo.fixture import (
    BUNDLE_V1_DIGEST,
    EVALUATOR_VERSION,
    PACK_VERSION_V1_ID,
)
from conformly.customer_demo.models import (
    CustomerDemoAdoption,
    CustomerDemoAnswers,
    CustomerDemoEvaluation,
    CustomerDemoWorkspace,
)
from conformly.customer_demo.work_models import CustomerControlWork
from conformly.customer_demo.work_scanner import StrictEvidenceMalwareScanner
from conformly.customer_demo.work_schemas import (
    CreateEvidenceRequest,
    CreateReviewRequest,
    InitializeWorkRequest,
)
from conformly.customer_demo.work_service import CustomerControlWorkService
from conformly.db.session import get_db
from conformly.entitlements.models import TenantEntitlement
from conformly.identity.models import (
    Membership,
    MembershipStatus,
    Tenant,
    TenantStatus,
    User,
    UserStatus,
)
from conformly.storage.models import StoredFile, StoredFileStatus


class MockSuccessfulScanner(StrictEvidenceMalwareScanner):
    def __init__(self) -> None:
        super().__init__(clamav_host="127.0.0.1", clamav_port=3310)

    def scan(self, data: bytes, filename: str) -> None:
        pass


@pytest.fixture(autouse=True)
def enable_demo_env(monkeypatch):
    monkeypatch.setenv("CONFORMLY_ENABLE_CUSTOMER_DEMO", "true")
    monkeypatch.setenv("CONFORMLY_ENVIRONMENT", "test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def test_app(session: Session):
    app = FastAPI()

    def _yielding_get_db():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    app.dependency_overrides[get_db] = _yielding_get_db
    register_customer_demo_routes(app)
    return app


def _seed_stored_file(
    session: Session, tenant_id: UUID, user_id: UUID, content: bytes = b"test evidence content"
) -> StoredFile:
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
    )
    session.add(f)
    session.commit()
    return f


@pytest.fixture
def env_fixture(session: Session):
    tenant_id = uuid4()
    owner_id = uuid4()
    mgr_id = uuid4()
    ctrl_owner_id = uuid4()
    auditor_id = uuid4()
    viewer_id = uuid4()
    now = datetime.now(UTC)

    tenant = Tenant(
        id=tenant_id,
        name="Assessment Demo Tenant",
        slug=f"tenant-{tenant_id}",
        status=TenantStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    session.add(tenant)

    users = [
        User(
            id=owner_id,
            oidc_issuer="https://auth.example.com",
            oidc_subject="sub-owner",
            email="owner@example.com",
            display_name="Alice Owner",
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        User(
            id=mgr_id,
            oidc_issuer="https://auth.example.com",
            oidc_subject="sub-mgr",
            email="mgr@example.com",
            display_name="Bob Manager",
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        User(
            id=ctrl_owner_id,
            oidc_issuer="https://auth.example.com",
            oidc_subject="sub-ctrl",
            email="ctrl@example.com",
            display_name="Carol ControlOwner",
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        User(
            id=auditor_id,
            oidc_issuer="https://auth.example.com",
            oidc_subject="sub-auditor",
            email="auditor@example.com",
            display_name="Dave Auditor",
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        User(
            id=viewer_id,
            oidc_issuer="https://auth.example.com",
            oidc_subject="sub-viewer",
            email="viewer@example.com",
            display_name="Eve Viewer",
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
    ]
    session.add_all(users)

    memberships = [
        Membership(
            tenant_id=tenant_id,
            user_id=owner_id,
            role=Role.OWNER,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        Membership(
            tenant_id=tenant_id,
            user_id=mgr_id,
            role=Role.COMPLIANCE_MANAGER,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        Membership(
            tenant_id=tenant_id,
            user_id=ctrl_owner_id,
            role=Role.CONTROL_OWNER,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        Membership(
            tenant_id=tenant_id,
            user_id=auditor_id,
            role=Role.AUDITOR,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        Membership(
            tenant_id=tenant_id,
            user_id=viewer_id,
            role=Role.VIEWER,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
    ]
    session.add_all(memberships)

    ent = TenantEntitlement(
        tenant_id=tenant_id,
        plan_code="tier_a",
        enabled_modules=["frameworks", "evidence", "tasks", "preaudit", "findings"],
        max_members=100,
        max_storage_bytes=10000000,
        allowed_framework_slugs=["*"],
        effective_from=now - timedelta(days=1),
        effective_until=now + timedelta(days=365),
    )
    session.add(ent)

    ws = CustomerDemoWorkspace(
        tenant_id=tenant_id,
        current_revision=1,
        selection_revision=1,
        created_at=now,
        updated_at=now,
    )
    session.add(ws)

    ans_digest = compute_answers_digest(
        "ALPHA", {"synthetic_wp09_uses_cloud": True, "synthetic_wp09_operating_region": "EU"}
    )
    answers = CustomerDemoAnswers(
        tenant_id=tenant_id,
        revision=1,
        company_code="ALPHA",
        answers={"synthetic_wp09_uses_cloud": True, "synthetic_wp09_operating_region": "EU"},
        content_digest=ans_digest,
        actor_id=owner_id,
        created_at=now,
    )
    session.add(answers)

    eval_results = evaluate_bundle(
        PACK_VERSION_V1_ID,
        {"synthetic_wp09_uses_cloud": True, "synthetic_wp09_operating_region": "EU"},
    )
    eval_digest = compute_evaluation_digest(
        answer_digest=ans_digest,
        answer_revision=1,
        bundle_digest=BUNDLE_V1_DIGEST,
        evaluator_version=EVALUATOR_VERSION,
        pack_version_id=PACK_VERSION_V1_ID,
        results=eval_results,
    )
    eval_id = uuid4()
    evaluation = CustomerDemoEvaluation(
        id=eval_id,
        tenant_id=tenant_id,
        answer_revision=1,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=BUNDLE_V1_DIGEST,
        evaluator_version=EVALUATOR_VERSION,
        content_digest=eval_digest,
        results=eval_results,
        actor_id=owner_id,
        created_at=now,
    )
    session.add(evaluation)

    adopt_id = uuid4()
    adoption = CustomerDemoAdoption(
        id=adopt_id,
        tenant_id=tenant_id,
        selection_revision=1,
        evaluation_id=eval_id,
        pack_version_id=PACK_VERSION_V1_ID,
        bundle_digest=BUNDLE_V1_DIGEST,
        actor_id=owner_id,
        created_at=now,
    )
    session.add(adoption)
    session.commit()

    owner_p = Principal(user_id=owner_id, mfa_verified=True)
    owner_t = TenantContext(tenant_id=tenant_id, role=Role.OWNER, user_id=owner_id)
    work_svc = CustomerControlWorkService(session, scanner=MockSuccessfulScanner())
    init_res = work_svc.initialize_work(
        owner_p,
        owner_t,
        InitializeWorkRequest(
            operation_id=uuid4(),
            adoption_id=adopt_id,
            expected_selection_revision=1,
            expected_answer_revision=1,
        ),
        request_id="req-init",
    )
    work_item_dto = init_res.items[0]
    work_orm = (
        session.query(CustomerControlWork).filter_by(tenant_id=tenant_id, id=work_item_dto.id).one()
    )

    file_content = b"Encrypted test file contents for compliance."
    stored_file = _seed_stored_file(session, tenant_id, owner_id, file_content)
    with patch("conformly.customer_demo.work_service.StorageService") as MockStorage:
        instance = MockStorage.return_value
        instance.download_file.return_value = (stored_file, file_content)
        ev_receipt = work_svc.create_evidence(
            owner_p,
            owner_t,
            work_item_dto.id,
            CreateEvidenceRequest(
                operation_id=uuid4(),
                expected_selection_revision=1,
                expected_answer_revision=1,
                expected_work_version=work_orm.version,
                file_id=stored_file.id,
                rationale="Audit policy evidence",
            ),
            request_id="req-pin",
        )
        link_id = ev_receipt.current_work.links[0].id
        session.refresh(work_orm)

        work_svc.create_review(
            owner_p,
            owner_t,
            work_item_dto.id,
            link_id,
            CreateReviewRequest(
                operation_id=uuid4(),
                expected_selection_revision=1,
                expected_answer_revision=1,
                expected_work_version=work_orm.version,
                decision="ACCEPTED",
                rationale="Reviewed and accepted",
            ),
            request_id="req-rev",
        )
    session.refresh(work_orm)

    return {
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "mgr_id": mgr_id,
        "ctrl_owner_id": ctrl_owner_id,
        "auditor_id": auditor_id,
        "viewer_id": viewer_id,
        "work": work_orm,
        "link_id": link_id,
    }


def _set_auth(app: FastAPI, user_id: UUID, tenant_id: UUID, role: Role):
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id=user_id, mfa_verified=True
    )
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=tenant_id, user_id=user_id, role=role
    )


def test_get_assessment_work_and_procedure(test_app: FastAPI, env_fixture: dict[str, Any]):
    tenant_id = env_fixture["tenant_id"]
    mgr_id = env_fixture["mgr_id"]
    work = env_fixture["work"]

    _set_auth(test_app, mgr_id, tenant_id, Role.COMPLIANCE_MANAGER)
    client = TestClient(test_app)

    # 1. GET list
    resp = client.get(f"/v2/tenants/{tenant_id}/customer-demo/assessment-work")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "summary" in data
    assert len(data["items"]) == 2
    assert data["summary"]["unassessed"] == 2

    # 2. GET procedure
    resp_proc = client.get(
        f"/v2/tenants/{tenant_id}/customer-demo/assessment-work/{work.id}/procedure"
    )
    assert resp_proc.status_code == 200
    proc = resp_proc.json()
    assert "id" in proc
    assert "digest" in proc
    assert len(proc["criteria"]) == 3


def test_assessment_full_api_journey(test_app: FastAPI, env_fixture: dict[str, Any]):
    tenant_id = env_fixture["tenant_id"]
    mgr_id = env_fixture["mgr_id"]
    ctrl_owner_id = env_fixture["ctrl_owner_id"]
    work = env_fixture["work"]
    link_id = env_fixture["link_id"]

    _set_auth(test_app, mgr_id, tenant_id, Role.COMPLIANCE_MANAGER)
    client = TestClient(test_app)

    # Get procedure
    proc_resp = client.get(
        f"/v2/tenants/{tenant_id}/customer-demo/assessment-work/{work.id}/procedure"
    )
    proc = proc_resp.json()

    # Step 1: POST assessment with FAIL and a finding
    op1_id = str(uuid4())
    assess_payload = {
        "operation_id": op1_id,
        "expected_answer_revision": 1,
        "expected_selection_revision": 1,
        "expected_work_version": work.version,
        "expected_assessment_revision": 0,
        "procedure_id": proc["id"],
        "procedure_version": proc["version"],
        "procedure_digest": proc["digest"],
        "evidence_link_ids": [str(link_id)],
        "criterion_results": [
            {"criterion_id": "implementation", "result": "FAIL"},
            {"criterion_id": "evidence", "result": "PASS"},
            {"criterion_id": "operation", "result": "PASS"},
        ],
        "result": "FAIL",
        "rationale": "Missing review sheet",
        "finding": {
            "severity": "MEDIUM",
            "owner_user_id": str(ctrl_owner_id),
            "due_date": (date.today() + timedelta(days=14)).isoformat(),
        },
    }

    resp1 = client.post(
        f"/v2/tenants/{tenant_id}/customer-demo/assessment-work/{work.id}/assessments",
        json=assess_payload,
    )
    assert resp1.status_code == 201
    r1_data = resp1.json()
    assert r1_data["applied_revision"] == 1
    assert r1_data["replayed"] is False
    assert r1_data["current_item"]["primary_state"] == "FAIL"
    assert len(r1_data["current_item"]["findings"]) == 1

    finding_id = r1_data["current_item"]["findings"][0]["id"]
    finding_ver = r1_data["current_item"]["findings"][0]["version"]

    # Step 2: GET history
    resp_hist = client.get(
        f"/v2/tenants/{tenant_id}/customer-demo/assessment-work/{work.id}/history"
    )
    assert resp_hist.status_code == 200
    hist_data = resp_hist.json()
    assert hist_data["total"] == 1
    assert hist_data["items"][0]["event_type"] == "ASSESSMENT"
    assert hist_data["items"][0]["result"] == "FAIL"

    # Step 3: PATCH finding
    patch_payload = {
        "operation_id": str(uuid4()),
        "expected_answer_revision": 1,
        "expected_selection_revision": 1,
        "expected_work_version": work.version,
        "expected_assessment_revision": 1,
        "expected_finding_version": finding_ver,
        "severity": "MEDIUM",
        "owner_user_id": str(ctrl_owner_id),
        "due_date": (date.today() + timedelta(days=14)).isoformat(),
        "status": "IN_REMEDIATION",
        "remediation_note": "Remediation initiated by security team",
    }
    resp_patch = client.patch(
        f"/v2/tenants/{tenant_id}/customer-demo/assessment-work/findings/{finding_id}",
        json=patch_payload,
    )
    assert resp_patch.status_code == 200
    r_patch_data = resp_patch.json()
    assert r_patch_data["current_item"]["findings"][0]["status"] == "IN_REMEDIATION"
    updated_finding_ver = r_patch_data["current_item"]["findings"][0]["version"]

    # Step 4: POST retest
    op2_id = str(uuid4())
    retest_payload = {
        "operation_id": op2_id,
        "expected_answer_revision": 1,
        "expected_selection_revision": 1,
        "expected_work_version": work.version,
        "expected_assessment_revision": 2,
        "procedure_id": proc["id"],
        "procedure_version": proc["version"],
        "procedure_digest": proc["digest"],
        "evidence_link_ids": [str(link_id)],
        "criterion_results": [
            {"criterion_id": "implementation", "result": "PASS"},
            {"criterion_id": "evidence", "result": "PASS"},
            {"criterion_id": "operation", "result": "PASS"},
        ],
        "result": "PASS",
        "rationale": "Remediation verified and policy attached",
        "findings": [{"id": finding_id, "expected_version": updated_finding_ver}],
    }
    resp_retest = client.post(
        f"/v2/tenants/{tenant_id}/customer-demo/assessment-work/{work.id}/retests",
        json=retest_payload,
    )
    assert resp_retest.status_code == 201
    r_retest_data = resp_retest.json()
    assert r_retest_data["applied_revision"] == 3
    assert r_retest_data["current_item"]["primary_state"] == "PASS"
    assert r_retest_data["current_item"]["findings"][0]["status"] == "RESOLVED"

    # Step 5: Test replay idempotency
    resp_replay = client.post(
        f"/v2/tenants/{tenant_id}/customer-demo/assessment-work/{work.id}/retests",
        json=retest_payload,
    )
    assert resp_replay.status_code == 201
    assert resp_replay.json()["replayed"] is True


def test_security_route_tenant_mismatch(test_app: FastAPI, env_fixture: dict[str, Any]):
    tenant_id = env_fixture["tenant_id"]
    mgr_id = env_fixture["mgr_id"]
    other_tenant_id = uuid4()

    _set_auth(test_app, mgr_id, tenant_id, Role.COMPLIANCE_MANAGER)
    client = TestClient(test_app)

    # Route with wrong tenant_id
    resp = client.get(f"/v2/tenants/{other_tenant_id}/customer-demo/assessment-work")
    assert resp.status_code == 403


def test_security_unauthorized_role(test_app: FastAPI, env_fixture: dict[str, Any]):
    tenant_id = env_fixture["tenant_id"]
    viewer_id = env_fixture["viewer_id"]

    _set_auth(test_app, viewer_id, tenant_id, Role.VIEWER)
    client = TestClient(test_app)

    resp = client.get(f"/v2/tenants/{tenant_id}/customer-demo/assessment-work")
    assert resp.status_code == 403


def test_security_16kib_payload_limit(test_app: FastAPI, env_fixture: dict[str, Any]):
    tenant_id = env_fixture["tenant_id"]
    mgr_id = env_fixture["mgr_id"]
    work = env_fixture["work"]

    _set_auth(test_app, mgr_id, tenant_id, Role.COMPLIANCE_MANAGER)
    client = TestClient(test_app)

    proc_resp = client.get(
        f"/v2/tenants/{tenant_id}/customer-demo/assessment-work/{work.id}/procedure"
    )
    proc = proc_resp.json()

    # Payload over 16KiB
    huge_payload = {
        "operation_id": str(uuid4()),
        "expected_answer_revision": 1,
        "expected_selection_revision": 1,
        "expected_work_version": work.version,
        "expected_assessment_revision": 0,
        "procedure_id": proc["id"],
        "procedure_version": proc["version"],
        "procedure_digest": proc["digest"],
        "evidence_link_ids": [],
        "criterion_results": [
            {"criterion_id": "implementation", "result": "PASS"},
            {"criterion_id": "evidence", "result": "PASS"},
            {"criterion_id": "operation", "result": "PASS"},
        ],
        "result": "PASS",
        "rationale": "X" * 17000,
    }

    resp = client.post(
        f"/v2/tenants/{tenant_id}/customer-demo/assessment-work/{work.id}/assessments",
        json=huge_payload,
    )
    assert resp.status_code == 413


def test_api_read_chain_metadata_tampering_marks_stale_and_blocks_pass(
    test_app: FastAPI, env_fixture: dict[str, Any], session: Session
):
    """Verify via HTTP API that tampering evaluation evaluator_version marks work item and list stale,
    removing PASS from current posture."""
    from sqlalchemy import select

    from conformly.customer_demo.models import CustomerDemoEvaluation

    tenant_id = env_fixture["tenant_id"]
    mgr_id = env_fixture["mgr_id"]
    work = env_fixture["work"]

    _set_auth(test_app, mgr_id, tenant_id, Role.COMPLIANCE_MANAGER)
    client = TestClient(test_app)

    # 1. Fetch procedure and record valid PASS
    proc_resp = client.get(
        f"/v2/tenants/{tenant_id}/customer-demo/assessment-work/{work.id}/procedure"
    )
    assert proc_resp.status_code == 200
    proc = proc_resp.json()

    pass_payload = {
        "operation_id": str(uuid4()),
        "expected_answer_revision": 1,
        "expected_selection_revision": 1,
        "expected_work_version": work.version,
        "expected_assessment_revision": 0,
        "procedure_id": proc["id"],
        "procedure_version": proc["version"],
        "procedure_digest": proc["digest"],
        "evidence_link_ids": [str(env_fixture["link_id"])],
        "criterion_results": [
            {"criterion_id": "implementation", "result": "PASS"},
            {"criterion_id": "evidence", "result": "PASS"},
            {"criterion_id": "operation", "result": "PASS"},
        ],
        "result": "PASS",
        "rationale": "Valid initial PASS via API",
    }

    create_resp = client.post(
        f"/v2/tenants/{tenant_id}/customer-demo/assessment-work/{work.id}/assessments",
        json=pass_payload,
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["current_item"]["primary_state"] == "PASS"

    # Verify baseline list read returns PASS
    list_resp = client.get(f"/v2/tenants/{tenant_id}/customer-demo/assessment-work")
    assert list_resp.status_code == 200
    list_json = list_resp.json()
    assert list_json["summary"]["pass_count"] == 1
    matched_item = next(i for i in list_json["items"] if i["work_id"] == str(work.id))
    assert matched_item["primary_state"] == "PASS"
    assert matched_item["latest_assessment"]["is_stale"] is False

    # 2. Tamper evaluation evaluator_version in DB
    eval_row = session.scalar(
        select(CustomerDemoEvaluation).where(CustomerDemoEvaluation.tenant_id == tenant_id)
    )
    assert eval_row is not None
    orig_ver = eval_row.evaluator_version

    try:
        eval_row.evaluator_version = "corrupt-evaluator-version"
        session.flush()

        # List GET must reflect 0 pass_count and STALE_ASSESSMENT
        list_resp_tampered = client.get(f"/v2/tenants/{tenant_id}/customer-demo/assessment-work")
        assert list_resp_tampered.status_code == 200
        list_data = list_resp_tampered.json()
        assert list_data["summary"]["pass_count"] == 0
        assert list_data["summary"]["stale_assessment"] >= 1
        tampered_item = next(i for i in list_data["items"] if i["work_id"] == str(work.id))
        assert tampered_item["primary_state"] == "STALE_ASSESSMENT"
        assert tampered_item["latest_assessment"]["is_stale"] is True
        assert "ASSESSMENT_STALE" in tampered_item["blockers"]
    finally:
        eval_row.evaluator_version = orig_ver
        session.flush()

    # Restoration returns cleanly to PASS
    restored_resp = client.get(f"/v2/tenants/{tenant_id}/customer-demo/assessment-work")
    assert restored_resp.status_code == 200
    restored_json = restored_resp.json()
    assert restored_json["summary"]["pass_count"] == 1
    restored_item = next(i for i in restored_json["items"] if i["work_id"] == str(work.id))
    assert restored_item["primary_state"] == "PASS"
    assert restored_item["latest_assessment"]["is_stale"] is False
