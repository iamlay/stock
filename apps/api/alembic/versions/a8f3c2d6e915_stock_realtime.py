"""stock realtime quotes

Revision ID: a8f3c2d6e915
Revises: d4f1b8e6a923
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8f3c2d6e915"
down_revision: str | None = "f7b3d1a29465"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stock_realtime_quotes",
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("prev_close", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("change_pct", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column(
            "amount",
            sa.Numeric(precision=18, scale=2),
            server_default="0",
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("quote_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "source",
            sa.String(length=16),
            server_default="tencent",
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["code"], ["instruments.code"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("code"),
    )


def downgrade() -> None:
    op.drop_table("stock_realtime_quotes")
