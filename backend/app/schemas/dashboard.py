import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.weak_topics import WeakTopicResponse


class DashboardReview(BaseModel):
    total_count: int
    due_count: int
    next_due_at: datetime | None


class DashboardScore(BaseModel):
    id: uuid.UUID
    quiz_id: uuid.UUID
    title: str
    topic: str
    score_percent: float
    correct_count: int
    question_count: int
    created_at: datetime


class DashboardSavedWork(BaseModel):
    id: uuid.UUID
    kind: Literal["answer", "quiz", "flashcards"]
    title: str
    created_at: datetime


class DashboardAction(BaseModel):
    type: Literal["review", "saved", "ask", "upload"]
    title: str
    reason: str
    label: str
    kind: Literal["answer", "quiz", "flashcards"] | None = None
    id: uuid.UUID | None = None
    prompt: str | None = None


class StudyDashboard(BaseModel):
    course_id: uuid.UUID
    course_title: str
    document_count: int
    saved_count: int
    quiz_attempt_count: int
    review: DashboardReview
    recent_scores: list[DashboardScore]
    weak_topics: list[WeakTopicResponse]
    saved_work: list[DashboardSavedWork]
    next_action: DashboardAction
