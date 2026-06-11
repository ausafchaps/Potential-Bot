import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import FlashcardDifficulty, FlashcardSetStatus


class FlashcardSetCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    card_count: int = Field(default=5, ge=1, le=20)
    difficulty: FlashcardDifficulty = FlashcardDifficulty.medium
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator("topic")
    @classmethod
    def normalize_topic(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("topic must not be empty")
        return normalized


class FlashcardCitationResponse(BaseModel):
    position: int
    document_id: uuid.UUID | None
    document_filename: str
    chunk_id: uuid.UUID | None
    chunk_index: int
    page_number: int | None
    text: str

    model_config = ConfigDict(from_attributes=True)


class FlashcardResponse(BaseModel):
    id: uuid.UUID
    position: int
    front: str
    back: str
    citations: list[FlashcardCitationResponse]


class FlashcardSetResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    topic: str
    title: str | None
    difficulty: FlashcardDifficulty
    status: FlashcardSetStatus
    provider: str
    cards: list[FlashcardResponse]
    created_at: datetime
    updated_at: datetime


class FlashcardSetSummaryResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    topic: str
    title: str | None
    difficulty: FlashcardDifficulty
    status: FlashcardSetStatus
    provider: str
    card_count: int
    created_at: datetime
    updated_at: datetime
