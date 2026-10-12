import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from app.api.upload_body_limit import UploadBodyLimitMiddleware
from app.api.upload_limits import read_upload
from app.core.config import Settings, settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Course, Document, DocumentChunk, User
from app.services import pdf_ingestion
from app.services.document_management import delete_document
from app.services.storage import UploadLimited, get_storage_usage
from app.services.text_ingestion import ingest_text_document
from auth_helpers import TEST_PASSWORD_HASH, authenticated_client
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def setup():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions() as db:
        user = User(email="storage@example.com", display_name="Storage",
                    password_hash=TEST_PASSWORD_HASH)
        courses = [Course(owner=user, title="One"), Course(owner=user, title="Two")]
        other = Course(owner=User(email="other@example.com", display_name="Other",
                                 password_hash=TEST_PASSWORD_HASH), title="Private")
        db.add_all([*courses, other])
        db.commit()
        ids = [course.id for course in [*courses, other]]
        user_id = user.id

    def override():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override
    try:
        yield authenticated_client(app, email="storage@example.com"), sessions, ids, user_id
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def upload(client, course_id, text=b"notes"):
    return client.post(f"/courses/{course_id}/documents/text",
                       files={"file": ("notes.txt", text, "text/plain")})


def test_file_boundary_and_no_rejected_record(setup, monkeypatch):
    client, sessions, courses, _ = setup
    monkeypatch.setattr(settings, "upload_max_bytes", 3)
    assert upload(client, courses[0], b"abc").status_code == 201
    assert upload(client, courses[0], b"abcd").status_code == 413
    response = client.post(f"/courses/{courses[0]}/documents/pdf",
                           files={"file": ("too-big.pdf", b"abcd", "application/pdf")})
    assert response.status_code == 413
    with sessions() as db:
        assert db.scalar(select(func.count(Document.id))) == 1


def test_file_reader_is_bounded_and_always_closes(monkeypatch):
    monkeypatch.setattr(settings, "upload_max_bytes", 3)
    calls = []

    class File:
        async def read(self, size):
            calls.append(size)
            return b"1234"

        async def close(self):
            calls.append("closed")

    with pytest.raises(UploadLimited):
        asyncio.run(read_upload(File()))
    assert calls == [4, "closed"]


@pytest.mark.parametrize("declared", [True, False])
def test_multipart_body_is_bounded_before_parser(monkeypatch, declared):
    monkeypatch.setattr(settings, "upload_max_bytes", 3)
    received, sent, entered = [], [], []
    async def app(scope, receive, send):
        entered.append(True)
    async def receive():
        received.append(True)
        return {"type": "http.request", "body": b"x" * 65540, "more_body": True}
    async def send(message):
        sent.append(message)
    scope = {"type": "http", "method": "POST", "path": "/courses/test/documents/text",
             "headers": [(b"content-length", b"65540")] if declared else []}
    asyncio.run(UploadBodyLimitMiddleware(app)(scope, receive, send))
    assert sent[0]["status"] == 413
    assert not entered
    assert len(received) == (0 if declared else 1)


def test_unicode_text_boundary_rolls_back_and_counts_bytes(setup, monkeypatch):
    client, sessions, courses, _ = setup
    monkeypatch.setattr(settings, "upload_max_text_chars", 2)
    accepted = upload(client, courses[0], "éx".encode())
    assert accepted.status_code == 201
    assert accepted.json()["storage_bytes"] == 3
    assert upload(client, courses[0], "éxy".encode()).status_code == 413
    usage = client.get("/auth/storage-usage")
    assert usage.headers["cache-control"] == "no-store"
    assert usage.json()["text_bytes"]["used"] == 3
    assert usage.json()["documents"]["used"] == 1
    with sessions() as db:
        assert db.scalar(select(func.count(DocumentChunk.id))) == 1


