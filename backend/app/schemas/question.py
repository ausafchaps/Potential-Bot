import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import AnswerStatus


class QuestionCreate(BaseModel):
    question: str = Field(min_length=1, max_length=1_000)
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be empty")
        return normalized


class AnswerCitationResponse(BaseModel):
    position: int
    document_id: uuid.UUID | None
    document_filename: str
    chunk_id: uuid.UUID | None
    chunk_index: int
    page_number: int | None
    text: str

    model_config = ConfigDict(from_attributes=True)


class RetrievedChunkResponse(BaseModel):
    document_id: uuid.UUID
    document_filename: str
    chunk_id: uuid.UUID
    chunk_index: int
    page_number: int | None
    text: str
    score: int
    matched_terms: list[str]


class QuestionAnswerResponse(BaseModel):
    status: AnswerStatus
    question_id: uuid.UUID
    answer_id: uuid.UUID
    answer: str | None
    provider: str
    citations: list[AnswerCitationResponse]
    retrieved_chunks: list[RetrievedChunkResponse]
    created_at: datetime

