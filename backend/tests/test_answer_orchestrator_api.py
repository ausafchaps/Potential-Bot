import uuid
from collections.abc import Generator

import pytest
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Answer, AnswerStatus, Citation, Question
from app.services.embeddings.base import (
    EmbeddingProviderConfigurationError,
    EmbeddingProviderError,
)
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


def test_question_endpoint_returns_fake_grounded_answer_with_citations() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(client, course_id, b"Binary search halves sorted arrays.")

        response = client.post(
            f"/courses/{course_id}/questions",
            json={"question": "What is binary search?", "limit": 3},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "answered"
        assert uuid.UUID(payload["question_id"])
        assert uuid.UUID(payload["answer_id"])
        assert payload["provider"] == "fake"
        assert payload["answer"] == (
            "Based on the provided study material: Binary search halves sorted arrays. [1]"
        )
        assert len(payload["citations"]) == 1
        assert payload["citations"][0]["position"] == 1
        assert payload["citations"][0]["document_filename"] == "notes.txt"
        assert payload["citations"][0]["chunk_index"] == 0
        assert "Binary search" in payload["citations"][0]["text"]
        assert len(payload["retrieved_chunks"]) == 1

        testing_session_local = client.testing_session_local  # type: ignore[attr-defined]
        verify_db = testing_session_local()
        question_id = uuid.UUID(payload["question_id"])
        answer_id = uuid.UUID(payload["answer_id"])
        assert verify_db.scalar(select(Question).where(Question.id == question_id))
        answer = verify_db.scalar(select(Answer).where(Answer.id == answer_id))
        citations = verify_db.scalars(select(Citation)).all()

        assert answer is not None
        assert answer.status == AnswerStatus.answered
        assert answer.prompt is not None
        assert "Study material" in answer.prompt
        assert len(citations) == 1
        verify_db.close()
    finally:
        app.dependency_overrides.clear()


def test_question_endpoint_uses_hybrid_retrieval_for_semantic_matches() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(
            client,
            course_id,
            b"Binary search quickly finds values in a sorted array.",
        )

        response = client.post(
            f"/courses/{course_id}/questions",
            json={
                "question": "What method supports rapid retrieval from an ordered list?",
                "limit": 3,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "answered"
        assert payload["answer"] == (
            "Based on the provided study material: "
            "Binary search quickly finds values in a sorted array. [1]"
        )
        assert len(payload["citations"]) == 1
        assert "Binary search quickly" in payload["citations"][0]["text"]
        assert len(payload["retrieved_chunks"]) == 1
        assert payload["retrieved_chunks"][0]["score"] > 0
    finally:
        app.dependency_overrides.clear()


def test_question_endpoint_returns_insufficient_evidence_without_citations() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(client, course_id, b"Stacks are last-in first-out structures.")

        response = client.post(
            f"/courses/{course_id}/questions",
            json={"question": "What is photosynthesis?"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "insufficient_evidence"
        assert payload["answer"] is None
        assert payload["provider"] == "fake"
        assert payload["citations"] == []
        assert payload["retrieved_chunks"] == []

        testing_session_local = client.testing_session_local  # type: ignore[attr-defined]
        verify_db = testing_session_local()
        answer_id = uuid.UUID(payload["answer_id"])
        answer = verify_db.scalar(select(Answer).where(Answer.id == answer_id))

        assert answer is not None
        assert answer.status == AnswerStatus.insufficient_evidence
        assert answer.prompt is None
        verify_db.close()
    finally:
        app.dependency_overrides.clear()


def test_question_endpoint_returns_404_for_missing_course() -> None:
    client = build_client()

    try:
        response = client.post(
            f"/courses/{uuid.uuid4()}/questions",
            json={"question": "What is binary search?"},
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (
            EmbeddingProviderConfigurationError("Embedding provider is not configured"),
            503,
        ),
        (
            EmbeddingProviderError("OpenAI embedding provider request failed"),
            502,
        ),
    ],
)
def test_question_endpoint_returns_embedding_errors(monkeypatch, error, expected_status) -> None:
    client = build_client()

    def raise_embedding_error(*_args, **_kwargs):
        raise error

    try:
        course_id = create_course(client)
        monkeypatch.setattr(
            "app.api.routes.questions.answer_course_question",
            raise_embedding_error,
        )

        response = client.post(
            f"/courses/{course_id}/questions",
            json={"question": "What is volatility?"},
        )

        assert response.status_code == expected_status
        assert response.json()["detail"] == str(error)
    finally:
        app.dependency_overrides.clear()
