from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError


def test_health_check() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "StudyBot",
        "environment": "test",
    }


def test_cors_allows_local_frontend_demo() -> None:
    client = TestClient(app)

    response = client.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_readiness_check_reports_available_database() -> None:
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "available",
    }


def test_readiness_check_returns_503_for_database_failure(monkeypatch) -> None:
    client = TestClient(app)

    def raise_database_error() -> None:
        raise SQLAlchemyError("connection failed")

    monkeypatch.setattr(
        "app.api.routes.health.check_database_connection",
        raise_database_error,
    )

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}
