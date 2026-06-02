from pydantic import BaseModel


class UsageMetricsResponse(BaseModel):
    users: int
    courses: int
    documents: int
    document_chunks: int
    questions: int
    answers: int
    citations: int
    feedback_events: int


class DocumentMetricsResponse(BaseModel):
    documents_by_status: dict[str, int]
    documents_by_content_type: dict[str, int]
    average_chunks_per_document: float


class AnswerMetricsResponse(BaseModel):
    answers_by_status: dict[str, int]
    citation_coverage_rate: float


class FeedbackMetricsResponse(BaseModel):
    average_feedback_rating: float | None
    feedback_rating_distribution: dict[str, int]


class AdminMetricsResponse(BaseModel):
    usage: UsageMetricsResponse
    documents: DocumentMetricsResponse
    answers: AnswerMetricsResponse
    feedback: FeedbackMetricsResponse

