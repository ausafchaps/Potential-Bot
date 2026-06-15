import uuid
from collections.abc import Generator

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import DocumentChunkEmbedding
from app.services.embeddings.base import (
    EmbeddingProviderConfigurationError,
    EmbeddingProviderError,
)
from app.services.vector_retrieval import (
    cosine_similarity,
    ensure_course_chunk_embeddings,
    search_course_chunks_by_vector,
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


def test_cosine_similarity_scores_identical_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([1.0], [1.0, 0.0]) == 0.0


def test_ensure_course_chunk_embeddings_creates_missing_embeddings_once() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        upload_text(client, course_id, "notes.txt", b"Binary search halves sorted arrays.")

        testing_session_local = client.testing_session_local  # type: ignore[attr-defined]
        db = testing_session_local()
        created_count = ensure_course_chunk_embeddings(db, course_id=uuid.UUID(course_id))
        second_created_count = ensure_course_chunk_embeddings(db, course_id=uuid.UUID(course_id))
        embeddings = db.scalars(select(DocumentChunkEmbedding)).all()

        assert created_count == 1
        assert second_created_count == 0
        assert len(embeddings) == 1
        assert embeddings[0].provider == "fake"
        assert embeddings[0].model == "fake-token-hash-v1"
        assert embeddings[0].dimensions == 24
        db.close()
    finally:
        app.dependency_overrides.clear()


def test_vector_search_ranks_semantic_synonym_match_above_distractor() -> None:
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
        results = search_course_chunks_by_vector(
            db,
            course_id=uuid.UUID(course_id),
            query="rapid retrieval ordered list",
            limit=2,
        )

        assert len(results) == 2
        assert results[0].document_filename == "binary-search.txt"
        assert results[0].similarity > results[1].similarity
        assert results[0].embedding_provider == "fake"
        db.close()
    finally:
        app.dependency_overrides.clear()


def test_vector_search_only_returns_chunks_from_requested_course() -> None:
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
        results = search_course_chunks_by_vector(
            db,
            course_id=uuid.UUID(algorithms_course_id),
            query="rapid retrieval ordered list",
        )

        assert len(results) == 1
        assert results[0].document_filename == "algorithms.txt"
        db.close()
    finally:
        app.dependency_overrides.clear()


def test_vector_search_endpoint_returns_ranked_results() -> None:
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
            f"/courses/{course_id}/search/vector",
            params={"query": "rapid retrieval ordered list"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["course_id"] == course_id
        assert payload["query"] == "rapid retrieval ordered list"
        assert len(payload["results"]) == 1
        assert payload["results"][0]["document_filename"] == "binary-search.txt"
        assert payload["results"][0]["similarity"] > 0
        assert payload["results"][0]["embedding_provider"] == "fake"
        assert payload["results"][0]["embedding_model"] == "fake-token-hash-v1"
    finally:
        app.dependency_overrides.clear()


def test_vector_search_endpoint_returns_404_for_missing_course() -> None:
    client = build_client()

    try:
        response = client.get(
            f"/courses/{uuid.uuid4()}/search/vector",
            params={"query": "binary search"},
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_vector_search_endpoint_rejects_empty_query_terms() -> None:
    client = build_client()

    try:
        course_id = create_course(client)
        response = client.get(
            f"/courses/{course_id}/search/vector",
            params={"query": "   "},
        )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_vector_search_endpoint_returns_503_for_embedding_config_error(
    monkeypatch,
) -> None:
    client = build_client()

    def raise_config_error():
        raise EmbeddingProviderConfigurationError("Embedding provider is not configured")

    try:
        course_id = create_course(client)
        monkeypatch.setattr(
            "app.services.vector_retrieval.get_embedding_provider",
            raise_config_error,
        )

        response = client.get(
            f"/courses/{course_id}/search/vector",
            params={"query": "binary search"},
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "Embedding provider is not configured"
    finally:
        app.dependency_overrides.clear()


def test_vector_search_endpoint_returns_502_for_embedding_provider_error(
    monkeypatch,
) -> None:
    client = build_client()

    class FailingEmbeddingProvider:
        provider_name = "openai"
        model_name = "text-embedding-3-small"
        dimensions = 1536

        def embed_text(self, _text: str) -> list[float]:
            raise EmbeddingProviderError("OpenAI embedding provider request failed")

    try:
        course_id = create_course(client)
        upload_text(client, course_id, "notes.txt", b"Binary search halves arrays.")
        monkeypatch.setattr(
            "app.services.vector_retrieval.get_embedding_provider",
            lambda: FailingEmbeddingProvider(),
        )

        response = client.get(
            f"/courses/{course_id}/search/vector",
            params={"query": "binary search"},
        )

        assert response.status_code == 502
        assert response.json()["detail"] == "OpenAI embedding provider request failed"
    finally:
        app.dependency_overrides.clear()
