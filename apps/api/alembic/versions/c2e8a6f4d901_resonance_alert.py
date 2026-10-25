"""resonance alerts

Revision ID: c2e8a6f4d901
Revises: b7d2f4a9c610
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2e8a6f4d901"
down_revision: str | None = "b7d2f4a9c610"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "alert_resonance",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "alert_resonance")
