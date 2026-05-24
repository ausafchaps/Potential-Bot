import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import DocumentStatus


class DocumentSummaryResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    filename: str
    content_type: str
    status: DocumentStatus
    page_count: int | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(DocumentSummaryResponse):
    pass


class DocumentChunkResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    text: str
    page_number: int | None
    token_count: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

