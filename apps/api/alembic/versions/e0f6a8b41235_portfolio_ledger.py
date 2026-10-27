"""Private opening positions, immutable transactions and dividend review ranges.

Revision ID: e0f6a8b41235
Revises: d9e5f7a30124
"""

import sqlalchemy as sa

from alembic import op

revision = "e0f6a8b41235"
down_revision = "d9e5f7a30124"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "portfolio_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("code", sa.String(16), sa.ForeignKey("instruments.code"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("event_date", sa.Date, nullable=False),
        sa.Column("day_order", sa.Integer, nullable=False),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("price", sa.Numeric(20, 6), nullable=False),
        sa.Column("fees", sa.Numeric(20, 6), nullable=False),
        sa.Column("total_cost", sa.Numeric(20, 6), nullable=False),
        sa.Column("history_status", sa.String(24), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("note", sa.String(500), nullable=False),
        sa.Column("evidence", sa.String(500), nullable=False),
        sa.Column("reverses_id", sa.String(36)),
        sa.Column("account_version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "account_id", "user_id", name="uq_portfolio_entry_owner"),
        sa.UniqueConstraint("account_id", "request_id", name="uq_portfolio_entry_request"),
        sa.UniqueConstraint("reverses_id", name="uq_portfolio_entry_reversal"),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["portfolio_accounts.id", "portfolio_accounts.user_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reverses_id", "account_id", "user_id"],
            ["portfolio_entries.id", "portfolio_entries.account_id", "portfolio_entries.user_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "quantity >= 0 AND price >= 0 AND fees >= 0 AND total_cost >= 0",
            name="ck_portfolio_entry_nonnegative",
        ),
        sa.CheckConstraint("day_order > 0", name="ck_portfolio_entry_order"),
        sa.CheckConstraint(
            "kind IN ('opening','buy','sell','adjustment','reversal')",
            name="ck_portfolio_entry_kind",
        ),
    )
    op.create_index(
        "ix_portfolio_entries_owner", "portfolio_entries", ["user_id", "account_id", "event_date"]
    )
    op.create_table(
        "portfolio_review_ranges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("from_date", sa.Date, nullable=False),
        sa.Column("account_version", sa.Integer, nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["portfolio_accounts.id", "portfolio_accounts.user_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_portfolio_review_owner", "portfolio_review_ranges", ["user_id", "account_id"]
    )


def downgrade():
    op.drop_table("portfolio_review_ranges")
    op.drop_table("portfolio_entries")