def test_page_limit_precedes_extraction_and_text_limit_stops_later_pages(monkeypatch):
    calls = []
    class Page:
        def extract_text(self):
            calls.append("extract")
            return "abc"
    monkeypatch.setattr(pdf_ingestion, "PdfReader", lambda _: SimpleNamespace(
        pages=[Page(), Page(), Page()]))
    monkeypatch.setattr(settings, "upload_max_pdf_pages", 2)
    with pytest.raises(UploadLimited, match="pages"):
        pdf_ingestion.extract_pdf_pages(b"dummy")
    assert not calls
    monkeypatch.setattr(settings, "upload_max_pdf_pages", 3)
    monkeypatch.setattr(settings, "upload_max_text_chars", 3)
    with pytest.raises(UploadLimited, match="characters"):
        pdf_ingestion.extract_pdf_pages(b"dummy")
    assert len(calls) == 2


@pytest.mark.parametrize("kind", ["documents", "bytes", "project"])
def test_quota_across_courses_and_deletion_frees_it(setup, monkeypatch, kind):
    client, sessions, courses, user_id = setup
    if kind == "documents":
        monkeypatch.setattr(settings, "storage_user_document_limit", 1)
    elif kind == "bytes":
        monkeypatch.setattr(settings, "storage_user_text_bytes", 5)
    else:
        monkeypatch.setattr(settings, "storage_project_text_bytes", 5)
    accepted = upload(client, courses[0])
    assert accepted.status_code == 201
    denied = upload(client, courses[1])
    assert denied.status_code == 409
    assert "Delete" in denied.json()["detail"]
    with sessions() as db:
        assert get_storage_usage(db, user_id).documents.used == 1
    assert client.delete(f"/documents/{accepted.json()['id']}").status_code == 204
    assert upload(client, courses[1]).status_code == 201


def test_failed_documents_count_slots_and_can_be_deleted(setup, monkeypatch):
    client, _, courses, _ = setup
    monkeypatch.setattr(settings, "storage_user_document_limit", 1)
    failure = upload(client, courses[0], b" ")
    assert failure.status_code == 422
    assert client.get("/auth/storage-usage").json()["documents"]["used"] == 1
    assert client.get("/auth/storage-usage").json()["text_bytes"]["used"] == 0
    assert upload(client, courses[1]).status_code == 409
    assert client.delete(f"/documents/{failure.json()['detail']['document_id']}").status_code == 204
    assert upload(client, courses[1]).status_code == 201


def test_rate_limits_include_failed_attempts_across_courses(setup, monkeypatch):
    client, _, courses, _ = setup
    monkeypatch.setattr(settings, "upload_user_hourly_limit", 2)
    assert upload(client, courses[0], b"notes").status_code == 201
    assert upload(client, courses[1], b" ").status_code == 422
    blocked = upload(client, courses[1])
    assert blocked.status_code == 429
    assert 1 <= int(blocked.headers["retry-after"]) <= 3600
    assert "upload attempts" in blocked.json()["detail"]
    assert client.get("/auth/storage-usage").status_code == 200


@pytest.mark.parametrize("scope", ["ip", "project"])
def test_shared_upload_rate_limits_cross_student_accounts(setup, monkeypatch, scope):
    client, _, courses, _ = setup
    monkeypatch.setattr(settings, "upload_ip_hourly_limit", 2 if scope == "ip" else 100)
    monkeypatch.setattr(settings, "upload_project_hourly_limit", 2 if scope == "project" else 100)
    assert upload(client, courses[0]).status_code == 201
    other = authenticated_client(app, email="other@example.com")
    assert upload(other, courses[2]).status_code == 201
    assert upload(client, courses[1]).status_code == 429


def test_pdf_rejection_does_not_leave_a_processing_record(setup, monkeypatch):
    client, sessions, courses, _ = setup
    def reject(content):
        raise UploadLimited("Too many PDF pages")
    monkeypatch.setattr(pdf_ingestion, "extract_pdf_pages", reject)
    response = client.post(f"/courses/{courses[0]}/documents/pdf",
                           files={"file": ("notes.pdf", b"%PDF", "application/pdf")})
    assert response.status_code == 413
    with sessions() as db:
        assert db.scalar(select(func.count(Document.id))) == 0


def test_chunk_overlap_is_charged_as_stored_utf8_bytes(setup):
    client, sessions, courses, _ = setup
    accepted = upload(client, courses[0], ("é" * 1201).encode())
    assert accepted.status_code == 201
    with sessions() as db:
        chunk_bytes = sum(len(text.encode()) for text in db.scalars(select(DocumentChunk.text)))
        assert chunk_bytes == (1201 + 150) * 2
        assert accepted.json()["storage_bytes"] == chunk_bytes


