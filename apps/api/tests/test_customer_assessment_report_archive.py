from __future__ import annotations

import io
import json
import zipfile
from dataclasses import replace
from uuid import uuid4

import pytest

from conformly.customer_demo import assessment_report_archive as module
from conformly.customer_demo.assessment_report_archive import (
    ReportArchiveError,
    package_report,
    verify_report_archive,
)
from tests.test_customer_assessment_report import ADOPTION, TENANT, build, snapshot


def test_deterministic_round_trip_and_exact_membership():
    bundle = build(snapshot("PASS"))
    first = package_report(bundle, tenant_id=TENANT, adoption_id=ADOPTION)
    assert first == package_report(bundle, tenant_id=TENANT, adoption_id=ADOPTION)
    assert verify_report_archive(first.content, tenant_id=TENANT, adoption_id=ADOPTION) == bundle
    assert first.answer_revision == 1
    assert first.selection_revision == 2
    with zipfile.ZipFile(io.BytesIO(first.content)) as archive:
        assert archive.namelist() == ["assessment.json", "assessment.html", "manifest.json"]
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
    assert "PRIVATE-" not in repr(first)


@pytest.mark.parametrize("member", ["report_json", "report_html", "manifest_json"])
def test_modified_bundle_bytes_rejected(member):
    bundle = build(snapshot("PASS"))
    changed = replace(bundle, **{member: getattr(bundle, member) + b"x"})
    with pytest.raises(ReportArchiveError):
        package_report(changed, tenant_id=TENANT, adoption_id=ADOPTION)


@pytest.mark.parametrize("context", ["tenant", "adoption"])
def test_scope_mismatch_rejected_before_packaging_and_after_receipt(context):
    bundle = build(snapshot())
    archive = package_report(bundle, tenant_id=TENANT, adoption_id=ADOPTION)
    tenant, adoption = (uuid4(), ADOPTION) if context == "tenant" else (TENANT, uuid4())
    with pytest.raises(ReportArchiveError, match="scope"):
        package_report(bundle, tenant_id=tenant, adoption_id=adoption)
    with pytest.raises(ReportArchiveError, match="scope"):
        verify_report_archive(archive.content, tenant_id=tenant, adoption_id=adoption)


def test_oversize_bundle_and_archive_rejected(monkeypatch):
    bundle = build(snapshot())
    archive = package_report(bundle, tenant_id=TENANT, adoption_id=ADOPTION)
    monkeypatch.setattr(module, "MAX_ARCHIVE_BYTES", 100)
    with pytest.raises(ReportArchiveError, match="limit"):
        package_report(bundle, tenant_id=TENANT, adoption_id=ADOPTION)
    with pytest.raises(ReportArchiveError, match="limit"):
        verify_report_archive(archive.content, tenant_id=TENANT, adoption_id=ADOPTION)


@pytest.mark.parametrize(
    "variant", ["traversal", "extra", "missing", "duplicate", "compressed", "symlink"]
)
def test_archive_structure_not_extracted_or_trusted(variant):
    bundle = build(snapshot())
    members = [
        ("assessment.json", bundle.report_json),
        ("assessment.html", bundle.report_html),
        ("manifest.json", bundle.manifest_json),
    ]
    if variant == "traversal":
        members[0] = ("../assessment.json", bundle.report_json)
    elif variant == "extra":
        members.append(("secret.txt", b"x"))
    elif variant == "missing":
        members.pop()
    elif variant == "duplicate":
        members[1] = members[0]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members:
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (0o120777 if variant == "symlink" else 0o100600) << 16
            info.compress_type = (
                zipfile.ZIP_DEFLATED if variant == "compressed" else zipfile.ZIP_STORED
            )
            if variant == "duplicate" and name in archive.namelist():
                with pytest.warns(UserWarning, match="Duplicate"):
                    archive.writestr(info, content)
            else:
                archive.writestr(info, content)
    with pytest.raises(ReportArchiveError):
        verify_report_archive(buffer.getvalue(), tenant_id=TENANT, adoption_id=ADOPTION)


def test_duplicate_json_keys_and_wrong_manifest_are_rejected():
    bundle = build(snapshot())
    duplicate = b'{"schema_version":"a","schema_version":"b"}'
    with pytest.raises(ReportArchiveError):
        package_report(
            replace(bundle, manifest_json=duplicate), tenant_id=TENANT, adoption_id=ADOPTION
        )
    manifest = json.loads(bundle.manifest_json)
    manifest["files"][0]["size_bytes"] += 1
    with pytest.raises(ReportArchiveError, match="integrity"):
        package_report(
            replace(bundle, manifest_json=json.dumps(manifest).encode()),
            tenant_id=TENANT,
            adoption_id=ADOPTION,
        )


def test_random_and_crc_corruption_rejected():
    with pytest.raises(ReportArchiveError):
        verify_report_archive(b"not a zip", tenant_id=TENANT, adoption_id=ADOPTION)
    archive = package_report(build(snapshot()), tenant_id=TENANT, adoption_id=ADOPTION)
    damaged = archive.content.replace(b"UNASSESSED", b"XXASSESSED", 1)
    with pytest.raises(ReportArchiveError):
        verify_report_archive(damaged, tenant_id=TENANT, adoption_id=ADOPTION)
