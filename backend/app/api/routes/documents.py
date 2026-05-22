import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.document import DocumentUploadResponse
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
        chunk_count=len(document.chunks),
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
        chunk_count=len(document.chunks),
    )
