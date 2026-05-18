import uuid
from collections.abc import Generator

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Course, Document, DocumentChunk, DocumentStatus, User
from app.services.text_ingestion import chunk_text, estimate_token_count
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def build_test_db() -> tuple[Session, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(bind=engine)
    return testing_session_local(), testing_session_local


def seed_course(db: Session) -> Course:
    user = User(email="student@example.com", display_name="Student")
    course = Course(title="Algorithms", owner=user)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def test_chunk_text_uses_fixed_size_and_overlap() -> None:
    chunks = chunk_text("abcdefghij", chunk_size=4, chunk_overlap=1)

    assert chunks == ["abcd", "defg", "ghij"]


def test_chunk_text_ignores_empty_input() -> None:
    assert chunk_text("   ") == []


def test_estimate_token_count_counts_words() -> None:
    assert estimate_token_count("Binary search halves the space") == 5


def test_upload_text_document_persists_document_and_chunks() -> None:
    setup_db, testing_session_local = build_test_db()
    course = seed_course(setup_db)
    setup_db.close()

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.post(
            f"/courses/{course.id}/documents/text",
            files={
                "file": (
                    "notes.txt",
                    b"Binary search works on sorted arrays.\nIt halves the search space.",
                    "text/plain",
                )
            },
        )

        assert response.status_code == 201
        payload = response.json()
        assert uuid.UUID(payload["id"])
        assert payload["course_id"] == str(course.id)
        assert payload["filename"] == "notes.txt"
        assert payload["content_type"] == "text/plain"
        assert payload["status"] == DocumentStatus.completed
        assert payload["chunk_count"] == 1

        verify_db = testing_session_local()
        document = verify_db.scalar(select(Document))
        chunks = verify_db.scalars(select(DocumentChunk)).all()

        assert document is not None
        assert document.status == DocumentStatus.completed
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert "Binary search" in chunks[0].text
        verify_db.close()
    finally:
        app.dependency_overrides.clear()


def test_upload_text_document_returns_404_for_missing_course() -> None:
    _, testing_session_local = build_test_db()

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.post(
            f"/courses/{uuid.uuid4()}/documents/text",
            files={"file": ("notes.txt", b"content", "text/plain")},
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_upload_text_document_marks_empty_text_as_failed() -> None:
    setup_db, testing_session_local = build_test_db()
    course = seed_course(setup_db)
    setup_db.close()

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.post(
            f"/courses/{course.id}/documents/text",
            files={"file": ("empty.txt", b"   ", "text/plain")},
        )

        assert response.status_code == 422

        verify_db = testing_session_local()
        document = verify_db.scalar(select(Document))

        assert document is not None
        assert document.status == DocumentStatus.failed
        verify_db.close()
    finally:
        app.dependency_overrides.clear()

