import uuid
from datetime import datetime, timedelta

import pytest
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import (
    AIUsageBucket,
    Answer,
    Course,
    Document,
    Flashcard,
    FlashcardProgress,
    FlashcardSet,
    Question,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    User,
)
from app.services import dashboard
from auth_helpers import TEST_PASSWORD_HASH, authenticated_client
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions() as db:
        owner = User(email="dashboard@example.com", display_name="Student",
                     password_hash=TEST_PASSWORD_HASH)
        other = User(email="private@example.com", display_name="Private",
                     password_hash=TEST_PASSWORD_HASH)
        courses = [Course(owner=owner, title="Algorithms"), Course(owner=owner, title="Empty"),
                   Course(owner=other, title="Private")]
        db.add_all(courses)
        db.commit()
        ids, user_id = [c.id for c in courses], owner.id
    def override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(dashboard.time, "time", lambda: 1000)
    try:
        yield authenticated_client(app, email="dashboard@example.com"), sessions, ids, user_id
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def make_quiz(db, course_id, topic="binary search", date=None, question=True):
    quiz = Quiz(course_id=course_id, topic=topic, title=f"Practice {topic}", difficulty="easy",
                status="generated", provider="fake", created_at=date or datetime(2026, 10, 12))
    if question:
        quiz.questions.append(QuizQuestion(position=1, question_text="What?", explanation="Why"))
    db.add(quiz)
    db.flush()
    return quiz


def seed_progress(db, course_id, user_id):
    date = datetime(2026, 10, 12)
    quiz = make_quiz(db, course_id, date=date)
    db.add(QuizAttempt(quiz_id=quiz.id, correct_count=1, question_count=4, score_percent=25,
                       created_at=date + timedelta(hours=1)))
    question = Question(course_id=course_id, text="Explain <binary> search", created_at=date)
    question.answers.append(Answer(status="answered", text="Sorted halves", provider="fake"))
    db.add(question)
    card_set = FlashcardSet(course_id=course_id, topic="binary search", title="Search cards",
                           status="generated", difficulty="easy", provider="fake", created_at=date)
    cards = [Flashcard(flashcard_set=card_set, position=i, front=f"Q{i}", back=f"A{i}")
             for i in range(1, 5)]
    db.add_all(cards)
    db.flush()
    # New, due before now, due exactly now, and scheduled in the future.
    for card, due_at in zip(cards[1:], [999, 1000, 1001], strict=True):
        db.add(FlashcardProgress(flashcard_id=card.id, user_id=user_id, due_at=due_at,
                                last_reviewed_at=900, last_rating="good",
                                review_count=1, interval_minutes=1))
    db.add(Document(course_id=course_id, filename="notes.txt", content_type="text/plain",
                    status="completed"))
    db.add(Document(course_id=course_id, filename="failed.txt", content_type="text/plain",
                    status="failed"))
    db.commit()
    return quiz.id, cards, card_set.id


def test_dashboard_has_bounded_course_progress_and_review_priority(setup):
    client, sessions, courses, user_id = setup
    with sessions() as db:
        seed_progress(db, courses[0], user_id)
        # Other-course results, even for the same owner, must not leak into this course.
        seed_progress(db, courses[1], user_id)
    response = client.get(f"/courses/{courses[0]}/dashboard")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["course_title"] == "Algorithms"
    assert data["document_count"] == 1
    assert data["saved_count"] == 3
    assert data["quiz_attempt_count"] == 1
    assert data["review"]["total_count"] == 4
    assert data["review"]["due_count"] == 3
    assert data["review"]["next_due_at"] == "1970-01-01T00:16:41Z"
    assert data["weak_topics"][0]["accuracy_rate"] == 0.25
    assert data["next_action"]["type"] == "review"
    assert len(data["recent_scores"]) == 1
    assert {item["kind"] for item in data["saved_work"]} == {"answer", "quiz", "flashcards"}
    assert "back" not in str(data["review"])
    with sessions() as db:
        assert db.scalar(select(func.count(AIUsageBucket.bucket_key))) == 0


