"""Tests for pre-audit readiness rules engine."""

from conformly.compliance.models import ControlImplementationStatus
from conformly.preaudit.models import CheckResult
from conformly.preaudit.rules import (
    CURRENT_RULE_VERSION,
    CheckInput,
    ReadinessRule,
    compute_overall_score,
    evaluate_control_readiness,
    get_rule_for_category,
    snapshot_input,
)


class TestRuleVersion:
    def test_current_version_is_semantic(self) -> None:
        parts = CURRENT_RULE_VERSION.lstrip("v").split(".")
        assert len(parts) == 3
        for p in parts:
            assert p.isdigit()


class TestGetRuleForCategory:
    def test_default_for_unknown_category(self) -> None:
        rule = get_rule_for_category("nonexistent_category_xyz")
        assert rule == get_rule_for_category("default")

    def test_access_control_category(self) -> None:
        rule = get_rule_for_category("access_control")
        assert rule.min_evidence_count == 2

    def test_case_insensitive(self) -> None:
        rule = get_rule_for_category("ACCESS_CONTROL")
        assert rule.min_evidence_count == 2


class TestEvaluateControlReadiness:
    def test_all_criteria_pass(self) -> None:
        rule = ReadinessRule(
            min_evidence_count=1,
            requires_valid_policy=True,
            max_open_critical_findings=0,
            max_open_high_findings=0,
            required_implementation_status=(ControlImplementationStatus.IMPLEMENTED),
        )
        inp = CheckInput(
            evidence_count=2,
            policy_count=1,
            open_critical_findings=0,
            open_high_findings=0,
            implementation_status=ControlImplementationStatus.IMPLEMENTED,
        )
        result, score = evaluate_control_readiness(rule, inp)
        assert result == CheckResult.PASS
        assert score == 1.0

    def test_no_evidence_fails(self) -> None:
        rule = ReadinessRule(min_evidence_count=1)
        inp = CheckInput(
            evidence_count=0,
            policy_count=1,
            open_critical_findings=0,
            open_high_findings=0,
            implementation_status=ControlImplementationStatus.IMPLEMENTED,
        )
        result, score = evaluate_control_readiness(rule, inp)
        assert result == CheckResult.FAIL
        assert score == 0.75

    def test_no_policy_fails_when_required(self) -> None:
        rule = ReadinessRule(requires_valid_policy=True)
        inp = CheckInput(
            evidence_count=1,
            policy_count=0,
            open_critical_findings=0,
            open_high_findings=0,
            implementation_status=ControlImplementationStatus.IMPLEMENTED,
        )
        result, score = evaluate_control_readiness(rule, inp)
        assert result == CheckResult.FAIL

    def test_policy_not_required_passes(self) -> None:
        rule = ReadinessRule(requires_valid_policy=False)
        inp = CheckInput(
            evidence_count=1,
            policy_count=0,
            open_critical_findings=0,
            open_high_findings=0,
            implementation_status=ControlImplementationStatus.IMPLEMENTED,
        )
        result, score = evaluate_control_readiness(rule, inp)
        assert result == CheckResult.PASS
        assert score == 1.0

    def test_too_many_critical_findings_fails(self) -> None:
        rule = ReadinessRule(max_open_critical_findings=0)
        inp = CheckInput(
            evidence_count=1,
            policy_count=1,
            open_critical_findings=1,
            open_high_findings=0,
            implementation_status=ControlImplementationStatus.IMPLEMENTED,
        )
        result, score = evaluate_control_readiness(rule, inp)
        assert result == CheckResult.FAIL

    def test_too_many_high_findings_fails(self) -> None:
        rule = ReadinessRule(max_open_high_findings=0)
        inp = CheckInput(
            evidence_count=1,
            policy_count=1,
            open_critical_findings=0,
            open_high_findings=1,
            implementation_status=ControlImplementationStatus.IMPLEMENTED,
        )
        result, score = evaluate_control_readiness(rule, inp)
        assert result == CheckResult.FAIL

    def test_implementation_not_started_fails(self) -> None:
        rule = ReadinessRule(
            required_implementation_status=(ControlImplementationStatus.IMPLEMENTED),
        )
        inp = CheckInput(
            evidence_count=1,
            policy_count=1,
            open_critical_findings=0,
            open_high_findings=0,
            implementation_status=ControlImplementationStatus.NOT_STARTED,
        )
        result, score = evaluate_control_readiness(rule, inp)
        assert result == CheckResult.FAIL
        assert score == 0.75

    def test_assessed_status_exceeds_implemented(self) -> None:
        rule = ReadinessRule(
            required_implementation_status=(ControlImplementationStatus.IMPLEMENTED),
        )
        inp = CheckInput(
            evidence_count=1,
            policy_count=1,
            open_critical_findings=0,
            open_high_findings=0,
            implementation_status=ControlImplementationStatus.ASSESSED,
        )
        result, score = evaluate_control_readiness(rule, inp)
        assert result == CheckResult.PASS

    def test_no_implementation_status_fails(self) -> None:
        rule = ReadinessRule()
        inp = CheckInput(
            evidence_count=1,
            policy_count=1,
            open_critical_findings=0,
            open_high_findings=0,
            implementation_status=None,
        )
        result, score = evaluate_control_readiness(rule, inp)
        assert result == CheckResult.FAIL

    def test_all_criteria_fail(self) -> None:
        rule = ReadinessRule(min_evidence_count=5)
        inp = CheckInput(
            evidence_count=0,
            policy_count=0,
            open_critical_findings=5,
            open_high_findings=5,
            implementation_status=None,
        )
        result, score = evaluate_control_readiness(rule, inp)
        assert result == CheckResult.FAIL
        assert score == 0.0

    def test_boundary_exactly_meets_threshold(self) -> None:
        rule = ReadinessRule(
            min_evidence_count=2,
            max_open_critical_findings=1,
            max_open_high_findings=2,
        )
        inp = CheckInput(
            evidence_count=2,
            policy_count=1,
            open_critical_findings=1,
            open_high_findings=2,
            implementation_status=ControlImplementationStatus.IMPLEMENTED,
        )
        result, score = evaluate_control_readiness(rule, inp)
        assert result == CheckResult.PASS


