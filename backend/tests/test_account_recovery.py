import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit

import pytest
from app.core.config import settings
from app.models import AccountToken, AuthSession, User
from app.services import account_email, account_recovery
from app.services.account_recovery import InvalidAccountLink, consume_link, issue_link
from app.services.auth import CredentialsChanged, create_session, hash_token
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from test_authentication_api import PASSWORD, headers, register
from test_authentication_api import auth_client as auth_client

NEW_PASSWORD = "new-password-long-enough"


@pytest.fixture
def recovery(auth_client, monkeypatch):
    client, sessions = auth_client
    monkeypatch.setattr(settings, "email_provider", "smtp")
    monkeypatch.setattr(settings, "public_app_url", "https://studybot.example.com")
    monkeypatch.setattr(settings, "auth_email_ip_limit", 100)
    monkeypatch.setattr(settings, "auth_email_address_limit", 100)
    messages = []
    monkeypatch.setattr(account_email, "send_account_email", lambda *args: messages.append(args))
    yield client, sessions, messages


def token(messages, purpose):
    link = next(message[2] for message in reversed(messages) if message[1] == purpose)
    return parse_qs(urlsplit(link).fragment)[purpose][0]


def test_signup_verification_is_explicit_single_use_and_bound_to_purpose(recovery):
    client, sessions, messages = recovery
    session = register(client)
    assert session["user"]["email_verified"] is False
    code = token(messages, "verify")
    assert "#verify=" in messages[0][2]
    assert client.post("/auth/reset-password", json={"token": code,
                       "password": NEW_PASSWORD}).status_code == 400
    with sessions() as db:
        saved = db.get(AccountToken, hash_token(code))
        assert saved.token_hash != code and saved.consumed_at is None
        assert db.get(User, saved.user_id).email_verified is False
    assert client.post("/auth/verify-email", json={"token": code}).status_code == 200
    assert client.post("/auth/verify-email", json={"token": code}).status_code == 400
    assert client.get("/auth/me", headers=headers(session)).json()["email_verified"] is True


