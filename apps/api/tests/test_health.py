from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conformly.db.session import get_db
from conformly.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "conformly-api"}
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]


def test_health_live() -> None:
    response = TestClient(app).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "conformly-api"}


def test_health_ready(session: Session) -> None:
    app.dependency_overrides[get_db] = lambda: session
    try:
        response = TestClient(app).get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert data["storage"] == "connected"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_preserves_caller_request_id() -> None:
    response = TestClient(app).get("/health", headers={"X-Request-ID": "test-request"})

    assert response.headers["X-Request-ID"] == "test-request"
    assert response.headers["X-Correlation-ID"] == "test-request"


def test_preserves_caller_correlation_id() -> None:
    response = TestClient(app).get("/health", headers={"X-Correlation-ID": "corr-12345"})

    assert response.headers["X-Correlation-ID"] == "corr-12345"
    assert response.headers["X-Request-ID"] == "corr-12345"


def test_prometheus_metrics_endpoint() -> None:
    client = TestClient(app)
    # Trigger a health check to produce metrics
    client.get("/health")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "conformly_http_requests_total" in response.text
    assert "conformly_database_connections_active" in response.text
    assert "conformly_backup_last_successful_timestamp" in response.text


def test_whistleblower_excluded_from_core_entry_points() -> None:
    client = TestClient(app)
    # With enable_whistleblower_addon=False (default), whistleblower endpoints must return 404
    response = client.get("/api/v1/whistleblower/cases")
    assert response.status_code == 404
    public_response = client.get("/api/v1/public/whistleblower/portal/test")
    assert public_response.status_code == 404
