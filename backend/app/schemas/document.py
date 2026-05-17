import uuid

from pydantic import BaseModel, ConfigDict

from app.models import DocumentStatus


class DocumentUploadResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    filename: str
    content_type: str
    status: DocumentStatus
    chunk_count: int

    model_config = ConfigDict(from_attributes=True)

