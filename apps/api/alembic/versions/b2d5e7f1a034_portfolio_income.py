"""portfolio dividend entitlements and receipts

Revision ID: b2d5e7f1a034
Revises: f1a7b9c52346
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2d5e7f1a034"
down_revision: str | None = "f1a7b9c52346"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dividend_entitlements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_revision", sa.Integer(), nullable=False),
        sa.Column("account_version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("record_date", sa.Date(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("eligible_quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("cash_per_share", sa.Numeric(20, 8), nullable=False),
        sa.Column("gross_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("calculation_version", sa.String(length=32), nullable=False),
        sa.Column("review_reasons", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "eligible_quantity >= 0 AND cash_per_share >= 0 AND gross_amount >= 0",
            name="ck_dividend_entitlement_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["portfolio_accounts.id", "portfolio_accounts.user_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["dividend_events.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id", "event_id", "revision", name="uq_dividend_entitlement_version"
        ),
    )
    op.create_index(
        "ix_dividend_entitlements_owner",
        "dividend_entitlements",
        ["user_id", "account_id", "is_active"],
    )
    op.create_table(
        "dividend_receipts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("entitlement_id", sa.String(length=36), nullable=True),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("received_date", sa.Date(), nullable=False),
        sa.Column("gross_amount", sa.Numeric(20, 2), nullable=True),
        sa.Column("tax_amount", sa.Numeric(20, 2), nullable=True),
        sa.Column("net_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "net_amount > 0 AND (gross_amount IS NULL OR gross_amount >= 0)",
            name="ck_dividend_receipt_amount",
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["portfolio_accounts.id", "portfolio_accounts.user_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entitlement_id"],
            ["dividend_entitlements.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "request_id", name="uq_dividend_receipt_request"),
    )
    op.create_index(
        "ix_dividend_receipts_owner",
        "dividend_receipts",
        ["user_id", "account_id", "received_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_dividend_receipts_owner", table_name="dividend_receipts")
    op.drop_table("dividend_receipts")
    op.drop_index("ix_dividend_entitlements_owner", table_name="dividend_entitlements")
    op.drop_table("dividend_entitlements")
