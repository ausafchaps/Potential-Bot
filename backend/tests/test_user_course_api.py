import uuid
from collections.abc import Generator

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def build_client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_create_and_get_user() -> None:
    client = build_client()

    try:
        create_response = client.post(
            "/users",
            json={"email": " Student@Example.com ", "display_name": " Student "},
        )

        assert create_response.status_code == 201
        created_user = create_response.json()
        assert uuid.UUID(created_user["id"])
        assert created_user["email"] == "student@example.com"
        assert created_user["display_name"] == "Student"

        get_response = client.get(f"/users/{created_user['id']}")

        assert get_response.status_code == 200
        assert get_response.json()["id"] == created_user["id"]
    finally:
        app.dependency_overrides.clear()


def test_create_user_rejects_duplicate_email() -> None:
    client = build_client()

    try:
        first_response = client.post(
            "/users",
            json={"email": "student@example.com", "display_name": "Student"},
        )
        duplicate_response = client.post(
            "/users",
            json={"email": "STUDENT@example.com", "display_name": "Student Two"},
        )

        assert first_response.status_code == 201
        assert duplicate_response.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_create_and_list_courses_for_user() -> None:
    client = build_client()

    try:
        user_response = client.post(
            "/users",
            json={"email": "student@example.com", "display_name": "Student"},
        )
        user_id = user_response.json()["id"]

        course_response = client.post(
            f"/users/{user_id}/courses",
            json={"title": " Algorithms ", "description": " Search and graphs "},
        )

        assert course_response.status_code == 201
        created_course = course_response.json()
        assert uuid.UUID(created_course["id"])
        assert created_course["owner_id"] == user_id
        assert created_course["title"] == "Algorithms"
        assert created_course["description"] == "Search and graphs"

        list_response = client.get(f"/users/{user_id}/courses")
        get_response = client.get(f"/courses/{created_course['id']}")

        assert list_response.status_code == 200
        assert [course["id"] for course in list_response.json()] == [created_course["id"]]
        assert get_response.status_code == 200
        assert get_response.json()["id"] == created_course["id"]
    finally:
        app.dependency_overrides.clear()


def test_create_course_returns_404_for_missing_user() -> None:
    client = build_client()

    try:
        response = client.post(
            f"/users/{uuid.uuid4()}/courses",
            json={"title": "Algorithms"},
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_create_user_course_then_upload_text_document() -> None:
    client = build_client()

    try:
        user_response = client.post(
            "/users",
            json={"email": "student@example.com", "display_name": "Student"},
        )
        course_response = client.post(
            f"/users/{user_response.json()['id']}/courses",
            json={"title": "Algorithms"},
        )
        course_id = course_response.json()["id"]

        upload_response = client.post(
            f"/courses/{course_id}/documents/text",
            files={
                "file": (
                    "notes.txt",
                    b"Binary search halves sorted search spaces.",
                    "text/plain",
                )
            },
        )

        assert upload_response.status_code == 201
        assert upload_response.json()["course_id"] == course_id
        assert upload_response.json()["chunk_count"] == 1
    finally:
        app.dependency_overrides.clear()

