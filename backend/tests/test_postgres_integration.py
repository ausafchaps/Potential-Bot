import uuid

import pytest
from app.db.session import engine
from app.main import app
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="PostgreSQL integration test requires a PostgreSQL database",
)


def test_postgres_supports_core_learning_flow() -> None:
    client = TestClient(app)
    unique_email = f"postgres-{uuid.uuid4()}@example.com"

    readiness_response = client.get("/ready")
    assert readiness_response.status_code == 200

    user_response = client.post(
        "/users",
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
