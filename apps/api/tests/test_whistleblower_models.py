"""Tests for whistleblower domain models."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from conformly.db.base import Base
from conformly.identity.models import Tenant, User  # noqa: F401
from conformly.storage.models import StoredFile  # noqa: F401
from conformly.whistleblower.models import (
    WHISTLEBLOWER_CASE_TRANSITIONS,
    WhistleblowerAttachment,
    WhistleblowerCase,
    WhistleblowerCaseAssignment,
    WhistleblowerCaseStatus,
    WhistleblowerMessage,
    WhistleblowerMessageSender,
    WhistleblowerPortal,
)


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


class TestWhistleblowerPortalModel:
    def test_create_portal(self) -> None:
        session = _session()
        tid = uuid4()
        portal = WhistleblowerPortal(
            tenant_id=tid,
            slug="acme-corp",
            title="Acme Whistleblower Portal",
            welcome_text="Report concerns anonymously.",
            is_active=True,
            version=1,
        )
        session.add(portal)
        session.flush()

        assert portal.id is not None
        assert portal.slug == "acme-corp"
        assert portal.is_active is True
        assert portal.version == 1

    def test_portal_cases_relationship(self) -> None:
        session = _session()
        tid = uuid4()
        portal = WhistleblowerPortal(
            tenant_id=tid,
            slug="acme-test",
            title="Acme Test Portal",
            welcome_text="Welcome",
        )
        session.add(portal)
        session.flush()

        case = WhistleblowerCase(
            tenant_id=tid,
            portal_id=portal.id,
            public_case_id="WB-2026-TEST01",
            return_secret_salt="salt123",
            return_secret_hash="hash123",
            status=WhistleblowerCaseStatus.SUBMITTED,
            category="fraud",
            title="Suspicious expense report",
        )
        session.add(case)
        session.flush()

        assert len(portal.cases) == 1
        assert portal.cases[0].public_case_id == "WB-2026-TEST01"
        assert portal.cases[0].portal.slug == "acme-test"


class TestWhistleblowerCaseModel:
    def test_create_case_with_encrypted_summary(self) -> None:
        session = _session()
        tid = uuid4()
        portal = WhistleblowerPortal(
            tenant_id=tid,
            slug="cyberdyne",
            title="Cyberdyne Ethics Line",
            welcome_text="Strictly anonymous",
        )
        session.add(portal)
        session.flush()

        case = WhistleblowerCase(
            tenant_id=tid,
            portal_id=portal.id,
            public_case_id="WB-2026-ABC123",
            return_secret_salt="1234567890abcdef",
            return_secret_hash="abcdef1234567890",
            status=WhistleblowerCaseStatus.SUBMITTED,
            category="safety",
            title="Safety violation in lab 4",
            encrypted_summary={"ciphertext": "dGVzdA==", "nonce": "MTIz"},
            version=1,
        )
        session.add(case)
        session.flush()

        assert case.id is not None
        assert case.status == WhistleblowerCaseStatus.SUBMITTED
        assert case.encrypted_summary is not None
        assert case.encrypted_summary["ciphertext"] == "dGVzdA=="

    def test_messages_relationship(self) -> None:
        session = _session()
        tid = uuid4()
        portal = WhistleblowerPortal(
            tenant_id=tid,
            slug="wayne-corp",
            title="Wayne Corp Intake",
            welcome_text="Report here",
        )
        session.add(portal)
        session.flush()

        case = WhistleblowerCase(
            tenant_id=tid,
            portal_id=portal.id,
            public_case_id="WB-2026-WAYNE1",
            return_secret_salt="salt",
            return_secret_hash="hash",
            status=WhistleblowerCaseStatus.SUBMITTED,
            category="harassment",
            title="Workplace concern",
        )
        session.add(case)
        session.flush()

        # Reporter message
        rep_msg = WhistleblowerMessage(
            tenant_id=tid,
            case_id=case.id,
            sender_type=WhistleblowerMessageSender.REPORTER,
            encrypted_body={"ciphertext": "rep_body"},
            sent_by_user_id=None,
        )
        # Handler message
        handler_uid = uuid4()
        hnd_msg = WhistleblowerMessage(
            tenant_id=tid,
            case_id=case.id,
            sender_type=WhistleblowerMessageSender.HANDLER,
            encrypted_body={"ciphertext": "hnd_body"},
            sent_by_user_id=handler_uid,
        )
        session.add_all([rep_msg, hnd_msg])
        session.flush()

        assert len(case.messages) == 2
        assert case.messages[0].sender_type == WhistleblowerMessageSender.REPORTER
        assert case.messages[0].sent_by_user_id is None
        assert case.messages[1].sender_type == WhistleblowerMessageSender.HANDLER
        assert case.messages[1].sent_by_user_id == handler_uid


class TestWhistleblowerCaseAssignmentModel:
    def test_case_assignment(self) -> None:
        session = _session()
        tid = uuid4()
        portal = WhistleblowerPortal(
            tenant_id=tid,
            slug="stark-ind",
            title="Stark Ethics",
            welcome_text="Speak up",
        )
        session.add(portal)
        session.flush()

        case = WhistleblowerCase(
            tenant_id=tid,
            portal_id=portal.id,
            public_case_id="WB-2026-STARK1",
            return_secret_salt="salt",
            return_secret_hash="hash",
            category="bribery",
            title="Procurement anomaly",
        )
        session.add(case)
        session.flush()

        handler_id = uuid4()
        assigned_by = uuid4()
        assignment = WhistleblowerCaseAssignment(
            tenant_id=tid,
            case_id=case.id,
            handler_user_id=handler_id,
            assigned_by_user_id=assigned_by,
            assigned_at=datetime.now(UTC),
        )
        session.add(assignment)
        session.flush()

        assert assignment.id is not None
        assert len(case.assignments) == 1
        assert case.assignments[0].handler_user_id == handler_id


class TestWhistleblowerAttachmentModel:
    def test_case_attachment(self) -> None:
        session = _session()
        tid = uuid4()
        portal = WhistleblowerPortal(
            tenant_id=tid,
            slug="oscorp",
            title="Oscorp Line",
            welcome_text="Confidential",
        )
        session.add(portal)
        session.flush()

        case = WhistleblowerCase(
            tenant_id=tid,
            portal_id=portal.id,
            public_case_id="WB-2026-OSCORP",
            return_secret_salt="salt",
            return_secret_hash="hash",
            category="safety",
            title="Toxic waste disposal",
        )
        session.add(case)
        session.flush()

        file_id = uuid4()
        attachment = WhistleblowerAttachment(
            tenant_id=tid,
            case_id=case.id,
            message_id=None,
            file_id=file_id,
            uploaded_by=WhistleblowerMessageSender.REPORTER,
            original_filename="manifest.pdf",
        )
        session.add(attachment)
        session.flush()

        assert len(case.attachments) == 1
        assert case.attachments[0].original_filename == "manifest.pdf"
        assert case.attachments[0].file_id == file_id


class TestWhistleblowerStateTransitions:
    def test_state_transition_rules(self) -> None:
        # Submitted transitions
        submitted_next = WHISTLEBLOWER_CASE_TRANSITIONS[WhistleblowerCaseStatus.SUBMITTED]
        assert WhistleblowerCaseStatus.ACKNOWLEDGED in submitted_next
        assert WhistleblowerCaseStatus.UNDER_INVESTIGATION in submitted_next
        assert WhistleblowerCaseStatus.DISMISSED in submitted_next
        assert WhistleblowerCaseStatus.RESOLVED not in submitted_next

        # Acknowledged transitions
        ack_next = WHISTLEBLOWER_CASE_TRANSITIONS[WhistleblowerCaseStatus.ACKNOWLEDGED]
        assert WhistleblowerCaseStatus.UNDER_INVESTIGATION in ack_next
        assert WhistleblowerCaseStatus.RESOLVED in ack_next
        assert WhistleblowerCaseStatus.DISMISSED in ack_next

        # Terminal states have no valid transitions
        assert len(WHISTLEBLOWER_CASE_TRANSITIONS[WhistleblowerCaseStatus.RESOLVED]) == 0
        assert len(WHISTLEBLOWER_CASE_TRANSITIONS[WhistleblowerCaseStatus.DISMISSED]) == 0
