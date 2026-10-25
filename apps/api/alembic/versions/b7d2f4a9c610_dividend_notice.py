"""dividend announcement fields

Revision ID: b7d2f4a9c610
Revises: 5a7c9e1f3b64
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d2f4a9c610"
down_revision: str | None = "5a7c9e1f3b64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "stock_dividends",
        "ex_date",
        existing_type=sa.Date(),
        nullable=True,
    )
    op.add_column(
        "stock_dividends",
        sa.Column("notice_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "stock_dividends",
        sa.Column("report_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "stock_dividends",
        sa.Column("progress", sa.String(length=32), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("stock_dividends", "progress")
    op.drop_column("stock_dividends", "report_date")
    op.drop_column("stock_dividends", "notice_date")
    op.alter_column(
        "stock_dividends",
        "ex_date",
        existing_type=sa.Date(),
        nullable=False,
    )
