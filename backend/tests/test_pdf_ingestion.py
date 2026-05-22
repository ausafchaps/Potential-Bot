import uuid
from collections.abc import Generator

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Document, DocumentChunk, DocumentStatus, User
from app.schemas.course import CourseCreate
from app.services.pdf_ingestion import extract_pdf_pages
from app.services.user_course import create_course_for_user
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


def make_text_pdf(text: str) -> bytes:
    escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 18 Tf 72 720 Td ({escaped_text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        ),
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)


def seed_course(db: Session):
    user = User(email="student@example.com", display_name="Student")
    db.add(user)
    db.commit()
    db.refresh(user)
    return create_course_for_user(db, user.id, CourseCreate(title="Algorithms"))


def test_extract_pdf_pages_reads_text_by_page() -> None:
    pages = extract_pdf_pages(make_text_pdf("Binary search halves arrays."))

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "Binary search" in pages[0].text


def test_upload_pdf_document_persists_page_count_and_page_chunks() -> None:
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
            f"/courses/{course.id}/documents/pdf",
            files={
                "file": (
                    "lecture.pdf",
                    make_text_pdf("Binary search halves sorted arrays."),
                    "application/pdf",
                )
            },
        )

        assert response.status_code == 201
        payload = response.json()
        assert uuid.UUID(payload["id"])
        assert payload["course_id"] == str(course.id)
        assert payload["filename"] == "lecture.pdf"
        assert payload["content_type"] == "application/pdf"
        assert payload["status"] == DocumentStatus.completed
        assert payload["chunk_count"] == 1

        verify_db = testing_session_local()
        document = verify_db.scalar(select(Document))
        chunks = verify_db.scalars(select(DocumentChunk)).all()

        assert document is not None
        assert document.page_count == 1
        assert document.status == DocumentStatus.completed
        assert len(chunks) == 1
        assert chunks[0].page_number == 1
        assert "Binary search" in chunks[0].text
        verify_db.close()
    finally:
        app.dependency_overrides.clear()


def test_upload_pdf_document_marks_textless_pdf_as_failed() -> None:
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
            f"/courses/{course.id}/documents/pdf",
            files={"file": ("blank.pdf", make_text_pdf("   "), "application/pdf")},
        )

        assert response.status_code == 422

        verify_db = testing_session_local()
        document = verify_db.scalar(select(Document))

        assert document is not None
        assert document.status == DocumentStatus.failed
        verify_db.close()
    finally:
        app.dependency_overrides.clear()


def test_upload_pdf_document_returns_415_for_non_pdf() -> None:
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
            f"/courses/{uuid.uuid4()}/documents/pdf",
            files={"file": ("notes.txt", b"not a pdf", "text/plain")},
        )

        assert response.status_code == 415
    finally:
        app.dependency_overrides.clear()
