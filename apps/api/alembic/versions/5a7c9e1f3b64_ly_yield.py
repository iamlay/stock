"""latest announced dividend yield

Revision ID: 5a7c9e1f3b64
Revises: 9e3b7c1a5d42
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5a7c9e1f3b64"
down_revision: str | None = "9e3b7c1a5d42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stock_metrics",
        sa.Column("dividend_yield_ly", sa.Numeric(precision=8, scale=4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stock_metrics", "dividend_yield_ly")
