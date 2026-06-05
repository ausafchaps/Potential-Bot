import uuid
from collections.abc import Generator

import pytest
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.hybrid_retrieval import (
    search_course_chunks_by_hybrid,
    validate_hybrid_weights,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


class ZeroEmbeddingProvider:
    provider_name = "zero"
    model_name = "zero-v1"
    dimensions = 3

    def embed_text(self, _text: str) -> list[float]:
        return [0.0, 0.0, 0.0]


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


def create_course(client: TestClient, email: str = "student@example.com") -> str:
    user_response = client.post(
        "/users",
        json={"email": email, "display_name": "Student"},
    )
    course_response = client.post(
        f"/users/{user_response.json()['id']}/courses",
        json={"title": "Algorithms"},
    )
    return course_response.json()["id"]


def upload_text(client: TestClient, course_id: str, filename: str, text: bytes) -> None:
    response = client.post(
        f"/courses/{course_id}/documents/text",
        files={"file": (filename, text, "text/plain")},
    )
    assert response.status_code == 201


def test_validate_hybrid_weights_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="zero or greater"):
        validate_hybrid_weights(keyword_weight=-0.1, vector_weight=1.0)

    with pytest.raises(ValueError, match="At least one"):
        validate_hybrid_weights(keyword_weight=0.0, vector_weight=0.0)


def test_hybrid_search_merges_keyword_and_vector_matches() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(
            client,
            course_id,
            "binary-search.txt",
            b"Binary search quickly finds values in a sorted array.",
        )

        testing_session_local = client.testing_session_local  # type: ignore[attr-defined]
        db = testing_session_local()
        results = search_course_chunks_by_hybrid(
            db,
            course_id=uuid.UUID(course_id),
            query="binary search",
        )

        assert len(results) == 1
        assert results[0].document_filename == "binary-search.txt"
        assert results[0].keyword_score > 0
        assert results[0].vector_similarity > 0
        assert results[0].retrieval_sources == ["keyword", "vector"]
        db.close()
    finally:
        app.dependency_overrides.clear()


def test_hybrid_search_keeps_keyword_only_matches() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(
            client,
            course_id,
            "recursion.txt",
            b"Recursion uses a base case to stop repeated calls.",
        )

        testing_session_local = client.testing_session_local  # type: ignore[attr-defined]
        db = testing_session_local()
        results = search_course_chunks_by_hybrid(
            db,
            course_id=uuid.UUID(course_id),
            query="recursion",
            embedding_provider=ZeroEmbeddingProvider(),
        )

        assert len(results) == 1
        assert results[0].document_filename == "recursion.txt"
        assert results[0].keyword_score > 0
        assert results[0].vector_similarity == 0
        assert results[0].retrieval_sources == ["keyword"]
        db.close()
    finally:
        app.dependency_overrides.clear()


def test_hybrid_search_keeps_vector_only_semantic_matches() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(
            client,
            course_id,
            "binary-search.txt",
            b"Binary search quickly finds values in a sorted array.",
        )

        testing_session_local = client.testing_session_local  # type: ignore[attr-defined]
        db = testing_session_local()
        results = search_course_chunks_by_hybrid(
            db,
            course_id=uuid.UUID(course_id),
            query="rapid retrieval ordered list",
        )

        assert len(results) == 1
        assert results[0].document_filename == "binary-search.txt"
        assert results[0].keyword_score == 0
        assert results[0].vector_similarity > 0
        assert results[0].retrieval_sources == ["vector"]
        db.close()
    finally:
        app.dependency_overrides.clear()


def test_hybrid_search_combined_score_ranks_shared_match_first() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(
            client,
            course_id,
            "binary-search.txt",
            b"Binary search quickly finds values in a sorted array.",
        )
        upload_text(
            client,
            course_id,
            "hash-table.txt",
            b"Hash tables provide lookup by mapping keys to array locations.",
        )

        testing_session_local = client.testing_session_local  # type: ignore[attr-defined]
        db = testing_session_local()
        results = search_course_chunks_by_hybrid(
            db,
            course_id=uuid.UUID(course_id),
            query="search sorted array",
            limit=2,
        )

        assert len(results) == 2
        assert results[0].document_filename == "binary-search.txt"
        assert results[0].retrieval_sources == ["keyword", "vector"]
        assert results[0].hybrid_score > results[1].hybrid_score
        db.close()
    finally:
        app.dependency_overrides.clear()


def test_hybrid_search_only_returns_chunks_from_requested_course() -> None:
    client = build_client()

    try:
        algorithms_course_id = create_course(client, "algo@example.com")
        biology_course_id = create_course(client, "bio@example.com")
        upload_text(
            client,
            algorithms_course_id,
            "algorithms.txt",
            b"Binary search quickly finds values in a sorted array.",
        )
        upload_text(
            client,
            biology_course_id,
            "biology.txt",
            b"Binary fission is a biological reproduction process.",
        )

        testing_session_local = client.testing_session_local  # type: ignore[attr-defined]
        db = testing_session_local()
        results = search_course_chunks_by_hybrid(
            db,
            course_id=uuid.UUID(algorithms_course_id),
            query="rapid retrieval ordered list",
        )

        assert len(results) == 1
        assert results[0].document_filename == "algorithms.txt"
        db.close()
    finally:
        app.dependency_overrides.clear()


def test_hybrid_search_endpoint_returns_explainable_results() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(
            client,
            course_id,
            "binary-search.txt",
            b"Binary search quickly finds values in a sorted array.",
        )

        response = client.get(
            f"/courses/{course_id}/search/hybrid",
            params={"query": "binary search"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["course_id"] == course_id
        assert payload["query"] == "binary search"
        assert len(payload["results"]) == 1
        result = payload["results"][0]
        assert result["document_filename"] == "binary-search.txt"
        assert result["hybrid_score"] > 0
        assert result["keyword_score"] > 0
        assert result["vector_similarity"] > 0
        assert result["retrieval_sources"] == ["keyword", "vector"]
    finally:
        app.dependency_overrides.clear()


def test_hybrid_search_endpoint_limit_controls_result_count() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(client, course_id, "a.txt", b"Graph search explores nodes.")
        upload_text(client, course_id, "b.txt", b"Tree search explores branches.")

        response = client.get(
            f"/courses/{course_id}/search/hybrid",
            params={"query": "search", "limit": 1},
        )

        assert response.status_code == 200
        assert len(response.json()["results"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_hybrid_search_endpoint_returns_404_for_missing_course() -> None:
    client = build_client()

    try:
        response = client.get(
            f"/courses/{uuid.uuid4()}/search/hybrid",
            params={"query": "binary search"},
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_hybrid_search_endpoint_rejects_empty_query_terms() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        response = client.get(
            f"/courses/{course_id}/search/hybrid",
            params={"query": "   "},
        )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
