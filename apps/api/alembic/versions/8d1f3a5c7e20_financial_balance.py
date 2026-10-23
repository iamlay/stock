"""financial balance sheet metrics

Revision ID: 8d1f3a5c7e20
Revises: 6c4e8a1f2d30
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8d1f3a5c7e20"
down_revision: str | None = "6c4e8a1f2d30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stock_financials",
        sa.Column("total_assets", sa.Numeric(precision=20, scale=2), nullable=True),
    )
    op.add_column(
        "stock_financials",
        sa.Column("total_liabilities", sa.Numeric(precision=20, scale=2), nullable=True),
    )
    op.add_column(
        "stock_financials",
        sa.Column("debt_asset_ratio", sa.Numeric(precision=8, scale=2), nullable=True),
    )
    op.add_column(
        "stock_financials",
        sa.Column("roa", sa.Numeric(precision=8, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stock_financials", "roa")
    op.drop_column("stock_financials", "debt_asset_ratio")
    op.drop_column("stock_financials", "total_liabilities")
    op.drop_column("stock_financials", "total_assets")
