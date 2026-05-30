import uuid
from collections.abc import Generator

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import AnswerFeedback
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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


def create_answer(client: TestClient) -> str:
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
    return answer_response.json()["answer_id"]


def test_create_answer_feedback() -> None:
    client = build_client()

    try:
        answer_id = create_answer(client)

        response = client.post(
            f"/answers/{answer_id}/feedback",
            json={"rating": 5, "comment": " Very helpful "},
        )

        assert response.status_code == 201
        payload = response.json()
        assert uuid.UUID(payload["id"])
        assert payload["answer_id"] == answer_id
        assert payload["rating"] == 5
        assert payload["comment"] == "Very helpful"
        assert payload["created_at"]

        testing_session_local = client.testing_session_local  # type: ignore[attr-defined]
        verify_db = testing_session_local()
        feedback = verify_db.scalar(select(AnswerFeedback))

        assert feedback is not None
        assert feedback.rating == 5
        assert feedback.comment == "Very helpful"
        verify_db.close()
    finally:
        app.dependency_overrides.clear()


def test_create_answer_feedback_allows_empty_comment() -> None:
    client = build_client()

    try:
        answer_id = create_answer(client)

        response = client.post(
            f"/answers/{answer_id}/feedback",
            json={"rating": 4, "comment": "   "},
        )

        assert response.status_code == 201
        assert response.json()["comment"] is None
    finally:
        app.dependency_overrides.clear()


def test_create_answer_feedback_returns_404_for_missing_answer() -> None:
    client = build_client()

    try:
        response = client.post(
            f"/answers/{uuid.uuid4()}/feedback",
            json={"rating": 3},
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_create_answer_feedback_validates_rating_range() -> None:
    client = build_client()

    try:
        answer_id = create_answer(client)

        low_response = client.post(f"/answers/{answer_id}/feedback", json={"rating": 0})
        high_response = client.post(f"/answers/{answer_id}/feedback", json={"rating": 6})

        assert low_response.status_code == 422
        assert high_response.status_code == 422
    finally:
        app.dependency_overrides.clear()

