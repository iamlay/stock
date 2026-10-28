"""Versioned position snapshots and preferences; retain legacy financial columns.

Revision ID: f1a7b9c52346
Revises: e0f6a8b41235
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "f1a7b9c52346"
down_revision = "e0f6a8b41235"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("portfolio_entries", sa.Column(
        "details", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True))
    op.drop_constraint("ck_portfolio_entry_kind", "portfolio_entries", type_="check")
    op.create_check_constraint("ck_portfolio_entry_kind", "portfolio_entries",
        "kind IN ('opening','buy','sell','adjustment','reversal','snapshot','preference','rebase')")


def downgrade():
    # Never silently discard signed balances, unknown states or user preferences.
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM portfolio_entries WHERE details IS NOT NULL")):
        raise RuntimeError("New position records exist; restore a verified backup instead of dropping them")
    op.drop_constraint("ck_portfolio_entry_kind", "portfolio_entries", type_="check")
    op.create_check_constraint("ck_portfolio_entry_kind", "portfolio_entries",
        "kind IN ('opening','buy','sell','adjustment','reversal')")
    op.drop_column("portfolio_entries", "details")
