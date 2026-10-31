"""automatic dividend receipts source

Revision ID: e2b7c4a9d183
Revises: d1a6b9e3f472
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2b7c4a9d183"
down_revision: str | None = "d1a6b9e3f472"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dividend_receipts",
        sa.Column(
            "source",
            sa.String(length=16),
            server_default="manual",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("dividend_receipts", "source")
