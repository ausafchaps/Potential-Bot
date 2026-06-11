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


def test_study_recommendations_empty_course_returns_no_recommendations() -> None:
    client = build_client()

    try:
        course_id = create_course(client)

        response = client.get(f"/courses/{course_id}/study-recommendations")

        assert response.status_code == 200
        assert response.json() == {
            "course_id": course_id,
            "source_topic_count": 0,
            "recommendation_count": 0,
            "recommendations": [],
        }
    finally:
        app.dependency_overrides.clear()


def test_study_recommendations_prioritize_weak_topics() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(client, course_id)
        binary_search_quiz = create_generated_quiz(client, course_id, "binary search")
        stacks_quiz = create_generated_quiz(client, course_id, "stacks")

        submit_attempt(client, binary_search_quiz, correct_answers=0)
        submit_attempt(client, stacks_quiz, correct_answers=2)

        response = client.get(f"/courses/{course_id}/study-recommendations")

        assert response.status_code == 200
        payload = response.json()
        assert payload["course_id"] == course_id
        assert payload["source_topic_count"] == 2
        assert payload["recommendation_count"] == 1
        assert len(payload["recommendations"]) == 1

        recommendation = payload["recommendations"][0]
        assert recommendation["topic"] == "binary search"
        assert recommendation["priority"] == "high"
        assert recommendation["reason"] == "Accuracy is 0% across 2 attempted questions."
        assert recommendation["attempt_count"] == 1
        assert recommendation["question_count"] == 2
        assert recommendation["incorrect_count"] == 2
        assert recommendation["accuracy_rate"] == 0.0
        assert recommendation["weakness_score"] == 1.0
        assert [action["type"] for action in recommendation["recommended_actions"]] == [
            "review_topic",
            "practice_missed_questions",
            "generate_quiz",
        ]
        assert recommendation["recommended_actions"][0]["prompt"] == (
            "Explain binary search using my course notes and cite the sources."
        )
        assert recommendation["recommended_actions"][2]["quiz_topic"] == "binary search"
    finally:
        app.dependency_overrides.clear()


def test_study_recommendations_support_filters_and_include_mastered() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(client, course_id)
        binary_search_quiz = create_generated_quiz(client, course_id, "binary search")
        stacks_quiz = create_generated_quiz(client, course_id, "stacks")

        submit_attempt(client, binary_search_quiz, correct_answers=0)
        submit_attempt(client, binary_search_quiz, correct_answers=2)
        submit_attempt(client, stacks_quiz, correct_answers=2)

        filtered_response = client.get(
            f"/courses/{course_id}/study-recommendations?limit=1&min_attempts=2"
        )
        include_mastered_response = client.get(
            f"/courses/{course_id}/study-recommendations?include_mastered=true"
        )

        assert filtered_response.status_code == 200
        filtered_payload = filtered_response.json()
        assert filtered_payload["recommendation_count"] == 1
        assert filtered_payload["recommendations"][0]["topic"] == "binary search"
        assert filtered_payload["recommendations"][0]["priority"] == "medium"
        assert filtered_payload["recommendations"][0]["accuracy_rate"] == 0.5
        assert filtered_payload["recommendations"][0]["weakness_score"] == 0.5

        assert include_mastered_response.status_code == 200
        mastered_recommendation = include_mastered_response.json()["recommendations"][1]
        assert mastered_recommendation["topic"] == "stacks"
        assert mastered_recommendation["priority"] == "mastered"
        assert mastered_recommendation["recommended_actions"] == [
            {
                "type": "maintain_topic",
                "label": "Keep stacks warm",
                "description": "Review this topic later to maintain retention.",
                "prompt": None,
                "quiz_topic": "stacks",
            }
        ]
    finally:
        app.dependency_overrides.clear()


def test_study_recommendations_return_404_for_missing_course() -> None:
    client = build_client()

    try:
        response = client.get(f"/courses/{uuid.uuid4()}/study-recommendations")

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
