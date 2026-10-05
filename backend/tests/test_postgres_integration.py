import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.db.session import engine
from app.main import app
from app.models import AuthRateLimit
from app.services import auth_rate_limit as limiter
from app.services.auth_rate_limit import AttemptLimit, AuthRateLimited, consume_attempts
from auth_helpers import register_user
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="PostgreSQL integration test requires a PostgreSQL database",
)


def test_postgres_supports_core_learning_flow() -> None:
    client = TestClient(app)
    unique_email = f"postgres-{uuid.uuid4()}@example.com"

    readiness_response = client.get("/ready")
    assert readiness_response.status_code == 200

    user_response = register_user(client,
        json={"email": unique_email, "display_name": "PostgreSQL Student"},
    )
    assert user_response.status_code == 201

    course_response = client.post(
        f"/users/{user_response.json()['id']}/courses",
        json={"title": "PostgreSQL Integration"},
    )
    assert course_response.status_code == 201
    course_id = course_response.json()["id"]

    document_response = client.post(
        f"/courses/{course_id}/documents/text",
        files={
            "file": (
                "postgres-notes.txt",
                b"Binary search repeatedly halves a sorted search space.",
                "text/plain",
            )
        },
    )
    assert document_response.status_code == 201

    question_response = client.post(
        f"/courses/{course_id}/questions",
        json={"question": "What does binary search do?"},
    )
    assert question_response.status_code == 200
    assert question_response.json()["status"] == "answered"


def test_postgres_rate_limits_are_atomic_across_connections(monkeypatch) -> None:
    # Keep the workers in one window even if CI starts at a minute boundary.
    monkeypatch.setattr(limiter.time, "time", lambda: 120.0)
    identity = f"postgres-concurrency-{uuid.uuid4()}"
    policy = AttemptLimit("integration", identity, 5, 60)

    def attempt(_):
        with Session(engine) as db:
            try:
                consume_attempts(db, [policy])
                return True
            except AuthRateLimited as exc:
                assert 1 <= exc.retry_after <= 60
                return False

    try:
        with ThreadPoolExecutor(max_workers=8) as workers:
            assert sum(workers.map(attempt, range(20))) == 5
    finally:
        # This CI database contains only disposable integration test data.
        with Session(engine) as db:
            db.execute(delete(AuthRateLimit))
            db.commit()
