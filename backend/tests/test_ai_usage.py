import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import AIUsageBucket, Answer, FlashcardSet, Question, Quiz
from app.services import ai_usage as limiter
from app.services.llm.base import LLMProviderError, LLMProviderRateLimited, LLMResponse
from auth_helpers import authenticated_client
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker


class StubProvider:
    provider_name = "groq"

    def __init__(self):
        self.calls = 0
        self.error = None

    def generate_answer(self, request):
        self.calls += 1
        if self.error:
            raise self.error
        if request.question.startswith("Generate a quiz"):
            return LLMResponse(json.dumps({"title": "Quiz", "questions": [{
                "question": "What does binary search do?", "explanation": "It halves arrays.",
                "options": [{"text": "Halves", "is_correct": True},
                            {"text": "Doubles", "is_correct": False}],
            }]}))
        if request.question.startswith("Generate flashcards"):
            return LLMResponse(json.dumps({"title": "Cards", "cards": [{
                "front": "What does binary search do?", "back": "Halves sorted arrays.",
            }]}))
        return LLMResponse("Binary search halves sorted arrays. [1]")


@pytest.fixture
def usage_app(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'ai.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(limiter.time, "time", lambda: 172800.0)
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "ai_user_daily_limit", 3)
    monkeypatch.setattr(settings, "ai_user_minute_limit", 10)
    monkeypatch.setattr(settings, "ai_project_daily_limit", 20)
    monkeypatch.setattr(settings, "ai_project_minute_limit", 20)
    monkeypatch.setattr(settings, "auth_client_ip_source", "direct")

    def database():
        with sessions() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_db] = database
    provider = StubProvider()
    for module in ["answer_orchestrator", "quiz_generation", "flashcard_generation"]:
        monkeypatch.setattr(f"app.services.{module}.get_llm_provider", lambda: provider)
    yield app, sessions, provider
    engine.dispose()


def course(client, user_id):
    response = client.post(f"/users/{user_id}/courses", json={"title": "Algorithms"})
    assert response.status_code == 201
    course_id = response.json()["id"]
    assert client.post(f"/courses/{course_id}/documents/text", files={
        "file": ("notes.txt", b"Binary search halves sorted arrays to find values.", "text/plain"),
    }).status_code == 201
    return course_id


def generate(client, course_id, kind="questions"):
    payload = {"question": "What is binary search?"} if kind == "questions" else {
        "topic": "binary search", "question_count": 1, "card_count": 1,
    }
    return client.post(f"/courses/{course_id}/{kind}", json=payload)


def test_generation_types_and_courses_share_user_budget(usage_app):
    app, sessions, provider = usage_app
    with authenticated_client(app) as client:
        user_id = client.get("/auth/me").json()["id"]
        first, second = course(client, user_id), course(client, user_id)
        assert generate(client, first).status_code == 200
        assert generate(client, second, "quizzes").status_code == 201
        assert generate(client, first, "flashcard-sets").status_code == 201
        usage = client.get("/auth/ai-usage")
        assert usage.headers["Cache-Control"] == "no-store"
        assert usage.json()["day"] == {
            "limit": 3, "remaining": 0, "used": 3, "resets_at": "1970-01-04T00:00:00Z",
        }
        for kind in ["questions", "quizzes", "flashcard-sets"]:
            response = generate(client, second, kind)
            assert response.status_code == 429
            assert response.headers["Retry-After"] == "86400"
            assert response.headers["Cache-Control"] == "no-store"
            assert "today" in response.json()["detail"]
        assert client.get(f"/courses/{first}/questions").status_code == 200
        assert client.post("/auth/logout").status_code == 204
    assert provider.calls == 3
    with sessions() as db:
        assert [db.scalar(select(func.count()).select_from(model))
                for model in [Question, Answer, Quiz, FlashcardSet]] == [1, 1, 1, 1]
        assert [row.attempts for row in db.scalars(select(AIUsageBucket))] == [3, 3, 3, 3]


def test_invalid_unauthorized_and_insufficient_requests_use_no_budget(usage_app):
    app, sessions, provider = usage_app
    with authenticated_client(app) as owner:
        course_id = course(owner, owner.get("/auth/me").json()["id"])
        with authenticated_client(app, email="other@example.com") as other:
            assert generate(other, course_id).status_code == 404
            assert other.get("/auth/ai-usage").json()["day"]["used"] == 0
        assert owner.post(f"/courses/{course_id}/questions", json={}).status_code == 422
        for kind in ["questions", "quizzes", "flashcard-sets"]:
            key = "question" if kind == "questions" else "topic"
            response = owner.post(f"/courses/{course_id}/{kind}", json={key: "photosynthesis"})
            assert response.json()["status"] == "insufficient_evidence"
        assert owner.get("/auth/ai-usage").json()["day"]["used"] == 0
    with TestClient(app) as anonymous:
        assert generate(anonymous, course_id).status_code == 401
        assert anonymous.get("/auth/ai-usage").status_code == 401
    assert provider.calls == 0
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(AIUsageBucket)) == 0


@pytest.mark.parametrize("kind", ["questions", "quizzes", "flashcard-sets"])
@pytest.mark.parametrize("error,status", [(LLMProviderError("Provider failed"), 502),
                                         (LLMProviderRateLimited(120), 429)])
def test_provider_failures_count_and_throttling_is_clear(usage_app, kind, error, status):
    app, _, provider = usage_app
    provider.error = error
    with authenticated_client(app) as client:
        course_id = course(client, client.get("/auth/me").json()["id"])
        response = generate(client, course_id, kind)
        assert response.status_code == status
        if status == 429:
            assert response.headers["Retry-After"] == "120"
            assert "provider" in response.json()["detail"]
        assert client.get("/auth/ai-usage").json()["day"]["used"] == 1
    assert provider.calls == 1


def test_fake_provider_does_not_consume_budget(usage_app, monkeypatch):
    app, sessions, provider = usage_app
    monkeypatch.setattr(settings, "llm_provider", "fake")
    provider.provider_name = "fake"
    with authenticated_client(app) as client:
        course_id = course(client, client.get("/auth/me").json()["id"])
        for _ in range(4):
            assert generate(client, course_id).status_code == 200
        assert client.get("/auth/ai-usage").json()["enabled"] is False
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(AIUsageBucket)) == 0


def test_storage_failure_blocks_provider_without_leaking_details(usage_app, monkeypatch):
    app, _, provider = usage_app
    with authenticated_client(app) as client:
        course_id = course(client, client.get("/auth/me").json()["id"])
        original = Session._execute_internal

        def fail_buckets(self, statement, *args, **kwargs):
            if "ai_usage_buckets" in str(statement):
                raise OperationalError("statement", {}, Exception("private connection detail"))
            return original(self, statement, *args, **kwargs)

        monkeypatch.setattr(Session, "_execute_internal", fail_buckets)
        for kind in ["questions", "quizzes", "flashcard-sets"]:
            response = generate(client, course_id, kind)
            assert response.status_code == 503
            assert response.headers["Retry-After"] == "30"
            assert "private" not in response.text
        assert client.get("/auth/ai-usage").status_code == 503
    assert provider.calls == 0


def test_minute_and_daily_expiry_and_rollback_of_other_budgets(usage_app, monkeypatch):
    _, sessions, _ = usage_app
    monkeypatch.setattr(settings, "ai_user_minute_limit", 1)
    user = uuid.uuid4()
    with sessions() as db:
        limiter.consume_generation(db, user)
        monkeypatch.setattr(limiter.time, "time", lambda: 172859.1)
        with pytest.raises(limiter.AIUsageLimited) as exc:
            limiter.consume_generation(db, user)
        assert exc.value.retry_after == 1
        assert all(row.attempts == 1 for row in db.scalars(select(AIUsageBucket)))
        for now in [172860.0, 172920.0]:
            monkeypatch.setattr(limiter.time, "time", lambda now=now: now)
            limiter.consume_generation(db, user)
        monkeypatch.setattr(limiter.time, "time", lambda: 172980.0)
        with pytest.raises(limiter.AIUsageLimited) as exc:
            limiter.consume_generation(db, user)
        assert exc.value.retry_after == 86220
        monkeypatch.setattr(limiter.time, "time", lambda: 259200.0)
        limiter.consume_generation(db, user)
        assert limiter.get_ai_usage(db, user).day.used == 1


def test_shared_project_budget_and_user_isolation(usage_app, monkeypatch):
    _, sessions, _ = usage_app
    monkeypatch.setattr(settings, "ai_project_daily_limit", 2)
    first, second, third = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with sessions() as db:
        limiter.consume_generation(db, first)
        assert limiter.get_ai_usage(db, second).day.used == 0
        limiter.consume_generation(db, second)
        with pytest.raises(limiter.AIUsageLimited, match="shared"):
            limiter.consume_generation(db, third)
        assert limiter.get_ai_usage(db, third).day.used == 0
        assert db.scalar(select(func.count()).select_from(AIUsageBucket)) == 6


def test_project_minute_limit_does_not_spend_other_users_allowance(usage_app, monkeypatch):
    _, sessions, _ = usage_app
    monkeypatch.setattr(settings, "ai_project_minute_limit", 1)
    first, second = uuid.uuid4(), uuid.uuid4()
    with sessions() as db:
        limiter.consume_generation(db, first)
        with pytest.raises(limiter.AIUsageLimited, match="shared") as exc:
            limiter.consume_generation(db, second)
        assert exc.value.retry_after == 60
        assert limiter.get_ai_usage(db, second).day.used == 0
        monkeypatch.setattr(limiter.time, "time", lambda: 172860.0)
        limiter.consume_generation(db, second)
        assert limiter.get_ai_usage(db, second).day.used == 1


@pytest.mark.parametrize("scope", ["user", "project"])
def test_concurrent_sessions_admit_only_budget(usage_app, monkeypatch, scope):
    _, sessions, _ = usage_app
    monkeypatch.setattr(settings, "ai_user_daily_limit", 5 if scope == "user" else 100)
    monkeypatch.setattr(settings, "ai_project_daily_limit", 5 if scope == "project" else 100)
    monkeypatch.setattr(settings, "ai_project_minute_limit", 100)
    user = uuid.uuid4()

    def attempt(_):
        with sessions() as db:
            try:
                limiter.consume_generation(db, user if scope == "user" else uuid.uuid4())
                return True
            except limiter.AIUsageLimited:
                return False

    with ThreadPoolExecutor(max_workers=8) as workers:
        assert sum(workers.map(attempt, range(20))) == 5


def test_expired_cleanup_is_bounded(usage_app):
    _, sessions, _ = usage_app
    with sessions() as db:
        db.add_all([AIUsageBucket(bucket_key=f"{i:064x}", attempts=1, expires_at=0)
                    for i in range(105)])
        db.commit()
        limiter.consume_generation(db, uuid.uuid4())
        assert db.scalar(select(func.count()).select_from(AIUsageBucket)) == 9