def test_reset_generic_response_changes_password_and_revokes_all_sessions(recovery):
    client, sessions, messages = recovery
    original = register(client)
    second = client.post("/auth/login", json={"email": "student@example.com",
                         "password": PASSWORD}).json()
    known = client.post("/auth/forgot-password", json={"email": " STUDENT@example.com "})
    code = token(messages, "reset")
    count = len(messages)
    unknown = client.post("/auth/forgot-password", json={"email": "missing@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json() and len(messages) == count
    assert code not in known.text
    assert client.post("/auth/reset-password", json={"token": code,
                       "password": "short"}).status_code == 422
    assert client.post("/auth/reset-password", json={"token": code,
                       "password": NEW_PASSWORD}).status_code == 200
    assert client.post("/auth/reset-password", json={"token": code,
                       "password": PASSWORD}).status_code == 400
    assert client.get("/auth/me", headers=headers(original)).status_code == 401
    assert client.get("/auth/me", headers=headers(second)).status_code == 401
    assert client.post("/auth/login", json={"email": "student@example.com",
                       "password": PASSWORD}).status_code == 401
    assert client.post("/auth/login", json={"email": "student@example.com",
                       "password": NEW_PASSWORD}).status_code == 200
    with sessions() as db:
        user = db.get(User, uuid.UUID(original["user"]["id"]))
        assert user.credential_version == 1
        assert user.email_verified is False


def test_expiry_old_links_and_legacy_accounts(recovery, monkeypatch):
    client, sessions, messages = recovery
    original = register(client)
    old_verify = token(messages, "verify")
    client.post("/auth/forgot-password", json={"email": "student@example.com"})
    code = token(messages, "reset")
    with sessions() as db:
        expiry = db.get(AccountToken, hash_token(code)).expires_at
    with monkeypatch.context() as patch:
        patch.setattr(account_recovery.time, "time", lambda: expiry)
        assert client.post("/auth/reset-password", json={"token": code,
                           "password": NEW_PASSWORD}).status_code == 400
    client.post("/auth/forgot-password", json={"email": "student@example.com"})
    second_code = token(messages, "reset")
    assert client.post("/auth/reset-password", json={"token": second_code,
                       "password": NEW_PASSWORD}).status_code == 200
    assert client.post("/auth/verify-email", json={"token": old_verify}).status_code == 400
    assert client.post("/auth/reset-password", json={"token": code,
                       "password": NEW_PASSWORD}).status_code == 400
    with sessions() as db:
        db.add(User(email="legacy@example.com", display_name="Legacy"))
        db.commit()
    before = len(messages)
    legacy = client.post("/auth/forgot-password", json={"email": "legacy@example.com"})
    assert legacy.status_code == 202
    assert len(messages) == before
    assert client.get("/auth/me", headers=headers(original)).status_code == 401


def test_delivery_disabled_and_shared_request_limits(recovery, monkeypatch):
    client, _, _ = recovery
    session = register(client)
    monkeypatch.setattr(settings, "email_provider", "disabled")
    assert client.get("/auth/capabilities").json()["account_email_enabled"] is False
    for email in ["student@example.com", "missing@example.com"]:
        assert client.post("/auth/forgot-password", json={"email": email}).status_code == 503
    monkeypatch.setattr(settings, "email_provider", "smtp")
    monkeypatch.setattr(settings, "auth_email_address_limit", 1)
    # Signup and manual resend share the address budget.
    result = client.post("/auth/resend-verification", headers=headers(session))
    assert result.status_code == 429 and int(result.headers["retry-after"]) > 0
    blocked = client.post("/auth/forgot-password", json={"email": "student@example.com"})
    assert blocked.status_code == 429
    assert client.post("/auth/resend-verification").status_code == 401


def test_required_verification_retains_account_access_and_unblocks_workspace(recovery, monkeypatch):
    client, _, messages = recovery
    monkeypatch.setattr(settings, "auth_require_email_verification", True)
    session = register(client)
    auth = headers(session)
    assert client.get("/auth/me", headers=auth).status_code == 200
    assert client.get(f"/users/{session['user']['id']}/courses", headers=auth).status_code == 403
    assert client.post("/auth/resend-verification", headers=auth).status_code == 202
    verified = client.post("/auth/verify-email", json={"token": token(messages, "verify")})
    assert verified.status_code == 200
    assert client.get(f"/users/{session['user']['id']}/courses", headers=auth).status_code == 200


def test_stale_login_cannot_create_session_after_reset(recovery):
    client, sessions, messages = recovery
    original = register(client)
    client.post("/auth/forgot-password", json={"email": "student@example.com"})
    code = token(messages, "reset")
    with sessions() as old_login:
        user = old_login.get(User, uuid.UUID(original["user"]["id"]))
        assert user.password_hash
        with sessions() as reset:
            consume_link(reset, code, "reset", NEW_PASSWORD)
        with pytest.raises(CredentialsChanged):
            create_session(old_login, user)
    with sessions() as db:
        assert db.scalar(select(AuthSession)) is None


def test_link_cannot_verify_a_changed_email_and_failures_roll_back(recovery, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    client, sessions, messages = recovery
    session = register(client)
    code = token(messages, "verify")
    user_id = uuid.UUID(session["user"]["id"])
    with sessions() as db:
        user = db.get(User, user_id)
        user.email = "changed@example.com"
        db.commit()
    assert client.post("/auth/verify-email", json={"token": code}).status_code == 400
    with sessions() as db:
        user = db.get(User, user_id)
        user.email = "student@example.com"
        db.commit()

    def unavailable(_):
        raise SQLAlchemyError("private database details")

    with monkeypatch.context() as patch:
        # Link throttling commits first, so fail only the token-consumption commit.
        original = Session.commit
        commits = []
        def commit(db):
            commits.append(1)
            if len(commits) > 1:
                return unavailable(db)
            return original(db)
        patch.setattr(Session, "commit", commit)
        result = client.post("/auth/verify-email", json={"token": code})
    assert result.status_code == 503 and "private database details" not in result.text
    with sessions() as db:
        assert db.get(User, user_id).email_verified is False
        assert db.get(AccountToken, hash_token(code)).consumed_at is None


@pytest.mark.parametrize("same_token", [True, False])
def test_concurrent_resets_allow_exactly_one_new_password(recovery, tmp_path, same_token):
    client, sessions, messages = recovery
    original = register(client)
    with sessions() as db:
        user = db.get(User, uuid.UUID(original["user"]["id"]))
        codes = [parse_qs(urlsplit(issue_link(db, user, "reset")).fragment)["reset"][0]
                 for _ in range(2)]
    source = sessions.kw["bind"]
    destination = create_engine(f"sqlite:///{tmp_path / 'reset.db'}")
    with source.connect() as src, destination.connect() as dst:
        src.connection.driver_connection.backup(dst.connection.driver_connection)

    def reset(i):
        with Session(destination) as db:
            try:
                consume_link(db, codes[0 if same_token else i % 2], "reset", NEW_PASSWORD)
                return True
            except InvalidAccountLink:
                return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(reset, range(8))) == 1
    with Session(destination) as db:
        assert db.get(User, uuid.UUID(original["user"]["id"])).credential_version == 1
        assert db.scalar(select(AuthSession)) is None
    destination.dispose()
