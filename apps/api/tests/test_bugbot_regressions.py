import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from conformly.compliance.models import ComplianceTask, TaskStatus
from conformly.compliance.service import (
    ComplianceService,
    InvalidStateTransitionError,
    InvalidTenantReferenceError,
)
from conformly.frameworks.models import (
    AdoptionStatus,
    ControlEntityType,
    FrameworkVersion,
    MappingType,
    ReleaseState,
    TenantFrameworkAdoption,
)
from conformly.frameworks.service import FrameworkVersionNotFoundError
from conformly.main import app
from conformly.storage.models import StoredFileStatus
from conformly.storage.providers import MemoryStorageProvider
from conformly.storage.service import StorageService
from conformly.storage.upload_limit import UploadLimitMiddleware
from tests.test_compliance_service import make_tenant_context
from tests.test_framework_tenant_adoptions import make_tenant, setup_released_framework
from tests.test_storage_service import create_tenant_and_user, make_encryption


def test_compare_requires_authentication(session):
    from conformly.auth.tokens import get_token_verifier
    from conformly.db.session import get_db

    app.dependency_overrides[get_token_verifier] = lambda: None
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as client:
        result = client.get(
            f"/v1/frameworks/{uuid4()}/compare",
            params={
                "source_version_id": str(uuid4()),
                "target_version_id": str(uuid4()),
            },
        )
    app.dependency_overrides.clear()
    assert result.status_code == 401


def test_compare_does_not_expose_drafts(session):
    service, framework, v1, v2, _, _ = setup_released_framework(session)
    version = session.get(FrameworkVersion, v2)
    version.release_state = ReleaseState.DRAFT
    session.flush()
    with pytest.raises(FrameworkVersionNotFoundError):
        service.compare_versions(framework, v1, v2)
    assert service.compare_versions(framework, v1, v2, is_platform_admin=True)


@pytest.mark.parametrize("field", ["assignee_user_id", "evidence_id", "policy_id"])
def test_task_rejects_foreign_references(session, test_codec, field):
    _, _, principal, context = make_tenant_context(session)
    _, other, other_principal, other_context = make_tenant_context(session)
    service = ComplianceService(session, test_codec)
    references = {
        "assignee_user_id": other.id,
        "evidence_id": service.create_evidence(
            other_principal,
            other_context,
            title="Other",
            description="Other",
            owner_user_id=other.id,
        ).id,
        "policy_id": service.create_policy(
            other_principal, other_context, title="Other", description="Other"
        ).id,
    }
    with pytest.raises(InvalidTenantReferenceError):
        service.create_task(
            principal,
            context,
            title="Task",
            description="Test",
            due_date=datetime.now(UTC),
            **{field: references[field]},  # type: ignore[arg-type]
        )


def test_task_completion_and_reopening(session, test_codec):
    _, _, principal, context = make_tenant_context(session)
    service = ComplianceService(session, test_codec)
    task = service.create_task(
        principal, context, title="Task", description="Test", due_date=datetime.now(UTC)
    )
    service.update_task(
        principal, context, task.id, expected_version=1, status=TaskStatus.COMPLETED
    )
    assert task.completed_at and task.completed_by_user_id == principal.user_id
    with pytest.raises(InvalidStateTransitionError):
        service.complete_task(principal, context, task.id, expected_version=2)
    service.update_task(principal, context, task.id, expected_version=2, status=TaskStatus.PENDING)
    assert task.completed_at is None and task.completed_by_user_id is None
    service.update_task(
        principal, context, task.id, expected_version=3, status=TaskStatus.CANCELLED
    )
    with pytest.raises(InvalidStateTransitionError):
        service.complete_task(principal, context, task.id, expected_version=4)


@pytest.mark.parametrize("operation", ["evidence", "finding", "task_update", "evidence_update"])
def test_assignment_rejects_foreign_member(session, test_codec, operation):
    _, user, principal, context = make_tenant_context(session)
    _, foreign, _, _ = make_tenant_context(session)
    service = ComplianceService(session, test_codec)
    with pytest.raises(InvalidTenantReferenceError):
        if operation == "evidence":
            service.create_evidence(
                principal, context, title="Test", description="Test", owner_user_id=foreign.id
            )
        elif operation == "finding":
            service.create_finding(
                principal, context, title="Test", description="Test", owner_user_id=foreign.id
            )
        elif operation == "task_update":
            task = service.create_task(
                principal, context, title="Test", description="Test", due_date=datetime.now(UTC)
            )
            service.update_task(
                principal, context, task.id, expected_version=1, assignee_user_id=foreign.id
            )
        else:
            evidence = service.create_evidence(
                principal, context, title="Test", description="Test", owner_user_id=user.id
            )
            service.update_evidence(
                principal, context, evidence.id, expected_version=1, owner_user_id=foreign.id
            )


