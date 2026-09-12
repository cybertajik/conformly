"""Deterministic, versioned readiness rules engine for pre-audit assessments.

Rules are pure functions. No AI, no generative logic.
Every evaluation records the exact rule version and input snapshot so the
result can be reproduced from recorded state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from conformly.compliance.models import ControlImplementationStatus
from conformly.preaudit.models import CheckResult

# Current rule-set semantic version.  Bump when rule logic or thresholds
# change.  Persisted alongside every check so past assessments remain
# reproducible.
CURRENT_RULE_VERSION = "v1.0.0"


class RuleCategory(StrEnum):
    """Broad grouping used to select which thresholds apply to a control."""

    DEFAULT = "default"
    ACCESS_CONTROL = "access_control"
    DATA_PROTECTION = "data_protection"
    INCIDENT_RESPONSE = "incident_response"
    RISK_MANAGEMENT = "risk_management"


@dataclass(frozen=True, slots=True)
class ReadinessRule:
    """Threshold configuration for a single readiness evaluation."""

    min_evidence_count: int = 1
    requires_valid_policy: bool = True
    max_open_critical_findings: int = 0
    max_open_high_findings: int = 0
    required_implementation_status: ControlImplementationStatus = (
        ControlImplementationStatus.IMPLEMENTED
    )


# ── Default rule catalogue ────────────────────────────────────────────────

DEFAULT_RULES: dict[RuleCategory, ReadinessRule] = {
    RuleCategory.DEFAULT: ReadinessRule(),
    RuleCategory.ACCESS_CONTROL: ReadinessRule(
        min_evidence_count=2,
        requires_valid_policy=True,
        max_open_critical_findings=0,
        max_open_high_findings=0,
    ),
    RuleCategory.DATA_PROTECTION: ReadinessRule(
        min_evidence_count=2,
        requires_valid_policy=True,
        max_open_critical_findings=0,
        max_open_high_findings=0,
    ),
    RuleCategory.INCIDENT_RESPONSE: ReadinessRule(
        min_evidence_count=1,
        requires_valid_policy=True,
        max_open_critical_findings=0,
        max_open_high_findings=1,
    ),
    RuleCategory.RISK_MANAGEMENT: ReadinessRule(
        min_evidence_count=1,
        requires_valid_policy=True,
        max_open_critical_findings=0,
        max_open_high_findings=0,
    ),
}


def get_rule_for_category(category: str) -> ReadinessRule:
    """Return the readiness rule for *category*, falling back to DEFAULT."""
    try:
        key = RuleCategory(category.lower().replace(" ", "_"))
    except ValueError:
        key = RuleCategory.DEFAULT
    return DEFAULT_RULES.get(key, DEFAULT_RULES[RuleCategory.DEFAULT])


# ── Pure evaluation functions ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CheckInput:
    """Snapshot of compliance state for a single control evaluation."""

    evidence_count: int
    policy_count: int
    open_critical_findings: int
    open_high_findings: int
    implementation_status: ControlImplementationStatus | None


# Minimum status ranking for comparison
_STATUS_RANK: dict[ControlImplementationStatus, int] = {
    ControlImplementationStatus.NOT_STARTED: 0,
    ControlImplementationStatus.IN_PROGRESS: 1,
    ControlImplementationStatus.IMPLEMENTED: 2,
    ControlImplementationStatus.ASSESSED: 3,
}


def evaluate_control_readiness(
    rule: ReadinessRule,
    inp: CheckInput,
) -> tuple[CheckResult, float]:
    """Evaluate a single control against *rule* using *inp*.

    Returns ``(result, score)`` where score is 0.0–1.0.
    """
    score = 0.0
    reasons_passed = 0
    total_criteria = 4  # evidence, policy, findings, implementation

    # 1. Evidence
    if inp.evidence_count >= rule.min_evidence_count:
        reasons_passed += 1
        score += 0.25

    # 2. Policy linkage
    if not rule.requires_valid_policy or inp.policy_count > 0:
        reasons_passed += 1
        score += 0.25

    # 3. Open findings within tolerance
    findings_ok = (
        inp.open_critical_findings <= rule.max_open_critical_findings
        and inp.open_high_findings <= rule.max_open_high_findings
    )
    if findings_ok:
        reasons_passed += 1
        score += 0.25

    # 4. Implementation status meets threshold
    actual_rank = _STATUS_RANK.get(
        inp.implementation_status or ControlImplementationStatus.NOT_STARTED, 0
    )
    required_rank = _STATUS_RANK.get(rule.required_implementation_status, 2)
    if actual_rank >= required_rank:
        reasons_passed += 1
        score += 0.25

    result = CheckResult.PASS if reasons_passed == total_criteria else CheckResult.FAIL
    return result, round(score, 4)


def compute_overall_score(
    results: list[tuple[CheckResult, float]],
) -> float:
    """Compute a deterministic overall readiness score from check results.

    Not-applicable checks are excluded from the denominator.
    Pending checks score 0.
    Returns 0.0 when no applicable checks exist.
    """
    applicable = [(r, s) for r, s in results if r != CheckResult.NOT_APPLICABLE]
    if not applicable:
        return 0.0
    total = sum(s for _, s in applicable)
    return round(total / len(applicable) * 100.0, 2)


def snapshot_input(inp: CheckInput) -> dict[str, Any]:
    """Return a JSON-serialisable snapshot of the check input."""
    raw = asdict(inp)
    if raw.get("implementation_status") is not None:
        raw["implementation_status"] = str(raw["implementation_status"])
    return raw
