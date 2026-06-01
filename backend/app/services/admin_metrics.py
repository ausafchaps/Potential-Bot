from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models import (
    Answer,
    AnswerFeedback,
    AnswerStatus,
    Citation,
    Course,
    Document,
    DocumentChunk,
    DocumentStatus,
    Question,
    User,
)
from app.schemas.admin import (
    AdminMetricsResponse,
    AnswerMetricsResponse,
    DocumentMetricsResponse,
    FeedbackMetricsResponse,
    UsageMetricsResponse,
)


def count_rows(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def count_by_field(db: Session, model, field) -> dict[str, int]:
    rows = db.execute(select(field, func.count()).select_from(model).group_by(field))
    return {str(value): count for value, count in rows}


def get_usage_metrics(db: Session) -> UsageMetricsResponse:
    return UsageMetricsResponse(
        users=count_rows(db, User),
        courses=count_rows(db, Course),
        documents=count_rows(db, Document),
        document_chunks=count_rows(db, DocumentChunk),
        questions=count_rows(db, Question),
        answers=count_rows(db, Answer),
        citations=count_rows(db, Citation),
        feedback_events=count_rows(db, AnswerFeedback),
    )


def get_document_metrics(db: Session) -> DocumentMetricsResponse:
    document_count = count_rows(db, Document)
    chunk_count = count_rows(db, DocumentChunk)
    status_counts = {status.value: 0 for status in DocumentStatus}
    status_counts.update(count_by_field(db, Document, Document.status))
    average_chunks = round(chunk_count / document_count, 2) if document_count else 0.0

    return DocumentMetricsResponse(
        documents_by_status=status_counts,
        documents_by_content_type=count_by_field(db, Document, Document.content_type),
        average_chunks_per_document=average_chunks,
    )


def get_answer_metrics(db: Session) -> AnswerMetricsResponse:
    answer_count = count_rows(db, Answer)
    status_counts = {status.value: 0 for status in AnswerStatus}
    status_counts.update(count_by_field(db, Answer, Answer.status))

    cited_answer_count = db.scalar(
        select(func.count(distinct(Citation.answer_id))).select_from(Citation)
    ) or 0
    citation_coverage = round(cited_answer_count / answer_count, 2) if answer_count else 0.0

    return AnswerMetricsResponse(
        answers_by_status=status_counts,
        citation_coverage_rate=citation_coverage,
    )


def get_feedback_metrics(db: Session) -> FeedbackMetricsResponse:
    feedback_count = count_rows(db, AnswerFeedback)
    average_rating = db.scalar(select(func.avg(AnswerFeedback.rating)))
    rating_distribution = {str(rating): 0 for rating in range(1, 6)}
    rating_distribution.update(count_by_field(db, AnswerFeedback, AnswerFeedback.rating))

    return FeedbackMetricsResponse(
        average_feedback_rating=round(float(average_rating), 2) if feedback_count else None,
        feedback_rating_distribution=rating_distribution,
    )


def get_admin_metrics(db: Session) -> AdminMetricsResponse:
    return AdminMetricsResponse(
        usage=get_usage_metrics(db),
        documents=get_document_metrics(db),
        answers=get_answer_metrics(db),
        feedback=get_feedback_metrics(db),
    )

