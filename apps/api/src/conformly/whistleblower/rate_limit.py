"""Privacy-preserving, bounded rate limits for anonymous whistleblower endpoints."""

import hashlib
import threading
import time
from dataclasses import dataclass


class WhistleblowerRateLimitExceeded(Exception):
    """Raised when an anonymous operation exceeds its fixed-window allowance."""


@dataclass(slots=True)
class _Bucket:
    window: int
    count: int


class AnonymousWhistleblowerRateLimiter:
    """Limits by portal/case identifiers without retaining network identity data."""

    def __init__(self, *, max_buckets: int = 10_000) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()
        self._max_buckets = max_buckets

    def check(
        self,
        operation: str,
        resource_key: str,
        *,
        limit: int,
        window_seconds: int = 60,
        now: float | None = None,
    ) -> None:
        timestamp = time.monotonic() if now is None else now
        window = int(timestamp // window_seconds)
        key = hashlib.sha256(f"{operation}:{resource_key}".encode()).hexdigest()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or bucket.window != window:
                if len(self._buckets) >= self._max_buckets:
                    self._buckets = {
                        digest: item
                        for digest, item in self._buckets.items()
                        if item.window >= window - 1
                    }
                bucket = _Bucket(window=window, count=0)
                self._buckets[key] = bucket
            if bucket.count >= limit:
                raise WhistleblowerRateLimitExceeded("Anonymous request rate limit exceeded")
            bucket.count += 1


anonymous_whistleblower_rate_limiter = AnonymousWhistleblowerRateLimiter()
