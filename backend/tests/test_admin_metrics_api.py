from collections.abc import Generator

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def build_client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def create_populated_metrics_fixture(client: TestClient) -> None:
    user_response = client.post(
        "/users",
        json={"email": "student@example.com", "display_name": "Student"},
    )
    course_response = client.post(
        f"/users/{user_response.json()['id']}/courses",
        json={"title": "Algorithms"},
    )
    course_id = course_response.json()["id"]
    upload_response = client.post(
        f"/courses/{course_id}/documents/text",
        files={
            "file": (
                "notes.txt",
                b"Binary search halves sorted arrays.",
                "text/plain",
            )
        },
    )
    assert upload_response.status_code == 201

    answered_response = client.post(
        f"/courses/{course_id}/questions",
        json={"question": "What is binary search?"},
    )
    insufficient_response = client.post(
        f"/courses/{course_id}/questions",
        json={"question": "What is photosynthesis?"},
    )

    assert answered_response.status_code == 200
    assert insufficient_response.status_code == 200

    answer_id = answered_response.json()["answer_id"]
    assert client.post(
        f"/answers/{answer_id}/feedback",
        json={"rating": 5, "comment": "Helpful"},
    ).status_code == 201
    assert client.post(
        f"/answers/{answer_id}/feedback",
        json={"rating": 3},
    ).status_code == 201


def test_admin_metrics_empty_database() -> None:
    client = build_client()

    try:
        response = client.get("/admin/metrics")

        assert response.status_code == 200
        assert response.json() == {
            "usage": {
                "users": 0,
                "courses": 0,
                "documents": 0,
                "document_chunks": 0,
                "questions": 0,
                "answers": 0,
                "citations": 0,
                "feedback_events": 0,
            },
            "documents": {
                "documents_by_status": {
                    "pending": 0,
                    "processing": 0,
                    "completed": 0,
                    "failed": 0,
                },
                "documents_by_content_type": {},
                "average_chunks_per_document": 0.0,
            },
            "answers": {
                "answers_by_status": {
                    "answered": 0,
                    "insufficient_evidence": 0,
                },
                "citation_coverage_rate": 0.0,
            },
            "feedback": {
                "average_feedback_rating": None,
                "feedback_rating_distribution": {
                    "1": 0,
                    "2": 0,
                    "3": 0,
                    "4": 0,
                    "5": 0,
                },
            },
        }
    finally:
        app.dependency_overrides.clear()


def test_admin_metrics_populated_database() -> None:
    client = build_client()

    try:
        create_populated_metrics_fixture(client)

        response = client.get("/admin/metrics")

        assert response.status_code == 200
        payload = response.json()
        assert payload["usage"] == {
            "users": 1,
            "courses": 1,
            "documents": 1,
            "document_chunks": 1,
            "questions": 2,
            "answers": 2,
            "citations": 1,
            "feedback_events": 2,
        }
        assert payload["documents"]["documents_by_status"]["completed"] == 1
        assert payload["documents"]["documents_by_content_type"] == {"text/plain": 1}
        assert payload["documents"]["average_chunks_per_document"] == 1.0
        assert payload["answers"]["answers_by_status"] == {
            "answered": 1,
            "insufficient_evidence": 1,
        }
        assert payload["answers"]["citation_coverage_rate"] == 0.5
        assert payload["feedback"]["average_feedback_rating"] == 4.0
        assert payload["feedback"]["feedback_rating_distribution"] == {
            "1": 0,
            "2": 0,
            "3": 1,
            "4": 0,
            "5": 1,
        }
    finally:
        app.dependency_overrides.clear()

