import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Course, Document, DocumentChunk


class CourseNotFoundError(ValueError):
    pass


class DocumentNotFoundError(ValueError):
    pass


def list_course_documents(db: Session, course_id: uuid.UUID) -> list[tuple[Document, int]]:
    course = db.get(Course, course_id)
    if course is None:
        raise CourseNotFoundError("Course was not found")

    statement = (
        select(Document, func.count(DocumentChunk.id).label("chunk_count"))
        .outerjoin(DocumentChunk, Document.id == DocumentChunk.document_id)
        .where(Document.course_id == course_id)
        .group_by(Document.id)
        .order_by(Document.created_at)
    )
    return [(document, chunk_count) for document, chunk_count in db.execute(statement)]


def get_document_with_chunk_count(db: Session, document_id: uuid.UUID) -> tuple[Document, int]:
    statement = (
        select(Document, func.count(DocumentChunk.id).label("chunk_count"))
        .outerjoin(DocumentChunk, Document.id == DocumentChunk.document_id)
        .where(Document.id == document_id)
        .group_by(Document.id)
    )
    result = db.execute(statement).one_or_none()
    if result is None:
        raise DocumentNotFoundError("Document was not found")

    document, chunk_count = result
    return document, chunk_count


def list_document_chunks(db: Session, document_id: uuid.UUID) -> list[DocumentChunk]:
    document = db.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError("Document was not found")

    statement = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    return list(db.scalars(statement))


def delete_document(db: Session, document_id: uuid.UUID) -> None:
    document = db.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError("Document was not found")

    db.delete(document)
    db.commit()