def test_empty_courses_and_notes_only_have_clear_next_steps(setup):
    client, sessions, courses, _ = setup
    empty = client.get(f"/courses/{courses[0]}/dashboard").json()
    assert empty["review"] == {"total_count": 0, "due_count": 0, "next_due_at": None}
    assert empty["saved_work"] == empty["recent_scores"] == empty["weak_topics"] == []
    assert empty["next_action"]["type"] == "upload"
    with sessions() as db:
        db.add(Document(course_id=courses[0], filename="notes.txt", content_type="text/plain",
                        status="completed"))
        db.commit()
    notes = client.get(f"/courses/{courses[0]}/dashboard").json()
    assert notes["next_action"]["type"] == "ask"
    assert notes["next_action"]["prompt"]


def test_weak_topic_opens_saved_quiz_when_no_cards_are_due(setup):
    client, sessions, courses, _ = setup
    with sessions() as db:
        quiz = make_quiz(db, courses[0])
        quiz_id = str(quiz.id)
        db.add(QuizAttempt(quiz_id=quiz.id, correct_count=0, question_count=4, score_percent=0))
        db.commit()
    data = client.get(f"/courses/{courses[0]}/dashboard").json()
    assert data["next_action"]["type"] == "saved"
    assert data["next_action"]["kind"] == "quiz"
    assert data["next_action"]["id"] == quiz_id
    assert "binary search" in data["next_action"]["title"]


def test_correct_quizzes_are_not_reported_as_weak_and_saved_work_resumes(setup):
    client, sessions, courses, _ = setup
    with sessions() as db:
        quiz = make_quiz(db, courses[0])
        db.add(QuizAttempt(quiz_id=quiz.id, correct_count=4, question_count=4, score_percent=100))
        db.commit()
    data = client.get(f"/courses/{courses[0]}/dashboard").json()
    assert data["weak_topics"] == []
    assert data["next_action"]["type"] == "saved"
    assert data["next_action"]["title"] == "Continue your saved study work"


def test_lists_are_bounded_newest_first_and_exclude_unusable_work(setup):
    client, sessions, courses, _ = setup
    with sessions() as db:
        for index in range(10):
            quiz = make_quiz(db, courses[0], topic=f"topic-{index}",
                             date=datetime(2026, 10, 1) + timedelta(days=index))
            db.add(QuizAttempt(quiz_id=quiz.id, correct_count=0, question_count=4, score_percent=0,
                               created_at=datetime(2026, 10, 1) + timedelta(days=index)))
        make_quiz(db, courses[0], topic="empty-quiz", question=False)
        question = Question(course_id=courses[0], text="No evidence")
        question.answers.append(Answer(status="insufficient_evidence", provider="fake"))
        db.add(question)
        db.commit()
    data = client.get(f"/courses/{courses[0]}/dashboard").json()
    assert len(data["recent_scores"]) == 5
    assert data["recent_scores"][0]["topic"] == "topic-9"
    assert len(data["weak_topics"]) == 5
    assert len(data["saved_work"]) == 6
    assert data["saved_work"][0]["title"] == "Practice topic-9"
    assert data["saved_count"] == 10
    assert data["quiz_attempt_count"] == 10
    assert "empty-quiz" not in str(data)
    assert "No evidence" not in str(data)


def test_owner_auth_and_optional_verification_gate(setup, monkeypatch):
    client, _, courses, _ = setup
    assert client.get(f"/courses/{courses[2]}/dashboard").status_code == 404
    assert client.get(f"/courses/{uuid.uuid4()}/dashboard").status_code == 404
    monkeypatch.setattr(settings, "auth_require_email_verification", True)
    assert client.get(f"/courses/{courses[0]}/dashboard").status_code == 403
    client.headers.clear()
    assert client.get(f"/courses/{courses[0]}/dashboard").status_code == 401


def test_storage_failure_is_safe_and_retryable(setup, monkeypatch):
    client, _, courses, _ = setup
    from app.api.routes import dashboard as route
    def fail(*args):
        raise OperationalError("read", {}, Exception("private database details"))
    monkeypatch.setattr(route, "get_study_dashboard", fail)
    response = client.get(f"/courses/{courses[0]}/dashboard")
    assert response.status_code == 503
    assert "private" not in response.text
    assert response.headers["cache-control"] == "no-store"
