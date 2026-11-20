"""Tests for LMS completion callback validation, correlation, and evidence integrity."""

from datetime import UTC, datetime, timedelta
import json
from typing import Any, Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.authz.roles import Role
from conformly.compliance.models import EvidenceItem, EvidenceStatus
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.db.session import get_db
from conformly.entitlements.models import TenantEntitlement
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User, UserStatus
from conformly.integrations.service import create_integration_credential
from conformly.lms.client import LmsPartnerSimulator
from conformly.lms.contract import LmsCompletionPayload
from conformly.lms.models import AssignmentStatus, TrainingAssignment, TrainingCompletion, TrainingCourse
from conformly.lms.service import create_training_assignment, create_training_course, record_training_completion
from conformly.main import app


def make_test_codec() -> EncryptedFieldCodec:
    import base64

    b64_key = base64.b64encode(b"\x07" * 32).decode("ascii")
    kms = LocalKeyManagementProvider({"v1": b64_key}, "v1")
    envelope = EnvelopeEncryptionService(AES256GCMProvider(), kms)
    return EncryptedFieldCodec(envelope)


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    test_codec = make_test_codec()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_encrypted_field_codec] = lambda: test_codec
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def setup_lms_environment(session: Session) -> tuple[Tenant, User, Any, str, str]:
    codec = make_test_codec()
    tenant = Tenant(
        name="LMS Validation Tenant",
        slug=f"lms-val-{uuid4().hex[:8]}",
        status=TenantStatus.ACTIVE,
    )
    user = User(
        oidc_issuer="https://identity.conformly.de",
        oidc_subject=str(uuid4()),
        email=f"learner-{uuid4().hex[:8]}@example.com",
        display_name="Security Learner",
    )
    session.add_all([tenant, user])
    session.flush()

    membership = Membership(
        tenant_id=tenant.id,
        user_id=user.id,
        role=Role.EMPLOYEE,
        status=MembershipStatus.ACTIVE,
    )
    session.add(membership)

    entitlement = TenantEntitlement(
        tenant_id=tenant.id,
        plan_code="tier_a",
        enabled_modules=["frameworks", "evidence", "tasks", "lms"],
        effective_from=datetime.now(UTC) - timedelta(days=1),
        effective_until=datetime.now(UTC) + timedelta(days=365),
    )
    session.add(entitlement)

    cred_res = create_integration_credential(
        session,
        codec,
        tenant_id=tenant.id,
        name="LMS Webhook Credential",
        scopes=["lms:write"],
    )

    course = create_training_course(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        title="Test Security Training",
        description="Test course description",
    )
    session.commit()

    return tenant, user, cred_res, cred_res.credential.key_id, cred_res.signing_secret


def test_failed_completion_does_not_create_evidence_or_complete_assignment(
    session: Session, client: TestClient
) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    # Create assignment
    due_date = datetime.now(UTC) + timedelta(days=14)
    assignment = create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=due_date,
    )
    session.commit()

    # Callback with passed = False (failed exam)
    event_id = f"fail-evt-{uuid4().hex[:8]}"
    completion_payload = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=False,
        assignment_id=str(assignment.id),
        score=45.0,
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        completion_payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )

    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp.status_code == 422
    assert "passed" in resp.json()["detail"].lower() or "failed" in resp.json()["detail"].lower()

    # Verify NO EvidenceItem exists for this completion
    ev_stmt = select(EvidenceItem).where(
        EvidenceItem.tenant_id == tenant.id,
        EvidenceItem.title.contains("SEC-TEST-001"),
    )
    evidence_items = list(session.scalars(ev_stmt).all())
    assert len(evidence_items) == 0

    # Verify assignment is NOT completed
    reloaded_assignment = session.get(TrainingAssignment, assignment.id)
    assert reloaded_assignment is not None
    assert reloaded_assignment.status != AssignmentStatus.COMPLETED


def test_foreign_or_invalid_assignment_id_rejected(
    session: Session, client: TestClient
) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    # 1. Non-existent assignment UUID
    event_id = f"missing-assign-{uuid4().hex[:8]}"
    completion_payload = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
        assignment_id=str(uuid4()),  # non-existent
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        completion_payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )
    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp.status_code == 404
    assert "Referenced assignment not found" in resp.json()["detail"]

    # 2. Malformed assignment UUID
    event_id_bad = f"bad-assign-{uuid4().hex[:8]}"
    bad_payload = LmsCompletionPayload(
        event_id=event_id_bad,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
        assignment_id="not-a-valid-uuid",
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        bad_payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )
    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp.status_code == 422


