import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, Document, DocumentChunk, DocumentStatus

QUERY_TERM_PATTERN = re.compile(r"[a-z0-9]+")


class EmptySearchQueryError(ValueError):
    pass


class CourseNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class RankedChunk:
    document_id: uuid.UUID
    document_filename: str
    chunk_id: uuid.UUID
    chunk_index: int
    page_number: int | None
    text: str
    score: int
    matched_terms: list[str]


def tokenize_query(query: str) -> list[str]:
    terms = QUERY_TERM_PATTERN.findall(query.lower())
    unique_terms = list(dict.fromkeys(terms))

    if not unique_terms:
        raise EmptySearchQueryError("Search query must include at least one word or number")

    return unique_terms


def score_text(text: str, terms: list[str]) -> tuple[int, list[str]]:
    normalized_text = text.lower()
    term_counts = {term: normalized_text.count(term) for term in terms}
    matched_terms = [term for term, count in term_counts.items() if count > 0]
    score = sum(term_counts.values())
    return score, matched_terms


def search_course_chunks(
    db: Session,
    *,
    course_id: uuid.UUID,
    query: str,
    limit: int = 5,
) -> list[RankedChunk]:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    course = db.get(Course, course_id)
    if course is None:
        raise CourseNotFoundError("Course was not found")

    terms = tokenize_query(query)
    statement = (
        select(DocumentChunk, Document)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(Document.course_id == course_id)
        .where(Document.status == DocumentStatus.completed)
        .order_by(Document.filename, DocumentChunk.chunk_index)
    )

    ranked_chunks: list[RankedChunk] = []
    for chunk, document in db.execute(statement):
        score, matched_terms = score_text(chunk.text, terms)
        if score == 0:
            continue

        ranked_chunks.append(
            RankedChunk(
                document_id=document.id,
                document_filename=document.filename,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                text=chunk.text,
                score=score,
                matched_terms=matched_terms,
            )
        )

    return sorted(
        ranked_chunks,
        key=lambda result: (-result.score, result.document_filename, result.chunk_index),
    )[:limit]