def test_storage_usage_is_private_and_other_users_do_not_consume_personal_quota(setup):
    client, sessions, courses, _ = setup
    with sessions() as db:
        ingest_text_document(db, course_id=courses[2], filename="private.txt",
                             content_type="text/plain", raw_content=b"secret")
    assert client.get("/auth/storage-usage").json()["documents"]["used"] == 0
    assert upload(client, courses[2]).status_code == 404
    assert client.delete(f"/documents/{uuid.uuid4()}").status_code == 404
    client.headers.clear()
    assert client.get("/auth/storage-usage").status_code == 401
    assert upload(client, courses[0]).status_code == 401


def test_storage_failure_fails_closed(setup, monkeypatch):
    client, _, courses, _ = setup
    from app.api import upload_limits
    def fail(*args):
        from app.services.auth_rate_limit import AuthRateLimitUnavailable
        raise AuthRateLimitUnavailable()
    monkeypatch.setattr(upload_limits, "consume_attempts", fail)
    assert upload(client, courses[0]).status_code == 503


def test_allowance_query_failure_has_a_safe_message(setup, monkeypatch):
    client, _, _, _ = setup
    from app.services import storage
    original_execute = Session.execute
    def execute(db, statement, *args, **kwargs):
        if "sum(documents.storage_bytes)" in str(statement):
            raise OperationalError("query", {}, Exception("private connection details"))
        return original_execute(db, statement, *args, **kwargs)
    monkeypatch.setattr(storage.Session, "execute", execute)
    response = client.get("/auth/storage-usage")
    assert response.status_code == 503
    assert "private" not in response.text


def test_commit_failure_releases_slot_and_bytes(setup, monkeypatch):
    _, sessions, courses, user_id = setup
    with sessions() as db:
        def fail():
            raise OperationalError("commit", {}, Exception("storage failure"))
        monkeypatch.setattr(db, "commit", fail)
        with pytest.raises(OperationalError):
            ingest_text_document(db, course_id=courses[0], filename="notes.txt",
                                 content_type="text/plain", raw_content=b"notes")
        db.rollback()
    with sessions() as db:
        assert get_storage_usage(db, user_id).documents.used == 0
        assert get_storage_usage(db, user_id).text_bytes.used == 0


@pytest.mark.parametrize("scope", ["documents", "bytes"])
def test_parallel_uploads_cannot_overfill_sqlite(tmp_path, monkeypatch, scope):
    engine = create_engine(f"sqlite:///{tmp_path / 'parallel.db'}",
                           connect_args={"timeout": 30})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="parallel@example.com", display_name="Parallel")
        course = Course(owner=user, title="Parallel")
        db.add(course)
        db.commit()
        course_id, user_id = course.id, user.id
    monkeypatch.setattr(settings, "storage_user_document_limit", 3 if scope == "documents" else 20)
    monkeypatch.setattr(settings, "storage_user_text_bytes", 9 if scope == "bytes" else 1000)

    def attempt(_):
        with Session(engine) as db:
            try:
                ingest_text_document(db, course_id=course_id, filename="notes.txt",
                                     content_type="text/plain", raw_content="é".encode())
                return True
            except UploadLimited:
                return False
    try:
        with ThreadPoolExecutor(max_workers=8) as workers:
            expected = 3 if scope == "documents" else 4
            assert sum(workers.map(attempt, range(12))) == expected
        with Session(engine) as db:
            usage = get_storage_usage(db, user_id)
            assert usage.documents.used == expected
            assert usage.text_bytes.used == expected * 2
            first = db.scalar(select(Document.id))
            delete_document(db, first)
        assert attempt(0)
    finally:
        engine.dispose()


@pytest.mark.parametrize("field", ["upload_max_bytes", "upload_max_pdf_pages",
    "upload_max_text_chars", "storage_user_document_limit", "storage_user_text_bytes",
    "storage_project_document_limit", "storage_project_text_bytes", "upload_user_hourly_limit"])
def test_limits_must_be_positive(field):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **{field: 0})
