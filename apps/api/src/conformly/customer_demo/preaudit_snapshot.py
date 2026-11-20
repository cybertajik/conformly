"""Snapshot serialization, hashing, bounds enforcement, and envelope cryptography."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.types import EncryptionContext

MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024  # 8 MiB
MAX_SNAPSHOT_CONTROLS = 512
MAX_SNAPSHOT_LINKS = 2048


class PreauditSnapshotError(ValueError):
    """Base error for snapshot operations."""


class PreauditOversizeError(PreauditSnapshotError):
    """Raised when snapshot data exceeds finite bounds."""


class PreauditIntegrityError(PreauditSnapshotError):
    """Raised when snapshot digest verification fails on read."""


def canonicalize_json(data: Any) -> bytes:
    """Deterministic, sorted, whitespace-stripped canonical UTF-8 JSON bytes."""
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def compute_digest(canonical_bytes: bytes) -> str:
    """Compute 64-char lowercase hex SHA-256 digest over canonical bytes."""
    return hashlib.sha256(canonical_bytes).hexdigest().lower()


def encrypt_snapshot_payload(
    codec: EncryptedFieldCodec,
    tenant_id: UUID,
    snapshot_id: UUID,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Serialize, bound-check, compute digest, and encrypt snapshot payload."""
    canonical_bytes = canonicalize_json(payload)
    if len(canonical_bytes) > MAX_SNAPSHOT_BYTES:
        raise PreauditOversizeError(
            f"Snapshot payload size {len(canonical_bytes)} exceeds maximum {MAX_SNAPSHOT_BYTES} bytes"
        )

    # Check collection bounds if present
    work_items = payload.get("work_items")
    if isinstance(work_items, list) and len(work_items) > MAX_SNAPSHOT_CONTROLS:
        raise PreauditOversizeError(
            f"Snapshot work items count {len(work_items)} exceeds maximum {MAX_SNAPSHOT_CONTROLS}"
        )

    total_links = sum(
        len(item.get("evidence_links", []))
        for item in (work_items if isinstance(work_items, list) else [])
        if isinstance(item, dict)
    )
    if total_links > MAX_SNAPSHOT_LINKS:
        raise PreauditOversizeError(
            f"Snapshot evidence links count {total_links} exceeds maximum {MAX_SNAPSHOT_LINKS}"
        )

    digest = compute_digest(canonical_bytes)
    plaintext = canonical_bytes.decode("utf-8")

    ctx = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="customer_preaudit_snapshot",
        resource_id=str(snapshot_id),
        field_name="payload",
    )
    encrypted_dict = codec.encrypt_text(plaintext, ctx)
    return encrypted_dict, digest


def decrypt_snapshot_payload(
    codec: EncryptedFieldCodec,
    tenant_id: UUID,
    snapshot_id: UUID,
    encrypted_dict: dict[str, Any],
    expected_digest: str,
) -> dict[str, Any]:
    """Decrypt snapshot payload and verify SHA-256 digest integrity."""
    ctx = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="customer_preaudit_snapshot",
        resource_id=str(snapshot_id),
        field_name="payload",
    )
    plaintext = codec.decrypt_text(encrypted_dict, ctx)
    canonical_bytes = canonicalize_json(json.loads(plaintext))
    actual_digest = compute_digest(canonical_bytes)

    if actual_digest != expected_digest.lower():
        raise PreauditIntegrityError(
            f"Snapshot digest verification failed: expected {expected_digest}, computed {actual_digest}"
        )

    return json.loads(plaintext)


def encrypt_event_payload(
    codec: EncryptedFieldCodec,
    tenant_id: UUID,
    event_id: UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Serialize and encrypt event payload."""
    canonical_bytes = canonicalize_json(payload)
    plaintext = canonical_bytes.decode("utf-8")
    ctx = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="customer_preaudit_event",
        resource_id=str(event_id),
        field_name="payload",
    )
    return codec.encrypt_text(plaintext, ctx)


def decrypt_event_payload(
    codec: EncryptedFieldCodec,
    tenant_id: UUID,
    event_id: UUID,
    encrypted_dict: dict[str, Any],
) -> dict[str, Any]:
    """Decrypt event payload."""
    ctx = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="customer_preaudit_event",
        resource_id=str(event_id),
        field_name="payload",
    )
    plaintext = codec.decrypt_text(encrypted_dict, ctx)
    return json.loads(plaintext)

