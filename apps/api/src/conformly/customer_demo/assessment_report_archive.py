"""Deterministic, bounded, in-memory packaging for synthetic assessment reports."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from conformly.customer_demo.assessment_report import (
    DISCLAIMER,
    SCHEMA_VERSION,
    AssessmentReportBundle,
)

MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
_MEMBER_NAMES = ("assessment.json", "assessment.html", "manifest.json")
_MANIFEST_SCHEMA = "conformly.synthetic-assessment-manifest.v1"


class ReportArchiveError(ValueError):
    """Invalid or oversized report artifact; messages never include report content."""


@dataclass(frozen=True, slots=True)
class ReportArchive:
    content: bytes = field(repr=False)
    sha256: str
    manifest_sha256: str
    tenant_id: UUID
    adoption_id: UUID
    answer_revision: int
    selection_revision: int


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReportArchiveError("Duplicate JSON member in report")
        result[key] = value
    return result


def _object(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ReportArchiveError("Malformed report metadata") from exc
    if not isinstance(value, dict):
        raise ReportArchiveError("Report metadata must be an object")
    return value


def _revision(value: object) -> int:
    if type(value) is not int or value < 1:
        raise ReportArchiveError("Invalid report revision")
    return value


def _validate_bundle(
    bundle: AssessmentReportBundle,
    *,
    tenant_id: UUID,
    adoption_id: UUID,
) -> tuple[int, int]:
    if (
        sum(map(len, (bundle.report_json, bundle.report_html, bundle.manifest_json)))
        > MAX_ARCHIVE_BYTES
    ):
        raise ReportArchiveError("Report exceeds download limit")
    report, manifest = _object(bundle.report_json), _object(bundle.manifest_json)
    if (
        report.get("schema_version") != SCHEMA_VERSION
        or manifest.get("schema_version") != _MANIFEST_SCHEMA
        or manifest.get("report_schema_version") != SCHEMA_VERSION
        or report.get("disclaimer") != DISCLAIMER
        or manifest.get("disclaimer") != DISCLAIMER
    ):
        raise ReportArchiveError("Unsupported report schema")
    for key, expected in (("tenant_id", str(tenant_id)), ("adoption_id", str(adoption_id))):
        if report.get(key) != expected or manifest.get(key) != expected:
            raise ReportArchiveError("Report scope mismatch")
    if not report.get("captured_at") or report.get("captured_at") != manifest.get("captured_at"):
        raise ReportArchiveError("Report capture mismatch")
    revisions = (
        _revision(report.get("answer_revision")),
        _revision(report.get("selection_revision")),
    )
    expected_files = [
        {"path": name, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for name, data in (
            ("assessment.json", bundle.report_json),
            ("assessment.html", bundle.report_html),
        )
    ]
    if manifest.get("files") != expected_files:
        raise ReportArchiveError("Report manifest integrity mismatch")
    return revisions


def package_report(
    bundle: AssessmentReportBundle,
    *,
    tenant_id: UUID,
    adoption_id: UUID,
) -> ReportArchive:
    answer, selection = _validate_bundle(bundle, tenant_id=tenant_id, adoption_id=adoption_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in zip(
            _MEMBER_NAMES,
            (bundle.report_json, bundle.report_html, bundle.manifest_json),
            strict=True,
        ):
            member = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            member.create_system = 3
            member.external_attr = 0o100600 << 16
            archive.writestr(member, data)
    content = buffer.getvalue()
    if len(content) > MAX_ARCHIVE_BYTES:
        raise ReportArchiveError("Report exceeds download limit")
    return ReportArchive(
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        manifest_sha256=hashlib.sha256(bundle.manifest_json).hexdigest(),
        tenant_id=tenant_id,
        adoption_id=adoption_id,
        answer_revision=answer,
        selection_revision=selection,
    )


def verify_report_archive(
    content: bytes,
    *,
    tenant_id: UUID,
    adoption_id: UUID,
) -> AssessmentReportBundle:
    """Verify exact archive membership and hashes without extracting any files.

    Integrity checks are not authentication or a signature. The caller must supply
    authorized expected context; never accept archive metadata as access authority.
    """
    if len(content) > MAX_ARCHIVE_BYTES:
        raise ReportArchiveError("Report exceeds download limit")
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
            members = archive.infolist()
            if [entry.filename for entry in members] != list(_MEMBER_NAMES):
                raise ReportArchiveError("Unexpected report archive membership")
            if (
                archive.comment
                or sum(entry.file_size for entry in members) > MAX_ARCHIVE_BYTES
                or any(
                    entry.compress_type != zipfile.ZIP_STORED
                    or entry.flag_bits & 1
                    or entry.is_dir()
                    or entry.external_attr >> 16 != 0o100600
                    for entry in members
                )
            ):
                raise ReportArchiveError("Unsupported report archive structure")
            contents = [archive.read(member) for member in members]
    except (zipfile.BadZipFile, RuntimeError, OSError, EOFError) as exc:
        raise ReportArchiveError("Invalid report archive") from exc
    bundle = AssessmentReportBundle(*contents)
    _validate_bundle(bundle, tenant_id=tenant_id, adoption_id=adoption_id)
    if package_report(bundle, tenant_id=tenant_id, adoption_id=adoption_id).content != content:
        raise ReportArchiveError("Non-canonical report archive")
    return bundle
