"""Unit tests for Customer Control Work & Evidence Pinning Service Layer."""

import hashlib
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.compliance.models import EvidenceItem, EvidenceRevision, EvidenceStatus
from conformly.config import get_settings
from conformly.crypto.policy import DataClassification
from conformly.customer_demo.evaluator import compute_answers_digest, compute_evaluation_digest
from conformly.customer_demo.fixture import (
    BUNDLE_V1_DIGEST,
    BUNDLE_2_V1_DIGEST,
    EVALUATOR_VERSION,
    PACK_VERSION_V1_ID,
    PACK_2_VERSION_V1_ID,
    CTRL_1_ID,
    CTRL_1_VER_ID,
)
from conformly.customer_demo.models import (
    CustomerDemoAdoption,
    CustomerDemoAnswers,
    CustomerDemoEvaluation,
    CustomerDemoWorkspace,
)
from conformly.customer_demo.policy import CustomerDemoAdmissionError
from conformly.customer_demo.service import evaluate_answers, adopt_evaluation
from conformly.customer_demo.work_models import (
    CustomerControlEvidenceLink,
    CustomerControlWork,
    CustomerControlWorkEvent,
)
from conformly.customer_demo.work_scanner import (
    StrictEvidenceMalwareScanner,
    StrictScanUnavailableError,
)
from conformly.customer_demo.work_schemas import (
    CreateEvidenceRequest,
    CreateLinkRequest,
    CreateReviewRequest,
    InitializeWorkRequest,
    PatchWorkRequest,
)
from conformly.customer_demo.work_service import (
    CustomerControlWorkService,
)
from conformly.db.base import Base
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
from conformly.storage.validation import MalwareDetectedError


class MockSuccessfulScanner(StrictEvidenceMalwareScanner):
    """Test scanner subclass simulating successful ClamAV verification."""

    def __init__(self) -> None:
        super().__init__(clamav_host="127.0.0.1", clamav_port=3310)
        self.scanned_items: list[tuple[bytes, str]] = []

    def scan(self, data: bytes, filename: str) -> None:
        self.scanned_items.append((data, filename))


@pytest.fixture(autouse=True)
def enable_customer_demo_feature(monkeypatch):
    """Enable customer demo feature in test environment."""
    cfg = get_settings()
    monkeypatch.setattr(cfg, "enable_customer_demo", True)
    monkeypatch.setattr(cfg, "environment", "test")


