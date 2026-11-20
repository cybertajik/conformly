"""Private frozen report generation and packaging for V2 Pre-Audit Review Workflow."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from html import escape
from typing import Any
from uuid import UUID

from conformly.customer_demo.preaudit_models import CustomerPreaudit, CustomerPreauditEvent, CustomerPreauditSnapshot

SCHEMA_VERSION = "conformly.synthetic-preaudit-report.v1"
MANIFEST_SCHEMA = "conformly.synthetic-preaudit-manifest.v1"
DISCLAIMER = (
    "Synthetic internal pre-audit readiness report. Not an accredited audit, issued "
    "Readiness Verification, legal certification, public publication, or complete customer data export."
)
LIMITATIONS = (
    "Generated exclusively from persisted, digest-verified frozen review snapshots; "
    "not a live operational report read.",
    "Counts describe observed control compliance states; no overall readiness percentage is calculated.",
    "Narratives, original evidence file contents, learner identities, and tokens are excluded.",
    "Hashes detect modification to these exact bytes; they are not digital signatures or proof of accredited certification.",
)

MAX_ARCHIVE_BYTES = 8 * 1024 * 1024  # 8 MiB


def generate_preaudit_report_archive(
    tenant_id: UUID,
    case: CustomerPreaudit,
    snapshot: CustomerPreauditSnapshot,
    snapshot_payload: dict[str, Any],
    events: list[CustomerPreauditEvent],
    is_current: bool,
) -> tuple[bytes, str]:
    """Build deterministic, bounded ZIP archive containing preaudit.json, preaudit.html, and manifest.json."""
    # 1. Build preaudit.json
    sanitized_events = [
        {
            "revision": ev.revision,
            "event_type": ev.event_type,
            "actor_user_id": str(ev.actor_user_id),
            "prior_status": ev.prior_status,
            "new_status": ev.new_status,
            "created_at": ev.created_at.isoformat(),
        }
        for ev in events
    ]

    # Sanitize frozen_data with explicit metadata allowlist (no raw narratives or learner data)
    sanitized_work_items = [
        {
            "work_id": str(item.get("work_id", "")),
            "control_version_id": str(item.get("control_version_id", "")),
            "work_version": item.get("work_version", 1),
            "primary_state": item.get("primary_state", ""),
            "assessment_revision": item.get("assessment_revision", 0),
            "latest_assessment_result": item.get("latest_assessment", {}).get("result"),
            "evidence_links": [
                {
                    "link_id": str(lk.get("link_id", "")),
                    "evidence_id": str(lk.get("evidence_id", "")),
                    "revision_number": lk.get("revision_number", 1),
                    "digest": lk.get("digest", ""),
                    "review_status": lk.get("review_status", ""),
                }
                for lk in item.get("evidence_links", [])
            ],
            "open_findings_count": item.get("open_findings_count", 0),
        }
        for item in snapshot_payload.get("work_items", [])
    ]

    sanitized_blockers = [
        {
            "code": b.get("code", "BLOCKER"),
            "description": b.get("description", ""),
            "work_id": str(b.get("work_id", "")) if b.get("work_id") else None,
            "control_code": b.get("control_code"),
        }
        for b in snapshot_payload.get("blockers", [])
    ]

    sanitized_frozen_data = {
        "scope_snapshot_id": str(snapshot_payload.get("scope_snapshot_id", "")),
        "adoption_id": str(snapshot_payload.get("adoption_id", "")),
        "review_fingerprint": snapshot_payload.get("review_fingerprint", ""),
        "work_items": sanitized_work_items,
        "blockers": sanitized_blockers,
    }

    report_dict = {
        "schema_version": SCHEMA_VERSION,
        "disclaimer": DISCLAIMER,
        "limitations": list(LIMITATIONS),
        "generated_at": snapshot.created_at.isoformat(),
        "tenant_id": str(tenant_id),
        "case_id": str(case.id),
        "status": case.status,
        "revision": case.revision,
        "is_current": is_current,
        "snapshot": {
            "id": str(snapshot.id),
            "kind": snapshot.kind,
            "sequence": snapshot.sequence,
            "digest": snapshot.digest,
            "created_at": snapshot.created_at.isoformat(),
        },
        "frozen_data": sanitized_frozen_data,
        "history": sanitized_events,
    }
    report_json = json.dumps(
        report_dict,
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8")

    # 2. Build preaudit.html
    html_lines = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"utf-8\">",
        "  <title>Conformly Pre-Audit Readiness Report</title>",
        "  <style>",
        "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.5; color: #1e293b; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }",
        "    .header { border-bottom: 2px solid #0284c7; padding-bottom: 1rem; margin-bottom: 1.5rem; }",
        "    .badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.85rem; font-weight: 600; }",
        "    .badge-approved { background: #dcfce7; color: #166534; }",
        "    .badge-review { background: #e0f2fe; color: #0369a1; }",
        "    .badge-draft { background: #f1f5f9; color: #475569; }",
        "    .card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; }",
        "    .disclaimer { font-size: 0.85rem; color: #64748b; margin-top: 2rem; border-top: 1px solid #e2e8f0; padding-top: 1rem; }",
        "    table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }",
        "    th, td { border: 1px solid #cbd5e1; padding: 0.5rem; text-align: left; font-size: 0.9rem; }",
        "    th { background: #f1f5f9; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <div class=\"header\">",
        "    <h1>Pre-Audit Readiness Review</h1>",
        f"    <p><strong>Tenant ID:</strong> {escape(str(tenant_id))} | <strong>Case ID:</strong> {escape(str(case.id))}</p>",
        f"    <p><strong>Status:</strong> <span class=\"badge badge-approved\">{escape(case.status)}</span> | <strong>Revision:</strong> {case.revision} | <strong>Current:</strong> {'YES' if is_current else 'NO (STALE)'}</p>",
        f"    <p><strong>Snapshot Digest:</strong> <code>{escape(snapshot.digest)}</code></p>",
        "  </div>",
        "  <div class=\"card\">",
        "    <h2>Scope & Findings Summary</h2>",
    ]

    work_items = snapshot_payload.get("work_items", [])
    blockers = snapshot_payload.get("blockers", [])
    html_lines.append(f"    <p><strong>Total Controls in Scope:</strong> {len(work_items)} | <strong>Blockers:</strong> {len(blockers)}</p>")

    if work_items:
        html_lines.append("    <table>")
        html_lines.append("      <thead><tr><th>Work ID</th><th>Control Version ID</th><th>State</th><th>Assessment</th></tr></thead>")
        html_lines.append("      <tbody>")
        for item in work_items:
            html_lines.append(
                f"        <tr><td>{escape(str(item.get('work_id', '')))}</td>"
                f"<td>{escape(str(item.get('control_version_id', '')))}</td>"
                f"<td>{escape(str(item.get('primary_state', '')))}</td>"
                f"<td>{escape(str(item.get('latest_assessment', {}).get('result', '')))}</td></tr>"
            )
        html_lines.append("      </tbody>")
        html_lines.append("    </table>")

    html_lines.extend([
        "  </div>",
        "  <div class=\"card\">",
        "    <h2>Timeline & Decisions</h2>",
        "    <table>",
        "      <thead><tr><th>Rev</th><th>Event</th><th>Actor</th><th>Status Transition</th><th>Date</th></tr></thead>",
        "      <tbody>",
    ])
    for ev in sanitized_events:
        html_lines.append(
            f"        <tr><td>{ev['revision']}</td><td>{escape(ev['event_type'])}</td>"
            f"<td>{escape(ev['actor_user_id'])}</td>"
            f"<td>{escape(str(ev['prior_status']))} &rarr; {escape(ev['new_status'])}</td>"
            f"<td>{escape(ev['created_at'])}</td></tr>"
        )
    html_lines.extend([
        "      </tbody>",
        "    </table>",
        "  </div>",
        "  <div class=\"disclaimer\">",
        f"    <p><strong>Disclaimer:</strong> {escape(DISCLAIMER)}</p>",
        "    <ul>",
    ])
    for lim in LIMITATIONS:
        html_lines.append(f"      <li>{escape(lim)}</li>")
    html_lines.extend([
        "    </ul>",
        "  </div>",
        "</body>",
        "</html>",
    ])
    report_html = "\n".join(html_lines).encode("utf-8")

    # 3. Build manifest.json
    manifest_dict = {
        "schema_version": MANIFEST_SCHEMA,
        "report_schema_version": SCHEMA_VERSION,
        "disclaimer": DISCLAIMER,
        "tenant_id": str(tenant_id),
        "case_id": str(case.id),
        "snapshot_id": str(snapshot.id),
        "snapshot_digest": snapshot.digest,
        "files": [
            {
                "path": "preaudit.json",
                "size_bytes": len(report_json),
                "sha256": hashlib.sha256(report_json).hexdigest(),
            },
            {
                "path": "preaudit.html",
                "size_bytes": len(report_html),
                "sha256": hashlib.sha256(report_html).hexdigest(),
            },
        ],
    }
    manifest_json = json.dumps(
        manifest_dict,
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8")

    total_bytes = len(report_json) + len(report_html) + len(manifest_json)
    if total_bytes > MAX_ARCHIVE_BYTES:
        raise ValueError(f"Report archive size {total_bytes} exceeds maximum {MAX_ARCHIVE_BYTES}")

    # 4. In-memory zip packaging
    fixed_time = (2026, 11, 1, 0, 0, 0)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname, data in [
            ("manifest.json", manifest_json),
            ("preaudit.html", report_html),
            ("preaudit.json", report_json),
        ]:
            zinfo = zipfile.ZipInfo(fname, date_time=fixed_time)
            zinfo.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(zinfo, data)

    zip_content = buf.getvalue()
    zip_sha256 = hashlib.sha256(zip_content).hexdigest()
    return zip_content, zip_sha256

