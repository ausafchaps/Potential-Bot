import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Course, Document, DocumentChunk, DocumentStatus

DEFAULT_CHUNK_SIZE = 1_200
DEFAULT_CHUNK_OVERLAP = 150


class CourseNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class TextPage:
    text: str
    page_number: int | None = None


@dataclass(frozen=True)
class DocumentIngestionFailure(Exception):
    document: Document
    reason: str


def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be zero or greater")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    normalized_text = text.strip()
    if not normalized_text:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(normalized_text):
        end = min(start + chunk_size, len(normalized_text))
        chunk = normalized_text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end == len(normalized_text):
            break

        start = end - chunk_overlap

    return chunks


def estimate_token_count(text: str) -> int:
    return len(text.split())


def create_processing_document(
    db: Session,
    *,
    course_id: uuid.UUID,
    filename: str,
    content_type: str,
    page_count: int | None = None,
) -> Document:
    course = db.get(Course, course_id)
    if course is None:
        raise CourseNotFoundError("Course was not found")

    document = Document(
        course_id=course_id,
        filename=filename,
        content_type=content_type,
        page_count=page_count,
        status=DocumentStatus.processing,
    )
    db.add(document)
    db.flush()
    return document


def complete_document_from_pages(
    db: Session,
    *,
    document: Document,
    pages: list[TextPage],
    empty_error_message: str,
) -> Document:
    chunk_index = 0

    for page in pages:
        for chunk in chunk_text(page.text):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk_index,
                    text=chunk,
                    page_number=page.page_number,
                    token_count=estimate_token_count(chunk),
                )
            )
            chunk_index += 1

    if chunk_index == 0:
        raise ValueError(empty_error_message)

    document.status = DocumentStatus.completed
    db.commit()
    db.refresh(document)
    return document


def fail_document_ingestion(db: Session, document: Document) -> Document:
    document.status = DocumentStatus.failed
    db.commit()
    db.refresh(document)
    return document

