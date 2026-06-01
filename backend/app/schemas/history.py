import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import AnswerStatus


class HistoryCitationResponse(BaseModel):
    id: uuid.UUID
    position: int
    document_id: uuid.UUID | None
    document_filename: str
    chunk_id: uuid.UUID | None
    chunk_index: int
    page_number: int | None
    text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HistoryFeedbackResponse(BaseModel):
    id: uuid.UUID
    answer_id: uuid.UUID
    rating: int
    comment: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnswerSummaryResponse(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    status: AnswerStatus
    answer: str | None
    provider: str
    citation_count: int
    feedback_count: int
    average_rating: float | None
    created_at: datetime
    updated_at: datetime


class QuestionSummaryResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    text: str
    answer_count: int
    created_at: datetime


class QuestionDetailResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    text: str
    created_at: datetime
    answers: list[AnswerSummaryResponse]


class AnswerDetailResponse(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    status: AnswerStatus
    answer: str | None
    provider: str
    prompt: str | None
    citations: list[HistoryCitationResponse]
    feedback: list[HistoryFeedbackResponse]
    created_at: datetime
    updated_at: datetime

