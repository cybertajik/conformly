"""Private, in-memory synthetic assessment reports; not an issuance/export API.

Only CustomerAssessmentReportService is an admitted entry point. The private
projection is metadata-only, never a substitute for authorization. No filesystem,
network, persistence, publication, or new readiness-scoring behavior lives here.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from conformly.authz.policy import Principal, TenantContext
from conformly.customer_demo.assessment_schemas import AssessmentWorkListResponse
from conformly.customer_demo.assessment_service import CustomerAssessmentService

SCHEMA_VERSION = "conformly.synthetic-assessment-report.v1"
DISCLAIMER = (
    "Synthetic internal operational snapshot. Not a certification, legal compliance "
    "decision, issued Readiness Verification, or complete customer data export."
)
LIMITATIONS = (
    "Captured from the existing multi-query assessment read; not a guaranteed "
    "point-in-time database snapshot or frozen pre-audit scope.",
    "Counts describe observed control states; no overall readiness percentage is calculated.",
    "Procedure metadata describes the current read model. Historical assessment-time "
    "procedure snapshots and complete framework-pack provenance are not included.",
    "Narratives, personal names, actor identifiers, file contents, history and original "
    "evidence files are intentionally excluded.",
    "Hashes detect changes to these exact bytes; they are not signatures or proof of issuance.",
)
STATE_FIELDS = {
    "STALE_WORK": "stale_work",
    "NEEDS_INFORMATION": "needs_information",
    "NOT_APPLICABLE": "not_applicable",
    "UNASSESSED": "unassessed",
    "UNAVAILABLE_EVIDENCE": "unavailable_evidence",
    "STALE_ASSESSMENT": "stale_assessment",
    "INSUFFICIENT_EVIDENCE": "insufficient_evidence",
    "FAIL": "fail",
    "PARTIAL": "partial",
    "PASS_WITH_OPEN_FINDINGS": "pass_with_open_findings",
    "PASS": "pass_count",
}
FINDING_FIELDS = {
    "OPEN": "open_findings",
    "IN_REMEDIATION": "in_remediation_findings",
    "RESOLVED": "resolved_findings",
}
_RESULTS = {"PASS", "PARTIAL", "FAIL", "INSUFFICIENT_EVIDENCE"}


class ReportSnapshotError(ValueError):
    """The admitted source cannot be represented safely; retry a fresh read."""


@dataclass(frozen=True, slots=True)
class AssessmentReportBundle:
    """Immutable bytes. Caller must retain private delivery/storage boundaries."""

    report_json: bytes
    report_html: bytes
    manifest_json: bytes


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def _utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ReportSnapshotError("Capture time must include a timezone")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _positive(value: int, *, zero: bool = False) -> None:
    if type(value) is not int or value < (0 if zero else 1):
        raise ReportSnapshotError("Invalid revision in assessment snapshot")


def _digest(value: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ReportSnapshotError("Invalid digest in assessment snapshot")


def _unique(values: list[UUID]) -> None:
    if len(values) != len(set(values)):
        raise ReportSnapshotError("Duplicate records in assessment snapshot")


def _project(
    source: AssessmentWorkListResponse, tenant_id: UUID, captured_at: datetime
) -> dict[str, Any]:
    # Copy once: projection/rendering cannot mutate the service DTOs.
    source = source.model_copy(deep=True)
    if source.tenant_id != tenant_id:
        raise ReportSnapshotError("Assessment snapshot tenant mismatch")
    if source.adoption_id is None or "ADOPTION_NOT_FOUND" in source.summary.reason_codes:
        raise ReportSnapshotError("An available adopted scope is required")
    _positive(source.answer_revision)
    _positive(source.selection_revision)
    _unique([item.work_id for item in source.items])
    _unique([item.control_version_id for item in source.items])
    _unique([finding.id for item in source.items for finding in item.findings])
    states = Counter(item.primary_state for item in source.items)
    findings = Counter(f.status for item in source.items for f in item.findings)
    if set(states) - STATE_FIELDS.keys() or set(findings) - FINDING_FIELDS.keys():
        raise ReportSnapshotError("Unsupported state in assessment snapshot")
    counts = {"total_controls": len(source.items)}
    counts.update({field: states[state] for state, field in STATE_FIELDS.items()})
    counts.update({field: findings[state] for state, field in FINDING_FIELDS.items()})
    if any(getattr(source.summary, key) != value for key, value in counts.items()):
        raise ReportSnapshotError("Assessment summary changed or is incomplete; read again")
    reasons = sorted(set(reason for item in source.items for reason in item.blockers))
    if reasons != sorted(set(source.summary.reason_codes)):
        raise ReportSnapshotError("Assessment reasons changed or are incomplete; read again")
    items: list[dict[str, Any]] = []
    for item in sorted(source.items, key=lambda entry: str(entry.work_id)):
        _positive(item.work_version)
        _positive(item.assessment_revision, zero=True)
        _digest(item.procedure.digest)
        latest = item.latest_assessment
        assessment: dict[str, Any] | None = None
        if latest is not None:
            _positive(latest.revision)
            if latest.revision > item.assessment_revision or latest.result not in _RESULTS:
                raise ReportSnapshotError("Inconsistent assessment revision or result")
            _unique([pin.link_id for pin in latest.evidence_pins])
            for pin in latest.evidence_pins:
                _positive(pin.revision_number)
                _digest(pin.revision_digest)
                _digest(pin.file_hash)
            criteria = [
                {"criterion_id": c.get("criterion_id"), "result": c.get("result")}
                for c in latest.criterion_results
            ]
            if (
                len(criteria) != 3
                or any(
                    not isinstance(c["criterion_id"], str) or not isinstance(c["result"], str)
                    for c in criteria
                )
                or {c["criterion_id"] for c in criteria}
                != {"implementation", "evidence", "operation"}
                or any(c["result"] not in _RESULTS - {"PARTIAL"} for c in criteria)
            ):
                raise ReportSnapshotError("Invalid criterion results")
            assessment = {
                "event_id": str(latest.event_id),
                "revision": latest.revision,
                "result": latest.result,
                # Existing SQLite fixtures return naive DB times. Preserve source
                # text verbatim rather than inventing a timezone for those values.
                "created_at": latest.created_at.isoformat(),
                "is_stale": latest.is_stale,
                "stale_reasons": sorted(set(latest.stale_reasons)),
                "criteria": sorted(criteria, key=lambda c: str(c["criterion_id"])),
                "evidence_pins": [
                    pin.model_dump(mode="json")
                    for pin in sorted(latest.evidence_pins, key=lambda p: str(p.link_id))
                ],
            }
        open_findings = [f for f in item.findings if f.status != "RESOLVED"]
        if item.primary_state in {"PASS", "PASS_WITH_OPEN_FINDINGS"}:
            if latest is None or latest.result != "PASS" or latest.is_stale or item.blockers:
                raise ReportSnapshotError("Passing state lacks a current passing assessment")
            if bool(open_findings) != (item.primary_state == "PASS_WITH_OPEN_FINDINGS"):
                raise ReportSnapshotError("Passing state conflicts with findings")
        for finding in item.findings:
            _positive(finding.version)
            if finding.severity not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
                raise ReportSnapshotError("Unsupported finding severity")
        items.append(
            {
                "work_id": str(item.work_id),
                "control_version_id": str(item.control_version_id),
                "work_version": item.work_version,
                "assessment_revision": item.assessment_revision,
                "primary_state": item.primary_state,
                "blockers": sorted(set(item.blockers)),
                "current_procedure": {
                    "id": str(item.procedure.id),
                    "version": item.procedure.version,
                    "digest": item.procedure.digest,
                },
                "latest_assessment": assessment,
                "findings": [
                    {
                        "id": str(f.id),
                        "source_event_id": str(f.source_event_id),
                        "current_event_id": str(f.current_event_id),
                        "version": f.version,
                        "status": f.status,
                        "severity": f.severity,
                        "due_date": f.due_date.isoformat() if f.due_date else None,
                    }
                    for f in sorted(item.findings, key=lambda finding: str(finding.id))
                ],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "purpose": "SYNTHETIC_INTERNAL_OPERATIONAL_SNAPSHOT",
        "disclaimer": DISCLAIMER,
        "limitations": list(LIMITATIONS),
        "tenant_id": str(tenant_id),
        "adoption_id": str(source.adoption_id),
        "captured_at": _utc(captured_at),
        "answer_revision": source.answer_revision,
        "selection_revision": source.selection_revision,
        "is_stale": source.is_stale,
        "scope_state": "NO_CONTROL_WORK" if not items else "OBSERVED_CONTROL_WORK",
        "summary": counts,
        "reason_codes": reasons,
        "items": items,
    }


def _html(report: dict[str, Any]) -> bytes:
    def text(value: Any) -> str:
        return escape(str(value), quote=True)

    def row(label: str, value: Any) -> str:
        return f'<tr><th scope="row">{text(label)}</th><td>{text(value)}</td></tr>'

    context = "".join(
        row(key.replace("_", " ").title(), report[key])
        for key in (
            "tenant_id",
            "adoption_id",
            "captured_at",
            "answer_revision",
            "selection_revision",
            "is_stale",
            "scope_state",
        )
    )
    counts = "".join(
        row(key.replace("_", " ").title(), value) for key, value in report["summary"].items()
    )
    sections = []
    for item in report["items"]:
        latest = item["latest_assessment"]
        details = "".join(
            row(key.replace("_", " ").title(), item[key])
            for key in (
                "control_version_id",
                "work_version",
                "assessment_revision",
                "primary_state",
            )
        )
        details += row("Current procedure ID", item["current_procedure"]["id"])
        details += row("Current procedure version", item["current_procedure"]["version"])
        details += row("Current procedure digest", item["current_procedure"]["digest"])
        details += row("Blockers", ", ".join(item["blockers"]) or "None reported")
        if latest:
            details += row("Assessment event", latest["event_id"])
            details += row("Assessment revision", latest["revision"])
            details += row("Assessment recorded at", latest["created_at"])
            details += row("Assessment result", latest["result"])
            details += row("Assessment stale", latest["is_stale"])
            details += row("Stale reasons", ", ".join(latest["stale_reasons"]) or "None reported")
            for criterion in latest["criteria"]:
                details += row(criterion["criterion_id"], criterion["result"])
        else:
            details += row("Assessment", "Not assessed")
        pins = (latest or {}).get("evidence_pins", [])
        evidence = (
            "".join(
                "<li><pre>" + text(json.dumps(pin, sort_keys=True, indent=2)) + "</pre></li>"
                for pin in pins
            )
            or "<li>No assessment evidence pins</li>"
        )
        findings = (
            "".join(
                "<li><pre>" + text(json.dumps(f, sort_keys=True, indent=2)) + "</pre></li>"
                for f in item["findings"]
            )
            or "<li>No findings reported</li>"
        )
        sections.append(
            f"<section><h2>Control work {text(item['work_id'])}</h2>"
            f"<table><caption>Observed control state and version pins</caption>{details}</table>"
            f"<h3>Evidence pins</h3><ul>{evidence}</ul>"
            f"<h3>Findings</h3><ul>{findings}</ul></section>"
        )
    body = "".join(sections) or "<p>No control work. This is not a passing assessment.</p>"
    limits = "".join(f"<li>{text(value)}</li>" for value in report["limitations"])
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Conformly internal assessment snapshot</title>"
        "<style>body{font:16px system-ui,sans-serif;line-height:1.5;max-width:70rem;"
        "margin:2rem auto;padding:0 1rem;color:#17212b}table{width:100%;border-collapse:"
        "collapse;margin:1rem 0}th,td{text-align:left;vertical-align:top;padding:.5rem;"
        "border-bottom:1px solid #ccd2d8;overflow-wrap:anywhere}caption{text-align:left;"
        "font-weight:bold}pre{white-space:pre-wrap;overflow-wrap:anywhere}"
        "section{margin:2rem 0}h2{overflow-wrap:anywhere}"
        "@media print{body{margin:0;font-size:11pt}tr,li{break-inside:avoid}}</style>"
        "</head><body><main><h1>Conformly internal assessment snapshot</h1>"
        f"<p><strong>{text(report['disclaimer'])}</strong></p>"
        f"<table><caption>Captured scope</caption>{context}</table>"
        f"<h2>Observed counts</h2><table><caption>States, not a readiness score</caption>"
        f"{counts}</table>{body}<h2>Limitations</h2><ul>{limits}</ul>"
        "</main></body></html>\n"
    ).encode()


def _bundle(report: dict[str, Any]) -> AssessmentReportBundle:
    data, html = _json_bytes(report), _html(report)
    manifest = {
        "schema_version": "conformly.synthetic-assessment-manifest.v1",
        "report_schema_version": SCHEMA_VERSION,
        "tenant_id": report["tenant_id"],
        "adoption_id": report["adoption_id"],
        "captured_at": report["captured_at"],
        "disclaimer": DISCLAIMER,
        "files": [
            {
                "path": name,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for name, content in (("assessment.json", data), ("assessment.html", html))
        ],
    }
    return AssessmentReportBundle(data, html, _json_bytes(manifest))


class CustomerAssessmentReportService:
    """Admitted internal call; intentionally not mounted as an HTTP endpoint."""

    def __init__(self, session: Session) -> None:
        self.assessments = CustomerAssessmentService(session)

    def generate(
        self,
        *,
        principal: Principal,
        tenant_context: TenantContext,
        adoption_id: UUID | None = None,
        captured_at: datetime | None = None,
    ) -> AssessmentReportBundle:
        source = self.assessments.get_assessment_work_list(
            principal=principal,
            tenant_context=tenant_context,
            adoption_id=adoption_id,
        )
        # A future adapter must supply authenticated server context, not client DTOs.
        if adoption_id is not None and source.adoption_id != adoption_id:
            raise ReportSnapshotError("Requested adoption is unavailable")
        report = _project(source, tenant_context.tenant_id, captured_at or datetime.now(UTC))
        return _bundle(report)
