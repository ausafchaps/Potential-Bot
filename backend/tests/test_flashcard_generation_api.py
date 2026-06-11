import uuid
from collections.abc import Generator

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Flashcard, FlashcardCitation, FlashcardSet, FlashcardSetStatus
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


def test_create_flashcard_set_generates_fake_cards_with_citations() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(client, course_id, b"Binary search halves sorted arrays to find values.")

        response = client.post(
            f"/courses/{course_id}/flashcard-sets",
            json={"topic": "binary search", "card_count": 2, "difficulty": "medium"},
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["course_id"] == course_id
        assert payload["topic"] == "binary search"
        assert payload["title"] == "Binary Search Flashcards"
        assert payload["difficulty"] == "medium"
        assert payload["status"] == "generated"
        assert payload["provider"] == "fake"
        assert len(payload["cards"]) == 2
        assert payload["cards"][0]["position"] == 1
        assert "binary search" in payload["cards"][0]["front"].lower()
        assert "Binary search halves" in payload["cards"][0]["back"]
        assert len(payload["cards"][0]["citations"]) == 1
        assert "Binary search halves" in payload["cards"][0]["citations"][0]["text"]

        testing_session_local = client.testing_session_local  # type: ignore[attr-defined]
        verify_db = testing_session_local()
        flashcard_set_id = uuid.UUID(payload["id"])
        assert verify_db.scalar(select(FlashcardSet).where(FlashcardSet.id == flashcard_set_id))
        assert len(verify_db.scalars(select(Flashcard)).all()) == 2
        assert len(verify_db.scalars(select(FlashcardCitation)).all()) == 2
        verify_db.close()
    finally:
        app.dependency_overrides.clear()


def test_create_flashcard_set_returns_insufficient_evidence_when_no_chunks_match() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(client, course_id, b"Stacks are last-in first-out structures.")

        response = client.post(
            f"/courses/{course_id}/flashcard-sets",
            json={"topic": "photosynthesis", "card_count": 2},
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["status"] == "insufficient_evidence"
        assert payload["title"] is None
        assert payload["cards"] == []

        testing_session_local = client.testing_session_local  # type: ignore[attr-defined]
        verify_db = testing_session_local()
        flashcard_set = verify_db.scalar(
            select(FlashcardSet).where(FlashcardSet.id == uuid.UUID(payload["id"]))
        )
        assert flashcard_set is not None
        assert flashcard_set.status == FlashcardSetStatus.insufficient_evidence
        assert flashcard_set.prompt is None
        verify_db.close()
    finally:
        app.dependency_overrides.clear()


def test_list_course_flashcard_sets_returns_summaries() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(client, course_id, b"Binary search halves sorted arrays to find values.")
        create_response = client.post(
            f"/courses/{course_id}/flashcard-sets",
            json={"topic": "binary search", "card_count": 1},
        )

        response = client.get(f"/courses/{course_id}/flashcard-sets")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["id"] == create_response.json()["id"]
        assert payload[0]["card_count"] == 1
    finally:
        app.dependency_overrides.clear()


def test_get_flashcard_set_returns_detail() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(client, course_id, b"Binary search halves sorted arrays to find values.")
        create_response = client.post(
            f"/courses/{course_id}/flashcard-sets",
            json={"topic": "binary search", "card_count": 1},
        )
        flashcard_set_id = create_response.json()["id"]

        response = client.get(f"/flashcard-sets/{flashcard_set_id}")

        assert response.status_code == 200
        assert response.json()["id"] == flashcard_set_id
        assert len(response.json()["cards"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_create_flashcard_set_returns_404_for_missing_course() -> None:
    client = build_client()

    try:
        response = client.post(
            f"/courses/{uuid.uuid4()}/flashcard-sets",
            json={"topic": "binary search"},
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_list_course_flashcard_sets_returns_404_for_missing_course() -> None:
    client = build_client()

    try:
        response = client.get(f"/courses/{uuid.uuid4()}/flashcard-sets")

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_flashcard_set_returns_404_for_missing_set() -> None:
    client = build_client()

    try:
        response = client.get(f"/flashcard-sets/{uuid.uuid4()}")

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_create_flashcard_set_rejects_invalid_card_count() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        response = client.post(
            f"/courses/{course_id}/flashcard-sets",
            json={"topic": "binary search", "card_count": 0},
        )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