def test_assignment_course_or_learner_mismatch_rejected(
    session: Session, client: TestClient
) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    due_date = datetime.now(UTC) + timedelta(days=14)
    assignment = create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=due_date,
    )
    session.commit()

    # Mismatched course_id
    event_id = f"mismatch-course-{uuid4().hex[:8]}"
    completion_payload = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="WRONG-COURSE-ID",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
        assignment_id=str(assignment.id),
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        completion_payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )
    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp.status_code == 422
    assert "Assignment course_id does not match" in resp.json()["detail"]


def test_unknown_or_inactive_learner_rejected(
    session: Session, client: TestClient
) -> None:
    tenant, _, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    # Unknown email (not a member of tenant)
    event_id = f"unknown-learner-{uuid4().hex[:8]}"
    completion_payload = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email="nonexistent-stranger@external.com",
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        completion_payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )
    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp.status_code == 422
    assert "not an active member" in resp.json()["detail"]


def test_signature_verification_and_replay_protection(
    session: Session, client: TestClient
) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    completion_payload = LmsCompletionPayload(
        event_id=f"sig-test-{uuid4().hex[:8]}",
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        completion_payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )

    # 1. Invalid signature
    tampered_headers = dict(headers)
    tampered_headers["X-Conformly-Signature"] = "v1=0000000000000000000000000000000000000000000000000000000000000000"
    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=tampered_headers,
    )
    assert resp.status_code == 401

    # 2. Stale timestamp (> 300s)
    stale_headers = dict(headers)
    stale_ts = str(int(datetime.now(UTC).timestamp()) - 600)
    stale_headers["X-Conformly-Timestamp"] = stale_ts
    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=stale_headers,
    )
    assert resp.status_code == 400
    assert "Replay protection error" in resp.json()["detail"]


def test_idempotent_duplicate_and_tampered_conflict(
    session: Session, client: TestClient
) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=datetime.now(UTC) + timedelta(days=14),
    )
    session.commit()

    event_id = f"idem-test-{uuid4().hex[:8]}"
    completion_payload = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
        score=99.0,
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        completion_payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )

    # First call: 200 completed
    resp1 = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "completed"

    # Second call (exact replay): 200 idempotent_replay
    resp2 = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "idempotent_replay"

    # Third call with SAME event_id but altered score (tampering): 409 Conflict
    tampered_payload = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
        score=50.0,  # altered
    )
    raw_tampered, tampered_headers = lms_partner.generate_signed_completion_event(
        tampered_payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )
    resp3 = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_tampered,
        headers=tampered_headers,
    )
    assert resp3.status_code == 409


def test_passed_as_string_false_rejected(session: Session, client: TestClient) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    # Raw JSON with passed as string "false"
    payload_dict = {
        "event_id": f"str-false-{uuid4().hex[:8]}",
        "tenant_id": str(tenant.id),
        "course_id": "SEC-TEST-001",
        "course_version": "1.0",
        "learner_email": user.email,
        "completed_at": datetime.now(UTC).isoformat(),
        "passed": "false",  # STRING "false"
    }
    from conformly.integrations.service import compute_webhook_signature
    import time
    raw_body = json.dumps(payload_dict).encode("utf-8")
    ts = int(time.time())
    sig = compute_webhook_signature(raw_body, ts, signing_secret)
    headers = {
        "Content-Type": "application/json",
        "X-Conformly-Key-Id": key_id,
        "X-Conformly-Signature": sig,
        "X-Conformly-Timestamp": str(ts),
        "X-Conformly-Idempotency-Key": payload_dict.get("event_id", ""),
    }

    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp.status_code == 422
    assert "boolean" in resp.json()["detail"].lower() or "passed" in resp.json()["detail"].lower()

    # Verify NO EvidenceItem was created
    ev = session.scalars(select(EvidenceItem).where(EvidenceItem.tenant_id == tenant.id)).all()
    assert len(list(ev)) == 0


