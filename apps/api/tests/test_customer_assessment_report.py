"""Offline contract and actual-service admission tests for private report generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select

from conformly.authz.policy import AuthorizationDeniedError
from conformly.authz.roles import Role
from conformly.config import get_settings
from conformly.customer_demo.assessment_report import (
    DISCLAIMER,
    FINDING_FIELDS,
    STATE_FIELDS,
    CustomerAssessmentReportService,
    ReportSnapshotError,
    _bundle,
    _project,
)
from conformly.customer_demo.assessment_schemas import (
    AssessmentCreateRequest,
    AssessmentCriterionResultDto,
    AssessmentWorkListResponse,
    FindingCreateSpecificationDto,
)
from conformly.customer_demo.assessment_service import CustomerAssessmentService
from conformly.entitlements.models import TenantEntitlement
from tests import test_customer_assessment_service as _assessment_fixtures

# Register existing offline fixtures without collecting that module's test functions.
db_session = _assessment_fixtures.db_session
enable_customer_demo_feature = _assessment_fixtures.enable_customer_demo_feature
test_setup = _assessment_fixtures.test_setup

NOW = datetime(2026, 10, 29, 16, 0, tzinfo=UTC)
TENANT = UUID(int=1)
ADOPTION = UUID(int=2)


def snapshot(state="UNASSESSED"):
    counts = dict.fromkeys([*STATE_FIELDS.values(), *FINDING_FIELDS.values()], 0)
    counts["total_controls"] = 1
    counts[STATE_FIELDS[state]] = 1
    assessed = state not in {"UNASSESSED", "NOT_APPLICABLE", "NEEDS_INFORMATION", "STALE_WORK"}
    result = state if state in {"FAIL", "PARTIAL", "INSUFFICIENT_EVIDENCE"} else "PASS"
    latest = (
        {
            "event_id": UUID(int=6),
            "revision": 1,
            "result": result,
            "actor_id": UUID(int=7),
            "created_at": NOW,
            "rationale": "PRIVATE-NARRATIVE",
            "criterion_results": [
                {"criterion_id": key, "result": "PASS", "private_extra": "PRIVATE-CRITERION"}
                for key in ("implementation", "evidence", "operation")
            ],
            "evidence_pins": [
                {
                    "link_id": UUID(int=8),
                    "evidence_id": UUID(int=9),
                    "revision_number": 3,
                    "revision_digest": "a" * 64,
                    "latest_review_event_id": UUID(int=10),
                    "file_id": UUID(int=11),
                    "file_hash": "b" * 64,
                    "scan_verified_at": NOW,
                }
            ],
            "is_stale": state in {"STALE_ASSESSMENT", "UNAVAILABLE_EVIDENCE"},
            "stale_reasons": ["EVIDENCE_CHANGED"] if state == "STALE_ASSESSMENT" else [],
        }
        if assessed
        else None
    )
    findings = []
    if state == "PASS_WITH_OPEN_FINDINGS":
        counts["open_findings"] = 1
        findings = [
            {
                "id": UUID(int=12),
                "source_event_id": UUID(int=6),
                "current_event_id": UUID(int=13),
                "severity": "HIGH",
                "owner_user_id": UUID(int=14),
                "owner_display_name": "PRIVATE-PERSON",
                "due_date": NOW.date(),
                "status": "OPEN",
                "version": 2,
                "created_at": NOW,
                "updated_at": NOW,
            }
        ]
    return AssessmentWorkListResponse.model_validate(
        {
            "tenant_id": TENANT,
            "adoption_id": ADOPTION,
            "answer_revision": 1,
            "selection_revision": 2,
            "is_stale": state == "STALE_WORK",
            "summary": {**counts, "blocked_control_ids": [], "reason_codes": []},
            "items": [
                {
                    "work_id": UUID(int=3),
                    "control_version_id": UUID(int=4),
                    "work_version": 5,
                    "assessment_revision": 1 if assessed else 0,
                    "procedure": {
                        "id": UUID(int=5),
                        "version": "1.0",
                        "digest": "c" * 64,
                        "criteria": [],
                        "disclaimer": "Not a legal procedure",
                    },
                    "latest_assessment": latest,
                    "primary_state": state,
                    "blockers": [],
                    "findings": findings,
                    "history": [
                        {
                            "event_id": UUID(int=6),
                            "revision": 1,
                            "operation_id": uuid4(),
                            "event_type": "ASSESSMENT",
                            "result": "PASS",
                            "observed_work_version": 5,
                            "actor_id": UUID(int=7),
                            "created_at": NOW,
                            "details": {"private": "PRIVATE-HISTORY"},
                        }
                    ],
                    "requirement_results": [{"private": "PRIVATE-REQUIREMENT"}],
                }
            ],
        }
    )


def build(source):
    return _bundle(_project(source, TENANT, NOW))


@pytest.mark.parametrize("state", list(STATE_FIELDS))
def test_every_observed_state_retained_without_overall_score(state):
    report = build(snapshot(state))
    data = json.loads(report.report_json)
    assert data["items"][0]["primary_state"] == state
    assert data["summary"][STATE_FIELDS[state]] == 1
    assert data["is_stale"] == (state == "STALE_WORK")
    assert "readiness_percentage" not in data
    assert DISCLAIMER in report.report_html.decode()
    assert "point-in-time" in report.report_html.decode()


def test_manifest_binds_exact_json_and_html_bytes():
    bundle = build(snapshot("PASS"))
    manifest = json.loads(bundle.manifest_json)
    assert manifest["tenant_id"] == str(TENANT)
    assert manifest["adoption_id"] == str(ADOPTION)
    assert [entry["path"] for entry in manifest["files"]] == ["assessment.json", "assessment.html"]
    for entry, content in zip(
        manifest["files"], (bundle.report_json, bundle.report_html), strict=True
    ):
        assert entry["sha256"] == hashlib.sha256(content).hexdigest()
        assert entry["size_bytes"] == len(content)
    assert bundle == build(snapshot("PASS"))  # random history operation is intentionally omitted


def test_metadata_projection_does_not_leak_private_fields_or_mutate_dto():
    source = snapshot("PASS_WITH_OPEN_FINDINGS")
    before = source.model_dump_json()
    report = build(source)
    combined = report.report_json + report.report_html + report.manifest_json
    assert b"PRIVATE-" not in combined
    assert str(UUID(int=7)).encode() not in combined
    assert str(UUID(int=14)).encode() not in combined
    data = json.loads(report.report_json)
    assert data["items"][0]["latest_assessment"]["evidence_pins"][0]["revision_number"] == 3
    assert data["items"][0]["findings"][0]["version"] == 2
    assert source.model_dump_json() == before


def test_html_escapes_metadata_without_scripts_or_links():
    source = snapshot()
    attack = '<script>alert("x")</script><img src="https://bad.example/a">'
    source.items[0].procedure.version = attack
    source.items[0].blockers = [attack]
    source.summary.reason_codes = [attack]
    html = build(source).report_html.decode()
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;" in html
    assert "&quot;x&quot;" in html
    assert '<html lang="en">' in html
    assert '<th scope="row">' in html


def test_timestamp_normalization_and_naive_rejection():
    source = snapshot()
    alternative = NOW.astimezone(timezone(timedelta(hours=2)))
    assert _project(source, TENANT, alternative) == _project(source, TENANT, NOW)
    with pytest.raises(ReportSnapshotError, match="timezone"):
        _project(source, TENANT, NOW.replace(tzinfo=None))


def test_source_pin_change_changes_both_report_and_manifest():
    source = snapshot("PASS")
    first = build(source)
    source.items[0].latest_assessment.evidence_pins[0].file_hash = "d" * 64
    second = build(source)
    assert first.report_json != second.report_json
    assert first.report_html != second.report_html
    assert first.manifest_json != second.manifest_json


def test_item_and_set_order_does_not_affect_bytes():
    source = snapshot()
    other = source.items[0].model_copy(deep=True)
    other.work_id = UUID(int=20)
    other.control_version_id = UUID(int=21)
    source.items.append(other)
    source.summary.total_controls = 2
    source.summary.unassessed = 2
    source.items[0].blockers = ["Z", "A", "Z"]
    source.summary.reason_codes = ["Z", "A"]
    first = build(source)
    source.items.reverse()
    source.items[1].blockers.reverse()
    source.summary.reason_codes.reverse()
    assert build(source) == first


@pytest.mark.parametrize("field", ["total_controls", "pass_count", "open_findings"])
def test_mismatched_counts_are_not_emitted_as_complete(field):
    source = snapshot()
    setattr(source.summary, field, getattr(source.summary, field) + 1)
    with pytest.raises(ReportSnapshotError, match="incomplete"):
        build(source)


@pytest.mark.parametrize("field", ["work_id", "control_version_id"])
def test_duplicate_records_fail_closed(field):
    source = snapshot()
    other = source.items[0].model_copy(deep=True)
    other.work_id = uuid4()
    other.control_version_id = uuid4()
    setattr(other, field, getattr(source.items[0], field))
    source.items.append(other)
    with pytest.raises(ReportSnapshotError, match="Duplicate"):
        build(source)


def test_duplicate_findings_fail_closed():
    source = snapshot("PASS_WITH_OPEN_FINDINGS")
    source.items[0].findings.append(source.items[0].findings[0].model_copy())
    with pytest.raises(ReportSnapshotError, match="Duplicate"):
        build(source)


def test_foreign_tenant_snapshot_fails_closed():
    with pytest.raises(ReportSnapshotError, match="tenant"):
        _project(snapshot(), uuid4(), NOW)


def test_missing_adoption_and_unknown_requested_adoption_fail_closed():
    source = snapshot()
    source.adoption_id = None
    with pytest.raises(ReportSnapshotError, match="adopted"):
        build(source)
    source.adoption_id = ADOPTION
    source.summary.reason_codes = ["ADOPTION_NOT_FOUND"]
    with pytest.raises(ReportSnapshotError, match="adopted"):
        build(source)


def test_no_work_is_not_presented_as_passed():
    source = snapshot()
    source.items = []
    source.summary.total_controls = source.summary.unassessed = 0
    report = build(source)
    assert json.loads(report.report_json)["scope_state"] == "NO_CONTROL_WORK"
    assert b"not a passing assessment" in report.report_html


@pytest.mark.parametrize(
    "target", ["state", "revision", "digest", "criteria", "stale_pass", "findings"]
)
def test_invalid_source_metadata_is_rejected(target):
    source = snapshot("PASS")
    item = source.items[0]
    if target == "state":
        item.primary_state = "FUTURE_UNKNOWN_STATE"
    elif target == "revision":
        item.work_version = 0
    elif target == "digest":
        item.latest_assessment.evidence_pins[0].file_hash = "invalid"
    elif target == "criteria":
        item.latest_assessment.criterion_results[0]["criterion_id"] = "not_a_criterion"
    elif target == "stale_pass":
        item.latest_assessment.is_stale = True
    else:
        item.findings = snapshot("PASS_WITH_OPEN_FINDINGS").items[0].findings
        source.summary.open_findings = 1
    with pytest.raises(ReportSnapshotError):
        build(source)


def test_reason_mismatch_rejects_torn_read():
    source = snapshot()
    source.summary.reason_codes = ["NEW_BLOCKER"]
    with pytest.raises(ReportSnapshotError, match="reasons"):
        build(source)


def test_stale_report_does_not_mislabel_current_procedure_as_historical():
    report = build(snapshot("STALE_ASSESSMENT"))
    data = json.loads(report.report_json)
    assert data["items"][0]["current_procedure"]["digest"] == "c" * 64
    assert "procedure" not in data["items"][0]
    assert b"Current procedure digest" in report.report_html
    assert b"assessment-time" in report.report_html


@pytest.mark.parametrize("field", ["criterion_id", "result"])
def test_malformed_criterion_metadata_fails_with_controlled_error(field):
    source = snapshot("PASS")
    source.items[0].latest_assessment.criterion_results[0][field] = ["not", "a", "string"]
    with pytest.raises(ReportSnapshotError, match="criterion"):
        build(source)


def test_actual_report_generation_uses_only_selects(db_session, test_setup):
    statements = []
    connection = db_session.connection()

    def observe(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.strip().split()[0].upper())

    event.listen(connection, "before_cursor_execute", observe)
    try:
        CustomerAssessmentReportService(db_session).generate(
            principal=test_setup["owner_p"],
            tenant_context=test_setup["owner_t"],
            captured_at=NOW,
        )
    finally:
        event.remove(connection, "before_cursor_execute", observe)
    assert statements
    assert set(statements) == {"SELECT"}


def test_actual_service_generates_metadata_report(db_session, test_setup):
    report = CustomerAssessmentReportService(db_session).generate(
        principal=test_setup["owner_p"],
        tenant_context=test_setup["owner_t"],
        adoption_id=test_setup["adoption_id"],
        captured_at=NOW,
    )
    data = json.loads(report.report_json)
    assert data["tenant_id"] == str(test_setup["tenant_id"])
    assert data["adoption_id"] == str(test_setup["adoption_id"])
    assert data["summary"]["total_controls"] > 0
    assert any(item["work_id"] == str(test_setup["work"].id) for item in data["items"])


def test_actual_assessment_finding_and_evidence_pins_survive_report(db_session, test_setup):
    service = CustomerAssessmentService(db_session)
    work = test_setup["work"]
    procedure = service.get_procedure(test_setup["mgr_p"], test_setup["mgr_t"], work.id)
    receipt = service.record_assessment(
        test_setup["mgr_p"],
        test_setup["mgr_t"],
        work.id,
        AssessmentCreateRequest(
            operation_id=uuid4(),
            expected_answer_revision=1,
            expected_selection_revision=1,
            expected_work_version=work.version,
            expected_assessment_revision=0,
            procedure_id=procedure.id,
            procedure_version=procedure.version,
            procedure_digest=procedure.digest,
            result="FAIL",
            rationale="PRIVATE-REAL-RATIONALE",
            criterion_results=[
                AssessmentCriterionResultDto(criterion_id=key, result="FAIL")
                for key in ("implementation", "evidence", "operation")
            ],
            evidence_link_ids=[test_setup["link_id"]],
            finding=FindingCreateSpecificationDto(severity="HIGH"),
        ),
    )
    report = CustomerAssessmentReportService(db_session).generate(
        principal=test_setup["mgr_p"],
        tenant_context=test_setup["mgr_t"],
        captured_at=NOW,
    )
    data = json.loads(report.report_json)
    item = next(i for i in data["items"] if i["work_id"] == str(work.id))
    assert item["primary_state"] == "FAIL"
    assert item["latest_assessment"]["event_id"] == str(receipt.event_id)
    assert item["latest_assessment"]["evidence_pins"][0]["link_id"] == str(test_setup["link_id"])
    assert item["findings"][0]["severity"] == "HIGH"
    assert b"PRIVATE-REAL-RATIONALE" not in report.report_json + report.report_html


@pytest.mark.parametrize(
    "denial",
    [
        "mfa",
        "role",
        "principal",
        "foreign_tenant",
        "disabled",
        "entitlement",
        "scoped",
        "workforce",
    ],
)
def test_actual_service_preserves_existing_admission(db_session, test_setup, monkeypatch, denial):
    principal, context = test_setup["owner_p"], test_setup["owner_t"]
    if denial == "mfa":
        principal = replace(principal, mfa_verified=False)
    elif denial == "role":
        context = replace(context, role=Role.EMPLOYEE)
    elif denial == "principal":
        principal = replace(principal, user_id=uuid4())
    elif denial == "foreign_tenant":
        context = replace(context, tenant_id=uuid4())
    elif denial == "disabled":
        monkeypatch.setattr(get_settings(), "enable_customer_demo", False)
    elif denial == "entitlement":
        ent = db_session.scalar(
            select(TenantEntitlement).where(TenantEntitlement.tenant_id == context.tenant_id)
        )
        ent.enabled_modules = []
        db_session.commit()
    elif denial == "scoped":
        context = replace(context, legal_entity_id=uuid4())
    else:
        context = replace(context, is_workforce=True)
    with pytest.raises((HTTPException, AuthorizationDeniedError)):
        CustomerAssessmentReportService(db_session).generate(
            principal=principal,
            tenant_context=context,
            captured_at=NOW,
        )


def test_actual_foreign_or_missing_adoption_does_not_return_a_report(db_session, test_setup):
    with pytest.raises(ReportSnapshotError, match="adopted"):
        CustomerAssessmentReportService(db_session).generate(
            principal=test_setup["owner_p"],
            tenant_context=test_setup["owner_t"],
            adoption_id=uuid4(),
            captured_at=NOW,
        )
