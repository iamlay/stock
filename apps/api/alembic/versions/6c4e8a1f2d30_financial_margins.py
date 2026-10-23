"""financial margins and operating cash flow

Revision ID: 6c4e8a1f2d30
Revises: 4b8c2d6e9f10
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6c4e8a1f2d30"
down_revision: str | None = "4b8c2d6e9f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stock_financials",
        sa.Column("operating_cash_flow", sa.Numeric(precision=20, scale=2), nullable=True),
    )
    op.add_column(
        "stock_financials",
        sa.Column("gross_margin", sa.Numeric(precision=8, scale=2), nullable=True),
    )
    op.add_column(
        "stock_financials",
        sa.Column("net_margin", sa.Numeric(precision=8, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stock_financials", "net_margin")
    op.drop_column("stock_financials", "gross_margin")
    op.drop_column("stock_financials", "operating_cash_flow")
