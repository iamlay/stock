"""grid alerts

Revision ID: 2f6a1d8c4e90
Revises: 7a2e5f9c1b3d
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2f6a1d8c4e90"
down_revision: str | None = "7a2e5f9c1b3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "alert_grid",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "alert_grid_yield",
            sa.Numeric(precision=4, scale=2),
            server_default=sa.text("5"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "alert_grid_yield")
    op.drop_column("users", "alert_grid")
