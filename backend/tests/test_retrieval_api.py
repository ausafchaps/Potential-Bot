import uuid
from collections.abc import Generator

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.retrieval import score_text, tokenize_query
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


def create_course(client: TestClient, email: str, title: str) -> str:
    user_response = client.post("/users", json={"email": email, "display_name": "Student"})
    course_response = client.post(
        f"/users/{user_response.json()['id']}/courses",
        json={"title": title},
    )
    return course_response.json()["id"]


def upload_text(client: TestClient, course_id: str, filename: str, content: bytes) -> None:
    response = client.post(
        f"/courses/{course_id}/documents/text",
        files={"file": (filename, content, "text/plain")},
    )
    assert response.status_code == 201


def test_tokenize_query_normalizes_and_deduplicates_terms() -> None:
    assert tokenize_query(" Binary, search; BINARY! ") == ["binary", "search"]


def test_score_text_counts_matched_terms() -> None:
    score, matched_terms = score_text("Binary search uses binary decisions.", ["binary", "tree"])

    assert score == 2
    assert matched_terms == ["binary"]


def test_search_returns_ranked_chunks_for_course() -> None:
    client = build_client()

    try:
        course_id = create_course(client, "student@example.com", "Algorithms")
        upload_text(
            client,
            course_id,
            "binary-search.txt",
            b"Binary search is a search algorithm. Binary search halves sorted arrays.",
        )
        upload_text(
            client,
            course_id,
            "linear-search.txt",
            b"Linear search checks each element in sequence.",
        )

        response = client.get(f"/courses/{course_id}/search", params={"query": "binary search"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["course_id"] == course_id
        assert payload["query"] == "binary search"
        assert len(payload["results"]) == 2
        assert payload["results"][0]["document_filename"] == "binary-search.txt"
        assert payload["results"][0]["score"] > payload["results"][1]["score"]
        assert payload["results"][0]["matched_terms"] == ["binary", "search"]
    finally:
        app.dependency_overrides.clear()


def test_search_only_returns_chunks_from_requested_course() -> None:
    client = build_client()

    try:
        algorithms_course_id = create_course(client, "algo@example.com", "Algorithms")
        biology_course_id = create_course(client, "bio@example.com", "Biology")
        upload_text(
            client,
            algorithms_course_id,
            "algorithms.txt",
            b"Binary search halves sorted arrays.",
        )
        upload_text(
            client,
            biology_course_id,
            "biology.txt",
            b"Binary fission is a biological reproduction process.",
        )

        response = client.get(
            f"/courses/{algorithms_course_id}/search",
            params={"query": "binary"},
        )

        assert response.status_code == 200
        assert len(response.json()["results"]) == 1
        assert response.json()["results"][0]["document_filename"] == "algorithms.txt"
    finally:
        app.dependency_overrides.clear()


def test_search_limit_controls_result_count() -> None:
    client = build_client()

    try:
        course_id = create_course(client, "student@example.com", "Algorithms")
        upload_text(client, course_id, "a.txt", b"graph search")
        upload_text(client, course_id, "b.txt", b"tree search")

        response = client.get(
            f"/courses/{course_id}/search",
            params={"query": "search", "limit": 1},
        )

        assert response.status_code == 200
        assert len(response.json()["results"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_search_returns_empty_list_when_no_chunks_match() -> None:
    client = build_client()

    try:
        course_id = create_course(client, "student@example.com", "Algorithms")
        upload_text(client, course_id, "notes.txt", b"Stacks are last-in first-out structures.")

        response = client.get(
            f"/courses/{course_id}/search",
            params={"query": "queue"},
        )

        assert response.status_code == 200
        assert response.json()["results"] == []
    finally:
        app.dependency_overrides.clear()


def test_search_returns_404_for_missing_course() -> None:
    client = build_client()

    try:
        response = client.get(
            f"/courses/{uuid.uuid4()}/search",
            params={"query": "binary"},
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_search_rejects_empty_query_terms() -> None:
    client = build_client()

    try:
        course_id = create_course(client, "student@example.com", "Algorithms")
        response = client.get(f"/courses/{course_id}/search", params={"query": "   "})

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()

