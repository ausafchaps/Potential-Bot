import uuid
from collections.abc import Generator

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import QuizAttempt, QuizAttemptAnswer
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


def upload_text(client: TestClient, course_id: str, text: bytes) -> None:
    response = client.post(
        f"/courses/{course_id}/documents/text",
        files={"file": ("notes.txt", text, "text/plain")},
    )
    assert response.status_code == 201


def create_generated_quiz(client: TestClient, question_count: int = 2) -> dict:
    course_id = create_course(client)
    upload_text(client, course_id, b"Binary search halves sorted arrays to find values.")
    response = client.post(
        f"/courses/{course_id}/quizzes",
        json={"topic": "binary search", "question_count": question_count},
    )
    assert response.status_code == 201
    return response.json()


def build_attempt_payload(quiz: dict, *, make_second_answer_wrong: bool = False) -> dict:
    answers = []
    for index, question in enumerate(quiz["questions"]):
        correct_option = next(option for option in question["options"] if option["is_correct"])
        selected_option = correct_option
        if index == 1 and make_second_answer_wrong:
            selected_option = next(
                option for option in question["options"] if not option["is_correct"]
            )

        answers.append(
            {
                "question_id": question["id"],
                "selected_option_id": selected_option["id"],
            }
        )
    return {"answers": answers}


def test_submit_quiz_attempt_grades_all_correct_answers() -> None:
    client = build_client()

    try:
        quiz = create_generated_quiz(client, question_count=2)

        response = client.post(
            f"/quizzes/{quiz['id']}/attempts",
            json=build_attempt_payload(quiz),
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["quiz_id"] == quiz["id"]
        assert payload["correct_count"] == 2
        assert payload["question_count"] == 2
        assert payload["score_percent"] == 100.0
        assert len(payload["answers"]) == 2
        assert all(answer["is_correct"] for answer in payload["answers"])

        testing_session_local = client.testing_session_local  # type: ignore[attr-defined]
        verify_db = testing_session_local()
        assert verify_db.scalar(
            select(QuizAttempt).where(QuizAttempt.id == uuid.UUID(payload["id"]))
        )
        assert len(verify_db.scalars(select(QuizAttemptAnswer)).all()) == 2
        verify_db.close()
    finally:
        app.dependency_overrides.clear()


def test_submit_quiz_attempt_grades_incorrect_answers() -> None:
    client = build_client()

    try:
        quiz = create_generated_quiz(client, question_count=2)

        response = client.post(
            f"/quizzes/{quiz['id']}/attempts",
            json=build_attempt_payload(quiz, make_second_answer_wrong=True),
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["correct_count"] == 1
        assert payload["question_count"] == 2
        assert payload["score_percent"] == 50.0
        assert [answer["is_correct"] for answer in payload["answers"]] == [True, False]
        assert (
            payload["answers"][1]["correct_option_id"]
            != payload["answers"][1]["selected_option_id"]
        )
    finally:
        app.dependency_overrides.clear()


def test_list_quiz_attempts_returns_summaries() -> None:
    client = build_client()

    try:
        quiz = create_generated_quiz(client, question_count=1)
        create_response = client.post(
            f"/quizzes/{quiz['id']}/attempts",
            json=build_attempt_payload(quiz),
        )

        response = client.get(f"/quizzes/{quiz['id']}/attempts")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["id"] == create_response.json()["id"]
        assert payload[0]["score_percent"] == 100.0
    finally:
        app.dependency_overrides.clear()


def test_get_quiz_attempt_returns_detail() -> None:
    client = build_client()

    try:
        quiz = create_generated_quiz(client, question_count=1)
        create_response = client.post(
            f"/quizzes/{quiz['id']}/attempts",
            json=build_attempt_payload(quiz),
        )
        attempt_id = create_response.json()["id"]

        response = client.get(f"/quiz-attempts/{attempt_id}")

        assert response.status_code == 200
        assert response.json()["id"] == attempt_id
        assert len(response.json()["answers"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_submit_quiz_attempt_rejects_missing_question_answer() -> None:
    client = build_client()

    try:
        quiz = create_generated_quiz(client, question_count=2)
        response = client.post(
            f"/quizzes/{quiz['id']}/attempts",
            json={"answers": [build_attempt_payload(quiz)["answers"][0]]},
        )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_submit_quiz_attempt_rejects_duplicate_question_answer() -> None:
    client = build_client()

    try:
        quiz = create_generated_quiz(client, question_count=1)
        answer = build_attempt_payload(quiz)["answers"][0]
        response = client.post(
            f"/quizzes/{quiz['id']}/attempts",
            json={"answers": [answer, answer]},
        )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_submit_quiz_attempt_rejects_option_from_another_question() -> None:
    client = build_client()

    try:
        quiz = create_generated_quiz(client, question_count=2)
        answers = build_attempt_payload(quiz)["answers"]
        answers[0]["selected_option_id"] = quiz["questions"][1]["options"][0]["id"]

        response = client.post(f"/quizzes/{quiz['id']}/attempts", json={"answers": answers})

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_submit_quiz_attempt_returns_404_for_missing_quiz() -> None:
    client = build_client()

    try:
        response = client.post(
            f"/quizzes/{uuid.uuid4()}/attempts",
            json={
                "answers": [
                    {
                        "question_id": str(uuid.uuid4()),
                        "selected_option_id": str(uuid.uuid4()),
                    }
                ]
            },
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_submit_quiz_attempt_rejects_insufficient_evidence_quiz() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(client, course_id, b"Stacks are last-in first-out structures.")
        quiz_response = client.post(
            f"/courses/{course_id}/quizzes",
            json={"topic": "photosynthesis", "question_count": 1},
        )
        quiz_id = quiz_response.json()["id"]

        response = client.post(
            f"/quizzes/{quiz_id}/attempts",
            json={
                "answers": [
                    {
                        "question_id": str(uuid.uuid4()),
                        "selected_option_id": str(uuid.uuid4()),
                    }
                ]
            },
        )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_list_quiz_attempts_returns_404_for_missing_quiz() -> None:
    client = build_client()

    try:
        response = client.get(f"/quizzes/{uuid.uuid4()}/attempts")

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_quiz_attempt_returns_404_for_missing_attempt() -> None:
    client = build_client()

    try:
        response = client.get(f"/quiz-attempts/{uuid.uuid4()}")

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
