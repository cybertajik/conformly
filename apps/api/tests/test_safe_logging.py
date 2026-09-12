import pytest
import structlog

from conformly.logging import configure_logging


def test_sensitive_structured_log_fields_are_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    structlog.get_logger().info(
        "security_test",
        access_token="bearer-secret-value",
        nested={"plaintext": "restricted-report-content", "safe_count": 2},
    )

    output = capsys.readouterr().out
    assert "bearer-secret-value" not in output
    assert "restricted-report-content" not in output
    assert output.count("[REDACTED]") == 2
    assert "safe_count" in output
