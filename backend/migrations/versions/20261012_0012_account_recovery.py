"""Add email verification state and single-use account links."""

import sqlalchemy as sa
from alembic import op

revision = "20261012_0012"
down_revision = "20261009_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False,
                                    server_default=sa.false()))
    op.add_column("users", sa.Column("credential_version", sa.Integer(), nullable=False,
                                    server_default=sa.text("0")))
    op.create_table(
        "account_tokens",
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(6), nullable=False),
        sa.Column("email_hash", sa.String(64), nullable=False),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("consumed_at", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("token_hash"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("purpose IN ('reset','verify')", name="ck_account_tokens_purpose"),
    )
    op.create_index("ix_account_tokens_user_id", "account_tokens", ["user_id"])
    op.create_index("ix_account_tokens_expires_at", "account_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_table("account_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("credential_version")
        batch.drop_column("email_verified")
