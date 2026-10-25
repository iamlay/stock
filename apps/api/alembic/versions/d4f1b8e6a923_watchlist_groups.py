"""watchlist groups

Revision ID: d4f1b8e6a923
Revises: c2e8a6f4d901
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4f1b8e6a923"
down_revision: str | None = "c2e8a6f4d901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stock_watchlist",
        sa.Column(
            "group_name",
            sa.String(length=32),
            server_default="默认",
            nullable=False,
        ),
    )
    op.add_column(
        "watchlist_items",
        sa.Column(
            "group_name",
            sa.String(length=32),
            server_default="默认",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("watchlist_items", "group_name")
    op.drop_column("stock_watchlist", "group_name")
