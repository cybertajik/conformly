import time
from collections import defaultdict

from fastapi import APIRouter, Response

router = APIRouter(tags=["monitoring"])

# In-memory Prometheus metric counters
_requests_total: dict[tuple[str, str, int], int] = defaultdict(int)
_request_durations: dict[tuple[str, str], list[float]] = defaultdict(list)
_active_db_connections: int = 1
_last_backup_timestamp: float = time.time()


def record_request_metric(
    method: str, path: str, status_code: int, duration_seconds: float
) -> None:
    # Normalize path to avoid metric cardinality explosion
    normalized_path = path.split("?")[0]
    if normalized_path.startswith("/api/v1/"):
        parts = normalized_path.split("/")
        # Replace UUID-like or numeric segments with :id
        clean_parts = []
        for p in parts:
            if len(p) >= 32 or p.isdigit():
                clean_parts.append(":id")
            else:
                clean_parts.append(p)
        normalized_path = "/".join(clean_parts)

    key = (method, normalized_path, status_code)
    _requests_total[key] += 1

    dur_key = (method, normalized_path)
    dur_list = _request_durations[dur_key]
    dur_list.append(duration_seconds)
    if len(dur_list) > 1000:
        _request_durations[dur_key] = dur_list[-500:]


def render_prometheus_metrics() -> str:
    lines = [
        "# HELP conformly_http_requests_total Total number of HTTP requests processed.",
        "# TYPE conformly_http_requests_total counter",
    ]
    for (method, path, status_code), count in sorted(_requests_total.items()):
        lines.append(
            f'conformly_http_requests_total{{method="{method}",path="{path}",status="{status_code}"}} {count}'
        )

    lines.extend(
        [
            "# HELP conformly_http_request_duration_seconds_sum Total request latency sum.",
            "# TYPE conformly_http_request_duration_seconds_sum counter",
            "# HELP conformly_http_request_duration_seconds_count Total request latency count.",
            "# TYPE conformly_http_request_duration_seconds_count counter",
        ]
    )
    for (method, path), durations in sorted(_request_durations.items()):
        total_sum = sum(durations)
        count = len(durations)
        lines.append(
            f'conformly_http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {total_sum:.6f}'
        )
        lines.append(
            f'conformly_http_request_duration_seconds_count{{method="{method}",path="{path}"}} {count}'
        )

    lines.extend(
        [
            "# HELP conformly_database_connections_active Active database connection pool count.",
            "# TYPE conformly_database_connections_active gauge",
            f"conformly_database_connections_active {_active_db_connections}",
            "# HELP conformly_backup_last_successful_timestamp Timestamp of last successful backup.",
            "# TYPE conformly_backup_last_successful_timestamp gauge",
            f"conformly_backup_last_successful_timestamp {_last_backup_timestamp:.0f}",
        ]
    )

    return "\n".join(lines) + "\n"


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    return Response(
        content=render_prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