def test_passed_omitted_rejected(session: Session, client: TestClient) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    # Raw JSON with passed omitted
    payload_dict = {
        "event_id": f"no-passed-{uuid4().hex[:8]}",
        "tenant_id": str(tenant.id),
        "course_id": "SEC-TEST-001",
        "course_version": "1.0",
        "learner_email": user.email,
        "completed_at": datetime.now(UTC).isoformat(),
    }
    from conformly.integrations.service import compute_webhook_signature
    import time
    raw_body = json.dumps(payload_dict).encode("utf-8")
    ts = int(time.time())
    sig = compute_webhook_signature(raw_body, ts, signing_secret)
    headers = {
        "Content-Type": "application/json",
        "X-Conformly-Key-Id": key_id,
        "X-Conformly-Signature": sig,
        "X-Conformly-Timestamp": str(ts),
        "X-Conformly-Idempotency-Key": payload_dict.get("event_id", ""),
    }

    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp.status_code == 422

    # Verify NO EvidenceItem was created
    ev = session.scalars(select(EvidenceItem).where(EvidenceItem.tenant_id == tenant.id)).all()
    assert len(list(ev)) == 0


def test_unregistered_course_rejected(session: Session, client: TestClient) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    payload = LmsCompletionPayload(
        event_id=f"unreg-course-{uuid4().hex[:8]}",
        tenant_id=str(tenant.id),
        course_id="NON-EXISTENT-COURSE-999",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )
    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp.status_code in (404, 422)

    ev = session.scalars(select(EvidenceItem).where(EvidenceItem.tenant_id == tenant.id)).all()
    assert len(list(ev)) == 0


def test_unknown_course_version_rejected(session: Session, client: TestClient) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    payload = LmsCompletionPayload(
        event_id=f"bad-ver-{uuid4().hex[:8]}",
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="999.9",  # Active course is 1.0
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )
    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp.status_code == 422
    assert "version" in resp.json()["detail"].lower()

    ev = session.scalars(select(EvidenceItem).where(EvidenceItem.tenant_id == tenant.id)).all()
    assert len(list(ev)) == 0


def test_foreign_body_tenant_id_rejected(session: Session, client: TestClient) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    foreign_tenant_id = str(uuid4())
    payload = LmsCompletionPayload(
        event_id=f"foreign-tenant-{uuid4().hex[:8]}",
        tenant_id=foreign_tenant_id,  # foreign body tenant
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )
    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp.status_code in (400, 422)
    assert "tenant" in resp.json()["detail"].lower()

    ev = session.scalars(select(EvidenceItem).where(EvidenceItem.tenant_id == tenant.id)).all()
    assert len(list(ev)) == 0


def test_unsigned_idempotency_header_override_rejected(session: Session, client: TestClient) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=datetime.now(UTC) + timedelta(days=14),
    )
    session.commit()

    signed_event_id = f"signed-event-{uuid4().hex[:8]}"
    payload = LmsCompletionPayload(
        event_id=signed_event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )

    # 1. Header differs from signed body event_id -> Must be REJECTED (400)
    conflicting_headers = dict(headers)
    conflicting_headers["X-Conformly-Idempotency-Key"] = f"header-override-{uuid4().hex[:8]}"
    resp_conflict = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=conflicting_headers,
    )
    assert resp_conflict.status_code == 400
    assert "idempotency" in resp_conflict.json()["detail"].lower() or "event_id" in resp_conflict.json()["detail"].lower()

    # 2. Sending matching header or no header succeeds
    resp_ok = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp_ok.status_code == 200
    evidence_id = resp_ok.json()["evidence_id"]
    assert evidence_id is not None

    # 3. Sending same raw_body with a DIFFERENT unsigned header must NOT create a 2nd evidence record
    conflicting_headers2 = dict(headers)
    conflicting_headers2["X-Conformly-Idempotency-Key"] = f"header-override-2-{uuid4().hex[:8]}"
    resp_conflict2 = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=conflicting_headers2,
    )
    assert resp_conflict2.status_code == 400

    # Total evidence items must be exactly 1
    ev = session.scalars(select(EvidenceItem).where(EvidenceItem.tenant_id == tenant.id)).all()
    assert len(list(ev)) == 1


