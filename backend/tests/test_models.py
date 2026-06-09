import uuid

from app.db.base import Base
from app.models import (
    Course,
    Document,
    DocumentChunk,
    DocumentChunkEmbedding,
    DocumentStatus,
    Quiz,
    QuizCitation,
    QuizDifficulty,
    QuizQuestion,
    QuizQuestionOption,
    QuizStatus,
    User,
)
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker


def build_test_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(bind=engine)
    return testing_session_local()


def test_core_tables_are_declared() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    inspector = inspect(engine)

    assert set(inspector.get_table_names()) == {
        "answer_feedback",
        "answers",
        "citations",
        "users",
        "courses",
        "documents",
        "document_chunks",
        "document_chunk_embeddings",
        "questions",
        "quiz_citations",
        "quiz_question_options",
        "quiz_questions",
        "quizzes",
    }


def test_user_course_document_chunk_relationships() -> None:
    session = build_test_session()

    user = User(email="student@example.com", display_name="Student")
    course = Course(title="Algorithms", description="CS course", owner=user)
    document = Document(
        filename="lecture-1.pdf",
        content_type="application/pdf",
        status=DocumentStatus.completed,
        page_count=12,
        course=course,
    )
    chunk = DocumentChunk(
        document=document,
        chunk_index=0,
        text="Binary search repeatedly halves a sorted search space.",
        page_number=3,
        token_count=9,
    )
    embedding = DocumentChunkEmbedding(
        chunk=chunk,
        provider="fake",
        model="fake-token-hash-v1",
        dimensions=24,
        vector_json="[1.0,0.0]",
    )
    quiz = Quiz(
        course=course,
        topic="binary search",
        title="Binary Search Quiz",
        difficulty=QuizDifficulty.medium,
        status=QuizStatus.generated,
        provider="fake",
        prompt="Generate a quiz",
    )
    quiz_question = QuizQuestion(
        quiz=quiz,
        position=1,
        question_text="What does binary search require?",
        explanation="It requires sorted input.",
    )
    QuizQuestionOption(
        question=quiz_question,
        position=1,
        text="A sorted array",
        is_correct=True,
    )
    QuizCitation(
        question=quiz_question,
        position=1,
        document_id=None,
        chunk_id=None,
        document_filename="lecture-1.pdf",
        chunk_index=0,
        page_number=3,
        text=chunk.text,
    )

    session.add(user)
    session.commit()

    saved_user = session.scalar(select(User).where(User.email == "student@example.com"))

    assert saved_user is not None
    assert isinstance(saved_user.id, uuid.UUID)
    assert saved_user.courses[0].title == "Algorithms"
    assert saved_user.courses[0].documents[0].status == DocumentStatus.completed
    assert saved_user.courses[0].documents[0].chunks[0].text == chunk.text
    assert saved_user.courses[0].documents[0].chunks[0].embeddings[0].id == embedding.id
    assert saved_user.courses[0].quizzes[0].questions[0].options[0].is_correct
    assert saved_user.courses[0].quizzes[0].questions[0].citations[0].text == chunk.text

    session.close()
