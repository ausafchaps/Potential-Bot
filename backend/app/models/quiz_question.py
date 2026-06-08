import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.quiz import Quiz
    from app.models.quiz_citation import QuizCitation
    from app.models.quiz_question_option import QuizQuestionOption


class QuizQuestion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "quiz_questions"
    __table_args__ = (
        UniqueConstraint("quiz_id", "position", name="uq_quiz_questions_quiz_position"),
    )

    quiz_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    quiz: Mapped["Quiz"] = relationship(back_populates="questions")
    options: Mapped[list["QuizQuestionOption"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuizQuestionOption.position",
    )
    citations: Mapped[list["QuizCitation"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuizCitation.position",
    )

