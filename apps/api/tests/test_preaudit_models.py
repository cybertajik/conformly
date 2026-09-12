"""Tests for pre-audit domain models."""

from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from conformly.db.base import Base
from conformly.preaudit.models import (
    PRE_AUDIT_TRANSITIONS,
    CertificateStatus,
    CheckResult,
    PreAudit,
    PreAuditCertificate,
    PreAuditCheck,
    PreAuditFinding,
    PreAuditManifest,
    PreAuditReport,
    PreAuditScope,
    PreAuditStatus,
)


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


class TestPreAuditModel:
    def test_create_pre_audit(self) -> None:
        session = _session()
        tid = uuid4()
        pa = PreAudit(
            tenant_id=tid,
            title="ISO 27001 Readiness",
            description="Annual readiness assessment",
            status=PreAuditStatus.PLANNING,
            framework_adoption_id=uuid4(),
            lead_user_id=uuid4(),
            rule_version="v1.0.0",
            version=1,
        )
        session.add(pa)
        session.flush()
        assert pa.id is not None
        assert pa.status == PreAuditStatus.PLANNING
        assert pa.version == 1

    def test_pre_audit_scope_relationship(self) -> None:
        session = _session()
        tid = uuid4()
        pa = PreAudit(
            tenant_id=tid,
            title="Test",
            framework_adoption_id=uuid4(),
            lead_user_id=uuid4(),
            rule_version="v1.0.0",
            version=1,
        )
        session.add(pa)
        session.flush()

        scope = PreAuditScope(
            tenant_id=tid,
            pre_audit_id=pa.id,
            framework_version_id=uuid4(),
            control_count=10,
            checked_count=0,
        )
        session.add(scope)
        session.flush()
        assert scope in pa.scopes

    def test_pre_audit_check(self) -> None:
        session = _session()
        tid = uuid4()
        pa = PreAudit(
            tenant_id=tid,
            title="Test",
            framework_adoption_id=uuid4(),
            lead_user_id=uuid4(),
            rule_version="v1.0.0",
            version=1,
        )
        session.add(pa)
        session.flush()

        scope = PreAuditScope(
            tenant_id=tid,
            pre_audit_id=pa.id,
            framework_version_id=uuid4(),
        )
        session.add(scope)
        session.flush()

        check = PreAuditCheck(
            tenant_id=tid,
            scope_id=scope.id,
            control_type="canonical",
            control_id=uuid4(),
            result=CheckResult.PASS,
            rule_version="v1.0.0",
            evidence_count=3,
            policy_count=1,
            open_findings_count=0,
            score=1.0,
        )
        session.add(check)
        session.flush()
        assert check.result == CheckResult.PASS
        assert check in scope.checks


class TestPreAuditFinding:
    def test_create_finding(self) -> None:
        session = _session()
        tid = uuid4()
        pa = PreAudit(
            tenant_id=tid,
            title="Test",
            framework_adoption_id=uuid4(),
            lead_user_id=uuid4(),
            rule_version="v1.0.0",
            version=1,
        )
        session.add(pa)
        session.flush()

        finding = PreAuditFinding(
            tenant_id=tid,
            pre_audit_id=pa.id,
            title="Missing evidence for A.5.1",
            description="No evidence linked",
            severity="high",
            version=1,
        )
        session.add(finding)
        session.flush()
        assert finding in pa.findings
        assert finding.version == 1


class TestPreAuditCertificate:
    def test_create_certificate(self) -> None:
        session = _session()
        tid = uuid4()
        pa = PreAudit(
            tenant_id=tid,
            title="Test",
            framework_adoption_id=uuid4(),
            lead_user_id=uuid4(),
            rule_version="v1.0.0",
            version=1,
        )
        session.add(pa)
        session.flush()

        from datetime import UTC, datetime, timedelta

        now = datetime.now(UTC)
        cert = PreAuditCertificate(
            tenant_id=tid,
            pre_audit_id=pa.id,
            certificate_number="CONF-RA-20260912-ABCD1234",
            status=CertificateStatus.ACTIVE,
            issued_at=now,
            expires_at=now + timedelta(days=365),
        )
        session.add(cert)
        session.flush()
        assert cert.status == CertificateStatus.ACTIVE
        assert cert in pa.certificates


class TestPreAuditReport:
    def test_create_report(self) -> None:
        session = _session()
        tid = uuid4()
        pa = PreAudit(
            tenant_id=tid,
            title="Test",
            framework_adoption_id=uuid4(),
            lead_user_id=uuid4(),
            rule_version="v1.0.0",
            version=1,
        )
        session.add(pa)
        session.flush()

        from datetime import UTC, datetime

        report = PreAuditReport(
            tenant_id=tid,
            pre_audit_id=pa.id,
            file_id=uuid4(),
            report_type="readiness_summary",
            rule_version="v1.0.0",
            generated_at=datetime.now(UTC),
        )
        session.add(report)
        session.flush()
        assert report in pa.reports


class TestPreAuditManifest:
    def test_create_manifest(self) -> None:
        session = _session()
        tid = uuid4()
        pa = PreAudit(
            tenant_id=tid,
            title="Test",
            framework_adoption_id=uuid4(),
            lead_user_id=uuid4(),
            rule_version="v1.0.0",
            version=1,
        )
        session.add(pa)
        session.flush()

        from datetime import UTC, datetime

        manifest = PreAuditManifest(
            tenant_id=tid,
            pre_audit_id=pa.id,
            file_id=uuid4(),
            manifest_hash_sha256="a" * 64,
            record_count=42,
            rule_version="v1.0.0",
            generated_at=datetime.now(UTC),
        )
        session.add(manifest)
        session.flush()
        assert manifest in pa.manifests


class TestStateTransitions:
    def test_planning_can_go_to_in_progress(self) -> None:
        allowed = PRE_AUDIT_TRANSITIONS[PreAuditStatus.PLANNING]
        assert PreAuditStatus.IN_PROGRESS in allowed

    def test_planning_cannot_go_to_completed(self) -> None:
        allowed = PRE_AUDIT_TRANSITIONS[PreAuditStatus.PLANNING]
        assert PreAuditStatus.COMPLETED not in allowed

    def test_in_review_can_complete_or_return(self) -> None:
        allowed = PRE_AUDIT_TRANSITIONS[PreAuditStatus.IN_REVIEW]
        assert PreAuditStatus.COMPLETED in allowed
        assert PreAuditStatus.IN_PROGRESS in allowed

    def test_completed_is_terminal(self) -> None:
        allowed = PRE_AUDIT_TRANSITIONS[PreAuditStatus.COMPLETED]
        assert len(allowed) == 0

    def test_cancelled_is_terminal(self) -> None:
        allowed = PRE_AUDIT_TRANSITIONS[PreAuditStatus.CANCELLED]
        assert len(allowed) == 0

    def test_every_non_terminal_can_cancel(self) -> None:
        for s in (
            PreAuditStatus.PLANNING,
            PreAuditStatus.IN_PROGRESS,
            PreAuditStatus.IN_REVIEW,
        ):
            assert PreAuditStatus.CANCELLED in PRE_AUDIT_TRANSITIONS[s]
