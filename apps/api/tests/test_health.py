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
