"""Allowlisted private preview projection for Customer Readiness Verification."""

from __future__ import annotations

from typing import Any

from conformly.customer_demo.verification_models import CustomerReadinessVerification
from conformly.customer_demo.verification_schemas import (
    SYNTHETIC_MARKER,
    TEST_QUALIFICATION,
    VerificationProjectionResponse,
)


def build_verification_projection(
    verification: CustomerReadinessVerification,
    decrypted_payload: dict[str, Any],
    effective_status: str,
    effective_reason: str | None,
) -> VerificationProjectionResponse:
    """Construct safe allowlisted private projection without sensitive internal secrets.

    Excludes:
    - tenant database IDs
    - evidence IDs / URLs / keys / hashes
    - user names / emails / IDs
    - private notes / reasoning
    - crypto metadata / raw ciphers / raw snapshots
    """
    scope_summary = decrypted_payload.get("scope_summary", {})
    controls_count = int(decrypted_payload.get("controls_count") or scope_summary.get("controls_count", 0))
    covered_count = int(decrypted_payload.get("covered_count") or scope_summary.get("covered_count", controls_count))
    exempt_count = int(decrypted_payload.get("exempt_count") or scope_summary.get("exempt_count", 0))
    safe_scope_summary = {
        "framework_id": decrypted_payload.get("framework_id"),
        "version_id": decrypted_payload.get("framework_version"),
        "controls_count": controls_count,
        "covered_count": covered_count,
        "exempt_count": exempt_count,
    }

    return VerificationProjectionResponse(
        verification_id=verification.id,
        synthetic_marker=SYNTHETIC_MARKER,
        test_qualification=TEST_QUALIFICATION,
        status=verification.status,
        effective_status=effective_status,
        effective_reason=effective_reason,
        issued_at=verification.issued_at,
        valid_through=verification.valid_through,
        framework_id=decrypted_payload.get("framework_id"),
        framework_version=decrypted_payload.get("framework_version"),
        framework_display_name=decrypted_payload.get("framework_display_name") or "Synthetic Customer Baseline Pack",
        organization_display_name=decrypted_payload.get("organization_display_name") or "Conformly Demo Organization",
        scope_summary=safe_scope_summary,
        controls_count=controls_count,
        limitations=decrypted_payload.get("limitations", []),
        superseded_by_id=verification.superseded_by_id,
        supersedes_id=verification.supersedes_id,
        public_disclosure_statement="Synthetic demonstration qualification; non-accredited and not a public certification body endorsement.",
    )