def test_multiple_active_assignments_without_explicit_id_rejected(
    session: Session, client: TestClient
) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    due_date = datetime.now(UTC) + timedelta(days=14)
    # Create TWO active assignments for same course & learner
    a1 = create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=due_date,
    )
    a2 = create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=due_date + timedelta(days=7),
    )
    session.commit()

    # Callback omits assignment_id
    payload = LmsCompletionPayload(
        event_id=f"ambig-assign-{uuid4().hex[:8]}",
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )
    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp.status_code == 422
    assert "multiple" in resp.json()["detail"].lower() or "ambiguous" in resp.json()["detail"].lower()

def test_zero_assignments_rejected(
    session: Session, client: TestClient
) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    # Zero assignments created for this learner and course
    payload = LmsCompletionPayload(
        event_id=f"zero-assign-{uuid4().hex[:8]}",
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )
    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp.status_code == 422
    assert "assignment" in resp.json()["detail"].lower()

    # Assert no EvidenceItem or TrainingCompletion created
    ev = session.scalar(select(EvidenceItem).where(EvidenceItem.tenant_id == tenant.id))
    assert ev is None
    tc = session.scalar(select(TrainingCompletion).where(TrainingCompletion.tenant_id == tenant.id))
    assert tc is None


def test_expired_explicit_assignment_rejected(
    session: Session, client: TestClient
) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    due_date = datetime.now(UTC) - timedelta(days=5)
    assignment = create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=due_date,
    )
    assignment.status = AssignmentStatus.EXPIRED
    session.commit()

    payload = LmsCompletionPayload(
        event_id=f"expired-assign-{uuid4().hex[:8]}",
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
        assignment_id=str(assignment.id),
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )
    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp.status_code == 422
    assert "eligible" in resp.json()["detail"].lower() or "expired" in resp.json()["detail"].lower()

    ev = session.scalar(select(EvidenceItem).where(EvidenceItem.tenant_id == tenant.id))
    assert ev is None


def test_already_completed_explicit_assignment_rejected(
    session: Session, client: TestClient
) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    due_date = datetime.now(UTC) + timedelta(days=10)
    assignment = create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=due_date,
    )
    assignment.status = AssignmentStatus.COMPLETED
    session.commit()

    payload = LmsCompletionPayload(
        event_id=f"already-completed-{uuid4().hex[:8]}",
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
        assignment_id=str(assignment.id),
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )
    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp.status_code == 422
    assert "eligible" in resp.json()["detail"].lower() or "completed" in resp.json()["detail"].lower()


def test_disabled_user_with_active_membership_rejected(
    session: Session, client: TestClient
) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    due_date = datetime.now(UTC) + timedelta(days=14)
    create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=due_date,
    )
    # Disable the user while leaving membership active
    user.status = UserStatus.DISABLED
    session.commit()

    payload = LmsCompletionPayload(
        event_id=f"disabled-user-{uuid4().hex[:8]}",
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        payload,
        signing_secret=signing_secret,
        key_id=key_id,
    )
    resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert resp.status_code == 422
    assert "active" in resp.json()["detail"].lower() or "disabled" in resp.json()["detail"].lower()

    ev = session.scalar(select(EvidenceItem).where(EvidenceItem.tenant_id == tenant.id))
    assert ev is None


def test_invalid_control_reference_rejected(
    session: Session, client: TestClient
) -> None:
    tenant, user, _, key_id, signing_secret = setup_lms_environment(session)
    lms_partner = LmsPartnerSimulator()

    due_date = datetime.now(UTC) + timedelta(days=14)

    # 1. Partial pair: control_id without control_type
    with pytest.raises(Exception) as exc1:
        create_training_assignment(
            session,
            tenant_id=tenant.id,
            course_id="SEC-TEST-001",
            workforce_email=user.email,
            due_date=due_date,
            control_id=uuid4(),
            control_type=None,
        )
    assert "422" in str(exc1.value) or "control" in str(exc1.value).lower()

    # 2. Unknown control_type: e.g. "v2_common_control"
    with pytest.raises(Exception) as exc2:
        create_training_assignment(
            session,
            tenant_id=tenant.id,
            course_id="SEC-TEST-001",
            workforce_email=user.email,
            due_date=due_date,
            control_id=uuid4(),
            control_type="v2_common_control",
        )
    assert "422" in str(exc2.value) or "control" in str(exc2.value).lower()

    # 3. Nonexistent canonical control
    with pytest.raises(Exception) as exc3:
        create_training_assignment(
            session,
            tenant_id=tenant.id,
            course_id="SEC-TEST-001",
            workforce_email=user.email,
            due_date=due_date,
            control_id=uuid4(),
            control_type="canonical",
        )
    assert "422" in str(exc3.value) or "control" in str(exc3.value).lower()


