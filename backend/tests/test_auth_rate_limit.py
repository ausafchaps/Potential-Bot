from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import AuthRateLimit, AuthSession, User
from app.services import auth_rate_limit as limiter
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

PASSWORD = "test-password-long-enough"


@pytest.fixture
def limited_app(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'limits.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(settings, "auth_client_ip_source", "direct")
    monkeypatch.setattr(settings, "auth_login_ip_limit", 3)
    monkeypatch.setattr(settings, "auth_login_email_limit", 2)
    monkeypatch.setattr(settings, "auth_login_window_seconds", 60)
    monkeypatch.setattr(settings, "auth_signup_ip_limit", 2)
    monkeypatch.setattr(settings, "auth_signup_window_seconds", 60)
    monkeypatch.setattr(limiter.time, "time", lambda: 120.0)

    def database():
        with sessions() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_db] = database
    yield app, sessions
    engine.dispose()


def signup_payload(email="student@example.com"):
    return {"email": email, "display_name": "Student", "password": PASSWORD}


def login(client, email="student@example.com", password="wrong", **kwargs):
    return client.post("/auth/login", json={"email": email, "password": password}, **kwargs)


def test_signup_aliases_share_limit_and_block_before_hashing(limited_app, monkeypatch):
    app, sessions = limited_app
    with TestClient(app) as client:
        assert client.post("/auth/register", json=signup_payload()).status_code == 201
        assert client.post("/users", json=signup_payload("other@example.com")).status_code == 201
        hasher = Mock(side_effect=AssertionError("Must not hash blocked signup"))
        monkeypatch.setattr("app.services.user_course.hash_password", hasher)
        for path in ["/users", "/auth/register"]:
            response = client.post(path, json=signup_payload("third@example.com"))
            assert response.status_code == 429
            assert response.headers["Retry-After"] == "60"
            assert response.headers["Cache-Control"] == "no-store"
        hasher.assert_not_called()
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 2
        assert db.scalar(select(func.count()).select_from(AuthSession)) == 1
        rows = db.scalars(select(AuthRateLimit)).all()
        assert len(rows) == 1
        assert rows[0].attempts == 2
        assert len(rows[0].bucket_key) == 64


def test_failed_logins_share_normalized_email_limit_across_clients(limited_app, monkeypatch):
    app, sessions = limited_app
    with TestClient(app, client=("192.0.2.1", 1234)) as first:
        assert login(first, " Missing@Example.com ").status_code == 401
    with TestClient(app, client=("192.0.2.2", 1234)) as second:
        assert login(second, "missing@example.com").status_code == 401
    verify = Mock(side_effect=AssertionError("Blocked login must not verify passwords"))
    monkeypatch.setattr("app.api.routes.auth.authenticate", verify)
    with TestClient(app, client=("192.0.2.3", 1234)) as third:
        response = login(third, "MISSING@EXAMPLE.COM")
        assert response.status_code == 429
    verify.assert_not_called()
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(AuthSession)) == 0


def test_ip_limit_blocks_email_rotation_and_forged_forwarding_headers(limited_app):
    app, sessions = limited_app
    with TestClient(app, client=("192.0.2.1", 1234)) as client:
        for index in range(3):
            assert login(client, f"missing{index}@example.com").status_code == 401
        response = login(client, "fourth@example.com", headers={
            "X-Forwarded-For": "192.0.2.99",
            "X-Real-IP": "192.0.2.98",
            "X-Vercel-Forwarded-For": "192.0.2.97",
        })
        assert response.status_code == 429
        assert client.get("/health").status_code == 200
        assert client.get("/auth/me").status_code == 401
    with sessions() as db:
        # One IP and three emails; a blocked IP cannot create more email buckets.
        assert db.scalar(select(func.count()).select_from(AuthRateLimit)) == 4
    with TestClient(app, client=("192.0.2.2", 1234)) as other:
        assert login(other, "fourth@example.com").status_code == 401


def test_successful_logins_are_limited_and_logout_still_works(limited_app):
    app, _ = limited_app
    with TestClient(app) as client:
        assert client.post("/auth/register", json=signup_payload()).status_code == 201
        first = login(client, password=PASSWORD)
        assert first.status_code == 200
        assert login(client, password=PASSWORD).status_code == 200
        assert login(client, password=PASSWORD).status_code == 429
        headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
        assert client.get("/auth/me", headers=headers).status_code == 200
        assert client.post("/auth/logout", headers=headers).status_code == 204


