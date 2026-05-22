from collections.abc import Generator

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import DocumentChunk
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


def create_user_course_and_document(client: TestClient) -> tuple[str, str]:
    user_response = client.post(
        "/users",
        json={"email": "student@example.com", "display_name": "Student"},
    )
    course_response = client.post(
        f"/users/{user_response.json()['id']}/courses",
        json={"title": "Algorithms"},
    )
    course_id = course_response.json()["id"]
    document_response = client.post(
        f"/courses/{course_id}/documents/text",
        files={
            "file": (
                "notes.txt",
                b"Binary search halves sorted arrays.",
                "text/plain",
            )
        },
    )
    return course_id, document_response.json()["id"]


def test_list_course_documents_returns_document_summaries() -> None:
    client = build_client()

    try:
        course_id, document_id = create_user_course_and_document(client)

        response = client.get(f"/courses/{course_id}/documents")

        assert response.status_code == 200
        documents = response.json()
        assert len(documents) == 1
        assert documents[0]["id"] == document_id
        assert documents[0]["course_id"] == course_id
        assert documents[0]["filename"] == "notes.txt"
        assert documents[0]["content_type"] == "text/plain"
        assert documents[0]["status"] == "completed"
        assert documents[0]["page_count"] is None
        assert documents[0]["chunk_count"] == 1
        assert documents[0]["created_at"]
        assert documents[0]["updated_at"]
    finally:
        app.dependency_overrides.clear()


def test_get_document_returns_summary() -> None:
    client = build_client()

    try:
        course_id, document_id = create_user_course_and_document(client)

        response = client.get(f"/documents/{document_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == document_id
        assert payload["course_id"] == course_id
        assert payload["filename"] == "notes.txt"
        assert payload["chunk_count"] == 1
    finally:
        app.dependency_overrides.clear()


def test_list_document_chunks_returns_ordered_chunks() -> None:
    client = build_client()

    try:
        _, document_id = create_user_course_and_document(client)

        response = client.get(f"/documents/{document_id}/chunks")

        assert response.status_code == 200
        chunks = response.json()
        assert len(chunks) == 1
        assert chunks[0]["document_id"] == document_id
        assert chunks[0]["chunk_index"] == 0
        assert "Binary search" in chunks[0]["text"]
    finally:
        app.dependency_overrides.clear()


def test_delete_document_removes_document_chunks_and_search_results() -> None:
    client = build_client()

    try:
        course_id, document_id = create_user_course_and_document(client)

        delete_response = client.delete(f"/documents/{document_id}")

        assert delete_response.status_code == 204
        assert client.get(f"/documents/{document_id}").status_code == 404
        assert client.get(f"/documents/{document_id}/chunks").status_code == 404

        search_response = client.get(f"/courses/{course_id}/search", params={"query": "binary"})
        assert search_response.status_code == 200
        assert search_response.json()["results"] == []

        testing_session_local = client.testing_session_local  # type: ignore[attr-defined]
        verify_db = testing_session_local()
        assert verify_db.scalars(select(DocumentChunk)).all() == []
        verify_db.close()
    finally:
        app.dependency_overrides.clear()


def test_document_management_returns_404_for_missing_resources() -> None:
    client = build_client()
    missing_course_url = "/courses/00000000-0000-0000-0000-000000000000/documents"
    missing_document_url = "/documents/00000000-0000-0000-0000-000000000000"
    missing_chunks_url = "/documents/00000000-0000-0000-0000-000000000000/chunks"

    try:
        assert client.get(missing_course_url).status_code == 404
        assert client.get(missing_document_url).status_code == 404
        assert client.get(missing_chunks_url).status_code == 404
        assert client.delete(missing_document_url).status_code == 404
    finally:
        app.dependency_overrides.clear()
