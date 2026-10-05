"""Add shared authentication attempt counters."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0009"
down_revision: str | None = "20261002_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_rate_limits",
        sa.Column("bucket_key", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("attempts >= 1", name=op.f("ck_auth_rate_limits_positive_attempts")),
        sa.PrimaryKeyConstraint("bucket_key"),
    )
    op.create_index("ix_auth_rate_limits_expires_at", "auth_rate_limits", ["expires_at"])


def downgrade() -> None:
    op.drop_table("auth_rate_limits")