def test_assignment_creation_with_mismatched_explicit_user_id_rejected(
    session: Session,
) -> None:
    tenant, user, _, _, _ = setup_lms_environment(session)
    due_date = datetime.now(UTC) + timedelta(days=14)

    arbitrary_user_id = uuid4()
    with pytest.raises(Exception) as exc:
        create_training_assignment(
            session,
            tenant_id=tenant.id,
            course_id="SEC-TEST-001",
            workforce_email=user.email,
            due_date=due_date,
            user_id=arbitrary_user_id,
        )
    assert "422" in str(exc.value) or "user" in str(exc.value).lower()


def test_direct_service_foreign_tenant_rejected(
    session: Session,
) -> None:
    tenant, user, _, _, _ = setup_lms_environment(session)
    codec = make_test_codec()

    foreign_tenant_id = uuid4()
    payload = LmsCompletionPayload(
        event_id=f"foreign-service-{uuid4().hex[:8]}",
        tenant_id=str(foreign_tenant_id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
    )
    with pytest.raises(Exception) as exc:
        record_training_completion(
            session,
            codec,
            tenant_id=tenant.id,
            payload=payload,
        )
    assert "422" in str(exc.value) or "tenant" in str(exc.value).lower()


def test_direct_service_reused_event_id_with_altered_semantics_conflicts(
    session: Session,
) -> None:
    tenant, user, _, _, _ = setup_lms_environment(session)
    codec = make_test_codec()

    due_date = datetime.now(UTC) + timedelta(days=14)
    create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=due_date,
    )
    session.commit()

    event_id = f"evt-conflict-{uuid4().hex[:8]}"
    payload1 = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
        score=95.0,
    )
    comp1, ev1, is_new1 = record_training_completion(
        session,
        codec,
        tenant_id=tenant.id,
        payload=payload1,
    )
    assert is_new1 is True

    # Replay with altered score: must raise 409 Conflict
    payload_altered = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
        score=50.0,
    )
    with pytest.raises(Exception) as exc:
        record_training_completion(
            session,
            codec,
            tenant_id=tenant.id,
            payload=payload_altered,
        )
    assert "409" in str(exc.value) or "conflict" in str(exc.value).lower()


def test_direct_service_exact_replay_returns_existing_after_completion(
    session: Session,
) -> None:
    tenant, user, _, _, _ = setup_lms_environment(session)
    codec = make_test_codec()

    due_date = datetime.now(UTC) + timedelta(days=14)
    assign = create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=due_date,
    )
    session.commit()

    event_id = f"evt-exact-replay-{uuid4().hex[:8]}"
    completed_at = datetime.now(UTC).isoformat()
    payload = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=completed_at,
        passed=True,
        assignment_id=str(assign.id),
        score=100.0,
    )
    comp1, ev1, is_new1 = record_training_completion(
        session,
        codec,
        tenant_id=tenant.id,
        payload=payload,
    )
    assert is_new1 is True
    assert assign.status == AssignmentStatus.COMPLETED

    # Exact replay after assignment is already completed
    comp2, ev2, is_new2 = record_training_completion(
        session,
        codec,
        tenant_id=tenant.id,
        payload=payload,
    )
    assert is_new2 is False
    assert comp2.id == comp1.id
    assert ev2.id == ev1.id



