"""bonus and reinvest ledger kinds

Revision ID: c9e4a1d7f250
Revises: b2d5e7f1a034
Create Date: 2026-10-31
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c9e4a1d7f250"
down_revision: str | None = "b2d5e7f1a034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW = (
    "opening','buy','sell','adjustment','reversal',"
    "'snapshot','preference','rebase','bonus','reinvest"
)
OLD = (
    "opening','buy','sell','adjustment','reversal',"
    "'snapshot','preference','rebase"
)


def upgrade() -> None:
    op.drop_constraint("ck_portfolio_entry_kind", "portfolio_entries", type_="check")
    op.create_check_constraint(
        "ck_portfolio_entry_kind",
        "portfolio_entries",
        f"kind IN ('{NEW}')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_portfolio_entry_kind", "portfolio_entries", type_="check")
    op.create_check_constraint(
        "ck_portfolio_entry_kind",
        "portfolio_entries",
        f"kind IN ('{OLD}')",
    )
