"""create flashcard tables

Revision ID: 20260611_0007
Revises: 20260609_0006
Create Date: 2026-06-11 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260611_0007"
down_revision: str | None = "20260609_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "flashcard_sets",
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
                name="flashcard_difficulty",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "generated",
                "insufficient_evidence",
                name="flashcard_set_status",
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
    op.create_index(
        op.f("ix_flashcard_sets_course_id"),
        "flashcard_sets",
        ["course_id"],
        unique=False,
    )

    op.create_table(
        "flashcards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("flashcard_set_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("front", sa.Text(), nullable=False),
        sa.Column("back", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["flashcard_set_id"],
            ["flashcard_sets.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "flashcard_set_id",
            "position",
            name="uq_flashcards_set_position",
        ),
    )
    op.create_index(
        op.f("ix_flashcards_flashcard_set_id"),
        "flashcards",
        ["flashcard_set_id"],
        unique=False,
    )

    op.create_table(
        "flashcard_citations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("flashcard_id", sa.Uuid(), nullable=False),
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
            ["flashcard_id"],
            ["flashcards.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "flashcard_id",
            "position",
            name="uq_flashcard_citations_card_position",
        ),
    )
    op.create_index(
        op.f("ix_flashcard_citations_flashcard_id"),
        "flashcard_citations",
        ["flashcard_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_flashcard_citations_flashcard_id"),
        table_name="flashcard_citations",
    )
    op.drop_table("flashcard_citations")
    op.drop_index(
        op.f("ix_flashcards_flashcard_set_id"),
        table_name="flashcards",
    )
    op.drop_table("flashcards")
    op.drop_index(op.f("ix_flashcard_sets_course_id"), table_name="flashcard_sets")
    op.drop_table("flashcard_sets")
