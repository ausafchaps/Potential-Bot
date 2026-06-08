import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import QuizDifficulty, QuizStatus


class QuizCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    question_count: int = Field(default=5, ge=1, le=10)
    difficulty: QuizDifficulty = QuizDifficulty.medium
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator("topic")
    @classmethod
    def normalize_topic(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("topic must not be empty")
        return normalized


class QuizCitationResponse(BaseModel):
    position: int
    document_id: uuid.UUID | None
    document_filename: str
    chunk_id: uuid.UUID | None
    chunk_index: int
    page_number: int | None
    text: str

    model_config = ConfigDict(from_attributes=True)


class QuizQuestionOptionResponse(BaseModel):
    id: uuid.UUID
    position: int
    text: str
    is_correct: bool

    model_config = ConfigDict(from_attributes=True)


class QuizQuestionResponse(BaseModel):
    id: uuid.UUID
    position: int
    question: str
    explanation: str
    options: list[QuizQuestionOptionResponse]
    citations: list[QuizCitationResponse]


class QuizResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    topic: str
    title: str | None
    difficulty: QuizDifficulty
    status: QuizStatus
    provider: str
    questions: list[QuizQuestionResponse]
    created_at: datetime
    updated_at: datetime


class QuizSummaryResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    topic: str
    title: str | None
    difficulty: QuizDifficulty
    status: QuizStatus
    provider: str
    question_count: int
    created_at: datetime
    updated_at: datetime

