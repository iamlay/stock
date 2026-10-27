"""Add isolated dividend event versions and review queue; no legacy rows rewritten.

Revision ID: c8d4e6f29013
Revises: a8f3c2d6e915
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c8d4e6f29013"
down_revision: str | None = "a8f3c2d6e915"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
JSONType = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "dividend_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "code",
            sa.String(16),
            sa.ForeignKey("instruments.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "legacy_dividend_id",
            sa.Integer,
            sa.ForeignKey("stock_dividends.id", ondelete="SET NULL"),
            unique=True,
        ),
        sa.Column("current_revision", sa.Integer, nullable=False),
        sa.Column("origin", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_dividend_events_code", "dividend_events", ["code"])
    op.create_table(
        "dividend_source_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "code",
            sa.String(16),
            sa.ForeignKey("instruments.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("normalized", JSONType, nullable=False),
        sa.Column("raw_payload", JSONType, nullable=False),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column(
            "event_id", sa.String(36), sa.ForeignKey("dividend_events.id", ondelete="CASCADE")
        ),
        sa.Column("applied_revision", sa.Integer),
        sa.Column("decision_hash", sa.String(64)),
        sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.Text),
        sa.UniqueConstraint(
            "source", "code", "fingerprint", name="uq_dividend_observation_content"
        ),
    )
    op.create_index(
        "ix_dividend_observations_state_code", "dividend_source_observations", ["state", "code"]
    )
    op.create_table(
        "dividend_event_versions",
        sa.Column(
            "event_id",
            sa.String(36),
            sa.ForeignKey("dividend_events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("revision", sa.Integer, primary_key=True),
        sa.Column(
            "observation_id",
            sa.String(36),
            sa.ForeignKey("dividend_source_observations.id", ondelete="SET NULL"),
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_url", sa.Text),
        sa.Column("source_event_id", sa.String(128)),
        sa.Column("announcement_url", sa.Text),
        *[
            sa.Column(field, sa.Date)
            for field in (
                "report_date",
                "notice_date",
                "plan_notice_date",
                "record_date",
                "ex_date",
                "payment_date",
            )
        ],
        sa.Column("cash_per_share", sa.Numeric(20, 8)),
        sa.Column("plan", sa.Text, nullable=False),
        sa.Column("progress", sa.String(128), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("evidence_status", sa.String(32), nullable=False),
        sa.Column("review_reasons", JSONType, nullable=False),
        sa.Column("rule_version", sa.String(32), nullable=False),
        sa.Column("raw_payload", JSONType, nullable=False),
        sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("review_note", sa.Text, nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("dividend_event_versions")
    op.drop_index("ix_dividend_observations_state_code", "dividend_source_observations")
    op.drop_table("dividend_source_observations")
    op.drop_index("ix_dividend_events_code", "dividend_events")
    op.drop_table("dividend_events")
