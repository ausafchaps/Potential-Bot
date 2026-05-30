import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnswerFeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2_000)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None


class AnswerFeedbackResponse(BaseModel):
    id: uuid.UUID
    answer_id: uuid.UUID
    rating: int
    comment: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

