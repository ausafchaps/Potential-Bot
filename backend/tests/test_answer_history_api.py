import uuid
from collections.abc import Generator
from datetime import UTC, datetime

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Question
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
    client = TestClient(app)
    client.testing_session_local = testing_session_local  # type: ignore[attr-defined]
    return client


def create_answer_with_feedback(client: TestClient) -> tuple[str, str, str]:
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
    answer_response = client.post(
        f"/courses/{course_id}/questions",
        json={"question": "What is binary search?"},
    )
    assert answer_response.status_code == 200
    payload = answer_response.json()
    feedback_response = client.post(
        f"/answers/{payload['answer_id']}/feedback",
        json={"rating": 5, "comment": "Helpful"},
    )
    assert feedback_response.status_code == 201
    return course_id, payload["question_id"], payload["answer_id"]


def test_list_course_questions_returns_newest_first() -> None:
    client = build_client()

    try:
        course_id, first_question_id, _ = create_answer_with_feedback(client)
        testing_session_local = client.testing_session_local  # type: ignore[attr-defined]
        db = testing_session_local()
        first_question = db.get(Question, uuid.UUID(first_question_id))
        assert first_question is not None
        first_question.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        db.commit()
        db.close()

        second_response = client.post(
            f"/courses/{course_id}/questions",
            json={"question": "What is binary search?"},
        )
        second_question_id = second_response.json()["question_id"]

        response = client.get(f"/courses/{course_id}/questions")

        assert response.status_code == 200
        payload = response.json()
        assert [question["id"] for question in payload] == [second_question_id, first_question_id]
        assert payload[0]["answer_count"] == 1
        assert payload[0]["text"] == "What is binary search?"
    finally:
        app.dependency_overrides.clear()


def test_get_question_detail_includes_answer_summaries() -> None:
    client = build_client()

    try:
        _, question_id, answer_id = create_answer_with_feedback(client)

        response = client.get(f"/questions/{question_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == question_id
        assert payload["text"] == "What is binary search?"
        assert len(payload["answers"]) == 1
        answer = payload["answers"][0]
        assert answer["id"] == answer_id
        assert answer["status"] == "answered"
        assert answer["provider"] == "fake"
        assert answer["citation_count"] == 1
        assert answer["feedback_count"] == 1
        assert answer["average_rating"] == 5.0
    finally:
        app.dependency_overrides.clear()


def test_get_answer_detail_includes_citations_and_feedback() -> None:
    client = build_client()

    try:
        _, _, answer_id = create_answer_with_feedback(client)

        response = client.get(f"/answers/{answer_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == answer_id
        assert payload["status"] == "answered"
        assert payload["answer"].startswith("Based on the provided study material")
        assert "Study material" in payload["prompt"]
        assert len(payload["citations"]) == 1
        assert payload["citations"][0]["document_filename"] == "notes.txt"
        assert len(payload["feedback"]) == 1
        assert payload["feedback"][0]["rating"] == 5
        assert payload["feedback"][0]["comment"] == "Helpful"
    finally:
        app.dependency_overrides.clear()


def test_list_answer_citations_and_feedback() -> None:
    client = build_client()

    try:
        _, _, answer_id = create_answer_with_feedback(client)

        citations_response = client.get(f"/answers/{answer_id}/citations")
        feedback_response = client.get(f"/answers/{answer_id}/feedback")

        assert citations_response.status_code == 200
        assert feedback_response.status_code == 200
        assert len(citations_response.json()) == 1
        assert citations_response.json()[0]["position"] == 1
        assert len(feedback_response.json()) == 1
        assert feedback_response.json()[0]["rating"] == 5
    finally:
        app.dependency_overrides.clear()


def test_history_endpoints_return_404_for_missing_resources() -> None:
    client = build_client()
    missing_id = uuid.uuid4()

    try:
        assert client.get(f"/courses/{missing_id}/questions").status_code == 404
        assert client.get(f"/questions/{missing_id}").status_code == 404
        assert client.get(f"/answers/{missing_id}").status_code == 404
        assert client.get(f"/answers/{missing_id}/citations").status_code == 404
        assert client.get(f"/answers/{missing_id}/feedback").status_code == 404
    finally:
        app.dependency_overrides.clear()
