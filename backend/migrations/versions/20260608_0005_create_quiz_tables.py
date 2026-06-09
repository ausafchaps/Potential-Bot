"""create quiz tables

Revision ID: 20260608_0005
Revises: 20260603_0004
Create Date: 2026-06-08 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260608_0005"
down_revision: str | None = "20260603_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quizzes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(length=300), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column(
            "difficulty",
            sa.Enum(
                "easy",
                "medium",
                "hard",
                name="quiz_difficulty",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "generated",
                "insufficient_evidence",
                name="quiz_status",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quizzes_course_id"), "quizzes", ["course_id"], unique=False)

    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quiz_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quiz_id", "position", name="uq_quiz_questions_quiz_position"),
    )
    op.create_index(
        op.f("ix_quiz_questions_quiz_id"),
        "quiz_questions",
        ["quiz_id"],
        unique=False,
    )

    op.create_table(
        "quiz_question_options",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quiz_question_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["quiz_question_id"],
            ["quiz_questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "quiz_question_id",
            "position",
            name="uq_quiz_question_options_question_position",
        ),
    )
    op.create_index(
        op.f("ix_quiz_question_options_quiz_question_id"),
        "quiz_question_options",
        ["quiz_question_id"],
        unique=False,
    )

    op.create_table(
        "quiz_citations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quiz_question_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("document_filename", sa.String(length=255), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["quiz_question_id"],
            ["quiz_questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "quiz_question_id",
            "position",
            name="uq_quiz_citations_question_position",
        ),
    )
    op.create_index(
        op.f("ix_quiz_citations_quiz_question_id"),
        "quiz_citations",
        ["quiz_question_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_quiz_citations_quiz_question_id"), table_name="quiz_citations")
    op.drop_table("quiz_citations")
    op.drop_index(
        op.f("ix_quiz_question_options_quiz_question_id"),
        table_name="quiz_question_options",
    )
    op.drop_table("quiz_question_options")
    op.drop_index(op.f("ix_quiz_questions_quiz_id"), table_name="quiz_questions")
    op.drop_table("quiz_questions")
    op.drop_index(op.f("ix_quizzes_course_id"), table_name="quizzes")
    op.drop_table("quizzes")
