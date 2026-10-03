"""Explicit authenticated setup shared by the existing learning-flow tests."""

from app.models import User
from app.services.auth import hash_password
from fastapi.testclient import TestClient

TEST_PASSWORD = "test-password-long-enough"
TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)


def sign_in(client: TestClient, email: str) -> None:
    response = client.post("/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


def register_user(client: TestClient, *, json: dict):
    response = client.post("/users", json={**json, "password": TEST_PASSWORD})
    if response.status_code == 201:
        sign_in(client, json["email"])
    return response


def authenticated_client(app, *, email: str = "fixture@example.com", admin=False) -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "display_name": "Test account",
            "password": TEST_PASSWORD,
        },
    )
    if response.status_code == 409:
        sign_in(client, email)
    else:
        assert response.status_code == 201, response.text
        client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    if admin:
        from app.db.session import get_db

        dependency = app.dependency_overrides.get(get_db, get_db)
        generator = dependency()
        db = next(generator)
        try:
            from sqlalchemy import select

            user = db.scalar(select(User).where(User.email == email))
            user.is_admin = True
            db.commit()
        finally:
            generator.close()
    return client
