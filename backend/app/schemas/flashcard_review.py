import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.flashcard import FlashcardCitationResponse


class ReviewRating(StrEnum):
    again = "again"
    hard = "hard"
    good = "good"
    easy = "easy"


class FlashcardReviewCreate(BaseModel):
    rating: ReviewRating
    version: int = Field(ge=0)


class FlashcardReviewResponse(BaseModel):
    flashcard_id: uuid.UUID
    version: int
    rating: ReviewRating
    interval_minutes: int
    reviewed_at: datetime
    due_at: datetime


class DueFlashcard(BaseModel):
    id: uuid.UUID
    flashcard_set_id: uuid.UUID
    title: str
    front: str
    back: str
    version: int
    due_at: datetime | None
    citations: list[FlashcardCitationResponse]


class FlashcardReviewQueue(BaseModel):
    total_count: int
    reviewed_count: int
    due_count: int
    next_due_at: datetime | None
    cards: list[DueFlashcard]
