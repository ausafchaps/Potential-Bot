import uuid
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


def create_course(client: TestClient) -> str:
    user_response = client.post(
        "/users",
        json={"email": "student@example.com", "display_name": "Student"},
    )
    course_response = client.post(
        f"/users/{user_response.json()['id']}/courses",
        json={"title": "Algorithms"},
    )
    return course_response.json()["id"]


def upload_text(client: TestClient, course_id: str) -> None:
    response = client.post(
        f"/courses/{course_id}/documents/text",
        files={
            "file": (
                "notes.txt",
                b"Binary search halves sorted arrays. Stacks are last-in first-out.",
                "text/plain",
            )
        },
    )
    assert response.status_code == 201


def create_generated_quiz(client: TestClient, course_id: str, topic: str) -> dict:
    response = client.post(
        f"/courses/{course_id}/quizzes",
        json={"topic": topic, "question_count": 2},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "generated"
    return payload


def build_attempt_payload(quiz: dict, *, correct_answers: int) -> dict:
    answers = []
    for index, question in enumerate(quiz["questions"]):
        correct_option = next(option for option in question["options"] if option["is_correct"])
        wrong_option = next(option for option in question["options"] if not option["is_correct"])
        selected_option = correct_option if index < correct_answers else wrong_option
        answers.append(
            {
                "question_id": question["id"],
                "selected_option_id": selected_option["id"],
            }
        )
    return {"answers": answers}


def submit_attempt(client: TestClient, quiz: dict, *, correct_answers: int) -> None:
    response = client.post(
        f"/quizzes/{quiz['id']}/attempts",
        json=build_attempt_payload(quiz, correct_answers=correct_answers),
    )
    assert response.status_code == 201


def test_weak_topics_empty_course_returns_no_topics() -> None:
    client = build_client()

    try:
        course_id = create_course(client)

        response = client.get(f"/courses/{course_id}/weak-topics")

        assert response.status_code == 200
        assert response.json() == {
            "course_id": course_id,
            "topic_count": 0,
            "attempt_count": 0,
            "question_count": 0,
            "weak_topics": [],
        }
    finally:
        app.dependency_overrides.clear()


def test_weak_topics_rank_attempted_topics_by_weakness() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(client, course_id)
        binary_search_quiz = create_generated_quiz(client, course_id, "binary search")
        stacks_quiz = create_generated_quiz(client, course_id, "stacks")

        submit_attempt(client, binary_search_quiz, correct_answers=0)
        submit_attempt(client, stacks_quiz, correct_answers=2)

        response = client.get(f"/courses/{course_id}/weak-topics")

        assert response.status_code == 200
        payload = response.json()
        assert payload["course_id"] == course_id
        assert payload["topic_count"] == 2
        assert payload["attempt_count"] == 2
        assert payload["question_count"] == 4
        assert [topic["topic"] for topic in payload["weak_topics"]] == [
            "binary search",
            "stacks",
        ]
        assert payload["weak_topics"][0] == {
            "topic": "binary search",
            "attempt_count": 1,
            "question_count": 2,
            "correct_count": 0,
            "incorrect_count": 2,
            "accuracy_rate": 0.0,
            "weakness_score": 1.0,
            "average_score_percent": 0.0,
            "last_attempted_at": payload["weak_topics"][0]["last_attempted_at"],
        }
        assert payload["weak_topics"][1]["accuracy_rate"] == 1.0
        assert payload["weak_topics"][1]["weakness_score"] == 0.0
    finally:
        app.dependency_overrides.clear()


def test_weak_topics_support_limit_and_min_attempts_filters() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(client, course_id)
        binary_search_quiz = create_generated_quiz(client, course_id, "binary search")
        stacks_quiz = create_generated_quiz(client, course_id, "stacks")

        submit_attempt(client, binary_search_quiz, correct_answers=0)
        submit_attempt(client, binary_search_quiz, correct_answers=1)
        submit_attempt(client, stacks_quiz, correct_answers=0)

        response = client.get(f"/courses/{course_id}/weak-topics?limit=1&min_attempts=2")

        assert response.status_code == 200
        payload = response.json()
        assert payload["topic_count"] == 2
        assert payload["attempt_count"] == 3
        assert len(payload["weak_topics"]) == 1
        assert payload["weak_topics"][0]["topic"] == "binary search"
        assert payload["weak_topics"][0]["attempt_count"] == 2
        assert payload["weak_topics"][0]["correct_count"] == 1
        assert payload["weak_topics"][0]["question_count"] == 4
        assert payload["weak_topics"][0]["accuracy_rate"] == 0.25
        assert payload["weak_topics"][0]["weakness_score"] == 0.75
        assert payload["weak_topics"][0]["average_score_percent"] == 25.0
    finally:
        app.dependency_overrides.clear()


def test_weak_topics_returns_404_for_missing_course() -> None:
    client = build_client()

    try:
        response = client.get(f"/courses/{uuid.uuid4()}/weak-topics")

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
