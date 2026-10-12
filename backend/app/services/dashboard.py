import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, case, func, literal, or_, select, union_all
from sqlalchemy.orm import Session

from app.models import (
    Answer,
    AnswerStatus,
    Course,
    Document,
    DocumentStatus,
    Flashcard,
    FlashcardProgress,
    FlashcardSet,
    FlashcardSetStatus,
    Question,
    Quiz,
    QuizAttempt,
    QuizStatus,
)
from app.schemas.dashboard import (
    DashboardAction,
    DashboardReview,
    DashboardSavedWork,
    DashboardScore,
    StudyDashboard,
)
from app.services.retrieval import CourseNotFoundError
from app.services.weak_topic_analytics import get_course_weak_topic_analytics


def get_study_dashboard(db: Session, course_id: uuid.UUID, user_id: uuid.UUID) -> StudyDashboard:
    course = db.scalar(select(Course).where(Course.id == course_id, Course.owner_id == user_id))
    if course is None:
        raise CourseNotFoundError("Course was not found")
    now = int(time.time())
    progress = FlashcardProgress
    due = or_(progress.flashcard_id.is_(None), progress.due_at <= now)
    counts = db.execute(select(
        func.count(Flashcard.id), func.coalesce(func.sum(case((due, 1), else_=0)), 0),
        func.min(case((progress.due_at > now, progress.due_at), else_=None)),
    ).join(FlashcardSet, Flashcard.flashcard_set_id == FlashcardSet.id).outerjoin(
        progress, and_(progress.flashcard_id == Flashcard.id, progress.user_id == user_id)
    ).where(FlashcardSet.course_id == course_id)).one()
    review = DashboardReview(total_count=counts[0], due_count=counts[1],
        next_due_at=datetime.fromtimestamp(counts[2], UTC) if counts[2] is not None else None)

    document_count = db.scalar(select(func.count(Document.id)).where(
        Document.course_id == course_id, Document.status == DocumentStatus.completed)) or 0
    scores = db.execute(select(QuizAttempt, Quiz.title, Quiz.topic).join(Quiz).where(
        Quiz.course_id == course_id).order_by(
        QuizAttempt.created_at.desc(), QuizAttempt.id.desc()).limit(5)).all()
    recent_scores = [DashboardScore(id=attempt.id, quiz_id=attempt.quiz_id,
        title=title or topic, topic=topic, score_percent=attempt.score_percent,
        correct_count=attempt.correct_count, question_count=attempt.question_count,
        created_at=attempt.created_at) for attempt, title, topic in scores]

    # One bounded union produces a stable newest-first list across saved types.
    quizzes = select(Quiz.id.label("id"), literal("quiz").label("kind"),
        func.coalesce(Quiz.title, Quiz.topic).label("title"), Quiz.created_at.label("created_at")
    ).where(Quiz.course_id == course_id, Quiz.status == QuizStatus.generated, Quiz.questions.any())
    cards = select(FlashcardSet.id, literal("flashcards"),
        func.coalesce(FlashcardSet.title, FlashcardSet.topic), FlashcardSet.created_at
    ).where(FlashcardSet.course_id == course_id,
            FlashcardSet.status == FlashcardSetStatus.generated, FlashcardSet.cards.any())
    questions = select(Question.id, literal("answer").label("kind"),
                       Question.text.label("title"), Question.created_at).where(
        Question.course_id == course_id,
        Question.answers.any(Answer.status == AnswerStatus.answered))
    saved = union_all(questions, quizzes, cards).subquery()
    saved_count = db.scalar(select(func.count()).select_from(saved)) or 0
    saved_work = [DashboardSavedWork(**dict(row._mapping)) for row in db.execute(
        select(saved).order_by(
            saved.c.created_at.desc(), saved.c.kind, saved.c.id.desc()).limit(6))]

    analytics = get_course_weak_topic_analytics(db, course_id=course_id, limit=5)
    weak_topics = [topic for topic in analytics.weak_topics if topic.weakness_score > 0]
    action = choose_action(db, course_id, review, weak_topics, saved_work, document_count)
    return StudyDashboard(course_id=course_id, course_title=course.title,
        document_count=document_count, saved_count=saved_count,
        quiz_attempt_count=analytics.attempt_count, review=review, recent_scores=recent_scores,
        weak_topics=weak_topics, saved_work=saved_work, next_action=action)


def choose_action(db, course_id, review, weak_topics, saved_work,
                  document_count) -> DashboardAction:
    if review.due_count:
        cards_label = "card is" if review.due_count == 1 else "cards are"
        return DashboardAction(type="review", title="Review your due flashcards",
            reason=(f"{review.due_count} {cards_label} ready. "
                    "A short review keeps your notes fresh."),
            label="Start review")
    if weak_topics:
        topic = weak_topics[0]
        quiz_id = db.scalar(select(Quiz.id).where(Quiz.course_id == course_id,
            Quiz.topic == topic.topic, Quiz.status == QuizStatus.generated, Quiz.questions.any()
        ).order_by(Quiz.created_at.desc(), Quiz.id.desc()).limit(1))
        reason = (f"Your accuracy on this topic is {round(topic.accuracy_rate * 100)}% "
                  "in saved quizzes.")
        if quiz_id:
            return DashboardAction(type="saved", title=f"Practice {topic.topic}", reason=reason,
                                   label="Open saved quiz", kind="quiz", id=quiz_id)
        if document_count:
            return DashboardAction(type="ask", title=f"Revisit {topic.topic}", reason=reason,
                label="Prepare a question",
                prompt=f"Explain {topic.topic} using my course notes and cite the sources.")
    if saved_work:
        newest = saved_work[0]
        return DashboardAction(type="saved", title="Continue your saved study work",
            reason=newest.title, label="Continue studying", kind=newest.kind, id=newest.id)
    if document_count:
        return DashboardAction(type="ask", title="Explore your uploaded notes",
            reason="Your notes are ready. Start with a grounded explanation of their key topics.",
            label="Prepare a question",
            prompt="Explain the key topics in my course notes and cite the sources.")
    return DashboardAction(type="upload", title="Add your first course notes",
        reason="Upload a text file or PDF to start asking questions and building study tools.",
        label="Add notes")
