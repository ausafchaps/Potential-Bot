import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.quiz_attempt import QuizAttempt
    from app.models.quiz_question import QuizQuestion


class QuizStatus(StrEnum):
    generated = "generated"
    insufficient_evidence = "insufficient_evidence"


class QuizDifficulty(StrEnum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class Quiz(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quizzes"

    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    topic: Mapped[str] = mapped_column(String(300), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    difficulty: Mapped[QuizDifficulty] = mapped_column(
        Enum(
            QuizDifficulty,
            name="quiz_difficulty",
            values_callable=lambda difficulties: [
                difficulty.value for difficulty in difficulties
            ],
            create_constraint=True,
        ),
        nullable=False,
    )
    status: Mapped[QuizStatus] = mapped_column(
        Enum(
            QuizStatus,
            name="quiz_status",
            values_callable=lambda statuses: [status.value for status in statuses],
            create_constraint=True,
        ),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    course: Mapped["Course"] = relationship(back_populates="quizzes")
    questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="QuizQuestion.position",
    )
    attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="QuizAttempt.created_at.desc()",
    )
