"""Automated Tests for Paid Pilot Release Gates & Sign-Off Subsystem."""

from conformly.release.gates import (
    GateStatus,
    evaluate_disaster_recovery_gate,
    evaluate_legal_product_gate,
    evaluate_migration_gate,
    evaluate_tenancy_security_gate,
    evaluate_vulnerability_crypto_gate,
    run_all_release_gates,
)


def test_gate_1_migration_and_schema_integrity() -> None:
    """Verifies Gate 1: Schema migration revisions, table registrations, and clean generation."""
    result = evaluate_migration_gate()
    assert result.status == GateStatus.PASSED
    assert result.details["registered_tables_count"] >= 50
    assert result.details["schema_integrity"] == "OK"


def test_gate_2_tenancy_and_authorization_security() -> None:
    """Verifies Gate 2: Cross-tenant isolation boundaries, RLS, and role capability boundaries."""
    result = evaluate_tenancy_security_gate()
    assert result.status == GateStatus.PASSED
    assert result.details["cross_tenant_denial"] == "VERIFIED"
    assert result.details["privilege_escalation_denial"] == "VERIFIED"
    assert result.details["canonical_six_roles"] == "ENFORCED"


def test_gate_3_disaster_recovery_rebuild() -> None:
    """Verifies Gate 3: Clean-room database + object restore, RTO <= 4h, and RPO <= 1h."""
    result = evaluate_disaster_recovery_gate()
    assert result.status == GateStatus.PASSED
    assert result.details["manifest_integrity"] == "VERIFIED"
    assert result.details["measured_rto_seconds"] < 4 * 3600
    assert result.details["measured_rpo_seconds"] < 1 * 3600


def test_gate_4_vulnerability_and_cryptographic_defense() -> None:
    """Verifies Gate 4: AES-256-GCM AEAD tamper resistance and malware heuristic barriers."""
    result = evaluate_vulnerability_crypto_gate()
    assert result.status == GateStatus.PASSED
    assert result.details["tamper_detection"] == "VERIFIED"
    assert result.details["eicar_detection"] == "VERIFIED"
    assert result.details["executable_barrier"] == "VERIFIED"


def test_gate_5_legal_and_product_positioning() -> None:
    """Verifies Gate 5: Pre-audit disclaimers, non-contractual pilot SLAs, and whistleblower privacy."""
    result = evaluate_legal_product_gate()
    assert result.status == GateStatus.PASSED
    assert result.details["preaudit_disclaimer"] == "VERIFIED"
    assert result.details["pilot_service_levels"] == "NON_CONTRACTUAL_OPERATIONAL_TARGETS"
    assert result.details["sla_prerequisite"] == "6_MONTHS_EVIDENCE_PLUS_2_RESTORES_REQUIRED"
    assert result.details["cancellation_window"] == "30D_EXPORT_90D_DELETION"
    assert result.details["whistleblower_privacy"] == "ANONYMOUS_PBKDF2_PROTECTED"


def test_run_all_release_gates_passes_for_pilot() -> None:
    """Comprehensive release sign-off evaluation verifying all 5 gates pass simultaneously."""
    report = run_all_release_gates()
    assert report.overall_status == GateStatus.PASSED
    assert report.total_gates_count == 5
    assert report.passed_gates_count == 5
    assert report.signoff_manifest_sha256 != ""
    assert all(g.status == GateStatus.PASSED for g in report.gate_results)