@pytest.mark.parametrize("source", [True, False])
def test_mapping_rejects_other_tenant_custom_control(session, source):
    service, _, _, _, canonical, _ = setup_released_framework(session)
    _, _, context, principal = make_tenant(session, "Tenant")
    _, _, foreign_context, foreign_principal = make_tenant(session, "Foreign")
    custom = service.create_custom_control(
        foreign_principal, foreign_context, "C-1", "Test", "Test", "Test", None, "create"
    )
    endpoints = [(ControlEntityType.CUSTOM, custom.id), (ControlEntityType.CANONICAL, canonical.id)]
    if not source:
        endpoints.reverse()
    with pytest.raises(ValueError, match="reference"):
        service.create_control_mapping(
            principal, context, *endpoints[0], *endpoints[1], MappingType.SATISFIES, None, "test"
        )


def test_version_predicate_rejects_second_writer(session, test_codec):
    _, _, principal, context = make_tenant_context(session)
    task = ComplianceService(session, test_codec).create_task(
        principal, context, title="Task", description="Test", due_date=datetime.now(UTC)
    )
    task_id = task.id
    session.commit()
    with Session(session.get_bind()) as first, Session(session.get_bind()) as second:
        a = first.get(ComplianceTask, task_id)
        b = second.get(ComplianceTask, task_id)
        assert a is not None and b is not None
        a.title = "Winner"
        a.version += 1
        first.commit()
        b.title = "Stale"
        b.version += 1
        with pytest.raises(StaleDataError):
            second.commit()


def test_duplicate_active_adoption_rejected(session):
    _, framework, v1, v2, _, _ = setup_released_framework(session)
    tenant, user, _, _ = make_tenant(session, "Tenant")
    for version in (v1, v2):
        session.add(
            TenantFrameworkAdoption(
                tenant_id=tenant.id,
                framework_id=framework,
                framework_version_id=version,
                status=AdoptionStatus.ACTIVE,
                adopted_at=datetime.now(UTC),
                adopted_by_user_id=user.id,
            )
        )
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("source", [True, False])
def test_mapping_rejects_unknown_endpoint(session, source):
    service, _, _, _, c1, _ = setup_released_framework(session)
    _, _, context, principal = make_tenant(session, "Tenant")
    with pytest.raises(ValueError, match="reference"):
        service.create_control_mapping(
            principal,
            context,
            ControlEntityType.CANONICAL,
            uuid4() if source else c1.id,
            ControlEntityType.CANONICAL,
            c1.id if source else uuid4(),
            MappingType.SATISFIES,
            None,
            "test",
        )


def test_delete_rollback_and_retry(session):
    _, _, context, principal = create_tenant_and_user(session)
    provider = MemoryStorageProvider()
    service = StorageService(session, provider, make_encryption())
    file = service.upload_file(
        principal,
        context,
        filename="test.txt",
        content=b"data",
        classification="Internal",
        content_type="text/plain",
        request_id="upload",
    )
    file_id, key = file.id, file.object_key
    session.commit()
    service.delete_file(principal, context, file_id=file_id, request_id="delete")
    with pytest.raises(RuntimeError):
        service.finalize_pending_deletions(principal, context, request_id="unsafe")
    session.rollback()
    assert provider.object_exists(key)
    assert (
        service.get_file_metadata(principal, context, file_id=file_id).status
        == StoredFileStatus.ACTIVE
    )
    service.delete_file(principal, context, file_id=file_id, request_id="delete")
    session.commit()
    # Simulate a crash after object removal, before completion is committed.
    service.finalize_pending_deletions(principal, context, request_id="cleanup")
    session.rollback()
    service.finalize_pending_deletions(principal, context, request_id="retry")
    session.commit()
    assert not provider.object_exists(key)


@pytest.mark.parametrize("headers", [[], [(b"content-length", b"100")]])
def test_upload_limit_before_parsing(headers):
    async def run():
        called = False
        sent = []

        async def downstream(scope, receive, send):
            nonlocal called
            called = True

        async def receive():
            return {"type": "http.request", "body": b"x" * 11, "more_body": False}

        async def send(message):
            sent.append(message)

        await UploadLimitMiddleware(downstream, 10)(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/tenants/id/files",
                "headers": headers,
            },
            receive,
            send,
        )
        assert not called
        assert sent[0]["status"] == 413

    asyncio.run(run())  # type: ignore[no-untyped-call]
