import logging
from typing import Any, cast

import structlog
from structlog.typing import EventDict, WrappedLogger

SENSITIVE_LOG_KEY_PARTS = frozenset(
    {
        "authorization",
        "ciphertext",
        "cookie",
        "credential",
        "dek",
        "key",
        "password",
        "plaintext",
        "secret",
        "token",
    }
)


def redact_sensitive_fields(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    def redact(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: (
                    "[REDACTED]"
                    if any(part in str(key).casefold() for part in SENSITIVE_LOG_KEY_PARTS)
                    else redact(nested)
                )
                for key, nested in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [redact(item) for item in value]
        return value

    return cast(EventDict, redact(event_dict))


def configure_logging(level: str) -> None:
    """Configure JSON logs suitable for correlation-aware request logging."""

    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=log_level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            redact_sensitive_fields,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )
