"""Exercise the same HTTP transport as the deployment runner against the real API."""
import importlib.util
import json
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import User
from app.services.llm.base import LLMResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

spec = importlib.util.spec_from_file_location(
    "staging_smoke", Path(__file__).resolve().parents[2] / "scripts/staging_smoke.py")
smoke = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = smoke
spec.loader.exec_module(smoke)


@pytest.fixture
def smoke_api(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def enable_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    app = create_app()
    def override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override
    monkeypatch.setattr("app.api.routes.health.check_database_connection", lambda: None)
    monkeypatch.setattr(settings, "email_provider", "disabled")
    monkeypatch.setattr(settings, "auth_require_email_verification", False)
    api = TestClient(app, raise_server_exceptions=False)
    yield api, sessions
    api.close()
    engine.dispose()


@pytest.fixture
def local_server(smoke_api):
    api, sessions = smoke_api
    with serve_api(api) as base_url:
        yield base_url, sessions


@contextmanager
def serve_api(api):
    class Handler(BaseHTTPRequestHandler):
        def dispatch(self):
            length = int(self.headers.get("Content-Length", 0))
            response = api.request(self.command, self.path,
                                   headers=dict(self.headers),
                                   content=self.rfile.read(length), follow_redirects=False)
            self.send_response(response.status_code)
            for name, value in response.headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(response.content)

        do_GET = do_POST = do_DELETE = dispatch

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def assert_no_students(sessions):
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0
        # Cascades remove every study/auth table. Only shared limit/lock rows remain.
        for table in Base.metadata.sorted_tables:
            if table.name not in {"ai_usage_buckets", "auth_rate_limits", "storage_lock"}:
                assert db.scalar(select(func.count()).select_from(table)) == 0, table.name


def test_complete_deployment_smoke_over_http(local_server):
    base_url, sessions = local_server
    result = smoke.run_smoke_test(base_url, allow_fake_ai=True)
    assert result["accounts_removed"] == 2
    assert result["generation_requests"] == 3
    assert_no_students(sessions)


def test_failed_generation_cleans_up_both_accounts(local_server, monkeypatch):
    base_url, sessions = local_server
    original = smoke.SmokeClient.request
    def fail(self, path, **kwargs):
        if path.endswith("/quizzes") and kwargs.get("method") == "POST":
            raise smoke.SmokeTestError("Simulated provider failure")
        return original(self, path, **kwargs)
    monkeypatch.setattr(smoke.SmokeClient, "request", fail)
    with pytest.raises(smoke.SmokeTestError, match="Simulated provider failure"):
        smoke.run_smoke_test(base_url, allow_fake_ai=True)
    assert_no_students(sessions)


@pytest.mark.parametrize("limit", [2, 3])
def test_metered_generations_and_budget_rejection_over_http(local_server, monkeypatch, limit):
    base_url, sessions = local_server
    class Provider:
        provider_name = "groq"
        calls = 0

        def generate_answer(self, request):
            self.calls += 1
            if request.question.startswith("Generate a quiz"):
                return LLMResponse(json.dumps({"title": "Recall quiz", "questions": [{
                    "question": f"What improves memory? {i}", "explanation": "Repeated recall.",
                    "options": [{"text": "Spaced repetition", "is_correct": True},
                                {"text": "No review", "is_correct": False}],
                } for i in range(3)]}))
            if request.question.startswith("Generate flashcards"):
                return LLMResponse(json.dumps({"title": "Recall cards", "cards": [{
                    "front": f"What improves memory? {i}", "back": "Spaced repetition",
                } for i in range(3)]}))
            return LLMResponse("Spaced repetition and active recall improve memory. [1]")

    provider = Provider()
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "ai_user_daily_limit", limit)
    for module in ("answer_orchestrator", "quiz_generation", "flashcard_generation"):
        monkeypatch.setattr(f"app.services.{module}.get_llm_provider", lambda: provider)
    if limit == 2:
        with pytest.raises(smoke.SmokeTestError, match="received 429"):
            smoke.run_smoke_test(base_url)
    else:
        assert smoke.run_smoke_test(base_url)["generation_requests"] == 3
    assert provider.calls == limit
    assert_no_students(sessions)


def test_wrong_revision_does_not_register(local_server):
    base_url, sessions = local_server
    with pytest.raises(smoke.SmokeTestError, match="expected healthy revision"):
        smoke.run_smoke_test(base_url, expected_revision="a" * 40, allow_fake_ai=True)
    assert_no_students(sessions)


@pytest.mark.parametrize("url", ["https://evil.example", "http://studybot-staging.vercel.app",
                                 "https://user:secret@studybot-staging.vercel.app",
                                 "https://studybot-staging.vercel.app/path",
                                 "https://studybot-staging.vercel.app?secret=1"])
def test_runner_rejects_untrusted_urls(url):
    with pytest.raises(smoke.SmokeTestError):
        smoke.SmokeClient(url)


def test_remote_cannot_bypass_real_ai_check():
    with pytest.raises(smoke.SmokeTestError, match="only allowed on local"):
        smoke.run_smoke_test(smoke.STAGING_URL, allow_fake_ai=True)


def test_email_enabled_stops_before_signup(local_server, monkeypatch):
    base_url, sessions = local_server
    monkeypatch.setattr(settings, "email_provider", "smtp")
    with pytest.raises(smoke.SmokeTestError, match="email and verification"):
        smoke.run_smoke_test(base_url, allow_fake_ai=True)
    assert_no_students(sessions)


def test_account_deletion_requires_session_password_and_explicit_confirmation(smoke_api):
    api, sessions = smoke_api
    password = "a-long-enough-password"
    first = api.post("/auth/register", json={"email": "first@example.com", "password": password,
                                             "display_name": "First"}).json()
    second = api.post("/auth/register", json={"email": "second@example.com", "password": password,
                                              "display_name": "Second"}).json()
    payload = {"password": password, "confirmation": "delete-my-account"}
    assert api.request("DELETE", "/auth/account", json=payload).status_code == 401
    headers = {"Authorization": f"Bearer {first['access_token']}"}
    assert api.request("DELETE", "/auth/account", headers=headers,
                       json={"password": password}).status_code == 422
    assert api.request("DELETE", "/auth/account", headers=headers,
                       json={**payload, "user_id": second["user"]["id"]}).status_code == 422
    assert api.request("DELETE", "/auth/account", headers=headers,
                       json={**payload, "password": "wrong"}).status_code == 403
    assert api.get("/auth/me", headers=headers).status_code == 200
    response = api.request("DELETE", "/auth/account", headers=headers, json=payload)
    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"
    assert api.get("/auth/me", headers=headers).status_code == 401
    assert api.get("/auth/me", headers={
        "Authorization": f"Bearer {second['access_token']}"}).status_code == 200
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1


def test_account_deletion_password_attempts_are_bounded(smoke_api):
    api, _ = smoke_api
    session = api.post("/auth/register", json={"email": "attempts@example.com",
                       "password": "a-long-enough-password", "display_name": "Student"}).json()
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    for _ in range(5):
        assert api.request("DELETE", "/auth/account", headers=headers, json={
            "password": "wrong", "confirmation": "delete-my-account"}).status_code == 403
    blocked = api.request("DELETE", "/auth/account", headers=headers, json={
        "password": "a-long-enough-password", "confirmation": "delete-my-account"})
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0


def test_admin_account_cannot_be_deleted(smoke_api):
    import uuid

    api, sessions = smoke_api
    session = api.post("/auth/register", json={"email": "admin@example.com",
                       "password": "a-long-enough-password", "display_name": "Admin"}).json()
    with sessions() as db:
        db.get(User, uuid.UUID(session["user"]["id"])).is_admin = True
        db.commit()
    response = api.request("DELETE", "/auth/account", headers={
        "Authorization": f"Bearer {session['access_token']}"}, json={
        "password": "a-long-enough-password", "confirmation": "delete-my-account"})
    assert response.status_code == 403


def test_http_transport_refuses_redirects_and_redacts_response_bodies(smoke_api):
    from fastapi.responses import JSONResponse, RedirectResponse

    api, _ = smoke_api
    forwarded = []
    api.app.add_api_route("/redirect", lambda: RedirectResponse("/target", status_code=307),
                          methods=["POST"])
    api.app.add_api_route("/target", lambda: forwarded.append(True), methods=["POST"])
    api.app.add_api_route("/failure", lambda: JSONResponse({"secret": "private-response"},
                                                           status_code=500))
    with serve_api(api) as base_url:
        client = smoke.SmokeClient(base_url)
        with pytest.raises(smoke.SmokeTestError, match="received 307"):
            client.request("/redirect", method="POST", token="private-token",
                           payload={"password": "private-password"})
        with pytest.raises(smoke.SmokeTestError) as failure:
            client.request("/failure")
    assert "private-response" not in str(failure.value)
    assert not forwarded


def test_deletion_refuses_stale_credentials_and_disabled_foreign_keys(smoke_api, monkeypatch):
    from types import SimpleNamespace

    from app.services import account_deletion
    from app.services.auth import hash_password
    from app.services.storage import StorageUnavailable
    from sqlalchemy import update

    _, sessions = smoke_api
    with sessions() as db:
        user = User(email="stale@example.com", display_name="Student",
                    password_hash=hash_password("a-long-enough-password"))
        db.add(user)
        db.commit()
        user_id = user.id
        def credentials_change(password, hashed):
            db.execute(update(User).where(User.id == user_id).values(credential_version=1),
                       execution_options={"synchronize_session": False})
            return True
        monkeypatch.setattr(account_deletion, "password_hasher",
                            SimpleNamespace(verify=credentials_change))
        with pytest.raises(account_deletion.AccountDeletionDenied):
            account_deletion.delete_own_account(db, user, "a-long-enough-password")
        assert db.get(User, user_id) is not None
        monkeypatch.setattr(account_deletion, "password_hasher",
                            SimpleNamespace(verify=lambda *_: True))
        db.commit()
        db.connection().exec_driver_sql("PRAGMA foreign_keys=OFF")
        with pytest.raises(StorageUnavailable):
            account_deletion.delete_own_account(db, user, "a-long-enough-password")
        assert db.get(User, user_id) is not None


def test_deletion_commit_failure_rolls_back_account_and_study_data(smoke_api, monkeypatch):
    import uuid

    from app.models import Course, Document
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session

    api, sessions = smoke_api
    password = "a-long-enough-password"
    session = api.post("/auth/register", json={"email": "rollback@example.com",
                       "password": password, "display_name": "Student"}).json()
    user_id = uuid.UUID(session["user"]["id"])
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    course = api.post(f"/users/{user_id}/courses", headers=headers,
                      json={"title": "Keep my notes"}).json()
    assert api.post(f"/courses/{course['id']}/documents/text", headers=headers,
                    files={"file": ("notes.txt", smoke.NOTES, "text/plain")}).status_code == 201
    original = Session.commit
    def fail_after_delete(db):
        if db.scalar(select(User).where(User.id == user_id)) is None:
            raise OperationalError("commit", {}, Exception("private-db-information"))
        return original(db)
    monkeypatch.setattr(Session, "commit", fail_after_delete)
    response = api.request("DELETE", "/auth/account", headers=headers,
                           json={"password": password, "confirmation": "delete-my-account"})
    assert response.status_code == 503
    assert "private-db-information" not in response.text
    with sessions() as db:
        assert db.get(User, user_id) is not None
        assert db.scalar(select(func.count()).select_from(Course)) == 1
        assert db.scalar(select(func.count()).select_from(Document)) == 1
