import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Course, Document, DocumentChunk, DocumentStatus

DEFAULT_CHUNK_SIZE = 1_200
DEFAULT_CHUNK_OVERLAP = 150
SUPPORTED_TEXT_CONTENT_TYPES = {"text/plain"}


class CourseNotFoundError(ValueError):
    pass


class UnsupportedTextDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class TextIngestionFailure(Exception):
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


def ingest_text_document(
    db: Session,
    *,
    course_id: uuid.UUID,
    filename: str,
    content_type: str,
    raw_content: bytes,
) -> Document:
    course = db.get(Course, course_id)
    if course is None:
        raise CourseNotFoundError("Course was not found")

    if content_type not in SUPPORTED_TEXT_CONTENT_TYPES and not filename.lower().endswith(".txt"):
        raise UnsupportedTextDocumentError("Only plain text documents are supported")

    document = Document(
        course_id=course_id,
        filename=filename,
        content_type=content_type or "text/plain",
        status=DocumentStatus.processing,
    )
    db.add(document)
    db.flush()

    try:
        text = raw_content.decode("utf-8")
        chunks = chunk_text(text)

        if not chunks:
            raise ValueError("Text document did not contain readable content")

        for index, chunk in enumerate(chunks):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    text=chunk,
                    token_count=estimate_token_count(chunk),
                )
            )

        document.status = DocumentStatus.completed
        db.commit()
        db.refresh(document)
        return document
    except (UnicodeDecodeError, ValueError) as exc:
        document.status = DocumentStatus.failed
        db.commit()
        db.refresh(document)
        raise TextIngestionFailure(document=document, reason=str(exc)) from exc

