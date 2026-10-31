"""dividend receipt quantity and per-share cash

Revision ID: d1a6b9e3f472
Revises: c9e4a1d7f250
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1a6b9e3f472"
down_revision: str | None = "c9e4a1d7f250"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dividend_receipts",
        sa.Column("quantity", sa.Numeric(20, 6), nullable=True),
    )
    op.add_column(
        "dividend_receipts",
        sa.Column("cash_per_share", sa.Numeric(20, 8), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("dividend_receipts", "cash_per_share")
    op.drop_column("dividend_receipts", "quantity")
