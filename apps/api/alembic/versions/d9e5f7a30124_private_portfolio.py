"""Private single-account ownership, explicit privacy acknowledgement and deletion markers.

Revision ID: d9e5f7a30124
Revises: c8d4e6f29013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "d9e5f7a30124"
down_revision: str | None = "c8d4e6f29013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
JSONType = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "portfolio_privacy_acceptances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("policy_sha256", sa.String(64), nullable=False),
        sa.Column("policy_snapshot", JSONType, nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "policy_version", "policy_sha256", name="uq_portfolio_acceptance"
        ),
        sa.UniqueConstraint("id", "user_id", name="uq_portfolio_acceptance_owner"),
    )
    op.create_table(
        "portfolio_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("is_archived", sa.Boolean, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("privacy_acceptance_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_portfolio_single_account"),
        sa.UniqueConstraint("id", "user_id", name="uq_portfolio_account_owner"),
        sa.ForeignKeyConstraint(
            ["privacy_acceptance_id", "user_id"],
            ["portfolio_privacy_acceptances.id", "portfolio_privacy_acceptances.user_id"],
        ),
    )
    op.create_table(
        "portfolio_audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("account_version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["portfolio_accounts.id", "portfolio_accounts.user_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_portfolio_audit_owner", "portfolio_audit_events", ["user_id", "account_id"])
    op.create_table(
        "portfolio_deletions",
        sa.Column("account_id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_portfolio_deletions_user", "portfolio_deletions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_portfolio_deletions_user", "portfolio_deletions")
    op.drop_table("portfolio_deletions")
    op.drop_index("ix_portfolio_audit_owner", "portfolio_audit_events")
    op.drop_table("portfolio_audit_events")
    op.drop_table("portfolio_accounts")
    op.drop_table("portfolio_privacy_acceptances")
