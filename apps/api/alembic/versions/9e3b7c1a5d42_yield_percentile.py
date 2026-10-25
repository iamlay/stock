"""stock yield percentile

Revision ID: 9e3b7c1a5d42
Revises: 8d1f3a5c7e20
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9e3b7c1a5d42"
down_revision: str | None = "8d1f3a5c7e20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stock_metrics",
        sa.Column("yield_percentile", sa.Numeric(precision=6, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stock_metrics", "yield_percentile")