def test_duplicate_and_invalid_signups_count_and_expiry_reopens_window(limited_app, monkeypatch):
    app, _ = limited_app
    with TestClient(app) as client:
        assert client.post("/users", json=signup_payload()).status_code == 201
        assert client.post("/auth/register", json=signup_payload()).status_code == 409
        monkeypatch.setattr(limiter.time, "time", lambda: 179.1)
        response = client.post("/users", json=signup_payload("second@example.com"))
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "1"
        # Blocked attempts do not push expiry forward.
        monkeypatch.setattr(limiter.time, "time", lambda: 180.0)
        assert client.post("/users", json={}).status_code == 422
        assert client.post("/users", json=signup_payload("second@example.com")).status_code == 201
        assert client.post("/auth/register", json=signup_payload()).status_code == 429


@pytest.mark.parametrize("header", [None, "invalid", "192.0.2.1, 192.0.2.2"])
def test_vercel_mode_requires_valid_platform_header(limited_app, monkeypatch, header):
    app, _ = limited_app
    monkeypatch.setattr(settings, "auth_client_ip_source", "vercel")
    with TestClient(app) as client:
        response = login(client, headers={"X-Vercel-Forwarded-For": header} if header else {})
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "30"


def test_vercel_mode_uses_platform_ip_and_canonicalizes_addresses(limited_app, monkeypatch):
    app, _ = limited_app
    monkeypatch.setattr(settings, "auth_client_ip_source", "vercel")
    with TestClient(app) as client:
        for index in range(3):
            assert login(client, f"missing{index}@example.com", headers={
                "X-Vercel-Forwarded-For": "::ffff:192.0.2.1",
                "X-Forwarded-For": f"192.0.2.{index + 10}",
            }).status_code == 401
        assert login(client, "fourth@example.com", headers={
            "X-Vercel-Forwarded-For": "192.0.2.1",
        }).status_code == 429
        assert login(client, "fourth@example.com", headers={
            "X-Vercel-Forwarded-For": "192.0.2.2",
        }).status_code == 401


def test_storage_failure_fails_closed_before_credentials(limited_app, monkeypatch):
    app, sessions = limited_app
    execute = Mock(side_effect=OperationalError("statement", {}, Exception("secret detail")))
    monkeypatch.setattr(Session, "execute", execute)
    with TestClient(app) as client:
        for path in ["/auth/login", "/auth/register", "/users"]:
            response = client.post(path, json=signup_payload())
            assert response.status_code == 503
            assert "secret detail" not in response.text
            assert response.headers["Cache-Control"] == "no-store"
        assert client.get("/health").status_code == 200
    monkeypatch.undo()
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0


def test_parallel_sessions_admit_exactly_limit(limited_app):
    _, sessions = limited_app
    policy = limiter.AttemptLimit("login-ip", "192.0.2.42", 5, 60)

    def attempt(_):
        with sessions() as db:
            try:
                limiter.consume_attempts(db, [policy])
                return True
            except limiter.AuthRateLimited:
                return False

    with ThreadPoolExecutor(max_workers=8) as workers:
        assert sum(workers.map(attempt, range(20))) == 5
    with sessions() as db:
        assert db.scalar(select(AuthRateLimit)).attempts == 5


def test_expired_bucket_cleanup_is_bounded(limited_app):
    _, sessions = limited_app
    with sessions() as db:
        db.add_all([
            AuthRateLimit(bucket_key=f"{index:064x}", attempts=1, expires_at=-100000)
            for index in range(105)
        ])
        db.commit()
        limiter.consume_attempts(db, [limiter.AttemptLimit("login-ip", "testclient", 3, 60)])
        assert db.scalar(select(func.count()).select_from(AuthRateLimit)) == 6


def test_retry_header_is_exposed_to_frontend(limited_app):
    app, _ = limited_app
    with TestClient(app) as client:
        for _ in range(2):
            login(client)
        response = login(client, headers={"Origin": "http://localhost:5173"})
        assert response.status_code == 429
        assert "Retry-After" in response.headers["Access-Control-Expose-Headers"]