class TestComputeOverallScore:
    def test_all_pass(self) -> None:
        results = [
            (CheckResult.PASS, 1.0),
            (CheckResult.PASS, 1.0),
        ]
        assert compute_overall_score(results) == 100.0

    def test_all_fail(self) -> None:
        results = [
            (CheckResult.FAIL, 0.0),
            (CheckResult.FAIL, 0.0),
        ]
        assert compute_overall_score(results) == 0.0

    def test_mixed(self) -> None:
        results = [
            (CheckResult.PASS, 1.0),
            (CheckResult.FAIL, 0.5),
        ]
        assert compute_overall_score(results) == 75.0

    def test_not_applicable_excluded(self) -> None:
        results = [
            (CheckResult.PASS, 1.0),
            (CheckResult.NOT_APPLICABLE, 0.0),
        ]
        assert compute_overall_score(results) == 100.0

    def test_empty_results(self) -> None:
        assert compute_overall_score([]) == 0.0

    def test_all_not_applicable(self) -> None:
        results = [
            (CheckResult.NOT_APPLICABLE, 0.0),
            (CheckResult.NOT_APPLICABLE, 0.0),
        ]
        assert compute_overall_score(results) == 0.0

    def test_pending_scores_zero(self) -> None:
        results = [
            (CheckResult.PENDING, 0.0),
            (CheckResult.PASS, 1.0),
        ]
        assert compute_overall_score(results) == 50.0


class TestSnapshotInput:
    def test_serializable(self) -> None:
        inp = CheckInput(
            evidence_count=3,
            policy_count=1,
            open_critical_findings=0,
            open_high_findings=1,
            implementation_status=ControlImplementationStatus.IMPLEMENTED,
        )
        snap = snapshot_input(inp)
        assert snap["evidence_count"] == 3
        assert snap["implementation_status"] == "implemented"

    def test_none_status(self) -> None:
        inp = CheckInput(
            evidence_count=0,
            policy_count=0,
            open_critical_findings=0,
            open_high_findings=0,
            implementation_status=None,
        )
        snap = snapshot_input(inp)
        assert snap["implementation_status"] is None


class TestDeterminism:
    """Verify that identical inputs always produce identical outputs."""

    def test_same_input_same_output(self) -> None:
        rule = ReadinessRule()
        inp = CheckInput(
            evidence_count=2,
            policy_count=1,
            open_critical_findings=0,
            open_high_findings=0,
            implementation_status=ControlImplementationStatus.IMPLEMENTED,
        )
        results = [evaluate_control_readiness(rule, inp) for _ in range(100)]
        assert all(r == results[0] for r in results)
