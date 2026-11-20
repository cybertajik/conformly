"""Cryptography, bounds enforcement, hashing and validity clock for Customer Readiness Verification."""

from __future__ import annotations

import calendar
import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from conformly.crypto.fields import EncryptedFieldCodec
from conformly.crypto.types import EncryptionContext

MAX_VERIFICATION_BYTES = 8 * 1024 * 1024  # 8 MiB per encrypted logical payload
MAX_MUTATION_BODY_BYTES = 16 * 1024       # 16 KiB mutation body
MAX_NOTES_CHARS = 4096                    # notes <= 4096 characters


class VerificationError(ValueError):
    """Base error for readiness verification operations."""


class VerificationOversizeError(VerificationError):
    """Raised when verification payload exceeds finite bounds."""


class VerificationIntegrityError(VerificationError):
    """Raised when verification digest or AAD verification fails on read."""


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


def compute_valid_through(issued_at: datetime) -> datetime:
    """Compute exact 12 calendar months validity from injected UTC issuance clock.

    Clamps Feb 29 to valid month-end (Feb 28).
    """
    new_year = issued_at.year + 1
    new_month = issued_at.month
    max_days = calendar.monthrange(new_year, new_month)[1]
    new_day = min(issued_at.day, max_days)
    return issued_at.replace(year=new_year, month=new_month, day=new_day)


def encrypt_verification_payload(
    codec: EncryptedFieldCodec,
    tenant_id: UUID,
    verification_id: UUID,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Serialize, bound-check, compute digest, and encrypt verification payload with domain AAD."""
    canonical_bytes = canonicalize_json(payload)
    if len(canonical_bytes) > MAX_VERIFICATION_BYTES:
        raise VerificationOversizeError(
            f"Verification payload size {len(canonical_bytes)} exceeds maximum {MAX_VERIFICATION_BYTES} bytes"
        )

    digest = compute_digest(canonical_bytes)
    plaintext = canonical_bytes.decode("utf-8")

    ctx = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="customer_readiness_verification",
        resource_id=str(verification_id),
        field_name="payload",
    )
    encrypted_dict = codec.encrypt_text(plaintext, ctx)
    return encrypted_dict, digest


def decrypt_verification_payload(
    codec: EncryptedFieldCodec,
    tenant_id: UUID,
    verification_id: UUID,
    encrypted_dict: dict[str, Any],
    expected_digest: str,
) -> dict[str, Any]:
    """Decrypt verification payload and verify SHA-256 digest and domain AAD."""
    ctx = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="customer_readiness_verification",
        resource_id=str(verification_id),
        field_name="payload",
    )
    try:
        plaintext = codec.decrypt_text(encrypted_dict, ctx)
    except Exception as exc:
        raise VerificationIntegrityError(f"Ciphertext decryption failed: {exc}") from exc

    canonical_bytes = canonicalize_json(json.loads(plaintext))
    actual_digest = compute_digest(canonical_bytes)

    if actual_digest != expected_digest.lower():
        raise VerificationIntegrityError(
            f"Verification digest mismatch: expected {expected_digest}, computed {actual_digest}"
        )

    return json.loads(plaintext)


def encrypt_verification_event_payload(
    codec: EncryptedFieldCodec,
    tenant_id: UUID,
    event_id: UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Serialize and encrypt event payload with domain AAD."""
    canonical_bytes = canonicalize_json(payload)
    if len(canonical_bytes) > MAX_VERIFICATION_BYTES:
        raise VerificationOversizeError(
            f"Event payload size {len(canonical_bytes)} exceeds maximum {MAX_VERIFICATION_BYTES} bytes"
        )
    plaintext = canonical_bytes.decode("utf-8")
    ctx = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="customer_readiness_verification_event",
        resource_id=str(event_id),
        field_name="payload",
    )
    return codec.encrypt_text(plaintext, ctx)


def decrypt_verification_event_payload(
    codec: EncryptedFieldCodec,
    tenant_id: UUID,
    event_id: UUID,
    encrypted_dict: dict[str, Any],
) -> dict[str, Any]:
    """Decrypt event payload."""
    ctx = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="customer_readiness_verification_event",
        resource_id=str(event_id),
        field_name="payload",
    )
    try:
        plaintext = codec.decrypt_text(encrypted_dict, ctx)
    except Exception as exc:
        raise VerificationIntegrityError(f"Event ciphertext decryption failed: {exc}") from exc
    return json.loads(plaintext)

