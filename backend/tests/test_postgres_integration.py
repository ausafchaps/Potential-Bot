import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.core.config import settings
from app.db.session import engine
from app.main import app
from app.models import (
    AIUsageBucket,
    AuthRateLimit,
    Course,
    Flashcard,
    FlashcardProgress,
    FlashcardSet,
    User,
)
from app.schemas.flashcard_review import FlashcardReviewCreate
from app.services import account_recovery, ai_usage, flashcard_review
from app.services import auth_rate_limit as limiter
from app.services.auth import hash_password
from app.services.auth_rate_limit import AttemptLimit, AuthRateLimited, consume_attempts
from app.services.storage import UploadLimited, totals
from app.services.text_ingestion import ingest_text_document
from auth_helpers import register_user
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="PostgreSQL integration test requires a PostgreSQL database",
)


@pytest.mark.parametrize("scope", ["user_documents", "user_bytes", "project_documents",
                                    "project_bytes"])
def test_postgres_upload_storage_admission_is_atomic(monkeypatch, scope):
    user_ids, course_ids = [], []
    with Session(engine) as db:
        baseline_docs, baseline_bytes = totals(db)
        for _ in range(2):
            user_id = uuid.uuid4()
            course = Course(owner=User(id=user_id, email=f"storage-{user_id}@example.com",
                                      display_name="Storage test"), title="Storage test")
            db.add(course)
            db.flush()
            user_ids.append(user_id)
            course_ids.append(course.id)
        db.commit()
    monkeypatch.setattr(settings, "storage_user_document_limit",
                        3 if scope == "user_documents" else 20)
    monkeypatch.setattr(settings, "storage_user_text_bytes", 6 if scope == "user_bytes" else 1000)
    monkeypatch.setattr(settings, "storage_project_document_limit",
                        baseline_docs + 3 if scope == "project_documents" else baseline_docs + 100)
    monkeypatch.setattr(settings, "storage_project_text_bytes",
                        baseline_bytes + 6 if scope == "project_bytes" else baseline_bytes + 10000)

    def attempt(index):
        course_id = course_ids[index % 2] if scope.startswith("project") else course_ids[0]
        with Session(engine) as db:
            try:
                ingest_text_document(db, course_id=course_id, filename="notes.txt",
                                     content_type="text/plain", raw_content="é".encode())
                return True
            except UploadLimited:
                return False
    try:
        with ThreadPoolExecutor(max_workers=8) as workers:
            assert sum(workers.map(attempt, range(12))) == 3
        with Session(engine) as db:
            assert totals(db) == (baseline_docs + 3, baseline_bytes + 6)
    finally:
        with Session(engine) as db:
            db.execute(delete(User).where(User.id.in_(user_ids)))
            db.commit()


@pytest.mark.parametrize("same_token", [True, False])
def test_postgres_account_links_are_single_use(monkeypatch, same_token):
    from urllib.parse import parse_qs, urlsplit

    monkeypatch.setattr(account_recovery.time, "time", lambda: 172800)
    user_id = uuid.uuid4()
    with Session(engine) as db:
        user = User(id=user_id, email=f"reset-{user_id}@example.com", display_name="Reset test",
                    password_hash=hash_password("original-password-long-enough"))
        db.add(user)
        db.commit()
        codes = [parse_qs(urlsplit(account_recovery.issue_link(db, user, "reset")).fragment)
                 ["reset"][0] for _ in range(2)]

    def reset(i):
        with Session(engine) as db:
            try:
                account_recovery.consume_link(db, codes[0 if same_token else i % 2],
                                              "reset", "new-password-long-enough")
                return True
            except account_recovery.InvalidAccountLink:
                return False

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert sum(pool.map(reset, range(8))) == 1
        with Session(engine) as db:
            assert db.get(User, user_id).credential_version == 1
    finally:
        with Session(engine) as db:
            db.execute(delete(User).where(User.id == user_id))
            db.commit()