def test_historical_partial_control_pair_rejected_before_evidence_creation_without_session_rollback(
    session: Session,
) -> None:
    tenant, user, _, _, _ = setup_lms_environment(session)
    codec = make_test_codec()

    # Create assignment with partial control reference directly in DB
    assign = TrainingAssignment(
        id=uuid4(),
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        user_id=user.id,
        workforce_email=user.email,
        due_date=datetime.now(UTC) + timedelta(days=14),
        status=AssignmentStatus.ASSIGNED,
        control_id=uuid4(),
        control_type=None,  # PARTIAL PAIR: control_id without control_type
    )
    session.add(assign)
    session.commit()

    ev_count_before = len(list(session.scalars(select(EvidenceItem).where(EvidenceItem.tenant_id == tenant.id)).all()))
    comp_count_before = len(list(session.scalars(select(TrainingCompletion).where(TrainingCompletion.tenant_id == tenant.id)).all()))

    payload = LmsCompletionPayload(
        event_id=f"evt-part-ctrl-{uuid4().hex[:8]}",
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
        assignment_id=str(assign.id),
    )

    with pytest.raises(Exception) as exc:
        record_training_completion(
            session,
            codec,
            tenant_id=tenant.id,
            payload=payload,
        )
    assert "422" in str(exc.value)

    # Without session rollback:
    # 1. session.new must NOT contain any EvidenceItem or TrainingCompletion
    new_evidence = [obj for obj in session.new if isinstance(obj, (EvidenceItem, TrainingCompletion))]
    assert len(new_evidence) == 0, "EvidenceItem or TrainingCompletion was created/flushed before validation!"

    # 2. Persisted counts must remain strictly unchanged
    ev_count_after = len(list(session.scalars(select(EvidenceItem).where(EvidenceItem.tenant_id == tenant.id)).all()))
    comp_count_after = len(list(session.scalars(select(TrainingCompletion).where(TrainingCompletion.tenant_id == tenant.id)).all()))
    assert ev_count_after == ev_count_before
    assert comp_count_after == comp_count_before

    # 3. Assignment status remains ASSIGNED
    session.refresh(assign)
    assert assign.status == AssignmentStatus.ASSIGNED


def test_historical_invalid_full_control_pair_rejected_before_evidence_creation(
    session: Session,
) -> None:
    tenant, user, _, _, _ = setup_lms_environment(session)
    codec = make_test_codec()

    # Create assignment with non-existent canonical control
    assign = TrainingAssignment(
        id=uuid4(),
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        user_id=user.id,
        workforce_email=user.email,
        due_date=datetime.now(UTC) + timedelta(days=14),
        status=AssignmentStatus.ASSIGNED,
        control_id=uuid4(),
        control_type="canonical",  # non-existent control
    )
    session.add(assign)
    session.commit()

    payload = LmsCompletionPayload(
        event_id=f"evt-bad-ctrl-{uuid4().hex[:8]}",
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
        assignment_id=str(assign.id),
    )

    with pytest.raises(Exception) as exc:
        record_training_completion(
            session,
            codec,
            tenant_id=tenant.id,
            payload=payload,
        )
    assert "422" in str(exc.value)

    new_evidence = [obj for obj in session.new if isinstance(obj, (EvidenceItem, TrainingCompletion))]
    assert len(new_evidence) == 0


def test_direct_service_empty_tenant_id_rejected(
    session: Session,
) -> None:
    tenant, user, _, _, _ = setup_lms_environment(session)
    codec = make_test_codec()

    assign = create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=datetime.now(UTC) + timedelta(days=14),
    )
    session.commit()

    # Empty string tenant_id
    payload = LmsCompletionPayload(
        event_id=f"evt-empty-tenant-{uuid4().hex[:8]}",
        tenant_id="",
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
        assignment_id=str(assign.id),
    )
    with pytest.raises(Exception) as exc:
        record_training_completion(
            session,
            codec,
            tenant_id=tenant.id,
            payload=payload,
        )
    assert "422" in str(exc.value)


def test_direct_service_nonfinite_score_rejected(
    session: Session,
) -> None:
    tenant, user, _, _, _ = setup_lms_environment(session)
    codec = make_test_codec()

    assign = create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=datetime.now(UTC) + timedelta(days=14),
    )
    session.commit()

    for bad_score in [float("inf"), float("-inf"), float("nan"), -10.0, 150.0]:
        payload = LmsCompletionPayload(
            event_id=f"evt-inf-score-{uuid4().hex[:8]}",
            tenant_id=str(tenant.id),
            course_id="SEC-TEST-001",
            course_version="1.0",
            learner_email=user.email,
            completed_at=datetime.now(UTC).isoformat(),
            passed=True,
            assignment_id=str(assign.id),
            score=bad_score,
        )
        with pytest.raises(Exception) as exc:
            record_training_completion(
                session,
                codec,
                tenant_id=tenant.id,
                payload=payload,
            )
        assert "422" in str(exc.value)


