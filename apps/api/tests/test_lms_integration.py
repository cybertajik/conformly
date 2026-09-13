import time
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.auth.dependencies import (
    get_current_principal,
    get_tenant_context,
)
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.compliance.models import EvidenceControlLink, EvidenceStatus
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.fields import EncryptedFieldCodec, get_encrypted_field_codec
from conformly.crypto.providers import AES256GCMProvider, LocalKeyManagementProvider
from conformly.db.session import get_db
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User
from conformly.integrations.service import create_integration_credential
from conformly.lms.client import LmsPartnerSimulator
from conformly.lms.contract import LmsAssignmentPayload, LmsCompletionPayload
from conformly.lms.models import AssignmentStatus, TrainingAssignment
from conformly.lms.service import (
    create_training_assignment,
    create_training_course,
    list_training_assignments,
    list_training_courses,
    record_training_completion,
)
from conformly.main import app


def make_test_codec() -> EncryptedFieldCodec:
    import base64

    b64_key = base64.b64encode(b"\x07" * 32).decode("ascii")
    kms = LocalKeyManagementProvider({"v1": b64_key}, "v1")
    envelope = EnvelopeEncryptionService(AES256GCMProvider(), kms)
    return EncryptedFieldCodec(envelope)


def create_user_and_tenant(
    session: Session, role: Role = Role.OWNER
) -> tuple[User, Tenant, Principal, TenantContext]:
    tenant = Tenant(
        name="LMS Test Tenant",
        slug=f"lms-{uuid4().hex[:8]}",
        status=TenantStatus.ACTIVE,
    )
    user = User(
        oidc_issuer="https://identity.conformly.de",
        oidc_subject=str(uuid4()),
        email=f"employee-{uuid4().hex[:8]}@example.com",
        display_name="Security Learner",
    )
    session.add_all([tenant, user])
    session.flush()

    membership = Membership(
        tenant_id=tenant.id,
        user_id=user.id,
        role=role,
        status=MembershipStatus.ACTIVE,
    )
    session.add(membership)
    session.commit()

    principal = Principal(user_id=user.id, mfa_verified=True)
    context = TenantContext(tenant_id=tenant.id, user_id=user.id, role=role)
    return user, tenant, principal, context


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    test_codec = make_test_codec()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_encrypted_field_codec] = lambda: test_codec
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_lms_courses_and_assignments_service(session: Session) -> None:
    user, tenant, _, _ = create_user_and_tenant(session)

    # 1. Register course in catalog
    course = create_training_course(
        session,
        tenant_id=tenant.id,
        course_id="SEC-AWARE-2026",
        version="1.0",
        title="Annual Information Security Awareness",
        description="Comprehensive ISO 27001 & GDPR security awareness training.",
        duration_minutes=45,
        validity_period_days=365,
    )
    session.commit()

    assert course.course_id == "SEC-AWARE-2026"
    assert course.duration_minutes == 45

    courses = list_training_courses(session, tenant.id)
    assert len(courses) == 1
    assert courses[0].title == "Annual Information Security Awareness"

    # 2. Create assignment mapped to a control
    mock_control_id = uuid4()
    due_date = datetime.now(UTC) + timedelta(days=14)
    assignment = create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-AWARE-2026",
        workforce_email=user.email,
        due_date=due_date,
        user_id=user.id,
        control_id=mock_control_id,
        control_type="canonical",
        assigned_by_user_id=user.id,
    )
    session.commit()

    assert assignment.status == AssignmentStatus.ASSIGNED
    assert assignment.workforce_email == user.email
    assert assignment.control_id == mock_control_id

    assignments = list_training_assignments(session, tenant.id)
    assert len(assignments) == 1
    assert assignments[0].id == assignment.id


def test_lms_partner_contract_and_evidence_generation(session: Session) -> None:
    user, tenant, _, _ = create_user_and_tenant(session)
    codec = make_test_codec()
    lms_partner = LmsPartnerSimulator(provider_name="Enterprise-LMS")

    # 1. Register course and assignment
    _course = create_training_course(
        session,
        tenant_id=tenant.id,
        course_id="SEC-AWARE-2026",
        title="Information Security Awareness",
        description="Core awareness training",
        validity_period_days=365,
    )
    mock_control_id = uuid4()
    assignment = create_training_assignment(
        session,
        tenant_id=tenant.id,
        course_id="SEC-AWARE-2026",
        workforce_email=user.email,
        due_date=datetime.now(UTC) + timedelta(days=30),
        user_id=user.id,
        control_id=mock_control_id,
        control_type="canonical",
    )
    session.commit()

    # 2. Dispatch assignment to external LMS via contract
    dispatch_result = lms_partner.dispatch_assignment(
        LmsAssignmentPayload(
            assignment_id=str(assignment.id),
            tenant_id=str(tenant.id),
            course_id=assignment.course_id,
            learner_email=assignment.workforce_email,
            learner_name=user.display_name or user.email,
            due_date=assignment.due_date.isoformat(),
            callback_url=f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        )
    )
    assert dispatch_result["status"] == "enrolled"
    assert len(lms_partner.received_assignments) == 1

    # 3. Simulate learner completing the course on external LMS
    event_id = f"lms-comp-{uuid4().hex[:8]}"
    completion_payload = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SEC-AWARE-2026",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
        assignment_id=str(assignment.id),
        score=95.0,
        certificate_id="CERT-ISO27001-9876",
    )

    completion, evidence, is_new = record_training_completion(
        session,
        codec,
        tenant_id=tenant.id,
        payload=completion_payload,
    )
    session.commit()

    assert is_new is True
    assert completion.score == 95.0
    assert completion.certificate_id == "CERT-ISO27001-9876"

    # Verify assignment status progressed to COMPLETED
    reloaded_assignment = session.get(TrainingAssignment, assignment.id)
    assert reloaded_assignment is not None
    assert reloaded_assignment.status == AssignmentStatus.COMPLETED

    # Verify automated evidence creation
    assert evidence is not None
    assert evidence.status == EvidenceStatus.VALID
    assert "Information Security Awareness" in evidence.title
    assert evidence.valid_until is not None

    # Verify evidence was linked to the mapped compliance control
    link_stmt = select(EvidenceControlLink).where(
        EvidenceControlLink.evidence_id == evidence.id,
        EvidenceControlLink.control_id == mock_control_id,
    )
    control_link = session.scalar(link_stmt)
    assert control_link is not None
    assert control_link.tenant_id == tenant.id

    # 4. Idempotent second call with same event_id does not duplicate records
    dup_comp, dup_ev, dup_is_new = record_training_completion(
        session,
        codec,
        tenant_id=tenant.id,
        payload=completion_payload,
    )
    assert dup_is_new is False
    assert dup_comp.id == completion.id


