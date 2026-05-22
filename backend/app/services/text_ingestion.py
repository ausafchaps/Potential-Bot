import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Document
from app.services.ingestion import (
    TextPage,
    complete_document_from_pages,
    create_processing_document,
    fail_document_ingestion,
)

SUPPORTED_TEXT_CONTENT_TYPES = {"text/plain"}


class UnsupportedTextDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class TextIngestionFailure(Exception):
    document: Document
    reason: str


def ingest_text_document(
    db: Session,
    *,
    course_id: uuid.UUID,
    filename: str,
    content_type: str,
    raw_content: bytes,
) -> Document:
    if content_type not in SUPPORTED_TEXT_CONTENT_TYPES and not filename.lower().endswith(".txt"):
        raise UnsupportedTextDocumentError("Only plain text documents are supported")

    document = create_processing_document(
        db,
        course_id=course_id,
        filename=filename,
        content_type=content_type or "text/plain",
    )

    try:
        text = raw_content.decode("utf-8")
        return complete_document_from_pages(
            db,
            document=document,
            pages=[TextPage(text=text)],
            empty_error_message="Text document did not contain readable content",
        )
    except (UnicodeDecodeError, ValueError) as exc:
        fail_document_ingestion(db, document)
        raise TextIngestionFailure(document=document, reason=str(exc)) from exc