def test_direct_service_replay_altered_timestamp_rejected(
    session: Session,
) -> None:
    tenant, user, _, _, _ = setup_lms_environment(session)
    codec = make_test_codec()

    assign = create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=datetime.now(UTC) + timedelta(days=14),
    )
    session.commit()

    event_id = f"evt-replay-time-{uuid4().hex[:8]}"
    t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
    payload1 = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=t0.isoformat(),
        passed=True,
        assignment_id=str(assign.id),
        score=90.0,
    )
    comp1, ev1, is_new1 = record_training_completion(
        session,
        codec,
        tenant_id=tenant.id,
        payload=payload1,
    )
    assert is_new1 is True

    # Same event_id with completed_at shifted 90 days
    t_shifted = t0 + timedelta(days=90)
    payload_shifted = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=t_shifted.isoformat(),
        passed=True,
        assignment_id=str(assign.id),
        score=90.0,
    )
    with pytest.raises(Exception) as exc:
        record_training_completion(
            session,
            codec,
            tenant_id=tenant.id,
            payload=payload_shifted,
        )
    assert "409" in str(exc.value) or "conflict" in str(exc.value).lower()


def test_direct_service_replay_altered_score_nullability_rejected(
    session: Session,
) -> None:
    tenant, user, _, _, _ = setup_lms_environment(session)
    codec = make_test_codec()

    assign = create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=datetime.now(UTC) + timedelta(days=14),
    )
    session.commit()

    event_id = f"evt-replay-score-{uuid4().hex[:8]}"
    t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
    payload_with_score = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=t0.isoformat(),
        passed=True,
        assignment_id=str(assign.id),
        score=85.0,
    )
    record_training_completion(
        session,
        codec,
        tenant_id=tenant.id,
        payload=payload_with_score,
    )

    # Replay with score changed to None
    payload_null_score = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=t0.isoformat(),
        passed=True,
        assignment_id=str(assign.id),
        score=None,
    )
    with pytest.raises(Exception) as exc:
        record_training_completion(
            session,
            codec,
            tenant_id=tenant.id,
            payload=payload_null_score,
        )
    assert "409" in str(exc.value) or "conflict" in str(exc.value).lower()


def test_direct_service_replay_altered_certificate_rejected(
    session: Session,
) -> None:
    tenant, user, _, _, _ = setup_lms_environment(session)
    codec = make_test_codec()

    assign = create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=datetime.now(UTC) + timedelta(days=14),
    )
    session.commit()

    event_id = f"evt-replay-cert-{uuid4().hex[:8]}"
    t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
    payload_cert = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=t0.isoformat(),
        passed=True,
        assignment_id=str(assign.id),
        certificate_id="CERT-ALPHA",
    )
    record_training_completion(
        session,
        codec,
        tenant_id=tenant.id,
        payload=payload_cert,
    )

    # Replay with certificate_id changed
    payload_altered_cert = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=t0.isoformat(),
        passed=True,
        assignment_id=str(assign.id),
        certificate_id="CERT-BETA",
    )
    with pytest.raises(Exception) as exc:
        record_training_completion(
            session,
            codec,
            tenant_id=tenant.id,
            payload=payload_altered_cert,
        )
    assert "409" in str(exc.value) or "conflict" in str(exc.value).lower()


def test_active_course_version_ambiguity_rejected_for_new_completion(
    session: Session,
) -> None:
    tenant, user, _, _, _ = setup_lms_environment(session)
    codec = make_test_codec()

    # Assignment created when only v1.0 was active
    assign = create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        workforce_email=user.email,
        due_date=datetime.now(UTC) + timedelta(days=14),
    )
    session.commit()

    # Now activate v2.0 as well (multiple active versions for SEC-TEST-001)
    v2_course = TrainingCourse(
        id=uuid4(),
        tenant_id=tenant.id,
        course_id="SEC-TEST-001",
        version="2.0",
        title="Security Awareness 2026 v2",
        description="Updated 2026 compliance course",
        provider="lms",
        duration_minutes=45,
        validity_period_days=365,
        is_active=True,
    )
    session.add(v2_course)
    session.commit()

    # Attempt new completion for v1.0
    payload = LmsCompletionPayload(
        event_id=f"evt-ambig-v1-{uuid4().hex[:8]}",
        tenant_id=str(tenant.id),
        course_id="SEC-TEST-001",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
        assignment_id=str(assign.id),
    )

    with pytest.raises(Exception) as exc:
        record_training_completion(
            session,
            codec,
            tenant_id=tenant.id,
            payload=payload,
        )
    assert "409" in str(exc.value) or "ambiguous" in str(exc.value).lower()