@pytest.mark.parametrize("version", [0, 1])
def test_postgres_review_ratings_commit_once(monkeypatch, version):
    monkeypatch.setattr(flashcard_review.time, "time", lambda: 172800)
    user_id, card_id = uuid.uuid4(), uuid.uuid4()
    with Session(engine) as db:
        user = User(id=user_id, email=f"review-{user_id}@example.com", display_name="Review test")
        course = Course(owner=user, title="Review test")
        card_set = FlashcardSet(course=course, topic="topic", difficulty="easy",
                               status="generated", provider="fake")
        db.add(Flashcard(id=card_id, flashcard_set=card_set, position=1, front="Q", back="A"))
        db.commit()
        if version:
            db.add(FlashcardProgress(flashcard_id=card_id, user_id=user_id, review_count=1,
                                    interval_minutes=1440, due_at=172800,
                                    last_reviewed_at=86400, last_rating="hard"))
            db.commit()

    def rate(_):
        with Session(engine) as db:
            try:
                flashcard_review.review_flashcard(db, card_id, user_id,
                    FlashcardReviewCreate(rating="good", version=version))
                return True
            except flashcard_review.ReviewConflict:
                return False

    try:
        with ThreadPoolExecutor(max_workers=8) as workers:
            assert sum(workers.map(rate, range(12))) == 1
        with Session(engine) as db:
            assert db.get(FlashcardProgress, (card_id, user_id)).review_count == version + 1
    finally:
        with Session(engine) as db:
            db.execute(delete(User).where(User.id == user_id))
            db.commit()


def test_postgres_supports_core_learning_flow() -> None:
    client = TestClient(app)
    unique_email = f"postgres-{uuid.uuid4()}@example.com"

    readiness_response = client.get("/ready")
    assert readiness_response.status_code == 200

    user_response = register_user(client,
        json={"email": unique_email, "display_name": "PostgreSQL Student"},
    )
    assert user_response.status_code == 201

    course_response = client.post(
        f"/users/{user_response.json()['id']}/courses",
        json={"title": "PostgreSQL Integration"},
    )
    assert course_response.status_code == 201
    course_id = course_response.json()["id"]

    document_response = client.post(
        f"/courses/{course_id}/documents/text",
        files={
            "file": (
                "postgres-notes.txt",
                b"Binary search repeatedly halves a sorted search space.",
                "text/plain",
            )
        },
    )
    assert document_response.status_code == 201

    question_response = client.post(
        f"/courses/{course_id}/questions",
        json={"question": "What does binary search do?"},
    )
    assert question_response.status_code == 200
    assert question_response.json()["status"] == "answered"

    dashboard_response = client.get(f"/courses/{course_id}/dashboard")
    assert dashboard_response.status_code == 200
    progress = dashboard_response.json()
    assert progress["document_count"] == 1
    assert progress["saved_count"] == 1
    assert progress["saved_work"][0]["kind"] == "answer"
    assert progress["next_action"]["type"] == "saved"


def test_postgres_rate_limits_are_atomic_across_connections(monkeypatch) -> None:
    # Keep the workers in one window even if CI starts at a minute boundary.
    monkeypatch.setattr(limiter.time, "time", lambda: 120.0)
    identity = f"postgres-concurrency-{uuid.uuid4()}"
    policy = AttemptLimit("integration", identity, 5, 60)

    def attempt(_):
        with Session(engine) as db:
            try:
                consume_attempts(db, [policy])
                return True
            except AuthRateLimited as exc:
                assert 1 <= exc.retry_after <= 60
                return False

    try:
        with ThreadPoolExecutor(max_workers=8) as workers:
            assert sum(workers.map(attempt, range(20))) == 5
    finally:
        # This CI database contains only disposable integration test data.
        with Session(engine) as db:
            db.execute(delete(AuthRateLimit))
            db.commit()


@pytest.mark.parametrize("scope", ["user", "project"])
def test_postgres_ai_budgets_are_atomic(monkeypatch, scope):
    monkeypatch.setattr(ai_usage.time, "time", lambda: 172800.0)
    monkeypatch.setattr(settings, "ai_user_daily_limit", 5 if scope == "user" else 100)
    monkeypatch.setattr(settings, "ai_project_daily_limit", 5 if scope == "project" else 100)
    monkeypatch.setattr(settings, "ai_user_minute_limit", 100)
    monkeypatch.setattr(settings, "ai_project_minute_limit", 100)
    user = uuid.uuid4()

    def attempt(_):
        with Session(engine) as db:
            try:
                ai_usage.consume_generation(db, user if scope == "user" else uuid.uuid4())
                return True
            except ai_usage.AIUsageLimited:
                return False

    try:
        with ThreadPoolExecutor(max_workers=8) as workers:
            assert sum(workers.map(attempt, range(20))) == 5
    finally:
        with Session(engine) as db:
            db.execute(delete(AIUsageBucket))
            db.commit()
