import json
import math
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Course,
    Document,
    DocumentChunk,
    DocumentChunkEmbedding,
    DocumentStatus,
)
from app.services.embeddings.base import EmbeddingProvider
from app.services.embeddings.factory import get_embedding_provider
from app.services.retrieval import CourseNotFoundError, EmptySearchQueryError


@dataclass(frozen=True)
class VectorRankedChunk:
    document_id: uuid.UUID
    document_filename: str
    chunk_id: uuid.UUID
    chunk_index: int
    page_number: int | None
    text: str
    similarity: float
    embedding_provider: str
    embedding_model: str


def ensure_course_chunk_embeddings(
    db: Session,
    *,
    course_id: uuid.UUID,
    provider: EmbeddingProvider | None = None,
) -> int:
    resolved_provider = provider or get_embedding_provider()
    validate_course_exists(db, course_id)

    chunks = db.execute(completed_course_chunks_statement(course_id)).all()
    created_count = 0

    for chunk, _document in chunks:
        existing_embedding = find_chunk_embedding(
            db,
            chunk_id=chunk.id,
            provider=resolved_provider.provider_name,
            model=resolved_provider.model_name,
        )
        if existing_embedding is not None:
            continue

        vector = resolved_provider.embed_text(chunk.text)
        db.add(
            DocumentChunkEmbedding(
                chunk_id=chunk.id,
                provider=resolved_provider.provider_name,
                model=resolved_provider.model_name,
                dimensions=len(vector),
                vector_json=serialize_vector(vector),
            )
        )
        created_count += 1

    if created_count:
        db.commit()

    return created_count


def search_course_chunks_by_vector(
    db: Session,
    *,
    course_id: uuid.UUID,
    query: str,
    limit: int = 5,
    provider: EmbeddingProvider | None = None,
) -> list[VectorRankedChunk]:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    if not query.strip():
        raise EmptySearchQueryError("Search query must include at least one word or number")

    resolved_provider = provider or get_embedding_provider()
    validate_course_exists(db, course_id)
    ensure_course_chunk_embeddings(db, course_id=course_id, provider=resolved_provider)
    query_vector = resolved_provider.embed_text(query)

    ranked_chunks: list[VectorRankedChunk] = []
    for chunk, document, embedding in db.execute(
        completed_course_chunk_embeddings_statement(
            course_id=course_id,
            provider=resolved_provider.provider_name,
            model=resolved_provider.model_name,
        )
    ):
        similarity = cosine_similarity(query_vector, deserialize_vector(embedding.vector_json))
        if similarity <= 0:
            continue

        ranked_chunks.append(
            VectorRankedChunk(
                document_id=document.id,
                document_filename=document.filename,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                text=chunk.text,
                similarity=similarity,
                embedding_provider=embedding.provider,
                embedding_model=embedding.model,
            )
        )

    return sorted(
        ranked_chunks,
        key=lambda result: (-result.similarity, result.document_filename, result.chunk_index),
    )[:limit]


def validate_course_exists(db: Session, course_id: uuid.UUID) -> None:
    if db.get(Course, course_id) is None:
        raise CourseNotFoundError("Course was not found")


def completed_course_chunks_statement(course_id: uuid.UUID):
    return (
        select(DocumentChunk, Document)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(Document.course_id == course_id)
        .where(Document.status == DocumentStatus.completed)
        .order_by(Document.filename, DocumentChunk.chunk_index)
    )


def completed_course_chunk_embeddings_statement(
    *,
    course_id: uuid.UUID,
    provider: str,
    model: str,
):
    return (
        select(DocumentChunk, Document, DocumentChunkEmbedding)
        .join(Document, DocumentChunk.document_id == Document.id)
        .join(DocumentChunkEmbedding, DocumentChunkEmbedding.chunk_id == DocumentChunk.id)
        .where(Document.course_id == course_id)
        .where(Document.status == DocumentStatus.completed)
        .where(DocumentChunkEmbedding.provider == provider)
        .where(DocumentChunkEmbedding.model == model)
        .order_by(Document.filename, DocumentChunk.chunk_index)
    )


def find_chunk_embedding(
    db: Session,
    *,
    chunk_id: uuid.UUID,
    provider: str,
    model: str,
) -> DocumentChunkEmbedding | None:
    return db.scalar(
        select(DocumentChunkEmbedding)
        .where(DocumentChunkEmbedding.chunk_id == chunk_id)
        .where(DocumentChunkEmbedding.provider == provider)
        .where(DocumentChunkEmbedding.model == model)
    )


def serialize_vector(vector: list[float]) -> str:
    return json.dumps(vector, separators=(",", ":"))


def deserialize_vector(vector_json: str) -> list[float]:
    payload = json.loads(vector_json)
    return [float(value) for value in payload]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0

    left_magnitude = math.sqrt(sum(value * value for value in left))
    right_magnitude = math.sqrt(sum(value * value for value in right))
    if left_magnitude == 0 or right_magnitude == 0:
        return 0.0

    dot_product = sum(
        left_value * right_value
        for left_value, right_value in zip(left, right, strict=True)
    )
    return dot_product / (left_magnitude * right_magnitude)
