import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.document import (
    DocumentChunkResponse,
    DocumentSummaryResponse,
    DocumentUploadResponse,
)
from app.services.document_management import (
    CourseNotFoundError as DocumentManagementCourseNotFoundError,
)
from app.services.document_management import (
    DocumentNotFoundError,
    delete_document,
    get_document_with_chunk_count,
    list_course_documents,
    list_document_chunks,
)
from app.services.ingestion import CourseNotFoundError
from app.services.pdf_ingestion import (
    PdfIngestionFailure,
    UnsupportedPdfDocumentError,
    ingest_pdf_document,
)
from app.services.text_ingestion import (
    TextIngestionFailure,
    UnsupportedTextDocumentError,
    ingest_text_document,
)

router = APIRouter(prefix="/courses/{course_id}/documents", tags=["documents"])
document_router = APIRouter(prefix="/documents", tags=["documents"])


def build_document_summary(document, chunk_count: int) -> DocumentSummaryResponse:
    return DocumentSummaryResponse(
        id=document.id,
        course_id=document.course_id,
        filename=document.filename,
        content_type=document.content_type,
        status=document.status,
        page_count=document.page_count,
        chunk_count=chunk_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get("", response_model=list[DocumentSummaryResponse])
def list_course_documents_endpoint(
    course_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[DocumentSummaryResponse]:
    try:
        documents = list_course_documents(db, course_id)
    except DocumentManagementCourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return [build_document_summary(document, chunk_count) for document, chunk_count in documents]


@router.post("/text", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_text_document(
    course_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
) -> DocumentUploadResponse:
    raw_content = await file.read()

    try:
        document = ingest_text_document(
            db,
            course_id=course_id,
            filename=file.filename or "upload.txt",
            content_type=file.content_type or "application/octet-stream",
            raw_content=raw_content,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnsupportedTextDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except TextIngestionFailure as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "document_id": str(exc.document.id),
                "status": exc.document.status,
                "reason": exc.reason,
            },
        ) from exc

    return DocumentUploadResponse(
        id=document.id,
        course_id=document.course_id,
        filename=document.filename,
        content_type=document.content_type,
        status=document.status,
        page_count=document.page_count,
        chunk_count=len(document.chunks),
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post("/pdf", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_pdf_document(
    course_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
) -> DocumentUploadResponse:
    raw_content = await file.read()

    try:
        document = ingest_pdf_document(
            db,
            course_id=course_id,
            filename=file.filename or "upload.pdf",
            content_type=file.content_type or "application/octet-stream",
            raw_content=raw_content,
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnsupportedPdfDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except (PdfIngestionFailure, ValueError) as exc:
        detail: str | dict[str, str]
        if isinstance(exc, PdfIngestionFailure):
            detail = {
                "document_id": str(exc.document.id),
                "status": exc.document.status,
                "reason": exc.reason,
            }
        else:
            detail = str(exc)

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=detail,
        ) from exc

    return DocumentUploadResponse(
        id=document.id,
        course_id=document.course_id,
        filename=document.filename,
        content_type=document.content_type,
        status=document.status,
        page_count=document.page_count,
        chunk_count=len(document.chunks),
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@document_router.get("/{document_id}", response_model=DocumentSummaryResponse)
def get_document_endpoint(
    document_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> DocumentSummaryResponse:
    try:
        document, chunk_count = get_document_with_chunk_count(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return build_document_summary(document, chunk_count)


@document_router.get("/{document_id}/chunks", response_model=list[DocumentChunkResponse])
def list_document_chunks_endpoint(
    document_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[DocumentChunkResponse]:
    try:
        return list_document_chunks(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@document_router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_endpoint(
    document_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    try:
        delete_document(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