@pytest.fixture
def db_session():
    """In-memory SQLite session with all models created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def test_setup(db_session: Session):
    """Seed test tenant, users, entitlement, and adopted workspace."""
    tenant_id = uuid4()
    owner_id = uuid4()
    mgr_id = uuid4()
    ctrl_owner_id = uuid4()
    foreign_user_id = uuid4()
    now = datetime.now(UTC)

    tenant = Tenant(
        id=tenant_id,
        name="Test Tenant",
        slug=f"tenant-{tenant_id}",
        status=TenantStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    db_session.add(tenant)

    owner_user = User(
        id=owner_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="sub-owner",
        email="owner@example.com",
        display_name="Alice Owner",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    mgr_user = User(
        id=mgr_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="sub-mgr",
        email="mgr@example.com",
        display_name="Bob Manager",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    ctrl_owner_user = User(
        id=ctrl_owner_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="sub-ctrl",
        email="ctrl@example.com",
        display_name="Carol ControlOwner",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    foreign_user = User(
        id=foreign_user_id,
        oidc_issuer="https://auth.example.com",
        oidc_subject="sub-foreign",
        email="foreign@example.com",
        display_name="Foreign User",
        status=UserStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([owner_user, mgr_user, ctrl_owner_user, foreign_user])

    # Memberships
    m_owner = Membership(
        tenant_id=tenant_id,
        user_id=owner_id,
        role=Role.OWNER,
        status=MembershipStatus.ACTIVE,
        is_workforce=False,
        is_external_advisor=False,
        created_at=now,
        updated_at=now,
    )
    m_mgr = Membership(
        tenant_id=tenant_id,
        user_id=mgr_id,
        role=Role.COMPLIANCE_MANAGER,
        status=MembershipStatus.ACTIVE,
        is_workforce=False,
        is_external_advisor=False,
        created_at=now,
        updated_at=now,
    )
    m_ctrl = Membership(
        tenant_id=tenant_id,
        user_id=ctrl_owner_id,
        role=Role.CONTROL_OWNER,
        status=MembershipStatus.ACTIVE,
        is_workforce=False,
        is_external_advisor=False,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([m_owner, m_mgr, m_ctrl])

    # Entitlement with evidence enabled
    ent = TenantEntitlement(
        tenant_id=tenant_id,
        plan_code="tier_a",
        enabled_modules=["frameworks", "evidence", "tasks"],
        max_members=100,
        max_storage_bytes=10000000,
        allowed_framework_slugs=["*"],
        effective_from=now - timedelta(days=1),
        effective_until=now + timedelta(days=365),
    )
    db_session.add(ent)

    # Adopted workspace setup
    ws = CustomerDemoWorkspace(
        tenant_id=tenant_id,
        current_revision=1,
        selection_revision=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(ws)

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
    db_session.add(answers)

    eval_digest = compute_evaluation_digest(
        answer_digest=ans_digest,
        answer_revision=1,
        bundle_digest=BUNDLE_V1_DIGEST,
        evaluator_version=EVALUATOR_VERSION,
        pack_version_id=PACK_VERSION_V1_ID,
        results=[],
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
        results=[],
        actor_id=owner_id,
        created_at=now,
    )
    db_session.add(evaluation)

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
    db_session.add(adoption)
    db_session.commit()

    principal = Principal(user_id=owner_id, mfa_verified=True)
    tenant_context = TenantContext(tenant_id=tenant_id, role=Role.OWNER, user_id=owner_id)

    return {
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "mgr_id": mgr_id,
        "ctrl_owner_id": ctrl_owner_id,
        "foreign_user_id": foreign_user_id,
        "adoption_id": adopt_id,
        "evaluation_id": eval_id,
        "principal": principal,
        "tenant_context": tenant_context,
    }


def _seed_stored_file(
    session: Session, tenant_id: UUID, user_id: UUID, content: bytes = b"test evidence content"
) -> StoredFile:
    """Helper to seed an active stored file in database."""
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


def test_get_owners_directory(db_session: Session, test_setup: dict[str, Any]):
    """Verify owner directory returns eligible owners and omits sensitive identity data."""
    scanner = MockSuccessfulScanner()
    service = CustomerControlWorkService(db_session, scanner=scanner)

    res = service.get_owners(test_setup["principal"], test_setup["tenant_context"])
    assert res.total == 3
    user_ids = {item.user_id for item in res.items}
    assert test_setup["owner_id"] in user_ids
    assert test_setup["mgr_id"] in user_ids
    assert test_setup["ctrl_owner_id"] in user_ids
    assert test_setup["foreign_user_id"] not in user_ids

    # Verify no email or subject present in DTO
    for item in res.items:
        assert hasattr(item, "display_name")
        assert not hasattr(item, "email")
        assert not hasattr(item, "oidc_subject")


def test_initialize_control_work_lifecycle(db_session: Session, test_setup: dict[str, Any]):
    """Verify initializing control work items in sorted order and idempotent replay."""
    scanner = MockSuccessfulScanner()
    service = CustomerControlWorkService(db_session, scanner=scanner)

    op_id = uuid4()
    req = InitializeWorkRequest(
        operation_id=op_id,
        adoption_id=test_setup["adoption_id"],
        expected_selection_revision=1,
        expected_answer_revision=1,
    )

    res = service.initialize_work(
        test_setup["principal"],
        test_setup["tenant_context"],
        req,
        request_id="req-init-1",
    )
    # Pack V1 has 2 controls
    assert res.total == 2
    assert len(res.items) == 2
    assert res.is_current is True
    assert res.is_stale is False

    # Check work items in DB
    work_items = (
        db_session.query(CustomerControlWork)
        .filter(CustomerControlWork.tenant_id == test_setup["tenant_id"])
        .order_by(CustomerControlWork.control_version_id.asc())
        .all()
    )
    assert len(work_items) == 2
    assert work_items[0].version == 1

    # Check INITIALIZED events created
    events = (
        db_session.query(CustomerControlWorkEvent)
        .filter(CustomerControlWorkEvent.tenant_id == test_setup["tenant_id"])
        .all()
    )
    assert len(events) == 2
    for e in events:
        assert e.event_type == "INITIALIZED"
        assert e.work_revision == 1

    # Idempotent repeat: re-initializing returns same items without error or duplication
    res2 = service.initialize_work(
        test_setup["principal"],
        test_setup["tenant_context"],
        req,
        request_id="req-init-2",
    )
    assert res2.total == 2
    assert len(db_session.query(CustomerControlWork).all()) == 2


def test_patch_work_assignment_and_replay(db_session: Session, test_setup: dict[str, Any]):
    """Verify owner assignment, due date update, optimistic locking, and idempotent replay."""
    scanner = MockSuccessfulScanner()
    service = CustomerControlWorkService(db_session, scanner=scanner)

    # Initialize first
    init_req = InitializeWorkRequest(
        operation_id=uuid4(),
        adoption_id=test_setup["adoption_id"],
        expected_selection_revision=1,
        expected_answer_revision=1,
    )
    init_res = service.initialize_work(
        test_setup["principal"],
        test_setup["tenant_context"],
        init_req,
        request_id="req-init",
    )
    work_id = init_res.items[0].id

    # Update owner and due date
    patch_op_id = uuid4()
    patch_req = PatchWorkRequest(
        operation_id=patch_op_id,
        expected_selection_revision=1,
        expected_answer_revision=1,
        expected_work_version=1,
        owner_user_id=test_setup["ctrl_owner_id"],
        due_date=date(2027, 1, 15),
    )
    receipt = service.patch_work(
        test_setup["principal"],
        test_setup["tenant_context"],
        work_id,
        patch_req,
        request_id="req-patch-1",
    )
    assert receipt.replayed is False
    assert receipt.applied_work_version == 2
    assert receipt.current_work.owner_user_id == test_setup["ctrl_owner_id"]
    assert receipt.current_work.owner_display_name == "Carol ControlOwner"
    assert receipt.current_work.due_date == date(2027, 1, 15)

    # Exact replay of same operation_id
    receipt_replay = service.patch_work(
        test_setup["principal"],
        test_setup["tenant_context"],
        work_id,
        patch_req,
        request_id="req-patch-2",
    )
    assert receipt_replay.replayed is True
    assert receipt_replay.applied_work_version == 2

    # Collision: same operation_id with changed payload -> 409
    collision_req = PatchWorkRequest(
        operation_id=patch_op_id,
        expected_selection_revision=1,
        expected_answer_revision=1,
        expected_work_version=2,
        owner_user_id=test_setup["mgr_id"],
        due_date=date(2027, 2, 20),
    )
    with pytest.raises(HTTPException) as exc:
        service.patch_work(
            test_setup["principal"],
            test_setup["tenant_context"],
            work_id,
            collision_req,
            request_id="req-patch-3",
        )
    assert exc.value.status_code == 409


def test_create_and_pin_evidence_and_reuse(db_session: Session, test_setup: dict[str, Any]):
    """Verify evidence upload/pinning, snapshot digest, deliberate reuse, and independent review."""
    scanner = MockSuccessfulScanner()
    service = CustomerControlWorkService(db_session, scanner=scanner)

    # Initialize work
    init_res = service.initialize_work(
        test_setup["principal"],
        test_setup["tenant_context"],
        InitializeWorkRequest(
            operation_id=uuid4(),
            adoption_id=test_setup["adoption_id"],
            expected_selection_revision=1,
            expected_answer_revision=1,
        ),
        request_id="req-init",
    )
    work1 = init_res.items[0]
    work2 = init_res.items[1]

    # Seed stored file
    file_content = b"Encrypted test file contents for compliance."
    stored_file = _seed_stored_file(
        db_session, test_setup["tenant_id"], test_setup["owner_id"], file_content
    )

    # Mock StorageService.download_file
    with patch("conformly.customer_demo.work_service.StorageService") as MockStorage:
        instance = MockStorage.return_value
        instance.download_file.return_value = (stored_file, file_content)

        # Pin evidence to Work 1
        ev_op_id = uuid4()
        ev_req = CreateEvidenceRequest(
            operation_id=ev_op_id,
            expected_selection_revision=1,
            expected_answer_revision=1,
            expected_work_version=1,
            file_id=stored_file.id,
            rationale="Initial cloud compliance evidence snapshot",
        )
        receipt1 = service.create_evidence(
            test_setup["principal"],
            test_setup["tenant_context"],
            work1.id,
            ev_req,
            request_id="req-ev-1",
        )
        assert receipt1.applied_work_version == 2
        assert len(receipt1.current_work.links) == 1
        link1 = receipt1.current_work.links[0]
        assert link1.review == "PENDING"
        assert link1.validity == "AVAILABLE"
        assert link1.rationale == "Initial cloud compliance evidence snapshot"

        # Scanner was called
        assert len(scanner.scanned_items) == 1
        assert scanner.scanned_items[0][0] == file_content

        # Deliberately reuse the pinned revision for Work 2
        reuse_op_id = uuid4()
        reuse_req = CreateLinkRequest(
            operation_id=reuse_op_id,
            expected_selection_revision=1,
            expected_answer_revision=1,
            expected_work_version=1,
            evidence_id=link1.evidence_id,
            evidence_revision_number=link1.revision_number,
            evidence_revision_digest=link1.digest,
            rationale="Reusing cloud baseline evidence for regional boundary control",
        )
        receipt2 = service.create_link(
            test_setup["principal"],
            test_setup["tenant_context"],
            work2.id,
            reuse_req,
            request_id="req-reuse-1",
        )
        assert receipt2.applied_work_version == 2
        assert len(receipt2.current_work.links) == 1
        link2 = receipt2.current_work.links[0]
        assert link2.review == "PENDING"
        assert link2.evidence_id == link1.evidence_id
        assert link2.revision_number == link1.revision_number
        assert link2.digest == link1.digest

        # Review Work 1 as ACCEPTED
        rev1_op_id = uuid4()
        rev1_req = CreateReviewRequest(
            operation_id=rev1_op_id,
            expected_selection_revision=1,
            expected_answer_revision=1,
            expected_work_version=2,
            decision="ACCEPTED",
            rationale="Evidence fully satisfies cloud architecture baseline",
        )
        receipt_rev1 = service.create_review(
            test_setup["principal"],
            test_setup["tenant_context"],
            work1.id,
            link1.id,
            rev1_req,
            request_id="req-rev-1",
        )
        assert receipt_rev1.applied_work_version == 3
        assert receipt_rev1.current_work.links[0].review == "ACCEPTED"

        # Review Work 2 as REJECTED (Independent review on reused evidence!)
        rev2_op_id = uuid4()
        rev2_req = CreateReviewRequest(
            operation_id=rev2_op_id,
            expected_selection_revision=1,
            expected_answer_revision=1,
            expected_work_version=2,
            decision="REJECTED",
            rationale="Insufficient proof of EU data residency in this snapshot",
        )
        receipt_rev2 = service.create_review(
            test_setup["principal"],
            test_setup["tenant_context"],
            work2.id,
            link2.id,
            rev2_req,
            request_id="req-rev-2",
        )
        assert receipt_rev2.applied_work_version == 3
        assert receipt_rev2.current_work.links[0].review == "REJECTED"

        # Verify Work 1 review remains ACCEPTED and independent
        work1_fresh = service.get_control_work_list(
            test_setup["principal"], test_setup["tenant_context"]
        )
        assert work1_fresh.items[0].links[0].review == "ACCEPTED"
        assert work1_fresh.items[1].links[0].review == "REJECTED"


def test_scanner_failure_fails_closed(db_session: Session, test_setup: dict[str, Any]):
    """Verify that unconfigured scanner or scanner failure blocks evidence creation with 503."""
    # Scanner without host
    unconfigured_scanner = StrictEvidenceMalwareScanner(clamav_host=None)
    service = CustomerControlWorkService(db_session, scanner=unconfigured_scanner)

    init_res = service.initialize_work(
        test_setup["principal"],
        test_setup["tenant_context"],
        InitializeWorkRequest(
            operation_id=uuid4(),
            adoption_id=test_setup["adoption_id"],
            expected_selection_revision=1,
            expected_answer_revision=1,
        ),
        request_id="req-init",
    )
    work1 = init_res.items[0]

    stored_file = _seed_stored_file(db_session, test_setup["tenant_id"], test_setup["owner_id"])

    with patch("conformly.customer_demo.work_service.StorageService") as MockStorage:
        instance = MockStorage.return_value
        instance.download_file.return_value = (stored_file, b"content")

        with pytest.raises(StrictScanUnavailableError) as exc:
            service.create_evidence(
                test_setup["principal"],
                test_setup["tenant_context"],
                work1.id,
                CreateEvidenceRequest(
                    operation_id=uuid4(),
                    expected_selection_revision=1,
                    expected_answer_revision=1,
                    expected_work_version=1,
                    file_id=stored_file.id,
                    rationale="Test failure",
                ),
                request_id="req-fail",
            )
        assert exc.value.status_code == 503


def test_entitlement_denial(db_session: Session, test_setup: dict[str, Any]):
    """Verify that missing or expired evidence module entitlement denies access."""
    # Delete entitlement
    db_session.query(TenantEntitlement).filter(
        TenantEntitlement.tenant_id == test_setup["tenant_id"]
    ).delete()
    db_session.commit()

    service = CustomerControlWorkService(db_session)
    with pytest.raises(CustomerDemoAdmissionError) as exc:
        service.get_control_work_list(test_setup["principal"], test_setup["tenant_context"])
    assert exc.value.status_code == 403


def test_strict_scanner_reply_validation_matrix():
    """Verify scanner handles exact NUL-terminated replies, rejecting fragments, garbage, and leaks."""
    scanner = StrictEvidenceMalwareScanner(
        clamav_host="127.0.0.1", clamav_port=3310, timeout_seconds=2.0
    )

    # Helper to mock socket connection returning specific byte sequence
    class MockSocket:
        def __init__(
            self, responses: list[bytes], raise_timeout: bool = False, hanging_after: bool = False
        ):
            self.responses = list(responses)
            self.raise_timeout = raise_timeout
            self.hanging_after = hanging_after

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def settimeout(self, t):
            pass

        def sendall(self, data):
            pass

        def recv(self, size):
            if self.raise_timeout:
                raise TimeoutError("Scan timed out")
            if self.responses:
                return self.responses.pop(0)
            if self.hanging_after:
                raise TimeoutError("Hung waiting for EOF")
            return b""

    # 1. Exact valid reply: b"stream: OK\0"
    with patch("socket.create_connection", return_value=MockSocket([b"stream: OK\0"])):
        scanner._scan_with_clamav(b"clean data")

    # 2. Fragmented valid frame: b"stream: " then b"OK\0" -> succeeds without waiting for EOF
    with patch("socket.create_connection", return_value=MockSocket([b"stream: ", b"OK\0"])):
        scanner._scan_with_clamav(b"clean data")

    # 3. Valid frame without EOF (socket hangs if recv called again): must succeed immediately on \0
    with patch(
        "socket.create_connection", return_value=MockSocket([b"stream: OK\0"], hanging_after=True)
    ):
        scanner._scan_with_clamav(b"clean data")

    # 4. Incomplete frame ending in EOF without NUL: b"stream: OK" -> 503
    with patch("socket.create_connection", return_value=MockSocket([b"stream: OK"])):
        with pytest.raises(StrictScanUnavailableError) as exc:
            scanner._scan_with_clamav(b"data")
        assert exc.value.status_code == 503
        assert "non-OK" in exc.value.detail or "unavailable" in exc.value.detail

    # 5. Truncated reply ending in EOF: b"stream: O" -> 503
    with patch("socket.create_connection", return_value=MockSocket([b"stream: O"])):
        with pytest.raises(StrictScanUnavailableError) as exc:
            scanner._scan_with_clamav(b"data")
        assert exc.value.status_code == 503

    # 6. Trailing same-chunk garbage: b"stream: OK\0UNTRUSTED" -> 503
    with patch("socket.create_connection", return_value=MockSocket([b"stream: OK\0UNTRUSTED"])):
        with pytest.raises(StrictScanUnavailableError) as exc:
            scanner._scan_with_clamav(b"data")
        assert exc.value.status_code == 503

    # 7. Trailing same-chunk padding: b"stream: OK\0 " or b"stream: OK\0\r\n" -> 503
    for trailing in (b"stream: OK\0 ", b"stream: OK\0\r\n", b"stream: OK\0\0"):
        with patch("socket.create_connection", return_value=MockSocket([trailing])):
            with pytest.raises(StrictScanUnavailableError) as exc:
                scanner._scan_with_clamav(b"data")
            assert exc.value.status_code == 503

    # 8. Trailing second frame in same chunk: b"stream: OK\0stream: OK\0" -> 503
    with patch("socket.create_connection", return_value=MockSocket([b"stream: OK\0stream: OK\0"])):
        with pytest.raises(StrictScanUnavailableError) as exc:
            scanner._scan_with_clamav(b"data")
        assert exc.value.status_code == 503

    # 9. Whitespace-padded reply: b"stream: OK \0" or b"stream: OK\r\n\0" -> 503
    with patch("socket.create_connection", return_value=MockSocket([b"stream: OK \0"])):
        with pytest.raises(StrictScanUnavailableError) as exc:
            scanner._scan_with_clamav(b"data")
        assert exc.value.status_code == 503

    # 10. Garbage reply: b"ERROR: daemon failed\0" -> 503
    with patch("socket.create_connection", return_value=MockSocket([b"ERROR: daemon failed\0"])):
        with pytest.raises(StrictScanUnavailableError) as exc:
            scanner._scan_with_clamav(b"data")
        assert exc.value.status_code == 503

    # 11. Scanner timeout -> 503
    with patch("socket.create_connection", return_value=MockSocket([], raise_timeout=True)):
        with pytest.raises(StrictScanUnavailableError) as exc:
            scanner._scan_with_clamav(b"data")
        assert exc.value.status_code == 503

    # 12. Absent configuration: clamav_host is None -> 503
    unconfigured_scanner = StrictEvidenceMalwareScanner(clamav_host=None)
    with pytest.raises(StrictScanUnavailableError) as exc_unconf:
        unconfigured_scanner.scan(b"data", "evidence.pdf")
    assert exc_unconf.value.status_code == 503
    assert "not configured" in exc_unconf.value.detail

    # 13. Oversize response (> 4096 bytes) -> 503
    with patch("socket.create_connection", return_value=MockSocket([b"A" * 5000])):
        with pytest.raises(StrictScanUnavailableError) as exc_over:
            scanner._scan_with_clamav(b"data")
        assert exc_over.value.status_code == 503

    # 14. Empty response -> 503
    with patch("socket.create_connection", return_value=MockSocket([b""])):
        with pytest.raises(StrictScanUnavailableError) as exc_empty:
            scanner._scan_with_clamav(b"data")
        assert exc_empty.value.status_code == 503

    # 15. FOUND reply: b"stream: Win.Trojan.555 FOUND\0" -> MalwareDetectedError without signature leak
    with patch(
        "socket.create_connection", return_value=MockSocket([b"stream: Win.Trojan.555 FOUND\0"])
    ):
        with pytest.raises(MalwareDetectedError) as exc_malware:
            scanner._scan_with_clamav(b"infected data")
        assert "Malware detected in uploaded evidence" in str(exc_malware.value)
        assert "Win.Trojan.555" not in str(exc_malware.value)
        assert "FOUND" not in str(exc_malware.value)


def test_direct_service_admission_database_validation(
    db_session: Session, test_setup: dict[str, Any]
):
    """Verify that public work_service admission strictly validates User and Membership rows in DB."""
    service = CustomerControlWorkService(db_session)
    principal = test_setup["principal"]
    tenant_context = test_setup["tenant_context"]
    tenant_id = test_setup["tenant_id"]
    owner_id = test_setup["owner_id"]

    # 1. Baseline: valid admitted caller
    owners = service.get_owners(principal, tenant_context)
    assert owners.total >= 1

    # Fetch DB rows
    user = db_session.query(User).filter(User.id == owner_id).one()
    membership = (
        db_session.query(Membership)
        .filter(Membership.tenant_id == tenant_id, Membership.user_id == owner_id)
        .one()
    )

    # 2. Suspended membership -> 403
    membership.status = MembershipStatus.SUSPENDED
    db_session.commit()
    with pytest.raises(CustomerDemoAdmissionError) as exc:
        service.get_control_work_list(principal, tenant_context)
    assert exc.value.status_code == 403
    assert "not active" in exc.value.detail

    # Restore
    membership.status = MembershipStatus.ACTIVE
    db_session.commit()

    # 3. Expired membership -> 403
    membership.expires_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.commit()
    with pytest.raises(CustomerDemoAdmissionError) as exc:
        service.get_control_work_list(principal, tenant_context)
    assert exc.value.status_code == 403
    assert "expired" in exc.value.detail

    # Restore
    membership.expires_at = None
    db_session.commit()

    # 4. Role downgrade in DB (e.g. CONTRIBUTOR) while caller claims OWNER context -> 403
    membership.role = Role.CONTRIBUTOR
    db_session.commit()
    with pytest.raises(CustomerDemoAdmissionError) as exc:
        service.get_control_work_list(principal, tenant_context)
    assert exc.value.status_code == 403
    assert "does not match" in exc.value.detail or "not admitted" in exc.value.detail

    # Restore
    membership.role = Role.OWNER
    db_session.commit()

    # 5. Workforce flag on membership -> 403
    membership.is_workforce = True
    db_session.commit()
    with pytest.raises(CustomerDemoAdmissionError) as exc:
        service.get_control_work_list(principal, tenant_context)
    assert exc.value.status_code == 403
    assert "Workforce" in exc.value.detail

    # Restore
    membership.is_workforce = False
    db_session.commit()

    # 6. External advisor flag on membership -> 403
    membership.is_external_advisor = True
    db_session.commit()
    with pytest.raises(CustomerDemoAdmissionError) as exc:
        service.get_control_work_list(principal, tenant_context)
    assert exc.value.status_code == 403
    assert "External advisor" in exc.value.detail

    # Restore
    membership.is_external_advisor = False
    db_session.commit()

    # 7. Sub-entity scope on membership -> 403
    membership.legal_entity_id = uuid4()
    db_session.commit()
    with pytest.raises(CustomerDemoAdmissionError) as exc:
        service.get_control_work_list(principal, tenant_context)
    assert exc.value.status_code == 403
    assert "Sub-entity" in exc.value.detail

    # Restore
    membership.legal_entity_id = None
    db_session.commit()

    # 8. User disabled / suspended -> 403
    user.status = UserStatus.DISABLED
    db_session.commit()
    with pytest.raises(CustomerDemoAdmissionError) as exc:
        service.get_control_work_list(principal, tenant_context)
    assert exc.value.status_code == 403
    assert "not active" in exc.value.detail

    # Restore
    user.status = UserStatus.ACTIVE
    db_session.commit()

    # 9. Tenant lifecycle: non-active tenant prohibits mutations
    tenant = db_session.query(Tenant).filter(Tenant.id == tenant_id).one()
    tenant.status = TenantStatus.SUSPENDED
    db_session.commit()
    with pytest.raises(CustomerDemoAdmissionError) as exc:
        service.initialize_work(
            principal,
            tenant_context,
            InitializeWorkRequest(
                operation_id=uuid4(),
                adoption_id=test_setup["adoption_id"],
                expected_selection_revision=1,
                expected_answer_revision=1,
            ),
            request_id="req-lifecycle-fail",
        )
    assert exc.value.status_code == 409

    # Restore tenant
    tenant.status = TenantStatus.ACTIVE
    db_session.commit()


def test_evidence_lifecycle_and_scan_proof_enforcement(
    db_session: Session, test_setup: dict[str, Any]
):
    """Verify dual lifecycle and historic scan proof enforcement on reuse, review, download, and listing."""
    service = CustomerControlWorkService(db_session, scanner=MockSuccessfulScanner())
    principal = test_setup["principal"]
    tenant_context = test_setup["tenant_context"]
    tenant_id = test_setup["tenant_id"]
    owner_id = test_setup["owner_id"]
    now = datetime.now(UTC)

    # 1. Initialize work
    init_res = service.initialize_work(
        principal,
        tenant_context,
        InitializeWorkRequest(
            operation_id=uuid4(),
            adoption_id=test_setup["adoption_id"],
            expected_selection_revision=1,
            expected_answer_revision=1,
        ),
        request_id="req-init-lifecycle",
    )
    work1 = init_res.items[0]

    # 2. Create and pin evidence
    stored_file = _seed_stored_file(db_session, tenant_id, owner_id, b"clean proof bytes")
    with patch("conformly.customer_demo.work_service.StorageService") as MockStorage:
        instance = MockStorage.return_value
        instance.download_file.return_value = (stored_file, b"clean proof bytes")

        receipt = service.create_evidence(
            principal,
            tenant_context,
            work1.id,
            CreateEvidenceRequest(
                operation_id=uuid4(),
                expected_selection_revision=1,
                expected_answer_revision=1,
                expected_work_version=1,
                file_id=stored_file.id,
                valid_until=now + timedelta(days=30),
                rationale="Audit lifecycle evidence",
            ),
            request_id="req-ev-create",
        )
    work1_ver = receipt.applied_work_version
    link_id = receipt.current_work.links[0].id
    evidence_id = receipt.current_work.links[0].evidence_id

    # Verify listing reports SCANNED_AT_LINK and AVAILABLE
    list_res = service.get_control_work_list(principal, tenant_context)
    link_dto = list_res.items[0].links[0]
    assert link_dto.validity == "AVAILABLE"
    assert link_dto.scan_status == "SCANNED_AT_LINK"
    assert link_dto.scan_verified_at is not None

    # 3. Pinned revision expired (valid_until in past)
    rev = (
        db_session.query(EvidenceRevision)
        .filter(
            EvidenceRevision.tenant_id == tenant_id,
            EvidenceRevision.evidence_id == evidence_id,
            EvidenceRevision.revision_number == receipt.current_work.links[0].revision_number,
        )
        .one()
    )
    orig_rev_until = rev.valid_until
    rev.valid_until = now - timedelta(days=1)
    link = (
        db_session.query(CustomerControlEvidenceLink)
        .filter(CustomerControlEvidenceLink.id == link_id)
        .one()
    )
    orig_link_digest = link.evidence_revision_digest
    from conformly.customer_demo.work_service import compute_evidence_revision_digest

    link.evidence_revision_digest = compute_evidence_revision_digest(
        evidence_id=rev.evidence_id,
        revision_number=rev.revision_number,
        title=rev.title,
        description=rev.description,
        classification=str(
            rev.classification.value if hasattr(rev.classification, "value") else rev.classification
        ),
        status_val=str(rev.status.value if hasattr(rev.status, "value") else rev.status),
        valid_from=rev.valid_from,
        valid_until=rev.valid_until,
        file_ids=rev.file_ids or [],
        control_ids=rev.control_ids or [],
    )
    db_session.commit()

    # Listing reflects EXPIRED
    list_res = service.get_control_work_list(principal, tenant_context)
    assert list_res.items[0].links[0].validity == "EXPIRED"

    # ACCEPTED review is rejected -> 409
    with pytest.raises(HTTPException) as exc:
        service.create_review(
            principal,
            tenant_context,
            work1.id,
            link_id,
            CreateReviewRequest(
                operation_id=uuid4(),
                expected_selection_revision=1,
                expected_answer_revision=1,
                expected_work_version=work1_ver,
                decision="ACCEPTED",
                rationale="Review accepted should fail on expired rev",
            ),
            request_id="req-rev-fail",
        )
    assert exc.value.status_code == 409
    assert "expired" in exc.value.detail

    # download_pinned_file is rejected -> 409
    with pytest.raises(HTTPException) as exc:
        service.download_pinned_file(
            principal,
            tenant_context,
            work1.id,
            link_id,
            stored_file.id,
            request_id="req-dl-fail",
        )
    assert exc.value.status_code == 409
    assert "expired" in exc.value.detail

    # However, REJECTED review remains available!
    rej_receipt = service.create_review(
        principal,
        tenant_context,
        work1.id,
        link_id,
        CreateReviewRequest(
            operation_id=uuid4(),
            expected_selection_revision=1,
            expected_answer_revision=1,
            expected_work_version=work1_ver,
            decision="REJECTED",
            rationale="Review rejected is allowed on expired/unavailable evidence",
        ),
        request_id="req-rej-ok",
    )
    assert rej_receipt.current_work.links[0].review == "REJECTED"
    work1_ver = rej_receipt.applied_work_version

    # Restore revision valid_until and link digest
    rev.valid_until = orig_rev_until
    link.evidence_revision_digest = orig_link_digest
    db_session.commit()

    # 4. Current EvidenceItem (head) ARCHIVED
    evidence_head = (
        db_session.query(EvidenceItem)
        .filter(EvidenceItem.tenant_id == tenant_id, EvidenceItem.id == evidence_id)
        .one()
    )
    orig_head_status = evidence_head.status
    evidence_head.status = EvidenceStatus.ARCHIVED
    db_session.commit()

    # Listing reflects UNAVAILABLE
    list_res = service.get_control_work_list(principal, tenant_context)
    assert list_res.items[0].links[0].validity == "UNAVAILABLE"

    # Reuse via create_link is rejected -> 409
    with pytest.raises(HTTPException) as exc:
        service.create_link(
            principal,
            tenant_context,
            init_res.items[1].id,
            CreateLinkRequest(
                operation_id=uuid4(),
                expected_selection_revision=1,
                expected_answer_revision=1,
                expected_work_version=1,
                evidence_id=evidence_id,
                evidence_revision_number=rev.revision_number,
                evidence_revision_digest=link_dto.digest,
                rationale="Attempt reuse archived head",
            ),
            request_id="req-reuse-archived",
        )
    assert exc.value.status_code == 409
    assert "not valid" in exc.value.detail or "archived" in exc.value.detail

    # Restore head status
    evidence_head.status = orig_head_status
    db_session.commit()

    # 5. Stored file hash changed (tampered / mismatched proof)
    orig_file_hash = stored_file.plaintext_sha256
    stored_file.plaintext_sha256 = "0" * 64
    db_session.commit()

    # Listing reflects UNVERIFIED
    list_res = service.get_control_work_list(principal, tenant_context)
    assert list_res.items[0].links[0].validity == "UNVERIFIED"
    assert list_res.items[0].links[0].scan_status == "UNVERIFIED"

    # Download is rejected -> 409
    with pytest.raises(HTTPException) as exc:
        service.download_pinned_file(
            principal,
            tenant_context,
            work1.id,
            link_id,
            stored_file.id,
            request_id="req-dl-hash-mismatch",
        )
    assert exc.value.status_code == 409
    assert "does not match current stored file" in exc.value.detail

    # Restore file hash
    stored_file.plaintext_sha256 = orig_file_hash
    db_session.commit()


def test_pack_2_work_initialization_and_deliberate_evidence_reuse(db_session, test_setup):
    """Verify pinned work initialization for Pack 2 and deliberate evidence reuse on shared control."""
    principal = test_setup["principal"]
    tenant_context = test_setup["tenant_context"]
    tenant_id = test_setup["tenant_id"]
    owner_id = test_setup["owner_id"]
    adopt_p1_id = test_setup["adoption_id"]

    scanner = MockSuccessfulScanner()
    service = CustomerControlWorkService(db_session, scanner=scanner)

    # Initialize work for Pack 1
    init_res1 = service.initialize_work(
        principal,
        tenant_context,
        InitializeWorkRequest(
            adoption_id=adopt_p1_id,
            expected_selection_revision=1,
            expected_answer_revision=1,
            operation_id=uuid4(),
        ),
        request_id="req-init-p1",
    )
    assert init_res1.total >= 2

    # Upload evidence item on Pack 1 control 1 (shared control)
    work_p1 = (
        db_session.query(CustomerControlWork)
        .filter(
            CustomerControlWork.tenant_id == tenant_id,
            CustomerControlWork.adoption_id == adopt_p1_id,
            CustomerControlWork.control_version_id == CTRL_1_VER_ID,
        )
        .one()
    )

    file_content = b"Production cloud baseline architecture document content"
    stored_file = _seed_stored_file(db_session, tenant_id, owner_id, file_content)

    with patch("conformly.customer_demo.work_service.StorageService") as MockStorage:
        instance = MockStorage.return_value
        instance.download_file.return_value = (stored_file, file_content)

        ev_receipt = service.create_evidence(
            principal,
            tenant_context,
            work_p1.id,
            CreateEvidenceRequest(
                expected_selection_revision=1,
                expected_answer_revision=1,
                expected_work_version=work_p1.version,
                file_id=stored_file.id,
                rationale="Production cloud baseline architecture document",
                operation_id=uuid4(),
            ),
            request_id="req-ev-p1",
        )
        ev_id = ev_receipt.current_work.links[0].evidence_id
        ev_rev_num = ev_receipt.current_work.links[0].revision_number
        ev_rev_digest = ev_receipt.current_work.links[0].digest

        # 2. Evaluate and adopt Pack 2 v1 via real service calls
        eval_p2 = evaluate_answers(
            db_session,
            principal,
            tenant_context,
            expected_revision=1,
            pack_version_id=PACK_2_VERSION_V1_ID,
            request_id="req-eval-p2",
        )
        assert eval_p2.pack_version_id == PACK_2_VERSION_V1_ID

        adopt_res = adopt_evaluation(
            db_session,
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

        # Initialize work for Pack 2
        init_res2 = service.initialize_work(
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
        assert init_res2.total == 3

        # Pack 2 has shared control CTRL_1_VER_ID
        work_p2 = (
            db_session.query(CustomerControlWork)
            .filter(
                CustomerControlWork.tenant_id == tenant_id,
                CustomerControlWork.adoption_id == adopt_p2_id,
                CustomerControlWork.control_version_id == CTRL_1_VER_ID,
            )
            .one()
        )

        # Old work_p1 is now stale and not current
        work_list_old = service.get_control_work_list(principal, tenant_context, adoption_id=adopt_p1_id)
        assert work_list_old.is_current is False
        assert work_list_old.is_stale is True

        # 3. Deliberately reuse the exact evidence revision from Pack 1 on Pack 2 shared control
        reuse_receipt = service.create_link(
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
        assert len(reuse_receipt.current_work.links) == 1
        new_link = reuse_receipt.current_work.links[0]
        assert new_link.evidence_id == ev_id
        assert new_link.review == "PENDING"  # NO automatic pass carryover!

        # 4. Perform independent review for the target resilience work item
        review_receipt = service.create_review(
            principal,
            tenant_context,
            work_p2.id,
            new_link.id,
            CreateReviewRequest(
                expected_selection_revision=2,
                expected_answer_revision=1,
                expected_work_version=reuse_receipt.current_work.version,
                decision="ACCEPTED",
                rationale="Suitability verified for resilience cloud baseline.",
                operation_id=uuid4(),
            ),
            request_id="req-target-review",
        )
        assert review_receipt.current_work.links[0].review == "ACCEPTED"
