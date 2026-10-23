"""stock financials

Revision ID: 7a2e5f9c1b3d
Revises: 41b39c7d5a9a
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7a2e5f9c1b3d"
down_revision: str | None = "41b39c7d5a9a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stock_financials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("period", sa.String(length=8), nullable=False),
        sa.Column("revenue", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("net_profit", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("revenue_yoy", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("net_profit_yoy", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("disclosure_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["code"], ["instruments.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "code", "report_date", name="uq_stock_financials_code_report"
        ),
    )
    op.create_index(
        "ix_stock_financials_code_report",
        "stock_financials",
        ["code", "report_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_stock_financials_code_report", table_name="stock_financials")
    op.drop_table("stock_financials")