def test_lms_signed_webhook_api_endpoint_flow(session: Session, client: TestClient) -> None:
    user, tenant, principal, context = create_user_and_tenant(session, role=Role.ADMINISTRATOR)
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_tenant_context] = lambda: context
    codec = make_test_codec()
    lms_partner = LmsPartnerSimulator()

    # 1. Issue tenant LMS integration credential
    cred_res = create_integration_credential(
        session,
        codec,
        tenant_id=tenant.id,
        name="LMS Webhook Callback Credential",
        scopes=["lms:write"],
    )
    session.commit()

    # 2. Register course & assignment via API
    course_resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/courses",
        json={
            "course_id": "SOC2-CC2.1-SEC",
            "title": "SOC 2 Security Principles",
            "description": "Organizational security controls training",
            "duration_minutes": 30,
        },
    )
    assert course_resp.status_code == 201

    mock_control_id = uuid4()
    assign_resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/assignments",
        json={
            "course_id": "SOC2-CC2.1-SEC",
            "workforce_email": user.email,
            "due_date": (datetime.now(UTC) + timedelta(days=15)).isoformat(),
            "control_id": str(mock_control_id),
            "control_type": "canonical",
        },
    )
    assert assign_resp.status_code == 201
    assignment_id = assign_resp.json()["id"]

    # 3. LMS Partner generates signed webhook payload
    event_id = f"soc2-comp-{uuid4().hex[:8]}"
    completion_payload = LmsCompletionPayload(
        event_id=event_id,
        tenant_id=str(tenant.id),
        course_id="SOC2-CC2.1-SEC",
        course_version="1.0",
        learner_email=user.email,
        completed_at=datetime.now(UTC).isoformat(),
        passed=True,
        assignment_id=assignment_id,
        score=100.0,
        certificate_id="SOC2-PASS-001",
    )
    raw_body, headers = lms_partner.generate_signed_completion_event(
        completion_payload,
        signing_secret=cred_res.signing_secret,
        key_id=cred_res.credential.key_id,
    )

    # 4. Deliver signed webhook callback
    webhook_resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert webhook_resp.status_code == 200
    res_data = webhook_resp.json()
    assert res_data["status"] == "completed"
    assert res_data["verified"] is True
    assert res_data["evidence_id"] is not None

    # 5. Verify assignment marked completed
    list_assign = client.get(f"/v1/tenants/{tenant.id}/lms/assignments")
    assert list_assign.status_code == 200
    assert list_assign.json()[0]["status"] == "completed"

    # 6. Replay test: re-sending identical callback gives idempotent response
    replay_resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=raw_body,
        headers=headers,
    )
    assert replay_resp.status_code == 200
    assert replay_resp.json()["status"] == "idempotent_replay"

    # 7. Replay attack with expired timestamp (> 300 seconds) is rejected
    expired_raw, expired_headers = lms_partner.generate_signed_completion_event(
        LmsCompletionPayload(
            event_id=f"exp-{uuid4().hex[:8]}",
            tenant_id=str(tenant.id),
            course_id="SOC2-CC2.1-SEC",
            course_version="1.0",
            learner_email=user.email,
            completed_at=datetime.now(UTC).isoformat(),
            passed=True,
        ),
        signing_secret=cred_res.signing_secret,
        timestamp=int(time.time()) - 600,  # 10 minutes ago
        key_id=cred_res.credential.key_id,
    )
    expired_resp = client.post(
        f"/v1/tenants/{tenant.id}/lms/webhooks/completion",
        content=expired_raw,
        headers=expired_headers,
    )
    assert expired_resp.status_code == 400
    assert "tolerance window" in expired_resp.json()["detail"]

    # 8. Never trust browser redirect (GET method rejected)
    get_resp = client.get(f"/v1/tenants/{tenant.id}/lms/webhooks/completion?completed=true")
    assert get_resp.status_code == 405  # Method Not Allowed
