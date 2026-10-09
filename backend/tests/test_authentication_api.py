import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import AuthSession, User
from app.services.auth import hash_token, password_hasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def auth_client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            yield client, sessions
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def register(client, email="student@example.com"):
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "display_name": "Student",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def headers(session):
    return {"Authorization": f"Bearer {session['access_token']}"}


def test_registration_stores_only_password_and_token_hashes(auth_client):
    client, sessions = auth_client
    response = client.post(
        "/auth/register",
        json={
            "email": " Student@Example.com ",
            "display_name": " Student ",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    session = response.json()
    assert session["user"]["email"] == "student@example.com"
    assert session["user"]["display_name"] == "Student"
    assert session["user"]["is_admin"] is False
    assert "password" not in session["user"]
    assert "password_hash" not in session["user"]
    assert datetime.fromisoformat(session["expires_at"]).replace(tzinfo=UTC) > datetime.now(UTC)
    with sessions() as db:
        user = db.get(User, uuid.UUID(session["user"]["id"]))
        assert user.password_hash.startswith("$argon2id$")
        assert password_hasher.verify(PASSWORD, user.password_hash)
        persisted = db.scalar(select(AuthSession))
        assert persisted.token_hash == hash_token(session["access_token"])
        assert persisted.token_hash != session["access_token"]
    me = client.get("/auth/me", headers=headers(session))
    assert me.status_code == 200
    assert me.json() == session["user"]


@pytest.mark.parametrize("password", ["short", "x" * 129])
def test_registration_rejects_invalid_password_length(auth_client, password):
    client, _ = auth_client
    for path in ["/auth/register", "/users"]:
        assert (
            client.post(
                path,
                json={
                    "email": "student@example.com",
                    "display_name": "Student",
                    "password": password,
                },
            ).status_code
            == 422
        )


def test_passwordless_registration_and_admin_escalation_are_rejected(auth_client):
    client, _ = auth_client
    for path in ["/users", "/auth/register"]:
        payload = {"email": "student@example.com", "display_name": "Student"}
        assert client.post(path, json=payload).status_code == 422
        payload.update(password=PASSWORD, is_admin=True)
        assert client.post(path, json=payload).status_code == 422


def test_login_normalizes_email_and_hides_unknown_accounts(auth_client):
    client, _ = auth_client
    register(client)
    response = client.post(
        "/auth/login",
        json={
            "email": " STUDENT@EXAMPLE.COM ",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    failures = [
        client.post("/auth/login", json={"email": email, "password": "wrong"})
        for email in ["student@example.com", "missing@example.com"]
    ]
    assert all(response.status_code == 401 for response in failures)
    assert failures[0].json() == failures[1].json()


def test_legacy_accounts_cannot_be_claimed_by_email(auth_client):
    client, sessions = auth_client
    with sessions() as db:
        db.add(User(email="student@example.com", display_name="Legacy"))
        db.commit()
    assert (
        client.post(
            "/auth/login",
            json={
                "email": "student@example.com",
                "password": PASSWORD,
            },
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/register",
            json={
                "email": "student@example.com",
                "display_name": "Attacker",
                "password": PASSWORD,
            },
        ).status_code
        == 409
    )
    with sessions() as db:
        assert db.scalar(select(User)).password_hash is None


@pytest.mark.parametrize(
    "authorization", [None, "Basic secret", "Bearer forged", "Bearer " + "x" * 300]
)
def test_missing_and_invalid_tokens_are_rejected(auth_client, authorization):
    client, _ = auth_client
    response = client.get(
        "/auth/me", headers={"Authorization": authorization} if authorization else {}
    )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_expired_session_is_rejected(auth_client):
    client, sessions = auth_client
    session = register(client)
    with sessions() as db:
        db.scalar(select(AuthSession)).expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert client.get("/auth/me", headers=headers(session)).status_code == 401


def test_logout_revokes_only_the_current_session(auth_client):
    client, sessions = auth_client
    first = register(client)
    second = client.post(
        "/auth/login",
        json={
            "email": "student@example.com",
            "password": PASSWORD,
        },
    ).json()
    assert client.post("/auth/logout", headers=headers(first)).status_code == 204
    assert client.get("/auth/me", headers=headers(first)).status_code == 401
    assert client.post("/auth/logout", headers=headers(first)).status_code == 401
    assert client.get("/auth/me", headers=headers(second)).status_code == 200
    with sessions() as db:
        assert len(db.scalars(select(AuthSession)).all()) == 1


def private_endpoints():
    return [
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        for method in methods
        if not path.startswith("/auth/")
        and path not in {"/health", "/ready"}
        and not (path == "/users" and method == "post")
    ]


@pytest.mark.parametrize(("method", "path"), private_endpoints())
def test_every_private_endpoint_requires_authentication(auth_client, method, path):
    client, _ = auth_client
    for parameter in [
        "user_id",
        "course_id",
        "document_id",
        "question_id",
        "answer_id",
        "quiz_id",
        "attempt_id",
        "flashcard_set_id",
    ]:
        path = path.replace("{" + parameter + "}", str(uuid.uuid4()))
    response = client.request(method, path, params={"query": "binary"}, json={})
    assert response.status_code == 401, (method, path, response.text)


def test_foreign_resources_are_hidden_and_cannot_be_modified(auth_client):
    client, sessions = auth_client
    owner = register(client, "owner@example.com")
    other = register(client, "other@example.com")
    owner_headers = headers(owner)
    other_headers = headers(other)
    user_id = owner["user"]["id"]
    course = client.post(
        f"/users/{user_id}/courses", headers=owner_headers, json={"title": "Private course"}
    ).json()
    course_id = course["id"]
    document = client.post(
        f"/courses/{course_id}/documents/text",
        headers=owner_headers,
        files={"file": ("notes.txt", b"Binary search halves sorted arrays.", "text/plain")},
    ).json()
    answer = client.post(
        f"/courses/{course_id}/questions",
        headers=owner_headers,
        json={"question": "What is binary search?"},
    ).json()
    quiz = client.post(
        f"/courses/{course_id}/quizzes",
        headers=owner_headers,
        json={"topic": "binary search", "question_count": 2},
    ).json()
    assert quiz["questions"]
    attempt = client.post(
        f"/quizzes/{quiz['id']}/attempts",
        headers=owner_headers,
        json={
            "answers": [
                {"question_id": q["id"], "selected_option_id": q["options"][0]["id"]}
                for q in quiz["questions"]
            ],
        },
    ).json()
    cards = client.post(
        f"/courses/{course_id}/flashcard-sets",
        headers=owner_headers,
        json={"topic": "binary search", "card_count": 2},
    ).json()
    paths = {
        "user_id": user_id,
        "course_id": course_id,
        "document_id": document["id"],
        "question_id": answer["question_id"],
        "answer_id": answer["answer_id"],
        "quiz_id": quiz["id"],
        "attempt_id": attempt["id"],
        "flashcard_set_id": cards["id"],
        "flashcard_id": cards["cards"][0]["id"],
    }
    for method, path in private_endpoints():
        if path.startswith("/admin"):
            continue
        for parameter, value in paths.items():
            path = path.replace("{" + parameter + "}", value)
        response = client.request(
            method, path, headers=other_headers, params={"query": "binary"}, json={}
        )
        assert response.status_code == 404, (method, path, response.text)
    assert client.get(f"/documents/{document['id']}", headers=owner_headers).status_code == 200
    # Admin privileges do not grant access to another student's coursework.
    with sessions() as db:
        db.get(User, uuid.UUID(other["user"]["id"])).is_admin = True
        db.commit()
    assert client.get(f"/courses/{course_id}", headers=other_headers).status_code == 404


def test_metrics_requires_admin_role_from_database(auth_client):
    client, sessions = auth_client
    session = register(client)
    auth = headers(session)
    assert client.get("/admin/metrics", headers=auth).status_code == 403

    with sessions() as db:
        db.get(User, uuid.UUID(session["user"]["id"])).is_admin = True
        db.commit()
    assert client.get("/admin/metrics", headers=auth).status_code == 200
    with sessions() as db:
        db.get(User, uuid.UUID(session["user"]["id"])).is_admin = False
        db.commit()
    assert client.get("/admin/metrics", headers=auth).status_code == 403


def test_operator_password_reset_revokes_all_sessions(auth_client, monkeypatch):
    from scripts import manage_account

    client, sessions = auth_client
    session = register(client)
    monkeypatch.setattr(manage_account, "SessionLocal", sessions)
    monkeypatch.setattr(
        "sys.argv", ["manage_account", "--email", "student@example.com", "--set-password"]
    )
    new_password = "replacement-password-long-enough"
    monkeypatch.setattr(manage_account.getpass, "getpass", lambda _: new_password)
    assert manage_account.main() == 0
    assert client.get("/auth/me", headers=headers(session)).status_code == 401
    assert (
        client.post(
            "/auth/login",
            json={
                "email": "student@example.com",
                "password": PASSWORD,
            },
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/login",
            json={
                "email": "student@example.com",
                "password": new_password,
            },
        ).status_code
        == 200
    )
