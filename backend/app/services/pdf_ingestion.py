import uuid
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.models import Document
from app.services.ingestion import (
    TextPage,
    complete_document_from_pages,
    create_processing_document,
    fail_document_ingestion,
)

SUPPORTED_PDF_CONTENT_TYPES = {"application/pdf"}


class UnsupportedPdfDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class PdfIngestionFailure(Exception):
    document: Document
    reason: str


def extract_pdf_pages(raw_content: bytes) -> list[TextPage]:
    reader = PdfReader(BytesIO(raw_content))
    pages: list[TextPage] = []

    for index, page in enumerate(reader.pages, start=1):
        pages.append(TextPage(text=page.extract_text() or "", page_number=index))

    return pages


def ingest_pdf_document(
    db: Session,
    *,
    course_id: uuid.UUID,
    filename: str,
    content_type: str,
    raw_content: bytes,
) -> Document:
    if content_type not in SUPPORTED_PDF_CONTENT_TYPES and not filename.lower().endswith(".pdf"):
        raise UnsupportedPdfDocumentError("Only PDF documents are supported")

    try:
        pages = extract_pdf_pages(raw_content)
    except Exception as exc:
        raise ValueError("PDF could not be read") from exc

    document = create_processing_document(
        db,
        course_id=course_id,
        filename=filename,
        content_type=content_type or "application/pdf",
        page_count=len(pages),
    )

    try:
        return complete_document_from_pages(
            db,
            document=document,
            pages=pages,
            empty_error_message="PDF did not contain extractable text",
        )
    except ValueError as exc:
        fail_document_ingestion(db, document)
        raise PdfIngestionFailure(document=document, reason=str(exc)) from exc
