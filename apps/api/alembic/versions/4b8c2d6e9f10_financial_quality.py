"""financial quality metrics

Revision ID: 4b8c2d6e9f10
Revises: 2f6a1d8c4e90
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4b8c2d6e9f10"
down_revision: str | None = "2f6a1d8c4e90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stock_financials",
        sa.Column("roe", sa.Numeric(precision=8, scale=2), nullable=True),
    )
    op.add_column(
        "stock_financials",
        sa.Column(
            "operating_cash_flow_per_share",
            sa.Numeric(precision=12, scale=4),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("stock_financials", "operating_cash_flow_per_share")
    op.drop_column("stock_financials", "roe")
