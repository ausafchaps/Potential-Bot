"""create quiz attempt tables

Revision ID: 20260609_0006
Revises: 20260608_0005
Create Date: 2026-06-09 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260609_0006"
down_revision: str | None = "20260608_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quiz_id", sa.Uuid(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("score_percent", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quiz_attempts_quiz_id"), "quiz_attempts", ["quiz_id"])

    op.create_table(
        "quiz_attempt_answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("selected_option_id", sa.Uuid(), nullable=False),
        sa.Column("question_position", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("selected_option_text", sa.Text(), nullable=False),
        sa.Column("correct_option_id", sa.Uuid(), nullable=False),
        sa.Column("correct_option_text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["attempt_id"], ["quiz_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["quiz_questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["selected_option_id"],
            ["quiz_question_options.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_quiz_attempt_answers_question"),
    )
    op.create_index(
        op.f("ix_quiz_attempt_answers_attempt_id"),
        "quiz_attempt_answers",
        ["attempt_id"],
    )
    op.create_index(
        op.f("ix_quiz_attempt_answers_question_id"),
        "quiz_attempt_answers",
        ["question_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_quiz_attempt_answers_question_id"), table_name="quiz_attempt_answers")
    op.drop_index(op.f("ix_quiz_attempt_answers_attempt_id"), table_name="quiz_attempt_answers")
    op.drop_table("quiz_attempt_answers")
    op.drop_index(op.f("ix_quiz_attempts_quiz_id"), table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
