import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.quiz_question import QuizQuestion


class QuizCitation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "quiz_citations"
    __table_args__ = (
        UniqueConstraint(
            "quiz_question_id",
            "position",
            name="uq_quiz_citations_question_position",
        ),
    )

    quiz_question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("quiz_questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    document_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    question: Mapped["QuizQuestion"] = relationship(back_populates="citations")

