"""Track one-time trials and entitlement provenance.

Revision ID: e6a2c9f08314
Revises: d4f1b8e6a923
"""
from alembic import op
import sqlalchemy as sa

revision = "e6a2c9f08314"
down_revision = "d4f1b8e6a923"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("trial_started_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("entitlement_source", sa.String(32)))
    # Keep active legacy expirations intact; retain consumption after a paid upgrade.
    op.execute("""
        UPDATE users SET trial_started_at = COALESCE(
            (SELECT MIN(redeemed_at) FROM redeem_codes
             WHERE redeemed_by = users.id AND plan = 'trial'), created_at)
        WHERE plan = 'trial' OR EXISTS (
            SELECT 1 FROM redeem_codes
            WHERE redeemed_by = users.id AND plan = 'trial')
    """)
    op.execute("""
        UPDATE users SET entitlement_source = CASE
            WHEN plan = 'trial' THEN 'legacy_trial'
            WHEN plan = 'member' THEN 'legacy'
            ELSE 'free' END
    """)
    # Unused trial codes enter the same seven-day, once-per-account flow.
    op.execute("UPDATE redeem_codes SET duration_days = 7 WHERE plan = 'trial' AND status = 'issued'")


def downgrade() -> None:
    op.drop_column("users", "entitlement_source")
    op.drop_column("users", "trial_started_at")
